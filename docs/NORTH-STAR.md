# NORTH-STAR — 框架演进北极星需求

> **状态**:锁定(2026-05-27)
> **作用**:本框架所有架构演进、代码重构、PoC 落地的**单一权威来源**(SSOT)。
> 与本文档冲突的任何 docs / skill / session 讨论 / 代码提案 **以本文档为准**。
> 修改本文档必须新增 ADR(架构决策记录),不得静默覆盖。
>
> **配套文档**:
> - `docs/architecture/CURRENT-STATE.md` — 现状基线快照(高频更新,不算决策)
> - `docs/architecture/OPEN-QUESTIONS.md` — 待决项追踪(随研究推进更新答案)
> - `docs/architecture/decisions/` — ADR 目录(决策日志)

---

## 1. 三大北极星需求(锁定,不可漂移)

| ID | 需求 |
|---|---|
| **NS-1** | **支持 36 链**(chain template 零代码加链 — 新链只配 JSON,不写 Python) |
| **NS-2** | **支持 mixed 模式 RPC method 权重配置**,并按 method 维度归因节点端系统资源消耗(CPU / MEM / EBS / Network 等维度,具体字段以 `monitoring-mechanism-zh.md` 和代码实查为准),生成 method 级图表(数量随 PoC 收敛后再定),引用至双语 HTML 报告 |
| **NS-3** | **零代码加链原则覆盖 adapter 层 + proxy 协议解析层**(NS-1 的强化形式 — proxy 解析规则也必须 declarative,新链填 JSON 即可) |

---

## 2. 真实业务驱动(为什么要做)

- **业务事实 1**:不同 RPC method 在节点端资源消耗差异显著
  (示例:`getBalance` 轻、`getLogs` / `getProgramAccounts` / `eth_call` 重)
- **业务事实 2**:真实业务流量中各 method 比例不同
  (示例:`getBalance` 60% / `getBlock` 30% / `getLogs` 10%)
- **业务事实 3**:节点运维人员需要在看到 method 级资源图时
  **快速判断**:"我的节点在生产负载下,瓶颈是哪条 method?哪条 method 撑满了 EBS?"
- **业务事实 4**:跨 36 链对称性 — 同一套压测 + 监控 + 报告流水线,
  通过切换 chain template 即可对任一支持的链做完整压测,产物形态完全一致。

---

## 3. 已锁定架构决策(2026-05-27 session)

| ID | 决策点 | 选定方案 |
|---|---|---|
| Q4-1 | **proxy 形态** | **独立进程**(systemd / docker container,虚拟机 + GKE 通用) |
| Q4-2 | **proxy 配置驱动** | **按 chain template 单链启动**,切链重启 proxy |
| Q4-3 | **proxy 日志 sink** | **默认 CSV/JSONL**(独立文件,分析层 join);**sink 抽象层预留 OTel/Prom**,生产场景可插拔 |
| Q4-4 | **chain template proxy 解析规则表达** | **完全 declarative DSL**(只支持有限模式:JSON body field / URL path regex / Bitcoin RPC body / gRPC method),**禁止内嵌 lua/python snippet** |
| Q4-5 | **vegeta → proxy 链路改造** | **`PROXY_ENABLED` + `PROXY_URL` 显式环境变量**,默认关闭(向后兼容老用户),可关 proxy 跑老模式做对比基线 |
| Q4-6 | **现有 monitor 字段** | **不动**(具体字段数以代码实查为准),proxy 是新增独立数据源,join 在分析层完成 |
| Q4-7 | **per-method 归因算法** | **加权 group_by + 秒级时间窗**;**权重源 = 公开资料先配粗粒度**(`analysis-notes/research_notes/01-06` 各 method "典型延迟量级" → 映射 1/10/100 三档),**后期实际使用根据真实压测数据迭代调整**(非阻塞决策);PoC 撤销条件:ground truth 误差 > 20% 才升级回归算法 |
| Q4-8 | **proxy 实现** | **自写 Go 小代理(主方案)**,严格 declarative DSL,目标 ≤ 800 行;**envoy + Lua 兜底(failback)**仅在主方案 PoC 失败时启用;PoC 撤销条件:性能 < 5k QPS @ p99 < 10ms,或 DSL 覆盖 < 32/36 链 → 启用兜底 |
| Q4-9 | **sink 默认格式** | **默认 CSV** + 字段最小集 6 列(`timestamp, method, req_bytes, resp_bytes, latency_ms, status`);sink 抽象层支持 JSONL/Parquet 切换(环境变量 `PROXY_SINK_FORMAT`);无强撤销条件,日志体积超 100GB/天再评估 |
| Q4-10 | **proxy 自身开销处理** | **默认透明记录 + 自报基线**(`proxy_self.csv`:每秒自报 cpu_pct / mem_mb);分析层从节点资源减去基线后再归因 method;K8s 生产用 sidecar 独立 pod 隔离;PoC 撤销条件:proxy CPU > 节点 10% 或自报偏差 > 30% → 必须 cgroup 隔离 |
| W-1 | **文档落点** | `docs/architecture/` 新目录,与现有"现状说明书"分开 |
| W-2 | **阶段 1 架构文档形态** | **3 份独立 md**(整体架构 + chain template spec + migration 路径) |
| W-3 | **架构图工具** | mermaid(git diff 友好,GitHub 原生渲染) |
| W-4 | **现有代码纳入策略** | **渐进重构**(adapter / monitor / target_generator 保留并改造,不重写、不 v2 并行、不激进重写) |
| W-5 | **阶段 1 期间** | **冻结代码**(28 链 adapter wave 暂停,直到阶段 1 架构文档 review 通过) |
| W-6 | **阶段 0 顺序** | 0-A NORTH-STAR + 0-B README 校正先做(阶段 1 输入);0-C/D/E 推迟 |

**待决项(未锁定)**:见 `docs/architecture/OPEN-QUESTIONS.md`
- ~~proxy 具体选型(envoy / nginx / mitmproxy / 自写 Go)~~ → **已锁 Q4-8**(2026-05-27 用户决策:自写 Go 主,envoy 兜底)
- proxy 部署形态细节(systemd vs docker container)
- ~~per-method 归因算法细节(group_by vs 回归)~~ → **已锁 Q4-7**(2026-05-27 用户决策:权重按公开资料配,后期迭代)
- ~~sink 默认格式(CSV vs JSONL)~~ → **已锁 Q4-9**(2026-05-27 用户决策:CSV 默认 + 抽象层支持切换)

---

## 4. 范围边界(明确不在范围内 / PoC 不做)

| 不做项 | 原因 |
|---|---|
| **OpenTelemetry / Prometheus / Grafana 实时 dashboard** | PoC 阶段范围外;Q4-3 sink 抽象层为生产场景预留接口 |
| **重写 user_config.sh / single mode 工作流** | 违 W-4 渐进重构,破坏现有用户 |
| **加 method 列到 unified monitor CSV** | 违 Q4-6,破坏现有 monitor schema |
| **proxy 内嵌 lua / python snippet** | 违 NS-3 + Q4-4,本质=写代码加链 |
| **iptables redirect 实现透明 proxy** | 违 Q4-5,GKE pod 网络模型不友好,需 root |
| **客户端时间窗切片做 per-method 归因**(60s 只发 method A → 60s 只发 method B) | 违 NS-2,破坏 mixed 真实业务工作负载模拟 |
| **proxy 自身做 method-level cgroup 资源切片** | 节点端 RPC 由 validator 单进程内部线程处理,cgroup 区分不到 method;归因靠 proxy 时序日志 + monitor 时序数据时间对齐 |
| **先做 36 链 PoC 再做架构设计** | 违 W-5 + W-6 阶段顺序,会导致 PoC 完成后被架构推翻返工 |
| **MEM cache hit rate 的 per-method 归因** | 状态量(非流量量)难以按时间窗分摊,确认可舍弃 |

---

## 5. 走偏识别 check list(防 session 漂移 — 任何 AI Agent / 新人触发以下任一情形,**立刻 STOP**)

| 触发情形 | 违反 | 应对 |
|---|---|---|
| 有人提"per-method 归因用客户端时间窗切片" | NS-2 mixed 真实流量原则 | STOP,改用 vegeta → proxy → 节点 + 分析层时间对齐 |
| 有人提"proxy 内嵌 lua / python filter" | NS-3 零代码加链 | STOP,只能 declarative DSL |
| 有人提"加 method 列到 unified_monitor CSV" | Q4-6 monitor 不动 | STOP,proxy 独立 CSV,分析层 join |
| 有人提"iptables redirect" | Q4-5,GKE 不友好 | STOP,改 `PROXY_ENABLED` 显式开关 |
| 有人提"先做 PoC 再设计架构" | W-5 / W-6 阶段顺序 | STOP,阶段 1 架构文档未 review 不动代码 |
| 有人提"重写 user_config / single mode" | W-4 渐进重构 | STOP,改为向后兼容改造 |
| 有人提"proxy 一次性加载全 36 链协议" | Q4-2 单链启动 | STOP,按 chain template 启动单链 proxy 实例 |
| 有人在 chain template 加 `proxy_extraction_lua` / `proxy_extraction_python` 字段 | NS-3 + Q4-4 | STOP,只允许 declarative 4 种模式 |
| 有人提"PoC 阶段就要做 Grafana dashboard" | 范围边界 | STOP,PoC 不做实时可视化,只出静态图 + HTML |
| 有人在未补 ADR 的情况下改本文档锁定决策 | 第 0 节文档前言 | STOP,要求先写 ADR |

---

## 6. 决策溯源

- **本文档锁定的所有决策**源自 conversation:2026-05-27 session(用户:lelandgong)
- **现状基线 commit**:`face2ac` (2026-05-27,S3-E.4 tezos)
- **现状快照**:`docs/architecture/CURRENT-STATE.md`(36 链 adapter 状态,会随实施变化)
- **待决项追踪**:`docs/architecture/OPEN-QUESTIONS.md`(proxy 选型 / 归因算法等)
- **后续修改纪律**:本文档所有决策修改必须在 `docs/architecture/decisions/` 新增 ADR
  (Architecture Decision Record:背景 / 选项 / 决策 / 后果),不得静默覆盖

---

## 7. 阶段路线(粗粒度,仅作 roadmap 索引;不锁时间,详细工作量见各阶段产物)

```
阶段 0  污染修复 + 北极星落地(当前)
  ├─ 0-A  本文档 docs/NORTH-STAR.md + CURRENT-STATE.md + OPEN-QUESTIONS.md  [in_progress]
  ├─ 0-B  README.md / README_ZH.md 校正        [next]
  ├─ 0-C  blockchain-testing-features-zh 加 weight 未实现警告  [推迟]
  ├─ 0-D  configuration-guide-zh + data-architecture-zh 阅读+污染补充  [推迟]
  └─ 0-E  _archive_v1.4 改名 _archive_pre-v1.5  [推迟]

阶段 1  架构设计文档(冻结代码期)
  ├─ 1-A  docs/architecture/per-method-proxy-architecture-zh.md
  ├─ 1-B  docs/architecture/chain-template-zero-code-spec-zh.md
  └─ 1-C  docs/architecture/migration-from-legacy-zh.md

阶段 2  调研档(支撑材料,可与阶段 1 并行)
  └─ analysis-notes/research_notes/07-per-method-resource-attribution-via-proxy.md

阶段 3  skill 沉淀
  └─ skill: blockchain-node-benchmark-architecture(锁北极星 + 架构 + 决策日志 + 反例 check list)

阶段 4  PoC 实施(solana 1 链全闭环,严格按新架构)
阶段 5  36 链 weight + proxy dispatcher 全覆盖
阶段 6  file-notes 补全 + README 终稿(含英文版翻译)
```

---

**末**:本文档保持紧凑(目标 < 200 行)以保证可读性;后续若架构决策膨胀,
应**外移到 ADR**,本文档只保留 SSOT 摘要 + check list。
英文版 `NORTH-STAR-EN.md` 推迟到中文版稳定后翻译(避免反复重译)。
