# 11-tezos 调研

> **本文件由 `_template.md` 衍生 + Wave3 强制 Section 11(11.1-11.8)。**
> **填写时遵守 H8(真实证据):curl 实测 + 官方文档 URL + 访问日期。**
> 未 100% 实证的断言均以 ⚠️ 显式标注。

---

## 元信息

| 项 | 值 |
|---|---|
| 链名(中) | Tezos |
| 链名(英) | Tezos |
| 编号 | 11 |
| Mainnet ChainID | `NetXdQprcVkpaWU`(字符串,非数字) |
| 调研日期 | 2026-05-23 |
| 调研者 | Hermes Agent |
| 状态 | 🟢 已完成(H8 实证 8 个 RPC + 3 链 REST 对比实证) |

---

## 1. Sources(权威来源)

| 类型 | URL | 访问日期 | 备注 |
|---|---|---|---|
| 官方协议站 | https://tezos.com/developers | 2026-05-23 | 协议入口 — ⚠️ 未 DOM 实证(仅引用) |
| Octez RPC 规范 | https://tezos.gitlab.io/shell/rpc.html | 2026-05-23 | Shell RPC reference(/chains/* /monitor/* 等)— ⚠️ 未 DOM 实证 |
| Octez 协议 RPC | https://tezos.gitlab.io/active/rpc.html | 2026-05-23 | active protocol RPC(`/context/contracts/*` 等)— ⚠️ 未 DOM 实证 |
| ECAD 公共节点 | https://mainnet.api.tez.ie | 2026-05-23 | **H8 实证:`/version` HTTP:200,Octez v24.4(release),commit 56bd3e33,2026-04-17** |
| TzKT Indexer API | https://api.tzkt.io | 2026-05-23 | **H8 实证:`/v1/operations/transactions` HTTP:200**(用于反查 tx_hash) |
| SmartPy 节点 | https://mainnet.smartpy.io | 2026-05-23 | **H8 实证:`/version` HTTP:200**(同样 Octez v24.4)— 备份 endpoint |
| Explorer(TzKT)| https://tzkt.io | 2026-05-23 | 用于人工 cross-check op_hash — ⚠️ 未 DOM |
| GitHub(Octez 源)| https://gitlab.com/tezos/tezos | 2026-05-23 | 客户端源码 — ⚠️ 未 git clone |

---

## 2. Protocol Family(协议族)

| 项 | 值 |
|---|---|
| Family | **Tezos**(独立 family,不与 Cosmos/Substrate/Move/EVM 混) |
| Consensus | **LPoS(Liquid Proof-of-Stake)** + Tenderbake BFT-style 终结性 — E3(文档),H8 仅证 protocol 升级链(`PtTALLi…` 在 head) |
| VM | **Michelson**(强类型栈式函数式 VM)+ Smart Rollup(SORU,L2) |
| Block Time | **~10s** — 推算自 H8 实测:level 13329316 @ 2026-05-23T18:44:13Z vs level 13329000 @ 2026-05-23T18:12:19Z → 316 blocks / 1914 s ≈ **6.06 s/block**(注:这是当前 protocol PtTALLi 的 minimal_block_delay;文档历史值 10-30s 视 protocol)|
| Finality | **2 blocks 决定性终结**(Tenderbake,E3 文档) — ⚠️ 未 E2 实测 finalized vs head 差 |
| Reuse Existing Adapter? | **No** — Tezos 是独立 family,需新增 `TezosAdapter`(详见 §10) |

---

## 3. Public RPC(公共节点)

| Endpoint | Auth | Rate Limit | 备注 |
|---|---|---|---|
| https://mainnet.api.tez.ie | 无 | ⚠️ 未公开文档 | **H8 实证活**:`/version` 200,延迟 ~0.41s,Octez v24.4(release) |
| https://mainnet.smartpy.io | 无 | ⚠️ 未公开文档 | **H8 实证活**:`/version` 200,延迟 ~0.35s,Octez v24.4(release)— 推荐备份 |
| https://api.tzkt.io | 无 | 文档称 10K req/day(free)| **Indexer 风格**(非 Octez RPC),用于反查 tx_hash;不能替代 Octez RPC |

**curl 实测**(证明 RPC 真活,2026-05-23 ~18:44 UTC):

```bash
# 1. /version — node 版本 + 网络名(用作健康检查)
$ curl -s https://mainnet.api.tez.ie/version
{"version":{"major":24,"minor":4,"build":0,"additional_info":"release"},
 "network_version":{"chain_name":"TEZOS_MAINNET","distributed_db_version":2,"p2p_version":1},
 "commit_info":{"commit_hash":"56bd3e33","commit_date":"2026-04-17 10:26:39 +0000"}}
# HTTP:200

# 2. head block header — chain_id + protocol_hash + level
$ curl -s https://mainnet.api.tez.ie/chains/main/blocks/head/header
{"protocol":"PtTALLiNtPec7mE7yY4m3k26J8Qukef3E3ehzhfXgFZKGtDdAXu",
 "chain_id":"NetXdQprcVkpaWU",
 "hash":"BLffzWLDPFwcaDU4qYtnbpwTgNeWmE8FXUEgZVxCLjoJj6VGPtQ",
 "level":13329316, "proto":24, "timestamp":"2026-05-23T18:44:13Z", ...}
# HTTP:200

# 3. balance(tz1 baker)
$ curl -s https://mainnet.api.tez.ie/chains/main/blocks/head/context/contracts/tz1KqTpEZ7Yob7QbPE4Hy4Wo8fHG8LhKxZSx/balance
"53"
# HTTP:200 — 注意是 JSON string(非数字),单位 mutez(10⁻⁶ XTZ)

# 4. chain_id 单独 endpoint
$ curl -s https://mainnet.api.tez.ie/chains/main/chain_id
"NetXdQprcVkpaWU"
# HTTP:200
```

---

## 4. Account Model(账户模型)

| 项 | 值 |
|---|---|
| 模型 | **Account**(余额直接挂账户;无 UTXO)|
| Native token decimals | **6**(单位 mutez = 10⁻⁶ XTZ)— E3 文档,H8 实测返 `"53"` mutez(string 包裹)|
| Address derivation | **多算法**:tz1=Ed25519 / tz2=Secp256k1 / tz3=P256 / KT1=hash of origination(智能合约)— 4 种前缀同一 36 字符格式 |
| Special account types | **Implicit account**(tz1/tz2/tz3,可直接收发)/ **Originated contract**(KT1,Michelson 合约)/ **Smart Rollup**(sr1,L2)— 当前调研聚焦前 4 种 |

---

## 5. Core RPC Methods(本框架监控所需)

> 仅列本基准测试框架需要的 method。完整 RPC 列表见 https://tezos.gitlab.io/active/rpc.html。
> **所有 method 都是 REST 风格 `<HTTP_VERB> <PATH>`,无 JSON-RPC method 字符串。**

| Method(HTTP verb + path)| 类别 | 说明 | mixed 权重建议 |
|---|---|---|---|
| `GET /chains/main/blocks/head/header` | block height + protocol | 探活、读 level、读 protocol_hash、读 chain_id | 0.10 |
| `GET /chains/main/blocks/{level\|hash}/header` | block content(轻量)| 历史 block header(不含 op 详情)| 0.10 |
| `GET /chains/main/blocks/{block}/operations/{validation_pass}` | tx lookup | 取该 block 的某 validation_pass 全部 op(返数组)| 0.15 |
| `GET /chains/main/blocks/head/context/contracts/{addr}/balance` | balance | 账户余额(mutez,JSON string)| 0.30 |
| `GET /chains/main/blocks/head/context/contracts/{addr}/counter` | tx prep | 账户 nonce-like counter(用于构造 tx)| 0.05 |
| `GET /chains/main/chain_id` | meta | chain_id 单独读取(常量)| 0.05 |
| `GET /version` | health/version | 节点 Octez 版本 + commit | 0.05 |
| `GET /chains/main/blocks/head/protocols` | **protocol upgrade 监控** | 当前 active protocol + next protocol(amendment 进行中时不同)| 0.10 |
| `GET /chains/main/blocks/head/votes/current_period` | governance | 当前投票周期阶段(proposal/exploration/cooldown/promotion/adoption)| 0.10 |

**总权重 = 0.10+0.10+0.15+0.30+0.05+0.05+0.05+0.10+0.10 = 1.00 ✅**

**注**:Tezos 没有 ERC20-like 原生 "token balance" 概念 — FA1.2/FA2 token 余额需要走合约 storage(`GET /chains/main/blocks/head/context/contracts/{KT1}/storage` 然后解析 big_map),复杂度高,**本框架 Phase 2.x 不监控**(留 Open Q)。`balance` 仅指 native XTZ。

---

## 6. Address Format(地址格式)

| 项 | 值 |
|---|---|
| 编码 | **Base58Check**(Bitcoin 风格 alphabet + 4-byte sha256d checksum) |
| 长度 | **36 字符固定**(3-byte prefix + 20-byte hash + 4-byte checksum,Base58 编码)|
| Checksum | **有**(Base58Check,prefix 4-byte sha256d 截断)|
| 前缀语义 | `tz1` Ed25519 / `tz2` Secp256k1 / `tz3` P256 / `KT1` 智能合约 / `sr1` Smart Rollup |
| 示例(主网真实) | `tz1KqTpEZ7Yob7QbPE4Hy4Wo8fHG8LhKxZSx`(Tezos Foundation baker)— **H8 实证 balance 200 返 `"53"` mutez** |
| 示例(KT1 实证) | `KT1WvzYHCNBvDSdwafTHv7nJ1dWmZ8GCYuuC`(objkt.com Marketplace v2)— **H8 实证 balance 200 返 `"108962378338"` mutez ≈ 108963 XTZ** |
| 校验正则 | `^(tz[1-3]|KT1|sr1)[1-9A-HJ-NP-Za-km-z]{33}$` |
| 错误证据(bad addr)| **H8 实证 `/contracts/tz1notarealaddress/balance` 返 HTTP:400 + `"Cannot parse contract id"`** — 验证服务端做严格 base58check |

---

## 7. Signature Lookup(签名/交易哈希)

| 项 | 值 |
|---|---|
| Hash 格式 | **Base58Check**(与地址同 alphabet 但 51 字符,前缀 `o` 系列)|
| 长度 | **51 字符**(`o` + 50)|
| 前缀语义 | `o` 起头 = operation hash(进一步细分 `oo` 是常见 transaction op,`op` / `on` / `ooen` 等亦合法)|
| 示例(主网真实) | `ong1822VPmQwj4bzXFwvaZUvpD6ydLsHMJMEw9UPrP7SL6EKjFd`(level 13329321 transaction)— **H8 实证 TzKT `/v1/operations/{hash}` 200 返完整 tx 详情** |
| 查询 method | **关键**:Octez RPC **没有 `getTxByHash(op_hash)` 单 endpoint** — 必须先用 indexer(TzKT)查 op_hash → block_hash + validation_pass + index,再 `GET /chains/main/blocks/{block}/operations/{vp}/{index}`。E2 实证 `GET /chains/main/blocks/{BL7ke9…}/operation_hashes` HTTP:200 返二维数组(4 个 vp,每 vp 内一串 op_hashes),证实查找模型 |
| Explorer URL 格式 | `https://tzkt.io/{op_hash}` |

---

## 8. Mixed Set(`mixed` 模式权重)

```json
{
  "balance_query":        0.30,
  "tx_lookup":            0.15,
  "block_query":          0.20,
  "protocol_monitor":     0.10,
  "governance_monitor":   0.10,
  "counter_query":        0.05,
  "chain_id":             0.05,
  "version":              0.05
}
```

**权重和 = 1.00 ✅**

**chain-specific 部分**(0.10+0.10+0.05+0.05+0.05 = 0.35):
- `protocol_monitor` (0.10):`GET /chains/main/blocks/head/protocols` — Tezos 独有,protocol amendment 监控
- `governance_monitor` (0.10):`GET /chains/main/blocks/head/votes/current_period` — LPoS 投票周期监控
- `counter_query` (0.05):tx 构造前置
- `chain_id` (0.05):常量 endpoint
- `version` (0.05):node 版本

**总权重 1.00,余 0.65 给"通用 RPC 5 类"**(balance/tx/block 主路径)。

---

## 8.5 Phase 2.1 caller/reader 改造点(token-level Gate 3)

| # | 位置(file:line) | 改动 | 原因 |
|---|---|---|---|
| 1 | `config/config_loader.sh:666` `supported_blockchains` | 新增 `tezos` 入列 | adapter dispatcher 必经,漏入则 `--chain tezos` fail |
| 2 | `config/config_loader.sh:<新增 section>` `rpc_methods.tezos.mixed` | 添 §8 9 个 method(用 path 为 key,如 `"GET_contracts_balance": 0.30`)| vegeta target 生成器消费 |
| 3 | `config/config_loader.sh:<新增>` `param_formats.tezos` | 添 path-param schema:`addr_base58check` / `block_id_or_level` / `validation_pass_0..3` | `generate_rpc_json` REST 路径模板替换 |
| 4 | `tools/mock_rpc_server.py:<新增>` REST router(若 Aptos 已加 REST framework)| 添 `GET /chains/main/blocks/head/header` / `.../balance` 等 9 个 path handler,返 H8 实测样本 JSON | mock fallback 必须支持(否则 mock 模式 vegeta 全 404)|
| 5 | `tools/fetch_active_accounts.py:<新增 TezosAdapter>` | 实现 `fetch_addresses()`(走 TzKT `/v1/accounts?sort.desc=balance&limit=N` 即可)| adapter dispatcher 调用 |
| 6 | `analysis-notes/baseline-current-state.md` grep "tezos" | 同步加 Tezos family 行 | doc 与 plugin 真相对齐 |
| 7 | `analysis-notes/disk-and-network-pipeline-redesign.md` grep "tezos" | 同步加 family | 同上 |
| 8 | `analysis-notes/research_notes/<本文件名>.md` | 此 doc 即笔记本体 | N/A(本 doc 就是研究笔记) |
| 9 | `tests/<新增 test_tezos_smoke.sh>` | E2 smoke:9 个 method 各跑 1 次,断言 HTTP:200 | L1 smoke gate |

**Phase 2.1 完成后必须跑** `core/master_qps_executor.sh --chain tezos --mixed --duration 30`(若已有该 CLI),抓 vegeta 错误率,**所有请求都应是 200**,作为本链改造的 E2 证据。

---

## 9. Mock Notes(mock_rpc_server 实现要点)

- **请求路径(REST)**:**9 个 path**(见 §5),全部 `GET`,无 body
- **响应 schema**(贴 H8 实测主网真样本):
  ```jsonc
  // GET /chains/main/blocks/head/header  →  application/json
  {
    "protocol": "PtTALLiNtPec7mE7yY4m3k26J8Qukef3E3ehzhfXgFZKGtDdAXu",
    "chain_id": "NetXdQprcVkpaWU",
    "hash":     "BLffzWLDPFwcaDU4qYtnbpwTgNeWmE8FXUEgZVxCLjoJj6VGPtQ",
    "level":    13329316,
    "proto":    24,
    "predecessor": "BL2HKyw28VenRHfW3WP2NFvCavNqACDvqSRpkWu38GBzGBeSMut",
    "timestamp": "2026-05-23T18:44:13Z",
    "validation_pass": 4
  }

  // GET /chains/main/blocks/head/context/contracts/{addr}/balance
  "53"   // ← 是 string 包裹的数字,单位 mutez。注意 application/json 但响应是 bare string

  // GET /chains/main/chain_id
  "NetXdQprcVkpaWU"   // ← 同样 bare string
  ```
- **特殊错误码**:
  - **HTTP 400**(非 RPC code):bad address 返 `"Cannot parse contract id"`(纯 text,非 JSON)— **H8 实证**
  - **HTTP 404**:不存在的 block_id / contract 通常 404
  - **无 JSON-RPC envelope**(无 `{"error":{...}}`),错误是 HTTP 状态 + plain text body
- **Mock 实现复杂度**:**Medium**
  - 复杂点:(1)9 个 path 中部分含 2 个 path-param(`{block_id}` + `{addr}`);(2)响应有时是 bare JSON string(`"53"`、`"NetXdQprcVkpaWU"`)需小心 `json.dumps` 引号;(3)错误是 plain text 非 JSON
  - 简单点:全部 GET,无 body parse;无鉴权;path 模式固定

---

## 10. Adapter Reuse Decision(adapter 复用决策)

### 候选 adapter

| Adapter | 兼容度 | 缺失能力 |
|---|---|---|
| EthereumAdapter | 0% | JSON-RPC + hex addr + ABI 完全不同 |
| SolanaAdapter | 0% | JSON-RPC + Base58 addr(虽 Base58 alphabet 同,但 32 byte vs Tezos 20 byte;且 SolanaAdapter 假设 method-string 协议)|
| CosmosAdapter(若已建)| **~50%** | 同走 REST/HTTP,但 Cosmos path 是 `/cosmos/{module}/v1beta1/...` Cosmos-SDK 命名空间,addr 是 bech32(`cosmos1…`),不能直接复用 path 模板;但 vegeta target REST 生成器层共用 |
| AptosAdapter(若已建)| **~40%** | 同 REST,但 Aptos addr 是 `0x` hex,path 是 `/v1/accounts/...`,且依赖 Move struct_tag 语义;path 形态完全不同 |

### 决策

- [ ] 复用 `<adapter 名>`
- [x] **新建 `TezosAdapter`**(Tezos 独立 family;protocol upgrade + Michelson + Base58Check addr + 极深 path 都是 Tezos 独有)
- [x] **复用 REST 基础设施层**(plugin loader 的 `protocol_kind: rest` + `verb + path_template + path_params + response_path` schema,与 Cosmos REST/Aptos REST/Algorand REST 共享)
- [ ] 混合

### 理由

**第一段 — Adapter 类必须独立(语义层)**。Tezos 的 4-prefix Base58Check 地址(tz1/tz2/tz3/KT1)需要专用验证函数(确认前缀 + Base58Check 校验);Tezos 的 op_hash 查找需要先走 indexer 二级查询(Octez RPC 无 `getTxByHash`);Tezos 的 protocol_hash 监控(`/protocols` 返 next/current/expected_commit 三字段)是其他链都没有的概念;Tezos 的 mutez 单位是 10⁻⁶(与 Cosmos uatom 10⁻⁶ 巧合但语义不同)。这些语义都需要 `TezosAdapter` 内部专属方法,不能塞进 CosmosAdapter / AptosAdapter。

**第二段 — REST 协议层可复用(plugin schema 层)**。本调研 §11.7 实证四链(Cosmos REST / Aptos REST / Algorand REST / Tezos REST)全走 `<HTTP_VERB> <path>` + JSON 响应,**plugin schema 字段集合完全可统一**:`protocol_kind` / `verb` / `path_template` / `path_params` / `body_template`(可选)/ `response_path` / `path_param_url_encode` / `headers`(可选 auth 用)/ `monitor_headers`(Aptos 用)。Tezos 不需要新增 schema 字段(详见 §11.8 决策),只需复用 Cosmos/Aptos 已立的 REST schema。**这是 plugin 层最大的复用胜利**。

**第三段 — 唯一新增 schema 候选:`monitor_protocol_version`**(详见 §11.8 ASK)。Tezos 是当前 28 链中**唯一定期自动升级链上 protocol** 的链(每 ~3 个月 amendment 周期 → 新 protocol_hash → 新 RPC schema 可能不兼容),需要 plugin 自描述"我监控 protocol_hash,变化触发告警/重跑 schema 探活"。但这是**链特性字段**,不是 protocol-binding 字段,可放在 plugin 的 `chain_specific` 子节点,**不污染 REST 共用 schema**。

### 配置 JSON 示例(本链)

```json
{
  "chain": "tezos",
  "family": "tezos",
  "adapter": "TezosAdapter",
  "chain_id": "NetXdQprcVkpaWU",
  "protocol_kind": "rest",
  "rpc_endpoint": "https://mainnet.api.tez.ie",
  "rpc_endpoint_backup": "https://mainnet.smartpy.io",
  "indexer_endpoint": "https://api.tzkt.io",
  "block_time_ms": 6060,
  "finality_blocks": 2,
  "address_format": "base58check",
  "address_prefixes": ["tz1", "tz2", "tz3", "KT1"],
  "native_decimals": 6,
  "rpc_methods": {
    "block_height":       {"verb": "GET", "path": "/chains/main/blocks/head/header",
                           "response_path": "$.level"},
    "balance":            {"verb": "GET",
                           "path": "/chains/main/blocks/head/context/contracts/{addr}/balance",
                           "path_params": ["addr"],
                           "response_path": "$"},
    "tx_lookup":          {"verb": "GET",
                           "path": "/chains/main/blocks/{block}/operations/{vp}",
                           "path_params": ["block", "vp"],
                           "response_path": "$"},
    "chain_id":           {"verb": "GET", "path": "/chains/main/chain_id"},
    "version":            {"verb": "GET", "path": "/version"},
    "protocol_monitor":   {"verb": "GET", "path": "/chains/main/blocks/head/protocols",
                           "response_path": "$.protocol"},
    "governance_monitor": {"verb": "GET", "path": "/chains/main/blocks/head/votes/current_period"},
    "counter":            {"verb": "GET",
                           "path": "/chains/main/blocks/head/context/contracts/{addr}/counter",
                           "path_params": ["addr"]}
  },
  "mixed_weights": {
    "balance_query":      0.30,
    "tx_lookup":          0.15,
    "block_query":        0.20,
    "protocol_monitor":   0.10,
    "governance_monitor": 0.10,
    "counter_query":      0.05,
    "chain_id":           0.05,
    "version":            0.05
  },
  "chain_specific": {
    "monitor_protocol_version": true,
    "current_protocol_hash":    "PtTALLiNtPec7mE7yY4m3k26J8Qukef3E3ehzhfXgFZKGtDdAXu",
    "current_protocol_seq":     24
  }
}
```

---

## 11. DSL 字段需求(Q4=C 95% 0 Python declarative DSL 输入)

### 11.1 RPC 调用协议

`protocol_kind: "rest"` — 与 Cosmos REST / Aptos REST / Algorand REST 同(plugin schema 4 链共用)。**无 JSON-RPC body**,**无鉴权**(public)。

### 11.2 method 调用 schema(每 method 一节)

格式统一为 `{verb, path, path_params?, body_template?, response_path}`(REST 通用)。详见 §10 配置 JSON。**Tezos 不需要 `body_template`**(全部 GET);**部分 method 需要 1-2 个 `path_params`**(`addr` / `block` / `vp`)。

### 11.3 cursor / pagination 模型

**Tezos Octez RPC 无原生分页**(全是按 block / address 直接查)。需要扫历史时:
- (a) 按 level 数字递减(`/chains/main/blocks/{level-1}/...`)
- (b) 沿 `predecessor` block_hash 反向链(每个 header 返 `predecessor`)

二者均无 `next_cursor` 字段,**DSL 不需要为 Tezos 引入新 pagination 字段**;但若 plugin 想表达"按 block 链分页",可复用 Substrate `parent_hash` 模式(`pagination_kind: "linked_list_by_field"` + `field: "predecessor"`)。

**TzKT indexer** 用 query string `?sort.desc=level&limit=N&offset.cr=<id>`(cursor),但 indexer 与 Octez RPC 是两套 API,**plugin 应分别注册**(`rpc_endpoint` vs `indexer_endpoint`)。

### 11.4 system addresses / 过滤规则

- **Burn address**:`tz1burnburnburnburnburnburnburjAYjjX`(社区约定)— ⚠️ 未 E2 验证此地址实际存在
- **Bakers**(系统地位高,可能想从 mixed set 排除以避免热点):`tz1KqTpEZ7Yob7QbPE4Hy4Wo8fHG8LhKxZSx`(本调研 E2 实证活)等几十个,完整列表需走 TzKT `/v1/delegates?active=true&sort.desc=delegatedBalance`
- **Framework system contracts**(若有):Tezos 无 EVM 风格的 precompile 地址(0x1-0xa);各 protocol 自带的 voting/baking 逻辑都在 protocol 内部,不暴露为可调用合约

### 11.5 异构性标记(对比现有 8 链 + 本调研)

| # | 维度 | Tezos | 对照(其他 8 链)|
|---|---|---|---|
| 1 | 协议 | **REST** | EVM/Solana/NEAR/Cosmos-RPC/Substrate/Bitcoin = JSON-RPC;Aptos = REST;Cosmos-REST = REST |
| 2 | 地址 | **Base58Check 36 字符 + 4 prefix** | Ed25519 Base58(Solana)/ hex(EVM/Aptos)/ Bech32(Cosmos)/ SS58(Substrate)/ string(NEAR) |
| 3 | tx hash | **Base58Check 51 字符 `o` 系列** | Hex 64(EVM/Bitcoin)/ Base58(Solana)/ Hex 大写(Cosmos)/ Base58(NEAR)|
| 4 | block id | **3 种**:`head` / level(数字) / hash(`B...` Base58Check)| EVM = `latest`/数字/hex hash;Solana = slot 数字;NEAR = `final`/`optimistic`/数字/hash(NEAR 最灵活)|
| 5 | finality 字段 | **无显式**(只能查 `protocols`/`head` 推断,无 `finalized` block tag)| NEAR 有 `finality: final/optimistic`;EVM 有 `finalized`/`safe` tag;Solana 有 commitment |
| 6 | tx 查询模型 | **必须先 indexer 反查 block + vp + index**,Octez RPC 无 `getTxByHash` | EVM/Solana/NEAR 都有 `getTransaction(hash)` 单 endpoint |
| 7 | protocol 升级 | **链上 amendment**(protocol_hash 会变,RPC schema 可能变)| **28 链中独此一家**;EVM hard fork 是社区协调,RPC method 名稳定 |
| 8 | 鉴权 | public | Algorand 需 X-Algo-API-Token;余多数 public |

### 11.6 DSL 设计 ASK(给 P2-DESIGN-v2 的需求)

1. **`protocol_kind: rest`** — 已被 Cosmos/Aptos 提请,Tezos 复用,**无新增**。
2. **`verb + path_template + path_params`** — 已被 Cosmos/Aptos 提请,Tezos 复用,**无新增**。
3. **`response_path`(JSONPath-lite)** — 已被 Aptos/NEAR 提请,Tezos 复用,**无新增**。
4. **`bare_string_response: true`(候选新字段)** — Tezos 多个 endpoint 返 bare JSON string(`"53"`、`"NetXdQprcVkpaWU"`),不是 object。DSL 解析器若硬假设 `dict` 会出 TypeError。**ASK:DSL 解析器需对 `bare_string_response` 容错**(或显式声明字段)。
5. **`monitor_protocol_version: true`(候选新字段,Tezos 独有)** — 详见 §11.8。**ASK:同意新增此 chain_specific 字段(不放 REST 共用 schema)。**
6. **`indexer_endpoint`(候选新字段)** — Tezos 的 tx_lookup 必须先经 indexer 反查;Aptos 也有类似(`fullnode` vs `indexer.mainnet.aptoslabs.com`);Cosmos 部分链有 mintscan;**ASK:DSL 是否需统一抽象 `endpoints: { rpc: ..., indexer: ..., explorer: ... }` 结构?**

### 11.7 Tezos vs 已 commit REST 链对比(本节强制要求 — 4 链 REST 实证横评)

> 本节所有列均为 H8/E2 实测(2026-05-23 ~18:44 UTC)。未实测项 ⚠️。
> Algorand 行:本调研未在 docs/zh/chains/ 找到 Algorand commit 文件(8 链中无),Algorand 列由**本调研单独 E2 实测** AlgoNode endpoint 填,但**未做完整 docs 调研**,仅作为 P1.2 Wave3 表内参考,⚠️ 标"未做完整调研"。

| 维度 | Cosmos REST(05-cosmos-hub)| Aptos REST(04-aptos)| Algorand REST(⚠️ 仅本表 E2,未完整 doc)| **Tezos REST(本调研)** |
|---|---|---|---|---|
| 协议 | REST/HTTP/JSON — **E2** | REST/HTTP/JSON — **E2** | REST/HTTP/JSON — **E2** `https://mainnet-api.algonode.cloud/v2/status` HTTP:200 | REST/HTTP/JSON — **E2** `https://mainnet.api.tez.ie/version` HTTP:200 |
| 鉴权 | public(publicnode)— **E2** | public(aptoslabs)— **E2** | public(AlgoNode 公益);商业(PureStake)需 `X-Algo-API-Token` — E3 文档 | public(ECAD/SmartPy)— **E2** |
| 路径深度 | 中(3-4 段)`/cosmos/bank/v1beta1/balances/{addr}` — **E2** | 浅(2-3 段)`/v1/accounts/{addr}` — **E2** | 浅(2-3 段)`/v2/accounts/{addr}` — E3 文档 | **深(5-7 段)**`/chains/main/blocks/head/context/contracts/{addr}/balance` — **E2(7 段)** |
| balance 路径 | `GET /cosmos/bank/v1beta1/balances/{addr}` 返 `{balances:[{denom,amount}]}` 数组 — **E2** | `POST /v1/view` body `{function:"0x1::coin::balance",...}` 返 array of string — **E2** | `GET /v2/accounts/{addr}` 返大 object 含 `amount`(microalgos)— E3 文档 | `GET /chains/main/blocks/head/context/contracts/{addr}/balance` 返 **bare string** `"53"`(mutez)— **E2** |
| 高度参数 | path `/blocks/{height}` 或 grpc-metadata `x-cosmos-block-height` — **E2** | header `x-aptos-block-height`(响应)/ query `?version=N`(请求)— **E2** | path `/v2/blocks/{round}` — E3 文档 | **path** `/chains/main/blocks/{level\|hash\|head}/...`(3 种 id 形态)— **E2** |
| pagination | `pagination.limit` + `pagination.key`(opaque base64 cursor)— **E2** | `start: <version>` + `limit`(数值游标)— **E2** | `?next: <token>`(opaque)+ `?limit` — E3 文档 | **无原生分页**;按 level 递减 / 沿 `predecessor` 链反查 — **E2** |
| protocol 版本字段 | `chain-id: "cosmoshub-4"` 字符串,固定 — **E2** | `x-aptos-chain-id: 1` 数字 header,固定 — **E2** | `genesis-hash-b64: "wGHE2P..."` 字符串,固定 — E3 文档 | **`protocol_hash: "PtTALLi..."` Base58Check,动态升级**(每 ~3 个月一次)— **E2** |
| 响应错误格式 | HTTP code + `{code,message,details}` JSON — E2 ✅ | HTTP code + `{message, error_code, vm_error_code}` JSON — E2(Aptos 04-doc)| HTTP code + `{message: "...."}` JSON — ⚠️ 未 E2 错误路径 | **HTTP 4xx + plain text**(非 JSON,如 `"Cannot parse contract id"`)— **E2 ✅ 400** |
| 响应 JSON 结构 | 全 object — E2 | 全 object 或 array of object — E2 | 全 object — E3 | **混合**:多数 object,但 `/balance` `/chain_id` 返 **bare JSON string** — **E2(独此一家)** |
| tx_lookup 模型 | `GET /cosmos/tx/v1beta1/txs/{HEX}` 单步 — E2 | `GET /v1/transactions/by_hash/{0xhex}` 单步 — E2 | `GET /v2/transactions/pending/{txid}` + indexer `/v2/transactions/{txid}` — E3 | **必须两步**:indexer 反查 → `GET /blocks/{block}/operations/{vp}/{index}` — **E2** |
| DSL schema 复杂度增量 | Low(纯 path + JSON)| Low-Med(`POST /view` body 模板 + URL encoding policy + `monitor_headers`)| Low(path + bearer header)— ⚠️ | **Med**(path 深 + bare-string 响应 + 错误是 plain text + protocol_hash 监控 + tx_lookup 两步)|

**统计**:全部 4 链共用 REST/HTTP/JSON 主路径 + 几乎全 public + GET 主导。**4 链 plugin schema 字段集合 95% 重合**(`protocol_kind/verb/path_template/path_params/response_path` 5 字段都用)。Tezos 引入的**新需求只有 2 个细节**:`bare_string_response` 容错(small) + `monitor_protocol_version` 独有(chain_specific,不污染共用 schema)。

### 11.8 DSL 选择建议(本节强制要求 — 关键产出)

**决策**:

- [x] **复用 Cosmos/Aptos REST DSL infra**(`protocol_kind: rest` + `verb` + `path_template` + `path_params` + `response_path`)
- [ ] Tezos 路径过深 → 新增 `path_template_max_depth` 配置 — **拒绝**(详见理由第二段)
- [ ] Tezos 路径过深 → 拆 path segment 数组 — **拒绝**(详见理由第二段)
- [x] **`monitor_protocol_version: true` 字段** 加入 `chain_specific` 子节点(**不**放共用 REST schema)
- [x] **`bare_string_response: true`** 加入 method 级可选字段(REST 共用)
- [x] **`indexer_endpoint`** 加入顶层 endpoint 结构(REST 共用,Aptos/Cosmos 也可用)

**理由(3 段)**:

**第一段 — REST infra 复用度极高(95%),Tezos 不需要新协议层抽象**。本节 11.7 实证 4 链 REST(Cosmos / Aptos / Algorand / Tezos)的 plugin schema 字段需求完全重合在 5 个核心字段上:`protocol_kind`(rest)/ `verb`(GET 主)/ `path_template`(含 `{param}` 占位符)/ `path_params`(数组)/ `response_path`(JSONPath-lite)。Tezos 没有引入任何新的协议层概念 — `GET /chains/main/blocks/head/context/contracts/{addr}/balance` 用 Cosmos 已有的同套 schema 一行就能表达。这意味着 plugin loader 写一次 REST handler,**4 条链全覆盖**。这与 EVM family 5 链共用 EthereumAdapter 的复用模式同质 — **协议层是真复用,语义层各自实现**。

**第二段 — 路径深(7 段)不构成 schema 问题,无需新增 max_depth 或 segment 数组**。Tezos 的 `/chains/main/blocks/head/context/contracts/{addr}/balance` 路径虽然比 Cosmos 的 `/cosmos/bank/v1beta1/balances/{addr}` 深 2-3 段,但 plugin schema 表达方式完全一致 — 都是单字符串 `path_template` + `path_params` 数组。**深路径只是字符串长一点,不是 schema 结构问题**。引入 `path_template_max_depth` 字段或拆 segment 数组反而是 over-engineering(token-level "把简单做成复杂"反模式):字符串拼接已经能干净处理任意深度,segment 数组需要新的拼接 helper、新的 URL encoding 边界处理、新的转义规则,**增加约 60 行 plugin loader 代码却 0 收益**。**决定:rejected,Tezos 走纯字符串模板**,与 Cosmos/Aptos/Algorand 完全同套。

**第三段 — 唯一真正的新需求是 `monitor_protocol_version`,但放在 chain_specific 不污染 REST 共用 schema**。Tezos 是 28 链中**唯一定期自动升级链上 protocol** 的链 — 当前 protocol_hash 是 `PtTALLi…`(第 24 个 protocol,本调研 E2 实证),历史已升过 23 次,平均 ~3 个月一次新 amendment。新 protocol 上线可能引入新 RPC method、修改响应字段、改 mutez 显示精度等(历史前例:Florence → Granada 改 baking accounts)。**这意味着 Tezos plugin 必须监控 `GET /chains/main/blocks/head/protocols`,当 `protocol` 字段变化时:(a) 告警(schema 可能漂移) (b) 自动触发 schema regression(把 §5 9 个 method 各跑一次断言 HTTP:200)**。但这个字段是 Tezos chain 特性,不是 REST 协议特性 — **正确归宿是 plugin 的 `chain_specific` 子节点**(同 Aptos `monitor_headers` 放 chain_specific 一样),plugin loader 在 chain_specific 上做 dispatch,不污染 4 链共用的 REST 主 schema。**最后一句**:`bare_string_response: true` 和 `indexer_endpoint` 是 REST 共用层 small adds(< 5 行 schema),无负担。

**结论一句话**:**Tezos 99% 复用 Cosmos/Aptos REST DSL infra(只加 `bare_string_response` + `indexer_endpoint` 两小字段进共用层);`monitor_protocol_version` 是 Tezos chain_specific 独有,放 chain_specific 子节点;Adapter 新建 `TezosAdapter`(独立 family),与 Cosmos/Aptos REST adapter 平级。** ✅

---

## 9.9 真实信源覆盖与时间戳

| 信源类型 | URL/路径 | 访问日期(UTC)| 状态 |
|---|---|---|---|
| ECAD `/version` | `GET https://mainnet.api.tez.ie/version` | 2026-05-23 18:44 | **H8:200,Octez v24.4 release commit 56bd3e33** |
| ECAD `/chains/main/blocks/head/header` | 同上 | 2026-05-23 18:44 | **H8:200,chain_id=NetXdQprcVkpaWU,protocol=PtTALLi…,level=13329316,proto=24** |
| ECAD `/balance` tz1 | `.../contracts/tz1KqTpEZ7Yob7QbPE4Hy4Wo8fHG8LhKxZSx/balance` | 2026-05-23 18:44 | **H8:200,`"53"` mutez** |
| ECAD `/balance` KT1 | `.../contracts/KT1WvzYHCNBvDSdwafTHv7nJ1dWmZ8GCYuuC/balance` | 2026-05-23 18:44 | **H8:200,`"108962378338"` mutez** |
| ECAD `/balance` bad addr | `.../contracts/tz1notarealaddress/balance` | 2026-05-23 18:44 | **H8:400 + plain text 错误(非 JSON)** |
| ECAD `/chain_id` | `.../chains/main/chain_id` | 2026-05-23 18:44 | **H8:200,bare string `"NetXdQprcVkpaWU"`** |
| ECAD `/protocols` | `.../protocols` | 2026-05-23 18:44 | **H8:200,returned ~30+ Base58Check protocol hashes(全 protocol 历史)** |
| ECAD `/counter` | `.../contracts/tz1Kq.../counter` | 2026-05-23 18:44 | **H8:200,`"8190584"`** |
| ECAD `/blocks/{level}/header` 历史 | `.../blocks/13329000/header` | 2026-05-23 18:44 | **H8:200,level=13329000 @ 2026-05-23T18:12:19Z(用于推算 block_time ≈ 6.06s)** |
| ECAD `/blocks/{hash}/operation_hashes` | `.../blocks/BL7ke9KaSf4…/operation_hashes` | 2026-05-23 18:44 | **H8:200,二维数组(4 validation_pass × N op_hashes)** |
| ECAD `/operations/3` | `.../blocks/head/operations/3` | 2026-05-23 18:44 | **H8:200,数组 of op,每 op 含 protocol/chain_id/hash/branch** |
| SmartPy `/version` | `GET https://mainnet.smartpy.io/version` | 2026-05-23 18:44 | **H8:200,同 Octez v24.4 release** |
| TzKT `/v1/operations/transactions` | `GET https://api.tzkt.io/v1/operations/transactions?limit=1&sort.desc=level` | 2026-05-23 18:44 | **H8:200,真实 op_hash `ong1822VPmQwj…`,level=13329321,block=BL7ke9KaSf…** |
| TzKT `/v1/operations/{hash}` | `GET .../ong1822VPmQwj…` | 2026-05-23 18:44 | **H8:200,完整 tx 详情** |
| TzKT `/v1/contracts?kind=smart_contract&sort.desc=numTransactions` | 同根 | 2026-05-23 18:44 | **H8:200,取真实 KT1 = objkt.com Marketplace v2** |
| **Cross-chain Cosmos REST** | `GET https://cosmos-rest.publicnode.com/cosmos/base/tendermint/v1beta1/node_info` | 2026-05-23 18:44 | **H8:200**(用于 §11.7 对比验活) |
| **Cross-chain Aptos REST** | `GET https://fullnode.mainnet.aptoslabs.com/v1` | 2026-05-23 18:44 | **H8:200,chain_id=1,block_height=783409612**(对比验活) |
| **Cross-chain Algorand REST** | `GET https://mainnet-api.algonode.cloud/v2/status` | 2026-05-23 18:44 | **H8:200,catchup-time=0**(对比验活) |
| Octez RPC 文档 | https://tezos.gitlab.io/active/rpc.html | 2026-05-23 | E1(引用,未 DOM)|

---

## Open Questions(待解决问题)

1. **Algorand 完整调研缺失** — 本表 §11.7 Algorand 列仅 E2 探活,未做完整 docs。Phase 2.x 加 Algorand 时需独立调研 doc。
2. **Tezos finality 实测缺失** — Tenderbake 文档说 2 block 终结性,本调研未 E2 对比 head 与 finalized block 差值(Octez RPC 路径 `/chains/main/blocks/head~2/header` 是否合规约定?)
3. **`/protocols` 字段语义不全验** — H8 看到返 30+ Base58 string 数组(`["ProtoALphaALpha…", "ProtoDemoCounter…", "PrqoTUFUrorf…", ...]`)— 但**这是 node 已知的全部 protocol 列表**,不是 active+next。**真正的 active protocol 应从 `/chains/main/blocks/head/protocols` 返 `{protocol, next_protocol}` object 读取** — 本调研用 head/header 拿到 `protocol` 字段了,但 head/protocols 字段未单独实测,⚠️。
4. **block_time 推算 6.06s vs 文档 10s** — H8 实测 1914s/316 blocks=6.06s,与一般文献报"~10s"出入。可能是当前 protocol 24(PtTALLi) `minimal_block_delay` 改成 6s 了 — ⚠️ 未查 protocol constants,Phase 2.x 调用 `/context/constants` 求证。
5. **mock_rpc_server REST framework** — Tezos 是继 Cosmos/Aptos/Algorand 之后第 4 条 REST 链,**Phase 2.0 应正式拆 mock_rpc_server 为 REST + JSON-RPC 双 handler**(否则 token-level Case-D:多链拼凑越改越乱)。
6. **`bare_string_response` 实现** — DSL parser 当前是否假设全部响应是 dict?Phase 2.x 加 Tezos 前先验证 plugin loader 对 bare string `"53"` 不 TypeError。
7. **protocol amendment 演习** — Tezos 上一次 protocol 升级(`P` → `Pt`)某些 RPC schema 改了。Phase 2.x 接入后,**是否需要建 protocol amendment dashboard alert**?(本 §11.8 已写需 monitor,但具体告警通道未定)
8. **`indexer_endpoint` 抽象层** — 若引入,Aptos / Cosmos / Tezos 都需在 plugin 顶层 endpoints 结构填,且 indexer URL 路径完全异(TzKT vs Aptos Indexer GraphQL vs Mintscan),DSL 是否还需 indexer protocol_kind?Phase 2.0 决策。

---

## Changelog

| Date | Author | Change |
|---|---|---|
| 2026-05-23 | Hermes Agent | 初次调研:H8 实证 ECAD `/version` `/header` `/balance`(tz1+KT1+bad)`/chain_id` `/protocols` `/counter` `/blocks/{level}/header` `/operation_hashes` `/operations/3` 共 10 个 endpoint;TzKT `/operations` + `/contracts` 反查;SmartPy `/version` 备份;cross-chain Cosmos/Aptos/Algorand REST 探活;§11.7 4 链 REST 横评 + §11.8 复用决策(95% 复用,仅加 `bare_string_response` + `indexer_endpoint` 进共用层,`monitor_protocol_version` 进 chain_specific) |
