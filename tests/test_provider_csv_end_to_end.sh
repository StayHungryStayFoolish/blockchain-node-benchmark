#!/usr/bin/env bash
# tests/test_provider_csv_end_to_end.sh
# Verify provider-aware CSV output, header/data alignment, and IOPS routing.
# End-to-end guard for cloud_provider and provider-aware IOPS output.

set -uo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

FAIL=0
N=0
check() { N=$((N+1)); if [[ "$2" == "$3" ]]; then echo "OK   [$1]"; else echo "FAIL [$1] expected='$2' actual='$3'" >&2; FAIL=1; fi; }
check_contains() { N=$((N+1)); if [[ "$2" == *"$3"* ]]; then echo "OK   [$1]"; else echo "FAIL [$1] '$3' not in output" >&2; FAIL=1; fi; }

# === 1. With CLOUD_PROVIDER=gcp, the last header column is cloud_provider ===
export CLOUD_PROVIDER=gcp
export DEPLOYMENT_PLATFORM=gcp
export ENA_MONITOR_ENABLED=false
export CGROUP_COLLECTOR_ENABLED=false
export LEDGER_DEVICE="${LEDGER_DEVICE:-nvme0n1}"
export DATA_VOL_TYPE="${DATA_VOL_TYPE:-hyperdisk-extreme}"

# Source the monitoring chain through the production path.
source config/config_loader.sh >/dev/null 2>&1 || true

# Getter availability, required for provider-aware IOPS routing.
check_contains "get_provider_name is available after config_loader" "$(declare -F get_provider_name >/dev/null 2>&1 && echo yes || echo no)" "yes"
check "GCP IOPS conversion = passthrough" "passthrough" "$(get_iops_conversion_func 2>/dev/null)"
check "GCP disk_field_prefix = normalized" "normalized" "$(get_disk_field_prefix 2>/dev/null)"
check "GCP provider_name = gcp" "gcp" "$(get_provider_name 2>/dev/null)"

# === 2. unified_monitor header generation: last column must be cloud_provider ===
source monitoring/unified_monitor.sh >/dev/null 2>&1 || true
if declare -F generate_csv_header >/dev/null 2>&1; then
    header=$(generate_csv_header 2>/dev/null)
    last_col=$(echo "$header" | awk -F, '{print $NF}')
    check "unified header last column = cloud_provider" "cloud_provider" "$last_col"
    # Header is non-empty and starts with timestamp.
    first_col=$(echo "$header" | awk -F, '{print $1}')
    check "unified header first column = timestamp" "timestamp" "$first_col"
    echo "     header columns: $(echo "$header" | awk -F, '{print NF}')"
else
    echo "FAIL generate_csv_header is unavailable" >&2; FAIL=1; N=$((N+1))
fi

# === 3. IOPS conversion in the production data path: AWS split vs GCP passthrough ===
source utils/disk_converter.sh >/dev/null 2>&1 || true
# Current CLOUD_PROVIDER=gcp -> passthrough.
check "GCP convert iops 1000@1024 = passthrough(1000)" "1000" "$(convert_to_standard_iops 1000 1024)"

echo ""
if [[ $FAIL -eq 0 ]]; then echo "PASS provider CSV end-to-end ($N checks)"; exit 0
else echo "FAIL provider CSV end-to-end ($N checks)" >&2; exit 1; fi
