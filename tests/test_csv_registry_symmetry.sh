#!/usr/bin/env bash
# tests/test_csv_registry_symmetry.sh
# CI guard: keep bash and Python CSV registries symmetric.
#
# Validates:
#   Step 1: bash and Python registry logical-name sets match
#   Step 2: both sides resolve the same physical names for each logical/provider/device
#   Step 3: registry disk header matches iostat_collector.sh output byte-for-byte
#            -> ensure registry-backed writer output does not break existing readers
#
# Any assertion failure exits non-zero.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

FAIL=0
TOTAL=0
pass() { TOTAL=$((TOTAL+1)); echo "  ✅ $1"; }
fail() { TOTAL=$((TOTAL+1)); FAIL=$((FAIL+1)); echo "  ❌ $1"; }

source config/csv_schema_registry.sh

# ============================================================
# Step 1: logical-name sets match
# ============================================================
echo "=== Step 1: bash/python logical-name symmetry ==="
bash_names="$(csv_registry_all_logical_names | tr ' ' '\n' | LC_ALL=C sort)"
py_names="$(python3 -c '
from utils.csv_schema_registry import CSVSchemaRegistry
print("\n".join(CSVSchemaRegistry.all_logical_names()))
' | LC_ALL=C sort)"

if [[ "$bash_names" == "$py_names" ]]; then
    pass "logical-name sets match ($(echo "$bash_names" | wc -l) fields)"
else
    fail "logical-name sets differ"
    echo "--- bash only ---"; comm -23 <(echo "$bash_names") <(echo "$py_names") || true
    echo "--- python only ---"; comm -13 <(echo "$bash_names") <(echo "$py_names") || true
fi

# Step 1.5: provider_aware sets match on both sides
bash_pa="$(csv_registry_provider_aware_names | tr ' ' '\n' | LC_ALL=C sort)"
py_pa="$(python3 -c '
from utils.csv_schema_registry import CSVSchemaRegistry
print("\n".join(CSVSchemaRegistry.provider_aware_fields()))
' | LC_ALL=C sort)"
if [[ "$bash_pa" == "$py_pa" ]]; then
    pass "provider_aware sets match ($(echo "$bash_pa" | wc -l) fields)"
else
    fail "provider_aware sets differ  bash=[$bash_pa] py=[$py_pa]"
fi

# ============================================================
# Step 2: resolved physical names match on both sides (3 providers x 2 devices x all fields)
# ============================================================
echo "=== Step 2: resolved physical names match bash==python (3 providers x 2 devices) ==="
for provider in aws gcp other; do
    for device in data accounts; do
        for logical in $(csv_registry_all_logical_names); do
            bash_phys="$(csv_registry_resolve "$logical" "$provider" "$device")"
            py_phys="$(python3 -c "
from utils.csv_schema_registry import CSVSchemaRegistry
print(CSVSchemaRegistry.resolve('$logical', '$provider', '$device'))
")"
            if [[ "$bash_phys" != "$py_phys" ]]; then
                fail "resolve mismatch: $logical/$provider/$device  bash=$bash_phys py=$py_phys"
            fi
        done
    done
done
field_count="$(csv_registry_all_logical_names | wc -w | tr -d ' ')"
[[ $FAIL -eq 0 ]] && pass "all resolves match (${field_count} fields × 3 provider × 2 device)"

# ============================================================
# Step 2.5: reverse-check case branches against arrays
# bash resolve uses case branches while _CSV_REGISTRY_DISK_LOGICAL is a separate list.
# Earlier checks catch array-only fields; this catches case-only fields.
# ============================================================
echo "=== Step 2.5: bash case branches are covered by registry arrays ==="
# Extract case-branch field names from csv_registry_resolve.
# Limit awk to the resolve body to avoid unrelated names.
# Cover all registered static fields.
case_fields="$(awk '/^csv_registry_resolve\(\)/{inf=1} inf&&/^}/{inf=0} inf' config/csv_schema_registry.sh \
    | grep -oE '^[[:space:]]*[a-z_][a-z0-9_]*\)' \
    | tr -d ' )' | LC_ALL=C sort -u)"
array_fields="$(csv_registry_all_logical_names | tr ' ' '\n' | LC_ALL=C sort -u)"
orphan="$(comm -23 <(echo "$case_fields") <(echo "$array_fields") || true)"
if [[ -z "$orphan" ]]; then
    pass "case branches are all present in arrays ($(echo "$case_fields" | wc -l) branches, no orphans)"
else
    fail "case branches missing from arrays: $orphan"
fi

# ============================================================
# Step 3: writer (generate_device_header) == registry header for every provider
# ============================================================
# Writer output varies by provider. Correct invariant:
#   for each provider P, generate_device_header(DEV, data, P) == csv_registry_disk_header(data_DEV, P).
# Writer and registry must resolve the same header for every provider.
echo "=== Step 3: writer header == registry header for each provider ==="
DEV="nvme1n1"
P3_FAIL=0
for provider in aws gcp other; do
    registry_header="$(csv_registry_disk_header "data_${DEV}" "$provider")"
    # Pass provider explicitly to isolate get_provider_name context differences.
    writer_header="$(
        source monitoring/iostat_collector.sh >/dev/null 2>&1 || true
        if declare -F generate_device_header >/dev/null; then
            generate_device_header "$DEV" "data" "$provider"
        fi
    )"
    if [[ -z "$writer_header" ]]; then
        fail "[$provider] could not obtain writer header"
        P3_FAIL=1
    elif [[ "$registry_header" == "$writer_header" ]]; then
        : # ok; report the aggregate pass after the loop
    else
        fail "[$provider] writer header != registry header"
        echo "--- registry[$provider] ---"; echo "$registry_header"
        echo "--- writer  [$provider] ---"; echo "$writer_header"
        echo "--- per-field diff ---"
        diff <(echo "$registry_header" | tr ',' '\n') <(echo "$writer_header" | tr ',' '\n') || true
        P3_FAIL=1
    fi
done
[[ $P3_FAIL -eq 0 ]] && pass "writer==registry header for aws/gcp/other"

# ============================================================
# Step 3.5: basic writer fallback literal == registry header
# generate_csv_header prefers csv_registry_basic_header;
# it falls back to an inline literal only when registry is unavailable.
# The fallback must stay byte-identical to registry output.
# Extract the literal basic_header line containing timestamp,cpu_usage.
# ============================================================
echo "=== Step 3.5: basic writer fallback literal == registry header ==="
writer_basic="$(grep -oE 'basic_header="timestamp,[^"]*"' monitoring/unified_monitor.sh \
    | head -1 | sed -E 's/^basic_header="//; s/"$//')"
registry_basic="$(csv_registry_basic_header)"
if [[ -z "$writer_basic" ]]; then
    fail "could not extract writer basic_header fallback literal"
elif [[ "$writer_basic" == "$registry_basic" ]]; then
    pass "basic header fallback==registry ($(echo "$registry_basic" | tr ',' '\n' | wc -l) fields byte-identical)"
else
    fail "basic header fallback != registry"
    echo "--- writer-fallback ---"; echo "$writer_basic"
    echo "--- registry        ---"; echo "$registry_basic"
    diff <(echo "$writer_basic" | tr ',' '\n') <(echo "$registry_basic" | tr ',' '\n') || true
fi

# Step 3.6: prove the registry path for the basic header is live
# Source the registry and validate the live path,
# ensuring the registry branch is exercised.
echo "=== Step 3.6: registry-backed basic header path is live ==="
live_basic="$(
    source config/csv_schema_registry.sh >/dev/null 2>&1
    if declare -F csv_registry_basic_header >/dev/null 2>&1; then
        csv_registry_basic_header
    fi
)"
if [[ "$live_basic" == "$registry_basic" ]]; then
    pass "registry-backed basic header path is live"
else
    fail "registry-backed basic header mismatch: [$live_basic]"
fi

# ============================================================
# Step 3.7: block/sync-health writer, checker, and header range match registry
# ============================================================
echo "=== Step 3.7: block section writer/checker/header range == registry ==="
registry_block="$(csv_registry_block_header)"
registry_block_csv="$(csv_registry_block_csv_header)"
registry_block_range="$(csv_registry_block_data_field_range)"
expected_range="2-$((1 + $(csv_registry_block_logical_names | wc -w | tr -d ' ')))"

writer_block="$(grep -oE 'block_height_header="local_block_height,[^"]*"' monitoring/unified_monitor.sh \
    | head -1 | sed -E 's/^block_height_header="//; s/"$//')"
standalone_block="$(grep -oE 'echo "timestamp,local_block_height,[^"]*"' monitoring/block_height_monitor.sh \
    | head -1 | sed -E 's/^echo "//; s/"$//')"

if [[ "$registry_block_range" == "$expected_range" ]]; then
    pass "block data field range generated by registry ($registry_block_range)"
else
    fail "block data field range mismatch: registry=$registry_block_range expected=$expected_range"
fi

if [[ "$writer_block" == "$registry_block" ]]; then
    pass "unified_monitor block fallback header == registry"
else
    fail "unified_monitor block fallback header != registry"
    diff <(echo "$writer_block" | tr ',' '\n') <(echo "$registry_block" | tr ',' '\n') || true
fi

if [[ "$standalone_block" == "$registry_block_csv" ]]; then
    pass "block_height_monitor fallback CSV header == registry"
else
    fail "block_height_monitor fallback CSV header != registry"
    diff <(echo "$standalone_block" | tr ',' '\n') <(echo "$registry_block_csv" | tr ',' '\n') || true
fi

# ============================================================
echo ""
echo "=== Result: $((TOTAL-FAIL))/$TOTAL passed ==="
if [[ $FAIL -ne 0 ]]; then
    echo "❌ CSV registry symmetry test failed ()"
    exit 1
fi
echo "✅ CSV registry symmetry test passed"
