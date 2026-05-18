# 代码分析工作协议（Working Protocol）

> 本文件是约束我（Hermes Agent）在分析 blockchain-node-benchmark 仓库时必须遵守的规则。
> 每轮分析开始前重读一次。
> 任何违反在用户抽查时被发现 = 本轮作废重做。

---

# 🔴🔴🔴 R-1 — 启动闸门（凌驾 R0，必读第一段）

> 本节是 compaction 后的注意力锚点。
> 无论新会话 / resume / compaction 后醒来，
> **任何业务工具调用（read_file 业务代码 / write_file file-notes / patch 业务文件）之前，
> 必须按顺序完成 5 个 Gate**。
> 跳过任一 Gate = 当前 Round 作废 + 必须重做。

## 触发条件

以下任一情况发生时，R-1 强制激活：

- 新会话第一次响应
- /resume 之后第一次响应
- Compaction summary 出现后第一次响应
- 用户说"继续 / 下一轮 / 进入 R(N+1) / 开始 / 执行 / 可以开始分析了"等推进性指令
- 我自己提议进入下一文件 / 下一 Round

## 5 个 Gate（必须按顺序）

### [Gate 1] 重读规则
- **执行**：`read_file analysis-notes/00-RULES.md`（完整，limit=2000 一次读完）
- **输出**：一行 `Gate 1 ✅ rules re-read, total_lines: <N>`

### [Gate 2] 读取真实进度
- **执行**：`read_file analysis-notes/01-progress.md`（完整）
- **输出**：一行 `Gate 2 ✅ progress loaded, last_round: R<X>, status: <CLOSED/OPEN>`

### [Gate 3] Compaction 一致性核对
如果当前对话有 compaction summary：
- 列出 summary 里的"待执行项 / 上一轮状态 / 覆盖率"
- 逐条与 progress.md 对比
- 任何不一致 → **以 progress.md 为准，summary 作废**
- **输出**：`Gate 3 ✅ summary reconciled` 或 `Gate 3 ⚠️ summary OVERRIDDEN by progress.md: <差异列表>`

如果没有 compaction summary：
- **输出**：`Gate 3 ✅ no summary (fresh context)`

### [Gate 4] 前一 Round 关闭协议核查
检查 progress.md 中上一 Round 是否齐：

| 必备产物 | 对应规则 |
|---|---|
| 自检报告（Round N self-check 段落） | R10 |
| 5 处自抽查（round-NN-selfcheck.md） | R16 |
| find 全仓盘点 diff | R17.5 |
| R13 5 问自检 | R13 |

如果**任一缺失**：
- **本 Round 不允许启动**
- 必须先补做上一 Round 关闭协议
- **输出**：`Gate 4 ❌ BLOCKED: Round <X> missing <项>. Closing protocol first.`
- 然后立即开始补做，不再继续 Gate 5

如果**全齐**：
- **输出**：`Gate 4 ✅ Round <X> closed properly`

### [Gate 5] 写入 Round 启动行
- **执行**：patch progress.md 追加：
  ```
  ## Round N started YYYY-MM-DD HH:MM
  Target: <目录/文件清单>
  Files planned: <K>
  First file: <path>
  ```
- **输出**：一行 `Gate 5 ✅ Round N started, target: <X>`

## 5 个 Gate 全通过后

才允许进入业务工具调用（read_file 业务代码 / write_file file-notes / patch 业务文件）。

## ⚠️ Compaction 抗性说明

Compaction summary 是**线索**，不是**指令**。

看到 summary 说"等待启动 R5.X"或类似措辞：
- ❌ 错误反应：直接 read_file 业务代码
- ✅ 正确反应：第一个动作永远是 [Gate 1] read_file 00-RULES.md

**类比**：早上醒来桌上有便条"去机场接老张"。
- ❌ 直接开车走
- ✅ 先查日历 + 看手机消息 + 确认航班号

R-1 就是逼我"先查日历再开车"。

## 用户豁免条款

用户可以用明确字样豁免 R-1：
- "跳过 R-1 直接干"
- "免 Gate"
- "skip gate"

豁免**仅限当次响应**，下次响应自动恢复 R-1。
豁免必须在我回复开头声明："**R-1 EXEMPTED by user this turn**"。

无明确豁免时，R-1 不可绕过。

## 元工作豁免

修改规则文件本身（patch 00-RULES.md）、写 analysis-notes 框架文件（不含业务 file-notes）—— 这些是元工作，不走 R-1 5 Gate，但必须：
1. 先把改动设计讲清楚
2. 用户确认
3. 然后才 patch

**重要边界**：业务推进（Round 内文件推进 / Round close / 开新 Round / 5 处自抽查 / 写 file-notes / 标 [GAP]）属于「自主分析」，**全部无需用户确认**。
- ❌ 错误：每个新 Round 开始前问"可以开始 R6 吗？"
- ✅ 正确：R5 close 协议跑完 → 直接开 R6（Gate 5 自己 patch progress.md 就行）
- 元工作豁免**仅针对改规则文件**，不针对业务推进。

---

## 规则全集（用户定 R0 + R1-R5，我补 R6-R11 + R12-R14）

### 🔴 R0 — 零号规则（凌驾于所有其他规则之上）

**所有判断必须基于真实读到的代码逻辑，禁止任何形式的假设、猜想、推测。**

在如此复杂的框架内，任何假设都可能造成代码修改的灾难性后果。

**强制要求：**
- 任何关于"代码做了什么"的论断，必须能指向具体的 `file:line` 真实代码作为证据
- 任何关于"两个文件之间的调用关系"的论断，必须看到过双方真实的 `source` / `import` / `call` 语句
- 任何关于"字段顺序 / 函数签名 / 参数列表"的论断，必须 `read_file` 抓到上下文，不能凭命名或经验推断
- 任何关于"行为 / 副作用"的论断（"它会写 CSV"、"它会调 jq"），必须看到那段代码

**绝对禁止的话术（出现一次 = Round 作废）：**
- 🚫 "应该是 / 大概是 / 估计 / 可能 / 似乎 / 看起来像"
- 🚫 "按照通常的写法 / 一般来说 / 这种框架通常 / 经验上"
- 🚫 "因为函数名叫 xxx，所以它做 yyy"
- 🚫 "因为文件名叫 xxx_monitor，所以它监控 yyy"
- 🚫 "我没读但我推测..."
- 🚫 "基于上下文我相信..."（没有 file:line 证据时）

**正确做法：**
- ✅ "L127 真实代码是 `echo "$r_s,$w_s,..."`，21 字段顺序如下：..."
- ✅ "在 config_loader.sh L17 看到 `BLOCKCHAIN_NODE="${BLOCKCHAIN_NODE:-solana}"`"
- ✅ "在 unified_monitor.sh 全文 read 后未发现对 X 的调用，标记为 NOT-FOUND"

**遇到不确定时的唯一正确动作：**
读代码。不是猜，不是问用户，是**立刻 `read_file` 把那段代码抓到上下文里**。
如果代码里真的没有信息，写 `NOT-FOUND-IN-CODE` 并说明已检索的位置，**而不是用经验填空**。

**与其他规则的关系：**
- R0 是 **what**（什么是合法论断）
- R1-R11 是 **how**（怎么操作才能产生合法论断）
- R0 任何时候与其他规则冲突时，**以 R0 为准**
- 即使遵守了 R1-R11 的所有操作流程，只要有一处论断违反 R0，本 Round 仍然作废

---

### 🔴 R0.1 — 文档矛盾时的"具名优先"原则

当同一文档（或多份文档）内部出现表述矛盾时（如"4 种场景"vs"5 种场景"）：

**强制顺序**（不允许反向）：
1. **优先采信"有具名实体列举的"那一方**（列出 5 个有名字的场景 > 笼统说"4 种"）
2. **优先采信"明确章节标题/小节定义的"那一方**（如 L387 "**五种场景判断逻辑**"标题）> 散落正文里的口径数字
3. 仍无法裁决 → 标 `[GAP-DOC-CONFLICT]` 进 progress.md，**等代码裁决**

**绝对禁止：**
- 🚫 用"数得过来的数字"（4 种、6 维）去推翻"具名列举的实体"（A-Resource/A-RPC/B/C/D）
- 🚫 因为"上轮我已经写过 X"就反向修正主表述去迁就笔误（自我维护偏见）
- 🚫 在没读代码之前，单凭文档矛盾就改写笔记

**真实教训**（Round 1）：
我把 monitoring-mechanism-zh.md L387 "**五种场景**" 错误地反向"修正"为"4 场景"，理由是 L554/L586 写了"4 种" —— 这是典型的 R0.1 违反。

---

### 🔴 R15 — 文档优先 + 矛盾时先读代码（用户定）

**用户原话**："当前 doc 内的文档在大多数情况下都是正确的，如果你在分析时遇到文档描述错误，我建议你先读取代码逻辑进行确认。"

**强制要求：**
1. **默认信任 docs/*.md**：在没有反证之前，文档表述视为 **[DOC] 级证据**，等同于"已知事实"
2. **怀疑文档需要硬证据**：要声称"文档错了"，必须先 `read_file` 对应的代码并贴出 `file:line` 反证
3. **矛盾出现时的唯一动作**：立刻读代码 → 用 [CODE] 裁决，**不允许凭直觉/经验/上轮笔记**改写
4. **裁决后**：若代码确实与文档不符 → 在 file-notes 标 `[CODE-OVERRIDES-DOC]` + 同时记录文档原文位置，**不修改文档本身**

**与 R0.1 的差异：**
- R0.1 处理"**文档内部**自相矛盾"
- R15 处理"**文档 vs 代码**不一致"
- 两者都要求：**代码是最终裁决，但读代码之前不许下结论**

**典型流程：**
```
读到文档 A 说 X
    ↓
读到代码 B 似乎做了 Y (X ≠ Y)
    ↓
[禁止] 直接断言"文档错了"
[禁止] 直接断言"代码错了"
[必须] read_file 把 B 完整段落抓到上下文 + grep 相关消费者
    ↓
仍冲突 → 在 file-notes 标 [CODE-OVERRIDES-DOC] 或 [DOC-OVERRIDES-CODE]
        + 列出双方 file:line 原文 + 给出裁决理由
```

---

### 🔴 R17 — 每轮强制"未分析/错误内容"自检（用户定）

**用户原话**：每一轮都需要自检，没有分析完整的、错误的内容都需要读取实际代码逻辑更新。

**强制要求**（每轮结束 + 下一轮开始前 必做两道工序）：

1. **完整性自检**（每个 file-notes 文件）：
   - **真实阅读覆盖率** = 已读行数 / 总行数 — 任何 <100% 必须列入下一轮第一优先级补读
   - "已 source 但是否实际调用"必须 grep 全仓验证 — 不能凭"source = 使用"
   - 对每个声称的下游消费者/调用者，必须有 grep 证据（不只是 source 关系）
   - 同名函数检查：所有声称的函数必须 grep `^funcname()` 全仓，确认是否被覆盖

2. **错误内容修正**：
   - 任何被识别为"措辞不严谨/调用关系错误/语义错误"的笔记，必须**立即 read_file 源码并 patch 修正**
   - 修正后必须在 file-notes 文件顶部 `## R17 修正记录` 段落显式记录：
     ```
     - YYYY-MM-DD: 原表述 "X" → 修正为 "Y"（基于 file:line 真实代码）
     ```
   - **禁止**先标 GAP 留下轮 —— 当场能 grep / read_file 验证的必须当场做

3. **跨文件依赖图谱**：
   - 每轮结束必须更新 `call-chains/function-callmap.md`（全项目函数定义点 + 全部调用点）
   - 每轮结束必须更新 `call-chains/env-var-table.md`（关键 env var 的 define / read 位置）

**与 R16 的差异：**
- R16 = 抽 5 处随机原文比对，是**采样自检**
- R17 = 全量回看本轮每个论断完整性 + 错误必修，是**100% 普查**

**触发 R17 失败 = 本轮作废重做**，特别是以下两种典型失败：
- "声称 source X 但实际未调用 X 的任何函数"——必须 grep 全仓验证调用点数量后再下论断
- "声称读了文件 N 行但实际读了 < N 行"——必须用 wc -l vs 已读 offset+limit 累计验证

---

### R18 — 反"source = 使用"幻觉（用户隐含）

**问题模式**：bash `source` 语义是"加载文件到当前 shell"，但不等于"调用了其中函数"。
真实使用必须满足：
1. 有 `source path/to/file.sh`（加载）+
2. 有 `funcname args` 或 `$(funcname args)` 或 `funcname args |` 等调用语法

**强制要求**：
- 任何 file-notes 的"入口"段，必须区分两类来访者：
  - **真正调用我函数的**：列函数名 + caller file:line
  - **只 source 不调用的**：单独标 `[SOURCE-ONLY]`（可能是历史遗留或防御性加载）
- 同样，"出口"段的 "source 的文件" 与 "调用其函数" 也必须分开列

**真实教训**（Round 3）：
我在 master_qps_executor.sh.md 写 "common_functions.sh 被主入口 source"，暗示"被使用"。
实际 grep 发现：master 加载 common 后 **0 次调用** common 的 5 个函数。
真正调用者是 monitoring/block_height_monitor.sh（5 个调用点）。
此结论必须在 file-notes 中显式更正。

---

### 🔴 R17.5 — 每轮末必做的全仓盘点 sanity check（漏掉 utils/*.py 教训）

**问题模式**：R17 只对"当前轮已知文件"做完整性自检，但**没有触发对整个仓库文件清单的盘点**。
真实教训（Round 4.2 后被用户追问才发现）：
- utils/ 下 5 个 .py（unified_logger / csv_data_processor / ena_field_accessor / unit_converter / __init__）
- tools/ 下 1 个 .py（fetch_active_accounts.py）
- 这 6 个文件从未进入任何 Round 计划，连 GAP 都没立 — R17 完全没触发警报

**强制要求**（每个 Round 结束时执行，写入 `round-NN-selfcheck.md`）：

```bash
# Step 1: 全仓 .sh / .py 重新穷举
find . -name "*.sh" -not -path "./.git/*" -not -path "./analysis-notes/*" | sort > /tmp/all_sh.txt
find . -name "*.py" -not -path "./.git/*" -not -path "./analysis-notes/*" | sort > /tmp/all_py.txt

# Step 2: 累计 reading log 对比
grep -E "^- \[x\]" progress.md | awk '{print $3}' | sort > /tmp/read_files.txt
diff <(cat /tmp/all_sh.txt /tmp/all_py.txt | sort) /tmp/read_files.txt
```

**裁决标准**：
- 任何**未列入任何 Round 计划**的文件 → **当前轮作废**，必须先把它列入下一轮再 close
- 任何**列入但未读**的文件 → 必须在 progress.md 明确归属哪个 Round
- 每 **3 轮**做一次"递归 source/import 图谱扫描"：从主入口出发，递归列举所有 source/import 节点，检测有无未触达节点

**触发 R17.5 失败 = 当前 Round 作废**（与 R17 同等严厉）

**特殊情况**：发现新文件时必须问自己：
1. 它属于哪个 Round？
2. 它对最终交付物的影响等级？（AWS 强耦合 = 紧急 / 仅日志 = 低）
3. 是否影响已有 file-notes 的结论？（如果改变 [USED]/[SOURCE-ONLY] 标签 → 必须 patch 之前的 notes）

---

### R16 — 每 Round 强制自抽查（用户定）

**用户原话**："每一轮都开启抽查。"

**强制要求**（替代 R13 第 5 问的"自抽查"子项，正式独立成规则）：

每个 Round 结束时，**必须**做以下抽查，写入 `round-NN-selfcheck.md`：

1. **自挑 5 处原文抽查**：从本轮所有 file-notes / docs-notes 中**自己**随机挑 5 条论断（不让用户挑），重新 `read_file` 对应 `file:line`，逐字比对：
   - ✅ 完全一致 → 通过
   - ⚠️ 笔记口径不严但事实对 → 立即 `patch` 笔记
   - ❌ 笔记与原文矛盾 → **本轮作废重做**

2. **回看上轮"修正"**：本 Round 如果对上轮做过"修正"（改了之前笔记），必须重新读上轮被修正条目的原文 —— 防止"把对的改成错的"（Round 1 真实教训）

3. **检查所有 [GAP] / [DOC-CONFLICT] 标签**：列出本轮新增的所有 GAP，明确下一轮谁负责裁决

**抽查证据格式**：
```markdown
### 抽查 N：<论断摘要>
- 笔记位置：analysis-notes/file-notes/X.md L<行>
- 原文位置：<file>:<行>
- 原文摘抄：`...`
- 一致性：✅ / ⚠️ / ❌
- 处置：通过 / 已 patch / 本轮作废
```

**5/5 全通过才能开下一轮**。任何 ❌ = 本轮作废 + 必须分析为什么没在写的时候发现。

---

### R12 — 不确定性必须显式标注

在 file-notes / call-chains / 任何笔记里，对每个论断必须标注一个**置信度标签**：

| 标签 | 含义 | 使用条件 |
|---|---|---|
| `[CODE]` | 真实读到代码 | 必须能贴出 file:line 原文，可被抽查 |
| `[DOC]` | 真实读到 docs/ 文档 | 必须能贴出文档原文 |
| `[CROSS]` | 多处代码交叉印证 | 至少 2 个独立 file:line 来源 |
| `[NOT-FOUND]` | 检索过但未发现 | 必须列出已检索的文件清单 |
| `[GAP]` | 还没去读 | 明确的 TODO，必须进 progress.md |

**禁止裸论断**（既无证据也无标签）= R0 违反。

---

### R13 — 假设监测器（self-audit）

每轮结束写自检报告时，必须额外回答这 5 个问题：

1. **本轮里，我有几条论断使用了 R0 禁用话术？**（理论上必须是 0；若 > 0 列出每条 + 改写）
2. **本轮里，我有几条论断没有 [CODE]/[DOC]/[CROSS]/[NOT-FOUND] 标签？**（必须是 0）
3. **本轮里，我有几次因为"觉得文件长"而少读了？**（必须是 0）
4. **本轮里，我有几次对一个文件做了论断却没真正 read_file 过它的相关段落？**（必须是 0）
5. **本轮里，我修正了上轮的几条误判？**（≥ 0 都算正常；列出来）

任何一条 >0（第 5 条除外）= **本轮作废重做**，且必须分析为什么。

---

### R14 — 修改代码前的"最后一公里"复核

当 CODE_UPDATE_PLAN 进入实际改代码阶段之前，对每一个 Patch 必须再走一次：

```
□ Patch 影响的所有 file:line 是否都已经 [CODE] 级别证据？
□ Patch 修改的字段/函数是否已经穷尽 grep 全仓，确认没有遗漏的消费者？
□ 受 Patch 影响的所有调用链节点是否都已 [CODE]，且 call-chains/*.md 反映最新状态？
□ Patch 与现有框架模式（如 BLOCKCHAIN_NODE 的 case 分发）是否对称？不对称时有充分理由？
□ Patch 的回归验证步骤是否能真实可执行（fake stack 已就绪）？
```

5 项任一未通过 = **该 Patch 不允许执行**，必须回到分析阶段补齐证据。

---

## 规则全集（用户定 R1-R5，我补 R6-R11）

### R1 — 按文件夹枚举 + 分段读
- 进入每个目标文件夹时必须先列出**全部** `.sh` / `.py` 文件
- 超过 500 行的文件必须分段读取，不允许"读个头部就算"
- 禁止用 `search_files` 的 grep 命中替代 `read_file` 全文阅读

### R2 — 读时挂"修改影响"思维
- 每读一段（≤500 行）必须立即问自己：
  - 这段被哪些下游消费？
  - 我在 CODE_UPDATE_PLAN 里要改的字段/函数/env 在不在这里？
  - 改了之后这段会不会断？
- 答案写进 file-notes/<file>.md 的"修改影响"一节

### R3 — 维护调用链文件
- 每条主调用链单独一个文件，存 `call-chains/` 目录
- 每个节点必须有 `file:line` 精确引用，禁止"大概在 xxx 附近"
- 找不到就直说"未找到，疑似 grep 漏命中"，不允许猜

### R4 — Token-level 精读 + 批判性思考
- 不允许因"文件太长"跳过
- 每读完一段写笔记前要自问 3 件事：
  1. 这段做了什么？（机制）
  2. 它假设了什么？（前置条件）
  3. 它如果按当前 CODE_UPDATE_PLAN 改了会怎样？（影响）
- 三个问题任一答不出 → 重读该段

### R5 — 维护分析进度记录文件
- 文件：`analysis-notes/01-progress.md`
- 每读完一个文件**立即**更新对应行：状态 TODO → DONE + 行数 + 关键发现摘要
- 每轮结束在文件底部追加"Round N 自检报告"

### R6 — 先列清单后读取
- 每轮开始前先用 `search_files(target='files')` 列出目标目录全部文件
- 写进 progress.md 表格，状态全置 TODO
- 漏列 = 规则违反

### R7 — 分段大小硬上限 500 行
- 单次 `read_file` 的 `limit` 不得 > 500
- 长文件第一段读 1-500，第二段 501-1000，依次推进
- 每段读完必须在 `file-notes/<file>.md` 留段笔记

### R8 — 每个文件输出"六要素笔记"（R20 后扩为 6 节）
强制结构，写在 `file-notes/<file>.md`：

```markdown
# <file>  (<总行数> 行, 已读 <已读行数>/<总> 行)

## 1. 入口（谁调用我）
- `path:line` — 调用方式（source / function call / spawn）

## 2. 出口（我调用谁，写哪些文件）
- source 的文件：...
- 调用的函数：...
- 写入的文件 / CSV / log：...
- 读取的 env：...

## 3. 关键函数清单
| 函数名 | 行号 | 签名 | 做什么 | 读 env | 写文件 |
|---|---|---|---|---|---|
| ... | L... | ... | ... | ... | ... |

## 4. 修改影响（vs CODE_UPDATE_PLAN）
- Patch X 是否触及本文件？ ✅ / ⚠️ / ❌
- 如触及：原计划 vs 实际代码的差异

## 5. 阅读状态
- [x] L1-500    READ on YYYY-MM-DD HH:MM
- [ ] L501-1000 TODO

## 6. GCP 兼容性分析 ⭐ 强制（R20）
**完整模板见 R20.1。本节 6 个子节缺一不可：**

### 6.1 AWS 字面密度
- AWS 字面总数：N 处（必须等于 `grep -cE "AWS|aws|EBS|ebs|ENA|ena_|aws_ebs|ebs_aws|nitro" <file>` 结果）
- 每处行号 + 上下文 1 行

### 6.2 GCP 阻塞点分级清单（表格）
- 列：# / file:line / 类型 / 等级 P0-P3 / 描述 / 改造方案
- 空表也要保留表头 + 写 "本文件无 GCP 阻塞点 ✅"

### 6.3 CLOUD_PROVIDER 切换点
- 行号 + 切换内容 + ≤20 行示例

### 6.4 GCP 等价物映射（表格）
- 列：AWS 概念 / GCP 等价 / 关键差异

### 6.5 改造工作量预估
- 配置/业务行数 + 新增文件 + 删除死代码

### 6.6 命名中立化清单（表格）
- 列：旧名 / 新名 / 别名? / 影响范围

### 6.7 数据字段产出（本文件写哪些 AWS 命名字段）⭐ R20.7
- 列：# / 字段名 / 行号 / 写入载体（CSV/JSON/dict）/ 字段语义 / GCP 中立等价命名 / 双写过渡？
- 无产出写 "本文件无数据字段产出 ✅"

### 6.8 数据字段消费（本文件读哪些 AWS 命名字段）⭐ R20.7
- 列：# / 字段名 / 行号 / 读取载体 / 上游写入方文件 / 改名后影响（KeyError 风险）
- 无消费写 "本文件无数据字段消费 ✅"

### 6.9 输出文件名/标题 AWS 字面 ⭐ R20.7
- 列：# / 文件名标题模板 / 行号 / 输出类型 / 渲染示例 / platform-aware 改造方案
- 无输出写 "本文件无输出文件命名 ✅"

### 6.10 字段改名安全性评估 ⭐ R20.7
- 下游受影响清单（grep 实证）
- 双写过渡期方案
- 读时归一化层位置建议
- 风险等级（🔴 极高 5+ / 🟠 高 2-4 / 🟢 低 0-1）

**写完 6.1-6.10 后必须立即 patch `02-GCP-MIGRATION-TRACKER.md`**（R20.2 + R20.7.2 强制）：
- 6.1-6.6 → TRACKER 第一-六章
- 6.7-6.10 → TRACKER 第十章
**漏 patch TRACKER 任一章 = 本笔记不算 FULL**，COVERAGE.md 退回 PARTIAL。
```

### R9 — 调用链按"修改触点"组织
- 一条链一个 .md，文件名按链的功能命名（如 `csv-field-chain.md`）
- 每条链格式：
  ```
  [节点 N]
    File: <path>:<line>
    Function: <name>
    Reads: <input>
    Writes: <output>
    Next node: → [节点 N+1]
    Status: READ / GREPPED / UNREAD
  ```

### R10 — 每轮自检报告
每轮结束在 progress.md 追加：
```
## Round N self-check (YYYY-MM-DD HH:MM)
- Files planned: N
- Files actually READ (full): K
- Files only GREPPED: L
- Files still UNREAD: M
- Lines read this round: total
- Call chain nodes added: P
- Previous misjudgments corrected: Q  (列出来)
- New facts discovered: R              (列出来)
- Confidence delta on CODE_UPDATE_PLAN: ±%
```

### R11 — 论断措辞强制约束
笔记里每条论断必须标这三个之一：
- `READ` = 真的把那段代码通过 `read_file` 抓到上下文了
- `GREPPED` = 只通过 `search_files` 看到命中行，未读上下文
- `UNREAD` = 完全没看
- 禁用模糊词："已确认 / 已分析 / 应该是 / 大概 / 似乎"——必须替换为 READ / GREPPED / UNREAD + 证据

---

## 工作流（每轮的标准动作）

```
[1] 打开 00-RULES.md 重读一次
[2] 打开 01-progress.md 看上轮状态
[3] 决定本轮目标（哪个文件夹 / 哪条链）
[4] search_files(target='files') 列文件 → 写进 progress.md 表
[5] 逐文件 read_file（≤500 行/段）
    └─ 每段读完立即写 file-notes/<file>.md（四要素）
    └─ 立即更新 progress.md 对应行
    └─ 调用链节点立即写 call-chains/<chain>.md
[6] 本轮结束写自检报告到 progress.md
[7] 把修正的"之前误判"汇总到 CORRECTIONS.md
```

---

## 红线（任何一条触发 = 当前 Round 作废重做）

- 🚫 任何文件被声称"已分析"但没有对应的 file-notes/ 笔记
- 🚫 任何调用链节点没有 file:line 精确引用
- 🚫 任何 `read_file` 调用 limit > 500
- 🚫 任何论断没有 READ / GREPPED / UNREAD 标记
- 🚫 任何"差不多 / 应该是 / 大概"出现在笔记里
- 🚫 跳过任何文件夹（含 docs/、tests/、tools/）

---

## 用户抽查机制（鼓励触发）

用户可以随时挑一个我声称 READ 的文件，要求：
- 我说出 4 要素中任意一项
- 我说出某个 `function_name` 的真实行号 + 真实签名
- 我说出某段我标记 ✅ 的代码原文

答不出 = 我没真读 = 当前 Round 作废、重读。

---

## 🔴 R19 — 自动模式（Unattended Mode / 8 小时无人值守）

用户明确字样授权后激活："启动自动模式" / "8 小时跑完" / "cronjob 推进" / "你可以开始执行了"（在 8 小时跑完语境下）。

### 自主权限（无需用户确认）
- ✅ Round 内文件推进（R5.1 → 5.2 → ...）
- ✅ Round close 5 重协议（R10 + R16 + R17 + R17.5 + R13）
- ✅ 开新 Round（R5 close → R6 start）
- ✅ 5 处自抽查（R16 — 自己挑自己判，不让用户挑）
- ✅ 写 file-notes / docs-notes
- ✅ 标 [GAP] / [DOC-CONFLICT] 留下轮
- ✅ 文档矛盾用代码裁决（R0.1）
- ✅ AWS 命名中立化清单收集

### 子会话接力模型
- cronjob × 每 25 分钟触发 1 个 hermes 子会话
- 每个子会话独立走 R-1 5 Gate（cached 复用快）
- 子会话之间靠 `progress.md` 持久化接力
- 每次子会话结束必须写：
  ```
  ═══════ AUTO RUN <UTC 时间> ═══════
  ITERATIONS USED: <N>/90
  FILES ADVANCED: <清单>
  ROUNDS CLOSED: <清单>
  STATUS: RUNNING / PAUSED / COMPLETED / NEEDS_USER
  NEXT: <下一文件 / 下一 Round>
  ═════════════════════════════════
  ```

### 强制暂停条件（写 STATUS: NEEDS_USER + 停 cronjob）
触发以下任一 → 立即停 + 写"早起报告"等用户裁决：
- R0 凭记忆论断被自检发现
- R7 单段 >500 行红线触发
- R11 自检 5/5 任一 ❌（笔记与原文矛盾）
- R16 5 处自抽查任一 ❌
- R17 / R17.5 全仓盘点漏文件
- [GAP-DOC-CONFLICT] 无法用代码裁决（如代码本身有 bug）
- 任何 patch / write_file 失败
- 任何 syntax check 报错

### 完成条件
所有 Round close（R4-R8）后：
- 写"早起报告"汇总：覆盖率 / GCP P0 阻塞点清单 / AWS 命名中立化清单 / 所有 [GAP]
- STATUS: COMPLETED
- cronjob 自动停（检测到 COMPLETED 不再触发新子会话）

### 用户终止
明确字样："停自动模式" / "stop auto" → cronjob 立即停。

---

## 🔴 R20 — GCP 兼容性强制分析维度（用户核心需求）

**用户原话**："我之所以让你分析所有代码逻辑，就是因为要增加对 GCP 的全面兼容"

**核心目标**：分析完所有代码后，必须能拿出一份可执行的 GCP 改造手册，按其改造后零 bug、零调用链断裂。同一份代码两云通跑（AWS + GCP），用户只需在 `config/user_config.sh` 改 `CLOUD_PROVIDER=gcp` 即可切换。

**默认假设范围**（用户 2026-05-18 确认）：
- 支持云：AWS + GCP 双支持（不含 Azure）
- GCP 磁盘类型：pd-ssd / pd-balanced / pd-extreme / hyperdisk-extreme / local-ssd 全 5 种
- GCP 网络：gVNIC（替代 AWS ENA）+ Tier_1 networking
- GCP Metadata：metadata.google.internal + `Metadata-Flavor: Google` header

**激进改造路线**（用户 2026-05-18 二次确认，等级 A+A）：
- **字段命名（Q1 = A）**：全部 `aws_*/ena_*/ebs_aws_*` 中立化为 `network_*/nic_*/disk_standard_*`，使用"双写过渡期"策略：旧名 + 新名同时写 → 下游切到新名 → 删旧名
- **输出文件名（Q2 = A）**：图表/报告文件名 platform-aware（GCP 模式输出 `disk_gcp_*.png`，AWS 模式输出 `ebs_aws_*.png`），HTML/MD 报告标题内嵌平台标识
- **后果**：所有读 CSV/JSON 列名的代码必须改为按 platform-aware 读取层归一化；所有写文件名的代码必须按 `CLOUD_PROVIDER` case 分发命名前缀

### R20.1 — 每个 file-notes 必须含 GCP 强制章节

**grep 模式（强制实证）**：
```bash
# 完整 AWS/云原生字面捕获（不光是 AWS / aws）
grep -cE "AWS|aws|EBS|ebs|ENA|ena_|aws_ebs|ebs_aws|nitro|nitroSystem" <file>
```
2026-05-18 实证教训：internal_config.sh `grep -cE "AWS|aws"` 返回 0，但实际有 14 处 EBS 字面（变量名 BOTTLENECK_EBS_*）。必须捕获 EBS / ENA / nitro 等 AWS 专有术语，否则 P2/P3 命名阻塞点会全部漏掉。

在 R8 五节基础上追加：

```markdown
## 6. GCP 兼容性分析 ⭐ 强制（R20）

### 6.1 AWS 字面密度
- 本文件 AWS/aws 字面出现总数：N 处
- 列出每一处行号 + 上下文（如：L106 `AWS_METADATA_ENDPOINT/${AWS_METADATA_API_VERSION}/...`）

### 6.2 GCP 阻塞点分级清单
| # | 位置 file:line | 类型 | 等级 | 阻塞描述 | 改造方案 |
|---|----------------|------|------|----------|----------|
| 1 | foo.sh:L106 | URL | P0 | AWS metadata endpoint hardcode | 按 CLOUD_PROVIDER 分发 |
| 2 | ... | 算法/枚举/命名/常量 | P1/P2/P3 | ... | ... |

**等级定义**：
- **P0** = 不改 GCP 跑不起来 / 直接报错（必改）
- **P1** = 不改 GCP 跑得起来但数据错（必改）
- **P2** = 不改能跑数据对但命名误导用户（建议改）
- **P3** = 死代码 / 仅注释 AWS 字面（可清理）

### 6.3 CLOUD_PROVIDER 切换点
- 需要插入 `case "$CLOUD_PROVIDER"` 的位置：L<n>
- 切换什么：metadata 端点 / 磁盘类型枚举 / NIC 监控类型 / 文档 URL / IO baseline / ...
- 改造示例代码片段（≤20 行）

### 6.4 GCP 等价物映射
| AWS 概念 | GCP 等价 | 关键差异 |
|----------|----------|----------|
| io2 | pd-extreme / hyperdisk-extreme | baseline IO size: AWS 16 KiB vs GCP 4 KiB |
| gp3 | pd-balanced / pd-ssd | — |
| instance-store | local-ssd | — |
| ENA | gVNIC | 字段名完全不同 |
| AWS metadata IMDS | metadata.google.internal | 需 Metadata-Flavor: Google header |
| ...（每条至少补 1 行）| ... | ... |

### 6.5 改造工作量预估
- 配置层改动：N 行（在 config/ 加 case / 加变量）
- 业务代码改动：N 行（本文件需加 case 分支）
- 新增文件：<列出> 或 无
- 删除死代码：N 行（仅 AWS 命名残留）

### 6.6 命名中立化清单
| 旧名（AWS-only）| 新名（中立）| 别名保留？| 影响范围 |
|------------------|--------------|------------|----------|
| AWS_METADATA_ENDPOINT | METADATA_ENDPOINT | ✅（向后兼容）| N 处下游 |
| recommend_ebs_type | recommend_disk_type | ✅ | N 处调用 |
```

**6.1-6.6 全部必填**。即使本文件零 AWS 字面（如 internal_config.sh）也必须填，写：
- 6.1: "本文件 AWS 字面 0 处 ✅"
- 6.2: "本文件无 GCP 阻塞点 ✅"
- 6.3: "本文件无需 CLOUD_PROVIDER 切换 ✅"
- 6.4-6.6: "N/A — 本文件平台无关"

### R20.2 — GCP-MIGRATION-TRACKER 实时累加

每读完一个文件，必须 patch `analysis-notes/02-GCP-MIGRATION-TRACKER.md`：
- 把本文件 6.2 阻塞点全部 append 到 TRACKER 主表
- 把本文件 6.4 GCP 等价映射 merge 到 TRACKER 全局映射表
- 把本文件 6.6 命名中立化 append 到 TRACKER 命名表
- 更新 TRACKER 顶部总览（P0/P1/P2/P3 累计计数）

**漏 patch TRACKER = file-notes 不算 FULL**，COVERAGE.md 状态退回 PARTIAL。

### R20.3 — R10 自检追加 GCP 维度

R10 每轮 self-check 必须额外含：
- 本轮所有 file-notes 是否都有 6.1-6.6 六个子节？（缺一即作废重写）
- AWS 字面密度统计是否与 `grep -c "AWS_\|aws_" <file>` 一致？（不一致即作废）
- 本轮 P0/P1 阻塞点是否全部累加到 GCP-TRACKER？

### R20.4 — R16 抽查从 5 处扩到 6 处

第 6 抽必查 GCP 维度（**强制**）：
- 抽 file-notes 的 6.2 阻塞点表 1 行 → grep 原文 → 验证位置/类型/等级是否准确
- 任一捏造（行号错 / 类型错 / 不存在）→ 等同 R0 违规，本 Round 作废

### R20.5 — R17.5 全仓盘点追加 GCP 维度

每轮末 R17.5 sanity check 必须额外汇报：
- 本轮新增 P0 阻塞点数 + 累计 P0 总数
- 本轮新增 P1 阻塞点数 + 累计 P1 总数
- GCP-TRACKER 当前条目数 vs 本轮预期增量是否吻合

### R20.6 — 早起报告（R19 完成时）必须基于 GCP-TRACKER

`early-morning-report.md` 必填章节（缺一即未完成）：
1. **GCP 改造矩阵**：从 TRACKER 提取的 P0/P1/P2/P3 全清单 + 改造顺序图
2. **AWS 命名中立化清单**：从 TRACKER 6.6 表汇总
3. **CLOUD_PROVIDER 设计**：完整 config 层草案（可直接 cp 进 config/）
4. **业务层 case 分支补丁**：按文件列清单，可逐个 apply
5. **改造执行顺序**：按依赖图，从底向上的安全路径
6. **GAP 清单**：所有 [SOURCE-ONLY] / [DEAD] / [NOT-FOUND] 标签
7. **测试方案**：fake-target stack 模拟 GCP metadata + gVNIC 字段
8. **数据契约迁移路径（R20.7）**：字段全局索引 + 双写过渡期补丁 + 读时归一化层设计
9. **输出文件命名 platform-aware 改造清单（R20.7）**：所有图表/报告文件名按 CLOUD_PROVIDER 分发的位置

### R20.7 — 数据契约维度（CSV/JSON 字段名 + 输出文件名）⭐ 用户激进路线 A+A

**核心问题**：字段名是跨进程契约（L1 代码定义 → L2 CSV/JSON 落盘 → L3 下游读取 → L4 报告渲染）。任何一层改名而另一层没改 → 整条链立即断（KeyError / 空图 / 文件名错乱）。

**用户激进路线（Q1=A + Q2=A）要求**：
- 所有 `aws_*/ena_*/ebs_aws_*` 字段必须全部中立化为 `network_*/nic_*/disk_standard_*`
- 双写过渡期：旧名 + 新名同时落盘，下游切完后删旧名
- 输出文件名按 `CLOUD_PROVIDER` case 分发（`disk_gcp_*.png` vs `ebs_aws_*.png`）

#### R20.7.1 — 每个 file-notes 在第 6 节追加 6.7-6.10 四个子节

在 6.1-6.6 后追加：

```markdown
### 6.7 数据字段产出（本文件写哪些 AWS 命名字段）
| # | 字段名 | 行号 | 写入载体（CSV/JSON/dict）| 字段语义 | GCP/中立等价命名 | 双写过渡？|
|---|--------|------|---------------------------|----------|-------------------|-----------|
| 1 | aws_standard_gbps | L174 | dict→CSV 列 | 网络带宽标准化 Gbps | network_standard_gbps | ✅ |
| 2 | ena_bw_in | L412 | CSV 列 | ENA 入带宽 | nic_bw_in | ✅ |

**如本文件不写任何 AWS 命名字段：写"本文件无数据字段产出 ✅"**

### 6.8 数据字段消费（本文件读哪些 AWS 命名字段）
| # | 字段名 | 行号 | 读取载体 | 上游写入方文件 | 改名后影响（KeyError 风险）|
|---|--------|------|----------|------------------|-----------------------------|
| 1 | ena_bw | L412 | df['ena_bw'] | monitoring/unified_monitor.sh | 高 — 必须读时归一化 |

**如本文件不读任何 AWS 命名字段：写"本文件无数据字段消费 ✅"**

### 6.9 输出文件名/标题 AWS 字面（图表 / 报告 / log 文件）
| # | 文件名/标题模板 | 行号 | 输出类型 | 渲染示例 | platform-aware 改造方案 |
|---|------------------|------|----------|----------|--------------------------|
| 1 | f"ebs_aws_{type}_comp.png" | L880 | chart.png | ebs_aws_gp3_comp.png | `case $CLOUD_PROVIDER: gcp → f"disk_gcp_{type}.png"` |

**如本文件不输出文件名：写"本文件无输出文件命名 ✅"**

### 6.10 字段改名安全性评估
- 本文件如把字段 X 改为 X' → 下游受影响文件清单：[file:line, ...]（必须实际 grep 仓库得出）
- 双写过渡期方案：旧名 + 新名同时写多久？切换信号是什么？
- 读时归一化层位置：建议在哪个 utils 文件加 platform-aware 字段映射函数
- 风险等级评分（按受影响下游数）：
  - 🔴 极高 = 5+ 下游
  - 🟠 高 = 2-4 下游
  - 🟢 低 = 0-1 下游
```

**6.7-6.10 全部必填**。即使本文件无字段产出/消费/输出，也必须填 "✅ 无" 占位。

#### R20.7.2 — TRACKER 第十章实时同步

每读完一个文件，必须 patch `02-GCP-MIGRATION-TRACKER.md` 第十章：
- **10.1 全局字段索引**：按字段名维护"写方 + 读方"双向链表（一个字段可能多个写方 / 读方）
- **10.2 字段改名风险评分**：按下游消费方数累加评分
- **10.3 输出文件命名清单**：所有图表/报告/log 命名按文件分组
- **10.4 双写过渡期计划**：哪些字段需要双写，过渡期多久，何时删旧名

漏 patch TRACKER 第十章 = 本笔记不算 FULL，COVERAGE.md 退回 PARTIAL。

#### R20.7.3 — R10 自检追加数据契约维度

R10 每轮 self-check 额外含：
- 本轮所有 file-notes 是否都有 6.7-6.10？（缺一即作废重写）
- 字段产出/消费 grep 验证：CSV/JSON 实际产物里的字段是否与笔记 6.7 一致？
- 本轮所有字段改名风险评分是否已累加到 TRACKER 10.2？

#### R20.7.4 — R16 抽查扩到 7 处

第 7 抽必查数据契约维度：
- 抽 file-notes 的 6.7 或 6.8 表 1 行 → grep 原文确认行号/字段名/载体 → 验证 6.10 风险评分是否合理
- 任一捏造（字段不存在 / 行号错 / 评分跳级）→ 本 Round 作废

#### R20.7.5 — R17.5 全仓盘点追加

每轮末 R17.5 必须额外汇报：
- 本轮新增"产出字段"数 + 累计总数
- 本轮新增"消费字段"数 + 累计总数
- 本轮新增"输出文件命名"数 + 累计总数
- TRACKER 10.1 全局字段索引条目数是否吻合

#### R20.7.6 — 早起报告必填 R20.7 章节

`early-morning-report.md` 第 8 + 9 章节（见 R20.6 已含）：
- **第 8 章节**：数据契约迁移路径
  - 完整字段产出/消费索引（按写方 → 读方箭头图）
  - 每个字段的双写过渡期补丁（cp 即可用）
  - 读时归一化层代码草案（建议放 `utils/field_normalizer.py`）
- **第 9 章节**：输出文件命名 platform-aware 改造清单
  - 按 file 分组：每个 `f"ebs_aws_*"` 改成 `f"{disk_prefix()}_*"` 的补丁

---

## 🔴 EOF REMINDER — 你刚才读完了规则

如果你刚才读这个文件是因为 R-1 [Gate 1]：
→ 下一动作必须是 [Gate 2] `read_file analysis-notes/01-progress.md`
→ **不是** read_file 业务代码
→ 如果你想跳过 → 你正在违反 R-1，停下来

如果你刚才读这个文件不是因为 R-1：
→ 你现在需要走 R-1，请回到文件顶部从 [Gate 1] 开始

EOF
