#!/usr/bin/env python3
"""Validate whether fake-node fixtures are real recorded RPC responses."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
CHAINS_DIR = REPO / "config" / "chains"
FIXTURES_DIR = REPO / "tools" / "fake-node" / "fixtures"
EVIDENCE_DIR = REPO / "docs" / "audit" / "rpc-fixtures"
FAKE_NODE_CONFIGS_DIR = REPO / "tools" / "fake-node" / "configs"
PLACEHOLDER_MARKERS = ("placeholder", "needs_real_recording", "\u5360\u4f4d")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def safe_name(value: str) -> str:
    value = value.replace("/", "_")
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "method"


def split_methods(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value or "").split(",") if v.strip()]


def configured_methods(tpl: dict[str, Any], modes: set[str]) -> list[dict[str, Any]]:
    rpc_methods = tpl.get("rpc_methods", {})
    by_method: dict[str, dict[str, Any]] = {}

    if "single" in modes:
        method = str(rpc_methods.get("single", "")).strip()
        if method:
            by_method.setdefault(method, {"method": method, "modes": [], "weight": 1})
            by_method[method]["modes"].append("single")

    if "mixed" in modes:
        weighted = rpc_methods.get("mixed_weighted") or []
        if isinstance(weighted, list) and weighted:
            for item in weighted:
                if not isinstance(item, dict):
                    continue
                method = str(item.get("method", "")).strip()
                if not method:
                    continue
                entry = by_method.setdefault(method, {"method": method, "modes": [], "weight": 0})
                entry["modes"].append("mixed")
                try:
                    entry["weight"] = max(entry["weight"], int(item.get("weight", 1)))
                except (TypeError, ValueError):
                    entry["weight"] = max(entry["weight"], 1)
        else:
            for method in split_methods(rpc_methods.get("mixed", "")):
                entry = by_method.setdefault(method, {"method": method, "modes": [], "weight": 1})
                entry["modes"].append("mixed")
    return sorted(by_method.values(), key=lambda x: x["method"])


def load_fixture_map(family: str) -> dict[str, str]:
    path = FAKE_NODE_CONFIGS_DIR / f"{family}.yaml"
    if not path.exists():
        return {}
    mapping: dict[str, str] = {}
    in_methods = False
    current: str | None = None
    for line in path.read_text().splitlines():
        raw = line.split("#", 1)[0].rstrip()
        if not raw.strip():
            continue
        if raw.strip() == "methods:":
            in_methods = True
            current = None
            continue
        if in_methods and not raw.startswith(" "):
            break
        if not in_methods:
            continue
        method_match = re.match(r"^  ([^:\n]+):\s*$", raw)
        if method_match:
            current = method_match.group(1).strip().strip("'\"")
            continue
        fixture_match = re.match(r"^\s+fixture:\s*(.+?)\s*$", raw)
        if fixture_match and current:
            mapping[current] = fixture_match.group(1).strip().strip("'\"")
    return mapping


def method_dir_name(method: str) -> str:
    return safe_name(method)


def fixture_rel(chain: str, family: str, method: str, fixture_maps: dict[str, dict[str, str]]) -> str:
    fmap = fixture_maps.setdefault(family, load_fixture_map(family))
    return f"{chain}/{fmap.get(method, safe_name(method) + '.json')}"


def contains_placeholder(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(errors="replace").lower()
    return any(marker in text for marker in PLACEHOLDER_MARKERS)


def response_semantic_ok(response: dict[str, Any]) -> tuple[bool, str]:
    if not response.get("ok"):
        return False, "response-not-ok"
    status = response.get("http_status")
    if not isinstance(status, int) or not 200 <= status < 400:
        return False, "http-not-success"
    parsed = response.get("json")
    if isinstance(parsed, dict):
        if parsed.get("error") is not None:
            return False, "rpc-error"
        if parsed.get("errors") is not None:
            return False, "rpc-errors"
        message = str(parsed.get("message", "")).lower()
        if message and any(word in message for word in ("error", "invalid", "not found", "forbidden", "unauthorized")):
            return False, "error-message"
    body_text = str(response.get("body_text", "")).lower()
    if any(marker in body_text for marker in PLACEHOLDER_MARKERS):
        return False, "placeholder-response"
    return True, "ok"


def build_rows(modes: set[str]) -> list[dict[str, Any]]:
    fixture_maps: dict[str, dict[str, str]] = {}
    rows: list[dict[str, Any]] = []
    for tpl_path in sorted(CHAINS_DIR.glob("*.json")):
        chain = tpl_path.stem
        tpl = load_json(tpl_path)
        family = tpl.get("_meta", {}).get("adapter_family", "")
        for item in configured_methods(tpl, modes):
            method = item["method"]
            rel = fixture_rel(chain, family, method, fixture_maps)
            fixture_path = FIXTURES_DIR / rel
            evidence_dir = EVIDENCE_DIR / chain / method_dir_name(method)
            request_path = evidence_dir / "request.json"
            response_path = evidence_dir / "response.json"
            meta_path = evidence_dir / "meta.json"

            status = "real-recorded"
            reason = "ok"
            response_status = None
            if not fixture_path.exists():
                status, reason = "missing-fixture", "fixture-file-missing"
            elif contains_placeholder(fixture_path):
                status, reason = "placeholder", "placeholder-fixture"
            elif not request_path.exists() or not response_path.exists() or not meta_path.exists():
                status, reason = "missing-evidence", "request-response-meta-required"
            else:
                try:
                    response = load_json(response_path)
                    response_status = response.get("http_status")
                    ok, reason = response_semantic_ok(response)
                    if not ok:
                        status = "failed-recording"
                except Exception as exc:
                    status, reason = "invalid-evidence", str(exc)

            rows.append({
                "chain": chain,
                "family": family,
                "method": method,
                "modes": item["modes"],
                "fixture": rel,
                "status": status,
                "reason": reason,
                "http_status": response_status,
                "evidence_dir": str(evidence_dir.relative_to(REPO)),
            })
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modes", default="single,mixed")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write-report", default=str(EVIDENCE_DIR / "authenticity-report.json"))
    parser.add_argument("--write-manifest", default=str(EVIDENCE_DIR / "manifest.json"))
    parser.add_argument("--allow-incomplete", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    modes = {m.strip().lower() for m in args.modes.split(",") if m.strip()}
    rows = build_rows(modes)
    counts = Counter(row["status"] for row in rows)

    Path(args.write_report).write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
    manifest_rows = [row for row in rows if row["status"] == "real-recorded"]
    Path(args.write_manifest).write_text(json.dumps(manifest_rows, indent=2, ensure_ascii=False) + "\n")

    payload = {
        "total": len(rows),
        "statuses": dict(sorted(counts.items())),
        "real_recorded": len(manifest_rows),
        "incomplete": len(rows) - len(manifest_rows),
        "report": str(Path(args.write_report)),
        "manifest": str(Path(args.write_manifest)),
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print("rpc fixture authenticity")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print("")
        print("| chain | method | status | reason | fixture |")
        print("|---|---|---|---|---|")
        for row in rows:
            if row["status"] != "real-recorded":
                print(f"| {row['chain']} | `{row['method']}` | {row['status']} | {row['reason']} | `{row['fixture']}` |")

    return 1 if payload["incomplete"] and not args.allow_incomplete else 0


if __name__ == "__main__":
    raise SystemExit(main())
