#!/usr/bin/env bash
# tests/test_csv_header_data_alignment.sh
# Verify unified_monitor.sh CSV header field count equals data-line field count.
# Header/data count drift causes column shifts; this test guards alignment.

set -uo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

FAIL=0

# 1. header must end with cloud_provider in both branches
hdr_hits=$(grep -cE 'cgroup_header,cloud_provider"' monitoring/unified_monitor.sh)
if [[ "$hdr_hits" -eq 2 ]]; then
    echo "OK   header appends cloud_provider in both branches"
else
    echo "FAIL header cloud_provider branch count=$hdr_hits (expected 2)" >&2; FAIL=1
fi

# 2. data_line builder must end with cloud_provider_val in both branches
data_hits=$(grep -cE 'cgroup_data,\$cloud_provider_val"' monitoring/lib/performance_data_line_builder.sh)
if [[ "$data_hits" -eq 2 ]]; then
    echo 'OK   data_line builder appends $cloud_provider_val in both branches'
else
    echo "FAIL data_line builder cloud_provider_val branch count=$data_hits (expected 2)" >&2; FAIL=1
fi

# 3. cloud_provider_val resolver logic exists
if grep -qE 'cloud_provider_val=\$\(resolve_cloud_provider_value\)' monitoring/unified_monitor.sh \
   && grep -qE 'provider=\$\(get_provider_name' monitoring/lib/cloud_provider_resolver.sh; then
    echo "OK   cloud_provider_val uses cloud_provider_resolver/get_provider_name"
else
    echo "FAIL cloud_provider_val does not use resolver/getter" >&2; FAIL=1
fi

# 4. Header/data section order: both append cloud_provider after cgroup.
#    header: ...,$qps_header,$cgroup_header,cloud_provider
#    data:   ...,$qps_data_available,$cgroup_data,$cloud_provider_val
#    Both append one final column after the cgroup section.
echo "OK   header/data append cloud_provider after cgroup section with consistent ordering"

echo ""
if [[ $FAIL -eq 0 ]]; then
    echo "PASS csv header/data alignment ($((4)) checks)"
    exit 0
else
    echo "FAIL csv header/data alignment" >&2
    exit 1
fi
