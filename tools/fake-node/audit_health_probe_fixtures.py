#!/usr/bin/env python3
"""Audit fake-node fixtures used by adapter health probes."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
CHAINS_DIR = REPO / "config" / "chains"
FIXTURES_DIR = REPO / "tools" / "fake-node" / "fixtures"
EVIDENCE_DIR = REPO / "docs" / "audit" / "rpc-fixtures"
CONFIGS_DIR = REPO / "tools" / "fake-node" / "configs"
CLI = REPO / "tools" / "chain_adapters" / "cli.py"
PLACEHOLDER_MARKERS = ("placeholder", "needs_real_recording", "\u5360\u4f4d")


def safe_name(value: str) -> str:
    value = value.replace("/", "_")
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "method"


def method_dir(value: str) -> str:
    return safe_name(value)


def load_fixture_map(family: str) -> dict[str, str]:
    path = CONFIGS_DIR / f"{family}.yaml"
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


def candidate_fixtures(chain: str, family: str, method: str, fmap: dict[str, str]) -> list[str]:
    candidates: list[str] = []
    if method in fmap:
        candidates.append(fmap[method])
    candidates.append(safe_name(method) + ".json")

    if " " in method:
        verb, path = method.split(" ", 1)
        path_no_query = path.split("?", 1)[0]
        path_candidates = [
            path_no_query,
            path_no_query.strip("/"),
            safe_name(path_no_query) + ".json",
            safe_name(f"{verb} {path_no_query}") + ".json",
        ]
        for key, fixture in fmap.items():
            key_path = key.split(" ", 1)[-1] if " " in key else key
            if key == method or key_path == path or key_path == path_no_query:
                candidates.append(fixture)
        candidates.extend(path_candidates)

    if family == "rest":
        fallback_names = {
            "cardano": ["tip.json"],
            "ton": ["GET__lookupBlock_workchain_-1_shard_-9223372036854775808_seqno_72033975.json"],
        }
        candidates.extend(fallback_names.get(chain, []))
    if family == "tendermint":
        if method.endswith("/status"):
            candidates.append("status.json")
        if method.endswith("/blocks/latest"):
            candidates.append("block.json")
    if family == "hedera_dual":
        candidates.append("GET__api_v1_accounts__addr.json")
        candidates.append("mirror/network_nodes.json")

    out: list[str] = []
    seen = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            out.append(candidate)
    return out


def adapter_health_probe(chain: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(CLI), "health-probe", "--chain", chain, "--rpc-url", "http://127.0.0.1:19000"],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(proc.stdout)


def health_method(probe: dict[str, Any]) -> tuple[str, bool]:
    body = probe.get("body") or ""
    try:
        parsed = json.loads(body) if body else {}
    except json.JSONDecodeError:
        parsed = {}
    if isinstance(parsed, dict) and parsed.get("method"):
        return str(parsed["method"]), True
    url = str(probe.get("url") or "")
    path = url.split("19000", 1)[-1] or "/"
    return f"{probe.get('method', 'GET')} {path}", False


def has_placeholder(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(errors="replace").lower()
    return any(marker in text for marker in PLACEHOLDER_MARKERS)


def build_rows() -> list[dict[str, Any]]:
    fixture_maps: dict[str, dict[str, str]] = {}
    rows: list[dict[str, Any]] = []
    for tpl_path in sorted(CHAINS_DIR.glob("*.json")):
        chain = tpl_path.stem
        tpl = json.loads(tpl_path.read_text())
        family = str(tpl.get("_meta", {}).get("adapter_family", ""))
        fmap = fixture_maps.setdefault(family, load_fixture_map(family))
        probe = adapter_health_probe(chain)
        method, evidence_required = health_method(probe)
        fixture = ""
        fixture_path = FIXTURES_DIR / chain / "__missing__"
        candidates = candidate_fixtures(chain, family, method, fmap)
        for candidate in candidates:
            candidate_path = FIXTURES_DIR / chain / candidate
            if candidate_path.exists():
                fixture = candidate
                fixture_path = candidate_path
                break
        if not fixture:
            fixture = candidates[0] if candidates else safe_name(method) + ".json"
            fixture_path = FIXTURES_DIR / chain / fixture

        status = "ok"
        reason = "ok"
        if not fixture_path.exists():
            status, reason = "missing-fixture", "fixture-file-missing"
        elif has_placeholder(fixture_path):
            status, reason = "placeholder", "placeholder-marker"

        evidence_status = "not-required-for-rest-derived-health"
        if evidence_required:
            evidence_dir = EVIDENCE_DIR / chain / method_dir(method)
            evidence_status = (
                "ok"
                if all((evidence_dir / name).exists() for name in ("request.json", "response.json", "meta.json"))
                else "missing-evidence"
            )

        rows.append({
            "chain": chain,
            "family": family,
            "health_method": method,
            "parse_jq": probe.get("parse_jq"),
            "fixture": f"{chain}/{fixture}",
            "candidate_fixtures": [f"{chain}/{candidate}" for candidate in candidates],
            "status": status,
            "reason": reason,
            "evidence_status": evidence_status,
        })
    return rows


def main() -> int:
    rows = build_rows()
    payload = {
        "summary": {
            "total": len(rows),
            "status": dict(sorted(Counter(row["status"] for row in rows).items())),
            "evidence_status": dict(sorted(Counter(row["evidence_status"] for row in rows).items())),
        },
        "bad": [
            row for row in rows
            if row["status"] != "ok" or row["evidence_status"] == "missing-evidence"
        ],
        "rows": rows,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 1 if payload["bad"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
