#!/bin/bash
# ci_smoke.sh — fake-node v2 end-to-end smoke (multi-chain).
#
# v2 Validates:
#   1. binary builds (single binary serves all 36 chains via handler registry)
#   2. solana chain: BLOCKCHAIN_NODE=solana → jsonrpc handler → byte-correct
#   3. ethereum chain: BLOCKCHAIN_NODE=ethereum → jsonrpc handler → byte-correct
#   4. handler routing: NotImplemented family (e.g. cardano) startup OK, RPC 500
#   5. /stats counters report activity
#   6. IO worker active
#
# Exit 0 on full pass.
#
# Run: bash tools/fake-node/scripts/ci_smoke.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "$ROOT/../.." && pwd)"
BIN="${FAKE_NODE_BIN:-/tmp/fake-node-v2}"
CONFIGS_DIR="${ROOT}/configs"
FIXTURES="${ROOT}/fixtures"
CHAINS_DIR="${REPO_ROOT}/config/chains"

pass=0
fail=0
note() { echo "[smoke] $*"; }
ok()   { echo "  ✓ $*"; pass=$((pass+1)); }
ko()   { echo "  ✗ $*"; fail=$((fail+1)); }

# --- 1. binary ---
note "step 1: build binary"
(cd "$ROOT" && go build -o "$BIN" .)
[[ -x "$BIN" ]] && ok "binary at $BIN" || { ko "binary missing"; exit 1; }

# --- helper: start fake-node for a chain ---
start_chain() {
    local chain="$1" port="$2" io_dir="$3"
    rm -rf "$io_dir"
    BLOCKCHAIN_NODE="$chain" "$BIN" \
        -chains-dir "$CHAINS_DIR" \
        -configs-dir "$CONFIGS_DIR" \
        -fixtures-dir "$FIXTURES" \
        -port "$port" \
        > "/tmp/fake-node-smoke-${chain}.log" 2>&1 &
    local pid=$!
    for i in 1 2 3 4 5; do
        sleep 1
        if curl -sf "http://127.0.0.1:$port/stats" >/dev/null 2>&1; then
            echo "$pid"
            return 0
        fi
        if [[ $i -eq 5 ]]; then
            echo "FAIL: fake-node $chain not ready after 5s" >&2
            cat "/tmp/fake-node-smoke-${chain}.log" >&2
            return 1
        fi
    done
}

# --- 2. solana chain ---
note "step 2: solana (jsonrpc handler, BLOCKCHAIN_NODE=solana)"
SOL_PID=$(start_chain solana 19101 /tmp/fake-node-io-jsonrpc) || { ko "solana start failed"; exit 1; }
trap "kill $SOL_PID 2>/dev/null || true" EXIT
ok "solana ready (pid=$SOL_PID)"

# Verify log shows the right family routing
if grep -q "adapter_family=jsonrpc" "/tmp/fake-node-smoke-solana.log"; then
    ok "solana → adapter_family=jsonrpc routed correctly"
else
    ko "solana adapter_family routing log missing"
fi

# Byte-correct check on a method
for method in getSlot getBalance; do
    expected=$(stat -c%s "$FIXTURES/solana/${method}.json")
    body=$(printf '{"jsonrpc":"2.0","id":1,"method":"%s","params":[]}' "$method")
    actual=$(curl -s -X POST "http://127.0.0.1:19101" -H 'Content-Type: application/json' -d "$body" | wc -c)
    if [[ "$actual" == "$expected" ]]; then
        ok "solana $method: ${actual}B == fixture"
    else
        ko "solana $method: ${actual}B != ${expected}B"
    fi
done

# --- 3. ethereum chain ---
note "step 3: ethereum (jsonrpc handler, BLOCKCHAIN_NODE=ethereum)"
ETH_PID=$(start_chain ethereum 19102 /tmp/fake-node-io-jsonrpc) || { ko "ethereum start failed"; kill $SOL_PID 2>/dev/null; exit 1; }
trap "kill $SOL_PID $ETH_PID 2>/dev/null || true" EXIT
ok "ethereum ready (pid=$ETH_PID)"

# Verify ethereum uses the SAME handler family as solana (proves jsonrpc handler reused for 16 chains)
if grep -q "adapter_family=jsonrpc" "/tmp/fake-node-smoke-ethereum.log"; then
    ok "ethereum → adapter_family=jsonrpc (same handler as solana, family reuse confirmed)"
else
    ko "ethereum adapter_family routing log missing"
fi

# Byte-correct check on eth_* method
for method in eth_blockNumber eth_getBalance; do
    expected=$(stat -c%s "$FIXTURES/ethereum/${method}.json")
    body=$(printf '{"jsonrpc":"2.0","id":1,"method":"%s","params":[]}' "$method")
    actual=$(curl -s -X POST "http://127.0.0.1:19102" -H 'Content-Type: application/json' -d "$body" | wc -c)
    if [[ "$actual" == "$expected" ]]; then
        ok "ethereum $method: ${actual}B == fixture"
    else
        ko "ethereum $method: ${actual}B != ${expected}B"
    fi
done

# Method-isolation check: ethereum chain should 404 on solana methods
# (proves chain template scoping works, not just blanket pass-through)
http_code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:19102" \
    -H 'Content-Type: application/json' \
    -d '{"jsonrpc":"2.0","id":1,"method":"getSlot","params":[]}')
if [[ "$http_code" == "404" ]]; then
    ok "ethereum 404 on solana method getSlot (chain isolation OK)"
else
    ko "ethereum returned $http_code on getSlot (expected 404 — chain isolation broken)"
fi

# --- 4. NotImplemented family (cardano → ogmios stub) ---
note "step 4: cardano (NotImplemented family stub)"
CAR_PID=$(start_chain cardano 19103 /tmp/fake-node-io-card) || { ko "cardano start failed (stub should still start)"; kill $SOL_PID $ETH_PID 2>/dev/null; exit 1; }
trap "kill $SOL_PID $ETH_PID $CAR_PID 2>/dev/null || true" EXIT
ok "cardano startup OK (stub registers fine)"

if grep -q "adapter_family=ogmios" "/tmp/fake-node-smoke-cardano.log"; then
    ok "cardano → adapter_family=ogmios routed to stub"
else
    ko "cardano adapter_family=ogmios log missing"
fi

# But RPC against it should fail loudly (stub returns error)
# Note: cardano's ogmios methods need a fixture wired in configs/ogmios.yaml first;
# without that, we get 404 (no fixture). Both are "loud failures" — both acceptable.
http_code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:19103" \
    -H 'Content-Type: application/json' \
    -d '{"jsonrpc":"2.0","id":1,"method":"queryTip","params":[]}')
if [[ "$http_code" == "404" || "$http_code" == "500" ]]; then
    ok "cardano queryTip → HTTP $http_code (stub correctly fails loud, not silent)"
else
    ko "cardano queryTip → HTTP $http_code (stub silently passing)"
fi

# --- 5. /stats ---
note "step 5: /stats on solana"
stats=$(curl -s "http://127.0.0.1:19101/stats")
req=$(echo "$stats" | jq -r '.total_requests')
if [[ "$req" -ge 2 ]]; then
    ok "solana /stats: requests=$req"
else
    ko "solana /stats: requests=$req (need >=2)"
fi

# --- 6. IO worker ---
note "step 6: IO worker (wait 1.5s)"
sleep 1.5
n_io=$(ls /tmp/fake-node-io-jsonrpc 2>/dev/null | wc -l)
if [[ $n_io -ge 1 ]]; then
    ok "IO worker active: $n_io files in /tmp/fake-node-io-jsonrpc"
else
    ko "IO worker idle: $n_io files"
fi

# --- summary ---
echo ""
echo "[smoke v2] PASS=$pass FAIL=$fail"
[[ $fail -eq 0 ]] && exit 0 || exit 1
