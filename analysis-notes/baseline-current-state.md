# Baseline 现状审计 (S0.1 交付物)

**日期**: 2026-05-20
**审计方式**: 全部基于 `grep` / `wc -l` / 读源码,**零猜测**
**对应 plan**: v1.4 §S0.1

---

## 1. 主入口调用链

入口: `blockchain_node_benchmark.sh` (978 行)

```
blockchain_node_benchmark.sh
├── L65 source config/config_loader.sh           # 配置层 (已含 S2 detector + k8s_paths 注入点)
├── L66 source utils/error_handler.sh
├── L67 source core/common_functions.sh
├── L120 python3 tools/fetch_active_accounts.py  # 数据预备(可选)
├── L143 tools/target_generator.sh               # 生成压测目标
├── L188 monitoring/monitoring_coordinator.sh start &   # 启监控(后台)
├── L271 core/master_qps_executor.sh             # QPS 压测核心
├── L222 monitoring/monitoring_coordinator.sh stop      # 停监控
├── L340 python3 utils/unit_converter.py --auto-process # 单位转换
├── L478 bash tools/ebs_analyzer.sh              # EBS 后分析
├── L515/520 python3 analysis/*.py               # 主分析(瓶颈窗口/性能悬崖)
├── L555 python3 analysis/comprehensive_analysis.py
├── L585/594/601 python3 analysis/qps_analyzer.py
├── L639 tools/benchmark_archiver.sh --archive
└── L681 python3 visualization/report_generator.py   # HTML 报告生成 ✓
```

**入口函数**(blockchain_node_benchmark.sh 内部):
- `execute_core_qps_test()` L242
- `execute_data_analysis()` L350
- `execute_bottleneck_window_analysis()` L534
- `execute_performance_cliff_analysis()` L568

---

## 2. 监控子任务 (monitoring_coordinator.sh)

`start_all_monitors()` L227 启动 5 个监控:

```bash
local monitors_to_start=("unified" "ena_network" "network" "block_height" "ebs_bottleneck")
```

对应脚本(`MONITOR_TASKS` 关联数组):
- `unified` → `unified_monitor.sh` (主监控,采 iostat / cgroup / mem / cpu)
- `ena_network` → AWS ENA allowance 监控
- `network` → 通用网络监控 (走 `network_unified_entry.sh` 分发)
- `block_height` → 区块链高度追踪
- `ebs_bottleneck` → EBS 瓶颈检测

monitoring/ 完整文件清单:
```
block_height_monitor.sh
bottleneck_detector.sh
cgroup_collector.py            ← S3 我新加
ena_network_monitor.sh
iostat_collector.sh
k8s_api_client.py              ← S5 我新加
kubelet_stats_client.py        ← S5 我新加
monitoring_coordinator.sh      ← 总协调
network/                       ← 5 个 NIC 后端
  ├── aws_ena.sh
  ├── gcp_gvnic.sh             ← Stage 1-3 已交付的 GCP gVNIC
  ├── gcp_virtio.sh            ← Stage 1-3 已交付的 GCP virtio
  ├── interface.sh
  └── other_none.sh
network_monitor.sh
network_unified_entry.sh       ← 分发器
pod_device_mapper.py           ← S5 我新加
unified_event_manager.sh
unified_monitor.sh             ← 主监控
```

---

## 3. 磁盘配置变量 (真实变量名,来自 `config/user_config.sh` L11-28)

| 变量 | 默认值 | 性质 |
|---|---|---|
| `LEDGER_DEVICE` | `nvme1n1` | **必选** — ledger 数据盘 |
| `ACCOUNTS_DEVICE` | `nvme2n1` | **可选** — accounts 数据盘 |
| `DATA_VOL_TYPE` | `io2` | LEDGER 元数据(命名遗留,`DATA_` 前缀实指 LEDGER) |
| `DATA_VOL_SIZE` | `2000` GB | |
| `DATA_VOL_MAX_IOPS` | `30000` | |
| `DATA_VOL_MAX_THROUGHPUT` | `700` MiB/s | |
| `ACCOUNTS_VOL_TYPE` | `io2` | |
| `ACCOUNTS_VOL_SIZE` | `500` GB | |
| `ACCOUNTS_VOL_MAX_IOPS` | `30000` | |
| `ACCOUNTS_VOL_MAX_THROUGHPUT` | `700` MiB/s | |

**关键校正(对 plan v1.4)**:
- ~~我之前 plan 写 `DATA_VOL_DEVICE` / `ACCOUNTS_VOL_DEVICE`~~ → 实际是 `LEDGER_DEVICE` / `ACCOUNTS_DEVICE`,plan 已修正
- 命名遗留:`DATA_VOL_*` 元数据系列(TYPE/SIZE/IOPS/THROUGHPUT)关联的是 `LEDGER_DEVICE` 而非新变量,**不要在 S0+ 中加 LEDGER_VOL_* 同义词**(会造成两套并行入口)

---

## 4. 1+1 磁盘可选性 — baseline 已实现 ✓ (**重大发现**)

`visualization/device_manager.py` (510 行) 已含完整的 ACCOUNTS 可选检测:

```python
class DeviceManager:
    def is_accounts_configured(self, df=None) -> bool:
        # L165-200
        # Detection logic:
        # 1. Primary: env vars ACCOUNTS_DEVICE / ACCOUNTS_VOL_TYPE / ACCOUNTS_VOL_MAX_IOPS
        # 2. Secondary (optional): if df provided, validate data columns
        accounts_device = os.getenv('ACCOUNTS_DEVICE', '').strip()
        accounts_vol_type = os.getenv('ACCOUNTS_VOL_TYPE', '').strip()
        accounts_max_iops = os.getenv('ACCOUNTS_VOL_MAX_IOPS', '').strip()
        ...
```

输出分支:
- 配置全 → `title_suffix='DATA & ACCOUNTS Devices'`, `devices=['DATA','ACCOUNTS']`
- 配置缺 → `"ACCOUNTS Device: Not Configured"` (报告里显式标注,不 crash)

**plan v1.4 § A.5.3 担心的"可选磁盘缺失 crash"已被 baseline 解决**。我的 S2-S5 新代码需要验证的是:
- cgroup_collector 在 ACCOUNTS=空 时不要 crash
- iostat 数据列缺 ACCOUNTS 时不要 crash
- 走 device_manager.is_accounts_configured() 做分支,不要重新实现一遍

---

## 5. HTML 报告章节(visualization/report_generator.py 4752 行)

已实现的 section 生成函数(每个对应 HTML 一节):

| 函数 | 行号 | 章节 |
|---|---|---|
| `generate_ebs_analysis_section` | L1623 | EBS 性能分析(瓶颈+基线统计) |
| `_generate_config_status_section` | L2051 | 配置状态 |
| `_generate_monitoring_overhead_section` | L2084 | 监控开销概览 |
| `_generate_monitoring_overhead_detailed_section` | L2256 | 监控开销详细 |
| `_generate_ebs_bottleneck_section` | L2715 | EBS 瓶颈分析 |
| `_generate_ena_warnings_section` | L3067 | ENA 网络告警 |
| `_generate_block_height_chart_section` | L3553 | 区块高度图表 |
| `_generate_data_loss_stats_section` | L3598 | 数据丢失统计 |
| `_generate_chart_gallery_section` | L3778 | 图表画廊 |
| `_generate_charts_section` | L3907 | 通用图表 |
| `_generate_bottleneck_section` | L4180 | 瓶颈分析 |

特性:
- 中英双语 i18n(L580+ 英文键、L1139+ 中文键,`self.t['key']` 取值)
- 标题: "Blockchain Node QPS Benchmark Report: Performance Analysis and Bottlenecks"

**缺失章节**(待 plan v1.4 各阶段补):
- ❌ RPC method 维度(S9 交付,S0 留占位)
- ❌ cgroup CPU/MEM/IO 19 字段图表(S3 已采,但 report_generator 没消费)
- ❌ K8s Pod 维度章节(S5 交付的 Pod→Device 映射没在 HTML 露)
- ❌ 8 链对称章节(目前是 Solana-centric)

---

## 6. visualization/ 目录(已存在,**S0+ 不要新建**)

```
advanced_chart_generator.py
chart_style_config.py
device_manager.py              ← 1+1 磁盘可选性逻辑住这
ebs_chart_generator.py
performance_visualizer.py
report_generator.py            ← HTML 入口 (4752 行)
```

S9 / SE 添加新图表(RPC method / cgroup / Pod 维度)**必须复用** `chart_style_config` + `device_manager.is_accounts_configured()`,不要重写。

---

## 7. tools/ 目录中已有的 mock 工具(**重大发现**)

```
tools/
├── benchmark_archiver.sh
├── ebs_analyzer.sh
├── ebs_bottleneck_detector.sh
├── fetch_active_accounts.py
├── framework_data_quality_checker.sh
├── mock_rpc_server.py            ← ✓ 已经有 mock!720 行 stdlib only
└── target_generator.sh
```

`tools/mock_rpc_server.py` 详情(基于源码):

- 720 行,纯 stdlib(http.server + socket-level WS upgrade),无 PyPI 依赖
- 启动: `python3 tools/mock_rpc_server.py --port 8899 --chain solana --ws-port 8900`
- 支持 chain: solana / ethereum (--chain 参数)
- **Solana method 已实现**: getSlot, getBlockHeight, getBalance, getAccountInfo,
  getTokenAccountBalance, getRecentBlockhash, getLatestBlockhash,
  getSignaturesForAddress, getTransaction, getVersion, getEpochInfo,
  getHealth, getIdentity, getGenesisHash
- **EVM method 已实现**: eth_blockNumber, eth_chainId, eth_getBalance,
  eth_getTransactionCount, eth_gasPrice, eth_maxPriorityFeePerGas,
  eth_getBlockByNumber, eth_getBlockByHash, eth_getTransactionByHash,
  eth_getTransactionReceipt, eth_getLogs, eth_call, eth_estimateGas, eth_getCode
- 支持 'single' 和 'mixed' rpc_methods 模式
- 请求计数: `_REQ_COUNT_BY_METHOD` 字典,可作为 access log
- Source of truth 标注: `config/config_loader.sh L388-600 (UNIFIED_BLOCKCHAIN_CONFIG)`
- WebSocket: socket-level upgrade(L492 WS_MAGIC,L589 sec-websocket-key 处理)

**对 plan v1.4 的校正**:
- ~~S0.2 "写 tools/mock_blockchain_node.py 1.5h"~~ → 改为 "**复用** tools/mock_rpc_server.py + 补缺 method (Sui/Aptos/Starknet/Bitcoin/Bsc/Base)"
- 估时从 1.5h 降到 ~0.5h (只补 4-6 个链的 method 占位)
- S9 RPC method 分析也要复用 `_REQ_COUNT_BY_METHOD` 的 access log 格式

---

## 8. 已有分析器(analysis/ 目录)

```
analysis/
├── comprehensive_analysis.py
├── cpu_ebs_correlation_analyzer.py   ← CPU↔EBS 相关性
├── network_analyzer.py
├── qps_analyzer.py
└── rpc_deep_analyzer.py              ← ✓ RPC 深度分析已有!
```

**重大发现**: `analysis/rpc_deep_analyzer.py` **已存在**。S9 "RPC method 级监控 10h" 必须先读这个文件,看 baseline 已经做到哪一步,**避免重写已有的功能**。

---

## 9. config/ 目录全清单

```
config/
├── cloud_provider.sh             ← AWS/GCP/Other 三态探测(Stage 1-3 已交付)
├── config_loader.sh              ← 主配置加载入口
├── deployment_mode_detector.sh   ← S2 我新加(6 mode 瀑布)
├── internal_config.sh
├── k8s_paths.sh                  ← S2 我新加(HOST_PROC 等)
├── system_config.sh
└── user_config.sh                ← 用户配置(LEDGER_DEVICE 等)
```

S2 已正确接入(`config_loader.sh` L342/L348 调用 detector 和 resolve_k8s_paths)。

---

## 10. 对 plan v1.4 的修正清单

| plan 原文 | 校正 | 影响阶段 |
|---|---|---|
| `DATA_VOL_DEVICE` / `ACCOUNTS_VOL_DEVICE` | → `LEDGER_DEVICE` / `ACCOUNTS_DEVICE` | §A.5.3, S0.3(已修) |
| S0.2 "写 mock_blockchain_node.py 1.5h" | → "复用 tools/mock_rpc_server.py + 补 4-6 链 method, 0.5h" | S0.2 |
| "1+1 磁盘缺失分支" 当作新工作 | → baseline 已实现 `device_manager.is_accounts_configured()`,我只需验证 S2-S5 新代码不破坏 | S5.5 |
| "HTML 模板留 RPC method 占位" | → 已知 `analysis/rpc_deep_analyzer.py` 存在,先读再决定占位 vs 复用 | S0.3, S9 |
| `tools/mock_blockchain_node.py` 新文件名 | → 用现有 `tools/mock_rpc_server.py` | S0.2, S0.3, e2e_smoke.sh |

---

## 11. S0 后续步骤(基于事实修正)

### S0.2 改为:补 mock_rpc_server.py 缺失链 (0.5h)
1. 读 `tools/mock_rpc_server.py` 完整源码
2. 看 `--chain` 当前支持的链,确认缺失:Sui / Aptos / Starknet / Bitcoin / Bsc / Base
3. 加 `handle_<chain>()` 函数,每条链给 3-5 个核心 method 的静态响应
4. **不重写已有的 Solana/EVM 部分**,只追加

### S0.3 改为:写 single_disk_workload + e2e_smoke (1h)
1. `tools/single_disk_workload_profile.sh`:
   - 设 `LEDGER_DEVICE="sda"`(cloudtop root)
   - 留 `ACCOUNTS_DEVICE=""` 验可选分支
   - dd workload + 1GB 写量护栏
2. `tools/e2e_smoke.sh`:
   - source `single_disk_workload_profile.sh`
   - 启 `mock_rpc_server.py`
   - 调 `blockchain_node_benchmark.sh` 入口(短跑 60s)
   - 验证产物:CSV ≥ 50 行、HTML > 10KB、含 "iostat" / "cgroup" / "EBS" 章节

### S5.5 改为(更精准):
1. 跑 e2e_smoke,看 S3 cgroup_collector 的 19 字段 CSV **是否真被 report_generator 消费**
2. 看 monitoring_coordinator 的 5 个监控里有没有调 cgroup_collector → **大概率没有**(因为 S3 commit 只新加文件没改 coordinator)→ 这是 L3 必抓的真空白
3. 验证 ACCOUNTS_DEVICE="" 时全链路不 crash(device_manager 已支持,验证我新代码也支持)

---

## 12. 还没确认的(下次审计补)

- [ ] `core/master_qps_executor.sh` 入口参数和输出 CSV 格式
- [ ] `analysis/rpc_deep_analyzer.py` 已支持哪些 method 维度
- [ ] `network_unified_entry.sh` 怎么分发到 5 个 NIC 后端
- [ ] HTML 章节的 i18n key 全清单(决定 RPC method 章节怎么加翻译)
- [ ] `config/internal_config.sh` 和 `system_config.sh` 内容

不阻塞 S0.2 / S0.3,在 S5.5 跑 e2e 暴露真空白后再补。
