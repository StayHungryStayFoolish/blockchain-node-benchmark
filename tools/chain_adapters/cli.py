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


def _build_inputs_and_spec(chain: str, method: str, address: str, param_format_override: str):
    """构建 (inputs, param_spec) 供 build_vegeta_target 新签名(S2)。

    - param_spec: resolve_param_spec(method, chain.param_spec, chain.param_formats) 解析出声明式结构
    - inputs: 批1 过渡 = {"account":[address], "_param_format": fmt(给5family老逻辑过渡键)}
              S1 填齐 tx_hash/block_height/contract_call 多池后, jsonrpc 走构造器,
              过渡键随 5family 切构造器一并删。
    """
    from chain_adapters import param_spec as ps  # noqa
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    chain_file = os.path.join(repo_root, "config", "chains", f"{chain}.json")
    chain_param_spec = None
    chain_param_formats = None
    if os.path.exists(chain_file):
        with open(chain_file) as f:
            tpl = json.load(f)
        chain_param_spec = tpl.get("param_spec")
        chain_param_formats = tpl.get("param_formats")
    # param_format_override(cli --param-format)显式覆盖 template 的 param_formats[method]:
    # 用户临时测某 method 用不同 param_format 时不改 template。非空时直接 expand_preset,
    # 走 R3 fail-fast(无 PRESET 映射则报错, 不静默退化)。空则按 template 解析。
    if param_format_override:
        spec = ps.expand_preset(param_format_override)
        if spec is None:
            raise ps.ParamSpecError(
                f"--param-format {param_format_override!r}: no PARAM_FORMAT_PRESETS mapping. "
                f"(R3: refusing silent fallback)"
            )
    else:
        spec = ps.resolve_param_spec(method, chain_param_spec, chain_param_formats)
    inputs = {"account": [address]}
    return inputs, spec


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
    inputs, spec = _build_inputs_and_spec(args.chain, args.method, args.address, args.param_format)
    target = adapter.build_vegeta_target(
        method=args.method,
        inputs=inputs,
        rpc_url=args.rpc_url,
        param_spec=spec,
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
    # Pre-cache (inputs-template, param_spec) per method — resolve_param_spec once per method
    spec_cache: dict[str, dict] = {}
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
        if method not in spec_cache:
            # param_spec 与 method 一对一(不随 address 变), 缓存; inputs 随 address 每行新建
            _, spec_cache[method] = _build_inputs_and_spec(args.chain, method, address, "")
        spec = spec_cache[method]
        inputs = {"account": [address]}
        target = adapter.build_vegeta_target(
            method=method, inputs=inputs,
            rpc_url=args.rpc_url, param_spec=spec,
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
