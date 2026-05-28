#!/usr/bin/env python3
"""
W1.1 — chain template 批量填 proxy_extraction 字段 (NS-3 + Q4-12)

按 _meta.adapter_family 选 extractor 模板:
  - jsonrpc / substrate / tendermint   → 1 个 json_rpc extractor (默认 split)
  - bitcoin_jsonrpc                    → 1 个 json_rpc extractor + auth.basic
  - rest                               → 1 个 rest extractor + 各链 rest_paths 全量 url_patterns
  - hedera_dual                        → 2 个 extractor (rest + json_rpc)

幂等:已有 proxy_extraction 字段的链跳过。
"""
import json
import sys
from pathlib import Path

CHAINS_DIR = Path(__file__).parent.parent / "config" / "chains"


def build_json_rpc_extractor(auth_type: str = "none") -> dict:
    e: dict = {
        "protocol": "json_rpc",
        "method_source": "body.method",
        "id_source": "body.id",
        "params_source": "body.params",
        "url_pattern": "^/$",
        "batch_handling": "split",
    }
    if auth_type != "none":
        e["auth"] = {"type": auth_type}
    return e


def build_rest_extractor(rest_paths: dict) -> dict:
    """Convert _meta.rest_paths -> list of url_patterns with method_name.

    rest_paths key format: 'GET /v1/foo/{addr}' or 'POST /v1/bar'.
    Output url_pattern: anchored regex from path, placeholders -> '[^/]+'.
    method_name: the original key (preserved as semantic label).
    """
    import re
    patterns = []
    for key, spec in rest_paths.items():
        # path 字段在 v1 schema 里都是统一的 {address} (见 rest.py:69)
        # 但 url_pattern 要匹配真实请求,所以从 key 提取实际占位符做泛化
        path_template = spec.get("path", "")
        # 把任意 {xxx} 替换成 '[^/]+' (单段 URL 不含斜杠的任意字符)
        pattern_body = re.sub(r"\{[^}]+\}", "[^/]+", path_template)
        # query string 处理: 把 '?...={address}' 后缀剥掉, query 不进 URL pattern
        # (proxy 只看 path; query 的 method 区分通过 url_patterns list 区分)
        pattern_body = pattern_body.split("?")[0]
        # 锚定
        pattern = f"^{pattern_body}$"
        patterns.append({
            "pattern": pattern,
            "method_name": key,
        })
    return {
        "protocol": "rest",
        "url_patterns": patterns,
    }


def build_hedera_dual_extractors() -> list:
    """Hedera = Mirror REST (api/v1/...) + EVM Relay (json_rpc /).

    Two extractors, REST first (URL-specific), JSON-RPC fallback (matches /).
    """
    return [
        {
            "protocol": "rest",
            "url_patterns": [
                {"pattern": "^/api/v1/accounts/[^/]+$", "method_name": "GET_ACCOUNT"},
                {"pattern": "^/api/v1/transactions/[^/]+$", "method_name": "GET_TRANSACTION"},
                {"pattern": "^/api/v1/balances$", "method_name": "GET_BALANCES"},
                {"pattern": "^/api/v1/blocks/[^/]+$", "method_name": "GET_BLOCK"},
            ],
        },
        build_json_rpc_extractor(),
    ]


def fill_chain(chain_file: Path) -> tuple[bool, str]:
    """Returns (changed, reason)."""
    with open(chain_file) as f:
        d = json.load(f)

    if "proxy_extraction" in d:
        return False, "already has proxy_extraction"

    family = d.get("_meta", {}).get("adapter_family")
    if not family:
        return False, "MISSING _meta.adapter_family"

    if family in ("jsonrpc", "substrate", "tendermint"):
        d["proxy_extraction"] = {"extractors": [build_json_rpc_extractor()]}
    elif family == "bitcoin_jsonrpc":
        d["proxy_extraction"] = {"extractors": [build_json_rpc_extractor(auth_type="basic")]}
    elif family == "rest":
        rest_paths = d.get("_meta", {}).get("rest_paths", {})
        if not rest_paths:
            return False, "rest family but no _meta.rest_paths"
        d["proxy_extraction"] = {"extractors": [build_rest_extractor(rest_paths)]}
    elif family == "hedera_dual":
        d["proxy_extraction"] = {"extractors": build_hedera_dual_extractors()}
    elif family == "ogmios":
        return False, "ogmios family deprecated (Q4-12), should be migrated to rest"
    else:
        return False, f"unknown family: {family}"

    with open(chain_file, "w") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return True, f"filled ({family})"


def main():
    chain_files = sorted(CHAINS_DIR.glob("*.json"))
    if not chain_files:
        print(f"NO chain files in {CHAINS_DIR}", file=sys.stderr)
        return 1

    filled = 0
    skipped = 0
    errors = []
    for cf in chain_files:
        changed, reason = fill_chain(cf)
        if changed:
            filled += 1
            print(f"  ✓ {cf.name}: {reason}")
        else:
            if "already" in reason or "deprecated" in reason:
                skipped += 1
                print(f"  - {cf.name}: SKIP ({reason})")
            else:
                errors.append((cf.name, reason))
                print(f"  ✗ {cf.name}: ERROR ({reason})")

    print()
    print(f"Summary: filled={filled} skipped={skipped} errors={len(errors)} total={len(chain_files)}")
    if errors:
        print("\nErrors:")
        for n, r in errors:
            print(f"  {n}: {r}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
