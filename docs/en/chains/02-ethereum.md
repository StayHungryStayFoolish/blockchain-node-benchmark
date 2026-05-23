# 02 — Ethereum Research Note

> **Version**: v1.0 (draft, Phase 1.1a)
> **Research date**: 2026-05-23
> **Author**: Hermes Agent (token-level + research-first + E1-verified)
> **Status**: 🟢 Awaiting user review (P1-USER-REVIEW gate)

---

## §1 Basic Info

| Field | Value | Source (E1) |
|---|---|---|
| Chain family | EVM (Ethereum Virtual Machine) | Official https://ethereum.org/developers/docs/apis/json-rpc/ (E1 accessed 2026-05-23) |
| Consensus | PoS (post-2022 Merge) | Official docs |
| Client implementations | Geth / Nethermind / Besu / Erigon / Reth | Official client list |
| Mainnet RPC URL | `https://ethereum-rpc.publicnode.com` (no API key public node) | User preference; framework `config_loader.sh:375-377` (TBD grep verify) |
| Framework support | ✅ (`fetch_active_accounts.py:287-461` EthereumAdapter) | E1 read_file confirmed |
| Sole representative of family? | ❌ (BSC/Base/Polygon/Scroll/Arbitrum etc. share EVM compatibility) | Framework already confirmed BSC/Base/Polygon/Scroll all use the same EthereumAdapter |

---

## §2 Address Format / Parsing Rules

| Field | Value | E1 Source |
|---|---|---|
| Address length | 20 bytes (40 hex chars + `0x` prefix = 42 chars) | EIP-55 |
| Character set | `0x` + `[0-9a-fA-F]{40}` | Standard |
| Checksum | EIP-55 mixed-case checksum (optional, most clients accept lowercase) | EIP-55 |
| Framework system_addresses | `0x0000000000000000000000000000000000000000`, `0x000000000000000000000000000000000000dead` | `config_loader.sh:455-458` (E1 read_file confirmed) |
| Framework target_address (USDT contract) | `0xdAC17F958D2ee523a2206206994597C13D831ec7` | `config_loader.sh:446` |
| Contract vs EOA detection | `eth_getCode(addr, "latest") != "0x"` → contract, else EOA | EthereumAdapter `_is_contract_address` L300-307 |

**Difference vs Solana**: Solana addresses are base58-encoded 32 bytes (~44 chars), Ethereum is hex-encoded 20 bytes (42 chars) — half the length.

---

## §3 RPC Method Current Status (each E1-verified)

### Methods actually called by framework EthereumAdapter

| Method | Purpose | Framework call site (E1) | Official spec status (E1) |
|---|---|---|---|
| `eth_getCode` | Contract address detection | `fetch_active_accounts.py:304` | ✅ Active (execution-apis spec) |
| `eth_blockNumber` | Get latest block | `fetch_active_accounts.py:312, 346` + `config_loader.sh:461 mixed` | ✅ Active |
| `eth_getLogs` | Contract log fetching | `fetch_active_accounts.py:332` + `config_loader.sh:452 methods.get_logs` | ✅ Active |
| `eth_getBlockByNumber` | EOA tx fetching (block-by-block scan) | `fetch_active_accounts.py:378` | ✅ Active |
| `eth_getTransactionByHash` | Tx details | `fetch_active_accounts.py:404` + `config_loader.sh:453 methods.get_transaction` | ✅ Active |
| `eth_getBalance` | Balance query (mixed mode) | `config_loader.sh:460-461` `single` + `mixed` | ✅ Active |
| `eth_getTransactionCount` | Nonce/tx count (mixed mode) | `config_loader.sh:461` `mixed` | ✅ Active |
| `eth_gasPrice` | Gas price (mixed mode) | `config_loader.sh:461` `mixed` | ✅ Active |

**All 8 methods exist in the current method list of Ethereum Execution APIs spec (https://ethereum.github.io/execution-apis/)** (E1: browser_console DOM extracted 61 method names, containing all 8).

### Key differences vs Solana

| Dimension | Solana | Ethereum |
|---|---|---|
| Mixed mode method count | 5 | **4** (one fewer) |
| Deprecated method residue | ❌ `getRecentBlockhash` deprecated but uncleaned (P0 bug) | ✅ **No deprecated method residue** |
| API spec authoritative source | https://solana.com/docs/rpc | https://ethereum.github.io/execution-apis/ |
| RPC protocol version | JSON-RPC 2.0 (custom method namespace) | JSON-RPC 2.0 (`eth_` + `net_` + `web3_` namespaces) |

**Conclusion**: Ethereum has no deprecation issues, **completely opposite to Solana**.

---

## §4 System Addresses (should be filtered)

| Address | Meaning | E1 Source |
|---|---|---|
| `0x0000000000000000000000000000000000000000` | Zero address (mint/burn convention from field) | `config_loader.sh:456` |
| `0x000000000000000000000000000000000000dead` | Dead address (burn convention) | `config_loader.sh:457` |

**Problem**: Framework lists only 2 system addresses, **but Ethereum ecosystem has many more convention filtering addresses to consider**:
- USDT/USDC/WETH contract addresses themselves (extremely high tx frequency, may skew active accounts stats)
- Beacon Deposit Contract (`0x00000000219ab540356cBB839Cbe05303d7705Fa`)
- WETH (`0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2`)

**Open Question (pending user review)**: Should framework build in a larger whitelist? Discuss when designing plugin in Phase 2.x.

---

## §5 Mixed Mode Weights (if enabled)

**Framework current implementation**: No mixed weights — `mixed` field is comma-separated string, looped equal-weight by target_generator:

```
config_loader.sh:461 → "eth_getBalance,eth_getTransactionCount,eth_blockNumber,eth_gasPrice"
                                    ↓ split by ','
CURRENT_RPC_METHODS_ARRAY = [eth_getBalance, eth_getTransactionCount, eth_blockNumber, eth_gasPrice]
                                    ↓ target_generator.sh:184/300-306 equal-weight loop
vegeta targets file
```

**Suggestion (Phase 2.x plugin design stage)**: Introduce weighted mixed schema in sync with Solana, Ethereum estimated real production workload:
- `eth_getBalance`: 0.30 (balance query highest frequency)
- `eth_getTransactionCount`: 0.20 (nonce query)
- `eth_blockNumber`: 0.30 (high-frequency heartbeat)
- `eth_gasPrice`: 0.10 (pre-transaction query)
- `eth_call`: 0.10 (contract read-only, **framework currently not configured, should add**)

Total = 1.00 ✅

**Note**: Weight numbers are draft suggestions (E5 SPECULATED), not based on real mainnet traffic stats, need Phase 2.x alignment with exchanges.

---

## §6 Framework Ethereum Call Chain (E1-verified)

```
[Startup] BLOCKCHAIN_NODE=ethereum
   ↓
[config_loader.sh:660] validate_blockchain_node → pass (ethereum in supported list)
   ↓
[config_loader.sh:381-383] case ethereum → MAINNET_RPC_URL=https://mainnet.publicnode.com (or similar)
   ↓
[config_loader.sh:440-468] UNIFIED_BLOCKCHAIN_CONFIG.blockchains.ethereum
   - methods.get_logs = "eth_getLogs"
   - methods.get_transaction = "eth_getTransactionByHash"
   - rpc_methods.single = "eth_getBalance"
   - rpc_methods.mixed = "eth_getBalance,eth_getTransactionCount,eth_blockNumber,eth_gasPrice"
   ↓
[fetch_active_accounts.py:287-461] EthereumAdapter
   - _single_request → _is_contract_address(eth_getCode)
                      → Contract: _fetch_contract_logs_fixed(eth_blockNumber, eth_getLogs)
                      → EOA:      _fetch_eoa_transactions_simple(eth_blockNumber, eth_getBlockByNumber block-by-block scan)
   - fetch_transaction → eth_getTransactionByHash
   - extract_accounts_from_transaction → extract addresses from tx.from / tx.to
   ↓
[target_generator.sh:184/300-306] read CURRENT_RPC_METHODS_ARRAY loop
   ↓
[vegeta targets file] → vegeta actually sends to mainnet node
```

**Comparison with Solana call chain**:
- Solana uses unified `getSignaturesForAddress` + `getTransaction`, no contract/EOA distinction
- Ethereum **must distinguish contract/EOA**, contracts use `eth_getLogs`, EOAs use block-by-block `eth_getBlockByNumber` (high performance overhead)
- EthereumAdapter has extra `_fetch_block_transactions` helper, **the densest RPC call point in EOA mode**

---

## §7 Chain-Specific Tuning (already implemented in framework)

`fetch_active_accounts.py:316-321` adjusts block_range by `chain_type`:

| chain_type | block_range | Reason |
|---|---|---|
| `bsc` | 50 | BSC node has stricter limits (smaller single eth_getLogs range cap) |
| `ethereum` | 100 | Moderate |
| Others (base/polygon/scroll) | 200 | More lenient |

**Open Question**: Are these thresholds actually tested? Picked by experience or measured against mainnet RPC rate limits? (No E1 evidence → E5 SPECULATED)

---

## §8 Phase 2.1 Implementation Changes / Caller-Reader Impact List

**Research-first mandatory rule — this section must exist (ref token-level-careful-edit Case-K)**

| # | Change | Content | Caller/Reader Impact |
|---|---|---|---|
| 1 | `config/config_loader.sh:440-468` Ethereum block extracted to `config/chains/ethereum.json` | Keep `chain_type / params / methods / system_addresses / rpc_methods / param_formats` schema | `generate_auto_config()` L704+ must change to importlib-like dynamic JSON loading, **cannot hardcode** |
| 2 | `fetch_active_accounts.py:287-461` EthereumAdapter extracted to `adapters/ethereum.py` | Class signature `class EthereumAdapter(BlockchainAdapter)` unchanged | When extracting **method names cannot change** (`_single_request / fetch_transaction / extract_accounts_from_transaction` + private `_is_contract_address / _fetch_contract_logs_fixed / _fetch_eoa_transactions_simple / _fetch_block_transactions`) |
| 3 | `chain_type` field must keep backward compat | EthereumAdapter L316-321 uses `self.chain_type.lower() == "bsc" / "ethereum"` for block_range branch | BSC/Polygon/Base/Scroll 4 chains reuse the same adapter, **chain_type is hot-path critical dispatch key**, renaming breaks 4-chain testing |
| 4 | `config_loader.sh:660` validate_blockchain_node hardcoded list must migrate | `local supported_blockchains=("solana" "ethereum" "bsc" "base" "scroll" "polygon" "starknet" "sui")` | Phase 2.0 design stage decision: plugin self-describing capability (scan `config/chains/*.json` auto-enumerate) vs central manifest |
| 5 | Mixed mode weight schema (if introduced) | Introduce `mixed_weights` JSON field | target_generator.sh:184/300-306 needs new weighted sampling logic (currently equal-weight round-robin) |

**§8.5 Phase 2.1 caller/reader table (token-level Gate 3)**

| Change | Caller (who calls this function/reads this data) | Reader (who consumes this output) | OK after change? |
|---|---|---|---|
| Extract ethereum.json | `generate_auto_config()` `config_loader.sh:704+` | `target_generator.sh:184` reads `CURRENT_RPC_METHODS_ARRAY` | **Must change in sync** (dynamic loading) |
| Extract EthereumAdapter | `fetch_active_accounts.py main` dispatches adapter instantiation | adapter outputs active accounts list to `target_generator.sh` | **Can extract one-to-one** (class signature unchanged) |
| chain_type retention | EthereumAdapter L316-321 `if chain_type == "bsc"` | BSC/Polygon/Base/Scroll 4 chains share | **Cannot rename** |

---

## §9 Real Source Coverage and Timestamps

| Source Type | URL/Path | Access Date (UTC) | Status |
|---|---|---|---|
| Official Spec | https://ethereum.github.io/execution-apis/ | 2026-05-23 | E1 ✅ DOM extracted 61 methods including all 8 |
| Official docs entry | https://ethereum.org/developers/docs/apis/json-rpc/ | 2026-05-23 | E1 ✅ accessed |
| Framework code | `fetch_active_accounts.py:287-461`, `config_loader.sh:440-468` | 2026-05-23 | E1 ✅ read_file verified |
| Real test against publicnode | (pending Phase 2.x implementation curl run) | — | E5 awaiting test |

---

## §10 Interface Contract Placeholder (fill at Phase 2.x completion)

```python
class EthereumAdapter(BlockchainAdapter):
    """Ethereum + EVM-compatible chain adapter (BSC/Base/Polygon/Scroll reuse)"""

    chain_type: str  # "ethereum" / "bsc" / "base" / "polygon" / "scroll" — hot path dispatch key

    async def _single_request(self, address: str, limit: int, verbose: bool) -> list[dict]:
        """Unified entry, contract/EOA branching"""

    async def _is_contract_address(self, address: str) -> bool:
        """eth_getCode(addr, latest) != '0x'"""

    async def _fetch_contract_logs_fixed(self, address: str, limit: int, verbose: bool) -> list[dict]:
        """eth_blockNumber + eth_getLogs (adjusts block_range by chain_type)"""

    async def _fetch_eoa_transactions_simple(self, address: str, limit: int, verbose: bool) -> list[dict]:
        """eth_blockNumber + block-by-block eth_getBlockByNumber scan"""

    async def _fetch_block_transactions(self, block_num: int, target_address: str, remaining_limit: int) -> list[dict]:
        """Single block tx scan, matching from/to == target"""

    async def fetch_transaction(self, tx_hash: str) -> dict | None:
        """eth_getTransactionByHash"""

    def extract_accounts_from_transaction(self, tx_data: dict, target_address: str) -> set[str]:
        """Extract addresses from tx.from / tx.to (Solana uses accountKeys)"""
```

**Note**: Line range L287-461 is current baseline (`b2c0ccc`) actual position, after Phase 2.1 extraction this placeholder should update to `adapters/ethereum.py:1-N`.

---

## §11 Open Questions (pending user review)

1. **Mixed weights**: Should Phase 2.x introduce weighted mixed? (Same question as Solana)
2. **system_addresses expansion**: Should Ethereum build in WETH/USDT/USDC/Beacon Deposit and other high-frequency contract whitelist?
3. **block_range threshold**: Are `bsc=50 / ethereum=100 / others=200` empirically verified? Should Phase 2.x do mainnet RPC rate limit testing?
4. **chain_type retention**: When Phase 2.x plugin self-describes, is `chain_type` field still necessary? Or change to plugin metadata's `family: "evm"` + `subfamily: "ethereum"`?
5. **EOA block-by-block scan cost**: `_fetch_eoa_transactions_simple` at large limits triggers hundreds of `eth_getBlockByNumber` calls, **does real mainnet run get rate-limited by publicnode?** Does framework need concurrent throttle?

---

## §12 Changelog

| Date (UTC) | Author | Change |
|---|---|---|
| 2026-05-23 | Hermes Agent | Initial draft, based on token-level + research-first + E1 verification (Ethereum Execution APIs spec + framework code) |
