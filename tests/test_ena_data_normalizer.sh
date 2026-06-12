#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# shellcheck source=/dev/null
source monitoring/lib/ena_data_normalizer.sh

fields="bw_in bw_out pps conntrack"

header="$(build_ena_header "$fields")"
[[ "$header" == "bw_in,bw_out,pps,conntrack" ]] || {
    echo "ENA header mismatch: $header"
    exit 1
}

valid="$(normalize_ena_data "1,2,3,4" "$fields")"
[[ "$valid" == "1,2,3,4" ]] || {
    echo "Valid ENA data changed unexpectedly: $valid"
    exit 1
}

fallback="$(normalize_ena_data "bad,value" "$fields")"
[[ "$fallback" == "0,0,0,0" ]] || {
    echo "Fallback ENA data mismatch: $fallback"
    exit 1
}

empty_fields="$(normalize_ena_data "bad" "")"
[[ -z "$empty_fields" ]] || {
    echo "Empty fields should produce empty fallback: $empty_fields"
    exit 1
}

echo "✅ ena_data_normalizer builds ENA header and fallback data as expected"
