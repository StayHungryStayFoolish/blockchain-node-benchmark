# 调研: vegeta 是否区块链节点 RPC 压测的最优工具(2026-06-02)

> 用户问: 我们用 vegeta 压测, 它是区块链节点性能测试最好的工具么?
> 方法: 先代码实证框架对压测工具的真实需求, 再对比候选工具按需求打分, 给带推荐的结论。

## 1. 框架对压测工具的真实需求(代码实证)

`core/master_qps_executor.sh:798`: `vegeta attack -format=json -targets=$targets_file -rate=$qps -duration=${duration}s`

提炼出的硬需求:
| # | 需求 | 说明 | 代码出处 |
|---|---|---|---|
| N1 | **恒定 QPS 速率(开环/open-loop)** | 按固定 rate 发请求, 不等响应回来才发下一个(开环模型, 测节点在固定负载下的真实表现) | -rate=$qps |
| N2 | **多档 QPS 爬坡** | 不同 qps 档位反复跑, 找节点瓶颈拐点 | master_qps_executor 多 level |
| N3 | **每请求独立 HTTP body** | 每个 target 是不同的 RPC(不同 method/params), 不是同一请求重放 | -targets=file(每行一个 target) |
| N4 | **POST JSON + 自定义 header + GET 混合** | jsonrpc POST body / rest GET path, 6 family 形态各异 | target JSON {method,url,header,body} |
| N5 | **准确延迟分位(p50/p99)+ status 码分布** | 出 success_rate/latency 报告 | vegeta report |
| N6 | **能与 proxy 串联** | PROXY_ENABLED 时流量经 proxy(per-method 归因) | target url 指 proxy |
| N7 | **CLI + 文件驱动 + CSV/JSON 可解析输出** | bash 框架集成, 产物进分析层 | -format=json + report |

**关键: 区块链 RPC 压测的本质 = 大量【异构 HTTP 请求】按【固定速率】打节点, 测资源/延迟。这其实是通用 HTTP 压测问题, 不是区块链专用问题**(节点对外就是 HTTP JSON-RPC/REST 端点)。所以候选 = 通用 HTTP 压测工具为主。

## 2. 候选工具对比(按 N1-N7 需求)

| 工具 | N1开环 | N3每请求异构body | N5延迟分位 | CLI文件驱动 | 语言/部署 | 区块链适配 |
|---|---|---|---|---|---|---|
| **vegeta**(现状) | ✅ 原生开环(核心卖点) | ✅ -targets 文件每行独立 target | ✅ 精确 p50/p90/p99 | ✅ Go 单二进制, 文件驱动 | Go 单二进制零依赖 | 通用 HTTP, 已适配 |
| **k6**(Grafana) | ⚠️ 默认闭环(VU 模型), 需 constant-arrival-rate executor 才开环 | ✅ JS 脚本灵活构造 | ✅ 强 | ⚠️ JS 脚本驱动(非纯文件), 依赖 k6 runtime | Go 核心+JS 脚本 | 通用, 需写 JS |
| **wrk / wrk2** | wrk 闭环 / wrk2 开环(修正 coordinated omission) | ⚠️ Lua 脚本构造, 每请求异构较繁 | wrk2 ✅ | ⚠️ Lua 脚本 | C, 需编译 | 通用, Lua 门槛 |
| **bombardier** | ⚠️ 偏闭环连接数模型 | ❌ 单一请求体为主, 异构 body 弱 | ✅ | ✅ Go 单二进制 | Go | 不适合异构 RPC |
| **locust** | ⚠️ 闭环 user 模型 | ✅ Python 灵活 | ✅ | ❌ Python 脚本+web UI, 重 | Python | 通用, 重 |
| **ethspam + versus** | versus 开环 | ⚠️ ethspam 专造 EVM 随机请求 | versus ✅ | ✅ | Go | **仅 EVM 专用**, 不覆盖 36 链非 EVM |
| **tsung / jmeter** | 可配 | ✅ | ✅ | ❌ XML 配置重 | Erlang/Java | 通用但重, 集成成本高 |

## 3. 分析

### 3.1 vegeta 的核心优势恰好命中区块链压测需求
- **开环恒定速率(N1)是 vegeta 的设计核心** —— 这正是节点性能测试最需要的模型: "节点在持续 X QPS 下能否撑住", 而不是闭环"发完等回再发"(闭环会被慢响应自我限速, 掩盖真实瓶颈 = coordinated omission 问题)。多数闭环工具(wrk/bombardier/locust 默认)在这点上不如 vegeta。
- **-targets 文件每行独立 target(N3/N4)** —— 完美匹配"每个 RPC method 不同 body"的需求, 框架现在正是逐行生成异构 target。换成 k6/wrk 要写 JS/Lua 脚本动态构造, 反而更复杂、更易错。
- **Go 单二进制零依赖(N7)** —— bash 框架集成最省心, 无 runtime 依赖(对比 k6 需 JS runtime、locust 需 Python 环境、jmeter 需 JVM)。

### 3.2 vegeta 的已知局限(诚实列出)
- **超高 QPS(>50k)单机受限**: vegeta 单进程在极高 QPS 下精度下降(skill poc-minimal-go-proxy 记载过 ticker 精度问题, 但那是自研 mock 不是 vegeta 本身)。区块链节点单点 QPS 通常远低于此(节点本身是瓶颈), 不构成实际限制。
- **无分布式原生支持**: 超大规模需多机 vegeta 手动协调。区块链单节点压测用不到。
- **不解析响应内容**: 但这正符合 NS-2(压测不需要响应业务内容, §5.0 已确认)。

### 3.3 区块链"专用"工具的真相
- ethspam+versus 等区块链专用工具**只覆盖 EVM**, 本框架要 36 链 6 family(含 solana/cosmos/substrate/bitcoin/...), 专用工具反而覆盖不全。
- 区块链节点对外 = HTTP JSON-RPC/REST 端点, 压测本质是通用 HTTP 异构请求开环压测 —— **通用工具 + 框架自己的 target 构造(adapter/DSL)才是正解**, 这也正是本框架的架构。

## 4. 结论(带推荐)

**推荐: 保留 vegeta, 不换。** 理由:
1. vegeta 的开环恒定速率(N1)+ 文件驱动异构 target(N3/N4)+ Go 零依赖(N7)精确命中区块链节点压测的真实需求, 在候选里综合最优。
2. 区块链"专用"工具(ethspam/versus)只覆盖 EVM, 不满足 36 链 6 family。
3. 换工具(k6/wrk)= 把"文件驱动异构 target"改成"脚本动态构造", 增加复杂度和出错面, 且要重做框架集成层 —— 与本次重构"不留债/链不断"目标冲突, 收益不明。
4. vegeta 的局限(超高 QPS/分布式)在区块链单节点压测场景不构成实际约束。

**唯一值得保留的撤销线**: 若未来出现"单节点需 >50k QPS 持续压测"或"需多机分布式协调"的需求, 再评估 k6 分布式 / 自研 Go 压测器。当前 PoC + 单节点性能画像场景, vegeta 是正确选择。

**对本次重构的影响**: 压测发生器层**不动**(vegeta 保留), 重构聚焦输入池 + 参数 DSL + 协议修复。vegeta target 文件格式(adapter 产出的 {method,url,header,body})是稳定契约, DSL 重构只改"如何生成 target body", 不改 vegeta 本身。这反而简化了重构范围。
