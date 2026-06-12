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

# shellcheck source=/dev/null
source monitoring/lib/process_collectors.sh

field_count() {
    awk -F, '{print NF}' <<<"$1"
}

empty_resources="$(calculate_process_resources "" "empty")"
[[ "$empty_resources" == "0,0,0,0" ]] || {
    echo "Empty process resources mismatch: $empty_resources"
    exit 1
}

current_resources="$(get_current_process_resources "$$")"
[[ "$(field_count "$current_resources")" -eq 2 ]] || {
    echo "Current process resource field count mismatch: $current_resources"
    exit 1
}

self_resources="$(calculate_process_resources "$$" "self")"
[[ "$(field_count "$self_resources")" -eq 4 ]] || {
    echo "Process resource field count mismatch: $self_resources"
    exit 1
}

export MONITORING_PROCESS_NAMES_STR="definitely_no_such_process_for_benchmark_test"
monitoring_pids="$(discover_monitoring_processes)"
[[ -z "$monitoring_pids" ]] || {
    echo "Unexpected monitoring process discovery result: $monitoring_pids"
    exit 1
}

export BLOCKCHAIN_PROCESS_NAMES_STR="definitely_no_such_blockchain_process_for_benchmark_test"
blockchain_pids="$(discover_blockchain_processes)"
[[ -z "$blockchain_pids" ]] || {
    echo "Unexpected blockchain process discovery result: $blockchain_pids"
    exit 1
}

blockchain_resources="$(get_blockchain_node_resources)"
[[ "$blockchain_resources" == "0,0,0,0" ]] || {
    echo "Empty blockchain resource result mismatch: $blockchain_resources"
    exit 1
}

echo "✅ process_collectors preserves process discovery/resource contracts"
