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
log_error() { echo "$*" >&2; }

declare -A COMMAND_CACHE
is_command_available() {
    command -v "$1" >/dev/null 2>&1
}

monitor_performance_impact() {
    :
}

get_unified_timestamp() {
    echo "2026-06-11 12:00:00"
}

is_accounts_configured() {
    return 1
}

safe_execute() {
    "$@"
}

validate_numeric_value() {
    local value="$1"
    local default_value="${2:-0}"
    if [[ "$value" =~ ^[0-9]+\.?[0-9]*$ ]] || [[ "$value" =~ ^[0-9]*\.[0-9]+$ ]]; then
        echo "$value"
    else
        echo "$default_value"
    fi
}

format_percentage() {
    local value="$1"
    local decimal_places="${2:-1}"
    value=$(validate_numeric_value "$value" "0")
    printf "%.${decimal_places}f" "$value" 2>/dev/null || echo "$value"
}

export MONITOR_INTERVAL=5
export ERROR_RECOVERY_ENABLED=false
export MONITORING_PROCESS_NAMES_STR="definitely_no_such_monitor_process_for_csv_test"
export BLOCKCHAIN_PROCESS_NAMES_STR="definitely_no_such_blockchain_process_for_csv_test"
export DATA_VOL_MAX_IOPS=30000
export DATA_VOL_MAX_THROUGHPUT=4000
export MONITORING_OVERHEAD_LOG="$TEST_ROOT/monitoring_overhead.csv"
export OVERHEAD_CSV_HEADER="timestamp,monitoring_cpu,monitoring_memory_percent,monitoring_memory_mb,monitoring_process_count,blockchain_cpu,blockchain_memory_percent,blockchain_memory_mb,blockchain_process_count,system_cpu_cores,system_memory_gb,system_disk_gb,system_cpu_usage,system_memory_usage,system_disk_usage,system_cached_gb,system_buffers_gb,system_anon_pages_gb,system_mapped_gb,system_shmem_gb"

# shellcheck source=/dev/null
source monitoring/lib/process_collectors.sh
# shellcheck source=/dev/null
source monitoring/lib/system_collectors.sh
# shellcheck source=/dev/null
source monitoring/lib/monitoring_overhead_csv.sh

field_count() {
    awk -F, '{print NF}' <<<"$1"
}

clean_float="$(clean_and_format_number "abc12.3.4x" "float")"
[[ "$clean_float" == "12.30" ]] || {
    echo "Float cleaner mismatch: $clean_float"
    exit 1
}

clean_int="$(clean_and_format_number "9.9" "int")"
[[ "$clean_int" == "10" ]] || {
    echo "Int cleaner mismatch: $clean_int"
    exit 1
}

valid_line="$(printf 'x,%.0s' {1..19})x"
validate_data_quality "$valid_line"

invalid_line="x,y"
if validate_data_quality "$invalid_line" 2>/dev/null; then
    echo "Invalid data quality line unexpectedly passed"
    exit 1
fi

validate_monitoring_overhead_config

data_line="$(collect_monitoring_overhead_data)"
[[ "$(field_count "$data_line")" -eq 20 ]] || {
    echo "Monitoring overhead data field count mismatch: $data_line"
    exit 1
}

write_monitoring_overhead_log
[[ -s "$MONITORING_OVERHEAD_LOG" ]] || {
    echo "Monitoring overhead log not written"
    exit 1
}

line_count="$(wc -l < "$MONITORING_OVERHEAD_LOG")"
[[ "$line_count" -eq 2 ]] || {
    echo "Monitoring overhead log line count mismatch: $line_count"
    cat "$MONITORING_OVERHEAD_LOG"
    exit 1
}

header_fields="$(head -1 "$MONITORING_OVERHEAD_LOG" | awk -F, '{print NF}')"
data_fields="$(tail -1 "$MONITORING_OVERHEAD_LOG" | awk -F, '{print NF}')"
[[ "$header_fields" -eq 20 && "$data_fields" -eq 20 ]] || {
    echo "Monitoring overhead log field mismatch: header=$header_fields data=$data_fields"
    exit 1
}

echo "✅ monitoring_overhead_csv preserves collection/write contracts"
