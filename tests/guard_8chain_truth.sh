#!/bin/bash
# tests/guard_8chain_truth.sh
# CI guard: prevent Aptos/Bitcoin re-introduction (v1.4.2 校正后铁律)
# 真 8 链来源: config/config_loader.sh:660 supported_blockchains
#   solana / ethereum / bsc / base / scroll / polygon / starknet / sui

set -euo pipefail
cd "$(dirname "$0")/.."

fail=0

echo "=== Guard 1: 代码层(.sh/.py/.json/.yaml)严禁 aptos/bitcoin 业务引用 ==="
# 例外: chain-as-plugin 未来若加链(目前 0),注释行允许提及历史变更
code_hits=$(grep -rEi 'aptos|bitcoin' . \
    --include='*.py' --include='*.sh' --include='*.json' --include='*.yaml' --include='*.yml' \
    2>/dev/null \
    | grep -vE 'analysis-notes|\.git|_archive|node_modules|tests/guard_8chain_truth\.sh' \
    | grep -vE '^[^:]+:\s*#.*[Bb]itcoin/[Aa]ptos\s+removed' \
    | grep -vE '^[^:]+:\s*#.*never in baseline' \
    || true)

if [[ -n "$code_hits" ]]; then
    echo "❌ Found aptos/bitcoin in code:"
    echo "$code_hits"
    fail=1
else
    echo "✓ no aptos/bitcoin in code"
fi

echo ""
echo "=== Guard 2: 真 8 链 supported_blockchains 数组完整 ==="
# config_loader.sh:660 supported_blockchains 是 function-local array,
# 不能 source 后用 declare 抓 — 改文本搜索验证
expected_chains="solana ethereum bsc base scroll polygon starknet sui"
all_present=1
for chain in $expected_chains; do
    if ! grep -qE "\"$chain\"" config/config_loader.sh 2>/dev/null; then
        echo "❌ $chain not found in config/config_loader.sh"
        all_present=0
    fi
done
# 额外:supported_blockchains 这一行必须包含全部 8 链
line=$(grep 'supported_blockchains=(' config/config_loader.sh || echo "")
if [[ -z "$line" ]]; then
    echo "❌ supported_blockchains= line not found"
    all_present=0
else
    for chain in $expected_chains; do
        if [[ "$line" != *"\"$chain\""* ]]; then
            echo "❌ supported_blockchains array missing $chain"
            all_present=0
        fi
    done
fi

if [[ $all_present -eq 1 ]]; then
    echo "✓ supported_blockchains line contains all 8 real chains"
else
    fail=1
fi

echo ""
echo "=== Guard 3: deployment_mode_detector.sh 不含 aptos-node/bitcoind ==="
if grep -E 'aptos-node|bitcoind' config/deployment_mode_detector.sh >/dev/null 2>&1; then
    echo "❌ found aptos-node or bitcoind in deployment_mode_detector.sh"
    fail=1
else
    echo "✓ clean"
fi

echo ""
echo "=== Guard 4: mock_rpc_server.py CHAIN_HANDLERS 覆盖真 8 链 ==="
missing=()
for chain in solana ethereum bsc base scroll polygon starknet sui; do
    if ! grep -qE "\"$chain\"\s*:" tools/mock_rpc_server.py 2>/dev/null; then
        missing+=("$chain")
    fi
done

if [[ ${#missing[@]} -gt 0 ]]; then
    echo "❌ mock_rpc_server.py CHAIN_HANDLERS missing: ${missing[*]}"
    fail=1
else
    echo "✓ all 8 chains in CHAIN_HANDLERS"
fi

echo ""
if [[ $fail -eq 0 ]]; then
    echo "✅ All 4 guards passed — real 8-chain truth preserved"
    exit 0
else
    echo "❌ Guard failures detected — see above"
    exit 1
fi
