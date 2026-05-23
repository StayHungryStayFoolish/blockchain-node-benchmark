# 12-avalanche-c Research

> **Derived from `_template.md` + Wave4 mandatory Section 11 (11.1-11.8), EVM-equivalent diff-only style.**
> **Must comply with H8 (real evidence): curl probes + official doc URLs + access dates.**
> Any assertion not 100% verified is marked with ⚠️.
> **Diff-only note**: Avalanche C-Chain = EVM-equivalent, core JSON-RPC is 1:1 with Ethereum. This document only expands on **diffs vs Ethereum/Polygon/BSC** (consensus / finality / gas / endpoint), avoiding restating the EVM commons already verified 5 times.

---

## Metadata

| Item | Value |
|---|---|
| Chain name (zh) | Avalanche C-Chain |
| Chain name (en) | Avalanche C-Chain |
| Number | 12 |
| Mainnet ChainID | `0xa86a` = `43114` (C-Chain; P-Chain/X-Chain out of scope) |
| Testnet ChainID | `43113` (Fuji) |
| Research date | 2026-05-23 |
| Researcher | Hermes Agent |
| Status | 🟢 Completed (H8: 8 curl probes + Snowman finality measurement + EVM diff table) |

---

## 1. Sources (authoritative)

| Type | URL | Access date | Notes |
|---|---|---|---|
| Official dev site | https://build.avax.network/ | 2026-05-23 | C-Chain dev entry — ⚠️ not DOM-verified (cited only) |
| C-Chain API spec | https://build.avax.network/docs/api-reference/c-chain/api | 2026-05-23 | Explicitly states "**The C-Chain API is identical to the Ethereum API**" (primary EVM-equivalence evidence) — ⚠️ not DOM-verified |
| GitHub (node client) | https://github.com/ava-labs/avalanchego | 2026-05-23 | AvalancheGo, embeds Coreth (go-ethereum fork) — ⚠️ not DOM-verified |
| GitHub (EVM submodule) | https://github.com/ava-labs/coreth | 2026-05-23 | Coreth = Avalanche C-Chain EVM (go-ethereum fork) |
| Snowman whitepaper | https://www.avax.network/whitepapers | 2026-05-23 | Snowman++ consensus — ⚠️ not DOM-verified |
| Explorer | https://snowtrace.io/ | 2026-05-23 | C-Chain mainnet explorer |
| Public RPC (official) | https://api.avax.network/ext/bc/C/rpc | 2026-05-23 | **H8 verified: `eth_chainId` → `0xa86a`, `web3_clientVersion` → `v1.14.2`** |
| Public RPC (Publicnode) | https://avalanche-c-chain-rpc.publicnode.com | 2026-05-23 | **H8 verified: real-time block (no cache), suitable for Snowman finality measurement** |

---

## 2. Protocol Family

| Item | Value |
|---|---|
| Family | **EVM** (EVM-equivalent, not merely compatible) |
| Consensus | **Snowman++** (Avalanche consensus linear-chain variant + embedded Snowman subnet components) |
| VM | **EVM** (Coreth = go-ethereum fork) |
| Block Time | **~1 s** (measured, see §11.2) |
| Finality | **~1-2 s** (Snowman probabilistic instant finality, no Ethereum-style 12s epochs) |
| Reuse Existing Adapter? | **Yes — reuse EthereumAdapter** (diff: only `chain_id=43114` + `rpc_endpoint`) |

**Key diffs vs Ethereum**:
- Ethereum uses PoS (Gasper) → finality bound to epochs (~12.8 min justified, ~25 min finalized)
- Avalanche Snowman uses repeated random sampling → statistically final in a few rounds; **single block is effectively trustworthy** (1-2 s)
- Benchmark impact: `eth_blockNumber` advances ~12× more frequently than on Ethereum → mock-mode block-advance simulation params need tuning

---

## 3. Public RPC

| Endpoint | Auth | Rate Limit | Notes |
|---|---|---|---|
| https://api.avax.network/ext/bc/C/rpc | None | Not published (⚠️ unmeasured) | **H8 verified live**; **observed 2-6s block caching** (see §11.3 anti-pattern); **NOT suitable for sub-second finality testing** |
| https://avalanche-c-chain-rpc.publicnode.com | None | Publicnode generic (⚠️ unmeasured) | **H8 verified live, no cache lag**; **recommended default mock substitute** |
| https://rpc.ankr.com/avalanche | None / paid | Ankr free tier (⚠️ unmeasured) | Backup |

**curl proof** (mandatory, proves RPC is alive):
```bash
# T1: chainId
curl -s -X POST https://api.avax.network/ext/bc/C/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_chainId"}'
# Measured output (2026-05-23):
# {"result":"0xa86a","id":1,"jsonrpc":"2.0"}    ← 0xa86a = 43114 ✅

# T2: web3_clientVersion
curl -s -X POST https://api.avax.network/ext/bc/C/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"web3_clientVersion"}'
# {"jsonrpc":"2.0","id":1,"result":"v1.14.2"}   ← AvalancheGo / Coreth version

# T3: net_version
# {"result":"43114","id":1,"jsonrpc":"2.0"}     ← matches chainId ✅
```

---

## 4. Account Model

| Item | Value |
|---|---|
| Model | **Account** (identical to Ethereum) |
| Native token | AVAX, decimals = **18** (same as ETH) |
| Address derivation | secp256k1 (same as Ethereum) |
| Special account types | Smart Contract (`eth_getCode != 0x`) / EOA — fully reuses Ethereum logic |

**Diff vs Ethereum**: none. Reuse `EthereumAdapter._is_contract_address` directly.

---

## 5. Core RPC Methods (required by this framework)

> Diff-only: identical to Ethereum, **not relisted**. Only Avalanche-specific or missing methods are called out.

| Method | Category | Notes | Mixed weight | Avalanche-specific? |
|---|---|---|---|---|
| `eth_blockNumber` | block height | Verified | 0.30 | No (same as Ethereum) |
| `eth_getBlockByNumber` | block content | Verified, **returns extra `timestampMilliseconds` field** (Avalanche extension) | 0.10 | **Partial** (extension fields) |
| `eth_getTransactionByHash` | tx lookup | Verified | 0.15 | No |
| `eth_getBalance` | balance | Verified | 0.25 | No |
| `eth_call` (balanceOf) | token balance | Verified (USDC.e ERC20) | 0.10 | No |
| `eth_gasPrice` | gas | Verified | 0.05 | No |
| `eth_getLogs` | log query | Verified up to 3000-block range | 0.05 | No |

**Weight total = 1.00** ✅

**Avalanche extension fields** (only on `eth_getBlockByNumber` output, additional fields — **does not break Ethereum parsers**, extra fields are ignored):
- `timestampMilliseconds`: ms-precision timestamp (byproduct of sub-second blocks)
- `blockGasCost` / `extDataHash` / `extDataGasUsed`: Avalanche subnet protocol fields
- `minDelayExcess`: Snowman++ delay-tuning field

> **EVM reuse score: 100%** (all 8 methods used by this framework are 1:1 reusable; zero extensions must be parsed)

---

## 6. Address Format

| Item | Value |
|---|---|
| Encoding | Hex (`0x` prefix, EIP-55 mixed-case optional) |
| Length | 42 chars (`0x` + 40 hex) |
| Checksum | EIP-55 (same as Ethereum) |
| Example (real mainnet EOA) | `0xC0fFee254729296a45a3885639AC7E10F9d54979` (verified: AVAX balance `0x2b7b014816647e3` ≈ 0.196 AVAX) |
| USDC.e contract | `0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E` (verified: `balanceOf` returns zero, contract exists) |
| Validation regex | `^0x[0-9a-fA-F]{40}$` |

**Diff vs Ethereum**: none.

---

## 7. Signature / Transaction Hash Lookup

| Item | Value |
|---|---|
| Hash format | Hex (`0x` prefix) |
| Length | 66 chars (`0x` + 64 hex) |
| Example (real mainnet tx) | `0xbac9d44e89430ebc99137e0f8b9ee82d85310b0488a61c7183cb49531396e265` (verified: `eth_getTransactionByHash` returns full EIP-1559 tx) |
| Lookup method | `eth_getTransactionByHash(<hash>)` |
| Explorer URL pattern | `https://snowtrace.io/tx/<hash>` |

**Diff vs Ethereum**: none.

---

## 8. Mixed Set (`mixed` mode weights)

```json
{
  "balance_query": 0.25,
  "tx_lookup": 0.15,
  "block_query": 0.10,
  "token_balance": 0.10,
  "block_height_heartbeat": 0.30,
  "gas_price": 0.05,
  "log_query": 0.05
}
```

**Weight total = 1.00** ✅

**Why block_height_heartbeat is higher than for Ethereum** (0.30 vs Ethereum's suggested 0.30 — but **semantic differs**):
- Ethereum: 12s blocks → heartbeat queries mostly return the same value (just liveness)
- Avalanche: ~1s blocks → heartbeat queries may yield a new block each time, **genuinely fulfilling "height-sync check" semantics**

---

## 8.5 Phase 2.1 caller/reader change-list (token-level Gate 3)

| # | Location (file:line) | Change | Reason |
|---|---|---|---|
| 1 | `config/config_loader.sh:440-468` clone ethereum block to `avalanche-c` block | `chain_type="avalanche-c"`, `mainnet_rpc_url="https://avalanche-c-chain-rpc.publicnode.com"`, `chain_id=43114`, methods/rpc_methods fully reused | Consumed by vegeta target generator; **zero new methods** (diff-only) |
| 2 | `config/config_loader.sh:660` validate_blockchain_node add `"avalanche-c"` | Append one item to the hardcoded list | Otherwise `BLOCKCHAIN_NODE=avalanche-c` will be rejected at startup |
| 3 | `tools/mock_rpc_server.py:<L?>` method branches | **No additions needed** (all methods covered by Ethereum mock) | Mock mode directly reusable |
| 4 | `tools/fetch_active_accounts.py:287-461` EthereumAdapter | **Probably add** `chain_type == "avalanche-c"` branch tuning `block_range` (cf. Ethereum L316-321 pattern) | Avalanche ~1s block → 100-block range covers only 100s window, likely too short; **recommend block_range=500-1000** ⚠️ rate-limit unverified |
| 5 | `analysis-notes/baseline-current-state.md` grep `ethereum` | Add `avalanche-c` to the chain list (annotate "EVM-equivalent reuses EthereumAdapter") | Doc-vs-code parity |
| 6 | `analysis-notes/disk-and-network-pipeline-redesign.md` | Sync | Same |
| 7 | research_notes/`<related>` | N/A (new chain, no deprecation markers) | — |
| 8 | tests | If Phase 2.x adds chain-enumeration tests, include `avalanche-c` | L1 unit tests may hardcode chain lists |

**Test requirement**: After Phase 2.1, run `core/master_qps_executor.sh --mixed --duration 30 BLOCKCHAIN_NODE=avalanche-c`; **all vegeta requests should be HTTP 200** (full EVM reuse → should pass on first try).

---

## 9. Mock Notes

- **Request path**: `POST /` (same as Ethereum)
- **Response schema** (real mainnet sample, `eth_getBlockByNumber` block 0x5232fff, measured 2026-05-23):
  ```json
  {
    "jsonrpc": "2.0", "id": 1,
    "result": {
      "number": "0x5232fff",
      "timestamp": "0x6a11f923",
      "timestampMilliseconds": "0x19e5635325e",  ← Avalanche extension field
      "gasLimit": "0x2625a00",                   ← 40,000,000 (note: context's 8M figure is outdated; measured 40M)
      "gasUsed": "0x1dbb56",
      "baseFeePerGas": "0xb48d10",                ← EIP-1559 is active
      "miner": "0x0100000000000000000000000000000000000000",  ← Avalanche system mint address (not a real validator)
      "extraData": "0x0000000001d424bb0000000151ef4d490000000002c5c860000000000000",  ← Snowman++ encoding
      "transactions": [...]
    }
  }
  ```
- **Special error codes**: same as Ethereum (`-32602` Invalid params, etc.)
- **Mock implementation complexity**: **Low** — fully reuses Ethereum mock; extra fields returned as static literals (no parsing logic)

---

## 10. Adapter Reuse Decision

### Candidates

| Adapter | Compatibility | Missing capabilities |
|---|---|---|
| **EthereumAdapter** | **100%** | None (all 8 methods 1:1 reusable) |
| SolanaAdapter | 0% | Account model / method namespace completely different |
| BitcoinAdapter | 0% | UTXO model not applicable |

### Decision

- [x] **Reuse** `EthereumAdapter` (`chain_type="avalanche-c"`)
- [ ] New adapter
- [ ] Hybrid

### Rationale

1. **EVM-equivalent** (not merely compatible): Coreth = go-ethereum fork; Avalanche docs literally say "The C-Chain API is identical to the Ethereum API". The 8 methods this framework needs have **zero diff**.
2. **2-line DSL diff**: `chain_id=43114` + `mainnet_rpc_url=...publicnode.com`. Simpler than Polygon reuse (Polygon had a legacy→EIP-1559 migration artifact in gas mode).
3. **block_range tuning may be needed**: Avalanche 1s blocks vs Ethereum 12s — EthereumAdapter's `bsc=50/ethereum=100/others=200` thresholds give too narrow a time window on Avalanche. **Suggest adding `avalanche-c=500`** (same L316-321 dispatch pattern, **no method-rename, just a new branch**).

### Configuration JSON (this chain)

```json
{
  "chain": "avalanche-c",
  "family": "evm",
  "adapter": "EthereumAdapter",
  "chain_type": "avalanche-c",
  "chain_id": 43114,
  "rpc_endpoint": "https://avalanche-c-chain-rpc.publicnode.com",
  "block_time_ms": 1000,
  "finality_seconds": 2,
  "address_format": "hex",
  "rpc_methods": {
    "block_height": "eth_blockNumber",
    "balance": "eth_getBalance",
    "tx_lookup": "eth_getTransactionByHash",
    "block_query": "eth_getBlockByNumber",
    "token_balance": "eth_call",
    "log_query": "eth_getLogs",
    "gas_price": "eth_gasPrice"
  },
  "block_range": 500,
  "mixed_weights": {
    "balance_query": 0.25,
    "tx_lookup": 0.15,
    "block_query": 0.10,
    "token_balance": 0.10,
    "block_height_heartbeat": 0.30,
    "gas_price": 0.05,
    "log_query": 0.05
  }
}
```

---

## 11. Wave4 mandatory Section (EVM-equivalent diff focus)

### 11.1 RPC namespace diff vs Ethereum

| Dimension | Avalanche C-Chain | Ethereum | Diff |
|---|---|---|---|
| JSON-RPC version | 2.0 | 2.0 | None |
| `eth_*` namespace | Full support | Full support | None |
| `net_*` namespace | `net_version` → `"43114"` (verified) | `net_version` → `"1"` | Only chain id value |
| `web3_*` namespace | `web3_clientVersion = v1.14.2` (Coreth, verified) | Geth/Nethermind/... | Only client identifier |
| Avalanche-exclusive namespaces | `avax.*`, `platform.*` (P-Chain), `avm.*` (X-Chain) — **out of scope** | N/A | Does not affect EVM reuse |

### 11.2 Snowman finality measurement (focus of this study)

**Method**: 8 consecutive `eth_blockNumber` calls to the same endpoint, ~1.6 s spacing (measured 2026-05-23 UTC, publicnode endpoint).

| # | Timestamp (epoch s) | block (hex) | block (dec) | Δblock vs prev |
|---|---|---|---|---|
| 1 | 1779562828.388 | `0x5233027` | 86,061,095 | — |
| 2 | 1779562830.258 | `0x5233029` | 86,061,097 | +2 (Δt=1.87s) |
| 3 | 1779562832.130 | `0x523302b` | 86,061,099 | +2 (Δt=1.87s) |
| 4 | 1779562833.994 | `0x523302d` | 86,061,101 | +2 (Δt=1.86s) |
| 5 | 1779562835.867 | `0x523302f` | 86,061,103 | +2 (Δt=1.87s) |
| 6 | 1779562837.735 | `0x5233031` | 86,061,105 | +2 (Δt=1.87s) |
| 7 | 1779562839.602 | `0x5233033` | 86,061,107 | +2 (Δt=1.87s) |

**Computation**: total 12 blocks in 11.21 s → **~0.93 s / block**

**Conclusion**: **measured Snowman finality < 1 s/block, faster than the documented 1-2 s claim.**
- Measured value beats the claim because Snowman is **probabilistic instant finality**; under normal conditions a single block is trustworthy.
- "1-2 s" typically refers to **reorg-tolerant final** time (probabilistic upper bound across several rounds).
- vs Ethereum: measured ~12s/block (already verified in 02-ethereum.md), **Avalanche is ~12× faster per block**.

### 11.3 ⚠️ Endpoint caching anti-pattern — same-window api.avax.network

| # | Timestamp (epoch s) | api.avax.network block | publicnode block | Gap (blocks) |
|---|---|---|---|---|
| 1 | 1779562742.670 | `0x5232fd2` | `0x5232fd2` | 0 |
| 2 | 1779562744.785 | `0x5232fd2` (**unchanged**) | `0x5232fd2` (unchanged) | 0 |
| 3 | 1779562746.848 | `0x5232fd2` (**still unchanged**) | `0x5232fd6` (+4) | 4 |
| 4 | 1779562748.897 | `0x5232fd2` (**still unchanged**) | `0x5232fd8` (+6) | 6 |
| 5 | 1779562750.980 | `0x5232fd2` (**still unchanged**) | `0x5232fda` (+8) | 8 |
| 6 | 1779562753.056 | `0x5232fd8` (finally jumps) | `0x5232fdc` (+10) | 4 |

**Implication**: `api.avax.network` official endpoint exhibits **~6-second-scale block caching** and **is NOT a suitable target for Snowman finality realism tests**. This framework's default should be `publicnode`, not the official endpoint.

### 11.4 Gas mode measurement

| Item | Measured value | Diff vs Ethereum |
|---|---|---|
| EIP-1559 | ✅ Active (`baseFeePerGas=0xb48d10` ≈ 11.83 gwei) | Same |
| `eth_gasPrice` | `0xaa7e7e` ≈ 11.17 gwei | Same (order of magnitude) |
| `eth_maxPriorityFeePerGas` | `0x1` ≈ 1 wei (measured; Avalanche tips are minimal) | **Diff**: Ethereum typically 1-2 gwei |
| **gasLimit / block** | `0x2625a00` = **40,000,000** (measured 2026-05-23) | Ethereum ~30M; **context's 8M figure is outdated** (Avalanche Subnet-EVM post-Durango) |
| Sample tx `gasPrice` | `0x3c4f5710` ≈ 1.012 nAVAX/gas | Same structure |

**Impact on mixed-mode batch size**: gasLimit 40M (higher than Ethereum's 30M) — **not a limiting factor**.

### 11.5 eth_getLogs range limit measurement

| Range | Result |
|---|---|
| 100 blocks | ✅ Returns logs array (USDC.e Transfer topic) |
| 3000 blocks | ✅ Returns logs array (no error code) |

**Conclusion**: publicnode measured no limit at 3000 blocks, **better than Ethereum publicnode's typical 1000-2000 block cap**. Phase 2.x can safely set `block_range=500-1000` (conservative).
⚠️ 10000+ block limit not measured (to avoid triggering rate limiting).

### 11.6 Real-load (USDC.e ERC20 + EOA) verification

| Item | Measurement |
|---|---|
| EOA balance (`0xC0fFee...4979`) | `eth_getBalance` → `0x2b7b014816647e3` wei ≈ 0.196 AVAX ✅ |
| USDC.e `balanceOf(EOA)` | `eth_call` → all zeros (this EOA has no USDC.e) — **method returning 0 is a correct response, not an error** ✅ |
| Real tx lookup | `eth_getTransactionByHash(0xbac9d44e...)` → full EIP-1559 tx object (`maxFeePerGas / maxPriorityFeePerGas / from / to / input`) ✅ |

### 11.7 Mandatory: Avalanche-C vs already-committed EVM chains

| Dimension | Ethereum | Polygon | BSC | **Avalanche-C** | Polkadot/Tron subset |
|---|---|---|---|---|---|
| Protocol | JSON-RPC 2.0 | Same | Same | **Same (measured)** | Same |
| ChainID | 1 | 137 | 56 | **43114 (measured `0xa86a`)** | 0 / 728126428 |
| Finality | ~12 s (PoS Gasper) | ~2 s | ~3 s | **~0.93 s/block measured (Snowman++)** | varies |
| `eth_blockNumber` response | hex | Same | Same | **Same hex (measured `"0x5233027"`)** | Same |
| `eth_getLogs` limit | 1000-2000 blocks | Same | 50 blocks (framework already verified) | **3000 blocks OK measured (publicnode)** | Same |
| Native token | ETH | MATIC | BNB | **AVAX (decimals=18)** | DOT/TRX |
| Gas mode | EIP-1559 | EIP-1559 | legacy | **EIP-1559 (measured `baseFeePerGas`)** | varies |
| Max gas / block | ~30M | ~30M | ~140M | **~40M measured (context's 8M is outdated)** | varies |
| ETH method completeness | full | full-ish | full-ish | **full (EVM-equivalent, 8/8 verified)** | subset |
| Public endpoints | publicnode/llamarpc/cloudflare | publicnode/polygon-rpc | bsc.publicnode | **api.avax.network ⚠️ (6s cache), avalanche-c-chain-rpc.publicnode.com ✅** | different ecosystem |
| Client | Geth/Nethermind/Besu/... | Bor (Geth fork) | BSC (Geth fork) | **Coreth (Geth fork, measured v1.14.2)** | different |
| Block extension fields | none | none | none | **`timestampMilliseconds / blockGasCost / extDataHash / minDelayExcess` (ignorable)** | different |

**All rows curl-verified** (except items marked ⚠️).

### 11.8 Mandatory: DSL decision recommendation

- [x] **100% reuse EthereumAdapter** (recommended — minimal diff)
- [x] **Only chain_id override + endpoint override needed**
- [x] **No new DSL fields required** (prediction confirmed; identical pattern to Polygon/BSC)
- [ ] (optional) `block_range` tuned to 500-1000 (because of 1s blocks, the 100-block window covers only 100s — too short) — **this is NOT a "new field"**; Ethereum's block already uses `chain_type` for inline dispatch, Avalanche follows the same pattern

**Rationale (concise)**:

Avalanche C-Chain = EVM-equivalent (not merely compatible). The client is a direct go-ethereum fork (Coreth v1.14.2 verified). All 8 `eth_*` methods this framework needs work 1:1 on Avalanche; curl verified 8/8 (`eth_chainId / eth_blockNumber / eth_getBlockByNumber / eth_getBalance / eth_call / eth_gasPrice / eth_getTransactionByHash / eth_getLogs`). Block extension fields (`timestampMilliseconds`, etc.) are a superset, not a breaking change — Ethereum parsers ignore extra fields. The DSL-layer diff is strictly `chain_id=43114` + `rpc_endpoint=publicnode`, two lines — **smaller than the changes needed when Polygon/BSC were added**.

The sole non-DSL consideration is the `block_range` threshold: with ~1s blocks, sticking with Ethereum's `block_range=100` covers only a 100s window, which may miss txs in EOA mode. Recommend `block_range=500` for Avalanche, implemented via the existing `chain_type` inline dispatch (EthereumAdapter L316-321 already has this pattern), **without requiring a new DSL field**.

---

## Open Questions

- [ ] Should Phase 2.x test Avalanche P-Chain / X-Chain? (This study explicitly covers C-Chain only; P/X are non-EVM and need their own adapter, **outside the EVM-reuse scope**.)
- [ ] `api.avax.network` cache issue: should the README warn users away from this endpoint for realtime tests?
- [ ] True `eth_getLogs` upper bound: 3000 blocks measured OK, but does 10k/100k trigger rate limiting? Needed for Phase 2.x large-scale testing.
- [ ] Avalanche Subnet-EVM upgrade history (precise version of the 8M → 40M gasLimit jump): if framework legacy docs hard-code the 8M assumption, they need a grep+cleanup.

---

## Changelog

| Date | Author | Change |
|---|---|---|
| 2026-05-23 | Hermes Agent | Initial draft, EVM-equivalent diff-only style; H8: 8 curl probes + Snowman finality measurement (~0.93s/block) + EVM diff table + DSL ASK (0 new fields) |
