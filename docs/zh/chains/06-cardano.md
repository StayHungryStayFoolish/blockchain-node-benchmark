# 06 — Cardano 调研稿

> **版本**:v1.0(初稿,Phase 1.2 Wave2)
> **调研日期**:2026-05-23
> **作者**:Hermes Agent
> **状态**:🟢 待 user review(P1-USER-REVIEW 卡点 + 关键架构决策见 §11.8)
> **真实证据严格遵守 H8**:本稿所有关键字段附 E1-E5 标记(E1=单元测试 / E2=curl 实证 / E3=官方文档 / E4=GitHub 源码 / E5=框架 grep)。
> **本链特殊性(28 链中唯一)**:cardano-node 原生**不暴露任何 HTTP RPC**,公网访问必须经过 middleware(Blockfrost / Koios / Ogmios / cardano-graphql)。DSL 必须能表达 "通过哪个 middleware 访问",详见 §11。

---

## 元信息

| 项 | 值 |
|---|---|
| 链名(中) | Cardano |
| 链名(英) | Cardano |
| 编号 | 06 |
| Mainnet ChainID | `1`(数字),Network Magic `764824073`;在 Koios 上不直接暴露 chain_id 字段,但 era=`Conway`、epoch=632 可唯一定位 mainnet — E2 实测 `https://api.koios.rest/api/v1/tip` |
| 节点应用 | **cardano-node**(Haskell 实现,IOG 维护);本调研访问的是 **Koios middleware**(cardano-node + cardano-db-sync + PostgREST + HAProxy 集群)— E3 |
| 调研日期 | 2026-05-23 |
| 调研者 | Hermes Agent |
| 状态 | 🟢 已完成(框架尚未支持本链,本调研为 Phase 2.x plugin 引入做准备) |
| 框架是否已支持 | ❌ — E5: `config/config_loader.sh:666` `supported_blockchains=(solana ethereum bsc base scroll polygon starknet sui)`,不含 cardano |

---

## 1. Sources(权威来源)

| 类型 | URL | 访问日期 | 备注 |
|---|---|---|---|
| 官方文档(Cardano) | https://docs.cardano.org/ | 2026-05-23 | Cardano 协议规范主页 |
| 官方文档(cardano-node) | https://github.com/IntersectMBO/cardano-node | 2026-05-23 | node 实现 + 配置 |
| Cardano CIP(改进提案) | https://cips.cardano.org/ | 2026-05-23 | 地址格式 CIP-19、token CIP-25/68 等 |
| **Blockfrost API 文档** | https://docs.blockfrost.io/ | 2026-05-23 | REST middleware,需 project_id |
| **Koios API 文档** | https://api.koios.rest/ | 2026-05-23 | 社区 REST middleware,免费无 key |
| **Ogmios API 文档** | https://ogmios.dev/ | 2026-05-23 | WebSocket JSON-RPC 包装 |
| **cardano-graphql** | https://github.com/cardano-foundation/cardano-graphql | 2026-05-23 | GraphQL middleware |
| GitHub(Koios) | https://github.com/cardano-community/koios-artifacts | 2026-05-23 | Koios 实现源码 |
| Explorer(Cardanoscan) | https://cardanoscan.io/ | 2026-05-23 | 地址/tx 浏览器,可验真实数据 |
| Explorer(Cexplorer) | https://cexplorer.io/ | 2026-05-23 | 备用 explorer |

---

## 2. Protocol Family(协议族)

| 项 | 值 |
|---|---|
| Family | **Cardano(EUTXO + Ouroboros)**,**独立族**,与 Bitcoin UTXO 形似神不同(EUTXO 含 datum + script + reference inputs) |
| Consensus | **Ouroboros Praos**(PoS,基于 VRF 的 slot leader 选举)— E2 实测 `vrf_key`、`op_cert` 字段确认 |
| VM | **Plutus**(基于 Haskell 的脚本语言,Plutus V1/V2/V3),非 EVM/WASM/MoveVM |
| Block Time | **平均 ~20 秒/block**(active slot coefficient `f=0.05`,1 slot = 1s,期望每 20 slot 一个块);E2 实测 epoch_slot=333120 / block_no=13456426,与官方一致 |
| Finality | **概率性最终**,常规视 ~36 slots(~12 min)为安全;Ouroboros Genesis 提供更强保证 |
| Reuse Existing Adapter? | **No,需新建 CardanoAdapter**:1) EUTXO 与 Bitcoin UTXO 数据结构差异大(datum/script);2) 无原生 HTTP RPC,需 middleware 抽象层;3) 地址格式 Bech32 + 多类型(payment / stake / script);4) 资产模型 native multi-asset(非 token contract) |
| 本族链数(框架计划内) | 1 条(Cardano mainnet),无 sister chain(Cardano 不支持 EVM,无平行链) |

---

## 3. Public RPC / Middleware(公共节点)

### ⚠️ 关键:Cardano 原生 cardano-node **不暴露 HTTP**,只有本地 Unix socket(`cardano-node-socket-path`),公网必须通过 middleware

### 端点候选(实测)

| Endpoint | Middleware 类型 | Auth | 实测状态 | 备注 |
|---|---|---|---|---|
| `https://api.koios.rest/api/v1` | **Koios REST**(PostgREST + cardano-db-sync) | 无 key | ✅ HTTP 200(E2,多次实测) | 社区免费集群,推荐 |
| `https://cardano-mainnet.blockfrost.io/api/v0` | **Blockfrost REST** | **必须 `project_id` header**(注册免费拿) | ⚠️ HTTP 403(E2,无 key 调用)— `{"error":"Forbidden","message":"Missing project token. Please include project_id in your request."}` | 需注册,免费层 50k/天 |
| `wss://ogmios-api.mainnet.dandelion.link/` | **Ogmios WebSocket** | 无 | ❌ HTTP 000(E2,2026-05-23 实测域名解析/连接失败,Dandelion 公共端点已下线) | 历史上 Dandelion 提供,**目前必须自部署** |
| `https://graphql-api.mainnet.dandelion.link/` | **cardano-graphql** | 无 | ❌ HTTP 000(E2,同上,Dandelion 下线) | **目前必须自部署** |

**Trade-off**:仅 Koios + Blockfrost 有可用公共端点。Ogmios/cardano-graphql 的免费公共端点(历史 Dandelion / Demeter)在本次调研窗口实测全部不可达;若要使用,**必须自部署**(增加 benchmark 部署成本)。**Koios 是 mock-fallback 唯一无 key 选择**。

### curl 实测(2026-05-23 ~18:18 UTC 真实执行,**数值字段有时效性**)

#### 3.1 Koios `/tip`(节点高度 + epoch + slot)

```bash
$ curl -s https://api.koios.rest/api/v1/tip
[{"hash":"5c7f63267a7f9fce7a464c4b70ed1ceda01903f99fca69aa73e0a235b23b085d",
  "epoch_no":632,
  "era":"Conway",
  "abs_slot":187993920,
  "epoch_slot":333120,
  "block_height":13456426,
  "block_no":13456426,
  "block_time":1779560211}]
# 解读:era=Conway(2024-09 hard fork 后的当前 era),height=13456426
```

#### 3.2 Koios `/blocks?limit=1`(最新块元数据)

```bash
$ curl -s "https://api.koios.rest/api/v1/blocks?limit=1"
[{"hash":"5c7f63267a7f9fce7a464c4b70ed1ceda01903f99fca69aa73e0a235b23b085d",
  "epoch_no":632, "abs_slot":187993920, "block_height":13456426,
  "block_size":12565, "block_time":1779560211, "tx_count":4,
  "vrf_key":"vrf_vk17h65ynw5n8lv5mux0gn645yd82prtqj2a0f85u6rdp05e045050qawtgmm",
  "pool":"pool1edqwpnln3zr9gj9sfsmyl72pen6hdwev07xgqj7uz5mkjrgfj6h",
  "proto_major":11, "proto_minor":0,
  "parent_hash":"d145b51828323cf1e6ebb40f1f178bdffc802f71b1729bd3694bba688fbd576e"}]
```

#### 3.3 Koios `POST /address_info`(地址余额 + UTXO 集)

```bash
$ curl -s -X POST https://api.koios.rest/api/v1/address_info \
    -H "Content-Type: application/json" \
    -d '{"_addresses":["addr1qxahjgt8c9fsjrc8g0937h5q2cqpyglq9kyy62834ngfyct0kzq5as673n2e05chwvsptgx0ngwtggj20shf84h4fx0qm4kw4a"]}'
[{"address":"addr1qxahjgt8c...m4kw4a",
  "balance":"3354648444",          # lovelace,即 3354.648444 ADA
  "stake_address":"stake1u9hmpq2wcd0ge4vh6vthxgq45r8e5895yf98ct5n6m65n8sxlwymg",
  "script_address":false,
  "utxo_set":[{"value":"5000000","tx_hash":"422f17c048...","tx_index":0,
               "asset_list":[], "block_time":1752445699, "block_height":12121688,
               "datum_hash":null, "inline_datum":null, "reference_script":null}, ...]}]
# 注意:`balance` 是 String(避免 JS Number 精度丢失,与 Cosmos REST 风格一致)
# `utxo_set` 含 EUTXO 特有字段:datum_hash / inline_datum / reference_script
```

#### 3.4 Koios `POST /tx_info`(交易详情)

```bash
$ curl -s -X POST https://api.koios.rest/api/v1/tx_info \
    -H "Content-Type: application/json" \
    -d '{"_tx_hashes":["a8aabe32bfb7b23a98c94b5037b60e4fedce468334ccaf94cdb642a9a47bc371"]}'
[{"tx_hash":"a8aabe32...","block_height":13456426,
  "tx_size":2205, "total_output":"3237701515", "fee":"606247",
  "invalid_after":"188000808",
  "collateral_inputs":[], "reference_inputs":[],
  "inputs":[...], "outputs":[
    {"value":"3235081035", "asset_list":[],
     "payment_addr":{"bech32":"addr1qxahjgt8c..."}, ...}
  ]}]
# EUTXO 关键字段:collateral_inputs(Plutus 失败抵押) / reference_inputs(CIP-31)
```

#### 3.5 Koios `POST /asset_info`(原生资产信息,Cardano native multi-asset)

```bash
$ curl -s -X POST https://api.koios.rest/api/v1/asset_info \
    -H "Content-Type: application/json" \
    -d '{"_asset_list":[["f0ff48bbb7bbe9d59a40f1ce90e9e9d0ff5002ec48f232b49ca0fb9a","000de140337574786f6361706974616c"]]}'
[{"policy_id":"f0ff48bb...", "asset_name":"000de140337574786f6361706974616c",
  "asset_name_ascii":"3utxocapital", "fingerprint":"asset13g6k8tgn0wuzhkgnlhkzmzyvunqd9sgukyd9gq",
  "total_supply":"1", "mint_cnt":1, "burn_cnt":0,
  "minting_tx_metadata":{"721":{...CIP-25 NFT metadata...}}}]
# Cardano 资产不在合约里,而是 native(policy_id + asset_name 组合 = 唯一 asset)
```

#### 3.6 延迟基线(Koios `/tip`,3 次连续调用)

```bash
$ for i in 1 2 3; do curl -s -o /dev/null -m 10 -w "tip call $i: %{time_total}s HTTP:%{http_code}\n" \
    "https://api.koios.rest/api/v1/tip"; done
tip call 1: 0.879014s HTTP:200
tip call 2: 0.681689s HTTP:200
tip call 3: 0.802307s HTTP:200
# 平均 ~0.78s(注:从中国到 Koios 公益集群,跨地理延迟为主)
```

### Rate limit(实测响应头)

```bash
$ curl -sI https://api.koios.rest/api/v1/tip
HTTP/2 200
date: Sat, 23 May 2026 18:19:08 GMT
content-range: 0-0/*
content-type: application/json; charset=utf-8
x-frame-options: DENY
# ⚠️ Koios 公开响应**不返回明确的 x-ratelimit-* header**(实测 2026-05-23);
# 官方文档(api.koios.rest 主页)说明:免费层是 IP-based,无明确数字限制,但禁止滥用。
# 推荐自部署 instance(社区提供 Koios stack 一键脚本)做生产 benchmark。
```

---

## 4. Account Model(账户模型)

| 项 | 值 |
|---|---|
| 模型 | **EUTXO**(Extended UTXO)— 与 Bitcoin UTXO 同源,但 UTXO 携带 datum / script / reference,可承载 Plutus 智能合约状态 |
| Native token decimals | **6**(ADA 主单位,1 ADA = 1,000,000 lovelace);native asset 由 CIP-67 元数据声明 decimals |
| Address derivation | **Ed25519**(payment key 和 stake key 均 Ed25519,与 Solana 同曲线,但地址格式不同) |
| Special account types | 1) **Payment address**(`addr1...`,可签出);2) **Stake address**(`stake1...`,委托用,不持币);3) **Script address**(`addr1z...` 或 `addr1w...`,Plutus 合约持币);4) **Reward address**(领取 staking 奖励)— E2 实测 `address_info.stake_address` 字段证实 |
| 资产模型 | **Native multi-asset**(非合约!),`asset_id = policy_id (28 bytes hex) + asset_name (≤32 bytes hex)`,所有原生资产享受与 ADA 同样的账本级保证 |

---

## 5. Core RPC / Middleware Methods(本框架监控所需)

> 仅列**本基准测试框架**需要的 method(以 Koios REST 为基准)。完整 API 列表参考 https://api.koios.rest/。

| Method | HTTP | 类别 | 说明 | 在 mixed 中权重建议 |
|---|---|---|---|---|
| `GET /tip` | GET | block height | 探活 + 高度同步检查(类似 `eth_blockNumber`) | 0.05 |
| `GET /blocks?limit=N` | GET | block list | 最新 N 个区块的元数据 | 0.05 |
| `POST /block_info` | POST | block content | 给定 hash 列表返回完整块信息 | 0.05 |
| `POST /block_txs` | POST | block tx list | 给定 block_hash 返回 tx_hash 列表(轻量) | 0.05 |
| `POST /tx_info` | POST | tx lookup | 给定 tx_hash 列表返回完整交易(含 EUTXO inputs/outputs) | 0.20 |
| `POST /tx_utxos` | POST | tx utxo | 仅返回 tx 的 inputs/outputs UTXO(更轻量) | 0.05 |
| `POST /address_info` | POST | balance | **地址余额 + UTXO 集**(Cardano 的 "getBalance" 等价) | 0.25 |
| `POST /address_assets` | POST | token balance | 地址持有的所有原生资产 | 0.15 |
| `POST /asset_info` | POST | asset metadata | 原生资产元数据(类似 ERC20 metadata,但是 native) | 0.10 |
| `GET /epoch_params` | GET | chain params | 当前 epoch 的协议参数(min_fee_a/b、max_tx_size 等) | 0.05 |

**总权重必须 = 1.0** ✅(0.05×5 + 0.20 + 0.25 + 0.15 + 0.10 = 1.00)

**关键差异 vs EVM/Solana**:
- 大多数读 method 是 **POST**(因为入参是数组,RESTful 设计选择 body 传 list)。Vegeta target 生成器必须支持 POST body + JSON content-type。
- 无 `eth_call` 等价,智能合约状态查询走 `script_info` / datum 查询。

---

## 6. Address Format(地址格式)

| 项 | 值 |
|---|---|
| 编码 | **Bech32**(CIP-19),`hrp = "addr"`(mainnet payment)或 `"stake"`(mainnet stake)或 `"addr_test"`(testnet) |
| 长度 | **payment addr 约 103 字符**(包括 hrp);stake addr 约 59 字符 — E2 实测 |
| Checksum | **有**(Bech32 BCH 校验,5 个字符 in 32-character alphabet) |
| 示例(主网真实地址) | `addr1qxahjgt8c9fsjrc8g0937h5q2cqpyglq9kyy62834ngfyct0kzq5as673n2e05chwvsptgx0ngwtggj20shf84h4fx0qm4kw4a`(E2 实测有 3354.648444 ADA 余额,可在 https://cardanoscan.io/address/... 验证) |
| Stake addr 示例 | `stake1u9hmpq2wcd0ge4vh6vthxgq45r8e5895yf98ct5n6m65n8sxlwymg`(同地址的委托端) |
| 校验正则 | `^addr1[02-9ac-hj-np-z]{50,110}$`(payment mainnet);`^stake1[02-9ac-hj-np-z]{50,70}$`(stake) |

**地址类型识别(从 header byte 第 4 bit)**:
- `addr1q...` = base(payment+stake)
- `addr1z...` / `addr1w...` = script-locked
- 类型识别要 Bech32 解码后看第 1 byte 的高 4 bits — adapter 必须实现

---

## 7. Signature Lookup(签名/交易哈希)

| 项 | 值 |
|---|---|
| Hash 格式 | **Hex(无 0x 前缀)**,Blake2b-256 摘要 |
| 长度 | **64 字符 hex**(32 bytes) |
| 示例(主网真实 tx) | `a8aabe32bfb7b23a98c94b5037b60e4fedce468334ccaf94cdb642a9a47bc371`(E2 实测 block 13456426 的 0 号 tx,可在 https://cardanoscan.io/transaction/a8aabe32... 验证) |
| 查询 method | Koios:`POST /tx_info`(body: `{"_tx_hashes":["<hash>"]}`)/ Blockfrost:`GET /txs/{hash}` |
| Explorer URL 格式 | `https://cardanoscan.io/transaction/<hash>` |

---

## 8. Mixed Set(`mixed` 模式权重)

> 用于 `BLOCKCHAIN_NODE_BENCHMARK_MODE=mixed` 时的请求分布

```json
{
  "balance_query": 0.25,
  "tx_lookup": 0.20,
  "token_balance": 0.15,
  "block_query": 0.15,
  "asset_metadata": 0.10,
  "chain_params": 0.05,
  "tip_check": 0.05,
  "tx_utxos": 0.05
}
```

**权重和 = 1.00** ✅

**chain-specific 部分说明**:
- `asset_metadata`(0.10):Cardano native multi-asset 是核心特色,实际 dApp 频繁查 `asset_info`。
- `chain_params`(0.05):Plutus 交易构造前必须拿 `epoch_params`(min_fee 系数),是常规链上调用。
- `tx_utxos`(0.05):比 `tx_info` 轻量,只看 UTXO 流转,wallet 常用。

---

## 8.5 Phase 2.1 caller/reader 改造点(token-level Gate 3)

**强制要求**:每条链调研必须列出 Phase 2.1 实施时的 caller/reader 改造清单,避免 Phase 2.1 改 plugin 时 caller-blind(参考 `token-level-careful-edit` skill Case-B/D)。

**本链是新增链(无现有代码),按要求 #1-3 必填,#4-8 视情况标 N/A**:

| # | 位置(file:line) | 改动 | 原因 |
|---|---|---|---|
| 1 | `config/config_loader.sh:666` `supported_blockchains=(...)` | **新增 `cardano`** 到数组 | 否则 `validate_blockchain_node` 拒绝 `BLOCKCHAIN_NODE=cardano` |
| 2 | `config/config_loader.sh` 本链 `rpc_methods.mixed` | **新建** block:列出 §5 的 10 个 method + §8 权重 | 直接被 vegeta target 生成器消费 |
| 3 | `config/config_loader.sh` 本链 `param_formats` | **新建**:`POST /address_info` body=`{"_addresses":[...]}`、`POST /tx_info` body=`{"_tx_hashes":[...]}` 等 | `generate_rpc_json` 漏字段会退默认,导致 vegeta 400 |
| 3a | `config/config_loader.sh` 本链 `http_method` 映射 | **新建**:Cardano 大量 method 是 **POST**(数组入参),与 Solana/EVM 全 POST 但路径单一不同,Koios 是 RESTful 多路径 POST/GET 混合 | vegeta target 默认 POST `/`,Cardano 必须按 method 切换路径与 verb |
| 4 | `tools/fetch_active_accounts.py` adapter | **新增 `CardanoAdapter`** 类:实现 `fetch_recent_blocks` → Koios `/blocks?limit=N` → 提取 `payment_addr.bech32` 去重 | mixed 模式需要真实地址池,不能用静态种子地址 |
| 5 | `analysis-notes/baseline-current-state.md` | grep "supported chains" 列表,**追加 cardano(EUTXO,middleware:Koios)** | 文档真相对齐,防 v1.4.1 同款 doc-vs-code 偏离 |
| 6 | `analysis-notes/disk-and-network-pipeline-redesign.md` | grep 本链名,**追加**:Cardano 走 Koios HTTPS,无 mempool websocket | 网络管线说明同步 |
| 7 | `analysis-notes/research_notes/<cardano 笔记>.md` | **新建** Cardano 研究笔记(若有早期 N/A 记录,升级为 wave2 调研结果) | 研究笔记反映现实 |
| 8 | `tests/<本链相关测试>.sh` 或 `.py` | **新建** `tests/test_cardano_smoke.sh`:调 `/tip`、`POST /address_info` 各 1 次,断言 HTTP 200 + 关键字段存在 | L1/L2 单测保证 plugin JSON 正确 |
| 9 | `tools/mock_rpc_server.py` | **新增** `/api/v1/tip`、`/api/v1/blocks`、`POST /api/v1/address_info`、`POST /api/v1/tx_info` 等 case;响应贴 §3 真实样本 | mock 模式跑通本配置 |

**特别注意:HTTP 多路径 + POST body**:Cardano 是 28 链中**首个非单一 `POST /` JSON-RPC 的链**(Cosmos 也类似但 path 较固定)。Phase 2.1 实施前必须确认 `core/master_qps_executor.sh` 的 vegeta target 文件格式支持 `METHOD URL\nHeader\n@body.json` 三段式,否则需先升级 target 生成器(独立 ticket)。

**测试要求**:Phase 2.1 完成后必须跑 `core/master_qps_executor.sh --mixed --duration 30`(或最短 e2e_smoke)抓 vegeta 错误率,**所有请求都应是 200**,作为本链改造的 E2 证据。

---

## 8.6 ADR-0005 实施期 caller/reader 改造点(2026-05-28 校正)

**强制要求**(token-level-careful-edit Case-K):ADR-0005 把 cardano 从 `ogmios` family 校正到 `rest` family,以下 caller/reader 必须同 PR 改:

| # | 位置(file:line) | 改动 | 原因 / Gate 3 验证 |
|---|---|---|---|
| 1 | `config/chains/cardano.json` `_meta.adapter_family` | `ogmios` → `rest` | 顶层 family 归位;`tools/chain_adapters/base.py:126` 读这个值 |
| 2 | `config/chains/cardano.json` `_meta.rest_paths` | **新增**:`{"tip":"/api/v1/tip","block_info":"/api/v1/blocks","address_info":"/api/v1/address_info","tx_info":"/api/v1/tx_info","asset_info":"/api/v1/asset_info","epoch_info":"/api/v1/epoch_info"}` | RestAdapter 用逻辑名 → 真 URL 映射,代替 framework 硬编 |
| 3 | `config/chains/cardano.json` `rpc_methods.mixed` | 改逻辑名:`["tip","block_info","address_info","tx_info","asset_info","epoch_info"]`(权重见 §8) | 与 `rest_paths` keys 对齐;`config_loader.sh:371` case dispatch 取这个 |
| 4 | `config/chains/cardano.json` `_meta.param_formats` | **新增** body 模板:`{"address_info":{"verb":"POST","body":{"_addresses":["{ADDRESS}"]}},"tx_info":{"verb":"POST","body":{"_tx_hashes":["{TX_HASH}"]}},"asset_info":{"verb":"POST","body":{"_asset_list":[["{POLICY}","{ASSET_NAME}"]]}},"tip":{"verb":"GET"},"block_info":{"verb":"GET","query":"limit=1"},"epoch_info":{"verb":"GET"}}` | RestAdapter 读这个生成正确的 vegeta target;**修复 rest.py:87 POST body bug 后**真正生效 |
| 5 | `config/chains/cardano.json` `_meta.health_probe` | **新增**:`{"path":"/api/v1/tip","method":"GET","expect_status":200}` | fake-node startup self-check + smoke 测试入口 |
| 6 | `tools/chain_adapters/rest.py:87` POST 分支 | **修 bug**:从 `chain_template["_meta"]["param_formats"][method]["body"]` 读 body,替换字段占位符(`{ADDRESS}` 等)而非传空 `{}` | 与 cardano + algorand/aptos/tezos/ton 共用;rest family 整体修复 |
| 7 | `tools/chain_adapters/ogmios.py` + `tools/chain_adapters/__init__.py` ogmios 注册 | **删除** | 0 链使用,parallel-entry-trap 0-user 规范;ADR-0005 决策 |
| 8 | `tools/fake-node/handlers/rest.go` | **新建** 通用 REST handler:dispatch on path + verb,从 fixture 读 response | 覆盖 cardano + algorand/aptos/tezos/ton 5 链 |
| 9 | `tools/fake-node/fixtures/cardano/` | **新建** 6 fixtures:`tip.json`, `blocks.json`, `address_info.json`, `tx_info.json`, `asset_info.json`, `epoch_info.json`(record 自 Koios 真 mainnet) | rest handler echo 这些固定响应 |
| 10 | `tools/fake-node/handlers/stub.go`(ogmios stub) | **删除** ogmios 注册行 | 同 #7,framework + fake-node 双侧对齐 |
| 11 | `tools/fake-node/main.go` `_REGISTRY` 列表 | grep 验证 ogmios 已无引用 | parallel-entry-trap step 3 |
| 12 | `tests/test_cardano_smoke.sh` | **新建**:`BLOCKCHAIN_NODE=cardano` 启 fake-node,curl 6 method 各 1 次,断言 HTTP 200 + 关键字段存在 | L1 单测 + L3 e2e 入口 |
| 13 | `tools/ci_smoke.sh` | **追加** cardano + algorand/aptos/tezos/ton + 5 substrate + 5 tendermint + hedera = 16 链 smoke | L3 全 PASS 是 ADR-0005 验收门 |
| 14 | `docs/architecture/CURRENT-STATE.md` fake-node RPC-ready 矩阵 | 20/36 → 36/36 | 同步实施进度,不污染 NORTH-STAR(architecture-governance 四件套纪律) |
| 15 | `docs/architecture/OPEN-QUESTIONS.md` OQ-9(若存在"ogmios 保留 stub"项) | RESOLVED:删 | ADR-0005 决策落地 |

**Gate 3 完整验证**(改完每一个 caller 后必须重 grep 验):
- `grep -rn "ogmios" tools/ config/` → 应只剩 ADR-0005 决策溯源,无活跃代码
- `grep -rn "cardano" tools/fake-node/` → 通过 rest handler + fixture 路径访问,无硬编 cardano 分支
- `grep -rn "adapter_family.*ogmios" config/` → 0 hits

---

## 9. Mock Notes(mock_rpc_server 实现要点)

- **请求路径**:**多路径**,不是单一 `POST /jsonrpc`。例:`GET /api/v1/tip`、`POST /api/v1/address_info`、`POST /api/v1/tx_info`。
- **响应 schema**(§3 已贴真实样本,简列关键 case):

  ```json
  // GET /api/v1/tip
  [{"hash":"<32-byte hex>","epoch_no":632,"era":"Conway","abs_slot":<int>,
    "epoch_slot":<int>,"block_height":<int>,"block_no":<int>,"block_time":<unix>}]

  // POST /api/v1/address_info
  [{"address":"addr1...","balance":"<lovelace string>",
    "stake_address":"stake1...","script_address":false,
    "utxo_set":[{"value":"<lovelace>","tx_hash":"<hex>","tx_index":<int>,
                 "asset_list":[],"datum_hash":null,"inline_datum":null,
                 "reference_script":null,"block_time":<unix>,"block_height":<int>}]}]
  ```

- **特殊错误码**(Koios PostgREST 风格):
  - HTTP 400:body schema 错(例如 `_addresses` 不是 array)
  - HTTP 404:路径不存在(method typo)
  - HTTP 429:rate limit(Koios 公益层偶发)
  - HTTP 403:Blockfrost 无 key
  - **无 JSON-RPC `error.code`**(RESTful 用 HTTP code,不像 EVM 的 `-32602`)

- **mock 实现复杂度**:**Medium**
  - 理由 1:多路径(~10 个 endpoint)而非单一 dispatcher
  - 理由 2:POST body 需 parse JSON array 入参(`_addresses` / `_tx_hashes` / `_block_hashes`)
  - 理由 3:UTXO 字段嵌套深(asset_list / datum_hash / inline_datum),但因是 mock 可固定吐 §3 样本
  - 优势:可直接拷 §3 实测 JSON 作为 fixture,不需手构

---

## 10. Adapter Reuse Decision(adapter 复用决策)

> **⚠️ 已被 ADR-0005 校正(2026-05-28)**:本 §10 原决策"新建 CardanoAdapter / family=cardano-eutxo"已被 superseded。
>
> **新决策(ADR-0005)**:cardano 加入既有 `rest` family(与 algorand/aptos/tezos/ton 同 family),复用 `RestAdapter` + 通用 Go rest handler。理由:
> 1. §11.8 自身就推荐 Koios REST(transport 层就是 HTTP REST + JSON,与 `rest` family 既有 4 链完全同构)
> 2. EUTXO 是数据模型概念(reader / analysis 层),不是 transport 层概念 — 不需要独立 family
> 3. 新建 `cardano-eutxo` family 重复造轮子(Python 新 adapter ~200 LOC + Go 新 handler ~150 LOC = ~350 LOC),而归位 `rest` 0 LOC 新增 adapter,仅需修复 `tools/chain_adapters/rest.py:87` POST body bug(独立必须的 framework bug,与本链解耦)
>
> 详见 `docs/architecture/decisions/0005-cardano-family-correction-and-handler-rollout.md`。
>
> 以下 §10 原文保留作为决策溯源(不再有效)。

### 候选 adapter

| Adapter | 兼容度 | 缺失能力 |
|---|---|---|
| EthereumAdapter | **5%** | 账户模型(EUTXO vs Account)、地址格式(Bech32 vs Hex)、API 协议(REST 多路径 vs JSON-RPC 单点)、资产模型(native vs ERC20)全不同 |
| SolanaAdapter | **5%** | 同上,虽然都用 Ed25519 但地址格式 + RPC 协议完全不同 |
| BitcoinAdapter | **15%** | UTXO 形似(都有 utxo_set),但 EUTXO 多 datum/script 字段;Bitcoin 用 secp256k1,Cardano 用 Ed25519;Bitcoin JSON-RPC 走 `bitcoin-cli` 自带 daemon,Cardano 必须走 middleware |
| CosmosAdapter(Wave1 计划)| **20%** | REST 风格相似(都 RESTful、都 String 数值);但 Cardano UTXO 模型 vs Cosmos Account 模型,地址格式不同,资产模型不同 |

### 决策

- [x] **新建** `CardanoAdapter`(独立族,EUTXO + middleware 抽象层)
- [ ] 复用
- [ ] 混合

### 理由

**理由 1(数据模型独立性)**:EUTXO 是与 Bitcoin UTXO、EVM Account、Cosmos Bank 都不同的第四种模型,核心差异是 UTXO 承载 datum(合约状态)+ script(锁定逻辑)+ reference inputs(CIP-31 只读引用)。任何复用现有 adapter 都会在 `parse_balance` / `parse_tx` 阶段失败 — UTXO 集合的 balance 是 `sum(utxo.value for utxo in utxo_set)` 而非单一 `balance` 字段。

**理由 2(协议层独立性)**:Cardano 是 28 链中**唯一无原生 HTTP RPC** 的链,必须经 middleware 访问。CardanoAdapter 必须封装 "middleware 选择" 抽象(支持 Blockfrost / Koios 切换,详见 §11.8),而其他 adapter 都假设单一 RPC endpoint。这个抽象必须在 adapter 层,不能在配置层硬塞。

**理由 3(API 调用风格)**:Koios 的 REST 是**多路径 POST**(`POST /address_info` body 传数组),既不同于 EVM 的单路径 JSON-RPC,也不同于 Cosmos 的纯 GET REST。CardanoAdapter 需实现 path-per-method 路由 + body 模板。

### 配置 JSON 示例(本链,以 Koios 为默认 middleware)

```json
{
  "chain": "cardano",
  "family": "cardano-eutxo",
  "adapter": "CardanoAdapter",
  "chain_id": 1,
  "network_magic": 764824073,
  "middleware": "koios",
  "rpc_endpoint": "https://api.koios.rest/api/v1",
  "block_time_ms": 20000,
  "address_format": "bech32",
  "address_prefix_payment": "addr1",
  "address_prefix_stake": "stake1",
  "native_decimals": 6,
  "rpc_methods": {
    "block_height": {"verb": "GET", "path": "/tip"},
    "block_query": {"verb": "POST", "path": "/block_info", "body_key": "_block_hashes"},
    "tx_lookup":   {"verb": "POST", "path": "/tx_info", "body_key": "_tx_hashes"},
    "tx_utxos":    {"verb": "POST", "path": "/tx_utxos", "body_key": "_tx_hashes"},
    "balance":     {"verb": "POST", "path": "/address_info", "body_key": "_addresses"},
    "token_balance":{"verb": "POST", "path": "/address_assets", "body_key": "_addresses"},
    "asset_metadata":{"verb":"POST", "path":"/asset_info", "body_key":"_asset_list"},
    "chain_params":{"verb": "GET", "path": "/epoch_params"}
  },
  "mixed_weights": {
    "balance_query": 0.25,
    "tx_lookup": 0.20,
    "token_balance": 0.15,
    "block_query": 0.15,
    "asset_metadata": 0.10,
    "chain_params": 0.05,
    "tip_check": 0.05,
    "tx_utxos": 0.05
  }
}
```

---

## 11. DSL 字段需求(本链特殊!)

### 11.1 基础字段(沿用模板)

`chain` / `family` / `adapter` / `chain_id` / `rpc_endpoint` / `block_time_ms` / `address_format` / `rpc_methods` / `mixed_weights` —— 见 §10 配置 JSON。

### 11.2 EUTXO-specific 字段

| 字段 | 含义 | 默认 |
|---|---|---|
| `account_model` | `eutxo` | `eutxo` |
| `native_decimals` | lovelace→ADA 的位数 | 6 |
| `address_prefix_payment` | Bech32 payment hrp+v | `addr1` |
| `address_prefix_stake` | Bech32 stake hrp+v | `stake1` |
| `network_magic` | mainnet=764824073 | 764824073 |

### 11.3 HTTP 多路径 + body 字段(关键新需求)

DSL 必须能表达**每个 method 对应的 (HTTP verb, URL path, body schema)**,因为 Cardano 不是单一 JSON-RPC dispatcher:

```yaml
rpc_methods:
  balance:
    verb: POST
    path: /address_info
    body_template: '{"_addresses":["{{address}}"]}'
```

**当前框架 caller-blind 风险**:若 `master_qps_executor.sh` 的 vegeta target 生成器假设 `POST /` + JSON-RPC body,则需先升级。

### 11.4 余额计算字段(EUTXO 特有)

DSL 必须声明 **balance 是 sum(utxo_set.value) 还是直接读 balance 字段**:

- Koios `/address_info` 直接返回 `balance`(已 sum),DSL 设 `balance_extractor: $.balance`
- Blockfrost `/addresses/{addr}` 返回 `amount: [{"unit":"lovelace","quantity":"..."}]`,DSL 设 `balance_extractor: $.amount[?(@.unit=="lovelace")].quantity`

### 11.5 资产模型字段(native multi-asset)

```yaml
asset_model: native_multi_asset
asset_id_format: "{policy_id}.{asset_name_hex}"   # 28+≤32 byte hex
asset_decimals_source: "cip67_metadata"           # 资产 decimals 来自 CIP-67 元数据
```

### 11.6 Finality 字段

```yaml
finality_type: probabilistic
finality_confirmations: 36   # ~12 min,推荐安全阈值
finality_genesis_alternative: ouroboros_genesis  # 可选更强保证
```

### 11.7 Cardano middleware 对比表(强制必填)

| 维度 | Blockfrost | Koios | Ogmios | cardano-graphql |
|---|---|---|---|---|
| 协议 | REST | REST(PostgREST) | WebSocket JSON-RPC | GraphQL |
| 鉴权 | **必须 `project_id` header**(注册免费拿) — E2 实测无 key=HTTP 403 | **无 key** — E2 实测 HTTP 200 | 无 | 无 |
| balance 查询 | `GET /addresses/{addr}` ⚠️ 未 E2(无 key 跳过) | `POST /address_info` body=`{"_addresses":[...]}` — E2 实测 ✅ | `Query/utxo`(WS JSON-RPC 自部署)⚠️ 未 E2 | `query addresses { utxos { value } }` ⚠️ 未 E2 |
| tx 查询 | `GET /txs/{hash}` ⚠️ 未 E2 | `POST /tx_info` body=`{"_tx_hashes":[...]}` — E2 实测 ✅ | `Query/utxo` 等 ⚠️ 未 E2 | `query transactions(hash:...)` ⚠️ 未 E2 |
| 公共端点 | `https://cardano-mainnet.blockfrost.io/api/v0` ✅ 可达(需 key) | `https://api.koios.rest/api/v1` ✅ 无 key 可用 | ❌ Dandelion `wss://ogmios-api.mainnet.dandelion.link/` E2 HTTP 000(下线),**必须自部署** | ❌ Dandelion `https://graphql-api.mainnet.dandelion.link/` E2 HTTP 000(下线),**必须自部署** |
| Rate limit | **50,000 请求/天**(free 层,官方文档)⚠️ 未 E2(无 key 无法触发) | **未明示数字**,IP-based,实测 3 次 `/tip` 全 200(响应头无 `x-ratelimit-*`)⚠️ Koios 官方建议生产用自部署 instance | 自部署无限 | 自部署无限 |
| 自部署成本 | 不支持(SaaS only) | **支持**(`koios-artifacts` 一键脚本,需 ~500GB SSD + cardano-node + db-sync) | 需 cardano-node + Ogmios binary(~500GB SSD) | 需 cardano-node + db-sync + hasura + graphql-engine(~500GB SSD,栈最复杂) |
| 与本框架 DSL 复用 | REST,与 Cosmos REST 复用 vegeta GET/POST 基础设施 ✅ | REST(POST body),与 Cosmos REST 部分复用 ✅,但需要 path-per-method | WebSocket,**与现有所有链都不复用**(框架无 WS target 生成器) | GraphQL,**框架无 GraphQL DSL 支持** |
| 数据完整度 | 高(包含 metadata、Plutus 脚本) | 高(社区 db-sync 全节点) | 完整(直接 node socket 转发) | 高(包含 Plutus、CIP 全部) |

### 11.8 DSL middleware 选择建议(强制必填)

本框架应该用哪个 middleware?

- [ ] Blockfrost(REST,公共,需 API key)
- [x] **Koios**(REST,免费无 key)— **推荐**
- [ ] Ogmios(WebSocket,自部署)
- [ ] cardano-graphql(GraphQL,需 DSL 支持 GraphQL)

**理由(3 段)**:

**段 1 — DSL 复杂度最低**:Koios 是 REST + JSON,与 Cosmos REST(Wave1)共享同一套 vegeta HTTP target 基础设施(GET URL / POST body / 应答 JSON)。新增 Koios 仅需扩 `rpc_methods.{verb, path, body_template}` 字段(本身是 §10 已写好的 plugin schema),不需要在框架引入新的 transport(WebSocket / GraphQL)。Ogmios 需要 WebSocket target 生成器(Vegaa 不原生支持 WS,需要新工具),cardano-graphql 需要 DSL 支持 GraphQL query 模板 + variables — 两者都是**新基础设施投资**,远超 Phase 2.x 本链 plugin 范围。

**段 2 — 公共端点可用性 + 零运营成本**:本次调研(2026-05-23)实测:Koios 公共集群 `api.koios.rest` 全 200,3 次 `/tip` 平均延迟 0.78s(跨地理);Blockfrost 需注册拿 project_id 才能用(50k/天 免费层),benchmark 上限会被锁(`50k/86400s ≈ 0.58 QPS`,完全无法做高 QPS 压测);Ogmios 和 cardano-graphql 的历史公共端点 Dandelion 已下线,自部署需要 ~500GB SSD + 跑 cardano-node 数天同步,在 CI/mock 场景**不现实**。Koios 是唯一**免运营成本** + **无 key 门槛**的选项。

**段 3 — Benchmark 准确性反例与反转条件**:Koios 公共集群是社区公益资源,**不适合做生产环境真实节点压测**(实测无 `x-ratelimit-*` header,Koios 官方文档建议高负载用自部署 instance)。本框架的 benchmark 角色应明确为 "RPC client 侧的协议正确性 + mock 兼容性测试",而非 "测 Koios 公共集群的服务器吞吐"。**反转条件**:若 Phase 2.x 需要**真实节点压测**(测 cardano-node 本身的 QPS 上限),则必须自部署 Koios stack 或 Ogmios,届时本决策升级为 "公共=Koios for smoke,自部署=Ogmios for load"。当前阶段 **Koios 公共 + mock_rpc_server fallback** 是最优解。

---

## Open Questions(待解决问题)

- [ ] **DSL 新字段 `(verb, path, body_template)` 接入哪个 schema 版本?** 当前 `config/config_loader.sh` 是 bash 数组风格,Cardano 是首个需要 path-per-method 的链,建议在 Phase 2.x 引入正式 `chains/<name>.json` plugin schema(Q4 = C 95% 加链 0 Python 目标的关键基础设施)。
- [ ] **EUTXO 抽象的余额定义**:CardanoAdapter 的 `getBalance(addr)` 是否要包含 stake reward?stake address 单独余额查询需 `POST /account_info`(本调研未实测,只验了 `address_info` 的 payment 余额)。
- [ ] **Plutus 智能合约状态查询**:本调研未覆盖 `script_info` / datum 查询(因 §5 mixed 不含 contract call)。Phase 2.x 若加 Plutus 调用压测,需补一节。
- [ ] **Koios 自部署的最小配置**:`koios-artifacts` 是否能跑无 db-sync 的 light mode?(影响 CI 成本)
- [ ] **Blockfrost project_id 获取与 secret 管理**:若 Phase 2.x 决定支持 Blockfrost(作为 Koios 故障转移),需要约定 env var 名称(例 `BLOCKFROST_PROJECT_ID`)+ benchmark 报告脱敏。

---

## Changelog

| Date | Author | Change |
|---|---|---|
| 2026-05-23 | Hermes Agent | 初次调研(Phase 1.2 Wave2):Koios 全部 method E2 实证;Blockfrost 无 key 路径 E2 确认 HTTP 403;Ogmios/cardano-graphql 公共端点 E2 确认 ❌(Dandelion 下线);推荐 Koios 作为框架 middleware。 |
