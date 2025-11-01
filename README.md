# Blockchain Node QPS Performance Benchmark Framework

[English](README.md) | [中文](README_ZH.md)

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Commercial License](https://img.shields.io/badge/License-Commercial-green.svg)](LICENSE.COMMERCIAL)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Shell Script](https://img.shields.io/badge/shell-bash-green.svg)](https://www.gnu.org/software/bash/)

A professional multi blockchain node performance benchmarking framework with comprehensive QPS testing, real-time monitoring, intelligent bottleneck detection, and advanced visualization reporting.

## 🎯 Key Features

- **[Multi-Mode QPS Testing](#-testing-modes)**: Quick (15+min), Standard (90+min), and Intensive (8+hr) testing modes
- **Cross-Platform Compatibility**: Supports 8 mainstream blockchain nodes (Solana, Ethereum, BSC, Base, Polygon, Scroll, Starknet, Sui) on AWS, other clouds, IDC, or local Linux environments
- **Real Transaction Data Testing**: Fetches active accounts from your blockchain node and generates test targets using single or mixed RPC methods
- **[Multi-Layered Performance Monitoring](#-monitoring-metrics)**: Professional monitoring system with 4 specialized data streams
  - Unified metrics (79 fields): CPU, Memory, EBS, Network, ENA, Block Height, QPS
  - Monitoring overhead tracking (20 fields): Self-monitoring and impact analysis
  - ENA deep monitoring (15 fields): AWS-specific network performance analysis
  - Blockchain health tracking (7 fields): Node sync status and data loss detection
- **Dual Bottleneck Monitoring Mechanism**:
  - **Real-time Detection**: 8-dimensional monitoring with 5-scenario judgment logic to avoid false positives
    - Resource bottleneck + Node healthy → False positive (reset counter)
    - RPC performance violation (success rate < 95% OR latency > 1000ms) → True bottleneck (necessary condition)
    - Any bottleneck + Node unhealthy → True bottleneck (3 consecutive times)
    - Node persistently unhealthy alone → Node failure (stop immediately)
    - All normal → Continue testing
  - **Offline Analysis**: Multi-dimensional deep analysis after test completion
    - Time window analysis (±30 seconds around bottleneck) for focused root cause investigation
    - Performance cliff analysis to identify QPS degradation patterns
    - EBS performance deep dive with AWS baseline comparison
    - CPU-EBS correlation analysis for resource bottleneck identification
    - RPC method performance profiling and optimization recommendations
- **AWS Deep Integration**: EBS performance baselines, ENA network monitoring
- **Professional Visualization**: [32 professional charts](#-generated-reports) and [comprehensive HTML reports](./docs/image/performance_report_en_20251030_171541.html)



## ⚡ Quick Configuration

**Before running the framework**, you must configure the following parameters:

### Required Configuration (in `config/config_loader.sh`)

```bash
# 1. RPC Endpoint (Required)
LOCAL_RPC_URL="http://localhost:8899"  # Your blockchain node RPC endpoint

# 2. Blockchain Type (Required)
BLOCKCHAIN_NODE="Solana"  # Supported: Solana, Ethereum, BSC, Base, Polygon, Scroll, Starknet, Sui

# 3. Blockchain Process Names (Required for monitoring)
BLOCKCHAIN_PROCESS_NAMES=(
    "agave-validator"    # Your actual blockchain node process name
    "solana-validator"   # Add all possible process names
    "validator"
)
# Check your process name with: ps aux | grep -i validator
```

### EBS Configuration (in `config/user_config.sh`)

```bash
# 4. DATA Device Configuration (Required)
LEDGER_DEVICE="nvme1n1"              # DATA device name (check with 'lsblk')
DATA_VOL_TYPE="io2"                  # Options: "gp3" | "io2" | "instance-store"
DATA_VOL_MAX_IOPS="30000"            # Your EBS volume's provisioned IOPS
DATA_VOL_MAX_THROUGHPUT="700"        # Your EBS volume's throughput (MiB/s)

# 5. ACCOUNTS Device (Optional, but recommended for complete monitoring)
ACCOUNTS_DEVICE="nvme2n1"            # ACCOUNTS device name
ACCOUNTS_VOL_TYPE="io2"              # Options: "gp3" | "io2" | "instance-store"
ACCOUNTS_VOL_MAX_IOPS="30000"        # ACCOUNTS volume's provisioned IOPS
ACCOUNTS_VOL_MAX_THROUGHPUT="700"    # ACCOUNTS volume's throughput (MiB/s)

# 6. Network Configuration (Required for AWS environments)
NETWORK_MAX_BANDWIDTH_GBPS=25        # Your instance's network bandwidth (Gbps)
```

**Quick Configuration Check:**
```bash
# Verify your blockchain process name
ps aux | grep -i validator
ps aux | grep -i agave
ps aux | grep -i solana

# Verify your EBS devices
lsblk

# Check your EBS volume configuration in AWS Console:
# EC2 → Volumes → Select your volume → Details tab
# - IOPS: Provisioned IOPS value
# - Throughput: Provisioned throughput value

# Check your instance network bandwidth:
# EC2 → Instance Types → Search your instance type → Networking
```

**Configuration File Locations:**
- `config/config_loader.sh` - RPC endpoint, blockchain type, process names
- `config/user_config.sh` - EBS devices, network bandwidth, monitoring intervals

**Note**: If you don't configure these parameters correctly, the framework will use default values which may not match your actual hardware, leading to inaccurate performance analysis.



## 🚀 Quick Start

### Prerequisites

```bash
# Install Python and virtual environment support
sudo apt-get install python3 python3-venv

# Create virtual environment
python3 -m venv node-env

# Activate virtual environment
source node-env/bin/activate

# Check Python version (requires Python 3.8+)
python3 --version

# Install Python dependencies
pip3 install -r requirements.txt

# Verify system tools
which vegeta    # QPS testing tool
which iostat    # I/O monitoring tool
which mpstat    # CPU monitoring tool
which sar       # Network monitoring tool
```

### Basic Usage

```bash
# Quick test (15+ minutes) - can run directly
./blockchain_node_benchmark.sh --quick

# Standard test (90+ minutes) - recommended to use screen
screen -S benchmark_$(date +%m%d_%H%M)
./blockchain_node_benchmark.sh --standard
# ⚠️ MUST press Ctrl+a then d to detach before closing SSH!

# Intensive test (up to 8 hours) - MUST use screen/tmux
screen -S benchmark_$(date +%m%d_%H%M)
./blockchain_node_benchmark.sh --intensive
# ⚠️ MUST press Ctrl+a then d to detach before closing SSH!
```

**⚠️ Critical**: For tests longer than 30 minutes, you **MUST**:
1. Use `screen` or `tmux` 
2. **Detach the session** (Ctrl+a, then d for screen) before closing SSH
3. Otherwise the test will stop when SSH disconnects!

See [Best Practices](#best-practices-for-long-running-tests) for detailed instructions.

### Custom Testing

```bash
# Custom intensive test with specific parameters
./blockchain_node_benchmark.sh --intensive \
    --initial-qps 1000 \
    --max-qps 10000 \
    --step-qps 500 \
    --duration 300 \
    --mixed  # Use mixed RPC method testing
```



## 📦 System Architecture

```
blockchain-node-benchmark/
├── 🎯 Core Execution Layer
│   ├── blockchain_node_benchmark.sh    # Main entry script
│   ├── master_qps_executor.sh          # QPS testing engine
│   └── common_functions.sh             # Shared function library
├── ⚙️ Configuration Management
│   ├── config_loader.sh                # Configuration loader
│   └── system_config.sh                # System configuration
├── 📊 Monitoring Data Layer
│   ├── unified_monitor.sh              # Unified monitor
│   ├── bottleneck_detector.sh          # Bottleneck detector
│   └── monitoring_coordinator.sh       # Monitoring coordinator
├── 🔬 Analysis Processing Layer
│   ├── comprehensive_analysis.py       # Comprehensive analyzer
│   ├── qps_analyzer.py                 # QPS analyzer
│   └── rpc_deep_analyzer.py            # RPC deep analyzer
├── 📈 Visualization Layer
│   ├── report_generator.py             # HTML report generator
│   ├── performance_visualizer.py       # Performance visualization engine
│   └── advanced_chart_generator.py     # Advanced chart generator
└── 🛠️ Tools & Utilities
    ├── benchmark_archiver.sh           # Test result archiver
    ├── ebs_bottleneck_detector.sh      # EBS bottleneck detector
    └── target_generator.sh             # Test target generator
```



## 📚 Documentation

Comprehensive documentation is available in the `docs/` directory:

### Core Documentation

#### [Architecture Overview](./docs/architecture-overview.md)
- 4-layer modular architecture design
- Component interaction and data flow
- 32 professional charts breakdown
- System integration points

#### [Data Architecture](./docs/data-architecture.md)
- Complete data file structure and field definitions
- 79-field performance data CSV format
- 20-field monitoring overhead CSV format
- Data flow architecture and file naming conventions
- JSON format specifications for test results

#### [Configuration Guide](./docs/configuration-guide.md)
- 4-layer configuration system (User/System/Internal/Dynamic)
- EBS volume configuration (gp3/io2/instance-store)
- Network and ENA settings
- Blockchain-specific parameters

#### [Monitoring Mechanism](./docs/monitoring-mechanism.md)
- Dual-layer monitoring architecture
- 79 performance metrics collection (updated)
- Self-monitoring and overhead analysis
- AWS standard conversion formulas

#### [Blockchain Testing Features](./docs/blockchain-testing-features.md)
- Single vs Mixed RPC testing modes
- Multi-blockchain support (Solana/Ethereum/BSC/Base/Polygon/Scroll/Starknet/Sui)
- RPC method configuration
- Real transaction data testing



## ⚙️ Configuration

### Basic Configuration

**RPC and Blockchain Settings** (`config/config_loader.sh`):
```bash
LOCAL_RPC_URL="http://localhost:8899"
BLOCKCHAIN_NODE="Solana"
BLOCKCHAIN_PROCESS_NAMES=(
    "agave-validator"
    "solana-validator"
    "validator"
)
```

**EBS Device Configuration** (`config/user_config.sh`):
```bash
# DATA device (required)
LEDGER_DEVICE="nvme1n1"
DATA_VOL_TYPE="io2"                  # io2/gp3/instance-store
DATA_VOL_MAX_IOPS="30000"
DATA_VOL_MAX_THROUGHPUT="700"        # MiB/s

# ACCOUNTS device (optional)
ACCOUNTS_DEVICE="nvme2n1"
ACCOUNTS_VOL_TYPE="io2"              # io2/gp3/instance-store
ACCOUNTS_VOL_MAX_IOPS="30000"
ACCOUNTS_VOL_MAX_THROUGHPUT="700"    # MiB/s

# Network configuration
NETWORK_MAX_BANDWIDTH_GBPS=25        # Gbps
```

**Note:** ACCOUNTS device is optional. If not configured, the framework will only monitor the DATA device.

### Advanced Configuration

**Bottleneck Detection Thresholds** (`config/internal_config.sh`):
```bash
BOTTLENECK_CPU_THRESHOLD=85
BOTTLENECK_MEMORY_THRESHOLD=90
BOTTLENECK_EBS_UTIL_THRESHOLD=90
BOTTLENECK_EBS_LATENCY_THRESHOLD=50
NETWORK_UTILIZATION_THRESHOLD=80
```

**Monitoring Intervals** (`config/user_config.sh`):
```bash
MONITOR_INTERVAL=5              # Default monitoring interval (seconds)
HIGH_FREQ_INTERVAL=1            # High-frequency monitoring interval
ULTRA_HIGH_FREQ_INTERVAL=0.5    # Ultra-high-frequency monitoring interval
```



## 📊 Testing Modes

| Mode | Duration      | QPS Range       | Step Size | Use Case |
|------|---------------|-----------------|-----------|----------|
| **Quick** | 15+ minutes   | 1000-3000       | 500 QPS | Basic performance verification |
| **Standard** | 90+ minutes   | 20000-50000     | 500 QPS | Comprehensive performance evaluation |
| **Intensive** | Up to 8 hours | 50000-unlimited | 250 QPS | Intelligent bottleneck detection |



## 🔍 Monitoring Metrics

### System Metrics (73-79 total)
- **Timestamp**: Unified timestamp (1 field)
- **CPU**: Usage, I/O wait, system calls (6 fields)
- **Memory**: Usage, available memory, cache (3 fields)
- **EBS Storage**: IOPS, throughput, latency, utilization (21 fields per device, 42 fields for 2 devices)
- **Network**: Bandwidth utilization, PPS, connections (10 fields)
- **ENA Network**: Allowance exceeded, bandwidth limits (6 fields, AWS only)
- **Monitoring Overhead**: System impact metrics (2 fields)
- **Block Height**: Local vs mainnet sync status (6 fields)
- **QPS Performance**: Current QPS, latency, availability (3 fields)

**Total**: 79 fields (with ENA on AWS) or 73 fields (without ENA on non-AWS)

### Detailed Monitoring Data Files

The framework generates multiple specialized CSV files for fine-grained analysis:

**1. Performance Metrics** (`performance_YYYYMMDD_HHMMSS.csv` - 79 fields)
- Unified performance data combining all system metrics
- Real-time collection at configurable intervals (default 5s)
- Used for comprehensive performance analysis and correlation studies

**2. Monitoring Overhead** (`monitoring_overhead_YYYYMMDD_HHMMSS.csv` - 20 fields)
- Monitoring system resource consumption (CPU, memory, process count)
- Blockchain node resource consumption
- System-level resource statistics (cores, memory, disk, cache, buffers)
- Used for monitoring impact analysis and overhead optimization

**3. ENA Network Details** (`ena_network_YYYYMMDD_HHMMSS.csv` - 15 fields, AWS only)
- Network interface statistics (rx/tx bytes, packets)
- ENA allowance tracking (bandwidth in/out, PPS, connection tracking, link-local)
- Network limitation status (network_limited, pps_limited, bandwidth_limited)
- Used for AWS ENA-specific bottleneck detection and network performance analysis

**4. Block Height Monitor** (`block_height_monitor_YYYYMMDD_HHMMSS.csv` - 7 fields)
- Local and mainnet block height tracking
- Block height difference and sync status
- Node health indicators (local_health, mainnet_health)
- Data loss detection flag
- Used for blockchain node sync analysis and health monitoring

### Bottleneck Detection (8 Dimensions)
1. **CPU Bottleneck**: Threshold 85%
2. **Memory Bottleneck**: Threshold 90%
3. **EBS Bottleneck**: IOPS/Throughput/Utilization > 90% baseline
4. **Network Bottleneck**: Bandwidth/PPS utilization > 80%
5. **ENA Bottleneck**: Allowance limits exceeded
6. **RPC Success Rate**: < 95% (Necessary Condition)
7. **RPC Latency**: P99 > 1000ms (Necessary Condition)
8. **RPC Error Rate**: > 5%



## 📈 Generated Reports

### Sample Reports

View complete sample reports generated from real test data (Standard mode, 90+ minutes):

- [HTML Report](./docs/image/performance_report_en_20251030_171541.html) - Interactive HTML with all charts
- [PDF Report](./docs/image/performance_report_en_20251030_171541.pdf) - Printable PDF version

### 32 Professional Charts (Complete Framework Coverage)

**Advanced Analysis Charts (9 charts)**:

1. `pearson_correlation_analysis.png` - Pearson Correlation Analysis
2. `linear_regression_analysis.png` - Linear Regression Analysis
3. `negative_correlation_analysis.png` - Negative Correlation Analysis
4. `ena_limitation_trends.png` - ENA Limitation Trends
5. `ena_connection_capacity.png` - ENA Connection Capacity
6. `ena_comprehensive_status.png` - ENA Comprehensive Status
7. `comprehensive_correlation_matrix.png` - Comprehensive Correlation Matrix
8. `performance_trend_analysis.png` - Performance Trend Analysis
9. `performance_correlation_heatmap.png` - Performance Correlation Heatmap

**EBS Professional Charts (7 charts)**:

10. `ebs_aws_capacity_planning.png` - AWS Capacity Planning Analysis
11. `ebs_iostat_performance.png` - Iostat Performance Analysis
12. `ebs_bottleneck_correlation.png` - Bottleneck Correlation Analysis
13. `ebs_performance_overview.png` - EBS Performance Overview
14. `ebs_bottleneck_analysis.png` - EBS Bottleneck Analysis
15. `ebs_aws_standard_comparison.png` - EBS AWS Standard Comparison
16. `ebs_time_series_analysis.png` - EBS Time Series Analysis

**Core Performance Charts (11 charts)**:

17. `performance_overview.png` - Performance Overview
18. `cpu_ebs_correlation_visualization.png` - CPU-EBS Correlation Analysis
19. `device_performance_comparison.png` - Device Performance Comparison
20. `await_threshold_analysis.png` - I/O Latency Threshold Analysis
21. `monitoring_overhead_analysis.png` - Monitoring Overhead Analysis
22. `qps_trend_analysis.png` - QPS Trend Analysis
23. `resource_efficiency_analysis.png` - Resource Efficiency Analysis
24. `bottleneck_identification.png` - Bottleneck Identification
25. `block_height_sync_chart.png` - Block Height Sync Chart
26. `smoothed_trend_analysis.png` - Smoothed Trend Analysis
27. `util_threshold_analysis.png` - Utilization Threshold Analysis

**Additional Analysis Charts (5 charts)**:

28. `resource_distribution_chart.png` - Resource Distribution Chart
29. `monitoring_impact_chart.png` - Monitoring Impact Analysis
30. `comprehensive_analysis_charts.png` - Comprehensive Analysis Charts
31. `performance_cliff_analysis.png` - Performance Cliff Analysis
32. `qps_performance_analysis.png` - QPS Performance Analysis

### HTML Report Sections
- **System-Level Bottleneck Analysis**: Bottleneck detection results and optimization recommendations
- **Performance Summary**: Test overview and key performance metrics
- **Configuration Status Check**: System configuration validation
- **Blockchain Node Sync Analysis**: Block height monitoring and sync status
- **EBS Performance Analysis Results**: Storage performance deep dive with AWS baseline comparison
- **Performance Chart Gallery**: All 32 professional visualization charts organized by category
- **Monitoring Overhead Analysis**: Comprehensive monitoring system impact analysis
- **CPU-EBS Correlation Analysis**: Resource correlation and bottleneck identification



## 📋 Usage Examples

### Example 1: Standard Performance Test
```bash
# Run standard test
./blockchain_node_benchmark.sh --standard

# View results
ls reports/
# comprehensive_analysis_report.html
# performance_overview.png
# cpu_ebs_correlation_visualization.png
# ... (other chart files)
```

### Example 2: Custom Intensive Test
```bash
# Custom intensive test with specific parameters
./blockchain_node_benchmark.sh --intensive \
    --initial-qps 2000 \
    --max-qps 15000 \
    --step-qps 1000 \
    --mixed  # Use mixed RPC method testing
```

### Example 3: Check System Status
```bash
# Check QPS testing engine status
./core/master_qps_executor.sh --status

# Check monitoring system status
./monitoring/monitoring_coordinator.sh status

# View test history
./tools/benchmark_archiver.sh --list
```



## 🚨 Troubleshooting

### Common Issues

#### 1. Vegeta Not Installed
```bash
# Ubuntu/Debian
sudo apt-get install vegeta

# CentOS/RHEL
sudo yum install vegeta

# macOS
brew install vegeta
```

#### 2. Missing System Monitoring Tools
```bash
# Install sysstat package
sudo apt-get install sysstat  # Ubuntu/Debian
sudo yum install sysstat      # CentOS/RHEL
```

#### 3. Python Dependencies Issues
```bash
# Reinstall dependencies
pip3 install --upgrade -r requirements.txt

# Check specific packages
python3 -c "import matplotlib, pandas, numpy; print('All packages OK')"
```

#### 4. Permission Issues
```bash
# Grant execution permissions
chmod +x blockchain_node_benchmark.sh
chmod +x core/master_qps_executor.sh
chmod +x monitoring/monitoring_coordinator.sh
```

### Log File Locations

All logs are stored in `blockchain-node-benchmark-result/current/logs/`:

- **QPS Test Log**: `master_qps_executor.log` - QPS test progress and results
- **Monitoring Log**: `unified_monitor.log` - System monitoring data
- **Bottleneck Detection**: `bottleneck_detector.log` - Bottleneck detection events
- **EBS Analysis**: `ebs_bottleneck_detector.log` - EBS performance analysis
- **Performance Data**: `performance_YYYYMMDD_HHMMSS.csv` - Raw performance metrics (79 fields)
- **Monitoring Overhead**: `monitoring_overhead_YYYYMMDD_HHMMSS.csv` - Monitoring system overhead (20 fields)
- **ENA Network**: `ena_network_YYYYMMDD_HHMMSS.csv` - ENA network detailed metrics (15 fields, AWS only)
- **Block Height Monitor**: `block_height_monitor_YYYYMMDD_HHMMSS.csv` - Block height sync tracking (7 fields)

### Viewing Test Progress

If your terminal disconnects during testing, you can reconnect and view progress:

```bash
# View QPS test progress in real-time
tail -f blockchain-node-benchmark-result/current/logs/master_qps_executor.log

# Check current test status
ps aux | grep vegeta | grep -v grep

# View latest performance data
tail -20 blockchain-node-benchmark-result/current/logs/performance_latest.csv

# Check if bottleneck detected
cat /dev/shm/blockchain-node-benchmark/bottleneck_status.json | jq '.'

# View completed test results
ls -lt blockchain-node-benchmark-result/current/vegeta_results/ | head -10
```

### After Test Completion

Once testing is complete, all results are archived:

```bash
# View archived results
ls -lt blockchain-node-benchmark-result/archives/

# Access specific test run
cd blockchain-node-benchmark-result/archives/run_XXX_YYYYMMDD_HHMMSS/

# View logs
cat logs/master_qps_executor.log

# View reports
open reports/performance_report_en_*.html
```

### Best Practices for Long-Running Tests

**⚠️ CRITICAL**: To prevent SSH disconnection from stopping your test, you **MUST** use one of these methods:

#### Method 1: Use screen (Recommended)

```bash
# Step 1: Create screen session with unique name
screen -S benchmark_$(date +%m%d_%H%M)
# Example: benchmark_1030_2200

# Step 2: Start test
./blockchain_node_benchmark.sh --intensive

# Step 3: ⚠️ IMPORTANT - Detach before closing SSH
# Press: Ctrl+a, then press d
# You should see: [detached from xxx.benchmark_1030_2200]

# Step 4: Now you can safely close SSH
exit

# Step 5: Reconnect anytime
# List all screen sessions
screen -ls

# Reconnect to specific session
# If shows "(Detached)" - use simple reconnect:
screen -r benchmark_1030_2200
# Or use PID:
screen -r 12345

# If shows "(Attached)" - use force reconnect:
screen -d -r 12345
# This detaches any existing connection and reconnects you
```

**Common Issues:**

```bash
# Problem: Multiple sessions with same name
screen -ls
# Shows: 13813.benchmark, 19327.benchmark, 54872.benchmark

# Solution 1: Use PID to reconnect to latest
screen -r 13813

# Solution 2: Clean up old sessions
screen -X -S 19327 quit
screen -X -S 54872 quit

# Solution 3: Kill all and start fresh
killall screen
```

**Why detach is critical**: If you close SSH without detaching, the test will stop!

#### Method 2: Use tmux

```bash
# Step 1: Create tmux session
tmux new -s benchmark

# Step 2: Start test
./blockchain_node_benchmark.sh --intensive

# Step 3: ⚠️ IMPORTANT - Detach before closing SSH
# Press: Ctrl+b, then press d

# Step 4: Reconnect anytime
tmux attach -t benchmark
```

#### Method 3: Use nohup
```
nohup ./blockchain_node_benchmark.sh --intensive > test.log 2>&1 &
# View progress: tail -f test.log
```



## 🔧 Advanced Features

### Test Result Archiving
```bash
# List historical tests
./tools/benchmark_archiver.sh --list

# Compare test results
./tools/benchmark_archiver.sh --compare run_001 run_002

# Clean up old tests
./tools/benchmark_archiver.sh --cleanup --days 30
```

### Custom Analysis
```python
# Use Python analysis components
from analysis.comprehensive_analysis import ComprehensiveAnalyzer

analyzer = ComprehensiveAnalyzer("reports")
analyzer.run_comprehensive_analysis("logs/performance_latest.csv")
```

### Batch Testing
```bash
# Run multiple test modes
for mode in quick standard intensive; do
    echo "Running $mode test..."
    ./blockchain_node_benchmark.sh --$mode
    sleep 60  # Wait for system recovery
done
```



## 🤝 Contributing

We welcome contributions! By contributing to this project, you agree to the following:

### Contributor License Agreement (CLA)

By submitting a pull request, you agree that:
- Your contributions will be licensed under both AGPL 3.0 and our Commercial License
- You grant the project maintainers the right to use your contributions in commercial versions
- You have the right to submit the contributions (no third-party IP conflicts)

### Development Environment Setup
```bash
# Clone the repository
git clone <repository-url>
cd blockchain-node-benchmark

# Install development dependencies
pip3 install -r requirements.txt

# Verify installation
python3 --version
bash --version
```

### Contribution Guidelines

1. **Fork and Branch**: Create a feature branch from `main`
2. **Code Style**: Follow PEP 8 for Python, use shellcheck for bash scripts
3. **Documentation**: Update relevant documentation
4. **Commit Messages**: Use clear, descriptive commit messages
5. **Pull Request**: Submit PR with detailed description

### Adding New Monitoring Metrics
1. Add data collection logic in `monitoring/unified_monitor.sh`
2. Update `generate_csv_header()` function to add new fields
3. Add corresponding analysis logic in Python analysis scripts
4. Update visualization components to generate related charts

### Questions?

Open an issue with the `question` label for any contribution-related questions.


## 📄 License

This project is dual-licensed:

### Open Source License (AGPL 3.0)
- Free for personal, academic, and open-source projects
- Modifications must be open-sourced
- Network use requires source disclosure
- See [LICENSE](LICENSE) for full terms

### Commercial License
- Required for commercial/proprietary use
- Closed-source integration allowed
- No AGPL obligations
- Enterprise support available
- See [LICENSE.COMMERCIAL](LICENSE.COMMERCIAL) for details

**Contact:** Open a GitHub Issue with label `commercial-license` for commercial licensing inquiries
