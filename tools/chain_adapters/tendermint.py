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
from .rest import RestAdapter


@register("tendermint")
class TendermintAdapter(ChainAdapter):

    def __init__(self):
        # tendermint 链的 method 多是 LCD REST path 风格(/cosmos/.../{addr}),
        # 走 RestAdapter 构造(S3.7 协议错配修复, 批3b); 少数 jsonrpc_list 类走本地构造器。
        self._rest = RestAdapter()

    def build_vegeta_target(
        self, method: str, inputs: dict, rpc_url: str, param_spec: dict,
    ) -> dict:
        """Tendermint: 双形态构造(批3a+批3b)。

        判定优先 method 名形态(而非仅 param_spec.transport, 因 no_params 在两种
        transport 下语义不同):
        - method 名是 "VERB /path" 形态(LCD REST: GET /cosmos/.../{addr}) → 委托
          RestAdapter(S3.7 协议错配修复: method 名是 REST path 但历史走 jsonrpc)
        - 否则(Tendermint RPC method: status/abci_query 等) → 本地 jsonrpc 构造器
        """
        m = method.strip()
        is_rest_path = (m[:4].upper() in ("GET ", "POST") and " " in m) or m.startswith("/")
        if is_rest_path:
            return self._rest.build_vegeta_target(method, inputs, rpc_url, param_spec)
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
