#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

entry="blockchain_node_benchmark.sh"
coordinator="monitoring/monitoring_coordinator.sh"
quality_checker="tools/framework_data_quality_checker.sh"

require_pattern() {
    local pattern="$1"
    local description="$2"

    if ! grep -qE "$pattern" "$entry"; then
        echo "FAIL: startup cleanup missing $description"
        echo "Pattern: $pattern"
        exit 1
    fi
}

require_pattern '^cleanup_memory_share_state\(\)' "memory-share cleanup function"
require_pattern '^cleanup_reused_runtime_files\(\)' "reused runtime file cleanup function"
require_pattern '^prepare_clean_runtime_state\(\)' "startup cleanup coordinator"
require_pattern '^prepare_clean_runtime_state$' "startup cleanup invocation"

for var in \
    LATEST_METRICS_FILE UNIFIED_METRICS_FILE QPS_STATUS_FILE \
    BOTTLENECK_STATUS_FILE BOTTLENECK_COUNTERS_FILE \
    UNIFIED_EVENTS_FILE EVENT_MANAGER_LOCK_FILE EVENT_NOTIFICATION_FILE \
    BLOCK_HEIGHT_CACHE_FILE NODE_HEALTH_CACHE_DIR \
    PERFORMANCE_LATEST_CSV PROXY_METHOD_CSV PROXY_SELF_CSV RPC_PROXY_LOG; do
    require_pattern "$var" "$var"
done

for tmp_file in \
    qps_test_status monitor_pids.txt monitoring_status.json \
    block_height_monitor.pid network_monitor.pid; do
    require_pattern "$tmp_file" "$tmp_file"
done

if ! grep -q "BLOCK_HEIGHT_CACHE_FILE" "$coordinator"; then
    echo "FAIL: monitoring coordinator cleanup does not use BLOCK_HEIGHT_CACHE_FILE"
    exit 1
fi

if ! grep -q "BLOCK_HEIGHT_CACHE_FILE" "$quality_checker"; then
    echo "FAIL: framework data quality checker does not use BLOCK_HEIGHT_CACHE_FILE"
    exit 1
fi

echo "✅ Runtime startup cleanup covers registered state and reused files"
