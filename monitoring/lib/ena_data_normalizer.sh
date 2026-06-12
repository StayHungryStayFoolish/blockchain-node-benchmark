#!/usr/bin/env bash
# =====================================================================
# ENA Data Normalizer for Unified Monitor
# =====================================================================
# Validates ENA allowance CSV data and returns a zero-filled fallback with the
# configured field count when the data is malformed.
# =====================================================================

build_zero_csv_fields() {
    local field_count="${1:-0}"

    if [[ ! "$field_count" =~ ^[0-9]+$ || "$field_count" -le 0 ]]; then
        echo ""
        return 0
    fi

    printf "0,%.0s" $(seq 1 "$field_count") | sed 's/,$//'
}

build_ena_header() {
    local ena_fields_str="${1:-${ENA_ALLOWANCE_FIELDS_STR:-}}"
    local header=""
    local ena_fields

    # shellcheck disable=SC2206
    ena_fields=($ena_fields_str)
    for field in "${ena_fields[@]}"; do
        if [[ -n "$header" ]]; then
            header="$header,$field"
        else
            header="$field"
        fi
    done

    echo "$header"
}

normalize_ena_data() {
    local raw_ena_data="$1"
    local ena_fields_str="${2:-${ENA_ALLOWANCE_FIELDS_STR:-}}"

    if [[ "$raw_ena_data" =~ ^[0-9,]+$ ]]; then
        echo "$raw_ena_data"
        return 0
    fi

    local field_count
    field_count=$(echo "$ena_fields_str" | wc -w | tr -d ' ')
    build_zero_csv_fields "$field_count"
}
