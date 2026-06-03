#!/usr/bin/env bash
# ci/check_adapter_family.sh
# CI 门 — 守护 adapter_family 治理缺口(rpc-method-abstraction-design.md §6.6.1, F1)。
#
# 背景: 36 链 chain template 都有 _meta.adapter_family, 但【无脚本自动生成】(grep 写入点=0),
#       靠人工填。fill_proxy_extraction.py / get_adapter(base.py) / fake-node fake_node.go 全靠它分派。
#       加新链时 adapter_family 漏填 → get_adapter raise / proxy_extraction 生成失败 / fake-node 启动失败。
#
# 为什么是"校验"不是"自动推断"(批判性纠正, §6.6.1):
#   adapter_family 是【协议族归属语义】= 领域知识, 无法从 rpc_protocol 可靠推断 —— 实证:
#     proto=rest 横跨 bitcoin_jsonrpc(bch)/rest(aptos)/tendermint(cosmos-hub) 3 family;
#     proto=mixed 横跨 5 family。bch 虽 HTTP 接口但协议是 Bitcoin Core fork → family=bitcoin_jsonrpc 非 rest。
#   故 family 归属人工权威定, 框架只 fail-fast 校验"必填 + 在 6 注册 family 内", 绝不启发式猜(会填错)。
#   与 skill §6 铁律"加新 adapter family 用 @register" 一致。
#
# 校验规则:
#   1. config/chains/*.json 每条必有 _meta.adapter_family(非空字符串)
#   2. adapter_family 必须在 6 注册 family 内(与 tools/chain_adapters/base.py _REGISTRY 一致)
#   3. 任一违反 → exit 1, 打印缺失/非法链名 + 修复提示

set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 6 注册 family (ADR-0005 后, list_adapters() 真实输出; 与 base.py 末尾 import 的 6 模块一致)
# 单一事实源: tools/chain_adapters/base.py 第 144 行 `from . import jsonrpc, rest, tendermint, bitcoin_jsonrpc, substrate, hedera_dual`
REGISTERED_FAMILIES="bitcoin_jsonrpc hedera_dual jsonrpc rest substrate tendermint"

CHAINS_DIR="config/chains"
FAIL=0
MISSING=()
ILLEGAL=()
OK=0

echo "=== adapter_family 治理门 (注册 family: $REGISTERED_FAMILIES) ==="

# 防漂移: 校验 base.py 实际注册的 family 与本脚本常量一致(防 base.py 加 family 后本门过期)
BASE_PY="tools/chain_adapters/base.py"
if [[ -f "$BASE_PY" ]]; then
    # 从 base.py 末尾 import 行提取实际注册的模块名
    actual="$(grep -oE 'from \. import [a-z_, ]+' "$BASE_PY" | sed -E 's/from \. import //' | tr ',' ' ' | tr -s ' ')"
    if [[ -n "$actual" ]]; then
        for fam in $actual; do
            fam_trim="$(echo "$fam" | tr -d ' ')"
            [[ -z "$fam_trim" ]] && continue
            if ! echo " $REGISTERED_FAMILIES " | grep -q " $fam_trim "; then
                echo "  ⚠️  base.py 注册了本门未知的 family: '$fam_trim' — 请同步更新本脚本 REGISTERED_FAMILIES"
                FAIL=$((FAIL+1))
            fi
        done
    fi
fi

for f in "$CHAINS_DIR"/*.json; do
    chain="$(basename "$f" .json)"
    fam="$(jq -r '._meta.adapter_family // ""' "$f" 2>/dev/null)"
    if [[ -z "$fam" || "$fam" == "null" ]]; then
        MISSING+=("$chain")
        FAIL=$((FAIL+1))
        continue
    fi
    if ! echo " $REGISTERED_FAMILIES " | grep -q " $fam "; then
        ILLEGAL+=("$chain($fam)")
        FAIL=$((FAIL+1))
        continue
    fi
    OK=$((OK+1))
done

echo "  ✅ $OK 链 adapter_family 合法"

if [[ ${#MISSING[@]} -gt 0 ]]; then
    echo "  ❌ ${#MISSING[@]} 链缺 _meta.adapter_family: ${MISSING[*]}"
    echo "     修复: 在 chain template 的 _meta 加 adapter_family(协议族归属, 人工定, 须是 6 family 之一)"
fi
if [[ ${#ILLEGAL[@]} -gt 0 ]]; then
    echo "  ❌ ${#ILLEGAL[@]} 链 adapter_family 非法(不在注册 family 内): ${ILLEGAL[*]}"
    echo "     合法值: $REGISTERED_FAMILIES"
fi

if [[ $FAIL -ne 0 ]]; then
    echo "❌ adapter_family 治理门失败 ($FAIL 项)"
    exit 1
fi
echo "✅ adapter_family 治理门通过 (36 链全有合法 family + 与 base.py 注册一致)"
