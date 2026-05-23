# 05 — Cosmos Hub Research Note

> **Version**: v1.0 (draft, Phase 1.2 Wave1)
> **Research date**: 2026-05-23
> **Author**: Hermes Agent
> **Status**: 🟢 Pending user review (P1-USER-REVIEW blocker)
> **Strict H8 real-evidence compliance**: every key field in this note carries an E1-E5 tag (E1=unit test / E2=curl-tested / E3=official docs / E4=GitHub source / E5=framework grep).

---

## Meta

| Field | Value |
|---|---|
| Chain name (zh) | Cosmos Hub |
| Chain name (en) | Cosmos Hub |
| Number | 05 |
| Mainnet ChainID | `cosmoshub-4` (string, not numeric) — E2 curl-tested `https://cosmos-rpc.publicnode.com/status` returns `network: "cosmoshub-4"` |
| Node app | **gaiad v27.3.0** (GaiaApp), Tendermint/CometBFT consensus layer `v0.38.19` — E2 |
| Research date | 2026-05-23 |
| Researcher | Hermes Agent |
| Status | 🟢 Complete (framework does not yet support this chain; this research prepares for Phase 2.x plugin introduction) |
| Already supported by framework? | ❌ — E5: `config/config_loader.sh:666` `supported_blockchains` only contains `(solana ethereum bsc base scroll polygon starknet sui)`, no cosmos |

---

## 1. Sources

| Type | URL | Accessed | Notes |
|---|---|---|---|
| Official docs (Cosmos SDK) | https://docs.cosmos.network/ | 2026-05-23 | Cosmos SDK modular framework home |
| Official docs (Hub) | https://hub.cosmos.network/ | 2026-05-23 | Cosmos Hub chain-specific spec |
| Tendermint RPC spec | https://docs.cometbft.com/v0.38/rpc/ | 2026-05-23 | CometBFT (formerly Tendermint) JSON-RPC full method list |
| Cosmos REST/LCD OpenAPI | https://docs.cosmos.network/api | 2026-05-23 | gRPC-gateway auto-generated REST interface |
| GitHub (gaia) | https://github.com/cosmos/gaia | 2026-05-23 | Cosmos Hub node daemon source (gaiad) |
| GitHub (cosmos-sdk) | https://github.com/cosmos/cosmos-sdk | 2026-05-23 | Module code (bank/staking/...) + proto definitions |
| GitHub (cometbft) | https://github.com/cometbft/cometbft | 2026-05-23 | Consensus layer + RPC implementation |
| Explorer (Mintscan) | https://www.mintscan.io/cosmos | 2026-05-23 | Address/tx/validator lookup |
| Explorer (Ping.pub) | https://ping.pub/cosmos | 2026-05-23 | Backup explorer |

---

## 2. Protocol Family

| Field | Value |
|---|---|
| Family | **Cosmos-SDK / Tendermint** (ABCI abstraction layer, dozens of chains reuse: Osmosis / Celestia / Injective / Sei / Kava / Stride / Neutron / dYdX v4 / Noble / ...) |
| Consensus | **Tendermint BFT / CometBFT** (instant finality, final after 1 block) |
| VM | **Cosmos SDK modules** (native Go modular, non-EVM); optional **CosmWasm** (WASM smart contracts, not enabled on Cosmos Hub mainnet, enabled on Juno/Neutron/Osmosis) |
| Block Time | ~6 seconds (E2 curl-tested: height 31248030 → 31248052 span ~131 seconds, about 5.96s/block) |
| Finality | **Instant final** (BFT, 1 block irreversible, no need to wait N confirmations) |
| Reuse Existing Adapter? | **No, need to build a new CosmosAdapter** (account model + address format + API protocol all three differ, nothing reusable) |
| Number of chains in this family (framework plan) | At least 6: cosmos / osmosis / celestia / injective / sei / kava (possibly more, pending Phase 2.x decision) |

---

## 3. Public RPC / REST

### Endpoint candidates

| Endpoint | API type | Auth | Measured status | Notes |
|---|---|---|---|---|
| `https://cosmos-rpc.publicnode.com` | Tendermint RPC :26657 | none | ✅ HTTP 200 (E2) | Allnodes/publicnode public-good node |
| `https://cosmos-rest.publicnode.com` | REST/LCD :1317 | none | ✅ HTTP 200 (E2) | Same as above |
| `https://cosmos-grpc.publicnode.com` | gRPC :9090 | none | ⚠️ Endpoint exists (domain returns a browser page) but **not curl-tested via grpcurl/protoc** (no grpcurl in this environment); HTTP/1.1 POST returns 415 = normal gRPC behavior | Public-good gRPC gateway |
| `https://rpc.cosmos.network` | Tendermint RPC | none | ❌ HTTP 525 (SSL handshake failed, measured 2026-05-23, possibly transient outage) | Official public node, **currently unavailable** |
| `https://rest.cosmos.network` | REST/LCD | none | ❌ HTTP 525 (same as above) | Official public node |

**Trade-off**: `rpc.cosmos.network` official node measured unreachable (SSL 525); `cosmos-rpc.publicnode.com` all 200. Recommend production mock-fallback prefer publicnode. **Reversal condition**: if Phase 2.x measures publicnode rate-limiting too strict, fall back to the official node (which should be recovered by then).

### curl-tested (2026-05-23 ~18:05 UTC actually executed, **numeric fields are time-sensitive**)

#### 3.1 Tendermint RPC :26657 (JSON-RPC, also supports GET style)

```bash
# /status — node status + latest height
$ curl -s https://cosmos-rpc.publicnode.com/status
{"jsonrpc":"2.0","id":-1,"result":{
  "node_info":{"network":"cosmoshub-4","version":"0.38.19",...},
  "sync_info":{
    "latest_block_hash":"057D121688D530344FDF519E2D1A6C870FEBB4E82E4BF519555799A918E62C5F",
    "latest_block_height":"31248039",
    "latest_block_time":"2026-05-23T18:03:49.254536256Z",
    "earliest_block_height":"25280088",
    "catching_up":false}}}
# Interpretation: chain_id=cosmoshub-4, height=31248039 (note: String type, not number)

# /abci_info — application-layer version
$ curl -s https://cosmos-rpc.publicnode.com/abci_info
{"jsonrpc":"2.0","id":-1,"result":{"response":{
  "data":"GaiaApp","version":"v27.3.0",
  "last_block_height":"31248042",
  "last_block_app_hash":"y9w+EkG/n0hMoJt06WhRBNbuoymFo1q0LXQICxIelUQ="}}}

# /block?height=N — block details (incl. tx list, base64 encoded)
$ curl -s "https://cosmos-rpc.publicnode.com/block?height=31248030"
{"jsonrpc":"2.0","id":-1,"result":{
  "block_id":{"hash":"F8CC501F944ED412A09B9C3DC3522A12D883F0960A11B34669F1588792E6B1E2",...},
  "block":{"header":{"chain_id":"cosmoshub-4","height":"31248030",
    "time":"2026-05-23T18:03:00.621898913Z","proposer_address":"56B2F053AD136642D3FC9098FB2DD01454F396D5"},
  "data":{"txs":["CvoBCosBChwvY29zbW9zLmJhbmsudjFiZXRhMS5Nc2dTZW5kEms..."]}}}}
# Interpretation: txs is base64-encoded protobuf; client must decode before reading MsgSend content

# /tx?hash=0x... — tx details (note hex uppercase, 0x prefix mandatory)
$ curl -s "https://cosmos-rpc.publicnode.com/tx?hash=0x1EC1293E8C5E266C76846F35EAC7E25DDCAAF049AEF5ABA67F492C61C57CEAA6"
{"jsonrpc":"2.0","id":-1,"result":{
  "hash":"1EC1293E8C5E266C76846F35EAC7E25DDCAAF049AEF5ABA67F492C61C57CEAA6",
  "height":"31248030","tx_result":{"code":0,"gas_wanted":"125000","gas_used":"106050",
  "events":[{"type":"tx","attributes":[
    {"key":"acc_seq","value":"cosmos1wypsnn7n5hsd2kvk424qv9yuretz9m6kvumev2/91150"}]}]}}}

# /abci_query — ABCI secondary routing (Cosmos-unique, DSL must be able to express)
$ curl -s 'https://cosmos-rpc.publicnode.com/abci_query?path="/app/version"'
{"jsonrpc":"2.0","id":-1,"result":{"response":{"code":0,
  "value":"djI3LjMuMA==","height":"31248049","codespace":"sdk"}}}
# Interpretation: value base64 → "v27.3.0"
```

#### 3.2 Cosmos REST/LCD :1317 (REST, path-style parameters)

```bash
# Balance query
$ curl -s https://cosmos-rest.publicnode.com/cosmos/bank/v1beta1/balances/cosmos1wypsnn7n5hsd2kvk424qv9yuretz9m6kvumev2
{"balances":[
  {"denom":"ibc/3622BC03E5098BF3EC0A2DB13E5031668290B98020C5FADB7901207F44C4D717","amount":"134000000000"},
  {"denom":"ibc/3B362DDD99879D5BA199A265C5BBD46AE139CA9F46B5CFCDE9C59D68792825C4","amount":"19499989999799000000"},
  ...
],"pagination":{"next_key":null,"total":"0"}}
# Interpretation: multi-denom asset array; IBC tokens identified by ibc/<hash> denom

# tx query
$ curl -s https://cosmos-rest.publicnode.com/cosmos/tx/v1beta1/txs/1EC1293E8C5E266C76846F35EAC7E25DDCAAF049AEF5ABA67F492C61C57CEAA6
{"tx":{"body":{"messages":[{
  "@type":"/cosmos.bank.v1beta1.MsgSend",
  "from_address":"cosmos1wypsnn7n5hsd2kvk424qv9yuretz9m6kvumev2",
  "to_address":"cosmos180phhck72hqkkfygyn6n77p6hvg6749f54uytv",
  "amount":[{"denom":"uatom","amount":"60"}]}],"memo":"1/5 🎁 💎$ATOM Airdrop..."}}}

# Latest block
$ curl -s https://cosmos-rest.publicnode.com/cosmos/base/tendermint/v1beta1/blocks/latest
{"block_id":{"hash":"fjs2y78cAi4Y2/Ccz9mVBmBKjR3waIMv2jFb22qAFCw=",...},
 "block":{"header":{"chain_id":"cosmoshub-4","height":"31248052","time":"2026-05-23T18:05:04.302220555Z"}}}
# Note: REST returns hash as base64-encoded, RPC returns hash as uppercase hex — same hash, two encodings!

# Node info (incl. git_commit, build_tags)
$ curl -s https://cosmos-rest.publicnode.com/cosmos/base/tendermint/v1beta1/node_info
{"default_node_info":{"network":"cosmoshub-4","version":"0.38.19",...},
 "application_version":{"name":"gaia","app_name":"gaiad","version":"v27.3.0",
   "git_commit":"ed341c8ae3802c3f522f9b3aeb95b872d59bcb89","build_tags":"netgo,ledger"}}

# Sync status
$ curl -s https://cosmos-rest.publicnode.com/cosmos/base/tendermint/v1beta1/syncing
{"syncing": false}

# validators list (to find real validator addresses)
$ curl -s "https://cosmos-rest.publicnode.com/cosmos/staking/v1beta1/validators?pagination.limit=2&status=BOND_STATUS_BONDED"
{"validators":[{"operator_address":"cosmosvaloper1q6d3d089hg59x6gcx92uumx70s5y5wadklue8s",
  "consensus_pubkey":{"@type":"/cosmos.crypto.ed25519.PubKey","key":"uEUR1gpesU4bnSWL2TOXOf3org2mCYhQHMYkiCJyMD4="},
  "status":"BOND_STATUS_BONDED","tokens":"1153338880041",
  "description":{"moniker":"Ubik Capital",...}}],
  "pagination":{"next_key":"FArILLpzgq04+y5e2aCGDLtnvPQs","total":"0"}}
```

#### 3.3 gRPC :9090 (not curl-tested this round, marked truthfully)

⚠️ **No E2 evidence**: this research environment has no `grpcurl` command (`which grpcurl` returns not found). The `https://cosmos-grpc.publicnode.com` endpoint exists (curl returns the publicnode browser page = reverse-proxy normal); HTTP/1.1 plain POST returns 415 Unsupported Media Type (= normal gRPC behavior, consistent with gRPC over HTTP/2 + protobuf protocol requirements).

E3 evidence (official spec): https://docs.cosmos.network/main/learn/advanced/grpc_rest explicitly states gRPC endpoint defaults to `:9090`, providing `cosmos.bank.v1beta1.Query/AllBalances`, `cosmos.tx.v1beta1.Service/GetTx`, `cosmos.base.tendermint.v1beta1.Service/GetLatestBlock`, etc.

**Evidence opening (mandatory if Phase 2.x decides to use gRPC)**:
```bash
# Run during Phase 2.x implementation (not run this round):
grpcurl -d '{"address":"cosmos1..."}' cosmos-grpc.publicnode.com:443 \
  cosmos.bank.v1beta1.Query/AllBalances
```

---

## 4. Account Model

| Field | Value |
|---|---|
| Model | **Account model** (not UTXO); accounts identified by bech32 address |
| Native token | **ATOM** (denom string = `uatom`, 1 ATOM = 1,000,000 uatom) — E2 curl-tested MsgSend.amount = `[{denom:"uatom",amount:"60"}]` |
| Native token decimals | **6** (uatom is micro-ATOM) — E3: Cosmos SDK standard |
| Address derivation | **secp256k1** (default) / **ed25519** (consensus pubkey) / **sr25519** (optional on some chains) — E2: observed validator consensus_pubkey uses ed25519 |
| Multi-asset | **Yes** (a single account may hold multiple denoms: uatom + ibc/<hash> various IBC tokens) — E2 curl-tested, see §3.2 balance query |
| Special account types | **Module Accounts** (held by modules, e.g. `cosmos1fl48vsnmsdzcv85q5d2q4z5ajdha8yu34mf0eh` = bank module), **Validator Operator** (`cosmosvaloper1...` prefix), **Consensus Address** (`cosmosvalcons1...`) — same hash, different bech32 prefix |

---

## 5. Core RPC Methods (required by this framework's monitoring)

> **Method-name labels: [TR]=Tendermint RPC, [RE]=REST/LCD, [GR]=gRPC**. The same logical functionality has completely different names across the three API sets; DSL must explicitly state which one is used.

| Logical function | [TR] Tendermint RPC :26657 | [RE] REST/LCD :1317 | [GR] gRPC :9090 | mixed weight suggestion |
|---|---|---|---|---|
| Block height (liveness) | `/status` (read `result.sync_info.latest_block_height`) | `GET /cosmos/base/tendermint/v1beta1/blocks/latest` | `cosmos.base.tendermint.v1beta1.Service/GetLatestBlock` | 0.10 |
| Block details | `/block?height=N` | `GET /cosmos/base/tendermint/v1beta1/blocks/{height}` | `cosmos.base.tendermint.v1beta1.Service/GetBlockByHeight` | 0.10 |
| ABCI info | `/abci_info` | (no equivalent, gRPC-gateway does not expose) | `cosmos.base.tendermint.v1beta1.Service/GetNodeInfo` (similar) | 0.05 |
| Balance query | `/abci_query?path="/cosmos.bank.v1beta1.Query/AllBalances"&data=<protobuf-hex>` (**requires protobuf-encoded query**, client-complex) | `GET /cosmos/bank/v1beta1/balances/{addr}` | `cosmos.bank.v1beta1.Query/AllBalances` | 0.30 |
| Single-denom balance | Same as above, query is `Balance` (single denom) | `GET /cosmos/bank/v1beta1/balances/{addr}/by_denom?denom=uatom` | `cosmos.bank.v1beta1.Query/Balance` | 0.05 |
| tx lookup | `/tx?hash=0xUPPER_HEX&prove=true` | `GET /cosmos/tx/v1beta1/txs/{hash}` | `cosmos.tx.v1beta1.Service/GetTx` | 0.15 |
| tx search | `/tx_search?query="tx.height=N"&per_page=K` | `GET /cosmos/tx/v1beta1/txs?events=...&pagination.limit=K` | `cosmos.tx.v1beta1.Service/GetTxsEvent` | 0.05 |
| validators | `/validators?height=N&per_page=K` | `GET /cosmos/staking/v1beta1/validators` | `cosmos.staking.v1beta1.Query/Validators` | 0.10 |
| delegations | (requires abci_query encoding) | `GET /cosmos/staking/v1beta1/delegations/{delegator_addr}` | `cosmos.staking.v1beta1.Query/DelegatorDelegations` | 0.05 |
| Node info | `/status` (same as above, see node_info) | `GET /cosmos/base/tendermint/v1beta1/node_info` | Same GetNodeInfo as above | 0.05 |

**Total weight**: 0.10+0.10+0.05+0.30+0.05+0.15+0.05+0.10+0.05+0.05 = **1.00** ✅

**Key observations**:
1. **Balance query**: Tendermint RPC path requires protobuf-encoded `data` parameter (high complexity); REST uses direct path parameter (simple); gRPC is native protobuf. **REST is the easiest to implement for benchmark**.
2. **tx hash case sensitivity**: Tendermint RPC `/tx?hash=0x...` mandates **uppercase hex + 0x prefix** (E2 verified); REST `/cosmos/tx/v1beta1/txs/{hash}` accepts uppercase hex without prefix (E2 verified).
3. **block hash encoding divergence**: Tendermint RPC `/block` returns hash = **uppercase hex string**; REST `/cosmos/base/tendermint/v1beta1/blocks/latest` returns hash = **base64 string** (same hash, two encodings!).

---

## 6. Address Format

| Field | Value |
|---|---|
| Encoding | **Bech32** (BIP173) — E3 |
| HRP (human-readable prefix) | **`cosmos`** (account) / **`cosmosvaloper`** (validator operator) / **`cosmosvalcons`** (consensus) / **`cosmospub`** (pubkey) / ... — **different per chain** (osmo / celestia / inj / sei / kava ...) |
| Total length | Account address = `cosmos1` + 38 chars = 45 chars (20-byte hash + 6-byte checksum + 1-byte separator) — E2 verified: `cosmos1wypsnn7n5hsd2kvk424qv9yuretz9m6kvumev2` length = 45 |
| Checksum | **Yes** (Bech32 algorithm includes a built-in 6-char BCH checksum) |
| Example (real mainnet account) | `cosmos1wypsnn7n5hsd2kvk424qv9yuretz9m6kvumev2` (E2: has real balance, see §3.2) |
| Example (real mainnet validator) | `cosmosvaloper1q6d3d089hg59x6gcx92uumx70s5y5wadklue8s` (Ubik Capital, E2 curl-tested bonded) |
| Example (target address — framework config candidate) | `cosmos1wypsnn7n5hsd2kvk424qv9yuretz9m6kvumev2` (active sender, acc_seq already at 91150 = extremely active account) |
| Validation regex | `^cosmos1[02-9ac-hj-np-z]{38}$` (account) / `^cosmosvaloper1[02-9ac-hj-np-z]{38}$` (validator) |
| Cross-chain address portability | **The same hash can derive other prefixes** (the same private key controls cosmos1.../osmo1.../celestia1..., essentially secp256k1 pubkey hash) |

---

## 7. Signature Lookup (signature / transaction hash)

| Field | Value |
|---|---|
| Hash format | **Hex uppercase** (SHA-256 → 32 bytes → 64 hex chars, **no prefix**; Tendermint RPC `/tx` query mandates **adding `0x` prefix**; REST does not need it) |
| Length | **64 chars** (32-byte SHA-256) |
| Example (real mainnet tx) | `1EC1293E8C5E266C76846F35EAC7E25DDCAAF049AEF5ABA67F492C61C57CEAA6` (E2: height 31248030, real MsgSend) |
| Lookup method (Tendermint RPC) | `/tx?hash=0x1EC1293E8C5E266C76846F35EAC7E25DDCAAF049AEF5ABA67F492C61C57CEAA6&prove=false` |
| Lookup method (REST) | `GET /cosmos/tx/v1beta1/txs/1EC1293E8C5E266C76846F35EAC7E25DDCAAF049AEF5ABA67F492C61C57CEAA6` |
| Explorer URL | `https://www.mintscan.io/cosmos/tx/<hash>` |

⚠️ **Case sensitivity**: Tendermint RPC measured returns normally in **uppercase**; changing to lowercase the hash still matches (SHA-256 hex case is semantically irrelevant), but the REST interface path part **conventionally uses uppercase** (both explorer and docs use uppercase). DSL should uniformly use uppercase.

---

## 8. Mixed Set (`mixed` mode weights)

> Used for request distribution when `BLOCKCHAIN_NODE_BENCHMARK_MODE=mixed`. **Same schema as Solana §8 / Ethereum §5** (currently equal-weight rotation by `config_loader.sh::generate_rpc_json`; Phase 2.x will introduce weighting and then use the weight field).

### Design suggestion (assuming DSL chooses REST/LCD, see §11.8)

```json
{
  "cosmos_bank_balance": 0.30,
  "cosmos_tx_get": 0.15,
  "cosmos_block_by_height": 0.10,
  "cosmos_block_latest": 0.10,
  "cosmos_validators_list": 0.10,
  "cosmos_node_info": 0.05,
  "cosmos_syncing": 0.05,
  "cosmos_tx_search": 0.05,
  "cosmos_delegations": 0.05,
  "cosmos_bank_balance_by_denom": 0.05
}
```

Concrete method mapping (REST):
- `cosmos_bank_balance` → `GET /cosmos/bank/v1beta1/balances/{addr}`
- `cosmos_tx_get` → `GET /cosmos/tx/v1beta1/txs/{hash}`
- `cosmos_block_by_height` → `GET /cosmos/base/tendermint/v1beta1/blocks/{N}`
- `cosmos_block_latest` → `GET /cosmos/base/tendermint/v1beta1/blocks/latest`
- `cosmos_validators_list` → `GET /cosmos/staking/v1beta1/validators?pagination.limit=10`
- ...

**Weight sum = 1.00 ✅**

---

## 8.5 Phase 2.1 Caller/Reader Retrofit Points (token-level Gate 3)

**This chain is newly added** (no existing code); items #4-8 are marked N/A as applicable. **Actions that must be performed in sync when adding cosmos**:

| # | Location (file:line) | Change | Reason |
|---|---|---|---|
| 1 | `config/config_loader.sh:666` `supported_blockchains` array | Add `"cosmos"` | Otherwise validate_blockchain_node will reject |
| 2 | `config/config_loader.sh:~380` add `case cosmos)` setting `MAINNET_RPC_URL=https://cosmos-rest.publicnode.com` (or RPC, see §11.8 decision) | Set endpoint | Mandatory |
| 3 | `config/config_loader.sh:~440-468`-style `UNIFIED_BLOCKCHAIN_CONFIG.blockchains.cosmos` section | Add methods / system_addresses / rpc_methods.single / rpc_methods.mixed / param_formats | Directly consumed by the vegeta target generator |
| 4 | `tools/mock_rpc_server.py:~137` method branch | Add cosmos method branch (REST style = **path parameters + GET**, completely different from the existing 8 chains' all-POST JSON-RPC!) | mock_rpc_server is the fallback target; **different protocol requires new HTTP routing** |
| 5 | `tools/fetch_active_accounts.py` add `CosmosAdapter(BlockchainAdapter)` class | Implement `_single_request` (REST GET) / `fetch_transaction` (REST GET) / `extract_accounts_from_transaction` (extract from MsgSend.from_address/to_address) | First of its family, no reusable adapter |
| 6 | `analysis-notes/baseline-current-state.md` grep `solana\|ethereum`, add this chain to the pipeline list | Sync update | Doc-truth alignment |
| 7 | `tests/` add `test_cosmos_adapter.py` (if test infrastructure exists) | At least run one real-mainnet fixture tx parse | L1 unit test |
| 8 | `core/master_qps_executor.sh --mixed --duration 30` passes | All requests 200, no -32601 / -32603 errors | E2 evidence, serves as this chain's retrofit success criterion |

**Key pitfalls (Cosmos-unique)**:
- REST is **GET + path parameters**, differing at the protocol layer from the existing 8 chains' **POST + JSON-RPC body** — `mock_rpc_server.py` currently uses `BaseHTTPRequestHandler.do_POST`; **must add `do_GET`**.
- The vegeta target generator (`target_generator.sh:184/300-306`) needs to support GET method + URL-only target (no body) — may require schema extension.

---

## 9. Mock Notes (mock_rpc_server implementation notes)

### If DSL chooses **REST/LCD :1317**:

- **Request paths**: multiple, e.g. `GET /cosmos/bank/v1beta1/balances/{addr}`, `GET /cosmos/tx/v1beta1/txs/{hash}`, `GET /cosmos/base/tendermint/v1beta1/blocks/latest`
- **Response schema samples** (real mainnet, see §3.2):
  ```json
  {"balances":[{"denom":"uatom","amount":"1234567"}],"pagination":{"next_key":null,"total":"0"}}
  {"tx":{"body":{"messages":[{"@type":"/cosmos.bank.v1beta1.MsgSend",...}]}}}
  ```
- **Special error codes**:
  - HTTP `501` + `{"jsonrpc":"","error":{"code":-32701,"message":"not implemented"}}` (unimplemented path, E2 curl-tested)
  - HTTP `400` + `{"code":3,"message":"invalid address: decoding bech32 failed: invalid checksum ..."}` (bech32 validation failure, E2 curl-tested)
  - HTTP `404` + `{"code":5,"message":"not found"}` (tx hash not found, common)
- **Key mock complexity**: **High**
  - Protocol layer differs from existing 8 chains (GET path vs POST body) — need to extend `mock_rpc_server.py` to add `do_GET` + path-routing dispatcher
  - Response schemas are deeply nested (`messages[].{@type, from_address, to_address, amount[]}`) — fixture mode recommended
  - Multi-denom assets (`uatom` + multiple `ibc/<hash>`) — fixtures must cover

### If DSL chooses **Tendermint RPC :26657**:

- **Request paths**: `GET /<method>?<query>` or `POST /` JSON-RPC body
- **Response schema samples**: see §3.1
- **Special error codes**:
  - `-32603 Internal error` (e.g. height beyond current height, E2 curl-tested)
  - `-32601 Method not found`
  - `-32700 Parse error`
- **Key mock complexity**: **Medium**
  - Same JSON-RPC protocol as existing 8 chains (POST body), easy to extend mock_rpc_server
  - But the `data` field of `abci_query` requires protobuf encoding; mock does not need real encoding (returning fixed fixtures is enough)

---

## 10. Adapter Reuse Decision

### Candidate adapters

| Adapter | Compatibility | Missing capability |
|---|---|---|
| SolanaAdapter | **0%** | Protocol/address/account model all differ |
| EthereumAdapter | **0%** | hex address vs bech32, JSON-RPC vs REST/abci |
| BitcoinAdapter (if 03 research produced) | **0%** | UTXO vs Account |
| New CosmosAdapter | **100%** | — |

### Decision

- [ ] Reuse
- [x] **Build new `CosmosAdapter`** (Cosmos-SDK / Tendermint family; **Osmosis / Celestia / Injective / Sei / Kava / Stride and dozens of other chains can reuse this adapter**; Phase 2.x distinguishes per-chain specifics like bech32 prefix / native denom / custom modules via the `chain_type` field, mirroring EthereumAdapter's `chain_type=bsc/ethereum/base` pattern)
- [ ] Hybrid

### Rationale

**3-paragraph explanation**:

(1) Cosmos is an independent family; its account model differs completely from Solana (SVM/PoH), Ethereum (EVM), Bitcoin (UTXO) — bech32 addresses + multi-denom assets + ABCI secondary routing + Tendermint consensus. No existing adapter is reusable.

(2) **High intra-family reuse value**: beyond Cosmos Hub, Osmosis (osmo1...) / Celestia (celestia1...) / Injective (inj1...) / Sei (sei1...) / Kava (kava1...) / Stride (stride1...) / Neutron (neutron1...) / dYdX v4 (dydx1...) and dozens of other chains all inherit Cosmos SDK + Tendermint ABCI abstractions; **API endpoint paths are completely identical** (only bech32 prefix and native denom differ). After Phase 2.x implements CosmosAdapter, each subsequent Cosmos-family chain only needs a new plugin JSON config (`bech32_prefix` + `native_denom` + `endpoint`), 0 lines of Python — consistent with the Q4=C 95%-chain-addition 0-Python goal.

(3) **chain_type pattern references EthereumAdapter**: CosmosAdapter should retain a `chain_type` field (`cosmos / osmosis / celestia / ...`), used for (a) bech32 prefix validation (each chain has a different hrp); (b) native denom configuration (`uatom` / `uosmo` / `utia` / `inj`); (c) if a chain has a custom module (e.g. Osmosis' GAMM, Sei's dex) requiring additional paths, branch handling within the adapter.

### Config JSON example (this chain)

```json
{
  "chain": "cosmos",
  "family": "cosmos-sdk",
  "adapter": "CosmosAdapter",
  "chain_id_str": "cosmoshub-4",
  "node_app": "gaiad",
  "node_app_version": "v27.3.0",
  "consensus_version": "0.38.19",
  "api_protocol": "rest",
  "rpc_endpoint": "https://cosmos-rest.publicnode.com",
  "rpc_endpoint_tendermint": "https://cosmos-rpc.publicnode.com",
  "rpc_endpoint_grpc": "cosmos-grpc.publicnode.com:443",
  "block_time_ms": 6000,
  "finality": "instant",
  "address_format": {
    "encoding": "bech32",
    "hrp_account": "cosmos",
    "hrp_validator": "cosmosvaloper",
    "hrp_consensus": "cosmosvalcons",
    "length": 45,
    "regex": "^cosmos1[02-9ac-hj-np-z]{38}$"
  },
  "native_denom": "uatom",
  "native_decimals": 6,
  "rpc_methods": {
    "block_height": "GET /cosmos/base/tendermint/v1beta1/blocks/latest",
    "block_by_height": "GET /cosmos/base/tendermint/v1beta1/blocks/{height}",
    "balance": "GET /cosmos/bank/v1beta1/balances/{addr}",
    "balance_by_denom": "GET /cosmos/bank/v1beta1/balances/{addr}/by_denom?denom={denom}",
    "tx_lookup": "GET /cosmos/tx/v1beta1/txs/{hash}",
    "tx_search": "GET /cosmos/tx/v1beta1/txs?events={query}",
    "validators": "GET /cosmos/staking/v1beta1/validators?pagination.limit={limit}",
    "delegations": "GET /cosmos/staking/v1beta1/delegations/{delegator_addr}",
    "node_info": "GET /cosmos/base/tendermint/v1beta1/node_info",
    "syncing": "GET /cosmos/base/tendermint/v1beta1/syncing"
  },
  "param_formats": {
    "balance": "path_addr",
    "balance_by_denom": "path_addr_query_denom",
    "tx_lookup": "path_hash_upper_hex_no_prefix",
    "block_by_height": "path_height",
    "validators": "query_pagination",
    "block_height": "no_params",
    "node_info": "no_params",
    "syncing": "no_params"
  },
  "mixed_weights": {
    "balance": 0.30,
    "tx_lookup": 0.15,
    "block_by_height": 0.10,
    "block_height": 0.10,
    "validators": 0.10,
    "tx_search": 0.05,
    "delegations": 0.05,
    "balance_by_denom": 0.05,
    "node_info": 0.05,
    "syncing": 0.05
  },
  "system_addresses": [
    "cosmos1fl48vsnmsdzcv85q5d2q4z5ajdha8yu34mf0eh",
    "cosmos17xpfvakm2amg962yls6f84z3kell8c5lserqta",
    "cosmos1jv65s3grqf6v6jl3dp4t6c9t9rk99cd88lyufl",
    "cosmos1tygms3xhhs3yv487phx3dw4a95jn7t7lpm470r"
  ],
  "system_addresses_note": "The above are common module accounts (bank/distribution/staking/fee_collector) — must E2-verify each address before Phase 2.x implementation",
  "default_target_address": "cosmos1wypsnn7n5hsd2kvk424qv9yuretz9m6kvumev2",
  "tx_hash_format": {
    "encoding": "hex_upper_no_prefix",
    "tendermint_rpc_prefix": "0x",
    "rest_prefix": ""
  }
}
```

⚠️ **system_addresses caveat**: this research did not E2-verify module account addresses (requires SHA-256(module_name) → bech32 computation or explorer lookup). Phase 2.x implementation must curl-test before; **the 4 addresses listed are E5 SPECULATED** (inferred from Cosmos SDK module-account derivation rules, pending verification).

---

## 11. DSL Field Requirements (Q4=C 95% 0-Python declarative DSL input)

### 11.1 RPC call protocol

**Cosmos specifics: three coexisting protocols, DSL must be able to dispatch**

| Dimension | Tendermint RPC :26657 | Cosmos REST/LCD :1317 | Cosmos gRPC :9090 |
|---|---|---|---|
| Protocol | JSON-RPC 2.0 (also supports GET query string) | REST / HTTP (GET/POST) | gRPC over HTTP/2 + Protobuf |
| HTTP method | POST (body) or GET (query) | GET (queries) / POST (broadcast) | HTTP/2 frames |
| Request path | `/<method>` | `/cosmos/<module>/v1beta1/<resource>` | `<package>.<Service>/<Method>` |
| Auth | Typically public (publicnode no key) | Typically public | Typically public |
| Content-Type | `application/json` | `application/json` | `application/grpc` |

**DSL auth field suggestion** (Phase 2.x):
```yaml
auth:
  type: none | basic | bearer | api_key
  # for bearer / api_key:
  header: "Authorization" | "X-API-Key"
  value_env: "COSMOS_API_KEY"  # do not write the literal key
```

### 11.2 method call schema (one section per method)

**REST protocol (assuming DSL chooses REST, see §11.8)**:

```yaml
methods:
  balance:
    http_method: GET
    path: "/cosmos/bank/v1beta1/balances/{addr}"
    path_params:
      - name: addr
        from: "$.target_address"
        validation: "^cosmos1[02-9ac-hj-np-z]{38}$"
    response_extract:
      balances: "$.balances[*]"
      first_denom: "$.balances[0].denom"
      first_amount: "$.balances[0].amount"
    error_codes:
      400: "invalid_address (bech32 fail)"
      501: "not_implemented"

  tx_lookup:
    http_method: GET
    path: "/cosmos/tx/v1beta1/txs/{hash}"
    path_params:
      - name: hash
        from: "$.cursor.tx_hash"
        transform: "upper_hex_no_prefix"
    response_extract:
      messages: "$.tx.body.messages[*]"
      msg_type: "$.tx.body.messages[0].@type"
      from: "$.tx.body.messages[0].from_address"
    error_codes:
      404: "tx_not_found"

  block_by_height:
    http_method: GET
    path: "/cosmos/base/tendermint/v1beta1/blocks/{height}"
    path_params:
      - name: height
        from: "$.cursor.height"
    response_extract:
      tx_count: "$.block.data.txs.length"
      time: "$.block.header.time"
      chain_id: "$.block.header.chain_id"
```

**Tendermint RPC protocol (for comparison)**:

```yaml
methods:
  block:
    http_method: GET  # also supports POST JSON-RPC
    path: "/block"
    query_params:
      - name: height
        from: "$.cursor.height"
    response_extract:
      hash: "$.result.block_id.hash"  # uppercase hex
      height: "$.result.block.header.height"  # String type!

  tx:
    http_method: GET
    path: "/tx"
    query_params:
      - name: hash
        from: "$.cursor.tx_hash"
        transform: "prefix_0x_upper_hex"  # 0x prefix mandatory
      - name: prove
        value: false
    response_extract:
      height: "$.result.height"
      gas_used: "$.result.tx_result.gas_used"

  abci_query:  # ABCI secondary routing — Cosmos-unique
    http_method: GET
    path: "/abci_query"
    query_params:
      - name: path  # quoted literal!
        value: '"/cosmos.bank.v1beta1.Query/AllBalances"'
      - name: data  # protobuf hex; DSL needs protobuf-encode helper
        from: "$.encoded_protobuf"
    response_extract:
      value_base64: "$.result.response.value"  # client needs base64 decode + protobuf decode
```

### 11.3 cursor / pagination model

**Cosmos has three cursor models (DSL must be able to express)**:

| Model | Scenario | DSL field suggestion |
|---|---|---|
| **Height monotonic** (monotonic integer) | block_by_height, validators?height=N | `cursor: { type: height_int, start: latest, increment: -1 }` |
| **next_key** (opaque string, base64) | REST validators / delegations and other large-list `pagination.next_key` | `cursor: { type: opaque_next_key, response_path: "$.pagination.next_key", request_param: "pagination.key" }` |
| **page / per_page** (integer paging) | Tendermint RPC `/validators?per_page=K&page=N`, `/tx_search` | `cursor: { type: page_offset, page_param: "page", per_page_param: "per_page" }` |
| **events query string** (using `events=tx.height=N`) | REST tx_search | `cursor: { type: events_query, template: "tx.height={height}" }` |

E2 verification: `pagination.next_key` is a base64 string (see §3.2 validators response `"next_key":"FArILLpzgq04+y5e2aCGDLtnvPQs"`); `pagination.total` is commonly `"0"` on publicnode (the node does not configure exact counts; this is known behavior, **do not trust total**).

### 11.4 system addresses / filter rules

**Address types that Cosmos should filter (framework decision point)**:

| Type | Example | Should filter |
|---|---|---|
| **Module accounts** (bank / distribution / fee_collector / staking) | `cosmos1fl48vsnmsdzcv85q5d2q4z5ajdha8yu34mf0eh` (bank, E5 pending verification) | **Yes** (held by modules, not users) |
| **Validator operator** | `cosmosvaloper1...` | Usually **no** (these are real business addresses) |
| **IBC channel escrow** | `cosmos1...` derived from SHA-256(channel-N) | **Yes** (IBC lockup temporary addresses, do not represent active users) |
| **CEX hot wallets** | Binance / Kraken, etc. | **No** (real user behavior, of interest to benchmark) |

**DSL filter-field suggestion**:
```yaml
account_filter:
  exclude_module_accounts: true   # compute module account addresses and filter
  exclude_ibc_escrow: true        # filter addresses derived from SHA-256(channel-N)
  exclude_prefixes:
    - "cosmosvalcons1"            # consensus addresses are not regular accounts
  custom_exclude:
    - "<additional address>"
```

### 11.5 Heterogeneity markers (vs existing 8 chains)

**Dimensions where Cosmos significantly differs from the existing 8 chains (solana / ethereum / bsc / base / scroll / polygon / starknet / sui)**:

| # | Dimension | Existing 8 chains | Cosmos Hub | DSL impact |
|---|---|---|---|---|
| 1 | **API protocol** | 100% JSON-RPC 2.0 (POST body) | **3 sets coexist**: Tendermint RPC (JSON-RPC), REST/LCD (GET path), gRPC | DSL must have `api_protocol: jsonrpc \| rest \| grpc` enum; mock_rpc_server must add `do_GET` |
| 2 | **Address encoding** | base58 (solana/sui), hex (5 EVM chains), felt (starknet) | **bech32 + hrp** (different hrp per chain: cosmos/osmo/celestia/inj/...) | DSL needs `bech32_hrp` field; validation regex must include hrp variable |
| 3 | **ChainID type** | Numeric (EVM) / string `mainnet-beta` (solana) / numeric hex (starknet) | **String** `cosmoshub-4` | DSL needs `chain_id` field to support string type |
| 4 | **Multi-asset model** | Single native + token (SPL/ERC20/...) | **Single account multi-denom** (uatom + multiple ibc/<hash>) | DSL balance-query response extraction must support arrays (`$.balances[*]`) |
| 5 | **ABCI secondary routing** | None | `/abci_query?path="/cosmos.bank.v1beta1.Query/AllBalances"` — **path is a quoted literal** + data is protobuf hex | DSL must be able to express: nested path / protobuf-encode helper |
| 6 | **tx hash encoding divergence** | Each chain uses one consistent set | **Same chain has 2 sets**: Tendermint RPC needs `0x` prefix uppercase hex, REST needs no-prefix uppercase hex | DSL transform field must support `prefix_0x` / `strip_0x` conversions |
| 7 | **block hash encoding divergence** | Each chain uses one set | **Same chain has 2 sets**: Tendermint RPC returns uppercase hex, REST returns base64 | response_extract needs base64-decode helper |
| 8 | **Finality** | Solana 32 slots / EVM N confirmations / Starknet probabilistic | **Instant** (BFT, 1 block final) | DSL needs `finality: instant \| slots:N \| confirmations:N` enum |
| 9 | **Node daemon name** | Differs per chain (solana-validator/geth/...) | **gaiad** (cosmos) / **osmosisd** / **celestia-appd** / ... differs per chain | Does not affect DSL, but affects plugin metadata |

### 11.6 DSL design ASK (requirements for P2-DESIGN-v2)

**Required capabilities**:
1. **`api_protocol` enum**: `jsonrpc | rest | grpc`; plugin must declare; target_generator picks the vegeta target format accordingly
2. **HTTP method enum**: `GET | POST` (REST mostly GET, JSON-RPC mostly POST); mock_rpc_server adds `do_GET`
3. **Path template + placeholders**: `/cosmos/bank/v1beta1/balances/{addr}`-style syntax; placeholders sourced from `$.target_address` / `$.cursor.X`
4. **`response_extract` JSONPath**: extract response fields (balance/height/hash) for the next-step cursor advance
5. **`bech32_hrp` field**: Cosmos-family chains have different hrp per chain; plugin declares it and adapter auto-validates
6. **`chain_id` supports string type**: must not allow only int
7. **Multi-denom balance response**: `$.balances[*]` array extraction; DSL JSONPath engine must support `[*]`
8. **`transform` field**: built-in helpers `upper_hex_no_prefix` / `prefix_0x_upper_hex` / `base64_decode` / `strip_0x`, etc.
9. **`cursor.type` enum**: `height_int | opaque_next_key | page_offset | events_query`
10. **`account_filter` block**: `exclude_module_accounts` / `exclude_ibc_escrow` / `exclude_prefixes`

**Optional capabilities**:
1. **`abci_query` sub-protocol** (if DSL chooses Tendermint RPC): path literal + protobuf-hex encoding helper — **high complexity; recommend deferring to post-Phase 2.x**
2. **gRPC protocol** (if choosing gRPC): requires protoc compilation + grpc client; **no reusable infrastructure currently, strongly recommend skipping**
3. **WebSocket subscriptions**: Tendermint RPC supports `/websocket` events subscription; this framework is pull-based benchmark, **not needed**
4. **broadcast tx**: Cosmos supports `POST /cosmos/tx/v1beta1/txs` (broadcast signed tx); benchmark is **read-only**, not needed

**Not-needed capabilities**:
1. **Client-side protobuf encoding** (unless going through abci_query / gRPC) — REST is all JSON, no protobuf client library required
2. **Local keyring integration** — this framework only reads mainnet, does not sign tx
3. **IBC cross-chain state machine** — complex, benchmark does not care

---

### 11.7 Cosmos three-API empirical comparison (this section is a mandatory requirement)

> **Each row in this section filled by E2 measurement** (2026-05-23 ~18:05 UTC); unmeasured items marked ⚠️.

| Dimension | Tendermint RPC :26657 | Cosmos REST/LCD :1317 | Cosmos gRPC :9090 |
|---|---|---|---|
| **Protocol** | JSON-RPC 2.0 (supports GET query shorthand) — E2 | REST/HTTP (JSON responses) — E2 | gRPC over HTTP/2 + Protobuf — ⚠️ no E2 (no grpcurl) |
| **Balance query method** | `abci_query?path="/cosmos.bank.v1beta1.Query/AllBalances"&data=<protobuf-hex>` (E3: requires protobuf client to encode query) | `GET /cosmos/bank/v1beta1/balances/{addr}` — **E2 ✅** returns multi-denom balance array | `cosmos.bank.v1beta1.Query/AllBalances` — ⚠️ no E2 |
| **tx query method** | `/tx?hash=0x<UPPER_HEX>&prove=false` — **E2 ✅** returns hash/height/events | `GET /cosmos/tx/v1beta1/txs/{UPPER_HEX_NO_PREFIX}` — **E2 ✅** returns messages array | `cosmos.tx.v1beta1.Service/GetTx` — ⚠️ no E2 |
| **block query method** | `/block?height=N` — **E2 ✅** returns block_id.hash (**uppercase hex**) | `GET /cosmos/base/tendermint/v1beta1/blocks/{height}` — **E2 ✅** returns block_id.hash (**base64**) | `cosmos.base.tendermint.v1beta1.Service/GetBlockByHeight` — ⚠️ no E2 |
| **status / height** | `/status` — **E2 ✅** contains sync_info.latest_block_height (String) | `GET /cosmos/base/tendermint/v1beta1/syncing` — **E2 ✅** `{"syncing":false}` | Similar GetNodeInfo — ⚠️ no E2 |
| **abci_query path encoding** | **Yes** (`path="/store/<module>/key"` or `path="/<package>.<Service>/<Method>"`, **literal with quotes**) — E2 ✅ ran `path="/app/version"` | **No** (direct REST path) | **No** (native gRPC service method) |
| **Pagination model** | `page` + `per_page` integer paging (E2 curl-tested `/tx_search?per_page=1`) | `pagination.limit` + `pagination.key` (opaque next_key, base64) — E2 ✅ measured returns `"next_key":"FArILLpzgq04+y5e2aCGDLtnvPQs"` | gRPC stream (E3 docs) — ⚠️ no E2 |
| **Auth** | publicnode public-good: public (no key) — E2 | publicnode public-good: public — E2 | publicnode public-good: public (domain reachable) — ⚠️ gRPC call not verified |
| **Response hash encoding** | **Uppercase hex** (no prefix) — E2 ✅ `057D121688D530344FDF519E2D1A6C870FEBB4E82E4BF519555799A918E62C5F` | **base64** (note!) — E2 ✅ `fjs2y78cAi4Y2/Ccz9mVBmBKjR3waIMv2jFb22qAFCw=` | Native protobuf bytes — ⚠️ no E2 |
| **Error format** | `{"jsonrpc":"2.0","error":{"code":-32603,"message":"Internal error","data":"..."}}` — E2 ✅ | HTTP error code + `{"code":N,"message":"...","details":[]}` — E2 ✅ (e.g. bech32 fail returns 400 + code 3) | gRPC status code (`OUT_OF_RANGE` / `NOT_FOUND` / ...) — E3 docs |
| **Response Content-Type** | `application/json` | `application/json` | `application/grpc` |
| **DSL implementation complexity** | **Medium**: same JSON-RPC protocol as existing 8 chains, but `abci_query` sub-protocol needs protobuf-encode helper; GET query shorthand format differs | **Low**: pure REST, responses directly readable; protocol-layer difference vs mock_rpc_server (GET vs POST) but schema is simple | **High**: requires protoc compilation of cosmos-sdk protos; no off-the-shelf Go/Python gRPC client integration; framework infrastructure is empty |

### 11.8 DSL choice recommendation (this section is a mandatory requirement)

**Decision**:

- [ ] Tendermint RPC :26657 (JSON-RPC, same protocol as existing 8 chains, highest DSL reuse)
- [x] **Cosmos REST/LCD :1317** (REST, requires DSL to support path parameters)
- [x] **DSL must support a protocol enum** (`jsonrpc | rest | grpc`) — support both of the above simultaneously, plugin self-describes
- [ ] gRPC :9090 (this framework abandons; rationale below)

**Rationale** (3 paragraphs):

**(1) REST/LCD is this framework's first choice (primary)**

REST has the simplest protocol layer — path parameters + GET + JSON response, no protobuf-encode helper needed, no abci_query secondary routing literal-quoted-path + protobuf-hex quirks. E2 measurement of `cosmos-rest.publicnode.com` returned HTTP 200 for every test method, with stable parseable response schemas (`$.balances[*]`, `$.tx.body.messages[0].from_address`, `$.block.header.height` are all intuitive JSONPath). REST mode incurs the lowest DSL complexity increment — the main new requirements are `api_protocol: rest` enum + HTTP method GET support + path template placeholders + bech32 validation; these are 28-chain-general infrastructure, **with returns far exceeding the abci_query complexity added solely for Cosmos**.

**(2) DSL must retain a protocol enum (do not lock REST in)**

Although REST is the recommendation, DSL should not hardcode REST. Some chains in the Cosmos ecosystem (e.g. Celestia's data-sampling queries) expose certain methods only via Tendermint RPC (the REST gateway is not generated), and Tendermint RPC shares the protocol with the existing 8 chains (JSON-RPC 2.0 POST), making reuse technically smoother. Plugins should be able to declare `via: tendermint_rpc` or `via: rest` per method (hybrid); DSL just provides both target generators. **Key reversal condition**: if Phase 2.x measures publicnode REST endpoint rate-limiting as severe while Tendermint RPC rate-limiting is loose, plugins can switch by changing `api_protocol: jsonrpc`; the DSL layer requires no rewrite.

**(3) Rationale for abandoning gRPC**

gRPC requires protoc compilation of the full cosmos-sdk protobuf definitions (`cosmos/bank/v1beta1/query.proto` etc., dozens of files) + grpc client integration + streaming response handling; this framework (Python + bash + vegeta) has no existing gRPC infrastructure (vegeta does not support gRPC; additional use of `grpcurl` or `ghz` would be required as substitutes). Performance-wise, gRPC is only 2-5x faster than REST (no JSON-parse overhead); for a benchmark framework (which measures the node, not the client overhead), **the performance difference is unimportant**. **Reversal condition**: if the user explicitly requires benchmarking the node's gRPC endpoint performance (because exchanges in production pull data via gRPC heavily), independently introduce `ghz` as a gRPC vegeta substitute; **but this is independent work, does not block the REST main path**.

---

## Open Questions

- [ ] **system_addresses 4 module accounts not E2-verified** (marked SPECULATED in §10 config JSON) — must curl-test each address before Phase 2.x implementation (can query module-account list via `GET /cosmos/auth/v1beta1/module_accounts` + extract base_account.address)
- [ ] **gRPC measurement missing** (§3.3, §11.7) — no grpcurl in this environment; must add grpcurl measurements before Phase 2.x implementation if gRPC is chosen
- [ ] **publicnode REST rate-limiting unknown** — `cosmos-rest.publicnode.com` public rate-limit docs not provided; Phase 2.x implementation may require `time.sleep` throttling (similar to Solana mainnet-beta < 10 req/s speculated)
- [ ] **abci_query data field protobuf encoding** — if DSL goes via the Tendermint RPC path, requires Go/Python protoc output of cosmos-sdk proto encoders; **the framework currently has no such infrastructure** (choosing REST sidesteps this issue)
- [ ] **chain_type field namespace** — same as Ethereum chain_type=bsc/base/...; CosmosAdapter's chain_type should be `cosmos/osmosis/celestia/...`, but do Osmosis/Celestia etc. need finer subdivision due to custom modules (GAMM/data sampling)? To be decided during Phase 2.0 plugin design
- [ ] **IBC token balance identifier** — REST returns `denom: "ibc/3622BC03..."` hash form; client needs `GET /ibc/apps/transfer/v1/denom_traces/{hash}` to reverse-resolve original chain + denom; does the benchmark need this step? Current recommendation **no** (benchmarking the node does not require displaying semantics)
- [ ] **Tendermint RPC and REST endpoint synchrony** — measured that on publicnode at the same moment RPC height=31248039 and REST node_info both accessible (no visible lag), but across nodes (rpc on one node, rest on another) might they differ by a few blocks? Phase 2.x measurement to confirm
- [ ] **Multi-chain shared endpoints** — publicnode provides osmosis-rpc.publicnode.com / celestia-rpc.publicnode.com etc.; Phase 2.x will unify this endpoint pattern when adding Cosmos-family chains

---

## Changelog

| Date | Author | Change |
|---|---|---|
| 2026-05-23 | Hermes Agent | Initial research: E2 curl-tested publicnode Tendermint RPC + REST 5 methods each (status/block/abci_info/tx/balance/validators/syncing/node_info/abci_query); gRPC E3 docs + endpoint liveness only, no grpcurl measurement |
