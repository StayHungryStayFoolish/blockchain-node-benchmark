#!/usr/bin/env python3
"""Runtime probe: get_block_height() must work against fake-node for 36 chains.

This exercises the production bash entry point in core/common_functions.sh:
  get_block_height(url) -> adapter health-probe -> curl -> adapter parse-height

It catches drift between chain templates, adapter health probes, fake-node
fixtures, and the monitor-facing bash function.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
CHAINS_DIR = REPO / "config" / "chains"
FAKE_NODE_DIR = REPO / "tools" / "fake-node"


def wait_ready(proc: subprocess.Popen[str], port: int, timeout: float = 3.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/stats", timeout=0.2):
                return True
        except Exception:
            time.sleep(0.1)
    return proc.poll() is None


def run_get_block_height(chain: str, port: int, timeout: float) -> tuple[int, str, str]:
    url = f"http://127.0.0.1:{port}"
    script = (
        "source core/common_functions.sh >/dev/null 2>&1; "
        f"BLOCKCHAIN_NODE={chain} MEMORY_SHARE_DIR=/tmp BLOCK_HEIGHT_CURL_TIMEOUT={timeout} "
        f"get_block_height {url}"
    )
    proc = subprocess.run(
        ["bash", "-lc", script],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout + 5,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fake-node-bin", default="/tmp/fake-node-v2")
    parser.add_argument("--base-port", type=int, default=19600)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows: list[dict[str, Any]] = []

    for index, path in enumerate(sorted(CHAINS_DIR.glob("*.json"))):
        chain = path.stem
        port = args.base_port + index
        log_path = Path(f"/tmp/fake-node-height-{chain}.log")
        with log_path.open("w") as log:
            proc = subprocess.Popen(
                [args.fake_node_bin, f"-chain={chain}", f"-port={port}"],
                cwd=FAKE_NODE_DIR,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
            )
            try:
                if not wait_ready(proc, port):
                    rows.append({
                        "chain": chain,
                        "status": "START_FAIL",
                        "height": "",
                        "stderr": str(log_path),
                    })
                    continue
                rc, stdout, stderr = run_get_block_height(chain, port, args.timeout)
                ok = rc == 0 and stdout.isdigit()
                rows.append({
                    "chain": chain,
                    "status": "ok" if ok else "FAIL",
                    "height": stdout,
                    "stderr": stderr[:180].replace("\n", " "),
                })
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()

    bad = [row for row in rows if row["status"] != "ok"]
    summary = {
        "total_chains": len(rows),
        "ok": len(rows) - len(bad),
        "bad": len(bad),
    }
    if args.json:
        print(json.dumps({"summary": summary, "bad": bad}, indent=2, sort_keys=True))
    else:
        print(json.dumps(summary, indent=2))
        for row in bad:
            print("BAD\t{chain}\t{status}\t{height}\t{stderr}".format(**row))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
