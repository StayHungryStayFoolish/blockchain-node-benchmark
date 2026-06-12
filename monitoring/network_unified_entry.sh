#!/bin/bash
# monitoring/network_unified_entry.sh
# Provider-aware NIC monitoring entrypoint
#
# After sourcing, these provider functions are available from
# ${CLOUD_PROVIDER_VARIANT}.sh:
#   init_network_monitoring
#   generate_network_csv_header
#   collect_network_metrics
#   get_network_field_metadata
#
# Usage:
#   source monitoring/network_unified_entry.sh
#   if init_network_monitoring; then
#       generate_network_csv_header > "$NETWORK_CSV"
#       while running; do collect_network_metrics >> "$NETWORK_CSV"; done
#   fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 1. Detect platform and NIC driver, exporting CLOUD_PROVIDER_VARIANT.
# shellcheck disable=SC1091
source "${PROJECT_ROOT}/config/cloud_provider.sh"

# 2. Source the provider implementation for the detected variant.
PROVIDER_FILE="${SCRIPT_DIR}/network/${CLOUD_PROVIDER_VARIANT}.sh"
if [[ ! -f "$PROVIDER_FILE" ]]; then
    echo "WARN: provider file not found: $PROVIDER_FILE, falling back to other_none" >&2
    PROVIDER_FILE="${SCRIPT_DIR}/network/other_none.sh"
fi

if [[ ! -f "$PROVIDER_FILE" ]]; then
    echo "ERROR: even other_none.sh missing at $PROVIDER_FILE" >&2
    return 1 2>/dev/null || exit 1
fi

# shellcheck disable=SC1090
source "$PROVIDER_FILE"

# 3. Verify the required provider functions are defined.
for fn in init_network_monitoring generate_network_csv_header collect_network_metrics get_network_field_metadata; do
    if ! declare -F "$fn" > /dev/null; then
        echo "ERROR: provider $PROVIDER_FILE missing function: $fn" >&2
        return 1 2>/dev/null || exit 1
    fi
done

# Expose selected provider metadata.
export NETWORK_PROVIDER_FILE="$PROVIDER_FILE"
export NETWORK_PROVIDER_VARIANT="$CLOUD_PROVIDER_VARIANT"
