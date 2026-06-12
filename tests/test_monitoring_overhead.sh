#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

log_debug() { :; }
log_warn() { :; }
log_info() { :; }

declare -A COMMAND_CACHE
is_command_available() {
    command -v "$1" >/dev/null 2>&1
}

monitor_performance_impact() {
    :
}

export MONITOR_INTERVAL=5

# shellcheck source=/dev/null
source monitoring/lib/process_collectors.sh
# shellcheck source=/dev/null
source monitoring/lib/monitoring_overhead.sh

field_count() {
    awk -F, '{print NF}' <<<"$1"
}

export MONITORING_SELF=true
recursive_guard="$(get_monitoring_overhead)"
unset MONITORING_SELF
[[ "$recursive_guard" == "0,0" ]] || {
    echo "Recursive monitoring overhead guard mismatch: $recursive_guard"
    exit 1
}

export MONITORING_PROCESS_NAMES_STR="definitely_no_such_monitor_process_for_overhead_test"
empty_overhead="$(get_monitoring_overhead)"
[[ "$empty_overhead" == "0,0" ]] || {
    echo "Empty monitoring overhead mismatch: $empty_overhead"
    exit 1
}

export MONITORING_PROCESS_NAMES_STR="bash"
real_overhead="$(get_monitoring_overhead)"
[[ "$(field_count "$real_overhead")" -eq 2 ]] || {
    echo "Monitoring overhead field count mismatch: $real_overhead"
    exit 1
}
[[ "$real_overhead" =~ ^[0-9]+([.][0-9]+)?,[0-9]+([.][0-9]+)?$ ]] || {
    echo "Monitoring overhead numeric format mismatch: $real_overhead"
    exit 1
}

LAST_IO_STATS["999999_read_bytes"]=1
cleanup_dead_process_io_stats
[[ -z "${LAST_IO_STATS["999999_read_bytes"]:-}" ]] || {
    echo "Dead process I/O state was not cleaned"
    exit 1
}

echo "✅ monitoring_overhead preserves overhead field and cleanup contracts"
