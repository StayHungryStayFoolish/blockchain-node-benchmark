# 产出文件全量清单 × 需求归属 × 命名烙印状态 (总表)

> 2026-05-31 落盘。触发: 用户"关于所有文件生成、使用的需求、解耦的分析完成了么"。
> 方法: 静态枚举(grep 文件名字面量, 非跑一次)所有写文件点 → 去重 185 个字面量
> → 剔除测试 fixture(fake-node 录制夹具)/纯文档 URL → 聚焦运行+对外产出物。
> 需求锚: skill `blockchain-node-benchmark-architecture` 三北极星 NS-1/2/3 + SSOT docs/NORTH-STAR.md。

## 北极星速查
- **NS-1**: 36 链零代码加链 (adapter/proxy 解析层零代码覆盖)
- **NS-2**: per-method 资源归因 (每 RPC 方法的 CPU/磁盘/网络消耗)
- **NS-3**: 零代码覆盖 adapter + proxy 解析层
- 横切: 性能基准/瓶颈检测/可视化报告 (服务三北极星的对外交付)

---

## A. 核心数据 CSV (运行时采集, 下游分析输入)

| 产出文件 | 写它的模块 | 需求归属 | 烙印状态 |
|---|---|---|---|
| `performance_${TS}.csv` / `performance_latest.csv` | unified_monitor.sh:208/2280, master_qps_executor.sh:477/582 | NS-2 资源归因主数据 | ✅ 中性 (字段已 normalized 化, ADR-0002) |
| `monitoring_overhead_${TS}.csv` | config_loader.sh:303 | 横切: 监控自身开销 | ✅ 中性 |
| `block_height_monitor_${TS}.csv` | config_loader.sh:295 | NS-1 链同步健康 | ✅ 中性 |
| `ena_network_${TS}.csv` | ena_network_monitor.sh:30 | 横切: 网络限额监控 | 🔴 **ENA 烙印 — 待裁** (D2 锁 ena→KEEP, 但对外 CSV 名是否适用 KEEP 需拍板) |
| `network_metrics.csv` | network_analyzer.py:10 (读取名) | 横切: 网络分析输入 | ✅ 中性 |
| `proxy_method.csv` | report_generator.py:4233 (读取名) | NS-2/NS-3 per-method 归因 | ✅ 中性 |
| `temp_performance_data_{pid}_{rid}.csv` | comprehensive_analysis.py:795 | 横切: 分析临时文件 | ✅ 中性 |

## B. 状态/事件 JSON (跨进程共享, MEMORY_SHARE_DIR)

| 产出文件 | 写它的模块 | 需求归属 | 烙印状态 |
|---|---|---|---|
| `bottleneck_status.json` / `bottleneck_counters.json` | bottleneck_detector.sh:122/123, master_qps_executor.sh:433 | 横切: 瓶颈检测 | ✅ 中性 |
| `bottleneck_analysis_${TS}.json` | master_qps_executor.sh:690 | 横切: 瓶颈分析 | ✅ 中性 |
| `bottleneck_analysis_result.json` | comprehensive_analysis.py:923 | 横切: 综合瓶颈 | ✅ 中性 |
| `latest_metrics.json` / `unified_metrics.json` | master_qps_executor.sh:475/476, unified_monitor.sh:2032/2055 | NS-2 实时指标 | ✅ 中性 |
| `qps_status.json` | config_loader.sh:299 | 横切: QPS 状态 | ✅ 中性 |
| `unified_events.json` / `event_notification.json` | unified_event_manager.sh:18/145 | 横切: 事件总线 | ✅ 中性 |
| `data_loss_stats.json` | block_height_monitor.sh:451 | 横切: 数据完整性 | ✅ 中性 |
| `block_height_monitor_cache.json` | config_loader.sh:294 | NS-1 链同步缓存 | ✅ 中性 |
| `monitoring_status.json` / `monitor_pids.txt` | monitoring_coordinator.sh:23/26 | 横切: 进程协调 | ✅ 中性 |
| `targets_mixed.json` / `targets_single.json` | config_loader.sh:297/298 | NS-1 多链目标 | ✅ 中性 |
| `ena_baseline.json` | bottleneck_detector.sh:537 | 横切: ENA 限额基线 | 🔴 **ENA 烙印 — 待裁** (内部共享态, 同 D2 簇) |
| `performance_cliff_analysis.json` | qps_analyzer.py:1193 | 横切: 性能悬崖 | ✅ 中性 |

## C. 图表 PNG (对外可视化交付物 — 重点中立化对象)

| 产出文件 | 写它的模块 | 需求归属 | 烙印状态 |
|---|---|---|---|
| `disk_bottleneck_analysis.png` | disk_chart_generator.py:35 | 横切: 磁盘瓶颈 | ✅ 已 ebs→disk |
| `disk_bottleneck_correlation.png` | disk_chart_generator.py:33 | 横切 | ✅ 已改 |
| `disk_capacity_planning.png` | disk_chart_generator.py:31 | 横切 | ✅ 已改 |
| `disk_iostat_performance.png` | disk_chart_generator.py:32 | 横切 | ✅ 已改 |
| `disk_normalized_comparison.png` | disk_chart_generator.py:36 | 横切 | ✅ 已改 (aws_standard→normalized) |
| `disk_performance_overview.png` | disk_chart_generator.py:34 | 横切 | ✅ 已改 |
| `disk_time_series_analysis.png` | disk_chart_generator.py:37 | 横切 | ✅ 已改 |
| `cpu_disk_correlation_visualization.png` | performance_visualizer.py:421/529 | NS-2 资源相关 | ✅ 已 ebs→disk |
| `ena_limitation_trends.png` | advanced_chart_generator.py:821 | 横切: 网络限额 | 🔴 **ENA 烙印 — 待裁** |
| `ena_connection_capacity.png` | advanced_chart_generator.py:897 | 横切 | 🔴 **ENA 烙印 — 待裁** |
| `ena_comprehensive_status.png` | advanced_chart_generator.py:1053 | 横切 | 🔴 **ENA 烙印 — 待裁** |
| `performance_overview.png` | performance_visualizer.py:362 | 横切 | ✅ 中性 |
| `performance_cliff_analysis.png` | qps_analyzer.py:421 | 横切 | ✅ 中性 |
| `qps_performance_analysis.png` / `qps_trend_analysis.png` | qps_analyzer.py:769, performance_visualizer.py:1665 | 横切: QPS | ✅ 中性 |
| `block_height_sync_chart.png` | performance_visualizer.py:2406 | NS-1 链同步 | ✅ 中性 |
| `device_performance_comparison.png` | performance_visualizer.py:1105 | NS-2 | ✅ 中性 |
| `await_threshold_analysis.png` / `util_threshold_analysis.png` | performance_visualizer.py:910/650 | 横切: 阈值 | ✅ 中性 |
| `bottleneck_identification.png` | performance_visualizer.py:2250 | 横切 | ✅ 中性 |
| `monitoring_overhead_analysis.png` / `monitoring_impact_chart.png` | performance_visualizer.py:1252, report_generator.py:2335 | 横切: 监控开销 | ✅ 中性 |
| `resource_distribution_chart.png` / `resource_efficiency_analysis.png` | report_generator.py:2320, performance_visualizer.py:1835 | NS-2 资源 | ✅ 中性 |
| `smoothed_trend_analysis.png` / `performance_trend_analysis.png` | performance_visualizer.py:1550, advanced_chart_generator.py:659 | 横切: 趋势 | ✅ 中性 |
| `pearson/comprehensive/negative/linear_*correlation*.png` (5 张) | advanced_chart_generator.py:289/542/468/387/1164 | NS-2 相关性 | ✅ 中性 |
| `comprehensive_analysis_charts.png` | comprehensive_analysis.py | 横切: 总览 | ✅ 中性 |

## D. 报告 HTML/TXT (对外终交付)

| 产出文件 | 写它的模块 | 需求归属 | 烙印状态 |
|---|---|---|---|
| `performance_report_{en,zh}_${TS}.html` | report_generator.py:2074 | 横切: 主报告 | ✅ 文案已中立化 (baseline 文案本轮改回中性 Disk Baseline) |
| `degraded_report.html` | degraded_report.py:371 | 横切: 降级报告 | ✅ 中性 |
| `*_insights.txt` (相关性洞察) | advanced_chart_generator.py:1203 | NS-2 | ✅ 中性 |
| `qps_*_report.txt` | bottleneck_detector.sh:659 | 横切: QPS 报告 | ✅ 中性 |
| `${data_file}_summary.txt` | disk_bottleneck_detector.sh:560 | 横切: 磁盘摘要 | ✅ 已 ebs→disk |
| `monitoring_performance_report_${TS}.txt` | unified_monitor.sh:1081 | 横切 | ✅ 中性 |
| `error_recovery_report_${TS}.txt` | unified_monitor.sh:2682 | 横切: 错误恢复 | ✅ 中性 |
| `vegeta_${qps}qps_${TS}.{txt,json}` | master_qps_executor.sh:811/584 | 横切: 压测原始 | ✅ 中性 |

## E. 日志 LOG (运行诊断)

| 产出文件 | 写它的模块 | 烙印状态 |
|---|---|---|
| `unified_monitor.log` / `master_qps_executor.log` / `bottleneck_detector.log` | 各组件 | ✅ 中性 |
| `disk_analyzer.log` / `disk_bottleneck_detector.log` | tools/disk_*.sh | ✅ 已 ebs→disk |
| `network_monitor.log` | network_monitor.sh:33 | ✅ 中性 |
| `ena_network_monitor.log` | ena_network_monitor.sh:26 | 🔴 **ENA 烙印 — 待裁** |
| `framework_errors_$(date).log` | error_handler.sh:23 | ✅ 中性 |
| `${component}_${type}_${TS}.log` (统一日志) | unified_logger.sh:94 | ✅ 中性 |
| `monitoring_errors_${TS}.log` / `monitoring_performance_${TS}.log` | config_loader.sh:305/304 | ✅ 中性 |

## F. 合理保留 (非烙印 — 不需改)

| 落点 | 说明 |
|---|---|
| `aws_provider.sh:45-48` AWS 文档 URL (ebs/ena-express/imds/provisioned-iops) | AWS provider **内部**引用 AWS 官方文档, 天经地义; GCP provider 自有自己的 URL。正确隔离 |
| fake-node fixtures (`*.json` 各链 record_*_fixtures.sh) | 测试夹具, 非框架运行产出物, 不在中立化范围 |

---

## 🎯 总结论

### 解耦分析 = 完成 (高置信, read body 实证)
- 两 registry (csv_schema ↔ network_field) 零交叉引用, disk 改名不碰 network
- network 四条边 writer↔reader 字节对账通过
- 调用点字符串 58 命中/7 文件全用新名

### 需求归属 = 完成 (本表)
- 全部运行+对外产出物已映射到 NS-1/NS-2/横切

### 命名烙印 = 仅剩 1 簇待你裁定
**ENA 烙印簇** (5 个产出文件, 性质同 ADR-0002/D2 锁定的 "ena→KEEP"):
1. `ena_network_${TS}.csv` (对外 CSV)
2. `ena_baseline.json` (内部共享态)
3. `ena_limitation_trends.png` / `ena_connection_capacity.png` / `ena_comprehensive_status.png` (3 张对外 PNG)
4. `ena_network_monitor.log` (日志)

**裁定点**: D2 当时锁 "ena→KEEP" 是针对**代码标识符**(ENA=AWS 专属网卡, GCP 用 gVNIC/virtio, 语义专属)。
但**对外产出物文件名**(尤其 CSV/PNG 会被拿到别处分析)是否同样 KEEP, 还是中立化为 `network_*`?
→ 这是命名多义裁定, 按用户偏好"对外交付物必须中立, 命名冲突必须用户拍板", 留待用户决定, AI 不自决。

### 其余未决: baseline 多义簇 — ✅ 语义已查实 (2026-05-31, 以沉淀文件为准)

**`disk_chart_generator.py:67` / `device_manager.py:312` 的 `data_baseline_iops` 语义已锁定**:

权威源: `decisions/ADR-0002-five-layer-disk-metric-naming.md` + skill ref `disk-field-four-layer-naming-map.md` (DEFINITIVE)。

- 数据来源 = `os.getenv('DATA_VOL_MAX_IOPS')` (device_manager.py:312); 用途 = 利用率公式**分母** (device_manager.py:308 注释自述"卷的基线能力"); 消费端 disk_chart_generator.py:67 已赋给 `self.data_provisioned_iops`。
- → **语义 = 层3 配置能力 (额定上限/分母)**, 按 ADR-0002 五层定案**正当名 = `provisioned`**, 非 baseline。
- baseline 一词在本仓库**唯一正当归属 = 层5 `baseline_io_kib`** (AWS 16KiB/GCP 4KiB 换算基准块常数, 神圣不动)。此处 `data_baseline_iops` 是 ADR-0002 之前的**层3 误名残留** (命名债务)。
- device_manager.py:307-310 "baseline 仅为业务语义"的辩护注释 = ADR-0002 前旧认知, 按 ref §0.1#3 "其他任何地方出现 baseline 当配置能力均属待修缮命名债务", **不构成反对改名理由**。

**处置 (用户拍板)**: 语义澄清本条落盘即可; **改名动作 (data/accounts_baseline_iops/throughput dict key → provisioned_*, 9 处字符串字面量 writer-first 同步) 归阶段6 CP-3 disk 字段治理主线一并做** (与 ref §5 第5步"清理层3 混名"同批), 不单独零敲。
- writer (device_manager.py:312/313/331/332 组 dict + :342-345 自引用 + :591 硬编码判断) 与 reader (disk_chart_generator.py:67/68/71/72/73) 必须同步改, 否则 KeyError 静默断链。
- 该组 key 是**业务配置 dict**, 不经 CSVSchemaRegistry (注释 §309 已说明非 CSV 物理列), 故不在 ref §3 registry reader 清单内, 属 ref §5 第5步层3 混名清理范畴。

---

## 🔴 2026-05-31 续: ENA 烙印簇深挖 — 发现 parallel-entry-trap, 升级为架构决策 (未动代码)

> 用户选"方向2 (对外产出物去烙印 ena_→network_)"后, 执行前按 token-level 纪律做 writer↔reader 全仓对账,
> grep 炸出**新旧并行入口**真相, 该问题性质从"改名"升级为"清理 parallel-entry 的架构决策" → 不自决, 落盘待裁。

### 真相: 网络监控三套实现并存
| 实现 | 文件 | 产出 CSV | 派发状态 | 性质 |
|---|---|---|---|---|
| 旧 (AWS legacy) | `monitoring/ena_network_monitor.sh` | `ena_network_${TS}.csv` | coordinator:35 `["ena_network"]` 仍注册 | AWS-only legacy |
| 新 (Y+ 架构) | `monitoring/network_monitor.sh` + `monitoring/network/{aws_ena,gcp_gvnic,gcp_virtio,other_none,interface}.sh` | `network_${TS}.csv` | coordinator:36 `["network"]` 已注册 | 平台感知 driver 分流, **已中立** |
| provider getter | aws→`ena_network_monitor` (aws_provider.sh:34) / gcp→`gvnic_network_monitor` (gcp_provider.sh:34) | — | getter 仍指旧的 | 派发名 |

**自证据 (代码注释)**:
- `monitoring/network/aws_ena.sh:3` "AWS ENA 实现 (driver=ena, 替代原 ena_network_monitor.sh)"
- `network_monitor.sh:5` "Replaces AWS-only ena_network_monitor.sh with platform-aware Y+ architecture"
- `network_monitor.sh:10` "Old ena_network_monitor.sh continues to coexist for AWS legacy compatibility"
- `network_monitor.sh:47` "Output CSV path — uses 'network_' prefix (not 'ena_network_') to distinguish from legacy"

### 矛盾点
1. 新架构 network_monitor.sh **已存在/已注册/产出已中立** (network_*.csv) → 中立化已做一半
2. 旧 ena_network_monitor.sh 仍 coexist/仍注册, aws_provider.sh:34 getter 仍指旧的 → **parallel-entry-trap** (skill §4#5 + §5)
3. aws_ena.sh 注释说自己替代 legacy, 但 getter 没切过去

### 为什么不自决 (停)
- 选 A (切新架构+下线 legacy): **动 AWS 生产路径**, 需验"AWS 下 network_monitor 能完全代 ena", 撞 memory"破坏性操作铁律"+skill"parallel-entry 不自决" → 用户超时未拍板时**不冒进**
- 选 B (只改名保并存): 撞新架构 network_*.csv 名, 排除
- 选 D (全 KEEP): 撤销用户已选方向2, 不符
- **C (本轮只动零架构风险部分) 为兜底**, 但深挖后连 PNG 都不宜盲改 (见下)

### 3 张 ENA PNG — 实为 D2 "ena→KEEP" 正当归属, 不宜改
- `ena_limitation_trends.png` / `ena_connection_capacity.png` / `ena_comprehensive_status.png`
- 由 advanced_chart_generator.py 生成, 内容 = **ENA allowance 限额** (PPS/带宽/连接跟踪上限)
- 这是 **ENA 特有指标语义** (不是"通用磁盘统计被误命名"), 恰是 D2"ena→KEEP"本意覆盖对象
- i18n 文案本身就写 "AWS ENA network limitation" (report_generator.py:547) — 内容确实 AWS ENA 专属
- → 与 aws_ebs_baseline_stats (假烙印/真通用) **性质相反**: 此处是真 AWS 专属, KEEP 正确

### 本轮结论 (零代码改动)
- **未动任何代码** (符合"高风险不自决+发现即落盘+宁停不冒进")
- ✅ **2026-05-31 用户已拍板「C + KEEP」, 锁定为 `decisions/ADR-0003-ena-imprint-keep-and-parallel-entry-defer.md`**:
  - D1 (KEEP): 5 个 ENA 产出物 (ena_network_*.csv / ena_baseline.json / 3 张 PNG / log) **保留 ena_ 前缀** (真 AWS 专属语义, 非误命名)
  - D2 (C, defer): ena_network legacy 入口 parallel-entry **暂不清理** (动 AWS 生产路径, 需 AWS L3 验收护航, 留架构层统一清理)
  - 撤销线见 ADR-0003
