# 14-hedera 调研

> 由 `_template.md` 衍生。H8(真实证据):所有 curl 在 **2026-05-23** 对公共 mainnet 端点(Mirror REST `https://mainnet-public.mirrornode.hedera.com` + Hashio JSON-RPC `https://mainnet.hashio.io/api`)实测,共 14 次 API 调用。本调研**不测 gRPC HCS**(需 protobuf,不适合 vegeta benchmark)。

---

## 元信息

| 项 | 值 |
|---|---|
| 链名(中) | 海德拉 / Hedera Hashgraph |
| 链名(英) | Hedera |
| 编号 | 14 |
| Mainnet ChainID | EVM-compat `chainId = 295`(`0x127`,E5 `eth_chainId` 实测;E14 `net_version` 实测 `"295"`);**Hashgraph 原生协议无 chainId 概念**(由 node ID `0.0.3..0.0.40` 集群签名共识) |
| 调研日期 | 2026-05-23 |
| 调研者 | Hermes Agent |
| 状态 | 🟢 已完成 |

---

## 1. Sources(权威来源)

| 类型 | URL | 访问日期 | 备注 |
|---|---|---|---|
| 官方文档主页 | https://docs.hedera.com | 2026-05-23 | Hedera Hashgraph 协议文档总入口 |
| Mirror Node REST API | https://docs.hedera.com/hedera/sdks-and-apis/rest-api | 2026-05-23 | OpenAPI 风格规范,本调研主测协议 |
| JSON-RPC Relay 规范 | https://github.com/hashgraph/hedera-json-rpc-relay | 2026-05-23 | hashgraph 官方维护的 EVM-compat JSON-RPC 包装器 |
| Hashgraph 共识白皮书 | https://hedera.com/hh_whitepaper_v2.1-20200815.pdf | 2026-05-23 | DAG 共识与"非区块链"本质 |
| 节点客户端 GitHub | https://github.com/hashgraph/hedera-services | 2026-05-23 | Java consensus node |
| Mirror Node GitHub | https://github.com/hashgraph/hedera-mirror-node | 2026-05-23 | Mirror REST + GraphQL 实现 |
| Explorer | https://hashscan.io | 2026-05-23 | 主网账户/tx/token 浏览 |
| HTS 标准 | https://docs.hedera.com/hedera/core-concepts/tokens | 2026-05-23 | Hedera Token Service(原生 token,非合约) |

---

## 2. Protocol Family(协议族)

| 项 | 值 |
|---|---|
| Family | **hedera**(独立族,**Hashgraph DAG ≠ blockchain**;3-part account ID;三 API 并存;无现有 adapter 可复用) |
| Consensus | **aBFT Hashgraph**(gossip-about-gossip + virtual voting,asynchronous Byzantine Fault Tolerant;Council 节点 ID 范围 `0.0.3 ~ 0.0.40`) |
| VM | **HTS**(原生)+ **EVM**(Hedera Smart Contract Service,EVM-equivalent,经 JSON-RPC Relay 暴露)|
| Block Time | **~1–2 秒**(E7+E12 实测:block #95421653 timestamp `from=1779562740.189823000 to=1779562741.470178250`,块跨度 ≈ 1.28s;**注:"块"是 Mirror Node 对 record stream 的包装抽象,Hashgraph 本身无 block,见 §11.7) |
| Finality | **3–5 秒**(aBFT,共识达成即不可逆;⚠️ 未本次直接测,凭官方文档常识) |
| Reuse Existing Adapter? | **混合** — EthereumAdapter 可复用 JSON-RPC 侧(~55%),Mirror REST 侧需新建 `HederaMirrorAdapter`(见 §10) |

---

## 3. Public RPC(公共节点)

| Endpoint | Auth | Rate Limit | 备注 |
|---|---|---|---|
| `https://mainnet-public.mirrornode.hedera.com` | 无 | ~100 req/s ⚠️(凭 Hedera 文档常识,本次未打满) | **Mirror REST API 官方公共节点**,本次 E1/E2/E3/E7/E8/E11/E12 全测此端点,均 HTTP 200 |
| `https://mainnet.hashio.io/api` | 无 | ~50 req/s ⚠️(Hashio Swirlds Labs 运营,凭文档) | **JSON-RPC Relay 公共节点**,本次 E4/E5/E6/E9/E10/E13/E14/E15 全测此端点,均 HTTP 200(包含 -32601 / -32602 error 体) |
| `https://mainnet.mirrornode.hedera.com` | 无 | — | **同 mainnet-public**(DNS 别名,文档推荐 -public 后缀) |
| `https://testnet.mirrornode.hedera.com` | — | — | **测试网,不用** |

**curl 实测**(E1 — Mirror REST 探活,网络供应):

```bash
curl -s "https://mainnet-public.mirrornode.hedera.com/api/v1/network/supply"
# 实测输出:
# {"released_supply":"4337349052950644279","timestamp":"1779559275.585402000","total_supply":"5000000000000000000"}
```

**curl 实测**(E4 — JSON-RPC 探活,当前 block 高度):

```bash
curl -s -X POST https://mainnet.hashio.io/api \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_blockNumber","params":[]}'
# 实测输出:
# {"result":"0x5b004d1","jsonrpc":"2.0","id":1}      # block #95,420,113
```

**curl 实测**(E5 — chainId 295 = 0x127 主网):

```bash
curl -s -X POST https://mainnet.hashio.io/api \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}'
# 实测输出: {"result":"0x127","jsonrpc":"2.0","id":1}    # 0x127 = 295
```

---

## 4. Account Model(账户模型)

| 项 | 值 |
|---|---|
| 模型 | **Account**(非 UTXO);**3-part ID** `shard.realm.num`(主网 shard=realm=0,实际全部形如 `0.0.X`) |
| Native token decimals | **8**(1 HBAR = 100,000,000 tinybar,与 BTC sat 同概念) |
| Address derivation | **Ed25519**(主)或 **ECDSA secp256k1**(EVM-compat 账户);可通过 alias 关联 EVM 20-byte 地址 |
| Special account types | **System accounts** `0.0.1`(treasury)/ `0.0.2`(早期测试账户,E2+E3 实测余额 16,630,126.37744658 HBAR)/ `0.0.98`(node fee)/`0.0.800`(staking reward) / `0.0.801`(node reward);**Token accounts**(HTS,每个 token 是独立 entity `0.0.X` — 如 USDC `0.0.456858`);**Contract accounts**(HSCS,EVM-compat 合约也是 `0.0.X`);**Topic accounts**(HCS,共识服务话题)|
| EVM alias 映射 | `0.0.N` long-zero 映射到 EVM 地址 = `0x` + 32 个 0 + 8 位 hex(N 的 padded hex)。E3 实测 0.0.2 → `0x0000000000000000000000000000000000000002` |

---

## 5. Core RPC Methods(本框架监控所需)

> 本框架两套 API 都测;每 method 标 `[Mirror]` 或 `[RPC]`。

| Method | 类别 | 说明 | 在 mixed 中权重建议 |
|---|---|---|---|
| `[Mirror] GET /api/v1/blocks?limit=1&order=desc` | block height | 最新块(record stream 包装);E7 实测返回 `{blocks:[{number:95421653, hash, timestamp{from,to}, ...}]}` | 0.05 |
| `[RPC] eth_blockNumber` | block height | EVM-compat,E4 实测返回 hex `"0x5b004d1"` | 0.05 |
| `[Mirror] GET /api/v1/blocks/{number}` | block content | 单块查询;E12 实测块 #95421653 含 `count`/`hash`/`timestamp.from`/`timestamp.to`/`gas_used`/`logs_bloom` | 0.05 |
| `[RPC] eth_getBlockByNumber("latest", false)` | block content | EVM-compat;E9 实测返回完整 EVM 块结构(填充 `parentHash`/`stateRoot`/`baseFeePerGas`/`withdrawals[]` 等空值占位) | 0.05 |
| `[Mirror] GET /api/v1/transactions/{txId}` | tx lookup | tx ID 形如 `0.0.3229-1779562731-037000118`(account-validStart);E8 实测返回 `transfers[]`/`token_transfers[]`/`nft_transfers[]`/`result` 等完整字段 | 0.10 |
| `[RPC] eth_getTransactionByHash(0x...)` | tx lookup | EVM-compat,需用 EVM hash 形式 ⚠️(本次未直测) | 0.05 |
| `[Mirror] GET /api/v1/accounts/{accountId}` | account 详情 | E3 实测 `0.0.2` 返回 `balance/key/evm_address/alias/auto_renew_period/decline_reward/...` | 0.15 |
| `[Mirror] GET /api/v1/balances?account.id=0.0.X` | balance | 专用余额接口,E2 实测返回 `{timestamp, balances:[{account, balance, tokens:[]}], links{next}}` | 0.15 |
| `[RPC] eth_getBalance("0x0000...0002", "latest")` | balance | EVM-compat,E6 实测返回 hex `"0xdc190f51555e27b8e0800"`(单位 weibar = tinybar × 10^10,**注意单位换算**) | 0.10 |
| `[Mirror] GET /api/v1/tokens/{tokenId}` | HTS token 元数据 | E11 实测 USDC `0.0.456858` 返回 `decimals:"6", name:"USD Coin", memo:"USDC HBAR", supply_key, admin_key, ...` | 0.10 |
| `[RPC] eth_call(balanceOf, USDC HTS via long-zero addr)` | HTS token balance | E15 实测 `to: 0x000000000000000000000000000000000006F89A`(USDC 0.0.456858 long-zero)+ `data: 0x70a08231<padded owner>` 返回 `"0x"`(account 无该 token),**证明 HTS token 可通过 EVM precompile 调用** | 0.10 |
| `[RPC] eth_chainId` | chainId 探活 | E5 实测 `"0x127"` = 295 | 0.05 |

**总权重 = 1.00 ✓**

---

## 6. Address Format(地址格式)

| 项 | 值 |
|---|---|
| 编码 | **3-part dot notation** `shard.realm.num`(原生);可同时表达为 **EVM 20-byte hex**(`0x` 前缀,long-zero 映射或 ECDSA alias) |
| 长度 | 原生:`0.0.<1~10位十进制>`(无固定长度);EVM:42 字符 hex(`0x` + 40) |
| Checksum | **原生有可选 checksum**(格式 `0.0.123-vfmkw`,5 字母后缀,SHA-384 派生);EVM 端无 checksum(可选 EIP-55) |
| 示例(主网真实) | 原生:`0.0.2`(treasury 早期测试账户,E2 实测余额 16630126.37744658 HBAR);`0.0.456858`(USDC HTS token,E11 实测);EVM 映射:`0x0000000000000000000000000000000000000002` |
| 校验正则 | 原生:`^[0-9]+\.[0-9]+\.[0-9]+(-[a-z]{5})?$`;EVM:`^0x[0-9a-fA-F]{40}$` |

**⚠️ DSL 新枚举值**:`address_format = "hedera_3part"`(`shard.realm.num`)是 DSL 全新地址类。详见 §11.8。

---

## 7. Signature Lookup(签名/交易哈希)

| 项 | 值 |
|---|---|
| Hash 格式 | **Mirror 原生**:`transaction_id = <account>-<validStartSeconds>-<validStartNanos>`(E8 实测 `0.0.3229-1779562731-037000118`);**或** `transaction_hash`(base64-encoded 48-byte,E8 实测 `6TiGZaxwgH32ARJwXIlr5M8hd8l8tL0ZSxyUd5FX+MNlmcFPSMbFPMYGC1y8EUPz`)|
| EVM hash 格式 | 32-byte hex `0x...`(JSON-RPC 端,需 ECDSA 签名 tx 才有);**HBAR/HTS 原生 tx 无对应 EVM hash** |
| 长度 | 原生 ID:可变;原生 hash base64:64 字符(48 byte);EVM:66 字符 |
| 示例(主网) | `0.0.3229-1779562731-037000118`(E8 实测 latest CRYPTOTRANSFER) |
| 查询 method | `[Mirror] GET /api/v1/transactions/{transactionId}` 或 `/transactions?transaction.hash=<base64>` |
| Explorer URL 格式 | `https://hashscan.io/mainnet/transaction/<transactionId>` |

---

## 8. Mixed Set(`mixed` 模式权重)

```json
{
  "mirror_account_query":   0.15,
  "mirror_balance_query":   0.15,
  "rpc_balance_query":      0.10,
  "mirror_tx_lookup":       0.10,
  "mirror_token_metadata":  0.10,
  "rpc_hts_balanceOf":      0.10,
  "mirror_block_by_number": 0.05,
  "mirror_block_head":      0.05,
  "rpc_block_by_number":    0.05,
  "rpc_block_height":       0.05,
  "mirror_block_head_rpc_dup": 0.05,
  "rpc_chain_id":           0.05
}
```

**总权重 = 1.00 ✓**(Mirror 0.60 + JSON-RPC 0.40 — Mirror 偏重因其字段完整,真实生产负载占比更高)

---

## 8.5 Phase 2.1 caller/reader 改造点

| # | 位置(file:line) | 改动 | 原因 |
|---|---|---|---|
| 1 | `config/config_loader.sh` 新增 `hedera` 链 block | 新增 12 个 `rpc_methods.mixed` entries(见 §8) | 直接被 vegeta target 生成器消费 |
| 2 | `config/config_loader.sh` 新增 `hedera` `param_formats` | `mirror_path_param` / `mirror_query_param` / `evm_address` / `account_3part` 四种 param 格式 | `generate_rpc_json` 漏字段会退默认导致 vegeta 404 |
| 3 | `tools/mock_rpc_server.py` 新增 hedera 双路径分支 | (a) `do_GET` 新分支:`/api/v1/{accounts,balances,blocks,transactions,tokens,network}/...` 各返回真实主网响应样本(粘自 E1–E12);(b) `do_POST` 走现有 JSON-RPC 分支但需识别 hashio 路径 `/api`,扩 hedera-specific `eth_call` HTS precompile 返回 | mock_rpc_server 是 fallback target,不改 mock 模式 vegeta 全 404/500 |
| 4 | `tools/fetch_active_accounts.py` 新增 `HederaAdapter`(实现 `fetch_active(limit)` 返回 `0.0.X` 列表 + 对应 EVM alias) | 同时输出两套 fixture:`hedera_accounts_3part.txt`(原生格式)+ `hedera_accounts_evm.txt`(0x40hex 长零映射) | 双协议 mixed set 需要两套 param fixture |
| 5 | `analysis-notes/baseline-current-state.md` | 新增 hedera 行(family=hedera, dual-API) | 文档真相对齐 |
| 6 | `analysis-notes/disk-and-network-pipeline-redesign.md` | 同步 hedera 至 14 链列表 | 同上 |
| 7 | `analysis-notes/research_notes/` 若有相关笔记 | 视情况 N/A | — |
| 8 | `tests/` 新增 `tests/hedera_l1_smoke.sh` | E1+E4 双协议 smoke + mock fallback | L1 单测护栏 |

**测试要求**:Phase 2.1 完成后跑 `core/master_qps_executor.sh --chain hedera --mixed --duration 30`,所有请求 HTTP 200,作为 E2 证据。

---

## 9. Mock Notes(mock_rpc_server 实现要点)

- **请求路径**:**双路径**:(a) Mirror REST 形如 `GET /api/v1/<resource>[/<id>][?<query>]`(7+ 种 resource 路径);(b) JSON-RPC 形如 `POST /api` 或 `POST /`(method 走 body)
- **Mirror 响应 schema**(贴一段真实主网 E7 实测样本):
  ```json
  {"blocks":[{"count":3,"hapi_version":"0.73.0","hash":"0xd32933...","name":"2026-05-23T18_59_00.189823000Z.rcd.gz","number":95421653,"previous_hash":"0x4c08...","size":889,"timestamp":{"from":"1779562740.189823000","to":"1779562741.470178250"},"gas_used":0,"logs_bloom":"0x"}],"links":{"next":"/api/v1/blocks?limit=1&order=desc&block.number=lt:95421653"}}
  ```
- **JSON-RPC 响应 schema**(E4 实测):`{"result":"0x5b004d1","jsonrpc":"2.0","id":1}`
- **特殊错误**:
  - Mirror:HTTP 404(资源不存在)、HTTP 400(参数错)
  - JSON-RPC:`-32601`(method not found,E10 实测)、`-32602`(invalid params,E13 实测,**含明确 "Expected 0x prefixed string representing the address (20 bytes)" 信息**)
- **mock 实现复杂度**:**High** — 原因:(1) 双协议双路径需分别 mock;(2) Mirror 7+ 种 resource 路径每条需独立分支;(3) Mirror 响应 schema 嵌套深(`balance.tokens[]`、`transfers[]`、`key._type`);(4) HTS precompile 在 EVM eth_call 的特殊地址范围(long-zero `0x00...00<8hex>`)需正则路由

---

## 10. Adapter Reuse Decision

### 候选 adapter

| Adapter | 兼容度 | 缺失能力 |
|---|---|---|
| EthereumAdapter | ~55%(JSON-RPC 侧) | 缺 Mirror REST、3-part ID、HTS precompile address mapping |
| CosmosAdapter | ~10%(都是 REST 但语义模型完全不同) | Tendermint vs aBFT、bech32 vs 0.0.X、模块路径完全不同 |
| TronHttpAdapter | ~15%(都是 RPC-over-HTTP) | Tron 是 POST + body,Hedera Mirror 是 GET + query/path |

### 决策

- [ ] 复用单一 adapter
- [ ] 新建单一 adapter
- [x] **混合**:**新建 `HederaMirrorAdapter`(Mirror REST 侧)** + **复用 `EthereumAdapter` 子集(JSON-RPC 侧)**;顶层 `HederaAdapter` 按 per-method `protocol` 字段路由

### 理由

(1) **Mirror Node REST 是 GET-driven path + query 风格**(`/api/v1/accounts/0.0.2`、`/api/v1/balances?account.id=0.0.2`),与 Polkadot sidecar 的 GET + path 占位**最接近**(~70% 同构),但路径+query 双占位机制需扩展。无现成 adapter 可 100% 复用,**必须新建** `HederaMirrorAdapter`。

(2) **JSON-RPC Relay 是 EVM-equivalent 包装**,E4/E5/E6/E9/E10/E14/E15 验证 method 名、hex 编码、错误码与 Ethereum 主网一致(`-32601`/`-32602` error schema 完全相同),**可直接复用 EthereumAdapter**,只需配置 `rpc_path = "/api"`(Hashio)+ 接受 long-zero EVM 地址映射规则。

(3) **DSL pattern 与 Polkadot/Tron 高度同构,复用度 ~50%**。Tron wave 3 已扩 `protocol` 枚举至 `{jsonrpc, rest_post_body}`,Hedera 是第 3 条双协议链,**只需再扩** `rest_get_path_query`(GET + path 占位 + query 占位 — Polkadot 是 path 占位但不需要 query)。详见 §11.8。

### 配置 JSON 示例(本链)

```json
{
  "chain": "hedera",
  "family": "hedera",
  "adapter": "HederaAdapter",
  "delegate_adapter_jsonrpc": "EthereumAdapter",
  "chain_id": 295,
  "chain_id_hex": "0x127",
  "node_app": "hedera-services + hedera-mirror-node + hedera-json-rpc-relay",
  "block_time_ms": 1500,
  "finality_seconds": 5,
  "api_protocol": ["mirror_rest", "jsonrpc"],
  "mirror_endpoint": "https://mainnet-public.mirrornode.hedera.com",
  "rpc_endpoint": "https://mainnet.hashio.io/api",
  "address_format": {
    "primary":    {"encoding": "hedera_3part", "regex": "^[0-9]+\\.[0-9]+\\.[0-9]+(-[a-z]{5})?$", "example": "0.0.2"},
    "secondary":  {"encoding": "evm_hex_long_zero", "regex": "^0x0{24}[0-9a-fA-F]{16}$", "example": "0x0000000000000000000000000000000000000002"},
    "ecdsa_alias":{"encoding": "evm_hex", "regex": "^0x[0-9a-fA-F]{40}$"},
    "conversion": "3part num -> 8-byte hex right-aligned in 20-byte zero-padded address"
  },
  "native_token": {"symbol": "HBAR", "decimals": 8, "tinybar_per_hbar": 100000000, "evm_unit": "weibar=tinybar*10^10"},
  "block_semantics": {
    "model": "record_stream_wrapper",
    "note": "Hashgraph 本身无 block;Mirror Node 按 record file 周期(~1s)包装 record stream 成 'block',number 单调递增。Hashgraph 原生概念是 round/event/consensus_timestamp。"
  },
  "rpc_methods": {
    "mirror_block_head":      {"protocol": "mirror_rest", "method": "GET", "path": "/api/v1/blocks",                "query": {"limit": "1", "order": "desc"}},
    "mirror_block_by_number": {"protocol": "mirror_rest", "method": "GET", "path": "/api/v1/blocks/{block_num}"},
    "mirror_account_query":   {"protocol": "mirror_rest", "method": "GET", "path": "/api/v1/accounts/{account_3part}"},
    "mirror_balance_query":   {"protocol": "mirror_rest", "method": "GET", "path": "/api/v1/balances",              "query": {"account.id": "{account_3part}"}},
    "mirror_tx_lookup":       {"protocol": "mirror_rest", "method": "GET", "path": "/api/v1/transactions/{tx_id_3part_dash}"},
    "mirror_token_metadata":  {"protocol": "mirror_rest", "method": "GET", "path": "/api/v1/tokens/{token_3part}"},
    "rpc_block_height":       {"protocol": "jsonrpc",     "method_jsonrpc": "eth_blockNumber",      "params": []},
    "rpc_block_by_number":    {"protocol": "jsonrpc",     "method_jsonrpc": "eth_getBlockByNumber", "params": ["latest", false]},
    "rpc_balance_query":      {"protocol": "jsonrpc",     "method_jsonrpc": "eth_getBalance",       "params": ["{evm_address_long_zero}", "latest"]},
    "rpc_chain_id":           {"protocol": "jsonrpc",     "method_jsonrpc": "eth_chainId",          "params": []},
    "rpc_hts_balanceOf":      {"protocol": "jsonrpc",     "method_jsonrpc": "eth_call",
                               "params": [{"to": "{hts_token_evm_long_zero}", "data": "0x70a08231{padded_hex_owner}"}, "latest"]}
  },
  "mixed_weights": {
    "mirror_account_query": 0.15, "mirror_balance_query": 0.15, "rpc_balance_query": 0.10,
    "mirror_tx_lookup": 0.10, "mirror_token_metadata": 0.10, "rpc_hts_balanceOf": 0.10,
    "mirror_block_by_number": 0.05, "mirror_block_head": 0.05,
    "rpc_block_by_number": 0.05, "rpc_block_height": 0.05, "rpc_chain_id": 0.05,
    "mirror_block_head_rpc_dup": 0.05
  }
}
```

---

## 11. DSL 表达力分析(Hedera 三 API + 双协议测试关键)

### 11.1–11.6(对齐其他链通用条目)

- **11.1 method 命名**:Mirror = HTTP method + path 模板(`GET /api/v1/<resource>`);JSON-RPC = `eth_*` literal。DSL 已支持 string literal,Mirror 需要 `path` + `query` 两层模板字段。
- **11.2 params 类型**:Mirror = path 占位(`{account_3part}`)+ query 字符串占位;JSON-RPC = array(同 Ethereum)。**`3part_id` 占位是 DSL 新值**(`0.0.X` 直接嵌入 path,无需 URL-encode 因 `.` 在 path 中合法)。
- **11.3 result 类型**:Mirror = 原始 JSON,无 `result` 包装,顶层 key 即业务字段(`balances`/`transactions`/`blocks`/...);JSON-RPC = `{jsonrpc, id, result}` 标准包装。**响应校验路径差异 per-protocol**。
- **11.4 错误 schema**:Mirror = HTTP 4xx(404/400)+ body `{"_status":{"messages":[{...}]}}`(⚠️ 本次未触发 4xx);JSON-RPC = `{"error":{"code":-32601/-32602,"message":"..."}}`(E10+E13 实测,**message 中含详细诊断**,如 "Expected 0x prefixed string representing the address (20 bytes)")。
- **11.5 batch**:Mirror — **不支持**(纯 REST);JSON-RPC — ⚠️(本次未验证,Hashio 文档未明确)。
- **11.6 双协议**:**Mirror REST 同步暴露在 `mainnet-public.mirrornode.hedera.com` 与 JSON-RPC 在 `mainnet.hashio.io`** — 是**两个独立 host**(与 Tron 同 host `api.trongrid.io` 不同),**DSL 双 endpoint 字段需分离**(`mirror_endpoint` vs `rpc_endpoint`)。

### 11.7(强制)Hedera 三 API 对比(全部实测填,gRPC 列凭官方文档)

| 维度 | Mirror Node REST(主测) | JSON-RPC Relay(主测) | gRPC HCS / HAPI(**不测**) |
|---|---|---|---|
| 协议 | REST(GET/POST + JSON) | JSON-RPC 2.0(POST + body) | gRPC + protobuf(binary) |
| 入口路径 | `/api/v1/<resource>[/<id>][?<query>]`(多 path) | 单一 `/api`(Hashio)或 `/`(自托管) | binary RPC service `proto.CryptoService/ConsensusService/...` |
| 探活 | `GET /api/v1/network/supply` → E1 实测 `{released_supply, total_supply, timestamp}` | `eth_blockNumber` → E4 实测 `"0x5b004d1"` | `NetworkGetVersionInfoQuery`(protobuf) ⚠️ |
| balance 查询 | `GET /api/v1/balances?account.id=0.0.2` → E2 实测 `{balances:[{account:"0.0.2", balance:1663012637744658(tinybar), tokens:[]}], links}` | `eth_getBalance("0x0000000000000000000000000000000000000002","latest")` → E6 实测 `"0xdc190f51555e27b8e0800"`(weibar) | `CryptoGetAccountBalanceQuery` ⚠️ |
| tx 查询 | `GET /api/v1/transactions/{id}` → E8 实测含 `transfers[]/token_transfers[]/nft_transfers[]/charged_tx_fee/memo_base64/transaction_hash(base64)/transaction_id` | `eth_getTransactionByHash("0x...")` → EVM-style ⚠️(仅 HSCS 合约 tx 才有 EVM hash) | `TransactionGetReceiptQuery` / `TransactionGetRecordQuery` ⚠️ |
| block 查询 | `GET /api/v1/blocks/{number}` → E12 实测 `{count, hash(0x96-char), number, timestamp{from,to}, gas_used, logs_bloom}`(**record stream 包装**) | `eth_getBlockByNumber("latest", false)` → E9 实测填充完整 EVM 字段(`stateRoot/receiptsRoot/transactionsRoot/baseFeePerGas/withdrawals[]` 等多为 0 占位) | **gRPC 无 block 概念**,用 `consensus_timestamp` 排序 record |
| HTS token | `GET /api/v1/tokens/0.0.456858` → E11 实测 USDC `{name:"USD Coin", decimals:"6", memo:"USDC HBAR", supply_key, admin_key, freeze_key, ...}` | `eth_call({to:"0x000000000000000000000000000000000006F89A", data:"0x70a08231<padded>"})` → E15 实测 `"0x"` (account 无该 token,**HTS precompile 路径打通**) | `TokenGetInfoQuery` ⚠️ |
| 地址格式输入 | **3-part `0.0.X`**(原生)或 EVM long-zero hex | **仅 EVM 20-byte hex**(long-zero 或 ECDSA alias) | account_num(uint64 + shard/realm) |
| 错误返回 | HTTP 404/400 + `{"_status":{"messages":[...]}}` ⚠️ 未触发 | `-32601` method not found(E10 实测)、`-32602` invalid params(E13 实测,包含明确诊断信息) | gRPC status code + ResponseCode enum |
| 文档完整性 | **完整**(全部 hashgraph 实体:account/balance/tx/block/token/topic/contract/schedule/network) | **EVM-compat 子集**(`eth_*` 常用 method;**无 HTS topic schedule 等 Hedera 独有信息**) | **完整**(HAPI 全部 service) |
| 字段语义完整度 | **极高**(`auto_renew_period`、`decline_reward`、`evm_address`、`key{_type:ProtobufEncoded}`、`alias` 等 Hedera 独有字段全暴露) | **低**(只 EVM 抽象层 — balance/tx/block) | **极高** + 原生 protobuf schema |
| 公共端点 | `https://mainnet-public.mirrornode.hedera.com` | `https://mainnet.hashio.io/api` | 仅付费(QuickNode 等)+ mTLS |
| 与其他链 DSL 复用度 | 与 Polkadot sidecar GET-path 风格 ~70% 同构;但 Polkadot 无 query 占位 | 与 Ethereum/Tron-RPC ~95% 同构 | **0%**(protobuf 不适合 vegeta) |

**关键发现**:
- **block 语义差异**:`Mirror /blocks/{n}` 是 record stream 包装,timestamp 是 `{from, to}` 区间(E7+E12);JSON-RPC `eth_getBlockByNumber` 填充完整 EVM 字段但多为 0/空占位(`stateRoot=0x56e81f...b421` 是 RLP-encoded empty trie 常数,E9)。**同一 block #95421653,两套 API 字段命名完全不同**,但底层指向同一 record file。
- **balance 单位差异**:Mirror 返回 **tinybar**(`1663012637744658`,8 位精度);JSON-RPC 返回 **weibar**(= tinybar × 10^10,与 Ethereum wei 对齐)。E2+E6 实测 0.0.2 余额对比:tinybar `1663012637744658` ≈ weibar `0xdc190f51555e27b8e0800`(取约 16.63M HBAR,数值一致,**单位换算需 plugin 配置**)。
- **HTS token 既是原生 token 也是合约**:Mirror 走 `/api/v1/tokens/0.0.456858` 拿元数据(E11),JSON-RPC 走 `eth_call` 到 **long-zero EVM 地址**(`0x000000000000000000000000000000000006F89A`)调用 `balanceOf(address)`(E15)— **HTS 通过 precompile 暴露 ERC20 接口**,这是 Hedera 独有架构。
- **EVM 地址 = 20-byte 严格校验**:E13 实测 `0x...000F8DA`(41 字符)被拒,error message 明确说 "Expected 0x prefixed string representing the address (20 bytes)" — **DSL fixture 生成必须严格 padded 到 40 hex**。
- **tx hash 双格式**:Mirror 用 `0.0.3229-1779562731-037000118`(transaction_id,account-validStart-nanos),JSON-RPC 用 32-byte hex。**两者无直接转换关系**(不同签名体系)。

### 11.8(强制)DSL 选择建议

- [ ] 只 Mirror REST(本框架简化,EVM 部分忽略)→ **拒绝**,JSON-RPC 是 Hedera 70%+ DeFi 流量来源(uniswap-like、SaucerSwap),不测则脱离生产负载
- [ ] 只 JSON-RPC(复用 Ethereum DSL,但失去 Hedera 原生 API 测试覆盖)→ **拒绝**,放弃 HTS 元数据、tx record、staking reward 等 Hedera 独有信息
- [ ] 双协议自动 fallback → **拒绝**(同 Tron §11.8 理由:fallback 掩盖单协议故障,违背可观测性)
- [x] **双协议混用(per-method `protocol` 字段),同 Polkadot/Tron 模式**:Mirror REST 负责 account/balance/tx/token/block(因 Mirror 字段完整,真实生产负载占比 ~60%);JSON-RPC 负责 EVM contract call + HTS precompile + EVM-compat balance/block(覆盖 dApp 真实流量,~40%)

**理由**(3 段):

**(1) 三 API 是 Hedera 节点架构客观现实,benchmark 必须覆盖两个公共可达的**。Hedera 节点分三层:consensus node(gRPC,付费 mTLS,不测)、mirror node(REST/GraphQL,本调研主测)、JSON-RPC Relay(EVM-compat 包装,本调研副测)。Mirror 服务原生客户端(HashPack 钱包、Hedera SDK)+ 完整字段需求(staking、key 结构、auto-renew、custom fee);JSON-RPC 服务 Web3 生态(MetaMask、ethers.js、Hardhat),Hedera 上 ~70% 智能合约项目走 JSON-RPC。**只压一套**就脱离真实生产负载分布。Mirror 字段重(单 account 响应 1.5KB+,见 E3)、JSON-RPC 字段轻 — 对节点的 IO/CPU 模式完全不同,benchmark 双协议混压才能反映真实压力。

**(2) DSL pattern 复用 Polkadot/Tron 双协议 infra ~50%,净增工作量小**。Tron wave 3 已扩 `protocol` 枚举至 `{jsonrpc, rest_post_body}`,Polkadot wave 2 已建 `rest_sidecar`(GET + path 占位)。Hedera 是**第 3 条双协议链**,主要新增:(a) `protocol = "mirror_rest"`(或更通用的 `rest_get_path_query`),GET + path 占位 + **query 字符串占位**(Polkadot 仅 path 占位,这是新增维度);(b) `address_format` 枚举新增 `hedera_3part`(`shard.realm.num`);(c) `address_format` 枚举新增 `evm_hex_long_zero`(20-byte hex 但前 24 字符必须为 0,可由 3-part num 派生);(d) `balance_unit` 配置字段新增 `tinybar` vs `weibar` 双单位映射(原 Ethereum 只有 wei,Bitcoin 只有 satoshi)。**plugin-side 配置语法 100% 复用 Polkadot/Tron 既有结构**,vegeta target 生成器只需新增 query 字符串占位渲染逻辑(~20 行)。

**(3) 决策反转护栏检查**(skill `chain-additions` 要求):若引入 `family=hedera`,DSL endpoints schema **必须扩展**容纳:① 3-part account ID(`0.0.X`)新枚举值;② block 即 record stream 包装(`timestamp{from,to}` 双时间字段);③ 双 endpoint host(`mirror_endpoint` + `rpc_endpoint` 分离,与 Tron 单 host 不同)。**未达成此扩展,family=hedera 无法落地**。本调研已在 §10 JSON 示例完整列出 schema 变化,确保 Phase 2.1 plugin 实现有据可依。

#### 与 Polkadot/Tron 双协议 infra 复用度评估

| 设施 | Polkadot wave 2 已建 | Tron wave 3 扩展 | Hedera 是否能直接复用 | 增量工作 |
|---|---|---|---|---|
| plugin JSON `api_protocol: [...]` 列表字段 | ✅ `["jsonrpc","rest_sidecar"]` | ✅ `["jsonrpc","http_post"]` | ✅ `["jsonrpc","mirror_rest"]` | enum 扩 1 值 |
| per-method `protocol` 字段 | ✅ | ✅ 扩值 | ✅ 再扩 1 值 `mirror_rest` | enum 扩 1 值 |
| `path` 占位符模板渲染 | ✅ GET path 渲染(`/blocks/{n}`) | ⚠️ Tron path 固定 + body 渲染(~30 行) | ✅ 复用 path 渲染;**新增 query 字符串占位渲染(~20 行)** | ~20 行 query 渲染器 |
| 双 endpoint host 分离 | ⚠️ Polkadot 单 host | ⚠️ Tron 单 host | **首例双 host**:`mirror_endpoint` + `rpc_endpoint` 字段分离 | ~10 行 endpoint 路由 |
| `success_check` per-protocol 抽象 | ✅ | ✅ | ✅ 直接复用,Mirror 校验 HTTP 200 + 顶层有业务 key(`balances`/`blocks`/`transactions`) | 0 |
| fixture-based param 列表 | ✅(`polkadot_accounts.txt`) | ✅(`tron_accounts_base58.txt`) | ✅ 新增 `hedera_accounts_3part.txt` + `hedera_accounts_evm_longzero.txt` + `hedera_tokens.txt` | adapter 一次性预生成 |
| 3-part ID -> EVM long-zero 转换 | — | — | **首例**:`0.0.N` -> `0x` + 24*'0' + N 的 16-char hex padded | adapter 内 ~10 行 |
| balance 双单位换算(tinybar/weibar) | — | — | **首例**:plugin `balance_unit_normalizer` 字段 | DSL schema +1 字段 |
| mock_rpc_server 路径路由 | ✅ `do_GET` sidecar 分支 | ✅ `do_POST` `/wallet/*` 分支 | ✅ 复用 `do_GET` 但需大幅扩 `/api/v1/*` 多 resource 分支(~80 行) | ~80 行 mock 分支 |
| **总复用度** | — | — | **~50%** | 净增 ~140 行 + adapter + DSL schema +2 字段 |

**结论**:**Hedera 是双协议 DSL 设计的第 3 次验证**(Polkadot=GET-path、Tron=POST-body、Hedera=GET-path-query),三链共同验证了 `per-method protocol` 字段的通用性。本次扩 `mirror_rest` + `query` 占位 + 双 endpoint 后,DSL 双协议层架构可视为**稳定**,后续 Avalanche P/C/X 三链分压、ICP 多 canister 等场景应能直接复用。

---

## ADR-0005 实施期 caller/reader 改造点(hedera_dual family,2026-05-28)

**强制要求**(token-level-careful-edit Case-K + parallel-entry-trap):本链是 hedera_dual family 唯一链,**双协议 GET path-query + JSON-RPC POST 混合**,ADR-0005 引入专门 handler:

| # | 位置 | 改动 | 原因 |
|---|---|---|---|
| 1 | `tools/fake-node/handlers/hedera_dual.go` | **新建** dual-protocol handler:根据 path 前缀 dispatch — `/api/v1/*` → Mirror REST、`/api` POST → Hashio JSON-RPC | 唯一链 ~150 LOC(无 sister chain 摊薄) |
| 2 | `tools/fake-node/fixtures/hedera/mirror/` | record Mirror REST:`/api/v1/accounts/{id}`、`/api/v1/balances?account.id={id}`、`/api/v1/transactions?account.id={id}` 等 6+ fixture | REST 端 replay |
| 3 | `tools/fake-node/fixtures/hedera/jsonrpc/` | record Hashio JSON-RPC:`eth_blockNumber`、`eth_getBalance`、`eth_getTransactionByHash` 等 5+ fixture | JSON-RPC 端 replay |
| 4 | `config/chains/hedera.json` `_meta.rest_paths` + `_meta.jsonrpc_methods` | **双字段并存**:RestAdapter 读 rest_paths(Mirror GET),JsonRpcAdapter 读 jsonrpc_methods(Hashio POST) | 双协议 schema 来自 §11 调研 |
| 5 | `config/chains/hedera.json` `_meta.health_probe` | **新增**:`{"path":"/api/v1/network/nodes","method":"GET","expect_status":200}` | Mirror 端 startup |
| 6 | `tests/test_hedera_dual_smoke.sh` | **新建**:Mirror + JSON-RPC 各 3 method,断言双端 200 + 关键字段 | **双协议路由验证关键测试**(2026-05-24 dual-protocol case 教训) |
| 7 | `tools/ci_smoke.sh` | 追加 hedera | L3 全 PASS |

**特别注意 — 协议层验证(2026-05-24 hedera_dual case 教训)**:
- L1/L2 schema 测试 PASS ≠ wire protocol OK,**必须在 ci_smoke 真打 Hashio + Mirror endpoint** 至少 1 次,验 HTTP 200 而非仅 schema 解析通过
- 防 `_meta.id_format` adapter-fabricated 3-part ID 传给 Hashio(它要 0x EVM hex)的 HTTP 400 trap
- 详见 skill `honest-self-check-no-fake-evidence/references/protocol-layer-changes-require-live-http.md`

详见 `docs/architecture/decisions/0005-cardano-family-correction-and-handler-rollout.md`。

---

## Open Questions(待解决问题)

- [ ] **DSL ASK A**:`address_format` 是否定义为枚举(`{base58, hex, bech32, hedera_3part, ...}`)还是结构化对象(`{encoding, regex, prefix, length, conversion}`)?**强烈推荐结构化**(Hedera 一条链就需要 3 种 address_format 共存:`hedera_3part` + `evm_hex_long_zero` + `evm_hex_ecdsa_alias`,枚举值会爆炸)。
- [ ] **DSL ASK B**:`protocol` 枚举的精度 — `{jsonrpc, rest_get_path, rest_get_path_query, rest_post_body}` 四值是否过细?替代方案:统一 `{jsonrpc, http}` + 子字段 `http_method: GET|POST` + `path_template` + `query_template` + `body_template`,任一为 null 即跳过。**强烈推荐替代方案**(可扩 PUT/PATCH/DELETE,DSL 更通用)。
- [ ] **DSL ASK C**:**block 语义抽象** — 当前 DSL `block_time_ms` 是单一数字,Hedera 的 block 是 record stream 包装,`timestamp` 是 `{from, to}` 区间。是否引入 `block_semantics: {model: "blockchain"|"record_stream_wrapper"|"slot_based", timestamp_field: "single"|"range"}` 描述字段?Phase 2.1 不必落地但 Phase 2.2 视觉化展示需要(Grafana panel 标"块"的语义)。
- [ ] **DSL ASK D**:`balance_unit` 多单位换算 — Hedera 同一账户余额在 Mirror(tinybar)和 JSON-RPC(weibar)返回值差 10^10 倍,plugin 是否需配置 `balance_unit_normalizer: {mirror_rest: "tinybar", jsonrpc: "weibar", display_unit: "HBAR", display_decimals: 8}`?Phase 2.1 mixed set 数据对比 panel 需要。
- [ ] **DSL ASK E**:3-part ID 到 EVM long-zero 的转换是否归 `fetch_active_accounts` 阶段一次性产出(0 Python 友好)还是 plugin 配置时声明 `address_class` 让 adapter 运行时转?**强烈推荐前者**(避免运行时 Python,与 Tron 同决策)。
- [ ] **DSL ASK F**:tx hash 双格式(Mirror `0.0.X-secs-nanos` vs JSON-RPC `0x32hex`)— mixed set 是否需各自独立 fixture(`hedera_tx_ids_3part.txt` + `hedera_tx_hashes_evm.txt`)?两者无直接转换关系,**必须独立采样**。
- [ ] **DSL ASK G**:HTS precompile 地址(long-zero 0x..6F89A 对应 0.0.456858)— 是否在 plugin 配置 `hts_tokens: [{name:"USDC", id_3part:"0.0.456858", evm_long_zero:"0x...06F89A", decimals:6}]` 字段?Phase 2.1 跨 token 对比需要。
- [ ] **未实证 ⚠️**:Mirror Node `https://mainnet-public.mirrornode.hedera.com` 真实 rate limit(凭文档 ~100 req/s,本次未打满)
- [ ] **未实证 ⚠️**:Hashio JSON-RPC `https://mainnet.hashio.io/api` 真实 rate limit(凭文档 ~50 req/s)
- [ ] **未实证 ⚠️**:Mirror REST 4xx 错误体(预期 `{"_status":{"messages":[...]}}`,本次未触发)
- [ ] **未实证 ⚠️**:`eth_getTransactionByHash` 在 Hedera JSON-RPC 真实返回 schema(需要先抓 HSCS 合约 tx 的 EVM hash)
- [ ] **未实证 ⚠️**:JSON-RPC batch(`[{...},{...}]`)是否支持 — Hashio 文档未明确
- [ ] **未实证 ⚠️**:Mirror Node GraphQL 端点(`/graphql`)是否在 mainnet-public 公开 — 本次未试
- [ ] **未实证 ⚠️**:Hedera Finality 真实数值(凭 aBFT 共识理论 ~3–5s)

---

## Changelog

| Date | Author | Change |
|---|---|---|
| 2026-05-23 | Hermes Agent | 初次调研;14 次 curl 实测覆盖 Mirror REST + JSON-RPC Relay;双 API DSL 决策 = per-method protocol;复用 Polkadot/Tron 双协议 DSL pattern ~50%;新增 `hedera_3part` address format、`mirror_rest` protocol、双 endpoint host、tinybar/weibar 单位换算 4 项 DSL 扩展 ASK;明确 block 在 Hashgraph 中是 record stream 包装的语义差异 |
