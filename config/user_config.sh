#!/bin/bash
# =====================================================================
# Solana QPS 测试框架 - 用户配置层
# =====================================================================
# 版本: 3.0 - 分层配置架构
# 目标用户: 所有使用框架的用户
# 配置内容: RPC连接、测试参数、EBS设备、监控基础配置
# 修改频率: 经常修改
# =====================================================================

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

# ----- 网络监控配置 -----
# EC2实例网络带宽配置 (单位: Gbps) - 用户必须根据EC2实例类型设置
NETWORK_MAX_BANDWIDTH_GBPS=25       # 网络最大带宽 (单位: Gbps) - 用户必须根据EC2实例类型设置

# ENA网络限制监控配置
ENA_MONITOR_ENABLED=true

# ----- 监控配置 -----
# 统一监控间隔 (秒) - 所有监控任务使用相同间隔
MONITOR_INTERVAL=5              # 统一监控间隔，适用于系统资源、区块链节点和监控开销统计

# ----- QPS 基准测试配置 -----
# 快速基准测试模式 (验证基本QPS能力)
QUICK_INITIAL_QPS=1000
QUICK_MAX_QPS=1500
QUICK_QPS_STEP=500
QUICK_DURATION=60   # 每个QPS级别测试1分钟 (避免长时间测试导致的资源问题)

# 标准基准测试模式 (标准性能测试)
STANDARD_INITIAL_QPS=1000
STANDARD_MAX_QPS=5000
STANDARD_QPS_STEP=500
STANDARD_DURATION=600

# 深度基准测试模式 (自动寻找系统瓶颈)
INTENSIVE_INITIAL_QPS=1000
INTENSIVE_MAX_QPS=999999      # 无实际上限，直到检测到瓶颈
INTENSIVE_QPS_STEP=250
INTENSIVE_DURATION=600
INTENSIVE_AUTO_STOP=true      # 启用自动瓶颈检测停止

# 基准测试间隔配置
QPS_COOLDOWN=30      # QPS级别间的冷却时间 (秒)
QPS_WARMUP_DURATION=60  # 预热时间 (秒)

# 导出用户配置变量
export LEDGER_DEVICE ACCOUNTS_DEVICE
export DATA_VOL_TYPE DATA_VOL_SIZE DATA_VOL_MAX_IOPS DATA_VOL_MAX_THROUGHPUT
export ACCOUNTS_VOL_TYPE ACCOUNTS_VOL_SIZE ACCOUNTS_VOL_MAX_IOPS ACCOUNTS_VOL_MAX_THROUGHPUT
export NETWORK_MAX_BANDWIDTH_GBPS ENA_MONITOR_ENABLED MONITOR_INTERVAL
export QUICK_INITIAL_QPS QUICK_MAX_QPS QUICK_QPS_STEP QUICK_DURATION
export STANDARD_INITIAL_QPS STANDARD_MAX_QPS STANDARD_QPS_STEP STANDARD_DURATION
export INTENSIVE_INITIAL_QPS INTENSIVE_MAX_QPS INTENSIVE_QPS_STEP INTENSIVE_DURATION INTENSIVE_AUTO_STOP
export QPS_COOLDOWN QPS_WARMUP_DURATION 