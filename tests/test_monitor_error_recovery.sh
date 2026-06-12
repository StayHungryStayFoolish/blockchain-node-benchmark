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

is_command_available() {
    command -v "$1" >/dev/null 2>&1
}

safe_write_csv() {
    local csv_file="$1"
    local csv_data="$2"
    echo "$csv_data" >> "$csv_file"
}

ok_function() {
    echo "ok-value"
}

failing_function() {
    echo "bad-value"
    return 7
}

export TMP_DIR="$TEST_ROOT/tmp"
export LOGS_DIR="$TEST_ROOT/logs"
export ERROR_LOG="$TEST_ROOT/logs/errors.csv"
export SESSION_TIMESTAMP="20260611_120000"
export MAX_CONSECUTIVE_ERRORS=99
export ERROR_RECOVERY_DELAY=0
export ERROR_RECOVERY_ENABLED=true
export PERFORMANCE_MONITORING_ENABLED=true
export MONITORING_PROCESS_NAMES_STR="x"
export MONITORING_OVERHEAD_LOG="$TEST_ROOT/logs/overhead.csv"

mkdir -p "$TMP_DIR" "$LOGS_DIR"

# shellcheck source=/dev/null
source monitoring/lib/monitor_error_recovery.sh

result="$(safe_execute ok_function)"
[[ "$result" == "ok-value" ]] || {
    echo "safe_execute success result mismatch: $result"
    exit 1
}

if safe_execute no_such_function >/dev/null 2>&1; then
    echo "safe_execute missing function unexpectedly passed"
    exit 1
fi

[[ "${ERROR_COUNTERS["no_such_function"]:-0}" -eq 1 ]] || {
    echo "Missing function error counter mismatch: ${ERROR_COUNTERS["no_such_function"]:-unset}"
    exit 1
}

if safe_execute failing_function >/dev/null 2>&1; then
    echo "safe_execute failing function unexpectedly passed"
    exit 1
fi

[[ "${ERROR_COUNTERS["failing_function"]:-0}" -eq 1 ]] || {
    echo "Failing function error counter mismatch: ${ERROR_COUNTERS["failing_function"]:-unset}"
    exit 1
}

[[ -s "$ERROR_LOG" ]] || {
    echo "Error log was not written"
    exit 1
}

generate_error_recovery_suggestions "failing_function"
generate_error_recovery_report

report="$LOGS_DIR/error_recovery_report_${SESSION_TIMESTAMP}.txt"
[[ -s "$report" ]] || {
    echo "Error recovery report was not written"
    exit 1
}

grep -q "failing_function" "$report" || {
    echo "Error recovery report missing failing function"
    exit 1
}

echo "✅ monitor_error_recovery preserves safe execution and report contracts"
