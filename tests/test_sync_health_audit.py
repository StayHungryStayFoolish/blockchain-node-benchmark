#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_sync_health_audit_manifest_is_complete():
    proc = subprocess.run(
        [sys.executable, "tools/audit_sync_health_registry.py", "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    manifest = json.loads(proc.stdout)
    assert manifest["summary"]["total_chains"] == 36
    assert manifest["summary"]["errors"] == 0
    assert len(manifest["chains"]) == 36
    assert {entry["current_mode"] for entry in manifest["chains"]} <= {
        "absolute_gap",
        "conditional_gap",
        "reported_lag",
        "freshness_only",
        "health_only",
    }


if __name__ == "__main__":
    test_sync_health_audit_manifest_is_complete()
    print("PASS: sync health audit manifest")
