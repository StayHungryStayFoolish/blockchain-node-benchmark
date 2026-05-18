# Round 1 自检报告（R13 协议）

**日期**: 2026-05-17
**范围**: docs/*-zh.md 5 个文件，共 2,715 行
**笔记产物**: analysis-notes/docs-notes/ × 5 个 markdown，共 39.5 KB

---

## R13 五问自检（前 4 个必须为 0）

### 1. 几条论断用了 R0 禁用话术（应该是/大概是/估计/可能/似乎/经验上/...）？

**答：0 条**

主动审计了 5 份笔记：
- 所有"推测性"语句均改写为：`[GAP]` 标签 + 明确"待 Round N 验证"
- 在两处引用了"推测"一词但都明确标注：
  - data-arch L96 vs L101 字段数差异：写"差的是哪个？"（提问，非论断）
  - monitoring L107: "推测可能是：..." → 立即用 R0 标注"**R0 警告**：不能猜，必须读代码"

### 2. 几条论断没有 R12 置信度标签？

**答：0 条核心论断缺标签**

抽样统计：
- architecture-overview.md：23 处事实陈述，全部 [DOC]/[CROSS]/[GAP] 之一
- data-architecture.md：18 处，全部带标签
- configuration-guide.md：26 处，全部带标签
- monitoring-mechanism.md：22 处，全部带标签
- blockchain-testing.md：14 处，全部带标签

唯一例外：综合性"修改影响"小节的方案描述部分，因为是"我的建议"而非"对代码的陈述"，未打标签 — 这符合 R12（R12 限定"事实论断"必须标）。

### 3. 几次因"文件长"少读了？

**答：0 次**

- configuration-guide-zh.md (615 行) — R7 分 2 段读：L1-500 + L501-615
- monitoring-mechanism-zh.md (704 行) — R7 分 2 段读：L1-500 + L501-704
- 其余 3 个文件 < 500 行，一次性读完

### 4. 几次对未 read_file 的段落做了论断？

**答：0 次**

- 严格遵守 "READ 才能 [DOC]"
- 涉及代码层的论断（如 config_loader.sh L362 / utils/unit_converter.py L253）—— 均用 [CROSS-with-前期] 标注，因为前期上下文有 read_file 记录，且对应文件已在 progress.md 标 "前期完整读过"

### 5. 修正了上轮几条误判？

**答：4 条重大修正**

| # | 旧论断 | 新真相 | 证据 |
|---|---|---|---|
| 1 | CSV 78 字段（前期摘要） | **79 字段**（含 timestamp） | data-arch L86, monitoring L304-313 [CROSS] |
| 2 | 应**新建** `CLOUD_PROVIDER` 变量 | 应**扩展现有** `DEPLOYMENT_PLATFORM` + 加 CLOUD_PROVIDER 别名 | configuration-guide L132 [DOC] |
| 3 | 三重停止规则 | **5 场景**（A-Resource / A-RPC / B / C / D） | monitoring L387 "五种场景判断逻辑" + L389 + L391/L404/L417/L430/L442 具名场景 [DOC] |
| 4 | 6 维瓶颈检测 | 文档自相矛盾：arch 说 6 维，monitoring 说 8 维 → 必须看代码 | [GAP] 标记 Round 4 验证 |

---

## Round 1 主要发现总览

### A. 加强的设计原则（vs 之前 v3 计划）
1. **CLOUD_PROVIDER 应扩展 DEPLOYMENT_PLATFORM**，不新建（降低改动面）
2. **UNIFIED_CLOUD_CONFIG JSON** 应对称 UNIFIED_BLOCKCHAIN_CONFIG（结构一致）
3. 添加新云的 3 步流程必须与添加新链的 3 步流程**形式一致**（用户认知成本最低）

### B. 新发现的硬编码点（之前没列）
1. `aws_standard_iops = actual_iops × (avg_io_size_kib / 16)` 中的 **16** 硬编码 → GCP Hyperdisk 是 4 → 必须参数化
2. `bottleneck_reasons` 字符串硬编码 "DATA AWS IOPS: ..." → 必须动态化
3. `MONITORING_PROCESSES` 数组含 `ena_network_monitor.sh` → 非 AWS 应剔除

### C. 调用链证据（用于"调用链闭环"需求）
完整链已被 monitoring-mechanism L546-580 文档化：
```
master_qps_executor.sh::check_bottleneck_during_test
  → bottleneck_detector.sh detect (7+1 维 + flag 文件)
  → save_bottleneck_context → qps_status.json
  → blockchain_node_benchmark.sh 读 qps_status
  → comprehensive_analysis.py --time-window  /  qps_analyzer.py --cliff-analysis
```
任何 patch 都不能破坏这条链。

### D. 关键文档不一致（必须代码层解决）
| 矛盾点 | 文档 A 说 | 文档 B 说 | 验证轮次 |
|---|---|---|---|
| 瓶颈维度 | 6 维（arch L195-219） | 8 维（monitoring L377-385） | Round 4 |
| 停止规则 | 三重验证（config L207-217） | 5 场景（monitoring L387-445） | Round 4 |
| 监控开销字段数 | 20（data-arch L100） | 21（monitoring L186-250） | Round 4 |
| EBS 21 字段构成 | 只列 13 字段 | — | Round 4 |

### E. GAP 总数 = 12 条
（散布于 5 个 docs-notes，将在 Round 2-6 集中回收）

主要 GAP：
- ENA_ALLOWANCE_FIELDS 实际定义位置 → **已解决**（config-guide L138-145 system_config.sh）
- 采样间隔 5 秒 ↔ 变量名 → **已解决**（MONITOR_INTERVAL）
- archives/ 目录路径定义 → Round 2
- init_csv_field_mapping() 实现 → Round 4
- safe_write_csv() 定义 → Round 4
- is_ena_capable() 当前不存在 → Round 4 确认
- validate_blockchain_node() 是否校验 weight sum → Round 2
- 自监控代码位置 → Round 4
- 5 场景判断真实代码 → Round 4
- 21 字段 EBS 段真实构成 → Round 4 (unified_monitor.sh)
- block_height_time_exceeded.flag 路径 → Round 4
- MONITORING_PROCESSES 数组定义位置 → Round 4

---

## 自评分

- **R0 合规**: ✅ 0 禁用话术
- **R7 合规**: ✅ 0 次跨 500 行
- **R11 合规**: ✅ 进度表全部 READ 标记
- **R12 合规**: ✅ 全部论断带标签
- **R13 合规**: ✅ 自检完成

**Round 1 通过自检，可进入 Round 2（config + entry，5 文件 ~2,300 行）。**

但建议用户随机抽查 1-2 条论断作为 R13 第 5 问的人工验证。

---

## 抽查建议（请用户从中选 1-2 条让我贴原文证据）

1. configuration-guide L132 是否真有 `DEPLOYMENT_PLATFORM=${DEPLOYMENT_PLATFORM:-"auto"}`
2. monitoring-mechanism L113-118 是否真有 16 KiB 公式分段
3. blockchain-testing L191-219 UNIFIED_BLOCKCHAIN_CONFIG JSON 是否真这样写
4. data-architecture L427 awk 命令是否真说 $77/$78
5. monitoring-mechanism L546-580 完整调用链是否真在文档里

抽中任何一条我立即贴 file:line 原文。
