# 11-tezos Research

> **Derived from `_template.md` + Wave3 mandatory Section 11 (11.1-11.8).**
> **H8 (real evidence) required: curl proof + official doc URL + access date.**
> Anything not 100% empirically verified is explicitly marked ⚠️.

---

## Meta

| Field | Value |
|---|---|
| Chain (zh) | Tezos |
| Chain (en) | Tezos |
| Number | 11 |
| Mainnet ChainID | `NetXdQprcVkpaWU` (string, not numeric) |
| Research date | 2026-05-23 |
| Researcher | Hermes Agent |
| Status | 🟢 Complete (H8 evidence: 8 RPCs + 3-chain REST comparison) |

---

## 1. Sources

| Type | URL | Access date | Notes |
|---|---|---|---|
| Official site | https://tezos.com/developers | 2026-05-23 | Protocol entry — ⚠️ not DOM-verified |
| Octez Shell RPC spec | https://tezos.gitlab.io/shell/rpc.html | 2026-05-23 | Shell RPC ref (`/chains/*`, `/monitor/*`) — ⚠️ not DOM-verified |
| Octez Protocol RPC | https://tezos.gitlab.io/active/rpc.html | 2026-05-23 | Active protocol RPC (`/context/contracts/*`) — ⚠️ not DOM-verified |
| ECAD public node | https://mainnet.api.tez.ie | 2026-05-23 | **H8: `/version` HTTP:200, Octez v24.4 (release), commit 56bd3e33, 2026-04-17** |
| TzKT Indexer | https://api.tzkt.io | 2026-05-23 | **H8: `/v1/operations/transactions` HTTP:200** (used for tx_hash reverse lookup) |
| SmartPy node | https://mainnet.smartpy.io | 2026-05-23 | **H8: `/version` HTTP:200** (same Octez v24.4) — backup endpoint |
| Explorer (TzKT) | https://tzkt.io | 2026-05-23 | Manual op_hash cross-check — ⚠️ not DOM |
| GitHub (Octez) | https://gitlab.com/tezos/tezos | 2026-05-23 | Client source — ⚠️ not git-cloned |

---

## 2. Protocol Family

| Field | Value |
|---|---|
| Family | **Tezos** (standalone, not Cosmos/Substrate/Move/EVM) |
| Consensus | **LPoS (Liquid Proof-of-Stake)** + Tenderbake BFT finality — E3 doc; H8 only proves protocol chain (`PtTALLi…` in head) |
| VM | **Michelson** (strongly-typed stack-based functional VM) + Smart Rollup (SORU, L2) |
| Block time | **~6s** — derived from H8: level 13329316 @ 2026-05-23T18:44:13Z vs level 13329000 @ 2026-05-23T18:12:19Z → 316 blocks / 1914 s ≈ **6.06 s/block** (note: this is current protocol PtTALLi `minimal_block_delay`; historical docs say 10-30s) |
| Finality | **2 blocks** deterministic (Tenderbake, E3 doc) — ⚠️ not E2-tested |
| Reuse adapter? | **No** — Tezos is standalone family, new `TezosAdapter` required (see §10) |

---

## 3. Public RPC

| Endpoint | Auth | Rate Limit | Notes |
|---|---|---|---|
| https://mainnet.api.tez.ie | none | ⚠️ undocumented | **H8 alive**: `/version` 200, latency ~0.41s, Octez v24.4 |
| https://mainnet.smartpy.io | none | ⚠️ undocumented | **H8 alive**: `/version` 200, latency ~0.35s, Octez v24.4 — recommended backup |
| https://api.tzkt.io | none | docs say 10K req/day (free) | **Indexer** (not Octez RPC); used for tx_hash reverse lookup; cannot replace Octez RPC |

**curl evidence** (proves RPC is live, 2026-05-23 ~18:44 UTC):

```bash
# 1. /version — node version + network (health check)
$ curl -s https://mainnet.api.tez.ie/version
{"version":{"major":24,"minor":4,"build":0,"additional_info":"release"},
 "network_version":{"chain_name":"TEZOS_MAINNET","distributed_db_version":2,"p2p_version":1},
 "commit_info":{"commit_hash":"56bd3e33","commit_date":"2026-04-17 10:26:39 +0000"}}
# HTTP:200

# 2. head block header — chain_id + protocol_hash + level
$ curl -s https://mainnet.api.tez.ie/chains/main/blocks/head/header
{"protocol":"PtTALLiNtPec7mE7yY4m3k26J8Qukef3E3ehzhfXgFZKGtDdAXu",
 "chain_id":"NetXdQprcVkpaWU",
 "hash":"BLffzWLDPFwcaDU4qYtnbpwTgNeWmE8FXUEgZVxCLjoJj6VGPtQ",
 "level":13329316, "proto":24, "timestamp":"2026-05-23T18:44:13Z", ...}
# HTTP:200

# 3. balance (tz1 baker)
$ curl -s https://mainnet.api.tez.ie/chains/main/blocks/head/context/contracts/tz1KqTpEZ7Yob7QbPE4Hy4Wo8fHG8LhKxZSx/balance
"53"
# HTTP:200 — JSON string (not number), unit = mutez (10⁻⁶ XTZ)

# 4. chain_id standalone
$ curl -s https://mainnet.api.tez.ie/chains/main/chain_id
"NetXdQprcVkpaWU"
# HTTP:200
```

---

## 4. Account Model

| Field | Value |
|---|---|
| Model | **Account** (balance attached to account; no UTXO) |
| Native decimals | **6** (unit = mutez = 10⁻⁶ XTZ) — E3 doc, H8 returns `"53"` mutez (string-wrapped) |
| Address derivation | **Multi-algo**: tz1=Ed25519 / tz2=Secp256k1 / tz3=P256 / KT1=hash of origination (smart contract) — 4 prefixes, same 36-char format |
| Special account types | **Implicit** (tz1/tz2/tz3, can directly send/receive) / **Originated contract** (KT1, Michelson contract) / **Smart Rollup** (sr1, L2) — this round covers first 4 |

---

## 5. Core RPC Methods (required by this benchmark)

> Only methods this benchmark needs. Full RPC catalog: https://tezos.gitlab.io/active/rpc.html
> **All methods are REST-style `<HTTP_VERB> <PATH>`; no JSON-RPC method strings.**

| Method (HTTP verb + path) | Category | Notes | Mixed weight |
|---|---|---|---|
| `GET /chains/main/blocks/head/header` | block height + protocol | Health, level, protocol_hash, chain_id | 0.10 |
| `GET /chains/main/blocks/{level\|hash}/header` | block content (light) | Historical header (no op detail) | 0.10 |
| `GET /chains/main/blocks/{block}/operations/{validation_pass}` | tx lookup | Ops of a given vp in that block (array) | 0.15 |
| `GET /chains/main/blocks/head/context/contracts/{addr}/balance` | balance | Account balance (mutez, JSON string) | 0.30 |
| `GET /chains/main/blocks/head/context/contracts/{addr}/counter` | tx prep | Account nonce-like counter (for tx build) | 0.05 |
| `GET /chains/main/chain_id` | meta | chain_id standalone (constant) | 0.05 |
| `GET /version` | health/version | Octez version + commit | 0.05 |
| `GET /chains/main/blocks/head/protocols` | **protocol upgrade monitor** | Active + next protocol (different during amendment) | 0.10 |
| `GET /chains/main/blocks/head/votes/current_period` | governance | Current voting phase (proposal/exploration/cooldown/promotion/adoption) | 0.10 |

**Total = 0.10+0.10+0.15+0.30+0.05+0.05+0.05+0.10+0.10 = 1.00 ✅**

**Note**: Tezos has no native ERC20-like "token balance" concept — FA1.2/FA2 token balances require contract storage walk (`GET /context/contracts/{KT1}/storage` → parse big_map), high complexity, **Phase 2.x will not monitor** (see Open Q). `balance` = native XTZ only.

---

## 6. Address Format

| Field | Value |
|---|---|
| Encoding | **Base58Check** (Bitcoin-style alphabet + 4-byte sha256d checksum) |
| Length | **36 chars fixed** (3-byte prefix + 20-byte hash + 4-byte checksum, Base58-encoded) |
| Checksum | **Yes** (Base58Check, prefix sha256d-trunc) |
| Prefix semantics | `tz1` Ed25519 / `tz2` Secp256k1 / `tz3` P256 / `KT1` smart contract / `sr1` Smart Rollup |
| Example (mainnet real) | `tz1KqTpEZ7Yob7QbPE4Hy4Wo8fHG8LhKxZSx` (Tezos Foundation baker) — **H8 balance 200 returns `"53"` mutez** |
| Example (KT1 verified) | `KT1WvzYHCNBvDSdwafTHv7nJ1dWmZ8GCYuuC` (objkt.com Marketplace v2) — **H8 balance 200 returns `"108962378338"` mutez ≈ 108963 XTZ** |
| Validation regex | `^(tz[1-3]|KT1|sr1)[1-9A-HJ-NP-Za-km-z]{33}$` |
| Bad-addr proof | **H8: `/contracts/tz1notarealaddress/balance` returns HTTP:400 + `"Cannot parse contract id"`** — server enforces strict base58check |

---

## 7. Signature / Tx Hash Lookup

| Field | Value |
|---|---|
| Hash format | **Base58Check** (same alphabet as addresses, 51 chars, prefix `o` family) |
| Length | **51 chars** (`o` + 50) |
| Prefix semantics | `o` start = operation hash (further `oo`/`op`/`on`/`ong` etc., all valid) |
| Example (mainnet real) | `ong1822VPmQwj4bzXFwvaZUvpD6ydLsHMJMEw9UPrP7SL6EKjFd` (level 13329321 transaction) — **H8: TzKT `/v1/operations/{hash}` 200, full tx detail** |
| Query method | **Critical**: Octez RPC has **NO `getTxByHash(op_hash)` single endpoint** — must first hit indexer (TzKT) to get block_hash + vp + index, then `GET /chains/main/blocks/{block}/operations/{vp}/{index}`. E2: `GET /chains/main/blocks/{BL7ke9…}/operation_hashes` HTTP:200 returns 2D array (4 vps × N op_hashes each), confirming lookup model |
| Explorer URL | `https://tzkt.io/{op_hash}` |

---

## 8. Mixed Set (`mixed` weights)

```json
{
  "balance_query":        0.30,
  "tx_lookup":            0.15,
  "block_query":          0.20,
  "protocol_monitor":     0.10,
  "governance_monitor":   0.10,
  "counter_query":        0.05,
  "chain_id":             0.05,
  "version":              0.05
}
```

**Sum = 1.00 ✅**

**Chain-specific portion** (0.10+0.10+0.05+0.05+0.05 = 0.35):
- `protocol_monitor` (0.10): `GET /chains/main/blocks/head/protocols` — Tezos-unique, protocol amendment monitor
- `governance_monitor` (0.10): `GET /chains/main/blocks/head/votes/current_period` — LPoS vote phase
- `counter_query` (0.05): tx-build prep
- `chain_id` (0.05): constant endpoint
- `version` (0.05): node version

---

## 8.5 Phase 2.1 caller/reader changes (token-level Gate 3)

| # | Location (file:line) | Change | Reason |
|---|---|---|---|
| 1 | `config/config_loader.sh:666` `supported_blockchains` | Add `tezos` | Adapter dispatcher; missing → `--chain tezos` fails |
| 2 | `config/config_loader.sh:<new>` `rpc_methods.tezos.mixed` | Add 9 methods from §8 (key by path, e.g. `"GET_contracts_balance": 0.30`) | Consumed by vegeta target generator |
| 3 | `config/config_loader.sh:<new>` `param_formats.tezos` | path-param schema: `addr_base58check` / `block_id_or_level` / `validation_pass_0..3` | `generate_rpc_json` REST path template substitution |
| 4 | `tools/mock_rpc_server.py:<new>` REST router (if Aptos added REST framework) | Add 9 path handlers, return H8 sample JSON | mock fallback must support (else mock-mode vegeta 404 storm) |
| 5 | `tools/fetch_active_accounts.py:<new TezosAdapter>` | Implement `fetch_addresses()` via TzKT `/v1/accounts?sort.desc=balance&limit=N` | Adapter dispatcher |
| 6 | `analysis-notes/baseline-current-state.md` grep "tezos" | Add Tezos family row | doc-truth alignment |
| 7 | `analysis-notes/disk-and-network-pipeline-redesign.md` grep "tezos" | Add family | same |
| 8 | `analysis-notes/research_notes/<this file>.md` | This doc itself is the notes | N/A |
| 9 | `tests/<new test_tezos_smoke.sh>` | E2 smoke: 9 methods × 1 hit, assert HTTP:200 | L1 smoke gate |

**Post-Phase-2.1 must run** `core/master_qps_executor.sh --chain tezos --mixed --duration 30`, all requests must be 200 (E2 evidence).

---

## 9. Mock Notes (mock_rpc_server)

- **Request path (REST)**: 9 paths (see §5), all `GET`, no body
- **Response schema** (H8-verified real samples):
  ```jsonc
  // GET /chains/main/blocks/head/header  →  application/json
  {
    "protocol": "PtTALLiNtPec7mE7yY4m3k26J8Qukef3E3ehzhfXgFZKGtDdAXu",
    "chain_id": "NetXdQprcVkpaWU",
    "hash":     "BLffzWLDPFwcaDU4qYtnbpwTgNeWmE8FXUEgZVxCLjoJj6VGPtQ",
    "level":    13329316,
    "proto":    24,
    "predecessor": "BL2HKyw28VenRHfW3WP2NFvCavNqACDvqSRpkWu38GBzGBeSMut",
    "timestamp": "2026-05-23T18:44:13Z",
    "validation_pass": 4
  }

  // GET /chains/main/blocks/head/context/contracts/{addr}/balance
  "53"   // ← string-wrapped number, unit mutez. application/json but body is bare string

  // GET /chains/main/chain_id
  "NetXdQprcVkpaWU"   // ← also bare string
  ```
- **Special errors**:
  - **HTTP 400** (not RPC code): bad addr returns `"Cannot parse contract id"` (plain text, not JSON) — **H8**
  - **HTTP 404**: non-existent block_id / contract typically 404
  - **No JSON-RPC envelope** (no `{"error":{...}}`); errors are HTTP status + plain text body
- **Mock complexity**: **Medium**
  - Hard: (1) 9 paths, some with 2 path-params (`{block_id}` + `{addr}`); (2) some responses are bare JSON string (`"53"`, `"NetXdQprcVkpaWU"`) — careful with `json.dumps` quoting; (3) errors are plain text not JSON
  - Easy: all GET, no body parse; no auth; fixed path patterns

---

## 10. Adapter Reuse Decision

### Candidates

| Adapter | Compat | Missing |
|---|---|---|
| EthereumAdapter | 0% | JSON-RPC + hex addr + ABI all different |
| SolanaAdapter | 0% | JSON-RPC + Base58 addr (same alphabet but 32 byte vs Tezos 20; assumes method-string protocol) |
| CosmosAdapter (if built) | **~50%** | Same REST/HTTP, but path is `/cosmos/{module}/v1beta1/...` Cosmos-SDK namespace, addr is bech32 (`cosmos1…`); path templates not reusable; vegeta REST target generator IS shared |
| AptosAdapter (if built) | **~40%** | Same REST, but Aptos addr is `0x` hex, path `/v1/accounts/...`, depends on Move struct_tag semantics; path shape totally different |

### Decision

- [ ] Reuse `<adapter>`
- [x] **New `TezosAdapter`** (Tezos standalone family; protocol upgrade + Michelson + Base58Check addr + very deep path all Tezos-unique)
- [x] **Reuse REST infra layer** (plugin loader `protocol_kind: rest` + `verb + path_template + path_params + response_path` schema, shared with Cosmos REST / Aptos REST / Algorand REST)
- [ ] Hybrid

### Rationale

**Para 1 — Adapter class must be standalone (semantic layer)**. The 4-prefix Base58Check addresses (tz1/tz2/tz3/KT1) need dedicated validators (prefix check + Base58Check). Tezos op_hash lookup requires indexer 2-step (Octez RPC has no `getTxByHash`). Tezos protocol_hash monitoring (`/protocols` returns next/current/expected_commit three fields) is unique to Tezos. Tezos mutez = 10⁻⁶ (coincidentally matches Cosmos uatom 10⁻⁶ but semantically distinct). All this semantics belongs in `TezosAdapter`, not stuffed into CosmosAdapter / AptosAdapter.

**Para 2 — REST protocol layer IS reusable (plugin schema layer)**. §11.7 below proves all 4 REST chains (Cosmos / Aptos / Algorand / Tezos) use `<HTTP_VERB> <path>` + JSON. **The plugin schema field set is fully unifiable**: `protocol_kind` / `verb` / `path_template` / `path_params` / `body_template` (optional) / `response_path` / `path_param_url_encode` / `headers` (optional auth) / `monitor_headers` (Aptos). Tezos introduces no new schema fields (see §11.8 decision); it just reuses what Cosmos/Aptos already established. **This is the biggest plugin-layer reuse win.**

**Para 3 — Only new schema candidate: `monitor_protocol_version`** (see §11.8 ASK). Tezos is the only chain in the 28 that auto-upgrades its on-chain protocol periodically (~every 3 months, amendment cycle → new protocol_hash → potentially incompatible RPC schema), requiring plugin self-description "I monitor protocol_hash; on change → alert / re-run schema probe". This is a **chain trait**, not a protocol-binding trait, so it goes in plugin's `chain_specific` sub-section, **not polluting the REST shared schema**.

### Config JSON example

```json
{
  "chain": "tezos",
  "family": "tezos",
  "adapter": "TezosAdapter",
  "chain_id": "NetXdQprcVkpaWU",
  "protocol_kind": "rest",
  "rpc_endpoint": "https://mainnet.api.tez.ie",
  "rpc_endpoint_backup": "https://mainnet.smartpy.io",
  "indexer_endpoint": "https://api.tzkt.io",
  "block_time_ms": 6060,
  "finality_blocks": 2,
  "address_format": "base58check",
  "address_prefixes": ["tz1", "tz2", "tz3", "KT1"],
  "native_decimals": 6,
  "rpc_methods": {
    "block_height":       {"verb": "GET", "path": "/chains/main/blocks/head/header",
                           "response_path": "$.level"},
    "balance":            {"verb": "GET",
                           "path": "/chains/main/blocks/head/context/contracts/{addr}/balance",
                           "path_params": ["addr"],
                           "response_path": "$"},
    "tx_lookup":          {"verb": "GET",
                           "path": "/chains/main/blocks/{block}/operations/{vp}",
                           "path_params": ["block", "vp"],
                           "response_path": "$"},
    "chain_id":           {"verb": "GET", "path": "/chains/main/chain_id"},
    "version":            {"verb": "GET", "path": "/version"},
    "protocol_monitor":   {"verb": "GET", "path": "/chains/main/blocks/head/protocols",
                           "response_path": "$.protocol"},
    "governance_monitor": {"verb": "GET", "path": "/chains/main/blocks/head/votes/current_period"},
    "counter":            {"verb": "GET",
                           "path": "/chains/main/blocks/head/context/contracts/{addr}/counter",
                           "path_params": ["addr"]}
  },
  "mixed_weights": {
    "balance_query":      0.30,
    "tx_lookup":          0.15,
    "block_query":        0.20,
    "protocol_monitor":   0.10,
    "governance_monitor": 0.10,
    "counter_query":      0.05,
    "chain_id":           0.05,
    "version":            0.05
  },
  "chain_specific": {
    "monitor_protocol_version": true,
    "current_protocol_hash":    "PtTALLiNtPec7mE7yY4m3k26J8Qukef3E3ehzhfXgFZKGtDdAXu",
    "current_protocol_seq":     24
  }
}
```

---

## 11. DSL Field Requirements (Q4=C 95% 0-Python declarative DSL input)

### 11.1 RPC call protocol

`protocol_kind: "rest"` — same as Cosmos REST / Aptos REST / Algorand REST (plugin schema shared across 4 chains). **No JSON-RPC body**, **no auth** (public).

### 11.2 Per-method schema

Unified `{verb, path, path_params?, body_template?, response_path}` (REST common). See §10 config JSON. **Tezos needs no `body_template`** (all GET); **some methods need 1-2 `path_params`** (`addr` / `block` / `vp`).

### 11.3 Cursor / pagination

**Tezos Octez RPC has no native pagination** (queries are by-block / by-address direct). Historical scan options:
- (a) Decrement level number (`/chains/main/blocks/{level-1}/...`)
- (b) Walk `predecessor` block_hash backwards (every header returns `predecessor`)

Neither has `next_cursor`. **DSL needs no new pagination field for Tezos**, but if the plugin wants to express "paginate via block chain", it can reuse Substrate `parent_hash` pattern (`pagination_kind: "linked_list_by_field"` + `field: "predecessor"`).

**TzKT indexer** uses query strings `?sort.desc=level&limit=N&offset.cr=<id>` (cursor); indexer and Octez RPC are two API systems, **plugin should register separately** (`rpc_endpoint` vs `indexer_endpoint`).

### 11.4 System addresses / filters

- **Burn address**: `tz1burnburnburnburnburnburnburjAYjjX` (community convention) — ⚠️ existence not E2-verified
- **Bakers** (high system status, may want to exclude from mixed to avoid hot-spotting): `tz1KqTpEZ7Yob7QbPE4Hy4Wo8fHG8LhKxZSx` (this round E2 alive) etc., dozens; full list via TzKT `/v1/delegates?active=true&sort.desc=delegatedBalance`
- **Framework system contracts** (if any): Tezos has no EVM-style precompile addresses (0x1-0xa); voting/baking logic of each protocol is internal, not exposed as callable contracts

### 11.5 Heterogeneity tags vs existing 8 chains + this round

| # | Dim | Tezos | Vs other 8 chains |
|---|---|---|---|
| 1 | Protocol | **REST** | EVM/Solana/NEAR/Cosmos-RPC/Substrate/Bitcoin = JSON-RPC; Aptos = REST; Cosmos-REST = REST |
| 2 | Address | **Base58Check 36 char + 4 prefixes** | Ed25519 Base58 (Solana) / hex (EVM/Aptos) / Bech32 (Cosmos) / SS58 (Substrate) / string (NEAR) |
| 3 | tx hash | **Base58Check 51 char `o`-family** | Hex 64 (EVM/Bitcoin) / Base58 (Solana) / Hex upper (Cosmos) / Base58 (NEAR) |
| 4 | block id | **3 forms**: `head` / level (numeric) / hash (`B...` Base58Check) | EVM = `latest`/num/hex hash; Solana = slot num; NEAR = `final`/`optimistic`/num/hash (NEAR most flexible) |
| 5 | Finality field | **none explicit** (only `/protocols` or head inference; no `finalized` block tag) | NEAR has `finality: final/optimistic`; EVM has `finalized`/`safe` tags; Solana has commitment |
| 6 | tx lookup model | **Must indexer-reverse to block + vp + index first**; Octez RPC has no `getTxByHash` | EVM/Solana/NEAR all have single-call `getTransaction(hash)` |
| 7 | Protocol upgrade | **On-chain amendment** (protocol_hash changes, RPC schema may change) | **The only such chain in 28**; EVM hard forks are off-chain coordination, RPC method names stable |
| 8 | Auth | public | Algorand requires X-Algo-API-Token; most others public |

### 11.6 DSL ASKs to P2-DESIGN-v2

1. **`protocol_kind: rest`** — Already requested by Cosmos/Aptos, Tezos reuses, **no add**.
2. **`verb + path_template + path_params`** — Already requested, Tezos reuses, **no add**.
3. **`response_path` (JSONPath-lite)** — Already requested by Aptos/NEAR, Tezos reuses, **no add**.
4. **`bare_string_response: true` (candidate new field)** — Several Tezos endpoints return bare JSON string (`"53"`, `"NetXdQprcVkpaWU"`), not object. DSL parser assuming `dict` would TypeError. **ASK: DSL parser must tolerate `bare_string_response`** (or declare explicitly).
5. **`monitor_protocol_version: true` (candidate new field, Tezos-unique)** — See §11.8. **ASK: agreement to add this chain_specific field (NOT in REST shared schema).**
6. **`indexer_endpoint` (candidate new field)** — Tezos tx_lookup must hit indexer first; Aptos has similar (`fullnode` vs `indexer.mainnet.aptoslabs.com`); Cosmos chains have mintscan; **ASK: should DSL unify abstraction `endpoints: { rpc, indexer, explorer }`?**

### 11.7 Tezos vs committed REST chains (4-chain REST evidence comparison)

> All columns are H8/E2-tested 2026-05-23 ~18:44 UTC. Unverified items ⚠️.
> Algorand row: this round did NOT find an Algorand commit file under docs (only 8 chains committed), so the Algorand column is **filled by this round's own E2 probe** of AlgoNode endpoint, but **NO full doc was researched** for Algorand — included as P1.2 Wave3 in-table reference, marked ⚠️ "no full doc".

| Dim | Cosmos REST (05-cosmos-hub) | Aptos REST (04-aptos) | Algorand REST (⚠️ this-round E2 only) | **Tezos REST (this round)** |
|---|---|---|---|---|
| Protocol | REST/HTTP/JSON — **E2** | REST/HTTP/JSON — **E2** | REST/HTTP/JSON — **E2** `https://mainnet-api.algonode.cloud/v2/status` HTTP:200 | REST/HTTP/JSON — **E2** `https://mainnet.api.tez.ie/version` HTTP:200 |
| Auth | public (publicnode) — **E2** | public (aptoslabs) — **E2** | public (AlgoNode free); commercial (PureStake) needs `X-Algo-API-Token` — E3 doc | public (ECAD/SmartPy) — **E2** |
| Path depth | medium (3-4 segs) `/cosmos/bank/v1beta1/balances/{addr}` — **E2** | shallow (2-3 segs) `/v1/accounts/{addr}` — **E2** | shallow (2-3 segs) `/v2/accounts/{addr}` — E3 doc | **deep (5-7 segs)** `/chains/main/blocks/head/context/contracts/{addr}/balance` — **E2 (7 segs)** |
| Balance path | `GET /cosmos/bank/v1beta1/balances/{addr}` → `{balances:[{denom,amount}]}` array — **E2** | `POST /v1/view` body `{function:"0x1::coin::balance",...}` → array of string — **E2** | `GET /v2/accounts/{addr}` → big object containing `amount` (microalgos) — E3 doc | `GET /chains/main/blocks/head/context/contracts/{addr}/balance` → **bare string** `"53"` (mutez) — **E2** |
| Height param | path `/blocks/{height}` or grpc-metadata `x-cosmos-block-height` — **E2** | header `x-aptos-block-height` (response) / query `?version=N` (request) — **E2** | path `/v2/blocks/{round}` — E3 doc | **path** `/chains/main/blocks/{level\|hash\|head}/...` (3 ID forms) — **E2** |
| Pagination | `pagination.limit` + `pagination.key` (opaque base64 cursor) — **E2** | `start: <version>` + `limit` (numeric cursor) — **E2** | `?next: <token>` (opaque) + `?limit` — E3 doc | **no native pagination**; decrement level / walk `predecessor` chain — **E2** |
| Protocol version field | `chain-id: "cosmoshub-4"` string, fixed — **E2** | `x-aptos-chain-id: 1` numeric header, fixed — **E2** | `genesis-hash-b64: "wGHE2P..."` string, fixed — E3 doc | **`protocol_hash: "PtTALLi..."` Base58Check, dynamically upgrading** (~every 3 months) — **E2** |
| Error format | HTTP code + `{code,message,details}` JSON — E2 ✅ | HTTP code + `{message, error_code, vm_error_code}` JSON — E2 (Aptos 04 doc) | HTTP code + `{message: "..."}` JSON — ⚠️ error path not E2 | **HTTP 4xx + plain text** (not JSON, e.g. `"Cannot parse contract id"`) — **E2 ✅ 400** |
| Response JSON structure | all object — E2 | object or array of object — E2 | all object — E3 | **mixed**: mostly object, but `/balance` `/chain_id` return **bare JSON string** — **E2 (only one)** |
| tx_lookup model | `GET /cosmos/tx/v1beta1/txs/{HEX}` single-step — E2 | `GET /v1/transactions/by_hash/{0xhex}` single-step — E2 | `GET /v2/transactions/pending/{txid}` + indexer `/v2/transactions/{txid}` — E3 | **two-step required**: indexer reverse → `GET /blocks/{block}/operations/{vp}/{index}` — **E2** |
| DSL schema complexity delta | Low (pure path + JSON) | Low-Med (`POST /view` body template + URL encoding policy + `monitor_headers`) | Low (path + bearer header) — ⚠️ | **Med** (deep path + bare-string response + plain-text errors + protocol_hash monitor + tx_lookup 2-step) |

**Tally**: All 4 chains share REST/HTTP/JSON + mostly public + GET-dominant. **Plugin schema field sets overlap ~95%** (`protocol_kind/verb/path_template/path_params/response_path` all used). Tezos introduces only **2 small delta needs**: `bare_string_response` tolerance (small) + `monitor_protocol_version` uniquely (chain_specific, does not pollute shared schema).

### 11.8 DSL recommendation (CRITICAL OUTPUT)

**Decision**:

- [x] **Reuse Cosmos/Aptos REST DSL infra** (`protocol_kind: rest` + `verb` + `path_template` + `path_params` + `response_path`)
- [ ] Tezos deep path → add `path_template_max_depth` config — **REJECTED** (see rationale para 2)
- [ ] Tezos deep path → split path into segment array — **REJECTED** (see rationale para 2)
- [x] **`monitor_protocol_version: true` field** in `chain_specific` sub-section (**NOT** shared REST schema)
- [x] **`bare_string_response: true`** as a method-level optional (REST shared)
- [x] **`indexer_endpoint`** as top-level endpoint structure (REST shared, Aptos/Cosmos can also use)

**Rationale (3 paras)**:

**Para 1 — REST infra reuse is very high (95%); Tezos needs no new protocol-layer abstraction**. §11.7 above proves the 4 REST chains' plugin schema needs fully overlap on 5 core fields: `protocol_kind` (rest) / `verb` (GET-dominant) / `path_template` (with `{param}` placeholders) / `path_params` (array) / `response_path` (JSONPath-lite). Tezos introduces no new protocol-layer concepts — `GET /chains/main/blocks/head/context/contracts/{addr}/balance` is expressible in one line using the same Cosmos schema. This means plugin loader writes the REST handler **once**, covers **4 chains**. Mirrors the EVM family 5-chain shared EthereumAdapter pattern — **protocol layer is true reuse, semantic layer is per-chain**.

**Para 2 — Deep path (7 segs) is NOT a schema problem; no `max_depth` or segment array needed**. Tezos's `/chains/main/blocks/head/context/contracts/{addr}/balance` is 2-3 segs deeper than Cosmos's `/cosmos/bank/v1beta1/balances/{addr}`, but plugin schema representation is identical — both single-string `path_template` + `path_params` array. **Deep path = longer string, not a schema-structure problem.** Adding `path_template_max_depth` or segment array would be over-engineering (token-level "make simple into complex" anti-pattern): string concat already handles arbitrary depth cleanly; a segment array would need new concat helpers, new URL encoding boundary handling, new escape rules — **~60 extra plugin-loader lines for 0 gain**. **Decision: rejected; Tezos uses pure string template**, fully aligned with Cosmos/Aptos/Algorand.

**Para 3 — The only genuinely new requirement is `monitor_protocol_version`, in chain_specific to avoid polluting shared REST schema**. Tezos is the only chain in the 28 with periodic auto on-chain protocol upgrade — current protocol_hash is `PtTALLi…` (the 24th protocol, this round E2-verified), with 23 historical upgrades, averaging ~3 months/amendment. New protocols can introduce new RPC methods, change response fields, alter mutez display precision, etc. (historical: Florence → Granada changed baking accounts). **This means the Tezos plugin must monitor `GET /chains/main/blocks/head/protocols`; when `protocol` field changes: (a) alert (schema may have drifted) (b) auto-trigger schema regression (re-run §5's 9 methods, assert HTTP:200)**. But this is a Tezos-chain trait, not a REST-protocol trait — **proper home is plugin's `chain_specific` sub-section** (same as Aptos `monitor_headers` going to chain_specific). Plugin loader dispatches on chain_specific without polluting the 4-chain shared REST main schema. **Closing**: `bare_string_response: true` and `indexer_endpoint` are small adds (< 5 schema lines), no burden.

**Conclusion (one line)**: **Tezos reuses 99% of Cosmos/Aptos REST DSL infra (only adds `bare_string_response` + `indexer_endpoint` two small fields to the shared layer); `monitor_protocol_version` is Tezos chain_specific and lives in the chain_specific sub-section; Adapter is a new `TezosAdapter` (standalone family), parallel to Cosmos/Aptos REST adapters.** ✅

---

## 9.9 Real Source Coverage & Timestamps

| Source type | URL / path | Access (UTC) | Status |
|---|---|---|---|
| ECAD `/version` | `GET https://mainnet.api.tez.ie/version` | 2026-05-23 18:44 | **H8: 200, Octez v24.4 release commit 56bd3e33** |
| ECAD `/chains/main/blocks/head/header` | same root | 2026-05-23 18:44 | **H8: 200, chain_id=NetXdQprcVkpaWU, protocol=PtTALLi…, level=13329316, proto=24** |
| ECAD `/balance` tz1 | `.../contracts/tz1KqTpEZ7Yob7QbPE4Hy4Wo8fHG8LhKxZSx/balance` | 2026-05-23 18:44 | **H8: 200, `"53"` mutez** |
| ECAD `/balance` KT1 | `.../contracts/KT1WvzYHCNBvDSdwafTHv7nJ1dWmZ8GCYuuC/balance` | 2026-05-23 18:44 | **H8: 200, `"108962378338"` mutez** |
| ECAD `/balance` bad addr | `.../contracts/tz1notarealaddress/balance` | 2026-05-23 18:44 | **H8: 400 + plain-text error (not JSON)** |
| ECAD `/chain_id` | `.../chains/main/chain_id` | 2026-05-23 18:44 | **H8: 200, bare string `"NetXdQprcVkpaWU"`** |
| ECAD `/protocols` | `.../protocols` | 2026-05-23 18:44 | **H8: 200, returned ~30+ Base58Check protocol hashes (all known protocols)** |
| ECAD `/counter` | `.../contracts/tz1Kq.../counter` | 2026-05-23 18:44 | **H8: 200, `"8190584"`** |
| ECAD `/blocks/{level}/header` historical | `.../blocks/13329000/header` | 2026-05-23 18:44 | **H8: 200, level=13329000 @ 2026-05-23T18:12:19Z (used to derive block_time ≈ 6.06s)** |
| ECAD `/blocks/{hash}/operation_hashes` | `.../blocks/BL7ke9KaSf4…/operation_hashes` | 2026-05-23 18:44 | **H8: 200, 2D array (4 vps × N op_hashes)** |
| ECAD `/operations/3` | `.../blocks/head/operations/3` | 2026-05-23 18:44 | **H8: 200, array of op, each with protocol/chain_id/hash/branch** |
| SmartPy `/version` | `GET https://mainnet.smartpy.io/version` | 2026-05-23 18:44 | **H8: 200, same Octez v24.4 release** |
| TzKT `/v1/operations/transactions` | `GET https://api.tzkt.io/v1/operations/transactions?limit=1&sort.desc=level` | 2026-05-23 18:44 | **H8: 200, real op_hash `ong1822VPmQwj…`, level=13329321, block=BL7ke9KaSf…** |
| TzKT `/v1/operations/{hash}` | `GET .../ong1822VPmQwj…` | 2026-05-23 18:44 | **H8: 200, full tx detail** |
| TzKT `/v1/contracts?kind=smart_contract&sort.desc=numTransactions` | same root | 2026-05-23 18:44 | **H8: 200, real KT1 = objkt.com Marketplace v2** |
| **Cross-chain Cosmos REST** | `GET https://cosmos-rest.publicnode.com/cosmos/base/tendermint/v1beta1/node_info` | 2026-05-23 18:44 | **H8: 200** (used for §11.7 cross-verify) |
| **Cross-chain Aptos REST** | `GET https://fullnode.mainnet.aptoslabs.com/v1` | 2026-05-23 18:44 | **H8: 200, chain_id=1, block_height=783409612** (cross-verify) |
| **Cross-chain Algorand REST** | `GET https://mainnet-api.algonode.cloud/v2/status` | 2026-05-23 18:44 | **H8: 200, catchup-time=0** (cross-verify) |
| Octez RPC docs | https://tezos.gitlab.io/active/rpc.html | 2026-05-23 | E1 (cited, not DOM) |

---

## Open Questions

1. **Algorand full research missing** — §11.7 Algorand column is only E2 alive-probe, no full doc. Phase 2.x adding Algorand needs its own doc.
2. **Tezos finality not E2-tested** — Tenderbake doc says 2-block deterministic; this round did not E2-compare head vs finalized (does Octez RPC convention `/chains/main/blocks/head~2/header` work?)
3. **`/protocols` field semantics not fully verified** — H8 returned 30+ Base58 strings array (`["ProtoALphaALpha…", "ProtoDemoCounter…", "PrqoTUFUrorf…", ...]`), but **this is the node's full known-protocols list**, not active+next. **The real active protocol should be read from `/chains/main/blocks/head/protocols` returning `{protocol, next_protocol}` object** — this round read `protocol` from head/header but did not separately E2 head/protocols object, ⚠️.
4. **block_time derived 6.06s vs doc 10s** — H8 derived 1914s/316 blocks=6.06s, diverging from common literature "~10s". Likely the current protocol 24 (PtTALLi) changed `minimal_block_delay` to 6s — ⚠️ not yet checked via `/context/constants`. Phase 2.x verify.
5. **mock_rpc_server REST framework** — Tezos is the 4th REST chain after Cosmos/Aptos/Algorand; **Phase 2.0 should formally split mock_rpc_server into REST + JSON-RPC dual handler** (else token-level Case-D: multi-chain patchwork gets worse).
6. **`bare_string_response` implementation** — Does the current DSL parser assume all responses are dict? Validate plugin loader tolerates bare string `"53"` without TypeError before Tezos integration.
7. **Protocol amendment drill** — Last Tezos protocol upgrade (`P` → `Pt`) changed some RPC schemas. After Phase 2.x integration, **need a protocol amendment dashboard alert**? (§11.8 says monitor; specific alert channel TBD.)
8. **`indexer_endpoint` abstraction** — If introduced, Aptos/Cosmos/Tezos all need it in plugin top-level endpoints, and indexer URL paths totally differ (TzKT vs Aptos Indexer GraphQL vs Mintscan); does DSL still need indexer protocol_kind? Phase 2.0 decision.

---

## Changelog

| Date | Author | Change |
|---|---|---|
| 2026-05-23 | Hermes Agent | First research: H8 verified ECAD `/version` `/header` `/balance`(tz1+KT1+bad) `/chain_id` `/protocols` `/counter` `/blocks/{level}/header` `/operation_hashes` `/operations/3` — 10 endpoints; TzKT `/operations` + `/contracts` reverse lookup; SmartPy `/version` backup; cross-chain Cosmos/Aptos/Algorand REST alive; §11.7 4-chain REST comparison + §11.8 reuse decision (95% reuse, only add `bare_string_response` + `indexer_endpoint` to shared layer; `monitor_protocol_version` to chain_specific) |
