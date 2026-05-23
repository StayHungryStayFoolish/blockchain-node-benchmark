# 19-Litecoin Research (DIFF-ONLY)

> **This document records ONLY the substantive differences between Litecoin and `03-bitcoin.md`.**
> Litecoin was forked from Bitcoin Core in 2011 (founder: Charlie Lee, repo: litecoin-project/litecoin). Its protocol, JSON-RPC schema, error codes, and auth mechanism are **~99% identical to Bitcoin**.
> Any field not appearing here (method signatures, error codes, Basic Auth, mock template, adapter-reuse decision logic) is **inherited verbatim from 03-bitcoin.md**. E1–E5 tags and H8 real-evidence rules apply unchanged.

---

## Metadata

| Field | Value |
|---|---|
| Chain (zh) | 莱特币 |
| Chain (en) | Litecoin |
| ID | 19 |
| Mainnet ChainID | N/A (UTXO chain has no EIP-155 ChainID; magic bytes `0xDBB6C0FB`, genesis hash `12a765e31ffd4059bada1e25190f6e98c99d9714d334efa41a195a7e7e04bfe2`) [E3 — litecoin-project README] |
| Research date | 2026-05-23 |
| Researcher | Hermes Agent |
| Status | 🟢 Complete (diff-only) |

---

## 1. Sources (delta only)

| Type | URL | Notes |
|---|---|---|
| GitHub | https://github.com/litecoin-project/litecoin | Forked from Bitcoin Core 0.3.x in 2011; long-term rebases against upstream BTC; current master ~ Bitcoin Core 0.21.x [E4] |
| MWEB LIP-0002/0003 | https://github.com/litecoin-project/lips/blob/master/lip-0002.mediawiki | MimbleWimble Extension Block, activated 2022-05 (block 2,257,920) [E3] |
| Scrypt PoW paper | https://www.tarsnap.com/scrypt/scrypt.pdf | Colin Percival, 2009 — LTC chose this for ASIC-resistance (later defeated by ASICs) |
| Public REST | https://litecoinspace.org/docs/api/rest | Esplora fork (mempool.space-style), operated by Litecoin Foundation [E2 — see §3] |
| Explorer | https://blockchair.com/litecoin | Cross-check for hashes/heights cited below |

**Fork lineage**: Bitcoin Core 0.3.x (2011) → Litecoin Core 0.x → continual cherry-pick of upstream BTC (segwit, PSBT, descriptor wallet) → today equivalent to Bitcoin Core 0.21.x. MWEB is Litecoin-exclusive — **no equivalent codepath exists in Bitcoin upstream**.

---

## 2. Substantive Differences vs BTC (core table)

| Dimension | Bitcoin | Litecoin | Impact on this framework |
|---|---|---|---|
| PoW algorithm | SHA-256d | **Scrypt** (N=1024, r=1, p=1) [E3 — scrypt paper] | Affects only mining/`getmininginfo.networkhashps` units; **does not affect RPC schema** |
| Target block time | 600 s | **150 s (2.5 min)** [E2 — measured in §8] | Sampling intervals can shrink 4×; mempool turnover faster |
| Halving interval | 210,000 blocks (~4y) | 840,000 blocks (~4y, since block time is 1/4 → 4× block count) | Does not affect RPC |
| Smallest unit | satoshi (1 BTC = 1e8 sat) | litoshi (1 LTC = 1e8 litoshi) | `amount` fields semantically identical, only display unit differs |
| Total supply | 21,000,000 BTC | 84,000,000 LTC | Does not affect RPC |
| SegWit | Activated 2017-08 (BIP-141) | **Activated 2017-05, before BTC** [E3] | weight/vsize fields 100% compatible, no diff |
| Taproot (BIP-341) | Activated 2021-11 | **Not activated** (no strong community demand) | No P2TR addresses (no bech32m); `scriptPubKey.type` never returns `witness_v1_taproot` |
| MWEB (MimbleWimble) | Does not exist | **Activated 2022-05** (LIP-0002/0003) | Exclusive codepath, see §5 below |
| Address prefix | `bc1q` (P2WPKH) / `bc1p` (P2TR) / `1`/`3` (legacy) | `ltc1q` (P2WPKH) / `L` (P2PKH, prefix 0x30) / `M`/`3` (P2SH, prefix 0x32) / `ltcmweb1...` (MWEB) | adapter must recognize LTC prefixes (same structure as 03-bitcoin.md §4) |
| Magic bytes | `0xD9B4BEF9` | `0xDBB6C0FB` | P2P-layer only, not exposed via RPC |
| Default RPC port | 8332 | 9332 | self-hosted target endpoint differs |

**Conclusion**: For the 8 methods this framework monitors (`getbestblockhash` / `getblockcount` / `getblock` / `getblockhash` / `getrawtransaction` / `getmempoolinfo` / `getrawmempool` / `scantxoutset`), there are **0 method-schema differences** and **0 error-code differences**. MWEB only adds **optional fields** (`pegin_amount`, `pegout_amount`, etc.; see §5), which do not break BTC reader compatibility.

---

## 3. Public RPC measurements (delta)

| Endpoint | Auth | Result | Notes |
|---|---|---|---|
| `https://litecoin-rpc.publicnode.com` | none | ❌ HTTP **404** (measured 2026-05-23) | BTC has this domain, LTC does **not**; publicnode provides no Litecoin RPC |
| `https://litecoinspace.org/api/*` | none | ✅ 200 (Esplora REST, **not JSON-RPC**) | **Evidence endpoint for this doc**; mempool.space-compatible schema |
| `https://api.blockchair.com/litecoin/stats` | none / API key | ✅ 200 | Backup; field naming differs from Esplora |
| `https://api.blockcypher.com/v1/ltc/main` | none / token | ✅ 200 | Third fallback |
| `http://<self-hosted>:9332` | basic auth | not tested | True benchmark-target path |
| `https://rpc.ankr.com/litecoin` | bearer | ❌ HTTP **403** (measured 2026-05-23) | Requires paid plan |

**Trade-off**: Unlike BTC, **no mainstream Litecoin public chain offers anonymous JSON-RPC 1.0**. Wave2 strategy:
1. Use `litecoinspace.org` Esplora REST for height/block/mempool liveness (read-only path, schema captured below);
2. Real benchmark must self-host `litecoind` (same fallback plan as BTC);
3. Mock layer needs only magic-bytes/port swap on top of BTC, **no new branch**.

**curl evidence** (mandatory):
```bash
# E2 — 2026-05-23 litecoinspace.org tip height
curl -s https://litecoinspace.org/api/blocks/tip/height
# Output: 3112566

# E2 — 2026-05-23 litecoinspace.org tip hash
curl -s https://litecoinspace.org/api/blocks/tip/hash
# Output: c72dd1d0a56a183e3536f918295362b45fd46701aaa93126c4f863d519d61b4c

# E2 — 2026-05-23 publicnode does not exist
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://litecoin-rpc.publicnode.com \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"1.0","id":1,"method":"getblockcount","params":[]}'
# Output: 404
```

---

## 4. Method differences (~99% same as BTC)

All 8 monitored methods share BTC's schema exactly. Only 2 caveats:

1. **`getblock` return value**: After MWEB activation, the block object **may** contain Litecoin-exclusive fields `mweb_block` (hex) and `hogex` (Hogwarts Express tx — the peg-in/out bridge between MWEB and main chain), appearing only at verbosity ≥ 2. **Readers must ignore unknown fields** (already a BTC framework convention).
2. **`getrawtransaction` return value**: TXs involving MWEB pegs include `vout[i].scriptPubKey.type == "witness_mweb_pegin"` / `"witness_mweb_hogaddr"`. The BTC reader recognizes 8 scriptPubKey types; this framework's `unknown_type` branch handles these gracefully — **non-blocking**.

**Identical methods** (link to 03-bitcoin.md §5):
`getbestblockhash` / `getblockcount` / `getblockhash` / `getrawtransaction` (non-MWEB tx) / `getmempoolinfo` / `getrawmempool` / `scantxoutset`.

**Litecoin-exclusive methods** (**not** monitored, recorded for completeness):
- `verifychain` parameter defaults identical to BTC, no diff
- No exclusive RPC method names exist; MWEB introduces no new methods, only new optional fields in existing method returns [E5 — grep over `RPCArg` in litecoin-project/litecoin reveals no methods absent from BTC]

---

## 5. Real-world Workload (mainstream tokens / use-cases)

| Use-case | Status | Impact on benchmark |
|---|---|---|
| Native LTC transfers (P2PKH/P2WPKH) | Primary workload | Identical to BTC, no diff |
| Stablecoins (USDT-LTC) | **Do not exist** — Tether never issued on LTC (no token standard beyond OP_RETURN) | No token-indexer layer needed |
| Ordinals / Inscriptions | Ported in 2023 (`ord-litecoin` fork) | Same large-witness-data signature as BTC; large-block mempool tests reusable |
| MWEB peg in/out | Live since 2022-05; < 1% of tx volume | See §4, field-level compatible |
| Lightning Network | Supported (LND/c-lightning compatible) | Out of scope for L1 monitoring |

**Live block (2026-05-23, height 3,112,566)**: 929 tx, size 330,405 B, weight 959,787 (< 4,000,000 cap, indicating broad segwit adoption), difficulty 103,531,654 (vs BTC ~1.36e14 same day — not directly comparable due to different Scrypt hashrate distribution).

---

## 6. DSL Decision (predicted: 0 new fields)

Reuse the BTC DSL under `family=utxo-btc`; only chain-level parameters differ:

```yaml
# config/chains/litecoin.yaml (P2-DESIGN-v2 stub)
chain_id: litecoin
family: utxo-btc           # reuse adapter defined in 03-bitcoin.md
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
public_rpc: []                       # No anonymous JSON-RPC; self-host required
methods: ${family.utxo-btc.methods}  # full inherit, no override
```

**Total new DSL fields: 0**. All differences expressed within already-parameterized fields of the existing family schema.

---

## 7. H8 Evidence (curl + real data)

The following 5 commands were measured on 2026-05-23 and returned real mainnet data (cross-checkable at https://blockchair.com/litecoin):

```bash
# 1. tip height
$ curl -s https://litecoinspace.org/api/blocks/tip/height
3112566

# 2. tip hash
$ curl -s https://litecoinspace.org/api/blocks/tip/hash
c72dd1d0a56a183e3536f918295362b45fd46701aaa93126c4f863d519d61b4c

# 3. block detail (proves segwit weight is in use)
$ curl -s https://litecoinspace.org/api/block/c72dd1d0a56a183e3536f918295362b45fd46701aaa93126c4f863d519d61b4c
{"id":"c72dd1d0...","height":3112566,"version":536870912,"timestamp":1779564023,
 "tx_count":929,"size":330405,"weight":959787,"merkle_root":"edd6c781...",
 "previousblockhash":"06def9ad...","mediantime":1779563109,"nonce":495071304,
 "bits":422149092,"difficulty":103531654.83378036}

# 4. mempool status (vs BTC's ~200-300k tx, LTC has only ~200)
$ curl -s https://litecoinspace.org/api/mempool
{"count":193,"vsize":66896,"total_fee":822737,"fee_histogram":[[1.01,52064],[1.00,14832]]}

# 5. recommended fees (LTC typically 1 litoshi/vB, vs BTC's frequent 10-100 sat/vB)
$ curl -s https://litecoinspace.org/api/v1/fees/recommended
{"fastestFee":1,"halfHourFee":1,"hourFee":1,"economyFee":1,"minimumFee":1}

# 6. block-time verification (blockchair 24h block count)
$ curl -s https://api.blockchair.com/litecoin/stats | python3 -c "import json,sys; d=json.load(sys.stdin)['data']; print('blocks_24h=',d['blocks_24h'],'-> avg block time =',86400/d['blocks_24h'],'s')"
blocks_24h= 601 -> avg block time = 143.76 s   # ≈ 2.5 min target [E2 ✅]
```

---

## 8. Decisions & Open Items

- **Reuse decision**: `family=utxo-btc` adapter is 100% reused; no new `LitecoinAdapter` class needed; chain-level config parameterized in yaml.
- **Mock changes**: `mock_rpc_server.py`'s Bitcoin branch only needs to accept a `chain_id` arg at init and swap magic/prefix/port — **no new branch**.
- **MWEB non-blocking**: Wave6 does not require MWEB field parsing; reader-layer `unknown_field` tolerance suffices. If future MWEB balance accounting is required, add a standalone `getmwebheader` parser (out of scope).
- **Public-chain limitation recorded**: LTC's lack of anonymous JSON-RPC is a hard constraint for wave2's endpoint matrix; CI-mock priority bumped.

---

## Changelog

- 2026-05-23 — Initial revision (diff-only, based on 03-bitcoin.md); `litecoin-rpc.publicnode.com` measured 404, switched evidence endpoint to litecoinspace.org Esplora REST; 0 new DSL fields.
