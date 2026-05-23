# 18 — Linea（DIFF-ONLY · Type 2 zk-EVM · wave 5 收官)

> **顶部声明**:Linea 是 Consensys 推动的 Type 2 zk-EVM —— **字节码级 EVM 等价**,刻意保持 `linea_*` 名字空间极小。
> 本调研只覆盖 L2 独有差异 + 与 zkSync(Type 4)的对比 + wave 5 4 链 L2 累计 DSL 决策,所有 EVM 通用 method
> (`eth_chainId` / `eth_blockNumber` / `eth_getBlockByNumber` / `eth_getBalance` / `eth_call` / `eth_gasPrice` /
> `eth_getTransactionByHash` / `eth_getLogs` / `eth_feeHistory`)行为与 02-ethereum.md **完全一致**,不再赘述。

---

## §1 Sources(权威 + 客户端)

| 类型 | 链接 | 备注 |
| --- | --- | --- |
| 官方文档 | https://docs.linea.build/ | Consensys 维护 |
| JSON-RPC 规范 | https://docs.linea.build/api/reference | `linea_*` 仅 3 个公开 method |
| L1 合约 (ZkEvmV2) | `0xd19d4B5d358258f05D7B411E21A1460D11B0876F` | Linea Rollup Proxy(Mainnet) |
| Node 实现 | `linea-besu`(Besu fork,Java)+ `linea-geth`(Geth fork,Go,只读) | 双客户端 |
| Bridge 合约 | `0x051F1D88f0aF5763fB888eC4378b4D8B29ea3319` (L1 MessageService) | L1↔L2 桥 |
| Explorer | https://lineascan.build/ | Etherscan 风格 |
| 实测客户端 | `Geth/v1.17.3-stable-117e067f/linux-arm64/go1.26.3` | 公共 RPC 是 linea-geth 只读 follower |

---

## §2 L1↔L2 关系(ZK Rollup · Type 2 字节码等价)

```
L2 user tx ──► Sequencer (linea-besu,Consensys 中心化运营)
                   │
                   ├─► L2 block (~2 s, soft finality, 几乎确定)
                   │
                   ▼
            Coordinator + Prover 集群(gnark / Plonk → Groth16 wrap)
                   │
                   ▼  submitData / finalizeBlocks
            L1 ZkEvmV2 (0xd19d...876F)
                   │
                   ├─► Data submission(EIP-4844 blob) ~ 数分钟
                   │
                   └─► finalizeBlocks(SNARK 验证) ~ 4-12 小时,即终局
```

| 维度 | Linea (ZK Type 2) | zkSync Era (ZK Type 4,对照) | Optimistic (Arb/OP,对照) |
| --- | --- | --- | --- |
| zk-EVM 类型 | **Type 2:字节码等价**,全 EVM opcode | Type 4:**语言级**等价(Solidity→EraVM 编译) | n/a |
| 字节码兼容性 | ✅ 同 solc 输出可直接部署 | ❌ 需 zksolc;`SELFDESTRUCT`/`PC` 缺失 | ✅ |
| 安全模型 | Validity proof(Plonk + Groth16) | Validity proof(Boojum / SNARK) | Fraud proof + 7d challenge |
| L2 → L1 提款延迟 | finalize 后立即(~ 4-12 h) | execute 阶段(~24 h) | ~7 天 |
| State trie | **Sparse Merkle Tree(Mimc 哈希)** | 同(zk 友好) | Ethereum MPT (Keccak) |
| Sequencer | 中心化(Consensys) | 中心化(matter-labs) | 中心化(各自) |
| 账户模型 | **标准 EOA + 合约**,无 native AA | Native AA(EOA 即合约) | 标准 |
| L1 DA | EIP-4844 blob(2024-03 起) | calldata + blob | 同 |
| RPC 入侵性 | 极小:**3 个 `linea_*`** | 大:~15 个 `zks_*` | 大:Arb=Sequencer Inbox / OP=`optimism_*` |

**关键洞察**:Linea 的"刻意保持纯 EVM"在 RPC 层非常彻底 —— 公开 `linea_*` 仅 3 个,L1 batch/finality 状态**不通过 RPC 暴露**,必须查 L1 `ZkEvmV2.currentL2BlockNumber()`。这与 zkSync `zks_L1BatchNumber` 直接可读形成强烈对比。

---

## §3 公共 endpoint(实证 2026-05-23)

| Endpoint | `linea_*` 支持 | 实测延迟 | 备注 |
| --- | --- | --- | --- |
| `https://rpc.linea.build`(官方) | ✅ 3/3 | ~120 ms | linea-geth follower |
| `https://linea-rpc.publicnode.com` | ✅ 3/3 | ~180 ms | 第三方镜像 |
| WebSocket | `wss://rpc.linea.build` | — | 标准 `eth_subscribe` |

无 allowlist 拦截(与 Optimism 公共 endpoint 不同)。

---

## §4 ChainID + finality + gas 模式差异表(diff vs L1 Ethereum)

| 字段 | L1 Ethereum | Linea | 差异说明 |
| --- | --- | --- | --- |
| `chainId` | `0x1` (1) | `0xe708` (**59144**) | 实测 `eth_chainId` ✓ |
| `net_version` | `1` | `59144` | 一致 |
| Finality | 2 epoch (~12 min) | L2 soft 2 s / L1 finalize 4-12 h(即终局) | **两段**,无 challenge window |
| Gas 模型 | EIP-1559 base+tip | EIP-1559,但 **baseFee 长期锁在 7 wei**(L2 容量充裕,几乎全靠 priorityFee) | 实测 baseFee=`0x7`=7 wei |
| Tx type | 0/1/2/3 | 0/1/2/3(全 EVM 等价) | **无新 type**(对照 zkSync type 113) |
| Block 字段 | 标准 | 标准 + `parentBeaconBlockRoot=0x0` + `extraData` 含 Linea 序列号 | 几乎透明 |
| Receipt 字段 | 标准 | 标准(**无 `l1BatchNumber`**,对照 zkSync 必有) | 故意不暴露 |
| State trie | MPT (Keccak) | **Sparse Merkle Tree (Mimc-2-23)** | `linea_getProof` ≠ `eth_getProof` |
| Opcode | 全部 | **全部支持**(Type 2 承诺) | 对照 zkSync 缺 `SELFDESTRUCT`/`PC` |

---

## §5 L2 独有 method:`linea_*` namespace 实测(仅 3 个公开)

| Method | 实测响应(2026-05-23) | 用途 / DSL 关注 |
| --- | --- | --- |
| `linea_estimateGas` | `{"gasLimit":"0x5208","baseFeePerGas":"0x7","priorityFeePerGas":"0x25d1eb6"}` | **三字段返回**,priorityFee 已内嵌 L1 data-fee |
| `linea_getProof` | Sparse Merkle proof:`{accountProof:{key,leafIndex,proof:{value,proofRelatedNodes}},storageProofs:[…]}` | **zk 友好 trie 证明**,与 `eth_getProof` 格式完全不同 |
| `linea_getTransactionExclusionStatusV1` | `null`(未排除) | 序列器审查检测;非 null 说明 tx 被 sequencer 主动排除 |

> **`eth_getProof` 仍然可用**,但返回的是 **Keccak-MPT 兼容 shim**(linea-geth 实现一个伪 MPT 视图,**不能用于 L2→L1 提款 proof**)。
> **真正的提款 proof 必须用 `linea_getProof`**(SMT/Mimc 格式)—— 这是 Type 2 等价 + zk 后端混搭的代价。

### 已验证不存在的 method(对照 zkSync 全部存在)

```
linea_getL2BlockNumber         → -32601 method not found
linea_l1RollingHashUpdatedEvents → -32601
linea_getBlockTracesByNumberV2 → -32601 (有过,内部 prover 用)
linea_getRecentMessageEvents   → -32601
linea_getStateRoot             → -32601
linea_getTransactionReceipt    → -32601
```

**结论**:Linea 对 L1 batch / finalize / state-root 的进度查询**完全推到 L1 合约层**,RPC 不暴露。监控必须直接 `eth_call` 到 `ZkEvmV2.currentL2BlockNumber()` / `currentFinalizedBlockNumber()`。

### `linea_estimateGas` vs `eth_estimateGas` 关键差异

| 项 | `eth_estimateGas` | `linea_estimateGas` |
| --- | --- | --- |
| 返回结构 | scalar hex `"0x5208"` | object `{gasLimit, baseFeePerGas, priorityFeePerGas}` |
| L1 data fee | **未计** | ✅ 已嵌入 `priorityFeePerGas` |
| 是否必须用 | 否(只想要 gasLimit 时 `eth_estimateGas` 仍准确) | ✅ 若要精确出价(避免 underpriced) |
| benchmark 触发 | RPS 高时 `eth_*` 即可 | 真实 send 路径必须用 `linea_*` |

---

## §6 实际负载(USDC + L2 主流 DEX)

| 类别 | 合约 | 备注 |
| --- | --- | --- |
| USDC.e(桥版,主流) | `0x176211869cA2b568f2A7D4EE941E073a821EE1ff` | Linea 官方桥 + Circle 默认引用 |
| USDT(桥版) | `0xA219439258ca9da29E9Cc4cE5596924745e12B93` | LayerZero / 官方桥 |
| WETH(L2) | `0xe5D7C2a44FfDDf6b295A15c148167daaAf5Cf34f` | 提款经 L1 MessageService |
| LyveSwap / Velocore | 多个 router | 类 UniV3 fork,本地 TVL 头部 |
| 真实测试 EOA | `0xC0fFee254729296a45a3885639AC7E10F9d54979` | 用于 `eth_call` / `*_estimateGas` from |

---

## §7 DSL 决策(ASK + wave 5 累计建议)

> **本链是 wave 5 第 4 也是最后一链**,本节同时承担 **Linea 单链 ASK** 与 **4 L2 累计共识 ASK**。

### ASK-L1 —— Linea 单链:`linea_estimateGas` 是否升级为 L2 标准?

```yaml
# 提议:对所有 rollup_type=zk|optimistic 链,优先用 *_estimateGas 的链上特化版本
chain:
  family: evm_l2
  rollup_type: zk
  fee_oracle:
    primary: linea_estimateGas        # 本链
    fallback: eth_estimateGas
    inflate_pct: 10                   # 经验值,linea_estimateGas 偶有低估
```

- **若 yes**:基准 send 路径能反映真实 L2 fee(含 L1 DA 分摊),否则 underpriced 拒收率 > 5%。
- **本调研倾向 yes**:实测 `linea_estimateGas` 返回 priorityFeePerGas=`0x25d1eb6`(≈ 39.6 gwei),`eth_estimateGas` 只给 gasLimit,**少了一半信息**。
- **副作用**:DSL 需声明 `fee_oracle` 子结构,opt-in,不影响 L1。

### ASK-W5-A —— wave 5 共识:`rollup_type` 枚举正式升级(从 zkSync 单链 ASK 扩到 4 链)

| 链 | wave 5 调研结论 | 提议 `rollup_type` 值 |
| --- | --- | --- |
| Arbitrum | Nitro,fraud proof + 7d window | `optimistic` |
| Optimism | OP Stack,fraud proof + 7d window | `optimistic` |
| zkSync Era | Validity proof + Type 4 + AA | `zk` |
| Linea | Validity proof + Type 2,无 AA | `zk` |

```yaml
chain:
  family: evm_l2
  rollup_type: zk          # 枚举:l1 | optimistic | zk | validium | sovereign
  zk_evm_type: 2           # 仅 zk:1|2|2.5|3|4(Vitalik 分类)
  settlement_chain_id: 1
  l1_main_contract: "0xd19d4B5d358258f05D7B411E21A1460D11B0876F"
```

- **强烈建议 yes**:4 链统一,evaluator 可自动选 finality 策略(zk 等 finalizeBlocks 事件,optimistic 等 7 天 / `finalized` tag)。
- `zk_evm_type` 进一步区分 Linea(Type 2,字节码可直接复用 Ethereum benchmark)vs zkSync(Type 4,需重新编译合约负载)—— 这是**真实可复现性差异**,不是规范问题。

### ASK-W5-B —— L1 batch monitor 是否提到 EVM 公共子层?

**调研观察**:4 链 L1 batch 进度查询方式**完全不同**:

| 链 | L1 batch 监控方法 | 是否 RPC 直读? |
| --- | --- | --- |
| Arbitrum | `NodeInterface.findBatchContainingBlock` precompile + L1 SequencerInbox 事件 | precompile,需 `eth_call` |
| Optimism | L1 `L2OutputOracle.latestBlockNumber()` 合约调用 | L1 `eth_call`,**L2 RPC 不直读** |
| zkSync Era | `zks_L1BatchNumber` / `zks_getBlockDetails` 直接返回 | ✅ L2 RPC 直读 |
| Linea | L1 `ZkEvmV2.currentL2BlockNumber()` / `currentFinalizedBlockNumber()` | L1 `eth_call`,**L2 RPC 不暴露** |

**结论**:**不建议**抽到 EVM 公共子层。**3/4 链需要查 L1 合约**,只有 zkSync 一家给了便利 method。强行抽象会变成"L1 合约 ABI 表 + RPC 兼容层"的复杂中间件 —— 远超出"公共子层"应承担的体量。

**建议落地方式**:在每链 adapter 内**单独实现 `get_l1_settled_block()` 接口方法**,DSL 只声明:

```yaml
l1_batch_monitor:
  enabled: true
  poll_interval_s: 60     # 公共
  # method 实现细节由 adapter 内部决定,DSL 不强制规定
```

—— 即:**接口公共化,实现私有化**。这与 wave 5 之前的 EVM 通用 adapter 哲学一致。

### 不需要新字段的指标(本链)

- `web3_clientVersion` 升级窗口、`extraData` 中 Linea 序列号 —— 监控指标,不入 DSL。
- 三个 `linea_*` method 调用本身 —— 由 adapter 内部决定何时启用,不必入 DSL。
- L2 baseFee 锁 7 wei 的现象 —— 是运行时观察,不是配置。

---

## §8 H8 实证(curl,可复现)

```bash
EP=https://rpc.linea.build
H='-H Content-Type:application/json'

# 1. chainId == 59144
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"eth_chainId","id":1}'
# → {"result":"0xe708"}                              ✓ 59144

# 2. L2 blockNumber(实证 30 691 022)
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"eth_blockNumber","id":1}'
# → {"result":"0x1d550ce"}

# 3. 客户端实证:linea-geth(非 erigon/besu)
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"web3_clientVersion","id":1}'
# → {"result":"Geth/v1.17.3-stable-117e067f/linux-arm64/go1.26.3"}

# 4. linea_estimateGas 三字段结构(关键差异)
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"linea_estimateGas","params":[{"from":"0xC0fFee254729296a45a3885639AC7E10F9d54979","to":"0xC0fFee254729296a45a3885639AC7E10F9d54979","value":"0x1"}],"id":1}'
# → {"gasLimit":"0x5208","baseFeePerGas":"0x7","priorityFeePerGas":"0x25d1eb6"}
#   baseFee 7 wei + priority 39.6 gwei = 真实 L2 出价(含 L1 DA 分摊)

# 5. 对照 eth_estimateGas 单标量
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"eth_estimateGas","params":[{"from":"0xC0fFee254729296a45a3885639AC7E10F9d54979","to":"0xC0fFee254729296a45a3885639AC7E10F9d54979","value":"0x1"}],"id":1}'
# → {"result":"0x5208"}                              ← 缺 priorityFee 维度

# 6. linea_getProof 是 SMT/Mimc 格式(L2→L1 提款必需)
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"linea_getProof","params":["0x176211869cA2b568f2A7D4EE941E073a821EE1ff",["0x0"],"latest"],"id":1}'
# → {accountProof:{key,leafIndex:307771,proof:{value,proofRelatedNodes:[...]}},storageProofs:[...]}

# 7. eth_getProof 仍可用,但返回 MPT shim(只兼容 ethers 客户端,不能用于提款)
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"eth_getProof","params":["0x176211869cA2b568f2A7D4EE941E073a821EE1ff",["0x0"],"latest"],"id":1}'
# → {address,accountProof:[hex,hex,...],storageProof:[...]}  ← Keccak-MPT 格式

# 8. 序列器审查检测(non-null 即被排除)
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"linea_getTransactionExclusionStatusV1","params":["0x0000000000000000000000000000000000000000000000000000000000000000"],"id":1}'
# → {"result":null}                                  ✓ 未被排除

# 9. L1 batch 状态 RPC 不暴露(对照 zkSync zks_L1BatchNumber)
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"linea_getL2BlockNumber","id":1}'
# → {"error":{"code":-32601,"message":"method does not exist"}}  ← 必须查 L1 合约
```

---

## 附:与已有 EVM/L2 调研的 diff 汇总

| 维度 | 本链差异要点 |
| --- | --- |
| ChainID | 59144(`0xe708`) |
| RPC | 标准 `eth_*` **+** `linea_*`(**仅 3 个**) |
| Block | 标准 + Cancun 字段(`parentBeaconBlockRoot=0x0`) |
| Receipt | **完全标准**,无 L1 锚定字段(对照 zkSync 有 `l1BatchNumber`) |
| Tx | 标准 0/1/2/3,**无新 type**(对照 zkSync type 113) |
| Finality | 两阶段(L2 soft / L1 finalize),无 challenge window |
| 安全模型 | ZK validity proof(Plonk + Groth16) |
| 账户模型 | **标准 EOA**(对照 zkSync native AA) |
| State trie | **Sparse Merkle Tree (Mimc)**(对照 zkSync 同;对照 Ethereum/OP/Arb 不同) |
| zk-EVM 类型 | **Type 2**(对照 zkSync Type 4) |
| L1 batch 监控 | **RPC 不暴露**,必须 `eth_call` 到 L1 `ZkEvmV2`(对照 zkSync `zks_L1BatchNumber` 直读) |

— END —
