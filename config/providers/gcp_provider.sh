#!/bin/bash
# GCP provider contract implementation.
#
# Sourced by config/cloud_provider.sh when CLOUD_PROVIDER=gcp.
# All getters print to stdout; callers consume them via $(get_X) instead of
# hardcoding provider-specific values.

# --- Platform metadata ---
get_provider_name()         { echo "gcp"; }
get_platform_display_name() { echo "GCP"; }

# --- Metadata group ---
get_metadata_endpoint()     { echo "http://metadata.google.internal"; }
get_metadata_header()       { echo "Metadata-Flavor: Google"; }   # Required by GCP IMDS to prevent DNS rebinding.
get_metadata_api_path()     { echo "computeMetadata/v1"; }

# --- IOPS accounting group ---
# GCP PD/Hyperdisk does not split IOPS by I/O size; use passthrough.
get_iops_conversion_func()  { echo "passthrough"; }
get_baseline_io_kib()         { echo "4"; }     # Hyperdisk 4 KiB block size
get_baseline_throughput_kib() { echo "256"; }   # Hyperdisk Extreme throughput baseline

# --- Disk type group ---
get_default_disk_type()     { echo "hyperdisk-extreme"; }   # Preferred for archive nodes where IOPS matters.
# Current GCP disk types, including pd-standard and Hyperdisk variants.
get_disk_type_options()     { echo "pd-standard pd-balanced pd-ssd pd-extreme hyperdisk-balanced hyperdisk-extreme hyperdisk-throughput local-ssd"; }

# --- NIC group (gVNIC) ---
get_nic_driver()            { echo "gve"; }
get_nic_allowance_fields()  { echo ""; }   # GCP gVNIC has no allowance counters.
get_nic_monitor_process_name() { echo "network_monitor"; }

# --- Naming / output group ---
get_disk_field_prefix()     { echo "normalized"; }   # Shared provider-normalized disk field prefix.
get_archive_dir_prefix()    { echo "gcp_run_"; }
get_bottleneck_label()      { echo "Disk"; }

# --- Documentation URLs ---
get_doc_url() {
    local category="${1:-}"
    case "$category" in
        disk) echo "https://cloud.google.com/compute/docs/disks/hyperdisks" ;;
        nic)  echo "https://cloud.google.com/compute/docs/networking/using-gvnic" ;;
        imds) echo "https://cloud.google.com/compute/docs/metadata/overview" ;;
        io2)  echo "https://cloud.google.com/compute/docs/disks/hyperdisks#hd-extreme" ;;
        *)    echo "https://cloud.google.com/compute/docs/" ;;
    esac
}
