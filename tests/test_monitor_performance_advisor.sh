#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

TEST_ROOT="$(mktemp -d)"
cleanup() {
    rm -rf "$TEST_ROOT"
}
trap cleanup EXIT

log_debug() { :; }
log_warn() { :; }
log_info() { :; }
log_error() { :; }

get_unified_timestamp() {
    echo "2026-06-11 12:00:00"
}

export LOGS_DIR="$TEST_ROOT/logs"
export PERFORMANCE_LOG="$TEST_ROOT/logs/performance_impact.csv"
export SESSION_TIMESTAMP="20260611_120000"
export PERFORMANCE_MONITORING_ENABLED=true
export MAX_COLLECTION_TIME_MS=100
export BOTTLENECK_CPU_THRESHOLD=80
export BOTTLENECK_MEMORY_THRESHOLD=85
export MONITOR_INTERVAL=1
export SYSTEM_TOTAL_MEMORY_MB=1000

mkdir -p "$LOGS_DIR"

# shellcheck source=/dev/null
source monitoring/lib/monitor_utils.sh
# shellcheck source=/dev/null
source monitoring/lib/monitor_performance_advisor.sh

monitor_performance_impact "unit_function" 1000 1150 90 900

[[ -s "$PERFORMANCE_LOG" ]] || {
    echo "performance impact log was not written"
    exit 1
}

grep -q "unit_function" "$PERFORMANCE_LOG" || {
    echo "performance impact log missing function record"
    exit 1
}

grep -q "Monitoring performance warning" "$LOGS_DIR/unified_monitor.log" || {
    echo "warning was not written to unified monitor log"
    exit 1
}

generate_performance_impact_report
report="$LOGS_DIR/monitoring_performance_report_${SESSION_TIMESTAMP}.txt"
[[ -s "$report" ]] || {
    echo "performance impact report was not written"
    exit 1
}

grep -q "unit_function" "$report" || {
    echo "performance impact report missing function summary"
    exit 1
}

auto_performance_optimization_advisor

system_load="$(assess_system_load)"
if ! [[ "$system_load" =~ ^[0-9]+$ ]]; then
    echo "assess_system_load did not return an integer: $system_load"
    exit 1
fi

if [[ "$system_load" -lt 0 || "$system_load" -gt 100 ]]; then
    echo "assess_system_load out of range: $system_load"
    exit 1
fi

echo "✅ monitor_performance_advisor preserves performance impact/report contracts"
