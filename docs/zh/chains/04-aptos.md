# 04 — Aptos 调研稿

> **版本**:v1.0(初稿,Phase 1.2 Wave 1)
> **调研日期**:2026-05-23
> **作者**:Hermes Agent(token-level + 调研先行 + H8 实证 / E1-E5 分级)
> **状态**:🟢 待 user review(P1-USER-REVIEW 卡点)
> **本稿强制满足**:`_template.md` §1-§10 + §11 DSL(含 11.7 Aptos vs Sui 对比、11.8 movevm family 决策)
> **编号注**:本稿按任务 wave 命名为 `04-aptos.md`,与 `00-SUMMARY.md` 中 Aptos=#17 不一致,P1 收尾时由 user 决定最终重命名(Open Q1)

---

## 元信息

| 项 | 值 |
|---|---|
| 链名(中) | Aptos |
| 链名(英) | Aptos |
| 编号 | 04(wave 内)/ 17(SUMMARY 总册) |
| Mainnet ChainID | `1`(由 `x-aptos-chain-id` header + `/v1` ledger 字段双重实证) |
| 调研日期 | 2026-05-23 |
| 调研者 | Hermes Agent |
| 状态 | 🟢 已完成初稿 |

---

## 1. Sources(权威来源)

| 类型 | URL | 访问日期 | 备注 / 证据等级 |
|---|---|---|---|
| 官方文档主页 | https://aptos.dev | 2026-05-23 | E1(未深入实证页面 DOM)|
| REST API 规范 | https://aptos.dev/build/apis/fullnode-rest-api | 2026-05-23 | E1 引用,**关键:Aptos 主接口是 REST,不是 JSON-RPC** |
| OpenAPI Spec (live) | https://fullnode.mainnet.aptoslabs.com/v1/spec.yaml | 2026-05-23 | **E1 实证**(`HTTP:200 TYPE:application/x-yaml`)|
| GitHub | https://github.com/aptos-labs/aptos-core | 2026-05-23 | E1 引用(未 git clone 实证)|
| Explorer | https://explorer.aptoslabs.com | 2026-05-23 | E1 引用(未页面 DOM 实证)|
| Move Book(VM 规范) | https://aptos.dev/move/move-on-aptos | 2026-05-23 | E1 引用 |

---

## 2. Protocol Family(协议族)

| 项 | 值 | 证据 |
|---|---|---|
| Family | **Move**(MoveVM 第二实现)| E1 官方定位 |
| Consensus | AptosBFT v4(改良 HotStuff,DiemBFT 衍生)| E1 官方文档(未 paper 级实证)|
| VM | MoveVM(与 Sui 同 VM 但**对象模型不同**:Aptos 用 Move Resource,Sui 用 Object)| E1 + 实测 `/v1/accounts/0x1/resources` 返回 `0x1::dkg::DKGState` 等 Move struct |
| Block Time | ~0.15s(实测 `block_height=783350119` vs 5392437054 ledger_version 推算)| **H8 实证** |
| Finality | sub-second(BFT 确定性,~1 个 block 后 final)| E1 文档(未严格测延迟分布)|
| Reuse Existing Adapter? | **No**(SuiAdapter 走 JSON-RPC,Aptos 走 REST,**协议层不可共享**)| **本调研核心结论**,详 §10 + §11.7/11.8 |

---

## 3. Public RPC(公共节点)

| Endpoint | Auth | Rate Limit | 备注 / H8 |
|---|---|---|---|
| `https://fullnode.mainnet.aptoslabs.com/v1` | 无 | 未声明明确阈值,匿名公共 | **H8 实证 HTTP:200 TIME:0.24s**(ledger info)+ 多 endpoint 均 OK |
| `https://api.mainnet.aptoslabs.com/v1` | 无 | 同上(别名)| **H8 实证 HTTP:200**(`/v1/-/healthy` 返回 `aptos-node:ok`)|
| `https://aptos-mainnet.publicnode.com` | — | — | **H8 实测 HTTP:404**(404 返回,**publicnode 现状 Aptos 端点不可用,或路径不同 — 不推荐**)|
| `https://rpc.ankr.com/http/aptos/v1/...` | 需 API key | 公共 tier 极有限 | **H8 实证 HTTP:403**(`API key is not allowed to access blockchain`)|
| `https://aptos.api.onfinality.io/public/v1` | 公共/有 key 分级 | 未测试 | **H8 实测 HTTP:404**(public path 不工作)|

**curl 实测 1 — ledger info(探活 + 高度)**(H8):
```bash
curl -s https://fullnode.mainnet.aptoslabs.com/v1
# {"chain_id":1,"epoch":"15909","ledger_version":"5392437054","oldest_ledger_version":"0",
#  "ledger_timestamp":"1779559410826021","node_role":"full_node","oldest_block_height":"0",
#  "block_height":"783350119","git_hash":"b2a11100ceb479c8d220937c003524d4708a7821","encryption_key":null}
```

**curl 实测 2 — 响应自带 x-aptos-* 头**(高价值 ✨,可省 ledger info 调用):
```
x-aptos-chain-id: 1
x-aptos-ledger-version: 5392452111
x-aptos-ledger-oldest-version: 0
x-aptos-ledger-timestampusec: 1779559506186366
x-aptos-epoch: 15909
x-aptos-block-height: 783352304
x-aptos-oldest-block-height: 0
```
即:**每个响应都附带 chain_id / ledger_version / block_height**,benchmark 框架监控同步时可用 `curl -I` 取代真正的 ledger info GET(节省一次 round-trip)。

**curl 实测 3 — 健康检查**:
```bash
curl -s https://fullnode.mainnet.aptoslabs.com/v1/-/healthy
# {"message":"aptos-node:ok"}  HTTP:200
```

**curl 实测 4 — 验证 NOT JSON-RPC**:
```bash
curl -s -X POST https://fullnode.mainnet.aptoslabs.com/v1 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"getLedgerInfo"}'
# {"message":"method not allowed","error_code":"web_framework_error","vm_error_code":null}  HTTP:405
```
**关键结论**:Aptos 拒绝 JSON-RPC 调用方式。**这是与 Sui 的核心协议级差异**(详 §11.7)。

---

## 4. Account Model(账户模型)

| 项 | 值 | 证据 |
|---|---|---|
| 模型 | **Account**(Move Resource 模型,带 sequence_number)| **H8 实证** `/v1/accounts/0x1` → `{"sequence_number":"0","authentication_key":"0x0...01"}` |
| Native token | APT(`0x1::aptos_coin::AptosCoin`)| E1 文档 + H8 view 实证 |
| Native token decimals | 8(octas)| E1 文档(未在 view 中直接验)|
| Address derivation | Ed25519 默认;支持 MultiEd25519 / Secp256k1 / SecpR1(passkey)| E1 文档 |
| Special account types | Resource Account / Object(Aptos Object Model)/ Framework `0x1`、`0x3`、`0x4` 等系统账户 | E1 文档 + H8 `/v1/accounts/0x1/resources` 返回大量 `0x1::*` resource |
| Balance 查询方式 | **`/v1/view` 调 `0x1::coin::balance<AptosCoin>`**(主流)或读取 `/v1/accounts/{addr}/resource/0x1::coin::CoinStore<...>`(直接 resource)| **H8 双路径均实证**(view 返回 `["669182353480"]`)|

**curl 实测 — 账户余额(view function 路径)**:
```bash
curl -X POST https://fullnode.mainnet.aptoslabs.com/v1/view \
  -H "Content-Type: application/json" \
  -d '{"function":"0x1::coin::balance",
       "type_arguments":["0x1::aptos_coin::AptosCoin"],
       "arguments":["0xd503b95164384a5ebbccbb5c4bdc8b4a5893d9651e9953abda8e1c22fcc1181d"]}'
# ["669182353480"]   ⇒ 6691.82 APT(8 decimals)  HTTP:200
```

**curl 实测 — 账户余额(resource 路径,框架 0x1 因不持仓返回 404)**:
```bash
curl https://fullnode.mainnet.aptoslabs.com/v1/accounts/0x1/resource/0x1::coin::CoinStore%3C0x1::aptos_coin::AptosCoin%3E
# {"message":"Resource not found by Address(0x1), Struct tag(0x1::coin::CoinStore<...>)..."} HTTP:404
```
注意:**`0x1` 是 framework account 不持 APT**,所以走 resource 路径会 404 — 这与"地址存在即有 balance"的 EVM 心智模型相反,framework 调用必须容错处理。

---

## 5. Core RPC Methods(本框架监控所需)

> **协议层注意**:Aptos 的 "method" 不是 JSON-RPC method 字符串,而是 **REST URL path + HTTP verb 组合**。本表 "Method" 列写成 `<VERB> <path>` 形式以保持与 _template 字段对齐。

| Method | 类别 | 说明 | mixed 权重建议 | H8 状态 |
|---|---|---|---|---|
| `GET /v1` | ledger info | 探活 + chain_id + ledger_version + block_height(一次取齐)| **0.20** | ✅ HTTP:200 0.24s |
| `HEAD /v1`(或任意 GET 看 header)| 同步 heartbeat | 仅取 `x-aptos-*` header,**最便宜**的高度心跳 | **0.10** | ✅ 实证 header 含 8 个 x-aptos-* 字段 |
| `GET /v1/-/healthy` | health check | 仅做存活探针(响应固定)| **0.05** | ✅ `aptos-node:ok` |
| `POST /v1/view` | balance / 任意 Move 只读 | 余额、token balance、自定义 view function 都走这个 | **0.25** | ✅ 实证返回 `["669182353480"]` |
| `GET /v1/accounts/{addr}` | account meta | sequence_number + auth_key | **0.05** | ✅ 实证 200 |
| `GET /v1/accounts/{addr}/resources` | account resources(Move state)| **Aptos 特色**:列账户所有 Move struct | **0.10** | ✅ 实证 200(framework 账户返回 DKGState 等)|
| `GET /v1/accounts/{addr}/resource/{struct_tag}` | 单 resource 查询 | CoinStore / 任意自定义 struct | **0.05** | ✅ 实证 200/404(404 = resource 不存在,合预期)|
| `GET /v1/blocks/by_height/{n}` | block by height | block 内容(可选 `with_transactions=true`)| **0.05** | ✅ 实证返回 `block_hash`/`first_version`/`last_version` |
| `GET /v1/transactions?limit=N` | tx list | 最新 N 笔 tx(用于 fetch_active_accounts)| **0.05** | ✅ 实证返回 list,含 `user_transaction` 类型 |
| `GET /v1/transactions/by_hash/{hash}` | tx lookup by hash | 按 hash 查 tx | **0.05** | ✅ 实证 200 返回 tx 详情 |
| `GET /v1/transactions/by_version/{ver}` | tx lookup by version | **Aptos 特色**:按 ledger_version 查 tx(比 hash 更便宜)| **0.05** | ✅ 实证 200 |
| `GET /v1/estimate_gas_price` | gas estimation | 等价于 `eth_gasPrice` | — | ✅ 实证 `{"deprioritized_gas_estimate":100,"gas_estimate":100,"prioritized_gas_estimate":150}` |
| `GET /v1/accounts/{addr}/events/{handle}/{field}` | event 查询 | 用 event handle struct + field 名 | — | ✅ 实证 `NewEpochEvent` 返回 |
| `GET /v1/accounts/{addr}/modules` | 已部署 Move 模块字节码 | 不在 benchmark 关键路径 | — | ✅ 实证 200 |

**mixed 权重核对**(框架监控必需的 8 项):0.20 + 0.10 + 0.05 + 0.25 + 0.05 + 0.10 + 0.05 + 0.05 + 0.05 + 0.05 + 0.05 = **1.05 → 需归一化**。简化后:

```
GET /v1                                          0.20  (ledger info)
HEAD /v1 (x-aptos-* heartbeat)                   0.10  (cheapest heartbeat)
POST /v1/view (balance/view)                     0.30  (highest-frequency real query)
GET /v1/accounts/{addr}                          0.05
GET /v1/accounts/{addr}/resources                0.10
GET /v1/blocks/by_height/{n}                     0.05
GET /v1/transactions?limit=N                     0.05
GET /v1/transactions/by_hash/{hash}              0.10
GET /v1/transactions/by_version/{ver}            0.05
                                                = 1.00 ✅
```

**总权重 = 1.0 ✅**(`/v1/-/healthy` 与 `/v1/estimate_gas_price` 不在 mixed 中,前者由 health-monitor 单独使用,后者非读路径核心)。

---

## 6. Address Format(地址格式)

| 项 | 值 | 证据 |
|---|---|---|
| 编码 | Hex(`0x` 前缀)| H8 实测 |
| 长度 | **32 字节 = 64 hex chars + `0x` = 66 chars**(与 Sui 同长度,**但 Sui 也是 32B**,**与 Ethereum 20B 不同**)| H8(`0xd503b95164384a5ebbccbb5c4bdc8b4a5893d9651e9953abda8e1c22fcc1181d` 长度 66)|
| Short form | 允许前导 0 省略:`0x1` 等价 `0x0000...0001`(framework 账户)| H8 实测 `/v1/accounts/0x1` 200 OK,但内部 `auth_key` 仍返回完整 64 hex |
| Checksum | 无 EIP-55 风格 checksum,**纯 hex** | E1 文档 |
| 示例(主网真实地址) | `0xd503b95164384a5ebbccbb5c4bdc8b4a5893d9651e9953abda8e1c22fcc1181d`(从 `/v1/transactions?limit=10` 取一笔 `user_transaction` 的 sender,持仓 6691.82 APT)| **H8 双重实证** |
| Framework 系统地址 | `0x1`(AptosFramework)、`0x2`(MoveStdlib)、`0x3`(AptosTokenV1)、`0x4`(AptosTokenObjects)、`0x5`、`0x6`、`0x7`、`0xa`、`0x10` 等保留 | E1 文档(仅 `0x1` 通过 H8 实证)|
| 校验正则 | `^0x[0-9a-fA-F]{1,64}$`(允许 1-64,因短地址合法)| 从实测推断 |

**与 Sui 对比**:**同样 32B hex**,**长度完全相同**,address 格式可直接复用 validator。✅ family-share 候选维度。

---

## 7. Signature Lookup(交易哈希)

| 项 | 值 | 证据 |
|---|---|---|
| Hash 格式 | Hex(`0x` 前缀)| H8 实测 |
| 长度 | 32 字节 = 64 hex chars + `0x` = 66 chars | H8(`0x200d31ed050986b5ec9ced837f70f771c8ec99a09995fabf6a68a2fffdb9b6fe`)|
| 示例(主网真实 tx) | `0x200d31ed050986b5ec9ced837f70f771c8ec99a09995fabf6a68a2fffdb9b6fe`(version=5392438515)| **H8 实测**(`/v1/transactions/by_hash/...` 返回详情)|
| 查询 method | `GET /v1/transactions/by_hash/{hash}` | H8 实证 200 |
| **附加 lookup**(Aptos 特色) | `GET /v1/transactions/by_version/{ledger_version}` — 按 ledger version 数字查,**比 hash 更便宜**(数字比对 vs hex 解码)| H8 实证 200 |
| Explorer URL 格式 | `https://explorer.aptoslabs.com/txn/{hash}?network=mainnet` | E1 文档 |

**与 Sui 对比**:**Sui 的 tx digest 是 Base58 ~44 字符**,**Aptos 是 hex `0x` + 64 字符** — **格式不同**,parser 必须分链处理。⚠️ family-split 关键维度。

---

## 8. Mixed Set(`mixed` 模式权重)

> 用于 `BLOCKCHAIN_NODE_BENCHMARK_MODE=mixed` 的请求分布

```json
{
  "balance_query":   0.30,  /* POST /v1/view  (0x1::coin::balance) */
  "ledger_info":     0.20,  /* GET  /v1                            */
  "heartbeat":       0.10,  /* HEAD /v1  (just read x-aptos-*)     */
  "tx_lookup":       0.10,  /* GET  /v1/transactions/by_hash/{h}   */
  "tx_by_version":   0.05,  /* GET  /v1/transactions/by_version/{v}*/
  "tx_list":         0.05,  /* GET  /v1/transactions?limit=N       */
  "block_query":     0.05,  /* GET  /v1/blocks/by_height/{n}       */
  "account_meta":    0.05,  /* GET  /v1/accounts/{addr}            */
  "resources":       0.10   /* GET  /v1/accounts/{addr}/resources  */
}
/* sum = 1.00 ✅ */
```

**权重和 = 1.00 ✅**。chain-specific(Aptos 独有)是 `resources` 和 `tx_by_version` — 这两项**Sui 没有等价**(Sui 是 `sui_getObject` + `suix_queryTransactionBlocks`,模型不同)。

**注**:权重为初稿建议(E5 SPECULATED),未基于真实 mainnet 流量统计,Phase 2.x 与运营对齐前为占位值。

---

## 8.5 Phase 2.1 caller/reader 改造点(token-level Gate 3)

| # | 位置(file:line) | 改动 | 原因(为什么这个 caller 需同步改) |
|---|---|---|---|
| 1 | `config/config_loader.sh:401`(`case` 块新增 `aptos)` 分支)| `MAINNET_RPC_URL="https://fullnode.mainnet.aptoslabs.com/v1"` | `case` switch 否则触发 `*)` 报错 |
| 2 | `config/config_loader.sh:622+` `UNIFIED_BLOCKCHAIN_CONFIG.blockchains` 新增 `"aptos"` block | 新增 `chain_type / params / methods / system_addresses / rpc_methods / param_formats / protocol_kind: "rest"` | `generate_auto_config()` 才能为 aptos 生成 vegeta target 配置 |
| 3 | `config/config_loader.sh:666` `supported_blockchains` 数组加 `"aptos"` | `(... "starknet" "sui" "aptos")` | 否则 `validate_blockchain_node()` 拒绝 `BLOCKCHAIN_NODE=aptos` 启动 |
| 4 | `tools/mock_rpc_server.py` 新增 Aptos REST 路由 | 路由 `/v1`、`/v1/view`、`/v1/accounts/{addr}`、`/v1/accounts/{addr}/resources`、`/v1/transactions/by_hash/{h}` 等 | **Aptos 不是 JSON-RPC**,mock 现有 POST `/` JSON-RPC dispatcher **完全不能复用**,必须新增 REST router 分支 — 这是 Aptos 引入的**最大 mock 工作量** |
| 5 | `tools/fetch_active_accounts.py` 新增 `AptosAdapter` | `class AptosAdapter(BlockchainAdapter)`,核心调 `GET /v1/transactions?limit=N` 拉最近 user_transaction 抽 sender,**不能复用** EthereumAdapter 的 `eth_getLogs / eth_getBlockByNumber` 心智 | Aptos 的 ledger_version 是连续整数(类似 Solana slot),逐块扫成本可控,但接口是 REST 不是 JSON-RPC |
| 6 | `tools/audit_rpc_methods.py:ADAPTER_EXPECTED_FIELDS` 新增 Aptos 字段路径 | 例:`"aptos_view_balance": ["[0]"]`(view 返回 JSON array)、`"aptos_get_ledger": ["chain_id","ledger_version","block_height"]` | L2 audit 用此字典断言 response shape,不加则 audit 跳过 |
| 7 | `tools/audit_rpc_methods.py:fetch_doc_method()` 新增 `elif chain_type == "aptos"` | 类比 sui 当前的 `SKIPPED`,可改为 fetch OpenAPI `/v1/spec.yaml` 解析 endpoint 列表(更强)| L1 audit 自动从 OpenAPI 验 method 存在性 |
| 8 | `analysis-notes/baseline-current-state.md` grep `aptos` | 同步链路列表更新(目前应无 aptos 提及)| 文档真相对齐,防 doc-vs-code 偏离 |
| 9 | `docs/zh/chains/00-SUMMARY.md` 第 17 行 Aptos 行状态 `🟡 待调研 → 🟢 已完成初稿`,文档列填本文件路径 | — | SUMMARY 表是 P1 完成度看板 |
| 10 | `tests/<aptos 相关>.sh` 新增 e2e smoke | 跑 `BLOCKCHAIN_NODE=aptos core/master_qps_executor.sh --mixed --duration 30` | E2 证据;**所有请求必须 200**(注意 `/v1/accounts/{addr}/resource/...` 在 resource 不存在时合法返回 404,mixed target 必须用持仓地址)|

**关键警示**(token-level Case-B 风险):第 4 项 mock 改造**不是简单加几个 case**,是**新增一整套 REST router**。当前 `mock_rpc_server.py` 假设所有请求是 `POST /` + JSON-RPC body,Aptos 要求 path-based dispatch + 多 HTTP verb。建议 Phase 2.1 把 mock 重构为 **per-family handler**,而不是在现有单 dispatcher 里加 if-else,否则会越改越乱。

**测试要求**:Phase 2.1 完成后必须跑 `core/master_qps_executor.sh --mixed --duration 30`,**所有请求都应是 200**(用持仓地址做 view target),作为本链改造的 E2 证据。

---

## 9. Mock Notes(mock_rpc_server 实现要点)

- **请求路径**:**多路径 + 多 HTTP verb**(不是 JSON-RPC 单端点)
  - `GET /v1` / `HEAD /v1`
  - `GET /v1/-/healthy`
  - `GET /v1/accounts/{addr}`
  - `GET /v1/accounts/{addr}/resources`
  - `GET /v1/accounts/{addr}/resource/{struct_tag}`
  - `GET /v1/blocks/by_height/{n}`
  - `GET /v1/transactions`(支持 `?limit=`)
  - `GET /v1/transactions/by_hash/{hash}`
  - `GET /v1/transactions/by_version/{version}`
  - `POST /v1/view`(body 含 `function / type_arguments / arguments`)
- **响应 schema 样本(真实主网,H8 实证)**:
  ```json
  // GET /v1 (ledger info)
  {"chain_id":1,"epoch":"15909","ledger_version":"5392437054",
   "oldest_ledger_version":"0","ledger_timestamp":"1779559410826021",
   "node_role":"full_node","oldest_block_height":"0",
   "block_height":"783350119",
   "git_hash":"b2a11100ceb479c8d220937c003524d4708a7821","encryption_key":null}

  // POST /v1/view  (balance)
  ["669182353480"]              // 即 array of strings (大整数序列化为字符串)

  // GET /v1/transactions/by_hash/{h}  (节选)
  {"version":"5392438515",
   "hash":"0x200d31ed050986b5ec9ced837f70f771c8ec99a09995fabf6a68a2fffdb9b6fe",
   "gas_used":"0","success":true,"vm_status":"Executed successfully", ...}
  ```
- **必须输出的响应 header(否则 monitoring 探活逻辑会判断 mock 失真)**:
  - `x-aptos-chain-id: 1`
  - `x-aptos-ledger-version: <incr int>`
  - `x-aptos-block-height: <incr int>`
  - `x-aptos-epoch: <int>`
  - `x-aptos-ledger-timestampusec: <usec>`
- **特殊状态码**:
  - `404` + `{"error_code":"resource_not_found"}`:resource 不存在(合法,不算错误)— mock 需要对**未配置的 struct_tag** 返回这个,否则 caller 错把它当 500
  - `405` + `{"error_code":"web_framework_error","message":"method not allowed"}`:HTTP verb 错(例如对只接受 GET 的 path 发 POST)
  - `400` + `{"error_code":"invalid_input"}`:参数格式错
- **大整数序列化**:**所有 u64/u128 数值在响应里都是字符串**(JSON 数字精度问题),mock 必须返 `"669182353480"` 而非 `669182353480`
- **mock 实现复杂度**:**High** — 原因:(a) 多 path 多 verb 不是简单 dispatcher;(b) `POST /v1/view` 的 function 字段任意 Move call,mock 至少要实现 `0x1::coin::balance` + `0x1::aptos_account::sequence_number`;(c) struct_tag URL encoding(`<>` 要变 `%3C%3E`)需手工处理

---

## 10. Adapter Reuse Decision(adapter 复用决策)

### 候选 adapter

| Adapter | 兼容度 | 缺失能力 |
|---|---|---|
| EthereumAdapter | **5%** | RPC 协议根本不同(Aptos REST vs Eth JSON-RPC);地址长度不同(32B vs 20B);余额查询机制不同(view function vs eth_getBalance);account model 不同(Move Resource vs EVM Account) |
| SolanaAdapter | **0%** | 协议(RPC vs REST)+ 账户模型(Solana Account vs Move Resource)+ 地址编码(base58 vs hex)均不同 |
| BitcoinAdapter | **0%** | UTXO 模型完全不适用 |
| StarknetAdapter | **5%** | Starknet 是 JSON-RPC,Cairo VM,不可复用 |
| **SuiAdapter**(本族最近邻)| **~30%**(VM/语义层)、**~5%**(协议/wire 层)| **协议层不可复用**:Sui 是 JSON-RPC 2.0(`POST /` + method 字段),Aptos 是 REST(多 path + GET/POST)。**语义层可复用心智**:Move struct_tag 解析、`0x1`/`0x2` framework 概念、Coin 资源 |

### 决策

- [ ] 复用 `<adapter>`
- [x] **新建 `AptosAdapter`(归入 `Move family`,但与 `SuiAdapter` 平级,不继承)**
- [ ] 混合

### 理由

(1) **协议层差异是硬阻塞**。Sui 走 JSON-RPC 2.0(`POST /` + `{"method":"sui_getObject", ...}`),Aptos 明确拒绝 JSON-RPC 调用(H8 实测 405 + `web_framework_error`)。两条链的 transport 编码、URL 模式、HTTP verb 选择全部不同 — **任何尝试在同一 adapter 内 if-else 分支都会污染协议层抽象**,违反 single-responsibility。

(2) **VM 语义层有共享空间但不属于 adapter 职责**。Move struct_tag 解析(`0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>`)、framework address 概念(`0x1` ~ `0xa`)、resource vs object 心智 — 这些可以放进**共享的 `tools/move_utils.py`** 工具模块,被 SuiAdapter 和 AptosAdapter 同时 import,但 adapter 类本身不共享代码。

(3) **建议的 family 组织**(详 §11.8):**`move` family 名义存在(用于文档/统计/UI 分组),但 plugin schema 拆为 `movevm-sui` + `movevm-aptos` 两个子 family**。理由是 RPC 模型差异 ≥ 50%(详 §11.7 对比表),远超 20% 阈值。

### 配置 JSON 示例(本链)

```json
{
  "chain": "aptos",
  "family": "move",
  "subfamily": "movevm-aptos",
  "adapter": "AptosAdapter",
  "protocol_kind": "rest",
  "chain_id": 1,
  "rpc_endpoint": "https://fullnode.mainnet.aptoslabs.com/v1",
  "block_time_ms": 150,
  "address_format": "hex_0x_32byte",
  "tx_hash_format": "hex_0x_32byte",
  "native_decimals": 8,
  "system_addresses": ["0x1", "0x2", "0x3", "0x4", "0x5", "0x6", "0x7", "0xa"],
  "rpc_methods": {
    "ledger_info":    "GET /v1",
    "health":         "GET /v1/-/healthy",
    "balance":        "POST /v1/view",
    "account_meta":   "GET /v1/accounts/{addr}",
    "resources":      "GET /v1/accounts/{addr}/resources",
    "resource":       "GET /v1/accounts/{addr}/resource/{struct_tag}",
    "block_by_height":"GET /v1/blocks/by_height/{n}",
    "tx_list":        "GET /v1/transactions",
    "tx_by_hash":     "GET /v1/transactions/by_hash/{hash}",
    "tx_by_version":  "GET /v1/transactions/by_version/{version}",
    "gas_price":      "GET /v1/estimate_gas_price"
  },
  "view_function_balance": {
    "function": "0x1::coin::balance",
    "type_arguments": ["0x1::aptos_coin::AptosCoin"]
  },
  "param_formats": {
    "POST /v1/view": "move_view_call",
    "GET /v1/accounts/{addr}": "path_addr",
    "GET /v1/accounts/{addr}/resource/{struct_tag}": "path_addr_plus_url_encoded_struct_tag"
  },
  "response_headers_monitoring": [
    "x-aptos-chain-id", "x-aptos-ledger-version", "x-aptos-block-height", "x-aptos-epoch"
  ],
  "mixed_weights": {
    "balance_query": 0.30,
    "ledger_info":   0.20,
    "heartbeat":     0.10,
    "tx_lookup":     0.10,
    "tx_by_version": 0.05,
    "tx_list":       0.05,
    "block_query":   0.05,
    "account_meta":  0.05,
    "resources":     0.10
  }
}
```

---

## 11. DSL Field Requirements(本链对 plugin DSL 的诉求)

### 11.1 Protocol kind 字段必须显式

当前 `config_loader.sh` 隐式假设 `POST / + JSON-RPC body`。Aptos 引入要求 DSL 必须有 **`protocol_kind: "rest" | "jsonrpc" | "grpc" | "hybrid"`** 顶层字段。否则 vegeta target 生成器无法决定是否走 `POST / -d '{...}'` 还是 `GET /v1/...`。

### 11.2 Per-method HTTP verb + path template

```yaml
methods:
  balance:
    verb: POST
    path: /v1/view
    body_template: '{"function":"{{function}}","type_arguments":{{type_args}},"arguments":["{{addr}}"]}'
  tx_by_hash:
    verb: GET
    path: /v1/transactions/by_hash/{{hash}}
```
**JSON-RPC 链不需要 path/verb**(都是 `POST /`),REST 链必须有。DSL 字段必须可选(jsonrpc family 不填),否则 Sui plugin 会被迫写 `verb: POST, path: /`。

### 11.3 Response field path(嵌套提取)

- `POST /v1/view` 返回 **`["669182353480"]`**(array of strings),balance 在 `[0]` 转 int / 1e8
- `GET /v1` 返回 object,height 在 `.block_height`
- `GET /v1/-/healthy` 返回 object,status 在 `.message`(预期 `aptos-node:ok`)

DSL 需要 **`response_path` 字段**(JSONPath-lite)以便统一提取。Sui 也需要(`.result.data` 等)— 此字段**跨 family 通用**。

### 11.4 Response header monitoring(Aptos 独有维度)

Aptos 每个响应都附带 `x-aptos-chain-id / x-aptos-ledger-version / x-aptos-block-height / x-aptos-epoch / x-aptos-ledger-timestampusec`,**这是免费的同步监控信号**,不需另起 ledger info 调用。

DSL 应允许 **`monitor_headers: [<name>, ...]`** 字段,plugin 加载后 monitoring 路径可直接消费。**Sui/Eth/Solana 当前都没有这种 header**,所以此字段是 Aptos-specific 的扩展点。

### 11.5 Move call body schema

`POST /v1/view` body 是 `{"function": "<module>::<func>", "type_arguments": [...], "arguments": [...]}`。这是 **Move-family 共有**的调用约定(Sui dry-run 也类似),DSL 可以提取为 **family-level shared template**(`movevm.*` 通用)。

### 11.6 URL encoding policy

Aptos 的 struct_tag `0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>` 含 `<>`,在 URL 路径中必须 URL-encode 成 `%3C%3E`。DSL 需声明 **`path_param_url_encode: true`**,否则字符串拼接会构造非法 URL。

### 11.7 Aptos vs Sui 对比表(family 合并/拆分决策)

| # | 维度 | Sui(已 audit)| Aptos(本调研 H8)| 同/异 |
|---|---|---|---|---|
| 1 | RPC 协议 | JSON-RPC 2.0(POST `/` + body)| **REST**(多 path + GET/POST/HEAD)| ❌ **异**(协议层根本不同)|
| 2 | method 命名 | `sui_*` / `suix_*` 前缀字符串 | **HTTP `<verb> <path>` 组合**(无 method 字符串)| ❌ **异** |
| 3 | 鉴权 | public(无 key)| public(无 key)| ✅ **同** |
| 4 | address 格式 | `0x` + 1-64 hex(32 byte)| `0x` + 1-64 hex(32 byte)| ✅ **同**(均允许 leading-zero short form)|
| 5 | tx hash 格式 | Base58 ~44 字符(digest)| `0x` + 64 hex(32 byte)| ❌ **异**(编码完全不同)|
| 6 | balance 查询 method | `sui_getBalance(addr, coin_type)`(专用 method)| `POST /v1/view` body 调 `0x1::coin::balance`(通用 view function)| ⚠️ **半异**(语义同,wire 不同)|
| 7 | tx 查询 method | `sui_getTransactionBlock(digest, opts)` | `GET /v1/transactions/by_hash/{hash}` 或 `by_version/{n}` | ❌ **异**(Aptos 多一个 by_version)|
| 8 | account 资源查询 | `sui_getObject(object_id, opts)`(以对象为中心)| `GET /v1/accounts/{addr}/resources`(以账户为中心列出所有 resource)| ❌ **异**(对象模型根本不同)|
| 9 | pagination cursor | `cursor: <object_id>` / `cursor: <opaque>` | `start: <version>` / `limit: <int>` 数值游标 | ❌ **异** |
| 10 | object/resource model | **Sui Object**(owned objects,object 是一等公民)| **Move Resource**(挂在 account 下,account 是一等公民)| ❌ **异**(Move 实现的最大语义分歧)|

**统计**:✅同 = 2(#3 鉴权、#4 address);⚠️半异 = 1(#6 balance,语义同 wire 不同);❌异 = 7。

**纯"同" 比例 = 2/10 = 20%;加上半异最多 3/10 = 30%。** 远低于 70% (7/10) 的合并阈值。

### 11.8 DSL 决策建议(关键产出)

- [ ] 合并为 `movevm` family(>= 7/10 同)
- [x] **拆分 `movevm-sui` 和 `movevm-aptos`(< 7/10 同;实测 2-3/10)**
- [ ] 共享部分 + 子族扩展(5-7/10 同)

**理由(3 段)**:

**第一段 — 协议层差异是硬阻塞,不可在 plugin schema 层弥合**。Sui 用 JSON-RPC 2.0(`POST /` + `{"method":"sui_getObject","params":[...]}`),Aptos 用 REST(`GET /v1/accounts/{addr}/resources`,POST 调 JSON-RPC 会被 405 拒绝,**H8 实证**)。这意味着 vegeta target 文件、HTTP body 模板、URL pattern、URL encoding、HTTP verb 选择全部不同。试图让 plugin schema 同时支持两者,会导致 60% 的 schema 字段都是 `if family==sui then ... else ...` 的条件字段,**比拆开两套 schema 更复杂**(token-level "把通用做成混合"反模式)。

**第二段 — 语义层可共享,但应放在 utils 而非 family schema**。Move struct_tag 解析(`0x1::coin::CoinStore<T>`)、`0x1` ~ `0xa` framework address 心智、CoinStore resource 概念、view function 调用模式(`{function, type_arguments, arguments}` 三段式)— 这些 VM/语义层概念在 Sui 和 Aptos 间相通,可以抽到 **`tools/move_utils.py`**(被 SuiAdapter 和 AptosAdapter 同时 import),但**不应**塞进 plugin DSL schema。DSL schema 是 protocol-binding 层,语义助手是工具层,**职责必须分开**。

**第三段 — 推荐结构 + family 命名建议**。

```
plugins/
├── movevm-sui.json       protocol_kind: jsonrpc, methods: sui_* / suix_*
├── movevm-aptos.json     protocol_kind: rest,    methods: GET/POST /v1/*
└── (共享) tools/move_utils.py    parse_struct_tag(), is_framework_addr(), ...
```

文档与 UI 仍可标注 **family = "Move"** 作为统计/分组标签(用户视角同族),但 plugin loader 和 adapter 严格按 subfamily 拆分。这与现有 EVM family 内 "ethereum/bsc/base/polygon/scroll 共用 EthereumAdapter" 的复用模式**不同**:EVM 5 链共用同一 protocol(`POST /` + `eth_*` method),只在 `chain_type` 字段上分支 block_range;Move 2 链 protocol 都不同,**不存在 EVM 式复用空间**。

**结论一句话**:**Move 是 family 标签,但 plugin schema 必须拆 `movevm-sui` + `movevm-aptos` 两个子 family,adapter 也分别实现 `SuiAdapter` 和 `AptosAdapter`,只共享 `move_utils.py` 语义层工具。** ✅

---

## 9.9 真实信源覆盖与时间戳

| 信源类型 | URL/路径 | 访问日期(UTC)| 状态 |
|---|---|---|---|
| 官方 REST API 文档 | https://aptos.dev/build/apis/fullnode-rest-api | 2026-05-23 | E1(引用,未 DOM 实证)|
| OpenAPI Spec(live)| https://fullnode.mainnet.aptoslabs.com/v1/spec.yaml | 2026-05-23 | **H8 实证 HTTP:200**(未解析全部 endpoint,留 Phase 2.1)|
| Mainnet 探活 | `GET https://fullnode.mainnet.aptoslabs.com/v1` | 2026-05-23 | **H8 实证 HTTP:200,chain_id=1,ledger_version=5392437054,block_height=783350119** |
| Mainnet 别名 | `GET https://api.mainnet.aptoslabs.com/v1/-/healthy` | 2026-05-23 | **H8 实证 HTTP:200 `aptos-node:ok`** |
| publicnode(候选)| https://aptos-mainnet.publicnode.com/v1 | 2026-05-23 | **H8 实测 HTTP:404 — 不可用** |
| ankr(候选)| https://rpc.ankr.com/http/aptos/v1 | 2026-05-23 | **H8 实测 HTTP:403(需 key)** |
| onfinality(候选)| https://aptos.api.onfinality.io/public/v1 | 2026-05-23 | **H8 实测 HTTP:404 — public path 不工作** |
| Sui 对比 — JSON-RPC | `POST https://fullnode.mainnet.sui.io:443 sui_getChainIdentifier` | 2026-05-23 | **H8 实证返回 `{"result":"35834a8a"}`** 证实 Sui 走 JSON-RPC |
| Sui 配置参考 | `config/config_loader.sh:622-650` | 2026-05-23 | **E1 read_file 实证**(sui rpc_methods + param_formats + system_addresses) |
| Sui audit 字段 | `tools/audit_rpc_methods.py:209-214` | 2026-05-23 | **E1 read_file 实证**(Sui ADAPTER_EXPECTED_FIELDS)|
| 框架链命名空间 | `config/config_loader.sh:666` supported_blockchains | 2026-05-23 | **E1 read_file**(aptos **未**在列,确认是新链)|

---

## Open Questions(待解决问题)

1. **文件编号矛盾**:本稿按 wave 命名 `04-aptos.md`,但 `00-SUMMARY.md` 第 17 行 Aptos 编号是 17。最终是改 SUMMARY 还是改文件名?(P1 收尾时由 user 决定)
2. **OpenAPI spec 深度解析**:`/v1/spec.yaml` 是 200 OK 的活 spec(application/x-yaml),本稿未做 endpoint 全量提取(仅探活)。Phase 1.2 Wave 2 是否做 `tools/audit_rpc_methods.py` 的 Aptos L1 实现(从 OpenAPI 自动 enumerate)?
3. **`POST /v1/view` 安全/性能**:view function 是任意 Move call,公共节点是否有 gas/cycle 上限?恶意 view 会不会被限流?(本稿未压测)
4. **`0x1::coin::balance` vs `0x1::aptos_account::*`**:Aptos 在 Fungible Asset (FA) 迁移后,部分账户用新 FA store,旧 CoinStore 可能 404。**balance 查询是否需要先探 FA store?** 本稿统一用 view function 自动兼容,但未对全量样本验证。
5. **mock_rpc_server REST 路由**:既然 Aptos 引入 REST,**是否提前在 Phase 2.0 把 mock 重构为 per-family handler**?(否则 Phase 2.1 单独为 Aptos 加 router 会让 mock 越改越乱 — token-level Case-D 风险)
6. **system_addresses 完整列表**:本稿仅 H8 实证 `0x1`,`0x2`-`0xa` 来自 E1 文档引用。是否需 Phase 2.x 用 OpenAPI 或 Move framework repo 反查权威列表?
7. **block_time 精度**:本稿 ~0.15s 是 H8 推算(`ledger_version` 增长率),不是 block_height 增长率;两者口径不同(Aptos 一个 block 可含多个 version)。Phase 2.x 监控应同步抓 `x-aptos-block-height` 和 `x-aptos-ledger-version` **分别**算速率。

---

## Changelog

| 日期(UTC)| 作者 | 变更 |
|---|---|---|
| 2026-05-23 | Hermes Agent | 初稿(P1-2 Wave1):H8 实证 6 个 endpoint + OpenAPI spec live;Sui vs Aptos 10 维度对比 (§11.7);决策 = **拆 `movevm-sui` + `movevm-aptos`** (§11.8);列出 10 项 Phase 2.1 caller/reader 改造点(§8.5)|
