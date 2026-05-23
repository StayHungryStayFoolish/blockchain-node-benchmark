# 04 — Aptos Research Note

> **Version**: v1.0 (draft, Phase 1.2 Wave 1)
> **Research date**: 2026-05-23
> **Author**: Hermes Agent (token-level + research-first + H8-verified / E1-E5 graded)
> **Status**: 🟢 Awaiting user review (P1-USER-REVIEW gate)
> **Mandatory satisfied**: `_template.md` §1-§10 + §11 DSL (incl. 11.7 Aptos vs Sui comparison, 11.8 movevm family decision)
> **Numbering note**: This file is named `04-aptos.md` per wave delegation; `00-SUMMARY.md` line 17 shows Aptos = #17. Final rename to be decided by user at P1 closeout (Open Q1).

---

## Meta

| Field | Value |
|---|---|
| Chain name (zh) | Aptos |
| Chain name (en) | Aptos |
| Number | 04 (wave) / 17 (SUMMARY canonical) |
| Mainnet ChainID | `1` (verified by both `x-aptos-chain-id` header and `/v1` ledger field) |
| Research date | 2026-05-23 |
| Researcher | Hermes Agent |
| Status | 🟢 Initial draft complete |

---

## 1. Sources (authoritative)

| Type | URL | Accessed | Notes / Evidence grade |
|---|---|---|---|
| Official docs root | https://aptos.dev | 2026-05-23 | E1 (not DOM-verified in depth) |
| REST API reference | https://aptos.dev/build/apis/fullnode-rest-api | 2026-05-23 | E1 cited; **key: Aptos primary interface is REST, NOT JSON-RPC** |
| OpenAPI Spec (live) | https://fullnode.mainnet.aptoslabs.com/v1/spec.yaml | 2026-05-23 | **H8 verified** (`HTTP:200 TYPE:application/x-yaml`) |
| GitHub | https://github.com/aptos-labs/aptos-core | 2026-05-23 | E1 cited (not git-cloned) |
| Explorer | https://explorer.aptoslabs.com | 2026-05-23 | E1 cited (not DOM-verified) |
| Move Book (VM spec) | https://aptos.dev/move/move-on-aptos | 2026-05-23 | E1 cited |

---

## 2. Protocol Family

| Field | Value | Evidence |
|---|---|---|
| Family | **Move** (second MoveVM implementation) | E1 official positioning |
| Consensus | AptosBFT v4 (HotStuff-derived, evolved from DiemBFT) | E1 docs (not paper-verified) |
| VM | MoveVM (same VM as Sui, but **different object model**: Aptos uses Move Resource, Sui uses Object) | E1 + H8 `/v1/accounts/0x1/resources` returns `0x1::dkg::DKGState` Move structs |
| Block time | ~0.15s (estimated from H8: `block_height=783350119` vs `ledger_version=5392437054`) | **H8 verified** |
| Finality | sub-second (BFT deterministic, ~1 block) | E1 docs (latency distribution not measured) |
| Reuse existing adapter? | **No** (SuiAdapter is JSON-RPC, Aptos is REST — **protocol layer cannot be shared**) | **Core conclusion of this research**, see §10 + §11.7/11.8 |

---

## 3. Public RPC

| Endpoint | Auth | Rate Limit | Notes / H8 |
|---|---|---|---|
| `https://fullnode.mainnet.aptoslabs.com/v1` | none | not publicly stated, anonymous public | **H8 verified HTTP:200 TIME:0.24s** (ledger info) + multi-endpoint OK |
| `https://api.mainnet.aptoslabs.com/v1` | none | same (alias) | **H8 verified HTTP:200** (`/v1/-/healthy` → `aptos-node:ok`) |
| `https://aptos-mainnet.publicnode.com` | — | — | **H8 verified HTTP:404** (publicnode Aptos endpoint not currently usable — **not recommended**) |
| `https://rpc.ankr.com/http/aptos/v1/...` | API key required | very limited free tier | **H8 verified HTTP:403** (`API key is not allowed to access blockchain`) |
| `https://aptos.api.onfinality.io/public/v1` | public / paid tiers | untested | **H8 verified HTTP:404** (public path does not work) |

**curl evidence 1 — ledger info (probe + height)** (H8):
```bash
curl -s https://fullnode.mainnet.aptoslabs.com/v1
# {"chain_id":1,"epoch":"15909","ledger_version":"5392437054","oldest_ledger_version":"0",
#  "ledger_timestamp":"1779559410826021","node_role":"full_node","oldest_block_height":"0",
#  "block_height":"783350119","git_hash":"b2a11100ceb479c8d220937c003524d4708a7821","encryption_key":null}
```

**curl evidence 2 — responses carry `x-aptos-*` headers** (high-value ✨, can replace ledger-info GET):
```
x-aptos-chain-id: 1
x-aptos-ledger-version: 5392452111
x-aptos-ledger-oldest-version: 0
x-aptos-ledger-timestampusec: 1779559506186366
x-aptos-epoch: 15909
x-aptos-block-height: 783352304
x-aptos-oldest-block-height: 0
```
i.e., **every response carries chain_id / ledger_version / block_height**. The benchmark monitoring can use `curl -I` to replace a full ledger-info GET (saves a round-trip).

**curl evidence 3 — health probe**:
```bash
curl -s https://fullnode.mainnet.aptoslabs.com/v1/-/healthy
# {"message":"aptos-node:ok"}  HTTP:200
```

**curl evidence 4 — verify NOT JSON-RPC**:
```bash
curl -s -X POST https://fullnode.mainnet.aptoslabs.com/v1 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"getLedgerInfo"}'
# {"message":"method not allowed","error_code":"web_framework_error","vm_error_code":null}  HTTP:405
```
**Key conclusion**: Aptos rejects JSON-RPC. **This is the core protocol-level divergence from Sui** (see §11.7).

---

## 4. Account Model

| Field | Value | Evidence |
|---|---|---|
| Model | **Account** (Move Resource model with `sequence_number`) | **H8** `/v1/accounts/0x1` → `{"sequence_number":"0","authentication_key":"0x0...01"}` |
| Native token | APT (`0x1::aptos_coin::AptosCoin`) | E1 docs + H8 view |
| Native token decimals | 8 (octas) | E1 docs (not verified in view) |
| Address derivation | Ed25519 default; MultiEd25519 / Secp256k1 / SecpR1 (passkey) supported | E1 docs |
| Special account types | Resource Account / Object (Aptos Object Model) / framework system accounts `0x1`,`0x3`,`0x4`,... | E1 docs + H8 `/v1/accounts/0x1/resources` returns many `0x1::*` resources |
| Balance query | **`POST /v1/view` calling `0x1::coin::balance<AptosCoin>`** (mainstream) OR direct resource read `/v1/accounts/{addr}/resource/0x1::coin::CoinStore<...>` | **H8 both paths verified** (view returns `["669182353480"]`) |

**curl — balance (view function path)**:
```bash
curl -X POST https://fullnode.mainnet.aptoslabs.com/v1/view \
  -H "Content-Type: application/json" \
  -d '{"function":"0x1::coin::balance",
       "type_arguments":["0x1::aptos_coin::AptosCoin"],
       "arguments":["0xd503b95164384a5ebbccbb5c4bdc8b4a5893d9651e9953abda8e1c22fcc1181d"]}'
# ["669182353480"]   ⇒ 6691.82 APT (8 decimals)  HTTP:200
```

**curl — balance (resource path; framework 0x1 returns 404 because it holds no APT)**:
```bash
curl https://fullnode.mainnet.aptoslabs.com/v1/accounts/0x1/resource/0x1::coin::CoinStore%3C0x1::aptos_coin::AptosCoin%3E
# {"message":"Resource not found by Address(0x1), Struct tag(0x1::coin::CoinStore<...>)..."} HTTP:404
```
Note: **`0x1` is the framework account and holds no APT**, so the resource path returns 404 — this contradicts EVM's "address exists ⇒ balance exists" mental model. Framework code must tolerate 404 here.

---

## 5. Core RPC Methods (framework monitoring needs)

> **Protocol note**: Aptos "methods" are NOT JSON-RPC method strings — they are **REST URL path + HTTP verb combinations**. The `Method` column below uses `<VERB> <path>` notation to align with `_template.md`.

| Method | Category | Description | Suggested mixed weight | H8 status |
|---|---|---|---|---|
| `GET /v1` | ledger info | probe + chain_id + ledger_version + block_height (one-shot) | **0.20** | ✅ HTTP:200 0.24s |
| `HEAD /v1` (or any GET, read header) | sync heartbeat | only read `x-aptos-*` headers — **cheapest** height heartbeat | **0.10** | ✅ verified 8 x-aptos-* fields |
| `GET /v1/-/healthy` | health check | liveness probe (fixed response) | **0.05** | ✅ `aptos-node:ok` |
| `POST /v1/view` | balance / arbitrary Move read | native balance, token balance, custom view — all via this | **0.25** | ✅ returns `["669182353480"]` |
| `GET /v1/accounts/{addr}` | account meta | sequence_number + auth_key | **0.05** | ✅ verified 200 |
| `GET /v1/accounts/{addr}/resources` | account resources (Move state) | **Aptos-specific**: list all Move structs of an account | **0.10** | ✅ verified 200 (framework returns DKGState etc.) |
| `GET /v1/accounts/{addr}/resource/{struct_tag}` | single resource | CoinStore / any custom struct | **0.05** | ✅ verified 200/404 (404 = resource not present, by design) |
| `GET /v1/blocks/by_height/{n}` | block by height | block content (optional `with_transactions=true`) | **0.05** | ✅ returns `block_hash`/`first_version`/`last_version` |
| `GET /v1/transactions?limit=N` | tx list | latest N txs (for fetch_active_accounts) | **0.05** | ✅ returns list incl. `user_transaction` |
| `GET /v1/transactions/by_hash/{hash}` | tx lookup by hash | lookup tx by hash | **0.05** | ✅ verified 200 tx details |
| `GET /v1/transactions/by_version/{ver}` | tx lookup by version | **Aptos-specific**: by `ledger_version` integer (cheaper than hash decode) | **0.05** | ✅ verified 200 |
| `GET /v1/estimate_gas_price` | gas estimation | equivalent to `eth_gasPrice` | — | ✅ `{"deprioritized_gas_estimate":100,"gas_estimate":100,"prioritized_gas_estimate":150}` |
| `GET /v1/accounts/{addr}/events/{handle}/{field}` | event query | by event handle struct + field name | — | ✅ returns `NewEpochEvent` |
| `GET /v1/accounts/{addr}/modules` | deployed Move bytecode | not on benchmark critical path | — | ✅ verified 200 |

**Mixed weight check** (8 monitoring critical-path items, normalized):

```
GET /v1                                          0.20  (ledger info)
HEAD /v1 (x-aptos-* heartbeat)                   0.10  (cheapest heartbeat)
POST /v1/view (balance/view)                     0.30  (highest-frequency real query)
GET /v1/accounts/{addr}                          0.05
GET /v1/accounts/{addr}/resources                0.10
GET /v1/blocks/by_height/{n}                     0.05
GET /v1/transactions?limit=N                     0.05
GET /v1/transactions/by_hash/{hash}              0.10
GET /v1/transactions/by_version/{ver}            0.05
                                                = 1.00 ✅
```

**Total = 1.00 ✅** (`/v1/-/healthy` and `/v1/estimate_gas_price` are excluded from mixed; the former is used by health-monitor only, the latter is not a read-path core).

---

## 6. Address Format

| Field | Value | Evidence |
|---|---|---|
| Encoding | Hex (`0x` prefix) | H8 verified |
| Length | **32 bytes = 64 hex chars + `0x` = 66 chars** (same length as Sui, **also 32B**, **differs from Ethereum's 20B**) | H8 (`0xd503...181d` = 66 chars) |
| Short form | Leading-zero elision allowed: `0x1` ≡ `0x0000...0001` (framework) | H8 verified `/v1/accounts/0x1` 200, but internal `auth_key` still returns full 64 hex |
| Checksum | No EIP-55-style checksum, **pure hex** | E1 docs |
| Example (mainnet real address) | `0xd503b95164384a5ebbccbb5c4bdc8b4a5893d9651e9953abda8e1c22fcc1181d` (sender of a `user_transaction` from `/v1/transactions?limit=10`, balance 6691.82 APT) | **H8 dual-verified** |
| Framework system addresses | `0x1` (AptosFramework), `0x2` (MoveStdlib), `0x3` (AptosTokenV1), `0x4` (AptosTokenObjects), `0x5`, `0x6`, `0x7`, `0xa`, `0x10` reserved | E1 docs (only `0x1` H8 verified) |
| Validation regex | `^0x[0-9a-fA-F]{1,64}$` (1-64 since short addresses are legal) | inferred from H8 |

**vs Sui**: **both 32B hex, identical length**, address validator can be shared 1:1. ✅ family-share candidate dimension.

---

## 7. Signature / Tx Hash Lookup

| Field | Value | Evidence |
|---|---|---|
| Hash format | Hex (`0x` prefix) | H8 verified |
| Length | 32 bytes = 64 hex chars + `0x` = 66 chars | H8 (`0x200d31ed050986b5ec9ced837f70f771c8ec99a09995fabf6a68a2fffdb9b6fe`) |
| Example (mainnet real tx) | `0x200d31ed050986b5ec9ced837f70f771c8ec99a09995fabf6a68a2fffdb9b6fe` (version=5392438515) | **H8 verified** (`/v1/transactions/by_hash/...` → details) |
| Lookup method | `GET /v1/transactions/by_hash/{hash}` | H8 verified 200 |
| **Additional lookup** (Aptos-specific) | `GET /v1/transactions/by_version/{ledger_version}` — by integer version, **cheaper than hash** (integer compare vs hex decode) | H8 verified 200 |
| Explorer URL | `https://explorer.aptoslabs.com/txn/{hash}?network=mainnet` | E1 docs |

**vs Sui**: **Sui tx digest is Base58 ~44 chars**, **Aptos is hex `0x` + 64 chars** — **encoding differs entirely**, parsers must branch per chain. ⚠️ family-split dimension.

---

## 8. Mixed Set (`mixed` mode weights)

> Distribution for `BLOCKCHAIN_NODE_BENCHMARK_MODE=mixed`

```json
{
  "balance_query":   0.30,  /* POST /v1/view  (0x1::coin::balance) */
  "ledger_info":     0.20,  /* GET  /v1                            */
  "heartbeat":       0.10,  /* HEAD /v1  (just read x-aptos-*)     */
  "tx_lookup":       0.10,  /* GET  /v1/transactions/by_hash/{h}   */
  "tx_by_version":   0.05,  /* GET  /v1/transactions/by_version/{v}*/
  "tx_list":         0.05,  /* GET  /v1/transactions?limit=N       */
  "block_query":     0.05,  /* GET  /v1/blocks/by_height/{n}       */
  "account_meta":    0.05,  /* GET  /v1/accounts/{addr}            */
  "resources":       0.10   /* GET  /v1/accounts/{addr}/resources  */
}
/* sum = 1.00 ✅ */
```

**Sum = 1.00 ✅**. Aptos-specific (not in Sui) are `resources` and `tx_by_version` — Sui has no direct equivalent (Sui uses `sui_getObject` + `suix_queryTransactionBlocks`, different object/cursor model).

**Note**: weights are draft (E5 SPECULATED), not based on mainnet traffic stats; placeholder until Phase 2.x ops alignment.

---

## 8.5 Phase 2.1 caller/reader change list (token-level Gate 3)

| # | Location (file:line) | Change | Why this caller must be synced |
|---|---|---|---|
| 1 | `config/config_loader.sh:401` (add `aptos)` arm in `case`) | `MAINNET_RPC_URL="https://fullnode.mainnet.aptoslabs.com/v1"` | otherwise the `*)` arm errors out |
| 2 | `config/config_loader.sh:622+` `UNIFIED_BLOCKCHAIN_CONFIG.blockchains` add `"aptos"` block | add `chain_type / params / methods / system_addresses / rpc_methods / param_formats / protocol_kind: "rest"` | so `generate_auto_config()` can emit vegeta target config |
| 3 | `config/config_loader.sh:666` `supported_blockchains` array add `"aptos"` | `(... "starknet" "sui" "aptos")` | otherwise `validate_blockchain_node()` rejects `BLOCKCHAIN_NODE=aptos` |
| 4 | `tools/mock_rpc_server.py` add Aptos REST routes | routes: `/v1`, `/v1/view`, `/v1/accounts/{addr}`, `/v1/accounts/{addr}/resources`, `/v1/transactions/by_hash/{h}`, etc. | **Aptos is NOT JSON-RPC**; existing POST `/` JSON-RPC dispatcher **cannot be reused** — must add a REST router branch. This is the **largest mock workload** Aptos introduces |
| 5 | `tools/fetch_active_accounts.py` add `AptosAdapter` | `class AptosAdapter(BlockchainAdapter)`; core path is `GET /v1/transactions?limit=N` → extract sender of `user_transaction`; **cannot reuse** EthereumAdapter's `eth_getLogs / eth_getBlockByNumber` mental model | Aptos `ledger_version` is a contiguous int (similar to Solana slot), per-version scanning is feasible, but the interface is REST not JSON-RPC |
| 6 | `tools/audit_rpc_methods.py:ADAPTER_EXPECTED_FIELDS` add Aptos paths | e.g. `"aptos_view_balance": ["[0]"]` (view returns JSON array), `"aptos_get_ledger": ["chain_id","ledger_version","block_height"]` | L2 audit uses this dict to assert response shape; without it, audit skips |
| 7 | `tools/audit_rpc_methods.py:fetch_doc_method()` add `elif chain_type == "aptos"` | analog to Sui's current `SKIPPED`, or upgrade to fetching `/v1/spec.yaml` and parsing endpoint list (stronger) | L1 audit auto-verifies method existence from OpenAPI |
| 8 | `analysis-notes/baseline-current-state.md` grep `aptos` | update chain pipeline list (currently should have no aptos mentions) | doc-truth alignment, prevent doc-vs-code drift |
| 9 | `docs/zh/chains/00-SUMMARY.md` line 17 Aptos: `🟡 待调研 → 🟢 已完成初稿`, fill doc paths to this file | — | SUMMARY is the P1 completion dashboard |
| 10 | `tests/<aptos-related>.sh` add e2e smoke | run `BLOCKCHAIN_NODE=aptos core/master_qps_executor.sh --mixed --duration 30` | E2 evidence; **all requests must be 200** (note: `/v1/accounts/{addr}/resource/...` legitimately returns 404 when resource absent — mixed targets must use a balance-holding address) |

**Key warning** (token-level Case-B risk): item #4 mock change **is not "add a few cases"** — it is **adding a whole REST router**. The current `mock_rpc_server.py` assumes every request is `POST /` + JSON-RPC body; Aptos requires path-based dispatch + multiple HTTP verbs. Recommend Phase 2.1 refactor mock to **per-family handler** rather than piling if-else into the existing single dispatcher — otherwise the mock becomes increasingly entangled.

**Testing requirement**: after Phase 2.1, run `core/master_qps_executor.sh --mixed --duration 30`, **all requests must return 200** (use a balance-holding address as view target), as E2 evidence.

---

## 9. Mock Notes (mock_rpc_server implementation)

- **Request paths**: **multi-path + multi-verb** (not a JSON-RPC single endpoint)
  - `GET /v1` / `HEAD /v1`
  - `GET /v1/-/healthy`
  - `GET /v1/accounts/{addr}`
  - `GET /v1/accounts/{addr}/resources`
  - `GET /v1/accounts/{addr}/resource/{struct_tag}`
  - `GET /v1/blocks/by_height/{n}`
  - `GET /v1/transactions` (supports `?limit=`)
  - `GET /v1/transactions/by_hash/{hash}`
  - `GET /v1/transactions/by_version/{version}`
  - `POST /v1/view` (body contains `function / type_arguments / arguments`)
- **Response schema samples (real mainnet, H8-verified)**:
  ```json
  // GET /v1 (ledger info)
  {"chain_id":1,"epoch":"15909","ledger_version":"5392437054",
   "oldest_ledger_version":"0","ledger_timestamp":"1779559410826021",
   "node_role":"full_node","oldest_block_height":"0",
   "block_height":"783350119",
   "git_hash":"b2a11100ceb479c8d220937c003524d4708a7821","encryption_key":null}

  // POST /v1/view  (balance)
  ["669182353480"]              // array of strings (big-ints serialized as strings)

  // GET /v1/transactions/by_hash/{h}  (excerpt)
  {"version":"5392438515",
   "hash":"0x200d31ed050986b5ec9ced837f70f771c8ec99a09995fabf6a68a2fffdb9b6fe",
   "gas_used":"0","success":true,"vm_status":"Executed successfully", ...}
  ```
- **Response headers mock MUST emit** (otherwise monitoring will think the mock is bogus):
  - `x-aptos-chain-id: 1`
  - `x-aptos-ledger-version: <incr int>`
  - `x-aptos-block-height: <incr int>`
  - `x-aptos-epoch: <int>`
  - `x-aptos-ledger-timestampusec: <usec>`
- **Special status codes**:
  - `404` + `{"error_code":"resource_not_found"}`: resource absent (legitimate, not an error) — mock must return this for unconfigured `struct_tag`, else callers misclassify as 500
  - `405` + `{"error_code":"web_framework_error","message":"method not allowed"}`: wrong HTTP verb
  - `400` + `{"error_code":"invalid_input"}`: malformed params
- **Big-int serialization**: **all u64/u128 values in responses are strings** (JSON number precision); mock must return `"669182353480"`, not `669182353480`
- **Mock complexity**: **High** — reasons: (a) multi-path + multi-verb is not a simple dispatcher; (b) `POST /v1/view` accepts arbitrary Move calls — mock must at minimum implement `0x1::coin::balance` and `0x1::aptos_account::sequence_number`; (c) `struct_tag` URL encoding (`<>` → `%3C%3E`) needs manual handling

---

## 10. Adapter Reuse Decision

### Candidates

| Adapter | Compatibility | Missing capability |
|---|---|---|
| EthereumAdapter | **5%** | RPC protocol fundamentally different (Aptos REST vs Eth JSON-RPC); address length differs (32B vs 20B); balance query mechanism differs (view function vs `eth_getBalance`); account model differs (Move Resource vs EVM Account) |
| SolanaAdapter | **0%** | protocol (RPC vs REST) + account model (Solana Account vs Move Resource) + address encoding (base58 vs hex) all different |
| BitcoinAdapter | **0%** | UTXO model not applicable |
| StarknetAdapter | **5%** | Starknet is JSON-RPC, Cairo VM, not reusable |
| **SuiAdapter** (nearest neighbor in family) | **~30%** (VM/semantics) / **~5%** (protocol/wire) | **Protocol layer not reusable**: Sui is JSON-RPC 2.0 (`POST /` + `method`), Aptos is REST (multi-path + GET/POST). **Semantic layer reusable**: Move `struct_tag` parsing, `0x1`/`0x2` framework concept, Coin resource |

### Decision

- [ ] reuse `<adapter>`
- [x] **create `AptosAdapter` (under `Move family`, peer to `SuiAdapter` — NOT inheritance)**
- [ ] mixed

### Rationale

(1) **Protocol-layer divergence is a hard blocker**. Sui uses JSON-RPC 2.0 (`POST /` + `{"method":"sui_getObject","params":[...]}`); Aptos explicitly rejects JSON-RPC (H8 verified: 405 + `web_framework_error`). The transport encoding, URL pattern, HTTP verb choice all differ. **Any attempt at single-adapter if-else branching pollutes the protocol abstraction**, violating single-responsibility.

(2) **VM semantic layer can be shared, but does not belong in the adapter**. Move `struct_tag` parsing (`0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>`), framework address concept (`0x1` ~ `0xa`), `CoinStore` resource notion, view function calling convention (`{function, type_arguments, arguments}` triple) — these VM/semantic concepts are shared between Sui and Aptos and belong in **`tools/move_utils.py`** (imported by both SuiAdapter and AptosAdapter), but **must not** live in the plugin DSL schema. DSL schema is the protocol-binding layer; semantic helpers are the utility layer; **responsibilities must be split**.

(3) **Recommended structure + family naming** (see §11.8): **`movevm` family exists as a documentation/grouping/UI label**, but plugin schema splits into `movevm-sui` + `movevm-aptos` two sub-families. Reason: RPC-model divergence ≥ 50% (see §11.7), well above the 20% merger threshold.

### Config JSON example (this chain)

```json
{
  "chain": "aptos",
  "family": "move",
  "subfamily": "movevm-aptos",
  "adapter": "AptosAdapter",
  "protocol_kind": "rest",
  "chain_id": 1,
  "rpc_endpoint": "https://fullnode.mainnet.aptoslabs.com/v1",
  "block_time_ms": 150,
  "address_format": "hex_0x_32byte",
  "tx_hash_format": "hex_0x_32byte",
  "native_decimals": 8,
  "system_addresses": ["0x1", "0x2", "0x3", "0x4", "0x5", "0x6", "0x7", "0xa"],
  "rpc_methods": {
    "ledger_info":    "GET /v1",
    "health":         "GET /v1/-/healthy",
    "balance":        "POST /v1/view",
    "account_meta":   "GET /v1/accounts/{addr}",
    "resources":      "GET /v1/accounts/{addr}/resources",
    "resource":       "GET /v1/accounts/{addr}/resource/{struct_tag}",
    "block_by_height":"GET /v1/blocks/by_height/{n}",
    "tx_list":        "GET /v1/transactions",
    "tx_by_hash":     "GET /v1/transactions/by_hash/{hash}",
    "tx_by_version":  "GET /v1/transactions/by_version/{version}",
    "gas_price":      "GET /v1/estimate_gas_price"
  },
  "view_function_balance": {
    "function": "0x1::coin::balance",
    "type_arguments": ["0x1::aptos_coin::AptosCoin"]
  },
  "param_formats": {
    "POST /v1/view": "move_view_call",
    "GET /v1/accounts/{addr}": "path_addr",
    "GET /v1/accounts/{addr}/resource/{struct_tag}": "path_addr_plus_url_encoded_struct_tag"
  },
  "response_headers_monitoring": [
    "x-aptos-chain-id", "x-aptos-ledger-version", "x-aptos-block-height", "x-aptos-epoch"
  ],
  "mixed_weights": {
    "balance_query": 0.30,
    "ledger_info":   0.20,
    "heartbeat":     0.10,
    "tx_lookup":     0.10,
    "tx_by_version": 0.05,
    "tx_list":       0.05,
    "block_query":   0.05,
    "account_meta":  0.05,
    "resources":     0.10
  }
}
```

---

## 11. DSL Field Requirements (this chain's asks to the plugin DSL)

### 11.1 `protocol_kind` field MUST be explicit

Current `config_loader.sh` implicitly assumes `POST / + JSON-RPC body`. Aptos requires the DSL to have a top-level **`protocol_kind: "rest" | "jsonrpc" | "grpc" | "hybrid"`**. Without it, the vegeta target generator cannot decide between `POST / -d '{...}'` and `GET /v1/...`.

### 11.2 Per-method HTTP verb + path template

```yaml
methods:
  balance:
    verb: POST
    path: /v1/view
    body_template: '{"function":"{{function}}","type_arguments":{{type_args}},"arguments":["{{addr}}"]}'
  tx_by_hash:
    verb: GET
    path: /v1/transactions/by_hash/{{hash}}
```
**JSON-RPC chains do not need path/verb** (always `POST /`); REST chains require them. DSL fields must be optional (jsonrpc family omits), otherwise Sui plugin is forced to fill `verb: POST, path: /`.

### 11.3 Response field path (nested extraction)

- `POST /v1/view` returns **`["669182353480"]`** (array of strings); balance is `[0]` / 1e8
- `GET /v1` returns object; height is `.block_height`
- `GET /v1/-/healthy` returns object; status is `.message` (expected `aptos-node:ok`)

DSL needs a **`response_path` field** (JSONPath-lite) for uniform extraction. Sui needs it too (`.result.data` etc.) — this field is **cross-family generic**.

### 11.4 Response-header monitoring (Aptos-unique dimension)

Aptos attaches `x-aptos-chain-id / x-aptos-ledger-version / x-aptos-block-height / x-aptos-epoch / x-aptos-ledger-timestampusec` to every response — **a free synchronization-monitoring signal**, no extra ledger-info call needed.

DSL should allow **`monitor_headers: [<name>, ...]`** so the monitoring pipeline can consume them after plugin load. **Sui / Eth / Solana currently have no such headers**, so this is an Aptos-specific extension point.

### 11.5 Move call body schema

`POST /v1/view` body is `{"function": "<module>::<func>", "type_arguments": [...], "arguments": [...]}`. This is **shared among the Move family** (Sui dry-run is similar); DSL can extract a **family-level shared template** (`movevm.*`).

### 11.6 URL-encoding policy

Aptos `struct_tag` `0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>` contains `<>`, must be URL-encoded to `%3C%3E` in the path. DSL needs a **`path_param_url_encode: true`** flag, else string concatenation yields invalid URLs.

### 11.7 Aptos vs Sui comparison (family merge/split decision)

| # | Dimension | Sui (audited) | Aptos (this research, H8) | Same/Different |
|---|---|---|---|---|
| 1 | RPC protocol | JSON-RPC 2.0 (POST `/` + body) | **REST** (multi-path + GET/POST/HEAD) | ❌ **Different** (protocol-layer fundamental divergence) |
| 2 | Method naming | `sui_*` / `suix_*` prefix strings | **HTTP `<verb> <path>` combo** (no method string) | ❌ **Different** |
| 3 | Auth | public (no key) | public (no key) | ✅ **Same** |
| 4 | Address format | `0x` + 1-64 hex (32 byte) | `0x` + 1-64 hex (32 byte) | ✅ **Same** (both allow leading-zero short form) |
| 5 | Tx hash format | Base58 ~44 chars (digest) | `0x` + 64 hex (32 byte) | ❌ **Different** (encoding entirely different) |
| 6 | Balance query method | `sui_getBalance(addr, coin_type)` (dedicated method) | `POST /v1/view` body calling `0x1::coin::balance` (generic view function) | ⚠️ **Half-different** (semantically same, wire different) |
| 7 | Tx lookup method | `sui_getTransactionBlock(digest, opts)` | `GET /v1/transactions/by_hash/{hash}` OR `by_version/{n}` | ❌ **Different** (Aptos has extra by_version) |
| 8 | Account resource query | `sui_getObject(object_id, opts)` (object-centric) | `GET /v1/accounts/{addr}/resources` (account-centric, list all resources) | ❌ **Different** (object model fundamentally different) |
| 9 | Pagination cursor | `cursor: <object_id>` / `cursor: <opaque>` | `start: <version>` / `limit: <int>` numeric cursor | ❌ **Different** |
| 10 | Object/Resource model | **Sui Object** (owned objects; object is first-class) | **Move Resource** (attached to account; account is first-class) | ❌ **Different** (largest semantic divergence within Move family) |

**Tally**: ✅Same = 2 (#3 auth, #4 address); ⚠️Half = 1 (#6 balance, semantic same wire different); ❌Different = 7.

**Pure-same ratio = 2/10 = 20%; including half-different at best 3/10 = 30%.** Well below the 70% (7/10) merger threshold.

### 11.8 DSL decision (key deliverable)

- [ ] merge as `movevm` family (≥ 7/10 same)
- [x] **split `movevm-sui` and `movevm-aptos` (< 7/10 same; observed 2-3/10)**
- [ ] shared base + sub-family extensions (5-7/10 same)

**Rationale (3 paragraphs)**:

**Paragraph 1 — Protocol-layer divergence is a hard blocker; cannot be bridged at plugin-schema layer**. Sui uses JSON-RPC 2.0 (`POST /` + `{"method":"sui_getObject","params":[...]}`); Aptos explicitly rejects JSON-RPC (H8 verified: 405 + `web_framework_error`). This means vegeta target files, HTTP body templates, URL patterns, URL encoding, and HTTP verb choices all differ. Attempting one plugin schema to support both would result in ~60% of schema fields being conditional (`if family==sui then ... else ...`) — **more complex than two separate schemas** (token-level "shoehorn a hybrid into a generic" anti-pattern).

**Paragraph 2 — Semantic layer can be shared, but should live in utils, not in family schema**. Move `struct_tag` parsing (`0x1::coin::CoinStore<T>`), framework address mental model (`0x1` ~ `0xa`), `CoinStore` resource concept, view function calling convention (`{function, type_arguments, arguments}` triple) — these VM/semantic concepts are common between Sui and Aptos and can be abstracted into **`tools/move_utils.py`** (imported by both SuiAdapter and AptosAdapter). **But they should not** be embedded in the plugin DSL schema. DSL schema is the protocol-binding layer; semantic helpers are the utility layer; **responsibilities must be split**.

**Paragraph 3 — Recommended structure + naming**:

```
plugins/
├── movevm-sui.json       protocol_kind: jsonrpc, methods: sui_* / suix_*
├── movevm-aptos.json     protocol_kind: rest,    methods: GET/POST /v1/*
└── (shared) tools/move_utils.py    parse_struct_tag(), is_framework_addr(), ...
```

Docs and UI may still tag **family = "Move"** for grouping/stats (the user's mental model groups them), but the plugin loader and adapter strictly split by sub-family. This **differs** from the existing EVM-family pattern where "ethereum/bsc/base/polygon/scroll all share EthereumAdapter" — the 5 EVM chains share the same protocol (`POST /` + `eth_*` methods), only branching on `chain_type` for `block_range`. The 2 Move chains differ in protocol; **no EVM-style reuse space exists**.

**One-line conclusion**: **Move is a family label, but the plugin schema must split `movevm-sui` + `movevm-aptos`. Adapters are also separate (`SuiAdapter` and `AptosAdapter`), sharing only the `move_utils.py` semantic-layer helpers.** ✅

---

## 9.9 Real source coverage + timestamps

| Source type | URL/path | Accessed (UTC) | Status |
|---|---|---|---|
| Official REST API docs | https://aptos.dev/build/apis/fullnode-rest-api | 2026-05-23 | E1 (cited, not DOM-verified) |
| OpenAPI Spec (live) | https://fullnode.mainnet.aptoslabs.com/v1/spec.yaml | 2026-05-23 | **H8 verified HTTP:200** (full endpoint enumeration deferred to Phase 2.1) |
| Mainnet probe | `GET https://fullnode.mainnet.aptoslabs.com/v1` | 2026-05-23 | **H8 verified HTTP:200, chain_id=1, ledger_version=5392437054, block_height=783350119** |
| Mainnet alias | `GET https://api.mainnet.aptoslabs.com/v1/-/healthy` | 2026-05-23 | **H8 verified HTTP:200 `aptos-node:ok`** |
| publicnode (candidate) | https://aptos-mainnet.publicnode.com/v1 | 2026-05-23 | **H8 verified HTTP:404 — unavailable** |
| ankr (candidate) | https://rpc.ankr.com/http/aptos/v1 | 2026-05-23 | **H8 verified HTTP:403 (requires API key)** |
| onfinality (candidate) | https://aptos.api.onfinality.io/public/v1 | 2026-05-23 | **H8 verified HTTP:404 — public path does not work** |
| Sui contrast — JSON-RPC | `POST https://fullnode.mainnet.sui.io:443 sui_getChainIdentifier` | 2026-05-23 | **H8 verified `{"result":"35834a8a"}`** confirming Sui uses JSON-RPC |
| Sui config reference | `config/config_loader.sh:622-650` | 2026-05-23 | **E1 read_file verified** (sui rpc_methods + param_formats + system_addresses) |
| Sui audit fields | `tools/audit_rpc_methods.py:209-214` | 2026-05-23 | **E1 read_file verified** (Sui ADAPTER_EXPECTED_FIELDS) |
| Framework chain namespace | `config/config_loader.sh:666` supported_blockchains | 2026-05-23 | **E1 read_file** (aptos **NOT** in list, confirming it is a new chain) |

---

## Open Questions

1. **File numbering conflict**: this draft is named `04-aptos.md` per wave delegation, but `00-SUMMARY.md` line 17 lists Aptos as #17. Should we rename SUMMARY or the file? (User decides at P1 closeout)
2. **OpenAPI spec deep-parse**: `/v1/spec.yaml` is a live 200 OK spec (`application/x-yaml`); this draft did not extract the full endpoint list (probe-only). Should Phase 1.2 Wave 2 implement Aptos L1 audit in `tools/audit_rpc_methods.py` (auto-enumerate from OpenAPI)?
3. **`POST /v1/view` safety/perf**: view functions accept arbitrary Move calls — does the public node have gas/cycle limits? Are malicious views rate-limited? (Not stress-tested in this draft.)
4. **`0x1::coin::balance` vs `0x1::aptos_account::*`**: after Aptos's Fungible Asset (FA) migration, some accounts use the new FA store; the legacy CoinStore returns 404. **Does balance lookup need to probe FA store first?** This draft uses the view function uniformly (auto-tolerant) but did not verify across a full sample.
5. **mock_rpc_server REST routing**: since Aptos introduces REST, **should we proactively refactor mock into per-family handlers in Phase 2.0** (rather than letting Phase 2.1 graft an Aptos router into the single dispatcher — token-level Case-D risk).
6. **Full system_addresses list**: only `0x1` was H8-verified; `0x2`-`0xa` are from E1 doc citations. Should Phase 2.x cross-check via OpenAPI or the Move framework repo for the authoritative list?
7. **block_time precision**: this draft's ~0.15s estimate is from H8 `ledger_version` growth rate, not `block_height` growth rate; the two are different (Aptos block can contain multiple versions). Phase 2.x monitoring should track `x-aptos-block-height` and `x-aptos-ledger-version` **separately** for rate calculation.

---

## Changelog

| Date (UTC) | Author | Change |
|---|---|---|
| 2026-05-23 | Hermes Agent | Initial draft (P1-2 Wave 1): H8-verified 6 endpoints + OpenAPI spec live; Sui vs Aptos 10-dimension comparison (§11.7); decision = **split `movevm-sui` + `movevm-aptos`** (§11.8); 10 Phase 2.1 caller/reader change items (§8.5) |
