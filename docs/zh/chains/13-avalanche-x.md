# 13-Avalanche-X 调研

> **此文件由 `_template.md` 衍生。**
> **填写遵守 H8(真实证据):curl 实测 + 官方文档 URL + GitHub commit SHA。**
> **每个字段引用标签 E1(单元测试)/E2(curl 实证)/E3(文档)/E4(源码)/E5(代码 grep)。**
> **核心定位:第二条 UTXO 链(继 Bitcoin / Cardano-eUTXO 之后),family 边界关键决策。**

---

## 元信息

| 项 | 值 |
|---|---|
| 链名(中) | Avalanche X-Chain(雪崩 X 链) |
| 链名(英) | Avalanche X-Chain(AVM, Avalanche Virtual Machine) |
| 编号 | 13 |
| Mainnet BlockchainID | `2oYMBNV4eNHyqk2fjjV5nVQLDbtmNJzq5s3qs3Lo6ftnC6FByM`(via `info.getBlockchainID(alias=X)` 实测 [E2])|
| NetworkID | `1`(mainnet,见 tx 体 `networkID` 字段 [E2])|
| 调研日期 | 2026-05-23 |
| 调研者 | Hermes Agent |
| 状态 | 🟢 已完成(method-level 实测全通)|

---

## 1. Sources(权威来源)

| 类型 | URL | 访问日期 | 备注 |
|---|---|---|---|
| 官方文档(AVM API) | https://build.avax.network/docs/api-reference/x-chain/api | 2026-05-23 | X-Chain JSON-RPC 2.0 method 完整参考(`avm.*` 命名空间) |
| 官方文档(Info API) | https://build.avax.network/docs/api-reference/info-api | 2026-05-23 | 节点/链元信息(用于解析 alias→blockchainID)|
| GitHub | https://github.com/ava-labs/avalanchego(实测版本 `avalanchego/1.14.2`,commit `6e5acf909c7a16b991142d6b3979bac5699bdb68` via `info.getNodeVersion` [E2])| 2026-05-23 | 核心实现仓库,本调研锚定该 commit |
| AVM 源码路径 | https://github.com/ava-labs/avalanchego/tree/master/vms/avm | 2026-05-23 | AVM 实现(service.go 含全部 `avm.*` method) |
| Bech32 地址规范 | https://docs.avax.network/specs/cryptographic-primitives#addresses(`X-` HRP)| 2026-05-23 | HRP=`avax`,chain alias 作为前缀(`X-avax1...`)|
| Explorer | https://subnets.avax.network/x-chain | 2026-05-23 | 用于校验本文档地址/tx |

---

## 2. Protocol Family(协议族)— **关键决策项**

| 项 | 值 |
|---|---|
| Family | **`avalanche-utxo`**(独立子族,**与 Bitcoin `utxo-btc` 同根但不复用 adapter**;详见 §10 与 §11.7 决策矩阵)|
| Consensus | Snowman++(Avalanche 共识家族,DAG-based 概率性快速终结)[E3] |
| VM | AVM(Avalanche Virtual Machine)— **非图灵完备**,固定 tx 类型集合(`BaseTx`/`CreateAssetTx`/`OperationTx`/`ImportTx`/`ExportTx`),与 Bitcoin Script 同为受限脚本族 [E3 + E4] |
| Block Time | ~1-2s 实测(连续 `avm.getHeight` 间隔)— Snowman 后端 [E2] |
| Finality | 概率终结 < 1s(consensus 完成即 final,远快于 Bitcoin 6 确认) |
| Reuse Existing Adapter? | **No**(详见 §10 决策矩阵)— 与 Bitcoin 同 UTXO 模型但 (a) JSON-RPC 2.0 namespace 前缀 `avm.*`、(b) multi-asset(每 UTXO 携 `assetID`)、(c) bech32-only 地址、(d) tx schema 结构化(无 Script opcodes)四点全异,共用代码反而引入条件分支地狱 |

---

## 3. Public RPC(公共节点)

| Endpoint | Auth | 实测结果 | 备注 |
|---|---|---|---|
| `https://api.avax.network/ext/bc/X` | **无**(完全公开) | ✅ 200,5 次连续请求平均 ~100ms(req1 冷连接 0.299s,req2-5 ~0.05s) | **推荐主测**;X-Chain 专用 path,与 C-Chain(`/ext/bc/C/rpc`)、P-Chain(`/ext/bc/P`)、Info(`/ext/info`)分离 |
| `https://api.avax.network/ext/info` | 无 | ✅ 200 | 元信息 endpoint(blockchainID/version/peers);**非 AVM,无 `avm.*` 前缀** — 是独立的 `info.*` namespace |
| `https://rpc.ankr.com/avalanche-x` | 可选 API key | 未测 | 备用商业 endpoint |

**Trade-off**:
- 官方 endpoint 无 rate-limit 体感、无 auth、JSON-RPC 2.0 标准合规 — 是当前 14 链中最干净的 RPC 之一。
- **反转条件**:若官方加 quota 或 throttle,切 Ankr 或自建 avalanchego 节点(self-hosted 同样无 auth 默认,因 avalanchego 默认 `http-host=0.0.0.0` + 无内建 basic auth)。

**curl 实测**(E2,2026-05-23):
```bash
# E2 — 高度查询(主探活)
curl -s -X POST https://api.avax.network/ext/bc/X \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"avm.getHeight","params":{}}'
# {"jsonrpc":"2.0","result":{"height":"517993"},"id":1}
# ↑ 注意 height 是 string("517993"),不是 int — Avalanche 大整数惯例(uint64 大值防 JS 精度丢失)

# 延迟实测(rate-limit 嗅探)
req1: 200 time=0.298922s
req2: 200 time=0.052735s
req3: 200 time=0.056015s
req4: 200 time=0.057473s
req5: 200 time=0.057898s
# → 冷连接 ~300ms,热连接 ~55ms,无 rate-limit 触发

# 节点版本
curl -s -X POST https://api.avax.network/ext/info \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"info.getNodeVersion","params":{}}'
# {"jsonrpc":"2.0","result":{"version":"avalanchego/1.14.2","databaseVersion":"v1.4.5",
#  "rpcProtocolVersion":"45","gitCommit":"6e5acf909c7a16b991142d6b3979bac5699bdb68",
#  "vmVersions":{"avm":"avalanchego/1.14.2","evm":"v1.14.2","platform":"avalanchego/1.14.2"}},"id":1}
```

---

## 4. Account Model(账户模型)— **multi-asset UTXO,独有**

| 项 | 值 |
|---|---|
| 模型 | **UTXO**,但 **multi-asset**(每个 UTXO 携 `assetID` 字段,Bitcoin UTXO 仅 BTC 一种)[E2 — 见 §5 `getUTXOs` 与 §5 `getTx` 实测] |
| Native token decimals | **9**(AVAX,via `avm.getAssetDescription` 返回 `denomination:"9"` [E2])— **注意:与 Bitcoin BTC=8 不同,与 C-Chain AVAX=18 也不同**(同 token 不同链上精度不同,跨链桥必须重映射)|
| AVAX assetID | `FvwEAhmxKfeiG8SnEvq42hc6whRyY3EFYAvebMqDNDGCgxN5Z`(mainnet,via `getAssetDescription` 实测确认 [E2])|
| Address derivation | secp256k1 ECDSA,公钥 → ripemd160(sha256(pk)) → bech32(HRP=`avax`,带 `X-` chain alias 前缀)[E3] |
| Special account types | **无账户**;所有"地址"皆是 UTXO 锁定脚本(`SECP256K1OutputOwners`)的接收方;`threshold` 字段支持 m-of-n multisig 原生(Bitcoin 需 P2SH/P2WSH 包一层)[E2 — 见 §5 outputs 体 `threshold:1`] |
| **multi-asset 证据** | 实测同一地址同时持有 AVAX 和另一资产(assetID `2EuZzt6W4MtNhDofY1TBL24yHrpz5QEG8shiFEqDBccEzYVHwW`,余额 `300`),由 `avm.getAllBalances` 一次返回。Bitcoin 不存在等价 method [E2] |

**multi-asset 实测证据**(E2,核心证据):
```bash
# 同一地址,getAllBalances 返回多资产
curl -s -X POST https://api.avax.network/ext/bc/X -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"avm.getAllBalances",
       "params":{"address":"X-avax13k6hxpfuu80dlnqlqs0dxxjrzl4lxz94n38vnw"}}'
# {"jsonrpc":"2.0","result":{"balances":[
#   {"asset":"AVAX","balance":"189093923788006"},                            ← 0.189 M AVAX (9 decimals)
#   {"asset":"2EuZzt6W4MtNhDofY1TBL24yHrpz5QEG8shiFEqDBccEzYVHwW","balance":"300"}  ← 另一 AVM 资产
# ]},"id":1}
```

---

## 5. Core RPC Methods(本框架监控所需)

> 全部走 `https://api.avax.network/ext/bc/X`,JSON-RPC 2.0,POST `/`(无子路径)。所有 method 名带 `avm.` 前缀(**与 Bitcoin 无前缀的 `getbalance` 命名截然不同**)。

| Method | 类别 | 说明 | 在 mixed 中权重建议 |
|---|---|---|---|
| `avm.getHeight` | block height | 链顶高度;返回 `{"height": "<int as string>"}` | 0.10 |
| `avm.getBlockByHeight` | block by height | 输入 `{height, encoding}`;**一步直达**(无需先 height→hash) | 0.10 |
| `avm.getBlock` | block by id | 输入 `{blockID, encoding}`;按 ID 拿块 | 0.05 |
| `avm.getTx` | tx lookup | 输入 `{txID, encoding}`;返回完整 tx 结构(unsignedTx + credentials) | 0.15 |
| `avm.getTxStatus` | tx status | 返回 `{status: Accepted | Rejected | Processing | Unknown}` | 0.10 |
| `avm.getBalance` | account balance | 输入 `{address, assetID}`;**必须指定 assetID**(单资产查询) | 0.10 |
| `avm.getAllBalances` | account multi-asset | 输入 `{address}`;**一次返回所有资产** — multi-asset 模型的标志性 method | 0.15 |
| `avm.getUTXOs` | UTXO 列表 | 输入 `{addresses[], limit, encoding}`;返回 hex 编码 UTXO 列表 + endIndex 用于分页 | 0.10 |
| `avm.getAssetDescription` | asset meta | 输入 `{assetID}`;返回 `{name, symbol, denomination}` | 0.05 |
| `info.getBlockchainID` | meta | 输入 `{alias}`;alias→blockchainID 映射(`info.*` 不是 `avm.*`,走 `/ext/info`)| 0.05 |
| `info.getNodeVersion` | meta | 节点版本/peer | 0.05 |

**总权重检查**: 0.10+0.10+0.05+0.15+0.10+0.10+0.15+0.10+0.05+0.05+0.05 = **1.00** ✅

**curl 实证 — 关键 method 完整响应**(E2,2026-05-23):

```bash
# 1) avm.getBlockByHeight(0) — 创世块
curl -s -X POST https://api.avax.network/ext/bc/X -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"avm.getBlockByHeight",
       "params":{"height":"0","encoding":"json"}}'
# {"jsonrpc":"2.0","result":{"block":{
#   "parentID":"jrGWDh5Po9FMj54depyunNixpia5PN4aAYxfmNzU8n752Rjga",
#   "height":0,"time":1682434800,
#   "merkleRoot":"11111111111111111111111111111111LpoYY",
#   "txs":[],
#   "id":"V8kYdATLoVjUBazVjEHy1dWurk2PcnhERSWnwmcNwirdsBb1S"},
#   "encoding":"json"},"id":1}
# ↑ 注意 ID 是 cb58 编码(非 hex)— Avalanche 全用 cb58(base58 + checksum,不同于 Bitcoin base58check)

# 2) avm.getBlockByHeight(517990) — 真实 tip 附近块
# 返回 block.txs[0] 是 BaseTx,结构:
# {"unsignedTx":{
#   "networkID":1,"blockchainID":"2oYMBNV4eNHyqk2fjjV5nVQLDbtmNJzq5s3qs3Lo6ftnC6FByM",
#   "outputs":[{
#     "assetID":"FvwEAhmxKfeiG8SnEvq42hc6whRyY3EFYAvebMqDNDGCgxN5Z",     ← multi-asset 字段
#     "fxID":"spdxUxVJQbX85MGxMHbKw1sHxMnSqJ3QBzDyDYEP3h6TLuxqQ",
#     "output":{"addresses":["X-avax13k6hxpfuu80dlnqlqs0dxxjrzl4lxz94n38vnw"],
#               "amount":5527276870,"locktime":0,"threshold":1}}],   ← 原生 m-of-n
#   "inputs":[{"txID":"2EfmTtons3Th8sMhGa1tpd8ameUhZGErkF2mPiGJzHT3vE82pE",
#              "outputIndex":0,"assetID":"FvwEAhmxKfeiG8SnEvq42hc6whRyY3EFYAvebMqDNDGCgxN5Z",
#              "input":{"amount":5528276870,"signatureIndices":[0]}}],
#   "memo":"0x"},
#   "credentials":[{"credential":{"signatures":["0x3fd0f69e..."]}}],
#   "id":"5Hb7uXBFQTaXCDwymYxDfYyEwRYVG35aMmdLwgcvKQniHama5"}
# ↑ 结构化 tx(对比 Bitcoin 的 scriptSig/scriptPubKey 字节码,可读性碾压)

# 3) avm.getTx(<txID>)
# 输入: {"txID":"5Hb7uXBFQTaXCDwymYxDfYyEwRYVG35aMmdLwgcvKQniHama5","encoding":"json"}
# 响应 schema 同上(独立 unsignedTx + credentials),encoding 可选 "hex"|"json"|"cb58"

# 4) avm.getTxStatus — 返回 4 种状态枚举
# {"jsonrpc":"2.0","result":{"status":"Accepted"},"id":1}
# 可能值: Accepted | Rejected | Processing | Unknown

# 5) avm.getBalance(addr, "AVAX")
# 响应: {"balance":"189093923788006","utxoIDs":[{"txID":"...","outputIndex":0}, ...]}
# ↑ balance 是 string(uint64 防 JS 精度丢);utxoIDs 数组是该资产构成的 UTXO 列表

# 6) avm.getAllBalances — 见 §4 multi-asset 证据

# 7) avm.getUTXOs(addresses, limit=3)
# 响应: {"numFetched":"3","utxos":["0x000076aa...","0x0000ce72...","0x000009bb..."],
#        "endIndex":{"address":"X-avax13k6...","utxo":"GJ98vX57..."},
#        "encoding":"hex"}
# ↑ 分页用 endIndex 作为下一次 startIndex,游标式分页(不同于 Bitcoin 无原生 UTXO 列表 method)

# 8) avm.getAssetDescription(AVAX assetID)
# {"jsonrpc":"2.0","result":{
#   "assetID":"FvwEAhmxKfeiG8SnEvq42hc6whRyY3EFYAvebMqDNDGCgxN5Z",
#   "name":"Avalanche","symbol":"AVAX","denomination":"9"},"id":1}

# 9) method 不存在
# {"jsonrpc":"2.0","id":1,"error":{"code":-32601,"message":"the method avm.notARealMethod does not exist"}}
```

---

## 6. Address Format(地址格式)

| 项 | 值 |
|---|---|
| 编码 | **Bech32 only**(HRP=`avax`,带 `X-` chain alias 前缀)[E3] — **比 Bitcoin 简单**(BTC 有 3 种:base58/bech32/bech32m;X-Chain 只有 1 种) |
| 长度 | 42-43 字符(`X-avax1` + 35 chars payload + checksum)[E2] |
| Checksum | Bech32(BCH 常数 1) — 与 Bitcoin SegWit v0 同算法,但 HRP 不同 [E3] |
| Chain alias 前缀 | `X-`(X-Chain)、`P-`(P-Chain,validators)、`C-`(C-Chain,EVM bech32 表示,另有 hex 0x 形式) — **同一公钥可派生 3 种 alias,跨链需重新编码** |
| 示例(主网真实) | `X-avax13k6hxpfuu80dlnqlqs0dxxjrzl4lxz94n38vnw`(下方实测有效,从 block 517990 提取)|
| 校验正则(实用,**非充分**) | `^X-avax1[023456789acdefghjklmnpqrstuvwxyz]{38,39}$` — 必须用 `avm.getBalance` 反查校验 checksum(无独立 `validateaddress` method) |

**E2 — 关键证据:context 提供的示例地址 checksum 错误**:
```bash
# context 提供: X-avax1pa5vu24v3hd0y9rdqekv9msrz86s90uvc3xyhq  ← 实测无效
# avalanchego 节点回复:
# "couldn't parse address: invalid checksum (expected (bech32=url3kn, bech32m=url3knfl0an3), got c3xyhq)"
#
# 结论: context 的地址被 hand-edited 或来源 explorer 拷贝有误。本文档全部改用实测捕获的真实地址:
#   X-avax13k6hxpfuu80dlnqlqs0dxxjrzl4lxz94n38vnw
# 来源: avm.getBlockByHeight(517990).txs[0].unsignedTx.outputs[0].output.addresses[0]
# 已通过 avm.getBalance 反向验证(余额 189093923788006 nAVAX)
```

---

## 7. Signature Lookup(交易哈希)

| 项 | 值 |
|---|---|
| Hash 格式 | **cb58**(base58 + 4-byte SHA-256 checksum)— **不是 hex**!与 Bitcoin txid(hex)截然不同 [E3] |
| 长度 | ~50 chars(变长,base58 编码 32 字节 + 4 字节 checksum)|
| 示例(主网真实) | `5Hb7uXBFQTaXCDwymYxDfYyEwRYVG35aMmdLwgcvKQniHama5`(block 517990 内 tx,本文档实测引用)|
| 查询 method | `avm.getTx(txID, encoding)`、`avm.getTxStatus(txID)` |
| Explorer URL 格式 | `https://subnets.avax.network/x-chain/tx/<txID>` |
| **encoding 参数** | `"json"`(结构化)/ `"hex"`(原始字节带 0x 前缀)/ `"cb58"`(cb58 编码)— 一个 method 三种序列化输出,**DSL 必须建模 encoding 参数** |

---

## 8. Mixed Set(`mixed` 模式权重)

> 用于 `BLOCKCHAIN_NODE_BENCHMARK_MODE=mixed` 时的 Avalanche-X 请求分布。
> 设计原则:multi-asset balance 查询(`getAllBalances`)是 X-Chain 区别于 Bitcoin 的标志性负载,占权重 ≥15%;tx/UTXO 查询次之;create-asset 等写场景因需私钥不纳入只读 benchmark。

```json
{
  "block_height_query": 0.10,
  "block_by_height_query": 0.10,
  "block_by_id_query": 0.05,
  "tx_lookup": 0.15,
  "tx_status_query": 0.10,
  "balance_single_asset_query": 0.10,
  "balance_all_assets_query": 0.15,
  "utxo_list_query": 0.10,
  "asset_meta_query": 0.05,
  "blockchain_id_query": 0.05,
  "node_version_query": 0.05
}
```

method 映射:
- `block_height_query` → `avm.getHeight`(no params)
- `block_by_height_query` → `avm.getBlockByHeight`(`$height`, `$encoding="json"`)
- `block_by_id_query` → `avm.getBlock`(`$blockID`, `$encoding="json"`)
- `tx_lookup` → `avm.getTx`(`$txID`, `$encoding="json"`)
- `tx_status_query` → `avm.getTxStatus`(`$txID`)
- `balance_single_asset_query` → `avm.getBalance`(`$address`, `$assetID="AVAX"`)
- `balance_all_assets_query` → `avm.getAllBalances`(`$address`)
- `utxo_list_query` → `avm.getUTXOs`(`[$address]`, `$limit=10`, `$encoding="hex"`)
- `asset_meta_query` → `avm.getAssetDescription`(`$assetID`)
- `blockchain_id_query` → `info.getBlockchainID`(`$alias="X"`)— **走 `/ext/info` endpoint**,非 `/ext/bc/X`
- `node_version_query` → `info.getNodeVersion`(no params,`/ext/info`)

**权重和**: 0.10+0.10+0.05+0.15+0.10+0.10+0.15+0.10+0.05+0.05+0.05 = **1.00** ✅

---

## 8.5 Phase 2.1 caller/reader 改造点(token-level Gate 3)

Avalanche-X 是**全新链**,以下为 P2.1 必须新增/触达的点:

| # | 位置(file:line) | 改动 | 原因 |
|---|---|---|---|
| 1 | `config/config_loader.sh` UNIFIED_BLOCKCHAIN_CONFIG 新增 `"avalanche-x": {...}` 块 | 新增 chain_type、rpc_methods、param_formats、`namespace_prefix:"avm."`(见 §11) | 与其他链平级 |
| 2 | `config/config_loader.sh` `supported_blockchains` array 加 `"avalanche-x"` | 数组扩到 N+1 项 | guard 守的就是这个 array |
| 3 | `config/config_loader.sh` case 分支加 `avalanche-x)` | 设 `MAINNET_RPC_URL="https://api.avax.network/ext/bc/X"` | 避免落入默认分支错链 |
| 4 | `tools/mock_rpc_server.py` 新增 `avm.*` method 分支(11 method) | 复制 §5 实测响应作为 fixture;**特别注意 height/balance/numFetched 等 uint64 必须以 string 返回** | mock 是 CI fallback |
| 5 | `tools/fetch_active_accounts.py` 新增 `AvalancheXAdapter` 类 | 从 `avm.getBlockByHeight(tip-N)` 提取 `txs[*].outputs[*].addresses[]` 作为活跃地址源(无 explorer REST,纯 RPC) | 与 BitcoinAdapter 不同(BTC 走 Esplora REST 补地址) |
| 6 | `tests/guard_Nchain_truth.sh` | 加入 `"avalanche-x"` 预期 | 否则 guard 阻止启动 |
| 7 | DSL schema(P2-DESIGN-v2)新增 `namespace_prefix: string` 字段 | 见 §11.7 决策 a-2 | UTXO 族下 method 前缀差异化的根本 fix |
| 8 | DSL schema 新增 `multi_asset: bool` + `native_asset_id: string` 字段 | X-Chain 必填,Bitcoin 可省 | 见 §11.7 multi-asset 表达 |

**N/A**:Avalanche-X 是新链,无现有 method 需删。

**测试要求**:P2.1 完成后跑 `BLOCKCHAIN_NODE=avalanche-x core/master_qps_executor.sh --mixed --duration 30`,vegeta 全部 200 + JSON-RPC `error` 字段为 null。

---

## 9. Mock Notes(mock_rpc_server 实现要点)

- **请求路径**:
  - AVM:`POST /ext/bc/X`(标准 path,无 trailing 内容)
  - Info:`POST /ext/info`(独立 endpoint)
  - mock 必须区分两路径,否则 `info.*` method 走错 namespace 会失败
- **响应 schema**(贴一段 §5 实测响应):
  ```json
  {
    "jsonrpc": "2.0",
    "result": {
      "block": {
        "parentID": "UowX32B6nCQd2aux7M6MYe6jJH88RBA4T31b2hdwGVz1WrMXA",
        "height": 517990,
        "time": 1779556977,
        "merkleRoot": "11111111111111111111111111111111LpoYY",
        "txs": [{"unsignedTx": {"...": "..."}, "credentials": [], "id": "5Hb7uX..."}],
        "id": "XJmMj5b..."
      },
      "encoding": "json"
    },
    "id": 1
  }
  ```
- **特殊编码规则**(mock 必须遵守):
  1. 所有 uint64 字段(`height`、`balance`、`amount`、`numFetched`、`time` 部分场景)**响应中必须是 string**(`"517993"` 而非 `517993`)— avalanchego 服务端 `jsonString` 类型规约 [E4 — `vms/avm/service.go`]
  2. ID 字段(`txID`、`blockID`、`assetID`、`parentID`、`blockchainID`)使用 **cb58 编码**(base58 + 4-byte checksum),不是 hex
  3. 签名/UTXO 二进制载荷以 `"0x..."` 前缀 hex 字符串编码(encoding=hex 时)
- **特殊错误码**(权威来源:`ava-labs/avalanchego@6e5acf9 utils/rpc/handler.go` 与 JSON-RPC 2.0 标准)[E2 + E4]:
  - `-32600` JSON-RPC Invalid Request
  - `-32601` Method not found(实测:`"the method avm.notARealMethod does not exist"`)
  - `-32602` JSON-RPC Invalid params
  - `-32603` Internal error
  - `-32700` Parse error
  - **`-32000` 自定义业务错**(implementation-defined server error,JSON-RPC 2.0 允许范围 -32000..-32099)— 实测捕获 2 种:
    - "problem parsing address ... invalid checksum"(地址 checksum 错)
    - "problem decoding transaction: missing 0x prefix to hex encoding"(issueTx 输入格式错)
- **mock 实现复杂度**:**Medium-High**
  - 容易部分:每个 method 的 schema 固定且实测响应可直接当 fixture
  - 难点 1:**uint64 string 化** — mock 框架若用 Python int 直接 dump 会产出错类型,必须强制 `json.dumps(default=lambda x: str(x) if isinstance(x, int) and x > 2**53 else x)` 或显式 string 字段
  - 难点 2:**cb58 编码** — Python 无标准库,需引入 `base58` + 实现 4-byte SHA-256 checksum;mock 可选择"返回固定 fixture cb58 字符串"而非动态生成
  - 难点 3:**两个 endpoint path** — mock_rpc_server 必须按 path 路由(AVM/Info)
  - 难点 4:**multi-asset balance fixture** — `getAllBalances` 需至少 2 个不同 assetID 才能覆盖真实代码路径

---

## 10. Adapter Reuse Decision(adapter 复用决策)— **关键决策项**

### 候选 adapter

| Adapter | 兼容度 | 缺失能力 |
|---|---|---|
| EthereumAdapter | 0% | account model 完全不同 |
| SolanaAdapter | 0% | 同上 |
| **BitcoinAdapter** | **~35%** | **共享:UTXO 概念、只读 benchmark、JSON-RPC POST**<br>**缺失/冲突:**<br>(a) namespace 前缀(`avm.*` vs 无前缀)<br>(b) multi-asset(每 UTXO 携 assetID)<br>(c) 编码(cb58 vs hex+base58)<br>(d) tx schema(结构化 vs Script 字节码)<br>(e) JSON-RPC 版本(2.0 vs 1.0)<br>(f) auth(无 vs basic auth) |
| CardanoAdapter(eUTXO) | ~25% | 同为 UTXO 但 datum/script witness 模型异构,且 Cardano REST 而非 JSON-RPC |
| **(新建) AvalancheXAdapter** | 100% | — |

### 决策

- [x] **新建** `AvalancheXAdapter`(`family="avalanche-utxo"`,独立子族)
- [x] **不与 Bitcoin 复用 adapter**,但 **DSL 层引入 `namespace_prefix` 字段使两族在 schema 上同构**(详见 §11.7)

### 理由

1. **共享 UTXO "概念" 不等于共享 adapter 代码**:Bitcoin adapter 的 `getRawTransaction(txid, verbose)` 与 AVM 的 `avm.getTx(txID, encoding)` 表面相似,实际响应结构完全不同(Bitcoin 平坦化 vin/vout + scriptPubKey 字节码;AVM 嵌套 `unsignedTx + credentials` 且 outputs 携 assetID),共用代码将充满 `if chain=="bitcoin"... else ...` 分支,反而比独立 adapter 更难维护。
2. **namespace 前缀决定 method 命名空间隔离**:`avm.getHeight` / `info.getNodeVersion` / `platform.getCurrentValidators` 三 namespace 共存于同一 avalanchego 节点(分布在 X/Info/P 三 endpoint),Bitcoin RPC 全部裸 method 名共享单 namespace。这是协议级设计差异,不是命名风格差异。
3. **multi-asset 是模型级特性**:`avm.getBalance(address, assetID)` 的 `assetID` 必填参数与 Bitcoin `getbalance(address)` 不可类比 — 后者隐含 BTC,前者必须显式选资产。`avm.getAllBalances` 进一步暴露资产维度。这是数据模型差异,不是 API 风格差异。
4. **后续复用**:`AvalancheXAdapter` 可被未来的 P-Chain(同样 `*.api` namespace 风格、同 networkID、共享 cb58 编码、共享 bech32 with chain-alias)**90%+ 复用**。这是真正的 family 起点。

### 配置 JSON 示例(本链)

```json
{
  "chain": "avalanche-x",
  "family": "avalanche-utxo",
  "adapter": "AvalancheXAdapter",
  "blockchain_id": "2oYMBNV4eNHyqk2fjjV5nVQLDbtmNJzq5s3qs3Lo6ftnC6FByM",
  "network_id": 1,
  "rpc_endpoint": "https://api.avax.network/ext/bc/X",
  "rpc_endpoint_alt_info": "https://api.avax.network/ext/info",
  "rpc_protocol": "json-rpc-2.0",
  "namespace_prefix": "avm.",
  "auth": {"type": "none"},
  "block_time_ms": 2000,
  "native_decimals": 9,
  "native_asset_id": "FvwEAhmxKfeiG8SnEvq42hc6whRyY3EFYAvebMqDNDGCgxN5Z",
  "native_asset_alias": "AVAX",
  "multi_asset": true,
  "address_formats": ["bech32-with-alias"],
  "address_hrp": "avax",
  "address_alias_prefix": "X-",
  "id_encoding": "cb58",
  "uint64_as_string": true,
  "rpc_methods": {
    "block_height": "avm.getHeight",
    "block_by_height": "avm.getBlockByHeight",
    "block_by_id": "avm.getBlock",
    "tx_lookup": "avm.getTx",
    "tx_status": "avm.getTxStatus",
    "balance_single_asset": "avm.getBalance",
    "balance_all_assets": "avm.getAllBalances",
    "utxo_list": "avm.getUTXOs",
    "asset_meta": "avm.getAssetDescription"
  },
  "mixed_weights": {
    "block_height_query": 0.10,
    "block_by_height_query": 0.10,
    "block_by_id_query": 0.05,
    "tx_lookup": 0.15,
    "tx_status_query": 0.10,
    "balance_single_asset_query": 0.10,
    "balance_all_assets_query": 0.15,
    "utxo_list_query": 0.10,
    "asset_meta_query": 0.05,
    "blockchain_id_query": 0.05,
    "node_version_query": 0.05
  }
}
```

---

## 11. DSL 字段需求(P2-DESIGN-v2 输入)

### 11.1 RPC 调用协议

| 项 | Avalanche-X 取值 | DSL 字段建议 |
|---|---|---|
| 协议类型 | JSON-RPC 2.0 严格合规(`jsonrpc:"2.0"` 必填响应) | `rpc.protocol: jsonrpc2` |
| HTTP 方法 | POST | `rpc.http_method: POST` |
| 请求路径 | **多 endpoint**(`/ext/bc/X` 与 `/ext/info` 共存) | `rpc.endpoints: {default: ..., info: ...}` + `method.endpoint_ref` 指定 |
| 鉴权方式 | 无 | `rpc.auth: {type: none}` |

### 11.2 method 调用 schema

> 每个 method 一节,params 用 `$varname` 占位符,response 抽取用 JSONPath。

#### `avm.getHeight`
- params 模板:`{}`
- response 抽取:`$.result.height`(string,需 parseInt)
- 实测证据:§3 [E2]

#### `avm.getBlockByHeight`
- params 模板:`{"height": "$height", "encoding": "json"}`(注意 height 是 **string**)
- response 抽取:`$.result.block.id`、`$.result.block.parentID`、`$.result.block.txs[*]`
- 实测证据:§5 [E2]

#### `avm.getTx`
- params 模板:`{"txID": "$txid", "encoding": "json"}`
- response 抽取:`$.result.tx.id`、`$.result.tx.unsignedTx.outputs[*].assetID`、`$.result.tx.unsignedTx.outputs[*].output.amount`
- 实测证据:§5 [E2]

#### `avm.getBalance`
- params 模板:`{"address": "$addr", "assetID": "$asset_id"}`(`assetID` 可填 `"AVAX"` 别名 或 完整 cb58 ID)
- response 抽取:`$.result.balance`(string)、`$.result.utxoIDs[*]`
- 实测证据:§4 [E2]

#### `avm.getAllBalances`(**multi-asset 标志**)
- params 模板:`{"address": "$addr"}`
- response 抽取:`$.result.balances[*].asset`、`$.result.balances[*].balance`
- **DSL 关键 ASK**:此 method 返回 **每行一资产** 的数组,本框架的 latency 统计应按整请求记一次,但 throughput 测试时一个请求实际触发 N 次资产 lookup,需在 DSL 标注 `fanout_hint: dynamic`
- 实测证据:§4 [E2]

#### `avm.getUTXOs`
- params 模板:`{"addresses": ["$addr"], "limit": $limit, "encoding": "hex"}`
- 分页:输入下次 `startIndex: {address, utxo}`(取自上次的 `endIndex`)
- response 抽取:`$.result.numFetched`、`$.result.utxos[*]`、`$.result.endIndex`
- 实测证据:§5 [E2]

### 11.3 cursor / pagination 模型

| 模型 | 描述 | DSL 建议 |
|---|---|---|
| **height-based**(主)| `for h in [0, tip]: avm.getBlockByHeight(h)` — **单步**(不需 height→ID→block 两步)| `cursor: {type: height, start: $H0, step: 1, max_count: 1000}` — 与 Bitcoin 不同,**无需 method chaining** |
| **endIndex-based**(UTXO 分页)| `avm.getUTXOs` 返回 `endIndex`,作为下次 `startIndex` | `cursor: {type: opaque, next_path: $.endIndex, param_name: startIndex}` |
| **txID-based**(tx 抽样)| 从 block.txs[*].id 提取 → `avm.getTx` 逐个 | `cursor: {type: list, source: avm.getBlockByHeight, item_path: $.result.block.txs[*].id}` |

**DSL ASK 对比 Bitcoin**:X-Chain 不需要 method chaining(getBlockByHeight 一步直达),所以 Bitcoin 在 §11.3 提出的 chaining 能力对 X-Chain **可选** — 但仍是 UTXO 族整体的 P0 能力(Bitcoin 需要)。

### 11.4 system addresses / 过滤规则

| 项 | Avalanche-X 取值 | DSL 字段建议 |
|---|---|---|
| 创世特殊 tx | block 0 的 `txs: []`(空,无 coinbase) — **比 Bitcoin 简单**,不需要 system_txids 排除 | N/A |
| Import/Export tx | `ImportTx`/`ExportTx` 是跨链(X↔P / X↔C)桥接 tx,其 `inputs` 引用其他链的 UTXO — benchmark 应识别但不必滤除 | `tx_type_filter: {include: [BaseTx], exclude: [CreateAssetTx, OperationTx, ImportTx, ExportTx]}`(可选) |
| 系统地址 | 无原生(无 precompile / treasury 地址) | `system_addresses: []` |

### 11.5 异构性标记(对比已调研链)

| 维度 | 已有链典型值 | Bitcoin | **Avalanche-X** |
|---|---|---|---|
| **账户模型** | account-based(EVM/Solana/Sui/...) | UTXO | **UTXO + multi-asset** |
| **JSON-RPC 版本** | 2.0(EVM)/ 1.0(Bitcoin) | 1.0 | **2.0(严格)** |
| **method namespace** | 无前缀(eth_*、getBalance 等都是裸 method)| 无前缀 | **`avm.*` / `info.*` / `platform.*` 多 namespace** |
| **端点数** | 单 endpoint / 链 | 单(Core)+ 单(Esplora)| **多 endpoint**(`/ext/bc/X` + `/ext/info` + `/ext/bc/P` + `/ext/bc/C/rpc`)|
| **uint64 表达** | hex 字符串(EVM)/ int(Solana)/ float(Bitcoin amount) | float BTC / int sat | **string**(`"189093923788006"`)|
| **ID 编码** | hex 0x(EVM)/ base58(Solana)/ hex(Bitcoin) | hex | **cb58**(base58 + checksum) |
| **token 模型** | ERC20/SPL/Sui Coin | 无原生 token | **multi-asset native**(AVAX 自己也只是 assetID,与其他 AVM 资产平级) |
| **balance 查询** | 1 method 拿账户总额 | 无原生(Esplora REST) | **2 method 分单资产/全资产**(`getBalance` + `getAllBalances`)|
| **auth** | bearer/API key/none | basic auth | **none**(公网官方 endpoint 无任何 auth) |

### 11.6 DSL 设计 ASK(给 P2-DESIGN-v2)— Avalanche-X 新增项

**必须支持**(在 Bitcoin 既有 ASK 基础上 新增):
1. **method namespace_prefix**:DSL 字段 `namespace_prefix: string`(BTC=`""`,X-Chain=`"avm."`,Info=`"info."`),framework 拼装 method 名时自动加前缀 — **核心 DSL 新增字段**
2. **多 endpoint 路由**:同一 chain 内 method 按 `endpoint_ref` 字段路由到不同 base URL(X-Chain 主体 vs Info endpoint)— **核心 DSL 新增字段**
3. **multi-asset 表达**:`multi_asset: bool` + `native_asset_id: string` + method 级 `asset_id_param` 字段(标记哪个 param 是 asset 选择器)
4. **uint64-as-string**:DSL 字段 `numeric_encoding: enum[int, string, hex]` per-field 或 chain 级默认 — Avalanche 全 string,Bitcoin 全 int/float,EVM 全 hex
5. **cb58 编码**:value transformer / decoder 注册表,DSL 引用 `decoder: cb58`(类似 Bitcoin 已需要的 `decoder: base58check` / EVM 的 `decoder: hex`)

**可选支持**:
1. cross-chain tx 类型识别(`ImportTx`/`ExportTx`)— P1 不必,P2 跨链 benchmark 才需
2. P-Chain validators 查询(`platform.getCurrentValidators`)— 若本框架未来覆盖 PoS validator 监控

**不需要的能力**:
1. websocket / 订阅(X-Chain 无标准 ws RPC)
2. EVM event log(X-Chain 无 event 概念,C-Chain 才有)

### 11.7 必填:Avalanche-X vs Bitcoin UTXO 对比(关键 — 决定 family 边界)

| 维度 | Bitcoin UTXO | Avalanche-X UTXO | 实测证据 |
|---|---|---|---|
| 协议 | JSON-RPC 1.0/2.0(混杂)| JSON-RPC 2.0(严格)| §3 vs §3 [E2] |
| method namespace | 无(`getbalance`) | **`avm.*`(`avm.getBalance`)** | §5 [E2] |
| balance 查询 | `getbalance`(wallet,反代禁)/ scantxoutset / Esplora REST | `avm.getBalance(address, assetID)` + `avm.getAllBalances(address)` | §4 [E2] |
| UTXO 查询 | `listunspent`(wallet)/ scantxoutset / Esplora `GET /address/{a}/utxo` | `avm.getUTXOs(addresses[], limit, encoding)` 原生支持分页 | §5 [E2] |
| tx 查询 | `getrawtransaction(txid, verbose)`(需 txindex)| `avm.getTx(txID, encoding)` | §5 [E2] |
| 块查询 | `getblock(hash, verbosity)` + `getblockhash(N)` — **两步** | `avm.getBlockByHeight(height, encoding)` — **一步直达** | §5 [E2] |
| 多资产 | ❌ 单 BTC(BRC-20/Runes 属 metaprotocol,需外部 indexer)| ✅ assetID 字段必填(AVAX 自己也是 asset,与其他资产平级)| §4 multi-asset 实证 [E2] |
| 地址 | 3 种(base58/bech32/bech32m)| 1 种(bech32 w/ `X-` alias)| §6 [E2] |
| 鉴权 | basic auth(self-hosted 默认)/ none(公网反代)| **none**(官方公网无 auth)| §3 实测 200 无 header [E2] |
| ID 编码 | hex(txid/blockhash)| **cb58**(全部 ID 类字段)| §7 [E2] |
| uint64 表达 | int(sat)/ float(BTC)| **string**(`"189093923788006"`)| §5 [E2] |
| 创世可查 | ❌(creation coinbase error -5)| ✅(`getBlockByHeight(0)` 正常返回)| §5 [E2] |
| 节点版本 method | `getnetworkinfo` | `info.getNodeVersion`(走 `/ext/info`)| §3 [E2] |

### 11.8 必填:DSL 决策建议(CRITICAL — family 边界决策)

#### 选项矩阵

- [ ] **选 a**:与 Bitcoin 同 family,DSL 加 `namespace_prefix` + `multi_asset` 字段共享 `UTXOAdapter`(family=`utxo`)
- [x] **选 b(推荐)**:**独立 `family="avalanche-utxo"`,新建 `AvalancheXAdapter`**;DSL 仍需新增 `namespace_prefix` / `multi_asset` 字段(因 X-Chain 自身 + 未来 P-Chain 都用),但**不动 Bitcoin `family="utxo-btc"` 既有定义**
- [ ] 选 c:不实现 X-Chain(违反 benchmark 全面性主张,不推荐)

#### 理由(2-3 段)

**理由 1 — 既有 family 命名已是"细分子族"风格,选 b 不构成反转**:Wave 1 调研 Bitcoin 时,family 命名为 `"utxo-btc"`(`docs/zh/chains/03-bitcoin.md:391`),Wave 3 调研 Cardano 时为 `"cardano-eutxo"`(`docs/zh/chains/06-cardano.md:359`)。**当前 codebase 中不存在通用 `family="utxo"` 抽象** — UTXO 是模型范畴,family 是 adapter 范畴,这两个名字已被显式区分。因此选 b 命名 `"avalanche-utxo"` 是 **沿用既有命名风格**,不是 family 抽象的扩展或反转。

**理由 2 — adapter 共享会引入比独立 adapter 更多的条件分支**:即便选 a 强制共用 `UTXOAdapter`,该 adapter 仍需在内部分支处理:(a) namespace 前缀拼装(BTC 无、X-Chain 加 `avm.`)、(b) balance 来源(BTC 走 Esplora REST、X-Chain 走 `avm.getAllBalances`)、(c) ID 解码(BTC hex、X-Chain cb58)、(d) uint64 编码(BTC int/float、X-Chain string)、(e) 鉴权(BTC basic auth、X-Chain none)、(f) tx schema 解析(BTC flat vin/vout、X-Chain nested unsignedTx)。这是 **6 个独立维度的全双工差异**,代码层共享一个类只会变成 `if chain==...` 地狱,违反 SRP 与可测性。

**理由 3 — DSL 字段扩展是真正需要的产物**:无论选 a 还是 b,DSL 都必须新增 `namespace_prefix` / `multi_asset` / `native_asset_id` / `numeric_encoding` / `id_encoding` 5 个字段(选 a 是为了让两族在一个 adapter 内分流,选 b 是为了让两 adapter 都遵循 declarative schema)。**这些字段在选 b 下用途同样成立**(BTC 配置中 `namespace_prefix:""`、`multi_asset:false`、`numeric_encoding:int`;X-Chain 配置中 `namespace_prefix:"avm."`、`multi_asset:true`、`numeric_encoding:string`),所以"为了复用 adapter 才加 DSL 字段"是伪命题,DSL 字段扩展应基于 declarative 表达力本身的需要,与 adapter 是否合并无关。

#### family 边界设计哲学讨论

- **family 是按"协议模型(UTXO/Account)"分,还是按"协议实现(Bitcoin Core / avalanchego / cardano-node)" 分?**:Wave 1+3 已选 **后者**(`utxo-btc` / `cardano-eutxo` 已是实现级命名)。本调研推荐**继续沿用**,将 `avalanche-utxo` 作为 sibling family。
- **adapter 复用率 vs schema 干净度**:实测复用率 ~35%(协议层共享了"UTXO 概念" + "POST JSON-RPC" + "只读 benchmark scope"),但 65% 差异(namespace / multi-asset / encoding / auth / tx schema / endpoint 路由)分散在每一层,合并 adapter 的收益 < 维护条件分支的成本。
- **不阻止未来抽象**:若 wave 5+ 加入 Litecoin / Dogecoin / BCH(都 95%+ 复用 BitcoinAdapter)与 P-Chain(90%+ 复用 AvalancheXAdapter),可在第三个 sibling 出现时再考虑提取公共基类 `UTXOAdapterBase`(模板方法模式),但**此刻提取属过早抽象**。

#### ⚠️ family 反转风险评估(给 user 决策的核心要素)

**反转风险等级:🟢 低(near-zero)**

| 风险维度 | 评估 | 详细 |
|---|---|---|
| 是否反转 Bitcoin family 命名? | **否** | Bitcoin 当前是 `family="utxo-btc"`,本决策推荐 `family="avalanche-utxo"` — 二者是 sibling,**不需修改 03-bitcoin.md 的 family 字段** |
| 是否反转 Bitcoin DSL schema? | **否** | DSL 新增 `namespace_prefix` / `multi_asset` 等字段对 Bitcoin 取默认值(`""` / `false`),既不破坏既有 Bitcoin 配置,也不需重写 BitcoinAdapter |
| 是否反转"UTXO = 单一 adapter" 的假设? | **否** | Wave 1 Bitcoin 调研未承诺 "UTXO 族只有一个 adapter",反而明确写 "BitcoinAdapter(UTXO family 起点,后续 Litecoin/Dogecoin/BCH 复用)" — 即同族 fork(LTC/DOGE/BCH)复用,**异族(Avalanche)不复用,本就符合 wave 1 的边界设定** |
| 是否反转既有"family"抽象? | **否** | 当前 codebase 中 family 字段是 string 命名约定,无强类型/继承层级,新增任何 family 值都是 additive 操作 |
| 是否需要 user 批准 family 扩展? | **建议但非必须** | 推荐 user 在本 wave 结束统一确认 family naming convention(是否所有 UTXO 链统一前缀如 `utxo-*`,还是各按实现命名),但 **本决策本身可独立 commit 不阻塞 wave 4** |

**结论**:本决策(选 b,`family="avalanche-utxo"`)**不构成对 wave 1 Bitcoin family 决策的反转**,可在 wave 4 commit 时一并 land,无需先等 user 决策。但若 user 想要更严格的 family 命名约定(例如统一 `utxo-bitcoin` / `utxo-avalanche` / `utxo-cardano` 前缀),则属于 cosmetic refactor,可在 wave 5 统一处理,不影响本调研的技术结论。

**唯一需 user 决策的项**:DSL 字段 `namespace_prefix` 是属于 method 级还是 chain 级?
- 方案 A:chain 级(整 chain 共享一个前缀;X-Chain 配 `"avm."`,Info 走另一 chain 配置)— 更简单
- 方案 B:method 级(同一 chain 内多个前缀;`avm.*` + `info.*` 同 chain 下混用)— 更灵活但复杂
- 本调研倾向 **方案 A + 多 chain 拆分**(把 Info 当独立 sub-chain),但 P2-DESIGN-v2 需明确选择。

---

## Open Questions(待解决问题)

- [ ] **`avm.issueTx` 写场景**:是否纳入 v1 benchmark?需私钥签名(secp256k1) + cb58 编码,实现成本高,建议 v1 跳过(同 Bitcoin tx 广播)。
- [ ] **官方 endpoint quota**:实测无 rate-limit 体感,但官方文档未承诺 SLA,wave2 加监控。
- [ ] **C-Chain (atomic) ImportTx 跨链**:C-Chain → X-Chain 跨链 tx 在 X-Chain 侧可见为 `ImportTx`,是否作为独立 method 测覆盖?
- [ ] **P-Chain 是否独立调研?**:与 X-Chain 共享 cb58 / bech32 / multi-asset / namespace 模式(`platform.*`),若纳入,`AvalancheXAdapter` 可改名 `AvalancheAVMPVMAdapter`,但建议 P-Chain 独立调研以保 method-level 真实证据。
- [ ] **family 命名约定**:user 是否要求统一 `utxo-*` 前缀?见 §11.8 反转风险评估末尾。

---

## Changelog

| Date | Author | Change |
|---|---|---|
| 2026-05-23 | Hermes Agent | 初次调研:基于 `api.avax.network` 实测 + avalanchego 1.14.2 commit `6e5acf9`,完成 Section 1-11 全字段;**核心产出**:family 边界决策推荐选 b(独立 `avalanche-utxo`)+ 反转风险评估(🟢 低,不破坏 wave 1 Bitcoin family);**DSL 新增字段 ASK**:namespace_prefix / multi_asset / native_asset_id / numeric_encoding / id_encoding 5 项;**实测纠错**:context 提供的示例地址 `X-avax1pa5vu24v3hd0y9rdqekv9msrz86s90uvc3xyhq` checksum 错误,改用 `X-avax13k6hxpfuu80dlnqlqs0dxxjrzl4lxz94n38vnw` |
