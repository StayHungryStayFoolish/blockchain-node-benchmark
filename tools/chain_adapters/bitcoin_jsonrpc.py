"""BitcoinJsonRpcAdapter — Bitcoin Core JSON-RPC family.

Covers 4 chains: Bitcoin / Litecoin / Dogecoin / Bitcoin-Cash.

Differences from standard JsonRpc:
    - Requires HTTP Basic Auth (rpcuser:rpcpassword)
    - Params are positional array (like JsonRpc) but no `jsonrpc` field is
      required by Bitcoin Core (it accepts both 1.0 and 2.0 form);
      we use 2.0 form for consistency
    - Health probe = `getblockcount` → .result is decimal int

Auth handling:
    BITCOIN_RPC_USER and BITCOIN_RPC_PASSWORD env vars (or read from
    _meta.basic_auth in chain template).
"""
from __future__ import annotations
import base64
import json
import os
from typing import Optional

from .base import ChainAdapter, register, _vegeta_post_json, _try_int, _b64
from .param_spec import build_params_from_spec


@register("bitcoin_jsonrpc")
class BitcoinJsonRpcAdapter(ChainAdapter):

    def _auth_header(self) -> Optional[str]:
        user = os.environ.get("BITCOIN_RPC_USER", "")
        pwd = os.environ.get("BITCOIN_RPC_PASSWORD", "")
        if not user:
            return None
        creds = base64.b64encode(f"{user}:{pwd}".encode()).decode()
        return f"Basic {creds}"

    def build_vegeta_target(
        self, method: str, inputs: dict, rpc_url: str, param_spec: dict,
    ) -> dict:
        # 批3a: 切 param_spec 真构造器(bitcoin 全 method 枚举已在 PARAM_FORMAT_PRESETS,
        # jsonrpc_list 类)。删除老 _build_params 枚举 if-else。
        params = build_params_from_spec(param_spec, inputs)
        body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        body_str = json.dumps(body, separators=(",", ":"))
        header = {"Content-Type": ["application/json"]}
        auth = self._auth_header()
        if auth:
            header["Authorization"] = [auth]
        return {
            "method": "POST",
            "url": rpc_url,
            "header": header,
            "body": _b64(body_str),
        }

    def health_check_request(self, rpc_url: str) -> dict:
        body = {"jsonrpc": "2.0", "id": 1, "method": "getblockcount", "params": []}
        headers = {"Content-Type": "application/json"}
        auth = self._auth_header()
        if auth:
            headers["Authorization"] = auth
        return {
            "method": "POST",
            "url": rpc_url,
            "headers": headers,
            "body": json.dumps(body, separators=(",", ":")),
            "parse_jq": ".result",
        }

    def parse_block_height(self, response_text: str) -> Optional[int]:
        if not response_text:
            return None
        try:
            obj = json.loads(response_text)
        except json.JSONDecodeError:
            return None
        return _try_int(obj.get("result"))
