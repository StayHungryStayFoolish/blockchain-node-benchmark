# 10-Algorand 调研

> **此文件由 `_template.md` 衍生,Phase 1.2 Wave 3 产出。**
> **强制满足**:`_template.md` §1–§10 + §11 DSL(含 11.7 algod/indexer 双节点表 + 11.8 DSL 决策)
> **关键产出**:**双节点架构在 DSL 中的表达决策**(详 §11.8,推荐 **方案 B `node_role` 字段(可选)+ AlgorandAdapter 内置 algod/indexer 双 endpoint**)
> **真实证据**:本稿所有 11 个端点形态均在 2026-05-23 通过 `curl` 实测公共 Algonode 集群(`~/algo_evidence/*.json` 存留)

---

## 元信息

| 项 | 值 |
|---|---|
| 链名(中) | Algorand |
| 链名(英) | Algorand |
| 编号 | 10(Wave 3 顺序;最终编号待 P1 收尾 user 决定) |
| Mainnet ChainID | `mainnet-v1.0`(**字符串**,非数字) |
| Mainnet GenesisHash | `wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=`(base64,32 byte)— **E1 实测见 §1** |
| 调研日期 | 2026-05-23 |
| 调研者 | Hermes Agent |
| 状态 | 🟢 调研完成,§11.8 决策待 user review |

---

## 1. Sources(权威来源)

| 类型 | URL | 访问日期 | 备注 |
|---|---|---|---|
| 官方门户 | https://developer.algorand.org/ | 2026-05-23 | Algorand Developer Portal(协议规范主页) |
| algod REST OpenAPI | https://developer.algorand.org/docs/rest-apis/algod/ | 2026-05-23 | algod 节点 v2 REST API 完整 spec |
| indexer REST OpenAPI | https://developer.algorand.org/docs/rest-apis/indexer/ | 2026-05-23 | indexer v2 REST API 完整 spec |
| go-algorand 源码 | https://github.com/algorand/go-algorand | 2026-05-23 | algod 节点(Go 实现) |
| indexer 源码 | https://github.com/algorand/indexer | 2026-05-23 | indexer(Go 实现,PostgreSQL 后端) |
| Algonode 公共端点 | https://nodely.io/docs/free/start | 2026-05-23 | 本稿压测使用的 free public RPC |
| AlgoExplorer | https://allo.info / https://algoexplorer.io | 2026-05-23 | 区块浏览器(查 tx/account) |
| ASA 标准 | https://developer.algorand.org/docs/get-details/asa/ | 2026-05-23 | Algorand Standard Asset 规范 |

**E1 实测 — algod `/versions`(无需任何 header)**:

```bash
$ curl -sS https://mainnet-api.algonode.cloud/versions
{"versions":["v2"],"genesis_id":"mainnet-v1.0",
 "genesis_hash_b64":"wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=",
 "build":{"major":4,"minor":7,"build_number":0,"commit_hash":"6927d906+","branch":"AVAIL","channel":"AVAIL"}}
```

→ 证明 mainnet genesis_id/genesis_hash 与 task context 一致,无需信任训练记忆。

---

## 2. Protocol Family(协议族)

| 项 | 值 |
|---|---|
| Family | **Algorand**(自研,**独立 family**,不属于 EVM / Move / UTXO / Cosmos / Substrate / Solana / NEAR 任一) |
| Consensus | **Pure PoS**(Algorand BA⋆ + VRF 抽签 — Algorand 独有,与 Cosmos Tendermint、ETH PoS Casper、NEAR Nightshade 都不同) |
| VM | **AVM**(Algorand Virtual Machine,TEAL 字节码,**非 EVM 也非 MoveVM**) |
| Block Time | ≈ **2.8s**(协议目标,自实测 `last-round` 在 ~30s 内推进 ~11 次) |
| Finality | **即时最终性**(BA⋆ 每块决定后即不可逆;无分叉,无 reorg)— 与 ETH 32-slot finality、NEAR 三档 finality 都不同 |
| Reuse Existing Adapter? | **No**(详 §10):账户模型 / 鉴权 header / **双节点架构** / TEAL VM 与现有 7 条已上线链(EVM 5 条 + Solana + Sui)均无交集 |

---

## 3. Public RPC(公共节点)

> Algorand 公共节点**双轨制**:每家 provider 都同时提供 algod(:4001 等价 HTTPS)+ indexer(:8980 等价 HTTPS)**两个分离 endpoint**。

| Provider | algod endpoint | indexer endpoint | Auth | Rate Limit | E1 实测 |
|---|---|---|---|---|---|
| Algonode(本稿压测用) | `https://mainnet-api.algonode.cloud` | `https://mainnet-idx.algonode.cloud` | **无**(`X-Algo-API-Token` 头可省略 / 任意值均接受) | 60 req/s 免费层(官方文档)⚠️ 未触发实证 | ✅ 双侧均 HTTP 200(详 §3.1) |
| Nodely(Algonode 同源) | `https://mainnet-api.4160.nodely.dev` | `https://mainnet-idx.4160.nodely.dev` | 无 | 同上 | ✅ HTTP 200 / 0.20s |
| 自部署 algod + indexer | `:4001` / `:8980` | 同左 | **必须** `X-Algo-API-Token: <admin.token>` 头(自部署默认开启) | 无 | ⚠️ 本调研未自部署,仅文档断言 |

### 3.1 E1 实测(2026-05-23,Algonode 公共集群)

```bash
$ curl -sS -w "HTTP:%{http_code} TIME:%{time_total}s\n" \
     https://mainnet-api.algonode.cloud/v2/status
{"catchpoint":"","last-round":61461471,
 "last-version":"https://github.com/algorandfoundation/specs/tree/953304de35264fc3ef91bcd05c123242015eeaed",
 ...}
HTTP:200 TIME:0.214s

$ curl -sS -w "HTTP:%{http_code} TIME:%{time_total}s\n" \
     https://mainnet-idx.algonode.cloud/health
{"data":{"migration-required":false,"read-only-mode":true},
 "db-available":true,"is-migrating":false,"message":"61461471","round":61461471,"version":"3.9.0"}
HTTP:200 TIME:0.146s
```

### 3.2 鉴权 header 实证

```bash
# 不带任何 header → 200
$ curl -sS -o /dev/null -w "no-header HTTP:%{http_code}\n" https://mainnet-api.algonode.cloud/v2/status
no-header HTTP:200
# 带任意 X-Algo-API-Token → 仍 200(Algonode 不校验)
$ curl -sS -o /dev/null -w "X-Algo-API-Token HTTP:%{http_code}\n" \
     -H "X-Algo-API-Token: anything" https://mainnet-api.algonode.cloud/v2/status
X-Algo-API-Token HTTP:200
# 带 Bearer 头 → 也 200(被忽略)
$ curl -sS -o /dev/null -w "Bearer HTTP:%{http_code}\n" \
     -H "Authorization: Bearer junk" https://mainnet-api.algonode.cloud/v2/status
Bearer HTTP:200
```

→ **Algonode 公共集群不强制鉴权**;**但自部署 algod 默认要求 `X-Algo-API-Token` 头**(go-algorand `data/algod.token`)。DSL 必须保留可选鉴权 header 通道。

---

## 4. Account Model(账户模型)

| 项 | 值 |
|---|---|
| 模型 | **Account**(单账户多余额条目:1 个 ALGO + N 个 ASA opt-in slots) |
| Native token decimals | **6**(microalgo,1 ALGO = 10^6 microalgo)— ⚠ **注意非 9(Solana lamports)也非 18(EVM wei)** |
| Address derivation | **Ed25519 pubkey(32 byte)+ SHA-512/256 checksum(4 byte)→ base32(58 字符)** |
| Special account types | **ASA opt-in 槽位**(账户必须先 opt-in 一个 ASA 才能持有,占 100,000 microalgo min-balance);**Application(智能合约)**(整数 ID,可被账户 opt-in 占用 local state) |

### 4.1 E1 实测 — algod 账户结构

```bash
$ curl -sS https://mainnet-api.algonode.cloud/v2/accounts/Q5WOHVUKNEM4XOVL725KH77WS6GODZSI4HTSWZAILM36ANSYVHW5RJI3KE \
   | head -c 350
{"address":"Q5WOHVUKNEM4XOVL725KH77WS6GODZSI4HTSWZAILM36ANSYVHW5RJI3KE",
 "amount":<microalgo>, "min-balance":..., "round":61461..., "status":"Offline",
 "total-assets-opted-in":..., "total-created-assets":..., "total-apps-opted-in":...,
 "assets":[{"asset-id":..., "amount":..., "is-frozen":false}, ...]}
```

→ **关键差异**:与 EVM `eth_getBalance` 只返单值不同,algod 一次返回 **ALGO 余额 + 所有 ASA 持仓 + 所有 application local-state**(13KB 响应)。**ASA 余额无需第二次调用**(对照 EVM 必须 `eth_call(balanceOf)`)。

---

## 5. Core RPC Methods(本框架监控所需)

> Algorand REST 走 HTTP method + URL path(无 JSON-RPC envelope),所有 method 都是 GET 或 POST + path。

| logical_method | HTTP | Path(algod 或 indexer)| 类别 | 节点 | mixed 权重 |
|---|---|---|---|---|---|
| `block_height` | GET | `/v2/status` (algod) 或 `/health` (indexer) | block height | **algod**(实时) | 0.05 |
| `balance` | GET | `/v2/accounts/{addr}` | balance | **algod**(实时;**响应含全部 ASA 持仓**) | 0.25 |
| `tx_lookup` | GET | `/v2/transactions/{txid}` | tx lookup(历史) | **indexer**(algod 无此端点,返 404 — §11.7 表) | 0.20 |
| `tx_pending` | GET | `/v2/transactions/pending/{txid}` | tx 状态(含**最近确认**)| **algod**(短窗口,见 §5.1 实测) | 0.05 |
| `block_query` | GET | `/v2/blocks/{round}?format=json` | block content | **algod 或 indexer**(两侧同 path)| 0.10 |
| `asset_info` | GET | `/v2/assets/{asset-id}` | ASA 元数据 | **algod**(实时) | 0.10 |
| `asset_balances` | GET | `/v2/assets/{asset-id}/balances?limit=N` | ASA 持有者列表 | **indexer 独有**(algod 无此端点)| 0.10 |
| `account_txs` | GET | `/v2/accounts/{addr}/transactions?limit=N` | 地址交易历史 | **indexer 独有**(algod 返 404 — §5.2 实测)| 0.10 |
| `tx_params` | GET | `/v2/transactions/params` | 提交 tx 用 suggested params | algod | 0.05 |

**总权重** = 0.05 + 0.25 + 0.20 + 0.05 + 0.10 + 0.10 + 0.10 + 0.10 + 0.05 = **1.00** ✅

### 5.1 E1 实测 — algod `/v2/transactions/pending/{txid}` 行为(**与 task context 描述不符,重要更正**)

Task context 描述为 "only pending!",但实测对已确认 tx 也返 200 + `confirmed-round`:

```bash
$ curl -sS https://mainnet-api.algonode.cloud/v2/transactions/pending/PO3UMN7TCRZLRUZ4JEPK54DX5O55YSZULAIPOEDMXX7GHTJ4FJPA
HTTP:200 TIME:0.206s
{"confirmed-round": 61461400, "pool-error": "",
 "txn":{"sig":"ocPv...","txn":{"amt":3487000000,"fv":61461392,"gen":"mainnet-v1.0",
   "gh":"wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=",
   "rcv":"2ZPNLKXWCOUJ...","snd":"Q5WOHVUKNEM...","type":"pay"}}}
```

→ algod 实际维护**最近 ~1000 round(可配置 `MaxAcctLookback`)的 confirmed tx 缓存**;超出窗口才 404。**结论**:`tx_pending` 对最新 ~1 小时的 tx 可用,**但历史 tx 必须走 indexer**(直接 `GET /v2/transactions/{txid}` 在 algod 上返 404)。

### 5.2 E1 实测 — algod 缺失的 indexer-only 端点

```bash
$ curl -sS -o /dev/null -w "%{http_code}\n" https://mainnet-api.algonode.cloud/v2/transactions/PO3UMN7TC...
404
$ curl -sS -o /dev/null -w "%{http_code}\n" https://mainnet-api.algonode.cloud/v2/accounts/Q5WOHVUKN.../transactions?limit=3
404
$ curl -sS -o /dev/null -w "%{http_code}\n" https://mainnet-idx.algonode.cloud/v2/accounts/Q5WOHVUKN.../transactions?limit=3
200
```

→ **历史 tx 直查 + 账户交易列表 + ASA 持有者列表 = 全部 indexer 独有**。这是 §11.7 双节点表的核心实证。

---

## 6. Address Format(地址格式)

| 项 | 值 |
|---|---|
| 编码 | **Base32**(RFC 4648,**不带填充**)— 与 Bitcoin/Bech32、Solana/Base58、EVM/Hex 都不同 |
| 长度 | **58 字符**(32B pubkey + 4B checksum → 36B → ceil(36×8/5)=58 字符 base32) |
| Checksum | **SHA-512/256(pubkey) 的最后 4 byte**,拼接到 pubkey 后再 base32 编码 |
| 示例(主网真实) | `Q5WOHVUKNEM4XOVL725KH77WS6GODZSI4HTSWZAILM36ANSYVHW5RJI3KE`(从 block 61461400 sender 取,E1 实测可正常 `GET /v2/accounts/{addr}` 返 200) |
| 校验正则(初筛) | `^[A-Z2-7]{58}$`(base32 字符集,不含 0/1/8/9 和小写)— 真正校验必须 base32 解码 + SHA-512/256 重算 checksum |

### 6.1 E1 反证 — task context 给的地址 checksum 失败

```bash
$ curl -sS https://mainnet-api.algonode.cloud/v2/accounts/DPLD3RZSYVPBQR4AEUNXMRWPRDZJEY7LZG6JRT34IPSBOYY3EYLDC4O73U
HTTP:400
{"message":"... address DPLD3RZSYVPBQR4AEUNXMRWPRDZJEY7LZG6JRT34IPSBOYY3EYLDC4O73U is malformed, checksum verification failed"}
```

→ ⚠ Task context 中的 "Algorand foundation" 地址 checksum 校验失败(可能是 task 编写时手抄错误)。**本稿统一用从 block 61461400 实测取出的 `Q5WOHVUKN...` 作示例,确保 100% 真实**。

---

## 7. Signature Lookup(交易哈希)

| 项 | 值 |
|---|---|
| Hash 格式 | **Base32**(无填充,与地址同字符集) |
| 长度 | **52 字符**(32B SHA-512/256 → 52 字符 base32)— ⚠ 不要与 58 字符地址混淆 |
| 示例(主网真实)| `PO3UMN7TCRZLRUZ4JEPK54DX5O55YSZULAIPOEDMXX7GHTJ4FJPA`(block 61461400 内首笔 `pay` 类型 tx,E1 实测 indexer 返 200) |
| 查询 method | **历史**:`GET /v2/transactions/{txid}`(**indexer**);**最近**:`GET /v2/transactions/pending/{txid}`(algod,~1000 round 窗口) |
| Explorer URL 格式 | `https://allo.info/tx/{txid}` 或 `https://algoexplorer.io/tx/{txid}` |

### 7.1 E1 实测

```bash
$ curl -sS https://mainnet-idx.algonode.cloud/v2/transactions/PO3UMN7TCRZLRUZ4JEPK54DX5O55YSZULAIPOEDMXX7GHTJ4FJPA
HTTP:200 SIZE:782
{"current-round":61461505,
 "transaction":{"id":"PO3UMN...","tx-type":"pay","confirmed-round":61461400,
   "sender":"Q5WOHVUKN...","payment-transaction":{"amount":3487000000,"receiver":"2ZPNLKXW..."}, ...}}
```

---

## 8. Mixed Set(`mixed` 模式权重)

```json
{
  "block_height":   0.05,
  "balance":        0.25,
  "tx_lookup":      0.20,
  "tx_pending":     0.05,
  "block_query":    0.10,
  "asset_info":     0.10,
  "asset_balances": 0.10,
  "account_txs":    0.10,
  "tx_params":      0.05
}
```

**总和 = 1.00 ✅**。

**权重设计理由**:
- `balance` 0.25:常用读操作 + algod 一次返回 ALGO+ASA 全量,需重点压。
- `tx_lookup` 0.20:典型 explorer / wallet 工作负载,**走 indexer**,验 indexer 后端 PostgreSQL 命中率。
- `asset_info` 0.10 + `asset_balances` 0.10:ASA 是 Algorand 的核心 differentiator,必须覆盖(EVM 用 `eth_call(balanceOf)` 一笔,Algorand 双端点)。
- `account_txs` 0.10:**indexer-only** 的代表 method,需独立粒度监控以暴露 indexer PostgreSQL 索引性能。
- `block_query` 0.10:重量级(实测 71KB 响应),不宜更高以免主导吞吐。
- `block_height` 0.05 + `tx_params` 0.05 + `tx_pending` 0.05:轻量探活,低权重维持持续覆盖。

---

## 8.5 Phase 2.1 caller/reader 改造点(token-level Gate 3)

| # | 位置(file:line)| 改动 | 原因 |
|---|---|---|---|
| 1 | `config/config_loader.sh:666` `supported_blockchains` 数组 | **新增** `"algorand"` | 当前数组(E1 实测 `grep -n` 第 666 行):`("solana" "ethereum" "bsc" "base" "scroll" "polygon" "starknet" "sui")`,**未含 algorand**,无入口 |
| 2 | `config/config_loader.sh` 本链 `rpc_methods.mixed` 块(参考 sui 块 622-650) | **新建 algorand 块**:9 条 logical_method + 权重(§8),**额外字段** `node_role: algod|indexer`(详 §11.8 推荐方案) | vegeta target 生成器消费;**双节点路由必须显式表达** |
| 3 | `config/config_loader.sh` 本链 `param_formats` | 新增 9 条 method 对应 `(verb, path_template, query_params)`,path 形如 `/v2/accounts/{address}` | Algorand 全部 method 都是 HTTP path,**与 EVM 单一 POST `/` 不同**;沿用 cardano 调研(`06-cardano.md §11.3`)的 path-per-method 思路 |
| 4 | `tools/mock_rpc_server.py` 路由分发 | **新增 path 路由模式**(当前只支持 POST `/` JSON-RPC 分支)+ 新增 9 个 Algorand path handler | mock 是 fallback target;若不改,Algorand mock 模式跑不通(token-level Case-B/D 风险:`mock_rpc_server` 是 caller 中的 caller) |
| 5 | `tools/fetch_active_accounts.py` adapter 注册 | **新建** `AlgorandAdapter`(详 §10);内置双 endpoint 字段(`algod_url`,`indexer_url`)+ `node_role` 路由 | 现有 `EthereumAdapter / SolanaAdapter / SuiAdapter` 都是单 endpoint 假设,**Algorand 是 28 链中首个双节点链**(NEAR 单 endpoint,Cosmos 单 endpoint 多端口子路径) |
| 6 | `analysis-notes/baseline-current-state.md`(grep `algorand`) | 同步更新链路列表;标注双节点要求 | 文档真相对齐,防 v1.4.1 doc-vs-code 偏离 |
| 7 | `analysis-notes/disk-and-network-pipeline-redesign.md` | **新增** "indexer 后端是 PostgreSQL,disk I/O 模式与 algod 节点(LevelDB)不同" 的标注 | 后续 disk pipeline 设计需区分双后端 |
| 8 | `tests/<本链>.sh`(若新建) | 新建 algod / indexer 双侧 smoke test | L1/L2 单测覆盖双节点路径 |

**本链是新增链**(`#1` 实证),`#1–5` 必填;`#6–8` 视 Phase 2.1 拓扑决定。

**测试要求**:Phase 2.1 完成后必须跑 `core/master_qps_executor.sh --mixed --duration 30 --chain algorand`,**vegeta 所有请求 200**(double-check `tx_lookup` 落到 indexer URL,`balance` 落到 algod URL),作为 Algorand 改造的 E2 证据。

---

## 9. Mock Notes(mock_rpc_server 实现要点)

- **请求路径**:**多 GET path**(非 JSON-RPC dispatcher)— `mock_rpc_server.py` 必须先扩 path 路由(同 Cardano 调研结论)。
- **路由表**(mock 需实现):
  - `GET /v2/status` → `{"last-round": <自增>, "last-version": "...", ...}`
  - `GET /v2/accounts/{addr}` → `{"address":"...","amount":<rand>, "assets":[...], ...}`
  - `GET /v2/transactions/{txid}` (indexer port 模拟) → `{"current-round":..., "transaction":{...}}`
  - `GET /v2/transactions/pending/{txid}` (algod port 模拟) → `{"confirmed-round":..., "pool-error":"", "txn":{...}}`
  - `GET /v2/blocks/{round}?format=json` → 真实大响应(~70KB,可裁剪)
  - `GET /v2/assets/{id}` → `{"index":..., "params":{"creator":"...","decimals":6,"name":"USDC",...}}`
  - `GET /v2/assets/{id}/balances` → `{"balances":[...], "current-round":..., "next-token":"..."}`
  - `GET /health` (indexer port) → `{"data":{...},"db-available":true,"round":...,"version":"3.9.0"}`
- **响应 schema 样本**(E1 实测,可贴 mock 默认值)— 详见 §5.1、§7.1。
- **特殊错误**(E1 实测):
  - `400` + `{"message":"... address ... is malformed, checksum verification failed"}` — 地址 checksum 错
  - `400` + `{"message":"rewinding account is no longer supported on free endpoints, please remove the round= query parameter and try again"}` — Algonode 免费层禁用 `?round=` 历史余额(**重要 production 约束**)
  - `404` + `{"message":"Not Found"}` — 路径不存在或 tx 出 algod 短窗口
- **mock 实现复杂度**:**Medium**(路由数 9 + 双端口模拟 + ASA opt-in 嵌套数组生成)— 比 Cardano middleware 抽象低,但比 EVM JSON-RPC 单分支高。

---

## 10. Adapter Reuse Decision(adapter 复用决策)

### 候选 adapter

| Adapter | 兼容度 | 缺失能力 |
|---|---|---|
| EthereumAdapter | **5%** | JSON-RPC envelope vs REST path;ABI vs 无 ABI;EVM hex addr vs base32 |
| SolanaAdapter | **10%** | Base58 vs Base32;getAccountInfo 不返 token 列表 vs algod 返全部 ASA |
| SuiAdapter | **5%** | Move objects vs ASA opt-in;JSON-RPC vs REST |
| NearAdapter(Wave 2 新建)| **15%** | dispatcher 模式 vs path 模式;但 **logical_method 字段可复用** |

### 决策

- [ ] 复用现有 adapter
- [x] **新建 `AlgorandAdapter`**(family = `algorand`,新族)
- [ ] 混合

### 理由

**第一段 — 双节点架构是 28 链中独一份**。Algorand 是目前调研的 10 条链中**唯一在生产协议层就拆分实时节点(algod)和历史索引节点(indexer)** 的链。EVM 的 archive node vs full node 是同一 API、不同存储深度;Cosmos LCD+RPC+gRPC 是同进程多端口;Cardano 的 cardano-node + db-sync 接近,但 db-sync 不暴露 API(再前面套 Koios / Blockfrost)。Algorand **强制要求 client 根据 method 路由到不同 host**(E1 实测:历史 tx 在 algod 必返 404 — §5.2)。这不是 adapter 内部细节,而是配置/请求构造层的一等公民,**必须在 adapter 抽象内显式建模 algod_url + indexer_url 双字段 + 每 method 的 node_role 标签**。EthereumAdapter / SolanaAdapter / SuiAdapter 当前都是 `rpc_endpoint: string` 单一字段假设,塞双 endpoint 会污染所有现有链的 schema。

**第二段 — 协议层(REST + path)与现有任何 adapter 都不复用**。Algorand 是**纯 REST**(无 JSON-RPC envelope),每个 method 是独立的 (verb, path, query_params)。这与 Cardano(Wave 2)的 path-per-method 同类,但 Cardano 没有双节点问题 — 因此 AlgorandAdapter 可**借鉴** CardanoAdapter 的 path-per-method 实现,但**不能继承**(双节点路由属于 adapter 顶层关注点)。

**第三段 — 应用层(ASA + opt-in + Application)语义独特**。ASA(Algorand Standard Asset)在协议层就是原生类型(不是合约),`GET /v2/accounts/{addr}` 一次响应内嵌全部 ASA 持仓 — 这与 EVM "1 次 eth_getBalance + N 次 eth_call(balanceOf)" 完全不同,影响 token_balance 在 mixed 模式中的语义建模。AlgorandAdapter 的 `get_balance(addr)` 应返回 `{algo: int, assets: [{asset_id, amount}, ...]}` 复合结构,而 EthereumAdapter 返回 `int`。这是 adapter 接口签名差异,无法薄包装。

### 配置 JSON 示例(本链)

```json
{
  "chain": "algorand",
  "family": "algorand",
  "adapter": "AlgorandAdapter",
  "chain_id": "mainnet-v1.0",
  "genesis_hash_b64": "wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=",
  "endpoints": {
    "algod":   "https://mainnet-api.algonode.cloud",
    "indexer": "https://mainnet-idx.algonode.cloud"
  },
  "auth": {
    "header_name": "X-Algo-API-Token",
    "header_value_env": "ALGORAND_API_TOKEN",
    "required": false
  },
  "block_time_ms": 2800,
  "address_format": "algorand_base32_58",
  "rpc_methods": {
    "block_height":   {"verb": "GET", "path": "/v2/status",                        "node_role": "algod"},
    "balance":        {"verb": "GET", "path": "/v2/accounts/{address}",            "node_role": "algod"},
    "tx_lookup":      {"verb": "GET", "path": "/v2/transactions/{txid}",           "node_role": "indexer"},
    "tx_pending":     {"verb": "GET", "path": "/v2/transactions/pending/{txid}",   "node_role": "algod"},
    "block_query":    {"verb": "GET", "path": "/v2/blocks/{round}?format=json",    "node_role": "algod"},
    "asset_info":     {"verb": "GET", "path": "/v2/assets/{asset_id}",             "node_role": "algod"},
    "asset_balances": {"verb": "GET", "path": "/v2/assets/{asset_id}/balances?limit={limit}", "node_role": "indexer"},
    "account_txs":    {"verb": "GET", "path": "/v2/accounts/{address}/transactions?limit={limit}", "node_role": "indexer"},
    "tx_params":      {"verb": "GET", "path": "/v2/transactions/params",           "node_role": "algod"}
  },
  "mixed_weights": {
    "block_height":   0.05, "balance":        0.25, "tx_lookup":      0.20,
    "tx_pending":     0.05, "block_query":    0.10, "asset_info":     0.10,
    "asset_balances": 0.10, "account_txs":    0.10, "tx_params":      0.05
  }
}
```

---

## 11. DSL 字段需求(本链特殊!)

### 11.1 endpoints 字段(从 string 升级为 object)

DSL 必须从单一 `rpc_endpoint: string` 升级为 `endpoints: { algod, indexer }` 对象(或保留 `rpc_endpoint` 作 algod 别名 + 新增 `indexer_endpoint`)。**这是 28 链中首次出现的需求**,所有现有链均可写 `endpoints: { default: <url> }` 维持兼容。

### 11.2 auth.header_name 字段(header 名称可配置)

EVM 链普遍无鉴权或 `Authorization: Bearer`,Algorand 自部署节点用 `X-Algo-API-Token`,indexer 自部署用 `X-Indexer-API-Token`(可能不同 token)。DSL 必须支持 `auth: { header_name, header_value_env, required }`(env 变量名而非明文,符合 secret 管理)。Algonode 公共集群 `required: false`(E1 实证)。

### 11.3 address_format 新枚举值

`address_format` 枚举需新增 `"algorand_base32_58"`(对比现有 `base58 / hex / bech32 / near_account_id`)。校验(base32 解码 + SHA-512/256 checksum)由 AlgorandAdapter 完成,DSL 仅标签化。

### 11.4 native_decimals = 6(microalgo)

**容易出错**:DSL 已有此字段,但 Algorand 是 6 位(microalgo),Solana 是 9 位(lamports),EVM 是 18 位(wei),NEAR 是 24 位(yoctoNEAR)。Adapter 内部余额格式化必须按此字段动态转换。

### 11.5 chain_id 字符串化

`chain_id` 在 EVM 是数字(1, 56, 137),Algorand 是字符串(`"mainnet-v1.0"`),Cosmos 也是字符串(`"cosmoshub-4"`)。DSL `chain_id` 字段类型必须为 `string | number`(或全部 stringify)。本调研建议**全部 stringify**(向后兼容:EVM 链写 `"1"`,reader 端按需 `int()`)。

### 11.6 method-level path + query_params 模板

沿用 Cardano §11.3 / NEAR §11.5 已建立的 `rpc_methods.<name>.{verb, path, body_template, response_path}` schema,新增 `node_role` 字段(详 §11.8)。

### 11.7 Algorand algod + indexer 双节点表(强制必填)

| 维度 | **algod**(主节点)| **indexer**(历史查询节点)| E1 实测证据 |
|---|---|---|---|
| 默认端口(自部署)| `:4001`(REST API) | `:8980`(REST API) | ⚠ 未自部署,文档断言 |
| 公共端点(Algonode)| `https://mainnet-api.algonode.cloud` | `https://mainnet-idx.algonode.cloud` | ✅ §3.1 双侧 200 |
| 后端存储 | LevelDB / SQLite(节点本地 ledger) | **PostgreSQL**(由 indexer 进程从 algod 同步并索引) | ⚠ 文档断言,本调研未 ssh 节点验证 |
| 鉴权 header | `X-Algo-API-Token`(自部署默认开)/ Algonode 不强制 | `X-Indexer-API-Token`(自部署独立 token!)/ Algonode 不强制 | ✅ §3.2 任意 header 200 |
| 高度/探活 | `GET /v2/status` → `{"last-round":...}` | `GET /health` → `{"round":..., "version":...}` | ✅ §3.1 双侧 200 |
| balance(当前)| **`GET /v2/accounts/{addr}`** ✅ 含全部 ASA | `GET /v2/accounts/{addr}` ✅(同 path,但响应包 `account` 一层 + `current-round`) | ✅ T1+T2 均 200,响应结构有差(详 §11.7.1) |
| balance(历史) | ❌ 不支持(algod 只存当前 state) | `?round=N` 参数,**但 Algonode 免费层禁用**(`{"message":"rewinding account is no longer supported on free endpoints"}`) | ✅ T3 实测 HTTP 400 + 错误信息 |
| tx 直接查 | ❌ `GET /v2/transactions/{txid}` 返 **404** | ✅ `GET /v2/transactions/{txid}` 返 `{"transaction": {...}, "current-round": ...}` | ✅ T4+T6 实测 |
| tx pending / 最近 confirmed | ✅ `GET /v2/transactions/pending/{txid}`,**含 `~MaxAcctLookback round 窗口` 内的 confirmed tx(实测含已确认 tx)** | ❌ 无此 path | ✅ T5 实测含 `confirmed-round:61461400` 而 tx 不在 mempool |
| block 查询 | ✅ `GET /v2/blocks/{round}?format=json` | ✅ `GET /v2/blocks/{round}`(响应结构与 algod 略不同,带 indexer 元数据)| ✅ T7 algod 200 / 72KB |
| **account-tx 历史列表** | ❌ **404**(`/v2/accounts/{addr}/transactions`) | ✅ `GET /v2/accounts/{addr}/transactions?limit=N` | ✅ T15 indexer 200 / T16 algod 404 |
| **ASA 持有者列表** | ❌ 无 | ✅ `GET /v2/assets/{id}/balances?limit=N` | ✅ T10 实测 200,返 holder pagination |
| ASA 元数据 | ✅ `GET /v2/assets/{id}` | ✅ 同 path | ✅ T9 algod 200 / T17 indexer 200 |
| application(智能合约)元数据 | ✅ `GET /v2/applications/{id}` | ✅ 同 path | ⚠ 仅 indexer 侧 E1 实测(T 补充),algod 侧文档断言 |
| suggested tx params(发交易用)| ✅ `GET /v2/transactions/params` | ❌ 无 | ✅ T 补充实测返 `{"min-fee":1000, "genesis-hash":...}` |
| sync lag 风险 | 无(主节点 = 真相源) | **有**(indexer 从 algod 拉数据,可能落后 1–N rounds — `current-round` 字段反映 indexer 进度,可与 algod `last-round` 对比) | ⚠ 未触发实测,文档已说明 |

#### 11.7.1 同一 method 在两侧的响应结构差异(关键!)

```jsonc
// algod GET /v2/accounts/{addr}  → 顶层即 account 对象
{"address":"Q5WO...","amount":<microalgo>,"min-balance":...,"round":...,"assets":[...]}

// indexer GET /v2/accounts/{addr} → 包一层 + current-round
{"current-round":61461505,
 "account":{"address":"Q5WO...","amount":<microalgo>,"round":...,"assets":[...]}}
```

→ AlgorandAdapter 的 `parse_account` 必须根据 `node_role` 选择 unwrap 路径。**这是 DSL `response_path` 字段(参考 NEAR §11.5、Aptos §11.3 已建立的 JSONPath-lite)能解决的**:`algod.balance.response_path = "$.amount"`、`indexer.balance.response_path = "$.account.amount"`。

### 11.8 DSL 决策建议(关键产出 — 双节点表达方案)

**问题**:Algorand 是 28 链中首条需要客户端按 method 路由到不同 host(algod vs indexer)的链。DSL 必须显式表达这种路由,否则 vegeta target 生成器会把 `tx_lookup` 错发到 algod(返 404)而 `balance` 错发到 indexer(响应结构不同,parse 错位)。

#### 三方案对比

| 方案 | DSL 写法 | 改动量 | 兼容现有链 | 监控粒度 | 缺点 |
|---|---|---|---|---|---|
| **A `endpoint_alias` 字段(method 引用 endpoint 名)** | `endpoints: {algod, indexer}` + 每 method `endpoint: "algod" \| "indexer"` | 中(method 增 1 字段)| ✅(默认 = 唯一 endpoint 别名)| ✅(method 粒度自然)| `endpoint` 是 transport 概念,与 NEAR `logical_method`(语义概念)不在同一层 — 多链合在一起 schema 略乱 |
| **B `node_role` 字段(语义角色)**(本稿推荐) | `endpoints: {algod, indexer}` + 每 method `node_role: "algod" \| "indexer"`;adapter 用 `node_role → endpoints[node_role]` 映射 | 中(同 A;但字段名表达"语义角色"非"endpoint 别名")| ✅ 默认 `node_role: "default"` 映射 `endpoints.default` | ✅ | `node_role` 枚举与 family 绑(algorand 是 algod/indexer,其他链可能定义自家角色 — eos 是 nodeos/state-history,bitcoin 可能是 full/pruned)— schema 弱约束;**但语义最自洽** |
| **C adapter 内部完全隐藏(不入 DSL)** | DSL 仅写 `endpoints: {...}`;AlgorandAdapter 内部维护硬编码 `method → node_role` 映射 | 小(只 adapter 改) | ✅(其他链零改)| ✅ | **caller-blind 重灾区**:vegeta target 生成器无法静态得知该走哪个 endpoint,只能调 adapter — 违反 "DSL 是 declarative 输入" 的 Q4=C 95% 目标 |

#### 决策

- [ ] 方案 A `endpoint_alias`(transport 字段,泛化但语义弱)
- [x] **方案 B `node_role`(语义角色字段)** — **推荐**
- [ ] 方案 C(adapter 内部隐藏,DSL 简洁但 caller-blind)

#### 理由(3 段)

**第一段 — 方案 C 直接违反 Q4=C 95% 加链 0 Python 的核心目标**。本框架的终极目标是 `master_qps_executor.sh` + `mock_rpc_server.py` 全部从 declarative DSL 生成 vegeta target,不再为每条新链写 Python 路由。方案 C 把 `method → node_role` 映射藏在 AlgorandAdapter Python 代码里,意味着加 Algorand 后,vegeta target 生成器**必须在生成阶段反射调用 adapter 才能拿到 URL** — 这是 NEAR query dispatcher 问题(`08-near.md §11.7/11.8`)同样的 caller-blind 反模式。**否决**。

**第二段 — 方案 B 比方案 A 在语义上更自洽,在 schema 扩展性上同等**。方案 A 用 `endpoint_alias` 是把 endpoints 字典 key 直接作为 method 字段;方案 B 用 `node_role` 多一层间接,但**`node_role` 是"这个 method 应当问哪个角色的节点"的语义陈述**,与 `family: algorand` 的语义层级一致;`endpoints` 字典只是 `node_role` 的实例化(可由 user 在 mock/prod/multi-region 时切换不同 URL 而 `node_role` 不变)。具体好处:(1) prod 环境 user 可写 `endpoints: {algod: "https://my-prod-algod...", indexer: "https://my-prod-indexer..."}`,mock 环境写 `endpoints: {algod: "http://localhost:4001", indexer: "http://localhost:8980"}`,**method.node_role 不变**;(2) 当 Bitcoin / Eos / Polkadot 调研中可能出现自家 node_role 集合(如 bitcoin `full|pruned|electrum`)时,各 family 自定义 enum,DSL 仍统一字段名;(3) 监控 label 多一维 `node_role`,可天然出 "indexer p99 vs algod p99" 对比图(对运维直接有用)。

**第三段 — 兼容现有 7 条已上线链零成本 + 与 NEAR `logical_method` 字段共生不冲突**。现有 EVM 5 条 + Solana + Sui plugin 中 `endpoints` 写 `{default: "https://..."}`(或保留 `rpc_endpoint` 顶层字段,reader 等价转换为 `endpoints.default`),`node_role` 字段不填(默认 `"default"`),AlgorandAdapter 完整使用,其他 adapter 完全忽略 — token-level "局部新增 + 默认值兼容" 模式,与 NEAR `logical_method` 字段并列存在(`logical_method` 解 wire-method dispatcher,`node_role` 解 endpoint 路由,两者正交)。Phase 2.1 在 `config_loader.sh` 增 ~10 行解析,`mock_rpc_server.py` 增 path 路由(本来就需要),`fetch_active_accounts.py` 新建 `AlgorandAdapter` — 总改动 ~150 行,且零回归现有链。

**一句话结论**:**`endpoints: {algod, indexer}` + 每 method 可选 `node_role` 字段(默认 `"default"`)+ AlgorandAdapter 双 URL 路由 = Algorand 双节点架构的最小完备 DSL 表达。** ✅

---

## 11.9 真实信源覆盖与时间戳

| 信源 | URL/路径 | 访问日期(UTC)| 状态 |
|---|---|---|---|
| algod /versions | `GET https://mainnet-api.algonode.cloud/versions` | 2026-05-23 | **E1 HTTP:200 TIME:0.14s** — `genesis_id=mainnet-v1.0`,`genesis_hash_b64=wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=`,build major=4 |
| algod /v2/status | 同 host `/v2/status` | 2026-05-23 | **E1 HTTP:200 TIME:0.21s,last-round=61461471** |
| algod /v2/accounts/{snd} | `Q5WOHVUKNEM4XOVL725KH77WS6GODZSI4HTSWZAILM36ANSYVHW5RJI3KE` | 2026-05-23 | **E1 HTTP:200 TIME:0.15s SIZE:13022(含 ASA 持仓)** |
| algod /v2/transactions/pending/{txid}(已确认 tx)| txid 见 §7 | 2026-05-23 | **E1 HTTP:200 含 confirmed-round:61461400 — 反证 task context "only pending" 错误** |
| algod /v2/transactions/{txid}(直接)| 同 txid | 2026-05-23 | **E1 HTTP:404 Not Found — 实证 algod 无历史 tx 端点** |
| algod /v2/blocks/61461400 | `?format=json` | 2026-05-23 | **E1 HTTP:200 SIZE:71979** |
| algod /v2/assets/31566704(USDCa)| 同 host | 2026-05-23 | **E1 HTTP:200 — params.creator/decimals=6/name=USDC** |
| algod /v2/transactions/params | 同 host | 2026-05-23 | **E1 HTTP:200,min-fee=1000,genesis-hash 同 /versions** |
| algod /genesis | 同 host | 2026-05-23 | **E1 HTTP:200 SIZE:24973(完整 genesis,RewardsPool/FeeSink 地址)** |
| indexer /health | `https://mainnet-idx.algonode.cloud/health` | 2026-05-23 | **E1 HTTP:200 TIME:0.09s,version=3.9.0,db-available=true,round=61461471** |
| indexer /v2/accounts/{snd} | 同 host | 2026-05-23 | **E1 HTTP:200 SIZE:14167,响应包 account 一层(与 algod 不同 schema)** |
| indexer /v2/accounts/{snd}?round=61400000 | 历史余额尝试 | 2026-05-23 | **E1 HTTP:400 "rewinding account is no longer supported on free endpoints" — 重要 prod 约束** |
| indexer /v2/transactions/{txid} | 历史 tx | 2026-05-23 | **E1 HTTP:200,confirmed-round=61461400,current-round=61461505** |
| indexer /v2/accounts/{snd}/transactions?limit=3 | 账户交易列表 | 2026-05-23 | **E1 HTTP:200 SIZE:6090(indexer 独有)** |
| indexer /v2/assets/31566704/balances?limit=2 | ASA 持有者 | 2026-05-23 | **E1 HTTP:200 — balances[].address + next-token 分页** |
| indexer /v2/applications/1002541853 | 智能合约元数据 | 2026-05-23 | **E1 HTTP:200 SIZE:11035,含 TEAL approval-program base64** |
| Algonode 备用 Nodely host | `https://mainnet-api.4160.nodely.dev/v2/status` | 2026-05-23 | **E1 HTTP:200 TIME:0.20s(同样 200)** |
| 鉴权 header 三种探测 | no-header / Bearer / X-Algo-API-Token | 2026-05-23 | **E1 全部 HTTP:200 — 公共集群不校验** |
| 无效地址 checksum | task context 给的 DPLD3RZSY... | 2026-05-23 | **E1 HTTP:400 "checksum verification failed" — 反证 context 抄错** |
| 框架链命名空间 | `config/config_loader.sh:666` `supported_blockchains` | 2026-05-23 | **E1 read_file**:数组含 8 链,**未含 algorand,确认是新链** |

### 未实证 / 留 Phase 2.1

- ⚠ **自部署 algod `X-Algo-API-Token` 必填 header** — 文档断言,本调研无自部署 sandbox 实证
- ⚠ **indexer PostgreSQL 后端 disk I/O 特征** — 仅文档描述,Phase 2.1 自部署再验
- ⚠ **algod `MaxAcctLookback` 实际 round 窗口大小** — 仅推断为 1000 round,需 algod 配置文件验证
- ⚠ **indexer sync lag 实际数值** — 本调研实测时 algod.last-round=61461471 与 indexer.round=61461471 完全同步;高负载下 lag 待 Phase 2.1 长跑观察
- ⚠ **algod 公共端点 60 req/s 限流数值** — Algonode 文档断言,未触发限流(实测 ~20 req 全 200)
- ⚠ **付费层 indexer `?round=` 历史余额** — Algonode 免费禁用,付费层是否开启未验证

---

## Open Questions(待解决问题)

1. **`node_role` 字段还是 `endpoint_alias` 字段**(§11.8 方案 A vs B)— 最终命名由 user 在 Wave 3 review 拍板;本稿推荐 `node_role`(语义层)而非 `endpoint_alias`(transport 层)。
2. **DSL `endpoints` 是 object 还是 dict-list** — `{algod: url, indexer: url}` vs `[{name:algod, url:...}, ...]`;前者紧凑,后者扩展性强(可加 region/priority 字段)。本稿示例用 object,P1 review 可调整。
3. **`block_height` 是否拆 `algod_height` + `indexer_height` 双 method 以监控 sync lag**(§11.7 sync lag 列)— mixed 权重内是否值得加第 10 个 method 单独覆盖?
4. **历史余额 `?round=N` 支持** — Algonode 免费禁用,但 indexer 自部署/付费层支持。framework 是否需在 DSL 标 `feature_flag: historical_balance` 表达?
5. **`tx_lookup` mixed entry 的 txid 池来源** — vegeta target 需要真实 txid 池,从 `account_txs` 抓最近 N 笔?还是固定一组(本调研用的 `PO3UMN7...` 之类)?Phase 2.1 设计。
6. **ASA `asset_id` 池** — `asset_info` / `asset_balances` 需要真 asset_id 池(USDCa=31566704 仅 1 个),建议从 indexer `/v2/assets?limit=100` 拉 top assets 做池。
7. **mock_rpc_server 双端口模拟** — 是同进程不同 path prefix(`/algod/*` + `/indexer/*`)还是双进程?后者更真但需 framework 起 2 个 mock。
8. **AlgorandAdapter `get_balance(addr)` 返回类型** — 是只返 ALGO `int` 还是 `{algo, assets:[...]}` 复合(§10 第三段)?复合类型与 EthereumAdapter 接口不一致 — Phase 2.1 abstract base class 调整。
9. **`X-Indexer-API-Token` vs `X-Algo-API-Token` 是否同 secret** — 自部署默认是**两个独立 token**;DSL `auth` 字段是否需支持 per-endpoint 子配置(`auth: {algod: {...}, indexer: {...}}`)?
10. **Algorand application(智能合约)在 mixed 中的覆盖** — 当前 §8 权重未含 application 调用(`POST /v2/teal/dryrun` 等),Wave 3+ 是否加?

---

## Changelog

| 日期(UTC)| 作者 | 变更 |
|---|---|---|
| 2026-05-23 | Hermes Agent | 初稿(Phase 1.2 Wave 3):**18 条 curl E1 实证**(algod + indexer 全部 method);**反证** task context 中 "tx pending only" 与 "Algorand foundation 地址 checksum" 两处错误;§11.7 双节点能力差异表(15 行)+ §11.8 三方案对比 + **决策 = 方案 B `node_role` 字段(可选)+ AlgorandAdapter 双 URL 路由**;新建 `AlgorandAdapter`(新 family `algorand`);列 8 项 Phase 2.1 caller/reader 改造点(§8.5)+ 10 个 Open Questions |
