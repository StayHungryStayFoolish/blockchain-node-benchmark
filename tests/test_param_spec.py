#!/usr/bin/env python3
"""Param-spec request construction tests.

Run directly:
    python3 tests/test_param_spec.py
"""
from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

from chain_adapters.bitcoin_jsonrpc import BitcoinJsonRpcAdapter  # noqa: E402
from chain_adapters.jsonrpc import JsonRpcAdapter  # noqa: E402
from chain_adapters.param_spec import (  # noqa: E402
    ParamSpecError,
    apply_rest_param_spec,
    build_jsonrpc_params,
    get_param_spec,
)
from chain_adapters.rest import RestAdapter  # noqa: E402
from chain_adapters.substrate import SubstrateAdapter  # noqa: E402
from chain_adapters.tendermint import TendermintAdapter  # noqa: E402


PASS = "\033[32m✓\033[0m"


def _ok(msg: str) -> None:
    print(f"  {PASS} {msg}")


def _target_body(target: dict) -> dict:
    return json.loads(base64.b64decode(target["body"]).decode())


def test_jsonrpc_list_and_dict() -> None:
    print("\n[1] JSON-RPC param_spec list/dict")
    tpl = {
        "params": {"target_height": "${TARGET_HEIGHT:-123}"},
        "param_spec": {
            "eth_getBalance": {
                "transport": "jsonrpc_list",
                "params": [{"source": "address"}, {"literal": "latest"}],
            },
            "eth_getStorageAt": {
                "transport": "jsonrpc_list",
                "params": [
                    {"source": "address"},
                    {"source": "target_storage_slot"},
                    {"literal": "latest"},
                ],
            },
            "example_getByHeight": {
                "transport": "jsonrpc_dict",
                "fields": {
                    "height": {"source": "target_height", "type": "int"},
                    "encoding": {"literal": "json"},
                },
            },
        },
    }
    assert build_jsonrpc_params(get_param_spec(tpl, "eth_getBalance"), tpl, "0xabc") == ["0xabc", "latest"]
    assert build_jsonrpc_params(get_param_spec(tpl, "eth_getStorageAt"), tpl, "0xabc") == [
        "0xabc",
        "0x0",
        "latest",
    ]
    assert build_jsonrpc_params(get_param_spec(tpl, "example_getByHeight"), tpl, "0xabc") == {
        "height": 123,
        "encoding": "json",
    }
    _ok("builds positional, 3-argument, and object JSON-RPC params")


def test_rest_query_and_body() -> None:
    print("\n[2] REST param_spec query/body")
    tpl = {
        "params": {
            "target_tx_hash": "${TARGET_TX_HASH:-0xdeadbeef}",
            "target_height": "${TARGET_HEIGHT:-456}",
        }
    }
    path, body, query = apply_rest_param_spec(
        {
            "transport": "rest_query",
            "bindings": {"height": {"source": "target_height", "type": "int"}},
            "query": {"hash": {"source": "target_tx_hash"}},
        },
        "/v1/block/{height}",
        None,
        tpl,
        "0xabc",
    )
    assert path == "/v1/block/456"
    assert body is None
    assert query == {"hash": "0xdeadbeef"}

    _, body, query = apply_rest_param_spec(
        {
            "transport": "rest_body",
            "body": {
                "owner": {"source": "address"},
                "visible": {"literal": True, "type": "bool"},
            },
        },
        "/wallet/triggerconstantcontract",
        {},
        tpl,
        "TAddress",
    )
    assert body == {"owner": "TAddress", "visible": True}
    assert query == {}
    _ok("applies path bindings, query values, and nested body templates")


def test_adapter_integration() -> None:
    print("\n[3] JsonRpc/REST adapter integration")
    jsonrpc_adapter = JsonRpcAdapter()
    jsonrpc_adapter._chain_cache["param-spec-jsonrpc"] = {
        "chain_type": "example",
        "params": {"target_height": "${TARGET_HEIGHT:-7}"},
        "param_spec": {
            "example_getByHeight": {
                "transport": "jsonrpc_dict",
                "fields": {"height": {"source": "target_height", "type": "int"}},
            }
        },
    }
    os.environ["BLOCKCHAIN_NODE"] = "param-spec-jsonrpc"
    target = jsonrpc_adapter.build_vegeta_target(
        "example_getByHeight", "0xabc", "http://localhost:8545", "single_address"
    )
    assert _target_body(target)["params"] == {"height": 7}

    rest_adapter = RestAdapter()
    rest_adapter._chain_cache["param-spec-rest"] = {
        "chain_type": "example-rest",
        "params": {"target_height": "${TARGET_HEIGHT:-9}"},
        "_meta": {
            "rest_paths": {
                "GET_BLOCK": {"method": "GET", "path": "/v1/block/{height}"},
            }
        },
        "param_spec": {
            "GET_BLOCK": {
                "transport": "rest_query",
                "bindings": {"height": {"source": "target_height", "type": "int"}},
                "query": {"verbose": {"literal": "true"}},
            }
        },
    }
    os.environ["BLOCKCHAIN_NODE"] = "param-spec-rest"
    target = rest_adapter.build_vegeta_target("GET_BLOCK", "0xabc", "http://localhost:8080", "")
    assert target["url"] == "http://localhost:8080/v1/block/9?verbose=true"
    _ok("adapters prefer explicit param_spec over generic param_formats/rest_paths")


def test_all_core_families_use_param_spec() -> None:
    print("\n[4] Core family adapter integration")

    bitcoin_adapter = BitcoinJsonRpcAdapter()
    bitcoin_adapter._chain_cache["param-spec-bitcoin"] = {
        "chain_type": "bitcoin-test",
        "params": {"target_txid": "${TARGET_TXID:-abc123}"},
        "param_spec": {
            "getrawtransaction": {
                "transport": "jsonrpc_list",
                "params": [{"source": "target_txid"}, {"literal": True, "type": "bool"}],
            }
        },
    }
    os.environ["BLOCKCHAIN_NODE"] = "param-spec-bitcoin"
    target = bitcoin_adapter.build_vegeta_target(
        "getrawtransaction", "fallback", "http://localhost:8332", "no_params"
    )
    assert _target_body(target)["params"] == ["abc123", True]

    substrate_adapter = SubstrateAdapter()
    substrate_adapter._chain_cache["param-spec-substrate"] = {
        "chain_type": "substrate-test",
        "params": {"target_block_hash": "${TARGET_BLOCK_HASH:-0xbeef}"},
        "param_spec": {
            "chain_getHeader": {
                "transport": "jsonrpc_list",
                "params": [{"source": "target_block_hash"}],
            }
        },
    }
    os.environ["BLOCKCHAIN_NODE"] = "param-spec-substrate"
    target = substrate_adapter.build_vegeta_target(
        "chain_getHeader", "fallback", "http://localhost:9944", "no_params"
    )
    assert _target_body(target)["params"] == ["0xbeef"]

    tendermint_adapter = TendermintAdapter()
    tendermint_adapter._chain_cache["param-spec-tendermint"] = {
        "chain_type": "tendermint-test",
        "params": {"target_height": "${TARGET_HEIGHT:-99}"},
        "param_spec": {
            "block": {
                "transport": "jsonrpc_dict",
                "fields": {"height": {"source": "target_height", "type": "int"}},
            }
        },
    }
    os.environ["BLOCKCHAIN_NODE"] = "param-spec-tendermint"
    target = tendermint_adapter.build_vegeta_target(
        "block", "fallback", "http://localhost:26657", "no_params"
    )
    assert _target_body(target)["params"] == {"height": 99}
    _ok("bitcoin_jsonrpc, substrate, and tendermint adapters honor param_spec")


def test_invalid_spec_fails() -> None:
    print("\n[5] Invalid param_spec")
    tpl = {"param_spec": {"bad": {"transport": "jsonrpc_list", "params": [{"source": ""}]}}}
    try:
        get_param_spec(tpl, "bad")
    except ParamSpecError:
        _ok("invalid source fails before benchmark runtime")
        return
    raise AssertionError("expected ParamSpecError")


def main() -> None:
    test_jsonrpc_list_and_dict()
    test_rest_query_and_body()
    test_adapter_integration()
    test_all_core_families_use_param_spec()
    test_invalid_spec_fails()
    print("\nParam-spec tests passed")


if __name__ == "__main__":
    main()
