# 19-Litecoin 调研(DIFF-ONLY)

> **本文件仅记录 Litecoin 与 `03-bitcoin.md` 的实质差异。**
> Litecoin 是 Bitcoin Core 2011 年 fork(创始人 Charlie Lee, GitHub: litecoin-project/litecoin),协议、JSON-RPC schema、错误码、鉴权机制 **99% 同 Bitcoin**。
> 凡未在此文件出现的字段(method 签名、error code、Basic Auth、mock 实现模板、adapter 复用判断逻辑),**默认完全复用 03-bitcoin.md**。E1-E5 标签与 H8 真实证据规则同前。

---

## 元信息

| 项 | 值 |
|---|---|
| 链名(中) | 莱特币 |
| 链名(英) | Litecoin |
| 编号 | 19 |
| Mainnet ChainID | N/A(UTXO 链无 EIP-155 ChainID;magic bytes `0xDBB6C0FB`,genesis hash `12a765e31ffd4059bada1e25190f6e98c99d9714d334efa41a195a7e7e04bfe2`)[E3 — litecoin-project README] |
| 调研日期 | 2026-05-23 |
| 调研者 | Hermes Agent |
| 状态 | 🟢 已完成(diff-only) |

---

## 1. Sources(差异权威来源)

| 类型 | URL | 备注 |
|---|---|---|
| GitHub | https://github.com/litecoin-project/litecoin | 2011 年从 Bitcoin Core 0.3.x fork,长期 rebase 跟随 BTC 上游,当前 master 对齐 Bitcoin Core 0.21.x 系列 [E4] |
| MWEB BIP-LIP-0002/0003 | https://github.com/litecoin-project/lips/blob/master/lip-0002.mediawiki | MimbleWimble Extension Block,2022-05 主网激活(block 2257920)[E3] |
| Scrypt PoW 论文 | https://www.tarsnap.com/scrypt/scrypt.pdf | Colin Percival, 2009 — Litecoin 选用其作为 ASIC 抵抗 PoW(后被 ASIC 攻克) |
| 公共 REST | https://litecoinspace.org/docs/api/rest | Esplora-fork(mempool.space 风格),Litecoin Foundation 运营 [E2 — 见 §3] |
| 浏览器 | https://blockchair.com/litecoin | 用于校验下文贴出的 hash/高度 |

**Fork lineage**:Bitcoin Core 0.3.x(2011)→ Litecoin Core 0.x → 长期 cherry-pick BTC 上游 segwit/PSBT/descriptor wallet → 当前 0.21.x 等价。MWEB 是 Litecoin 独有,**Bitcoin upstream 无此 codepath**。

---

## 2. 与 BTC 的实质差异表(核心)

| 维度 | Bitcoin | Litecoin | 对本框架的影响 |
|---|---|---|---|
| PoW 算法 | SHA-256d | **Scrypt**(N=1024, r=1, p=1)[E3 — scrypt 论文] | 仅影响挖矿/`getmininginfo.networkhashps` 单位,**不影响 RPC schema** |
| 目标出块时间 | 600 s | **150 s(2.5 min)**[E2 — 实测见 §8] | 监控/采样间隔可缩短 4×;mempool turnover 更快 |
| 区块奖励减半周期 | 210,000 块 (~4y) | 840,000 块 (~4y,因块时间 1/4 故块数 4×) | 不影响 RPC |
| 单位 | satoshi (1 BTC = 1e8 sat) | litoshi (1 LTC = 1e8 litoshi) | `amount` 字段语义同 BTC,仅显示单位变 |
| 总供应 | 21,000,000 BTC | 84,000,000 LTC | 不影响 RPC |
| SegWit | 2017-08 激活(BIP-141) | **2017-05 激活,先于 BTC**[E3] | weight/vsize 字段 100% 兼容,无差异 |
| Taproot (BIP-341) | 2021-11 激活 | **未激活**(社区无强烈需求) | 无 P2TR 地址(bech32m 不出现),`scriptPubKey.type` 不会返回 `witness_v1_taproot` |
| MWEB(MimbleWimble) | 不存在 | **2022-05 激活**(LIP-0002/0003) | 独有 codepath,见下文 §5 |
| Address prefix | `bc1q` (P2WPKH) / `bc1p` (P2TR) / `1`/`3` (legacy) | `ltc1q` (P2WPKH) / `L` (P2PKH, prefix 0x30) / `M`/`3` (P2SH, prefix 0x32) / `ltcmweb1...` (MWEB) | adapter 需识别 LTC 前缀(详见 §4 of 03-bitcoin.md 同结构) |
| Magic bytes | `0xD9B4BEF9` | `0xDBB6C0FB` | 用于 P2P 层,RPC 层不暴露 |
| 默认 RPC port | 8332 | 9332 | self-hosted target 时 endpoint 差异 |

**结论**:对本框架监控所需 8 个 method(`getbestblockhash` / `getblockcount` / `getblock` / `getblockhash` / `getrawtransaction` / `getmempoolinfo` / `getrawmempool` / `scantxoutset`),**0 个 method schema 差异**,**0 个 error code 差异**。MWEB 仅新增 `pegin_amount`/`pegout_amount` 等 **可选字段**(参见 §5),不破坏 BTC reader 兼容性。

---

## 3. 公共 RPC 实测(diff 部分)

| Endpoint | Auth | 实测 | 备注 |
|---|---|---|---|
| `https://litecoin-rpc.publicnode.com` | 无 | ❌ HTTP **404**(2026-05-23 实测) | BTC 有此域名,LTC **无**;publicnode 未提供 Litecoin RPC |
| `https://litecoinspace.org/api/*` | 无 | ✅ 200(Esplora REST,**非 JSON-RPC**) | **本文档实证 endpoint**;mempool.space 兼容 schema |
| `https://api.blockchair.com/litecoin/stats` | 无 / API key | ✅ 200 | 兼用,字段命名与 Esplora 不同 |
| `https://api.blockcypher.com/v1/ltc/main` | 无 / token | ✅ 200 | 第三 fallback |
| `http://<self-hosted>:9332` | basic auth | 未测 | 真实 benchmark target 路径 |
| `https://rpc.ankr.com/litecoin` | bearer | ❌ HTTP **403**(2026-05-23 实测) | 需付费 plan |

**Trade-off**:与 BTC 不同,**Litecoin 主流公链未提供匿名 JSON-RPC 1.0 endpoint**。本框架 wave2 实测策略:
1. 使用 `litecoinspace.org` Esplora REST 做高度/区块/mempool 探活(只读路径,schema 已贴出);
2. 真实 benchmark 必须 self-host litecoind(同 BTC 的 fallback 计划);
3. mock 层在 BTC 基础上仅切换 magic bytes / port,**无需新增分支**。

**curl 实测**(必填):
```bash
# E2 — 2026-05-23 litecoinspace.org tip 高度
curl -s https://litecoinspace.org/api/blocks/tip/height
# 实测输出:3112566

# E2 — 2026-05-23 litecoinspace.org tip hash
curl -s https://litecoinspace.org/api/blocks/tip/hash
# 实测输出:c72dd1d0a56a183e3536f918295362b45fd46701aaa93126c4f863d519d61b4c

# E2 — 2026-05-23 publicnode 不存在
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://litecoin-rpc.publicnode.com \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"1.0","id":1,"method":"getblockcount","params":[]}'
# 实测输出:404
```

---

## 4. Method 差异(99% 同 BTC,只列差异)

本框架监控的 8 method **schema 与 BTC 完全一致**,仅以下 2 处需要注意:

1. **`getblock` 返回值**:MWEB 激活后,块对象**可能**包含独有字段 `mweb_block`(hex)、`hogex`(Hogwarts Express tx,MWEB 与 main chain 的 peg in/out 桥),仅在 verbosity≥2 出现。**Reader 应忽略未知字段**(已是 BTC 框架既有约定)。
2. **`getrawtransaction` 返回值**:涉及 MWEB peg 的 tx 含 `vout[i].scriptPubKey.type == "witness_mweb_pegin"` / `"witness_mweb_hogaddr"`。BTC reader 仅识别 8 种 scriptPubKey type,本框架在 `unknown_type` 分支可平滑忽略,**不阻塞**。

**完全相同的 method**(链接到 03-bitcoin.md §5 即可):
`getbestblockhash` / `getblockcount` / `getblockhash` / `getrawtransaction`(非 MWEB tx) / `getmempoolinfo` / `getrawmempool` / `scantxoutset`。

**Litecoin 独有 method**(本框架**不监控**,仅记录):
- `verifychain` 参数 default level 同 BTC,无差异
- 无任何独有 RPC method 名;MWEB 不引入新 method,仅在既有 method 返回值中新增可选字段 [E5 — litecoin-project/litecoin grep `RPCArg` 未发现 BTC 不存在的 method 注册]

---

## 5. 真实负载(主流 token / 用例)

| 用例 | 现状 | 对 benchmark 影响 |
|---|---|---|
| 原生 LTC 转账(P2PKH/P2WPKH) | 主要负载 | 同 BTC,无差异 |
| Stablecoin (USDT-LTC) | **不存在** — Tether 未在 LTC 发行(LTC 无 OP_RETURN 之外的 token 标准) | 无需 token 索引层 |
| Ordinals / Inscriptions | 2023 起被移植(`ord-litecoin` fork) | 与 BTC 同样表现为大尺寸 witness data;mempool 大块测试可复用 |
| MWEB peg in/out | 2022-05 起激活,占比 < 1% tx | 见 §4,字段层兼容 |
| 闪电网络 | 支持(同 BTC LND/c-lightning 兼容) | 与本框架 layer-1 监控无关 |

**实测块(2026-05-23,高度 3,112,566)**:929 tx,size 330,405 B,weight 959,787(< 4,000,000 上限,说明 segwit 普遍使用),difficulty 103,531,654(对比 BTC 同期 1.36e14,因 Scrypt 算力分布不同,数值不可直接比较)。

---

## 6. DSL 决策(预测 0 新字段)

复用 `family=utxo-btc` 的 BTC DSL,仅以下 chain-level 参数不同:

```yaml
# config/chains/litecoin.yaml (P2-DESIGN-v2 预填)
chain_id: litecoin
family: utxo-btc           # 复用 03-bitcoin.md 定义的 adapter
display_name: "Litecoin"
units:
  base: litoshi
  display: LTC
  decimals: 8
block_time_target_s: 150   # vs BTC 600
default_rpc_port: 9332     # vs BTC 8332
magic_bytes: "0xDBB6C0FB"  # vs BTC 0xD9B4BEF9
genesis_hash: "12a765e31ffd4059bada1e25190f6e98c99d9714d334efa41a195a7e7e04bfe2"
address_prefixes:
  p2pkh: 0x30   # 'L' (vs BTC 0x00 '1')
  p2sh:  0x32   # 'M' or '3' (vs BTC 0x05 '3')
  bech32_hrp: "ltc"  # vs BTC "bc"
public_rest:
  - https://litecoinspace.org/api    # Esplora-style, only viable anonymous endpoint
public_rpc: []                       # 无匿名 JSON-RPC;self-host required
methods: ${family.utxo-btc.methods}  # 完全继承,无 override
```

**新增 DSL 字段总数:0**。所有差异均在 既有 family schema 的参数化字段内表达。

---

## 7. H8 实证(curl + 真实数据)

下列 5 条命令于 2026-05-23 实测,均返回真实主网数据(可在 https://blockchair.com/litecoin 校验):

```bash
# 1. tip height
$ curl -s https://litecoinspace.org/api/blocks/tip/height
3112566

# 2. tip hash
$ curl -s https://litecoinspace.org/api/blocks/tip/hash
c72dd1d0a56a183e3536f918295362b45fd46701aaa93126c4f863d519d61b4c

# 3. block detail (segwit weight 证据)
$ curl -s https://litecoinspace.org/api/block/c72dd1d0a56a183e3536f918295362b45fd46701aaa93126c4f863d519d61b4c
{"id":"c72dd1d0...","height":3112566,"version":536870912,"timestamp":1779564023,
 "tx_count":929,"size":330405,"weight":959787,"merkle_root":"edd6c781...",
 "previousblockhash":"06def9ad...","mediantime":1779563109,"nonce":495071304,
 "bits":422149092,"difficulty":103531654.83378036}

# 4. mempool 状态(对比 BTC ~2-300k tx,LTC 仅 ~200)
$ curl -s https://litecoinspace.org/api/mempool
{"count":193,"vsize":66896,"total_fee":822737,"fee_histogram":[[1.01,52064],[1.00,14832]]}

# 5. 推荐手续费(LTC 普遍 1 litoshi/vB,vs BTC 常 10-100 sat/vB)
$ curl -s https://litecoinspace.org/api/v1/fees/recommended
{"fastestFee":1,"halfHourFee":1,"hourFee":1,"economyFee":1,"minimumFee":1}

# 6. 出块时间验证(blockchair 24h 块数)
$ curl -s https://api.blockchair.com/litecoin/stats | python3 -c "import json,sys; d=json.load(sys.stdin)['data']; print('blocks_24h=',d['blocks_24h'],'-> avg block time =',86400/d['blocks_24h'],'s')"
blocks_24h= 601 -> avg block time = 143.76 s   # ≈ 2.5 min target [E2 ✅]
```

---

## 8. 决策与遗留

- **复用决策**:`family=utxo-btc` adapter 100% 复用,无需新建 LitecoinAdapter 类;chain-level 配置在 yaml 内参数化。
- **mock 改造**:`mock_rpc_server.py` 的 Bitcoin 分支只需在初始化时接收 `chain_id` 参数,替换 magic/prefix/port,**无新增分支**。
- **MWEB 不阻塞**:本框架 wave6 暂不要求解析 MWEB 字段;读取层 `unknown_field` 容错足以通过。后续若需 MWEB 余额统计,新增独立 method `getmwebheader` 解析(out of scope)。
- **公链限制 已记录**:LTC 缺匿名 JSON-RPC 是 wave2 endpoint matrix 的硬约束;CI mock 优先级 ↑。

---

## Changelog

- 2026-05-23 — 初版(diff-only,基于 03-bitcoin.md);`litecoin-rpc.publicnode.com` 实测 404,改用 litecoinspace.org Esplora REST 取证;0 新 DSL 字段。
