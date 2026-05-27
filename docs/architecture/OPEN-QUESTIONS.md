# OPEN-QUESTIONS — 待决项追踪

> **状态**:跟踪中(随研究推进更新答案)
> **作用**:记录已识别但**尚未决策**的设计选项,避免在 session 中重复发散。
> 每个决策落定后,从本文档移除并**同步到 NORTH-STAR.md 决策表 + 写 ADR**。

---

## OQ-1:proxy 具体选型

**问题**:Q4-1 已定 proxy = 独立进程(VM + GKE),但**具体用什么实现?**

| 候选 | 优点 | 缺点 | 适配 NS-3 declarative? |
|---|---|---|---|
| **envoy** | 工业级、稳定、HTTP filter chain 成熟、Wasm/Lua 扩展 | 部署重(配置 YAML 复杂)、二进制大 | ⚠️ 默认配置 YAML 偏 declarative,但 method extraction 需 Lua/Wasm 写一次性 filter |
| **nginx + access_log custom format** | 轻、运维熟悉、URL path 提取直接 | EVM JSON-RPC body 提取需要 Lua 模块、不支持 gRPC | ❌ JSON body 提取需 Lua |
| **mitmproxy(Python)** | 开发快、可编程性极强、单机 PoC 首选 | 生产场景吞吐有限(Python GIL)、不适合 36 链规模 | ✅ Python 脚本可读 chain template,但**违 NS-3 零代码**(脚本=代码) |
| **自写 Go 小代理** | 轻(~200-500 行)、吞吐高、可控、原生支持 declarative DSL | 需要开发 + 维护 | ✅ 设计上完全 declarative,从 chain template 读取规则 |
| **Caddy + custom handler** | 配置极简、HTTP/3、自动 TLS | method extraction 需要 Go plugin、生态比 nginx 小 | ⚠️ 同 nginx,需 Go plugin |

**当前倾向**:**自写 Go 小代理**(理由:NS-3 零代码加链原则下,只有自写 + declarative 设计能完全满足;envoy/nginx 都需要为新协议写一次性 filter,违反 NS-3)

**决策时点**:阶段 2 调研档 `07-per-method-resource-attribution-via-proxy.md` 完成后

**决策依据需要**:
- 36 链协议矩阵覆盖测试(declarative DSL 能表达多少链?)
- 性能基准(自写 Go 小代理在 PoC 阶段吞吐能否撑 vegeta 压力?)
- 维护成本评估(谁来 maintain Go 代理?)

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

## OQ-3:per-method 归因算法

**问题**:proxy 输出"每请求 method + timestamp + latency",monitor 输出"每秒资源时序",**如何归因?**

| 算法候选 | 描述 | 优点 | 缺点 |
|---|---|---|---|
| **(a) 简单 group_by**(秒级时间窗) | 按 1s 窗口 group proxy 请求,统计每 method 占比,按比例分摊该秒的资源增量 | 简单、直观、运维易懂 | 假设资源消耗与请求数线性相关,不精确 |
| **(b) 加权回归**(method 占比 → 资源消耗) | 线性回归 / 多元回归,各 method 占比为自变量,资源消耗为因变量 | 较精确 | 需大样本、有共线性风险、运维难解释 |
| **(c) 蒙特卡洛 / 试验设计** | 不同 method 比例下多轮压测,反推每 method 单位资源消耗 | 最精确 | 时间成本高(每链多轮压测) |

**用户原话(2026-05-27)**:"运维人员看 rpc method 相关的资源图可以快速理解,获取到运维人员希望获取的数据就可以"

**当前倾向**:**(a) 简单 group_by + 秒级时间窗** — 符合"运维快速理解"原则,可解释性强,实施成本低;(b)(c) 作为后续增强,不在 PoC 范围

**决策时点**:阶段 1-A 架构文档落地时

---

## OQ-4:sink 默认格式

**问题**:Q4-3 已定 sink = CSV/JSONL,**默认用哪个?**

| 候选 | 优点 | 缺点 |
|---|---|---|
| **CSV** | 与现有 unified_monitor CSV 格式一致,分析层 pandas join 简单 | 字段固定、扩展不灵活、转义麻烦 |
| **JSONL**(每行一条 JSON) | 字段灵活、扩展友好、native 表达嵌套 | 解析慢、文件大、分析层需要额外 parse 步骤 |

**当前倾向**:**JSONL**(理由:proxy 日志 schema 可能随 chain template 协议变化,JSONL 扩展性更好;CSV 适合固定 schema 的 monitor,proxy 是新增可演进数据源)

**决策时点**:阶段 1-A 架构文档落地时

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

## OQ-8:proxy 自身资源消耗如何排除?

**问题**:proxy 与节点同机(Q4-1),proxy 自身的 CPU / MEM 消耗会被 unified_monitor 采到,**如何排除?**

**候选**:
- **(a) cgroup 隔离 proxy 进程**,monitor 排除 proxy cgroup 数据 → 精确
- **(b) proxy 自报资源(periodic stat)**,分析层减去 → 简单但有偏差
- **(c) 不排除,记录 proxy 开销,在报告中说明**(运维知道 proxy 占了多少) → 最透明

**当前倾向**:**(c) + 可选 (a)** — PoC 阶段先 (c) 透明记录,生产环境可启用 (a)

**决策时点**:阶段 1-A 架构文档落地时

---

## 更新规则

- 每个 OQ 决策落定时,**从本文档移除**,同步:
  1. 更新 `NORTH-STAR.md` 决策表(增加新行)
  2. 写 ADR 到 `docs/architecture/decisions/000X-<short-name>.md`
- 新发现的待决项,**追加到本文档**(用下一个 OQ-N 编号)
- 本文档不需要 ADR

---

**当前状态**:**8 个 OQ 待决**
**下次预期更新**:阶段 1 架构文档 review 通过后(OQ-2 / OQ-3 / OQ-4 / OQ-5 / OQ-7 / OQ-8 部分应该可决);阶段 2 调研档完成后 OQ-1 可决
