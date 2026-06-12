#!/bin/bash
# config/cloud_provider.sh
# Detect cloud provider, NIC driver, and provider variant.
# Sourcing this file exports:
#   CLOUD_PROVIDER         - gcp | aws | other
#   NIC_DRIVER             - gvnic | virtio | ena | none
#   CLOUD_PROVIDER_VARIANT - ${CLOUD_PROVIDER}_${NIC_DRIVER}
#   NETWORK_INTERFACE      - primary network interface name

# === detect_platform: metadata-based provider detection ===
# Validate response bodies instead of curl exit codes so proxy or sandbox HTML
# responses are not misclassified as cloud metadata.
detect_platform() {
    local body

    # --- 1. GCP metadata (3s timeout) ---
    # GCP instance IDs are numeric. Metadata-Flavor is required by the GCP
    # metadata contract.
    body=$(curl -s -m 3 -H 'Metadata-Flavor: Google' \
        http://metadata.google.internal/computeMetadata/v1/instance/id 2>/dev/null)
    if [[ "$body" =~ ^[0-9]+$ ]]; then
        echo "gcp"; return
    fi

    # --- 2. AWS IMDSv2 (3s timeout) ---
    # EC2 instance IDs use the i-... shape and require an IMDSv2 token here.
    local token
    token=$(curl -s -m 3 -X PUT 'http://169.254.169.254/latest/api/token' \
        -H 'X-aws-ec2-metadata-token-ttl-seconds: 60' 2>/dev/null)
    if [[ -n "$token" ]]; then
        body=$(curl -s -m 3 -H "X-aws-ec2-metadata-token: $token" \
            http://169.254.169.254/latest/meta-data/instance-id 2>/dev/null)
        if [[ "$body" =~ ^i-[0-9a-f]+$ ]]; then
            echo "aws"; return
        fi
    fi

    echo "other"
}

# === detect_network_interface: default-route interface ===
detect_network_interface() {
    local iface
    if command -v ip >/dev/null 2>&1; then
        iface=$(ip route 2>/dev/null | awk '/^default/ {print $5; exit}')
    elif command -v route >/dev/null 2>&1; then
        iface=$(route get default 2>/dev/null | awk '/interface:/ {print $2; exit}')
    else
        iface=""
    fi
    [[ -n "$iface" ]] && echo "$iface" || echo ""
}

# === detect_nic_driver: driver detection via ethtool -i ===
detect_nic_driver() {
    local iface="${1:-$(detect_network_interface)}"
    [[ -z "$iface" ]] && { echo "none"; return; }
    command -v ethtool >/dev/null 2>&1 || { echo "none"; return; }

    local driver
    driver=$(ethtool -i "$iface" 2>/dev/null | awk '/^driver:/ {print $2}')
    case "$driver" in
        ena|efa) echo "ena" ;;
        gve) echo "gvnic" ;;
        virtio_net) echo "virtio" ;;
        *) echo "none" ;;
    esac
}

# === detect_cloud_provider: main entrypoint ===
detect_cloud_provider() {
    export NETWORK_INTERFACE="${NETWORK_INTERFACE:-$(detect_network_interface)}"
    export CLOUD_PROVIDER="${CLOUD_PROVIDER:-$(detect_platform)}"
    export NIC_DRIVER="${NIC_DRIVER:-$(detect_nic_driver "$NETWORK_INTERFACE")}"
    export CLOUD_PROVIDER_VARIANT="${CLOUD_PROVIDER}_${NIC_DRIVER}"

    # Known supported variants. Unexpected combinations fall back to other_none.
    case "$CLOUD_PROVIDER_VARIANT" in
        aws_ena|gcp_gvnic|gcp_virtio|other_none)
            :
            ;;
        gcp_none|aws_none|other_ena|other_gvnic|other_virtio)
            echo "WARN: unusual variant '$CLOUD_PROVIDER_VARIANT', falling back to other_none" >&2
            export CLOUD_PROVIDER_VARIANT="other_none"
            ;;
        *)
            echo "WARN: unknown variant '$CLOUD_PROVIDER_VARIANT', falling back to other_none" >&2
            export CLOUD_PROVIDER_VARIANT="other_none"
            ;;
    esac

    # Load provider-specific getter implementation
    _load_provider_getters
}

# === _load_provider_getters: load provider-specific getter implementation ===
_load_provider_getters() {
    local _prov_dir
    _prov_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/providers" 2>/dev/null && pwd)"
    local _prov_file
    case "${CLOUD_PROVIDER:-other}" in
        aws)   _prov_file="${_prov_dir}/aws_provider.sh" ;;
        gcp)   _prov_file="${_prov_dir}/gcp_provider.sh" ;;
        *)     _prov_file="${_prov_dir}/other_provider.sh" ;;
    esac
    if [[ -f "$_prov_file" ]]; then
        # shellcheck source=/dev/null
        source "$_prov_file"
        export -f get_provider_name get_platform_display_name \
            get_metadata_endpoint get_metadata_header get_metadata_api_path \
            get_iops_conversion_func get_baseline_io_kib get_baseline_throughput_kib \
            get_default_disk_type get_disk_type_options \
            get_nic_driver get_nic_allowance_fields get_nic_monitor_process_name \
            get_disk_field_prefix get_archive_dir_prefix get_bottleneck_label \
            get_doc_url 2>/dev/null || true
    else
        echo "WARN: provider file not found: $_prov_file (getters unavailable)" >&2
    fi
}

# === Auto-run when sourced ===
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
    detect_cloud_provider
fi
