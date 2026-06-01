#!/bin/bash
# =====================================================================
# iostat Data Collector
# =====================================================================
# Unified iostat data collection and processing logic
# Eliminate empirical values, calculate precisely based on real-time data
# =====================================================================

# Safely load configuration file to avoid readonly variable conflicts
if ! source "$(dirname "${BASH_SOURCE[0]}")/../config/config_loader.sh" 2>/dev/null; then
    echo "Warning: Configuration file loading failed, using default configuration"
    LOGS_DIR=${LOGS_DIR:-"/tmp/blockchain-node-benchmark/logs"}
fi
source "$(dirname "${BASH_SOURCE[0]}")/../utils/disk_converter.sh"
# CSV Schema Registry (S1: disk 段 header 单一事实源, 替代手工字符串拼接)
source "$(dirname "${BASH_SOURCE[0]}")/../config/csv_schema_registry.sh"

# Load logging functions
source "$(dirname "${BASH_SOURCE[0]}")/../utils/unified_logger.sh" 2>/dev/null || {
    # Provide simple alternatives if logging functions are unavailable
    log_warn() { echo "⚠️ $*" >&2; }
    log_debug() { echo "🔍 $*" >&2; }
}

# Get complete iostat data
get_iostat_data() {
    local device="$1"
    local logical_name="$2"  # data or accounts
    
    if [[ -z "$device" || -z "$logical_name" ]]; then
        echo "0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0"
        return
    fi
    
    # Implement true iostat continuous sampling
    local monitor_rate=${DISK_MONITOR_RATE:-1}
    local iostat_pid_file="/tmp/iostat_${device}_${logical_name}.pid"
    local iostat_data_file="/tmp/iostat_${device}_${logical_name}.data"
    
    # Check if continuous sampling process already exists
    if [[ ! -f "$iostat_pid_file" ]] || ! kill -0 "$(cat "$iostat_pid_file" 2>/dev/null)" 2>/dev/null; then
        # Start continuous sampling process
        if [[ "$(uname -s)" == "Linux" ]]; then
            iostat -dx "$monitor_rate" > "$iostat_data_file" &
            local iostat_pid=$!
            echo "$iostat_pid" > "$iostat_pid_file"
            log_debug "Started iostat continuous sampling: $device, PID: $iostat_pid, Rate: ${monitor_rate}s, Data file: $iostat_data_file"
        else
            log_warn "iostat functionality only available in Linux environment, current system: $(uname -s)"
            return 1
        fi
    fi
    
    # Get latest device data line
    local device_stats=$(tail -n 20 "$iostat_data_file" 2>/dev/null | awk "/^${device}[[:space:]]/ {latest=\$0} END {print latest}")
    
    if [[ -z "$device_stats" ]]; then
        echo "0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0"
        return
    fi
    
    local fields=($device_stats)
    
    # Extract iostat fields (eliminate hardcoded indices)
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
    
    # Calculate derived metrics (based on real-time data, no empirical values)
    local total_iops=$(awk "BEGIN {printf \"%.2f\", $r_s + $w_s}" 2>/dev/null || echo "0")
    local total_throughput_kbs=$(awk "BEGIN {printf \"%.2f\", $rkb_s + $wkb_s}" 2>/dev/null || echo "0")
    local total_throughput_mibs=$(awk "BEGIN {printf \"%.2f\", $total_throughput_kbs / 1024}" 2>/dev/null || echo "0")
    
    # Calculate separate read/write throughput (KB/s → MiB/s)
    local read_throughput_mibs=$(awk "BEGIN {printf \"%.2f\", $rkb_s / 1024}" 2>/dev/null || echo "0")
    local write_throughput_mibs=$(awk "BEGIN {printf \"%.2f\", $wkb_s / 1024}" 2>/dev/null || echo "0")
    
    # Calculate provider-standard throughput
    local standard_throughput_mibs="0"
    if command -v convert_to_standard_throughput >/dev/null 2>&1; then
        # Calculate weighted average IO size
        local weighted_avg_io_kib
        if [[ $(awk "BEGIN {print ($total_iops > 0) ? 1 : 0}") -eq 1 ]]; then
            weighted_avg_io_kib=$(awk "BEGIN {printf \"%.2f\", $total_throughput_kbs / $total_iops}" 2>/dev/null || echo "0")
        else
            weighted_avg_io_kib="0"
        fi
        
        if [[ "$weighted_avg_io_kib" != "0" ]]; then
            standard_throughput_mibs=$(convert_to_standard_throughput "$total_throughput_mibs" "$weighted_avg_io_kib")
        else
            standard_throughput_mibs="$total_throughput_mibs"  # Use raw value if average IO size cannot be calculated
        fi
    else
        log_debug "convert_to_standard_throughput function unavailable, using raw throughput value"
        standard_throughput_mibs="$total_throughput_mibs"
    fi
    
    local avg_await=$(awk "BEGIN {printf \"%.2f\", ($r_await + $w_await) / 2}" 2>/dev/null || echo "0")
    
    # Calculate average I/O size (based on real-time data)
    local avg_io_kib
    if [[ $(awk "BEGIN {print ($total_iops > 0) ? 1 : 0}") -eq 1 ]]; then
        avg_io_kib=$(awk "BEGIN {printf \"%.2f\", $total_throughput_kbs / $total_iops}" 2>/dev/null || echo "0")
    else
        avg_io_kib="0"
    fi
    
    # Calculate provider-standard IOPS (based on real-time data)
    # B: IOPS 拆分规则按【磁盘类型】定 (不再 provider 一刀切). 按 logical_name 选对应卷型,
    #   经 disk_iops_io_cap_kib 求 io_cap: AWS SSD(gp3/io2)=256 / AWS HDD(st1/sc1)=1024 /
    #   GCP 盘型+instance-store+other=0(passthrough 不拆). 依据 aws-gcp-io-counting-rules-verified.md。
    local _vol_type
    case "$logical_name" in
        accounts) _vol_type="${ACCOUNTS_VOL_TYPE:-}" ;;
        *)        _vol_type="${DATA_VOL_TYPE:-}" ;;
    esac
    local _io_cap=256
    if declare -F disk_iops_io_cap_kib >/dev/null 2>&1; then
        _io_cap=$(disk_iops_io_cap_kib "$_vol_type")
    fi
    local standard_iops
    if [[ $(awk "BEGIN {print ($avg_io_kib > 0) ? 1 : 0}") -eq 1 ]]; then
        standard_iops=$(convert_to_standard_iops "$total_iops" "$avg_io_kib" "$_io_cap")
    else
        standard_iops="$total_iops"
    fi
    
    # Return complete data (21 fields)
    echo "$r_s,$w_s,$rkb_s,$wkb_s,$r_await,$w_await,$avg_await,$aqu_sz,$util,$rrqm_s,$wrqm_s,$rrqm_pct,$wrqm_pct,$rareq_sz,$wareq_sz,$total_iops,$standard_iops,$read_throughput_mibs,$write_throughput_mibs,$total_throughput_mibs,$standard_throughput_mibs"
}

# Generate CSV header for device
# 列名由 csv_schema_registry 单一事实源生成 (替代手工字符串拼接).
# 方案甲(中立命名): provider_aware 字段三云统一 normalized_iops/normalized_throughput_mibs (ADR-0002),
#   物理名不含云厂商烙印; provider 信息由 CSV cloud_provider 列承载 (与配置一致).
# 第 3 参 provider: 仅作 registry 接口透传 (当前三云同名, 留作将来某云特殊命名挂点).
#   不传则用 get_provider_name (配置驱动: CLOUD_PROVIDER 配置优先, 未配则探测).
generate_device_header() {
    local device="$1"
    local logical_name="$2"
    local provider="${3:-}"
    if [[ -z "$provider" ]]; then
        if declare -F get_provider_name >/dev/null 2>&1; then
            provider="$(get_provider_name 2>/dev/null)"
        fi
        provider="${provider:-other}"   # getter 不可用时中立兜底, 不偏向任何云
    fi

    # Use unified naming convention {logical_name}_{device_name}_{metric}
    # DATA device uses data prefix, ACCOUNTS device uses accounts prefix
    local prefix
    case "$logical_name" in
        "data") prefix="data_${device}" ;;
        "accounts") prefix="accounts_${device}" ;;
        *) prefix="${logical_name}_${device}" ;;
    esac

    # 从 registry 生成整段 21 列 header (单一事实源, reader 经 registry resolve 对齐)
    if declare -F csv_registry_disk_header >/dev/null 2>&1; then
        csv_registry_disk_header "$prefix" "$provider"
    else
        # 防御: registry 未 source 时回退. 用 get_disk_field_prefix 保持与 provider 一致,
        # 仍不硬编码 aws (无倾向兜底). 默认值与三云统一前缀 normalized 对齐.
        local dfp="normalized"
        declare -F get_disk_field_prefix >/dev/null 2>&1 && dfp="$(get_disk_field_prefix 2>/dev/null || echo normalized)"
        log_warn "csv_registry_disk_header unavailable — fallback header (dfp=$dfp)"
        echo "${prefix}_r_s,${prefix}_w_s,${prefix}_rkb_s,${prefix}_wkb_s,${prefix}_r_await,${prefix}_w_await,${prefix}_avg_await,${prefix}_aqu_sz,${prefix}_util,${prefix}_rrqm_s,${prefix}_wrqm_s,${prefix}_rrqm_pct,${prefix}_wrqm_pct,${prefix}_rareq_sz,${prefix}_wareq_sz,${prefix}_total_iops,${prefix}_${dfp}_iops,${prefix}_read_throughput_mibs,${prefix}_write_throughput_mibs,${prefix}_total_throughput_mibs,${prefix}_${dfp}_throughput_mibs"
    fi
}

# Get data for all configured devices
get_all_devices_data() {
    local device_data=""

    # Degraded mode: device(s) unavailable — emit NaN placeholders matching header shape
    if [[ "${DEVICE_VALIDATION_DEGRADED:-0}" == "1" ]]; then
        # 21 NaN fields per device (matches get_iostat_data output)
        local nan_row="NaN,NaN,NaN,NaN,NaN,NaN,NaN,NaN,NaN,NaN,NaN,NaN,NaN,NaN,NaN,NaN,NaN,NaN,NaN,NaN,NaN"
        device_data="$nan_row"
        if is_accounts_configured; then
            device_data="${device_data},$nan_row"
        fi
        echo "$device_data"
        return 0
    fi

    # DATA device - use data as logical name prefix (required)
    if [[ -n "$DATA_VOL_TYPE" ]]; then
        local data_stats=$(get_iostat_data "$LEDGER_DEVICE" "data")
        device_data="$data_stats"
    else
        log_error "DATA_VOL_TYPE not configured - this is required"
        return 1
    fi

    # ACCOUNTS device - use accounts as logical name prefix
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

# Generate CSV header for all devices
generate_all_devices_header() {
    local device_header=""

    # S1(方案甲): provider 随云变. writer 端 provider 唯一合法源 = get_provider_name (运行时探测);
    # reader 端则必须从 CSV cloud_provider 列取 (见 proposal §4.5 铁律). 二者不可混用.
    # 此处解析一次, 4 处 generate_device_header 同源传入, 保证 device 列名与 cloud_provider 列值自洽.
    local provider="aws"
    if declare -F get_provider_name >/dev/null 2>&1; then
        local _p; _p=$(get_provider_name 2>/dev/null)
        [[ -n "$_p" ]] && provider="$_p"
    fi

    # Degraded mode: use "NA" as device-name placeholder so header column count is stable
    if [[ "${DEVICE_VALIDATION_DEGRADED:-0}" == "1" ]]; then
        local data_dev="${LEDGER_DEVICE:-NA}"
        device_header=$(generate_device_header "$data_dev" "data" "$provider")
        if is_accounts_configured; then
            local acc_dev="${ACCOUNTS_DEVICE:-NA}"
            local accounts_header=$(generate_device_header "$acc_dev" "accounts" "$provider")
            device_header="${device_header},$accounts_header"
        fi
        echo "$device_header"
        return 0
    fi

    # DATA device header - use data as logical name prefix (required)
    if [[ -n "$DATA_VOL_TYPE" ]]; then
        device_header=$(generate_device_header "$LEDGER_DEVICE" "data" "$provider")
    else
        log_error "DATA_VOL_TYPE not configured - this is required"
        return 1
    fi

    # ACCOUNTS device header - use accounts as logical name prefix
    if is_accounts_configured; then
        local accounts_header=$(generate_device_header "$ACCOUNTS_DEVICE" "accounts" "$provider")
        if [[ -n "$device_header" ]]; then
            device_header="${device_header},$accounts_header"
        else
            device_header="$accounts_header"
        fi
    fi

    echo "$device_header"
}

# Validate device availability
# Supports STRICT_DEVICE_VALIDATION env var:
#   - true  : hard fail on missing devices (original behavior, for AWS EC2)
#   - false : degraded mode (default) — WARN, set DEVICE_VALIDATION_DEGRADED=1, return 0
validate_devices() {
    local errors=()
    local strict="${STRICT_DEVICE_VALIDATION:-false}"

    # DATA device validation (required)
    if [[ -z "$LEDGER_DEVICE" ]]; then
        errors+=("LEDGER_DEVICE is required but not configured")
    elif [[ ! -b "/dev/$LEDGER_DEVICE" ]]; then
        errors+=("LEDGER_DEVICE /dev/$LEDGER_DEVICE does not exist")
    fi

    if [[ -n "$ACCOUNTS_DEVICE" && ! -b "/dev/$ACCOUNTS_DEVICE" ]]; then
        errors+=("ACCOUNTS_DEVICE /dev/$ACCOUNTS_DEVICE does not exist")
    fi

    if [[ ${#errors[@]} -gt 0 ]]; then
        if [[ "$strict" == "true" ]]; then
            printf "❌ Device validation failed:\n"
            printf "  - %s\n" "${errors[@]}"
            return 1
        else
            printf "⚠️  Device validation WARN (degraded mode, STRICT_DEVICE_VALIDATION=false):\n" >&2
            printf "  - %s\n" "${errors[@]}" >&2
            printf "⚠️  Disk I/O columns will be filled with N/A; CPU/mem/net monitoring still active.\n" >&2
            printf "💡 Set STRICT_DEVICE_VALIDATION=true to enforce hard failure (AWS EC2 default expectation).\n" >&2
            export DEVICE_VALIDATION_DEGRADED=1
            return 0
        fi
    fi

    return 0
}

# If this script is executed directly, run test
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "🔧 iostat Data Collector Test"
    echo "========================="
    
    if validate_devices; then
        echo "✅ Device validation passed"
        echo ""
        echo "📊 CSV Header:"
        echo "timestamp,$(generate_all_devices_header)"
        echo ""
        echo "📊 Current Data:"
        echo "$(date +"$TIMESTAMP_FORMAT"),$(get_all_devices_data)"
    else
        echo "❌ Device validation failed"
        exit 1
    fi
fi
