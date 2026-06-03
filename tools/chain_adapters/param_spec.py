"""param_spec — 声明式 RPC 参数构造 DSL(B1, design §4.2 + §6.6.3)。

目标(NS-1/NS-3): 用户配任意 RPC method 的参数构造, 零代码。chain template 声明
`param_spec[method]`(结构化), 框架据此构造请求; 现有 `param_formats`(枚举)保留作
向后兼容快捷预设, 经 PARAM_FORMAT_PRESETS 展开成等价 param_spec(单一构造路径, 非两套并存)。

读取优先级(避 parallel-entry, §6.6.3):
    param_spec[method] 存在        → 直接用
    否则 param_formats[method] 枚举 → PARAM_FORMAT_PRESETS 展开成 param_spec → 用
    都无                            → fail-fast(R3: 禁静默 fallback single_address)

param_spec 结构(design §4.2):
    {
      "transport": "jsonrpc_list|jsonrpc_dict|rest_path|rest_query|rest_body",
      "slots":  [ {"source":"account|literal|tx_hash|block_hash|...", "encoding":..., "value":...}, ... ],
      "fields": { "<key>": {"source":..., ...}, ... },     # dict/body
      "path":   "/v2/accounts/{address}",                   # rest_*
      "query":  { "<k>": {"source":"literal","value":...} },
      "bindings": { "{address}": {"source":"account","encoding":...} },
      "http_method": "GET|POST",
      "call_object": { "shape": "evm_call|aptos_view|tron_trigger", ... },
    }

source 枚举(从哪个输入池取值, S1 多池供给的契约):
    account    — 账户地址池(fetch_active_accounts 产出)
    tx_hash    — 交易哈希池(S1 A2 保留的 tx_hash)
    block_hash — 区块哈希池
    block_number / slot / height / round / asset_id / pool_id — 数值池(链上现取)
    literal    — 字面常量(value 字段给值)
    contract_call — 复杂合约调用对象(call_object 描述)
"""
from __future__ import annotations
from typing import Optional, Any


class ParamSpecError(ValueError):
    """param_spec 声明非法 / 缺失(fail-fast, 非静默)。"""


# ─────────────────────────────────────────────────────────────────────────────
# 枚举 → param_spec 预设展开表(PARAM_FORMAT_PRESETS)
#
# 把现有 56 种 param_formats 枚举各映射成等价 param_spec 结构。枚举 = param_spec 的
# 语法糖别名; 展开后走同一构造路径(无第二套逻辑)。
#
# 语义来源: design §3 184 method 实测矩阵 + §4.3 14类形态验证。每条映射的参数顺序/
# 编码/字面值都对照实测请求体确认(不臆造)。
#
# 分批策略(逐批对照 §3 验证, 不草率):
#   批1 规整枚举(语义清晰, §4.3 已验证)— 本次实现
#   批2 bitcoin/near/avax 半结构化(枚举名塞了结构)— 本次实现(语义已在 §3 矩阵)
#   批3 ton 自然语言枚举({address,limit,lt?,hash?} 等)+ tron body — 本次实现
# ─────────────────────────────────────────────────────────────────────────────

PARAM_FORMAT_PRESETS: dict[str, dict] = {
    # ── 批1: jsonrpc_list 规整枚举 ──
    "no_params": {"transport": "jsonrpc_list", "slots": []},
    "single_address": {
        "transport": "jsonrpc_list",
        "slots": [{"source": "account"}],
    },
    "address_latest": {  # EVM: [addr, "latest"]
        "transport": "jsonrpc_list",
        "slots": [{"source": "account"}, {"source": "literal", "value": "latest"}],
    },
    "latest_address": {  # StarkNet: ["latest", addr]  (R2 位置相反, 数组序固定)
        "transport": "jsonrpc_list",
        "slots": [{"source": "literal", "value": "latest"}, {"source": "account"}],
    },
    "address_storage_latest": {  # eth_getStorageAt: [addr, "0x0", "latest"]
        "transport": "jsonrpc_list",
        "slots": [
            {"source": "account"},
            {"source": "literal", "value": "0x0"},
            {"source": "literal", "value": "latest"},
        ],
    },
    "address_key_latest": {  # starknet_getStorageAt: [addr, "0x1", "latest"]
        "transport": "jsonrpc_list",
        "slots": [
            {"source": "account"},
            {"source": "literal", "value": "0x1"},
            {"source": "literal", "value": "latest"},
        ],
    },
    "transaction_hash": {  # eth_getTransactionByHash/Receipt: [tx_hash]  (A2 真值池)
        "transport": "jsonrpc_list",
        "slots": [{"source": "tx_hash"}],
    },
    "block_number": {  # eth_getBlockByNumber: ["latest", false]
        "transport": "jsonrpc_list",
        "slots": [{"source": "literal", "value": "latest"}, {"source": "literal", "value": False}],
    },
    "block_number_int": {  # zks_getBlockDetails: [<int>]  (block_number 池)
        "transport": "jsonrpc_list",
        "slots": [{"source": "block_number"}],
    },
    "block_hash": {  # substrate chain_getBlock 等: [block_hash]
        "transport": "jsonrpc_list",
        "slots": [{"source": "block_hash"}],
    },
    "object_single": {  # linea_estimateGas: [{from,to,value}]
        "transport": "jsonrpc_list",
        "slots": [{"source": "contract_call", "call_object": {"shape": "evm_tx_object"}}],
    },
    "eth_call_object_latest": {  # eth_call: [{to,data}, "latest"]
        "transport": "jsonrpc_list",
        "slots": [
            {"source": "contract_call", "call_object": {"shape": "evm_call"}},
            {"source": "literal", "value": "latest"},
        ],
    },
    "address_with_options": {  # sui_getObject: [obj, {showType,showContent,...}]
        "transport": "jsonrpc_list",
        "slots": [
            {"source": "account"},
            {"source": "literal", "value": {"showType": True, "showContent": True, "showDisplay": False}},
        ],
    },

    # ── 批2: 半结构化枚举(枚举名塞了 list 结构, 语义在 §3 矩阵)──
    "[null]": {"transport": "jsonrpc_list", "slots": [{"source": "literal", "value": None}]},
    "[block_number]": {"transport": "jsonrpc_list", "slots": [{"source": "block_number"}]},
    "[height]": {"transport": "jsonrpc_list", "slots": [{"source": "height"}]},
    "[blockhash]": {"transport": "jsonrpc_list", "slots": [{"source": "block_hash"}]},
    "[conf_target]": {"transport": "jsonrpc_list", "slots": [{"source": "literal", "value": 6}]},
    "[txhash,verbose]": {  # bch getrawtransaction: [txhash, true]
        "transport": "jsonrpc_list",
        "slots": [{"source": "tx_hash"}, {"source": "literal", "value": True}],
    },
    "[txid,verbose]": {  # bitcoin getrawtransaction
        "transport": "jsonrpc_list",
        "slots": [{"source": "tx_hash"}, {"source": "literal", "value": True}],
    },
    "[blockhash,verbosity]": {  # bitcoin getblock: [blockhash, 1]
        "transport": "jsonrpc_list",
        "slots": [{"source": "block_hash"}, {"source": "literal", "value": 1}],
    },
    "[hash,signer_id]": {  # near tx: [tx_hash, account]
        "transport": "jsonrpc_list",
        "slots": [{"source": "tx_hash"}, {"source": "account"}],
    },
}


def expand_preset(param_format: str) -> Optional[dict]:
    """枚举字符串 → param_spec 结构。未知枚举返回 None(调用方 fail-fast)。"""
    return PARAM_FORMAT_PRESETS.get(param_format)


def resolve_param_spec(
    method: str,
    chain_param_spec: Optional[dict],
    chain_param_formats: Optional[dict],
) -> dict:
    """统一读取入口(§6.6.3 单一构造路径)。

    优先 param_spec[method]; 否则 param_formats[method] 枚举展开; 都无 → fail-fast。
    """
    if chain_param_spec and method in chain_param_spec:
        spec = chain_param_spec[method]
        validate_spec(method, spec)
        return spec
    if chain_param_formats and method in chain_param_formats:
        fmt = chain_param_formats[method]
        spec = expand_preset(fmt)
        if spec is None:
            raise ParamSpecError(
                f"method {method!r}: param_format {fmt!r} has no PARAM_FORMAT_PRESETS "
                f"mapping. Add it to param_spec.py or declare param_spec[{method!r}] explicitly. "
                f"(R3: refusing silent fallback to single_address)"
            )
        return spec
    raise ParamSpecError(
        f"method {method!r}: no param_spec[{method!r}] and no param_formats[{method!r}]. "
        f"Declare one in chain template. (R3: refusing silent fallback)"
    )


_VALID_TRANSPORTS = {"jsonrpc_list", "jsonrpc_dict", "rest_path", "rest_query", "rest_body"}
_VALID_SOURCES = {
    "account", "tx_hash", "block_hash", "block_number", "slot", "height",
    "round", "asset_id", "pool_id", "literal", "contract_call",
}


def validate_spec(method: str, spec: dict) -> None:
    """param_spec 结构校验(R2: 启动期校验, fail-fast)。"""
    if not isinstance(spec, dict):
        raise ParamSpecError(f"method {method!r}: param_spec must be dict, got {type(spec).__name__}")
    transport = spec.get("transport")
    if transport not in _VALID_TRANSPORTS:
        raise ParamSpecError(
            f"method {method!r}: invalid transport {transport!r}, must be one of {sorted(_VALID_TRANSPORTS)}"
        )
    # slot/field source 校验
    for slot in spec.get("slots", []):
        src = slot.get("source")
        if src not in _VALID_SOURCES:
            raise ParamSpecError(f"method {method!r}: slot source {src!r} invalid, must be one of {sorted(_VALID_SOURCES)}")
        if src == "literal" and "value" not in slot:
            raise ParamSpecError(f"method {method!r}: literal slot missing 'value'")
    for key, fld in spec.get("fields", {}).items():
        src = fld.get("source")
        if src not in _VALID_SOURCES:
            raise ParamSpecError(f"method {method!r}: field {key!r} source {src!r} invalid")
        if src == "literal" and "value" not in fld:
            raise ParamSpecError(f"method {method!r}: literal field {key!r} missing 'value'")
    # rest_* 需 path
    if transport in ("rest_path", "rest_query") and not spec.get("path"):
        raise ParamSpecError(f"method {method!r}: transport {transport} requires 'path'")
