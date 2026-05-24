# P2 执行总日志

## 决策记录

| 决策 | 时间 | 选择 | 理由 |
|---|---|---|---|
| 测试规则颗粒度 | 2026-05-23 | 用既有 single/mixed mode,28 链全跑通 | 项目北极星 = QPS benchmark,不是 method matrix |
| endpoint 来源 | 2026-05-23 | A 公链优先 | 用户确认 |
| chain template 格式 | 2026-05-23 | **JSON 不动** + `_comment` 字段 + schema 校验 + pre-commit | 现有 155 处 jq,改 yq 风险高;可读性靠 schema 校验和注释字段补 |
| 决策模式 | 2026-05-23 | A 全自动 + 5 停手条件 + exec-log | 用户确认 |

## 5 停手条件(强制)

1. 任何 wave L3 e2e 未全过 → 停
2. > 3 链同时公链不可达 → 停(网络问题非代码)
3. 8 链回归 diff ≠ 0 → 立即停 S1
4. 修 bug 涉及改 `core/master_qps_executor.sh` 或 `tools/audit_rpc_methods.py` → 停(核心引擎需 review)
5. 出现 v2/defer 倾向 → 停(no-deferred-bugs)

## Wave 索引

| Wave | 内容 | 状态 | commit | exec-log |
|---|---|---|---|---|
| S0 | baseline + 设计 | ✅ 完成 | — | wave-S0-baseline.md |
| S1.1 | 8 链 JSON 拆出 + hook 改造 | 待 | — | — |
| S1.2 | 8 链回归实测 L3 | 待 | — | — |
| S1.3 | S1 commit | 待 | — | — |

## 整体进度

- 28 链调研 P1-2 ✅ (head=ffbeeee)
- P2 plugin 化:S0/S1/S2/S3/S4 共 ~13-17 wave 预估
