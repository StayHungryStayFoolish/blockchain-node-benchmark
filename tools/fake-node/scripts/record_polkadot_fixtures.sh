#!/bin/bash
# record_polkadot_fixtures.sh — record Polkadot mainnet JSON-RPC fixtures for fake-node.
# ADR-0005 (2026-05-28): substrate family handler introduced.

set -euo pipefail
OUT_DIR="${1:-$(dirname "$0")/../fixtures/polkadot}"
ENDPOINT="${POLKADOT_RPC:-https://rpc.polkadot.io}"
mkdir -p "$OUT_DIR"
echo "Recording polkadot fixtures to: $OUT_DIR (endpoint=$ENDPOINT)"

FAILED=0
record() {
  local fixture="$1" method="$2" params="$3"
  local body=$(printf '{"jsonrpc":"2.0","id":1,"method":"%s","params":%s}' "$method" "$params")
  local out="$OUT_DIR/$fixture"
  status=$(curl -sS -m 15 -o "$out" -w "%{http_code}" -X POST -H "Content-Type: application/json" -d "$body" "$ENDPOINT" || echo ERR)
  if [[ "$status" == "200" ]] && jq -e 'has("result")' "$out" >/dev/null 2>&1; then
    echo "  OK $method → $fixture ($(stat -c%s "$out" 2>/dev/null || stat -f%z "$out")B)"
  else
    echo "  !! $method status=$status"; FAILED=$((FAILED+1))
  fi
  sleep 1
}

record  "system_chain.json"            "system_chain"            "[]"
record  "system_health.json"           "system_health"           "[]"
record  "chain_getFinalizedHead.json"  "chain_getFinalizedHead"  "[]"
record  "chain_getBlockHash.json"      "chain_getBlockHash"      "[]"
record  "state_getRuntimeVersion.json" "state_getRuntimeVersion" "[]"

echo "Done. Failed: $FAILED"
exit $FAILED
