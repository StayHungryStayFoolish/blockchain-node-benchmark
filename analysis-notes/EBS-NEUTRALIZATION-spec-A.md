# A 档 ebs→disk 彻底中立化 — 执行规格 (SSOT)

> 用户拍板档位 A：ebs 标识全面中立化（函数名/变量/JSON键/配置变量/文字/文件名），
> 仅保留第三类 AWS 专有产品概念。本文件是所有执行批次的单一事实源。
> 方案甲前置已完成：CSV 物理字段名三云统一中性 standard_iops / standard_throughput_mibs。

## 0. 黄金规则

1. **ebs 是 AWS Elastic Block Store 专有术语** → 通用磁盘概念一律改 `disk`。
2. **三类语义严格区分**（token-level 精读每一处，不全局替换）：
   - 通用磁盘概念 → 改 `disk`
   - 卷配置额定上限(分母) baseline → 改 `provisioned`
   - **AWS 专有产品概念 → 保留**（见 §3 保留清单）
3. **改名必全链同步**：定义改了，所有引用同步改，grep 验证前后引用计数一致。
4. provider 来源唯一合法 = CSV cloud_provider 列，禁运行时探测。
5. 不 commit，改动留工作区。

## 1. 改名映射表（通用概念 ebs→disk）

### 1.1 配置变量（定义 config/internal_config.sh:16-34,70-71；全链引用）
| 旧 | 新 |
|---|---|
| BOTTLENECK_EBS_UTIL_THRESHOLD | BOTTLENECK_DISK_UTIL_THRESHOLD |
| BOTTLENECK_EBS_LATENCY_THRESHOLD | BOTTLENECK_DISK_LATENCY_THRESHOLD |
| BOTTLENECK_EBS_IOPS_THRESHOLD | BOTTLENECK_DISK_IOPS_THRESHOLD |
| BOTTLENECK_EBS_THROUGHPUT_THRESHOLD | BOTTLENECK_DISK_THROUGHPUT_THRESHOLD |

引用点（已知）：master_qps_executor.sh、bottleneck_detector.sh、ebs_analyzer.sh、
config/user_config.sh、config/system_config.sh —— 改定义必须全仓 grep 同步。

### 1.2 函数名
| 旧 | 新 | 定义文件 |
|---|---|---|
| check_ebs_bottleneck | check_disk_bottleneck | monitoring/bottleneck_detector.sh:415 |
| get_ebs_data_from_csv | get_disk_data_from_csv | tools/ebs_bottleneck_detector.sh |
| _recalculate_aws_standard_metrics | _recalculate_disk_standard_metrics | (已由子agent改) |

### 1.3 变量名
| 旧 | 新 |
|---|---|
| ebs_aws_iops / ebs_aws_throughput | disk_iops / disk_throughput |
| ebs_throughput (作通用磁盘吞吐) | disk_throughput |
| ebs_util | disk_util |
| ebs_latency | disk_latency |
| baseline_iops/throughput (=VOL_MAX 额定上限) | provisioned_iops/throughput |

### 1.4 JSON 键（跨 reader 契约，全链同步）
| 旧 | 新 | 消费方 |
|---|---|---|
| ebs_baselines | disk_provisioned | bottleneck_detector.sh:200 + 读取方 |
| data_baseline_iops/throughput (JSON键) | data_provisioned_iops/throughput | 同上 |
| ebs_util (JSON键) | disk_util | master_qps disk_info, reader |
| ebs_latency (JSON键) | disk_latency | 同上 |

### 1.5 输出/日志文字
"EBS ... bottleneck" → "Disk ... bottleneck"
"EBS performance baselines" → "Disk provisioned limits"
"AWS baseline IOPS/throughput" → "Disk provisioned IOPS/throughput"
"DATA/ACCOUNTS AWS IOPS" → "DATA/ACCOUNTS Disk IOPS" (已由 reader3 改)

### 1.6 文件名（物理改名，不留软链；全引用同步）
| 旧 | 新 |
|---|---|
| utils/ebs_converter.sh | utils/disk_converter.sh |
| tools/ebs_bottleneck_detector.sh | tools/disk_bottleneck_detector.sh |
| tools/ebs_analyzer.sh | tools/disk_analyzer.sh |
| visualization/ebs_chart_generator.py | visualization/disk_chart_generator.py |
| analysis/cpu_ebs_correlation_analyzer.py | analysis/cpu_disk_correlation_analyzer.py |

文件名引用点（已知 source/import/路径字面）：见 §4。

### 1.7 PNG 文件名 / 翻译 key（producer/consumer 跨文件强耦合，必须同步改两端）
| 旧 | 新 |
|---|---|
| ebs_aws_standard_comparison.png | disk_standard_comparison.png |
| ebs_*.png (其余) | disk_*.png |
| 翻译 key chart_ebs_* | chart_disk_* |
| method generate_ebs_aws_standard_comparison | generate_disk_standard_comparison |

producer = ebs_chart_generator.py(CHART_FILES + method)，
consumer = report_generator.py(翻译 dict + 文件名查找 :4093)。两端必须同 commit 改。

## 2. ebs_converter.sh 函数别名清理（选甲后）
- 删兼容别名 convert_to_aws_standard_iops/throughput（L171-172,175-176,188-189）
  —— 选甲彻底中立，不留 aws_standard 别名。
- 先 grep 全仓确认无调用方用旧名（iostat_collector 已用 convert_to_standard_*）。
- 文件头注释 "AWS EBS IOPS/Throughput Processing Script" → 中性。
- 参数名 aws_standard_iops(L118/121) → standard_iops。

## 3. 保留清单（AWS 专有产品概念，绝对不改）
- ENA 全部：ENA / ena_* / aws_ena.sh / build_ena_header / ena_baseline*（基准快照语义）
- AWS EBS 产品类型：gp3 / io2 / instance-store / recommend_ebs_type /
  analyze_instance_store_performance / calculate_io2_throughput（AWS 专属逻辑）
- config/providers/aws_provider.sh 内的 aws 字样（这是 AWS provider 实现，本就该叫 aws）
- monitoring/network/aws_ena.sh（AWS 网络实现文件，命名正确）

## 4. 文件名引用同步清单（改名后必须全部跟改，否则断 source/import）
ebs_converter.sh 引用（7处）：
- tools/ebs_bottleneck_detector.sh:16, monitoring/bottleneck_detector.sh:26,
  monitoring/iostat_collector.sh:14, monitoring/unified_monitor.sh:21,
  config/user_config.sh:72-77, blockchain_node_benchmark.sh:339-340,
  tests/test_l3_csv_e2e.sh:47, tests/test_iops_conversion.sh:10
ebs_analyzer.sh 引用：blockchain_node_benchmark.sh + 调度
ebs_chart_generator.py 引用：visualization/__init__ / report_generator import / 调度
cpu_ebs_correlation_analyzer.py 引用：调度 + import
（每个文件改名前先 execute_code python grep 找全引用，改完 grep 验证 0 残旧名）

## 5. 验证标准（每批 + 总验收）
每批：① bash -n / ast.parse 语法过；② grep 该批改的旧名 0 残留（注释/保留清单除外）；
     ③ 改名定义的引用计数前后一致。
总验收（三层）：
- L1 对称测试 test_csv_registry_symmetry.sh 5/5
- L2 writer header==registry roundtrip
- L3 fake-node e2e：改 provider 重跑，图还在 + grep `<img` 非空 + section 非空
- grep 全仓核心代码 ebs（排除 §3 保留）= 0；grep aws_standard 字段名 = 0

## 6. 批次划分
- 批1：config 配置变量 BOTTLENECK_EBS_*→DISK_* 全链同步（internal_config + 所有引用）
- 批2：bottleneck_detector.sh ebs→disk + baseline→provisioned + JSON键（ENA不动）
- 批3：master_qps/unadded 文字、unit_converter.py、ebs_converter 别名清理
- 批4：5 文件改名 + 全引用同步（含 PNG/翻译key 两端）
- 批5：三层验收
