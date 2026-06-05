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

    def _path_from_method_or_map(self, chain_name: str, method: str) -> tuple[str, str]:
        """返回 (http_method, path_template)。两种来源:
        ① method 名带 HTTP 动词前缀("GET /cosmos/.../{addr}")→ 拆出动词 + path
        ② method 名是逻辑名 → _meta.rest_paths[method] 映射(cardano GET_TIP→/tip)
        """
        m = method.strip()
        if m[:4].upper() in ("GET ", "POST") and " " in m:
            verb, path = m.split(" ", 1)
            return verb.upper(), path
        if m.startswith("/"):
            # method 名本身是 path(无 HTTP 动词前缀, 如 /cosmos/.../balances/{address})
            # → 默认 GET(tendermint LCD / cosmos REST 多为 GET 查询)
            return "GET", m
        # 逻辑名 → rest_paths 映射
        tpl = self._load_chain(chain_name)
        rest_paths = tpl.get("_meta", {}).get("rest_paths", {})
        if method in rest_paths:
            spec = rest_paths[method]
            return spec.get("method", "GET").upper(), spec["path"]
        raise ValueError(
            f"REST chain {chain_name}: method {method!r} 既非 'VERB /path' 形态, "
            f"也不在 _meta.rest_paths。Available rest_paths: {list(rest_paths)}"
        )

    def build_vegeta_target(
        self, method: str, inputs: dict, rpc_url: str, param_spec: dict,
    ) -> dict:
        """REST 声明式构造(批3b, S3.8): 按 param_spec transport 从 inputs 多池构造。

        path 来自 method 名("GET /cosmos/.../{addr}")或 _meta.rest_paths 映射。
        param_spec.transport:
          rest_path  — path 占位按 bindings 从 inputs 对应池取值替换(占位污染修复:
                       {hash} 从 tx_hash 池, {height} 从 block_height 池, 非全 account)
          rest_query — path + query string(bindings 替占位 + query 拼 ?k=v)
          rest_body  — POST body_template 占位从 inputs 池填
        """
        from .param_spec import _take, ParamSpecError
        chain_name = os.environ.get("BLOCKCHAIN_NODE", "").lower()
        if not chain_name:
            raise RuntimeError("RestAdapter requires BLOCKCHAIN_NODE env var")
        http_method, path = self._path_from_method_or_map(chain_name, method)
        transport = param_spec.get("transport", "rest_path")

        # ── path 占位替换(bindings 声明每个占位的 source 池)──
        bindings = param_spec.get("bindings", {})
        placeholders = re.findall(r"\{(\w+)\}", path)
        for ph in placeholders:
            bind = bindings.get(ph)
            if bind is None:
                # 兼容历史: path 占位无 bindings 声明 → 默认 account 池(占位污染过渡)
                val = _take(inputs, "account", 0)
            elif bind.get("source") == "literal":
                val = str(bind["value"])
            else:
                val = str(_take(inputs, bind["source"], 0))
            path = path.replace("{" + ph + "}", val)

        base = rpc_url.rstrip("/")
        if not path.startswith("/"):
            path = "/" + path
        full_url = base + path

        # ── rest_query: 拼 query string ──
        if transport == "rest_query":
            query = param_spec.get("query", {})
            qs = []
            for qk, qv in query.items():
                if qv.get("source") == "literal":
                    qs.append(f"{qk}={qv['value']}")
                else:
                    qs.append(f"{qk}={_take(inputs, qv['source'], 0)}")
            if qs:
                sep = "&" if "?" in full_url else "?"
                full_url = full_url + sep + "&".join(qs)
            return _vegeta_get(full_url)

        # ── rest_body: POST body 模板从 inputs 池填 ──
        if transport == "rest_body":
            body_template = param_spec.get("body_template", {})
            body_str = json.dumps(body_template)
            # 替换 {account}/{tx_hash}/{block_height}/{policy}/{asset_name} 等占位
            for src in ("account", "tx_hash", "block_height"):
                if "{" + src + "}" in body_str:
                    body_str = body_str.replace("{" + src + "}", str(_take(inputs, src, 0)))
            # business 占位(policy/asset_name 等)从 business_id 池取; 池空 fail-fast
            # (不退 account — policy_id/asset_name 是资产标识非地址, 退 account 会填错值,
            #  2026-06-05 自检发现的真 bug)。批4 补 business_id 池后真值生效。
            for biz in re.findall(r"\{(policy|asset_name|workchain|shard|seqno)\}", body_str):
                val = _take(inputs, "business_id", 0)
                body_str = body_str.replace("{" + biz + "}", str(val))
            body = json.loads(body_str)
            return _vegeta_post_json(full_url, body)

        # ── rest_path(默认): 占位已替换, GET ──
        if http_method == "POST":
            return _vegeta_post_json(full_url, {})
        return _vegeta_get(full_url)

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
