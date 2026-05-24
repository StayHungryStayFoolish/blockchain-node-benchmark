"""TendermintAdapter — Tendermint/Cosmos SDK chains.

Covers 5 chains: Cosmos-Hub / Osmosis / Celestia / Injective / Sei.

Protocol: JSON-RPC-like but params are an OBJECT keyed by field name (not array).
Endpoint structure differs between:
    Tendermint RPC (port 26657): /status, /block, /abci_query
    Cosmos REST  (port 1317):    /cosmos/bank/v1beta1/balances/{address}

For benchmarking we use Tendermint RPC POST JSON-RPC 2.0 form:
    POST /
    Content-Type: application/json
    {"jsonrpc":"2.0","id":1,"method":"abci_query","params":{"path":"/cosmos.bank.v1beta1.Query/Balance","data":"...","prove":false}}

Health probe = `status` method → .result.sync_info.latest_block_height (string of int).
"""
from __future__ import annotations
import json
import os
from typing import Optional

from .base import ChainAdapter, register, _vegeta_post_json, _try_int


@register("tendermint")
class TendermintAdapter(ChainAdapter):

    def build_vegeta_target(
        self, method: str, address: str, rpc_url: str, param_format: str = "",
    ) -> dict:
        """Tendermint RPC: POST JSON-RPC with object params.

        param_format conventions:
            no_params          → params: {}
            single_address     → params: {"address": "<addr>"} (caller-chain-specific)
            height_param       → params: {"height": "<addr>"} (block-height query, address holds height)
        """
        params = self._build_params(param_format, address)
        body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        return _vegeta_post_json(rpc_url, body)

    @staticmethod
    def _build_params(param_format: str, address: str) -> dict:
        if param_format in ("no_params", ""):
            return {}
        if param_format == "single_address":
            return {"address": address}
        if param_format == "height_param":
            return {"height": address}
        if param_format == "abci_balance_query":
            # Cosmos bank balance query
            return {
                "path": "/cosmos.bank.v1beta1.Query/Balance",
                "data": address,
                "prove": False,
            }
        # default: single address as object
        return {"address": address}

    def health_check_request(self, rpc_url: str) -> dict:
        """Tendermint health = `status` method."""
        body = {"jsonrpc": "2.0", "id": 1, "method": "status", "params": {}}
        return {
            "method": "POST",
            "url": rpc_url,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body, separators=(",", ":")),
            "parse_jq": ".result.sync_info.latest_block_height",
        }

    def parse_block_height(self, response_text: str) -> Optional[int]:
        if not response_text:
            return None
        try:
            obj = json.loads(response_text)
        except json.JSONDecodeError:
            return None
        try:
            return _try_int(obj["result"]["sync_info"]["latest_block_height"])
        except (KeyError, TypeError):
            return None
