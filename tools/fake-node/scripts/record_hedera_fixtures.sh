#!/bin/bash
# record_hedera_fixtures.sh — record hedera mainnet dual-protocol fixtures for fake-node.
# ADR-0005 (2026-05-28): hedera_dual family handler introduced.

set -euo pipefail
OUT_DIR="${1:-$(dirname "$0")/../fixtures/hedera}"
JSON_RPC="${HEDERA_JSON_RPC:-https://mainnet.hashio.io/api}"
MIRROR="${HEDERA_MIRROR:-https://mainnet-public.mirrornode.hedera.com}"
mkdir -p "$OUT_DIR/jsonrpc" "$OUT_DIR/mirror"

FAILED=0
record_jsonrpc() {
  local fixture="$1" method="$2" params="$3"
  local body=$(printf '{"jsonrpc":"2.0","id":1,"method":"%s","params":%s}' "$method" "$params")
  local out="$OUT_DIR/jsonrpc/$fixture"
  status=$(curl -sS -m 15 -o "$out" -w "%{http_code}" -X POST -H "Content-Type: application/json" -d "$body" "$JSON_RPC" || echo ERR)
  if [[ "$status" == "200" ]] && jq -e 'has("result")' "$out" >/dev/null 2>&1; then
    echo "  OK eth $method → jsonrpc/$fixture"
  else
    echo "  !! $method status=$status"; FAILED=$((FAILED+1))
  fi
  sleep 1
}

record_mirror() {
  local fixture="$1" path="$2"
  local out="$OUT_DIR/mirror/$fixture"
  status=$(curl -sS -m 15 -o "$out" -w "%{http_code}" "$MIRROR$path" || echo ERR)
  if [[ "$status" == "200" ]]; then
    echo "  OK GET $path → mirror/$fixture"
  else
    echo "  !! GET $path status=$status"; FAILED=$((FAILED+1))
  fi
  sleep 1
}

record_jsonrpc "eth_blockNumber.json" "eth_blockNumber" "[]"
record_jsonrpc "eth_chainId.json"     "eth_chainId"     "[]"
record_mirror  "network_nodes.json"   "/api/v1/network/nodes?limit=3"

echo "Done. Failed: $FAILED"
exit $FAILED
