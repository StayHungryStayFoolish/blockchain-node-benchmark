"""CLI bridge — called from bash (target_generator.sh, common_functions.sh)
to access ChainAdapter functionality.

Usage:
    python3 cli.py build-target --chain ethereum --method eth_getBalance \\
        --address 0xabc... --rpc-url http://localhost:8545 \\
        [--param-format address_latest]

    python3 cli.py health-probe --chain ethereum --rpc-url http://localhost:8545

    python3 cli.py family --chain ethereum
"""
from __future__ import annotations
import argparse
import json
import os
import sys

# cli.py lives in tools/chain_adapters/. Add tools/ to sys.path so
# `from chain_adapters import …` resolves as a top-level package.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))           # tools/chain_adapters
_TOOLS_DIR = os.path.dirname(_THIS_DIR)                          # tools
sys.path.insert(0, _TOOLS_DIR)

from chain_adapters import get_adapter  # noqa: E402


def _get_param_format(chain: str, method: str) -> str:
    """Read param_format from chain template params field for given method.

    Falls back to '' (which adapters interpret as default)."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    chain_file = os.path.join(repo_root, "config", "chains", f"{chain}.json")
    if not os.path.exists(chain_file):
        return ""
    with open(chain_file) as f:
        tpl = json.load(f)
    params = tpl.get("params", {})
    if isinstance(params, dict):
        return params.get(method, "")
    return ""


def cmd_build_target(args):
    adapter = get_adapter(args.chain)
    # Honor BLOCKCHAIN_NODE so RestAdapter can resolve _meta.rest_paths
    # --chain is the explicit user intent; ALWAYS override any inherited
    # BLOCKCHAIN_NODE env var (setdefault is wrong here: it lets a stale
    # parent-process value silently hijack the call and route RestAdapter
    # to the wrong chain template — caught in S3-E.2 when test_7 leaked
    # BLOCKCHAIN_NODE=aptos into the test_10 subprocess and all algorand
    # CLI calls then queried aptos's rest_paths).
    os.environ["BLOCKCHAIN_NODE"] = args.chain
    param_format = args.param_format or _get_param_format(args.chain, args.method)
    target = adapter.build_vegeta_target(
        method=args.method,
        address=args.address,
        rpc_url=args.rpc_url,
        param_format=param_format,
    )
    # Vegeta accepts compact JSON, one target per line
    print(json.dumps(target, separators=(",", ":")))


def cmd_build_targets_batch(args):
    """Read tab-separated (method\\taddress) pairs from stdin,
    one per line. Emit one vegeta target JSON per line, in order.

    Hugely faster than calling cli.py per target (Python startup cost
    amortizes across all targets in one process).
    """
    adapter = get_adapter(args.chain)
    os.environ["BLOCKCHAIN_NODE"] = args.chain  # always override; see cmd_build_target
    # Pre-cache param_format per method
    pf_cache: dict[str, str] = {}
    out = sys.stdout
    for line in sys.stdin:
        line = line.rstrip("\n")
        if not line:
            continue
        if "\t" in line:
            method, address = line.split("\t", 1)
        else:
            # Allow space separator as fallback
            parts = line.split(None, 1)
            if len(parts) != 2:
                continue
            method, address = parts
        if method not in pf_cache:
            pf_cache[method] = _get_param_format(args.chain, method)
        target = adapter.build_vegeta_target(
            method=method, address=address,
            rpc_url=args.rpc_url, param_format=pf_cache[method],
        )
        out.write(json.dumps(target, separators=(",", ":")) + "\n")
    out.flush()


def cmd_health_probe(args):
    adapter = get_adapter(args.chain)
    os.environ["BLOCKCHAIN_NODE"] = args.chain  # always override; see cmd_build_target
    req = adapter.health_check_request(args.rpc_url)
    print(json.dumps(req, separators=(",", ":")))


def cmd_family(args):
    adapter = get_adapter(args.chain)
    print(adapter.protocol_family)


def cmd_parse_height(args):
    adapter = get_adapter(args.chain)
    response = sys.stdin.read()
    height = adapter.parse_block_height(response)
    if height is None:
        print("N/A")
        sys.exit(1)
    print(height)


def main():
    ap = argparse.ArgumentParser(prog="chain_adapters.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build-target")
    b.add_argument("--chain", required=True)
    b.add_argument("--method", required=True)
    b.add_argument("--address", required=True)
    b.add_argument("--rpc-url", required=True)
    b.add_argument("--param-format", default="")
    b.set_defaults(func=cmd_build_target)

    bb = sub.add_parser("build-targets-batch",
        help="Read TSV (method\\taddress) from stdin, emit vegeta JSON per line")
    bb.add_argument("--chain", required=True)
    bb.add_argument("--rpc-url", required=True)
    bb.set_defaults(func=cmd_build_targets_batch)

    h = sub.add_parser("health-probe")
    h.add_argument("--chain", required=True)
    h.add_argument("--rpc-url", required=True)
    h.set_defaults(func=cmd_health_probe)

    f = sub.add_parser("family")
    f.add_argument("--chain", required=True)
    f.set_defaults(func=cmd_family)

    ph = sub.add_parser("parse-height", help="Read response JSON from stdin, print height")
    ph.add_argument("--chain", required=True)
    ph.set_defaults(func=cmd_parse_height)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
