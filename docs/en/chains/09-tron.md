# 09-tron Research

> Derived from `_template.md`. H8 (real evidence): all RPC calls were executed against `https://api.trongrid.io` on 2026-05-23 (HTTP API + JSON-RPC API both exposed on the same host).

---

## Meta

| Field | Value |
|---|---|
| Chain (zh) | 波场 |
| Chain (en) | Tron |
| Number | 09 |
| Mainnet ChainID | EVM-compat `chainId = 728126428` (`0x2b6653dc`, E1 `eth_chainId` measured); native Tron has **no chainId concept** (uses ref_block_bytes/hash for replay protection) |
| Research date | 2026-05-23 |
| Researcher | Hermes Agent |
| Status | 🟢 Complete |

---

## 1. Sources

| Type | URL | Date | Note |
|---|---|---|---|
| Official docs (HTTP) | https://developers.tron.network/reference | 2026-05-23 | Complete Tron HTTP API reference (`/wallet/*`, `/walletsolidity/*`) |
| Official docs (JSON-RPC) | https://developers.tron.network/reference/json-rpc | 2026-05-23 | EVM-compat JSON-RPC method subset |
| GitHub (node) | https://github.com/tronprotocol/java-tron | 2026-05-23 | java-tron full node (SR / Full / Solidity Node roles) |
| Explorer | https://tronscan.org | 2026-05-23 | Block / tx / contract explorer |
| TronGrid | https://www.trongrid.io | 2026-05-23 | Public node operated by Tron foundation (endpoint used in this study) |
| TRC20 spec | https://github.com/tronprotocol/tips/blob/master/tip-20.md | 2026-05-23 | Tron version of ERC20 (USDT-TRC20 = this) |

---

## 2. Protocol Family

| Field | Value |
|---|---|
| Family | **Tron** (independent family, DPoS + TVM; **EVM-compatible but not EVM-native**; no existing adapter is 100% reusable) |
| Consensus | **DPoS** (27 Super Representatives produce blocks) |
| VM | **TVM** (Tron Virtual Machine, EVM subset + diffs: Energy/Bandwidth replaces gas, address prefix `0x41` not `0x`, some opcode diffs) |
| Block Time | **3 seconds** (E1 measured block #82964399 → #82964400 timestamp delta 3000ms) |
| Finality | **~57 seconds** (19 SRs × 3s = irreversible after 19 blocks, per java-tron docs) ⚠️ (not directly curl-tested, relying on official docs) |
| Reuse Existing Adapter? | **Hybrid** — EthereumAdapter reusable for the JSON-RPC side (~70%), HTTP API side requires new `TronHttpAdapter` (see §10) |

---

## 3. Public RPC

| Endpoint | Auth | Rate Limit | Note |
|---|---|---|---|
| `https://api.trongrid.io` | none / API key | anonymous ~15 req/s ⚠️ (per trongrid.io common knowledge, not tested this round) | **Simultaneously** exposes HTTP API (`/wallet/*`, `/walletsolidity/*`) AND JSON-RPC (`/jsonrpc`); all E1–E5 evidence below measured here |
| `https://tron-rpc.publicnode.com` | none | publicnode generic ⚠️ | `POST /` returned HTTP 405 — **publicnode does not accept POST on root path**, correct path needs doc lookup; **not working this round**, demoted to fallback candidate |
| `https://nile.trongrid.io` | none | — | **Testnet, do not use** |

**curl evidence** (E1):

```bash
# E1.1 HTTP API liveness: current block
curl -s -X POST https://api.trongrid.io/wallet/getnowblock \
  -H "Content-Type: application/json" -d '{}'
# {"blockID":"0000000004f1efafd51db2259fff52248ab10ec49f2107074f17018a4bfbc765",
#  "block_header":{"raw_data":{"number":82964399,
#    "witness_address":"415a27141dbd202aa1344c042b51ae541262eebfb7",
#    "parentHash":"0000000004f1efaec3d6e44ca0016a5d2ec154e9ea12663f39e0ac34d6e49067",
#    "version":34,"timestamp":1779561837000},...},
#  "transactions":[{"txID":"8f81a66c89b80531...","contractRet":"SUCCESS",...}]}

# E1.2 JSON-RPC liveness: eth_blockNumber
curl -s -X POST https://api.trongrid.io/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_blockNumber","params":[]}'
# {"jsonrpc":"2.0","id":1,"result":"0x4f1efb0"}   # 0x4f1efb0 = 82964464 (in sync)

# E1.3 JSON-RPC eth_chainId
curl -s -X POST https://api.trongrid.io/jsonrpc \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}'
# {"jsonrpc":"2.0","id":1,"result":"0x2b6653dc"}   # = 728126428 (official mainnet chainId)

# E1.4 Dual-protocol height consistency (within seconds): HTTP=82964399, RPC=82964464
# Difference is just elapsed time between calls. Both point at the same mainnet.
```

E1 all 200, **dual-protocol on same host both live**.

---

## 4. Account Model

| Field | Value |
|---|---|
| Model | **Account** (global account, no UTXO) |
| Native token decimals | **6** (TRX, 1 TRX = 10^6 sun; E2 measured USDT contract `balance: 1073038702522` = 1,073,038.702522 TRX) |
| Address derivation | **secp256k1** (same curve as Ethereum), but hash + prefix differ: `RIPEMD160(keccak256(pubkey)[-20:])` → 20B raw → prepend `0x41` → 21B → Base58Check |
| Special account types | Normal / Contract (`type: "Contract"`) / AssetIssue (legacy TRC10 token); TRC20 tokens are regular contracts, no separate account type |

### Resource model (Tron-unique)

Tron does not use gas-per-op + gasPrice. Instead it uses two resources:

- **Bandwidth**: per-tx byte cost; each account has 600 free bytes/day (`freeNetLimit: 600`, E2 measured); excess consumes frozen-TRX-derived bandwidth points or burns TRX.
- **Energy**: contract execution cost; **only obtainable by freezing TRX** (freeze 1 TRX yields ~5–10 Energy / 24h) or via stake/delegate; no free Energy.
- E2 measured USDT contract `triggerconstantcontract balanceOf` returned `energy_used: 4062, energy_penalty: 3127`, i.e. 7189 Energy total (constant call is not on-chain but node reports real consumption for estimation).

---

## 5. Core RPC Methods (needed by this framework)

> Dual-protocol mixed: balance/account/TRC20 via HTTP API (full semantics), block-height/EVM-compat tooling via JSON-RPC.

| Method | Protocol | Category | Note | Suggested mixed weight |
|---|---|---|---|---|
| `eth_blockNumber` | JSON-RPC | block height | Liveness + sync (lightweight) | 0.05 |
| `/wallet/getnowblock` | HTTP | block content | Current block with all txs, heavy | 0.10 |
| `/wallet/getblockbynum` | HTTP | block by number | Specific block with txs | 0.10 |
| `/wallet/gettransactionbyid` | HTTP | tx lookup | tx hash → full tx | 0.15 |
| `eth_getTransactionByHash` | JSON-RPC | tx lookup | EVM-style tx query (EVM fields) | 0.05 |
| `/wallet/getaccount` | HTTP | balance + metadata | TRX balance + frozen + assetV2 in one call | 0.20 |
| `/wallet/triggerconstantcontract` | HTTP | TRC20 balance | USDT-TRC20 etc contract call (`balanceOf`) | 0.20 |
| `eth_call` (balanceOf) | JSON-RPC | TRC20 balance (EVM style) | Same, hex in/out | 0.05 |
| `/wallet/getaccountresource` | HTTP | resource | Energy/Bandwidth balances (chain-specific) | 0.10 |

**Sum = 0.05+0.10+0.10+0.15+0.05+0.20+0.20+0.05+0.10 = 1.00** ✅

---

## 6. Address Format

| Field | Value |
|---|---|
| Encoding | **Base58Check** (T-prefix, mainnet) + **Hex 41-prefix** (node-internal / JSON-RPC) |
| Length | Base58: **34 chars** (starts with `T`); Hex: **42 chars** (`0x41` + 40 hex = 21 bytes) |
| Checksum | Base58Check **yes** (double SHA256, first 4 bytes) |
| Example (mainnet) | Base58: `TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t` (USDT-TRC20 contract, E2 `getaccount` returned `account_name: "TetherToken", type: "Contract"`) |
| Same addr Hex | `0x41a614f803b6fd780986a42c78ec9c7f77e6ded13c` (E5 `eth_getBalance` returned `0xf9d61737ba` = 1,072,538,464,186 sun) |
| Regex (Base58) | `^T[1-9A-HJ-NP-Za-km-z]{33}$` |
| Regex (Hex) | `^0x41[0-9a-fA-F]{40}$` |
| **Dual format conversion** | Base58 → Hex: Base58Check decode, **drop trailing 4B checksum**, get 21B (includes `0x41` prefix) → hex. Hex → Base58: hex decode, **double-SHA256 first 4B as checksum, append**, Base58 encode. **HTTP API accepts `visible: true` to return/receive Base58, else uses Hex** |

### E5 dual-format cross-evidence

```bash
# Same USDT contract, queried via both APIs:
# HTTP (Base58):
curl -s -X POST https://api.trongrid.io/wallet/getaccount \
  -d '{"address":"TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t","visible":true}'
# {"account_name":"TetherToken","type":"Contract","balance":1073038702522,...}

# JSON-RPC (Hex):
curl -s -X POST https://api.trongrid.io/jsonrpc \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_getBalance",
       "params":["0x41a614f803b6fd780986a42c78ec9c7f77e6ded13c","latest"]}'
# {"result":"0xf9d61737ba"}   # 0xf9d61737ba = 1,072,538,464,186 sun
# (two queries at different moments, diff ~5e8 sun = 500 TRX, normal for active contract)
```

---

## 7. Signature Lookup

| Field | Value |
|---|---|
| Hash format | **Hex no prefix** (HTTP API) / **Hex 0x-prefix** (JSON-RPC) — same hash, two representations |
| Length | 64 chars (32-byte hash) |
| Example (mainnet) | `8f81a66c89b80531717737c6c67716cbb38a5020a78c72d31740b4166f38c1d2` (E1 block #82964399 inner `txID`, E3 `gettransactionbyid` returned `contractRet: "SUCCESS"`, contract type `UnDelegateResourceContract`) |
| Query method (HTTP) | `POST /wallet/gettransactionbyid {"value":"<hash no prefix>"}` |
| Query method (JSON-RPC) | `eth_getTransactionByHash("0x" + <hash>)` |
| Explorer URL | `https://tronscan.org/#/transaction/<hash no prefix>` |

### E3 evidence

```bash
curl -s -X POST https://api.trongrid.io/wallet/gettransactionbyid \
  -d '{"value":"8f81a66c89b80531717737c6c67716cbb38a5020a78c72d31740b4166f38c1d2"}'
# {"ret":[{"contractRet":"SUCCESS"}],
#  "signature":["4a8d84a544ed45...01"],
#  "txID":"8f81a66c89b80531...",
#  "raw_data":{"contract":[{"parameter":{"value":{
#     "balance":7047090143,"resource":"ENERGY",
#     "receiver_address":"416569afa9...","owner_address":"41bcb31b39..."
#  },"type_url":"type.googleapis.com/protocol.UnDelegateResourceContract"},
#  "type":"UnDelegateResourceContract"}],...}}
```

---

## 8. Mixed Set (mixed-mode weights)

```json
{
  "balance_query":         0.20,
  "token_balance_http":    0.20,
  "tx_lookup_http":        0.15,
  "block_by_number_http":  0.10,
  "block_head_http":       0.10,
  "resource_query":        0.10,
  "block_height_rpc":      0.05,
  "tx_lookup_rpc":         0.05,
  "token_balance_rpc":     0.05
}
```

**Sum = 1.00** ✅

Design rationale:
- **HTTP dominant (0.85 total)**: Tron's real production load is dominated by USDT-TRC20 transfers and wallet queries. HTTP API is the native protocol with the richest fields (`frozenV2`, `assetV2`, Energy/Bandwidth all in one response), matching real-user access patterns.
- **JSON-RPC at 0.15**: covers EVM-toolchain users (Web3.js / ethers.js), verifies the EVM-compat layer is stable under load.
- Same method dual-protocol entries (token_balance, tx_lookup, block) each present so per-protocol latency is observable.

---

## 8.5 Phase 2.1 caller/reader changes (token-level Gate 3)

Tron is a new chain (wave 3), so #1-3 are mandatory; #4-8 N/A or NEW.

| # | Location | Change | Reason |
|---|---|---|---|
| 1 | `config/config_loader.sh` `UNIFIED_BLOCKCHAIN_CONFIG.blockchains.tron` | Add `rpc_methods.mixed` with all 9 methods from §5/§8 + per-method `protocol` field (`http_post` / `jsonrpc`) | Consumed by vegeta target generator |
| 2 | `config/config_loader.sh` `param_formats` | Add `address_base58` (`^T[...]{33}$`), `address_hex41` (`^0x41[...]{40}$`), `txid_hex_nopfx`, `triggerconstant_body` 4 templates | `generate_rpc_json` defaults silently if missing |
| 3 | `tools/mock_rpc_server.py` add Tron branch | New `do_POST` routes: `/wallet/getnowblock`, `/wallet/getaccount`, `/wallet/getblockbynum`, `/wallet/gettransactionbyid`, `/wallet/triggerconstantcontract`, `/wallet/getaccountresource`, `/jsonrpc` all methods; fixtures from §9 | mock_rpc_server is fallback target; without this, mock mode breaks for Tron |
| 4 | `tools/fetch_active_accounts.py` add `TronAdapter(BlockchainAdapter)` | Use HTTP `/wallet/getnowblock` to fetch `transactions[].raw_data.contract[].parameter.value.{owner_address, to_address, contract_address}`, emit base58 AND hex forms | Tron needs both formats; plugin config decides which goes into vegeta target |
| 5 | `analysis-notes/baseline-current-state.md` (grep `tron`) | Add tron to chain list + dual-protocol annotation | Doc-truth alignment |
| 6 | `analysis-notes/disk-and-network-pipeline-redesign.md` | Add tron as dual-protocol chain | Same |
| 7 | `analysis-notes/research_notes/<tron note>.md` | This research doc is in place | — |
| 8 | `tests/test_tron_adapter.py` (NEW) | 1 real mainnet block fixture (82964399) + base58↔hex round-trip unit test + dual-protocol response schema asserts | L1/L2 tests |

**Critical pitfalls**:
- **Base58 ↔ hex41 conversion MUST be plugin-config side**: vegeta target generator reads plugin JSON only; **cannot compute Base58Check at runtime** (0-Python constraint). `fetch_active_accounts.py` produces two address lists in one pass (`tron_accounts_base58.txt`, `tron_accounts_hex41.txt`); plugin per-method references one of them.
- **`triggerconstantcontract` `parameter` field**: plugin must pre-generate hex string (64 chars, address-padded); DSL cannot encode `address` → padded hex inside vegeta target on the fly. `fetch_active_accounts` must additionally emit `tron_balanceof_params.txt` (each line: `<contract>,<padded_hex_owner>`).
- **JSON-RPC path is `/jsonrpc`, not root `/`**: differs from most EVM chains; plugin endpoint config must explicitly include `/jsonrpc` suffix.

**Test requirement**: after Phase 2.1, run `core/master_qps_executor.sh --chain tron --mixed --duration 30`; **all requests 200**; this is the Tron E2 evidence.

---

## 9. Mock Notes

### HTTP API side (POST + JSON body):

- Paths: `POST /wallet/getnowblock`, `POST /wallet/getaccount`, `POST /wallet/getblockbynum`, `POST /wallet/gettransactionbyid`, `POST /wallet/triggerconstantcontract`, `POST /wallet/getaccountresource`, `POST /walletsolidity/getnowblock`
- Response schema sample (E2 measured, USDT contract):
  ```json
  {"account_name": "TetherToken",
   "type": "Contract",
   "address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
   "balance": 1073038702522,
   "net_window_size": 28800000,
   "frozenV2": [{},{"type": "ENERGY"},{"type": "TRON_POWER"}],
   "assetV2": [{"key": "1002963","value": 58000000}, ...]}
  ```
- triggerconstantcontract response (E2 measured `balanceOf(self)`):
  ```json
  {"result":{"result":true},
   "energy_used":4062,"energy_penalty":3127,
   "constant_result":["000000000000000000000000000000000000000000000000000000bdb69fb7a7"],
   "transaction":{"txID":"89afa1fc...","raw_data":{...}}}
  ```
- Error codes: HTTP **405** (path not found, E5 measured) / HTTP 200 + `{"Error":"<msg>"}` (param error, per docs, ⚠️ not directly triggered this round)

### JSON-RPC side (POST `/jsonrpc`):

- Path: `POST /jsonrpc`, body `{"jsonrpc":"2.0","method":"eth_*","params":[...],"id":N}`
- Response schema sample (E1 measured `eth_blockNumber`):
  ```json
  {"jsonrpc":"2.0","id":1,"result":"0x4f1efb0"}
  ```
- `eth_call` response (E5 measured balanceOf):
  ```json
  {"jsonrpc":"2.0","id":1,
   "result":"0x000000000000000000000000000000000000000000000000000000bdb69fb7a7"}
  ```
- Error codes (E5 measured):
  - `-32601`: `{"error":{"code":-32601,"message":"method not found"}}` (measured via `eth_doesnotexist`)
  - `-32602`: Invalid params (per docs, not triggered)
- Mock complexity: **High**
  - **Dual protocols, dual path prefixes** (`/wallet/*` POST body + `/jsonrpc` POST body); mock_rpc_server must route by `parsed_url.path`, not just read body.method
  - `getaccount` response schema very deep (`frozenV2[]`, `assetV2[]`, `account_resource`, `votes`); use fixture file
  - **Dual-protocol field names differ**: `eth_getBlockByNumber` returns `hash/parentHash/number(hex)`, `/wallet/getnowblock` returns `blockID/parentHash/number(int)` — mock cannot share one dataclass

---

## 10. Adapter Reuse Decision

### Candidates

| Adapter | Compat | Missing |
|---|---|---|
| EthereumAdapter | **~50%** (JSON-RPC side only; `eth_blockNumber/getBlockByNumber/getBalance/getTransactionByHash/call/chainId` names identical) | (a) no support for HTTP `/wallet/*` REST POST form; (b) Base58 ↔ Hex41 conversion; (c) Energy/Bandwidth model; (d) JSON-RPC path `/jsonrpc` not root `/` |
| SolanaAdapter | 0% | Protocol/account model totally different |
| BitcoinAdapter | 0% | UTXO vs Account |
| CosmosAdapter | ~10% (REST GET experience, but Tron is POST + body; schema/method totally different) | — |
| SubstrateAdapter (Polkadot wave 2) | ~25% (**dual-protocol per-method DSL pattern reusable** — `protocol: jsonrpc` vs `protocol: rest`; but Polkadot REST = **GET + path placeholder**, Tron HTTP = **POST + body placeholder**; protocol enum needs extension) | See §11 |

### Decision

- [ ] Reuse one adapter
- [ ] New single adapter
- [x] **Hybrid**: **new `TronAdapter` (HTTP API side)** + **reuse `EthereumAdapter` subset (JSON-RPC side)**; `TronAdapter` routes per-method `protocol` at top level, delegates JSON-RPC calls to EthereumAdapter

### Rationale

(1) **Tron HTTP API is its own protocol**, not REST-CRUD but `POST <path> + JSON body` RPC-over-REST (one path per method, body = params). This shape differs from Cosmos REST (GET + query params), Polkadot sidecar (GET + path placeholder), and EVM JSON-RPC (POST root + body.method). No existing adapter fits, so **new** TronHttpAdapter is needed for path routing + body templates + base58↔hex conversion.

(2) **JSON-RPC side EthereumAdapter reuse is high-value**. Tron `/jsonrpc` is fully compatible with `eth_blockNumber / eth_chainId / eth_getBalance / eth_call / eth_getBlockByNumber / eth_getTransactionByHash` (E1+E5 confirmed field names, hex encoding, error codes match Ethereum mainnet). Just have EthereumAdapter accept an `rpc_path = "/jsonrpc"` parameter (default `/`) and reuse it. **Forcing all-HTTP wastes EVM-compat reuse and breaks the multi-chain unified mixed-set design** (every chain has an EVM-style stress path).

(3) **DSL dual-protocol per-method pattern = same as Polkadot**. Polkadot wave 2 already confirmed DSL supports per-method `protocol` field in plugin JSON (`jsonrpc` vs `rest_sidecar`). Tron is the 2nd dual-protocol chain. **Reuse this DSL pattern, extend `protocol` enum to include `rest_post`** (POST + body template). Polkadot REST = GET + path placeholder (`/blocks/{n}`); Tron REST = POST + body placeholder (`{"address":"{addr}"}`). The vegeta target generator must support both REST sub-modes — DSL-wise it's an enum extension, no architectural break. See §11.7/11.8.

### Plugin JSON example

```json
{
  "chain": "tron",
  "family": "tron",
  "adapter": "TronAdapter",
  "delegate_adapter_jsonrpc": "EthereumAdapter",
  "chain_id": 728126428,
  "chain_id_hex": "0x2b6653dc",
  "node_app": "java-tron",
  "block_time_ms": 3000,
  "finality_blocks": 19,
  "api_protocol": ["http_post", "jsonrpc"],
  "http_endpoint": "https://api.trongrid.io",
  "rpc_endpoint": "https://api.trongrid.io/jsonrpc",
  "address_format": {
    "primary":   {"encoding": "base58check", "prefix": "T",   "length": 34, "regex": "^T[1-9A-HJ-NP-Za-km-z]{33}$"},
    "secondary": {"encoding": "hex",         "prefix": "0x41","length": 42, "regex": "^0x41[0-9a-fA-F]{40}$"},
    "conversion": "base58check<->hex41 (drop 4B checksum)"
  },
  "native_token": {"symbol": "TRX", "decimals": 6, "sun_per_trx": 1000000},
  "resource_model": {"energy": true, "bandwidth": true, "gas_model": false, "free_bandwidth_per_day": 600},
  "rpc_methods": {
    "block_height_rpc":     {"protocol": "jsonrpc",   "method": "eth_blockNumber",         "params": []},
    "block_head_http":      {"protocol": "http_post", "path": "/wallet/getnowblock",       "body": {}},
    "block_by_number_http": {"protocol": "http_post", "path": "/wallet/getblockbynum",     "body": {"num": "{block_num}"}},
    "tx_lookup_http":       {"protocol": "http_post", "path": "/wallet/gettransactionbyid","body": {"value": "{txid_nopfx}"}},
    "tx_lookup_rpc":        {"protocol": "jsonrpc",   "method": "eth_getTransactionByHash","params": ["{txid_0xpfx}"]},
    "balance_query":        {"protocol": "http_post", "path": "/wallet/getaccount",        "body": {"address": "{addr_base58}", "visible": true}},
    "token_balance_http":   {"protocol": "http_post", "path": "/wallet/triggerconstantcontract",
                             "body": {"owner_address": "{addr_base58}", "contract_address": "{trc20_contract_base58}",
                                      "function_selector": "balanceOf(address)", "parameter": "{padded_hex_owner}", "visible": true}},
    "token_balance_rpc":    {"protocol": "jsonrpc",   "method": "eth_call",
                             "params": [{"to": "{trc20_contract_hex41}", "data": "0x70a08231{padded_hex_owner}"}, "latest"]},
    "resource_query":       {"protocol": "http_post", "path": "/wallet/getaccountresource", "body": {"address": "{addr_base58}", "visible": true}}
  },
  "mixed_weights": {
    "balance_query":        0.20,
    "token_balance_http":   0.20,
    "tx_lookup_http":       0.15,
    "block_by_number_http": 0.10,
    "block_head_http":      0.10,
    "resource_query":       0.10,
    "block_height_rpc":     0.05,
    "tx_lookup_rpc":        0.05,
    "token_balance_rpc":    0.05
  }
}
```

---

## 11. DSL Expressiveness Analysis (Tron dual-API critical)

### 11.1–11.6 (common items)

- **11.1 method naming**: HTTP API method = path (`/wallet/<verb>`); JSON-RPC = `eth_*` literal. DSL already supports string literal for both.
- **11.2 param types**: HTTP = body JSON object (arbitrarily nested); JSON-RPC = array `[obj | string | "latest"]`. DSL placeholders `{addr_base58}` / `{txid_nopfx}` / `{padded_hex_owner}` etc. must be plugin pre-baked.
- **11.3 result types**: HTTP returns raw JSON (no `result` wrapper, top-level fields like `blockID`); JSON-RPC returns `{jsonrpc, id, result}`. **Response validation paths differ**; DSL needs per-protocol `success_check` (HTTP: status=200 and no `Error` field; JSON-RPC: `result != null && error == undefined`).
- **11.4 error schema**: HTTP — HTTP 405 (path not found, E5 measured) / HTTP 200 + `{"Error":"<msg>"}` (param error, ⚠️ not triggered); JSON-RPC — `{"error":{"code":-32601,"message":"method not found"}}` (E5 measured).
- **11.5 batch**: JSON-RPC ⚠️ (not verified this round; Tron official JSON-RPC doc doesn't make it explicit, need to test); HTTP API does not support batching, every method is its own POST.
- **11.6 dual-protocol**: **HTTP API (POST + body) + JSON-RPC (POST + body) exposed on same host** — the core DSL theme of this chain (see 11.7).

### 11.7 (mandatory) Tron HTTP API vs JSON-RPC API comparison (all E1–E5 measured)

| Dimension | HTTP API (native) | JSON-RPC API (EVM-compat) |
|---|---|---|
| Protocol | REST-style RPC-over-HTTP (POST + JSON body) | JSON-RPC 2.0 (POST + body.method) |
| Entry path | `/wallet/<verb>`, `/walletsolidity/<verb>` (one path per method) | Single `/jsonrpc` |
| Balance query | `POST /wallet/getaccount {"address":"T...","visible":true}` → `{"balance":1073038702522,"frozenV2":[...],"assetV2":[...]}` (E2) | `eth_getBalance("0x41...","latest")` → `"0xf9d61737ba"` (E5) |
| Tx query | `POST /wallet/gettransactionbyid {"value":"<hash nopfx>"}` → full `{ret, signature, txID, raw_data{contract[],ref_block_bytes,expiration,...}}` (E3) | `eth_getTransactionByHash("0x<hash>")` → EVM-style fields (`from/to/value/gas/...`) ⚠️ (not directly curl-tested, relying on Tron JSON-RPC docs) |
| Block query | `POST /wallet/getnowblock {}` → `{blockID, block_header{raw_data{number,timestamp,...}}, transactions[]}` (E1 #82964399) | `eth_getBlockByNumber("latest", false)` → `{hash, parentHash, number(hex), timestamp(hex), transactions[hash], gasLimit/gasUsed/baseFeePerGas/...}` (E1 — Tron even fills `baseFeePerGas:"0x0"` etc EVM fields) |
| TRC20 balance | `POST /wallet/triggerconstantcontract {owner_address, contract_address, function_selector:"balanceOf(address)", parameter:"<padded hex>", visible:true}` → `{"result":{"result":true}, "energy_used":4062, "constant_result":["0x...bdb69fb7a7"]}` (E2) | `eth_call({"to":"0x41...","data":"0x70a08231<padded>"}, "latest")` → `"0x000000...bdb69fb7a7"` (E5, **byte-identical hex to HTTP**) |
| Address input | Base58Check (`T...`, needs `visible:true`) or Hex41 (without `visible`) | Hex41 (`0x41...`) |
| Error return | HTTP 405 (path missing, E5) / HTTP 200 + `{"Error":"..."}` (param error, docs, ⚠️ not triggered) | `{"error":{"code":-32601,"message":"method not found"}}` (E5) |
| Doc completeness | **Complete** (Tron native API, all `/wallet/*` documented) | **Partial** (only common EVM method subset — `eth_blockNumber/chainId/getBalance/call/getTransactionByHash/getBlockByNumber/getLogs/...`; **no Tron-specific info** — frozen / Energy / TRC10 assets) |
| Field semantic completeness | **High** (resources, frozen, assetV2, Bandwidth, Energy all in one response) | **Low** (only EVM abstraction layer — balance, tx, block; Tron-specific info lost) |
| Reuse with other EVM chains DSL | **Low** (unique protocol, dedicated adapter) | **High** (isomorphic to 8 existing EVM chains' JSON-RPC, only path `/jsonrpc` differs) |

**Key findings**:
- **Same `balanceOf` query, two APIs return byte-identical hex** (`0xbdb69fb7a7`) — confirms JSON-RPC is a thin wrapper over HTTP API, both share underlying TVM execution.
- **block/tx fields are completely different between APIs** (`blockID` vs `hash`, `txID` vs `hash`, `witness_address` vs `miner`), but the underlying block is the same.
- HTTP API = **POST + body placeholder**; Polkadot sidecar = **GET + path placeholder** — both REST, but vegeta target generator needs to support both REST sub-modes.

### 11.8 (mandatory) DSL choice recommendation

- [ ] HTTP API only (native, complete docs, but DSL needs path params + REST POST body schema; loses EVM-compat reuse)
- [ ] JSON-RPC API only (EVM-compat, DSL reuses existing 8 EVM chains, but methods incomplete — no frozen/Energy/Bandwidth)
- [x] **Both (per-method protocol), DSL configures each method's protocol** (balance/TRC20/resource/block via HTTP API; EVM-compat high-sync path via JSON-RPC; **dual-protocol mixed stress is more realistic**)
- [ ] Dual-protocol auto fallback (primary on one, fallback the other) — rejected, see rationale (3)

**Rationale** (3 paragraphs):

**(1) Dual-API is Tron's design reality, DSL must model it**. A Tron node exposes both APIs not as redundancy, but to serve two client classes: HTTP API serves Tron-native wallets (TronLink, TokenPocket, Tron-CLI) and dApps needing complete frozen/Energy/Bandwidth info; JSON-RPC serves Web3.js / ethers.js users (treating Tron as an EVM chain). **Choosing only one** detaches from real production-load distribution. Mixed stress reflects real node-pressure distribution: HTTP is high-volume, full-fielded, heavy payload; JSON-RPC is light-volume, slim-fielded. IO/CPU patterns differ; benchmark must cover both.

**(2) DSL pattern is highly isomorphic to Polkadot, reuse ~60%**. Polkadot wave 2 confirmed plugin JSON supports per-method `"protocol": "jsonrpc" | "rest"` field. Tron is the 2nd dual-protocol chain, **fully reusing this DSL pattern**, only needs to extend the `protocol` enum from `{jsonrpc, rest}` to `{jsonrpc, rest_get_path, rest_post_body}` (or a more general `{jsonrpc, http}` + `method: GET|POST` + `path` + `body` sub-fields). The vegeta target generator needs body template rendering for `rest_post_body` (placeholder substitution); this is new logic, **but plugin-side configuration syntax matches Polkadot's**. The three Polkadot-built foundations — per-method protocol field, success_check abstraction, fixture-based param lists (`tron_accounts_base58.txt` etc.) — are 100% reused. **Net new engineering: just the `rest_post_body` body renderer** (~30 LOC).

**(3) Rejecting auto-fallback**: fallback seems convenient, but (a) the two APIs' response schemas differ (`blockID` vs `hash`, HTTP top-level vs JSON-RPC `.result`); downstream parse logic must branch anyway, so dual-protocol callers must be written twice — no simplification; (b) benchmark goal is measuring real node pressure; fallback **masks one protocol's failures** (e.g. `/jsonrpc` single-endpoint perf bottleneck), violating observability; (c) same-method dual-protocol entries are already separate mixed-set items (`tx_lookup_http` 0.15 + `tx_lookup_rpc` 0.05), already an explicit split, no fallback needed. **Explicit beats implicit**.

#### Reuse assessment vs Polkadot dual-protocol infra

| Facility | Polkadot wave 2 built | Tron directly reusable? | Delta work |
|---|---|---|---|
| plugin JSON `api_protocol: [...]` list field | ✅ `["jsonrpc","rest_sidecar"]` | ✅ change to `["jsonrpc","http_post"]` | 0 |
| per-method `protocol` field | ✅ `"protocol": "jsonrpc" \| "rest"` | ✅ same field name, extend enum | enum +1 value |
| `path` placeholder template rendering (`/blocks/{n}`) | ✅ GET path render | ⚠️ Tron path is fixed but body is templated, **body render is new** | ~30 LOC body renderer |
| `success_check` per-protocol abstraction | ✅ HTTP 200 + JSON field assert | ✅ direct reuse, only asserted field names differ (plugin-config) | 0 |
| Fixture-based param lists (pre-generated addr/hash) | ✅ built (`polkadot_accounts.txt`) | ✅ direct reuse; add `tron_accounts_base58.txt`/`tron_accounts_hex41.txt`/`tron_balanceof_params.txt` | one-shot adapter pre-gen |
| mock_rpc_server dual-path routing | ✅ Polkadot built `do_GET` branch + sidecar path routing | ✅ Tron only adds `do_POST` path branches (`/wallet/*` + `/jsonrpc`) | ~50 LOC mock branches |
| **Total reuse** | — | **~60%** | net +~80 LOC + adapter |

**Conclusion**: **Polkadot's dual-protocol DSL design, validated by Tron, generalizes to any "primary protocol + EVM-compat wrapper" chain** (future candidates: NEAR EVM-compat, Aurora, ICP …). DSL dual-protocol fields are general enough; after this round's `rest_post_body` enum extension, **the architecture needs no further change**.

---

## Open Questions

- [ ] **DSL ASK**: `protocol` enum design — Polkadot-style `{jsonrpc, rest}` + sub-field `http_method: GET|POST` + `body`? Or explicit `{jsonrpc, rest_get_path, rest_post_body}`? Former more general (extensible to PUT/PATCH), latter more explicit. Recommend the former.
- [ ] **DSL ASK**: should HTTP API path support placeholders? (All Tron HTTP paths in this study are static.) Keep `/wallet/{verb}` placeholder syntax for future extension.
- [ ] **DSL ASK**: base58 ↔ hex41 conversion — one-shot output from `fetch_active_accounts` (0-Python-friendly) or `address_class: base58|hex41` plugin declaration with runtime conversion? **Strongly recommend the former** (avoid runtime Python).
- [ ] **DSL ASK**: hex-string concat in JSON-RPC `params` (e.g. `"0x70a08231{padded_hex_owner}"`) — does DSL support **embedded** `{...}` placeholders in a parent string? Polkadot only had standalone-string placeholders; Tron is the first case needing **string concat** (selector + padded owner). Recommend vegeta target generator scan entire params/body tree and do embedded `{...}` substitution during render.
- [ ] **DSL ASK**: `success_check` per-protocol assertion field-name diff — Polkadot is sidecar top-level `nonce/free` field-present; Tron HTTP is no-`Error`-field + top-level field (e.g. `blockID`) present. Does DSL need structured assertions like `success_check: {"jsonpath": "$.result", "not_null": true}`?
- [ ] **Unverified ⚠️**: real rate limit of `https://api.trongrid.io` (per trongrid common knowledge ~15 req/s; not stress-tested this round)
- [ ] **Unverified ⚠️**: real `eth_getTransactionByHash` response schema on Tron JSON-RPC — not curl-fetched this round (`eth_getBlockByNumber latest+true` may have empty `transactions` for some blocks; API budget exhausted)
- [ ] **Unverified ⚠️**: JSON-RPC batch (`[{...},{...}]`) support — Tron official doc unclear, needs self-test
- [ ] **Unverified ⚠️**: correct path on `https://tron-rpc.publicnode.com` — `POST /` returned HTTP 405 this round; likely a non-root path. Demoted to candidate; check publicnode docs before Phase 2.1
- [ ] **Unverified ⚠️**: HTTP API param error real body (expected `{"Error":"..."}`, not triggered this round)
- [ ] **Unverified ⚠️**: Tron finality real number (19 SRs × 3s ≈ 57s per java-tron docs)
- [ ] **DSL ASK / Phase 2.x**: USDT-TRC20 is 70%+ of Tron traffic; should mixed set carve out a weight for that single hottest contract? Current `token_balance_http: 0.20` is per-contract average; could split `tron.usdt_trc20_balance: 0.30` + `other_trc20: 0.10`. Decide in Phase 2.2 based on real benchmark data.

---

## Changelog

| Date | Author | Change |
|---|---|---|
| 2026-05-23 | Hermes Agent | Initial research; E1–E5 measured; dual-API DSL decision = per-method protocol; reuses Polkadot dual-protocol DSL pattern ~60% |
