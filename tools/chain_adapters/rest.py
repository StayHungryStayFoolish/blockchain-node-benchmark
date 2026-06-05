"""RestAdapter — RESTful HTTP API (path templates, GET/POST mix).

Covers 5 chains: Aptos / Algorand / Hedera / TON / Tezos.

Method convention (chain template rpc_methods.single):
    For REST chains, `rpc_methods.single` holds a method NAME (not RPC),
    which the adapter maps to an HTTP path template containing {address}.

Examples:
    aptos:    "GET_ACCOUNT"          → GET  /v1/accounts/{address}
    algorand: "GET_ACCOUNT"          → GET  /v2/accounts/{address}
    hedera:   "GET_ACCOUNT"          → GET  /api/v1/accounts/{address}
    ton:      "GET_ACCOUNT"          → GET  /api/v2/getAddressInformation?address={address}
    tezos:    "GET_BLOCK_HEAD"       → GET  /chains/main/blocks/head

Health probe = standardized "get latest block" per chain.

Path templates are per-chain — adapter looks them up via _meta.rest_paths in
chain template:

    "_meta": {
        "adapter_family": "rest",
        "rest_paths": {
            "GET_ACCOUNT":     {"method": "GET", "path": "/v1/accounts/{address}"},
            "GET_BLOCK_HEIGHT": {"method": "GET", "path": "/v1"}
        }
    }
"""
from __future__ import annotations
import json
import os
import re
from pathlib import Path
from typing import Optional

from .base import ChainAdapter, register, _vegeta_get, _vegeta_post_json, _try_int

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CHAINS_DIR = _REPO_ROOT / "config" / "chains"


@register("rest")
class RestAdapter(ChainAdapter):

    def __init__(self):
        self._chain_cache: dict[str, dict] = {}

    def _load_chain(self, chain_name: str) -> dict:
        if chain_name not in self._chain_cache:
            with open(_CHAINS_DIR / f"{chain_name}.json") as f:
                self._chain_cache[chain_name] = json.load(f)
        return self._chain_cache[chain_name]

    def _resolve_path(self, chain_name: str, method: str, address: str) -> tuple[str, str, dict | None]:
        """Return (http_method, path_with_substituted_address, body_dict_or_None).

        body comes from optional `_meta.rest_paths[method].body` template.
        Body may contain placeholders ({address}, {addresses_array}) which are
        substituted; pass `None` for GET methods.
        """
        tpl = self._load_chain(chain_name)
        rest_paths = tpl.get("_meta", {}).get("rest_paths", {})
        if method not in rest_paths:
            raise ValueError(
                f"REST chain {chain_name}: method {method!r} not in _meta.rest_paths. "
                f"Available: {list(rest_paths)}"
            )
        spec = rest_paths[method]
        path = spec["path"].replace("{address}", address)
        body = None
        if "body" in spec:
            # Deep-substitute {address} / {addresses_array} inside body template
            body_template = spec["body"]
            body_json_str = json.dumps(body_template)
            body_json_str = body_json_str.replace("{address}", address)
            # Special: PostgREST-style array fields like _addresses, _tx_hashes
            # may be templated as ["{address}"] to receive the single account.
            body = json.loads(body_json_str)
        return spec.get("method", "GET"), path, body

    def build_vegeta_target(
        self, method: str, inputs: dict, rpc_url: str, param_spec: dict,
    ) -> dict:
        """For REST, `method` is a logical method NAME mapped via _meta.rest_paths.
        rpc_url base is the chain's base URL (LOCAL_RPC_URL). The full URL is
        rpc_url + path. The chain name is taken from BLOCKCHAIN_NODE env var
        (master_qps_executor sets this).

        批1 过渡: 签名统一为 (inputs, param_spec); 内部用兼容 address 替换 {address}。
        REST path 占位参数({addr}/{hash}/{height})路由是 S3.8 待修(归 S2/S3 REST 处理)。
        """
        from .base import _account_from_inputs
        address = _account_from_inputs(inputs)
        chain_name = os.environ.get("BLOCKCHAIN_NODE", "").lower()
        if not chain_name:
            raise RuntimeError("RestAdapter requires BLOCKCHAIN_NODE env var")
        http_method, path, body = self._resolve_path(chain_name, method, address)
        # Strip trailing slash from rpc_url, ensure path starts with /
        base = rpc_url.rstrip("/")
        if not path.startswith("/"):
            path = "/" + path
        full_url = base + path
        if http_method.upper() == "GET":
            return _vegeta_get(full_url)
        else:
            # ADR-0005 fix: read body from _meta.rest_paths[method].body template
            # (falls back to empty dict to preserve old behavior for chains that
            # haven't declared a body template yet).
            return _vegeta_post_json(full_url, body if body is not None else {})

    def health_check_request(self, rpc_url: str) -> dict:
        """REST health probe varies per chain. Default: GET / (root).
        Per-chain override via _meta.health_probe in chain template:
            {"method": "GET", "path": "/v1", "parse_jq": ".block_height"}
        """
        chain_name = os.environ.get("BLOCKCHAIN_NODE", "").lower()
        probe = {}
        if chain_name:
            tpl = self._load_chain(chain_name)
            probe = tpl.get("_meta", {}).get("health_probe", {})
        method = probe.get("method", "GET")
        path = probe.get("path", "/")
        parse_jq = probe.get("parse_jq", ".block_height // .height // .level")
        base = rpc_url.rstrip("/")
        if not path.startswith("/"):
            path = "/" + path
        return {
            "method": method,
            "url": base + path,
            "headers": {},
            "body": "",
            "parse_jq": parse_jq,
        }

    def parse_block_height(self, response_text: str) -> Optional[int]:
        """Try multiple common JSON paths."""
        if not response_text:
            return None
        try:
            obj = json.loads(response_text)
        except json.JSONDecodeError:
            return None
        for key in ("block_height", "height", "level", "ledger_index",
                    "last-round", "blockHeight", "block_no"):
            v = obj.get(key) if isinstance(obj, dict) else None
            if v is not None:
                parsed = _try_int(v)
                if parsed is not None:
                    return parsed
        # Tezos returns the full block header — try .header.level
        if isinstance(obj, dict):
            header = obj.get("header")
            if isinstance(header, dict):
                return _try_int(header.get("level"))
        # Cardano (Koios /tip) returns a JSON array — try first element's
        # block_no / block_height / abs_slot fallback (ADR-0005).
        if isinstance(obj, list) and obj:
            first = obj[0]
            if isinstance(first, dict):
                for key in ("block_no", "block_height", "height", "abs_slot"):
                    v = first.get(key)
                    if v is not None:
                        parsed = _try_int(v)
                        if parsed is not None:
                            return parsed
        return None
