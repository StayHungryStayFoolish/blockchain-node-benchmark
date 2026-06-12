#!/bin/bash
# Unit test for deployment_mode_detector.sh — mock all 6 modes via env override
# Use standalone direct-exec mode to avoid nested bash -c quoting issues.
set -u

cd "$(dirname "$0")/.." || exit 1
DETECTOR="config/deployment_mode_detector.sh"

PASS=0
FAIL=0

test_mode() {
    local expected="$1"
    local desc="$2"
    local out
    # Execute detector directly with an env prefix; tail selects DEPLOYMENT_MODE.
    out=$(DEPLOYMENT_MODE="$expected" bash "$DETECTOR" 2>&1 | grep "^  DEPLOYMENT_MODE=" | head -1)
    if [[ "$out" == "  DEPLOYMENT_MODE=$expected" ]]; then
        echo "  ✅ PASS: $desc → $out"
        PASS=$((PASS+1))
    else
        echo "  ❌ FAIL: $desc — expected '  DEPLOYMENT_MODE=$expected', got: '$out'"
        FAIL=$((FAIL+1))
    fi
}

test_invalid() {
    local bad="$1"
    local rc
    DEPLOYMENT_MODE="$bad" bash "$DETECTOR" >/dev/null 2>&1
    rc=$?
    if [[ $rc -eq 1 ]]; then
        echo "  ✅ PASS: invalid '$bad' rejected (exit=1)"
        PASS=$((PASS+1))
    else
        echo "  ❌ FAIL: invalid '$bad' should be rejected, exit=$rc"
        FAIL=$((FAIL+1))
    fi
}

test_source_chain() {
    local expected="$1"
    local expected_src="$2"
    local desc="$3"
    local out
    out=$(DEPLOYMENT_MODE="$expected" bash "$DETECTOR" 2>&1 | grep "^  DEPLOYMENT_MODE_SOURCE=" | head -1)
    if [[ "$out" == "  DEPLOYMENT_MODE_SOURCE=$expected_src" ]]; then
        echo "  ✅ PASS: $desc → $out"
        PASS=$((PASS+1))
    else
        echo "  ❌ FAIL: $desc — expected '  DEPLOYMENT_MODE_SOURCE=$expected_src', got: '$out'"
        FAIL=$((FAIL+1))
    fi
}

test_auto_environment() {
    # auto mode should detect Docker when the test runs in the Docker harness,
    # otherwise it should take the default bare-VM branch.
    local expected_mode="vm_bare"
    local expected_source="default"
    if [[ -f /.dockerenv ]]; then
        expected_mode="docker"
        expected_source="dockerenv"
    fi

    local out
    out=$(bash "$DETECTOR" 2>&1 | grep "^  DEPLOYMENT_MODE=" | head -1)
    if [[ "$out" == "  DEPLOYMENT_MODE=$expected_mode" ]]; then
        echo "  ✅ PASS: auto-detect current environment → $out"
        PASS=$((PASS+1))
    else
        echo "  ❌ FAIL: auto-detect current environment — expected $expected_mode, got: '$out'"
        FAIL=$((FAIL+1))
    fi
    out=$(bash "$DETECTOR" 2>&1 | grep "^  DEPLOYMENT_MODE_SOURCE=" | head -1)
    if [[ "$out" == "  DEPLOYMENT_MODE_SOURCE=$expected_source" ]]; then
        echo "  ✅ PASS: auto-detect source → $expected_source"
        PASS=$((PASS+1))
    else
        echo "  ❌ FAIL: auto-detect source — expected $expected_source, got: '$out'"
        FAIL=$((FAIL+1))
    fi
}

echo "=== Test 1: Explicit override (6 valid modes) ==="
test_mode "vm_bare"     "explicit vm_bare"
test_mode "vm_systemd"  "explicit vm_systemd"
test_mode "docker"      "explicit docker"
test_mode "k8s_eks"     "explicit k8s_eks"
test_mode "k8s_gke"     "explicit k8s_gke"
test_mode "k8s_other"   "explicit k8s_other"

echo
echo "=== Test 2: Invalid modes rejected (exit=1) ==="
test_invalid "invalid_mode"
test_invalid "vm"
test_invalid "k8s"

echo
echo "=== Test 3: SOURCE chain correctly attributed ==="
test_source_chain "vm_bare"     "env" "vm_bare → source=env"
test_source_chain "docker"      "env" "docker  → source=env"
test_source_chain "k8s_eks"     "env" "k8s_eks → source=env"

echo
echo "=== Test 4: Auto-detect on current environment ==="
test_auto_environment

echo
echo "=== Summary ==="
echo "  PASS: $PASS"
echo "  FAIL: $FAIL"
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
