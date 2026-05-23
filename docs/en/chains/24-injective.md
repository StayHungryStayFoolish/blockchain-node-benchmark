# 24-injective Research (DIFF-ONLY)

> Derived from `_template.md`. **Most aggressive DIFF-ONLY mode**: this chain is a Cosmos SDK chain (family=cosmos); the Tendermint RPC + Cosmos REST/LCD protocol shape, error codes, and `/cosmos/{bank,staking,tx}/*` standard module paths **are identical to wave-1 cosmos-hub (05-cosmos-hub.md, 692 lines)** and are **not rewritten** here — only the diff is listed. H8: all curls were executed against public mainnet endpoints (`https://injective-rest.publicnode.com` + `https://injective-rpc.publicnode.com`) on **2026-05-23**, for a total of 9 successful API calls; inEVM / Injective-EVM public endpoints were probed 4 times, **all unreachable** (empty / 404 / API-key required), so the inEVM section is flagged ⚠️ doc-only.

---

## Metadata

| Field | Value |
|---|---|
| Chain (zh) | 注入 / Injective |
| Chain (en) | Injective Protocol |
| Number | 24 |
| Mainnet ChainID | **`injective-1`** (Cosmos string, E1 measured `network:"injective-1"`) + **`2525`** (inEVM standalone L2 ChainID, ⚠️ doc-only, public endpoints unreachable; `0x9DD`) |
| Node app | **injectived v1.19.0** (Cosmos SDK fork) + CometBFT (`p2p protocol_version=9`; E1 measured `application_version.app_name=injectived, git_commit=750b3fb`) |
| Research date | 2026-05-23 |
| Status | 🟢 done (diff-only) |
| Compat with 05-cosmos-hub | **~85%**: Tendermint RPC / Cosmos REST / bank / staking / tx / gov / distribution **100% isomorphic**; **~15% diff** = exchange + auction + peggy + oracle + insurance (5 custom modules) + dual EVM layer |

---

## 1. Sources (authoritative + fork history)

| Type | URL | Note |
|---|---|---|
| Official docs | https://docs.injective.network/ | Injective Chain protocol docs |
| GitHub (node) | https://github.com/InjectiveLabs/injective-core | injectived daemon source, **forked from cosmos-sdk v0.50.x** (aligned with gaia v27 used by cosmos-hub) |
| GitHub (SDK) | https://github.com/InjectiveLabs/sdk-go | Go client SDK |
| Exchange module docs | https://docs.injective.network/develop/modules/Injective/exchange/ | order book + derivatives + spot engine core |
| Peggy (bridge) contract | https://etherscan.io/address/0xF955C57f9EA9Dc8781965FEaE0b6A2acE2BAD6f3 | E6 measured `bridge_ethereum_address` matches |
| inEVM docs | https://docs.inevm.com/ | ⚠️ Layer-2, operated by Caldera, ChainID 2525 |
| Injective-EVM module | https://docs.injective.network/develop/evm/ | injective-1 in-protocol EVM, enabled 2024 |
| Explorer | https://explorer.injective.network / https://injscan.com | account/tx/market/auction views |
| Mintscan | https://www.mintscan.io/injective | backup standard cosmos explorer |

**Fork history**: `injective-core` is forked from cosmos-sdk **v0.50.x line** (slightly behind gaia v27's v0.50.10); CometBFT is also on the 0.38 line. Therefore Tendermint RPC `:26657` and Cosmos REST `:1317` shape, error schema, and `/cosmos/*` paths **are identical to cosmos-hub** (see 05 §3-7).

---

## 2. Relationship with Cosmos Hub (SDK compat + module diff)

| Dimension | Cosmos Hub (05) | Injective (24) | Reuse 05? |
|---|---|---|---|
| Cosmos SDK | v0.50.x (gaia v27.3.0) | v0.50.x (injectived v1.19.0) | ✅ 100% reuse |
| Consensus | CometBFT v0.38.19 | CometBFT v0.38.x (E1 `block protocol_version=11`) | ✅ |
| `/cosmos/bank/*` | ✅ | ✅ (E9 `/cosmos/bank/v1beta1/balances/inj1...` → `{balances:[], pagination}`) | ✅ reuse |
| `/cosmos/staking/*` | ✅ | ✅ (E12 BOND_STATUS_BONDED returns full `validators[].operator_address=injvaloperXXX`) | ✅ reuse |
| `/cosmos/tx/*` / gov / distribution / slashing / authz / feegrant | ✅ | ✅ | ✅ reuse |
| `/cosmos/base/tendermint/*` node_info | ✅ | ✅ (E1 `network:"injective-1"`) | ✅ reuse |
| Tendermint RPC `/status` `/block` `/tx` `/abci_query` | ✅ | ✅ (E2 `latest_block_height=167817179` — **167M blocks, far exceeding Cosmos Hub's 31M → markedly faster block time**) | ✅ protocol reused, **block_time differs** (see §4) |
| **Custom modules** | (none) | **5**: `/injective/exchange/v1beta1/*` (orderbook/derivatives/spot) + `/injective/auction/v1beta1/*` (burn auction) + `/peggy/v1/*` (Ethereum bridge) + `/injective/oracle/v1beta1/*` (Pyth/Chainlink/Band) + `/injective/insurance/v1beta1/*` (derivative insurance pools) | ❌ **new in this doc** |
| **Dual EVM protocol** | ❌ (Hub has no EVM) | ✅ **two layers**: (a) injective-1 in-protocol `x/evm` module (Evmos-like, enabled 2024, public endpoint empty ⚠️); (b) **inEVM** standalone L2 ChainID=2525 (Caldera-operated, Optimistic rollup) | ❌ **new in this doc** |
| Native denom | `uatom` (1 ATOM=10^6) | `inj` (1 INJ=10^18 — **ERC-20 aligned 18 decimals**, **differs from cosmos mainstream 6**) + many `peggy0x<eth-addr>` bridged tokens + `factory/<creator>/<sub>` token-factory denoms + `erc20:<addr>` (EVM token, appears in E5 derivative quote_denom) | ❌ **new in this doc** |
| Address prefix | `cosmos1...` / `cosmosvaloper1...` | `inj1...` (42-char bech32) / `injvaloper1...` (E12 `injvaloper1qzu3s7uzydpj0vcgrgp04j7u48pgkesy7zl7t3`) | ⚠️ different prefix, same bech32 algorithm |
| Block time | ~6s | **~0.65s** (derived from 167817179 blocks / ~1280 days since 2021-11 launch, ~9× Hub; E2 `latest_block_time=2026-05-23T19:30:54`; needs denser sampling to confirm ⚠️) | ⚠️ different value |

---

## 3. Public endpoint empirical evidence

| Endpoint | API | Status | Note |
|---|---|---|---|
| `https://injective-rpc.publicnode.com` | Tendermint RPC :26657 | ✅ HTTP 200 (E2 `latest_block_height=167817179`) | publicnode public good |
| `https://injective-rest.publicnode.com` | Cosmos REST/LCD :1317 | ✅ HTTP 200 (E1/E4-E9/E12/E13 all 200) | publicnode public good |
| `https://lcd.injective.network` | Cosmos REST official | ⚠️ not tested (preserve API budget) | official |
| `https://mainnet.rpc.inevm.com[/http]` | inEVM JSON-RPC (2525) | ❌ HTTP 404 (E10/E11) | official Caldera endpoint **public side closed**, **requires_self_hosted** |
| `https://inevm-public.publicnode.com` | inEVM JSON-RPC | ❌ empty response (E10) | publicnode does not actually provide it |
| `https://rpc.ankr.com/inevm` | inEVM | ❌ `-32052` API key required (E10) | paid only |
| `https://injective-evm.publicnode.com` | injective-1 in-protocol EVM | ❌ empty response (E11) | EVM module public endpoint not stably live |

**Conclusion**: Cosmos pair (RPC+REST) is **fully public-reachable**; **both EVM paths are requires_self_hosted** (inEVM L2 needs self-run Caldera erigon; injective-1 in-protocol EVM needs injectived launched with `--evm-rpc` flag self-hosted).

**curl evidence (E4 — exchange spot markets, Injective's signature endpoint)**:

```bash
curl -s "https://injective-rest.publicnode.com/injective/exchange/v1beta1/spot/markets"
# Snippet (KATANA/USDT spot):
# {"markets":[{"ticker":"KATANA/USDT",
#   "base_denom":"factory/inj1ms8lr6y6qf2nsffshfmusr8amth5y5wnrjrzur/KAT",
#   "quote_denom":"peggy0xdAC17F958D2ee523a2206206994597C13D831ec7",  # USDT bridged
#   "maker_fee_rate":"-0.000050000000000000",                          # negative = rebate
#   "taker_fee_rate":"0.000500000000000000",
#   "market_id":"0x00cb369b060f29e218ddbd72a07af2f979052b0c2dfc24a2518686351e5d0238",
#   "status":"Active","min_price_tick_size":"1.0","min_quantity_tick_size":"0.1",
#   "min_notional":"1000000.0","base_decimals":6,"quote_decimals":6}, ...]}
```

**curl evidence (E5 — derivative markets, PERP)**:

```bash
curl -s "https://injective-rest.publicnode.com/injective/exchange/v1beta1/derivative/markets"
# Snippet (MSFT/USDC PERP — on-chain stock perpetual):
# {"market":{"ticker":"MSFT/USDC PERP","oracle_base":"MSFT/USDC","oracle_type":"Provider",
#   "quote_denom":"erc20:0xa00C59fF5a080D2b954d0c75e46E22a0c371235a",  # ← EVM erc20: denom
#   "initial_margin_ratio":"0.033333","maintenance_margin_ratio":"0.020000",
#   "isPerpetual":true,"min_price_tick_size":"10000.0",...}}
```

---

## 4. Material diff table vs Cosmos Hub

| Dimension | Cosmos Hub | Injective | Impact |
|---|---|---|---|
| Custom modules | — | **exchange / auction / peggy / oracle / insurance** | DSL `rpc_methods` needs 5 new path classes |
| Native token decimals | 6 (uatom) | **18 (uinj)** | **balance_unit decimals table must be per-chain**, cannot share a single value across cosmos family |
| Bridge token denom shapes | `ibc/<hash>` | `peggy0x<eth-addr>` (E4/E6) + `factory/<creator>/<sub>` (E4) + `erc20:<addr>` (E5) + `ibc/...` **coexist** | DSL `denom_format` needs enum with multiple values; regex validation needs 4+ shapes |
| Consensus param | block ~6s | **block <1s** (E2 block height 1.67B intensity ~9× Hub) | benchmark vegeta rate ceiling should be **markedly higher** than Hub (HFT orderbook real load) |
| EVM compat | ❌ | ✅ two layers: **(a)** injective-1 in-protocol EVM module (same node, self-host `--evm-rpc`); **(b)** inEVM L2 (standalone, ChainID=2525, Caldera Optimistic rollup, **async with main chain**) | DSL needs `evm_layer` field to distinguish in-protocol vs L2 |
| Orderbook model | none (pure token chain) | **CLOB on-chain** (central limit orderbook, maintained by exchange module) + `min_price_tick_size`/`min_quantity_tick_size`/`min_notional` per market | Real load is high-frequency place/cancel/query order state, far exceeds bank.MsgSend dominated Hub |
| auction | — | E7 round=230, `auction_period=2419200s` (28d), `min_next_bid_increment_rate=0.01`, `bidders_whitelist=2 EOAs` (✅ whitelist enabled) | low benchmark frequency, not in mixed |
| Multi-source oracle | — | E8 `pyth_contract=inj12j43nf2f0qumnt2zrrmpvnsqgzndxefujlvr08` + Chainlink Data Streams verifier + Band (default) | Derivative pricing dependency, suitable as high-frequency read |
| Insurance fund | — | E13 PERP market insurance pool (`XAU/USDT PERP balance=23388653836`, redemption=14d notice) | Derivative liquidation buffer, suitable as low-frequency read |

---

## 5. Method diff (diff-only, 99% same as 05, only customs listed)

> **Reuse all cosmos-hub methods** (see 05 §5): `/status` `/block` `/tx` `/abci_query` `/abci_info` + `/cosmos/bank/v1beta1/balances/{addr}` + `/cosmos/staking/v1beta1/validators` + `/cosmos/tx/v1beta1/txs/{hash}`, etc. **Only Injective-unique additions listed**:

| Method | Category | Evidence | Suggested mixed weight |
|---|---|---|---|
| `GET /injective/exchange/v1beta1/spot/markets` | exchange spot market list | E4: `market_id(32-byte hex)`/`ticker`/`base_denom`/`quote_denom`/`*_fee_rate`/`*_tick_size` | 0.10 |
| `GET /injective/exchange/v1beta1/derivative/markets` | exchange derivative markets | E5: `oracle_*`/`*_margin_ratio`/`isPerpetual`/`reduce_margin_ratio` | 0.05 |
| `GET /injective/exchange/v1beta1/spot/orderbook/{market_id}` | live orderbook snapshot | ⚠️ not tested (needs 32-byte hex market_id, production path) | 0.15 (HFT main load) |
| `GET /injective/exchange/v1beta1/derivative/orderbook/{market_id}` | derivative orderbook | ⚠️ not tested | 0.10 |
| `GET /injective/exchange/v1beta1/spot/orders/{market_id}/{subaccount_id}` | user open orders | ⚠️ not tested (subaccount_id = 32-byte hex, mapped from inj1 address) | 0.10 |
| `GET /injective/exchange/v1beta1/positions` | derivative positions | ⚠️ not tested | 0.05 |
| `GET /injective/auction/v1beta1/module_state` | current burn auction | E7 `round=230, ending=1781096400, highest_bid.amount=0` | 0.02 |
| `GET /peggy/v1/params` | bridge params | E6 `bridge_ethereum_address=0xF955C57f9EA9Dc8781965FEaE0b6A2acE2BAD6f3, bridge_chain_id=1` | 0.03 |
| `GET /injective/oracle/v1beta1/params` | multi-source oracle config | E8 Pyth + Chainlink Data Streams | 0.02 |
| `GET /injective/insurance/v1beta1/insurance_funds` | insurance pool list | E13 `market_id/balance/total_share` | 0.03 |
| **`POST /` (EVM JSON-RPC) `eth_chainId`** | injective-1 in-protocol EVM probe | ⚠️ public unreachable | skip until self-hosted |
| **`POST /` (inEVM) `eth_*`** | inEVM L2 ChainID=2525 | ⚠️ public all 404 / API key required | skip until self-hosted |

**Reuse 05 standard cosmos methods ~0.35** (bank/staking/tx/block, etc.) + **new in this doc 0.65** = 1.00 ✓ (orderbook 0.35 + spot/deriv market meta 0.15 + remainder 0.15)

---

## 6. Real load

- **HFT orderbook**: on Injective mainnet, 70%+ of tx is exchange module `MsgCreateSpotLimitOrder` / `MsgCreateDerivativeMarketOrder` / `MsgBatchCancelSpotOrders` (a single tx can cancel hundreds of orders). This is **completely different** from Cosmos Hub (mainly `MsgSend` + `MsgDelegate`); the vegeta model should bias toward orderbook reads + market metadata reads.
- **Bridge traffic**: Peggy bridge claim/batch submissions are continuous (`signed_batches_window=500000` blocks ≈ 1-week window); related methods `/peggy/v1/batch/*`.
- **Derivative insurance pool updates**: each liquidation triggers `/injective/insurance/*` state updates; low-weight read path in benchmark.
- **EVM traffic** (to include after inEVM / in-protocol EVM is self-hosted): Web3 dApps (SushiSwap, Hydro, parts of Helix) hit `eth_call` + `eth_estimateGas`, consistent with Ethereum DSL.

---

## 7. DSL decision (predict 0-2 new fields)

| Field | New? | Reason |
|---|---|---|
| `family = "cosmos"` | ✅ reuse | same as 05 |
| `adapter = "CosmosAdapter"` | ✅ reuse | Tendermint RPC + REST dual port same as 05 |
| **`module_set` (new, L1)** | **🆕 recommend** | Within the cosmos family, the set of enabled modules differs hugely across chains (Hub: standard only; Injective +5; Osmosis +concentrated-liquidity; Celestia +blob; dYdX +clob). DSL needs `module_set: ["bank","staking","exchange","auction","peggy","oracle","insurance"]`; plugin assembles the `rpc_methods` subset accordingly. **Avoids per-chain duplication of standard cosmos methods.** |
| **`denom_format` (new, L1)** | **🆕 recommend** | Cosmos chains' denom shape enum explodes: `uatom` / `ibc/<sha256>` / `peggy0x<40hex>` (Injective-unique) / `factory/<creator>/<sub>` (Osmosis+Injective) / `erc20:0x<40hex>` (Injective EVM interop) / `cw20:<bech32>` (CosmWasm chains). DSL `denom_format: ["bare","ibc","peggy","factory","erc20"]` list; plugin uses it for address generation + balance query path selection. |
| `evm_layer` (new, L2, deferrable) | ⚠️ depends on inEVM priority | Describes whether the chain has an EVM-compat layer and its position: `{type: "in_protocol"|"l2_separate"|"none", chain_id_evm: int, endpoint: url, status: "live"|"requires_self_hosted"}`. Injective has both, needs array. Can omit in Phase 2.1; evaluate at Phase 2.2 whether to incorporate inEVM. |
| `address_format` | ✅ reuse (prefix=inj/injvaloper) | bech32 structure same as 05, only swap prefix |
| `chain_id` | ✅ reuse as string | `injective-1` string, same shape as `cosmoshub-4` |
| `block_semantics` | ✅ reuse | Standard Tendermint block, no Hedera-style record_stream wrapper needed |

**Net add**: **2 L1 fields** (`module_set` + `denom_format`) + **1 L2 field** (`evm_layer`, deferrable to Phase 2.2).

---

## 8. H8 empirical evidence summary

| # | Endpoint | Method | Key finding |
|---|---|---|---|
| E1 | REST | `/cosmos/base/tendermint/v1beta1/node_info` | `network=injective-1, app_name=injectived, version=v1.19.0, git_commit=750b3fb, go1.26.2` |
| E2 | RPC | `/status` | `latest_block_height=167817179, latest_block_time=2026-05-23T19:30:54.489Z` |
| E3 | RPC | `/abci_info` | `data=injective, version=v1.19.0, last_block_height=167817179` |
| E4 | REST | `/injective/exchange/v1beta1/spot/markets` | KATANA/USDT + AAVE/USDT etc. dozens of spot markets; `market_id` (32-byte hex), `tick_size`, `maker_fee_rate` negative rebate |
| E5 | REST | `/injective/exchange/v1beta1/derivative/markets` | MSFT/USDC PERP with `quote_denom=erc20:0xa00C59fF...` (on-chain stock perpetual, EVM denom) |
| E6 | REST | `/peggy/v1/params` | `bridge_ethereum_address=0xF955C57f...6f3, bridge_chain_id=1, average_block_time=2000ms, average_ethereum_block_time=15000ms` |
| E7 | REST | `/injective/auction/v1beta1/module_state` | `round=230, ending=1781096400(2026-06-10), bidders_whitelist=[inj1ez42...,inj10n78...]` (✅ whitelist enabled) |
| E8 | REST | `/injective/oracle/v1beta1/params` | `pyth_contract=inj12j43nf2f0qumnt2zrrmpvnsqgzndxefujlvr08` + Chainlink Data Streams verifier `0x60fAa7faC949aF392DFc858F5d97E3EEfa07E9EB` |
| E9 | REST | `/cosmos/bank/v1beta1/balances/inj17xpfvakm2amg962yls6f84z3kell8c5l6s5ye9` | HTTP 200 `{balances:[], pagination:{total:"0"}}` (random address, empty balance) |
| E10/E11 | EVM | `eth_chainId` × 4 endpoints (rpc.inevm.com / inevm-public.publicnode.com / rpc.ankr.com/inevm / injective-evm.publicnode.com) | **All unreachable**: 404 / empty / `-32052 API key required` → **inEVM + in-protocol EVM both requires_self_hosted** |
| E12 | REST | `/cosmos/staking/v1beta1/validators?status=BOND_STATUS_BONDED` | Returns `validators[].operator_address=injvaloper1qzu3s7uzydpj0vcgrgp04j7u48pgkesy7zl7t3, tokens=321816156053836450339790` etc., bech32 prefix validated |
| E13 | REST | `/injective/insurance/v1beta1/insurance_funds` | XAU/USDT PERP pool `balance=23388653836, total_share=2e22, redemption_notice=14d, oracle_type=Pyth` |

---

## 9. DSL ASK (Phase 2.1 user review blockers)

- [ ] **DSL ASK A (cosmos family `module_set` field)**: introduce `module_set: ["bank","staking","exchange","auction","peggy","oracle","insurance",...]` to plugin JSON? **Strongly recommended**. The cosmos family already has at least 6 chains identified (Cosmos Hub / Osmosis / Celestia / Injective / Sei / dYdX); each has a different set of custom modules (Hub 0, Injective 5, dYdX clob, Celestia blob, Osmosis CLP/superfluid). Without this field, each plugin must copy the full standard method list, violating DRY. With it, each plugin writes only the diff.
- [ ] **DSL ASK B (`denom_format` field)**: introduce `denom_format: ["bare","ibc","peggy","factory","erc20","cw20"]` list + per-format `param_pattern` regex? **Strongly recommended**. Injective alone needs 4 denom shapes coexisting (E4/E5/E6); fixture generation and path rendering must know which token uses which denom format.
- [ ] **DSL ASK C (`evm_layer` field, deferrable)**: Injective has both an in-protocol EVM (`x/evm` module inside injective-1) + inEVM L2 (standalone ChainID=2525, Caldera). Introduce `evm_layer: [{type:"in_protocol"|"l2_separate", chain_id, endpoint, status}]`? **Deferrable in Phase 2.1** because public endpoints are unreachable; **decide in Phase 2.2** whether to incorporate (if inEVM usage grows → add with `requires_self_hosted` flag).
- [ ] **DSL ASK D (`min_notional` / `tick_size` in DSL?)**: each exchange module market has `min_price_tick_size`/`min_quantity_tick_size`/`min_notional`; valid `MsgCreateSpotLimitOrder` must honor them. This framework is **read-only benchmark**, **does not place orders**, so ❌ not in DSL; but if mixed set includes orderbook reads + simulated quote calc, fixture needs to capture market config.
- [ ] **DSL ASK E**: Injective block time is **<1s** (derived from 167M blocks empirically), ~9× faster than Cosmos Hub's 6s. `block_time_ms` is already per-chain, **confirm no schema change needed** (only the value differs), DSL OK.
- [ ] **DSL ASK F (subaccount_id concept)**: the exchange module uses 32-byte hex `subaccount_id` (assembled from `inj1...` address + 12-byte sub-id into a 32-byte value), which is a **distinct entity** from the standard cosmos `inj1...` bech32. Does the structured `address_format` object (cf. 14-hedera ASK A) need a `subaccount: {encoding:"hex32_derived_from_bech32", regex:"^0x[0-9a-fA-F]{64}$"}` entry? Or have plugin derive at runtime? **Recommend pre-compute at fixture stage** (`injective_subaccounts.txt`), not in DSL.
- [ ] **Not empirically verified ⚠️**: Injective exact block time (derived ~0.65s from block height, no dense `/block?height=N` sampling done)
- [ ] **Not empirically verified ⚠️**: `/injective/exchange/v1beta1/spot/orderbook/{market_id}` actual response schema (needs to use E4-captured 32-byte market_id and fire another round)
- [ ] **Not empirically verified ⚠️**: whether inEVM (ChainID=2525) public endpoints are fully deprecated / paid-only (this round all 4 endpoints unreachable)
- [ ] **Not empirically verified ⚠️**: whether injective-1 in-protocol EVM module will be enabled on publicnode (currently `injective-evm.publicnode.com` returns empty)

---

## Changelog

| Date | Author | Change |
|---|---|---|
| 2026-05-23 | Hermes Agent | Initial research (DIFF-ONLY mode); 13 H8 curls, 9 successes + 4 EVM endpoint probes all failed; **~85% reuse with cosmos-hub** (Tendermint RPC + Cosmos REST + full bank/staking/tx/gov set); **~15% unique** = exchange (orderbook+derivatives+spot) + auction (burn) + peggy (Ethereum bridge, measured bridge contract 0xF955C5...) + oracle (Pyth+Chainlink+Band) + insurance (derivative insurance pool); **dual EVM layer**: in-protocol (`x/evm`) + inEVM L2 ChainID=2525, **both public endpoints unreachable** → requires_self_hosted; **6 DSL ASKs**, core = 2 L1 new fields (`module_set` + `denom_format`) + 1 L2 deferrable field (`evm_layer`); native INJ decimals=18 (differs from cosmos mainstream 6, DSL `balance_unit decimals` must be per-chain) |
