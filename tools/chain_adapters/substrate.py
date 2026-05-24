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


@register("substrate")
class SubstrateAdapter(ChainAdapter):

    def build_vegeta_target(
        self, method: str, address: str, rpc_url: str, param_format: str = "",
    ) -> dict:
        params = self._build_params(param_format, address)
        body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        return _vegeta_post_json(rpc_url, body)

    @staticmethod
    def _build_params(param_format: str, address: str) -> list:
        if param_format in ("no_params", ""):
            return []
        if param_format == "single_address":
            return [address]
        if param_format == "storage_key":
            # state_getStorage: [storage_key, block_hash?]
            return [address]
        if param_format == "block_hash":
            return [address]
        if param_format == "address_with_block":
            return [address, None]
        return [address]

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
