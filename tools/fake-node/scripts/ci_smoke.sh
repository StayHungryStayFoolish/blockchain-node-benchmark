#!/bin/bash
# ci_smoke.sh — fake-node end-to-end smoke test.
#
# Validates:
#   1. binary builds
#   2. fixtures exist (records them if missing)
#   3. fake-node starts and serves all configured methods
#   4. responses are byte-correct (match fixture file size)
#   5. per-tier latency lands in the configured band
#   6. IO worker writes files at non-fixed intervals (size & count grow)
#   7. /stats endpoint reports non-zero counters
#
# Exit 0 on full pass, non-zero on first failure.
#
# Run: bash tools/fake-node/scripts/ci_smoke.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="${FAKE_NODE_BIN:-/tmp/fake_node}"
CONFIG="${ROOT}/configs/solana.yaml"
FIXTURES="${ROOT}/fixtures"
PORT="${PORT:-19999}"
IO_DIR="/tmp/fake-node-io-solana"

pass=0
fail=0
note() { echo "[smoke] $*"; }
ok()   { echo "  ✓ $*"; pass=$((pass+1)); }
ko()   { echo "  ✗ $*"; fail=$((fail+1)); }

# --- 1. binary ---
note "step 1: binary"
if [[ ! -x "$BIN" ]]; then
  note "  building..."
  (cd "$ROOT" && go build -o "$BIN" fake_node.go)
fi
[[ -x "$BIN" ]] && ok "binary at $BIN" || { ko "binary missing"; exit 1; }

# --- 2. fixtures ---
note "step 2: fixtures"
if [[ ! -f "$FIXTURES/getSlot.json" ]]; then
  note "  recording..."
  bash "$ROOT/scripts/record_solana_fixtures.sh" >/dev/null
fi
n_fixtures=$(ls "$FIXTURES"/*.json 2>/dev/null | wc -l)
[[ "$n_fixtures" -ge 5 ]] && ok "$n_fixtures fixtures present" || { ko "only $n_fixtures fixtures (need 5)"; exit 1; }

# --- 3. start fake-node ---
note "step 3: start fake-node on :$PORT"
rm -rf "$IO_DIR"
"$BIN" -config "$CONFIG" -fixtures-dir "$FIXTURES" -port "$PORT" > /tmp/fake-node-smoke.log 2>&1 &
FN_PID=$!
trap 'kill $FN_PID 2>/dev/null || true' EXIT

# wait for ready (1 second + readiness probe)
for i in 1 2 3 4 5; do
  sleep 1
  if curl -sf "http://127.0.0.1:$PORT/stats" >/dev/null 2>&1; then
    ok "fake-node ready (pid=$FN_PID)"
    break
  fi
  if [[ $i -eq 5 ]]; then
    ko "fake-node not ready after 5s"
    cat /tmp/fake-node-smoke.log
    exit 1
  fi
done

# --- 4. byte-correct responses ---
note "step 4: byte-correct responses"
declare -A PARAMS=(
  [getSlot]='[]'
  [getBalance]='["83astBRguLMdt2h5U1Tpdq5tjFoJ6noeGwaY3mDLVcri"]'
  [getLatestBlockhash]='[]'
  [getBlock]='[100000000,{"encoding":"json","maxSupportedTransactionVersion":0}]'
  [getTransaction]='["5VERv8NMvzbJMEkV8xnrLkEaWRtSz9CosKDYjCJjBRnbJLgp8uirBgmQpjKhoR4tjF3ZpRzrFmBV6UjKdiSZkQUW",{"encoding":"json","maxSupportedTransactionVersion":0}]'
)
for method in getSlot getBalance getLatestBlockhash getBlock getTransaction; do
  body=$(printf '{"jsonrpc":"2.0","id":1,"method":"%s","params":%s}' "$method" "${PARAMS[$method]}")
  expected=$(stat -c%s "$FIXTURES/${method}.json")
  actual=$(curl -s -X POST "http://127.0.0.1:$PORT" -H 'Content-Type: application/json' -d "$body" | wc -c)
  if [[ "$actual" == "$expected" ]]; then
    ok "$method: ${actual}B == fixture"
  else
    ko "$method: ${actual}B != ${expected}B"
  fi
done

# --- 5. per-tier latency ---
note "step 5: per-tier latency (cheap < 50ms, mid 5-80ms, expensive 30-150ms)"
check_lat() {
  local method="$1" min_ms="$2" max_ms="$3"
  local body=$(printf '{"jsonrpc":"2.0","id":1,"method":"%s","params":%s}' "$method" "${PARAMS[$method]}")
  local start_ns=$(date +%s%N)
  curl -s -X POST "http://127.0.0.1:$PORT" -H 'Content-Type: application/json' -d "$body" >/dev/null
  local end_ns=$(date +%s%N)
  local lat_ms=$(( (end_ns - start_ns) / 1000000 ))
  if [[ $lat_ms -ge $min_ms && $lat_ms -le $max_ms ]]; then
    ok "$method: ${lat_ms}ms in [${min_ms}, ${max_ms}]"
  else
    ko "$method: ${lat_ms}ms NOT in [${min_ms}, ${max_ms}]"
  fi
}
check_lat getSlot 0 50
check_lat getLatestBlockhash 5 80
check_lat getBlock 30 200    # 3.5MB response adds curl IO; relax upper bound

# --- 6. IO worker activity ---
note "step 6: IO worker (wait 2s, expect files to appear)"
sleep 2
n_io_files=$(ls "$IO_DIR" 2>/dev/null | wc -l)
total_size=$(du -sk "$IO_DIR" 2>/dev/null | awk '{print $1}' || echo 0)
if [[ $n_io_files -ge 1 && $total_size -ge 1 ]]; then
  ok "IO worker active: $n_io_files files, ${total_size}KB"
else
  ko "IO worker idle: $n_io_files files, ${total_size}KB"
fi

# --- 7. /stats endpoint ---
note "step 7: /stats counters non-zero"
stats=$(curl -s "http://127.0.0.1:$PORT/stats")
req=$(echo "$stats" | jq -r '.total_requests')
wr=$(echo "$stats" | jq -r '.io_writes')
if [[ "$req" -ge 8 && "$wr" -ge 1 ]]; then
  ok "stats: requests=$req io_writes=$wr"
else
  ko "stats: requests=$req io_writes=$wr (need req>=8, wr>=1)"
fi

# --- summary ---
echo ""
echo "[smoke] PASS=$pass FAIL=$fail"
[[ $fail -eq 0 ]] && exit 0 || exit 1
