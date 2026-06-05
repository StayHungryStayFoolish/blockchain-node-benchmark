"""ChainAdapter ABC and factory.

ABC interface contract:
    - protocol_family: str  ← class attribute identifying which family
    - build_vegeta_target(method, address, rpc_url, param_format) → dict
    - health_check_request(rpc_url) → dict
    - parse_block_height(response_text) → Optional[int]

Vegeta target schema (https://github.com/tsenart/vegeta):
    {
        "method": "POST" | "GET",
        "url": "http://...",
        "header": {"Content-Type": ["application/json"]},
        "body": "<base64-encoded body>"   ← omit for GET with no body
    }
"""
from __future__ import annotations
import base64
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

# Repo root: tools/chain_adapters/base.py → ../../
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CHAINS_DIR = _REPO_ROOT / "config" / "chains"


class ChainAdapter(ABC):
    """Abstract base for per-protocol-family chain adapters."""

    protocol_family: str = ""  # subclass overrides

    @abstractmethod
    def build_vegeta_target(
        self,
        method: str,
        inputs: dict,
        rpc_url: str,
        param_spec: dict,
    ) -> dict:
        """Build a vegeta target dict for one RPC request.

        S1+S2+B3 原子单元(2026-06-05): 签名从单 address 槽改为多源 inputs。
          inputs: dict — 输入池, 按 source 分键: {"account":[...], "tx_hash":[...],
                  "block_height":[...], "contract_call":[...], ...}。批1 暂传
                  {"account":[address]} 兼容; S1 填齐多池。
          param_spec: dict — 声明式参数构造规范(param_spec.resolve_param_spec 解析出),
                  含 transport + slots/fields/path/bindings。取代旧 param_format 枚举字符串
                  (枚举经 PARAM_FORMAT_PRESETS 展开成 param_spec, 单一构造路径)。
        """

    @abstractmethod
    def health_check_request(self, rpc_url: str) -> dict:
        """Build a single curl/HTTP request descriptor for health probing.

        Returns: {method, url, headers, body, parse_jq?}
            parse_jq — optional jq expression that, applied to the JSON response,
                       yields the block height as numeric or hex string.
        """

    @abstractmethod
    def parse_block_height(self, response_text: str) -> Optional[int]:
        """Parse decimal block height from response. Returns None on failure."""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers used by multiple subclasses
# ─────────────────────────────────────────────────────────────────────────────

def _b64(s: str) -> str:
    """Base64-encode a string (vegeta target body format)."""
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def _vegeta_post_json(rpc_url: str, body_obj: dict) -> dict:
    """Standard JSON POST vegeta target."""
    body_str = json.dumps(body_obj, separators=(",", ":"))
    return {
        "method": "POST",
        "url": rpc_url,
        "header": {"Content-Type": ["application/json"]},
        "body": _b64(body_str),
    }


def _vegeta_get(url: str, headers: Optional[dict] = None) -> dict:
    """GET vegeta target (no body)."""
    h = headers or {}
    return {
        "method": "GET",
        "url": url,
        "header": h,
    }


def _try_int(s) -> Optional[int]:
    """Parse decimal int from str/int. Returns None on failure."""
    if s is None:
        return None
    try:
        if isinstance(s, int):
            return s
        s = str(s).strip()
        if s.startswith("0x") or s.startswith("0X"):
            return int(s, 16)
        return int(s)
    except (ValueError, TypeError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────

_REGISTRY: dict[str, type[ChainAdapter]] = {}


def register(family: str):
    """Class decorator: register adapter under a family name."""
    def _wrap(cls):
        _REGISTRY[family] = cls
        cls.protocol_family = family
        return cls
    return _wrap


def get_adapter(chain_name: str) -> ChainAdapter:
    """Load chain template, look up _meta.adapter_family, return adapter instance."""
    chain_file = _CHAINS_DIR / f"{chain_name}.json"
    if not chain_file.exists():
        raise FileNotFoundError(f"Chain template not found: {chain_file}")
    with open(chain_file) as f:
        tpl = json.load(f)
    family = tpl.get("_meta", {}).get("adapter_family")
    if not family:
        raise ValueError(
            f"chain {chain_name}: _meta.adapter_family not set in {chain_file}"
        )
    if family not in _REGISTRY:
        raise ValueError(
            f"chain {chain_name}: unknown adapter_family {family!r}. "
            f"Registered: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[family]()


def list_adapters() -> list[str]:
    return sorted(_REGISTRY)


# Trigger registration of all subclasses
from . import jsonrpc, rest, tendermint, bitcoin_jsonrpc, substrate, hedera_dual  # noqa: E402, F401
