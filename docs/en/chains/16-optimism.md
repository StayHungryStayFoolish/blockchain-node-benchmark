# 16-optimism (DIFF-ONLY)

> **This file derives from `_template.md` + Wave5 EVM-L2 diff-only style (guardrail #2).**
> **Per H8 (real evidence): live `curl` + official-doc URLs + access dates.**
> Any assertion not 100% empirically verified is explicitly tagged ⚠️.
> **Diff-only note**: Optimism = 100% EVM-equivalent (post-Bedrock). The eight core JSON-RPC methods (`eth_chainId` / `eth_blockNumber` / `eth_getBlockByNumber` / `eth_getBalance` / `eth_call` / `eth_gasPrice` / `eth_getTransactionByHash` / `eth_getLogs`) were already empirically verified on Ethereum, Polygon, BSC, Avalanche-C, and Polkadot-EVM. They are **not re-documented here**. This file only covers **L2-specific deltas**: rollup topology, `optimism_*` / `rollup_*` namespaces, L1 batch info, receipt L1-fee fields, and OP Stack reuse value.

---

## Metadata

| Item | Value |
|---|---|
| Chain (EN) | OP Mainnet (formerly Optimism) |
| Chain (ZH) | Optimism(OP Mainnet) |
| ID | 16 |
| Mainnet ChainID | `0xa` = `10` (H8 verified, see §8) |
| Testnet ChainID | `11155420` (OP Sepolia) — ⚠️ not curl-verified |
| Survey date | 2026-05-23 |
| Surveyor | Hermes Agent |
| Status | 🟢 Completed (H8: 10 curls; `optimism_*` / `rollup_*` liveness probe done; OP Stack reuse value rated) |

---

## 1. Sources (authoritative + clients)

| Type | URL | Accessed | Note |
|---|---|---|---|
| Official dev portal | https://docs.optimism.io/ | 2026-05-23 | OP Stack docs root — ⚠️ no DOM verification (cited only) |
| OP Stack specs | https://specs.optimism.io/ | 2026-05-23 | Bedrock + Cannon + Ecotone specs — ⚠️ |
| GitHub (monorepo) | https://github.com/ethereum-optimism/optimism | 2026-05-23 | OP Stack main repo — ⚠️ |
| GitHub (op-geth) | https://github.com/ethereum-optimism/op-geth | 2026-05-23 | go-ethereum fork, L2 execution client |
| GitHub (op-reth) | https://github.com/paradigmxyz/reth/tree/main/crates/optimism | 2026-05-23 | Reth's OP implementation — **H8 confirmed public RPC returns reth/v2.2.0** (§8) |
| Explorer | https://optimistic.etherscan.io/ | 2026-05-23 | OP Mainnet explorer |
| L1 batch poster | https://etherscan.io/address/0x6887246668a3b87F54DeB3b94Ba47a6f63F32985 | 2026-05-23 | OP Batch Inbox on L1 — ⚠️ no DOM verification |
| Public RPC (official) | https://mainnet.optimism.io | 2026-05-23 | **H8: `eth_chainId=0xa`, `web3_clientVersion=reth/v2.2.0-88505c7`** |
| Public RPC (Publicnode) | https://optimism-rpc.publicnode.com | 2026-05-23 | Backup — ⚠️ standalone curl not run (API budget + user-blocked) |
| Public RPC (LlamaRPC) | https://optimism.llamarpc.com | 2026-05-23 | Third fallback — ⚠️ unverified |

---

## 2. L1 ↔ L2 relationship (rollup topology)

| Item | Value |
|---|---|
| Rollup type | **Optimistic Rollup** (fraud-proof, 7-day challenge window) |
| Stack version | **OP Stack post-Bedrock (~2023-06)**, includes Ecotone (EIP-4844 blobs) + Fjord |
| Sequencer | **Single sequencer** (OP Labs operated today), same model as Arbitrum |
| Settlement L1 | **Ethereum Mainnet** (ChainID=1) |
| Batch poster | L1 contract `0x68872...32985` Batch Inbox (compressed L2 tx batches every few minutes) |
| Batch DA | **EIP-4844 blobs after Ecotone** (~128 KiB/blob, 12/block); calldata before Ecotone — ⚠️ blob cutover date 2024-03 |
| State output | L1 `L2OutputOracle` (Bedrock) / `DisputeGameFactory` (Cannon/fault-proof) — ⚠️ not curl-verified |
| Finality model | L2 block ~2s soft / L1 batch finalized ~12 min / **withdrawal executable after 7 days** |

**Key deltas vs Arbitrum**:
- Arbitrum runs the **Nitro** stack (geth fork) + optional AnyTrust DA; Optimism runs **OP Stack** (op-geth + op-node + op-batcher + op-proposer).
- Arbitrum L2 block ~250 ms; **Optimism L2 block ~2 s** (fixed slot).
- Arbitrum L1 batch ~10 min; Optimism L1 batch a few minutes (EIP-4844 blob).
- Namespaces: Arbitrum=`arb_*`; Optimism=`optimism_*` + `rollup_*` (full comparison in §5).

---

## 3. Public endpoints (verified)

| Endpoint | Auth | Rate limit | H8 result |
|---|---|---|---|
| `https://mainnet.optimism.io` | none | public | ✅ `eth_chainId=0xa`, `eth_blockNumber=0x90f10ee` (~152,041,710), `web3_clientVersion=reth/v2.2.0-88505c7/x86_64-unknown-linux-gnu` |
| `https://optimism-rpc.publicnode.com` | none | public | ⚠️ standalone curl not executed (API budget + user-blocked); assumed available based on cross-chain pattern |
| `https://optimism.llamarpc.com` | none | public | ⚠️ unverified |

**Surprising finding**: the official public RPC now serves **op-reth** (not op-geth!). Reth's OP rollout is fast. Impact:
- Node resource profile differs from op-geth (reth uses MDBX rather than LevelDB/Pebble).
- Private namespaces (`debug_*`, `admin_*`) may behave differently on reth — ⚠️ unverified.

---

## 4. ChainID + Finality + Gas deltas (vs Ethereum)

| Dimension | Ethereum (L1) | Optimism | Delta meaning |
|---|---|---|---|
| ChainID | 1 | **10** | DSL only needs `chain_id: 10` |
| Block time | ~12 s | **~2 s** | Fixed 2s slot; mock-mode block-advance must be ×6 |
| Finality | Gasper ~12.8 min (justified) / ~25 min (finalized) | **L2 soft ~2 s / L1-confirmed ~12 min / withdrawal ~7 d** | Benchmarks typically use "L2 soft" |
| Gas model | EIP-1559 base + tip | **EIP-1559 base + tip + L1 data fee** (in receipt) | See §5 receipt fields |
| Pre-EIP-1559 | n/a | n/a | OP is EIP-1559 from day 1 |
| Block size | gas limit 30M | gas limit 40M observed (`0x2625a00`) | ⚠️ OP currently 30-50M, dynamic |
| Adapter reuse | baseline | **Yes — reuse EthereumAdapter**, only chain_id + endpoint | 0 new code |

---

## 5. L2-only methods (`optimism_*` / `rollup_*`) + vs Arbitrum `arb_*`

### 5.1 H8 liveness probe (6 OP-specific methods)

| Method | Namespace | Source | Result on `mainnet.optimism.io` |
|---|---|---|---|
| `rollup_gasPrices` | rollup | op-node | ❌ `{"code":-32601,"message":"rpc method is not whitelisted"}` |
| `optimism_outputAtBlock` | optimism | op-node | ❌ not whitelisted |
| `optimism_syncStatus` | optimism | op-node | ❌ not whitelisted |
| `optimism_rollupConfig` | optimism | op-node | ❌ not whitelisted |
| `optimism_version` | optimism | op-node | ❌ not whitelisted |
| `rollup_getInfo` | rollup | (legacy name, leftover in some docs) | ❌ not whitelisted |

**Conclusion**: **6/6 OP-specific methods are uniformly blocked on the official public RPC** (JSON-RPC `-32601` + custom message `"rpc method is not whitelisted"`), confirming an explicit allowlist proxy/gateway. Using `optimism_*` requires **self-hosted op-node** or a **paid provider** (Alchemy / QuickNode / Infura).

### 5.2 vs Arbitrum `arb_*`

| Dimension | Arbitrum (`arb_*`) | Optimism (`optimism_*` + `rollup_*`) |
|---|---|---|
| Namespace count | 1 (`arb_*`) | **2** (`optimism_*` for op-node API, `rollup_*` for op-node rollup API) |
| Typical methods | `arb_getBlock`, `arb_estimateComponents`, `arb_findBatchContainingBlock` | `optimism_syncStatus`, `optimism_outputAtBlock`, `optimism_rollupConfig`, `rollup_gasPrices` |
| Receipt extensions | `l1Fee`, `l1FeeScalar`, `gasUsedForL1` | **`l1Fee`, `l1GasUsed`, `l1GasPrice`, `l1FeeScalar`** (+ `l1BaseFeeScalar`, `l1BlobBaseFee`, `l1BlobBaseFeeScalar` post-Ecotone) — ⚠️ standalone receipt curl not run (budget); cited from OP Specs |
| Block extensions | `l1BlockNumber`, `l1Timestamp` | No direct L1 fields on block; L1 batch info via `optimism_outputAtBlock` |
| Public RPC exposure | ⚠️ (covered in Arbitrum survey) | **❌ all blocked by allowlist** (verified here) |
| Naming style | medium | medium — both vendors isolate L2 specifics in a dedicated namespace, **not polluting `eth_*`** |

**Benchmark implication**:
- L2-specific methods, even though documented, are **essentially unavailable on production public endpoints**. Mock mode should **default to the 8-method EVM suite** and treat L2-specific methods as **opt-in** (probed only when a private RPC is supplied).
- This conclusion matches Arbitrum → factor out a shared "L2 private-namespace liveness probe" subroutine.

### 5.3 Receipt L1-fee fields (`eth_getTransactionReceipt` extensions on OP)

⚠️ Standalone curl not executed (API budget). Below is from OP Specs (https://specs.optimism.io/protocol/exec-engine.html#l1-cost-fees-l1-fee-l1-fee-scalar) + op-geth source:

```jsonc
// Standard EVM fields (already verified on Ethereum) + Optimism extras:
{
  "l1Fee": "0x...",                  // L1 data fee (wei)
  "l1GasUsed": "0x...",              // L1-gas estimate to post this tx
  "l1GasPrice": "0x...",             // L1 gasPrice snapshot
  "l1FeeScalar": "0.684",            // pre-Ecotone scalar (deprecated)
  // Post-Ecotone (2024-03):
  "l1BaseFeeScalar": "0x...",
  "l1BlobBaseFee": "0x...",
  "l1BlobBaseFeeScalar": "0x..."
}
```

**Benchmark impact**: tolerate unknown fields when parsing receipts (JSON forward-compat). Throughput benchmarks **don't need to differentiate**, but L1-cost attribution would. → Mark as future enhancement, **not in Wave5 DSL**.

---

## 6. Real workload (USDC/USDT/DEX)

| Token / Contract | Address | Note |
|---|---|---|
| USDC (native, Circle 2023+) | `0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85` | Mainstream USDC (replaced legacy USDC.e bridged) |
| USDC.e (bridged legacy) | `0x7F5c764cBc14f9669B88837ca1490cCa17c31607` | ⚠️ unverified, doc cited |
| USDT (bridged) | `0x94b008aA00579c1307B0EF2c499aD98a8ce58e58` | ⚠️ unverified |
| WETH | `0x4200000000000000000000000000000000000006` | OP "predeployed" address (the `0x4200...` block is OP system-contract namespace) |
| Mainstream DEXes | Velodrome / Uniswap v3 / Curve | Velodrome = OP-native ve(3,3) DEX |
| Real EOA | `0xC0fFee254729296a45a3885639AC7E10F9d54979` (Vitalik) | Same address cross-chain (EOA); reused in benchmark |

**Workload strategy**: identical to Ethereum baseline — `eth_call` (ERC20 `balanceOf`), `eth_getLogs` (Transfer event), `eth_getBalance`. **Zero extra methods.**

---

## 7. DSL decision (prediction + verification)

**Prediction**: 0 new DSL fields.
**Verified**: **0 new fields confirmed**, only:

```yaml
chain:
  id: optimism
  chain_id: 10
  family: evm
  adapter: EthereumAdapter        # reused, no new adapter
  endpoints:
    - url: https://mainnet.optimism.io
      priority: 1
    - url: https://optimism-rpc.publicnode.com
      priority: 2
  l2:                              # optional, declarative-only, no new code paths
    type: optimistic
    stack: op-stack
    l1_chain_id: 1
    l2_block_time_sec: 2
  optional_methods:                # opt-in liveness probes; only enabled if endpoint supports them
    - optimism_syncStatus
    - optimism_outputAtBlock
    - rollup_gasPrices
```

**ASKs (for upstream P1-2 review)**:

1. **Include the `l2:` subtree in the DSL?** Purely *declarative*, no adapter change. **Recommend**: include, all fields optional; preserves the interface for future OP Superchain (Base / Mantle / Worldchain) **reuse**.
2. **Semantics of `optional_methods:`** — "skip silently if unsupported" or "warn"? **Recommend**: Wave5 default = "skip + INFO log"; introduce strict mode in Wave6.
3. **OP Stack reuse assertion**: Base (ChainID=8453) / Mantle (5000) / Worldchain (480) all fork OP Stack and in theory **reuse this survey's conclusions** (EVM 8-method core + same `optimism_*` / `rollup_*` namespaces + same receipt L1-fee fields), only swapping chain_id + endpoint. **ASK**: should Wave6 collapse them into a single OP-superchain page? **Recommend**: yes, but each chain still needs a 5-curl H8 micro-survey (chain_id + blockNumber + 1 × `optimism_*` probe + receipt L1-field spot-check + USDC sanity).
4. **op-reth vs op-geth**: the official public RPC has switched to reth. Should Wave6 add a "client family" dimension? **Recommend**: metadata field only, no adapter impact.

---

## 8. H8 evidence (10 curls, 2026-05-23, endpoint=`https://mainnet.optimism.io`)

| # | Method | Params | Result (truncated) | Note |
|---|---|---|---|---|
| 1 | `eth_chainId` | `[]` | `{"result":"0xa"}` | ✅ 10 ✓ |
| 2 | `web3_clientVersion` | `[]` | `{"result":"reth/v2.2.0-88505c7/x86_64-unknown-linux-gnu"}` | ✅ **op-reth** (not op-geth) |
| 3 | `eth_blockNumber` | `[]` | `{"result":"0x90f10ee"}` | ✅ 152,041,710 |
| 4 | `rollup_gasPrices` | `[]` | `error -32601: "rpc method is not whitelisted"` | ❌ allowlisted out |
| 5 | `optimism_outputAtBlock` | `["0x1"]` | `error -32601: "rpc method is not whitelisted"` | ❌ |
| 6 | `optimism_syncStatus` | `[]` | `error -32601: "rpc method is not whitelisted"` | ❌ |
| 7 | `optimism_rollupConfig` | `[]` | `error -32601: "rpc method is not whitelisted"` | ❌ |
| 8 | `optimism_version` | `[]` | `error -32601: "rpc method is not whitelisted"` | ❌ |
| 9 | `rollup_getInfo` | `[]` | `error -32601: "rpc method is not whitelisted"` | ❌ |
| 10 | `eth_getBlockByNumber` | `["latest", false]` | block hash `0x0f2d88b8…6487`, `gasLimit=0x2625a00` (40M), `gasUsed=0xa017a9` (~10.5M), `baseFeePerGas=0x185` (389 wei!), `blobGasUsed=0x295ea0` (=2.7M, **proves OP runs EIP-4844 blob mode**), `difficulty=0x0` (PoS-style) | ✅ multiple L2-relevant signals |

**Key observations**:
- `baseFeePerGas=0x185=389 wei` — OP L2 base fee is **~6 orders of magnitude lower** than Ethereum L1, confirming the L2 cost model.
- `blobGasUsed=0x295ea0=2,711,200` — **even the L2 block consumes blob gas** (post-Ecotone OP block structure is EIP-4844-compatible).
- 0/6 OP-specific methods reachable → operational rule: **only probe OP-specific methods when the user explicitly passes `--enable-l2-methods` AND the endpoint accepts them**; the default 8-method EVM suite is enough.

---

## 9. OP Stack reuse value (decision input for Wave6)

| Chain | ChainID | Diff vs Optimism | Reuses this survey? |
|---|---|---|---|
| Base | 8453 | Coinbase L2, pure OP Stack | ✅ ~95% reuse, swap endpoint + chain_id |
| Mantle | 5000 | Custom DA (EigenDA instead of ETH blob) + MNT gas token | ⚠️ ~70% reuse; extra survey for DA + gas token |
| Worldchain | 480 | Standard OP Stack fork + Worldcoin priority blockspace | ✅ ~90% reuse |
| Zora | 7777777 | Standard OP Stack fork | ✅ ~95% reuse |
| Mode | 34443 | Standard OP Stack fork + sequencer fee sharing | ✅ ~90% reuse |

**Conclusion**: this survey + the Arbitrum survey form a "dual benchmark for Optimistic Rollup L2s". For Wave6 OP-superchain entries, each chain needs only a **5-curl H8 micro-survey** (chain_id / blockNumber / 1 × `optimism_*` probe / receipt spot-check / USDC sanity), **saving ~80% of the survey effort**.
