"""HederaDualAdapter — Hedera 双协议 adapter (Mirror REST + JSON-RPC Relay).

Hedera 是天然双协议链:
  - Mirror REST  https://mainnet-public.mirrornode.hedera.com  (账户/balance/tx)
  - JSON-RPC Relay https://mainnet.hashio.io/api               (EVM-compat eth_*)

method 路由规则 (per-request):
  - method 以 'eth_' 开头 或 等于已知 JSON-RPC 方法名 → 走 JSON-RPC POST + json body
    rpc_url 取 _meta.json_rpc_url (chain template 显式声明)
  - 否则按 REST 路径处理 (method key 必须在 _meta.rest_paths 里)
    rpc_url 取 build_vegeta_target 传入的 rpc_url (即 LOCAL_RPC_URL = Mirror REST)

为什么不直接复用 RestAdapter+JsonRpcAdapter?
  ChainAdapter ABC + factory 是 chain→family 1:1 映射。同一 chain 单 request 内
  按 method 分协议路由,必须新 family。

测试 invariant (L1-CLI):address 必须出现在生成的 vegeta target 的 url 或 body 里。
  REST 侧 → address 进 path → 进 url
  JSON-RPC 侧 → address 进 params[0] → 进 body
"""
from __future__ import annotations
import json
import os
import re
from typing import Optional

from .base import ChainAdapter, register, _vegeta_get, _vegeta_post_json, _try_int
from .rest import RestAdapter, _CHAINS_DIR
from .jsonrpc import JsonRpcAdapter


_JSONRPC_METHOD_RE = re.compile(r"^(eth_|net_|web3_|debug_|trace_)")


def _is_jsonrpc_method(method: str) -> bool:
    """Decide if a method name should be routed to the JSON-RPC Relay.

    True for eth_* / net_* / web3_* / debug_* / trace_* (standard EVM
    JSON-RPC namespaces). False for REST path-style keys like
    'GET /api/v1/accounts/{addr}'.
    """
    return bool(_JSONRPC_METHOD_RE.match(method))


@register("hedera_dual")
class HederaDualAdapter(ChainAdapter):
    """Per-request protocol routing for Hedera Mirror REST + JSON-RPC Relay."""

    def __init__(self):
        # Delegate the two protocol concerns to the existing single-protocol
        # adapters — no logic duplication, only routing.
        self._rest = RestAdapter()
        self._jsonrpc = JsonRpcAdapter()
        self._chain_cache: dict[str, dict] = {}

    def _load_chain(self, chain_name: str) -> dict:
        if chain_name not in self._chain_cache:
            with open(_CHAINS_DIR / f"{chain_name}.json") as f:
                self._chain_cache[chain_name] = json.load(f)
        return self._chain_cache[chain_name]

    def _get_chain_name(self) -> str:
        chain_name = os.environ.get("BLOCKCHAIN_NODE", "").lower()
        if not chain_name:
            raise RuntimeError("HederaDualAdapter requires BLOCKCHAIN_NODE env var")
        return chain_name

    def _get_jsonrpc_url(self, chain_name: str) -> str:
        """JSON-RPC url comes from chain template _meta.json_rpc_url.

        Required because LOCAL_RPC_URL (the single env var used as rpc_url
        for this run) points at Mirror REST; JSON-RPC traffic needs a
        separate endpoint (Hashio relay for hedera).
        """
        tpl = self._load_chain(chain_name)
        url = tpl.get("_meta", {}).get("json_rpc_url")
        if not url:
            raise ValueError(
                f"hedera_dual chain {chain_name}: _meta.json_rpc_url not set; "
                f"required for routing eth_*/net_*/web3_* methods."
            )
        return url

    # ─── ABC contract ──────────────────────────────────────────────────────

    def build_vegeta_target(
        self, method: str, inputs: dict, rpc_url: str, param_spec: dict,
    ) -> dict:
        # 批1 过渡: 签名统一为 (inputs, param_spec); 双模式委托 jsonrpc/rest 传新签名。
        chain_name = self._get_chain_name()
        if _is_jsonrpc_method(method):
            jsonrpc_url = self._get_jsonrpc_url(chain_name)
            return self._jsonrpc.build_vegeta_target(
                method=method, inputs=inputs,
                rpc_url=jsonrpc_url, param_spec=param_spec,
            )
        # REST path-style: delegate to RestAdapter (uses BLOCKCHAIN_NODE +
        # _meta.rest_paths from chain template, same as before)
        return self._rest.build_vegeta_target(
            method=method, inputs=inputs,
            rpc_url=rpc_url, param_spec=param_spec,
        )

    def health_check_request(self, rpc_url: str) -> dict:
        """Health probe uses REST side (_meta.health_probe).

        Mirror REST is the primary observability surface; JSON-RPC liveness
        is an orthogonal concern. If both must be probed, run two probes
        externally (eth_blockNumber against json_rpc_url).
        """
        return self._rest.health_check_request(rpc_url)

    def parse_block_height(self, response_text: str) -> Optional[int]:
        """Best-effort: try REST shape first (.block_height / .blocks[0].number),
        then JSON-RPC shape (.result as hex or int).
        """
        h = self._rest.parse_block_height(response_text)
        if h is not None:
            return h
        return self._jsonrpc.parse_block_height(response_text)
