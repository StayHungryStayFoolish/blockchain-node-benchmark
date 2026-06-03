"""L1 单测: param_spec 枚举展开 + resolve 优先级 + 校验器 fail-fast。

验证 B1 核心交付(design §6.6.3)。对照 §3 实测语义(参数顺序/编码/字面值)。
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from chain_adapters import param_spec as ps


def test_no_params_empty_slots():
    s = ps.expand_preset("no_params")
    assert s == {"transport": "jsonrpc_list", "slots": []}


def test_address_latest_order():
    # §3 实测: EVM eth_getBalance = [addr, "latest"] 顺序
    s = ps.expand_preset("address_latest")
    assert s["slots"][0]["source"] == "account"
    assert s["slots"][1] == {"source": "literal", "value": "latest"}


def test_latest_address_reversed_order():
    # §3 实测 R2: StarkNet 相反顺序 ["latest", addr]
    s = ps.expand_preset("latest_address")
    assert s["slots"][0] == {"source": "literal", "value": "latest"}
    assert s["slots"][1]["source"] == "account"


def test_transaction_hash_uses_tx_hash_pool():
    # A2: tx_hash 真值池(非 account)
    s = ps.expand_preset("transaction_hash")
    assert s["slots"][0]["source"] == "tx_hash"


def test_near_tx_two_sources():
    # near tx: [tx_hash, account] — 两个不同池
    s = ps.expand_preset("[hash,signer_id]")
    assert [x["source"] for x in s["slots"]] == ["tx_hash", "account"]


def test_resolve_prefers_param_spec_over_format():
    explicit = {"foo": {"transport": "jsonrpc_list", "slots": [{"source": "account"}]}}
    formats = {"foo": "no_params"}
    s = ps.resolve_param_spec("foo", explicit, formats)
    assert s["slots"] == [{"source": "account"}]  # param_spec 赢


def test_resolve_falls_back_to_format_enum():
    s = ps.resolve_param_spec("bar", None, {"bar": "address_latest"})
    assert s["slots"][1]["value"] == "latest"


def test_resolve_unknown_enum_fail_fast():
    # R3: 未知枚举不静默 fallback, 必报错
    try:
        ps.resolve_param_spec("baz", None, {"baz": "totally_unknown_format"})
        assert False, "should have raised ParamSpecError"
    except ps.ParamSpecError as e:
        assert "no PARAM_FORMAT_PRESETS mapping" in str(e)


def test_resolve_no_declaration_fail_fast():
    # R3: 既无 param_spec 又无 param_formats → fail-fast(禁静默 single_address)
    try:
        ps.resolve_param_spec("qux", None, None)
        assert False, "should have raised"
    except ps.ParamSpecError as e:
        assert "refusing silent fallback" in str(e)


def test_validate_rejects_bad_transport():
    try:
        ps.validate_spec("m", {"transport": "bogus"})
        assert False
    except ps.ParamSpecError as e:
        assert "invalid transport" in str(e)


def test_validate_rejects_literal_without_value():
    try:
        ps.validate_spec("m", {"transport": "jsonrpc_list", "slots": [{"source": "literal"}]})
        assert False
    except ps.ParamSpecError as e:
        assert "missing 'value'" in str(e)


def test_validate_rest_requires_path():
    try:
        ps.validate_spec("m", {"transport": "rest_path"})
        assert False
    except ps.ParamSpecError as e:
        assert "requires 'path'" in str(e)


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS {fn.__name__}")
            passed += 1
        except Exception:
            print(f"  FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)
