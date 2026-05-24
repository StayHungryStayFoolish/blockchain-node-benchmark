# S3-A3 实施报告 — AvaXAdapter (Avalanche X-Chain AVM)

**Date**: 2026-05-24
**Branch**: main
**Baseline**: `60827ad` (S3-A2 head)
**Commit**: (this commit)
**Scope**: Add AvaX (Avalanche X-Chain AVM JSON-RPC 2.0) adapter family — independent of jsonrpc, with multi-endpoint routing, object params, and uint64-as-string contract.

---

## 1. Problem statement

Avalanche X-Chain (`avalanche-x.json`) was declared `adapter_family: jsonrpc`, which is wrong on 4 axes:

| Axis | EVM jsonrpc | Avalanche AVM |
|---|---|---|
| params shape | **array** `[arg1, arg2]` | **object** `{"height":"517990","encoding":"json"}` |
| uint64 encoding | hex string `"0x..."` | **decimal string** `"517990"` (not int) |
| ID encoding | hex 0x | **cb58** (base58 + 4-byte SHA-256 checksum) |
| endpoint | single `/` | **multi**: `/ext/bc/X` (avm.*), `/ext/info` (info.*), `/ext/bc/P` (platform.*) |

Source: live probes against `https://api.avax.network` (avalanchego 1.14.2 commit `6e5acf9`), documented in `docs/zh|en/chains/13-avalanche-x.md` with 11 sections + E1-E5 evidence. The research doc explicitly recommended option (b): independent `avalanche-utxo` family with reusable adapter for future P-Chain.

The 5 `param_formats` declared in the chain template (`no_params`, `height_encoding`, `txid_encoding`, `single_address`, `addresses_limit_encoding`) were placeholder names that did not match any adapter enum. Without a real AvaX adapter, vegeta would never produce correctly-shaped AVM requests.

---

## 2. Design decisions

### 2.1 New family, not jsonrpc reuse

Considered: extend `JsonRpcAdapter` with `namespace_prefix` + `params_shape` knobs.
**Rejected**: the divergence is 4 axes deep (params shape, encoding, IDs, multi-endpoint). Branching JsonRpcAdapter for every `chain==avax` case would violate SRP and breed the same conditional-branch hell the research doc warns against. Family registration is cheap (one decorator); maintenance cost of conditional-branch hell is forever.

### 2.2 Method-name prefix dispatches endpoint

```python
if method.startswith("avm."):      url = base + "/ext/bc/X"
elif method.startswith("info."):   url = base + "/ext/info"
elif method.startswith("platform.")):  url = base + "/ext/bc/P"
else: raise ValueError(...)
```

Rationale: the namespace prefix IS the endpoint selector. avalanchego enforces this server-side (info.* on /ext/bc/X returns -32601). Encoding this at the adapter level rather than chain-template level keeps the chain template declarative (just lists methods) and the adapter authoritative (knows the protocol).

### 2.3 Address surrogation for cross-chain target_generator

The framework's `target_generator.py` is chain-agnostic — it produces EVM-style `0x...` addresses regardless of target chain. AvaXAdapter detects this and substitutes a known-valid bech32 placeholder (`X-avax13k6hxpfuu80dlnqlqs0dxxjrzl4lxz94n38vnw`, extracted from block 517990, verified via avm.getBalance round-trip per research §6 E2). Same logic for cb58 IDs.

This is consistent with the Bitcoin/Cardano/Substrate adapter pattern: framework supplies a generic "address" string; adapter chooses the right encoding for its protocol.

### 2.4 platform.* support (P-Chain) included pre-emptively

Even though v1 mixed set uses only avm.* and info.*, adding the `/ext/bc/P` route now is free (1 line) and saves the next agent from having to revisit AvaXAdapter when P-Chain support is needed (research §10 notes the AvaXAdapter is "90 %+ reusable" by P-Chain).

### 2.5 Mock: namespace-path consistency enforcement

`process_avax_jsonrpc()` rejects cross-namespace requests (info.* at /ext/bc/X) with JSON-RPC -32601. This catches client bugs at test time and matches real avalanchego behavior. Verified by probe 6 in the new e2e sibling.

---

## 3. Files changed

| File | Δ | Note |
|---|---|---|
| `tools/chain_adapters/avax.py` | +175 (NEW) | AvaXAdapter with 10 param_format handlers + 3-endpoint dispatch |
| `tools/chain_adapters/base.py` | +1/-1 | Import `avax` to trigger registration |
| `config/chains/avalanche-x.json` | +3/-1 | `adapter_family: jsonrpc → avax`, translate `single_address → address_only` |
| `tools/mock_rpc_server.py` | +160 | `process_avax_jsonrpc` + 11 method handlers + path dispatch + CHAIN_HANDLERS placeholder |
| `tests/test_chain_adapters.py` | +91 | `test_11_avax_adapter_shapes` (10 sub-assertions) + test list |
| `tools/e2e_smoke_avax_matrix.sh` | +233 (NEW) | e2e harness + 6 AVM contract probes |

**No edits to**: target_generator, vegeta_runner, fetch_active_accounts, e2e_smoke.sh — AvaXAdapter integrates via the existing adapter contract.

---

## 4. Test evidence

### 4.1 L1 — `tests/test_chain_adapters.py` (Python unit)

```
[1] Factory registration
  ✓ 8 families registered: ['avax', 'bitcoin_jsonrpc', 'jsonrpc', 'ogmios', 'rest', 'substrate', 'tendermint', 'tron']
[2] 36 chain templates → adapter resolution
  ✓ 36/36 chains resolve to a registered adapter
[11] AvaXAdapter: avm.*/info.* multi-endpoint + object params + uint64-as-string
  ✓ avm.getHeight → POST /ext/bc/X with params={}
  ✓ avm.getBlockByHeight → height='517990' as STRING
  ✓ avm.getAllBalances → bech32 surrogate when EVM addr supplied
  ✓ avm.getAllBalances → bech32 preserved when supplied
  ✓ avm.getUTXOs → addresses[list] + limit + encoding
  ✓ info.getBlockchainID → POST /ext/info with alias='X'
  ✓ platform.* → POST /ext/bc/P
  ✓ parse_block_height: result.height='517990' (string) → 517990
  ✓ health_check → POST /ext/bc/X avm.getHeight
  ✓ unknown namespace raises ValueError: AvaXAdapter: cannot dispatch ...
✓ ALL TESTS PASSED (11 groups)
```

**11/11 PASS** including 10 AvaX sub-assertions. Tests 1-10 unchanged from S3-A2 (zero regression in baseline/EVM-compat/Tron coverage).

### 4.2 L3 — full sibling matrix (zero regression)

| Sweep | Chains | Result |
|---|---|---|
| `e2e_smoke_8chain_matrix.sh` | 8 baseline | **8/8 PASS** |
| `e2e_smoke_5evm_compat_matrix.sh` | 5 EVM-compat (S3-A) | **5/5 PASS** |
| `e2e_smoke_tron_matrix.sh` | tron + 5 HTTP probe | **2/2 PASS** |
| `e2e_smoke_avax_matrix.sh` (NEW) | avalanche-x + 6 AVM probe | **2/2 PASS** |
| **Totals** | 16 chains + 11 contract probes | **17/17 PASS** |

### 4.3 New sibling probe details (6/6 PASS)

| # | Probe | Verifies |
|---|---|---|
| 1 | `POST /ext/bc/X avm.getHeight` | uint64-as-string contract (`height` is `"517990"` not int) |
| 2 | `POST /ext/bc/X avm.getBlockByHeight` | object params (`{"height":"517990","encoding":"json"}`) accepted |
| 3 | `POST /ext/bc/X avm.getAllBalances` | multi-asset model (≥2 distinct assets returned, balances are strings) |
| 4 | `POST /ext/bc/X avm.getUTXOs` | `numFetched` is STRING, `utxos` is list, `endIndex` present for pagination |
| 5 | `POST /ext/info info.getNodeVersion` | multi-endpoint routing (info.* at /ext/info) |
| 6 | `POST /ext/bc/X info.getBlockchainID` | namespace isolation (info.* at /ext/bc/X rejected with -32601) |

All 6 probes target the real S3-A3 contract surface; none are smoke tests.

---

## 5. Pitfalls encountered

### 5.1 Port collision from leaked Tron sibling proc

First avax sibling run failed at e2e harness step with `OSError: [Errno 98] Address already in use` on port 28569. Root cause: previous Tron sibling run left a `mock_rpc_server.py --chain tron --port 28568` zombie that somehow ended up listening on 28569 (likely socket inheritance from the harness fork sequence). Fix: `pkill -f mock_rpc_server.py` before re-running. **Codified**: each sibling matrix now contains its own `trap "kill $PID" EXIT` but inter-sibling cleanup is the operator's responsibility. Future improvement: add a `tools/cleanup_mock_procs.sh` helper or shared trap in a top-level driver.

### 5.2 Chain-template `param_formats` placeholder names

`single_address` was the placeholder name from research-doc stub; the adapter enum uses `address_only` (matches the actual JSON shape `{"address": ...}`). Translation table applied during template update; verified by L1 `test_11_avax_adapter_shapes` probes 11c+11d (bech32 in, bech32 out).

### 5.3 `block.height` vs `result.height` — one returns int, the other string

Per research §11.2:
- `avm.getHeight` → `{"result": {"height": "517990"}}` (string)
- `avm.getBlockByHeight` → `{"result": {"block": {"height": 517990}}}` (int, nested in block object)

This is avalanchego's `jsonString` type contract: outer uint64 fields are strings, but nested struct fields preserve their declared type. Mock honors this: `_avax_getHeight` returns string, `_avax_getBlockByHeight` returns int. Parsed correctly by `parse_block_height` which uses `_try_int(result.get("height"))` to handle both forms.

---

## 6. Reusability for next wave (S3-A4 Near + future P-Chain)

AvaXAdapter establishes the pattern for "JSON-RPC 2.0 with object params + multi-endpoint + namespace-prefix dispatch". S3-A4 NearAdapter follows the same skeleton but with:
- params shape: object (same as avax)
- method names: flat (no namespace prefix; uses `block`, `query`, `tx`, etc.)
- dispatch knob: logical_method (Near's `query` is a dispatcher that takes a `request_type` field)

**P-Chain reuse path** (90%+ per research §10): rename AvaXAdapter to `AvaxAvmPvmAdapter`, add `platform.*` method handlers to mock (`platform.getCurrentValidators`, `platform.getHeight`, etc.), add P-Chain config to `_meta.adapter_family: avax`. The dispatch table already routes platform.* to /ext/bc/P; only the method handlers are missing.

---

## 7. R0 hygiene check

| Rule | Status | Evidence |
|---|---|---|
| R0 调研先行 | ✓ | docs/{zh,en}/chains/13-avalanche-x.md (11 sections, E1-E5 evidence, 2026-05-23) read before implementation |
| R-1 honest self-check | ✓ | port collision diagnosed and documented (§5.1); no "passes locally" hand-waving |
| R17.5 critical self-audit | ✓ | namespace isolation tested in probe 6 (the negative test catches the kind of bug that "looks ok" but is actually wrong) |
| R20 老测保护 | ✓ | tests 1-10 unmodified; 36 chain count preserved; all 4 L3 sweeps green |
| R20.7 parallel-entry-trap guard | ✓ | AvaXAdapter is sibling to JsonRpcAdapter, not a parallel-rewrite; uses same `ChainAdapter` ABC; integrates via existing factory |
| Family count: ABC before concrete | ✓ | `ChainAdapter` ABC unchanged; AvaXAdapter is a concrete subclass; no ABC modification needed for this family |
| Decision-with-tradeoffs | ✓ | §2.1 documents the rejected alternative (extend JsonRpcAdapter) with reasoning |
| No deferred bugs | ✓ | port-collision pitfall documented inline; no TODO/FIXME left in code |
