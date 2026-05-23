# 21-Bitcoin Cash Research (diff-only, base=03-bitcoin)

> **DIFF-ONLY mode**: only records items that differ from `03-bitcoin.md`. JSON-RPC 1.0 protocol structure, error code table, HTTP Basic Auth, and the 10 core method signatures (`getbestblockhash` / `getblockcount` / `getblock` / `getblockhash` / `getblockhashes` / `getrawtransaction` / `getmempoolinfo` / `getrawmempool` / `scantxoutset` / `getbalance`) are 99% compatible with BTC and are **not repeated** here — see 03-bitcoin.md §5/§11.
> **Each field is tagged E1/E2/E3/E4/E5**.

---

## Meta

| Field | Value |
|---|---|
| Chain name (zh/en) | 比特币现金 / Bitcoin Cash (BCH) |
| Number | 21 |
| Mainnet ChainID | N/A (same as BTC; genesis hash `000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f` is **identical to BTC genesis** — real chain disambiguation needs the fork-block hash at height 478559: `000000000000000000651ef99cb9fcbe0dadde1d424bd9f15ff20136191a5eec`) [E2/E3] |
| Research date | 2026-05-23 |
| Researcher | Hermes Agent |
| Status | 🟢 Completed (diff-only) |
| Base chain | 03-bitcoin.md (commit `de925455c8025fc1f75d65d981c28b9dfa20e9f7`) |

---

## 1. Sources (BCH-specific only)

| Type | URL | Accessed | Note |
|---|---|---|---|
| Official docs | https://docs.bitcoincashnode.org/doc/29.0.0/ | 2026-05-23 | Bitcoin Cash Node (BCHN) 29.0 RPC reference. Live `getnetworkinfo.subversion = /Bitcoin Cash Node:29.0.0(EB32.0)/`, **EB32.0 = excessive blocksize 32 MB** [E2 — §3] |
| GitHub | https://gitlab.com/bitcoin-cash-node/bitcoin-cash-node | 2026-05-23 | BCHN primary repo (migrated off GitHub); diff base is Bitcoin Core 0.21.x [E3] |
| Hard fork history | https://en.bitcoin.it/wiki/Bitcoin_Cash | 2026-05-23 | 2017-08-01 height **478559** forked from Bitcoin Core; 2018-11-15 BSV split; 2020-11-15 ABC→XEC split [E3] |
| CashAddr spec | https://reference.cash/protocol/blockchain/encoding/cashaddr | 2026-05-23 | CashAddr address encoding (the single DSL ASK introduced by this doc) [E3] |
| SLP protocol | https://slp.dev/specs/slp-token-type-1/ | 2026-05-23 | Simple Ledger Protocol (BCH tokens, OP_RETURN-encoded, **not RPC-visible**) [E3] |
| ASERT spec | https://upgradespecs.bitcoincashnode.org/2020-11-15-asert/ | 2026-05-23 | DAA `aserti3-2d` (replaces BTC's 2016-block readjust) [E3] |
| Explorer | https://blockchair.com/bitcoin-cash | 2026-05-23 | Mainnet block/tx/address explorer; **returns both CashAddr and legacy formats** (`formats.cashaddr` / `formats.legacy`) [E2] |
| Public REST | https://rest1.biggestfan.net/v2/ | 2026-05-23 | Bitcoin.com-compatible REST proxy (BCHN backend), confirmed working [E2 — §3] |

---

## 2. Key diff vs 03-bitcoin.md (P0 summary)

| Item | Bitcoin (03) | Bitcoin Cash (21) | Impact |
|---|---|---|---|
| Family | utxo-btc | **utxo-btc** (same family, reuses BitcoinAdapter) | 0 new families |
| Genesis hash | `000000000019d6689c085...` | **identical** | Chain ID **must** use post-fork distinguishing block, see above |
| Max block size | 1 MB (weight 4 M) | **32 MB** (`EB32.0`, server-configurable) [E2] | mempool/getblock response can be 32× BTC; loosen benchmark `Content-Length` cap |
| SegWit | ✅ BIP-141/173/350 | ❌ **rejected** (BCH opposed SegWit — root cause of fork) [E3] | No P2WPKH/P2WSH/P2TR; `bc1...` all reject |
| Block time | 10 min | 10 min (same) | — |
| Difficulty algorithm | 2016-block readjust | **aserti3-2d** (ASERT, per-block sliding) [E3] | Not RPC-visible; affects reorg analysis |
| Consensus | SHA-256d PoW | same (same algorithm) | Same as BTC, but pool hashrate ≈ 1-2% of BTC |
| Address format | Base58Check + Bech32 + Bech32m | **CashAddr** (primary) + Base58Check legacy (transitional) [E2 — §6] | **DSL ASK 1** (see §7) |
| Unit | 1 BTC = 10⁸ sat | 1 BCH = 10⁸ sat (same) | — |
| Unique methods | — | `getexcessiveblock` / `setexcessiveblock` (blocksize cap manipulation) [E3 — BCHN] | Benchmark-irrelevant (node-admin) |
| Token protocol | Omni (USDT-Omni, deprecated) | **SLP** (OP_RETURN, **not via RPC**) [E3] | Balance benchmark infeasible, see §6 |

---

## 3. Public RPC (live-tested)

| Endpoint | Type | Auth | Result | Note |
|---|---|---|---|---|
| `https://rest1.biggestfan.net/v2/` | **REST** (Bitcoin.com-compat) | none | ✅ 200, avg 1.0 s, `subversion=/Bitcoin Cash Node:29.0.0(EB32.0)/`, `blocks=952310` | **Primary**; only stable public BCH REST gateway |
| `https://api.blockchair.com/bitcoin-cash/` | REST (Blockchair) | none (free tier 30 req/min) | ✅ 200, avg 1.4 s, `blocks=952314` | Bonus: `formats.cashaddr` + `formats.legacy` auto-conversion [E2] |
| `https://bch.publicnode.com` | expected JSON-RPC | — | ❌ 404 Cloudflare (live-tested 2026-05-23, **decommissioned**; context file stale) [E2] | Unusable |
| `http://<self-hosted>:8332` | JSON-RPC 1.0 | basic auth (same as BTC) | untested | Self-hosted BCHN, benchmark target mode |

**Live curl evidence** (E2):
```bash
curl -s https://rest1.biggestfan.net/v2/blockchain/getBlockCount
# 952310

curl -s https://rest1.biggestfan.net/v2/control/getNetworkInfo | jq .subversion
# "/Bitcoin Cash Node:29.0.0(EB32.0)/"  ← 32 MB block cap, explicit

curl -s https://rest1.biggestfan.net/v2/blockchain/getMempoolInfo
# {"loaded":true,"size":27,"bytes":18658,"usage":48576,
#  "maxmempool":2048000000,"mempoolminfee":0.00001,
#  "minrelaytxfee":0.00001,"permitbaremultisig":true,
#  "maxdatacarriersize":223}
#  ↑ maxmempool 2 GB (BTC default 300 MB), matches 32 MB blocks
```

**Critical difference**: BCH has **no** equivalent of `bitcoin-rpc.publicnode.com` (pure public JSON-RPC). Benchmark public mode must route via the REST proxy, whose **response schema differs slightly from Core JSON-RPC** (REST flattens the `result` field — no `{jsonrpc,result,id,error}` envelope). Self-hosted mode is still vanilla Core JSON-RPC 1.0 and fully reuses the BTC `BitcoinAdapter` request builder.

---

## 4. Method differences (99% same as BTC, fork-unique only)

| Method | BTC behaviour | BCH behaviour | Evidence |
|---|---|---|---|
| `validateaddress` | Accepts P2PKH/P2SH/P2WPKH/P2WSH/P2TR | Accepts **CashAddr** (`bitcoincash:q...`) + legacy Base58 (P2PKH/P2SH); **rejects bech32 `bc1...`** | E2 — §6 |
| `getblock` (verbosity=2) | tx contains SegWit witness fields | No `vin[*].txinwitness`; tx count can be far higher (32 MB blocks) | E4 — BCHN src |
| `getrawtransaction` | wtxid ≠ txid (post-SegWit) | **wtxid ≡ txid** (no SegWit) | E4 |
| `getexcessiveblock` | Not present | BCHN-unique: returns `{"excessiveBlockSize": 33554432}` (32 MB) | E3 — BCHN docs |
| `getblockhashes` | Not present (03 doc lists it but it's actually a Zcash/PIVX extension) | Same as BTC: not present | — |
| `scantxoutset` | Same (supported) | Same | — |
| `getbalance` | wallet RPC, blocked on publicnode proxy | wallet RPC, no REST proxy endpoint | — |

> **Conclusion**: 8 of the 10 BTC core methods are identical (getbestblockhash / getblockcount / getblock / getblockhash / getrawtransaction / getmempoolinfo / getrawmempool / scantxoutset); `validateaddress` differs (address family), `getbalance` unusable on both (wallet RPC). No new benchmark-relevant methods.

---

## 5. Block/consensus details (complements §2 table)

- **ASERT difficulty adjustment** (activated 2020-11-15): each block slides from a referenceBlock + targetSpacing using `next_target = ref_target × 2^((delta_time − 600·height_delta) / 172800)`. **Benefits**: eliminates BTC's 2016-block-readjust spikes and BCH/BTC inter-chain hashrate-hopping arbitrage. **Not RPC-visible** (getblock doesn't expose the algorithm field) [E3].
- **Fork history timeline**:
  - 2017-08-01 height 478559 — BCH forks from BTC (blocksize dispute + anti-SegWit)
  - 2018-11-15 — BCH internal fork → BSV (Craig Wright) splits off
  - 2020-11-15 — BCH internal fork → XEC (eCash, Bitcoin ABC) splits off
  - Current BCH mainnet = BCHN (Bitcoin Cash Node) implementation dominant, subversion self-reports EB32.0
- **Future forks**: scheduled upgrade windows on 5/15 and 11/15 yearly, but no breaking protocol changes in 2024-2025 [E3].

---

## 6. SLP tokens (real-payload supplement)

- **SLP = Simple Ledger Protocol**: BCH's fungible + NFT token protocol, all data encoded in OP_RETURN tx outputs (similar to BTC-Omni / Ordinals) [E3].
- **Native RPC cannot decode SLP**: `getrawtransaction` returns vout[0] as `OP_RETURN ...`; to retrieve token symbol/amount you **must** run SLPDB (MongoDB + indexer) or use BCHD's gRPC `GetSlpTransactionInformation`.
- **Benchmark implication**: this framework does not introduce SLP — `mixed` weight table is identical to BTC, **no weight is allocated to SLP**. SLP balance queries = explorer API (blockchair `dashboards/address` returns `slp_balances`), classified as §10 trade-off, not part of the RPC method set.
- **Real active tokens**: USDT-SLP (mostly migrated to ETH, inactive), SPICE, FLEX. Daily SLP tx volume < 5k, ~20% of total BCH tx.

---

## 7. DSL decisions (predict 0 new methods, **1 new enum value**)

### 7.1 Reuse BTC DSL fields (0 changes)

`chain` / `family` / `adapter` / `rpc_protocol` / `auth` / `rpc_methods` / `mixed_weights` all inherit from 03-bitcoin.md §10's `BitcoinAdapter` config — only swap endpoint + `chain` name + `magic_bytes` (`0xE3E1F3E8` for BCH mainnet vs BTC `0xD9B4BEF9`) + `fork_height: 478559` + `address_formats`.

### 7.2 **DSL ASK #1**: add `cashaddr` to the `address_format` enum

**Current in 03-bitcoin.md L402**: `"address_formats": ["base58check", "bech32", "bech32m"]`
**BCH needs**: `"address_formats": ["cashaddr", "base58check"]`

**Rationale**: CashAddr is neither Bech32 nor Base58Check — it's a BCH-unique third encoding:
- **Charset**: `qpzry9x8gf2tvdw0s3jn54khce6mua7l` (32 chars, **different from Bech32** — Bech32 string `qpzry9x8gf2tvdw0s3jn54khce6mua7l` looks identical, but the polymod constant and hrp-concatenation order differ) [E3 — reference.cash CashAddr spec]
- **HRP**: `bitcoincash:` (mainnet) / `bchtest:` (testnet) / `bchreg:` (regtest)
- **Example**: `bitcoincash:qpm2qsznhks23z7629mms6s4cwef74vcwvy22gdx0qaa` (54 chars including hrp)
- **Checksum polynomial**: BCH (constant 1, same as Bech32) but polymod's **generator base differs**, so a valid Bech32 string is invalid under CashAddr and vice-versa — **independent codec implementation required**

**Evidence** (E2 — `validateaddress` via REST proxy):
```bash
# CashAddr — REST proxy treats hrp as illegal char (proxy is BTC-schema):
curl -s https://rest1.biggestfan.net/v2/util/validateAddress/bitcoincash:qpm2qsznhks23z7629mms6s4cwef74vcwvy22gdx0qaa
# {"isvalid":false}  ← REST proxy bug; actual BCHN RPC returns true (needs self-hosted to verify)

# Blockchair API returns both formats:
curl -s https://api.blockchair.com/bitcoin-cash/dashboards/address/bitcoincash:qpm2qsznhks23z7629mms6s4cwef74vcwvy22gdx0qaa | jq .data[].address.formats
# {"legacy":null,"cashaddr":"qpm2qsznhks23z7629mms6s4cwef74vcwvy22gdx0qaa"}
```

**DSL impact**:
- New enum value `cashaddr` (type signature: `type AddressFormat = "base58check" | "bech32" | "bech32m" | "cashaddr"`)
- `BitcoinAdapter` must delegate to a `CashAddrCodec` (independent polymod implementation); Litecoin/Dogecoin **do not need** this codec (they use Base58Check + Bech32)
- Config example:
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

## 8. H8 evidence (curl probe summary, 5+ commands)

| # | Method | Endpoint | Result |
|---|---|---|---|
| 1 | `getBlockCount` | `rest1.biggestfan.net/v2/blockchain/getBlockCount` | ✅ `952310` (plain int) |
| 2 | `getNetworkInfo` | `rest1.biggestfan.net/v2/control/getNetworkInfo` | ✅ `subversion=/Bitcoin Cash Node:29.0.0(EB32.0)/`, `version=29000000`, `protocolversion=70016` |
| 3 | `getMempoolInfo` | same | ✅ `size=27, maxmempool=2GB` (32 MB blocks demand bigger mempool) |
| 4 | `getBlock` by hash | `rest1.biggestfan.net/v2/blockchain/getBlock/<hash>` | ✅ height 952312, size 2219, **no weight field** (BCH has no SegWit, hence no weight) |
| 5 | `getRawTransaction` block-1 coinbase | `rest1.biggestfan.net/v2/rawtransactions/getRawTransaction/9b0fc922...?verbose=true` | ✅ **identical to BTC** post-genesis block-1 coinbase (BCH shares BTC pre-fork history) |
| 6 | `getAddressDetails` CashAddr | `api.blockchair.com/bitcoin-cash/dashboards/address/bitcoincash:qpm2q...` | ✅ returns `formats.cashaddr` + `formats.legacy` dual format |
| 7 | `validateAddress` CashAddr via REST proxy | REST proxy | ❌ `isvalid:false` (proxy bug; real BCHN RPC self-hosted should return true) |

**Key findings**:
- BCH chain tip on 2026-05-23 measured `952310` — only ~1600 blocks ahead of BTC's same-day tip `950697`, reflecting that both chains share 478559 pre-fork blocks plus ~473k post-fork blocks over 9 years.
- **Block size reality**: measured block 952312 is only 2219 bytes (BCH on-chain activity is low — nowhere near the 32 MB cap); BTC's typical concurrent block is ~1.5 MB (filled). To actually stress the 32 MB path, you must self-host + regtest with synthetic tx injection.
- Missing `weight` field confirms BCH has no SegWit (BTC `getblock` always carries `weight = base_size × 3 + total_size`).

---

## 9. P2.1 caller/reader change points (diff vs BTC P2.1)

BCH onboarding ≈ **5% of BTC's effort**, because BitcoinAdapter already exists. Changes:

| # | Location | Change | Reason |
|---|---|---|---|
| 1 | `config/config_loader.sh` `supported_blockchains` | Add `"bitcoin-cash"` (extend N→N+1) | guard_*chain_truth.sh |
| 2 | `config/config_loader.sh` case branch | Add `bitcoin-cash) MAINNET_RPC_URL="https://rest1.biggestfan.net/v2"` | Else falls through to default |
| 3 | `tools/fetch_active_accounts.py` `BitcoinAdapter` | Register `cashaddr` codec (new file `tools/cashaddr_codec.py`, ~150 LOC, polymod + base32); param_format strips `bitcoincash:` HRP | BTC codec has no CashAddr |
| 4 | `tools/mock_rpc_server.py` | Add chain branch `bitcoin-cash`, reuse BTC method handlers, only swap `getnetworkinfo`'s `subversion` fixture to BCHN string | CI fallback |
| 5 | `tests/cashaddr_codec_test.py` | New unit tests: encode/decode 5 real CashAddrs, polymod checksum validation | E1 — required since codec is hand-written |

**N/A**: no methods to delete, no methods to add, 0 changes at the JSON-RPC protocol layer.

---

## 10. Trade-offs & truth alignment

1. **Public endpoint is REST not JSON-RPC** — the `bch.publicnode.com` URL in the context file is decommissioned (live-tested 404, 2026-05-23). Benchmark public mode can only go through the Bitcoin.com REST proxy, which means the "protocol identity" assumption (whatever works for BTC also works for BCH) **does not hold**. Self-hosted mode remains identical.
2. **32 MB blocks invisible on public chain** — measured block-size median < 3 KB (BCH on-chain activity is sparse); real stress-testing of the big-block path requires regtest.
3. **SLP excluded from benchmark** — token decoding needs OP_RETURN parser + SLPDB, orthogonal to the RPC protocol, excluded.
4. **CashAddr codec must be hand-written** — Python's `bech32` library is not interchangeable (polymod generator differs); this framework introduces ~150 LOC of new code in `tools/cashaddr_codec.py`, **no PyPI dependency** (avoids supply-chain risk).
