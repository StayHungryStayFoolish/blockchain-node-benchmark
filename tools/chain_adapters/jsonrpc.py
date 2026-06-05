"""JsonRpcAdapter — standard JSON-RPC 2.0 POST.

Covers 16 chains: Ethereum / BSC / Polygon / Base / Scroll / Arbitrum /
Optimism / zkSync-Era / Linea / Solana / Sui / StarkNet / NEAR /
Avalanche-C / Avalanche-X / Tron.

Param formats (from baseline target_generator.sh L77-109):
    no_params              → []
    single_address         → ["<addr>"]
    address_latest         → ["<addr>", "latest"]      (EVM)
    latest_address         → ["latest", "<addr>"]      (StarkNet)
    address_storage_latest → ["<addr>", "0x0", "latest"]   (eth_getStorageAt)
    address_key_latest     → ["<addr>", "0x1", "latest"]   (starknet_getStorageAt)
    address_with_options   → ["<addr>", {showType:true, showContent:true, showDisplay:false}]  (sui)

Health probe per-subchain method (from common_functions.sh L194-275):
    solana → getBlockHeight    → decimal int
    EVM    → eth_blockNumber   → 0x-hex
    starknet → starknet_blockNumber → decimal int
    sui    → sui_getTotalTransactionBlocks → decimal int

Chains beyond these baseline-5 (NEAR, tron, arbitrum, optimism, zksync-era,
linea, avalanche-c, avalanche-x) — health uses chain-template-specific method
read from rpc_methods.single field. Default health probe = chain's single method
with empty params, expecting either decimal int or 0x-hex result.
"""
from __future__ import annotations
import json
import re
from typing import Optional

from .base import ChainAdapter, register, _vegeta_post_json, _try_int
from .param_spec import build_params_from_spec


@register("jsonrpc")
class JsonRpcAdapter(ChainAdapter):

    def build_vegeta_target(
        self, method: str, inputs: dict, rpc_url: str, param_spec: dict,
    ) -> dict:
        # S2: 参数由 param_spec(声明式结构)+ inputs(多池真值)构造,
        # 取代旧 _build_params(param_format, address) 枚举 if-else。
        params = build_params_from_spec(param_spec, inputs)
        body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        return _vegeta_post_json(rpc_url, body)

    def health_check_request(self, rpc_url: str) -> dict:
        """Default health probe = eth_blockNumber. Caller can override per-chain
        by passing a different method via env var BLOCKCHAIN_HEALTH_METHOD."""
        # Subclasses or callers pass via env, but for a generic adapter we
        # need a default that works for the most common case (EVM).
        body = {"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []}
        return {
            "method": "POST",
            "url": rpc_url,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body, separators=(",", ":")),
            "parse_jq": ".result",
        }

    def parse_block_height(self, response_text: str) -> Optional[int]:
        """Try .result as decimal int or 0x-hex string."""
        if not response_text:
            return None
        try:
            obj = json.loads(response_text)
        except json.JSONDecodeError:
            return None
        result = obj.get("result")
        return _try_int(result)
