# Blockchain Node QPS Performance Benchmark Framework

[English](README.md) | [中文](README_ZH.md)

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Commercial License](https://img.shields.io/badge/License-Commercial-green.svg)](LICENSE.COMMERCIAL)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Shell Script](https://img.shields.io/badge/shell-bash-green.svg)](https://www.gnu.org/software/bash/)

A professional multi blockchain node performance benchmarking framework with comprehensive QPS testing, real-time monitoring, intelligent bottleneck detection, and advanced visualization reporting.

## 🎯 Key Features

- **Multi-Mode QPS Testing**: Quick (15+min), Standard (90+min), and Intensive (8+hr) testing modes
- **Real-Time Performance Monitoring**: 73-79 performance metrics including CPU, Memory, EBS, Network, ENA
- **Intelligent Bottleneck Detection**: 6-dimensional bottleneck detection with scientific evaluation algorithms
- **Professional Visualization**: 32 professional charts and comprehensive HTML reports
- **AWS Deep Integration**: EBS performance baselines, ENA network monitoring, EC2 instance optimization
- **Blockchain Node Specialization**: Block height monitoring, validator log analysis, RPC performance analysis



## ⚡ Quick Configuration

**Before running the framework**, you must configure the following parameters in `config/config_loader.sh`:

```bash
# 1. RPC Endpoint (Required)
LOCAL_RPC_URL="http://localhost:8899"  # Your blockchain node RPC endpoint

# 2. Blockchain Type (Required)
BLOCKCHAIN_NODE="Solana"  # Supported: Solana, Ethereum, BSC, Base, Polygon, Scroll, Starknet, Sui

# 3. EBS Device Configuration (Required)
LEDGER_DEVICE="nvme1n1"              # DATA device name (check with 'lsblk')
DATA_VOL_MAX_IOPS="30000"            # Your EBS volume's provisioned IOPS
DATA_VOL_MAX_THROUGHPUT="4000"      # Your EBS volume's throughput (MiB/s)

# 4. ACCOUNTS Device (Optional, but recommended for complete monitoring)
ACCOUNTS_DEVICE="nvme2n1"            # ACCOUNTS device name
ACCOUNTS_VOL_MAX_IOPS="30000"       # ACCOUNTS volume's provisioned IOPS
ACCOUNTS_VOL_MAX_THROUGHPUT="4000"  # ACCOUNTS volume's throughput (MiB/s)

# 5. Network Configuration (Required for AWS environments)
NETWORK_MAX_BANDWIDTH_GBPS=25       # Your instance's network bandwidth (Gbps)
```

**Quick Configuration Check:**
```bash
# Verify your EBS devices
lsblk

# Check your EBS volume configuration in AWS Console:
# EC2 → Volumes → Select your volume → Details tab
# - IOPS: Provisioned IOPS value
# - Throughput: Provisioned throughput value

# Check your instance network bandwidth:
# EC2 → Instance Types → Search your instance type → Networking
```

**Note**: If you don't configure these parameters correctly, the framework will use default values which may not match your actual hardware, leading to inaccurate performance analysis.



## 🚀 Quick Start

### Prerequisites

```bash
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
# Quick test (15+ minutes)
./blockchain_node_benchmark.sh --quick

# Standard test (90+ minutes)
./blockchain_node_benchmark.sh --standard

# Intensive test (up to 8 hours with automatic bottleneck detection)
./blockchain_node_benchmark.sh --intensive
```

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

### Basic Configuration (`config/config_loader.sh`)

```bash
# Basic settings
LOCAL_RPC_URL="http://localhost:8899"
BLOCKCHAIN_NODE="Solana"

# EBS device configuration
LEDGER_DEVICE="nvme1n1"      # DATA device (required)
ACCOUNTS_DEVICE="nvme2n1"    # ACCOUNTS device (optional)

# DATA volume configuration (required)
DATA_VOL_TYPE="io2"          # io2/gp3/instance-store
DATA_VOL_MAX_IOPS="30000"    # Maximum IOPS
DATA_VOL_MAX_THROUGHPUT="700" # Maximum throughput (MiB/s)

# ACCOUNTS volume configuration (optional)
ACCOUNTS_VOL_TYPE="io2"      # io2/gp3/instance-store
ACCOUNTS_VOL_MAX_IOPS="30000" # Maximum IOPS
ACCOUNTS_VOL_MAX_THROUGHPUT="500" # Maximum throughput (MiB/s)

# Network configuration
NETWORK_MAX_BANDWIDTH_GBPS=25 # Network bandwidth (Gbps)
```

**Note:** ACCOUNTS device is optional. If not configured, the framework will only monitor the DATA device.

### Advanced Configuration

```bash
# Bottleneck detection thresholds
BOTTLENECK_CPU_THRESHOLD=85
BOTTLENECK_MEMORY_THRESHOLD=90
BOTTLENECK_EBS_UTIL_THRESHOLD=90
BOTTLENECK_EBS_LATENCY_THRESHOLD=50
NETWORK_UTILIZATION_THRESHOLD=80

# Monitoring intervals
MONITOR_INTERVAL=5              # Default monitoring interval (seconds)
HIGH_FREQ_INTERVAL=1            # High-frequency monitoring interval
ULTRA_HIGH_FREQ_INTERVAL=0.5    # Ultra-high-frequency monitoring interval
```



## 📊 Testing Modes

| Mode | Duration      | QPS Range | Step Size | Use Case |
|------|---------------|-----------|-----------|----------|
| **Quick** | 15+ minutes   | 1000-3000 | 500 QPS | Basic performance verification |
| **Standard** | 90+ minutes   | 1000-5000 | 500 QPS | Comprehensive performance evaluation |
| **Intensive** | Up to 8 hours | 1000-unlimited | 250 QPS | Intelligent bottleneck detection |



## 🔍 Monitoring Metrics

### System Metrics (73-79 total)
- **CPU**: Usage, I/O wait, system calls (6 fields)
- **Memory**: Usage, available memory, cache (3 fields)
- **EBS Storage**: IOPS, throughput, latency, utilization (42 fields for 2 devices)
- **Network**: Bandwidth utilization, PPS, connections (10 fields)
- **ENA Network**: Allowance exceeded, bandwidth limits (6 fields, conditional)
- **Monitoring Overhead**: System impact metrics (2 fields)
- **Block Height**: Local vs mainnet sync status (6 fields)
- **QPS Performance**: Current QPS, latency, availability (3 fields)

### Bottleneck Detection (6 Dimensions)
1. **CPU Bottleneck**: Threshold 85%, Weight 25%
2. **Memory Bottleneck**: Threshold 90%, Weight 20%
3. **EBS Bottleneck**: IOPS/Latency/Utilization, Weight 30%
4. **Network Bottleneck**: Bandwidth/PPS utilization, Weight 15%
5. **ENA Bottleneck**: Allowance limits, Weight 5%
6. **RPC Bottleneck**: Latency/Error rate, Weight 5%



## 📈 Generated Reports

### Sample Reports

View complete sample reports generated from real test data (Standard mode, 90+ minutes):

- [HTML Report](./docs/image/performance_report_en_20251025_150834.html) - Interactive HTML with all charts
- [PDF Report](./docs/image/performance_report_en_20251025_150834.pdf) - Printable PDF version

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
- **Executive Summary**: Test overview and key findings
- **Performance Analysis**: Detailed performance metrics analysis
- **Bottleneck Analysis**: Bottleneck detection results and optimization recommendations
- **Chart Gallery**: All 32 professional visualization charts
- **EBS Analysis**: Storage performance deep dive
- **ENA Analysis**: Network performance analysis (AWS environments)
- **Blockchain Node Analysis**: Blockchain-specific metrics analysis



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
- **Main Log**: `logs/blockchain_node_benchmark.log`
- **Monitoring Log**: `logs/unified_monitor.log`
- **Performance Data**: `logs/performance_YYYYMMDD_HHMMSS.csv`
- **Bottleneck Events**: `logs/bottleneck_events.jsonl`



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

### Development Environment Setup
```bash
# Clone the repository
git clone <repository-url>
cd blockchain-node-benchmark

# Install development dependencies
pip3 install -r requirements.txt

# Run tests
python3 -m pytest tests/
```

### Adding New Monitoring Metrics
1. Add data collection logic in `monitoring/unified_monitor.sh`
2. Update `generate_csv_header()` function to add new fields
3. Add corresponding analysis logic in Python analysis scripts
4. Update visualization components to generate related charts



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
