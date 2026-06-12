#!/bin/bash
# =====================================================================
# Blockchain Node Benchmark Framework - Provider Disk Post-Processing
# =====================================================================
# Target users: Framework maintainers
# Purpose: Normalize provider-specific disk baselines after user_config.sh is loaded.
# =====================================================================

configure_provider_disk_volumes() {
    echo "Checking provider disk type configuration..." >&2

    local provider
    provider=$(printf '%s' "${CLOUD_PROVIDER:-gcp}" | tr '[:upper:]' '[:lower:]')

    # AWS io2 throughput can be derived from provisioned IOPS. GCP Hyperdisk/PD
    # and generic disks use the explicit user-provided throughput baseline.
    if [[ "$provider" != "aws" ]]; then
        return 0
    fi

    if [[ "$DATA_VOL_TYPE" == "io2" || "$ACCOUNTS_VOL_TYPE" == "io2" ]]; then
        if [[ -f "${CONFIG_DIR}/../utils/disk_converter.sh" ]]; then
            # shellcheck source=/dev/null
            source "${CONFIG_DIR}/../utils/disk_converter.sh"
            echo "Disk converter loaded successfully" >&2
        else
            echo "Error: disk_converter.sh does not exist, cannot process AWS io2 type" >&2
            echo "   Path: ${CONFIG_DIR}/../utils/disk_converter.sh" >&2
            exit 1
        fi
    fi

    if [[ "$DATA_VOL_TYPE" == "io2" && -n "$DATA_VOL_MAX_IOPS" ]]; then
        local original_throughput="$DATA_VOL_MAX_THROUGHPUT"
        local auto_throughput

        if auto_throughput=$(calculate_io2_throughput "$DATA_VOL_MAX_IOPS" 2>/dev/null); then
            DATA_VOL_MAX_THROUGHPUT="$auto_throughput"
            echo "DATA volume AWS io2 auto-calculated: $original_throughput -> $auto_throughput MiB/s (based on $DATA_VOL_MAX_IOPS IOPS)" >&2
        else
            echo "Error: DATA volume AWS io2 throughput calculation failed" >&2
            exit 1
        fi
    fi

    if [[ "$ACCOUNTS_VOL_TYPE" == "io2" && -n "$ACCOUNTS_VOL_MAX_IOPS" && -n "$ACCOUNTS_DEVICE" ]]; then
        local original_throughput="$ACCOUNTS_VOL_MAX_THROUGHPUT"
        local auto_throughput

        if auto_throughput=$(calculate_io2_throughput "$ACCOUNTS_VOL_MAX_IOPS" 2>/dev/null); then
            ACCOUNTS_VOL_MAX_THROUGHPUT="$auto_throughput"
            echo "ACCOUNTS volume AWS io2 auto-calculated: $original_throughput -> $auto_throughput MiB/s (based on $ACCOUNTS_VOL_MAX_IOPS IOPS)" >&2
        else
            echo "Error: ACCOUNTS volume AWS io2 throughput calculation failed" >&2
            exit 1
        fi
    fi
}

configure_provider_disk_volumes

export DATA_VOL_MAX_THROUGHPUT ACCOUNTS_VOL_MAX_THROUGHPUT
export -f configure_provider_disk_volumes
