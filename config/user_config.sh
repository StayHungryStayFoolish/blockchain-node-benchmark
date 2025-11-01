#!/bin/bash
# =====================================================================
# Blockchain Node Benchmark Framework - User Configuration Layer
# =====================================================================
# Target users: All users of the framework
# Configuration content: RPC connection, test parameters, EBS devices, basic monitoring configuration
# Modification frequency: Frequently modified
# =====================================================================

# ----- EBS Device Configuration -----
# DATA device (LEDGER data storage)
LEDGER_DEVICE="nvme1n1"
# ACCOUNTS device (optional, for account data storage)
ACCOUNTS_DEVICE="nvme2n1"

# Use unified naming convention {logical_name}_{device_name}_{metric}
# DATA device uses data prefix, ACCOUNTS device uses accounts prefix
# Data volume configuration
DATA_VOL_TYPE="io2"                    # Options: "gp3" | "io2" | "instance-store"
DATA_VOL_SIZE="2000"                   # Current required data size to keep both snapshot archive and unarchived version of it
DATA_VOL_MAX_IOPS="30000"              # Max IOPS for EBS volumes (REQUIRED for "instance-store")
DATA_VOL_MAX_THROUGHPUT="700"          # Max throughput in MiB/s (REQUIRED for "instance-store", auto-calculated for "io2")

# Accounts volume configuration (optional)
ACCOUNTS_VOL_TYPE="io2"                # Options: "gp3" | "io2" | "instance-store"
ACCOUNTS_VOL_SIZE="500"                # Current required data size to keep both snapshot archive and unarchived version of it
ACCOUNTS_VOL_MAX_IOPS="30000"          # Max IOPS for EBS volumes (REQUIRED for "instance-store")
ACCOUNTS_VOL_MAX_THROUGHPUT="700"      # Max throughput in MiB/s (REQUIRED for "instance-store", auto-calculated for "io2")

# ----- Network Monitoring Configuration -----
# EC2 instance network bandwidth configuration (unit: Gbps) - User must set according to EC2 instance type
NETWORK_MAX_BANDWIDTH_GBPS=25       # Maximum network bandwidth (unit: Gbps) - User must set according to EC2 instance type

# ENA network limitation monitoring configuration
ENA_MONITOR_ENABLED=true

# ----- Monitoring Configuration -----
# Unified monitoring interval (seconds) - All monitoring tasks use the same interval
MONITOR_INTERVAL=5              # Unified monitoring interval, applicable to system resources, blockchain node, and monitoring overhead statistics
EBS_MONITOR_RATE=1              # EBS separate monitoring frequency

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

# ----- EBS io2 Type Automatic Throughput Calculation -----
configure_io2_volumes() {
    echo "🔧 Checking EBS io2 type configuration..." >&2

    # Load EBS converter (if needed)
    if [[ "$DATA_VOL_TYPE" == "io2" || "$ACCOUNTS_VOL_TYPE" == "io2" ]]; then
        if [[ -f "${CONFIG_DIR}/../utils/ebs_converter.sh" ]]; then
            source "${CONFIG_DIR}/../utils/ebs_converter.sh"
            echo "✅ EBS converter loaded successfully" >&2
        else
            echo "❌ Error: ebs_converter.sh does not exist, cannot process io2 type" >&2
            echo "   Path: ${CONFIG_DIR}/../utils/ebs_converter.sh" >&2
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
export NETWORK_MAX_BANDWIDTH_GBPS ENA_MONITOR_ENABLED MONITOR_INTERVAL EBS_MONITOR_RATE
export QUICK_INITIAL_QPS QUICK_MAX_QPS QUICK_QPS_STEP QUICK_DURATION
export STANDARD_INITIAL_QPS STANDARD_MAX_QPS STANDARD_QPS_STEP STANDARD_DURATION
export INTENSIVE_INITIAL_QPS INTENSIVE_MAX_QPS INTENSIVE_QPS_STEP INTENSIVE_DURATION INTENSIVE_AUTO_STOP
export QPS_COOLDOWN QPS_WARMUP_DURATION 