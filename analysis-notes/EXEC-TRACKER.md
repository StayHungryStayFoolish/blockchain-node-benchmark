# EXEC-TRACKER: CSV Schema 解耦 + ebs/baseline 命名治理

> ⚠️ 防丢失核心文件。任何 context 压缩/重启后,先读本文件 + ADR-0001 + NAMING-GOVERNANCE-audit 即可精确接续。
> 不依赖 agent 记忆。每完成一步,立即更新本文件的状态列 + 证据列(E1/E2)。
> 高频更新,不需 ADR(决策变更才写 ADR)。
> Owner: 用户 lelandgong。最后更新: 2026-05-31(S2/S3/S6 basic 段 .sh 双侧对称落盘,见§6)。
>
> ════════════════════════════════════════════════════════════════
> 🔴 **2026-05-31 全体系核实修正(本文件已部分过时,读前必看)**:
> 1. **命名定案已从 ADR-0001(standard)推进到 ADR-0002(normalized)**。本文件 §0/§2 D1/§3 T5-T7/§5.6
>    全文写的 "standard" 均应读作 **"normalized"**(层2 折算值物理前缀三云统一 normalized)。
> 2. **registry 层改名已落地**(2026-05-31 本会话执行,未 commit):
>    - utils/csv_schema_registry.py L30-32 DISK_FIELD_PREFIX 三 value = normalized ✅
>    - config/csv_schema_registry.sh L65-67 = normalized ✅(test_csv_registry_symmetry.sh 5/5 绿)
>    - providers×3 get_disk_field_prefix + iostat_collector fallback = normalized ✅(§5.6 fallback bug 已修)
>    - device_manager.py 8 处 aws_standard 业务别名键 = normalized ✅(T6 已执行)
> 3. **§5.6 writer fallback bug 已修复**:iostat_collector.sh fallback 默认值/getter 兜底从 standard→normalized,
>    与 registry 主路径一致(原 bug:fallback 用 provider 层旧名;现两路同名 normalized)。
> 4. **🟢 对外烙印 active 落点已清理完成(2026-05-31 本会话执行,未 commit,留工作区)**:
>    `standard`→`normalized` 三个对外落点全部中性化 + L3 回归过:
>    - (s1) visualization/ebs_chart_generator.py: CHART_FILES['comparison'] 产出文件名
>      `ebs_aws_standard_comparison.png`→`ebs_normalized_comparison.png`(L36);
>      方法名 `generate_ebs_aws_standard_comparison`→`generate_ebs_normalized_comparison`
>      (定义 L1015 + 唯一调用 L245,全仓 grep 证仅 2 处)✅ AST OK
>    - (s2) visualization/report_generator.py: i18n 键 `chart_ebs_aws_standard_comparison`(+_desc)
>      →`chart_ebs_normalized_comparison`,en(L570/571)+zh(L1129/1130)两套;文案中性化
>      (EBS Normalized Comparison / EBS 折算值对比);死代码静态表 filename 引用(L4093-4095)同步改 ✅
>      **契约对齐证据**:动态 gallery `_generate_chart_gallery_section` L3838-3843 按 PNG stem
>      拼 `chart_<stem>` 键查 self.t,故文件名 stem 与 i18n 键名必须字节一致,已对齐。
>    - (s3) ci/check_csv_registry_bypass.sh: VIOLATION_PATTERN 旧抓 `aws_standard_*`(已消失的物理名,
>      rename 后此门已静默失效)→改抓 `(data|accounts)_<device>_normalized_(iops|throughput)`
>      带 device 段形态防同名异义误报(normalized 是高频第三方词:is_normalized/normalized_cov_params...);
>      baseline 段(层3多义)原样保留 ✅ 门跑通 EXIT=0 无误报 + 负向测试(注入 data_sda_normalized_iops
>      →门 FAIL EXIT=1)证非 no-op guard。
>    - **L3 回归硬证**(/tmp/verify_l3_rename.py,项目 venv blockchain-benchmark-env):
>      7 PNG 全真生成非空(371-548KB)✅ 新名 ebs_normalized_comparison.png 出现+旧名消失 ✅
>      comparison 图读 normalized 折算列(data_sda_normalized_iops 样本[2.0,8.0]非零)✅ 防静默归零过。
>    - **0 残留**:3 目标文件 + 全仓 py/sh 代码 grep `ebs_aws_standard_comparison`/`chart_ebs_aws_standard`=0;
>      剩余 4 处 aws_standard 全是说明性注释("不裸写 aws_standard_*"),非烙印输出,保留正确。
>    - **未做(任务范围外)**:docs/README/architecture-overview(4 处文档清单)+ docs/image/*.html
>      (2 处历史快照报告)仍含旧 png 名——文档/历史产物,非源码逻辑,不在本任务 3 落点范围。
> 5. **🟢 L3 真跑已完成(2026-05-31,推翻"最大盲区未跑"状态)**:依赖装入项目 venv blockchain-benchmark-env,
>    fake-node ci_smoke 36链全过;主入口跑出真实 unified CSV → **运行硬证**:
>    (a) 折算列名 = `data_sda_normalized_iops`/`_normalized_throughput_mibs`,无旧名残留 ✅
>    (b) 折算列数据非零(iops 样本 [2.0,8.0])✅ 防静默归零铁律过
>    (c) cloud_provider 列 = gcp ✅
>    (d) ebs_chart_generator 读 normalized CSV 出图,7 PNG 全生成非空(371-548KB)✅ reader 端不断链
>    **结论:disk 改名 standard→normalized 端到端不断链,改名安全(运行硬证,非静态推断)。**
>    (e) 实证 D2 准确:出图文件名仍是 `ebs_aws_standard_comparison.png`(内容读 normalized 正确,仅文件名带旧烙印未改)。
>    验证脚本:/tmp/verify_l3_csv.py + /tmp/verify_l3_charts.py。
> ════════════════════════════════════════════════════════════════

## 0. 一句话现状
解耦做了一半(S0 registry + S1 disk reader 部分接入),停在 A/B 决策矛盾的半成品态。
决策已锁 A(ADR-0001)。当前任务 = 先止血(消解 A/B 矛盾 + 文档扶正),再继续 S2-S6。

## 1. 权威文档索引(读这几个就够)
| 文件 | 作用 |
|---|---|
| analysis-notes/decisions/ADR-0001-*.md | 锁定 A 决策(只增不改) |
| analysis-notes/NAMING-GOVERNANCE-audit-2026-05-30.md | ebs/ena/baseline 语义审计(代码事实) |
| analysis-notes/CSV-SCHEMA-ABSTRACTION-proposal.md | 解耦完整方案(§4.5 已过时,待改指向 ADR-0001) |
| 本文件 | 任务清单 + 进度 + 接续指引 |

## 2. 已锁定事实(不可推翻,改需 ADR)
- D1: disk 物理列名 = 统一 standard(A) — ADR-0001
- D2: ebs(通用磁盘逻辑)→ disk;ena → 保留(AWS 专属网卡);见 NAMING audit §一
- D3: baseline 多语义:B1判定阈值=保留 / B2卷额定能力=已改provisioned(2026-05-31 device_manager writer dict key + disk_chart_generator reader 真改完, 删 get_baseline_values 死方法; 此前仅消费端变量名改、writer dict key 未改是半改态, 现已彻底) / B3 IO size基准=保留(层5 baseline_io_kib 神圣不动) / B5链模板=不动;见 NAMING audit §一.3 + ADR-0002
- D4: reader 取 provider 唯一合法来源 = CSV cloud_provider 列,禁运行时探测 — proposal §4.5 防护(此条仍有效)

## 3. 任务清单 + 状态(每步带验证证据)

### 阶段 T — 止血:消解 A/B 矛盾 + 文档扶正(当前阶段,最高优先)
> 顺序调整(2026-05-30 用户认可):T1-T3 文档先行 → **T8 先跑 L3 baseline**(建回归基线,
> 证明当前半成品能跑通,把静态推断变运行硬证)→ 再做 T4-T7 清理 → 每步回归 L3。
> 不"攒到最后才跑 L3"(proposal §3.4 铁律,你反复踩的债务陷阱)。
| ID | 任务 | 状态 | 证据(E1/E2) |
|---|---|---|---|
| T1 | 落盘 ADR-0001 锁 A | DONE | analysis-notes/decisions/ADR-0001 已写 |
| T2 | 落盘本 EXEC-TRACKER | DONE | 本文件 |
| T3 | 更新 proposal §4.5 → 指向 ADR-0001(改 B 为 A) | DONE | proposal.md §4.5 已替换,终态表三云=standard |
| T3b | 扩大审计修正写入文档(本次 §5 新增节) | DONE | 见下 §5 |
| T8a | **先跑 L3 baseline** — 确认当前半成品 fake-node e2e 能跑通出图(回归基线) | DONE | 2026-05-31 L3 已跑(顶部修正块):fake-node 36链过+主入口出真实 unified CSV+7 PNG非空+normalized数据非零(防静默归零) |
| T4 | grep 全仓找"随云变/aws_standard/baseline"误导注释(范围扩大:含 .py/.sh registry 自身 + 4+ reader) | DONE | 2026-05-31核实(亲读12文件E1):aws_standard残留43处/10文件全部判定完毕,见§5.8 |
| T5 | 清理误导注释 → "三云统一 normalized, provider 由 cloud_provider 列承载" | DONE | 清5处撒谎注释(registry.py L11/66 + bottleneck_detector.sh L906 + disk_bottleneck_detector.sh L163/231),改ADR-0002 normalized口径;语法过+对称测试5/5绿 |
| T6 | 清理 device_manager.py 残留 aws_standard/baseline 混血别名 → 中性别名 | DONE | normalized会话已清:device_manager L428 map key已=normalized_iops/normalized_throughput_mibs(非aws_standard) |
| T7 | 验证 writer/registry/reader 三方全=normalized,0 残留 B | DONE | 对称测试writer==registry三provider字节一致;L3回归reader出图读normalized列非零;0 active aws_standard残留(剩余全A1兼容别名/官方示例/中立声明/dead code) |
| T8b | T4-T7 改完回归 L3 — 确认清理未破坏出图 | DONE | 注释清理不碰逻辑;ebs→disk会话L3已验7 PNG出图+gallery分类+CI门EXIT=0 |

### 阶段 S — 继续解耦(止血后,proposal §3.4 波次)
| ID | 任务 | 状态 | 备注 |
|---|---|---|---|
| S0 | registry 骨架 + 契约测试 | PARTIAL-DONE | registry.py 仅 disk 段 21 字段;契约测试 tests/test_csv_*.sh 已有 |
| S1 | disk 段 writer + 6类 reader 接入 registry | PARTIAL-DONE | 14 文件已引用 registry(E2);但停在 A/B 混血态,需 T 阶段扶正后才算真完成 |
| S2 | framework_data_quality_checker 整串等值→字段集校验 | DONE | 路子B 段感知 registry。basic writer-first 切换 DONE(§6/§8: L1 symmetry 7/7 + L2 + L3 整框架真出 CSV)。framework_data_quality_checker basic_header 经 registry 收敛双源(§8) |
| S3 | basic/cpu/mem 段接入 + 统一 mem 列名分歧 | DONE | 与S2合并。basic 段 .py+.sh 双侧 registry + writer-first + L3 闭环(§6/§8)。mem 列名经 registry resolve 统一 |
| S4 | performance_visualizer 裸下标→registry+守卫 | TODO | 最隐蔽静默空图。本会话仅去 aws 倾向(删 'aws' not in col 死过滤,§7),裸下标→registry 守卫仍 TODO |
| S5 | per_method(proxy_method.csv)接入 | PARTIAL-DONE | per-method 链路本会话大幅推进(§9): P0-1 详细CSV落盘 + P0-2 静默异常修 + P0-3 proxy流量绕过根治 + single/mixed 双模式闭环。但 per_method 字段未纳入 csv_schema_registry 单源(独立 schema), 原义"接入registry"仍 TODO |
| S6 | cgroup 段三处重复 header 收敛单源 | TODO | 本会话**未碰** cgroup(§7.4: generate_expected_csv_header L403 自曝未含 cgroup 19 字段, 预存缺陷待修) |

### 阶段 N — ebs→disk 纯命名收尾(非 CSV 字段部分,可独立)
| ID | 任务 | 状态 | 备注 |
|---|---|---|---|
| N1 | 配置变量 BOTTLENECK_EBS_*→DISK_* | DONE | 64处/9文件/0残留(本会话) |
| N2 | 函数名 check_ebs_bottleneck→check_disk_bottleneck 等 | DONE | bottleneck_detector.sh,0残留 |
| N3 | 文件改名 ebs_*.sh/.py→disk_* + 全引用同步 | DONE | 5文件git mv(disk_bottleneck_detector/disk_converter/disk_analyzer/disk_chart_generator/cpu_disk_correlation_analyzer)+类名(DiskChartGenerator/DiskCorrelationAnalyzer),0旧名引用残留,source/import链同步(2026-05-31本会话) |
| N4 | report_generator/chart 的 ebs 文字/PNG名/翻译key | DONE | 7产出PNG中性化(disk_*)+i18n键lockstep(chart_disk_*,7键×en/zh对齐)+图上标题/print/docstring显示文字全改Disk+8历史PNG git mv+2历史HTML中性化+10份.md文档中性化+EBS_MONITOR_RATE→DISK_MONITOR_RATE(4处lockstep)。L3回归硬证:7 PNG真出图非空+normalized数据非零+0旧名+动态gallery分类修复(0误落other)+CI门EXIT=0+全源码语法过。剩余ebs全A1真AWS概念(aws_ebs_baseline/AWS EBS 16KiB层5/provider label aws=EBS·gcp=Disk/CSI卷识别/AWS官方URL/recommend_ebs_type/convert_aws_ebs_metrics)。修1误伤(ebs_aws_baseline_analysis dead键已回滚)+1 active bug(_categorize_charts关键词['disk',iostat,bottleneck]修复,改名前['ebs','aws']抓不到disk图致4图误落other)。未commit。 |

## 4. 接续指引(压缩/重启后照做)
1. 读本文件第 3 节,找第一个非 DONE 的任务。
2. 按 token-level skill:改前精读 + grep caller/reader + 改后验证 0 残留 + 语法。
3. 每完成一步,立即回写本文件状态列 + 证据列。
4. A/B 决策已锁 A(ADR-0001),禁止重开此辩论;reader 必须经 registry resolve 拿 standard。
5. 当前卡点:T 阶段(止血)未完成前,不要推进 S2-S6(歪地基不盖楼)。

## 5. 扩大审计发现(2026-05-30 token-level 复验,E1/E2 实证)

### 5.1 文档准确性复核结果
✅ 准确:A/B 矛盾真实(E1);选 A 后三方自洽**有运行硬证**(E2:bash header + python resolve 三云全 standard,
   bash vs python 全 21 字段逐字段对比 mismatch=0);S0+S1 部分执行(14 reader 引用 registry);
   framework_data_quality_checker A 类硬断链已消解(L361-366 走 registry)。
❌ 低估/不准:
   - 误导注释范围比原估广 — 不止 reader,csv_schema_registry.sh:14-16 + .py:26 自身就有"随云变 aws_standard/baseline"
     注释而代码做 standard。T4 范围扩大到全仓(含 registry 双实现 + bottleneck_detector + ebs_bottleneck_detector 注释)。
   - device_manager.py 残留 aws_standard/baseline 远不止 1 处 — 实为 7+(L46/62/431/506/581/589 patterns键 + L347-350 字典键)。

### 5.2 device_manager.py aws_standard/baseline 别名 — AP5 验证结论
- 经 AP5 协议(读全函数 + 追数据流):这些键名是**业务别名**,值经 get_mapped_field→patterns→registry 解析的
  `_disk_iops_suffix`(=_standard_iops)正则匹配真实 CSV 列 → **当前运行不断链,安全**。
- 但是 A/B 混血技术债(键名 aws_standard 误导,与 ADR-0001 中立目标不一致)→ T6 清理为中性,不紧急不影响运行。

### 5.3 结构性脆弱点(非 active bug,诚实修正)
- iostat_collector header 走 registry(L159),但 data 行(L129)仍手工拼接裸串。
- E1 逐位置对比:当前 21:21 对位**正确**,无错位。但 data 未纳入 registry,靠人肉保持顺序一致 →
  registry 数组改顺序/加字段时 data 不自动跟变 → 会静默错位。属 proposal §3.4 "writer-first 只做了 header 一半"。
- 应在 S 阶段补 "data 也从 registry 生成"。**我曾一度夸大此为"严重 BUG",经 E1 实证后降级为结构性脆弱点。**

### 5.4 范围缺口(最大问题:registry 只覆盖 disk 段)
框架生成多个 CSV(E2:unified.csv / ENA CSV / network CSV / per_method),registry 仅覆盖 **unified 主 CSV 的 disk 段**。
- network 段:有独立 network_field_registry(已解耦范本,但与 csv_schema_registry 两套系统)
- ENA CSV(ena_network_monitor.sh:86 generate_ena_csv_header):**完全未纳入** registry
- cgroup/basic/qps 段 + per_method CSV:未纳入(proposal §3.4 S2-S6 全 TODO)
"有没有严重 bug"的终判**必须等 T8a L3 baseline 跑通**。静态层面未发现 active 断链 bug,但无资格断言"无 bug"。

### 5.6 🔴 新发现真实 BUG(2026-05-30 实跑 + AP5 追数据流,E1):writer fallback 分支用 B 方案
- iostat_collector.sh generate_device_header **双行为**:
  - 主路径 L159:registry 可用 → csv_registry_disk_header → 写 **standard**(A)✅
  - fallback L162-165:registry 未 source → 用 provider 层 `get_disk_field_prefix` → GCP 下写 **baseline**(B)🔴
- 后果:若某次运行 registry 没 source 成功,GCP 环境 writer 写出 `*_baseline_iops`,而所有 reader 走 registry 期望
  `*_standard_iops` → 静默全空图。fallback 用了与主路径相反的命名方案。
- 根因:provider 层 `get_disk_field_prefix`(gcp_provider.sh:37 = baseline,未改)与 registry 层
  `_csv_registry_disk_field_prefix`(= standard)**两个 getter 并存返回不同值**。fallback 误用了 provider 层。
- E2 消费方:provider 层 get_disk_field_prefix 仅 iostat_collector fallback(L165)+ 2 测试断言用;
  生产主路径全走 registry。即 bug 仅在 "registry 未 source" 边缘条件触发,但触发即静默断链。
- 修复(并入 T 阶段):fallback 也应产出 standard(把 L165 的 `dfp="$(get_disk_field_prefix...)"` 改为固定
  `dfp="standard"`,与 ADR-0001 一致);并修 test_l3_csv_e2e.sh:29 断言(测了非生产 getter,是假绿)。
- **此 bug 之前 proposal + 我的文档全未覆盖 — 用户坚持扩大范围/批判性复验才挖出。**

### 5.7 test_l3_csv_e2e.sh 名实不符 + 假绿
- 它只 source 脚本调函数检查 header 列,是 **L2 强**,非 proposal §3.3 真 L3(起 fake-node→出图→grep `<img`)。
- L29 断言 GCP disk_field_prefix=baseline,测的是 provider 层 getter(=baseline),非真正决定 CSV 列名的
  registry 层(=standard)→ **假绿**(测了没人用来写列名的 getter)。T8a 真 L3 需另找/另建 fake-node harness。

### 5.5 终判限制(最大盲区)
至今**未跑 L3**(真起 fake-node 跑整框架出图)。所有"自洽/不断链"结论 = 静态 + 组件级实跑(registry 函数单跑),
**非整框架 e2e**。proposal §3.3 铁律:L1/L2 绿≠闭环,L3 必过。当前验证强度 = L1+部分L2。
"有没有严重 bug"的终判**必须等 T8a L3 baseline 跑通**。静态层面未发现 active 断链 bug,但无资格断言"无 bug"。
> 🟢 **2026-05-31 更新:T8a L3 已跑通(顶部修正块 + ebs→disk 会话),此盲区已消除。**

### 5.8 🟢 T 阶段核实结论(2026-05-31, 亲读 12 文件 E1, T4-T7 钉死)
> 触发: 进 S2 前核实 T 真实完成度(standard→normalized 迁移让原 TODO 失真)。亲读不 grep 抽样。
**aws_standard 残留 43处/10文件全部判定**:
- ✅ **代码层 0 active 残留** — 两 registry(.py L30-32 / .sh L66-68)= normalized 三云统一(E1);
  device_manager L428 map key 已 normalized_iops/normalized_throughput_mibs(T6 已被 normalized 会话清);
  test_l3_csv_e2e.sh:29 断言已扶正为 normalized(原§5.7 假绿已修)。
- 🔴→✅ **撒谎注释 5 处已清(T5)**: registry.py L11/66 + bottleneck_detector.sh L906 +
  disk_bottleneck_detector.sh L163/231,原描述旧 A/B 混血(gcp→baseline/aws→aws_standard),
  改为 ADR-0002 normalized 口径。语法过 + 对称测试 5/5 绿。
- ✅ **保留项(A1/中立声明,非残留)**: disk_converter.sh `convert_to_aws_standard_*` 兼容别名(L171-176)
  + recommend_ebs_type 局部变量 aws_standard_iops(真AWS卷型推荐);report_generator/disk_chart/device_manager
  的"不认/不裸写 aws_standard 字面量"中立声明(是中立化的证明);test_iops_conversion AWS 官方折算示例。
**结论: T 阶段(止血)已完成,地基已正,可干净进 S2。**

### 5.9 独立清理项(非 T/S 阶段, 低优先 latent): unit_converter.py dead code
- `utils/unit_converter.py` 的 `convert_aws_ebs_metrics`/`aws_standard_iops`/`format_network_speed_aws_standard`
  = **never-wired 并行 Python 折算实现**。E1 实证: (a) 输出键 aws_standard_iops 0 跨文件 reader;
  (b) 函数仅被同文件 __main__ 演示代码调用; (c) blockchain_node_benchmark.sh:349 调
  `unit_converter.py --auto-process` 但 __main__(L404)**不解析任何参数**,只 print 硬编码示例 →
  --auto-process 被静默忽略,真实 CSV 从未被此脚本转换。
- 真生产折算 = disk_converter.sh(bash)。unit_converter.py 这步是**死调用 + 误导性"✅ Unit conversion
  completed"日志**。属技术债(latent,不破坏数据因 disk_converter 已转好),非 active bug。
- 待决: 删 dead code + 删 blockchain_node_benchmark.sh:348-352 死调用块(需用户定夺,本次未动)。

## 6. S2/S3/S6 basic 段 — registry 双侧对称落盘(2026-05-31 本会话)

> 续点说明: 上一会话只做了 .py 侧 basic FieldDef; 本会话补齐 .sh 侧对称 + 升级 symmetry 测试覆盖 basic。
> 路子B(段感知统一 registry)已定, 不重开。所有改动留工作区, 未 commit。

### 6.1 已完成(双侧对称 + 测试全绿, 带证据)
**writer SSOT 实证来源**: monitoring/unified_monitor.sh:1927 generate_csv_header 内
  `local basic_header="timestamp,cpu_usage,cpu_usr,cpu_sys,cpu_iowait,cpu_soft,cpu_idle,mem_used,mem_total,mem_usage"`
  (10 字段, 全静态, 物理名=逻辑名, 无 provider 分流)。亲读核对, 非凭记忆。

| 文件 | 改动 | 证据 |
|---|---|---|
| utils/csv_schema_registry.py | (上会话)_BASIC_FIELDS 10字段 + SEGMENT_ORDER + DYNAMIC_SEGMENTS + _ALL_STATIC_FIELDS + segment_logical_names/segment_header | python import OK, all_logical_names()=31 |
| config/csv_schema_registry.sh | (本会话)_CSV_REGISTRY_BASIC_LOGICAL 10字段数组 + SEGMENT_ORDER/DYNAMIC_SEGMENTS 镜像 + resolve case 加 basic 10 分支(物理名=逻辑名) + 新函数 basic_logical_names/all_logical_names/segment_logical_names/basic_header/segment_header | bash -n OK; source 后逐字节对齐 .py |
| tests/test_csv_registry_symmetry.sh | (本会话)Phase1 改 all↔all(修原 disk-only↔all 错配); Phase2 扩 31字段×3×2=186组; Phase2.5 awk 限定 resolve 函数体提 case 分支(覆盖 basic+disk); 新增 Phase3.5 basic header writer(字面量)==registry 字节级 | 6/6 通过 EXIT=0 |

**对称硬证(命令+输出)**:
- 改前: Phase1 ❌(py 多 10 basic 字段, bash 缺)
- 改后: 6/6 全绿; bash basic_header == py segment_header('basic') 逐字节一致;
  bash/py segment_header('device','aws','data_nvme1n1') 逐字节一致(disk 段未回归)。

### 6.2 关键纠错
- 原 Phase1 比的是 bash `disk_logical_names`(21) ↔ py `all_logical_names`(31), 是 disk-only 时代遗留错配;
  本会话顺手修正为 all↔all 真对称。
- basic 字段名/顺序经实读 writer SSOT(unified_monitor.sh:1927) 核对无误, 与 .py 一致。

### 6.3 续作点 — S1 basic writer-first 切换(2026-05-31 本会话已完成)
**目标**: 让 generate_csv_header(unified_monitor.sh:1926) 经 registry 出 basic header, 消除 parallel-entry 风险(registry 已建但 writer 未用)。

**GREP-EVIDENCE(parallel-entry-trap 强制, 实测 stdout)**:
- registry 生产 source 链: iostat_collector.sh:16 硬 source csv_schema_registry.sh(无容错);
  unified_monitor.sh:204 source iostat_collector.sh → generate_csv_header 执行时 csv_registry_basic_header 必可用。
- device 段范本: iostat_collector.sh:159 `declare -F csv_registry_disk_header && csv_registry_disk_header`(探测可用走 registry, 否则 fallback) — 复刻此模式。

**改动(工作区, 未 commit)**:
| 文件 | 改动 |
|---|---|
| monitoring/unified_monitor.sh:1926 | generate_csv_header basic_header 字面量 → 优先 `declare -F csv_registry_basic_header && csv_registry_basic_header`, registry 缺失时 fallback 内联字面量(与 registry 字节一致) |
| monitoring/iostat_collector.sh:134 | 清撒谎注释 standard_iops/standard_throughput_mibs → normalized_*(ADR-0002), 与代码实际一致 |
| tests/test_csv_registry_symmetry.sh | Phase3.5 改守 fallback 字面量↔registry(原 grep 法因 writer 变函数调用失效); 新增 Phase3.6 source registry 后验 writer 经 registry 出 basic(live 路径非死代码) |

**验证硬证**:
- 三文件 bash -n 全过(unified_monitor/iostat_collector/registry SYNTAX_OK)。
- symmetry 测试 7/7 全绿 EXIT=0。
- **parallel-entry live-path 硬证**(隔离脚本执行真 generate_csv_header): FULL_HEADER 前 10 列
  = `timestamp,cpu_usage,cpu_usr,cpu_sys,cpu_iowait,cpu_soft,cpu_idle,mem_used,mem_total,mem_usage`
  == csv_registry_basic_header 输出, 逐字节一致 → writer 真经 registry, 非死代码。

**L3 整框架 e2e(2026-05-31 本会话已跑通, 运行硬证)**:
- 启动方式: 直接执行 `bash monitoring/unified_monitor.sh -d 10 -i 2`(unified monitor 独立采集 10 秒,
  basic 段=CPU/mem 采集与 RPC 无关, 无需 fake-node; main→start_unified_monitoring→generate_csv_header 真实写 CSV)。RC=0。
- 产出真实 CSV: blockchain-node-benchmark-result/current/logs/performance_20260531_170848.csv(1918 bytes, 2 数据行, 72 列)。
- **writer 端硬证**: 落盘 CSV header 前 10 列 = `timestamp,cpu_usage,cpu_usr,cpu_sys,cpu_iowait,cpu_soft,cpu_idle,mem_used,mem_total,mem_usage`
  == csv_registry_basic_header 输出, 逐字节一致 → 切换后 writer 经 registry 真实出 basic header。
- **数据非零硬证**(防静默归零): cpu_usage 样本[2.42,2.42] mem_used[5501,5498] mem_usage[17.14,17.13], 真实采集值非零。
- **reader 端硬证**(pandas, 生产同款): basic 10 列全可按名访问 0 缺失, 前 10 列顺序匹配, cpu/mem 非空非零 → 端到端不断链。

**结论: S2/S3 basic 段 writer-first 切换 DONE(L1 symmetry 7/7 + L2 隔离/真实 source 链 + L3 整框架真出 CSV, 三层全过)。**

## 7. 去 AWS 倾向性 + 全链路闭环(2026-05-31 本会话, 工作区未 commit)

> 任务: 当前框架内所有"写 CSV / 读 CSV / 用数据出图"环节, disk+network 去 aws 倾向;
> provider 真专属(ENA/gvnic)走条件单独显示, 不硬编码 aws。
> 方法论权威源: skill blockchain-node-benchmark-architecture §5 E12 + references/output-vendor-neutralization-three-way.md
> (三向裁决: 假烙印真通用→中立化 / 真烙印真专属→KEEP / 内容真按云变→provider-aware, **由 body 语义定不由名字定**)
> + references/disk-field-four-layer-naming-map.md(baseline 五层语义 DEFINITIVE)。

### 7.1 已改(中立化, 带验证)
| 文件:落点 | 处置 | 验证 |
|---|---|---|
| visualization/performance_visualizer.py:948-957 | 删 `'aws' not in col` 死过滤 ×4(中立化; 现物理名 normalized, 该过滤已 no-op 且是 aws 倾向残留) | AST OK |
| visualization/report_generator.py | 6 个 i18n key 去 ebs 烙印 → disk_baseline_*(aws_ebs_baseline_stats/no_aws_ebs_baseline/improved_ebs_baseline/ebs_aws_baseline_analysis/ebs_baseline_notes/ebs_baseline_generation_failed), en+zh+引用点 lockstep。**判定=假烙印真通用**(读 L1778 body "通用磁盘基准不分云" + 渲染 DATA_VOL_MAX 配置上限 vs 实测; 不做 provider-aware, 避开 E12 错误) | AST OK; 6 key en+zh 全可渲染; 0 旧 key 残留(实测 self.t) |
| tools/framework_data_quality_checker.sh:351 | basic_header 字面量 → 经 csv_registry_basic_header(双源收敛, 与 writer 同源) | bash -n OK; 三方对齐(expected==registry==writer 落盘 CSV) |

### 7.2 判定 KEEP / 不改(附理由, 非偷懒)
- **ENA 簇(316 处)**: 真烙印真专属(AWS 弹性网卡 allowance, GCP 无对应), ADR-0003 锁 KEEP; 已条件显示(ENA_MONITOR_ENABLED gate)。
- **层5 baseline_io_kib**(AWS 16KiB/GCP 4KiB 换算常数): 神圣不动。
- **report_generator baseline_config/baseline_value 等无厂商烙印 UI 文案**: baseline 是中性 UI 词, 不在去 aws 范围。
- **unified CSV network 段(net_interface/net_rx_mbps... 10 字段)**: 字段名全中性无 aws 烙印, writer 用通用 get_network_data, 无 provider 倾向 → **已合规, 不需改**。network_field_registry 管的是 rx_bytes/ena_*/gvnic_*(另一套 Y+ 架构 CSV), 与 unified net 段字段名不同源, 强接属 yak-shaving。
- **gvnic(GCP 专属)**: 走独立 network_monitor.sh + Y+ 架构(独立 CSV), 不在 unified CSV。

### 7.3 全链路闭环 L3(框架入口 + fake-node, 运行硬证)
- 启动: `blockchain_node_benchmark.sh --fake-node --quick --single`(GCP 环境, solana), 跑完整框架 ~6.5min, RC=0。
- fake-node: QPS 1000(100% 成功 1.81ms) + 1500 完成; 监控采 46 行真实数据。
- 产出: archives/run_001_20260531_172653/{logs/performance_20260531_172653.csv(47行), reports/*.html(双语 60K)}。
- **CSV 硬证**: basic 前10列经 registry 字节正确; disk 折算列=normalized(0 aws_standard/baseline_iops 旧烙印); cloud_provider=gcp; **无 ena_ 列(GCP 环境 provider 条件显示正确禁用 ENA)**。
- **expected header 校验**: "Performance CSV validation passed: 46 rows"(7.1 改的 generate_expected_csv_header 经 registry 通过)。
- **HTML 硬证**: 36 个 base64 PNG 出图, 双语 60K 非空, 0 KeyError/aws_ebs/Traceback 残留。
- **诚实追查点**: HTML 未现"磁盘基准性能统计"文案 → 实测根因 = parse_disk_analyzer_log() 返空(warnings=[]/metrics={}), generate_disk_analysis_section guard 早退 return ""(fake-node 磁盘负载低), **与 i18n key 改动无关**; 实测 6 新 key 可正确渲染, 非 parallel-entry 死代码。

### 7.4 剩余(预存缺陷, 非本任务引入, 未碰)
- generate_expected_csv_header L403 自曝: 未含 cgroup 19 字段, 与实际 CSV 不完全对齐(S6 范围)。
- network 段 unified writer 仍字面量(已判定中性合规, 接 registry 仅整洁度收益, 非去倾向必需)。

## 8. Bug 修复 + 数据正确性核验(2026-05-31 本会话, 工作区未 commit)

> 触发: 用户要求先确认数据/文件正确性 + 修当前 bug, 再谈新功能。核心需求 = single/mixed
> RPC method 资源消耗图必须展示在 HTML(框架核心点)。基于 token-level + 运行硬证。

### 8.1 修复的 3 个真 bug(代码逻辑 bug, 运行硬证)
| Bug | 根因(代码事实) | 修复 | 验证 |
|---|---|---|---|
| **BUG-1 proxy 僵尸进程** | blockchain_node_benchmark.sh:981 fake-node 的 `trap ... EXIT INT TERM` **覆盖**了 L128 cleanup_framework trap(bash trap 覆盖非叠加)→ stop_rpc_proxy 不被调 → proxy 孤儿占 18545 → 下次 bind fail 降级 "continuing without proxy" | ① fake-node 清理合并进 cleanup_framework(读全局 FAKE_NODE_PID)+ 删 L981 覆盖 trap ② lib/proxy_lifecycle.sh start 前 `_proxy_reap_orphans`(pgrep 精确匹配二进制路径 + fuser 兜底)+ `_proxy_port_in_use` 检测 ③ stop 兜底 reap | 重跑 proxy "✅ RPC proxy healthy"(之前 failed); 跑完 `pgrep tools/proxy/proxy` 无残留 |
| **BUG-3 per-method 时间戳崩溃(核心需求根因)** | analysis/per_method_attribution.py:110 read_monitor_csv `int(float(ts_raw))` 只支持 epoch 数字; unified CSV 的 timestamp 是 ISO 字符串 `'2026-05-31 19:19:50'` → float() 抛 ValueError → per_method section 被 except 吞成 `<!-- skipped: could not convert string to float -->` | read_monitor_csv 支持 ISO 字符串(`%Y-%m-%d %H:%M:%S`/ISO8601/fromisoformat)+ epoch 数字双格式 → epoch 秒 | 单测: ISO/epoch 双格式解析正确且与 proxy ns//1e9 对齐; **HTML BUG3残留=0(之前=1)** |
| **fixture 缺失(全链路阻塞)** | fake-node solana 无 getSignaturesForAddress.json → fetch_active_accounts Phase 1 取 accounts 404 → 全链路卡死(single+mixed 都卡) | 补 fixtures/solana/getSignaturesForAddress.json(3 签名)+ 修 getTransaction.json(加 accountKeys, 原 result=null)+ jsonrpc.yaml 加映射 | Phase 1 "Retrieved 3/6/9... signatures" 取到 accounts, 全链路跑通 |

### 8.2 核心需求验证(run_003_20260531_193427, 运行硬证)
- **HTML per-method section 真出现**: "📊 Per-Method 性能归因 — solana" + 4 SVG 图(per_method_{qps,latency,error_rate,resource}_solana.svg, 各 2.2-2.4KB 含 16-18 绘图元素)+ 摘要表。之前是 skipped 注释。
- en+zh 双语 HTML 各 33 个 `<img>` 引用 **0 断链**。

### 8.3 数据正确性全面核验(run_003, pandas reader)
- performance CSV: 72 列 47 行, **0 列数不一致**(writer 自洽); basic 前10列经 registry; disk 折算列 normalized(无 aws 烙印); cloud_provider 列=gcp。
- pandas reader: 47行72列 0 解析错误; cpu/mem 数据全非零。
- 子 CSV 列数正常: block_height(7)/network(12)/overhead(20)/proxy_method(9)/proxy_self(3)。

### 8.4 BUG-2(latent, 未大改, 已标注)
- iostat_collector.sh:123 convert_to_standard_iops 第3参 io_cap 默认 256(SSD), AWS HDD(st1/sc1)应 1024。
- 判定: provider 层 get_iops_conversion_func 固定 aws_ssd_ceil_256 未区分 HDD; 区块链节点几乎不用 HDD(st1 ~500 IOPS 跑不动)→ **低优先不可达**, 已加 NOTE(latent) 注释标明边界 + 将来支持路径, 不静默错。SSD 路径完全正确(iops 单测 13/13 PASS 含 cap=1024 能力)。

### 8.5 诚实局限(非 bug)
- proxy_method.csv 仅 1 条 getHealth 404 数据: vegeta targets 的 method 在 fake-node 无对应 fixture。per-method **架构链路已完全打通**(图能出/section 能渲染), 但图内**数据丰富度**受限于 fake-node fixture 覆盖。要丰富真实数据需补更多 method fixture 或上真节点(用户已知"fake node 监测不到真瓶颈")。
- 🔴 **此结论已被 §9 P0-3 推翻(2026-06-01)**: "数据稀疏"真因不是 fake-node fixture, 是 vegeta 流量绕过 proxy(proxy 启动晚于 targets 固化 url)。修 P0-3 后 proxy 采到 16万行真实 method, 数据丰富。保留此条作"self-authored 旧结论会过期"的教训。

## 9. per-method 链路深度审计 + P0-3 流量绕过修复(2026-06-01 本会话)

> 触发: 用户重述需求 + 要求加载全 skill/memory, token-level 批判性复审已提交代码(commit 9ed60e9)
> 找逻辑错误/漏需求。用户两个澄清: ① single/mixed **各自模式**资源利用图(非互比) ②
> per-method 资源消耗需有**详细文件落盘**供外部系统分析。

### 9.1 审计发现的问题(基于代码事实)
| 问题 | 级别 | 根因 |
|---|---|---|
| P0-1 per-method 详细 CSV 未落盘 | 🔴漏需求 | report_generator._generate_per_method_section_safe 只 generate_all_charts 出图, 未调 write_qps_csv/write_resource_csv(此二函数仅单测被调)→ 外部拿不到结构化数据 |
| P0-2 per-method section 静默吞异常 | 🔴结构隐患 | except 仅 return HTML 注释, 任何异常静默消失无报错(BUG-3 曾被此吞) |
| P1-1 single/mixed 文件名不区分 | 🟡 | proxy/per_method CSV+SVG 无模式标识, 先 single 后 mixed 互相覆盖 |
| P0-3 vegeta 流量绕过 proxy | 🔴**核心需求真断点** | proxy 在 Phase 2.5 启动, 晚于 Phase 1 targets 生成; targets 把 LOCAL_RPC_URL(8899)固化进 url; proxy 后改 LOCAL_RPC_URL=18545 太晚; vegeta 用固化 targets 直连 8899 绕过 proxy → proxy 仅采 getHealth 1 条 → per-method 数据全空 |

### 9.2 修复
- P0-1: 渲染链接入 write_qps_csv/write_resource_csv → 落盘 per_method_{qps,resource}_<chain>_<mode>.csv 到 LOGS_DIR。
- P0-2: except 加 stderr + traceback.print_exc(); CSV 落盘失败单独 WARN 不阻断出图。
- P1-1: blockchain_node_benchmark.sh export RPC_MODE; report_generator 读 RPC_MODE 给文件名加 _single/_mixed 后缀。
- P0-3(方案A 改时序): proxy 从 Phase 2.5 前移到 **Phase 0.5**(Phase 1 之前)。fake-node(8899)→proxy(upstream8899/listen18545, 改 LOCAL_RPC_URL=18545)→Phase1 targets 用 18545→vegeta 经 proxy。
- commit: dcfabc9(P0-1/2 + P1-1 + P1-2) + 73f56c7(P0-3)。

### 9.3 闭环验证(run_005_20260601_033206, mixed, 运行硬证)
- **P0-3 命门**: targets url = http://localhost:18545(之前 8899)✓
- proxy_method.csv **163337 行**(之前 1 行 getHealth): getAccountInfo 75000/200 + getBalance 74999/200 + getTransaction 10000/200 + getSignaturesForAddress 3334/200 + getBlockHeight 2/200 + getHealth 1/404。
- per_method_resource_solana_mixed.csv 34 数据行: getAccountInfo/getBalance 各 17 行, 按权重(0.499/0.500)归因 CPU%(11.3)/MEM(2837MB)✓ 供外部分析。
- per_method_qps_solana_mixed.csv 345 行; HTML per-method section skipped=0。
- R0 12/12, 无残留 proxy(BUG-1 修复持续生效)。

### 9.4 single 模式闭环验证(run_006_20260601_034507, 运行硬证)
- targets url = http://localhost:18545 ✓; proxy 采 163339 行: getAccountInfo 150001/200(single 单 method 符合预期)+ getSignaturesForAddress 3334 + getTransaction 10000。
- 文件名带 **_single** 后缀(per_method_resource_solana_single.csv 等), 与 mixed 的 _mixed 两套并存不覆盖 ✓ (P1-1 验证)。
- HTML per-method section skipped=0 ✓。
- **结论: single + mixed 两模式均闭环, 各自独立资源利用图 + 详细 CSV 落盘, 满足用户两个澄清需求。**

### 9.5 遗留(非 bug)
- mixed_weighted 5 method 中 fake-node 仅 getAccountInfo/getBalance 进 targets(target_generator 只生成有 fixture 的)→ 真节点会全 5 个。fake-node 范围。
- ~~CP-2 config 业务中立化(GCP 磁盘类型可切)未做~~ → **已做, 见 §10(commit 8ac8a87)**。

## 10. CP-2 磁盘类型 → IOPS 计算规则 + GCP 磁盘配置中立化(2026-06-01 本会话)

> 触发: 用户执行方向1(config 中立化)。用户多次澄清收窄范围:
>   - "不需要查各种实例类型"→ 删 vm 双天花板/machine-type 查表(实例存储带宽是用户自己该清楚的)
>   - "关心磁盘类型用什么规则算 iops/throughput"→ B 真实核心 = 磁盘类型决定 IOPS 计算规则
>   - 要求先确认沉淀计算规则准确性再执行。
> 依据: analysis-notes/aws-gcp-io-counting-rules-verified.md(4 云厂商官方文档实证, 逐条核验
>   出处具体/示例自洽/与 skill aws-gcp-sizing reference 交叉一致, 准确性通过; 局限: 沙盒无外网
>   未重抓官方页, 凭文档内部一致性+双沉淀源互证)。

### 10.1 磁盘类型 → IOPS 计算规则(权威文档核验后定案)
| 磁盘类型 | io_cap | IOPS 规则 | 出处 |
|---|---|---|---|
| AWS EBS SSD (gp3/io2) | 256 KiB | (r/s+w/s)×ceil(io_size/256) | ebs-io-characteristics.html "capped at 256 KiB for SSD" |
| AWS EBS HDD (st1/sc1) | 1024 KiB | (r/s+w/s)×ceil(io_size/1024) | 同文档 "1,024 KiB for HDD" + st1/sc1 IOPS 按 1MiB |
| GCP 全盘型 (pd-*/hyperdisk-*) | 0(不拆) | r/s+w/s passthrough | optimizing-pd-performance "throughput=IOPS×IOsize" 独立轴 |
| instance-store/other | 0(不拆) | passthrough | — |
| throughput(三云) | — | 实测 MiB/s passthrough | convert_to_standard_throughput 已 passthrough |

### 10.2 改动
- config/user_config.sh: 加 CLOUD_PROVIDER(auto/aws/gcp/other) + DATA/ACCOUNTS_VOL_TYPE 注释列全 8 GCP 盘型;
  configure_io2_volumes 加注释说明 io2 是 AWS 专属, GCP 盘型 VOL_TYPE≠io2 天然跳过(provider-aware by VOL_TYPE)。
- utils/disk_converter.sh: 新增 disk_iops_io_cap_kib(vol_type)→io_cap 映射(gp3/io2=256, st1/sc1=1024, 其余=0);
  convert_to_standard_iops 加 io_cap=0 强制 passthrough 守卫(磁盘类型优先于 provider, 即 AWS 也可不拆)。
- monitoring/iostat_collector.sh: get_iostat_data 按 logical_name 选 DATA/ACCOUNTS_VOL_TYPE →
  disk_iops_io_cap_kib 求 io_cap → 传 convert_to_standard_iops 第3参。删旧 BUG-2 latent NOTE(已根治)。

### 10.3 验证(实测)
- 7 盘型 io_cap 规则实测全对(1000iops@1024KiB): gp3/io2→4000(×4) / st1/sc1→1000(×1) / pd-ssd/hyperdisk/instance-store→1000(passthrough)。
- iops 单测 13/13, R0 12/12, symmetry 7/7 全绿。
- **BUG-2(AWS HDD io_cap 恒 256)随此根治**: 现按 vol_type 选 1024。

### 10.4 范围澄清(用户明确不做)
- vm 双天花板 min(disk,vm) / VM_MAX_* / machine-type 查表: **不做**(实例存储带宽是用户自己该清楚的, 与框架无关)。
- 仅做"磁盘类型→IOPS/throughput 计算规则"(框架职责)。

## 11. 本会话(2026-05-31~06-01)任务状态总览 + 剩余清单

> 一处汇总, 防 §3 总表与 §6-10 详情漂移(用户 2026-06-01 核对要求)。每项带 commit + 状态。

### 11.1 已完成(DONE, 带 commit)
| 任务 | 状态 | commit | 详情 |
|---|---|---|---|
| S2/S3 basic 段 writer-first(registry 双侧 + L3 闭环) | DONE | 9ed60e9 | §6/§8 |
| 去 AWS 倾向性(performance_visualizer 死过滤 + report_generator i18n key) | DONE | 9ed60e9 | §7 |
| BUG-1 proxy 僵尸进程 + trap 覆盖 | DONE | 9ed60e9 | §8.1 |
| BUG-3 per-method 时间戳崩溃 | DONE | 9ed60e9 | §8.1 |
| fake-node getSignaturesForAddress fixture | DONE | 9ed60e9 | §8.1 |
| P0-1 per-method 详细 CSV 落盘 | DONE | dcfabc9 | §9 |
| P0-2 per-method section 静默吞异常修 | DONE | dcfabc9 | §9 |
| P1-1 single/mixed 文件名区分 | DONE | dcfabc9 | §9 |
| P1-2 mixed 全链路闭环 | DONE | dcfabc9 | §9 |
| P0-3 proxy 流量绕过(Phase 0.5 时序) | DONE | 73f56c7 | §9 |
| single+mixed 双模式闭环验证(run_005/006) | DONE | 73f56c7 | §9.3/9.4 |
| CP-2 磁盘类型→IOPS 规则 + GCP 磁盘配置中立化 | DONE | 8ac8a87 | §10 |
| BUG-2 AWS HDD io_cap(随 CP-2 根治) | DONE | 8ac8a87 | §10.3 |

### 11.2 剩余未做(下一轮候选, 按优先级)
| 任务 | 状态 | 说明 |
|---|---|---|
| S4 performance_visualizer 裸下标→registry+守卫 | TODO | 最隐蔽静默空图; 本会话只去了 aws 倾向, 守卫未做 |
| S5 per_method 字段纳入 csv_schema_registry 单源 | PARTIAL | 链路已闭环(§9), 但 per_method schema 仍独立未并入 registry |
| S6 cgroup 段 header 收敛单源 + generate_expected_csv_header 补 cgroup 19 字段 | TODO | §7.4 预存缺陷, 本会话未碰 |
| CP-2 GCP 磁盘类型 e2e 实跑验证 | TODO | config/规则代码已改+单测过, 但未实跑 GCP 盘型场景 e2e |
| mixed_weighted 5 method 真节点验证 | TODO | fake-node 仅覆盖 2 method, 真节点全 5 个待验 |
| S0/S1 PARTIAL-DONE 收尾(其余段 reader 全接 registry) | PARTIAL | network/overhead/qps 段 writer 仍字面量(§7.4 判定中性合规, 非紧急) |

## 12. 框架本身问题修复 F1-F5(2026-06-01 本会话)

> 触发: 用户"先将框架当前问题全部修复完善, GCP 真机测试后置"。做框架级问题全扫描(end-to-end
> health audit + parallel-entry 全扫), 列 5 类问题逐个修。

| ID | 问题 | 修复 | commit | 验证 |
|---|---|---|---|---|
| F1 | network/overhead/block/qps 4 段双源 header(unified_monitor + framework_data_quality_checker 各一份字面量) | registry 加 4 段 FieldDef(52字段)+ 两端经 csv_registry_segment_header | 0bf6a41 | symmetry 7/7; writer 端到端 4 段经 registry 出 |
| F5 | generate_expected_csv_header 漏 cgroup 19 字段(与实际 CSV 差19列, validate 必失败) | expected 补 cgroup 段(调 cgroup_collector.py --header + fail-soft 占位) | d900d13 | expected 72列 == run_005 真实 CSV 72列 |
| F3 | disk_chart_generator CSV 路径 timestamp 无守卫(与 DataFrame 路径不对称) | CSV 路径加 if 'timestamp' in columns 守卫 | cfc0a1b | AST OK; 双路径对称 |
| F2 | 疑似 ~20 处 except 静默吞错 | **审计结论: 无真 bug**。34 except 仅 6 静默吞, 逐个 active-vs-latent triage 全是合理容错(JSON坏行skip/读文件失败continue/seaborn降级默认/timestamp多格式循环末尾有raise)。grep 粗数假象 | — | — |
| F4 | ena_network_monitor 双源 header | **不修**(ADR-0003: ENA 是 AWS legacy, parallel-entry defer) | — | — |

**回归**: symmetry 7/7 + R0 12/12 + iops 13/13 + per-method 17/17 全绿。

**成果**: unified CSV 全部静态段(basic/disk/network/overhead/block/qps)经 registry 单源 +
expected header 与实际 CSV 完全对齐(72列) — "改字段头断调用链"痛点在 unified CSV 层根治。

### 12.1 §3 S 阶段状态更新(F1-F5 后)
- S2: DONE(F1 补完 4 段双源收敛, 至此 framework_data_quality_checker 全段经 registry)
- S4: 仍 TODO 守卫部分(F3 只修了 disk_chart timestamp 不对称, performance_visualizer 裸下标→registry 守卫未做; 但 F2 审计确认现有 except 容错合理, 无静默空图风险)
- S6: DONE(F5 补 cgroup expected; cgroup 段 writer 本就经 get_cgroup_header/collector 单源, 无双源)

### 12.2 S4/S5 判定: 不做无价值重构(2026-06-01 代码事实 + active-vs-latent)
> 触发: 继续 registry 单源化收尾时, 精读 performance_visualizer + per_method schema 后判定。

- **S4(performance_visualizer 裸下标→registry 守卫): 判定不做**。精读实证: 该文件已 66 处
  `in self.df.columns` 守卫 + plot 用的列名是 `[col for col in df.columns if startswith/endswith]`
  动态发现 + `if not cols: return None` 守卫(如 L553-557)后才用, 列不存在优雅 return 不 KeyError。
  等效防住静默空图(F2 已确认无风险)。改成 registry resolve 是纯整洁度重构, 不解决实际 bug =
  yak-shaving。唯一真不对称点 disk_chart timestamp 已由 F3 修。
- **S5(per_method 字段纳入 csv_schema_registry 单源): 判定不做**。per_method 是独立 CSV +
  独立 dataclass schema(PerMethodQpsRow/PerMethodResourceRow, 字段 timestamp_ns/method_name/
  weight/cpu_pct/mem_mb), 与 unified CSV registry(timestamp/cpu_usage/data_*/net_*/cgroup_*)
  **完全不同字段域、不同 CSV**。强行并入 registry = 错误耦合两个独立 schema。per_method 链路
  已闭环(§9), 独立 schema 是正确设计。
- **结论**: 框架本身的真问题(双源/缺字段/静默空图风险)已全部修完(F1/F3/F5)。S4/S5 经精读确认
  无真问题, 重构无价值/反耦合, 不做。剩余仅后置真机项(CP-2 GCP e2e / mixed 真节点)。
