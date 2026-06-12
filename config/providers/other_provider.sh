#!/bin/bash
# Fallback provider contract implementation.
#
# Fallback provider implementation for non-cloud or unknown environments
#
# Sourced by config/cloud_provider.sh when CLOUD_PROVIDER=other.
# Fallback for local, bare-metal, or unknown environments. It assumes no cloud
# metadata API and no cloud-specific IOPS split semantics.

# --- Platform metadata ---
get_provider_name()         { echo "other"; }
get_platform_display_name() { echo "Other"; }

# --- Metadata group (no metadata API) ---
get_metadata_endpoint()     { echo ""; }
get_metadata_header()       { echo ""; }
get_metadata_api_path()     { echo ""; }

# --- IOPS accounting group ---
# No cloud-side split semantics: use raw iostat r/s+w/s passthrough.
get_iops_conversion_func()  { echo "passthrough"; }
get_baseline_io_kib()         { echo "0"; }   # 0 means unknown; callers must handle it explicitly.
get_baseline_throughput_kib() { echo "0"; }   # 0 means unknown; callers must handle it explicitly.

# --- Disk type group (local disk, no cloud disk type) ---
get_default_disk_type()     { echo ""; }
get_disk_type_options()     { echo ""; }

# --- NIC group (no saturation signal) ---
get_nic_driver()            { echo "none"; }
get_nic_allowance_fields()  { echo ""; }
get_nic_monitor_process_name() { echo "none"; }

# --- Naming / output group ---
get_disk_field_prefix()     { echo "normalized"; }   # Shared provider-normalized disk field prefix.
get_archive_dir_prefix()    { echo "run_"; }
get_bottleneck_label()      { echo "Disk"; }

# --- Documentation URLs ---
get_doc_url() {
    local category="${1:-}"
    case "$category" in
        *) echo "" ;;
    esac
}
