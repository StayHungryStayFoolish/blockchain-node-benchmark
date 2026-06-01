# ADR-0002: disk 指标五层语义命名定案 (supersedes ADR-0001)

## 状态
Accepted (2026-05-30, 用户拍板) — **supersedes ADR-0001**(统一 `standard` 选词部分)

ADR-0001 的"物理名只编码语义不编码云厂商(中立化)"原则 **保留有效**;
本 ADR 仅推翻其"语义词用 `standard`"的选词,改为 `normalized`,并把单一字段
扩展为完整的五层语义体系(此前文档只讨论了 disk 段 provider_aware 一层,
忽略了同链路上另外四个相邻实体,导致 baseline/provisioned 反复混名)。

## 背景:为什么要分五层
disk IOPS/throughput 从 iostat 采集到 HTML 报告判瓶颈,数据流经过五个**语义不同**
的实体。此前 session 把它们搅在一起 blanket replace,造成 `baseline`/`provisioned`
在代码里一词多义、自相矛盾(E1 实证见下)。本 ADR 给每层钉死唯一名字。

数据流:
```
[层1 iostat原始]──convert(除以 层5 基准块大小)──>[层2 折算值]──÷[层3 配置能力]──比──>[层4 阈值]──超→报警
```

## 五层定案

| 层 | 含义 | 数据来源 | 定名 | 动作 |
|----|------|----------|------|------|
| 层1 | iostat 实测原始 IOPS/throughput (r/s+w/s 求和) | iostat 实时采集 | `total` | 不动(已是) |
| 层2 | 按云厂商计量规则**折算后**的等效值(分子,每采样点在变) | 层1 经 convert 公式 | **`normalized`** | 改:standard/provider_adjusted → normalized |
| 层3 | 用户在 config 配置的磁盘**额定能力上限**(分母,固定) | user_config.sh DATA_VOL_MAX_* | `provisioned` | 对齐:部分已是,清理误叫 baseline 的几处 |
| 层4 | 利用率**百分比报警阈值**(90%/50ms 等) | internal_config.sh BOTTLENECK_*_THRESHOLD | `THRESHOLD` | 不动 |
| 层5 | 云厂商 IO size **换算基准块大小**(AWS 16KiB/GCP 4KiB) | system_config + providers get_baseline_io_kib | `baseline_io_kib` | 不动 |

利用率公式自洽读法:`normalized ÷ provisioned × 100 > THRESHOLD → 报警提示加配磁盘`

## 选词理由(逐层)
- **层1 `total`**:比 raw 更贴算法(r/s+w/s 求和),已是现状,不动。
- **层2 `normalized`**(本 ADR 核心改动):
  - 本质 = 把不同云、不同 IO 块大小的实测值折算到**统一可比口径**,这正是"归一化"的标准定义。
  - 否决 `standard`(ADR-0001 旧选):太泛,对外读者易误读为"标准盘/默认值"。
  - 否决 `provisioned`(用户曾倾向):与 AWS/GCP 官方术语正面冲突——云厂商 "provisioned IOPS"
    专指**配置的固定上限**(层3),而层2 是每采样点都在变的实测值。读者看到一列每秒在变的
    `provisioned_iops` 会困惑。
  - 否决 `adjusted`:准但泛("adjusted by what?"需查文档);`normalized` 自带"折算到统一口径"语义,自解释。
  - 中立无厂商烙印,符合"CSV 是对外交付物"的可读性要求。
- **层3 `provisioned`**:贴 AWS/GCP 官方术语("Provisioned IOPS SSD" io1/io2),
  读者一眼懂"这是我给磁盘配的能力"。代码现状已多处用对(master_qps_executor.sh
  `data_provisioned_iops=${DATA_VOL_MAX_IOPS}`),只需清理误叫 baseline 的残留。
- **层4 `THRESHOLD`**:代码现状变量名一直是 `BOTTLENECK_*_THRESHOLD`,语义无歧义,不动。
  注意:internal_config.sh:26 注释 "above baseline thresholds" 中的 baseline 是形容词("基准线"),
  非变量名,不构成冲突。
- **层5 `baseline_io_kib`**:`baseline` 在 AWS/GCP 文档里的原生术语就是 "baseline IO size"
  (换算基准块大小)。这是 `baseline` 一词唯一正当的归属,神圣保留,不挪作他用。

## E1 实证:推翻前的混名现状(2026-05-30 代码审计)
同一实体 `DATA_VOL_MAX_IOPS`(层3 配置能力)在代码里有 3 个名字:
- `monitoring/bottleneck_detector.sh:352` 打印成 "baseline"
- `monitoring/bottleneck_detector.sh:423` 变量名 `provisioned_iops`
- `monitoring/bottleneck_detector.sh:200` JSON key `disk_provisioned`

层2(折算值)物理名:
- `monitoring/iostat_collector.sh:129` 写 `standard_iops`
- 逻辑名 `disk_iops_provider_adjusted`(registry)
- registry DISK_FIELD_PREFIX 三云统一 `standard`

层5(基准块大小)正确用例(保留参照):
- `config/system_config.sh:53` `AWS_EBS_BASELINE_IO_SIZE_KIB=16`
- `config/providers/aws_provider.sh:23` `get_baseline_io_kib(){ echo "16"; }`
- `config/providers/gcp_provider.sh:23` `get_baseline_io_kib(){ echo "4"; }`(Hyperdisk 4KiB)

## 后续工作(交叉改名清单,见 EXEC-TRACKER)

> 🔴 **2026-05-31 落地状态更新**(本会话执行,未 commit):第1/2/3条 registry+writer+reader 经 registry 部分**已完成**;
> 新增完整性 grep 发现的 off-path 落点(产出文件名/i18n/CI 门)见 WRITER-SIDE 第七轮 D2/D3/D4,**仍待执行**。
> - ✅ 第1条 registry:py L30-32 + sh L65-67 已 normalized(test_csv_registry_symmetry 5/5 绿)
> - ✅ providers×3 get_disk_field_prefix + iostat_collector fallback 已 normalized
> - ✅ device_manager.py 8 处业务别名键已 normalized
> - ⬜ 第4条 bottleneck_detector.sh:352 "baseline" 打印→provisioned(层3 混名,仍未清,E1 核实仍是 baseline)
> - ⬜ 第6条 CI 守卫 VIOLATION_PATTERN(仍抓旧名 aws_standard,须 lockstep 改 normalized)
> - ⬜ off-path(WRITER-SIDE 第七轮):ebs_chart 产出 PNG 文件名+方法名 + report png gallery i18n 键
> - ⬜ 第7条 L3 真跑验证(至今未做,最大盲区)

逻辑名/物理名两层都要动,reader 经 registry resolve 后改一处即可:
1. **registry**(单源):`utils/csv_schema_registry.py` + `config/csv_schema_registry.sh`
   - DISK_FIELD_PREFIX 三云 `standard` → `normalized`
   - 逻辑名 `disk_iops_provider_adjusted` → `disk_iops_normalized`(throughput 同)
2. **writer**:`monitoring/iostat_collector.sh` 局部变量 `standard_iops` → `normalized_iops`(L121/129 等)
3. **reader**(经 registry,改逻辑名即随动):master_qps_executor / ebs_bottleneck_detector /
   ebs_analyzer / ebs_chart_generator
4. **清理层3 混名**:bottleneck_detector.sh:352 "baseline" 打印 → "provisioned";
   确认 :423 `provisioned_iops`、:200 `disk_provisioned` 已对(层3 本义),保留。
5. **层5 不动**:所有 `baseline_io_kib` / `AWS_EBS_BASELINE_*` 保持。
6. **CI 守卫**:`ci/check_csv_registry_bypass.sh` VIOLATION_PATTERN 更新(standard→normalized)。
7. **L3 真跑验证**:三方(writer/registry/reader)自洽 + 出图非空(铁律:L1/L2 绿≠闭环)。

## 不变量(给未来 reviewer / reader)
- 五个实体五个名,任意两个不得共享词根。
- 层2 物理名三云统一(中立),provider 维度由 cloud_provider 列承载(继承 ADR-0001 原则)。
- `baseline` 一词仅归层5(换算基准块大小),其他任何地方出现 baseline 当"阈值/配置能力"均属待修缮的命名债务。

## 调用链精读发现的静默断链点 / 隐患(2026-05-30 全程 read_file 亲读, E1 实证)
> 方法: 不靠 grep 抽样/不靠注释/不靠记忆, 逐个 reader 的 resolve helper 实现亲读。
> 主干结论(所有 disk 折算值 reader 都经 registry, 改名自动随动)成立, 但精读挖出 4 个
> 此前文档遗漏的点 —— 全部是"改名改坏也不报错"的静默面, 决定 L3 验收标准。

### 发现⑧ — master_qps_executor.sh:301-304 双层静默归零(E1)
`_mqe_provider_field` (L292-305) 真调 `csv_registry_resolve` (L298-299) ✅。但:
- L301-302: registry resolve 失败(改名时逻辑名没同步改→对旧逻辑名 return 1)→ col 空 → `echo "0"` 静默归零, **不报错**。
- L304: `jq ."col" // 0` 第二层兜底。
影响: 改名若逻辑名只改一半 → 图表数据全 0 但框架 EXIT=0。**验收必须看值非零, 禁止"跑通没报错"=通过。**

### 发现⑨ — ebs_chart_generator.py:153-169 折算值"计算逻辑双源"(E1)
`_recalculate_disk_standard_metrics` (L153-169) **不直接用 CSV 里 writer 算好的折算值,
而是 L169 `self.df[std_iops_field] = ...where(...)` 自己重算一遍覆写该列**(L168 注释
"no scaling when avg_io > 16 KiB")。即折算公式有两份: writer(iostat_collector + ebs_converter)
+ chart(此处)。
- 对改名: 不受影响(L159 经 registry 随动)。
- 独立隐患: writer 与 chart 两套公式若不一致, CSV 折算值 ≠ 图上折算值。属解耦目标
  ("文件逻辑处理抽象到 utils, 计算单源")应收编项, 是 proposal §5 未列的"第6个双源"(计算逻辑双源)。

### 发现⑩ — bottleneck_detector.sh:83-96 三变体扫描死逻辑(E1)
`build_provider_aware_patterns` (L83-96) 对 aws/gcp/other 三 variant 各调一次 resolve,
拼成 `|` grep 模式(L94-95)。注释 L81-82: "模块加载时不知 provider, 含三变体任一命中"。
- 对改名: 三云同名→三变体退化成重复值, 改 normalized 后仍三个相同, 随动不断 ✅。
- 残留: 这是 ADR-0001 中立化"之前"为"随云变"准备的机制, 现三云同名已退化。与
  `get_disk_field_prefix` 三方不一致(发现③)同源, 属解耦后该清理的死逻辑。

### 发现⑪ — bottleneck_detector.sh:110-120 文件级 ERR trap → exit 0(E1, 最隐蔽)
L120 `trap 'handle_detector_error $LINENO' ERR` → L116 `exit 0`(注释"不中断主测试")。
**整个文件任何错误都被吞成 exit 0**。改名导致 resolve 拿空列名/awk 除零/jq 取空 →
触发 ERR → 静默 exit 0, 主流程以为成功。
影响: 比发现⑧的 jq//0 更狠(文件级错误吞没)。**L3 验收绝不能信"跑通没报错",
必须看 bottleneck_status.json 的值是否合理。**

### 对 L3 验收标准的硬性修订(由⑧⑨⑩⑪ 推出)
改名后 L3 不仅要"图出来了/没报错", 必须额外验:
1. master_qps 输出的 disk 折算值 **非零且与 CSV 折算列一致**(防发现⑧静默归零)。
2. bottleneck_status.json 的 disk_iops/disk_throughput 值合理 **非 null**(防发现⑪ ERR 吞没)。
3. CSV 折算列值 == chart 图上折算值(防发现⑨计算双源漂移) —— 至少抽样一个时间点核对。

### 发现⑫ — ebs_bottleneck_detector.sh:173/181 第三个静默归零层(E1)
`get_ebs_data_from_csv`(L138-196) 经 `_ebs_resolve`(L130-135 真调 registry ✅)拿列名,
但 L173 `CSV_FIELD_MAP["$std_iops_field"]:-` + L181 `fields[$idx]:-0` + L187-192 数字校验
→ 列名 map 查不到 / 非数字 → 静默 0。改名验收同样看值非零。

### 发现⑬ — ebs_bottleneck_detector.sh:163 注释撒谎(E1, code-comments-are-claims)
L163 注释写"gcp→baseline_* / aws→aws_standard_* 物理列名", **但代码事实(registry L65-67)
三云统一 standard**。注释描述 ADR-0001 之前的行为, 与当前代码矛盾。信注释会得出
"物理名随云变"的错误结论 → 必须读代码不读注释。改名时此类撒谎注释一并清。

### 发现(排除) — ebs_analyzer.sh 不在改名范围(E1)
`ebs_analyzer.sh`(L35-109) 用裸字面量 case 匹配, 但只匹配 `_util/_total_iops/
_total_throughput_mibs/_avg_await`(L44-47/63-66) —— **全是非 provider_aware 字段**(层1 total
+ util/await), 不含任何折算值。改名 standard→normalized 不涉及它。idx=-1 找不到留 log_warn
不静默归零。**排除嫌疑。**

### 发现⑭ — 两个 Python reader 用两种 registry 调用方式(E1, 脆弱耦合)
- ebs_chart_generator `_resolve_disk_field`(L141): `resolve(logical, provider, device_prefix)`
  传真实 prefix, 再 L143 切 suffix。
- report_generator `_resolve_disk_columns`(L1653): `resolve(logical, provider, '')` 传空串拿纯后缀。
两者都依赖 registry 模板 `{prefix}_{dfp}_iops` 的具体格式。改 dfp(standard→normalized)两者都安全;
但若改模板结构, report_generator 传空串方式先坏(假设 {prefix} 替换空后剩干净 `_dfp_suffix`)。
非改名直接风险, 属逻辑名/模板层的隐藏假设, 记此防未来踩。
