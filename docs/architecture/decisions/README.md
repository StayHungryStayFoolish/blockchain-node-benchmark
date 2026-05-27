# Architecture Decision Records (ADR)

每当 NORTH-STAR.md 决策表发生变更时,本目录新增一份 ADR 记录决策背景。

## ADR 文件命名

`NNNN-<short-name>.md`,NNNN 为 4 位编号(0001 起)

## ADR 模板

```markdown
# ADR-NNNN: <决策标题>

## 状态
Proposed / Accepted / Deprecated / Superseded by ADR-XXXX

## 背景
为什么要做这个决策?触发条件是什么?

## 选项
- 选项 A:...
- 选项 B:...
- 选项 C:...

## 决策
选定方案 + 一句话理由

## 后果
- 正面影响
- 负面影响
- 后续工作
```

## 当前 ADR 索引

| 编号 | 标题 | 状态 | commit |
|---|---|---|---|
| [ADR-0001](0001-per-method-attribution.md) | per-method 资源归因算法 — monitor + proxy 旁路 + 离线 join | Accepted | `5338bba` |
| [ADR-0002](0002-proxy-implementation.md) | proxy 实现 — Go 反向代理 + 流式 JSON decoder 提 method 字段 | Accepted | `9e52ead` |
| [ADR-0003](0003-sink-format.md) | sink 格式 — CSV(ts_ns, method, status, latency_ns) | Accepted | `9e52ead` |
| [ADR-0004](0004-proxy-overhead.md) | proxy 自身开销 — 目标 < 节点 CPU 10% | Accepted | `9e52ead` |

> 备注:NORTH-STAR.md 初始决策表(commit `7921b71`)作为 baseline 不写 ADR;
> baseline 之后的决策变更必须写 ADR。

