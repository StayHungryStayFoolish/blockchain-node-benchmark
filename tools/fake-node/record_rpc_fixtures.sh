#!/usr/bin/env bash
# Central fake-node RPC fixture recording entrypoint.
#
# Usage:
#   tools/fake-node/record_rpc_fixtures.sh
#   tools/fake-node/record_rpc_fixtures.sh all
#   tools/fake-node/record_rpc_fixtures.sh solana
#   tools/fake-node/record_rpc_fixtures.sh solana,ethereum,bitcoin
#
# Extra arguments are forwarded to tools/fake-node/record_rpc_fixtures.py, for example:
#   tools/fake-node/record_rpc_fixtures.sh solana --delay 0.5 --timeout 20
#   tools/fake-node/record_rpc_fixtures.sh all --modes single

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

CHAINS="all"
if [[ $# -gt 0 && "${1}" != --* ]]; then
  CHAINS="$1"
  shift
fi

MODES="${RPC_FIXTURE_MODES:-single,mixed}"

exec python3 "${REPO_ROOT}/tools/fake-node/record_rpc_fixtures.py" \
  --chains "${CHAINS}" \
  --modes "${MODES}" \
  --record \
  --write-fake-node-fixtures \
  "$@"
