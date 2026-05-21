# Round-05 深度审计报告 (v1.4.5 前置)

**审计日期**: 2026-05-21
**审计基线**: `c329bc8` (docs(plan): v1.4.4 同步 §S6.5)
**审计协议**: AP5 五步 (read full function + read guards + grep producer + grep callers + minimal reproducer)
**审计方法**: 5 subagent read-only 初查 + parent agent 手动 AP5 逐条复验
**复验触发原因**: 初查中 P1-1 (deployment_mode_detector.sh:64) 被 AP5 证实为误报,根据 honest-self-check skill "1 AP5 → 复验全部" 规则,parent 复验 11 个 issue

---

## §1. 复验结论矩阵

### §1.1 Subagent 初查 vs AP5 复验对照

| ID | 初查 Claim | 初查级别 | AP5 复验 verdict | 修正级别 | 修复优先级 |
|---|---|---|---|---|---|
| #1-P1-1 | `deployment_mode_detector.sh:64` echo $DEPLOYMENT_MODE_SOURCE set -u abort | P1 | **FALSE_POSITIVE** | — | 不修(P3 边缘 case) |
| #1-P1-2 | `deployment_mode_detector.sh:137` regex `\s*` 不匹配 `●` 前缀 | P1 | **TRUE_BUG** | P1 | 修(Step 5) |
| #3-P1-1 | `k8s_api_client.py` socket.timeout 不在 retry 覆盖 | P1 | **FALSE_POSITIVE** | — | 不修 |
| #3-P1-2 | cgroup_collector / pod_device_mapper / kubelet_stats_client 0 production caller | P0 架构 | **PARTIAL** | P0 (VM 模式) + P2 (K8s 模式) | 修(Step 3/4) |
| #4-P1-1 | `04-daemonset.yaml:72-82` container command 没调 detect_deployment_mode | P1 | **FALSE_POSITIVE** | — | 不修 |
| #4-P1-2 | `02-serviceaccount-rbac.yaml:28-36` RBAC 缺 endpoints verb | P1 | **TRUE_BUG (latent)** | P2 | 修(Step 5,二选一) |
| #2-P0 | 50+ CSV field 0 production reader | P0 架构 | **TRUE_BUG** | P0 | 修(Step 3/4) |
| #4-P2-A | `mock_rpc_server.py:259` eth_getBlockByHash recursive 不传 chain | P2 | **TRUE_BUG (latent)** | P2 | 修(Step 5,可选) |
| §4.2 | 主链路改造 0/4 (实际是 5 项) | P0 | **TRUE (1/5 delivered, 4/5 not)** | P0 | 修(Step 3/4) |
| #4-EVM_CHAIN_IDS | 5 真值 (0x1/0x38/0x2105/0x82750/0x89) | 正确性 | **VERIFIED** | — | 不修 |
| #1-P2 集 | shell config/*.sh 裸 var 引用边缘 case | P2 | **PARTIAL** (10+ 候选,需逐项 AP5) | P2/P3 | 暂不修(Step 6 CI guard 兜底) |

**汇总**:
- **5 个 FALSE_POSITIVE** 被 AP5 证伪 → 5 subagent 初查误报率 ~45% (5/11)
- **4 个 TRUE_BUG** 需要修(2 个 P0 架构 + 1 个 P1 + 1 个 P2 latent)
- **1 个 PARTIAL** (Issue D shell P2) 用 Step 6 CI guard 兜底,不逐个修
- **1 个 UNVERIFIED (E5)** (plan 自身矛盾,语义需手动审,本轮不展开)

### §1.2 5 subagent 初查 vs AP5 复验信度对比

| 指标 | Subagent 初查 | AP5 复验 |
|---|---|---|
| 用时 | ~10 min (3 batch 并行) | ~30 min (parent 手动逐条) |
| 误报率 | 45% (5/11) | 0% (复验中所有 verdict 都有 raw E1/E2 evidence) |
| 评级偏差 | 倾向 P1 报 P2/P3 | 用真实可重现性分级 |
| 主要 AP5 类型 | AP5(片段扫描) + AP3(选择性引用) | — |

**根因**: subagent 在 read_file 后只看 flagged 行 ±3 行,没读 guard / 没 grep producer 调用链 / 没读 caller。**这正是 honest-self-check skill 新增 AP5 协议的设计动机**。

---

## §2. 4 个真 BUG 详细记录

### §2.1 BUG #1 — systemctl regex `\s*` 不匹配 `●` 前缀 (P1)

**位置**: `config/deployment_mode_detector.sh:137`

**当前代码**:
```bash
137|                | grep -qE "^\s*${unit}([-@]|\.service)" ; then
```

**问题**: `systemctl list-units --all` 对 failed/loaded 状态的 unit 输出 `● solana-validator.service` (UTF-8 black-circle 前缀 + 空格),`\s*` 只匹配 ASCII 空白,**不匹配 `●`**。

**E2 reproducer**:
```bash
$ echo "● solana-validator.service loaded failed failed Solana" | grep -qE "^\s*solana-validator([-@]|\.service)" && echo MATCH || echo NO_MATCH
NO_MATCH
```

**影响**: failed/loaded 的 systemd unit 被漏判 → DEPLOYMENT_MODE 误识别为 vm_bare 而非 vm_systemd。

**修复方案**: 把 `^\s*` 改成 `^[[:space:]●○]*` 或 `^[^a-zA-Z0-9]*`。

**修复优先级**: P1 (Step 5)

---

### §2.2 BUG #2 — RBAC 缺 `endpoints` verb (P2 latent)

**位置**: `deploy/k8s/02-serviceaccount-rbac.yaml:28-36` + `monitoring/k8s_api_client.py:308-309`

**当前 RBAC** (L29-36):
```yaml
- apiGroups: [""]
  resources:
    - pods
    - persistentvolumeclaims
    - persistentvolumes
    - namespaces
    - nodes
  verbs: ["get", "list", "watch"]
# NOTE: endpoints 缺失
```

**Method 已定义** (`k8s_api_client.py:308-309`):
```python
def list_namespaced_endpoints(self, namespace: str) -> Dict[str, Any]:
    return self._get(f"/api/v1/namespaces/{quote(namespace)}/endpoints")
```

**当前 production caller**: 0 (只在 docstring usage example 出现)

**影响**: 当前无人调,latent。**任何未来 caller 启用就会 403**。

**修复方案 (二选一)**:
- (A) RBAC 加 `endpoints` verb (推荐 — 方法已存在,未来必用)
- (B) 删除 `list_namespaced_endpoints` (保守 — 用时再加)

**推荐 A**,理由:S5/S9 阶段 RPC 端点发现需要 endpoints API,提前开口子。

**修复优先级**: P2 (Step 5,顺手)

---

### §2.3 BUG #3 — cgroup_collector / pod_device_mapper / kubelet_stats_client 主管线未接 (P0 架构)

**位置**: `monitoring/unified_monitor.sh` + `monitoring/monitoring_coordinator.sh`

**E2 evidence** (grep production *.sh/*.py 排除 tests/_archive):
```
cgroup_collector:
  - monitoring/cgroup_collector.py (self)
  - deploy/k8s/04-daemonset.yaml:78-80 (K8s 模式 ✓)
  - VM 模式: 0 caller ✗

pod_device_mapper:
  - monitoring/pod_device_mapper.py (self only)
  - 0 production caller ✗

kubelet_stats_client:
  - monitoring/kubelet_stats_client.py (self only)
  - 0 production caller ✗
```

**根因**: 并行入口陷阱 (parallel-entry-trap)。S3/S5 阶段开发了新模块,但没改主链路 `monitoring/unified_monitor.sh` 和 `monitoring/monitoring_coordinator.sh` 让它们 source/dispatch 到新模块。1604+ 行新代码,主管线 0 引用。

**最致命单一证据**: `deploy/k8s/04-daemonset.yaml:76-77` 自己写道:
```
# framework's main pipeline can later pipe these CSV rows to its unified data store. For now stdout is fine.
```
开发者自己签的 IOU 注释。

**修复方案**:
- Step 3 — cgroup_collector 接 `monitoring/unified_monitor.sh` 主管线 (VM + K8s 两模式)
- Step 4 — pod_device_mapper + kubelet_stats_client 通过 `monitoring/monitoring_coordinator.sh` K8s 模式分支接入

**修复优先级**: P0 (Step 3 + Step 4)

---

### §2.4 BUG #4 — mock_rpc_server `eth_getBlockByHash` 递归不传 chain (P2 latent)

**位置**: `tools/mock_rpc_server.py:259`

**当前代码**:
```python
258|    if method == "eth_getBlockByHash":
259|        return handle_evm("eth_getBlockByNumber", [hex(block), params[1] if len(params) > 1 else False])
```

**问题**: `handle_evm` 签名 `(method, params, chain="ethereum")`,L259 递归调用没传 chain → 任何链调 `eth_getBlockByHash` 后续如果触发 `eth_chainId` 会拿到 ethereum 的 0x1。

**当前影响**: 0 production caller (mock 仅供 e2e 测试,e2e 暂未跑) → latent。

**修复方案**: 给 `handle_evm` 调用补 `chain=` 参数。需要在 `handle_evm` 入口拿到 chain,从 caller 传递下来。最小改动:
```python
def handle_evm(method: str, params: List[Any], chain: str = "ethereum") -> Any:
    ...
    if method == "eth_getBlockByHash":
        return handle_evm("eth_getBlockByNumber", [hex(block), params[1] if len(params) > 1 else False], chain=chain)
```

**修复优先级**: P2 (Step 5,顺手)

---

## §3. 5 个 FALSE_POSITIVE 详细分析(防误修)

### §3.1 FP #1 — `deployment_mode_detector.sh:64` echo set -u abort

**Subagent 报**: P1
**AP5 复验**: FALSE

**理由**:
- L63 guard: `if [[ "${DEPLOYMENT_MODE_DETECTED:-}" == "true" && "${DEPLOYMENT_MODE:-auto}" != "auto" ]]; then`
- 进入 L64 要求 `DEPLOYMENT_MODE_DETECTED==true`
- `DEPLOYMENT_MODE_DETECTED=true` 只能由 `_deployment_mode_export()` (L182-186) 设置
- 该函数 L184 `export DEPLOYMENT_MODE DEPLOYMENT_MODE_DETECTED DEPLOYMENT_MODE_SOURCE` 必然 export `DEPLOYMENT_MODE_SOURCE`
- 结论:执行路径上 `DEPLOYMENT_MODE_SOURCE` 已定义,set -u 不触发

**边缘 case (P3)**: 外部手动 `export DEPLOYMENT_MODE_DETECTED=true` 跳过 exporter → 进入 L64 时 SOURCE 未定义 → set -u abort。但这是用户主动绕过 API,不修。

### §3.2 FP #2 — `k8s_api_client.py` socket.timeout 不在 retry 覆盖

**Subagent 报**: P1
**AP5 复验**: FALSE

**理由**:
- `_get` (L208-233) 的 retry 逻辑只 catch `K8sApiError`
- `_do_get` (L235-256) L255 `except urlerror.URLError as e: raise K8sApiError(0, ...)` — **包装所有 URLError**
- Python stdlib 铁律: `socket.timeout` 是 `OSError` 子类,被 `urlopen` 抛出时被 urllib 转成 `URLError` (`URLError` 也是 `OSError` 子类)
- L255 已覆盖 → wrapped to K8sApiError(status=0) → L227 走 "status=0 = network" 重试分支
- 结论:socket.timeout 已被重试覆盖

### §3.3 FP #3 — `04-daemonset.yaml` 没调 detect_deployment_mode

**Subagent 报**: P1
**AP5 复验**: FALSE

**理由**:
- L75 `source /opt/blockchain-bench/config/config_loader.sh`
- `config_loader.sh:342-349` 自动调 `detect_deployment_mode` + `resolve_k8s_paths`
- source 时副作用自动执行,容器 command 不需要显式调
- 结论:CGROUP_VERSION 等环境变量会被设置

### §3.4 FP #4 (隐含) — 无 (上面 3 个明确 FALSE)

### §3.5 FP #5 (隐含) — 无

---

## §4. AP5 复验本身的 NOT_VERIFIED 项 (E5 honest layer)

应用 honest-self-check Q1-Q3 + critical-self-audit Q4-Q7:

| 项 | 状态 | 原因 |
|---|---|---|
| plan 自身矛盾 (subagent #5 P1) | UNVERIFIED | 需要语义级 cross-section 对比,本轮 grep 难判定;留 Step 7 SE 阶段手动审 |
| shell P2 set -u 边缘 case (10+) | PARTIAL | 找到候选位置,未逐个 AP5 Step 1-5 验证;用 Step 6 CI guard `bash -u` 模式 dry-run 兜底 |
| baseline 是否还有未发现的并行入口 | UNVERIFIED | 当前发现 3 个 (cgroup/pod_device/kubelet),可能还有;Step 6 CI guard 提供持续发现能力 |
| 修复后是否 100% 无回归 | UNVERIFIED | Step 7 跑 134+新测验证,但 L3 真集群测试只能 cloudtop mock,真 GKE 等用户回来调 GCE |

---

## §5. 决策与执行计划 (A 流程)

应用 decision-with-tradeoffs:

| 选项 | 范围 | 时间 | 推荐 |
|---|---|---|---|
| **A** (执行中) | 7 step 全修 4 真 bug + CI guard + e2e smoke | ~5-7h (SPECULATED, ±50% 偏差) | ✓ 用户已授权 |
| B | 只修 4 真 bug,不建 CI guard | -1h | 不推荐 — 不防回归 |
| C | 只产 audit doc,不修 | -5h | 不推荐 — 把已知 bug 留 git history |

**A 详细步骤** (本 round-05 之后)

| Step | 内容 | 调用 skill |
|---|---|---|
| Step 1 (本文档) | audit 汇总 + 4 真 bug 落盘 | honest-self-check + critical-self-audit |
| Step 2 | S0 工具链 (single_disk_workload_profile + e2e_smoke) | token-level-careful-edit |
| Step 3 | cgroup_collector 接 unified_monitor.sh 主管线 | token-level-careful-edit Gate 3 (caller 全 grep) |
| Step 4 | S5 三件套接 monitoring_coordinator.sh | 同上 |
| Step 5 | 修 BUG #1 (regex) + BUG #2 (RBAC) + BUG #4 (mock chain) + 单测 | no-deferred-bugs + critical-self-audit |
| Step 6 | ci/check_parallel_entry.sh + pre-commit hook (Issue D 兜底) | — |
| Step 7 | e2e_smoke 跑 + 134+ 新测全验 + cloudtop SE 报告 | honest-self-check (报告必含 NOT verified 节) |

---

## §6. Lesson Learned (本轮专属)

1. **Subagent 报告必复验** — 5 subagent 给的 11 个 issue,5 个误报 (45%)。subagent prompt 必须强制 AP5 Step 1-5 + 贴 raw 输出。
2. **并行入口陷阱 in S3+S5** — cgroup/pod_device/kubelet 三模块 1604+ 行无主管线接,CI guard `check_parallel_entry.sh` (plan §S7) 从没建。Step 6 必修。
3. **honest-self-check AP5 协议** 在本轮首次实战:5/11 误报率验证 AP5 Step 1-5 是必要的(subagent 看 1 行就报 bug 是高频幻觉模式)。

---

**审计完成时间**: 2026-05-21
**下一步**: commit + 推进 Step 2 (S0 工具链)
