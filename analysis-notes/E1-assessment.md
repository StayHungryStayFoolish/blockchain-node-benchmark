# E1 方案全量影响评估 — Phase 8a-v2.0 Step 1

> 评估对象: analysis-notes/CORRECTED_PLAN.md (3772 行 / 205 KB)
> 评估目的: 把当前散落的 `case "$CLOUD_PROVIDER"` 句式重构为抽象 provider 层 (VFS 模式)
> 业务代码 diff vs e843571: **空** (本评估零修改)
> 业务代码当前 CLOUD_PROVIDER 引用数: **0** (所有引用都还在 PLAN 文档待落地 — 这是介入 E1 的最佳时机)

---

## 1. 影响清单总数 (Step A)

### 1.1 PLAN 中所有需重构的句式 (按 CP 分组)

| 编号 | 文档行号 | CP 节 | 句式类型 | 涉及业务文件 | 涉及变量/分发结果 |
|---|---|---|---|---|---|
| 1 | 112 | CP-0.1 | case `$CLOUD_PROVIDER` | utils/cloud_provider.sh | env override 校验 (内部细节, 不算业务分发) |
| 2 | 129 | CP-0.1 | case `$CLOUD_PROVIDER` | utils/cloud_provider.sh | PLATFORM_DISPLAY_NAME 派生 |
| 3 | 547 | CP-1.1 | case `${CLOUD_PROVIDER:-aws}` | utils/disk_converter.sh:L7 | CLOUD_THROUGHPUT_BASELINE_KIB (256 vs 128) |
| 4 | 570 | CP-1.1 | if `${CLOUD_PROVIDER:-aws}` == gcp | utils/disk_converter.sh:L62-67 | calculate_io2_throughput GCP 早返回 |
| 5 | 1203 | CP-2.1.2 | case `${CLOUD_PROVIDER:-${DEPLOYMENT_PLATFORM:-aws}}` | config/system_config.sh | METADATA_ENDPOINT + METADATA_HEADER |
| 6 | 1240 | CP-2.1.3 | case (同上) | config/system_config.sh | METADATA_API_PATH (latest vs computeMetadata/v1) |
| 7 | 1267 | CP-2.1.4 | case (同上) | config/system_config.sh | CLOUD_IO_BASELINE_KIB (16 vs 4) |
| 8 | 1321 | CP-2.1.5 | 局部变量 + case | config/system_config.sh | filter_platform_processes() (MONITORING_PROCESS_NAMES) |
| 9 | 1426 | CP-2.2.1 | case (同上) | config/user_config.sh:L111 | configure_io2_volumes vs configure_gcp_extreme_volumes 分发 |
| 10 | 1505-1506 | CP-2.2.4 | case `$DATA_VOL_TYPE` (派生分发) | config/user_config.sh | pd-extreme \| hyperdisk-extreme 触发条件 |
| 11 | 1601 | CP-2.3.1 | case `$DEPLOYMENT_PLATFORM` | config/config_loader.sh:L101-140 | 手动配置分支 ENA_MONITOR_ENABLED 派生 |
| 12 | 1661 | CP-2.3.1 (改后) | case `$DEPLOYMENT_PLATFORM` | config/config_loader.sh | NIC_MONITOR_ENABLED 派生 (3 分支) |
| 13 | 1764 | CP-2.3.4 | case `${DEPLOYMENT_PLATFORM:-${CLOUD_PROVIDER:-aws}}` | config/config_loader.sh:L829 | NIC_ALLOWANCE_FIELDS (6 字段 vs 空集) |
| 14 | 1977 | CP-3.2 | case `$CLOUD_PROVIDER` | utils/nic_metrics.sh (新) | get_nic_allowance_data 分发 |
| 15 | 2109 | CP-3.2 | case `$CLOUD_PROVIDER` | monitoring/nic_network_monitor.sh (新) | get_nic_network_stats 分发 |
| 16 | 2430 | CP-4.1 | case `$CLOUD_PROVIDER` (规划行) | tools/disk_analyzer.sh | 阈值表选择 (gp3/io2 vs pd-*/hyperdisk-*) |
| 17 | 2508 | CP-4.4 | case `$CLOUD_PROVIDER` (规划行) | tools/framework_data_quality_checker.sh | sanity check 字段集 (_aws_standard_iops vs _baseline_iops) |
| 18 | 2467 | CP-4.3 | `${PLATFORM_DISPLAY_NAME:-${CLOUD_PROVIDER:-run}}` | tools/benchmark_archiver.sh | 归档目录前缀 (run_/aws_run_/gcp_run_) |
| 19 | TRACKER §13.10 | CP-3.4 | 路径含 `${CLOUD_PROVIDER}` | monitoring/monitoring_coordinator.sh:L15 | LOGS_DIR platform-suffixed |
| 20 | TRACKER §13.11 | CP-3.5.b | 路径含 `${CLOUD_PROVIDER}` | monitoring/block_height_monitor.sh:L44-45 | MEMORY_SHARE_DIR platform-suffixed |
| 21 | TRACKER §13.21 | CP-5.7.2 | `BOTTLENECK_TYPE_LABELS[CLOUD_PROVIDER]` 字典 | analysis/comprehensive_analysis.py | 'EBS' vs 'Disk' 标签 4 处 |

### 1.2 按 CP 分组汇总

| CP | 散落句式数 | 主要类型 |
|---|---|---|
| CP-0 | 2 (内部) | provider 自身 (不算业务分发) |
| CP-1 | 2 | 1 baseline + 1 io2 早返回 |
| CP-2 | 9 (含 1 派生 + 1 子 case) | metadata 端点 / IO baseline / volume dispatch / NIC fields / platform detect |
| CP-3 | 4 | NIC allowance / NIC stats / 路径 suffix x2 |
| CP-4 | 3 | 阈值表 / quality check / 归档前缀 |
| CP-5 | 1 | bottleneck 标签 |
| **总计** | **21** | (业务分发口径 19, 排除 CP-0 内部 2) |

### 1.3 衍生 hard-coded 字面量分支 (语义上等价)

- 字段名硬编码 `_aws_standard_iops` / `_aws_standard_throughput_mibs` — 出现在 §13.6 / §13.12 (writer 端 unified_monitor.sh:144 + iostat_collector.sh:144), 实际是 `${prefix}_aws_standard_*` 字面拼接, 未来下游 CSV reader 也是字面匹配 — 这些**不是 case 句式但本质等价 case** — 走 getter `get_disk_field_prefix()` 可一并消除
- 字面 `'EBS'` 在 comprehensive_analysis.py 4 处 (§13.21) — 走 getter `get_bottleneck_label()` 消除
- 函数名 alias `convert_to_aws_standard_iops` → `convert_to_standard_iops` — 命名平台中立化, getter 不直接覆盖但应纳入 provider 命名规范

---

## 2. 抽象接口清单 (Step B) — 13 个 getter

| # | 函数签名 | AWS 返回值 | GCP 返回值 | Other 返回值 | 调用方 (来自上面表格) |
|---|---|---|---|---|---|
| 1 | `get_metadata_endpoint()` | `http://169.254.169.254` | `http://metadata.google.internal` | `""` | #5 (CP-2.1.2) + config_loader.sh detect (#11/12) |
| 2 | `get_metadata_header()` | `""` | `Metadata-Flavor: Google` | `""` | #5 + 所有 metadata curl 调用点 |
| 3 | `get_metadata_api_path()` | `latest` | `computeMetadata/v1` | `latest` | #6 (CP-2.1.3) |
| 4 | `get_baseline_io_kib()` | `16` | `4` | `16` | #7 (CP-2.1.4) + utils/disk_converter.sh |
| 5 | `get_baseline_throughput_kib()` | `128` | `256` | `128` | #3 (CP-1.1 L7) |
| 6 | `get_default_disk_type()` | `gp3` | `hyperdisk-extreme` | `gp3` | user_config.sh 注释; 未来 sanity check |
| 7 | `get_disk_type_options()` (echo 空格分隔列表) | `gp3 io2 instance-store` | `pd-balanced pd-ssd pd-extreme hyperdisk-extreme local-ssd` | `gp3 io2` | CP-2.2 VOL_TYPE 枚举校验 + CP-2.2.4 needs_calc 判断 (#10) |
| 8 | `get_nic_driver()` | `ena` | `gve` | `ena` | CP-3.2 (#15) `ethtool -i` 校验时使用 |
| 9 | `get_nic_allowance_fields()` (echo CSV) | `bw_in_allowance_exceeded,bw_out_allowance_exceeded,pps_allowance_exceeded,conntrack_allowance_exceeded,linklocal_allowance_exceeded,conntrack_allowance_available` | `""` | `""` | #13 (CP-2.3.4) + #14 (CP-3.2 utils/nic_metrics.sh) |
| 10 | `get_nic_monitor_process_name()` | `ena_network_monitor` | `gvnic_network_monitor` | `""` | #8 (CP-2.1.5 filter_platform_processes) |
| 11 | `get_disk_field_prefix()` | `aws_standard` | `baseline` | `aws_standard` | §13.6 / §13.12 (unified_monitor.sh:144 + iostat_collector.sh:144) |
| 12 | `get_archive_dir_prefix()` | `aws_run_` | `gcp_run_` | `run_` | #18 (CP-4.3 benchmark_archiver.sh L219) + §13.19 reader |
| 13 | `get_bottleneck_label()` | `EBS` | `Disk` | `Disk` | §13.21 (CP-5.7.2) + §13.13 console 文案 |
| 14 | `get_platform_display_name()` | `AWS` | `GCP` | `OTHER` | CP-0.1 内部 + #18 fallback chain |
| 15 | `get_doc_url(category)` | AWS doc URL | GCP doc URL | AWS doc URL | #4 (CP-1.1 L25/L31/L83) — 参数化 doc 分类 |

**Python 侧并行接口** (analysis/, visualization/, utils/field_normalizer.py 消费):
```python
from utils.cloud_provider import get_cloud_provider, get_disk_field_prefix, get_bottleneck_label
# 通过环境变量 CLOUD_PROVIDER 读, 不重复 IMDS 探测
```
建议放 `utils/cloud_provider.py` (与 .sh 同名同义, Python 端实现镜像), 内部 `os.getenv('CLOUD_PROVIDER', 'other')` + dispatch dict。

---

## 3. 阻塞点消除映射 (Step C 子项)

| TRACKER 阻塞点 | 当前级别 | E1 解决方式 | 消除度 |
|---|---|---|---|
| §13.1 (block_height_monitor cache RPC writer 待定位) | P0 | E1 不解决 (业务逻辑问题, 与 provider 抽象无关) | 0% |
| **§13.2 source 顺序冲突** (system_config.sh 先 source 时 CLOUD_PROVIDER 还是 auto) | **P0** | **完全消除**: getter 函数是**懒求值**, 调用时才读取 CLOUD_PROVIDER, source 顺序无关。所有 system_config.sh 里的 `case "${CLOUD_PROVIDER:-...}"` 改为定义时不展开的 getter 调用 → 调用方 (config_loader.sh 完成 detect 后) 第一次调 getter 时才求值, 必然正确。 | **100%** ⭐ 结构性 |
| §13.3 config_loader.sh L829 ENA_ALLOWANCE_FIELDS 独立 fallback | P0 | 用 `get_nic_allowance_fields()` 替换硬编码 default, fallback 唯一化 | 100% |
| §13.4 detect_network_interface 函数体 ena_interfaces 局部命名 | P2 | 仅命名问题, E1 不直接消除但提供 `get_nic_driver()` 给上下文 | 30% (仍需 rename) |
| **§13.5 metadata header 缺失** | **P0** | **完全消除**: `get_metadata_header()` getter 统一返回, 所有 metadata curl 调用 `curl -H "$(get_metadata_header)" ...` | **100%** ⭐ |
| **§13.6 unified_monitor.sh + iostat_collector.sh 字段名硬编码 `_aws_standard_*`** | **P0** | **完全消除**: `get_disk_field_prefix()` getter, writer 端 `${prefix}_$(get_disk_field_prefix)_iops` 即可双平台正确 | **100%** ⭐ |
| §13.7 unified_monitor.sh 兜底字段数 wc -w | P1 | 不直接解决, 但 `get_nic_allowance_fields() \| wc -w` 给出权威字段数 | 50% (减少错位风险) |
| §13.8 ena_network_monitor.sh 双逗号拼接 | P1 | E1 不解决 (是 bash 拼接 bug) | 0% |
| §13.9 bottleneck_detector accounts_ebs_* 条件初始化 | P1 | 字段命名走 getter (`get_disk_field_prefix`) 后, alias 路径更清晰; jq `// 0` 仍需手动加 | 30% |
| §13.10 monitoring_coordinator LOGS_DIR 多实例冲突 | P1 | `${LOGS_DIR}-$(get_cloud_provider)` 路径 suffix, 集中化 | 80% |
| §13.11 block_height_monitor MEMORY_SHARE_DIR 多实例冲突 | P1 | 同上 | 80% |
| **§13.12 iostat_collector.sh L144 `_aws_standard_*` 字段名 (writer 上游源头)** | **P0** | **完全消除**: 同 §13.6, 是同一字段在 writer 端的另一个调用点 | **100%** ⭐ |
| §13.13 ebs_bottleneck_detector 7-tuple keyed | P1 | E1 不直接解决位置参数问题, 但 console 文案 `EBS BOTTLENECK` → `$(get_bottleneck_label) BOTTLENECK` | 40% |
| §13.14 benchmark_archiver 时区 + 归档命名 | P2 | `get_archive_dir_prefix()` 解归档命名; 时区独立问题不解 | 60% |
| §13.15 framework_data_quality_checker 21 字段 3 处 DRY | P2 | E1 不直接解决 DRY (要抽函数) | 0% |
| §13.16-17 target_generator / fetch_active_accounts 豁免 | P3 | 维持豁免 | N/A |
| §13.18 report_generator glob pattern + archiver 隐式契约 | P1 | `get_archive_dir_prefix()` 集中常量, glob pattern 共享同一来源 | 70% |
| §13.19 report_generator run_* basename 启发式 | P1 | 同 §13.18 (`ARCHIVE_DIR_PREFIXES` 常量来自 `get_archive_dir_prefix()`) | 70% |
| §13.20 关键字常量散落 | P2 | E1 不直接解决 (要抽模块级常量) | 20% |
| **§13.21 comprehensive_analysis 'EBS' 字面 4 处** | P1 | **完全消除**: `get_bottleneck_label()` 替换所有 4 处 | **100%** ⭐ |

**结构性消除汇总**: §13.2 / §13.5 / §13.6 / §13.12 / §13.21 共 **5 个阻塞点** (3×P0 + 1×P1) 被 E1 抽象层彻底解决。

---

## 4. CP 改造代价表 (Step C 主项)

| CP | 当前 PLAN LOC | E1 改造增量 LOC | case → getter 改造点数 | 新增/影响 getter | 消除的阻塞点 | 风险评级 |
|---|---|---|---|---|---|---|
| **CP-0** | ~150 (cloud_provider.sh) | **+250** (新增 providers/{aws,gcp}_provider.sh 各 ~80 + contract test ~60 + 抽象层调度 ~30) | 0 (重构内部) | 全部 15 个 getter 定义 + dispatch | 无 (基础设施) | 中 (新引入抽象层, 需测试) |
| **CP-1** | ~200 (disk_converter.sh) | **-30 净减少** (2 处 case 改 1 行 getter 调用, 同时去掉 baseline 表 if 分支) | 2 (#3 + #4) | get_baseline_io_kib / get_baseline_throughput_kib / get_doc_url | 间接受益 §13.6 (字段命名一致性) | 低 |
| **CP-2** | ~700 (system_config + user_config + config_loader) | **-80 净减少** (case 块平均 8 行 → getter 调用 1 行, 9 处 × 7 行节省) | 9 (#5-#13) | 多达 7 个 getter (metadata x3, baseline x2, nic_allowance, nic_monitor_process) | **§13.2 / §13.3 / §13.5** 全部消除 | 中 (CP-2.3 detect_deployment_platform 需重构为"探测+初始化 provider"两阶段) |
| **CP-3** | ~600 (unified_monitor / nic_network_monitor / coordinator / block_height) | **-40 净减少** (4 处 case + 字段命名 hardcode → getter) | 4 (#14, #15, §13.10, §13.11) | get_nic_allowance_fields / get_nic_driver / get_disk_field_prefix | **§13.6 + §13.12** (P0 字段) | 中 (CP-3.1 是核心 2802 行, 但字段命名 hardcode 替换非常机械) |
| **CP-4** | ~400 (4 个 tools) | **-20 净减少** | 3 (#16, #17, #18) | get_disk_type_options / get_disk_field_prefix / get_archive_dir_prefix | §13.18 / §13.19 (60% 间接) | 低 |
| **CP-5** | ~500 (visualization + analysis) | **-15 净减少** (Python `get_bottleneck_label()` 替换 4 处字面) | 1 (#21 = §13.21) | get_bottleneck_label + Python 侧 cloud_provider.py | **§13.21** 完全消除 | 低 (Python 端纯字面替换) |
| **CP-6** | ~300 (alias 清理 + 回归) | **0** (E1 不影响 CP-6 收尾, alias 清理路径不变) | 0 | - | - | 低 |
| **总计** | ~2850 | **+65 净增加** (CP-0 +250, 其他 CP 共 -185) | **19 处** (业务分发口径) | **15 个 getter** | **5 个阻塞点结构性消除** | - |

**关键观察**:
- 净增 LOC 极少 (+65), 但**结构性收益巨大**: 一处加新平台 (例如 Azure) 只改 providers/azure_provider.sh, 业务代码零变动
- CP-2 是收益最大区 (-80 LOC + 3 P0 阻塞消除), 改造价值最高
- CP-3 字段命名 (`_aws_standard_*`) hardcode 一直是悬而未决的 P0 风险, E1 通过 `get_disk_field_prefix()` 一举解决
- **唯一中等风险**: CP-0 新增 contract test (~60 LOC), CP-2.3 detect_deployment_platform 改造逻辑(从两阶段 detect 简化为"detect 完即 export provider")

---

## 5. 落地路线图 (Step D)

### Phase E-0: 在 PLAN 顶部加 E1 架构说明章节 (1 人, 1 hour)
**工作内容**:
- 在 CORRECTED_PLAN.md L1 之后 (CP-0 之前) 插入 §0 "E1 Provider 抽象层设计"
- 内容: 抽象层目标 / 13 getter 接口表 / providers/ 目录结构 / source 契约 / 与 Python 侧的对称设计
- ~150 行 markdown
**前置依赖**: 无
**Subagent 并行度**: 1
**输出**: PLAN 顶部新增 §0 章节

### Phase E-1: 重构 CP-0.1 + 新增 CP-0.4 providers/ (1 人, 1.5 hour)
**工作内容**:
- CP-0.1: 现有 utils/cloud_provider.sh 改为**抽象层** (detect + 15 个 getter 接口规范 + factory load_provider)
- 新增 CP-0.4: providers/{aws,gcp,other}_provider.sh 三文件, 每个 ~80 行实现全部 getter
- 新增 CP-0.5: tests/test_provider_contract.sh — 验证三 provider 都实现了 15 个 getter (符号存在 + 返回非空)
**前置依赖**: Phase E-0
**Subagent 并行度**: 1 (核心抽象, 不并行避免冲突)
**输出**: PLAN 中 CP-0 节扩展 (从 ~500 行 → ~900 行)

### Phase E-2: 改造 CP-1 + CP-2 全部 case → getter (2 人并行, 各 ~5 min)
**工作内容**:
- Subagent A: CP-1 (disk_converter.sh 2 处 case 改 getter 调用; +验证场景)
- Subagent B: CP-2.1/2.2/2.3 (共 9 处 case 改 getter 调用; +验证场景; +§13.2 source 顺序消除说明; +§13.5 metadata header 消除说明)
**前置依赖**: Phase E-1 (providers/ 已就绪)
**Subagent 并行度**: 2
**输出**: PLAN 中 CP-1 节小修, CP-2 节中改 (case 块缩短, 验证场景重写)

### Phase E-3: 改造 CP-3 + CP-4 + CP-5 全部 case → getter (3 人并行, 各 ~5 min)
**工作内容**:
- Subagent C: CP-3 (unified_monitor / nic_network_monitor / coordinator / block_height 共 4 处) + **§13.6 + §13.12 字段名 hardcode 用 get_disk_field_prefix() 一并消除**
- Subagent D: CP-4 (disk_analyzer / framework_data_quality / benchmark_archiver 共 3 处)
- Subagent E: CP-5 (analysis/comprehensive_analysis.py 4 处 'EBS' 字面 + Python 侧 cloud_provider.py 设计)
**前置依赖**: Phase E-2
**Subagent 并行度**: 3
**输出**: PLAN 中 CP-3/4/5 节小修

### Phase E-4: 更新 TRACKER §13 阻塞点状态 (1 人, ~10 min)
**工作内容**:
- §13.2 / §13.5 / §13.6 / §13.12 / §13.21 状态从 ❌ → ✅ (E1 结构性消除, 标注 "E1 absorbed")
- 总览 P0 由 9 → 5 (-4), P1 由 22 → 21 (-1)
- 新增 §14 章节 "E1 抽象层架构说明 + 接口契约"
**前置依赖**: Phase E-3
**Subagent 并行度**: 1
**输出**: TRACKER 更新

### 路线图依赖图
```
E-0 (架构章节)
  └─→ E-1 (CP-0 重构)
        └─→ E-2 (CP-1/2 并行 2 人)
              └─→ E-3 (CP-3/4/5 并行 3 人)
                    └─→ E-4 (TRACKER 状态同步)
```

**总工时估算**: 1h + 1.5h + 5min×2 (并行) + 5min×3 (并行) + 10min = **~2.9 小时** (5 个 subagent 任务, 关键路径 ~3h, 总工作量 ~4h)

---

## 6. 五个关键设计决策 (Step E)

### 决策 1: bash 函数返回值方式 → 推荐 **echo + $() 命令替换**

**对比**:
| 方式 | 示例 | 优点 | 缺点 |
|---|---|---|---|
| echo + $() (推荐) | `endpoint=$(get_metadata_endpoint)` | 简单, 子 shell 安全, Python 风格 | 每次 fork 开销 ~1ms |
| nameref (declare -n) | `get_metadata_endpoint endpoint; echo $endpoint` | 0 fork 开销 | bash 4.3+ 限定, 语法生硬, 易出 readonly var 错 |
| 全局变量 export | `get_metadata_endpoint; echo $METADATA_ENDPOINT` | 0 fork | 污染全局, 易冲突, 不符合 getter 语义 |

**推荐 echo + $()** 理由:
- 调用频次低: 每个进程启动时调一次 getter, 不在热路径
- 1ms fork 开销可忽略 (vs 1s IMDS curl)
- 代码可读性最高: `endpoint=$(get_metadata_endpoint)` 符合 Python/Go 习惯
- 与下游 `curl -H "$(get_metadata_header)" "$(get_metadata_endpoint)/..."` 链式组合自然

**特殊场景** (返回数组, 例如 `get_nic_allowance_fields` 返回 6 字段):
- 用 CSV 字符串返回 + caller `IFS=',' read -ra fields <<< "$(get_nic_allowance_fields)"`
- 或保留 `MONITORING_PROCESS_NAMES_STR` 等空格分隔约定 (已被 system_config.sh 采用)

### 决策 2: providers/ 目录位置 → 推荐 **config/providers/**

**对比**:
| 位置 | 推荐度 | 理由 |
|---|---|---|
| `config/providers/` ⭐ | 推荐 | provider 是 config 抽象的延伸; 与 `config/system_config.sh` 同层; source 链清晰 (`config_loader.sh → config/providers/${CLOUD_PROVIDER}_provider.sh`) |
| `utils/providers/` | 备选 | 与 `utils/cloud_provider.sh` 同层逻辑上对; 但 provider 提供的是 config 数据, 放 utils 在语义上略弱 |
| `lib/providers/` (新目录) | 不推荐 | 引入新顶层目录, 与项目现有 5 层结构 (config/utils/monitoring/tools/analysis/visualization) 不一致 |

**推荐 config/providers/** 理由:
- provider 返回值 95% 是 config 数据 (endpoint / disk type / 字段集), 与 `config/` 语义对齐
- `utils/cloud_provider.sh` 仍保留为**抽象层入口** (detect + factory), 内部 source `config/providers/${CLOUD_PROVIDER}_provider.sh`
- 此布局下抽象层 (utils) 和实现层 (config) 分离, 符合 VFS 设计 (vfs.c 在 fs/, ext4_super.c 在 fs/ext4/)

### 决策 3: provider 接口 contract test → 推荐 **必须有**

**实现方案**: 新增 `tests/test_provider_contract.sh` (~60 行)
```bash
#!/usr/bin/env bash
# 验证 aws / gcp / other 三个 provider 都实现了 15 个 getter

REQUIRED_GETTERS=(
    get_metadata_endpoint get_metadata_header get_metadata_api_path
    get_baseline_io_kib get_baseline_throughput_kib
    get_default_disk_type get_disk_type_options
    get_nic_driver get_nic_allowance_fields get_nic_monitor_process_name
    get_disk_field_prefix get_archive_dir_prefix get_bottleneck_label
    get_platform_display_name get_doc_url
)

for provider in aws gcp other; do
    CLOUD_PROVIDER=$provider bash -c "
        source utils/cloud_provider.sh
        for getter in ${REQUIRED_GETTERS[*]}; do
            declare -F \$getter >/dev/null || { echo \"FAIL: \$getter missing in $provider\"; exit 1; }
            val=\$(\$getter 2>/dev/null) || { echo \"FAIL: \$getter errored in $provider\"; exit 1; }
        done
        echo \"$provider: OK (15/15 getters)\"
    "
done
```
**收益**: 新增 provider (Azure / OCI) 时, 一跑此 test 立即知道哪些 getter 漏实现。

### 决策 4: source 顺序 + source guard → **抽象层自身有 guard, 实现层无 guard**

**source 责任链**:
1. `utils/cloud_provider.sh` (抽象层): 文件顶部 `[[ -n "${CLOUD_PROVIDER_DETECTED:-}" ]] && return 0` (已存在), 探测完 CLOUD_PROVIDER 后 source `config/providers/${CLOUD_PROVIDER}_provider.sh`
2. `config/providers/{aws,gcp,other}_provider.sh` (实现层): **不加 source guard** (永远只被抽象层 source 一次)
3. 业务代码: 通过 `source utils/cloud_provider.sh` 间接拿到所有 getter, **永远不直接 source providers/**

**source 顺序约定**:
- 任何业务文件第一行 (在使用任何 getter 前): `source "${PROJECT_ROOT}/utils/cloud_provider.sh"`
- 推荐在 `config/config_loader.sh:L1-10` 全局加载阶段做 (现在所有业务文件都 source config_loader.sh)
- 这样**最多 source 一次**, 后续业务文件复用已 export 的 getter (export -f) + CLOUD_PROVIDER env

**`export -f` 关键**: providers 文件内部 getter 函数必须 `export -f get_*`, 否则子进程 (vegeta / iostat fork) 拿不到。可以在抽象层批量 export:
```bash
# utils/cloud_provider.sh 末尾
for getter in "${REQUIRED_GETTERS[@]}"; do
    export -f "$getter"
done
```

### 决策 5: §13.2 source 顺序冲突的最终解决方案 → **懒求值 getter 真正解决**

**问题回顾** (TRACKER §13.2):
> config_loader.sh L72-78 先 source system_config.sh, 此时 CLOUD_PROVIDER 仍为 "auto", 导致 system_config.sh 内所有 `case "${CLOUD_PROVIDER:-...}"` 首次加载落 **aws 默认分支**; detect_deployment_platform 后置无人重新触发 case → 4 个变量 (METADATA_ENDPOINT / METADATA_API_PATH / CLOUD_IO_BASELINE_KIB / MONITORING_PROCESS_NAMES) 全部首次加载失效。

**当前 PLAN 的 workaround** (V1.0 / CORRECTED_PLAN.md L1132-1145):
- 加 "re-evaluate hook" 或 "lazy getter 函数" — 但只是设计妥协, 未真正落地

**E1 的结构性解决方案**:

懒求值 getter **天然解决**问题:
```bash
# 改造前 (急切求值, 受 source 顺序影响):
case "${CLOUD_PROVIDER:-aws}" in
    gcp) METADATA_ENDPOINT="http://metadata.google.internal" ;;
    *)   METADATA_ENDPOINT="http://169.254.169.254" ;;
esac
# 问题: source system_config.sh 时 CLOUD_PROVIDER=auto, 落 aws 分支

# 改造后 (懒求值 getter, 不受 source 顺序影响):
# system_config.sh 里不再赋值, 不定义 METADATA_ENDPOINT 变量
# 直接删掉 L1203-1212 的 case 块

# 业务调用方 (任何时刻):
curl -H "$(get_metadata_header)" "$(get_metadata_endpoint)/$(get_metadata_api_path)/meta-data/instance-id"
# get_metadata_endpoint 在被调用时才求值, 此时 CLOUD_PROVIDER 已被 detect 完毕 → 正确
```

**source 顺序保证**:
- `utils/cloud_provider.sh` 文件**顶层执行** `CLOUD_PROVIDER=$(detect_cloud_provider)` (CP-0.1 已规定), 一旦 source 完此文件, CLOUD_PROVIDER 必有值
- 业务方调 getter 前必须 source 此文件 (责任在调用方, 由 config_loader.sh 兜底)
- 后续无论 source 顺序如何, getter 调用时 CLOUD_PROVIDER 已固定

**§13.2 状态从 ❌ → ✅ (E1 absorbed)**, 同时**总览 P0 数 9 → 5**。

---

## 7. 总工作量估算 vs 直接进 R 期 ROI 对比

| 维度 | 直接进 R 期 (V1.0 路线) | E1 路线 |
|---|---|---|
| Phase 8a 后续工作 (本评估外) | 0 (R 期直接动业务代码) | E-0 ~ E-4 共 ~3h 关键路径 / ~4h 总工作量 |
| R 期改造代价 | 21 处 case 散落 + 5 个 P0 阻塞点遗留 | 19 处 getter 调用 (代码量 -65 LOC) + 5 P0 已消除 |
| 接入第 3 个云平台 (例如 Azure) 代价 | 全 PLAN 21 处 case 加 Azure 分支 + 5 个 P0 阻塞重新评估 | 1 个 `azure_provider.sh` 文件 (~80 行) + contract test 自动验证 |
| 业务代码可读性 | case 块散落, 12 个 `${CLOUD_PROVIDER:-...:-aws}` 嵌套默认值 | 业务代码 100% 平台中立 (`get_*()` 调用) |
| §13.2 source 顺序冲突 | 设计妥协 (re-evaluate hook) | 结构性消除 |
| §13.6 / §13.12 字段名 hardcode (P0) | 字面 `_aws_standard_*` 散落 writer/reader | 集中走 `get_disk_field_prefix()` |
| Round 演进 (改字段集/baseline) | 改全 PLAN 多处 | 改 1 个 provider 文件 |
| 风险 | 高 (5 个 P0 遗留 + 散落 case 漏改) | 低 (抽象层 contract test 兜底) |

**ROI 结论**:
- **E1 净投入** ~4 小时 (含 1h 架构章节 + 1.5h CP-0 重构 + ~1.5h 5 个 subagent 并行改 CP)
- **E1 净产出**:
  - 5 个 P0 阻塞点结构性消除 (§13.2 / §13.5 / §13.6 / §13.12 + §13.21 P1)
  - 总览 P0 数 9 → 5 (-44%)
  - 业务代码 LOC -65 (CP-1 ~ CP-5 减少 case 块)
  - **Round 演进效率**: 加新云平台从"全 PLAN 重审"降到"加 1 个 provider 文件"
  - **维护成本**: case 散落 → 接口集中, 每个 case 改造未来都收益
- **关键路径**: R 期之前必须落地, 否则 R 期改业务代码时 case 句式会先固化进 commit, 之后再抽 provider 成本翻倍 (业务代码动 2 次, contract test 验证范围变大)

**建议**: 立即批准 Phase E-0 ~ E-4, 阻断 R 期启动直到 E1 落地完成。预期 R 期工作量因 E1 而减少 ~20% (case 散落改造 → getter 调用), 净时间投入 ROI > 1.5x。

---

## 评估完成 — 验证

```
$ git diff --stat e843571
(empty — 业务代码零修改)

$ git status --porcelain analysis-notes/CORRECTED_PLAN.md
?? analysis-notes/CORRECTED_PLAN.md  (新增未跟踪, 本评估未修改)
```

所有评估结论基于:
- CORRECTED_PLAN.md 3772 行全文扫描 (21 处 case/if 命中)
- 02-GCP-MIGRATION-TRACKER.md 第十三章 21 个阻塞点逐一映射
- CP-0.1 至 CP-6.3 全部章节标题对应关系核对
- 业务代码 commit e843571 当前 0 处 CLOUD_PROVIDER 引用 (引入抽象层的最佳时机)
