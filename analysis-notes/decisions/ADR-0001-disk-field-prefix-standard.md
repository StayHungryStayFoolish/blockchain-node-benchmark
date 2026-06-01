# ADR-0001: disk CSV 字段物理列名统一中性 "standard"(A 方案)

## 状态
**Superseded by ADR-0002 (2026-05-30)** — 本 ADR"中立化/物理名不编码云厂商"原则仍有效并被 ADR-0002 继承;
但其"语义词用 `standard`"选词已被推翻,改为 `normalized`(见 ADR-0002 层2)。
原始状态:Accepted (2026-05-30, 用户拍板) — 取代 proposal.md §4.5 旧决策(随云变 B)

⚠️ 阅读本文请同时读 ADR-0002。下方"决策:选 A(统一 standard)"中的"中立化"对、"用 standard 这个词"已废。

## 背景
CSV schema 解耦重构中,disk 段 provider_aware 字段(IOPS/throughput)的物理列名命名方式有两套候选:
- A. 三云统一中性 `standard`(standard_iops / standard_throughput_mibs)
- B. 随云变厂商术语(aws→aws_standard / gcp→baseline / other→standard)

**关键事实(2026-05-30 审计发现,E1 实证)**:proposal.md §4.5 曾锁定 B(随云变),
但代码实际已实现 A:
- writer iostat_collector.sh:129 写 `standard_iops`(注释 L134 "方案甲中立命名:三云统一 standard")
- registry utils/csv_schema_registry.py:29-33 `DISK_FIELD_PREFIX = {aws:standard, gcp:standard, other:standard}`
- 但部分 reader 注释仍写"随云变 aws_standard/baseline"(注释与代码行为矛盾,代码实际经 registry 拿 standard)

即:文档锁 B、代码做 A、注释混写。运行时三方实际值都是 standard 故暂时自洽未断链,
但这是定时炸弹——任何人按文档把 registry 改成 B 而 writer 仍写 standard → 全 disk reader 静默空图。

## 选项
- A. 统一 standard:物理列名只编码语义不编码云厂商,provider 信息由独立 cloud_provider 列承载
- B. 随云变:物理列名带厂商术语,贴近各云 SRE 心智

## 决策
**选 A(统一中性 standard)。** 理由(软件设计维度):
1. 关注点分离:字段物理名只表达"是什么指标",不表达"来自哪个云"(环境维度由 cloud_provider 列承载)
2. 消除 N 个失败面:三云同名,reader 不需知道环境即可定位列;离线/跨环境分析不断链
3. 开闭原则:加第四个云零改 reader(列名不变,值按新云规则算)
4. 对外中立可读:CSV 是对外交付物,GCP 用户看 aws_standard/baseline 会困惑
5. 代码现状已是 A → 选 A 是"扶正",非重写,风险最小

B 的唯一卖点(SRE 厂商术语贴近性)可由展示层(HTML 报告 / 图表 label,经 get_bottleneck_label
"EBS"/"Disk")满足 → 展示层做本地化,数据层保持中立(又一次关注点分离)。

## 后果
正面:数据层中立、reader 解耦失败面归零、可移植、可扩展。
负面:CSV 物理列名不带厂商术语(SRE 需看 cloud_provider 列判断来源)—— 可接受。
后续工作(止血 + 扶正,见 EXEC-TRACKER):
1. registry / writer 已是 A,无需改值;
2. 清理 reader 中"随云变"误导注释 → 改为"三云统一 standard,provider 由 cloud_provider 列承载";
3. 清理 device_manager.py:46 残留 `data_aws_standard_iops` 字面别名;
4. 更新 proposal.md §4.5 指向本 ADR;
5. L3 真跑验证三方自洽(proposal §3.3 铁律:L1/L2 绿≠闭环)。
