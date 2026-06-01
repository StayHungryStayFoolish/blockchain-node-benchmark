#!/bin/bash
# Other Provider 契约实现 — Provider 抽象层 (CP-1)
#
# 依据: skill ref aws-gcp-sizing-rules-and-variant-taxonomy.md §7 (Other 返值列)
#
# 由 config/cloud_provider.sh 在 CLOUD_PROVIDER=other 时 source。
# 兜底实现 — Mac / IDC / 无 metadata API 环境。不假设任何云特性。
# IOPS 走 passthrough(无云端拆分语义);磁盘类型留空(本地盘由 lsblk 决定)。

# --- 平台元信息 ---
get_provider_name()         { echo "other"; }
get_platform_display_name() { echo "Other"; }

# --- metadata 子组 (无 metadata API) ---
get_metadata_endpoint()     { echo ""; }
get_metadata_header()       { echo ""; }
get_metadata_api_path()     { echo ""; }

# --- IOPS 计量 子组 ---
# 无云端拆分语义 — passthrough(直接用 iostat 原始 r/s+w/s)
get_iops_conversion_func()  { echo "passthrough"; }
get_baseline_io_kib()         { echo "0"; }   # 0 = 未知,禁止默认 16(AWS)/4(GCP) — 调用方判 0 处理
get_baseline_throughput_kib() { echo "0"; }   # 0 = 未知,禁止默认 128/256

# --- disk type 子组 (本地盘,无云盘类型) ---
get_default_disk_type()     { echo ""; }
get_disk_type_options()     { echo ""; }

# --- NIC 子组 (无饱和信号) ---
get_nic_driver()            { echo "none"; }
get_nic_allowance_fields()  { echo ""; }
get_nic_monitor_process_name() { echo "none"; }

# --- 命名 / 输出 子组 ---
get_disk_field_prefix()     { echo "normalized"; }   # 三云统一中立前缀; 折算值列 data_normalized_iops (与 registry 对称, fallback 用)
get_archive_dir_prefix()    { echo "run_"; }
get_bottleneck_label()      { echo "Disk"; }

# --- 文档 URL ---
get_doc_url() {
    local category="${1:-}"
    case "$category" in
        *) echo "" ;;
    esac
}
