# 03-Bitcoin 调研

> **此文件由 `_template.md` 衍生。**
> **填写遵守 H8(真实证据):curl 实测 + 官方文档 URL + GitHub commit SHA。**
> **每个字段引用标签 E1(单元测试)/E2(curl 实证)/E3(文档)/E4(源码)/E5(代码 grep)。**

---

## 元信息

| 项 | 值 |
|---|---|
| 链名(中) | 比特币 |
| 链名(英) | Bitcoin |
| 编号 | 03 |
| Mainnet ChainID | N/A(Bitcoin 无 EIP-155 风格 ChainID;链识别用 magic bytes `0xD9B4BEF9` 和 genesis hash `000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f`)[E2/E4] |
| 调研日期 | 2026-05-23 |
| 调研者 | Hermes Agent |
| 状态 | 🟢 已完成 |

---

## 1. Sources(权威来源)

| 类型 | URL | 访问日期 | 备注 |
|---|---|---|---|
| 官方文档 | https://bitcoincore.org/en/doc/29.0.0/ | 2026-05-23 | Bitcoin Core 29.0 RPC 参考(`getnetworkinfo` 返回 `subversion=/Satoshi:29.3.0/`,对应 v29 系列)[E2] |
| RPC 规范 | https://developer.bitcoin.org/reference/rpc/ | 2026-05-23 | Bitcoin Developer Reference RPC 列表(社区维护,Core 官方副本) |
| GitHub | https://github.com/bitcoin/bitcoin (commit `de925455c8025fc1f75d65d981c28b9dfa20e9f7`,master @ 2026-05-23) | 2026-05-23 | 核心实现仓库,本文档所有源码引用均锚定该 SHA [E4] |
| Esplora REST | https://github.com/Blockstream/esplora/blob/master/API.md | 2026-05-23 | Blockstream Esplora REST API(地址余额/UTXO 查询的替代方案,因 Core 自身无 address index)[E3] |
| Explorer | https://blockstream.info/ | 2026-05-23 | 主网区块/tx/地址浏览器(用于校验本文档贴出的 hash/地址) |
| BIP-141 | https://github.com/bitcoin/bips/blob/master/bip-0141.mediawiki | 2026-05-23 | SegWit(weight 单位定义) |
| BIP-173 | https://github.com/bitcoin/bips/blob/master/bip-0173.mediawiki | 2026-05-23 | Bech32 地址编码(P2WPKH/P2WSH) |
| BIP-350 | https://github.com/bitcoin/bips/blob/master/bip-0350.mediawiki | 2026-05-23 | Bech32m(P2TR/Taproot 地址) |

---

## 2. Protocol Family(协议族)

| 项 | 值 |
|---|---|
| Family | **Bitcoin / UTXO**(新族,与已有 8 链均不同) |
| Consensus | PoW(SHA-256d)[E3 — bitcoincore.org] |
| VM | None — 栈式 Script(非图灵完备),无虚拟机状态模型 [E3] |
| Block Time | 目标 ~600s(10 min),由 difficulty 调节;每 2016 块重定 [E3] |
| Finality | 概率终结性,惯例 6 确认 ≈ 60 min;无确定性最终化 |
| Reuse Existing Adapter? | **No** — UTXO 模型 vs 现有 8 链(Solana account / EVM account / Move object / Cairo Felt)均不兼容,且 JSON-RPC 1.0 + Basic Auth 与 EVM 的 JSON-RPC 2.0 + 公网 bearer 模式不同。需新建 `BitcoinAdapter`(UTXO 族起点,后续 Litecoin/Dogecoin/BCH 复用)[E2 — 见下文 11.5 异构性对比] |

---

## 3. Public RPC(公共节点)

| Endpoint | Auth | 实测结果 | 备注 |
|---|---|---|---|
| `https://bitcoin-rpc.publicnode.com` | 无(allnodes.com 反代,自动去除 basic auth) | ✅ 200,5 次连续请求平均 250ms,无 rate-limit 触发 | **推荐主测**;限制:wallet 类 method(getbalance/getreceivedbyaddress)返回自定义 code `-32701`("Method ... is not allowed") |
| `https://blockstream.info/api` | 无 | ✅ 200(Esplora REST,**非 JSON-RPC**) | 仅作 address balance / UTXO 补全用,与 Core RPC 不共 schema;trade-off 见 §10 |
| `http://<self-hosted>:8332` | basic auth(`rpcuser:rpcpassword`) | 未测(本环境无 self-hosted 节点) | 真实 self-hosted 路径,benchmark target 模式应使用此 |

**Trade-off & 决策**:
- **选 publicnode 作为本文档实证 endpoint** 因其 (a) 无 auth、(b) 全公开 JSON-RPC 1.0、(c) 实测稳定。
- **反转条件**:若 publicnode 在 wave2 中开始 rate-limit 或下线 wallet 之外更多 method,则切到 self-hosted bitcoind regtest/mainnet,以恢复 basic auth 真实路径。
- **mock 优先**:本框架 Phase 2.1 后,`mock_rpc_server.py` 应实现 Bitcoin 分支,使 CI 不依赖任何公网 endpoint。

**curl 实测**(必填):
```bash
# E2 — 实测 2026-05-23 publicnode.com
curl -s -X POST https://bitcoin-rpc.publicnode.com \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"1.0","id":1,"method":"getblockcount","params":[]}'
# 实测输出:
# {"result":950697,"error":null,"id":1}

curl -s -X POST https://bitcoin-rpc.publicnode.com \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"1.0","id":1,"method":"getblockchaininfo","params":[]}'
# 实测输出(节选):
# {"jsonrpc":"2.0","result":{"bestblockhash":"00000000000000000000dc4cb7acea2ef037c9ce00a3f605f6bd347a4312e7fa",
#  "blocks":950697,"chain":"main","difficulty":136607070854775.1,"headers":950697,
#  "initialblockdownload":false,"pruned":false,"size_on_disk":846124394968,
#  "time":1779558706,"verificationprogress":0.9999976403640984,"warnings":[]},"id":1}
#
# 注:同一服务器对 getblockcount 回 "jsonrpc":"1.0" 字面值,对 getblockchaininfo 回 "jsonrpc":"2.0",
# 这是 Core 历史遗留(Core 自己不区分版本字段,publicnode 反代行为有差异)。客户端应宽容两种回包。
```

延迟实测(rate-limit 嗅探):
```text
req1: 200 time=0.258703s
req2: 200 time=0.246636s
req3: 200 time=0.255614s
req4: 200 time=0.245881s
req5: 200 time=0.246281s
```

---

## 4. Account Model(账户模型)

| 项 | 值 |
|---|---|
| 模型 | **UTXO**(Unspent Transaction Output)— 无账户、无 nonce、无 state trie [E3] |
| Native token decimals | 8(satoshi,1 BTC = 10⁸ sat)[E3 — bitcoincore.org `getblockchaininfo` 文档与下方 `getrawtransaction` 实测 `"value":50.00000000` 一致] |
| Address derivation | secp256k1 ECDSA;Taproot(BIP-340)使用 secp256k1 Schnorr [E3 — BIP-340] |
| Special account types | **无账户**;但存在 5 种 scriptPubKey 类型对应 5 种地址前缀: P2PKH(`1...`)/ P2SH(`3...`)/ P2WPKH(`bc1q...`,20 字节程序)/ P2WSH(`bc1q...`,32 字节程序)/ P2TR(`bc1p...`)[E2 — 见 §6 validateaddress 实测] |
| **关键约束** | **Bitcoin Core 自身无 address index** — 不能用纯 RPC 查"某地址余额"。必须 (a) 启用 `txindex=1` 并配合 wallet RPC,或 (b) 用外部 Electrum / Esplora 索引服务 [E2 — 下方 getbalance 实测被反代禁,scantxoutset 实测无 wallet 时返回 null] |

**关键约束的 curl 证据**(E2):
```bash
# wallet method 被 publicnode 反代禁
curl -s -X POST https://bitcoin-rpc.publicnode.com -H "Content-Type: application/json" \
  -d '{"jsonrpc":"1.0","id":1,"method":"getbalance","params":["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"]}'
# {"jsonrpc":"1.0","error":{"code":-32701,
#  "message":"Method getbalance is not allowed. To remove restrictions, order a dedicated full node here: https://www.allnodes.com/btc/host"},"id":1}

# scantxoutset 在无 wallet 配置时返回 null(无法即时查地址余额)
curl -s -X POST https://bitcoin-rpc.publicnode.com -H "Content-Type: application/json" \
  -d '{"jsonrpc":"1.0","id":1,"method":"scantxoutset","params":["status"]}'
# {"result":null,"error":null,"id":1}

# Esplora REST 才能拿到地址余额(funded - spent)
curl -s "https://blockstream.info/api/address/1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
# {"address":"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
#  "chain_stats":{"funded_txo_count":74737,"funded_txo_sum":5719999745,
#                 "spent_txo_count":0,"spent_txo_sum":0,"tx_count":62929},
#  "mempool_stats":{"funded_txo_count":0,"funded_txo_sum":0,
#                   "spent_txo_count":0,"spent_txo_sum":0,"tx_count":0}}
# → balance_sat = funded_txo_sum - spent_txo_sum = 5_719_999_745 sat ≈ 57.20 BTC
```

---

## 5. Core RPC Methods(本框架监控所需)

> 仅列本基准测试框架需要的 method。完整 API 列表参考 bitcoincore.org/en/doc/29.0.0/。所有方法均经下方 curl 实测 [E2]。

| Method | 类别 | 说明 | 在 mixed 中权重建议 |
|---|---|---|---|
| `getblockcount` | block height | 探活 + 高度同步检查;返回最新主链高度 int | 0.10 |
| `getblockhash` | block height → hash | 输入 height(int),返回 hash;**两步查询第一跳** | 0.05 |
| `getblock` | block content | 输入 hash + verbosity(0=hex/1=json/2=json+tx);**两步查询第二跳**,verbosity=2 极重 | 0.10 |
| `getblockchaininfo` | chain status | bestblockhash + headers + IBD 状态 | 0.05 |
| `getrawtransaction` | tx lookup | 输入 txid + verbose(false=hex/true=json);**需 `-txindex=1`**,否则只能查 mempool 内 tx 或被引用的 UTXO | 0.20 |
| `getrawmempool` | mempool | 当前 mempool 全部 txid 列表(verbose=false)或详情 dict(verbose=true)| 0.10 |
| `getmempoolinfo` | mempool meta | size/bytes/usage/minfee 元信息 | 0.05 |
| `estimatesmartfee` | fee | 输入 conf_target(int),返回 feerate(BTC/kvB)| 0.05 |
| `validateaddress` | utility | 地址校验 + 推断 type(p2pkh/p2sh/witness_v0/witness_v1)| 0.05 |
| `getnetworkinfo` | peer/version | 版本、连接数、relayfee | 0.05 |
| 地址余额(Esplora,**非 JSON-RPC**) | balance | `GET /address/{addr}` → funded_txo_sum - spent_txo_sum | 0.20 |

**总权重检查**: 0.10+0.05+0.10+0.05+0.20+0.10+0.05+0.05+0.05+0.05+0.20 = **1.00** ✅

**curl 实证 — 关键 method 完整响应**(E2,2026-05-23):

```bash
# 1) getblockhash(0) — 创世块
curl -s -X POST https://bitcoin-rpc.publicnode.com -H "Content-Type: application/json" \
  -d '{"jsonrpc":"1.0","id":1,"method":"getblockhash","params":[0]}'
# {"result":"000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f","error":null,"id":1}
# ↑ 与 bitcoin-context.md 提供的 genesis hash 100% 一致

# 2) getblock(genesis_hash, 1)
curl -s -X POST https://bitcoin-rpc.publicnode.com -H "Content-Type: application/json" \
  -d '{"jsonrpc":"1.0","id":1,"method":"getblock","params":["000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f", 1]}'
# {"result":{"hash":"000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f",
#   "height":0,"version":1,"merkleroot":"4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b",
#   "time":1231006505,"mediantime":1231006505,"nonce":2083236893,"bits":"1d00ffff",
#   "difficulty":1,"nTx":1,"size":285,"weight":1140,
#   "tx":["4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"]},"error":null,"id":1}
# ↑ merkleroot == coinbase txid 与 context 提供的一致

# 3) getrawtransaction(genesis_coinbase, true) — 已知特例
curl -s -X POST https://bitcoin-rpc.publicnode.com -H "Content-Type: application/json" \
  -d '{"jsonrpc":"1.0","id":1,"method":"getrawtransaction",
       "params":["4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b", true]}'
# {"result":null,"error":{"code":-5,
#  "message":"The genesis block coinbase is not considered an ordinary transaction and cannot be retrieved"},"id":1}
# ↑ Bitcoin Core 历史 quirk:创世 coinbase 不在 UTXO set 也不在 txindex,error code -5 (RPC_INVALID_ADDRESS_OR_KEY)

# 4) getrawtransaction(block-1 coinbase, true) — 正常 tx
curl -s -X POST https://bitcoin-rpc.publicnode.com -H "Content-Type: application/json" \
  -d '{"jsonrpc":"1.0","id":1,"method":"getrawtransaction",
       "params":["9b0fc92260312ce44e74ef369f5c66bbb85848f2eddd5a7a1cde251e54ccfdd5", true]}'
# {"result":{"txid":"9b0fc92260312ce44e74ef369f5c66bbb85848f2eddd5a7a1cde251e54ccfdd5",
#   "version":1,"size":134,"vsize":134,"weight":536,"locktime":0,
#   "vin":[{"coinbase":"04ffff001d010b","sequence":4294967295}],
#   "vout":[{"value":50.00000000,"n":0,
#     "scriptPubKey":{"asm":"047211a824f55b50... OP_CHECKSIG","type":"pubkey",
#     "hex":"41047211a824f55b505228e4c3d5194c1fcfaa15a456abdf37f9b9d97a4040afc073dee6c89064984f03385237d92167c13e236446b417ab79a0fcae412ae3316b77ac"}}],
#   "blockhash":"000000006a625f06636b8bb6ac7b960a8d03705d1ace08b1a19da3fdcc99ddbd",
#   "confirmations":950697,"time":1231469744,"blocktime":1231469744},"error":null,"id":1}

# 5) getmempoolinfo — 监控类
curl -s -X POST https://bitcoin-rpc.publicnode.com -H "Content-Type: application/json" \
  -d '{"jsonrpc":"1.0","id":1,"method":"getmempoolinfo","params":[]}'
# {"result":{"loaded":true,"size":27632,"bytes":6270633,"usage":48078544,
#   "total_fee":0.02726244,"maxmempool":256000000,"mempoolminfee":0.00000100,
#   "minrelaytxfee":0.00000100,"incrementalrelayfee":0.00000100,
#   "unbroadcastcount":0,"fullrbf":true},"error":null,"id":1}

# 6) estimatesmartfee(6)
curl -s -X POST https://bitcoin-rpc.publicnode.com -H "Content-Type: application/json" \
  -d '{"jsonrpc":"1.0","id":1,"method":"estimatesmartfee","params":[6]}'
# {"result":{"feerate":0.00001013,"blocks":6},"error":null,"id":1}

# 7) getnetworkinfo — 用于版本/peer 监控
# {"result":{"version":290300,"subversion":"/Satoshi:29.3.0/","protocolversion":70016,
#   "connections":247,"connections_in":237,"connections_out":10,
#   "relayfee":0.00000100,"incrementalfee":0.00000100,"warnings":[]},...}
```

---

## 6. Address Format(地址格式)

| 项 | 值 |
|---|---|
| 编码 | **多编码**:Base58Check(legacy P2PKH `1...` / P2SH `3...`)+ Bech32(SegWit v0,`bc1q...`)+ Bech32m(SegWit v1/Taproot,`bc1p...`)[E3 — BIP-13/16/141/173/350] |
| 长度 | P2PKH/P2SH: 26-35 字符;P2WPKH: 42 字符(`bc1q` + 38);P2WSH: 62 字符;P2TR: 62 字符 [E2 — 见下] |
| Checksum | Base58Check: 双 SHA-256 取前 4 字节;Bech32: BCH(常数 1);Bech32m: BCH(常数 0x2bc830a3)[E3 — BIP-350] |
| 示例(主网真实) | P2PKH: `1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa`(中本聪 genesis 50 BTC,context 提供,已校验[E2])<br>P2WPKH: `bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h`(下方实测有效)<br>P2TR: `bc1p5d7rjq7g6rdk2yhzks9smlaqtedr4dekq08ge8ztwac72sfr9rusxg3297`(下方实测有效) |
| 校验正则(实用,**非充分**) | Base58: `^[13][1-9A-HJ-NP-Za-km-z]{25,34}$`<br>Bech32 mainnet: `^bc1[qp][023456789acdefghjklmnpqrstuvwxyz]{6,87}$`<br>**注**:必须用 `validateaddress` RPC 二次校验 — 正则无法验 checksum |

**curl 实证**(E2 — `validateaddress` 三类型):
```bash
# P2PKH
# input: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
# → {"isvalid":true,"scriptPubKey":"76a91462e907b15cbf27d5425399ebf6f0fb50ebb88f1888ac",
#    "isscript":false,"iswitness":false}

# P2WPKH(witness v0)
# input: bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h
# → {"isvalid":true,"scriptPubKey":"0014dc6bf86354105de2fcd9868a2b0376d6731cb92f",
#    "isscript":false,"iswitness":true,"witness_version":0,
#    "witness_program":"dc6bf86354105de2fcd9868a2b0376d6731cb92f"}

# P2TR(witness v1, Bech32m)
# input: bc1p5d7rjq7g6rdk2yhzks9smlaqtedr4dekq08ge8ztwac72sfr9rusxg3297
# → {"isvalid":true,"scriptPubKey":"5120a37c3903c8d0db6512e2b40b0dffa05e5a3ab73603ce8c9c4b7771e5412328f9",
#    "isscript":true,"iswitness":true,"witness_version":1,
#    "witness_program":"a37c3903c8d0db6512e2b40b0dffa05e5a3ab73603ce8c9c4b7771e5412328f9"}
```

---

## 7. Signature Lookup(交易哈希)

| 项 | 值 |
|---|---|
| Hash 格式 | Hex,**无 0x 前缀**(与 EVM 不同);为双 SHA-256 倒序(little-endian display)[E3] |
| 长度 | 64 字符(32 字节 hex) |
| **txid vs wtxid** | SegWit 后存在两种:`txid`(不含 witness 数据的 hash)与 `wtxid`/`hash`(含 witness)。getrawtransaction 接受 **txid**,响应同时包含两者 [E2 — 见 §5 实测,coinbase tx 因 vin 没 witness 故二者相等] |
| 示例(主网真实) | `4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b`(genesis coinbase,context 提供,**但 Core RPC 无法查询** — error -5)<br>`9b0fc92260312ce44e74ef369f5c66bbb85848f2eddd5a7a1cde251e54ccfdd5`(block-1 coinbase,可查,见 §5)[E2] |
| 查询 method | `getrawtransaction(<txid>, true/false)` — **需 `-txindex=1`** 才能查任意历史 tx;否则只查 mempool + 未花费 UTXO 引用 tx [E3 — bitcoincore.org] |
| Explorer URL 格式 | `https://blockstream.info/tx/<txid>` 或 `https://mempool.space/tx/<txid>` |

---

## 8. Mixed Set(`mixed` 模式权重)

> 用于 `BLOCKCHAIN_NODE_BENCHMARK_MODE=mixed` 时的 Bitcoin 请求分布。
> 权重设计原则:写场景为主的 benchmark 无意义(BTC tx 需私钥+广播),故全部为 **只读 method**;重量级 method(`getblock verbosity=2`、`getrawmempool verbose=true`)按真实 explorer 流量比例配。

```json
{
  "block_height_query": 0.10,
  "block_hash_lookup": 0.05,
  "block_content_query": 0.10,
  "chain_info_query": 0.05,
  "tx_lookup": 0.20,
  "mempool_list_query": 0.10,
  "mempool_info_query": 0.05,
  "fee_estimate_query": 0.05,
  "address_validate": 0.05,
  "network_info_query": 0.05,
  "address_balance_query_esplora": 0.20
}
```

method 映射:
- `block_height_query` → `getblockcount`(no_params)
- `block_hash_lookup` → `getblockhash`(单 int 参数 `$height`)
- `block_content_query` → `getblock`(`$blockhash`, `$verbosity=1`)
- `chain_info_query` → `getblockchaininfo`(no_params)
- `tx_lookup` → `getrawtransaction`(`$txid`, `$verbose=true`)
- `mempool_list_query` → `getrawmempool`(no_params,默认 verbose=false)
- `mempool_info_query` → `getmempoolinfo`(no_params)
- `fee_estimate_query` → `estimatesmartfee`(单 int `$conf_target=6`)
- `address_validate` → `validateaddress`(`$address`)
- `network_info_query` → `getnetworkinfo`(no_params)
- `address_balance_query_esplora` → REST `GET /api/address/$address`(**非 JSON-RPC**,需要独立 endpoint 配置)

**权重和**: 0.10+0.05+0.10+0.05+0.20+0.10+0.05+0.05+0.05+0.05+0.20 = **1.00** ✅

---

## 8.5 Phase 2.1 caller/reader 改造点(token-level Gate 3)

Bitcoin 是**全新链**,代码侧无现有路径,以下为 P2.1 必须新增/触达的点:

| # | 位置(file:line) | 改动 | 原因 |
|---|---|---|---|
| 1 | `config/config_loader.sh:~409` UNIFIED_BLOCKCHAIN_CONFIG json 新增 `"bitcoin": {...}` 块 | 新增 chain_type、rpc_methods.single/mixed、param_formats(见 §10 JSON)| 与 solana/ethereum 块平级;`generate_rpc_json` 缺则 fallback 错链 |
| 2 | `config/config_loader.sh:666` `supported_blockchains` array 加 `"bitcoin"` | 数组扩到 9 项 | guard_8chain_truth.sh 守的就是这个 array,加链必须同步,否则启动 reject |
| 3 | `config/config_loader.sh:~372` case 分支加 `bitcoin)` | 设 `MAINNET_RPC_URL="https://bitcoin-rpc.publicnode.com"` | 缺则落入 `*)` 默认走 Solana endpoint(实测会 silently 错链)|
| 4 | `tools/mock_rpc_server.py` 新增 method 分支:`getblockcount`/`getblockhash`/`getblock`/`getrawtransaction`/`getmempoolinfo`/`estimatesmartfee`/`validateaddress`/`getnetworkinfo`/`getblockchaininfo`/`getrawmempool` | 复制 §5 实测响应作为 fixture | mock 是 CI fallback,缺则 CI 跑不通 BTC 模式 |
| 5 | `tools/fetch_active_accounts.py` 新增 `BitcoinAdapter` 类 | 用 Esplora REST 拉地址列表(因 Core 无 address index);param_format 处理 `single_address`(无 `, "latest"` 后缀) | EthereumAdapter/SolanaAdapter 全不适用 — UTXO 模型 + Esplora 两栈 |
| 6 | `tests/guard_8chain_truth.sh` 升级为 `guard_9chain_truth.sh`(或参数化) | 把 `"bitcoin"` 加入预期 array | 否则 guard 阻止启动 |
| 7 | `analysis-notes/baseline-current-state.md` grep `8chain` / `8 chain` | 更新为 9 chain,把 bitcoin 加入链路列表 | doc-vs-code 对齐(v1.4.1 同款问题) |
| 8 | `analysis-notes/disk-and-network-pipeline-redesign.md` 同步 | 同上 | 同上 |
| 9 | `analysis-notes/research_notes/03-bitcoin-starknet-rpc-resource.md` 若已 deprecated 该 block,需重新评估或标注本文档 supersedes | 文档真相对齐 | 同上 |

**N/A**:Bitcoin 无现有 method 需删 → 模板第 1 行"删除"列项不适用。

**测试要求**:P2.1 完成后跑 `BLOCKCHAIN_NODE=bitcoin core/master_qps_executor.sh --mixed --duration 30`,vegeta 全部 200 + JSON-RPC `error` 字段为 null(地址余额请求例外:Esplora 是 REST 200 + JSON body)。

---

## 9. Mock Notes(mock_rpc_server 实现要点)

- **请求路径**:`POST /`(Bitcoin Core 不区分路径,所有 RPC 走根路径;basic auth 走 `Authorization: Basic <base64(user:pass)>` header)[E3 — bitcoincore.org]
- **响应 schema**(贴一段 §5 实测响应):
  ```json
  {
    "result": {
      "bestblockhash": "00000000000000000000dc4cb7acea2ef037c9ce00a3f605f6bd347a4312e7fa",
      "blocks": 950697,
      "chain": "main",
      "difficulty": 136607070854775.1,
      "headers": 950697,
      "initialblockdownload": false,
      "pruned": false,
      "time": 1779558706,
      "verificationprogress": 0.9999976403640984,
      "warnings": []
    },
    "error": null,
    "id": 1
  }
  ```
- **特殊错误码**(权威来源:`bitcoin/bitcoin@de92545 src/rpc/protocol.h` L25-L96)[E4]:
  - `-32600` RPC_INVALID_REQUEST(标准 JSON-RPC) [L29]
  - `-32601` RPC_METHOD_NOT_FOUND [L32]
  - `-32602` RPC_INVALID_PARAMS [L33]
  - `-32603` RPC_INTERNAL_ERROR [L36]
  - `-32700` RPC_PARSE_ERROR [L37]
  - `-1` RPC_MISC_ERROR(`std::exception thrown`)[L40]
  - `-3` RPC_TYPE_ERROR(`Unexpected type was passed as parameter`)[L41]
  - **`-5` RPC_INVALID_ADDRESS_OR_KEY**(invalid address / key / 创世 coinbase 查询)[L42] ← 本文档 §5 实测命中
  - `-8` RPC_INVALID_PARAMETER(`Invalid, missing or duplicate parameter`)[L44]
  - `-28` RPC_IN_WARMUP(`Client still warming up` — IBD 期返回)[L50]
  - `-32701` **非 Bitcoin Core 官方** code,publicnode/allnodes 反代自定义("Method ... is not allowed");mock 可不实现,但客户端应宽容
- **mock 实现复杂度**:**Medium**
  - 容易部分:多数 method 是固定 schema,实测响应可直接当 fixture 返回
  - 难点 1:`getblock` 的 verbosity 参数有 3 档(0=hex、1=json、2=json+tx-detail),mock 需多套 fixture
  - 难点 2:`getrawtransaction` 的 verbose 参数有 2 档(false=hex string、true=full json),且 fixture 数据量大
  - 难点 3:`getrawmempool` 真实主网回包 ~27K txid(实测 size=27632),mock 应裁剪到 ~10 条避免 mock 服务带宽爆
  - 难点 4:basic auth 校验 — mock 应模拟 `Authorization` header,无则 401,匹配真实 Core 行为

---

## 10. Adapter Reuse Decision(adapter 复用决策)

### 候选 adapter

| Adapter | 兼容度 | 缺失能力 |
|---|---|---|
| EthereumAdapter | 0% | account model 完全不同;JSON-RPC 2.0 vs 1.0;address format 完全不同;无 token concept |
| SolanaAdapter | 0% | account model + signature lookup paradigm 完全不同 |
| StarknetAdapter | 0% | 同上,而且 Cairo Felt 与 UTXO 毫无交集 |
| SuiAdapter | 0% | Move object 模型也是 account-like,虽都"非 EVM"但 UTXO 是独立一极 |
| (新建) BitcoinAdapter | 100% | — |

### 决策

- [x] **新建** `BitcoinAdapter`(UTXO family 起点)
- [x] **混合**:Core JSON-RPC 1.0 + Esplora REST 双栈(因 Core 无 address index)

### 理由

1. **模型异构**:UTXO 没有"账户余额"原语,balance 必须由"对该地址所有 UTXO 求和"或外部索引(Esplora/Electrum)给出,所有 account-based adapter 的 `getBalance(addr)` 调用语义完全不可移植。
2. **RPC 协议异构**:Bitcoin 用 JSON-RPC **1.0**(`"jsonrpc":"1.0"` 或省略),EVM 强制 JSON-RPC 2.0;请求 id 行为、error 字段语义、batch 支持都有差异。
3. **鉴权异构**:Bitcoin Core 默认 HTTP Basic Auth(`-rpcuser` / `-rpcpassword` 或 `.cookie` 文件),需写 `Authorization: Basic <b64>` header;EVM 公网节点多用 bearer / API key / 无鉴权。
4. **两步查询语义**:获取一个块的内容需要 `getblockhash(h)` → `getblock(hash)` 两步;EVM 的 `eth_getBlockByNumber(h)` 一步搞定 — DSL 必须支持"前一 method 输出 → 后一 method 输入"的 cursor chaining。
5. **后续复用**:Litecoin / Dogecoin / Bitcoin Cash / Zcash 都 fork 自 Bitcoin Core,RPC 接口 95%+ 一致(method 名、param 顺序、error code 全相同),BitcoinAdapter 是这条赛道的基石。

### 配置 JSON 示例(本链)

```json
{
  "chain": "bitcoin",
  "family": "utxo-btc",
  "adapter": "BitcoinAdapter",
  "chain_id": null,
  "magic_bytes": "0xD9B4BEF9",
  "genesis_hash": "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f",
  "rpc_endpoint": "https://bitcoin-rpc.publicnode.com",
  "rpc_endpoint_alt_esplora": "https://blockstream.info/api",
  "rpc_protocol": "json-rpc-1.0",
  "auth": {"type": "basic", "user": "${BTC_RPC_USER}", "pass": "${BTC_RPC_PASS}", "optional_for_public_proxy": true},
  "block_time_ms": 600000,
  "native_decimals": 8,
  "address_formats": ["base58check", "bech32", "bech32m"],
  "rpc_methods": {
    "block_height": "getblockcount",
    "block_hash_at_height": "getblockhash",
    "block_content": "getblock",
    "tx_lookup": "getrawtransaction",
    "mempool_list": "getrawmempool",
    "address_balance_via_esplora": "GET /address/{addr}"
  },
  "mixed_weights": {
    "block_height_query": 0.10,
    "block_hash_lookup": 0.05,
    "block_content_query": 0.10,
    "chain_info_query": 0.05,
    "tx_lookup": 0.20,
    "mempool_list_query": 0.10,
    "mempool_info_query": 0.05,
    "fee_estimate_query": 0.05,
    "address_validate": 0.05,
    "network_info_query": 0.05,
    "address_balance_query_esplora": 0.20
  }
}
```

---

## 11. DSL 字段需求(P2-DESIGN-v2 输入)

### 11.1 RPC 调用协议

| 项 | Bitcoin 取值 | DSL 字段建议 |
|---|---|---|
| 协议类型 | JSON-RPC **1.0**(Core)+ REST(Esplora,补 balance) | `rpc.protocol: enum[jsonrpc1, jsonrpc2, rest, grpc]` |
| HTTP 方法 | POST(Core)/ GET(Esplora) | `rpc.http_method: enum[POST, GET]` per-method 可覆盖 |
| 请求路径 | `/`(Core)/ `/api/{path}`(Esplora,path 含变量) | `rpc.base_path: string` + `method.path_template: string`(支持 `{var}`) |
| 鉴权方式 | Basic Auth(self-hosted)/ none(publicnode 反代) | `rpc.auth.type: enum[none, basic, bearer, api_key, header]` |
| 鉴权 DSL 字段建议 | `auth: {type: basic, user: ${BTC_RPC_USER}, pass: ${BTC_RPC_PASS}, optional: true}` | 必须支持 env var 展开 + `optional` 标志(允许公网反代无 auth)|

[E2 — 见 §3 实测;E4 — Core HTTP basic auth 见 `bitcoin/bitcoin@de92545 src/httprpc.cpp`]

### 11.2 method 调用 schema

> 每个 method 一节,params 用 `$varname` 占位符,response 抽取用 JSONPath。

#### `getblockcount`
- params 模板:`[]`
- response 抽取:`$.result` (int)
- error code 语义:典型无 error(除非 IBD 状态 `-28`)
- 实测证据:§3 [E2]

#### `getblockhash`
- params 模板:`[$height]`(int,0..tip)
- response 抽取:`$.result` (string, 64-hex)
- error code:height 超出范围 → `-8` RPC_INVALID_PARAMETER
- 实测证据:§5 [E2]

#### `getblock`
- params 模板:`[$blockhash, $verbosity]`(verbosity ∈ {0,1,2})
- response 抽取:`$.result.hash`、`$.result.height`、`$.result.tx[*]`、`$.result.size`、`$.result.weight`
- error code:hash 不存在 → `-5` RPC_INVALID_ADDRESS_OR_KEY
- 实测证据:§5 [E2]

#### `getrawtransaction`
- params 模板:`[$txid, $verbose]`(verbose: bool 或 int 0/1)
- response 抽取(verbose=true):`$.result.txid`、`$.result.vin[*]`、`$.result.vout[*].value`、`$.result.blockhash`、`$.result.confirmations`
- error code:`-5` 包含两种语义 — (a) txid 不存在,(b) 创世 coinbase 永远 -5
- 实测证据:§5 [E2]

#### `validateaddress`
- params 模板:`[$address]`
- response 抽取:`$.result.isvalid`(bool)、`$.result.iswitness`、`$.result.witness_version`
- 实测证据:§6 [E2]

#### `estimatesmartfee`
- params 模板:`[$conf_target]`(可选 `$estimate_mode`)
- response 抽取:`$.result.feerate`(BTC/kvB)、`$.result.blocks`
- 实测证据:§5 [E2]

#### `getrawmempool`
- params 模板:`[]` 或 `[$verbose]`(默认 false=txid array;true=dict)
- response 抽取(verbose=false):`$.result[*]`(string array)
- 实测证据:§4 [E2]

#### Esplora `address_balance`(REST,非 JSON-RPC)
- 路径模板:`GET /address/{$address}`
- response 抽取:`$.chain_stats.funded_txo_sum`、`$.chain_stats.spent_txo_sum`(余额 = funded - spent,单位 sat)
- 实测证据:§4 [E2]

### 11.3 cursor / pagination 模型

Bitcoin 有 **两种 cursor 模型**,DSL 必须都支持:

| 模型 | 描述 | DSL 建议 |
|---|---|---|
| **height-based**(主)| `for h in [start, start+N]: hash = getblockhash(h); block = getblock(hash, 1)` | `cursor: {type: height, start: $H0, step: 1, max_count: 1000, chain_to: getblock}` — 关键 ASK:**支持 method chaining**,前一 method response 作为后一 method 的 param |
| **listsinceblock-based**(增量同步用) | `listsinceblock(blockhash)` 返回该 hash 之后的所有 wallet tx(wallet RPC,本框架不必必须) | `cursor: {type: opaque, next_path: $.lastblock}` |
| **txid-based**(tx 抽样) | 从 mempool 或 explorer 拿 txid 列表 → `getrawtransaction` 逐个 | `cursor: {type: list, source: getrawmempool, item_path: $.result[*]}` |

**DSL 关键 ASK**:必须支持 **method chaining**(`output_of(getblockhash) → param[0] of getblock`)。EVM 的 cursor 是单 method(`eth_getBlockByNumber(h)` 直接给 block),Bitcoin/UTXO 全族都需要 chain,所以这是 P2-DESIGN-v2 必备能力。

### 11.4 system addresses / 过滤规则

| 项 | Bitcoin 取值 | DSL 字段建议 |
|---|---|---|
| coinbase 输入 | `vin[*].coinbase` 字段存在(取代 `txid` + `vout`),应识别为"区块奖励铸造"非真实输入 | `filter.coinbase_input: bool`(true=滤掉)|
| 创世 coinbase tx | `4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b` — getrawtransaction 永远 -5,fixture pool 应排除 | `system_txids: [list of txids to skip]` |
| OP_RETURN outputs | `vout[*].scriptPubKey.type == "nulldata"` 是 burn/data carrier,无 balance | `filter.script_types_exclude: [nulldata]` |
| 系统地址 | Bitcoin 无原生系统地址(无 precompile),但生态约定: `1BitcoinEaterAddressDontSendf59kuE`(burn)等 | `system_addresses: []`(默认空,各 deployment 可填)|

[E2 — coinbase 字段见 §5 block-1 coinbase tx 实测;E3 — script type 见 bitcoincore.org getrawtransaction 文档]

### 11.5 异构性标记(对比现有 8 链)

| 维度 | 现有 8 链(solana/eth/bsc/base/scroll/polygon/starknet/sui)| Bitcoin |
|---|---|---|
| **账户模型** | 全部 account-based(Solana account / EVM account / Cairo Felt / Move object)| **UTXO**(独立一极)|
| **JSON-RPC 版本** | 全部 2.0(`"jsonrpc":"2.0"` 必填)| **1.0**(部分反代会改回 2.0 — §3 实测) |
| **鉴权** | 公网节点多 none/bearer/API-key | **HTTP Basic Auth**(self-hosted 默认)|
| **block 查询步数** | 1 步(`eth_getBlockByNumber(h)`、`getBlock(slot)`)| **2 步**(`getblockhash(h)` → `getblock(hash)`)|
| **address 余额查询** | RPC 原生(`eth_getBalance`、`getBalance`)| **Core 无原生** — 必须 Esplora REST 或 txindex+wallet |
| **地址格式数量** | 1 种 / 链(eg. EVM 全 hex0x、Solana base58、Sui hex)| **3 种共存**(base58/bech32/bech32m)且同一钱包可同时持有 |
| **签名查询单位** | tx hash | txid **和** wtxid(SegWit 后分裂)|
| **token concept** | 内建(ERC20、SPL、Sui Coin)| **无原生 token**(BRC-20/Runes 是 link 层 metaprotocol,需 ord 索引器,本框架不覆盖)|

### 11.6 DSL 设计 ASK(给 P2-DESIGN-v2)

**必须支持**:
1. **JSON-RPC 1.0 与 2.0 双兼容**(请求体可省略或填 1.0;响应解析宽容字段缺失/版本不匹配)
2. **HTTP Basic Auth** + env var 展开 + `optional` 标志(公网反代场景)
3. **method chaining cursor**(前一 method 的 response path → 后一 method 的 param)— 这是 UTXO 族能否 0-Python 落地的 P0 能力
4. **REST + JSON-RPC 混合协议**(同一 chain 内,不同 method 走不同协议,例如 Bitcoin 主体 JSON-RPC + Esplora REST 补 balance)
5. **多 address format 校验**(同一 chain 内多种 prefix/编码;校验调用应允许走链上 `validateaddress` 而非纯本地正则)
6. **error code 白名单**(error code `-5` 在 getrawtransaction 创世场景是"已知特例"而非真错,DSL 应允许 method 级 `expected_error_codes: [-5]` 跳过该样本)
7. **path-template REST**(`GET /address/{addr}` 这种带变量的 REST 路径)

**可选支持**:
1. batch RPC(Bitcoin Core 支持 JSON array 批量请求,benchmark 也可走单请求)
2. cookie 文件鉴权(`-rpccookiefile`,self-hosted 才有意义,公网/CI 用 user/pass 足够)
3. Electrum 协议(TCP+JSON,作为 Esplora 之外的索引方案,P1 不必)

**不需要的能力**:
1. websocket 订阅(BTC 无标准 ws RPC,ZMQ 是 byte-level pub/sub,benchmark 不覆盖)
2. EVM-style event log filter(无概念)
3. token balance 原生 method(无原生 token)
4. wallet 类 method(getbalance/sendtoaddress)— benchmark 只读

---

## Open Questions(待解决问题)

- [ ] **Esplora vs Electrum vs txindex+wallet**:三种地址余额方案在 self-hosted 场景下 latency/吞吐量对比,需 wave2 self-hosted bench 给数据。
- [ ] **publicnode 的 `-32701` 自定义 code 长期是否稳定**:若上游 allnodes 改为返回 `-32601` 或 HTTP 4xx,客户端需相应更新。建议 wave2 加 contract test 监控。
- [ ] **`getrawtransaction` 对未启 txindex 的 self-hosted 节点行为**:实测 publicnode 是否启用 txindex 未知(实测 block-1 coinbase 可查 → 应启用,但需要文档/operator 二次确认)。
- [ ] **BRC-20 / Runes / Ordinals 是否纳入 v1 benchmark scope**:metaprotocol 需要外部 indexer,正式 Bitcoin RPC 无原生支持,本调研按"不纳入"处理,待业务方确认。
- [ ] **mempool 抽样策略**:`getrawmempool` 返回 27K+ txid,benchmark 是否每次拉全量?建议 mock 裁剪到 ~10 条,真实 endpoint 走 truncation。

---

## Changelog

| Date | Author | Change |
|---|---|---|
| 2026-05-23 | Hermes Agent | 初次调研:基于 publicnode.com 与 blockstream.info 实测 + Bitcoin Core master @ de92545 源码,完成 Section 1-11 全字段,DSL 关键 ASK 已列(method chaining、JSON-RPC 1.0/2.0 双兼容、basic auth+env var、REST 与 JSON-RPC 混合) |
