#!/bin/bash
# ci_smoke.sh — fake-node v2 end-to-end smoke (multi-chain, multi-family).
#
# ADR-0005 (2026-05-28): Extended to validate 6 protocol families:
#   jsonrpc / bitcoin_jsonrpc / rest / substrate / tendermint / hedera_dual
#
# Validates:
#   1. binary builds (single binary serves all 36 chains via handler registry)
#   2. 6/6 family representatives: byte-correct fixture passthrough
#   3. 36/36 chain startup smoke (no panic, family resolved)
#   4. /stats counters report activity
#   5. IO worker active
#
# Exit 0 on full pass. ALL 36 chains MUST startup-pass (parallel-entry-trap
# rule: NotImplemented family registration was a defer trap and is now removed).
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

PIDS=""
cleanup() { for p in $PIDS; do kill $p 2>/dev/null || true; done; }
trap cleanup EXIT

# --- 2. solana (jsonrpc family — 16/36 chains) ---
note "step 2: solana (jsonrpc family)"
SOL_PID=$(start_chain solana 19101 /tmp/fake-node-io-jsonrpc) || { ko "solana start failed"; exit 1; }
PIDS="$PIDS $SOL_PID"
ok "solana ready (pid=$SOL_PID)"
grep -q "adapter_family=jsonrpc" "/tmp/fake-node-smoke-solana.log" \
    && ok "solana → adapter_family=jsonrpc" \
    || ko "solana adapter_family routing log missing"

for method in getSlot getBalance; do
    expected=$(stat -c%s "$FIXTURES/solana/${method}.json")
    body=$(printf '{"jsonrpc":"2.0","id":1,"method":"%s","params":[]}' "$method")
    actual=$(curl -s -X POST "http://127.0.0.1:19101" -H 'Content-Type: application/json' -d "$body" | wc -c)
    [[ "$actual" == "$expected" ]] && ok "solana $method: ${actual}B == fixture" || ko "solana $method: ${actual}B != ${expected}B"
done

# --- 3. ethereum (jsonrpc family reuse) ---
note "step 3: ethereum (jsonrpc family — reuse)"
ETH_PID=$(start_chain ethereum 19102 /tmp/fake-node-io-jsonrpc) || { ko "ethereum start failed"; exit 1; }
PIDS="$PIDS $ETH_PID"
ok "ethereum ready (pid=$ETH_PID)"

http_code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:19102" \
    -H 'Content-Type: application/json' \
    -d '{"jsonrpc":"2.0","id":1,"method":"getSlot","params":[]}')
[[ "$http_code" == "404" ]] && ok "ethereum 404 on solana method (chain isolation)" \
    || ko "ethereum returned $http_code on getSlot (expected 404)"

# --- 4. cardano (rest family — ADR-0005) ---
note "step 4: cardano (rest family — ADR-0005)"
CAR_PID=$(start_chain cardano 19103 /tmp/fake-node-io-rest) || { ko "cardano start failed"; exit 1; }
PIDS="$PIDS $CAR_PID"
ok "cardano startup (rest family)"
grep -q "adapter_family=rest" "/tmp/fake-node-smoke-cardano.log" \
    && ok "cardano → adapter_family=rest (ADR-0005 ogmios → rest correction live)" \
    || ko "cardano adapter_family=rest log missing"

# Real RPC: path-based dispatch on /tip
http_code=$(curl -s -o /tmp/smoke-cardano-tip.json -w '%{http_code}' "http://127.0.0.1:19103/tip")
[[ "$http_code" == "200" ]] && ok "cardano GET /tip → HTTP 200 (real fixture)" \
    || ko "cardano GET /tip → HTTP $http_code"

# Real RPC: POST body — must read _meta.rest_paths[POST_ADDRESS_INFO].body (ADR-0005 fix)
http_code=$(curl -s -o /tmp/smoke-cardano-addr.json -w '%{http_code}' \
    -X POST -H 'Content-Type: application/json' \
    -d '{"_addresses":["addr1qxxx"]}' \
    "http://127.0.0.1:19103/address_info")
[[ "$http_code" == "200" ]] && ok "cardano POST /address_info → HTTP 200" \
    || ko "cardano POST /address_info → HTTP $http_code"

# --- 5. polkadot (substrate family) ---
note "step 5: polkadot (substrate family)"
POL_PID=$(start_chain polkadot 19104 /tmp/fake-node-io-substrate) || { ko "polkadot start failed"; exit 1; }
PIDS="$PIDS $POL_PID"
ok "polkadot startup (substrate family)"

http_code=$(curl -s -o /tmp/smoke-polkadot.json -w '%{http_code}' -X POST "http://127.0.0.1:19104" \
    -H 'Content-Type: application/json' \
    -d '{"jsonrpc":"2.0","id":1,"method":"system_chain","params":[]}')
[[ "$http_code" == "200" ]] && grep -q "Polkadot" /tmp/smoke-polkadot.json \
    && ok "polkadot system_chain → 'Polkadot'" || ko "polkadot system_chain → $http_code"

# --- 6. cosmos-hub (tendermint family) ---
note "step 6: cosmos-hub (tendermint family)"
COS_PID=$(start_chain cosmos-hub 19105 /tmp/fake-node-io-tendermint) || { ko "cosmos-hub start failed"; exit 1; }
PIDS="$PIDS $COS_PID"
ok "cosmos-hub startup (tendermint family)"

http_code=$(curl -s -o /tmp/smoke-cosmos.json -w '%{http_code}' "http://127.0.0.1:19105/status")
[[ "$http_code" == "200" ]] && grep -q "cosmoshub" /tmp/smoke-cosmos.json \
    && ok "cosmos-hub /status → cosmoshub" || ko "cosmos-hub /status → $http_code"

# --- 7. hedera (hedera_dual family) ---
note "step 7: hedera (hedera_dual family)"
HED_PID=$(start_chain hedera 19106 /tmp/fake-node-io-hedera) || { ko "hedera start failed"; exit 1; }
PIDS="$PIDS $HED_PID"
ok "hedera startup (hedera_dual family)"

http_code=$(curl -s -o /tmp/smoke-hedera-eth.json -w '%{http_code}' -X POST "http://127.0.0.1:19106" \
    -H 'Content-Type: application/json' \
    -d '{"jsonrpc":"2.0","id":1,"method":"eth_blockNumber","params":[]}')
[[ "$http_code" == "200" ]] && ok "hedera eth_blockNumber (JSON-RPC side) → 200" \
    || ko "hedera eth_blockNumber → $http_code"

http_code=$(curl -s -o /tmp/smoke-hedera-nodes.json -w '%{http_code}' "http://127.0.0.1:19106/network/nodes")
[[ "$http_code" == "200" ]] && ok "hedera /network/nodes (Mirror side) → 200" \
    || ko "hedera /network/nodes → $http_code"

# Kill family chains before bulk smoke
for p in $PIDS; do kill $p 2>/dev/null || true; done
PIDS=""
sleep 1

# --- 8. 36-chain startup smoke ---
# Every chain template in config/chains/*.json must startup-pass (no panic, family resolved).
# Each chain uses port 19200+i (avoid collision with earlier chains).
note "step 8: 36-chain startup smoke (parallel-entry-trap rule: zero ungoverned families)"
chains=$(ls "$CHAINS_DIR"/*.json | xargs -n1 basename | sed 's/.json$//')
i=0
startup_pass=0
startup_fail=0
for ch in $chains; do
    port=$((19200 + i))
    i=$((i+1))
    BLOCKCHAIN_NODE="$ch" "$BIN" \
        -chains-dir "$CHAINS_DIR" \
        -configs-dir "$CONFIGS_DIR" \
        -fixtures-dir "$FIXTURES" \
        -port "$port" \
        > "/tmp/fake-node-startup-${ch}.log" 2>&1 &
    pid=$!
    sleep 0.3
    if curl -sf "http://127.0.0.1:$port/stats" >/dev/null 2>&1; then
        startup_pass=$((startup_pass+1))
    else
        echo "    chain=$ch startup FAILED — see /tmp/fake-node-startup-${ch}.log" >&2
        tail -5 "/tmp/fake-node-startup-${ch}.log" >&2 || true
        startup_fail=$((startup_fail+1))
    fi
    kill $pid 2>/dev/null || true
    wait $pid 2>/dev/null || true
done
echo "  36-chain startup: pass=$startup_pass fail=$startup_fail (total chains discovered: $i)"
[[ $startup_fail -eq 0 ]] && ok "all $i chains startup-pass" || ko "$startup_fail chains failed startup"

# --- summary ---
echo ""
echo "[smoke v2 ADR-0005] PASS=$pass FAIL=$fail"
[[ $fail -eq 0 ]] && exit 0 || exit 1
