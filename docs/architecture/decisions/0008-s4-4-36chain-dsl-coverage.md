# ADR-0008: S4.4 — 36 链 DSL 双模式 smoke 覆盖率验收

**Status**: Accepted
**Date**: 2026-05-28
**Stage**: S4.4(NS-2/NS-3 收尾)
**Parent**: ADR-0006(W2 proxy perf baseline)、ADR-0007(S4.3 solana PoC 验收)
**Plan**: `docs/plans/2026-05-28-s4-ns2-implementation.md` §6

## Context

W2 已交付 36/36 chain template 通过 `LoadChain` — 但 load 只验 JSON schema +
extractor 构造能成功,**没验真正送一个请求进去能不能抽出 method_name**。

NS-3 "零代码加链" 原则的真业务含义是:**新增一条链只需写 chain template JSON,
proxy 不动**。这要求 W2 extractor 实现对所有 36 链都"开箱可用",而不是有 4-5
条链需要在 proxy 里特判。S4.4 就是验这一点。

## Decision

**采用 dry-run DSL smoke 测试**(不启 proxy 进程,纯单元):

1. 在 `tools/proxy/internal/config/dsl_coverage_test.go` 新增
   `TestProxyDSLCoverage_All36Chains`
2. 对 36 条链每条:`LoadChain` → 推导 fixture HTTP 请求 → `Chain.Extract` →
   验抽出 method_name 非空
3. 阈值:**≥ 32/36 PASS** = OK;< 32 → 触发 Q4-8 envoy + Lua 兜底评估

## Outcome

**实测 36/36 PASS** ✅,远超 32/36 阈值。

| 协议 | 链数 | 备注 |
|---|---|---|
| `json_rpc` | 30 | EVM 系 + 多数非 EVM |
| `rest` | 6 | algorand, aptos, cardano, hedera, tezos, ton |
| dual(rest + json_rpc) | 1 | hedera(rest 优先) |

**不触发 Q4-8 envoy + Lua 兜底评估** — W2 stdlib-only Go proxy 充分覆盖 36 链
DSL 解析需求。

## Why not 真节点 e2e?

S4.4 plan 明确 "**不要求 e2e benchmark**(那是 NS-1)"。真节点 e2e 36 链需要:
- 36 个 archive 节点(无 access)
- vegeta(沙盒 apt 禁)
- 真 RPC 比例数据(部分链尚无 baseline)

推后到 NS-1 阶段,与 S4.3 solana 真节点复测合并处理。

## Why Go 测试 而非 Python?

- extractor 是 Go 实现,Python 测试要么调 binary(增加 surface)要么 reimplement(R0-7 违规)
- Go 原生测试 0.016s 跑完 36 链,零外部依赖
- 跟 W2 `TestLoadChain_All36Chains` 同包同风格,新人发现性强

## 测试编写过程的 3 个 fixture 推导 bug

(都是测试本身的 bug,**非 W2 extractor bug** — 修后 36/36)

1. **bug-1**: 裸 character class `[^/]+` 等未被 `patternToSamplePath` 处理 →
   生成的 URL 字面带 regex 字符,不 match 任何 pattern。
   **fix**: 加替换规则覆盖 `[^/]+`、`[^/]*`、`\\d+`、`\\w+`。

2. **bug-2**: POST-only rest endpoint(如 aptos `POST /v1/view`)推 GET 失败。
   **fix**: 从 `method_name` 前缀("GET "/"POST "/...)推导 HTTP verb,
   优先级:显式 `method` 字段 > `method_name` 前缀 > GET 兜底。

3. **bug-3**: `fmt.Sprint(nil)` 返回 `"<nil>"` 未被 `httpMethod == ""` 检测
   到 → 当作合法 HTTP method 传给 `http.NewRequest`,直接报 `invalid method`。
   **fix**: 显式 reset `httpMethod = ""`,再走推导,最后兜底。

每个 bug 都先看到 fail 才修,符合 R0(诚实记录,不掩盖);R0-7 警觉(没把
hard threshold 改 soft warn 隐藏问题)。

## Verification

```bash
cd tools/proxy
go test -run TestProxyDSLCoverage_All36Chains -v ./internal/config/
```

预期输出尾行:
```
=== S4.4 DSL coverage: 36/36 PASS ===
--- PASS: TestProxyDSLCoverage_All36Chains (0.01s)
```

完整 36 链 PASS 行 + 抽出的 method_name:
见 `docs/architecture/s4-4-36chain-smoke/coverage_log.txt`。

## Acceptance(plan §6)

- [x] `TestProxyDSLCoverage_All36Chains` 覆盖率 ≥ 32/36 — **36/36 实测**
- [x] < 32 时记 OQ + 触发 ADR-0007 envoy 兜底 — 不适用
- [x] ADR-0008 记录覆盖率 + 不触发兜底决策
- [x] 端证 `docs/architecture/s4-4-36chain-smoke/` 落盘

## Trade-offs

| 维度 | 选项 | 选择 | 理由 |
|---|---|---|---|
| 测试位置 | Go vs Python | **Go** | 离 extractor 最近,0 跨语言开销 |
| 启动模式 | dry-run vs 36 个真 proxy | **dry-run** | 0.016s vs 几分钟,资源占用极低 |
| 真请求 vs fixture 推导 | 真 RPC vs 推导 | **推导** | 真 RPC 推后到 NS-1(GCE) |
| 阈值放宽 | 严格 36 vs 宽松 ≥ 32 | **严格 36 实测** | 阈值 ≥ 32 是兜底,目标永远是 36 |

## Reversal Criteria

如果未来发现某条链虽 DSL 解析 PASS 但真 RPC e2e fail(NS-1 阶段),
需补 method-level diff 测试,并将 dry-run 测试升级为含小型 in-memory upstream
的 e2e 测试。
