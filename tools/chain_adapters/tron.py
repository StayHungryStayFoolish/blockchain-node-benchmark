"""TronAdapter — dual-protocol (HTTP /wallet/* + JSON-RPC /jsonrpc subset).

Tron node exposes two APIs on the same host:
  1. HTTP API: POST /wallet/<verb> + JSON body (each method → distinct path)
  2. JSON-RPC: POST /jsonrpc + body.method (EVM-compat subset)

DSL dispatch by method name shape:
  - method starts with "/wallet/" or "/walletsolidity/"  → HTTP API path
  - method starts with "eth_" or "net_" or "web3_"        → JSON-RPC at /jsonrpc

Param formats (extracted from research doc docs/zh/chains/09-tron.md):
  no_params                              → empty body {}
  body_address_visible                   → {"address": <addr>, "visible": true}
  body_value_txid_nopfx                  → {"value": <txid>}                # no 0x
  body_owner_contract_selector_parameter → triggerconstantcontract balanceOf

For JSON-RPC subset, delegates to JsonRpcAdapter param logic (address_latest etc.).

Endpoint convention:
  rpc_url passed in is the BASE host (e.g. https://api.trongrid.io)
  HTTP methods append /wallet/<verb>; JSON-RPC methods append /jsonrpc
"""
from __future__ import annotations
import json
from typing import Optional

from .base import ChainAdapter, register, _vegeta_post_json, _try_int


@register("tron")
class TronAdapter(ChainAdapter):

    def build_vegeta_target(
        self, method: str, address: str, rpc_url: str, param_format: str = "",
    ) -> dict:
        # Strip trailing slash from base URL to normalize
        base = rpc_url.rstrip("/")

        # HTTP API path: method itself is the path like "/wallet/getaccount"
        if method.startswith("/wallet/") or method.startswith("/walletsolidity/"):
            url = base + method
            body_obj = self._build_http_body(param_format, address)
            return _vegeta_post_json(url, body_obj)

        # JSON-RPC subset: eth_*/net_*/web3_*
        if method.startswith(("eth_", "net_", "web3_")):
            url = base + "/jsonrpc"
            params = self._build_jsonrpc_params(param_format, address)
            body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
            return _vegeta_post_json(url, body)

        # Unknown method shape → raise to surface in CI
        raise ValueError(
            f"TronAdapter: cannot dispatch method {method!r}. "
            f"Expected '/wallet/...' or 'eth_*'/'net_*'/'web3_*'."
        )

    @staticmethod
    def _build_http_body(param_format: str, address: str) -> dict:
        """Body templates for Tron HTTP API. address is repurposed by format."""
        if param_format == "no_params":
            return {}
        if param_format == "body_address_visible":
            # /wallet/getaccount, /wallet/getaccountresource → {address, visible}
            return {"address": address, "visible": True}
        if param_format == "body_value_txid_nopfx":
            # /wallet/gettransactionbyid → {value: <txid_no_0x>}
            # If address starts with 0x, strip it
            txid = address[2:] if address.startswith("0x") else address
            return {"value": txid}
        if param_format == "body_num":
            # /wallet/getblockbynum → {num: <int>}
            try:
                n = int(address)
            except (TypeError, ValueError):
                n = 1
            return {"num": n}
        if param_format == "body_owner_contract_selector_parameter":
            # /wallet/triggerconstantcontract → balanceOf(address)
            # owner_address and contract_address both base58 ("T..." form);
            # parameter is 32-byte hex-padded address (last 20B of hex41 form, padded)
            # For placeholder: use empty padded parameter.
            return {
                "owner_address": address,
                "contract_address": address,  # placeholder; production injects real TRC20 contract
                "function_selector": "balanceOf(address)",
                "parameter": "0" * 64,  # 32-byte padded zero
                "visible": True,
            }
        # default fallback
        return {}

    @staticmethod
    def _build_jsonrpc_params(param_format: str, address: str) -> list:
        """Minimal JSON-RPC param builder for Tron's /jsonrpc subset."""
        if param_format == "no_params" or param_format == "":
            return []
        if param_format == "single_address":
            return [address]
        if param_format == "address_latest":
            return [address, "latest"]
        if param_format == "transaction_hash":
            tx_hash = address if address.startswith("0x") and len(address) == 66 else "0x" + "0" * 64
            return [tx_hash]
        return [address]

    def health_check_request(self, rpc_url: str) -> dict:
        """Health probe = HTTP /wallet/getnowblock with empty body."""
        base = rpc_url.rstrip("/")
        return {
            "method": "POST",
            "url": base + "/wallet/getnowblock",
            "headers": {"Content-Type": "application/json"},
            "body": "{}",
            # parse: $.block_header.raw_data.number
            "parse_jq": ".block_header.raw_data.number",
        }

    def parse_block_height(self, response_text: str) -> Optional[int]:
        """Parse Tron getnowblock response → block_header.raw_data.number (int).

        Also handles the JSON-RPC eth_blockNumber response (.result as 0x-hex).
        """
        if not response_text:
            return None
        try:
            obj = json.loads(response_text)
        except json.JSONDecodeError:
            return None
        # HTTP API path
        try:
            n = obj["block_header"]["raw_data"]["number"]
            return _try_int(n)
        except (KeyError, TypeError):
            pass
        # JSON-RPC fallback
        return _try_int(obj.get("result"))
