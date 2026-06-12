#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

# shellcheck source=/dev/null
source config/csv_schema_registry.sh
# shellcheck source=/dev/null
source monitoring/lib/block_height_csv_reader.sh

expected_default="0,0,0,1,1,0,absolute_gap,healthy,0,block,0,null"

missing_out="$(get_block_height_csv_fields "$TEST_ROOT/missing.csv")"
[[ "$missing_out" == "$expected_default" ]] || {
    echo "Missing CSV did not return default fields: $missing_out"
    exit 1
}

header_only="$TEST_ROOT/header_only.csv"
csv_registry_block_csv_header > "$header_only"
header_out="$(get_block_height_csv_fields "$header_only")"
[[ "$header_out" == "$expected_default" ]] || {
    echo "Header-only CSV did not return default fields: $header_out"
    exit 1
}

data_csv="$TEST_ROOT/block_height.csv"
{
    csv_registry_block_csv_header
    echo "2026-06-11 12:00:00,100,111,11,1,1,0,absolute_gap,behind,11,block,0,null"
} > "$data_csv"

data_out="$(get_block_height_csv_fields "$data_csv")"
expected_data="100,111,11,1,1,0,absolute_gap,behind,11,block,0,null"
[[ "$data_out" == "$expected_data" ]] || {
    echo "Data CSV fields mismatch"
    echo "expected: $expected_data"
    echo "actual:   $data_out"
    exit 1
}

echo "✅ block_height_csv_reader returns expected sync-health fields"
