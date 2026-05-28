# S4 wave — NS-2 Per-Method Resource Attribution 实施计划

> **Plan ID**: 2026-05-28-s4-ns2
> **Goal**: 实现 NS-2(mixed RPC method 权重 + per-method 资源归因 + method 级图表 + 双语 HTML 报告),不砍 NS-1/NS-3
> **Strategy**: γ 方案(三路并行 + solana 收尾验证)
> **Baseline commit**: `3277a3c` (feat/architecture-docs 分支)
> **关联文档**:
> - SSOT: `docs/NORTH-STAR.md` (NS-2 + Q4-1~Q4-10)
> - 架构: `docs/architecture/per-method-proxy-architecture-zh.md` (1-A)
> - Schema spec: `docs/architecture/chain-template-zero-code-spec-zh.md` (1-B)
> - Migration: `docs/architecture/migration-from-legacy-zh.md` (1-C)
> - 待决: `docs/architecture/OPEN-QUESTIONS.md` (OQ-5 / OQ-7 待 S4.1 锁定)

---

## 1. 范围与边界

### 1.1 本 plan 交付(NS-2 闭环)
- mixed mode 支持 weight 配置(per-chain template 驱动)
- proxy 拦截层(独立 Go 二进制,2 模式 declarative DSL)
- per-method 资源归因(秒级 group_by,分析层 join)
- method 级图表 + HTML 报告章节
- solana 1 链 e2e 跑通 + 36 链 schema 对称 + DSL 覆盖率验证

### 1.2 本 plan 不交付(NORTH-STAR 范围边界 + OPEN-QUESTIONS 推后)
- ❌ OpenTelemetry / Prometheus / Grafana 实时 dashboard(sink 抽象预留接口即可)
- ❌ fetcher 28 链扩展(OQ-6,归阶段 5)
- ❌ fake-node v2 剩余 5 个 stub handler(OQ-9,归阶段 5)
- ❌ envoy + Lua failback 实现(Q4-8 兜底,PoC 失败才启用)
- ❌ NS-3 §6.1 现存 3 处违规的修复(OQ-9 (d),独立 PR)

---

## 2. γ 方案 4 阶段总览

```
S4.1  spec 锁定 (1-3 天)
      └─ 阶段 1-B chain-template-zero-code-spec 补 OQ-5/OQ-7 章节
         + spec 锁定必答清单(W1/W2/W3 实施前必答)
         + 签字才进 S4.2

S4.2  三路并行 (~2 周)
      ├─ W1: chain template 36 链填 (mixed_weighted + proxy_extraction)
      ├─ W2: Go proxy 实现 (DSL parser + 2 模式 + sink)
      └─ W3: 分析层 + 可视化 (per-method 归因 + 图表 + HTML 章节)

S4.3  solana 端到端集成 (3-5 天)
      └─ W1+W2+W3 在 solana 真节点跑通
         对照 per-method-proxy-architecture-zh.md §8 八条验收

S4.4  36 链对称验证 (2-3 天)
      └─ 36 链分别启 proxy,smoke 验 DSL 2 模式覆盖率
         不要求每链 e2e benchmark(那是 NS-1)
         覆盖率 < 32/36 → 触发 Q4-8 envoy+Lua 兜底评估
```

**总工时(架构师视角)**:2-3 周(并行 vs 串行可省 ~30%)
**风险**:S4.1 spec 锁不死 → 三路返工 → 用严格签字 + spec 必答清单防御

---

## 3. S4.1 — Spec 锁定阶段

### Task 1.1: chain-template-spec 补 OQ-5 (proxy_extraction DSL) 章节

**目标**:把 OPEN-QUESTIONS.md OQ-5 初稿(4 种模式 + 字段定义)正式合入 spec §1.7(新章节)+ §1.1 顶层字段表加一行

**文件**:
- Modify: `docs/architecture/chain-template-zero-code-spec-zh.md`
  - §1.1 顶层字段从 8 个扩到 9 个(加 `proxy_extraction`)
  - 新增 §1.7 `proxy_extraction` 完整字段定义
- Modify: `docs/architecture/OPEN-QUESTIONS.md` OQ-5 标 ✅ 已锁定
- Modify: `docs/NORTH-STAR.md` §3 决策表加 Q4-11 行

**Step 1: 写 4 种模式的 Schema (json_rpc / rest / bitcoin_rpc / grpc)**
```jsonc
"proxy_extraction": {
  "protocol": "json_rpc | rest | bitcoin_rpc | grpc",  // 枚举,必填

  // 模式 1: json_rpc / bitcoin_rpc
  "method_source": "body.method",          // JSON path
  "id_source": "body.id",                  // 可选,latency 配对
  "params_source": "body.params",          // 可选,统计 params 大小

  // 模式 2: rest
  "url_pattern": "^/v2/([^/]+)/.*$",       // 正则
  "url_method_group": 1,                   // 捕获组索引
  "method_normalize": { "transactions": "get_transactions" },  // 可选映射

  // 模式 3: grpc
  "grpc_service": "hedera.MirrorService",  // 全限定服务名
  "grpc_method_field": "method"            // :method header 提取
}
```

**Step 2: 36 链穷举填表证明 DSL 够用(AP9 防绝对宣言)**
- 为 7 个 adapter family 各挑 1 个代表链,人工填 `proxy_extraction`
- 如果某 family 4 种模式都表达不出 → **STOP**,reverse 到 Q4-8 envoy+Lua 兜底评估
- 期望产物:7 个 family 各自至少 1 个填好的范例,放 spec §1.7 末

**Step 3: spec 写 schema 校验规则**
- 必填 `protocol`,enum check
- 按 `protocol` 值不同,必填字段不同(条件必填规则)
- 校验工具 `tools/validate_chain_template.py` 必须扩展支持(归 W1 实施)

**Step 4: review + commit**
```bash
git add docs/architecture/chain-template-zero-code-spec-zh.md \
        docs/architecture/OPEN-QUESTIONS.md \
        docs/NORTH-STAR.md
git commit -m "spec(s4.1): OQ-5 proxy_extraction DSL 锁定 + 7 family 范例填表

- chain-template-spec §1.7 新增 proxy_extraction 完整字段定义(2 模式)
- OPEN-QUESTIONS OQ-5 标 ✅ 已锁定
- NORTH-STAR §3 决策表加 Q4-11(proxy_extraction DSL schema)
- ADR-0005 后续: ADR-0006 待补 (S4.4 36 链对称验证通过后)"
```

---

### Task 1.2: chain-template-spec 补 OQ-7 (mixed_weighted schema) 章节

**目标**:把 OPEN-QUESTIONS.md OQ-7 候选 B(新增 `mixed_weighted` 向后兼容)合入 spec §1.4

**文件**:
- Modify: `docs/architecture/chain-template-zero-code-spec-zh.md` §1.4 `rpc_methods` 格式
- Modify: `docs/architecture/OPEN-QUESTIONS.md` OQ-7 标 ✅ 已锁定
- Modify: `docs/NORTH-STAR.md` §3 决策表加 Q4-12 行

**Step 1: 写 schema(候选 B,向后兼容)**
```jsonc
"rpc_methods": {
  "single": "eth_getBalance",                                  // 现有,不动
  "mixed": "eth_getBalance,eth_getTransactionCount,...",       // 现有,保留(老 user_config)
  "mixed_weighted": [                                          // 新增,可选
    {"method": "eth_getBalance", "weight": 40},
    {"method": "eth_getTransactionCount", "weight": 30},
    {"method": "eth_blockNumber", "weight": 20},
    {"method": "eth_gasPrice", "weight": 10}
  ]
}
```

**Step 2: 兼容规则**
- 若 `mixed_weighted` 缺失 → 退化为均匀分布(round-robin,现有行为)
- 若 `mixed_weighted` 存在 → 必须满足:weight sum = 100,每个 method 在 `param_formats` 有对应 key
- `mixed_weighted` 列出的 method 必须是 `mixed` 字符串的子集(schema 校验)

**Step 3: review + commit**
```bash
git add docs/architecture/chain-template-zero-code-spec-zh.md \
        docs/architecture/OPEN-QUESTIONS.md \
        docs/NORTH-STAR.md
git commit -m "spec(s4.1): OQ-7 mixed_weighted schema 锁定(候选 B 向后兼容)"
```

---

### Task 1.3: Spec 锁定必答清单(W1/W2/W3 实施前必须知道的字段决策)

**目标**:出一份 `docs/plans/2026-05-28-s4-spec-checklist.md`,列 W1/W2/W3 各自实施前必须签字的字段决策,防止三路并行时基于不同隐性假设实现

**文件**:Create `docs/plans/2026-05-28-s4-spec-checklist.md`

**必答清单**(草稿):

**For W1 (chain template 36 链填):**
- [ ] mixed_weighted 默认权重(若 PoC 阶段无真实数据)用什么?(候选:全 100/N 均匀;或用 research_notes 01-06 的 "典型延迟量级" 倒数加权)
- [ ] 36 链 mixed 字段历史上的 method 列表,哪些是不该用 weight 的(只读 vs 写入分布)?

**For W2 (Go proxy):**
- [ ] sink 文件命名规则(`proxy_method_<chain>_<timestamp>.csv` 还是 `<run_id>/proxy_method.csv`)?
- [ ] sink 字段最小集 6 列(Q4-9 已定:`timestamp, method, req_bytes, resp_bytes, latency_ms, status`)是否够?是否要加 `node_response_status`?
- [ ] proxy 失败模式:upstream 节点 504 时,proxy 是 503 还是 透传?
- [ ] DSL 2 模式中,`json_rpc` 是否需要支持 batch request(数组 body)?

**For W3 (分析层 + 可视化):**
- [ ] 秒级 group_by 的时间窗对齐策略(monitor CSV 是每秒 1 行,proxy JSONL 是流式)— 用左闭右开 `[t, t+1)` 还是中心对齐?
- [ ] HTML 报告 method 级章节模板:每 method 至少 3 图(QPS/latency/资源归因),具体哪 3 资源维度(CPU/MEM/EBS-iops/Network)?
- [ ] per_method_resource_*.csv 字段顺序与 unified_monitor CSV 一致还是按 method 分组?

**Step 1**: 三路各列 3-5 个必答问题(W1/W2/W3)
**Step 2**: user review + 逐条签字
**Step 3**: 签字结果合入 spec 文档对应章节(或写 ADR)

---

### Task 1.4: S4.1 review gate(进 S4.2 前置条件)

**Gate 必过条件**:
- [ ] spec OQ-5 章节合入,7 family 至少各 1 个范例填好
- [ ] spec OQ-7 章节合入,向后兼容规则明确
- [ ] 必答清单全部签字
- [ ] 至少 1 个 commit 推到 origin(spec 锁定 commit)
- [ ] 用户明示同意进 S4.2

---

## 4. S4.2 — 三路并行实施阶段

### 4.1 W1 — chain template 36 链填

**目标**:36 链 chain template 全部填 `mixed_weighted` + `proxy_extraction`,**0 Python 改动**(NS-3 验证)

**文件路径**:`config/chains/*.json` × 36
**预计工时**:~1 周(借鉴 ADR-0005 step 9 批改流程,边际成本低)

**Task W1.1**: 扩展 `tools/validate_chain_template.py` 支持新 schema 校验
**Task W1.2**: 36 链按 family 分组批改(EVM 16 / substrate 5 / tendermint 5 / rest 4 / bitcoin 4 / ogmios 1 / hedera_dual 1)
**Task W1.3**: 每 family 完成后跑 `tests/test_chain_adapters.py` + ci_smoke 验证不退化
**Task W1.4**: 36 链 commit 拆分原则(每 family 1 commit,便于 review 和 bisect)

**验收**:
- [ ] 36/36 link 通过 `validate_chain_template.py`
- [ ] `test_chain_adapters.py` 12/12 PASS 不退化
- [ ] ci_smoke.sh 19/19 PASS 不退化
- [ ] `git diff --name-only baseline..head` 只有 `config/chains/*.json` + `tools/validate_chain_template.py`(NS-3 验证)

---

### 4.2 W2 — Go proxy 实现

**目标**:独立 Go 二进制,DSL parser + 2 模式 handler + sink,目标 ≤ 800 行(Q4-8 锁定)

**文件路径**:新建 `tools/proxy/` 目录
- `tools/proxy/main.go` — entry point + flag parsing
- `tools/proxy/dsl.go` — DSL parser(读 chain template,build extractor)
- `tools/proxy/extractor.go` — 2 模式 extractor 实现
- `tools/proxy/sink.go` — sink 抽象(CSV 默认 + JSONL/Parquet 切换)
- `tools/proxy/server.go` — HTTP/gRPC reverse proxy(transparent forwarding)
- `tools/proxy/self_meter.go` — proxy 自报基线(Q4-10 OQ-8 已锁,CPU/MEM 每秒自报)
- `tools/proxy/proxy_test.go` — 单测(用 fake-node v2 做 upstream)
- `tools/proxy/go.mod` / `tools/proxy/go.sum`
- `Makefile` — `make proxy` 编译目标

**预计工时**:~2 周
**依赖**:S4.1 OQ-5 spec 锁定;独立于 W1/W3

**Task W2.1**: Go module init + Makefile + CI 集成
**Task W2.2**: DSL parser(读 chain template `proxy_extraction` 字段)
**Task W2.3**: 2 模式 extractor 实现(json_rpc / rest)
**Task W2.4**: HTTP 反向代理 + transparent forwarding
**Task W2.5**: sink 抽象层(CSV 默认 + 环境变量 `PROXY_SINK_FORMAT` 切换)
**Task W2.6**: proxy 自报基线(`proxy_self.csv` 每秒 cpu_pct/mem_mb)
**Task W2.7**: 单测(7 family 各至少 1 个 happy path + 1 个 error path)
**Task W2.8**: 性能 benchmark(Q4-8 撤销条件:< 5k QPS @ p99 < 10ms → 启用 envoy 兜底)

**验收**:
- [ ] `go test ./tools/proxy/...` 全绿
- [ ] LOC ≤ 800(Q4-8 锁定)
- [ ] `make proxy` 出独立二进制
- [ ] 性能 benchmark ≥ 5k QPS @ p99 < 10ms(Q4-8)

---

### 4.3 W3 — 分析层 + 可视化

**目标**:Python 模块实现 per-method 归因(秒级 join)+ method 级图表 + HTML 报告章节

**文件路径**:新建文件
- `analysis/per_method_attribution.py` — 秒级 group_by 归因算法(Q4-7)
- `visualization/per_method_charts.py` — method 级图表生成器
- `templates/report_per_method_section.html` — HTML 报告新章节模板
- `tests/test_per_method_attribution.py` — 归因算法单测(mock sink 数据驱动)
- `tests/test_per_method_charts.py` — 图表生成单测

**预计工时**:~1.5 周
**依赖**:S4.1 OQ-5 sink schema 锁定(Q4-9 已定 6 列);独立于 W1/W2

**Task W3.1**: 归因算法实现(秒级 group_by + weight = method count / total)
**Task W3.2**: 单测覆盖(mock proxy sink 数据 + mock monitor CSV)
**Task W3.3**: method 级图表生成器(QPS / latency / 资源归因 / heatmap)
**Task W3.4**: HTML 报告章节模板 + 主报告 include
**Task W3.5**: 双语支持(中文 + 英文,与现有报告框架对齐)
**Task W3.6**: e2e 验收数据用 mock 跑通(W3 阶段不依赖真 W2 proxy 输出,用 fixture)

**验收**:
- [ ] `pytest tests/test_per_method_attribution.py` 全绿
- [ ] `pytest tests/test_per_method_charts.py` 全绿
- [ ] mock 数据生成的 HTML 报告 method 级章节渲染正常(本地浏览器看)
- [ ] 字段命名与 W2 sink 输出对齐(S4.1 必答清单签字结果)

---

## 5. S4.3 — solana 端到端集成

**目标**:W1+W2+W3 在 solana 真节点跑通,对照 `per-method-proxy-architecture-zh.md` §8 八条验收

**前置**:S4.2 三路全部完成 + 各自 commit 已 push

**验收 8 条(逐条勾)**:
- [ ] solana.json 已填 `proxy_extraction` + `mixed_weighted`,**无 Python 代码改动**(NS-3)
- [ ] `PROXY_ENABLED=true` 跑通 vegeta → proxy → 节点,vegeta success rate ≥ 99%
- [ ] `PROXY_ENABLED=false` 跑老模式(回归测试,W-4 渐进改造验证)
- [ ] `proxy_method_solana_*.csv` 字段完整(6 列最小集)
- [ ] 分析层秒级 join 出 `per_method_resource_*.csv`
- [ ] HTML 报告含 method 级章节,每 method 至少 3 图
- [ ] proxy 自身 CPU/MEM 在报告中显式标注(`proxy_self.csv`)
- [ ] chain template 走偏 check list 无违规

**PoC 撤销条件**(任一未过):
- 文档 NS-3 章节必须改为"NS-3 是目标,当前未达成"
- 必须暂停 S4.4 并回头检讨
- 写 ADR-0006 记录 PoC 失败原因 + 调整方案

---

## 6. S4.4 — 36 链对称验证

**目标**:36 链分别启 proxy,smoke 验 DSL 2 模式覆盖率;**不要求 e2e benchmark**(那是 NS-1)

**Task S4.4.1**: 写 `tests/test_proxy_dsl_coverage.py`,36 链分别 load chain template + dry-run DSL extractor(用 fixture 请求)
**Task S4.4.2**: 出覆盖率报告(N/36 链 DSL 解析成功)
**Task S4.4.3**: 覆盖率 ≥ 32/36 → OK,继续;< 32/36 → 触发 Q4-8 envoy+Lua 兜底评估

**验收**:
- [ ] `test_proxy_dsl_coverage.py` 覆盖率 ≥ 32/36
- [ ] 失败链(若 < 36)记入 `OPEN-QUESTIONS.md` 新 OQ + 触发 ADR-0007

---

## 7. Commit 节奏 + branch 策略

**分支**:`feat/architecture-docs`(继续在当前分支,不开新分支,避免 rebase 麻烦)

**Commit 拆分**(每 task 1 commit,frequent commits 原则):
- S4.1: 3-4 commits(spec OQ-5 / spec OQ-7 / 必答清单 / review)
- S4.2 W1: 7 commits(每 family 1 commit)
- S4.2 W2: 8 commits(每 Task W2.N 1 commit)
- S4.2 W3: 6 commits(每 Task W3.N 1 commit)
- S4.3: 1 commit(solana 集成 + 验收报告)
- S4.4: 1 commit(36 链对称验证 + 覆盖率报告)

**预计总 commits**:~26 个

**Push 节奏**:每 task 完成后立即 push,避免本地堆积

---

## 8. 风险登记 + 反转条件

| 风险 | 影响 | 反转条件 | 应对 |
|---|---|---|---|
| S4.1 spec 锁不死 → 三路返工 | 高 | spec review 后发现 > 3 处歧义 | 暂停 S4.2,补 spec |
| DSL 2 模式覆盖 < 32/36 链 | 高 | S4.4 覆盖率 < 32/36 | 触发 Q4-8 envoy+Lua 兜底,写 ADR-0007 |
| Go proxy LOC > 800 | 中 | W2 完成 LOC 超 | 必须重构或砍非核心特性(自报基线优先级最低) |
| Proxy 性能 < 5k QPS @ p99 < 10ms | 中 | W2.8 benchmark 未达 | 触发 Q4-8 envoy 兜底 |
| solana 真节点 access 失败 | 中 | S4.3 节点连不通 | 用 fake-node v2 + solana fixtures 临时替代 |
| W1/W2/W3 三路 schema 对不齐 | 中 | S4.3 集成时字段错配 | S4.1 必答清单防御;真错配走 fix-forward |

---

## 9. ADR 待写清单

- `ADR-0006`: S4.3 PoC 验收结果(8 条逐条记录,通过 / 未通过)
- `ADR-0007`: 仅当 S4.4 覆盖率 < 32/36 时写(envoy+Lua 兜底启用决策)
- `ADR-0008`: 仅当 S4.1 OQ-5 spec 锁定后,proxy DSL 2 模式有第 5 模式必要时写

---

## 10. 执行 handoff

**Plan 完成后**,按 `writing-plans` skill execution handoff 段:

> Plan complete and saved. Ready to execute using subagent-driven-development — I'll dispatch a fresh subagent per task with two-stage review (spec compliance then code quality).

但本 plan 涉及 NORTH-STAR / spec 文档修改 + Go 代码新建 + Python 重构,**用户须先签字 plan 整体可行**(γ 方案确认)+ **S4.1 spec 锁定后再决定 S4.2 是否走 subagent 并行**。

**S4.1 由主对话直接执行**(spec 文档修改不适合 subagent),S4.2 W1/W2/W3 可选 subagent 并行(独立 toolset)。

---

**End of Plan v1.0**
