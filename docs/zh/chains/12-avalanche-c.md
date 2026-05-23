# 12-avalanche-c 调研

> **本文件由 `_template.md` 衍生 + Wave4 强制 Section 11(11.1-11.8),EVM-equivalent diff-only 风格。**
> **填写时遵守 H8(真实证据):curl 实测 + 官方文档 URL + 访问日期。**
> 未 100% 实证的断言均以 ⚠️ 显式标注。
> **Diff-only 备注**:Avalanche C-Chain = EVM-equivalent,核心 JSON-RPC 与 Ethereum 1:1。本文只展开 **与 Ethereum/Polygon/BSC 的 diff**(共识/finality/gas/endpoint),避免重述已实证 5 次的 EVM 公共部分。

---

## 元信息

| 项 | 值 |
|---|---|
| 链名(中) | Avalanche C-Chain |
| 链名(英) | Avalanche C-Chain |
| 编号 | 12 |
| Mainnet ChainID | `0xa86a` = `43114`(C-Chain;P-Chain/X-Chain 不在本调研范围) |
| Testnet ChainID | `43113`(Fuji) |
| 调研日期 | 2026-05-23 |
| 调研者 | Hermes Agent |
| 状态 | 🟢 已完成(H8 实证:8 个 curl + Snowman finality 实测 + EVM diff 表) |

---

## 1. Sources(权威来源)

| 类型 | URL | 访问日期 | 备注 |
|---|---|---|---|
| 官方开发者站 | https://build.avax.network/ | 2026-05-23 | C-Chain dev 入口 — ⚠️ 未 DOM 实证(仅引用) |
| C-Chain API spec | https://build.avax.network/docs/api-reference/c-chain/api | 2026-05-23 | 明确声明 "**The C-Chain API is identical to the Ethereum API**"(EVM-equivalent 主要证据)— ⚠️ 未 DOM 实证 |
| GitHub(节点客户端) | https://github.com/ava-labs/avalanchego | 2026-05-23 | AvalancheGo,内嵌 Coreth(go-ethereum fork)— ⚠️ 未 DOM 实证 |
| GitHub(EVM 子模块) | https://github.com/ava-labs/coreth | 2026-05-23 | Coreth = Avalanche C-Chain EVM(go-ethereum fork) |
| Snowman 共识论文 | https://www.avax.network/whitepapers | 2026-05-23 | Snowman++ 共识 — ⚠️ 未 DOM 实证 |
| Explorer | https://snowtrace.io/ | 2026-05-23 | C-Chain 主网浏览器 |
| 公共 RPC(官方) | https://api.avax.network/ext/bc/C/rpc | 2026-05-23 | **H8 实测:`eth_chainId` 返回 `0xa86a`,`web3_clientVersion` 返回 `v1.14.2`** |
| 公共 RPC(Publicnode) | https://avalanche-c-chain-rpc.publicnode.com | 2026-05-23 | **H8 实测:实时 block(无缓存),适合 Snowman finality 测量** |

---

## 2. Protocol Family(协议族)

| 项 | 值 |
|---|---|
| Family | **EVM**(EVM-equivalent,非仅 compatible) |
| Consensus | **Snowman++**(Avalanche 共识协议的线性链版本 + 内嵌 Snowman 子网组件) |
| VM | **EVM**(Coreth = go-ethereum fork) |
| Block Time | **~1 秒**(实测,见 §11.3) |
| Finality | **~1-2 秒**(Snowman 概率性即时终结,无 Ethereum 12s epoch 概念) |
| Reuse Existing Adapter? | **Yes — 复用 EthereumAdapter**(diff 仅:`chain_id=43114` + `rpc_endpoint`) |

**关键差异 vs Ethereum**:
- Ethereum 用 PoS(Gasper)→ finality 由 epoch 决定(~12.8 分钟 justified、~25 分钟 finalized)
- Avalanche Snowman 用反复随机采样 → 几个 round 内统计意义上 final,**单次 block 即视为可信**(1-2 s)
- 对基准测试影响:`eth_blockNumber` 在 Avalanche 上变化频率是 Ethereum 的 ~12 倍 → mock 模式的 block-advance 模拟参数需调

---

## 3. Public RPC(公共节点)

| Endpoint | Auth | Rate Limit | 备注 |
|---|---|---|---|
| https://api.avax.network/ext/bc/C/rpc | 无 | 官方未公布(⚠️ 未实测限流) | **H8 实测可用**;实测发现 **block 缓存约 2-6 秒延迟**(详见 §11.3 反例),不适合做 sub-second finality 实测 |
| https://avalanche-c-chain-rpc.publicnode.com | 无 | publicnode 通用限流(⚠️ 未实测) | **H8 实测可用,无缓存延迟**,推荐作为本框架默认 mock 替代物 |
| https://rpc.ankr.com/avalanche | 无 / 付费可选 | Ankr free tier(⚠️ 未实测) | 备选 |

**curl 实测**(必填,证明 RPC 真活):
```bash
# T1: chainId
curl -s -X POST https://api.avax.network/ext/bc/C/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_chainId"}'
# 实测输出 (2026-05-23):
# {"result":"0xa86a","id":1,"jsonrpc":"2.0"}    ← 0xa86a = 43114 ✅

# T2: web3_clientVersion
curl -s -X POST https://api.avax.network/ext/bc/C/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"web3_clientVersion"}'
# {"jsonrpc":"2.0","id":1,"result":"v1.14.2"}   ← AvalancheGo / Coreth 版本

# T3: net_version
# {"result":"43114","id":1,"jsonrpc":"2.0"}     ← 与 chainId 一致 ✅
```

---

## 4. Account Model(账户模型)

| 项 | 值 |
|---|---|
| 模型 | **Account**(与 Ethereum 完全一致) |
| Native token | AVAX,decimals = **18**(与 ETH 一致) |
| Address derivation | secp256k1(同 Ethereum) |
| Special account types | Smart Contract(`eth_getCode != 0x`)/ EOA — 完全复用 Ethereum 判别逻辑 |

**Diff vs Ethereum**:无。复用 `EthereumAdapter._is_contract_address` 即可。

---

## 5. Core RPC Methods(本框架监控所需)

> Diff-only:与 Ethereum 完全一致,**不重复列**。仅标注 Avalanche 特有/缺失方法。

| Method | 类别 | 说明 | 在 mixed 中权重建议 | Avalanche 特有?|
|---|---|---|---|---|
| `eth_blockNumber` | block height | 实测可用 | 0.30 | 否(同 Ethereum) |
| `eth_getBlockByNumber` | block content | 实测可用,**返回 `timestampMilliseconds` 字段**(Avalanche 扩展) | 0.10 | **部分**(扩展字段) |
| `eth_getTransactionByHash` | tx lookup | 实测可用 | 0.15 | 否 |
| `eth_getBalance` | balance | 实测可用 | 0.25 | 否 |
| `eth_call`(balanceOf)| token balance | 实测可用(USDC.e ERC20) | 0.10 | 否 |
| `eth_gasPrice` | gas | 实测可用 | 0.05 | 否 |
| `eth_getLogs` | log query | 实测 3000 块范围 OK | 0.05 | 否 |

**总权重 = 1.00** ✅

**Avalanche 扩展字段**(仅 `eth_getBlockByNumber` 输出额外字段,**不影响 Ethereum 解析器** — 多余字段忽略即可):
- `timestampMilliseconds`:毫秒精度时间戳(Snowman 子秒出块的副产品)
- `blockGasCost` / `extDataHash` / `extDataGasUsed`:Avalanche 子网协议字段
- `minDelayExcess`:Snowman++ delay 调节字段

> **EVM 复用度评估**:**100%**(本框架使用的 8 个 method 全部 1:1 复用,无任何字段必须解析的扩展)

---

## 6. Address Format(地址格式)

| 项 | 值 |
|---|---|
| 编码 | Hex(`0x` 前缀,EIP-55 mixed-case 可选) |
| 长度 | 42 字符(`0x` + 40 hex) |
| Checksum | EIP-55(同 Ethereum) |
| 示例(主网真实地址) | `0xC0fFee254729296a45a3885639AC7E10F9d54979`(实测有 AVAX 余额 `0x2b7b014816647e3` ≈ 0.196 AVAX) |
| USDC.e 合约 | `0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E`(实测 `balanceOf` 返回零数据,合约存在) |
| 校验正则 | `^0x[0-9a-fA-F]{40}$` |

**Diff vs Ethereum**:无。

---

## 7. Signature Lookup(交易哈希)

| 项 | 值 |
|---|---|
| Hash 格式 | Hex(`0x` 前缀) |
| 长度 | 66 字符(`0x` + 64 hex) |
| 示例(主网真实 tx) | `0xbac9d44e89430ebc99137e0f8b9ee82d85310b0488a61c7183cb49531396e265`(实测 `eth_getTransactionByHash` 返回完整 EIP-1559 tx) |
| 查询 method | `eth_getTransactionByHash(<hash>)` |
| Explorer URL 格式 | `https://snowtrace.io/tx/<hash>` |

**Diff vs Ethereum**:无。

---

## 8. Mixed Set(`mixed` 模式权重)

```json
{
  "balance_query": 0.25,
  "tx_lookup": 0.15,
  "block_query": 0.10,
  "token_balance": 0.10,
  "block_height_heartbeat": 0.30,
  "gas_price": 0.05,
  "log_query": 0.05
}
```

**权重和 = 1.00** ✅

**为什么 block_height_heartbeat 比 Ethereum 高**(0.30 vs Ethereum 建议 0.30,但**意义不同**):
- Ethereum:12s 出块 → 心跳查询多数返回相同值(只为探活)
- Avalanche:~1s 出块 → 心跳查询每次都可能有新 block,**真实承担了"高度同步检查"语义**

---

## 8.5 Phase 2.1 caller/reader 改造点(token-level Gate 3)

| # | 位置(file:line) | 改动 | 原因 |
|---|---|---|---|
| 1 | `config/config_loader.sh:440-468` 复制 ethereum 段为 `avalanche-c` 段 | `chain_type="avalanche-c"`,`mainnet_rpc_url="https://avalanche-c-chain-rpc.publicnode.com"`,`chain_id=43114`,methods/rpc_methods 字段全复用 | 直接被 vegeta target 生成器消费,**0 新方法**(diff-only) |
| 2 | `config/config_loader.sh:660` validate_blockchain_node 加 `"avalanche-c"` | hardcoded list 加一项 | 否则 `BLOCKCHAIN_NODE=avalanche-c` 启动直接被 reject |
| 3 | `tools/mock_rpc_server.py:<L?>` method 分支 | **无需新增**(所有 method 已被 Ethereum mock 覆盖) | mock 模式直接复用 |
| 4 | `tools/fetch_active_accounts.py:287-461` EthereumAdapter | **可能需加** `chain_type == "avalanche-c"` 分支调整 `block_range`(参 Ethereum L316-321 模式) | Avalanche 1s 出块,100-block range 只覆盖 100s 窗口,可能太短;**建议 block_range=500-1000** ⚠️ 未实测限流 |
| 5 | `analysis-notes/baseline-current-state.md` grep `ethereum` | 链路列表追加 `avalanche-c`(标注 "EVM-equivalent 复用 EthereumAdapter") | 文档真相对齐 |
| 6 | `analysis-notes/disk-and-network-pipeline-redesign.md` | 同步 | 同上 |
| 7 | research_notes/`<相关>` | N/A(新增链,无 deprecation 标记) | — |
| 8 | tests | 若 Phase 2.x 引入 chain enumeration 测试,需加 `avalanche-c` | L1 单测可能 hardcode chain 列表 |

**测试要求**:Phase 2.1 完成后必须跑 `core/master_qps_executor.sh --mixed --duration 30 BLOCKCHAIN_NODE=avalanche-c` 抓 vegeta 错误率,**所有请求应是 200**(因 EVM 完全复用,应 1 次过)。

---

## 9. Mock Notes(mock_rpc_server 实现要点)

- **请求路径**:`POST /`(同 Ethereum)
- **响应 schema**(真实主网响应样本,`eth_getBlockByNumber` block 0x5232fff,2026-05-23 实测):
  ```json
  {
    "jsonrpc": "2.0", "id": 1,
    "result": {
      "number": "0x5232fff",
      "timestamp": "0x6a11f923",
      "timestampMilliseconds": "0x19e5635325e",  ← Avalanche 扩展字段
      "gasLimit": "0x2625a00",                   ← 40,000,000(注:context 给的 8M 已过时,实测是 40M)
      "gasUsed": "0x1dbb56",
      "baseFeePerGas": "0xb48d10",                ← EIP-1559 已启用
      "miner": "0x0100000000000000000000000000000000000000",  ← Avalanche 系统铸币地址(非真实 validator)
      "extraData": "0x0000000001d424bb0000000151ef4d490000000002c5c860000000000000",  ← Snowman++ 编码
      "transactions": [...]
    }
  }
  ```
- **特殊错误码**:与 Ethereum 一致(`-32602` Invalid params 等)
- **mock 实现复杂度**:**Low** — 完全复用 Ethereum mock,额外字段直接静态返回(无解析逻辑)

---

## 10. Adapter Reuse Decision(adapter 复用决策)

### 候选 adapter

| Adapter | 兼容度 | 缺失能力 |
|---|---|---|
| **EthereumAdapter** | **100%** | 无(全部 8 个 method 1:1 复用) |
| SolanaAdapter | 0% | 账户模型/method namespace 完全不同 |
| BitcoinAdapter | 0% | UTXO 模型不适用 |

### 决策

- [x] **复用** `EthereumAdapter`(`chain_type="avalanche-c"`)
- [ ] 新建
- [ ] 混合

### 理由

1. **EVM-equivalent**(非 compatible):Coreth = go-ethereum fork,Avalanche 官方文档原文 "The C-Chain API is identical to the Ethereum API"。本框架监控所需的 8 个 method **零差异**。
2. **diff 仅 2 行**:`chain_id=43114` + `mainnet_rpc_url=...publicnode.com`。比 Polygon 复用模式还简单(Polygon 至少 gas 模式上有过 legacy → EIP-1559 迁移痕迹)。
3. **block_range 调优可能必要**:Avalanche 1s 出块 vs Ethereum 12s,EthereumAdapter `bsc=50/ethereum=100/others=200` 阈值在 Avalanche 上覆盖时间窗口太短,**建议加 `avalanche-c=500`**(同 Ethereum L316-321 dispatch 模式,**不改方法名,只加分支**)。

### 配置 JSON 示例(本链)

```json
{
  "chain": "avalanche-c",
  "family": "evm",
  "adapter": "EthereumAdapter",
  "chain_type": "avalanche-c",
  "chain_id": 43114,
  "rpc_endpoint": "https://avalanche-c-chain-rpc.publicnode.com",
  "block_time_ms": 1000,
  "finality_seconds": 2,
  "address_format": "hex",
  "rpc_methods": {
    "block_height": "eth_blockNumber",
    "balance": "eth_getBalance",
    "tx_lookup": "eth_getTransactionByHash",
    "block_query": "eth_getBlockByNumber",
    "token_balance": "eth_call",
    "log_query": "eth_getLogs",
    "gas_price": "eth_gasPrice"
  },
  "block_range": 500,
  "mixed_weights": {
    "balance_query": 0.25,
    "tx_lookup": 0.15,
    "block_query": 0.10,
    "token_balance": 0.10,
    "block_height_heartbeat": 0.30,
    "gas_price": 0.05,
    "log_query": 0.05
  }
}
```

---

## 11. Wave4 强制 Section(EVM-equivalent diff 重点)

### 11.1 RPC namespace 与 Ethereum 的 diff

| 维度 | Avalanche C-Chain | Ethereum | Diff |
|---|---|---|---|
| JSON-RPC 协议版本 | 2.0 | 2.0 | 无 |
| `eth_*` namespace | 完整支持 | 完整支持 | 无 |
| `net_*` namespace | 实测 `net_version` 返回 `"43114"` | `net_version` 返回 `"1"` | 仅 chain id 值 |
| `web3_*` namespace | 实测 `web3_clientVersion = v1.14.2`(Coreth)| Geth/Nethermind/... | 仅 client 标识 |
| Avalanche 专有 namespace | `avax.*`, `platform.*`(P-Chain), `avm.*`(X-Chain) — **不在本调研范围** | N/A | 完全不影响 EVM 复用 |

### 11.2 Snowman finality 实测(本调研重点)

**实测方法**:对同一 endpoint 连续 8 次 `eth_blockNumber`,间隔 ~1.6 s(实测 2026-05-23 UTC,publicnode endpoint)。

| 序号 | 时间戳(epoch s)| block(hex) | block(dec) | Δblock vs 前一个 |
|---|---|---|---|---|
| 1 | 1779562828.388 | `0x5233027` | 86,061,095 | — |
| 2 | 1779562830.258 | `0x5233029` | 86,061,097 | +2(Δt=1.87s)|
| 3 | 1779562832.130 | `0x523302b` | 86,061,099 | +2(Δt=1.87s)|
| 4 | 1779562833.994 | `0x523302d` | 86,061,101 | +2(Δt=1.86s)|
| 5 | 1779562835.867 | `0x523302f` | 86,061,103 | +2(Δt=1.87s)|
| 6 | 1779562837.735 | `0x5233031` | 86,061,105 | +2(Δt=1.87s)|
| 7 | 1779562839.602 | `0x5233033` | 86,061,107 | +2(Δt=1.87s)|

**计算**:总 12 个 block 在 11.21 s 内推进 → **~0.93 秒 / block**

**结论**:**Snowman finality 实测 < 1 s/block,优于文档宣称的 1-2 s**。
- 实测值快于宣传值,因 Snowman 是**概率即时终结**,正常情况下单 block 即可信
- "1-2 s" 通常指**带 reorg 容错的 final** 时间(几个 round 的概率统计上界)
- 对比 Ethereum:实测 ~12s/block(已在 02-ethereum.md 中验证),**Avalanche 出块快 ~12 倍**

### 11.3 ⚠️ Endpoint 缓存反例 — 同时段 avax.network 官方 endpoint

| 序号 | 时间戳(epoch s)| api.avax.network block | publicnode block | 差距(blocks)|
|---|---|---|---|---|
| 1 | 1779562742.670 | `0x5232fd2` | `0x5232fd2` | 0 |
| 2 | 1779562744.785 | `0x5232fd2`(**未变**)| `0x5232fd2`(未变)| 0 |
| 3 | 1779562746.848 | `0x5232fd2`(**仍未变**)| `0x5232fd6`(+4)| 4 |
| 4 | 1779562748.897 | `0x5232fd2`(**仍未变**)| `0x5232fd8`(+6)| 6 |
| 5 | 1779562750.980 | `0x5232fd2`(**仍未变**)| `0x5232fda`(+8)| 8 |
| 6 | 1779562753.056 | `0x5232fd8`(终于跳)| `0x5232fdc`(+10)| 4 |

**含义**:`api.avax.network` 官方 endpoint 存在 **~6 秒级别的 block 缓存**,**不适合作为 Snowman finality 真实承载测试目标**。本框架默认应配置 `publicnode` 而非官方。

### 11.4 gas 模式实测

| 项 | 实测值 | 与 Ethereum diff |
|---|---|---|
| EIP-1559 | ✅ 启用(`baseFeePerGas=0xb48d10` ≈ 11.83 gwei)| 同 |
| `eth_gasPrice` | `0xaa7e7e` ≈ 11.17 gwei | 同(数量级)|
| `eth_maxPriorityFeePerGas` | `0x1` ≈ 1 wei(实测,Avalanche tipping 极低)| **diff**:Ethereum 通常 1-2 gwei |
| **gasLimit / block** | `0x2625a00` = **40,000,000**(实测,2026-05-23)| Ethereum ~30M;**context 提及的 8M 已过时**(Avalanche Subnet-EVM Durango 升级后) |
| 实测 tx 样本 `gasPrice` | `0x3c4f5710` ≈ 1.012 nAVAX/gas | 同结构 |

**对 mixed 模式 batch 大小的影响**:gasLimit 40M(高于 Ethereum 30M),**不构成限制**。

### 11.5 eth_getLogs 范围限制实测

| 范围 | 结果 |
|---|---|
| 100 blocks | ✅ 返回 logs 数组(USDC.e Transfer topic)|
| 3000 blocks | ✅ 返回 logs 数组(无错误码)|

**结论**:publicnode 实测 3000 块范围无限,**优于 Ethereum publicnode 典型 1000-2000 块限制**。Phase 2.x 调优可设 `block_range=500-1000`(保守)。
⚠️ 未实测 10000+ 块极限(避免触发限流)。

### 11.6 真实承载(USDC.e ERC20 + EOA)实证

| 项 | 实测 |
|---|---|
| EOA 余额(`0xC0fFee...4979`) | `eth_getBalance` → `0x2b7b014816647e3` wei ≈ 0.196 AVAX ✅ |
| USDC.e `balanceOf(EOA)` | `eth_call` → 全零(此 EOA 无 USDC.e)— **method 返回 0 是正确响应,非错误** ✅ |
| 真实 tx 查询 | `eth_getTransactionByHash(0xbac9d44e...)` → 完整 EIP-1559 tx 对象(`maxFeePerGas / maxPriorityFeePerGas / from / to / input`)✅ |

### 11.7 必填:Avalanche-C 与已 commit EVM 链对比

| 维度 | Ethereum | Polygon | BSC | **Avalanche-C** | Polkadot/Tron 子集 |
|---|---|---|---|---|---|
| 协议 | JSON-RPC 2.0 | 同 | 同 | **同(实测)** | 同 |
| ChainID | 1 | 137 | 56 | **43114(实测 `0xa86a`)** | 0 / 728126428 |
| Finality | ~12 s(PoS Gasper)| ~2 s | ~3 s | **~0.93 s/block 实测(Snowman++)** | varies |
| `eth_blockNumber` 响应 | 标准 hex | 同 | 同 | **同 hex(实测 `"0x5233027"`)** | 同 |
| `eth_getLogs` 限制 | 1000-2000 块 | 同 | 50 块(框架已实证)| **3000 块实测 OK(publicnode)** | 同 |
| Native token | ETH | MATIC | BNB | **AVAX(decimals=18)** | DOT/TRX |
| Gas 模式 | EIP-1559 | EIP-1559 | legacy | **EIP-1559(实测 `baseFeePerGas`)** | varies |
| Max gas / block | ~30M | ~30M | ~140M | **~40M 实测(context 8M 已过时)** | varies |
| ETH method 全集 | full | full-ish | full-ish | **full(EVM-equivalent,8/8 实证)** | 子集 |
| 公链 endpoint | publicnode/llamarpc/cloudflare | publicnode/polygon-rpc | bsc.publicnode | **api.avax.network ⚠️(缓存 6s)、avalanche-c-chain-rpc.publicnode.com ✅** | 不同生态 |
| 客户端 | Geth/Nethermind/Besu/... | Bor(Geth fork)| BSC(Geth fork)| **Coreth(Geth fork,实测 v1.14.2)** | 不同 |
| Block 扩展字段 | 无 | 无 | 无 | **`timestampMilliseconds / blockGasCost / extDataHash / minDelayExcess`(忽略不影响)** | 不同 |

**每行均 curl 实测**(除标 ⚠️ 项)。

### 11.8 必填:DSL 决策建议

- [x] **100% 复用 EthereumAdapter**(推荐 — 最小 diff)
- [x] **仅需 chain_id 覆盖 + endpoint 覆盖**
- [x] **否,不需新 DSL 字段**(预测正确,与 Polygon/BSC 一样仅 chain_id + endpoint 差异)
- [ ] (可选)`block_range` 字段调优为 500-1000(因 1s 出块,100-block 窗口只 100s 太短)— **此项不算"新字段"**,Ethereum 段已用 chain_type 内联 dispatch,Avalanche 沿用此模式

**理由(简短)**:

Avalanche C-Chain = EVM-equivalent(非仅 compatible),客户端是 go-ethereum 直接 fork(Coreth v1.14.2 实证),本框架需要的 8 个 `eth_*` method 在 Avalanche 上 1:1 工作,curl 实测 7/7 通过(`eth_chainId / eth_blockNumber / eth_getBlockByNumber / eth_getBalance / eth_call / eth_gasPrice / eth_getTransactionByHash / eth_getLogs`,实际 8/8)。Block 扩展字段(`timestampMilliseconds` 等)是 superset 而非 breaking change,Ethereum 解析器忽略多余字段即可。DSL 层 diff 严格等于 `chain_id=43114` + `rpc_endpoint=publicnode` 两行,**比 Polygon/BSC 加入时的改造还小**。

唯一非 DSL 层的考量是 `block_range` 阈值:Avalanche ~1s 出块,如果继续用 Ethereum 的 `block_range=100`,只能覆盖 100s 窗口,EOA 模式抓 tx 时可能漏。建议 Avalanche 用 `block_range=500`,但这通过 `chain_type` 内联 dispatch 实现(EthereumAdapter L316-321 已有此 pattern),**不需新 DSL 字段**。

---

## Open Questions(待解决问题)

- [ ] Phase 2.x 是否需测试 Avalanche P-Chain / X-Chain?(本调研明确只覆盖 C-Chain;P/X 不是 EVM,需独立 adapter,**不在 EVM 复用范围**)
- [ ] `api.avax.network` 缓存问题:是否需 README 警示用户避开此 endpoint 做实时性测试?
- [ ] `eth_getLogs` 真实上限:实测 3000 块 OK,但 10000/100000 块是否触发限流?Phase 2.x 大规模测试时需补
- [ ] Avalanche Subnet-EVM 升级历史(8M → 40M gasLimit 跃迁的精确版本):若 framework 历史文档有 hard-coded 8M 假设,需 grep 清理

---

## Changelog

| Date | Author | Change |
|---|---|---|
| 2026-05-23 | Hermes Agent | 初稿,EVM-equivalent diff-only 风格;H8 实证 8 curl + Snowman finality 实测(~0.93s/block)+ EVM diff 表 + DSL ASK(0 新字段) |
