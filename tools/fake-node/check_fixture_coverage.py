#!/usr/bin/env python3
"""Check fake-node fixture coverage against config/chains templates."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
CHAINS_DIR = REPO / "config" / "chains"
FAKE_NODE_DIR = REPO / "tools" / "fake-node"
DEFAULT_FIXTURES_DIR = FAKE_NODE_DIR / "fixtures"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def safe_name(value: str) -> str:
    value = value.replace("/", "_")
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "method"


def split_methods(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value or "").split(",") if v.strip()]


def chain_names(selected: str) -> list[str]:
    if selected == "all":
        return sorted(p.stem for p in CHAINS_DIR.glob("*.json"))
    return [c.strip() for c in selected.split(",") if c.strip()]


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
    path = FAKE_NODE_DIR / "configs" / f"{family}.yaml"
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chains", default="all", help="Comma-separated chain names, or all")
    parser.add_argument("--modes", default="single,mixed", help="Comma-separated: single,mixed")
    parser.add_argument("--fixtures-dir", default=str(DEFAULT_FIXTURES_DIR))
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of table")
    parser.add_argument("--strict", action="store_true", help="Require non-placeholder fixture plus successful request/response evidence")
    parser.add_argument("--allow-missing", action="store_true", help="Exit 0 even when coverage is incomplete")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    modes = {m.strip().lower() for m in args.modes.split(",") if m.strip()}
    fixtures_dir = Path(args.fixtures_dir)
    rows: list[dict[str, Any]] = []

    strict_rows_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    if args.strict:
        from validate_fixture_authenticity import build_rows
        for row in build_rows(modes):
            strict_rows_by_key[(row["chain"], row["method"])] = row

    fixture_maps: dict[str, dict[str, str]] = {}
    for chain in chain_names(args.chains):
        tpl_path = CHAINS_DIR / f"{chain}.json"
        if not tpl_path.exists():
            rows.append({"chain": chain, "family": "", "method": "", "status": "missing-template"})
            continue
        tpl = load_json(tpl_path)
        family = tpl.get("_meta", {}).get("adapter_family", "")
        fixture_map = fixture_maps.setdefault(family, load_fixture_map(family))
        for item in configured_methods(tpl, modes):
            method = item["method"]
            fixture = fixture_map.get(method)
            mapping_source = "yaml"
            if not fixture:
                fixture = f"{safe_name(method)}.json"
                mapping_source = "chain-template-default"
            path = fixtures_dir / chain / fixture
            status = "ok" if path.exists() else "missing-fixture"
            reason = ""
            if args.strict:
                strict_row = strict_rows_by_key.get((chain, method))
                if strict_row:
                    status = "ok" if strict_row["status"] == "real-recorded" else strict_row["status"]
                    reason = strict_row["reason"]
            rows.append({
                "chain": chain,
                "family": family,
                "method": method,
                "modes": item["modes"],
                "status": status,
                "reason": reason,
                "fixture": str(path.relative_to(fixtures_dir)),
                "mapping_source": mapping_source,
            })

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1

    if args.json:
        print(json.dumps({"total": len(rows), "statuses": counts, "rows": rows}, indent=2, sort_keys=True))
    else:
        print("fake-node fixture coverage")
        print(json.dumps({"total": len(rows), "statuses": counts}, indent=2, sort_keys=True))
        print("")
        print("| chain | family | method | modes | status | fixture |")
        print("|---|---|---|---|---|---|")
        for row in rows:
            print(
                f"| {row['chain']} | {row['family']} | `{row['method']}` | "
                f"{','.join(row.get('modes', []))} | {row['status']} | `{row.get('fixture', '')}` |"
            )

    incomplete = any(row["status"] != "ok" for row in rows)
    return 1 if incomplete and not args.allow_missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
