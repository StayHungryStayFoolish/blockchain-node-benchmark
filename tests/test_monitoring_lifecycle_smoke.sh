#!/usr/bin/env bash
set -eo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

TEST_ROOT="$(mktemp -d)"
COORDINATOR_PID=""

cleanup() {
    set +e
    if [[ -n "${TMP_DIR:-}" ]]; then
        rm -f "$TMP_DIR/qps_test_status" "$TMP_DIR/qps_test_status.tmp"
    fi
    if [[ -n "$COORDINATOR_PID" ]] && kill -0 "$COORDINATOR_PID" 2>/dev/null; then
        kill "$COORDINATOR_PID" 2>/dev/null
        wait "$COORDINATOR_PID" 2>/dev/null
    fi
    rm -rf "$TEST_ROOT"
}
trap cleanup EXIT

wait_for() {
    local description="$1"
    local timeout="$2"
    local predicate="$3"
    local start now
    start="$(date +%s)"

    while true; do
        if bash -c "$predicate"; then
            echo "✅ $description"
            return 0
        fi
        now="$(date +%s)"
        if (( now - start >= timeout )); then
            echo "FAIL: timed out waiting for $description"
            echo "--- coordinator log ---"
            cat "$TEST_ROOT/coordinator.log" 2>/dev/null || true
            echo "--- unified log ---"
            cat "${LOGS_DIR:-$TEST_ROOT}/unified_monitor.log" 2>/dev/null || true
            echo "--- block height log/csv ---"
            ls -la "${LOGS_DIR:-$TEST_ROOT}" 2>/dev/null || true
            return 1
        fi
        sleep 1
    done
}

export BLOCKCHAIN_BENCHMARK_DATA_DIR="$TEST_ROOT/result"
export MEMORY_SHARE_DIR="$TEST_ROOT/memory"
export NODE_HEALTH_CACHE_DIR="$MEMORY_SHARE_DIR/node_health_cache"
export SESSION_TIMESTAMP="20260611_120000"
export BLOCKCHAIN_NODE="solana"
export LOCAL_RPC_URL="http://127.0.0.1:9"
export MAINNET_RPC_URL="http://127.0.0.1:9"
export BLOCK_HEIGHT_CURL_TIMEOUT=1
export ENA_MONITOR_ENABLED=false
export FORCE_CONFIG_RELOAD=true

set +e +u
# shellcheck source=/dev/null
source config/config_loader.sh >"$TEST_ROOT/config_loader.log" 2>&1
config_rc=$?
set -e
set -u
if [[ "$config_rc" -ne 0 ]]; then
    echo "FAIL: config_loader.sh failed with rc=$config_rc"
    cat "$TEST_ROOT/config_loader.log" 2>/dev/null || true
    exit "$config_rc"
fi

rm -rf "$DATA_DIR" "$MEMORY_SHARE_DIR"
mkdir -p "$LOGS_DIR" "$REPORTS_DIR" "$VEGETA_RESULTS_DIR" "$TMP_DIR" "$MEMORY_SHARE_DIR" "$NODE_HEALTH_CACHE_DIR"

export MONITOR_PIDS_FILE="${TMP_DIR}/monitor_pids.txt"
export MONITOR_STATUS_FILE="${TMP_DIR}/monitoring_status.json"

echo "running" > "$TMP_DIR/qps_test_status"

env -u SHELLOPTS bash monitoring/monitoring_coordinator.sh start >"$TEST_ROOT/coordinator.log" 2>&1 &
COORDINATOR_PID=$!

wait_for "coordinator process is running" 5 "kill -0 '$COORDINATOR_PID' 2>/dev/null"
wait_for "monitor PID registry is populated" 15 "[[ -s '$MONITOR_PIDS_FILE' ]]"
wait_for "performance_latest.csv has at least one data row" 20 "[[ -e '$PERFORMANCE_LATEST_CSV' ]] && [[ \$(wc -l < '$PERFORMANCE_LATEST_CSV') -gt 1 ]]"
wait_for "latest_metrics.json is written" 20 "[[ -s '$LATEST_METRICS_FILE' ]]"
wait_for "unified_metrics.json is written" 20 "[[ -s '$UNIFIED_METRICS_FILE' ]]"
wait_for "sample_count is written" 20 "[[ -s '$MEMORY_SHARE_DIR/sample_count' ]]"
wait_for "block height CSV has at least one data row" 25 "[[ -s '$BLOCK_HEIGHT_DATA_FILE' ]] && [[ \$(wc -l < '$BLOCK_HEIGHT_DATA_FILE') -gt 1 ]]"

rm -f "$TMP_DIR/qps_test_status"

wait_for "coordinator exits after lifecycle marker removal" 20 "! kill -0 '$COORDINATOR_PID' 2>/dev/null"
COORDINATOR_PID=""

echo "✅ monitoring lifecycle smoke test passed"
