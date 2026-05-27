# ADR-0004: proxy 自身开销 — 目标 < 节点 CPU 10%

## 状态
Accepted(2026-05-27,commit `9e52ead`)

## 背景

ADR-0001 + 0002 + 0003 把 proxy 放在 hot path。问题:proxy 自身要烧 CPU/MEM/Net,**这部分开销算不算在节点账上**?

如果 proxy 自己烧 1 core 而节点烧 8 core,归因结果"节点 CPU"是按 8 算还是按 9 算?如果 proxy 开销 > 节点开销的 20%,**所有 per-method 归因结果都失真**。

OQ-8(旧编号)= proxy 自身开销目标和监控方式。

## 选项

- **选项 A:不限制 proxy 开销,只记账分离**
  - 优:简单,proxy 开心怎么写都行
  - 劣:proxy CPU 高时归因失真不可控
- **选项 B(选定):目标 < 节点 CPU 10%,自报偏差 < 30%**
  - proxy 自身 CPU 通过 `/proc/<pid>/stat` 自采,与节点 CPU 同时间窗对比
  - 设硬撤销线:**proxy CPU > 节点 10% 或自报偏差 > 30%** → 撤销 ADR-0002 转选项 A(nginx+lua)或选项 D(Rust+tokio)
- **选项 C:proxy 用独立机器**(sidecar 模式)
  - 优:开销隔离
  - 劣:**网络一跳 latency 不可接受**,违反 ADR-0001 "proxy 与节点同机 clock 一致"前提
- **选项 D:proxy 与节点 cgroup 隔离,记账分账**
  - 优:精细
  - 劣:cgroup 配置复杂,36 链每个部署都要配,运维负担大

## 决策

**选 B**。

**目标**:proxy CPU < 节点 CPU × 10%

**监控方式**:
- proxy 自身在 hot path 用 `runtime.NumGoroutine() / GC stats / pid CPU%` 自采
- 写入独立 channel(不混 method log CSV)
- 与 monitor 进程的节点 CPU 数据在离线 join 阶段对齐
- 自报偏差 = `(proxy 自采 CPU%) - (/proc/<proxy_pid>/stat 第三方采)`,差 > 30% 说明 proxy 自报不可信

**撤销线**:
- proxy CPU > 节点 10%(归因失真不可接受)
- 或自报偏差 > 30%(proxy 自身指标不可信)

## 后果

**正面**:
- 撤销线明确,达不到就换方案
- 双采(自报 + /proc)互校,防 proxy 谎报
- 与 ADR-0001 / 0002 / 0003 解耦:本 ADR 撤销只触发 0002 改实现,不动归因算法和 sink 格式

**负面**:
- **10% 阈值是猜的**:无行业数据背书,阶段 4 实测可能太严或太松
- **真节点测才准**:本 PoC 用 mock 节点(节点开销极低),proxy 占比被放大;阶段 4 真节点压测才是 ground truth
- **自报代码侵入 proxy hot path**:每秒一次 CPU 采样有 sub-percent 开销

**最小 PoC 实测对比**(2026-05-27):
- proxy CPU 峰值 172%(1.72 core)@ 6.8k QPS
- mock 节点 CPU 几乎为零(就返回固定 JSON)
- **比例计算无意义**(mock 节点放大占比)
- **阶段 4 真节点必复测**:真 solana 节点 8-16 core 满负载时,1.72 core proxy ≈ 节点的 10-20%,**接近撤销线**

## 后续工作

- 阶段 4 完整 PoC:**第 1 优先级**做真节点 CPU 比例实测
- 若超 10% 阈值:
  - 先优化(io.TeeReader / buffered CSV / 必要时换 fasthttp,详见 REPORT.md §7)
  - 仍超则撤销 ADR-0002 转 nginx+lua 或 Rust+tokio
- 加 proxy 自身指标 endpoint(/metrics)便于 Prometheus 拉

## 关联

- NORTH-STAR.md §3 Q4-10
- ADR-0001 / 0002 / 0003(本 ADR 与上述独立,撤销不联动)
- tools/proxy/poc-min/REPORT.md §6(撤销线对比)
- analysis-notes/research_notes/07-per-method-resource-attribution-via-proxy.md §5
- OPEN-QUESTIONS.md(OQ-8 已锁)
