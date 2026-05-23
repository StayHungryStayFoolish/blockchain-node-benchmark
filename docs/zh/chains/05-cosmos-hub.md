# 05 — Cosmos Hub 调研稿

> **版本**:v1.0(初稿,Phase 1.2 Wave1)
> **调研日期**:2026-05-23
> **作者**:Hermes Agent
> **状态**:🟢 待 user review(P1-USER-REVIEW 卡点)
> **真实证据严格遵守 H8**:本稿所有关键字段附 E1-E5 标记(E1=单元测试 / E2=curl 实证 / E3=官方文档 / E4=GitHub 源码 / E5=框架 grep)。

---

## 元信息

| 项 | 值 |
|---|---|
| 链名(中) | Cosmos Hub |
| 链名(英) | Cosmos Hub |
| 编号 | 05 |
| Mainnet ChainID | `cosmoshub-4`(字符串,非数字)— E2 实测 `https://cosmos-rpc.publicnode.com/status` 返回 `network: "cosmoshub-4"` |
| 节点应用 | **gaiad v27.3.0**(GaiaApp),Tendermint/CometBFT 共识层 `v0.38.19` — E2 |
| 调研日期 | 2026-05-23 |
| 调研者 | Hermes Agent |
| 状态 | 🟢 已完成(框架尚未支持本链,本调研为 Phase 2.x plugin 引入做准备) |
| 框架是否已支持 | ❌ — E5: `config/config_loader.sh:666` `supported_blockchains` 仅 `(solana ethereum bsc base scroll polygon starknet sui)`,不含 cosmos |

---

## 1. Sources(权威来源)

| 类型 | URL | 访问日期 | 备注 |
|---|---|---|---|
| 官方文档(Cosmos SDK) | https://docs.cosmos.network/ | 2026-05-23 | Cosmos SDK 模块化框架主页 |
| 官方文档(Hub) | https://hub.cosmos.network/ | 2026-05-23 | Cosmos Hub 链具体规范 |
| Tendermint RPC spec | https://docs.cometbft.com/v0.38/rpc/ | 2026-05-23 | CometBFT(原 Tendermint)JSON-RPC 完整 method 列表 |
| Cosmos REST/LCD OpenAPI | https://docs.cosmos.network/api | 2026-05-23 | gRPC-gateway 自动生成的 REST 接口 |
| GitHub(gaia) | https://github.com/cosmos/gaia | 2026-05-23 | Cosmos Hub 节点 daemon 源码(gaiad) |
| GitHub(cosmos-sdk) | https://github.com/cosmos/cosmos-sdk | 2026-05-23 | 模块代码(bank/staking/...)+ proto 定义 |
| GitHub(cometbft) | https://github.com/cometbft/cometbft | 2026-05-23 | 共识层 + RPC 实现 |
| Explorer(Mintscan) | https://www.mintscan.io/cosmos | 2026-05-23 | 地址/tx/validator 查询 |
| Explorer(Ping.pub) | https://ping.pub/cosmos | 2026-05-23 | 备用 explorer |

---

## 2. Protocol Family(协议族)

| 项 | 值 |
|---|---|
| Family | **Cosmos-SDK / Tendermint**(ABCI 抽象层,几十条链复用:Osmosis / Celestia / Injective / Sei / Kava / Stride / Neutron / dYdX v4 / Noble / ...) |
| Consensus | **Tendermint BFT / CometBFT**(即时最终性,1 区块即 final) |
| VM | **Cosmos SDK 模块**(原生 Go 模块化,非 EVM);可选 **CosmWasm**(WASM 智能合约,Cosmos Hub 主网未启用,Juno/Neutron/Osmosis 启用) |
| Block Time | ~6 秒(E2 实测:height 31248030 → 31248052 跨度 ~131 秒,约 5.96s/block) |
| Finality | **即时 final**(BFT,1 区块即不可逆,无需等 N 确认) |
| Reuse Existing Adapter? | **No,需新建 CosmosAdapter**(账户模型 + 地址格式 + API 协议三重不同,无可复用) |
| 本族链数(框架计划内) | 至少 6 条:cosmos / osmosis / celestia / injective / sei / kava(可能更多,待 Phase 2.x 决定) |

---

## 3. Public RPC / REST(公共节点)

### 端点候选

| Endpoint | API 类型 | Auth | 实测状态 | 备注 |
|---|---|---|---|---|
| `https://cosmos-rpc.publicnode.com` | Tendermint RPC :26657 | 无 | ✅ HTTP 200(E2) | Allnodes/publicnode 公益节点 |
| `https://cosmos-rest.publicnode.com` | REST/LCD :1317 | 无 | ✅ HTTP 200(E2) | 同上 |
| `https://cosmos-grpc.publicnode.com` | gRPC :9090 | 无 | ⚠️ 端点存在(域名返浏览器页面)但**未用 grpcurl/protoc 实测**(本环境无 grpcurl),HTTP/1.1 POST 返 415 = 正常 gRPC 行为 | 公益 gRPC 网关 |
| `https://rpc.cosmos.network` | Tendermint RPC | 无 | ❌ HTTP 525(SSL handshake failed,2026-05-23 实测,可能临时故障) | 官方公共节点,**当前不可用** |
| `https://rest.cosmos.network` | REST/LCD | 无 | ❌ HTTP 525(同上) | 官方公共节点 |

**Trade-off**:`rpc.cosmos.network` 官方节点实测不可达(SSL 525),`cosmos-rpc.publicnode.com` 全 200。建议生产 mock-fallback 优先用 publicnode,**反转条件**:若 Phase 2.x 实测 publicnode 限流过严,则回退官方节点(应届时官方节点已恢复)。

### curl 实测(2026-05-23 ~18:05 UTC 真实执行,**数值字段有时效性**)

#### 3.1 Tendermint RPC :26657(JSON-RPC,GET style 也支持)

```bash
# /status — 节点状态 + 最新高度
$ curl -s https://cosmos-rpc.publicnode.com/status
{"jsonrpc":"2.0","id":-1,"result":{
  "node_info":{"network":"cosmoshub-4","version":"0.38.19",...},
  "sync_info":{
    "latest_block_hash":"057D121688D530344FDF519E2D1A6C870FEBB4E82E4BF519555799A918E62C5F",
    "latest_block_height":"31248039",
    "latest_block_time":"2026-05-23T18:03:49.254536256Z",
    "earliest_block_height":"25280088",
    "catching_up":false}}}
# 解读:chain_id=cosmoshub-4,height=31248039(注意:String 类型,非 number)

# /abci_info — 应用层版本
$ curl -s https://cosmos-rpc.publicnode.com/abci_info
{"jsonrpc":"2.0","id":-1,"result":{"response":{
  "data":"GaiaApp","version":"v27.3.0",
  "last_block_height":"31248042",
  "last_block_app_hash":"y9w+EkG/n0hMoJt06WhRBNbuoymFo1q0LXQICxIelUQ="}}}

# /block?height=N — 区块详情(含 tx 列表,base64 编码)
$ curl -s "https://cosmos-rpc.publicnode.com/block?height=31248030"
{"jsonrpc":"2.0","id":-1,"result":{
  "block_id":{"hash":"F8CC501F944ED412A09B9C3DC3522A12D883F0960A11B34669F1588792E6B1E2",...},
  "block":{"header":{"chain_id":"cosmoshub-4","height":"31248030",
    "time":"2026-05-23T18:03:00.621898913Z","proposer_address":"56B2F053AD136642D3FC9098FB2DD01454F396D5"},
  "data":{"txs":["CvoBCosBChwvY29zbW9zLmJhbmsudjFiZXRhMS5Nc2dTZW5kEms..."]}}}}
# 解读:txs 是 base64 编码的 protobuf,客户端要 decode 后才能读 MsgSend 内容

# /tx?hash=0x... — tx 详情(注意 hex 大写,必须加 0x 前缀)
$ curl -s "https://cosmos-rpc.publicnode.com/tx?hash=0x1EC1293E8C5E266C76846F35EAC7E25DDCAAF049AEF5ABA67F492C61C57CEAA6"
{"jsonrpc":"2.0","id":-1,"result":{
  "hash":"1EC1293E8C5E266C76846F35EAC7E25DDCAAF049AEF5ABA67F492C61C57CEAA6",
  "height":"31248030","tx_result":{"code":0,"gas_wanted":"125000","gas_used":"106050",
  "events":[{"type":"tx","attributes":[
    {"key":"acc_seq","value":"cosmos1wypsnn7n5hsd2kvk424qv9yuretz9m6kvumev2/91150"}]}]}}}

# /abci_query — ABCI 二级路由(Cosmos 独有,DSL 必须能表达)
$ curl -s 'https://cosmos-rpc.publicnode.com/abci_query?path="/app/version"'
{"jsonrpc":"2.0","id":-1,"result":{"response":{"code":0,
  "value":"djI3LjMuMA==","height":"31248049","codespace":"sdk"}}}
# 解读:value base64 → "v27.3.0"
```

#### 3.2 Cosmos REST/LCD :1317(REST,路径式参数)

```bash
# 余额查询
$ curl -s https://cosmos-rest.publicnode.com/cosmos/bank/v1beta1/balances/cosmos1wypsnn7n5hsd2kvk424qv9yuretz9m6kvumev2
{"balances":[
  {"denom":"ibc/3622BC03E5098BF3EC0A2DB13E5031668290B98020C5FADB7901207F44C4D717","amount":"134000000000"},
  {"denom":"ibc/3B362DDD99879D5BA199A265C5BBD46AE139CA9F46B5CFCDE9C59D68792825C4","amount":"19499989999799000000"},
  ...
],"pagination":{"next_key":null,"total":"0"}}
# 解读:多 denom 资产数组,IBC token 用 ibc/<hash> denom 标识

# tx 查询
$ curl -s https://cosmos-rest.publicnode.com/cosmos/tx/v1beta1/txs/1EC1293E8C5E266C76846F35EAC7E25DDCAAF049AEF5ABA67F492C61C57CEAA6
{"tx":{"body":{"messages":[{
  "@type":"/cosmos.bank.v1beta1.MsgSend",
  "from_address":"cosmos1wypsnn7n5hsd2kvk424qv9yuretz9m6kvumev2",
  "to_address":"cosmos180phhck72hqkkfygyn6n77p6hvg6749f54uytv",
  "amount":[{"denom":"uatom","amount":"60"}]}],"memo":"1/5 🎁 💎$ATOM Airdrop..."}}}

# 最新块
$ curl -s https://cosmos-rest.publicnode.com/cosmos/base/tendermint/v1beta1/blocks/latest
{"block_id":{"hash":"fjs2y78cAi4Y2/Ccz9mVBmBKjR3waIMv2jFb22qAFCw=",...},
 "block":{"header":{"chain_id":"cosmoshub-4","height":"31248052","time":"2026-05-23T18:05:04.302220555Z"}}}
# 注意:REST 返回 hash 是 base64 编码,RPC 返回 hash 是 hex 大写 — 同一 hash 两种编码!

# 节点信息(含 git_commit、build_tags)
$ curl -s https://cosmos-rest.publicnode.com/cosmos/base/tendermint/v1beta1/node_info
{"default_node_info":{"network":"cosmoshub-4","version":"0.38.19",...},
 "application_version":{"name":"gaia","app_name":"gaiad","version":"v27.3.0",
   "git_commit":"ed341c8ae3802c3f522f9b3aeb95b872d59bcb89","build_tags":"netgo,ledger"}}

# 同步状态
$ curl -s https://cosmos-rest.publicnode.com/cosmos/base/tendermint/v1beta1/syncing
{"syncing": false}

# validators 列表(用于找真实 validator 地址)
$ curl -s "https://cosmos-rest.publicnode.com/cosmos/staking/v1beta1/validators?pagination.limit=2&status=BOND_STATUS_BONDED"
{"validators":[{"operator_address":"cosmosvaloper1q6d3d089hg59x6gcx92uumx70s5y5wadklue8s",
  "consensus_pubkey":{"@type":"/cosmos.crypto.ed25519.PubKey","key":"uEUR1gpesU4bnSWL2TOXOf3org2mCYhQHMYkiCJyMD4="},
  "status":"BOND_STATUS_BONDED","tokens":"1153338880041",
  "description":{"moniker":"Ubik Capital",...}}],
  "pagination":{"next_key":"FArILLpzgq04+y5e2aCGDLtnvPQs","total":"0"}}
```

#### 3.3 gRPC :9090(本次未实测,如实标记)

⚠️ **未 E2 实证**:本调研环境无 `grpcurl` 命令(`which grpcurl` 返 not found)。`https://cosmos-grpc.publicnode.com` 端点存在(curl 返 publicnode 浏览器页面 = 反代正常),HTTP/1.1 plain POST 返 415 Unsupported Media Type(= 正常 gRPC 行为,符合 gRPC over HTTP/2 + protobuf 协议要求)。

E3 证据(官方 spec):https://docs.cosmos.network/main/learn/advanced/grpc_rest 明确 gRPC 端点默认在 `:9090`,提供 `cosmos.bank.v1beta1.Query/AllBalances`、`cosmos.tx.v1beta1.Service/GetTx`、`cosmos.base.tendermint.v1beta1.Service/GetLatestBlock` 等。

**实证开口(若 Phase 2.x 决定用 gRPC,必须补)**:
```bash
# Phase 2.x 实施时跑(本次未跑):
grpcurl -d '{"address":"cosmos1..."}' cosmos-grpc.publicnode.com:443 \
  cosmos.bank.v1beta1.Query/AllBalances
```

---

## 4. Account Model(账户模型)

| 项 | 值 |
|---|---|
| 模型 | **Account 模型**(非 UTXO);账户由 bech32 地址标识 |
| Native token | **ATOM**(denom 字符串 = `uatom`,1 ATOM = 1,000,000 uatom)— E2 实测 MsgSend.amount = `[{denom:"uatom",amount:"60"}]` |
| Native token decimals | **6**(uatom 是 micro-ATOM)— E3: Cosmos SDK 标准 |
| Address derivation | **secp256k1**(默认)/ **ed25519**(consensus pubkey)/ **sr25519**(部分链可选)— E2:观察 validator consensus_pubkey 用 ed25519 |
| 多资产 | **是**(单账户可持有多 denom:uatom + ibc/<hash> 各种 IBC token)— E2 实测见 §3.2 余额查询 |
| Special account types | **Module Accounts**(模块持有,如 `cosmos1fl48vsnmsdzcv85q5d2q4z5ajdha8yu34mf0eh` = bank module)、**Validator Operator**(`cosmosvaloper1...` 前缀)、**Consensus Address**(`cosmosvalcons1...`)— 同一 hash 不同 bech32 prefix |

---

## 5. Core RPC Methods(本框架监控所需)

> **方法名标注 [TR]=Tendermint RPC, [RE]=REST/LCD, [GR]=gRPC**。同一逻辑功能 3 套 API 名字完全不同,DSL 必须明示用哪套。

| 逻辑功能 | [TR] Tendermint RPC :26657 | [RE] REST/LCD :1317 | [GR] gRPC :9090 | mixed 权重建议 |
|---|---|---|---|---|
| 块高(探活) | `/status`(读 `result.sync_info.latest_block_height`)| `GET /cosmos/base/tendermint/v1beta1/blocks/latest` | `cosmos.base.tendermint.v1beta1.Service/GetLatestBlock` | 0.10 |
| 块详情 | `/block?height=N` | `GET /cosmos/base/tendermint/v1beta1/blocks/{height}` | `cosmos.base.tendermint.v1beta1.Service/GetBlockByHeight` | 0.10 |
| ABCI info | `/abci_info` | (无对应,gRPC-gateway 不暴露) | `cosmos.base.tendermint.v1beta1.Service/GetNodeInfo`(类似) | 0.05 |
| 余额查询 | `/abci_query?path="/cosmos.bank.v1beta1.Query/AllBalances"&data=<protobuf-hex>`(**需 protobuf 编码 query**,客户端复杂)| `GET /cosmos/bank/v1beta1/balances/{addr}` | `cosmos.bank.v1beta1.Query/AllBalances` | 0.30 |
| 单 denom 余额 | 同上,query 是 `Balance`(单 denom)| `GET /cosmos/bank/v1beta1/balances/{addr}/by_denom?denom=uatom` | `cosmos.bank.v1beta1.Query/Balance` | 0.05 |
| tx 查询 | `/tx?hash=0xUPPER_HEX&prove=true` | `GET /cosmos/tx/v1beta1/txs/{hash}` | `cosmos.tx.v1beta1.Service/GetTx` | 0.15 |
| tx 搜索 | `/tx_search?query="tx.height=N"&per_page=K` | `GET /cosmos/tx/v1beta1/txs?events=...&pagination.limit=K` | `cosmos.tx.v1beta1.Service/GetTxsEvent` | 0.05 |
| validators | `/validators?height=N&per_page=K` | `GET /cosmos/staking/v1beta1/validators` | `cosmos.staking.v1beta1.Query/Validators` | 0.10 |
| delegations | (需 abci_query 编码)| `GET /cosmos/staking/v1beta1/delegations/{delegator_addr}` | `cosmos.staking.v1beta1.Query/DelegatorDelegations` | 0.05 |
| 节点信息 | `/status`(同上,见 node_info)| `GET /cosmos/base/tendermint/v1beta1/node_info` | 同上 GetNodeInfo | 0.05 |

**总权重**:0.10+0.10+0.05+0.30+0.05+0.15+0.05+0.10+0.05+0.05 = **1.00** ✅

**关键观察**:
1. **余额查询**:Tendermint RPC 路径需 protobuf 编码 `data` 参数(复杂度高);REST 直接路径参数(简单);gRPC 原生 protobuf。**REST 是 benchmark 最易实现的**。
2. **tx hash 大小写差异**:Tendermint RPC `/tx?hash=0x...` 必须**大写 hex + 0x 前缀**(E2 验证),REST `/cosmos/tx/v1beta1/txs/{hash}` 接受大写 hex 无前缀(E2 验证)。
3. **block hash 编码差异**:Tendermint RPC `/block` 返回 hash = **大写 hex 字符串**,REST `/cosmos/base/tendermint/v1beta1/blocks/latest` 返回 hash = **base64 字符串**(同一 hash 两种编码!)。

---

## 6. Address Format(地址格式)

| 项 | 值 |
|---|---|
| 编码 | **Bech32**(BIP173)— E3 |
| HRP(human-readable prefix) | **`cosmos`**(账户)/ **`cosmosvaloper`**(validator operator)/ **`cosmosvalcons`**(consensus)/ **`cosmospub`**(pubkey)/ ... — **每链不同**(osmo / celestia / inj / sei / kava ...) |
| 总长度 | 账户地址 = `cosmos1` + 38 字符 = 45 字符(20 字节 hash + 6 字节 checksum + 1 字节 separator)— E2 验证:`cosmos1wypsnn7n5hsd2kvk424qv9yuretz9m6kvumev2` 长度 = 45 |
| Checksum | **有**(Bech32 算法内置 6 字符 BCH checksum) |
| 示例(真实主网账户) | `cosmos1wypsnn7n5hsd2kvk424qv9yuretz9m6kvumev2`(E2:有真实余额,见 §3.2)|
| 示例(真实主网 validator) | `cosmosvaloper1q6d3d089hg59x6gcx92uumx70s5y5wadklue8s`(Ubik Capital,E2 实测 bonded)|
| 示例(目标 address — 框架配置候选) | `cosmos1wypsnn7n5hsd2kvk424qv9yuretz9m6kvumev2`(活跃 sender,acc_seq 已到 91150,= 极活跃账户) |
| 校验正则 | `^cosmos1[02-9ac-hj-np-z]{38}$`(账户)/ `^cosmosvaloper1[02-9ac-hj-np-z]{38}$`(validator)|
| 跨链地址迁移性 | **同一 hash 可派生其他 prefix**(同一私钥可控 cosmos1.../osmo1.../celestia1...,本质 secp256k1 公钥 hash)|

---

## 7. Signature Lookup(签名/交易哈希)

| 项 | 值 |
|---|---|
| Hash 格式 | **Hex 大写**(SHA-256 → 32 字节 → 64 字符 hex,**无前缀**;Tendermint RPC `/tx` query 必须**加 `0x` 前缀**;REST 不需要)|
| 长度 | **64 字符**(32 字节 SHA-256) |
| 示例(主网真实 tx) | `1EC1293E8C5E266C76846F35EAC7E25DDCAAF049AEF5ABA67F492C61C57CEAA6`(E2:height 31248030,真实 MsgSend)|
| 查询 method(Tendermint RPC) | `/tx?hash=0x1EC1293E8C5E266C76846F35EAC7E25DDCAAF049AEF5ABA67F492C61C57CEAA6&prove=false` |
| 查询 method(REST) | `GET /cosmos/tx/v1beta1/txs/1EC1293E8C5E266C76846F35EAC7E25DDCAAF049AEF5ABA67F492C61C57CEAA6` |
| Explorer URL | `https://www.mintscan.io/cosmos/tx/<hash>` |

⚠️ **大小写敏感性**:Tendermint RPC 实测**大写**正常返回,改成小写则 hash 仍能匹配(SHA-256 hex 大小写无意义),但 REST 接口 path 部分**惯例用大写**(explorer / docs 均用大写)。DSL 应统一大写。

---

## 8. Mixed Set(`mixed` 模式权重)

> 用于 `BLOCKCHAIN_NODE_BENCHMARK_MODE=mixed` 时的请求分布。**与 Solana §8、Ethereum §5 同 schema**(由 `config_loader.sh::generate_rpc_json` 等权循环,Phase 2.x 引入加权后再用 weight 字段)。

### 设计建议(假设 DSL 选 REST/LCD,见 §11.8)

```json
{
  "cosmos_bank_balance": 0.30,
  "cosmos_tx_get": 0.15,
  "cosmos_block_by_height": 0.10,
  "cosmos_block_latest": 0.10,
  "cosmos_validators_list": 0.10,
  "cosmos_node_info": 0.05,
  "cosmos_syncing": 0.05,
  "cosmos_tx_search": 0.05,
  "cosmos_delegations": 0.05,
  "cosmos_bank_balance_by_denom": 0.05
}
```

具体 method 映射(REST):
- `cosmos_bank_balance` → `GET /cosmos/bank/v1beta1/balances/{addr}`
- `cosmos_tx_get` → `GET /cosmos/tx/v1beta1/txs/{hash}`
- `cosmos_block_by_height` → `GET /cosmos/base/tendermint/v1beta1/blocks/{N}`
- `cosmos_block_latest` → `GET /cosmos/base/tendermint/v1beta1/blocks/latest`
- `cosmos_validators_list` → `GET /cosmos/staking/v1beta1/validators?pagination.limit=10`
- ...

**权重和 = 1.00 ✅**

---

## 8.5 Phase 2.1 caller/reader 改造点(token-level Gate 3)

**本链是新增链**(无现有代码),#4-8 视情况标 N/A。**新增 cosmos 时必须同步动作**:

| # | 位置(file:line) | 改动 | 原因 |
|---|---|---|---|
| 1 | `config/config_loader.sh:666` `supported_blockchains` 数组 | 加 `"cosmos"` | 否则 validate_blockchain_node 拒绝 |
| 2 | `config/config_loader.sh:~380` 新增 `case cosmos)` 设 `MAINNET_RPC_URL=https://cosmos-rest.publicnode.com`(或 RPC,见 §11.8 决策) | 设 endpoint | 必填 |
| 3 | `config/config_loader.sh:~440-468` 风格 `UNIFIED_BLOCKCHAIN_CONFIG.blockchains.cosmos` 段 | 新增 methods / system_addresses / rpc_methods.single / rpc_methods.mixed / param_formats | 直接被 vegeta target 生成器消费 |
| 4 | `tools/mock_rpc_server.py:~137` method 分支 | 新增 cosmos method 分支(REST 风格 = **路径参数 + GET**,与现有 8 链全 POST JSON-RPC 完全不同!)| mock_rpc_server 是 fallback target,**协议不同需新增 HTTP routing** |
| 5 | `tools/fetch_active_accounts.py` 新增 `CosmosAdapter(BlockchainAdapter)` 类 | 实现 `_single_request`(REST GET)/ `fetch_transaction`(REST GET)/ `extract_accounts_from_transaction`(从 MsgSend.from_address/to_address 取)| 本族唯一,无可复用 adapter |
| 6 | `analysis-notes/baseline-current-state.md` grep `solana\|ethereum`,本链加入链路列表 | 同步更新 | 文档真相对齐 |
| 7 | `tests/` 新增 `test_cosmos_adapter.py`(若有测试基础设施)| 至少跑 1 笔真主网 fixture tx 解析 | L1 单测 |
| 8 | `core/master_qps_executor.sh --mixed --duration 30` 跑通 | 所有请求 200,无 -32601 / -32603 错 | E2 证据,作为本链改造 success criterion |

**关键陷阱(Cosmos 独有)**:
- REST 是 **GET + 路径参数**,与现有 8 链 **POST + JSON-RPC body** 协议层不同 — `mock_rpc_server.py` 当前用 `BaseHTTPRequestHandler.do_POST`,**必须加 `do_GET`**。
- vegeta target 生成器(`target_generator.sh:184/300-306`)需支持 GET method + URL-only target(不带 body) — 可能需扩 schema。

---

## 9. Mock Notes(mock_rpc_server 实现要点)

### 若 DSL 选 **REST/LCD :1317**:

- **请求路径**:多个,例如 `GET /cosmos/bank/v1beta1/balances/{addr}`、`GET /cosmos/tx/v1beta1/txs/{hash}`、`GET /cosmos/base/tendermint/v1beta1/blocks/latest`
- **响应 schema 样本**(真实主网,见 §3.2):
  ```json
  {"balances":[{"denom":"uatom","amount":"1234567"}],"pagination":{"next_key":null,"total":"0"}}
  {"tx":{"body":{"messages":[{"@type":"/cosmos.bank.v1beta1.MsgSend",...}]}}}
  ```
- **特殊错误码**:
  - HTTP `501` + `{"jsonrpc":"","error":{"code":-32701,"message":"not implemented"}}`(未实现路径,E2 实测)
  - HTTP `400` + `{"code":3,"message":"invalid address: decoding bech32 failed: invalid checksum ..."}`(bech32 校验失败,E2 实测)
  - HTTP `404` + `{"code":5,"message":"not found"}`(tx hash 不存在,常见)
- **关键 mock 复杂度**:**High**
  - 协议层与现有 8 链不同(GET 路径 vs POST body) — 需扩 `mock_rpc_server.py` 加 `do_GET` + 路径路由 dispatcher
  - 响应 schema 嵌套深(`messages[].{@type, from_address, to_address, amount[]}`) — 建议 fixture 模式
  - 多 denom 资产(`uatom` + 多个 `ibc/<hash>`) — fixture 必须覆盖

### 若 DSL 选 **Tendermint RPC :26657**:

- **请求路径**:`GET /<method>?<query>` 或 `POST /` JSON-RPC body
- **响应 schema 样本**:见 §3.1
- **特殊错误码**:
  - `-32603 Internal error`(如 height 超过当前高度,E2 实测)
  - `-32601 Method not found`
  - `-32700 Parse error`
- **关键 mock 复杂度**:**Medium**
  - 与现有 8 链 JSON-RPC 协议相同(POST body),易扩 mock_rpc_server
  - 但 `abci_query` 的 `data` 字段需 protobuf 编码,mock 无需真编码(返固定 fixture 即可)

---

## 10. Adapter Reuse Decision(adapter 复用决策)

### 候选 adapter

| Adapter | 兼容度 | 缺失能力 |
|---|---|---|
| SolanaAdapter | **0%** | 协议/地址/账户模型全不同 |
| EthereumAdapter | **0%** | hex 地址 vs bech32,JSON-RPC vs REST/abci |
| BitcoinAdapter(若 03 调研产出)| **0%** | UTXO vs Account |
| 新建 CosmosAdapter | **100%** | — |

### 决策

- [ ] 复用
- [x] **新建 `CosmosAdapter`**(Cosmos-SDK / Tendermint 族,**Osmosis / Celestia / Injective / Sei / Kava / Stride 等几十条链可复用此 adapter**,Phase 2.x 通过 `chain_type` 字段(同 EthereumAdapter `chain_type=bsc/ethereum/base` 模式)区分各链特殊性如 bech32 prefix / native denom / 自定义模块)
- [ ] 混合

### 理由

**3 段说明**:

(1) Cosmos 是独立族,与 Solana(SVM/PoH)、Ethereum(EVM)、Bitcoin(UTXO)账户模型完全不同 — 用 bech32 地址 + 多 denom 资产 + ABCI 二级路由 + Tendermint 共识。无现有 adapter 可复用。

(2) **本族高复用价值**:Cosmos Hub 之外,Osmosis(osmo1...)/ Celestia(celestia1...)/ Injective(inj1...)/ Sei(sei1...)/ Kava(kava1...)/ Stride(stride1...)/ Neutron(neutron1...)/ dYdX v4(dydx1...)等几十条链全部继承 Cosmos SDK + Tendermint ABCI 抽象,**API 端点路径完全相同**(只有 bech32 prefix 和 native denom 不同)。Phase 2.x 实施 CosmosAdapter 后,后续每条 Cosmos 系链只需新增 plugin JSON 配置(`bech32_prefix` + `native_denom` + `endpoint`),0 行 Python — 符合 Q4=C 的 95% 加链 0 Python 目标。

(3) **chain_type 模式参考 EthereumAdapter**:CosmosAdapter 应保留 `chain_type` 字段(`cosmos / osmosis / celestia / ...`),用于(a)bech32 prefix 验证(各链 hrp 不同);(b)native denom 配置(`uatom` / `uosmo` / `utia` / `inj`);(c)若某链有自定义模块(如 Osmosis 的 GAMM、Sei 的 dex)需要额外 path,在 adapter 内分支处理。

### 配置 JSON 示例(本链)

```json
{
  "chain": "cosmos",
  "family": "cosmos-sdk",
  "adapter": "CosmosAdapter",
  "chain_id_str": "cosmoshub-4",
  "node_app": "gaiad",
  "node_app_version": "v27.3.0",
  "consensus_version": "0.38.19",
  "api_protocol": "rest",
  "rpc_endpoint": "https://cosmos-rest.publicnode.com",
  "rpc_endpoint_tendermint": "https://cosmos-rpc.publicnode.com",
  "rpc_endpoint_grpc": "cosmos-grpc.publicnode.com:443",
  "block_time_ms": 6000,
  "finality": "instant",
  "address_format": {
    "encoding": "bech32",
    "hrp_account": "cosmos",
    "hrp_validator": "cosmosvaloper",
    "hrp_consensus": "cosmosvalcons",
    "length": 45,
    "regex": "^cosmos1[02-9ac-hj-np-z]{38}$"
  },
  "native_denom": "uatom",
  "native_decimals": 6,
  "rpc_methods": {
    "block_height": "GET /cosmos/base/tendermint/v1beta1/blocks/latest",
    "block_by_height": "GET /cosmos/base/tendermint/v1beta1/blocks/{height}",
    "balance": "GET /cosmos/bank/v1beta1/balances/{addr}",
    "balance_by_denom": "GET /cosmos/bank/v1beta1/balances/{addr}/by_denom?denom={denom}",
    "tx_lookup": "GET /cosmos/tx/v1beta1/txs/{hash}",
    "tx_search": "GET /cosmos/tx/v1beta1/txs?events={query}",
    "validators": "GET /cosmos/staking/v1beta1/validators?pagination.limit={limit}",
    "delegations": "GET /cosmos/staking/v1beta1/delegations/{delegator_addr}",
    "node_info": "GET /cosmos/base/tendermint/v1beta1/node_info",
    "syncing": "GET /cosmos/base/tendermint/v1beta1/syncing"
  },
  "param_formats": {
    "balance": "path_addr",
    "balance_by_denom": "path_addr_query_denom",
    "tx_lookup": "path_hash_upper_hex_no_prefix",
    "block_by_height": "path_height",
    "validators": "query_pagination",
    "block_height": "no_params",
    "node_info": "no_params",
    "syncing": "no_params"
  },
  "mixed_weights": {
    "balance": 0.30,
    "tx_lookup": 0.15,
    "block_by_height": 0.10,
    "block_height": 0.10,
    "validators": 0.10,
    "tx_search": 0.05,
    "delegations": 0.05,
    "balance_by_denom": 0.05,
    "node_info": 0.05,
    "syncing": 0.05
  },
  "system_addresses": [
    "cosmos1fl48vsnmsdzcv85q5d2q4z5ajdha8yu34mf0eh",
    "cosmos17xpfvakm2amg962yls6f84z3kell8c5lserqta",
    "cosmos1jv65s3grqf6v6jl3dp4t6c9t9rk99cd88lyufl",
    "cosmos1tygms3xhhs3yv487phx3dw4a95jn7t7lpm470r"
  ],
  "system_addresses_note": "上述为常见 module account(bank/distribution/staking/fee_collector)— Phase 2.x 实施前必须 E2 验证每个地址",
  "default_target_address": "cosmos1wypsnn7n5hsd2kvk424qv9yuretz9m6kvumev2",
  "tx_hash_format": {
    "encoding": "hex_upper_no_prefix",
    "tendermint_rpc_prefix": "0x",
    "rest_prefix": ""
  }
}
```

⚠️ **system_addresses 限制**:本调研未 E2 验证 module account 地址(需 SHA-256(module_name) → bech32 计算或查 explorer)。Phase 2.x 实施前必须实测,**当前列出的 4 个地址是 E5 SPECULATED**(根据 Cosmos SDK module account 派生规则推测,需验证)。

---

## 11. DSL 字段需求(Q4=C 95% 0 Python declarative DSL 输入)

### 11.1 RPC 调用协议

**Cosmos 的特殊性:三种协议并存,DSL 必须能 dispatch**

| 维度 | Tendermint RPC :26657 | Cosmos REST/LCD :1317 | Cosmos gRPC :9090 |
|---|---|---|---|
| 协议 | JSON-RPC 2.0(也支持 GET query string)| REST / HTTP(GET/POST)| gRPC over HTTP/2 + Protobuf |
| HTTP 方法 | POST(body)或 GET(query)| GET(查询)/ POST(广播)| HTTP/2 frames |
| 请求路径 | `/<method>` | `/cosmos/<module>/v1beta1/<resource>` | `<package>.<Service>/<Method>` |
| 鉴权 | 通常 public(publicnode 无 key)| 通常 public | 通常 public |
| Content-Type | `application/json` | `application/json` | `application/grpc` |

**DSL 鉴权字段建议**(Phase 2.x):
```yaml
auth:
  type: none | basic | bearer | api_key
  # bearer / api_key 时:
  header: "Authorization" | "X-API-Key"
  value_env: "COSMOS_API_KEY"  # 不写明文 key
```

### 11.2 method 调用 schema(每 method 一节)

**REST 协议(假设 DSL 选 REST,见 §11.8)**:

```yaml
methods:
  balance:
    http_method: GET
    path: "/cosmos/bank/v1beta1/balances/{addr}"
    path_params:
      - name: addr
        from: "$.target_address"
        validation: "^cosmos1[02-9ac-hj-np-z]{38}$"
    response_extract:
      balances: "$.balances[*]"
      first_denom: "$.balances[0].denom"
      first_amount: "$.balances[0].amount"
    error_codes:
      400: "invalid_address (bech32 fail)"
      501: "not_implemented"

  tx_lookup:
    http_method: GET
    path: "/cosmos/tx/v1beta1/txs/{hash}"
    path_params:
      - name: hash
        from: "$.cursor.tx_hash"
        transform: "upper_hex_no_prefix"
    response_extract:
      messages: "$.tx.body.messages[*]"
      msg_type: "$.tx.body.messages[0].@type"
      from: "$.tx.body.messages[0].from_address"
    error_codes:
      404: "tx_not_found"

  block_by_height:
    http_method: GET
    path: "/cosmos/base/tendermint/v1beta1/blocks/{height}"
    path_params:
      - name: height
        from: "$.cursor.height"
    response_extract:
      tx_count: "$.block.data.txs.length"
      time: "$.block.header.time"
      chain_id: "$.block.header.chain_id"
```

**Tendermint RPC 协议(作为对比)**:

```yaml
methods:
  block:
    http_method: GET  # 也支持 POST JSON-RPC
    path: "/block"
    query_params:
      - name: height
        from: "$.cursor.height"
    response_extract:
      hash: "$.result.block_id.hash"  # 大写 hex
      height: "$.result.block.header.height"  # String 类型!

  tx:
    http_method: GET
    path: "/tx"
    query_params:
      - name: hash
        from: "$.cursor.tx_hash"
        transform: "prefix_0x_upper_hex"  # 必须加 0x 前缀
      - name: prove
        value: false
    response_extract:
      height: "$.result.height"
      gas_used: "$.result.tx_result.gas_used"

  abci_query:  # ABCI 二级路由 — Cosmos 独有
    http_method: GET
    path: "/abci_query"
    query_params:
      - name: path  # 引号字面值!
        value: '"/cosmos.bank.v1beta1.Query/AllBalances"'
      - name: data  # protobuf hex,DSL 需支持 protobuf encode helper
        from: "$.encoded_protobuf"
    response_extract:
      value_base64: "$.result.response.value"  # 客户端需 base64 decode + protobuf decode
```

### 11.3 cursor / pagination 模型

**Cosmos 三种 cursor 模型(DSL 必须能表达)**:

| 模型 | 场景 | DSL 字段建议 |
|---|---|---|
| **height 递增**(单调整数)| block_by_height、validators?height=N | `cursor: { type: height_int, start: latest, increment: -1 }` |
| **next_key**(opaque 字符串,base64)| REST validators / delegations 等大列表的 `pagination.next_key` | `cursor: { type: opaque_next_key, response_path: "$.pagination.next_key", request_param: "pagination.key" }` |
| **page / per_page**(整数翻页)| Tendermint RPC `/validators?per_page=K&page=N`、`/tx_search` | `cursor: { type: page_offset, page_param: "page", per_page_param: "per_page" }` |
| **events 查询字符串**(用 `events=tx.height=N`)| REST tx_search | `cursor: { type: events_query, template: "tx.height={height}" }` |

E2 验证:`pagination.next_key` 是 base64 字符串(见 §3.2 validators 响应 `"next_key":"FArILLpzgq04+y5e2aCGDLtnvPQs"`);`pagination.total` 在 publicnode 上常为 `"0"`(节点未配置精确计数,这是已知行为,**不能信赖 total**)。

### 11.4 system addresses / 过滤规则

**Cosmos 应过滤的地址类型(框架决策点)**:

| 类型 | 示例 | 是否应过滤 |
|---|---|---|
| **Module accounts**(bank / distribution / fee_collector / staking)| `cosmos1fl48vsnmsdzcv85q5d2q4z5ajdha8yu34mf0eh`(bank,E5 待验证)| **是**(模块持有,非用户) |
| **Validator operator** | `cosmosvaloper1...` | 通常**否**(是真实业务地址)|
| **IBC channel escrow** | `cosmos1...` SHA-256(channel-N) 派生 | **是**(IBC 锁仓临时地址,不代表活跃用户) |
| **CEX hot wallets** | Binance / Kraken 等 | **否**(真实用户行为,benchmark 关注) |

**DSL 过滤字段建议**:
```yaml
account_filter:
  exclude_module_accounts: true   # 计算 module account 地址并过滤
  exclude_ibc_escrow: true        # SHA-256(channel-N) 派生地址过滤
  exclude_prefixes:
    - "cosmosvalcons1"            # consensus 地址不是普通账户
  custom_exclude:
    - "<额外地址>"
```

### 11.5 异构性标记(对比现有 8 链)

**Cosmos 与已有 8 链(solana / ethereum / bsc / base / scroll / polygon / starknet / sui)显著不同的维度**:

| # | 维度 | 已有 8 链 | Cosmos Hub | DSL 影响 |
|---|---|---|---|---|
| 1 | **API 协议** | 100% JSON-RPC 2.0(POST body)| **3 套并存**:Tendermint RPC(JSON-RPC)、REST/LCD(GET 路径)、gRPC | DSL 必须有 `api_protocol: jsonrpc \| rest \| grpc` enum;mock_rpc_server 必须加 `do_GET` |
| 2 | **地址编码** | base58(solana/sui)、hex(EVM 5 条)、felt(starknet)| **bech32 + hrp**(每链 hrp 不同:cosmos/osmo/celestia/inj/...)| DSL 需 `bech32_hrp` 字段;校验正则需含 hrp 变量 |
| 3 | **ChainID 类型** | 数字(EVM)/ 字符串 `mainnet-beta`(solana)/ 数字 hex(starknet)| **字符串** `cosmoshub-4` | DSL 需 `chain_id` 字段支持 string 类型 |
| 4 | **多资产模型** | 单 native + token(SPL/ERC20/...)| **单账户多 denom**(uatom + 多个 ibc/<hash>) | DSL 余额查询响应抽取需支持数组(`$.balances[*]`) |
| 5 | **ABCI 二级路由** | 无 | `/abci_query?path="/cosmos.bank.v1beta1.Query/AllBalances"` — **path 是字面值带引号** + data 是 protobuf hex | DSL 必须能表达:嵌套 path / protobuf 编码 helper |
| 6 | **tx hash 编码差异** | 各链统一 1 套 | **同一链 2 套**:Tendermint RPC 要 `0x` 前缀大写 hex,REST 要无前缀大写 hex | DSL transform 字段需支持 `prefix_0x` / `strip_0x` 转换 |
| 7 | **block hash 编码差异** | 各链统一 | **同一链 2 套**:Tendermint RPC 返大写 hex,REST 返 base64 | response_extract 需 base64-decode helper |
| 8 | **Finality** | Solana 32 slots / EVM N confirmations / Starknet probabilistic | **即时**(BFT 1 区块 final) | DSL 需 `finality: instant \| slots:N \| confirmations:N` enum |
| 9 | **节点 daemon 名** | 各链不同(solana-validator/geth/...)| **gaiad**(cosmos)/ **osmosisd** / **celestia-appd** / ... 每链不同 | 不影响 DSL,但影响 plugin metadata |

### 11.6 DSL 设计 ASK(给 P2-DESIGN-v2 的需求)

**必须支持的能力**:
1. **`api_protocol` enum**:`jsonrpc | rest | grpc`,plugin 必须声明,target_generator 据此选 vegeta target 格式
2. **HTTP method enum**:`GET | POST`(REST 多 GET,JSON-RPC 多 POST),mock_rpc_server 加 `do_GET`
3. **路径模板 + 占位符**:`/cosmos/bank/v1beta1/balances/{addr}` 类语法,占位符从 `$.target_address` / `$.cursor.X` 取
4. **`response_extract` JSONPath**:抽取响应字段(余额/高度/hash),供下一步 cursor 推进
5. **`bech32_hrp` 字段**:cosmos 系链每链 hrp 不同,plugin 声明后 adapter 内自动校验
6. **`chain_id` 支持 string 类型**:不能只允许 int
7. **多 denom 余额响应**:`$.balances[*]` 数组抽取,DSL JSONPath 引擎须支持 `[*]`
8. **`transform` 字段**:`upper_hex_no_prefix` / `prefix_0x_upper_hex` / `base64_decode` / `strip_0x` 等内置 helper
9. **`cursor.type` enum**:`height_int | opaque_next_key | page_offset | events_query`
10. **`account_filter` 块**:`exclude_module_accounts` / `exclude_ibc_escrow` / `exclude_prefixes`

**可选支持的能力**:
1. **`abci_query` 子协议**(若 DSL 选 Tendermint RPC):path 字面值 + protobuf hex 编码 helper — **复杂度高,建议 Phase 2.x 后再做**
2. **gRPC 协议**(若选 gRPC):需 protoc 编译 + grpc client,**当前无可复用基础设施,强烈建议跳过**
3. **WebSocket 订阅**:Tendermint RPC 支持 `/websocket` 订阅 events,本框架是 pull-based benchmark,**不需要**
4. **broadcast tx**:Cosmos 支持 `POST /cosmos/tx/v1beta1/txs`(广播签名 tx),benchmark **只读**,不需要

**不需要的能力**:
1. **客户端侧 protobuf 编码**(除非走 abci_query / gRPC)— REST 全 JSON,无需 protobuf 客户端库
2. **本地 keyring 集成** — 本框架只读 mainnet,不签 tx
3. **IBC 跨链状态机** — 复杂,benchmark 不关心

---

### 11.7 Cosmos 三套 API 实证对比(本节强制要求)

> **本节每行 E2 实测填**(2026-05-23 ~18:05 UTC),未实测的标 ⚠️。

| 维度 | Tendermint RPC :26657 | Cosmos REST/LCD :1317 | Cosmos gRPC :9090 |
|---|---|---|---|
| **协议** | JSON-RPC 2.0(支持 GET query 简写)— E2 | REST/HTTP(JSON 响应)— E2 | gRPC over HTTP/2 + Protobuf — ⚠️ 未 E2(无 grpcurl) |
| **balance 查询 method** | `abci_query?path="/cosmos.bank.v1beta1.Query/AllBalances"&data=<protobuf-hex>`(E3:需 protobuf 客户端编码 query)| `GET /cosmos/bank/v1beta1/balances/{addr}` — **E2 ✅** 返多 denom 余额数组 | `cosmos.bank.v1beta1.Query/AllBalances` — ⚠️ 未 E2 |
| **tx 查询 method** | `/tx?hash=0x<UPPER_HEX>&prove=false` — **E2 ✅** 返 hash/height/events | `GET /cosmos/tx/v1beta1/txs/{UPPER_HEX_NO_PREFIX}` — **E2 ✅** 返 messages 数组 | `cosmos.tx.v1beta1.Service/GetTx` — ⚠️ 未 E2 |
| **block 查询 method** | `/block?height=N` — **E2 ✅** 返 block_id.hash(**大写 hex**) | `GET /cosmos/base/tendermint/v1beta1/blocks/{height}` — **E2 ✅** 返 block_id.hash(**base64**) | `cosmos.base.tendermint.v1beta1.Service/GetBlockByHeight` — ⚠️ 未 E2 |
| **status / 高度** | `/status` — **E2 ✅** 含 sync_info.latest_block_height(String)| `GET /cosmos/base/tendermint/v1beta1/syncing` — **E2 ✅** `{"syncing":false}` | 类似 GetNodeInfo — ⚠️ 未 E2 |
| **abci_query path 编码** | **是**(`path="/store/<module>/key"` 或 `path="/<package>.<Service>/<Method>"`,**字面值带引号**)— E2 ✅ 跑了 `path="/app/version"` | **否**(直接 REST 路径)| **否**(原生 gRPC service method)|
| **pagination 模型** | `page` + `per_page` 整数翻页(E2 实测 `/tx_search?per_page=1`)| `pagination.limit` + `pagination.key`(opaque next_key,base64)— E2 ✅ 实测返 `"next_key":"FArILLpzgq04+y5e2aCGDLtnvPQs"` | gRPC stream(E3 文档)— ⚠️ 未 E2 |
| **鉴权** | publicnode 公益:public(无 key)— E2 | publicnode 公益:public — E2 | publicnode 公益:public(域名可达)— ⚠️ gRPC 调用未验 |
| **响应 hash 编码** | **大写 hex**(无前缀)— E2 ✅ `057D121688D530344FDF519E2D1A6C870FEBB4E82E4BF519555799A918E62C5F` | **base64**(注意!)— E2 ✅ `fjs2y78cAi4Y2/Ccz9mVBmBKjR3waIMv2jFb22qAFCw=` | 原生 protobuf bytes — ⚠️ 未 E2 |
| **错误格式** | `{"jsonrpc":"2.0","error":{"code":-32603,"message":"Internal error","data":"..."}}` — E2 ✅ | HTTP 错误码 + `{"code":N,"message":"...","details":[]}` — E2 ✅(如 bech32 fail 返 400 + code 3)| gRPC status code(`OUT_OF_RANGE` / `NOT_FOUND` / ...)— E3 文档 |
| **Content-Type 响应** | `application/json` | `application/json` | `application/grpc` |
| **DSL 实现复杂度** | **Medium**:与现有 8 链 JSON-RPC 同协议,但 `abci_query` 子协议需 protobuf 编码 helper,GET query 简写格式不同 | **Low**:纯 REST,响应直接可读,与 mock_rpc_server 协议层差异(GET vs POST)但 schema 简单 | **High**:需 protoc 编译 cosmos-sdk protos,无现成 Go/Python gRPC client 集成,框架基础设施空白 |

### 11.8 DSL 选择建议(本节强制要求)

**决策**:

- [ ] Tendermint RPC :26657(JSON-RPC,与现有 8 链协议同,DSL 复用度最高)
- [x] **Cosmos REST/LCD :1317**(REST,需 DSL 支持 path 参数)
- [x] **DSL 必须支持 protocol enum**(`jsonrpc | rest | grpc`)— 同时支持上述两种,plugin 自描述
- [ ] gRPC :9090(本框架放弃,理由见下)

**理由**(3 段):

**(1)REST/LCD 是本框架首选(主推)**

REST 协议层最简单 — 路径参数 + GET + JSON 响应,无需 protobuf 编码 helper,无需 abci_query 二级路由的字面值引号 + protobuf hex 怪异语法。E2 实测 `cosmos-rest.publicnode.com` 全部测试方法返 HTTP 200,响应 schema 稳定可解析(`$.balances[*]`、`$.tx.body.messages[0].from_address`、`$.block.header.height` 都是直观 JSONPath)。REST 模式下 DSL 复杂度增量最低 — 主要新需求是 `api_protocol: rest` enum + HTTP method GET 支持 + 路径模板占位符 + bech32 校验,这些是 28 链通用基础设施,**收益远大于专为 Cosmos 加的 abci_query 复杂度**。

**(2)DSL 必须保留 protocol enum(不锁死 REST)**

虽然 REST 是主推,但 DSL 不应硬编码 REST。Cosmos 生态有些链(如 Celestia 的数据采样查询)的某些 method 仅在 Tendermint RPC 暴露(REST gateway 未生成),且 Tendermint RPC 与现有 8 链协议同(JSON-RPC 2.0 POST),技术上复用更顺。Plugin 应能在 method 级别声明 `via: tendermint_rpc` 或 `via: rest`(混合),DSL 提供两种 target 生成器即可。**关键反转条件**:若 Phase 2.x 实测 publicnode REST 端点限流严重而 Tendermint RPC 限流宽松,plugin 可改 `api_protocol: jsonrpc` 切换,DSL 层无需重写。

**(3)gRPC 放弃理由**

gRPC 需要 protoc 编译 cosmos-sdk 全套 protobuf 定义(`cosmos/bank/v1beta1/query.proto` 等数十个文件)+ grpc client 集成 + 流式响应处理,本框架(Python + bash + vegeta)无任何现成 gRPC 基础设施(vegeta 不支持 gRPC,需要额外用 `grpcurl` 或 `ghz` 替代)。性能上 gRPC 仅比 REST 快 2-5x(无 JSON parse 开销),对 benchmark 框架(测节点而非测客户端开销)**性能差异不重要**。**反转条件**:若用户明确要求 benchmark 测节点的 gRPC 端点性能(因为生产链上交易所大量用 gRPC 拉数据),则单独引入 `ghz` 作为 gRPC vegeta 替代物,**但这是独立工程,不阻塞 REST 主路径**。

---

## Open Questions(待解决问题)

- [ ] **system_addresses 4 个 module account 未 E2 验证**(§10 配置 JSON 中标 SPECULATED)— Phase 2.x 实施前必须实测每个地址(可通过 `GET /cosmos/auth/v1beta1/module_accounts` 查 module account 列表 + 提取 base_account.address)
- [ ] **gRPC 实测缺失**(§3.3、§11.7)— 本环境无 grpcurl,Phase 2.x 实施前如选 gRPC 必须补 grpcurl 实测
- [ ] **publicnode REST 限流未知** — `cosmos-rest.publicnode.com` 公开速率限制文档未提供,Phase 2.x 实施时可能需要 `time.sleep` throttle(类似 Solana mainnet-beta < 10 req/s 推测)
- [ ] **abci_query data 字段 protobuf 编码** — 若 DSL 走 Tendermint RPC 路径,需要 Go/Python protoc 输出 cosmos-sdk proto 编码器,**当前框架无此基础设施**(选 REST 即可绕过此问题)
- [ ] **chain_type 字段命名空间** — 同 Ethereum chain_type=bsc/base/...,CosmosAdapter 的 chain_type 应为 `cosmos/osmosis/celestia/...`,但 Osmosis/Celestia 等是否会因为自定义模块(GAMM/数据采样)需要更细分?Phase 2.0 plugin 设计时决定
- [ ] **IBC token 余额标识** — REST 返回 `denom: "ibc/3622BC03..."` hash 形式,客户端需查询 `GET /ibc/apps/transfer/v1/denom_traces/{hash}` 反查原 chain + denom,benchmark 是否需要这一步?当前建议**否**(benchmark 测节点不需展示语义)
- [ ] **Tendermint RPC 与 REST endpoint 同步性** — 实测 publicnode 同时刻 RPC height=31248039、REST node_info 仍可访问(无延迟可见),但跨节点(rpc 走某节点、rest 走另一节点)是否会差几个 block?Phase 2.x 实测确认
- [ ] **多链共用 endpoint** — publicnode 提供 osmosis-rpc.publicnode.com / celestia-rpc.publicnode.com 等,Phase 2.x 加 Cosmos 系链时统一这套 endpoint 模式

---

## Changelog

| Date | Author | Change |
|---|---|---|
| 2026-05-23 | Hermes Agent | 初次调研:E2 实测 publicnode Tendermint RPC + REST 各 5 method(status/block/abci_info/tx/balance/validators/syncing/node_info/abci_query),gRPC 仅 E3 文档 + 端点存活,无 grpcurl 实测 |
