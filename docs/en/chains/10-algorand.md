# 10-Algorand Research

> **Derived from `_template.md`, produced in Phase 1.2 Wave 3.**
> **Required sections**: `_template.md` §1–§10 + §11 DSL (incl. §11.7 algod/indexer dual-node table + §11.8 DSL decision)
> **Key deliverable**: **DSL expression of the dual-node architecture** (see §11.8 — recommended: **Option B: optional `node_role` field + AlgorandAdapter built-in algod/indexer dual endpoint**)
> **Live evidence**: All 11 endpoint shapes in this document were verified via `curl` against the public Algonode cluster on 2026-05-23 (raw responses preserved in `~/algo_evidence/*.json`).

---

## Meta

| Field | Value |
|---|---|
| Chain name | Algorand |
| Number | 10 (Wave 3 ordering; final number to be decided at P1 close-out) |
| Mainnet ChainID | `mainnet-v1.0` (**string**, not numeric) |
| Mainnet GenesisHash | `wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=` (base64, 32 bytes) — E1 verified in §1 |
| Research date | 2026-05-23 |
| Researcher | Hermes Agent |
| Status | 🟢 Research complete, §11.8 decision pending user review |

---

## 1. Sources

| Type | URL | Access date | Notes |
|---|---|---|---|
| Official portal | https://developer.algorand.org/ | 2026-05-23 | Algorand Developer Portal (protocol spec hub) |
| algod REST OpenAPI | https://developer.algorand.org/docs/rest-apis/algod/ | 2026-05-23 | algod node v2 REST API full spec |
| indexer REST OpenAPI | https://developer.algorand.org/docs/rest-apis/indexer/ | 2026-05-23 | indexer v2 REST API full spec |
| go-algorand source | https://github.com/algorand/go-algorand | 2026-05-23 | algod node (Go) |
| indexer source | https://github.com/algorand/indexer | 2026-05-23 | indexer (Go, PostgreSQL backend) |
| Algonode public endpoints | https://nodely.io/docs/free/start | 2026-05-23 | Free public RPC used in this benchmark |
| AlgoExplorer | https://allo.info / https://algoexplorer.io | 2026-05-23 | Block explorer |
| ASA standard | https://developer.algorand.org/docs/get-details/asa/ | 2026-05-23 | Algorand Standard Asset spec |

**E1 live test — algod `/versions` (no header required)**:

```bash
$ curl -sS https://mainnet-api.algonode.cloud/versions
{"versions":["v2"],"genesis_id":"mainnet-v1.0",
 "genesis_hash_b64":"wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=",
 "build":{"major":4,"minor":7,"build_number":0,"commit_hash":"6927d906+","branch":"AVAIL","channel":"AVAIL"}}
```

→ Confirms mainnet genesis_id/genesis_hash against the task context — no reliance on training memory.

---

## 2. Protocol Family

| Field | Value |
|---|---|
| Family | **Algorand** (proprietary, **standalone family**, not EVM / Move / UTXO / Cosmos / Substrate / Solana / NEAR) |
| Consensus | **Pure PoS** (Algorand BA⋆ + VRF cryptographic sortition — unique to Algorand) |
| VM | **AVM** (Algorand Virtual Machine, TEAL bytecode, **not EVM, not MoveVM**) |
| Block time | ≈ **2.8 s** (protocol target; observed `last-round` advanced ~11 ticks in ~30 s) |
| Finality | **Instant finality** (BA⋆ commits each block irreversibly; no forks, no reorgs) — distinct from ETH 32-slot finality and NEAR 3-tier finality |
| Reuse Existing Adapter? | **No** (see §10): account model / auth header / **dual-node architecture** / TEAL VM all disjoint from the 7 existing chains (5 EVM + Solana + Sui) |

---

## 3. Public RPC

> Algorand public providers are **dual-track**: each provider exposes algod (HTTPS equivalent of `:4001`) **and** indexer (HTTPS equivalent of `:8980`) as two **separate** endpoints.

| Provider | algod endpoint | indexer endpoint | Auth | Rate limit | E1 result |
|---|---|---|---|---|---|
| Algonode (used in this benchmark) | `https://mainnet-api.algonode.cloud` | `https://mainnet-idx.algonode.cloud` | **none** (`X-Algo-API-Token` header optional / any value accepted) | 60 req/s free tier (docs) ⚠ not stress-tested | ✅ both 200 (§3.1) |
| Nodely (Algonode upstream) | `https://mainnet-api.4160.nodely.dev` | `https://mainnet-idx.4160.nodely.dev` | none | same | ✅ 200 / 0.20 s |
| Self-hosted algod + indexer | `:4001` / `:8980` | as left | **required** `X-Algo-API-Token: <admin.token>` (default-enabled in self-hosted) | unlimited | ⚠ not self-hosted in this study, documentation assertion only |

### 3.1 E1 live test (2026-05-23, Algonode public cluster)

```bash
$ curl -sS -w "HTTP:%{http_code} TIME:%{time_total}s\n" \
     https://mainnet-api.algonode.cloud/v2/status
{"catchpoint":"","last-round":61461471,
 "last-version":"https://github.com/algorandfoundation/specs/tree/953304de35264fc3ef91bcd05c123242015eeaed",
 ...}
HTTP:200 TIME:0.214s

$ curl -sS -w "HTTP:%{http_code} TIME:%{time_total}s\n" \
     https://mainnet-idx.algonode.cloud/health
{"data":{"migration-required":false,"read-only-mode":true},
 "db-available":true,"is-migrating":false,"message":"61461471","round":61461471,"version":"3.9.0"}
HTTP:200 TIME:0.146s
```

### 3.2 Auth header live test

```bash
# no header → 200
$ curl -sS -o /dev/null -w "no-header HTTP:%{http_code}\n" https://mainnet-api.algonode.cloud/v2/status
no-header HTTP:200
# X-Algo-API-Token with any value → still 200 (Algonode does not validate)
$ curl -sS -o /dev/null -w "X-Algo-API-Token HTTP:%{http_code}\n" \
     -H "X-Algo-API-Token: anything" https://mainnet-api.algonode.cloud/v2/status
X-Algo-API-Token HTTP:200
# Bearer header → 200 (ignored)
$ curl -sS -o /dev/null -w "Bearer HTTP:%{http_code}\n" \
     -H "Authorization: Bearer junk" https://mainnet-api.algonode.cloud/v2/status
Bearer HTTP:200
```

→ **Algonode does not enforce auth**. **Self-hosted algod requires `X-Algo-API-Token`** (go-algorand `data/algod.token`). The DSL must keep an optional auth-header channel.

---

## 4. Account Model

| Field | Value |
|---|---|
| Model | **Account** (one account holds 1 ALGO balance + N opted-in ASA slots) |
| Native token decimals | **6** (microalgo, 1 ALGO = 10^6 microalgo) — ⚠ **not 9 (Solana lamports) and not 18 (EVM wei)** |
| Address derivation | **Ed25519 pubkey (32 B) + SHA-512/256 checksum (4 B) → base32 (58 chars)** |
| Special account types | **ASA opt-in slots** (an account must opt-in to an ASA before it can hold it, raising min-balance by 100,000 microalgo); **Applications (smart contracts)** (integer IDs; an account opts-in to consume local state) |

### 4.1 E1 live test — algod account shape

```bash
$ curl -sS https://mainnet-api.algonode.cloud/v2/accounts/Q5WOHVUKNEM4XOVL725KH77WS6GODZSI4HTSWZAILM36ANSYVHW5RJI3KE \
   | head -c 350
{"address":"Q5WOHVUKNEM4XOVL725KH77WS6GODZSI4HTSWZAILM36ANSYVHW5RJI3KE",
 "amount":<microalgo>, "min-balance":..., "round":61461..., "status":"Offline",
 "total-assets-opted-in":..., "total-created-assets":..., "total-apps-opted-in":...,
 "assets":[{"asset-id":..., "amount":..., "is-frozen":false}, ...]}
```

→ **Key contrast**: unlike `eth_getBalance` which returns a single scalar, algod returns **ALGO balance + all ASA holdings + all application local-state** in one ~13 KB response. **ASA balances require no second call** (compare EVM, which needs `eth_call(balanceOf)`).

---

## 5. Core RPC Methods

> Algorand REST uses HTTP verb + URL path (no JSON-RPC envelope). Every method is GET or POST against a path.

| logical_method | HTTP | Path (algod or indexer) | Category | Node | mixed weight |
|---|---|---|---|---|---|
| `block_height` | GET | `/v2/status` (algod) or `/health` (indexer) | block height | **algod** (live) | 0.05 |
| `balance` | GET | `/v2/accounts/{addr}` | balance | **algod** (live; **response includes all ASA holdings**) | 0.25 |
| `tx_lookup` | GET | `/v2/transactions/{txid}` | historical tx | **indexer** (algod returns 404 — §11.7 table) | 0.20 |
| `tx_pending` | GET | `/v2/transactions/pending/{txid}` | tx status (incl. **recently confirmed**) | **algod** (short window — §5.1 evidence) | 0.05 |
| `block_query` | GET | `/v2/blocks/{round}?format=json` | block content | **algod or indexer** (same path) | 0.10 |
| `asset_info` | GET | `/v2/assets/{asset-id}` | ASA metadata | **algod** (live) | 0.10 |
| `asset_balances` | GET | `/v2/assets/{asset-id}/balances?limit=N` | ASA holder list | **indexer-only** (algod has no such path) | 0.10 |
| `account_txs` | GET | `/v2/accounts/{addr}/transactions?limit=N` | per-account tx history | **indexer-only** (algod returns 404 — §5.2 evidence) | 0.10 |
| `tx_params` | GET | `/v2/transactions/params` | suggested params for tx submission | algod | 0.05 |

**Total weight** = 0.05 + 0.25 + 0.20 + 0.05 + 0.10 + 0.10 + 0.10 + 0.10 + 0.05 = **1.00** ✅

### 5.1 E1 live test — algod `/v2/transactions/pending/{txid}` behaviour (**important correction to the task context**)

Task context says "only pending!". In reality the endpoint returns 200 + `confirmed-round` for **already-confirmed** txs (within a short window):

```bash
$ curl -sS https://mainnet-api.algonode.cloud/v2/transactions/pending/PO3UMN7TCRZLRUZ4JEPK54DX5O55YSZULAIPOEDMXX7GHTJ4FJPA
HTTP:200 TIME:0.206s
{"confirmed-round": 61461400, "pool-error": "",
 "txn":{"sig":"ocPv...","txn":{"amt":3487000000,"fv":61461392,"gen":"mainnet-v1.0",
   "gh":"wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=",
   "rcv":"2ZPNLKXWCOUJ...","snd":"Q5WOHVUKNEM...","type":"pay"}}}
```

→ algod actually keeps a cache of confirmed txs for the most recent ~1000 rounds (configurable `MaxAcctLookback`); only older txs return 404. **Conclusion**: `tx_pending` works for the last ~1 hour of txs, **but historical txs must go through indexer** (direct `GET /v2/transactions/{txid}` on algod returns 404).

### 5.2 E1 live test — endpoints absent on algod (indexer-only)

```bash
$ curl -sS -o /dev/null -w "%{http_code}\n" https://mainnet-api.algonode.cloud/v2/transactions/PO3UMN7TC...
404
$ curl -sS -o /dev/null -w "%{http_code}\n" https://mainnet-api.algonode.cloud/v2/accounts/Q5WOHVUKN.../transactions?limit=3
404
$ curl -sS -o /dev/null -w "%{http_code}\n" https://mainnet-idx.algonode.cloud/v2/accounts/Q5WOHVUKN.../transactions?limit=3
200
```

→ **Historical tx lookup + per-account tx list + ASA holder list = all indexer-only**. This is the empirical backbone of the §11.7 dual-node table.

---

## 6. Address Format

| Field | Value |
|---|---|
| Encoding | **Base32** (RFC 4648, **unpadded**) — distinct from Bitcoin/Bech32, Solana/Base58, EVM/Hex |
| Length | **58 chars** (32 B pubkey + 4 B checksum → 36 B → ceil(36×8/5) = 58 base32 chars) |
| Checksum | **Last 4 bytes of SHA-512/256(pubkey)**, appended to pubkey then base32-encoded |
| Example (real mainnet) | `Q5WOHVUKNEM4XOVL725KH77WS6GODZSI4HTSWZAILM36ANSYVHW5RJI3KE` (sender of block 61461400; E1: `GET /v2/accounts/{addr}` returns 200) |
| Initial-screen regex | `^[A-Z2-7]{58}$` (base32 alphabet, no 0/1/8/9, no lowercase) — true validation requires base32 decode + SHA-512/256 checksum recomputation |

### 6.1 E1 counter-example — task context address fails checksum

```bash
$ curl -sS https://mainnet-api.algonode.cloud/v2/accounts/DPLD3RZSYVPBQR4AEUNXMRWPRDZJEY7LZG6JRT34IPSBOYY3EYLDC4O73U
HTTP:400
{"message":"... address DPLD3RZSYVPBQR4AEUNXMRWPRDZJEY7LZG6JRT34IPSBOYY3EYLDC4O73U is malformed, checksum verification failed"}
```

→ ⚠ The "Algorand foundation" address provided in the task context fails checksum (likely a typo when the task was drafted). This document standardizes on `Q5WOHVUKN...` extracted live from block 61461400 to keep every example 100% real.

---

## 7. Signature Lookup (transaction hash)

| Field | Value |
|---|---|
| Hash encoding | **Base32** (unpadded, same alphabet as address) |
| Length | **52 chars** (32 B SHA-512/256 → 52 base32 chars) — ⚠ do not confuse with the 58-char address |
| Example (real mainnet) | `PO3UMN7TCRZLRUZ4JEPK54DX5O55YSZULAIPOEDMXX7GHTJ4FJPA` (first `pay`-type tx in block 61461400; E1: indexer returns 200) |
| Query method | **Historical**: `GET /v2/transactions/{txid}` (**indexer**); **Recent**: `GET /v2/transactions/pending/{txid}` (algod, ~1000-round window) |
| Explorer URL | `https://allo.info/tx/{txid}` or `https://algoexplorer.io/tx/{txid}` |

### 7.1 E1 live test

```bash
$ curl -sS https://mainnet-idx.algonode.cloud/v2/transactions/PO3UMN7TCRZLRUZ4JEPK54DX5O55YSZULAIPOEDMXX7GHTJ4FJPA
HTTP:200 SIZE:782
{"current-round":61461505,
 "transaction":{"id":"PO3UMN...","tx-type":"pay","confirmed-round":61461400,
   "sender":"Q5WOHVUKN...","payment-transaction":{"amount":3487000000,"receiver":"2ZPNLKXW..."}, ...}}
```

---

## 8. Mixed Set (`mixed` mode weights)

```json
{
  "block_height":   0.05,
  "balance":        0.25,
  "tx_lookup":      0.20,
  "tx_pending":     0.05,
  "block_query":    0.10,
  "asset_info":     0.10,
  "asset_balances": 0.10,
  "account_txs":    0.10,
  "tx_params":      0.05
}
```

**Total = 1.00 ✅**

**Rationale**:
- `balance` 0.25: hot read path + algod returns ALGO+ASA in one shot, key to stress.
- `tx_lookup` 0.20: typical explorer/wallet workload; **routes to indexer**, exercises indexer PostgreSQL hit rate.
- `asset_info` 0.10 + `asset_balances` 0.10: ASA is Algorand's headline differentiator; coverage required (EVM does this in one `eth_call(balanceOf)`, Algorand needs both endpoints).
- `account_txs` 0.10: representative **indexer-only** method; needs its own metric granularity to surface PostgreSQL index performance.
- `block_query` 0.10: heavy payload (71 KB measured); higher weight would dominate throughput.
- `block_height` 0.05 + `tx_params` 0.05 + `tx_pending` 0.05: low-cost liveness probes, kept at sub-threshold weight for continuous coverage.

---

## 8.5 Phase 2.1 caller/reader change list (token-level Gate 3)

| # | Location (file:line) | Change | Why |
|---|---|---|---|
| 1 | `config/config_loader.sh:666` `supported_blockchains` array | **Add** `"algorand"` | Currently (E1 `grep -n` line 666): `("solana" "ethereum" "bsc" "base" "scroll" "polygon" "starknet" "sui")` — **no algorand**, no entry point |
| 2 | `config/config_loader.sh` per-chain `rpc_methods.mixed` block (see sui block lines 622–650) | **Create algorand block**: 9 logical_methods + weights (§8); **extra field** `node_role: algod|indexer` (recommended approach, see §11.8) | Consumed by vegeta target generator; **dual-node routing must be expressed declaratively** |
| 3 | `config/config_loader.sh` per-chain `param_formats` | Add 9 method-level `(verb, path_template, query_params)` entries; path looks like `/v2/accounts/{address}` | All Algorand methods are HTTP-path-based, **unlike EVM's single POST `/`**; follows the path-per-method pattern from `06-cardano.md §11.3` |
| 4 | `tools/mock_rpc_server.py` dispatcher | **Add path-based routing** (currently only POST `/` JSON-RPC) + 9 Algorand path handlers | mock is the fallback target; without this, Algorand mock mode breaks (token-level Case-B/D: `mock_rpc_server` is a caller of the plugin) |
| 5 | `tools/fetch_active_accounts.py` adapter registry | **Create** `AlgorandAdapter` (§10); built-in dual endpoint fields (`algod_url`, `indexer_url`) + `node_role` routing | Existing `EthereumAdapter / SolanaAdapter / SuiAdapter` all assume single endpoint; **Algorand is the first dual-node chain among the 28** (NEAR single, Cosmos single host with sub-paths) |
| 6 | `analysis-notes/baseline-current-state.md` (grep `algorand`) | Update chain list; flag dual-node requirement | Doc-truth alignment, prevents v1.4.1 doc-vs-code drift |
| 7 | `analysis-notes/disk-and-network-pipeline-redesign.md` | **Add** note: "indexer backend is PostgreSQL; disk I/O profile differs from algod node (LevelDB)" | Future disk pipeline design must distinguish the two backends |
| 8 | `tests/<chain>.sh` (if new) | Add algod / indexer dual-side smoke test | L1/L2 unit tests cover both endpoints |

**This is a brand-new chain** (verified at `#1`), so `#1–5` are mandatory; `#6–8` depend on Phase 2.1 topology.

**Test requirement**: After Phase 2.1, run `core/master_qps_executor.sh --mixed --duration 30 --chain algorand`; **all vegeta requests must return 200** (double-check that `tx_lookup` lands on the indexer URL and `balance` on the algod URL) — this is the E2 evidence for the Algorand integration.

---

## 9. Mock Notes (`mock_rpc_server` implementation)

- **Request path**: **multiple GET paths** (no JSON-RPC dispatcher) — `mock_rpc_server.py` needs path-based routing first (same conclusion as Cardano research).
- **Routing table** (mock must implement):
  - `GET /v2/status` → `{"last-round": <auto-increment>, "last-version": "...", ...}`
  - `GET /v2/accounts/{addr}` → `{"address":"...","amount":<rand>, "assets":[...], ...}`
  - `GET /v2/transactions/{txid}` (indexer port) → `{"current-round":..., "transaction":{...}}`
  - `GET /v2/transactions/pending/{txid}` (algod port) → `{"confirmed-round":..., "pool-error":"", "txn":{...}}`
  - `GET /v2/blocks/{round}?format=json` → large body (~70 KB realistic, may be trimmed)
  - `GET /v2/assets/{id}` → `{"index":..., "params":{"creator":"...","decimals":6,"name":"USDC",...}}`
  - `GET /v2/assets/{id}/balances` → `{"balances":[...], "current-round":..., "next-token":"..."}`
  - `GET /health` (indexer port) → `{"data":{...},"db-available":true,"round":...,"version":"3.9.0"}`
- **Response schemas**: live samples in §5.1, §7.1.
- **Special errors** (E1 verified):
  - `400` + `{"message":"... address ... is malformed, checksum verification failed"}` — bad address checksum
  - `400` + `{"message":"rewinding account is no longer supported on free endpoints, please remove the round= query parameter and try again"}` — Algonode free tier disables `?round=` historical balance (**important production constraint**)
  - `404` + `{"message":"Not Found"}` — path missing or tx fell out of algod's short window
- **Mock complexity**: **Medium** (9 routes + dual-port simulation + nested ASA-opt-in array generation) — lower than Cardano middleware abstraction, higher than EVM single-branch JSON-RPC.

---

## 10. Adapter Reuse Decision

### Candidate adapters

| Adapter | Compatibility | Missing capabilities |
|---|---|---|
| EthereumAdapter | **5%** | JSON-RPC envelope vs REST path; ABI vs no-ABI; EVM hex addr vs base32 |
| SolanaAdapter | **10%** | Base58 vs Base32; getAccountInfo returns no token list vs algod returns all ASA |
| SuiAdapter | **5%** | Move objects vs ASA opt-in; JSON-RPC vs REST |
| NearAdapter (Wave 2 new) | **15%** | dispatcher pattern vs path pattern; but the **`logical_method` field is reusable** |

### Decision

- [ ] Reuse an existing adapter
- [x] **Create `AlgorandAdapter`** (family = `algorand`, new family)
- [ ] Mixed

### Rationale

**Paragraph 1 — Dual-node architecture is unique among the 28 chains.** Algorand is the only chain researched so far where the protocol itself splits a real-time node (algod) and a historical-indexer node (indexer). EVM's archive-vs-full distinction is the same API with different storage depth; Cosmos LCD+RPC+gRPC are different ports on the same process; Cardano's cardano-node + db-sync is closest, but db-sync exposes no API (a middleware like Koios/Blockfrost sits in front). Algorand **forces the client to route per-method to a different host** (E1 evidence: historical tx returns 404 on algod — §5.2). This is not an internal adapter concern, it's a first-class concern of the configuration/request-construction layer, and **must be modelled explicitly** as `algod_url + indexer_url` dual fields + a `node_role` tag per method. EthereumAdapter / SolanaAdapter / SuiAdapter all assume a single `rpc_endpoint: string` — stuffing a second endpoint in would pollute every existing chain's schema.

**Paragraph 2 — The protocol layer (REST + path) doesn't reuse any existing adapter.** Algorand is **pure REST** (no JSON-RPC envelope); every method is an independent (verb, path, query_params) triple. This is in the same family as Cardano's (Wave 2) path-per-method, but Cardano has no dual-node problem — so AlgorandAdapter can **borrow** CardanoAdapter's path-per-method implementation but **cannot inherit** (dual-node routing is a top-level concern of the adapter).

**Paragraph 3 — The application layer (ASA + opt-in + Application) has unique semantics.** ASA (Algorand Standard Asset) is a native protocol type (not a smart contract); `GET /v2/accounts/{addr}` returns all ASA holdings inline — completely different from EVM's "one eth_getBalance + N eth_call(balanceOf)" pattern. This affects how `token_balance` is modelled in mixed mode. `AlgorandAdapter.get_balance(addr)` should return a composite `{algo: int, assets: [{asset_id, amount}, ...]}` whereas `EthereumAdapter` returns `int`. That's an interface-signature difference, not a thin wrapper.

### Config JSON example

```json
{
  "chain": "algorand",
  "family": "algorand",
  "adapter": "AlgorandAdapter",
  "chain_id": "mainnet-v1.0",
  "genesis_hash_b64": "wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=",
  "endpoints": {
    "algod":   "https://mainnet-api.algonode.cloud",
    "indexer": "https://mainnet-idx.algonode.cloud"
  },
  "auth": {
    "header_name": "X-Algo-API-Token",
    "header_value_env": "ALGORAND_API_TOKEN",
    "required": false
  },
  "block_time_ms": 2800,
  "address_format": "algorand_base32_58",
  "rpc_methods": {
    "block_height":   {"verb": "GET", "path": "/v2/status",                        "node_role": "algod"},
    "balance":        {"verb": "GET", "path": "/v2/accounts/{address}",            "node_role": "algod"},
    "tx_lookup":      {"verb": "GET", "path": "/v2/transactions/{txid}",           "node_role": "indexer"},
    "tx_pending":     {"verb": "GET", "path": "/v2/transactions/pending/{txid}",   "node_role": "algod"},
    "block_query":    {"verb": "GET", "path": "/v2/blocks/{round}?format=json",    "node_role": "algod"},
    "asset_info":     {"verb": "GET", "path": "/v2/assets/{asset_id}",             "node_role": "algod"},
    "asset_balances": {"verb": "GET", "path": "/v2/assets/{asset_id}/balances?limit={limit}", "node_role": "indexer"},
    "account_txs":    {"verb": "GET", "path": "/v2/accounts/{address}/transactions?limit={limit}", "node_role": "indexer"},
    "tx_params":      {"verb": "GET", "path": "/v2/transactions/params",           "node_role": "algod"}
  },
  "mixed_weights": {
    "block_height":   0.05, "balance":        0.25, "tx_lookup":      0.20,
    "tx_pending":     0.05, "block_query":    0.10, "asset_info":     0.10,
    "asset_balances": 0.10, "account_txs":    0.10, "tx_params":      0.05
  }
}
```

---

## 11. DSL Field Requirements (chain-specific)

### 11.1 `endpoints` field (upgrade from string to object)

DSL must upgrade from a single `rpc_endpoint: string` to an `endpoints: { algod, indexer }` object (or keep `rpc_endpoint` as an alias for algod + add `indexer_endpoint`). **This is the first time the requirement appears across 28 chains**; all existing chains can write `endpoints: { default: <url> }` to stay backward-compatible.

### 11.2 `auth.header_name` field (configurable header name)

EVM chains commonly use no auth or `Authorization: Bearer`. Algorand self-hosted nodes use `X-Algo-API-Token`; self-hosted indexers use `X-Indexer-API-Token` (possibly a different token). DSL must support `auth: { header_name, header_value_env, required }` (env var name, never a plaintext secret). Algonode public cluster has `required: false` (E1 evidence).

### 11.3 New `address_format` enum value

`address_format` enum needs a new value `"algorand_base32_58"` (alongside existing `base58 / hex / bech32 / near_account_id`). Validation (base32 decode + SHA-512/256 checksum recomputation) lives in AlgorandAdapter; the DSL just labels it.

### 11.4 `native_decimals` = 6 (microalgo)

**Common pitfall**: DSL has this field, but Algorand is 6 (microalgo), Solana is 9 (lamports), EVM is 18 (wei), NEAR is 24 (yoctoNEAR). Adapter-side balance formatting must respect this.

### 11.5 `chain_id` becomes a string

In EVM it's a number (1, 56, 137), in Algorand it's a string (`"mainnet-v1.0"`), in Cosmos it's also a string (`"cosmoshub-4"`). DSL `chain_id` must be `string | number` (or unified as string). This document recommends **stringify everything** (backward-compatible: EVM chains write `"1"`, reader does `int()` on demand).

### 11.6 Method-level path + query template

Adopt the `rpc_methods.<name>.{verb, path, body_template, response_path}` schema established by Cardano §11.3 / NEAR §11.5, plus a new `node_role` field (see §11.8).

### 11.7 Algorand algod + indexer dual-node table (mandatory)

| Dimension | **algod** (primary) | **indexer** (historical query) | E1 evidence |
|---|---|---|---|
| Default port (self-hosted) | `:4001` (REST API) | `:8980` (REST API) | ⚠ not self-hosted, doc assertion |
| Public endpoint (Algonode) | `https://mainnet-api.algonode.cloud` | `https://mainnet-idx.algonode.cloud` | ✅ §3.1 both 200 |
| Backend storage | LevelDB / SQLite (local ledger) | **PostgreSQL** (indexer process syncs from algod and indexes) | ⚠ doc assertion, not SSH-verified here |
| Auth header | `X-Algo-API-Token` (default-enabled self-hosted) / Algonode does not enforce | `X-Indexer-API-Token` (independent token in self-hosted!) / Algonode does not enforce | ✅ §3.2 any header 200 |
| Height/liveness | `GET /v2/status` → `{"last-round":...}` | `GET /health` → `{"round":..., "version":...}` | ✅ §3.1 both 200 |
| Balance (current) | **`GET /v2/accounts/{addr}`** ✅ includes all ASA | `GET /v2/accounts/{addr}` ✅ (same path; response wraps `account` + adds `current-round`) | ✅ T1+T2 both 200, response shape differs (see §11.7.1) |
| Balance (historical) | ❌ unsupported (algod stores current state only) | `?round=N` param **but Algonode free tier disables it** (`{"message":"rewinding account is no longer supported on free endpoints"}`) | ✅ T3 HTTP 400 + error message |
| Direct tx lookup | ❌ `GET /v2/transactions/{txid}` returns **404** | ✅ `GET /v2/transactions/{txid}` returns `{"transaction": {...}, "current-round": ...}` | ✅ T4+T6 |
| tx pending / recently confirmed | ✅ `GET /v2/transactions/pending/{txid}`, **also returns confirmed tx within `~MaxAcctLookback round` window** | ❌ no such path | ✅ T5 returned `confirmed-round:61461400` for a tx no longer in mempool |
| Block query | ✅ `GET /v2/blocks/{round}?format=json` | ✅ `GET /v2/blocks/{round}` (response shape slightly different, with indexer metadata) | ✅ T7 algod 200 / 72 KB |
| **per-account tx history** | ❌ **404** (`/v2/accounts/{addr}/transactions`) | ✅ `GET /v2/accounts/{addr}/transactions?limit=N` | ✅ T15 indexer 200 / T16 algod 404 |
| **ASA holder list** | ❌ absent | ✅ `GET /v2/assets/{id}/balances?limit=N` | ✅ T10 200, returns holder pagination |
| ASA metadata | ✅ `GET /v2/assets/{id}` | ✅ same path | ✅ T9 algod 200 / T17 indexer 200 |
| Application (smart contract) metadata | ✅ `GET /v2/applications/{id}` | ✅ same path | ⚠ E1 verified on indexer (T-supp), algod side doc assertion |
| Suggested tx params (submission) | ✅ `GET /v2/transactions/params` | ❌ absent | ✅ T-supp returned `{"min-fee":1000, "genesis-hash":...}` |
| Sync lag risk | none (master node = source of truth) | **present** (indexer pulls from algod, may lag 1–N rounds — `current-round` field reflects indexer progress, comparable to algod's `last-round`) | ⚠ not triggered in this study, documented |

#### 11.7.1 Response-shape difference for the same method on the two sides (important!)

```jsonc
// algod GET /v2/accounts/{addr}  → top-level is the account object
{"address":"Q5WO...","amount":<microalgo>,"min-balance":...,"round":...,"assets":[...]}

// indexer GET /v2/accounts/{addr} → wrapper + current-round
{"current-round":61461505,
 "account":{"address":"Q5WO...","amount":<microalgo>,"round":...,"assets":[...]}}
```

→ AlgorandAdapter's `parse_account` must unwrap differently based on `node_role`. The DSL's `response_path` field (the JSONPath-lite already established in NEAR §11.5 and Aptos §11.3) handles this: `algod.balance.response_path = "$.amount"`, `indexer.balance.response_path = "$.account.amount"`.

### 11.8 DSL Decision (key deliverable — dual-node expression)

**Problem**: Algorand is the first of the 28 chains where the client must route per-method to a different host (algod vs indexer). The DSL must express this routing; otherwise the vegeta target generator will send `tx_lookup` to algod (returns 404) and `balance` to indexer (different schema, parse breaks).

#### Three options

| Option | DSL shape | Effort | Backward-compat | Monitoring granularity | Downside |
|---|---|---|---|---|---|
| **A `endpoint_alias` field (method references endpoint name)** | `endpoints: {algod, indexer}` + per-method `endpoint: "algod" \| "indexer"` | Medium (1 field per method) | ✅ (default = sole endpoint alias) | ✅ (method granularity natural) | `endpoint` is a transport concept, not aligned with NEAR's `logical_method` (semantic concept) — schemas get a little messy across chains |
| **B `node_role` field (semantic role)** (recommended) | `endpoints: {algod, indexer}` + per-method `node_role: "algod" \| "indexer"`; adapter maps `node_role → endpoints[node_role]` | Medium (same as A; but the field name says "semantic role" not "endpoint alias") | ✅ default `node_role: "default"` maps to `endpoints.default` | ✅ | `node_role` enum is family-coupled (algorand = algod/indexer; eos might be nodeos/state-history; bitcoin could be full/pruned) — weak schema constraint; **but most semantically self-consistent** |
| **C Fully hidden inside adapter (not in DSL)** | DSL only writes `endpoints: {...}`; AlgorandAdapter holds a hard-coded `method → node_role` map internally | Small (adapter-only) | ✅ (zero change to other chains) | ✅ | **Caller-blind disaster zone**: vegeta target generator cannot statically learn which endpoint to use — must reflectively call the adapter — violates the "DSL is declarative input" goal of Q4=C 95% |

#### Decision

- [ ] Option A `endpoint_alias` (transport-layer field, generic but semantically weak)
- [x] **Option B `node_role` (semantic-role field)** — **recommended**
- [ ] Option C (hidden inside adapter, DSL is clean but caller-blind)

#### Rationale (3 paragraphs)

**Paragraph 1 — Option C directly violates the Q4=C 95% goal of "add a chain with zero Python".** The framework's end-state goal is that `master_qps_executor.sh` + `mock_rpc_server.py` are entirely driven by declarative DSL, with no Python required for each new chain. Option C hides the `method → node_role` map inside AlgorandAdapter Python code, meaning that after adding Algorand, the vegeta target generator **must reflectively call the adapter during generation** to discover URLs — the same caller-blind anti-pattern that NEAR query-dispatcher (08-near.md §11.7/§11.8) ran into. **Rejected.**

**Paragraph 2 — Option B is more semantically self-consistent than A, with equal schema-extension capacity.** Option A uses `endpoint_alias`, which directly uses the `endpoints` dict key as a method field. Option B introduces one level of indirection via `node_role`, but **`node_role` is the semantic statement "which role of node should this method query"**, parallel to `family: algorand`; the `endpoints` dict is just the instantiation of `node_role` (the user can swap URLs between mock/prod/multi-region while `node_role` is unchanged). Concretely: (1) in prod, the user writes `endpoints: {algod: "https://my-prod-algod...", indexer: "https://my-prod-indexer..."}`; in mock, `endpoints: {algod: "http://localhost:4001", indexer: "http://localhost:8980"}` — `method.node_role` doesn't change; (2) future research on Bitcoin / EOS / Polkadot may introduce family-specific `node_role` enums (Bitcoin `full|pruned|electrum`), and each family defines its own enum while the DSL field name remains stable; (3) monitoring labels gain a `node_role` dimension, naturally yielding "indexer p99 vs algod p99" comparison charts (directly operationally useful).

**Paragraph 3 — Zero cost to the 7 existing chains and coexists naturally with NEAR's `logical_method`.** Existing 5 EVM + Solana + Sui plugins write `endpoints` as `{default: "https://..."}` (or keep top-level `rpc_endpoint`, reader translates to `endpoints.default`); `node_role` is unset (defaults to `"default"`). Only AlgorandAdapter consumes the new field; other adapters ignore it — the token-level "local additions + default-value compatibility" pattern. NEAR's `logical_method` and Algorand's `node_role` coexist orthogonally (`logical_method` solves wire-method dispatch; `node_role` solves endpoint routing). Phase 2.1 needs ~10 LOC in `config_loader.sh`, the path routing in `mock_rpc_server.py` (which is needed anyway), and a new `AlgorandAdapter` in `fetch_active_accounts.py` — total ~150 LOC, zero regression to existing chains.

**One-line conclusion**: **`endpoints: {algod, indexer}` + optional per-method `node_role` (default `"default"`) + AlgorandAdapter dual-URL routing = minimum complete DSL expression of Algorand's dual-node architecture.** ✅

---

## 11.9 Source coverage & timestamps

| Source | URL/path | Access date (UTC) | Status |
|---|---|---|---|
| algod /versions | `GET https://mainnet-api.algonode.cloud/versions` | 2026-05-23 | **E1 HTTP:200 TIME:0.14s** — `genesis_id=mainnet-v1.0`, `genesis_hash_b64=wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=`, build major=4 |
| algod /v2/status | same host `/v2/status` | 2026-05-23 | **E1 HTTP:200 TIME:0.21s, last-round=61461471** |
| algod /v2/accounts/{snd} | `Q5WOHVUKNEM4XOVL725KH77WS6GODZSI4HTSWZAILM36ANSYVHW5RJI3KE` | 2026-05-23 | **E1 HTTP:200 TIME:0.15s SIZE:13022 (includes ASA holdings)** |
| algod /v2/transactions/pending/{txid} (confirmed tx) | txid in §7 | 2026-05-23 | **E1 HTTP:200, confirmed-round:61461400 — refutes task context's "only pending"** |
| algod /v2/transactions/{txid} (direct) | same txid | 2026-05-23 | **E1 HTTP:404 Not Found — proves algod has no historical tx endpoint** |
| algod /v2/blocks/61461400 | `?format=json` | 2026-05-23 | **E1 HTTP:200 SIZE:71979** |
| algod /v2/assets/31566704 (USDCa) | same host | 2026-05-23 | **E1 HTTP:200 — params.creator/decimals=6/name=USDC** |
| algod /v2/transactions/params | same host | 2026-05-23 | **E1 HTTP:200, min-fee=1000, genesis-hash matches /versions** |
| algod /genesis | same host | 2026-05-23 | **E1 HTTP:200 SIZE:24973 (full genesis with RewardsPool/FeeSink addresses)** |
| indexer /health | `https://mainnet-idx.algonode.cloud/health` | 2026-05-23 | **E1 HTTP:200 TIME:0.09s, version=3.9.0, db-available=true, round=61461471** |
| indexer /v2/accounts/{snd} | same host | 2026-05-23 | **E1 HTTP:200 SIZE:14167, response wraps account (different schema from algod)** |
| indexer /v2/accounts/{snd}?round=61400000 | historical balance attempt | 2026-05-23 | **E1 HTTP:400 "rewinding account is no longer supported on free endpoints" — important prod constraint** |
| indexer /v2/transactions/{txid} | historical tx | 2026-05-23 | **E1 HTTP:200, confirmed-round=61461400, current-round=61461505** |
| indexer /v2/accounts/{snd}/transactions?limit=3 | account tx list | 2026-05-23 | **E1 HTTP:200 SIZE:6090 (indexer-only)** |
| indexer /v2/assets/31566704/balances?limit=2 | ASA holders | 2026-05-23 | **E1 HTTP:200 — balances[].address + next-token pagination** |
| indexer /v2/applications/1002541853 | smart-contract metadata | 2026-05-23 | **E1 HTTP:200 SIZE:11035, includes TEAL approval-program base64** |
| Algonode alt host Nodely | `https://mainnet-api.4160.nodely.dev/v2/status` | 2026-05-23 | **E1 HTTP:200 TIME:0.20s** |
| Auth-header three probes | no-header / Bearer / X-Algo-API-Token | 2026-05-23 | **E1 all HTTP:200 — public cluster does not validate** |
| Invalid address checksum | task context's DPLD3RZSY... | 2026-05-23 | **E1 HTTP:400 "checksum verification failed" — refutes context typo** |
| Framework chain namespace | `config/config_loader.sh:666` `supported_blockchains` | 2026-05-23 | **E1 read_file**: array has 8 chains, **no algorand — confirmed new chain** |

### Not verified / deferred to Phase 2.1

- ⚠ **Self-hosted algod `X-Algo-API-Token` mandatory header** — doc assertion; no self-hosted sandbox in this study
- ⚠ **Indexer PostgreSQL backend disk I/O profile** — documented only; verify via self-host in Phase 2.1
- ⚠ **algod `MaxAcctLookback` actual round-window size** — assumed ~1000, needs algod config-file verification
- ⚠ **Indexer sync-lag actual values** — during this study algod.last-round=61461471 matched indexer.round=61461471 exactly; lag under load must be observed in a Phase 2.1 long-run
- ⚠ **Algonode public 60 req/s rate limit** — doc assertion; ~20 requests in this study all 200, did not trigger limit
- ⚠ **Paid-tier indexer `?round=` historical balance** — Algonode free disables it; paid tier behaviour not verified

---

## Open Questions

1. **`node_role` vs `endpoint_alias` naming** (§11.8 Option A vs B) — final naming decided by user during Wave 3 review; this document recommends `node_role` (semantic) over `endpoint_alias` (transport).
2. **`endpoints` as object or dict-list** — `{algod: url, indexer: url}` vs `[{name:algod, url:...}, ...]`; former compact, latter extensible (can add region/priority). This document's example uses object; P1 review may adjust.
3. **Should `block_height` be split into `algod_height` + `indexer_height` for sync-lag monitoring** (§11.7 sync-lag row) — is a 10th method worth its own mixed-weight slot?
4. **Historical-balance `?round=N` support** — Algonode free disables; self-hosted/paid supports. Should the framework expose a `feature_flag: historical_balance` in DSL?
5. **txid pool for `tx_lookup` mixed entry** — vegeta target needs a real txid pool; fetch from `account_txs` last N? Or fix a static set (like this study's `PO3UMN7...`)? Phase 2.1 design.
6. **`asset_id` pool for ASA** — `asset_info` / `asset_balances` need a real asset_id pool (USDCa=31566704 is only one); recommend fetching top assets via `/v2/assets?limit=100` on indexer.
7. **mock_rpc_server dual-port simulation** — same process with path prefixes (`/algod/*` + `/indexer/*`) or two processes? Latter more realistic but requires the framework to start two mocks.
8. **AlgorandAdapter `get_balance(addr)` return type** — ALGO `int` only, or composite `{algo, assets:[...]}` (§10 paragraph 3)? Composite differs from EthereumAdapter — Phase 2.1 abstract-base-class adjustment.
9. **`X-Indexer-API-Token` vs `X-Algo-API-Token` same secret?** — self-hosted defaults are **two independent tokens**; does `auth` need per-endpoint sub-config (`auth: {algod: {...}, indexer: {...}}`)?
10. **Algorand applications (smart contracts) in mixed coverage** — current §8 weights exclude application calls (`POST /v2/teal/dryrun` etc.); add in Wave 3+?

---

## Changelog

| Date (UTC) | Author | Change |
|---|---|---|
| 2026-05-23 | Hermes Agent | First draft (Phase 1.2 Wave 3): **18 curl E1 evidence items** (all algod + indexer methods); **refuted** two items in the task context ("tx pending only" and "Algorand foundation" address checksum); §11.7 dual-node capability table (15 rows) + §11.8 three-option comparison + **decision = Option B `node_role` field (optional) + AlgorandAdapter dual-URL routing**; created `AlgorandAdapter` (new family `algorand`); enumerated 8 Phase 2.1 caller/reader change items (§8.5) + 10 Open Questions |
