# 20-Dogecoin 调研(diff-only vs 03-bitcoin.md)

> **激进 DIFF-ONLY 模式**:JSON-RPC 协议结构 / error code 表 / 鉴权机制完全继承 `03-bitcoin.md`,本文只记录差异。
> 证据标签:E1(单元)/E2(curl 实证)/E3(文档)/E4(源码)/E5(grep)。

---

## 元信息

| 项 | 值 |
|---|---|
| 链名 | Dogecoin(狗狗币) |
| 编号 | 20 |
| Mainnet ChainID | N/A;识别用 magic bytes `0xC0C0C0C0` 与 genesis `1a91e3dace36e2be3bf030a65679fe821aa1d6ef92e7c9902eb318182c355691` [E3 dogecoin/dogecoin chainparams.cpp] |
| Family | utxo-btc(Bitcoin Core fork)→ 复用 `BitcoinAdapter`,无需新建 |
| 调研日期 | 2026-05-23 |
| 状态 | 🟢 已完成 |

---

## 1. Sources

| 类型 | URL | 备注 |
|---|---|---|
| 官方仓库 | https://github.com/dogecoin/dogecoin | tag `v1.14.9`(2025),fork 起点 Bitcoin Core 0.21 + Litecoin 0.21 中间件 [E4] |
| Fork lineage 文档 | https://github.com/dogecoin/dogecoin/blob/master/doc/release-notes.md | 历代 release-notes 列出每次从 BTC/LTC 上游 backport 的范围 [E3] |
| RPC 参考 | https://developer.bitcoin.org/reference/rpc/ | 复用 Bitcoin Core 文档;Doge 子集在 src/rpc/ 内删减/扩展(见 §5) |
| AuxPoW BIP | https://en.bitcoin.it/wiki/Merged_mining_specification | Namecoin 起源的 AuxPoW 规范,Doge 自 2014 块高 371,337 启用与 LTC 合并挖矿 [E3] |
| BlockCypher REST | https://api.blockcypher.com/v1/doge/main | 本调研主要实证 endpoint(JSON-RPC 公链几乎无,见 §3) |
| Blockchair REST | https://api.blockchair.com/dogecoin/stats | 备份实证 endpoint |
| Explorer | https://dogechain.info / https://blockchair.com/dogecoin | 数据交叉校验 |

---

## 2. Fork 关系(两层 fork)

```
Bitcoin Core (Satoshi 0.6, 2011)
        │
        ├── fork ──► Litecoin (2011-10) ── 加 Scrypt PoW、2.5 min 出块、4× supply
        │                   │
        │                   └── fork ──► Dogecoin (2013-12, by Markus & Palmer)
        │                                  ├── 1 min 出块(LTC 的 1/2.5)
        │                                  ├── 初始无 supply 上限(2014 改为每年 5B 永久 inflation)
        │                                  └── 2014-09 启用 AuxPoW(与 LTC 合并挖矿至今)
        │
        └──(独立演化:SegWit / Taproot,Doge **都没有**)
```

- Doge 从 **Litecoin** 直接 fork(非 BTC),因此早期 codebase = LTC fork = BTC fork,**两层 fork**。
- Doge 长期从 BTC/LTC 上游 backport 修复(v1.14 系列已对齐到 Bitcoin Core 0.21),但**主动拒绝 SegWit/Taproot 激活**(社区共识 + 矿工未发信号)[E3 release-notes v1.14.5]。
- 与 BTC 协议偏移:UTXO 模型相同、Script opcode 集相同(包括 OP_CHECKLOCKTIMEVERIFY/CSV),**缺少** SegWit witness 字段、bech32 地址、Taproot。

---

## 3. Public RPC(公链 endpoint 实测)

| Endpoint | 类型 | 实测 | 备注 |
|---|---|---|---|
| `https://dogecoin-rpc.publicnode.com` | JSON-RPC 1.0 | ❌ 空响应 / 域名未配置 | publicnode 2026-05 未提供 Doge [E2] |
| `https://rpc.ankr.com/doge` | JSON-RPC | ❌ HTTP 403 | Ankr 已下架公开 Doge 路由 [E2] |
| `https://doge.nownodes.io` | JSON-RPC | ⚠️ HTTP 422(缺 `api-key` header) | 付费 endpoint,无 free tier [E2] |
| `https://doge.getblock.io/mainnet/` | JSON-RPC | ⚠️ 需 access-token | 付费 [E3] |
| `https://api.blockcypher.com/v1/doge/main` | **REST**(非 JSON-RPC) | ✅ 200,height=6,218,871 | 本调研主实证 fallback [E2] |
| `https://api.blockchair.com/dogecoin/stats` | **REST** | ✅ 200,height=6,218,871 | 交叉校验 [E2] |

**结论(关键):Dogecoin 是本调研所有 UTXO 链中公链 JSON-RPC 可用性最差的**。所有免费 endpoint 均不开放;实证只能走 explorer REST 或自建节点。Benchmark 目标必须假定 self-hosted(端口 22555,默认 cookie 鉴权同 BTC)。

---

## 4. 与 BTC 的实质差异表

| 维度 | Bitcoin | Dogecoin | 影响 |
|---|---|---|---|
| 出块时间 | 600s(10 min) | **60s(1 min)** | 同窗口数据量 10×,getblock 调用频率提升 |
| 共识算法 | SHA-256d PoW | **Scrypt PoW + AuxPoW**(与 LTC 合并挖矿) | block header 含 auxpow 字段,getblock verbosity=2 返回 `auxpow` 对象 |
| Block size | 1 MB(SegWit 后 ~4 MWU) | **历史无上限 → 2014 起 1 MB 硬上限**(无 weight 概念) | 单块容量小于 BTC,但出块快 ×10 ≈ 总吞吐与 BTC 同量级 |
| SegWit / Taproot | ✅ BIP141 / BIP341 | **❌ 均未激活** | 无 witness 字段、无 P2WPKH/P2WSH/P2TR 地址、无 vsize 概念 |
| 地址前缀 | `1`(P2PKH)/`3`(P2SH)/`bc1`(bech32) | **`D`(P2PKH 0x1E)/ `A` 或 `9`(P2SH 0x16)**,无 bech32 | 地址解析器需独立 base58 prefix 表;不需要 bech32 解码 |
| 货币单位 | 1 BTC = 10⁸ sat | **1 DOGE = 10⁸ koinu**(同精度,名字不同) | 反序列化字段 sat→koinu 显示即可 |
| 供应量 | 21 M 硬上限 | **无上限**,每年 +5 B(永久 inflation) | benchmark 无关,但 coin amount 字段可能更大 |
| Wallet RPC | 子集受限(publicnode 屏蔽) | 同样在公链端被屏蔽 | 与 BTC 行为一致 |
| RPC 端口 | 8332 / testnet 18332 | **22555 / testnet 44555** | 自建节点配置差异 |
| Magic bytes | `0xD9B4BEF9` | `0xC0C0C0C0` | P2P 层识别,RPC 层无感 |

---

## 5. Method 差异(99% 同 BTC,只列差异)

| Method | BTC | Doge | 差异 |
|---|---|---|---|
| `getbestblockhash` | ✅ | ✅ | 同 |
| `getblockcount` | ✅ | ✅ | 同(实测 height 6,218,871 @ 2026-05-23)[E2] |
| `getblock` | ✅ verbosity 0/1/2 | ✅ verbosity 0/1/2 | **返回多出 `auxpow` 对象**(verbosity≥1 且块在 AuxPoW 启用后),含 `parentblock`/`coinbasebranch`/`chainmerklebranch` |
| `getblockhash` | ✅ | ✅ | 同 |
| `getblockhashes` | ❌(BTC Core 没有,Bitcore patch) | ❌ | 同(Doge 也无) |
| `getrawtransaction` | ✅ | ✅ | 同;**返回的 tx 无 `vsize` / `weight` / `wtxid` 字段**(因无 SegWit),只有 `size` |
| `getmempoolinfo` | ✅ | ✅ | 同 |
| `getrawmempool` | ✅ | ✅ | 同 |
| `scantxoutset` | ✅(v0.17+) | ⚠️ **不可用**(Doge 主线 v1.14 基于 BTC 0.16/0.21 混合,scantxoutset 未 backport) | 用 explorer REST 替代 [E5 grep src/rpc/blockchain.cpp 无 scantxoutset 注册] |
| `getbalance` | ✅(wallet,公链屏蔽) | ✅(wallet,公链屏蔽) | 同 |
| `getauxblock` | ❌ | ✅ **Doge 独有** | AuxPoW 矿工接口,benchmark 不涉及 |
| `getblockheader` | ✅ | ✅ | 同;返回 `version` 字段高位含 AuxPoW flag(version & 0x100) |

**核心结论**:8 method 调研集中,**7 个完全兼容,1 个(`scantxoutset`)Doge 不支持**;另有 `auxpow` 字段差异需在 schema 中标注。

---

## 6. 真实负载

- **无内置 token 标准**(无 OP_RETURN-based fungible token 协议成熟生态;无 Doge 版 BRC-20 / SLP / Runes)。
- 主流量 = 原生 DOGE 转账(Elon Musk 推文驱动峰值 + 长尾小额打赏)。
- 真实地址(D-prefix):`D7Y55r6Yoc1G8EECxkQ6SuSjTGGJqHGTaC`(Dogecoin Foundation 公开热钱包)
- 真实块 hash(2026-05-23):`14e0b6e223f1484d345d25a9dde2707fed19ab0447f593cc82ccbc8ea8023018`(height 6,218,871,ver=6422788 即 0x620104,AuxPoW flag 置位)[E2]

---

## 7. DSL 决策

**预测新字段:0**。复用 `BitcoinAdapter` + `utxo-btc` family。仅需:

```yaml
chains:
  dogecoin:
    family: utxo-btc
    adapter: BitcoinAdapter        # 直接复用
    chain_id: dogecoin-mainnet
    rpc_port: 22555
    magic_bytes: "0xC0C0C0C0"
    block_time_sec: 60
    address_prefixes: { p2pkh: 0x1E, p2sh: 0x16 }
    segwit_enabled: false          # 影响 tx schema:无 vsize/weight/wtxid
    auxpow_enabled: true           # 影响 getblock schema:含 auxpow 字段
    unsupported_methods: ["scantxoutset"]
    endpoints:
      - https://api.blockcypher.com/v1/doge/main   # REST fallback
      - https://api.blockchair.com/dogecoin        # REST fallback
      # JSON-RPC 公链不可用,benchmark 默认 self-hosted
```

无需在 DSL schema 引入新顶级字段;`segwit_enabled` / `auxpow_enabled` / `unsupported_methods` 在 BTC 调研已规划,Doge 只是首次同时把 segwit 设 false 且 auxpow 设 true 的链。

---

## 8. H8 实证(curl)

```bash
# 1. height 交叉校验(REST,2026-05-23 19:21 UTC)
curl -s https://api.blockcypher.com/v1/doge/main | jq '.height,.hash'
# → 6218871
# → "14e0b6e223f1484d345d25a9dde2707fed19ab0447f593cc82ccbc8ea8023018"

curl -s https://api.blockchair.com/dogecoin/stats | jq '.data.best_block_height'
# → 6218871  ✅ 两源一致

# 2. block 详情(确认 AuxPoW version flag)
curl -s https://api.blockcypher.com/v1/doge/main/blocks/14e0b6e223f1484d345d25a9dde2707fed19ab0447f593cc82ccbc8ea8023018 | jq '.ver,.nonce'
# → 6422788   # = 0x620104,bit 0x100 (AuxPoW) 置位
# → 0         # AuxPoW 块本地 nonce 通常为 0,PoW 在 parent (LTC) 块

# 3. JSON-RPC 公链探活(全部失败,佐证 §3 结论)
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://dogecoin-rpc.publicnode.com   # 000 / 空
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://rpc.ankr.com/doge             # 403
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://doge.nownodes.io              # 422 (需 api-key)

# 4. 出块速率验证(1 min 目标)
# Blockchair: blocks_24h = 1366 → 86400/1366 ≈ 63.2s,符合 60s 目标 [E2]
```

---

## 9. ASK(DSL 决策请求)

1. **是否在 DSL 引入 `auxpow_enabled` 布尔字段?** 当前 Wave 6 BTC fork 中仅 Doge / Namecoin / RSK 用 AuxPoW;若只 1-2 链可走 `chain_specific` 子表,无需顶级字段。
2. **`unsupported_methods` 字段是否升级为 Wave 6 标准?** Doge(scantxoutset)、BCH(scantxoutset 也不可用)、LTC(部分可用)各有差异,建议在 `_template.md` 加入。
3. **公链不可用链的 benchmark 策略**:Doge 公链 JSON-RPC 几乎无,是否在 DSL 标注 `requires_self_hosted: true` 以让 runner 跳过公链探测阶段?
