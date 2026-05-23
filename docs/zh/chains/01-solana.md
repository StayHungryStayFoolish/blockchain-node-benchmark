# 01-solana 调研

> 第一份调研,用作 28 链调研模板示范。**真实证据严格遵守 H8**。

---

## 元信息

| 项 | 值 |
|---|---|
| 链名(中) | Solana |
| 链名(英) | Solana |
| 编号 | 01 |
| Mainnet ChainID | `mainnet-beta`(无数字 chain_id,用网络名标识) |
| Genesis Hash | `5eykt4UsFv8P8NJdTREpY1vzqKqZKvdpKuc147dw2N9d` |
| 调研日期 | 2026-05-23 |
| 调研者 | Hermes Agent |
| 状态 | 🟢 已完成 |

---

## 1. Sources(权威来源)

| 类型 | URL | 访问日期 | 备注 |
|---|---|---|---|
| 官方文档 | https://solana.com/docs | 2026-05-23 | 协议规范主页 |
| RPC 规范 | https://solana.com/docs/rpc | 2026-05-23 | JSON-RPC HTTP/WS 接口完整文档 |
| RPC 方法详表 | https://solana.com/docs/rpc/http | 2026-05-23 | 全部 HTTP method 列表 |
| GitHub(Agave 客户端) | https://github.com/anza-xyz/agave | 2026-05-23 | 主流验证器节点客户端(Solana Foundation fork) |
| GitHub(原 solana) | https://github.com/solana-labs/solana | 2026-05-23 | 历史仓库,已 archive |
| Explorer | https://explorer.solana.com | 2026-05-23 | 区块/账户/tx 浏览器 |
| Solscan | https://solscan.io | 2026-05-23 | 备用 explorer,搜索 token 信息更友好 |

---

## 2. Protocol Family(协议族)

| 项 | 值 |
|---|---|
| Family | **Solana**(独立族,不与 EVM/Bitcoin/Move 共用) |
| Consensus | **PoH(Proof of History) + TowerBFT(基于 PoS 的 BFT)** |
| VM | **SVM**(Sealevel,并行执行 BPF/sBPF 字节码) |
| Block Time | ~400ms(目标 slot 时间) |
| Finality | 32 slots(~12.8s)进入 finalized 状态 |
| Reuse Existing Adapter? | **No,使用 SolanaAdapter**(本族唯一) |

---

## 3. Public RPC(公共节点)

| Endpoint | Auth | Rate Limit | 备注 |
|---|---|---|---|
| `https://api.mainnet-beta.solana.com` | 无 | 官方未公布精确数,推测 < 10 req/s | Solana Foundation 官方公共节点,**生产不适合,仅供调研 / mock 替代** |
| `https://api.devnet.solana.com` | 无 | 同上 | Devnet |
| `https://api.testnet.solana.com` | 无 | 同上 | Testnet |
| `https://solana-rpc.publicnode.com` | 无 | 中等 | Allnodes 公益节点 |

**信源覆盖**:

| Method | 信源数 | 说明 |
|---|---|---|
| `getRecentBlockhash` | **2 源(dual-source)** | mainnet-beta + publicnode 均返 `-32601`,废弃事实可信 |
| 其余 7 个 method | **1 源(single-source)** | 仅 mainnet-beta,数值类(slot/blockHeight/balance)有时效性 |

> ⚠️ AP3 提醒:single-source 实测不足以判定全行业行为。Phase 1.2 起若发现关键 method 跨节点行为差异,需补 publicnode 等 dual-source 复验。

**curl 实测**(2026-05-23 ~02:14 UTC 真实执行,数值字段有时效性,**重测会变**):

```bash
# getSlot — 当前 slot
$ curl -s -X POST https://api.mainnet-beta.solana.com \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"getSlot"}'
{"jsonrpc":"2.0","result":421541028,"id":1}

# getBlockHeight — 当前块高
$ curl -s -X POST https://api.mainnet-beta.solana.com \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"getBlockHeight"}'
{"jsonrpc":"2.0","result":399629216,"id":1}

# getBalance — WSOL 包装地址余额
$ curl -s -X POST https://api.mainnet-beta.solana.com \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"getBalance","params":["So11111111111111111111111111111111111111112"]}'
{"jsonrpc":"2.0","result":{"context":{"apiVersion":"4.0.0","slot":421541035},"value":1512828393160},"id":1}
# 解读:1512.828393160 SOL(lamports/1e9)

# getVersion
$ curl -s ... -d '{"method":"getVersion"}'
{"jsonrpc":"2.0","result":{"feature-set":3718597879,"solana-core":"4.0.0"},"id":1}

# getHealth — 探活
$ curl -s ... -d '{"method":"getHealth"}'
{"jsonrpc":"2.0","result":"ok","id":1}

# getSignaturesForAddress — 真实签名查询(本框架核心 method)
$ curl -s ... -d '{"method":"getSignaturesForAddress","params":["So11111111111111111111111111111111111111112",{"limit":2}]}'
{"jsonrpc":"2.0","result":[
  {"blockTime":1779501907,"confirmationStatus":"finalized","signature":"2JenZjSJhZiVrAqBsJKQjyVt6pcjfHgdpcFNguqNURAJHLuas5Ezx519fYrLvxgBxs92TjUoaieMa1JmnfCVKsRb","slot":421541075,"transactionIndex":1081,...},
  {"blockTime":1779501907,"confirmationStatus":"finalized","signature":"2WhoAaN2DZaF52R8xkWE3Uk14rxpUqPTYnnQjbpGmYSTk8Tm3bpwxfYHEpCmqGRbGX29z5RnSdYpaxWU8zJz3vBG","slot":421541075,...}
],"id":1}
```

---

## 4. Account Model(账户模型)

| 项 | 值 |
|---|---|
| 模型 | **Account 模型**(非 UTXO),所有数据存在 Account 中 |
| Native token decimals | **9**(1 SOL = 1,000,000,000 lamports) |
| Address derivation | **Ed25519** 公钥(32 字节) |
| Special account types | **PDA**(Program Derived Address,无私钥)、**SPL Token Account**(由 Token Program 派生)、**Program Account**(部署的合约) |
| 系统账户(本框架配置中) | `11111111111111111111111111111111`(System Program)<br>`TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA`(SPL Token Program)<br>`ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL`(Associated Token Program)<br>`metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s`(Metaplex Token Metadata)<br>`SysvarRent111111111111111111111111111111111`(Sysvar Rent)<br>`ComputeBudget111111111111111111111111111111`(Compute Budget Program) |

**当前 config 中的 target_address**:`EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`(USDC mint account,Solana 上最活跃账户之一,日交易量极大)

---

## 5. Core RPC Methods(本框架监控所需)

| Method | 类别 | 说明 | mixed 权重(建议) | 本框架现状 |
|---|---|---|---|---|
| `getSlot` | block height | 当前 slot 数 | 0.05 | ❌ 未启用(应加) |
| `getBlockHeight` | block height | 当前 finalized 块高 | 0.05 | ✅ 在 mixed |
| `getHealth` | health | 节点健康探活 | 0.05 | ❌ 未启用 |
| `getBalance` | balance | 账户原生 SOL 余额 | 0.20 | ✅ 在 mixed |
| `getAccountInfo` | account | 账户完整信息(data/owner/lamports) | 0.20 | ✅ 在 mixed(single+mixed) |
| `getTokenAccountBalance` | token balance | SPL Token 余额 | 0.20 | ✅ 在 mixed |
| `getSignaturesForAddress` | sig list | 地址的签名列表(本 adapter `_single_request` 核心) | 0.05 | ✅ 在 `methods.get_signatures` |
| `getTransaction` | tx detail | 单笔交易详情 | 0.10 | ✅ 在 `methods.get_transaction` |
| `getLatestBlockhash` | blockhash | 最新 blockhash(替代废弃的 getRecentBlockhash) | 0.10 | ❌ **当前用废弃的 `getRecentBlockhash`,需改** |

**总权重**:0.05+0.05+0.05+0.20+0.20+0.20+0.05+0.10+0.10 = **1.00** ✅

---

## 6. Address Format(地址格式)

| 项 | 值 |
|---|---|
| 编码 | **Base58**(无 0x 前缀) |
| 长度 | **32-44 字符**(典型 43-44) |
| Checksum | 无独立 checksum(Base58 编码本身有错误检测) |
| 示例(主网真实) | `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`(USDC mint,44 字符) |
| 示例(short address) | `11111111111111111111111111111111`(System Program,32 字符,纯 1) |
| 校验正则 | `^[1-9A-HJ-NP-Za-km-z]{32,44}$` |

---

## 7. Signature Lookup(签名/交易哈希)

| 项 | 值 |
|---|---|
| Hash 格式 | **Base58**(无前缀) |
| 长度 | **87-88 字符**(64 字节 Ed25519 签名 → Base58) |
| 示例(主网真实 tx) | `2JenZjSJhZiVrAqBsJKQjyVt6pcjfHgdpcFNguqNURAJHLuas5Ezx519fYrLvxgBxs92TjUoaieMa1JmnfCVKsRb`(2026-05-23 finalized) |
| 查询 method | `getTransaction(signature, {"encoding":"jsonParsed","maxSupportedTransactionVersion":0})` |
| Explorer URL | `https://explorer.solana.com/tx/<signature>` |

⚠️ **maxSupportedTransactionVersion 必传**:本框架代码已传(`fetch_active_accounts.py:265`),否则 versioned tx(v0)解析报错。

---

## 8. Mixed Set(`mixed` 模式权重)

> **⚠️ 文档内部 schema 警告**:本节(§8)、§5、§10 配置 JSON 各自列了**不同 schema 的权重**。Phase 2.1 实施时必须统一到 §10 的"真 method 名为 key"形式(`config_loader.sh` reader 直接消费),§5/§8 是设计草图,**最终以 §10 为准**。

抽象层 method 分组(供 reader 理解,**不直接被 config_loader 消费**):

```json
{
  "balance_query": 0.20,
  "account_info": 0.20,
  "token_balance": 0.20,
  "block_height": 0.10,
  "blockhash": 0.10,
  "sig_lookup": 0.10,
  "health_and_slot": 0.10
}
```

具体 method 映射:
- `balance_query` → `getBalance`
- `account_info` → `getAccountInfo`
- `token_balance` → `getTokenAccountBalance`
- `block_height` → `getBlockHeight`
- `blockhash` → `getLatestBlockhash`(**不再用 getRecentBlockhash**)
- `sig_lookup` → `getSignaturesForAddress` + `getTransaction`(2 阶段)
- `health_and_slot` → `getHealth` + `getSlot` 轮换

**权重和 = 1.00 ✅**

### Phase 2.1 caller/reader 改造点(必读)

修 `getRecentBlockhash` → `getLatestBlockhash` 时,**所有以下点必须同步改**(token-level Gate 3,避免 caller-blind):

| # | 位置 | 改动 | 原因 |
|---|------|------|------|
| 1 | `config/config_loader.sh:430` mixed 字符串 | 删 `getRecentBlockhash`,加 `getLatestBlockhash` | 直接被 vegeta 消费 |
| 2 | `config/config_loader.sh:436` param_formats | 删 `"getRecentBlockhash": "no_params"`,加 `"getLatestBlockhash": "no_params"` | `generate_rpc_json` 漏字段会退默认,新 method 必须显式列出 |
| 3 | `tools/mock_rpc_server.py:137` `if method == "getRecentBlockhash"` | 加 `getLatestBlockhash` 分支(可保留旧分支返 deprecated error 模拟真实节点) | mock_rpc_server 是 fallback target,不改则 mock 模式跑不通新配置 |
| 4 | `analysis-notes/baseline-current-state.md:193` 链路列表 | 同步移除旧 method | 文档真相对齐,防 v1.4.1 同款 doc-vs-code 偏离 |
| 5 | `analysis-notes/disk-and-network-pipeline-redesign.md:216` | 同步 | 同上 |
| 6 | `analysis-notes/research_notes/02-solana-sui-aptos-rpc-resource.md:33` | 把 `(deprecated)` 标注升级为 `(removed from framework, replaced by getLatestBlockhash)` | 研究笔记反映现实 |

**测试要求**:Phase 2.1 完成后必须跑 `core/master_qps_executor.sh --mixed --duration 30`(或最短 e2e_smoke)抓 vegeta 错误率,**所有请求都应是 200,无 `-32601`**,作为本 bug 修复的 E2 证据。

---

## 9. Mock Notes(mock_rpc_server 实现要点)

- **请求路径**:`POST /`(单一 JSON-RPC endpoint)
- **响应 schema 样本**(真实主网):
  ```json
  {"jsonrpc":"2.0","result":421541028,"id":1}
  {"jsonrpc":"2.0","result":{"context":{"apiVersion":"4.0.0","slot":421541035},"value":1512828393160},"id":1}
  {"jsonrpc":"2.0","error":{"code":-32601,"message":"Method not found"},"id":1}
  ```
- **特殊错误码**:
  - `-32601`:Method not found(如 `getRecentBlockhash`)
  - `-32602`:Invalid params(常见,如签名格式错)
  - `-32603`:Internal error
- **关键 mock 复杂度**:**Medium**
  - 简单 method(getSlot/getBlockHeight/getHealth):返回单一数值/字符串,**Low**
  - getBalance/getAccountInfo:需返回 `context+value` 嵌套结构,**Medium**
  - getSignaturesForAddress:需返回数组(可由 fixture 提供),**Medium**
  - getTransaction:嵌套深(message/accountKeys/instructions),**High** — 建议用 fixture 模式从真实主网 dump 几笔 tx 复用

---

## 10. Adapter Reuse Decision(adapter 复用决策)

### 候选 adapter

| Adapter | 兼容度 | 缺失能力 |
|---|---|---|
| SolanaAdapter | **100%** | — |
| EthereumAdapter | 0% | 账户模型完全不同,无 logs/topics 概念 |
| 其他 | 0% | — |

### 决策

- [x] **复用** `SolanaAdapter`(已有,无需新建)
- [ ] 新建
- [ ] 混合

### 理由

Solana 是其本族的唯一代表(无其他链使用 SVM + PoH)。SolanaAdapter 已在 `tools/fetch_active_accounts.py:248-284` 实现完整(3 个方法:`_single_request` / `fetch_transaction` / `extract_accounts_from_transaction`),本次重构**只需将其迁出到 `adapters/solana.py`**,并补充 `getLatestBlockhash` 替换废弃的 `getRecentBlockhash`。

### 接口契约 placeholder(Phase 2.0 设计稿出来后填)

> ⚠️ 当前未列 `BlockchainAdapter` 基类(`tools/fetch_active_accounts.py:156-245`)对 plugin 的接口契约要求。Phase 2.0 plugin 框架设计阶段需补:
>
> - [ ] 列出 plugin adapter 必须实现的所有方法签名
> - [ ] 列出基类已实现可复用的方法(避免子类重复实现)
> - [ ] 列出 plugin JSON 配置 → adapter 实例化的字段映射
> - [ ] 列出 adapter 测试 fixture 的最低集(每 adapter 至少 N 笔真主网 tx)
>
> Phase 2.0 设计稿完成后回填此节,28 链调研全部复用同一份接口契约。

### 配置 JSON 示例(本链)

```json
{
  "chain": "solana",
  "family": "solana",
  "adapter": "SolanaAdapter",
  "network": "mainnet-beta",
  "rpc_endpoint": "LOCAL_RPC_URL",
  "block_time_ms": 400,
  "finality_slots": 32,
  "address_format": {
    "encoding": "base58",
    "length_min": 32,
    "length_max": 44,
    "regex": "^[1-9A-HJ-NP-Za-km-z]{32,44}$"
  },
  "native_decimals": 9,
  "rpc_methods": {
    "block_height": "getBlockHeight",
    "balance": "getBalance",
    "tx_lookup": "getTransaction",
    "sig_list": "getSignaturesForAddress",
    "token_balance": "getTokenAccountBalance",
    "account_info": "getAccountInfo",
    "blockhash": "getLatestBlockhash",
    "health": "getHealth",
    "slot": "getSlot"
  },
  "param_formats": {
    "getAccountInfo": "single_address",
    "getBalance": "single_address",
    "getTokenAccountBalance": "single_address",
    "getLatestBlockhash": "no_params",
    "getBlockHeight": "no_params",
    "getHealth": "no_params",
    "getSlot": "no_params"
  },
  "mixed_weights": {
    "getBalance": 0.20,
    "getAccountInfo": 0.20,
    "getTokenAccountBalance": 0.20,
    "getBlockHeight": 0.10,
    "getLatestBlockhash": 0.10,
    "getSignaturesForAddress": 0.05,
    "getTransaction": 0.05,
    "getHealth": 0.05,
    "getSlot": 0.05
  },
  "system_addresses": [
    "11111111111111111111111111111111",
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",
    "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s",
    "SysvarRent111111111111111111111111111111111",
    "ComputeBudget111111111111111111111111111111"
  ],
  "default_target_address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
  "tx_lookup_params": {
    "encoding": "jsonParsed",
    "maxSupportedTransactionVersion": 0
  }
}
```

---

## Open Questions(待解决问题)

- [x] ⚠️ **`getRecentBlockhash` 已被官方废弃**(实测返回 `-32601 Method not found`),双源验证(`api.mainnet-beta.solana.com` + `solana-rpc.publicnode.com` 均返同样错误)。
  - **此 method 废弃事实早有记录**:`analysis-notes/research_notes/02-solana-sui-aptos-rpc-resource.md:33` 已标注 `getRecentBlockhash (deprecated) | Memory | <1ms | 已被 getLatestBlockhash 替代`。
  - **但** `config/config_loader.sh:430` 的 mixed 列表仍含此 method 未清理,`config_loader.sh:436` 的 `param_formats` 也仍保留对应条目。
  - **调用链已验**:`config_loader.sh:430` → `target_generator.sh:184/300-306`(读 `CURRENT_RPC_METHODS_ARRAY` 循环每 account × method)→ `generate_rpc_json` → vegeta targets file → vegeta 真发 mainnet。
  - **失败率估算(E5 SPECULATED,未实测)**:mixed 模式 5 method 等权 → **理论上 ~20% 请求**会返 `-32601`。**未跑 vegeta 实测**,真实失败率受 vegeta 默认成功判定(HTTP 200 + JSON `error` 字段在 vegeta 默认 200-class 成功)等因素影响,可能与理论值不同。Phase 2.1 验收时必须实测确认。
  - **官方 deprecation 已 E1 查证**(https://solana.com/docs/rpc/deprecated/getrecentblockhash):原文 "*This method is expected to be removed in `solana-core` v2.0. Please use getLatestBlockhash instead.*" 实测 `getVersion` 公共节点已是 `solana-core 4.0.0`(>>v2.0),即移除承诺已生效,公共节点确认返 `-32601`。
  - **本次拆 plugin 时必须同步修复**(no-deferred-bugs):mixed 列表里 `getRecentBlockhash` 换成 `getLatestBlockhash`,`param_formats` 也同步加 `"getLatestBlockhash": "no_params"` 项,旧条目删除。
- [ ] mock_rpc_server 的 `getTransaction` 是否需要复杂的 versioned tx (v0) 处理?当前 SolanaAdapter 已传 `maxSupportedTransactionVersion=0` 参数,mock 也应支持。
- [ ] 是否需要支持 `getProgramAccounts`?当前框架未用,但若交易所要测合约级监控可能要加。

---

## Changelog

| Date | Author | Change |
|---|---|---|
| 2026-05-23 | Hermes Agent | 初次调研,实测 8 个 method,发现 `getRecentBlockhash` 废弃 bug |
| 2026-05-23 | Hermes Agent | Self-audit v1 token-level 自检后修 7 漏点:措辞降级(archive 早记)、§8 加 caller/reader 改造点表、§3 加信源覆盖+时间戳、§10 行号修正(L248-285→L248-284)、§10 加接口契约 placeholder、§8 加 schema 不一致警告 |
