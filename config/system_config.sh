#!/bin/bash
# =====================================================================
# Blockchain Node Benchmark Framework - 系统配置层
# =====================================================================
# 目标用户: 系统管理员和高级用户
# 配置内容: AWS参数、日志配置、高级瓶颈检测阈值
# 修改频率: 偶尔修改
# =====================================================================

# ----- 部署平台检测配置 -----
# 部署平台类型 (auto: 自动检测, aws: AWS环境, other: 其他环境)
DEPLOYMENT_PLATFORM=${DEPLOYMENT_PLATFORM:-"auto"}

# ENA网络限制监控配置 - 基于AWS ENA文档 (将根据部署平台自动调整)
ENA_ALLOWANCE_FIELDS=(
    "bw_in_allowance_exceeded"
    "bw_out_allowance_exceeded"
    "pps_allowance_exceeded"
    "conntrack_allowance_exceeded"
    "linklocal_allowance_exceeded"
    "conntrack_allowance_available"
)

# ----- 统一日志管理配置 -----
# 日志级别配置 (0=DEBUG, 1=INFO, 2=WARN, 3=ERROR, 4=FATAL)
LOG_LEVEL=${LOG_LEVEL:-1}  # 默认INFO级别

# 日志格式配置
LOG_FORMAT=${LOG_FORMAT:-"[%timestamp%] [%level%] [%component%] %message%"}

# 日志轮转配置
MAX_LOG_SIZE=${MAX_LOG_SIZE:-"10M"}    # 最大日志文件大小
MAX_LOG_FILES=${MAX_LOG_FILES:-5}      # 保留的日志文件数量

# 日志输出配置
LOG_JSON=${LOG_JSON:-false}            # JSON格式输出

# ----- 错误处理和恢复配置 -----
# 错误恢复开关 (true/false) - 基准测试框架中禁用自动恢复以保证测试准确性
ERROR_RECOVERY_ENABLED=${ERROR_RECOVERY_ENABLED:-false}

# 错误处理阈值
ERROR_RECOVERY_DELAY=${ERROR_RECOVERY_DELAY:-10}          # 错误恢复延迟 (秒)

# ----- 错误处理和日志配置 -----
# 基于统一路径结构的错误处理目录 (将在detect_deployment_paths中设置完整路径)
ERROR_LOG_SUBDIR="error_logs"                                  # 错误日志子目录名
PYTHON_ERROR_LOG_SUBDIR="python_logs"                         # Python错误日志子目录名
TEMP_FILE_PREFIX="blockchain-node-qps"                                 # 临时文件前缀

# ----- AWS相关配置 -----
# AWS EBS基准配置
AWS_EBS_BASELINE_IO_SIZE_KIB=16                               # AWS EBS基准IO大小 (KiB)
AWS_EBS_BASELINE_THROUGHPUT_SIZE_KIB=128                      # AWS EBS基准Throughput大小 (KiB)

# AWS元数据服务端点配置
AWS_METADATA_ENDPOINT="http://169.254.169.254"                # AWS实例元数据端点
AWS_METADATA_TOKEN_TTL=21600                                  # 元数据令牌TTL (6小时)
AWS_METADATA_API_VERSION="latest"                             # API版本

# ----- 监控进程配置 -----
# 监控进程名配置（用于监控开销计算）
MONITORING_PROCESS_NAMES=(
    "iostat"
    "mpstat"
    "sar"
    "vmstat"
    "netstat"
    "unified_monitor"
    "bottleneck_detector"
    "ena_network_monitor"
    "block_height_monitor"
    "performance_visualizer"
    "report_generator"
)

# 时间格式标准
TIMESTAMP_FORMAT="%Y-%m-%d %H:%M:%S"

get_unified_timestamp() {
    date +"$TIMESTAMP_FORMAT"
}

get_unified_epoch() {
    date +%s
}

# 静默模式配置
SILENT_MODE=${SILENT_MODE:-false}

# 监控开销CSV表头定义 - 20个字段 (与unified_monitor.sh实际输出匹配)
OVERHEAD_CSV_HEADER="timestamp,monitoring_cpu,monitoring_memory_percent,monitoring_memory_mb,monitoring_process_count,blockchain_cpu,blockchain_memory_percent,blockchain_memory_mb,blockchain_process_count,system_cpu_cores,system_memory_gb,system_disk_gb,system_cpu_usage,system_memory_usage,system_disk_usage,system_cached_gb,system_buffers_gb,system_anon_pages_gb,system_mapped_gb,system_shmem_gb"

# 添加配置验证函数
validate_overhead_csv_header() {
    if [[ -z "$OVERHEAD_CSV_HEADER" ]]; then
        echo "错误: OVERHEAD_CSV_HEADER变量未定义" >&2
        return 1
    fi
    
    local field_count=$(echo "$OVERHEAD_CSV_HEADER" | tr ',' '\n' | wc -l)
    if [[ $field_count -ne 20 ]]; then
        echo "警告: OVERHEAD_CSV_HEADER字段数量不正确，期望20个，实际${field_count}个" >&2
    fi
}

# 导出系统配置变量
export -f get_unified_timestamp get_unified_epoch
export ENA_ALLOWANCE_FIELDS_STR="${ENA_ALLOWANCE_FIELDS[*]}"
export MONITORING_PROCESS_NAMES_STR="${MONITORING_PROCESS_NAMES[*]}"
export ENA_ALLOWANCE_FIELDS MONITORING_PROCESS_NAMES DEPLOYMENT_PLATFORM
export LOG_LEVEL LOG_FORMAT MAX_LOG_SIZE MAX_LOG_FILES LOG_JSON
export ERROR_RECOVERY_ENABLED ERROR_RECOVERY_DELAY
export ERROR_LOG_SUBDIR PYTHON_ERROR_LOG_SUBDIR TEMP_FILE_PREFIX
export AWS_EBS_BASELINE_IO_SIZE_KIB AWS_EBS_BASELINE_THROUGHPUT_SIZE_KIB AWS_METADATA_ENDPOINT AWS_METADATA_TOKEN_TTL AWS_METADATA_API_VERSION
export TIMESTAMP_FORMAT SILENT_MODE OVERHEAD_CSV_HEADER