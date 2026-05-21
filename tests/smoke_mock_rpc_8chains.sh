#!/bin/bash
# S0.2 mock_rpc_server.py 8 链冒烟测试
# 启动每条链的 mock 监听不同端口,各 curl 几个核心 method,验证 200 + 合理 JSON
# 之后停掉所有 mock 进程

set -uo pipefail
cd "$(dirname "$0")/.."

BASE_PORT=18800
PIDS=()
LOG_DIR=$(mktemp -d)
trap 'echo "[cleanup] killing PIDs: ${PIDS[*]:-none}"; for pid in "${PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done; rm -rf "$LOG_DIR"' EXIT

# 8 链 + 各自核心 method 探针(method 必须真在 handler 里)
declare -A CHAIN_METHOD=(
  [solana]='getSlot'
  [ethereum]='eth_blockNumber'
  [bsc]='eth_blockNumber'
  [base]='eth_blockNumber'
  [scroll]='eth_blockNumber'
  [polygon]='eth_blockNumber'
  [starknet]='starknet_blockNumber'
  [sui]='sui_getLatestCheckpointSequenceNumber'
)

# 启动顺序固定,便于排查
CHAINS=(solana ethereum bsc base scroll polygon starknet sui)

PASS=0
FAIL=0
i=0
for chain in "${CHAINS[@]}"; do
  port=$((BASE_PORT + i))
  i=$((i+1))
  log="$LOG_DIR/${chain}.log"
  python3 tools/mock_rpc_server.py --chain "$chain" --port "$port" --no-ws --latency-ms 0 > "$log" 2>&1 &
  PIDS+=($!)
done

# 等所有 server READY
sleep 2

i=0
for chain in "${CHAINS[@]}"; do
  port=$((BASE_PORT + i))
  i=$((i+1))
  method="${CHAIN_METHOD[$chain]}"
  payload="{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"$method\",\"params\":[]}"
  resp=$(curl -s --max-time 5 -X POST -H 'Content-Type: application/json' \
              -d "$payload" "http://127.0.0.1:${port}" || echo "CURL_FAIL")
  if echo "$resp" | grep -q '"result"' && ! echo "$resp" | grep -q '"error"'; then
    echo "  ✓ $chain  port=$port  $method  -> $(echo "$resp" | head -c 80)..."
    PASS=$((PASS+1))
  else
    echo "  ✗ $chain  port=$port  $method  -> $resp"
    echo "    log tail:"; tail -5 "$log" | sed 's/^/      /'
    FAIL=$((FAIL+1))
  fi
done

echo ""
echo "=== Summary: $PASS passed, $FAIL failed (of 8 chains) ==="
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
