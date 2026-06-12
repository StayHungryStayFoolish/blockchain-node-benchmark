#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

export NODE_HEALTH_CACHE_DIR="$TEST_ROOT/node-health"

# common_functions.sh is not authored for nounset mode; keep this test focused
# on node health cache path resolution.
set +u
# shellcheck source=/dev/null
source core/common_functions.sh >/dev/null 2>&1
set -u

cache_file="$(get_node_health_cache_file "http://127.0.0.1:8899")"

case "$cache_file" in
    "$NODE_HEALTH_CACHE_DIR"/node_health_*.cache) ;;
    *)
        echo "Unexpected node health cache path: $cache_file"
        exit 1
        ;;
esac

[[ -d "$NODE_HEALTH_CACHE_DIR" ]] || { echo "NODE_HEALTH_CACHE_DIR was not created"; exit 1; }

echo "✅ node health cache path uses NODE_HEALTH_CACHE_DIR"
