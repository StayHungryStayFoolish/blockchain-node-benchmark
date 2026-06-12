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

export LOGS_DIR="$TEST_ROOT/logs"
export MEMORY_SHARE_DIR="$TEST_ROOT/memory"
export LATEST_METRICS_FILE="$MEMORY_SHARE_DIR/latest_metrics.json"
export UNIFIED_METRICS_FILE="$MEMORY_SHARE_DIR/unified_metrics.json"
export UNIFIED_LOG="$TEST_ROOT/logs/performance.csv"
export LEDGER_DEVICE="/dev/sda"
export DATA_VOL_MAX_IOPS=10000
export DATA_VOL_MAX_THROUGHPUT=500
export OVERHEAD_CSV_HEADER="timestamp,cpu"
export BOTTLENECK_DISK_IOPS_THRESHOLD=80
export BOTTLENECK_DISK_THROUGHPUT_THRESHOLD=80
export BOTTLENECK_MEMORY_THRESHOLD=85

mkdir -p "$LOGS_DIR" "$MEMORY_SHARE_DIR"
touch "$LATEST_METRICS_FILE" "$UNIFIED_METRICS_FILE" "$MEMORY_SHARE_DIR/sample_count"

# shellcheck source=/dev/null
source monitoring/lib/monitor_utils.sh

[[ "$(validate_numeric_value 12.5 0)" == "12.5" ]] || {
    echo "validate_numeric_value did not preserve valid decimal"
    exit 1
}

[[ "$(validate_numeric_value abc 7)" == "7" ]] || {
    echo "validate_numeric_value did not use default for invalid input"
    exit 1
}

[[ "$(format_percentage 120 1)" == "100.0" ]] || {
    echo "format_percentage did not clamp high value"
    exit 1
}

[[ "$(format_percentage -1 1)" == "0.0" ]] || {
    echo "format_percentage did not clamp negative value"
    exit 1
}

[[ "$(sanitize_process_name 'bad,"name')" == "badname" ]] || {
    echo "sanitize_process_name did not remove CSV-sensitive characters"
    exit 1
}

is_command_available bash >/dev/null || {
    echo "is_command_available failed for bash"
    exit 1
}

[[ "${COMMAND_CACHE["bash"]:-}" == "1" ]] || {
    echo "command cache was not populated"
    exit 1
}

[[ "$(calculate_memory_percentage 256 1024)" == "25.00" ]] || {
    echo "calculate_memory_percentage mismatch"
    exit 1
}

safe_write_csv "$UNIFIED_LOG" "a,b,c"
grep -q "a,b,c" "$UNIFIED_LOG" || {
    echo "safe_write_csv did not append data"
    exit 1
}

basic_config_check >/dev/null

cleanup_monitor_processes
[[ ! -e "$LATEST_METRICS_FILE" && ! -e "$UNIFIED_METRICS_FILE" && ! -e "$MEMORY_SHARE_DIR/sample_count" ]] || {
    echo "cleanup_monitor_processes did not remove shared memory files"
    exit 1
}

echo "✅ monitor_utils preserves utility and cleanup contracts"
