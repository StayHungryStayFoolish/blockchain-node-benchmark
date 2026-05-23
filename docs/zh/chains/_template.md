# <编号>-<链名> 调研

> **此文件由 `_template.md` 衍生,每条链一份。**
> **填写时必须遵守 H8(真实证据):curl 实测 + 官方文档 URL + 访问日期。**

---

## 元信息

| 项 | 值 |
|---|---|
| 链名(中) | <例:Solana> |
| 链名(英) | <例:Solana> |
| 编号 | <01-28> |
| Mainnet ChainID | <例:101 / 1 / 56> |
| 调研日期 | YYYY-MM-DD |
| 调研者 | Hermes Agent |
| 状态 | 🟡 进行中 / 🟢 已完成 / 🔴 阻塞 |

---

## 1. Sources(权威来源)

| 类型 | URL | 访问日期 | 备注 |
|---|---|---|---|
| 官方文档 | https://... | YYYY-MM-DD | 协议规范主页 |
| RPC 规范 | https://... | YYYY-MM-DD | JSON-RPC 或 REST 接口文档 |
| GitHub | https://github.com/... | YYYY-MM-DD | 客户端源码 |
| Explorer | https://... | YYYY-MM-DD | 区块浏览器(查地址/tx 示例) |

---

## 2. Protocol Family(协议族)

| 项 | 值 |
|---|---|
| Family | <Solana / EVM / Bitcoin / Move / Cosmos-SDK / Substrate / Tendermint / 其他> |
| Consensus | <PoH+PoS / PoW / PoS / DPoS / BFT> |
| VM | <SVM / EVM / MoveVM / WASM / None(UTXO)> |
| Block Time | <秒,例:0.4s> |
| Finality | <slot/block,例:32 slots ≈ 12.8s> |
| Reuse Existing Adapter? | <Yes(指明哪个 adapter)/ No(新族,需新 adapter)> |

---

## 3. Public RPC(公共节点)

| Endpoint | Auth | Rate Limit | 备注 |
|---|---|---|---|
| https://... | 无 / API key | <次/秒 或 次/天> | 是否适合 mock 替代物 |
| https://... | 无 / API key | ... | ... |

**curl 实测**(必填,证明 RPC 真活):
```bash
curl -s -X POST https://api.mainnet-beta.solana.com \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"getSlot"}'
# 实测输出:
# {"jsonrpc":"2.0","result":<真实 slot>,"id":1}
```

---

## 4. Account Model(账户模型)

| 项 | 值 |
|---|---|
| 模型 | UTXO / Account / Hybrid |
| Native token decimals | <例:9(lamports)> |
| Address derivation | <Ed25519 / secp256k1 / Sr25519 / 其他> |
| Special account types | <例:PDA(Solana)/ Smart Contract / Native Token Account> |

---

## 5. Core RPC Methods(本框架监控所需)

> 仅列**本基准测试框架**需要的 method。完整 API 列表参考官方文档。

| Method | 类别 | 说明 | 在 mixed 中权重建议 |
|---|---|---|---|
| `getSlot` / `eth_blockNumber` / ... | block height | 探活 + 高度同步检查 | 0.05 |
| `getBlock` / `eth_getBlockByNumber` / ... | block content | 重量级,带 tx 详情 | 0.10 |
| `getTransaction` / `eth_getTransactionByHash` / ... | tx lookup | 签名查询 | 0.20 |
| `getBalance` / `eth_getBalance` / ... | balance | 账户余额 | 0.25 |
| `getTokenAccountBalance` / `eth_call(balanceOf)` / ... | token balance | ERC20/SPL token | 0.20 |
| ... | ... | ... | ... |

**总权重必须 = 1.0**

---

## 6. Address Format(地址格式)

| 项 | 值 |
|---|---|
| 编码 | Base58 / Hex(0x前缀)/ Bech32 / Bech32m / Base32 |
| 长度 | <例:32-44 字符(Base58)/ 42 字符(Hex)> |
| Checksum | 有(算法名)/ 无 |
| 示例(主网真实地址) | `<真实地址,可在 explorer 查到>` |
| 校验正则 | `^[1-9A-HJ-NP-Za-km-z]{32,44}$` |

---

## 7. Signature Lookup(签名/交易哈希)

| 项 | 值 |
|---|---|
| Hash 格式 | Base58 / Hex(0x 前缀) |
| 长度 | <字符数> |
| 示例(主网真实 tx) | `<真实 tx hash>` |
| 查询 method | `getTransaction(<sig>)` |
| Explorer URL 格式 | `https://.../tx/<hash>` |

---

## 8. Mixed Set(`mixed` 模式权重)

> 用于 `BLOCKCHAIN_NODE_BENCHMARK_MODE=mixed` 时的请求分布

```json
{
  "balance_query": 0.25,
  "tx_lookup": 0.20,
  "block_query": 0.10,
  "token_balance": 0.20,
  "<chain-specific>": 0.25
}
```

**权重和必须 = 1.0**。chain-specific 部分要列具体 method。

---

## 8.5 Phase 2.1 caller/reader 改造点(token-level Gate 3)

**强制要求**:每条链调研必须列出 Phase 2.1 实施时的 caller/reader 改造清单,避免 Phase 2.1 改 plugin 时 caller-blind(参考 `token-level-careful-edit` skill Case-B/D)。

| # | 位置(file:line) | 改动 | 原因(为什么这个 caller 需同步改) |
|---|---|---|---|
| 1 | `config/config_loader.sh:<L?>` 本链 `rpc_methods.mixed` | <列出新增/删除的 method> | 直接被 vegeta target 生成器消费 |
| 2 | `config/config_loader.sh:<L?>` 本链 `param_formats` | <列出新增/删除的 method 对应 param 格式> | `generate_rpc_json` 漏字段会退默认 |
| 3 | `tools/mock_rpc_server.py:<L?>` method 分支 | <列出 mock 需要新增的 case> | mock_rpc_server 是 fallback target,不改则 mock 模式跑不通新配置 |
| 4 | `tools/fetch_active_accounts.py:<L?>` adapter 实现 | <列出 adapter 方法是否需补/改> | 本链 SolanaAdapter / EthereumAdapter / ... 是否要扩 |
| 5 | `analysis-notes/baseline-current-state.md`(grep 本链名) | <同步更新链路列表> | 文档真相对齐,防 v1.4.1 同款 doc-vs-code 偏离 |
| 6 | `analysis-notes/disk-and-network-pipeline-redesign.md`(grep 本链名) | <同步> | 同上 |
| 7 | `analysis-notes/research_notes/<相关本链笔记>.md` | <若有 deprecated 标记升级为 removed/replaced> | 研究笔记反映现实 |
| 8 | `tests/<本链相关测试>.sh` 或 `.py` | <若有 method/字段断言需同步> | L1/L2 单测可能 hardcode 旧 method 名 |

**若本链是新增链(无现有代码)**,#1-3 仍要填(在 plugin JSON + mock 中需新增),#4-8 视情况标 N/A。

**测试要求**:Phase 2.1 完成后必须跑 `core/master_qps_executor.sh --mixed --duration 30`(或最短 e2e_smoke)抓 vegeta 错误率,**所有请求都应是 200**,作为本链改造的 E2 证据。

---

## 9. Mock Notes(mock_rpc_server 实现要点)

- **请求路径**:`<例:POST / 或 POST /jsonrpc>`
- **响应 schema**(必须贴一段真实主网响应做样本):
  ```json
  {"jsonrpc":"2.0","result":<真实数据>,"id":1}
  ```
- **特殊错误码**(如有):
  - `-32602`:Invalid params
  - `<chain-specific>`:...
- **mock 实现复杂度**:Low / Medium / High(列原因)

---

## 10. Adapter Reuse Decision(adapter 复用决策)

### 候选 adapter

| Adapter | 兼容度 | 缺失能力 |
|---|---|---|
| EthereumAdapter | <例:60%> | <例:缺 SPL token 支持> |
| SolanaAdapter | <例:0%> | <账户模型完全不同> |
| BitcoinAdapter | <例:0%> | <UTXO 模型不适用> |

### 决策

- [ ] **复用** `<adapter 名>`(指明)
- [ ] **新建** `<adapter 名>`(说明族)
- [ ] **混合**(说明部分复用 + 部分自实现,例:Tron 双 API)

### 理由

<2-3 段说明>

### 配置 JSON 示例(本链)

```json
{
  "chain": "<chain-name>",
  "family": "<family>",
  "adapter": "<AdapterClass>",
  "chain_id": <id>,
  "rpc_endpoint": "https://...",
  "block_time_ms": <ms>,
  "address_format": "base58 / hex / bech32",
  "rpc_methods": {
    "block_height": "<method>",
    "balance": "<method>",
    "tx_lookup": "<method>"
  },
  "mixed_weights": {
    "balance_query": 0.25,
    "tx_lookup": 0.20,
    "block_query": 0.10,
    "token_balance": 0.20,
    "chain_specific": 0.25
  }
}
```

---

## Open Questions(待解决问题)

- [ ] <例:Avalanche P-Chain 的 X 接口是否支持批量查询?>
- [ ] <例:Tron `/wallet/getaccount` 是否需要 ABI 解码?>

---

## Changelog

| Date | Author | Change |
|---|---|---|
| YYYY-MM-DD | Hermes Agent | 初次调研 |
