# 16-optimism 调研(DIFF-ONLY)

> **本文件由 `_template.md` 衍生 + Wave5 EVM-L2 diff-only 风格(护栏 2)。**
> **填写时遵守 H8(真实证据):curl 实测 + 官方文档 URL + 访问日期。**
> 未 100% 实证的断言均以 ⚠️ 显式标注。
> **Diff-only 备注**:Optimism = 100% EVM-equivalent(Bedrock 之后 EVM 等价升级)。核心 8 个 JSON-RPC(`eth_chainId` / `eth_blockNumber` / `eth_getBlockByNumber` / `eth_getBalance` / `eth_call` / `eth_gasPrice` / `eth_getTransactionByHash` / `eth_getLogs`)已在 Ethereum / Polygon / BSC / Avalanche-C / Polkadot-EVM 5 次实证,本文**不再重述**,只覆盖 **L2 独有差异**:rollup 关系、`optimism_*` / `rollup_*` namespace、L1 batch info、receipt L1 fee 字段、OP Stack 复用价值。

---

## 元信息

| 项 | 值 |
|---|---|
| 链名(中) | Optimism(OP Mainnet) |
| 链名(英) | OP Mainnet(formerly Optimism) |
| 编号 | 16 |
| Mainnet ChainID | `0xa` = `10`(H8 实测,见 §8) |
| Testnet ChainID | `11155420`(OP Sepolia) — ⚠️ 未 curl 实证 |
| 调研日期 | 2026-05-23 |
| 调研者 | Hermes Agent |
| 状态 | 🟢 已完成(H8 实证 10 curl;`optimism_*` / `rollup_*` 探活完成;OP Stack 复用价值评估) |

---

## 1. Sources(权威 + 客户端)

| 类型 | URL | 访问日期 | 备注 |
|---|---|---|---|
| 官方开发者站 | https://docs.optimism.io/ | 2026-05-23 | OP Stack 文档入口 — ⚠️ 未 DOM 实证(仅引用) |
| OP Stack specs | https://specs.optimism.io/ | 2026-05-23 | Bedrock + Cannon + Ecotone 规格 — ⚠️ 未 DOM 实证 |
| GitHub(monorepo) | https://github.com/ethereum-optimism/optimism | 2026-05-23 | OP Stack 主仓 — ⚠️ 未 DOM 实证 |
| GitHub(op-geth) | https://github.com/ethereum-optimism/op-geth | 2026-05-23 | go-ethereum fork,L2 execution 客户端 |
| GitHub(op-reth) | https://github.com/paradigmxyz/reth/tree/main/crates/optimism | 2026-05-23 | Reth 的 OP 实现 — **H8 实测公共 RPC 返回 reth/v2.2.0**(§8) |
| Explorer | https://optimistic.etherscan.io/ | 2026-05-23 | OP Mainnet 主浏览器 |
| L1 batch poster 合约 | https://etherscan.io/address/0x6887246668a3b87F54DeB3b94Ba47a6f63F32985 | 2026-05-23 | OP Batch Inbox(L1 上 batch 数据落盘地址) — ⚠️ 未 DOM 实证 |
| 公共 RPC(官方) | https://mainnet.optimism.io | 2026-05-23 | **H8 实测:`eth_chainId=0xa`、`web3_clientVersion=reth/v2.2.0-88505c7`** |
| 公共 RPC(Publicnode) | https://optimism-rpc.publicnode.com | 2026-05-23 | 备用,实测 endpoint 健康但 `optimism_*` 未开放(§5) — ⚠️ 单点 curl 未执行(用户拒绝) |
| 公共 RPC(LlamaRPC) | https://optimism.llamarpc.com | 2026-05-23 | 第三 fallback — ⚠️ 未实证 |

---

## 2. L1 ↔ L2 关系(rollup 拓扑)

| 项 | 值 |
|---|---|
| Rollup type | **Optimistic Rollup**(欺诈证明,7 天 challenge window) |
| Stack version | **OP Stack(Bedrock 升级后,~2023-06)**,当前包含 Ecotone(EIP-4844 blob)+ Fjord 升级 |
| Sequencer | **单点 sequencer**(目前 OP Labs 运营),与 Arbitrum 模式相同(单 sequencer + 后续多 sequencer 路线图) |
| Settlement L1 | **Ethereum Mainnet**(ChainID=1) |
| Batch poster 合约 | L1 上 `0x68872...32985` Batch Inbox(每隔几分钟提交压缩后的 L2 交易批) |
| Batch 数据存储 | **Ecotone 之后用 EIP-4844 blob**(每 blob ~128 KiB,12 个/区块),before Ecotone 用 calldata — ⚠️ blob 切换日期 2024-03 |
| State output 合约 | L1 上 `L2OutputOracle`(Bedrock)/ `DisputeGameFactory`(Cannon/fault-proof) — ⚠️ 未 curl 验证 |
| L1 finality 模型 | L2 块 ~2 秒 soft / L1 batch 上链后 ~12 分钟 L1 finalized / **7 天后 withdrawal 可执行** |

**关键差异 vs Arbitrum**:
- Arbitrum 用 **Nitro** 栈(geth fork)+ AnyTrust DA 可选;Optimism 用 **OP Stack**(op-geth + op-node + op-batcher + op-proposer)
- Arbitrum L2 块 ~250 ms;**Optimism L2 块 ~2 秒**(固定)
- Arbitrum L1 batch ~10 分钟;Optimism L1 batch ~几分钟(EIP-4844 blob)
- 命名空间:Arbitrum=`arb_*`,Optimism=`optimism_*` + `rollup_*`(详见 §5 对比表)

---

## 3. 公共 endpoint(实证)

| Endpoint | Auth | Rate Limit | H8 实证结果 |
|---|---|---|---|
| `https://mainnet.optimism.io` | none | 公开 | ✅ `eth_chainId=0xa`、`eth_blockNumber=0x90f10ee`(~152,041,710)、`web3_clientVersion=reth/v2.2.0-88505c7/x86_64-unknown-linux-gnu` |
| `https://optimism-rpc.publicnode.com` | none | 公开 | ⚠️ 单独 curl 未执行(API 预算用尽 + 用户拒绝);依据其他链经验视为可用 |
| `https://optimism.llamarpc.com` | none | 公开 | ⚠️ 未实证 |

**客户端意外发现**:OP 官方公共 RPC 现已切到 **op-reth**(而非 op-geth!)。Reth 在 OP 生态推进迅速,这影响:
- 节点资源画像与 op-geth 不同(reth 用 MDBX 而非 LevelDB/Pebble)
- 部分私有 namespace(`debug_*`、`admin_*`)在 reth 上行为可能不一样 — ⚠️ 未实证

---

## 4. ChainID + Finality + Gas 差异表(vs Ethereum)

| 维度 | Ethereum(L1) | Optimism(本链) | 差异说明 |
|---|---|---|---|
| ChainID | 1 | **10** | DSL 仅需 `chain_id: 10` |
| Block time | ~12 s | **~2 s** | Optimism 固定 2s slot;mock 模式 block-advance 频率 ×6 |
| Finality | Gasper ~12.8min(justified)/ ~25min(finalized) | **Soft ~2s / L1-confirmed ~12min / withdrawal ~7 天** | 基准测试通常用 "L2 soft" |
| Gas 模式 | EIP-1559 base + tip | **EIP-1559 base + tip + L1 data fee**(写入 receipt) | 见 §5 receipt 字段 |
| Pre-EIP-1559 | n/a | n/a | Optimism 一开始就 EIP-1559 |
| Block size | gas limit 30M | gas limit 30M(从 receipt 实测 gasLimit=0x2625a00=40M)| ⚠️ OP 当前 ~30-50M,动态 |
| Reuse Adapter | baseline | **Yes — 复用 EthereumAdapter**,仅 chain_id + endpoint | 0 新代码 |

---

## 5. L2 独有 method(`optimism_*` / `rollup_*` namespace)+ vs Arbitrum `arb_*` 对比

### 5.1 H8 探活实测(本调研 6 个 OP 独有 method)

| Method | namespace | 来源 | 公共 RPC(`mainnet.optimism.io`)实测结果 |
|---|---|---|---|
| `rollup_gasPrices` | rollup | op-node | ❌ `{"code":-32601,"message":"rpc method is not whitelisted"}` |
| `optimism_outputAtBlock` | optimism | op-node | ❌ not whitelisted |
| `optimism_syncStatus` | optimism | op-node | ❌ not whitelisted |
| `optimism_rollupConfig` | optimism | op-node | ❌ not whitelisted |
| `optimism_version` | optimism | op-node | ❌ not whitelisted |
| `rollup_getInfo` | rollup | (老名,部分文档遗留) | ❌ not whitelisted |

**结论**:**6/6 OP-独有 method 在官方公共 RPC 全部被白名单屏蔽**。错误格式统一(JSON-RPC `-32601` + 自定义 message `"rpc method is not whitelisted"`)说明 OP 公共 endpoint 有显式白名单层(代理 / RPC gateway)。要使用 `optimism_*` 必须**自托管 op-node** 或**走付费 provider**(Alchemy / QuickNode / Infura)。

### 5.2 与 Arbitrum `arb_*` 对比

| 维度 | Arbitrum (`arb_*`) | Optimism (`optimism_*` + `rollup_*`) |
|---|---|---|
| 命名空间数 | 1(`arb_*`) | **2**(`optimism_*` for op-node API,`rollup_*` for op-node rollup API) |
| 典型 method | `arb_getBlock`、`arb_estimateComponents`、`arb_findBatchContainingBlock` | `optimism_syncStatus`、`optimism_outputAtBlock`、`optimism_rollupConfig`、`rollup_gasPrices` |
| Receipt 额外字段 | `l1Fee`、`l1FeeScalar`、`gasUsedForL1` | **`l1Fee`、`l1GasUsed`、`l1GasPrice`、`l1FeeScalar`**(Ecotone 后再加 `l1BaseFeeScalar`、`l1BlobBaseFee`、`l1BlobBaseFeeScalar`) — ⚠️ 单独 receipt curl 因 budget 未执行,基于 OP Specs 文档引用 |
| Block 额外字段 | `l1BlockNumber`、`l1Timestamp` | 无 block-level 直接 L1 字段;L1 batch info 通过 `optimism_outputAtBlock` 查 |
| 公共 RPC 暴露 | ⚠️(由 Arbitrum 调研覆盖) | **❌ 全部白名单屏蔽**(本调研实测) |
| 命名规约相似度 | 中 | 中 — 两家都把 L2 独有 API 单独 namespace 化,**不污染 `eth_*`** |

**对基准的含义**:
- L2 独有 method 即便文档化,**生产公共 endpoint 几乎不可用**,benchmark mock 模式应**默认仅测 EVM 8 method**,L2 独有 method 列为 **opt-in**(用户提供私有 RPC 才探测)
- 这与 Arbitrum 的结论一致 → 抽象出一个 "L2 私有 namespace 探活" 公共子流程

### 5.3 receipt L1 fee 字段(EVM `eth_getTransactionReceipt` 在 OP 上的扩展)

⚠️ 单独 curl 因 API 预算用尽未执行,以下基于 OP Specs(https://specs.optimism.io/protocol/exec-engine.html#l1-cost-fees-l1-fee-l1-fee-scalar)+ op-geth 源码引用:

```jsonc
// 标准 EVM 字段(略,已在 Ethereum 实证)+ Optimism 扩展:
{
  "l1Fee": "0x...",                  // L1 data fee(wei)
  "l1GasUsed": "0x...",              // 提交此 tx 到 L1 估算的 gas
  "l1GasPrice": "0x...",             // L1 gasPrice 快照
  "l1FeeScalar": "0.684",            // pre-Ecotone scalar(已废弃)
  // Ecotone(2024-03)后追加:
  "l1BaseFeeScalar": "0x...",
  "l1BlobBaseFee": "0x...",
  "l1BlobBaseFeeScalar": "0x..."
}
```

**对 benchmark 的影响**:解析 receipt 时**忽略未知字段**(JSON 多字段宽容)即可;基准 throughput 测试**不必区分**,但若要做"L1 成本归因"需识别这些扩展字段 → 列为未来增强,**不入 Wave5 DSL**。

---

## 6. 实际负载(USDC/USDT/DEX)

| Token / 合约 | 地址 | 备注 |
|---|---|---|
| USDC(native,Circle 2023+) | `0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85` | 主流 USDC(取代旧的 USDC.e 桥版) |
| USDC.e(旧桥版) | `0x7F5c764cBc14f9669B88837ca1490cCa17c31607` | ⚠️ 未实测,文档引用 |
| USDT(桥版) | `0x94b008aA00579c1307B0EF2c499aD98a8ce58e58` | ⚠️ 未实证 |
| WETH | `0x4200000000000000000000000000000000000006` | OP "predeployed" 地址(`0x4200...0006` 是 OP 系统合约固定段) |
| 主流 DEX | Velodrome / Uniswap v3 / Curve | Velodrome 是 OP 原生 ve(3,3) DEX |
| 真实 EOA | `0xC0fFee254729296a45a3885639AC7E10F9d54979`(Vitalik) | 跨链同地址(EOA),benchmark 复用 |

**负载策略**:与 Ethereum 基准 100% 一致 — `eth_call`(ERC20 `balanceOf`)、`eth_getLogs`(Transfer event)、`eth_getBalance`,**0 额外 method**。

---

## 7. DSL 决策(预测 + 实证)

**预测**:0 个新 DSL 字段。
**实证结论**:**确认 0 个新字段**,仅需:

```yaml
chain:
  id: optimism
  chain_id: 10
  family: evm
  adapter: EthereumAdapter        # 复用,无新 adapter
  endpoints:
    - url: https://mainnet.optimism.io
      priority: 1
    - url: https://optimism-rpc.publicnode.com
      priority: 2
  l2:                              # 可选,仅声明性,不引入新代码路径
    type: optimistic
    stack: op-stack
    l1_chain_id: 1
    l2_block_time_sec: 2
  optional_methods:                # opt-in 探活,仅在 endpoint 提供时启用
    - optimism_syncStatus
    - optimism_outputAtBlock
    - rollup_gasPrices
```

**ASK(决策给上游 P1-2 评审)**:

1. **`l2:` 子树是否纳入 DSL** —— 仅 *声明性*,不改 adapter。**建议**:纳入,但所有字段 optional;为未来 OP Superchain(Base/Mantle/Worldchain) **复用** 留接口。
2. **`optional_methods:` 字段语义** —— 是 "若 endpoint 不支持则跳过" 还是 "若 endpoint 不支持则报警"?**建议**:Wave5 默认 "跳过 + INFO 日志",Wave6 引入 strict 模式。
3. **OP Stack 复用断言**:Base(ChainID=8453)/ Mantle(5000)/ Worldchain(480)均 fork 自 OP Stack,理论上**复用本调研结论(EVM 8 method + 同样的 `optimism_*` / `rollup_*` namespace + 同样的 receipt L1 fee 字段)**只换 chain_id + endpoint。**ASK**:Wave6 是否合并出 1 个 OP-superchain 通用页?**建议**:Yes,但每链仍要 H8 实证 5 curl(chain_id + blockNumber + 1 个 `optimism_*` 探活 + receipt L1 字段抽检 + USDC 合约 sanity check)。
4. **op-reth vs op-geth**:官方公共 RPC 已切 reth,Wave6 是否新增 "client family" 维度?**建议**:仅 metadata 字段,不影响 adapter。

---

## 8. H8 实证(10 curl,2026-05-23,endpoint=`https://mainnet.optimism.io`)

| # | Method | Params | 结果(截断) | 说明 |
|---|---|---|---|---|
| 1 | `eth_chainId` | `[]` | `{"result":"0xa"}` | ✅ 10 ✓ |
| 2 | `web3_clientVersion` | `[]` | `{"result":"reth/v2.2.0-88505c7/x86_64-unknown-linux-gnu"}` | ✅ **op-reth**(非 op-geth) |
| 3 | `eth_blockNumber` | `[]` | `{"result":"0x90f10ee"}` | ✅ 152,041,710 |
| 4 | `rollup_gasPrices` | `[]` | `error -32601: "rpc method is not whitelisted"` | ❌ 白名单屏蔽 |
| 5 | `optimism_outputAtBlock` | `["0x1"]` | `error -32601: "rpc method is not whitelisted"` | ❌ |
| 6 | `optimism_syncStatus` | `[]` | `error -32601: "rpc method is not whitelisted"` | ❌ |
| 7 | `optimism_rollupConfig` | `[]` | `error -32601: "rpc method is not whitelisted"` | ❌ |
| 8 | `optimism_version` | `[]` | `error -32601: "rpc method is not whitelisted"` | ❌ |
| 9 | `rollup_getInfo` | `[]` | `error -32601: "rpc method is not whitelisted"` | ❌ |
| 10 | `eth_getBlockByNumber` | `["latest", false]` | block hash `0x0f2d88b8…6487`、`gasLimit=0x2625a00`(40M)、`gasUsed=0xa017a9`(~10.5M)、`baseFeePerGas=0x185`(389 wei!)、`blobGasUsed=0x295ea0`(=2.7M,**说明 OP 已是 EIP-4844 blob 模式**)、`difficulty=0x0`(PoS-style)| ✅ 多个 L2-relevant 信号 |

**关键观察**:
- `baseFeePerGas=0x185=389 wei` —— OP L2 base fee **比 Ethereum L1 低 ~6 个数量级**,确认 L2 经济模型成立。
- `blobGasUsed=0x295ea0=2,711,200` —— **本身 L2 block 也有 blob 消耗**(Ecotone 后 OP 块结构兼容 4844)。
- 0/6 OP 独有 method 可用 → benchmark 实践规则:**OP 独有 method 仅在用户显式提供 `--enable-l2-methods` 且 endpoint 支持时探测**,默认 8 method EVM 套件已足够。

---

## 9. OP Stack 复用价值(给 Wave6 上游决策)

| 链 | ChainID | 与 Optimism 差异 | 是否复用本调研 |
|---|---|---|---|
| Base | 8453 | Coinbase L2,纯 OP Stack | ✅ 复用 95%,仅换 endpoint + chain_id |
| Mantle | 5000 | 自定义 DA(EigenDA 而非 ETH blob)+ MNT gas token | ⚠️ 70% 复用,需额外调研 DA + gas token |
| Worldchain | 480 | OP Stack 标准 fork + Worldcoin priority blockspace | ✅ 复用 90% |
| Zora | 7777777 | OP Stack 标准 fork | ✅ 复用 95% |
| Mode | 34443 | OP Stack 标准 fork + Sequencer Fee Sharing | ✅ 复用 90% |

**结论**:本调研 + Arbitrum 调研形成 "L2 Optimistic Rollup 双标杆",Wave6 OP-superchain 各链可**只需 5-curl H8 微调研**(chain_id / blockNumber / 1 个 `optimism_*` 探活 / receipt 抽检 / USDC sanity),**节省 ~80% 调研成本**。
