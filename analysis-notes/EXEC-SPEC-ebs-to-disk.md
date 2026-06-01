# EXEC-SPEC: ebs→disk 中立化改名规格 (N3/N4 提前执行)

> ════════════════════════════════════════════════════════════════
> ✅ **2026-05-31 已全部执行完毕 (运行硬证, 未 commit)**:
> - N3 文件改名: 5 文件 git mv (disk_bottleneck_detector.sh/disk_converter.sh/disk_analyzer.sh/
>   disk_chart_generator.py/cpu_disk_correlation_analyzer.py) + 类名 DiskChartGenerator/DiskCorrelationAnalyzer,
>   0 旧名引用残留, source/import 链全同步。
> - N4 产出物中性化: 7 PNG→disk_* + i18n 键 chart_disk_* (7键×en/zh 与图 stem 全对齐, Rule7) +
>   图上标题/print/docstring 显示文字全改 Disk + 8 历史 PNG git mv + 2 历史 HTML 中性化 +
>   10 份 .md 文档中性化 + EBS_MONITOR_RATE→DISK_MONITOR_RATE (4处 lockstep, AP4 读写两端)。
> - **L3 回归硬证**: 7 PNG 真出图非空(370-548KB) + normalized 数据非零(防静默归零) + 0 旧名 +
>   动态 gallery 分类修复生效(0 误落 other) + CI 门 EXIT=0 + 全源码 ast/bash-n 语法过。
> - **副带修复**: (1) 误伤 ebs_aws_baseline_analysis dead键已回滚保留(A1真AWS); (2) active bug
>   _categorize_charts 关键词 ['ebs','aws']→['disk',iostat,bottleneck](改名前抓不到 disk_* 图致 4 图误落 other)。
> - **剩余 ebs 全 A1 真AWS概念**(67处源码+若干文档): aws_ebs_baseline / AWS EBS 16KiB 层5基准 /
>   provider label(aws_provider=EBS·gcp_provider=Disk,正确厂商抽象) / CSI 卷识别 / AWS 官方URL /
>   recommend_ebs_type(gp3/io2) / convert_aws_ebs_metrics。
> ════════════════════════════════════════════════════════════════

> 2026-05-31 本会话生成。判定全部用 token-level-careful-edit Rule 0/0.5 算法定死,无需再问用户。
> 算法 = "名字 claim 处理 AWS 特有概念,这个 claim 是真的吗?" 真→保留aws(忠于事实) / 假(实为通用磁盘)→改disk。
> 中立原则(USER PROFILE + skill Rule 0.5):产出交付物(图/报告/CSV)对外可读 → 一律去 aws/ebs 烙印,无例外。

## A. 不动项 (绝对不改, 已 E1 验证)

### A1. 真·AWS 平台专属标识符 (claim 真, 改了=事实错误/指错资源)
| 落点 | E1 证据 | 为何保留 |
|---|---|---|
| `_extract_ebs_csi` / `ebs.csi.aws.com` (pod_device_mapper.py L120-137, test_s5_k8s_stack.py) | 解析 `nvme-Amazon_Elastic_Block_Store_vol*` AWS EBS 设备真实 NVMe 命名,与 `_extract_gce_csi`/`_extract_azure_csi` 并列三云分支 | K8s driver 真名,改了指错 driver |
| `recommend_ebs_type` (ebs_converter.sh L120) | 推荐 gp3/io2/instance-store,全是 AWS EBS 卷型 | GCP 无 gp3,改 disk_type 语义矛盾 |
| `convert_aws_ebs_metrics` (unit_converter.py L228) | docstring "strictly following AWS documentation",算 AWS EBS standard IOPS | 真按 AWS 文档折算规则 |
| `aws_ebs_baseline_stats`/`no_aws_ebs_baseline` (report i18n) | "AWS EBS 卷基准性能" | AWS EBS 卷特有概念 |
| AWS 官方文档 URL `docs.aws.amazon.com/ebs/...` (aws_provider.sh L45-49) | AWS 资源链接 | 真实外部 URL |
| `convert_to_aws_standard_*` 向后兼容别名 (ebs_converter.sh L171) | 主实现已中立化,别名防断链(注释L169已说明) | 兼容层 |

### A2. 多义保留 (D3 锁定)
- `ebs_baseline_throughput_size_kib` = 层5 IO基准块, D3 保留

### A3. 巧合子串 / 历史记录 / 数据 (不动)
- `websocket`/`websockets` (含 ebs 子串): 链文档 03-bitcoin/05-cosmos-hub/13-avalanche-x + 各处
- 区块哈希 fixtures: solana/getBlock.json, proxy fixtures, audit/_raw-evidence/sui.json
- 历史决策记录: .hermes-handoff-2026-05-29.md, docs/architecture/CURRENT-STATE.md, OPEN-QUESTIONS.md, docs/adr/, docs/architecture/decisions/
- 我的审计 notes: analysis-notes/, .hermes/plans/

## B. 产出图名 (对外交付物, 全中立去 aws/ebs) — CHART_FILES 字典 (ebs_chart_generator.py L30-38)

| 旧名 | 新名 | 备注 |
|---|---|---|
| ebs_aws_capacity_planning.png | disk_capacity_planning.png | 去双烙印 ebs_+aws_ |
| ebs_iostat_performance.png | disk_iostat_performance.png | |
| ebs_bottleneck_correlation.png | disk_bottleneck_correlation.png | |
| ebs_performance_overview.png | disk_performance_overview.png | |
| ebs_bottleneck_analysis.png | disk_bottleneck_analysis.png | |
| ebs_normalized_comparison.png | disk_normalized_comparison.png | 本会话上轮刚从aws_standard改来,现去ebs_ |
| ebs_time_series_analysis.png | disk_time_series_analysis.png | |

注: advanced_chart_generator.py 出图名已中性 (pearson_/linear_regression_/negative_correlation_), 无需改。

## C. i18n 翻译键 (Rule 7 契约: 必须 = 新图名 stem, lockstep) — report_generator.py en+zh 两套

每个 `chart_<旧stem>`(+_desc) → `chart_<新stem>`(+_desc):
- chart_ebs_aws_capacity_planning → chart_disk_capacity_planning
- chart_ebs_iostat_performance → chart_disk_iostat_performance
- chart_ebs_bottleneck_correlation → chart_disk_bottleneck_correlation
- chart_ebs_performance_overview → chart_disk_performance_overview
- chart_ebs_bottleneck_analysis → chart_disk_bottleneck_analysis
- chart_ebs_normalized_comparison → chart_disk_normalized_comparison (上轮已建,再改stem)
- chart_ebs_time_series_analysis → chart_disk_time_series_analysis
- chart_cpu_ebs_correlation(+_desc) → chart_cpu_disk_correlation (cpu_ebs 关联图)
显示文字: "EBS 性能/瓶颈/概览/对比" → "磁盘 ..."; 但 A1 的 aws_ebs_baseline 类文字保留。

## D. 源码纯前缀误用 (claim 假, 实为通用磁盘) → 改 disk

### D1. 文件改名 (N3) + 全引用同步
| 旧文件 | 新文件 |
|---|---|
| tools/ebs_bottleneck_detector.sh | tools/disk_bottleneck_detector.sh |
| utils/ebs_converter.sh | utils/disk_converter.sh |
| tools/ebs_analyzer.sh | tools/disk_analyzer.sh |
| visualization/ebs_chart_generator.py | visualization/disk_chart_generator.py |
| analysis/cpu_ebs_correlation_analyzer.py | analysis/cpu_disk_correlation_analyzer.py |

### D2. 类名
- EBSChartGenerator → DiskChartGenerator
- (cpu_ebs correlation analyzer 类名同步)

### D3. 函数/变量 (局部误用通用磁盘前缀)
- 局部变量: ebs_queue_field(实读*_aqu_sz), ebs_col/ebs_cols/required_ebs_cols, ebs_data, ebs_metric(s), ebs_iops_fields, missing_ebs_field, ebs_log_path, ebs_analysis_pid 等
- 函数: get_ebs_data_from_csv, detect_ebs_bottleneck, init_ebs_limits, _ebs_resolve, generate_all_ebs_charts, generate_ebs_bottleneck_analysis, generate_ebs_time_series, analyze_ebs_under_qps, recommend_ebs_type 除外(A1)
- 阈值: ebs_util_threshold, ebs_latency_threshold

### D4. 测试 lockstep (改了函数/文件名测试必须跟改否则断)
- tests/test_iops_conversion.sh, tests/test_l3_csv_e2e.sh, test_pod_device_mapper(非csi部分)
- test_s5_k8s_stack.py 的 ebs_csi 测试 = A1 保留

## E. 执行顺序 (safe-multifile-rename skill)
1. 先 PLACEHOLDER 保护 A1/A2/A3 所有保留 token (ena_*, ebs.csi, ebs_baseline, recommend_ebs_type, convert_aws_ebs, aws_ebs_baseline, websocket, docs.aws URL)
2. 长串优先排序替换 ebs_aws_* → disk_* (去双烙印) 先于 ebs_ → disk_
3. git mv 5 个文件 (D1)
4. 同脚本验: residual=0(排除保留) + ast.parse/bash -n + i18n键==图stem(Rule7) + CI门negtest
5. 历史快照HTML(docs/image/*.html): 手改 src+alt+h4+p (静态快照不走glob)
6. L3 回归: 项目venv跑出图, 验7 PNG=disk_*新名 + 数据normalized非零 + HTML动态gallery引用对

## F. 验收铁律
- grep ebs (排除A区保留) = 0 残留
- 图名 7 个全 disk_*, 0 个 ebs_/aws_
- i18n键 stem == 图名 stem (字节级)
- L3: 真出图 disk_*.png 7个非空 + comparison读normalized非零 + 动态gallery显示新名不死图
- 测试全过 (改名未断测试)
