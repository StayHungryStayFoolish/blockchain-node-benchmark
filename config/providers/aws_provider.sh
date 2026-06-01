#!/bin/bash
# AWS Provider 契约实现 — Provider 抽象层 (CP-1)
#
# 依据: analysis-notes/aws-gcp-io-counting-rules-verified.md (AWS EBS SSD ceil(256)/HDD ceil(1024) 官方实证)
#       skill ref aws-gcp-sizing-rules-and-variant-taxonomy.md §1 (IOPS 公式) / §7 (15 getter 表)
#
# 由 config/cloud_provider.sh 在 CLOUD_PROVIDER=aws 时 source。
# AWS 与 GCP 是双云对等一等公民 — 各有各的正确计量,不是迁移残留。

# --- 平台元信息 ---
get_provider_name()         { echo "aws"; }
get_platform_display_name() { echo "AWS"; }

# --- metadata 子组 (IMDSv1 路径) ---
get_metadata_endpoint()     { echo "http://169.254.169.254"; }
get_metadata_header()       { echo ""; }   # AWS IMDSv1 无需 header
get_metadata_api_path()     { echo "latest/meta-data"; }

# --- IOPS 计量 子组 (核心分歧点) ---
# AWS EBS SSD 按 256 KiB 拆分,HDD 按 1024 KiB 拆分 (官方文档实证)
# convert func 名,实际拆分由 utils/disk_converter.sh 按此值分流
get_iops_conversion_func()  { echo "aws_ssd_ceil_256"; }
get_baseline_io_kib()         { echo "16"; }
get_baseline_throughput_kib() { echo "128"; }

# --- disk type 子组 ---
get_default_disk_type()     { echo "gp3"; }
get_disk_type_options()     { echo "gp3 io2 instance-store"; }

# --- NIC 子组 (ENA) ---
get_nic_driver()            { echo "ena"; }
# AWS ENA 6 个限速计数器 (限速触发计数)
get_nic_allowance_fields()  { echo "bw_in_allowance_exceeded bw_out_allowance_exceeded pps_allowance_exceeded conntrack_allowance_exceeded linklocal_allowance_exceeded conntrack_allowance_available"; }
get_nic_monitor_process_name() { echo "ena_network_monitor"; }

# --- 命名 / 输出 子组 ---
get_disk_field_prefix()     { echo "normalized"; }   # 三云统一中立前缀; 折算值列 data_normalized_iops (与 registry 对称, fallback 用)
get_archive_dir_prefix()    { echo "aws_run_"; }
get_bottleneck_label()      { echo "EBS"; }

# --- 文档 URL ---
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
