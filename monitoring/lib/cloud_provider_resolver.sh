#!/usr/bin/env bash
# =====================================================================
# Cloud Provider Resolver for Unified Monitor
# =====================================================================
# Resolves the cloud_provider CSV column value. Prefer provider abstraction
# when available, then CLOUD_PROVIDER, then unknown.
# =====================================================================

resolve_cloud_provider_value() {
    local provider=""

    if declare -F get_provider_name >/dev/null 2>&1; then
        provider=$(get_provider_name 2>/dev/null || true)
    fi

    if [[ -z "$provider" ]]; then
        provider="${CLOUD_PROVIDER:-unknown}"
    fi

    if [[ -z "$provider" ]]; then
        provider="unknown"
    fi

    echo "$provider"
}
