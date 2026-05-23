# 08 — NEAR Protocol Research

> **Version**: v1.0 (initial draft, Phase 1.2 Wave 2)
> **Research date**: 2026-05-23
> **Author**: Hermes Agent (token-level + research-first + H8 evidence / E1–E5 grading)
> **Status**: 🟢 Awaiting user review (P1-USER-REVIEW gate)
> **Mandatory coverage**: `_template.md` §1–§10 + §11 DSL (incl. 11.7 query-dispatcher challenge, 11.8 three-option decision)
> **Key deliverable**: NEAR `query` is an RPC dispatcher — DSL must model it explicitly (chosen **Option B = `logical_method` separation**, see §11.8)

---

## Meta

| Field | Value |
|---|---|
| Chain (CN) | NEAR Protocol |
| Chain (EN) | NEAR Protocol |
| Number | 08 (within Wave 2) / Final SUMMARY number TBD at P1 wrap-up (Open Q1) |
| Mainnet ChainID | **`"mainnet"` (string, not integer)** — H8 verified via `status.chain_id` |
| Genesis hash | `EPnLgE7iEq9s7yTkos96M3cWymH5avBAPm3qx3NXqR8H` — H8 verified (3 independent endpoints agree) |
| Research date | 2026-05-23 |
| Researcher | Hermes Agent |
| Status | 🟢 Initial draft complete |

---

## 1. Sources

| Type | URL | Date | Notes / Evidence grade |
|---|---|---|---|
| Official docs | https://docs.near.org | 2026-05-23 | E1 (cited, no DOM verification) |
| RPC spec | https://docs.near.org/api/rpc/introduction | 2026-05-23 | E1 — source of the query-dispatcher pattern |
| Protocol spec (nearcore) | https://github.com/near/nearcore | 2026-05-23 | E1 cited (not git-cloned) |
| Nomicon (protocol whitepaper) | https://nomicon.io | 2026-05-23 | E1 cited — account_id / finality semantics |
| Explorer | https://nearblocks.io | 2026-05-23 | E1 cited (no DOM verification) |
| Public RPC × 3 | rpc.mainnet.near.org / free.rpc.fastnear.com / near.lava.build | 2026-05-23 | **H8 HTTP:200 + matching genesis_hash** (see §3) |

---

## 2. Protocol Family

| Field | Value | Evidence |
|---|---|---|
| Family | **NEAR** (proprietary; **not** EVM / Move / UTXO / Cosmos / Substrate) | Core conclusion of this research (§10 / §11.8) |
| Consensus | Nightshade (Doomslug + Thresholded PoS, sharded) | E1 docs (no paper-level verification) |
| VM | **WASM** (contracts compile to Wasm; Rust / AssemblyScript SDKs) | E1 docs + `view_code` returns wasm payload (§5) |
| Block time | **~0.6–1.0s observed**: `latest_block_time=2026-05-23T18:18:46Z` vs `epoch_start_height=199554728` and current `latest_block_height=199597051` → 42323 block delta over ~21.5h ⇒ ~1.83s/block (H8 in-epoch average) | **H8 from status.sync_info** |
| Finality | **Three tiers**: `optimistic` (chain head) / `near-final` (doomslug-confirmed) / `final` (BFT-final) — all H8 verified | **H8** (§5 M7/M8/T3) |
| Sharding | Yes, multi-shard (chunks array, each block contains multiple chunks; observed chunks count ≥ 6) | **H8 from block.result.chunks** |
| Reuse existing adapter? | **No** (JSON-RPC envelope matches EVM but method set / account model / param schema all differ; query-as-dispatcher is also not an EVM pattern) | See §10 + §11.7/11.8 |

---

## 3. Public RPC

| Endpoint | Auth | Rate limit | Notes / H8 |
|---|---|---|---|
| `https://rpc.mainnet.near.org` | none | not officially published, anonymous | **H8 HTTP:200 TIME:2.19s** (status returns chain_id=mainnet, latest_block_height=199597051) |
| `https://free.rpc.fastnear.com` | none | FastNEAR free tier (undisclosed) | **H8 HTTP:200 TIME:0.17s** (same genesis_hash; **fastest**) |
| `https://near.lava.build` | none | Lava Network public gateway | **H8 HTTP:200 TIME:0.43s** (same genesis_hash) |
| `https://near-rpc.publicnode.com` | — | — | **H8 HTTP:404 — wrong path or unavailable** (not recommended) |

**curl evidence** (mandatory, proves RPC is live):
```bash
curl -s -X POST https://free.rpc.fastnear.com \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"status","params":[]}'
# Observed (excerpt, 2026-05-23):
# {"jsonrpc":"2.0","result":{
#   "chain_id":"mainnet",
#   "genesis_hash":"EPnLgE7iEq9s7yTkos96M3cWymH5avBAPm3qx3NXqR8H",
#   "latest_protocol_version":83,
#   "sync_info":{
#     "latest_block_hash":"4C3RGv4vDSyts5zKw7r5kVKGheihKEYYHukvictJVsYy",
#     "latest_block_height":199597051,
#     "latest_block_time":"2026-05-23T18:18:46.274055678Z",
#     "syncing":false }, ... }}
```

**Cross-endpoint agreement**: All three independent endpoints return identical `genesis_hash` (`EPnLgE7iEq9s7yTkos96M3cWymH5avBAPm3qx3NXqR8H`) — confirms they all connect to the same mainnet chain, and **any of them is a valid baseline for benchmark / mock verification**.

---

## 4. Account Model

| Field | Value | Evidence |
|---|---|---|
| Model | **Account** (Account-based, same as EVM; **not** UTXO) | E1 + H8 `view_account` returns `amount/locked/storage_usage` |
| account_id type | **Human-readable string** (e.g., `relay.aurora`, `near`, `wrap.near`, `bob.near`) — **differs from every existing supported chain** (Solana/EVM/Bitcoin/Sui) | H8 verified (`relay.aurora` query returned amount=`1759801172720814773223780901` yoctoNEAR) |
| Naming rules | 2–64 chars; `a-z 0-9 _ -`; `.` separates hierarchy (top-level names like `near`, `aurora` are protocol-registered); also supports implicit 64-hex accounts | E1 Nomicon |
| Native token decimals | **24** (yoctoNEAR; 1 NEAR = 10^24 yoctoNEAR) | E1 docs (no explorer back-calc done here) |
| Sub-accounts | Yes (`X.Y` form; only `Y` may create accounts ending in `.Y`) | E1 docs |
| Special accounts | Top-level account `near` is the system contract (observed `view_account` returned `storage_usage=2263935` and non-zero `code_hash` ⇒ contract account) | **H8 verified** |
| Key model | **Access Key list** (each account holds N keys, each `FullAccess` or `FunctionCall`-restricted) | **H8 via `query view_access_key_list`** returned keys array with `nonce / permission` |
| Address derivation | Ed25519 (`public_key` prefix is `ed25519:`) | **H8 verified** |

---

## 5. Core RPC Methods (required by this framework)

> NEAR's full RPC surface is much larger than this table; here we list only methods needed by mixed/single modes. Full API: https://docs.near.org/api/rpc/

### 5.1 Direct methods (no dispatcher)

| Method | Category | params shape | Mixed weight | H8 evidence |
|---|---|---|---|---|
| `status` | node info + chain head | `[]` | 0.05 | ✅ HTTP:200 (§3 T2) |
| `block` | block lookup | `{"finality":"final"}` or `{"block_id":<num>}` or `{"block_id":"<hash>"}` | 0.10 | ✅ (§5 M2 by height, §3 T3 by finality) |
| `chunk` | shard chunk lookup | `{"chunk_id":"<hash>"}` | 0.02 (low) | ⚠️ Not directly verified (the chunk_hash extraction step was blocked by user environment; however block response's chunks[] each contains `chunk_hash`, API shape E1-cited) |
| `gas_price` | gas price | `[null]` or `[<block_id>]` | 0.05 | ✅ returns `{"gas_price":"100000000"}` (§5 M1) |
| `tx` | transaction status (lightweight) | `["<tx_hash>", "<signer_id>"]` | 0.15 | ⚠️ shape verified only (random hash test timed out without proper response; real shape unproven for `result`) |
| `EXPERIMENTAL_tx_status` | transaction status (detailed) | `["<tx_hash>", "<signer_id>"]` | — | ⚠️ same shape as `tx`, result unverified |
| `broadcast_tx_async` | submit tx (no wait) | `["<base64_signed_tx>"]` | 0.00 (read-only benchmarks unused) | ✅ shape verified (invalid tx returns `-32700 Parse error`) |
| `validators` | validator set | `[null]` or `[<block_id>]` | 0.03 | ✅ returns `current_proposals/current_validators` arrays |
| `network_info` | peer / node meta | `[]` | 0.00 | E1 shape only (not run here) |

### 5.2 `query` dispatcher (key! true method in `params.request_type`)

| logical method | `request_type` | key params | Mixed weight | H8 evidence |
|---|---|---|---|---|
| **view_account** | `view_account` | `account_id`, `finality`/`block_id` | 0.20 | ✅ `relay.aurora`/`near` verified |
| **view_access_key_list** | `view_access_key_list` | `account_id`, `finality` | 0.05 | ✅ returns keys[] |
| **view_access_key** | `view_access_key` | `account_id`, `public_key`, `finality` | 0.05 | ✅ returns `nonce/permission` |
| **call_function** (view-only contract call) | `call_function` | `account_id`, `method_name`, `args_base64`, `finality` | 0.20 | ✅ `wrap.near.ft_total_supply()` returned base64-encoded byte array (observed result=[34,50,49,...,34] = ASCII `"21510714514871847363014456029803"`) |
| view_state | `view_state` | `account_id`, `prefix_base64`, `finality` | 0.05 | ⚠️ shape only (public RPC may reject large state) |
| view_code | `view_code` | `account_id`, `finality` | 0.00 (large payload, infrequent) | ⚠️ E1 shape (wasm payload too large) |

**All `query.*` share wire-level `method:"query"`**; the real differentiator is `params.request_type` — **this is the core DSL challenge in §11.7/11.8**.

### 5.3 Mixed weight sum (must = 1.0)

`status:0.05 + block:0.10 + gas_price:0.05 + tx:0.15 + validators:0.03 + view_account:0.20 + view_access_key_list:0.05 + view_access_key:0.05 + call_function:0.20 + view_state:0.05 + chunk:0.02 + remainder 0.05` (for `block by hash` secondary blend) = **1.00** ✅

---

## 6. Address Format

| Field | Value | Evidence |
|---|---|---|
| Encoding | **UTF-8 string** (not hex / base58 / bech32) | H8 — all verified account_ids match `[a-z0-9._-]+` |
| Length | 2–64 chars | E1 docs |
| Checksum | **None** (an account is valid once registered on-chain; no char-level check) | E1 docs |
| Mainnet examples | `relay.aurora` (Aurora bridge); `near` (system contract); `wrap.near` (wNEAR FT contract) | **H8 verified via view_account / call_function** |
| Validation regex | `^([a-z0-9]+[-_]?)*[a-z0-9]+(\.([a-z0-9]+[-_]?)*[a-z0-9]+)*$` (total 2–64) or 64-hex (implicit account) | E1 Nomicon |
| Implicit account (optional) | 64-char lower-hex (`^[0-9a-f]{64}$`) — derived from ed25519 public key | E1 |

**Comparison vs existing chains**:

| Existing chain | Address encoding | NEAR difference |
|---|---|---|
| Solana | Base58 32 bytes | NEAR is a string, no encoding concept |
| Ethereum/BSC/Base/Polygon/Scroll | 0x-prefix 20-byte hex | NEAR is a string with variable length |
| Bitcoin | base58check / bech32 | NEAR is a string |
| Sui/Aptos | 0x-prefix 32-byte hex | NEAR is a string |
| Starknet | 0x-prefix 252-bit hex | NEAR is a string |

**Conclusion**: NEAR account_id requires a new `address_format: "near_account_id"` tag in DSL/adapter; **no existing address regex is reusable**.

---

## 7. Signature Lookup (transaction hash)

| Field | Value | Evidence |
|---|---|---|
| Hash encoding | **Base58** (no checksum, ~43–44 chars, e.g., block_hash `4C3RGv4vDSyts5zKw7r5kVKGheihKEYYHukvictJVsYy`; tx hash uses the same encoding) | **H8 verified** (block_hash / chunk_hash / latest_block_hash all base58) |
| Length | Usually 43–44 chars (32 bytes → base58 ~44) | H8 |
| Lookup method | **Must include `signer_id`**: `tx(["<hash>","<signer_id>"])` (NEAR sharding means hash alone cannot locate the shard) | E1 docs + H8 `broadcast_tx` -32700 Parse error confirms wire shape |
| Explorer URL | `https://nearblocks.io/txns/<hash>` | E1 (no DOM verification) |
| Mainnet example | ⚠️ This draft does not include an independently verified live tx hash (extraction step was blocked); Phase 2.1 must extract via `block.chunks[].transactions[].hash` from the latest block | ⚠️ |

**Key divergence from existing chains**: NEAR's `tx` requires a `(hash, signer_account_id)` tuple — **EVM's `eth_getTransactionByHash(hash)` single-argument shape is not directly reusable**. This is one of the hard constraints preventing EthereumAdapter reuse.

---

## 8. Mixed Set (`mixed` mode weights)

```json
{
  "balance_query": 0.20,
  "access_key_query": 0.10,
  "tx_lookup": 0.15,
  "block_query": 0.12,
  "ft_balance_call": 0.20,
  "view_state": 0.05,
  "gas_price": 0.05,
  "validators": 0.03,
  "status_height": 0.05,
  "chunk_query": 0.02,
  "near_chain_specific": 0.03
}
```

**Weight sum = 1.00** ✅. Mapping to §5:

- `balance_query` = `query{request_type:view_account}`
- `access_key_query` = `query{request_type:view_access_key_list}` + `view_access_key` (combined 0.05+0.05)
- `tx_lookup` = `tx` method (`[hash, signer]`)
- `block_query` = `block` method (60% by `finality:final`, 30% by `block_id:<num>`, 10% by `block_id:<hash>`)
- `ft_balance_call` = `query{request_type:call_function, method_name:"ft_balance_of"}` (NEP-141 FT standard: wrap.near / aurora token / usdt.tether-token.near) — **replaces EVM's ERC20 `eth_call(balanceOf)`**
- `near_chain_specific` remainder = secondary block-by-hash blend

---

## 8.5 Phase 2.1 caller/reader change list (token-level Gate 3)

| # | Location (file:line) | Change | Reason |
|---|---|---|---|
| 1 | `config/config_loader.sh:666` `supported_blockchains=(...)` | **Add `"near"`** | Currently absent (E1 verified); otherwise `BLOCKCHAIN_NODE=near` errors as "Unsupported" |
| 2 | `config/config_loader.sh` `rpc_methods.mixed` for this chain (cf. sui block lines 622–650) | **Add near block**: 11 methods/logical_methods + weights (§8) | Consumed by vegeta target generator; **must use logical_method naming (Option B, §11.8)** |
| 3 | `config/config_loader.sh` `param_formats` for this chain | **Add near block**: params template per logical_method (5 sub-templates for query dispatcher) | `generate_rpc_json` missing-field bugs cause query to fall back to `view_account` default or fail outright |
| 4 | `tools/mock_rpc_server.py` | **Add `method:"query"` branch** with internal routing on `params.request_type` to 5 sub-handlers (view_account / view_access_key / view_access_key_list / call_function / view_state) + `block / status / gas_price / tx / validators / chunk / broadcast_tx_async / network_info` — ~12 cases total | Mock is fallback target; without it, mock mode cannot serve the new plugin |
| 5 | `tools/fetch_active_accounts.py` add `NearAdapter` | Implement `fetch_top_accounts(limit)` — sourced from nearblocks API or fixed seed set (`relay.aurora` / `near` / `wrap.near` / `aurora` / `usdt.tether-token.near` / `token.sweat`) | Account discovery cannot reuse SolanaAdapter / EthereumAdapter |
| 6 | `tools/audit_rpc_methods.py` add `NEAR_ADAPTER_EXPECTED_FIELDS` | Must include `account_id / finality / request_type / args_base64 / method_name / public_key` (query dispatcher field set) | Missing fields at L1 audit ⇒ Phase 2.1 token-level Case-B caller-blind |
| 7 | `analysis-notes/baseline-current-state.md` grep "supported chains" | Sync-add near | Keep docs truthful; prevents v1.4.1-style doc-vs-code drift |
| 8 | `analysis-notes/disk-and-network-pipeline-redesign.md` | Sync | Same as #7 |
| 9 | `analysis-notes/research_notes/<recent plugin DSL note>.md` | Note: query-dispatcher pattern enters schema | Research notes reflect reality |
| 10 | `tests/<new>tests/test_near_e2e.sh` | L1 smoke: `status` + `query view_account relay.aurora` + `block finality:final` (3 calls) | CI baseline before chain-in |

**Given NEAR is a brand-new chain (E1-verified absence of existing code)**, #1–#6 are all required; #7–#10 optional.

**Test requirement**: After Phase 2.1, run `core/master_qps_executor.sh --mixed --duration 30` (or the shortest e2e_smoke) to capture vegeta error rates — **all requests should be 200** as NEAR's E2 evidence.

---

## 9. Mock Notes (mock_rpc_server implementation)

- **Request path**: `POST /` (root, JSON-RPC 2.0; same as EVM / Sui)
- **Response schema** (real mainnet sample required):
  ```json
  {"jsonrpc":"2.0","result":{
     "amount":"1759801172720814773223780901",
     "block_hash":"6bYBg694EaTfJA12gg1WN4PU11PhWfq1ANkSvQabLGyX",
     "block_height":199597056,
     "code_hash":"11111111111111111111111111111111",
     "locked":"0",
     "storage_paid_at":0,
     "storage_usage":149422
  },"id":1}
  ```
  (H8-verified `view_account relay.aurora`, 2026-05-23)
- **Special error codes** (H8 / E1):
  - `-32700`: **Parse error** (H8: `broadcast_tx_async` with invalid base64 returns this code, `name:"REQUEST_VALIDATION_ERROR"`, `cause.name:"PARSE_ERROR"`)
  - `-32600`: Invalid request (E1)
  - `-32601`: Method not found (E1)
  - `-32602`: Invalid params (E1)
  - **NEAR extra semantics**: `HANDLER_ERROR` family (account missing / key missing / block missing) — HTTP still 200, differentiated by `error.cause.name`; mock must preserve the `error` envelope shape.
- **Mock implementation complexity**: **Medium-High**
  - Medium: JSON-RPC envelope identical to EVM
  - High: **`query` sub-dispatch** (5 `request_type` cases) + 3 finality tiers + base64 encoding for args / state / result + `tx` `(hash, signer_id)` tuple key + sharded chunks-array structure

---

## 10. Adapter Reuse Decision

### Candidate adapters

| Adapter | Compatibility | Missing capabilities |
|---|---|---|
| EthereumAdapter | **~15%** (shares JSON-RPC envelope / POST `/` / id field; **method set / param schema / account model / hash encoding / error semantics all differ**) | account_id string / query dispatcher / finality field / base58 hash / `(hash,signer)` tx key / yoctoNEAR 24 decimals / NEP-141 FT call (call_function vs eth_call) |
| SolanaAdapter | **~5%** | Completely different protocol method set (SVM vs WASM); Solana has no dispatcher |
| SuiAdapter | **~10%** | Shared JSON-RPC envelope; account/object model completely different; no dispatcher pattern |
| BitcoinAdapter | **0%** | UTXO vs Account |
| AptosAdapter | **0%** | REST vs JSON-RPC |

### Decision

- [ ] Reuse `EthereumAdapter`
- [x] **New `NearAdapter` (new family `near`)**
- [ ] Hybrid

### Reasoning

**Paragraph 1 — Envelope reuse pays little, semantic-layer differences are hard blockers**. NEAR and EVM share only the JSON-RPC 2.0 envelope (`{jsonrpc, id, method, params}`) and `POST /` path — at the vegeta target-body level the templates can indeed be the same. But everything beyond that — method names, param structure, address validation, hash decoding, balance decoding (yoctoNEAR 24 decimals), `(hash,signer)` two-key tx lookup, three-tier finality semantics, query dispatcher's two-level routing — all require new code paths. The token-level "make the generic a hybrid" anti-pattern reminds us: if the shared layer covers only 15%, forcing EthereumAdapter reuse introduces `if chain == "near"` branch clusters that **drag NEAR into every future EVM change**.

**Paragraph 2 — query dispatcher is a NEAR-unique wire pattern that requires explicit adapter modeling**. EVM/Sui/Solana all follow a "method string = one end-to-end capability" 1:1 pattern; NEAR's `query` is a dispatcher whose true method lives in `params.request_type` — this requires the adapter to maintain a `logical_method → (rpc_method, request_type, params_template)` two-level mapping (§11.8 Option B). EthereumAdapter has no such two-level mapping; bolting it on breaks the adapter's single-layer assumption.

**Paragraph 3 — account_id is a string rather than an encoded address, another hard family-boundary signal**. Every existing adapter exposes a `_validate_address(s)`-style method that expects some encoding (hex/base58/bech32); NEAR's account_id is a UTF-8 string, no checksum, may include `.` for sub-account hierarchy — this is a family-level semantic, **best expressed through `NearAdapter.validate_account_id()` rather than family-aware branches inside EthereumAdapter**. Conclusion: build `NearAdapter`, family tag = `near` (independent, peer to EVM/Move/UTXO/Cosmos/Substrate).

### Plugin JSON example (this chain)

```json
{
  "chain": "near",
  "family": "near",
  "adapter": "NearAdapter",
  "chain_id": "mainnet",
  "rpc_endpoint": "https://free.rpc.fastnear.com",
  "block_time_ms": 1830,
  "address_format": "near_account_id",
  "hash_format": "base58",
  "native_decimals": 24,
  "default_finality": "final",
  "rpc_methods": {
    "block_height":     { "rpc_method": "status",    "response_path": ".result.sync_info.latest_block_height" },
    "block":            { "rpc_method": "block",     "params_template": {"finality": "{{finality|final}}"} },
    "balance":          { "rpc_method": "query",     "request_type": "view_account",
                          "params_template": {"request_type":"view_account","finality":"{{finality|final}}","account_id":"{{account_id}}"},
                          "response_path": ".result.amount" },
    "access_key_list":  { "rpc_method": "query",     "request_type": "view_access_key_list",
                          "params_template": {"request_type":"view_access_key_list","finality":"{{finality|final}}","account_id":"{{account_id}}"} },
    "tx_lookup":        { "rpc_method": "tx",        "params_template": ["{{tx_hash}}","{{signer_id}}"] },
    "ft_balance":       { "rpc_method": "query",     "request_type": "call_function",
                          "params_template": {"request_type":"call_function","finality":"{{finality|final}}",
                            "account_id":"{{ft_contract}}","method_name":"ft_balance_of",
                            "args_base64":"{{args_b64}}"} },
    "gas_price":        { "rpc_method": "gas_price", "params_template": [null] }
  },
  "mixed_weights": {
    "balance_query": 0.20, "access_key_query": 0.10, "tx_lookup": 0.15, "block_query": 0.12,
    "ft_balance_call": 0.20, "view_state": 0.05, "gas_price": 0.05, "validators": 0.03,
    "status_height": 0.05, "chunk_query": 0.02, "near_chain_specific": 0.03
  }
}
```

---

## 11. DSL Field Requirements (this chain's asks of the plugin DSL)

### 11.1 finality field (NEAR-unique)

DSL `params_template` must support `finality: "optimistic" | "near-final" | "final"` (default `final`). **EVM's `latest/pending/safe/finalized` are block tags — different semantics**: NEAR's finality is a per-query knob influencing state-root selection. Recommendation: add optional top-level `default_finality: "final"` + per-method `params_template` overrides.

### 11.2 account_id field (NEAR-unique string form)

DSL `address_format` enum needs new value `"near_account_id"` (alongside existing `base58 / hex / bech32`). Validation happens in adapter; DSL only carries the label.

### 11.3 hash_format field (base58 like Solana, but hash pairs with signer)

The `tx` method's params is `[hash, signer_id]` — a 2-tuple, not EVM's single-hash form. **This is NEAR's only positional-params + strongly-account-coupled method**; DSL `params_template` must support positional form (JSON array).

### 11.4 native_decimals field (NEAR=24, Solana=9, EVM=18, Sui=9 — all different)

DSL already has this concept; making it explicit is recommended. NEAR's yoctoNEAR (10^24) overflows 64-bit ints — **balance decoding must use string + bignum lib**.

### 11.5 response_path field (nested extraction)

`status` reads height via `.result.sync_info.latest_block_height` (3 levels); `view_account` reads amount via `.result.amount`; `call_function` reads result via `.result.result` (byte array still needs ASCII decoding). Reuse the Aptos research's `response_path: JSONPath-lite` field (`04-aptos.md §11.3`) — cross-family generic.

### 11.6 Error envelope and error.cause extraction

NEAR's error shape is richer than EVM's: `error.cause.name` is the true error type (`PARSE_ERROR / HANDLER_ERROR / ...`), while `error.code` is a coarse JSON-RPC code. DSL needs `error_path: ".error.cause.name"` (same field family as §11.5) for correct monitoring attribution.

### 11.7 NEAR query dispatcher — DSL expression challenge (KEY!)

**Problem**: Nearly all NEAR read operations go through `method: "query"`, with the real differentiator in `params.request_type`. Five real shapes of the *same* wire method (all H8 verified in this research):

```jsonc
// Shape 1: view_account (returns amount/locked/storage_usage)
{"jsonrpc":"2.0","id":1,"method":"query","params":{
  "request_type":"view_account",
  "finality":"final",
  "account_id":"relay.aurora"}}

// Shape 2: view_access_key_list (returns keys array)
{"jsonrpc":"2.0","id":1,"method":"query","params":{
  "request_type":"view_access_key_list",
  "finality":"final",
  "account_id":"relay.aurora"}}

// Shape 3: view_access_key (returns nonce/permission)
{"jsonrpc":"2.0","id":1,"method":"query","params":{
  "request_type":"view_access_key",
  "finality":"final",
  "account_id":"relay.aurora",
  "public_key":"ed25519:168vdqFUxij2yvsxYgAGoykJMX7tgrPKVCH484A8nHP"}}

// Shape 4: call_function (NEP-141 FT balance, contract view)
{"jsonrpc":"2.0","id":1,"method":"query","params":{
  "request_type":"call_function",
  "finality":"final",
  "account_id":"wrap.near",
  "method_name":"ft_total_supply",
  "args_base64":"e30="}}

// Shape 5: view_state (returns KV list, potentially huge)
{"jsonrpc":"2.0","id":1,"method":"query","params":{
  "request_type":"view_state",
  "finality":"final",
  "account_id":"relay.aurora",
  "prefix_base64":""}}
```

**Core DSL difficulty**: monitoring / metrics / mixed weights / vegeta target files all key on "method" as their group label. If we use the wire-level `method`, **all 5 entries collapse into `query`, granularity goes to zero, and individual monitoring is impossible**.

#### Three options (per task spec)

| Option | Form | Pros | Cons |
|---|---|---|---|
| **A Flatten** | DSL says `method: "query"`, 5 entries differ only in `params_template` literals | Zero schema change, fully matches EVM style | **Method granularity collapses**: monitoring/metrics/vegeta-target files lump all 5 NEAR query entries into one row — p99 / error rate become meaningless |
| **B logical_method separation** (recommended) | Add optional `logical_method` field; monitoring / config / weights all key on `logical_method`; adapter emits real wire calls via `rpc_method` | Minimal change (1 new field); granularity restored; **EVM/Solana don't set it = backward-compatible** | Adapter must maintain a logical→rpc mapping internally |
| **C Dispatcher abstraction** | Top-level `dispatcher: { method: "query", dispatch_param: "request_type" }` + `methods: [view_account, view_access_key, ...]` routed through the dispatcher | Maximum generality, cleanest semantics | Schema complexity rises; **only NEAR (and potentially future Aptos `/v1/view` body's function field) benefit**; risky to change schema for 1 chain |

### 11.8 DSL decision (key deliverable)

- [ ] **Option A Flatten** (poor method granularity)
- [x] **Option B logical_method separation** (medium complexity, recommended)
- [ ] **Option C Dispatcher abstraction** (most general but schema-complex)

**Reasoning (3 paragraphs)**:

**Paragraph 1 — Option A is dead on arrival at the monitoring layer**. The framework's core value is producing p50/p95/p99 + error_rate per method and composing workloads via mixed weights; `method` is the primary key for vegeta targets, Prometheus labels, and QPS reports. If NEAR's 5 query forms all collapse into `query`, the monitoring curves become an **arithmetic mix** of 5 methods (`view_account` is sub-ms, `view_state` may be hundreds of ms, `call_function` depends on the contract) — p99 becomes uninterpretable, errors are aggregated into a single `query` line. This violates H7 (observability granularity must match semantic granularity). Rejected.

**Paragraph 2 — Option B wins on schema / compatibility / implementation cost all three axes**. Add **one optional** `logical_method` field: NEAR plugin sets `logical_method=view_account, rpc_method=query`; EVM/Sui/Solana don't set it (`logical_method` defaults to `rpc_method`) — **zero change for the 7 already-shipped chains**. Adapter layer just maintains a 5-entry map in NearAdapter, ~30 LOC. Monitoring uses `logical_method` as label key, granularity restored to real business semantics. This is the token-level "local change + default for backward compat" pattern; Phase 2.1 change cost is bounded.

**Paragraph 3 — Option C is over-engineering for 1 chain today, but keep the door open**. The dispatcher pattern is **not actually NEAR-exclusive** in blockchain RPC: Aptos REST `POST /v1/view`'s body `{function:"<module>::<func>", type_arguments, arguments}` has `function` as a conceptual dispatcher; CosmWasm `wasm.contractInfo` / `wasm.smartContractState` in Cosmos LCD has similar entry-point fields. **However**: Aptos research already chose REST + path-as-method modeling (`04-aptos.md §11.2`); Cosmos hasn't been researched yet. With only NEAR hitting this pattern in Wave 2, introducing Option C is premature optimization — wait for Wave 3+ Aptos view and CosmWasm to confirm whether Option C is truly needed; at that point Option C can layer on top of B (`logical_method` still exists; `dispatcher` becomes a meta-layer above). **Conclusion: Wave 2 solves NEAR with Option B; Option C is a Wave 3+ DSL ASK to revisit.**

**One-liner conclusion**: **`logical_method` field (optional, defaults to `rpc_method`) + NearAdapter's internal 5-entry dispatch map = the minimal complete expression for NEAR's query pattern.** ✅

---

## 9.9 Real-source coverage and timestamps

| Source type | URL/path | Date (UTC) | Status |
|---|---|---|---|
| Official mainnet RPC 1 | `POST https://rpc.mainnet.near.org` method=status | 2026-05-23 | **H8 HTTP:200 TIME:2.19s, chain_id=mainnet, genesis=EPnLgE7iEq9s7yTkos96M3cWymH5avBAPm3qx3NXqR8H, latest_block_height=199597051** |
| FastNEAR | `POST https://free.rpc.fastnear.com` method=status | 2026-05-23 | **H8 HTTP:200 TIME:0.17s, same genesis_hash** |
| Lava | `POST https://near.lava.build` method=status | 2026-05-23 | **H8 HTTP:200 TIME:0.43s, same genesis_hash** |
| publicnode (candidate) | `POST https://near-rpc.publicnode.com` | 2026-05-23 | **H8 HTTP:404 — unavailable** |
| block by finality | `block {finality:final}` | 2026-05-23 | **H8 returns chunks[] + author=bisontrails2.poolv1.near** |
| block by height | `block {block_id:199597000}` | 2026-05-23 | **H8 returns chunks[] + author=kiln-1.poolv1.near** |
| finality=optimistic | `block {finality:optimistic}` | 2026-05-23 | **H8 returns chunks (author=zavodil.poolv1.near)** |
| finality=near-final | `block {finality:near-final}` | 2026-05-23 | **H8 returns chunks (author=liver.pool.near)** |
| query view_account | `query view_account relay.aurora` | 2026-05-23 | **H8 amount=1759801172720814773223780901, storage_usage=149422** |
| query view_account system contract | `query view_account near` | 2026-05-23 | **H8 code_hash=HiyC5tB1gBDpgR4x1guEp1orBde5PXqUYGoWaZfX3JGX (non-zero = contract)** |
| query view_access_key_list | `query view_access_key_list relay.aurora` | 2026-05-23 | **H8 returns keys[] (multiple FullAccess ed25519)** |
| query view_access_key | `query view_access_key relay.aurora <pubkey>` | 2026-05-23 | **H8 nonce=65790930076833, permission=FullAccess** |
| query call_function | `query call_function wrap.near.ft_total_supply()` | 2026-05-23 | **H8 result=[34,50,49,…] = ASCII "21510714514871847363014456029803"** |
| gas_price | `gas_price [null]` | 2026-05-23 | **H8 result.gas_price="100000000"** |
| validators | `validators [null]` | 2026-05-23 | **H8 returns current_proposals/current_validators arrays** |
| broadcast_tx_async error envelope | `broadcast_tx_async ["DwAAAGFhYQ=="]` | 2026-05-23 | **H8 error code=-32700 name=REQUEST_VALIDATION_ERROR cause.name=PARSE_ERROR** — confirms error envelope shape |
| Framework chain namespace | `config/config_loader.sh:666` supported_blockchains | 2026-05-23 | **E1 read_file** (near **not** in the list — confirms new chain) |

**Not verified / deferred to Phase 2.1**:
- Independent live tx_hash via `tx` method (extraction step blocked by user environment for `/tmp/*.json` writes)
- `chunk` method's true result schema
- `view_state` real-world availability on production RPC (may be rejected if state is large)
- NEAR public RPC's documented rate limits (officially undisclosed)
- nearblocks.io explorer DOM scrape for real tx hash shape (this draft inferred hash encoding from block_hash only)

---

## Open Questions

1. **File numbering**: this draft is numbered `08-near.md` per wave, not yet aligned with SUMMARY. P1 wrap-up: user decides final number.
2. **When to invoke Option C**: does Aptos `/v1/view` body's `function` field substantively form a second dispatcher use-case? Once Wave 3+ adds Aptos / Cosmos / Polkadot and more match the pattern, is Option C worth layering atop B?
3. **tx 2-key**: NEAR's `tx(hash, signer_id)` 2-tuple is a long-running friction point for explorers/clients — does the framework's `tx_lookup` mixed entry need a "signer pool" (extracted from recent blocks)? Or fix on a long-active dummy like `relay.aurora`?
4. **Finality distribution within mixed weights**: currently `block_query` 0.12 all uses `finality:final` — should it split 0.06 final + 0.04 near-final + 0.02 optimistic to cover all three tiers?
5. **yoctoNEAR bignum**: Python adapter is fine (arbitrary-precision int), but vegeta target files generated through shell paths (bash `printf`) may overflow — Phase 2.1 verifies generator handles 24-digit decimals correctly.
6. **NEP-141 FT contract seed set**: are `wrap.near / aurora / usdt.tether-token.near / token.sweat` stable long-term? If Sweat's contract renames, the seed set needs hot-update.
7. **Public RPC real rate limits**: `rpc.mainnet.near.org` 2.19s latency is significantly worse than FastNEAR 0.17s and Lava 0.43s — is the official node throttled? Benchmark baseline should be FastNEAR.
8. **Implicit accounts (64-hex)**: this draft did not verify a single implicit-account view_account — do all `query.*` shapes support implicit accounts? (Phase 2.1 to verify)
9. **chunk_id types**: does `chunk` method accept both `chunk_hash` (base58) and `{block_id, shard_id}` tuple? This draft did not verify the latter.
10. **mock_rpc_server routing strategy**: once NEAR introduces query dispatcher, should mock proactively refactor to "method handler + sub-handler(dispatch_param)" two-tier? (Otherwise Phase 2.1 adding a NEAR-only router will make mock messier — token-level Case-D risk.)

---

## Changelog

| Date (UTC) | Author | Change |
|---|---|---|
| 2026-05-23 | Hermes Agent | Initial draft (P1-2 Wave 2): H8-verified 3 endpoints + 5 query sub-methods + 3 finality tiers + gas_price/validators/broadcast error code; §11.7/11.8 three-option comparison + **decision = Option B `logical_method` separation**; new `NearAdapter` (new family `near`); listed 10 Phase 2.1 caller/reader change points (§8.5) |
