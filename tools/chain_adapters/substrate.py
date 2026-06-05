"""SubstrateAdapter — Substrate-based parachains.

Covers 5 chains: Polkadot / Kusama / Acala / Moonbeam / Astar.

Protocol: JSON-RPC 2.0 POST with positional array params.
Method namespace: state_*, chain_*, system_*, etc.

Examples:
    chain_getHeader            → params: [block_hash?]
    state_getStorage           → params: [storage_key, block_hash?]
    system_chain               → params: []

Health probe = `chain_getHeader` (no params) → .result.number is 0x-hex.
"""
from __future__ import annotations
import json
from typing import Optional

from .base import ChainAdapter, register, _vegeta_post_json, _try_int
from .param_spec import build_params_from_spec


@register("substrate")
class SubstrateAdapter(ChainAdapter):

    def build_vegeta_target(
        self, method: str, inputs: dict, rpc_url: str, param_spec: dict,
    ) -> dict:
        # 批3a: 切 param_spec 真构造器(substrate jsonrpc_list 类枚举已在 PRESETS)。
        # path_* 类 method(polkadot Sidecar)走批3b REST 构造, 在此 fail-fast(归批3b)。
        params = build_params_from_spec(param_spec, inputs)
        body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        return _vegeta_post_json(rpc_url, body)

    def health_check_request(self, rpc_url: str) -> dict:
        """Substrate health = `chain_getHeader` (no params) → result.number is 0x-hex."""
        body = {"jsonrpc": "2.0", "id": 1, "method": "chain_getHeader", "params": []}
        return {
            "method": "POST",
            "url": rpc_url,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body, separators=(",", ":")),
            "parse_jq": ".result.number",
        }

    def parse_block_height(self, response_text: str) -> Optional[int]:
        if not response_text:
            return None
        try:
            obj = json.loads(response_text)
        except json.JSONDecodeError:
            return None
        try:
            number = obj["result"]["number"]
            return _try_int(number)
        except (KeyError, TypeError):
            return None
