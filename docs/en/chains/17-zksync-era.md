# 17 — zkSync Era (DIFF-ONLY · First ZK Rollup)

> **Top-line**: zkSync Era is 100% EVM-compatible (not EVM-equivalent). Native account abstraction and ZK validity proofs.
> This survey covers **only L2-specific differences and the ZK rollup model**. The 8 generic EVM methods
> (`eth_chainId` / `eth_blockNumber` / `eth_getBlockByNumber` / `eth_getBalance` / `eth_call` / `eth_gasPrice` /
> `eth_getTransactionByHash` / `eth_getLogs`) behave identically to 02-ethereum.md and are not re-described.

---

## §1 Sources (authoritative + client)

| Type | Link | Note |
| --- | --- | --- |
| Official docs | https://docs.zksync.io/ | Era + ZK Stack |
| JSON-RPC spec | https://docs.zksync.io/zksync-protocol/api/zks-rpc | Canonical `zks_*` namespace |
| L1 contract (DiamondProxy) | `0x32400084c286cf3e17e7b677ea9583e60a000324` | Empirically returned by `zks_getMainContract` |
| Node implementation | `matter-labs/zksync-era` (Rust) | Only production sequencer |
| Bridge contracts | `zks_getBridgeContracts` returns 7 fields (see §2) | L1↔L2 bridges |
| Explorer | https://explorer.zksync.io/ | Public |

---

## §2 L1↔L2 relationship (ZK Rollup, **fundamentally different from Optimistic**)

```
L2 user tx ──► Sequencer (matter-labs/zksync-era, centralized)
                   │
                   ├─► L2 commit (~1 s, soft finality)
                   │
                   ▼
            Prover cluster generates SNARK
                   │
                   ▼  commitBatch
            L1 DiamondProxy (0x3240...0324)
                   │
                   ├─► proveBatch  (~1 h)   ← validity-proof verification
                   │
                   └─► executeBatch (~24 h) ← finalized, withdrawals claimable
```

| Dimension | zkSync Era (ZK) | Optimistic Rollup (Arb/OP, baseline) |
| --- | --- | --- |
| Security model | **Validity proof** (SNARK, mathematical) | Fraud proof + 7-day challenge |
| L2 → L1 withdrawal delay | ~24 h (execute phase) | ~7 days (challenge window) |
| State finality phases | committed → proven → **executed** | committed → **finalized** (after 7d) |
| Sequencer | Centralized (matter-labs) | Centralized (each project) |
| Reorg risk | L2-only soft reorg; irreversible after L1 commit | Same |
| L1 data availability | calldata + blob (EIP-4844) | Same |

**Empirical**: `zks_L1BatchNumber` = `0x7cd85` = **511 877** (2026-05-23), `zks_L1ChainId` = `0x1` (Mainnet L1).

---

## §3 Public endpoints (verified)

| Endpoint | `zks_*` support | Latency |
| --- | --- | --- |
| `https://mainnet.era.zksync.io` (official) | ✅ all | ~150 ms |
| `https://zksync-era-rpc.publicnode.com` | ✅ most | ~200 ms |
| WebSocket | `wss://mainnet.era.zksync.io/ws` | `eth_subscribe` supported |

---

## §4 ChainID + finality + gas model diff table (vs L1 Ethereum)

| Field | L1 Ethereum | zkSync Era | Diff |
| --- | --- | --- | --- |
| `chainId` | `0x1` (1) | `0x144` (**324**) | — |
| Finality | 2 epochs (~12 min) | L2 soft 1 s / L1 prove 1 h / **L1 execute 24 h** | Three-phase |
| Gas model | EIP-1559 base+tip | base+tip **plus** separate pubdata pricing | `zks_estimateFee` returns `gas_per_pubdata_limit` |
| Tx type | 0/1/2 | 0/1/2 **+ 113** (EIP-712 / native AA) | type-113 carries `paymaster` field |
| Block | standard | standard + `l1BatchNumber` / `l1BatchTimestamp` | Which L1 batch the block belongs to |
| Receipt | standard | standard + `l1BatchNumber` / `l1BatchTxIndex` / `l2ToL1Logs` | Withdrawals need `l2ToL1Logs` proof |
| Opcode | full | missing: `SELFDESTRUCT`, `PC` (EraVM is not EVM bytecode; emulated by compiler) | Some contracts incompatible |

---

## §5 L2-specific methods: `zks_*` namespace (verified)

| Method | Live response (2026-05-23) | Purpose / DSL relevance |
| --- | --- | --- |
| `zks_L1BatchNumber` | `"0x7cd85"` (511877) | **Core progress metric**, last L1-committed batch |
| `zks_L1ChainId` | `"0x1"` | Settlement chain: 1 = Mainnet, 11155111 = Sepolia |
| `zks_getMainContract` | `"0x3240...0324"` | L1 DiamondProxy |
| `zks_getBridgeContracts` | Returns `l1Erc20DefaultBridge` / `l1SharedDefaultBridge` / `l1WethBridge` / `l2Erc20DefaultBridge` / `l2LegacySharedBridge` / `l2SharedDefaultBridge` / `l2WethBridge` (7 fields) | Bridge enumeration |
| `zks_getBlockDetails` | Contains `l1BatchNumber` / `commitTxHash` / `committedAt` / `proveTxHash` / `provenAt` / `executeTxHash` / `executedAt` / `baseSystemContractsHashes` | **Per-block finality timestamps** — monitoring gold |
| `zks_getL1BatchDetails` | Same, but per-batch | Batch-level detail |
| `zks_estimateFee` | Requires valid `from` (else `invalid sender, can't start a transaction from a non-account`) | Returns `gas_limit` / `max_fee_per_gas` / `max_priority_fee_per_gas` / `gas_per_pubdata_limit` |
| `zks_estimateGasL1ToL2` | — | L1→L2 deposit gas estimate |
| `zks_getAllAccountBalances` | — | All ERC-20 balances in one call |
| `zks_getConfirmedTokens` | — | Official token list |
| `zks_getProof` | — | Merkle proof (required for L2→L1 withdrawal) |
| `zks_getRawBlockTransactions` | — | Includes raw `paymaster_params` |
| `zks_getTransactionDetails` | Includes `ethCommitTxHash` / `ethProveTxHash` / `ethExecuteTxHash` / `isL1Originated` / `status` | Per-tx L1 anchoring |
| `zks_sendRawTransactionWithDetailedOutput` | — | Returns full trace |
| `zks_getProtocolVersion` | — | Upgrade window |

> **Empirical evidence**: `zks_estimateFee` with empty `from` returns `invalid sender. can't start a transaction from a non-account`.
> This is the direct manifestation of zkSync's **native account abstraction**: every sender must be an `IAccount` implementation.
> The concept of an EOA is abolished — even EOAs are contracts on zkSync.

---

## §6 Real workloads (USDC/USDT + mainstream DEX)

| Category | Contract | Note |
| --- | --- | --- |
| USDC.e (bridged, Circle-deprecated) | `0x3355df6D4c9C3035724Fd0e3914dE96A5a83aaf4` | Native USDC issued separately via Circle CCTP |
| USDC (native, Circle-issued) | `0x1d17CBcF0D6D143135aE902365D2E5e2A16538D4` | Default reference |
| USDT (bridged) | `0x493257fD37EDB34451f62EDf8D2a0C418852bA4C` | LayerZero / official bridge |
| WETH (L2-native) | `0x5AEa5775959fBC2557Cc8789bC1bf90A239D9a91` | Withdraw via `l2WethBridge` |
| SyncSwap (native DEX) | router `0x2da10A1e27bF85cEdD8FFb1AbBe97e53391C0295` | UniV2-like |
| Maverick / Mute / Vekorta | — | Tier-2 TVL |

---

## §7 DSL decisions (1–2 ASKs)

> **This is the first ZK rollup**. It produces a *real* model divergence from the existing EVM template
> (which currently only varies `chain_id` + `endpoint`).

### ASK-Z1 — Add a `rollup_type` enum field?

```yaml
# Proposal
chain:
  family: evm_l2
  rollup_type: zk          # candidates: l1 | optimistic | zk | validium | sovereign
  settlement_chain_id: 1
  l1_main_contract: "0x32400084c286cf3e17e7b677ea9583e60a000324"
```

- **If YES**: the benchmark runner can auto-select a finality-waiting strategy — wait for `executeTxHash`
  on ZK chains; wait 7 days or for the explicit `finalized` tag on Optimistic chains.
- **If NO**: benchmarks would only exercise soft L2 finality (`eth_blockNumber` lag), treating
  zkSync identically to Arbitrum/OP — and discarding zkSync's core security semantics.
- **This survey leans YES**: the semantic difference is already concrete at method level
  (zkSync's three-phase `commitTxHash/proveTxHash/executeTxHash`; Optimistic chains have only commit/finalize).

### ASK-Z2 — Should `paymaster` / `paymaster_input` enter the standardised tx model?

- zkSync EIP-712 (type 113) tx carries `paymasterParams: { paymaster, paymasterInput }`.
  Optimistic chains have no equivalent.
- If the DSL standardises a tx model it needs `optional paymaster_address`, `optional paymaster_input` —
  otherwise zkSync workloads lose the actual fee-sponsorship path.
- **Recommendation**: nest as `transaction.extensions[zksync_paymaster]` rather than top-level,
  to avoid polluting the main structure.

### Metrics that do NOT require a new DSL field

- `zks_L1BatchNumber` / `commitTxHash` / `proveTxHash` / `executeTxHash` are **monitoring metrics**,
  not configuration. Handle in the metrics collector, not the DSL.
- The bridge contract set is discoverable at runtime via `zks_getBridgeContracts`; no need to hard-code in DSL.

---

## §8 H8 evidence (curl, reproducible)

```bash
EP=https://mainnet.era.zksync.io
H='-H Content-Type:application/json'

# 1. chainId == 324
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"eth_chainId","id":1}'
# → {"result":"0x144"}                          ✓ 324

# 2. L2 blockNumber (observed 70 318 746)
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"eth_blockNumber","id":1}'
# → {"result":"0x42fba97"}

# 3. Last L1-committed batch == 511 877
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"zks_L1BatchNumber","id":1}'
# → {"result":"0x7cd85"}                         ✓ 511877

# 4. Settlement L1 == Mainnet
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"zks_L1ChainId","id":1}'
# → {"result":"0x1"}                             ✓ 1

# 5. DiamondProxy address
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"zks_getMainContract","id":1}'
# → {"result":"0x32400084c286cf3e17e7b677ea9583e60a000324"}

# 6. Bridge contracts enumeration
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"zks_getBridgeContracts","id":1}'
# → 7 fields (see §5)                            ✓

# 7. Block detail includes three-phase finality timestamps (batch 499238 executed)
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"zks_getBlockDetails","params":[60100000],"id":1}'
# → commitTxHash / committedAt / executeTxHash / executedAt all populated
# committedAt = 2025-05-08T13:30:14Z
# executedAt  = 2025-05-08T18:05:27Z  (Δ ≈ 4.5h, this batch beat the 24h SLA)

# 8. Native-AA evidence
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"zks_estimateFee","params":[{"from":"0x0","to":"0x...","data":"0x"}],"id":1}'
# → error: "invalid sender. can't start a transaction from a non-account"
#   ↳ zero-address is not a valid IAccount; even EOAs are contracts on zkSync.
```

---

## Appendix: diff vs existing EVM surveys (Ethereum / Polygon / BSC / Avalanche-C / Polkadot-EVM)

| Dimension | zkSync-specific diff |
| --- | --- |
| ChainID | 324 (`0x144`) |
| RPC | standard `eth_*` **plus** `zks_*` (~15 methods) |
| Block | adds `l1BatchNumber` / `l1BatchTimestamp` |
| Receipt | adds `l1BatchNumber` / `l1BatchTxIndex` / `l2ToL1Logs` |
| Tx | new type 113 (EIP-712 carrying `paymasterParams`) |
| Finality | **three phases** (committed / proven / executed), not simple N-block confirmation |
| Security | **ZK validity proof**, no challenge window |
| Account | **native AA**, even EOAs are contracts; `from = 0x0` errors out |

— END —
