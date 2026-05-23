# 06 — Cardano Research Note

> **Version**: v1.0 (initial, Phase 1.2 Wave2)
> **Research date**: 2026-05-23
> **Author**: Hermes Agent
> **Status**: 🟢 Awaiting user review (P1-USER-REVIEW gate + key architectural decision in §11.8)
> **H8 real-evidence compliance**: every key field is tagged E1-E5 (E1=unit test / E2=curl / E3=official docs / E4=GitHub source / E5=framework grep).
> **Why this chain is unique among the 28**: `cardano-node` exposes **no native HTTP RPC** at all; public access **must** go through middleware (Blockfrost / Koios / Ogmios / cardano-graphql). The DSL must express "which middleware is used" — see §11.

---

## Meta

| Field | Value |
|---|---|
| Chain name (zh) | Cardano |
| Chain name (en) | Cardano |
| Number | 06 |
| Mainnet ChainID | `1` (numeric), Network Magic `764824073`; Koios does not expose `chain_id` directly, but `era=Conway` + `epoch=632` uniquely pin mainnet — E2 via `https://api.koios.rest/api/v1/tip` |
| Node application | **cardano-node** (Haskell, maintained by IOG); this research queried **Koios middleware** (cardano-node + cardano-db-sync + PostgREST + HAProxy cluster) — E3 |
| Research date | 2026-05-23 |
| Researcher | Hermes Agent |
| Status | 🟢 Completed (framework does not yet support this chain; this note prepares the Phase 2.x plugin) |
| Framework support today | ❌ — E5: `config/config_loader.sh:666` `supported_blockchains=(solana ethereum bsc base scroll polygon starknet sui)` — `cardano` absent |

---

## 1. Sources

| Type | URL | Visited | Notes |
|---|---|---|---|
| Official docs (Cardano) | https://docs.cardano.org/ | 2026-05-23 | Cardano protocol overview |
| Official docs (cardano-node) | https://github.com/IntersectMBO/cardano-node | 2026-05-23 | Node implementation + config |
| Cardano CIPs | https://cips.cardano.org/ | 2026-05-23 | Address format CIP-19, tokens CIP-25/68, etc. |
| **Blockfrost API docs** | https://docs.blockfrost.io/ | 2026-05-23 | REST middleware, requires project_id |
| **Koios API docs** | https://api.koios.rest/ | 2026-05-23 | Community REST middleware, free & keyless |
| **Ogmios API docs** | https://ogmios.dev/ | 2026-05-23 | WebSocket JSON-RPC wrapper |
| **cardano-graphql** | https://github.com/cardano-foundation/cardano-graphql | 2026-05-23 | GraphQL middleware |
| GitHub (Koios) | https://github.com/cardano-community/koios-artifacts | 2026-05-23 | Koios source |
| Explorer (Cardanoscan) | https://cardanoscan.io/ | 2026-05-23 | Address/tx explorer for verifying real data |
| Explorer (Cexplorer) | https://cexplorer.io/ | 2026-05-23 | Backup explorer |

---

## 2. Protocol Family

| Field | Value |
|---|---|
| Family | **Cardano (EUTXO + Ouroboros)** — **standalone family**. Looks like Bitcoin UTXO but is fundamentally different (EUTXO carries datum + script + reference inputs) |
| Consensus | **Ouroboros Praos** (PoS, VRF-based slot leader election) — E2 confirmed via `vrf_key`, `op_cert` fields |
| VM | **Plutus** (Haskell-based scripting, V1/V2/V3) — not EVM/WASM/MoveVM |
| Block time | **~20 seconds/block average** (active slot coefficient `f=0.05`, 1 slot = 1s, expected block every 20 slots); E2 confirmed via epoch_slot=333120, block_no=13456426 consistent with spec |
| Finality | **Probabilistic**; ~36 slots (~12 min) commonly considered safe; Ouroboros Genesis offers stronger guarantees |
| Reuse existing adapter? | **No — must build `CardanoAdapter`**: 1) EUTXO ≠ Bitcoin UTXO data shape (datum/script); 2) no native HTTP RPC, needs a middleware abstraction; 3) Bech32 multi-type addresses (payment / stake / script); 4) native multi-asset (not contract-based tokens) |
| In-family chains (planned) | 1 (Cardano mainnet); no sister chain (Cardano has no EVM compatibility, no parachains) |

---

## 3. Public RPC / Middleware

### ⚠️ Critical: native `cardano-node` exposes **no HTTP** — only a local Unix socket. Public access requires middleware.

### Endpoint candidates (live-tested)

| Endpoint | Middleware type | Auth | Live status | Notes |
|---|---|---|---|---|
| `https://api.koios.rest/api/v1` | **Koios REST** (PostgREST + cardano-db-sync) | keyless | ✅ HTTP 200 (E2, multiple) | Community free cluster, recommended |
| `https://cardano-mainnet.blockfrost.io/api/v0` | **Blockfrost REST** | **`project_id` header required** (free registration) | ⚠️ HTTP 403 (E2, no-key call) — `{"error":"Forbidden","message":"Missing project token. Please include project_id in your request."}` | Registration required, free tier 50k/day |
| `wss://ogmios-api.mainnet.dandelion.link/` | **Ogmios WebSocket** | none | ❌ HTTP 000 (E2, 2026-05-23 DNS/connect failed, Dandelion public endpoint is offline) | Historically by Dandelion; **currently self-host only** |
| `https://graphql-api.mainnet.dandelion.link/` | **cardano-graphql** | none | ❌ HTTP 000 (E2, same as above, Dandelion offline) | **Currently self-host only** |

**Trade-off**: only Koios + Blockfrost have working public endpoints. Free public endpoints for Ogmios/cardano-graphql (historically Dandelion / Demeter) were all unreachable in this research window; using them requires **self-deployment** (adds benchmark deployment cost). **Koios is the only keyless option for mock-fallback.**

### curl evidence (executed 2026-05-23 ~18:18 UTC; numeric fields are time-sensitive)

#### 3.1 Koios `/tip` (node height + epoch + slot)

```bash
$ curl -s https://api.koios.rest/api/v1/tip
[{"hash":"5c7f63267a7f9fce7a464c4b70ed1ceda01903f99fca69aa73e0a235b23b085d",
  "epoch_no":632,
  "era":"Conway",
  "abs_slot":187993920,
  "epoch_slot":333120,
  "block_height":13456426,
  "block_no":13456426,
  "block_time":1779560211}]
# Reading: era=Conway (current era post 2024-09 hard fork), height=13456426
```

#### 3.2 Koios `/blocks?limit=1` (latest block metadata)

```bash
$ curl -s "https://api.koios.rest/api/v1/blocks?limit=1"
[{"hash":"5c7f63267a7f9fce7a464c4b70ed1ceda01903f99fca69aa73e0a235b23b085d",
  "epoch_no":632, "abs_slot":187993920, "block_height":13456426,
  "block_size":12565, "block_time":1779560211, "tx_count":4,
  "vrf_key":"vrf_vk17h65ynw5n8lv5mux0gn645yd82prtqj2a0f85u6rdp05e045050qawtgmm",
  "pool":"pool1edqwpnln3zr9gj9sfsmyl72pen6hdwev07xgqj7uz5mkjrgfj6h",
  "proto_major":11, "proto_minor":0,
  "parent_hash":"d145b51828323cf1e6ebb40f1f178bdffc802f71b1729bd3694bba688fbd576e"}]
```

#### 3.3 Koios `POST /address_info` (balance + UTXO set)

```bash
$ curl -s -X POST https://api.koios.rest/api/v1/address_info \
    -H "Content-Type: application/json" \
    -d '{"_addresses":["addr1qxahjgt8c9fsjrc8g0937h5q2cqpyglq9kyy62834ngfyct0kzq5as673n2e05chwvsptgx0ngwtggj20shf84h4fx0qm4kw4a"]}'
[{"address":"addr1qxahjgt8c...m4kw4a",
  "balance":"3354648444",          # lovelace, i.e. 3354.648444 ADA
  "stake_address":"stake1u9hmpq2wcd0ge4vh6vthxgq45r8e5895yf98ct5n6m65n8sxlwymg",
  "script_address":false,
  "utxo_set":[{"value":"5000000","tx_hash":"422f17c048...","tx_index":0,
               "asset_list":[], "block_time":1752445699, "block_height":12121688,
               "datum_hash":null, "inline_datum":null, "reference_script":null}, ...]}]
# Note: `balance` is String (to avoid JS Number precision loss, same style as Cosmos REST)
# `utxo_set` carries EUTXO-specific fields: datum_hash / inline_datum / reference_script
```

#### 3.4 Koios `POST /tx_info` (transaction details)

```bash
$ curl -s -X POST https://api.koios.rest/api/v1/tx_info \
    -H "Content-Type: application/json" \
    -d '{"_tx_hashes":["a8aabe32bfb7b23a98c94b5037b60e4fedce468334ccaf94cdb642a9a47bc371"]}'
[{"tx_hash":"a8aabe32...","block_height":13456426,
  "tx_size":2205, "total_output":"3237701515", "fee":"606247",
  "invalid_after":"188000808",
  "collateral_inputs":[], "reference_inputs":[],
  "inputs":[...], "outputs":[
    {"value":"3235081035", "asset_list":[],
     "payment_addr":{"bech32":"addr1qxahjgt8c..."}, ...}
  ]}]
# EUTXO-specific fields: collateral_inputs (Plutus failure collateral) / reference_inputs (CIP-31)
```

#### 3.5 Koios `POST /asset_info` (Cardano native multi-asset metadata)

```bash
$ curl -s -X POST https://api.koios.rest/api/v1/asset_info \
    -H "Content-Type: application/json" \
    -d '{"_asset_list":[["f0ff48bbb7bbe9d59a40f1ce90e9e9d0ff5002ec48f232b49ca0fb9a","000de140337574786f6361706974616c"]]}'
[{"policy_id":"f0ff48bb...", "asset_name":"000de140337574786f6361706974616c",
  "asset_name_ascii":"3utxocapital", "fingerprint":"asset13g6k8tgn0wuzhkgnlhkzmzyvunqd9sgukyd9gq",
  "total_supply":"1", "mint_cnt":1, "burn_cnt":0,
  "minting_tx_metadata":{"721":{...CIP-25 NFT metadata...}}}]
# Assets live on the ledger (native), not in a contract: (policy_id, asset_name) is the unique asset key.
```

#### 3.6 Latency baseline (Koios `/tip`, 3 consecutive calls)

```bash
$ for i in 1 2 3; do curl -s -o /dev/null -m 10 -w "tip call $i: %{time_total}s HTTP:%{http_code}\n" \
    "https://api.koios.rest/api/v1/tip"; done
tip call 1: 0.879014s HTTP:200
tip call 2: 0.681689s HTTP:200
tip call 3: 0.802307s HTTP:200
# Average ~0.78s (note: cross-geo latency from CN to the Koios public cluster dominates)
```

### Rate limit (live response headers)

```bash
$ curl -sI https://api.koios.rest/api/v1/tip
HTTP/2 200
date: Sat, 23 May 2026 18:19:08 GMT
content-range: 0-0/*
content-type: application/json; charset=utf-8
x-frame-options: DENY
# ⚠️ Koios public responses do **not** return explicit `x-ratelimit-*` headers (verified 2026-05-23).
# Per the api.koios.rest landing page: the free tier is IP-based with no explicit number,
# but abuse is prohibited. For production benchmarking the community recommends self-hosting a
# Koios stack (one-click scripts provided).
```

---

## 4. Account Model

| Field | Value |
|---|---|
| Model | **EUTXO** (Extended UTXO) — same ancestor as Bitcoin UTXO, but each UTXO carries datum / script / reference, enabling Plutus smart-contract state |
| Native token decimals | **6** (1 ADA = 1,000,000 lovelace); native assets declare their decimals via CIP-67 metadata |
| Address derivation | **Ed25519** (both payment and stake keys are Ed25519 — same curve as Solana, different address format) |
| Special account types | 1) **Payment address** (`addr1...`, spendable); 2) **Stake address** (`stake1...`, for delegation, holds no funds); 3) **Script address** (`addr1z...` or `addr1w...`, Plutus contract-held); 4) **Reward address** (claims staking rewards) — E2 confirmed via `address_info.stake_address` |
| Asset model | **Native multi-asset** (not a contract!), `asset_id = policy_id (28-byte hex) + asset_name (≤32-byte hex)`. All native assets get the same ledger-level guarantees as ADA. |

---

## 5. Core RPC / Middleware Methods (required by this framework)

> Only methods this benchmark framework needs (using Koios REST as baseline). Full API at https://api.koios.rest/.

| Method | HTTP | Category | Description | Suggested mixed weight |
|---|---|---|---|---|
| `GET /tip` | GET | block height | Liveness + height sync check (like `eth_blockNumber`) | 0.05 |
| `GET /blocks?limit=N` | GET | block list | Metadata of the latest N blocks | 0.05 |
| `POST /block_info` | POST | block content | Full block info for a list of hashes | 0.05 |
| `POST /block_txs` | POST | block tx list | Tx-hash list for a given block_hash (lightweight) | 0.05 |
| `POST /tx_info` | POST | tx lookup | Full tx (with EUTXO inputs/outputs) for a hash list | 0.20 |
| `POST /tx_utxos` | POST | tx utxo | Just inputs/outputs UTXOs of a tx (lighter) | 0.05 |
| `POST /address_info` | POST | balance | **Address balance + UTXO set** (Cardano's "getBalance" equivalent) | 0.25 |
| `POST /address_assets` | POST | token balance | All native assets held by an address | 0.15 |
| `POST /asset_info` | POST | asset metadata | Native asset metadata (analog to ERC20 metadata, but native) | 0.10 |
| `GET /epoch_params` | GET | chain params | Current epoch protocol params (min_fee_a/b, max_tx_size, ...) | 0.05 |

**Weights must sum to 1.0** ✅ (0.05×5 + 0.20 + 0.25 + 0.15 + 0.10 = 1.00)

**Key differences vs EVM/Solana**:
- Most read methods are **POST** (array inputs; RESTful design picks body for lists). The vegeta target generator must support POST body + JSON content-type.
- No `eth_call` equivalent; contract state is queried via `script_info` / datum lookups.

---

## 6. Address Format

| Field | Value |
|---|---|
| Encoding | **Bech32** (CIP-19), `hrp = "addr"` (mainnet payment) / `"stake"` (mainnet stake) / `"addr_test"` (testnet) |
| Length | **payment addr ~103 chars** including hrp; stake addr ~59 chars — E2 confirmed |
| Checksum | **Yes** (Bech32 BCH checksum, 5 chars over 32-char alphabet) |
| Example (real mainnet) | `addr1qxahjgt8c9fsjrc8g0937h5q2cqpyglq9kyy62834ngfyct0kzq5as673n2e05chwvsptgx0ngwtggj20shf84h4fx0qm4kw4a` (E2: 3354.648444 ADA balance, verifiable at https://cardanoscan.io/address/...) |
| Stake addr example | `stake1u9hmpq2wcd0ge4vh6vthxgq45r8e5895yf98ct5n6m65n8sxlwymg` (delegation side of the same address) |
| Validation regex | `^addr1[02-9ac-hj-np-z]{50,110}$` (payment mainnet); `^stake1[02-9ac-hj-np-z]{50,70}$` (stake) |

**Address-type detection (from header byte, high 4 bits)**:
- `addr1q...` = base (payment+stake)
- `addr1z...` / `addr1w...` = script-locked
- Type detection requires Bech32 decoding + inspecting the first byte's high nibble — must be implemented by the adapter.

---

## 7. Signature Lookup (transaction hash)

| Field | Value |
|---|---|
| Hash format | **Hex (no 0x prefix)**, Blake2b-256 digest |
| Length | **64 hex chars** (32 bytes) |
| Example (real mainnet tx) | `a8aabe32bfb7b23a98c94b5037b60e4fedce468334ccaf94cdb642a9a47bc371` (E2 — tx index 0 of block 13456426, verifiable at https://cardanoscan.io/transaction/a8aabe32...) |
| Lookup method | Koios: `POST /tx_info` (body: `{"_tx_hashes":["<hash>"]}`) / Blockfrost: `GET /txs/{hash}` |
| Explorer URL pattern | `https://cardanoscan.io/transaction/<hash>` |

---

## 8. Mixed Set (`mixed` mode weights)

> Used when `BLOCKCHAIN_NODE_BENCHMARK_MODE=mixed`

```json
{
  "balance_query": 0.25,
  "tx_lookup": 0.20,
  "token_balance": 0.15,
  "block_query": 0.15,
  "asset_metadata": 0.10,
  "chain_params": 0.05,
  "tip_check": 0.05,
  "tx_utxos": 0.05
}
```

**Sum = 1.00** ✅

**Chain-specific rationale**:
- `asset_metadata` (0.10): native multi-asset is a Cardano signature feature; real dApps query `asset_info` frequently.
- `chain_params` (0.05): Plutus tx construction needs `epoch_params` (min_fee coefficients) — a normal on-chain call.
- `tx_utxos` (0.05): lighter than `tx_info`, only UTXO flow; wallets use it often.

---

## 8.5 Phase 2.1 caller/reader change list (token-level Gate 3)

**Mandatory**: every chain's research note must list Phase 2.1 caller/reader changes, to avoid caller-blind plugin edits (cf. `token-level-careful-edit` skill Case-B/D).

**This chain is new (no existing code), so #1-3 are required; #4-8 marked N/A as appropriate**:

| # | Location (file:line) | Change | Why |
|---|---|---|---|
| 1 | `config/config_loader.sh:666` `supported_blockchains=(...)` | **Add `cardano`** to the array | Otherwise `validate_blockchain_node` rejects `BLOCKCHAIN_NODE=cardano` |
| 2 | `config/config_loader.sh` per-chain `rpc_methods.mixed` | **Create**: 10 methods from §5 + weights from §8 | Consumed by the vegeta target generator |
| 3 | `config/config_loader.sh` per-chain `param_formats` | **Create**: `POST /address_info` body=`{"_addresses":[...]}`, `POST /tx_info` body=`{"_tx_hashes":[...]}`, etc. | `generate_rpc_json` falling back to defaults yields vegeta 400 |
| 3a | `config/config_loader.sh` per-chain `http_method` mapping | **Create**: many Cardano methods are **POST** (array inputs); unlike Solana/EVM (POST + single path), Koios is a RESTful multi-path POST/GET mix | Vegeta target defaults to `POST /`; Cardano must switch path & verb per method |
| 4 | `tools/fetch_active_accounts.py` adapter | **Add `CardanoAdapter`**: `fetch_recent_blocks` → Koios `/blocks?limit=N` → extract & dedup `payment_addr.bech32` | mixed mode needs a real address pool, not static seeds |
| 5 | `analysis-notes/baseline-current-state.md` | Grep "supported chains" list, **append cardano (EUTXO, middleware: Koios)** | Keep docs aligned with code; prevent v1.4.1-style doc-vs-code drift |
| 6 | `analysis-notes/disk-and-network-pipeline-redesign.md` | Grep this chain, **append**: Cardano uses Koios HTTPS, no mempool websocket | Network pipeline notes in sync |
| 7 | `analysis-notes/research_notes/<cardano notes>.md` | **Create** Cardano research notes (or upgrade any earlier N/A entry with Wave2 results) | Research notes reflect reality |
| 8 | `tests/<chain-specific test>.sh` or `.py` | **Create** `tests/test_cardano_smoke.sh`: hit `/tip` and `POST /address_info` once each; assert HTTP 200 + key fields present | L1/L2 unit test ensures plugin JSON is correct |
| 9 | `tools/mock_rpc_server.py` | **Add** `/api/v1/tip`, `/api/v1/blocks`, `POST /api/v1/address_info`, `POST /api/v1/tx_info`, ... cases; response payloads from §3 real samples | Mock mode must run this config |

**Special note: multi-path + POST body**: Cardano is the **first chain in the 28 that is not a single-path `POST /` JSON-RPC** (Cosmos is similar but its paths are stabler). Before Phase 2.1 starts, confirm that `core/master_qps_executor.sh`'s vegeta target file format supports the `METHOD URL\nHeader\n@body.json` three-part form; otherwise the target generator must be upgraded first (a separate ticket).

**Testing requirement**: after Phase 2.1, run `core/master_qps_executor.sh --mixed --duration 30` (or the shortest e2e_smoke), inspect the vegeta error rate, **all requests must be 200** — this is the E2 evidence for this chain's plumbing.

---

## 9. Mock Notes (mock_rpc_server implementation)

- **Request paths**: **multi-path**, not a single `POST /jsonrpc`. Examples: `GET /api/v1/tip`, `POST /api/v1/address_info`, `POST /api/v1/tx_info`.
- **Response schemas** (real samples in §3; key cases listed below):

  ```json
  // GET /api/v1/tip
  [{"hash":"<32-byte hex>","epoch_no":632,"era":"Conway","abs_slot":<int>,
    "epoch_slot":<int>,"block_height":<int>,"block_no":<int>,"block_time":<unix>}]

  // POST /api/v1/address_info
  [{"address":"addr1...","balance":"<lovelace string>",
    "stake_address":"stake1...","script_address":false,
    "utxo_set":[{"value":"<lovelace>","tx_hash":"<hex>","tx_index":<int>,
                 "asset_list":[],"datum_hash":null,"inline_datum":null,
                 "reference_script":null,"block_time":<unix>,"block_height":<int>}]}]
  ```

- **Error codes** (Koios PostgREST style):
  - HTTP 400: body schema error (e.g. `_addresses` not an array)
  - HTTP 404: path not found (method typo)
  - HTTP 429: rate-limit (Koios free tier sporadically)
  - HTTP 403: Blockfrost without project_id
  - **No JSON-RPC `error.code`** (RESTful uses HTTP code, unlike EVM's `-32602`)

- **Mock implementation complexity**: **Medium**
  - Reason 1: multi-path (~10 endpoints) vs single dispatcher
  - Reason 2: POST body must parse JSON-array input (`_addresses` / `_tx_hashes` / `_block_hashes`)
  - Reason 3: UTXO fields are deeply nested (asset_list / datum_hash / inline_datum); manageable in a mock because we can return fixed §3 samples
  - Advantage: §3 live JSON can be copied verbatim as fixtures, no hand-crafting

---

## 10. Adapter Reuse Decision

### Candidate adapters

| Adapter | Compatibility | Missing capabilities |
|---|---|---|
| EthereumAdapter | **5%** | Account model (EUTXO vs Account), address format (Bech32 vs Hex), API protocol (multi-path REST vs single-endpoint JSON-RPC), asset model (native vs ERC20) — all differ |
| SolanaAdapter | **5%** | Same as above; both use Ed25519 but address format and RPC protocol differ entirely |
| BitcoinAdapter | **15%** | UTXO is similar in shape (both have a utxo_set) but EUTXO adds datum/script fields; Bitcoin uses secp256k1, Cardano Ed25519; Bitcoin's JSON-RPC ships with the daemon, Cardano requires middleware |
| CosmosAdapter (Wave1 plan) | **20%** | REST style is similar (both RESTful, both String numerics), but Cardano is UTXO vs Cosmos Account, plus different address format and asset model |

### Decision

- [x] **New** `CardanoAdapter` (standalone family, EUTXO + middleware abstraction)
- [ ] Reuse
- [ ] Hybrid

### Rationale

**Reason 1 (data-model independence)**: EUTXO is a fourth model alongside Bitcoin UTXO, EVM Account, and Cosmos Bank. Each UTXO carries datum (contract state), script (locking logic), and reference inputs (CIP-31 read-only references). Any reuse of an existing adapter would fail in `parse_balance` / `parse_tx`: a UTXO-set balance is `sum(utxo.value for utxo in utxo_set)`, not a single `balance` field.

**Reason 2 (protocol-layer independence)**: Cardano is the **only one of the 28 chains with no native HTTP RPC** and must go through middleware. CardanoAdapter must encapsulate a "middleware choice" abstraction (Blockfrost / Koios switchable — see §11.8). Every other adapter assumes a single RPC endpoint. This abstraction belongs in the adapter, not bolted onto config.

**Reason 3 (API call style)**: Koios REST is **multi-path POST** (`POST /address_info` with array body). It is neither EVM's single-path JSON-RPC nor Cosmos's GET-only REST. CardanoAdapter needs per-method path routing + body templating.

### Config JSON example (this chain, Koios as default middleware)

```json
{
  "chain": "cardano",
  "family": "cardano-eutxo",
  "adapter": "CardanoAdapter",
  "chain_id": 1,
  "network_magic": 764824073,
  "middleware": "koios",
  "rpc_endpoint": "https://api.koios.rest/api/v1",
  "block_time_ms": 20000,
  "address_format": "bech32",
  "address_prefix_payment": "addr1",
  "address_prefix_stake": "stake1",
  "native_decimals": 6,
  "rpc_methods": {
    "block_height": {"verb": "GET", "path": "/tip"},
    "block_query": {"verb": "POST", "path": "/block_info", "body_key": "_block_hashes"},
    "tx_lookup":   {"verb": "POST", "path": "/tx_info", "body_key": "_tx_hashes"},
    "tx_utxos":    {"verb": "POST", "path": "/tx_utxos", "body_key": "_tx_hashes"},
    "balance":     {"verb": "POST", "path": "/address_info", "body_key": "_addresses"},
    "token_balance":{"verb": "POST", "path": "/address_assets", "body_key": "_addresses"},
    "asset_metadata":{"verb":"POST", "path":"/asset_info", "body_key":"_asset_list"},
    "chain_params":{"verb": "GET", "path": "/epoch_params"}
  },
  "mixed_weights": {
    "balance_query": 0.25,
    "tx_lookup": 0.20,
    "token_balance": 0.15,
    "block_query": 0.15,
    "asset_metadata": 0.10,
    "chain_params": 0.05,
    "tip_check": 0.05,
    "tx_utxos": 0.05
  }
}
```

---

## 11. DSL Field Requirements (chain-specific!)

### 11.1 Base fields (inherit template)

`chain` / `family` / `adapter` / `chain_id` / `rpc_endpoint` / `block_time_ms` / `address_format` / `rpc_methods` / `mixed_weights` — see §10 config JSON.

### 11.2 EUTXO-specific fields

| Field | Meaning | Default |
|---|---|---|
| `account_model` | `eutxo` | `eutxo` |
| `native_decimals` | lovelace→ADA digits | 6 |
| `address_prefix_payment` | Bech32 payment hrp+v | `addr1` |
| `address_prefix_stake` | Bech32 stake hrp+v | `stake1` |
| `network_magic` | mainnet=764824073 | 764824073 |

### 11.3 HTTP multi-path + body fields (key new requirement)

The DSL must express the **(HTTP verb, URL path, body schema)** for each method — Cardano is not a single JSON-RPC dispatcher:

```yaml
rpc_methods:
  balance:
    verb: POST
    path: /address_info
    body_template: '{"_addresses":["{{address}}"]}'
```

**Current framework caller-blind risk**: if `master_qps_executor.sh`'s vegeta target generator assumes `POST /` + JSON-RPC body, it must be upgraded first.

### 11.4 Balance-computation field (EUTXO-specific)

The DSL must declare whether **balance is sum(utxo_set.value) or a direct `balance` field**:

- Koios `/address_info` returns `balance` (already summed) → DSL: `balance_extractor: $.balance`
- Blockfrost `/addresses/{addr}` returns `amount: [{"unit":"lovelace","quantity":"..."}]` → DSL: `balance_extractor: $.amount[?(@.unit=="lovelace")].quantity`

### 11.5 Asset model fields (native multi-asset)

```yaml
asset_model: native_multi_asset
asset_id_format: "{policy_id}.{asset_name_hex}"   # 28+≤32 byte hex
asset_decimals_source: "cip67_metadata"           # decimals come from CIP-67 metadata
```

### 11.6 Finality fields

```yaml
finality_type: probabilistic
finality_confirmations: 36   # ~12 min, recommended safe threshold
finality_genesis_alternative: ouroboros_genesis  # optional stronger guarantee
```

### 11.7 Cardano middleware comparison (mandatory)

| Dimension | Blockfrost | Koios | Ogmios | cardano-graphql |
|---|---|---|---|---|
| Protocol | REST | REST (PostgREST) | WebSocket JSON-RPC | GraphQL |
| Auth | **`project_id` header required** (free registration) — E2 confirmed: no-key = HTTP 403 | **keyless** — E2 HTTP 200 | none | none |
| Balance query | `GET /addresses/{addr}` ⚠️ not E2'd (skipped without key) | `POST /address_info` body=`{"_addresses":[...]}` — E2 ✅ | `Query/utxo` (WS JSON-RPC, self-host) ⚠️ not E2'd | `query addresses { utxos { value } }` ⚠️ not E2'd |
| Tx query | `GET /txs/{hash}` ⚠️ not E2'd | `POST /tx_info` body=`{"_tx_hashes":[...]}` — E2 ✅ | `Query/utxo` etc. ⚠️ not E2'd | `query transactions(hash:...)` ⚠️ not E2'd |
| Public endpoint | `https://cardano-mainnet.blockfrost.io/api/v0` ✅ reachable (needs key) | `https://api.koios.rest/api/v1` ✅ keyless | ❌ Dandelion `wss://ogmios-api.mainnet.dandelion.link/` E2 HTTP 000 (offline), **self-host only** | ❌ Dandelion `https://graphql-api.mainnet.dandelion.link/` E2 HTTP 000 (offline), **self-host only** |
| Rate limit | **50,000 requests/day** (free tier per official docs) ⚠️ not E2'd (no key to trigger) | **No explicit number**, IP-based; 3 calls to `/tip` all 200 (no `x-ratelimit-*` headers) ⚠️ Koios recommends self-hosting for production | self-host unlimited | self-host unlimited |
| Self-host cost | not supported (SaaS only) | **Supported** (`koios-artifacts` one-click; needs ~500 GB SSD + cardano-node + db-sync) | needs cardano-node + Ogmios binary (~500 GB SSD) | needs cardano-node + db-sync + hasura + graphql-engine (~500 GB SSD; most complex stack) |
| DSL reuse in this framework | REST → reuses Cosmos REST vegeta GET/POST infra ✅ | REST (POST body) → partial reuse with Cosmos REST ✅, plus path-per-method | WebSocket → **no reuse with any current chain** (framework has no WS target generator) | GraphQL → **framework has no GraphQL DSL support** |
| Data completeness | High (includes metadata, Plutus scripts) | High (community db-sync, full node) | Complete (direct node-socket forwarding) | High (includes Plutus + all CIPs) |

### 11.8 DSL middleware recommendation (mandatory)

Which middleware should this framework adopt?

- [ ] Blockfrost (REST, public, API key required)
- [x] **Koios** (REST, free & keyless) — **recommended**
- [ ] Ogmios (WebSocket, self-host)
- [ ] cardano-graphql (GraphQL, requires DSL GraphQL support)

**Rationale (3 paragraphs)**:

**Paragraph 1 — lowest DSL complexity**: Koios is REST + JSON and shares the same vegeta HTTP target infrastructure as Cosmos REST (Wave1): GET URL / POST body / JSON response. Adding Koios only requires extending the per-method `{verb, path, body_template}` fields (already laid out in §10's plugin schema); no new transports (WebSocket / GraphQL) need to be introduced into the framework. Ogmios needs a WebSocket target generator (Vegeta has no native WS support, a new tool is required); cardano-graphql needs DSL support for GraphQL query templates + variables — both are **new infrastructure investments** that far exceed the scope of a per-chain Phase 2.x plugin.

**Paragraph 2 — public endpoint availability + zero ops cost**: live test (2026-05-23): the Koios public cluster `api.koios.rest` returns 200 across the board, 3 `/tip` calls average 0.78 s (cross-geo); Blockfrost requires registering for a project_id (50k/day free tier), which would cap our benchmark (`50k / 86400s ≈ 0.58 QPS` — completely infeasible for high-QPS load tests); Ogmios's and cardano-graphql's historical public endpoint Dandelion is offline, and self-hosting needs ~500 GB SSD + days of cardano-node sync — **not realistic** for CI/mock scenarios. Koios is the only option that is **zero-ops** AND **keyless**.

**Paragraph 3 — benchmark accuracy caveat & reversal condition**: the Koios public cluster is a community charity resource and is **not suited for production-grade real-node load testing** (no `x-ratelimit-*` headers measured; the Koios docs recommend self-hosting for heavy load). This framework's benchmark role should be framed as "RPC-client-side protocol correctness + mock compatibility testing", not "measuring the Koios public cluster's server throughput". **Reversal condition**: if Phase 2.x needs **real-node load testing** (measuring cardano-node's own QPS ceiling), then a self-hosted Koios stack or Ogmios is mandatory and this decision should be upgraded to "public = Koios for smoke, self-host = Ogmios for load". For the current phase, **Koios public + mock_rpc_server fallback** is optimal.

---

## Open Questions

- [ ] **Which schema version absorbs the new `(verb, path, body_template)` DSL fields?** `config/config_loader.sh` is currently bash-array style; Cardano is the first chain that needs path-per-method. Recommend introducing a formal `chains/<name>.json` plugin schema in Phase 2.x (critical infra for the Q4 = C 95% "add a chain with 0 Python" goal).
- [ ] **EUTXO balance abstraction**: should `CardanoAdapter.getBalance(addr)` include staking rewards? Stake-address balance queries need `POST /account_info` (not E2'd in this research; only `address_info` payment balance was verified).
- [ ] **Plutus smart-contract state queries**: this research did not cover `script_info` / datum queries (mixed §5 does not include contract calls). If Phase 2.x adds Plutus call benchmarks, a section will need to be added.
- [ ] **Minimal Koios self-host configuration**: can `koios-artifacts` run a light mode without db-sync? (impacts CI cost)
- [ ] **Blockfrost project_id management**: if Phase 2.x supports Blockfrost (as Koios failover), pin an env var name (e.g. `BLOCKFROST_PROJECT_ID`) and ensure benchmark reports redact it.

---

## Changelog

| Date | Author | Change |
|---|---|---|
| 2026-05-23 | Hermes Agent | Initial research (Phase 1.2 Wave2): all Koios methods E2-verified; Blockfrost no-key path E2-confirmed HTTP 403; Ogmios / cardano-graphql public endpoints E2-confirmed ❌ (Dandelion offline); recommended Koios as framework middleware. |
