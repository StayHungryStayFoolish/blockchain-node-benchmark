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
from typing import Optional


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
    "block_number_int": {  # zks_getBlockDetails: [<int>]  (block_height 池, 整数块号)
        "transport": "jsonrpc_list",
        "slots": [{"source": "block_height"}],
    },
    "block_hash": {  # substrate chain_getBlock 等: [区块哈希]
        "transport": "jsonrpc_list",
        "slots": [{"source": "block_height"}],
    },
    "object_single": {  # linea_estimateGas: [{from,to,value}]
        "transport": "jsonrpc_list",
        "slots": [{"source": "contract_call", "call_object": {"shape": "evm_call"}}],
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
            {"source": "config_object", "value": {"showType": True, "showContent": True, "showDisplay": False}},
        ],
    },

    # ── 批2: 半结构化枚举(枚举名塞了 list 结构, 语义在 §3 矩阵)──
    "[null]": {"transport": "jsonrpc_list", "slots": [{"source": "literal", "value": None}]},
    "[block_number]": {"transport": "jsonrpc_list", "slots": [{"source": "block_height"}]},
    "[height]": {"transport": "jsonrpc_list", "slots": [{"source": "block_height"}]},
    "[blockhash]": {"transport": "jsonrpc_list", "slots": [{"source": "block_height"}]},
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
        "slots": [{"source": "block_height"}, {"source": "literal", "value": 1}],
    },
    "[hash,signer_id]": {  # near tx: [tx_hash, account]
        "transport": "jsonrpc_list",
        "slots": [{"source": "tx_hash"}, {"source": "account"}],
    },

    # ── 批3b收尾: near dict 参数(query dispatcher, fixture 真机结构实证) ──
    # near query 是 dispatcher: params 是 dict, request_type 判别查询类型(jsonrpc_dict)。
    # 真机 fixture: {request_type:'view_account', finality:'final', account_id:'<addr>'}
    "query_dispatcher_request_type": {
        "transport": "jsonrpc_dict",
        "fields": {
            "request_type": {"source": "literal", "value": "view_account"},
            "finality": {"source": "literal", "value": "final"},
            "account_id": {"source": "account"},
        },
    },
    # near block: params={finality:'final'}(真机 fixture 实证)
    "block_finality_or_id": {
        "transport": "jsonrpc_dict",
        "fields": {"finality": {"source": "literal", "value": "final"}},
    },

    # ── 批3b: REST transport 预设(rest_path/rest_query/rest_body) ──
    # method 名本身是 path 模板(GET /cosmos/.../{addr}); PRESET 声明 transport +
    # 占位名→source 池映射。rest.py 按此从 inputs 多池取值替换占位 / 拼 query / 填 body。
    # 占位污染修复: {address} 历史被硬塞, 这里声明真实 source(txid→tx_hash 非 account)。
    #
    # rest_path: path 占位替换。bindings 声明每个占位从哪个 source 池取。
    "path_addr": {"transport": "rest_path", "bindings": {"addr": {"source": "account"}, "address": {"source": "account"}}},
    "path_address": {"transport": "rest_path", "bindings": {"address": {"source": "account"}, "addr": {"source": "account"}}},
    "path_addr_base32": {"transport": "rest_path", "bindings": {"address": {"source": "account"}, "addr": {"source": "account"}}},
    "path_hash": {"transport": "rest_path", "bindings": {"hash": {"source": "tx_hash"}}},
    "path_hash_upper_hex_no_prefix": {"transport": "rest_path", "bindings": {"hash": {"source": "tx_hash"}}},
    "path_txid_base32": {"transport": "rest_path", "bindings": {"txid": {"source": "tx_hash"}}},
    "path_height": {"transport": "rest_path", "bindings": {"height": {"source": "block_height"}}},
    "path_round_int": {"transport": "rest_path", "bindings": {"round": {"source": "block_height"}}},
    "path_asset_id_int": {"transport": "rest_path", "bindings": {"asset_id": {"source": "business_id"}}},  # 资产ID(独立 business_id 池, 非块高)
    "path_pool_id": {"transport": "rest_path", "bindings": {"pool_id": {"source": "business_id"}}},  # 池ID(独立 business_id 池)
    "path_block_and_vp": {"transport": "rest_path", "bindings": {"block": {"source": "block_height"}, "vp": {"source": "literal", "value": "0"}}},
    "path_addr_query_limit": {"transport": "rest_query", "bindings": {"address": {"source": "account"}, "addr": {"source": "account"}}, "query": {"limit": {"source": "literal", "value": "10"}}},
    # rest_query: path(可能含占位) + query string
    "query_pagination": {"transport": "rest_query", "query": {"pagination.limit": {"source": "literal", "value": "10"}}},
    "query_params": {"transport": "rest_query", "query": {}},  # 具体 query 由 method 自带(twap 等), 占位为空安全
    "query_epoch_int": {"transport": "rest_query", "query": {}},
    # rest_body: POST body 模板。fields 声明 body 各字段从哪个 source 取(数组形态)。
    "body_addresses_array": {"transport": "rest_body", "http_method": "POST", "body_template": {"_addresses": ["{account}"]}},
    "body_tx_hashes_array": {"transport": "rest_body", "http_method": "POST", "body_template": {"_tx_hashes": ["{tx_hash}"]}},
    "body_block_hashes_array": {"transport": "rest_body", "http_method": "POST", "body_template": {"_block_hashes": ["{block_height}"]}},
    "asset_policy_name": {"transport": "rest_body", "http_method": "POST", "body_template": {"_asset_list": [["{policy}", "{asset_name}"]]}},
    "move_view_call": {"transport": "rest_body", "http_method": "POST", "body_template": {"function": "0x1::coin::balance", "type_arguments": ["0x1::aptos_coin::AptosCoin"], "arguments": ["{account}"]}},

    # ── 批3b收尾: ton 自然语言枚举 → 规整 PRESET(toncenter v2 官方结构, path 自带 query) ──
    # ton rest_paths path 已含 query(?address={address}&limit=10), 用 rest_path + {address} bindings 即可。
    "{address: friendly_base64url|raw}": {"transport": "rest_path", "bindings": {"address": {"source": "account"}}},
    "{address, limit, lt?, hash?}": {"transport": "rest_path", "bindings": {"address": {"source": "account"}}},  # limit 已在 path 写死, lt/hash 可选不填
    "{workchain: int, shard: dec_string, seqno: int}": {"transport": "rest_path", "bindings": {}},  # path 已写死 workchain/shard/seqno(masterchain 定值), 无占位
    "{address, method: string, stack: array}": {"transport": "rest_body", "http_method": "POST", "body_template": {"address": "{account}", "method": "seqno", "stack": []}},  # runGetMethod

    # ── 批3b收尾: tron /wallet REST POST body(混协议链, /wallet→REST + eth_→jsonrpc 走 dual adapter) ──
    # fixture 真机 body 实证。address/owner_address 从 account 池, value(txid) 从 tx_hash 池, visible literal。
    "body_address_visible": {"transport": "rest_body", "http_method": "POST", "body_template": {"address": "{account}", "visible": True}},  # /wallet/getaccount
    "body_value_txid_nopfx": {"transport": "rest_body", "http_method": "POST", "body_template": {"value": "{tx_hash}"}},  # /wallet/gettransactionbyid
    "body_owner_contract_selector_parameter": {"transport": "rest_body", "http_method": "POST", "body_template": {"owner_address": "{account}", "contract_address": "{account}", "function_selector": "totalSupply()", "visible": True}},  # /wallet/triggerconstantcontract(contract_address 应业务合约, 批4 business 池)
    "rest_post_empty": {"transport": "rest_body", "http_method": "POST", "body_template": {}},  # tron /wallet/getnowblock 等 REST POST 空 body(区别于 jsonrpc no_params 空 list)
}


def expand_preset(param_format: str) -> Optional[dict]:
    """枚举字符串 → param_spec 结构。未知枚举返回 None(调用方 fail-fast)。"""
    return PARAM_FORMAT_PRESETS.get(param_format)


# ─────────────────────────────────────────────────────────────────────────────
# 构造器: param_spec + inputs → 实际请求参数(S2 核心, design §4.2 执行端)
#
# resolve_param_spec 给出【结构】(transport + slots/fields/...), build_params_from_spec
# 按结构从 inputs 多池取真值, 组装成协议参数。这是 param_spec.py 从"孤岛草稿"接入
# 生产的关键缺失件(SSOT: 缺 spec→params 构造器)。
#
# inputs 契约(S1 多池供给, 批1 暂 {"account":[address]}):
#   {"account": [...], "tx_hash": [...], "block_height": [...], "contract_call": [...]}
#   每池是 list; 构造时取第 idx 个(默认 0, mixed 轮询时由调用方传 idx 轮换)。
# ─────────────────────────────────────────────────────────────────────────────

# ERC-20 balanceOf(address) selector + 32B padded — calldata 池最常用(§5.2)
_EVM_BALANCEOF_SELECTOR = "0x70a08231"


def _take(inputs: dict, source: str, idx: int):
    """从 inputs[source] 池取第 idx 个值。池空/缺 → ParamSpecError(fail-fast, 非占位)。"""
    pool = inputs.get(source)
    if not pool:
        raise ParamSpecError(
            f"inputs pool {source!r} empty/missing — S1 输入供给未填该池, 拒绝占位兜底(R3)。"
            f" 现有池: {sorted(k for k, v in inputs.items() if v)}"
        )
    return pool[idx % len(pool)]


def _build_call_object(shape: str, inputs: dict, idx: int, extra: Optional[dict]) -> dict:
    """contract_call source → 合约调用对象(design §4.2 call_object, §5.2 calldata)。"""
    if shape == "evm_call":
        # eth_call/estimateGas: {to: <合约/账户>, data: <selector+args>}
        # 真值地基 §5.2: to 来自 contract_call 池(或退 account), data 用高频 selector
        to = None
        cc = inputs.get("contract_call")
        if cc:
            obj = cc[idx % len(cc)]
            if isinstance(obj, dict):
                return obj  # 池里已是完整 {to,data}
            to = obj
        if to is None:
            to = _take(inputs, "account", idx)  # 退账户地址作 to(余额查询语义)
        return {"to": to, "data": _EVM_BALANCEOF_SELECTOR + "0" * 64}
    if shape == "aptos_view":
        # Move view: {function, type_arguments, arguments}(§5.3 aptos /v1/view)
        return extra.get("value", {}) if extra else {}
    if shape == "tron_trigger":
        return extra.get("value", {}) if extra else {}
    raise ParamSpecError(f"call_object shape {shape!r} 未实现构造")


def _resolve_slot_value(slot: dict, inputs: dict, idx: int):
    """单个 slot → 实际值(按 source 从池取 / literal 直取 / contract_call 拼对象)。"""
    src = slot.get("source")
    if src == "literal":
        return slot["value"]
    if src == "config_object":
        return slot["value"]
    if src == "contract_call":
        co = slot.get("call_object", {})
        return _build_call_object(co.get("shape", "evm_call"), inputs, idx, slot)
    if src in ("account", "tx_hash", "block_height"):
        return _take(inputs, src, idx)
    raise ParamSpecError(f"slot source {src!r} 构造未实现")


def build_params_from_spec(spec: dict, inputs: dict, idx: int = 0):
    """param_spec + inputs → 实际请求参数(jsonrpc_list→list, jsonrpc_dict→dict)。

    rest_* transport 的 path/bindings 构造归 RestAdapter(S3.8 占位路由), 此处只处理
    jsonrpc_list/jsonrpc_dict(覆盖 24 PRESET 主力 + jsonrpc/bitcoin/substrate family)。
    """
    transport = spec.get("transport")
    if transport == "jsonrpc_list":
        return [_resolve_slot_value(s, inputs, idx) for s in spec.get("slots", [])]
    if transport == "jsonrpc_dict":
        return {k: _resolve_slot_value(f, inputs, idx) for k, f in spec.get("fields", {}).items()}
    # rest_* 由 adapter 侧用 path+bindings 构造(S3.8), 不在此构造 list/dict 参数
    raise ParamSpecError(
        f"transport {transport!r} 参数构造不在 build_params_from_spec(rest_* 走 adapter path 构造)"
    )


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
# source 集 = design §4.2 schema L388 + §4.3 维度C 权威定义(不自创细分)。
# 注: 沉淀把 block_hash(字符串)/block_number(整数) 统一归 block_height —— 服从权威源,
#     "是否该拆 block_hash vs block_number" 的设计问题记 §6.6.5 留 B2/C 处理,此处不私拆。
_VALID_SOURCES = {
    "account", "literal", "block_height", "tx_hash", "contract_call", "config_object",
    "business_id",  # 批3b自检修复(2026-06-05): 业务标识池(asset_id/pool_id/epoch),
                    # 与 block_height 语义不同(资产ID/池ID≠块高), 独立池避免占位污染变种。
}
# call_object.shape = design §4.2 L406 权威(3个), 不自创。
_VALID_SHAPES = {"evm_call", "aptos_view", "tron_trigger"}


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
    # rest_path / rest_query 的 path 占位符绑定校验(bindings)
    for placeholder, bind in spec.get("bindings", {}).items():
        src = bind.get("source")
        if src not in _VALID_SOURCES:
            raise ParamSpecError(
                f"method {method!r}: binding {placeholder!r} source {src!r} invalid, "
                f"must be one of {sorted(_VALID_SOURCES)}"
            )
        if src == "literal" and "value" not in bind:
            raise ParamSpecError(f"method {method!r}: literal binding {placeholder!r} missing 'value'")
    # rest_query 的 query 参数校验
    for qk, qv in spec.get("query", {}).items():
        src = qv.get("source")
        if src not in _VALID_SOURCES:
            raise ParamSpecError(f"method {method!r}: query {qk!r} source {src!r} invalid")
        if src == "literal" and "value" not in qv:
            raise ParamSpecError(f"method {method!r}: literal query {qk!r} missing 'value'")
    # rest_path/rest_query: path 来自 method 名(method 名本身是 path 模板, 如
    # "GET /cosmos/.../{addr}"), 或 _meta.rest_paths 映射(逻辑名→path)。spec 不强制 path。
    # 批3b: 占位替换/query 由 bindings/query 声明 source, rest.py 按 method名path + bindings 构造。
    # rest_body / POST 类需 http_method(GET 默认, POST 显式)
    hm = spec.get("http_method")
    if hm is not None and hm not in ("GET", "POST"):
        raise ParamSpecError(f"method {method!r}: http_method {hm!r} invalid, must be GET|POST")
    # call_object shape 校验(contract_call source 时)
    co = spec.get("call_object")
    if co is not None:
        shape = co.get("shape")
        if shape not in _VALID_SHAPES:
            raise ParamSpecError(
                f"method {method!r}: call_object shape {shape!r} invalid, must be one of {sorted(_VALID_SHAPES)}"
            )
