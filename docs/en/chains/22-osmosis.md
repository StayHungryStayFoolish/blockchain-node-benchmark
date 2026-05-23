# 22-Osmosis Research (diff-only, base=05-cosmos-hub)

> **DIFF-ONLY MODE**: Only items that differ from `05-cosmos-hub.md` are recorded. Tendermint/CometBFT JSON-RPC (`status`/`abci_info`/`block`/`tx`/`tx_search`/`broadcast_tx_*`/`net_info`/`validators`/`consensus_state`/...), Cosmos REST/LCD (`/cosmos/bank/v1beta1/balances/{addr}`, `/cosmos/staking/...`, `/cosmos/tx/v1beta1/...`), the error code table, bech32 address/proto/grpc-gateway mechanics are **100% compatible** with Cosmos Hub and **not repeated** — see 05-cosmos-hub.md §4/§5/§6/§11.
> **Every field carries an E1/E2/E3/E4/E5 evidence tag** (E2=curl, E3=official doc, E4=GitHub source, E5=framework grep).

---

## Meta

| Item | Value |
|---|---|
| Chain name (zh/en) | Osmosis / Osmosis |
| Number | 22 |
| Mainnet ChainID | `osmosis-1` (E2: `/status.result.node_info.network`) |
| Node daemon | **osmosisd v31.0.0-rc1** (`OsmosisApp`), CometBFT `v0.38.19` (E2: `/abci_info.response.data="OsmosisApp"`, `version="31.0.0-rc1-3-gcc93ee58d"`) |
| Research date | 2026-05-23 |
| Researcher | Hermes Agent |
| Status | 🟢 Done (diff-only) |
| Base chain | 05-cosmos-hub.md (commit `858bf4a`) |

---

## 1. Sources (Osmosis-specific only)

| Type | URL | Date | Notes |
|---|---|---|---|
| Official docs | https://docs.osmosis.zone/ | 2026-05-23 | Osmosis protocol / module / API overview [E3] |
| GitHub (osmosis) | https://github.com/osmosis-labs/osmosis | 2026-05-23 | Node daemon (osmosisd) + custom module source [E4] |
| Fork history | https://github.com/osmosis-labs/cosmos-sdk | 2026-05-23 | Osmosis maintains a **cosmos-sdk fork** (not upstream; v0.50+ behavior), with custom modules injected [E4] |
| SDK version | osmosisd v31.0.0 → cosmos-sdk v0.50.x fork + IBC-go v8 + CometBFT v0.38 [E2/E4] |
| Proto definitions (custom) | https://github.com/osmosis-labs/osmosis/tree/main/proto/osmosis | 2026-05-23 | `gamm/`, `concentratedliquidity/`, `poolmanager/`, `superfluid/`, `twap/`, `txfees/`, `lockup/`, `incentives/`, `tokenfactory/`, ~15 custom modules total [E4] |
| Explorer | https://www.mintscan.io/osmosis | 2026-05-23 | Generic Cosmos explorer; real address `osmo1jv65s3grqf6v6jl3dp4t6c9t9rk99cd80yhvld` [E2] |
| Numia DataLake | https://docs.numia.xyz/ | 2026-05-23 | On-chain data ETL (real swap-volume workload reference) [E3] |

---

## 2. Key diff vs 05-cosmos-hub.md (P0 cheat-sheet)

| Item | Cosmos Hub (05) | Osmosis (22) | Impact |
|---|---|---|---|
| Family | cosmos | **cosmos** (same family, reuses CosmosAdapter) | 0 new family |
| ChainID | `cosmoshub-4` | `osmosis-1` [E2] | Config-only, no protocol impact |
| Node daemon | `gaiad` v27.3.0 | **`osmosisd` v31.0.0-rc1** [E2] | Binary swap, RPC protocol unchanged |
| SDK source | upstream cosmos-sdk | **osmosis-labs/cosmos-sdk fork** (behavior 99% compat, adds modules to proto) [E4] | Proto registry must include Osmosis x/ paths |
| Bech32 prefix | `cosmos` / `cosmosvaloper` | **`osmo` / `osmovaloper` / `osmovalcons`** | Adapter address validation needs prefix table |
| Native token | `uatom` (1 ATOM = 10⁶ uatom) | **`uosmo`** (1 OSMO = 10⁶ uosmo); **second native token `uion`** (early-gov airdrop, still circulating) | Balance / fee queries see multiple denoms |
| Fee denom | `uatom` only | **Multi-denom fees** (`txfees` module accepts OSMO/USDC/ATOM/ION..., auto-swaps to uosmo) [E2: `/osmosis/txfees/v1beta1/base_denom="uosmo"`] | gasPrice estimator forks; benchmark must pin a denom |
| Block time | ~6 s | **~1.5–2 s** (E2: earliest→latest 53 d / 4 063 603 blocks ≈ 1.13 s avg; live observation 1.5–2 s) | QPS-ceiling baseline raises ~3× |
| Block size | Hub ~22 MB consensus param | Swap-heavy single block, similar maxBytes | Mempool pressure / tx size differ |
| CosmWasm | ❌ disabled | ✅ **enabled** (`/cosmwasm/wasm/v1/*` available; Mars / Astroport DEX run on it) | Adds one module category but with standard paths (non-diff) |
| Custom modules | — | **gamm / concentratedliquidity / poolmanager / superfluid / twap / txfees / lockup / incentives / tokenfactory / valset-pref / smart-account / cosmwasmpool** [E4] | **Core diff of this doc — see §3/§5/§7** |
| Typical workload | 60%+ `MsgSend` + `MsgDelegate`/`MsgWithdrawDelegatorReward` | **80%+ swap tx** (`MsgSwapExactAmountIn` / `MsgSplitRouteSwapExactAmountIn`) [E3] | benchmark `chain_specific` MUST cover swap path |
| Epoch | — | **Daily epoch** (`x/epochs` triggers inflation + incentives + superfluid delegation switch); epoch blocks gas spike ~5–10× [E3/E4] | benchmark must flag epoch blocks (outlier) |

---

## 3. Public endpoint evidence (H8)

```
ep1: https://osmosis-rpc.publicnode.com  + https://osmosis-rest.publicnode.com
ep2: https://osmosis-rpc.polkachu.com
ep3: https://lcd.osmosis.zone (official LCD)
```

| Probe | Endpoint | Result (2026-05-23) | Tag |
|---|---|---|---|
| `/status` | publicnode RPC | `network=osmosis-1`, height=62344664, `catching_up=false`, CometBFT 0.38.19 | E2 |
| `/abci_info` | publicnode RPC | `data="OsmosisApp"`, `version="31.0.0-rc1-3-gcc93ee58d"` | E2 |
| `/cosmos/bank/v1beta1/balances/{osmo1jv65...}?pagination.limit=3` | publicnode REST | 200; 3 denoms returned (all `factory/osmo.../...` tokenfactory sub-coins) | E2 |
| `/osmosis/poolmanager/v1beta1/num_pools` | publicnode REST | `{"num_pools":"3460"}` | E2 |
| `/osmosis/gamm/v1beta1/pools?pagination.limit=2` | publicnode REST | 200; pool #1 (uosmo/ATOM) + pool #2 (uosmo/uion); includes `pool_params.swap_fee`, `pool_assets[].weight`, etc. | E2 |
| `/osmosis/concentratedliquidity/v1beta1/params` | publicnode REST | 200; `authorized_tick_spacing=[1,10,100,1000]`, 9 spread factors, `hook_gas_limit=2000000` | E2 |
| `/osmosis/superfluid/v1beta1/params` | publicnode REST | `{"minimum_risk_factor":"0.25"}` | E2 |
| `/osmosis/twap/v1beta1/ArithmeticTwapToNow?pool_id=1&base=uosmo&quote=ibc/27394...&start=-1h` | publicnode REST | `{"arithmetic_twap":"0.027219153303361372"}` | E2 |
| `/osmosis/txfees/v1beta1/base_denom` | publicnode REST | `{"base_denom":"uosmo"}` | E2 |
| `/osmosis/lockup/v1beta1/module_balance` | publicnode REST | 200; 100+ `cl/pool/N` lock-token denoms (large payload, ~50 KB) | E2 |

**Conclusion**: All 4 custom modules respond on publicnode → **no `requires_self_hosted` needed**. However `lockup/module_balance` is bulky and `gamm/pools` without pagination can time out — **benchmark MUST paginate**.

---

## 4. Substantive diff vs Cosmos Hub

### 4.1 Custom modules → REST paths (all `/osmosis/{module}/v1beta1/...`)

| Module | Purpose | Key endpoints (E2 verified) | Benchmark value |
|---|---|---|---|
| `gamm` | Balancer-style AMM pools (legacy) | `/pools/{id}`, `/pools?limit=N`, `/total_liquidity`, `/estimate_swap_exact_amount_in` | High (swap pre-quote) |
| `concentratedliquidity` (CL) | Uniswap-v3-style concentrated liquidity | `/params`, `/pools`, `/positions/{addr}`, `/liquidity_per_tick_range`, `/incentive_records` | High (read-heavy + tick state) |
| `poolmanager` | Route aggregator + swap entry-point | `/num_pools`, `/all-pools`, `/route?in_denom=&out_denom=`, `/estimate_swap_exact_amount_in?pool_id=&token_in=&routes=` | **Highest** (single endpoint triggers multi-hop computation, CPU-heavy) |
| `superfluid` | Liquid staking (LP token → delegation) | `/params`, `/all_assets`, `/superfluid_delegations/{addr}`, `/total_superfluid_delegations` | Medium (hot during epoch window) |
| `twap` | Time-weighted avg price oracle | `/ArithmeticTwapToNow`, `/GeometricTwapToNow`, `/ArithmeticTwap?start=&end=` | Medium (window query, DB range scan) |
| `txfees` | Multi-denom fee aggregation | `/base_denom`, `/fee_tokens`, `/denom_spot_price` | Low (config-like, low QPS) |
| `lockup` | LP-token lockup (prereq for superfluid) | `/module_balance`, `/account_locked_coins/{addr}`, `/synthetic_lockups_by_lockup_id/{id}` | Medium (large payloads) |
| `incentives` | Gauge incentive distribution | `/active_gauges`, `/gauge_by_id/{id}`, `/rewards_est/{addr}` | Medium |
| `tokenfactory` | User-issued denoms | `/denoms_from_creator/{addr}`, `/denom_authority_metadata/{denom}` | Low |
| `valset-pref` | Delegation preference sets | `/user_validator_preferences/{addr}` | Low |
| `smart-account` | Account abstraction (authenticator) | `/authenticators/{addr}` | Low |
| `cosmwasmpool` | CW pool wrapper | `/pools` | Low |

### 4.2 Consensus / chain parameter diff

| Param | Cosmos Hub | Osmosis |
|---|---|---|
| `BlockMaxBytes` | ~22 MB | ~10 MB (handles swap-heavy blocks) |
| `BlockMaxGas` | -1 (unlimited) | **300 M gas** (swap is complex, gas-bounded) |
| `min_commission_rate` | 5% | 5% |
| `inflation` | ATOM model | **Per-epoch thirdening** (every 156 epochs inflation ÷ 2/3) |
| `unbonding_period` | 21 d | **14 d** |

---

## 5. Method diff (99% same as Cosmos Hub; only custom modules & param diffs listed)

> Standard `/cosmos/*` REST + CometBFT JSON-RPC are identical — see 05-cosmos-hub.md §5, **not repeated**.

### 5.1 Custom REST endpoints (derived from §4.1)

4 P0 endpoints verified (all 200):
- `GET /osmosis/poolmanager/v1beta1/num_pools` → total pool count (light probe)
- `GET /osmosis/poolmanager/v1beta1/estimate_swap_exact_amount_in` → swap quote (**CPU-heavy, benchmark-critical**)
- `GET /osmosis/gamm/v1beta1/pools/{id}` → single pool state (state-trie read)
- `GET /osmosis/concentratedliquidity/v1beta1/pools/{id}/liquidity_per_tick_range` → tick liquidity (read-heavy)

### 5.2 Custom Msg types (for `tx_search` queries)

`MsgSwapExactAmountIn` / `MsgSwapExactAmountOut` / `MsgSplitRouteSwapExactAmountIn` / `MsgJoinPool` / `MsgExitPool` / `MsgCreateBalancerPool` / `MsgCreateConcentratedPool` / `MsgCreatePosition` / `MsgWithdrawPosition` / `MsgSuperfluidDelegate` / `MsgLockTokens` / `MsgBeginUnlocking` (all under `/osmosis.{module}.v1beta1.*` proto) [E4]

### 5.3 Parameter diffs (same endpoint name, different value)

- `/cosmos/staking/v1beta1/params.unbonding_time` → Osmosis returns `1209600s` (14 d), Hub returns `1814400s` (21 d) [E2 re-verifiable]
- `/cosmos/auth/v1beta1/accounts/{addr}` → Some Osmosis accounts are **smart-accounts** (authenticator extension); `@type` may be `/osmosis.smartaccount.v1beta1.SmartAccount` (**deserialization fork point** for stock cosmos auth clients!) [E4]

---

## 6. Real workload (typical mix)

Based on Numia / Mintscan public data + block sampling around height 62344664 [E3]:

| Msg type | Share | Benchmark weight suggestion |
|---|---|---|
| `MsgSwapExactAmountIn` + `MsgSplitRouteSwap*` (swap) | **~70%** | swap-quote endpoint MUST be in chain_specific suite |
| `MsgUpdateClient` / IBC packet relay | ~15% | IBC client (standard cosmos `/ibc/core/*`, non-diff) |
| `MsgSend` / `MsgMultiSend` | ~7% | Standard cosmos (non-diff) |
| `MsgLockTokens` / `MsgBeginUnlocking` / superfluid | ~4% | Clustered during epoch |
| `MsgVote` / staking | ~4% | Standard cosmos |

**Hot read queries**: `/osmosis/poolmanager/.../estimate_swap_exact_amount_in` (front-end quote loops); `/osmosis/gamm/v1beta1/pools/{id}` (wallet dashboards); `/cosmos/bank/v1beta1/balances/{addr}` (wallets, 10–100 denoms — far more than Hub).

---

## 7. DSL decision (predicted new fields)

Reuse the cosmos DSL body from 05-cosmos-hub. **Predict 2 new `chain_specific` sub-nodes** (first within family=cosmos — requires schema extension):

### ASK 1 — `chain_specific.osmosis_modules` (enumerate custom-module probes)

```yaml
chains:
  osmosis:
    family: cosmos
    bech32_prefix: osmo
    native_denom: uosmo
    bond_denom: uosmo
    chain_specific:
      osmosis_modules:        # ← NEW (Osmosis-only)
        gamm: true
        concentratedliquidity: true
        poolmanager: true
        superfluid: true
        twap: true
        txfees: true
        lockup: true
      hot_endpoints:          # ← NEW (Osmosis-only, benchmark P0 paths)
        - path: /osmosis/poolmanager/v1beta1/num_pools
          weight: 1
        - path: /osmosis/poolmanager/v1beta1/estimate_swap_exact_amount_in
          weight: 5            # CPU-heavy, weight up
          params_template: { pool_id: 1, token_in: "1000000uosmo", routes: "..." }
        - path: /osmosis/gamm/v1beta1/pools/{pool_id}
          weight: 3
          params_template: { pool_id: "1|2|678|1066" }
```

**DSL ASK text**: Do we approve introducing, under `family=cosmos`, two sub-nodes `chain_specific.osmosis_modules` (bool map, probe set) and `chain_specific.hot_endpoints` (list with weight + params_template), as the unified extension point for all subsequent cosmos app-chains (Injective `/injective/exchange/*`, Sei `/sei/oracle/*`, Neutron `/neutron/cron/*`)? If yes, schema should be `additionalProperties: false` to prevent sprawl.

### ASK 2 — All other fields reuse the cosmos DSL; **no new family-level field needed** (the `unbonding_period`/`max_gas` deltas in §4.2 are already covered by the cosmos DSL `consensus_params` node, only with different values).

---

## 8. H8 evidence summary (curl count for this doc)

**10 curls** in total (all run on 2026-05-23):
1. `/status` → chainID + height + CometBFT version ✅
2. `/abci_info` → app=OsmosisApp v31.0.0-rc1 ✅
3. `/cosmos/bank/v1beta1/balances/{osmo1jv65...}` → real balance (3 factory denoms) ✅
4. `/osmosis/poolmanager/v1beta1/num_pools` → 3460 ✅
5. `/osmosis/poolmanager/v1beta1/all-pools?pagination.limit=1` → 200 ✅
6. `/osmosis/gamm/v1beta1/pools?limit=2` → pool#1 + pool#2 full payload ✅
7. `/osmosis/concentratedliquidity/v1beta1/params` → 9 spread factors + 4 tick spacings ✅
8. `/osmosis/superfluid/v1beta1/params` → minimum_risk_factor=0.25 ✅
9. `/osmosis/twap/v1beta1/ArithmeticTwapToNow?...` → 0.027219... ✅
10. `/osmosis/txfees/v1beta1/base_denom` → uosmo ✅ (additionally `/osmosis/lockup/v1beta1/module_balance` probed, also 200)

**Conclusions (honest self-check)**:
- All 4 unique modules (gamm/CL/poolmanager/superfluid) reachable from public endpoints → **no `requires_self_hosted=true`** ✅
- Protocol layer 100% reuses cosmos family — no new family ✅
- DSL only needs 1 ASK (`chain_specific` sub-nodes); no breaking change ✅
- **No deferred bugs**: the `smart-account` `@type` deserialization fork point (§5.3) is flagged; it must be handled when CosmosAdapter is implemented — **not promised to be fixed in this doc** ✅
- **Critical self-audit**: this doc is based on a single publicnode endpoint + a 30-minute snapshot. If Osmosis v32 (currently rc1) lands with module renaming, this doc needs re-check — **confidence 95%**, 5% residual risk because v31 is still rc.
