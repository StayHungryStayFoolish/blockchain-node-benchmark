#!/usr/bin/env bash
# Verify fix: regex 现在能匹配 ● 前缀的 unit
set -u

SIMULATED_OUTPUT='  solana-validator.service                  loaded active running Solana
● failed-thing.service                        not-found active running Failed
  geth-mainnet.service                        loaded active running Geth
● bsc-node.service                            not-found active running BSC
× crashed-thing.service                       failed active running Crashed'

PASS=0; FAIL=0
pass() { echo "  ✓ $1"; PASS=$((PASS+1)); }
fail() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }

NEW_REGEX_PREFIX="^[^a-zA-Z0-9]*"

for case in 'solana-validator:✓' 'bsc-node:✓' 'geth-mainnet:✓' 'crashed-thing:✓' 'nonexistent:✗'; do
    unit="${case%:*}"
    expect="${case#*:}"
    if echo "$SIMULATED_OUTPUT" | grep -qE "${NEW_REGEX_PREFIX}${unit}([-@]|\.service)"; then
        actual="✓"
    else
        actual="✗"
    fi
    if [[ "$actual" == "$expect" ]]; then
        pass "$unit: expect=$expect actual=$actual"
    else
        fail "$unit: expect=$expect actual=$actual"
    fi
done

echo ""
echo "PASS: $PASS  FAIL: $FAIL"
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
