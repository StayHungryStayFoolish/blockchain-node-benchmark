#!/bin/bash
# =====================================================================
# Test: validate_devices() degraded-mode behavior
# =====================================================================
# Verifies:
#   T1: STRICT_DEVICE_VALIDATION=true + missing device => return 1
#   T2: STRICT_DEVICE_VALIDATION unset (default false) + missing device =>
#       return 0, print ⚠️ WARN, export DEVICE_VALIDATION_DEGRADED=1
#   T3: STRICT_DEVICE_VALIDATION=false explicit + missing device => same as T2
#   T4: Valid LEDGER_DEVICE (auto-detect a real /dev block dev) => return 0, no DEGRADED
# =====================================================================

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IOSTAT_SH="${SCRIPT_DIR}/../monitoring/iostat_collector.sh"

PASS=0
FAIL=0

note() { echo "    $*"; }
ok()   { echo "  ✅ PASS: $*"; PASS=$((PASS+1)); }
bad()  { echo "  ❌ FAIL: $*"; FAIL=$((FAIL+1)); }

# Each test runs validate_devices() in a fresh subshell so we don't pollute env between cases.
run_case() {
    local desc="$1"; shift
    local script="$1"; shift
    echo ""
    echo "── Case: $desc"
    # Execute the inline script in a subshell that sources iostat_collector.sh definitions
    # but does NOT run its "main" block (BASH_SOURCE[0] != $0 path).
    local out rc
    out=$(bash -c "
        set +e
        # Silence sourcing noise
        source '$IOSTAT_SH' >/dev/null 2>&1
        $script
    " 2>&1)
    rc=$?
    echo "    [rc=$rc]"
    echo "$out" | sed 's/^/    > /'
    LAST_OUT="$out"
    LAST_RC=$rc
}

# ---------------------------------------------------------------------
# T1: STRICT=true, missing device => return 1
# ---------------------------------------------------------------------
run_case "STRICT=true + missing LEDGER_DEVICE => return 1" '
    export STRICT_DEVICE_VALIDATION=true
    export LEDGER_DEVICE=nvme9n9
    export ACCOUNTS_DEVICE=""
    export DATA_VOL_TYPE="gp3"
    validate_devices
    echo "RC=$?"
    echo "DEGRADED=${DEVICE_VALIDATION_DEGRADED:-unset}"
'
if echo "$LAST_OUT" | grep -q "RC=1" && echo "$LAST_OUT" | grep -q "Device validation failed"; then
    ok "T1: strict mode hard-fails with RC=1 and ❌ message"
else
    bad "T1: expected RC=1 + '❌ Device validation failed'"
fi
if echo "$LAST_OUT" | grep -q "DEGRADED=unset"; then
    ok "T1: DEVICE_VALIDATION_DEGRADED NOT set in strict mode"
else
    bad "T1: DEGRADED flag must not be set in strict mode"
fi

# ---------------------------------------------------------------------
# T2: STRICT unset (default false), missing device => return 0 + WARN + DEGRADED=1
# ---------------------------------------------------------------------
run_case "STRICT unset (default false) + missing LEDGER_DEVICE => return 0 + DEGRADED=1" '
    unset STRICT_DEVICE_VALIDATION
    export LEDGER_DEVICE=nvme9n9
    export ACCOUNTS_DEVICE=""
    export DATA_VOL_TYPE="gp3"
    validate_devices
    echo "RC=$?"
    echo "DEGRADED=${DEVICE_VALIDATION_DEGRADED:-unset}"
'
if echo "$LAST_OUT" | grep -q "RC=0"; then
    ok "T2: degraded mode returns RC=0"
else
    bad "T2: expected RC=0 in degraded mode"
fi
if echo "$LAST_OUT" | grep -q "⚠️"  && echo "$LAST_OUT" | grep -q "degraded mode"; then
    ok "T2: WARN message printed with ⚠️ and 'degraded mode'"
else
    bad "T2: expected ⚠️ WARN with 'degraded mode' substring"
fi
if echo "$LAST_OUT" | grep -q "DEGRADED=1"; then
    ok "T2: DEVICE_VALIDATION_DEGRADED=1 exported"
else
    bad "T2: DEVICE_VALIDATION_DEGRADED must be exported as 1"
fi
if echo "$LAST_OUT" | grep -q "❌ Device validation failed"; then
    bad "T2: must NOT print ❌ hard-fail message in degraded mode"
else
    ok "T2: no ❌ hard-fail message printed (warn-only)"
fi

# ---------------------------------------------------------------------
# T3: STRICT=false explicit => same as T2
# ---------------------------------------------------------------------
run_case "STRICT=false explicit + missing LEDGER_DEVICE => return 0 + DEGRADED=1" '
    export STRICT_DEVICE_VALIDATION=false
    export LEDGER_DEVICE=nvme9n9
    export ACCOUNTS_DEVICE=""
    export DATA_VOL_TYPE="gp3"
    validate_devices
    echo "RC=$?"
    echo "DEGRADED=${DEVICE_VALIDATION_DEGRADED:-unset}"
'
if echo "$LAST_OUT" | grep -q "RC=0" && echo "$LAST_OUT" | grep -q "DEGRADED=1"; then
    ok "T3: explicit STRICT=false also yields RC=0 + DEGRADED=1"
else
    bad "T3: expected RC=0 + DEGRADED=1 with explicit STRICT=false"
fi

# ---------------------------------------------------------------------
# T4: A real block device exists => happy path, no degraded flag
# Find any /dev/* block device that exists; skip the case if none found.
# ---------------------------------------------------------------------
REAL_DEV=""
for cand in sda sda1 vda vda1 nvme0n1 nvme0n1p1; do
    if [[ -b "/dev/$cand" ]]; then REAL_DEV="$cand"; break; fi
done
if [[ -n "$REAL_DEV" ]]; then
    run_case "Real device /dev/$REAL_DEV present => happy path, no DEGRADED" "
        unset STRICT_DEVICE_VALIDATION
        export LEDGER_DEVICE=$REAL_DEV
        export ACCOUNTS_DEVICE=\"\"
        export DATA_VOL_TYPE=\"gp3\"
        validate_devices
        echo \"RC=\$?\"
        echo \"DEGRADED=\${DEVICE_VALIDATION_DEGRADED:-unset}\"
    "
    if echo "$LAST_OUT" | grep -q "RC=0" && echo "$LAST_OUT" | grep -q "DEGRADED=unset"; then
        ok "T4: happy path returns RC=0 and does NOT set DEGRADED"
    else
        bad "T4: expected RC=0 and DEGRADED=unset for valid device"
    fi
else
    echo ""
    echo "── Case: T4 skipped (no real /dev block device found among candidates)"
fi

# ---------------------------------------------------------------------
echo ""
echo "==========================================================="
echo "  Summary: PASS=$PASS  FAIL=$FAIL"
echo "==========================================================="
if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
exit 0
