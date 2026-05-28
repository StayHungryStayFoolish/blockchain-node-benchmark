# OPEN-QUESTIONS — 待决项追踪

> **状态**:跟踪中(随研究推进更新答案)
> **作用**:记录已识别但**尚未决策**的设计选项,避免在 session 中重复发散。
> 每个决策落定后,从本文档移除并**同步到 NORTH-STAR.md 决策表 + 写 ADR**。

---

## OQ-1:proxy 具体选型 ✅ 已锁定(2026-05-27)

> **状态**:已锁定,合入 NORTH-STAR §3 **Q4-8**。
> **决策摘要**:**自写 Go 小代理(主方案)**,严格 declarative DSL,目标 ≤ 800 行;**envoy + Lua 兜底(failback)**仅在主方案 PoC 失败时启用。
> **PoC 撤销条件**:性能 < 5k QPS @ p99 < 10ms,或 DSL 覆盖 < 32/36 链 → 启用 envoy + Lua 兜底(接受违 NS-3 但保证可用)。
> **决策依据**:NS-3 零代码加链原则下,只有"自写 Go + chain template DSL"能完全满足"加链 = 改 JSON";envoy/nginx 需要为新协议写一次性 Lua filter,违 NS-3。完整反方论证见 `analysis-notes/research_notes/07-per-method-resource-attribution-via-proxy.md` §3。
> **ADR 待写**:`docs/architecture/decisions/0002-proxy-implementation.md`(归阶段 4 PoC 启动前补)

---

## OQ-2:proxy 部署形态细节 ✅ 已锁定(2026-05-28)

> **状态**:已锁定,合入 NORTH-STAR §3 **Q4-11**。
> **决策摘要**:**systemd + docker 双部署**(同一 Go 二进制),虚拟机/cloudtop 走 systemd unit,跨平台开发/CI 走 docker container;**PoC 阶段允许裸跑**(`./proxy &`);K8s 生产形态走 sidecar(Q4-10 已定)。
> **决策依据**:运维场景全覆盖 + 跨平台兼容 + PoC 阻力最小化。
> **ADR 待写**:`docs/architecture/decisions/0005-proxy-deployment.md`(归阶段 4 PoC 启动前补)

---

## OQ-3:per-method 归因算法 ✅ 已锁定(2026-05-27)

> **状态**:已锁定,合入 NORTH-STAR §3 **Q4-7**。
> **决策摘要**:加权 group_by(秒级时间窗);权重源 = 公开资料先配粗粒度(`analysis-notes/research_notes/01-06` 各 method "典型延迟量级" → 映射 1/10/100 三档);后期实际使用根据真实压测数据迭代调整;PoC 撤销条件 = ground truth 误差 > 20% 才升级 (b) 加权回归。
> **决策依据**:用户原话 "运维人员看 rpc method 相关的资源图可以快速理解" + 收敛于 `analysis-notes/research_notes/07-per-method-resource-attribution-via-proxy.md` §2。
> **ADR 待写**:`docs/architecture/decisions/0001-per-method-attribution.md`(归阶段 4 PoC 启动前补)

---

## OQ-4:sink 默认格式 ✅ 已锁定(2026-05-27)

> **状态**:已锁定,合入 NORTH-STAR §3 **Q4-9**。
> **决策摘要**:**默认 CSV** + 字段最小集 6 列(`timestamp, method, req_bytes, resp_bytes, latency_ms, status`);sink 抽象层支持 JSONL/Parquet 切换(环境变量 `PROXY_SINK_FORMAT`)。
> **关键变化**:初始倾向是 JSONL(理由:扩展性),但 07 调研档 §4 反方论证 R9-R12 把倾向翻成 CSV — (R9) 嵌套字段不归 proxy 责任,(R10) CSV 加列也兼容 + JSONL 体积大 30%,(R11) 高 QPS 下文件体积压力,(R12) Parquet 学习成本高。**决策准则**:与 unified_monitor CSV 一致,pandas 友好,运维熟悉。
> **撤销条件**:无强撤销条件,日志体积 > 100GB/天再评估切 Parquet。
> **决策依据**:`analysis-notes/research_notes/07-per-method-resource-attribution-via-proxy.md` §4。
> **ADR 待写**:`docs/architecture/decisions/0003-sink-format.md`(归阶段 4 PoC 启动前补)

---

## OQ-5:chain template proxy_extraction DSL 完整 spec ✅ 已锁定(2026-05-28)

> **状态**:已锁定,合入 NORTH-STAR §3 **Q4-12**,完整 schema 落 `chain-template-zero-code-spec-zh.md` §1.7。
> **决策摘要**:**2 模式(json_rpc + rest)+ `extractors:[]` 数组 + `batch_handling` 必填 + `auth` 可选**;100% 覆盖 36 链(jsonrpc/substrate/tendermint/bitcoin_jsonrpc 统一走 json_rpc,rest 走 rest,hedera dual 用 2 条 extractor 自然支持);**删 grpc 模式(36 链零 gRPC,YAGNI)+ 删 ogmios 模式(cardano 实测走 rest)**。
> **关键变化**:初稿 4 模式(json_rpc / rest / bitcoin_rpc / grpc)经 6 family × 36 链对照实证后,有 2 BLOCKER(ogmios WS / hedera dual);改 2 模式 + extractors 数组 + url_patterns list + batch_handling 必填 后 0 BLOCKER 0 envoy 兜底。
> **6 family 范例**:arbitrum (jsonrpc) / bch (bitcoin_jsonrpc) / acala (substrate) / algorand (rest) / celestia (tendermint) / hedera (hedera_dual) — 全部覆盖,见 spec §1.7。
> **决策依据**:36 链 6 family 实证分布(`_meta.adapter_family` audit:jsonrpc=16, rest=5, substrate=5, tendermint=5, bitcoin_jsonrpc=4, hedera_dual=1, ogmios=0);batch_handling 来自 EVM batch JSON-RPC 真实生产场景。
> **ADR 待写**:`docs/architecture/decisions/0006-proxy-extraction-dsl.md`(归阶段 4 PoC 启动前补)

---

## OQ-6:proxy 与 fetcher 的边界 ✅ 已锁定(2026-05-28)

> **状态**:已锁定,合入 NORTH-STAR §3 **Q4-13**。
> **决策摘要**:**proxy 与 fetcher 解耦** — proxy 只解 body / URL 抓 method 名,不依赖 fetcher;fetcher 28 链扩展归阶段 5 wave(非 S4 blocker);PoC solana 1 链 fetcher 已支持;e2e benchmark 链路 = fetcher → target_generator → vegeta → proxy → 节点。
> **决策依据**:proxy 工作在 vegeta → 节点链路的中间层,只关心 wire format(body / URL),与 fetcher 取地址池逻辑完全正交;fetcher 28 链扩展是独立工作量,塞进 S4 会拖延 NS-2 主线。
> **ADR 待写**:`docs/architecture/decisions/0007-proxy-fetcher-boundary.md`(归阶段 4 PoC 启动前补)

---

## OQ-7:weight 配置的 chain template schema ✅ 已锁定(2026-05-28)

> **状态**:已锁定,合入 NORTH-STAR §3 **Q4-14**,完整 schema 落 `chain-template-zero-code-spec-zh.md` §1.8。
> **决策摘要**:**候选 B(新增 `rpc_methods.mixed_weighted: [{method, weight}, ...]` 字段,向后兼容)**:旧 `mixed` 字符串字段保留,新增 `mixed_weighted` 时优先生效;weight 为正整数,target_generator 按 `weight_i / sum(weights)` 归一化;权重源参考 `analysis-notes/research_notes/01-06`。
> **决策依据**:候选 A(扩展 mixed 字符串)语法不易扩展;候选 C(完全替代)破坏老用户配置;候选 B 兼容 + 显式,符合 W-4 渐进重构。
> **验证手段**:pre-commit hook 校验 `mixed_weighted[].method` ⊂ `param_formats` keys + weight > 0 + integer。
> **ADR 待写**:`docs/architecture/decisions/0008-mixed-weighted-schema.md`(归阶段 4 PoC 启动前补)

---

## OQ-8:proxy 自身资源消耗如何排除? ✅ 已锁定(2026-05-27)

> **状态**:已锁定,合入 NORTH-STAR §3 **Q4-10**。
> **决策摘要**:**默认透明记录 + 自报基线**(`proxy_self.csv`:每秒自报 cpu_pct / mem_mb);分析层从节点资源减去基线后再归因 method;K8s 生产用 sidecar 独立 pod 隔离。
> **PoC 撤销条件**:proxy CPU > 节点 10% 或自报偏差 > 30% → 必须启用 cgroup 隔离。
> **决策依据**:候选 (c) 透明 + 自报基线兼顾"运维知情"与"实施简单";(a) cgroup 隔离在 GKE pod 内难做,K8s 直接走 sidecar 形态更自然。完整反方论证见 `analysis-notes/research_notes/07-per-method-resource-attribution-via-proxy.md` §5。
> **ADR 待写**:`docs/architecture/decisions/0004-proxy-overhead.md`(归阶段 4 PoC 启动前补)

---

## OQ-9:fake-node v2 — 5 个 stub handler 何时落地?

**背景**(2026-05-27, R1 范式纠正):fake-node v2 实现了 7 个协议族的 handler 注册 + dispatch 架构,但 R1 只完整实现 2/7 (jsonrpc + bitcoin_jsonrpc, 覆盖 20/36 链),剩余 5/7 注册为 `NotImplementedHandler` stub (覆盖 16/36 链 startup,RPC 调用返回 loud error)。

**待决问题**:5 个 stub handler 的实施时点与顺序。

| Handler            | Chains | Coverage 链名                                   | 实施成本 (估)        | 触发优先级     |
|--------------------|-------:|-------------------------------------------------|----------------------|----------------|
| `substrate`        | 5      | polkadot, kusama, acala, astar, moonbeam        | ~250 行 Go + 5 fixtures | 中 (有商用流量) |
| `tendermint`       | 5      | cosmos-hub, osmosis, celestia, injective, sei   | ~300 行 Go + 5 fixtures | 中             |
| `rest`             | 4      | algorand, aptos, tezos, ton                     | ~200 行 Go + 4 fixtures | 低             |
| `ogmios`           | 1      | cardano                                         | ~200 行 Go (websocket fixture replay) | 低 |
| `hedera_dual`      | 1      | hedera                                          | ~250 行 Go (双协议)  | 低             |

**当前倾向**:**按"商用使用率从高到低"实施**,而非按字母序。下一波:`substrate + tendermint`(5+5=10 链,商用流量大),再 `rest`,最后 `ogmios + hedera_dual` (各 1 链)。

**安全网**:stub 已注册不静默失败 (smoke step 4 验过 cardano: HTTP 404, NOT 200)。R1 完成 = "20 链可 smoke + 36 链可 startup + 16 链 RPC 必失败有响"。

**决策时点**:阶段 5 (36 链 weight + proxy 协议 dispatcher 全覆盖) 启动前必须给出实施顺序;`no-deferred-bugs` 4th 已检查过 (这是范围切分非 P0 推后)。

---

## OQ-10:fake-node fixture 录制流水线如何标准化?

**背景**:R1 ethereum fixtures 当前是手写最小合法 JSON-RPC 响应 (字节假但格式真),非真 mainnet 录制。Solana fixtures 用 `scripts/record_solana_fixtures.sh` 录的,但 EVM/其他链没有等价脚本。

**候选**:

| 选项 | 描述 | 利 | 弊 |
|---|---|---|---|
| (a) per-chain 手写 record_<chain>.sh | 复用 solana 模式 | 简单, 各链独立 | 36 个脚本维护成本 |
| (b) 统一 `record_fixtures.py` + `config/chains/*.json:rpc_methods` 驱动 | 一份代码 36 链覆盖 | 加链零脚本 | 需先有 RPC endpoint config |
| (c) 录制改为录 framework 真实 e2e 流量 (代理 tap) | 真实流量 fixture | 真实性最高 | 需 framework 已能压目标链 (鸡生蛋) |

**当前倾向**:**(b)**,与 framework `_meta` 字段驱动一致 (parallel-entry-trap 既有结论 = 不要再造 ad-hoc 入口)。

**决策时点**:阶段 5 前;blocker 程度低 (手写 stub fixture 也能 smoke 通)。

---

## 更新规则

- 每个 OQ 决策落定时,**从本文档移除**,同步:
  1. 更新 `NORTH-STAR.md` 决策表(增加新行)
  2. 写 ADR 到 `docs/architecture/decisions/000X-<short-name>.md`
- 新发现的待决项,**追加到本文档**(用下一个 OQ-N 编号)
- 本文档不需要 ADR

---

**当前状态**:**2 个 OQ 待决**(OQ-9 / OQ-10;OQ-1 / OQ-2 / OQ-3 / OQ-4 / OQ-5 / OQ-6 / OQ-7 / OQ-8 已锁 → NORTH-STAR Q4-7~14)
**下次预期更新**:阶段 5 启动前 OQ-9 (fake-node stub handler) / OQ-10 (fixture 录制流水线) 可决
