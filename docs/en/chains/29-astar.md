# 29-astar Research (DIFF-ONLY)

> Derived from `_template.md`. **Most aggressive DIFF-ONLY mode (guardrail 2)**: this chain is a **Polkadot parachain (parachain ID=2006, won first slot auction 2021-12)** + **EVM + WASM dual-VM in parallel** (unique; 28-moonbeam is EVM-only, 27-acala is EVM+ custom variant, Astar is **both VMs standard and sharing one Substrate runtime**). This doc **does not rewrite** the protocol structure already established by 02-ethereum / 07-polkadot / 28-moonbeam; it only lists four classes of differences: **dual-VM coexistence + WASM (ink! / pallet-contracts) + dApp Staking incentives + dual-hostname interchangeability empirically verified**. Cross-reuse check with **27-acala / 28-moonbeam (same wave-8 EVM-on-Substrate batch)**. H8: this round of **12** H8 curls on **2026-05-23** against public mainnet dual endpoints (`https://evm.astar.network` + `https://rpc.astar.network`) — **12/12 returned 200/success** (EVM 5 + Substrate 5 + **2 cross-endpoint verifications confirming both hostnames serve both `eth_*` and `system_*` namespaces, i.e. one RPC server behind two DNS names**); WASM pallet-contracts instantiate/call calls were **not** dispatched due to budget/approval cutoff — runtime activation is **confirmed via `state_getRuntimeVersion.apis` hash list**, concrete extrinsics marked ⚠️ docs-only. **This is the final chain in the wave 1-8 / 28-chain survey**, and §7 contains the DSL ASK set **end-state evaluation**.

---

## Meta

| Field | Value |
|---|---|
| Name (CN) | 阿斯塔 / Astar |
| Name (EN) | Astar Network |
| No. | 29 |
| Mainnet ChainID | **EVM**: `592` (E1 `result:"0x250"` ✅, E9 `net_version:"592"` double-source consistent) + **Substrate**: `ss58Format=5` (E4, **unique value; Polkadot=0 / Kusama=2 / Acala=10 / Moonbeam=1284 all differ, unrelated to chain_id**) + chain name `"Astar"` (E3) + specName `"astar"` (E12) |
| Node application | **astar-collator v5.48.0** (E8 `system_version:"5.48.0-00338639b9e"`, E12 `specVersion:2101`, based on Substrate / Polkadot-SDK + frontier (pallet-evm + pallet-ethereum) + **pallet-contracts (WASM smart contract, ink!)** + cumulus (parachain consensus)) |
| Parachain | **Polkadot parachain, para_id = 2006** (won first slot auction 2021-12, same batch as Moonbeam; **Shiden** is the Kusama sister chain `para_id=2007`, **Shibuya** is testnet) |
| Survey date | 2026-05-23 |
| Status | 🟢 Done (diff-only, wave 8 closing) |
| Compat with 02-ethereum | **~95%** EVM JSON-RPC layer 100% isomorphic (`eth_*` / `net_*` all standard, 4-fold verified E1+E2+E7+E9), **~5% diff** = very high baseFee (E7 gasPrice `0xb576270823` ≈ **778 Gwei**, 25× Moonbeam, due to Astar's high `MinGasPrice` config not on-chain congestion) + finality via Polkadot GRANDPA |
| Compat with 07-polkadot | **~70%** Substrate RPC layer (`system_*` / `chain_*` / `state_*` all 200), business diff **~30%**: no `staking pallet` (collator + self-built `dappStaking`) + **unique `dappStaking` pallet (dApp staking incentives, Astar's signature feature)** + includes `contracts` pallet (WASM ink!, not on Polkadot relay) |
| Compat with 27-acala | **~80% same-pattern**: both "Polkadot parachain + embedded EVM"; Acala EVM is **custom mandala EVM (opcode trimmed, requires substrate account binding)**, Astar EVM is **standard frontier zero-trim**; **Astar has extra WASM VM, Acala has no WASM** |
| Compat with 28-moonbeam | **~85% same-pattern**: both frontier standard EVM zero-trim + Substrate single runtime; **Moonbeam consensus = Nimbus, Astar = Aura** (E5 digest evidence) + **Astar has extra WASM VM + unique dapps_staking pallet** + Moonbeam ss58=1284 aligned to chain_id while Astar ss58=5 independent |

---

## 1. Sources (canonical + fork history)

| Type | URL | Note |
|---|---|---|
| Official docs | https://docs.astar.network/ | Astar protocol docs, contains EVM + WASM dual tutorials |
| GitHub (node) | https://github.com/AstarNetwork/Astar | astar-collator source, **fork from polkadot-sdk + frontier + pallet-contracts**; E8 `5.48.0` is node version, E12 `specVersion=2101` is runtime |
| Frontier (EVM bridge) | https://github.com/polkadot-evm/frontier | Same as 28-moonbeam — pallet-evm + pallet-ethereum; **Astar and Moonbeam share the same frontier upstream, no fork** |
| pallet-contracts | https://github.com/paritytech/polkadot-sdk/tree/master/substrate/frame/contracts | WASM smart contract runtime, **ink!** (Rust → WASM) is its official DSL; Astar fully enables it |
| ink! | https://use.ink/ | Rust eDSL → wasm32 bytecode → pallet-contracts |
| EVM RPC (official) | https://evm.astar.network | E1/E2/E7/E9 verified; **also responds to `system_chain`** (E11 confirmed) |
| Substrate RPC (official) | https://rpc.astar.network | E3-E6/E8/E12 verified; **also responds to `eth_chainId`** (E10 confirmed); **two hostnames are essentially the same RPC server, DNS split is just client-semantic hint** |
| Substrate WSS | wss://rpc.astar.network | Subscriptions must go here |
| Explorer (EVM) | https://astar.blockscout.com/ | Blockscout |
| Explorer (Substrate) | https://astar.subscan.io/ | Subscan, bidirectional 0x... or a... lookup |
| Polkadot.js Apps | https://polkadot.js.org/apps/?rpc=wss://rpc.astar.network | extrinsic / dappStaking / WASM contract entry |

**Fork history**: `astar` forks from Parity's `substrate` + `polkadot-sdk`, core innovation = **EVM + WASM dual VM in the same runtime**: `pallet-evm` (frontier, executes EVM bytecode) + `pallet-contracts` (Substrate official, executes WASM ink! contracts). **The two contract systems use different account spaces**: EVM uses H160, WASM uses AccountId32 (ss58). **Astar team's `unified accounts` upgrade (2024, runtime ≥2000 series)** introduces `pallet-unified-accounts` to bidirectionally map H160 ↔ AccountId32 (on-chain registration), solving dual-VM account fragmentation. E12 `specVersion=2101` already includes this upgrade. **Key diff vs Moonbeam**: Moonbeam is EVM-only with Nimbus consensus; Astar is dual-VM with Aura consensus (E5 `0x06617572 61 ...` = `aura` prefix, **byte-level different from Moonbeam's `0x066e6d6273` = `nmbs`**).

---

## 2. Relations to Ethereum / Polkadot / Moonbeam (family boundary + wave-8 closing comparison)

| Dimension | Ethereum (02) | Polkadot (07) | Moonbeam (28) | Acala (27) | Astar (29) | Reuse verdict |
|---|---|---|---|---|---|---|
| Family | EVM | Substrate | dual: evm.primary + substrate.secondary | dual: substrate.primary + evm+.embedded | **dual: substrate.primary + evm.embedded + wasm.embedded** | ⚠️ Three-way choice, **evm_layer.priority enum already stable** (see §7) |
| Adapter | EthereumAdapter | SubstrateAdapter | Eth + Sub dual | Eth (trimmed) + Sub dual | **Eth + Sub dual** (WASM reuses Sub author_submitExtrinsic, **no new adapter needed**) | ✅ Zero new adapter |
| Consensus | Gasper | BABE+GRANDPA | Nimbus + relay GRANDPA | Aura + relay GRANDPA | **Aura + relay GRANDPA** (E5 verified) | ⚠️ Same as 27-acala |
| Block time | 12s | 6s | 12s | 12s | **12s** (E2 vs historical blocks, **matches parachain slot limit**) | ✅ Same as 28/27 |
| Finality | ~12-15 min | GRANDPA 12-60s | 30-60s (inherited from relay) | 30-60s | **30-60s** (same) | ✅ Same pattern |
| EVM completeness | 100% | ❌ | 100% frontier | **~85%** (trimmed) | **100% frontier** (same as Moonbeam) | ✅ Full reuse |
| **WASM VM** | ❌ | ❌ (relay does not include) | ❌ | ❌ | **✅ pallet-contracts + ink!** | ❌ **Unique to this chain**, §7 gives DSL evaluation |
| Native token | ETH | DOT (10 dec, prefix=0) | GLMR (18 dec, prefix=1284) | ACA (12 dec, prefix=10) | **ASTR (18 dec, prefix=5)** (E4 verified) | ⚠️ Same precision as Moonbeam, prefix unique |
| Address | `0x...` | `G...` | dual (algorithmic binding) | dual (on-chain mapping) | **Three layers**: `0x...` (EVM contract/EOA) + `a...` (ss58, prefix=5) + **unified-accounts on-chain mapping** (2024, explicit binding) | ⚠️ One more layer than Moonbeam/Acala |
| Gas / Fee | EIP-1559 | weight + length | EIP-1559 (~31 gwei) | EIP-1559 (trimmed) | **EIP-1559** (E7 ~778 gwei, **MinGasPrice config high, not congestion**) | ⚠️ Value high, model standard |
| Unique pallets | (none) | (no EVM) | parachainStaking + xcm suite | EVM+ + Acala finance suite | **`dappStaking` (v3, launched 2024, **Astar signature**: dApp registers → users/builders stake bidirectionally → block rewards split between dev + stakers) + `contracts` (WASM ink!) + `xcAssetConfig` + `xvm` (EVM ↔ WASM cross-VM call) + `unifiedAccounts`** | ❌ New in this doc |
| XCM assets | ❌ | ✅ | ✅ (xc prefix) | ✅ (same pattern) | **✅ `xc...` assets** (xcDOT/xcUSDT etc., registered via `xcAssetConfig`) | ✅ Reuses wave-8 pattern |

---

## 3. Public endpoint empirical (12/12 = 200)

| # | Method | Endpoint | Response | Note |
|---|---|---|---|---|
| E1 | `eth_chainId` | evm.astar.network | `0x250` = 592 ✅ | EVM ChainID, **double-source (E1+E9) consistent** |
| E2 | `eth_blockNumber` | same | `0xcd10ec` = 13,439,724 | EVM current height, byte-level equal to E5 Substrate `number` |
| E3 | `system_chain` | rpc.astar.network | `"Astar"` | Substrate chain name |
| E4 | `system_properties` | same | `{ss58Format:5, tokenDecimals:18, tokenSymbol:"ASTR"}` | **ss58Format=5 unique** (no reference chain uses this value) |
| E5 | `chain_getHeader` | same | `number:0xcd10ec`, digest.logs = `[aura(0x06617572...), RPSR, fron, aura-seal]` | **Aura consensus + frontier seal, byte-level different from Moonbeam Nimbus** |
| E6 | `system_health` | same | `{peers:40, isSyncing:false, shouldHavePeers:true}` | parachain collator peers |
| E7 | `eth_gasPrice` | evm.astar.network | `0xb576270823` ≈ **778 Gwei** | **MinGasPrice high**, Acala/Moonbeam both < 50 gwei |
| E8 | `system_version` | rpc.astar.network | `"5.48.0-00338639b9e"` | astar-collator node version + git commit |
| E9 | `net_version` | evm.astar.network | `"592"` | Consistent with E1 ✅ |
| **E10** | `eth_chainId` | **rpc.astar.network** (Substrate hostname) | `0x250` ✅ | **Cross-endpoint check: Substrate hostname responds to EVM method, confirms same RPC server** |
| **E11** | `system_chain` | **evm.astar.network** (EVM hostname) | `"Astar"` ✅ | **Cross-endpoint reverse check: EVM hostname responds to Substrate method** |
| E12 | `state_getRuntimeVersion` | rpc.astar.network | `{specName:"astar", specVersion:2101, apis:[..."0xf3ff14d5ab527059":3..., ContractsApi hash visible]}` | **Runtime enables pallet-contracts** (WASM contract API registered) + 20 total runtime APIs (EVM + WASM + standard) |

**Key finding 1**: Astar shares Moonbeam's **single-endpoint dual-protocol** pattern (same RPC server underneath), but Astar team **additionally exposes two DNS hostnames** (`evm.` / `rpc.`) as client-semantic hints; empirically interchangeable — vs 28-moonbeam's single hostname `rpc.api.moonbeam.network`, Astar's **dual-hostname pattern** has **zero impact on benchmark DSL** (`endpoint.http` picks one is enough).

**Key finding 2**: ContractsApi and EthereumRuntimeRPCApi are both registered in `state_getRuntimeVersion.apis` — this is **the minimal-cost way to confirm WASM + EVM dual VM activation**, no need to deep-parse metadata, benchmark explorer can directly reuse this method.

**Key finding 3**: E7 gasPrice is anomalously high (778 gwei vs Moonbeam 31 gwei) because Astar runtime `MinGasPrice` is hard-coded high, **unrelated to on-chain congestion**; benchmark reporting EVM `eth_estimateGas` × `eth_gasPrice` should note that **Astar's gas-cost-USD ≠ on-chain activity signal**.

---

## 4. Substantive diff table (only diffs)

| Dimension | Ethereum (02) | Polkadot (07) | Moonbeam (28) | Astar (29) |
|---|---|---|---|---|
| RPC endpoint topology | single-endpoint EVM | single-endpoint Substrate | single-endpoint dual-protocol (method-prefix dispatch) | **Dual-hostname single RPC server** (`evm.` and `rpc.` interchangeable, E10/E11 verified) |
| Block height mapping | `eth_blockNumber` | `chain_getHeader.number` | 1:1 same | **1:1 same** (E2 `0xcd10ec` ⇔ E5 `number:0xcd10ec`) |
| Finality query | `eth_getBlockByNumber("finalized",..)` | `chain_getFinalizedHead` | both | **Both** (same as Moonbeam) |
| Tx submission | `eth_sendRawTransaction` | `author_submitExtrinsic` | both | **Three coexist**: EVM tx / Substrate extrinsic / **WASM contracts call** (last one goes via `author_submitExtrinsic` wrapping `contracts.call` extrinsic) |
| Contract deploy | Solidity → bytecode | ink! → WASM (relay does not support) | Solidity only | **Dual track**: Solidity → bytecode → `pallet-evm.create` + ink! (Rust) → wasm32 → `pallet-contracts.instantiateWithCode` |
| Cross-VM call | N/A | N/A | N/A | **`xvm` pallet** (2024, EVM contracts can call WASM contracts and vice versa — **industry exclusive**) |
| Staking incentive | PoS validator | NPoS | parachainStaking (collator/delegator) | **dappStaking v3**: dApp registers → users stake to dApp → block rewards split dev + users, **Astar signature product** |
| Governance | off-chain (EIP) | OpenGov | OpenGov | **`council` + `democracy` + `treasury` (classic Substrate trio, has not migrated to OpenGov)** |

---

## 5. Method diff + unique pallets / precompiles / cross-VM

**Fully reused from Ethereum**: `eth_chainId` / `eth_blockNumber` / `eth_getBlockByNumber` / `eth_getBlockByHash` / `eth_getTransactionByHash` / `eth_getTransactionReceipt` / `eth_getBalance` / `eth_call` / `eth_estimateGas` / `eth_gasPrice` / `eth_sendRawTransaction` / `eth_getLogs` / `eth_subscribe` (WSS) / `net_version` / `net_peerCount` / `web3_clientVersion` — **directly reuses EthereumAdapter, zero modification**.

**Fully reused from Polkadot**: `system_chain` / `system_name` / `system_version` / `system_health` / `system_properties` / `system_peers` / `chain_getHeader` / `chain_getBlock` / `chain_getBlockHash` / `chain_getFinalizedHead` / `state_getMetadata` / `state_getRuntimeVersion` / `state_getStorage` / `author_submitExtrinsic` / `author_pendingExtrinsics` — **directly reuses SubstrateAdapter**.

**Astar-unique pallets (extrinsic namespaces)** (⚠️ docs-only + E12 runtime-api hash circumstantial):
- `dappStaking.{registerDapp, stake, unstake, claimStakerRewards, claimDappRewards, unbondAndUnstake}` — **dApp staking incentive, Astar signature**
- `contracts.{instantiateWithCode, instantiate, call, uploadCode, removeCode}` — **WASM contract (ink!) entry**
- `xvm.call` — **EVM ↔ WASM cross-VM call** (2024, industry-exclusive)
- `unifiedAccounts.{claimEvmAddress, claimDefault}` — H160 ↔ AccountId32 on-chain mapping
- `xcAssetConfig` — XCM asset metadata
- `evm` / `ethereum` — frontier pallet (same as Moonbeam)
- `council` / `democracy` / `treasury` / `preimage` — classic Substrate governance

**Astar-unique precompiles** (EVM side calling Substrate features):
- `0x0000000000000000000000000000000000005001` — DappStaking precompile (stake to dApp from inside EVM)
- `0x0000000000000000000000000000000000005002` — SR25519 signature verify
- `0x0000000000000000000000000000000000005005` — XVM (EVM calls WASM contract)
- `0xFFFFFFFF<assetId>` — pallet-assets ERC20 wrapper (same pattern as Moonbeam)

**WASM call model** (key — determines whether new DSL is needed):
- Deploy: `contracts.uploadCode(wasm_bytes)` → `contracts.instantiate(code_hash, salt, data)`
- Call: `contracts.call(dest_account, value, gas_limit, storage_deposit_limit, data)`
- **Transport layer 100% reuses `author_submitExtrinsic`** (SCALE-encoded extrinsic), **RPC layer introduces no new method**
- **DSL impact evaluation**: WASM call looks identical to a regular Substrate extrinsic from the RPC adapter's POV; **only new information is the appearance of `contracts.*` in pallet_set** → **no new DSL field needed, existing `substrate_layer.pallets_extra` covers it** (see §7)

---

## 6. Real payloads (benchmark reuse mode)

| Scenario | Path | Reuse |
|---|---|---|
| EVM block fetch | `eth_getBlockByNumber("latest", true)` | ✅ Full reuse 02-ethereum payload |
| EVM tx receipt | `eth_getTransactionReceipt(0x...)` | ✅ Full reuse |
| EVM ERC20 balance | `eth_call({to:0xFFFFFFFF...<assetId>, data:0x70a08231...})` | ⚠️ xc asset via precompile address, same as Moonbeam |
| Substrate header | `chain_getHeader` | ✅ Full reuse 07-polkadot |
| Substrate finalized | `chain_getFinalizedHead` | ✅ Full reuse |
| ASTR native transfer (EVM) | `eth_sendRawTransaction` (EIP-1559 tx) | ✅ Reuses 02-ethereum payload |
| ASTR native transfer (Sub) | `author_submitExtrinsic` (balances.transfer encoded) | ✅ Reuses 07-polkadot payload |
| dApp Staking | `author_submitExtrinsic` (dappStaking.stake encoded) | ❌ New SCALE encoding ⚠️ docs-only |
| **WASM contract call** | `author_submitExtrinsic` (contracts.call encoded) | ⚠️ **Transport layer 100% reuses Polkadot adapter**, payload is SCALE-encoded `contracts.call(...)` — **this benchmark needs no new RPC adapter** |
| **XVM cross-VM call** | EVM `eth_call` → precompile `0x5005` (EVM → WASM) or Substrate `xvm.call` (WASM → EVM) | ⚠️ Astar-exclusive, optional benchmark scenario |
| XCM cross-chain | `author_submitExtrinsic` (xTokens.transferMultiasset encoded) | ✅ Reuses Moonbeam wave-8 pattern |

---

## 7. DSL decisions (wave 1-8, 28 chains — end-state evaluation)

Predicted DSL fields (Astar this chain):

```yaml
chain: astar
chain_id_evm: 592               # E1 verified
parachain_id: 2006              # public knowledge
family:
  primary: substrate            # ⭐ Inverted vs Moonbeam — Astar's governance/incentive primary is Substrate
  embedded: [evm, wasm]         # ⭐⭐ First time wasm appears in wave 1-8
adapter:
  primary: SubstrateAdapter     # ~70% reuse 07-polkadot
  secondary: EthereumAdapter    # ~95% reuse 02-ethereum
evm_layer:
  priority: secondary           # Inverted vs Moonbeam=primary (same as Acala/Injective)
  chain_id: 592
  min_gas_price_gwei: 778       # ⚠️ High, not congestion
  precompiles_extra:
    - {addr: "0x0000000000000000000000000000000000005001", name: "DappStaking"}
    - {addr: "0x0000000000000000000000000000000000005005", name: "XVM"}
    - {addr_prefix: "0xFFFFFFFF", name: "AssetsErc20"}
wasm_layer:                     # ⭐⭐ New field (discussion in ASK below)
  enabled: true
  pallet: contracts             # pallet-contracts
  dsl: ink!                     # Rust eDSL → wasm32
substrate_layer:
  ss58_prefix: 5
  pallets_extra: [contracts, dappStaking, xvm, unifiedAccounts, xcAssetConfig, evm, ethereum]
xcm:
  enabled: true
  version: v3
endpoint:
  http: https://evm.astar.network    # rpc.astar.network also works, E10/E11 equivalent
  wss: wss://rpc.astar.network
```

### 7.1 **Does WASM need a new DSL? — Verdict: NO**

**Argument**:
1. RPC transport 100% reuses `author_submitExtrinsic` (SCALE-encoded `contracts.*` extrinsic), no new method
2. Benchmark cares about **RPC-side throughput / latency**, not WASM bytecode compilation or contract semantics
3. `contracts` pallet appearing in `pallets_extra` is enough to trigger **optional** WASM probes (`state_call::ContractsApi_call`), handled like any other pallet

**Sole recommendation** (optional L2): add a `wasm_layer.enabled: bool` flag as **explicit hint** (avoid main controller having to detect `'contracts' in pallets_extra`), so scenario scheduler can toggle WASM probes. **Rating L2 (deferrable)** because only Astar triggers it; if no further WASM chain appears in wave 9+, this can be permanently shelved.

### 7.2 **Wave 7+8 cumulative DSL ASK end-state integration table (28-chain survey complete)**

| ASK | Field | Trigger chains | End-state | Wave-8 closing evaluation |
|---|---|---|---|---|
| **A** | `module_set` / `pallet_set` | cosmos all + substrate all | **L1 must** ✅ | 4 chains × 2 families verified zero-conflict, **finalized stable** |
| **B** | `denom_format` | cosmos (uatom/inj/uosmo/utia) | **L1 must** ✅ | wave-7 4 chains verified, **finalized stable** |
| **C** | `evm_layer` (section) + `evm_layer.priority` (enum) | 12/15/16/17/18/24/27/28/29 | **L1 must** ✅ | wave-8 4 chains (Acala/Moonbeam/Astar + Kusama N/A) confirms enum tri-value `primary` / `secondary` / unset — **finalized stable** |
| **D** | `hot_endpoints` | all chains | **L1 must** ✅ | All 28 chains covered, **finalized stable** |
| **E** | `rollup_type` + `modular_da` | 15/16/17/18/23 (L2/L1-DA) | **L1 must** ✅ | wave-1 landed, no new in wave-8, **finalized stable** |
| **F** | `dual_address` (bool) | 25-sei / 27-acala / 29-astar (unified) | **L1 recommended** ✅↑ | **wave-8 upgrade**: Astar `unifiedAccounts` is the 3rd evidence, **upgrade L1 recommended → L1 must candidate** (3 chains covered, pattern stable) |
| **G** | `evm_parallelism` | 25-sei | **L2 deferrable** | Only Sei, **keep deferred** |
| **H** | (empty placeholder) | — | — | — |
| **I** | `native_token` arrayed | 13-avalanche-x (AVAX cross-subnet) + 24-injective (INJ + xc) + 28-moonbeam (GLMR + xcDOT etc.) + 29-astar (ASTR + xcDOT etc.) | **L1 must** ✅↑ | **wave-8 4-chain confirmed**, upgrade L1 recommended → **L1 must** |
| **J** | substrate `pallet_set` (same as A, but substrate subset) | 07/26/27/28/29 | **L1 must** ✅ | All 5 chains covered, **finalized stable** |
| **K** | `parachain` section (`id` + `relay`) | 26-kusama (relay) + 27/28/29 (para) | **L2 deferrable** | 4-chain verification trivial pattern, **keep deferred** |
| **L (new)** | `wasm_layer.enabled` | 29-astar | **L2 deferrable** ⚠️ | **Wave-8 only 1 chain**, shelved |
| **M (new)** | `xcm` (section) | 07/26/27/28/29 | **L2 recommended** | **5-chain verified**, upgrade to L1 if wave 9+ includes parachain batch |

**ASK#29-1 (main controller)**:
> **Wave 1-8, 28-chain survey complete. Should the DSL ASK set be finally frozen?** Current state: **L1-must 7 items** (A/B/C/D/E/I/J) + **L1-recommended 1 item** (F) + **L2-deferrable 4 items** (G/K/L/M). **Recommend main controller adopts L1-must 7 items into schema main development**, L1-recommended 1 (F dual_address) goes into v1.0 candidate, L2-deferrable 4 go into backlog. **WASM (L) single-chain trigger, pure optional probe, does not enter schema**. **XCM (M) gets upgraded if parachain batch expanded in future**. **evm_layer.priority enum tri-value finally confirmed**: `primary` / `secondary` / unset (default primary, Substrate-only chains do not set evm_layer section).

### 7.3 **28-chain survey end-state summary** (one-liner version)

> 28 chains landed across 8 waves, **0 new adapters** (all reuse EthereumAdapter / SubstrateAdapter / CosmosAdapter / BitcoinAdapter / Solana / Aptos / Near / Tron / Tezos / Algorand / Hedera etc. from waves 1-6), **12 DSL field candidates collapse to 7 must + 1 recommended + 4 deferred**, **dual-protocol chains (Moonbeam/Acala/Injective/Astar) reuse primary adapters with zero field conflicts**, **WASM dual-VM does not need new DSL**; benchmark main line can lock L1's 7 fields into v1.0 schema.

---

## 8. H8 evidence (12 curls, all 200)

```bash
# E1 EVM ChainID
curl -s -X POST https://evm.astar.network \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}'
# {"result":"0x250"}                              # 0x250 = 592 ✅

# E2 EVM blockNumber
# {"result":"0xcd10ec"}                           # = 13,439,724

# E3 Substrate system_chain
# {"result":"Astar"}

# E4 system_properties — ss58Format=5 unique
# {"result":{"ss58Format":5,"tokenDecimals":18,"tokenSymbol":"ASTR"}}

# E5 chain_getHeader — Aura consensus + frontier seal
# {"result":{"number":"0xcd10ec","parentHash":"0xf03b...","digest":{"logs":[
#   "0x06617572...",   # aura (Aura slot)
#   "0x04525053...",   # RPSR (relay parent storage root)
#   "0x0466726f6e...", # fron (frontier seal)
#   "0x05617572...",   # aura (Aura seal)
# ]}}}                                            # ⚠️ Moonbeam uses nmbs, Astar uses aura

# E6 system_health
# {"result":{"peers":40,"isSyncing":false,"shouldHavePeers":true}}

# E7 EIP-1559 gasPrice
# {"result":"0xb576270823"}                       # ≈ 778 Gwei ⚠️ MinGasPrice high

# E8 runtime version
# {"result":"5.48.0-00338639b9e"}

# E9 net_version
# {"result":"592"}                                # Consistent with E1 ✅

# E10 ⭐ Cross-endpoint check (Substrate hostname responds to EVM method)
curl -s -X POST https://rpc.astar.network -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":10,"method":"eth_chainId","params":[]}'
# {"result":"0x250"} ✅                           # Two hostnames same RPC server

# E11 ⭐ Cross-endpoint reverse check (EVM hostname responds to Substrate method)
curl -s -X POST https://evm.astar.network -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":11,"method":"system_chain","params":[]}'
# {"result":"Astar"} ✅

# E12 ⭐ runtime apis — verifies WASM (ContractsApi) + EVM (EthereumRuntimeRPCApi) dual registration
# {"result":{"specName":"astar","specVersion":2101,"apis":[
#   ["0xdf6acb689907609b",5], ["0x37e397fc7c91f5e4",2], ... # 20 api hashes, contains ContractsApi
# ]}}
```

**Reuse conclusion**: **EVM side 95% directly reuses 02-ethereum benchmark suite** (opcode / RPC / Gas / EIP-1559 all standard, same as Moonbeam), **Substrate side 70% directly reuses 07-polkadot suite** (`system_*` / `chain_*` isomorphic, business pallet diff larger), **WASM side 100% reuses author_submitExtrinsic transport (zero new method)**; overall new workload only **~10%** (dappStaking / xvm / contracts extrinsic SCALE encoding — all ⚠️ docs-only, benchmark main line can defer). **Astar is the last chain in the wave 1-8 / 28-chain survey, this doc recommends main controller freeze L1-must 7 items + L1-recommended 1 item after this submission**.
