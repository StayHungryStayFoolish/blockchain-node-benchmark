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

# shellcheck source=/dev/null
source monitoring/lib/ena_data_normalizer.sh
# shellcheck source=/dev/null
source monitoring/lib/system_collectors.sh

field_count() {
    awk -F, '{print NF}' <<<"$1"
}

export NETWORK_INTERFACE=""
network_data="$(get_network_data)"
[[ "$network_data" == "unknown,0,0,0,0,0,0,0,0,0" ]] || {
    echo "Unexpected empty-interface network data: $network_data"
    exit 1
}
[[ "$(field_count "$network_data")" -eq 10 ]] || {
    echo "Network field count mismatch: $network_data"
    exit 1
}

export ENA_MONITOR_ENABLED=false
export ENA_ALLOWANCE_FIELDS_STR="bw_in_allowance_exceeded bw_out_allowance_exceeded pps_allowance_exceeded"
ena_data="$(get_ena_allowance_data)"
[[ "$ena_data" == "0,0,0" ]] || {
    echo "ENA fallback mismatch: $ena_data"
    exit 1
}

static_data="$(get_system_static_resources)"
[[ "$(field_count "$static_data")" -eq 3 ]] || {
    echo "Static resource field count mismatch: $static_data"
    exit 1
}

dynamic_data="$(get_system_dynamic_resources)"
[[ "$(field_count "$dynamic_data")" -eq 8 ]] || {
    echo "Dynamic resource field count mismatch: $dynamic_data"
    exit 1
}

cpu_data="$(get_cpu_data)"
[[ "$(field_count "$cpu_data")" -eq 6 ]] || {
    echo "CPU field count mismatch: $cpu_data"
    exit 1
}

memory_data="$(get_memory_data)"
[[ "$(field_count "$memory_data")" -eq 3 ]] || {
    echo "Memory field count mismatch: $memory_data"
    exit 1
}

echo "✅ system_collectors preserves system metric field contracts"
