#!/usr/bin/env bash
# tools/e2e_smoke_5evm_compat_matrix.sh
# S3-A: run e2e_smoke once per EVM-compat new chain (5 chains).
# Sibling of tools/e2e_smoke_8chain_matrix.sh — same pattern, different chain set.
#
# Chains: arbitrum, optimism, zksync-era, linea, avalanche-c
# All reuse handle_evm in mock_rpc_server.py (verified at lines 441-462
# of mock_rpc_server.py CHAIN_HANDLERS).

set -u
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

CHAINS=(arbitrum optimism zksync-era linea avalanche-c)

declare -A PORTS=(
    [arbitrum]=28552
    [optimism]=28553
    [zksync-era]=28554
    [linea]=28555
    [avalanche-c]=28556
)

results=""
total_pass=0
total_fail=0
failed_chains=()

echo "═══════════════════════════════════════════════════════════════════════"
echo "  S3-A — 5 EVM-compat chains e2e_smoke matrix"
echo "═══════════════════════════════════════════════════════════════════════"
echo ""

for chain in "${CHAINS[@]}"; do
    port="${PORTS[$chain]}"
    log_file="/tmp/e2e_smoke_${chain}.log"

    printf "▸ %-12s (port=%5d) ... " "$chain" "$port"

    if MOCK_CHAIN="$chain" MOCK_PORT="$port" \
       timeout 90 bash tools/e2e_smoke.sh > "$log_file" 2>&1; then
        echo "PASS"
        total_pass=$((total_pass + 1))
        results+="  PASS  $chain  (port $port, log $log_file)"$'\n'
    else
        rc=$?
        echo "FAIL (exit=$rc)"
        total_fail=$((total_fail + 1))
        failed_chains+=("$chain")
        results+="  FAIL  $chain  (port $port, exit=$rc, log $log_file)"$'\n'
        results+="$(tail -8 "$log_file" | sed 's/^/        | /')"$'\n'
    fi

    pkill -f "mock_rpc_server.py --chain $chain" 2>/dev/null || true
    sleep 1
done

echo ""
echo "───────────────────────────────────────────────────────────────────────"
echo "$results"
echo "───────────────────────────────────────────────────────────────────────"
echo "  TOTAL: $total_pass PASS / $total_fail FAIL  (out of ${#CHAINS[@]} chains)"

if [[ $total_fail -gt 0 ]]; then
    echo ""
    echo "  FAILED CHAINS: ${failed_chains[*]}"
    echo "  Inspect logs at: /tmp/e2e_smoke_<chain>.log"
fi
echo "═══════════════════════════════════════════════════════════════════════"

[[ $total_fail -eq 0 ]] && exit 0 || exit 1
