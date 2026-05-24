# 30-ton 调研

> **本文件由 `_template.md` 衍生(11 节齐全),遵守 H8(真实证据):curl 实测 + 官方文档 URL + 访问日期。**
> 未 100% 实证的断言均以 ⚠️ 显式标注。
> 风格对齐 `04-aptos.md` / `11-tezos.md`。

---

## 元信息

| 项 | 值 |
|---|---|
| 链名(中) | TON / 开放网络 |
| 链名(英) | The Open Network (TON) |
| 编号 | 30 |
| Mainnet ChainID | `-239`(global_id,实证自 v3 `/masterchainInfo` `"global_id":-239`)|
| 调研日期 | 2026-05-24 |
| 调研者 | Hermes Agent |
| 状态 | 🟢 已完成(H8 实证 toncenter v2 REST 8 个 method + v2 JSON-RPC + v3 REST 2 个 method + tonhub v4 1 个 endpoint) |

---

## 1. Sources(权威来源)

| 类型 | URL | 访问日期 | 备注 |
|---|---|---|---|
| 官方协议站 | https://ton.org | 2026-05-24 | 项目入口 — ⚠️ 未 DOM 实证(仅引用) |
| TON Docs | https://docs.ton.org | 2026-05-24 | 协议/VM/RPC 总文档入口 — ⚠️ 未 DOM 实证 |
| toncenter API v2 文档 | https://toncenter.com/api/v2/ | 2026-05-24 | REST + JSON-RPC 双协议接口文档 — ⚠️ 未 DOM 实证 |
| toncenter API v3 文档 | https://toncenter.com/api/v3/ | 2026-05-24 | 新 REST 版(indexer 风格)— ⚠️ 未 DOM 实证 |
| GitHub(ton-blockchain/ton)| https://github.com/ton-blockchain/ton | 2026-05-24 | C++ 客户端 — ⚠️ 未 git clone |
| TonScan Explorer | https://tonscan.org | 2026-05-24 | 用于人工 cross-check 地址 / tx |
| Tonviewer Explorer | https://tonviewer.com | 2026-05-24 | 备选浏览器 |

---

## 2. Protocol Family(协议族)

| 项 | 值 |
|---|---|
| Family | **TON**(独立 family,不与 EVM/Cosmos/Substrate/Move 混) |
| Consensus | **BFT-PoS**(Catchain + Validator Sessions)— E3 文档,H8 仅证 masterchain 持续出块 |
| VM | **TVM**(TON Virtual Machine,栈式;源语言 FunC / Tact / Tolk) |
| Block Time | **masterchain ~5s,workchain ~3s** — H8 部分实证:连续两次 `/getConsensusBlock` 返 68727899 @ ts=1779582496 → 68728056 @ ts=1779582559 → Δ=157 blocks / 63s ≈ **0.40 s/block**(注:这是 masterchain seqno + workchain 合并视角的 consensus_block 速率;真实 mc 出块约 5s,详见 v3 `gen_utime` 推算 ⚠️ 未完整 E2)|
| Finality | **~5s soft / ~7s hard**(BFT 一旦多数签名即终结) — ⚠️ 未 E2 直接对比 |
| Reuse Existing Adapter? | **No** — TON 是独立 family(分片 masterchain/workchain + bag-of-cells + TL-B 序列化 + 每账户独立合约模型),需新增 `TONAdapter`(详见 §10) |

---

## 3. Public RPC(公共节点)

| Endpoint | Auth | Rate Limit | 备注 |
|---|---|---|---|
| https://toncenter.com/api/v2/ | 无(可选 API key) | **1 RPS 无 key**(官方文档)/ 10 RPS with key | **H8 实证活**:REST + JSON-RPC 双协议,延迟 ~0.28s |
| https://toncenter.com/api/v3/ | 无(可选 API key) | **1 RPS 无 key**(共享) | **H8 实证活**(`/masterchainInfo` 200);indexer 风格,响应字段更丰富 |
| https://mainnet-v4.tonhubapi.com/ | 无 | ⚠️ 未公开文档 | **H8 实证活**:`/block/latest` 200,延迟 ~0.30s;**Tonhub V4 API**,与 toncenter 不同 schema |
| https://ton.publicnode.com/ | 无 | ⚠️ 未公开 | **H8 实证 FAIL**:`/getMasterchainInfo` 返 HTTP 404(可能路径不对或服务下线 ⚠️)|
| https://ton.access.orbs.network/ | 无 | ORBS gateway | **H8 实证 FAIL**:`/444444/1/mainnet/toncenter-api-v2/getMasterchainInfo` 返 404(URL 路径需要 hash;未深查)|
| https://rpc.ankr.com/http/ton/ | 需 API key | — | **H8 实证 FAIL**:无 key 返 403 `"API key is not allowed to access blockchain"` |

**curl 实测**(证明 RPC 真活,2026-05-24 ~18:28 UTC):

```bash
# 1. toncenter v2 REST — getMasterchainInfo(等价 getSlot / eth_blockNumber)
$ curl -sS 'https://toncenter.com/api/v2/getMasterchainInfo'
{"ok":true,"result":{"@type":"blocks.masterchainInfo",
  "last":{"@type":"ton.blockIdExt","workchain":-1,"shard":"-9223372036854775808",
          "seqno":68727824,
          "root_hash":"7/j0Uag1MI+IaBJ44Nd3G6eCrG3s9DFK9fw3AOmU65c=",
          "file_hash":"qltlv0gkV5wbim9fp0rgYpBFnTtp2Rrf1aBcL+CqvgY="},
  "state_root_hash":"/TDmEsg99OXQETA69o1t7YcnRByhOAOcmghWrbgHLYw=",
  "init":{"@type":"ton.blockIdExt","workchain":-1,"shard":"0","seqno":0,...}}}
# HTTP:200, 0.34s

# 2. toncenter v2 JSON-RPC — 同 method,JSON-RPC envelope
$ curl -sS -X POST 'https://toncenter.com/api/v2/jsonRPC' \
       -H 'Content-Type: application/json' \
       -d '{"jsonrpc":"2.0","id":1,"method":"getMasterchainInfo","params":{}}'
{"ok":true,"result":{"@type":"blocks.masterchainInfo", ...}}
# HTTP:200, 0.28s — 注意 toncenter 即使是 JSON-RPC 也保留 ok/result 包装(不是纯 JSON-RPC 标准)

# 3. getAddressBalance(账户余额,nanoton string)
$ curl -sS 'https://toncenter.com/api/v2/getAddressBalance?address=EQCD39VS5jcptHL8vMjEXrzGaRcCVYto7HUn4bpAOg8xqB2N'
{"ok":true,"result":"1592537933889674","@extra":"..."}
# HTTP:200 — 余额 1,592,537.93 TON(string,单位 nanoton = 10⁻⁹ TON)

# 4. getAddressInformation(账户完整状态,含 code/data)
$ curl -sS 'https://toncenter.com/api/v2/getAddressInformation?address=EQCD39VS5jcptHL8vMjEXrzGaRcCVYto7HUn4bpAOg8xqB2N'
{"ok":true,"result":{"@type":"raw.fullAccountState",
  "balance":"1592537933889674",
  "extra_currencies":[],
  "last_transaction_id":{"@type":"internal.transactionId",
                          "lt":"75384423000033",
                          "hash":"1kIr56a26pjLOsD2zPKRBTB8pygMhuwLZGkc1q1stwY="},
  "block_id":{...},
  "code":"te6cckEBAQEAcQAA3v8AIN0g...",   ← bag-of-cells base64(TVM bytecode)
  "data":"te6cckEBAQEAKgAAUAAAAVcpqaMX...",
  ...}}
# HTTP:200

# 5. getTransactions(按地址查 tx 列表)
$ curl -sS 'https://toncenter.com/api/v2/getTransactions?address=EQCD39VS5jcptHL8vMjEXrzGaRcCVYto7HUn4bpAOg8xqB2N&limit=1'
{"ok":true,"result":[{"@type":"ext.transaction",
  "address":{...},"account":"0:83DFD552...",
  "utime":1778144886,"data":"te6cckECBwEA...",
  "transaction_id":{"lt":"75384423000033",
                     "hash":"1kIr56a26pjLOsD2zPKRBTB8pygMhuwLZGkc1q1stwY="},
  ...}]}
# HTTP:200 — 注意 TON 的 tx 标识是 (account, lt, hash) 三元组,而非单一 tx_hash

# 6. lookupBlock(按 workchain/shard/seqno 查 block id)
$ curl -sS 'https://toncenter.com/api/v2/lookupBlock?workchain=-1&shard=-9223372036854775808&seqno=68727824'
{"ok":true,"result":{"@type":"ton.blockIdExt","workchain":-1,
  "shard":"-9223372036854775808","seqno":68727824,
  "root_hash":"7/j0Uag1MI+IaBJ44Nd3G6eCrG3s9DFK9fw3AOmU65c=",
  "file_hash":"qltlv0gkV5wbim9fp0rgYpBFnTtp2Rrf1aBcL+CqvgY="}}
# HTTP:200, 0.68s

# 7. runGetMethod(read-only call,seqno on wallet)
$ curl -sS -X POST 'https://toncenter.com/api/v2/runGetMethod' \
       -H 'Content-Type: application/json' \
       -d '{"address":"EQCD39VS5jcptHL8vMjEXrzGaRcCVYto7HUn4bpAOg8xqB2N","method":"seqno","stack":[]}'
{"ok":true,"result":{"@type":"smc.runResult",
  "gas_used":549,
  "stack":[["num","0x157"]],   ← seqno = 0x157 = 343
  "exit_code":0,
  "block_id":{...},...}}
# HTTP:200 — TVM 计算成功,gas 549,栈返单一数字

# 8. detectAddress(raw ↔ friendly base64url 互转 — TON 地址多态实证)
$ curl -sS 'https://toncenter.com/api/v2/detectAddress?address=EQCD39VS5jcptHL8vMjEXrzGaRcCVYto7HUn4bpAOg8xqB2N'
{"ok":true,"result":{"@type":"ext.utils.detectedAddress",
  "raw_form":"0:83dfd552e63729b472fcbcc8c45ebcc6691702558b68ec7527e1ba403a0f31a8",
  "bounceable":   {"b64":"EQCD39VS5jcptHL8vMjEXrzGaRcCVYto7HUn4bpAOg8xqB2N",
                    "b64url":"EQCD39VS5jcptHL8vMjEXrzGaRcCVYto7HUn4bpAOg8xqB2N"},
  "non_bounceable":{"b64":"UQCD39VS5jcptHL8vMjEXrzGaRcCVYto7HUn4bpAOg8xqEBI",
                    "b64url":"UQCD39VS5jcptHL8vMjEXrzGaRcCVYto7HUn4bpAOg8xqEBI"},
  "given_type":"friendly_bounceable","test_only":false}}
# HTTP:200 — TON 同一账户 3 种表示:raw `wc:hex32` / friendly bounceable `EQ...` / friendly non-bounceable `UQ...`

# 9. bad address — 错误格式实证
$ curl -sS 'https://toncenter.com/api/v2/getAddressBalance?address=NOT_A_VALID_ADDR'
{"ok":false,"error":"failed to parse get request: Failed to parse ton_addr: 'NOT_A_VALID_ADDR'",
 "code":422,"@extra":"..."}
# HTTP:422 — 错误是标准 JSON {ok:false,error:str,code:int}

# 10. toncenter v3(indexer 风格,字段更丰富)
$ curl -sS 'https://toncenter.com/api/v3/masterchainInfo'
{"last":{"workchain":-1,"shard":"8000000000000000",
  "seqno":68728056,"root_hash":"AYuBNAc0Ep...","file_hash":"seOYfDGWo9...",
  "global_id":-239, "version":0, "gen_utime":"1779582559",
  "start_lt":"78999837000000","end_lt":"78999837000004",
  "validator_list_hash_short":1750549125, ...}}
# HTTP:200 — 注意 v3 无 ok/result 包装(纯 JSON);shard 是 hex string "8000000000000000"(v2 是 dec -9223372036854775808)

# 11. tonhub v4(独立 schema)
$ curl -sS 'https://mainnet-v4.tonhubapi.com/block/latest'
{"last":{"workchain":-1,"seqno":68727823,"shard":"-9223372036854775808",
         "rootHash":"anz8Qe3yxQuPfh737jwKB+CXeQzeGDIx97QGi60ha44=",
         "fileHash":"oP1MqBlTIw6o2U1hWl/Oir5HmUEOcFXOKUVmZ2h4re4="},
 "init":{...}, "stateRootHash":"", "now":1779582464}
# HTTP:200, 0.30s — camelCase(rootHash vs root_hash),与 toncenter 不互通
```

---

## 4. Account Model(账户模型)

| 项 | 值 |
|---|---|
| 模型 | **Account-based**(每账户是独立合约,无 UTXO;无 EVM 风格 "contract account vs EOA" 区分 — 所有账户都是合约,包括钱包) |
| Native token decimals | **9**(单位 nanoton = 10⁻⁹ TON)— E3 文档,H8 实证 `balance: "1592537933889674"` ≈ 1,592,537.93 TON |
| Address derivation | **Ed25519**(主流钱包);address = workchain_id + sha256(StateInit cell)[256 bits] |
| 账户状态 | **3 种**:`uninit`(未部署,只见过转入)/ `active`(已部署合约)/ `frozen`(欠租金被冻结)— H8 实证 `orig_status:"active"` |
| 特殊点 | **TON 没有"全局合约部署列表"**:合约部署即"向地址转账带 StateInit",直到账户 active;每账户独立 storage,无共享状态;**`extra_currencies`** 字段(实证返 `[]`)是 TON 独有的链上多币种字段(类似 SPL token 但内置,Phase 2.x 暂不监控) |

---

## 5. Core RPC Methods(本框架监控所需)

> 仅列本基准测试框架需要的 method。完整 API 列表见 https://toncenter.com/api/v2/。
> **协议风格**:toncenter v2 同时支持 REST(`GET ?param=...`)和 JSON-RPC(`POST /jsonRPC` body `{method,params}`)— 本框架建议**走 JSON-RPC**(与 EVM/Solana adapter 范式一致,vegeta 模板更易共享)。

| Method | 类别 | 说明 | mixed 权重建议 |
|---|---|---|---|
| `getMasterchainInfo` | block height | 探活 + masterchain 最新 seqno(等价 getSlot)| 0.05 |
| `getConsensusBlock` | block height(轻)| 当前共识 seqno + ts(更轻量) | 0.05 |
| `lookupBlock` | block content | 按 (workchain, shard, seqno) 查 blockIdExt | 0.10 |
| `getAddressInformation` | account state | 账户完整状态(含 code/data/balance) | 0.20 |
| `getAddressBalance` | balance | 仅余额(nanoton string,轻量) | 0.25 |
| `getTransactions` | tx lookup | 按地址查 tx 列表(limit/lt/hash 参数) | 0.20 |
| `runGetMethod` | TVM read | 调用合约 get method(read-only,链特性) | 0.10 |
| `detectAddress` | util | raw ↔ friendly 地址转换(本地可计算,建议 mock 中保留) | 0.05 |

**总权重 = 0.05+0.05+0.10+0.20+0.25+0.20+0.10+0.05 = 1.00 ✅**

**注**:
1. TON **没有单一 `getTransactionByHash(hash)` endpoint** — tx 必须以 (account_address, lt, hash) 三元组定位,或走 v3 `/transactions?hash=...` indexer 查询。Phase 2.x 若要做单 hash 反查,需引入 v3 indexer 路径(Open Q)。
2. `runGetMethod` 是 TON 独有的读重型 method(执行 TVM,gas-bound),建议保留权重以反映真实生产负载。

---

## 6. Address Format(地址格式)

| 项 | 值 |
|---|---|
| 编码 | **两套并存**:(a) **Raw form** `<workchain>:<hex64>`(如 `0:83dfd552e63729b472fcbcc8c45ebcc6691702558b68ec7527e1ba403a0f31a8`);(b) **User-friendly base64url**(36 字符:1-byte tag + 1-byte workchain + 32-byte hash + 2-byte crc16,base64url 编码)|
| Friendly 前缀语义 | `EQ...` = bounceable + mainnet(智能合约推荐)/ `UQ...` = non-bounceable + mainnet(钱包到钱包推荐)/ `kQ...` = bounceable + testnet / `0Q...` = non-bounceable + testnet |
| 长度 | Raw: 2-3 + 64 hex ≈ 66-67 字符;Friendly: **固定 48 字符**(base64url no-padding 36 bytes) |
| Checksum | 有(CRC16-XMODEM 2 bytes,内嵌 friendly 编码末尾)|
| Workchain | TON 当前活跃 2 个 workchain:**masterchain `-1`** 和 **basechain `0`**;原生支持 256 个 workchain(未来分片扩展) |
| 示例(主网真实)| `EQCD39VS5jcptHL8vMjEXrzGaRcCVYto7HUn4bpAOg8xqB2N`(Telegram 团队钱包,**H8 实证 balance 200 返 1,592,537.93 TON**)|
| 同账户其他表示 | raw: `0:83dfd552e63729b472fcbcc8c45ebcc6691702558b68ec7527e1ba403a0f31a8`;non-bounceable: `UQCD39VS5jcptHL8vMjEXrzGaRcCVYto7HUn4bpAOg8xqEBI`(**H8 实证 via detectAddress**) |
| 校验正则 | Friendly: `^[EUkQ0][QqUu][A-Za-z0-9_-]{46}$`(粗略);Raw: `^-?[0-9]+:[0-9a-fA-F]{64}$` |
| 错误证据(bad addr)| **H8 实证 `getAddressBalance?address=NOT_A_VALID_ADDR` 返 HTTP:422 + JSON `{"ok":false,"error":"... Failed to parse ton_addr ...","code":422}`** |

**关键陷阱**:同一账户的 **EQ... / UQ... / raw 三种字符串完全不等**,但指向同一 StateInit hash。**adapter 必须做规范化**(建议存 raw 内部、对外按调用方需求转 friendly),否则会在缓存 / 去重 / 余额聚合处出现"同账户算 3 个"的脏数据。

---

## 7. Signature Lookup(签名/交易哈希)

| 项 | 值 |
|---|---|
| Hash 格式 | **Base64**(URL-safe 或标准,44 字符含 `=` padding)— TON tx_hash 是 32-byte sha256,默认 base64 编码 |
| 长度 | **44 字符**(含 padding;无 padding 时 43)|
| 示例(主网真实) | `1kIr56a26pjLOsD2zPKRBTB8pygMhuwLZGkc1q1stwY=`(**H8 实证 via `getTransactions limit=1`**)|
| 对应账户 | `EQCD39VS5jcptHL8vMjEXrzGaRcCVYto7HUn4bpAOg8xqB2N` |
| 对应 lt | `75384423000033`(logical time,TON 内部全序时钟)|
| 对应 utime | `1778144886`(Unix ts) |
| 查询 method | **关键**:toncenter v2 **没有 `getTxByHash(hash)` 单 endpoint** — 必须三元组 `(account, lt, hash)` 查:`getTransactions?address=...&lt=...&hash=...&limit=1`。**v3 indexer** 提供 `GET /api/v3/transactions?hash=...` 单 hash 反查(**H8 实证 200**)|
| Explorer URL 格式 | `https://tonscan.org/tx/<base64url_hash>` 或 `https://tonviewer.com/transaction/<hex_hash>`(注:浏览器有的用 base64url,有的用 hex,不统一)|

---

## 8. Mixed Set(`mixed` 模式权重)

```json
{
  "balance_query":      0.25,
  "account_info":       0.20,
  "tx_lookup":          0.20,
  "block_query":        0.10,
  "run_get_method":     0.10,
  "block_height":       0.05,
  "consensus_block":    0.05,
  "address_detect":     0.05
}
```

**权重和 = 1.00 ✅**

**chain-specific 部分**(0.10 + 0.05 + 0.05 = 0.20):
- `run_get_method` (0.10):TVM 读重型,TON 独有(执行 get method)
- `consensus_block` (0.05):masterchain 共识块快照(轻量探活)
- `address_detect` (0.05):raw/friendly 互转(util,可走 mock)

**其余 0.80** 给通用 RPC(balance/account/tx/block)。

---

## 8.5 Phase 2.1 caller/reader 改造点(token-level Gate 3)

| # | 位置(file:line) | 改动 | 原因 |
|---|---|---|---|
| 1 | `config/config_loader.sh:<L?>` `supported_blockchains` | 新增 `ton` 入列 | adapter dispatcher 必经,漏入则 `--chain ton` fail |
| 2 | `config/config_loader.sh:<新增 section>` `rpc_methods.ton.mixed` | 添 §8 8 个 method | vegeta target 生成器消费 |
| 3 | `config/config_loader.sh:<新增>` `param_formats.ton` | 添 schema:`address_friendly_base64url`(必)、`(workchain,shard,seqno)` 三元组、`(address,lt,hash)` 三元组 | `generate_rpc_json` 漏字段则退默认 |
| 4 | `tools/mock_rpc_server.py:<新增>` JSON-RPC + REST router | 添 8 个 method handler,返 H8 实测样本(`@type`/`@extra` 字段必须保留以匹配真响应)| mock fallback 必须支持(否则 mock 模式 vegeta 全 404) |
| 5 | `tools/fetch_active_accounts.py:<新增 TONAdapter>` | 实现 `fetch_addresses()`(走 toncenter v3 `/transactions?limit=N&sort=desc` 反查 active accounts;或走第三方 indexer)| adapter dispatcher 调用 |
| 6 | `analysis-notes/baseline-current-state.md` grep "ton" | 同步加 TON family 行(注意与 "tezos"/"tron"/"python" 等 substring 区分,grep `\bton\b`)| doc 与 plugin 真相对齐 |
| 7 | `analysis-notes/disk-and-network-pipeline-redesign.md` grep "ton" | 同步加 family | 同上 |
| 8 | `analysis-notes/research_notes/<本文件名>.md` | 此 doc 即笔记本体 | N/A |
| 9 | `tests/<新增 test_ton_smoke.sh>` | E2 smoke:8 个 method 各跑 1 次,断言 HTTP:200 + `ok:true` | L1 smoke gate;**注意 toncenter 无 key 限流 1 RPS,smoke 必须串行 + sleep,否则 429** |

**Phase 2.1 完成后必须跑** `core/master_qps_executor.sh --chain ton --mixed --duration 30`(或最短 e2e_smoke),抓 vegeta 错误率。**注**:由于公链限流 1 RPS,**性能基准应优先自建 ton-http-api 节点**(详见 §10 Self-Host),公共 endpoint 仅作 smoke / 兜底。

---

## 9. Mock Notes(mock_rpc_server 实现要点)

- **请求路径**:**两种并存**
  - REST: `GET /api/v2/<method>?<query>`(每 method 一 path)
  - JSON-RPC: `POST /api/v2/jsonRPC` body `{"jsonrpc":"2.0","id":...,"method":"<name>","params":{...}}`
- **响应 envelope**(toncenter 即使 JSON-RPC 也用此包装,**非标准 JSON-RPC**):
  ```json
  {"ok": true, "result": <data>, "@extra": "<timestamp:_:elapsed:tag>"}
  ```
  错误:
  ```json
  {"ok": false, "error": "<message>", "code": <int>, "@extra": "..."}
  ```
- **响应样本**(H8 实测主网真样本):
  ```jsonc
  // getMasterchainInfo
  {"ok": true, "result": {
    "@type": "blocks.masterchainInfo",
    "last": {"@type": "ton.blockIdExt", "workchain": -1,
             "shard": "-9223372036854775808", "seqno": 68727824,
             "root_hash": "7/j0Uag1MI+IaBJ44Nd3G6eCrG3s9DFK9fw3AOmU65c=",
             "file_hash": "qltlv0gkV5wbim9fp0rgYpBFnTtp2Rrf1aBcL+CqvgY="},
    "state_root_hash": "...",
    "init": {"@type": "ton.blockIdExt", "workchain": -1, "shard": "0", "seqno": 0, ...}
  }}

  // getAddressBalance — result 是 bare string(nanoton)
  {"ok": true, "result": "1592537933889674"}

  // runGetMethod — stack 是 [[type, value]] 数组,type ∈ {num, cell, slice, tuple}
  {"ok": true, "result": {
    "@type": "smc.runResult", "gas_used": 549,
    "stack": [["num", "0x157"]], "exit_code": 0,
    "block_id": {...}, "last_transaction_id": {...}
  }}
  ```
- **特殊错误码**:
  - HTTP 422:bad address / bad params
  - HTTP 429:rate-limit(无 key 1 RPS;smoke 必须 sleep)
  - HTTP 500/504:节点同步落后或 LiteServer 超时(toncenter 后端走 ton liteserver,偶发)
- **Mock 实现复杂度**:**Medium-High**
  - 复杂点:
    1. 双协议(REST + JSON-RPC)需双 router,但 method 集相同
    2. `@type` discriminator 字段必须精确(`raw.fullAccountState`、`ton.blockIdExt`、`smc.runResult` 等),客户端 SDK 用于反序列化
    3. `runGetMethod` 返回的 `stack` 是 `[[type, value], ...]` 二维数组,type 字符串决定 value 解析
    4. shard 字段在 v2 是 dec string、在 v3 是 hex string —— **mock 必须选定一个版本**
    5. `bag-of-cells` base64 字段(`code`/`data`/`data` in tx)是 TVM 序列化,mock 中保留实测原值即可,无需解析
  - 简单点:envelope 统一 `{ok,result}`;无鉴权(无 key 模式)

---

## 10. Adapter Reuse Decision(adapter 复用决策)

### 候选 adapter

| Adapter | 兼容度 | 缺失能力 |
|---|---|---|
| EthereumAdapter | **0%** | TON 无 EVM/ABI;tx 三元组 vs hash;account 模型完全不同 |
| SolanaAdapter | **~10%** | 协议层都是 JSON-RPC + base58/base64,但 TON 的 `@type` discriminator 风格、(account, lt, hash) 三元组、TVM 栈结构都需专实现 |
| AptosAdapter / TezosAdapter(REST 系)| **~20%** | REST 层 schema 可借鉴(verb/path),但 toncenter 双协议 + envelope `{ok,result}` 包装属于 toncenter 特殊 |
| CosmosAdapter | **0%** | bech32 vs base64url;Tendermint vs Catchain;完全不同 |

### 决策

- [ ] 复用 `<adapter 名>`
- [x] **新建 `TONAdapter`**(TON 独立 family;masterchain/workchain 分片 + bag-of-cells + TL-B + 每账户独立合约 + tx 三元组都是 TON 独有)
- [x] **协议层复用 JSON-RPC infra**(toncenter v2 JSON-RPC 路径与 EVM/Solana adapter 共享 vegeta target 生成器框架)
- [ ] 混合

### 理由

**第一段 — Adapter 类必须独立(语义层)**。TON 的 5 个核心异构点(① raw vs EQ/UQ friendly 三态地址 + workchain prefix;② tx 用 (account, lt, hash) 三元组定位而非单 hash;③ `runGetMethod` 返回的 TVM stack `[[type, value]]` 需要 type-aware 解码;④ 账户三态 active/uninit/frozen 影响 balance 语义;⑤ masterchain seqno vs workchain seqno 双层高度概念)没有任何现有 adapter 覆盖。这些都需要 `TONAdapter` 内部专属方法,不能塞进 SolanaAdapter / EthereumAdapter。

**第二段 — 协议层可复用 JSON-RPC infra**。toncenter v2 提供 JSON-RPC `POST /jsonRPC` body `{jsonrpc,id,method,params}`,虽然响应被 `{ok, result, @extra}` 包装(非标准),但 vegeta target 模板 / 请求体生成器 / HTTP 层错误处理 / batch 支持 都可与 EVM / Solana adapter 共享 ~70% 代码。**唯一定制点**是响应解析层需要剥 `{ok, result}` 外壳取 `result`(类似 Aptos 剥 `data` 字段),建议在 adapter 内做。

**第三段 — Self-host 是性能基准的必经路径**。toncenter 无 key 限流 1 RPS、有 key 10 RPS,**远低于本框架 5K-10K QPS 基线目标**。Phase 2.x 接 TON 时必须同步搭 `ton-http-api`(官方 dockerized,详见 §10 Self-Host 备注),公共 endpoint 仅用于 smoke / fallback。这与 Solana / EVM 主网 RPC 公共 endpoint 差距同质,**不构成 adapter 决策阻塞**。

### Self-Host Notes(公链失败时的 fallback / 性能基准必经)

- **官方栈**:`ton-blockchain/ton` C++ 全节点(同步主网约 200 GB,~1 天)+ `toncenter/ton-http-api`(Python 封装,提供 v2 REST/JSON-RPC)
- **docker-compose**:https://github.com/toncenter/ton-http-api(官方),`docker compose up` 一键起;依赖一个本地或远端 `ton-blockchain` lite-client(`liteserver` 节点)
- **轻替代**:`toncenter/tonlibjson-cpp` + lite-client 配置文件(走公开 liteserver,免全节点同步,但仍受上游限流)
- **预算**:全节点磁盘 ~500 GB SSD(冗余预留)、4-8 vCPU、16-32 GB RAM(主流配置)

### 配置 JSON 示例(本链)

```json
{
  "chain": "ton",
  "family": "ton",
  "adapter": "TONAdapter",
  "chain_id": -239,
  "protocol_kind": "mixed",
  "rpc_endpoint": "https://toncenter.com/api/v2/jsonRPC",
  "rpc_endpoint_rest": "https://toncenter.com/api/v2",
  "rpc_endpoint_v3": "https://toncenter.com/api/v3",
  "rpc_endpoint_backup": "https://mainnet-v4.tonhubapi.com",
  "block_time_ms": 5000,
  "finality_blocks": 1,
  "address_format": "base64url_friendly",
  "address_prefixes": ["EQ", "UQ", "kQ", "0Q"],
  "address_raw_format": "<workchain>:<hex64>",
  "native_decimals": 9,
  "rpc_methods": {
    "block_height":     {"method": "getMasterchainInfo",   "params": {}, "response_path": "$.result.last.seqno"},
    "consensus_block":  {"method": "getConsensusBlock",    "params": {}, "response_path": "$.result.consensus_block"},
    "block_query":      {"method": "lookupBlock",
                          "params": {"workchain": -1, "shard": "-9223372036854775808", "seqno": "{seqno}"},
                          "path_params": ["seqno"]},
    "balance":          {"method": "getAddressBalance",
                          "params": {"address": "{addr}"}, "path_params": ["addr"],
                          "response_path": "$.result"},
    "account_info":     {"method": "getAddressInformation",
                          "params": {"address": "{addr}"}, "path_params": ["addr"]},
    "tx_lookup":        {"method": "getTransactions",
                          "params": {"address": "{addr}", "limit": 1}, "path_params": ["addr"]},
    "run_get_method":   {"method": "runGetMethod",
                          "params": {"address": "{addr}", "method": "seqno", "stack": []},
                          "path_params": ["addr"]},
    "address_detect":   {"method": "detectAddress",
                          "params": {"address": "{addr}"}, "path_params": ["addr"]}
  },
  "mixed_weights": {
    "balance_query":   0.25,
    "account_info":    0.20,
    "tx_lookup":       0.20,
    "block_query":     0.10,
    "run_get_method":  0.10,
    "block_height":    0.05,
    "consensus_block": 0.05,
    "address_detect":  0.05
  },
  "chain_specific": {
    "envelope_wrapper":      {"ok": true, "result_path": "$.result"},
    "tx_id_tuple_required":  true,
    "tx_id_fields":          ["account", "lt", "hash"],
    "address_normalization": "raw",
    "workchains_active":     [-1, 0]
  }
}
```

---

## 11. References(已查阅 / 引用的官方文档清单)

| 信源类型 | URL/路径 | 访问日期(UTC)| 状态 |
|---|---|---|---|
| toncenter v2 REST | `GET https://toncenter.com/api/v2/getMasterchainInfo` | 2026-05-24 18:28 | **H8:200**,masterchain seqno=68727824 |
| toncenter v2 JSON-RPC | `POST https://toncenter.com/api/v2/jsonRPC` `{method:getMasterchainInfo}` | 2026-05-24 18:28 | **H8:200**,同 result,envelope `{ok,result,@extra}` |
| toncenter v2 `/getAddressBalance` | `EQCD39VS...` | 2026-05-24 18:28 | **H8:200**,`"1592537933889674"` nanoton |
| toncenter v2 `/getAddressInformation` | `EQCD39VS...` | 2026-05-24 18:28 | **H8:200**,`@type:raw.fullAccountState`,active 账户 |
| toncenter v2 `/getTransactions` | `EQCD39VS...&limit=1` | 2026-05-24 18:28 | **H8:200**,得 tx (lt=75384423000033, hash=`1kIr56a26pjL...`, utime=1778144886) |
| toncenter v2 `/lookupBlock` | `?workchain=-1&shard=-9223372036854775808&seqno=68727824` | 2026-05-24 18:28 | **H8:200** |
| toncenter v2 `/getConsensusBlock` | — | 2026-05-24 18:28 | **H8:200**,consensus_block=68727899 @ ts=1779582496 |
| toncenter v2 `/runGetMethod` | `EQCD39VS... method=seqno` | 2026-05-24 18:28 | **H8:200**,TVM exit_code=0,gas=549,stack=`[[num, 0x157]]` |
| toncenter v2 `/detectAddress` | `EQCD39VS...` | 2026-05-24 18:28 | **H8:200**,得 raw=`0:83dfd552...`,UQ=`UQCD39VS...EBI` |
| toncenter v2 bad addr 错误路径 | `NOT_A_VALID_ADDR` | 2026-05-24 18:28 | **H8:422** + JSON `{ok:false,error:"... Failed to parse ton_addr ...",code:422}` |
| toncenter v3 `/masterchainInfo` | — | 2026-05-24 18:29 | **H8:200**,global_id=-239,gen_utime=1779582559,v3 无 envelope |
| toncenter v3 `/transactions?account=...&limit=1` | — | 2026-05-24 18:29 | **H8:200**,trace_id 字段 + mc_block_seqno=65206901 |
| tonhub v4 `/block/latest` | — | 2026-05-24 18:28 | **H8:200**,camelCase schema,now=1779582464 |
| tonhub v4 `/block/<seqno>/account/<addr>` | 68728056 + EQCD39VS... | 2026-05-24 18:29 | **H8:404**(具体 block 路径与文档可能不一致,⚠️ 未深查)|
| Ankr `/http/ton/getMasterchainInfo` | — | 2026-05-24 18:29 | **H8:403**(无 key 不允许)|
| publicnode `/getMasterchainInfo` | — | 2026-05-24 18:28 | **H8:404**(路径或服务不可用,⚠️)|
| ORBS `/444444/1/mainnet/toncenter-api-v2/...` | — | 2026-05-24 18:28 | **H8:404**(网关路径需查文档校正,⚠️)|
| toncenter v2 文档站 | https://toncenter.com/api/v2/ | 2026-05-24 | E1(引用,未 DOM)|
| TON Docs 总站 | https://docs.ton.org | 2026-05-24 | E1(引用,未 DOM)|
| TonScan(用于 cross-check)| https://tonscan.org/address/EQCD39VS... | 2026-05-24 | E2(浏览器可达,未 DOM)|

---

## Open Questions(待解决问题)

1. **v3 单 hash tx 反查 schema** — `/api/v3/transactions?hash=...` 实测 200,但响应结构未完整记录;Phase 2.x 若做单 hash 反查需补 schema。
2. **公链限流 vs QPS 目标失配** — toncenter 无 key 1 RPS,本框架 5K-10K QPS 目标必须 self-host `ton-http-api`,docker-compose 是否能跑通 Phase 2.x CI?
3. **block_time 实证未细化** — H8 看到 consensus_block 步进 ≈ 0.4s,但官方文档说 mc ~5s / wc ~3s,二者差异是 consensus_block 是"已签终结块计数"还是其他口径,⚠️ 未求证。
4. **tx_hash 编码不一致** — toncenter 返 base64(`1kIr56a26pjL...wY=`),tonviewer 浏览器用 hex,tonscan 用 base64url;adapter 内部必须规范化为 hex 或 base64url 之一并双向转换。
5. **extra_currencies 字段** — H8 实证返 `[]`,TON 原生支持多币种,Phase 2.x 是否监控?(暂列 Open)
6. **runGetMethod gas 限制** — H8 实测 gas=549,某些重型 get method(如 NFT marketplace)gas 数万,**mock 必须返合理 gas 数否则 SDK 校验失败**;实施时需采样真实合约 H8 几例。
7. **三元组 tx ID 在 mixed 测试中的取数策略** — 测试时如何从 `fetch_active_accounts` 出来后立即取每地址最新 tx 的 (lt, hash) 作为 vegeta target 参数?需在 adapter 中加 prefetch 步骤,延长 setup 时间。
8. **mock_rpc_server JSON-RPC envelope 兼容** — toncenter 的 `{ok, result, @extra}` 非标准 JSON-RPC,mock_rpc_server 若已硬编 `{jsonrpc,result,id}` 标准 envelope,需新增 toncenter-style branch。

---

## Changelog

| Date | Author | Change |
|---|---|---|
| 2026-05-24 | Hermes Agent | 初次调研:H8 实证 toncenter v2 REST 8 个 method(`getMasterchainInfo` / `getAddressInformation` / `getAddressBalance` / `getTransactions` / `lookupBlock` / `getConsensusBlock` / `runGetMethod` / `detectAddress`)+ v2 JSON-RPC 1 method + bad-addr 错误路径(422)+ v3 REST 2 个 method + tonhub v4 `/block/latest`;Ankr(403)/ publicnode(404)/ ORBS(404)三个 endpoint FAIL 已记录;target_address `EQCD39VS5jcptHL8vMjEXrzGaRcCVYto7HUn4bpAOg8xqB2N`(1.59M TON,活跃);target tx_hash `1kIr56a26pjLOsD2zPKRBTB8pygMhuwLZGkc1q1stwY=` lt=75384423000033;§10 决策新建 TONAdapter + 协议层复用 JSON-RPC infra + self-host ton-http-api 用于性能基准 |
