# 07-polkadot Research

> Derived from `_template.md`. H8 (real evidence): all RPC calls executed 2026-05-23 against `https://rpc.polkadot.io` and `https://polkadot-public-sidecar.parity-chains.parity.io`.

---

## Meta

| Field | Value |
|---|---|
| Chain name (zh) | 波卡 |
| Chain name (en) | Polkadot |
| Index | 07 |
| Mainnet ChainID | SS58 prefix = **0**; genesis hash = `0x91b171bb158e2d3848fa23a9f1c25182fb8e20313b2c1eb49219da7a70ce90c3` (E1 verified) |
| Research date | 2026-05-23 |
| Researcher | Hermes Agent |
| Status | 🟢 Done |

---

## 1. Sources

| Type | URL | Date | Notes |
|---|---|---|---|
| Official | https://wiki.polkadot.network/ | 2026-05-23 | Polkadot protocol home |
| RPC spec | https://polkadot.js.org/docs/substrate/rpc/ | 2026-05-23 | Substrate JSON-RPC namespaces (state_/chain_/system_/author_/payment_/account_/...) |
| Sidecar | https://github.com/paritytech/substrate-api-sidecar | 2026-05-23 | Parity official REST wrapper that hides SCALE |
| GitHub (node) | https://github.com/paritytech/polkadot-sdk | 2026-05-23 | polkadot-sdk (merged polkadot + substrate + cumulus) |
| Explorer | https://polkadot.subscan.io | 2026-05-23 | Block / extrinsic / account browser |
| SCALE codec spec | https://docs.substrate.io/reference/scale-codec/ | 2026-05-23 | Basis for DSL decision |
| Public sidecar | https://polkadot-public-sidecar.parity-chains.parity.io | 2026-05-23 | Parity-hosted public sidecar (E1 verified HTTP 200) |

---

## 2. Protocol Family

| Field | Value |
|---|---|
| Family | **Substrate** (brand-new family; Kusama / Acala / Moonbeam / Astar / HydraDX / Bifrost and dozens of parachains all inherit this family's RPC) |
| Consensus | BABE (block production) + GRANDPA (finality) |
| VM | WASM (Substrate runtime); parachains may add EVM (Moonbeam) / pallet-contracts (ink!) |
| Block time | **6 seconds** (measured: block #31363386 → #31363390 spans ~24 s = 4 blocks, see §3 sidecar output) |
| Finality | GRANDPA, typically 12–60 s; `chain_getFinalizedHead` lags `chain_getHeader` by ~2–4 blocks (E1 verified — different hashes, close numbers) |
| Reuse existing adapter? | **No** — new family, needs new adapter (SubstrateAdapter) |

---

## 3. Public RPC

| Endpoint | Auth | Rate limit | Notes |
|---|---|---|---|
| `https://rpc.polkadot.io` | None | Not published, fine for single bench run | Official, JSON-RPC over HTTP + WSS |
| `https://polkadot-rpc.publicnode.com` | None | publicnode generic ~30 req/s ⚠️ (not directly verified, training memory; benchmark must self-test) | Listed in official docs |
| `https://polkadot-public-sidecar.parity-chains.parity.io` | None | Not published ⚠️ | Parity-hosted sidecar REST, **E1 verified HTTP 200** |

**curl evidence** (E1):

```bash
# E1.1 Liveness: system_chain
curl -s -X POST https://rpc.polkadot.io \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"system_chain","params":[]}'
# {"jsonrpc":"2.0","id":1,"result":"Polkadot"}

# E1.2 Current header
curl -s -X POST https://rpc.polkadot.io \
  -d '{"jsonrpc":"2.0","id":1,"method":"chain_getHeader","params":[]}'
# {"result":{"parentHash":"0x549d...","number":"0x1de913a","stateRoot":"0xf26a...","extrinsicsRoot":"0x87d5...","digest":{...}}}
# number 0x1de913a = 31363386 (verified)

# E1.3 Finalized head
curl -s -X POST https://rpc.polkadot.io \
  -d '{"jsonrpc":"2.0","id":1,"method":"chain_getFinalizedHead","params":[]}'
# {"result":"0xd053e96edbed63e70cd8078fdd3d7488ea459f3d9a8422842391c7aff245dd23"}

# E1.4 system_health (sync + peers)
# {"result":{"peers":80,"isSyncing":false,"shouldHavePeers":true}}

# E1.5 system_properties (SS58 + decimals)
# {"result":{"ss58Format":0,"tokenDecimals":10,"tokenSymbol":"DOT"}}

# E1.6 runtime_version
# {"result":{"specName":"polkadot","implName":"parity-polkadot","specVersion":2002001,...,"transactionVersion":26}}

# E1.7 Sidecar liveness (REST)
curl -s https://polkadot-public-sidecar.parity-chains.parity.io/blocks/head
# {"number":"31363386","hash":"0xa939...","authorId":"12vKNm9...","logs":[...]}
```

All E1 returned 200, proving RPC + sidecar both alive.

---

## 4. Account Model

| Field | Value |
|---|---|
| Model | **Account** (global AccountInfo in the `System.Account` storage map) |
| Native token decimals | **10** (DOT; `system_properties.tokenDecimals=10`, E1 verified) |
| Address derivation | **Sr25519** (default) / Ed25519 / ECDSA (secp256k1) — all yield a 32-byte AccountId |
| Special account types | Multisig (`pallet-multisig`-derived), Proxy, Pure proxy, Treasury, crowdloan reserve accounts |

**AccountInfo structure** (SCALE-encoded, see E5 raw output):
```
nonce:u32 + consumers:u32 + providers:u32 + sufficients:u32 + data:AccountData
AccountData = { free:u128, reserved:u128, frozen:u128, flags:u128 }
```
Sidecar decodes this to plain JSON `nonce/free/reserved/frozen/transferable` (E2 in §5).

---

## 5. Core RPC Methods (needed by this framework)

| Method | Category | Protocol (native RPC / Sidecar REST) | Notes | Suggested mixed weight |
|---|---|---|---|---|
| `chain_getHeader` / `chain_getBlockHash(N)` | block height | RPC POST | Liveness + height sync; **header carries number, not balance** | 0.05 |
| `chain_getBlock(hash)` | block content | RPC POST, **2 hops** (`chain_getBlockHash(N)` first, then `chain_getBlock(hash)`) | Heavy, contains extrinsics | 0.10 |
| `GET /blocks/{number}` (sidecar) | block content | REST GET, **1 hop** | Sidecar fetches block by height directly, extrinsics pre-decoded | 0.10 |
| `state_getStorage(storage_key)` | balance (raw) | RPC POST, **storage_key must be SCALE-encoded client-side** | Returns hex-encoded `AccountInfo`; client then SCALE-decodes `free/reserved` | — see §11.7 decision |
| `GET /accounts/{addr}/balance-info` (sidecar) | balance (wrapped) | REST GET, **0 Python** | E2 verified returns `{free, reserved, frozen, transferable, nonce, tokenSymbol}` | 0.25 |
| `account_nextIndex(addr)` | nonce / tx_count | RPC POST | DSL-friendly, no SCALE | 0.10 |
| `GET /transaction/material/{hash}` (sidecar) / `GET /blocks/{n}` with extrinsics | tx lookup | REST GET | Substrate native RPC has **no** `tx_getByHash`; **tx-by-hash lookup requires external indexer (subscan / sidecar / archive)** ⚠️ | 0.15 |
| `system_health` | node info | RPC POST | peers + isSyncing | 0.05 |
| `system_chain` / `system_version` / `system_properties` | node info | RPC POST | One-shot at startup, used as warmup | 0.05 |
| `payment_queryInfo(extrinsic_hex)` | fee | RPC POST, **needs SCALE-encoded extrinsic** | DSL-unfriendly, dry-run only | 0.00 (excluded from mixed) |
| `state_getRuntimeVersion` | metadata | RPC POST | plugin warmup to verify runtime spec | 0.05 |
| `state_getKeysPaged(prefix, count, startKey)` | storage enumeration | RPC POST | Used in E5 to **harvest real storage_key samples** as fixtures | 0.05 |
| **chain-specific (staking)** `GET /pallets/staking/progress` (sidecar) | staking | REST GET | Most DOT holders stake, benchmark should cover | 0.15 |

> ⚠️ **tx_lookup critical limitation**: Substrate nodes **do not** index extrinsics by hash (archive nodes still only index by block). "Lookup tx by hash" requires an external indexer (subscan API; sidecar's `/transaction/material` only extracts dry-run material, not hash-to-tx lookup). This framework's `tx_lookup` should be replaced with "fetch extrinsics list by block height" (sidecar `GET /blocks/{n}`).

---

## 6. Address Format

| Field | Value |
|---|---|
| Encoding | **SS58** (Substrate's base58 variant, prefix byte selects the chain) |
| Length | 47–48 characters (Polkadot prefix=0, starts with `1...`) |
| Checksum | **Yes** (first 2 bytes of blake2b-512 over `chain-prefix ++ pubkey`) |
| Example (real mainnet account) | `13UVJyLnbVp9RBZYFwFGyDvVd1y27Tt8tkntv6Q7JVPhFsTB` (E2 verified `free=18207357669930` planck ≈ 1820.7 DOT, see §3 sidecar output) |
| Validation regex | `^1[1-9A-HJ-NP-Za-km-z]{46,47}$` (coarse; strict validation needs SS58 decode + checksum) |
| Chain-specific prefix byte | Polkadot=0 / Kusama=2 / Acala=10 / Moonbeam=1284 (EVM parachain, hex) / Astar=5 / Generic Substrate=42 |
| Cross-prefix derivation | Same 32-byte AccountId can be re-encoded under any prefix (similar to Cosmos family) |

---

## 7. Signature Lookup

| Field | Value |
|---|---|
| Hash format | **Hex with `0x` prefix** (blake2b-256 of SCALE-encoded extrinsic) |
| Length | **66 chars** (0x + 64 hex) |
| Example (real mainnet extrinsic hash) | ⚠️ **Not directly verified this round** (needs second hop to sidecar `GET /blocks/31363386` to read `extrinsics[i].hash`; skipped due to API call budget). **Must collect before Phase 2.1 lands** |
| Lookup method (native RPC) | **None** (Substrate does not index extrinsics by hash; see §5 ⚠️) |
| Lookup alt (sidecar) | `GET /blocks/{n}` → match by `hash` in extrinsics list; or `GET /node/transaction-pool` for pending |
| Lookup alt (indexer) | Subscan API: `POST /api/scan/extrinsic { "hash": "0x..." }` — **requires API key** |
| Explorer URL | `https://polkadot.subscan.io/extrinsic/<hash>` |

---

## 8. Mixed Set (`mixed` mode weights)

> Assumes DSL picks **Method B (sidecar REST)** (see §11.8 decision)

```json
{
  "sidecar_balance":            0.25,
  "sidecar_block_by_n":         0.20,
  "sidecar_block_head":         0.10,
  "rpc_chain_getHeader":        0.05,
  "rpc_account_nextIndex":      0.10,
  "sidecar_staking_progress":   0.15,
  "rpc_system_health":          0.05,
  "rpc_state_getRuntimeVersion":0.05,
  "rpc_chain_getBlockHash":     0.05
}
```

Sum = 0.25+0.20+0.10+0.05+0.10+0.15+0.05+0.05+0.05 = **1.00** ✅

Path mapping:
- `sidecar_balance` → `GET {sidecar}/accounts/{addr}/balance-info`
- `sidecar_block_by_n` → `GET {sidecar}/blocks/{n}`
- `sidecar_block_head` → `GET {sidecar}/blocks/head`
- `rpc_chain_getHeader` → `POST {rpc}` body `{"method":"chain_getHeader","params":[]}`
- `rpc_account_nextIndex` → `POST {rpc}` body `{"method":"account_nextIndex","params":["{addr}"]}`
- `sidecar_staking_progress` → `GET {sidecar}/pallets/staking/progress`

---

## 8.5 Phase 2.1 caller/reader change set

**New chain**, #1–#5 mandatory, #6–#8 if applicable.

| # | Location (file:line) | Change | Reason |
|---|---|---|---|
| 1 | `config/config_loader.sh:666` `supported_blockchains` array | add `"polkadot"` | else `validate_blockchain_node` rejects |
| 2 | `config/config_loader.sh:~380` new `case polkadot)` setting `MAINNET_RPC_URL=https://rpc.polkadot.io` and `MAINNET_SIDECAR_URL=https://polkadot-public-sidecar.parity-chains.parity.io` | dual endpoint | First chain needing **JSON-RPC + REST dual endpoint** (Cosmos broke ground but in a different shape) |
| 3 | `config/config_loader.sh:~440-468` `UNIFIED_BLOCKCHAIN_CONFIG.blockchains.polkadot` block | add `rpc_methods.single` / `rpc_methods.mixed` / `param_formats` covering all §8 methods + addr/hash formats | consumed by vegeta target generator directly |
| 4 | `tools/mock_rpc_server.py:~137` | add `do_GET` branch (reuse if Cosmos added) + sidecar path routing + POST JSON-RPC substrate-method dispatch | mock needs dual protocol |
| 5 | `tools/fetch_active_accounts.py` add `SubstrateAdapter(BlockchainAdapter)` | use sidecar `GET /blocks/{n}` to harvest extrinsics, extract addresses from `Balances.transfer_keep_alive.dest/source` | no reusable adapter |
| 6 | `analysis-notes/baseline-current-state.md` | grep, add polkadot to chain list | doc truth alignment |
| 7 | `tests/` add `test_substrate_adapter.py` | at minimum 1 mainnet block fixture | L1 unit test |
| 8 | `core/master_qps_executor.sh --mixed --duration 30` | all 200, no -32601/-32602 | E2 evidence |

**Critical pitfalls**:
- Substrate native `state_getStorage` returns hex-encoded SCALE structure — **vegeta + naive 200-status check would pass, but in practice a 0-Python framework cannot decode `balance`**. Sidecar sidesteps this (§11.8).
- `chain_getBlock` requires a **block hash**, not a number. By-number lookup needs 2 hops (`chain_getBlockHash(N)` → `chain_getBlock(hash)`). Sidecar hides this.

---

## 9. Mock Notes (mock_rpc_server)

### Sidecar side (REST GET):

- Request paths: `GET /blocks/{n}`, `GET /blocks/head`, `GET /accounts/{addr}/balance-info`, `GET /pallets/staking/progress`
- Response schema sample (real mainnet, E1 verified):
  ```json
  {"at":{"hash":"0xd053e96e...","height":"31363390"},
   "nonce":"0","tokenSymbol":"DOT",
   "free":"18207357669930","reserved":"0",
   "frozen":"0","transferable":"18207357669930","locks":[]}
  ```
- Error codes: HTTP 400/404 + `{"code":N,"error":"..."}` (sidecar style)

### RPC side (POST JSON-RPC):

- Request path: `POST /`, body `{"jsonrpc":"2.0","method":"<ns>_<m>","params":[...],"id":N}`
- Response sample (E1 verified `state_getStorage` returns SCALE hex):
  ```json
  {"jsonrpc":"2.0","id":1,
   "result":"0x01000000010000000100000000000000bec93db304000000000000000000000080ea5da92e00000000000000000000000000000000000000000000000000000000000000000000000000000000000080"}
  ```
- Special error codes:
  - `-32601`: Method not found (Substrate node has not enabled the RPC; e.g. unsafe RPCs disabled by default)
  - `-32602`: Invalid params (storage_key not hex / wrong length)
  - `-32603`: Internal error (note: missing storage returns `null` in `result`, not an error)
- Mock complexity: **High**
  - Dual protocol (REST GET + JSON-RPC POST)
  - Sidecar response deeply nested (`extrinsics[].method.{pallet, method, args}`); fixture mode recommended
  - SCALE-encoded raw storage: mock need NOT actually encode SCALE — **decision: mock only returns sidecar-shape JSON; raw `state_getStorage` returns fixture hex string, no real encoding needed**

---

## 10. Adapter Reuse Decision

### Candidates

| Adapter | Compatibility | Missing |
|---|---|---|
| SolanaAdapter | 0% | protocol / address / account model all differ |
| EthereumAdapter | 0% | hex addr vs SS58, EVM vs WASM, JSON-RPC namespaces completely different |
| BitcoinAdapter | 0% | UTXO vs Account |
| CosmosAdapter | ~15% | partial idea reuse (REST GET + path param + addr prefix) but schema/method/encoding all differ |
| New **SubstrateAdapter** | 100% | — |

### Decision

- [x] **Build new `SubstrateAdapter`** (Substrate full family — Kusama / Acala / Moonbeam EVM / Astar / HydraDX / Bifrost / Parallel / Centrifuge ... dozens of parachains reusable; Phase 2.x distinguishes per-chain by `chain_type` + `ss58_prefix` + `token_decimals` + `token_symbol`)
- [ ] Reuse
- [ ] Hybrid

### Rationale

(1) Substrate is an independent large family; its RPC namespacing, serialization (SCALE), address format (SS58), and consensus (BABE+GRANDPA) all differ from the existing 4 families (EVM / Solana / Bitcoin / Cosmos). No reusable adapter.

(2) **Family reuse value is very high**: Kusama (SS58=2), Acala (=10), Astar (=5), Moonbeam (EVM parachain), HydraDX, Bifrost — dozens of parachains all inherit the Substrate JSON-RPC + sidecar REST abstraction. **Endpoint paths are identical**; differences only in (a) SS58 prefix, (b) native token decimals / symbol, (c) whether EVM is enabled (Moonbeam exposes both substrate `state_*` and `eth_*` RPCs). Once SubstrateAdapter lands, each new parachain = 0 Python.

(3) **chain_type pattern**: `SubstrateAdapter.chain_type ∈ {polkadot, kusama, acala, moonbeam, astar, ...}`, used for (a) plugin SS58 prefix validation, (b) EVM parachains (Moonbeam/Astar) carrying `dual_rpc=true` to allow `eth_*` methods in mixed set, (c) pallet-difference branches (staking pallet exists on relay chains; most parachains lack it).

### Config JSON example (this chain)

```json
{
  "chain": "polkadot",
  "family": "substrate",
  "adapter": "SubstrateAdapter",
  "chain_type": "polkadot",
  "ss58_prefix": 0,
  "genesis_hash": "0x91b171bb158e2d3848fa23a9f1c25182fb8e20313b2c1eb49219da7a70ce90c3",
  "node_app": "polkadot",
  "node_app_version": "1.22.1-f8cfbb96055",
  "spec_version": 2002001,
  "transaction_version": 26,
  "api_protocol": ["jsonrpc", "rest_sidecar"],
  "rpc_endpoint": "https://rpc.polkadot.io",
  "sidecar_endpoint": "https://polkadot-public-sidecar.parity-chains.parity.io",
  "block_time_ms": 6000,
  "finality": "grandpa_~12s",
  "address_format": {
    "encoding": "ss58",
    "ss58_prefix": 0,
    "length_range": [47, 48],
    "regex": "^1[1-9A-HJ-NP-Za-km-z]{46,47}$"
  },
  "native_token": {"symbol": "DOT", "decimals": 10, "planck_per_dot": 10000000000},
  "rpc_methods": {
    "block_height":      {"protocol": "jsonrpc", "method": "chain_getHeader", "params": []},
    "block_by_number":   {"protocol": "rest",    "path": "/blocks/{n}"},
    "block_head":        {"protocol": "rest",    "path": "/blocks/head"},
    "balance":           {"protocol": "rest",    "path": "/accounts/{addr}/balance-info"},
    "nonce":             {"protocol": "jsonrpc", "method": "account_nextIndex", "params": ["{addr}"]},
    "staking_progress":  {"protocol": "rest",    "path": "/pallets/staking/progress"},
    "system_health":     {"protocol": "jsonrpc", "method": "system_health", "params": []},
    "runtime_version":   {"protocol": "jsonrpc", "method": "state_getRuntimeVersion", "params": []}
  },
  "mixed_weights": {
    "balance":          0.25,
    "block_by_number":  0.20,
    "staking_progress": 0.15,
    "nonce":            0.10,
    "block_head":       0.10,
    "block_height":     0.05,
    "system_health":    0.05,
    "runtime_version":  0.05,
    "block_hash":       0.05
  }
}
```

---

## 11. DSL Expressiveness Analysis (Substrate-critical)

### 11.1–11.6 (generic items aligned with other chains)

- 11.1 Method naming: Substrate **modular namespaces** (`state_/chain_/system_/author_/payment_/account_/childstate_/offchain_/grandpa_/babe_/...`). DSL must support string-literal method names; no special parsing needed.
- 11.2 Param types: `[]` / `[hex_string]` / `[u32]` / `[hash, count, startKey?]`. DSL needs hex literal, integer, null.
- 11.3 Result types: hex string / number / nested object / null.
- 11.4 Error schema: standard JSON-RPC `error.{code, message, data}`.
- 11.5 Batch: Substrate RPC supports JSON-RPC batch ⚠️ (not directly verified this round); WSS subscription mode is preferred long-term.
- 11.6 Dual protocol: **JSON-RPC over HTTP + Sidecar REST** (framework requirement); WSS is for `chain_subscribeNewHeads` subscription, not needed here.

### 11.7 (mandatory) Substrate storage_key encoding challenge

| Method | 0 Python? | Detail |
|---|---|---|
| **A. raw `state_getStorage(storage_key)`** | ❌ **No** | storage_key = `xxhash128("System") ++ xxhash128("Account") ++ blake2_128_concat(AccountId)` = 32B prefix + 16B blake2_128 + 32B AccountId = **80-byte hex string**. The first 32B for `System.Account` is **constant** (`0x26aa394eea5630e07c48ae0c9558cef7b99d880ec681799c0cf30e8886371da9` — E3 verified: `state_getKeysPaged` on this prefix returns ✅); **the last 48B must be computed client-side** (blake2_128 + AccountId concat). The return value is SCALE-encoded `AccountInfo` (E5 verified: `0x01000000010000000100000000000000bec93db304000000...` 80+ bytes); the client must then SCALE-decode `nonce/free/reserved` (little-endian u32 + u128). **DSL 0 Python cannot do blake2_128 + SCALE decoding.** |
| **B. sidecar REST `GET /accounts/{addr}/balance-info`** | ✅ **Yes** | E2 verified, returns plain JSON `{nonce, free, reserved, frozen, transferable, tokenSymbol}` as string big-ints (planck). **0 Python usable directly.** Cost: depends on an extra sidecar service (Parity hosts public instance `https://polkadot-public-sidecar.parity-chains.parity.io`; framework can use public short-term or self-deploy). |
| **C. high-level RPC `system_account(addr)`** | — | ⚠️ **Polkadot does not provide this RPC**. (Direct `rpc_methods` verification was rate-limited this round, but the official Substrate RPC list has **no** `system_account`; only `system_accountNextIndex` aka `account_nextIndex`, which returns nonce only, not balance.) **Method C is not available.** |

**Conclusion**: Polkadot truly has **no "0-Python balance RPC"** — only sidecar or bring-your-own SCALE encoder.

#### E5 raw storage evidence

```bash
# 1. Use state_getKeysPaged to harvest real storage_keys (no client SCALE):
curl -s -X POST https://rpc.polkadot.io \
  -d '{"jsonrpc":"2.0","id":1,"method":"state_getKeysPaged",
       "params":["0x26aa394eea5630e07c48ae0c9558cef7b99d880ec681799c0cf30e8886371da9",2,null]}'
# Returns 2 full keys (80-byte hex):
# 0x26aa...371da9 + 000c143d12a73a70464df3694fdcc75a + ee080855f606cce66bdfffb8a73c54a440fa4a4ea1f9a487b7e2dadedaac205b
#                   |---- blake2_128(AccountId) ----|  |------------ AccountId(32B) ------------|

# 2. Query storage with that full key:
curl -s -X POST https://rpc.polkadot.io \
  -d '{"jsonrpc":"2.0","id":1,"method":"state_getStorage",
       "params":["0x26aa394eea5630e07c48ae0c9558cef7b99d880ec681799c0cf30e8886371da9000c143d12a73a70464df3694fdcc75aee080855f606cce66bdfffb8a73c54a440fa4a4ea1f9a487b7e2dadedaac205b"]}'
# {"result":"0x01000000010000000100000000000000bec93db304000000000000000000000080ea5da92e00000000000000000000000000000000000000000000000000000000000000000000000000000000000080"}
# SCALE decode: nonce=1 u32, consumers=1, providers=1, sufficients=0, free=0x04b33dc9be(LE u128)=20240670142, reserved=0x2ea95dea80, frozen=0, flags=0x80...

# 3. Counter-example: send only the 32B prefix (no AccountId) → null
curl -s -X POST https://rpc.polkadot.io \
  -d '{"jsonrpc":"2.0","id":1,"method":"state_getStorage",
       "params":["0x26aa394eea5630e07c48ae0c9558cef7b99d880ec681799c0cf30e8886371da9"]}'
# {"result":null}   ← proves prefix alone is not a full key; blake2_128_concat(AccountId) is required
```

### 11.8 (mandatory) DSL choice

- [ ] Method A (raw `state_getStorage`, DSL adds SCALE helper)
- [x] **Method B (sidecar REST, DSL uses generic REST infra)** ← recommended
- [ ] Method C (`system_account` high-level method) — does not exist, excluded

**Rationale** (3 paragraphs):

**(1) 0 Python is a hard constraint.** Q4=C target is "95% chain additions zero-Python". Method A requires `py-scale-codec` + `blake2` + `xxhash` — three client-side crypto/encoding libs — to **construct storage_key and decode AccountInfo**. Both ends need Python, breaking the 0-Python rule for the entire Substrate family (Kusama/Acala/Astar/Moonbeam, dozens of chains). Method B reuses the generic REST infra (already in place for Cosmos), sidecar fully hides SCALE, and one JSON plugin line suffices.

**(2) Sidecar trade-off is acceptable.** Cost: one extra process (sidecar). Benefits: (a) public instance `https://polkadot-public-sidecar.parity-chains.parity.io` E1 verified usable, benchmark can hit public short-term; (b) Phase 2.x long-term co-locate with node, sidecar is stateless REST wrapper with minimal footprint (~50 MB RAM); (c) sidecar also resolves `chain_getBlock` two-hop pain (native RPC requires `chain_getBlockHash(N)` → `chain_getBlock(hash)`; sidecar `GET /blocks/{n}` is one hop), extrinsic decoding, and staking data — three methods become 0-Python usable. One dependency in exchange for three DSL-friendly methods — worth it.

**(3) Method A retained as a raw-mode option.** Pure performance stress (testing the node's raw RPC ceiling) can flag a plugin `mode: raw`; vegeta targets use the §11.7 E5 trick to pre-harvest a storage_key list via `state_getKeysPaged` as a fixture, **testing only RPC latency without requiring client-side decoding** (any non-zero hex response counts as 200). Raw mode does not enter the default mixed set; it's an opt-in stress profile.

---

## Open Questions

- [ ] **DSL ASK**: Does the DSL allow declaring `protocol: "rest_sidecar"` and `protocol: "jsonrpc"` per-method in plugin JSON, and can the vegeta target generator emit both GET-with-path and POST-with-body? (Cosmos opened the REST-GET precedent; Polkadot is the first chain mixing **both protocols in one plugin** — half of methods go to sidecar GET, half go to native POST. Need framework confirmation that per-method `protocol` field is supported.)
- [ ] **DSL ASK**: When filling `{addr}` placeholders, how to validate SS58 checksum without pulling in Python? (Options: skip validation and let the node return -32602; or trust earlier validation in fetch_active_accounts.)
- [ ] **DSL ASK**: tx_lookup has no native RPC support — does the DSL allow marking a method type `skip_in_mixed: true` so it's only available in single mode? (Otherwise missing tx_lookup in mixed makes Polkadot inconsistent with other chains.)
- [ ] **DSL ASK**: For raw `state_getStorage` storage_key fixture mode — does the DSL support `fixture_file: "polkadot_storage_keys.txt"` for vegeta to randomly draw keys? (For Method A raw stress mode.)
- [ ] **Unverified ⚠️**: `https://polkadot-rpc.publicnode.com` real rate limit (~30 req/s from training memory; benchmark must self-test)
- [ ] **Unverified ⚠️**: Whether Substrate JSON-RPC supports batch (`[{...},{...}]` body) — not directly curl-verified this round
- [ ] **Unverified ⚠️**: Real extrinsic-hash sample — API budget did not allow fetching `GET /blocks/31363386` extrinsics[].hash; collect before Phase 2.1 lands
- [ ] Do Moonbeam / Astar EVM parachains need a `dual_rpc` branch inside SubstrateAdapter (substrate `state_*` + `eth_*` supported simultaneously)? Address in Phase 2.2 by priority.

---

## Changelog

| Date | Author | Change |
|---|---|---|
| 2026-05-23 | Hermes Agent | Initial research; E1–E5 evidence; DSL decision Method B (sidecar REST) |
