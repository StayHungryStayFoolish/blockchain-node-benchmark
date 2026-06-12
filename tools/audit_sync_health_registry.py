#!/usr/bin/env python3
"""Audit chain-template sync_health registry coverage.

This tool does not contact public RPC endpoints. It inspects local chain
templates and adapter-generated health probes, then emits a calibration
manifest for the next research/verification pass.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CHAINS_DIR = REPO_ROOT / "config" / "chains"
CLI = REPO_ROOT / "tools" / "chain_adapters" / "cli.py"

MODE_VALUES = {"absolute_gap", "conditional_gap", "reported_lag", "freshness_only", "health_only"}


def load_chain(path: Path) -> dict[str, Any]:
    with path.open() as f:
        return json.load(f)


def adapter_health_probe(chain: str) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            [sys.executable, str(CLI), "health-probe", "--chain", chain, "--rpc-url", "http://127.0.0.1:1"],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            check=True,
        )
        return json.loads(proc.stdout)
    except Exception as exc:  # pragma: no cover - surfaced in manifest
        return {"error": str(exc)}


def infer_probe_kind(probe: dict[str, Any]) -> str:
    if "error" in probe:
        return "error"
    body = str(probe.get("body") or "")
    url = str(probe.get("url") or "")
    parse_jq = str(probe.get("parse_jq") or "")
    signal = " ".join([body, url, parse_jq]).lower()
    if "timestamp" in signal:
        return "monotonic_timestamp"
    if "gethealth" in signal:
        return "boolean_or_reported_health"
    if "eth_syncing" in signal or "system_syncstate" in signal:
        return "conditional_sync_state"
    if any(token in signal for token in (
        "blocknumber",
        "getblockheight",
        "getblockcount",
        "getheight",
        "gettotaltransactionblocks",
        "latest_block_height",
        "chain_getheader",
        "block.header.height",
        "block_height",
        "height",
        "seqno",
        "level",
        "last-round",
        "block_no",
        '"method":"block"',
    )):
        return "numeric_height"
    return "unknown"


def family_calibration_note(family: str, chain: str, probe_kind: str, mode: str, probe: dict[str, Any]) -> tuple[str, str, str]:
    """Return recommended_mode, status, note."""
    if chain == "hedera":
        return (
            "freshness_only",
            "implemented",
            "Hedera Mirror probe returns a consensus timestamp cursor, not canonical block height.",
        )
    if family == "bitcoin_jsonrpc":
        if "getblockchaininfo" in str(probe.get("body") or "").lower():
            return (
                "absolute_gap",
                "implemented",
                "Health probe uses getblockchaininfo.blocks as the comparable cursor; headers and initialblockdownload remain available for future local-only sync enrichment.",
            )
        return (
            "absolute_gap",
            "calibration_candidate",
            "Current adapter uses getblockcount. Bitcoin-family nodes can often expose richer local blocks/headers sync state via getblockchaininfo; confirm whether to switch health_probe later.",
        )
    if family == "substrate":
        if probe_kind == "numeric_height":
            return (
                "absolute_gap",
                "implemented",
                "Adapter compares chain_getHeader.number as the Substrate height cursor documented in local chain evidence. system_syncState remains a future conditional_gap enhancement only after per-chain fixture verification.",
            )
        return (
            "absolute_gap",
            "needs_research",
            "Substrate adapter did not expose a numeric chain_getHeader cursor; verify official docs and real node response before changing mode.",
        )
    if family == "jsonrpc" and chain in {"ethereum", "bsc", "polygon", "base", "scroll", "arbitrum", "optimism", "zksync-era", "linea", "avalanche-c"}:
        if mode == "conditional_gap" and "eth_syncing" in str(probe.get("body") or "").lower():
            return (
                "conditional_gap",
                "implemented",
                "Health probe uses local eth_syncing. false maps to lag 0; syncing objects map to highestBlock-currentBlock and reuse BLOCK_HEIGHT_DIFF_THRESHOLD.",
            )
        return (
            "absolute_gap",
            "calibration_candidate",
            "Current adapter compares eth_blockNumber. eth_syncing/highestBlock may be disabled on public RPCs; keep absolute_gap until local-node support is verified.",
        )
    if chain == "solana":
        if mode == "reported_lag" and "gethealth" in str(probe.get("body") or "").lower():
            return (
                "reported_lag",
                "implemented",
                "Health probe uses Solana getHealth. A healthy result maps to lag 0; unhealthy responses with numSlotsBehind map to slot lag and reuse BLOCK_HEIGHT_DIFF_THRESHOLD.",
            )
        return (
            "absolute_gap",
            "calibration_candidate",
            "Current adapter compares getBlockHeight. Solana getHealth can provide cluster-lag semantics, but fake-node/adapter path currently uses numeric height.",
        )
    if probe_kind == "numeric_height":
        return ("absolute_gap", "implemented", "Adapter health probe returns a numeric height/cursor that can be compared across local and target endpoints.")
    if probe_kind == "monotonic_timestamp":
        return ("freshness_only", "implemented", "Health probe returns a monotonic timestamp-like cursor.")
    return (
        mode,
        "needs_research",
        "Probe kind is not clearly classifiable from local templates; verify official docs and real node response.",
    )


def audit_chain(path: Path) -> dict[str, Any]:
    chain = path.stem
    tpl = load_chain(path)
    meta = tpl.get("_meta", {})
    family = meta.get("adapter_family")
    sync = meta.get("sync_health") or {}
    probe = adapter_health_probe(chain)
    probe_kind = infer_probe_kind(probe)
    mode = sync.get("mode")
    recommended_mode, status, note = family_calibration_note(str(family), chain, probe_kind, str(mode), probe)

    errors: list[str] = []
    if family is None:
        errors.append("missing _meta.adapter_family")
    if not isinstance(sync, dict) or not sync:
        errors.append("missing _meta.sync_health")
    elif mode not in MODE_VALUES:
        errors.append(f"invalid sync_health.mode: {mode!r}")
    if mode == "absolute_gap" and not sync.get("target_probe"):
        errors.append("absolute_gap requires target_probe")

    return {
        "chain": chain,
        "adapter_family": family,
        "current_mode": mode,
        "recommended_mode": recommended_mode,
        "calibration_status": status,
        "threshold_unit": sync.get("threshold_unit"),
        "time_threshold_env": sync.get("time_threshold_env"),
        "probe_kind": probe_kind,
        "health_probe": {
            "method": probe.get("method"),
            "url": probe.get("url"),
            "parse_jq": probe.get("parse_jq"),
            "body": probe.get("body"),
            "error": probe.get("error"),
        },
        "notes": note,
        "errors": errors,
    }


def render_markdown(entries: list[dict[str, Any]]) -> str:
    by_status = Counter(e["calibration_status"] for e in entries)
    by_mode = Counter(e["current_mode"] for e in entries)
    lines = [
        "# Sync Health Registry Audit",
        "",
        "Generated from local chain templates and adapter health probes. This audit does not contact public RPC endpoints.",
        "",
        "## Summary",
        "",
        f"- Total chains: {len(entries)}",
        f"- Current modes: {dict(sorted(by_mode.items()))}",
        f"- Calibration status: {dict(sorted(by_status.items()))}",
        "",
        "## Chain Matrix",
        "",
        "| Chain | Family | Current | Recommended | Unit | Probe Kind | Status | Notes |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for e in sorted(entries, key=lambda x: x["chain"]):
        note = str(e["notes"]).replace("|", "/")
        lines.append(
            f"| {e['chain']} | {e['adapter_family']} | {e['current_mode']} | "
            f"{e['recommended_mode']} | {e['threshold_unit']} | {e['probe_kind']} | "
            f"{e['calibration_status']} | {note} |"
        )
    lines.extend(
        [
            "",
            "## Next Calibration Rules",
            "",
            "- Keep `absolute_gap` when the same numeric height/slot/round can be queried from local and target RPC endpoints.",
            "- Use `conditional_gap` only after a chain's local node exposes a reliable highest-known network height or sync object.",
            "- Use `reported_lag` only when the local node directly reports lag in a documented unit.",
            "- Use `freshness_only` for monotonic cursors or liveness signals that are not canonical block heights.",
            "- Continue reusing `BLOCK_HEIGHT_TIME_THRESHOLD` for sustained unhealthy/stale states.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Print JSON manifest")
    parser.add_argument("--write", action="store_true", help="Write docs/audit/sync-health manifest files")
    args = parser.parse_args()

    entries = [audit_chain(path) for path in sorted(CHAINS_DIR.glob("*.json"))]
    manifest = {
        "summary": {
            "total_chains": len(entries),
            "current_modes": dict(sorted(Counter(e["current_mode"] for e in entries).items())),
            "calibration_status": dict(sorted(Counter(e["calibration_status"] for e in entries).items())),
            "errors": sum(len(e["errors"]) for e in entries),
        },
        "chains": entries,
    }

    if args.write:
        out_dir = REPO_ROOT / "docs" / "audit" / "sync-health"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        (out_dir / "README.md").write_text(render_markdown(entries))

    if args.json:
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
    else:
        print(render_markdown(entries))

    return 1 if manifest["summary"]["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
