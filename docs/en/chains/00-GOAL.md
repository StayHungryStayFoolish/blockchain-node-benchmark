# 28-Chain Plugin Refactor — Strategic Goal & Hard Constraints

> **This file is the anchor for the chain-as-plugin refactor. Every cron tick / compaction / new session MUST read this file first before continuing.**
> **Purpose: prevent strategic-goal drift in long tasks. Violating any hard constraint = refactor failure, must roll back.**

---

## 1. Strategic Goal (locked, no drift)

Enable exchange business users to **add a new chain by dropping in ONE JSON config file**, with zero code changes.

- Current pain: adding a chain requires modifying 3 sections of `config_loader.sh` (880-line shell) + factory `if/elif` dispatch in `tools/fetch_active_accounts.py` + test fixtures
- After refactor: `config/chains/<chain>.json` is all you need. If the new chain's protocol family already has an adapter → **zero code**. If it's a brand-new family → business user submits a PR adding 1 adapter file.

---

## 2. Coverage (28 public chains)

See `00-SUMMARY.md` for the full list. Categories:

| Category | Count | Notes |
|---|---|---|
| 8 existing chains | 8 | Solana / Ethereum / BSC / Base / Polygon / Scroll / Starknet / Sui — regression protected |
| 15 new core-adapter chains | 15 | Each requires a new adapter module |
| 4 Bitcoin reuse chains | 4 | Zcash / LTC / DOGE / BCH — reuse BitcoinAdapter |
| 1 Tron dual-API | (in 15) | Must support both `/jsonrpc` and `/wallet/*` |

---

## 3. Hard Constraints (violation = refactor failure)

| # | Constraint | Verification |
|---|---|---|
| H1 | 8 existing chains: e2e_smoke matrix 100% PASS, no existing tests broken | `python3 -m unittest tests.X -v` + e2e_smoke 8/8 |
| H2 | Adapters are also plugin-loaded via `importlib`, no hard dispatch | grep verify: no `if chain == "X"` dispatching |
| H3 | Tron MUST support dual API (JSON-RPC + native `/wallet/*`), incl. TRC20 | curl-verify USDT-TRC20 balance |
| H4 | Cross-cloud parity preserved (AWS/GCP both run all 28 chains) | cross-cloud comparison test |
| H5 | No new PyPI deps; if required, sync `requirements.txt` + `install_deps.sh` | git diff inspection |
| H6 | Real-name rule: `LEDGER_DEVICE` (default nvme1n1) + `ACCOUNTS_DEVICE` (default nvme2n1) semantics unchanged | grep verify |
| H7 | Bilingual doc parity (`docs/zh/chains/` ↔ `docs/en/chains/`, 1:1) | mirror file names + dirs |
| H8 | Every chain doc MUST contain **real evidence** (curl test output + official doc URL + access date) | review sampling |
| H9 | Fixture "each pool independent, recent N blocks" rule preserved | no shared-fixture refactor |
| H10 | Business user adds new chain = JSON only (when same-family adapter exists) | acceptance: add 1 new EVM chain with 0 lines of Python |

---

## 4. Doc Conventions

### 4.1 Bilingual Mirroring

- `docs/zh/chains/01-solana.md` ↔ `docs/en/chains/01-solana.md`
- Contents **correspond**. Chinese version may include more localized notes, but **section headings and table structures MUST match**.
- File numbering 01-28 follows the chain order in `00-SUMMARY.md`.

### 4.2 Research Template

See `_template.md`. Fixed 10-section structure:

1. Sources (official doc URL + access date)
2. Protocol Family (family / consensus / account model)
3. Public RPC (endpoint + auth + rate limits)
4. Account Model (UTXO vs Account)
5. Core RPC Methods (methods our framework monitors)
6. Address Format (format / checksum / length)
7. Signature Lookup (sig / tx-hash format)
8. Mixed Set (weight suggestion for `mixed` mode)
9. Mock Notes (mock_rpc_server impl notes)
10. Adapter Reuse Decision (adapter reuse decision + rationale)

### 4.3 Real-Evidence Requirements

Each chain MUST include:
- ✅ At least 1 `curl ... | jq` real output
- ✅ Official doc URL + access date (YYYY-MM-DD)
- ✅ Mainnet real data (block height / tx hash / address)
- ❌ No making up schema/method from memory. **Research first (R20.7)**.

---

## 5. 28-Chain Checklist (mark ✅ on completion)

### 8 existing chains (Phase 1.1)
- [ ] 01-solana
- [ ] 02-ethereum
- [ ] 03-bsc
- [ ] 04-base
- [ ] 05-polygon
- [ ] 06-scroll
- [ ] 07-starknet
- [ ] 08-sui

### 15 new core-adapter chains (Phase 1.2)
- [ ] 09-bitcoin
- [ ] 10-ton
- [ ] 11-cardano
- [ ] 12-tron (dual-API)
- [ ] 13-cosmos
- [ ] 14-avalanche-p-x (non-C chain)
- [ ] 15-near
- [ ] 16-polkadot
- [ ] 17-aptos
- [ ] 18-xrp
- [ ] 19-stellar
- [ ] 20-algorand
- [ ] 21-hedera
- [ ] 22-filecoin
- [ ] 23-icp
- [ ] 24-monero

### 4 Bitcoin reuse chains (Phase 1.3)
- [ ] 25-zcash
- [ ] 26-litecoin
- [ ] 27-dogecoin
- [ ] 28-bitcoin-cash

---

## 6. Failure Rollback

Any H1-H10 violation → that Phase MUST be **fully rolled back** (`git reset --hard`). NO "continue first, fix later".

Reference skills: `no-deferred-bugs` + memory rule #6.

---

**Last updated**: 2026-05-23 by Hermes Agent
**Target version**: v1.4.7
**Baseline commit**: `b2c0ccc`
