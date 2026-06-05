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
from .param_spec import build_params_from_spec


@register("tendermint")
class TendermintAdapter(ChainAdapter):

    def build_vegeta_target(
        self, method: str, inputs: dict, rpc_url: str, param_spec: dict,
    ) -> dict:
        """Tendermint RPC: POST JSON-RPC.

        批3a: 切 param_spec 真构造器。tendermint 的非 path method(no_params/
        address_latest/address_with_options)是 jsonrpc_list 类(PRESET 已覆盖)。
        path 风格 method(/cosmos/... LCD REST)走批3b REST 构造, 在此 fail-fast(归批3b)。
        """
        params = build_params_from_spec(param_spec, inputs)
        body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        return _vegeta_post_json(rpc_url, body)

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
