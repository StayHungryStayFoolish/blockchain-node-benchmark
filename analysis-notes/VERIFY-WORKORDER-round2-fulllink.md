# 回验工单 Round 2: 全链路无差别精读 (C 范围) + 老 token 穷举

> 2026-05-31 落盘。触发: 用户"是否需再基于 token-level/精读/批判性思维, 扩大代码逻辑分析范围,
> 特别是逻辑调用链, 再次确认"。用户选 C (disk + network + 所有 reader/writer 四条边)。
> Round 1 (VERIFY-WORKORDER-resolve-silent-paths.md) 只沿 disk 数据路径读 resolve body,
> 漏了: 调用点字符串字面量 / 老 token 链路外残留穷举 / registry SSOT body / 两 registry 交叉引用 / network 四条边。
>
> 纪律: read_file 亲读 body 不委派; 老 token 穷举 grep; active-vs-latent triage 每个 defect; 发现即落盘。

## 🔴 Round 1 漏掉、本轮老 token 穷举炸出的链路外残留 (skill 2026-05-31 实证印证)

完整性 grep: `grep -rn 'aws_standard' + 'baseline'` 源码目录排 venv/fixtures。

### A. aws_standard 残留分类
| 落点 | 类别 | active/latent/dead | E1 + triage |
|---|---|---|---|
| unit_converter.py:253/263 `aws_standard_iops` (convert_aws_ebs_metrics 返回 key) | 死折算 key | **DEAD** | 消费方全仓 0 命中; perf_visualizer/advanced_chart import UnitConverter 并实例化但 grep `unit_converter.` 方法调用 0 命中 (存实例没调方法)。ebs_converter 的平行 Python 实现, 从未接线。**按 skill pitfall#6 先追消费方再定级, 未 inflate** |
| unit_converter.py:174 `aws_standard_gbps` / :291 `format_network_speed_aws_standard` / :394/441 | 死 network 格式化 | **DEAD** (待最终确认 caller) | 同 module, 同样需确认无消费; 初判 dead |
| disk_converter.sh:171-176 `convert_to_aws_standard_iops/throughput` 向后兼容别名 | 旧烙印别名 | **生产 DEAD** | 生产 .sh 0 调用; 仅 tests/test_iops_conversion.sh + test_l3_csv_e2e.sh 调。违反用户"改名彻底不留旧烙印别名"偏好 → 建议删别名+改测试 |
| disk_chart_generator:213 / report_generator:1644/1794/1812 / device_manager:17 注释"不裸写 aws_standard" | 说明性注释 | 无害 | 是"不保留 aws_standard"的正向说明, 非烙印 |

### B. baseline 残留 (多义, Rule 0 消歧, 待逐簇裁定)
| 落点 | 语义簇 | 处置 |
|---|---|---|
| disk_chart_generator.py:67-73 `data_baseline_iops`/`_throughput` thresholds key | 层3 配置能力/阈值 (memory 多义簇 B2) | 待裁: 是否随 provisioned 改名 |
| report_generator.py 大量 `*_baseline_*` i18n key + "AWS EBS baseline" 文案 | 报告文案/翻译键 | 待裁: 对外交付物中立化 (用户偏好) |
| chart_style_config:150 baseline (颜色名) / advanced_chart_generator:56 baseline (ENA delta 基线) | 无关簇 (颜色/delta基准) | 保留 |

## ✅ 本轮已 VERIFIED (read_file 亲读)
- [x] unit_converter convert_aws_ebs_metrics + aws_standard_iops key = DEAD (消费方 0, 实例化无方法调用)
- [x] disk_converter.sh 旧别名 = 生产 DEAD, 仅测试调

## ⏳ Round 2 待读清单 (C 全范围, 尚未亲读 — 按此续做, 不重复已 ✅)
- [ ] unit_converter aws_standard_gbps/format_network_speed_aws_standard 最终 caller 确认 (初判 dead)
- [ ] 调用点字符串字面量: 所有传 'disk_iops_provider_adjusted'/'disk_throughput_provider_adjusted' 的点, 确认改名后字符串未漏改
- [ ] csv_schema_registry.py resolve() 函数体 + DISK_FIELD_PREFIX 字典 body (SSOT 真查字典?)
- [ ] network_field_registry.py body + 与 csv_schema_registry 是否交叉引用 (两 SSOT 解耦真伪)
- [ ] network 四条边: writer (network_monitor.sh / ena_network_monitor.sh 字段名怎么产) + reader (network_analyzer.py) + 跨进程契约 + 旁路硬编码 (device_manager.py ENA 全称字段)
- [ ] 派发层: cloud_provider.sh variant 探测 + network_unified_entry.sh variant 派发
- [ ] report_generator baseline i18n key 多义裁定 (需用户拍板对外文案中立化范围)

## ✅ C 全范围四条边亲读完成 (2026-05-31, 续读, read_file body 实证)

### 两 registry 解耦 = 真 (read body 确认, 非靠文件名)
- csv_schema_registry.py 仅 L4 注释提"仿 network 范本", 零 import/调用 network_field_registry
- network_field_registry.py 零引用 CSVSchemaRegistry → 两 SSOT 代码层完全不交叉, disk 改名不碰 network

### 调用点字符串字面量 = 改名未漏
- disk_iops/throughput_provider_adjusted 共 58 命中 / 7 文件, 全用新逻辑名, 无旧字符串残留
- 调用点字符串 == registry 字典 key 字节一致 → resolve 不硬失败前提成立

### network 四条边字节对账 (writer↔reader)
- **writer 真实列名** (config_loader.sh:685 + system_config.sh:15 ENA_ALLOWANCE_FIELDS):
  `bw_in_allowance_exceeded / bw_out_allowance_exceeded / pps_allowance_exceeded /
   conntrack_allowance_exceeded / linklocal_allowance_exceeded / conntrack_allowance_available`
  (**无 ena_ 前缀, 带 _allowance**); ena_network_monitor.sh:92 按变量动态拼, 不硬编码
- **主 reader** network_analyzer.py:27 走 NetworkFieldRegistry.group_by_semantic (语义分组,
  docstring L4 禁 hardcode ena_*) → 安全正路
- **ena_field_accessor.py:85-92** get_available_ena_fields `if field_name in df.columns` 精确匹配
  configured_fields(=无前缀名) → 与 writer 列名一致 → **正确匹配, 非 skill 早期担心的不匹配**
- **旁路死映射** device_manager.py:97-106:
  - L97-101 五个无前缀名 → 匹配 writer ✓
  - **L102-106 五个带 ena_ 前缀名 (ena_bw_in_allowance_exceeded 等) → writer 从不产带前缀列 → DEAD 映射 key**

### active-vs-latent triage: device_manager L102-106 带 ena_ 前缀死映射
- Gate: get_mapped_field L211 `if field_name in self.patterns` — 只有消费方主动用 `ena_*` 前缀名查才命中
- 消费方追踪: device_manager 被 disk_chart/perf_visualizer/advanced_chart/report_generator 调,
  但均查 disk/net 字段, 无人用 ena_ 前缀名查 ENA allowance (ENA 走 ena_field_accessor 路)
- **判定: LATENT/DEAD** — 无消费方触发, 不造成 active 静默断链; 违反 network_analyzer "禁 hardcode
  ena_ 字面量"契约 + 命名残渣 → 建议清理 (删 L102-106 五行)

---

## 🎯 Round 2 全链路最终结论 (C 范围全覆盖, 无未读区残留)

**Round 1 "数据路径无 active 断链" 成立且经本轮加固** (调用点字符串/registry body/两 registry 解耦
全部回验)。但 Round 1 漏报的链路外问题, 本轮老 token 穷举 + 四条边对账炸出, 全部归类如下:

| # | 问题 | active/latent/dead | 影响 | 处置建议 |
|---|---|---|---|---|
| 1 | unit_converter.py aws_standard_iops/gbps + convert_aws_ebs_metrics + format_network_speed_aws_standard | **DEAD** (消费方 0) | 无运行影响; 对外烙印+死代码 | 删整簇方法 |
| 2 | disk_converter.sh convert_to_aws_standard_* 向后兼容别名 | 生产 **DEAD** (仅测试调) | 违"改名彻底不留旧烙印别名"偏好 | 删别名+改 2 测试 |
| 3 | device_manager.py:102-106 ena_ 前缀死映射 key | **DEAD** (无消费方) | 违"禁 hardcode ena_"契约+残渣 | 删 5 行 |
| 4 | baseline 多义簇 (disk_chart thresholds key / report i18n / 颜色名) | 多义, 部分无关 | 对外文案烙印 | 需用户裁定中立化范围 |
| 5 | 撒谎注释 4 处 (framework_data_quality:354 / registry .py.sh L60 / report L1628) | 文档层 | 误导后人 | 清理 |

**无任何 active 静默断链点**。3 处 DEAD 烙印/残渣 (1/2/3) + baseline 多义簇 (4) + 撒谎注释 (5) 均不阻塞运行,
但 1/2/3 是对外烙印/死代码 (违用户中立化+改名彻底偏好), 4 需用户拍板对外文案范围。

→ **进 S2 不被阻塞**; 但若要"改名彻底无烙印残渣"达标, 建议清理 1/2/3/5 (纯删除/改注释, 零运行风险),
   4 (baseline 多义) 单独拉一次命名裁定。

## 🔧 A 清单执行完成 (2026-05-31, 删前已评估参考价值, 删后全验证)

> 删前确认: 候选1/2/3 死代码均无参考价值 (旧线性折算被 disk_converter.sh provider-aware 实现取代且更正确;
> 格式化/命名残渣无独特知识) → 直接杀, 不记录。删前/删后均跑测试。

### 候选1 — unit_converter aws_standard 死代码闭环【已删, 零风险】
全仓+动态形态消费方 0; 内部自引用闭环 (convert_aws_ebs_metrics ← convert_iostat_to_standard_units;
format_network_speed_aws_standard ← format_performance_metrics; 两 module-level 函数外部 0 消费, 仅 __main__)。
删: convert_aws_ebs_metrics(L227-269) + format_network_speed_aws_standard(L290-315) +
convert_iostat_to_standard_units + format_performance_metrics + __main__ 对应引用。AST OK, __main__ 可跑。
**遗留待裁**: unit_converter.py:174 `aws_standard_gbps` (convert_network_throughput 方法的 dict key)。
该方法整体也 dead (外部 0 消费), 但不在原 A 清单, 未擅自删 — 见下方 OPEN。

### 候选2 — disk_converter.sh convert_to_aws_standard_* 别名【已删名+改测试, 测试全绿】
旧名生产 0 调用, 仅 14 处测试 (test_iops_conversion 13 + test_l3_csv_e2e 1)。
处置: 先改 14 处测试调用 → convert_to_standard_*, 再删别名定义+export+help 旧名, 清 2 撒谎注释 (L32/74)。
baseline 绿 → 改后仍绿 (13+7 checks PASS)。真实函数 convert_to_standard_* 是 active, 未动逻辑。

### 候选3 — device_manager.py:102-106 ena_ 前缀死映射【已删 5 行, 零风险】
5 个带 ena_ 前缀 key 全仓+动态(get_mapped_field('ena_..'))消费方 0。删 L102-106。AST OK。
L97-101 无前缀 active key (匹配 writer 真实列名) 保留。

### 候选5 — 撒谎注释【已扶正 3 处】
csv_schema_registry.sh:60 / report_generator.py:1628 / framework_data_quality_checker.sh:354
全部 standard → normalized (ADR-0002)。(原记 csv_schema_registry.py L60 经核为 dataclass 字段定义, 无撒谎, grep 为准)

### 验证 (全过)
- Python AST: unit_converter / device_manager / report_generator 全 OK
- bash -n: disk_converter / csv_schema_registry / framework_data_quality_checker / 2 测试 全 OK
- 测试: iops_conversion 13 ✓ / l3_csv_e2e 7 ✓ / csv_registry_symmetry S0 对称 ✓
- 旧 token 终扫: convert_to_aws/convert_aws_ebs/ena_前缀死映射 = 全仓 0

### OPEN (待用户裁定, 未擅自动)
1. **unit_converter.py convert_network_throughput 整方法 + aws_standard_gbps key**: 删候选1 时发现该方法
   外部 0 消费 (也是 dead), 但不在原 A 清单。L174 aws_standard_gbps 是命名烙印。删整方法属范围蔓延 → 待裁。
2. **disk_converter.sh L116-130 recommend_ebs_type 内 `local aws_standard_iops` 局部变量**: 内部命名非对外
   烙印 (不出现在 CSV/产出物), 影响小; 要不要顺手中立化为 normalized_iops 待裁。
3. **候选4 baseline 多义簇**: 未动, 需单独命名裁定 (你之前明确这类必须你拍板)。
Round 1 "可干净进 S2" 结论**需补充**: 数据路径无 active 断链成立, 但链路外有
**2 类 DEAD 烙印残留** (unit_converter aws_standard_* 死实现 + disk_converter 旧别名),
以及 **baseline 多义簇待裁定**。这些不是 active bug (不影响运行), 但属对外烙印/死代码,
违反用户"中立化+改名彻底"偏好。→ 进 S2 前是否清理由用户定; network 四条边 + 两 registry
交叉引用尚未亲读, 全链路结论待续读完成。
