#!/usr/bin/env bash
# =====================================================================
# Block Height CSV Reader for Unified Monitor
# =====================================================================
# Converts the latest block_height_monitor CSV row into the sync-health field
# segment embedded in performance_latest.csv.
# =====================================================================

DEFAULT_BLOCK_HEIGHT_CSV_FIELDS="0,0,0,1,1,0,absolute_gap,healthy,0,block,0,null"

get_block_height_csv_fields() {
    local block_height_file="${1:-${BLOCK_HEIGHT_DATA_FILE:-}}"

    if [[ -z "$block_height_file" || ! -f "$block_height_file" ]]; then
        echo "$DEFAULT_BLOCK_HEIGHT_CSV_FIELDS"
        return 0
    fi

    local latest_block_data
    latest_block_data=$(tail -1 "$block_height_file" 2>/dev/null || true)

    if [[ -z "$latest_block_data" || "$latest_block_data" == *"timestamp"* ]]; then
        echo "$DEFAULT_BLOCK_HEIGHT_CSV_FIELDS"
        return 0
    fi

    local block_field_range="2-13"
    if declare -F csv_registry_block_data_field_range >/dev/null 2>&1; then
        block_field_range="$(csv_registry_block_data_field_range)"
    fi

    local fields
    fields=$(echo "$latest_block_data" | cut -d',' -f"$block_field_range")
    if [[ -z "$fields" ]]; then
        echo "$DEFAULT_BLOCK_HEIGHT_CSV_FIELDS"
        return 0
    fi

    echo "$fields"
}
