# 07-polkadot 调研

> 由 `_template.md` 衍生。H8(真实证据):所有 RPC 调用均在 2026-05-23 对 `https://rpc.polkadot.io` 与 `https://polkadot-public-sidecar.parity-chains.parity.io` 实测。

---

## 元信息

| 项 | 值 |
|---|---|
| 链名(中) | 波卡 |
| 链名(英) | Polkadot |
| 编号 | 07 |
| Mainnet ChainID | SS58 prefix = **0**;Genesis hash = `0x91b171bb158e2d3848fa23a9f1c25182fb8e20313b2c1eb49219da7a70ce90c3`(E1 实测) |
| 调研日期 | 2026-05-23 |
| 调研者 | Hermes Agent |
| 状态 | 🟢 已完成 |

---

## 1. Sources(权威来源)

| 类型 | URL | 访问日期 | 备注 |
|---|---|---|---|
| 官方文档 | https://wiki.polkadot.network/ | 2026-05-23 | Polkadot 协议主页 |
| RPC 规范 | https://polkadot.js.org/docs/substrate/rpc/ | 2026-05-23 | Substrate JSON-RPC method 命名空间(state_/chain_/system_/author_/payment_/account_/...) |
| Sidecar | https://github.com/paritytech/substrate-api-sidecar | 2026-05-23 | Parity 官方 REST 包装,屏蔽 SCALE 编码 |
| GitHub(节点) | https://github.com/paritytech/polkadot-sdk | 2026-05-23 | polkadot-sdk(原 polkadot + substrate + cumulus 合并) |
| Explorer | https://polkadot.subscan.io | 2026-05-23 | 区块/extrinsic/account 浏览 |
| SCALE 编码规范 | https://docs.substrate.io/reference/scale-codec/ | 2026-05-23 | DSL 决策依据 |
| 公共 Sidecar | https://polkadot-public-sidecar.parity-chains.parity.io | 2026-05-23 | Parity 维护的公共 sidecar 实例(E1 实测 HTTP 200) |

---

## 2. Protocol Family(协议族)

| 项 | 值 |
|---|---|
| Family | **Substrate**(全新族;Kusama / Acala / Moonbeam / Astar / HydraDX / Bifrost 等几十条平行链全部继承本族 RPC) |
| Consensus | BABE(出块)+ GRANDPA(确定性) |
| VM | WASM(Substrate runtime);平行链可挂 EVM(Moonbeam)/ pallet-contracts(ink!) |
| Block Time | **6 秒**(实测 block #31363386 → #31363390 间隔约 24s = 4 block,见 §3 sidecar 返回) |
| Finality | GRANDPA,通常 12–60 秒;`chain_getFinalizedHead` 与 `chain_getHeader` 差约 2-4 个 block(E1 实测两者返回不同 hash 但相近 number) |
| Reuse Existing Adapter? | **No** — 新族需新 adapter(SubstrateAdapter) |

---

## 3. Public RPC(公共节点)

| Endpoint | Auth | Rate Limit | 备注 |
|---|---|---|---|
| `https://rpc.polkadot.io` | 无 | 未公开,实测可承受单测试 | 官方,JSON-RPC over HTTP + WSS |
| `https://polkadot-rpc.publicnode.com` | 无 | publicnode 通用 ~30 req/s ⚠️(未实测,凭训练记忆,需 benchmark 自测) | 官方文档列出 |
| `https://polkadot-public-sidecar.parity-chains.parity.io` | 无 | 未公开 ⚠️ | Parity 官方 sidecar REST,**E1 实测 HTTP 200** |

**curl 实测**(E1):

```bash
# E1.1 探活:system_chain
curl -s -X POST https://rpc.polkadot.io \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"system_chain","params":[]}'
# {"jsonrpc":"2.0","id":1,"result":"Polkadot"}

# E1.2 当前块头
curl -s -X POST https://rpc.polkadot.io \
  -d '{"jsonrpc":"2.0","id":1,"method":"chain_getHeader","params":[]}'
# {"result":{"parentHash":"0x549d...","number":"0x1de913a","stateRoot":"0xf26a...","extrinsicsRoot":"0x87d5...","digest":{...}}}
# number 0x1de913a = 31363386(实测)

# E1.3 finalized head
curl -s -X POST https://rpc.polkadot.io \
  -d '{"jsonrpc":"2.0","id":1,"method":"chain_getFinalizedHead","params":[]}'
# {"result":"0xd053e96edbed63e70cd8078fdd3d7488ea459f3d9a8422842391c7aff245dd23"}

# E1.4 system_health(同步 + peers)
# {"result":{"peers":80,"isSyncing":false,"shouldHavePeers":true}}

# E1.5 system_properties(SS58 + decimals)
# {"result":{"ss58Format":0,"tokenDecimals":10,"tokenSymbol":"DOT"}}

# E1.6 runtime_version
# {"result":{"specName":"polkadot","implName":"parity-polkadot","specVersion":2002001,...,"transactionVersion":26}}

# E1.7 Sidecar 探活(REST)
curl -s https://polkadot-public-sidecar.parity-chains.parity.io/blocks/head
# {"number":"31363386","hash":"0xa939...","authorId":"12vKNm9...","logs":[...]}
```

E1 全部 200,证 RPC + sidecar 均真活。

---

## 4. Account Model(账户模型)

| 项 | 值 |
|---|---|
| 模型 | **Account**(全局 AccountInfo,存储于 `System.Account` storage map) |
| Native token decimals | **10**(DOT;`system_properties.tokenDecimals=10` E1 实测) |
| Address derivation | **Sr25519**(默认)/ Ed25519 / ECDSA(secp256k1)三选,均派生为 32-byte AccountId |
| Special account types | Multisig(`pallet-multisig` 派生)、Proxy、Pure proxy、Treasury、Crowdloan reserve 账户 |

**AccountInfo 结构**(SCALE 编码,见 E5 raw 输出):
```
nonce:u32 + consumers:u32 + providers:u32 + sufficients:u32 + data:AccountData
AccountData = { free:u128, reserved:u128, frozen:u128, flags:u128 }
```
sidecar 直接解码为 JSON 字段 `nonce/free/reserved/frozen/transferable`(E2 见 §5)。

---

## 5. Core RPC Methods(本框架监控所需)

| Method | 类别 | 协议层(原生 RPC / Sidecar REST) | 说明 | 在 mixed 中权重建议 |
|---|---|---|---|---|
| `chain_getHeader` / `chain_getBlockHash(N)` | block height | RPC POST | 探活 + 高度同步;**header 含 number 而非余额** | 0.05 |
| `chain_getBlock(hash)` | block content | RPC POST,**需 2 跳**(先 `chain_getBlockHash(N)` 再 `chain_getBlock(hash)`) | 重量级,带 extrinsics | 0.10 |
| `GET /blocks/{number}`(sidecar) | block content | REST GET,**1 跳** | sidecar 直接按 height 取块,extrinsics 已解码 | 0.10 |
| `state_getStorage(storage_key)` | balance(raw) | RPC POST,**storage_key 必须 client-side SCALE 编码** | 返回 hex-encoded `AccountInfo`,客户端需 SCALE 解码 `free/reserved` | — 见 §11.7 决策 |
| `GET /accounts/{addr}/balance-info`(sidecar) | balance(包装) | REST GET,**0 Python** | E2 实测返回 `{free, reserved, frozen, transferable, nonce, tokenSymbol}` | 0.25 |
| `account_nextIndex(addr)` | nonce / tx_count | RPC POST | DSL 友好,无 SCALE | 0.10 |
| `GET /transaction/material/{hash}`(sidecar)/ `GET /blocks/{n}` 含 extrinsics | tx lookup | REST GET | Substrate 原生 RPC 无 `tx_getByHash`,**tx 查询必须依赖索引器(subscan/sidecar/archive)** ⚠️ | 0.15 |
| `system_health` | node info | RPC POST | peers + isSyncing | 0.05 |
| `system_chain` / `system_version` / `system_properties` | node info | RPC POST | 启动期一次性,benchmark 用作 warmup | 0.05 |
| `payment_queryInfo(extrinsic_hex)` | fee | RPC POST,**需 SCALE 编码 extrinsic** | DSL 不友好,仅 dry-run 场景需要 | 0.00(不入 mixed) |
| `state_getRuntimeVersion` | metadata | RPC POST | 用于 plugin warmup 校验 runtime spec | 0.05 |
| `state_getKeysPaged(prefix, count, startKey)` | storage 枚举 | RPC POST | E5 用此命令**抓真实 storage_key 样本**做 fixture | 0.05 |
| **chain-specific(staking)** `GET /pallets/staking/progress`(sidecar)| staking | REST GET | DOT 用户绝大多数有 staking,benchmark 应覆盖 | 0.15 |

> ⚠️ **tx_lookup 关键限制**:Substrate 节点**不**索引 extrinsic-by-hash(归档节点也只按 block 索引)。要"按 tx hash 查 tx"必须靠外部索引器(subscan API / sidecar `/transaction/material` 仅做 dry-run material 提取,不是 hash → tx 查询)。本框架的 `tx_lookup` 应替换为"按 block height 抓 extrinsics 列表"(sidecar `GET /blocks/{n}`)。

---

## 6. Address Format(地址格式)

| 项 | 值 |
|---|---|
| 编码 | **SS58**(Substrate 自定义 base58 变种,前缀 byte 决定链) |
| 长度 | 47–48 字符(Polkadot prefix=0,字符 `1...` 开头) |
| Checksum | **有**(blake2b-512 截前 2 字节,含 chain-prefix 在内一起 hash) |
| 示例(主网真实账户) | `13UVJyLnbVp9RBZYFwFGyDvVd1y27Tt8tkntv6Q7JVPhFsTB`(E2 实测有 `free=18207357669930` planck ≈ 1820.7 DOT,见 §3 sidecar 返回) |
| 校验正则 | `^1[1-9A-HJ-NP-Za-km-z]{46,47}$`(粗;严格校验需 SS58 decode + checksum 验证)|
| Chain-specific prefix byte | Polkadot=0 / Kusama=2 / Acala=10 / Moonbeam=1284(EVM 平行链用 hex)/ Astar=5 / Generic Substrate=42 |
| 跨 prefix 派生 | 同一 AccountId(32 字节)可重编码为任意 prefix 的 SS58(同 cosmos 系) |

---

## 7. Signature Lookup(签名/交易哈希)

| 项 | 值 |
|---|---|
| Hash 格式 | **Hex,带 `0x` 前缀**(blake2b-256 of SCALE-encoded extrinsic) |
| 长度 | **66 字符**(0x + 64 hex) |
| 示例(主网真实 extrinsic hash) | ⚠️ **未在本次 curl 中直接验证**(需从 sidecar `GET /blocks/31363386` 中取 `extrinsics[i].hash`,API 计算预算限制未执行第二跳)。**Phase 2.1 落地前必须补 E2 抓 hash** |
| 查询 method(原生 RPC) | **无**(Substrate 不按 hash 索引 extrinsic;见 §5 ⚠️) |
| 查询替代(sidecar) | `GET /blocks/{n}` 拿到 extrinsics 列表后用 `hash` 字段匹配,或 `GET /node/transaction-pool` 查 pending |
| 查询替代(索引器) | Subscan API:`POST /api/scan/extrinsic { "hash": "0x..." }` — **需 API key** |
| Explorer URL | `https://polkadot.subscan.io/extrinsic/<hash>` |

---

## 8. Mixed Set(`mixed` 模式权重)

> 假设 DSL 选 **Method B(sidecar REST)**(见 §11.8 决策)

```json
{
  "sidecar_balance":        0.25,
  "sidecar_block_by_n":     0.20,
  "sidecar_block_head":     0.10,
  "rpc_chain_getHeader":    0.05,
  "rpc_account_nextIndex":  0.10,
  "sidecar_staking_progress": 0.15,
  "rpc_system_health":      0.05,
  "rpc_state_getRuntimeVersion": 0.05,
  "rpc_chain_getBlockHash": 0.05
}
```

总和 = 0.25+0.20+0.10+0.05+0.10+0.15+0.05+0.05+0.05 = **1.00** ✅

具体路径映射:
- `sidecar_balance` → `GET {sidecar}/accounts/{addr}/balance-info`
- `sidecar_block_by_n` → `GET {sidecar}/blocks/{n}`
- `sidecar_block_head` → `GET {sidecar}/blocks/head`
- `rpc_chain_getHeader` → `POST {rpc}` body `{"method":"chain_getHeader","params":[]}`
- `rpc_account_nextIndex` → `POST {rpc}` body `{"method":"account_nextIndex","params":["{addr}"]}`
- `sidecar_staking_progress` → `GET {sidecar}/pallets/staking/progress`

---

## 8.5 Phase 2.1 caller/reader 改造点

**本链是新增链**,#1–#5 强制,#6–#8 视情况。

| # | 位置(file:line) | 改动 | 原因 |
|---|---|---|---|
| 1 | `config/config_loader.sh:666` `supported_blockchains` 数组 | 加 `"polkadot"` | 否则 `validate_blockchain_node` 拒绝 |
| 2 | `config/config_loader.sh:~380` 新增 `case polkadot)` 设 `MAINNET_RPC_URL=https://rpc.polkadot.io` 与 `MAINNET_SIDECAR_URL=https://polkadot-public-sidecar.parity-chains.parity.io` | 双 endpoint | 框架第一条需要 **JSON-RPC + REST 双 endpoint** 的链(Cosmos 已开先例但形态不同) |
| 3 | `config/config_loader.sh:~440-468` `UNIFIED_BLOCKCHAIN_CONFIG.blockchains.polkadot` | 新增 `rpc_methods.single` / `rpc_methods.mixed` / `param_formats` 含 §8 全部 method + addr/hash 格式 | 直接被 vegeta target 生成器消费 |
| 4 | `tools/mock_rpc_server.py:~137` | 新增 `do_GET` 分支(若 Cosmos 已加则复用)+ sidecar 路径路由 + POST JSON-RPC 的 substrate method 分支 | mock 需双协议 |
| 5 | `tools/fetch_active_accounts.py` 新增 `SubstrateAdapter(BlockchainAdapter)` | 用 sidecar `GET /blocks/{n}` 抓 extrinsics,从 `Balances.transfer_keep_alive.dest/source` 抽地址 | 本族无可复用 adapter |
| 6 | `analysis-notes/baseline-current-state.md` | grep 加 polkadot 入链路 | 文档真相 |
| 7 | `tests/` 新增 `test_substrate_adapter.py` | 至少 1 笔真主网 block fixture | L1 单测 |
| 8 | `core/master_qps_executor.sh --mixed --duration 30` | 全 200,无 -32601/-32602 | E2 证据 |

**关键陷阱**:
- Substrate 原生 `state_getStorage` 返回 hex-encoded SCALE 结构,**vegeta + 简单 status-code 校验会判 200 通过,但实际 0 Python 框架无法解出 balance** — 用 sidecar 规避(§11.8)。
- `chain_getBlock` 必须传 **block hash** 而非 number;若按 number 查需 2 跳(`chain_getBlockHash(N)` → `chain_getBlock(hash)`)。sidecar 屏蔽此差异。

---

## 9. Mock Notes(mock_rpc_server 实现要点)

### Sidecar 侧(REST GET):

- 请求路径:`GET /blocks/{n}`、`GET /blocks/head`、`GET /accounts/{addr}/balance-info`、`GET /pallets/staking/progress`
- 响应 schema 样本(真实主网,E1 实测):
  ```json
  {"at":{"hash":"0xd053e96e...","height":"31363390"},
   "nonce":"0","tokenSymbol":"DOT",
   "free":"18207357669930","reserved":"0",
   "frozen":"0","transferable":"18207357669930","locks":[]}
  ```
- 错误码:HTTP 400/404 + `{"code":N,"error":"..."}`(sidecar 风格)

### RPC 侧(POST JSON-RPC):

- 请求路径:`POST /`,body `{"jsonrpc":"2.0","method":"<ns>_<m>","params":[...],"id":N}`
- 响应 schema 样本(E1 实测 `state_getStorage` 返回 SCALE hex):
  ```json
  {"jsonrpc":"2.0","id":1,
   "result":"0x01000000010000000100000000000000bec93db304000000000000000000000080ea5da92e00000000000000000000000000000000000000000000000000000000000000000000000000000000000080"}
  ```
- 特殊错误码:
  - `-32601`:Method not found(Substrate 节点未开启的 RPC,如 unsafe RPC 默认禁用)
  - `-32602`:Invalid params(storage_key 非 hex / 长度不对)
  - `-32603`:Internal error(如 storage 不存在返回 `null` 在 `result` 字段而非 error)
- mock 复杂度:**High**
  - 双协议(REST GET + JSON-RPC POST)
  - sidecar 响应嵌套深(`extrinsics[].method.{pallet, method, args}`),建议 fixture
  - SCALE-encoded raw storage 返回值若 mock 真实编码需 polkadot.js / py-scale-codec — **决策上 mock 只返 sidecar 形态,raw `state_getStorage` 返回 fixture hex 串即可,不需真编码**

---

## 10. Adapter Reuse Decision(adapter 复用决策)

### 候选 adapter

| Adapter | 兼容度 | 缺失能力 |
|---|---|---|
| SolanaAdapter | 0% | 协议/地址/账户模型全不同 |
| EthereumAdapter | 0% | hex 地址 vs SS58,EVM vs WASM,JSON-RPC method 命名完全不同 |
| BitcoinAdapter | 0% | UTXO vs Account |
| CosmosAdapter | ~15% | 部分思路可借(REST GET + path param + 地址 prefix)但 schema/method/编码全不同 |
| 新建 **SubstrateAdapter** | 100% | — |

### 决策

- [x] **新建 `SubstrateAdapter`**(Substrate 全族,Kusama / Acala / Moonbeam EVM / Astar / HydraDX / Bifrost / Parallel / Centrifuge 等几十条平行链可复用,Phase 2.x 通过 `chain_type` + `ss58_prefix` + `token_decimals` + `token_symbol` 区分各链)
- [ ] 复用
- [ ] 混合

### 理由

(1) Substrate 是独立大族,与现有 4 族(EVM / Solana / Bitcoin / Cosmos)RPC method 命名空间、序列化(SCALE)、地址格式(SS58)、共识(BABE+GRANDPA)全不同,无 adapter 可复用。

(2) **族复用价值极高**:Kusama(SS58=2)、Acala(=10)、Astar(=5)、Moonbeam(EVM 平行链)、HydraDX、Bifrost 等几十条平行链全部继承 Substrate JSON-RPC + sidecar REST 抽象,**端点路径完全相同**,差异仅在(a)SS58 prefix(b)native token decimals / symbol(c)是否启用 EVM(Moonbeam 同时支持 substrate `state_*` 和 `eth_*` 双套 RPC)。SubstrateAdapter 落地后,每条平行链 0 Python 加链。

(3) **chain_type 模式**:`SubstrateAdapter.chain_type ∈ {polkadot, kusama, acala, moonbeam, astar, ...}`,用于(a)plugin 配置 SS58 prefix 校验;(b)EVM 平行链(Moonbeam/Astar)在 plugin 标 `dual_rpc=true`,允许 mixed set 混入 `eth_*` 方法;(c)pallet 差异(staking pallet 在 relay 链有,平行链多数无)。

### 配置 JSON 示例(本链)

```json
{
  "chain": "polkadot",
  "family": "substrate",
  "adapter": "SubstrateAdapter",
  "chain_type": "polkadot",
  "ss58_prefix": 0,
  "genesis_hash": "0x91b171bb158e2d3848fa23a9f1c25182fb8e20313b2c1eb49219da7a70ce90c3",
  "node_app": "polkadot",
  "node_app_version": "1.22.1-f8cfbb96055",
  "spec_version": 2002001,
  "transaction_version": 26,
  "api_protocol": ["jsonrpc", "rest_sidecar"],
  "rpc_endpoint": "https://rpc.polkadot.io",
  "sidecar_endpoint": "https://polkadot-public-sidecar.parity-chains.parity.io",
  "block_time_ms": 6000,
  "finality": "grandpa_~12s",
  "address_format": {
    "encoding": "ss58",
    "ss58_prefix": 0,
    "length_range": [47, 48],
    "regex": "^1[1-9A-HJ-NP-Za-km-z]{46,47}$"
  },
  "native_token": {"symbol": "DOT", "decimals": 10, "planck_per_dot": 10000000000},
  "rpc_methods": {
    "block_height":      {"protocol": "jsonrpc", "method": "chain_getHeader", "params": []},
    "block_by_number":   {"protocol": "rest",    "path": "/blocks/{n}"},
    "block_head":        {"protocol": "rest",    "path": "/blocks/head"},
    "balance":           {"protocol": "rest",    "path": "/accounts/{addr}/balance-info"},
    "nonce":             {"protocol": "jsonrpc", "method": "account_nextIndex", "params": ["{addr}"]},
    "staking_progress":  {"protocol": "rest",    "path": "/pallets/staking/progress"},
    "system_health":     {"protocol": "jsonrpc", "method": "system_health", "params": []},
    "runtime_version":   {"protocol": "jsonrpc", "method": "state_getRuntimeVersion", "params": []}
  },
  "mixed_weights": {
    "balance":          0.25,
    "block_by_number":  0.20,
    "staking_progress": 0.15,
    "nonce":            0.10,
    "block_head":       0.10,
    "block_height":     0.05,
    "system_health":    0.05,
    "runtime_version":  0.05,
    "block_hash":       0.05
  }
}
```

---

## 11. DSL 表达力分析(Substrate 关键)

### 11.1–11.6(对齐其他链通用条目)

- 11.1 method 命名:Substrate **模块化命名空间**(`state_/chain_/system_/author_/payment_/account_/childstate_/offchain_/grandpa_/babe_/...`),DSL 应支持 string-literal method 名,无需特殊解析。
- 11.2 params 类型:`[]` / `[hex_string]` / `[u32]` / `[hash, count, startKey?]`。DSL 需支持 hex literal、整数、null。
- 11.3 result 类型:hex string / number / 嵌套对象 / null。
- 11.4 错误 schema:标准 JSON-RPC `error.{code, message, data}`。
- 11.5 batch:Substrate RPC 支持 JSON-RPC batch ⚠️(未在本次 curl 直接验证),WSS 推荐用 subscription 模式。
- 11.6 双协议:**JSON-RPC over HTTP + Sidecar REST**(本框架需求);WSS 用于订阅 `chain_subscribeNewHeads`,本框架不需要。

### 11.7(强制)Substrate storage_key 编码挑战

| Method | 0 Python? | 详细 |
|---|---|---|
| **A. raw `state_getStorage(storage_key)`** | ❌ **否** | storage_key = `xxhash128("System") ++ xxhash128("Account") ++ blake2_128_concat(AccountId)` = 32B prefix + 16B blake2_128 + 32B AccountId = **80 byte hex 串**。前 32B 对 `System.Account` 是**常量**(`0x26aa394eea5630e07c48ae0c9558cef7b99d880ec681799c0cf30e8886371da9` — E3 实测验证:用 `state_getKeysPaged` 该前缀返回 ✅);**后 48B 必须 client-side 计算**(blake2_128 + AccountId 拼接)。返回值是 SCALE-encoded `AccountInfo`(E5 实测:`0x0100000001000000010000000000000 0bec93db304000000... ` 80+ byte),**客户端再 SCALE 解码** `nonce/free/reserved`(little-endian u32 + u128)。**DSL 0 Python 无法完成 blake2_128 + SCALE 解码**。 |
| **B. sidecar REST `GET /accounts/{addr}/balance-info`** | ✅ **是** | E2 实测返回纯 JSON `{nonce, free, reserved, frozen, transferable, tokenSymbol}`,字符串型大整数(planck),**0 Python 可直接用**。代价:依赖额外 sidecar 服务(Parity 提供公共实例 `https://polkadot-public-sidecar.parity-chains.parity.io`,本框架自部署或公共均可)。 |
| **C. 高层 RPC `system_account(addr)`** | — | ⚠️ **Polkadot 节点未提供此 RPC**(本次 `rpc_methods` 调用被 rate-limit 未直接验证,但 Substrate 官方 RPC list 中**无** `system_account`;有 `system_accountNextIndex` 即 `account_nextIndex` 别名,只返 nonce 不返 balance)。**Method C 不可用**。 |

**结论**:Polkadot **真没有"0 Python 拿 balance 的 RPC method"**,只能选 sidecar 或自带 SCALE 编码。

#### E5 raw storage 实测证据

```bash
# 1. 用 state_getKeysPaged 抓真实 storage_key(无需 client SCALE):
curl -s -X POST https://rpc.polkadot.io \
  -d '{"jsonrpc":"2.0","id":1,"method":"state_getKeysPaged",
       "params":["0x26aa394eea5630e07c48ae0c9558cef7b99d880ec681799c0cf30e8886371da9",2,null]}'
# 返回 2 个完整 key(80 byte hex):
# 0x26aa...371da9 + 000c143d12a73a70464df3694fdcc75a + ee080855f606cce66bdfffb8a73c54a440fa4a4ea1f9a487b7e2dadedaac205b
#                   |---- blake2_128(AccountId) ----|  |------------ AccountId(32B) ------------|

# 2. 用上述完整 key 查 storage:
curl -s -X POST https://rpc.polkadot.io \
  -d '{"jsonrpc":"2.0","id":1,"method":"state_getStorage",
       "params":["0x26aa394eea5630e07c48ae0c9558cef7b99d880ec681799c0cf30e8886371da9000c143d12a73a70464df3694fdcc75aee080855f606cce66bdfffb8a73c54a440fa4a4ea1f9a487b7e2dadedaac205b"]}'
# {"result":"0x01000000010000000100000000000000bec93db304000000000000000000000080ea5da92e00000000000000000000000000000000000000000000000000000000000000000000000000000000000080"}
# SCALE 解码:nonce=1 u32, consumers=1, providers=1, sufficients=0, free=0x04b33dc9be(LE u128)=20240670142, reserved=0x2ea95dea80, frozen=0, flags=0x80...

# 3. 反例:仅传 32B 前缀(无 AccountId)→ null
curl -s -X POST https://rpc.polkadot.io \
  -d '{"jsonrpc":"2.0","id":1,"method":"state_getStorage",
       "params":["0x26aa394eea5630e07c48ae0c9558cef7b99d880ec681799c0cf30e8886371da9"]}'
# {"result":null}   ← 证明 prefix 不是完整 key,必须 blake2_128_concat(AccountId) 才能命中
```

### 11.8(强制)DSL 选择建议

- [ ] Method A(raw `state_getStorage`,DSL 加 SCALE helper)
- [x] **Method B(sidecar REST,DSL 用通用 REST infra)** ← 推荐
- [ ] Method C(`system_account` 高层 method)— 不存在,排除

**理由**(3 段):

**(1) 0 Python 是硬约束**。Q4=C 目标"95% 加链 0 Python"。Method A 需引入 `py-scale-codec` + `blake2` + `xxhash` 三个 client-side 加密 / 编码库才能 **构造 storage_key 与解码 AccountInfo**;两端都要 Python,等于 substrate 全族(Kusama/Acala/Astar/Moonbeam 等几十条链)全部破 0 Python 约束。Method B 用通用 REST infra(已有 Cosmos REST 基础设施),sidecar 把 SCALE 全部屏蔽,plugin JSON 一行配置即可。

**(2) Sidecar 的 trade-off 可接受**。代价:多一个进程(sidecar)。收益:(a)公共实例 `https://polkadot-public-sidecar.parity-chains.parity.io` E1 实测可用,benchmark 短期可直接打公共;(b)Phase 2.x 长期可与节点同机部署,sidecar 是无状态 REST 包装,资源占用极小(~50MB RAM);(c)sidecar 同时屏蔽 `chain_getBlock` 双跳问题(原生 RPC 必须先 `chain_getBlockHash(N)` → `chain_getBlock(hash)`,sidecar `GET /blocks/{n}` 一跳)、extrinsic decode、staking 数据 — 三个方法都直接 0 Python 可用。一个依赖换三个方法的 DSL 友好性,值。

**(3) Method A 保留为 raw mode 选项**。某些场景(如纯性能 stress 测,要测节点 raw RPC 极限)可在 plugin 标 `mode: raw`,vegeta target 用 §11.7 E5 提到的 `state_getKeysPaged` 抓预生成的 storage_key 列表作 fixture,**只测 RPC 响应延迟,不要求客户端解码**(响应 hex 串 ≠ 0,即可判 200)。raw mode 不入默认 mixed,作为 stress profile 备选。

---

## ADR-0005 实施期 caller/reader 改造点(substrate family,2026-05-28)

**强制要求**(token-level-careful-edit Case-K + parallel-entry-trap):本链是 substrate family 5 链代表(polkadot/kusama/acala/astar/moonbeam),ADR-0005 引入 fake-node v2 `tools/fake-node/handlers/substrate.go`,改造点如下:

| # | 位置 | 改动 | 原因 |
|---|---|---|---|
| 1 | `tools/fake-node/handlers/substrate.go` | **新建** hex replay handler:`chain_getBlock` / `state_getStorage` 等返回的 SCALE-encoded hex 串无需解码,record 真 mainnet 一次 → replay echo | 通用 ~120 LOC 覆盖 substrate 5 链 |
| 2 | `tools/fake-node/fixtures/polkadot/` | record 8 method × 1 response = 8 fixture json | hex replay 数据源 |
| 3 | `config/chains/polkadot.json` `_meta.health_probe` | **新增**:`{"method":"system_chain","expect_result":"Polkadot"}` | fake-node startup self-check |
| 4 | sister chains(kusama / acala / astar / moonbeam)`_meta.health_probe` | 同结构,改 `expect_result` 为各自链名 | 5 链对称 |
| 5 | `tools/fake-node/fixtures/{kusama,acala,astar,moonbeam}/` | 每链 record 8 method,共 32 fixture json | replay 数据源,4 sister 链各自的 hex 不同 |
| 6 | `tests/test_substrate_smoke.sh` | **新建**:轮询 5 链 × 主要 method,断言 200 + hex 串非空 | L3 e2e |
| 7 | `tools/ci_smoke.sh` | 追加 substrate 5 链 | L3 全 PASS |

**Gate 3 验证**:改完跑 `grep -rn substrate tools/fake-node/handlers/` 确认 handler 注册 + `grep -rn 'adapter_family":"substrate"' config/chains/` 确认 5 链全有 family。

详见 `docs/architecture/decisions/0005-cardano-family-correction-and-handler-rollout.md`。

---

## Open Questions(待解决问题)

- [ ] **DSL ASK**:DSL 是否允许在 plugin JSON 中声明 `protocol: "rest_sidecar"` 与 `protocol: "jsonrpc"` 两种 method,vegeta target 生成器能否分别生成 GET + path 与 POST + body?(Cosmos 已开 REST GET 先例,Polkadot 是首条**双协议混用**的链 — 同一 plugin 一半 method 走 sidecar GET,一半走原生 POST。需框架确认 target 生成器支持 per-method `protocol` 字段。)
- [ ] **DSL ASK**:`{addr}` 占位符填充时,如何校验 SS58 checksum 而不引 Python?(候选:跳过校验交由节点返回 -32602;或 fetch_active_accounts 阶段已校验过,可信)
- [ ] **DSL ASK**:tx_lookup 无原生 RPC 支持,DSL 是否允许某 method 类型标 `skip_in_mixed: true` 仅在 single 模式可选?(否则 mixed 中无 tx_lookup 会与其他链不对齐。)
- [ ] **DSL ASK**:raw `state_getStorage` 的 storage_key fixture 模式 — DSL 是否支持 `fixture_file: "polkadot_storage_keys.txt"` 让 vegeta 从文件随机抽 key?(用于 Method A raw stress mode。)
- [ ] **未实证 ⚠️**:`https://polkadot-rpc.publicnode.com` 的真实 rate limit(凭训练记忆 ~30 req/s,需 benchmark 自测)
- [ ] **未实证 ⚠️**:Substrate JSON-RPC 是否支持 batch(`[{...},{...}]` body)— 本次未直接 curl 验证
- [ ] **未实证 ⚠️**:真实 extrinsic hash 抽样 — 本次因 API 预算未抓 `GET /blocks/31363386` 的 `extrinsics[].hash`,Phase 2.1 落地前补
- [ ] Moonbeam / Astar 等 EVM 平行链是否需要在 SubstrateAdapter 内做 `dual_rpc` 分支(substrate `state_*` + `eth_*` 同时支持)?Phase 2.2 视优先级处理。

---

## Changelog

| Date | Author | Change |
|---|---|---|
| 2026-05-23 | Hermes Agent | 初次调研;E1–E5 实测;DSL 决策 Method B(sidecar REST) |
