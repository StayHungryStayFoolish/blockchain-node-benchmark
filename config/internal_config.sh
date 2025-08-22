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

# 配置初始化标记文件
CONFIG_INIT_FLAG_FILE=""  # 将在路径检测完成后设置

# ----- 瓶颈检测配置 -----
# 瓶颈检测阈值 (极限测试用)
BOTTLENECK_CPU_THRESHOLD=85               # CPU使用率超过85%视为瓶颈
BOTTLENECK_MEMORY_THRESHOLD=90            # 内存使用率超过90%视为瓶颈
BOTTLENECK_EBS_UTIL_THRESHOLD=90          # EBS利用率超过90%视为瓶颈
BOTTLENECK_EBS_LATENCY_THRESHOLD=50       # EBS延迟超过50ms视为瓶颈
BOTTLENECK_NETWORK_THRESHOLD=80           # 网络利用率超过80%视为瓶颈
BOTTLENECK_ERROR_RATE_THRESHOLD=5         # 错误率超过5%视为瓶颈
BOTTLENECK_EBS_IOPS_THRESHOLD=90          # EBS 的 IOPS 利用率超过90%视为瓶颈
BOTTLENECK_EBS_THROUGHPUT_THRESHOLD=90    # EBS 的 Throughput 利用率超过90%视为瓶颈


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

# ----- Slot 监控配置 -----
# Slot 差异阈值
SLOT_DIFF_THRESHOLD=500
# Slot 时间阈值 (秒)
SLOT_TIME_THRESHOLD=600
# Slot 监控间隔 (秒)
SLOT_MONITOR_INTERVAL=10

# ----- 日志输出配置 -----
LOG_CONSOLE=${LOG_CONSOLE:-true}       # 控制台输出
LOG_FILE=${LOG_FILE:-true}             # 文件输出

# 导出内部配置变量
export CONFIG_LOADED CONFIG_INIT_FLAG_FILE
export BOTTLENECK_CPU_THRESHOLD BOTTLENECK_MEMORY_THRESHOLD BOTTLENECK_EBS_UTIL_THRESHOLD
export BOTTLENECK_EBS_LATENCY_THRESHOLD BOTTLENECK_NETWORK_THRESHOLD BOTTLENECK_ERROR_RATE_THRESHOLD BOTTLENECK_EBS_IOPS_THRESHOLD BOTTLENECK_EBS_THROUGHPUT_THRESHOLD
export BOTTLENECK_CONSECUTIVE_COUNT BOTTLENECK_ANALYSIS_WINDOW
export PERFORMANCE_MONITORING_ENABLED MAX_COLLECTION_TIME_MS MAX_CONSECUTIVE_ERRORS
export SUCCESS_RATE_THRESHOLD MAX_LATENCY_THRESHOLD
export SLOT_DIFF_THRESHOLD SLOT_TIME_THRESHOLD SLOT_MONITOR_INTERVAL
export LOG_CONSOLE LOG_FILE