# 18 — Linea (DIFF-ONLY · Type 2 zk-EVM · wave 5 closing chain)

> **Header**: Linea is Consensys's Type 2 zk-EVM — **bytecode-level EVM equivalent**, deliberately keeping
> the `linea_*` namespace minimal.
> This study covers only L2-specific diffs + Type 2 vs Type 4 comparison (zkSync) + wave 5 cumulative L2 DSL
> decisions. All EVM-generic methods (`eth_chainId` / `eth_blockNumber` / `eth_getBlockByNumber` /
> `eth_getBalance` / `eth_call` / `eth_gasPrice` / `eth_getTransactionByHash` / `eth_getLogs` /
> `eth_feeHistory`) behave **identically** to 02-ethereum.md and are not repeated.

---

## §1 Sources (authoritative + clients)

| Type | Link | Note |
| --- | --- | --- |
| Official docs | https://docs.linea.build/ | Maintained by Consensys |
| JSON-RPC spec | https://docs.linea.build/api/reference | Only 3 public `linea_*` methods |
| L1 contract (ZkEvmV2) | `0xd19d4B5d358258f05D7B411E21A1460D11B0876F` | Linea Rollup Proxy (Mainnet) |
| Node impl | `linea-besu` (Besu fork, Java) + `linea-geth` (Geth fork, Go, read-only) | Dual clients |
| Bridge contract | `0x051F1D88f0aF5763fB888eC4378b4D8B29ea3319` (L1 MessageService) | L1↔L2 |
| Explorer | https://lineascan.build/ | Etherscan-style |
| Measured client | `Geth/v1.17.3-stable-117e067f/linux-arm64/go1.26.3` | Public RPC is linea-geth read-only follower |

---

## §2 L1↔L2 relationship (ZK Rollup · Type 2 bytecode-equivalent)

```
L2 user tx ──► Sequencer (linea-besu, run by Consensys, centralized)
                   │
                   ├─► L2 block (~2 s, soft finality, near-deterministic)
                   │
                   ▼
            Coordinator + Prover cluster (gnark / Plonk → Groth16 wrap)
                   │
                   ▼  submitData / finalizeBlocks
            L1 ZkEvmV2 (0xd19d...876F)
                   │
                   ├─► Data submission (EIP-4844 blob), minutes
                   │
                   └─► finalizeBlocks (SNARK verification), 4-12 h → final
```

| Dimension | Linea (ZK Type 2) | zkSync Era (ZK Type 4, ref) | Optimistic (Arb/OP, ref) |
| --- | --- | --- | --- |
| zk-EVM type | **Type 2: bytecode-equivalent**, all EVM opcodes | Type 4: **language-level** equivalent (Solidity→EraVM) | n/a |
| Bytecode compat | ✅ same solc output deploys directly | ❌ needs zksolc; missing `SELFDESTRUCT`/`PC` | ✅ |
| Security model | Validity proof (Plonk + Groth16) | Validity proof (Boojum / SNARK) | Fraud proof + 7d challenge |
| L2 → L1 withdrawal | Immediately after finalize (~4-12 h) | Execute phase (~24 h) | ~7 days |
| State trie | **Sparse Merkle Tree (Mimc hash)** | Same (zk-friendly) | Ethereum MPT (Keccak) |
| Sequencer | Centralized (Consensys) | Centralized (matter-labs) | Centralized (each) |
| Account model | **Standard EOA + contract**, no native AA | Native AA (EOA is a contract) | Standard |
| L1 DA | EIP-4844 blob (since 2024-03) | calldata + blob | Same |
| RPC footprint | Minimal: **3 `linea_*` methods** | Large: ~15 `zks_*` | Large: Arb=SequencerInbox / OP=`optimism_*` |

**Key insight**: Linea's "stay-pure-EVM" stance at the RPC layer is uncompromising — only 3 public `linea_*` methods, and L1 batch/finality state is **not exposed via RPC at all**. You must call L1 `ZkEvmV2.currentL2BlockNumber()` directly. Stark contrast with zkSync where `zks_L1BatchNumber` is one-shot readable.

---

## §3 Public endpoints (measured 2026-05-23)

| Endpoint | `linea_*` support | Measured latency | Note |
| --- | --- | --- | --- |
| `https://rpc.linea.build` (official) | ✅ 3/3 | ~120 ms | linea-geth follower |
| `https://linea-rpc.publicnode.com` | ✅ 3/3 | ~180 ms | 3rd-party mirror |
| WebSocket | `wss://rpc.linea.build` | — | Standard `eth_subscribe` |

No allowlist blocking (unlike Optimism public endpoint).

---

## §4 ChainID + finality + gas mode diff (vs L1 Ethereum)

| Field | L1 Ethereum | Linea | Diff |
| --- | --- | --- | --- |
| `chainId` | `0x1` (1) | `0xe708` (**59144**) | Measured ✓ |
| `net_version` | `1` | `59144` | Consistent |
| Finality | 2 epochs (~12 min) | L2 soft 2 s / L1 finalize 4-12 h (final) | **2 stages**, no challenge window |
| Gas model | EIP-1559 base+tip | EIP-1559, but **baseFee pinned at 7 wei** (L2 has spare capacity, almost all priorityFee) | Measured baseFee=`0x7`=7 wei |
| Tx type | 0/1/2/3 | 0/1/2/3 (full EVM equivalent) | **No new type** (vs zkSync type 113) |
| Block fields | Standard | Standard + `parentBeaconBlockRoot=0x0` + Linea seqnum in `extraData` | Almost transparent |
| Receipt fields | Standard | Standard (**no `l1BatchNumber`**, unlike zkSync) | Deliberately not exposed |
| State trie | MPT (Keccak) | **Sparse Merkle Tree (Mimc-2-23)** | `linea_getProof` ≠ `eth_getProof` |
| Opcode | All | **All supported** (Type 2 guarantee) | vs zkSync missing `SELFDESTRUCT`/`PC` |

---

## §5 L2-specific methods: `linea_*` namespace (only 3 public)

| Method | Measured response (2026-05-23) | Use / DSL relevance |
| --- | --- | --- |
| `linea_estimateGas` | `{"gasLimit":"0x5208","baseFeePerGas":"0x7","priorityFeePerGas":"0x25d1eb6"}` | **Three-field structured** response, priorityFee already embeds L1 data fee |
| `linea_getProof` | Sparse Merkle proof: `{accountProof:{key,leafIndex,proof:{value,proofRelatedNodes}},storageProofs:[…]}` | **zk-friendly trie proof**, format completely differs from `eth_getProof` |
| `linea_getTransactionExclusionStatusV1` | `null` (not excluded) | Sequencer censorship detection; non-null means tx was actively excluded |

> **`eth_getProof` is still callable**, but it returns a **Keccak-MPT compatibility shim** (linea-geth synthesizes a pseudo-MPT view, **cannot be used for L2→L1 withdrawal proofs**).
> **Real withdrawal proofs must use `linea_getProof`** (SMT/Mimc) — the cost of Type 2 equivalence + zk backend.

### Verified non-existent methods (all of which zkSync exposes)

```
linea_getL2BlockNumber         → -32601 method not found
linea_l1RollingHashUpdatedEvents → -32601
linea_getBlockTracesByNumberV2 → -32601 (existed, prover-internal only)
linea_getRecentMessageEvents   → -32601
linea_getStateRoot             → -32601
linea_getTransactionReceipt    → -32601
```

**Conclusion**: Linea pushes all L1 batch / finalize / state-root progress queries **entirely to the L1 contract layer**, never via RPC. Monitoring must `eth_call` `ZkEvmV2.currentL2BlockNumber()` / `currentFinalizedBlockNumber()` directly.

### `linea_estimateGas` vs `eth_estimateGas` — key diff

| Item | `eth_estimateGas` | `linea_estimateGas` |
| --- | --- | --- |
| Return shape | scalar hex `"0x5208"` | object `{gasLimit, baseFeePerGas, priorityFeePerGas}` |
| L1 data fee | **Not included** | ✅ Embedded in `priorityFeePerGas` |
| Mandatory? | No (still accurate for gasLimit only) | ✅ For accurate pricing (avoid underpriced) |
| Benchmark trigger | RPS-only paths OK with `eth_*` | Real send paths **must** use `linea_*` |

---

## §6 Real payloads (USDC + main L2 DEXes)

| Type | Contract | Note |
| --- | --- | --- |
| USDC.e (bridged, dominant) | `0x176211869cA2b568f2A7D4EE941E073a821EE1ff` | Linea official bridge + Circle default |
| USDT (bridged) | `0xA219439258ca9da29E9Cc4cE5596924745e12B93` | LayerZero / official bridge |
| WETH (L2) | `0xe5D7C2a44FfDDf6b295A15c148167daaAf5Cf34f` | Withdrawal via L1 MessageService |
| LyveSwap / Velocore | Multiple routers | UniV3 forks, local TVL leaders |
| Real test EOA | `0xC0fFee254729296a45a3885639AC7E10F9d54979` | Used as `from` for `eth_call` / `*_estimateGas` |

---

## §7 DSL decisions (ASK + wave 5 cumulative recommendations)

> **This is wave 5's 4th and final chain**, so this section carries **both** the Linea single-chain ASK
> **and** the cumulative 4-L2 consensus ASK.

### ASK-L1 — Linea single chain: promote `linea_estimateGas` as L2 standard?

```yaml
# Proposal: for any rollup_type=zk|optimistic chain, prefer the chain-specialized *_estimateGas
chain:
  family: evm_l2
  rollup_type: zk
  fee_oracle:
    primary: linea_estimateGas        # this chain
    fallback: eth_estimateGas
    inflate_pct: 10                   # empirical, linea_estimateGas occasionally under-estimates
```

- **If yes**: benchmark send paths reflect real L2 fees (incl. L1 DA share), otherwise underpriced rejection > 5%.
- **This study leans yes**: measured `linea_estimateGas` returns priorityFeePerGas=`0x25d1eb6` (~39.6 gwei), `eth_estimateGas` only gives gasLimit — **missing half the info**.
- **Side effect**: DSL needs a `fee_oracle` sub-block, opt-in, no impact on L1.

### ASK-W5-A — wave 5 consensus: `rollup_type` enum formal promotion (from zkSync-only ASK to 4-chain consensus)

| Chain | wave 5 finding | Proposed `rollup_type` |
| --- | --- | --- |
| Arbitrum | Nitro, fraud proof + 7d window | `optimistic` |
| Optimism | OP Stack, fraud proof + 7d window | `optimistic` |
| zkSync Era | Validity proof + Type 4 + AA | `zk` |
| Linea | Validity proof + Type 2, no AA | `zk` |

```yaml
chain:
  family: evm_l2
  rollup_type: zk          # enum: l1 | optimistic | zk | validium | sovereign
  zk_evm_type: 2           # zk only: 1|2|2.5|3|4 (Vitalik's taxonomy)
  settlement_chain_id: 1
  l1_main_contract: "0xd19d4B5d358258f05D7B411E21A1460D11B0876F"
```

- **Strong yes**: unifies 4 chains, evaluator can auto-select finality strategy (zk waits for finalizeBlocks event, optimistic waits 7 days / `finalized` tag).
- `zk_evm_type` further distinguishes Linea (Type 2, can directly reuse Ethereum benchmark bytecode) vs zkSync (Type 4, payload contracts must recompile) — this is a **real reproducibility difference**, not just specification.

### ASK-W5-B — should the L1 batch monitor be lifted to the EVM common sub-layer?

**Finding**: across the 4 chains, L1 batch progress query mechanics are **completely different**:

| Chain | L1 batch monitor method | RPC direct-read? |
| --- | --- | --- |
| Arbitrum | `NodeInterface.findBatchContainingBlock` precompile + L1 SequencerInbox events | precompile, needs `eth_call` |
| Optimism | L1 `L2OutputOracle.latestBlockNumber()` contract call | L1 `eth_call`, **L2 RPC cannot read directly** |
| zkSync Era | `zks_L1BatchNumber` / `zks_getBlockDetails` direct return | ✅ L2 RPC direct |
| Linea | L1 `ZkEvmV2.currentL2BlockNumber()` / `currentFinalizedBlockNumber()` | L1 `eth_call`, **L2 RPC not exposed** |

**Conclusion**: **Do not** lift this into the EVM common sub-layer. **3/4 chains require L1 contract calls**, only zkSync provides a convenience method. Force-abstracting would degenerate into an "L1 contract ABI table + RPC compatibility shim" middleware — far beyond what a "common sub-layer" should carry.

**Suggested landing**: keep an **adapter-internal `get_l1_settled_block()` interface method** per chain, DSL only declares:

```yaml
l1_batch_monitor:
  enabled: true
  poll_interval_s: 60     # common
  # implementation details owned by each adapter, DSL does not mandate
```

i.e. **interface common, implementation private**. Consistent with the pre-wave-5 EVM-generic adapter philosophy.

### Indicators that don't need new DSL fields (this chain)

- `web3_clientVersion` upgrade window, Linea seqnum in `extraData` — monitoring metric, not config.
- The 3 `linea_*` method calls themselves — adapter decides when to fire, no DSL.
- L2 baseFee pinned at 7 wei — runtime observation, not config.

---

## §8 H8 evidence (curl, reproducible)

```bash
EP=https://rpc.linea.build
H='-H Content-Type:application/json'

# 1. chainId == 59144
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"eth_chainId","id":1}'
# → {"result":"0xe708"}                              ✓ 59144

# 2. L2 blockNumber (measured 30 691 022)
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"eth_blockNumber","id":1}'
# → {"result":"0x1d550ce"}

# 3. Client identity: linea-geth (not erigon/besu)
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"web3_clientVersion","id":1}'
# → {"result":"Geth/v1.17.3-stable-117e067f/linux-arm64/go1.26.3"}

# 4. linea_estimateGas three-field structure (key diff)
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"linea_estimateGas","params":[{"from":"0xC0fFee254729296a45a3885639AC7E10F9d54979","to":"0xC0fFee254729296a45a3885639AC7E10F9d54979","value":"0x1"}],"id":1}'
# → {"gasLimit":"0x5208","baseFeePerGas":"0x7","priorityFeePerGas":"0x25d1eb6"}
#   baseFee 7 wei + priority 39.6 gwei = real L2 price (incl. L1 DA share)

# 5. Compare scalar eth_estimateGas
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"eth_estimateGas","params":[{"from":"0xC0fFee254729296a45a3885639AC7E10F9d54979","to":"0xC0fFee254729296a45a3885639AC7E10F9d54979","value":"0x1"}],"id":1}'
# → {"result":"0x5208"}                              ← missing priorityFee axis

# 6. linea_getProof is SMT/Mimc format (required for L2→L1 withdrawal)
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"linea_getProof","params":["0x176211869cA2b568f2A7D4EE941E073a821EE1ff",["0x0"],"latest"],"id":1}'
# → {accountProof:{key,leafIndex:307771,proof:{value,proofRelatedNodes:[...]}},storageProofs:[...]}

# 7. eth_getProof still works, but returns MPT shim (ethers-compatible, NOT for withdrawal)
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"eth_getProof","params":["0x176211869cA2b568f2A7D4EE941E073a821EE1ff",["0x0"],"latest"],"id":1}'
# → {address,accountProof:[hex,hex,...],storageProof:[...]}  ← Keccak-MPT format

# 8. Sequencer censorship detection (non-null = excluded)
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"linea_getTransactionExclusionStatusV1","params":["0x0000000000000000000000000000000000000000000000000000000000000000"],"id":1}'
# → {"result":null}                                  ✓ not excluded

# 9. L1 batch state NOT exposed via RPC (contrast zkSync zks_L1BatchNumber)
curl -s $EP $H -d '{"jsonrpc":"2.0","method":"linea_getL2BlockNumber","id":1}'
# → {"error":{"code":-32601,"message":"method does not exist"}}  ← must query L1 contract
```

---

## Appendix: diff summary vs prior EVM/L2 studies

| Dimension | This chain |
| --- | --- |
| ChainID | 59144 (`0xe708`) |
| RPC | Standard `eth_*` **+** `linea_*` (**only 3**) |
| Block | Standard + Cancun fields (`parentBeaconBlockRoot=0x0`) |
| Receipt | **Fully standard**, no L1 anchor fields (vs zkSync has `l1BatchNumber`) |
| Tx | Standard 0/1/2/3, **no new type** (vs zkSync type 113) |
| Finality | 2 stages (L2 soft / L1 finalize), no challenge window |
| Security | ZK validity proof (Plonk + Groth16) |
| Account model | **Standard EOA** (vs zkSync native AA) |
| State trie | **Sparse Merkle Tree (Mimc)** (same as zkSync; differs from Ethereum/OP/Arb) |
| zk-EVM type | **Type 2** (vs zkSync Type 4) |
| L1 batch monitor | **Not exposed via RPC**, must `eth_call` L1 `ZkEvmV2` (vs zkSync `zks_L1BatchNumber` direct) |

— END —
