#!/bin/bash
# record_cosmos_fixtures.sh — record cosmos-hub Tendermint RPC fixtures for fake-node.
# ADR-0005 (2026-05-28): tendermint family handler introduced.

set -euo pipefail
OUT_DIR="${1:-$(dirname "$0")/../fixtures/cosmos-hub}"
ENDPOINT="${COSMOS_RPC:-https://cosmos-rpc.publicnode.com}"
mkdir -p "$OUT_DIR"
echo "Recording cosmos-hub fixtures to: $OUT_DIR (endpoint=$ENDPOINT)"

FAILED=0
record_get() {
  local fixture="$1" path="$2"
  local out="$OUT_DIR/$fixture"
  status=$(curl -sS -m 30 -o "$out" -w "%{http_code}" "$ENDPOINT$path" || echo ERR)
  if [[ "$status" == "200" ]]; then
    echo "  OK GET $path → $fixture ($(stat -c%s "$out" 2>/dev/null || stat -f%z "$out")B)"
  else
    echo "  !! GET $path status=$status"; FAILED=$((FAILED+1))
  fi
  sleep 1
}

record_get  "status.json"     "/status"
record_get  "abci_info.json"  "/abci_info"
record_get  "block.json"      "/block"

echo "Done. Failed: $FAILED"
exit $FAILED
