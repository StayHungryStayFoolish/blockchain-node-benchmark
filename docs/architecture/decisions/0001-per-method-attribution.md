# ADR-0001: per-method 资源归因算法 — monitor + proxy 旁路 + 离线 join

## 状态
Accepted(2026-05-27,commit `5338bba`)

## 背景

NS-2 要求支持 mixed RPC method workload 下的 **per-method 资源归因**(CPU / MEM / EBS / Net 按 method 维度拆分)。问题:

1. 真实 workload 是多 method 混跑(如 `getBalance` + `getBlock` + `getTransaction` 同时打)
2. 节点进程本身**只暴露聚合资源指标**,不区分"这 1% CPU 是哪个 method 烧的"
3. 行业内无 OOTB 解决方案(直接 ptrace / eBPF 注入 solana 进程不现实,工程量爆炸)
4. 用户必须能拿到 method 级图表 + 双语 HTML 报告,否则 NS-2 北极星不达标

OQ-3(OPEN-QUESTIONS.md 旧编号)= "per-method 归因怎么算",阻塞阶段 1 架构定型。

## 选项

- **选项 A:eBPF 注入节点进程**
  - 优:精度高,系统调用级别归因
  - 劣:工程量爆炸(需 BCC/libbpf 工具链 + 内核版本兼容 + 节点进程符号表),36 链每个节点都要适配 = 不可行
- **选项 B:节点内 RPC handler hook**(改节点源码)
  - 优:精度最高
  - 劣:36 链 = 36 个节点项目 fork,每次升级要 rebase = 不可维护
- **选项 C(选定):monitor 独立采集 + proxy 旁路记 method + 离线时间窗 join + 按 method 权重分摊**
  - monitor 进程独立采系统级聚合指标(CPU / MEM / EBS / Net)按 1s 采样
  - proxy 旁路记 `(ts_ns, method, latency_ns)` 进 CSV
  - 离线 join:每 1s 窗口内 group by method 求 method 调用次数 + 权重(qps × 单次成本档位)
  - 按权重比例分摊聚合资源给各 method
- **选项 D:无 proxy,client 端发 method 时记 trace + 节点端只采聚合**
  - 优:proxy 链路省一跳
  - 劣:client 与节点 clock skew + 网络 jitter = 时间窗 join 不准

## 决策

**选 C**。理由:
1. monitor 和 proxy 都不动节点本体 = **零侵入**,36 链通用
2. proxy 与节点同机 = **clock 一致**,时间窗 join 准
3. 权重表精度不够时可后期迭代(详见 Q4-7 权重源策略)— 决策本身不被 weight 表精度阻塞

**权重源策略**(Q4-7 子决策):
- 公开资料先配粗粒度 1/10/100 三档(便宜 method / 中等 method / 昂贵 method)
- 后期实测节点级日志或 profiling 数据迭代调整

## 后果

**正面**:
- 36 链通用,无需 fork 节点
- 实施门槛低,Go proxy + Python join 即可
- 权重表可迭代,不阻塞 PoC

**负面**:
- **精度依赖 weight 表**:weight 表不准 → 归因偏差;阶段 4 必须实测验证
- **时间窗 join 有窗口边缘误差**:1s 窗口内 method 比例 ≠ 1s 内瞬时资源分布;长 workload 下统计上可忽略,短 burst 不准
- **proxy 必须在 hot path**:节点直连 client 时无法归因

**撤销线**:per-method 归因误差 > **20%** → 撤销本决策,转选项 B(fork 节点 hook)

**后续工作**:
- 阶段 4 完整 PoC 实测归因精度(真节点 + 真 workload + ground truth 对比)
- 阶段 5 36 链 weight 表分链补
- 若撤销线触发,启动 Plan B 评估

## 关联

- NORTH-STAR.md §3 Q4-7
- analysis-notes/research_notes/07-per-method-resource-attribution-via-proxy.md §2
- docs/architecture/per-method-proxy-architecture-zh.md(1-A)
- OPEN-QUESTIONS.md(OQ-3 已锁)
