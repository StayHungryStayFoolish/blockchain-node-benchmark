# 区块链节点 QPS 性能基准测试框架

[English](README.md) | [中文](README_ZH.md)

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Commercial License](https://img.shields.io/badge/License-Commercial-green.svg)](LICENSE.COMMERCIAL)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Shell Script](https://img.shields.io/badge/shell-bash-green.svg)](https://www.gnu.org/software/bash/)

一个专业的多区块链节点性能基准测试框架，具备全面的 QPS 测试、实时监控、智能瓶颈检测和高级可视化报告功能。

## 🎯 核心特性

- **多模式 QPS 测试**：快速（15+分钟）、标准（90+分钟）和密集（8+小时）测试模式
- **实时性能监控**：73-79 项性能指标，包括 CPU、内存、EBS、网络、ENA
- **智能瓶颈检测**：6 维度瓶颈检测，采用科学评估算法
- **专业可视化**：32 张专业图表和全面的 HTML 报告
- **AWS 深度集成**：EBS 性能基线、ENA 网络监控、EC2 实例优化
- **区块链节点专业化**：区块高度监控、验证器日志分析、RPC 性能分析



## ⚡ 快速配置

**在运行框架之前**，您必须在 `config/config_loader.sh` 中配置以下参数：

```bash
# 1. RPC 端点（必需）
LOCAL_RPC_URL="http://localhost:8899"  # 您的区块链节点 RPC 端点

# 2. 区块链类型（必需）
BLOCKCHAIN_NODE="Solana"  # 支持：Solana、Ethereum、BSC、Base、Polygon、Scroll、Starknet、Sui

# 3. EBS 设备配置（必需）
LEDGER_DEVICE="nvme1n1"              # DATA 设备名称（使用 'lsblk' 检查）
DATA_VOL_MAX_IOPS="30000"            # 您的 EBS 卷预配置的 IOPS
DATA_VOL_MAX_THROUGHPUT="4000"      # 您的 EBS 卷吞吐量（MiB/s）

# 4. ACCOUNTS 设备（可选，但建议配置以进行完整监控）
ACCOUNTS_DEVICE="nvme2n1"            # ACCOUNTS 设备名称
ACCOUNTS_VOL_MAX_IOPS="30000"       # ACCOUNTS 卷的 IOPS
ACCOUNTS_VOL_MAX_THROUGHPUT="4000"  # ACCOUNTS 卷的吞吐量（MiB/s）

# 5. 网络配置（AWS 环境必需）
NETWORK_MAX_BANDWIDTH_GBPS=25       # 您的实例网络带宽（Gbps）
```

**快速配置检查：**
```bash
# 验证您的 EBS 设备
lsblk

# 在 AWS 控制台检查您的 EBS 卷配置：
# EC2 → 卷 → 选择您的卷 → 详细信息选项卡
# - IOPS：预配置的 IOPS 值
# - 吞吐量：预配置的吞吐量值

# 检查您的实例网络带宽：
# EC2 → 实例类型 → 搜索您的实例类型 → 网络
```

**注意**：如果您没有正确配置这些参数，框架将使用默认值，这可能与您的实际硬件不匹配，导致性能分析不准确。



## 🚀 快速开始

### 前置条件

```bash
# 检查 Python 版本（需要 Python 3.8+）
python3 --version

# 安装 Python 依赖
pip3 install -r requirements.txt

# 验证系统工具
which vegeta    # QPS 测试工具
which iostat    # I/O 监控工具
which mpstat    # CPU 监控工具
which sar       # 网络监控工具
```

### 基本使用

```bash
# 快速测试（15+ 分钟）
./blockchain_node_benchmark.sh --quick

# 标准测试（90+ 分钟）
./blockchain_node_benchmark.sh --standard

# 密集测试（最多 8 小时，带自动瓶颈检测）
./blockchain_node_benchmark.sh --intensive
```

### 自定义测试

```bash
# 自定义密集测试，指定参数
./blockchain_node_benchmark.sh --intensive \
    --initial-qps 1000 \
    --max-qps 10000 \
    --step-qps 500 \
    --duration 300 \
    --mixed  # 使用混合 RPC 方法测试
```



## 📦 系统架构

```
blockchain-node-benchmark/
├── 🎯 核心执行层
│   ├── blockchain_node_benchmark.sh    # 主入口脚本
│   ├── master_qps_executor.sh          # QPS 测试引擎
│   └── common_functions.sh             # 共享函数库
├── ⚙️ 配置管理
│   ├── config_loader.sh                # 配置加载器
│   └── system_config.sh                # 系统配置
├── 📊 监控数据层
│   ├── unified_monitor.sh              # 统一监控器
│   ├── bottleneck_detector.sh          # 瓶颈检测器
│   └── monitoring_coordinator.sh       # 监控协调器
├── 🔬 分析处理层
│   ├── comprehensive_analysis.py       # 综合分析器
│   ├── qps_analyzer.py                 # QPS 分析器
│   └── rpc_deep_analyzer.py            # RPC 深度分析器
├── 📈 可视化层
│   ├── report_generator.py             # HTML 报告生成器
│   ├── performance_visualizer.py       # 性能可视化引擎
│   └── advanced_chart_generator.py     # 高级图表生成器
└── 🛠️ 工具与实用程序
    ├── benchmark_archiver.sh           # 测试结果归档器
    ├── ebs_bottleneck_detector.sh      # EBS 瓶颈检测器
    └── target_generator.sh             # 测试目标生成器
```



## 📚 文档

`docs/` 目录中提供了全面的文档：

### 核心文档

#### [架构概览](./docs/architecture-overview.md)
- 4 层模块化架构设计
- 组件交互和数据流
- 32 张专业图表详解
- 系统集成点

#### [数据架构](./docs/data-architecture-zh.md)
- 完整的数据文件结构和字段定义
- 79 字段性能数据 CSV 格式
- 20 字段监控开销 CSV 格式
- 数据流架构和文件命名约定
- 测试结果的 JSON 格式规范

#### [配置指南](./docs/configuration-guide.md)
- 4 层配置系统（用户/系统/内部/动态）
- EBS 卷配置（gp3/io2/instance-store）
- 网络和 ENA 设置
- 区块链特定参数

#### [监控机制](./docs/monitoring-mechanism.md)
- 双层监控架构
- 79 项性能指标收集（已更新）
- 自我监控和开销分析
- AWS 标准转换公式

#### [区块链测试特性](./docs/blockchain-testing-features.md)
- 单一 vs 混合 RPC 测试模式
- 多区块链支持（Solana/Ethereum/BSC/Base/Polygon/Scroll/Starknet/Sui）
- RPC 方法配置
- 真实交易数据测试



## ⚙️ 配置

### 基本配置（`config/config_loader.sh`）

```bash
# 基本设置
LOCAL_RPC_URL="http://localhost:8899"
BLOCKCHAIN_NODE="Solana"

# EBS 设备配置
LEDGER_DEVICE="nvme1n1"      # DATA 设备（必需）
ACCOUNTS_DEVICE="nvme2n1"    # ACCOUNTS 设备（可选）

# DATA 卷配置（必需）
DATA_VOL_TYPE="io2"          # io2/gp3/instance-store
DATA_VOL_MAX_IOPS="30000"    # 最大 IOPS
DATA_VOL_MAX_THROUGHPUT="700" # 最大吞吐量（MiB/s）

# ACCOUNTS 卷配置（可选）
ACCOUNTS_VOL_TYPE="io2"      # io2/gp3/instance-store
ACCOUNTS_VOL_MAX_IOPS="30000" # 最大 IOPS
ACCOUNTS_VOL_MAX_THROUGHPUT="500" # 最大吞吐量（MiB/s）

# 网络配置
NETWORK_MAX_BANDWIDTH_GBPS=25 # 网络带宽（Gbps）
```

**注意：** ACCOUNTS 设备是可选的。如果未配置，框架将仅监控 DATA 设备。

### 高级配置

```bash
# 瓶颈检测阈值
BOTTLENECK_CPU_THRESHOLD=85
BOTTLENECK_MEMORY_THRESHOLD=90
BOTTLENECK_EBS_UTIL_THRESHOLD=90
BOTTLENECK_EBS_LATENCY_THRESHOLD=50
NETWORK_UTILIZATION_THRESHOLD=80

# 监控间隔
MONITOR_INTERVAL=5              # 默认监控间隔（秒）
HIGH_FREQ_INTERVAL=1            # 高频监控间隔
ULTRA_HIGH_FREQ_INTERVAL=0.5    # 超高频监控间隔
```



## 📊 测试模式

| 模式 | 持续时间 | QPS 范围 | 步长 | 使用场景 |
|------|----------|----------|------|----------|
| **快速** | 15+ 分钟 | 1000-3000 | 500 QPS | 基本性能验证 |
| **标准** | 90+ 分钟 | 1000-5000 | 500 QPS | 全面性能评估 |
| **密集** | 最多 8 小时 | 1000-无限制 | 250 QPS | 智能瓶颈检测 |



## 🔍 监控指标

### 系统指标（共 73-79 项）
- **CPU**：使用率、I/O 等待、系统调用（6 个字段）
- **内存**：使用率、可用内存、缓存（3 个字段）
- **EBS 存储**：IOPS、吞吐量、延迟、利用率（2 个设备共 42 个字段）
- **网络**：带宽利用率、PPS、连接数（10 个字段）
- **ENA 网络**：配额超限、带宽限制（6 个字段，条件性）
- **监控开销**：系统影响指标（2 个字段）
- **区块高度**：本地 vs 主网同步状态（6 个字段）
- **QPS 性能**：当前 QPS、延迟、可用性（3 个字段）

### 瓶颈检测（6 个维度）
1. **CPU 瓶颈**：阈值 85%，权重 25%
2. **内存瓶颈**：阈值 90%，权重 20%
3. **EBS 瓶颈**：IOPS/延迟/利用率，权重 30%
4. **网络瓶颈**：带宽/PPS 利用率，权重 15%
5. **ENA 瓶颈**：配额限制，权重 5%
6. **RPC 瓶颈**：延迟/错误率，权重 5%



## 📈 生成的报告

### 示例报告

查看基于真实测试数据生成的完整示例报告（标准模式，90+ 分钟）：

- [HTML 报告](./docs/image/performance_report_zh_20251025_150834.html) - 包含所有图表的交互式 HTML
- [PDF 报告](./docs/image/performance_report_zh_20251025_150834.pdf) - 可打印的 PDF 版本

### 32 张专业图表（完整框架覆盖）

**高级分析图表（9 张）**：

1. `pearson_correlation_analysis.png` - Pearson 相关性分析
2. `linear_regression_analysis.png` - 线性回归分析
3. `negative_correlation_analysis.png` - 负相关性分析
4. `ena_limitation_trends.png` - ENA 限制趋势
5. `ena_connection_capacity.png` - ENA 连接容量
6. `ena_comprehensive_status.png` - ENA 综合状态
7. `comprehensive_correlation_matrix.png` - 综合相关性矩阵
8. `performance_trend_analysis.png` - 性能趋势分析
9. `performance_correlation_heatmap.png` - 性能相关性热图

**EBS 专业图表（7 张）**：

10. `ebs_aws_capacity_planning.png` - AWS 容量规划分析
11. `ebs_iostat_performance.png` - Iostat 性能分析
12. `ebs_bottleneck_correlation.png` - 瓶颈相关性分析
13. `ebs_performance_overview.png` - EBS 性能概览
14. `ebs_bottleneck_analysis.png` - EBS 瓶颈分析
15. `ebs_aws_standard_comparison.png` - EBS AWS 标准对比
16. `ebs_time_series_analysis.png` - EBS 时间序列分析

**核心性能图表（11 张）**：

17. `performance_overview.png` - 性能概览
18. `cpu_ebs_correlation_visualization.png` - CPU-EBS 相关性分析
19. `device_performance_comparison.png` - 设备性能对比
20. `await_threshold_analysis.png` - I/O 延迟阈值分析
21. `monitoring_overhead_analysis.png` - 监控开销分析
22. `qps_trend_analysis.png` - QPS 趋势分析
23. `resource_efficiency_analysis.png` - 资源效率分析
24. `bottleneck_identification.png` - 瓶颈识别
25. `block_height_sync_chart.png` - 区块高度同步图表
26. `smoothed_trend_analysis.png` - 平滑趋势分析
27. `util_threshold_analysis.png` - 利用率阈值分析

**附加分析图表（5 张）**：

28. `resource_distribution_chart.png` - 资源分布图表
29. `monitoring_impact_chart.png` - 监控影响分析
30. `comprehensive_analysis_charts.png` - 综合分析图表
31. `performance_cliff_analysis.png` - 性能悬崖分析
32. `qps_performance_analysis.png` - QPS 性能分析

### HTML 报告章节
- **执行摘要**：测试概览和关键发现
- **性能分析**：详细的性能指标分析
- **瓶颈分析**：瓶颈检测结果和优化建议
- **图表库**：所有 32 张专业可视化图表
- **EBS 分析**：存储性能深度分析
- **ENA 分析**：网络性能分析（AWS 环境）
- **区块链节点分析**：区块链特定指标分析



## 📋 使用示例

### 示例 1：标准性能测试
```bash
# 运行标准测试
./blockchain_node_benchmark.sh --standard

# 查看结果
ls reports/
# comprehensive_analysis_report.html
# performance_overview.png
# cpu_ebs_correlation_visualization.png
# ...（其他图表文件）
```

### 示例 2：自定义密集测试
```bash
# 自定义密集测试，指定参数
./blockchain_node_benchmark.sh --intensive \
    --initial-qps 2000 \
    --max-qps 15000 \
    --step-qps 1000 \
    --mixed  # 使用混合 RPC 方法测试
```

### 示例 3：检查系统状态
```bash
# 检查 QPS 测试引擎状态
./core/master_qps_executor.sh --status

# 检查监控系统状态
./monitoring/monitoring_coordinator.sh status

# 查看测试历史
./tools/benchmark_archiver.sh --list
```



## 🚨 故障排除

### 常见问题

#### 1. Vegeta 未安装
```bash
# Ubuntu/Debian
sudo apt-get install vegeta

# CentOS/RHEL
sudo yum install vegeta

# macOS
brew install vegeta
```

#### 2. 缺少系统监控工具
```bash
# 安装 sysstat 包
sudo apt-get install sysstat  # Ubuntu/Debian
sudo yum install sysstat      # CentOS/RHEL
```

#### 3. Python 依赖问题
```bash
# 重新安装依赖
pip3 install --upgrade -r requirements.txt

# 检查特定包
python3 -c "import matplotlib, pandas, numpy; print('All packages OK')"
```

#### 4. 权限问题
```bash
# 授予执行权限
chmod +x blockchain_node_benchmark.sh
chmod +x core/master_qps_executor.sh
chmod +x monitoring/monitoring_coordinator.sh
```

### 日志文件位置
- **主日志**：`logs/blockchain_node_benchmark.log`
- **监控日志**：`logs/unified_monitor.log`
- **性能数据**：`logs/performance_YYYYMMDD_HHMMSS.csv`
- **瓶颈事件**：`logs/bottleneck_events.jsonl`



## 🔧 高级功能

### 测试结果归档
```bash
# 列出历史测试
./tools/benchmark_archiver.sh --list

# 比较测试结果
./tools/benchmark_archiver.sh --compare run_001 run_002

# 清理旧测试
./tools/benchmark_archiver.sh --cleanup --days 30
```

### 自定义分析
```python
# 使用 Python 分析组件
from analysis.comprehensive_analysis import ComprehensiveAnalyzer

analyzer = ComprehensiveAnalyzer("reports")
analyzer.run_comprehensive_analysis("logs/performance_latest.csv")
```

### 批量测试
```bash
# 运行多个测试模式
for mode in quick standard intensive; do
    echo "Running $mode test..."
    ./blockchain_node_benchmark.sh --$mode
    sleep 60  # 等待系统恢复
done
```



## 🤝 贡献

### 开发环境设置
```bash
# 克隆仓库
git clone <repository-url>
cd blockchain-node-benchmark

# 安装开发依赖
pip3 install -r requirements.txt

# 运行测试
python3 -m pytest tests/
```

### 添加新的监控指标
1. 在 `monitoring/unified_monitor.sh` 中添加数据收集逻辑
2. 更新 `generate_csv_header()` 函数以添加新字段
3. 在 Python 分析脚本中添加相应的分析逻辑
4. 更新可视化组件以生成相关图表



## 📄 许可证

本项目采用双许可证模式：

### 开源许可证（AGPL 3.0）
- 个人、学术和开源项目免费使用
- 修改后必须开源
- 网络使用需要公开源码
- 详见 [LICENSE](LICENSE) 文件

### 商业许可证
- 商业/专有用途需要购买
- 允许闭源集成
- 无 AGPL 义务
- 提供企业支持
- 详见 [LICENSE.COMMERCIAL](LICENSE.COMMERCIAL) 文件

**联系方式：** 在 GitHub 提交 Issue 并添加 `commercial-license` 标签咨询商业许可
