#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

export BLOCKCHAIN_BENCHMARK_DATA_DIR="$TEST_ROOT/result"
export SESSION_TIMESTAMP="20260611_120000"
export BLOCKCHAIN_NODE="solana"
export RPC_MODE="mixed"

# config_loader.sh is not authored for nounset/errexit mode; keep this test
# focused on runtime path registry semantics rather than local platform probes.
set +eu
# shellcheck source=/dev/null
source config/config_loader.sh >"$TEST_ROOT/config_loader.log" 2>&1
set -eu

current_dir="$BLOCKCHAIN_BENCHMARK_DATA_DIR/current"
logs_dir="$current_dir/logs"
tmp_dir="$current_dir/tmp"
memory_dir="/dev/shm/blockchain-node-benchmark"

assert_eq() {
    local actual="$1"
    local expected="$2"
    local label="$3"

    if [[ "$actual" != "$expected" ]]; then
        echo "FAIL: $label"
        echo "  expected: $expected"
        echo "  actual:   $actual"
        echo "Config loader output:"
        cat "$TEST_ROOT/config_loader.log"
        exit 1
    fi
}

assert_eq "$UNIFIED_LOG" "$logs_dir/performance_${SESSION_TIMESTAMP}.csv" "UNIFIED_LOG"
assert_eq "$PERFORMANCE_LATEST_CSV" "$logs_dir/performance_latest.csv" "PERFORMANCE_LATEST_CSV"
assert_eq "$MONITORING_OVERHEAD_LOG" "$logs_dir/monitoring_overhead_${SESSION_TIMESTAMP}.csv" "MONITORING_OVERHEAD_LOG"
assert_eq "$PROXY_METHOD_CSV" "$logs_dir/proxy_method.csv" "PROXY_METHOD_CSV"
assert_eq "$PROXY_SELF_CSV" "$logs_dir/proxy_self.csv" "PROXY_SELF_CSV"
assert_eq "$RPC_PROXY_LOG" "$logs_dir/rpc_proxy.log" "RPC_PROXY_LOG"
assert_eq "$NETWORK_CSV" "$logs_dir/network_${SESSION_TIMESTAMP}.csv" "NETWORK_CSV"
assert_eq "$NETWORK_PID_FILE" "$tmp_dir/network_monitor.pid" "NETWORK_PID_FILE"
assert_eq "$LATEST_METRICS_FILE" "$memory_dir/latest_metrics.json" "LATEST_METRICS_FILE"
assert_eq "$UNIFIED_METRICS_FILE" "$memory_dir/unified_metrics.json" "UNIFIED_METRICS_FILE"
assert_eq "$BLOCK_HEIGHT_CACHE_FILE" "$memory_dir/block_height_monitor_cache.json" "BLOCK_HEIGHT_CACHE_FILE"
assert_eq "$QPS_STATUS_FILE" "$memory_dir/qps_status.json" "QPS_STATUS_FILE"
assert_eq "$BOTTLENECK_STATUS_FILE" "$memory_dir/bottleneck_status.json" "BOTTLENECK_STATUS_FILE"
assert_eq "$BOTTLENECK_COUNTERS_FILE" "$memory_dir/bottleneck_counters.json" "BOTTLENECK_COUNTERS_FILE"
assert_eq "$NODE_HEALTH_CACHE_DIR" "$memory_dir/node_health_cache" "NODE_HEALTH_CACHE_DIR"
assert_eq "$UNIFIED_EVENTS_FILE" "$memory_dir/unified_events.json" "UNIFIED_EVENTS_FILE"
assert_eq "$EVENT_MANAGER_LOCK_FILE" "$memory_dir/event_manager.lock" "EVENT_MANAGER_LOCK_FILE"
assert_eq "$EVENT_NOTIFICATION_FILE" "$memory_dir/event_notification.json" "EVENT_NOTIFICATION_FILE"

for exported_var in \
    UNIFIED_LOG PERFORMANCE_LATEST_CSV PROXY_METHOD_CSV PROXY_SELF_CSV RPC_PROXY_LOG \
    NETWORK_CSV NETWORK_PID_FILE LATEST_METRICS_FILE UNIFIED_METRICS_FILE \
    BLOCK_HEIGHT_CACHE_FILE QPS_STATUS_FILE BOTTLENECK_STATUS_FILE BOTTLENECK_COUNTERS_FILE NODE_HEALTH_CACHE_DIR \
    UNIFIED_EVENTS_FILE EVENT_MANAGER_LOCK_FILE EVENT_NOTIFICATION_FILE; do
    if ! export -p | grep -q "declare -x ${exported_var}="; then
        echo "FAIL: $exported_var is not exported"
        exit 1
    fi
done

override_memory_dir="$TEST_ROOT/shared-memory"
override_output=$(
    MEMORY_SHARE_DIR="$override_memory_dir" \
    BLOCKCHAIN_BENCHMARK_DATA_DIR="$TEST_ROOT/override-result" \
    SESSION_TIMESTAMP="20260611_120001" \
    BLOCKCHAIN_NODE="solana" \
    RPC_MODE="mixed" \
    bash -lc '
        set +eu
        unset CONFIG_ALREADY_LOADED
        export FORCE_CONFIG_RELOAD=true
        unset LATEST_METRICS_FILE UNIFIED_METRICS_FILE BLOCK_HEIGHT_CACHE_FILE QPS_STATUS_FILE BOTTLENECK_STATUS_FILE BOTTLENECK_COUNTERS_FILE NODE_HEALTH_CACHE_DIR UNIFIED_EVENTS_FILE EVENT_MANAGER_LOCK_FILE EVENT_NOTIFICATION_FILE
        source config/config_loader.sh >/dev/null 2>&1
        set -eu
        printf "%s|%s|%s" "$MEMORY_SHARE_DIR" "$LATEST_METRICS_FILE" "$BLOCK_HEIGHT_CACHE_FILE"
    '
)
assert_eq "$override_output" "${override_memory_dir}|${override_memory_dir}/latest_metrics.json|${override_memory_dir}/block_height_monitor_cache.json" "MEMORY_SHARE_DIR override"

echo "✅ Runtime path registry variables are exported and point to expected locations"
