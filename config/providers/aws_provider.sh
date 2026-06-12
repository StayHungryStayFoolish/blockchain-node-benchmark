#!/bin/bash
# AWS provider contract implementation.
#
# Sourced by config/cloud_provider.sh when CLOUD_PROVIDER=aws.

# --- Platform metadata ---
get_provider_name()         { echo "aws"; }
get_platform_display_name() { echo "AWS"; }

# --- Instance metadata ---
# AWS metadata access is IMDSv2-only. Callers must first request a token from
# /latest/api/token, then pass it with the X-aws-ec2-metadata-token header.
get_metadata_endpoint()     { echo "http://169.254.169.254"; }
get_metadata_header()       { echo "X-aws-ec2-metadata-token"; }
get_metadata_api_path()     { echo "latest/meta-data"; }

# --- IOPS accounting ---
# AWS EBS SSD uses 256 KiB accounting chunks; HDD uses 1024 KiB.
# utils/disk_converter.sh dispatches by this conversion function name.
get_iops_conversion_func()  { echo "aws_ssd_ceil_256"; }
get_baseline_io_kib()         { echo "16"; }
get_baseline_throughput_kib() { echo "128"; }

# --- Disk type ---
get_default_disk_type()     { echo "gp3"; }
get_disk_type_options()     { echo "gp3 io2 instance-store"; }

# --- NIC (ENA) ---
get_nic_driver()            { echo "ena"; }
get_nic_allowance_fields()  { echo "bw_in_allowance_exceeded bw_out_allowance_exceeded pps_allowance_exceeded conntrack_allowance_exceeded linklocal_allowance_exceeded conntrack_allowance_available"; }
get_nic_monitor_process_name() { echo "network_monitor"; }

# --- Naming / output ---
get_disk_field_prefix()     { echo "normalized"; }
get_archive_dir_prefix()    { echo "aws_run_"; }
get_bottleneck_label()      { echo "EBS"; }

# --- Documentation URL ---
get_doc_url() {
    local category="${1:-}"
    case "$category" in
        disk) echo "https://docs.aws.amazon.com/ebs/latest/userguide/ebs-volume-types.html" ;;
        nic)  echo "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ena-express.html" ;;
        imds) echo "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instancedata-data-retrieval.html" ;;
        io2)  echo "https://docs.aws.amazon.com/ebs/latest/userguide/provisioned-iops.html" ;;
        *)    echo "https://docs.aws.amazon.com/ebs/latest/userguide/" ;;
    esac
}
