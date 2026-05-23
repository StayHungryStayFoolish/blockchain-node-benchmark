# <NN>-<chain-name> Research

> **This file is derived from `_template.md`, one per chain.**
> **Filling rule H8 (real evidence): curl test + official doc URL + access date.**

---

## Metadata

| Field | Value |
|---|---|
| Chain (EN) | <e.g. Solana> |
| Chain (ZH) | <e.g. Solana> |
| Number | <01-28> |
| Mainnet ChainID | <e.g. 101 / 1 / 56> |
| Research Date | YYYY-MM-DD |
| Researcher | Hermes Agent |
| Status | 🟡 In Progress / 🟢 Done / 🔴 Blocked |

---

## 1. Sources (authoritative)

| Type | URL | Access Date | Notes |
|---|---|---|---|
| Official Docs | https://... | YYYY-MM-DD | Protocol spec homepage |
| RPC Spec | https://... | YYYY-MM-DD | JSON-RPC or REST interface docs |
| GitHub | https://github.com/... | YYYY-MM-DD | Client source |
| Explorer | https://... | YYYY-MM-DD | Block explorer (for address/tx samples) |

---

## 2. Protocol Family

| Field | Value |
|---|---|
| Family | <Solana / EVM / Bitcoin / Move / Cosmos-SDK / Substrate / Tendermint / Other> |
| Consensus | <PoH+PoS / PoW / PoS / DPoS / BFT> |
| VM | <SVM / EVM / MoveVM / WASM / None (UTXO)> |
| Block Time | <seconds, e.g. 0.4s> |
| Finality | <slot/block, e.g. 32 slots ≈ 12.8s> |
| Reuse Existing Adapter? | <Yes (name which) / No (new family, needs new adapter)> |

---

## 3. Public RPC

| Endpoint | Auth | Rate Limit | Notes |
|---|---|---|---|
| https://... | None / API key | <req/s or req/day> | Suitable for mock substitute? |
| https://... | None / API key | ... | ... |

**curl test** (REQUIRED, proves RPC is alive):
```bash
curl -s -X POST https://api.mainnet-beta.solana.com \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"getSlot"}'
# Actual output:
# {"jsonrpc":"2.0","result":<real slot>,"id":1}
```

---

## 4. Account Model

| Field | Value |
|---|---|
| Model | UTXO / Account / Hybrid |
| Native token decimals | <e.g. 9 (lamports)> |
| Address derivation | <Ed25519 / secp256k1 / Sr25519 / Other> |
| Special account types | <e.g. PDA (Solana) / Smart Contract / Native Token Account> |

---

## 5. Core RPC Methods (for this framework)

> Only list methods THIS benchmark framework needs. See official docs for full API.

| Method | Category | Notes | Mixed weight (suggested) |
|---|---|---|---|
| `getSlot` / `eth_blockNumber` / ... | block height | Health + height sync check | 0.05 |
| `getBlock` / `eth_getBlockByNumber` / ... | block content | Heavyweight, includes tx detail | 0.10 |
| `getTransaction` / `eth_getTransactionByHash` / ... | tx lookup | Signature query | 0.20 |
| `getBalance` / `eth_getBalance` / ... | balance | Account balance | 0.25 |
| `getTokenAccountBalance` / `eth_call(balanceOf)` / ... | token balance | ERC20/SPL token | 0.20 |
| ... | ... | ... | ... |

**Total weight MUST = 1.0**

---

## 6. Address Format

| Field | Value |
|---|---|
| Encoding | Base58 / Hex (0x prefix) / Bech32 / Bech32m / Base32 |
| Length | <e.g. 32-44 chars (Base58) / 42 chars (Hex)> |
| Checksum | Yes (algorithm) / No |
| Example (real mainnet) | `<real address, verifiable on explorer>` |
| Validation regex | `^[1-9A-HJ-NP-Za-km-z]{32,44}$` |

---

## 7. Signature Lookup (sig / tx hash)

| Field | Value |
|---|---|
| Hash format | Base58 / Hex (0x prefix) |
| Length | <char count> |
| Example (real mainnet tx) | `<real tx hash>` |
| Lookup method | `getTransaction(<sig>)` |
| Explorer URL format | `https://.../tx/<hash>` |

---

## 8. Mixed Set (`mixed` mode weights)

> Used when `BLOCKCHAIN_NODE_BENCHMARK_MODE=mixed`

```json
{
  "balance_query": 0.25,
  "tx_lookup": 0.20,
  "block_query": 0.10,
  "token_balance": 0.20,
  "<chain-specific>": 0.25
}
```

**Weights MUST sum to 1.0**. The chain-specific block must list concrete methods.

---

## 8.5 Phase 2.1 caller/reader change points (token-level Gate 3)

**MANDATORY**: each chain research must list Phase 2.1 implementation caller/reader change checklist to avoid caller-blind during Phase 2.1 plugin refactor (refer to `token-level-careful-edit` skill Case-B/D).

| # | Location (file:line) | Change | Reason (why this caller needs sync change) |
|---|---|---|---|
| 1 | `config/config_loader.sh:<L?>` this chain `rpc_methods.mixed` | <list added/removed methods> | Directly consumed by vegeta target generator |
| 2 | `config/config_loader.sh:<L?>` this chain `param_formats` | <list new/removed methods with param formats> | `generate_rpc_json` falls back to default if field missing |
| 3 | `tools/mock_rpc_server.py:<L?>` method branch | <list mock cases needing addition> | mock_rpc_server is fallback target; without this, mock mode breaks with new config |
| 4 | `tools/fetch_active_accounts.py:<L?>` adapter impl | <list adapter methods needing add/change> | This chain's SolanaAdapter / EthereumAdapter / ... needs extension? |
| 5 | `analysis-notes/baseline-current-state.md` (grep this chain name) | <sync chain list update> | Doc truth alignment, prevent v1.4.1-style doc-vs-code drift |
| 6 | `analysis-notes/disk-and-network-pipeline-redesign.md` (grep this chain name) | <sync> | Same as above |
| 7 | `analysis-notes/research_notes/<related chain note>.md` | <if has deprecated annotations, upgrade to removed/replaced> | Research notes reflect reality |
| 8 | `tests/<this chain related tests>.sh` or `.py` | <if has method/field assertions, sync> | L1/L2 unit tests may hardcode old method names |

**If this chain is a new chain (no existing code)**, #1-3 still must be filled (need addition in plugin JSON + mock), #4-8 mark N/A as appropriate.

**Test requirement**: After Phase 2.1 completes, must run `core/master_qps_executor.sh --mixed --duration 30` (or shortest e2e_smoke) to capture vegeta error rate. **All requests should be 200**, as E2 evidence of this chain's refactor.

---

## 9. Mock Notes (mock_rpc_server impl)

- **Request path**: `<e.g. POST / or POST /jsonrpc>`
- **Response schema** (must paste a real mainnet response as sample):
  ```json
  {"jsonrpc":"2.0","result":<real data>,"id":1}
  ```
- **Special error codes** (if any):
  - `-32602`: Invalid params
  - `<chain-specific>`: ...
- **Mock implementation complexity**: Low / Medium / High (state why)

---

## 10. Adapter Reuse Decision

### Candidates

| Adapter | Compatibility | Missing capabilities |
|---|---|---|
| EthereumAdapter | <e.g. 60%> | <e.g. lacks SPL token support> |
| SolanaAdapter | <e.g. 0%> | <account model totally different> |
| BitcoinAdapter | <e.g. 0%> | <UTXO model not applicable> |

### Decision

- [ ] **Reuse** `<adapter name>` (specify)
- [ ] **New** `<adapter name>` (state family)
- [ ] **Hybrid** (state partial reuse + partial new, e.g. Tron dual-API)

### Rationale

<2-3 paragraphs>

### JSON config example (this chain)

```json
{
  "chain": "<chain-name>",
  "family": "<family>",
  "adapter": "<AdapterClass>",
  "chain_id": <id>,
  "rpc_endpoint": "https://...",
  "block_time_ms": <ms>,
  "address_format": "base58 / hex / bech32",
  "rpc_methods": {
    "block_height": "<method>",
    "balance": "<method>",
    "tx_lookup": "<method>"
  },
  "mixed_weights": {
    "balance_query": 0.25,
    "tx_lookup": 0.20,
    "block_query": 0.10,
    "token_balance": 0.20,
    "chain_specific": 0.25
  }
}
```

---

## Open Questions

- [ ] <e.g. Does Avalanche P-Chain's X endpoint support batch queries?>
- [ ] <e.g. Does Tron `/wallet/getaccount` need ABI decoding?>

---

## Changelog

| Date | Author | Change |
|---|---|---|
| YYYY-MM-DD | Hermes Agent | Initial research |
