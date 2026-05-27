# CURRENT-STATE — 现状基线快照

> **状态**:快照(高频更新,**不算决策**)
> **作用**:记录框架当前实施状态,供 session 重启 / 新人快速了解"现在做到哪了"。
> 与 `NORTH-STAR.md`(锁定决策)分离,避免每次实施进展污染 NORTH-STAR 的 git diff。
> **本文档可以随时改,不需要 ADR**。

---

## 1. 基线 commit

- **当前 head**:`face2ac`(2026-05-27,S3-E.4 tezos)
- **远端同步状态**:本地与 `origin/main` 同步,无本地领先 commit
- **分支模型**:目前 main 直推为主;NORTH-STAR / 架构文档改走 feature branch + PR

---

## 2. 36 链 adapter 现状(L1 测试矩阵)

**总计**:36 链 chain template,**12 healthy / 24 known-broken**

### Healthy(12):L1 测试 PASS,可拼出 vegeta target
```
algorand   aptos     base      bsc
ethereum   hedera    polygon   scroll
solana     starknet  sui       tezos
```

### Known-broken(24):L1 测试有 ledger 记账
- **F1**(1):`ton` — 公开 endpoint URL 路径需 hash,H8 实证 404
- **F3 NOADDR**(21):需要专用地址池但未注入(待 fetcher 补支持或地址池建设)
- **F4**(2):`cardano` / `near` — 协议特殊性,adapter 未覆盖
- **KNOWN_BROKEN_MIXED**(2,与上面 24 部分重叠):
  - `hedera`:PARAM + ADDR_FMT 双重问题
  - `tezos`:`operations` method MULTI_PLACEHOLDER 待 RestAdapter v2

详见 `tests/test_chain_adapters.py` 中的 `KNOWN_BROKEN_CLI` / `KNOWN_BROKEN_MIXED` 集合。

---

## 3. fetcher 现状(`tools/fetch_active_accounts.py`)

**仅 8 链支持**,与 audit matrix 覆盖一致:
```
solana   ethereum   bsc        base
scroll   polygon    starknet   sui
```
其余 28 链 `raise ValueError: Unsupported chain type`。

**含义**:即使 adapter healthy(如 algorand / aptos / hedera / tezos),
端到端跑 benchmark 仍卡在 fetcher 不支持,**无法真正出报告**。
fetcher 28 链扩展是阶段 5 必修项(L1 测试已通,但 e2e 跑不通)。

---

## 4. method audit 现状(`docs/audit/method-status-matrix.md`)

**覆盖 8 链 × 51 method 的 4 层证据校验**:
- L1 doc 判别(URL 是否 deprecated)
- L2 doc cURL 实证(打 mainnet 验 method 可用)
- L3 schema 比对(对 tier-mid+ method 验 adapter 字段在 response 里)
- L4 错误传递语义(对 tier-high method 用故意非法 input 触发 error)

**结果**:29 PASS / 16 P1_RPC_ERROR / 6 P1_NOT_IN_SPEC

**含义**:audit 是 method 静态正确性,与 adapter L1 测试**职责正交**
(详见 NORTH-STAR 决策溯源 + 历史 session Q3 解答)。
两套 ledger 目前**无 join 视图**,这是 P1 缺口(归阶段 5 修)。

---

## 5. monitoring 层现状

**已实现**:
- `monitoring/unified_monitor.sh` — 节点级聚合监控,字段含 CPU / MEM / EBS / Network / ENA / 区块高度 / QPS
  (字段总数 README 写 79、architecture-overview-zh 写 73,**以代码实查为准**,待 1-A 架构文档统一对齐)
- `monitoring/bottleneck_detector.sh` — 实时瓶颈检测,5 场景判断逻辑
- `monitoring/cgroup_collector.py` / `k8s_api_client.py` / `kubelet_stats_client.py` — K8s/cgroup 支持
- `monitoring/ena_network_monitor.sh` — AWS ENA 深度监控
- `monitoring/block_height_monitor.sh` — 区块链健康跟踪

**缺失**:**所有字段都是节点级聚合,无 method 维度 label**(NS-2 待实施)

---

## 6. analysis / visualization 现状

**已实现**:
- `analysis/qps_analyzer.py` — 解析 vegeta json + 节点 monitor 时序,出节点级 QPS / latency / success rate
- `analysis/comprehensive_analysis.py` — 多维度综合分析
- `analysis/cpu_ebs_correlation_analyzer.py` — CPU-EBS 关联分析
- `visualization/` — 节点级图表生成器(README 称 32 图表,**具体数量以代码实查为准**)
- `visualization/report_generator.py` — 双语 HTML 报告框架

**缺失**:**所有分析都是节点级聚合,无 method 维度 group_by**(NS-2 待实施)

---

## 7. mixed mode 当前行为(已知错配)

- **docs `blockchain-testing-features-zh.md` 写**:"40% / 30% / 20% / 10%" 权重分布
- **实际代码 `tools/target_generator.sh` L254**:`account_index % method_count` round-robin(均匀分布)
- **chain template `rpc_methods.mixed`**:只支持逗号分隔 method 列表,**无 weight 字段**

**含义**:weight 配置完全未实现,docs 是设计意图。NS-2 阶段 1 设计 + 阶段 4 实施补齐。

---

## 8. 已 push 到 main 的历史(本 session 之前)

```
face2ac  fix(tezos): switch single to balance + add rest_paths (S3-E.4)
e3ae757  [cli-param-bug] fix cli.py 3 bugs + Gate 4 + ledger reset 13→25
c9ca754  S3-E.3-followup: hedera_dual 真实证 + adapter 单测 + KNOWN_BROKEN_MIXED 立 ledger
```

**说明**:这 3 个 commit 当时直推 main(未走 PR),用户已接受既往不咎。
**自 NORTH-STAR 落地起,所有高 stake 文档 / 架构改动走 feature branch + PR**。

---

## 9. 已识别污染源(阶段 0 待修)

| ID | 污染 | 严重度 | 阶段 |
|---|---|---|---|
| P0-1 | README 写 8 链,实际 36 链 chain template | 🔴 P0 | 0-B |
| P0-2 | KNOWN_BROKEN_CLI vs method-status-matrix 两套 ledger 无 join 视图 | 🔴 P0 | 5 |
| P0-3 | 无 SSOT 指明北极星 → 本 NORTH-STAR 文档落地后修复 | 🔴 P0 | **0-A 已修** ✅ |
| P1-1 | blockchain-testing-features-zh "40/30/20/10" 是设计未实现 | 🟡 P1 | 0-C |
| P1-2 | `tools/chain_adapters/` 7 文件无 file-notes 文档 | 🟡 P1 | 6 |
| P1-3 | `_archive_v1.4/` 命名模糊(当前已 v1.4+) | 🟡 P1 | 0-E |
| P1-4 | 中英 docs 12 份未做同步性 diff | 🟡 P1 | 6 |
| P2-1 | 73 vs 79 字段两个口径并存 | ⚪ P2 | 1-A |
| P2-2 | `configuration-guide-zh.md` + `data-architecture-zh.md` 未通读 | ⚪ P2 | 0-D |

---

## 10. 更新规则

- 本文档可以随时改,**不需要 ADR**
- 每次实施进展(adapter wave 完成 / 污染修复 / PoC 验证 等)应**同步更新本文档**
- NORTH-STAR.md 的决策**不进本文档**;本文档的快照**不进 NORTH-STAR.md**

---

**当前快照时间**:2026-05-27 session
**下次预期更新**:阶段 0-B README 校正完成 / 阶段 1 架构文档 review 通过 / 阶段 4 PoC 节点
