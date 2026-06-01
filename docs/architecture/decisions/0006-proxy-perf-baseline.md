# ADR-0006: Proxy 性能基线 + Q4-8 envoy 兜底未触发

| 字段 | 值 |
|---|---|
| **状态** | Accepted |
| **日期** | 2026-05-28 |
| **关联** | S4.2 W2 (Go proxy 实现) / Q4-8 撤销条件 |
| **作者** | 自动化代理(用户授权代行) |

## 背景

S4.2 W2 完成 Go proxy(796 行 production code, 8 个 sub-task 全交付)后,
必须验证 **Q4-8 撤销条件**:

> 性能 < 5k QPS @ p99 < 10ms → 启用 envoy 兜底重做 proxy 协议层

ADR-0004(proxy-overhead)给出过设计预算;本 ADR 给出**实测基线**。

## 测试方法

- 测试平台:cloudtop e2-standard-8(8 核 AMD EPYC 7B12,8 GB,Linux 6.18 rodete)
- 测试代码:`tools/proxy/internal/proxy/handler_perf_test.go`(build tag `perf`)
- 配置:32 并发 worker / 3 秒持续打 / loopback httptest server 作 upstream
- 工作负载:`eth_blockNumber` JSON-RPC(单条 60 字节请求)
- 命令:`make perf`(等价于 `go test -tags=perf -run=TestPerformanceGate ./internal/proxy/`)

**注意**:perf 测试**不带 `-race`**(race detector 慢 5-10x 会让结果失真);
`make test` 跑功能 + race,`make perf` 跑性能 gate,分开。

## 测试结果(2026-05-28 W2 完成时)

| 指标 | 实测 | Q4-8 阈值 | 状态 |
|---|---|---|---|
| 总请求数 | 39,127 | — | — |
| QPS | **13,042** | ≥ 5,000 | ✅ 过 161% |
| p99 延迟 | **7.06 ms** | < 10 ms | ✅ 过 29% |

**Baseline 对照**(直连 httptest server,无 proxy):
- 直连 QPS: 44,027 / p99: 3.4 ms
- proxy 开销:吞吐降 70%,p99 增 +3.6 ms — 在预算内

## 关键优化(W2 调试发现)

初版未配 Transport,QPS 6.6k / p99 16ms,**p99 不达标**。
排查 ~5 分钟定位到 `httputil.NewSingleHostReverseProxy` 的默认
`http.DefaultTransport.MaxIdleConnsPerHost=2` 在 32 并发 loopback 下严重瓶颈。

补 6 行 Transport 配置(`MaxIdleConnsPerHost=256` + `MaxConnsPerHost=512` 等),
QPS 翻倍至 13k、p99 减半到 7ms,**不需要启 envoy 兜底**。

```go
rp.Transport = &http.Transport{
    MaxIdleConns: 512, MaxIdleConnsPerHost: 256, MaxConnsPerHost: 512,
    IdleConnTimeout: 90 * time.Second, DisableCompression: true,
}
```

## 决策

1. **Q4-8 envoy 兜底**:**不触发**。继续按当前 Go proxy 路线推进 W3 / S4.3 / S4.4。
2. **性能 gate** 进 `make perf` Makefile target,**不进默认 CI**(避免 race / 无负载机器误报)。
   生产前(S4.3 solana e2e 之前)必须再跑一次,且必须用真实 Solana node 作 upstream,
   不能继续用 httptest mock。
3. **预算冗余**:QPS 161% 过线、p99 29% 过线 — 留余地给真实 upstream 额外延迟。
   但不留太多 — 真实 Solana RPC 上游延迟比 loopback 可能 +5-50 ms,
   **proxy 自己的开销 7 ms 已经吃掉 p99 预算的一半**。
4. **未做 / 故意未做的优化**(W3 之前不动,避免过度工程):
   - body 双拷贝(`io.ReadAll` + `bytes.NewReader`)— 80B JSON-RPC 时影响微小
   - sink CSV 串行 Lock — discard sink 已绕过,production sink batch 写是 W3 范围
   - HTTP/2 / 自定义 ReverseProxy → 都是 envoy 路线的等价复杂度,不值得

## 复盘条件 / 何时回到本 ADR

- S4.3 solana 真集成 QPS / p99 任一项触发 Q4-8 阈值
- 任何真实链上游让 proxy 自身 p99 > 12 ms(留 2 ms 给真实抖动)
- 多 worker 并发场景(W3 mixed_weighted 之上)出现 race 或锁竞争

满足上述任一,重开本 ADR → 评估是否切 envoy 或加 batch sink。

## 相关文件

- `tools/proxy/internal/proxy/handler.go`(L33-41 Transport 配置)
- `tools/proxy/internal/proxy/handler_perf_test.go`
- `tools/proxy/Makefile`(`make perf` target)
- `docs/architecture/decisions/0004-proxy-overhead.md`(设计预算前置)
