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
# Test 1: Factory registration — 6 families (ADR-0005: ogmios removed)
# ─────────────────────────────────────────────────────────────────────────────
def test_factory_registers_seven_families():
    print("\n[1] Factory registration")
    fams = list_adapters()
    expected = {"jsonrpc", "rest", "tendermint", "bitcoin_jsonrpc", "substrate", "hedera_dual"}
    assert set(fams) == expected, f"expected {expected}, got {fams}"
    _ok(f"6 families registered (ADR-0005: ogmios removed): {sorted(fams)}")


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
        # Read from param_formats (method→format map) — was reading from
        # tpl["params"] (fetcher config) pre-cli-param-bug fix; that path
        # tested nothing because both _bash_old_target and JsonRpcAdapter
        # fell back to [address] for unknown "param_formats" like
        # "ACCOUNT_COUNT", trivially byte-equal but not real-method coverage.
        for method, pf in tpl.get("param_formats", {}).items():
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
    # Guard against the bug where total=0 because field name is wrong
    assert total >= 8 * 2, f"too few methods tested ({total}); param_formats field name likely wrong"
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

    # Ogmios family was removed in ADR-0005 (2026-05-28) — cardano now uses
    # rest family (Koios REST). The block height path is now exercised below
    # via RestAdapter on cardano with the Koios /tip response shape (block_no).
    os.environ["BLOCKCHAIN_NODE"] = "cardano"
    a = get_adapter("cardano")
    h = a.parse_block_height(json.dumps([{"block_no": 10500000, "abs_slot": 99}]))
    assert h == 10500000, f"cardano (rest via Koios /tip): got {h}"
    _ok("RestAdapter parses Cardano Koios /tip .[0].block_no (ADR-0005)")

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
        t = a.build_vegeta_target("getblockcount", {"account": ["addr"], "_param_format": "no_params"}, "http://localhost:8332", {"transport": "jsonrpc_list", "slots": []})
        assert "Authorization" in t["header"], f"missing auth header: {t}"
        expected_auth = "Basic " + base64.b64encode(b"alice:secret").decode()
        assert t["header"]["Authorization"][0] == expected_auth
        _ok("Bitcoin adapter injects Authorization: Basic header")
    finally:
        del os.environ["BITCOIN_RPC_USER"]
        del os.environ["BITCOIN_RPC_PASSWORD"]

    # Without auth env, no Authorization header
    a = get_adapter("bitcoin")
    t = a.build_vegeta_target("getblockcount", {"account": ["addr"], "_param_format": "no_params"}, "http://localhost:8332", {"transport": "jsonrpc_list", "slots": []})
    assert "Authorization" not in t["header"], f"unexpected auth header: {t}"
    _ok("Bitcoin adapter omits Authorization when no env set")


# ─────────────────────────────────────────────────────────────────────────────
# Test 7: REST adapter requires BLOCKCHAIN_NODE env
# ─────────────────────────────────────────────────────────────────────────────
def test_rest_requires_env_and_path_map():
    print("\n[7] RestAdapter requires BLOCKCHAIN_NODE + _meta.rest_paths")
    # Save original to restore at end — otherwise leaks into test_10's
    # subprocess env and silently hijacks RestAdapter chain resolution.
    _saved_env = os.environ.get("BLOCKCHAIN_NODE")
    try:
        os.environ.pop("BLOCKCHAIN_NODE", None)
        a = get_adapter("aptos")
        try:
            a.build_vegeta_target("GET_ACCOUNT", {"account": ["0xabc"]}, "http://localhost:8080", {"transport": "rest_path", "path": "/x"})
            _fail("expected RuntimeError without BLOCKCHAIN_NODE")
        except RuntimeError as e:
            _ok(f"RuntimeError correctly raised: {e}")

        # With env set but no rest_paths in template, expect ValueError
        os.environ["BLOCKCHAIN_NODE"] = "aptos"
        try:
            a = get_adapter("aptos")
            a.build_vegeta_target("nonexistent_method", {"account": ["0xabc"]}, "http://localhost:8080", {"transport": "rest_path", "path": "/x"})
            _fail("expected ValueError for unknown method")
        except ValueError as e:
            _ok(f"ValueError correctly raised for unknown method: {e}")
    finally:
        # Restore original env state (or remove if it wasn't set)
        if _saved_env is None:
            os.environ.pop("BLOCKCHAIN_NODE", None)
        else:
            os.environ["BLOCKCHAIN_NODE"] = _saved_env


# ─────────────────────────────────────────────────────────────────────────────
# Test 8 (S3-A): JsonRpc new formats — block_number / block_number_int /
#                transaction_hash / eth_call_object_latest / object_single
# ─────────────────────────────────────────────────────────────────────────────
def test_jsonrpc_s3a_new_formats():
    print("\n[8] JsonRpc S2 新构造器 (param_spec + inputs 多池, 废除旧 address 占位)")
    a = get_adapter("arbitrum")  # any jsonrpc chain works
    url = "http://x"
    from chain_adapters.param_spec import expand_preset, build_params_from_spec

    def _build(fmt, inputs):
        """用 PRESET 展开 spec + 真值池 inputs 调新构造器(模拟 cli 层 resolve+build)。"""
        spec = expand_preset(fmt)
        return a.build_vegeta_target("m", inputs, url, spec)

    # block_number → ["latest", false] (literal, 不依赖输入池)
    t = _build("block_number", {"account": ["0xabc"]})
    body = json.loads(base64.b64decode(t["body"]))
    assert body["params"] == ["latest", False], f"block_number wrong: {body['params']}"
    _ok(f"block_number → {body['params']}")

    # block_number_int → [<int>] 从 block_height 池取(S2: 不再 int(address), 从真值池)
    t = _build("block_number_int", {"block_height": [60100000]})
    body = json.loads(base64.b64decode(t["body"]))
    assert body["params"] == [60100000], f"block_number_int wrong: {body['params']}"
    _ok(f"block_number_int (从 block_height 池) → {body['params']}")
    # 池空 → fail-fast(S2 废除占位兜底, R3)
    from chain_adapters.param_spec import ParamSpecError
    try:
        _build("block_number_int", {"account": ["0xabc"]})  # 缺 block_height 池
        _fail("block_number_int 池空应 fail-fast")
    except ParamSpecError as e:
        _ok(f"block_number_int 池空 → fail-fast(非占位): {str(e)[:40]}")

    # transaction_hash → [<tx_hash>] 从 tx_hash 池取(S2: 不再用 address 占位)
    real_hash = "0x" + "ab" * 32
    t = _build("transaction_hash", {"tx_hash": [real_hash]})
    body = json.loads(base64.b64decode(t["body"]))
    assert body["params"] == [real_hash], f"transaction_hash wrong: {body['params']}"
    _ok(f"transaction_hash (从 tx_hash 池) → {body['params'][0][:18]}...")
    # 池空 → fail-fast
    try:
        _build("transaction_hash", {"account": ["0xabc"]})  # 缺 tx_hash 池
        _fail("transaction_hash 池空应 fail-fast")
    except ParamSpecError as e:
        _ok(f"transaction_hash 池空 → fail-fast(非占位): {str(e)[:40]}")

    # eth_call_object_latest → [{to, data}, "latest"] (contract_call, evm_call shape)
    t = _build("eth_call_object_latest", {"account": ["0xc0ffee"]})
    body = json.loads(base64.b64decode(t["body"]))
    assert body["params"][1] == "latest", f"eth_call missing latest: {body['params']}"
    assert body["params"][0]["to"] == "0xc0ffee", f"eth_call to wrong: {body['params']}"
    assert body["params"][0]["data"].startswith("0x70a08231"), f"data missing balanceOf selector: {body['params']}"
    _ok("eth_call_object_latest → [{to,data}, latest] (evm_call)")

    # object_single → [{to, data}] (contract_call evm_call shape, 单元素 list)
    t = _build("object_single", {"account": ["0xc0ffee"]})
    body = json.loads(base64.b64decode(t["body"]))
    assert isinstance(body["params"], list) and len(body["params"]) == 1
    assert body["params"][0]["to"] == "0xc0ffee"
    assert body["params"][0]["data"].startswith("0x70a08231")
    _ok("object_single → [{to,data}] 单元素 list (evm_call)")


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
    # ─────────────────────────────────────────────────────────────────────
    # 批3 完整完成(2026-06-05): 36/36 链 build-target healthy。
    # tron(混协议 /wallet REST + eth_ jsonrpc)复用 hedera_dual 通用 dual 路由
    # (family=hedera_dual: _is_jsonrpc_method 分派, /wallet→rest_body, eth_→jsonrpc;
    #  补 /wallet body PRESET + rest_post_empty)→ 转 healthy。
    # KNOWN_BROKEN_CLI 清空(批1+2 的 12 → 批3b 1 → 批3完成 0, must shrink 达成)。
    # ─────────────────────────────────────────────────────────────────────
}

assert len(KNOWN_BROKEN_CLI) == 0, (
    f"KNOWN_BROKEN_CLI 应为 0 条(批3 完整完成, 36/36 链 build-target healthy)。"
    f"got {len(KNOWN_BROKEN_CLI)}"
)


# ─────────────────────────────────────────────────────────────────────────────
# KNOWN_BROKEN_MIXED — chains whose `single` benchmark passes L1-CLI test_10
# but whose `mixed` (multi-method) path is broken in production (live HTTP
# would 4xx/5xx). Documented here for honesty; not auto-asserted because we
# don't yet have a `mixed` equivalent of test_10. When a future wave adds a
# mixed-path test, this dict graduates to enforced invariant.
#
# Format: (chain, failure_layer, fix_wave, evidence)
#   failure_layer:
#     PARAM     — cli.py reads tpl['params'] (fetcher config) when it should
#                 read tpl['param_formats'] (method→shape). Affects all
#                 JSON-RPC chains' eth_* calls (missing 'latest'). Fix wave: cli-param-bug
#     ADDR_FMT  — fetch_active_accounts.py doesn't know chain-specific address
#                 transformations (hedera 3-part 0.0.N → EVM 0x...0N).
#                 Fix wave: S4 (per-chain account fetcher)
# ─────────────────────────────────────────────────────────────────────────────
KNOWN_BROKEN_MIXED = {
    "hedera": (
        "PARAM+ADDR_FMT", "cli-param-bug + S4",
        "S3-E.3 C1 实证:adapter routing 正确 (test_11 PASS),但 (1) cli.py L40 "
        "读 tpl['params'] 应读 tpl['param_formats'] → eth_getBalance 缺 'latest'; "
        "(2) fetch_active_accounts.py 不支持 hedera → 喂 3-part ID 0.0.N 给 Hashio "
        "返 HTTP 400 'Expected 0x prefixed string representing the address (20 bytes)'. "
        "需 fetcher 拿 mirror /accounts/{id} 的 evm_address 字段。"
        " [PARAM resolved in cli-param-bug commit e3ae757; ADDR_FMT still blocking, S4]"
    ),
    "tezos": (
        "MULTI_PLACEHOLDER", "S4 (RestAdapter v2)",
        "S3-E.4 2026-05-25: single (balance) works in single mode L1+L3 PASS, "
        "but mixed mode method 'GET /chains/main/blocks/{block}/operations/{vp}' "
        "needs both {block} and {vp} (validation_pass int 0-3) placeholders. "
        "RestAdapter v1 only supports single {address} placeholder. Fix requires "
        "either RestAdapter v2 with named multi-placeholder template, OR a "
        "two-step adapter (query operation_hashes → iterate (block, vp, index))."
        " 4 of 5 methods in mixed are no-placeholder or single-{addr} so they "
        "are not blocked; only operations method is."
    ),
}


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
        # ogmios removed in ADR-0005 (cardano migrated to rest family)
        "rest":            "TESTADDR123",
        # hedera_dual: native 3-part account ID; L1 only asserts the address
        # string appears in url-or-body, not EVM semantics. Production
        # fetch_active_accounts must convert 0.0.N → EVM 0x...0N for eth_*
        # routes — out of scope for L1.
        "hedera_dual":     "0.0.2",
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
        # Gate 4: single_method must be EXPLICITLY declared in chain template
        # (param_formats for JSON-RPC families, _meta.rest_paths for REST).
        # Otherwise cli.py falls back to "single_address" and silently injects
        # the address into a method that semantically takes no address
        # (e.g. cardano `GET /tip`, acala `system_chain`). The vegeta target
        # generates fine but the real node returns -32602 / 404 / empty.
        # Discovered during cli-param-bug wave (2026-05-25): default
        # fallback "single_address" was masking 11 F1/F2/F3 broken chains.
        param_formats = tpl.get("param_formats") or {}
        rest_paths = (tpl.get("_meta") or {}).get("rest_paths") or []
        method_declared = (
            single_method in param_formats
            or single_method in rest_paths
        )
        if not method_declared:
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
# Test 11: HederaDualAdapter — per-request protocol routing
# ─────────────────────────────────────────────────────────────────────────────
def test_hedera_dual_adapter_routing():
    print("\n[11] HederaDualAdapter per-method protocol routing")
    import base64 as _b64
    import json as _json
    from chain_adapters.hedera_dual import HederaDualAdapter, _is_jsonrpc_method

    _saved = os.environ.get("BLOCKCHAIN_NODE")
    os.environ["BLOCKCHAIN_NODE"] = "hedera"
    try:
        a = HederaDualAdapter()
        mirror_url = "https://mainnet-public.mirrornode.hedera.com"
        # REST path-style method → GET against passed rpc_url
        tgt = a.build_vegeta_target(
            method="GET /api/v1/accounts/{addr}",
            inputs={"account": ["0.0.2"]}, rpc_url=mirror_url,
            param_spec={"transport": "rest_path", "path": "/api/v1/accounts/{addr}"},
        )
        assert tgt["method"] == "GET", f"REST should be GET, got {tgt['method']}"
        assert tgt["url"] == f"{mirror_url}/api/v1/accounts/0.0.2", f"got {tgt['url']}"
        assert "body" not in tgt or not tgt.get("body"), "GET should have no body"
        _ok("REST method → GET Mirror URL with address in path")

        # JSON-RPC method → POST against _meta.json_rpc_url, NOT rpc_url
        tgt = a.build_vegeta_target(
            method="eth_blockNumber", inputs={"account": [""]},
            rpc_url=mirror_url, param_spec={"transport": "jsonrpc_list", "slots": []},
        )
        assert tgt["method"] == "POST", f"JSON-RPC should be POST, got {tgt['method']}"
        assert tgt["url"] == "https://mainnet.hashio.io/api", \
            f"JSON-RPC URL should come from _meta.json_rpc_url, got {tgt['url']}"
        body = _json.loads(_b64.b64decode(tgt["body"]).decode())
        assert body["method"] == "eth_blockNumber"
        assert body["params"] == []
        _ok("eth_blockNumber → POST Hashio with empty params")

        # eth_getBalance routing → POST with [addr, "latest"] (address_latest spec)
        tgt = a.build_vegeta_target(
            method="eth_getBalance",
            inputs={"account": ["0x0000000000000000000000000000000000000002"]},
            rpc_url=mirror_url,
            param_spec={"transport": "jsonrpc_list", "slots": [{"source": "account"}, {"source": "literal", "value": "latest"}]},
        )
        assert tgt["url"] == "https://mainnet.hashio.io/api"
        body = _json.loads(_b64.b64decode(tgt["body"]).decode())
        assert body["params"] == ["0x0000000000000000000000000000000000000002", "latest"], \
            f"params should be [addr, 'latest'], got {body['params']}"
        _ok("eth_getBalance routes to Hashio with [addr, latest] payload")

        # Missing _meta.json_rpc_url → ValueError (defensive check)
        # We test by temporarily mutating the cached chain dict
        a2 = HederaDualAdapter()
        a2._load_chain("hedera")  # populate cache
        original = a2._chain_cache["hedera"]["_meta"].pop("json_rpc_url")
        try:
            try:
                a2.build_vegeta_target(method="eth_blockNumber", inputs={"account": [""]},
                                       rpc_url=mirror_url, param_spec={"transport": "jsonrpc_list", "slots": []})
                assert False, "should have raised ValueError when json_rpc_url missing"
            except ValueError as e:
                assert "json_rpc_url" in str(e), f"error msg should mention json_rpc_url: {e}"
            _ok("Missing _meta.json_rpc_url raises ValueError")
        finally:
            a2._chain_cache["hedera"]["_meta"]["json_rpc_url"] = original

        # Missing BLOCKCHAIN_NODE → RuntimeError
        del os.environ["BLOCKCHAIN_NODE"]
        try:
            a.build_vegeta_target(method="eth_blockNumber", inputs={"account": [""]},
                                  rpc_url=mirror_url, param_spec={"transport": "jsonrpc_list", "slots": []})
            assert False, "should have raised RuntimeError when BLOCKCHAIN_NODE missing"
        except RuntimeError as e:
            assert "BLOCKCHAIN_NODE" in str(e)
        _ok("Missing BLOCKCHAIN_NODE raises RuntimeError")
    finally:
        if _saved is None:
            os.environ.pop("BLOCKCHAIN_NODE", None)
        else:
            os.environ["BLOCKCHAIN_NODE"] = _saved


# ─────────────────────────────────────────────────────────────────────────────
# Test 12: _is_jsonrpc_method regex boundary
# ─────────────────────────────────────────────────────────────────────────────
def test_is_jsonrpc_method_regex():
    print("\n[12] _is_jsonrpc_method routing regex boundary")
    from chain_adapters.hedera_dual import _is_jsonrpc_method
    # Positive cases — JSON-RPC namespaces
    for m in ["eth_getBalance", "eth_call", "eth_blockNumber",
              "net_version", "web3_clientVersion",
              "debug_traceTransaction", "trace_block"]:
        assert _is_jsonrpc_method(m), f"{m!r} should route to JSON-RPC"
    # Negative cases — REST path keys, never JSON-RPC
    for m in ["GET /api/v1/accounts/{addr}",
              "GET /api/v1/balances?account.id={addr}",
              "POST /api/v1/contracts/call",
              "mirror_account_query",  # legacy logical name
              "getAccount",            # camelCase non-eth
              "ethReporter",           # starts with "eth" but no underscore
              "_eth_getBalance"]:      # leading underscore
        assert not _is_jsonrpc_method(m), f"{m!r} should NOT route to JSON-RPC"
    _ok("regex correctly distinguishes 7 JSON-RPC namespaces from REST/other forms")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    tests = [
        test_factory_registers_seven_families,
        test_all_36_chains_resolve,
        test_baseline_8_vegeta_byte_equality,
        test_parse_block_height_per_family,
        test_health_check_requests,
        test_bitcoin_auth,
        test_rest_requires_env_and_path_map,
        test_jsonrpc_s3a_new_formats,
        test_evm_compat_5chains_standard_enum,
        test_cli_build_target_all_36_chains,
        test_hedera_dual_adapter_routing,
        test_is_jsonrpc_method_regex,
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
