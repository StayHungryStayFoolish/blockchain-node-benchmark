"""Structured RPC parameter construction helpers.

`param_formats` is intentionally compact, but it is limited when a new RPC
method needs mixed positional parameters, request-body objects, path bindings,
or query values. `param_spec` is an optional chain-template field for those
cases. Existing chain templates keep working without it.

Supported example:

    "param_spec": {
      "eth_getBalance": {
        "transport": "jsonrpc_list",
        "params": [
          {"source": "address"},
          {"literal": "latest"}
        ]
      }
    }
"""
from __future__ import annotations

import copy
from typing import Any

from .url_overrides import resolve_param, resolve_value


class ParamSpecError(ValueError):
    """Raised when a param_spec entry is malformed or unsupported."""


SUPPORTED_TRANSPORTS = {
    "jsonrpc_list",
    "jsonrpc_dict",
    "rest_path",
    "rest_query",
    "rest_body",
}


def get_param_spec(tpl: dict[str, Any], method: str) -> dict[str, Any] | None:
    """Return a validated param_spec for method, or None when not configured."""
    specs = tpl.get("param_spec")
    if not isinstance(specs, dict):
        return None
    spec = specs.get(method)
    if spec is None:
        return None
    if not isinstance(spec, dict):
        raise ParamSpecError(f"param_spec.{method} must be an object")
    validate_param_spec(method, spec)
    return copy.deepcopy(spec)


def validate_param_spec(method: str, spec: dict[str, Any]) -> None:
    transport = spec.get("transport")
    if transport not in SUPPORTED_TRANSPORTS:
        raise ParamSpecError(
            f"param_spec.{method}.transport must be one of {sorted(SUPPORTED_TRANSPORTS)}"
        )

    if transport == "jsonrpc_list":
        params = spec.get("params", spec.get("slots", []))
        if not isinstance(params, list):
            raise ParamSpecError(f"param_spec.{method}.params must be a list")
        for item in params:
            _validate_value_spec(method, item)
        return

    if transport == "jsonrpc_dict":
        fields = spec.get("fields", spec.get("params", {}))
        if not isinstance(fields, dict):
            raise ParamSpecError(f"param_spec.{method}.fields must be an object")
        for item in fields.values():
            _validate_value_spec(method, item)
        return

    bindings = spec.get("bindings", {})
    if bindings is not None and not isinstance(bindings, dict):
        raise ParamSpecError(f"param_spec.{method}.bindings must be an object")
    for item in bindings.values():
        _validate_value_spec(method, item)

    query = spec.get("query", {})
    if query is not None and not isinstance(query, dict):
        raise ParamSpecError(f"param_spec.{method}.query must be an object")
    for item in query.values():
        _validate_value_spec(method, item)

    if "body" in spec:
        _validate_template(method, spec["body"])


def build_jsonrpc_params(spec: dict[str, Any], tpl: dict[str, Any], address: str) -> Any:
    """Build JSON-RPC params from a jsonrpc_list/jsonrpc_dict param_spec."""
    transport = spec.get("transport")
    if transport == "jsonrpc_list":
        params = spec.get("params", spec.get("slots", []))
        return [_resolve_value(item, tpl, address) for item in params]
    if transport == "jsonrpc_dict":
        fields = spec.get("fields", spec.get("params", {}))
        return {key: _resolve_value(item, tpl, address) for key, item in fields.items()}
    raise ParamSpecError(f"transport {transport!r} cannot build JSON-RPC params")


def apply_rest_param_spec(
    spec: dict[str, Any],
    path: str,
    body: Any,
    tpl: dict[str, Any],
    address: str,
) -> tuple[str, Any, dict[str, str]]:
    """Apply rest_path/rest_query/rest_body fields to path/body.

    Returns `(path, body, query_values)`. The caller still owns base URL and
    HTTP method selection from `_meta.rest_paths`.
    """
    transport = spec.get("transport")
    bindings = spec.get("bindings", {})
    for name, value_spec in bindings.items():
        token = str(name)
        if not token.startswith("{"):
            token = "{" + token.strip("{}") + "}"
        path = path.replace(token, str(_resolve_value(value_spec, tpl, address)))

    query_values: dict[str, str] = {}
    if transport == "rest_query":
        for key, value_spec in spec.get("query", {}).items():
            query_values[key] = str(_resolve_value(value_spec, tpl, address))

    if transport == "rest_body":
        body = _resolve_template(spec.get("body", {}), tpl, address)
    elif "body" in spec:
        body = _resolve_template(spec["body"], tpl, address)

    return path, body, query_values


def _validate_value_spec(method: str, item: Any) -> None:
    if isinstance(item, (str, int, float, bool)) or item is None:
        return
    if not isinstance(item, dict):
        raise ParamSpecError(f"param_spec.{method} value spec must be scalar or object")
    if "literal" in item or "value" in item:
        return
    source = item.get("source")
    if not isinstance(source, str) or not source:
        raise ParamSpecError(f"param_spec.{method} value spec missing source")


def _validate_template(method: str, value: Any) -> None:
    if isinstance(value, dict):
        for item in value.values():
            _validate_template(method, item)
    elif isinstance(value, list):
        for item in value:
            _validate_template(method, item)
    else:
        _validate_value_spec(method, value)


def _resolve_template(value: Any, tpl: dict[str, Any], address: str) -> Any:
    if isinstance(value, dict) and _looks_like_value_spec(value):
        return _resolve_value(value, tpl, address)
    if isinstance(value, dict):
        return {key: _resolve_template(item, tpl, address) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_template(item, tpl, address) for item in value]
    return value


def _looks_like_value_spec(value: dict[str, Any]) -> bool:
    return "source" in value or "literal" in value or "value" in value


def _resolve_value(item: Any, tpl: dict[str, Any], address: str) -> Any:
    if isinstance(item, dict):
        if "literal" in item:
            value = item["literal"]
        elif "value" in item:
            value = item["value"]
        else:
            value = _source_value(str(item["source"]), tpl, address)
        value = resolve_value(value)
        if item.get("type") == "int":
            return int(value)
        if item.get("type") == "bool":
            if isinstance(value, bool):
                return value
            return str(value).lower() in {"1", "true", "yes", "on"}
        if item.get("wrap_array"):
            return [value]
        return value
    return resolve_value(item)


def _source_value(source: str, tpl: dict[str, Any], address: str) -> Any:
    params = tpl.get("params", {}) if isinstance(tpl.get("params"), dict) else {}
    if source in {"address", "account", "target_address"}:
        return resolve_param(params, "target_address", address) if source == "target_address" else address
    if source in {"tx_hash", "target_tx_hash"}:
        return resolve_param(params, "target_tx_hash", resolve_param(params, "tx_hash", address))
    if source in {"txid", "target_txid"}:
        return resolve_param(params, "target_txid", resolve_param(params, "txid", address))
    if source in {"block_hash", "target_block_hash"}:
        return resolve_param(params, "target_block_hash", resolve_param(params, "block_hash", address))
    if source in {"height", "block_height", "target_height"}:
        return resolve_param(params, "target_height", resolve_param(params, "height", "1"))
    if source in {"storage_slot", "slot", "target_storage_slot"}:
        return resolve_param(params, "target_storage_slot", resolve_param(params, "storage_slot", "0x0"))
    if source in {"block", "target_block"}:
        return resolve_param(params, "target_block", resolve_param(params, "block", "head"))
    if source in {"round", "target_round"}:
        return resolve_param(params, "target_round", resolve_param(params, "round", "1"))
    if source in {"asset_id", "target_asset_id"}:
        return resolve_param(params, "target_asset_id", resolve_param(params, "asset_id", "1"))
    if source in {"asset", "target_asset"}:
        return resolve_param(params, "target_asset", resolve_param(params, "asset", address))
    if source in {"pool_id", "target_pool_id"}:
        return resolve_param(params, "target_pool_id", resolve_param(params, "pool_id", "1"))
    if source in {"contract_address", "target_contract_address"}:
        return resolve_param(params, "target_contract_address", address)
    if source in {"evm_address", "target_evm_address"}:
        return resolve_param(params, "target_evm_address", address)
    raise ParamSpecError(f"unsupported param_spec source: {source}")
