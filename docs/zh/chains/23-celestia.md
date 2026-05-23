# 23 — Celestia 调研稿(DIFF-ONLY vs 05-cosmos-hub.md)

> **版本**:v1.0(Phase 1.2 Wave7)
> **调研日期**:2026-05-23
> **作者**:Hermes Agent
> **状态**:🟢 待 user review
> **模式**:**最激进 DIFF-ONLY**(护栏 2)。本稿仅记录 Celestia 相对 Cosmos Hub 的**实质差异**,Tendermint RPC 与 Cosmos REST/LCD 的通用协议结构、错误码表、`/cosmos/bank/*` `/cosmos/staking/*` `/cosmos/tx/*` 标准 module 路径,请直接参见 `docs/zh/chains/05-cosmos-hub.md`(692 行,Wave1 已 commit)。
> **真实证据**:E1 单元测试 / E2 curl 实证 / E3 官方文档 / E4 GitHub 源码 / E5 框架 grep。

---

## 元信息

| 项 | 值 |
|---|---|
| 链名(中) | Celestia |
| 链名(英) | Celestia |
| 编号 | 23 |
| Mainnet ChainID | `celestia`(字符串,非数字)— E2 实测 `https://celestia-rpc.publicnode.com` `status.result.node_info.network = "celestia"` |
| 节点应用 | **celestia-app v8.0.3**(`celestia-appd`,git_commit `0fc10e0`,build_tags `ledger,multiplexer`)— E2 实测 `/cosmos/base/tendermint/v1beta1/node_info.application_version` |
| 共识层 | **CometBFT v0.38.17**(protocol app=8 block=11 p2p=8)— E2 |
| 调研日期 | 2026-05-23 |
| 框架是否已支持 | ❌ — E5 同 cosmos hub:`supported_blockchains` 未含 cosmos 家族 |
| Mainnet launch | 2023-10-31(块 1)— E3 |

---

## 1. Sources(权威 + fork 历史)

| 类型 | URL | 备注 |
|---|---|---|
| 官方文档 | https://docs.celestia.org/ | 含 modular 概念、blob lifecycle、DA sampling |
| 官方文档(node) | https://docs.celestia.org/nodes/overview | bridge / full / light 三种节点角色 |
| GitHub(celestia-app) | https://github.com/celestiaorg/celestia-app | **应用层**,fork 自 cosmos-sdk |
| GitHub(celestia-node) | https://github.com/celestiaorg/celestia-node | **DA 层**(bridge/full/light),独立 JSON-RPC(`blob.*` `header.*` `share.*` `das.*` `p2p.*`)— 与 celestia-app 的 Tendermint RPC 是**两套不同 RPC** |
| GitHub(celestia-core) | https://github.com/celestiaorg/celestia-core | fork 自 cometbft v0.38,加入 erasure coding / NMT(Namespaced Merkle Tree) |
| Specs | https://celestiaorg.github.io/celestia-app/ | proto + module spec(blob/blobstream/minfee) |
| Explorer(Celenium) | https://celenium.io | DA 友好,可查 namespace |
| Explorer(Mintscan) | https://www.mintscan.io/celestia | 常规 tx/staking |
| Publicnode RPC | https://celestia-rpc.publicnode.com | E2 验证通过 |
| Publicnode REST | https://celestia-rest.publicnode.com | E2 验证通过 |
| Numia REST | https://celestia-api.numia.xyz | 备用 |

**Fork 历史(E4)**:
- celestia-app v8.x 当前对齐 **cosmos-sdk v0.50.x**(Eden upgrade 后);v0.38 CometBFT 与 Cosmos Hub gaia v27 的 v0.38.19 几乎同版本 → **Tendermint RPC 100% 协议兼容**。
- 独有 module 通过 cosmos-sdk module 机制注入(非 fork 修改 stdlib),理论上其他链可借用。

---

## 2. 与 Cosmos Hub 关系

| 维度 | Cosmos Hub(gaia v27.3.0) | Celestia(celestia-app v8.0.3) | 是否兼容 |
|---|---|---|---|
| Cosmos SDK 版本 | v0.50.x 系列 | v0.50.x 系列(同代) | ✅ 标准 module 路径 100% 复用 |
| CometBFT 版本 | v0.38.19 | v0.38.17 | ✅ Tendermint RPC 完全一致 |
| 共识算法 | Tendermint BFT | Tendermint BFT + **DA erasure coding** | ⚠️ 共识层结构兼容,数据层多一个 `data_hash` 语义升级(NMT root) |
| 地址 bech32 prefix | `cosmos` | `celestia` | ⚠️ 地址互不兼容(prefix 不同,但 32 字节 raw 同构) |
| Native denom | `uatom` | `utia` | ⚠️ amount 字段语义同 |
| 块时间 | ~6s | ~6s(latest 11218365,与历史可推算) | ✅ |
| **块大小** | ~50–500 KB(typical) | **可达 8 MB**(square_size 128,Hyperion 升级后上限 8 MiB)— 实测分布见 §6 | ❌ **100× 差距,benchmark 必须显式处理** |
| 独有 module | (无) | **`blob` / `blobstream`(原 qgb)/ `minfee` / `signal`** | ❌ |
| 不存在的 module | — | **无 `mint`(TIA inflation 由 `x/mint` 改造)、无 `gov` proposal type 部分扩展、无 IBC packet middleware(部分)** | — |

---

## 3. 公链 endpoint 实证(E2,2026-05-23)

| Endpoint | 协议 | status | latest_block_height | 应用版本 | 备注 |
|---|---|---|---|---|---|
| https://celestia-rpc.publicnode.com | Tendermint RPC | 200 | **11218365** | celestia-app 8.0.3 | `/status` 返回完整 node_info(E2 实测 1 KB JSON);archive 节点 earliest=8718365(~250 万块历史) |
| https://celestia-rest.publicnode.com | Cosmos REST | 200 | 同上 | 同上 | `/cosmos/base/tendermint/v1beta1/blocks/latest` 实测返回 NMT 风格的 data_hash(base64) |
| https://celestia-api.numia.xyz | Cosmos REST | 未实测(留作备用) | — | — | requires_self_hosted=No |

**关键 E2 发现(blob/state/share module 探活)**:

```
# 通过 publicnode REST 探活 4 个独有 module(2026-05-23):
GET /celestia/blob/v1/params          → -32701 "not implemented"
GET /celestia/v1/blob/params          → -32701 "not implemented"
GET /qgb/v1/params                    → -32701 "not implemented"
GET /celestia/minfee/v1/params        → -32701 "not implemented"
```

→ **结论**:publicnode 的 REST gateway **关闭了 Celestia 独有 module 的 grpc-gateway 路由**(标准 `/cosmos/*` 路径正常)。这表明:
1. 独有 module 查询 **必须自建 celestia-app 全节点**才能稳定使用;
2. 框架 plugin 设计须将 `blob/blobstream/minfee` 标记 `requires_self_hosted=true`,与标准 `/cosmos/*` 路径解耦;
3. 同样 publicnode 也**未暴露 celestia-node 的 `blob.GetAll` / `share.GetSharesByNamespace`**(那是 DA-node 独立 JSON-RPC,不在 app RPC 内)。

---

## 4. 实质差异表(Cosmos Hub → Celestia)

### 4.1 独有 module(E3 + E4)

| Module | 路径(REST) | RPC 方法 | 作用 | benchmark 影响 |
|---|---|---|---|---|
| `blob` | `/celestia/blob/v1/params` `/celestia/blob/v1/params/gas_per_blob_byte` | `MsgPayForBlobs`(tx 类型,不是 query) | 提交 rollup 数据(blob)+ 查参数(GasPerBlobByte / GovMaxSquareSize) | 🔴 **核心负载**,80%+ tx 是 PayForBlobs |
| `blobstream`(原 qgb) | `/qgb/v1/params` `/qgb/v1/attestations` | — | Ethereum → Celestia DA bridge 的轻客户端 attestation | 🟡 低频,可忽略 |
| `minfee` | `/celestia/minfee/v1/params` | — | 网络强制最低 gas price(`network_min_gas_price`) | 🟢 1 次启动 read,缓存即可 |
| `signal` | `/celestia/signal/v1/*` | — | hard fork upgrade 版本协调(替代 `x/upgrade` 部分语义) | 🟢 无需 benchmark |
| **DA-node 独立 RPC**(celestia-node,**不在 celestia-app 内**) | JSON-RPC 26658 端口 | `blob.GetAll(height, namespaces[])` `blob.Submit(blobs[], gasPrice)` `share.GetSharesByNamespace` `share.GetEDS` `header.GetByHeight` `das.SamplingStats` `p2p.PeerInfo` | rollup / 应用层读 blob、light node DAS 采样 | 🔴 **plugin 必须额外建一个 connection target**:`celestia-da-node` 与 `celestia-app` 共享 chain 但 RPC 端点 / method 完全不同 |

### 4.2 共识 / 数据结构差异

| 项 | Cosmos Hub | Celestia |
|---|---|---|
| `block.data.txs` | 普通 tx 数组 | tx 数组 + 独立 `square` 结构(rollup blob 存在 data square,**不在 txs 内**)。`data_hash` = NMT root,非简单 Merkle |
| `block.header` 扩展字段 | 标准 14 字段 | + 隐式 `square_size`(通过 `part_set_header.total` 推断,E2 实测 `total:5` for 1.6 MB 块) |
| Max block size | ~22 MB 理论,~1 MB 实践 | **8 MiB hard cap(GovMaxSquareSize=128,SquareSize²×ShareSize≈8MiB)**;实际历史块见 §6 |
| Erasure coding | 无 | **2D Reed-Solomon**,允许 light node 通过 DAS 采样验证 |

### 4.3 Token 模型

| 项 | Cosmos Hub | Celestia |
|---|---|---|
| Native denom | `uatom`(6 decimals) | `utia`(6 decimals) |
| Inflation | 7%–20% 动态 bonded ratio | 8% 起,每年 -10% 衰减至 1.5% 底(E3) |
| Staking / Slashing | 标准 `x/staking` `x/slashing` | 同(无修改) |

---

## 5. Method 差异(99% 同 Cosmos Hub,只列独有)

> **不重复**:所有 `/cosmos/bank/*` `/cosmos/staking/*` `/cosmos/tx/*` `/cosmos/auth/*` `/cosmos/base/tendermint/*` 路径与 cosmos-hub.md §5 完全一致(E5 grep cosmos-sdk v0.50.x proto 文件确认)。

### 5.1 Celestia 独有 query(REST)

| Path | 入参 | 返回 | 实测 | 备注 |
|---|---|---|---|---|
| GET `/celestia/blob/v1/params` | — | `gas_per_blob_byte` `gov_max_square_size` | E2 publicnode 拒绝(不在 self-hosted 节点不可用) | 启动期读 1 次缓存 |
| GET `/celestia/minfee/v1/params` | — | `network_min_gas_price`(string,如 `"0.000001"`) | 同上 | 启动期读 |
| GET `/celestia/signal/v1/upgrade` | — | `app_version` | — | 升级监测 |
| GET `/qgb/v1/attestations/{nonce}` | nonce uint64 | DataCommitment / ValsetConfirm | — | 仅 ETH 桥用 |

### 5.2 celestia-node 独立 JSON-RPC(端口 26658,**与 app RPC 26657 不同**)

| Method | params | 返回 | benchmark 关键性 |
|---|---|---|---|
| `header.GetByHeight` | `[height]` | Header(含 DAH=DataAvailabilityHeader) | 🟢 替代 `/block` 当只要 header 时 |
| `blob.GetAll` | `[height, namespaces[]]` | `[]Blob`(每个 blob 含 data / namespace / share_version) | 🔴 **fetch_blocks 核心**:对一个 height 拉指定 namespace 所有 blob |
| `blob.Submit` | `[blobs[], gas_price]` | tx hash | 仅 rollup sequencer 用 |
| `share.GetSharesByNamespace` | `[height, namespace]` | shares[] + NMT proof | 🟡 DA 采样验证 |
| `share.GetEDS` | `[height]` | ExtendedDataSquare(完整 2D 矩阵) | 🔴 **全 EDS 下载可达 32 MB**(8MB blob × 4 erasure-coded),benchmark 必须独立 case |
| `das.SamplingStats` | — | `{head_of_sampled_chain, head_of_catchup, ...}` | 🟢 light node 健康度 |
| `p2p.PeerInfo` | — | peers[] | 🟢 |

---

## 6. 真实负载实测(E2,2026-05-23)

**5 连续高度块大小分布**(从 `/block?height=H` JSON 返回大小测,heights = 11218360..11218364):

| Height | JSON 返回字节 | 推测 | 备注 |
|---|---:|---|---|
| 11218360 | 479,724 | ~470 KB | 中型 blob 块 |
| 11218361 | 351,480 | ~340 KB | 小 |
| 11218362 | **1,642,337** | **~1.6 MB** | **大 blob 块**(rollup batch) |
| 11218363 | 328,230 | ~320 KB | 小 |
| 11218364 | 533,830 | ~520 KB | 中 |

**对比 Cosmos Hub 同期实测**(cosmos-hub.md §6):单块 JSON 通常 20–80 KB,**Celestia 平均大 10–20×,峰值大 80–100×**。

**对 benchmark 函数的影响**:
1. `fetch_blocks` 函数:**单 HTTP 响应 buffer 必须 ≥ 16 MB**(8 MB blob + base64 膨胀 ~33% + JSON-RPC 包装)。当前框架的 EVM 默认 1 MB buffer **必须显式扩**。
2. **HTTP timeout 必须放宽到 ≥ 30s**:8 MB 块在普通 100 Mbps 链路下传输 ~1s,但 publicnode CDN + JSON 序列化峰值 5–10s。
3. **并发拉块策略改写**:Cosmos Hub 可 16 并发,Celestia 建议 4–8 并发(否则带宽打满,latency 指标失真)。
4. **网络指标(NET I/O)**首次成为瓶颈:8 MB × 6s/block = ~10.7 Mbps 持续下行,16 并发 catch-up 可触发 100 Mbps 链路上限 → 这正是 Celestia 测试**最有价值的发现点**。

**典型 tx**:`MsgPayForBlobs`(`celestia.blob.v1.MsgPayForBlobs`),含 `signer / namespaces[] / blob_sizes[] / share_versions[] / share_commitments[]`。真实 blob data 通过 BlobTx wrapper 与 tx 分离传输(E3 ADR-006)。

---

## 7. DSL 决策(预测新字段)

### 7.1 现有 DSL 字段复用

- `family: "cosmos"`(同 Cosmos Hub,**不新增 family**)
- `consensus: "tendermint-bft"`
- `address_format: "bech32"` + `bech32_prefix: "celestia"`
- `native_denom: "utia"`
- `requires_self_hosted_for: ["blob", "blobstream", "minfee", "signal"]`(新)

### 7.2 **新增 DSL 子枚举**:`rollup_type: "modular_da"`

**ASK**(请 user 决策):

```yaml
# 提议在 chain DSL 中加入 rollup_type 字段(子枚举,默认 null):
rollup_type:
  - null                # 普通 L1(Cosmos Hub / Solana / BTC)
  - "optimistic"        # OP rollup(Arbitrum / Optimism / Base)
  - "zk"                # ZK rollup(zkSync Era / Linea / Starknet)
  - "validium"          # 链下数据 + ZK proof(Immutable X)
  - "modular_da"        # 【新】纯 DA 层,本身不是 rollup,但服务于 rollup(Celestia / Avail / EigenDA)
```

**理由**:
1. Celestia 不是 rollup,但其负载特征(blob 提交 / 巨块 / DA 采样)与 L1/L2 完全不同,需独立分类以**驱动 benchmark profile**(buffer / timeout / 并发数)。
2. 框架后续接入 Avail / EigenDA 时复用同枚举,无需再扩。
3. 与 `family: "cosmos"` 正交(Celestia 同时是 cosmos family + modular_da type)。

### 7.3 推荐 plugin profile 默认值

```yaml
celestia:
  family: cosmos
  rollup_type: modular_da
  block_time_s: 6
  expected_block_size_mb: { p50: 0.5, p95: 4, max: 8 }
  fetch_buffer_mb: 16
  http_timeout_s: 30
  fetch_concurrency: 6
  da_node_rpc_port: 26658     # 独立 connection target
  app_rpc_port: 26657
  bottleneck_priority: [NET, DISK_WRITE, CPU]  # 不同于 EVM 的 [CPU, DISK_IOPS]
```

---

## 8. H8 实证清单

| # | 命令 | 结果 | 用途 |
|---|---|---|---|
| E2-1 | `POST /status` (RPC) | `network=celestia`, `latest_block_height=11218365`, `version=0.38.17` | ChainID + CometBFT 版本 |
| E2-2 | `GET /cosmos/base/tendermint/v1beta1/node_info` | `application_version.name=celestia-app version=8.0.3 git_commit=0fc10e0` | 应用版本 |
| E2-3 | `GET /cosmos/base/tendermint/v1beta1/blocks/latest` | data_hash + part_set_header.total=5 | block 结构对齐 |
| E2-4 | `GET /celestia/blob/v1/params` | `-32701 not implemented` | publicnode 不开放独有 module → requires_self_hosted 证据 |
| E2-5 | `GET /qgb/v1/params` | `-32701 not implemented` | 同上 |
| E2-6 | `GET /celestia/minfee/v1/params` | `-32701 not implemented` | 同上 |
| E2-7 | 连续 5 块大小测量 | 320 KB / 350 KB / **1.6 MB** / 480 KB / 530 KB | 块大小分布,验证 8 MB 上限假设、佐证 NET 瓶颈优先级 |

---

## 9. 风险 / 未决项

- [ ] **DA-node RPC 未实测**:celestia-node 26658 端口需自建 light/full node(publicnode 不提供),`blob.GetAll` / `share.GetEDS` 的真实延迟与峰值带宽留待 Phase 2.x 自建节点后补 E2。
- [ ] **8 MB 峰值块未直接抓到**:5 连续块最大 1.6 MB,需扫历史高峰(Eclipse / Manta 集中提交时段)补充 E2。
- [ ] **rollup_type 枚举**:等 user ack 后再写入 `config/chains/*.yaml` schema。
- [ ] **Plugin 设计**:`CelestiaAdapter` 是否继承 `CosmosAdapter` 仅 override `fetch_blocks` + 加 `DANodeAdapter`?待 Phase 2.x 架构会议。
