## 任务：补全 file-note 中漏覆盖的函数到 R20 §6.x 子节

**项目根目录**: `/usr/local/google/home/lelandgong/blockchain-node-benchmark`
**审计基线 commit**: `e843571`（业务代码绝对不动）
**当前工作目录**: 同上

### 任务目标

针对**指定的 1 个业务源文件**，把它的 file-note 里**漏覆盖的函数**补回到 R20 §6（或 §8、§14，沿用 note 已有编号约定）的对应子节里。

### 输入

你会收到 3 个变量：
- `CODE_PATH`: 源代码文件的相对路径（如 `monitoring/unified_monitor.sh`）
- `NOTE_PATH`: 对应 file-note 的绝对路径
- `MISSING_FUNCS`: JSON 数组 `[{"line": 119, "name": "validate_numeric_value"}, ...]`，列出漏覆盖的所有函数

### 工作步骤

1. **读现有 note 全文**（`read_file NOTE_PATH`）
   - 弄清这个 note 用的章节编号约定：是 §6.x / §8.x / 还是 §14.x？
   - 看现有 §6.1（字段输出链）/ §6.2（字段消费链）/ §6.3（调用链）/ §6.4（CSV 数据契约）/ §6.5（复合指标公式）/ §6.6（退化策略）/ §6.7-§6.10（数据契约 R20.7）的内容**风格、表格格式、详略程度**
   - 找出 §3（调用链）、§4（关键函数清单）、§5（关键事实）等业务章节如何描述函数

2. **逐个读 MISSING_FUNCS 列出的函数**（`read_file CODE_PATH offset=line limit=80`）
   - 弄清函数的：职责（1 句话）、参数、返回值、内部调用、被谁调用、读写什么文件/字段、是否含 AWS 字面、是否含 GCP 阻塞点

3. **写补丁**——把漏函数补到 note，**两个补充位置**（必须都做）：
   - **(a) note 业务章节** — 比如 §3（关键函数清单）或 §4（关键事实），追加这批函数到表格里，格式参考现有行：
     ```
     | L行号 | 函数名 | 职责 | 调用关系 | 备注 |
     ```
   - **(b) R20 §6.x 章节** — 视函数性质分别追加到：
     - §6.1（字段输出链）：如果函数输出 CSV 列 / env var / log line / JSON key
     - §6.2（字段消费链）：如果函数读取上游字段
     - §6.3（调用链）：如果函数 spawn / exec / source 其他文件
     - §6.4（CSV 数据契约）：如果函数生成 / 解析 CSV header
     - §6.5（复合指标公式）：如果函数做数值派生
     - §6.6（退化策略）：如果函数实现 fallback / 错误恢复 / 重试

4. **写 note** 用 `patch` 工具（精确插入，不要重写整个文件）：
   - 在现有相关章节的末尾追加新行 / 新表格行
   - 保留所有现有内容不动
   - 行号引用必须用 `L<n>` 格式（让 audit-coverage.py 能识别）
   - 函数名必须**字面出现**在 note 中（这是 audit 工具的识别 key）

### 规则强制

- **R0 零号规则**：不编造。每个函数描述必须可在 `read_file CODE_PATH` 验证
- **R7 红线**：单次 `read_file` 不要超过 500 行；分段读大文件
- **R12 标签**：如果某函数有 AWS 字面、GCP 阻塞、跨进程契约，必须打 `[AWS-ONLY]` / `[GCP-BLOCKER P0/P1/P2/P3]` / `[CROSS-PROC-CONTRACT]` 标签
- **保留风格**：完全沿用现有 note 的表格列数、emoji、标题层级、行号引用密度

### 验收标准（自检）

完成后必须**自己跑一次验证**：
```bash
python3 -c "
with open('NOTE_PATH') as f: content = f.read()
import json
missing = json.loads('MISSING_FUNCS')
unmentioned = [m for m in missing if m['name'] not in content]
print(f'剩余未点名: {len(unmentioned)}/{len(missing)}')
for u in unmentioned: print(f'  L{u[\"line\"]} {u[\"name\"]}')
"
```

**期望输出**：`剩余未点名: 0/N`

### 报告（return value）

返回结构化总结：
1. 用的章节编号约定（§6 / §8 / §14）
2. 在哪些章节追加了内容 + 追加字节数
3. 自检验证结果（必须 0/N）
4. 是否发现新的 GCP 阻塞点 / AWS 字面（如有，列出 file:line + 性质）
5. 是否触动业务代码（绝对不能；若有任何编辑请说"已 revert 业务代码 X"）

不要省略自检。不要"我估计 OK"。必须跑命令验证 0/N 才能 return success。
