#!/usr/bin/env python3
"""Runtime probe: adapter-generated targets must hit fake-node fixtures.

This is stricter than fixture coverage:
  - starts fake-node once per configured chain,
  - generates Vegeta targets through the production chain_adapters CLI,
  - performs real HTTP requests against fake-node,
  - fails if any configured method does not return HTTP 200,
  - fails if any target URL escapes the supplied fake-node endpoint.
"""
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
CHAINS_DIR = REPO / "config" / "chains"
FAKE_NODE_DIR = REPO / "tools" / "fake-node"
DEFAULT_ADDRESS = "11111111111111111111111111111111"


def configured_methods(template: dict[str, Any]) -> list[str]:
    rpc = template.get("rpc_methods", {})
    seen: list[str] = []

    def add(method: str) -> None:
        method = method.strip()
        if method and method not in seen:
            seen.append(method)

    add(str(rpc.get("single", "")))
    weighted = rpc.get("mixed_weighted") or []
    if isinstance(weighted, list):
        for item in weighted:
            if isinstance(item, dict):
                add(str(item.get("method", "")))
    for method in str(rpc.get("mixed", "")).split(","):
        add(method)
    return seen


def normalize_headers(headers: dict[str, Any] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in (headers or {}).items():
        if isinstance(value, list):
            out[key] = ", ".join(str(v) for v in value)
        else:
            out[key] = str(value)
    return out


def build_target(chain: str, method: str, address: str, port: int) -> dict[str, Any]:
    output = subprocess.check_output(
        [
            "python3",
            "tools/chain_adapters/cli.py",
            "build-target",
            "--chain",
            chain,
            "--method",
            method,
            "--address",
            address,
            "--rpc-url",
            f"http://127.0.0.1:{port}",
        ],
        cwd=REPO,
        text=True,
        stderr=subprocess.STDOUT,
    )
    return json.loads(output)


def call_target(target: dict[str, Any], timeout: float) -> tuple[Any, str, str]:
    data = base64.b64decode(target["body"]) if target.get("body") else None
    request = urllib.request.Request(
        target["url"],
        data=data,
        method=target.get("method", "GET"),
        headers=normalize_headers(target.get("header")),
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(200).decode("utf-8", "replace"), target["url"]
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(200).decode("utf-8", "replace"), target["url"]
    except Exception as exc:  # noqa: BLE001 - diagnostic probe should report exact failure
        return "ERR", str(exc), target.get("url", "")


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fake-node-bin", default="/tmp/fake-node-v2")
    parser.add_argument("--base-port", type=int, default=19400)
    parser.add_argument("--address", default=DEFAULT_ADDRESS)
    parser.add_argument("--timeout", type=float, default=1.5)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows: list[dict[str, Any]] = []

    for index, path in enumerate(sorted(CHAINS_DIR.glob("*.json"))):
        chain = path.stem
        port = args.base_port + index
        template = json.loads(path.read_text())
        log_path = Path(f"/tmp/fake-node-probe-{chain}.log")
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
                    rows.append({"chain": chain, "method": "<startup>", "status": "START_FAIL", "url": "", "sample": str(log_path)})
                    continue
                for method in configured_methods(template):
                    try:
                        target = build_target(chain, method, args.address, port)
                        status, sample, url = call_target(target, args.timeout)
                    except Exception as exc:  # noqa: BLE001 - diagnostic probe should continue
                        status, sample, url = "TARGET_ERR", str(exc), ""
                    rows.append({
                        "chain": chain,
                        "method": method,
                        "status": status,
                        "url": url,
                        "sample": sample[:120].replace("\n", " "),
                    })
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()

    bad = [row for row in rows if row["status"] != 200]
    external = [
        row for row in rows
        if row["url"] and "127.0.0.1" not in row["url"] and "localhost" not in row["url"]
    ]
    summary = {
        "total_calls": len(rows),
        "ok": len(rows) - len(bad),
        "bad": len(bad),
        "external_url_targets": len(external),
    }
    if args.json:
        print(json.dumps({"summary": summary, "bad": bad}, indent=2, sort_keys=True))
    else:
        print(json.dumps(summary, indent=2))
        for row in bad:
            print("BAD\t{chain}\t{method}\t{status}\t{sample}\t{url}".format(**row))
    return 1 if bad or external else 0


if __name__ == "__main__":
    raise SystemExit(main())
