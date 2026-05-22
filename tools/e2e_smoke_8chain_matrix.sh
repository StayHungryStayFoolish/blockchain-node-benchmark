#!/usr/bin/env bash
# tools/e2e_smoke_8chain_matrix.sh
# v1.4.6 Step C: run e2e_smoke once per supported chain (8 chains).
# Production-grade matrix runner — each chain gets its own port so
# parallel runs don't collide; each failure is reported individually
# so partial regressions are visible (not all-or-nothing).

set -u
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Real chain registry — sourced from CHAIN_HANDLERS in mock_rpc_server.py.
# DO NOT hardcode by domain reputation — grep the registry. Adding/removing
# a chain in mock_rpc_server.py without updating this list = parallel-entry
# trap variant. Verified 2026-05-22 against mock_rpc_server.py:413-422.
CHAINS=(solana ethereum bsc base polygon scroll starknet sui)

# Per-chain port allocation. Solana convention = 8899; others get sequential
# ports starting at 28xxx (avoid collision with anyone running a local node).
declare -A PORTS=(
    [solana]=28899
    [ethereum]=28545
    [bsc]=28546
    [base]=28547
    [polygon]=28548
    [scroll]=28549
    [starknet]=28550
    [sui]=28551
)

results=""
total_pass=0
total_fail=0
failed_chains=()

echo "═══════════════════════════════════════════════════════════════════════"
echo "  v1.4.6 Step C — 8-chain e2e_smoke matrix"
echo "═══════════════════════════════════════════════════════════════════════"
echo ""

for chain in "${CHAINS[@]}"; do
    port="${PORTS[$chain]}"
    log_file="/tmp/e2e_smoke_${chain}.log"

    printf "▸ %-10s (port=%5d) ... " "$chain" "$port"

    # Run e2e_smoke with chain-specific env. timeout 90s = same as
    # earlier validation (single-chain run was 33s; 90s gives headroom
    # for slower mock startup on first invocation).
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

    # Defensive cleanup — e2e_smoke does its own cleanup but if it crashes
    # mid-way we want to kill any orphaned mock_rpc_server.
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
