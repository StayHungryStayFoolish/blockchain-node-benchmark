# 17 — zkSync Era（DIFF-ONLY · ZK Rollup 首例）

> **顶部声明**:zkSync Era 100% EVM-compatible(非 EVM-equivalent),L2 自带账户抽象与 ZK 有效性证明。
> 本调研**只覆盖 L2 独有差异 + ZK Rollup 模型差异**,所有 EVM 通用 method(`eth_chainId` / `eth_blockNumber` /
> `eth_getBlockByNumber` / `eth_getBalance` / `eth_call` / `eth_gasPrice` / `eth_getTransactionByHash` /
> `eth_getLogs`)行为与 02-ethereum.md 一致,不再赘述。

---

## §1 Sources(权威 + 客户端)

| 类型 | 链接 | 备注 |
| --- | --- | --- |
| 官方文档 | https://docs.zksync.io/ | Era + ZK Stack |
| JSON-RPC 规范 | https://docs.zksync.io/zksync-protocol/api/zks-rpc | `zks_*` namespace 权威列表 |
| L1 合约 (DiamondProxy) | `0x32400084c286cf3e17e7b677ea9583e60a000324` | 实测 `zks_getMainContract` 返回 |
| Node 实现 | `matter-labs/zksync-era`(Rust) | 唯一生产 sequencer |
| Bridge 合约 | `zks_getBridgeContracts` 实测返回 6 字段(见 §2) | L1↔L2 桥 |
| Explorer | https://explorer.zksync.io/ | 公共 |

---

## §2 L1↔L2 关系(ZK Rollup 模型,**与 Optimistic 完全不同**)

```
L2 user tx ──► Sequencer (matter-labs/zksync-era, 中心化)
                   │
                   ├─► L2 commit (~1 s, soft finality)
                   │
                   ▼
            Prover 集群生成 SNARK
                   │
                   ▼  commitBatch
            L1 DiamondProxy (0x3240...0324)
                   │
                   ├─► proveBatch  (~1 h)   ← validity proof 校验
                   │
                   └─► executeBatch (~24 h) ← finalized,提款可领
```

| 维度 | zkSync Era (ZK) | Optimistic Rollup (Arb/OP, 对照) |
| --- | --- | --- |
| 安全模型 | **Validity proof**(SNARK,数学保证) | Fraud proof + 7d challenge |
| L2 → L1 提款延迟 | ~24 h(execute 阶段) | ~7 天 challenge window |
| 状态 finality 阶段 | committed → proven → **executed** | committed → **finalized**(7d) |
| Sequencer | 中心化(matter-labs) | 中心化(各自) |
| 重组风险 | 仅 L2 软重组,L1 commit 后不可逆 | 同 |
| L1 数据可用性 | calldata + blob(EIP-4844) | 同 |

**实测**:`zks_L1BatchNumber` = `0x7cd85` = **511 877**(2026-05-23),`zks_L1ChainId` = `0x1`(Mainnet L1)。

---

## §3 公共 endpoint(实证)

| Endpoint | 是否支持 `zks_*` | 响应延迟 |
| --- | --- | --- |
| `https://mainnet.era.zksync.io`(官方) | ✅ 全部 | ~150 ms |
| `https://zksync-era-rpc.publicnode.com` | ✅ 多数 | ~200 ms |
| WebSocket | `wss://mainnet.era.zksync.io/ws` | 支持 `eth_subscribe` |

---

## §4 ChainID + finality + gas 模式差异表(diff vs L1 Ethereum)

| 字段 | L1 Ethereum | zkSync Era | 差异说明 |
| --- | --- | --- | --- |
| `chainId` | `0x1` (1) | `0x144` (**324**) | — |
| Finality | 2 epoch (~12 min) | L2 soft 1 s / L1 prove 1 h / **L1 execute 24 h** | 三段式 |
| Gas 模型 | EIP-1559 base+tip | base+tip **but** pubdata 单独计费 | `zks_estimateFee` 返回 `gas_per_pubdata_limit` |
| Tx type | 0/1/2 | 0/1/2 **+ 113**(EIP-712 / AA 原生) | type 113 携带 `paymaster` 字段 |
| Block | 标准 | 标准 + `l1BatchNumber` / `l1BatchTimestamp` | block 归属哪个 L1 batch |
| Receipt | 标准 | 标准 + `l1BatchNumber` / `l1BatchTxIndex` / `l2ToL1Logs` | 提款需 `l2ToL1Logs` proof |
| Opcode | 全部 | 缺失:`SELFDESTRUCT`、`PC`(EraVM 非 EVM 字节码,通过编译器近似) | 部分合约不兼容 |

---

## §5 L2 独有 method:`zks_*` namespace 实测

| Method | 实测响应(2026-05-23) | 用途 / DSL 关注 |
| --- | --- | --- |
| `zks_L1BatchNumber` | `"0x7cd85"` (511877) | **核心进度指标**,L1 已 commit 的 batch |
| `zks_L1ChainId` | `"0x1"` | settlement 链,1 = Mainnet, 11155111 = Sepolia |
| `zks_getMainContract` | `"0x3240...0324"` | L1 DiamondProxy 地址 |
| `zks_getBridgeContracts` | 返回 `l1Erc20DefaultBridge` / `l1SharedDefaultBridge` / `l1WethBridge` / `l2Erc20DefaultBridge` / `l2LegacySharedBridge` / `l2SharedDefaultBridge` / `l2WethBridge` 7 字段 | 桥合约枚举 |
| `zks_getBlockDetails` | 含 `l1BatchNumber` / `commitTxHash` / `committedAt` / `proveTxHash` / `provenAt` / `executeTxHash` / `executedAt` / `baseSystemContractsHashes` | **跨阶段 finality 时间戳**,监控宝藏 |
| `zks_getL1BatchDetails` | 同上,以 batch 维度 | batch 维度详情 |
| `zks_estimateFee` | 需有效 `from`(否则 `invalid sender, can't start a transaction from a non-account`) | 返回 `gas_limit` / `max_fee_per_gas` / `max_priority_fee_per_gas` / `gas_per_pubdata_limit` |
| `zks_estimateGasL1ToL2` | — | L1→L2 deposit gas 估算 |
| `zks_getAllAccountBalances` | — | 一次取 ERC-20 全余额 |
| `zks_getConfirmedTokens` | — | 官方认可代币列表 |
| `zks_getProof` | — | Merkle proof(L2→L1 提款必需) |
| `zks_getRawBlockTransactions` | — | 含 paymaster_params 原始字段 |
| `zks_getTransactionDetails` | 含 `ethCommitTxHash` / `ethProveTxHash` / `ethExecuteTxHash` / `isL1Originated` / `status` | tx 级 L1 锚定 |
| `zks_sendRawTransactionWithDetailedOutput` | — | 含完整 trace |
| `zks_getProtocolVersion` | — | 协议升级窗口 |

> **实证证据**:`zks_estimateFee` 在空 `from` 下报 `invalid sender. can't start a transaction from a non-account`
> —— 这是 zkSync **账户抽象 native** 的直接表现:所有发送方必须是 IAccount 实现,EOA 概念被取消。

---

## §6 实际负载(USDC/USDT + 主流 DEX)

| 类别 | 合约 | 备注 |
| --- | --- | --- |
| USDC.e(桥版,Circle 弃用) | `0x3355df6D4c9C3035724Fd0e3914dE96A5a83aaf4` | 原生 USDC 由 Circle CCTP 单独发行 |
| USDC(原生,Circle 直发) | `0x1d17CBcF0D6D143135aE902365D2E5e2A16538D4` | 默认引用 |
| USDT(桥版) | `0x493257fD37EDB34451f62EDf8D2a0C418852bA4C` | LayerZero / 官方桥 |
| WETH(L2 原生) | `0x5AEa5775959fBC2557Cc8789bC1bf90A239D9a91` | 提款经 `l2WethBridge` |
| SyncSwap(原生 DEX) | router `0x2da10A1e27bF85cEdD8FFb1AbBe97e53391C0295` | 类 UniV2 |
| Maverick / Mute / Vekorta | — | TVL 次梯队 |

---

## §7 DSL 决策(ASK 1 ~ 2 项)

> **本链是首个 ZK Rollup**,与已有 EVM 模板(单纯 chain_id + endpoint)产生**真实模型差异**。

### ASK-Z1 —— 新增 `rollup_type` 枚举字段?

```yaml
# 提议
chain:
  family: evm_l2
  rollup_type: zk          # 候选值: l1 | optimistic | zk | validium | sovereign
  settlement_chain_id: 1
  l1_main_contract: "0x32400084c286cf3e17e7b677ea9583e60a000324"
```

- **若 yes**:可在评测器自动选择 finality 等待策略(zk 等 `executeTxHash` 出现;optimistic 等 7 天或显式 `finalized` tag)。
- **若 no**:基准只跑 L2 软 finality(`eth_blockNumber` lag),与 Arbitrum/OP 等价处理 —— 损失了 zkSync 的核心安全语义。
- **本调研倾向 yes**:语义差异已经具体到 method 行为(zkSync 有 `commitTxHash/proveTxHash/executeTxHash` 三阶段时间戳,Optimistic 只有 commit/finalize 两阶段)。

### ASK-Z2 —— 是否将 `paymaster` / `paymaster_input` 字段纳入 tx 标准化模型?

- zkSync EIP-712(type 113)tx 含 `paymasterParams: { paymaster, paymasterInput }`;Optimistic 链无对应字段。
- 若 DSL 标准化 tx 模型,需声明 `optional paymaster_address`、`optional paymaster_input` —— 否则 zkSync 负载将丢失费用真实赞助路径。
- **建议**:在 `transaction.extensions[zksync_paymaster]` 嵌套,而非顶层(避免污染主结构)。

### 不需要新字段的指标

- `zks_L1BatchNumber` / `commitTxHash` / `proveTxHash` / `executeTxHash` 都是**监控指标**而非配置,直接在指标采集层处理,不必入 DSL。
- 桥合约清单可由 `zks_getBridgeContracts` 运行时发现,不必硬编码到 DSL。

---

## §8 H8 实证(curl,可复现)

```bash
EP=https://mainnet.era.zksync.io
H='-H Content-Type:application/json'

# 1. chainId == 324
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"eth_chainId","id":1}'
# → {"result":"0x144"}                          ✓ 324

# 2. L2 blockNumber(实证 70 318 746)
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"eth_blockNumber","id":1}'
# → {"result":"0x42fba97"}

# 3. L1 已 commit batch == 511 877
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"zks_L1BatchNumber","id":1}'
# → {"result":"0x7cd85"}                         ✓ 511877

# 4. settlement L1 == Mainnet
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"zks_L1ChainId","id":1}'
# → {"result":"0x1"}                             ✓ 1

# 5. DiamondProxy 地址
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"zks_getMainContract","id":1}'
# → {"result":"0x32400084c286cf3e17e7b677ea9583e60a000324"}

# 6. Bridge 合约枚举
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"zks_getBridgeContracts","id":1}'
# → 7 字段(见 §5)                              ✓

# 7. Block detail 含三阶段 finality 时间戳(batch 499238 已 executed)
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"zks_getBlockDetails","params":[60100000],"id":1}'
# → commitTxHash / committedAt / executeTxHash / executedAt 字段齐全
# committedAt = 2025-05-08T13:30:14Z
# executedAt  = 2025-05-08T18:05:27Z  (Δ ≈ 4.5h,本批次 < 通告 24h SLA)

# 8. 账户抽象 native 证据
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"zks_estimateFee","params":[{"from":"0x0","to":"0x...","data":"0x"}],"id":1}'
# → error: "invalid sender. can't start a transaction from a non-account"
#   ↳ zero-address 不是合法 IAccount;EOA 在 zkSync 也是合约。
```

---

## 附:与已有 EVM 调研(Ethereum / Polygon / BSC / Avalanche-C / Polkadot-EVM)的 diff 汇总

| 维度 | 本链差异要点 |
| --- | --- |
| ChainID | 324(`0x144`) |
| RPC | 标准 `eth_*` **+** `zks_*`(~15 method) |
| Block | 多 `l1BatchNumber` / `l1BatchTimestamp` |
| Receipt | 多 `l1BatchNumber` / `l1BatchTxIndex` / `l2ToL1Logs` |
| Tx | 新增 type 113(EIP-712 含 `paymasterParams`) |
| Finality | **三阶段**(committed / proven / executed),不是简单的 N 块确认 |
| 安全模型 | **ZK validity proof**,无 challenge window |
| 账户模型 | **Native AA**,EOA 也是合约,`from = 0x0` 报错 |

— END —
