#!/usr/bin/env python3
"""Adapter L1 unit tests — per-family unit + cross-family byte equality with bash.

Run directly (repo has no pytest):
    python3 tests/test_chain_adapters.py

Exits non-zero on first failure with descriptive message.
"""
from __future__ import annotations
import base64
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

from chain_adapters import get_adapter, list_adapters


PASS = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"


def _ok(msg: str): print(f"  {PASS} {msg}")
def _fail(msg: str):
    print(f"  {FAIL} {msg}")
    raise AssertionError(msg)


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Factory registration — 6 families
# ─────────────────────────────────────────────────────────────────────────────
def test_factory_registers_six_families():
    print("\n[1] Factory registration")
    fams = list_adapters()
    expected = {"jsonrpc", "rest", "tendermint", "bitcoin_jsonrpc", "substrate", "ogmios"}
    assert set(fams) == expected, f"expected {expected}, got {fams}"
    _ok(f"6 families registered: {sorted(fams)}")


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: All 36 chains resolve to an adapter
# ─────────────────────────────────────────────────────────────────────────────
def test_all_36_chains_resolve():
    print("\n[2] 36 chain templates → adapter resolution")
    chains_dir = REPO / "config" / "chains"
    chain_files = sorted(chains_dir.glob("*.json"))
    assert len(chain_files) == 36, f"expected 36 chains, got {len(chain_files)}"
    for cf in chain_files:
        chain = cf.stem
        try:
            a = get_adapter(chain)
            assert a.protocol_family, f"{chain}: empty protocol_family"
        except Exception as e:
            _fail(f"{chain}: {e}")
    _ok(f"36/36 chains resolve to a registered adapter")


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: JsonRpcAdapter — byte equality with bash for all baseline 8 chains
# ─────────────────────────────────────────────────────────────────────────────
def _bash_old_target(method, address, rpc_url, param_format):
    """Mirror of target_generator.sh generate_rpc_json() L67-124."""
    if param_format == "no_params":
        params = []
    elif param_format == "single_address":
        params = [address]
    elif param_format == "address_latest":
        params = [address, "latest"]
    elif param_format == "latest_address":
        params = ["latest", address]
    elif param_format == "address_storage_latest":
        params = [address, "0x0", "latest"]
    elif param_format == "address_key_latest":
        params = [address, "0x1", "latest"]
    elif param_format == "address_with_options":
        params = [address, {"showType": True, "showContent": True, "showDisplay": False}]
    else:
        params = [address]
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    body_str = json.dumps(body, separators=(",", ":"))
    target = {
        "method": "POST",
        "url": rpc_url,
        "header": {"Content-Type": ["application/json"]},
        "body": base64.b64encode(body_str.encode()).decode(),
    }
    return json.dumps(target, separators=(",", ":"))


def test_baseline_8_vegeta_byte_equality():
    print("\n[3] Baseline 8 chains vegeta target byte-equality (Python adapter vs old bash)")
    baseline = ["ethereum", "bsc", "polygon", "base", "scroll", "solana", "starknet", "sui"]
    test_addr = "0xd8da6bf26964af9d7eed9e03e53415d37aa96045"
    rpc_url = "http://localhost:8545"
    chains_dir = REPO / "config" / "chains"
    total = 0
    for chain in baseline:
        tpl = json.loads((chains_dir / f"{chain}.json").read_text())
        for method, pf in tpl.get("params", {}).items():
            if not isinstance(pf, str):
                continue
            expected = _bash_old_target(method, test_addr, rpc_url, pf)
            r = subprocess.run(
                ["python3", str(REPO / "tools/chain_adapters/cli.py"), "build-target",
                 "--chain", chain, "--method", method,
                 "--address", test_addr, "--rpc-url", rpc_url,
                 "--param-format", pf],
                capture_output=True, text=True)
            actual = r.stdout.strip()
            if actual != expected:
                _fail(f"{chain}/{method}({pf}): mismatch\n      expected: {expected}\n      actual:   {actual}")
            total += 1
    _ok(f"{total} (chain × method) targets all byte-equal old bash path")


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: Each family adapter parse_block_height round-trip
# ─────────────────────────────────────────────────────────────────────────────
def test_parse_block_height_per_family():
    print("\n[4] parse_block_height per family")

    # JsonRpc — EVM 0x-hex
    a = get_adapter("ethereum")
    h = a.parse_block_height(json.dumps({"result": "0x10D4F"}))
    assert h == 0x10D4F == 68943, f"jsonrpc EVM 0x-hex: got {h}"
    _ok("JsonRpcAdapter parses 0x-hex result")

    # JsonRpc — Solana decimal int
    h = a.parse_block_height(json.dumps({"result": "337632288"}))
    assert h == 337632288, f"jsonrpc decimal: got {h}"
    _ok("JsonRpcAdapter parses decimal int result")

    # Tendermint
    a = get_adapter("cosmos-hub")
    h = a.parse_block_height(json.dumps(
        {"result": {"sync_info": {"latest_block_height": "21459123"}}}))
    assert h == 21459123, f"tendermint: got {h}"
    _ok("TendermintAdapter parses sync_info.latest_block_height")

    # Bitcoin
    a = get_adapter("bitcoin")
    h = a.parse_block_height(json.dumps({"result": 870000}))
    assert h == 870000, f"bitcoin: got {h}"
    _ok("BitcoinJsonRpcAdapter parses int result")

    # Substrate
    a = get_adapter("polkadot")
    h = a.parse_block_height(json.dumps({"result": {"number": "0x1A2B3C"}}))
    assert h == 0x1A2B3C, f"substrate: got {h}"
    _ok("SubstrateAdapter parses .result.number 0x-hex")

    # Ogmios
    a = get_adapter("cardano")
    h = a.parse_block_height(json.dumps({"result": {"height": 10500000, "slot": 99}}))
    assert h == 10500000, f"ogmios: got {h}"
    _ok("OgmiosAdapter prefers height over slot")

    # Rest — Tezos with .header.level
    os.environ["BLOCKCHAIN_NODE"] = "tezos"
    a = get_adapter("tezos")
    h = a.parse_block_height(json.dumps({"header": {"level": 8888888}}))
    assert h == 8888888, f"rest tezos: got {h}"
    _ok("RestAdapter parses Tezos .header.level")


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: Health-check requests are well-formed per family
# ─────────────────────────────────────────────────────────────────────────────
def test_health_check_requests():
    print("\n[5] health_check_request shape per family")

    for chain in ["ethereum", "bitcoin", "cosmos-hub", "polkadot", "cardano"]:
        os.environ["BLOCKCHAIN_NODE"] = chain
        a = get_adapter(chain)
        req = a.health_check_request("http://localhost:8545")
        for k in ("method", "url", "headers", "body", "parse_jq"):
            assert k in req, f"{chain}: health request missing {k!r}"
        assert req["method"] in ("GET", "POST")
        assert req["url"]
        _ok(f"{chain:12s} health request well-formed (method={req['method']})")


# ─────────────────────────────────────────────────────────────────────────────
# Test 6: BitcoinJsonRpcAdapter honors auth env vars
# ─────────────────────────────────────────────────────────────────────────────
def test_bitcoin_auth():
    print("\n[6] BitcoinJsonRpcAdapter auth")
    os.environ["BITCOIN_RPC_USER"] = "alice"
    os.environ["BITCOIN_RPC_PASSWORD"] = "secret"
    try:
        a = get_adapter("bitcoin")
        t = a.build_vegeta_target("getblockcount", "addr", "http://localhost:8332", "no_params")
        assert "Authorization" in t["header"], f"missing auth header: {t}"
        expected_auth = "Basic " + base64.b64encode(b"alice:secret").decode()
        assert t["header"]["Authorization"][0] == expected_auth
        _ok("Bitcoin adapter injects Authorization: Basic header")
    finally:
        del os.environ["BITCOIN_RPC_USER"]
        del os.environ["BITCOIN_RPC_PASSWORD"]

    # Without auth env, no Authorization header
    a = get_adapter("bitcoin")
    t = a.build_vegeta_target("getblockcount", "addr", "http://localhost:8332", "no_params")
    assert "Authorization" not in t["header"], f"unexpected auth header: {t}"
    _ok("Bitcoin adapter omits Authorization when no env set")


# ─────────────────────────────────────────────────────────────────────────────
# Test 7: REST adapter requires BLOCKCHAIN_NODE env
# ─────────────────────────────────────────────────────────────────────────────
def test_rest_requires_env_and_path_map():
    print("\n[7] RestAdapter requires BLOCKCHAIN_NODE + _meta.rest_paths")
    os.environ.pop("BLOCKCHAIN_NODE", None)
    a = get_adapter("aptos")
    try:
        a.build_vegeta_target("GET_ACCOUNT", "0xabc", "http://localhost:8080", "")
        _fail("expected RuntimeError without BLOCKCHAIN_NODE")
    except RuntimeError as e:
        _ok(f"RuntimeError correctly raised: {e}")

    # With env set but no rest_paths in template, expect ValueError
    os.environ["BLOCKCHAIN_NODE"] = "aptos"
    try:
        a = get_adapter("aptos")
        a.build_vegeta_target("nonexistent_method", "0xabc", "http://localhost:8080", "")
        _fail("expected ValueError for unknown method")
    except ValueError as e:
        _ok(f"ValueError correctly raised for unknown method: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Test 8 (S3-A): JsonRpc new formats — block_number / block_number_int /
#                transaction_hash / eth_call_object_latest / object_single
# ─────────────────────────────────────────────────────────────────────────────
def test_jsonrpc_s3a_new_formats():
    print("\n[8] JsonRpc S3-A new formats (5 EVM-compat chains)")
    a = get_adapter("arbitrum")  # any jsonrpc chain works
    url = "http://x"

    # block_number → ["latest", false]
    t = a.build_vegeta_target("eth_getBlockByNumber", "0xabc", url, "block_number")
    body = json.loads(base64.b64decode(t["body"]))
    assert body["params"] == ["latest", False], f"block_number wrong: {body['params']}"
    _ok(f"block_number → {body['params']}")

    # block_number_int → [<int>]
    t = a.build_vegeta_target("zks_getBlockDetails", "60100000", url, "block_number_int")
    body = json.loads(base64.b64decode(t["body"]))
    assert body["params"] == [60100000], f"block_number_int wrong: {body['params']}"
    _ok(f"block_number_int (int address) → {body['params']}")
    # fallback when address not int-parseable
    t = a.build_vegeta_target("zks_getBlockDetails", "not_an_int", url, "block_number_int")
    body = json.loads(base64.b64decode(t["body"]))
    assert body["params"] == [1], f"block_number_int fallback wrong: {body['params']}"
    _ok(f"block_number_int (bad address) → fallback {body['params']}")

    # transaction_hash → [<tx_hash>]
    # with valid 0x + 64-hex address-as-hash:
    fake_hash = "0x" + "ab" * 32
    t = a.build_vegeta_target("eth_getTransactionReceipt", fake_hash, url, "transaction_hash")
    body = json.loads(base64.b64decode(t["body"]))
    assert body["params"] == [fake_hash], f"transaction_hash wrong: {body['params']}"
    _ok(f"transaction_hash (valid) → {body['params'][0][:18]}...")
    # fallback when address is not a tx hash shape:
    t = a.build_vegeta_target("eth_getTransactionReceipt", "0xshort", url, "transaction_hash")
    body = json.loads(base64.b64decode(t["body"]))
    assert body["params"] == ["0x" + "0" * 64], f"transaction_hash fallback wrong: {body['params']}"
    _ok(f"transaction_hash (short addr) → fallback {body['params'][0][:18]}...")

    # eth_call_object_latest → [{to, data}, "latest"]
    t = a.build_vegeta_target("eth_call", "0xc0ffee", url, "eth_call_object_latest")
    body = json.loads(base64.b64decode(t["body"]))
    assert body["params"][1] == "latest", f"eth_call missing latest: {body['params']}"
    assert body["params"][0]["to"] == "0xc0ffee", f"eth_call to wrong: {body['params']}"
    assert body["params"][0]["data"].startswith("0x70a08231"), f"data missing balanceOf selector: {body['params']}"
    _ok(f"eth_call_object_latest → [{{to,data}}, latest]")

    # object_single → [{from, to, value}]
    t = a.build_vegeta_target("linea_estimateGas", "0xc0ffee", url, "object_single")
    body = json.loads(base64.b64decode(t["body"]))
    assert isinstance(body["params"], list) and len(body["params"]) == 1
    assert body["params"][0]["from"] == "0xc0ffee"
    assert body["params"][0]["value"] == "0x1"
    _ok(f"object_single → [{{from,to,value}}] single-elem list")


# ─────────────────────────────────────────────────────────────────────────────
# Test 9 (S3-A): 5 EVM-compat chains have only standard-enum param_formats
# ─────────────────────────────────────────────────────────────────────────────
def test_evm_compat_5chains_standard_enum():
    print("\n[9] EVM-compat 5 chains: param_formats ⊂ adapter standard enum")
    STANDARD = {
        "no_params", "single_address", "address_latest", "latest_address",
        "address_storage_latest", "address_key_latest", "address_with_options",
        "block_number", "block_number_int", "transaction_hash",
        "eth_call_object_latest", "object_single",
    }
    EVM_COMPAT = ["arbitrum", "optimism", "zksync-era", "linea", "avalanche-c"]
    for chain in EVM_COMPAT:
        p = REPO / "config" / "chains" / f"{chain}.json"
        data = json.loads(p.read_text())
        pf = data.get("param_formats", {})
        bad = {m: f for m, f in pf.items() if f not in STANDARD}
        if bad:
            _fail(f"{chain} has nonstandard formats: {bad}")
        _ok(f"{chain}: {len(pf)} formats all standard")


# ─────────────────────────────────────────────────────────────────────────────
# Test 10: L1-CLI end-to-end — every chain must produce a valid vegeta target
# via the real production entrypoint (tools/chain_adapters/cli.py build-target),
# which is the only path called by target_generator.sh -> master_qps_executor.sh.
#
# Two assertions per chain:
#   (a) cli.py exits 0
#   (b) decoded body contains the supplied address
#
# KNOWN_BROKEN: chains where the CURRENT state is broken at the CLI entrypoint
# (commit 436e1d0 baseline, 2026-05-24 audit). Each entry MUST cite its
# failure-mode bucket (F1/F2/F3/F4) so the responsible S3 wave knows what to fix.
#
# Invariant: KNOWN_BROKEN must shrink monotonically. New chains may not be added
# without explicit user decision. Each S3-B/C/D/E/F wave is required to remove
# at least the entries assigned to it (see "Fix wave" column below).
# ─────────────────────────────────────────────────────────────────────────────

# (chain, expected_failure_mode, fix_wave_owner, reason)
KNOWN_BROKEN_CLI = {
    # F1: rpc_methods.single picked a health-probe (no address) instead of
    #     a real benchmark method. Fix = pick a method from param_formats
    #     that takes an address. Pure chain-template edit, no adapter work.
    "algorand":  ("F1", "S3-E", "single='GET /v2/status' is health-probe; use 'GET /v2/accounts/{address}'"),
    "hedera":    ("F1", "S3-E", "single='mirror_account_query' is logical name, no real path; use 'mirror_balance_query' or 'eth_getBalance'"),
    "tezos":     ("F1", "S3-E", "single='GET /chains/main/blocks/head/header' has no address; use '/contracts/{addr}/balance'"),
    "ton":       ("F1", "S3-E", "single='getMasterchainInfo' is health-probe; use 'getAddressBalance'"),
    "kusama":    ("F1", "S3-C", "single='chain_getHeader' has no address; use 'system_account' or similar"),
    "polkadot":  ("F1", "S3-C", "single='chain_getHeader' has no address; mixed_first 'GET /accounts/{addr}/balance-info' is correct shape"),

    # F2: chain template uses REST paths in rpc_methods.single but
    #     family=tendermint goes through jsonrpc.py generic builder which
    #     wraps everything in {jsonrpc:"2.0", method:"<path>", params:{}}.
    #     Fix = adapter dispatch (tendermint must do HTTP GET <path>, not POST JSON).
    "celestia":   ("F2", "S3-B", "REST path '/status' wrapped as jsonrpc body; tendermint adapter must HTTP GET"),
    "injective":  ("F2", "S3-B", "REST path '/status' wrapped as jsonrpc body"),
    "osmosis":    ("F2", "S3-B", "REST path '/status' wrapped as jsonrpc body"),
    "cosmos-hub": ("F2", "S3-B", "REST path wrapped as jsonrpc body"),
    "cardano":    ("F2", "S3-F", "ogmios family wraps 'GET /tip' as jsonrpc body; ogmios adapter is WebSocket JSON-RPC, different protocol"),

    # F3: family=substrate but chain runs EVM via Frontier pallet. mixed_first
    #     is eth_chainId (no address). Fix = decide family (substrate vs jsonrpc)
    #     and pick benchmark method with address (eth_getBalance).
    "astar":     ("F3", "S3-C", "family=substrate but Astar runs EVM via Frontier; single='eth_chainId' has no address"),
    "moonbeam":  ("F3", "S3-C", "family=substrate but Moonbeam runs EVM via Frontier; single='eth_chainId' has no address"),
    "sei":       ("F3", "S3-B", "family=tendermint with EVM compat layer; single='eth_chainId' has no address"),
    "acala":     ("F3", "S3-C", "family=substrate; single='system_chain' has no address; pick eth_getBalance from param_formats"),
}

assert len(KNOWN_BROKEN_CLI) == 15, f"KNOWN_BROKEN_CLI must have exactly 15 entries (commit 436e1d0 baseline minus aptos fixed in S3-E.1), got {len(KNOWN_BROKEN_CLI)}"


def _sample_address_for(family: str) -> str:
    """Return a family-appropriate sample address for the build-target probe.

    Adapters either echo the address verbatim into the body (so any string works
    for the L1 assertion) or template it into a URL path (REST {address}/{addr}).
    These canonical samples are recognizable in decoded bodies.
    """
    return {
        "jsonrpc":         "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "bitcoin_jsonrpc": "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
        "substrate":       "12bzRJfh7arnnfPPUZHeJUaE62QLEwhK48QnH9LXeK2m1iZU",
        "tendermint":      "cosmos1abc",
        "ogmios":          "addr1q9adlx6mh0dr8xs0gpcm9nz5pqe5w2hzfx5l8qj5",
        "rest":            "TESTADDR123",
    }.get(family, "TESTADDR123")


def test_cli_build_target_all_36_chains():
    """L1-CLI: every chain produces a valid vegeta target via cli.py with address.

    Real production path: target_generator.sh:74 invokes this exact cli.py
    incantation. If this test passes, the CLI path is healthy; L1 PASS via
    direct adapter calls (test_3 / test_8 etc.) is NOT sufficient because
    cli.py adds an additional layer of plumbing (param_format lookup from
    chain template, BLOCKCHAIN_NODE env, sys.path manipulation).
    """
    print("\n[10] CLI build-target end-to-end for all 36 chains (real production path)")
    chains_dir = REPO / "config" / "chains"
    cli_py = REPO / "tools" / "chain_adapters" / "cli.py"

    expected_broken = set(KNOWN_BROKEN_CLI.keys())
    actually_broken: set[str] = set()
    healthy: list[str] = []

    for cf in sorted(chains_dir.glob("*.json")):
        chain = cf.stem
        tpl = json.loads(cf.read_text())
        family = tpl.get("_meta", {}).get("adapter_family", "")
        single_method = (tpl.get("rpc_methods") or {}).get("single")
        if not single_method:
            actually_broken.add(chain)
            continue

        addr = _sample_address_for(family)
        r = subprocess.run(
            ["python3", str(cli_py), "build-target",
             "--chain", chain, "--method", single_method,
             "--address", addr, "--rpc-url", "http://localhost:8545"],
            capture_output=True, text=True, timeout=10,
        )

        # Gate 1: exit code
        if r.returncode != 0:
            actually_broken.add(chain)
            continue
        # Gate 2: body is valid JSON (body is optional for GET requests)
        try:
            tgt = json.loads(r.stdout)
            body_b64 = tgt.get("body", "")
            body = base64.b64decode(body_b64).decode("utf-8", errors="replace") if body_b64 else ""
        except Exception:
            actually_broken.add(chain)
            continue
        # Gate 3: body or URL contains the address we passed
        url = tgt.get("url", "")
        if addr not in body and addr not in url:
            actually_broken.add(chain)
            continue

        healthy.append(chain)

    # Invariant check: actually_broken must be a SUBSET of expected_broken
    # (broken set may only shrink, never grow). New chains added to the
    # framework must either pass cleanly or be explicitly added to
    # KNOWN_BROKEN_CLI with a fix-wave owner.
    unexpected_new_broken = actually_broken - expected_broken
    unexpectedly_healthy = expected_broken - actually_broken

    print(f"  Healthy: {len(healthy)}/36 chains")
    print(f"  KNOWN_BROKEN (must shrink, never grow): {len(expected_broken)}")
    print(f"  Actually broken now: {len(actually_broken)}")

    if unexpected_new_broken:
        _fail(
            f"REGRESSION — new chains broken at CLI entrypoint that were "
            f"NOT in KNOWN_BROKEN_CLI: {sorted(unexpected_new_broken)}. "
            f"Either fix them or add to KNOWN_BROKEN_CLI with explicit "
            f"fix-wave assignment (F1/F2/F3/F4 + S3-B/C/D/E/F owner)."
        )

    if unexpectedly_healthy:
        # This is GOOD news — chain got fixed. But the test must enforce the
        # KNOWN_BROKEN list is current, so author must remove the entry.
        _fail(
            f"PROGRESS — these chains are now healthy and must be REMOVED "
            f"from KNOWN_BROKEN_CLI: {sorted(unexpectedly_healthy)}. "
            f"Edit tests/test_chain_adapters.py KNOWN_BROKEN_CLI dict."
        )

    _ok(f"{len(healthy)}/36 healthy + {len(actually_broken)} known-broken (set matches expected)")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    tests = [
        test_factory_registers_six_families,
        test_all_36_chains_resolve,
        test_baseline_8_vegeta_byte_equality,
        test_parse_block_height_per_family,
        test_health_check_requests,
        test_bitcoin_auth,
        test_rest_requires_env_and_path_map,
        test_jsonrpc_s3a_new_formats,
        test_evm_compat_5chains_standard_enum,
        test_cli_build_target_all_36_chains,
    ]
    print(f"Running {len(tests)} test groups for chain_adapters")
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"\n{FAIL} TEST FAILED: {t.__name__}")
            print(f"   {e}")
            sys.exit(1)
        except Exception as e:
            print(f"\n{FAIL} TEST ERROR: {t.__name__}: {type(e).__name__}: {e}")
            import traceback; traceback.print_exc()
            sys.exit(2)
    print(f"\n{PASS} ALL TESTS PASSED ({len(tests)} groups)")


if __name__ == "__main__":
    main()
