# 01-solana Research

> First chain research, serves as the template demonstration for 28 chains. **Real evidence H8 strictly enforced.**

---

## Metadata

| Field | Value |
|---|---|
| Chain (EN) | Solana |
| Chain (ZH) | Solana |
| Number | 01 |
| Mainnet ChainID | `mainnet-beta` (no numeric chain_id, uses network name) |
| Genesis Hash | `5eykt4UsFv8P8NJdTREpY1vzqKqZKvdpKuc147dw2N9d` |
| Research Date | 2026-05-23 |
| Researcher | Hermes Agent |
| Status | 🟢 Done |

---

## 1. Sources (authoritative)

| Type | URL | Access Date | Notes |
|---|---|---|---|
| Official Docs | https://solana.com/docs | 2026-05-23 | Protocol spec homepage |
| RPC Spec | https://solana.com/docs/rpc | 2026-05-23 | Full JSON-RPC HTTP/WS reference |
| RPC Method List | https://solana.com/docs/rpc/http | 2026-05-23 | All HTTP methods |
| GitHub (Agave client) | https://github.com/anza-xyz/agave | 2026-05-23 | Mainstream validator client (Solana Foundation fork) |
| GitHub (legacy solana) | https://github.com/solana-labs/solana | 2026-05-23 | Historical repo, archived |
| Explorer | https://explorer.solana.com | 2026-05-23 | Block/account/tx explorer |
| Solscan | https://solscan.io | 2026-05-23 | Alt explorer, better token info search |

---

## 2. Protocol Family

| Field | Value |
|---|---|
| Family | **Solana** (independent family, not shared with EVM/Bitcoin/Move) |
| Consensus | **PoH (Proof of History) + TowerBFT (PoS-based BFT)** |
| VM | **SVM** (Sealevel, parallel BPF/sBPF bytecode execution) |
| Block Time | ~400ms (target slot time) |
| Finality | 32 slots (~12.8s) to reach finalized state |
| Reuse Existing Adapter? | **No, use SolanaAdapter** (sole member of this family) |

---

## 3. Public RPC

| Endpoint | Auth | Rate Limit | Notes |
|---|---|---|---|
| `https://api.mainnet-beta.solana.com` | none | not officially published, estimated < 10 req/s | Solana Foundation official public node, **not for production, research / mock fallback only** |
| `https://api.devnet.solana.com` | none | same | Devnet |
| `https://api.testnet.solana.com` | none | same | Testnet |
| `https://solana-rpc.publicnode.com` | none | medium | Allnodes community node |

**Source coverage**:

| Method | Source count | Notes |
|---|---|---|
| `getRecentBlockhash` | **2 sources (dual-source)** | mainnet-beta + publicnode both return `-32601`, deprecation fact reliable |
| Other 7 methods | **1 source (single-source)** | mainnet-beta only; numeric fields (slot/blockHeight/balance) are time-sensitive |

> ⚠️ AP3 reminder: single-source measurement insufficient to determine industry-wide behavior. From Phase 1.2 onward, if cross-node behavior differences are found for critical methods, add publicnode etc. dual-source re-verification.

**curl real measurements** (2026-05-23 ~02:14 UTC actually executed; numeric fields are time-sensitive, **re-running will yield different values**):

```bash
# getSlot — current slot
$ curl -s -X POST https://api.mainnet-beta.solana.com \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"getSlot"}'
{"jsonrpc":"2.0","result":421541028,"id":1}

# getBlockHeight — current block height
$ curl -s -X POST https://api.mainnet-beta.solana.com \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"getBlockHeight"}'
{"jsonrpc":"2.0","result":399629216,"id":1}

# getBalance — WSOL wrapped address balance
$ curl -s -X POST https://api.mainnet-beta.solana.com \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"getBalance","params":["So11111111111111111111111111111111111111112"]}'
{"jsonrpc":"2.0","result":{"context":{"apiVersion":"4.0.0","slot":421541035},"value":1512828393160},"id":1}
# Decoded: 1512.828393160 SOL (lamports / 1e9)

# getVersion
$ curl -s ... -d '{"method":"getVersion"}'
{"jsonrpc":"2.0","result":{"feature-set":3718597879,"solana-core":"4.0.0"},"id":1}

# getHealth — health check
$ curl -s ... -d '{"method":"getHealth"}'
{"jsonrpc":"2.0","result":"ok","id":1}

# getSignaturesForAddress — real signature query (core method of this framework)
$ curl -s ... -d '{"method":"getSignaturesForAddress","params":["So11111111111111111111111111111111111111112",{"limit":2}]}'
{"jsonrpc":"2.0","result":[
  {"blockTime":1779501907,"confirmationStatus":"finalized","signature":"2JenZjSJhZiVrAqBsJKQjyVt6pcjfHgdpcFNguqNURAJHLuas5Ezx519fYrLvxgBxs92TjUoaieMa1JmnfCVKsRb","slot":421541075,"transactionIndex":1081,...},
  {"blockTime":1779501907,"confirmationStatus":"finalized","signature":"2WhoAaN2DZaF52R8xkWE3Uk14rxpUqPTYnnQjbpGmYSTk8Tm3bpwxfYHEpCmqGRbGX29z5RnSdYpaxWU8zJz3vBG","slot":421541075,...}
],"id":1}
```

---

## 4. Account Model

| Field | Value |
|---|---|
| Model | **Account model** (not UTXO); all data lives in Accounts |
| Native token decimals | **9** (1 SOL = 1,000,000,000 lamports) |
| Address derivation | **Ed25519** public key (32 bytes) |
| Special account types | **PDA** (Program Derived Address, no private key), **SPL Token Account** (derived by Token Program), **Program Account** (deployed contract) |
| System accounts (in this framework config) | `11111111111111111111111111111111` (System Program)<br>`TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA` (SPL Token Program)<br>`ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL` (Associated Token Program)<br>`metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s` (Metaplex Token Metadata)<br>`SysvarRent111111111111111111111111111111111` (Sysvar Rent)<br>`ComputeBudget111111111111111111111111111111` (Compute Budget Program) |

**Current `target_address` in config**: `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v` (USDC mint account, one of the most active accounts on Solana, very high daily tx volume)

---

## 5. Core RPC Methods (for this framework)

| Method | Category | Notes | Mixed weight (suggested) | Current state |
|---|---|---|---|---|
| `getSlot` | block height | Current slot | 0.05 | ❌ Not enabled (should add) |
| `getBlockHeight` | block height | Current finalized block height | 0.05 | ✅ In mixed |
| `getHealth` | health | Node health check | 0.05 | ❌ Not enabled |
| `getBalance` | balance | Account native SOL balance | 0.20 | ✅ In mixed |
| `getAccountInfo` | account | Full account info (data/owner/lamports) | 0.20 | ✅ In mixed (single+mixed) |
| `getTokenAccountBalance` | token balance | SPL Token balance | 0.20 | ✅ In mixed |
| `getSignaturesForAddress` | sig list | Address signature list (core of adapter `_single_request`) | 0.05 | ✅ In `methods.get_signatures` |
| `getTransaction` | tx detail | Single tx detail | 0.10 | ✅ In `methods.get_transaction` |
| `getLatestBlockhash` | blockhash | Latest blockhash (replaces deprecated getRecentBlockhash) | 0.10 | ❌ **Currently uses deprecated `getRecentBlockhash`, must fix** |

**Total weight**: 0.05+0.05+0.05+0.20+0.20+0.20+0.05+0.10+0.10 = **1.00** ✅

---

## 6. Address Format

| Field | Value |
|---|---|
| Encoding | **Base58** (no 0x prefix) |
| Length | **32-44 chars** (typically 43-44) |
| Checksum | No separate checksum (Base58 encoding has implicit error detection) |
| Example (real mainnet) | `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v` (USDC mint, 44 chars) |
| Example (short address) | `11111111111111111111111111111111` (System Program, 32 chars, all 1s) |
| Validation regex | `^[1-9A-HJ-NP-Za-km-z]{32,44}$` |

---

## 7. Signature Lookup (sig / tx hash)

| Field | Value |
|---|---|
| Hash format | **Base58** (no prefix) |
| Length | **87-88 chars** (64-byte Ed25519 signature → Base58) |
| Example (real mainnet tx) | `2JenZjSJhZiVrAqBsJKQjyVt6pcjfHgdpcFNguqNURAJHLuas5Ezx519fYrLvxgBxs92TjUoaieMa1JmnfCVKsRb` (2026-05-23 finalized) |
| Lookup method | `getTransaction(signature, {"encoding":"jsonParsed","maxSupportedTransactionVersion":0})` |
| Explorer URL | `https://explorer.solana.com/tx/<signature>` |

⚠️ **maxSupportedTransactionVersion is required**: framework code already passes it (`fetch_active_accounts.py:265`); otherwise versioned tx (v0) parsing errors out.

---

## 8. Mixed Set (`mixed` mode weights)

> **⚠️ Internal schema warning**: §8, §5, §10 each list **different weight schemas**. Phase 2.1 implementation must unify on §10's "real method name as key" form (consumed directly by `config_loader.sh` reader). §5/§8 are design sketches — **§10 is authoritative**.

Abstract method grouping (for reader comprehension, **NOT directly consumed by config_loader**):

```json
{
  "balance_query": 0.20,
  "account_info": 0.20,
  "token_balance": 0.20,
  "block_height": 0.10,
  "blockhash": 0.10,
  "sig_lookup": 0.10,
  "health_and_slot": 0.10
}
```

Specific method mapping:
- `balance_query` → `getBalance`
- `account_info` → `getAccountInfo`
- `token_balance` → `getTokenAccountBalance`
- `block_height` → `getBlockHeight`
- `blockhash` → `getLatestBlockhash` (**no longer getRecentBlockhash**)
- `sig_lookup` → `getSignaturesForAddress` + `getTransaction` (2-stage)
- `health_and_slot` → `getHealth` + `getSlot` round-robin

**Weights sum = 1.00 ✅**

### Phase 2.1 caller/reader change points (MUST READ)

When fixing `getRecentBlockhash` → `getLatestBlockhash`, **all of the following points must be changed in sync** (token-level Gate 3, to avoid caller-blind):

| # | Location | Change | Reason |
|---|------|------|------|
| 1 | `config/config_loader.sh:430` mixed string | Remove `getRecentBlockhash`, add `getLatestBlockhash` | Directly consumed by vegeta |
| 2 | `config/config_loader.sh:436` param_formats | Remove `"getRecentBlockhash": "no_params"`, add `"getLatestBlockhash": "no_params"` | `generate_rpc_json` falls back to default if field missing; new method must be explicitly listed |
| 3 | `tools/mock_rpc_server.py:137` `if method == "getRecentBlockhash"` | Add `getLatestBlockhash` branch (may keep old branch returning deprecated error to simulate real node) | mock_rpc_server is fallback target; without this, mock mode breaks with new config |
| 4 | `analysis-notes/baseline-current-state.md:193` chain list | Sync remove old method | Doc truth alignment, prevent v1.4.1-style doc-vs-code drift |
| 5 | `analysis-notes/disk-and-network-pipeline-redesign.md:216` | Sync | Same as above |
| 6 | `REFACTOR-SSOT.md §5.1(资源画像, 原02已合并删):33` | Upgrade `(deprecated)` annotation to `(removed from framework, replaced by getLatestBlockhash)` | Research notes reflect reality |

**Test requirement**: After Phase 2.1 completes, must run `core/master_qps_executor.sh --mixed --duration 30` (or shortest e2e_smoke) to capture vegeta error rate. **All requests should be 200, no `-32601`**, as E2 evidence of this bug fix.

---

## 9. Mock Notes (mock_rpc_server impl)

- **Request path**: `POST /` (single JSON-RPC endpoint)
- **Response schema samples** (real mainnet):
  ```json
  {"jsonrpc":"2.0","result":421541028,"id":1}
  {"jsonrpc":"2.0","result":{"context":{"apiVersion":"4.0.0","slot":421541035},"value":1512828393160},"id":1}
  {"jsonrpc":"2.0","error":{"code":-32601,"message":"Method not found"},"id":1}
  ```
- **Special error codes**:
  - `-32601`: Method not found (e.g. `getRecentBlockhash`)
  - `-32602`: Invalid params (common, e.g. malformed signature)
  - `-32603`: Internal error
- **Mock impl complexity**: **Medium**
  - Simple methods (getSlot/getBlockHeight/getHealth): return single value/string, **Low**
  - getBalance/getAccountInfo: needs `context+value` nested struct, **Medium**
  - getSignaturesForAddress: needs array (fixture-providable), **Medium**
  - getTransaction: deep nesting (message/accountKeys/instructions), **High** — recommend fixture-based: dump a few real mainnet txs and reuse

---

## 10. Adapter Reuse Decision

### Candidates

| Adapter | Compatibility | Missing capabilities |
|---|---|---|
| SolanaAdapter | **100%** | — |
| EthereumAdapter | 0% | Completely different account model, no logs/topics concept |
| Other | 0% | — |

### Decision

- [x] **Reuse** `SolanaAdapter` (existing, no new build)
- [ ] New
- [ ] Hybrid

### Rationale

Solana is the sole representative of its family (no other chain uses SVM + PoH). SolanaAdapter is already fully implemented at `tools/fetch_active_accounts.py:248-284` (3 methods: `_single_request` / `fetch_transaction` / `extract_accounts_from_transaction`). This refactor **only needs to extract it to `adapters/solana.py`** and add `getLatestBlockhash` to replace the deprecated `getRecentBlockhash`.

### Interface contract placeholder (fill after Phase 2.0 design)

> ⚠️ Currently does not list `BlockchainAdapter` base class (`tools/fetch_active_accounts.py:156-245`) interface contract requirements for plugins. Phase 2.0 plugin framework design phase must add:
>
> - [ ] List all method signatures plugin adapter must implement
> - [ ] List methods already implemented in base class (avoid subclass duplication)
> - [ ] List plugin JSON config → adapter instantiation field mapping
> - [ ] List minimum adapter test fixture set (each adapter needs at least N real mainnet txs)
>
> After Phase 2.0 design completes, backfill this section. All 28 chain research will reuse the same interface contract.

### JSON config example (this chain)

```json
{
  "chain": "solana",
  "family": "solana",
  "adapter": "SolanaAdapter",
  "network": "mainnet-beta",
  "rpc_endpoint": "LOCAL_RPC_URL",
  "block_time_ms": 400,
  "finality_slots": 32,
  "address_format": {
    "encoding": "base58",
    "length_min": 32,
    "length_max": 44,
    "regex": "^[1-9A-HJ-NP-Za-km-z]{32,44}$"
  },
  "native_decimals": 9,
  "rpc_methods": {
    "block_height": "getBlockHeight",
    "balance": "getBalance",
    "tx_lookup": "getTransaction",
    "sig_list": "getSignaturesForAddress",
    "token_balance": "getTokenAccountBalance",
    "account_info": "getAccountInfo",
    "blockhash": "getLatestBlockhash",
    "health": "getHealth",
    "slot": "getSlot"
  },
  "param_formats": {
    "getAccountInfo": "single_address",
    "getBalance": "single_address",
    "getTokenAccountBalance": "single_address",
    "getLatestBlockhash": "no_params",
    "getBlockHeight": "no_params",
    "getHealth": "no_params",
    "getSlot": "no_params"
  },
  "mixed_weights": {
    "getBalance": 0.20,
    "getAccountInfo": 0.20,
    "getTokenAccountBalance": 0.20,
    "getBlockHeight": 0.10,
    "getLatestBlockhash": 0.10,
    "getSignaturesForAddress": 0.05,
    "getTransaction": 0.05,
    "getHealth": 0.05,
    "getSlot": 0.05
  },
  "system_addresses": [
    "11111111111111111111111111111111",
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",
    "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s",
    "SysvarRent111111111111111111111111111111111",
    "ComputeBudget111111111111111111111111111111"
  ],
  "default_target_address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
  "tx_lookup_params": {
    "encoding": "jsonParsed",
    "maxSupportedTransactionVersion": 0
  }
}
```

---

## Open Questions

- [x] ⚠️ **`getRecentBlockhash` has been deprecated by Solana** (real test returns `-32601 Method not found`), dual-source verified (`api.mainnet-beta.solana.com` + `solana-rpc.publicnode.com` both return the same error).
  - **This deprecation was already documented**: `REFACTOR-SSOT.md §5.1(资源画像, 原02已合并删):33` already noted `getRecentBlockhash (deprecated) | Memory | <1ms | replaced by getLatestBlockhash`.
  - **However**, `config/config_loader.sh:430` mixed list still contains this method uncleaned, `config_loader.sh:436` param_formats also still keeps the entry.
  - **Call chain verified**: `config_loader.sh:430` → `target_generator.sh:184/300-306` (reads `CURRENT_RPC_METHODS_ARRAY` looping over each account × method) → `generate_rpc_json` → vegeta targets file → vegeta actually sends to mainnet.
  - **Failure rate estimate (E5 SPECULATED, not measured)**: mixed mode 5 methods equal weight → **theoretically ~20% of requests** will return `-32601`. **Vegeta not actually run**; real failure rate depends on vegeta default success criteria (HTTP 200 + JSON `error` field counts as 200-class success in vegeta defaults) and other factors, may differ from theory. Phase 2.1 acceptance must measure to confirm.
  - **Official deprecation E1-verified** (https://solana.com/docs/rpc/deprecated/getrecentblockhash): verbatim "*This method is expected to be removed in `solana-core` v2.0. Please use getLatestBlockhash instead.*" Measured `getVersion` on public node returns `solana-core 4.0.0` (>>v2.0), i.e. removal promise has taken effect, public nodes confirmed return `-32601`.
  - **Must fix in this plugin refactor** (no-deferred-bugs): mixed list replaces `getRecentBlockhash` with `getLatestBlockhash`, param_formats also syncs add `"getLatestBlockhash": "no_params"`, old entries removed.
- [ ] Does mock_rpc_server need complex versioned tx (v0) handling? SolanaAdapter already passes `maxSupportedTransactionVersion=0`; mock should support it too.
- [ ] Need to support `getProgramAccounts`? Framework doesn't use it currently, but if exchanges want to test contract-level monitoring it may be needed.

---

## Changelog

| Date | Author | Change |
|---|---|---|
| 2026-05-23 | Hermes Agent | Initial research, tested 8 methods, discovered `getRecentBlockhash` deprecation bug |
| 2026-05-23 | Hermes Agent | Self-audit v1 token-level fixes for 7 issues: tone downgrade (archive already noted), §8 added caller/reader change table, §3 added source coverage + timestamp, §10 line number correction (L248-285→L248-284), §10 added interface contract placeholder, §8 added schema inconsistency warning |
