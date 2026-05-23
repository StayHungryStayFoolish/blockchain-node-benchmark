# 20-Dogecoin Research (diff-only vs 03-bitcoin.md)

> **Aggressive DIFF-ONLY mode**: JSON-RPC envelope / error code table / auth scheme are fully inherited from `03-bitcoin.md`. This file only records deltas.
> Evidence tags: E1 (unit) / E2 (curl) / E3 (doc) / E4 (source) / E5 (grep).

---

## Meta

| Field | Value |
|---|---|
| Chain | Dogecoin |
| Number | 20 |
| Mainnet ChainID | N/A; identified by magic bytes `0xC0C0C0C0` and genesis `1a91e3dace36e2be3bf030a65679fe821aa1d6ef92e7c9902eb318182c355691` [E3 dogecoin/dogecoin chainparams.cpp] |
| Family | utxo-btc (Bitcoin Core fork) → reuses `BitcoinAdapter`, no new adapter |
| Research date | 2026-05-23 |
| Status | 🟢 Complete |

---

## 1. Sources

| Type | URL | Note |
|---|---|---|
| Official repo | https://github.com/dogecoin/dogecoin | tag `v1.14.9` (2025); fork origin = Bitcoin Core 0.21 + Litecoin 0.21 middle layer [E4] |
| Fork lineage | https://github.com/dogecoin/dogecoin/blob/master/doc/release-notes.md | Per-release backport ranges from BTC/LTC upstream [E3] |
| RPC reference | https://developer.bitcoin.org/reference/rpc/ | Reused; Doge subset is trimmed/extended in src/rpc/ (see §5) |
| AuxPoW spec | https://en.bitcoin.it/wiki/Merged_mining_specification | Namecoin-origin AuxPoW; Doge enabled merged mining with LTC at block 371,337 (2014) [E3] |
| BlockCypher REST | https://api.blockcypher.com/v1/doge/main | Primary live endpoint for this research (public JSON-RPC ≈ none, see §3) |
| Blockchair REST | https://api.blockchair.com/dogecoin/stats | Cross-check endpoint |
| Explorer | https://dogechain.info / https://blockchair.com/dogecoin | Cross-validation of hashes/addresses |

---

## 2. Fork Lineage (two-layer fork)

```
Bitcoin Core (Satoshi 0.6, 2011)
        │
        ├── fork ──► Litecoin (2011-10) ── Scrypt PoW, 2.5 min blocks, 4× supply
        │                   │
        │                   └── fork ──► Dogecoin (2013-12, Markus & Palmer)
        │                                  ├── 1 min block time (LTC × 1/2.5)
        │                                  ├── initially uncapped supply (changed 2014 to +5 B/yr forever)
        │                                  └── 2014-09 activated AuxPoW (merged mining with LTC, still on)
        │
        └── (independent evolution: SegWit / Taproot — Doge has NEITHER)
```

- Doge forked directly from **Litecoin** (not BTC), so its codebase = LTC fork = BTC fork → **two-layer fork**.
- Doge continually backports fixes from BTC/LTC upstreams (v1.14 line is aligned to Bitcoin Core 0.21) but has **deliberately not activated SegWit/Taproot** (community + miner-signaling consensus) [E3 release-notes v1.14.5].
- Protocol drift vs BTC: identical UTXO model, identical Script opcode set (incl. OP_CHECKLOCKTIMEVERIFY/CSV); **missing** SegWit witness fields, bech32 addresses, Taproot.

---

## 3. Public RPC (live endpoint probing)

| Endpoint | Kind | Result | Note |
|---|---|---|---|
| `https://dogecoin-rpc.publicnode.com` | JSON-RPC 1.0 | ❌ empty / no record | publicnode does not ship Doge as of 2026-05 [E2] |
| `https://rpc.ankr.com/doge` | JSON-RPC | ❌ HTTP 403 | Ankr removed the public Doge route [E2] |
| `https://doge.nownodes.io` | JSON-RPC | ⚠️ HTTP 422 (missing `api-key`) | Paid only, no free tier [E2] |
| `https://doge.getblock.io/mainnet/` | JSON-RPC | ⚠️ requires access-token | Paid [E3] |
| `https://api.blockcypher.com/v1/doge/main` | **REST** (not JSON-RPC) | ✅ 200, height=6,218,871 | Primary fallback for this research [E2] |
| `https://api.blockchair.com/dogecoin/stats` | **REST** | ✅ 200, height=6,218,871 | Cross-check [E2] |

**Key conclusion: Dogecoin has the worst public JSON-RPC availability of all UTXO chains in this study.** No free endpoint is open; live evidence is only obtainable via explorer REST or self-hosted node. The benchmark MUST assume self-hosted (port 22555, cookie auth identical to BTC).

---

## 4. Substantive Diff vs BTC

| Dimension | Bitcoin | Dogecoin | Impact |
|---|---|---|---|
| Block time | 600 s (10 min) | **60 s (1 min)** | 10× data per window; getblock call rate ↑ |
| Consensus | SHA-256d PoW | **Scrypt PoW + AuxPoW** (merged-mined with LTC) | Header carries auxpow; getblock verbosity=2 returns an `auxpow` object |
| Block size | 1 MB (≈4 MWU after SegWit) | **historically uncapped → 1 MB hard cap since 2014** (no weight) | Smaller per-block than BTC, but 10× rate → comparable total throughput |
| SegWit / Taproot | ✅ BIP141 / BIP341 | **❌ neither activated** | No witness, no P2WPKH/P2WSH/P2TR, no vsize |
| Address prefix | `1` (P2PKH) / `3` (P2SH) / `bc1` (bech32) | **`D` (P2PKH 0x1E) / `A` or `9` (P2SH 0x16)**, no bech32 | Address parser needs an independent base58-prefix table; no bech32 needed |
| Currency unit | 1 BTC = 10⁸ sat | **1 DOGE = 10⁸ koinu** (same precision, different name) | Display-only rename of sat → koinu |
| Supply | 21 M hard cap | **uncapped**, +5 B/yr perpetually | Benchmark-irrelevant; amount fields may be larger |
| Wallet RPC | Subset blocked on publicnode | Same — blocked on public endpoints too | Same behaviour as BTC |
| RPC port | 8332 / testnet 18332 | **22555 / testnet 44555** | Self-hosted config delta |
| Magic bytes | `0xD9B4BEF9` | `0xC0C0C0C0` | P2P-layer only; invisible at RPC |

---

## 5. Method Diff (99% identical to BTC — only deltas listed)

| Method | BTC | Doge | Delta |
|---|---|---|---|
| `getbestblockhash` | ✅ | ✅ | identical |
| `getblockcount` | ✅ | ✅ | identical (observed height 6,218,871 @ 2026-05-23) [E2] |
| `getblock` | ✅ verbosity 0/1/2 | ✅ verbosity 0/1/2 | **extra `auxpow` object** in response (verbosity≥1, blocks after AuxPoW activation) with `parentblock` / `coinbasebranch` / `chainmerklebranch` |
| `getblockhash` | ✅ | ✅ | identical |
| `getblockhashes` | ❌ (BTC Core lacks it; Bitcore patch only) | ❌ | identical (Doge also lacks it) |
| `getrawtransaction` | ✅ | ✅ | identical; **returned tx has no `vsize` / `weight` / `wtxid`** (no SegWit), only `size` |
| `getmempoolinfo` | ✅ | ✅ | identical |
| `getrawmempool` | ✅ | ✅ | identical |
| `scantxoutset` | ✅ (v0.17+) | ⚠️ **unavailable** — Doge mainline v1.14 sits on a mixed BTC 0.16/0.21 base; scantxoutset never backported | Use explorer REST instead [E5 grep src/rpc/blockchain.cpp shows no scantxoutset registration] |
| `getbalance` | ✅ (wallet; blocked publicly) | ✅ (wallet; blocked publicly) | identical |
| `getauxblock` | ❌ | ✅ **Doge-only** | AuxPoW miner-facing RPC; benchmark-irrelevant |
| `getblockheader` | ✅ | ✅ | identical; `version` high bits carry AuxPoW flag (version & 0x100) |

**Bottom line: of the 8 methods in scope, 7 are fully compatible and 1 (`scantxoutset`) is missing on Doge**; plus an `auxpow` field delta that the schema must flag.

---

## 6. Real Workload

- **No native token standard** (no mature OP_RETURN fungible-token protocol; no Doge counterpart to BRC-20 / SLP / Runes).
- Real traffic ≈ native DOGE transfers (Elon Musk tweet-driven spikes + long-tail tipping).
- Real address (D-prefix): `D7Y55r6Yoc1G8EECxkQ6SuSjTGGJqHGTaC` (Dogecoin Foundation public hot wallet)
- Real block hash (2026-05-23): `14e0b6e223f1484d345d25a9dde2707fed19ab0447f593cc82ccbc8ea8023018` (height 6,218,871, ver=6422788 = 0x620104 with AuxPoW flag set) [E2]

---

## 7. DSL Decision

**Predicted new fields: 0.** Reuse `BitcoinAdapter` + family `utxo-btc`. Only need:

```yaml
chains:
  dogecoin:
    family: utxo-btc
    adapter: BitcoinAdapter        # direct reuse
    chain_id: dogecoin-mainnet
    rpc_port: 22555
    magic_bytes: "0xC0C0C0C0"
    block_time_sec: 60
    address_prefixes: { p2pkh: 0x1E, p2sh: 0x16 }
    segwit_enabled: false          # affects tx schema: drop vsize/weight/wtxid
    auxpow_enabled: true           # affects getblock schema: include auxpow object
    unsupported_methods: ["scantxoutset"]
    endpoints:
      - https://api.blockcypher.com/v1/doge/main   # REST fallback
      - https://api.blockchair.com/dogecoin        # REST fallback
      # No public JSON-RPC — benchmark defaults to self-hosted
```

No new top-level DSL schema field is required; `segwit_enabled` / `auxpow_enabled` / `unsupported_methods` were already pencilled in the BTC research. Doge is the first chain that simultaneously sets segwit=false **and** auxpow=true.

---

## 8. H8 Evidence (curl)

```bash
# 1. height cross-check (REST, 2026-05-23 19:21 UTC)
curl -s https://api.blockcypher.com/v1/doge/main | jq '.height,.hash'
# → 6218871
# → "14e0b6e223f1484d345d25a9dde2707fed19ab0447f593cc82ccbc8ea8023018"

curl -s https://api.blockchair.com/dogecoin/stats | jq '.data.best_block_height'
# → 6218871  ✅ both sources agree

# 2. block detail (confirms AuxPoW version flag)
curl -s https://api.blockcypher.com/v1/doge/main/blocks/14e0b6e223f1484d345d25a9dde2707fed19ab0447f593cc82ccbc8ea8023018 | jq '.ver,.nonce'
# → 6422788   # = 0x620104, AuxPoW bit (0x100) set
# → 0         # AuxPoW blocks usually have local nonce=0; PoW lives in parent (LTC) header

# 3. public JSON-RPC liveness (all fail — corroborates §3)
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://dogecoin-rpc.publicnode.com   # 000 / empty
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://rpc.ankr.com/doge             # 403
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://doge.nownodes.io              # 422 (api-key needed)

# 4. block-rate sanity check (1 min target)
# Blockchair: blocks_24h = 1366 → 86400/1366 ≈ 63.2s, matches 60s target [E2]
```

---

## 9. ASK (DSL decision requests)

1. **Add `auxpow_enabled` boolean to the DSL?** Only Doge / Namecoin / RSK use AuxPoW in Wave 6 BTC forks; if only 1-2 chains need it, push it into a `chain_specific` sub-table instead of a top-level field.
2. **Promote `unsupported_methods` to a Wave-6 standard field?** Doge (scantxoutset), BCH (scantxoutset also gone), LTC (partial) all differ. Recommend adding it to `_template.md`.
3. **Benchmark strategy for chains without public JSON-RPC**: Doge has essentially none. Should we add `requires_self_hosted: true` to the DSL so the runner skips the public-endpoint discovery phase?
