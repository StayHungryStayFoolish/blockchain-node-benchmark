#!/usr/bin/env bash
# tools/e2e_smoke_chain_matrix.sh
# v1.4.6 — chain-template-driven matrix runner.
#
# Discovers chains automatically from config/chains/*.json (no hardcoded
# list). Each chain runs e2e_smoke.sh with:
#   - MOCK_CHAIN     = filename stem (e.g. "ethereum" from ethereum.json)
#   - MOCK_PORT      = sequential port starting at $BASE_PORT
#   - CHAIN_CONFIG   = absolute path to the JSON (triggers the gate)
#
# Per-chain failure surfaces individually (not all-or-nothing).
#
# ENV OVERRIDES:
#   BASE_PORT=29000           # starting port (default 29000, avoids 8080/3000)
#   ONLY_CHAINS="a,b,c"       # comma-separated subset (substring match on stem)
#   SKIP_CHAINS="x,y"         # comma-separated exclude list
#   DURATION_SEC=5            # passed through to each smoke run (default 5)
#   WORKLOAD_CAP_MIB=4        # passed through (default 4 MiB = fast)
#   PARALLEL=0                # 1 = parallel (NOT recommended — GCE shared)
#   FAIL_FAST=0               # 1 = stop on first chain fail
#
# Per-chain artifacts at /tmp/e2e_smoke_chain_matrix/<chain>.log
# Exit 0 iff every chain PASS.
# =====================================================================
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_ROOT"

CHAINS_DIR="$REPO_ROOT/config/chains"
LOG_DIR="/tmp/e2e_smoke_chain_matrix"
mkdir -p "$LOG_DIR"

BASE_PORT="${BASE_PORT:-29000}"
ONLY_CHAINS="${ONLY_CHAINS:-}"
SKIP_CHAINS="${SKIP_CHAINS:-}"
DURATION_SEC="${DURATION_SEC:-5}"
WORKLOAD_CAP_MIB="${WORKLOAD_CAP_MIB:-4}"
PARALLEL="${PARALLEL:-0}"
FAIL_FAST="${FAIL_FAST:-0}"

if [[ ! -d "$CHAINS_DIR" ]]; then
  echo "ERROR: $CHAINS_DIR not found" >&2; exit 2
fi

# Discover chains
mapfile -t ALL_CHAINS < <(
  find "$CHAINS_DIR" -maxdepth 1 -name '*.json' -type f -printf '%f\n' \
    | sed 's/\.json$//' | sort
)
if [[ ${#ALL_CHAINS[@]} -eq 0 ]]; then
  echo "ERROR: no chain JSON files in $CHAINS_DIR" >&2; exit 2
fi

# Apply ONLY / SKIP filters (substring match for ONLY, exact for SKIP)
CHAINS=()
IFS=',' read -ra ONLY_ARR <<< "$ONLY_CHAINS"
IFS=',' read -ra SKIP_ARR <<< "$SKIP_CHAINS"
for c in "${ALL_CHAINS[@]}"; do
  if [[ -n "$ONLY_CHAINS" ]]; then
    keep=0
    for o in "${ONLY_ARR[@]}"; do
      [[ -n "$o" && "$c" == *"$o"* ]] && keep=1 && break
    done
    [[ $keep -eq 0 ]] && continue
  fi
  skip=0
  for s in "${SKIP_ARR[@]}"; do
    [[ -n "$s" && "$c" == "$s" ]] && skip=1 && break
  done
  [[ $skip -eq 1 ]] && continue
  CHAINS+=("$c")
done

if [[ ${#CHAINS[@]} -eq 0 ]]; then
  echo "ERROR: filter left 0 chains (ONLY=$ONLY_CHAINS SKIP=$SKIP_CHAINS)" >&2; exit 2
fi

echo "═══════════════════════════════════════════════════════════════════════"
echo "  e2e_smoke chain-template matrix — ${#CHAINS[@]} chain(s) discovered"
echo "  base_port=$BASE_PORT  duration=${DURATION_SEC}s  cap=${WORKLOAD_CAP_MIB}MiB"
echo "═══════════════════════════════════════════════════════════════════════"

run_one() {
  local chain="$1"
  local port="$2"
  local log="$LOG_DIR/${chain}.log"
  local cfg="$CHAINS_DIR/${chain}.json"

  if MOCK_CHAIN="$chain" MOCK_PORT="$port" \
     CHAIN_CONFIG="$cfg" \
     DURATION_SEC="$DURATION_SEC" WORKLOAD_CAP_MIB="$WORKLOAD_CAP_MIB" \
     SKIP_HTML=1 \
     timeout 90 bash "$SCRIPT_DIR/e2e_smoke.sh" > "$log" 2>&1; then
    echo "PASS"
    return 0
  else
    local rc=$?
    echo "FAIL (exit=$rc)"
    return "$rc"
  fi
}

total_pass=0
total_fail=0
failed_chains=()
results=""
i=0

for chain in "${CHAINS[@]}"; do
  port=$((BASE_PORT + i))
  i=$((i + 1))
  printf "▸ %-14s (port=%5d, cfg=config/chains/%s.json) ... " \
    "$chain" "$port" "$chain"

  if run_one "$chain" "$port"; then
    total_pass=$((total_pass + 1))
    results+="  PASS  $chain  (port $port)"$'\n'
  else
    rc=$?
    total_fail=$((total_fail + 1))
    failed_chains+=("$chain")
    results+="  FAIL  $chain  (port $port, exit=$rc, log $LOG_DIR/${chain}.log)"$'\n'
    # Show last 6 lines of failing log inline so the matrix output is self-debugging
    while IFS= read -r line; do
      results+="        | $line"$'\n'
    done < <(tail -6 "$LOG_DIR/${chain}.log" 2>/dev/null)
    [[ "$FAIL_FAST" == "1" ]] && { echo "FAIL_FAST=1 → stopping early"; break; }
  fi

  # Defensive cleanup — kill any orphaned mock_rpc_server for this chain
  pkill -f "mock_rpc_server.py --chain $chain" 2>/dev/null || true
  sleep 1
done

echo ""
echo "───────────────────────────────────────────────────────────────────────"
echo "$results"
echo "───────────────────────────────────────────────────────────────────────"
echo "  TOTAL: $total_pass PASS / $total_fail FAIL  (of ${#CHAINS[@]} run)"

if [[ $total_fail -gt 0 ]]; then
  echo ""
  echo "  FAILED CHAINS: ${failed_chains[*]}"
  echo "  Inspect logs at: $LOG_DIR/<chain>.log"
  exit 1
fi
exit 0
