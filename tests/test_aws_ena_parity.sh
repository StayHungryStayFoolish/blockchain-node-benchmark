#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

TEST_ROOT="$(mktemp -d)"
cleanup() {
    rm -rf "$TEST_ROOT"
}
trap cleanup EXIT

export PATH="$TEST_ROOT/bin:$PATH"
export NETWORK_INTERFACE="eth-test0"
export NET_SYS_CLASS_DIR="$TEST_ROOT/sys/class/net"
export ENA_ALLOWANCE_FIELDS_STR="bw_in_allowance_exceeded bw_out_allowance_exceeded pps_allowance_exceeded conntrack_allowance_exceeded linklocal_allowance_exceeded conntrack_allowance_available"
export LOGS_DIR="$TEST_ROOT/logs"
export TMP_DIR="$TEST_ROOT/tmp"
export SESSION_TIMESTAMP="20260611_120000"
export LOG_LEVEL=1
export DEPLOYMENT_PLATFORM="aws"

mkdir -p "$TEST_ROOT/bin" "$NET_SYS_CLASS_DIR/$NETWORK_INTERFACE/statistics" "$LOGS_DIR" "$TMP_DIR"

cat > "$TEST_ROOT/bin/ethtool" <<'EOF'
#!/usr/bin/env bash
if [[ "$1" == "-i" ]]; then
    cat <<DRIVER
driver: ena
version: test
DRIVER
    exit 0
fi

if [[ "$1" == "-S" ]]; then
    cat <<STATS
     bw_in_allowance_exceeded: 1
     bw_out_allowance_exceeded: 2
     pps_allowance_exceeded: 3
     conntrack_allowance_exceeded: 4
     linklocal_allowance_exceeded: 5
     conntrack_allowance_available: 600
STATS
    exit 0
fi

exit 1
EOF
chmod +x "$TEST_ROOT/bin/ethtool"

printf '1000\n' > "$NET_SYS_CLASS_DIR/$NETWORK_INTERFACE/statistics/rx_bytes"
printf '2000\n' > "$NET_SYS_CLASS_DIR/$NETWORK_INTERFACE/statistics/tx_bytes"
printf '300\n' > "$NET_SYS_CLASS_DIR/$NETWORK_INTERFACE/statistics/rx_packets"
printf '400\n' > "$NET_SYS_CLASS_DIR/$NETWORK_INTERFACE/statistics/tx_packets"

# shellcheck source=/dev/null
source monitoring/network/aws_ena.sh
export NETWORK_INTERFACE="eth-test0"
export NET_SYS_CLASS_DIR="$TEST_ROOT/sys/class/net"

init_network_monitoring
new_header="$(generate_network_csv_header)"
new_row="$(collect_network_metrics)"

IFS=',' read -r -a new_fields <<< "$new_row"

expected_values=(
    "eth-test0"
    "1000"
    "2000"
    "300"
    "400"
    "1"
    "2"
    "3"
    "4"
    "5"
    "600"
    "1"
    "1"
    "1"
)

for idx in "${!expected_values[@]}"; do
    field_idx=$((idx + 1))
    if [[ "${new_fields[$field_idx]}" != "${expected_values[$idx]}" ]]; then
        echo "AWS ENA field mismatch at index $field_idx: expected='${expected_values[$idx]}' actual='${new_fields[$field_idx]}'"
        echo "new header: $new_header"
        echo "new row:    $new_row"
        exit 1
    fi
done

grep -q "network_saturation_signal" <<< "$new_header" || {
    echo "New header missing network_saturation_signal"
    exit 1
}

grep -q "ena_pps_limited,ena_bandwidth_limited,network_saturation_signal" <<< "$new_header" || {
    echo "New header missing AWS ENA derived limitation fields"
    echo "new header: $new_header"
    exit 1
}

echo "✅ AWS ENA provider collector matches the AWS-verified ENA counter fixture"
