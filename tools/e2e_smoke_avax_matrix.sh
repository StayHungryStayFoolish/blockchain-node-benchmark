#!/usr/bin/env bash
# tools/e2e_smoke_avax_matrix.sh
# S3-A3: Avalanche X-Chain e2e smoke — verifies AVM JSON-RPC dispatch through mock server.
#
# Avalanche X-Chain (AVM) uses JSON-RPC 2.0 but is distinct from EVM in 4 ways:
#   1. params is OBJECT not array  → {"height":"517990","encoding":"json"}
#   2. uint64 fields are STRINGS in responses ("517990" not 517990)
#   3. IDs use cb58 encoding, not hex
#   4. Multi-endpoint: /ext/bc/X (avm.*), /ext/info (info.*), /ext/bc/P (platform.*)
#
# The default e2e_smoke.sh ready-check uses POST / eth_blockNumber which still
# works for avalanche-x because CHAIN_HANDLERS[avalanche-x]=handle_evm is registered
# as a placeholder for the JSON-RPC dispatch table (the / path falls through to it).
#
# This sibling additionally verifies the /ext/bc/X path returns AVM-shaped JSON
# (with uint64-as-string + object params), which is the S3-A3 contract.

set -u
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

CHAIN=avalanche-x
PORT=28569
LOG_FILE="/tmp/e2e_smoke_${CHAIN}.log"

echo "═══════════════════════════════════════════════════════════════════════"
echo "  S3-A3 — Avalanche X-Chain e2e_smoke (AVM JSON-RPC + multi-endpoint)"
echo "═══════════════════════════════════════════════════════════════════════"

# ── Step 1: run the standard e2e_smoke harness for JSON-RPC plumbing ──
printf "▸ %-12s (port=%5d, e2e_smoke harness) ... " "$CHAIN" "$PORT"
if MOCK_CHAIN="$CHAIN" MOCK_PORT="$PORT" \
   timeout 90 bash tools/e2e_smoke.sh > "$LOG_FILE" 2>&1; then
    echo "PASS"
    e2e_pass=1
else
    rc=$?
    echo "FAIL (exit=$rc)"
    e2e_pass=0
fi

# ── Step 2: directly verify /ext/bc/X + /ext/info + /ext/bc/P routing (S3-A3 contract) ──
# Start dedicated mock for AVM probe (e2e harness has torn down by now)
echo ""
echo "▸ Avalanche AVM contract probe (port=$((PORT+11)))"
AVAX_PORT=$((PORT + 11))
python3 tools/mock_rpc_server.py --chain "$CHAIN" --port "$AVAX_PORT" \
    > "/tmp/e2e_smoke_${CHAIN}_avm.log" 2>&1 &
AVAX_PID=$!
trap "kill $AVAX_PID 2>/dev/null || true" EXIT
sleep 2

avm_pass=1

# Probe 1: avm.getHeight → result.height is STRING (uint64-as-string contract)
echo -n "  ▸ POST /ext/bc/X avm.getHeight ... "
resp=$(curl -sf -m 5 "http://localhost:${AVAX_PORT}/ext/bc/X" \
    -X POST -H 'Content-Type: application/json' \
    -d '{"jsonrpc":"2.0","id":1,"method":"avm.getHeight","params":{}}' 2>/dev/null)
if echo "$resp" | python3 -c "
import sys, json
o = json.loads(sys.stdin.read())
h = o['result']['height']
assert isinstance(h, str), f'height must be STRING per uint64-as-string contract, got {type(h).__name__}: {h!r}'
assert int(h) > 0, f'height must parse to positive int: {h}'
print('OK height=' + h)
" 2>&1 | grep -q "^OK"; then
    echo "PASS"
else
    echo "FAIL (resp=$resp)"
    avm_pass=0
fi

# Probe 2: avm.getBlockByHeight with OBJECT params (not array)
echo -n "  ▸ POST /ext/bc/X avm.getBlockByHeight ... "
resp=$(curl -sf -m 5 "http://localhost:${AVAX_PORT}/ext/bc/X" \
    -X POST -H 'Content-Type: application/json' \
    -d '{"jsonrpc":"2.0","id":1,"method":"avm.getBlockByHeight","params":{"height":"517990","encoding":"json"}}' 2>/dev/null)
if echo "$resp" | python3 -c "
import sys, json
o = json.loads(sys.stdin.read())
b = o['result']['block']
assert 'parentID' in b, f'no parentID: {b}'
assert 'txs' in b, f'no txs: {b}'
assert o['result']['encoding'] == 'json', f'encoding must echo: {o[\"result\"]}'
print('OK')
" 2>&1 | grep -q "^OK"; then
    echo "PASS"
else
    echo "FAIL (resp=$resp)"
    avm_pass=0
fi

# Probe 3: avm.getAllBalances → multi-asset (≥2 distinct assets)
echo -n "  ▸ POST /ext/bc/X avm.getAllBalances ... "
resp=$(curl -sf -m 5 "http://localhost:${AVAX_PORT}/ext/bc/X" \
    -X POST -H 'Content-Type: application/json' \
    -d '{"jsonrpc":"2.0","id":1,"method":"avm.getAllBalances","params":{"address":"X-avax13k6hxpfuu80dlnqlqs0dxxjrzl4lxz94n38vnw"}}' 2>/dev/null)
if echo "$resp" | python3 -c "
import sys, json
o = json.loads(sys.stdin.read())
bals = o['result']['balances']
assert isinstance(bals, list) and len(bals) >= 2, f'multi-asset model requires >=2 entries: {bals}'
for entry in bals:
    assert 'asset' in entry and 'balance' in entry, f'malformed entry: {entry}'
    assert isinstance(entry['balance'], str), f'balance must be STRING: {entry}'
print('OK n_assets=' + str(len(bals)))
" 2>&1 | grep -q "^OK"; then
    echo "PASS"
else
    echo "FAIL (resp=$resp)"
    avm_pass=0
fi

# Probe 4: avm.getUTXOs → numFetched is STRING, addresses is LIST
echo -n "  ▸ POST /ext/bc/X avm.getUTXOs ... "
resp=$(curl -sf -m 5 "http://localhost:${AVAX_PORT}/ext/bc/X" \
    -X POST -H 'Content-Type: application/json' \
    -d '{"jsonrpc":"2.0","id":1,"method":"avm.getUTXOs","params":{"addresses":["X-avax13k6hxpfuu80dlnqlqs0dxxjrzl4lxz94n38vnw"],"limit":10,"encoding":"hex"}}' 2>/dev/null)
if echo "$resp" | python3 -c "
import sys, json
o = json.loads(sys.stdin.read())
r = o['result']
assert isinstance(r['numFetched'], str), f'numFetched must be STRING: {r[\"numFetched\"]!r}'
assert isinstance(r['utxos'], list), f'utxos must be list: {r}'
assert 'endIndex' in r, f'no endIndex (pagination): {r}'
print('OK')
" 2>&1 | grep -q "^OK"; then
    echo "PASS"
else
    echo "FAIL (resp=$resp)"
    avm_pass=0
fi

# Probe 5: /ext/info routing — info.getNodeVersion (multi-endpoint contract)
echo -n "  ▸ POST /ext/info info.getNodeVersion ... "
resp=$(curl -sf -m 5 "http://localhost:${AVAX_PORT}/ext/info" \
    -X POST -H 'Content-Type: application/json' \
    -d '{"jsonrpc":"2.0","id":1,"method":"info.getNodeVersion","params":{}}' 2>/dev/null)
if echo "$resp" | python3 -c "
import sys, json
o = json.loads(sys.stdin.read())
assert 'version' in o['result'], f'no version: {o}'
assert o['result']['version'].startswith('avalanche/'), f'bad version: {o[\"result\"]}'
print('OK')
" 2>&1 | grep -q "^OK"; then
    echo "PASS"
else
    echo "FAIL (resp=$resp)"
    avm_pass=0
fi

# Probe 6: namespace isolation — info.* MUST NOT be accepted at /ext/bc/X
echo -n "  ▸ POST /ext/bc/X info.getBlockchainID (must reject) ... "
resp=$(curl -s -m 5 "http://localhost:${AVAX_PORT}/ext/bc/X" \
    -X POST -H 'Content-Type: application/json' \
    -d '{"jsonrpc":"2.0","id":1,"method":"info.getBlockchainID","params":{}}' 2>/dev/null)
if echo "$resp" | python3 -c "
import sys, json
o = json.loads(sys.stdin.read())
assert 'error' in o, f'should have rejected info.* at /ext/bc/X: {o}'
assert o['error']['code'] == -32601, f'wrong error code: {o[\"error\"]}'
print('OK')
" 2>&1 | grep -q "^OK"; then
    echo "PASS"
else
    echo "FAIL (resp=$resp)"
    avm_pass=0
fi

kill $AVAX_PID 2>/dev/null || true
wait $AVAX_PID 2>/dev/null || true

# ── Summary ──
echo ""
echo "───────────────────────────────────────────────────────────────────────"
if [[ $e2e_pass -eq 1 ]]; then
    echo "  PASS  $CHAIN e2e harness  (port $PORT, log $LOG_FILE)"
else
    echo "  FAIL  $CHAIN e2e harness  (port $PORT, log $LOG_FILE)"
    tail -8 "$LOG_FILE" | sed 's/^/        | /'
fi
if [[ $avm_pass -eq 1 ]]; then
    echo "  PASS  $CHAIN AVM contract probes (6/6)"
else
    echo "  FAIL  $CHAIN AVM contract probes (see /tmp/e2e_smoke_${CHAIN}_avm.log)"
fi
echo "───────────────────────────────────────────────────────────────────────"

if [[ $e2e_pass -eq 1 && $avm_pass -eq 1 ]]; then
    echo "  TOTAL: 2 PASS / 0 FAIL"
    echo "═══════════════════════════════════════════════════════════════════════"
    exit 0
else
    echo "  TOTAL: $((e2e_pass + avm_pass)) PASS / $((2 - e2e_pass - avm_pass)) FAIL"
    echo "═══════════════════════════════════════════════════════════════════════"
    exit 1
fi
