"""AvaXAdapter — Avalanche X-Chain (AVM) JSON-RPC 2.0.

Avalanche X-Chain uses JSON-RPC 2.0 but differs from EVM in 4 key ways:
  1. params is an OBJECT (not array): {"height":"517990", "encoding":"json"}
  2. uint64 fields are STRINGS in both params and responses ("517990" not 517990)
  3. IDs (txID, blockID, assetID) use cb58 encoding, not hex
  4. Multi-endpoint: /ext/bc/X (avm.*) vs /ext/info (info.*) — route by namespace

method_name prefix dispatches endpoint:
  - "avm.*"     → POST /ext/bc/X
  - "info.*"    → POST /ext/info
  - "platform.*" → POST /ext/bc/P (P-Chain, future-proof; not in v1 mixed set)

Param formats (extracted from research doc docs/zh|en/chains/13-avalanche-x.md):
  no_params                       → {}
  height_encoding                 → {"height": "<int as STRING>", "encoding": "json"}
  blockid_encoding                → {"blockID": "<cb58>", "encoding": "json"}
  txid_encoding                   → {"txID": "<cb58>", "encoding": "json"}
  txid_only                       → {"txID": "<cb58>"}                    # getTxStatus
  address_only                    → {"address": "<bech32>"}              # getAllBalances
  address_assetid                 → {"address": "<bech32>", "assetID": "AVAX"}
  addresses_limit_encoding        → {"addresses": ["<bech32>"], "limit": <int>, "encoding": "hex"}
  assetid_only                    → {"assetID": "<cb58>"}                # getAssetDescription
  alias_only                      → {"alias": "<str>"}                   # info.getBlockchainID

Address surrogate: when the framework supplies an EVM-style "0x..." address into
this adapter (because target_generator is chain-agnostic), build_vegeta_target
substitutes a known-valid X-Chain bech32 placeholder.
"""
from __future__ import annotations
import json
from typing import Optional

from .base import ChainAdapter, register, _vegeta_post_json, _try_int


# Known-valid X-Chain bech32 placeholder (from block 517990 — verified live).
_PLACEHOLDER_X_ADDR = "X-avax13k6hxpfuu80dlnqlqs0dxxjrzl4lxz94n38vnw"
# Known cb58 ID placeholder (32-byte zeroes + 4-byte checksum is just zeros for fixture).
_PLACEHOLDER_CB58_ID = "11111111111111111111111111111111LpoYY"  # genesis-like


@register("avax")
class AvaXAdapter(ChainAdapter):

    def build_vegeta_target(
        self, method: str, address: str, rpc_url: str, param_format: str = "",
    ) -> dict:
        base = rpc_url.rstrip("/")

        # Endpoint routing by namespace prefix
        if method.startswith("avm."):
            url = base + "/ext/bc/X"
        elif method.startswith("info."):
            url = base + "/ext/info"
        elif method.startswith("platform."):
            url = base + "/ext/bc/P"
        else:
            raise ValueError(
                f"AvaXAdapter: cannot dispatch method {method!r}. "
                f"Expected 'avm.*', 'info.*', or 'platform.*'."
            )

        params = self._build_params(param_format, address)
        body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        return _vegeta_post_json(url, body)

    @staticmethod
    def _build_params(param_format: str, address: str) -> dict:
        """Build the params OBJECT (Avalanche uses dict not list)."""
        # Address sanitization: if address is EVM-style 0x..., swap to X-Chain placeholder.
        bech32_addr = address if address.startswith("X-") else _PLACEHOLDER_X_ADDR
        # cb58 ID sanitization: if address is 0x-hex, swap to cb58 placeholder.
        cb58_id = address if not address.startswith("0x") else _PLACEHOLDER_CB58_ID

        if param_format == "no_params" or param_format == "":
            return {}
        if param_format == "height_encoding":
            # height MUST be string per avalanchego jsonString contract
            try:
                h_int = int(address) if address.isdigit() else 0
            except (ValueError, AttributeError):
                h_int = 0
            return {"height": str(h_int), "encoding": "json"}
        if param_format == "blockid_encoding":
            return {"blockID": cb58_id, "encoding": "json"}
        if param_format == "txid_encoding":
            return {"txID": cb58_id, "encoding": "json"}
        if param_format == "txid_only":
            return {"txID": cb58_id}
        if param_format == "address_only":
            return {"address": bech32_addr}
        if param_format == "address_assetid":
            return {"address": bech32_addr, "assetID": "AVAX"}
        if param_format == "addresses_limit_encoding":
            return {"addresses": [bech32_addr], "limit": 10, "encoding": "hex"}
        if param_format == "assetid_only":
            return {"assetID": cb58_id}
        if param_format == "alias_only":
            return {"alias": "X"}
        # Fallback: empty object (better than crashing — uint64-as-string
        # contract means we can't blindly pass arrays).
        return {}

    def health_check_request(self, rpc_url: str) -> dict:
        """Health probe = avm.getHeight on /ext/bc/X."""
        base = rpc_url.rstrip("/")
        body = json.dumps({
            "jsonrpc": "2.0", "id": 1,
            "method": "avm.getHeight", "params": {},
        }, separators=(",", ":"))
        return {
            "method": "POST",
            "url": base + "/ext/bc/X",
            "headers": {"Content-Type": "application/json"},
            "body": body,
            # height is returned as string per uint64-as-string contract
            "parse_jq": ".result.height",
        }

    def parse_block_height(self, response_text: str) -> Optional[int]:
        """Parse avm.getHeight response → .result.height (STRING, parse to int)."""
        if not response_text:
            return None
        try:
            obj = json.loads(response_text)
        except json.JSONDecodeError:
            return None
        result = obj.get("result")
        if not isinstance(result, dict):
            return None
        # height is a string per avalanchego contract; _try_int handles both.
        return _try_int(result.get("height"))
