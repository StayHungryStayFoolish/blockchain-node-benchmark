#!/usr/bin/env bash
# tools/e2e_smoke_tron_matrix.sh
# S3-A2: Tron e2e smoke — verifies dual-protocol routing through mock server.
#
# Tron is unique: HTTP /wallet/* (not JSON-RPC) + /jsonrpc subset (EVM-compat).
# The default e2e_smoke.sh ready-check uses POST / eth_blockNumber which still
# works for Tron because handle_evm is registered for chain=tron and routes /
# requests through process_jsonrpc → CHAIN_HANDLERS[tron]=handle_evm.
#
# This sibling additionally verifies the HTTP /wallet/* path returns Tron-shaped
# JSON (not a JSON-RPC envelope), which is the S3-A2 contract.

set -u
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

CHAIN=tron
PORT=28557
LOG_FILE="/tmp/e2e_smoke_${CHAIN}.log"

echo "═══════════════════════════════════════════════════════════════════════"
echo "  S3-A2 — Tron e2e_smoke (dual-protocol HTTP + JSON-RPC)"
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

# ── Step 2: directly verify HTTP /wallet/* routing (S3-A2 contract) ──
# Start dedicated mock for HTTP probe (e2e harness has torn down by now)
echo ""
echo "▸ Tron HTTP /wallet/* contract probe (port=$((PORT+11)))"
TRON_PORT=$((PORT + 11))
python3 tools/mock_rpc_server.py --chain "$CHAIN" --port "$TRON_PORT" \
    > "/tmp/e2e_smoke_${CHAIN}_http.log" 2>&1 &
TRON_PID=$!
trap "kill $TRON_PID 2>/dev/null || true" EXIT
sleep 2

http_pass=1

# Probe 1: /wallet/getnowblock → must return Tron envelope (block_header.raw_data.number)
echo -n "  ▸ POST /wallet/getnowblock ... "
resp=$(curl -sf -m 5 "http://localhost:${TRON_PORT}/wallet/getnowblock" \
    -X POST -H 'Content-Type: application/json' -d '{}' 2>/dev/null)
if echo "$resp" | python3 -c "
import sys, json
o = json.loads(sys.stdin.read())
n = o['block_header']['raw_data']['number']
assert isinstance(n, int) and n > 0, f'bad number: {n}'
print('OK number=' + str(n))
" 2>&1 | grep -q "^OK"; then
    echo "PASS"
else
    echo "FAIL (resp=$resp)"
    http_pass=0
fi

# Probe 2: /wallet/getaccount → must return {address, balance, ...}
echo -n "  ▸ POST /wallet/getaccount ... "
resp=$(curl -sf -m 5 "http://localhost:${TRON_PORT}/wallet/getaccount" \
    -X POST -H 'Content-Type: application/json' \
    -d '{"address":"TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t","visible":true}' 2>/dev/null)
if echo "$resp" | python3 -c "
import sys, json
o = json.loads(sys.stdin.read())
assert 'balance' in o, f'no balance: {o}'
assert o.get('address','').startswith('T'), f'bad address: {o.get(\"address\")}'
print('OK')
" 2>&1 | grep -q "^OK"; then
    echo "PASS"
else
    echo "FAIL (resp=$resp)"
    http_pass=0
fi

# Probe 3: /wallet/gettransactionbyid → must return {txID, ret:[{contractRet}]}
echo -n "  ▸ POST /wallet/gettransactionbyid ... "
resp=$(curl -sf -m 5 "http://localhost:${TRON_PORT}/wallet/gettransactionbyid" \
    -X POST -H 'Content-Type: application/json' \
    -d '{"value":"abcdef1234567890"}' 2>/dev/null)
if echo "$resp" | python3 -c "
import sys, json
o = json.loads(sys.stdin.read())
assert o.get('txID') == 'abcdef1234567890', f'txID mismatch: {o.get(\"txID\")}'
assert o['ret'][0]['contractRet'] == 'SUCCESS', f'ret bad: {o.get(\"ret\")}'
print('OK')
" 2>&1 | grep -q "^OK"; then
    echo "PASS"
else
    echo "FAIL (resp=$resp)"
    http_pass=0
fi

# Probe 4: /wallet/triggerconstantcontract → must return {result, constant_result}
echo -n "  ▸ POST /wallet/triggerconstantcontract ... "
resp=$(curl -sf -m 5 "http://localhost:${TRON_PORT}/wallet/triggerconstantcontract" \
    -X POST -H 'Content-Type: application/json' \
    -d '{"owner_address":"T0","contract_address":"T1","function_selector":"balanceOf(address)","parameter":"00","visible":true}' 2>/dev/null)
if echo "$resp" | python3 -c "
import sys, json
o = json.loads(sys.stdin.read())
assert o['result']['result'] is True, f'result not true: {o}'
assert isinstance(o.get('constant_result'), list), f'constant_result not list: {o}'
print('OK')
" 2>&1 | grep -q "^OK"; then
    echo "PASS"
else
    echo "FAIL (resp=$resp)"
    http_pass=0
fi

# Probe 5: JSON-RPC subset still works at / (Tron's eth_blockNumber)
echo -n "  ▸ POST / (eth_blockNumber JSON-RPC subset) ... "
resp=$(curl -sf -m 5 "http://localhost:${TRON_PORT}/" \
    -X POST -H 'Content-Type: application/json' \
    -d '{"jsonrpc":"2.0","id":1,"method":"eth_blockNumber","params":[]}' 2>/dev/null)
if echo "$resp" | python3 -c "
import sys, json
o = json.loads(sys.stdin.read())
r = o.get('result','')
assert r.startswith('0x'), f'no 0x result: {o}'
print('OK')
" 2>&1 | grep -q "^OK"; then
    echo "PASS"
else
    echo "FAIL (resp=$resp)"
    http_pass=0
fi

kill $TRON_PID 2>/dev/null || true
wait $TRON_PID 2>/dev/null || true

# ── Summary ──
echo ""
echo "───────────────────────────────────────────────────────────────────────"
if [[ $e2e_pass -eq 1 ]]; then
    echo "  PASS  $CHAIN e2e harness  (port $PORT, log $LOG_FILE)"
else
    echo "  FAIL  $CHAIN e2e harness  (port $PORT, log $LOG_FILE)"
    tail -8 "$LOG_FILE" | sed 's/^/        | /'
fi
if [[ $http_pass -eq 1 ]]; then
    echo "  PASS  $CHAIN HTTP /wallet/* probes (5/5)"
else
    echo "  FAIL  $CHAIN HTTP /wallet/* probes (see /tmp/e2e_smoke_${CHAIN}_http.log)"
fi
echo "───────────────────────────────────────────────────────────────────────"

if [[ $e2e_pass -eq 1 && $http_pass -eq 1 ]]; then
    echo "  TOTAL: 2 PASS / 0 FAIL"
    echo "═══════════════════════════════════════════════════════════════════════"
    exit 0
else
    echo "  TOTAL: $((e2e_pass + http_pass)) PASS / $((2 - e2e_pass - http_pass)) FAIL"
    echo "═══════════════════════════════════════════════════════════════════════"
    exit 1
fi
