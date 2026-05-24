"""OgmiosAdapter — Cardano via Ogmios HTTP bridge.

Covers 1 chain: Cardano.

Protocol: Ogmios (https://ogmios.dev/) is JSON-RPC 2.0 over either
WebSocket or HTTP POST. For benchmarking we use HTTP POST.

Method convention: "queryNetwork/tip", "queryLedgerState/utxo", etc.
Params are object form.

Health probe = "queryNetwork/tip" → .result.slot or .result.height
"""
from __future__ import annotations
import json
from typing import Optional

from .base import ChainAdapter, register, _vegeta_post_json, _try_int


@register("ogmios")
class OgmiosAdapter(ChainAdapter):

    def build_vegeta_target(
        self, method: str, address: str, rpc_url: str, param_format: str = "",
    ) -> dict:
        params = self._build_params(param_format, address)
        body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        return _vegeta_post_json(rpc_url, body)

    @staticmethod
    def _build_params(param_format: str, address: str) -> dict:
        if param_format in ("no_params", ""):
            return {}
        if param_format == "single_address":
            return {"addresses": [address]}
        if param_format == "utxo_address":
            return {"addresses": [address]}
        if param_format == "transaction_id":
            return {"id": address}
        return {"address": address}

    def health_check_request(self, rpc_url: str) -> dict:
        body = {"jsonrpc": "2.0", "id": 1, "method": "queryNetwork/tip", "params": {}}
        return {
            "method": "POST",
            "url": rpc_url,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body, separators=(",", ":")),
            "parse_jq": ".result.height // .result.slot",
        }

    def parse_block_height(self, response_text: str) -> Optional[int]:
        if not response_text:
            return None
        try:
            obj = json.loads(response_text)
        except json.JSONDecodeError:
            return None
        result = obj.get("result")
        if not isinstance(result, dict):
            return None
        # Prefer height, fall back to slot
        for key in ("height", "slot", "blockHeight"):
            v = result.get(key)
            if v is not None:
                parsed = _try_int(v)
                if parsed is not None:
                    return parsed
        return None
