#!/bin/bash
# GCP Provider 契约实现 — Provider 抽象层 (CP-1)
#
# 依据: analysis-notes/CORRECTED_PLAN.md §1146-1175 (GCP 默认值)
#       skill ref aws-gcp-sizing-rules-and-variant-taxonomy.md §1.1 (8 种盘) / §7 (15 getter 表)
#       analysis-notes/aws-gcp-io-counting-rules-verified.md (GCP PD/Hyperdisk 不拆分 IOPS)
#
# 由 config/cloud_provider.sh 在 CLOUD_PROVIDER=gcp 时 source。
# 所有 getter 输出到 stdout,业务层通过 $(get_X) 消费,绝不硬编码 provider 值。

# --- 平台元信息 ---
get_provider_name()         { echo "gcp"; }
get_platform_display_name() { echo "GCP"; }

# --- metadata 子组 ---
get_metadata_endpoint()     { echo "http://metadata.google.internal"; }
get_metadata_header()       { echo "Metadata-Flavor: Google"; }   # GCP IMDS 必须带此 header(防 DNS rebinding)
get_metadata_api_path()     { echo "computeMetadata/v1"; }

# --- IOPS 计量 子组 (核心分歧点) ---
# GCP PD/Hyperdisk 不按 IO size 拆分 IOPS (官方文档实证) — passthrough
get_iops_conversion_func()  { echo "passthrough"; }
get_baseline_io_kib()         { echo "4"; }     # Hyperdisk 4 KiB block size
get_baseline_throughput_kib() { echo "256"; }   # Hyperdisk Extreme throughput baseline

# --- disk type 子组 ---
get_default_disk_type()     { echo "hyperdisk-extreme"; }   # 区块链 archive 节点首选(IOPS 关键)
# 8 种现役盘(ref §1.1 校正 — 含 pd-standard + 3 种 hyperdisk)
get_disk_type_options()     { echo "pd-standard pd-balanced pd-ssd pd-extreme hyperdisk-balanced hyperdisk-extreme hyperdisk-throughput local-ssd"; }

# --- NIC 子组 (gVNIC) ---
get_nic_driver()            { echo "gve"; }
get_nic_allowance_fields()  { echo ""; }   # GCP gVNIC 无 allowance 概念,严格返空
get_nic_monitor_process_name() { echo "gvnic_network_monitor"; }

# --- 命名 / 输出 子组 ---
get_disk_field_prefix()     { echo "normalized"; }   # 三云统一中立前缀; 折算值列 data_normalized_iops (与 registry 对称, fallback 用)
get_archive_dir_prefix()    { echo "gcp_run_"; }
get_bottleneck_label()      { echo "Disk"; }       # GCP 用通用语义

# --- 文档 URL ---
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
