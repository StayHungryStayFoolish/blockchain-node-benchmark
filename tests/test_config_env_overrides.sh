#!/usr/bin/env bash
set -euo pipefail

# Guard that user_config defaults do not override explicit smoke/E2E settings.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

export BLOCKCHAIN_NODE=solana
export RPC_MODE=mixed
export QUICK_INITIAL_QPS=1
export QUICK_MAX_QPS=2
export QUICK_QPS_STEP=1
export QUICK_DURATION=3
export QPS_WARMUP_DURATION=0
export QPS_COOLDOWN=0
export BLOCKCHAIN_BENCHMARK_DATA_DIR
BLOCKCHAIN_BENCHMARK_DATA_DIR="$(mktemp -d /tmp/bnb-config-data.XXXXXX)"
export MEMORY_SHARE_DIR
MEMORY_SHARE_DIR="$(mktemp -d /tmp/bnb-config-shm.XXXXXX)"

cleanup() {
    rm -rf "$BLOCKCHAIN_BENCHMARK_DATA_DIR" "$MEMORY_SHARE_DIR"
}
trap cleanup EXIT

# config_loader.sh is not authored for nounset mode; keep the test focused on
# environment override semantics instead of changing framework shell options.
set +u
# shellcheck source=/dev/null
source config/config_loader.sh >/tmp/test_config_env_overrides.log 2>&1
set -u

[[ "$QUICK_INITIAL_QPS" == "1" ]] || { echo "QUICK_INITIAL_QPS override lost"; exit 1; }
[[ "$QUICK_MAX_QPS" == "2" ]] || { echo "QUICK_MAX_QPS override lost"; exit 1; }
[[ "$QUICK_QPS_STEP" == "1" ]] || { echo "QUICK_QPS_STEP override lost"; exit 1; }
[[ "$QUICK_DURATION" == "3" ]] || { echo "QUICK_DURATION override lost"; exit 1; }
[[ "$QPS_WARMUP_DURATION" == "0" ]] || { echo "QPS_WARMUP_DURATION override lost"; exit 1; }
[[ "$QPS_COOLDOWN" == "0" ]] || { echo "QPS_COOLDOWN override lost"; exit 1; }

echo "✅ Config environment overrides are preserved"
