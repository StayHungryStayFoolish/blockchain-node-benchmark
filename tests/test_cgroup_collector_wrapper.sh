#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

log_warn() { :; }

# shellcheck source=/dev/null
source monitoring/lib/cgroup_collector_wrapper.sh

field_count() {
    awk -F',' '{print NF}' <<< "$1"
}

export CGROUP_COLLECTOR_ENABLED=false
disabled_header="$(get_cgroup_header)"
disabled_data="$(get_cgroup_data)"
[[ "$(field_count "$disabled_header")" == "19" ]] || { echo "Disabled header field count mismatch"; exit 1; }
[[ "$(field_count "$disabled_data")" == "19" ]] || { echo "Disabled data field count mismatch"; exit 1; }
[[ "$disabled_data" == *",disabled" ]] || { echo "Disabled data should mark meta_source=disabled"; exit 1; }

export CGROUP_COLLECTOR_ENABLED=true
export CGROUP_COLLECTOR_PATH="/does/not/exist/cgroup_collector.py"
missing_header="$(get_cgroup_header)"
missing_data="$(get_cgroup_data)"
[[ "$(field_count "$missing_header")" == "19" ]] || { echo "Missing collector header field count mismatch"; exit 1; }
[[ "$(field_count "$missing_data")" == "19" ]] || { echo "Missing collector data field count mismatch"; exit 1; }
[[ "$missing_data" == *",unavailable" ]] || { echo "Missing collector data should mark meta_source=unavailable"; exit 1; }

unset CGROUP_COLLECTOR_PATH
real_header="$(get_cgroup_header)"
real_data="$(get_cgroup_data)"
[[ "$(field_count "$real_header")" == "19" ]] || { echo "Real collector header field count mismatch"; exit 1; }
[[ "$(field_count "$real_data")" == "19" ]] || { echo "Real collector data field count mismatch"; exit 1; }

echo "✅ cgroup_collector_wrapper preserves 19-field fail-soft contract"
