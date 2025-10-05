# Blockchain Node QPS Performance Benchmark Framework

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Shell Script](https://img.shields.io/badge/shell-bash-green.svg)](https://www.gnu.org/software/bash/)

A professional multi blockchain node performance benchmarking framework with comprehensive QPS testing, real-time monitoring, intelligent bottleneck detection, and advanced visualization reporting.

## 🎯 Key Features

- **Multi-Mode QPS Testing**: Quick (7min), Standard (15min), and Intensive (2hr) testing modes
- **Real-Time Performance Monitoring**: 73-79 performance metrics including CPU, Memory, EBS, Network, ENA
- **Intelligent Bottleneck Detection**: 6-dimensional bottleneck detection with scientific evaluation algorithms
- **Professional Visualization**: 18 types of professional charts and comprehensive HTML reports
- **AWS Deep Integration**: EBS performance baselines, ENA network monitoring, EC2 instance optimization
- **Blockchain Node Specialization**: Block height monitoring, validator log analysis, RPC performance analysis

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
# Quick test (7 minutes)
./blockchain_node_benchmark.sh --quick

# Standard test (15 minutes)
./blockchain_node_benchmark.sh --standard

# Intensive test (up to 2 hours with automatic bottleneck detection)
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

## 📊 Testing Modes

| Mode | Duration | QPS Range | Step Size | Use Case |
|------|----------|-----------|-----------|----------|
| **Quick** | 7 minutes | 1000-3000 | 500 QPS | Basic performance verification |
| **Standard** | 15 minutes | 1000-5000 | 500 QPS | Comprehensive performance evaluation |
| **Intensive** | Up to 2 hours | 1000-unlimited | 250 QPS | Intelligent bottleneck detection |

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

### 32 Professional Charts (Complete Framework Coverage)
**Advanced Analysis Charts (9 charts)**:
1. `pearson_correlation_analysis.png` - Pearson相关性分析
2. `linear_regression_analysis.png` - 线性回归分析
3. `negative_correlation_analysis.png` - 负相关分析
4. `ena_limitation_trends.png` - ENA限制趋势
5. `ena_connection_capacity.png` - ENA连接容量
6. `ena_comprehensive_status.png` - ENA综合状态
7. `comprehensive_correlation_matrix.png` - 综合相关性矩阵
8. `performance_trend_analysis.png` - 性能趋势分析
9. `performance_correlation_heatmap.png` - 相关性热力图

**EBS Professional Charts (7 charts)**:
10. `ebs_aws_capacity_planning.png` - AWS容量规划分析
11. `ebs_iostat_performance.png` - Iostat性能分析
12. `ebs_bottleneck_correlation.png` - 瓶颈相关性分析
13. `ebs_performance_overview.png` - EBS性能概览
14. `ebs_bottleneck_analysis.png` - EBS瓶颈分析
15. `ebs_aws_standard_comparison.png` - EBS AWS标准对比
16. `ebs_time_series_analysis.png` - EBS时间序列

**Core Performance Charts (11 charts)**:
17. `performance_overview.png` - 性能概览图表
18. `cpu_ebs_correlation_visualization.png` - CPU-EBS相关性分析
19. `device_performance_comparison.png` - 设备性能对比
20. `await_threshold_analysis.png` - I/O延迟阈值分析
21. `monitoring_overhead_analysis.png` - 监控开销分析
22. `qps_trend_analysis.png` - QPS趋势分析
23. `resource_efficiency_analysis.png` - 资源效率分析
24. `bottleneck_identification.png` - 瓶颈识别图表
25. `block_height_sync_chart.png` - 区块高度同步图表
26. `smoothed_trend_analysis.png` - 平滑趋势分析
27. `util_threshold_analysis.png` - 利用率阈值分析

**Additional Analysis Charts (5 charts)**:
28. `resource_distribution_chart.png` - 资源分布图表
29. `monitoring_impact_chart.png` - 监控影响分析
30. `comprehensive_analysis_charts.png` - 综合分析图表
31. `performance_cliff_analysis.png` - 性能悬崖分析
32. `qps_performance_analysis.png` - QPS性能分析

### HTML Report Sections
- **Executive Summary**: Test overview and key findings
- **Performance Analysis**: Detailed performance metrics analysis
- **Bottleneck Analysis**: Bottleneck detection results and optimization recommendations
- **Chart Gallery**: All 18 professional visualization charts
- **EBS Analysis**: Storage performance deep dive
- **ENA Analysis**: Network performance analysis (AWS environments)
- **Blockchain Node Analysis**: Blockchain-specific metrics analysis

## ⚙️ Configuration

### Basic Configuration (`config/config_loader.sh`)

```bash
# Basic settings
LOCAL_RPC_URL="http://localhost:8899"
BLOCKCHAIN_NODE="Solana"

# EBS device configuration
LEDGER_DEVICE="nvme1n1"      # DATA device
ACCOUNTS_DEVICE="nvme2n1"    # ACCOUNTS device (optional)

# Volume configuration
DATA_VOL_TYPE="io2"          # io2/gp3/instance-store
DATA_VOL_MAX_IOPS="20000"    # Maximum IOPS
DATA_VOL_MAX_THROUGHPUT="700" # Maximum throughput (MiB/s)

# Network configuration
NETWORK_MAX_BANDWIDTH_GBPS=25 # Network bandwidth (Gbps)
```

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

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## 🆘 Support

If you encounter issues or need help:

1. Check the troubleshooting section in this README
2. Review log files in the `logs/` directory
3. Run `./blockchain_node_benchmark.sh --help` for help information
4. Submit an issue to the project repository

---
