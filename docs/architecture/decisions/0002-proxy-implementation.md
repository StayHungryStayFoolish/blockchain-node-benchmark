# ADR-0002: proxy 实现 — Go 反向代理 + 流式 JSON decoder 提 method 字段

## 状态
Accepted(2026-05-27,commit `9e52ead`)

## 背景

ADR-0001 定下"proxy 旁路记 method"路径,但 proxy 怎么实现是开放问题(OQ-1)。关键约束:

1. 必须扛 mixed workload 下的高 QPS(目标 10k+ / 链)
2. 必须正确解析 JSON-RPC body 拿 `method` 字段(不只 URL 路径)
3. 必须**透传 upstream 响应不损坏**(status / body / headers / streaming)
4. 必须能 36 链 DSL 化(协议 dispatcher 可零代码加链,NS-3)
5. proxy 自身开销受 ADR-0004 撤销线约束(< 节点 CPU 10%)

## 选项

- **选项 A:nginx + lua module(openresty)**
  - 优:成熟,运维熟
  - 劣:JSON 解析要 cjson 模块,lua 写 36 链 DSL 不直观;CPU 开销在 lua VM 上有不可控尾巴
- **选项 B:envoy + WASM filter**
  - 优:云原生,可扩展
  - 劣:WASM filter 工具链重(Rust/Go SDK),36 链 DSL 化需要每链编一份 WASM,**学习成本和 CI 复杂度爆炸**
- **选项 C(选定):自写 Go 反向代理 + 流式 JSON decoder**
  - 单二进制 ~150 行,标准库 net/http + encoding/json
  - 流式 decoder 只解 top-level `method` 字段,不全 unmarshal
  - 36 链 DSL 化通过 protocol family(jsonrpc / rest / substrate / ogmios / hedera_dual / bitcoin_jsonrpc / tendermint)dispatcher
- **选项 D:Rust + tokio**
  - 优:性能极致(零拷贝)
  - 劣:团队无 Rust 经验,学习成本不划算;Go 性能下限已够本场景

## 决策

**选 C**。理由:
1. **代码量小**:最小 PoC 实测 146 行(`tools/proxy/poc-min/proxy.go`)
2. **零依赖**:Go 标准库 net/http + encoding/json 即可
3. **DSL 化路径清**:protocol family registry + per-family parser,与现有 `tools/chain_adapters/` 模式一致
4. **性能下限够**:最小 PoC 实测 6.8k QPS @ p99 3.6ms,1.72 core
5. **运维门槛低**:单二进制 + 单 CSV log,容器化容易

## 后果

**正面**:
- 单二进制,部署 1 个文件
- Go 团队熟,DSL 扩展按 family 注册,代码量可控
- 流式 decoder 节省 CPU(不全 unmarshal)
- net/http 标准库稳定,无 supply chain 风险

**负面**:
- **net/http 标准库性能不如 fasthttp**:阶段 4 / 5 若打不到 10k+ QPS / core 可切 fasthttp(已在 REPORT.md §7 备选)
- **每请求两次 IO**:io.ReadAll body + 转发,内存峰值高于零拷贝方案;可改 io.TeeReader 优化
- **CSV writer 全局锁**:`sync.Mutex` 在高 QPS 下成瓶颈,需 buffered + 周期 flush

**撤销线**:
- < 5k QPS @ p99 < 10ms(本 PoC 6.8k,已过)
- 或 DSL 支持 < 32/36 链 → 撤销转 nginx+lua(选项 A)

**后续工作**:
- 阶段 4:加 protocol family dispatcher,接 monitor + 真节点验全闭环
- 阶段 5:36 链 family 全覆盖,Wave W1-W7 按 family 分波
- 性能优化(io.TeeReader / buffered CSV / 必要时换 fasthttp)

## 关联

- NORTH-STAR.md §3 Q4-8
- tools/proxy/poc-min/proxy.go(最小 PoC 实现)
- tools/proxy/poc-min/REPORT.md §4-6(实测数据)
- analysis-notes/research_notes/07-per-method-resource-attribution-via-proxy.md §3
- docs/architecture/per-method-proxy-architecture-zh.md(1-A)
- OPEN-QUESTIONS.md(OQ-1 已锁)
