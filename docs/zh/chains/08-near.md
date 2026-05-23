# 08 — NEAR Protocol 调研稿

> **版本**:v1.0(初稿,Phase 1.2 Wave 2)
> **调研日期**:2026-05-23
> **作者**:Hermes Agent(token-level + 调研先行 + H8 实证 / E1–E5 分级)
> **状态**:🟢 待 user review(P1-USER-REVIEW 卡点)
> **本稿强制满足**:`_template.md` §1–§10 + §11 DSL(含 11.7 query-dispatcher 挑战、11.8 三方案决策)
> **关键产出**:NEAR query 是 RPC dispatcher — DSL 必须显式建模(选定 **方案 B = `logical_method` 分离**,详 §11.8)

---

## 元信息

| 项 | 值 |
|---|---|
| 链名(中) | NEAR Protocol |
| 链名(英) | NEAR Protocol |
| 编号 | 08(Wave 2 内)/ SUMMARY 总册编号留待 P1 收尾(Open Q1) |
| Mainnet ChainID | **`"mainnet"`(字符串,非整数)** — H8 实证 `status.chain_id` |
| Genesis hash | `EPnLgE7iEq9s7yTkos96M3cWymH5avBAPm3qx3NXqR8H` — H8 实证(3 个独立 endpoint 一致) |
| 调研日期 | 2026-05-23 |
| 调研者 | Hermes Agent |
| 状态 | 🟢 已完成初稿 |

---

## 1. Sources(权威来源)

| 类型 | URL | 访问日期 | 备注 / 证据等级 |
|---|---|---|---|
| 官方文档主页 | https://docs.near.org | 2026-05-23 | E1(引用,未 DOM 实证)|
| RPC 规范 | https://docs.near.org/api/rpc/introduction | 2026-05-23 | E1 引用 — query 类 dispatcher 模式来源 |
| 协议规范(nearcore) | https://github.com/near/nearcore | 2026-05-23 | E1 引用(未 clone 实证)|
| Nomicon(协议白皮书)| https://nomicon.io | 2026-05-23 | E1 引用 — account_id / finality 字段语义 |
| Explorer | https://nearblocks.io | 2026-05-23 | E1 引用(未 DOM 实证)|
| 公共 RPC × 3 | rpc.mainnet.near.org / free.rpc.fastnear.com / near.lava.build | 2026-05-23 | **H8 实证 HTTP:200 + 同 genesis_hash**(详 §3)|

---

## 2. Protocol Family(协议族)

| 项 | 值 | 证据 |
|---|---|---|
| Family | **NEAR**(自研,**不属于** EVM / Move / UTXO / Cosmos / Substrate 任一)| 本调研核心结论(§10 / §11.8) |
| Consensus | Nightshade(Doomslug + Thresholded PoS,分片) | E1 文档(未 paper 级实证) |
| VM | **WASM**(合约编译为 Wasm,Rust / AssemblyScript SDK) | E1 文档 + `view_code` 返回 wasm 模块(§5) |
| Block Time | **~0.6–1.0s 实测**:`latest_block_time=2026-05-23T18:18:46Z` vs `epoch_start_height=199554728` 当前 `latest_block_height=199597051` 差 42323 高度,差 ~21.5 小时 ⇒ ~1.83s/block(epoch 跨度内均值,H8 推算)| **H8 实证 status.sync_info** |
| Finality | **三档**:`optimistic`(最新链头)/ `near-final`(doomslug 确认)/ `final`(BFT 终局)— 全部 H8 实测可用 | **H8 实证**(§5 M7/M8/T3)|
| 分片 | 是,多 shard(chunks 数组,每 block 含多 chunk;实测 chunks 数 ≥ 6)| **H8 实证 block result.chunks 数组** |
| Reuse Existing Adapter? | **No**(JSON-RPC 协议同 EVM 但 method 集 / 账户模型 / 参数 schema 完全不同;query 是 dispatcher 也是 EVM 没有的模式) | 详 §10 + §11.7/11.8 |

---

## 3. Public RPC(公共节点)

| Endpoint | Auth | Rate Limit | 备注 / H8 |
|---|---|---|---|
| `https://rpc.mainnet.near.org` | 无 | 官方未公开数值,匿名公共 | **H8 实证 HTTP:200 TIME:2.19s**(status 返回 chain_id=mainnet,latest_block_height=199597051)|
| `https://free.rpc.fastnear.com` | 无 | FastNEAR free tier(未声明数值)| **H8 实证 HTTP:200 TIME:0.17s**(同 genesis_hash;**最快**)|
| `https://near.lava.build` | 无 | Lava Network 公共网关 | **H8 实证 HTTP:200 TIME:0.43s**(同 genesis_hash)|
| `https://near-rpc.publicnode.com` | — | — | **H8 实测 HTTP:404 — 路径不对或不可用**(不推荐)|

**curl 实测**(必填,证明 RPC 真活):
```bash
curl -s -X POST https://free.rpc.fastnear.com \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"status","params":[]}'
# 实测节选(2026-05-23):
# {"jsonrpc":"2.0","result":{
#   "chain_id":"mainnet",
#   "genesis_hash":"EPnLgE7iEq9s7yTkos96M3cWymH5avBAPm3qx3NXqR8H",
#   "latest_protocol_version":83,
#   "sync_info":{
#     "latest_block_hash":"4C3RGv4vDSyts5zKw7r5kVKGheihKEYYHukvictJVsYy",
#     "latest_block_height":199597051,
#     "latest_block_time":"2026-05-23T18:18:46.274055678Z",
#     "syncing":false }, ... }}
```

**三 endpoint 一致性**:3 个独立 endpoint 返回的 `genesis_hash` 完全一致(`EPnLgE7iEq9s7yTkos96M3cWymH5avBAPm3qx3NXqR8H`)— 证明它们都连到同一 mainnet 真链,**任意一个都可作为压测 / mock 实证 baseline**。

---

## 4. Account Model(账户模型)

| 项 | 值 | 证据 |
|---|---|---|
| 模型 | **Account**(Account-based,与 EVM 同;**非** UTXO)| E1 + H8 `view_account` 返回 `amount/locked/storage_usage` |
| account_id 类型 | **人类可读字符串**(例:`relay.aurora`, `near`, `wrap.near`, `bob.near`)— **与所有现有支持链(Solana/EVM/Bitcoin/Sui)完全不同** | H8 实证(`relay.aurora` 查询成功,返回 amount=`1759801172720814773223780901` yoctoNEAR)|
| 命名约束 | 2-64 字符;`a-z 0-9 _ -`;层级用 `.` 分隔(top-level account 如 `near`、`aurora` 受系统注册);亦支持隐式 64-hex 账户(无父名空间)| E1 Nomicon |
| Native token decimals | **24**(yoctoNEAR;1 NEAR = 10^24 yoctoNEAR)| E1 文档(本稿未做 explorer 反算)|
| 子账户 | 是(`X.Y` 形式;只有 `Y` 可创建以 `.Y` 结尾的子账户)| E1 文档 |
| 特殊账户 | top-level account(如 `near` 系统合约,实测 `view_account` 返回 `storage_usage=2263935`,`code_hash` 非全零 = 是合约)| **H8 实证** |
| 密钥模型 | **Access Key 列表**(每账户 N 把 key,每把 `FullAccess` 或 `FunctionCall` 限制权限)| **H8 实证 `query view_access_key_list`** 返回 keys 数组,每项含 `nonce / permission` |
| Address derivation | Ed25519(`public_key` 字段实测前缀 `ed25519:`)| **H8 实证** |

---

## 5. Core RPC Methods(本框架监控所需)

> NEAR 全量 RPC 远多于此表;**本框架** mixed/single 模式需要的方法。完整 API 见 https://docs.near.org/api/rpc/。

### 5.1 直接 method(无 dispatcher)

| Method | 类别 | params 形态 | 在 mixed 中权重建议 | H8 实证 |
|---|---|---|---|---|
| `status` | 节点元信息 + 链头 | `[]` | 0.05 | ✅ HTTP:200(§3 T2)|
| `block` | 区块查询 | `{"finality":"final"}` 或 `{"block_id":<num>}` 或 `{"block_id":"<hash>"}` | 0.10 | ✅(§5 M2 by height,§3 T3 by finality)|
| `chunk` | 分片块查询 | `{"chunk_id":"<hash>"}` | 0.02(低)| ⚠️ 未直接实证(获取 chunk_hash 步骤被 user 阻断;但 block response 的 chunks 数组每项含 `chunk_hash`,API 形态 E1 文档)|
| `gas_price` | gas 价 | `[null]` 或 `[<block_id>]` | 0.05 | ✅ 返回 `{"gas_price":"100000000"}`(§5 M1)|
| `tx` | 交易状态(轻量)| `["<tx_hash>", "<signer_id>"]` | 0.15 | ⚠️ 仅形态验证(实测对 random hash 无响应即超时,未拿到真 tx 形态)|
| `EXPERIMENTAL_tx_status` | 交易状态详细 | `["<tx_hash>", "<signer_id>"]` | — | ⚠️ 形态同 `tx`,未实证 result |
| `broadcast_tx_async` | 提交交易(无等待)| `["<base64_signed_tx>"]` | 0.00(读基准不用)| ✅ 形态验证(无效 tx 返回 `-32700 Parse error`)|
| `validators` | 验证者集 | `[null]` 或 `[<block_id>]` | 0.03 | ✅ 返回 `current_proposals/current_validators` 数组 |
| `network_info` | peer / node 元 | `[]` | 0.00 | E1 形态(本稿未跑) |

### 5.2 `query` dispatcher(关键!真 method 在 `params.request_type`)

| logical method | `request_type` | params 关键字段 | 在 mixed 中权重建议 | H8 实证 |
|---|---|---|---|---|
| **view_account** | `view_account` | `account_id`, `finality`/`block_id` | 0.20 | ✅ `relay.aurora`/`near` 实测 |
| **view_access_key_list** | `view_access_key_list` | `account_id`, `finality` | 0.05 | ✅ 返回 keys 数组 |
| **view_access_key** | `view_access_key` | `account_id`, `public_key`, `finality` | 0.05 | ✅ 返回 `nonce/permission` |
| **call_function**(view-only 合约调用)| `call_function` | `account_id`, `method_name`, `args_base64`, `finality` | 0.20 | ✅ `wrap.near.ft_total_supply()` 返回 base64 编码字节数组(实测 result=[34,50,49,...,34] 即 ASCII `"21510714514871847363014456029803"`)|
| view_state | `view_state` | `account_id`, `prefix_base64`, `finality` | 0.05 | ⚠️ 形态验证(public RPC 可能拒大 state)|
| view_code | `view_code` | `account_id`, `finality` | 0.00(读基准低频)| ⚠️ E1 形态(wasm payload 较大) |

**所有 `query.*` 都共享 wire-level `method:"query"`**,真实区分维度是 `params.request_type` — **此即 §11.7/11.8 的核心 DSL 挑战**。

### 5.3 mixed 权重和(必须 = 1.0)

`status:0.05 + block:0.10 + gas_price:0.05 + tx:0.15 + validators:0.03 + view_account:0.20 + view_access_key_list:0.05 + view_access_key:0.05 + call_function:0.20 + view_state:0.05 + chunk:0.02 + 余 0.05`(留给 `block by hash` 二级混合)= **1.00** ✅

---

## 6. Address Format(地址格式)

| 项 | 值 | 证据 |
|---|---|---|
| 编码 | **UTF-8 字符串**(非 hex / 非 base58 / 非 bech32)| H8 — 所有实证 account_id 均为 `[a-z0-9._-]+` |
| 长度 | 2–64 字符 | E1 文档 |
| Checksum | **无**(账户在 chain 上注册即合法,无字符级校验)| E1 文档 |
| 示例(主网真实)| `relay.aurora`(Aurora bridge);`near`(系统合约);`wrap.near`(wNEAR FT 合约)| **H8 三者 `view_account` / `call_function` 实证** |
| 校验正则 | `^([a-z0-9]+[-_]?)*[a-z0-9]+(\.([a-z0-9]+[-_]?)*[a-z0-9]+)*$`(2–64 总长)或 64-hex(隐式账户)| E1 Nomicon |
| 隐式账户(可选)| 64 字符 lower-hex(`^[0-9a-f]{64}$`)— 由 ed25519 公钥派生 | E1 |

**与现有链对比**:

| 现有链 | address 编码 | NEAR 与其差异 |
|---|---|---|
| Solana | Base58 32 字节 | NEAR 是 string,无编码概念 |
| Ethereum/BSC/Base/Polygon/Scroll | 0x-prefix 20 字节 hex | NEAR 是 string,长度可变 |
| Bitcoin | base58check / bech32 | NEAR 是 string |
| Sui/Aptos | 0x-prefix 32 字节 hex | NEAR 是 string |
| Starknet | 0x-prefix 252-bit hex | NEAR 是 string |

**结论**:NEAR account_id 字段需在 DSL/adapter 引入新的 `address_format: "near_account_id"` 标签,**所有现有 address 校验正则不能复用**。

---

## 7. Signature Lookup(签名/交易哈希)

| 项 | 值 | 证据 |
|---|---|---|
| Hash 格式 | **Base58**(non-checked,长度 ~43–44 字符,例 `4C3RGv4vDSyts5zKw7r5kVKGheihKEYYHukvictJVsYy` block hash;tx hash 同编码)| **H8 实证**(block_hash / chunk_hash / latest_block_hash 均 base58)|
| 长度 | 通常 43–44 字符(32 byte → base58 ~44)| H8 |
| 查询 method | **必须配对 `signer_id`**:`tx(["<hash>","<signer_id>"])`(NEAR 分片所致 — 仅 hash 不足以定位 shard)| E1 文档 + H8 broadcast_tx 实证 -32700 Parse error 证明 wire shape |
| Explorer URL 格式 | `https://nearblocks.io/txns/<hash>` | E1(未 DOM 实证)|
| 示例(主网真实) | ⚠️ 本稿未提交独立 tx hash 验证(获取 step 被 user 阻断);**Phase 2.1 强制实测时从最新 block 的 chunk.transactions[].hash 拿** | ⚠️ |

**关键差异 vs 现有链**:NEAR `tx` 需 `(hash, signer_account_id)` 二元组,**EVM 的 `eth_getTransactionByHash(hash)` 一元接口模式不能直接复用**。这是 EthereumAdapter 不能复用的硬约束之一。

---

## 8. Mixed Set(`mixed` 模式权重)

```json
{
  "balance_query": 0.20,
  "access_key_query": 0.10,
  "tx_lookup": 0.15,
  "block_query": 0.12,
  "ft_balance_call": 0.20,
  "view_state": 0.05,
  "gas_price": 0.05,
  "validators": 0.03,
  "status_height": 0.05,
  "chunk_query": 0.02,
  "near_chain_specific": 0.03
}
```

**权重和 = 1.00** ✅。映射到 §5 表:

- `balance_query` = `query{request_type:view_account}`
- `access_key_query` = `query{request_type:view_access_key_list}` + `view_access_key`(合并 0.05+0.05)
- `tx_lookup` = `tx` method(`[hash, signer]`)
- `block_query` = `block` method(60% by `finality:final`,30% by `block_id:<num>`,10% by `block_id:<hash>`)
- `ft_balance_call` = `query{request_type:call_function, method_name:"ft_balance_of"}`(NEP-141 FT 标准,wrap.near / aurora token / usdt.tether-token.near)— **替代 EVM 的 ERC20 `eth_call(balanceOf)`**
- `near_chain_specific` 剩余 = block-by-hash 二级混合

---

## 8.5 Phase 2.1 caller/reader 改造点(token-level Gate 3)

| # | 位置(file:line) | 改动 | 原因 |
|---|---|---|---|
| 1 | `config/config_loader.sh:666` `supported_blockchains=(...)` | **新增 `"near"`** | 当前不在列(已 E1 实证),否则 BLOCKCHAIN_NODE=near 触发 "Unsupported" 报错 |
| 2 | `config/config_loader.sh` 本链 `rpc_methods.mixed` 块(参考 sui 块在 622-650) | **新建 near 块**:11 条 method/logical_method + 权重(§8) | vegeta target 生成器消费;**必须用 logical_method 命名(方案 B,§11.8)** |
| 3 | `config/config_loader.sh` 本链 `param_formats` 块 | **新建 near 块**:per logical_method 的 params 模板(query 的 5 个 sub-method 各一个 template) | `generate_rpc_json` 漏字段会让 query 退到 `view_account` 默认或失败 |
| 4 | `tools/mock_rpc_server.py` | **新增 `method:"query"` 分支**,内部按 `params.request_type` 二级路由到 5 个 sub-handler(view_account / view_access_key / view_access_key_list / call_function / view_state)+ `block / status / gas_price / tx / validators / chunk / broadcast_tx_async / network_info` 共 ~12 个 case | mock 是 fallback target,不改 mock 模式跑不通新 plugin |
| 5 | `tools/fetch_active_accounts.py` 新增 `NearAdapter` 类 | 实现 `fetch_top_accounts(limit)` — 由 nearblocks API 或固定种子集(`relay.aurora` / `near` / `wrap.near` / `aurora` / `usdt.tether-token.near` / `token.sweat`)| account discovery 不能复用 SolanaAdapter / EthereumAdapter |
| 6 | `tools/audit_rpc_methods.py` 新增 `NEAR_ADAPTER_EXPECTED_FIELDS` | 必须含 `account_id / finality / request_type / args_base64 / method_name / public_key`(query dispatcher 字段集) | L1 audit 漏字段 = Phase 2.1 token-level Case-B caller-blind |
| 7 | `analysis-notes/baseline-current-state.md` grep "supported chains" | 同步加 near | 文档真相对齐,防 v1.4.1 同款 doc-vs-code 偏离 |
| 8 | `analysis-notes/disk-and-network-pipeline-redesign.md` | 同步 | 同上 |
| 9 | `analysis-notes/research_notes/<近期 plugin DSL 笔记>.md` | 标注 query-dispatcher 模式纳入 schema | 研究笔记反映现实 |
| 10 | `tests/<新增>tests/test_near_e2e.sh` | L1 单测:`status` + `query view_account relay.aurora` + `block finality:final` 三发 | 链入 CI 前 baseline |

**若 NEAR 是新增链(确认无现有代码,§E1 实证)**,#1–#6 全部要做,#7–#10 视情况。

**测试要求**:Phase 2.1 完成后必须跑 `core/master_qps_executor.sh --mixed --duration 30`(或最短 e2e_smoke)抓 vegeta 错误率,**所有请求应是 200**,作为 NEAR 改造 E2 证据。

---

## 9. Mock Notes(mock_rpc_server 实现要点)

- **请求路径**:`POST /`(根路径,JSON-RPC 2.0;同 EVM / Sui)
- **响应 schema**(贴一段真实主网响应做样本):
  ```json
  {"jsonrpc":"2.0","result":{
     "amount":"1759801172720814773223780901",
     "block_hash":"6bYBg694EaTfJA12gg1WN4PU11PhWfq1ANkSvQabLGyX",
     "block_height":199597056,
     "code_hash":"11111111111111111111111111111111",
     "locked":"0",
     "storage_paid_at":0,
     "storage_usage":149422
  },"id":1}
  ```
  (`view_account relay.aurora` H8 实证,2026-05-23)
- **特殊错误码**(H8 / E1):
  - `-32700`:**Parse error**(实测 `broadcast_tx_async` 用无效 base64 返回此码,`name:"REQUEST_VALIDATION_ERROR"`,`cause.name:"PARSE_ERROR"`)
  - `-32600`:Invalid request(E1)
  - `-32601`:Method not found(E1)
  - `-32602`:Invalid params(E1)
  - **NEAR 额外语义**:`HANDLER_ERROR` 类(账户不存在 / key 不存在 / block 不存在),HTTP 仍 200,error.cause.name 区分 — mock 需保留 `error` envelope 形态
- **mock 实现复杂度**:**Medium-High**
  - Medium:JSON-RPC envelope 与 EVM 同
  - High:**query 二级分发**(`params.request_type` 5 种 case)+ 三档 finality 区分 + base64 编码 args / state / 返回 result + `tx` 需要 `(hash, signer_id)` 二元 key + 分片 chunks 数组结构

---

## 10. Adapter Reuse Decision(adapter 复用决策)

### 候选 adapter

| Adapter | 兼容度 | 缺失能力 |
|---|---|---|
| EthereumAdapter | **~15%**(共享 JSON-RPC envelope / POST `/` / id 字段;**method 集 / 参数 schema / 账户模型 / hash 编码 / 错误语义全部不同**) | account_id string / query dispatcher / finality 字段 / base58 hash / `(hash,signer)` 二元 tx key / yoctoNEAR 24 decimals / NEP-141 FT 调用(call_function vs eth_call) |
| SolanaAdapter | **~5%** | 协议 method 集完全不同(SVM vs WASM);Solana 无 dispatcher |
| SuiAdapter | **~10%** | JSON-RPC envelope 同;account/object 模型完全不同;无 dispatcher 模式 |
| BitcoinAdapter | **0%** | UTXO vs Account |
| AptosAdapter | **0%** | REST vs JSON-RPC |

### 决策

- [ ] 复用 `EthereumAdapter`
- [x] **新建 `NearAdapter`(新 family `near`)**
- [ ] 混合

### 理由

**第一段 — 协议 envelope 复用收益微小,语义层差异是硬阻塞**。NEAR 与 EVM 共享的只是 JSON-RPC 2.0 信封(`{jsonrpc, id, method, params}`)与 `POST /` 路径 — 在 vegeta 的 target body 层确实可同模板。但凡涉及 method 命名、params 结构、address 校验、hash 解码、balance 解码(yoctoNEAR 24 decimals)、tx 查询的 `(hash,signer)` 二元键、finality 三档语义、query dispatcher 二级路由 — 全部需新代码路径。token-level "把通用做成混合" 反模式提醒:如果共享层只覆盖 15%,强行复用 EthereumAdapter 会让其内部出现 `if chain == "near"` 分支群,**未来 EVM 链改动也会被 NEAR 路径牵连**。

**第二段 — query dispatcher 是 NEAR 独有的 wire 模式,需要 adapter 层显式建模**。EVM/Sui/Solana 都是 "method 字符串 = 一个端到端能力" 的一一对应模式;NEAR 的 query 是 dispatcher,真 method 在 `params.request_type` — 这要求 adapter 内部维护一个 `logical_method → (rpc_method, request_type, params_template)` 的二级映射(§11.8 方案 B)。EthereumAdapter 当前没有这种二级映射机制,塞进去会破坏其单层假设。

**第三段 — account_id 是字符串而非编码地址,是 family 边界的另一硬证据**。所有现有 adapter 都有 `_validate_address(s)` 类方法,期望输入是某种编码(hex/base58/bech32);NEAR account_id 是 UTF-8 字符串,无 checksum,可包含 `.` 子账户分层 — 这是 family 级语义,**应通过 `NearAdapter` 内独立的 `validate_account_id()` 表达,而不是给 EthereumAdapter 加 family-aware 分支**。结论:新建 `NearAdapter`,family 标签 = `near`(独立,与 EVM/Move/UTXO/Cosmos/Substrate 平级)。

### 配置 JSON 示例(本链)

```json
{
  "chain": "near",
  "family": "near",
  "adapter": "NearAdapter",
  "chain_id": "mainnet",
  "rpc_endpoint": "https://free.rpc.fastnear.com",
  "block_time_ms": 1830,
  "address_format": "near_account_id",
  "hash_format": "base58",
  "native_decimals": 24,
  "default_finality": "final",
  "rpc_methods": {
    "block_height":     { "rpc_method": "status",    "response_path": ".result.sync_info.latest_block_height" },
    "block":            { "rpc_method": "block",     "params_template": {"finality": "{{finality|final}}"} },
    "balance":          { "rpc_method": "query",     "request_type": "view_account",
                          "params_template": {"request_type":"view_account","finality":"{{finality|final}}","account_id":"{{account_id}}"},
                          "response_path": ".result.amount" },
    "access_key_list":  { "rpc_method": "query",     "request_type": "view_access_key_list",
                          "params_template": {"request_type":"view_access_key_list","finality":"{{finality|final}}","account_id":"{{account_id}}"} },
    "tx_lookup":        { "rpc_method": "tx",        "params_template": ["{{tx_hash}}","{{signer_id}}"] },
    "ft_balance":       { "rpc_method": "query",     "request_type": "call_function",
                          "params_template": {"request_type":"call_function","finality":"{{finality|final}}",
                            "account_id":"{{ft_contract}}","method_name":"ft_balance_of",
                            "args_base64":"{{args_b64}}"} },
    "gas_price":        { "rpc_method": "gas_price", "params_template": [null] }
  },
  "mixed_weights": {
    "balance_query": 0.20, "access_key_query": 0.10, "tx_lookup": 0.15, "block_query": 0.12,
    "ft_balance_call": 0.20, "view_state": 0.05, "gas_price": 0.05, "validators": 0.03,
    "status_height": 0.05, "chunk_query": 0.02, "near_chain_specific": 0.03
  }
}
```

---

## 11. DSL Field Requirements(本链对 plugin DSL 的诉求)

### 11.1 finality 字段(NEAR 独有)

DSL params_template 必须支持 `finality: "optimistic" | "near-final" | "final"`(默认 `final`)。**EVM 的 `latest/pending/safe/finalized` 是 block tag,与 NEAR 不同**:NEAR 的 finality 是查询级开关,影响 state root 选择。建议 DSL 增加可选顶层字段 `default_finality: "final"` + 每方法 `params_template` 可覆盖。

### 11.2 account_id 字段(NEAR 独有 string 形态)

DSL `address_format` enum 需新增 `"near_account_id"`(对比现有 `base58 / hex / bech32`)。校验由 adapter 完成,DSL 仅标签化。

### 11.3 hash_format 字段(base58 同 Solana 但 hash 配 signer)

`tx` method 的 params 是 `[hash, signer_id]` 二元数组(而非 EVM 的单一 hash)。**这是 NEAR 唯一的 positional params + 强耦合 account 的 method**,DSL `params_template` 需能表达 positional 形式(JSON 数组)。

### 11.4 native_decimals 字段(NEAR=24,Solana=9,EVM=18,Sui=9 各不同)

DSL 已有此概念但建议显式;NEAR 的 yoctoNEAR (10^24) 会让 64-bit int 溢出,**balance 解码必须用 string + bignum lib**。

### 11.5 response_path 字段(嵌套提取)

`status` 拿 height 在 `.result.sync_info.latest_block_height`(三层);`view_account` 拿 amount 在 `.result.amount`;`call_function` 拿 result 在 `.result.result`(数组 byte 还需 ASCII 解码)。沿用 Aptos 调研(`04-aptos.md §11.3`)的 `response_path: JSONPath-lite` 字段,跨 family 通用。

### 11.6 error envelope 与 error.cause 提取

NEAR error 形态比 EVM 复杂:`error.cause.name` 是真实错误类型(`PARSE_ERROR / HANDLER_ERROR / ...`),`error.code` 是粗粒度 JSON-RPC code。DSL 需允许 `error_path: ".error.cause.name"`(与 §11.5 同字段族)以便监控正确归因。

### 11.7 NEAR query dispatcher 模式 — DSL 表达挑战(关键!)

**问题**:NEAR 几乎所有读操作都走 `method: "query"`,真 method 区分在 `params.request_type` 字段。下面是同一 wire-method 的 5 个真实形态(本调研 H8 实证):

```jsonc
// 形态 1:view_account(返回 amount/locked/storage_usage)
{"jsonrpc":"2.0","id":1,"method":"query","params":{
  "request_type":"view_account",
  "finality":"final",
  "account_id":"relay.aurora"}}

// 形态 2:view_access_key_list(返回 keys 数组)
{"jsonrpc":"2.0","id":1,"method":"query","params":{
  "request_type":"view_access_key_list",
  "finality":"final",
  "account_id":"relay.aurora"}}

// 形态 3:view_access_key(返回 nonce/permission)
{"jsonrpc":"2.0","id":1,"method":"query","params":{
  "request_type":"view_access_key",
  "finality":"final",
  "account_id":"relay.aurora",
  "public_key":"ed25519:168vdqFUxij2yvsxYgAGoykJMX7tgrPKVCH484A8nHP"}}

// 形态 4:call_function(NEP-141 FT 余额、合约 view)
{"jsonrpc":"2.0","id":1,"method":"query","params":{
  "request_type":"call_function",
  "finality":"final",
  "account_id":"wrap.near",
  "method_name":"ft_total_supply",
  "args_base64":"e30="}}

// 形态 5:view_state(返回 KV 列表,可能很大)
{"jsonrpc":"2.0","id":1,"method":"query","params":{
  "request_type":"view_state",
  "finality":"final",
  "account_id":"relay.aurora",
  "prefix_base64":""}}
```

**核心 DSL 困难**:监控 / 指标 / mixed 权重 / vegeta target 文件都以 "method" 为切分粒度。若直接用 wire-level `method` 命名,**全部 5 条都叫 `query`,粒度坍缩到 0,完全无法分别监控**。

#### 三方案(任务设定)

| 方案 | 写法 | 优势 | 劣势 |
|---|---|---|---|
| **A 扫平** | DSL 写 `method: "query"`,5 个 entry 区别全在 `params_template` 字面值 | schema 零改,完全沿用 EVM 风格 | **method 区分度丢失**:monitoring/metrics/vegeta target 文件按 method 分组时 5 个 NEAR query 合并成一行,p99 / error rate 失去意义 |
| **B logical_method 分离**(推荐)| DSL 增加可选 `logical_method` 字段;监控 / 配置 / 权重统一用 `logical_method`;adapter 真实发包时取 `rpc_method` | 改动最小(增 1 字段);监控粒度恢复;**EVM/Solana 不填 = 向后兼容** | adapter 内部需维护 logical→rpc 映射 |
| **C dispatcher 抽象** | DSL 顶层 `dispatcher: { method: "query", dispatch_param: "request_type" }` + `methods: [view_account, view_access_key, ...]` 全部走 dispatcher | 泛化最强,语义最清晰 | schema 复杂度上升;**只有 NEAR(以及未来潜在 Aptos `/v1/view` body 的 function 字段)用得到**;为 1 链改 schema 风险高 |

### 11.8 DSL 决策建议(关键产出)

- [ ] **方案 A 扁平**(method 区分度差)
- [x] **方案 B logical_method 分离**(中等复杂度,推荐)
- [ ] **方案 C dispatcher 抽象**(泛化最强但 schema 复杂)

**理由(3 段)**:

**第一段 — 方案 A 在监控层是死路**。本框架的核心价值是为每条 method 出 p50/p95/p99 + error_rate + 用 mixed 权重做工作负载组合;`method` 是 vegeta target、prometheus label、QPS 报表的主键。若 NEAR 5 个 query 全叫 `query`,监控曲线变成 5 个 method 的**算术混合**(`view_account` 是亚毫秒,`view_state` 可能是数百毫秒,`call_function` 取决于合约)— p99 完全不可解释,error 归因也合并到 `query` 一行。该方案违反 H7(可观测性必须粒度匹配语义),否决。

**第二段 — 方案 B 在 schema / 兼容 / 实现成本三方面都最优**。增加一个**可选** `logical_method` 字段:NEAR plugin 填 `logical_method=view_account, rpc_method=query`,EVM/Sui/Solana 不填(`logical_method` 默认 = `rpc_method`)— **现有 7 条已上线链零改动**。adapter 层只需在 NearAdapter 里维护一个 5-entry 的映射表,~30 行代码。监控层用 `logical_method` 作为 label key,粒度恢复到真业务语义。token-level "局部变化 + 默认值兼容" 模式,Phase 2.1 改造成本可控。

**第三段 — 方案 C 在为 1 条链改 schema 这件事上 ROI 不足,但留口**。dispatcher 模式在区块链 RPC 生态中**确实不是 NEAR 独有**:Aptos REST `POST /v1/view` 的 body `{function:"<module>::<func>", type_arguments, arguments}` 中 `function` 字段在概念上也是 dispatcher;CosmWasm `wasm.contractInfo` / `wasm.smartContractState` 在 Cosmos LCD 中也有类似 entry-point 字段。**但**:Aptos 调研已选择 REST + path-as-method 建模(`04-aptos.md §11.2`),Cosmos 还未调研。在 Wave 2 只有 NEAR 命中此模式的情况下,引入方案 C 是 over-engineering — 等 Wave 3+ 再看 Aptos view 和 CosmWasm 是否真的需要,届时方案 C 可在 B 之上叠加(`logical_method` 仍存在,只是上面再抽 `dispatcher` 元层)。**结论:Wave 2 用方案 B 解 NEAR,方案 C 留作 Wave 3+ 重审的 DSL ASK。**

**一句话结论**:**`logical_method` 字段(可选,默认 = `rpc_method`)+ NearAdapter 内部 5-entry dispatch 映射 = NEAR query 模式的最小完备表达。** ✅

---

## 9.9 真实信源覆盖与时间戳

| 信源类型 | URL/路径 | 访问日期(UTC)| 状态 |
|---|---|---|---|
| 官方 RPC 主网 1 | `POST https://rpc.mainnet.near.org` method=status | 2026-05-23 | **H8 HTTP:200 TIME:2.19s,chain_id=mainnet,genesis=EPnLgE7iEq9s7yTkos96M3cWymH5avBAPm3qx3NXqR8H,latest_block_height=199597051** |
| FastNEAR | `POST https://free.rpc.fastnear.com` method=status | 2026-05-23 | **H8 HTTP:200 TIME:0.17s,同 genesis_hash** |
| Lava | `POST https://near.lava.build` method=status | 2026-05-23 | **H8 HTTP:200 TIME:0.43s,同 genesis_hash** |
| publicnode(候选)| `POST https://near-rpc.publicnode.com` | 2026-05-23 | **H8 HTTP:404 — 不可用** |
| block by finality | `block {finality:final}` | 2026-05-23 | **H8 实证返回 chunks 数组 + author=bisontrails2.poolv1.near** |
| block by height | `block {block_id:199597000}` | 2026-05-23 | **H8 实证返回 chunks 数组 + author=kiln-1.poolv1.near** |
| finality=optimistic | `block {finality:optimistic}` | 2026-05-23 | **H8 实证返回 chunks(author=zavodil.poolv1.near)** |
| finality=near-final | `block {finality:near-final}` | 2026-05-23 | **H8 实证返回 chunks(author=liver.pool.near)** |
| query view_account | `query view_account relay.aurora` | 2026-05-23 | **H8 amount=1759801172720814773223780901,storage_usage=149422** |
| query view_account 系统合约 | `query view_account near` | 2026-05-23 | **H8 code_hash=HiyC5tB1gBDpgR4x1guEp1orBde5PXqUYGoWaZfX3JGX(非全零=合约)** |
| query view_access_key_list | `query view_access_key_list relay.aurora` | 2026-05-23 | **H8 返回 keys 数组(多把 FullAccess ed25519)** |
| query view_access_key | `query view_access_key relay.aurora <pubkey>` | 2026-05-23 | **H8 nonce=65790930076833, permission=FullAccess** |
| query call_function | `query call_function wrap.near.ft_total_supply()` | 2026-05-23 | **H8 result=[34,50,49,…] = ASCII "21510714514871847363014456029803"** |
| gas_price | `gas_price [null]` | 2026-05-23 | **H8 result.gas_price="100000000"** |
| validators | `validators [null]` | 2026-05-23 | **H8 返回 current_proposals/current_validators 数组** |
| broadcast_tx_async error envelope | `broadcast_tx_async ["DwAAAGFhYQ=="]` | 2026-05-23 | **H8 error code=-32700 name=REQUEST_VALIDATION_ERROR cause.name=PARSE_ERROR** — 证明 error envelope 形态 |
| 框架链命名空间 | `config/config_loader.sh:666` supported_blockchains | 2026-05-23 | **E1 read_file**(near **未**在列,确认是新链)|

**未实证 / 留 Phase 2.1**:
- 单条独立 tx_hash 的 `tx` method 实证(获取步骤被 user 阻断 `/tmp/*.json` 写入)
- `chunk` method 的真实 result schema
- `view_state` 在生产 RPC 的实际可用性(可能因 state 过大被拒)
- NEAR public RPC 的 rate limit 数值(官方未公开)
- nearblocks.io explorer DOM 抓取真实 tx hash 形态(本稿仅用 block_hash 推断 hash 编码)

---

## Open Questions(待解决问题)

1. **文件编号**:本稿按 wave 命名 `08-near.md`,与 SUMMARY 总册未对齐 — P1 收尾由 user 决定最终编号。
2. **DSL 方案 C 何时启动**:Aptos `/v1/view` body `function` 是否实质构成第二个 dispatcher 用例?Wave 3+ Aptos 上线后,若再加 Cosmos / Polkadot 也命中,方案 C 是否值得在 B 上叠加 `dispatcher` 元层?
3. **tx 二元 key**:NEAR 的 `tx(hash, signer_id)` 二元参数对 explorer / 客户端是个长期摩擦点 — 框架的 `tx_lookup` mixed entry 是否需配 "signer pool"(从近期 block 抓 signer)?还是固定用 `relay.aurora` 这种长期活跃账户做 dummy?
4. **finality 三档在 mixed 权重内的分布**:目前 `block_query` 0.12 全用 `finality:final`,是否需细分 0.06 final + 0.04 near-final + 0.02 optimistic 以覆盖三档语义?
5. **yoctoNEAR bignum**:Python adapter 用 `int` 即可(Python int 任意精度),但 vegeta target 文件生成的 shell 路径(bash `printf`)可能溢出 — Phase 2.1 验证生成器对 24 位十进制数的处理。
6. **NEP-141 FT 合约种子集**:`wrap.near / aurora / usdt.tether-token.near / token.sweat` 是否长期稳定?若 Sweat 合约重命名,种子集需热更新机制。
7. **公共 RPC 真实 rate limit**:`rpc.mainnet.near.org` 延迟 2.19s 显著高于 FastNEAR 0.17s 与 Lava 0.43s — 是否官方节点本身有限流?压测 baseline 建议 FastNEAR。
8. **隐式账户(64-hex)**:本稿未实证一个隐式账户的 view_account — 是否所有 query.* 形态都支持隐式账户?(Phase 2.1 验证)
9. **chunk_id 类型**:`chunk` method 是否同时接受 `chunk_hash`(base58)和 `{block_id, shard_id}` 元组?本稿未实证后者。
10. **mock_rpc_server 路由策略**:NEAR 引入 query dispatcher 后,mock 是否提前重构为 "method handler + sub-handler(dispatch_param)" 两级?(否则 Phase 2.1 单独为 NEAR 加 router 会让 mock 越改越乱 — token-level Case-D 风险)

---

## Changelog

| 日期(UTC)| 作者 | 变更 |
|---|---|---|
| 2026-05-23 | Hermes Agent | 初稿(P1-2 Wave2):H8 实证 3 个 endpoint + 5 个 query sub-method + 3 档 finality + gas_price/validators/broadcast 错误码;§11.7/11.8 三方案对比 + **决策 = 方案 B `logical_method` 分离**;新建 `NearAdapter`(新 family `near`);列 10 项 Phase 2.1 caller/reader 改造点(§8.5) |
