#!/usr/bin/env python3
"""
Legacy migration helper: normalize older chain templates to the baseline
chain-template format.

Input:  config/chains/<chain>.json  (older research-oriented format)
Output: config/chains/<chain>.json  (chain-template format with _meta provenance)

IDEMPOTENT: re-running on already-normalized file = no-op (detected via _meta.normalized_at).

Field mapping (research → baseline):
    chain_type           → chain_type            (kept)
    rpc_url              ← "LOCAL_RPC_URL"       (constant placeholder for local node endpoints)
    rpc_methods.single   ← single_method         (string)
    rpc_methods.mixed    ← ",".join(mixed_methods)
    param_formats        → param_formats         (kept)
    params               ← {
        account_count, max_signatures, output_file,
        semaphore_limit, target_address, tx_batch_size
    }  (baseline template; target_address from research target_address)
    system_addresses     → system_addresses      (kept)

Research-only fields (DROPPED but preserved in _meta.original):
    chain / public_endpoints / single_method / mixed_methods /
    rpc_protocol / target_address / notes

Non-JSON-RPC chains: `_meta.adapter_required = true` if rpc_protocol in {rest, mixed}.
These chains are normalized to baseline shape, but HTTP-path methods require a
family adapter before they can be exercised by fake-node or target generation.

Usage:
    python3 tools/normalize_chain_templates.py [--dry-run]
"""

import json
import os
import sys
import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHAINS_DIR = REPO_ROOT / "config" / "chains"

# baseline chain names (already in baseline format, MUST NOT be touched)
BASELINE_8 = {"solana", "ethereum", "bsc", "base", "scroll", "polygon", "starknet", "sui"}

# Baseline params template used by normalized chain configs in config/chains/.
BASELINE_PARAMS_TEMPLATE = {
    "account_count": "ACCOUNT_COUNT",
    "max_signatures": "ACCOUNT_MAX_SIGNATURES",
    "output_file": "ACCOUNTS_OUTPUT_FILE",
    "semaphore_limit": "ACCOUNT_SEMAPHORE_LIMIT",
    "target_address": None,  # filled per chain
    "tx_batch_size": "ACCOUNT_TX_BATCH_SIZE",
}

# Required baseline keys.
BASELINE_REQUIRED_KEYS = {
    "chain_type", "param_formats", "params",
    "rpc_methods", "rpc_url", "system_addresses",
}


def is_already_baseline(tpl: dict) -> bool:
    """Detect baseline-format template (idempotency guard)."""
    return BASELINE_REQUIRED_KEYS.issubset(set(tpl.keys()) - {"_meta"})


def normalize_one(chain_name: str, tpl: dict) -> dict:
    """Convert a research-format template to baseline format. Returns new dict."""
    if is_already_baseline(tpl):
        return tpl  # idempotent no-op

    # Extract research fields with defensive defaults
    chain_type = tpl.get("chain_type", chain_name)
    single_method = tpl.get("single_method", "")
    mixed_methods = tpl.get("mixed_methods", [])
    if isinstance(mixed_methods, list):
        mixed_str = ",".join(mixed_methods)
    else:
        mixed_str = str(mixed_methods)
    param_formats = tpl.get("param_formats", {})
    system_addresses = tpl.get("system_addresses", [])
    target_address = tpl.get("target_address", "")
    rpc_protocol = tpl.get("rpc_protocol", "json-rpc")
    notes = tpl.get("notes", "")
    public_endpoints = tpl.get("public_endpoints", [])

    # Build baseline params dict
    params = dict(BASELINE_PARAMS_TEMPLATE)
    params["target_address"] = target_address

    # Preserve original meta + add provenance
    old_meta = tpl.get("_meta", {})
    new_meta = {
        **old_meta,
        "normalized_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "normalized_by": "tools/normalize_chain_templates.py",
        "original_rpc_protocol": rpc_protocol,
        "original_public_endpoints": public_endpoints,
        "original_notes": notes,
        "adapter_required": rpc_protocol in {"rest", "mixed"} or "/" in single_method,
    }

    return {
        "chain_type": chain_type,
        "param_formats": param_formats,
        "params": params,
        "rpc_methods": {
            "single": single_method,
            "mixed": mixed_str,
        },
        "rpc_url": "LOCAL_RPC_URL",
        "system_addresses": system_addresses,
        "_meta": new_meta,
    }


def main():
    dry_run = "--dry-run" in sys.argv

    files = sorted(CHAINS_DIR.glob("*.json"))
    print(f"== Found {len(files)} chain template(s) in {CHAINS_DIR}")
    print(f"== Mode: {'DRY-RUN (no writes)' if dry_run else 'LIVE'}")
    print()

    skipped_baseline = []
    skipped_empty = []
    normalized = []
    already_norm = []
    adapter_required = []

    for f in files:
        chain = f.stem
        if chain in BASELINE_8:
            skipped_baseline.append(chain)
            continue

        try:
            content = f.read_text()
        except Exception as e:
            print(f"  ✗ {chain}: read error {e}")
            continue

        if not content.strip():
            skipped_empty.append(chain)
            print(f"  ⚠ {chain}: EMPTY FILE — will skip (fix manually)")
            continue

        try:
            tpl = json.loads(content)
        except Exception as e:
            print(f"  ✗ {chain}: JSON parse error {e}")
            continue

        if is_already_baseline(tpl):
            already_norm.append(chain)
            continue

        new_tpl = normalize_one(chain, tpl)

        if new_tpl["_meta"].get("adapter_required"):
            adapter_required.append(chain)

        new_text = json.dumps(new_tpl, indent=2, ensure_ascii=False) + "\n"

        if not dry_run:
            f.write_text(new_text)
            print(f"  ✓ {chain:14s}  normalized ({len(content)}B → {len(new_text)}B"
                  f"{', adapter_required' if new_tpl['_meta'].get('adapter_required') else ''})")
        else:
            print(f"  [dry] {chain:14s}  would normalize ({len(content)}B → {len(new_text)}B"
                  f"{', adapter_required' if new_tpl['_meta'].get('adapter_required') else ''})")
        normalized.append(chain)

    print()
    print(f"== Summary")
    print(f"   baseline 8 (untouched):  {len(skipped_baseline)}: {skipped_baseline}")
    print(f"   already normalized:      {len(already_norm)}: {already_norm}")
    print(f"   normalized this run:     {len(normalized)}")
    print(f"   empty files (skipped):   {len(skipped_empty)}: {skipped_empty}")
    print(f"   adapter_required marked: {len(adapter_required)}: {adapter_required}")

    if skipped_empty:
        print(f"\n⚠ {len(skipped_empty)} empty file(s) require manual fix before re-run.")
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
