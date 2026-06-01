# Writer 端逐函数精读 — disk 改名调用链补全 (2026-05-30)

> 方法: token-level 全文分批 read_file 亲读(不 grep 抽样/不 delegate/不靠注释/不靠记忆),
> 每条结论贴 E1 文件:行。本文件补 proposal/ADR-0002/EXEC-TRACKER **遗漏的 writer 端**。
> 触发: 用户指出"当前沉淀文档不全面,writer 端只有零散行号没逐函数精读"。
> 加载 skill: token-level-careful-edit (Gate 2/3) + honest-self-check-no-fake-evidence (E1/E5)。
> 范围边界: reader 端已在 proposal §6 / ADR-0002 ⑧-⑭ 盘过; 本文件只补 writer 端。

---

## 文件 1: monitoring/unified_monitor.sh (2864 行, 16 批全文读完, 行号台账无跳行)

### 角色定性 (E1 全文实证)
unified_monitor.sh 对 disk 折算值是 **"组装 + 转发"** 角色, **不是 "计算" 角色**。
全文 2864 行 **无一处** 计算/写 disk 折算 IOPS/throughput(normalized/standard)。
- disk 折算值的 **header writer** = `generate_all_devices_header` (L1928 调用, 函数体在 iostat_collector.sh)
- disk 折算值的 **data writer** = `get_all_devices_data` (L2063 调用, 函数体在 iostat_collector.sh)
- 折算 **公式** 在 ebs_converter.sh (L21 source 进来)
→ 改名靶心在 iostat_collector.sh + ebs_converter.sh, 不在本文件。

### 纠正文档误判 (VERIFIED, E1)

**纠正-1 (最重要): 发现⑰ 的 "JSON 折算 key 断链" 路径不成立**
- ADR-0002 发现⑰: "master_qps 真实数据源是 JSON; 谁写 latest_metrics.json? 若 JSON writer 用裸字符串
  拼 disk 折算 key 而非 registry → 改名时 CSV 改了 JSON 没改 → 静默归零。"
- E1 实证 generate_json_metrics (L1988-2056):
  - L2021-2029 latest_metrics.json 只有 7 key: timestamp/cpu_usage/memory_usage/disk_util/disk_latency/network_util/error_rate
  - **没有折算 IOPS/throughput(normalized/standard) 字段**
  - L2015-2016: `disk_util=$(echo "$device_data"|cut -d',' -f9)` / `disk_latency=...-f7`
    → 按 **硬编码列号 f9/f7** 从 device_data 取 util/await, 不是按列名/折算 key
  - L2035-2053 unified_metrics.json 的 detailed_data.device_data (L2047) 是整段 21 字段原始 CSV 字符串原样塞入, 不解析成 key
- 结论: 改名只改折算 IOPS/throughput **列名**, 不动 util/await 的 **列号位置** → JSON 这条路不因改名断链。
  **发现⑰ 的断链路径证伪。** (但引出新风险 B, 见下)

**纠正-2: disk 段 writer 函数名文档记错**
- proposal §6.4 写 "iostat_collector.sh:144 generate_device_header + :127 data"
- E1: unified_monitor L1928 调 `generate_all_devices_header`(复数 all_devices), L2063 调 `get_all_devices_data`
- 真实入口是 all_devices 系列(多设备循环上层), 不是单数 device。改名找入口要按 all_devices 系列。

**纠正-3: header "9 段" 描述不准**
- proposal §2.1 说 9 段裸字符串拼接。E1 generate_csv_header (L1926-1944):
  basic(10,L1927) + device(函数,L1928) + network(10,L1929) + [ena 条件,L1939] + overhead(2,L1930)
  + block_height(6,L1931) + qps(3,L1932) + cgroup(函数,L1933) + cloud_provider(末尾,L1940/1942)
- device 段是 **唯一调函数动态生成的指标段**(其他全裸字面量) → 改名靶心。

### 文档未记的真风险 (VERIFIED, 新增)

**风险 A 🔴 主 CSV 写入零列数校验 (改名最大结构风险, 所有文档都没明确点出)**
- E1 主 CSV data 写入路径: L2174 `if safe_write_csv "$UNIFIED_LOG" "$data_line"`
- safe_write_csv 实现 (L2619-2670): 只做并发锁(L2634 等锁/L2652 建锁/L2662 删锁) + L2656 `echo "$csv_data" >> "$csv_file"` 裸 append。
  **无列数校验、无字段对位校验、无空字段检测。**
- 对比 overhead CSV: write_monitoring_overhead_log (L1772-1839) 有 validate_data_quality(L1812)
  + 列数对位校验(L1823 `actual==expected`)。**主 unified CSV 完全没有这层。**
- 后果: header(generate_all_devices_header) 与 data(get_all_devices_data) 列数若因改名重构不同步,
  **无任何运行时门拦截**, 直接写出错位 CSV。唯一会硬报错的是下游 framework_data_quality_checker
  整串等值(proposal §6.3), 即"改名后第一个会 fail 的点"。
- 改名验收推论: L3 必须验 header 列数 == data 列数(主 CSV), 不能靠 writer 自校验(它没有)。

**风险 B 🔴 JSON 用硬编码列号 f9/f7 取 disk 值 (G3-Hygiene-2 危险模式)**
- E1 L2014-2016: 注释 "21 fields: r_s,w_s,rkb_s,wkb_s,r_await,w_await,avg_await,aqu_sz,util",
  `disk_util=cut -f9`(util) / `disk_latency=cut -f7`(avg_await)。
- 风险: 改名重构若调整 device 段 **列序/列数**(如 registry 化时重排), f9/f7 静默取错列 → JSON
  disk_util/latency 拿到隔壁列值, 不报错。
- 这是改名重构必须守的 **隐式契约**: device 段前 9 列顺序(尤其 f7=await, f9=util)不可动。proposal/ADR 未记。

**风险 C 🟡 DEGRADED MODE NaN 污染源 (L3 验收混淆源)**
- E1 L254-256: `DEVICE_VALIDATION_DEGRADED=1` 时 "iostat columns will be NaN placeholders"。
- 设备校验失败 → disk 列变 NaN。L3 验收必须先确认 **非降级模式**, 否则分不清
  "改名断链导致的空/0 值" vs "设备没配导致的 NaN"。proposal/ADR 未记此混淆源。

**风险 D 🟡 注释撒谎第 4 处 (code-comments-are-claims)**
- E1 L2586-2587: 函数名 `validate_ebs_thresholds` + 注释 "EBS configuration validation",
  但内部变量已是 `BOTTLENECK_DISK_IOPS_THRESHOLD`(L2591) / `BOTTLENECK_DISK_THROUGHPUT_THRESHOLD`(L2597)。
- 函数名/注释还是 ebs, 变量已 disk → EXEC-TRACKER N3(文件/函数改名 TODO) 的残留。

### 验证文档准确的部分 (VERIFIED, E1)
- cgroup 19 字段三副本: L1957(disabled)/L1963(缺文件)/L1967(python失败兜底) ✅ proposal §2.1 准
- cloud_provider 末尾列 + get_provider_name 写(L2071, fallback env L2074) ✅ ADR-0001 D4 准
- BOTTLENECK_EBS_*→DISK_* 改名在本文件已落实(L2566/2591/2597 全是 DISK) ✅ EXEC-TRACKER N1 准
- data 段手工位置对位(L2151/2158 拼接序 == header L1940/1942 序) ✅ EXEC-TRACKER §5.3 准
- 层3 provisioned 源 = DATA_VOL_MAX_IOPS(L2566 basic_config_check 校验) ✅ ADR-0002 层3 准
- 层4 THRESHOLD 源 = BOTTLENECK_DISK_*_THRESHOLD(L2591-2599 校验 50-100) ✅ ADR-0002 层4 准

### 顺带发现的相邻技术债 (非 disk 改名, 记录防遗忘)
- get_memory_data 注释 L358 说返回 mem_used_mb, 实际 L387 输出 mem_used(无_mb) → 注释撒谎(对应 proposal §2.3 mem 列名分歧 writer 源头)
- 框架实际产 **6 个 CSV/log** (文档只列 4): unified.csv + ENA + network + per_method + PERFORMANCE_LOG(L1023) + ERROR_LOG(L1364)。EXEC-TRACKER §5.4 "多个 CSV" 清单不全。
- 跨进程文件 sample_count(L2186, cleanup L192 删) — 文档完全没提
- L2355 awk 双引号嵌套 `awk "BEGIN {printf "%.1f"...}"` 疑似引号被吞(对比 L2366 单引号正确) — fixed-duration 进度显示, 非数据路径, 既存小 bug
- error log header 字面量重复 2 处: L1364 + L2846

---

## 文件 2: monitoring/iostat_collector.sh (310 行, 2 批全文读完)

### 角色定性 (E1 全文)
**这是 disk 折算值的真正 writer 靶心。** unified_monitor 调的 generate_all_devices_header(L210) /
get_all_devices_data(L172) 函数体在此; 折算值在 get_iostat_data(L26-130) 算 + 输出。

### 21 字段位置契约 (E1 L65-78 抽取 + L129 输出, 改名铁律)
```
位置: 1   2   3     4     5       6       7         8      9   10     11     12       13       14       15       16          17           18        19         20             21
字段:r_s,w_s,rkb_s,wkb_s,r_await,w_await,avg_await,aqu_sz,util,rrqm_s,wrqm_s,rrqm_pct,wrqm_pct,rareq_sz,wareq_sz,total_iops,standard_iops,read_thr,write_thr,total_thr_mibs,standard_throughput_mibs
```
- 折算值在 **第17位(standard_iops)** + **第21位(standard_throughput_mibs)**。
- **坐实风险 B**: unified_monitor JSON `disk_latency=cut -f7`=avg_await ✅ / `disk_util=cut -f9`=util ✅,
  与此处顺序一致。改名只改第17/21位的 **名**, 不动位置 → JSON f7/f9 安全。
  **风险 B 精化结论: 改名安全的充要条件 = 不重排 device 段 21 列顺序(尤其前9列)。**

### header/data 双源对位机制 (E1, 改名安全性根本)
- **header** generate_device_header(L138-169): 主路径 L160 `csv_registry_disk_header "$prefix" "$provider"`
  → 走 registry → 列名 `${prefix}_standard_iops`(第17) / `${prefix}_standard_throughput_mibs`(第21)。
- **data** get_iostat_data(L129): 21 个 **纯值** 硬编码字符串拼接, **不带列名**, 靠位置对位 header。
- 多设备: header L237(DATA)+L245(ACCOUNTS可选) / data L189(DATA)+L198(ACCOUNTS可选), 各自拼接。
- **关键**: header 走 registry, data 走硬编码顺序 → 改名改 registry 列名时 data 不自动跟变。
  但改名只改名不改序, data 值不带名 → **改名不破对位**。仅当"改名顺带重构列序"才需手工同步 data L129(无校验兜底, 见 unified_monitor 风险 A)。

### 坐实 EXEC-TRACKER §5.6 真 BUG (E1 L158-168, 现状确认仍在 + 精化)
```
159| if declare -F csv_registry_disk_header; then
160|   csv_registry_disk_header "$prefix" "$provider"   ← 主路径 registry, 写 standard ✅
161| else                                                ← fallback (registry 未 source)
164|   local dfp="standard"                              ← 默认 standard
165|   declare -F get_disk_field_prefix && dfp="$(get_disk_field_prefix ...)"  ← 若 getter 存在则覆盖!
167|   echo "...${prefix}_${dfp}_iops...${prefix}_${dfp}_throughput_mibs"
```
- 精化: fallback L164 先 standard, 但 L165 若 get_disk_field_prefix 存在就 **覆盖成 provider 层值**
  (gcp_provider get_disk_field_prefix = baseline, 据文档) → registry未source + GCP + getter存在 → 写 baseline_iops,
  reader 经 registry 找 standard(改名后 normalized) → 静默断链。**BUG 现状确认存在。**

### 改名在本文件的精确落点 (E1, 补 EXEC-TRACKER 空白)
1. L164 fallback `dfp="standard"` → `"normalized"` (真 BUG 修复点之一)
2. L165 fallback get_disk_field_prefix 覆盖逻辑 — 需联动 provider 层改名(否则 fallback 仍写旧值)
3. L90 `standard_throughput_mibs` / L121 `standard_iops` 局部变量名 — 内部, 不进列名, 一致性改(中立化)
4. 21 字段位置契约(L129) — 改名 **不可动位置**(守 JSON f7/f9 + reader 列序)
5. 主路径 header(L160 csv_registry_disk_header) — 不在本文件, 改 registry 即随动

### 注释撒谎第 5 处 (code-comments-are-claims)
- L64 注释 "eliminate hardcoded indices", 但 L65-78 全是 `${fields[1]}`..`${fields[22]}` 硬编码 iostat 列索引(采集端依赖, 非改名范围)。
### 注释准确的 (验证为真, 非撒谎)
- L213-215 "writer provider 源=get_provider_name / reader 从 cloud_provider 列取, 不可混用" — E1 L217 代码确实如此 ✅ 符合 ADR-0001 D4。

### 降级模式列数稳定 (E1, 好设计)
- 降级 header(L223-232)/data(L176-185) 都产 "21字段×设备数" 占位(header 设备名占位/data NaN) → 列数不破。呼应风险 C: NaN=降级标志, L3 验收要区分 NaN(设备没配) vs 0/空(改名断链)。

---

## 文件 3: utils/ebs_converter.sh (191 行, 2 批全文读完) — 折算公式 writer 真身

### 折算公式 1: IOPS (convert_to_standard_iops L33-68) — 已 provider-aware 中立化
```
L45-48: conv_func = get_iops_conversion_func()   (provider 层分流键; getter 不可用→passthrough)
L50-67: case:
  aws_*/*ceil*  → multiplier = ceil(avg_io_kib / io_cap_kib)[最小1]  →  iops × multiplier  (L60-61)
  GCP/other/passthrough → iops 原样 (L65)
```
- AWS 公式(L60): `multiplier = ceil(avg_io_size_kib / cap)`, cap 默认 256(SSD)/1024(HDD)。按 I/O size 拆分计数。
- GCP/other: passthrough(不拆分)。
- **印证 ADR-0002 层2 normalized 语义** = "按云厂商规则折算到统一口径"。折算已中立(L50 case 分流), 非"AWS 写死"。
- 边界: L39 非正 iops→0; L54-57 无 io_size 信息→退化 passthrough(不凭空放大, 避免假告警)。

### 🔴 折算公式 2: throughput (convert_to_standard_throughput L75-88) — **零折算 (重大语义事实)**
- E1 L85-87: `echo "$actual_throughput_mibs"` — **直接返回原值, 完全不折算**。
- **后果(ADR-0002 没记)**: 第21列 standard_throughput_mibs == 第20列 total_throughput_mibs, **值恒相等**。
  → 改名后 `normalized_throughput_mibs` 永远 == `total_throughput_mibs`。
  → **throughput 的 normalized 层是退化的(恒等于 total); 只有 IOPS 真折算。** 五层模型对 throughput 而言层1≡层2。
  → 改名/出图/告警时不要假设 throughput 的 normalized 与 total 不同(它们一样)。

### 🟡 向后兼容别名 (L169-176) — 违背用户"不留旧烙印名"偏好
- L171-172 保留 `convert_to_aws_standard_iops` / `convert_to_aws_standard_throughput` 作别名 + export(L175-176) + help(L188-189)。
- 用户偏好: 反对软链接/旧名兼容("留旧烙印名违背中立, 宁 breaking change 求干净")。
- 改名收尾应评估删除这俩 aws 别名 — 先 grep 确认无外部调用方/测试仍依赖旧名。

### 🟡 文件头/help 仍 "AWS EBS" (L3-4 / L185 / L188-189) + 文件名烙印 (N3 残留)
- 实现已三云中立(L50 case), 但标题/help 措辞还是 AWS → 注释滞后。
- 文件名 `ebs_converter.sh` 按 ADR-0001/0002 应改 `disk_converter.sh`(ebs=AWS 专属), 但属文件改名(breaking,
  需联动 iostat_collector L14 等所有 source 点)。

### 发现⑨ "计算双源" — writer 那一半锁定
- writer 折算公式 = 本文件 L60 (AWS: iops × ceil(io_kib/cap))。
- 发现⑨ 称 ebs_chart_generator.py 有第二套重算。验证闭环 = 读 ebs_chart_generator._recalculate*,
  对比是否同样 ceil(io_size/256)。**这是发现⑨ 的最后一步**(reader 端, proposal §6 已部分矩阵化)。

### 其他常量 (E1)
- L7 AWS_EBS_BASELINE_THROUGHPUT_SIZE_KIB=128 (注释称 throughput 转换基线, 但 L85-87 实际没用它 → 死常量/历史残留)。
- L10 IO2_THROUGHPUT_RATIO=0.256 / L14 IO2_MAX_THROUGHPUT=4000 (仅 calculate_io2_throughput L93-98 用, EBS 类型推荐路径)。
- recommend_ebs_type(L120-139) / analyze_instance_store_performance(L103-115): AWS EBS 选型建议, 非 disk 指标采集主路径, 改名不涉及。

---

## 三文件精读总结 — disk 改名调用链 writer 端全貌 (E1 闭环)

**数据流(writer)**: iostat -dx → get_iostat_data(L26 算 21字段, 折算调 ebs_converter) → get_all_devices_data(多设备拼值) → unified_monitor.safe_write_csv(裸 append 无校验) → CSV。
**列名(writer)**: generate_device_header(registry 主路径/fallback 兜底) → generate_all_devices_header(多设备拼名) → unified_monitor.generate_csv_header(L1928 调) → CSV header。

**改名 standard→normalized 的全部 writer 落点(E1, 主路径走 registry 自动随动, 需手改的是 fallback + 内部变量 + 注释)**:
| # | 文件:行 | 内容 | 类型 |
|---|---------|------|------|
| 1 | csv_schema_registry.sh/.py | DISK_FIELD_PREFIX / 逻辑名 disk_iops_provider_adjusted | **单源(改这就主路径全动)** |
| 2 | iostat_collector.sh:164 | fallback `dfp="standard"`→normalized | 真BUG修复 |
| 3 | iostat_collector.sh:165 | fallback get_disk_field_prefix 覆盖逻辑 | 联动 provider 层 |
| 4 | iostat_collector.sh:90/121 | data 局部变量名 standard_* | 内部一致性(不进列名) |
| 5 | ebs_converter.sh:33/75 | 函数名 convert_to_standard_* | 已中立(无需改, normalized 是列名层不是函数层) |
| 6 | ebs_converter.sh:169-176 | aws 旧别名 | 评估删除(用户偏好) |
| 7 | provider 层 get_disk_field_prefix | aws/gcp/other 返回值(gcp=baseline?) | BUG 联动确认 |

**改名安全铁律(E1 实证)**:
- 充要条件 = **不重排 device 段 21 列顺序**(守 unified_monitor JSON f7=await/f9=util + reader 列序)。
- writer 主 CSV 无列数校验(unified_monitor safe_write_csv) → header(registry)/data(硬编码L129) 列序必须人工保证一致。
- throughput normalized ≡ total(零折算), 只 IOPS 真折算。
- L3 验收必须区分 NaN(降级模式/设备没配) vs 0/空(改名断链)。

## 待读 (reader/可视化端 — "文件生成→使用→生成图片→HTML 引用"链)

---

## 文件 4: visualization/ebs_chart_generator.py (1343 行, 4 批全文读完) — disk 折算图生成器

### 🔴 计算双源实锤 + 升级 (skill 点名 L153-169, E1 全文确认比 skill 描述更严重)
- `_recalculate_disk_standard_metrics`(L153-197) 在 `__init__`→`_init_framework_methods`(L114) 阶段
  **原地覆写** `self.df[data/accounts_*_std_iops]` 列。
- chart 重算公式(L169-172 DATA / L191-194 ACCOUNTS, 完全相同):
  `df[std_iops] = total_iops.where(avg_io_kib>16, total_iops*(avg_io_kib/16))`
  → io>16 用原值; io≤16 **线性缩小** (×avg_io/16)。**无任何 provider 分支**(对三云套同一公式)。
- **公式三方对比 (E1 实锤, 三套互不一致且方向相反)**:
  | 来源 | 文件:行 | 公式 |
  |---|---|---|
  | writer AWS | ebs_converter.sh:60 | total×**ceil**(avg_io/cap), cap=256/1024, **放大≥1** |
  | writer GCP/other | ebs_converter.sh:65 | passthrough(不变) |
  | chart 重算 | ebs_chart_generator.py:169 | io>16原值 / io≤16 ×(avg_io/**16**) **缩小≤1**, 无视 provider |
- **升级结论 (比 skill "双源" 更准)**: 因 L114 在构造期就覆写, 之后所有图读到的折算列都是 chart 版,
  **writer 写进 CSV 的折算值在本生成器内被完全丢弃(覆写)= ebs_chart 链上 writer 折算值是死代码,
  实际出图用的是 chart 的 16KiB 公式(错误且无视 provider)。**

### 折算列的真实消费者 (E1, 修正第二批"几乎不消费"的初判)
- 容量分析图 `_create_aws_capacity_analysis`(L263-447): 用 **total 原始列**算利用率(注释L274"not provider-adjusted"), **不用折算列**。
- iostat 性能/相关图(L449-744): 用 read/write/util/aqu/await **原始 iostat 列**, 不用折算列。
- **但以下 4 张图大量消费折算列(经 chart 覆写版)**:
  1. `generate_ebs_performance_overview` 图1/2(L764/786) — plot 折算 IOPS/吞吐 vs provisioned
  2. `generate_ebs_bottleneck_analysis` 图1/2(L893/926) — **L914 `bottleneck_points = df[折算列]>threshold` 折算值判瓶颈点**
  3. `generate_ebs_aws_standard_comparison` 全图(L1028/1059/1090/1117/1148) — 专门对比 Raw vs Standard, summary 算 Difference%(L1122/1137)
  4. `generate_ebs_time_series`(L1189/1213/1239/1301) — 归一化/移动均线/峰谷/统计
- **后果**: comparison 图标榜"Raw vs Standard"对比, 但 Standard 是 chart 用 16KiB 线性公式(无视 provider)算的,
  **不是 writer 的 AWS ceil(256) 折算** → 这张图在 AWS 上系统性偏离真实折算关系; 瓶颈判定也基于错误折算值。

### 改名安全性 (reader 端, E1)
- ✅ 所有折算列访问走 `_resolve_disk_field(逻辑名, 设备前缀)`(L130-151) → `CSVSchemaRegistry.resolve`(L141)
  → 取 suffix 后正则匹配真实列名(L147-149)。改 registry standard→normalized **自动随动**, 不硬编码列名。
- ✅ provider 从 CSV cloud_provider 列读(L111/L116-128 `_read_cloud_provider_from_csv`), 符合 D4 铁律(不运行时探测)。
- 🟡 **silent-None 面**(L150 `return None`): registry 改名后与 CSV 不同步 → resolve 返回 None →
  L765/787/894/1030 等 `if field and field in columns` 为假 → **整张子图静默跳过(空白图), 不报错**。
  **改名验收必须验这 4 张图非空 + 折算列值非全 0**(呼应 skill silent-zero 验收铁律)。

### 🟡 多义词 baseline 再现 (E1)
- L67-73 DeviceManager 返回键名 `data_baseline_iops`/`accounts_baseline_iops` = **层3 provisioned**(额定上限 VOL_MAX),
  注释 L63 也说 "Provisioned ceiling (VOL_MAX)"。变量左侧已用 `self.data_provisioned_iops`, 但字典键仍 baseline。
- 与 chart 重算的 "16 KiB baseline"(层5 IO 基准块, L168/170) **同词不同义** → ADR-0002 baseline 多义实证。
- 改名时 DeviceManager 的 `*_baseline_iops` 键(层3)应改 provisioned, **不能误伤层5 的 16KiB baseline**。待 device_manager.py 确认键源。

### 🟡 函数名/产出 png 文件名仍带 aws 烙印 (N3 残留 + HTML 引用联动点, E1)
- L1015 `generate_ebs_aws_standard_comparison` 函数名 + L36 `CHART_FILES['comparison']='ebs_aws_standard_comparison.png'`。
  docstring/标题已改 "Disk Standard"(L1016/1022) 但函数名 + png 名还是 aws。
- **关键**: `ebs_aws_standard_comparison.png` 是**产出图片文件名**, HTML 报告按此名引用(待 report_generator 验证)。
  改 png 名 = breaking, 必须联动 report_generator 里引用该文件名处。CHART_FILES 还有 `ebs_aws_capacity_planning.png`(L31) 同理。
- L1337 `validate_ebs_integration` 的 `len(CHART_FILES)==7`(L1341) 是 change-detector 式硬编码(测试自检, 非生产路径)。

### 待读
- device_manager.py: `get_mapped_field`/`get_threshold_values`/`build_field_mapping`/`is_accounts_configured` 实现
  (ebs_chart 的 field 映射 + 阈值 + baseline 键全委托给它 — 必须读 body 验"经 registry"与 baseline 键源)。
- performance_visualizer.py(2564): 主出图器, disk 段另一大消费者。
- report_generator.py(4859): HTML 报告生成 + 图片 `<img src>` 引用(png 文件名联动点)。

---

## 文件 5: visualization/device_manager.py (599 行, 2 批全文读完) — 字段映射/阈值中枢

### 🟢 baseline 多义彻底澄清 (E1 L308-340, 确证隔离, 修正 ebs_chart 那批的误伤担忧)
- `get_threshold_values`(L316-340) 注释 L311-315 明确: `data_baseline_iops`/`data_baseline_throughput`
  = **业务配置变量**(来自 DATA_VOL_MAX_IOPS 环境变量), **不是 CSV 列名, 不经 registry** = 层3 provisioned(利用率分母)。
- 改名 standard→normalized **完全不碰这些 baseline 键**(不同层/不同来源)。✅ 代码层确证隔离, 不会误伤。
- 折算 CSV 列另走 registry(`_disk_iops_suffix` L34 / `_resolve_disk_suffix` L170-178)。两类概念代码注释 L31-33 已自证区分。

### 🔴 aws 业务别名键有真实消费者 (E1, 改名第二层命名债, ADR-0002 未明确覆盖)
- 别名键 `aws_standard_iops`/`aws_standard_throughput_mibs`(aws 烙印) value 已中立(registry suffix), 但 key 本身是烙印名。
- **真实消费链(E1, 非死键)**:
  1. patterns 字典 key(L46-47/62-63) — `'data_aws_standard_iops': rf'...{registry_suffix}'`
  2. build_field_mapping(L430-433/456-460) — provider_aware_suffix_map 产 mapping key `{device}_aws_standard_iops`
  3. **validate_ebs_configuration(L581/589)** — `data_fields=['data_aws_standard_iops',...]` 经 check_data_availability→get_mapped_field 消费
  4. get_device_label metric_map(L506-507) — 显示标签 'AWS Standard IOPS'
- 注释 L45/429/503/579 都自承"保留 aws_standard 作业务别名"。
- **与 ebs_chart 的 `_resolve_disk_field`(直接 registry) 是两条并行取折算列路径**: ebs_chart 主用直接 registry; validate 用别名→patterns。
- **改名定性(需用户裁定)**: value 自动随动, 但 key `aws_standard_*` 违背"不留烙印名"偏好。
  按用户偏好应改 `disk_normalized_*`, 涉及: patterns L46-47/62-63 + build_field_mapping L431-432 + validate L581/589
  + get_device_label L506-507 + 全仓 grep `aws_standard_iops` 确认无其他消费者。**这是 ADR-0002 物理名之外的第二层命名债。**

### 🔴 改名隐蔽风险: get_mapped_field 的 fallback 模糊匹配 (E1 L218-222)
- get_mapped_field 优先级: 精确列名(L206) → patterns 正则(L211) → **fallback 子串/后缀模糊匹配(L218-222)**:
  `if field_name in col or col.endswith(field_name.split('_')[-1])`。
- **风险**: 改名后若 patterns 正则没匹配上折算列, fallback 会用 `endswith('iops')` 撞到 total_iops 等错误列 → **静默取错列(非 None, 是错值)**。
  比 silent-None 更隐蔽(返回的是合法但错误的列)。改名验收必须验折算图取的是折算列不是 total 列。

### 🟡 既存 bug (非改名引入, E1)
- get_baseline_values(L342-351) L349-350 无条件读 `accounts_baseline_*`, 但 get_threshold_values 仅 ACCOUNTS 配置时才加这俩键(L334-338)
  → **未配 ACCOUNTS 时 get_baseline_values KeyError**。待确认有无消费者。

### 🟢 改名安全 (reader 端, E1)
- 折算列两路径都经 registry(`_resolve_disk_suffix` L178 + patterns value L46 用 `self._disk_iops_suffix`), 改 registry 自动随动 ✅
- provider 从 CSV cloud_provider 列读(L156-168), D4 铁律 ✅
- silent-None 面: `_resolve_disk_field` L197 / get_mapped_field L224 / find_field_by_pattern L482 均 return None
- is_accounts_configured(L227-263): 配置驱动优先(env)+ 数据列兜底, 与 ebs_converter.sh is_accounts_configured(shell 端) 是跨语言双实现(需口径一致)

### 待读
- performance_visualizer.py(2564): 主出图器, disk 段另一大消费者。
- report_generator.py(4859): HTML 报告生成 + 图片 `<img src>` 引用(png 文件名联动点)。

---

## 文件 6: visualization/performance_visualizer.py (2564 行, 6 批全文读完) — 主出图器(~14 张 png)

### 🟢 核心结论: performance_visualizer 全程不消费折算列, 对 standard→normalized 改名基本不敏感 (E1 全文)
- 所有 disk 图(overview L262 / correlation L394 / util L553 / await L682 / device_comparison L948 / smoothed L1501
  / efficiency L1713 / cliff / bottleneck_identification L1950)取的都是**原始 iostat 列**:
  `total_iops` / `total_throughput_mibs` / `util` / `avg_await` / `aqu_sz` / `r_s` / `w_s`。
- 注释多处自证 "iostat raw data"(L309/328/342/1060)。**没有任何函数 plot 折算列 `*_standard_iops`/`*_normalized_iops`**。
- 折算图全部**委托** EBSChartGenerator(L2264/2273/2533-2540, 每次 new 新实例→每次重触发 chart 端 16KiB 覆写重算)。

### 🔴 取列机制与 ebs_chart 完全不同 + 一个改名失效的冗余过滤器 (E1)
- **取列方式**: 全用 `[col for col in df.columns if col.startswith('data_') and col.endswith('_<suffix>')]` 硬编码后缀,
  **完全绕过 DeviceManager.get_mapped_field / registry**。两套并行 reader 取列机制(ebs_chart 走 registry; perf_viz 走硬编码后缀)。
- 🔴 **create_device_comparison_chart L948-949/956-957 用 `'aws' not in col` 过滤折算列**:
  `[... if 'total_iops' in col and 'aws' not in col]`。
  - 当前命名下原始列=`*_total_iops`(含 total_iops 子串)、折算列=`*_aws_standard_iops`(不含 total_iops),
    实际靠 `'total_iops' in col` 就已区分, `'aws' not in col` 是**冗余防御**(不影响功能)。
  - **但改名 standard→normalized 后 `'aws' not in col` 语义失效**(normalized 无 'aws' 子串)→ 留一个"看似防折算列实则靠 total_iops 区分"的误导性死过滤器。
  - 定性: N3 aws 烙印残留 + 防御逻辑债。改名时应清理(删 `'aws' not in col` 或改判断), 否则误导后人。

### 🟡 silent 空图面 (E1)
- 取列用 `xxx_cols[0]`(L316/341/428/559/688/969...), 都有 `if xxx_cols:` 守卫 → 列缺失画 "No Data" 文本(L335/353/417/523/1523), 不崩不报错。
- 改名让原始列匹配不上时显示 No Data(静默空图)。但原始列名稳定, 本次 standard→normalized 不动原始列, 故 perf_viz 不受影响。
- 🟡 残留风险: 若未来改原始列名(total_iops→...), perf_viz 的硬编码后缀全断链(不在本次范围, 记录备查)。

### 产出 png 清单 (generate_all_charts L1275-1391, HTML 引用来源)
advanced(委托 AdvancedChartGenerator) + 7 张 ebs_*(委托 EBSChartGenerator) + block_height_sync_chart.png
+ performance_overview.png + cpu_ebs_correlation_visualization.png + device_performance_comparison.png
+ smoothed_trend_analysis.png + await_threshold_analysis.png + qps_trend_analysis.png
+ resource_efficiency_analysis.png + bottleneck_identification.png + util_threshold_analysis.png
+ monitoring_overhead_analysis.png + performance_cliff_analysis.png

### 待读 (新会话续读优先级)
- ✅ report_generator.py(4859) — 2026-05-31 全文读完(见文件 7)。
- advanced_chart_generator.py(1231): 另一出图器(委托自 perf_viz L1300), 是否消费折算列待查 = ★下一优先★。
- config/csv_schema_registry.sh: bash SSOT, 验 DISK_FIELD_PREFIX 与 python 1:1 对称(test_csv_registry_symmetry)。
- chart_style_config.py(715): UnifiedChartStyle + load_framework_config(被所有出图器依赖)。

---

## 文件 9: visualization/advanced_chart_generator.py (1231 行, ★全文 100% 读完 2026-05-31★) — 高级统计出图器(被 perf_viz L1300 委托)

### 🟢 入口 = generate_all_charts (E1 L1065-1104)
产 7+ 图: pearson_correlation_analysis / linear_regression_analysis / negative_correlation_analysis / ena_limitation_trends + ena_connection_capacity + ena_comprehensive_status / comprehensive_correlation_matrix / performance_trend_analysis / performance_correlation_heatmap。

### 🟢 大部分图取 iostat 原始列(util/aqu_sz/avg_await/r_s/w_s/cpu_*), 不取折算列 → 改名不敏感 (E1)
- pearson(L183-198)、regression(L310-313)、negative(L408-409): 精确 endswith 取 util/aqu_sz/r_s/w_s。
- ENA 三图(L682-1063): 全走 ENAFieldAccessor, 独立。ena 保留不改。

### 🔴🔴 折算列"误纳/双份"横切隐患 (改名敏感 + 疑似既有统计 bug, E1 token-level)
**根因: 多处用子串 `in` 匹配吞吐/IOPS, 会把层1原始列(total/read/write_throughput_mibs)与层2折算列(standard/normalized_throughput_mibs)同时命中。**
1. **performance_trend_analysis throughput 图 L614**: `'throughput' in col and 'mibs' in col` → 命中 read+write+total(层1) + standard/normalized(层2 折算), 取 `[0]`(L617)。**画的是原始还是折算取决于列字母序**, 改名(standard→normalized)改变字母序 → `[0]` 选中列可能静默切换 → 图内容变。IOPS 图 L599 `'total_iops' in col` 当前 schema 仅命中 total(较安全)。
2. **comprehensive_correlation_matrix L495-501**: `ebs_patterns` 含 `'total_iops'/'throughput_mibs'`, `pattern in col`(L497) + `matching_cols[:2]`(L501) → 原始+折算列都进候选, `[:2]` 截断纳哪 2 个随列序变 → 改名敏感。
3. **correlation_heatmap L1118-1122**: `select_dtypes(number)` 全数值列, 仅排除 timestamp/current_qps/test_duration → **折算列+原始列同时入大热图**(改名不敏感, 不按名取; 但本就是双份重复入矩阵的设计)。
→ 改名验收必查: trend throughput 图 + correlation matrix 改名前后画的列是否同一个(防 `[0]`/`[:2]` 静默漂移)。

### 🟡 死代码 (E1, 建议清理)
- `get_field_name_safe`(L143-157) 含最宽松 fuzzy(`field_name.lower() in col.lower()` 无 avg/max 排除), **全文无调用** = 死代码。改名不敏感(不被调用)。
- analysis/ 各文件(qps/comprehensive/network/cpu_ebs_correlation/rpc_deep/degraded/per_method_attribution): 查有无硬编码折算列后缀(改名断链高发点) = ★下一优先★。

---

## 文件 10: visualization/chart_style_config.py (714 行, ★全文 100% 读完 2026-05-31★) — 纯样式/布局工具类
- 🟢 **改名完全不敏感**: 全是 FONT/COLORS/CHART_CONFIGS/SUBPLOT_LAYOUTS/COLORMAPS 常量 + getter classmethod + 时间轴格式化。无任何 CSV 列名/折算列/字段解析。
- `load_framework_config`(L22-113): source config_loader.sh 抓 env(读 DATA_VOL_MAX_IOPS 等层3阈值配置变量到 dict), 不碰 CSV 列名。被所有出图器依赖但只供样式/阈值, 非字段链。
- 不进改名落点清单。

---

## 文件 11: analysis/qps_analyzer.py (1220 行, ★全文 100% 读完 2026-05-31★) — QPS 性能/瓶颈/cliff 分析器

### 🔴 throughput 字段提取脆弱契约 (改名敏感, E1 L138-149)
- `_get_dynamic_key_metrics`(L77-189): `disk_throughput_field` 提取 L141 `startswith('data_') and endswith('_throughput_mibs')` + `break`(取列序首个)。
- `endswith('_throughput_mibs')` 同时命中 read/write/total(层1) + standard/normalized(层2 折算)。`break` 选**列序首个** → 当前 CSV header(iostat_collector L22-44) total(L42) 排在 provider_adjusted(L43) 前 → break 选 total(层1, 正确), 但**脆弱**: 改名/列重排会让 break 命中折算列 → cliff 分析的 throughput 指标静默从原始切到折算。
- 对比 IOPS L128 `endswith('_total_iops')` 安全(折算列结尾是 `_iops` 非 `_total_iops`, 不命中)。util/latency/queue(L85/100/107/154) 全精确取 iostat 原始列。
- 影响面: 这些字段只进 cliff factor 变化率比较(L255-274), 不进 png 名/翻译键。改名验收需确认 throughput cliff 指标取的仍是 total 列。

### 🟢 其余全不碰折算列 (E1)
- L281-1220: cliff 图/CSV加载/QPS性能图(CPU/Mem/Latency/SuccessRate 时序)/vegeta 解析/评分/报告 全用 cpu_usage/mem_usage/rpc_latency_ms/current_qps/vegeta。
- comprehensive_analysis L373 `'total_iops' in col`+`.sum(axis=1)`(待全读确认): total_iops 子串当前仅命中层1, 跨设备求和, 改名不敏感。
- L508 注释 "mapped standard field names" 的 standard = 英文"标准"词义, 非折算列。

---

## 文件 12: analysis/comprehensive_analysis.py (944 行, ★全文 100% 读完 2026-05-31★) — 顶层编排器
- 🟢 **基本不碰折算列**。是编排器: 调 qps_analyzer + rpc_deep_analyzer + PerformanceVisualizer(L809-810 委托出图) + 生成综合报告。
- VERIFIED L373 `ebs_iops_fields=[col for col if 'total_iops' in col]`+`.sum(axis=1)`(L375): 子串 total_iops 当前**仅命中层1**(折算列是 `_iops` 结尾不含 total_iops), 跨设备求和画 Total IOPS vs QPS。改名不敏感, 正确实现。
- `analyze_bottleneck_correlation`(L250-304): 全数值列 corr(L272 select_dtypes), 折算+原始列都进 correlations dict, 但按列名遍历不取特定名 → 改名不敏感(自动随动); 同样"双份入相关性"特征(非改名问题)。
- 其余(CPU/Mem/RPC vs QPS 图 + 评分 + 报告)全用 current_qps/cpu_usage/mem_usage/rpc_latency_ms。
- 不进改名落点清单(L373 安全)。

### analysis/ 剩余待读
cpu_ebs_correlation_analyzer.py(612, grep 全取 util/aqu_sz/await/r_s/w_s 原始列, 预判改名不敏感待证) / network_analyzer.py(162, 走 NetworkFieldRegistry 独立) / rpc_deep_analyzer.py(549, grep 全 cpu/mem/rpc/qps) / degraded_report.py(390) / per_method_attribution.py(234) / per_method_report.py / per_method_charts.py。

### 文件 13: analysis/cpu_ebs_correlation_analyzer.py (612 行, ★全文 100% 读完★) — 🟢 改名完全不敏感
18 种相关性分析全部**精确 endswith** 取 iostat 原始列(util/aqu_sz/avg_await/r_s/w_s/rrqm_s/wrqm_s/rareq_sz/wareq_sz) + cpu_* 标量。无子串匹配、无 throughput/iops、不碰折算列。analysis/ 最干净文件。不进落点清单。

### 文件 14: analysis/per_method_attribution.py (234 行, ★全文 100% 读完★) — 🟢 不碰 disk 折算列
proxy sink CSV + monitor CSV 的 method 级 CPU/MEM 归因(权重=method_count/total_count)。列名 cpu_usage/mem_used_mb/timestamp(可配参数)。**坐实 CP-1 坑**: L98 默认 `mem_col="mem_used_mb"`, report_generator L4268 显式传 `mem_col="mem_used"` 覆盖(生产真实列名), 漏传则内存归因恒 0(静默)。已修但脆弱列名契约。改名不敏感。

### 文件 15: analysis/network_analyzer.py (162 行, ★全文 100% 读完★) — 🟢 不同 registry/不同 CSV, 完全不相关
走 NetworkFieldRegistry.group_by_semantic 分析 network_metrics.csv (throughput/packet/saturation/drop/error counter)。L3-4 文档"零 platform 分支, 禁 hardcode ena_*/gvnic_*"。与 disk 折算列改名无任何关系。不进落点清单。

### analysis/ 仍待读: rpc_deep_analyzer.py(549) / degraded_report.py(390) / per_method_report.py / per_method_charts.py

### 文件 16: analysis/degraded_report.py (390 行, ★全文 100% 读完★) — 🟢 不碰 disk 折算列
降级模式 HTML(performance.csv 缺失时 fallback), 纯 stdlib。只读 vegeta JSON + block_height CSV(local_block_height/block_height/height 列 L172)。L274 文案明确"Disk I/O analysis skipped"。改名不敏感。

### 文件 17-18: visualization/per_method_report.py(247) + per_method_charts.py(283) (★全文 100% 读完★) — 🟢 不碰 disk 折算列
- report.py: HTML 章节生成器, 消费 PerMethodQpsRow/ResourceRow(method/qps/p99/error/cpu_share), 独立 PER_METHOD_TRANSLATIONS dict。`<img src>` 路径由调用方传入。
- charts.py: 纯 stdlib SVG 出图 4 类(qps/latency/error/resource 堆叠), 产 `per_method_*_<chain>.svg`(不含 ebs/aws/standard)。
- **关键**: per_method 出 .svg 不是 .png, 由 report_generator `_generate_per_method_section_safe`(L4280) 独立 render, **不走** `_generate_chart_gallery_section` glob+翻译键机制 → 不受 png 改名联动影响。改名完全不敏感。

### analysis/ 仅剩: rpc_deep_analyzer.py(549) — grep 仅命中 sync_data_available(block_height, 非 disk), 预判改名不敏感待全读证。

### 文件 19: analysis/rpc_deep_analyzer.py (549 行, ★全文 100% 读完★) — 🟢 不碰 disk 折算列
RPC 性能深度分析(latency trend/IQR 异常/QPS-latency 相关/cliff/瓶颈分类) + 报告。全用 rpc_latency_ms/current_qps/cpu_usage/mem_usage/block_height_diff。无字段名子串匹配。改名不敏感。

### ★analysis/ 全目录读完结论 (9 文件)★
analysis/ 唯一改名敏感点 = qps_analyzer L141 throughput 提取脆弱契约(endswith `_throughput_mibs`+break, 当前列序选 total 正确但脆弱)。其余 comprehensive(L373 total_iops 安全)/cpu_ebs_correlation(精确后缀)/network(独立 registry)/per_method×3(svg 不走 png 联动)/degraded(不读 disk)/rpc_deep(纯 RPC) 全部改名不敏感。

---

## 文件 7: visualization/report_generator.py (4859 行, ★全文 100% 读完 2026-05-31★) — HTML 报告生成器

### 🟢 折算列读取经 registry (E1 L1638-1655 `_resolve_disk_columns`)
- `provider = _provider_from_df(df)`(L1651, 从 CSV cloud_provider 列读, D4 ✅) → `CSVSchemaRegistry.resolve(logical, provider, '')`(L1653)
  → `[col for col in df.columns if col.startswith(prefix) and col.endswith(suffix)]`(L1655)。改名自动随动 ✅。注释 L1644 自承"不保留 aws_standard 字面量"。
- 🟡 silent 面: 返回 `[]`(L1650/1655), 下游 `if cols:` 守卫则静默跳过。

### 🔴 图表翻译键 ↔ png 文件名映射 = png 改名的 HTML 联动链 (E1)
- 翻译键命名规律 `chart_<png_stem>` + `chart_<png_stem>_desc`(TRANSLATIONS, en L514-597 / zh L1073-1156):
  - `chart_ebs_aws_standard_comparison`(L570/1129) ↔ png `ebs_aws_standard_comparison.png`(ebs_chart CHART_FILES L37)
  - `chart_ebs_aws_capacity_planning`(L560/1119) ↔ png `ebs_aws_capacity_planning.png`(ebs_chart L31)
- **png 改名联动链(改 1 个 ebs png 名要同步 3 处)**: ①ebs_chart CHART_FILES(L31-37) ②report_generator 翻译键 en+zh 各一对(键名+_desc) ③按 stem 拼 `chart_<stem>` 的查找逻辑(在 L1721+ 未读区, 待确认)。
- 🟡 文案层 aws 烙印(L171/231/451/565/567/570/1008/1119/1126/1129...): HTML 给用户看的 "AWS标准IOPS"/"AWS容量规划", GCP 用户困惑(用户中立化关注点), 属 UX 文案层不影响数据链。

### 🟡 其他 (E1)
- `_validate_overhead_csv_format` L1427 `expected_fields=20` 硬编码 overhead CSV 列数(只 print 不 fail, L1432-1433, change-detector 隐患)。
- `parse_ebs_analyzer_log`(L1501) 解析 ebs_bottleneck_detector.log 文本(IOPS/Throughput 正则切分) = reader 消费 writer 日志的文本契约。
- `_load_config`(L1200-1206) 读 DATA_VOL_MAX_IOPS 等环境变量(层3 provisioned 配置)。

### report_generator L1721-4859 精读结论 (2026-05-31 本会话补全, E1)

**🟢🔴 png→HTML 真实联动机制 = 动态画廊 glob, 非硬编码 (E1 L3812-3870 `_generate_chart_gallery_section`)**
- 真实出 HTML 的是动态画廊: `_discover_chart_files()`(L3704-3763) glob 扫磁盘所有 *.png → `chart_key=basename.replace('.png','')`(L3839) → `title_key=f'chart_{chart_key}'`(L3842) / `desc_key=f'chart_{chart_key}_desc'`(L3843) → `<img src="{rel_path}">`(L3859, rel_path 来自 glob 磁盘扫描)。
- **★关键: png 改名后 `<img src>` 自动随动 (glob 不硬编码), 但翻译键 `chart_<旧stem>` 失配 → L3844 silent fallback 到 `basename.replace('_',' ').title()` 丑标题, 不报错。** = png 改名验收必查项(标题不能退化成自动丑标题)。
- 入口确认: main(L4819)→generate_html_report(L2067)→_generate_html_content(L3872)→拼装段 L3923-3938 只调 `_generate_chart_gallery_section()`(L3897)。

**🔴 `_generate_charts_section`(L3946-4217) = 死代码 (E1)**
- 271 行静态 chart 定义表(硬编码 filename 字面量, 含 L4068 `ebs_aws_capacity_planning.png` / L4093 `ebs_aws_standard_comparison.png` + 翻译键 chart_<stem>+_desc), **但 _generate_html_content 从不调用它** (拼装段无此方法)。
- 改名影响: 此处硬编码 filename 改不改都不影响产物(死代码), 但应一并清理避免误导后人。**之前(L362-366)以为静态表是联动点③的主链, 修正: 真正生效的是动态画廊的翻译键失配。**

**🟢 EBS 7 图名全含 'ebs' 前缀 → 分类不破 (E1 L4068/4073/4078/4083/4088/4093/4098)**
- `_categorize_charts`(L3765-3810) 靠关键字 'ebs'/'aws'/'iostat'(L3796) 归类。7 张 ebs 图全 `ebs_*` 开头, 改名去 'aws' 后仍含 'ebs' → 仍归 ebs 类 ✅。

**🟢 折算列(provider_adjusted)消费点 = AWS EBS baseline 表, 经 registry (E1 L1795-1796/1813-1814)**
- `_resolve_disk_columns(df,'data'/'accounts','disk_iops_provider_adjusted')` 入 HTML baseline 统计表(Min/Max/Avg)。改名随动 ✅。注释 L1794/1812 自承"经 registry, 不认 aws_standard 字面量"。

**🟢 iostat 原始列(total_*)消费 = 硬编码后缀匹配, 不经 registry (E1)**
- "iostat raw sampling stats"表 L1915/1934 `startswith('data_'/'accounts_') and endswith(f'_{metric}')`, metric∈{total_iops,total_throughput_mibs,util,avg_await}(层1)。
- performance_summary L4788/4792 endswith `_total_iops`(层1)。本次改名不动 total, 但若将来层1改名这是断链点。

**🔴 fuzzy 模糊匹配技术债分散三处 (改名后 silent 撞名高发区, E1)**
- ①device_manager `get_mapped_field` fallback(L218-222, 前轮已记) ②report_generator `_resolve_disk_columns`(经 registry, 较安全) ③本文件 `find_matching_column`(L3378-3390, CPU-EBS 相关性表用, target=util/aqu_sz/r_await 等 iostat 原始字段, 非折算列)。三套独立实现, 改名验收须确认无 endswith/in 撞到折算列。

**🟡 多处 silent 兜底 (E1)**
- per_method section(L4219-4285): 文件缺失静默返空(L4235/4242), 异常吞进 HTML 注释(L4283-4285)。**L4265-4268 注释自承 CP-1 已修内存列名坑**: `read_monitor_csv(mem_col="mem_used")` 不显式指定→per-method 内存归因恒 0(静默) = parallel-entry-trap 同类债(已修)。
- get_mapped_field 经 device_manager fallback(L2642/2647 取 total_iops)。

**🟢 不消费折算列的 section (改名不敏感, E1)**: monitoring_overhead(L2118+)、resource_distribution/impact 图(L2390-2747, 取 cpu/mem/net)、EBS bottleneck(L2749-2906, 取 JSON 非 CSV)、ENA(L3101-3290, ENAFieldAccessor 独立)、CPU-EBS correlation(L3292-3485, 取 iostat 原始列)、block_height(L3487-3702, 取 JSON+block_height 列)、system bottleneck(L4287-4388, 取 bottleneck_data dict)。

### ★联动点③ 最终结论 (修正 L366)★
png 改名 (ebs_aws_standard_comparison.png → 新名) 实际只需联动 2 处, 不是 3 处:
1. **ebs_chart_generator.py CHART_FILES(L31-37)** — 生成端文件名(改这里 png 才真正改名)
2. **report_generator 翻译键 en+zh `chart_<新stem>` + `_desc`(L514-597/1073-1156)** — 否则动态画廊 silent fallback 丑标题
3. ~~静态表 _generate_charts_section 硬编码 filename~~ = **死代码, 改产物无影响, 仅建议清理**
- 动态画廊 `<img src>` glob 随动, 无需改。

---

## 文件 8: utils/csv_schema_registry.py (140 行, 全文读完) — ★改名单一真相源(SSOT)★

### 🟢🔴 改名 standard→normalized 的"靶心"= 这 3 个 value (E1 L29-33)
```python
DISK_FIELD_PREFIX = {"aws": "standard", "gcp": "standard", "other": "standard"}
```
- 整个 disk 折算物理列名的**唯一来源**: resolve(L127) `dfp = DISK_FIELD_PREFIX.get(provider,"standard")` → template `{prefix}_{dfp}_iops`(L85) → `data_standard_iops`。
- **改名只需把这 3 个 value 改 "normalized"**, 所有经 registry 的 reader(ebs_chart/device_manager/report_generator)全自动随动 ✅ — 解耦设计的兑现点。
- 注释 L22-28 已锁定方案甲(中立命名三云统一 standard, provider 由 cloud_provider 列承载) = ADR-0001/0002 一致。

### 🔴 两个硬约束 (E1)
1. **bash 对称实现必须 1:1 同步改**(注释 L4/L15): `config/csv_schema_registry.sh` 的 DISK_FIELD_PREFIX 必须同步改 normalized,
   否则 writer(bash 写 CSV)与 reader(python 经 registry)**列名错位断链**。有 `test_csv_registry_symmetry` 守护(L15), 改完必跑。= parallel-entry-trap 数据层命门。
2. physical_template `{prefix}_{dfp}_iops`(L85/89) 本身不动, 只动 dfp 值。

### 🟢 SSOT 层硬失败不静默 (E1 L119-126)
- resolve 未注册 logical_name 直接 `raise KeyError`(L123), 不返回空。比各 reader 的 silent-None 好。
- **但** reader 在 registry 之上又包 silent 兜底(ebs_chart L150 None / device_manager L197 None / report_generator L1655 []),
  registry 的 KeyError 会被 reader 的 try 或 `if cols` 吞掉 → 改名验收仍须验值非空, 不能只看"没抛异常"。

### 🟢 provider_aware 仅 2 字段 (E1 L66/85/89)
- `disk_iops_provider_adjusted`(L85) + `disk_throughput_provider_adjusted`(L89) 是仅有的 2 个 provider_aware(物理名随云变)。
  其余 19 个 disk 字段 provider_aware=False(物理名固定)。**改名只影响这 2 个折算字段。**

---

## ★改名 standard→normalized 最小落点清单 (E1 汇总, 截至已读 19 文件 — 全链路读完 2026-05-31)★
1. **utils/csv_schema_registry.py:30-32** — DISK_FIELD_PREFIX 三 value standard→normalized (Python SSOT)
2. **config/csv_schema_registry.sh:65-67** — `_csv_registry_disk_field_prefix` 三 case 全 `echo "standard"`→`"normalized"` (bash SSOT, 必须与 python L30-32 1:1, test_csv_registry_symmetry 守护)。template L96/L100 `${prefix}_${dfp}_iops` 不动, 逻辑名清单 L22-44 不动。
   **⚠ 同时修正过时注释 L15-16** `# aws->aws_standard / gcp->baseline / other->standard` — 此注释撒谎(code-comments-are-claims), 真实代码 L65-67 已三云统一 standard, 注释是 ADR-0001 前的残留。改名时勿被注释误导以为三云 prefix 不同。
3. 改完上述 2 处, 经 registry 的 reader 全自动随动: ebs_chart/device_manager/report_generator ✅ (E1 已验三者都走 registry)
4. **第二层命名债(可选, 需用户裁定)**: device_manager 的业务别名键 `aws_standard_iops`(patterns/build_field_mapping/validate/get_device_label) — registry value 随动但 key 仍 aws 烙印
5. **冗余死过滤器**: performance_visualizer.py:948-949/956-957 `'aws' not in col` 改名后语义失效, 应清理
6. **png 文件名 + 翻译键(可选, breaking)**: ebs_aws_standard_comparison.png / ebs_aws_capacity_planning.png + report_generator 翻译键 en/zh
7. **chart 计算双源(独立 bug, 非改名但同区)**: ebs_chart_generator.py:153-197 重算覆写折算列, 公式与 writer 三方不一致且无视 provider

## 改名验收铁律 (E1, 多 reader 有 silent 兜底)
- 禁止"跑通没报错"=通过。必须验: ①折算图非空 ②折算列值非全 0 ③chart 折算值与 CSV writer 折算列一致(若修双源)
  ④bash/python registry header 字节级一致 ⑤device_comparison 图取的是 total 列不是误匹配折算列。
  ⑥**新增(本会话)**: throughput 类提取(qps_analyzer L141 / advanced perf_trend L614 / advanced matrix L495)改名前后画的列必须仍是 total 不是折算列(防 endswith/`in`+`[0]`/`[:2]` 随列字母序静默漂移)。
  ⑦**新增**: png gallery 改名后翻译键 `chart_<新stem>` 必须配齐 en+zh, 否则 silent fallback 丑标题。

## ★全链路横切隐患汇总 (E1, 非改名也存在的技术债, 本会话精读发现)★
**A. fuzzy/子串匹配技术债 4+ 处独立实现**(改名后撞名高发, 应统一收敛到 registry):
  - device_manager get_mapped_field fallback(L218-222) / report_generator _resolve_disk_columns(经 registry 较安全)+find_matching_column(L3378) / advanced get_field_name_safe(L143 死代码,最宽松) / qps_analyzer L141 / comprehensive L373。
**B. 层1+层2 双份入相关性矩阵**(疑似既有统计 bug, 非改名): advanced comprehensive_correlation_matrix(L495 `pattern in col`) + correlation_heatmap(L1118 全数值列) + comprehensive analyze_bottleneck_correlation(L272 全数值列) 都会把 total_* 原始列 + standard/normalized 折算列同时纳入同一相关性计算 → 同一物理量重复计入。
**C. 死代码 3 处**(建议清理): report_generator `_generate_charts_section`(L3946-4217, 271 行静态 chart 表从不被调用) / advanced get_field_name_safe(L143) / performance_visualizer `'aws' not in col` 死过滤器(L948)。
**D. silent 兜底链**: 各 reader 在 registry KeyError 之上包 try/`if cols`/返空串 → 改名验收不能只看"没抛异常"必须验值。CP-1 内存列名(per_method mem_col="mem_used" vs 默认"mem_used_mb")漏传则归因恒 0。

## ★全链路读完总结 (2026-05-31, 19 文件 token-level 精读)★
writer 侧(unified_monitor/iostat_collector/ebs_converter) + registry(py+sh SSOT) + reader 侧(ebs_chart/device_manager/report_generator/advanced/chart_style + analysis 9 文件)全链路已亲读。
**改名 standard→normalized 真实最小落点 = 2 处 SSOT(py L30-32 + sh L65-67)**, 经 registry 的 reader 全自动随动。
**非 registry 的脆弱点(需人工核)**: qps_analyzer L141 + advanced L495/L614(throughput endswith/子串 + 截断, 当前列序正确但脆弱)。
**可选清理**: 死代码 3 处 + device_manager aws_standard 业务别名键 + png/翻译键 breaking。
**独立 bug(非改名)**: ebs_chart 双源重算(L153-197) + 多处层1/层2 双份入相关性矩阵。

---

# ════════ 第二轮复核 (2026-05-31, 扩大范围: network 纳入 + resolver body 再读) ════════

> 方法同第一轮(token-level read_file 亲读, 不 delegate/不 grep 下结论, 每条 E1)。
> 触发: 用户要求基于第一轮文档逐问题再读实际代码, 扩大调用链(尤其 network), 找漏判/误判。
> 本轮亲读: csv_schema_registry.py(全) + config/csv_schema_registry.sh(全) + utils/network_field_registry.py(全)
>   + monitoring/network/{interface,aws_ena,gcp_gvnic,gcp_virtio,other_none}.sh(全 5 个)
>   + analysis/network_analyzer.py(全) + visualization/device_manager.py L90-325(network 字段区+get_mapped_field)
>   + tests/_verify_registry.py。

## 复核-A 🟢 disk SSOT 结论第一轮正确, 但行号表述需统一 (VERIFIED E1)
- csv_schema_registry.py: `DISK_FIELD_PREFIX = {` 在 **L29**, 三 value 在 **L30/L31/L32**, 闭合 `}` L33。
  → 改名精确改 L30/L31/L32 三个 `"standard"`。第一轮文档内部一处写 "L29-33" 一处写 "L30-32" → **统一为: dict 块 L29-33, 待改 value L30-32**。
- config/csv_schema_registry.sh: `_csv_registry_disk_field_prefix` L63-69, 三 case echo 在 **L65/L66/L67**。✅ 第一轮落点准。
- 注释撒谎坐实: sh **L15** `# aws->aws_standard / gcp->baseline / other->standard`, 真实 L65-67 三云统一 standard。改名连带清此注释。✅ 第一轮记录准。
- bash↔python 对称有测试守护: **tests/test_csv_registry_symmetry.sh 存在(6365 字节)** + tests/_verify_registry.py(仅验 python 内部一致性, 不验跨语言)。✅

## 复核-B 🔴🔴 第一轮重大盲区: network 字段【不经 csv_schema_registry】, 走完全独立的第二 SSOT (VERIFIED E1)
- csv_schema_registry(py+sh) **只注册 disk 段 21 字段**(py `_DISK_FIELDS` L68-90 / sh `_CSV_REGISTRY_DISK_LOGICAL` L22-44), resolve case 零 network 分支。VALID_SEGMENTS 虽列 network/ena(py L42) 但**无任何 network FieldDef**。
- network 真正 SSOT = **utils/network_field_registry.py** (NetworkFieldRegistry), 与 disk registry 是**两个独立文件、两套机制**。
- **结论(对本轮 network 改名需求关键)**: disk 改名(DISK_FIELD_PREFIX) 与 network 改名**完全解耦, 互不影响** = 好消息; 但第一轮把 network 判"不相关"略过 → **network 改名落点至今空白, 本轮补全(见复核-C/D/E)**。

## 复核-C 🔴 network 命名架构与 disk 根本不同 → "network 改名"语义必须先澄清 (VERIFIED E1)
- network **没有** disk 的 `{prefix}_{dfp}_xxx` provider_aware 模板。network 物理名 = **平台特异硬前缀**: `ena_*`(AWS) / `gvnic_*`+`virtio_*`(GCP), 公共列 `rx_bytes/tx_bytes/rx_packets/tx_packets/network_saturation_signal`(无前缀)。
- NetworkFieldRegistry 是**静态字段名→语义类型映射表**(_SEMANTIC_MAP L20-47, 14 个平台特异 key), **无 resolve 物理名功能**(只有 get_semantic_type/group_by_semantic)。reader 靠语义分组取列, 不靠物理名。
- 前缀写死在正则 `^(ena|gvnic|virtio)_` (py L72/L77)。
- **"network 改名"两种可能含义, 代价天差地别**:
  - (a) 若指 disk 那种"中立化去厂商前缀"(ena_→?): 则**伤筋动骨** = 改 4 个 provider .sh header/采集 + _SEMANTIC_MAP 全 14 key + 2 个正则 + validate_csv_columns 前缀校验(L85/91-99)。**且 ena/gvnic/virtio 是真实驱动名(ethtool driver), 不是厂商烙印** → 按 ADR-0001 约束"ena=AWS 专属驱动→保留", network 前缀**本就不该中立化**。
  - (b) 若指 disk standard→normalized 那一个 dfp 改名: **network 根本没有这个维度**, 不涉及 network。
  → **需用户澄清: network 到底要不要改、改什么。当前证据强烈建议 network 维持现状(驱动名是物理事实)。**

## 复核-D 🔴 network 真实跨进程脆弱契约 (AP4 writer/reader skew, 第一轮完全没记, VERIFIED E1)
- writer network 字段名是**多处独立硬编码字符串变换现拼**, 无 bash registry resolve:
  - aws_ena.sh L42 `ena_${field/_allowance/}`: 把数组 `bw_in_allowance_exceeded`(L11) **删 `_allowance`** → 写出 `ena_bw_in_exceeded`。**变换逻辑藏在 header 拼接里**。
  - gcp_gvnic.sh L30 `gvnic_${field}` / gcp_virtio.sh L33 `virtio_${field}` + L35 额外手拼 `virtio_per_queue_rx_drops_sum`。
- reader NetworkFieldRegistry._SEMANTIC_MAP key(py L29 `'ena_bw_in_exceeded'`) 必须与 writer 变换后物理名**字节级一致**, 否则 get_semantic_type 返 'unknown' → 该列静默漏归类(group_by_semantic 丢进 unknown 组, analyze 不分析它)。
- bash 端 get_network_field_metadata(每 provider .sh 各一份) 与 python _SEMANTIC_MAP 是**双实现**(py L3/L18 自承"与 bash 1:1 对称"), **但 grep 未发现 network 版对称测试**(只有 disk 的 test_csv_registry_symmetry)。→ network 改名/加字段时, bash 三处变换 + python 静态表 + (可能)无测试守护, 极易漂移。

## 复核-E 🔴 第一轮漏判的 network 真断链点: device_manager 硬编码 ENA 全称字面量 = 既存死映射 (VERIFIED E1)
- visualization/device_manager.py patterns 字典(__init__):
  - L97-101: `bw_in_allowance_exceeded` 等 5 个**裸全称**(无 ena 前缀)
  - L102-106: `ena_bw_in_allowance_exceeded` 等 5 个**ena 前缀+全称**
  - 全部带 `_allowance_`, value 是同名裸正则。
- **但 writer 写进 CSV 的实际列名是删掉 `_allowance` 的 `ena_bw_in_exceeded`(aws_ena.sh L42)** → device_manager 这 10 个 key 的正则**永远 match 不上真实列**:
  - get_mapped_field(L199-225): 精确列名(L206 不中)→patterns 正则(L211-216, `re.match('ena_bw_in_allowance_exceeded', 'ena_bw_in_exceeded')` 不中)→fallback(L218-220, `'ena_bw_in_allowance_exceeded' in 'ena_bw_in_exceeded'` 不中, endswith('exceeded') **可能误撞任一 *_exceeded 列**!) → 多半 None 或撞错列。
- **定性**: 既存 bug(非改名引入), 违反 network_analyzer.py L4 禁令"下游禁 hardcode ena_*/gvnic_* 字面量"。需确认有无消费方真请求这些 ENA field(若无=死键, 清理即可; 若有=静默错列/None)。**与本次 disk standard→normalized 改名无关, 但属"network 相关逻辑解耦"必须治理的债**(用户本轮明确要 network 纳入)。
- 注: device_manager L220 fallback `endswith(field_name.split('_')[-1])` 对 network 同样是隐患(所有 `*_exceeded` 字段后缀都是 'exceeded', 互相撞)。

## 复核-F 🟢 network reader(analysis/network_analyzer.py) 本身干净 (VERIFIED E1)
- 全程零 platform 分支, 靠 group_by_semantic 按语义取列(L27/36-57), _detect_platform_from_columns(L62-69) 用 get_platform_prefix 正则识别平台。
- reader 端改 network 物理名只要 registry 同步即自动随动。✅ 第一轮"network_analyzer 不相关"对**这个文件**成立; 但第一轮据此把**整个 network 子系统**判为不相关 = 过度外推(真断链在 device_manager, 见复核-E)。

## ★第二轮复核总结★
1. **disk standard→normalized 改名结论第一轮全部成立** = 2 处 SSOT(py L30-32 + sh L65-67)+ 注释 L15。本轮零推翻, 仅统一行号表述。
2. **第一轮最大盲区已补**: network 自成独立 SSOT(network_field_registry), 与 disk 改名解耦; network reader 干净。
3. **本轮新发现 2 个 network 真问题**(第一轮漏):
   - 复核-D: network writer 字段名靠隐式字符串变换(`/_allowance/`), 与 reader 静态表跨进程字节契约, 无对称测试守护。
   - 复核-E: device_manager L97-106 硬编码 10 个 ENA 全称字面量, 与真实 CSV 列名不符 = 既存死映射 + fallback endswith 撞名隐患。
4. **network "改名"需求需用户澄清**: ena/gvnic/virtio 是真实驱动名(物理事实, 非厂商烙印), 按 ADR-0001 应保留 → 当前强烈建议 network 物理前缀维持现状; 真正该治理的是复核-D/E 的对称契约债, 不是"中立化前缀"。

---

# ════════ 第三轮: network 分流逻辑正确性验证 (2026-05-31, 用户确认分流已实现, 只需验对) ════════

> 触发: 用户指出 network 两云字段数量+语义不同, 应有分流逻辑, 确认分流已实现后要求验证逻辑正确。
> 本轮补读(前两轮漏读的分流核心): config/cloud_provider.sh(全) + monitoring/network_monitor.sh(全)
>   + monitoring/network_unified_entry.sh(全)。
> ★自我纠正: 前两轮把 network 判"不相关"+ 只看 reader, 漏读了整个分流派发层 → 给出偏负面印象。
>   实际分流逻辑【已存在且设计良好】(接口契约+variant 派发+语义注册表 reader)。★

## 复核-G 🟢 分流架构 = (CLOUD_PROVIDER, NIC_DRIVER) 二元组派发 (VERIFIED E1, 设计正确)
完整链路:
```
config/cloud_provider.sh detect_cloud_provider():
  detect_platform()   -> CLOUD_PROVIDER ∈{aws,gcp,other}  (L13-39, metadata 内容校验非 exit code, 防沙盒误判)
  detect_nic_driver() -> NIC_DRIVER ∈{ena,gvnic,virtio,none} (L48-62, ethtool -i driver: ena/efa→ena, gve→gvnic, virtio_net→virtio)
  CLOUD_PROVIDER_VARIANT = ${CLOUD_PROVIDER}_${NIC_DRIVER}  (L69) 合法4值 aws_ena|gcp_gvnic|gcp_virtio|other_none (L73)
  → monitoring/network_unified_entry.sh L26: source network/${VARIANT}.sh
  → 4 函数接口契约 L41-46 强制校验(缺函数 fail 不静默)
  → network_monitor.sh cmd_start 调 4 函数写 CSV → network_analyzer.py 按语义分组读
```
- **为何按"云+driver"而非纯"云": GCP 一云两 driver(gve gvnic / virtio_net), 字段集完全不同** → 纯按 CLOUD_PROVIDER 无法区分。二元组是正确设计。✅
- 三层降级兜底完整: 非法 variant→cloud_provider.sh L80/84 other_none; provider 文件缺→entry L29; init 失败→network_monitor L65 重 source。

## 复核-H 🟢 逐 variant writer↔reader 字节级三方对账全部一致 (VERIFIED E1, 分流核心正确性)
**aws_ena (6 字段)**: writer `ena_${field/_allowance/}` 变换后 = ena_bw_in_exceeded/ena_bw_out_exceeded/ena_pps_exceeded/ena_conntrack_exceeded/ena_linklocal_exceeded/ena_conntrack_available ↔ python _SEMANTIC_MAP L29-34 **6/6 一致** ↔ bash 通配 ena_*_exceeded(L81)+conntrack_available(L82) 全覆盖。✅
**gcp_gvnic (3 字段)**: gvnic_tx_drops/gvnic_rx_no_buffer/gvnic_tx_timeout ↔ python L37-39 **3/3 一致** ↔ bash L69-70。✅
**gcp_virtio (5 字段)**: virtio_rx_drops/virtio_tx_tx_timeouts/virtio_rx_xdp_drops/virtio_tx_xdp_tx_drops/virtio_per_queue_rx_drops_sum ↔ python L42-46 **5/5 一致** ↔ bash L75-76。✅ (writer header 顺序: 4数组循环+末尾手拼 per_queue_sum, reader 按语义分组不依赖顺序)
**公共 5 字段**: rx_bytes/tx_bytes→throughput, rx_packets/tx_packets→packet_count, network_saturation_signal→saturation_signal, 三端一致。✅
- **语义分流正确**: AWS limit-exceeded→saturation_counter(云限速语义) / GCP drops→drop_counter(丢包语义) / timeout→error_counter。两云不同瓶颈语义正确分开。✅
- **列数 variant 间不同(6/3/5/0)不会错位**: reader 用 group_by_semantic 按语义取列, 不按列号/列数。呼应 G3-Hygiene-2(列数随配置变只要无固定列号 reader 即安全)。✅

## ★第三轮结论: network 分流逻辑端到端正确 (VERIFIED)★
主链 writer(cloud_provider 派发→4 variant 实现)→CSV→network_analyzer reader 三 variant 全字节对齐, 分流派发+字段契约+语义分类+降级兜底全部正确。
**唯一破坏分流抽象的旁路 = 复核-E device_manager.py L97-106 硬编码 10 个 ENA 全称字段(_allowance_ 与真实列名不符)**, 违反"下游禁 hardcode 平台字段"契约, 是 network 子系统唯一需治理的真债(主监控/分析链不受影响)。
**前两轮误判更正**: 不是"分流缺失/不相关", 而是分流已实现且正确, 前两轮漏读派发层(cloud_provider.sh/network_monitor.sh/network_unified_entry.sh)。

---

# ════════ 第四轮: ENA 旁路债影响面深挖 — 发现两套并存且字段名互斥的 network 监控体系 (2026-05-31) ════════

> 触发: 用户选"先查 device_manager 旁路债的实际影响面"。深挖 ENA 字段消费链时发现远比 device_manager 死键严重的真 bug。
> 本轮亲读: utils/ena_field_accessor.py(全) + advanced_chart_generator.py L805-875(ENA 图) + report_generator.py L3155-3215(ENA 分析/表)
>   + config/system_config.sh L10-22 + config/config_loader.sh:685 + config/providers/{aws,gcp,other}_provider.sh get_nic_allowance_fields
>   + monitoring/ena_network_monitor.sh L50-95(老 ENA writer header)。

## 复核-I 🔴🔴🔴 ENA 字段名【三套互不兼容】的命名, 主分析链静默断裂 (VERIFIED E1, AP5 五步坐实)
**三套 ENA 字段名形态 (E1 实证)**:
| 来源 | 文件:行 | ENA 字段物理形态 | 举例 |
|---|---|---|---|
| ① 新体系 writer (Y+) | monitoring/network/aws_ena.sh:42 | `ena_` 前缀 + **删 `_allowance`** | `ena_bw_in_exceeded` |
| ② 老体系 writer | monitoring/ena_network_monitor.sh:93-94 | **裸全称**(无前缀,保留 `_allowance`) | `bw_in_allowance_exceeded` |
| ③ reader 配置/访问层 | system_config.sh:15-22 / config_loader.sh:685 / aws_provider.sh:33 / ena_field_accessor.py FIELD_CONFIG | **裸全称**(同②) | `bw_in_allowance_exceeded` |

**断链事实 (AP5 Step 1-5)**:
- ENAFieldAccessor.get_available_ena_fields(ena_field_accessor.py:85-94) 用 `if field_name in df.columns`(L91) **精确匹配**, field_name 来自 configured_fields = 环境变量 ENA_ALLOWANCE_FIELDS_STR(裸全称 ③) 或 fallback FIELD_CONFIG.keys()(裸全称 ③)。
- **若 CSV 由【新体系 network_monitor.sh】产生** (列名 `ena_bw_in_exceeded` ①) → `'bw_in_allowance_exceeded' in df.columns` 恒 False → **6/6 全 miss → 返回 [] → 所有 ENA 图表/HTML 分析静默跳过**:
  - advanced_chart_generator.py:838 `_generate_ena_connection_capacity_chart` → 空 → L843 `if not available_field: return None`
  - report_generator.py:3158 `_analyze_ena_limitations` → 空 limitations
  - report_generator.py:3210 `_generate_ena_data_table` → L3211 `if not ena_columns: return ""`
- **若 CSV 由【老体系 ena_network_monitor.sh】产生** (列名 `bw_in_allowance_exceeded` ②=③) → 精确匹配命中 → ENA 分析正常。
- **结论**: ENA 可视化/HTML 分析链【只兼容老体系 writer】, 与新 Y+ 体系 writer 字段名互斥。新旧体系并存(network_monitor.sh:10 注释自承"Old ena_network_monitor.sh continues to coexist") → **取决于实际跑哪个 writer, ENA 分析可能整段静默失效**。这是 P1 静默 bug(非改名引入), 比 device_manager 死键(复核-E)严重: 那是单文件旁路, 这是 ENA 主分析接口。

## 复核-J 🔴 disk 改名分析的前提矛盾: provider getter 仍返回旧物理名 (VERIFIED E1, 修正前三轮)
- **第二轮复核-A 说 sh L15 注释"gcp->baseline"撒谎、真实三云统一 standard** — 这对 **csv_schema_registry.sh** 成立。
- **但** config/providers/{aws,gcp,other}_provider.sh 的 `get_disk_field_prefix` **仍返回旧的 provider 物理名**(E1):
  - aws_provider.sh:37 `get_disk_field_prefix() { echo "aws_standard"; }` 注释"保持 AWS 历史字段命名 aws_standard_iops"
  - gcp_provider.sh:37 `echo "baseline"` 注释"GCP 字段命名 baseline_iops"
  - other_provider.sh:35 `echo "standard"`
- **这正是第一轮 iostat_collector.sh 复核里记的真 BUG(文件2 L126-128 fallback L165)的根源**: registry 主路径返 standard(三云统一), 但 provider getter 返 aws_standard/baseline/standard(三云不同)。**两个 SSOT 对同一物理名给出不同答案**:
  - registry 路径(csv_schema_registry) → `data_standard_iops`(三云)
  - provider getter 路径(get_disk_field_prefix) → `data_aws_standard_iops`(aws) / `data_baseline_iops`(gcp) / `data_standard_iops`(other)
- **改名 standard→normalized 落点必须扩充**: 不只 csv_schema_registry 2 处, 还要决定 get_disk_field_prefix 三返回值怎么办。当前只要主路径(registry)生效、fallback(getter)不触发, 改 registry 即可; 但只要 registry 未 source 而 getter 触发(iostat_collector.sh:165), 就写出 getter 的旧名 → 改名后断链。**这是第一轮已标但本轮坐实根因的真 BUG, 改名前必须连同 get_disk_field_prefix 一起治理或确认 fallback 永不触发。**

## ★第四轮结论★
1. **device_manager 旁路债(复核-E)影响面查清**: 它不是孤例, 是 ENA 字段【三套命名不兼容】症候群的一个表现。真正严重的是复核-I(ENAFieldAccessor 主分析链与新 writer 互斥, P1 静默)。
2. **ENA 字段名亟需统一**: 三套形态(`ena_bw_in_exceeded` / `bw_in_allowance_exceeded` ×2) 必须收敛到一套, 否则新旧 writer + 各 reader 随机断链。这是比 disk 改名更紧迫的真 bug。
3. **disk 改名落点修正(复核-J)**: get_disk_field_prefix 三 provider 返回值(aws_standard/baseline/standard)是第二 SSOT, 与 csv_schema_registry 矛盾, 是 iostat_collector fallback 断链 BUG 的根因, 改名必须一并处理。

---

# ════════ 第五轮: ENA 断链触发条件钉死 — 发现 1 从 P1 降级为潜伏债 + 新 Y+ aws_ena 是死代码 (2026-05-31) ════════

> 触发: 用户选"继续查生产实际跑哪个 writer, 钉死发现 1 严重程度"。
> 本轮亲读: monitoring_coordinator.sh L35-36/140-164/231/421 + unified_monitor.sh L1936-1944(ENA header 条件)
>   + config/user_config.sh:35 + config/config_loader.sh:150-185(ENA_MONITOR_ENABLED 决策) + 确认 reader df 源(performance_csv=unified)。

## 复核-K 🟢 决定性事实: 新旧 network writer 互斥(非并存), 由 ENA_MONITOR_ENABLED 二选一 (VERIFIED E1)
- monitoring_coordinator.sh **同时登记** 老("ena_network"=ena_network_monitor.sh L35)+新("network"=network_monitor.sh L36), monitors_to_start 含两者(L231), **但启动时互斥**:
  - L156-159 "network"(新Y+): `if ENA_MONITOR_ENABLED==true: skip Y+ (avoid duplicate); return 0`
  - L141-151 "ena_network"(老): `if ENA_MONITOR_ENABLED==true: 启动; else skip`
  → **永远只跑一个**。
- unified_monitor.sh 第三处 ENA: L1938-1943 `if ENA_MONITOR_ENABLED==true: 拼 build_ena_header(裸全称③)入主CSV; else: 不写 ENA 段`。

## 复核-L 🟢 ENA_MONITOR_ENABLED 由部署平台自动决定 → 真值表钉死触发条件 (VERIFIED E1)
config_loader.sh L150-164(auto)/L167-185(手动): aws→true(L152) / gcp→false(L156) / other→false(L161)。user_config.sh:35 默认 true(被 auto 覆盖)。
| 部署(auto) | ENA_MONITOR_ENABLED | 跑的 writer | ENA 列名 | ENAFieldAccessor(认裸全称③) | ENA 分析 |
|---|---|---|---|---|---|
| aws | true | 老 ena_network + unified ENA 段 | 裸全称 `bw_in_allowance_exceeded` | ✅命中 | ✅正常 |
| gcp | false | 新 Y+(gvnic/virtio) | 无 ENA 列(GCP 无 ENA) | 空(合理) | ✅合理 |
| other | false | 新 Y+(other_none) | 无平台字段 | 空 | ✅合理 |
- reader df 源确认: report_generator `__init__(performance_csv)`(L1181) = unified CSV; ENA 分析 _analyze_ena_limitations(L3155)/_generate_ena_data_table(L3207) 消费的 df 来自此 unified CSV → AWS 下 unified 写裸全称(③) → ENAFieldAccessor 命中 ✅。

## ★第五轮结论: 发现 1 降级修正 (VERIFIED, 推翻第四轮"active P1")★
1. **正常自动部署路径下, 发现 1 不触发**: AWS auto→ENA_MONITOR_ENABLED=true→跑老 writer 写裸全称→ENAFieldAccessor 命中→ENA 分析正常。GCP/other auto→false→无 ENA 字段, 本就该空(合理)。
2. **新 Y+ aws_ena.sh(写 `ena_bw_in_exceeded` ①)是实质死代码**: 只要 auto 检测出 AWS, ENA_MONITOR_ENABLED=true → coordinator L156 跳过新 Y+ network 任务 → aws_ena.sh 永不被启动。它的 `ena_` 前缀命名(①)在生产路径上不产生任何 CSV。
3. **触发条件(潜伏债, 非 active)**: 仅当**手动**把 AWS 机器 DEPLOYMENT_PLATFORM/ENA_MONITOR_ENABLED 设 false(config_loader L167+ 手动分支) → 跑新 Y+ aws_ena 写 `ena_` 前缀 → ENAFieldAccessor 认裸全称全 miss → 有 ENA 数据却静默不分析。
4. **定性**: 发现 1 从"active P1 静默 bug"**降级为潜伏债(latent)**。device_manager 旁路债(复核-E)同理(走 unified CSV 裸全称, AWS 下其实能 fallback 命中或部分命中, 非 active 断链)。
5. **真正该治理的收敛点(若要根治潜伏债)**: ENA 字段三套命名(①`ena_bw_in_exceeded` / ②③裸全称)统一 + 决定新 Y+ aws_ena.sh 是删(死代码)还是让 ENAFieldAccessor 兼容其 `ena_` 前缀命名。优先级低于 disk 改名(disk 是 active 需求, ENA 是潜伏债)。

---

# ════════ 第六轮(收尾): 复核-J 钉死 — disk provider getter fallback 是潜伏债非 active (2026-05-31) ════════

> 触发: 用户选"钉死复核-J(disk getter fallback 生产是否触发), 与 ENA 对称收尾"。
> 本轮亲读: iostat_collector.sh L14-19(source 链)+L155-170(header 主/fallback) + unified_monitor.sh L203-204(source iostat) + 全仓 csv_schema_registry.sh source 点。

## 复核-M 🟢 决定性: iostat_collector 无条件硬 source registry → fallback 永不在生产触发 (VERIFIED E1)
- **iostat_collector.sh:16** `source ".../config/csv_schema_registry.sh"` — **无 `2>/dev/null||true`, 硬 source**(对比 L19 unified_logger 带容错)。
- source 链: unified_monitor.sh:204 `source iostat_collector.sh` → iostat_collector.sh:16 硬 source registry → 进 generate_device_header 时 L159 `declare -F csv_registry_disk_header` **必为真** → 走主路径 L160(registry, 写 standard 三云统一)。
- **fallback L162-167(用 get_disk_field_prefix 写 aws_standard/baseline)在生产路径永不触发** — registry 总被 iostat_collector 自己 source 进来。fallback 仅"单独跑函数且未 source registry"的非生产场景可能走到。
- 全仓 6 处 source csv_schema_registry.sh(framework_data_quality_checker/ebs_bottleneck_detector/master_qps_executor/bottleneck_detector/iostat_collector + 它自身), reader/writer 关键路径都 source 了 → registry 主路径全程生效。

## ★复核-J 最终判定(与第五轮 ENA 对称)★
- disk provider getter(aws_standard/baseline/standard) 与 registry(standard) 矛盾是**事实**(两 SSOT 不同答案), 但 getter 路径(iostat_collector fallback L165)是**潜伏债(latent), 非 active**: 生产自动路径走 registry 主路径(写 standard), getter fallback 是防御死支。
- **结论修正(第一轮/第四轮曾标此为"真 BUG/改名必须处理")**: 改名 standard→normalized 的 **active 落点仍是 2 处 SSOT**(csv_schema_registry.py L30-32 + sh L65-67)。get_disk_field_prefix 三返回值是**潜伏债**, 改名时**建议一并改**(求干净, 避免未来 fallback 触发写旧名), 但**非 active 阻塞项** — 即便不改, 生产路径也走 registry 不会断链。

# ════════ ★★★ 六轮全分析最终汇总 (2026-05-31) ★★★ ════════
**用户原始需求**: disk/network 字段解耦改名时尽量不引入更多问题。

## A. disk 改名 standard→normalized (active 需求)
- **真实 active 落点 = 2 处 SSOT**: csv_schema_registry.py L30-32 + config/csv_schema_registry.sh L65-67(+清 L15 撒谎注释)。经 registry 的 reader 全自动随动。test_csv_registry_symmetry.sh 守护。
- **建议一并改的潜伏债**: get_disk_field_prefix 三 provider 返回值(aws_standard/baseline/standard, 复核-J/M, latent 不阻塞) + ebs_converter aws 旧别名 + device_manager aws_standard 业务别名键。
- **验收铁律**: 禁"跑通没报错"=通过, 必须验折算列非空非全0 + bash/py header 字节一致 + 折算图取折算列非 total。

## B. network 分流逻辑 (用户问的: 两云字段数量/语义不同应分流)
- **✅ 分流已实现且正确**(第三轮字节级验证): (CLOUD_PROVIDER,NIC_DRIVER) 二元组派发 → aws_ena(6字段)/gcp_gvnic(3)/gcp_virtio(5)/other_none(0), writer↔reader 三 variant 全字节对齐, 语义分流正确(AWS限速saturation_counter / GCP丢包drop_counter), 三层降级兜底完整。
- **network 物理前缀(ena_/gvnic_/virtio_)是真实驱动名, 非厂商烙印 → 不应中立化**(ADR-0001 保留 ena)。

## C. ENA 字段潜伏债 (非 active, 查 device_manager 旁路债时挖出)
- ENA 字段三套命名(①新Y+ `ena_bw_in_exceeded` / ②老writer ③配置层 裸全称) 不统一, 但**自动部署路径不触发**(AWS→老writer裸全称↔ENAFieldAccessor命中; GCP→无ENA合理)。
- **新 Y+ aws_ena.sh 是实质死代码**(AWS 下 ENA_MONITOR_ENABLED=true → coordinator 跳过新 Y+ network 任务)。
- 触发仅限手动误配 AWS 机器 ENA_MONITOR_ENABLED=false。优先级低于 disk。

## D. 全分析方法论 (六轮共读文件)
writer(unified_monitor/iostat_collector/ebs_converter) + disk registry(py+sh) + reader(ebs_chart/device_manager/report_generator/advanced/chart_style/perf_viz + analysis 9文件) + network 全链(cloud_provider/network_monitor/network_unified_entry/interface/aws_ena/gcp_gvnic/gcp_virtio/other_none/network_field_registry/network_analyzer) + ENA(ena_field_accessor/ena_network_monitor) + 配置(system_config/config_loader/user_config/providers×3) + 调度(monitoring_coordinator)。
**前几轮误判更正**: ①network 非"不相关"(分流已实现且正确, 前两轮漏读派发层) ②ENA 断链非 active P1(降级潜伏债) ③disk getter fallback 非 active 阻塞(潜伏债)。每条均 token-level read_file 亲读 + E1 实证。

---

# ════════ ★★★ 第七轮: 完整性 grep 修正 — 六轮"active落点=2"是 UNDER-COUNT (2026-05-31) ★★★ ════════

> 触发: 用户要求"基于 skill 用 token-level 批判性再核实是否有漏判/误判, 以代码为事实, 扩大调用链范围"。
> 方法纪律(skill: active-vs-latent-defect-triage + token-level-careful-edit): 禁 delegate, 只 read_file 亲读;
>   签字前必跑【老 token 全形式完整性 grep】(六轮 curated 精读沿数据路径走, 系统性漏掉 off-path 的字面量字符串)。
> 完整性 grep: aws_standard(42) + baseline_iops(12) + baseline_throughput(12) + _standard_iops(23) + _standard_throughput(13)。

## ★最重要修正: 六轮"active落点=2 SSOT"是 UNDER-COUNT★
六轮 curated 精读沿 writer→CSV→reader→chart 数据路径走, **系统性漏掉了 off-path 的字面量字符串**(死输出键 / 產出文件名 / i18n 翻译键 / CI 守护正则)。这些**不经 registry 自动随动**, 携带旧 token 作为字面量。一次 `grep aws_standard` 全找出, 六轮读数据路径一个都碰不到。

## ★★ baseline 多义词消歧 (Rule 0, 最危险 — 当初若 blanket replace 会改坏两类) ★★
`baseline` 在本仓有 **4 个正交语义**, 必须分簇处理, 绝不可统一替换 (E1 each):
| # | 语义簇 | E1 落点 | ADR-0002 层 | 改名处置 |
|---|---|---|---|---|
| 1 | disk 折算前缀(GCP 历史) standard/baseline→normalized | csv_schema_registry.py L30-32 DISK_FIELD_PREFIX value | 层2 normalized | ✅已改(只动字典value, 没碰下面三类) |
| 2 | 卷额定能力配置变量 `*_baseline_iops/throughput` | device_manager.py L317/336(getenv DATA_VOL_MAX_IOPS) + L347-350 + ebs_chart L67/72 消费→provisioned | **层3 provisioned** | ⛔本次不动(独立层3治理) |
| 3 | IO size 换算基准块大小 `get_baseline_throughput_kib` | providers aws=128/gcp=256/other=0 + cloud_provider.sh:110 | **层5 baseline_io_kib** | ⛔ADR-0002 明确保留 |
| 4 | (注释中描述 GCP 物理列前缀曾叫 baseline) | 多处注释 claims | — | 注释清理 |
- **关键**: 当初改名只动了 DISK_FIELD_PREFIX 字典的 value(语义1), 没碰语义2/3 → 没改坏。若早期 blanket `sed baseline→normalized` 会把层3配置变量+层5基准块大小全毁。这正是 skill Rule 0 警告的多义词陷阱, 此处侥幸避开。

## 第七轮完整性 grep 逐 hit 分类 (每类标 active/latent + 处置)
**A. SSOT 核心 (auto-propagate, 已改)**
- csv_schema_registry.py L30-32 DISK_FIELD_PREFIX → normalized ✅(已落地, 对称测试 5/5 绿)
- csv_schema_registry.sh L65-67 → normalized ✅

**B. provider getter + iostat fallback (潜伏债, 已改)**
- providers×3 get_disk_field_prefix → normalized ✅; iostat_collector.sh fallback L164-165 → normalized ✅
- (复核-J/M: 生产硬 source registry, fallback 永不触发, latent)

**C. device_manager 业务别名键 (latent 内部自用无外部消费, 已改)**
- L46-47/62-63/431-432/506-507/581/589 aws_standard→normalized ✅(8处, 已证 grep 无外部消费方)

**D. ★六轮漏掉的 off-path 字面量 (未改, 本次新登记)★**
- D1 unit_converter.py L253/263 `aws_standard_iops` 折算输出键 → **DEAD KEY**(全仓零消费方, 真折算实现是 ebs_converter.sh; unit_converter 是平行未接线 Python 实现)。**latent/dead-code**。⚠️首见时曾误报"最严重 active 折算公式", grep 消费方=0 后降为死键(active-vs-latent skill Pitfall 6 实证案例)。
- D2 ebs_chart_generator.py L36/245/1015 產出 PNG 文件名 `ebs_aws_standard_comparison.png` + 方法名 `generate_ebs_aws_standard_comparison()` → **active 產出**(L245 主图表列表无条件调用), 但图表内容已随动(L159/161 经 _resolve_disk_field→registry→normalized)。仅【名字】带烙印。对外交付物, 用户偏好须中性化。
- D3 report_generator.py L570-571/1129-1130(en+zh i18n)+L4093-4095(gallery 引用)`chart_ebs_aws_standard_comparison` → **active**(验收铁律#7 png gallery 翻译键)。配套 D2 一起改。
- D4 ci/check_csv_registry_bypass.sh L24 VIOLATION_PATTERN 硬编码旧物理名 `aws_standard_iops|...` → **active 守护逻辑**。改名后此 CI 门抓旧名失效, 新名 normalized_iops 成不被守护盲区。须 lockstep 更新(注意 normalized 通用词误报风险, 用带 device 段形态 `(data|accounts)_.*_normalized_(iops|throughput)`)。

**E. calc double-source (独立 bug, 非改名引入, 改名安全)**
- ebs_chart_generator.py L114 `__init__` 无条件调 `_recalculate_disk_standard_metrics`(L153-176): 用自己公式覆写 writer 已算的折算列。E1 读函数体: 取列全经 `_resolve_disk_field`(L159/161/183/185)→registry→已随动 normalized, **不硬编码旧列名** → 改名不断链。计算双源(公式与 ebs_converter 不一致)是独立 bug, 与改名正交。

**F. 注释 claims (撒谎注释, 待清, 非执行路径)**
- csv_schema_registry.py L11/L22/L66(L22"方案甲统一standard"与代码 normalized 矛盾) + L127 fallback 默认值仍 "standard"
- ebs_bottleneck_detector.sh L163/231 + bottleneck_detector.sh L906 + ebs_chart L136-142/213 + report_generator L1644/1794/1812 + device_manager L17/30/174-176 注释描述旧物理名

## ★第七轮最终修正结论★
1. **改名 active 落点 ≠ 2, 而是: SSOT核心2(A) + 对外烙印 active 3类(D2/D3/D4) = 须改的 active 共 5 类落点**。六轮"=2"只数了 auto-propagate 的 SSOT, 漏了 off-path 不随动的 active 字面量(產出文件名/i18n/CI 门)。
2. **latent/已改: B(getter) + C(device_manager别名) + D1(unit_converter死键)**。
3. **独立 bug 非改名阻塞: E(calc double-source)**。
4. **明确不动(超本次层2范围): baseline 语义2(层3 provisioned)+ 语义3(层5 baseline_io_kib)** — 单独立项做层3治理。
5. **network 线: 维持六轮结论不变**(独立第二 SSOT network_field_registry, 分流正确, 物理驱动名不中立化), 第七轮 grep 未触及 network 字段(完整性 grep 的 token 是 disk 物理名), network 无新增改动。

## 当前落地执行状态 (截至第七轮)
- ✅ 已落地未 commit: A(registry py+sh) + B(getter×3+iostat fallback) + C(device_manager 8处别名键)
- ⬜ 待执行(用户定调范围后): D2/D3(ebs_chart 文件名+方法名 + report i18n, 一起改) + D4(CI门正则 lockstep) + F(注释清理含 registry L22/L127) + D1(unit_converter 死键顺带清)
- ⬜ 单独立项: baseline 层3 provisioned 命名治理(语义2)
- ⬜ 验收: L3 e2e(折算列非空非全0 + 折算图取折算列 + device_comparison 取 total + png gallery 翻译键配齐)
- 测试现状: test_csv_registry_symmetry.sh 5/5 绿(守护 A 的 py↔sh 对称)
