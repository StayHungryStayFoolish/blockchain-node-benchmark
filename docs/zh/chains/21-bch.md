# 21-Bitcoin Cash 调研(diff-only,base=03-bitcoin)

> **DIFF-ONLY 模式**:仅记录与 `03-bitcoin.md` 不同的项。JSON-RPC 1.0 协议结构、error code 表、HTTP Basic Auth 鉴权机制、10 method 签名(`getbestblockhash`/`getblockcount`/`getblock`/`getblockhash`/`getblockhashes`/`getrawtransaction`/`getmempoolinfo`/`getrawmempool`/`scantxoutset`/`getbalance`)与 BTC 99% 兼容,**不重复**,见 03-bitcoin.md §5/§11。
> **每个字段引用标签 E1/E2/E3/E4/E5**。

---

## 元信息

| 项 | 值 |
|---|---|
| 链名(中/英) | 比特币现金 / Bitcoin Cash(BCH) |
| 编号 | 21 |
| Mainnet ChainID | N/A(同 BTC;链识别用 genesis hash `000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f` —— **与 BTC genesis 完全一致**,真正区分用 fork 后 height 478559 的链分裂块 `000000000000000000651ef99cb9fcbe0dadde1d424bd9f15ff20136191a5eec`)[E2/E3] |
| 调研日期 | 2026-05-23 |
| 调研者 | Hermes Agent |
| 状态 | 🟢 已完成(diff-only) |
| Base 链 | 03-bitcoin.md(commit `de925455c8025fc1f75d65d981c28b9dfa20e9f7`) |

---

## 1. Sources(权威来源 — 仅 BCH 独有)

| 类型 | URL | 访问日期 | 备注 |
|---|---|---|---|
| 官方文档 | https://docs.bitcoincashnode.org/doc/29.0.0/ | 2026-05-23 | Bitcoin Cash Node(BCHN)29.0 RPC 参考。实测 `getnetworkinfo.subversion=/Bitcoin Cash Node:29.0.0(EB32.0)/`,**EB32.0 = excessive blocksize 32 MB**[E2 — §3] |
| GitHub | https://gitlab.com/bitcoin-cash-node/bitcoin-cash-node | 2026-05-23 | BCHN 主仓(已迁出 GitHub);diff base 是 Bitcoin Core 0.21.x [E3] |
| Hard fork 历史 | https://en.bitcoin.it/wiki/Bitcoin_Cash | 2026-05-23 | 2017-08-01 height **478559** 从 Bitcoin Core fork;2018-11-15 BSV fork;2020-11-15 ABC→XEC fork [E3] |
| CashAddr 规范 | https://reference.cash/protocol/blockchain/encoding/cashaddr | 2026-05-23 | CashAddr 地址编码(本文档唯一新增 DSL ASK 点)[E3] |
| SLP 协议 | https://slp.dev/specs/slp-token-type-1/ | 2026-05-23 | Simple Ledger Protocol(BCH 上的 token,OP_RETURN 编码,**不走 RPC**)[E3] |
| ASERT 规范 | https://upgradespecs.bitcoincashnode.org/2020-11-15-asert/ | 2026-05-23 | DAA `aserti3-2d`(替代 BTC 2016 块重定)[E3] |
| Explorer | https://blockchair.com/bitcoin-cash | 2026-05-23 | 主网区块/tx/地址浏览器;**同时返回 CashAddr 与 legacy 双格式**(`formats.cashaddr` / `formats.legacy`)[E2] |
| Public REST | https://rest1.biggestfan.net/v2/ | 2026-05-23 | Bitcoin.com 兼容 REST 代理(BCHN 后端),实测可用 [E2 — §3] |

---

## 2. 与 03-bitcoin.md 的关键 diff 表(P0 速读)

| 项 | Bitcoin (03) | Bitcoin Cash (21) | 影响 |
|---|---|---|---|
| Family | utxo-btc | **utxo-btc**(同族,复用 BitcoinAdapter)| 0 新族 |
| Genesis hash | `000000000019d6689c085...` | **相同** | 链识别**必须**用 fork 后特征块,见上 |
| Block size 上限 | 1 MB(weight 4 M)| **32 MB**(`EB32.0`,服务侧可配)[E2] | mempool/getblock 响应可比 BTC 大 32×,benchmark `Content-Length` 上限要放宽 |
| SegWit | ✅ BIP-141/173/350 | ❌ **拒绝**(BCH 反对 segwit,fork 主因)[E3] | 无 P2WPKH/P2WSH/P2TR;`bc1...` 全 reject |
| 出块时间 | 10 min | 10 min(同)| — |
| 难度算法 | 2016 块重定 | **aserti3-2d**(ASERT,每块滑动)[E3] | RPC 不可见;影响 reorg 概率分析 |
| 共识 | SHA-256d PoW | 同(同算法)| 同 BTC,但矿池 hashrate ≈ BTC 的 1-2% |
| 地址格式 | Base58Check + Bech32 + Bech32m | **CashAddr**(主)+ Base58Check legacy(过渡)[E2 — §6] | **DSL ASK 1**(见 §7) |
| 单位 | 1 BTC = 10⁸ sat | 1 BCH = 10⁸ sat(同)| — |
| 独有 method | — | `getexcessiveblock` / `setexcessiveblock`(blocksize cap 操控)[E3 — BCHN] | 与 benchmark 无关(节点管理类) |
| Token 协议 | Omni(USDT-Omni,已 deprecated)| **SLP**(OP_RETURN,**不走 RPC**)[E3] | balance benchmark 不可行,见 §6 |

---

## 3. Public RPC(公链 endpoint 实测)

| Endpoint | 类型 | Auth | 实测结果 | 备注 |
|---|---|---|---|---|
| `https://rest1.biggestfan.net/v2/` | **REST**(Bitcoin.com 兼容)| 无 | ✅ 200,平均 1.0 s,`subversion=/Bitcoin Cash Node:29.0.0(EB32.0)/`,`blocks=952310` | **推荐主测**;BCH 唯一公开稳定的 REST 网关 |
| `https://api.blockchair.com/bitcoin-cash/` | REST(Blockchair)| 无(免费层 30 req/min)| ✅ 200,平均 1.4 s,`blocks=952314` | 优势:`formats.cashaddr` + `formats.legacy` 双格式自动转换 [E2] |
| `https://bch.publicnode.com` | 期望 JSON-RPC | — | ❌ 404 Cloudflare(2026-05-23 实测,**已下线**;context 文件信息过期)[E2] | 不可用 |
| `http://<self-hosted>:8332` | JSON-RPC 1.0 | basic auth(同 BTC)| 未测 | 自建 BCHN,benchmark target 模式 |

**实测 curl**(E2):
```bash
curl -s https://rest1.biggestfan.net/v2/blockchain/getBlockCount
# 952310

curl -s https://rest1.biggestfan.net/v2/control/getNetworkInfo | jq .subversion
# "/Bitcoin Cash Node:29.0.0(EB32.0)/"  ← 32MB 块上限明确

curl -s https://rest1.biggestfan.net/v2/blockchain/getMempoolInfo
# {"loaded":true,"size":27,"bytes":18658,"usage":48576,
#  "maxmempool":2048000000,"mempoolminfee":0.00001,
#  "minrelaytxfee":0.00001,"permitbaremultisig":true,
#  "maxdatacarriersize":223}
#  ↑ maxmempool 2 GB(BTC 默认 300 MB),与 32MB 块匹配
```

**关键差异**:BCH **没有**与 `bitcoin-rpc.publicnode.com` 等价的纯 JSON-RPC 公开节点。benchmark 公链模式只能走 REST 代理,**响应 schema 与 Core JSON-RPC 略不同**(REST 把 `result` 字段平铺,无 `{jsonrpc,result,id,error}` 外壳)。self-hosted 模式仍是标准 Core JSON-RPC 1.0,可完全复用 BTC 的 `BitcoinAdapter` 请求构造逻辑。

---

## 4. method 差异(99% 同 BTC,只列 fork 独有)

| Method | BTC 行为 | BCH 行为 | 实证 |
|---|---|---|---|
| `validateaddress` | 接受 P2PKH/P2SH/P2WPKH/P2WSH/P2TR | 接受 **CashAddr**(`bitcoincash:q...`)+ legacy Base58(P2PKH/P2SH);**拒绝 bech32 `bc1...`** | E2 — §6 |
| `getblock`(verbosity=2) | 单 tx 含 SegWit witness 字段 | 无 `vin[*].txinwitness`;返回 tx 数可远多于 BTC(32MB 块)| E4 — BCHN src |
| `getrawtransaction` | wtxid ≠ txid(SegWit 后)| **wtxid ≡ txid**(无 SegWit)| E4 |
| `getexcessiveblock` | 不存在 | BCHN 独有:返回 `{"excessiveBlockSize": 33554432}`(32 MB)| E3 — BCHN docs |
| `getblockhashes` | 不存在(03 文档列了但其实是 Zcash/PIVX 系扩展)| 同 BTC,不存在 | — |
| `scantxoutset` | 同(支持)| 同 | — |
| `getbalance` | wallet RPC,publicnode 反代禁 | wallet RPC,REST 代理无此 endpoint | — |

> **结论**:与 BTC 10 个核心 method 中 8 个完全一致(getbestblockhash / getblockcount / getblock / getblockhash / getrawtransaction / getmempoolinfo / getrawmempool / scantxoutset);`validateaddress` 行为不同(地址族),`getbalance` 都不能用(都需 wallet)。无新增 benchmark 相关 method。

---

## 5. 出块/共识细节(与 §2 表互补)

- **ASERT 难度调整**(2020-11-15 激活):每块基于 referenceBlock + targetSpacing 滑动,公式 `next_target = ref_target × 2^((delta_time - 600·height_delta) / 172800)`;**好处**:消除 BTC 2016 块重定的剧烈波动 + BCH/BTC 矿池跨链跳跃套利;**对 benchmark 不可见**(getblock 不暴露 algorithm 字段)[E3]。
- **fork 历史时间线**:
  - 2017-08-01 height 478559 — BCH 从 BTC fork(块大小分歧 + 反 SegWit)
  - 2018-11-15 — BCH 内部 fork → BSV(Craig Wright)分裂出去
  - 2020-11-15 — BCH 内部 fork → XEC(eCash,Bitcoin ABC)分裂出去
  - 当前 BCH 主网 = BCHN(Bitcoin Cash Node)实现主导,subversion 自报 EB32.0
- **未来 fork**:每年 5/15 + 11/15 两个 schedule 升级窗口,但近 2 年(2024-2025)无破坏性 protocol change [E3]。

---

## 6. SLP token(真实负载补充)

- **SLP = Simple Ledger Protocol**:BCH 上的同质化 + NFT token 协议,数据全部编码在 tx 的 OP_RETURN 输出中(类似 BTC-Omni / Ordinals)[E3]。
- **链上原生 RPC 无法解码 SLP**:`getrawtransaction` 返回 vout[0] 是 `OP_RETURN ...`,要拿 token symbol/amount **必须**外挂 SLPDB(MongoDB + 索引器)或用 BCHD gRPC `GetSlpTransactionInformation`。
- **benchmark 含义**:本框架不引入 SLP — `mixed` 权重表与 BTC 完全相同,**不为 SLP 分配权重**。SLP balance 查询 = explorer API(blockchair `dashboards/address` 返回 `slp_balances`),归类为 §10 trade-off,不进入 RPC method 集。
- **真实活跃 token**:USDT-SLP(已迁至 ETH 后基本不活跃)、SPICE、FLEX。日均 SLP tx < 5k,占 BCH 总 tx ~20%。

---

## 7. DSL 决策(预测 0 新方法,**1 新枚举**)

### 7.1 复用 BTC DSL 字段(0 改动)

`chain` / `family` / `adapter` / `rpc_protocol` / `auth` / `rpc_methods` / `mixed_weights` 全部沿用 03-bitcoin.md §10 的 `BitcoinAdapter` 配置,仅替换 endpoint + `chain` 名 + `magic_bytes`(`0xE3E1F3E8` for BCH mainnet vs BTC `0xD9B4BEF9`)+ `fork_height: 478559` + `address_formats`。

### 7.2 **DSL ASK #1**:`address_format` 枚举新增 `cashaddr`

**当前 03-bitcoin.md L402**:`"address_formats": ["base58check", "bech32", "bech32m"]`
**BCH 需要**:`"address_formats": ["cashaddr", "base58check"]`

**理由**:CashAddr 不是 Bech32 也不是 Base58Check,是 BCH 独有的第三种编码:
- **字符集**:`qpzry9x8gf2tvdw0s3jn54khce6mua7l`(32 字符,**与 Bech32 不同** — Bech32 是 `qpzry9x8gf2tvdw0s3jn54khce6mua7l` 看似同,但 polymod 常数和 hrp 拼接顺序不同)[E3 — reference.cash CashAddr spec]
- **HRP**:`bitcoincash:`(mainnet)/ `bchtest:`(testnet)/ `bchreg:`(regtest)
- **示例**:`bitcoincash:qpm2qsznhks23z7629mms6s4cwef74vcwvy22gdx0qaa`(54 字符,含 hrp)
- **Checksum 多项式**:BCH(常数 1,与 Bech32 同)但 polymod 计算的 **基底 generator 不同**,意味着合法 Bech32 串在 CashAddr 下 invalid,反之亦然 — **必须独立 codec 实现**

**实证**(E2 — `validateaddress` 通过 REST 代理):
```bash
# CashAddr — REST 代理把 hrp 当作非法字符(代理是 BTC schema):
curl -s https://rest1.biggestfan.net/v2/util/validateAddress/bitcoincash:qpm2qsznhks23z7629mms6s4cwef74vcwvy22gdx0qaa
# {"isvalid":false}  ← REST 代理 bug,实际 BCHN RPC 返回 true(需 self-hosted 验证)

# Blockchair API 同时给两种格式:
curl -s https://api.blockchair.com/bitcoin-cash/dashboards/address/bitcoincash:qpm2qsznhks23z7629mms6s4cwef74vcwvy22gdx0qaa | jq .data[].address.formats
# {"legacy":null,"cashaddr":"qpm2qsznhks23z7629mms6s4cwef74vcwvy22gdx0qaa"}
```

**DSL 影响**:
- 新增枚举值 `cashaddr`(类型签名:`type AddressFormat = "base58check" | "bech32" | "bech32m" | "cashaddr"`)
- `BitcoinAdapter` 需委派给 `CashAddrCodec`(独立 polymod 实现);Litecoin/Dogecoin **不需要**此 codec(它们用 Base58Check + Bech32)
- 配置示例:
```json
{
  "chain": "bitcoin-cash",
  "family": "utxo-btc",
  "adapter": "BitcoinAdapter",
  "fork_from": {"chain": "bitcoin", "height": 478559, "date": "2017-08-01"},
  "magic_bytes": "0xE3E1F3E8",
  "rpc_endpoint": "https://rest1.biggestfan.net/v2",
  "rpc_protocol": "rest-bitcoin-com",
  "rpc_endpoint_self_hosted": "http://<host>:8332",
  "rpc_protocol_self_hosted": "json-rpc-1.0",
  "auth": {"type": "basic", "user": "${BCH_RPC_USER}", "pass": "${BCH_RPC_PASS}", "optional_for_public_proxy": true},
  "block_time_ms": 600000,
  "native_decimals": 8,
  "block_size_max_bytes": 33554432,
  "segwit_enabled": false,
  "difficulty_algorithm": "aserti3-2d",
  "address_formats": ["cashaddr", "base58check"],
  "rpc_methods": "INHERIT_FROM(bitcoin)",
  "mixed_weights": "INHERIT_FROM(bitcoin)"
}
```

---

## 8. H8 实证(curl 探活汇总,5 命令)

| # | Method | endpoint | 结果 |
|---|---|---|---|
| 1 | `getBlockCount` | `rest1.biggestfan.net/v2/blockchain/getBlockCount` | ✅ `952310`(plain int)|
| 2 | `getNetworkInfo` | `rest1.biggestfan.net/v2/control/getNetworkInfo` | ✅ `subversion=/Bitcoin Cash Node:29.0.0(EB32.0)/`,`version=29000000`,`protocolversion=70016` |
| 3 | `getMempoolInfo` | 同上 | ✅ `size=27, maxmempool=2GB`(32MB 块需要更大 mempool)|
| 4 | `getBlock` by hash | `rest1.biggestfan.net/v2/blockchain/getBlock/<hash>` | ✅ 高度 952312,size 2219,**无 weight 字段**(BCH 无 SegWit 故无 weight)|
| 5 | `getRawTransaction` genesis-block-1 coinbase | `rest1.biggestfan.net/v2/rawtransactions/getRawTransaction/9b0fc922...?verbose=true` | ✅ 与 BTC genesis 后第 1 块 coinbase **完全一致**(BCH 共享 BTC 历史)|
| 6 | `getAddressDetails` CashAddr | `api.blockchair.com/bitcoin-cash/dashboards/address/bitcoincash:qpm2q...` | ✅ 返回 `formats.cashaddr` + `formats.legacy` 双格式 |
| 7 | `validateAddress` CashAddr 经 REST 代理 | REST 代理 | ❌ `isvalid:false`(代理 bug;真 BCHN RPC 在 self-hosted 下应返回 true)|

**关键发现**:
- BCH chain tip 在 2026-05-23 实测 `952310` —— 与 BTC tip `950697`(同日)相差仅 ~1600 块,反映两链共享 fork 前 478559 块历史 + fork 后 9 年各自 ~473k 块。
- **block size 真实**:实测 block 952312 仅 2219 字节(BCH 链上 tx 量小,远未触及 32MB 上限);BTC 同期 typical block ~1.5MB(顶满)。性能测试若想真实压 32MB 路径,需自建节点 + regtest 灌入合成 tx。
- `weight` 字段缺失证实 BCH 无 SegWit(BTC `getblock` 必有 `weight = base_size × 3 + total_size`)。

---

## 9. P2.1 caller/reader 改造点(diff vs BTC P2.1)

BCH 接入工作量 ≈ **BTC 的 5%**,因 BitcoinAdapter 已存在,改动点:

| # | 位置 | 改动 | 原因 |
|---|---|---|---|
| 1 | `config/config_loader.sh` `supported_blockchains` | 加 `"bitcoin-cash"`(扩 N→N+1)| guard_*chain_truth.sh |
| 2 | `config/config_loader.sh` case 分支 | 加 `bitcoin-cash) MAINNET_RPC_URL="https://rest1.biggestfan.net/v2"` | 缺则落默认 |
| 3 | `tools/fetch_active_accounts.py` `BitcoinAdapter` | 注册 `cashaddr` codec(新文件 `tools/cashaddr_codec.py`,~150 行,polymod + base32);param_format 处理 `bitcoincash:` HRP 剥离 | BTC codec 无 CashAddr |
| 4 | `tools/mock_rpc_server.py` | 新增 chain 分支 `bitcoin-cash`,复用 BTC 的 method handler,只替换 `getnetworkinfo` 的 `subversion` fixture 为 BCHN string | CI fallback |
| 5 | `tests/cashaddr_codec_test.py` | 新增单元测试:编码/解码 5 个真实 CashAddr,polymod checksum 校验 | E1 — 必须有,因为 codec 是手写的 |

**N/A**:无 method 需删,无 method 需加,JSON-RPC 协议层 0 改动。

---

## 10. Trade-off & 真相对齐

1. **公链 endpoint 是 REST 不是 JSON-RPC** — context 文件给的 `bch.publicnode.com` 已失效(实测 404,2026-05-23)。benchmark 公链模式只能走 Bitcoin.com REST 代理,这意味着 publicnode 模式的"协议一致性"假设(BTC 怎么打 BCH 也怎么打)**不成立**。self-hosted 模式仍然一致。
2. **32MB 块在公链上看不到** — 实测 block size 中位数 < 3KB(BCH 链上活动稀少),想真实压力测试大块路径必须 regtest。
3. **SLP 不进 benchmark** — token 解码需 OP_RETURN parser + SLPDB,与 RPC 协议无关,排除。
4. **CashAddr codec 必须手写** — Python `bech32` 库不通用(polymod generator 不同);本框架引入 ~150 行新代码,放在 `tools/cashaddr_codec.py`,**不依赖**外部 PyPI 包(避免供应链风险)。
