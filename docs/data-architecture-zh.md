# 数据架构

## 概述

区块链节点基准测试框架实现了**多层数据架构**，高效地收集、处理和分析性能指标。系统通过协调监控系统生成**79字段性能数据**和**20字段监控开销数据**。

---

## 数据流架构

### 1. 整体架构流程

```mermaid
graph TB
    A[blockchain_node_benchmark.sh<br/>框架入口] --> B[监控系统]
    A --> C[QPS测试]
    A --> D[数据分析]
    A --> E[报告生成]
    
    B --> B1[monitoring_coordinator.sh<br/>监控协调器]
    B1 --> B2[unified_monitor.sh<br/>统一监控器]
    B1 --> B3[block_height_monitor.sh<br/>区块高度监控]
    B1 --> B4[ena_network_monitor.sh<br/>ENA网络监控]
    B1 --> B5[ebs_bottleneck_detector.sh<br/>EBS瓶颈检测]
    
    C --> C1[master_qps_executor.sh<br/>QPS测试引擎]
    C1 --> C2[Vegeta压力测试]
    C1 --> C3[实时瓶颈检测]
    
    D --> D1[comprehensive_analysis.py<br/>综合分析器]
    D --> D2[qps_analyzer.py<br/>QPS分析器]
    D --> D3[validator_log_analyzer.py<br/>日志分析器]
    
    E --> E1[report_generator.py<br/>HTML报告生成]
    E --> E2[performance_visualizer.py<br/>性能可视化]
    E --> E3[advanced_chart_generator.py<br/>高级图表生成]
```

### 2. 数据流管道

```mermaid
graph LR
    subgraph "数据生产层"
        A1[unified_monitor.sh<br/>系统监控]
        A2[block_height_monitor.sh<br/>区块链状态]
        A3[ena_network_monitor.sh<br/>网络性能]
        A4[master_qps_executor.sh<br/>QPS测试]
    end
    
    subgraph "数据存储层"
        B1[performance_*.csv<br/>核心数据枢纽<br/>79个字段]
        B2[monitoring_overhead_*.csv<br/>监控开销<br/>20个字段]
        B3[block_height_*.csv<br/>区块链数据]
        B4[ena_network_*.csv<br/>ENA网络数据]
        B5[bottleneck_events.jsonl<br/>瓶颈事件]
    end
    
    subgraph "数据消费层"
        C1[ebs_bottleneck_detector.sh<br/>实时检测]
        C2[comprehensive_analysis.py<br/>分析处理]
        C3[report_generator.py<br/>报告生成]
        C4[performance_visualizer.py<br/>可视化]
    end
    
    A1 --> B1
    A1 --> B2
    A2 --> B1
    A2 --> B3
    A3 --> B4
    A4 --> B5
    
    B1 --> C1
    B1 --> C2
    B1 --> C3
    B1 --> C4
    B2 --> C3
    B3 --> C2
    B4 --> C2
    B5 --> C2
```

### 3. 核心数据文件关系

```mermaid
graph TD
    subgraph "performance_*.csv - 核心数据枢纽 (79个字段)"
        P1[timestamp]
        P2[CPU指标 - 6个字段<br/>cpu_usage, cpu_usr, cpu_sys<br/>cpu_iowait, cpu_soft, cpu_idle]
        P3[内存指标 - 3个字段<br/>mem_used, mem_total, mem_usage]
        P4[DATA设备 - 21个字段<br/>data_*_r_s, data_*_w_s<br/>data_*_total_iops<br/>data_*_aws_standard_*]
        P5[ACCOUNTS设备 - 21个字段<br/>accounts_*_r_s, accounts_*_w_s<br/>accounts_*_total_iops<br/>accounts_*_aws_standard_*]
        P6[网络指标 - 10个字段<br/>net_interface, net_*_mbps<br/>net_*_gbps, net_*_pps]
        P7[ENA指标 - 6个字段<br/>bw_*_allowance_exceeded<br/>pps_allowance_exceeded<br/>conntrack_allowance_*]
        P8[监控开销 - 2个字段<br/>monitoring_iops_per_sec<br/>monitoring_throughput_mibs_per_sec]
        P9[区块高度 - 6个字段<br/>local_block_height<br/>mainnet_block_height<br/>block_height_diff<br/>*_health, data_loss]
        P10[QPS性能 - 3个字段<br/>current_qps<br/>rpc_latency_ms<br/>qps_data_available]
    end
    
    subgraph "专项数据文件"
        S1[monitoring_overhead_*.csv<br/>20个字段<br/>monitoring_cpu, monitoring_memory_*<br/>blockchain_cpu, blockchain_memory_*<br/>system_cpu_cores, system_memory_gb]
        S2[block_height_*.csv<br/>区块高度监控<br/>timestamp, local_block_height<br/>mainnet_block_height, block_height_diff<br/>local_health, mainnet_health, data_loss]
        S3[ena_network_*.csv<br/>ENA网络指标<br/>timestamp, interface<br/>rx_bytes, tx_bytes<br/>+ ENA_ALLOWANCE_FIELDS]
    end
    
    S2 -.->|数据集成| P9
    S1 -.->|数据摘要| P8
    S3 -.->|条件集成| P7
```

### 4. 监控系统调用链

```mermaid
sequenceDiagram
    participant Main as blockchain_node_benchmark.sh
    participant Coord as monitoring_coordinator.sh
    participant Unified as unified_monitor.sh
    participant Block as block_height_monitor.sh
    participant ENA as ena_network_monitor.sh
    participant EBS as ebs_bottleneck_detector.sh
    
    Main->>+Coord: start_monitoring_system()
    Note over Main,Coord: 导出环境变量<br/>MONITOR_PIDS_FILE<br/>MONITOR_STATUS_FILE
    
    Coord->>+Unified: start unified_monitor.sh
    Coord->>+Block: start block_height_monitor.sh
    Coord->>+ENA: start ena_network_monitor.sh (条件性)
    Coord->>+EBS: start ebs_bottleneck_detector.sh
    
    Note over Unified: 创建performance_*.csv<br/>创建符号链接performance_latest.csv
    Note over Block: 创建block_height_*.csv
    Note over ENA: 创建ena_network_*.csv
    
    Unified->>Unified: 数据收集循环<br/>log_performance_data()
    Block->>Block: 区块高度监控循环<br/>monitor_block_height_diff()
    ENA->>ENA: ENA网络监控循环<br/>get_ena_network_stats()
    
    Note over Unified,Block: unified_monitor.sh读取<br/>区块高度数据并集成
    Unified->>Block: tail -1 BLOCK_HEIGHT_DATA_FILE
    Block-->>Unified: 最新区块高度数据
    
    Note over EBS: 实时监听performance_latest.csv
    EBS->>Unified: tail -F performance_latest.csv
    Unified-->>EBS: 实时数据流
    
    EBS->>EBS: 动态字段映射<br/>init_csv_field_mapping()
    EBS->>EBS: 瓶颈检测<br/>detect_ebs_bottleneck()
```

### 5. 数据处理和分析流程

```mermaid
graph TB
    subgraph "数据收集阶段"
        A1[系统指标<br/>CPU, Memory, Network]
        A2[存储指标<br/>EBS IOPS, Throughput, Latency]
        A3[区块链指标<br/>Block Height, RPC Status]
        A4[网络指标<br/>ENA Allowance, Bandwidth]
        A5[QPS测试数据<br/>Vegeta Results, Bottleneck Events]
    end
    
    subgraph "数据整合阶段"
        B1[unified_monitor.sh<br/>数据汇聚和格式化]
        B2[CSV表头生成<br/>generate csv header]
        B3[符号链接创建<br/>performance_latest.csv]
        B4[实时数据流<br/>tail -F 监听]
    end
    
    subgraph "实时分析阶段"
        C1[EBS瓶颈检测<br/>动态字段映射]
        C2[QPS瓶颈检测<br/>6维度评估]
        C3[事件记录<br/>JSON格式日志]
    end
    
    subgraph "离线分析阶段"
        D1[综合分析<br/>comprehensive_analysis.py]
        D2[QPS分析<br/>qps_analyzer.py]
        D3[日志分析<br/>validator_log_analyzer.py]
        D4[RPC深度分析<br/>rpc_deep_analyzer.py]
    end
    
    subgraph "可视化输出阶段"
        E1[HTML报告生成<br/>32张专业图表]
        E2[性能可视化<br/>趋势分析图表]
        E3[高级图表<br/>相关性分析]
        E4[归档管理<br/>历史数据对比]
    end
    
    A1 --> B1
    A2 --> B1
    A3 --> B1
    A4 --> B1
    A5 --> B1
    
    B1 --> B2
    B2 --> B3
    B3 --> B4
    
    B4 --> C1
    B4 --> C2
    C1 --> C3
    C2 --> C3
    
    B3 --> D1
    B3 --> D2
    C3 --> D3
    C3 --> D4
    
    D1 --> E1
    D2 --> E2
    D3 --> E3
    D4 --> E4
```

### 6. 符号链接和文件轮转机制

```mermaid
graph LR
    subgraph "文件创建机制"
        A1[unified_monitor.sh启动]
        A2[生成时间戳文件名<br/>performance_YYYYMMDD_HHMMSS.csv]
        A3[创建符号链接<br/>performance_latest.csv]
        A4[写入CSV表头<br/>generate csv header]
    end
    
    subgraph "实时数据流"
        B1[数据收集循环<br/>log performance data]
        B2[写入时间戳文件<br/>safe write csv]
        B3[EBS检测器监听<br/>tail -F performance_latest.csv]
        B4[动态字段映射<br/>CSV_FIELD_MAP]
    end
    
    subgraph "文件轮转支持"
        C1[检测CSV格式变化<br/>timestamp格式验证]
        C2[重新初始化映射<br/>init csv field mapping]
        C3[符号链接自动跟随<br/>ln -sf 新文件]
        C4[无缝数据流切换<br/>tail -F 继续工作]
    end
    
    A1 --> A2
    A2 --> A3
    A3 --> A4
    A4 --> B1
    B1 --> B2
    B2 --> B3
    B3 --> B4
    
    B4 --> C1
    C1 --> C2
    C2 --> C3
    C3 --> C4
```

---

## 数据文件结构

### 归档目录结构

```
archives/run_*_YYYYMMDD_HHMMSS/
├── logs/
│   ├── performance_*.csv              # 主性能数据 (79个字段)
│   ├── monitoring_overhead_*.csv      # 监控开销数据 (20个字段)
│   ├── block_height_monitor_*.csv     # 区块高度监控
│   ├── ena_network_*.csv              # ENA网络监控
│   ├── blockchain_node_benchmark.log  # 主执行日志
│   └── unified_monitor.log            # 监控系统日志
├── reports/
│   ├── performance_report_en_*.html   # 英文HTML报告
│   ├── performance_report_zh_*.html   # 中文HTML报告
│   └── *.png                          # 32张专业图表
├── vegeta_results/
│   └── vegeta_*qps_*.json            # 每个级别的QPS测试结果
├── tmp/
│   ├── targets_single.json            # 单一RPC方法目标
│   ├── targets_mixed.json             # 混合RPC方法目标
│   └── monitoring_status.json         # 监控系统状态
└── test_summary.json                  # 测试摘要元数据
```

---

## 核心数据文件

### 1. 性能数据文件

**文件模式**: `logs/performance_*.csv`  
**总字段数**: 79个字段  
**更新频率**: 每5秒（可配置）

#### 字段分类

| 分类 | 字段数 | 描述 |
|------|--------|------|
| **时间戳** | 1 | 数据采集时间戳 |
| **CPU指标** | 6 | cpu_usage, cpu_usr, cpu_sys, cpu_iowait, cpu_soft, cpu_idle |
| **内存指标** | 3 | mem_used, mem_total, mem_usage |
| **DATA设备EBS** | 21 | IOPS, 吞吐量, 延迟, 利用率, AWS标准指标 |
| **ACCOUNTS设备EBS** | 21 | 与DATA设备相同结构 |
| **网络指标** | 10 | 接口, 带宽 (Mbps/Gbps), 每秒包数 |
| **ENA网络** | 6 | 配额超限计数器, 连接跟踪 |
| **监控开销** | 2 | IOPS和吞吐量开销 |
| **区块高度** | 6 | 本地/主网高度, 差值, 健康状态, 数据丢失 |
| **QPS性能** | 3 | 当前QPS, RPC延迟, 数据可用性 |

### 2. 监控开销数据文件

**文件模式**: `logs/monitoring_overhead_*.csv`  
**总字段数**: 20个字段  
**更新频率**: 每5秒

#### 字段分类

| 分类 | 字段数 | 描述 |
|------|--------|------|
| **时间戳** | 1 | 数据采集时间戳 |
| **监控系统** | 4 | CPU, 内存 (百分比/MB), 进程数 |
| **区块链节点** | 4 | CPU, 内存 (百分比/MB), 进程数 |
| **系统资源** | 3 | CPU核心数, 内存 (GB), 磁盘 (GB) |
| **系统使用率** | 3 | CPU使用率, 内存使用率, 磁盘使用率 |
| **内存详情** | 5 | 缓存, 缓冲区, 匿名页, 映射, 共享内存 |

### 3. 测试摘要文件

**文件模式**: `test_summary.json`  
**格式**: JSON

```json
{
    "run_id": "run_*_YYYYMMDD_HHMMSS",
    "benchmark_mode": "quick|standard|intensive",
    "start_time": "YYYY-MM-DD HH:MM:SS",
    "end_time": "YYYY-MM-DD HH:MM:SS",
    "duration_minutes": 0,
    "max_successful_qps": 5000,
    "bottleneck_detected": false,
    "bottleneck_types": [],
    "bottleneck_summary": "none|cpu|memory|ebs|network",
    "test_parameters": {
        "initial_qps": 1000,
        "max_qps": 5000,
        "qps_step": 500,
        "duration_per_level": 600
    },
    "data_size": {
        "logs_mb": 3,
        "reports_mb": 34,
        "vegeta_results_mb": 1,
        "total_mb": 38
    }
}
```

### 4. Vegeta QPS测试结果

**文件模式**: `vegeta_results/vegeta_*qps_*.json`  
**格式**: JSON

```json
{
    "latencies": {
        "mean": 139674,
        "50th": 123974,
        "90th": 169127,
        "95th": 192415,
        "99th": 354598,
        "max": 41183837,
        "min": 59940
    },
    "requests": 600000,
    "rate": 1000.001044157757,
    "throughput": 1000.0007889739558,
    "success": 1,
    "status_codes": {
        "200": 600000
    },
    "errors": []
}
```

---

## 文件命名规范

### 时间戳格式

- **模式**: `YYYYMMDD_HHMMSS`
- **示例**: `20251025_150834`
- **时区**: UTC或本地系统时间

### 文件模式

| 文件类型 | 模式 | 示例 |
|---------|------|------|
| 性能数据 | `performance_*.csv` | `performance_20251025_150834.csv` |
| 监控开销 | `monitoring_overhead_*.csv` | `monitoring_overhead_20251025_150834.csv` |
| 区块高度 | `block_height_monitor_*.csv` | `block_height_monitor_20251025_150834.csv` |
| ENA网络 | `ena_network_*.csv` | `ena_network_20251025_150834.csv` |
| Vegeta结果 | `vegeta_*qps_*.json` | `vegeta_1000qps_20251025_150834.json` |
| HTML报告 | `performance_report_{lang}_*.html` | `performance_report_zh_20251025_150834.html` |

---

## 数据使用示例

### Python分析

```python
import pandas as pd

# 加载主性能数据
df = pd.read_csv('logs/performance_*.csv')
print(f"总字段数: {len(df.columns)}")  # 79个字段

# 加载监控开销数据
overhead_df = pd.read_csv('logs/monitoring_overhead_*.csv')
print(f"开销字段数: {len(overhead_df.columns)}")  # 20个字段
```

### Shell脚本

```bash
# 统计总字段数
head -1 logs/performance_*.csv | tr ',' '\n' | wc -l  # 79

# 提取特定列
awk -F',' '{print $1,$77,$78}' logs/performance_*.csv  # timestamp, current_qps, rpc_latency_ms
```

---

## 相关文档

- [架构概览](./architecture-overview.md)
- [配置指南](./configuration-guide.md)
- [监控机制](./monitoring-mechanism.md)
- [区块链测试特性](./blockchain-testing-features.md)
