# 28-moonbeam Research (DIFF-ONLY)

> Derived from `_template.md`. **Most aggressive DIFF-ONLY mode (guardrail 2)**: this chain is a **Polkadot parachain (parachain ID=2004, won 2021 slot auction)** + **100% Ethereum-compatible EVM** (full Solidity / Web3 tooling / standard JSON-RPC; **even more "standard EVM" than 12-avalanche-c, 15-arbitrum, 16-optimism** because it does **zero opcode/Gas-model trimming**). This doc does **not** re-derive 02-ethereum / 07-polkadot protocol structures, only lists the **dual-protocol priority inversion + parachain embedding + XCM cross-chain assets** delta; and cross-validates reuse against **wave-7 sibling 24-injective (Cosmos+EVM dual-protocol)** and **wave-1 dual-protocol 17-zksync-era / 18-linea**. H8: 9 live curls on **2026-05-23** against public mainnet endpoint `https://rpc.api.moonbeam.network`, **all 9 returned 200/success** (6 EVM + 3 Substrate, **single-endpoint dual-protocol reuse ✅**). XCM precompile / pallet-evm extrinsic deferred due to budget/approval cutoff, marked ⚠️ doc-only.

---

## Meta

| Field | Value |
|---|---|
| Chain (zh) | 月光束 |
| Chain (en) | Moonbeam Network |
| No. | 28 |
| Mainnet ChainID | **EVM primary**: `1284` (E1 live `result:"0x504"` ✅, E9 `net_version:"1284"` dual-source) + **Substrate secondary**: `SS58Prefix=1284` (E4 live, **numerically identical to EVM ChainID — Moonbeam team intentionally aligned, unique among family=substrate**) + Substrate chain name `Moonbeam` (E3) |
| Node app | **moonbeam-node v0.51.2** (E8 `system_version:"0.51.2-16fe6f71de5"`, built on Substrate / Polkadot-SDK + frontier (pallet-evm + pallet-ethereum) + cumulus (parachain consensus)) |
| Parachain | **Polkadot parachain, para_id = 2004** (2021-12 round-2 slot auction winner, 96-week lease + renewal; Kusama sister chain **Moonriver para_id=2023**) |
| Research date | 2026-05-23 |
| Status | 🟢 Done (diff-only) |
| Compat. vs 02-ethereum | **~95%** EVM JSON-RPC layer 100% isomorphic (`eth_*` / `net_*` / `web3_*` all standard, **confirmed E1+E2+E7+E9**), **~5% delta** = 12s blocks (same as Ethereum 12s but finality via GRANDPA, not PoS slot vote) + EIP-1559 default-on with very low baseFee (E7 gasPrice 31.25 gwei) + no PoW/MEV-Boost concept |
| Compat. vs 07-polkadot | **~70%** Substrate RPC layer (`system_*` / `chain_*` / `state_*` E3+E4+E5+E6 live 200), but **business-layer delta ~30%**: no `staking` pallet (collators use cumulus + nimbus) + no `balances` pallet direct transfer (assets all via EVM layer) + Moonbeam-only `parachainStaking` / `ethereumXcm` / `xcmTransactor` / `assets` (XCM assets) pallets |
| Compat. vs 24-injective | **~60% pattern same**: both are "primary-protocol + embedded-EVM" dual-port, but Moonbeam **EVM is primary (user surface), Substrate is secondary (consensus/gov)**; Injective **Cosmos primary, EVM secondary**; priorities **fully inverted** |

---

## 1. Sources (authority + fork history)

| Type | URL | Notes |
|---|---|---|
| Official docs | https://docs.moonbeam.network/ | Protocol docs, EVM tutorial + XCM guide |
| GitHub (node) | https://github.com/moonbeam-foundation/moonbeam | moonbeam-node source, **fork from substrate / polkadot-sdk + frontier (Parity EVM bridge) + cumulus (parachain runtime)**; E8 `0.51.2` is runtime version |
| Frontier (EVM bridge) | https://github.com/polkadot-evm/frontier | **pallet-evm + pallet-ethereum + pallet-base-fee + rpc-ethereum**, embeds EVM in any Substrate runtime — **Moonbeam is its flagship; Astar/HydraDX/Acala also use it** |
| EVM RPC (official) | https://rpc.api.moonbeam.network | **Single HTTP POST endpoint serves both EVM and Substrate protocols** (E1-E9 live), JSON-RPC `method` namespace dispatches |
| Substrate WSS | wss://wss.api.moonbeam.network | WebSocket; subscriptions / state subscribe must use WSS (HTTP endpoint has no sub support) |
| Explorer (EVM) | https://moonbeam.moonscan.io/ | **Etherscan fork**, lookup by 0x... |
| Explorer (Substrate) | https://moonbeam.subscan.io/ | Subscan, lookup by G... ss58 or 0x... (bidirectional) |
| Polkadot.js Apps | https://polkadot.js.org/apps/?rpc=wss://wss.api.moonbeam.network | Substrate-side extrinsic submission / gov / staking entry |
| XCM docs | https://docs.moonbeam.network/builders/interoperability/xcm/overview/ | XCM v3 cross-chain msgs; xcUSDT / xcUSDC / xcDOT etc. "xc-assets" all in `pallet-assets` |

**Fork history**: `moonbeam` forked from Parity's `substrate` + `polkadot-sdk` (which consolidated substrate / polkadot / cumulus in 2024). Core innovation is the **frontier suite** (`pallet-evm` + `pallet-ethereum` + `pallet-base-fee` + `fc-rpc`), running SputnikVM (Rust EVM impl) inside WASM runtime and exposing **byte-compatible `eth_*` RPC** at the RPC layer. E8 `system_version:"0.51.2-16fe6f71de5"` is runtime spec version + git commit; **moonbeam runtime version is independent of polkadot-sdk version** (polkadot-sdk currently on stable2412 line). **Key delta vs Acala (also EVM-on-Substrate)**: Acala uses self-built mandala EVM (trims some opcodes, requires Substrate account binding); Moonbeam uses frontier **zero-trim** — any Solidity contract + Hardhat/Foundry/MetaMask deploys **with zero modification**.

---

## 2. Dual relationship with Ethereum / Polkadot (family boundary)

| Dim | Ethereum (02) | Polkadot (07) | Moonbeam (28) | Reuse |
|---|---|---|---|---|
| Family | EVM | Substrate | **dual: family.primary=evm, family.secondary=substrate** | ⚠️ new DSL field (§7) |
| Adapter | EthereumAdapter | SubstrateAdapter (wave 2) | **EthereumAdapter (primary, ~95% reuse)** + SubstrateAdapter (secondary, ~70% reuse) | ✅ dual reuse, no new adapter |
| Consensus | Gasper (PoS + LMD-GHOST + Casper FFG) | BABE+GRANDPA | **Nimbus (parachain collator selection) + inherits Polkadot relay-chain BABE+GRANDPA finality** (parachain block finalized only after entering relay-chain) | ❌ new "inherited finality" concept |
| Block time | 12s | 6s | **12s** (parachain bound by relay-chain slot, **coincidentally same as Ethereum**, E5 `number=0xf01ff8=15737336`) | ⚠️ same number as Ethereum, totally different mechanism |
| Finality | ~12-15 min (2 epochs) | GRANDPA 12-60s | **GRANDPA via relay-chain backed → included → finalized, typically 30-60s** | ⚠️ ~15× faster than Ethereum |
| EVM completeness | 100% reference | ❌ none | **100%** (full opcodes, EIP-1559 / EIP-2930 / EIP-2718 / EIP-155 all on) | ✅ reuses EthereumAdapter |
| Native token | ETH (18 dec) | DOT (10 dec, SS58 prefix=0) | **GLMR (18 dec, E4 `tokenDecimals:18, tokenSymbol:"GLMR"`) + SS58 prefix=1284 (unique, **intentionally aligned with EVM ChainID**)** | ⚠️ precision same as ETH, prefix unique |
| Address | `0x...` (20 bytes) | `G...` (SS58) | **Dual address space**: `0x...` and `G...` **bound by one-way `H160 ↔ AccountId32` padding** (`AccountId32 = H160 + 0x00*12`, **deterministic algorithm**, no on-chain mapping store needed) | ❌ new |
| Gas / fee | EIP-1559 baseFee+tip (wei) | weight + length (plank) | **EIP-1559** (E7 live `eth_gasPrice:"0x746a52880"≈31.25 gwei`) — frontier converts weight to gas, user only sees wei | ✅ EVM-side standard |
| Unique modules/pallets | (none) | (no EVM) | `parachainStaking` (collator/delegator staking, **replaces Polkadot's NPoS, Moonbeam-original**) + `ethereumXcm` (XCM → EVM call, cross-chain contract calls) + `xcmTransactor` / `xTokens` (XCM asset bridge) + `assets` (pallet-assets, **xc-asset storage**) + `proxy` / `democracy` / `treasury` / `councilCollective` / `referenda` (gov) | ❌ new |
| XCM assets | ❌ | ✅ (native DOT XCM) | **xcUSDT / xcUSDC / xcDOT / xcINTR / xcASTR / ... 20+ total** | ❌ new |

---

## 3. Public RPC live evidence (9/9 returned 200)

| # | Method | Endpoint | Response | Note |
|---|---|---|---|---|
| E1 | `eth_chainId` | rpc.api.moonbeam.network | `0x504` = 1284 ✅ | EVM ChainID, **dual-source (E1+E9) consistent** |
| E2 | `eth_blockNumber` | same | `0xf01ff8` = 15737336 | EVM current block (1:1 with Substrate block) |
| E3 | `system_chain` | same | `"Moonbeam"` | Substrate chain name |
| E4 | `system_properties` | same | `{SS58Prefix:1284, tokenDecimals:18, tokenSymbol:"GLMR"}` | **SS58Prefix=1284 numerically identical to EVM ChainID, unique example** |
| E5 | `chain_getHeader` | same | `number:0xf01ff8`, `parentHash:0x180e...`, `digest.logs:[5 entries: nmbs/rand/RPSR/fron]` | **digest contains frontier-engine logs, differs from pure Polkadot** |
| E6 | `system_health` | same | `{peers:38, isSyncing:false, shouldHavePeers:true}` | parachain collator peers |
| E7 | `eth_gasPrice` | same | `0x746a52880` ≈ 31.25 gwei | baseFee + tip, EIP-1559 active |
| E8 | `system_version` | same | `"0.51.2-16fe6f71de5"` | moonbeam runtime version + git commit |
| E9 | `net_version` | same | `"1284"` | EVM net id, matches E1 ChainID |

**Key finding**: **a single HTTP-POST JSON-RPC endpoint serves both `eth_*` and `system_*` / `chain_*` / `state_*`** — this is frontier's design (fc-rpc registers two RPC namespaces, dispatches by method prefix). **Implication: benchmark needs only 1 endpoint × 2 adapter call-sets**, no dual-endpoint config required.

---

## 4. Material differences vs Ethereum / Polkadot (delta-only)

| Dim | Ethereum (02) | Polkadot (07) | Moonbeam (28) |
|---|---|---|---|
| RPC endpoint topology | single EVM endpoint | single Substrate endpoint | **single endpoint dual-protocol** (method-prefix dispatch) |
| Block-height correspondence | `eth_blockNumber` | `chain_getHeader.number` | **two values numerically identical** (E2 `0xf01ff8` ⇔ E5 `number:0xf01ff8`), frontier 1:1 mapping |
| Finality query | `eth_getBlockByNumber("finalized",..)` | `chain_getFinalizedHead` | **both work**; `chain_getFinalizedHead` via GRANDPA (authoritative), `eth_getBlockByNumber("finalized")` is frontier translation (semantics slightly laggy ⚠️ doc-only) |
| Tx submission | `eth_sendRawTransaction` | `author_submitExtrinsic` | **both coexist**: EVM tx via `eth_sendRawTransaction` (wrapped as extrinsic by pallet-ethereum); Substrate extrinsic via `author_submitExtrinsic` (mandatory for gov / staking) |
| Transfer asset | ETH (native) | DOT (balances pallet) | **GLMR via EVM `eth_sendTransaction`** (coordinated by pallet-balances + pallet-evm) + xc-assets via EVM ERC20 interface (exposed by pallet-assets through **ERC20 precompile** at `0xFFFFFFFF...<assetId>`) |
| Contract deploy | Solidity → bytecode → CREATE | ink! / WASM → pallet-contracts | **Solidity → bytecode → CREATE** (fully standard; Hardhat / Foundry / Remix zero-config) |
| Cross-chain | bridge (external) | XCM (native) | **XCM native** (`xcmTransactor.transactThroughSigned`) + invoke from inside EVM via **XCM precompile `0x0000...0804`** |
| Governance | off-chain (EIPs) | OpenGov (referenda + conviction voting) | **OpenGov on-chain** (Moonbeam launched 2023-08, inherits Polkadot gov model) |

---

## 5. Method delta + unique pallets/precompiles

**Fully reused from Ethereum**: `eth_chainId` / `eth_blockNumber` / `eth_getBlockByNumber` / `eth_getBlockByHash` / `eth_getTransactionByHash` / `eth_getTransactionReceipt` / `eth_getBalance` / `eth_call` / `eth_estimateGas` / `eth_gasPrice` / `eth_sendRawTransaction` / `eth_getLogs` / `eth_subscribe` (WSS) / `net_version` / `net_peerCount` / `web3_clientVersion` / `txpool_status` — **all reused directly by EthereumAdapter, zero modifications**.

**Fully reused from Polkadot**: `system_chain` / `system_name` / `system_version` / `system_health` / `system_properties` / `system_peers` / `chain_getHeader` / `chain_getBlock` / `chain_getBlockHash` / `chain_getFinalizedHead` / `state_getMetadata` / `state_getRuntimeVersion` / `state_getStorage` / `author_submitExtrinsic` / `author_pendingExtrinsics` / `payment_queryInfo` — **reused directly by SubstrateAdapter**.

**Moonbeam-unique pallets (extrinsic namespaces)** (⚠️ doc-only; not E10-tested in this budget):
- `parachainStaking.{joinCandidates, delegate, executeDelegationRequest, scheduleLeaveCandidates}` — collator/delegator staking
- `ethereumXcm.transact` — invoke Moonbeam EVM contracts via XCM from other parachains
- `xcmTransactor.{transactThroughSigned, transactThroughDerivative}` — send XCM calls from Moonbeam to other parachains
- `xTokens.transferMultiasset` — XCM asset bridge
- `assets.{create, mint, burn, transfer}` — pallet-assets, xc-asset carrier
- `democracy` / `referenda` / `convictionVoting` / `treasury` / `preimage` — OpenGov

**Moonbeam-unique precompiles** (standard way for EVM-side to invoke Substrate functions):
- `0x0000000000000000000000000000000000000800` — ParachainStaking precompile (stake directly inside EVM)
- `0x0000000000000000000000000000000000000801` — Crowdloan rewards
- `0x0000000000000000000000000000000000000804` — XCM Utils
- `0x0000000000000000000000000000000000000808` — XCM Transactor
- `0xFFFFFFFF<assetId in hex>` — pallet-assets ERC20 wrapper (one address per xc-asset; xcUSDT/xcDOT/...)

---

## 6. Real payload (benchmark reuse map)

| Scenario | Path | Reuse |
|---|---|---|
| EVM block fetch | `eth_getBlockByNumber("latest", true)` | ✅ fully reuses 02-ethereum payload |
| EVM tx receipt | `eth_getTransactionReceipt(0x...)` | ✅ fully reused |
| EVM ERC20 balance | `eth_call({to:0xFFFFFFFF...<assetId>, data:0x70a08231...})` | ⚠️ xc-assets use precompile address; contract-call mode identical |
| Substrate header | `chain_getHeader` | ✅ fully reuses 07-polkadot |
| Substrate finalized | `chain_getFinalizedHead` | ✅ fully reused |
| GLMR native transfer | EVM `eth_sendRawTransaction` (EIP-1559 tx) | ✅ reuses 02-ethereum payload |
| XCM cross-chain | Substrate `author_submitExtrinsic` (xTokens.transferMultiasset encoded extrinsic) | ❌ new; requires SCALE encoding ⚠️ doc-only |

---

## 7. DSL decision (3 new fields + 1 ASK predicted)

Predicted DSL fields:

```yaml
chain: moonbeam
chain_id_evm: 1284              # E1 live
parachain_id: 2004              # public knowledge + docs
family:
  primary: evm                  # ⭐ primary protocol — users/dApps all use EVM
  secondary: substrate          # ⭐ secondary protocol — gov/staking/XCM via Substrate
adapter:
  primary: EthereumAdapter      # ~95% reused from 02-ethereum
  secondary: SubstrateAdapter   # ~70% reused from 07-polkadot
evm_layer:
  priority: primary             # ⭐ new field: opposite of 24-injective (secondary)
  chain_id: 1284
  precompiles_extra:            # ⭐ new field: Moonbeam-unique precompile block
    - {addr: "0x0000000000000000000000000000000000000800", name: "ParachainStaking"}
    - {addr: "0x0000000000000000000000000000000000000804", name: "XcmUtils"}
    - {addr_prefix: "0xFFFFFFFF", name: "AssetsErc20"}  # wildcard prefix
substrate_layer:
  ss58_prefix: 1284             # E4 live, numerically equals chain_id_evm (unique)
  pallets_extra: [parachainStaking, ethereumXcm, xcmTransactor, xTokens, assets]
xcm:
  enabled: true                 # ⭐ new field
  version: v3
  xc_assets_precompile_prefix: "0xFFFFFFFF"
endpoint:
  http: https://rpc.api.moonbeam.network    # single endpoint dual-protocol ✅
  wss: wss://wss.api.moonbeam.network
```

**New fields**: `evm_layer.priority` (enum `primary | secondary`, mutually exclusive with Injective), `xcm.enabled` + `xcm.version`, `evm_layer.precompiles_extra`.

**ASK (to orchestrator)**:

> **DSL ASK#28-1**: should `evm_layer.priority` be promoted to top-level DSL schema? 4 combinations confirmed — Moonbeam=primary (EVM is user surface) / Injective=secondary (EVM is secondary chain-id) / pure EVM (02/12/15/16/17/18, field omitted = primary) / pure Substrate (07, field omitted = N/A). **Recommendation**: make `evm_layer.priority` an enum, default `primary`; Injective explicitly overrides to `secondary`; Substrate-only chains do not set `evm_layer` block. **Also confirm**: should the `xcm` block be introduced uniformly across family=substrate chains (07/28/Acala/Astar/...) so wave-9+ parachain batches can reuse directly?

---

## 8. H8 evidence (9 curls, all 200)

```bash
# E1 EVM ChainID
curl -s -X POST https://rpc.api.moonbeam.network \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}'
# {"jsonrpc":"2.0","id":1,"result":"0x504"}                       # 0x504 = 1284 ✅

# E2 EVM blockNumber
# {"result":"0xf01ff8"}                                            # = 15,737,336

# E3 Substrate system_chain
# {"result":"Moonbeam"}

# E4 system_properties — SS58Prefix == ChainID (unique)
# {"result":{"SS58Prefix":1284,"tokenDecimals":18,"tokenSymbol":"GLMR"}}

# E5 chain_getHeader — digest contains frontier-engine logs
# {"result":{"number":"0xf01ff8","parentHash":"0x180e...","digest":{"logs":[
#   "0x066e6d6273...",   # nmbs (Nimbus collator slot)
#   "0x0672616e64...",   # rand (VRF randomness)
#   "0x04525053...",     # RPSR (relay parent storage root)
#   "0x0466726f6e...",   # fron (frontier seal)
#   "0x056e6d6273..."    # nmbs (nimbus consensus)
# ]}}}

# E6 system_health
# {"result":{"peers":38,"isSyncing":false,"shouldHavePeers":true}}

# E7 EIP-1559 gasPrice
# {"result":"0x746a52880"}                                         # ≈ 31.25 gwei

# E8 runtime version
# {"result":"0.51.2-16fe6f71de5"}

# E9 net_version (EVM dual-source)
# {"result":"1284"}                                                # matches E1 ✅
```

**Reuse conclusion**: **EVM side reuses 02-ethereum benchmark suite ~95% directly** (opcodes / RPC / Gas / EIP-1559 all standard), **Substrate side reuses 07-polkadot suite ~70% directly** (`system_*` / `chain_*` isomorphic; business pallets differ). Net new effort only **~10%** (XCM precompile calls + SCALE encoding for Moonbeam-only pallet extrinsics).
