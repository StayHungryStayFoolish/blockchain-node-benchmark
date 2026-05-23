# 13-Avalanche-X Research

> **Derived from `_template.md`.**
> **Filled per H8 (real evidence): curl probes + official doc URLs + GitHub commit SHAs.**
> **Each field tagged E1 (unit test) / E2 (curl) / E3 (docs) / E4 (source) / E5 (codebase grep).**
> **Core role: the second UTXO chain (after Bitcoin / Cardano-eUTXO), critical family-boundary decision.**

---

## Metadata

| Field | Value |
|---|---|
| Chain name (ZH) | 雪崩 X 链 |
| Chain name (EN) | Avalanche X-Chain (AVM, Avalanche Virtual Machine) |
| Number | 13 |
| Mainnet BlockchainID | `2oYMBNV4eNHyqk2fjjV5nVQLDbtmNJzq5s3qs3Lo6ftnC6FByM` (via `info.getBlockchainID(alias=X)` [E2]) |
| NetworkID | `1` (mainnet, observed in tx body `networkID` field [E2]) |
| Research date | 2026-05-23 |
| Researcher | Hermes Agent |
| Status | 🟢 Complete (method-level probes all pass) |

---

## 1. Sources

| Type | URL | Accessed | Note |
|---|---|---|---|
| Official AVM API | https://build.avax.network/docs/api-reference/x-chain/api | 2026-05-23 | X-Chain JSON-RPC 2.0 method reference (`avm.*` namespace) |
| Official Info API | https://build.avax.network/docs/api-reference/info-api | 2026-05-23 | Node/chain metadata (used to resolve alias→blockchainID) |
| GitHub | https://github.com/ava-labs/avalanchego (observed version `avalanchego/1.14.2`, commit `6e5acf909c7a16b991142d6b3979bac5699bdb68` via `info.getNodeVersion` [E2]) | 2026-05-23 | Core implementation; this doc anchored to this SHA |
| AVM source path | https://github.com/ava-labs/avalanchego/tree/master/vms/avm | 2026-05-23 | AVM implementation (service.go contains all `avm.*` methods) |
| Bech32 address spec | https://docs.avax.network/specs/cryptographic-primitives#addresses (`X-` HRP) | 2026-05-23 | HRP=`avax`, chain alias as prefix (`X-avax1...`) |
| Explorer | https://subnets.avax.network/x-chain | 2026-05-23 | Used to verify addresses/txs cited in this doc |

---

## 2. Protocol Family — **Key Decision**

| Field | Value |
|---|---|
| Family | **`avalanche-utxo`** (independent sub-family, **same root as Bitcoin `utxo-btc` but does NOT share adapter**; see §10 and §11.7 decision matrix) |
| Consensus | Snowman++ (Avalanche consensus family, DAG-based probabilistic fast finality) [E3] |
| VM | AVM (Avalanche Virtual Machine) — **not Turing-complete**, fixed tx type set (`BaseTx`/`CreateAssetTx`/`OperationTx`/`ImportTx`/`ExportTx`); same constrained-script family as Bitcoin Script [E3 + E4] |
| Block Time | ~1–2 s observed (between successive `avm.getHeight` calls) — Snowman backend [E2] |
| Finality | Probabilistic < 1 s (final upon consensus completion; much faster than Bitcoin's 6-conf convention) |
| Reuse Existing Adapter? | **No** (see §10 decision matrix) — same UTXO model as Bitcoin but differs in: (a) JSON-RPC 2.0 with `avm.*` namespace prefix, (b) multi-asset (each UTXO carries `assetID`), (c) bech32-only addresses, (d) structured tx schema (no Script opcodes). Sharing code introduces conditional-branch hell |

---

## 3. Public RPC

| Endpoint | Auth | Result | Note |
|---|---|---|---|
| `https://api.avax.network/ext/bc/X` | **None** (fully public) | ✅ 200, 5 consecutive requests ~100 ms avg (cold req1 0.299 s, warm req2-5 ~0.05 s) | **Primary test endpoint**; X-Chain-specific path, separate from C-Chain (`/ext/bc/C/rpc`), P-Chain (`/ext/bc/P`), Info (`/ext/info`) |
| `https://api.avax.network/ext/info` | None | ✅ 200 | Metadata endpoint (blockchainID/version/peers); **NOT AVM, no `avm.*` prefix** — uses separate `info.*` namespace |
| `https://rpc.ankr.com/avalanche-x` | Optional API key | Not tested | Backup commercial endpoint |

**Trade-off**:
- The official endpoint exhibits no perceived rate-limiting, no auth, strict JSON-RPC 2.0 — one of the cleanest RPCs among the 14 chains studied.
- **Reversal condition**: if the official endpoint adds quotas/throttling, switch to Ankr or a self-hosted avalanchego (which also has no auth by default; avalanchego's `http-host=0.0.0.0` with no built-in basic auth).

**curl evidence** (E2, 2026-05-23):
```bash
# E2 — height probe (primary liveness)
curl -s -X POST https://api.avax.network/ext/bc/X \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"avm.getHeight","params":{}}'
# {"jsonrpc":"2.0","result":{"height":"517993"},"id":1}
# ↑ Note: height is a STRING ("517993"), not int — Avalanche uint64 convention
#   (string-encoded to prevent JS number-precision loss)

# Latency probe (rate-limit sniff)
req1: 200 time=0.298922s
req2: 200 time=0.052735s
req3: 200 time=0.056015s
req4: 200 time=0.057473s
req5: 200 time=0.057898s
# → Cold ~300 ms, warm ~55 ms, no rate-limit triggered

# Node version
curl -s -X POST https://api.avax.network/ext/info \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"info.getNodeVersion","params":{}}'
# {"jsonrpc":"2.0","result":{"version":"avalanchego/1.14.2","databaseVersion":"v1.4.5",
#  "rpcProtocolVersion":"45","gitCommit":"6e5acf909c7a16b991142d6b3979bac5699bdb68",
#  "vmVersions":{"avm":"avalanchego/1.14.2","evm":"v1.14.2","platform":"avalanchego/1.14.2"}},"id":1}
```

---

## 4. Account Model — **multi-asset UTXO, unique**

| Field | Value |
|---|---|
| Model | **UTXO**, but **multi-asset** (each UTXO carries an `assetID` field; Bitcoin UTXOs carry only BTC) [E2 — see §5 `getUTXOs` and `getTx` probes] |
| Native token decimals | **9** (AVAX, via `avm.getAssetDescription` → `denomination:"9"` [E2]) — **Note: differs from Bitcoin BTC=8 AND from C-Chain AVAX=18** (same token, different decimals across chains; cross-chain bridges must re-scale) |
| AVAX assetID | `FvwEAhmxKfeiG8SnEvq42hc6whRyY3EFYAvebMqDNDGCgxN5Z` (mainnet, confirmed via `getAssetDescription` [E2]) |
| Address derivation | secp256k1 ECDSA, pubkey → ripemd160(sha256(pk)) → bech32 (HRP=`avax`, with `X-` chain-alias prefix) [E3] |
| Special account types | **No accounts**; every "address" is the receiver of a UTXO locking script (`SECP256K1OutputOwners`); the `threshold` field provides native m-of-n multisig (Bitcoin needs P2SH/P2WSH wrapping) [E2 — outputs.threshold:1] |
| **Multi-asset evidence** | Same address simultaneously holds AVAX AND another asset (assetID `2EuZzt6W4MtNhDofY1TBL24yHrpz5QEG8shiFEqDBccEzYVHwW`, balance `300`), returned in a single `avm.getAllBalances` call. No Bitcoin equivalent exists [E2] |

**Multi-asset evidence** (E2, core proof):
```bash
# Same address; getAllBalances returns multiple assets
curl -s -X POST https://api.avax.network/ext/bc/X -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"avm.getAllBalances",
       "params":{"address":"X-avax13k6hxpfuu80dlnqlqs0dxxjrzl4lxz94n38vnw"}}'
# {"jsonrpc":"2.0","result":{"balances":[
#   {"asset":"AVAX","balance":"189093923788006"},                            ← 0.189 M AVAX (9 decimals)
#   {"asset":"2EuZzt6W4MtNhDofY1TBL24yHrpz5QEG8shiFEqDBccEzYVHwW","balance":"300"}  ← another AVM asset
# ]},"id":1}
```

---

## 5. Core RPC Methods (required by this framework)

> All target `https://api.avax.network/ext/bc/X`, JSON-RPC 2.0, POST `/` (no sub-paths). Every method name carries the `avm.` prefix (**markedly different from Bitcoin's unprefixed `getbalance`**).

| Method | Category | Notes | Weight in mixed |
|---|---|---|---|
| `avm.getHeight` | block height | Chain tip height; returns `{"height": "<int as string>"}` | 0.10 |
| `avm.getBlockByHeight` | block by height | Input `{height, encoding}`; **single-step** (no height→hash chaining required) | 0.10 |
| `avm.getBlock` | block by id | Input `{blockID, encoding}`; fetch by ID | 0.05 |
| `avm.getTx` | tx lookup | Input `{txID, encoding}`; returns full tx structure (unsignedTx + credentials) | 0.15 |
| `avm.getTxStatus` | tx status | Returns `{status: Accepted | Rejected | Processing | Unknown}` | 0.10 |
| `avm.getBalance` | account balance | Input `{address, assetID}`; **assetID is required** (single-asset query) | 0.10 |
| `avm.getAllBalances` | account multi-asset | Input `{address}`; **returns all assets in one call** — signature method of the multi-asset model | 0.15 |
| `avm.getUTXOs` | UTXO list | Input `{addresses[], limit, encoding}`; returns hex-encoded UTXOs + `endIndex` for pagination | 0.10 |
| `avm.getAssetDescription` | asset meta | Input `{assetID}`; returns `{name, symbol, denomination}` | 0.05 |
| `info.getBlockchainID` | meta | Input `{alias}`; alias→blockchainID lookup (`info.*` not `avm.*`; uses `/ext/info`) | 0.05 |
| `info.getNodeVersion` | meta | Node version/peer info | 0.05 |

**Weight check**: 0.10+0.10+0.05+0.15+0.10+0.10+0.15+0.10+0.05+0.05+0.05 = **1.00** ✅

**curl evidence — key methods full responses** (E2, 2026-05-23):

```bash
# 1) avm.getBlockByHeight(0) — genesis
curl -s -X POST https://api.avax.network/ext/bc/X -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"avm.getBlockByHeight",
       "params":{"height":"0","encoding":"json"}}'
# {"jsonrpc":"2.0","result":{"block":{
#   "parentID":"jrGWDh5Po9FMj54depyunNixpia5PN4aAYxfmNzU8n752Rjga",
#   "height":0,"time":1682434800,
#   "merkleRoot":"11111111111111111111111111111111LpoYY",
#   "txs":[],
#   "id":"V8kYdATLoVjUBazVjEHy1dWurk2PcnhERSWnwmcNwirdsBb1S"},
#   "encoding":"json"},"id":1}
# ↑ Note: IDs are cb58-encoded (not hex) — Avalanche uses cb58 throughout
#   (base58 + 4-byte SHA-256 checksum; differs from Bitcoin's base58check)

# 2) avm.getBlockByHeight(517990) — near-tip block
# Returns block.txs[0] as BaseTx, schema:
# {"unsignedTx":{
#   "networkID":1,"blockchainID":"2oYMBNV4eNHyqk2fjjV5nVQLDbtmNJzq5s3qs3Lo6ftnC6FByM",
#   "outputs":[{
#     "assetID":"FvwEAhmxKfeiG8SnEvq42hc6whRyY3EFYAvebMqDNDGCgxN5Z",     ← multi-asset field
#     "fxID":"spdxUxVJQbX85MGxMHbKw1sHxMnSqJ3QBzDyDYEP3h6TLuxqQ",
#     "output":{"addresses":["X-avax13k6hxpfuu80dlnqlqs0dxxjrzl4lxz94n38vnw"],
#               "amount":5527276870,"locktime":0,"threshold":1}}],   ← native m-of-n
#   "inputs":[{"txID":"2EfmTtons3Th8sMhGa1tpd8ameUhZGErkF2mPiGJzHT3vE82pE",
#              "outputIndex":0,"assetID":"FvwEAhmxKfeiG8SnEvq42hc6whRyY3EFYAvebMqDNDGCgxN5Z",
#              "input":{"amount":5528276870,"signatureIndices":[0]}}],
#   "memo":"0x"},
#   "credentials":[{"credential":{"signatures":["0x3fd0f69e..."]}}],
#   "id":"5Hb7uXBFQTaXCDwymYxDfYyEwRYVG35aMmdLwgcvKQniHama5"}
# ↑ Structured tx — far more readable than Bitcoin's scriptSig/scriptPubKey bytecode

# 3) avm.getTx(<txID>)
# Input: {"txID":"5Hb7uXBFQTaXCDwymYxDfYyEwRYVG35aMmdLwgcvKQniHama5","encoding":"json"}
# Response schema same as above (separate unsignedTx + credentials); encoding ∈ "hex"|"json"|"cb58"

# 4) avm.getTxStatus — 4-state enum
# {"jsonrpc":"2.0","result":{"status":"Accepted"},"id":1}
# Possible: Accepted | Rejected | Processing | Unknown

# 5) avm.getBalance(addr, "AVAX")
# Response: {"balance":"189093923788006","utxoIDs":[{"txID":"...","outputIndex":0}, ...]}
# ↑ balance is STRING (uint64 to avoid JS precision loss); utxoIDs lists UTXOs of that asset

# 6) avm.getAllBalances — see §4 multi-asset evidence

# 7) avm.getUTXOs(addresses, limit=3)
# Response: {"numFetched":"3","utxos":["0x000076aa...","0x0000ce72...","0x000009bb..."],
#            "endIndex":{"address":"X-avax13k6...","utxo":"GJ98vX57..."},
#            "encoding":"hex"}
# ↑ Pagination via endIndex → startIndex; cursor-style (different from Bitcoin
#   which has no native UTXO-list method)

# 8) avm.getAssetDescription(AVAX assetID)
# {"jsonrpc":"2.0","result":{
#   "assetID":"FvwEAhmxKfeiG8SnEvq42hc6whRyY3EFYAvebMqDNDGCgxN5Z",
#   "name":"Avalanche","symbol":"AVAX","denomination":"9"},"id":1}

# 9) method not found
# {"jsonrpc":"2.0","id":1,"error":{"code":-32601,"message":"the method avm.notARealMethod does not exist"}}
```

---

## 6. Address Format

| Field | Value |
|---|---|
| Encoding | **Bech32 only** (HRP=`avax`, with `X-` chain-alias prefix) [E3] — **simpler than Bitcoin** (BTC has 3: base58/bech32/bech32m; X-Chain has 1) |
| Length | 42–43 chars (`X-avax1` + 35-char payload + checksum) [E2] |
| Checksum | Bech32 (BCH constant 1) — same algorithm as Bitcoin SegWit v0, but different HRP [E3] |
| Chain alias prefix | `X-` (X-Chain), `P-` (P-Chain, validators), `C-` (C-Chain, EVM bech32 form; also has hex 0x form) — **same pubkey derives 3 alias forms; cross-chain requires re-encoding** |
| Mainnet example | `X-avax13k6hxpfuu80dlnqlqs0dxxjrzl4lxz94n38vnw` (proven valid below; extracted from block 517990) |
| Practical regex (NOT sufficient) | `^X-avax1[023456789acdefghjklmnpqrstuvwxyz]{38,39}$` — must validate checksum via `avm.getBalance` round-trip (no standalone `validateaddress` method) |

**E2 — Key finding: context-supplied example address has invalid checksum**:
```bash
# Context provided: X-avax1pa5vu24v3hd0y9rdqekv9msrz86s90uvc3xyhq  ← INVALID
# avalanchego replied:
# "couldn't parse address: invalid checksum (expected (bech32=url3kn, bech32m=url3knfl0an3), got c3xyhq)"
#
# Conclusion: the context address was hand-edited or copied incorrectly from an explorer.
# This doc uses the verified live address instead:
#   X-avax13k6hxpfuu80dlnqlqs0dxxjrzl4lxz94n38vnw
# Source: avm.getBlockByHeight(517990).txs[0].unsignedTx.outputs[0].output.addresses[0]
# Confirmed valid via avm.getBalance (returned balance 189093923788006 nAVAX)
```

---

## 7. Signature / Transaction Hash Lookup

| Field | Value |
|---|---|
| Hash format | **cb58** (base58 + 4-byte SHA-256 checksum) — **NOT hex**! Completely unlike Bitcoin txid (hex) [E3] |
| Length | ~50 chars (variable; base58 of 32-byte hash + 4-byte checksum) |
| Mainnet example | `5Hb7uXBFQTaXCDwymYxDfYyEwRYVG35aMmdLwgcvKQniHama5` (tx inside block 517990; used throughout this doc) |
| Lookup methods | `avm.getTx(txID, encoding)`, `avm.getTxStatus(txID)` |
| Explorer URL | `https://subnets.avax.network/x-chain/tx/<txID>` |
| **encoding parameter** | `"json"` (structured) / `"hex"` (raw bytes with 0x prefix) / `"cb58"` (cb58 encoded) — one method, three serializations, **DSL must model the encoding parameter** |

---

## 8. Mixed Set (`mixed` mode weights)

> Distribution for `BLOCKCHAIN_NODE_BENCHMARK_MODE=mixed` Avalanche-X traffic.
> Design rationale: multi-asset balance (`getAllBalances`) is X-Chain's signature workload vs Bitcoin, weighted ≥15 %; tx/UTXO queries next; create-asset write paths excluded from read-only benchmark.

```json
{
  "block_height_query": 0.10,
  "block_by_height_query": 0.10,
  "block_by_id_query": 0.05,
  "tx_lookup": 0.15,
  "tx_status_query": 0.10,
  "balance_single_asset_query": 0.10,
  "balance_all_assets_query": 0.15,
  "utxo_list_query": 0.10,
  "asset_meta_query": 0.05,
  "blockchain_id_query": 0.05,
  "node_version_query": 0.05
}
```

Method mapping:
- `block_height_query` → `avm.getHeight` (no params)
- `block_by_height_query` → `avm.getBlockByHeight` (`$height`, `$encoding="json"`)
- `block_by_id_query` → `avm.getBlock` (`$blockID`, `$encoding="json"`)
- `tx_lookup` → `avm.getTx` (`$txID`, `$encoding="json"`)
- `tx_status_query` → `avm.getTxStatus` (`$txID`)
- `balance_single_asset_query` → `avm.getBalance` (`$address`, `$assetID="AVAX"`)
- `balance_all_assets_query` → `avm.getAllBalances` (`$address`)
- `utxo_list_query` → `avm.getUTXOs` (`[$address]`, `$limit=10`, `$encoding="hex"`)
- `asset_meta_query` → `avm.getAssetDescription` (`$assetID`)
- `blockchain_id_query` → `info.getBlockchainID` (`$alias="X"`) — **routed to `/ext/info`**, not `/ext/bc/X`
- `node_version_query` → `info.getNodeVersion` (no params, `/ext/info`)

**Weight sum**: 0.10+0.10+0.05+0.15+0.10+0.10+0.15+0.10+0.05+0.05+0.05 = **1.00** ✅

---

## 8.5 Phase 2.1 caller/reader changes (token-level Gate 3)

Avalanche-X is a **new chain**; new/touched points required in P2.1:

| # | Location | Change | Reason |
|---|---|---|---|
| 1 | `config/config_loader.sh` UNIFIED_BLOCKCHAIN_CONFIG add `"avalanche-x": {...}` block | new chain_type, rpc_methods, param_formats, `namespace_prefix:"avm."` (see §11) | sibling with other chains |
| 2 | `config/config_loader.sh` `supported_blockchains` array add `"avalanche-x"` | grow array to N+1 | the guard watches this array |
| 3 | `config/config_loader.sh` add `avalanche-x)` case | set `MAINNET_RPC_URL="https://api.avax.network/ext/bc/X"` | avoid default branch (wrong chain) |
| 4 | `tools/mock_rpc_server.py` add `avm.*` method branches (11 methods) | copy §5 responses as fixtures; **uint64 fields like height/balance/numFetched MUST serialize as strings** | mock is CI fallback |
| 5 | `tools/fetch_active_accounts.py` new `AvalancheXAdapter` class | pull `avm.getBlockByHeight(tip-N).txs[*].outputs[*].addresses[]` as active address source (no explorer REST; pure RPC) | unlike BitcoinAdapter which uses Esplora REST |
| 6 | `tests/guard_Nchain_truth.sh` | add `"avalanche-x"` expectation | else guard blocks startup |
| 7 | DSL schema (P2-DESIGN-v2) add `namespace_prefix: string` field | see §11.7 decision a-2 | root fix for method-prefix differentiation within UTXO family |
| 8 | DSL schema add `multi_asset: bool` + `native_asset_id: string` | required for X-Chain, optional for Bitcoin | see §11.7 multi-asset expression |

**N/A**: Avalanche-X is new; no methods to remove.

**Test requirement**: After P2.1, run `BLOCKCHAIN_NODE=avalanche-x core/master_qps_executor.sh --mixed --duration 30`; expect vegeta all 200 + JSON-RPC `error` field null.

---

## 9. Mock Notes (mock_rpc_server implementation)

- **Request paths**:
  - AVM: `POST /ext/bc/X` (standard path, no trailing data)
  - Info: `POST /ext/info` (separate endpoint)
  - mock MUST distinguish the two; otherwise `info.*` calls route to the wrong namespace and fail
- **Response schema** (sample from §5 probe):
  ```json
  {
    "jsonrpc": "2.0",
    "result": {
      "block": {
        "parentID": "UowX32B6nCQd2aux7M6MYe6jJH88RBA4T31b2hdwGVz1WrMXA",
        "height": 517990,
        "time": 1779556977,
        "merkleRoot": "11111111111111111111111111111111LpoYY",
        "txs": [{"unsignedTx": {"...": "..."}, "credentials": [], "id": "5Hb7uX..."}],
        "id": "XJmMj5b..."
      },
      "encoding": "json"
    },
    "id": 1
  }
  ```
- **Special encoding rules** (mock must honor):
  1. All uint64 fields (`height`, `balance`, `amount`, `numFetched`, sometimes `time`) **must be strings in responses** (`"517993"` not `517993`) — avalanchego `jsonString` type contract [E4 — `vms/avm/service.go`]
  2. ID fields (`txID`, `blockID`, `assetID`, `parentID`, `blockchainID`) use **cb58** (base58 + 4-byte checksum), not hex
  3. Binary payloads (signatures, UTXOs in hex mode) use `"0x..."` hex strings
- **Error codes** (authoritative: `ava-labs/avalanchego@6e5acf9 utils/rpc/handler.go` + JSON-RPC 2.0 standard) [E2 + E4]:
  - `-32600` JSON-RPC Invalid Request
  - `-32601` Method not found (observed: `"the method avm.notARealMethod does not exist"`)
  - `-32602` JSON-RPC Invalid params
  - `-32603` Internal error
  - `-32700` Parse error
  - **`-32000` custom application errors** (implementation-defined server error, allowed range -32000..-32099) — two captured:
    - "problem parsing address ... invalid checksum"
    - "problem decoding transaction: missing 0x prefix to hex encoding"
- **Mock implementation complexity**: **Medium-High**
  - Easy: most methods have fixed schemas; observed responses can become fixtures directly
  - Hard #1: **uint64-as-string** — Python `json.dumps` of int produces wrong type; force `str(x)` for uint64 fields or use explicit string fields
  - Hard #2: **cb58 encoding** — no Python stdlib support; needs `base58` + 4-byte SHA-256 checksum impl; mock may choose to return fixed fixture cb58 strings instead of generating
  - Hard #3: **two endpoint paths** — mock_rpc_server must route by path (AVM vs Info)
  - Hard #4: **multi-asset balance fixture** — `getAllBalances` needs ≥2 distinct assetIDs to exercise the real code path

---

## 10. Adapter Reuse Decision — **Key Decision**

### Candidate adapters

| Adapter | Compatibility | Missing capability |
|---|---|---|
| EthereumAdapter | 0 % | completely different account model |
| SolanaAdapter | 0 % | same |
| **BitcoinAdapter** | **~35 %** | **Shared: UTXO concept, read-only benchmark, JSON-RPC POST**<br>**Conflicts:**<br>(a) namespace prefix (`avm.*` vs none)<br>(b) multi-asset (UTXO carries assetID)<br>(c) encoding (cb58 vs hex+base58)<br>(d) tx schema (structured vs Script bytecode)<br>(e) JSON-RPC version (2.0 vs 1.0)<br>(f) auth (none vs basic auth) |
| CardanoAdapter (eUTXO) | ~25 % | also UTXO but datum/script-witness model differs; Cardano uses REST not JSON-RPC |
| **(new) AvalancheXAdapter** | 100 % | — |

### Decision

- [x] **Create** `AvalancheXAdapter` (`family="avalanche-utxo"`, independent sub-family)
- [x] **Do NOT share adapter with Bitcoin**, but **introduce `namespace_prefix` DSL field so both families are structurally homogeneous at the schema layer** (see §11.7)

### Rationale

1. **Sharing the UTXO "concept" ≠ sharing adapter code**: Bitcoin adapter's `getRawTransaction(txid, verbose)` and AVM's `avm.getTx(txID, encoding)` look similar but their response structures differ completely (Bitcoin flat vin/vout + scriptPubKey bytecode; AVM nested `unsignedTx + credentials` with assetID per output). Shared code becomes an `if chain=="bitcoin"... else ...` minefield, harder to maintain than two independent adapters.
2. **Namespace prefix is protocol-level isolation**: `avm.getHeight` / `info.getNodeVersion` / `platform.getCurrentValidators` coexist across three namespaces on the same avalanchego node (split across X/Info/P endpoints). Bitcoin RPC methods all live in one flat namespace. This is a protocol design difference, not a naming style preference.
3. **Multi-asset is a model-level feature**: the `assetID` required parameter of `avm.getBalance(address, assetID)` has no analog in Bitcoin's `getbalance(address)` (which implicitly means BTC). `avm.getAllBalances` further surfaces the asset dimension. This is data-model heterogeneity, not API-style heterogeneity.
4. **Future reuse**: `AvalancheXAdapter` can be **90 %+ reused** by the future P-Chain (same `*.api` namespace style, same networkID, shared cb58 encoding, shared bech32-with-chain-alias). This makes it a true family seed.

### Config JSON example

```json
{
  "chain": "avalanche-x",
  "family": "avalanche-utxo",
  "adapter": "AvalancheXAdapter",
  "blockchain_id": "2oYMBNV4eNHyqk2fjjV5nVQLDbtmNJzq5s3qs3Lo6ftnC6FByM",
  "network_id": 1,
  "rpc_endpoint": "https://api.avax.network/ext/bc/X",
  "rpc_endpoint_alt_info": "https://api.avax.network/ext/info",
  "rpc_protocol": "json-rpc-2.0",
  "namespace_prefix": "avm.",
  "auth": {"type": "none"},
  "block_time_ms": 2000,
  "native_decimals": 9,
  "native_asset_id": "FvwEAhmxKfeiG8SnEvq42hc6whRyY3EFYAvebMqDNDGCgxN5Z",
  "native_asset_alias": "AVAX",
  "multi_asset": true,
  "address_formats": ["bech32-with-alias"],
  "address_hrp": "avax",
  "address_alias_prefix": "X-",
  "id_encoding": "cb58",
  "uint64_as_string": true,
  "rpc_methods": {
    "block_height": "avm.getHeight",
    "block_by_height": "avm.getBlockByHeight",
    "block_by_id": "avm.getBlock",
    "tx_lookup": "avm.getTx",
    "tx_status": "avm.getTxStatus",
    "balance_single_asset": "avm.getBalance",
    "balance_all_assets": "avm.getAllBalances",
    "utxo_list": "avm.getUTXOs",
    "asset_meta": "avm.getAssetDescription"
  },
  "mixed_weights": {
    "block_height_query": 0.10,
    "block_by_height_query": 0.10,
    "block_by_id_query": 0.05,
    "tx_lookup": 0.15,
    "tx_status_query": 0.10,
    "balance_single_asset_query": 0.10,
    "balance_all_assets_query": 0.15,
    "utxo_list_query": 0.10,
    "asset_meta_query": 0.05,
    "blockchain_id_query": 0.05,
    "node_version_query": 0.05
  }
}
```

---

## 11. DSL Field Requirements (P2-DESIGN-v2 input)

### 11.1 RPC call protocol

| Field | Avalanche-X value | DSL field |
|---|---|---|
| Protocol | JSON-RPC 2.0 strict (response always has `jsonrpc:"2.0"`) | `rpc.protocol: jsonrpc2` |
| HTTP method | POST | `rpc.http_method: POST` |
| Request path | **Multi-endpoint** (`/ext/bc/X` and `/ext/info` coexist) | `rpc.endpoints: {default: ..., info: ...}` + per-method `endpoint_ref` |
| Auth | None | `rpc.auth: {type: none}` |

### 11.2 Method call schemas

#### `avm.getHeight`
- params: `{}`
- extraction: `$.result.height` (string, needs parseInt)
- evidence: §3 [E2]

#### `avm.getBlockByHeight`
- params: `{"height": "$height", "encoding": "json"}` (height is **string**)
- extraction: `$.result.block.id`, `$.result.block.parentID`, `$.result.block.txs[*]`
- evidence: §5 [E2]

#### `avm.getTx`
- params: `{"txID": "$txid", "encoding": "json"}`
- extraction: `$.result.tx.id`, `$.result.tx.unsignedTx.outputs[*].assetID`, `$.result.tx.unsignedTx.outputs[*].output.amount`
- evidence: §5 [E2]

#### `avm.getBalance`
- params: `{"address": "$addr", "assetID": "$asset_id"}` (`assetID` accepts `"AVAX"` alias or full cb58 ID)
- extraction: `$.result.balance` (string), `$.result.utxoIDs[*]`
- evidence: §4 [E2]

#### `avm.getAllBalances` (**multi-asset flagship**)
- params: `{"address": "$addr"}`
- extraction: `$.result.balances[*].asset`, `$.result.balances[*].balance`
- **DSL ASK**: returns an array of `(asset, balance)` rows; latency is one-request, but throughput tests effectively trigger N asset lookups per request — annotate with `fanout_hint: dynamic`
- evidence: §4 [E2]

#### `avm.getUTXOs`
- params: `{"addresses": ["$addr"], "limit": $limit, "encoding": "hex"}`
- pagination: feed next `startIndex: {address, utxo}` from previous `endIndex`
- extraction: `$.result.numFetched`, `$.result.utxos[*]`, `$.result.endIndex`
- evidence: §5 [E2]

### 11.3 Cursor / pagination

| Model | Description | DSL |
|---|---|---|
| **height-based** (primary) | `for h in [0, tip]: avm.getBlockByHeight(h)` — **single-step** (no height→ID→block chaining) | `cursor: {type: height, start: $H0, step: 1, max_count: 1000}` — unlike Bitcoin, **no method chaining needed** |
| **endIndex-based** (UTXO pagination) | `avm.getUTXOs` returns `endIndex` → feed as next `startIndex` | `cursor: {type: opaque, next_path: $.endIndex, param_name: startIndex}` |
| **txID-based** (tx sampling) | Extract `block.txs[*].id` → `avm.getTx` per id | `cursor: {type: list, source: avm.getBlockByHeight, item_path: $.result.block.txs[*].id}` |

**DSL ASK vs Bitcoin**: X-Chain does NOT need method chaining (getBlockByHeight is single-step), so the chaining capability Bitcoin demanded in its §11.3 is **optional** for X-Chain — but it remains a P0 capability for the UTXO family as a whole (Bitcoin requires it).

### 11.4 System addresses / filter rules

| Field | Avalanche-X value | DSL |
|---|---|---|
| Genesis special tx | block 0 has `txs: []` (empty, no coinbase) — **simpler than Bitcoin**; no system_txids exclusion needed | N/A |
| Import/Export tx | `ImportTx`/`ExportTx` are cross-chain (X↔P / X↔C) bridge tx; their `inputs` reference UTXOs on other chains — benchmark should recognize but not filter | `tx_type_filter: {include: [BaseTx], exclude: [CreateAssetTx, OperationTx, ImportTx, ExportTx]}` (optional) |
| System addresses | None native (no precompile / treasury) | `system_addresses: []` |

### 11.5 Heterogeneity matrix (vs studied chains)

| Dimension | Typical existing chain | Bitcoin | **Avalanche-X** |
|---|---|---|---|
| **Account model** | account-based (EVM/Solana/Sui/...) | UTXO | **UTXO + multi-asset** |
| **JSON-RPC version** | 2.0 (EVM) / 1.0 (Bitcoin) | 1.0 | **2.0 (strict)** |
| **Method namespace** | unprefixed (eth_*, getBalance — bare method names) | unprefixed | **`avm.*` / `info.*` / `platform.*` multi-namespace** |
| **Endpoint count** | 1 per chain | 1 (Core) + 1 (Esplora) | **multi-endpoint** (`/ext/bc/X` + `/ext/info` + `/ext/bc/P` + `/ext/bc/C/rpc`) |
| **uint64 encoding** | hex string (EVM) / int (Solana) / float (Bitcoin amount) | float BTC / int sat | **string** (`"189093923788006"`) |
| **ID encoding** | hex 0x (EVM) / base58 (Solana) / hex (Bitcoin) | hex | **cb58** (base58 + checksum) |
| **Token model** | ERC20/SPL/Sui Coin | no native token | **multi-asset native** (AVAX itself is just an assetID, peer to other AVM assets) |
| **Balance query** | 1 method returns account total | none native (Esplora REST) | **2 methods, split single-asset vs all-assets** |
| **Auth** | bearer/API key/none | basic auth | **none** (official public endpoint has no auth) |

### 11.6 DSL design ASKs (for P2-DESIGN-v2) — Avalanche-X additions

**Must support** (on top of Bitcoin's existing ASKs):
1. **Method namespace_prefix**: DSL field `namespace_prefix: string` (BTC=`""`, X-Chain=`"avm."`, Info=`"info."`); framework auto-prepends when assembling method names — **core DSL addition**
2. **Multi-endpoint routing**: methods within one chain dispatch to different base URLs via `endpoint_ref` (X-Chain primary vs Info endpoint) — **core DSL addition**
3. **Multi-asset expression**: `multi_asset: bool` + `native_asset_id: string` + per-method `asset_id_param` (marks which param selects the asset)
4. **uint64-as-string**: DSL field `numeric_encoding: enum[int, string, hex]` per-field or chain-default — Avalanche all-string, Bitcoin int/float, EVM hex
5. **cb58 encoding**: value transformer / decoder registry; DSL references `decoder: cb58` (analogous to Bitcoin's `decoder: base58check` or EVM's `decoder: hex`)

**Optional**:
1. Cross-chain tx-type recognition (`ImportTx`/`ExportTx`) — not needed for v1; only when cross-chain benchmark added in P2
2. P-Chain validator queries (`platform.getCurrentValidators`) — only if this framework covers PoS validator monitoring

**Not needed**:
1. websocket / subscriptions (X-Chain has no standard ws RPC)
2. EVM event log (X-Chain has no event concept; that lives on C-Chain)

### 11.7 REQUIRED: Avalanche-X vs Bitcoin UTXO comparison (decides family boundary)

| Dimension | Bitcoin UTXO | Avalanche-X UTXO | Evidence |
|---|---|---|---|
| Protocol | JSON-RPC 1.0/2.0 (mixed) | JSON-RPC 2.0 (strict) | §3 vs §3 [E2] |
| Method namespace | none (`getbalance`) | **`avm.*` (`avm.getBalance`)** | §5 [E2] |
| Balance query | `getbalance` (wallet, proxy-banned) / scantxoutset / Esplora REST | `avm.getBalance(address, assetID)` + `avm.getAllBalances(address)` | §4 [E2] |
| UTXO query | `listunspent` (wallet) / scantxoutset / Esplora `GET /address/{a}/utxo` | `avm.getUTXOs(addresses[], limit, encoding)` with native pagination | §5 [E2] |
| Tx query | `getrawtransaction(txid, verbose)` (needs txindex) | `avm.getTx(txID, encoding)` | §5 [E2] |
| Block query | `getblock(hash, verbosity)` + `getblockhash(N)` — **two steps** | `avm.getBlockByHeight(height, encoding)` — **single step** | §5 [E2] |
| Multi-asset | ❌ BTC only (BRC-20/Runes are metaprotocols requiring external indexers) | ✅ assetID is a required field (AVAX itself is just an asset, peer to others) | §4 multi-asset evidence [E2] |
| Address | 3 forms (base58/bech32/bech32m) | 1 form (bech32 w/ `X-` alias) | §6 [E2] |
| Auth | basic auth (self-hosted default) / none (public proxy) | **none** (official endpoint has no auth) | §3 200 with no header [E2] |
| ID encoding | hex (txid/blockhash) | **cb58** (all ID fields) | §7 [E2] |
| uint64 encoding | int (sat) / float (BTC) | **string** (`"189093923788006"`) | §5 [E2] |
| Genesis queryable | ❌ (creation coinbase returns error -5) | ✅ (`getBlockByHeight(0)` works) | §5 [E2] |
| Node version method | `getnetworkinfo` | `info.getNodeVersion` (on `/ext/info`) | §3 [E2] |

### 11.8 REQUIRED: DSL Decision (CRITICAL — family boundary)

#### Options

- [ ] **Option (a)**: Same family as Bitcoin, add `namespace_prefix` + `multi_asset` DSL fields, share `UTXOAdapter` (family=`utxo`)
- [x] **Option (b) — RECOMMENDED**: **Independent `family="avalanche-utxo"`, new `AvalancheXAdapter`**; DSL still adds `namespace_prefix` / `multi_asset` fields (X-Chain needs them now; P-Chain will too) but **leaves Bitcoin's existing `family="utxo-btc"` untouched**
- [ ] Option (c): Skip X-Chain (violates benchmark comprehensiveness mandate; not recommended)

#### Rationale (2–3 paragraphs)

**Rationale 1 — existing family names already follow a "specific sub-family" pattern; option (b) is NOT a reversal**: Wave 1 Bitcoin research set `family="utxo-btc"` (`docs/zh/chains/03-bitcoin.md:391`); Wave 3 Cardano set `family="cardano-eutxo"` (`docs/zh/chains/06-cardano.md:359`). **There is no generic `family="utxo"` abstraction in the current codebase** — UTXO is a model category, family is an adapter category, and the two have been kept distinct by explicit naming. Therefore naming option (b) `"avalanche-utxo"` is **consistent with the established convention**, not an extension or reversal of the family abstraction.

**Rationale 2 — sharing an adapter introduces MORE conditional branches than two independent adapters**: even if option (a) forces shared use of `UTXOAdapter`, that adapter must still branch internally on (a) namespace assembly (BTC none, X-Chain prepend `avm.`), (b) balance source (BTC via Esplora REST, X-Chain via `avm.getAllBalances`), (c) ID decoding (BTC hex, X-Chain cb58), (d) uint64 encoding (BTC int/float, X-Chain string), (e) auth (BTC basic auth, X-Chain none), (f) tx schema parsing (BTC flat vin/vout, X-Chain nested unsignedTx). That's **six full-duplex axes of divergence**; sharing one class becomes `if chain==...` hell, violating SRP and testability.

**Rationale 3 — DSL field expansion is the genuinely needed artifact**: regardless of option, the DSL must add `namespace_prefix` / `multi_asset` / `native_asset_id` / `numeric_encoding` / `id_encoding` (5 fields). Option (a) wants them so that one adapter can branch on chain; option (b) wants them so that both adapters honor a declarative schema. **These fields are equally useful under option (b)** (BTC config: `namespace_prefix:""`, `multi_asset:false`, `numeric_encoding:int`; X-Chain config: `namespace_prefix:"avm."`, `multi_asset:true`, `numeric_encoding:string`). So "we need DSL fields to enable adapter reuse" is a false premise; DSL field expansion stands on its own declarative-expressiveness needs, independent of adapter sharing.

#### Family-boundary design philosophy

- **Is family partitioned by "protocol model (UTXO/Account)" or by "protocol implementation (Bitcoin Core / avalanchego / cardano-node)"?**: Waves 1 and 3 already chose **the latter** (`utxo-btc` and `cardano-eutxo` are implementation-level names). This research recommends **continuing that convention**, placing `avalanche-utxo` as a sibling.
- **Adapter reuse rate vs schema cleanliness**: observed reuse ~35 % (shared UTXO concept + POST JSON-RPC + read-only benchmark scope), but 65 % divergence (namespace / multi-asset / encoding / auth / tx schema / endpoint routing) spread across every layer. Adapter merging saves less than the cost of maintaining conditional branches.
- **Not foreclosing future abstraction**: if waves 5+ add Litecoin / Dogecoin / BCH (each 95 %+ reuses BitcoinAdapter) and P-Chain (90 %+ reuses AvalancheXAdapter), a future common base `UTXOAdapterBase` (template-method pattern) could be extracted when a third sibling appears. **Extracting it now is premature abstraction.**

#### ⚠️ Family Reversal Risk Assessment (core deliverable for user)

**Reversal risk level: 🟢 LOW (near-zero)**

| Risk dimension | Assessment | Detail |
|---|---|---|
| Reverses Bitcoin family name? | **No** | Bitcoin is currently `family="utxo-btc"`; this recommends `family="avalanche-utxo"` — siblings, **no edit to 03-bitcoin.md family field required** |
| Reverses Bitcoin DSL schema? | **No** | New DSL fields (`namespace_prefix` / `multi_asset` etc.) take defaults for Bitcoin (`""` / `false`); neither breaks existing Bitcoin config nor requires BitcoinAdapter rewrite |
| Reverses the "UTXO = single adapter" assumption? | **No** | Wave 1 Bitcoin research never claimed "the UTXO family has only one adapter"; it explicitly stated "BitcoinAdapter (UTXO family seed; later reused by Litecoin/Dogecoin/BCH)" — i.e. same-family forks (LTC/DOGE/BCH) reuse, **different-family chains (Avalanche) do NOT reuse — which fits wave 1's stated boundary** |
| Reverses any existing "family" abstraction? | **No** | family is currently a string naming convention in this codebase with no strong-type/inheritance hierarchy; adding new family values is additive |
| Requires user approval for family extension? | **Recommended but not required** | Recommend user confirms family naming convention at the end of this wave (e.g. whether all UTXO chains should share a `utxo-*` prefix or use per-implementation names), but **this decision can be committed independently within wave 4** |

**Conclusion**: this recommendation (option b, `family="avalanche-utxo"`) **does NOT reverse the wave 1 Bitcoin family decision** and can land alongside wave 4 commit without waiting on user. However, if the user wants a stricter convention (e.g. unified `utxo-bitcoin` / `utxo-avalanche` / `utxo-cardano` prefix), that's a cosmetic refactor for wave 5 and does not change this research's technical conclusion.

**The one item that DOES need user decision**: is the DSL `namespace_prefix` field chain-level or method-level?
- Variant A: chain-level (the whole chain shares one prefix; X-Chain configures `"avm."`, Info is a separate chain config) — simpler
- Variant B: method-level (one chain may mix multiple prefixes; `avm.*` + `info.*` coexist under one chain) — more flexible but more complex
- This research leans toward **Variant A + multi-chain split** (treat Info as an independent sub-chain), but P2-DESIGN-v2 must make the call.

---

## Open Questions

- [ ] **`avm.issueTx` write paths**: include in v1 benchmark? Requires private-key signing (secp256k1) + cb58 encoding; high implementation cost; recommend skipping in v1 (same as Bitcoin tx broadcast).
- [ ] **Official endpoint quota**: no rate-limit observed but no SLA promised in docs; add monitoring in wave 2.
- [ ] **C-Chain atomic ImportTx cross-chain**: C-Chain → X-Chain cross-chain tx shows up as `ImportTx` on the X-Chain side; should it be a separately measured method?
- [ ] **Should P-Chain be researched independently?**: shares cb58 / bech32 / multi-asset / namespace pattern (`platform.*`) with X-Chain; if added, `AvalancheXAdapter` could be renamed `AvalancheAVMPVMAdapter`. Recommend P-Chain as a separate research item to preserve method-level evidence quality.
- [ ] **Family naming convention**: does the user mandate a unified `utxo-*` prefix? See end of §11.8 reversal risk assessment.

---

## Changelog

| Date | Author | Change |
|---|---|---|
| 2026-05-23 | Hermes Agent | Initial research: based on `api.avax.network` live probes + avalanchego 1.14.2 commit `6e5acf9`. Sections 1–11 fully populated. **Core deliverables**: family-boundary decision recommending option (b) — independent `avalanche-utxo` — plus reversal risk assessment (🟢 low, does not break wave 1 Bitcoin family). **DSL additions ASK**: namespace_prefix / multi_asset / native_asset_id / numeric_encoding / id_encoding (5 fields). **Evidence correction**: context-supplied example address `X-avax1pa5vu24v3hd0y9rdqekv9msrz86s90uvc3xyhq` has invalid checksum; replaced throughout with `X-avax13k6hxpfuu80dlnqlqs0dxxjrzl4lxz94n38vnw` (extracted from block 517990, verified via getBalance round-trip). |
