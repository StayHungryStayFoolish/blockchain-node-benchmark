#!/usr/bin/env bash
# config/csv_schema_registry.sh
# CSV Schema Registry (bash 侧) — 全 CSV 字段定义 SSOT, writer 用.
#
# 设计依据: analysis-notes/CSV-SCHEMA-ABSTRACTION-proposal.md §3
# 与 utils/csv_schema_registry.py 严格 1:1 对称 (test_csv_registry_symmetry.sh 守护).
# 仿 network 范本 (monitoring/network/interface.sh + utils/network_field_registry.py 对称模式).
#
# 核心职责:
#   csv_registry_disk_logical_names      -> 列出 disk 段所有逻辑名 (顺序 = CSV 列顺序)
#   csv_registry_resolve <logical> <provider> <device_prefix> -> 物理列名
#   csv_registry_disk_header <device_prefix> <provider>       -> 整个 disk 段 header (writer 用)
#
# provider_aware 字段 (物理名随云变) 通过 disk_field_prefix 分流:
#   aws/gcp/other 三云统一 -> normalized (中立命名, 物理名只表达逻辑指标)
#   provider 信息由 CSV cloud_provider 列承载, 不污染指标名 => 架构中立、无厂商烙印
#   (与 config/providers/{aws,gcp,other}_provider.sh get_disk_field_prefix 对称)
#
# 接入范围: basic 段 (10 字段, 静态) + disk 段 (21 字段). 其余段后续波次扩展.

# ── 段顺序 (= CSV 列序 SSOT, 实证来源 monitoring/unified_monitor.sh:1940/1942 generate_csv_header) ──
# 与 utils/csv_schema_registry.py SEGMENT_ORDER 严格对称.
# 动态段 (device/ena/cgroup) 长度运行时可变, 不用静态逻辑名枚举; 由各自生成函数产出.
_CSV_REGISTRY_SEGMENT_ORDER="basic device network ena overhead block qps cgroup meta"
# 动态段集合 (与 python DYNAMIC_SEGMENTS 对称: device/ena; 注: cgroup 走 collector, 不在静态 registry)
_CSV_REGISTRY_DYNAMIC_SEGMENTS="device ena"

# ── basic 段 10 字段逻辑名 (顺序 = monitoring/unified_monitor.sh:1927 basic_header) ──
# 全部物理名固定 (= 逻辑名), 无 provider 分流. 与 utils/csv_schema_registry.py _BASIC_FIELDS 顺序严格一致.
_CSV_REGISTRY_BASIC_LOGICAL=(
    timestamp
    cpu_usage
    cpu_usr
    cpu_sys
    cpu_iowait
    cpu_soft
    cpu_idle
    mem_used
    mem_total
    mem_usage
)

# ── disk 段 21 字段逻辑名 (顺序 = monitoring/iostat_collector.sh:144 header 顺序) ──
# 与 utils/csv_schema_registry.py _DISK_FIELDS 顺序严格一致.
_CSV_REGISTRY_DISK_LOGICAL=(
    disk_r_s
    disk_w_s
    disk_rkb_s
    disk_wkb_s
    disk_r_await
    disk_w_await
    disk_avg_await
    disk_aqu_sz
    disk_util
    disk_rrqm_s
    disk_wrqm_s
    disk_rrqm_pct
    disk_wrqm_pct
    disk_rareq_sz
    disk_wareq_sz
    disk_total_iops
    disk_iops_provider_adjusted
    disk_read_throughput_mibs
    disk_write_throughput_mibs
    disk_total_throughput_mibs
    disk_throughput_provider_adjusted
)

# provider_aware 逻辑名集合 (物理名随云变的 2 个字段)
_CSV_REGISTRY_PROVIDER_AWARE="disk_iops_provider_adjusted disk_throughput_provider_adjusted"

# 列出 disk 段所有逻辑名 (空格分隔, 顺序 = CSV 列序)
csv_registry_disk_logical_names() {
    echo "${_CSV_REGISTRY_DISK_LOGICAL[*]}"
}

# 列出 basic 段所有逻辑名 (空格分隔, 顺序 = CSV 列序)
csv_registry_basic_logical_names() {
    echo "${_CSV_REGISTRY_BASIC_LOGICAL[*]}"
}

# 列出全部静态段逻辑名 (basic + disk, 顺序 = 段顺序内各段录入序)
# 与 utils/csv_schema_registry.py CSVSchemaRegistry.all_logical_names() 对称.
csv_registry_all_logical_names() {
    echo "${_CSV_REGISTRY_BASIC_LOGICAL[*]} ${_CSV_REGISTRY_DISK_LOGICAL[*]}"
}

# 列出某静态段逻辑名 (与 python segment_logical_names 对称).
# 动态段 (device/ena) 无静态枚举 -> 返回空; 调用方应改用 writer 生成函数.
# 未录入的静态段 (network/overhead/block/qps/meta, 后续波次) 同样返回空.
csv_registry_segment_logical_names() {
    case "$1" in
        basic) echo "${_CSV_REGISTRY_BASIC_LOGICAL[*]}" ;;
        device) echo "${_CSV_REGISTRY_DISK_LOGICAL[*]}" ;;
        *) echo "" ;;
    esac
}

# 列出 provider_aware 逻辑名 (与 python CSVSchemaRegistry.provider_aware_fields 对称)
csv_registry_provider_aware_names() {
    echo "$_CSV_REGISTRY_PROVIDER_AWARE"
}

# disk_field_prefix — 方案甲(中立命名): 三云统一 "normalized" (ADR-0002).
# 物理名只表达逻辑指标, provider 由 CSV cloud_provider 列承载 => 架构中立、无厂商烙印.
# provider 参数仍保留(签名不变)作将来挂点; 当前三云同名.
# 与 utils/csv_schema_registry.py DISK_FIELD_PREFIX 严格对称.
_csv_registry_disk_field_prefix() {
    case "$1" in
        aws)   echo "normalized" ;;
        gcp)   echo "normalized" ;;
        *)     echo "normalized" ;;
    esac
}

# 逻辑名 -> 物理列名
# 用法: csv_registry_resolve <logical_name> <provider> <device_prefix>
#   device_prefix: 'data' / 'accounts' / 'data_nvme1n1' 等 (writer 拼好的前缀)
# 未知逻辑名 -> 返回非 0 + stderr 报错 (硬失败, 不静默)
csv_registry_resolve() {
    local logical="$1" provider="$2" prefix="$3"
    local dfp
    dfp="$(_csv_registry_disk_field_prefix "$provider")"
    case "$logical" in
        # ── basic 段 10 字段 (物理名 = 逻辑名, 无 provider/prefix 变化) ──
        timestamp)                         echo "timestamp" ;;
        cpu_usage)                         echo "cpu_usage" ;;
        cpu_usr)                           echo "cpu_usr" ;;
        cpu_sys)                           echo "cpu_sys" ;;
        cpu_iowait)                        echo "cpu_iowait" ;;
        cpu_soft)                          echo "cpu_soft" ;;
        cpu_idle)                          echo "cpu_idle" ;;
        mem_used)                          echo "mem_used" ;;
        mem_total)                         echo "mem_total" ;;
        mem_usage)                         echo "mem_usage" ;;
        # ── disk 段 21 字段 ──
        disk_r_s)                          echo "${prefix}_r_s" ;;
        disk_w_s)                          echo "${prefix}_w_s" ;;
        disk_rkb_s)                        echo "${prefix}_rkb_s" ;;
        disk_wkb_s)                        echo "${prefix}_wkb_s" ;;
        disk_r_await)                      echo "${prefix}_r_await" ;;
        disk_w_await)                      echo "${prefix}_w_await" ;;
        disk_avg_await)                    echo "${prefix}_avg_await" ;;
        disk_aqu_sz)                       echo "${prefix}_aqu_sz" ;;
        disk_util)                         echo "${prefix}_util" ;;
        disk_rrqm_s)                       echo "${prefix}_rrqm_s" ;;
        disk_wrqm_s)                       echo "${prefix}_wrqm_s" ;;
        disk_rrqm_pct)                     echo "${prefix}_rrqm_pct" ;;
        disk_wrqm_pct)                     echo "${prefix}_wrqm_pct" ;;
        disk_rareq_sz)                     echo "${prefix}_rareq_sz" ;;
        disk_wareq_sz)                     echo "${prefix}_wareq_sz" ;;
        disk_total_iops)                   echo "${prefix}_total_iops" ;;
        disk_iops_provider_adjusted)       echo "${prefix}_${dfp}_iops" ;;
        disk_read_throughput_mibs)         echo "${prefix}_read_throughput_mibs" ;;
        disk_write_throughput_mibs)        echo "${prefix}_write_throughput_mibs" ;;
        disk_total_throughput_mibs)        echo "${prefix}_total_throughput_mibs" ;;
        disk_throughput_provider_adjusted) echo "${prefix}_${dfp}_throughput_mibs" ;;
        *)
            echo "csv_registry_resolve: unknown logical field: $logical" >&2
            return 1
            ;;
    esac
}

# 生成整个 disk 段 header (writer 用, 替代 iostat_collector.sh:144 字符串拼接)
# 用法: csv_registry_disk_header <device_prefix> <provider>
csv_registry_disk_header() {
    local prefix="$1" provider="$2"
    local out="" logical phys
    for logical in "${_CSV_REGISTRY_DISK_LOGICAL[@]}"; do
        phys="$(csv_registry_resolve "$logical" "$provider" "$prefix")" || return 1
        if [[ -z "$out" ]]; then
            out="$phys"
        else
            out="${out},${phys}"
        fi
    done
    echo "$out"
}

# 生成 basic 段 header (writer 用; 物理名固定, provider 忽略)
csv_registry_basic_header() {
    local out="" logical phys
    for logical in "${_CSV_REGISTRY_BASIC_LOGICAL[@]}"; do
        phys="$(csv_registry_resolve "$logical" "other" "")" || return 1
        if [[ -z "$out" ]]; then
            out="$phys"
        else
            out="${out},${phys}"
        fi
    done
    echo "$out"
}

# 生成某静态段 header (与 python segment_header 对称).
# 用法: csv_registry_segment_header <segment> [provider] [device_prefix]
#   provider/device_prefix 仅对 provider_aware 字段有意义 (basic 等静态段忽略).
#   动态/未录入段返回空串.
csv_registry_segment_header() {
    local segment="$1" provider="${2:-other}" prefix="${3:-}"
    local names out="" logical phys
    names="$(csv_registry_segment_logical_names "$segment")"
    [[ -z "$names" ]] && { echo ""; return 0; }
    for logical in $names; do
        phys="$(csv_registry_resolve "$logical" "$provider" "$prefix")" || return 1
        if [[ -z "$out" ]]; then
            out="$phys"
        else
            out="${out},${phys}"
        fi
    done
    echo "$out"
}
