#!/usr/bin/env bash
# ci/check_csv_registry_bypass.sh
# CI guard: prevent readers from bypassing the CSV registry and writing raw
# provider-aware physical column names directly.
#
# Rules:
#   - Once a reader is migrated to the registry, add it to MIGRATED_FILES.
#   - Migrated readers must not emit raw provider-aware physical column names.
#   - Unmigrated readers are not enforced until they are added to the list.
#

set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Raw provider-aware physical column-name pattern.
# Match only concrete CSV column shapes such as
# (data|accounts)_<device>_normalized_(iops|throughput) to avoid false positives
# from unrelated uses of words like "normalized" or "baseline".
VIOLATION_PATTERN='(data|accounts)_[a-z0-9]+_normalized_(iops|throughput)|(data|accounts)_[a-z0-9]+_baseline_(iops|throughput)'
# Backward-compatible variable alias.
BARE_PATTERN="$VIOLATION_PATTERN"

# Migrated file list.
MIGRATED_FILES=(
    tools/disk_bottleneck_detector.sh
    monitoring/bottleneck_detector.sh
)

# Files allowed to define physical column names directly.
ALLOWLIST_REGEX='^(config/csv_schema_registry\.sh|utils/csv_schema_registry\.py|config/providers/|tests/test_csv_registry_symmetry|ci/check_csv_registry_bypass|monitoring/iostat_collector\.sh)'

FAIL=0
echo "=== CSV registry bypass guard (migrated files: ${#MIGRATED_FILES[@]}) ==="

if [[ ${#MIGRATED_FILES[@]} -eq 0 ]]; then
    echo "  ℹ️  No migrated files registered yet; guard is ready"
    echo "  ℹ️  Current raw provider-aware physical column-name distribution:"
    grep -rlE "$BARE_PATTERN" --include='*.py' --include='*.sh' . 2>/dev/null \
        | grep -vE "$ALLOWLIST_REGEX" | sed 's/^/      /' || echo "      (none)"
    echo "✅ CSV registry bypass guard ready"
    exit 0
fi

# Check every migrated file for raw provider-aware physical names
for f in "${MIGRATED_FILES[@]}"; do
    if [[ ! -f "$f" ]]; then
        echo "  ⚠️  Migrated file is missing: $f (is the list stale?)"
        continue
    fi
    # Match concrete CSV physical column names only.
    hits="$(grep -nE "$VIOLATION_PATTERN" "$f" 2>/dev/null || true)"
    if [[ -n "$hits" ]]; then
        echo "  ❌ Migrated file still contains raw provider-aware physical column names: $f"
        echo "$hits" | sed 's/^/        /'
        FAIL=$((FAIL+1))
    else
        echo "  ✅ $f has no raw physical column names (registry path is used)"
    fi
done

if [[ $FAIL -ne 0 ]]; then
    echo "❌ registry bypass guard failed (${FAIL} file(s)) - migrated readers must not use raw provider-aware physical names"
    exit 1
fi
echo "✅ registry bypass guard passed"
