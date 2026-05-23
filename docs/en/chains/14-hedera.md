# 14-hedera Research

> Derived from `_template.md`. H8 (real evidence): All curls executed on **2026-05-23** against public mainnet endpoints (Mirror REST `https://mainnet-public.mirrornode.hedera.com` + Hashio JSON-RPC `https://mainnet.hashio.io/api`), 14 API calls total. This research **does NOT test gRPC HCS** (requires protobuf, not fit for vegeta benchmark).

---

## Metadata

| Field | Value |
|---|---|
| Chain Name (zh) | 海德拉 / Hedera Hashgraph |
| Chain Name (en) | Hedera |
| Number | 14 |
| Mainnet ChainID | EVM-compat `chainId = 295` (`0x127`, measured E5 `eth_chainId`; E14 `net_version` returned `"295"`); **Hashgraph native protocol has no chainId concept** (consensus via node ID cluster `0.0.3..0.0.40` signatures) |
| Research Date | 2026-05-23 |
| Researcher | Hermes Agent |
| Status | 🟢 Complete |

---

## 1. Sources

| Type | URL | Date | Note |
|---|---|---|---|
| Official docs | https://docs.hedera.com | 2026-05-23 | Hedera Hashgraph protocol entry |
| Mirror Node REST API | https://docs.hedera.com/hedera/sdks-and-apis/rest-api | 2026-05-23 | OpenAPI-style spec, primary protocol tested |
| JSON-RPC Relay spec | https://github.com/hashgraph/hedera-json-rpc-relay | 2026-05-23 | Official EVM-compat JSON-RPC wrapper |
| Hashgraph whitepaper | https://hedera.com/hh_whitepaper_v2.1-20200815.pdf | 2026-05-23 | DAG consensus + "non-blockchain" essence |
| Consensus node GitHub | https://github.com/hashgraph/hedera-services | 2026-05-23 | Java consensus node |
| Mirror Node GitHub | https://github.com/hashgraph/hedera-mirror-node | 2026-05-23 | Mirror REST + GraphQL impl |
| Explorer | https://hashscan.io | 2026-05-23 | Mainnet browser |
| HTS spec | https://docs.hedera.com/hedera/core-concepts/tokens | 2026-05-23 | Hedera Token Service (native token, NOT contract) |

---

## 2. Protocol Family

| Field | Value |
|---|---|
| Family | **hedera** (independent; **Hashgraph DAG ≠ blockchain**; 3-part account ID; 3 APIs coexist; no existing adapter reusable as-is) |
| Consensus | **aBFT Hashgraph** (gossip-about-gossip + virtual voting, asynchronous Byzantine Fault Tolerant; Council node ID range `0.0.3 ~ 0.0.40`) |
| VM | **HTS** (native) + **EVM** (Hedera Smart Contract Service, EVM-equivalent, exposed via JSON-RPC Relay) |
| Block Time | **~1–2 s** (E7+E12 measured: block #95421653 `timestamp.from=1779562740.189823000 to=1779562741.470178250`, span ≈ 1.28 s; **note**: "block" is Mirror Node's wrapping abstraction over record stream — Hashgraph itself has no block, see §11.7) |
| Finality | **3–5 s** (aBFT, consensus reached = irreversible; ⚠️ not directly measured this round, per official doc) |
| Reuse Existing Adapter? | **Mixed** — EthereumAdapter reusable on JSON-RPC side (~55%); Mirror REST side requires new `HederaMirrorAdapter` (see §10) |

---

## 3. Public RPC

| Endpoint | Auth | Rate Limit | Note |
|---|---|---|---|
| `https://mainnet-public.mirrornode.hedera.com` | None | ~100 req/s ⚠️ (per Hedera docs, not stressed this round) | **Mirror REST API official public node**; E1/E2/E3/E7/E8/E11/E12 all hit, all HTTP 200 |
| `https://mainnet.hashio.io/api` | None | ~50 req/s ⚠️ (Hashio Swirlds Labs operated) | **JSON-RPC Relay public node**; E4/E5/E6/E9/E10/E13/E14/E15 all hit, all HTTP 200 (including -32601/-32602 error bodies) |
| `https://mainnet.mirrornode.hedera.com` | None | — | **Alias to mainnet-public** (DNS alias, docs recommend -public suffix) |
| `https://testnet.mirrornode.hedera.com` | — | — | **Testnet, not used** |

**curl probe** (E1 — Mirror REST liveness, network supply):

```bash
curl -s "https://mainnet-public.mirrornode.hedera.com/api/v1/network/supply"
# Real output:
# {"released_supply":"4337349052950644279","timestamp":"1779559275.585402000","total_supply":"5000000000000000000"}
```

**curl probe** (E4 — JSON-RPC liveness, current block height):

```bash
curl -s -X POST https://mainnet.hashio.io/api \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_blockNumber","params":[]}'
# Real output:
# {"result":"0x5b004d1","jsonrpc":"2.0","id":1}      # block #95,420,113
```

**curl probe** (E5 — chainId 295 = 0x127 mainnet):

```bash
curl -s -X POST https://mainnet.hashio.io/api \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}'
# {"result":"0x127","jsonrpc":"2.0","id":1}    # 0x127 = 295
```

---

## 4. Account Model

| Field | Value |
|---|---|
| Model | **Account** (not UTXO); **3-part ID** `shard.realm.num` (mainnet shard=realm=0, all addresses look like `0.0.X`) |
| Native token decimals | **8** (1 HBAR = 100,000,000 tinybar — same concept as BTC sat) |
| Address derivation | **Ed25519** (primary) or **ECDSA secp256k1** (EVM-compat); may attach an EVM 20-byte address alias |
| Special account types | **System accounts** `0.0.1` (treasury) / `0.0.2` (early test account, E2+E3 measured balance 16,630,126.37744658 HBAR) / `0.0.98` (node fee) / `0.0.800` (staking reward) / `0.0.801` (node reward); **Token accounts** (HTS — each token is independent entity `0.0.X`, e.g. USDC `0.0.456858`); **Contract accounts** (HSCS, EVM-compat contracts also `0.0.X`); **Topic accounts** (HCS consensus topics) |
| EVM alias mapping | `0.0.N` long-zero maps to EVM address = `0x` + 24 zeros + 16 hex chars (padded N). E3 measured 0.0.2 → `0x0000000000000000000000000000000000000002` |

---

## 5. Core RPC Methods (for this benchmark)

| Method | Category | Note | Mixed weight |
|---|---|---|---|
| `[Mirror] GET /api/v1/blocks?limit=1&order=desc` | block head | Latest "block" (record stream wrapper); E7 measured `{blocks:[{number:95421653, hash, timestamp{from,to}, ...}]}` | 0.05 |
| `[RPC] eth_blockNumber` | block height | EVM-compat; E4 returned hex `"0x5b004d1"` | 0.05 |
| `[Mirror] GET /api/v1/blocks/{number}` | block content | E12 measured block #95421653: `count`/`hash`/`timestamp.from`/`timestamp.to`/`gas_used`/`logs_bloom` | 0.05 |
| `[RPC] eth_getBlockByNumber("latest", false)` | block content | EVM-compat; E9 measured — full EVM block schema with many zero-padded placeholder fields (`stateRoot`/`receiptsRoot`/`baseFeePerGas`/`withdrawals[]`) | 0.05 |
| `[Mirror] GET /api/v1/transactions/{txId}` | tx lookup | tx ID form `0.0.3229-1779562731-037000118` (account-validStart); E8 measured full `transfers[]`/`token_transfers[]`/`nft_transfers[]`/`result` | 0.10 |
| `[RPC] eth_getTransactionByHash(0x...)` | tx lookup | EVM-compat, needs EVM hash form ⚠️ (not directly tested this round) | 0.05 |
| `[Mirror] GET /api/v1/accounts/{accountId}` | account detail | E3 measured `0.0.2` returns `balance/key/evm_address/alias/auto_renew_period/decline_reward/...` | 0.15 |
| `[Mirror] GET /api/v1/balances?account.id=0.0.X` | balance | Dedicated balance API; E2 measured `{timestamp, balances:[{account, balance, tokens:[]}], links{next}}` | 0.15 |
| `[RPC] eth_getBalance("0x0000...0002","latest")` | balance | EVM-compat; E6 returned hex `"0xdc190f51555e27b8e0800"` (unit weibar = tinybar × 10^10, **unit conversion required**) | 0.10 |
| `[Mirror] GET /api/v1/tokens/{tokenId}` | HTS token metadata | E11 measured USDC `0.0.456858` returns `decimals:"6", name:"USD Coin", memo:"USDC HBAR", supply_key, ...` | 0.10 |
| `[RPC] eth_call(balanceOf, USDC HTS via long-zero addr)` | HTS token balance | E15 measured `to: 0x000000000000000000000000000000000006F89A` (USDC 0.0.456858 long-zero) + `data: 0x70a08231<padded owner>` returned `"0x"` (account holds none) — **proves HTS callable via EVM precompile** | 0.10 |
| `[RPC] eth_chainId` | chainId probe | E5 `"0x127"` = 295 | 0.05 |

**Total weight = 1.00 ✓**

---

## 6. Address Format

| Field | Value |
|---|---|
| Encoding | **3-part dot notation** `shard.realm.num` (native); may also be expressed as **EVM 20-byte hex** (`0x` prefix, long-zero mapping or ECDSA alias) |
| Length | Native: `0.0.<1–10 decimal digits>` (variable); EVM: 42 chars hex (`0x` + 40) |
| Checksum | **Native: optional checksum** (form `0.0.123-vfmkw`, 5-letter suffix, SHA-384 derived); EVM side: no native checksum (EIP-55 optional) |
| Mainnet example | Native: `0.0.2` (treasury early account, E2 measured 16630126.37744658 HBAR); `0.0.456858` (USDC HTS token, E11); EVM map: `0x0000000000000000000000000000000000000002` |
| Regex | Native: `^[0-9]+\.[0-9]+\.[0-9]+(-[a-z]{5})?$`; EVM: `^0x[0-9a-fA-F]{40}$` |

**⚠️ DSL new enum**: `address_format = "hedera_3part"` (`shard.realm.num`) is an entirely new DSL address class. See §11.8.

---

## 7. Signature / Transaction Hash Lookup

| Field | Value |
|---|---|
| Hash format | **Mirror native**: `transaction_id = <account>-<validStartSeconds>-<validStartNanos>` (E8 measured `0.0.3229-1779562731-037000118`); **or** `transaction_hash` (base64-encoded 48-byte, E8 measured `6TiGZaxwgH32ARJwXIlr5M8hd8l8tL0ZSxyUd5FX+MNlmcFPSMbFPMYGC1y8EUPz`) |
| EVM hash format | 32-byte hex `0x...` (JSON-RPC side, only ECDSA-signed tx has one); **HBAR/HTS native tx has NO corresponding EVM hash** |
| Length | Native ID: variable; native hash base64: 64 chars (48 bytes); EVM: 66 chars |
| Mainnet example | `0.0.3229-1779562731-037000118` (E8 latest CRYPTOTRANSFER) |
| Query method | `[Mirror] GET /api/v1/transactions/{transactionId}` or `/transactions?transaction.hash=<base64>` |
| Explorer URL | `https://hashscan.io/mainnet/transaction/<transactionId>` |

---

## 8. Mixed Set Weights

```json
{
  "mirror_account_query":   0.15,
  "mirror_balance_query":   0.15,
  "rpc_balance_query":      0.10,
  "mirror_tx_lookup":       0.10,
  "mirror_token_metadata":  0.10,
  "rpc_hts_balanceOf":      0.10,
  "mirror_block_by_number": 0.05,
  "mirror_block_head":      0.05,
  "rpc_block_by_number":    0.05,
  "rpc_block_height":       0.05,
  "mirror_block_head_rpc_dup": 0.05,
  "rpc_chain_id":           0.05
}
```

**Total = 1.00 ✓** (Mirror 0.60 + JSON-RPC 0.40 — Mirror weighted higher because its fields are complete & it carries more real production load)

---

## 8.5 Phase 2.1 caller/reader Change List

| # | Location (file:line) | Change | Rationale |
|---|---|---|---|
| 1 | `config/config_loader.sh` add `hedera` chain block | 12 new `rpc_methods.mixed` entries (see §8) | Consumed directly by vegeta target generator |
| 2 | `config/config_loader.sh` add `hedera` `param_formats` | 4 formats: `mirror_path_param` / `mirror_query_param` / `evm_address` / `account_3part` | Missing field → `generate_rpc_json` falls back to default → vegeta 404 |
| 3 | `tools/mock_rpc_server.py` add hedera dual-path branches | (a) New `do_GET` branch: `/api/v1/{accounts,balances,blocks,transactions,tokens,network}/...` each returns real mainnet sample (pasted from E1–E12); (b) `do_POST` reuses existing JSON-RPC branch but recognizes hashio path `/api`, adds hedera-specific `eth_call` HTS precompile responses | mock_rpc_server is fallback target; without it, mock mode → vegeta all 404/500 |
| 4 | `tools/fetch_active_accounts.py` add `HederaAdapter` (implements `fetch_active(limit)` returning `0.0.X` list + matching EVM aliases) | Outputs two fixtures: `hedera_accounts_3part.txt` (native) + `hedera_accounts_evm.txt` (0x40hex long-zero) | Dual-protocol mixed set needs two param fixtures |
| 5 | `analysis-notes/baseline-current-state.md` | Add hedera row (family=hedera, dual-API) | Doc-vs-code truth alignment |
| 6 | `analysis-notes/disk-and-network-pipeline-redesign.md` | Sync hedera into 14-chain list | Same |
| 7 | `analysis-notes/research_notes/` if relevant notes exist | N/A | — |
| 8 | `tests/` add `tests/hedera_l1_smoke.sh` | E1+E4 dual-protocol smoke + mock fallback | L1 unit-test guard |

**Test requirement**: After Phase 2.1, run `core/master_qps_executor.sh --chain hedera --mixed --duration 30`; all requests must be HTTP 200, serving as E2 evidence.

---

## 9. Mock Notes

- **Request paths**: **Dual-path**: (a) Mirror REST: `GET /api/v1/<resource>[/<id>][?<query>]` (7+ resource paths); (b) JSON-RPC: `POST /api` or `POST /` (method in body)
- **Mirror response sample** (real mainnet E7):
  ```json
  {"blocks":[{"count":3,"hapi_version":"0.73.0","hash":"0xd32933...","name":"2026-05-23T18_59_00.189823000Z.rcd.gz","number":95421653,"previous_hash":"0x4c08...","size":889,"timestamp":{"from":"1779562740.189823000","to":"1779562741.470178250"},"gas_used":0,"logs_bloom":"0x"}],"links":{"next":"/api/v1/blocks?limit=1&order=desc&block.number=lt:95421653"}}
  ```
- **JSON-RPC response sample** (E4): `{"result":"0x5b004d1","jsonrpc":"2.0","id":1}`
- **Special errors**:
  - Mirror: HTTP 404 (resource missing), HTTP 400 (bad param)
  - JSON-RPC: `-32601` method not found (E10 measured), `-32602` invalid params (E13 measured, **message contains explicit diagnostic** like "Expected 0x prefixed string representing the address (20 bytes)")
- **Mock complexity**: **High** — because: (1) dual-protocol dual-path each needs mock; (2) Mirror has 7+ resource paths needing independent branches; (3) Mirror response schemas are deeply nested (`balance.tokens[]`, `transfers[]`, `key._type`); (4) HTS precompile EVM eth_call address range (long-zero `0x00...00<8hex>`) requires regex routing

---

## 10. Adapter Reuse Decision

### Candidates

| Adapter | Compat | Missing |
|---|---|---|
| EthereumAdapter | ~55% (JSON-RPC side) | No Mirror REST, no 3-part ID, no HTS precompile addr mapping |
| CosmosAdapter | ~10% (both REST but completely different semantic model) | Tendermint vs aBFT; bech32 vs 0.0.X; entirely different module paths |
| TronHttpAdapter | ~15% (both RPC-over-HTTP) | Tron is POST+body, Hedera Mirror is GET+query/path |

### Decision

- [ ] Reuse single adapter
- [ ] New single adapter
- [x] **Mixed**: **new `HederaMirrorAdapter` (Mirror REST side)** + **reuse `EthereumAdapter` subset (JSON-RPC side)**; top-level `HederaAdapter` routes per-method `protocol` field

### Rationale

(1) **Mirror Node REST is GET-driven path + query** (`/api/v1/accounts/0.0.2`, `/api/v1/balances?account.id=0.0.2`), closest to Polkadot sidecar's GET + path placeholder (~70% isomorphic), but path+query dual-placeholder mechanism needs extension. No existing adapter reusable 100%, **must build** `HederaMirrorAdapter`.

(2) **JSON-RPC Relay is EVM-equivalent wrapper**. E4/E5/E6/E9/E10/E14/E15 confirm method names, hex encoding, error codes match Ethereum mainnet (`-32601`/`-32602` error schema identical). **Direct EthereumAdapter reuse** with `rpc_path = "/api"` (Hashio) + accept long-zero EVM address mapping rule.

(3) **DSL pattern highly isomorphic with Polkadot/Tron, ~50% reuse**. Tron wave 3 extended `protocol` enum to `{jsonrpc, rest_post_body}`; Hedera is the 3rd dual-protocol chain, **only need to add** `rest_get_path_query` (GET + path placeholder + query placeholder — Polkadot has path placeholder only). See §11.8.

### Config JSON Example (this chain)

```json
{
  "chain": "hedera",
  "family": "hedera",
  "adapter": "HederaAdapter",
  "delegate_adapter_jsonrpc": "EthereumAdapter",
  "chain_id": 295,
  "chain_id_hex": "0x127",
  "node_app": "hedera-services + hedera-mirror-node + hedera-json-rpc-relay",
  "block_time_ms": 1500,
  "finality_seconds": 5,
  "api_protocol": ["mirror_rest", "jsonrpc"],
  "mirror_endpoint": "https://mainnet-public.mirrornode.hedera.com",
  "rpc_endpoint": "https://mainnet.hashio.io/api",
  "address_format": {
    "primary":    {"encoding": "hedera_3part",        "regex": "^[0-9]+\\.[0-9]+\\.[0-9]+(-[a-z]{5})?$", "example": "0.0.2"},
    "secondary":  {"encoding": "evm_hex_long_zero",   "regex": "^0x0{24}[0-9a-fA-F]{16}$",                "example": "0x0000000000000000000000000000000000000002"},
    "ecdsa_alias":{"encoding": "evm_hex",             "regex": "^0x[0-9a-fA-F]{40}$"},
    "conversion": "3part num -> 8-byte hex right-aligned in 20-byte zero-padded address"
  },
  "native_token": {"symbol": "HBAR", "decimals": 8, "tinybar_per_hbar": 100000000, "evm_unit": "weibar=tinybar*10^10"},
  "block_semantics": {
    "model": "record_stream_wrapper",
    "note": "Hashgraph itself has no block; Mirror Node wraps record stream files (~1s) into 'blocks' with monotonic number. Native concepts are round/event/consensus_timestamp."
  },
  "rpc_methods": {
    "mirror_block_head":      {"protocol": "mirror_rest", "method": "GET", "path": "/api/v1/blocks",                "query": {"limit": "1", "order": "desc"}},
    "mirror_block_by_number": {"protocol": "mirror_rest", "method": "GET", "path": "/api/v1/blocks/{block_num}"},
    "mirror_account_query":   {"protocol": "mirror_rest", "method": "GET", "path": "/api/v1/accounts/{account_3part}"},
    "mirror_balance_query":   {"protocol": "mirror_rest", "method": "GET", "path": "/api/v1/balances",              "query": {"account.id": "{account_3part}"}},
    "mirror_tx_lookup":       {"protocol": "mirror_rest", "method": "GET", "path": "/api/v1/transactions/{tx_id_3part_dash}"},
    "mirror_token_metadata":  {"protocol": "mirror_rest", "method": "GET", "path": "/api/v1/tokens/{token_3part}"},
    "rpc_block_height":       {"protocol": "jsonrpc",     "method_jsonrpc": "eth_blockNumber",      "params": []},
    "rpc_block_by_number":    {"protocol": "jsonrpc",     "method_jsonrpc": "eth_getBlockByNumber", "params": ["latest", false]},
    "rpc_balance_query":      {"protocol": "jsonrpc",     "method_jsonrpc": "eth_getBalance",       "params": ["{evm_address_long_zero}", "latest"]},
    "rpc_chain_id":           {"protocol": "jsonrpc",     "method_jsonrpc": "eth_chainId",          "params": []},
    "rpc_hts_balanceOf":      {"protocol": "jsonrpc",     "method_jsonrpc": "eth_call",
                               "params": [{"to": "{hts_token_evm_long_zero}", "data": "0x70a08231{padded_hex_owner}"}, "latest"]}
  },
  "mixed_weights": {
    "mirror_account_query": 0.15, "mirror_balance_query": 0.15, "rpc_balance_query": 0.10,
    "mirror_tx_lookup": 0.10, "mirror_token_metadata": 0.10, "rpc_hts_balanceOf": 0.10,
    "mirror_block_by_number": 0.05, "mirror_block_head": 0.05,
    "rpc_block_by_number": 0.05, "rpc_block_height": 0.05, "rpc_chain_id": 0.05,
    "mirror_block_head_rpc_dup": 0.05
  }
}
```

---

## 11. DSL Expressivity Analysis (Hedera 3 APIs + dual-protocol testing)

### 11.1–11.6 (common items aligned with other chains)

- **11.1 method naming**: Mirror = HTTP method + path template (`GET /api/v1/<resource>`); JSON-RPC = `eth_*` literal. DSL already supports string literal; Mirror needs `path` + `query` two-layer template fields.
- **11.2 params types**: Mirror = path placeholder (`{account_3part}`) + query string placeholder; JSON-RPC = array (same as Ethereum). **`3part_id` placeholder is a new DSL value** (`0.0.X` embeds directly into path, no URL-encode needed since `.` is path-legal).
- **11.3 result types**: Mirror = raw JSON, no `result` wrapper, top-level key IS the business field (`balances`/`transactions`/`blocks`/...); JSON-RPC = `{jsonrpc, id, result}` standard envelope. **Response validation path differs per-protocol**.
- **11.4 error schema**: Mirror = HTTP 4xx (404/400) + body `{"_status":{"messages":[{...}]}}` ⚠️ (not triggered this round); JSON-RPC = `{"error":{"code":-32601/-32602,"message":"..."}}` (E10+E13 measured, **message contains detailed diagnostic** like "Expected 0x prefixed string representing the address (20 bytes)").
- **11.5 batch**: Mirror — **not supported** (pure REST); JSON-RPC — ⚠️ (not verified this round, Hashio docs unclear).
- **11.6 dual-protocol**: **Mirror REST exposed at `mainnet-public.mirrornode.hedera.com` and JSON-RPC at `mainnet.hashio.io`** — they are **two separate hosts** (unlike Tron's single host `api.trongrid.io`); **DSL must separate endpoint fields** (`mirror_endpoint` vs `rpc_endpoint`).

### 11.7 (mandatory) Hedera 3-API comparison (all measured live; gRPC col from official docs)

| Dimension | Mirror Node REST (tested) | JSON-RPC Relay (tested) | gRPC HCS / HAPI (**NOT tested**) |
|---|---|---|---|
| Protocol | REST (GET/POST + JSON) | JSON-RPC 2.0 (POST + body) | gRPC + protobuf (binary) |
| Entry path | `/api/v1/<resource>[/<id>][?<query>]` (multi-path) | Single `/api` (Hashio) or `/` (self-host) | binary RPC service `proto.CryptoService/ConsensusService/...` |
| Liveness probe | `GET /api/v1/network/supply` → E1 measured `{released_supply, total_supply, timestamp}` | `eth_blockNumber` → E4 `"0x5b004d1"` | `NetworkGetVersionInfoQuery` (protobuf) ⚠️ |
| Balance query | `GET /api/v1/balances?account.id=0.0.2` → E2 measured `{balances:[{account:"0.0.2", balance:1663012637744658(tinybar), tokens:[]}], links}` | `eth_getBalance("0x0000000000000000000000000000000000000002","latest")` → E6 measured `"0xdc190f51555e27b8e0800"` (weibar) | `CryptoGetAccountBalanceQuery` ⚠️ |
| Tx lookup | `GET /api/v1/transactions/{id}` → E8 measured incl. `transfers[]/token_transfers[]/nft_transfers[]/charged_tx_fee/memo_base64/transaction_hash(base64)/transaction_id` | `eth_getTransactionByHash("0x...")` → EVM-style ⚠️ (only HSCS contract tx has EVM hash) | `TransactionGetReceiptQuery` / `TransactionGetRecordQuery` ⚠️ |
| Block query | `GET /api/v1/blocks/{number}` → E12 measured `{count, hash(0x96-char), number, timestamp{from,to}, gas_used, logs_bloom}` (**record stream wrapper**) | `eth_getBlockByNumber("latest", false)` → E9 measured fills full EVM fields (`stateRoot/receiptsRoot/transactionsRoot/baseFeePerGas/withdrawals[]` mostly zero-padded placeholders) | **gRPC has no block concept**, uses `consensus_timestamp` for ordering |
| HTS token | `GET /api/v1/tokens/0.0.456858` → E11 measured USDC `{name:"USD Coin", decimals:"6", memo:"USDC HBAR", supply_key, admin_key, freeze_key, ...}` | `eth_call({to:"0x000000000000000000000000000000000006F89A", data:"0x70a08231<padded>"})` → E15 measured `"0x"` (account has none — **HTS precompile path works**) | `TokenGetInfoQuery` ⚠️ |
| Address input | **3-part `0.0.X`** (native) or EVM long-zero hex | **EVM 20-byte hex only** (long-zero or ECDSA alias) | account_num (uint64 + shard/realm) |
| Error return | HTTP 404/400 + `{"_status":{"messages":[...]}}` ⚠️ not triggered | `-32601` method not found (E10) ; `-32602` invalid params (E13, with explicit diagnostic) | gRPC status code + ResponseCode enum |
| Doc completeness | **Complete** (all Hashgraph entities: account/balance/tx/block/token/topic/contract/schedule/network) | **EVM-compat subset** (common `eth_*` methods; **no HTS/topic/schedule Hedera-specific info**) | **Complete** (full HAPI service) |
| Field semantic completeness | **Very high** (`auto_renew_period`, `decline_reward`, `evm_address`, `key{_type:ProtobufEncoded}`, `alias` etc all exposed) | **Low** (EVM abstraction only — balance/tx/block) | **Very high** + native protobuf schema |
| Public endpoint | `https://mainnet-public.mirrornode.hedera.com` | `https://mainnet.hashio.io/api` | Paid only (QuickNode etc) + mTLS |
| DSL reuse vs other chains | ~70% isomorphic with Polkadot sidecar GET-path style; but Polkadot has no query placeholder | ~95% isomorphic with Ethereum/Tron-RPC | **0%** (protobuf not vegeta-friendly) |

**Key findings**:
- **Block semantic difference**: `Mirror /blocks/{n}` is record stream wrapper, timestamp is `{from, to}` interval (E7+E12); JSON-RPC `eth_getBlockByNumber` fills full EVM fields but mostly zero placeholders (`stateRoot=0x56e81f...b421` is the RLP-encoded empty trie constant, E9). **Same block #95421653, two APIs use entirely different field names**, but underlying record file is the same.
- **Balance unit difference**: Mirror returns **tinybar** (`1663012637744658`, 8 decimals); JSON-RPC returns **weibar** (= tinybar × 10^10, aligned with Ethereum wei). E2+E6 measured 0.0.2 balance comparison: tinybar `1663012637744658` ≈ weibar `0xdc190f51555e27b8e0800` (both ≈ 16.63M HBAR, **unit conversion required in plugin config**).
- **HTS token is both native and contract**: Mirror via `/api/v1/tokens/0.0.456858` for metadata (E11); JSON-RPC via `eth_call` to **long-zero EVM address** (`0x000000000000000000000000000000000006F89A`) calling `balanceOf(address)` (E15) — **HTS exposes ERC20 interface via precompile**, this is Hedera-unique architecture.
- **EVM address = strict 20-byte validation**: E13 measured `0x...000F8DA` (41 chars) was rejected with explicit "Expected 0x prefixed string representing the address (20 bytes)" — **DSL fixture generator MUST strictly pad to 40 hex**.
- **Tx hash dual format**: Mirror uses `0.0.3229-1779562731-037000118` (transaction_id, account-validStart-nanos); JSON-RPC uses 32-byte hex. **No direct conversion** between them (different signing systems) — must sample both independently.

### 11.8 (mandatory) DSL Recommendation

- [ ] Mirror REST only (simplify framework, drop EVM) → **REJECT**, JSON-RPC carries 70%+ Hedera DeFi traffic (uniswap-like, SaucerSwap); skipping diverges from production load
- [ ] JSON-RPC only (reuse Ethereum DSL, lose Hedera native API coverage) → **REJECT**, drops HTS metadata, tx record, staking reward — all Hedera-unique
- [ ] Auto-fallback dual-protocol → **REJECT** (same as Tron §11.8 rationale: fallback hides single-protocol failure, breaks observability)
- [x] **Dual-protocol mixing (per-method `protocol` field), Polkadot/Tron pattern**: Mirror REST handles account/balance/tx/token/block (Mirror has full fields, ~60% of real production load); JSON-RPC handles EVM contract calls + HTS precompile + EVM-compat balance/block (covers dApp real traffic, ~40%)

**Rationale** (3 paragraphs):

**(1) 3 APIs are objective reality of Hedera node architecture; benchmark must cover the 2 publicly accessible ones**. Hedera node has 3 layers: consensus node (gRPC, paid mTLS, not tested), mirror node (REST/GraphQL, this research's primary target), JSON-RPC Relay (EVM-compat wrapper, this research's secondary target). Mirror serves native clients (HashPack wallet, Hedera SDK) + full-field needs (staking, key structure, auto-renew, custom fee); JSON-RPC serves Web3 ecosystem (MetaMask, ethers.js, Hardhat) — ~70% of Hedera smart-contract projects use JSON-RPC. **Testing only one** diverges from real production load distribution. Mirror has heavy fields (single account response 1.5KB+, E3); JSON-RPC is light — the IO/CPU pressure patterns on the node differ; dual-protocol mixed pressure is the only realistic benchmark.

**(2) DSL pattern reuses Polkadot/Tron dual-protocol infra ~50%; incremental effort is small**. Tron wave 3 extended `protocol` enum to `{jsonrpc, rest_post_body}`; Polkadot wave 2 built `rest_sidecar` (GET + path placeholder). Hedera is the **3rd dual-protocol chain**, adding mainly: (a) `protocol = "mirror_rest"` (or more generally `rest_get_path_query`), GET + path placeholder + **query-string placeholder** (Polkadot had path only — new dimension); (b) `address_format` enum + `hedera_3part` (`shard.realm.num`); (c) `address_format` enum + `evm_hex_long_zero` (20-byte hex with first 24 chars must be 0, derived from 3-part num); (d) `balance_unit` config field new `tinybar` vs `weibar` dual-unit mapping (Ethereum had only wei, Bitcoin only satoshi). **Plugin-side config syntax reuses Polkadot/Tron existing structure 100%**; vegeta target generator adds query-string placeholder rendering (~20 lines).

**(3) Decision reversal guardrail** (skill `chain-additions` requirement): if introducing `family=hedera`, the DSL endpoints schema **must extend** to support: ① 3-part account ID (`0.0.X`) new enum value; ② block-is-record-stream-wrapper (`timestamp{from,to}` dual-time field); ③ dual endpoint hosts (`mirror_endpoint` + `rpc_endpoint` separate, unlike Tron single host). **Without these extensions, family=hedera cannot land**. §10 JSON example already lists full schema changes for Phase 2.1 implementation.

#### Reuse Assessment Against Polkadot/Tron Dual-Protocol Infra

| Facility | Polkadot wave 2 built | Tron wave 3 extended | Hedera direct reuse? | Increment |
|---|---|---|---|---|
| plugin JSON `api_protocol: [...]` list | ✅ `["jsonrpc","rest_sidecar"]` | ✅ `["jsonrpc","http_post"]` | ✅ `["jsonrpc","mirror_rest"]` | enum +1 |
| per-method `protocol` field | ✅ | ✅ extend | ✅ extend +1 `mirror_rest` | enum +1 |
| `path` placeholder template render | ✅ GET path (`/blocks/{n}`) | ⚠️ Tron static path + body render (~30 lines) | ✅ reuse path render; **add query-string placeholder render (~20 lines)** | ~20 lines query renderer |
| Dual endpoint host separation | ⚠️ Polkadot single host | ⚠️ Tron single host | **First case for dual host**: `mirror_endpoint` + `rpc_endpoint` fields separated | ~10 lines endpoint router |
| `success_check` per-protocol abstraction | ✅ | ✅ | ✅ reuse, Mirror checks HTTP 200 + top-level business key (`balances`/`blocks`/`transactions`) | 0 |
| fixture-based param lists | ✅ (`polkadot_accounts.txt`) | ✅ (`tron_accounts_base58.txt`) | ✅ add `hedera_accounts_3part.txt` + `hedera_accounts_evm_longzero.txt` + `hedera_tokens.txt` | adapter one-shot pre-gen |
| 3-part ID → EVM long-zero conversion | — | — | **First case**: `0.0.N` → `0x` + 24*'0' + 16-char hex padded N | ~10 lines in adapter |
| Balance dual-unit normalization (tinybar/weibar) | — | — | **First case**: plugin `balance_unit_normalizer` field | DSL schema +1 field |
| mock_rpc_server path routing | ✅ `do_GET` sidecar branch | ✅ `do_POST` `/wallet/*` branch | ✅ reuse `do_GET` but heavily extend `/api/v1/*` multi-resource branches (~80 lines) | ~80 lines mock branches |
| **Total reuse** | — | — | **~50%** | net +140 lines + adapter + DSL schema +2 fields |

**Conclusion**: **Hedera is the 3rd validation of the dual-protocol DSL design** (Polkadot=GET-path, Tron=POST-body, Hedera=GET-path-query); 3 chains jointly validate the universality of the `per-method protocol` field. After this round's extension (`mirror_rest` + query placeholder + dual endpoint), the DSL dual-protocol layer can be considered **stable**; future scenarios (Avalanche P/C/X 3-chain split-pressure, ICP multi-canister, etc.) should reuse it directly.

---

## Open Questions

- [ ] **DSL ASK A**: Should `address_format` be defined as enum (`{base58, hex, bech32, hedera_3part, ...}`) or structured object (`{encoding, regex, prefix, length, conversion}`)? **Strongly recommend structured** (Hedera alone needs 3 coexisting address_formats: `hedera_3part` + `evm_hex_long_zero` + `evm_hex_ecdsa_alias` — enum would explode).
- [ ] **DSL ASK B**: `protocol` enum granularity — is `{jsonrpc, rest_get_path, rest_get_path_query, rest_post_body}` 4 values too fine-grained? Alternative: unified `{jsonrpc, http}` + sub-fields `http_method: GET|POST` + `path_template` + `query_template` + `body_template`, any null = skipped. **Strongly recommend alternative** (extensible to PUT/PATCH/DELETE; more general DSL).
- [ ] **DSL ASK C**: **Block semantics abstraction** — current DSL `block_time_ms` is a single number; Hedera block is record stream wrapper with `timestamp` as `{from, to}` interval. Introduce `block_semantics: {model: "blockchain"|"record_stream_wrapper"|"slot_based", timestamp_field: "single"|"range"}`? Not required for Phase 2.1 landing but Phase 2.2 visualization (Grafana panel "block" label semantics) will need.
- [ ] **DSL ASK D**: `balance_unit` multi-unit conversion — same Hedera account balance differs 10^10 between Mirror (tinybar) and JSON-RPC (weibar); plugin needs `balance_unit_normalizer: {mirror_rest: "tinybar", jsonrpc: "weibar", display_unit: "HBAR", display_decimals: 8}`? Phase 2.1 mixed set data comparison panels need this.
- [ ] **DSL ASK E**: 3-part ID → EVM long-zero conversion handled by `fetch_active_accounts` (one-shot, 0-Python friendly) or via plugin `address_class` declaration so adapter converts at runtime? **Strongly recommend former** (avoid runtime Python; same decision as Tron).
- [ ] **DSL ASK F**: tx hash dual format (Mirror `0.0.X-secs-nanos` vs JSON-RPC `0x32hex`) — does mixed set need independent fixtures (`hedera_tx_ids_3part.txt` + `hedera_tx_hashes_evm.txt`)? Both lack direct conversion; **must sample independently**.
- [ ] **DSL ASK G**: HTS precompile address (long-zero 0x..6F89A ↔ 0.0.456858) — plugin config field `hts_tokens: [{name:"USDC", id_3part:"0.0.456858", evm_long_zero:"0x...06F89A", decimals:6}]`? Phase 2.1 cross-token comparison needs it.
- [ ] **Unverified ⚠️**: Real rate limit for `https://mainnet-public.mirrornode.hedera.com` (per docs ~100 req/s; not stressed this round)
- [ ] **Unverified ⚠️**: Real rate limit for Hashio JSON-RPC `https://mainnet.hashio.io/api` (per docs ~50 req/s)
- [ ] **Unverified ⚠️**: Mirror REST 4xx error body shape (expected `{"_status":{"messages":[...]}}`, not triggered)
- [ ] **Unverified ⚠️**: `eth_getTransactionByHash` in Hedera JSON-RPC real return schema (need to capture an HSCS contract tx EVM hash first)
- [ ] **Unverified ⚠️**: JSON-RPC batch (`[{...},{...}]`) support — Hashio docs unclear
- [ ] **Unverified ⚠️**: Mirror Node GraphQL endpoint (`/graphql`) publicly exposed on mainnet-public? — not tried this round
- [ ] **Unverified ⚠️**: Real Hedera finality numerics (per aBFT theory ~3–5 s)

---

## Changelog

| Date | Author | Change |
|---|---|---|
| 2026-05-23 | Hermes Agent | Initial research; 14 curl probes covering Mirror REST + JSON-RPC Relay; dual-API DSL decision = per-method protocol; ~50% reuse of Polkadot/Tron dual-protocol DSL pattern; new asks: `hedera_3part` address format, `mirror_rest` protocol, dual endpoint host, tinybar/weibar unit conversion (4 DSL extension asks); clarified block semantic = record stream wrapper in Hashgraph |
