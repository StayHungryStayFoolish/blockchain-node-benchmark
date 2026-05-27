#!/bin/bash
# record_fixtures.sh
# 一次性脚本: 从 solana mainnet 录 5 个常用 method 的 response,存 fixtures/
#
# 限流避险: 每个 method 间 sleep 2s
# 总耗时: ~10s
#
# 用法: bash record_fixtures.sh [output_dir]
#
# 关联: tools/proxy/poc-min/REPORT.md "录-放 PoC"

set -euo pipefail

OUT_DIR="${1:-$(dirname "$0")/../fixtures}"
ENDPOINT="${SOLANA_RPC:-https://api.mainnet-beta.solana.com}"

mkdir -p "$OUT_DIR"

# (method, params_json) 二元组
# 选 5 个常见 method, 覆盖 cheap/mid/expensive 三档:
#   cheap   : getSlot, getBalance
#   mid     : getLatestBlockhash
#   expensive: getBlock, getTransaction
declare -a METHODS=(
  "getSlot|[]"
  "getBalance|[\"83astBRguLMdt2h5U1Tpdq5tjFoJ6noeGwaY3mDLVcri\"]"
  "getLatestBlockhash|[]"
  "getBlock|[100000000,{\"encoding\":\"json\",\"maxSupportedTransactionVersion\":0}]"
  "getTransaction|[\"5VERv8NMvzbJMEkV8xnrLkEaWRtSz9CosKDYjCJjBRnbJLgp8uirBgmQpjKhoR4tjF3ZpRzrFmBV6UjKdiSZkQUW\",{\"encoding\":\"json\",\"maxSupportedTransactionVersion\":0}]"
)

echo "Recording fixtures to: $OUT_DIR"
echo "Endpoint: $ENDPOINT"
echo ""

FAILED=0
for entry in "${METHODS[@]}"; do
  method="${entry%%|*}"
  params="${entry#*|}"
  out_file="$OUT_DIR/${method}.json"

  body=$(printf '{"jsonrpc":"2.0","id":1,"method":"%s","params":%s}' "$method" "$params")
  echo "  [$method] body=$body"

  # -sS = silent + show error;-w = print http status
  status=$(curl -sS -o "$out_file" -w "%{http_code}" \
    -X POST "$ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "$body" || echo "ERR")

  if [[ "$status" != "200" ]]; then
    echo "    !! status=$status, body saved anyway for inspection"
    FAILED=$((FAILED+1))
  else
    size=$(stat -c%s "$out_file" 2>/dev/null || stat -f%z "$out_file")
    # 校验返回是 valid JSON 且有 result key 或 error key (允许 result=null)
    if jq -e 'has("result") or has("error")' "$out_file" > /dev/null 2>&1; then
      kind=$(jq -r 'if has("error") then "rpc_error" elif (.result == null) then "ok_null" else "ok" end' "$out_file")
      echo "    OK status=200 size=${size}B kind=$kind"
    else
      echo "    !! invalid JSON or missing result/error key"
      FAILED=$((FAILED+1))
    fi
  fi

  sleep 2
done

echo ""
echo "Done. Failed: $FAILED / ${#METHODS[@]}"
ls -la "$OUT_DIR"
exit $FAILED
