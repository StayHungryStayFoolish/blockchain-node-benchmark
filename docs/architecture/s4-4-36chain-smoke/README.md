# S4.4 — 36 链 DSL 双模式 smoke 覆盖率

**Plan**: `docs/plans/2026-05-28-s4-ns2-implementation.md` §6
**ADR**: `docs/architecture/decisions/0008-s4-4-36chain-dsl-coverage.md`
**Test**: `tools/proxy/internal/config/dsl_coverage_test.go`
**Commit**: `<this commit>`(parent `bbe82fb`)

## 目标

验 36 条 chain template 的 `proxy_extraction` DSL 是否能被 W2 Go proxy 真正解析,
不只是 load 能过(W2 `TestLoadChain_All36Chains` 已覆盖),还要**构造一个能命中
extractor 的 fixture HTTP 请求,验抽出的 method_name 非空**。

这是 NS-3"零代码加链"原则的对称性验证 — 任何被 W2 接受的 chain template,
都必须真正能在 runtime 被解析,否则 proxy 上线后该链 method-level 归因失效。

## 验收阈值

| 覆盖率 | 决策 |
|---|---|
| **≥ 32/36** | OK,继续 NS-1 真节点 e2e |
| < 32/36 | 触发 Q4-8 envoy + Lua 兜底评估 |

**实测**: **36/36 PASS** ✅ — 远超阈值。

## 实测结果

```
=== S4.4 DSL coverage: 36/36 PASS ===
```

完整 36 条逐项:见 `coverage_log.txt`。

### 协议分布(by extractor[0])

| 协议 | 链数 | 链 |
|---|---|---|
| `json_rpc` | 30 | acala, arbitrum, astar, avalanche-c, avalanche-x, base, bch, bitcoin, bsc, celestia, cosmos-hub, dogecoin, ethereum, injective, kusama, linea, litecoin, moonbeam, near, optimism, osmosis, polkadot, polygon, scroll, sei, solana, starknet, sui, tron, zksync-era |
| `rest` | 6 | algorand, aptos, cardano, hedera, tezos, ton |
| dual (rest + json_rpc) | 1 | hedera (rest 优先) |

### Sample 推导样本

| 链 | 协议 | 请求 verb | URL/body | 抽出 method_name |
|---|---|---|---|---|
| ethereum | json_rpc | POST | `/` body=eth_getBalance | `eth_getBalance` |
| algorand | rest | GET | `/v2/accounts/sample` | `GET /v2/accounts/{address}` |
| aptos | rest | POST | `/v1/view` | `POST /v1/view` |
| cardano | rest | GET | `/tip` | `GET_TIP` |
| hedera | rest | GET | `/api/v1/accounts/sample` | `GET_ACCOUNT` |
| tezos | rest | GET | `/chains/main/blocks/head/context/contracts/sample/balance` | `GET /chains/main/blocks/head/context/contracts/{addr}/balance` |
| ton | rest | GET | `/getMasterchainInfo` | `getMasterchainInfo` |
| starknet | json_rpc | POST | body=starknet_getClassAt | `starknet_getClassAt` |

## 测试设计

dry-run 策略 — **不启 proxy 进程**,直接调用 `config.LoadChain()` + `extractor.Chain.Extract()`,
对每条链:

1. `LoadChain(path)` → 构造出 `*extractor.Chain`(W2 已验 36/36 load)
2. `buildFixtureRequest(path)`:
   - **json_rpc**: 从 `rpc_methods.mixed_weighted[0].method` 推 method,组 POST body
   - **rest**: 从 `extractors[0].url_patterns[0]` 推 sample URL,verb 优先级:
     - 显式 `method` 字段 > `method_name` 前缀(`GET `/`POST `/...)> GET 兜底
3. `chain.Extract(req, body)` → 期望 `out[0].MethodName != ""`

测试 0.016s 跑完 36 链,纯单元测试无外部依赖。

## 关键修复

测试编写过程发现 3 个 fixture-推导 bug(不是 extractor bug):
- `[^/]+` 等裸 character class regex 未被处理 → 加替换规则
- POST-only rest endpoint 推 GET 失败 → 从 `method_name` 前缀推导 verb
- `fmt.Sprint(nil)` 返回 `"<nil>"` 不被空字符串检测 → 显式 reset

修复后 36/36 PASS,**说明 W2 proxy 的 extractor 实现对 36 链 0 缺漏**,
真业务北极星 NS-3"零代码加链"在 DSL 层面 ✅。

## 验收 checklist(plan §6)

- [x] `test_proxy_dsl_coverage.go` 覆盖率 ≥ 32/36 — **实测 36/36**
- [x] 失败链(若 < 36)记入 OPEN-QUESTIONS.md + 触发 ADR-0007 — **不适用,0 失败**
- [x] ADR-0008 记录覆盖率结果 + 不触发 envoy 兜底的决策

## NS-1 / NS-2 / NS-3 对账

| 北极星 | S4.4 贡献 |
|---|---|
| **NS-1** (36 链支持) | DSL 层 36/36 解析通过,加链 0 代码不破 |
| **NS-2** (mixed RPC + per-method 归因) | S4.3 端到端已 PASS,此处不涉及 |
| **NS-3** (零代码加链) | **本节核心验证** — chain template JSON 唯一改动点,proxy 不动 |

## 残留(非阻塞)

- 真节点 e2e(36 链各送真 RPC):推后到 NS-1 阶段,需 GCE archive 节点
- `mixed_weighted` 比例平衡审计:S4.3 solana 已验,其它 35 链放 NS-2 滚动覆盖
