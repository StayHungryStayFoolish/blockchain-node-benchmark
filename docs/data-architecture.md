# Data Architecture

## Overview

The Blockchain Node Benchmark Framework implements a **multi-layer data architecture** that efficiently collects, processes, and analyzes performance metrics. The system generates **79-field performance data** and **20-field monitoring overhead data** through a coordinated monitoring system.

---

## Data Flow Architecture

### 1. Overall Architecture Flow

```mermaid
graph TB
    A[blockchain_node_benchmark.sh<br/>Framework Entry] --> B[Monitoring System]
    A --> C[QPS Testing]
    A --> D[Data Analysis]
    A --> E[Report Generation]
    
    B --> B1[monitoring_coordinator.sh<br/>Coordinator]
    B1 --> B2[unified_monitor.sh<br/>Unified Monitor]
    B1 --> B3[block_height_monitor.sh<br/>Block Height Monitor]
    B1 --> B4[ena_network_monitor.sh<br/>ENA Network Monitor]
    B1 --> B5[ebs_bottleneck_detector.sh<br/>EBS Bottleneck Detector]
    
    C --> C1[master_qps_executor.sh<br/>QPS Test Engine]
    C1 --> C2[Vegeta Load Testing]
    C1 --> C3[Real-time Bottleneck Detection]
    
    D --> D1[comprehensive_analysis.py<br/>Comprehensive Analyzer]
    D --> D2[qps_analyzer.py<br/>QPS Analyzer]
    D --> D3[validator_log_analyzer.py<br/>Log Analyzer]
    
    E --> E1[report_generator.py<br/>HTML Report Generator]
    E --> E2[performance_visualizer.py<br/>Performance Visualizer]
    E --> E3[advanced_chart_generator.py<br/>Advanced Chart Generator]
```

### 2. Data Flow Pipeline

```mermaid
graph LR
    subgraph "Data Production Layer"
        A1[unified_monitor.sh<br/>System Monitoring]
        A2[block_height_monitor.sh<br/>Blockchain State]
        A3[ena_network_monitor.sh<br/>Network Performance]
        A4[master_qps_executor.sh<br/>QPS Testing]
    end
    
    subgraph "Data Storage Layer"
        B1[performance_*.csv<br/>Core Data Hub<br/>79 fields]
        B2[monitoring_overhead_*.csv<br/>Monitoring Overhead<br/>20 fields]
        B3[block_height_*.csv<br/>Blockchain Data]
        B4[ena_network_*.csv<br/>ENA Network Data]
        B5[bottleneck_events.jsonl<br/>Bottleneck Events]
    end
    
    subgraph "Data Consumption Layer"
        C1[ebs_bottleneck_detector.sh<br/>Real-time Detection]
        C2[comprehensive_analysis.py<br/>Analysis Processing]
        C3[report_generator.py<br/>Report Generation]
        C4[performance_visualizer.py<br/>Visualization]
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

### 3. Core Data File Relationships

```mermaid
graph TD
    subgraph "performance_*.csv - Core Data Hub (79 fields)"
        P1[timestamp]
        P2[CPU Metrics - 6 fields<br/>cpu_usage, cpu_usr, cpu_sys<br/>cpu_iowait, cpu_soft, cpu_idle]
        P3[Memory Metrics - 3 fields<br/>mem_used, mem_total, mem_usage]
        P4[DATA Device - 21 fields<br/>data_*_r_s, data_*_w_s<br/>data_*_total_iops<br/>data_*_aws_standard_*]
        P5[ACCOUNTS Device - 21 fields<br/>accounts_*_r_s, accounts_*_w_s<br/>accounts_*_total_iops<br/>accounts_*_aws_standard_*]
        P6[Network Metrics - 10 fields<br/>net_interface, net_*_mbps<br/>net_*_gbps, net_*_pps]
        P7[ENA Metrics - 6 fields<br/>bw_*_allowance_exceeded<br/>pps_allowance_exceeded<br/>conntrack_allowance_*]
        P8[Monitoring Overhead - 2 fields<br/>monitoring_iops_per_sec<br/>monitoring_throughput_mibs_per_sec]
        P9[Block Height - 6 fields<br/>local_block_height<br/>mainnet_block_height<br/>block_height_diff<br/>*_health, data_loss]
        P10[QPS Performance - 3 fields<br/>current_qps<br/>rpc_latency_ms<br/>qps_data_available]
    end
    
    subgraph "Specialized Data Files"
        S1[monitoring_overhead_*.csv<br/>20 fields<br/>monitoring_cpu, monitoring_memory_*<br/>blockchain_cpu, blockchain_memory_*<br/>system_cpu_cores, system_memory_gb]
        S2[block_height_*.csv<br/>Block height monitoring<br/>timestamp, local_block_height<br/>mainnet_block_height, block_height_diff<br/>local_health, mainnet_health, data_loss]
        S3[ena_network_*.csv<br/>ENA network metrics<br/>timestamp, interface<br/>rx_bytes, tx_bytes<br/>+ ENA_ALLOWANCE_FIELDS]
    end
    
    S2 -.->|Data Integration| P9
    S1 -.->|Data Summary| P8
    S3 -.->|Conditional Integration| P7
```

### 4. Monitoring System Call Chain

```mermaid
sequenceDiagram
    participant Main as blockchain_node_benchmark.sh
    participant Coord as monitoring_coordinator.sh
    participant Unified as unified_monitor.sh
    participant Block as block_height_monitor.sh
    participant ENA as ena_network_monitor.sh
    participant EBS as ebs_bottleneck_detector.sh
    
    Main->>+Coord: start_monitoring_system()
    Note over Main,Coord: Export environment variables<br/>MONITOR_PIDS_FILE<br/>MONITOR_STATUS_FILE
    
    Coord->>+Unified: start unified_monitor.sh
    Coord->>+Block: start block_height_monitor.sh
    Coord->>+ENA: start ena_network_monitor.sh (conditional)
    Coord->>+EBS: start ebs_bottleneck_detector.sh
    
    Note over Unified: Create performance_*.csv<br/>Create symlink performance_latest.csv
    Note over Block: Create block_height_*.csv
    Note over ENA: Create ena_network_*.csv
    
    Unified->>Unified: Data collection loop<br/>log_performance_data()
    Block->>Block: Block height monitoring loop<br/>monitor_block_height_diff()
    ENA->>ENA: ENA network monitoring loop<br/>get_ena_network_stats()
    
    Note over Unified,Block: unified_monitor.sh reads<br/>block height data and integrates
    Unified->>Block: tail -1 BLOCK_HEIGHT_DATA_FILE
    Block-->>Unified: Latest block height data
    
    Note over EBS: Real-time monitoring performance_latest.csv
    EBS->>Unified: tail -F performance_latest.csv
    Unified-->>EBS: Real-time data stream
    
    EBS->>EBS: Dynamic field mapping<br/>init_csv_field_mapping()
    EBS->>EBS: Bottleneck detection<br/>detect_ebs_bottleneck()
```

### 5. Data Processing and Analysis Flow

```mermaid
graph TB
    subgraph "Data Collection Stage"
        A1[System Metrics<br/>CPU, Memory, Network]
        A2[Storage Metrics<br/>EBS IOPS, Throughput, Latency]
        A3[Blockchain Metrics<br/>Block Height, RPC Status]
        A4[Network Metrics<br/>ENA Allowance, Bandwidth]
        A5[QPS Test Data<br/>Vegeta Results, Bottleneck Events]
    end
    
    subgraph "Data Integration Stage"
        B1[unified_monitor.sh<br/>Data aggregation and formatting]
        B2[CSV header generation<br/>generate_csv_header()]
        B3[Symlink creation<br/>performance_latest.csv]
        B4[Real-time data stream<br/>tail -F monitoring]
    end
    
    subgraph "Real-time Analysis Stage"
        C1[EBS Bottleneck Detection<br/>Dynamic field mapping]
        C2[QPS Bottleneck Detection<br/>6-dimensional evaluation]
        C3[Event Recording<br/>JSON format logging]
    end
    
    subgraph "Offline Analysis Stage"
        D1[Comprehensive Analysis<br/>comprehensive_analysis.py]
        D2[QPS Analysis<br/>qps_analyzer.py]
        D3[Log Analysis<br/>validator_log_analyzer.py]
        D4[RPC Deep Analysis<br/>rpc_deep_analyzer.py]
    end
    
    subgraph "Visualization Output Stage"
        E1[HTML Report Generation<br/>32 professional charts]
        E2[Performance Visualization<br/>Trend analysis charts]
        E3[Advanced Charts<br/>Correlation analysis]
        E4[Archive Management<br/>Historical data comparison]
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

### 6. Symlink and File Rotation Mechanism

```mermaid
graph LR
    subgraph "File Creation Mechanism"
        A1[unified_monitor.sh startup]
        A2[Generate timestamped filename<br/>performance_YYYYMMDD_HHMMSS.csv]
        A3[Create symlink<br/>performance_latest.csv]
        A4[Write CSV header<br/>generate_csv_header()]
    end
    
    subgraph "Real-time Data Stream"
        B1[Data collection loop<br/>log_performance_data()]
        B2[Write to timestamped file<br/>safe_write_csv()]
        B3[EBS detector monitoring<br/>tail -F performance_latest.csv]
        B4[Dynamic field mapping<br/>CSV_FIELD_MAP]
    end
    
    subgraph "File Rotation Support"
        C1[Detect CSV format changes<br/>timestamp format validation]
        C2[Reinitialize mapping<br/>init_csv_field_mapping()]
        C3[Symlink auto-follow<br/>ln -sf new file]
        C4[Seamless data stream switch<br/>tail -F continues working]
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

## Data File Structure

### Archive Directory Structure

```
archives/run_*_YYYYMMDD_HHMMSS/
├── logs/
│   ├── performance_*.csv              # Main performance data (79 fields)
│   ├── monitoring_overhead_*.csv      # Monitoring overhead data (20 fields)
│   ├── block_height_monitor_*.csv     # Block height monitoring
│   ├── ena_network_*.csv              # ENA network monitoring
│   ├── blockchain_node_benchmark.log  # Main execution log
│   └── unified_monitor.log            # Monitoring system log
├── reports/
│   ├── performance_report_en_*.html   # English HTML report
│   ├── performance_report_zh_*.html   # Chinese HTML report
│   └── *.png                          # 32 professional charts
├── vegeta_results/
│   └── vegeta_*qps_*.json            # QPS test results per level
├── tmp/
│   ├── targets_single.json            # Single RPC method targets
│   ├── targets_mixed.json             # Mixed RPC method targets
│   └── monitoring_status.json         # Monitoring system status
└── test_summary.json                  # Test summary metadata
```

---

## Core Data Files

### 1. Performance Data File

**File Pattern**: `logs/performance_*.csv`  
**Total Fields**: 79 fields  
**Update Frequency**: Every 5 seconds (configurable)

#### Field Categories

| Category | Fields | Description |
|----------|--------|-------------|
| **Timestamp** | 1 | Data collection timestamp |
| **CPU Metrics** | 6 | cpu_usage, cpu_usr, cpu_sys, cpu_iowait, cpu_soft, cpu_idle |
| **Memory Metrics** | 3 | mem_used, mem_total, mem_usage |
| **DATA Device EBS** | 21 | IOPS, throughput, latency, utilization, AWS standard metrics |
| **ACCOUNTS Device EBS** | 21 | Same structure as DATA device |
| **Network Metrics** | 10 | Interface, bandwidth (Mbps/Gbps), packets per second |
| **ENA Network** | 6 | Allowance exceeded counters, connection tracking |
| **Monitoring Overhead** | 2 | IOPS and throughput overhead |
| **Block Height** | 6 | Local/mainnet height, diff, health status, data loss |
| **QPS Performance** | 3 | Current QPS, RPC latency, data availability |

### 2. Monitoring Overhead Data File

**File Pattern**: `logs/monitoring_overhead_*.csv`  
**Total Fields**: 20 fields  
**Update Frequency**: Every 5 seconds

#### Field Categories

| Category | Fields | Description |
|----------|--------|-------------|
| **Timestamp** | 1 | Data collection timestamp |
| **Monitoring System** | 4 | CPU, memory (percent/MB), process count |
| **Blockchain Node** | 4 | CPU, memory (percent/MB), process count |
| **System Resources** | 3 | CPU cores, memory (GB), disk (GB) |
| **System Usage** | 3 | CPU usage, memory usage, disk usage |
| **Memory Details** | 5 | Cached, buffers, anon pages, mapped, shared memory |

### 3. Test Summary File

**File Pattern**: `test_summary.json`  
**Format**: JSON

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

### 4. Vegeta QPS Test Results

**File Pattern**: `vegeta_results/vegeta_*qps_*.json`  
**Format**: JSON

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

## File Naming Conventions

### Timestamp Format

- **Pattern**: `YYYYMMDD_HHMMSS`
- **Example**: `20251025_150834`
- **Timezone**: UTC or local system time

### File Patterns

| File Type | Pattern | Example |
|-----------|---------|---------|
| Performance Data | `performance_*.csv` | `performance_20251025_150834.csv` |
| Monitoring Overhead | `monitoring_overhead_*.csv` | `monitoring_overhead_20251025_150834.csv` |
| Block Height | `block_height_monitor_*.csv` | `block_height_monitor_20251025_150834.csv` |
| ENA Network | `ena_network_*.csv` | `ena_network_20251025_150834.csv` |
| Vegeta Results | `vegeta_*qps_*.json` | `vegeta_1000qps_20251025_150834.json` |
| HTML Reports | `performance_report_{lang}_*.html` | `performance_report_en_20251025_150834.html` |

---

## Data Usage Examples

### Python Analysis

```python
import pandas as pd

# Load main performance data
df = pd.read_csv('logs/performance_*.csv')
print(f"Total fields: {len(df.columns)}")  # 79 fields

# Load monitoring overhead data
overhead_df = pd.read_csv('logs/monitoring_overhead_*.csv')
print(f"Overhead fields: {len(overhead_df.columns)}")  # 20 fields
```

### Shell Script

```bash
# Count total fields
head -1 logs/performance_*.csv | tr ',' '\n' | wc -l  # 79

# Extract specific columns
awk -F',' '{print $1,$77,$78}' logs/performance_*.csv  # timestamp, current_qps, rpc_latency_ms
```

---

## Related Documentation

- [Architecture Overview](./architecture-overview.md)
- [Configuration Guide](./configuration-guide.md)
- [Monitoring Mechanism](./monitoring-mechanism.md)
- [Blockchain Testing Features](./blockchain-testing-features.md)
