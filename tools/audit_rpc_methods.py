#!/usr/bin/env python3
"""
RPC Method Audit Tool — R1-PRIME 实证工具

为每个链的每个 RPC method 做 4 层证据验证:
  L1 — 文档判别(URL 路径是否 deprecated)
  L2 — doc cURL 实证(用官方 doc 示例 POST 到 mainnet,验 method 可用)
  L3 — schema 比对(对 tier-mid+ method 验框架 adapter 访问的字段在 response 里)
  L4 — 错误传递语义(对 tier-high method 用故意非法 input 触发 error,看错误如何返回)

输入:docs/audit/_method-inventory.json (Phase A 产物)
输出:docs/audit/method-status-matrix.md + docs/audit/_raw-evidence/*.json

用法:
    python3 tools/audit_rpc_methods.py [--chains solana,ethereum] [--methods getBalance,eth_gasPrice]

风险分层:
  tier-low  : L1 + L2
  tier-mid  : L1 + L2 + L3
  tier-high : L1 + L2 + L3 + L4
"""
import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INVENTORY = REPO / "docs/audit/_method-inventory.json"
EVIDENCE_DIR = REPO / "docs/audit/_raw-evidence"
MATRIX_OUT = REPO / "docs/audit/method-status-matrix.md"

# Rate limit:每 method 间隔(秒)
RATE_LIMIT_DELAY = 0.5
# Timeout
HTTP_TIMEOUT = 15
# Retry on rate-limit
RATE_LIMIT_RETRIES = 1
RATE_LIMIT_BACKOFF = 5


# ============================================================
# Param 构造器 — 把 param_format + target_address 转 RPC params
# ============================================================
def build_params(method_name: str, param_format: str, target_address: str) -> list:
    """根据 param_format 字符串构造 RPC params 数组。"""
    if param_format == "no_params":
        return []
    if param_format == "single_address":
        return [target_address]
    if param_format == "address_latest":
        # eth_getBalance / eth_getTransactionCount 等 EVM 标准
        return [target_address, "latest"]
    if param_format == "latest_address":
        # starknet_getClassAt / starknet_getNonce
        return ["latest", target_address]
    if param_format == "address_key_latest":
        # starknet_getStorageAt(address, key, block_id)
        return [target_address, "0x0", "latest"]
    if param_format == "address_with_options":
        # sui_getObject(object_id, options)
        return [target_address, {"showType": True, "showOwner": True}]
    # 默认:no params
    return []


# ============================================================
# JSON-RPC POST
# ============================================================
def jsonrpc_post(endpoint: str, method: str, params: list, request_id: int = 1) -> dict:
    """POST jsonrpc 2.0 请求,返回 (status_code, response_json, error_string)。"""
    body = json.dumps({
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": params,
    }).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "blockchain-node-benchmark-audit/1.0"},
        method="POST",
    )
    for attempt in range(RATE_LIMIT_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                body_bytes = resp.read()
                try:
                    return {"http_status": resp.status, "json": json.loads(body_bytes), "raw": body_bytes.decode("utf-8", errors="replace"), "error": None}
                except json.JSONDecodeError as e:
                    return {"http_status": resp.status, "json": None, "raw": body_bytes.decode("utf-8", errors="replace"), "error": f"JSON decode: {e}"}
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < RATE_LIMIT_RETRIES:
                time.sleep(RATE_LIMIT_BACKOFF)
                continue
            try:
                body_str = e.read().decode("utf-8", errors="replace")
            except Exception:
                body_str = ""
            return {"http_status": e.code, "json": None, "raw": body_str, "error": f"HTTP {e.code}: {e.reason}"}
        except urllib.error.URLError as e:
            return {"http_status": None, "json": None, "raw": "", "error": f"URLError: {e.reason}"}
        except Exception as e:
            return {"http_status": None, "json": None, "raw": "", "error": f"{type(e).__name__}: {e}"}
    return {"http_status": None, "json": None, "raw": "", "error": "Exhausted retries"}


# ============================================================
# L1 — 文档判别
# ============================================================
def l1_doc_check(chain_type: str, doc_base: str, method: str) -> dict:
    """L1: 拉文档页 URL,判断 method 是否 deprecated。"""
    if chain_type == "solana":
        # Solana 每 method 一页,URL = /docs/rpc/http/{method_lower};deprecated 的会 redirect 到 /docs/rpc/deprecated/{method_lower}
        url = doc_base.format(method_lower=method.lower())
        try:
            with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT) as resp:
                final_url = resp.url
                if "/deprecated/" in final_url:
                    return {"status": "DEPRECATED", "evidence_url": final_url, "method": "URL path contains /deprecated/"}
                return {"status": "ACTIVE", "evidence_url": final_url, "method": "URL path in /http/, not /deprecated/"}
        except urllib.error.HTTPError as e:
            return {"status": "DOC_404", "evidence_url": url, "method": f"HTTP {e.code}"}
        except Exception as e:
            return {"status": "DOC_ERROR", "evidence_url": url, "method": f"{type(e).__name__}: {e}"}
    elif chain_type in ("ethereum", "bsc", "base", "polygon", "scroll"):
        # EVM 用 ethereum.github.io/execution-apis/ — single page spec,我们已知 grep "deprecat" = 0 命中
        # 这里更严格:fetch spec,看 method 名是否在 spec
        url = doc_base
        try:
            with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                if method in body:
                    return {"status": "ACTIVE", "evidence_url": url, "method": f"'{method}' found in execution-apis spec"}
                else:
                    return {"status": "NOT_IN_SPEC", "evidence_url": url, "method": f"'{method}' NOT found in execution-apis spec body"}
        except Exception as e:
            return {"status": "DOC_ERROR", "evidence_url": url, "method": f"{type(e).__name__}: {e}"}
    elif chain_type == "starknet":
        # Starknet 用 openrpc.json
        url = doc_base
        try:
            # 注意:GitHub blob URL 不是 raw,改取 raw
            raw_url = url.replace("github.com/", "raw.githubusercontent.com/").replace("/blob/", "/")
            with urllib.request.urlopen(raw_url, timeout=HTTP_TIMEOUT) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                if method in body:
                    return {"status": "ACTIVE", "evidence_url": raw_url, "method": f"'{method}' found in openrpc.json"}
                else:
                    return {"status": "NOT_IN_SPEC", "evidence_url": raw_url, "method": f"'{method}' NOT found in openrpc.json"}
        except Exception as e:
            return {"status": "DOC_ERROR", "evidence_url": url, "method": f"{type(e).__name__}: {e}"}
    elif chain_type == "sui":
        # Sui 文档没有稳定的 per-method URL,跳过 L1(留 L2 来验)
        return {"status": "SKIPPED", "evidence_url": doc_base, "method": "Sui docs structure不易自动判别,L1 skipped, rely on L2"}
    else:
        return {"status": "SKIPPED", "evidence_url": "", "method": f"Unknown chain_type: {chain_type}"}


# ============================================================
# L2 — endpoint POST(method 可用性)
# ============================================================
def l2_endpoint_check(endpoint: str, method: str, params: list) -> dict:
    """L2: 真 POST,验 method 在 mainnet 可用(不返 jsonrpc error)。"""
    resp = jsonrpc_post(endpoint, method, params)
    if resp["error"]:
        return {"status": "ENDPOINT_ERROR", "detail": resp["error"], "raw_excerpt": resp["raw"][:300]}
    if resp["json"] is None:
        return {"status": "INVALID_RESPONSE", "detail": "Response not JSON", "raw_excerpt": resp["raw"][:300]}
    j = resp["json"]
    if "error" in j:
        err = j["error"]
        # JSON-RPC error — method 不可用或参数错
        err_code = err.get("code") if isinstance(err, dict) else None
        err_msg = err.get("message") if isinstance(err, dict) else str(err)
        # -32601 = method not found
        if err_code == -32601:
            return {"status": "METHOD_NOT_FOUND", "detail": f"code=-32601: {err_msg}", "raw_excerpt": json.dumps(j)[:300]}
        return {"status": "RPC_ERROR", "detail": f"code={err_code}: {err_msg}", "raw_excerpt": json.dumps(j)[:300]}
    if "result" in j:
        return {"status": "PASS", "detail": "result returned", "result_type": type(j["result"]).__name__, "result_excerpt": json.dumps(j["result"])[:200]}
    return {"status": "UNKNOWN_SHAPE", "detail": "No result and no error", "raw_excerpt": json.dumps(j)[:300]}


# ============================================================
# L3 — schema 比对(对 tier-mid+ method)
# ============================================================
# 框架 adapter parse 代码访问的字段路径(人工提取自 fetch_active_accounts.py)
# 注意:这里只填 tier-mid+ 的 method;tier-low 的不做 L3
ADAPTER_EXPECTED_FIELDS = {
    # Solana
    "getAccountInfo": ["result.value"],  # adapter 检查 value 是否非 None,深度访问较少
    "getTokenAccountBalance": ["result.value", "result.value.amount"],
    "getRecentBlockhash": ["result.value", "result.value.blockhash"],  # 已 deprecated,但仍验
    "getLatestBlockhash": ["result.value", "result.value.blockhash"],  # 取代 getRecentBlockhash
    "getSignaturesForAddress": ["result"],  # 返 array
    "getTransaction": ["result.transaction", "result.meta"],
    # EVM
    "eth_gasPrice": ["result"],  # 返 hex string,L3 只验 result 存在
    "eth_getLogs": ["result"],   # 返 array of {topics, data, blockNumber, transactionHash}
    "eth_getTransactionByHash": ["result.hash", "result.blockNumber", "result.from", "result.to"],
    # Starknet
    "starknet_getClassAt": ["result"],
    "starknet_getEvents": ["result.events"],
    "starknet_getTransactionByHash": ["result"],
    # Sui
    "sui_getObject": ["result.data"],
    "sui_getObjectsOwnedByAddress": ["result"],
    "suix_getOwnedObjects": ["result.data"],
    "sui_getTransactionBlock": ["result"],
    "suix_queryTransactionBlocks": ["result.data"],
}


def _access_path(obj, path: str):
    """访问 'result.value.amount' 这样的路径,返回 (exists, value)。"""
    keys = path.split(".")
    cur = obj
    for k in keys:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        elif isinstance(cur, list) and k == "result":
            # special case: result 已经被 extract,但 path 还是从 result 开始
            continue
        else:
            return (False, None)
    return (True, cur)


def l3_schema_check(method: str, l2_result: dict) -> dict:
    """L3: 验框架 adapter 访问的字段在 response 里存在。"""
    if l2_result["status"] != "PASS":
        return {"status": "SKIPPED", "detail": "L2 not PASS"}
    expected = ADAPTER_EXPECTED_FIELDS.get(method)
    if not expected:
        return {"status": "SKIPPED", "detail": "No expected fields defined for this method"}
    # l2_result 里 result_excerpt 是截断的,需要重新 fetch full response
    # 简化:L3 比对只检查 result 是否有结构(top-level result 已确认)
    # 真正深度 L3 需要 raw response;这里 mark 为 NEEDS_FULL_RESPONSE
    return {"status": "NEEDS_FULL_PAYLOAD", "detail": f"Expected fields: {expected}", "_todo": "需要在 L2 阶段就保留 full response 以便深度访问"}


# ============================================================
# L4 — 错误传递语义(对 tier-high)
# ============================================================
def l4_error_semantics_check(endpoint: str, method: str) -> dict:
    """L4: 故意发非法 input,看错误怎么返回。"""
    # 用一个明显非法的 param 触发错误
    bad_params = ["0xINVALID_NOT_HEX"]
    resp = jsonrpc_post(endpoint, method, bad_params)
    if resp["error"]:
        return {"status": "TRANSPORT_ERROR", "detail": resp["error"]}
    if resp["json"] is None:
        return {"status": "INVALID_RESPONSE", "detail": "Response not JSON"}
    j = resp["json"]
    if "error" in j:
        err = j["error"]
        err_code = err.get("code") if isinstance(err, dict) else None
        return {
            "status": "ERROR_THROWN_AT_RPC_LAYER",
            "detail": "Bad params triggered JSON-RPC error (top-level error field) — framework needs to handle this",
            "error_code": err_code,
            "error_msg": (err.get("message") if isinstance(err, dict) else str(err))[:200],
        }
    if "result" in j:
        # 错误塞进 result(如 Solana simulateTransaction 模式)
        return {
            "status": "ERROR_SILENT_OR_IN_RESULT",
            "detail": "Bad params did NOT trigger JSON-RPC error — error may be silent or embedded in result",
            "result_excerpt": json.dumps(j["result"])[:300],
        }
    return {"status": "UNKNOWN", "detail": "Neither error nor result"}


# ============================================================
# Main audit loop
# ============================================================
def audit_chain(chain_name: str, chain_cfg: dict, filter_methods=None) -> list:
    """Audit 一条链所有 method,返回每 method 的 result 字典列表。"""
    results = []
    endpoint = chain_cfg["official_rpc"]
    doc_base = chain_cfg["doc_base"]
    chain_type = chain_cfg["chain_type"]
    target_address = chain_cfg["target_address"]
    
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Chain: {chain_name} | Endpoint: {endpoint}", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    
    for m in chain_cfg["methods"]:
        method_name = m["name"]
        if filter_methods and method_name not in filter_methods:
            continue
        tier = m["risk_tier"]
        param_format = m.get("param_format")
        params = build_params(method_name, param_format, target_address) if param_format else []
        
        print(f"  [{tier}] {method_name} ...", end=" ", file=sys.stderr, flush=True)
        
        # L1
        l1 = l1_doc_check(chain_type, doc_base, method_name)
        # L2 — always do
        l2 = l2_endpoint_check(endpoint, method_name, params)
        # L3 — only tier-mid+
        l3 = None
        if tier in ("tier-mid", "tier-high"):
            l3 = l3_schema_check(method_name, l2)
        # L4 — only tier-high
        l4 = None
        if tier == "tier-high":
            l4 = l4_error_semantics_check(endpoint, method_name)
        
        # Overall verdict
        if l1["status"] == "DEPRECATED":
            verdict = "🔴 P0_DEPRECATED"
        elif l1["status"] == "NOT_IN_SPEC":
            verdict = "🟡 P1_NOT_IN_SPEC"
        elif l2["status"] == "METHOD_NOT_FOUND":
            verdict = "🔴 P0_METHOD_NOT_FOUND_ON_ENDPOINT"
        elif l2["status"] in ("ENDPOINT_ERROR", "INVALID_RESPONSE", "RPC_ERROR"):
            verdict = f"🟡 P1_{l2['status']}"
        elif l2["status"] == "PASS":
            verdict = "🟢 PASS"
        else:
            verdict = "⚪ UNKNOWN"
        
        result = {
            "chain": chain_name,
            "method": method_name,
            "tier": tier,
            "param_format": param_format,
            "params_sent": params,
            "verdict": verdict,
            "L1_doc": l1,
            "L2_endpoint": l2,
            "L3_schema": l3,
            "L4_error_semantics": l4,
        }
        results.append(result)
        
        print(verdict, file=sys.stderr)
        time.sleep(RATE_LIMIT_DELAY)
    
    return results


def render_matrix(all_results: list) -> str:
    """渲染 method-status-matrix.md。"""
    lines = ["# RPC Method Audit Status Matrix\n"]
    lines.append("**R1-PRIME 实证结果** — 基于 4 层证据(L1 文档判别 / L2 endpoint POST / L3 schema 比对 / L4 错误语义)\n")
    lines.append(f"**Total methods audited**: {len(all_results)}\n")
    lines.append("**Risk tier rules**:\n")
    lines.append("- `tier-low` : L1 + L2(简单读取,无 schema drift 风险)\n")
    lines.append("- `tier-mid` : L1 + L2 + L3(结构化读取,验框架访问字段在)\n")
    lines.append("- `tier-high`: L1 + L2 + L3 + L4(写入/事件/模拟,验错误传递语义)\n\n")
    
    # Summary
    verdict_counts = {}
    for r in all_results:
        v = r["verdict"]
        verdict_counts[v] = verdict_counts.get(v, 0) + 1
    lines.append("## Summary\n")
    lines.append("| Verdict | Count |\n|---|---:|\n")
    for v, c in sorted(verdict_counts.items()):
        lines.append(f"| {v} | {c} |\n")
    lines.append("\n")
    
    # Per-chain matrix
    by_chain = {}
    for r in all_results:
        by_chain.setdefault(r["chain"], []).append(r)
    
    for chain in by_chain:
        lines.append(f"## {chain}\n\n")
        lines.append("| Method | Tier | Verdict | L1 doc | L2 endpoint | L3 schema | L4 error |\n")
        lines.append("|---|---|---|---|---|---|---|\n")
        for r in by_chain[chain]:
            l1s = r["L1_doc"]["status"]
            l2s = r["L2_endpoint"]["status"]
            l3s = r["L3_schema"]["status"] if r["L3_schema"] else "—"
            l4s = r["L4_error_semantics"]["status"] if r["L4_error_semantics"] else "—"
            lines.append(f"| `{r['method']}` | {r['tier']} | {r['verdict']} | {l1s} | {l2s} | {l3s} | {l4s} |\n")
        lines.append("\n")
    
    # Detailed issues
    lines.append("## Detailed Issues (non-PASS)\n\n")
    for r in all_results:
        if "PASS" in r["verdict"]:
            continue
        lines.append(f"### {r['chain']} / `{r['method']}` — {r['verdict']}\n\n")
        lines.append(f"- **Risk tier**: {r['tier']}\n")
        lines.append(f"- **L1 doc**: {r['L1_doc']['status']} — {r['L1_doc'].get('method', '')}\n")
        lines.append(f"  - URL: {r['L1_doc'].get('evidence_url', '')}\n")
        lines.append(f"- **L2 endpoint**: {r['L2_endpoint']['status']} — {r['L2_endpoint'].get('detail', '')}\n")
        if r["L2_endpoint"].get("raw_excerpt"):
            lines.append(f"  - Raw excerpt: `{r['L2_endpoint']['raw_excerpt'][:200]}`\n")
        if r["L3_schema"]:
            lines.append(f"- **L3 schema**: {r['L3_schema']['status']} — {r['L3_schema'].get('detail', '')}\n")
        if r["L4_error_semantics"]:
            lines.append(f"- **L4 error semantics**: {r['L4_error_semantics']['status']} — {r['L4_error_semantics'].get('detail', '')}\n")
        lines.append("\n")
    
    return "".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chains", help="Comma-separated chain names; default = all in inventory")
    ap.add_argument("--methods", help="Comma-separated method names filter")
    ap.add_argument("--inventory", default=str(INVENTORY))
    ap.add_argument("--output", default=str(MATRIX_OUT))
    args = ap.parse_args()
    
    with open(args.inventory) as f:
        inv = json.load(f)
    
    filter_chains = set(args.chains.split(",")) if args.chains else None
    filter_methods = set(args.methods.split(",")) if args.methods else None
    
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    
    all_results = []
    for chain_name, chain_cfg in inv["chains"].items():
        if filter_chains and chain_name not in filter_chains:
            continue
        results = audit_chain(chain_name, chain_cfg, filter_methods)
        all_results.extend(results)
        # 落 raw evidence
        evidence_path = EVIDENCE_DIR / f"{chain_name}.json"
        with open(evidence_path, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
    
    # 渲染 matrix
    matrix = render_matrix(all_results)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        f.write(matrix)
    
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"✅ Audit complete: {len(all_results)} methods", file=sys.stderr)
    print(f"   Matrix: {args.output}", file=sys.stderr)
    print(f"   Raw evidence: {EVIDENCE_DIR}/", file=sys.stderr)


if __name__ == "__main__":
    main()
