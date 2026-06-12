#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

# shellcheck source=/dev/null
source monitoring/lib/sample_count_tracker.sh

counter_file="$TEST_ROOT/runtime/sample_count"

first="$(next_sample_count "$counter_file")"
[[ "$first" == "1" ]] || {
    echo "First sample count mismatch: $first"
    exit 1
}

second="$(next_sample_count "$counter_file")"
[[ "$second" == "2" ]] || {
    echo "Second sample count mismatch: $second"
    exit 1
}

echo "not-a-number" > "$counter_file"
recovered="$(next_sample_count "$counter_file")"
[[ "$recovered" == "1" ]] || {
    echo "Corrupt sample count should recover to 1: $recovered"
    exit 1
}

[[ "$(cat "$counter_file")" == "1" ]] || {
    echo "Counter file did not persist recovered value"
    exit 1
}

echo "✅ sample_count_tracker increments and recovers sample count state"
