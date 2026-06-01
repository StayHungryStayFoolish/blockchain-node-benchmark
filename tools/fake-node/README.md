# fake-node — long-lived test fixture for the blockchain-node-benchmark framework

**Purpose**: framework 集成测试夹具 (NOT a PoC, NOT a benchmark target). 每次 framework 改动 (monitor / proxy / analyzer / reporter / chain adapter) 都跑一次 framework → fake-node 全链路, 验闭环.

**What it provides**:
- JSON-RPC over HTTP, 按 method 返回对应 fixture (byte-correct, 真节点录的)
- 非固定频率磁盘 IO worker (随机大小, 随机间隔), 让 monitor 有真 IO 可观察
- **多协议族 handler 架构** (v2): `BLOCKCHAIN_NODE` env → chain template → `_meta.adapter_family` → handler dispatch
- 单二进制 + per-family YAML + per-chain fixtures = 36 链覆盖能力

**What it does NOT solve**:
- weight 数值精度 (等真节点)
- 真节点性能极限 (等真节点)

---

## v2 范式纠正 (2026-05-27)

v1 实现错误: 单文件 + per-chain YAML + 声称"零代码加链", 与 framework 既有 `BLOCKCHAIN_NODE` env + `_meta.adapter_family` switch 约定不一致。 用户质问: *"BLOCKCHAIN_NODE 变量存在,fake-node 难道不能 switch case? 36 链本身就不是完全相同,怎么可能一个 fake-node 复用?"*

v2 改为镜像 framework `tools/chain_adapters/` 架构:
- `handlers/base.go` → `Handler` interface + `_REGISTRY` (镜像 `chain_adapters/base.py:107`)
- `handlers/<family>.go` → per-protocol-family 实现 (1 handler = 1 family = N chains)
- 入口同 framework: 读 `BLOCKCHAIN_NODE` env → load `config/chains/<chain>.json` → 取 `_meta.adapter_family` → dispatch

---

## 加链工作量诚实矩阵 (取代 v1 的"零代码加链"绝对声明)

| 场景                                  | Go 改动                       | 配置改动                              | 工作量等级       |
|---------------------------------------|-------------------------------|---------------------------------------|------------------|
| 已实现协议族新成员 (如新 EVM 链)     | **0 行**                      | +1 chain template (framework 共用)    | < 30 分钟        |
| 协议族内特殊调优 (tier/IO 档位)      | 0 行                          | +1 family yaml field                  | < 10 分钟        |
| **全新协议族** (5/7 仍 stub)         | **+1 handler.go ~150-300 行** | +1 family yaml + per-chain fixtures   | 1-2 工时         |

工作量与 framework `tools/chain_adapters/<family>.py` 对称 (1 协议族 = 1 adapter 模块)。

---

## 36 链 → 7 协议族归并 (源: `config/chains/*.json:_meta.adapter_family`)

| Family            | Chains | Coverage | Handler 状态                                    |
|-------------------|-------:|----------|-------------------------------------------------|
| `jsonrpc`         | 16     | solana, ethereum, bsc, base, polygon, scroll, arbitrum, optimism, linea, avalanche-c, avalanche-x, zksync-era, near, tron, sui, starknet | ✅ **implemented** |
| `bitcoin_jsonrpc` | 4      | bitcoin, bch, dogecoin, litecoin                | ✅ **implemented** (无 smoke 覆盖, P2) |
| `substrate`       | 5      | polkadot, kusama, acala, astar, moonbeam        | ⚠️ stub (OQ-X)   |
| `tendermint`      | 5      | cosmos-hub, osmosis, celestia, injective, sei   | ⚠️ stub (OQ-X)   |
| `rest`            | 4      | algorand, aptos, tezos, ton                     | ⚠️ stub (OQ-X)   |
| `ogmios`          | 1      | cardano                                         | ⚠️ stub (OQ-X)   |
| `hedera_dual`     | 1      | hedera                                          | ⚠️ stub (OQ-X)   |
| **TOTAL**         | **36** | -        | **20/36 RPC-ready, 16/36 startup-ready 仅**     |

**Stub 行为**: 已注册到 registry, startup OK, 但 RPC 请求返回明确 error (HTTP 404 "method not declared" 或 500 "family not yet implemented") — **不静默通过, 不假装 healthy**.

5 个 stub 已入账 `docs/architecture/OPEN-QUESTIONS.md` (OQ-X), 不算 `no-deferred-bugs` defer (这是 R1 阶段范围切分, 不是 P0 bug 推后).

---

## 用法

```bash
# Build
cd tools/fake-node && go build -o /tmp/fake-node-v2 .

# Run for a specific chain (env var, framework 一致方式)
BLOCKCHAIN_NODE=solana   /tmp/fake-node-v2 -port 19101
BLOCKCHAIN_NODE=ethereum /tmp/fake-node-v2 -port 19102
BLOCKCHAIN_NODE=bitcoin  /tmp/fake-node-v2 -port 19103

# Or via flag (overrides env)
/tmp/fake-node-v2 -chain solana -port 19101

# Smoke (3 chains: solana + ethereum + cardano stub)
bash tools/fake-node/scripts/ci_smoke.sh
```

CLI flags:
- `-chain`: chain name; overrides `BLOCKCHAIN_NODE` env; default `solana`
- `-chains-dir`: directory of framework chain templates (default `../../config/chains`)
- `-configs-dir`: directory of per-family fake-node YAML (default `configs`)
- `-fixtures-dir`: fixtures root (per-chain subdirs) (default `./fixtures`)
- `-port`: listen port (default `19000`)

`BLOCKCHAIN_NODE` env handling matches framework `config/config_loader.sh:17,20`: default `solana`, lowercased.

---

## 目录结构

```
tools/fake-node/
├── fake_node.go              # main: env → template → family → handler
├── handlers/
│   ├── base.go               # Handler interface + _REGISTRY + NotImplementedHandler
│   ├── jsonrpc.go            # 16-chain handler (byte-passthrough)
│   ├── bitcoin_jsonrpc.go    # 4-chain handler (byte-passthrough)
│   └── stubs.go              # 5 stub registrations (substrate/tendermint/rest/ogmios/hedera_dual)
├── configs/
│   ├── jsonrpc.yaml          # method list (union) + tiers + IO
│   ├── bitcoin_jsonrpc.yaml
│   ├── substrate.yaml        # stub (empty methods)
│   ├── tendermint.yaml       # stub
│   ├── rest.yaml             # stub
│   ├── ogmios.yaml           # stub
│   └── hedera_dual.yaml      # stub
├── fixtures/
│   ├── solana/               # 5 real recorded fixtures
│   │   ├── getSlot.json
│   │   ├── getBalance.json
│   │   ├── getLatestBlockhash.json
│   │   ├── getBlock.json
│   │   └── getTransaction.json
│   ├── ethereum/             # 6 stub fixtures (minimal valid JSON-RPC)
│   │   ├── eth_blockNumber.json
│   │   ├── eth_gasPrice.json
│   │   ├── eth_getBalance.json
│   │   ├── eth_getTransactionCount.json
│   │   ├── eth_getBlockByNumber.json
│   │   └── eth_getTransactionByHash.json
│   └── <other-chains>/       # populated on demand
└── scripts/
    ├── ci_smoke.sh           # 3-chain smoke (15 checks)
    └── record_solana_fixtures.sh  # recorder (reusable per-chain via mainnet RPC)
```

---

## 录制 fixture (per-chain)

```bash
# Solana (already done, fixtures committed)
bash tools/fake-node/scripts/record_solana_fixtures.sh

# Ethereum (using stub fixtures currently; replace with real mainnet recording)
# TODO: scripts/record_evm_fixtures.sh — needs an EVM endpoint
```

Recording uses the same approach as `tools/proxy/poc-min/scripts/record_fixtures.sh` — `curl` mainnet, save response verbatim.

---

## smoke 覆盖范围

`scripts/ci_smoke.sh` 当前 15 个检查:
1. binary builds
2. solana startup + 路由 `adapter_family=jsonrpc` 正确
3. solana getSlot / getBalance byte-correct
4. ethereum startup + 复用 jsonrpc handler (证 family 抽象)
5. ethereum eth_blockNumber / eth_getBalance byte-correct
6. ethereum 在 solana method 上 404 (证 chain 隔离)
7. cardano stub startup OK + RPC 失败有响
8. /stats 计数对
9. IO worker 活跃

**未覆盖** (P2, 进 OQ):
- substrate / tendermint / rest / hedera_dual 真 fixture + handler 实现
- 4 个 EVM 兄弟链 (bsc/base/polygon/...) smoke
- bitcoin_jsonrpc 真 fixture (handler 已实现, fixtures 待录)
