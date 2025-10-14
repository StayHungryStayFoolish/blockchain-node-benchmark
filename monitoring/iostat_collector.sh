#!/bin/bash
# =====================================================================
# iostat 数据收集器
# =====================================================================
# 统一的 iostat 数据收集和处理逻辑
# 消除经验值，基于实时数据精准计算
# =====================================================================

# 安全加载配置文件，避免readonly变量冲突
if ! source "$(dirname "${BASH_SOURCE[0]}")/../config/config_loader.sh" 2>/dev/null; then
    echo "警告: 配置文件加载失败，使用默认配置"
    LOGS_DIR=${LOGS_DIR:-"/tmp/blockchain-node-benchmark/logs"}
fi
source "$(dirname "${BASH_SOURCE[0]}")/../utils/ebs_converter.sh"

# 加载日志函数
source "$(dirname "${BASH_SOURCE[0]}")/../utils/unified_logger.sh" 2>/dev/null || {
    # 如果日志函数不可用，提供简单的替代
    log_warn() { echo "⚠️ $*" >&2; }
    log_debug() { echo "🔍 $*" >&2; }
}

# 获取完整的 iostat 数据
get_iostat_data() {
    local device="$1"
    local logical_name="$2"  # data 或 accounts
    
    if [[ -z "$device" || -z "$logical_name" ]]; then
        echo "0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0"
        return
    fi
    
    # 实现真正的iostat持续采样
    local monitor_rate=${EBS_MONITOR_RATE:-1}
    local iostat_pid_file="/tmp/iostat_${device}_${logical_name}.pid"
    local iostat_data_file="/tmp/iostat_${device}_${logical_name}.data"
    
    # 检查是否已有持续采样进程
    if [[ ! -f "$iostat_pid_file" ]] || ! kill -0 "$(cat "$iostat_pid_file" 2>/dev/null)" 2>/dev/null; then
        # 启动持续采样进程
        if [[ "$(uname -s)" == "Linux" ]]; then
            iostat -dx "$monitor_rate" > "$iostat_data_file" &
            local iostat_pid=$!
            echo "$iostat_pid" > "$iostat_pid_file"
            log_debug "启动iostat持续采样: $device, PID: $iostat_pid, 频率: ${monitor_rate}秒, 数据文件: $iostat_data_file"
        else
            log_warn "iostat功能仅在Linux环境下可用，当前系统: $(uname -s)"
            return 1
        fi
    fi
    
    # 获取最新的设备数据行
    local device_stats=$(tail -n 20 "$iostat_data_file" 2>/dev/null | awk "/^${device}[[:space:]]/ {latest=\$0} END {print latest}")
    
    if [[ -z "$device_stats" ]]; then
        echo "0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0"
        return
    fi
    
    local fields=($device_stats)
    
    # 提取 iostat 字段 (消除硬编码索引)
    local r_s=${fields[1]:-0}
    local rkb_s=${fields[2]:-0}
    local rrqm_s=${fields[3]:-0}
    local rrqm_pct=${fields[4]:-0}
    local r_await=${fields[5]:-0}
    local rareq_sz=${fields[6]:-0}
    local w_s=${fields[7]:-0}
    local wkb_s=${fields[8]:-0}
    local wrqm_s=${fields[9]:-0}
    local wrqm_pct=${fields[10]:-0}
    local w_await=${fields[11]:-0}
    local wareq_sz=${fields[12]:-0}
    local aqu_sz=${fields[21]:-0}
    local util=${fields[22]:-0}
    
    # 计算衍生指标 (基于实时数据，无经验值)
    local total_iops=$(awk "BEGIN {printf \"%.2f\", $r_s + $w_s}" 2>/dev/null || echo "0")
    local total_throughput_kbs=$(awk "BEGIN {printf \"%.2f\", $rkb_s + $wkb_s}" 2>/dev/null || echo "0")
    local total_throughput_mibs=$(awk "BEGIN {printf \"%.2f\", $total_throughput_kbs / 1024}" 2>/dev/null || echo "0")
    
    # 计算读写吞吐量分离 (KB/s → MiB/s)
    local read_throughput_mibs=$(awk "BEGIN {printf \"%.2f\", $rkb_s / 1024}" 2>/dev/null || echo "0")
    local write_throughput_mibs=$(awk "BEGIN {printf \"%.2f\", $wkb_s / 1024}" 2>/dev/null || echo "0")
    
    # 计算AWS标准throughput
    local aws_standard_throughput_mibs="0"
    if command -v convert_to_aws_standard_throughput >/dev/null 2>&1; then
        # 计算加权平均IO大小
        local weighted_avg_io_kib
        if [[ $(awk "BEGIN {print ($total_iops > 0) ? 1 : 0}") -eq 1 ]]; then
            weighted_avg_io_kib=$(awk "BEGIN {printf \"%.2f\", $total_throughput_kbs / $total_iops}" 2>/dev/null || echo "0")
        else
            weighted_avg_io_kib="0"
        fi
        
        if [[ "$weighted_avg_io_kib" != "0" ]]; then
            aws_standard_throughput_mibs=$(convert_to_aws_standard_throughput "$total_throughput_mibs" "$weighted_avg_io_kib")
        else
            aws_standard_throughput_mibs="$total_throughput_mibs"  # 如果无法计算平均IO大小，使用原始值
        fi
    else
        log_debug "convert_to_aws_standard_throughput函数不可用，使用原始throughput值"
        aws_standard_throughput_mibs="$total_throughput_mibs"
    fi
    
    local avg_await=$(awk "BEGIN {printf \"%.2f\", ($r_await + $w_await) / 2}" 2>/dev/null || echo "0")
    
    # 计算平均 I/O 大小 (基于实时数据)
    local avg_io_kib
    if [[ $(awk "BEGIN {print ($total_iops > 0) ? 1 : 0}") -eq 1 ]]; then
        avg_io_kib=$(awk "BEGIN {printf \"%.2f\", $total_throughput_kbs / $total_iops}" 2>/dev/null || echo "0")
    else
        avg_io_kib="0"
    fi
    
    # 计算 AWS 标准 IOPS (基于实时数据)
    local aws_standard_iops
    if [[ $(awk "BEGIN {print ($avg_io_kib > 0) ? 1 : 0}") -eq 1 ]]; then
        aws_standard_iops=$(convert_to_aws_standard_iops "$total_iops" "$avg_io_kib")
    else
        aws_standard_iops="$total_iops"
    fi
    
    # 返回完整数据 (21个字段)
    echo "$r_s,$w_s,$rkb_s,$wkb_s,$r_await,$w_await,$avg_await,$aqu_sz,$util,$rrqm_s,$wrqm_s,$rrqm_pct,$wrqm_pct,$rareq_sz,$wareq_sz,$total_iops,$aws_standard_iops,$read_throughput_mibs,$write_throughput_mibs,$total_throughput_mibs,$aws_standard_throughput_mibs"
}

# 生成设备的 CSV 表头
generate_device_header() {
    local device="$1"
    local logical_name="$2"
    
    # 使用统一的命名规则 {逻辑名}_{设备名}_{指标}
    # DATA设备使用data前缀，ACCOUNTS设备使用accounts前缀
    local prefix
    case "$logical_name" in
        "data") prefix="data_${device}" ;;
        "accounts") prefix="accounts_${device}" ;;
        *) prefix="${logical_name}_${device}" ;;
    esac
    
    echo "${prefix}_r_s,${prefix}_w_s,${prefix}_rkb_s,${prefix}_wkb_s,${prefix}_r_await,${prefix}_w_await,${prefix}_avg_await,${prefix}_aqu_sz,${prefix}_util,${prefix}_rrqm_s,${prefix}_wrqm_s,${prefix}_rrqm_pct,${prefix}_wrqm_pct,${prefix}_rareq_sz,${prefix}_wareq_sz,${prefix}_total_iops,${prefix}_aws_standard_iops,${prefix}_read_throughput_mibs,${prefix}_write_throughput_mibs,${prefix}_total_throughput_mibs,${prefix}_aws_standard_throughput_mibs"
}

# 获取所有配置设备的数据
get_all_devices_data() {
    local device_data=""
    
    # DATA 设备 - 使用data作为逻辑名前缀（必须存在）
    if [[ -n "$DATA_VOL_TYPE" ]]; then
        local data_stats=$(get_iostat_data "$LEDGER_DEVICE" "data")
        device_data="$data_stats"
    else
        log_error "DATA_VOL_TYPE not configured - this is required"
        return 1
    fi
    
    # ACCOUNTS 设备 - 使用accounts作为逻辑名前缀
    if is_accounts_configured; then
        local accounts_stats=$(get_iostat_data "$ACCOUNTS_DEVICE" "accounts")
        if [[ -n "$device_data" ]]; then
            device_data="${device_data},$accounts_stats"
        else
            device_data="$accounts_stats"
        fi
    fi
    
    echo "$device_data"
}

# 生成所有设备的 CSV 表头
generate_all_devices_header() {
    local device_header=""
    
    # DATA 设备表头 - 使用data作为逻辑名前缀（必须存在）
    if [[ -n "$DATA_VOL_TYPE" ]]; then
        device_header=$(generate_device_header "$LEDGER_DEVICE" "data")
    else
        log_error "DATA_VOL_TYPE not configured - this is required"
        return 1
    fi
    
    # ACCOUNTS 设备表头 - 使用accounts作为逻辑名前缀
    if is_accounts_configured; then
        local accounts_header=$(generate_device_header "$ACCOUNTS_DEVICE" "accounts")
        if [[ -n "$device_header" ]]; then
            device_header="${device_header},$accounts_header"
        else
            device_header="$accounts_header"
        fi
    fi
    
    echo "$device_header"
}

# 验证设备可用性
validate_devices() {
    local errors=()
    
    # DATA设备验证（必须存在）
    if [[ -z "$LEDGER_DEVICE" ]]; then
        errors+=("LEDGER_DEVICE is required but not configured")
    elif [[ ! -b "/dev/$LEDGER_DEVICE" ]]; then
        errors+=("LEDGER_DEVICE /dev/$LEDGER_DEVICE does not exist")
    fi
    
    if [[ -n "$ACCOUNTS_DEVICE" && ! -b "/dev/$ACCOUNTS_DEVICE" ]]; then
        errors+=("ACCOUNTS_DEVICE /dev/$ACCOUNTS_DEVICE does not exist")
    fi
    
    if [[ ${#errors[@]} -gt 0 ]]; then
        printf "❌ Device validation failed:\n"
        printf "  - %s\n" "${errors[@]}"
        return 1
    fi
    
    return 0
}

# 如果直接执行此脚本，进行测试
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "🔧 iostat 数据收集器测试"
    echo "========================="
    
    if validate_devices; then
        echo "✅ 设备验证通过"
        echo ""
        echo "📊 CSV 表头:"
        echo "timestamp,$(generate_all_devices_header)"
        echo ""
        echo "📊 当前数据:"
        echo "$(date +"$TIMESTAMP_FORMAT"),$(get_all_devices_data)"
    else
        echo "❌ 设备验证失败"
        exit 1
    fi
fi
