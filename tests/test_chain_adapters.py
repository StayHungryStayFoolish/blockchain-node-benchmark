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
    expected = {"jsonrpc", "rest", "tendermint", "bitcoin_jsonrpc", "substrate", "ogmios", "tron"}
    assert set(fams) == expected, f"expected {expected}, got {fams}"
    _ok(f"7 families registered: {sorted(fams)}")


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
# Test 10: TronAdapter — dual-protocol shapes
# ─────────────────────────────────────────────────────────────────────────────
def test_tron_adapter_shapes():
    print("\n[10] TronAdapter: HTTP /wallet/* + JSON-RPC /jsonrpc subset")
    import base64
    a = get_adapter("tron")
    assert a.protocol_family == "tron", f"expected 'tron', got {a.protocol_family!r}"

    BASE = "http://localhost:8545"
    ADDR = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"  # base58 tron address

    # 10a: /wallet/getnowblock → empty body
    t = a.build_vegeta_target("/wallet/getnowblock", ADDR, BASE, "no_params")
    assert t["method"] == "POST"
    assert t["url"] == "http://localhost:8545/wallet/getnowblock", f"bad url: {t['url']}"
    body = json.loads(base64.b64decode(t["body"]))
    assert body == {}, f"expected empty body, got {body}"
    _ok(f"/wallet/getnowblock → POST {t['url']} body={{}}")

    # 10b: /wallet/getaccount → {address, visible}
    t = a.build_vegeta_target("/wallet/getaccount", ADDR, BASE, "body_address_visible")
    body = json.loads(base64.b64decode(t["body"]))
    assert body == {"address": ADDR, "visible": True}, f"bad body: {body}"
    _ok(f"/wallet/getaccount → body={{address: {ADDR[:10]}..., visible: True}}")

    # 10c: /wallet/gettransactionbyid → {value: txid_no_0x}
    txid = "0xabc123" + "0" * 58
    t = a.build_vegeta_target("/wallet/gettransactionbyid", txid, BASE, "body_value_txid_nopfx")
    body = json.loads(base64.b64decode(t["body"]))
    assert body["value"] == "abc123" + "0" * 58, f"expected stripped 0x: {body}"
    _ok(f"/wallet/gettransactionbyid → body.value 0x-stripped")

    # 10d: /wallet/triggerconstantcontract → 5-field body
    t = a.build_vegeta_target(
        "/wallet/triggerconstantcontract", ADDR, BASE,
        "body_owner_contract_selector_parameter",
    )
    body = json.loads(base64.b64decode(t["body"]))
    assert body["function_selector"] == "balanceOf(address)", f"bad selector: {body.get('function_selector')}"
    assert body["owner_address"] == ADDR
    assert len(body["parameter"]) == 64, f"parameter must be 32-byte hex, got len={len(body['parameter'])}"
    _ok(f"/wallet/triggerconstantcontract → 5-field body with balanceOf selector")

    # 10e: JSON-RPC subset routes to /jsonrpc path
    t = a.build_vegeta_target("eth_blockNumber", ADDR, BASE, "no_params")
    assert t["url"] == "http://localhost:8545/jsonrpc", f"jsonrpc path mismatch: {t['url']}"
    body = json.loads(base64.b64decode(t["body"]))
    assert body["method"] == "eth_blockNumber"
    assert body["params"] == []
    _ok(f"eth_blockNumber → POST /jsonrpc with JSON-RPC envelope")

    # 10f: parse_block_height — Tron getnowblock response
    sample = json.dumps({
        "blockID": "0" * 64,
        "block_header": {"raw_data": {"number": 60100000, "timestamp": 1735200000000}},
    })
    h = a.parse_block_height(sample)
    assert h == 60100000, f"expected 60100000, got {h}"
    _ok(f"parse_block_height Tron envelope → 60100000")

    # 10g: parse_block_height — JSON-RPC fallback
    rpc_sample = json.dumps({"jsonrpc": "2.0", "id": 1, "result": "0x3947ea0"})
    h = a.parse_block_height(rpc_sample)
    assert h == 0x3947ea0, f"expected {0x3947ea0}, got {h}"
    _ok(f"parse_block_height JSON-RPC fallback → {0x3947ea0}")

    # 10h: health_check_request shape
    hc = a.health_check_request(BASE)
    assert hc["method"] == "POST"
    assert hc["url"] == BASE + "/wallet/getnowblock"
    assert hc["body"] == "{}"
    assert hc["parse_jq"] == ".block_header.raw_data.number"
    _ok(f"health_check → POST /wallet/getnowblock + parse_jq")

    # 10i: unknown method shape → raises
    try:
        a.build_vegeta_target("foo_bar", ADDR, BASE, "")
        _fail("expected ValueError for unknown method")
    except ValueError as e:
        _ok(f"unknown method raises ValueError: {str(e)[:60]}")


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
        test_tron_adapter_shapes,
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
