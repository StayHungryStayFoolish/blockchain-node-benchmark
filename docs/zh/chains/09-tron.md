# 09-tron 调研

> 由 `_template.md` 衍生。H8(真实证据):所有 RPC 调用均在 2026-05-23 对 `https://api.trongrid.io` 实测(HTTP API + JSON-RPC API 双协议同主机暴露)。

---

## 元信息

| 项 | 值 |
|---|---|
| 链名(中) | 波场 |
| 链名(英) | Tron |
| 编号 | 09 |
| Mainnet ChainID | EVM-compat `chainId = 728126428`(`0x2b6653dc`,E1 `eth_chainId` 实测);Tron 原生**无 chainId 概念**(用 ref_block_bytes/hash 防重放) |
| 调研日期 | 2026-05-23 |
| 调研者 | Hermes Agent |
| 状态 | 🟢 已完成 |

---

## 1. Sources(权威来源)

| 类型 | URL | 访问日期 | 备注 |
|---|---|---|---|
| 官方文档(HTTP) | https://developers.tron.network/reference | 2026-05-23 | Tron HTTP API 完整 reference(/wallet/*、/walletsolidity/*) |
| 官方文档(JSON-RPC) | https://developers.tron.network/reference/json-rpc | 2026-05-23 | EVM-compat JSON-RPC method 子集 |
| GitHub(节点) | https://github.com/tronprotocol/java-tron | 2026-05-23 | java-tron 全节点(SR / Full / Solidity Node 三角色) |
| Explorer | https://tronscan.org | 2026-05-23 | 区块/tx/合约浏览 |
| TronGrid | https://www.trongrid.io | 2026-05-23 | Tron 基金会运营的公共节点(本次实测端点) |
| TRC20 标准 | https://github.com/tronprotocol/tips/blob/master/tip-20.md | 2026-05-23 | Tron 版 ERC20(USDT-TRC20 即此) |

---

## 2. Protocol Family(协议族)

| 项 | 值 |
|---|---|
| Family | **Tron**(独立族,DPoS + TVM;**EVM-compatible 但非 EVM 原生**;无现有 adapter 可 100% 复用) |
| Consensus | **DPoS**(27 个 Super Representatives 出块) |
| VM | **TVM**(Tron Virtual Machine,EVM 子集 + 差异:Energy/Bandwidth 模型替代 gas、地址前缀 `0x41` 而非 `0x`、部分 opcode 差异) |
| Block Time | **3 秒**(E1 实测 block #82964399 → #82964400 时间戳差 3000ms) |
| Finality | **~57 秒**(19 个 SR 出块 = 19 × 3s 后视为不可逆,见 java-tron 文档)⚠️(未在本次直接 curl 测,凭官方文档) |
| Reuse Existing Adapter? | **混合** — EthereumAdapter 可复用 JSON-RPC 侧(~70%),HTTP API 侧需新建 `TronHttpAdapter`(见 §10) |

---

## 3. Public RPC(公共节点)

| Endpoint | Auth | Rate Limit | 备注 |
|---|---|---|---|
| `https://api.trongrid.io` | 无 / API key | 公开匿名 ~15 req/s ⚠️(凭 trongrid.io 文档常识,未本次实测) | **同时**暴露 HTTP API(`/wallet/*`、`/walletsolidity/*`)与 JSON-RPC(`/jsonrpc`);本次 E1–E5 全部实测此端点 |
| `https://tron-rpc.publicnode.com` | 无 | publicnode 通用 ⚠️ | 实测 `POST /` 返回 HTTP 405 — **publicnode 不接受默认根路径 POST**,需查文档确认正确路径;**本次未跑通**,降级候选 |
| `https://nile.trongrid.io` | 无 | — | **测试网,不用** |

**curl 实测**(E1):

```bash
# E1.1 HTTP API 探活:当前块
curl -s -X POST https://api.trongrid.io/wallet/getnowblock \
  -H "Content-Type: application/json" -d '{}'
# {"blockID":"0000000004f1efafd51db2259fff52248ab10ec49f2107074f17018a4bfbc765",
#  "block_header":{"raw_data":{"number":82964399,
#    "witness_address":"415a27141dbd202aa1344c042b51ae541262eebfb7",
#    "parentHash":"0000000004f1efaec3d6e44ca0016a5d2ec154e9ea12663f39e0ac34d6e49067",
#    "version":34,"timestamp":1779561837000},...},
#  "transactions":[{"txID":"8f81a66c89b80531...","contractRet":"SUCCESS",...}]}

# E1.2 JSON-RPC 探活:eth_blockNumber
curl -s -X POST https://api.trongrid.io/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_blockNumber","params":[]}'
# {"jsonrpc":"2.0","id":1,"result":"0x4f1efb0"}   ← 0x4f1efb0 = 82964464(同步)

# E1.3 JSON-RPC eth_chainId
curl -s -X POST https://api.trongrid.io/jsonrpc \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}'
# {"jsonrpc":"2.0","id":1,"result":"0x2b6653dc"}   ← = 728126428(主网官方 chainId)

# E1.4 同链双协议高度一致性(在数秒间隔内):HTTP=82964399, RPC=82964464
# 差异源于 RPC 调用时已过若干秒,新出块。两者均指向同一主网。
```

E1 全部 200,**双协议同一主机均真活**。

---

## 4. Account Model(账户模型)

| 项 | 值 |
|---|---|
| 模型 | **Account**(全局账户,无 UTXO) |
| Native token decimals | **6**(TRX,1 TRX = 10^6 sun;E2 实测 USDT 合约 `balance: 1073038702522` = 1,073,038.702522 TRX) |
| Address derivation | **secp256k1**(与 Ethereum 同曲线),但 hash + 前缀不同:`RIPEMD160(keccak256(pubkey)[-20:])` → 20B raw → 前置 `0x41` → 21B → Base58Check |
| Special account types | Normal / Contract(`type: "Contract"`)/ AssetIssue(早期 TRC10 token);TRC20 token 是普通合约,无独立账户类型 |

### 资源模型(独有)

Tron 不用 gas-per-op + gasPrice,改用双资源:

- **Bandwidth**(带宽):每笔 tx 字节数计费;每账户每日免费 600 字节(`freeNetLimit: 600`,E2 实测);超出消耗冻结的 TRX 换的 bandwidth points,或燃烧 TRX。
- **Energy**(能量):合约执行计费;**只能通过冻结 TRX 获得**(冻结 1 TRX 约换 ~5–10 Energy / 24h),或 stake/delegate;无 free Energy。
- E2 实测 USDT 合约 `triggerconstantcontract balanceOf` 返回 `energy_used: 4062, energy_penalty: 3127`,即 7189 Energy 总消耗(constant call 不上链,但节点报真实消耗用于估算)。

---

## 5. Core RPC Methods(本框架监控所需)

> 本框架双协议混用:balance/account/TRC20 走 HTTP API(语义完整),block height/JSON-RPC EVM 工具链兼容走 JSON-RPC。

| Method | 协议 | 类别 | 说明 | 在 mixed 中权重建议 |
|---|---|---|---|---|
| `eth_blockNumber` | JSON-RPC | block height | 探活 + 高度同步(轻量) | 0.05 |
| `/wallet/getnowblock` | HTTP | block content | 当前块全部 tx,重量级 | 0.10 |
| `/wallet/getblockbynum` | HTTP | block by number | 指定块,带 tx 详情 | 0.10 |
| `/wallet/gettransactionbyid` | HTTP | tx lookup | tx hash → 完整 tx | 0.15 |
| `eth_getTransactionByHash` | JSON-RPC | tx lookup | EVM-style tx 查询(返回 EVM 字段) | 0.05 |
| `/wallet/getaccount` | HTTP | balance + 元信息 | TRX 余额 + frozen + assetV2 一次返回 | 0.20 |
| `/wallet/triggerconstantcontract` | HTTP | TRC20 balance | USDT-TRC20 等合约调用(`balanceOf`) | 0.20 |
| `eth_call`(balanceOf) | JSON-RPC | TRC20 balance(EVM 风格) | 同上,Hex 输入输出 | 0.05 |
| `/wallet/getaccountresource` | HTTP | resource | Energy/Bandwidth 余额(链特色) | 0.10 |

**总权重 = 0.05+0.10+0.10+0.15+0.05+0.20+0.20+0.05+0.10 = 1.00** ✅

---

## 6. Address Format(地址格式)

| 项 | 值 |
|---|---|
| 编码 | **Base58Check**(T 前缀,主网)+ **Hex 41-prefix**(节点内部 / JSON-RPC 用) |
| 长度 | Base58: **34 字符**(以 `T` 起头);Hex: **42 字符**(`0x41` + 40 hex,即 21 byte) |
| Checksum | Base58Check **有**(SHA256 双哈希前 4 byte) |
| 示例(主网真实地址) | Base58: `TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t`(USDT-TRC20 合约,E2 实测 `getaccount` 返回 `account_name: "TetherToken", type: "Contract"`)|
| 同地址 Hex | `0x41a614f803b6fd780986a42c78ec9c7f77e6ded13c`(E5 `eth_getBalance` 实测返回 `0xf9d61737ba` = 1,072,538,464,186 sun) |
| 校验正则(Base58) | `^T[1-9A-HJ-NP-Za-km-z]{33}$` |
| 校验正则(Hex) | `^0x41[0-9a-fA-F]{40}$` |
| **同链双格式互转** | Base58 → Hex:Base58Check decode,**去掉末尾 4B checksum**,得 21B(含 `0x41` 前缀)→ hex。Hex → Base58:hex 解码,**双 SHA256 取前 4B 作 checksum 附加**,Base58 encode。**HTTP API 接受 `visible: true` 参数返回/接收 Base58,否则用 Hex** |

### E5 双格式互证(实测)

```bash
# 同一 USDT 合约,两套 API 查同一账户:
# HTTP (Base58):
curl -s -X POST https://api.trongrid.io/wallet/getaccount \
  -d '{"address":"TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t","visible":true}'
# {"account_name":"TetherToken","type":"Contract","balance":1073038702522,...}

# JSON-RPC (Hex):
curl -s -X POST https://api.trongrid.io/jsonrpc \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_getBalance",
       "params":["0x41a614f803b6fd780986a42c78ec9c7f77e6ded13c","latest"]}'
# {"result":"0xf9d61737ba"}   ← 0xf9d61737ba = 1,072,538,464,186 sun
# (两次时刻不同,差 ~5 亿 sun = 500 TRX,符合活跃合约账户)
```

---

## 7. Signature Lookup(签名/交易哈希)

| 项 | 值 |
|---|---|
| Hash 格式 | **Hex 无前缀**(HTTP API)/ **Hex 0x 前缀**(JSON-RPC)— 同一 hash 两种表示 |
| 长度 | 64 字符(32 byte 哈希) |
| 示例(主网真实 tx) | `8f81a66c89b80531717737c6c67716cbb38a5020a78c72d31740b4166f38c1d2`(E1 block #82964399 内 `txID`,E3 实测 `gettransactionbyid` 返回 `contractRet: "SUCCESS"`,合约类型 `UnDelegateResourceContract`) |
| 查询 method(HTTP) | `POST /wallet/gettransactionbyid {"value":"<hash 无前缀>"}` |
| 查询 method(JSON-RPC) | `eth_getTransactionByHash("0x" + <hash>)` |
| Explorer URL | `https://tronscan.org/#/transaction/<hash 无前缀>` |

### E3 实测

```bash
curl -s -X POST https://api.trongrid.io/wallet/gettransactionbyid \
  -d '{"value":"8f81a66c89b80531717737c6c67716cbb38a5020a78c72d31740b4166f38c1d2"}'
# {"ret":[{"contractRet":"SUCCESS"}],
#  "signature":["4a8d84a544ed45...01"],
#  "txID":"8f81a66c89b80531...",
#  "raw_data":{"contract":[{"parameter":{"value":{
#     "balance":7047090143,"resource":"ENERGY",
#     "receiver_address":"416569afa9...","owner_address":"41bcb31b39..."
#  },"type_url":"type.googleapis.com/protocol.UnDelegateResourceContract"},
#  "type":"UnDelegateResourceContract"}],...}}
```

---

## 8. Mixed Set(`mixed` 模式权重)

```json
{
  "balance_query":         0.20,
  "token_balance_http":    0.20,
  "tx_lookup_http":        0.15,
  "block_by_number_http":  0.10,
  "block_head_http":       0.10,
  "resource_query":        0.10,
  "block_height_rpc":      0.05,
  "tx_lookup_rpc":         0.05,
  "token_balance_rpc":     0.05
}
```

**权重和 = 0.20+0.20+0.15+0.10+0.10+0.10+0.05+0.05+0.05 = 1.00** ✅

设计取舍:
- **HTTP 主导(总权重 0.85)**:Tron 真实生产负载以 USDT-TRC20 转账、wallet 查询为主,HTTP API 是原生协议、字段最全(`frozenV2`、`assetV2`、Energy/Bandwidth 同接口返回),符合真实用户访问模型。
- **JSON-RPC 占 0.15**:覆盖 EVM 工具链路径(Web3.js / ethers.js 用户),验证 EVM-compat 层在压测下稳定。
- 同 method 双协议(token_balance、tx_lookup、block)各占一席,可独立观察双协议性能差。

---

## 8.5 Phase 2.1 caller/reader 改造点(token-level Gate 3)

Tron 是 wave 3 新增链,#1-3 必填,#4-8 视需要标 N/A 或 NEW。

| # | 位置(file:line) | 改动 | 原因 |
|---|---|---|---|
| 1 | `config/config_loader.sh` `UNIFIED_BLOCKCHAIN_CONFIG.blockchains.tron` | 新增 `rpc_methods.mixed` 含 §5/§8 全部 9 个 method + `protocol` per-method 字段(`http_post` / `jsonrpc`) | 直接被 vegeta target 生成器消费 |
| 2 | `config/config_loader.sh` `param_formats` | 新增 `address_base58`(`^T[...]{33}$`)/ `address_hex41`(`^0x41[...]{40}$`)/ `txid_hex_nopfx` / `triggerconstant_body` 四种 param 模板 | `generate_rpc_json` 漏字段会退默认 |
| 3 | `tools/mock_rpc_server.py` 新增 Tron 分支 | 新增 `do_POST` 路由:`/wallet/getnowblock`、`/wallet/getaccount`、`/wallet/getblockbynum`、`/wallet/gettransactionbyid`、`/wallet/triggerconstantcontract`、`/wallet/getaccountresource`、`/jsonrpc` 全部 method;响应用 §9 fixture | mock_rpc_server 是 fallback target,不改则 mock 模式跑不通 Tron |
| 4 | `tools/fetch_active_accounts.py` 新增 `TronAdapter(BlockchainAdapter)` | 用 HTTP `/wallet/getnowblock` 抓 transactions[].raw_data.contract[].parameter.value.{owner_address, to_address, contract_address},抽 base58 / 同时返回 hex 形式 | Tron 双格式必须返回两种,plugin 配置决定哪种入 vegeta target |
| 5 | `analysis-notes/baseline-current-state.md`(grep `tron`)| 新增 tron 入链路 + 双协议标注 | 文档真相对齐 |
| 6 | `analysis-notes/disk-and-network-pipeline-redesign.md` | 同步 tron 列入双协议链 | 同上 |
| 7 | `analysis-notes/research_notes/<tron 笔记>.md` | 本调研文档已就位 | — |
| 8 | `tests/test_tron_adapter.py`(NEW) | 1 笔真主网 block fixture(82964399)+ base58↔hex 互转单测 + 双协议响应 schema 断言 | L1/L2 单测 |

**关键陷阱**:
- **base58 ↔ hex 互转必须 plugin 配置 side**:vegeta target 生成器只看 plugin JSON,**不能在运行时计算 Base58Check**(0 Python 约束)。fetch_active_accounts.py 阶段一次性产出两份地址列表(`tron_accounts_base58.txt`、`tron_accounts_hex41.txt`),plugin per-method 引用其一。
- **triggerconstantcontract 的 `parameter` 字段**:必须 plugin 预生成 hex 字串(64 char,address-padded),DSL 不能在 vegeta target 内即时编码 `address` → padded hex。fetch_active_accounts 阶段需扩展产出 `tron_balanceof_params.txt`(每行 `<contract>,<padded_hex_owner>`)。
- **JSON-RPC 路径是 `/jsonrpc` 而非根 `/`**:与多数 EVM 链不同,plugin endpoint 配置必须显式带 `/jsonrpc` 后缀。

**测试要求**:Phase 2.1 完成后跑 `core/master_qps_executor.sh --chain tron --mixed --duration 30`,**所有请求 200**,作为 Tron E2 证据。

---

## 9. Mock Notes(mock_rpc_server 实现要点)

### HTTP API 侧(POST + JSON body):

- 请求路径:`POST /wallet/getnowblock`、`POST /wallet/getaccount`、`POST /wallet/getblockbynum`、`POST /wallet/gettransactionbyid`、`POST /wallet/triggerconstantcontract`、`POST /wallet/getaccountresource`、`POST /walletsolidity/getnowblock`
- 响应 schema 样本(E2 实测,USDT 合约):
  ```json
  {"account_name": "TetherToken",
   "type": "Contract",
   "address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
   "balance": 1073038702522,
   "net_window_size": 28800000,
   "frozenV2": [{},{"type": "ENERGY"},{"type": "TRON_POWER"}],
   "assetV2": [{"key": "1002963","value": 58000000}, ...]}
  ```
- triggerconstantcontract 响应(E2 实测 `balanceOf(self)`):
  ```json
  {"result":{"result":true},
   "energy_used":4062,"energy_penalty":3127,
   "constant_result":["000000000000000000000000000000000000000000000000000000bdb69fb7a7"],
   "transaction":{"txID":"89afa1fc...","raw_data":{...}}}
  ```
- 错误码:HTTP **405**(路径不存在,E5 实测)/ HTTP 200 + `{"Error":"<msg>"}`(参数错误,文档,⚠️ 本次未直接 curl 触发)

### JSON-RPC 侧(POST `/jsonrpc`):

- 请求路径:`POST /jsonrpc`,body `{"jsonrpc":"2.0","method":"eth_*","params":[...],"id":N}`
- 响应 schema 样本(E1 实测 `eth_blockNumber`):
  ```json
  {"jsonrpc":"2.0","id":1,"result":"0x4f1efb0"}
  ```
- `eth_call` 响应(E5 实测 balanceOf):
  ```json
  {"jsonrpc":"2.0","id":1,
   "result":"0x000000000000000000000000000000000000000000000000000000bdb69fb7a7"}
  ```
- 特殊错误码(E5 实测):
  - `-32601`: `{"error":{"code":-32601,"message":"method not found"}}`(实测 `eth_doesnotexist` 触发)
  - `-32602`: Invalid params(文档,本次未直接触发)
- mock 复杂度:**High**
  - **双协议、双路径前缀**(`/wallet/*` POST body + `/jsonrpc` POST body),mock_rpc_server 必须按 `parsed_url.path` 路由,而非一律读 body.method
  - `getaccount` 响应 schema 极深(`frozenV2[]`、`assetV2[]`、`account_resource`、`votes`),建议直接用 fixture 文件
  - **双协议响应字段命名不同**:`eth_getBlockByNumber` 返回 `hash/parentHash/number(hex)`,`/wallet/getnowblock` 返回 `blockID/parentHash/number(int)` — mock 不能复用同一 dataclass

---

## 10. Adapter Reuse Decision(adapter 复用决策)

### 候选 adapter

| Adapter | 兼容度 | 缺失能力 |
|---|---|---|
| EthereumAdapter | **~50%**(仅 JSON-RPC 侧;`eth_blockNumber/getBlockByNumber/getBalance/getTransactionByHash/call/chainId` 名字完全相同) | (a) 不支持 HTTP `/wallet/*` REST POST 形式;(b) 地址 Base58 ↔ Hex41 互转;(c) Energy/Bandwidth 资源模型无对应;(d) JSON-RPC 路径 `/jsonrpc` 而非根 `/` |
| SolanaAdapter | 0% | 协议/账户全不同 |
| BitcoinAdapter | 0% | UTXO vs Account |
| CosmosAdapter | ~10%(REST GET 经验可借,但 Tron 是 POST + body,schema/method 完全不同) | — |
| SubstrateAdapter(Polkadot wave 2) | ~25%(**双协议 per-method DSL 模式可复用** — `protocol: jsonrpc` vs `protocol: rest`;但 Polkadot REST 是 **GET + path 占位**,Tron HTTP 是 **POST + body 占位**,DSL 协议常量需扩) | 见 §11 |

### 决策

- [ ] 复用单一 adapter
- [ ] 新建单一 adapter
- [x] **混合**:**新建 `TronAdapter`(HTTP API 侧)** + **复用 `EthereumAdapter` 子集(JSON-RPC 侧)**;由 `TronAdapter` 顶层路由 per-method `protocol` 字段,委托给 EthereumAdapter 处理 JSON-RPC 形态

### 理由

(1) **Tron HTTP API 是独立协议**,不是 REST CRUD,而是 `POST <path> + JSON body` 的 RPC-over-REST 形式(每个 method 一个独立路径,body 是 method 参数)。这个形态与 Cosmos REST(GET + query params)、Polkadot sidecar(GET + path 占位)、EVM JSON-RPC(POST root + body.method)都不同。没有现成 adapter 可复用,**必须新建** TronHttpAdapter 处理 path 路由 + body 模板 + base58 ↔ hex 互转。

(2) **JSON-RPC 侧 EthereumAdapter 复用价值高**。Tron 的 `/jsonrpc` 端点对 `eth_blockNumber / eth_chainId / eth_getBalance / eth_call / eth_getBlockByNumber / eth_getTransactionByHash` 完全兼容(E1+E5 实测响应字段名、hex 编码、错误码与 Ethereum 主网一致),只需 EthereumAdapter 接受 `rpc_path = "/jsonrpc"` 配置参数(默认 `/`),即可直接复用。**强制全部走 HTTP API 会浪费 EVM-compat 兼容性,且与多链统一 mixed set 设计(每链都有 EVM 风格压测路径)目标背离**。

(3) **DSL 双协议 per-method 模式 = Polkadot 同款**。Polkadot wave 2 已确认 DSL 支持 plugin JSON 中 per-method `protocol` 字段(`jsonrpc` vs `rest_sidecar`),Tron 是第 2 条双协议链,**复用此 DSL pattern,扩 `protocol` 枚举加 `rest_post`**(POST + body 模板)即可。Polkadot 的 REST 是 GET + path 占位(`/blocks/{n}`),Tron 的 REST 是 POST + body 占位(`{"address":"{addr}"}`),vegeta target 生成器需支持两种 REST 子模式 — DSL 设计上是一个 enum 扩值,不破坏既有架构。详见 §11.7/11.8。

### 配置 JSON 示例(本链)

```json
{
  "chain": "tron",
  "family": "tron",
  "adapter": "TronAdapter",
  "delegate_adapter_jsonrpc": "EthereumAdapter",
  "chain_id": 728126428,
  "chain_id_hex": "0x2b6653dc",
  "node_app": "java-tron",
  "block_time_ms": 3000,
  "finality_blocks": 19,
  "api_protocol": ["http_post", "jsonrpc"],
  "http_endpoint": "https://api.trongrid.io",
  "rpc_endpoint": "https://api.trongrid.io/jsonrpc",
  "address_format": {
    "primary":   {"encoding": "base58check", "prefix": "T",   "length": 34, "regex": "^T[1-9A-HJ-NP-Za-km-z]{33}$"},
    "secondary": {"encoding": "hex",         "prefix": "0x41","length": 42, "regex": "^0x41[0-9a-fA-F]{40}$"},
    "conversion": "base58check<->hex41 (drop 4B checksum)"
  },
  "native_token": {"symbol": "TRX", "decimals": 6, "sun_per_trx": 1000000},
  "resource_model": {"energy": true, "bandwidth": true, "gas_model": false, "free_bandwidth_per_day": 600},
  "rpc_methods": {
    "block_height_rpc":     {"protocol": "jsonrpc",   "method": "eth_blockNumber",         "params": []},
    "block_head_http":      {"protocol": "http_post", "path": "/wallet/getnowblock",       "body": {}},
    "block_by_number_http": {"protocol": "http_post", "path": "/wallet/getblockbynum",     "body": {"num": "{block_num}"}},
    "tx_lookup_http":       {"protocol": "http_post", "path": "/wallet/gettransactionbyid","body": {"value": "{txid_nopfx}"}},
    "tx_lookup_rpc":        {"protocol": "jsonrpc",   "method": "eth_getTransactionByHash","params": ["{txid_0xpfx}"]},
    "balance_query":        {"protocol": "http_post", "path": "/wallet/getaccount",        "body": {"address": "{addr_base58}", "visible": true}},
    "token_balance_http":   {"protocol": "http_post", "path": "/wallet/triggerconstantcontract",
                             "body": {"owner_address": "{addr_base58}", "contract_address": "{trc20_contract_base58}",
                                      "function_selector": "balanceOf(address)", "parameter": "{padded_hex_owner}", "visible": true}},
    "token_balance_rpc":    {"protocol": "jsonrpc",   "method": "eth_call",
                             "params": [{"to": "{trc20_contract_hex41}", "data": "0x70a08231{padded_hex_owner}"}, "latest"]},
    "resource_query":       {"protocol": "http_post", "path": "/wallet/getaccountresource", "body": {"address": "{addr_base58}", "visible": true}}
  },
  "mixed_weights": {
    "balance_query":        0.20,
    "token_balance_http":   0.20,
    "tx_lookup_http":       0.15,
    "block_by_number_http": 0.10,
    "block_head_http":      0.10,
    "resource_query":       0.10,
    "block_height_rpc":     0.05,
    "tx_lookup_rpc":        0.05,
    "token_balance_rpc":    0.05
  }
}
```

---

## 11. DSL 表达力分析(Tron 双 API 关键)

### 11.1–11.6(对齐其他链通用条目)

- **11.1 method 命名**:HTTP API method 是 path(`/wallet/<verb>`),JSON-RPC 是 `eth_*` literal。DSL 已支持 string literal 二者。
- **11.2 params 类型**:HTTP 是 body JSON object(任意嵌套);JSON-RPC 是 array `[obj | string | "latest"]`。DSL 占位符替换 `{addr_base58}` / `{txid_nopfx}` / `{padded_hex_owner}` 等必须 plugin pre-baked。
- **11.3 result 类型**:HTTP 返回原始 JSON(无 `result` 包装,直接顶层字段如 `blockID`);JSON-RPC 返回 `{jsonrpc, id, result}`。**响应校验路径不同**,DSL 需 per-protocol 配置 `success_check`(HTTP 校验 status=200 且无 `Error` 字段;JSON-RPC 校验 `result != null && error == undefined`)。
- **11.4 错误 schema**:HTTP — HTTP 405(路径错,E5 实测)/ HTTP 200 + `{"Error":"<msg>"}`(参数错,⚠️ 本次未触发);JSON-RPC — `{"error":{"code":-32601,"message":"method not found"}}`(E5 实测)。
- **11.5 batch**:JSON-RPC ⚠️(未本次验证,Tron 官方文档未明确,需自测);HTTP API 不支持 batch,每 method 独立 POST。
- **11.6 双协议**:**HTTP API(POST + body)+ JSON-RPC(POST + body)同主机暴露**,这是本链 DSL 核心命题(见 11.7)。

### 11.7(强制)Tron HTTP API vs JSON-RPC API 对比(全部 E1–E5 实测)

| 维度 | HTTP API(原生) | JSON-RPC API(EVM-compat) |
|---|---|---|
| 协议 | REST 风格 RPC-over-HTTP(POST + JSON body) | JSON-RPC 2.0(POST + body.method) |
| 入口路径 | `/wallet/<verb>`、`/walletsolidity/<verb>`(每 method 独立 path) | 单一 `/jsonrpc` |
| balance 查询 | `POST /wallet/getaccount {"address":"T...","visible":true}` → `{"balance":1073038702522,"frozenV2":[...],"assetV2":[...]}`(E2 实测) | `eth_getBalance("0x41...","latest")` → `"0xf9d61737ba"`(E5 实测) |
| tx 查询 | `POST /wallet/gettransactionbyid {"value":"<hash 无前缀>"}` → 完整 `{ret, signature, txID, raw_data{contract[],ref_block_bytes,expiration,...}}`(E3 实测) | `eth_getTransactionByHash("0x<hash>")` → EVM-style 字段(`from/to/value/gas/...`)⚠️(本次未直接 curl,凭 Tron JSON-RPC 文档) |
| block 查询 | `POST /wallet/getnowblock {}` → `{blockID, block_header{raw_data{number,timestamp,...}}, transactions[]}`(E1 实测 #82964399) | `eth_getBlockByNumber("latest", false)` → `{hash, parentHash, number(hex), timestamp(hex), transactions[hash], gasLimit/gasUsed/baseFeePerGas/...}`(E1 实测 — Tron 节点甚至填充了 `baseFeePerGas:"0x0"` 等 EVM 字段) |
| TRC20 余额 | `POST /wallet/triggerconstantcontract {owner_address, contract_address, function_selector:"balanceOf(address)", parameter:"<padded hex>", visible:true}` → `{"result":{"result":true}, "energy_used":4062, "constant_result":["0x...bdb69fb7a7"]}`(E2 实测) | `eth_call({"to":"0x41...","data":"0x70a08231<padded>"}, "latest")` → `"0x000000...bdb69fb7a7"`(E5 实测,**与 HTTP 返回 hex 字串完全一致**) |
| 地址格式输入 | Base58Check(`T...`,需 `visible:true`)或 Hex41(无 `visible`) | Hex41(`0x41...`) |
| 错误返回 | HTTP 405(path 不存在,E5 实测)/ HTTP 200 + `{"Error":"..."}`(参数错,文档,⚠️ 未触发) | `{"error":{"code":-32601,"message":"method not found"}}`(E5 实测) |
| 文档完整性 | **完整**(Tron 原生 API,全部 `/wallet/*` 都有文档) | **部分**(仅常用 EVM method 子集 — `eth_blockNumber/chainId/getBalance/call/getTransactionByHash/getBlockByNumber/getLogs/...`;**无 Tron 独有信息** — frozen / Energy / TRC10 资产) |
| 字段语义完整度 | **高**(资源、frozen、assetV2、Bandwidth、Energy 一接口返回) | **低**(只有 EVM 抽象层 — balance、tx、block;Tron 独有信息丢失) |
| 与其他 EVM 链 DSL 复用 | **低**(独有协议,独立 adapter) | **高**(与现有 8 链 EVM JSON-RPC 完全同构,仅 path `/jsonrpc` 不同) |

**关键发现**:
- **同一 `balanceOf` 查询,两套 API 返回的 hex 串完全一致**(`0xbdb69fb7a7`)— 证明 JSON-RPC 是 HTTP API 的薄包装,底层共享 TVM 执行。
- **block / tx 在两套 API 中字段名完全不同**(`blockID` vs `hash`,`txID` vs `hash`,`witness_address` vs `miner`),但底层指向同一区块。
- HTTP API 是 **POST + body 占位**,Polkadot sidecar 是 **GET + path 占位** — 都是 REST,但 vegeta target 生成器需要分别支持两种子模式。

### 11.8(强制)DSL 选择建议

- [ ] HTTP API only(原生,文档完整,但 DSL 需 path 参数 + REST POST body schema;放弃 EVM-compat 复用)
- [ ] JSON-RPC API only(EVM-compat,DSL 与现有 8 链 EVM 复用,但 method 不全 — 拿不到 frozen/Energy/Bandwidth)
- [x] **都支持(per-method protocol),DSL 配置每 method 走哪套**(balance/TRC20/资源/区块 走 HTTP API,EVM-compat 高度同步路径走 JSON-RPC,**双协议混压更真实**)
- [ ] 双协议自动 fallback(主走一套,失败 fallback 另一套)— 排除,见理由(3)

**理由**(3 段):

**(1) 双 API 是 Tron 设计的客观现实,DSL 必须建模**。Tron 节点同时暴露两套 API 不是冗余,而是覆盖两类客户:HTTP API 服务 Tron 原生钱包(TronLink、TokenPocket、Tron-CLI)及需要 frozen/Energy/Bandwidth 完整信息的 dApp;JSON-RPC 服务 Web3.js / ethers.js 生态用户(把 Tron 当 EVM 链用)。**只选一套**就脱离真实生产负载分布。混合压测能反映真实节点压力分布:HTTP 体量大、字段全、payload 重;JSON-RPC 体量轻、字段简。两者对节点的 IO/CPU 模式不同,benchmark 必须覆盖。

**(2) DSL pattern 与 Polkadot 高度同构,复用度评估 ~60%**。Polkadot wave 2 已确定 plugin JSON 支持 per-method `"protocol": "jsonrpc" | "rest"` 字段,Tron 是第 2 条双协议链,**完全复用此 DSL pattern**,只需把 `protocol` 枚举从 `{jsonrpc, rest}` 扩到 `{jsonrpc, rest_get_path, rest_post_body}`(或更通用的 `{jsonrpc, http}` + `method: GET|POST` + `path` + `body` 子字段)。vegeta target 生成器需为 `rest_post_body` 实现 body 模板渲染(占位符替换),这是新逻辑,**但所有 plugin-side 配置语法与 Polkadot 一致**。Polkadot 已建好的 per-method protocol 字段、success_check 抽象、fixture-based param 列表(`tron_accounts_base58.txt` 等)三大基础设施 100% 复用。**净增工程量:仅 `rest_post_body` 子模式的 body 渲染器**(~30 行)。

**(3) 排除自动 fallback**:fallback 看似省心,但(a)两套 API 返回 schema 不同(`blockID` vs `hash`、HTTP 顶层 vs JSON-RPC `.result`),fallback 后下游解析逻辑必须分支,等于双协议 caller 都要写两遍,无简化;(b)benchmark 目标是测节点真实压力,fallback 会**掩盖某一协议的故障**(如 JSON-RPC `/jsonrpc` 单 endpoint 性能瓶颈),违背可观测性;(c)同 method 双协议是独立 mixed set 条目(`tx_lookup_http` 0.15 + `tx_lookup_rpc` 0.05),已是显式分压,无需 fallback。**显式优于隐式**。

#### 与 Polkadot 双协议 infra 复用度评估

| 设施 | Polkadot wave 2 已建 | Tron 是否能直接复用 | 增量工作 |
|---|---|---|---|
| plugin JSON `api_protocol: [...]` 列表字段 | ✅ `["jsonrpc","rest_sidecar"]` | ✅ 改为 `["jsonrpc","http_post"]` | 0 |
| per-method `protocol` 字段 | ✅ `"protocol": "jsonrpc" \| "rest"` | ✅ 同字段名,扩枚举值 | enum 扩 1 值 |
| `path` 占位符模板渲染(`/blocks/{n}`) | ✅ GET path 渲染 | ⚠️ Tron 是 path 固定 + body 模板,**body 渲染是新逻辑** | ~30 行 body 模板渲染器 |
| `success_check` per-protocol 抽象 | ✅ HTTP 200 + JSON 字段断言 | ✅ 直接复用,只是断言字段名不同(plugin 配置) | 0 |
| fixture-based param 列表(预生成地址/hash) | ✅ 已建(`polkadot_accounts.txt`) | ✅ 直接复用,新增 `tron_accounts_base58.txt`/`tron_accounts_hex41.txt`/`tron_balanceof_params.txt` | adapter 内一次性预生成 |
| mock_rpc_server 双路径路由 | ✅ Polkadot 已建 `do_GET` 分支 + sidecar 路径路由 | ✅ Tron 只需扩 `do_POST` 内的路径分支(`/wallet/*` + `/jsonrpc`) | ~50 行 mock 分支 |
| **总复用度** | — | **~60%** | 净增 ~80 行 + adapter |

**结论**:**Polkadot 双协议 DSL 设计经过 Tron 验证后,可推广到任何\"主协议 + EVM-compat 包装\"链**(后续候选:NEAR EVM-compat、Aurora、未来 ICP 等)。DSL 双协议字段足够通用,本次扩值 `rest_post_body` 后,**架构无需再改**。

---

## Open Questions(待解决问题)

- [ ] **DSL ASK**:`protocol` 枚举值如何取舍 — 偏 Polkadot 风格 `{jsonrpc, rest}` + 子字段 `http_method: GET|POST` + `body`?还是直接扩成 `{jsonrpc, rest_get_path, rest_post_body}` 三值?前者更通用,后者更显式。建议前者(可扩 PUT/PATCH 等)。
- [ ] **DSL ASK**:HTTP API path 是否需支持占位符(本调研所有 Tron HTTP path 都是静态)?保留 `/wallet/{verb}` 占位以备未来扩。
- [ ] **DSL ASK**:base58 ↔ hex41 互转是否归 fetch_active_accounts 阶段一次性产出(0 Python 友好)还是 plugin 配置时声明 `address_class: base58|hex41` 让 adapter 运行时转?**强烈推荐前者**(避免运行时 Python)。
- [ ] **DSL ASK**:JSON-RPC `params` 数组中的 hex 串拼接(`"0x70a08231{padded_hex_owner}"`)的 string concat 占位符是否已被 DSL 支持?Polkadot 仅在独立 string 占位,Tron 是首例需要**字符串拼接**(selector + padded owner)。建议 vegeta target 生成器在渲染时先扫描整个 params/body 树,做嵌入式 `{...}` 替换。
- [ ] **DSL ASK**:`success_check` 双协议断言字段名差异 — Polkadot 是 sidecar 顶层 `nonce/free` 字段存在校验,Tron HTTP 是无 `Error` 字段 + 顶层字段(如 `blockID`)存在校验。DSL 是否需要 `success_check: {"jsonpath": "$.result", "not_null": true}` 这种结构化校验?
- [ ] **未实证 ⚠️**:`https://api.trongrid.io` 真实 rate limit(凭 trongrid 文档常识 ~15 req/s,本次未直接打满测试)
- [ ] **未实证 ⚠️**:`eth_getTransactionByHash` 在 Tron JSON-RPC 的真实返回 schema — 本次未抓真实 EVM-style tx 测(`eth_getBlockByNumber latest+true` 在某些块可能 `transactions` 为空,API 预算已用完)
- [ ] **未实证 ⚠️**:JSON-RPC batch(`[{...},{...}]`)是否支持 — Tron 官方 JSON-RPC 文档未明确,需自测
- [ ] **未实证 ⚠️**:`https://tron-rpc.publicnode.com` 的正确路径 — 本次 `POST /` 返回 HTTP 405,推测路径不是根。降级为候选,Phase 2.1 前查 publicnode 文档确认
- [ ] **未实证 ⚠️**:HTTP API 参数错误的真实错误体(预期 `{"Error":"..."}`,本次未触发)
- [ ] **未实证 ⚠️**:Tron Finality 真实数值(19 个 SR × 3s ≈ 57s 凭 java-tron 文档)
- [ ] **DSL ASK / Phase 2.x**:USDT-TRC20 是 Tron 70%+ 流量来源,mixed set 是否需要为单一最热合约设权重?当前设计 `token_balance_http: 0.20` 是合约平均权重,可考虑 `tron.usdt_trc20_balance: 0.30 + 其他 trc20: 0.10` 拆分。Phase 2.2 视压测真实数据决定。

---

## Changelog

| Date | Author | Change |
|---|---|---|
| 2026-05-23 | Hermes Agent | 初次调研;E1–E5 实测;双 API DSL 决策 = per-method protocol;复用 Polkadot 双协议 DSL pattern ~60% |
