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

## OQ-2:proxy 部署形态细节

**问题**:Q4-1 已定独立进程,但部署细节?

| 候选 | 适用场景 | 缺点 |
|---|---|---|
| **systemd unit**(Linux VM 直跑) | 虚拟机 + cloudtop 直接跑 | 不跨平台,Mac/Win 开发不友好 |
| **docker container** | 跨平台、隔离、镜像可发布 | 多一层 docker daemon 依赖 |
| **K8s pod / sidecar(同 namespace)** | GKE / K8s 生产环境 | PoC 阶段过重 |
| **二进制裸跑**(./proxy &) | 开发调试最快 | 无生命周期管理 |

**当前倾向**:**支持 systemd + docker 双部署**(同一二进制,部署方式按环境选);PoC 阶段允许裸跑

**决策时点**:阶段 1-A 架构文档落地时(确定部署 spec 即可,实现归阶段 4)

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

## OQ-5:chain template proxy_extraction DSL 完整 spec

**问题**:Q4-4 已定 declarative DSL,**4 种模式的完整字段定义?**

**初稿(2026-05-27,待阶段 1-B 细化)**:

```jsonc
{
  "proxy_extraction": {
    "protocol": "json_rpc",  // 枚举: json_rpc | rest | bitcoin_rpc | grpc

    // protocol=json_rpc / bitcoin_rpc:
    "method_source": "body.method",     // JSON path,提取 method 名
    "id_source": "body.id",             // 可选,提取 request id 做 latency 配对
    "params_source": "body.params",     // 可选,统计 params 大小 / 复杂度

    // protocol=rest:
    "url_pattern": "^/v2/([^/]+)/.*$",  // 正则,提取 method 名
    "url_method_group": 1,              // 捕获组索引
    "method_normalize": {               // 可选,映射归一化
      "transactions": "get_transactions",
      "blocks": "get_blocks"
    },

    // protocol=grpc:
    "grpc_service": "hedera.MirrorService",  // 全限定服务名
    "grpc_method_field": "method"            // 通过 :method gRPC header 提取
  }
}
```

**决策时点**:阶段 1-B `chain-template-zero-code-spec-zh.md` 落地时(必须用 36 链全部协议**填表证明 DSL 够用**)

**验证手段**:为 36 链每条都写出 `proxy_extraction` 配置,如果某链 4 种模式都表达不出,**反推扩充 DSL**(或将该链标 KNOWN_BROKEN_PROXY)

---

## OQ-6:proxy 与 fetcher 的边界

**问题**:fetcher (`tools/fetch_active_accounts.py`) 当前仅 8 链支持,**proxy 是否依赖 fetcher?**

**已知**:
- fetcher 产物 = `accounts.txt`(地址池),供 target_generator 拼 vegeta target body 用
- proxy 不依赖 fetcher,只解 body / URL 抓 method 名
- 但 e2e 跑 benchmark **需要** fetcher → target_generator → vegeta → proxy → 节点

**当前倾向**:**fetcher 和 proxy 解耦,但 e2e 需要 fetcher 28 链扩展**(归阶段 5)。PoC(solana 1 链)fetcher 已支持,不阻塞。

**决策时点**:阶段 1-C `migration-from-legacy-zh.md` 落地时(明确 fetcher 28 链补全的责任边界)

---

## OQ-7:weight 配置的 chain template schema

**问题**:NS-2 要求 mixed mode 支持 weight 配置,**chain template 怎么表达?**

**候选 schema**:

```jsonc
// 候选 A: 扩展 mixed 字符串
"rpc_methods": {
  "single": "eth_getBalance",
  "mixed": "eth_getBalance:40,eth_getTransactionCount:30,eth_blockNumber:20,eth_gasPrice:10"
}

// 候选 B: 新增 mixed_weighted 字段(向后兼容)
"rpc_methods": {
  "single": "eth_getBalance",
  "mixed": "eth_getBalance,eth_getTransactionCount,eth_blockNumber,eth_gasPrice",  // 老格式保留
  "mixed_weighted": [
    {"method": "eth_getBalance", "weight": 40},
    {"method": "eth_getTransactionCount", "weight": 30},
    {"method": "eth_blockNumber", "weight": 20},
    {"method": "eth_gasPrice", "weight": 10}
  ]
}

// 候选 C: 完全替代 mixed
"rpc_methods": {
  "single": "eth_getBalance",
  "mixed": [
    {"method": "eth_getBalance", "weight": 40},  // 老格式废弃
    ...
  ]
}
```

**当前倾向**:**B(新增 mixed_weighted)** — 向后兼容老 user_config,且新功能显式

**决策时点**:阶段 1-B `chain-template-zero-code-spec-zh.md` 落地时

---

## OQ-8:proxy 自身资源消耗如何排除? ✅ 已锁定(2026-05-27)

> **状态**:已锁定,合入 NORTH-STAR §3 **Q4-10**。
> **决策摘要**:**默认透明记录 + 自报基线**(`proxy_self.csv`:每秒自报 cpu_pct / mem_mb);分析层从节点资源减去基线后再归因 method;K8s 生产用 sidecar 独立 pod 隔离。
> **PoC 撤销条件**:proxy CPU > 节点 10% 或自报偏差 > 30% → 必须启用 cgroup 隔离。
> **决策依据**:候选 (c) 透明 + 自报基线兼顾"运维知情"与"实施简单";(a) cgroup 隔离在 GKE pod 内难做,K8s 直接走 sidecar 形态更自然。完整反方论证见 `analysis-notes/research_notes/07-per-method-resource-attribution-via-proxy.md` §5。
> **ADR 待写**:`docs/architecture/decisions/0004-proxy-overhead.md`(归阶段 4 PoC 启动前补)

---

## 更新规则

- 每个 OQ 决策落定时,**从本文档移除**,同步:
  1. 更新 `NORTH-STAR.md` 决策表(增加新行)
  2. 写 ADR 到 `docs/architecture/decisions/000X-<short-name>.md`
- 新发现的待决项,**追加到本文档**(用下一个 OQ-N 编号)
- 本文档不需要 ADR

---

**当前状态**:**4 个 OQ 待决**(OQ-2 / OQ-5 / OQ-6 / OQ-7;OQ-1 / OQ-3 / OQ-4 / OQ-8 已锁 → NORTH-STAR Q4-7~10)
**下次预期更新**:阶段 1 架构文档 review 通过后(OQ-2 / OQ-3 / OQ-4 / OQ-5 / OQ-7 / OQ-8 部分应该可决);阶段 2 调研档完成后 OQ-1 可决
