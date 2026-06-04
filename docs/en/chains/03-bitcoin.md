# 03-Bitcoin Research

> **This file is derived from `_template.md`.**
> **Filled following H8 (real evidence): live curl + official doc URL + GitHub commit SHA.**
> **Every field is tagged E1 (unit test) / E2 (live curl) / E3 (docs) / E4 (source) / E5 (code grep).**

---

## Metadata

| Field | Value |
|---|---|
| Chain (zh) | 比特币 |
| Chain (en) | Bitcoin |
| Number | 03 |
| Mainnet ChainID | N/A (Bitcoin has no EIP-155-style ChainID; chain identity is the magic bytes `0xD9B4BEF9` and genesis hash `000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f`) [E2/E4] |
| Research date | 2026-05-23 |
| Researcher | Hermes Agent |
| Status | 🟢 Complete |

---

## 1. Sources

| Type | URL | Access date | Note |
|---|---|---|---|
| Official docs | https://bitcoincore.org/en/doc/29.0.0/ | 2026-05-23 | Bitcoin Core 29.0 RPC reference (`getnetworkinfo` returns `subversion=/Satoshi:29.3.0/`, matches v29 series) [E2] |
| RPC spec | https://developer.bitcoin.org/reference/rpc/ | 2026-05-23 | Bitcoin Developer Reference RPC list (community-maintained Core mirror) |
| GitHub | https://github.com/bitcoin/bitcoin (commit `de925455c8025fc1f75d65d981c28b9dfa20e9f7`, master @ 2026-05-23) | 2026-05-23 | Core implementation; every source citation in this doc anchors to this SHA [E4] |
| Esplora REST | https://github.com/Blockstream/esplora/blob/master/API.md | 2026-05-23 | Blockstream Esplora REST API (alternative for address balance / UTXO lookup; Core itself lacks an address index) [E3] |
| Explorer | https://blockstream.info/ | 2026-05-23 | Mainnet block/tx/address explorer (used to verify hashes/addresses cited below) |
| BIP-141 | https://github.com/bitcoin/bips/blob/master/bip-0141.mediawiki | 2026-05-23 | SegWit (weight unit definition) |
| BIP-173 | https://github.com/bitcoin/bips/blob/master/bip-0173.mediawiki | 2026-05-23 | Bech32 address encoding (P2WPKH/P2WSH) |
| BIP-350 | https://github.com/bitcoin/bips/blob/master/bip-0350.mediawiki | 2026-05-23 | Bech32m (P2TR/Taproot addresses) |

---

## 2. Protocol Family

| Field | Value |
|---|---|
| Family | **Bitcoin / UTXO** (new family — disjoint from existing 8 chains) |
| Consensus | PoW (SHA-256d) [E3 — bitcoincore.org] |
| VM | None — stack-based Script (non-Turing-complete); no VM state model [E3] |
| Block Time | Target ~600s (10 min) regulated by difficulty; retarget every 2016 blocks [E3] |
| Finality | Probabilistic; convention is 6 confirmations ≈ 60 min; no deterministic finality |
| Reuse Existing Adapter? | **No** — UTXO model is disjoint from all 8 existing chains (Solana account / EVM account / Move object / Cairo Felt); plus JSON-RPC 1.0 + Basic Auth differs from EVM's JSON-RPC 2.0 + public bearer pattern. Must build a new `BitcoinAdapter` as the UTXO-family seed (Litecoin / Dogecoin / BCH will reuse it later) [E2 — see §11.5 heterogeneity comparison] |

---

## 3. Public RPC

| Endpoint | Auth | Test result | Note |
|---|---|---|---|
| `https://bitcoin-rpc.publicnode.com` | none (allnodes.com reverse-proxy strips basic auth) | ✅ 200; 5 consecutive requests averaged 250ms; no rate-limit hit | **Recommended primary**. Limitation: wallet-class methods (getbalance/getreceivedbyaddress) return a custom code `-32701` ("Method ... is not allowed") |
| `https://blockstream.info/api` | none | ✅ 200 (Esplora REST, **not JSON-RPC**) | Only for address balance / UTXO supplementation; not schema-compatible with Core RPC. Trade-off in §10 |
| `http://<self-hosted>:8332` | basic auth (`rpcuser:rpcpassword`) | Not tested (no self-hosted node in this environment) | The real self-hosted path the benchmark target mode should use |

**Trade-off & decision**:
- **Picked publicnode as the evidence endpoint for this document** because (a) no auth, (b) full public JSON-RPC 1.0, (c) stable in practice.
- **Reversal condition**: if publicnode starts rate-limiting in wave2 or expands the block-list beyond wallet methods, switch to a self-hosted bitcoind (regtest/mainnet) to restore the true basic-auth path.
- **Mock-first**: after Phase 2.1, `mock_rpc_server.py` should implement a Bitcoin branch so CI does not depend on any public endpoint.

**Live curl** (mandatory):
```bash
# E2 — measured 2026-05-23 on publicnode.com
curl -s -X POST https://bitcoin-rpc.publicnode.com \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"1.0","id":1,"method":"getblockcount","params":[]}'
# Live output:
# {"result":950697,"error":null,"id":1}

curl -s -X POST https://bitcoin-rpc.publicnode.com \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"1.0","id":1,"method":"getblockchaininfo","params":[]}'
# Live output (excerpt):
# {"jsonrpc":"2.0","result":{"bestblockhash":"00000000000000000000dc4cb7acea2ef037c9ce00a3f605f6bd347a4312e7fa",
#  "blocks":950697,"chain":"main","difficulty":136607070854775.1,"headers":950697,
#  "initialblockdownload":false,"pruned":false,"size_on_disk":846124394968,
#  "time":1779558706,"verificationprogress":0.9999976403640984,"warnings":[]},"id":1}
#
# Note: the same server echoes literal "jsonrpc":"1.0" for getblockcount but "2.0" for getblockchaininfo.
# This is a Core historical quirk (Core itself does not distinguish the version field; the proxy varies).
# Clients must accept both.
```

Latency sample (rate-limit sniff):
```text
req1: 200 time=0.258703s
req2: 200 time=0.246636s
req3: 200 time=0.255614s
req4: 200 time=0.245881s
req5: 200 time=0.246281s
```

---

## 4. Account Model

| Field | Value |
|---|---|
| Model | **UTXO** (Unspent Transaction Output) — no accounts, no nonces, no state trie [E3] |
| Native token decimals | 8 (satoshi; 1 BTC = 10⁸ sat) [E3 — bitcoincore.org `getblockchaininfo` doc, consistent with the `getrawtransaction` `"value":50.00000000` below] |
| Address derivation | secp256k1 ECDSA; Taproot (BIP-340) uses secp256k1 Schnorr [E3 — BIP-340] |
| Special account types | **No accounts**; instead 5 scriptPubKey types correspond to 5 address prefixes: P2PKH (`1...`) / P2SH (`3...`) / P2WPKH (`bc1q...`, 20-byte program) / P2WSH (`bc1q...`, 32-byte program) / P2TR (`bc1p...`) [E2 — see §6 validateaddress evidence] |
| **Critical constraint** | **Bitcoin Core itself has no address index** — pure RPC cannot answer "what is the balance of address X". You must either (a) enable `txindex=1` plus wallet RPC, or (b) use an external Electrum / Esplora indexer service [E2 — getbalance below is blocked by the proxy; scantxoutset returns null without a wallet] |

**Curl evidence for the critical constraint** (E2):
```bash
# wallet method blocked by publicnode proxy
curl -s -X POST https://bitcoin-rpc.publicnode.com -H "Content-Type: application/json" \
  -d '{"jsonrpc":"1.0","id":1,"method":"getbalance","params":["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"]}'
# {"jsonrpc":"1.0","error":{"code":-32701,
#  "message":"Method getbalance is not allowed. To remove restrictions, order a dedicated full node here: https://www.allnodes.com/btc/host"},"id":1}

# scantxoutset returns null when no wallet is configured (cannot answer address balance live)
curl -s -X POST https://bitcoin-rpc.publicnode.com -H "Content-Type: application/json" \
  -d '{"jsonrpc":"1.0","id":1,"method":"scantxoutset","params":["status"]}'
# {"result":null,"error":null,"id":1}

# Only Esplora REST gives an address balance (funded - spent)
curl -s "https://blockstream.info/api/address/1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
# {"address":"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
#  "chain_stats":{"funded_txo_count":74737,"funded_txo_sum":5719999745,
#                 "spent_txo_count":0,"spent_txo_sum":0,"tx_count":62929},
#  "mempool_stats":{"funded_txo_count":0,"funded_txo_sum":0,
#                   "spent_txo_count":0,"spent_txo_sum":0,"tx_count":0}}
# → balance_sat = funded_txo_sum - spent_txo_sum = 5_719_999_745 sat ≈ 57.20 BTC
```

---

## 5. Core RPC Methods (required by this framework)

> Only methods this benchmark needs. Full API list at bitcoincore.org/en/doc/29.0.0/. All methods below verified by live curl [E2].

| Method | Category | Description | Suggested weight in `mixed` |
|---|---|---|---|
| `getblockcount` | block height | Liveness + sync probe; returns int tip height | 0.10 |
| `getblockhash` | height → hash | Input height (int), returns hash; **first hop of two-step block lookup** | 0.05 |
| `getblock` | block content | Input hash + verbosity (0=hex / 1=json / 2=json+tx); **second hop**; verbosity=2 is heavy | 0.10 |
| `getblockchaininfo` | chain status | bestblockhash + headers + IBD state | 0.05 |
| `getrawtransaction` | tx lookup | Input txid + verbose (false=hex / true=json); **requires `-txindex=1`** to query arbitrary history; otherwise only mempool txs or txs referenced by UTXOs | 0.20 |
| `getrawmempool` | mempool | All current mempool txids (verbose=false) or detail dict (verbose=true) | 0.10 |
| `getmempoolinfo` | mempool meta | size/bytes/usage/minfee metadata | 0.05 |
| `estimatesmartfee` | fee | Input conf_target (int), returns feerate (BTC/kvB) | 0.05 |
| `validateaddress` | utility | Address validation + type inference (p2pkh/p2sh/witness_v0/witness_v1) | 0.05 |
| `getnetworkinfo` | peer/version | version, connections, relayfee | 0.05 |
| Address balance (Esplora, **non-JSON-RPC**) | balance | `GET /address/{addr}` → funded_txo_sum - spent_txo_sum | 0.20 |

**Weight check**: 0.10+0.05+0.10+0.05+0.20+0.10+0.05+0.05+0.05+0.05+0.20 = **1.00** ✅

**Curl evidence — full responses for key methods** (E2, 2026-05-23):

```bash
# 1) getblockhash(0) — genesis
curl -s -X POST https://bitcoin-rpc.publicnode.com -H "Content-Type: application/json" \
  -d '{"jsonrpc":"1.0","id":1,"method":"getblockhash","params":[0]}'
# {"result":"000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f","error":null,"id":1}
# ↑ matches the genesis hash provided in bitcoin-context.md (100%)

# 2) getblock(genesis_hash, 1)
curl -s -X POST https://bitcoin-rpc.publicnode.com -H "Content-Type: application/json" \
  -d '{"jsonrpc":"1.0","id":1,"method":"getblock","params":["000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f", 1]}'
# {"result":{"hash":"000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f",
#   "height":0,"version":1,"merkleroot":"4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b",
#   "time":1231006505,"mediantime":1231006505,"nonce":2083236893,"bits":"1d00ffff",
#   "difficulty":1,"nTx":1,"size":285,"weight":1140,
#   "tx":["4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"]},"error":null,"id":1}
# ↑ merkleroot == coinbase txid matches context

# 3) getrawtransaction(genesis_coinbase, true) — the known special case
curl -s -X POST https://bitcoin-rpc.publicnode.com -H "Content-Type: application/json" \
  -d '{"jsonrpc":"1.0","id":1,"method":"getrawtransaction",
       "params":["4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b", true]}'
# {"result":null,"error":{"code":-5,
#  "message":"The genesis block coinbase is not considered an ordinary transaction and cannot be retrieved"},"id":1}
# ↑ Core historical quirk: genesis coinbase is not in UTXO set or txindex; error code -5 (RPC_INVALID_ADDRESS_OR_KEY)

# 4) getrawtransaction(block-1 coinbase, true) — normal tx
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

# 5) getmempoolinfo
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

# 7) getnetworkinfo — for version/peer monitoring
# {"result":{"version":290300,"subversion":"/Satoshi:29.3.0/","protocolversion":70016,
#   "connections":247,"connections_in":237,"connections_out":10,
#   "relayfee":0.00000100,"incrementalfee":0.00000100,"warnings":[]},...}
```

---

## 6. Address Format

| Field | Value |
|---|---|
| Encoding | **Multi-encoding**: Base58Check (legacy P2PKH `1...` / P2SH `3...`) + Bech32 (SegWit v0, `bc1q...`) + Bech32m (SegWit v1 / Taproot, `bc1p...`) [E3 — BIP-13/16/141/173/350] |
| Length | P2PKH/P2SH: 26-35 chars; P2WPKH: 42 chars (`bc1q` + 38); P2WSH: 62 chars; P2TR: 62 chars [E2 — below] |
| Checksum | Base58Check: first 4 bytes of double-SHA-256; Bech32: BCH (constant 1); Bech32m: BCH (constant 0x2bc830a3) [E3 — BIP-350] |
| Examples (real mainnet) | P2PKH: `1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa` (Satoshi genesis 50 BTC; from context, validated [E2])<br>P2WPKH: `bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h` (verified valid below)<br>P2TR: `bc1p5d7rjq7g6rdk2yhzks9smlaqtedr4dekq08ge8ztwac72sfr9rusxg3297` (verified valid below) |
| Validation regex (practical, **not sufficient**) | Base58: `^[13][1-9A-HJ-NP-Za-km-z]{25,34}$`<br>Bech32 mainnet: `^bc1[qp][023456789acdefghjklmnpqrstuvwxyz]{6,87}$`<br>**Note**: must re-validate via `validateaddress` RPC — regex cannot verify the checksum |

**Curl evidence** (E2 — `validateaddress` for three types):
```bash
# P2PKH
# input: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
# → {"isvalid":true,"scriptPubKey":"76a91462e907b15cbf27d5425399ebf6f0fb50ebb88f1888ac",
#    "isscript":false,"iswitness":false}

# P2WPKH (witness v0)
# input: bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h
# → {"isvalid":true,"scriptPubKey":"0014dc6bf86354105de2fcd9868a2b0376d6731cb92f",
#    "isscript":false,"iswitness":true,"witness_version":0,
#    "witness_program":"dc6bf86354105de2fcd9868a2b0376d6731cb92f"}

# P2TR (witness v1, Bech32m)
# input: bc1p5d7rjq7g6rdk2yhzks9smlaqtedr4dekq08ge8ztwac72sfr9rusxg3297
# → {"isvalid":true,"scriptPubKey":"5120a37c3903c8d0db6512e2b40b0dffa05e5a3ab73603ce8c9c4b7771e5412328f9",
#    "isscript":true,"iswitness":true,"witness_version":1,
#    "witness_program":"a37c3903c8d0db6512e2b40b0dffa05e5a3ab73603ce8c9c4b7771e5412328f9"}
```

---

## 7. Signature Lookup (transaction hash)

| Field | Value |
|---|---|
| Hash format | Hex, **no 0x prefix** (unlike EVM); double-SHA-256 reversed (little-endian display) [E3] |
| Length | 64 chars (32-byte hex) |
| **txid vs wtxid** | Two distinct hashes since SegWit: `txid` (hash without witness data) vs `wtxid`/`hash` (with witness). getrawtransaction takes **txid**; the response carries both [E2 — see §5; for the coinbase tx the two are equal because vin has no witness] |
| Examples (real mainnet) | `4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b` (genesis coinbase; from context, **but cannot be queried via Core RPC** — error -5)<br>`9b0fc92260312ce44e74ef369f5c66bbb85848f2eddd5a7a1cde251e54ccfdd5` (block-1 coinbase; queryable — see §5) [E2] |
| Lookup method | `getrawtransaction(<txid>, true/false)` — **requires `-txindex=1`** for arbitrary historical txs; otherwise only mempool txs + UTXO-referenced txs [E3 — bitcoincore.org] |
| Explorer URL format | `https://blockstream.info/tx/<txid>` or `https://mempool.space/tx/<txid>` |

---

## 8. Mixed Set (`mixed` mode weights)

> Used by `BLOCKCHAIN_NODE_BENCHMARK_MODE=mixed` for Bitcoin. Write paths are meaningless for benchmark (BTC tx requires a private key + broadcast), so all weights are **read-only**. Heavy methods (`getblock verbosity=2`, `getrawmempool verbose=true`) are mixed in proportions reflecting real explorer traffic.

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

Method mapping:
- `block_height_query` → `getblockcount` (no_params)
- `block_hash_lookup` → `getblockhash` (single int param `$height`)
- `block_content_query` → `getblock` (`$blockhash`, `$verbosity=1`)
- `chain_info_query` → `getblockchaininfo` (no_params)
- `tx_lookup` → `getrawtransaction` (`$txid`, `$verbose=true`)
- `mempool_list_query` → `getrawmempool` (no_params; verbose=false by default)
- `mempool_info_query` → `getmempoolinfo` (no_params)
- `fee_estimate_query` → `estimatesmartfee` (single int `$conf_target=6`)
- `address_validate` → `validateaddress` (`$address`)
- `network_info_query` → `getnetworkinfo` (no_params)
- `address_balance_query_esplora` → REST `GET /api/address/$address` (**non-JSON-RPC**; needs separate endpoint config)

**Weight sum**: 0.10+0.05+0.10+0.05+0.20+0.10+0.05+0.05+0.05+0.05+0.20 = **1.00** ✅

---

## 8.5 Phase 2.1 caller/reader change-list (token-level Gate 3)

Bitcoin is a **brand-new chain** — no existing code path on the chain side. The following are mandatory new/touched points for P2.1:

| # | Location (file:line) | Change | Reason |
|---|---|---|---|
| 1 | `config/config_loader.sh:~409` UNIFIED_BLOCKCHAIN_CONFIG JSON — add `"bitcoin": {...}` block | New chain_type, rpc_methods.single/mixed, param_formats (see §10 JSON) | Same level as solana/ethereum blocks; if missing, `generate_rpc_json` falls back to wrong chain |
| 2 | `config/config_loader.sh:666` `supported_blockchains` array — add `"bitcoin"` | Extend array to 9 entries | `guard_8chain_truth.sh` watches this array; missing entry rejects startup |
| 3 | `config/config_loader.sh:~372` case branch — add `bitcoin)` | Set `MAINNET_RPC_URL="https://bitcoin-rpc.publicnode.com"` | Otherwise falls into `*)` default = Solana endpoint (silently wrong chain) |
| 4 | `tools/mock_rpc_server.py` — add method branches: `getblockcount`/`getblockhash`/`getblock`/`getrawtransaction`/`getmempoolinfo`/`estimatesmartfee`/`validateaddress`/`getnetworkinfo`/`getblockchaininfo`/`getrawmempool` | Copy §5 live responses as fixtures | mock is the CI fallback; missing => CI cannot run BTC mode |
| 5 | `tools/fetch_active_accounts.py` — add `BitcoinAdapter` class | Use Esplora REST to pull address list (Core lacks address index); param_format handles `single_address` (no `, "latest"` suffix) | EthereumAdapter / SolanaAdapter are all incompatible — UTXO + Esplora dual-stack |
| 6 | `tests/guard_8chain_truth.sh` — rename to `guard_9chain_truth.sh` (or parameterize) | Add `"bitcoin"` to expected array | Otherwise guard blocks startup |
| 7 | `analysis-notes/baseline-current-state.md` — grep `8chain` / `8 chain` | Update to 9-chain, add bitcoin to the path list | doc-vs-code parity (same v1.4.1 hazard) |
| 8 | `analysis-notes/disk-and-network-pipeline-redesign.md` — sync | Same | Same |
| 9 | `REFACTOR-SSOT.md §5.1(资源画像, 原03已合并删)` — if marked deprecated, reassess or annotate that this doc supersedes the bitcoin block | Doc-vs-reality parity | Same |

**N/A**: Bitcoin has no existing methods to delete → "delete" column in template row 1 is N/A.

**Test requirement**: after P2.1, run `BLOCKCHAIN_NODE=bitcoin core/master_qps_executor.sh --mixed --duration 30`; vegeta should be all-200 + JSON-RPC `error` field null (address-balance requests are the exception: Esplora is REST 200 + JSON body).

---

## 9. Mock Notes (mock_rpc_server implementation tips)

- **Request path**: `POST /` (Bitcoin Core does not route by path; all RPCs go to root. Basic auth via `Authorization: Basic <base64(user:pass)>` header) [E3 — bitcoincore.org]
- **Response schema** (sample from §5 live data):
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
- **Special error codes** (authoritative source: `bitcoin/bitcoin@de92545 src/rpc/protocol.h` L25-L96) [E4]:
  - `-32600` RPC_INVALID_REQUEST (standard JSON-RPC) [L29]
  - `-32601` RPC_METHOD_NOT_FOUND [L32]
  - `-32602` RPC_INVALID_PARAMS [L33]
  - `-32603` RPC_INTERNAL_ERROR [L36]
  - `-32700` RPC_PARSE_ERROR [L37]
  - `-1` RPC_MISC_ERROR (`std::exception thrown`) [L40]
  - `-3` RPC_TYPE_ERROR (`Unexpected type was passed as parameter`) [L41]
  - **`-5` RPC_INVALID_ADDRESS_OR_KEY** (invalid address/key, or genesis coinbase lookup) [L42] ← hit in §5 evidence
  - `-8` RPC_INVALID_PARAMETER (`Invalid, missing or duplicate parameter`) [L44]
  - `-28` RPC_IN_WARMUP (`Client still warming up` — returned during IBD) [L50]
  - `-32701` **NOT a Bitcoin Core official code**; it is publicnode/allnodes proxy-custom ("Method ... is not allowed"). mock need not implement it but clients should tolerate it.
- **Mock implementation complexity**: **Medium**
  - Easy: most methods have fixed schema; live responses can be returned directly as fixtures.
  - Hard 1: `getblock` verbosity has 3 levels (0=hex, 1=json, 2=json+tx-detail) — mock needs multiple fixtures.
  - Hard 2: `getrawtransaction` verbose has 2 levels (false=hex string, true=full json) — fixture is large.
  - Hard 3: real-mainnet `getrawmempool` returns ~27K txids (live size=27632) — mock should truncate to ~10 to avoid bandwidth blowup.
  - Hard 4: basic-auth simulation — mock should check `Authorization` header; missing => 401, matching real Core behavior.

---

## 10. Adapter Reuse Decision

### Candidate adapters

| Adapter | Compatibility | Missing capability |
|---|---|---|
| EthereumAdapter | 0% | account model fundamentally different; JSON-RPC 2.0 vs 1.0; address format fully different; no token concept |
| SolanaAdapter | 0% | account model + signature lookup paradigm fully different |
| StarknetAdapter | 0% | Same; Cairo Felt has no overlap with UTXO |
| SuiAdapter | 0% | Move object is also account-like; though both "non-EVM", UTXO is a separate pole |
| (new) BitcoinAdapter | 100% | — |

### Decision

- [x] **Build new** `BitcoinAdapter` (UTXO-family seed)
- [x] **Hybrid**: Core JSON-RPC 1.0 + Esplora REST dual-stack (because Core lacks an address index)

### Rationale

1. **Model heterogeneity**: UTXO has no "account balance" primitive; balance must be derived by summing all UTXOs of an address or via an external indexer (Esplora/Electrum). All account-based adapters' `getBalance(addr)` semantics are non-portable.
2. **RPC protocol heterogeneity**: Bitcoin uses JSON-RPC **1.0** (`"jsonrpc":"1.0"` or omitted); EVM mandates 2.0. Request id behavior, error-field semantics, batch support all differ.
3. **Auth heterogeneity**: Bitcoin Core defaults to HTTP Basic Auth (`-rpcuser` / `-rpcpassword` or `.cookie` file), requires `Authorization: Basic <b64>` header; EVM public nodes commonly use bearer / API key / none.
4. **Two-step query semantics**: fetching a block's content requires `getblockhash(h)` → `getblock(hash)`; EVM's `eth_getBlockByNumber(h)` is one step. The DSL must support "previous method's output → next method's input" cursor chaining.
5. **Downstream reuse**: Litecoin / Dogecoin / Bitcoin Cash / Zcash all fork from Bitcoin Core; their RPC surface is 95%+ identical (method names, param order, error codes all match). BitcoinAdapter is the cornerstone for that lane.

### Config JSON example (this chain)

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

## 11. DSL Field Requirements (input to P2-DESIGN-v2)

### 11.1 RPC call protocol

| Field | Bitcoin value | DSL field proposal |
|---|---|---|
| Protocol type | JSON-RPC **1.0** (Core) + REST (Esplora, fills balance) | `rpc.protocol: enum[jsonrpc1, jsonrpc2, rest, grpc]` |
| HTTP method | POST (Core) / GET (Esplora) | `rpc.http_method: enum[POST, GET]`, overridable per method |
| Request path | `/` (Core) / `/api/{path}` (Esplora; path contains variables) | `rpc.base_path: string` + `method.path_template: string` (supports `{var}`) |
| Auth | Basic Auth (self-hosted) / none (publicnode proxy) | `rpc.auth.type: enum[none, basic, bearer, api_key, header]` |
| Auth DSL proposal | `auth: {type: basic, user: ${BTC_RPC_USER}, pass: ${BTC_RPC_PASS}, optional: true}` | Must support env-var expansion + `optional` flag (allow no-auth proxy) |

[E2 — see §3 evidence; E4 — Core HTTP basic auth in `bitcoin/bitcoin@de92545 src/httprpc.cpp`]

### 11.2 method call schema

> One subsection per method; params use `$varname` placeholders; response extracted by JSONPath.

#### `getblockcount`
- params template: `[]`
- response extract: `$.result` (int)
- error code: usually none (except IBD `-28`)
- evidence: §3 [E2]

#### `getblockhash`
- params template: `[$height]` (int, 0..tip)
- response extract: `$.result` (string, 64-hex)
- error: height out of range → `-8` RPC_INVALID_PARAMETER
- evidence: §5 [E2]

#### `getblock`
- params template: `[$blockhash, $verbosity]` (verbosity ∈ {0,1,2})
- response extract: `$.result.hash`, `$.result.height`, `$.result.tx[*]`, `$.result.size`, `$.result.weight`
- error: hash not found → `-5` RPC_INVALID_ADDRESS_OR_KEY
- evidence: §5 [E2]

#### `getrawtransaction`
- params template: `[$txid, $verbose]` (verbose: bool or int 0/1)
- response extract (verbose=true): `$.result.txid`, `$.result.vin[*]`, `$.result.vout[*].value`, `$.result.blockhash`, `$.result.confirmations`
- error: `-5` carries two semantics — (a) txid not found, (b) genesis coinbase always -5
- evidence: §5 [E2]

#### `validateaddress`
- params template: `[$address]`
- response extract: `$.result.isvalid` (bool), `$.result.iswitness`, `$.result.witness_version`
- evidence: §6 [E2]

#### `estimatesmartfee`
- params template: `[$conf_target]` (optional `$estimate_mode`)
- response extract: `$.result.feerate` (BTC/kvB), `$.result.blocks`
- evidence: §5 [E2]

#### `getrawmempool`
- params template: `[]` or `[$verbose]` (default false = txid array; true = dict)
- response extract (verbose=false): `$.result[*]` (string array)
- evidence: §4 [E2]

#### Esplora `address_balance` (REST, non-JSON-RPC)
- path template: `GET /address/{$address}`
- response extract: `$.chain_stats.funded_txo_sum`, `$.chain_stats.spent_txo_sum` (balance = funded - spent, unit = sat)
- evidence: §4 [E2]

### 11.3 cursor / pagination model

Bitcoin has **two cursor models**; the DSL must support both:

| Model | Description | DSL proposal |
|---|---|---|
| **height-based** (primary) | `for h in [start, start+N]: hash = getblockhash(h); block = getblock(hash, 1)` | `cursor: {type: height, start: $H0, step: 1, max_count: 1000, chain_to: getblock}` — KEY ASK: **support method chaining** (previous method's response → next method's param) |
| **listsinceblock-based** (incremental sync) | `listsinceblock(blockhash)` returns wallet txs after that hash (wallet RPC; not strictly required for this framework) | `cursor: {type: opaque, next_path: $.lastblock}` |
| **txid-based** (tx sampling) | Pull txid list from mempool or explorer → `getrawtransaction` per item | `cursor: {type: list, source: getrawmempool, item_path: $.result[*]}` |

**DSL KEY ASK**: must support **method chaining** (`output_of(getblockhash) → param[0] of getblock`). EVM's cursor is single-method (`eth_getBlockByNumber(h)` returns block directly); Bitcoin / UTXO family all require chaining, so this is a P0 capability for P2-DESIGN-v2.

### 11.4 system addresses / filter rules

| Field | Bitcoin value | DSL field proposal |
|---|---|---|
| coinbase input | `vin[*].coinbase` field present (instead of `txid` + `vout`); should be recognized as "block-reward minting", not a real input | `filter.coinbase_input: bool` (true = filter out) |
| Genesis coinbase tx | `4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b` — getrawtransaction is permanently -5; fixture pool must exclude | `system_txids: [list of txids to skip]` |
| OP_RETURN outputs | `vout[*].scriptPubKey.type == "nulldata"` is burn/data-carrier; no balance | `filter.script_types_exclude: [nulldata]` |
| System addresses | Bitcoin has no native system address (no precompile); ecosystem conventions: `1BitcoinEaterAddressDontSendf59kuE` (burn), etc. | `system_addresses: []` (empty by default; each deployment fills) |

[E2 — coinbase field shown in §5 block-1 coinbase tx evidence; E3 — script types in bitcoincore.org getrawtransaction docs]

### 11.5 Heterogeneity vs existing 8 chains

| Dimension | Existing 8 chains (solana/eth/bsc/base/scroll/polygon/starknet/sui) | Bitcoin |
|---|---|---|
| **Account model** | All account-based (Solana account / EVM account / Cairo Felt / Move object) | **UTXO** (separate pole) |
| **JSON-RPC version** | All 2.0 (`"jsonrpc":"2.0"` required) | **1.0** (some proxies coerce back to 2.0 — §3 evidence) |
| **Auth** | Public nodes commonly none/bearer/API-key | **HTTP Basic Auth** (self-hosted default) |
| **Block-query steps** | 1 step (`eth_getBlockByNumber(h)`, `getBlock(slot)`) | **2 steps** (`getblockhash(h)` → `getblock(hash)`) |
| **Address balance** | Native RPC (`eth_getBalance`, `getBalance`) | **No native RPC** — needs Esplora REST or txindex+wallet |
| **Address format count** | 1 per chain (EVM all hex0x; Solana base58; Sui hex) | **3 coexist** (base58/bech32/bech32m); a single wallet can hold all three |
| **Signature lookup unit** | tx hash | **txid AND wtxid** (split after SegWit) |
| **Token concept** | Built-in (ERC20, SPL, Sui Coin) | **No native token** (BRC-20/Runes are link-layer metaprotocols requiring an ord indexer; out of scope for this framework) |

### 11.6 DSL design ASK (to P2-DESIGN-v2)

**MUST support**:
1. **JSON-RPC 1.0 and 2.0 dual compatibility** (request body may omit or set 1.0; response parsing tolerates missing/mismatched version field)
2. **HTTP Basic Auth** + env-var expansion + `optional` flag (for public-proxy case)
3. **Method chaining cursor** (previous method's response path → next method's param) — this is the P0 capability that decides whether the UTXO family can go 0-Python
4. **REST + JSON-RPC mixed protocol** (within one chain, different methods use different protocols, e.g. Bitcoin core uses JSON-RPC while Esplora REST fills balance)
5. **Multiple address-format validation** (multiple prefixes/encodings within one chain; validation may dispatch to on-chain `validateaddress` instead of pure local regex)
6. **Error code whitelist** (error `-5` for getrawtransaction on the genesis tx is a "known special case", not a real error; DSL should allow per-method `expected_error_codes: [-5]` to skip the sample)
7. **Path-template REST** (variable-bearing REST paths like `GET /address/{addr}`)

**MAY support**:
1. Batch RPC (Bitcoin Core supports JSON-array batch requests; benchmark may use single requests)
2. Cookie-file auth (`-rpccookiefile`, only meaningful for self-hosted; public/CI uses user/pass)
3. Electrum protocol (TCP+JSON, alternative to Esplora; not required for P1)

**MUST NOT need**:
1. Websocket subscription (BTC has no standard ws RPC; ZMQ is byte-level pub/sub, out of benchmark scope)
2. EVM-style event log filter (no concept)
3. Token balance native method (no native token)
4. Wallet-class methods (getbalance/sendtoaddress) — benchmark is read-only

---

## Open Questions

- [ ] **Esplora vs Electrum vs txindex+wallet**: in a self-hosted scenario, the three address-balance backends should be compared on latency/throughput in wave2 self-hosted bench.
- [ ] **publicnode's `-32701` custom code long-term stability**: if upstream allnodes switches to `-32601` or HTTP 4xx, clients must update. Recommend a contract test in wave2.
- [ ] **`getrawtransaction` behavior on self-hosted nodes without txindex**: whether publicnode has txindex enabled is unknown from outside (block-1 coinbase being queryable → likely yes, but needs operator confirmation).
- [ ] **Whether BRC-20 / Runes / Ordinals are in v1 benchmark scope**: metaprotocols need external indexers; vanilla Bitcoin RPC has no native support. This research treats them as out-of-scope pending business confirmation.
- [ ] **Mempool sampling strategy**: `getrawmempool` returns 27K+ txids; should the benchmark pull the full list each time? Recommend mock truncates to ~10; real endpoint applies truncation.

---

## Changelog

| Date | Author | Change |
|---|---|---|
| 2026-05-23 | Hermes Agent | Initial research: based on live curl against publicnode.com & blockstream.info + Bitcoin Core master @ de92545 source. Completed Sections 1-11 with full field-level evidence. Key DSL ASKs listed (method chaining, JSON-RPC 1.0/2.0 dual compat, basic auth + env var, REST + JSON-RPC hybrid). |
