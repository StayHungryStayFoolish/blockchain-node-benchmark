#!/bin/bash
# =====================================================================
# Solana QPS 测试框架 - 统一配置文件
# =====================================================================
# 版本: 2.0 - 生产级配置管理
# =====================================================================

# =====================================================================
# 用户配置区域 - 请根据您的环境修改以下配置
# =====================================================================

# ----- 基础配置 -----
# RPC 端点配置
LOCAL_RPC_URL=${RPC_URL:-"http://localhost:8899"}
# Mainnet RPC (用于对比测试)
MAINNET_RPC_URL="https://api.mainnet-beta.solana.com"

# ----- 区块链节点配置 -----
BLOCKCHAIN_NODE="Solana"

# ----- EBS 设备配置 -----
# DATA 设备 (LEDGER 数据存储)
LEDGER_DEVICE="nvme1n1"
# ACCOUNTS 设备 (可选，用于账户数据存储)
ACCOUNTS_DEVICE="nvme2n1"

# Data volume configuration
DATA_VOL_TYPE="io2"                    # Options: "gp3" | "io2" | "instance-store"
DATA_VOL_SIZE="2000"                   # Current required data size to keep both snapshot archive and unarchived version of it
DATA_VOL_MAX_IOPS="20000"              # Max IOPS for EBS volumes (REQUIRED for "instance-store")
DATA_VOL_MAX_THROUGHPUT="700"          # Max throughput in MiB/s (REQUIRED for "instance-store", auto-calculated for "io2")

# Accounts volume configuration (optional)
ACCOUNTS_VOL_TYPE="io2"                # Options: "gp3" | "io2" | "instance-store"
ACCOUNTS_VOL_SIZE="500"                # Current required data size to keep both snapshot archive and unarchived version of it
ACCOUNTS_VOL_MAX_IOPS="20000"          # Max IOPS for EBS volumes (REQUIRED for "instance-store")
ACCOUNTS_VOL_MAX_THROUGHPUT="700"      # Max throughput in MiB/s (REQUIRED for "instance-store", auto-calculated for "io2")

# =====================================================================
# Instance Store 配置说明
# =====================================================================
# 如果使用 "instance-store" 类型，必须根据您的EC2实例类型配置性能参数:
# 配置示例:
# DATA_VOL_TYPE="instance-store"
# DATA_VOL_MAX_IOPS="8000"        # 根据实例类型设置
# DATA_VOL_MAX_THROUGHPUT="600"   # 根据实例类型设置
#
# 参考文档: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instance-store-policy.html
# =====================================================================

# ----- 网络监控配置 -----
# EC2实例网络带宽配置 (单位: Gbps) - 用户必须根据EC2实例类型设置
# 📖 参考: https://docs.aws.amazon.com/ec2/latest/userguide/ec2-instance-network-bandwidth.html

NETWORK_MAX_BANDWIDTH_GBPS=25       # 网络最大带宽 (单位: Gbps) - 用户必须根据EC2实例类型设置

# 网络利用率阈值 (%) - 用于瓶颈检测
NETWORK_UTILIZATION_THRESHOLD=80    # 网络利用率超过80%视为瓶颈

# ----- 部署平台检测配置 -----
# 部署平台类型 (auto: 自动检测, aws: AWS环境, other: 其他环境)
DEPLOYMENT_PLATFORM=${DEPLOYMENT_PLATFORM:-"auto"}

# ENA网络限制监控配置 - 基于AWS ENA文档 (将根据部署平台自动调整)
ENA_MONITOR_ENABLED=true
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
LOG_CONSOLE=${LOG_CONSOLE:-true}       # 控制台输出
LOG_FILE=${LOG_FILE:-true}             # 文件输出
LOG_JSON=${LOG_JSON:-false}            # JSON格式输出

# Python日志配置
PYTHON_LOG_LEVEL=${PYTHON_LOG_LEVEL:-"INFO"}

# 导出日志配置环境变量
export LOG_LEVEL LOG_FORMAT MAX_LOG_SIZE MAX_LOG_FILES
export LOG_CONSOLE LOG_FILE LOG_JSON PYTHON_LOG_LEVEL

# ----- 监控配置 -----
# 统一监控间隔 (秒) - 可根据区块链节点需求调整
MONITOR_INTERVAL=5              # 默认监控间隔 (适合大多数场景)
# 默认监控时长 (秒) - 适合QPS测试
DEFAULT_MONITOR_DURATION=1800   # 30分钟
# 高频监控间隔 (秒) - 适用于高TPS区块链节点
HIGH_FREQ_INTERVAL=1            # 1秒高频监控
# 超高频监控间隔 (秒) - 适用于极高TPS场景 (如Solana)
ULTRA_HIGH_FREQ_INTERVAL=0.5    # 0.5秒超高频监控
# 监控开销统计间隔 (秒)
OVERHEAD_STAT_INTERVAL=60

# ----- 监控开销优化配置 -----
# 监控开销统计开关 (true/false) - 启用后会统计监控系统本身的资源开销
MONITORING_OVERHEAD_ENABLED=${MONITORING_OVERHEAD_ENABLED:-true}

# 监控开销日志配置
MONITORING_OVERHEAD_LOG="${LOGS_DIR}/monitoring_overhead_$(date +%Y%m%d_%H%M%S).csv"

# 监控开销CSV表头
OVERHEAD_CSV_HEADER="timestamp,monitoring_cpu_percent,monitoring_memory_percent,monitoring_memory_mb,monitoring_process_count,blockchain_cpu_percent,blockchain_memory_percent,blockchain_memory_mb,blockchain_process_count,system_cpu_cores,system_memory_gb,system_disk_gb,system_cpu_usage,system_memory_usage,system_disk_usage"

# 监控开销统计间隔 (秒) - 独立于主监控间隔
OVERHEAD_COLLECTION_INTERVAL=${OVERHEAD_COLLECTION_INTERVAL:-10}

# 监控开销阈值配置 - 用于警告和自动调整
OVERHEAD_CPU_WARNING_THRESHOLD=${OVERHEAD_CPU_WARNING_THRESHOLD:-3.0}      # 监控CPU使用率警告阈值 (%)
OVERHEAD_CPU_CRITICAL_THRESHOLD=${OVERHEAD_CPU_CRITICAL_THRESHOLD:-5.0}    # 监控CPU使用率严重阈值 (%)
OVERHEAD_MEMORY_WARNING_THRESHOLD=${OVERHEAD_MEMORY_WARNING_THRESHOLD:-2.0} # 监控内存使用率警告阈值 (%)
OVERHEAD_MEMORY_CRITICAL_THRESHOLD=${OVERHEAD_MEMORY_CRITICAL_THRESHOLD:-3.0} # 监控内存使用率严重阈值 (%)

# ----- 性能影响监控配置 -----
# 性能监控开关 (true/false) - 启用后会监控监控系统本身的性能影响
PERFORMANCE_MONITORING_ENABLED=${PERFORMANCE_MONITORING_ENABLED:-true}

# 性能阈值配置
MAX_COLLECTION_TIME_MS=${MAX_COLLECTION_TIME_MS:-1000}     # 最大数据收集时间 (毫秒)
CPU_THRESHOLD_PERCENT=${CPU_THRESHOLD_PERCENT:-5.0}        # CPU使用率阈值 (%)
MEMORY_THRESHOLD_MB=${MEMORY_THRESHOLD_MB:-100}            # 内存使用阈值 (MB)

# 性能监控详细级别 (basic/detailed/full)
PERFORMANCE_MONITORING_LEVEL=${PERFORMANCE_MONITORING_LEVEL:-"basic"}

# 性能日志配置
PERFORMANCE_LOG="${LOGS_DIR}/monitoring_performance_$(date +%Y%m%d_%H%M%S).log"

# 性能数据保留策略
PERFORMANCE_DATA_RETENTION_DAYS=${PERFORMANCE_DATA_RETENTION_DAYS:-7}      # 性能数据保留天数

# ----- 自适应频率调整配置 -----
# 自适应频率调整开关 (true/false) - 启用后会根据系统负载自动调整监控频率
ADAPTIVE_FREQUENCY_ENABLED=${ADAPTIVE_FREQUENCY_ENABLED:-true}

# 频率调整范围
MIN_MONITOR_INTERVAL=${MIN_MONITOR_INTERVAL:-2}            # 最小监控间隔 (秒)
MAX_MONITOR_INTERVAL=${MAX_MONITOR_INTERVAL:-30}           # 最大监控间隔 (秒)

# 系统负载阈值配置
SYSTEM_LOAD_THRESHOLD=${SYSTEM_LOAD_THRESHOLD:-80}         # 系统负载阈值 (%) - 超过此值将降低监控频率
SYSTEM_LOAD_HIGH_THRESHOLD=${SYSTEM_LOAD_HIGH_THRESHOLD:-90} # 高负载阈值 (%) - 超过此值将大幅降低监控频率
SYSTEM_LOAD_CRITICAL_THRESHOLD=${SYSTEM_LOAD_CRITICAL_THRESHOLD:-95} # 严重负载阈值 (%) - 超过此值将最小化监控

# 频率调整策略配置
FREQUENCY_ADJUSTMENT_FACTOR=${FREQUENCY_ADJUSTMENT_FACTOR:-1.5}            # 频率调整因子
FREQUENCY_ADJUSTMENT_AGGRESSIVE=${FREQUENCY_ADJUSTMENT_AGGRESSIVE:-false}   # 激进调整模式

# 频率调整日志
FREQUENCY_ADJUSTMENT_LOG="${LOGS_DIR}/frequency_adjustment_$(date +%Y%m%d_%H%M%S).log"

# ----- 优雅降级配置 -----
# 优雅降级开关 (true/false) - 启用后会在高负载时自动降级监控功能
GRACEFUL_DEGRADATION_ENABLED=${GRACEFUL_DEGRADATION_ENABLED:-true}

# 降级级别配置
DEGRADATION_LEVEL_1_THRESHOLD=${DEGRADATION_LEVEL_1_THRESHOLD:-75}         # 轻度降级阈值 (%)
DEGRADATION_LEVEL_2_THRESHOLD=${DEGRADATION_LEVEL_2_THRESHOLD:-85}         # 中度降级阈值 (%)
DEGRADATION_LEVEL_3_THRESHOLD=${DEGRADATION_LEVEL_3_THRESHOLD:-95}         # 严重降级阈值 (%)

# 降级策略配置
DEGRADATION_DISABLE_DETAILED_METRICS=${DEGRADATION_DISABLE_DETAILED_METRICS:-true}    # 降级时禁用详细指标
DEGRADATION_REDUCE_LOGGING=${DEGRADATION_REDUCE_LOGGING:-true}                        # 降级时减少日志记录
DEGRADATION_SKIP_NON_CRITICAL=${DEGRADATION_SKIP_NON_CRITICAL:-true}                  # 降级时跳过非关键监控

# ----- 错误处理和恢复配置 -----
# 错误恢复开关 (true/false) - 启用后会自动处理和恢复监控系统错误
ERROR_RECOVERY_ENABLED=${ERROR_RECOVERY_ENABLED:-true}

# 错误处理阈值
MAX_CONSECUTIVE_ERRORS=${MAX_CONSECUTIVE_ERRORS:-5}        # 最大连续错误次数
ERROR_RECOVERY_DELAY=${ERROR_RECOVERY_DELAY:-10}          # 错误恢复延迟 (秒)
ERROR_RECOVERY_MAX_ATTEMPTS=${ERROR_RECOVERY_MAX_ATTEMPTS:-3}  # 最大恢复尝试次数

# 错误类型配置
ERROR_TYPES_TO_RECOVER=(                                  # 需要自动恢复的错误类型
    "process_not_found"
    "permission_denied"
    "disk_full"
    "network_timeout"
    "resource_unavailable"
)

# 错误日志配置
ERROR_LOG="${LOGS_DIR}/monitoring_errors_$(date +%Y%m%d_%H%M%S).log"

# 错误统计配置
ERROR_STATISTICS_ENABLED=${ERROR_STATISTICS_ENABLED:-true}                 # 启用错误统计
ERROR_STATISTICS_WINDOW=${ERROR_STATISTICS_WINDOW:-300}                    # 错误统计时间窗口 (秒)

# ----- 监控系统健康检查配置 -----
# 健康检查开关 (true/false) - 启用后会定期检查监控系统健康状态
HEALTH_CHECK_ENABLED=${HEALTH_CHECK_ENABLED:-true}

# 健康检查间隔配置
HEALTH_CHECK_INTERVAL=${HEALTH_CHECK_INTERVAL:-60}        # 健康检查间隔 (秒)
HEALTH_CHECK_TIMEOUT=${HEALTH_CHECK_TIMEOUT:-10}          # 健康检查超时 (秒)

# 健康检查项目配置
HEALTH_CHECK_ITEMS=(                                      # 健康检查项目列表
    "disk_space"
    "memory_usage"
    "cpu_usage"
    "process_status"
    "log_file_size"
    "network_connectivity"
)

# 健康检查阈值
HEALTH_CHECK_DISK_THRESHOLD=${HEALTH_CHECK_DISK_THRESHOLD:-90}             # 磁盘使用率健康阈值 (%)
HEALTH_CHECK_MEMORY_THRESHOLD=${HEALTH_CHECK_MEMORY_THRESHOLD:-85}         # 内存使用率健康阈值 (%)
HEALTH_CHECK_CPU_THRESHOLD=${HEALTH_CHECK_CPU_THRESHOLD:-80}               # CPU使用率健康阈值 (%)

# 健康检查日志
HEALTH_CHECK_LOG="${LOGS_DIR}/health_check_$(date +%Y%m%d_%H%M%S).log"

# 时间格式标准
TIMESTAMP_FORMAT="%Y-%m-%d %H:%M:%S"

# ----- Slot 监控配置 -----
# Slot 差异阈值
SLOT_DIFF_THRESHOLD=500
# Slot 时间阈值 (秒)
SLOT_TIME_THRESHOLD=600
# Slot 监控间隔 (秒)
SLOT_MONITOR_INTERVAL=10

# ----- 日志文件路径配置 -----
# Validator 日志路径 - Solana生产环境日志 (只读，用于分析)
VALIDATOR_LOG_PATH="/data/data/log/validator.log"

# ----- QPS 基准测试配置 -----
# 快速基准测试模式 (验证基本QPS能力)
QUICK_INITIAL_QPS=1000
QUICK_MAX_QPS=3000
QUICK_QPS_STEP=500
QUICK_DURATION=60   # 每个QPS级别测试1分钟 (避免长时间测试导致的资源问题)

# 标准基准测试模式 (标准性能测试)
STANDARD_INITIAL_QPS=1000
STANDARD_MAX_QPS=5000
STANDARD_QPS_STEP=500
STANDARD_DURATION=600   # 每个QPS级别测试10分钟

# 深度基准测试模式 (自动寻找系统瓶颈)
INTENSIVE_INITIAL_QPS=1000
INTENSIVE_MAX_QPS=999999      # 无实际上限，直到检测到瓶颈
INTENSIVE_QPS_STEP=250
INTENSIVE_DURATION=600        # 每个QPS级别测试10分钟
INTENSIVE_AUTO_STOP=true      # 启用自动瓶颈检测停止

# 基准测试间隔配置
QPS_COOLDOWN=30      # QPS级别间的冷却时间 (秒)
QPS_WARMUP_DURATION=60  # 预热时间 (秒)

# QPS测试成功率和延迟阈值
SUCCESS_RATE_THRESHOLD=95    # 成功率阈值 (%)
MAX_LATENCY_THRESHOLD=1000   # 最大延迟阈值 (ms)
MAX_RETRIES=3               # 最大重试次数

# 账户和目标文件配置
ACCOUNT_COUNT=1000                                              # 默认账户数量

# ----- 账户获取工具配置 -----
# 账户获取工具的详细配置参数
ACCOUNT_OUTPUT_FILE="active_accounts.txt"                       # 输出文件名
ACCOUNT_TARGET_ADDRESS="TSLvdd1pWpHVjahSpsvCXUbgwsL3JAcvokwaKt1eokM"  # 示例目标地址
ACCOUNT_MAX_SIGNATURES=50000                                    # 最大签名数量
ACCOUNT_TX_BATCH_SIZE=100                                      # 交易批处理大小
ACCOUNT_SEMAPHORE_LIMIT=10                                     # 并发限制

# ----- 错误处理和日志配置 -----
# 基于统一路径结构的错误处理目录 (将在detect_deployment_paths中设置完整路径)
ERROR_LOG_SUBDIR="error_logs"                                  # 错误日志子目录名
PYTHON_ERROR_LOG_SUBDIR="python_logs"                         # Python错误日志子目录名
TEMP_FILE_PREFIX="solana-qps"                                 # 临时文件前缀

# ----- AWS相关配置 -----
# AWS EBS基准配置
AWS_EBS_BASELINE_IO_SIZE_KIB=16                               # AWS EBS基准IO大小 (KiB)

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
    "slot_monitor"
    "performance_visualizer"
    "overhead_monitor"
    "adaptive_frequency"
    "health_checker"
    "error_recovery"
    "report_generator"
)

# 区块链节点进程名配置（用于资源使用统计）
BLOCKCHAIN_PROCESS_NAMES=(
    "solana-validator"
    "solana"
    "blockchain"
    "validator"
    "node"
)

# 监控进程优先级配置（用于资源分配优化）
MONITORING_PROCESS_PRIORITY=(
    "unified_monitor:high"          # 核心监控进程，高优先级
    "overhead_monitor:medium"       # 开销监控，中等优先级
    "health_checker:medium"         # 健康检查，中等优先级
    "adaptive_frequency:low"        # 自适应调整，低优先级
    "error_recovery:high"           # 错误恢复，高优先级
    "report_generator:low"          # 报告生成，低优先级
)

# 关键监控进程配置（这些进程不能被降级或停止）
CRITICAL_MONITORING_PROCESSES=(
    "unified_monitor"
    "error_recovery"
    "health_checker"
)

# 可选监控进程配置（在资源紧张时可以暂停的进程）
OPTIONAL_MONITORING_PROCESSES=(
    "performance_visualizer"
    "report_generator"
    "adaptive_frequency"
)

# ----- 瓶颈检测配置 -----
# 瓶颈检测阈值 (极限测试用)
BOTTLENECK_CPU_THRESHOLD=85         # CPU使用率超过85%视为瓶颈
BOTTLENECK_MEMORY_THRESHOLD=90      # 内存使用率超过90%视为瓶颈
BOTTLENECK_EBS_UTIL_THRESHOLD=90    # EBS利用率超过90%视为瓶颈
BOTTLENECK_EBS_LATENCY_THRESHOLD=50 # EBS延迟超过50ms视为瓶颈
BOTTLENECK_ERROR_RATE_THRESHOLD=5   # 错误率超过5%视为瓶颈

# 网络带宽配置 (用于计算网络利用率) - 由系统自动配置区域设置

# 瓶颈检测连续次数 (避免偶发性波动)
BOTTLENECK_CONSECUTIVE_COUNT=3      # 连续3次检测到瓶颈才停止

# 瓶颈分析时间窗口配置
BOTTLENECK_ANALYSIS_WINDOW=30       # 瓶颈时间点前后分析窗口 (秒)
BOTTLENECK_CORRELATION_WINDOW=60    # 关联分析时间窗口 (秒)
PERFORMANCE_CLIFF_WINDOW=45         # 性能悬崖分析窗口 (秒)

# ----- RPC模式配置 -----
RPC_MODE="${RPC_MODE:-single}"      # RPC模式: single/mixed (默认single)

# =====================================================================
# 系统自动配置区域 - 以下变量由系统自动设置，用户通常无需修改
# =====================================================================

# ----- 自动计算的网络配置 -----
# 自动转换为Mbps (用于内部计算，用户无需修改)
NETWORK_MAX_BANDWIDTH_MBPS=$((NETWORK_MAX_BANDWIDTH_GBPS * 1000))
# 网络瓶颈检测阈值 (自动设置)
BOTTLENECK_NETWORK_THRESHOLD=$NETWORK_UTILIZATION_THRESHOLD

# =====================================================================
# 系统函数区域 - 请勿修改以下函数定义
# =====================================================================

# ----- 部署平台检测函数 -----
# 自动检测部署平台并调整ENA监控配置
detect_deployment_platform() {
    if [[ "$DEPLOYMENT_PLATFORM" == "auto" ]]; then
        echo "🔍 自动检测部署平台..." >&2
        
        # 检测是否在AWS环境 (通过AWS元数据服务)
        if curl -s --max-time 3 --connect-timeout 2 "${AWS_METADATA_ENDPOINT}/${AWS_METADATA_API_VERSION}/meta-data/instance-id" >/dev/null 2>&1; then
            DEPLOYMENT_PLATFORM="aws"
            ENA_MONITOR_ENABLED=true
            echo "✅ 检测到AWS环境，启用ENA监控" >&2
        else
            DEPLOYMENT_PLATFORM="other"
            ENA_MONITOR_ENABLED=false
            echo "ℹ️  检测到非AWS环境 (IDC/其他云)，禁用ENA监控" >&2
        fi
    else
        echo "🔧 使用手动配置的部署平台: $DEPLOYMENT_PLATFORM" >&2
        case "$DEPLOYMENT_PLATFORM" in
            "aws")
                ENA_MONITOR_ENABLED=true
                echo "✅ AWS环境，启用ENA监控" >&2
                ;;
            "other"|"idc")
                ENA_MONITOR_ENABLED=false
                echo "ℹ️  非AWS环境，禁用ENA监控" >&2
                ;;
            *)
                echo "⚠️  未知部署平台: $DEPLOYMENT_PLATFORM，禁用ENA监控" >&2
                ENA_MONITOR_ENABLED=false
                ;;
        esac
    fi
    
    # 输出最终配置
    echo "📊 部署平台配置:" >&2
    echo "   平台类型: $DEPLOYMENT_PLATFORM" >&2
    echo "   ENA监控: $ENA_MONITOR_ENABLED" >&2
    
    # 标记平台检测已完成并导出到子进程
    DEPLOYMENT_PLATFORM_DETECTED=true
    export DEPLOYMENT_PLATFORM_DETECTED
}

# ----- 路径检测和配置函数 -----
# 检测部署环境并设置路径
detect_deployment_paths() {
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local framework_dir="$(dirname "$script_dir")"
    local deployment_dir="$(dirname "$framework_dir")"
    
    echo "🔍 检测部署结构..." >&2
    echo "   框架目录: $framework_dir" >&2
    echo "   部署目录: $deployment_dir" >&2
    
    # 设置内存共享目录 (独立于数据目录，保持系统级路径)
    if [[ "$(uname -s)" == "Darwin" ]]; then
        # macOS 开发环境
        BASE_MEMORY_DIR="${TMPDIR:-/tmp}/blockchain-node-benchmark"
        DEPLOYMENT_ENV="development"
        echo "🔧 检测到开发环境 (macOS)" >&2
    else
        # Linux 生产环境 - 使用系统 tmpfs
        BASE_MEMORY_DIR="/dev/shm/blockchain-node-benchmark"
        DEPLOYMENT_ENV="production"
        echo "🐧 检测到Linux生产环境" >&2
    fi
    
    # 标准化路径配置
    BASE_FRAMEWORK_DIR="$framework_dir"
    BASE_DATA_DIR="${BLOCKCHAIN_BENCHMARK_DATA_DIR:-${deployment_dir}/blockchain-node-benchmark-result}"
    DEPLOYMENT_STRUCTURE="standard"
    
    echo "🚀 使用标准部署结构" >&2
    echo "   数据目录: $BASE_DATA_DIR" >&2
    
    # 支持环境变量覆盖
    if [[ -n "${BLOCKCHAIN_BENCHMARK_DATA_DIR:-}" ]]; then
        echo "   (使用环境变量: BLOCKCHAIN_BENCHMARK_DATA_DIR)" >&2
    fi
    
    # 验证部署结构
    validate_deployment_structure "$framework_dir" "$BASE_DATA_DIR"
    
    # 设置目录结构 - 基于新的标准化路径
    # 主数据目录 (QPS测试专属)
    DATA_DIR="${BASE_DATA_DIR}"
    # 当前测试数据目录
    CURRENT_TEST_DIR="${DATA_DIR}/current"
    # 日志目录 (性能监控数据)
    LOGS_DIR="${CURRENT_TEST_DIR}/logs"
    # 报告目录 (分析报告和图表)
    REPORTS_DIR="${CURRENT_TEST_DIR}/reports"
    # Vegeta 结果目录 (压测原始数据)
    VEGETA_RESULTS_DIR="${CURRENT_TEST_DIR}/vegeta_results"
    # 临时文件目录 (运行时临时数据)
    TMP_DIR="${CURRENT_TEST_DIR}/tmp"
    # 归档目录 (历史测试数据)
    ARCHIVES_DIR="${DATA_DIR}/archives"
    # 错误处理和日志目录
    ERROR_LOG_DIR="${CURRENT_TEST_DIR}/${ERROR_LOG_SUBDIR}"
    PYTHON_ERROR_LOG_DIR="${CURRENT_TEST_DIR}/${PYTHON_ERROR_LOG_SUBDIR}"
    
    # 内存共享目录 (独立于数据目录，使用系统级路径)
    MEMORY_SHARE_DIR="${BASE_MEMORY_DIR}"
    
    # 设置动态路径变量
    SLOT_CACHE_FILE="${MEMORY_SHARE_DIR}/slot_monitor_cache.json"
    SLOT_DATA_FILE="${LOGS_DIR}/slot_monitor_$(date +%Y%m%d_%H%M%S).csv"
    ACCOUNTS_OUTPUT_FILE="${TMP_DIR}/${ACCOUNT_OUTPUT_FILE}"
    SINGLE_METHOD_TARGETS_FILE="${TMP_DIR}/targets_single.json"
    MIXED_METHOD_TARGETS_FILE="${TMP_DIR}/targets_mixed.json"
    QPS_STATUS_FILE="${MEMORY_SHARE_DIR}/qps_status.json"
    TEST_SESSION_DIR="${TMP_DIR}/session_$(date +%Y%m%d_%H%M%S)"
    
    # 临时文件模式 (用于清理)
    TEMP_FILE_PATTERN="${TMP_DIR}/${TEMP_FILE_PREFIX}-*"
    
    # 输出最终配置
    echo "📋 路径配置完成:" >&2
    echo "   部署结构: $DEPLOYMENT_STRUCTURE" >&2
    echo "   框架目录: $BASE_FRAMEWORK_DIR" >&2
    echo "   数据目录: $BASE_DATA_DIR" >&2
    echo "   内存共享: $MEMORY_SHARE_DIR" >&2
    
    # 标记路径检测已完成并导出到子进程
    DEPLOYMENT_PATHS_DETECTED=true
    export DEPLOYMENT_PATHS_DETECTED
}

# ----- 部署结构验证函数 -----
validate_deployment_structure() {
    local framework_dir="$1"
    local data_dir="$2"
    
    echo "🔍 验证部署结构..." >&2
    
    # 验证框架目录结构
    local required_dirs=("analysis" "config" "core" "monitoring" "tools" "utils" "visualization")
    local missing_dirs=()
    
    for dir in "${required_dirs[@]}"; do
        if [[ ! -d "${framework_dir}/${dir}" ]]; then
            missing_dirs+=("$dir")
        fi
    done
    
    if [[ ${#missing_dirs[@]} -gt 0 ]]; then
        echo "❌ 框架目录结构不完整，缺少目录: ${missing_dirs[*]}" >&2
        echo "   框架路径: $framework_dir" >&2
        return 1
    fi
    
    # 验证数据目录父路径权限
    local data_parent_dir="$(dirname "$data_dir")"
    if [[ ! -d "$data_parent_dir" ]]; then
        echo "⚠️  数据目录父路径不存在: $data_parent_dir" >&2
        echo "   将尝试创建..." >&2
    elif [[ ! -w "$data_parent_dir" ]]; then
        echo "❌ 数据目录父路径不可写: $data_parent_dir" >&2
        echo "   请检查权限设置" >&2
        return 1
    fi
    
    # 检查磁盘空间 (如果df命令可用)
    if command -v df >/dev/null 2>&1; then
        local available_space=$(df "$data_parent_dir" 2>/dev/null | awk 'NR==2 {print $4}' || echo "0")
        if [[ "$available_space" -lt 1048576 ]]; then  # 1GB = 1048576 KB
            echo "⚠️  磁盘空间不足 (可用: ${available_space}KB): $data_parent_dir" >&2
            echo "   建议至少保留1GB空间用于测试数据" >&2
        fi
    fi
    
    echo "✅ 部署结构验证通过" >&2
    
    # 标记部署结构验证已完成并导出到子进程
    DEPLOYMENT_STRUCTURE_VALIDATED=true
    export DEPLOYMENT_STRUCTURE_VALIDATED
    
    return 0
}

# ----- 目录创建函数 -----
# 安全创建目录函数 - 增强版
create_directories_safely() {
    local dirs=("$@")
    local created_dirs=()
    local failed_dirs=()
    
    echo "🔧 正在创建必要的目录..." >&2
    
    for dir in "${dirs[@]}"; do
        if [[ ! -d "$dir" ]]; then
            # 检查父目录是否存在且可写
            local parent_dir=$(dirname "$dir")
            if [[ ! -d "$parent_dir" ]]; then
                echo "⚠️  父目录不存在，尝试创建: $parent_dir" >&2
                if ! mkdir -p "$parent_dir" 2>/dev/null; then
                    echo "❌ 无法创建父目录: $parent_dir" >&2
                    failed_dirs+=("$dir")
                    continue
                fi
            fi
            
            # 检查磁盘空间 (如果df命令可用)
            local available_space
            if command -v df >/dev/null 2>&1; then
                available_space=$(df "$parent_dir" 2>/dev/null | awk 'NR==2 {print $4}' || echo "0")
                if [[ "$available_space" -lt 1048576 ]]; then  # 1GB = 1048576 KB
                    echo "⚠️  磁盘空间不足 (可用: ${available_space}KB): $parent_dir" >&2
                fi
            fi
            
            if mkdir -p "$dir" 2>/dev/null; then
                echo "✅ 创建目录: $dir" >&2
                created_dirs+=("$dir")
                
                # 设置合适的权限
                chmod 755 "$dir" 2>/dev/null || true
            else
                echo "❌ 无法创建目录: $dir" >&2
                failed_dirs+=("$dir")
                
                # 使用临时目录作为后备
                local temp_dir="${TMPDIR:-/tmp}/solana-qps-test/$(basename "$dir")"
                echo "🔄 使用临时目录替代: $temp_dir" >&2
                if mkdir -p "$temp_dir" 2>/dev/null; then
                    # 更新变量指向临时目录
                    case "$dir" in
                        *logs*) LOGS_DIR="$temp_dir" ;;
                        *reports*) REPORTS_DIR="$temp_dir" ;;
                        *vegeta*) VEGETA_RESULTS_DIR="$temp_dir" ;;
                        *tmp*) TMP_DIR="$temp_dir" ;;
                        *shm*) MEMORY_SHARE_DIR="$temp_dir" ;;
                    esac
                    created_dirs+=("$temp_dir")
                fi
            fi
        else
            echo "✅ 目录已存在: $dir" >&2
        fi
    done
    
    # 标记目录创建已完成并导出到子进程
    DIRECTORIES_CREATED=true
    export DIRECTORIES_CREATED
    
    # 返回结果摘要
    if [[ ${#failed_dirs[@]} -gt 0 ]]; then
        echo "⚠️  部分目录创建失败: ${failed_dirs[*]}" >&2
        return 1
    else
        echo "✅ 所有目录创建成功" >&2
        return 0
    fi
}

# ----- 网络接口检测函数 -----
# 自动检测ENA网络接口
detect_network_interface() {
    # 优先检测ENA接口
    local ena_interfaces
    if command -v ip >/dev/null 2>&1; then
        ena_interfaces=($(ip link show 2>/dev/null | grep -E "^[0-9]+: (eth|ens|enp)" | grep "state UP" | cut -d: -f2 | tr -d ' '))
    else
        ena_interfaces=()
    fi
    
    # 如果找到ENA接口，优先使用第一个
    if [[ ${#ena_interfaces[@]} -gt 0 ]]; then
        echo "${ena_interfaces[0]}"
        return 0
    fi
    
    # 如果没有找到ENA接口，使用传统方法检测
    local interface=""
    if command -v ip >/dev/null 2>&1; then
        interface=$(ip route 2>/dev/null | grep default | awk '{print $5}' | head -1)
    elif command -v route >/dev/null 2>&1; then
        interface=$(route get default 2>/dev/null | grep interface | awk '{print $2}')
    elif command -v netstat >/dev/null 2>&1; then
        interface=$(netstat -rn 2>/dev/null | grep default | awk '{print $6}' | head -1)
    fi
    
    # 如果仍然没有找到，使用系统默认
    if [[ -z "$interface" ]]; then
        case "$(uname -s)" in
            "Darwin") interface="en0" ;;  # macOS默认
            "Linux") interface="eth0" ;;   # Linux默认
            *) interface="eth0" ;;         # 其他系统默认
        esac
    fi
    
    echo "$interface"
}

# ----- EBS性能基准计算函数 -----
calculate_ebs_performance_baselines() {
    # 根据卷类型和配置计算基准性能 - 基于AWS官方文档修正
    case "$DATA_VOL_TYPE" in
        "gp3")
            DATA_BASELINE_IOPS=${DATA_VOL_MAX_IOPS:-3000}
            # GP3最大吞吐量是1000 MiB/s，基准是125 MiB/s
            DATA_BASELINE_THROUGHPUT=${DATA_VOL_MAX_THROUGHPUT:-1000}
            ;;
        "io2")
            DATA_BASELINE_IOPS=${DATA_VOL_MAX_IOPS:-1000}
            # IO2吞吐量 = IOPS × 0.256，最大4000 MiB/s
            local calculated_throughput=$(( (${DATA_VOL_MAX_IOPS:-1000} * 256) / 1000 ))
            if [[ $calculated_throughput -gt 4000 ]]; then
                DATA_BASELINE_THROUGHPUT=4000  # 不超过最大值
            else
                DATA_BASELINE_THROUGHPUT=$calculated_throughput
            fi
            ;;
        "instance-store")
            # Instance Store性能必须由用户配置，不使用估算值
            if [[ -z "$DATA_VOL_MAX_IOPS" ]]; then
                echo "❌ 错误: DATA_VOL_MAX_IOPS 未配置"
                echo "   Instance Store性能因实例类型而异，请根据您的实例类型配置:"
                echo "   export DATA_VOL_MAX_IOPS=<您的实例IOPS>"
                echo "   参考: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instance-store-policy.html"
                exit 1
            fi
            
            if [[ -z "$DATA_VOL_MAX_THROUGHPUT" ]]; then
                echo "❌ 错误: DATA_VOL_MAX_THROUGHPUT 未配置"
                echo "   Instance Store吞吐量必须配置，请根据您的实例类型配置:"
                echo "   export DATA_VOL_MAX_THROUGHPUT=<您的实例吞吐量MiB/s>"
                echo "   参考: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instance-store-policy.html"
                exit 1
            fi
            
            DATA_BASELINE_IOPS=$DATA_VOL_MAX_IOPS
            DATA_BASELINE_THROUGHPUT=$DATA_VOL_MAX_THROUGHPUT
            ;;
        *)
            echo "❌ 错误: 不支持的DATA卷类型: $DATA_VOL_TYPE"
            echo "   支持的类型: gp3, io2, instance-store"
            exit 1
            ;;
    esac
    
    # ACCOUNTS设备配置 - 应用相同的逻辑
    if [[ -n "$ACCOUNTS_VOL_TYPE" ]]; then
        case "$ACCOUNTS_VOL_TYPE" in
            "gp3")
                ACCOUNTS_BASELINE_IOPS=${ACCOUNTS_VOL_MAX_IOPS:-3000}
                ACCOUNTS_BASELINE_THROUGHPUT=${ACCOUNTS_VOL_MAX_THROUGHPUT:-1000}
                ;;
            "io2")
                ACCOUNTS_BASELINE_IOPS=${ACCOUNTS_VOL_MAX_IOPS:-1000}
                # IO2吞吐量动态计算
                local accounts_calculated_throughput=$(( (${ACCOUNTS_VOL_MAX_IOPS:-1000} * 256) / 1000 ))
                if [[ $accounts_calculated_throughput -gt 4000 ]]; then
                    ACCOUNTS_BASELINE_THROUGHPUT=4000
                else
                    ACCOUNTS_BASELINE_THROUGHPUT=$accounts_calculated_throughput
                fi
                ;;
            "instance-store")
                # ACCOUNTS Instance Store也必须由用户配置
                if [[ -z "$ACCOUNTS_VOL_MAX_IOPS" ]]; then
                    echo "❌ 错误: ACCOUNTS_VOL_MAX_IOPS 未配置"
                    echo "   ACCOUNTS Instance Store性能必须配置:"
                    echo "   export ACCOUNTS_VOL_MAX_IOPS=<您的实例IOPS>"
                    exit 1
                fi
                
                if [[ -z "$ACCOUNTS_VOL_MAX_THROUGHPUT" ]]; then
                    echo "❌ 错误: ACCOUNTS_VOL_MAX_THROUGHPUT 未配置"
                    echo "   ACCOUNTS Instance Store吞吐量必须配置:"
                    echo "   export ACCOUNTS_VOL_MAX_THROUGHPUT=<您的实例吞吐量MiB/s>"
                    exit 1
                fi
                
                ACCOUNTS_BASELINE_IOPS=$ACCOUNTS_VOL_MAX_IOPS
                ACCOUNTS_BASELINE_THROUGHPUT=$ACCOUNTS_VOL_MAX_THROUGHPUT
                ;;
            *)
                echo "❌ 错误: 不支持的ACCOUNTS卷类型: $ACCOUNTS_VOL_TYPE"
                echo "   支持的类型: gp3, io2, instance-store"
                exit 1
                ;;
        esac
    fi
    
    # 输出计算结果用于调试
    if [[ "${DEBUG:-false}" == "true" ]]; then
        echo "🔧 EBS性能基准计算结果:"
        echo "  DATA设备 ($DATA_VOL_TYPE): ${DATA_BASELINE_IOPS} IOPS, ${DATA_BASELINE_THROUGHPUT} MiB/s"
        if [[ -n "$ACCOUNTS_VOL_TYPE" ]]; then
            echo "  ACCOUNTS设备 ($ACCOUNTS_VOL_TYPE): ${ACCOUNTS_BASELINE_IOPS} IOPS, ${ACCOUNTS_BASELINE_THROUGHPUT} MiB/s"
        fi
    fi
}

# ----- 时间管理函数 -----
get_unified_timestamp() {
    date +"$TIMESTAMP_FORMAT"
}

# 时间范围管理
record_time_range() {
    local event_type="$1"
    local start_time="$2"
    local end_time="$3"
    
    local time_range_file="${MEMORY_SHARE_DIR}/time_ranges.json"
    
    # 创建或更新时间范围记录
    local time_record="{\"event_type\":\"$event_type\",\"start_time\":\"$start_time\",\"end_time\":\"$end_time\",\"start_epoch\":$(date -d "$start_time" +%s 2>/dev/null || echo 0),\"end_epoch\":$(date -d "$end_time" +%s 2>/dev/null || echo 0)}"
    
    if [[ -f "$time_range_file" ]]; then
        # 添加到现有记录
        jq ". += [$time_record]" "$time_range_file" > "${time_range_file}.tmp" && mv "${time_range_file}.tmp" "$time_range_file"
    else
        # 创建新记录
        echo "[$time_record]" > "$time_range_file"
    fi
}

get_time_ranges() {
    local time_range_file="${MEMORY_SHARE_DIR}/time_ranges.json"
    if [[ -f "$time_range_file" ]]; then
        cat "$time_range_file"
    else
        echo "[]"
    fi
}

# ----- 监控开销优化配置管理函数 -----
# 动态调整监控间隔
adjust_monitor_interval() {
    local new_interval="$1"
    local reason="${2:-"manual adjustment"}"
    
    # 验证新间隔是否在允许范围内
    if (( $(echo "$new_interval < $MIN_MONITOR_INTERVAL" | bc -l) )); then
        echo "⚠️  调整后的监控间隔 ($new_interval) 小于最小值 ($MIN_MONITOR_INTERVAL)，使用最小值"
        new_interval=$MIN_MONITOR_INTERVAL
    elif (( $(echo "$new_interval > $MAX_MONITOR_INTERVAL" | bc -l) )); then
        echo "⚠️  调整后的监控间隔 ($new_interval) 大于最大值 ($MAX_MONITOR_INTERVAL)，使用最大值"
        new_interval=$MAX_MONITOR_INTERVAL
    fi
    
    local old_interval=${CURRENT_MONITOR_INTERVAL:-$MONITOR_INTERVAL}
    CURRENT_MONITOR_INTERVAL=$new_interval
    
    # 记录调整日志
    local timestamp=$(get_unified_timestamp)
    echo "$timestamp: 监控间隔调整: $old_interval -> $new_interval (原因: $reason)" >> "$FREQUENCY_ADJUSTMENT_LOG"
    
    echo "✅ 监控间隔已调整: $old_interval -> $new_interval 秒"
    return 0
}

# 获取当前有效的监控间隔
get_current_monitor_interval() {
    echo "${CURRENT_MONITOR_INTERVAL:-$MONITOR_INTERVAL}"
}

# 重置监控间隔到默认值
reset_monitor_interval() {
    local reason="${1:-"manual reset"}"
    adjust_monitor_interval "$MONITOR_INTERVAL" "$reason"
}

# 启用/禁用监控开销统计
toggle_monitoring_overhead() {
    local action="$1"  # enable/disable
    
    case "$action" in
        "enable")
            MONITORING_OVERHEAD_ENABLED=true
            echo "✅ 监控开销统计已启用"
            ;;
        "disable")
            MONITORING_OVERHEAD_ENABLED=false
            echo "✅ 监控开销统计已禁用"
            ;;
        *)
            echo "❌ 无效操作: $action (使用 enable 或 disable)"
            return 1
            ;;
    esac
    
    # 记录状态变更
    local timestamp=$(get_unified_timestamp)
    echo "$timestamp: 监控开销统计状态变更: $action" >> "$ERROR_LOG"
    
    return 0
}

# 启用/禁用自适应频率调整
toggle_adaptive_frequency() {
    local action="$1"  # enable/disable
    
    case "$action" in
        "enable")
            ADAPTIVE_FREQUENCY_ENABLED=true
            echo "✅ 自适应频率调整已启用"
            ;;
        "disable")
            ADAPTIVE_FREQUENCY_ENABLED=false
            echo "✅ 自适应频率调整已禁用"
            ;;
        *)
            echo "❌ 无效操作: $action (使用 enable 或 disable)"
            return 1
            ;;
    esac
    
    # 记录状态变更
    local timestamp=$(get_unified_timestamp)
    echo "$timestamp: 自适应频率调整状态变更: $action" >> "$FREQUENCY_ADJUSTMENT_LOG"
    
    return 0
}

# 启用/禁用优雅降级
toggle_graceful_degradation() {
    local action="$1"  # enable/disable
    
    case "$action" in
        "enable")
            GRACEFUL_DEGRADATION_ENABLED=true
            echo "✅ 优雅降级已启用"
            ;;
        "disable")
            GRACEFUL_DEGRADATION_ENABLED=false
            echo "✅ 优雅降级已禁用"
            ;;
        *)
            echo "❌ 无效操作: $action (使用 enable 或 disable)"
            return 1
            ;;
    esac
    
    # 记录状态变更
    local timestamp=$(get_unified_timestamp)
    echo "$timestamp: 优雅降级状态变更: $action" >> "$ERROR_LOG"
    
    return 0
}

# 设置监控开销阈值
set_overhead_threshold() {
    local threshold_type="$1"  # cpu_warning/cpu_critical/memory_warning/memory_critical
    local threshold_value="$2"
    
    # 验证阈值值
    if ! [[ "$threshold_value" =~ ^[0-9]+\.?[0-9]*$ ]]; then
        echo "❌ 阈值必须是数字: $threshold_value"
        return 1
    fi
    
    case "$threshold_type" in
        "cpu_warning")
            OVERHEAD_CPU_WARNING_THRESHOLD="$threshold_value"
            echo "✅ CPU开销警告阈值已设置为: $threshold_value%"
            ;;
        "cpu_critical")
            OVERHEAD_CPU_CRITICAL_THRESHOLD="$threshold_value"
            echo "✅ CPU开销严重阈值已设置为: $threshold_value%"
            ;;
        "memory_warning")
            OVERHEAD_MEMORY_WARNING_THRESHOLD="$threshold_value"
            echo "✅ 内存开销警告阈值已设置为: $threshold_value%"
            ;;
        "memory_critical")
            OVERHEAD_MEMORY_CRITICAL_THRESHOLD="$threshold_value"
            echo "✅ 内存开销严重阈值已设置为: $threshold_value%"
            ;;
        *)
            echo "❌ 无效的阈值类型: $threshold_type"
            echo "   支持的类型: cpu_warning, cpu_critical, memory_warning, memory_critical"
            return 1
            ;;
    esac
    
    # 记录阈值变更
    local timestamp=$(get_unified_timestamp)
    echo "$timestamp: 监控开销阈值变更: $threshold_type = $threshold_value%" >> "$ERROR_LOG"
    
    return 0
}

# 获取监控开销配置摘要
get_monitoring_overhead_summary() {
    echo "📊 监控开销优化配置摘要"
    echo "========================"
    echo "状态: ${MONITORING_OVERHEAD_ENABLED:-"未设置"}"
    echo "当前监控间隔: $(get_current_monitor_interval)秒"
    echo "自适应调整: ${ADAPTIVE_FREQUENCY_ENABLED:-"未设置"}"
    echo "优雅降级: ${GRACEFUL_DEGRADATION_ENABLED:-"未设置"}"
    echo "错误恢复: ${ERROR_RECOVERY_ENABLED:-"未设置"}"
    echo "健康检查: ${HEALTH_CHECK_ENABLED:-"未设置"}"
    echo "CPU阈值: 警告=${OVERHEAD_CPU_WARNING_THRESHOLD:-"未设置"}%, 严重=${OVERHEAD_CPU_CRITICAL_THRESHOLD:-"未设置"}%"
    echo "内存阈值: 警告=${OVERHEAD_MEMORY_WARNING_THRESHOLD:-"未设置"}%, 严重=${OVERHEAD_MEMORY_CRITICAL_THRESHOLD:-"未设置"}%"
    echo "========================"
}

# 导出监控开销配置到文件
export_monitoring_overhead_config() {
    local output_file="${1:-"${LOGS_DIR}/monitoring_overhead_config_$(date +%Y%m%d_%H%M%S).conf"}"
    
    cat > "$output_file" << EOF
# 监控开销优化配置导出
# 导出时间: $(get_unified_timestamp)
# ========================================

# 基础配置
MONITORING_OVERHEAD_ENABLED=${MONITORING_OVERHEAD_ENABLED:-"true"}
PERFORMANCE_MONITORING_ENABLED=${PERFORMANCE_MONITORING_ENABLED:-"true"}
PERFORMANCE_MONITORING_LEVEL=${PERFORMANCE_MONITORING_LEVEL:-"basic"}

# 时间间隔配置
MONITOR_INTERVAL=${MONITOR_INTERVAL:-"5"}
OVERHEAD_COLLECTION_INTERVAL=${OVERHEAD_COLLECTION_INTERVAL:-"10"}
MIN_MONITOR_INTERVAL=${MIN_MONITOR_INTERVAL:-"2"}
MAX_MONITOR_INTERVAL=${MAX_MONITOR_INTERVAL:-"30"}
CURRENT_MONITOR_INTERVAL=${CURRENT_MONITOR_INTERVAL:-$MONITOR_INTERVAL}

# 阈值配置
OVERHEAD_CPU_WARNING_THRESHOLD=${OVERHEAD_CPU_WARNING_THRESHOLD:-"3.0"}
OVERHEAD_CPU_CRITICAL_THRESHOLD=${OVERHEAD_CPU_CRITICAL_THRESHOLD:-"5.0"}
OVERHEAD_MEMORY_WARNING_THRESHOLD=${OVERHEAD_MEMORY_WARNING_THRESHOLD:-"2.0"}
OVERHEAD_MEMORY_CRITICAL_THRESHOLD=${OVERHEAD_MEMORY_CRITICAL_THRESHOLD:-"3.0"}

# 系统负载阈值
SYSTEM_LOAD_THRESHOLD=${SYSTEM_LOAD_THRESHOLD:-"80"}
SYSTEM_LOAD_HIGH_THRESHOLD=${SYSTEM_LOAD_HIGH_THRESHOLD:-"90"}
SYSTEM_LOAD_CRITICAL_THRESHOLD=${SYSTEM_LOAD_CRITICAL_THRESHOLD:-"95"}

# 功能开关
ADAPTIVE_FREQUENCY_ENABLED=${ADAPTIVE_FREQUENCY_ENABLED:-"true"}
GRACEFUL_DEGRADATION_ENABLED=${GRACEFUL_DEGRADATION_ENABLED:-"true"}
ERROR_RECOVERY_ENABLED=${ERROR_RECOVERY_ENABLED:-"true"}
HEALTH_CHECK_ENABLED=${HEALTH_CHECK_ENABLED:-"true"}

# 错误处理配置
MAX_CONSECUTIVE_ERRORS=${MAX_CONSECUTIVE_ERRORS:-"5"}
ERROR_RECOVERY_DELAY=${ERROR_RECOVERY_DELAY:-"10"}
ERROR_RECOVERY_MAX_ATTEMPTS=${ERROR_RECOVERY_MAX_ATTEMPTS:-"3"}

# 健康检查配置
HEALTH_CHECK_INTERVAL=${HEALTH_CHECK_INTERVAL:-"60"}
HEALTH_CHECK_TIMEOUT=${HEALTH_CHECK_TIMEOUT:-"10"}
EOF
    
    echo "✅ 监控开销配置已导出到: $output_file"
    return 0
}

# ----- EBS设备配置验证函数 -----
# 验证单个EBS设备配置
validate_ebs_device_config() {
    local device_type="$1"  # DATA 或 ACCOUNTS
    local errors=()
    
    # 获取配置变量
    local vol_type_var="${device_type}_VOL_TYPE"
    local vol_iops_var="${device_type}_VOL_MAX_IOPS"
    local vol_throughput_var="${device_type}_VOL_MAX_THROUGHPUT"
    
    local vol_type="${!vol_type_var}"
    local vol_iops="${!vol_iops_var}"
    local vol_throughput="${!vol_throughput_var}"
    
    if [[ -n "$vol_type" ]]; then
        case "$vol_type" in
            "gp3")
                [[ -z "$vol_iops" ]] && errors+=("${vol_iops_var} is required for gp3 volumes")
                [[ -z "$vol_throughput" ]] && errors+=("${vol_throughput_var} is required for gp3 volumes")
                ;;
            "io2")
                [[ -z "$vol_iops" ]] && errors+=("${vol_iops_var} is required for ${vol_type} volumes")
                # throughput对io2不适用，忽略该参数
                ;;
            "instance-store")
                [[ -z "$vol_iops" ]] && errors+=("${vol_iops_var} is required for instance-store volumes")
                [[ -z "$vol_throughput" ]] && errors+=("${vol_throughput_var} is required for instance-store volumes")
                ;;
            *)
                errors+=("Unsupported ${vol_type_var}: $vol_type")
                ;;
        esac
    fi
    
    printf '%s\n' "${errors[@]}"
}

# 检查设备是否配置
is_device_configured() {
    local device_type="$1"
    case "$device_type" in
        "DATA")
            [[ -n "$DATA_VOL_TYPE" ]]
            ;;
        "ACCOUNTS")
            [[ -n "$ACCOUNTS_VOL_TYPE" ]]
            ;;
        *)
            return 1
            ;;
    esac
}

# 获取逻辑名映射
get_logical_name() {
    local device_type="$1"
    case "$device_type" in
        "DATA") echo "ledger" ;;
        "ACCOUNTS") echo "accounts" ;;
        *) echo "unknown" ;;
    esac
}

# ----- 监控开销优化配置验证函数 -----
# 验证监控开销优化配置
validate_monitoring_overhead_config() {
    local errors=()
    local warnings=()
    
    # 验证监控开销阈值配置
    if [[ -n "$OVERHEAD_CPU_WARNING_THRESHOLD" ]]; then
        if ! [[ "$OVERHEAD_CPU_WARNING_THRESHOLD" =~ ^[0-9]+\.?[0-9]*$ ]]; then
            errors+=("OVERHEAD_CPU_WARNING_THRESHOLD must be a number: $OVERHEAD_CPU_WARNING_THRESHOLD")
        elif (( $(echo "$OVERHEAD_CPU_WARNING_THRESHOLD > 10" | bc -l) )); then
            warnings+=("OVERHEAD_CPU_WARNING_THRESHOLD is very high (>10%): $OVERHEAD_CPU_WARNING_THRESHOLD")
        fi
    fi
    
    if [[ -n "$OVERHEAD_CPU_CRITICAL_THRESHOLD" ]]; then
        if ! [[ "$OVERHEAD_CPU_CRITICAL_THRESHOLD" =~ ^[0-9]+\.?[0-9]*$ ]]; then
            errors+=("OVERHEAD_CPU_CRITICAL_THRESHOLD must be a number: $OVERHEAD_CPU_CRITICAL_THRESHOLD")
        elif (( $(echo "$OVERHEAD_CPU_CRITICAL_THRESHOLD <= $OVERHEAD_CPU_WARNING_THRESHOLD" | bc -l) )); then
            errors+=("OVERHEAD_CPU_CRITICAL_THRESHOLD must be greater than WARNING_THRESHOLD")
        fi
    fi
    
    # 验证频率调整配置
    if [[ -n "$MIN_MONITOR_INTERVAL" && -n "$MAX_MONITOR_INTERVAL" ]]; then
        if (( MIN_MONITOR_INTERVAL >= MAX_MONITOR_INTERVAL )); then
            errors+=("MIN_MONITOR_INTERVAL must be less than MAX_MONITOR_INTERVAL")
        fi
        if (( MIN_MONITOR_INTERVAL < 1 )); then
            warnings+=("MIN_MONITOR_INTERVAL is very low (<1s): $MIN_MONITOR_INTERVAL")
        fi
        if (( MAX_MONITOR_INTERVAL > 60 )); then
            warnings+=("MAX_MONITOR_INTERVAL is very high (>60s): $MAX_MONITOR_INTERVAL")
        fi
    fi
    
    # 验证系统负载阈值配置
    local load_thresholds=("$SYSTEM_LOAD_THRESHOLD" "$SYSTEM_LOAD_HIGH_THRESHOLD" "$SYSTEM_LOAD_CRITICAL_THRESHOLD")
    local prev_threshold=0
    for threshold in "${load_thresholds[@]}"; do
        if [[ -n "$threshold" ]]; then
            if ! [[ "$threshold" =~ ^[0-9]+$ ]]; then
                errors+=("Load threshold must be an integer: $threshold")
            elif (( threshold <= prev_threshold )); then
                errors+=("Load thresholds must be in ascending order")
            elif (( threshold > 100 )); then
                errors+=("Load threshold cannot exceed 100%: $threshold")
            fi
            prev_threshold=$threshold
        fi
    done
    
    # 验证错误处理配置
    if [[ -n "$MAX_CONSECUTIVE_ERRORS" ]]; then
        if ! [[ "$MAX_CONSECUTIVE_ERRORS" =~ ^[0-9]+$ ]]; then
            errors+=("MAX_CONSECUTIVE_ERRORS must be an integer: $MAX_CONSECUTIVE_ERRORS")
        elif (( MAX_CONSECUTIVE_ERRORS < 1 )); then
            errors+=("MAX_CONSECUTIVE_ERRORS must be at least 1")
        elif (( MAX_CONSECUTIVE_ERRORS > 20 )); then
            warnings+=("MAX_CONSECUTIVE_ERRORS is very high (>20): $MAX_CONSECUTIVE_ERRORS")
        fi
    fi
    
    # 验证健康检查配置
    if [[ -n "$HEALTH_CHECK_INTERVAL" ]]; then
        if ! [[ "$HEALTH_CHECK_INTERVAL" =~ ^[0-9]+$ ]]; then
            errors+=("HEALTH_CHECK_INTERVAL must be an integer: $HEALTH_CHECK_INTERVAL")
        elif (( HEALTH_CHECK_INTERVAL < 10 )); then
            warnings+=("HEALTH_CHECK_INTERVAL is very low (<10s): $HEALTH_CHECK_INTERVAL")
        fi
    fi
    
    # 验证监控进程配置
    if [[ ${#MONITORING_PROCESS_NAMES[@]} -eq 0 ]]; then
        errors+=("MONITORING_PROCESS_NAMES array is empty")
    fi
    
    if [[ ${#BLOCKCHAIN_PROCESS_NAMES[@]} -eq 0 ]]; then
        warnings+=("BLOCKCHAIN_PROCESS_NAMES array is empty - blockchain process monitoring disabled")
    fi
    
    # 验证关键进程配置
    for critical_process in "${CRITICAL_MONITORING_PROCESSES[@]}"; do
        local found=false
        for process in "${MONITORING_PROCESS_NAMES[@]}"; do
            if [[ "$process" == "$critical_process" ]]; then
                found=true
                break
            fi
        done
        if [[ "$found" == "false" ]]; then
            warnings+=("Critical process not in monitoring list: $critical_process")
        fi
    done
    
    # 输出结果
    local has_errors=false
    if [[ ${#errors[@]} -gt 0 ]]; then
        echo "❌ 监控开销优化配置验证失败:"
        printf '  - %s\n' "${errors[@]}"
        has_errors=true
    fi
    
    if [[ ${#warnings[@]} -gt 0 ]]; then
        echo "⚠️  监控开销优化配置警告:"
        printf '  - %s\n' "${warnings[@]}"
    fi
    
    if [[ "$has_errors" == "false" ]]; then
        echo "✅ 监控开销优化配置验证通过"
        return 0
    else
        return 1
    fi
}

# ----- 配置验证函数 -----
validate_config() {
    local errors=()
    
    # 检查必要目录
    if [[ ! -d "$DATA_DIR" ]]; then
        errors+=("DATA_DIR does not exist: $DATA_DIR")
    fi
    
    # 验证DATA设备（必须配置）
    if [[ -z "$LEDGER_DEVICE" ]]; then
        errors+=("LEDGER_DEVICE is not configured")
    elif [[ ! -b "/dev/$LEDGER_DEVICE" ]]; then
        errors+=("LEDGER_DEVICE does not exist: /dev/$LEDGER_DEVICE")
    fi
    
    # 验证DATA卷配置
    if is_device_configured "DATA"; then
        local data_errors
        data_errors=($(validate_ebs_device_config "DATA"))
        if [[ ${#data_errors[@]} -gt 0 ]]; then
            errors+=("${data_errors[@]}")
        fi
    fi
    
    # 验证ACCOUNTS设备（可选）
    if [[ -n "$ACCOUNTS_DEVICE" ]]; then
        if [[ ! -b "/dev/$ACCOUNTS_DEVICE" ]]; then
            errors+=("ACCOUNTS_DEVICE does not exist: /dev/$ACCOUNTS_DEVICE")
        fi
        
        # 验证ACCOUNTS卷配置
        if is_device_configured "ACCOUNTS"; then
            local accounts_errors
            accounts_errors=($(validate_ebs_device_config "ACCOUNTS"))
            if [[ ${#accounts_errors[@]} -gt 0 ]]; then
                errors+=("${accounts_errors[@]}")
            fi
        fi
    fi
    
    # 检查日志文件
    if [[ -n "$VALIDATOR_LOG_PATH" && ! -f "$VALIDATOR_LOG_PATH" ]]; then
        errors+=("VALIDATOR_LOG_PATH does not exist: $VALIDATOR_LOG_PATH")
    fi
    
    # 检查网络接口
    if [[ -z "$NETWORK_INTERFACE" ]]; then
        errors+=("Cannot detect network interface")
    fi
    
    # 验证监控开销优化配置
    validate_monitoring_overhead_config
    local overhead_validation_result=$?
    
    # 输出错误
    if [[ ${#errors[@]} -gt 0 ]]; then
        echo "❌ Configuration validation failed:"
        printf '  - %s\n' "${errors[@]}"
        return 1
    elif [[ $overhead_validation_result -ne 0 ]]; then
        echo "❌ Configuration validation failed due to monitoring overhead config errors"
        return 1
    else
        echo "✅ Configuration validation passed"
        return 0
    fi
}

# ----- 配置信息显示函数 -----
show_config() {
    echo "📋 Blockchain Node Benchmark Framework Configuration"
    echo "=================================================="
    echo "Deployment Structure: ${DEPLOYMENT_STRUCTURE:-"unknown"}"
    echo "Framework Directory: ${BASE_FRAMEWORK_DIR:-"N/A"}"
    echo "Data Directory: $DATA_DIR"
    echo "Logs Directory: $LOGS_DIR"
    echo "Reports Directory: $REPORTS_DIR"
    echo "Memory Share Directory: $MEMORY_SHARE_DIR"
    echo "Network Interface: $NETWORK_INTERFACE"
    echo "Network Bandwidth: ${NETWORK_MAX_BANDWIDTH_GBPS} Gbps"
    echo "DATA Device: $LEDGER_DEVICE ($DATA_VOL_TYPE)"
    echo "ACCOUNTS Device: ${ACCOUNTS_DEVICE:-"Not configured"} (${ACCOUNTS_VOL_TYPE:-"N/A"})"
    echo "Validator Log: $VALIDATOR_LOG_PATH"
    echo "Deployment Environment: $DEPLOYMENT_ENV"
    echo ""
    echo "📊 Monitoring Overhead Optimization Configuration"
    echo "=================================================="
    echo "Monitoring Overhead Enabled: ${MONITORING_OVERHEAD_ENABLED:-"false"}"
    echo "Performance Monitoring Enabled: ${PERFORMANCE_MONITORING_ENABLED:-"false"}"
    echo "Adaptive Frequency Enabled: ${ADAPTIVE_FREQUENCY_ENABLED:-"false"}"
    echo "Graceful Degradation Enabled: ${GRACEFUL_DEGRADATION_ENABLED:-"false"}"
    echo "Error Recovery Enabled: ${ERROR_RECOVERY_ENABLED:-"false"}"
    echo "Health Check Enabled: ${HEALTH_CHECK_ENABLED:-"false"}"
    echo ""
    echo "Monitor Interval Range: ${MIN_MONITOR_INTERVAL:-"N/A"}s - ${MAX_MONITOR_INTERVAL:-"N/A"}s"
    echo "Current Monitor Interval: ${MONITOR_INTERVAL:-"N/A"}s"
    echo "Overhead Collection Interval: ${OVERHEAD_COLLECTION_INTERVAL:-"N/A"}s"
    echo "Health Check Interval: ${HEALTH_CHECK_INTERVAL:-"N/A"}s"
    echo ""
    echo "CPU Overhead Thresholds: Warning=${OVERHEAD_CPU_WARNING_THRESHOLD:-"N/A"}%, Critical=${OVERHEAD_CPU_CRITICAL_THRESHOLD:-"N/A"}%"
    echo "Memory Overhead Thresholds: Warning=${OVERHEAD_MEMORY_WARNING_THRESHOLD:-"N/A"}%, Critical=${OVERHEAD_MEMORY_CRITICAL_THRESHOLD:-"N/A"}%"
    echo "System Load Thresholds: Normal=${SYSTEM_LOAD_THRESHOLD:-"N/A"}%, High=${SYSTEM_LOAD_HIGH_THRESHOLD:-"N/A"}%, Critical=${SYSTEM_LOAD_CRITICAL_THRESHOLD:-"N/A"}%"
    echo ""
    echo "Monitoring Processes: ${#MONITORING_PROCESS_NAMES[@]} configured"
    echo "Blockchain Processes: ${#BLOCKCHAIN_PROCESS_NAMES[@]} configured"
    echo "Critical Processes: ${#CRITICAL_MONITORING_PROCESSES[@]} configured"
    echo "Optional Processes: ${#OPTIONAL_MONITORING_PROCESSES[@]} configured"
    echo "=================================================="
}

# 显示监控开销优化配置详情
show_monitoring_overhead_config() {
    echo "📊 监控开销优化详细配置"
    echo "=================================================="
    echo ""
    echo "🔧 基础配置:"
    echo "  监控开销统计: ${MONITORING_OVERHEAD_ENABLED:-"未设置"}"
    echo "  性能监控: ${PERFORMANCE_MONITORING_ENABLED:-"未设置"}"
    echo "  监控级别: ${PERFORMANCE_MONITORING_LEVEL:-"未设置"}"
    echo "  数据保留天数: ${PERFORMANCE_DATA_RETENTION_DAYS:-"未设置"}"
    echo ""
    echo "⏱️  时间间隔配置:"
    echo "  基础监控间隔: ${MONITOR_INTERVAL:-"未设置"}秒"
    echo "  开销收集间隔: ${OVERHEAD_COLLECTION_INTERVAL:-"未设置"}秒"
    echo "  健康检查间隔: ${HEALTH_CHECK_INTERVAL:-"未设置"}秒"
    echo "  最小监控间隔: ${MIN_MONITOR_INTERVAL:-"未设置"}秒"
    echo "  最大监控间隔: ${MAX_MONITOR_INTERVAL:-"未设置"}秒"
    echo ""
    echo "🚨 阈值配置:"
    echo "  CPU开销警告阈值: ${OVERHEAD_CPU_WARNING_THRESHOLD:-"未设置"}%"
    echo "  CPU开销严重阈值: ${OVERHEAD_CPU_CRITICAL_THRESHOLD:-"未设置"}%"
    echo "  内存开销警告阈值: ${OVERHEAD_MEMORY_WARNING_THRESHOLD:-"未设置"}%"
    echo "  内存开销严重阈值: ${OVERHEAD_MEMORY_CRITICAL_THRESHOLD:-"未设置"}%"
    echo "  系统负载阈值: ${SYSTEM_LOAD_THRESHOLD:-"未设置"}%"
    echo "  高负载阈值: ${SYSTEM_LOAD_HIGH_THRESHOLD:-"未设置"}%"
    echo "  严重负载阈值: ${SYSTEM_LOAD_CRITICAL_THRESHOLD:-"未设置"}%"
    echo ""
    echo "🔄 自适应调整配置:"
    echo "  自适应频率调整: ${ADAPTIVE_FREQUENCY_ENABLED:-"未设置"}"
    echo "  调整因子: ${FREQUENCY_ADJUSTMENT_FACTOR:-"未设置"}"
    echo "  激进调整模式: ${FREQUENCY_ADJUSTMENT_AGGRESSIVE:-"未设置"}"
    echo ""
    echo "📉 优雅降级配置:"
    echo "  优雅降级: ${GRACEFUL_DEGRADATION_ENABLED:-"未设置"}"
    echo "  轻度降级阈值: ${DEGRADATION_LEVEL_1_THRESHOLD:-"未设置"}%"
    echo "  中度降级阈值: ${DEGRADATION_LEVEL_2_THRESHOLD:-"未设置"}%"
    echo "  严重降级阈值: ${DEGRADATION_LEVEL_3_THRESHOLD:-"未设置"}%"
    echo ""
    echo "🛠️  错误处理配置:"
    echo "  错误恢复: ${ERROR_RECOVERY_ENABLED:-"未设置"}"
    echo "  最大连续错误: ${MAX_CONSECUTIVE_ERRORS:-"未设置"}"
    echo "  恢复延迟: ${ERROR_RECOVERY_DELAY:-"未设置"}秒"
    echo "  最大恢复尝试: ${ERROR_RECOVERY_MAX_ATTEMPTS:-"未设置"}"
    echo "  错误统计: ${ERROR_STATISTICS_ENABLED:-"未设置"}"
    echo ""
    echo "💊 健康检查配置:"
    echo "  健康检查: ${HEALTH_CHECK_ENABLED:-"未设置"}"
    echo "  检查超时: ${HEALTH_CHECK_TIMEOUT:-"未设置"}秒"
    echo "  磁盘阈值: ${HEALTH_CHECK_DISK_THRESHOLD:-"未设置"}%"
    echo "  内存阈值: ${HEALTH_CHECK_MEMORY_THRESHOLD:-"未设置"}%"
    echo "  CPU阈值: ${HEALTH_CHECK_CPU_THRESHOLD:-"未设置"}%"
    echo ""
    echo "📋 进程配置:"
    echo "  监控进程数量: ${#MONITORING_PROCESS_NAMES[@]}"
    echo "  区块链进程数量: ${#BLOCKCHAIN_PROCESS_NAMES[@]}"
    echo "  关键进程数量: ${#CRITICAL_MONITORING_PROCESSES[@]}"
    echo "  可选进程数量: ${#OPTIONAL_MONITORING_PROCESSES[@]}"
    echo ""
    echo "📁 日志文件配置:"
    echo "  监控开销日志: ${MONITORING_OVERHEAD_LOG:-"未设置"}"
    echo "  性能监控日志: ${PERFORMANCE_LOG:-"未设置"}"
    echo "  频率调整日志: ${FREQUENCY_ADJUSTMENT_LOG:-"未设置"}"
    echo "  错误日志: ${ERROR_LOG:-"未设置"}"
    echo "  健康检查日志: ${HEALTH_CHECK_LOG:-"未设置"}"
    echo "=================================================="
}

# =====================================================================
# 系统初始化区域 - 自动执行的初始化代码
# =====================================================================

# 检查是否需要静默执行（防止重复日志）
CONFIG_INIT_FLAG_FILE="${TMPDIR:-/tmp}/blockchain-benchmark-config-initialized"
SILENT_MODE=false

if [[ -f "$CONFIG_INIT_FLAG_FILE" ]]; then
    SILENT_MODE=true
fi

# 始终执行路径检测和配置（但可能静默）
if [[ "$SILENT_MODE" == "true" ]]; then
    detect_deployment_paths >/dev/null 2>&1
else
    detect_deployment_paths
fi

# 始终执行部署平台检测（但可能静默）
if [[ "$SILENT_MODE" == "true" ]]; then
    detect_deployment_platform >/dev/null 2>&1
else
    detect_deployment_platform
fi

# 设置网络接口
NETWORK_INTERFACE=$(detect_network_interface)

# 始终创建必要的目录（但可能静默）
if [[ "$SILENT_MODE" == "true" ]]; then
    create_directories_safely "${LOGS_DIR}" "${REPORTS_DIR}" "${VEGETA_RESULTS_DIR}" "${TMP_DIR}" "${ARCHIVES_DIR}" "${MEMORY_SHARE_DIR}" "${ERROR_LOG_DIR}" "${PYTHON_ERROR_LOG_DIR}" >/dev/null 2>&1
else
    create_directories_safely "${LOGS_DIR}" "${REPORTS_DIR}" "${VEGETA_RESULTS_DIR}" "${TMP_DIR}" "${ARCHIVES_DIR}" "${MEMORY_SHARE_DIR}" "${ERROR_LOG_DIR}" "${PYTHON_ERROR_LOG_DIR}"
fi

# 执行EBS性能基准计算
calculate_ebs_performance_baselines

# 创建标记文件（如果不存在）
if [[ ! -f "$CONFIG_INIT_FLAG_FILE" ]]; then
    touch "$CONFIG_INIT_FLAG_FILE"
fi

# 自动验证配置 (如果直接执行此脚本)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    show_config
    validate_config
fi
