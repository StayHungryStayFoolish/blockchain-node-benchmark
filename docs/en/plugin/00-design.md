# Chain-as-Plugin Framework Design (v1.4.7)

**Status**: DRAFT, awaiting user review before implementation
**Date**: 2026-05-23
**Author**: Hermes Agent (decision gate: `decision-with-tradeoffs` + R1-PRIME empirical baseline)
**Prerequisites**: R1-PRIME audit committed (`bc6a3ae`, `8402291`), 8-chain method-level empirical verification complete

---

## 0. Goals and Boundaries

### 0.1 Design Goals (Acceptance Criteria)

| Goal | Acceptance |
|---|---|
| G1. Business adds a new chain by **JSON only** (≥ 80% coverage) | New chain reusing existing family: 0 Python lines, 1 `config/chains/<chain>.json` |
| G2. Adding new family (beyond SVM / EVM / StarkVM / MoveVM) **only needs 1 adapter + 1 JSON** | Add `adapters/<family>.py` + `config/chains/<chain>.json`, no changes to `fetch_active_accounts.py` |
| G3. All 8 existing chains migrate out of `here-doc` with **functional equivalence** (zero behavior regression) | 8-chain e2e_smoke matrix all PASS; `generate_auto_config` output diff = empty pre/post migration |
| G4. CHAIN_CONFIG env var protocol **fully compatible** with current `fetch_active_accounts.py` / `target_generator.sh` / `mock_rpc_server.py` | These 3 consumers **don't change read logic** (only `create_adapter()` dispatch changes) |
| G5. Plugin loading has **explicit failure modes** (unknown chain throws, no silent default) | `load_chain("xxx")` not found → `ChainNotRegisteredError` |

### 0.2 Non-Goals (out of scope this phase)

- ❌ Plugin hot-reload (in-process reload): JSON loaded per test run from disk, no hot reload needed
- ❌ Plugin remote fetch (URL/git): all JSON in-tree, version follows git
- ❌ Plugin inter-dependency graph: each chain independent, no inherit / extends
- ❌ Plugin sandbox: adapters are in-process Python, trusts repo code

### 0.3 Reversal Conditions

| Signal | Action |
|---|---|
| P1-2 research finds ≥ 3 chains schema can't accommodate (non-family heterogeneity) | Add `extras: {...}` free-form field, document schema |
| User changes mind requiring "0 Python add chain" full coverage on 28 chains | Introduce family-agnostic generic adapter (not this phase, Cosmos/Aptos/Cardano models too divergent) |
| `chain_type` dispatch becomes bottleneck | Switch to `__init_subclass__` registry, no such pressure this phase (single-process tests) |

---

## 1. Current State Analysis (Why Plugin)

### 1.1 Existing 8-Chain here-doc Field Matrix (Axis 1 Empirical)

From `config/config_loader.sh` `UNIFIED_BLOCKCHAIN_CONFIG` parse:

| Field | 8-chain coverage | Purpose |
|---|---|---|
| `chain_type` | all ✓ | adapter dispatch key |
| `rpc_url` | all ✓ | endpoint (runtime replaced with `LOCAL_RPC_URL`) |
| `params.{account_count, output_file, target_address, max_signatures, tx_batch_size, semaphore_limit}` | all ✓ | adapter runtime params |
| `methods.get_transaction` | all ✓ | adapter method name for fetching tx |
| `methods.get_signatures` | solana only | SolanaAdapter |
| `methods.get_logs` | EVM 5 chains | EthereumAdapter |
| `methods.get_events_native` | starknet only | StarknetAdapter |
| `methods.get_owned_objects`, `get_transactions` | sui only | SuiAdapter |
| `rpc_methods.{single, mixed}` | all ✓ | target_generator.sh produces vegeta targets |
| `param_formats.<method>` | all ✓ | target_generator.sh constructs params (free-form map) |
| `system_addresses` | all ✓ | adapter filters system addresses |

**Conclusion**: **No field is family-exclusive** (`methods.*` sub-keys are family-specific but live under a shared `methods` container). Schema can be **strict required + family-aware optional + free-form param map**.

### 1.2 Existing Downstream Consumers (Axis 2 Empirical)

```
┌──────────────────────────────────────────────────────────────┐
│ config/config_loader.sh                                       │
│  └ UNIFIED_BLOCKCHAIN_CONFIG (here-doc JSON, 8 chains in one) │
│  └ generate_auto_config() injects LOCAL_RPC_URL etc.          │
│  └ export CHAIN_CONFIG=<chain sub-JSON>                      │
└──────────────────────────────────────────────────────────────┘
        │
        ▼ env var CHAIN_CONFIG (JSON string)
        │
   ┌────┴───────────────────────────────┐
   ▼                ▼                   ▼
┌──────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ fetch_active │ │ target_generator │ │ mock_rpc_server  │
│ _accounts.py │ │   .sh            │ │   .py            │
│              │ │                  │ │ (mock data only, │
│ create_      │ │ jq .rpc_methods  │ │  doesn't read    │
│  adapter()   │ │ jq .param_       │ │  config)         │
│  ⚠️ hardcoded │ │  formats         │ │                  │
│  chain_type  │ │                  │ │                  │
│  → Adapter   │ │                  │ │                  │
│  branch      │ │                  │ │                  │
└──────────────┘ └──────────────────┘ └──────────────────┘
```

**Only hardcoded point** = `tools/fetch_active_accounts.py:663-674` `create_adapter()` 5-branch if-else. **This is the sole real blocker** for chain-as-plugin. Other consumers read JSON without chain branching — **already plugin-friendly**.

---

## 2. Design: Plugin Framework

### 2.1 Directory Structure

```
blockchain-node-benchmark/
├── config/
│   ├── config_loader.sh           # change: load from chains/*.json, remove UNIFIED_BLOCKCHAIN_CONFIG
│   └── chains/                    # new
│       ├── solana.json
│       ├── ethereum.json
│       ├── bsc.json
│       ├── base.json
│       ├── scroll.json
│       ├── polygon.json
│       ├── starknet.json
│       ├── sui.json
│       └── _schema.json           # JSON Schema (optional, for human review)
│
├── tools/
│   ├── fetch_active_accounts.py   # change: create_adapter() via registry
│   ├── adapters/                  # new
│   │   ├── __init__.py            # ADAPTER_REGISTRY exposed
│   │   ├── _base.py               # ChainAdapter ABC
│   │   ├── solana.py              # SolanaAdapter (moved from fetch_active_accounts.py)
│   │   ├── ethereum.py            # EthereumAdapter
│   │   ├── starknet.py            # StarknetAdapter
│   │   └── sui.py                 # SuiAdapter
│   └── plugin_loader.py           # new: load_chain(name) / list_chains() / family_of(name)
│
└── docs/
    ├── zh/plugin/
    │   ├── 00-design.md           # this doc
    │   ├── 01-adding-a-chain.md   # how-to: add new chain (JSON only / new family)
    │   └── 02-schema.md           # JSON schema field doc
    └── en/plugin/                 # same
```

### 2.2 `config/chains/<chain>.json` Schema

**Example** (solana.json, based on R1-PRIME corrected state):

```json
{
  "$schema": "../_schema.json",
  "chain_id": "solana",
  "chain_type": "solana",
  "family": "svm",
  "official_rpc": "https://api.mainnet-beta.solana.com",
  "doc_base": "https://solana.com/docs/rpc",
  "rpc_url_var": "LOCAL_RPC_URL",
  "params": {
    "account_count": "ACCOUNT_COUNT",
    "output_file": "ACCOUNTS_OUTPUT_FILE",
    "target_address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "max_signatures": "ACCOUNT_MAX_SIGNATURES",
    "tx_batch_size": "ACCOUNT_TX_BATCH_SIZE",
    "semaphore_limit": "ACCOUNT_SEMAPHORE_LIMIT"
  },
  "methods": {
    "get_signatures": "getSignaturesForAddress",
    "get_transaction": "getTransaction"
  },
  "system_addresses": [
    "11111111111111111111111111111111",
    "..."
  ],
  "rpc_methods": {
    "single": "getAccountInfo",
    "mixed": "getAccountInfo,getBalance,getTokenAccountBalance,getLatestBlockhash,getBlockHeight"
  },
  "param_formats": {
    "getAccountInfo": "single_address",
    "getBalance": "single_address",
    "getTokenAccountBalance": "single_address",
    "getLatestBlockhash": "no_params",
    "getBlockHeight": "no_params"
  }
}
```

### 2.3 Schema Field Constraints

| Field | Type | Required | Description |
|---|---|---|---|
| `chain_id` | string | ✓ | Filename (without `.json`) = chain_id, used by plugin loader for lookup |
| `chain_type` | string | ✓ | adapter dispatch key (can = chain_id or = family alias) |
| `family` | enum: svm/evm/starkvm/movevm/utxo/cosmos/... | ✓ | adapter implementation mapping; new family must implement ChainAdapter at `adapters/<family>.py` |
| `official_rpc` | URL | ✓ | Official recommended mainnet endpoint (audit tool uses) |
| `doc_base` | URL | ✓ | Doc base URL (audit L1_doc uses) |
| `rpc_url_var` | string | ✓ | Runtime replacement token (default `LOCAL_RPC_URL`) |
| `params` | object | ✓ | adapter runtime params, free-form keys |
| `methods` | object | ✓ | adapter method name mapping (must have `get_transaction`) |
| `system_addresses` | array<string> | ✓ | Filter system addresses, can be empty |
| `rpc_methods.single` | string | ✓ | benchmark single-method mode |
| `rpc_methods.mixed` | string | ✓ | benchmark mixed mode (comma-separated method list) |
| `param_formats` | object | ✓ | param template for each method in mixed; key = method name, value = format enum |
| `param_formats.<method>` | enum: `no_params/single_address/address_latest/latest_address/address_storage_latest/address_key_latest/address_with_options` | ✓ | See `target_generator.sh:77-108` |

**Strictness**:
- ❌ No additional fields (JSON Schema `additionalProperties: false`) — prevents silent typo bugs
- ✅ Free-form keys inside `params` / `methods` / `param_formats` (chains differ)

### 2.4 `tools/adapters/_base.py` ABC Interface

```python
from abc import ABC, abstractmethod
from typing import List, Optional

class ChainAdapter(ABC):
    """Contract for all family adapters. One implementation per family."""

    chain_type: str  # subclass must set (used as registry key, validation)
    family: str      # same

    def __init__(self, config: dict):
        self.config = config
        self.chain_type = config["chain_type"]
        self.family = config["family"]
        self.target_address = config["params"]["target_address"]
        # ...

    @abstractmethod
    async def fetch_signatures(self, address: str, cursor=None, limit=500, verbose=False) -> List[dict]:
        """Fetch tx signatures (or equivalent unit — sui digest, starknet hash)."""

    @abstractmethod
    async def fetch_transaction(self, sig_or_hash: str, verbose=False) -> Optional[dict]:
        """Fetch single tx detail by signature/hash."""

    @abstractmethod
    def extract_accounts_from_transaction(self, tx: dict) -> List[str]:
        """Extract account addresses involved in a tx detail."""

    # Optional hooks (default impl):
    def filter_system_addresses(self, addrs: List[str]) -> List[str]:
        sys_set = set(self.config.get("system_addresses", []))
        return [a for a in addrs if a not in sys_set]
```

### 2.5 `tools/plugin_loader.py`

```python
"""Chain plugin loader. Single responsibility: load config/chains/*.json + adapter dispatch."""
from __future__ import annotations
import json, importlib, os
from pathlib import Path
from typing import Dict

REPO = Path(__file__).resolve().parent.parent
CHAINS_DIR = REPO / "config" / "chains"
ADAPTERS_PKG = "tools.adapters"

# family → module name mapping (explicit, no importlib guessing)
FAMILY_MODULES = {
    "svm": "solana",        # currently only solana
    "evm": "ethereum",      # ethereum/bsc/base/scroll/polygon share
    "starkvm": "starknet",
    "movevm": "sui",
}

class ChainNotRegisteredError(LookupError):
    pass

class UnknownFamilyError(LookupError):
    pass

def list_chains() -> list[str]:
    """Return all registered chain_ids (dir scan)."""
    return sorted(p.stem for p in CHAINS_DIR.glob("*.json") if not p.stem.startswith("_"))

def load_chain(chain_id: str) -> dict:
    """Load chain JSON + validate required fields."""
    path = CHAINS_DIR / f"{chain_id}.json"
    if not path.exists():
        raise ChainNotRegisteredError(
            f"Chain '{chain_id}' not found. Available: {list_chains()}"
        )
    cfg = json.loads(path.read_text())
    _validate(cfg, chain_id)
    return cfg

def _validate(cfg: dict, chain_id: str):
    """Minimum field validation (JSON Schema strict-check can be added later)."""
    required = ["chain_type", "family", "official_rpc", "rpc_url_var",
                "params", "methods", "rpc_methods", "param_formats", "system_addresses"]
    missing = [k for k in required if k not in cfg]
    if missing:
        raise ValueError(f"Chain '{chain_id}' missing fields: {missing}")
    if cfg["family"] not in FAMILY_MODULES:
        raise UnknownFamilyError(
            f"Chain '{chain_id}' family='{cfg['family']}' not in {list(FAMILY_MODULES)}. "
            f"Add tools/adapters/<family>.py + register in FAMILY_MODULES."
        )

def create_adapter(cfg: dict):
    """Dispatch adapter instance from cfg. Replaces old create_adapter() 5-branch if-else."""
    family = cfg["family"]
    module_name = FAMILY_MODULES.get(family)
    if not module_name:
        raise UnknownFamilyError(f"family='{family}' not registered")
    mod = importlib.import_module(f"{ADAPTERS_PKG}.{module_name}")
    # convention: each family module exposes ADAPTER_CLASS
    return mod.ADAPTER_CLASS(cfg)
```

### 2.6 `tools/fetch_active_accounts.py` Changes

```python
# OLD (L661-674):
def create_adapter(config):
    chain_type = config["chain_type"].lower()
    if chain_type == "solana":
        return SolanaAdapter(config)
    elif chain_type in ["ethereum", "bsc", "base", "scroll", "polygon"]:
        return EthereumAdapter(config)
    elif chain_type == "starknet":
        return StarknetAdapter(config)
    elif chain_type == "sui":
        return SuiAdapter(config)
    else:
        raise ValueError(f"Unsupported chain type: {chain_type}")

# NEW:
from tools.plugin_loader import create_adapter as _plugin_create_adapter
def create_adapter(config):
    return _plugin_create_adapter(config)
```

**Another spot** `fetch_all_signatures()` L684 `if adapter.chain_type == "solana"` also needs change — Solana cursor semantics differ. **Fix**: move cursor advancement to adapter's `next_cursor(batch)` method, `fetch_all_signatures()` only calls `adapter.next_cursor(batch)`, **outer layer no longer if chain_type**.

### 2.7 `config/config_loader.sh` Changes

**Remove**: `UNIFIED_BLOCKCHAIN_CONFIG=$(cat <<'EOF' ... EOF)` here-doc (L402-651, ~250 lines)

**Add** loader function:

```bash
load_chain_config() {
    local chain_id="$1"
    local chain_file="${HERE_DIR}/chains/${chain_id}.json"
    if [[ ! -f "$chain_file" ]]; then
        echo "❌ Chain '${chain_id}' not registered. Available:" >&2
        ls "${HERE_DIR}/chains/" | grep -v '^_' | sed 's/.json$//' >&2
        return 1
    fi
    # Inject LOCAL_RPC_URL etc runtime vars (originally done by generate_auto_config)
    jq --arg url "$LOCAL_RPC_URL" '.rpc_url = $url' "$chain_file"
}

# generate_auto_config becomes:
# CHAIN_CONFIG=$(load_chain_config "$BLOCKCHAIN_NODE")
# export CHAIN_CONFIG
```

**Preserve**: `get_param_format_from_json()`, `get_current_rpc_methods()` (CHAIN_CONFIG consumer logic unchanged)

### 2.8 Test Strategy (P2-4 execution)

| Layer | Validates | Pass criteria |
|---|---|---|
| L1 unit | `plugin_loader.load_chain("solana")` etc 8 chains all OK, unknown chain throws `ChainNotRegisteredError` | 8 + 1 = 9 cases PASS |
| L1 unit | `create_adapter()` dispatches to correct class | 8-chain isinstance check |
| L2 integ | 8-chain `target_generator.sh` runs through, generated target.json byte-identical to pre-migration | `diff -r` empty |
| L2 integ | 8-chain `fetch_active_accounts.py --count 5 --max-sigs 10` runs through | no errors, has output |
| L3 e2e | 8-chain e2e_smoke matrix (existing `tests/e2e_smoke/`) | all PASS |
| L3 e2e | Audit result diff = empty pre/post migration (same endpoint same method) | matrix identical |

---

## 3. Migration Path (P2-1 ~ P2-5 sub-task breakdown)

### 3.1 P2-1: Framework landing + 8-chain JSON split

1. Write `tools/adapters/_base.py` ChainAdapter ABC
2. Write `tools/plugin_loader.py`
3. Move 4 existing adapter classes from `fetch_active_accounts.py` to `tools/adapters/{solana,ethereum,starknet,sui}.py`, end each with `ADAPTER_CLASS = XxxAdapter`
4. Change `fetch_active_accounts.py`: `create_adapter()` via plugin_loader, `fetch_all_signatures()` uses `adapter.next_cursor()` to replace `if chain_type == "solana"`
5. Split here-doc into `config/chains/{solana,ethereum,bsc,base,scroll,polygon,starknet,sui}.json` 8 files (add `family` field)
6. Change `config/config_loader.sh`: remove here-doc, add `load_chain_config()`
7. L1+L2+L3 all PASS (P2-4), **byte-identical** verification

### 3.2 P2-2 / P2-3: Add new chains (not part of P2-DESIGN)

- 15 new core adapter chains (Aptos / Cosmos / Cardano etc): 1 JSON per chain, may add 1 family adapter
- 4 Bitcoin-reuse chains: all use utxo family, JSON only

### 3.3 P2-5: commit + push

Split by logical commit:
- C3: plugin loader + ABC + 8 adapter migration (pure refactor, zero behavior change)
- C4: 8-chain JSON split + config_loader.sh rewrite
- C5: fetch_active_accounts.py plumbing to plugin_loader
- C6: e2e_smoke verification + doc updates

---

## 4. Risks and Mitigation

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Hidden branches like `fetch_active_accounts.py:684 if chain_type == "solana"` not all found | Medium | Behavior regression | search_files full grep `chain_type ==` / `chain_type.lower()` then audit Q3 |
| Post-JSON-split jq parse differs from here-doc (whitespace/encoding) | Low | Byte-diff fails | Migration script jq round-trip + `diff` verify |
| `adapter.next_cursor()` interface doesn't fit sui (sui uses cursor object) | Medium | Sui adapter stuck | Interface v0 set to `Optional[Any]`, each adapter returns freely (self can consume) |
| `_schema.json` not written → typo-prone field doesn't error | Medium | Plugin silently fails | `_validate()` required-field hard check; Schema can be added later |
| target_generator.sh jq query path incompatible with new JSON | Low | Bench fails | P2-4 L2 integ byte-identical check catches |

---

## 5. Decision Gates (decision-with-tradeoffs)

### D1: family explicit declare vs auto-infer
- **Recommended: explicit declare** (`family` field required)
- Why: ① friendly audit/loader error messages (specify missing family); ② forces thinking about belonging when adding chain
- Reversal: family count > 12 → maintenance cost high, consider auto-infer
- Residual risk: writing wrong family in JSON — `_validate()` throws UnknownFamilyError as backstop

### D2: adapter dispatch mechanism — registry dict vs `__init_subclass__`
- **Recommended: explicit FAMILY_MODULES dict** (`plugin_loader.py:14`)
- Why: ① import-time side effects minimal, debug-friendly; ② no import-order dependency; ③ lists support up-front
- Reversal: family count > 20 → switch to `__init_subclass__` auto-registry
- Residual risk: adding new family requires plugin_loader.py change (1 line), not "0 change"

### D3: JSON field strictness — `additionalProperties: false` or allow extras
- **Recommended: strict** (JSON Schema `additionalProperties: false`)
- Why: prevent typo bugs silently ignored (typical: `rpcUrl` vs `rpc_url`)
- Reversal: P1-2 research finds ≥ 3 chains need family-specific extension fields → use `extras: { ... }` sandbox
- Residual risk: normal — strictness > flexibility (failure must speak)

### D4: rpc_url injection timing — load-time vs consume-time
- **Recommended: load-time** (`load_chain_config()` uses jq to inject `LOCAL_RPC_URL`)
- Why: consistent with existing `generate_auto_config()` behavior, downstream consumers transparent
- Reversal: none (this is compatibility constraint)

### D5: migration path — one-shot vs incremental
- **Recommended: one-shot** (8 chains together, single PR)
- Why: ① 8 chains all have here-doc, partial migration leaves dual-source-of-truth hell; ② byte-identical diff in one pass cheaper than 8 passes
- Reversal: ≥ 2 of 8 chains have already-broken e2e_smoke → fix broken first
- Residual risk: big diff, hard to review; mitigation = split into 4 logical commits (loader / adapter migration / JSON split / plumbing)

---

## 6. Acceptance Checklist (P2-1 completion)

- [ ] `tools/adapters/_base.py` + 4 adapter files all in place
- [ ] `tools/plugin_loader.py` 8 chains all `load_chain()` + `create_adapter()` work
- [ ] `tools/plugin_loader.py` unknown chain throws `ChainNotRegisteredError` + lists available
- [ ] `config/chains/*.json` 8 files + `_schema.json` (optional)
- [ ] `config/config_loader.sh` removes here-doc, adds `load_chain_config()`
- [ ] `tools/fetch_active_accounts.py` no more `if chain_type ==` hardcoded
- [ ] L1 + L2 + L3 tests all PASS
- [ ] 8-chain audit re-run: matrix diff = empty (method/endpoint unchanged)
- [ ] 8-chain target_generator output: byte-identical to pre-migration
- [ ] critical-self-audit-after-fix three questions pass (caller blind / reader blind / can run)

---

## 7. History

| Date | Author | Change |
|---|---|---|
| 2026-05-23 | Hermes Agent | DRAFT v1, awaiting user review |
