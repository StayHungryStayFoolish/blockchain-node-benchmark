#!/usr/bin/env python3
"""
W1.3 — chain template 二字段 (proxy_extraction + mixed_weighted) schema 校验

校验 spec §1.7 + §1.8 的所有硬约束:

proxy_extraction:
  - 顶层必须有 extractors 数组,非空
  - 每个 extractor.protocol ∈ {json_rpc, rest}
  - json_rpc: 必须含 method_source/id_source/params_source/url_pattern/batch_handling
  - json_rpc.batch_handling ∈ {reject, split, tag_batch}
  - json_rpc.auth.type ∈ {none, basic, bearer} (auth 可选)
  - rest: 必须含 url_patterns 数组,非空
  - rest.url_patterns[*]: 必须含 pattern + method_name
  - rest.url_patterns[*].pattern: 必须是合法正则

mixed_weighted:
  - 必须是数组,非空
  - 每项必须含 method (str, 非空) + weight (int, >0)

执行:python3 tests/test_chain_template_proxy_extraction.py
"""
import json
import re
import sys
from pathlib import Path

CHAINS_DIR = Path(__file__).parent.parent / "config" / "chains"

JSON_RPC_REQUIRED = {"method_source", "id_source", "params_source", "url_pattern", "batch_handling"}
BATCH_HANDLING_VALUES = {"reject", "split", "tag_batch"}
AUTH_TYPES = {"none", "basic", "bearer"}


def validate_proxy_extraction(chain: str, pe: dict, errors: list) -> None:
    if not isinstance(pe, dict):
        errors.append(f"[{chain}] proxy_extraction must be object")
        return
    extractors = pe.get("extractors")
    if not isinstance(extractors, list) or not extractors:
        errors.append(f"[{chain}] proxy_extraction.extractors must be non-empty array")
        return

    for i, ex in enumerate(extractors):
        tag = f"[{chain}].extractors[{i}]"
        if not isinstance(ex, dict):
            errors.append(f"{tag} must be object")
            continue
        proto = ex.get("protocol")
        if proto not in ("json_rpc", "rest"):
            errors.append(f"{tag}.protocol must be 'json_rpc' or 'rest', got {proto!r}")
            continue

        if proto == "json_rpc":
            missing = JSON_RPC_REQUIRED - set(ex.keys())
            if missing:
                errors.append(f"{tag} json_rpc missing fields: {sorted(missing)}")
            bh = ex.get("batch_handling")
            if bh not in BATCH_HANDLING_VALUES:
                errors.append(f"{tag}.batch_handling must be one of {BATCH_HANDLING_VALUES}, got {bh!r}")
            auth = ex.get("auth")
            if auth is not None:
                if not isinstance(auth, dict):
                    errors.append(f"{tag}.auth must be object")
                elif auth.get("type") not in AUTH_TYPES:
                    errors.append(f"{tag}.auth.type must be one of {AUTH_TYPES}, got {auth.get('type')!r}")

        elif proto == "rest":
            ups = ex.get("url_patterns")
            if not isinstance(ups, list) or not ups:
                errors.append(f"{tag} rest must have non-empty url_patterns array")
                continue
            for j, up in enumerate(ups):
                up_tag = f"{tag}.url_patterns[{j}]"
                if not isinstance(up, dict):
                    errors.append(f"{up_tag} must be object")
                    continue
                pattern = up.get("pattern")
                method_name = up.get("method_name")
                if not isinstance(pattern, str) or not pattern:
                    errors.append(f"{up_tag}.pattern must be non-empty string")
                else:
                    try:
                        re.compile(pattern)
                    except re.error as e:
                        errors.append(f"{up_tag}.pattern is invalid regex: {e}")
                if not isinstance(method_name, str) or not method_name:
                    errors.append(f"{up_tag}.method_name must be non-empty string")


def validate_mixed_weighted(chain: str, mw, errors: list) -> None:
    if not isinstance(mw, list) or not mw:
        errors.append(f"[{chain}] mixed_weighted must be non-empty array")
        return
    for i, item in enumerate(mw):
        tag = f"[{chain}].mixed_weighted[{i}]"
        if not isinstance(item, dict):
            errors.append(f"{tag} must be object")
            continue
        method = item.get("method")
        weight = item.get("weight")
        if not isinstance(method, str) or not method:
            errors.append(f"{tag}.method must be non-empty string")
        if not isinstance(weight, int) or isinstance(weight, bool) or weight <= 0:
            errors.append(f"{tag}.weight must be positive integer, got {weight!r}")


def main() -> int:
    chain_files = sorted(CHAINS_DIR.glob("*.json"))
    if not chain_files:
        print(f"NO chain files in {CHAINS_DIR}", file=sys.stderr)
        return 1

    errors: list = []
    chains_with_proxy = 0
    chains_with_weighted = 0

    for cf in chain_files:
        chain = cf.stem
        try:
            d = json.load(open(cf))
        except json.JSONDecodeError as e:
            errors.append(f"[{chain}] invalid JSON: {e}")
            continue

        pe = d.get("proxy_extraction")
        if pe is None:
            errors.append(f"[{chain}] missing proxy_extraction field")
        else:
            chains_with_proxy += 1
            validate_proxy_extraction(chain, pe, errors)

        mw = d.get("rpc_methods", {}).get("mixed_weighted")
        if mw is None:
            errors.append(f"[{chain}] missing rpc_methods.mixed_weighted field")
        else:
            chains_with_weighted += 1
            validate_mixed_weighted(chain, mw, errors)

    print(f"Total chains: {len(chain_files)}")
    print(f"  with proxy_extraction:  {chains_with_proxy}")
    print(f"  with mixed_weighted:    {chains_with_weighted}")
    print()

    if errors:
        print(f"✗ SCHEMA VALIDATION FAILED ({len(errors)} errors):")
        for e in errors[:50]:
            print(f"  {e}")
        if len(errors) > 50:
            print(f"  ... and {len(errors) - 50} more")
        return 2

    print(f"✓ ALL {len(chain_files)} CHAINS PASS SCHEMA VALIDATION")
    return 0


if __name__ == "__main__":
    sys.exit(main())
