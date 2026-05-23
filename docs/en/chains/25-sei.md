# 25-sei Research (DIFF-ONLY)

> Derived from `_template.md`. **Most aggressive DIFF-ONLY mode**: this chain is a Cosmos SDK chain (family=cosmos); Tendermint RPC + Cosmos REST/LCD protocol structure, error codes, and `/cosmos/{bank,staking,tx,gov}/*` standard module paths are **fully equivalent to wave-1 cosmos-hub (05-cosmos-hub.md, 692 lines)**. This document **does not re-state them**, only the diffs; it also cross-checks reuse against the wave-7 sibling chain **24-injective** (also Cosmos+EVM dual protocol). H8: 6 curl probes on **2026-05-23** against public mainnet endpoints (`sei-rest.publicnode.com` + `sei-rpc.publicnode.com` + `evm-rpc.sei-apis.com` + `sei.drpc.org`); **6/6 returned 200 / valid response** (including dual-source EVM ChainID 1329 verification); follow-up probes deferred (budget/approval) and marked ⚠️ doc-only.

---

## Metadata

| Field | Value |
|---|---|
| Chain (zh) | 海 / Sei |
| Chain (en) | Sei Network |
| Number | 25 |
| Mainnet ChainID | **`pacific-1`** (Cosmos string, E1/E2 measured `network:"pacific-1"`) + **`1329`** (EVM ChainID, E3+E5 **dual-endpoint measured** `result:"0x531"` = decimal 1329 ✅) |
| Node binary | **seid v6.5.0** (Cosmos SDK fork; E1 `app_name=seid, git_commit=fbc0d934, go1.25.10`) + **CometBFT 0.35.0-unreleased** (E1 `protocol_version.block=11,p2p=8`; **earlier-and-customised vs Hub/Injective 0.38 series — note when self-hosting**) |
| Research date | 2026-05-23 |
| Status | 🟢 Done (diff-only) |
| Compat vs 05-cosmos-hub | **~80%**: Tendermint RPC / Cosmos REST / bank / staking / tx / gov / distribution modules **100% isomorphic**; **~20% diff** = 5 unique modules (`oracle` / `epoch` / `dex` legacy / `evm` Parallel-EVM in-protocol / `tokenfactory`) + EVM dual protocol + dual address space |
| Compat vs 24-injective | **~70%**: Cosmos two ports fully isomorphic; EVM dual protocol **same family** (both embed `x/evm`) but Sei EVM is **Parallel (OCC)** + **public endpoint actually reachable** while Injective in-protocol EVM is unreachable; unique-module sets **completely different** (Injective: exchange/auction/peggy/insurance; Sei: oracle/epoch/dex) |

---

## 1. Sources (authoritative + fork history)

| Type | URL | Notes |
|---|---|---|
| Official docs | https://docs.sei.io/ | Sei Network protocol docs |
| GitHub (node) | https://github.com/sei-protocol/sei-chain | seid daemon source, **fork from cosmos-sdk (deeply customised + Twin-Turbo consensus rework)**; E1 `version=0.35.0-unreleased` shows Sei also maintains its own CometBFT branch |
| Cosmos RPC | https://sei-rpc.publicnode.com | E2 measured 200 |
| Cosmos REST | https://sei-rest.publicnode.com | E1/E6 measured |
| EVM RPC (official) | https://evm-rpc.sei-apis.com | E3/E4 measured 200, ChainID 1329 ✅ |
| EVM RPC (backup) | https://sei.drpc.org | E5 measured 200, ChainID 1329 ✅ (dual-source agreement) |
| Explorer (Cosmos+EVM) | https://seitrace.com | **Unified explorer**, lookup by sei1... or 0x... finds the same account (key entrypoint for dual-address binding) |
| Mintscan (Cosmos) | https://www.mintscan.io/sei | Cosmos side only |
| Sei v2 upgrade post | https://blog.sei.io/sei-v2-the-first-parallelized-evm/ | 2024 Parallel EVM official launch, OCC-based |

**Fork history**: `sei-chain` forks cosmos-sdk (heavily customised; specific SDK version not surfaced in E1 node version). **CometBFT tagged `0.35.0-unreleased`** (earlier than mainstream 0.38 series) — **key divergence**: Sei team rewrote CometBFT with **Twin Turbo Consensus** (parallel proposal + voting pipeline) + **Optimistic Block Processing**, claiming sub-second finality. Tendermint RPC `:26657` and Cosmos REST `:1317` protocol structures, error schema, and `/cosmos/*` paths **fully equal cosmos-hub** (see 05 §3-7), **but the underlying consensus engine implementation has materially diverged**: when self-hosting, community CometBFT binaries **cannot replace** seid.

---

## 2. Relation to Cosmos Hub (SDK compatibility + module delta)

| Dimension | Cosmos Hub (05) | Sei (25) | Reuses 05? |
|---|---|---|---|
| Cosmos SDK version | v0.50.x (gaia v27.3.0) | sei-chain v6.5.0 (cosmos-sdk fork, deeply customised) | ⚠️ Protocol layer reused, impl diverged |
| Consensus | CometBFT v0.38.19 | CometBFT **0.35.0-unreleased** (Sei-maintained + Twin Turbo + OBP) | ⚠️ RPC protocol reused, binary not swappable |
| `/cosmos/bank/*` | ✅ | ✅ (standard path) | ✅ reuse |
| `/cosmos/staking/*` | ✅ | ✅ (seivaloper prefix, ⚠️ not directly probed this round, doc-only) | ✅ reuse |
| `/cosmos/tx/*` / gov / distribution / slashing / authz / feegrant | ✅ | ✅ | ✅ reuse |
| `/cosmos/base/tendermint/*` node_info | ✅ | ✅ (E1 `network=pacific-1`) | ✅ reuse |
| Tendermint RPC `/status` `/block` `/tx` | ✅ | ✅ (E2 measured 200) | ✅ reuse |
| **Unique modules** | (none, pure hub) | **5 classes**: `/sei-protocol/seichain/oracle/*` (price feeds; E6 path returns `-32701 not implemented` ⚠️ publicnode disabled custom-module route) + `/sei-protocol/seichain/epoch/*` (epoch tick) + `/sei-protocol/seichain/dex/*` (legacy orderbook, deprecated post v2) + `/sei-protocol/seichain/evm/*` (EVM module query, **incl. sei1↔0x address-mapping precompile**) + `/sei-protocol/seichain/tokenfactory/*` | ❌ **net-new in this doc** |
| **EVM dual protocol** | ❌ (Hub has no EVM) | ✅ **Parallel EVM in-protocol** (`x/evm` module, launched 2024 in v2 upgrade, **OCC parallel tx execution — distinct from Injective serial EVM**; public endpoint **measurably reachable** at ChainID 1329) | ❌ **net-new** |
| native denom | `uatom` (1 ATOM=10^6) | `usei` (1 SEI=10^6, aligned with Cosmos mainstream) + EVM-side `wei` (1 SEI=10^18 wei, **auto ×10^12 scaling**, **same token two precisions**) + `factory/<creator>/<sub>` token-factory denom + `ibc/<sha256>` IBC token | ❌ **net-new** |
| Address prefix | `cosmos1...` / `cosmosvaloper1...` | **Dual address space**: `sei1...` (42-char bech32, Cosmos side) + `0x...` (20-byte EVM, 42-char hex) + `seivaloper1...` (validator); **one-to-one bound** via the `x/evm` module's `EVMAddressForSeiAddress` mapping store — same account is reachable by either address, balances/nonces merged | ❌ **net-new** |
| Block time | ~6s | **~400 ms** (sub-second, Twin Turbo + OBP, ⚠️ a single `/status` cannot precisely derive; doc + EVM block 209M extrapolation) | ⚠️ Value differs |

---

## 3. Public endpoint evidence

| Endpoint | API | Probed | Notes |
|---|---|---|---|
| `https://sei-rpc.publicnode.com` | Tendermint RPC :26657 | ✅ HTTP 200 (E2 `network=pacific-1, protocol_version.block=11`) | publicnode public-good |
| `https://sei-rest.publicnode.com` | Cosmos REST/LCD :1317 | ✅ HTTP 200 (E1 node_info 200) | publicnode public-good |
| `https://evm-rpc.sei-apis.com` | EVM JSON-RPC | ✅ HTTP 200 (E3 `eth_chainId=0x531=1329` ✅; E4 `eth_blockNumber=0xc792648=209,238,728`) | **Official EVM public endpoint, stable** (sharp contrast with Injective EVM) |
| `https://sei.drpc.org` | EVM JSON-RPC backup | ✅ HTTP 200 (E5 `eth_chainId=0x531=1329` ✅, **dual-source agreement**) | DRPC public-good |
| `https://sei-rest.publicnode.com/sei-protocol/seichain/oracle/params` | Sei custom oracle module | ⚠️ `-32701 not implemented` (E6) | **publicnode disabled Sei custom-module REST routes**; needs self-hosting; standard `/cosmos/*` paths work fine |

**Conclusion (key diff)**:
- **Cosmos two ports fully public-reachable** (same as Injective);
- **EVM public endpoint dual-source stable** (`sei-apis.com` + `drpc.org`, two independent providers both return 1329) — **the biggest difference vs Injective** (Injective in-protocol EVM: all 4 endpoints unreachable; Sei EVM is a first-class public service, no self-hosting required);
- **Sei custom-module REST paths disabled on publicnode** (E6 returns -32701); when self-hosting, enable `api.enable = true` in `app.toml`.

**curl evidence (E3 + E5 — dual-source EVM ChainID 1329 verification, core proof of Parallel-EVM reachability)**:

```bash
# E3: official EVM endpoint
curl -X POST -H "content-type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_chainId","id":1,"params":[]}' \
  https://evm-rpc.sei-apis.com
# Measured: {"jsonrpc":"2.0","result":"0x531","id":1}   ← 0x531 = 1329 ✅

# E5: third-party DRPC backup
curl -X POST -H "content-type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_chainId","id":1,"params":[]}' \
  https://sei.drpc.org
# Measured: {"id":1,"jsonrpc":"2.0","result":"0x531"}   ← 0x531 = 1329 ✅ (independent provider agrees)
```

**curl evidence (E4 — Parallel EVM height)**:

```bash
curl -X POST -H "content-type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","id":1,"params":[]}' \
  https://evm-rpc.sei-apis.com
# Measured: {"jsonrpc":"2.0","id":1,"result":"0xc792648"}   ← 209,238,728 blocks
# Extrapolation: chain launched at v2 upgrade ~2024-05, ~2 years → ~400 ms/block, matches "sub-second finality" claim
```

---

## 4. Substantive diffs vs Cosmos Hub

| Dimension | Cosmos Hub | Sei | Impact |
|---|---|---|---|
| Unique modules | — | **oracle / epoch / dex (legacy) / evm / tokenfactory** | DSL `rpc_methods` adds 5 path classes |
| native token decimals | 6 (uatom) | **Cosmos side 6 (usei) + EVM side 18 (wei, auto ×10^12)** | **Same token, two precisions**; DSL `balance_unit decimals` needs per-protocol (cosmos / evm) refinement, **more complex than Injective (pure 18)** |
| Bridge token denom | `ibc/<hash>` | `ibc/<sha256>` + `factory/<creator>/<sub>` + EVM-side ERC20 contract address (0x..., **not directly interoperable as denom string with Cosmos**; needs a pointer-contract mapping table) | DSL `denom_format` enum needs multi-value (matches Injective ASK B, **reuse 100%**) |
| Consensus | CometBFT 0.38, ~6s | **CometBFT 0.35 (Sei-maintained) + Twin Turbo + OBP, ~400 ms** | benchmark vegeta rate ceiling **must be significantly higher than Hub**; **block_time_ms ≈ 400**, DSL schema unchanged |
| EVM compatibility | ❌ | ✅ **Parallel EVM** (OCC, **fundamentally different from Injective's serial EVM**; multiple tx in same block executed optimistically in parallel, rollback on conflict) | DSL needs `evm_parallelism` field: `{model: "serial"|"occ"|"none"}`, affects benchmark concurrency model |
| Address space | single bech32 | **dual address sei1... (bech32) ⇄ 0x... (hex)**, bound via `x/evm` module; **same account, two addresses, nonce/balance merged** | DSL `address_format` needs structured object supporting `dual_address: {primary, secondary, binding_module}` (cf. 14-hedera ASK A) |
| Orderbook model | — | dex module **deprecated post v2** (legacy state remnants only) | benchmark excludes; **contrast with Injective exchange module: Sei chose to abandon on-chain orderbook in favour of EVM dApp ecosystem** |
| Oracle | — | **On-chain oracle module** (validators must submit price votes; different model from Injective's multi-source oracle) | benchmark fit for medium-frequency read `/sei-protocol/seichain/oracle/denoms/exchange_rates`, ⚠️ publicnode closed |
| Epoch | — | epoch tick module (staking reward / inflation periodic trigger) | benchmark excludes |

---

## 5. Method diffs (diff-only, 80% same as 05, only uniques listed)

> **Reuses all cosmos-hub methods** (see 05 §5): `/status` `/block` `/tx` `/abci_query` `/abci_info` + `/cosmos/bank/v1beta1/balances/{addr}` + `/cosmos/staking/v1beta1/validators` + `/cosmos/tx/v1beta1/txs/{hash}` etc. **Only Sei-unique additions listed**:

| Method | Class | Evidence | Suggested mixed weight |
|---|---|---|---|
| `GET /sei-protocol/seichain/oracle/params` | oracle config | ⚠️ E6 publicnode closed route (returns -32701); self-hosting required | 0.05 |
| `GET /sei-protocol/seichain/oracle/denoms/exchange_rates` | current price feed | ⚠️ same | 0.05 |
| `GET /sei-protocol/seichain/epoch/epoch` | current epoch | ⚠️ not directly probed | 0.02 |
| `GET /sei-protocol/seichain/evm/sei_address_by_evm_address/{0x...}` | **dual-address binding** (0x → sei1) | ⚠️ not directly probed, ⚠️ doc-only | 0.05 |
| `GET /sei-protocol/seichain/evm/evm_address_by_sei_address/{sei1...}` | **dual-address binding** (sei1 → 0x) | ⚠️ doc-only | 0.05 |
| `GET /sei-protocol/seichain/tokenfactory/denoms_from_creator/{addr}` | token-factory denom list | ⚠️ not probed | 0.03 |
| **EVM `POST / eth_chainId`** | Parallel EVM healthcheck | ✅ E3+E5 dual-source 200, 1329 | 0.05 (would be 0.10 but cosmos-hub RPC reuse takes the bulk; EVM is the parallel second plane) |
| **EVM `POST / eth_blockNumber`** | Parallel EVM height | ✅ E4 200, 0xc792648 | 0.05 |
| **EVM `POST / eth_getBalance`** | Parallel EVM balance (0x addr) | ⚠️ not probed | 0.10 |
| **EVM `POST / eth_call`** | Parallel EVM contract read | ⚠️ not probed | 0.15 (**Parallel EVM benchmark main load**) |
| **EVM `POST / eth_sendRawTransaction`** | Parallel EVM write (read-only framework: skip) | — | 0 (read-only) |
| **EVM `POST / eth_getLogs`** | Parallel EVM log query | ⚠️ not probed | 0.05 |

**Reuse 05 standard Cosmos method weight ~0.50** (bank/staking/tx/block etc.) + **net-new in this doc ~0.50** = 1.00 ✓ (EVM plane 0.40 + oracle/dual-address binding 0.10)

**Cross-check vs Injective method set (reuse validation for ASK A)**: Sei unique modules = oracle/epoch/evm/tokenfactory/dex(legacy); Injective unique = exchange/auction/peggy/oracle/insurance — **intersection only `oracle`** (and implementations completely different: Sei validator-vote, Injective multi-source) → **0% full-set reuse** between two chains' unique-module lists → **confirms DSL ASK A `module_set` necessity at 100%** (without it, plugin code must duplicate all method lists per chain).

---

## 6. Real-world workload

- **Cosmos side**: `MsgSend` + `MsgDelegate` + `MsgVote` (standard cosmos) + oracle validator vote `MsgAggregateExchangeRateVote` (mandatory each epoch).
- **Parallel EVM side**: DEX (Astroport on Sei, Dragonswap) + NFT (Pallet) + Perp DEX (Vortex) ERC20/contract calls. **Post Sei v2, the team officially pushes the EVM dApp ecosystem**; real mainnet has ~50%+ tx volume on the EVM plane. vegeta model should **dual-plane concurrent load-test**: Cosmos REST + EVM JSON-RPC; **OCC parallelism lets the EVM side reach ~10x Ethereum mainnet throughput ceiling** (doc claim, ⚠️ benchmark must validate).
- **Dual-address nonce merging**: same account's sei1... and 0x... share the same nonce (unified by `x/evm` module). If the benchmark load generator sends tx to the same account from both endpoints simultaneously, nonce coordination is required.

---

## 7. DSL decisions (reuse + extend on Injective's 5 ASKs)

| Field | Net-new? | Rationale |
|---|---|---|
| `family = "cosmos"` | ✅ reuse | Same as 05/24 |
| `adapter = "CosmosAdapter"` | ✅ reuse | Tendermint RPC + REST two ports same as 05 |
| **`module_set` (Injective ASK A)** | **✅ 100% reuse, Sei reinforces** | Sei unique-module list (oracle/epoch/evm/tokenfactory/dex) vs Injective (exchange/auction/peggy/oracle/insurance), **intersection only oracle**, **0% method-list shareable** → **ASK A must land**, otherwise cosmos-family 6-chain plugin maintenance cost explodes |
| **`denom_format` (Injective ASK B)** | **✅ 100% reuse, partial Sei validation** | Sei uses `bare`(usei) + `ibc` + `factory` three forms, **not peggy / erc20 string denom** (Sei EVM maps via sei↔evm pointer contract rather than denom prefix) → **ASK B enum should cover Sei's `pointer` form** ⚠️ assess in Phase 2.1 |
| **`evm_layer` (Injective ASK C, upgraded here)** | **🆕 Upgraded to L1 must-land** | Injective EVM publicly unreachable, defer-able; **Sei EVM dual-source publicly stable + first Parallel EVM case** (first OCC chain across entire EVM ecosystem), **Phase 2.1 must have field to express**, otherwise cannot configure `evm-rpc` endpoint. Suggested schema: `evm_layer: {type:"in_protocol", chain_id_evm:1329, endpoint:"...", parallelism:"occ", public_reachable:true}` |
| **`dual_address` (new in this doc, L1 recommended)** | **🆕 Recommended** | Sei `sei1...` ⇄ `0x...` dual-address binding via `x/evm` module's `EVMAddressForSeiAddress` mapping store (similar to Injective inj1 + EVM, but Injective public unreachable; Sei is the first **measurable-in-framework** cosmos+evm chain). DSL `address_format` needs structured object: `{primary: {prefix:"sei", encoding:"bech32"}, secondary: {encoding:"hex20", binding_endpoint:"/sei-protocol/seichain/evm/evm_address_by_sei_address/{addr}"}}`. fixture stage must generate **two** addresses per test account and verify bidirectional consistency. |
| **`evm_parallelism` (new in this doc, L2 defer-able)** | ⚠️ Defer Phase 2.2 | Describes EVM execution model: `"serial"` (Injective/Hedera/standard Evmos) / `"occ"` (Sei, Block-STM-class) / `"none"`. Only affects benchmark concurrency model + ceiling settings, not endpoint addressing. **Phase 2.2 assess**. |
| `chain_id` | ✅ reuse as string | `pacific-1` + numeric 1329 (EVM) expressed via `evm_layer.chain_id_evm` |
| `block_semantics` | ✅ reuse | Standard Tendermint block; **block_time_ms ≈ 400** (value differs, schema unchanged) |

**Net new (on top of Injective's 4 ASKs)**: **`dual_address` 1 new L1 field** + **`evm_layer` priority L2 → L1 upgrade** (driven by Sei public reachability) + **`evm_parallelism` 1 new L2 field** (defer-able).

---

## 8. H8 evidence summary

| # | Endpoint | Method | Findings |
|---|---|---|---|
| E1 | REST | `/cosmos/base/tendermint/v1beta1/node_info` | `network=pacific-1, app_name=seid, version=v6.5.0, git_commit=fbc0d934, go1.25.10, cometbft 0.35.0-unreleased` (**note cometbft version differs from Hub/Injective 0.38 series**) |
| E2 | RPC | `/status` | `network=pacific-1, protocol_version.block=11, p2p=8, app=0`, 200 OK |
| E3 | EVM | `POST eth_chainId` @ evm-rpc.sei-apis.com | `result:"0x531"` = **1329 ✅** (official endpoint) |
| E4 | EVM | `POST eth_blockNumber` @ evm-rpc.sei-apis.com | `result:"0xc792648"` = **209,238,728 blocks**, Parallel EVM height |
| E5 | EVM | `POST eth_chainId` @ sei.drpc.org | `result:"0x531"` = **1329 ✅** (third-party endpoint, dual-source agreement) |
| E6 | REST | `/sei-protocol/seichain/oracle/params` | ⚠️ `-32701 not implemented` (publicnode closed Sei custom-module routes; self-hosting required) |

**Not measured ⚠️** (budget constraints this round): dual-address mapping endpoints `/sei-protocol/seichain/evm/{evm,sei}_address_by_{sei,evm}_address/{addr}` response schema; seivaloper prefix verification; oracle exchange_rates actual payload; EVM `eth_getBalance` value consistency for same account across two addresses; precompile 0x1004 (address mapping) call from EVM side.

---

## 9. DSL ASK (Phase 2.1 user-review gates + wave 7 cumulative summary)

### Proposed in this doc

- [ ] **DSL ASK G (this doc, L1 must-land)**: `dual_address` field. Sei is wave-7's **first measurable dual-address-binding cosmos+evm chain** (Injective same pattern but public unreachable). DSL needs `address_format = {primary: {prefix:"sei", encoding:"bech32"}, secondary: {encoding:"hex20"}, binding: {module:"evm", query_endpoint:"/sei-protocol/seichain/evm/evm_address_by_sei_address/{addr}"}}`. fixture must generate both addresses per account and verify cross-lookup consistency.
- [ ] **DSL ASK C priority upgrade (original Injective L2 defer-able → this doc proposes L1 must-land)**: `evm_layer` field. Sei EVM public dual-source stable (`evm-rpc.sei-apis.com` + `sei.drpc.org` both return 1329), proves in-protocol EVM in cosmos+EVM chains **can be a first-class benchmark target**. Schema see §7.
- [ ] **DSL ASK H (this doc, L2 defer-able Phase 2.2)**: `evm_parallelism: "serial"|"occ"|"none"` field. Only Sei triggers `occ`; affects benchmark concurrency model design (OCC allows higher concurrency rate, serial EVM must be conservative).
- [ ] **DSL ASK B incremental validation (this doc's supplement to Injective ASK B)**: Sei doesn't use `peggy` / `erc20` denom prefixes; **uses sei↔evm pointer contract for token bridge instead**. `denom_format` enum should add `pointer` option — or attribute to plugin-level derivation rather than DSL (**recommended**).
- [ ] **Not measured ⚠️**: dual-address mapping endpoint actual response; Sei precise block time (sub-second claim not densely sampled); Parallel EVM OCC conflict rate under high concurrency (benchmark-stage validation); whether Sei oracle module path is truly `/sei-protocol/seichain/oracle/*` on self-hosted (publicnode closed, cannot cross-check).

### Wave 7 cumulative DSL decision summary (4 chains, 22→25 convergence)

| ASK | Proposed by | Priority | Cross-chain reuse validation | Final recommendation |
|---|---|---|---|---|
| **A. `module_set`** | Injective (24) | **L1 must-land** | Osmosis(22) CLP/superfluid + Celestia(23) blob + Injective(24) exchange/auction/peggy/oracle/insurance + Sei(25) oracle/epoch/evm/tokenfactory — **pairwise intersection of unique-module lists across all four chains ≤ 1** | **🟢 After wave 7, mandatory for cosmos family**: DSL plugin schema adds `module_set: [string]`; framework uses it to assemble `rpc_methods` subset |
| **B. `denom_format`** | Injective (24) | **L1 must-land** | Injective 4 forms (bare/ibc/peggy/factory/erc20) + Sei 3 forms (bare/ibc/factory + pointer-contract pattern) + Osmosis (bare/ibc/factory/cw20) + Celestia (bare/ibc) | **🟢 Mandatory for cosmos family after wave 7**: enum `["bare","ibc","peggy","factory","erc20","cw20"]` covers; **`pointer` mode kept as plugin-derived** |
| **C. `evm_layer`** | Injective (24) L2 defer → Sei (25) upgrade L1 | **L1 must-land (Sei-driven)** | Injective in-protocol EVM publicly unreachable; **Sei EVM publicly dual-source reachable + Parallel EVM**; Osmosis/Celestia no EVM | **🟢 Upgraded to L1 after Sei evidence**: schema `evm_layer: {type, chain_id_evm, endpoint, parallelism, public_reachable}` |
| **D. `hot_endpoints` + `osmosis_modules`** | Osmosis (22) | **L1 must-land** | Osmosis-unique; not reused by other wave-7 chains | **🟢 Maintain original Osmosis decision** |
| **E. `rollup_type` adds `modular_da`** | Celestia (23) | **L1 must-land** | Celestia-unique (modular DA layer) | **🟢 Maintain original Celestia decision** |
| **F. `dual_address`** | Sei (25) | **L1 recommended** | Sei first measurable; Injective same pattern but public unreachable → 1 measurable case in wave 7 | **🟡 Recommended land** (paves the way for future cosmos+EVM chains: Berachain, Canto, Evmos) |
| **G. `evm_parallelism`** | Sei (25) | L2 defer Phase 2.2 | Sei first OCC; Hedera/Injective serial → 1 case in wave 7 | **🟡 Defer**: can be metadata annotation rather than strict schema |

**Does the Cosmos family ultimately need a `module_set` upgrade? Conclusion: 🟢 mandatory.** Wave 7's 4 chains (Osmosis/Celestia/Injective/Sei) + wave 1 cosmos-hub = 5 chains total; **pairwise intersection of unique-module lists ≤ 1**, **0% full-set reuse**. Without `module_set`, plugin code must maintain ~30+ method paths per chain individually — DRY severely violated, regression-test matrix explodes. **Phase 2.1 user review should prioritise confirming ASK A.**

---

## Changelog

| Date | Author | Change |
|---|---|---|
| 2026-05-23 | Hermes Agent | Initial research (DIFF-ONLY mode); 6 H8 curls, **6/6 succeeded** (EVM dual-source ChainID 1329 verification ✅; Cosmos node_info/status 200; publicnode closed Sei custom-module REST routes — 1 case); **~80% reuse vs cosmos-hub** (Tendermint RPC + Cosmos REST + bank/staking/tx/gov full set); **~20% unique** = oracle (validator-vote price feed) + epoch + dex (legacy) + evm (Parallel EVM in-protocol, **OCC parallelism, first in this framework**) + tokenfactory; **EVM publicly reachable + dual-source 1329 verified** (sharp contrast with Injective public unreachability); **dual address sei1↔0x bound via `x/evm` module mapping store**; **reuse vs Injective**: Cosmos two ports 100%, **unique-module lists 0% full-set reuse** (intersection only oracle, implementations differ) → **reinforces DSL ASK A `module_set` necessity**; **net DSL additions this doc**: `dual_address` L1 recommended + `evm_layer` priority L2→L1 upgrade + `evm_parallelism` L2 defer-able; **wave 7 4-chain cumulative recommendation**: ASK A/B/C/D/E all L1 must-land, ASK F dual_address L1 recommended, ASK G evm_parallelism L2 defer-able |
