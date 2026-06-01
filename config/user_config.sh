#!/bin/bash
# =====================================================================
# Blockchain Node Benchmark Framework - User Configuration Layer
# =====================================================================
# Target users: All users of the framework
# Configuration content: RPC connection, test parameters, Disk devices, basic monitoring configuration
# Modification frequency: Frequently modified
# =====================================================================

# ----- Cloud Provider Configuration -----
# 云平台: "auto" 自动探测(metadata) | "aws" | "gcp" | "other" 强制指定.
# auto 时由 config/cloud_provider.sh detect_platform() 探测; 探测不准可显式指定.
CLOUD_PROVIDER="${CLOUD_PROVIDER:-auto}"

# ----- Disk Device Configuration -----
# DATA device (LEDGER data storage)
LEDGER_DEVICE="sda"
# ACCOUNTS device (optional, for account data storage)
ACCOUNTS_DEVICE=""

# Use unified naming convention {logical_name}_{device_name}_{metric}
# DATA device uses data prefix, ACCOUNTS device uses accounts prefix
# Data volume configuration
# DATA_VOL_TYPE 选项随云平台不同 (config/providers/<provider>.sh get_disk_type_options):
#   AWS:   "gp3" | "io2" | "instance-store"
#   GCP:   "pd-standard" | "pd-balanced" | "pd-ssd" | "pd-extreme" |
#          "hyperdisk-balanced" | "hyperdisk-extreme" | "hyperdisk-throughput" | "local-ssd"
#   GCP Provisioned 型盘 (pd-extreme / hyperdisk-*) 的 IOPS+Throughput 独立购买,
#   sizing 用 max(read+write, total) 兜底 (见 analysis-notes/aws-gcp-io-counting-rules-verified.md)。
DATA_VOL_TYPE="io2"                    # 按上面 CLOUD_PROVIDER 选对应云的盘类型
DATA_VOL_SIZE="2000"                   # Current required data size to keep both snapshot archive and unarchived version of it
DATA_VOL_MAX_IOPS="30000"              # Max IOPS for Disk volumes (REQUIRED for "instance-store"); GCP Provisioned 盘=购买的 IOPS 配额
DATA_VOL_MAX_THROUGHPUT="700"          # Max throughput in MiB/s (REQUIRED for "instance-store", auto-calculated for AWS "io2"; GCP Provisioned 盘=购买的 throughput 配额)
# Accounts volume configuration (optional)
ACCOUNTS_VOL_TYPE="io2"                # 同 DATA_VOL_TYPE, 按 CLOUD_PROVIDER 选对应云盘类型
ACCOUNTS_VOL_SIZE="500"                # Current required data size to keep both snapshot archive and unarchived version of it
ACCOUNTS_VOL_MAX_IOPS="30000"          # Max IOPS for Disk volumes (REQUIRED for "instance-store")
ACCOUNTS_VOL_MAX_THROUGHPUT="700"      # Max throughput in MiB/s (REQUIRED for "instance-store", auto-calculated for AWS "io2")

# ----- Network Monitoring Configuration -----
# EC2 instance network bandwidth configuration (unit: Gbps) - User must set according to EC2 instance type
NETWORK_MAX_BANDWIDTH_GBPS=25       # Maximum network bandwidth (unit: Gbps) - User must set according to EC2 instance type

# ENA network limitation monitoring configuration
ENA_MONITOR_ENABLED=true

# ----- Monitoring Configuration -----
# Unified monitoring interval (seconds) - All monitoring tasks use the same interval
MONITOR_INTERVAL=5              # Unified monitoring interval, applicable to system resources, blockchain node, and monitoring overhead statistics
DISK_MONITOR_RATE=1            # Disk separate monitoring frequency

# ----- QPS Benchmark Configuration -----
# Quick benchmark mode (verify basic QPS capability)
QUICK_INITIAL_QPS=1000
QUICK_MAX_QPS=1500
QUICK_QPS_STEP=500
QUICK_DURATION=60   # Test 1 minute per QPS level (avoid resource issues from long-running tests)

# Standard benchmark mode (standard performance testing)
STANDARD_INITIAL_QPS=2000
STANDARD_MAX_QPS=50000
STANDARD_QPS_STEP=500
STANDARD_DURATION=600

# Intensive benchmark mode (automatically find system bottlenecks)
INTENSIVE_INITIAL_QPS=50000
INTENSIVE_MAX_QPS=9999999      # No practical upper limit, until bottleneck detected
INTENSIVE_QPS_STEP=250
INTENSIVE_DURATION=600
INTENSIVE_AUTO_STOP=true      # Enable automatic bottleneck detection stop

# Benchmark interval configuration
QPS_COOLDOWN=30      # Cooldown time between QPS levels (seconds)
QPS_WARMUP_DURATION=60  # Warmup time (seconds)

# ----- Disk io2 Type Automatic Throughput Calculation -----
# 注意: io2 是 AWS EBS 专属盘型, calculate_io2_throughput 用 AWS io2 Block Express
# 的 0.256 ratio 公式自动算 throughput。GCP 盘型 (pd-*/hyperdisk-*) VOL_TYPE 不等于
# "io2", 天然跳过此函数, DATA_VOL_MAX_THROUGHPUT 保持用户手配值 (GCP Provisioned 盘的
# IOPS/Throughput 是独立购买配额, 不存在 AWS io2 那种按 IOPS 自动推算 throughput 的关系)。
# => 本函数对 GCP/other 是 no-op, provider-aware 由 VOL_TYPE 取值天然隔离, 无需显式分支。
configure_io2_volumes() {
    echo "🔧 Checking Disk io2 type configuration..." >&2

    # Load Disk converter (if needed)
    if [[ "$DATA_VOL_TYPE" == "io2" || "$ACCOUNTS_VOL_TYPE" == "io2" ]]; then
        if [[ -f "${CONFIG_DIR}/../utils/disk_converter.sh" ]]; then
            source "${CONFIG_DIR}/../utils/disk_converter.sh"
            echo "✅ Disk converter loaded successfully" >&2
        else
            echo "❌ Error: disk_converter.sh does not exist, cannot process io2 type" >&2
            echo "   Path: ${CONFIG_DIR}/../utils/disk_converter.sh" >&2
            exit 1
        fi
    fi

    # Process DATA volume io2 automatic calculation
    if [[ "$DATA_VOL_TYPE" == "io2" && -n "$DATA_VOL_MAX_IOPS" ]]; then
        local original_throughput="$DATA_VOL_MAX_THROUGHPUT"
        local auto_throughput

        if auto_throughput=$(calculate_io2_throughput "$DATA_VOL_MAX_IOPS" 2>/dev/null); then
            DATA_VOL_MAX_THROUGHPUT="$auto_throughput"
            echo "ℹ️  DATA volume io2 auto-calculated: $original_throughput → $auto_throughput MiB/s (based on $DATA_VOL_MAX_IOPS IOPS)" >&2
        else
            echo "❌ Error: DATA volume io2 throughput calculation failed" >&2
            exit 1
        fi
    fi

    # Process ACCOUNTS volume io2 automatic calculation
    if [[ "$ACCOUNTS_VOL_TYPE" == "io2" && -n "$ACCOUNTS_VOL_MAX_IOPS" && -n "$ACCOUNTS_DEVICE" ]]; then
        local original_throughput="$ACCOUNTS_VOL_MAX_THROUGHPUT"
        local auto_throughput

        if auto_throughput=$(calculate_io2_throughput "$ACCOUNTS_VOL_MAX_IOPS" 2>/dev/null); then
            ACCOUNTS_VOL_MAX_THROUGHPUT="$auto_throughput"
            echo "ℹ️  ACCOUNTS volume io2 auto-calculated: $original_throughput → $auto_throughput MiB/s (based on $ACCOUNTS_VOL_MAX_IOPS IOPS)" >&2
        else
            echo "❌ Error: ACCOUNTS volume io2 throughput calculation failed" >&2
            exit 1
        fi
    fi
}

configure_io2_volumes

# Export user configuration variables
export LEDGER_DEVICE ACCOUNTS_DEVICE
export DATA_VOL_TYPE DATA_VOL_SIZE DATA_VOL_MAX_IOPS DATA_VOL_MAX_THROUGHPUT
export ACCOUNTS_VOL_TYPE ACCOUNTS_VOL_SIZE ACCOUNTS_VOL_MAX_IOPS ACCOUNTS_VOL_MAX_THROUGHPUT
export NETWORK_MAX_BANDWIDTH_GBPS ENA_MONITOR_ENABLED MONITOR_INTERVAL DISK_MONITOR_RATE
export QUICK_INITIAL_QPS QUICK_MAX_QPS QUICK_QPS_STEP QUICK_DURATION
export STANDARD_INITIAL_QPS STANDARD_MAX_QPS STANDARD_QPS_STEP STANDARD_DURATION
export INTENSIVE_INITIAL_QPS INTENSIVE_MAX_QPS INTENSIVE_QPS_STEP INTENSIVE_DURATION INTENSIVE_AUTO_STOP
export QPS_COOLDOWN QPS_WARMUP_DURATION 