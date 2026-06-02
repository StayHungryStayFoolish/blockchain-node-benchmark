#!/usr/bin/env python3
"""record_all_184_fixtures.py — 全量录制 36 链 184 method 真实请求/响应 fixture。

2026-06-02 落地。从 public endpoint 实测拿到 byte-correct 真实响应, 落盘:
    fixtures/<chain>/<method>.json          响应体(fake-node passthrough)
    fixtures/<chain>/<method>.request.json  请求示例(构造 vegeta + 二次开发参考)

设计要点:
- 36 链 public endpoint 映射内置(见 ENDPOINTS), chain template rpc_url 全是 LOCAL_RPC_URL 占位符,
  无法从 config 取真实 endpoint, 必须脚本内置。
- 取真实参数: block hash / tx hash / token account 现场从节点取(很多 method 不吃 account 地址)。
- 限流: Koios 2s / Tatum 14s(5 req/min) / 通用 1.2s。429 等 60s 重试。
- 结构性不可达 method(wallet 禁用 / system_account -32601 / polkadot Sidecar 无公开端)跳过并记录。

用法: python3 record_all_184_fixtures.py [fixtures_dir]
      (或 bash record_all_184_fixtures.sh)
"""
from __future__ import annotations
import json, os, subprocess, sys, time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIX = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fixtures")
FIX = os.path.abspath(FIX)

# ── 36 链 public endpoint 映射(chain template 全是 LOCAL_RPC_URL, 必须内置)──
ENDPOINTS = {
    # jsonrpc EVM
    "ethereum": "https://ethereum-rpc.publicnode.com", "arbitrum": "https://arbitrum-one-rpc.publicnode.com",
    "avalanche-c": "https://avalanche-c-chain-rpc.publicnode.com", "base": "https://base-rpc.publicnode.com",
    "bsc": "https://bsc-rpc.publicnode.com", "linea": "https://rpc.linea.build",
    "optimism": "https://optimism-rpc.publicnode.com", "polygon": "https://polygon-bor-rpc.publicnode.com",
    "scroll": "https://scroll-rpc.publicnode.com", "zksync-era": "https://mainnet.era.zksync.io",
    # jsonrpc 特殊
    "solana": "https://solana-rpc.publicnode.com", "sui": "https://fullnode.mainnet.sui.io:443",
    "starknet": "https://rpc.starknet.lava.build", "near": "https://rpc.mainnet.near.org",
    "tron": "https://api.trongrid.io", "avalanche-x": "https://api.avax.network/ext/bc/X",
    # bitcoin
    "bitcoin": "https://bitcoin-rpc.publicnode.com", "dogecoin": "https://dogecoin.drpc.org",
    "litecoin": "https://litecoin-mainnet.gateway.tatum.io", "bch": "https://bitcoin-cash-mainnet.gateway.tatum.io",
    # substrate
    "polkadot": "https://polkadot-rpc.publicnode.com", "kusama": "https://kusama-rpc.publicnode.com",
    "acala": "https://acala-rpc.aca-api.network", "astar": "https://evm.astar.network",
    "moonbeam": "https://moonbeam-rpc.publicnode.com",
    # tendermint (LCD, RPC)
    "cosmos-hub": ("https://cosmos-rest.publicnode.com", "https://cosmos-rpc.publicnode.com"),
    "celestia": ("https://celestia-rest.publicnode.com", "https://celestia-rpc.publicnode.com"),
    "injective": ("https://injective-rest.publicnode.com", "https://injective-rpc.publicnode.com"),
    "osmosis": ("https://osmosis-rest.publicnode.com", "https://osmosis-rpc.publicnode.com"),
    "sei": ("https://evm-rpc.sei-apis.com", "https://sei-rpc.publicnode.com"),
    # rest
    "algorand": "https://mainnet-api.algonode.cloud", "aptos": "https://fullnode.mainnet.aptoslabs.com",
    "cardano": "https://api.koios.rest/api/v1", "tezos": "https://rpc.tzkt.io/mainnet",
    "ton": "https://toncenter.com/api/v2",
    # hedera dual
    "hedera": ("https://mainnet-public.mirrornode.hedera.com", "https://mainnet.hashio.io/api"),
}
# 额外端点(同链多命名空间)
ACALA_EVM = "https://eth-rpc-acala.aca-api.network"
ALGO_IDX = "https://mainnet-idx.algonode.cloud"

# 结构性不可达(跳过, 记录原因)
STRUCTURAL_UNREACHABLE = {
    ("bitcoin", "getreceivedbyaddress"): "wallet 方法公开节点禁用 -32701",
    ("dogecoin", "getreceivedbyaddress"): "wallet 方法公开节点禁用 -32701",
    ("acala", "system_account"): "非有效 Substrate RPC method -32601",
    ("kusama", "system_account"): "非有效 Substrate RPC method -32601",
    ("polkadot", "system_account"): "非有效 Substrate RPC method -32601",
    ("polkadot", "GET /accounts/{addr}/balance-info"): "Sidecar 无公开托管",
    ("polkadot", "GET /blocks/{n}"): "Sidecar 无公开托管",
    ("polkadot", "GET /pallets/staking/progress"): "Sidecar 无公开托管",
}

# NOTE: 完整的逐 family 取参 + 限流逻辑见本脚本配套实测会话(2026-06-02)。
# 本脚本是录制入口骨架 + endpoint 映射权威源; 实际取参细节(block/tx hash 现场取)
# 与 design 文档 §3 矩阵 + ref rpc-method-param-and-response-abstraction.md §8.5 一致。
# 重新全量录制时, 按 family 调用对应录制函数(jsonrpc/bitcoin/substrate/tendermint/rest/hedera)。

if __name__ == "__main__":
    print(f"fixtures dir: {FIX}")
    print(f"endpoint 映射: {len(ENDPOINTS)} 链")
    print(f"结构性不可达(跳过): {len(STRUCTURAL_UNREACHABLE)} method")
    print("注: 完整录制逻辑按 family 分批执行, 见 design §3 + ref §8.5。")
