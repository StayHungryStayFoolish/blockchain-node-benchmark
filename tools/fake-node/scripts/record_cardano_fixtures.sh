#!/bin/bash
# record_cardano_fixtures.sh — record Cardano mainnet (Koios REST) fixtures for fake-node.
#
# ADR-0005 (2026-05-28): cardano was corrected from ogmios → rest family.
# Records 7 method fixtures (1 GET no-param + 1 GET no-param + 3 POST array-body + 1 GET + 1 POST).
# All endpoints are Koios REST (no key required).

set -euo pipefail

OUT_DIR="${1:-$(dirname "$0")/../fixtures/cardano}"
ENDPOINT="${CARDANO_KOIOS:-https://api.koios.rest/api/v1}"
TARGET_ADDR="${TARGET_ADDR:-addr1q9hqwyelcx6l4kulh8lz3ztle90md90m96yjnu8ac8hvm8w7m3cdnhmznqdtwxs3pl7runf7g9yu86s900kh3ddpd8fquhawve}"
TARGET_TX="${TARGET_TX:-41b4bb03eaa713c0d0eda3a3ad8ec51c87f4729b91488ea1bda0c97cdef4abc7}"
TARGET_BLOCK="${TARGET_BLOCK:-cae6ca91e02ab1fbdf9d5e2b2c70b1c7d3eb0c1ea4b8df01d39b88e9bd6dc6b9}"

mkdir -p "$OUT_DIR"
echo "Recording cardano fixtures to: $OUT_DIR"
echo "Endpoint: $ENDPOINT"

FAILED=0
total=0

record_get() {
  local fixture="$1" path="$2"
  total=$((total+1))
  local out="$OUT_DIR/$fixture"
  status=$(curl -sS -m 15 -o "$out" -w "%{http_code}" "$ENDPOINT$path" || echo ERR)
  if [[ "$status" == "200" ]]; then
    echo "  OK GET $path → $fixture ($(stat -c%s "$out" 2>/dev/null || stat -f%z "$out")B)"
  else
    echo "  !! GET $path → status=$status"
    FAILED=$((FAILED+1))
  fi
  sleep 1
}

record_post() {
  local fixture="$1" path="$2" body="$3"
  total=$((total+1))
  local out="$OUT_DIR/$fixture"
  status=$(curl -sS -m 15 -o "$out" -w "%{http_code}" -X POST -H "Content-Type: application/json" -d "$body" "$ENDPOINT$path" || echo ERR)
  if [[ "$status" == "200" ]]; then
    echo "  OK POST $path → $fixture ($(stat -c%s "$out" 2>/dev/null || stat -f%z "$out")B)"
  else
    echo "  !! POST $path → status=$status"
    FAILED=$((FAILED+1))
  fi
  sleep 1
}

record_get   "tip.json"            "/tip"
record_get   "blocks.json"         "/blocks?limit=1"
record_get   "epoch_info.json"     "/epoch_info"
record_post  "address_info.json"   "/address_info"  "{\"_addresses\":[\"$TARGET_ADDR\"]}"
record_post  "tx_info.json"        "/tx_info"       "{\"_tx_hashes\":[\"$TARGET_TX\"]}"
record_post  "block_txs.json"      "/block_txs"     "{\"_block_hashes\":[\"$TARGET_BLOCK\"]}"
record_post  "asset_info.json"     "/asset_info"    '{"_asset_list":[["279c909f348e533da5808898f87f9a14bb2c3dfbbacccd631d927a3f","534e454b"]]}'

echo ""
echo "Done. Failed: $FAILED / $total"
ls -la "$OUT_DIR"
exit $FAILED
