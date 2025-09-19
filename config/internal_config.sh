#!/bin/bash
# =====================================================================
# Blockchain Node Benchmark Framework - 内部配置层
# =====================================================================
# 目标用户: 框架开发者
# 配置内容: 内部实现细节、动态检测结果、性能参数
# 修改频率: 很少修改
# =====================================================================

# ----- 内部状态管理 -----
# 配置加载状态标记
CONFIG_LOADED=true

# ----- 瓶颈检测配置 -----
# 瓶颈检测阈值 (极限测试用)
BOTTLENECK_CPU_THRESHOLD=85               # CPU使用率超过85%视为瓶颈
BOTTLENECK_MEMORY_THRESHOLD=90            # 内存使用率超过90%视为瓶颈
# EBS 瓶颈检测阈值 (用于瓶颈检测系统)
BOTTLENECK_EBS_UTIL_THRESHOLD=90          # EBS利用率超过90%视为瓶颈
BOTTLENECK_EBS_LATENCY_THRESHOLD=50       # EBS延迟超过50ms视为瓶颈
BOTTLENECK_NETWORK_THRESHOLD=80           # 网络利用率超过80%视为瓶颈
BOTTLENECK_ERROR_RATE_THRESHOLD=5         # 错误率超过5%视为瓶颈
BOTTLENECK_EBS_IOPS_THRESHOLD=90          # EBS 的 IOPS 利用率超过90%视为瓶颈
BOTTLENECK_EBS_THROUGHPUT_THRESHOLD=90    # EBS 的 Throughput 利用率超过90%视为瓶颈

# 多层次监控阈值说明:
# - ebs_bottleneck_detector.sh (实时瓶颈检测):
#   * HIGH级别: 使用上述基准阈值 (90%, 50ms)
#   * CRITICAL级别: 基准阈值 + 5% (95%) 或 基准阈值 * 2 (100ms)
# - ebs_analyzer.sh (离线性能分析):
#   * WARNING级别: 利用率 = BOTTLENECK_EBS_UTIL_THRESHOLD * 0.8 (72%)
#   * WARNING级别: 延迟 = BOTTLENECK_EBS_LATENCY_THRESHOLD * 0.4 (20ms)
# 
# 注意: EBS性能分析器(ebs_analyzer.sh)使用计算方式避免变量膨胀:
# 利用率警告级别 = BOTTLENECK_EBS_UTIL_THRESHOLD * 0.8 (90% * 0.8 = 72%)
# 延迟警告级别 = BOTTLENECK_EBS_LATENCY_THRESHOLD * 0.4 (50ms * 0.4 = 20ms)


# 瓶颈检测连续次数 (避免偶发性波动)
BOTTLENECK_CONSECUTIVE_COUNT=3      # 连续3次检测到瓶颈才停止

# 瓶颈分析时间窗口配置
BOTTLENECK_ANALYSIS_WINDOW=30       # 瓶颈时间点前后分析窗口 (秒)

# ----- 性能监控配置 -----
# 性能监控开关 (true/false) - 启用后会监控监控系统本身的性能影响
PERFORMANCE_MONITORING_ENABLED=${PERFORMANCE_MONITORING_ENABLED:-true}

# 性能阈值配置
MAX_COLLECTION_TIME_MS=${MAX_COLLECTION_TIME_MS:-1000}     # 最大数据收集时间 (毫秒)

# 错误处理阈值
MAX_CONSECUTIVE_ERRORS=${MAX_CONSECUTIVE_ERRORS:-5}        # 最大连续错误次数

# QPS测试成功率和延迟阈值
SUCCESS_RATE_THRESHOLD=95    # 成功率阈值 (%)
MAX_LATENCY_THRESHOLD=1000   # 最大延迟阈值 (ms)

# ----- Block Node Height 监控配置 -----
# 区块高度差异阈值，触发警告
BLOCK_HEIGHT_DIFF_THRESHOLD=50
# 区块高度时间阈值 (秒)，触发警告
BLOCK_HEIGHT_TIME_THRESHOLD=300
# 区块高度监控频率 (每秒监控次数)
BLOCK_HEIGHT_MONITOR_RATE=1

# ----- 日志输出配置 -----
LOG_CONSOLE=${LOG_CONSOLE:-true}       # 控制台输出
LOG_FILE=${LOG_FILE:-true}             # 文件输出

# 导出内部配置变量
export CONFIG_LOADED
export BOTTLENECK_CPU_THRESHOLD BOTTLENECK_MEMORY_THRESHOLD BOTTLENECK_EBS_UTIL_THRESHOLD
export BOTTLENECK_EBS_LATENCY_THRESHOLD BOTTLENECK_NETWORK_THRESHOLD BOTTLENECK_ERROR_RATE_THRESHOLD BOTTLENECK_EBS_IOPS_THRESHOLD BOTTLENECK_EBS_THROUGHPUT_THRESHOLD
export BOTTLENECK_CONSECUTIVE_COUNT BOTTLENECK_ANALYSIS_WINDOW
export PERFORMANCE_MONITORING_ENABLED MAX_COLLECTION_TIME_MS MAX_CONSECUTIVE_ERRORS
export SUCCESS_RATE_THRESHOLD MAX_LATENCY_THRESHOLD
export BLOCK_HEIGHT_DIFF_THRESHOLD BLOCK_HEIGHT_TIME_THRESHOLD BLOCK_HEIGHT_MONITOR_RATE
export LOG_CONSOLE LOG_FILE