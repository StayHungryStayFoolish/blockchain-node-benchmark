#!/bin/bash
# =====================================================================
# Unit test: systemctl unit-name regex in deployment_mode_detector.sh
# =====================================================================
# Purpose: prevent regression of v1.4.3 fix for Issue #1 (multi-instance
#          unit names like solana-validator-mainnet.service were missed
#          by the v1.3 regex `^\s*${unit}(\.service|@)`).
#
# Strategy: extract the regex pattern from the production grep -E line,
#           feed it 19 hand-crafted systemd line samples, assert each
#           match/no-match matches the expected truth table.
#
# Why not exec the detector? It calls real systemctl, which we cannot
# mock cheaply on a cloudtop. We test the regex in isolation, which is
# exactly the layer where the v1.3 bug lived.
#
# Failure mode this guards against: someone widens the regex (e.g. drops
# the anchor) and starts matching `some-geth-tool.service`, OR narrows
# it back and starts missing `solana-validator-mainnet.service`.
# =====================================================================
set -u

cd "$(dirname "$0")/.." || exit 1
DETECTOR="config/deployment_mode_detector.sh"

# Extract the exact regex pattern from the production code. If the
# detector ever changes the grep line shape, this extraction will fail
# and force a test-update — which is the right outcome.
REGEX_TEMPLATE=$(grep -oE 'grep -qE "[^"]+"' "$DETECTOR" | head -1 \
    | sed -E 's/grep -qE "(.*)"/\1/')

if [[ -z "$REGEX_TEMPLATE" ]]; then
    echo "❌ FAIL: could not extract regex from $DETECTOR"
    exit 1
fi

echo "Extracted regex template: $REGEX_TEMPLATE"
echo

PASS=0
FAIL=0

# Run one case: substitute ${unit} into template, feed `line` to grep -qE,
# assert exit matches expectation.
run_case() {
    local unit="$1"
    local line="$2"
    local expect="$3"  # "match" | "nomatch"
    local desc="$4"

    # Substitute ${unit} placeholder with the literal (escape regex metachars)
    local unit_escaped="${unit//./\\.}"
    local pattern="${REGEX_TEMPLATE//\$\{unit\}/$unit_escaped}"

    if echo "$line" | grep -qE "$pattern"; then
        actual="match"
    else
        actual="nomatch"
    fi

    if [[ "$actual" == "$expect" ]]; then
        PASS=$((PASS + 1))
        # echo "  ✓ $desc"
    else
        FAIL=$((FAIL + 1))
        echo "  ❌ FAIL: $desc"
        echo "      unit='$unit'  line='$line'"
        echo "      expected=$expect  actual=$actual  pattern='$pattern'"
    fi
}

# =====================================================================
# Truth table — 19 cases derived from real production unit naming
# =====================================================================

# --- Standard naming (must match) ---
run_case "solana-validator" "  solana-validator.service        loaded active running" "match" "std: solana-validator.service"
run_case "geth"             "  geth.service                    loaded active running" "match" "std: geth.service"
run_case "sui-node"         "  sui-node.service                loaded active running" "match" "std: sui-node.service"

# --- systemd template instance (@) ---
run_case "solana-validator" "  solana-validator@mainnet.service loaded active running" "match" "tmpl: solana-validator@mainnet"
run_case "geth"             "  geth@1.service                   loaded active running" "match" "tmpl: geth@1"

# --- Suffix variant (-) — v1.4.3 NEW SUPPORT ---
run_case "solana-validator" "  solana-validator-mainnet.service loaded active running" "match" "suffix: solana-validator-mainnet"
run_case "solana-validator" "  solana-validator-1.service       loaded active running" "match" "suffix: solana-validator-1"
run_case "geth"             "  geth-mainnet.service             loaded active running" "match" "suffix: geth-mainnet"
run_case "bor"              "  bor-1.service                    loaded active running" "match" "suffix: bor-1"

# --- Anti-collision: EVM chains must stay isolated ---
run_case "geth"             "  bsc-geth.service                 loaded active running" "nomatch" "isolation: geth vs bsc-geth"
run_case "geth"             "  scroll-geth.service              loaded active running" "nomatch" "isolation: geth vs scroll-geth"
run_case "bsc-geth"         "  bsc-geth.service                 loaded active running" "match" "bsc-geth.service"
run_case "bsc-geth"         "  bsc-geth-mainnet.service         loaded active running" "match" "bsc-geth-mainnet"
run_case "scroll-geth"      "  scroll-geth.service              loaded active running" "match" "scroll-geth.service"

# --- Polygon: ops may prefix bor but we only register bare 'bor' ---
# This is INTENTIONAL nomatch: if ops uses polygon-bor, they should add
# the explicit unit to the array OR use bare 'bor.service'.
run_case "bor"              "  polygon-bor.service              loaded active running" "nomatch" "no-prefix: polygon-bor"

# --- Non-business units (must not false-positive) ---
run_case "geth"             "  systemd-networkd.service         loaded active running" "nomatch" "noise: systemd-networkd"
run_case "solana-validator" "  ssh.service                      loaded active running" "nomatch" "noise: ssh"
run_case "sui-node"         "  cron.service                     loaded active running" "nomatch" "noise: cron"

# --- Substring trap: unit name in middle of line ---
run_case "geth"             "  some-geth-tool.service           loaded active running" "nomatch" "trap: some-geth-tool"

# =====================================================================
echo
echo "=== Summary: $PASS passed, $FAIL failed (of $((PASS + FAIL)) cases) ==="
[[ "$FAIL" -eq 0 ]] || exit 1
