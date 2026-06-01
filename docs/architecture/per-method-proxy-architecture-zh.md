# Per-Method 资源归因架构(via proxy)

> **状态**:阶段 1-A 草稿(2026-05-27)
> **作用**:本框架 NS-2(per-method 资源归因)+ NS-3(零代码加链覆盖 proxy 解析层)的**整体架构设计**。
> 阶段 1-B(chain template spec)+ 1-C(migration)是本文档的下游展开。
> **修改纪律**:本文档修改架构决策必须先更新 [NORTH-STAR](../NORTH-STAR.md)+ 写 ADR(`decisions/000X-*.md`)。
>
> **配套文档**:
> - [NORTH-STAR.md](../NORTH-STAR.md) — SSOT 北极星(NS-1/2/3 + 12 决策)
> - [CURRENT-STATE.md](./CURRENT-STATE.md) — 现状快照
> - [OPEN-QUESTIONS.md](./OPEN-QUESTIONS.md) — 9 个待决项
> - [chain-template-zero-code-spec-zh.md](./chain-template-zero-code-spec-zh.md) — 阶段 1-B(chain template DSL 完整 spec)
> - [migration-from-legacy-zh.md](./migration-from-legacy-zh.md) — 阶段 1-C(渐进迁移路径)
> - 现有架构文档:[architecture-overview-zh](../architecture-overview-zh.md) / [monitoring-mechanism-zh](../monitoring-mechanism-zh.md) / [data-architecture-zh](../data-architecture-zh.md) / [configuration-guide-zh](../configuration-guide-zh.md)

---

## 1. 北极星回顾(为什么需要本架构)

NORTH-STAR NS-2 要求 mixed RPC method 权重 + per-method 资源归因。当前框架的根本缺陷:

| 维度 | 当前现状 | NS-2 目标差距 |
|---|---|---|
| **mixed 流量构成** | `target_generator.sh` L254 `account_index % method_count` round-robin(均匀分布) | 真实业务非均匀(示例:`getBalance` 60% / `getBlock` 30% / `getLogs` 10%) |
| **资源监控维度** | 节点级聚合(CPU / MEM / EBS / Network 等,字段总数见 §4) | 无 method 维度 label,无法回答"哪条 method 撑满 EBS" |
| **图表归因** | 节点级 QPS / latency / success rate | 缺 method 级图表 |
| **报告** | 双语 HTML 报告(框架已就位) | 缺 method 级章节 + 引用 |

**根本约束**(NORTH-STAR 走偏 check list 已驳回):
- ❌ 不能客户端时间窗切片(60s 只发 A → 60s 只发 B)— 破坏 mixed 真实负载语义
- ❌ 不能加 method 列到 unified_monitor CSV(Q4-6:monitor schema 不动)
- ❌ 不能 proxy 内嵌 lua/python(违 NS-3 零代码加链)
- ❌ 不能 iptables redirect(违 Q4-5:GKE pod 网络不友好)

---

## 2. 架构总图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Per-Method 资源归因架构                                │
└─────────────────────────────────────────────────────────────────────────────┘

                          ┌──────────────────────┐
                          │  user_config.sh      │
                          │  PROXY_ENABLED=true  │  ← Q4-5 显式开关,默认关
                          │  PROXY_URL=...       │
                          └──────────┬───────────┘
                                     │
                                     ▼
        ┌─────────────────────────────────────────────────────────────┐
        │  第 1 层:执行层(现有,W-4 渐进改造)                          │
        │  ┌─────────────────┐    ┌──────────────────────┐            │
        │  │ fetcher (现有)   │ →  │ target_generator     │            │
        │  │ accounts.txt    │    │ (mixed weight 新增)  │            │
        │  └─────────────────┘    └──────────┬───────────┘            │
        │                                    │ targets.txt            │
        │                         (按 weight 分布拼 method)            │
        │                                    │                        │
        │                                    ▼                        │
        │                         ┌──────────────────────┐            │
        │                         │  vegeta attack       │            │
        │                         └──────────┬───────────┘            │
        └────────────────────────────────────│────────────────────────┘
                                             │ HTTP/gRPC 请求
                                             ▼
        ┌─────────────────────────────────────────────────────────────┐
        │  第 1.5 层:**proxy(NS-2/3 新增,独立进程)**                 │
        │                                                             │
        │  PROXY_ENABLED=true 时:vegeta → proxy:PORT → 节点          │
        │  PROXY_ENABLED=false 时(默认):vegeta → 节点(老模式)        │
        │                                                             │
        │  ┌──────────────────────────────────────────────────────┐  │
        │  │  proxy 进程(systemd unit / docker container)        │  │
        │  │  ┌────────────────────────────────────────────────┐ │  │
        │  │  │  config 来源:chain template proxy_extraction  │ │  │
        │  │  │  (Q4-2 单链启动,切链重启 proxy)              │ │  │
        │  │  └────────────────────────────────────────────────┘ │  │
        │  │  ┌────────────────────────────────────────────────┐ │  │
        │  │  │  declarative DSL 解析(Q4-4,4 种模式)         │ │  │
        │  │  │  - JSON body field(json_rpc / bitcoin_rpc)    │ │  │
        │  │  │  - URL path regex(rest)                       │ │  │
        │  │  │  - gRPC :method header(grpc)                  │ │  │
        │  │  └────────────────────────────────────────────────┘ │  │
        │  │  ┌────────────────────────────────────────────────┐ │  │
        │  │  │  转发请求 → 节点(透明 proxy)                  │ │  │
        │  │  │  记录 timestamp / method / latency / status   │ │  │
        │  │  │  → sink: proxy_method_*.jsonl(Q4-3 抽象)     │ │  │
        │  │  └────────────────────────────────────────────────┘ │  │
        │  └──────────────────────────────────────────────────────┘  │
        └─────────────────────────────────────────────────────────────┘
                                             │ 转发
                                             ▼
        ┌─────────────────────────────────────────────────────────────┐
        │  blockchain 节点(solana-validator / geth / ...)             │
        │  ─ proxy 与节点同机(Q4-1)                                  │
        │  ─ 节点 RPC 由 validator 单进程内部线程处理                  │
        │    cgroup 区分不到 method 粒度(本质约束)                    │
        └─────────────────────────────────────────────────────────────┘
                                             ▲
                                             │ 同机采集(节点 + proxy 自身)
                                             │
        ┌────────────────────────────────────│────────────────────────┐
        │  第 2 层:监控层(现有,Q4-6 不动) │                          │
        │  ┌──────────────────────────────────┴───────────────────┐  │
        │  │  unified_monitor.sh(节点级聚合,字段算账见 §4)      │  │
        │  │  → performance_*.csv                                 │  │
        │  └──────────────────────────────────────────────────────┘  │
        │  ┌──────────────────────────────────────────────────────┐  │
        │  │  bottleneck_detector.sh / cgroup_collector.py / ... │  │
        │  └──────────────────────────────────────────────────────┘  │
        └─────────────────────────────────────────────────────────────┘
                                             │
                                             ▼
        ┌─────────────────────────────────────────────────────────────┐
        │  第 3 层:分析层(现有 + NS-2 新增 join 逻辑)                │
        │  ┌──────────────────────────────────────────────────────┐  │
        │  │  现有:qps_analyzer / comprehensive_analysis /       │  │
        │  │       cpu_disk_correlation_analyzer / ...            │  │
        │  └──────────────────────────────────────────────────────┘  │
        │  ┌──────────────────────────────────────────────────────┐  │
        │  │  **NS-2 新增 per-method 归因(秒级 group_by)**      │  │
        │  │  输入:performance_*.csv + proxy_method_*.jsonl     │  │
        │  │  输出:per_method_resource_*.csv                    │  │
        │  │  算法:                                              │  │
        │  │   for 秒 t in performance.csv:                      │  │
        │  │     proxy[t] = group(proxy_jsonl, ts==t)            │  │
        │  │     for method m:                                   │  │
        │  │       weight = proxy[t].count[m] / proxy[t].total  │  │
        │  │       attributed[t,m] = perf[t].resource × weight   │  │
        │  └──────────────────────────────────────────────────────┘  │
        └─────────────────────────────────────────────────────────────┘
                                             │
                                             ▼
        ┌─────────────────────────────────────────────────────────────┐
        │  第 4 层:可视化层(现有 + NS-2 新增 method 级图表)          │
        │  ┌──────────────────────────────────────────────────────┐  │
        │  │  现有:节点级图表(见 architecture-overview-zh L295) │  │
        │  └──────────────────────────────────────────────────────┘  │
        │  ┌──────────────────────────────────────────────────────┐  │
        │  │  **NS-2 新增 method 级图表**(具体数量阶段 4 PoC 定)│  │
        │  │  ─ Per-method QPS / latency / success rate           │  │
        │  │  ─ Per-method CPU/MEM/EBS/Network attribution        │  │
        │  │  ─ Method × time heatmap                             │  │
        │  └──────────────────────────────────────────────────────┘  │
        │  ┌──────────────────────────────────────────────────────┐  │
        │  │  双语 HTML 报告(现有 + 引用 method 级章节)         │  │
        │  └──────────────────────────────────────────────────────┘  │
        └─────────────────────────────────────────────────────────────┘
```

---

## 3. 数据流时序

```
T0  ─ user_config.sh 设 BLOCKCHAIN_NODE + PROXY_ENABLED
T1  ─ config_loader.sh 读取 chain template(config/chains/${BLOCKCHAIN_NODE}.json)
T2  ─ proxy 启动(读 chain template proxy_extraction 字段,Q4-2 单链)
T3  ─ fetcher 抓 accounts.txt
T4  ─ target_generator 拼 targets.txt(mixed weight 按 chain template mixed_weighted)
T5  ─ unified_monitor 启动(节点级,Q4-6 schema 不动)
T6  ─ vegeta attack → proxy(若 PROXY_ENABLED)→ 节点
       ├─ vegeta 出 results.json(节点级 latency,现有)
       ├─ proxy 出 proxy_method_*.jsonl(method × ts × latency,新)
       └─ unified_monitor 出 performance_*.csv(节点级,现有)
T7  ─ 测试结束,vegeta + monitor + proxy 停
T8  ─ 分析层 per-method 归因
       └─ 秒级 join:performance_*.csv ⨝ proxy_method_*.jsonl
       → per_method_resource_*.csv
T9  ─ 可视化层出 method 级图表 + HTML 报告
```

---

## 4. 字段算账(P2-1 污染源修正,以代码实查为准)

**docs 历史写 73-79 字段**(README.md / monitoring-mechanism-zh / data-architecture-zh / architecture-overview-zh 多处),但实测代码已变。

**实测公式**(基于 `monitoring/unified_monitor.sh` L1920-1936 `generate_csv_header()`):

```
字段总数 = basic(10)
         + N_EBS_devices × 21   (iostat_collector.sh L126 注释明写 21 字段/设备)
         + network(10)
         + ENA(可选,默认 6,由 ENA_ALLOWANCE_FIELDS 数组定义)
         + overhead(2)          (monitoring_iops_per_sec + throughput_mibs_per_sec)
         + block_height(6)
         + qps(3)
         + cgroup(可选,19;CGROUP_COLLECTOR_ENABLED=true 时启用)
```

**典型场景**:

| 场景 | 字段数 |
|---|---|
| 最小(1 EBS / no ENA / no cgroup) | **52** |
| 1 EBS + ENA + cgroup | **77** |
| **2 EBS + ENA + cgroup(AWS 推荐)** | **98** |

**与 docs 历史"79"差距来源**:
- v1 公式:`10 + 2×21 + 10 + 6 + 2 + 6 + 3 = 79`(无 cgroup,EBS 21 字段)
- v1.4.5 新增 `cgroup_collector.py`(19 字段)未同步到 docs
- ENA 实际通过 `build_ena_header()` 动态生成(可变长,默认 6)
- 第 2 层"自监控 20 字段"是 `overhead_*.csv` 独立文件(`OVERHEAD_CSV_HEADER` in `system_config.sh`),**不在 performance.csv**;monitoring-mechanism-zh L186 "自监控指标(20 个字段)"是这个 — docs 没说清两者关系

**proxy 引入影响**:proxy 出独立的 `proxy_method_*.jsonl`,**不进 performance.csv**(Q4-6 monitor 不动),分析层 join。

**修正纪律**:本文档及后续 docs **不再写死字段数**,统一用公式 + 典型场景表。

---

## 5. 与现有 4 层架构的关系

NORTH-STAR W-4 渐进改造,**不重写、不并行 v2、不激进重写**。本架构在现有 4 层之间**插入第 1.5 层 proxy**,各层影响:

| 现有层 | 改动 | 范围 |
|---|---|---|
| **第 1 层 执行层** | `target_generator.sh` 支持 `mixed_weighted` chain template 字段 | 新增 if 分支,默认走老 mixed round-robin |
| **第 1.5 层 proxy** | **新增独立进程** | systemd/docker,默认关 |
| **第 2 层 监控层** | **不动**(Q4-6) | 维持节点级 schema |
| **第 3 层 分析层** | 新增 per-method 归因模块 | `analysis/per_method_attribution.py`(新文件) |
| **第 4 层 可视化层** | 新增 method 级图表生成器 | `visualization/per_method_charts.py`(新文件)+ 报告模板章节 |

**fetcher**(`tools/fetch_active_accounts.py`)**不在 proxy 路径上**,但 e2e 跑 benchmark 仍需 28 链扩展(OQ-6 + OQ-9,归阶段 5)。

---

## 6. 关键设计决策(锁定,引用 NORTH-STAR)

| ID | 决策 | 出处 |
|---|---|---|
| Q4-1 | proxy 独立进程(VM + GKE 通用,节点同机) | [NORTH-STAR](../NORTH-STAR.md) §3 |
| Q4-2 | proxy 按 chain template 单链启动,切链重启 | 同上 |
| Q4-3 | sink 默认 CSV/JSONL,sink 抽象层预留 OTel/Prom | 同上 |
| Q4-4 | chain template proxy_extraction = declarative DSL(4 模式),禁 lua/python | 同上 |
| Q4-5 | `PROXY_ENABLED` + `PROXY_URL` 显式环境变量,默认关 | 同上 |
| Q4-6 | unified_monitor 字段不动,proxy 独立数据源,分析层 join | 同上 |
| 归因算法 | 秒级 group_by(OQ-3 倾向 a,简单可解释) | [OPEN-QUESTIONS](./OPEN-QUESTIONS.md) OQ-3 |
| sink 默认格式 | JSONL(OQ-4 倾向,扩展性好) | OQ-4 |

---

## 7. 不在本架构范围内(范围边界,防走偏)

引用 [NORTH-STAR](../NORTH-STAR.md) §4 范围边界,本架构**明确不做**:

- ❌ OpenTelemetry / Prometheus / Grafana 实时 dashboard(sink 抽象预留接口,实现归生产阶段)
- ❌ 重写 user_config.sh / single mode 工作流
- ❌ 加 method 列到 unified_monitor CSV
- ❌ proxy 内嵌 lua / python snippet
- ❌ iptables redirect 实现透明 proxy
- ❌ 客户端时间窗切片做 per-method 归因
- ❌ proxy 自身做 method-level cgroup 资源切片
- ❌ MEM cache hit rate 的 per-method 归因

---

## 8. 阶段 4 PoC 验收标准(为 1-C migration 留接口)

**PoC 范围**:solana 1 链 / 1 节点 / a+b 全闭环(mixed weight + per-method 归因)

**验收**(为阶段 4 收尾时对照):

1. ✅ `config/chains/solana.json` 增加 `proxy_extraction` + `mixed_weighted` 字段,**无 Python 代码改动**
2. ✅ `PROXY_ENABLED=true` 跑通 vegeta → proxy → 节点,**vegeta success rate ≥ 99%**(proxy 开销 < 1% 误差)
3. ✅ `PROXY_ENABLED=false` 跑老模式(回归测试,确认 W-4 渐进改造)
4. ✅ `proxy_method_*.jsonl` 字段完整(timestamp / method / latency / status)
5. ✅ 分析层秒级 join 出 `per_method_resource_*.csv`,字段数 = monitor 资源维度 × method 数
6. ✅ HTML 报告含 method 级章节,每 method 至少 3 图(QPS / latency / 资源归因)
7. ✅ proxy 自身 CPU/MEM 在报告中**显式标注**(OQ-8 倾向 c,透明记录)
8. ✅ chain template "走偏 check list"(本文档 §7)无任何违规

**验收时**新增 ADR 记录 PoC 验证结果。

---

## 9. ADR 索引

无(本文档为初稿,所有决策来自 NORTH-STAR 锁定 + OPEN-QUESTIONS 当前倾向)。

阶段 1-A review 通过后,本文档结构 + 决策落定即视为 baseline,后续修改逐条新增 ADR。

---

**末**:本文档保持紧凑(目标 < 400 行)以保证可读性;后续若架构细节膨胀,
应**外移到 1-B(chain template spec)+ 1-C(migration)+ ADR**,本文档只保留架构总图 + 数据流 + 决策摘要。
英文版 `per-method-proxy-architecture.md` 推迟到中文版稳定后翻译。
