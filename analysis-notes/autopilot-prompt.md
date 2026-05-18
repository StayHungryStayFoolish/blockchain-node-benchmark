# Autopilot Prompt — blockchain-node-benchmark 代码分析自动模式（R19）

你正在执行 blockchain-node-benchmark 仓库的代码分析自动模式（R19）。这是 cron 触发的独立子会话，无前文对话上下文。你的工作目录已是 `/usr/local/google/home/lelandgong/blockchain-node-benchmark`。

# 第一动作（强制）：检查自动模式状态

```bash
tail -60 analysis-notes/01-progress.md | grep -E "AUTO MODE|STATUS:|COMPLETED|NEEDS_USER|PAUSED"
```

如果看到 `STATUS: COMPLETED` → 立即结束本次响应，输出 "Auto mode already completed, exiting." 不做任何其他事。
如果看到 `STATUS: NEEDS_USER` 或 `STATUS: PAUSED` → 立即结束本次响应，输出 "Auto mode paused, awaiting user. Exiting."
如果没看到 `AUTO MODE ACTIVATED` 锚点 → 立即结束，输出 "Auto mode not activated, exiting."
否则继续。

# 第二动作（强制）：走 R-1 5 Gate

按 analysis-notes/00-RULES.md L7-114 严格执行：

- **Gate 1**: read_file analysis-notes/00-RULES.md（limit=2000 一次读完）。输出 `Gate 1 ✅ rules re-read, total_lines: <N>`
- **Gate 2**: read_file analysis-notes/01-progress.md（完整，limit=2000）。输出 `Gate 2 ✅ progress loaded, last_round: R<X>, status: <CLOSED/OPEN>`
- **Gate 3**: 输出 `Gate 3 ✅ no summary (fresh cronjob context)`
- **Gate 4**: 从 progress.md 中查找最后一个完结的 Round 是否齐 4 件套（R10 自检 / R16 5 处自抽查 / R17.5 find 盘点 / R13 5 问）。输出 `Gate 4 ✅ Round <X> closed properly` 或 `Gate 4 ❌ BLOCKED: Round <X> missing <项>`（如 BLOCKED 必须先补做关闭协议）
- **Gate 5**: patch progress.md 追加 "Round N continued <UTC>" 行（如果是 Round 内推进）或 "Round N started <UTC>" 行（如果开新 Round）。输出 `Gate 5 ✅`

# 第三动作：推进业务（B+ 路线）

## ⚠️ 重读优先级（2026-05-18 用户裁决 方案 B）

**如果 COVERAGE.md 显示以下 5 文件状态为 `⏸ PENDING (R16 ❌ voided)`，必须先重读这 5 文件，然后才进入正常 R5 close 协议：**

1. utils/unified_logger.py (365 行 1 段) — R5.4 重读
2. utils/ena_field_accessor.py (166 行 1 段) ⭐ GCP P0 — R5.5 重读
3. utils/csv_data_processor.py (257 行 1 段) — R5.6 重读
4. utils/unit_converter.py (447 行 1 段) ⭐ GCP P1 — R5.7 重读（第四节是上次违规处，**必须用原文 L1-100 写表格**）
5. utils/__init__.py (1 行 1 段) — R5.8 重读

**重读规则强化**：
- 每个文件的每一节表格都必须包含原文 `L<n>-<m>` 行号
- 涉及具体常量/字段/函数名，必须 grep 原文确认存在后再写
- 写完每个文件立即做 5/5 自抽查（笔记 vs 原文逐行比对），任一 ❌ → 立即停止并 STATUS: NEEDS_USER
- 旧版作废笔记可参考但不可直接复制：`analysis-notes/file-notes/_voided/round-05-tick1/<name>.md`

**重读完成后**：
- patch COVERAGE.md 把 5 行从 `⏸ PENDING (R16 ❌ voided)` 改回 `✅ FULL`
- 总览数字：12 FULL → 17 FULL / 18.7% → 24.3%
- R5 行：3/8 → 8/8 / 21.8% → 100%
- 然后才能走 R5 close 协议（R10/R16/R17/R17.5/R13）

---

## 正常推进顺序（重读完成后）

按 progress.md 末尾的 NEXT 字段执行。优先顺序：

1. **R5.4-5.7**: utils/ 剩余 .py 文件
   - 5.4 utils/unified_logger.py (365 行) ⭐ AWS env 检测
   - 5.5 utils/ena_field_accessor.py (165 行) ⭐ GCP P0 AWS ENA
   - 5.6 utils/csv_data_processor.py (257 行)
   - 5.7 utils/unit_converter.py (447 行) ⭐ GCP P1 aws_standard_gbps
2. **R5 close**（5 重协议）
3. **R4.3-4.7**: monitoring/ 剩余 .sh 文件
   - 4.3 ena_network_monitor.sh (266 行)
   - 4.4 iostat_collector.sh (239 行)
   - 4.5 monitoring_coordinator.sh (605 行) — 大文件，需 2 段读
   - 4.6 unified_event_manager.sh (277 行)
   - 4.7 unified_monitor.sh (2802 行) — 超大文件，**必须按 450 行分段**：L1-450 / L451-900 / L901-1350 / L1351-1800 / L1801-2250 / L2251-2702 + L2703-2802 共 7 段
4. **R4 close**
5. **R6**: tools/ 6 文件
   - 6.1 benchmark_archiver.sh (689) — 2 段
   - 6.2 ebs_analyzer.sh (161)
   - 6.3 ebs_bottleneck_detector.sh (678) — 2 段
   - 6.4 framework_data_quality_checker.sh (701) — 2 段
   - 6.5 target_generator.sh (382)
   - 6.6 fetch_active_accounts.py (841) ⭐ 8 链对称 — 2 段
6. **R6 close**
7. **R7**: analysis/ 4 .py
   - 7.1 comprehensive_analysis.py (944) — 3 段
   - 7.2 cpu_ebs_correlation_analyzer.py (612) — 2 段
   - 7.3 qps_analyzer.py (1220) — 3 段
   - 7.4 rpc_deep_analyzer.py (549) — 2 段
8. **R7 close**
9. **R8**: visualization/ 6 .py（最重）
   - 8.1 chart_style_config.py (714) — 2 段
   - 8.2 device_manager.py (510) — 2 段
   - 8.3 ebs_chart_generator.py (1297) ⭐ ebs_aws_* — 3 段
   - 8.4 advanced_chart_generator.py
   - 8.5 performance_visualizer.py
   - 8.6 report_generator.py (4752) ⭐ aws_ebs_* — **必须按 450 行分段** = 11 段
10. **R8 close → 写早起报告 → STATUS: COMPLETED**

## 每个文件的标准流程（约 10-15 工具调用）

1. **read_file** 业务代码（全文，limit=2000；如果文件 >450 行**必须分段读**，每段 ≤450 行符合 R7）
2. **execute_code** 跑 grep 验证调用链：
   - source / import 入站方
   - 函数调用次数（每个公开函数）
   - AWS / GCP / azure 字面密度
   - 同名函数检查 `^funcname()` 全仓
3. **write_file** analysis-notes/file-notes/<filename>.md，**必须按 R8 十节模板（R20.7 后新版）**：
   - 第 1-5 节：原四要素 + 阅读状态（同旧版）
   - **第 6 节 GCP 兼容性分析（强制 10 子节，缺一即作废）**：
     - 6.1 AWS 字面密度（数字必须 == `grep -cE "AWS|aws|EBS|ebs|ENA|ena_|aws_ebs|ebs_aws|nitro" <file>` 实跑结果）
     - 6.2 GCP 阻塞点分级清单（表格 # / file:line / 类型 / P0-P3 / 描述 / 改造方案）
     - 6.3 CLOUD_PROVIDER 切换点（行号 + 切换内容 + ≤20 行示例）
     - 6.4 GCP 等价物映射表
     - 6.5 改造工作量预估
     - 6.6 命名中立化清单（旧名/新名/别名?/影响范围）
     - **6.7 数据字段产出**（R20.7 ⭐）：本文件写的 aws_*/ena_*/ebs_aws_* 字段（表格 # / 字段名 / 行号 / 写入载体 / 语义 / 中立等价名 / 双写过渡?）
     - **6.8 数据字段消费**（R20.7 ⭐）：本文件读的 aws_*/ena_*/ebs_aws_* 字段（表格 # / 字段名 / 行号 / 读取载体 / 上游写入方 / 改名后 KeyError 风险）
     - **6.9 输出文件名/标题 AWS 字面**（R20.7 ⭐）：图表/报告/log 文件名模板（表格 # / 模板 / 行号 / 类型 / 渲染示例 / platform-aware 方案）
     - **6.10 字段改名安全性评估**（R20.7 ⭐）：下游受影响清单（grep 实证）+ 双写过渡方案 + 归一化层位置 + 风险等级 🔴/🟠/🟢
   - 其他原有内容（R12 标签 / Bug / 死代码 / GAP）仍写入对应章节
4. **🔴 强制同步 GCP-TRACKER**（R20.2 + R20.7.2）：写完 file-notes 立即 patch `analysis-notes/02-GCP-MIGRATION-TRACKER.md`：
   - **第一-六章**：阻塞点 / 等价映射 / 命名 / 切换点 / 新增文件 / 工作量
   - **第十章**（R20.7 新增）：
     - 10.1 全局字段索引 ← append 本文件 6.7 节
     - 10.2 风险评分 ← 按本文件 6.10 风险等级累加
     - 10.3 输出文件命名清单 ← append 本文件 6.9 节
     - 10.4 双写过渡期计划 ← 累加本文件 6.7 中"双写过渡=✅"的字段
   - 总览顶部 重算 P0/P1/P2/P3 计数 + 已分析文件数 + **R20.7 5 个新指标**
   - **不更新 TRACKER 任一章 = 本笔记不算 FULL，COVERAGE.md 退回 PARTIAL**
5. **patch** progress.md 追加完成记录（R5.X / R4.X / R6.X / R7.X / R8.X 章节）
6. **🔴 强制 patch** `analysis-notes/00-COVERAGE.md`：
   - 把对应行的 「已读」字段从 0 改成实际读到的行数
   - 「状态」⏸ PENDING → ✅ FULL（如果全读完）或 🟡 PARTIAL N/M（如果分段读到一半）
   - 「file-notes」`-` 改成 `[name.md](file-notes/name.md)`
   - 重新计算总览 4 个数字（FULL/PARTIAL/PENDING/覆盖率）
   - **不更新 COVERAGE.md = 本文件未完成，下次 tick 会重读**
   - 分段读取时：每读完 1 段就更新一次（状态为 🟡 PARTIAL <累计>/<总>）

## Round close 时（5 重协议）

完成本 Round 所有文件后：

1. **R10**: 写 self-check 段落进 progress.md（本 Round 的总结：覆盖率 / Bug / 死代码 / GCP P0 / AWS 命名清单 / 同名冲突）
2. **R16**: 自挑 5 处原文抽查（自己挑自己判），写 `analysis-notes/round-NN-selfcheck.md`。任何 ❌ = 本 Round 作废重做
3. **R17**: 同名函数检查全仓
4. **R17.5**: 跑 `find ... -name "*.sh" -o -name "*.py"` 全仓盘点 diff 已读清单
5. **R13**: 回答 R13 5 问写进 progress.md

# 第四动作（强制）：写本次 AUTO RUN 报告

无论本次推进多少、成功失败，**响应结束前必须** patch progress.md 末尾追加：

```
═══════ AUTO RUN <UTC ISO 时间> ═══════
ITERATIONS USED: <估计 N>/90
FILES ADVANCED: <清单>
ROUNDS CLOSED: <清单>
STATUS: RUNNING / PAUSED / COMPLETED / NEEDS_USER
NEXT: <下一文件 / 下一 Round>
NOTES: <任何异常/GAP/阻塞原因>
═════════════════════════════════
```

# 强制暂停条件（写 STATUS: NEEDS_USER 后立即结束响应）

触发以下任一立即停：

- R0 凭记忆论断被自检发现
- R7 单段 >500 行
- R11 / R16 自抽查任一 ❌（笔记与原文矛盾）
- R17 / R17.5 漏文件
- **R20 file-notes 缺 6.1-6.6 任一子节**（GCP 维度漏写）
- **R20.2 写完 file-notes 漏 patch GCP-TRACKER**
- **R20.4 第 6 抽（GCP 维度）任一捏造（行号错 / 类型错 / 不存在）**
- **R20.7 file-notes 缺 6.7-6.10 任一子节**（数据契约维度漏写）
- **R20.7.2 写完 file-notes 漏 patch GCP-TRACKER 第十章**
- **R20.7.4 第 7 抽（数据契约维度）任一捏造（字段不存在 / 行号错 / 评分跳级）**
- [GAP-DOC-CONFLICT] 代码也读不出（如代码本身有 bug 或文档与代码完全无法对齐）
- 任何 patch / write_file 失败 3 次
- 接近 iteration 上限（>= 75/90）→ 主动留余地写报告

# 完成条件

所有 R4-R8 close 后：

1. **校验 00-COVERAGE.md**：FULL == 38 / PARTIAL == 0 / PENDING == 0 / 覆盖率 == 100%。若任一不满足 → 写 STATUS: NEEDS_USER 并列出差距
2. **校验 02-GCP-MIGRATION-TRACKER.md**（R20 + R20.7）：
   - 总览「已分析文件数」== 38
   - 阻塞点主表行数 == sum(每 file-notes 6.2 节行数)
   - 命名清单行数 == sum(每 file-notes 6.6 节行数)
   - **第十章 10.1 全局字段索引条目数 == 各 file-notes 6.7 字段去重后**（R20.7）
   - **第十章 10.3 输出文件命名总数 == 各 file-notes 6.9 行数之和**（R20.7）
   - 任一不吻合 → 写 STATUS: NEEDS_USER 列出差距
3. 写早起报告到 `analysis-notes/early-morning-report.md`，**必填 9 章节（R20.6 + R20.7.6）**：
   1. **GCP 改造矩阵**：从 TRACKER 提取 P0/P1/P2/P3 全清单 + 改造顺序图
   2. **AWS 命名中立化清单**：从 TRACKER 三 表汇总
   3. **CLOUD_PROVIDER 设计**：完整 config 层草案（可直接 cp 进 config/）
   4. **业务层 case 分支补丁**：按文件列清单，可逐个 apply
   5. **改造执行顺序**：按依赖图，从底向上的安全路径
   6. **GAP 清单**：所有 [SOURCE-ONLY] / [DEAD] / [NOT-FOUND] 标签
   7. **测试方案**：fake-target stack 模拟 GCP metadata + gVNIC 字段
   8. **数据契约迁移路径（R20.7）**：字段全局索引（写方→读方箭头图）+ 双写过渡期补丁（cp 即可用）+ 读时归一化层代码草案（utils/field_normalizer.py）
   9. **输出文件命名 platform-aware 改造清单（R20.7）**：按 file 分组的命名前缀改造补丁
4. progress.md 末尾写 `STATUS: COMPLETED`
5. 输出 "Auto mode COMPLETED. Coverage 100% (38/38 files / 29,109 lines). Total rounds closed: R4/R5/R6/R7/R8. GCP migration ready."

# 关键约束（不可违反）

- 不改业务代码（baseline e843571 保持）
- 不改规则文件 00-RULES.md（元工作需用户确认）
- 不删 analysis-notes 已有内容
- 每个论断必须有 file:line 证据（R0 零号规则）
- 中文写 file-notes（与已有 notes 保持一致）
- 大文件强制分段读，每段 ≤450 行（R7）

# 时间预算

- 单 tick 约 5-12 分钟（取决于推进文件大小）
- 系统 cron 每 15 分钟触发一次
- 如果本 tick 还没跑完且时间快到，主动写 AUTO RUN 报告 `STATUS: RUNNING` 并结束，下 tick 接力

现在开始执行。
