# CSV Schema 抽象层重构 — 完整调用链分析 + 重构方案（v2 深化版）

> 创建：2026-05-29 夜间（占位）→ 深化：2026-05-30（CP-1 完成后，基于完整调用链彻底分析）
> 方法论：token-level 精读（非 grep 抽样）+ Gate 3 调用链全展开 + 贴 文件:行 实证 + 初判/实证严格分层。
> 状态：**完整调用链已实证完毕**（network 蓝本 + utils registry + 20 reader 矩阵 + 全 writer 契约）。本文档结论基于代码事实，非记忆。
> 锁约束：本重构不得违反 Q4-6「现有 monitor 字段不动」—— 抽象层是在现有字段契约**之上**加中介，不改字段语义。

---

## §1 需求（用户原话）

框架生成多个 CSV，字段头每次更改都连锁打断其他调用链的 reader。
设想：把**写文件 + 读文件 + 文件逻辑处理**抽象到 utils/，使读写逻辑与原调用链**解耦**、**可插拔**，让改字段头不再连锁断 reader。

---

## §2 断链根因（完整调用链实证结论）

### 2.1 结构性根因：writer 与 reader 之间无契约中介

主 CSV（unified monitor CSV）的契约源头是一条**手工对位**的拼接链：

| 环节 | 文件:行 | 机制 |
|---|---|---|
| 总 header 组装 | unified_monitor.sh:1926-1944 `generate_csv_header` | 9 段裸字符串拼接：basic(10)+device(N×21)+network(10)+[ena]+overhead(2)+block(6)+qps(3)+cgroup(19)+cloud_provider(1) |
| 总 data 组装 | unified_monitor.sh:generate_csv_data | 必须与 header **严格同序对位**（位置耦合） |
| device 段 header | iostat_collector.sh:144 `generate_device_header` | 21 字段裸字符串 `${prefix}_aws_standard_iops` 等 |
| device 段 data | iostat_collector.sh:127 | 21 值按位置对位 :144 |
| cgroup 段 | unified_monitor.sh:1957/1963/1967 | 19 字段裸字符串，**三处重复硬编码**（disabled/缺文件/正常各一份） |
| basic 段 | unified_monitor.sh:1927 | `timestamp,cpu_usage,...,mem_used,mem_total,mem_usage` 裸串 |

writer 这边：header 的定义 + data 的对位 + cgroup 的三处副本，全是**字面字符串手工维护**。
reader 那边（见 §2.2）：20 个文件各自用 5 种不同方式硬编码同一批字段名。
**writer 和 20 reader 之间没有任何共享的 schema 定义**——这就是改一个字段名要追改 N 处、漏一处就静默断链的结构性原因。

### 2.2 reader 读取方式 5 分天下（决定重构难度的关键事实）

完整 20 reader 矩阵实证（每条均贴 文件:行，见 §6 附录）。按读取机制归类：

| 机制 | reader | schema 敏感度 | 改字段名后果 |
|---|---|---|---|
| **A. 整行 header 严格等值** | framework_data_quality_checker.sh:80（`actual==expected`，expected 在 :346-396 全硬编码） | **极高** | 改任何字段名/列序/增删列 → 立即 mismatch `return 1` 报错 |
| **B. 固定末尾列号** `$NF/$(NF-1)` | ena_network_monitor.sh:204-206 | **高** | 末尾加列即错位（CP-1 给主 CSV 末尾加 cloud_provider 安全，是因为主 CSV 无此类 reader；但 ENA CSV 有） |
| **C. 列名解析→列号读** | ebs_analyzer.sh:40-68 名解析→:104-132 `cut -f$N` | 中 | 字段名改→解析失败→idx=-1 数据 not found |
| **D. pandas 裸下标** `df['cpu_usage']` | performance_visualizer.py（cpu_usage 9处/mem_usage 6处，无守卫）；report_generator.py:2377 `usecols=['mem_used','mem_total']` | 中（静默） | KeyError/ValueError→方法级 except 吞→空图，**不报错** |
| **D'. pandas 模糊匹配** endswith/startswith | report_generator.py:1761/1762/1779/1780；qps_analyzer / cpu_ebs / comprehensive 的 `_util/_total_iops/...` 后缀 | 中 | 后缀改→匹配空→统计跳过空图 |
| **E. 列名查表/语义分组**（已解耦） | ebs_bottleneck_detector.sh（CSV_FIELD_MAP 名→idx）；bottleneck_detector.sh（header 名遍历）；master_qps_executor.sh（jq key + DictReader）；per_method_attribution.py / offline_join.py（csv.DictReader）；network_analyzer.py（**NetworkFieldRegistry.group_by_semantic，唯一全解耦**） | 低 | 加列/换序无感；改名时 E 类多数有显式校验或 jq `//0` 静默兜底 |

关键洞察：
- **全仓无任何 `iloc[:,N]` / `csv.reader` 下标读主 CSV**（好消息：纯列号读取不存在于主 CSV reader，CP-1 末尾加列才安全）。
- 真正脆弱的是 **A（整串等值）+ D（裸下标静默）**。A 是唯一会"硬报错"的，D 是最隐蔽的"静默出错图"。
- **E 类已经是用户想要的解耦形态**——尤其 network_analyzer.py + NetworkFieldRegistry 是现成范本。

### 2.3 已存在的跨 reader schema 分歧（重构必须顺手统一）

| 分歧 | 实证 | 影响 |
|---|---|---|
| 内存列名不一致 | qps/comprehensive 用 `mem_usage`/`mem_used`；per_method_attribution.py:98 默认 `mem_used_mb` | 靠 report_generator.py:4234 显式传 `mem_col="mem_used"` 临时补；任何其它调用方不传即静默归因 0 |
| bottlenecks dict 键死路 | identify_bottlenecks 写 `CPU/Memory/RPC_Latency`，评估函数读 `detected_bottlenecks`（qps_analyzer:909） | 永远拿到 []，bottleneck 分支走不到（既存逻辑 bug） |
| aws_standard 两套读法 | report_generator endswith 裸读 vs ebs_chart_generator 经 get_mapped_field | 同类列两处分别维护 |
| EBS 后缀字面量重复 | cpu_ebs(:67-398) 与 qps(:85-161) 各硬编码一份 `_total_iops/_util/...` | 改后缀两处都要改 |

### 2.4 框架已有的"半成品抽象"（重构起点，不必推倒重来）

| 资产 | 文件 | 能力 | 缺口 |
|---|---|---|---|
| **network 三层契约（蓝本）** | interface.sh（4 函数契约+不变量）+ {aws_ena,gcp_gvnic,gcp_virtio,other_none}.sh + network_field_registry.py | 完整可插拔：writer 问 header、reader 按 semantic_type 取列、不变量守护（首列 timestamp/末列 saturation_signal/列数=header列数） | **只覆盖 network**，未推广到 disk/cpu/mem/per_method |
| Python 字段语义注册表 | utils/network_field_registry.py | `get_semantic_type` / `group_by_semantic` / `validate_csv_columns` 静态查表，bash 侧 1:1 镜像 | 只注册 network 字段 |
| 字段映射抽象（disk） | device_manager.py:135-161 `get_mapped_field` + patterns 字典(:20-133) | 把 `data_*_aws_standard_iops` 含设备名变体收敛到逻辑名（正则解耦设备名） | (a)patterns 字典自身硬编码全 schema；(b)第3级兜底:154-158 易误匹配静默；(c)返回 None 静默；(d)report_generator/perf_viz 大量**绕过它**裸读 |
| CSV 加载器 | utils/csv_data_processor.py | load+clean+has_field+validate_required_fields | docstring 明写"Removed field mapping"，是加载器不是 schema 层 |

---

## §3 重构方案（基于事实的最终方案，非初判）

### 3.1 核心设计：CSV Schema Registry 作为 writer/reader 唯一契约中介（SSOT）

复制 network 三层模式到全 CSV，建立**单一字段定义源**，writer 和 reader 都向它要信息，不再各自硬编码：

```
            ┌─────────────────────────────────────────┐
            │  utils/csv_schema_registry.{py,sh}  (SSOT)│
            │  每列: {logical_name, semantic_type,       │
            │         provider_condition, segment, order}│
            └─────────────────────────────────────────┘
              ↑ 问 header/顺序          ↑ 按 semantic/logical 取列
   ┌──────────┴─────────┐      ┌────────┴──────────────┐
   │ writer:             │      │ reader (20 个):         │
   │ generate_csv_header │      │ 不认裸字段名,           │
   │ 从 registry 生成     │      │ 用 registry.resolve()   │
   │ (不再字面拼接)       │      │ 或 group_by_semantic()  │
   └────────────────────┘      └───────────────────────┘
```

字段定义示例（registry 条目，逻辑名 + 语义 + provider 条件 + 段）：
```
disk_iops_provider_adjusted:   # 逻辑名（稳定，reader 只认这个）
  physical_name_template: "{prefix}_{disk_field_prefix}_iops"  # aws→aws_standard_iops / gcp→baseline_iops
  semantic_type: iops
  segment: device
  provider_aware: true   # 物理名随 cloud_provider 变,逻辑名不变
```
→ reader 调 `registry.resolve("disk_iops_provider_adjusted", provider, device)` 拿物理列名，**字段名怎么改 reader 都不断**。这正根治了 CP-1 方案乙"被迫保留 aws_standard 列名"的妥协。

### 3.2 三大不变量（仿 network，扩展到全 CSV）

1. **首列恒为 timestamp**（所有 reader 时间对齐依赖）
2. **列数 == registry.expected_column_count(provider, devices, flags)**（防 writer header/data 对位漂移）
3. **段顺序固定**（basic→device→network→[ena]→overhead→block→qps→cgroup→cloud_provider），段内列顺序由 registry 定义，writer 不得手工插列

### 3.3 闭环测试 = L1/L2/L3 三层全绿（缺一不可，不许只跑前两层就宣称"测试通过"）

> 铁律（2026-05-29 教训）：L1+L2 全绿 **不等于** 闭环。§5 的两个最严重 bug（双解析源、registry 漂移）只有 L3 真跑整框架才暴露——因为 L1/L2 用测试桩，writer 真实拼接 + pandas 真实按位置对齐的错位，只有真跑才看得见。**闭环 = L3 必过**。

| 层 | 测试 | 守护对象 | 数据源 |
|---|---|---|---|
| **L1 单测** | test_registry_resolve | resolve() 正确解析逻辑名→物理名（含 provider_aware 随云变） | 桩 |
| L1 | test_bash_python_registry_symmetry | bash registry 与 python registry 字段集 1:1（仿 network_field_registry） | 桩 |
| L1 | test_invariants | 首列 timestamp / 段顺序 / expected_column_count 三不变量函数正确 | 桩 |
| **L2 模块集成** | test_csv_schema_roundtrip | writer 生成 header → registry 解析 → 每列逻辑名可反查（写读闭环） | 桩 CSV |
| L2 | test_writer_header_data_alignment | generate_csv_header 列数 == generate_csv_data 列数（扩展已有 test_csv_header_data_alignment.sh） | 桩 CSV |
| L2 | test_reader_resolves_via_registry | **改一个物理字段名，所有 reader 经 registry 仍解析到**（断链回归门，本重构的核心契约） | 桩 CSV |
| **L3 整框架 e2e** | test_l3_schema_e2e（扩展已有 test_l3_csv_e2e.sh） | 起 fake-node→跑框架→真生成 unified CSV→EBS 图 + per-method 图真进 HTML（grep `<img` + section 非空注释，不能只看不报错） | **真跑** |
| **L3 根治验收（关键）** | test_l3_rename_survives | **改一次物理字段名（aws_standard_iops→baseline_iops）重跑整框架，图仍然出**——这是"解耦真生效"的唯一硬证据，没过=没根治 | **真跑** |
| CI 门 | test_no_bare_fieldname_in_readers | CI grep：迁移后的 reader 不得再出现裸 `aws_standard_iops` 等物理名（防新代码绕过 registry，仿 ci/check_parallel_entry.sh v1.4.5） | 静态 |

L3 harness 现成：CP-1 阶段7 已验证 fake-node e2e 链路可跑通（编译 9.6MB / getSlot 响应 / 4 类 per-method 图进 HTML，见 CP-1-execution-tracker §5 阶段7）。本重构直接复用，不另起。

### 3.4 增量迁移顺序（风险倒序，每步可回滚，绝不大爆改）

> 铁律 1：**渐进重构在现有代码上改，不并存 v2**（违 W-4 + parallel-entry-trap）。每步跑 R0 老测 + 契约测试。
>
> 铁律 2（writer-first，防 §5 风险1 双解析源）：**每个段必须按此顺序，不许颠倒**——
> ① writer 的 generate_header 改成从 registry 生成（删除旧字符串拼接，不保留）→ ② 跑 L2 roundtrip + 列数不变量绿 → ③ 才允许动该段 reader → ④ reader 一个一个改，每改一个 grep 验证它不再有裸物理字段名 + 跑 L2 → ⑤ 该段全部 reader 改完跑一次 L3。
> **绝不"全段一次性改完再测"**（攒到最后 = 昨晚 L1+L2 绿 L3 未知的债务陷阱）。每个 reader 是一个独立可回滚单元。

| 波次 | 范围 | 风险/收益 | 前置 |
|---|---|---|---|
| **S0** | 建 utils/csv_schema_registry.{py,sh} 骨架 + 契约测试框架 + CI grep gate | 零运行时改动，纯新增 | — |
| **S1** | disk 段（aws_standard/baseline）接入 registry：writer iostat_collector + 6 类 reader（ebs_chart/device_manager/report_generator/ebs_bottleneck_detector/bottleneck_detector/master_qps_executor）改为 resolve | **最高收益**（CP-1 痛点根因 + 双云字段随云变的根治） | S0 |
| **S2** | framework_data_quality_checker.sh 从整串等值改为 registry 驱动的"字段集校验"（顺序无关 + 缺列才报错） | 消灭最硬的 A 类断链点 | S1 |
| **S3** | basic/cpu/mem 段接入 + 统一 mem 列名分歧（§2.3） | 中收益（统一 mem_used/mem_usage/mem_used_mb） | S1 |
| **S4** | performance_visualizer 裸下标（D 类）改为 registry resolve + 守卫 | 消灭最隐蔽的静默空图 | S3 |
| **S5** | per_method（proxy_method.csv）接入 registry | 与 NS-2 per-method 对齐 | S3 |
| **S6** | cgroup 段三处重复 header 收敛到 registry 单源 | 消除三副本漂移 | S3 |

network 段已解耦，无需迁移（直接并入 registry 作为已完成范本）。

### 3.5 工时估计

| 维度 | 估计 |
|---|---|
| 工时 | S0~S2 ≈ 1.5-2 工作日（核心收益段，S1 完即解决 CP-1 痛点）；S3~S6 ≈ 2-3 工作日（全量）。可分波交付。 |
| 回滚点 | 每波 commit 独立，registry 是新增中介层；每个 reader 是独立可回滚单元（铁律2）。任一波/任一 reader 出问题可单独回退，不影响已迁移部分。 |

---

## §5 严重 BUG 风险 + 强制防护（红队自审，2026-05-30 补）

> 结论：**目标架构无结构性 bug 风险，但迁移过程有 4 个会导致严重 bug 的陷阱，全部属 parallel-entry-trap 家族**。照搬波次表而不加下列防护，S1/S2 几乎必炸。每个风险都配了"必做防护"和"触发它的反模式"。

### 风险 1（🔴 最高危）：registry 引入"双解析源" = parallel-entry 变体

- **机制**：reader 改成 `registry.resolve(...)` 拿物理名，但若 writer 仍用旧字符串模板拼物理名，registry 又独立存一份模板 → 两套模板必须永远一致，否则 writer 写出的列名 registry 解析不到 → **所有 reader 静默拿空**（pandas 列匹配不到→endswith 空列表→统计跳过→空图，不报错）。
- **反模式**：先改 reader 用 registry，writer 留着旧拼接"以后再说"。
- **必做防护**：铁律2 writer-first——writer 的 generate_header **必须先**改成从 registry 生成并删除旧拼接，L2 roundtrip 绿了**才**动 reader。writer 和 reader 共用同一 registry = 单源。test_csv_schema_roundtrip 是这一条的硬门。

### 风险 2（🔴 最高危）：bash/python 双 registry 对称漂移 → 整 CSV 错位

- **机制**：writer 是 bash、reader 一半 python 一半 bash，所以要 bash registry + python registry 两份。若有人给某段加一列只改了一侧 → header 列数与 data 列数对不上 → **pandas 按位置对齐，header 错一列后面全部平移，所有按列名的 reader 全读错列**（最隐蔽的灾难：每个字段名都在，但值全是隔壁列的）。
- **反模式**：加字段时只改 python registry（因为 reader 是 python），忘了 bash writer 同步。
- **必做防护**：S0 **前置阻塞项**——必须先建 test_bash_python_registry_symmetry 且设为 CI 硬门，才能开始任何迁移。network 范本就是靠这个对称测试活下来的（network_field_registry.py 注释明写"与 bash get_network_field_metadata 1:1 对称"）。

### 风险 3（🟡 中危）：framework_data_quality_checker 校验"反转过松"→ 漏报错位

- **机制**：现状 :80 整行 `==`（过严，改名误报）。S2 要改成"字段集校验"。但若改得只查"字段是否存在"不查顺序 → **顺序错了但字段都在，校验通过，而 pandas 按位置对齐导致数据全错位且无人发现**——把"过严误报"修成了"过松漏报"，比原来更危险。
- **反模式**：`set(actual) == set(expected)` 集合比较（丢了顺序信息）。
- **必做防护**：S2 新校验必须同时验 ①字段集 == registry 定义集 **且** ②顺序 == registry 定义顺序。是把"过严"修成"恰当"，不是修成"过松"。

### 风险 4（🟡 中危）：get_mapped_field 与 registry 并存 = 又一个双源

- **机制**：device_manager.py:135-161 的 get_mapped_field + patterns 字典(:20-133) 已经在做"含设备名变体的列收敛"（正则解耦设备名 nvme1n1）。registry 也要解 disk 段物理名。若两者并存 → disk 段有两套解析逻辑，patterns 字典改了 registry 没改（或反之）→ ebs_chart_generator（走 get_mapped_field）和 report_generator（走 registry）对同一列解析出不同结果。
- **反模式**：新建 registry 但 device_manager 的 patterns 原样不动，两条路都活着。
- **必做防护**：S1 必须把 get_mapped_field 的正则能力**收编进 registry**（registry 的 resolve 内部调用/吸收 patterns 逻辑），device_manager 改为薄转发到 registry 或删除。不是并存，是替代。

### 跨风险的两个既有静默陷阱（改造时必须正视，否则验收会被骗）

- **master_qps_executor.sh jq `// 0` 兜底**（:316/326/338/348/688/689）：字段改名时它不报错、悄悄归零。迁移这个 reader 后，验收不能只看"没报错"，要看值非零。
- **report_generator.py:4249-4251 except 吞为 HTML 注释**：per-method section 失败静默变注释。L3 验收必须 grep HTML 里真有 `<img` + section 非空，不能只看"跑完没异常"。

### §5 总结

| 风险 | 级别 | 触发波次 | 防护落点 |
|---|---|---|---|
| 1 双解析源 | 🔴 | S1 | 铁律2 writer-first + test_csv_schema_roundtrip |
| 2 双 registry 漂移 | 🔴 | S0 起全程 | S0 前置 test_bash_python_registry_symmetry CI 硬门 |
| 3 校验反转过松 | 🟡 | S2 | 校验同时验字段集 + 顺序 |
| 4 get_mapped_field 并存 | 🟡 | S1 | registry 收编 patterns，不并存 |
| 既有 jq//0 + except 吞 | 🟡 | S1/S5 | L3 验收看值非零 + grep `<img` |

**只要这 5 条防护都落实，本方案可安全实施，闭环验收标准 = L1+L2+L3 三层全绿（尤其 test_l3_rename_survives 根治验收过）。**

---

## §4 与 CP-1 的关系（已落地事实）

- CP-1 用方案乙（保留 aws_standard 列名 + 末尾加 cloud_provider 列）**回避**了断链，6 类 reader 一处未改。这是"绕过"。
- 本重构是"根治"：建 registry 后，物理字段名可随云变（aws_standard_iops ↔ baseline_iops）而 reader 经 resolve 不断。
- 落地后 CP-1 可从方案乙切回方案甲（字段名随云变更语义清晰），无断链风险。

---

## §4.5 列名终态决策 —— ⚠️ 已被 ADR-0001 取代（2026-05-30 重新拍板）

> ⛔ 本节原决策（随云变 aws_standard/baseline）已作废。
> **现行决策 = A 方案「三云统一中性 standard」，权威源见 analysis-notes/decisions/ADR-0001-disk-field-prefix-standard.md。**
>
> 作废原因（2026-05-30 代码审计 E1 实证）：原 §4.5 锁定"随云变 B"，但代码实际已实现"统一 standard A"
> （writer iostat_collector.sh:129 写 standard_iops / registry.py:29-33 三云=standard）。文档锁 B、代码做 A、
> reader 注释混写 → 文档与代码相反，是断链定时炸弹。重新评估后，A 更符合软件设计（关注点分离 /
> 消除 N 失败面 / 开闭 / 中立可读），且代码现状已是 A → 选 A 为"扶正"非"重写"。详见 ADR-0001。

### 现行终态行为（A，统一 standard）

| 环境 | writer 写的物理列名 | reader resolve 找的列名 | 对齐 |
|---|---|---|---|
| aws | `data_X_standard_iops` | `data_X_standard_iops` | ✅ |
| gcp | `data_X_standard_iops` | `data_X_standard_iops` | ✅ |
| other | `data_X_standard_iops` | `data_X_standard_iops` | ✅ |

- 逻辑名恒定 `disk_iops_provider_adjusted` / `disk_throughput_provider_adjusted`，reader 只认逻辑名。
- 物理名中性 standard，三云同名；云厂商信息由独立 `cloud_provider` 列承载（不污染指标名）。
- SRE 厂商术语贴近性需求 → 由展示层（HTML/图表 label，经 get_bottleneck_label "EBS"/"Disk"）满足。

### 🔴 仍有效的强制防护（与 A/B 无关，ADR-0001 后仍铁律）

> **reader 取 provider 的唯一合法来源 = CSV 自身的 `cloud_provider` 列，禁止 reader 运行时重新探测。**

- 此防护原为 B 方案设计，A 方案下三云同名虽不依赖 provider 拼列名，但 cloud_provider 列读取
  仍是数据可移植/自包含的正确做法，保留为铁律（D4）。
- 实现检查点：每个 disk reader 的 provider 来源必须是"读 CSV cloud_provider 列"，非 os 探测/环境变量/重 source。

### 执行追踪
- 当前进度 + 任务清单见 analysis-notes/EXEC-TRACKER.md（防丢失外置文件）。
- 当前阶段 = T（止血：消解 A/B 矛盾 + 文档扶正），T 完成前不推进 S2-S6。

---

## §6 附录：20 reader × 字段依赖完整矩阵（实证，文件:行）

> 🔴 **2026-05-31 核实更新**: 本矩阵是改名/解耦**前**的快照。部分 reader 后续已被重构经 registry,
> 矩阵的 `aws_standard 裸 endswith/jq key` 标注**部分过时**。已核实变化:
> - **report_generator.py**: §6.2 标"aws_standard 裸 endswith(:1761/1762/1779/1780)" —— 已重构为
>   `_resolve_disk_columns(df,'data','disk_iops_provider_adjusted')` 经 registry(L1794-1796 注释明写
>   "不认 aws_standard 字面量")。**该 reader 已解耦,改名不需再动它。**
> - **physical 列前缀**: 全矩阵 `aws_standard_*` 物理列名已随 registry 改为 `normalized_*`(reader 经 resolve 随动)。
> - **仍属实的硬耦合点**: framework_data_quality_checker.sh 整行 `==`(:82-84,行号偏移)未变,仍是最硬耦合。
> 核实方法: token-level read_file 亲读对应行 + E1。矩阵的"静默面/双源/下标脆弱"定性仍有效,仅"裸 aws_standard"字面量描述需按上述修正。

### 6.1 Python reader（analysis/）
- comprehensive_analysis.py: pandas 列名+子串。读 unified CSV(:906/213-217)。字段 timestamp/current_qps/cpu_usage/mem_usage/rpc_latency_ms + 子串'total_iops'(:373)。静默:safe_calculate_mean 缺列返0(:46-57)。
- cpu_ebs_correlation_analyzer.py: pandas 列名+startswith/endswith。读 unified(:58)。CPU 精确列 cpu_iowait/usr/sys/idle/soft(:62)。EBS 后缀 _util/_aqu_sz/_avg_await/_r_s/_w_s/_rrqm_s/_wrqm_s/_rareq_sz/_wareq_sz(:67-398)。
- network_analyzer.py: **NetworkFieldRegistry.group_by_semantic(:27)，唯一全解耦**。读 network_metrics.csv（外部传入 df）。
- qps_analyzer.py: ★主 reader。pandas 列名+动态发现+虚拟列注入。读 unified(:460)。current_qps/timestamp/cpu_usage/mem_usage/rpc_latency_ms + EBS 后缀(:85-161)。死代码:cliff(:193-429)/两套vegeta解析/detected_bottlenecks逻辑死路(:909)。
- per_method_attribution.py: csv.DictReader 列名。读 proxy_method.csv(:76)+unified(:105)。proxy:method_name/timestamp_ns/status_code/latency_ms(:79-90)。monitor 列名参数化默认 mem_used_mb(:98,分歧点)。
- degraded_report.py: csv.DictReader+候选名匹配。读 block_height_*.csv/performance_latest.csv 兜底。纯 stdlib 降级 reader。

### 6.2 Python reader（visualization/）
- report_generator.py(~275KB): 断链高发。读 unified(多处)+overhead+proxy_method.csv。aws_standard 裸 endswith(:1761/1762/1779/1780)。mem_used usecols 硬失败点(:2377→except 降0 :2380)。per_method except 吞为 HTML 注释(:4249-4251)。
- performance_visualizer.py(~138KB): 裸下标 self.df['cpu_usage'](9处)/['mem_usage'](6处)无守卫，KeyError→方法级 except→空图（最隐蔽）。EBS 主动排除 aws(:948 'aws' not in col)。
- ebs_chart_generator.py: 几乎全走 get_mapped_field（16+处 aws_standard :116/118/140/142/718/727/740/749/796/847/859/880/890/982/992/1013/1023/1044/1054/1055/1086/1102/1143/1147/1167/1238/1243/1255）。
- device_manager.py: 不读文件，提供 get_mapped_field(:135-161)+patterns字典(:20-133)。aws_standard 正则(:26/27/41/42)。第3级兜底易误匹配静默(:154-158)。

### 6.3 shell reader + offline_join
- master_qps_executor.sh: jq 按列名（CSV→JSON后）。aws_standard jq key(:316/326/338/348/688/689)，`//0` 静默兜底（最易漏的隐性断链）。
- bottleneck_detector.sh: header 名遍历取下标（健壮）。aws_standard(:872/874/899/901/1002/1006)。
- unified_monitor.sh: 主 CSV **writer-only**（cut -fN 仅作用于内部 overhead .log 非主 CSV）。
- ena_network_monitor.sh: **$NF/$(NF-1)/$(NF-2) 末尾列号(:204-206)最脆弱** + 名定位下标(:217-221)。读 ENA 独立 CSV。
- monitoring_coordinator.sh: 不读 CSV（只管 PID）。
- network_monitor.sh: pandas 委托 NetworkAnalyzer（按列名，健壮）。读 network 独立 CSV。
- ebs_analyzer.sh: 名解析下标(:40-68)→cut -f$N 读(:104-132)。用 total_iops/throughput **不读 aws_standard**。
- ebs_bottleneck_detector.sh: **CSV_FIELD_MAP 名→idx 查表(:84-101)**，最优雅。aws_standard(:135/136/168/169/178/179) + 显式缺字段报错(:187)。
- framework_data_quality_checker.sh: **整行 header 严格==(:80)**，expected 全硬编码(:346-396)，改任何字段→mismatch return 1（最硬耦合）。aws_standard 进 expected(:352/356/358)。
- offline_join.py: csv.DictReader 按列名。读 proxy/monitor 独立 CSV（ts_ns/method/status/latency_ns + proxy_cpu_pct 等）。

### 6.4 writer 端契约源头
- unified_monitor.sh:1926 generate_csv_header（9段拼接）+ generate_csv_data（同序对位）。basic:1927 / network:1929 / overhead:1930 / block:1931 / qps:1932 / cgroup:1957/1963/1967(三副本) / cloud_provider:1940/1942(末尾)。
- iostat_collector.sh:144 generate_device_header(21字段) + :127 data(对位)。
- monitoring/network/*.sh: generate_network_csv_header（已解耦范本）。
- per_method_attribution.py:222/231 csv.writer（proxy_method 输出端）。
