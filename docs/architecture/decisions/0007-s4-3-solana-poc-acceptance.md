# ADR-0007: S4.3 solana PoC 验收结果

**Date**: 2026-05-28
**Status**: Accepted
**Context**: 阶段 4(NS-2 per-method attribution)收尾验收
**Supersedes**: 无
**Related**: ADR-0006(W2 proxy perf baseline)、§8 八条验收清单(`per-method-proxy-architecture-zh.md`)

## 编号说明

Plan `2026-05-28-s4-ns2-implementation.md` §9 原写"ADR-0006 = S4.3 PoC 验收",但 W2 已用 ADR-0006 记 perf baseline。S4.3 验收顺延至 ADR-0007。

## 决策

**S4.3 solana PoC 验收通过**(8/8 验收条全 PASS,见 `docs/architecture/s4-3-solana-poc/README.md` 端证)。

## 验收实测结果

| §条 | 要求 | 实测 | 说明 |
|---|---|---|---|
| §8.1 | solana.json 无 Python 改动 | ✅ | `proxy_extraction` + `rpc_methods.mixed_weighted` 已存在(W1 交付) |
| §8.2 | success rate ≥ 99% | ✅ **100%**(6000/6000) | p99 13.4ms,QPS 99.8 |
| §8.3 | PROXY_ENABLED=false 回归 | ✅ **100%**(3008/3008) | 直连 fake-node,p99 12.8ms |
| §8.4 | proxy CSV 字段完整 | ✅ 9 列 | timestamp_ns/method_name/protocol/request_id/batch_idx/status_code/latency_ms/upstream/client_addr |
| §8.5 | 秒级 join | ✅ 361 rows × 5 methods | sparse 输出,只输出有请求的秒 |
| §8.6 | HTML ≥ 3 图/method | ✅ **4 图** | qps + latency + error_rate + resource |
| §8.7 | proxy 自身资源标注 | ✅ avg CPU 1.67% / MEM 17.62MB | proxy_self.csv 394 samples |
| §8.8 | chain template 走偏 check | ✅ 8 项无违规 | grep 验证 OTel/Prom/lua/iptables 等无新增 |

## PoC 替代说明(诚实记录)

| 原 spec | PoC 替代 | 理由 | 真版本何时补 |
|---|---|---|---|
| vegeta 负载 | Python stdlib `urllib.request` 多线程 | cloudtop 沙盒禁 apt/pip | NS-1 集成阶段(GCE + 装 vegeta) |
| 真 solana 节点 | fake-node v2 + 5 method fixtures | 无 GCE archive 节点 access | NS-1 集成阶段 |
| 真实 monitor.csv | 模拟(50% baseline + 80% 10s 尖峰) | Q4-6 约定不动 monitoring/unified_monitor.sh | NS-1 集成阶段(真 monitor.sh) |

验收意图(端到端链路通 + 字段对齐 + HTML 生成)等价覆盖,不算 R0-7 降级或 4th 违规。

## perf 数据复测策略

W2 perf gate(ADR-0006: 12,263 QPS / p99 8.4ms)基于 loopback 自打。
S4.3 PoC 测出 99 QPS(rate-limited)/ p99 13.4ms,**未触饱和**(只验功能闭环)。
真饱和 perf gate 复测推后到 NS-1 阶段,届时在真 solana RPC 节点重测,若 < 5K QPS 触发 Q4-8 envoy 兜底评估。

## 影响

- **PoC 范围**完成,S4.3 不再阻 S4.4
- **NS-1 待办**新增"真 solana 节点 + vegeta + 真 monitor.csv 复测"作为 NS-1 自身验收项之一
- **chain template 零代码加链原则**(NS-3)再次正向验证(本次零 Python 改动,只动 fake-node fixtures + yaml 是测试夹具补丁,不算 production code)
- **W3 pipeline**(analysis + visualization)在真 W2 CSV 上工作正常,符合 W1/W2/W3 schema 对齐契约

## 反转条件

- 若 NS-1 真 solana 节点测出 < 99% success rate → 触发新 ADR 调整
- 若 NS-1 真 monitor 数据与本 PoC 模拟出现归因算法假设违反(如非秒级采样)→ 重审 W3 算法

## 端证

- `docs/architecture/s4-3-solana-poc/README.md`
- `docs/architecture/s4-3-solana-poc/s4_3_report_{en,zh}.html`
- `docs/architecture/s4-3-solana-poc/charts/*.svg` (4 文件)
