#!/usr/bin/env bash
# ci/check_parallel_entry.sh
# ===========================================================================
# CI guard against monitoring helper modules becoming disconnected from the
# main pipeline. Every registered helper must appear at least once as a
# source/import on the expected caller path.
#
# This script is dispatcher-table-driven: add a row to PARALLEL_ENTRY_RULES
# whenever you land a new replacement file. CI runs this on every push.
# ===========================================================================

set -u
# Don't `set -e` — we want to collect ALL violations, not fail-fast.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Each rule: "new_file|expected_caller_glob|description"
# Use '@@' as multi-caller separator. CI checks at least one match in EVERY
# caller-glob (so we don't accidentally allow drift in any single direction).
PARALLEL_ENTRY_RULES=(
    "monitoring/lib/cgroup_collector_wrapper.sh|monitoring/unified_monitor.sh|cgroup_collector wrapper must be sourced by unified_monitor main pipeline"
    "monitoring/cgroup_collector.py|monitoring/lib/cgroup_collector_wrapper.sh@@monitoring/monitoring_coordinator.sh|cgroup_collector must be invoked by the wrapper and diagnostics"
    "monitoring/kubelet_stats_client.py|monitoring/cgroup_collector.py@@monitoring/monitoring_coordinator.sh|kubelet_stats_client must have a live caller"
    "monitoring/pod_device_mapper.py|monitoring/monitoring_coordinator.sh|pod_device_mapper must be invoked from monitoring_coordinator diagnostics"
    "tools/single_disk_workload_profile.sh|tools/legacy_mock_rpc_e2e_smoke.sh|single_disk_workload_profile must be invoked by legacy mock RPC smoke harness"
)

# Optional: files whose mere presence (with NO live caller) should fail CI.
# Currently empty — add legacy file paths here as we deprecate them.
LEGACY_FILES_THAT_MUST_NOT_BE_SOURCED=()

# ---------------------------------------------------------------------------
violations=0
checked=0

check_rule() {
    local new_file="$1"
    local caller_globs="$2"
    local desc="$3"
    checked=$((checked + 1))

    if [[ ! -f "$new_file" ]]; then
        echo "FAIL: rule references missing file: $new_file"
        echo "      ($desc)"
        violations=$((violations + 1))
        return
    fi

    # Extract bare file name (without extension) for grep — Python imports
    # don't use .py suffix; sourced shell scripts do reference .sh suffix.
    local basename_noext basename_full
    basename_full="$(basename "$new_file")"
    basename_noext="${basename_full%.*}"

    # Loop through each caller glob (@@-separated). Use bash's native string
    # replacement to convert @@ -> newline, then read line-by-line. This
    # avoids IFS-based splitting bugs that fired in the v1 implementation.
    local callers_nl="${caller_globs//@@/$'\n'}"
    local missing=()
    local caller
    while IFS= read -r caller; do
        [[ -z "$caller" ]] && continue
        if [[ ! -f "$caller" ]]; then
            missing+=("$caller (file missing)")
            continue
        fi
        # Match either bare name or full basename — covers Python `import x`
        # and bash `source path/x.sh` and `bash path/x.sh`.
        # Use \b word boundaries so XXX_cgroup_collector_XXX doesn't match
        # cgroup_collector (caught by negative test on 2026-05-22).
        # Skip comment-only lines (^\s*#) to avoid false positives where
        # a caller "references" the file only in a banner comment.
        if ! grep -E "\b(${basename_noext}|${basename_full})\b" "$caller" \
              | grep -vE '^\s*#' \
              | grep -q .; then
            missing+=("$caller (no live reference to $basename_full or $basename_noext)")
        fi
    done <<< "$callers_nl"

    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "FAIL: $new_file"
        echo "      Expected referenced by: $caller_globs"
        echo "      Missing in:"
        local m
        for m in "${missing[@]}"; do
            echo "        - $m"
        done
        echo "      Rationale: $desc"
        echo ""
        violations=$((violations + 1))
    fi
}

check_legacy_not_sourced() {
    local legacy="$1"
    checked=$((checked + 1))
    if [[ -z "$legacy" ]]; then
        return
    fi
    local basename_full
    basename_full="$(basename "$legacy")"
    # Grep entire repo for active references (skip the legacy file itself)
    local hits
    hits=$(grep -rlE "(source[[:space:]]+.*${basename_full}|^\\.[[:space:]]+.*${basename_full})" \
              --include='*.sh' . 2>/dev/null | grep -v "/${basename_full}$" || true)
    if [[ -n "$hits" ]]; then
        echo "FAIL: legacy file $legacy still sourced by:"
        echo "$hits" | sed 's/^/        - /'
        echo ""
        violations=$((violations + 1))
    fi
}

# ---------------------------------------------------------------------------
echo "═══════════════════════════════════════════════════════════════════════"
echo "  Monitoring Entry Guard — ci/check_parallel_entry.sh"
echo "═══════════════════════════════════════════════════════════════════════"
echo ""

echo "[1/2] Checking replacement files have live callers..."
for rule in "${PARALLEL_ENTRY_RULES[@]}"; do
    IFS='|' read -r f c d <<<"$rule"
    check_rule "$f" "$c" "$d"
done

echo "[2/2] Checking legacy files are not actively sourced..."
if [[ ${#LEGACY_FILES_THAT_MUST_NOT_BE_SOURCED[@]} -gt 0 ]]; then
    for legacy in "${LEGACY_FILES_THAT_MUST_NOT_BE_SOURCED[@]}"; do
        check_legacy_not_sourced "$legacy"
    done
fi

echo ""
echo "───────────────────────────────────────────────────────────────────────"
if [[ $violations -eq 0 ]]; then
    echo "✓ PASS — $checked checks, 0 violations"
    exit 0
else
    echo "✗ FAIL — $checked checks, $violations violation(s)"
    echo ""
    echo "How to fix: either (a) add the missing source/import in the caller,"
    echo "or (b) update PARALLEL_ENTRY_RULES if the dependency genuinely changed."
    exit 1
fi
