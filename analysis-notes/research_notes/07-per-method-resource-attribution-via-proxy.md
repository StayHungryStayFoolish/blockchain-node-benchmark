# Per-Method 资源归因 via Proxy:机制调研 + 收敛决策

> **范围**:本调研档为 NORTH-STAR NS-2(method 维度资源归因)提供**实施机制证据**,收敛 `OPEN-QUESTIONS.md` 中 OQ-1 / OQ-3 / OQ-4 / OQ-8 的"倾向意见"→ 锁定决策。
> **不在范围**:OQ-2 部署细节归 1-A;OQ-5 DSL spec 归 1-B;OQ-6 fetcher 边界归 1-C;OQ-7 weight schema 归 1-B。
> **方法论**:对 OPEN-QUESTIONS 已有的"当前倾向",补足 (a) 反方论证 (b) ground truth 验证方案 (c) PoC 撤销条件 (d) 风险登记。
> **完成日期**:2026-05-27
> **配套文档**:[NORTH-STAR.md](../../docs/NORTH-STAR.md) / [1-A per-method-proxy-architecture-zh.md](../../docs/architecture/per-method-proxy-architecture-zh.md) / [OPEN-QUESTIONS.md](../../docs/architecture/OPEN-QUESTIONS.md) / [monitoring-mechanism-zh.md](../../docs/monitoring-mechanism-zh.md)

---

## 1. 问题定义

### 1.1 NS-2 的核心矛盾

NORTH-STAR NS-2 要求:**按 method 维度归因节点端系统资源消耗**(CPU / MEM / EBS / Network 等;具体字段数以 `monitoring-mechanism-zh.md` 第 1 层 主监控章节实查为准 — 第 1 章 CPU 6 字段 / 内存 3 字段 / EBS 双盘 42 字段 / 网络 10 字段 / ENA 6 字段 / 区块高度 6 字段 / QPS 3 字段)。

但**单看 unified monitor CSV 不够**:

- 每行 = 时间戳 + 节点级聚合资源(CPU% / mem_used_mb / iops / bandwidth_mbps...)
- **无 method 维度** — 节点端 RPC 由 validator 单进程内部线程处理,无法在节点端区分 "这秒钟 CPU 涨的是 eth_call 还是 eth_blockNumber"

### 1.2 §4 已排除的 3 种"看似显然"方案

NORTH-STAR §4(范围边界)已锁定**不做**以下方案,本调研不再讨论可行性,仅复述排除原因:

| 方案 | 排除原因(§4) |
|---|---|
| 客户端时窗切片(60s 只发 method A → 60s 只发 method B) | 破坏 mixed 真实业务负载模拟,违 NS-2 本质 |
| proxy 自身做 method-level cgroup 资源切片 | RPC 由 validator 单进程内部线程处理,cgroup 区分不到 method |
| 加 method 列到 unified monitor CSV | 违 Q4-6 不动现有 monitor 字段,破坏 schema |
| MEM cache hit rate 的 per-method 归因 | 状态量(非流量量),难以按时间窗分摊,确认可舍弃 |

### 1.3 本仓库已锁机制:proxy 时序 + monitor 时序 join

NORTH-STAR §3 Q4-1 ~ Q4-6 已锁:**proxy 独立进程**(Q4-1)、**按 chain template 单链启动**(Q4-2)、**默认 CSV/JSONL sink**(Q4-3)、**完全 declarative DSL**(Q4-4)、**默认关闭,显式 PROXY_ENABLED**(Q4-5)、**monitor 字段不动**(Q4-6)。

剩余决策点 = **归因算法 + proxy 选型 + sink 格式 + proxy 自身开销处理** = 本调研稿收敛对象。

---

## 2. 归因算法收敛(OQ-3)

### 2.1 OPEN-QUESTIONS 当前倾向

**(a) 简单 group_by + 秒级时间窗**(优于 (b) 加权回归 / (c) 蒙特卡洛)

理由来自用户原话(2026-05-27):"运维人员看 rpc method 相关的资源图可以快速理解,获取到运维人员希望获取的数据就可以"。

### 2.2 反方论证(为什么 (a) 可能不够)

| 反方论点 | 严重度 | 应对 |
|---|---|---|
| **R1**: (a) 假设资源与请求数线性,heavy method 如 `eth_call` / `debug_traceTransaction` 会被低估 | 中 | 通过 method 权重表(由 01-06 研究档资源画像产出)做加权 group_by,而不是纯计数 |
| **R2**: 秒级窗口内 method 混合时,归因边界模糊(无法区分"100 次 eth_blockNumber + 1 次 debug_trace" vs "200 次 eth_blockNumber") | 高 | PoC 阶段用 ground truth 比对(§2.4),如果误差 > 20%,升级 (b) 或加权 |
| **R3**: 节点 GC / cache miss / 后台 compaction 与 method 无关,但会污染归因 | 中 | 通过引入"基线噪声窗口"(无 vegeta 压力期间的资源消耗)作为减项 |
| **R4**: solana 等链有 `getMultipleAccounts` 这种"单请求多账户"的非线性,纯计数归因失真 | 中(solana 特定) | PoC solana 阶段必须验证;失真严重则在 chain template 加 `request_weight` 字段 |

### 2.3 推荐决策:**(a) + 方法权重表**

**最终算法**:`per_method_resource_share(method, t) = sum(method.weight * count) / sum(all_methods.weight * count) * delta_resource(t)`

- `method.weight` 来自 01-06 研究档已有的资源画像(eth_call=10, eth_blockNumber=1, debug_trace=100 等)
- `delta_resource(t)` 来自 unified monitor CSV 时间窗内的资源增量
- PoC 阶段 weight 用粗粒度(1/10/100 三档),v2 视情况细化

### 2.4 Ground Truth 验证方案(PoC 必跑)

**不验证 = 不锁定。** PoC solana 阶段必须做以下"双对照"实验:

| 实验组 | vegeta 配置 | 验证目标 |
|---|---|---|
| **对照组 A**:单 method 压测 | 60s 纯 `getBalance` × 5 个 method × 5 轮 | 取每 method 单独压测下的真实资源消耗作为 ground truth |
| **实验组 B**:mixed 模式 + 已知权重 | weight=[getBalance:40, getBlock:30, getAccountInfo:20, getSlot:10] | 用算法 (a) 归因,与对照组 A 数据加权求和比对 |
| **撤销条件** | 误差 > 20% / 任意 method 归因方向反(给高资源 method 算出低消耗) | 升级到 (b) 加权回归或重新设计 |

### 2.5 OQ-3 锁定建议

→ 推荐合入 NORTH-STAR §3:**Q4-7: per-method 归因算法 = 加权 group_by(秒级时间窗),权重表来自 method 资源画像研究档 01-06**

---

## 3. proxy 选型收敛(OQ-1)

### 3.1 OPEN-QUESTIONS 当前倾向

**自写 Go 小代理**(优于 envoy / nginx / mitmproxy / Caddy)

理由:NS-3 零代码加链原则下,只有自写 + declarative 设计能完全满足;envoy/nginx 都需要为新协议写一次性 filter,违反 NS-3。

### 3.2 反方论证(为什么不立刻锁"自写 Go")

| 反方论点 | 严重度 | 应对 |
|---|---|---|
| **R5**: 自写代理引入维护成本,小团队不可持续 | 高 | 严格控制规模 < 800 行,只做最小集:HTTP/2 + JSON-RPC body 解析 + URL path 正则 + gRPC :method header + 写日志。**不做** retry / circuit breaker / TLS termination(直接代理) |
| **R6**: envoy 配置 + Lua 一次性 filter 也能 declarative,只是 DSL 不在 chain template 里 | 中 | 反驳:Lua filter 是 envoy YAML 外挂代码,违 NS-3"零代码"(每加 1 链改 1 个 Lua)。**自写 Go + chain template DSL** 是唯一让"加链 = 改 JSON"的方案 |
| **R7**: gRPC 链(hedera mirror)的 :method 提取在 envoy 上零成本(原生 metadata filter) | 中(gRPC 特定) | 自写 Go 需引入 `golang.org/x/net/http2` 解析 HEADERS frame,可控但工作量 +2 天 |
| **R8**: 自写代理性能可能撑不住 vegeta 高 QPS | 高 | PoC 阶段验:目标 ≥ 10k QPS @ p99 < 5ms(本机 loopback);不达标则切 envoy + Lua 兜底 |

### 3.3 推荐决策:**自写 Go,但 PoC 必跑性能基线 + envoy 兜底方案保留**

- **主方案**:自写 Go(~500-800 行),严格 declarative,从 chain template 读 `proxy_extraction` 字段
- **兜底方案**:envoy + per-链 Lua filter(违 NS-3 但保证可用),仅在主方案 PoC 失败时启用
- **撤销条件**:PoC solana 性能 < 5k QPS @ p99 < 10ms,或 declarative DSL 无法覆盖 36 链 ≥ 32 链 → 启用兜底

### 3.4 选型矩阵(36 链协议覆盖测试)

DSL 4 模式(json_rpc / rest / bitcoin_rpc / grpc)覆盖测试 — 需在阶段 1-B `chain-template-zero-code-spec-zh.md` 完成时填:

| 协议 | 实测 adapter family | 链数 | DSL 覆盖度 | 风险 |
|---|---|---|---|---|
| json_rpc | `jsonrpc` | 16+ | ✓ body.method | 低 |
| bitcoin_rpc | `bitcoin_jsonrpc` | 2(BTC + 衍生) | ✓ 同 json_rpc | 低 |
| rest | `rest` | 4-6 | ✓ url_pattern + regex | 中(每链 regex 不同) |
| grpc | `hedera_dual` 部分 | 1-2 | ⚠️ 需 HEADERS frame 解析 | 高 |
| 自有协议(ogmios / substrate / tendermint) | `ogmios` / `substrate` / `tendermint` | 5-8 | ⚠️ 需逐协议确认 | 高 |

**待 1-B 完成 36 链 proxy_extraction 填表后**,本表更新真实覆盖率。

### 3.5 OQ-1 锁定建议

→ 推荐合入 NORTH-STAR §3:**Q4-8: proxy 选型 = 自写 Go 小代理(主方案),envoy + Lua 兜底(仅 PoC 失败时启用)**

---

## 4. sink 格式收敛(OQ-4)

### 4.1 OPEN-QUESTIONS 当前倾向

**CSV**(与现有 unified_monitor CSV 一致,pandas join 简单)

### 4.2 反方论证

| 反方论点 | 严重度 | 应对 |
|---|---|---|
| **R9**: CSV 不能表达嵌套 params(eth_call 的 data 字段) | 中 | 嵌套字段不归 proxy 责任,只记 method/timestamp/req_bytes/resp_bytes/latency_ms/status;复杂分析归离线脚本 |
| **R10**: JSONL 更利于未来加字段(向前兼容) | 低 | CSV 加列也兼容(分析层 pandas read 自动适配),且 JSONL 体积大 30%+ |
| **R11**: 高 QPS 下 CSV 文件巨大(10k QPS × 30min = 18M 行) | 中 | 默认按小时切割 + gzip,分析时按需 load |
| **R12**: Parquet 性能远超 CSV 但学习成本高 | 低 | PoC 阶段 CSV 够用;v2 视分析瓶颈再切 Parquet |

### 4.3 推荐决策:**默认 CSV,sink 抽象层预留 JSONL/Parquet 切换**

- 默认 = CSV(运维熟悉,与 unified monitor 一致,pandas 友好)
- sink 抽象层(已锁 Q4-3)预留 JSONL / Parquet 切换,环境变量 `PROXY_SINK_FORMAT={csv|jsonl|parquet}`
- 字段最小集:`timestamp,method,req_bytes,resp_bytes,latency_ms,status`(6 字段固定,不带 params/body)

### 4.4 OQ-4 锁定建议

→ 推荐合入 NORTH-STAR §3:**Q4-9: sink 默认 CSV + 字段最小集 6 列;sink 抽象层支持 JSONL/Parquet 切换**

---

## 5. proxy 自身资源开销处理(OQ-8)

### 5.1 OPEN-QUESTIONS 当前倾向

**(c) 不排除,记录 proxy 开销,在报告中说明** + 可选 (a) cgroup 隔离

### 5.2 反方论证

| 反方论点 | 严重度 | 应对 |
|---|---|---|
| **R13**: proxy 占了 5% CPU 也算在节点头上,会让 method 归因偏高 | 中 | 加"proxy 自报基线"(每秒自报 self CPU%/mem),分析层从节点级数据减去 |
| **R14**: cgroup 隔离 (a) 在 GKE pod 内难做(pod 已是 cgroup) | 中(GKE 特定) | GKE 场景用 sidecar pattern,proxy 独立 pod,资源完全隔离;不依赖 cgroup |
| **R15**: 自报基线不准(proxy 进程 CPU/MEM 与 RPC 处理 CPU/MEM 量纲不同) | 低 | PoC 阶段做对照实验:无 proxy / 有 proxy 但不打 vegeta,差值 = proxy 净开销 |

### 5.3 推荐决策:**(c) 透明记录 + 自报基线;(a) cgroup 留 K8s sidecar 形态**

- **PoC**:proxy 每秒自报 `proxy_self_cpu_pct` / `proxy_self_mem_mb`,写入独立 `proxy_self.csv`
- **分析层**:节点级 CPU/MEM - proxy_self 基线 = 真实 validator 资源 → 再归因到 method
- **K8s 生产**:proxy 独立 pod,资源天然隔离,不需要减基线
- **撤销条件**:proxy 自身 CPU > 节点 CPU 的 10%,或 proxy 自报与实测偏差 > 30% → 必须做 cgroup 隔离

### 5.4 OQ-8 锁定建议

→ 推荐合入 NORTH-STAR §3:**Q4-10: proxy 开销默认透明记录 + 自报基线;K8s 生产用 sidecar 隔离**

---

## 6. 数据流完整视图(归因如何实施)

```
                  vegeta(打压客户端)
                          │  HTTP/gRPC
                          ▼
              ┌───────────────────────┐
              │   proxy (自写 Go)      │── proxy_log.csv(timestamp, method,
              │   - declarative DSL    │              req_bytes, resp_bytes,
              │   - 解 method/URL/grpc │              latency_ms, status)
              │   - 透传 → validator   │
              │   - 自报 → proxy_self  │── proxy_self.csv(timestamp,
              └───────────────────────┘              cpu_pct, mem_mb)
                          │
                          ▼
                  validator(被测节点)
                          │
              ┌───────────────────────┐
              │  unified_monitor 已有  │── unified.csv(timestamp,
              │  (字段以 monitoring-   │              cpu_6字段, mem_3字段,
              │   mechanism-zh.md      │              ebs_42字段, net_10字段,
              │   实查为准)            │              ena_6字段, ...)
              └───────────────────────┘

                          │  (离线分析阶段)
                          ▼
              ┌───────────────────────┐
              │ 时序 JOIN(秒级窗口)    │
              │ + 减 proxy 基线        │
              │ + 加权 group_by 归因    │
              └───────────────────────┘
                          │
                          ▼
              method 级资源消耗图 + 双语 HTML 报告
```

**关键点**:proxy 与 monitor **独立采集,独立持久化,分析层 join** — 这让 proxy 故障不会阻塞 monitor,monitor schema 不会被破坏(对齐 Q4-6)。

---

## 7. PoC 验证矩阵(阶段 4 必跑)

PoC 选 solana(NORTH-STAR §3 路线已定),以下 8 条硬验收(对齐 1-C `migration-from-legacy-zh.md` 8 条 PoC 验收):

| # | 验收项 | 失败 → 撤销条件 |
|---|---|---|
| 1 | proxy 启动 + chain template 加载 + 解 solana getBalance / getBlock / getAccountInfo / getSlot 4 method | 解不出 → §3.4 矩阵失败,选型重审 |
| 2 | proxy 透传 vegeta → solana 节点 → 响应原路返回(0 包丢失) | 丢包 → 代理实现缺陷,不进归因阶段 |
| 3 | proxy_log.csv 写盘 ≥ 10k QPS 不丢日志(异步 + 缓冲) | 丢日志 → 升级 sink 写入策略 |
| 4 | proxy 性能基线:p99 < 5ms @ 10k QPS @ 本机 loopback | 不达标 → §3.3 启用 envoy 兜底 |
| 5 | proxy_self.csv CPU%/MEM 与 `top`/`ps` 实测偏差 < 20% | 偏差大 → §5.3 启用 cgroup 隔离 |
| 6 | **算法 (a) ground truth 比对**(§2.4)误差 < 20% | 误差大 → §2.5 升级 (b) 加权回归 |
| 7 | 离线分析脚本输出 method 级资源图(CPU/MEM/IOPS 至少 3 张) | 图出不来 → 分析层缺陷,不进 1-A 闭环 |
| 8 | 双语 HTML 报告引用 method 级图 + proxy 开销说明 | 报告缺图/缺说明 → 不算 NS-2 闭环 |

---

## 8. 风险与不确定性登记

| ID | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| K1 | 自写 Go proxy 性能不达标 → 切 envoy → DSL 失效 → 36 链需逐链写 Lua | 中 | 高(违 NS-3) | §3.3 envoy 兜底接受"违 NS-3 但保证可用",并在 README 显式标 KNOWN_BROKEN_PROXY |
| K2 | gRPC 链(hedera)HEADERS frame 解析复杂度爆炸 | 中 | 中 | PoC 仅做 solana(json_rpc),gRPC 链推到阶段 5 W7 殿后 |
| K3 | 归因算法 (a) 误差大于 20% → 升级 (b) 需大样本 → PoC 周期翻倍 | 中 | 中 | PoC 设短路:误差 20%-50% 内接受 "PoC 可视化能用,精度 v2 提升";> 50% 才升级 (b) |
| K4 | proxy 在生产 K8s 集群 sidecar 形态与 PoC VM systemd 形态资源占用差异大 | 高 | 中 | PoC 不验生产形态,生产形态留阶段 5 增量验;PoC 报告显式说"PoC 数据仅代表 VM systemd 形态" |
| K5 | 36 链 chain template `proxy_extraction` 填表过程发现 DSL 4 模式不够 | 中 | 高(违 NS-3) | 1-B 阶段提前填 36 链试验,DSL 扩 5/6 模式可接受;无法表达的链标 KNOWN_BROKEN_PROXY 不阻塞 |
| K6 | proxy 故障导致 vegeta 压不到节点,影响整个 benchmark | 高 | 高 | Q4-5 已锁 `PROXY_ENABLED` 默认关闭;proxy 启用前必跑健康检查(curl proxy 自身的 /health 端点);失败立即 fail-fast |

---

## 9. 决策汇总(给 NORTH-STAR §3 / ADR 喂)

本调研稿收敛产出 4 条决策,建议合入 NORTH-STAR §3 + 各写 ADR:

| 决策 ID | 内容 | 对应 OQ | 撤销条件(PoC 阶段验) |
|---|---|---|---|
| Q4-7 | per-method 归因 = 加权 group_by(秒级窗口),权重来自 01-06 资源画像 | OQ-3 | §2.4 误差 > 20% |
| Q4-8 | proxy = 自写 Go 小代理(主),envoy + Lua 兜底(failback) | OQ-1 | §3.3 性能不达标 or DSL < 32 链 |
| Q4-9 | sink 默认 CSV + 字段最小集 6 列;抽象层支持 JSONL/Parquet | OQ-4 | 无强撤销,体积超 100GB/天再讨论 |
| Q4-10 | proxy 开销默认透明记录 + 自报基线;K8s 用 sidecar 隔离 | OQ-8 | §5.3 proxy CPU > 节点 10% |

---

## 10. 引用与依赖

- **上游 SSOT**:`docs/NORTH-STAR.md` §1 NS-1/2/3 / §3 Q4-1~6 / §4 范围边界 / §7 阶段路线
- **同期架构文档**:`docs/architecture/per-method-proxy-architecture-zh.md` (1-A) / `chain-template-zero-code-spec-zh.md` (1-B) / `migration-from-legacy-zh.md` (1-C)
- **待决项 → 本档收敛**:`docs/architecture/OPEN-QUESTIONS.md` OQ-1 / OQ-3 / OQ-4 / OQ-8
- **同系列研究档(权重表来源)**:`analysis-notes/research_notes/01-evm-rpc-resource.md` / `02-solana-sui-aptos-rpc-resource.md` / `03-bitcoin-starknet-rpc-resource.md` / `03b-evm-l2-rpc-resource.md` / `04-evm-complex-params.md` / `05-multichain-complex-params.md` / `06-fixture-pool-engineering.md`
- **现状字段实查**:`docs/monitoring-mechanism-zh.md` 第 1 层 主监控章节(CPU/MEM/EBS/Net/ENA/区块/QPS 字段数以该文档实查为准)
- **代码现状**:`tools/chain_adapters/base.py` 7 族 register / `tools/fetch_active_accounts.py` L661 create_adapter + L677 fetch_all_signatures / `blockchain_node_benchmark.sh` 真入口

---

**末**:本调研稿为阶段 2 收敛产物,后续:
1. 用户 review 后,4 条决策合入 NORTH-STAR §3,从 OPEN-QUESTIONS 移除 OQ-1/3/4/8
2. 写 4 份 ADR(`docs/architecture/decisions/0001-0004-*.md`)
3. 阶段 3 沉淀 skill `blockchain-node-benchmark-architecture` 锁北极星
4. 阶段 4 PoC solana,严格按 §7 验收矩阵
