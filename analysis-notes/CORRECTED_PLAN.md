# CORRECTED_PLAN.md — GCP 兼容性改造执行手册

> **本文件用途**：把 `02-GCP-MIGRATION-TRACKER.md` 的 109 行阻塞点 + 64 字段 + 75 输出文件 + 命名中立化清单，**重组成可执行的代码改造手册**。
>
> **目标**：按依赖顺序逐步改代码，每一步都可独立验证，零业务功能回归。
>
> **基线**：commit `e843571`（业务代码当前未动）  
> **来源**：`02-GCP-MIGRATION-TRACKER.md` §1/§2/§3/§10 + `early-morning-report.md` §11.3（Phase 7.5 新发现 5 阻塞点）  
> **改造策略**：B+（utils → monitoring → tools → analysis → viz）  
> **命名策略**：A+A（全字段中立化 + 输出文件名 platform-aware + utils/field_normalizer.py 读时归一化层）

---

## 总览：6 大改造阶段

| 阶段 | 范围 | 依赖 | 工作量估算 | 改造文件数 |
|---|---|---|---|---|
| **CP-0** | 前置：fake-target stack + GCP probe + config/cloud_provider.sh 抽象层 + config/providers/{aws,gcp,other}_provider.sh + tests/test_provider_contract.sh | 无 | 1.5d | 7 新增 |
| **CP-1** | utils/ 层：cloud_provider/disk_converter/field_normalizer/unified_logger | CP-0 | 2d | 5 改 + 1 新 |
| **CP-2** | config/ 层：system_config/user_config/config_loader 中立化 + GCP 分支 | CP-1 | 2d | 4 改 |
| **CP-3** | monitoring/ 层：unified_monitor (CSV header) + ena_network_monitor → gvnic_network_monitor + bottleneck_detector | CP-2 | 3d | 7 改 + 1 新 |
| **CP-4** | tools/ 层：ebs_analyzer/ebs_bottleneck_detector → disk_*；benchmark_archiver 输出文件名 platform-aware | CP-3 | 2d | 6 改 |
| **CP-5** | analysis/ + visualization/：双写字段；device_manager/report_generator/_categorize_charts 等 5 个 Phase 7.5 新阻塞点 | CP-4 | 3d | 10 改 |
| **CP-6** | 收尾：清理 AWS_ alias / 完整 GCP E2E 回归 / 文档更新 | CP-1..5 | 1d | 全仓 |

**总工作量估算**：~14 工作日（单人）；并行 3 worker 可压到 5-6 工作日

**Phase E-1 增量 LOC 明细（CP-0 重构，零业务代码改动）**：
- CP-0.1 `config/cloud_provider.sh` 抽象层入口：~80 LOC（detect + factory + export-f 批量化 + contract check）
- CP-0.4 `config/providers/{aws,gcp,other}_provider.sh`：~80 LOC × 3 ≈ 240 LOC（纯 bash getter 实现，15 getter / provider）
- CP-0.5 `tests/test_provider_contract.sh` 契约测试：~80 LOC（45 项检查，含 AWS≠GCP 防抄断言）
- 合计：~400 LOC 新增脚本 + ~600 行 PLAN 文档扩展（CP-0 章节 528 → ~1130 行）

---

## §0 E1 Provider 抽象层架构说明

> **本章节用途**：在进入 CP-0 ~ CP-6 业务改造手册之前，统一说明 **E1 方案**（VFS-like Provider 抽象层）的设计动机、架构总览、接口契约、source 责任链、阻塞点结构性消除映射、Phase E 执行路线图、5 个关键设计决策与 ROI 评估。
>
> **来源**：`analysis-notes/E1-assessment.md`（358 行全量影响评估）；本章节为**手册级落地版**，CP-0 ~ CP-6 的具体改造步骤均假定本架构已就位。
>
> **本章节落地后业务代码 diff**：**0 行**（§0 只是文档约定，实际代码落地在 Phase E-1 起的 CP-0 重构）。

---

### §0.1 设计动机（Why E1+）

**架构哲学（E1+ 升级）**：本项目目标是同一框架在 AWS EC2 与 GCP GCE 上跑公平的 benchmark 对比，因此 **AWS / GCP / Other 在架构上完全对等**。原项目只考虑 AWS + other 二分（项目作者初版），现入职 GCP 后需修正为三平台平权。具体落实为 3 条不可妥协的设计准则：

1. **配置一等公民**：平台抽象层入口放 `config/cloud_provider.sh`（不放 utils/），因为平台选择是**用户可见的配置决策**，不是隐式工具。
2. **平台对等性**：providers/ 下三个文件 `aws_provider.sh` / `gcp_provider.sh` / `other_provider.sh` 完全对等，无主从。任何 `${CLOUD_PROVIDER:-aws}` 隐式默认值都是反模式。
3. **性能对比公平性**：字段命名（如 `_aws_standard_iops`）必须通过 `get_disk_field_prefix()` 抽象，否则 GCP 数据塞 AWS 字段导致对比图表失真。

**旧方案（V1.0 / 直接进 R 期）的结构性问题**：

1. **21 处 `case "$CLOUD_PROVIDER"` 散落全 PLAN**（详见 E1-assessment.md §1.1），分布于 CP-0 ~ CP-5 各章节，每加一个云平台都要重审全文。
2. **`${CLOUD_PROVIDER:-aws}` 隐式 AWS default 共 12 处**，让新读者误判项目"偏向 AWS"，违背 GCP 兼容性改造的**平台中立**初衷。
3. **§13.2 source 顺序冲突** 在 V1.0 路线下只能用 "re-evaluate hook" / "lazy getter" 等设计妥协 workaround，**治标不治本**（system_config.sh 首次 source 时 `CLOUD_PROVIDER=auto` 落 AWS 默认分支，detect_deployment_platform 后置无人重新触发 case → 4 个变量永久错误）。
4. **字段名硬编码 `_aws_standard_*`**（§13.6 / §13.12 两个 P0）散布 writer/reader 两端，未来加字段成本翻倍。
5. **加新云平台代价巨大**：例如要加 Azure，必须改全 PLAN 21 处 case + 5 个 P0 阻塞点重新评估 + 业务代码 LOC 增加 ~80 行。

> **E1+ 同时解决以上 3 个老问题 + 用户提出的架构哲学诉求**：相比旧 E1 把抽象层放 utils/、容忍隐式 AWS default，E1+ 把入口搬到 config/（用户 grep config/ 一次发现）、禁止隐式默认（强制 detect 或显式 export）、AWS/GCP/Other 在目录布局与字段命名上完全对等。

**E1+ 解法（VFS-like 抽象层 + 对等 driver + config 一等公民）**：

- 抽象层（`config/cloud_provider.sh`）只做 **detect + factory + 接口规范**，不带任何云特定逻辑。⭐ 入口在 config/
- 实现层（`config/providers/{aws,gcp,other}_provider.sh`）**对等平权**，每个文件 ~80 行实现全部 15 getter；目录命名、文件命名、getter 命名均无 AWS bias。
- 业务代码 100% 平台中立：从 `case "$CLOUD_PROVIDER"` 改为 `$(get_metadata_endpoint)` getter 调用；**禁止 `${CLOUD_PROVIDER:-aws}` 隐式默认值**，未 detect 时必须 fail-fast。
- **加新云只需 1 个 provider 文件**（例如 `azure_provider.sh`），业务代码零变动，contract test 自动验证 15 个 getter 都实现且 AWS/GCP 返回值不同（防抄）。
- **5 个阻塞点结构性消除**（§13.2 / §13.5 / §13.6 / §13.12 / §13.21），P0 总数从 9 降至 5（-44%）。

**最佳介入时机**：当前业务代码（commit `e843571`）`CLOUD_PROVIDER` 引用数 = **0**（所有引用都还在 PLAN 文档待落地），这是引入抽象层零迁移成本的窗口；一旦 R 期把 case 句式固化进 commit，再抽 provider 成本将翻倍（业务代码动两次）。

---

### §0.2 架构总览

**目录与责任分工（E1+ — config 一等公民）**：

```
config/cloud_provider.sh                 ← 抽象层入口（detect + factory + 接口规范）⭐ 入口在 config/
config/providers/aws_provider.sh         ← AWS 15 getter 实现 (~80 行)
config/providers/gcp_provider.sh         ← GCP 15 getter 实现 (~80 行)
config/providers/other_provider.sh       ← 通用 fallback 15 getter 实现 (~80 行)
config/system_config.sh                  ← 业务方（调 getter，不再定义 case）
config/user_config.sh                    ← 业务方（调 getter，不再定义 case）
config/config_loader.sh                  ← 全局加载入口（L1-10 source config/cloud_provider.sh 兜底）

utils/cloud_provider.py                  ← Python 侧 facade（analysis/ + visualization/ 消费）
tests/test_provider_contract.sh          ← 契约测试（15 getter × 3 provider + AWS≠GCP 防抄断言）
```

**source 责任链 ASCII 架构图**：

```
   ┌────────────────────────────────────────────────────────────────┐
   │  业务文件 (monitoring/ / tools/ / analysis/ / config/*)         │
   │     │                                                          │
   │     │  source "${PROJECT_ROOT}/config/config_loader.sh"        │
   │     │  （config_loader.sh:L1-10 全局兜底 source 抽象层）         │
   │     ▼                                                          │
   ├────────────────────────────────────────────────────────────────┤
   │  config/cloud_provider.sh  (抽象层 — VFS 入口) ⭐ 在 config/      │
   │     │  1. source guard:                                         │
   │     │     [[ -n "${CLOUD_PROVIDER_DETECTED:-}" ]] && return 0   │
   │     │  2. detect_cloud_provider() → CLOUD_PROVIDER∈{aws,gcp,    │
   │     │     other}  (IMDS probe / env override / fail-fast)       │
   │     │     ⚠ 禁止 ${CLOUD_PROVIDER:-aws} 隐式默认                  │
   │     │  3. export CLOUD_PROVIDER PLATFORM_DISPLAY_NAME            │
   │     │  4. source "${PROJECT_ROOT}/config/providers/              │
   │     │            ${CLOUD_PROVIDER}_provider.sh"                  │
   │     │  5. for f in "${REQUIRED_GETTERS[@]}"; do export -f "$f"   │
   │     ▼                                                          │
   ├────────────────────────────────────────────────────────────────┤
   │  config/providers/${CLOUD_PROVIDER}_provider.sh  (实现层)        │
   │     │  AWS / GCP / Other 三平台对等，无默认/主从关系              │
   │     │  无 source guard（永远只被抽象层 source 一次）              │
   │     │  实现全部 15 个 getter 函数:                                │
   │     │     get_metadata_endpoint(), get_metadata_header(), ...    │
   │     ▼                                                          │
   │  全部 getter 已就位，子进程通过 export -f 继承                    │
   └────────────────────────────────────────────────────────────────┘
```

**为什么抽象层入口在 config/ 而非 utils/（E1+ 关键决策）**：

- **语义对齐**：`utils/` 语义是「无状态工具函数」（如字符串格式化、单位换算）；平台抽象层是**配置决策**（涉及业务行为差异、字段命名差异、IO baseline 差异），不属于工具。
- **新人发现性**：新人 onboarding 路径是 `README → config/ → utils/`，把入口放 `config/` 让 GCP 兼容性「一眼可见」；用户工作流 `grep -r GCP config/` 必须能命中入口。
- **locality 原则**：providers/ 实现已经在 `config/providers/` 下，入口跨目录（utils/ → config/providers/）违反 locality；入口与实现同目录便于一次 `ls config/` 看清全貌。
- **Python facade 例外**：`utils/cloud_provider.py` 保留在 utils/ 是合理的——它是 analysis/ + visualization/ 的**只读消费方**（从 `os.getenv('CLOUD_PROVIDER')` 读取已 detect 结果），不参与 detect/factory，属于纯工具函数。

**关键约束（E1+ 平台对等性）**：

- **业务文件永远不直接 source `config/providers/*_provider.sh`**，统一走 `config/cloud_provider.sh`。
- **抽象层是唯一 detect 入口**，禁止任何业务文件自行 `curl IMDS`（避免 §13.5 metadata header 缺失 + 1s timeout 浪费）。
- **export -f 必须批量执行**，否则 vegeta / iostat 等 fork 子进程拿不到 getter。
- **禁止 `${CLOUD_PROVIDER:-aws}` 隐式默认**：未 detect 场景必须 `${CLOUD_PROVIDER:?CLOUD_PROVIDER not set, run config/cloud_provider.sh first}` 强制 fail-fast。
- **AWS / GCP / Other 在目录层、命名层、字段层完全对等**：无任何 `if aws ... else ...` 二分结构，统一三分支 / dispatch dict。

---

### §0.3 抽象接口规范（15 个 getter 完整签名表）

下表为 E1+ 抽象层的**完整契约**。3 个 provider 文件（aws/gcp/other）必须全部实现，否则 `tests/test_provider_contract.sh` 失败。表格在 `E1-assessment.md §2`（行号 60-76）基础上**修订 Other 列以贯彻平台对等原则**（Other = 「未知平台的中立 fallback」，不再是「AWS 的降级版」）。

| # | 函数签名 | AWS 返回值 | GCP 返回值 | Other 返回值（E1+ 中立化） | 调用方 (来自 E1-assessment.md §1 表格) |
|---|---|---|---|---|---|
| 1 | `get_metadata_endpoint()` | `http://169.254.169.254` | `http://metadata.google.internal` | `""`（未知平台无 IMDS） | #5 (CP-2.1.2) + config_loader.sh detect (#11/12) |
| 2 | `get_metadata_header()` | `""` | `Metadata-Flavor: Google` | `""`（明确：通用平台无 IMDS header） | #5 + 所有 metadata curl 调用点 |
| 3 | `get_metadata_api_path()` | `latest` | `computeMetadata/v1` | `""`（未知，调用方需判空） | #6 (CP-2.1.3) |
| 4 | `get_baseline_io_kib()` | `16` | `4` | `0`（未知，调用方需处理） | #7 (CP-2.1.4) + utils/disk_converter.sh |
| 5 | `get_baseline_throughput_kib()` | `128` | `256` | `0`（未知，调用方需处理） | #3 (CP-1.1 L7) |
| 6 | `get_default_disk_type()` | `gp3` | `hyperdisk-extreme` | `""`（中立空值，不偏 AWS） | user_config.sh 注释; 未来 sanity check |
| 7 | `get_disk_type_options()` (echo 空格分隔列表) | `gp3 io2 instance-store` | `pd-balanced pd-ssd pd-extreme hyperdisk-extreme local-ssd` | `""`（空集 — 未知平台不预设盘类型） | CP-2.2 VOL_TYPE 枚举校验 + CP-2.2.4 needs_calc 判断 (#10) |
| 8 | `get_nic_driver()` | `ena` | `gve` | `""`（未知 NIC driver） | CP-3.2 (#15) `ethtool -i` 校验时使用 |
| 9 | `get_nic_allowance_fields()` (echo CSV) | `bw_in_allowance_exceeded,bw_out_allowance_exceeded,pps_allowance_exceeded,conntrack_allowance_exceeded,linklocal_allowance_exceeded,conntrack_allowance_available` | `""`（GCP gvnic 无 allowance 概念） | `""`（中立空集） | #13 (CP-2.3.4) + #14 (CP-3.2 utils/nic_metrics.sh) |
| 10 | `get_nic_monitor_process_name()` | `ena_network_monitor` | `gvnic_network_monitor` | `""`（无平台特定 monitor） | #8 (CP-2.1.5 filter_platform_processes) |
| 11 | `get_disk_field_prefix()` | `aws_standard` | `baseline` | `standard`（中立命名，不偏 AWS） | §13.6 / §13.12 (unified_monitor.sh:144 + iostat_collector.sh:144) |
| 12 | `get_archive_dir_prefix()` | `aws_run_` | `gcp_run_` | `run_`（保持） | #18 (CP-4.3 benchmark_archiver.sh L219) + §13.19 reader |
| 13 | `get_bottleneck_label()` | `EBS` | `Disk` | `Disk`（保持，与 GCP 同——通用语义） | §13.21 (CP-5.7.2) + §13.13 console 文案 |
| 14 | `get_platform_display_name()` | `AWS` | `GCP` | `OTHER` | CP-0.1 内部 + #18 fallback chain |
| 15 | `get_doc_url(category)` | AWS doc URL | GCP doc URL | `""`（无平台特定文档） | #4 (CP-1.1 L25/L31/L83) — 参数化 doc 分类 |

**E1+ Other 列修订原则**：
- Other 不是「AWS 的降级版」，是「未知平台的中立 fallback」。
- 涉及 AWS 特有概念（如 ENA allowance / `_aws_standard_*` 字段前缀 / IMDS endpoint）的 getter，Other 必须返回**中立值或空集**，**禁止继承 AWS 默认值**。
- 调用方负责判空：`endpoint=$(get_metadata_endpoint); [[ -z "$endpoint" ]] && { log_warn "no metadata endpoint on Other platform, skip probe"; return 0; }`
- contract test 不仅验证「getter 存在 + 返回非空」，还断言「AWS 返回值 ≠ GCP 返回值」（防 GCP getter 抄 AWS 实现）。

**Python 侧并行接口**（`utils/cloud_provider.py`，与 `.sh` 同名同义，analysis/ + visualization/ + utils/field_normalizer.py 消费）：

```python
from utils.cloud_provider import (
    get_cloud_provider,
    get_disk_field_prefix,
    get_bottleneck_label,
)
# 通过环境变量 CLOUD_PROVIDER 读，不重复 IMDS 探测（detect 已由 bash 抽象层完成）
# 内部实现：os.environ['CLOUD_PROVIDER'] (KeyError if未 set — fail-fast，禁止隐式 default)
#          + dispatch dict {aws: ..., gcp: ..., other: ...}
```

---

### §0.4 source 契约

**source guard 规则（E1+ 入口在 config/）**：

| 文件 | 是否有 source guard | 理由 |
|---|---|---|
| `config/cloud_provider.sh` (抽象层入口) ⭐ | **有** — 顶部 `[[ -n "${CLOUD_PROVIDER_DETECTED:-}" ]] && return 0` | 业务文件可能多次 source，幂等保证不重复 detect / 不重复 export -f |
| `config/providers/{aws,gcp,other}_provider.sh` (实现层) | **无** | 永远只被抽象层 source 一次（在抽象层 source guard 之后），无需额外 guard |
| 业务文件 | N/A | 业务文件**永远不直接 source providers/**，统一走 `config/cloud_provider.sh`（或经 `config/config_loader.sh` 间接兜底） |

**推荐 source 时机**：

- `config/config_loader.sh:L1-10` 全局加载阶段加入 `source "${PROJECT_ROOT}/config/cloud_provider.sh"`。
- 现状：所有业务文件都已 source `config_loader.sh`，由此一次性兜底所有下游脚本拿到 getter。
- 后续业务文件**只需用 getter，不必关心 source 顺序**。

**export -f 关键**（子进程继承）：

```bash
# config/cloud_provider.sh 末尾（抽象层入口）
REQUIRED_GETTERS=(
    get_metadata_endpoint get_metadata_header get_metadata_api_path
    get_baseline_io_kib get_baseline_throughput_kib
    get_default_disk_type get_disk_type_options
    get_nic_driver get_nic_allowance_fields get_nic_monitor_process_name
    get_disk_field_prefix get_archive_dir_prefix get_bottleneck_label
    get_platform_display_name get_doc_url
)
for getter in "${REQUIRED_GETTERS[@]}"; do
    export -f "$getter"
done
export CLOUD_PROVIDER PLATFORM_DISPLAY_NAME CLOUD_PROVIDER_DETECTED=1
```

**为什么 export -f 必要**：vegeta / iostat / sar 等监控工具会 fork 子进程，子进程默认拿不到父 shell 的函数定义；`export -f` 把函数写入环境变量 `BASH_FUNC_*`，子进程 source 时自动可见。

---

### §0.5 §13.X 阻塞点结构性消除映射表

下表照抄自 `E1-assessment.md §3`，列出 E1 抽象层结构性消除的 5 个阻塞点（3×P0 + 2×P1）。"结构性消除"指**不靠手工修补**，而是抽象层接口本身让该类问题不再可能出现。

| TRACKER 阻塞点 | 当前级别 | E1 解决方式 | 消除度 |
|---|---|---|---|
| **§13.2 source 顺序冲突** (system_config.sh 先 source 时 CLOUD_PROVIDER 还是 auto) | **P0** | **完全消除**：getter 函数是**懒求值**，调用时才读取 CLOUD_PROVIDER，source 顺序无关。所有 system_config.sh 里的 `case "${CLOUD_PROVIDER:-...}"` 改为定义时不展开的 getter 调用 → 调用方第一次调 getter 时才求值，必然正确。 | **100%** ⭐ 结构性 |
| **§13.5 metadata header 缺失** (GCP 调 IMDS 必须带 `Metadata-Flavor: Google` header) | **P0** | **完全消除**：`get_metadata_header()` getter 统一返回，所有 metadata curl 调用统一写 `curl -H "$(get_metadata_header)" "$(get_metadata_endpoint)/..."` | **100%** ⭐ |
| **§13.6 unified_monitor.sh 字段名硬编码 `_aws_standard_*`** | **P0** | **完全消除**：`get_disk_field_prefix()` getter，writer 端 `${prefix}_$(get_disk_field_prefix)_iops` 即可双平台正确。AWS 返回 `aws_standard`、GCP 返回 `baseline`。 | **100%** ⭐ |
| **§13.12 iostat_collector.sh L144 `_aws_standard_*` 字段名（writer 上游源头）** | **P0** | **完全消除**：同 §13.6，是同一字段在 writer 端的另一个调用点 | **100%** ⭐ |
| **§13.21 comprehensive_analysis.py `'EBS'` 字面 4 处** | P1 | **完全消除**：`get_bottleneck_label()` 替换所有 4 处字面 `'EBS'`，AWS 返回 `EBS`、GCP 返回 `Disk` | **100%** ⭐ |

**结构性消除汇总**：5 个阻塞点（**3×P0 + 2×P1**）被 E1 抽象层彻底解决。

> **E1+ 强化条款**：本表所有 case 删除后，**禁止重新引入 `${CLOUD_PROVIDER:-aws}` 默认值**——未 detect 时必须 fail-fast (`${CLOUD_PROVIDER:?...}`)；违反者 CI 应拒绝（详见 §0.7 决策 6）。

**总览数据变化**：
- P0 总数：**9 → 5**（-44%）
- P1 总数：22 → 20（-2，含 §13.21 与 §13.13 console 文案）
- 间接缓解（消除度 30%~80%）：§13.3 / §13.4 / §13.7 / §13.9 / §13.10 / §13.11 / §13.13 / §13.14 / §13.18 / §13.19（详见 E1-assessment.md §3 完整表）

---

### §0.6 Phase E 执行路线图

| Phase | 内容 | 并行度 | 时长 | 输出 |
|---|---|---|---|---|
| **E-0** | 在 CORRECTED_PLAN.md 顶部插入 §0 E1 架构说明章节 | 1 人 | 1 hour | PLAN 顶部 §0 新增 ~250 行 |
| **E-0+** | §0 升级为 E1+（config 一等公民 + AWS/GCP/Other 平台对等 + 禁用隐式默认 + 新增决策 2.5/6）| 1 人 | 30 min | §0 修订 ~80 行 |
| **E-1** | **新增 `config/cloud_provider.sh` 抽象层入口**（不修改 utils/，原 CP-0.1 创建 `utils/cloud_provider.sh` 的设计废弃；保留 `utils/cloud_provider.py` 作为 Python facade）+ 新增 `config/providers/{aws,gcp,other}_provider.sh` + contract test（含 AWS≠GCP 防抄断言）| 1 人（核心抽象，不并行避免冲突）| 1.5 hour | CP-0 章节扩展（~500 → ~900 行）|
| **E-1.5** | `config/system_config.sh` / `config/user_config.sh` / `config/config_loader.sh` 平台对等性审查（grep `:-aws` 反模式，全部替换为 `:?` fail-fast 或 getter 调用）| 1 人 | 30 min | config/ 内零 `${CLOUD_PROVIDER:-aws}`，CI gate 上线 |
| **E-2** | 改造 CP-1 + CP-2 全部 case → getter（A: CP-1 disk_converter / B: CP-2.1/2.2/2.3 system_config + user_config + config_loader） | 2 人并行 | 各 ~5 min | CP-1 小修 + CP-2 中改（case 块缩短，验证场景重写） |
| **E-3** | 改造 CP-3 + CP-4 + CP-5（C: CP-3 unified_monitor + nic + coordinator + §13.6/§13.12 字段消除 / D: CP-4 disk_analyzer + quality_checker + archiver / E: CP-5 comprehensive_analysis.py + Python cloud_provider.py） | 3 人并行 | 各 ~5 min | CP-3/4/5 小修 |
| **E-4** | TRACKER §13 阻塞点状态同步（§13.2 / §13.5 / §13.6 / §13.12 / §13.21 状态 ❌ → ✅ "E1 absorbed" + 新增 §14 抽象层架构契约说明） | 1 人 | ~10 min | TRACKER 更新 |

**依赖链**：

```
E-0  (架构章节 V1) ✅
  └─→ E-0+ (E1+ 升级 — 本任务) ✅
        └─→ E-1 (CP-0 重构 — config/cloud_provider.sh 入口)
              └─→ E-1.5 (config/ 平台对等性审查)
                    └─→ E-2 (CP-1/2 并行 2 人)
                          └─→ E-3 (CP-3/4/5 并行 3 人)
                                └─→ E-4 (TRACKER 状态同步)
```

**总工时估算**：1h + 30min + 1.5h + 30min + 5min×2 (并行) + 5min×3 (并行) + 10min = **关键路径 ~4 小时 / 总工作量 ~5 小时**（含 E-0+ / E-1.5 新增子任务）。

---

### §0.7 关键设计决策（E1+ 共 7 项）

#### 决策 1：bash 函数返回值方式 → 推荐 **echo + $() 命令替换**

**推荐理由**：
- 调用频次低（每个进程启动时调一次 getter，不在热路径），1ms fork 开销 vs 1s IMDS curl 完全可忽略。
- 可读性最高：`endpoint=$(get_metadata_endpoint)` 符合 Python/Go 习惯，与下游 `curl -H "$(get_metadata_header)" "$(get_metadata_endpoint)/..."` 链式组合自然。
- vs `declare -n` nameref：bash 4.3+ 限定、语法生硬、易出 readonly var 错。
- vs 全局变量 export：污染全局、易冲突、不符合 getter 语义。

**关键代码片段**：
```bash
# AWS provider 实现
get_metadata_endpoint() { echo "http://169.254.169.254"; }
# 业务调用
curl -H "$(get_metadata_header)" "$(get_metadata_endpoint)/$(get_metadata_api_path)/meta-data/instance-id"
```

**数组特殊场景**（如 `get_nic_allowance_fields` 返回 6 字段）：CSV 字符串返回 + caller `IFS=',' read -ra fields <<< "$(get_nic_allowance_fields)"`。

#### 决策 2：providers/ 目录位置 → 推荐 **config/providers/**

**推荐理由**：
- provider 返回值 95% 是 config 数据（endpoint / disk type / 字段集），与 `config/` 语义对齐。
- `config/cloud_provider.sh` 作为**抽象层入口**（detect + factory），内部 source `config/providers/${CLOUD_PROVIDER}_provider.sh`（⭐ E1+ 入口与实现同目录）。
- 抽象层（入口）与实现层（providers/）同 `config/` 目录下，符合 VFS 设计的 locality 原则（vfs.c 在 fs/，ext4_super.c 在 fs/ext4/，但本项目层级浅，全部放 config/ 即可）。
- vs `utils/providers/`：与已迁出的 `config/cloud_provider.sh` 不同层，破坏 locality。
- vs `lib/providers/`：引入新顶层目录，与项目现有 5 层结构（config/utils/monitoring/tools/analysis/visualization）不一致。

**关键代码片段**：
```bash
# config/cloud_provider.sh （抽象层入口，⭐ E1+ 在 config/）
source "${PROJECT_ROOT}/config/providers/${CLOUD_PROVIDER}_provider.sh"
```

#### 决策 2.5：抽象层入口位置 → **`config/cloud_provider.sh`**（E1+ 升级，覆盖旧 E1）

**问题背景**：旧 E1 把抽象层入口放在 `utils/cloud_provider.sh`，但用户工作流是「先 grep config/ 找 GCP 兼容性入口」，且业务诉求是 AWS/GCP 平权对比性能（不是 AWS+other 的旧二分法）。

**选项对比**：

| 选项 | 入口位置 | 用户发现性 | 语义匹配 | 决策 |
|---|---|---|---|---|
| A | `utils/cloud_provider.sh`（旧 E1）| 差（用户 grep config/ 看不到）| 弱（utils 应该是无状态工具）| ❌ |
| B | `config/cloud_provider.sh`（E1+ ⭐）| 强（grep config/ 一次命中）| 强（平台选择是配置决策）| ✅ |

**决策**：**B** — 抽象层入口搬到 `config/cloud_provider.sh`。

**理由**：
1. **用户工作流对齐**：用户从 GCP 团队入职后，首选 `grep -r GCP config/` 找入口，把抽象层放 config/ 让 GCP 兼容性「一眼可见」。
2. **语义对齐**：平台选择是**用户可见的配置决策**（涉及 IO baseline、字段命名、NIC driver 等业务行为差异），不是无状态工具函数。
3. **locality 原则**：providers/ 实现已经在 `config/providers/` 下，入口跨目录违反「入口与实现同居」原则。
4. **Python facade 例外保留**：`utils/cloud_provider.py` 不动——它是 analysis/visualization/ 的只读消费方，不参与 detect/factory，符合 utils 的工具语义。

**影响范围**：
- 原 CP-0.1（创建 `utils/cloud_provider.sh`）方案**废弃**，改为创建 `config/cloud_provider.sh`。
- 所有 §0 / CP-0 ~ CP-6 文档中 `utils/cloud_provider.sh` 引用全部替换为 `config/cloud_provider.sh`。
- 业务代码 source 路径相应改为 `source "${PROJECT_ROOT}/config/cloud_provider.sh"`（或通过 `config_loader.sh:L1-10` 间接兜底）。

#### 决策 3：provider 接口 contract test → 推荐 **必须有**

**推荐理由**：新增 provider（Azure / OCI）时，一跑此 test 立即知道哪些 getter 漏实现；contract test 是抽象层最便宜的保险（~60 行）。

**关键代码片段**（`tests/test_provider_contract.sh`）：
```bash
#!/usr/bin/env bash
REQUIRED_GETTERS=(
    get_metadata_endpoint get_metadata_header get_metadata_api_path
    get_baseline_io_kib get_baseline_throughput_kib
    get_default_disk_type get_disk_type_options
    get_nic_driver get_nic_allowance_fields get_nic_monitor_process_name
    get_disk_field_prefix get_archive_dir_prefix get_bottleneck_label
    get_platform_display_name get_doc_url
)
for provider in aws gcp other; do
    CLOUD_PROVIDER=$provider bash -c "
        source config/cloud_provider.sh
        for getter in ${REQUIRED_GETTERS[*]}; do
            declare -F \$getter >/dev/null || { echo \"FAIL: \$getter missing in $provider\"; exit 1; }
            val=\$(\$getter 2>/dev/null) || { echo \"FAIL: \$getter errored in $provider\"; exit 1; }
        done
        echo \"$provider: OK (15/15 getters)\"
    "
done
```

#### 决策 4：source 顺序 + source guard → **抽象层自身有 guard，实现层无 guard**

**推荐理由**：
- 抽象层 guard 保证业务文件可多次 source（幂等），但实际只 detect 一次、只 export -f 一次。
- 实现层无 guard 因为永远只被抽象层 source 一次（在抽象层 guard 之后），加 guard 反而干扰未来重新加载场景（如 contract test 切换 CLOUD_PROVIDER）。
- 业务代码**永远不直接 source providers/**，统一走 `config/cloud_provider.sh`，由 `config/config_loader.sh:L1-10` 全局兜底。

**关键代码片段**：
```bash
# config/cloud_provider.sh 顶部（抽象层入口）
[[ -n "${CLOUD_PROVIDER_DETECTED:-}" ]] && return 0
# ... detect + source provider ...
export CLOUD_PROVIDER_DETECTED=1

# config/providers/aws_provider.sh 顶部
# （无 source guard — 永远只被抽象层 source 一次）
get_metadata_endpoint() { echo "http://169.254.169.254"; }
```

#### 决策 5：§13.2 source 顺序冲突的最终解决方案 → **懒求值 getter 真正解决**

**问题回顾**：`config_loader.sh:L72-78` 先 source `system_config.sh`，此时 `CLOUD_PROVIDER` 仍为 "auto"，导致 system_config.sh 内所有 `case "${CLOUD_PROVIDER:-...}"` 首次加载落 aws 默认分支；detect_deployment_platform 后置无人重新触发 case → 4 个变量（METADATA_ENDPOINT / METADATA_API_PATH / CLOUD_IO_BASELINE_KIB / MONITORING_PROCESS_NAMES）全部首次加载失效。

**V1.0 workaround**：加 "re-evaluate hook" 或 "lazy getter 函数" — 设计妥协，未真正落地。

**E1 结构性解决方案**：懒求值 getter **天然解决** — 函数体在被调用时才求值，CLOUD_PROVIDER 此时已固定。

**关键代码片段**：
```bash
# 改造前（急切求值，受 source 顺序影响）：
case "${CLOUD_PROVIDER:-aws}" in
    gcp) METADATA_ENDPOINT="http://metadata.google.internal" ;;
    *)   METADATA_ENDPOINT="http://169.254.169.254" ;;
esac
# 问题：source system_config.sh 时 CLOUD_PROVIDER=auto，落 aws 分支

# 改造后（懒求值 getter，不受 source 顺序影响）：
# system_config.sh 里删掉整个 case 块，不再定义 METADATA_ENDPOINT 变量
# 业务调用方（任何时刻）：
curl -H "$(get_metadata_header)" "$(get_metadata_endpoint)/$(get_metadata_api_path)/meta-data/instance-id"
# get_metadata_endpoint 在被调用时才求值，此时 CLOUD_PROVIDER 已 detect 完毕 → 正确
```

**§13.2 状态从 ❌ → ✅（E1 absorbed），同时总览 P0 数 9 → 5**。

#### 决策 6：AWS / GCP / Other 平等性强制（E1+ 新增）

**问题背景**：旧 E1 容忍 `${CLOUD_PROVIDER:-aws}` 隐式默认值，让 GCP 团队 onboarding 时误以为项目「以 AWS 为正、其他平台为补丁」，违背业务诉求的「跨云性能公平对比」。

**强制条款**：

1. **禁止 `${CLOUD_PROVIDER:-aws}`**（也禁止 `${CLOUD_PROVIDER:-other}` 等任何隐式默认）。
2. **必须 `${CLOUD_PROVIDER:?CLOUD_PROVIDER not set, run config/cloud_provider.sh first}` 强制 detect**——未设置时直接 fail-fast，把 onboarding 错误前置。
3. **contract test 不仅验「getter 存在 + 返回非空」，还断言「AWS / GCP 返回值不同」**（防 GCP getter 抄 AWS 实现）：
   ```bash
   # tests/test_provider_contract.sh 追加片段
   for getter in get_metadata_endpoint get_metadata_header get_baseline_io_kib \
                 get_nic_driver get_nic_monitor_process_name get_disk_field_prefix \
                 get_archive_dir_prefix get_platform_display_name; do
       aws_val=$(CLOUD_PROVIDER=aws bash -c "source config/cloud_provider.sh && $getter")
       gcp_val=$(CLOUD_PROVIDER=gcp bash -c "source config/cloud_provider.sh && $getter")
       [[ "$aws_val" != "$gcp_val" ]] || {
           echo "FAIL: $getter returns identical value on AWS and GCP — GCP impl likely copied from AWS"
           exit 1
       }
   done
   ```
4. **CI gate**：grep `\\$\\{CLOUD_PROVIDER:-` 在 `config/` / `monitoring/` / `tools/` / `analysis/` / `visualization/` 下应**零命中**（仅允许在 `tests/` 反例引用 + `analysis-notes/` 文档描述出现）。

**强制理由**：
- 性能对比公平性：GCP 数据塞 `_aws_standard_iops` 字段会让对比图表失真，必须靠 contract test 防住。
- 维护清晰度：fail-fast 比「静默落 aws 分支」更容易在 CI 发现 bug。
- 文化建设：`${...:?}` 语法在代码里就是「AWS/GCP/Other 必须显式声明」的视觉提醒。

**违反案例**（必须 CI 拒绝）：
```bash
# ❌ 反模式 1
case "${CLOUD_PROVIDER:-aws}" in ...   # 隐式 AWS 默认

# ❌ 反模式 2
endpoint="${METADATA_ENDPOINT:-http://169.254.169.254}"   # 隐式 AWS endpoint

# ✅ 正确写法
endpoint="$(get_metadata_endpoint)"
[[ -z "$endpoint" ]] && { log_warn "no IMDS on $(get_platform_display_name)"; return 0; }
```

---

### §0.8 ROI 评估

| 维度 | 直接进 R 期 (V1.0 路线) | E1 路线 |
|---|---|---|
| Phase 8a 后续工作 (本评估外) | 0 (R 期直接动业务代码) | E-0 ~ E-4 共 ~3h 关键路径 / ~4h 总工作量 |
| R 期改造代价 | 21 处 case 散落 + 5 个 P0 阻塞点遗留 | 19 处 getter 调用（代码量 -65 LOC）+ 5 P0 已消除 |
| 接入第 3 个云平台 (例如 Azure) 代价 | 全 PLAN 21 处 case 加 Azure 分支 + 5 个 P0 阻塞重新评估 | 1 个 `azure_provider.sh` 文件（~80 行）+ contract test 自动验证 |
| 业务代码可读性 | case 块散落，12 个 `${CLOUD_PROVIDER:-...:-aws}` 嵌套默认值 | 业务代码 100% 平台中立（`get_*()` 调用） |
| §13.2 source 顺序冲突 | 设计妥协 (re-evaluate hook) | 结构性消除 |
| §13.6 / §13.12 字段名 hardcode (P0) | 字面 `_aws_standard_*` 散落 writer/reader | 集中走 `get_disk_field_prefix()` |
| Round 演进（改字段集/baseline） | 改全 PLAN 多处 | 改 1 个 provider 文件 |
| 风险 | 高（5 个 P0 遗留 + 散落 case 漏改） | 低（抽象层 contract test 兜底） |

**ROI 结论**：

- **E1 净投入** ~4 小时（含 1h §0 架构章节 + 1.5h CP-0 重构 + ~1.5h 5 个 subagent 并行改 CP）。
- **E1 净产出**：
  - **5 个阻塞点结构性消除**（§13.2 / §13.5 / §13.6 / §13.12 + §13.21）
  - **总览 P0 数 9 → 5**（-44%）
  - **业务代码 LOC -65**（CP-1 ~ CP-5 case 块缩短：CP-1 -30 / CP-2 -80 / CP-3 -40 / CP-4 -20 / CP-5 -15 / CP-0 +250；净 +65 集中在抽象层基础设施）
  - **Round 演进效率倍增**：加新云平台从"全 PLAN 重审"降到"加 1 个 provider 文件"
  - **维护成本下降**：case 散落 → 接口集中，每个未来 case 改造都收益
- **关键路径警告**：R 期之前必须落地 E1，否则 R 期改业务代码时 case 句式会先固化进 commit，之后再抽 provider 成本翻倍（业务代码动 2 次，contract test 验证范围变大）。

**建议**：立即批准 Phase E-0 ~ E-4，阻断 R 期启动直到 E1 落地完成。预期 R 期工作量因 E1 而减少 ~20%（case 散落改造 → getter 调用），净时间投入 **ROI > 1.5x**。

#### §0.8.1 用户架构诉求对齐（E1+ 新增）

本 E1+ 是项目作者从「AWS-first + other 兜底」到「AWS / GCP / Other 三平台对等」的架构演进，回应用户明确诉求：

- **业务价值**：跨云性能对比的**方法论基础**——避免字段命名 bias（`_aws_standard_*` → `get_disk_field_prefix()`）、避免默认值 bias（`${CLOUD_PROVIDER:-aws}` → `${CLOUD_PROVIDER:?...}` fail-fast），让 AWS / GCP 的 benchmark 结果在同一框架下可信对比。
- **维护价值**：未来加 Azure / OCI 时，目录结构（`config/providers/azure_provider.sh`）+ 接口契约（15 getter + contract test）已就绪，**零业务代码改动**。
- **用户工作流价值**：抽象层入口在 `config/cloud_provider.sh`，用户 `grep -r GCP config/` 一次发现平台兼容性入口，符合 GCP 团队 onboarding 习惯。
- **文化建设价值**：禁用隐式 AWS 默认值 + contract test 强制 AWS≠GCP 返回值差异，从代码层杜绝「项目偏 AWS」的暗示，确立**平台中立的工程文化**。

**E1+ vs 旧 E1 增量收益**：

| 维度 | 旧 E1 | E1+ 增量 |
|---|---|---|
| 抽象层入口位置 | `utils/cloud_provider.sh` | `config/cloud_provider.sh`（用户发现性 ↑）|
| 平台默认值 | 容忍 `${CLOUD_PROVIDER:-aws}` | 禁用，强制 `${CLOUD_PROVIDER:?...}` fail-fast |
| Other 列语义 | 「AWS 降级版」（继承 AWS 默认值）| 「未知平台中立 fallback」（中立空值/空集）|
| contract test 强度 | 仅验「getter 存在 + 返回非空」 | 追加「AWS ≠ GCP」防抄断言 + CI gate |
| 字段命名公平性 | 已通过 `get_disk_field_prefix()` 抽象 | 不变（E1 已经做好）|

**E1+ 净增量投入**：~30 min（§0 文档修订）+ ~30 min（E-1.5 config/ 平台对等性审查）= **1 小时**；产出是「跨云对比方法论基础」+ 「GCP 团队 onboarding 友好度」，ROI 显著高于 1。

---

### §0.X 架构演进触发器总览 (跨章节决策依据)

**目的**: 把"现在保守, 未来什么条件下要升级"的判断显式量化, 避免任性升级 (over-engineering) 和任性保守 (technical debt)。

| 模块 | 当前架构 | 升级到接口抽象的触发条件 (满足任一) | 升级后预估成本 | 引用章节 |
|---|---|---|---|---|
| **NIC 监控** | Y+ 接口抽象层 (aws.sh/gcp.sh/other.sh) | (已升级) | (已落地, CP-2.5) | CP-2.5.7 |
| **Disk 监控** | getter 拼接 (CLOUD_PROVIDER 参数化) | 1) 新平台 disk 引入 semantic 分裂字段 (例 GCP Hyperdisk Extreme 新增"provisioned throughput"而 AWS io2 无对应物); 2) 平台数 ≥5 时 case 列表过长; 3) 同平台多 disk 类型字段集差异显著 (例 Azure premium_v2 vs ultra vs standard ssd) | ~600 LOC / 4-6h, 含 disk/interface.sh + 3 provider + DiskFieldRegistry | CP-2.5.7 |
| **CPU 监控** | 三平台同 (/proc/stat) | 1) 平台引入硬件性能 counter (如 Apple Silicon P-core/E-core 分类); 2) ARM/x86 字段集分裂 | ~400 LOC / 3-4h | (未触发, 暂保留) |
| **Mem 监控** | 三平台同 (/proc/meminfo) | 1) 平台引入 NUMA-aware 监控; 2) 引入 memory bandwidth counter (Intel RDT 类) | ~400 LOC / 3-4h | (未触发, 暂保留) |
| **Chain 监控 (Solana/ETH 等)** | 已按 chain 多态 (chains/<chain>/) | (已多态) | (已落地) | CP-0 章节 |

**判断原则** (Sandi Metz / John Ousterhout):
- 出现 Rule of Three (同类重复 ≥3 次) → 考虑升级
- 出现"差异是 semantic 而非命名" → 必须升级 (不能用参数化糊弄)
- 出现"差异是命名而非 semantic" → 用参数化 (升级是 over-engineering)

**反例警告** (避免"任性升级"):
- ❌ 因为"看着 disk 字段也不少, 顺手也升级到接口" → 违反 YAGNI
- ❌ 因为"未来可能加 Azure" → 等真加 Azure 时再升级 (Rule of Three: AWS+GCP+Azure 才触发)
- ❌ 因为"接口抽象更优雅" → 在没有 semantic 分裂的场景下, 抽象就是负债 (Ousterhout: "Modules should be deep")

**反例警告** (避免"任性保守"):
- ❌ "再加一个 provider 也就 case 多一行" → 当 case 数 ≥5 时, 接口抽象的总维护成本反而低
- ❌ "我们就 AWS+GCP 两家不会再加了" → 历史上每个项目都这么想, 最后都加了第三家

---

## CP-0：前置基础设施（无业务代码改动）

> **本阶段产物**：7 个新文件
> - `config/cloud_provider.sh`（抽象层入口）
> - `config/providers/aws_provider.sh` / `gcp_provider.sh` / `other_provider.sh`（3 个 provider 实现）
> - `utils/field_normalizer.py`（CSV/JSON 归一化层）
> - `tests/test_provider_contract.sh`（provider 契约测试，含 AWS≠GCP 防抄断言）
> - `tests/fake_target_stack/`（mock 模拟器规约，Phase 8b 落地）
>
> **业务代码 diff**：0 行（CP-0 只新增、不改既有；utils/cloud_provider.py Python facade 保留 utils/ 路径不动）。
> **验证目标**：5 个新文件单独可跑、`bash tests/test_provider_contract.sh` 全绿、`pytest tests/utils/test_field_normalizer.py` 全绿，方可进入 CP-1。

---

### CP-0.1 创建 config/cloud_provider.sh（抽象层入口，新增）

> **E1+ 升级说明**：本节**整章作废重写**。旧 CP-0.1（创建 `utils/cloud_provider.sh`）方案废弃，依据 §0.7 决策 2.5（抽象层入口位置）+ 决策 6（AWS/GCP/Other 平等性强制）。新文件路径强制为 `config/cloud_provider.sh`，**不放 utils/**。

#### CP-0.1.1 目标 & 设计原则

**目标**：成为 CLOUD_PROVIDER + 15 getter 函数的**唯一权威定义点 / 抽象层入口**。下游所有脚本（CP-2.3 config_loader.sh / CP-3.2 nic_network_monitor.sh / CP-1.1 disk_converter.sh 等）通过 `config/config_loader.sh:L1-10` 间接拿到 getter，**禁止自行 curl metadata、禁止直接 source providers/**。

**3 条不可妥协的设计原则**（来自 §0.1）：

1. **配置一等公民**：路径强制 `config/cloud_provider.sh`（不是 `utils/`）。平台选择是用户可见的配置决策，不是隐式工具。
2. **三平台对等性**：`detect_cloud_provider()` 返回 `aws | gcp | other` 三值之一，**无默认值**。providers/ 下 `aws_provider.sh` / `gcp_provider.sh` / `other_provider.sh` 三文件完全对等，无主从关系。
3. **责任划分**：
   - 本文件（抽象层入口）只做 **detect + factory + 接口规范注释 + export-f 批量化 + contract sanity check**。
   - 具体 getter 实现放 `config/providers/${CLOUD_PROVIDER}_provider.sh`（详见 CP-0.4）。
   - 永远禁用 `${CLOUD_PROVIDER:-aws}` 等隐式默认值（§0.7 决策 6 第 1 条 CI gate 拒绝）。

#### CP-0.1.2 完整 bash 代码（~80 行，可直接执行无省略）

**文件路径**：`config/cloud_provider.sh`

```bash
#!/usr/bin/env bash
# config/cloud_provider.sh — E1+ Cloud Provider Abstract Layer (Entry Point)
#
# 责任：detect 当前云平台（aws/gcp/other）+ source 对应 providers/${name}_provider.sh
#       + 批量 export -f 15 个 getter 函数（保证子进程 vegeta/iostat fork 可见）
#       + contract sanity check（缺 getter 立即 fail-fast）
#
# 设计准则（§0.7 决策 6）：
#   1. AWS / GCP / Other 三平台完全对等，无主从
#   2. 禁用 ${CLOUD_PROVIDER:-aws} 等隐式默认值；未 detect 时 fail-fast
#   3. detect 一次后通过 export 持久化，下游业务代码只调 getter 不重复 detect
#
# Usage:
#   source config/cloud_provider.sh        # 推荐由 config/config_loader.sh:L1-10 全局兜底
#   echo "$CLOUD_PROVIDER"                  # → aws | gcp | other
#   curl -H "$(get_metadata_header)" "$(get_metadata_endpoint)/$(get_metadata_api_path)/..."

# ---- source guard（幂等，§0.4 contract）----
[[ -n "${CLOUD_PROVIDER_DETECTED:-}" ]] && return 0 2>/dev/null || true

# ---- detect 函数 ----
detect_cloud_provider() {
    # 优先级 1: 用户显式 export CLOUD_PROVIDER=aws|gcp|other 最高优先级
    if [[ -n "${CLOUD_PROVIDER:-}" && "${CLOUD_PROVIDER}" != "auto" ]]; then
        case "$CLOUD_PROVIDER" in
            aws|gcp|other) echo "$CLOUD_PROVIDER"; return 0 ;;
            *) echo "FATAL: invalid CLOUD_PROVIDER='$CLOUD_PROVIDER' (expected aws|gcp|other)" >&2
               return 1 ;;
        esac
    fi

    # 优先级 2: AWS IMDSv2 probe（先 PUT token，再 GET instance-id）
    local aws_token
    aws_token="$(curl -fsS -m 1 --connect-timeout 1 \
                     -X PUT 'http://169.254.169.254/latest/api/token' \
                     -H 'X-aws-ec2-metadata-token-ttl-seconds: 60' 2>/dev/null)" || true
    if [[ -n "$aws_token" ]] && \
       curl -fsS -m 1 --connect-timeout 1 \
            -H "X-aws-ec2-metadata-token: $aws_token" \
            'http://169.254.169.254/latest/meta-data/instance-id' >/dev/null 2>&1; then
        echo "aws"; return 0
    fi

    # 优先级 3: GCP metadata probe
    if curl -fsS -m 1 --connect-timeout 1 \
            -H 'Metadata-Flavor: Google' \
            'http://metadata.google.internal/computeMetadata/v1/instance/id' >/dev/null 2>&1; then
        echo "gcp"; return 0
    fi

    # 优先级 4: fallback "other"（中立 fallback，不偏 AWS — §0.7 决策 6 第 1 条）
    echo "other"
}

# ---- 主流程：detect → source provider → 批量 export -f ----
CLOUD_PROVIDER="$(detect_cloud_provider)" || {
    echo "FATAL: cloud provider detection failed" >&2
    return 1 2>/dev/null || exit 1
}
export CLOUD_PROVIDER

PROVIDER_FILE="${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}/config/providers/${CLOUD_PROVIDER}_provider.sh"
[[ -f "$PROVIDER_FILE" ]] || {
    echo "FATAL: provider file not found: $PROVIDER_FILE" >&2
    return 1 2>/dev/null || exit 1
}
# shellcheck source=/dev/null
source "$PROVIDER_FILE"

# ---- contract sanity check：15 getter 必须全部由 provider 实现 ----
REQUIRED_GETTERS=(
    get_metadata_endpoint get_metadata_header get_metadata_api_path
    get_baseline_io_kib get_baseline_throughput_kib
    get_default_disk_type get_disk_type_options
    get_nic_driver get_nic_allowance_fields get_nic_monitor_process_name
    get_disk_field_prefix get_archive_dir_prefix get_bottleneck_label
    get_platform_display_name get_doc_url
)
for getter in "${REQUIRED_GETTERS[@]}"; do
    declare -F "$getter" >/dev/null || {
        echo "FATAL: provider '$CLOUD_PROVIDER' missing required getter: $getter" >&2
        return 1 2>/dev/null || exit 1
    }
    export -f "$getter"
done

# ---- 派生 PLATFORM_DISPLAY_NAME 并 export guard 标记 ----
PLATFORM_DISPLAY_NAME="$(get_platform_display_name)"
export PLATFORM_DISPLAY_NAME
export CLOUD_PROVIDER_DETECTED=1
```

**代码合规自查**（§0.7 决策 6）：
- ✅ 第 27 行 `${CLOUD_PROVIDER:-}` 是判空（不是默认值赋值），符合 contract。
- ✅ 第 28 行只接受 aws/gcp/other 三值，其他立即 fail-fast。
- ✅ 第 56 行 fallback `other` 是中立值（不是 `aws`），不偏向任何平台。
- ✅ 第 79-83 行 contract check 缺 getter 立即报错退出，防止下游静默使用 undefined 函数。
- ✅ 末尾 `export -f` 批量化保证 vegeta / iostat 子进程可见（§0.4 关键）。

#### CP-0.1.3 加载契约（source 时机）

| 调用方 | source 方式 | 时机 |
|---|---|---|
| `config/config_loader.sh:L1-10` | `source "${PROJECT_ROOT}/config/cloud_provider.sh"` | **全局加载阶段**，统一兜底 |
| 业务文件（monitoring/ tools/ analysis/）| **不直接 source** | 通过 config_loader.sh 间接拿到 CLOUD_PROVIDER + 15 getter |
| `config/providers/*_provider.sh` | **不直接 source** | 永远只由 `config/cloud_provider.sh` 内部 source 一次 |
| `tests/test_provider_contract.sh` | `CLOUD_PROVIDER=aws bash -c "source config/cloud_provider.sh; ..."` | 测试切换 provider 时单独 source |

**关键约束**：detect 一次后 CLOUD_PROVIDER + 15 getter 通过 export / export -f 持久化，子进程（vegeta / iostat / awk / sar）fork 时自动继承。

#### CP-0.1.4 与旧 CP-0.1（utils/cloud_provider.sh）的差异

| 维度 | 旧设计（utils/cloud_provider.sh，已废弃）| 新设计（config/cloud_provider.sh，E1+）|
|---|---|---|
| 文件路径 | `utils/cloud_provider.sh` | **`config/cloud_provider.sh`**（§0.7 决策 2.5）|
| 入口职责 | detect + 设 PLATFORM_DISPLAY_NAME 完事 | detect + factory + source providers/ + 批量 export-f + contract check |
| 默认值哲学 | 容忍 `${CLOUD_PROVIDER:-aws}` 隐式默认 | **禁用**所有隐式默认；未 set 时 fail-fast |
| detect 顺序 | GCP 在前、AWS 在后（旧的 cheaper DNS 论调）| AWS 在前、GCP 在后（业务诉求是 AWS/GCP 对等，无优先级偏好；按字母序）|
| Provider 实现加载方式 | 单文件内 case 分发（21 处散落全 PLAN）| 拆分 3 文件 `providers/{aws,gcp,other}_provider.sh`，本文件只 source 一次 |

**Python facade 保留**：`utils/cloud_provider.py`（analysis/ + visualization/ + utils/field_normalizer.py 的只读消费方）保留 `utils/` 路径不动——它不参与 detect/factory，符合 utils 的工具语义（决策 2.5 第 4 条例外）。

#### CP-0.1.5 验证场景（4 个手动用例）

```bash
# === 场景 1: AWS EC2 上 source（真实 IMDSv2）===
cd /usr/local/google/home/lelandgong/blockchain-node-benchmark
unset CLOUD_PROVIDER CLOUD_PROVIDER_DETECTED
source config/cloud_provider.sh
echo "$CLOUD_PROVIDER / $PLATFORM_DISPLAY_NAME"
# 期望 stdout: aws / AWS
# 验证 15 getter 全 export:
for g in get_metadata_endpoint get_metadata_header get_metadata_api_path \
         get_baseline_io_kib get_baseline_throughput_kib \
         get_default_disk_type get_disk_type_options \
         get_nic_driver get_nic_allowance_fields get_nic_monitor_process_name \
         get_disk_field_prefix get_archive_dir_prefix get_bottleneck_label \
         get_platform_display_name get_doc_url; do
    declare -F "$g" >/dev/null && echo "OK $g=$($g 2>/dev/null | head -c 60)"
done
# 期望: 15 行 OK，无任何 "function not found"
# 例：OK get_metadata_endpoint=http://169.254.169.254
#     OK get_baseline_io_kib=16

# === 场景 2: GCP GCE 上 source（真实 metadata.google.internal）===
unset CLOUD_PROVIDER CLOUD_PROVIDER_DETECTED
source config/cloud_provider.sh
echo "$CLOUD_PROVIDER / $PLATFORM_DISPLAY_NAME"
# 期望 stdout: gcp / GCP
# 验证 15 getter：
echo "$(get_metadata_endpoint) / $(get_metadata_header) / $(get_baseline_io_kib)"
# 期望: http://metadata.google.internal / Metadata-Flavor: Google / 4

# === 场景 3: 本地 Mac / 无 metadata 服务 source（中立 fallback）===
unset CLOUD_PROVIDER CLOUD_PROVIDER_DETECTED
source config/cloud_provider.sh
echo "$CLOUD_PROVIDER / $PLATFORM_DISPLAY_NAME"
# 期望 stdout: other / OTHER（IMDS 探测均超时后 fallback；耗时约 4-6 秒，4 次 curl × 1s timeout）
# 验证 15 getter 全 export 且返回中立值（不偏 AWS）：
echo "endpoint=[$(get_metadata_endpoint)] disk_type=[$(get_default_disk_type)] field_prefix=[$(get_disk_field_prefix)]"
# 期望: endpoint=[] disk_type=[] field_prefix=[standard]
#   （endpoint/disk_type 为空，field_prefix=standard 中立命名，绝不出现 gp3 / aws_standard）

# === 场景 4: export CLOUD_PROVIDER=foo 后 source（fail-fast 报错退出）===
unset CLOUD_PROVIDER_DETECTED
CLOUD_PROVIDER=foo bash -c 'source config/cloud_provider.sh; echo "should-not-reach"'
echo "exit_code=$?"
# 期望 stderr: FATAL: invalid CLOUD_PROVIDER='foo' (expected aws|gcp|other)
#       stdout: （空，should-not-reach 不应打印）
#       exit_code=1
```

**回归断言**（任一失败则 CP-0.1 验证不通过）：
1. 场景 1/2/3 三个平台都必须有 `CLOUD_PROVIDER_DETECTED=1` 被 export
2. 15 getter 在子进程 `bash -c 'declare -F get_metadata_endpoint'` 中可见（export -f 生效）
3. 场景 4 必须 exit code 非 0，且 stderr 含 "FATAL: invalid CLOUD_PROVIDER"
4. 场景 3 的 `get_disk_field_prefix` **必须返回 "standard"，禁止返回 "aws_standard"**（§0.7 决策 6 反例）

#### CP-0.1.6 与下游联动点

| 下游消费方 | 联动方式 | 改造时机 |
|---|---|---|
| `config/config_loader.sh:L1-10` | 全局 source（兜底所有业务文件） | CP-2.3 |
| `config/config_loader.sh:L102-128 detect_deployment_platform()` | 复用 CLOUD_PROVIDER 不再重复 IMDS curl | CP-2.3 |
| `utils/disk_converter.sh:L7` | 调 `get_baseline_throughput_kib()` 替换 case | CP-1.1 |
| `monitoring/nic_network_monitor.sh` (CP-3.2 新) | 调 `get_nic_driver` / `get_nic_allowance_fields` | CP-3.2 |
| `utils/field_normalizer.py` (CP-0.2) | Python 端经 `utils/cloud_provider.py` facade 读 `os.environ['CLOUD_PROVIDER']` | CP-0.2 |
| `tools/benchmark_archiver.sh` | 调 `get_archive_dir_prefix` 派生归档目录名 | CP-4.3 |
| `monitoring/unified_monitor.sh` CSV header | 调 `get_disk_field_prefix` 替换 `_aws_standard_*` 硬编码 | CP-3.1 |

---

### CP-0.2 创建 utils/field_normalizer.py（新增）

**目的**：CSV/JSON 读时归一化层 + 写时双写辅助层。所有 analysis/visualization 文件**统一**通过它读 DataFrame，旧字段名（含 `aws_/ebs_/ena_` 字面）自动 alias 到新字段名（中立化 `disk_/network_/nic_`）。

**字段清单来源**：TRACKER §10.1（63 行字段表）+ §3 命名清单（13 行 DM-* 条目）。下表只列**真正需要 alias 的字段**（写方/读方任一含 aws_/ebs_/ena_ 字面且 TRACKER 标"✅ 双写" / "✅ alias"），TRACKER 中标"❌ 直接改"（0 外部下游）的字段**不进 ALIASES dict**（直接改源即可，alias 反而是噪音）。

**预估 alias 条目数**：33 个（CSV 列 21 + JSON key 7 + env var 5；详见下文 dict）。

**完整文件内容**：

```python
# utils/field_normalizer.py — 新增
"""
Field name normalization layer for CSV/JSON I/O during AWS → GCP migration.

Read path  : normalize_df(df)         old field names → new (neutralized) names
Write path : denormalize_for_dual_write(record_dict)  emit BOTH old & new keys

Source of truth for FIELD_ALIASES: analysis-notes/02-GCP-MIGRATION-TRACKER.md §10.1
                                   analysis-notes/02-GCP-MIGRATION-TRACKER.md §3 (DM-*)

Lifecycle:
  - Phase CP-1..CP-5 : dual-write enabled (writers emit both keys; readers normalize)
  - Phase CP-6       : remove old keys from writers; keep ALIASES for back-compat
                       reading of archived CSV/JSON for at least 1 release
"""
from __future__ import annotations
import os
import re
from typing import Dict, Mapping, MutableMapping, Iterable, TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

# ============================================================
# Static alias table (exact-match field names)
# ============================================================
FIELD_ALIASES: Dict[str, str] = {
    # ----- CSV column: disk standard performance (iostat_collector writes;
    #       master_qps_executor / bottleneck_detector / ebs_chart_generator /
    #       report_generator / device_manager / framework_data_quality_checker read)
    "data_aws_standard_iops":               "data_disk_standard_iops",
    "data_aws_standard_throughput_mibs":    "data_disk_standard_throughput_mibs",
    "accounts_aws_standard_iops":           "accounts_disk_standard_iops",
    "accounts_aws_standard_throughput_mibs":"accounts_disk_standard_throughput_mibs",

    # ----- CSV column: network bandwidth raw (unit_converter; 0 external readers
    #       but unify naming for future-proofing — TRACKER §10.1 #2-6)
    "aws_standard_gbps":      "network_standard_gbps",
    "aws_display_mbps":       "network_display_mbps",
    "aws_rx_gbps":            "network_rx_gbps",
    "aws_tx_gbps":            "network_tx_gbps",
    "aws_total_gbps":         "network_total_gbps",

    # ----- CSV column: ENA allowance counters (AWS-only; on GCP these columns
    #       are not written, but readers should map them to neutral names so
    #       cross-platform analysis code uses a single key. TRACKER §10.1 #14-17)
    "bw_in_allowance_exceeded":      "network_bw_in_dropped",
    "bw_out_allowance_exceeded":     "network_bw_out_dropped",
    "pps_allowance_exceeded":        "network_pps_dropped",
    "conntrack_allowance_exceeded":  "network_conntrack_dropped",
    "linklocal_allowance_exceeded":  "network_linklocal_dropped",
    "conntrack_allowance_available": "network_conntrack_available",

    # ----- JSON top-level keys: bottleneck_status / latest_metrics
    #       (TRACKER §10.1 #44/#45/#46 + #52)
    "ebs_util":          "disk_util",
    "ebs_latency":       "disk_latency",
    "ebs_aws_iops":      "disk_standard_iops",
    "ebs_aws_throughput":"disk_standard_throughput_mibs",
    "ebs_throughput":    "disk_throughput",
    "ena_data":          "network_allowance_data",   # JSON sub-object name
    "ebs_bottlenecks":   "disk_bottlenecks",         # nested list key

    # ----- bottleneck_counters.json counter keys (TRACKER §10.1 #58/#59)
    "ena_limit":         "nic_limit",
    "accounts_ebs_util": "accounts_disk_util",
    "accounts_ebs_latency": "accounts_disk_latency",

    # ----- env var names that flow into CSV column names indirectly
    #       (TRACKER §10.1 #12/#13/#31, DM-5/6/7)
    "ENA_MONITOR_ENABLED":         "NIC_MONITOR_ENABLED",
    "ENA_ALLOWANCE_FIELDS":        "NIC_ALLOWANCE_FIELDS",
    "ENA_ALLOWANCE_FIELDS_STR":    "NIC_ALLOWANCE_FIELDS_STR",
    "BOTTLENECK_EBS_UTIL_THRESHOLD":       "BOTTLENECK_DISK_UTIL_THRESHOLD",
    "BOTTLENECK_EBS_LATENCY_THRESHOLD":    "BOTTLENECK_DISK_LATENCY_THRESHOLD",
    "BOTTLENECK_EBS_IOPS_THRESHOLD":       "BOTTLENECK_DISK_IOPS_THRESHOLD",
    "BOTTLENECK_EBS_THROUGHPUT_THRESHOLD": "BOTTLENECK_DISK_THROUGHPUT_THRESHOLD",

    # ----- dict key inside ENAFieldAccessor.analyze_ena_field() return
    #       (TRACKER §10.1 #63)
    "aws_description":   "cloud_description",
}

# Reverse map for dual-write on producer side.
# Note: rebuild from FIELD_ALIASES so single source of truth holds.
REVERSE_ALIASES: Dict[str, str] = {new: old for old, new in FIELD_ALIASES.items()}

# ============================================================
# Pattern-based aliases (device-prefixed columns)
# ============================================================
# iostat columns look like: data_nvme1n1_aws_standard_iops where device id is
# runtime-dynamic. We can't enumerate every device, so use regex substitution.
_DEVICE_PATTERNS = [
    (re.compile(r"^(data|accounts)_([a-z0-9]+)_aws_standard_iops$"),
     r"\1_\2_disk_standard_iops"),
    (re.compile(r"^(data|accounts)_([a-z0-9]+)_aws_standard_throughput_mibs$"),
     r"\1_\2_disk_standard_throughput_mibs"),
    (re.compile(r"^ena_(\w+)_allowance_(exceeded|available)$"),
     r"network_\1_\2"),
]

def _apply_patterns(name: str) -> str:
    for pat, repl in _DEVICE_PATTERNS:
        new = pat.sub(repl, name)
        if new != name:
            return new
    return name

def _build_rename_map(columns: Iterable[str]) -> Dict[str, str]:
    """Build per-DataFrame rename dict: combines static FIELD_ALIASES + dynamic
    device-prefixed pattern substitution. Skips columns already in neutral form."""
    rename_map: Dict[str, str] = {}
    for col in columns:
        if col in FIELD_ALIASES:
            rename_map[col] = FIELD_ALIASES[col]
        else:
            patterned = _apply_patterns(col)
            if patterned != col:
                rename_map[col] = patterned
    return rename_map

# ============================================================
# Public API
# ============================================================
def normalize_df(df: "pd.DataFrame") -> "pd.DataFrame":
    """Read-time normalization: rename legacy AWS/EBS/ENA column names to
    cloud-neutral names. Idempotent (already-neutral columns untouched)."""
    if df is None or df.empty:
        return df
    rename_map = _build_rename_map(df.columns)
    return df.rename(columns=rename_map) if rename_map else df

def normalize_key(key: str) -> str:
    """Normalize a single field/JSON-key/env-var name. Used by code that
    handles individual keys (e.g. JSON parsing, env var lookup)."""
    if key in FIELD_ALIASES:
        return FIELD_ALIASES[key]
    return _apply_patterns(key)

def denormalize_for_dual_write(record: Mapping[str, object]) -> Dict[str, object]:
    """Write-time helper: given a record dict keyed by NEW names, return a
    dict containing BOTH new and old keys (same value). Producers use this
    during the CP-1..CP-5 dual-write transition window. After CP-6 cutover
    this function will be deprecated."""
    out: Dict[str, object] = dict(record)
    for new_key, value in list(record.items()):
        old_key = REVERSE_ALIASES.get(new_key)
        if old_key and old_key not in out:
            out[old_key] = value
    return out

def get_known_aliases() -> Mapping[str, str]:
    """Return read-only view of static alias table (for debugging / tests)."""
    return dict(FIELD_ALIASES)
```

**pytest 测试样例（≥5 个，覆盖 5 类场景）**：

```python
# tests/utils/test_field_normalizer.py — Phase 8a 同步交付
import pandas as pd
import pytest
from utils.field_normalizer import (
    normalize_df, normalize_key, denormalize_for_dual_write,
    FIELD_ALIASES, REVERSE_ALIASES,
)

def test_read_old_names_only():
    """T1: 旧字段名读入 → rename 到新字段名"""
    df = pd.DataFrame({"data_aws_standard_iops": [1, 2], "ebs_util": [0.5, 0.6]})
    out = normalize_df(df)
    assert "data_disk_standard_iops" in out.columns
    assert "disk_util" in out.columns
    assert "data_aws_standard_iops" not in out.columns

def test_read_new_names_idempotent():
    """T2: 新字段名读入 → 不变（已中立）"""
    df = pd.DataFrame({"data_disk_standard_iops": [1, 2], "cpu_usage": [10, 20]})
    out = normalize_df(df)
    assert list(out.columns) == ["data_disk_standard_iops", "cpu_usage"]

def test_read_mixed_old_and_new():
    """T3: 旧新混合 → 仅旧名 rename，新名保留，值不变"""
    df = pd.DataFrame({
        "data_aws_standard_iops": [100],         # 旧
        "accounts_disk_standard_iops": [200],    # 新
        "cpu_iowait": [5.0],                     # 中立
    })
    out = normalize_df(df)
    assert set(out.columns) == {
        "data_disk_standard_iops", "accounts_disk_standard_iops", "cpu_iowait"
    }
    assert out["data_disk_standard_iops"].iloc[0] == 100

def test_empty_df_no_crash():
    """T4: 空 df 不崩"""
    assert normalize_df(pd.DataFrame()).empty
    assert normalize_df(None) is None  # 兼容某些 caller 传 None

def test_unknown_field_passthrough():
    """T5: 未在 FIELD_ALIASES 的字段不变（最坏退化为 identity，不抛 KeyError）"""
    df = pd.DataFrame({"some_future_field_xyz": [1], "data_aws_standard_iops": [2]})
    out = normalize_df(df)
    assert "some_future_field_xyz" in out.columns
    assert "data_disk_standard_iops" in out.columns

def test_device_prefixed_pattern():
    """T6 (bonus): 动态 device 前缀（iostat_collector 输出真实形态）"""
    df = pd.DataFrame({
        "data_nvme1n1_aws_standard_iops": [1],
        "accounts_nvme2n1_aws_standard_throughput_mibs": [2],
    })
    out = normalize_df(df)
    assert "data_nvme1n1_disk_standard_iops" in out.columns
    assert "accounts_nvme2n1_disk_standard_throughput_mibs" in out.columns

def test_dual_write_emits_both_keys():
    """T7 (bonus): 写方双写 → record 同时含新旧 key"""
    rec = denormalize_for_dual_write({"disk_util": 0.85, "cpu_usage": 30})
    assert rec["disk_util"] == 0.85
    assert rec["ebs_util"] == 0.85   # 旧名回写
    assert rec["cpu_usage"] == 30    # 中立字段不动

def test_reverse_map_bijection():
    """T8 (bonus): FIELD_ALIASES 必须是 1:1 映射（防止合并冲突）"""
    assert len(REVERSE_ALIASES) == len(FIELD_ALIASES), \
        "FIELD_ALIASES has duplicate target names; dual-write would conflict"
```

**与下游联动点**：

| 下游消费方 | 联动方式 | 改造时机 |
|---|---|---|
| `utils/csv_data_processor.py:load_csv_data` (~L106) | wrap `pd.read_csv(...)` 返回值 `return normalize_df(df)` — **单点拦截**，下游 5+ reader 自动归一 | CP-1.6 |
| `analysis/comprehensive_analysis.py` / `qps_analyzer.py` / `cpu_ebs_correlation_analyzer.py` / `rpc_deep_analyzer.py` | 继承 CSVDataProcessor 自动获得；如果直接 `pd.read_csv` 需改为 `normalize_df(pd.read_csv(...))` | CP-5.7 |
| `visualization/{performance_visualizer,advanced_chart_generator,report_generator,device_manager,ebs_chart_generator}.py` | 同上 | CP-5.1/5.2/5.4/5.5/5.6 |
| `monitoring/unified_monitor.sh` writer (bash) | bash 端不调 Python；写方在 generate_csv_header / generate_json_metrics 双写新旧两列，**读方靠 normalize_df 归一** | CP-3.1 |
| `monitoring/bottleneck_detector.sh` JSON writer | heredoc 同时 emit `disk_util` + `ebs_util` 两 key（手动双写，因 bash 无 Python helper） | CP-3.3 |

---

### CP-0.3 创建 fake-target stack 模拟器（新增）

**目的**：让 blockchain-node-benchmark 在**无真实 Solana/blockchain 节点 + 无真实 EBS/PD 盘 + 无真实 ENA/gVNIC 网卡**的环境下能端到端跑，用于 CP-1..CP-6 改造过程中的快速回归（CI / 开发机 / 临时 VM）。

**范围声明**：本 CP-0.3 仅做**接口设计 + 实现估算**；实际 mock 代码 build 是 Phase 8b 工作（独立 worker）。本节产物是 Phase 8b 的需求规约。

#### Mock 接口清单（5 类共 8 个 mock 点）

| # | Mock 类别 | Mock 接口 | 业务调用点 (file:line) | 实现思路 | 估算 LOC |
|---|---|---|---|---|---|
| **M1** | HTTP RPC | `POST /` `{"jsonrpc":"2.0","method":"getHealth"}` → `{"jsonrpc":"2.0","result":"ok","id":1}` | `core/master_qps_executor.sh` health probe before benchmark（精确行号待 R 期 worker grep `curl.*jsonrpc` 定位） | Python `http.server.BaseHTTPRequestHandler` 单文件 ~80 LOC; method dispatch by `request.json['method']` ∈ {getHealth, getSlot, getBlockHeight, getAccountInfo, getMultipleAccounts} | 80 |
| **M2** | HTTP RPC (load) | vegeta target 文件中的所有 RPC method (`targets_single.json` / `targets_mixed.json` 由 `tools/target_generator.sh` 生成；精确行号待 R 期定位) | vegeta 进程发起：`core/master_qps_executor.sh` 发 N qps × M duration | 复用 M1 server，单进程足以承受 ≤5000 qps（fake 路径 0 IO）；超过用 `gunicorn -w 4` 横扩 | 0 (复用 M1) |
| **M3** | Block height monitor | **不是 RPC**：`monitoring/block_height_monitor.sh` 全文 452 行 grep `curl/http/jsonrpc/getSlot` **0 命中**；它读取 `block_height_monitor_cache.json`（路径见 L44）+ `node_health_*.cache`（L45）。真正的 RPC 调用在**别处**（候选：master_qps_executor.sh 或外部 daemon 写 cache）。R 期需先定位**谁写这两个 cache 文件**，再 mock 那一层。 | `monitoring/block_height_monitor.sh:L44-45` 读 cache（间接消费） | 方案 A（推荐）：fixture 直接写 `${MEMORY_SHARE_DIR}/block_height_monitor_cache.json` 模拟 lag；方案 B：找到真 RPC writer 后用 M1 server 替代 | 20（方案 A） |
| **M4** | iostat 输出 | `iostat -dx <interval>` 流式输出（被 `monitoring/iostat_collector.sh:L42` 后台 spawn） | `monitoring/iostat_collector.sh:L42` `iostat -dx "$monitor_rate" > "$iostat_data_file" &`；L53 `awk` parse 倒数 20 行 | 替代方案 A（推荐）：shim 脚本 `tests/fake_target_stack/bin/iostat` 放 PATH 前置，每秒打印一行假数据匹配真 iostat header（Device/r/s/w/s/rkB/s/wkB/s/await/util）；替代方案 B：mock `/proc/diskstats` + 真 iostat（更真实但复杂） | 50 (方案 A) |
| **M5** | lsblk / blkid | 设备发现：`lsblk -dno NAME,TYPE,SIZE` | `config/config_loader.sh` 与 `utils/disk_converter.sh` 在 detect_devices 路径调用（待 CP-2.3 改造时精确定位） | PATH-前置 shim，固定返回 `nvme0n1 disk 100G\nnvme1n1 disk 500G\nnvme2n1 disk 500G`（模拟 root + DATA + ACCOUNTS 三盘配置） | 15 |
| **M6** | ethtool -S (AWS ENA) | `ethtool -S eth0` 输出含 `bw_in_allowance_exceeded:` / `bw_out_allowance_exceeded:` / `pps_allowance_exceeded:` 等 6 字段 | `monitoring/ena_network_monitor.sh:L65,L116,L130,L137-138` (grep `:` then awk `$2`) | PATH-前置 shim `ethtool`：按 `$2` (interface) + `$1`=`-S` 派发；预设字段值用 env `MOCK_ENA_BW_IN_EXCEEDED=123` 注入；也支持 GCP 模式返回空（CP-3.2 验证 gVNIC 分支） | 40 |
| **M7** | ethtool -S (GCP gVNIC) | `ethtool -S ens4` 输出含 gVNIC 字段（`rx_packets/tx_packets/rx_dropped/tx_dropped`，**无** allowance 概念） | CP-3.2 改造后新增的 `monitoring/nic_network_monitor.sh` 的 gcp 分支 | 同 M6 shim 的 `CLOUD_PROVIDER=gcp` 分支；按 GCP gVNIC 实际字段集打印 | 30 (复用 M6 shim) |
| **M8** | /proc/net/dev 备用 | 部分代码 fallback 读 `/proc/net/dev` 算 rx_bytes/tx_bytes | `utils/unit_converter.py` 网络计算（具体行待 R 期 worker 精确定位） | 替代方案：`bind mount` 一个假 `/proc/net/dev` 到测试 namespace；或在 Python 端 monkeypatch `open('/proc/net/dev')` | 25 (pytest fixture) |

#### 实现形态（Phase 8b 交付清单）

```
tests/fake_target_stack/
├── README.md                       # 启动方式 + 接口 contract
├── docker-compose.yml              # 一键拉起 M1+M2+M3 (HTTP server) + M4-M7 (PATH shim 容器内 /usr/local/bin 前置)
├── server/
│   ├── rpc_server.py               # M1+M2+M3 HTTP server (~100 LOC, stdlib only)
│   └── state.py                    # slot counter / lag injection knobs
├── bin/
│   ├── iostat                      # M4 shim (~50 LOC bash)
│   ├── lsblk                       # M5 shim (~15 LOC bash)
│   └── ethtool                     # M6+M7 shim (~50 LOC bash, CLOUD_PROVIDER 派发)
├── fixtures/
│   └── proc_net_dev_fake           # M8 假 /proc/net/dev (5 行静态)
└── pytest_plugin.py                # pytest fixture: monkeypatch open() + PATH inject
```

**启动 / 烟测命令**（Phase 8b 完工后样例）：

```bash
# 启动整个 fake stack（docker-compose 拉起 HTTP server + PATH shim 注入容器）
cd tests/fake_target_stack && docker-compose up -d

# 在容器内跑一次 benchmark（验证 zero 真实云依赖）
docker-compose exec runner bash -c '
    export LOCAL_RPC_URL=http://localhost:8899
    export MAINNET_RPC_URL=http://localhost:8899/mainnet
    export CLOUD_PROVIDER=gcp     # 或 aws 切换 ethtool 字段集
    bash core/blockchain_node_benchmark.sh quick
'

# 验证产物 CSV 列名 platform-aware
docker-compose exec runner head -1 logs/performance_*.csv | grep -oE 'disk_standard_iops|aws_standard_iops'
```

**估算总 LOC**：~260 行（HTTP server 100 + 3 个 bash shim 115 + pytest plugin 25 + docker-compose 20）。Phase 8b 1 worker 1 day。

**与 CP-1..CP-6 的关系**：

- CP-1..CP-5 的"验证命令"列**只覆盖单文件改造正确性**（变量值、case 分支、rename 生效），不验证端到端业务流。
- Phase 8b fake-target stack 上线后，**每个 CP-N 完成时**额外跑一次 `docker-compose up && bash core/blockchain_node_benchmark.sh quick` 烟测，确保 CP-N 改动没有破坏端到端 pipeline。
- Phase 8c 真 GCP 环境回归是最后兜底，但成本高（GCP VM ≥ $5/h），日常 CI 用 fake stack 即可。

---

### CP-0.4 创建 config/providers/{aws,gcp,other}_provider.sh（3 个 provider 实现，新增）

> **E1+ 新增章节**。本节给出 3 个 provider 文件的**完整 bash 代码**（每个 ~80 行，无省略），严格按 §0.3 表格的 AWS / GCP / Other 三列返回值实现。所有 15 getter 必须存在且签名一致，否则 `config/cloud_provider.sh` contract sanity check 会 fail-fast 拒绝加载（详见 CP-0.1.2）。

**3 文件对等性原则**（§0.1 第 2 条 + §0.7 决策 6 第 3 条）：
- 3 个文件**字数 / 行数大致对等**，无主从关系。
- Other provider 严格按 §0.3 修订后的中立列实现，**禁止抄 AWS 默认值**（如 `gp3` / `aws_standard` / `EBS`），违者 CP-0.5 contract test 第 2 阶段 AWS≠GCP 防抄断言会触发额外的 AWS≠Other 反例查（Other 不参与 AWS≠Other 比对，但代码 review 必须人工核对）。
- 文件末尾**不需要 `export -f`**（统一由 `config/cloud_provider.sh` 批量 export，避免分散管理）。

#### CP-0.4.1 config/providers/aws_provider.sh（完整代码，~80 行）

```bash
#!/usr/bin/env bash
# config/providers/aws_provider.sh — E1+ AWS Provider Implementation
#
# 15 getter 实现（严格按 §0.3 表格 AWS 列）。
# 永远只被 config/cloud_provider.sh 内部 source 一次（在抽象层 source guard 之后）。
# 无 source guard、无 export -f（由抽象层统一管理）。

# --- metadata 子组 (IMDSv2) ---
get_metadata_endpoint()    { echo "http://169.254.169.254"; }
get_metadata_header()      { echo ""; }   # AWS IMDSv2 token 由调用方单独走 -H X-aws-ec2-metadata-token，无固定 header
get_metadata_api_path()    { echo "latest"; }

# --- disk baseline 子组 (gp3 默认值) ---
get_baseline_io_kib()         { echo "16"; }    # gp3 默认 IO 单元 16 KiB
get_baseline_throughput_kib() { echo "128"; }   # gp3 默认 throughput baseline 128 KiB

# --- disk type 子组 ---
get_default_disk_type()    { echo "gp3"; }
get_disk_type_options()    { echo "gp3 io2 instance-store"; }

# --- NIC 子组 (ENA) ---
get_nic_driver()           { echo "ena"; }
get_nic_allowance_fields() {
    # 6 字段 CSV，对应 §0.3 #9 / §13.5
    echo "bw_in_allowance_exceeded,bw_out_allowance_exceeded,pps_allowance_exceeded,conntrack_allowance_exceeded,linklocal_allowance_exceeded,conntrack_allowance_available"
}
get_nic_monitor_process_name() { echo "ena_network_monitor"; }

# --- 命名 / 输出 子组 ---
get_disk_field_prefix()    { echo "aws_standard"; }   # §13.6 unified_monitor.sh / §13.12 iostat_collector.sh
get_archive_dir_prefix()   { echo "aws_run_"; }       # §13.19 benchmark_archiver.sh L219
get_bottleneck_label()     { echo "EBS"; }            # §13.21 comprehensive_analysis.py 'EBS' literal

# --- 平台元信息 子组 ---
get_platform_display_name() { echo "AWS"; }
get_doc_url() {
    local category="${1:-}"
    case "$category" in
        disk) echo "https://docs.aws.amazon.com/ebs/latest/userguide/general-purpose.html" ;;
        nic)  echo "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ena-allowance.html" ;;
        imds) echo "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-metadata.html" ;;
        io2)  echo "https://docs.aws.amazon.com/ebs/latest/userguide/provisioned-iops.html" ;;
        *)    echo "https://docs.aws.amazon.com/" ;;
    esac
}

# === 文件末尾不需要 export -f （由 config/cloud_provider.sh 批量 export）===
```

#### CP-0.4.2 config/providers/gcp_provider.sh（完整代码，~80 行）

```bash
#!/usr/bin/env bash
# config/providers/gcp_provider.sh — E1+ GCP Provider Implementation
#
# 15 getter 实现（严格按 §0.3 表格 GCP 列 + E1-assessment.md §2 表格）。
# 永远只被 config/cloud_provider.sh 内部 source 一次。

# --- metadata 子组 ---
get_metadata_endpoint()    { echo "http://metadata.google.internal"; }
get_metadata_header()      { echo "Metadata-Flavor: Google"; }       # §13.5 P0 — GCP IMDS 必须带此 header
get_metadata_api_path()    { echo "computeMetadata/v1"; }

# --- disk baseline 子组 (Hyperdisk Extreme 默认值) ---
get_baseline_io_kib()         { echo "4"; }     # Hyperdisk 4 KiB block size
get_baseline_throughput_kib() { echo "256"; }   # Hyperdisk Extreme throughput baseline 256 KiB

# --- disk type 子组 ---
get_default_disk_type()    { echo "hyperdisk-extreme"; }
get_disk_type_options()    { echo "pd-balanced pd-ssd pd-extreme hyperdisk-extreme local-ssd"; }

# --- NIC 子组 (gVNIC) ---
get_nic_driver()           { echo "gve"; }
get_nic_allowance_fields() {
    # GCP gVNIC 无 allowance 概念（§0.3 #9 — 严格返回空）
    echo ""
}
get_nic_monitor_process_name() { echo "gvnic_network_monitor"; }   # CP-3.2 重命名 ena_network_monitor → gvnic_network_monitor

# --- 命名 / 输出 子组 ---
get_disk_field_prefix()    { echo "baseline"; }   # §13.6 / §13.12 — GCP 字段命名用 baseline_iops / baseline_throughput
get_archive_dir_prefix()   { echo "gcp_run_"; }   # §13.19 benchmark_archiver.sh L219
get_bottleneck_label()     { echo "Disk"; }       # §13.21 — GCP 用通用语义 "Disk"

# --- 平台元信息 子组 ---
get_platform_display_name() { echo "GCP"; }
get_doc_url() {
    local category="${1:-}"
    case "$category" in
        disk) echo "https://cloud.google.com/compute/docs/disks/hyperdisks" ;;
        nic)  echo "https://cloud.google.com/compute/docs/networking/using-gvnic" ;;
        imds) echo "https://cloud.google.com/compute/docs/metadata/overview" ;;
        io2)  echo "https://cloud.google.com/compute/docs/disks/hyperdisks#hd-extreme" ;;
        *)    echo "https://cloud.google.com/compute/docs/" ;;
    esac
}

# === 文件末尾不需要 export -f （由 config/cloud_provider.sh 批量 export）===
```

#### CP-0.4.3 config/providers/other_provider.sh（完整代码，~80 行）

> **关键合规要求**（§0.7 决策 6 第 1 条 + §0.3 E1+ Other 列修订原则）：
> - Other 不是「AWS 的降级版」，是「未知平台的中立 fallback」。
> - 涉及 AWS 特有概念（IMDS endpoint / ENA allowance / `_aws_standard_*` 字段前缀）的 getter，Other **必须返回空字符串或中立值**。
> - **禁止返回** `gp3` / `aws_standard` / `EBS` / `ena` / `aws_run_` 等 AWS 特有字面值。
> - 调用方负责判空：`endpoint=$(get_metadata_endpoint); [[ -z "$endpoint" ]] && { log_warn "..."; return 0; }`

```bash
#!/usr/bin/env bash
# config/providers/other_provider.sh — E1+ Other (Neutral) Provider Implementation
#
# 15 getter 实现（严格按 §0.3 Other 列 — 中立 fallback，禁止偏 AWS）。
# 适用场景：本地开发机 / IDC 自建机 / 未识别云平台 / CI 环境。
# 永远只被 config/cloud_provider.sh 内部 source 一次。

# --- metadata 子组（未知平台无 IMDS — §0.3 #1/2/3）---
get_metadata_endpoint()    { echo ""; }   # 调用方判空跳过 probe
get_metadata_header()      { echo ""; }   # 无平台特定 header
get_metadata_api_path()    { echo ""; }   # 调用方判空

# --- disk baseline 子组（未知，调用方需处理 — §0.3 #4/5）---
get_baseline_io_kib()         { echo "0"; }   # 0 = 未知，禁止默认 16 (AWS) 或 4 (GCP)
get_baseline_throughput_kib() { echo "0"; }   # 0 = 未知，禁止默认 128 / 256

# --- disk type 子组（未知平台不预设盘类型 — §0.3 #6/7）---
get_default_disk_type()    { echo ""; }       # 中立空值，不偏 gp3 / hyperdisk-extreme
get_disk_type_options()    { echo ""; }       # 空集，禁止枚举 AWS / GCP 类型

# --- NIC 子组（未知 NIC driver — §0.3 #8/9/10）---
get_nic_driver()           { echo ""; }       # 不偏 ena / gve
get_nic_allowance_fields() { echo ""; }       # 中立空集（与 GCP 行为一致）
get_nic_monitor_process_name() { echo ""; }   # 无平台特定 monitor

# --- 命名 / 输出 子组（中立命名，禁止偏 AWS — §0.3 #11/12/13）---
get_disk_field_prefix()    { echo "standard"; }   # 中立命名，绝不返回 "aws_standard"
get_archive_dir_prefix()   { echo "run_"; }       # 保持通用前缀（§0.3 #12 Other 列）
get_bottleneck_label()     { echo "Disk"; }       # 与 GCP 共享通用语义，禁止返回 "EBS"

# --- 平台元信息 子组（§0.3 #14/15）---
get_platform_display_name() { echo "OTHER"; }
get_doc_url() {
    local category="${1:-}"
    # 无平台特定文档；返回空字符串告知调用方使用通用提示
    echo ""
}

# === 文件末尾不需要 export -f （由 config/cloud_provider.sh 批量 export）===
#
# 合规自查（CP-0.5 contract test 会在 review 阶段对比）：
#   ✅ 无任何 'gp3' / 'aws_standard' / 'EBS' / 'ena' 字面（防抄 AWS）
#   ✅ 无任何 'hyperdisk' / 'baseline' / 'gve' / 'gvnic' 字面（防抄 GCP）
#   ✅ get_disk_field_prefix 返回 "standard" 而非 "aws_standard"（§0.7 决策 6 反例）
```

#### CP-0.4.4 三 provider 关键差异对照（自验表）

| getter | AWS 返回 | GCP 返回 | Other 返回 | AWS≠GCP? |
|---|---|---|---|---|
| `get_metadata_endpoint` | `http://169.254.169.254` | `http://metadata.google.internal` | `""` | ✅ |
| `get_metadata_header` | `""` | `Metadata-Flavor: Google` | `""` | ✅ |
| `get_metadata_api_path` | `latest` | `computeMetadata/v1` | `""` | ✅ |
| `get_baseline_io_kib` | `16` | `4` | `0` | ✅ |
| `get_baseline_throughput_kib` | `128` | `256` | `0` | ✅ |
| `get_default_disk_type` | `gp3` | `hyperdisk-extreme` | `""` | ✅ |
| `get_disk_type_options` | `gp3 io2 instance-store` | `pd-balanced pd-ssd pd-extreme hyperdisk-extreme local-ssd` | `""` | ✅ |
| `get_nic_driver` | `ena` | `gve` | `""` | ✅ |
| `get_nic_allowance_fields` | 6 字段 CSV | `""` | `""` | ✅ |
| `get_nic_monitor_process_name` | `ena_network_monitor` | `gvnic_network_monitor` | `""` | ✅ |
| `get_disk_field_prefix` | `aws_standard` | `baseline` | `standard` | ✅ |
| `get_archive_dir_prefix` | `aws_run_` | `gcp_run_` | `run_` | ✅ |
| `get_bottleneck_label` | `EBS` | `Disk` | `Disk` | ✅ |
| `get_platform_display_name` | `AWS` | `GCP` | `OTHER` | ✅ |
| `get_doc_url disk` | AWS EBS doc | GCP Hyperdisk doc | `""` | ✅ |

**结论**：15 getter × AWS≠GCP 全绿（15/15）。CP-0.5 contract test 第 2 阶段 AWS≠GCP 防抄断言可对其中 7 个关键值断言（详见 CP-0.5）。

---

### CP-0.5 创建 tests/test_provider_contract.sh（契约测试，新增）

> **E1+ 新增章节**，对应 §0.7 决策 3 + 决策 6 第 3 条。本测试是 CI gate 的一部分：任何新加 provider（Azure / OCI 等）或修改现有 provider 时，必须 `bash tests/test_provider_contract.sh` 全绿才能合入主干。

**目标**：
1. **Phase 1 完整性检查**：aws/gcp/other 3 个 provider 都必须实现 15 个 getter；aws/gcp 必须返回非空（other 允许返回空，因为是中立 fallback）。
2. **Phase 2 AWS≠GCP 防抄断言**（§0.7 决策 6 第 3 条）：7 个关键 getter 在 AWS 和 GCP 上返回值**必须不同**，否则视为 GCP 实现抄了 AWS（性能对比公平性会因此失真）。

**完整测试脚本**（~80 行）：

```bash
#!/usr/bin/env bash
# tests/test_provider_contract.sh
# E1+ Provider Contract Test — 验证 aws/gcp/other 三 provider 都实现了 15 个 getter
# 且 AWS≠GCP 防抄断言（§0.7 决策 6 第 3 条）。
# 任一断言失败 → exit 1，CI gate 拒绝合入。

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

REQUIRED_GETTERS=(
    get_metadata_endpoint get_metadata_header get_metadata_api_path
    get_baseline_io_kib get_baseline_throughput_kib
    get_default_disk_type get_disk_type_options
    get_nic_driver get_nic_allowance_fields get_nic_monitor_process_name
    get_disk_field_prefix get_archive_dir_prefix get_bottleneck_label
    get_platform_display_name get_doc_url
)

FAIL=0
TOTAL_CHECKS=0

# ============================================================
# Phase 1: 三 provider 都实现 15 getter（45 项检查）
# ============================================================
echo "=== Phase 1: 完整性检查 (3 providers × 15 getters = 45 checks) ==="
for provider in aws gcp other; do
    output=$(CLOUD_PROVIDER=$provider bash -c "
        export PROJECT_ROOT='$PROJECT_ROOT'
        unset CLOUD_PROVIDER_DETECTED
        source config/cloud_provider.sh >/dev/null 2>&1
        for getter in ${REQUIRED_GETTERS[*]}; do
            declare -F \$getter >/dev/null || { echo \"FAIL: \$getter missing in $provider\" >&2; exit 1; }
            val=\$(\$getter 2>/dev/null || true)
            # other 允许返回空 (中立 fallback); aws/gcp 必须非空 (15 getter 都有意义)
            # 例外：aws 的 get_metadata_header 故意返回空（IMDSv2 token 走 -H X-aws-ec2-metadata-token）
            if [[ \"$provider\" != \"other\" && -z \"\$val\" ]]; then
                if [[ \"$provider\" == \"aws\" && \"\$getter\" == \"get_metadata_header\" ]]; then
                    : # 允许 AWS get_metadata_header 返回空（已知特例）
                elif [[ \"$provider\" == \"gcp\" && \"\$getter\" == \"get_nic_allowance_fields\" ]]; then
                    : # 允许 GCP get_nic_allowance_fields 返回空（gVNIC 无 allowance 概念）
                else
                    echo \"FAIL: \$getter returned empty in $provider\" >&2; exit 1
                fi
            fi
        done
        echo \"$provider: OK (15/15 getters)\"
    " 2>&1) || { echo "$output"; FAIL=1; TOTAL_CHECKS=$((TOTAL_CHECKS+15)); continue; }
    echo "$output"
    TOTAL_CHECKS=$((TOTAL_CHECKS+15))
done

# ============================================================
# Phase 2: AWS ≠ GCP 防抄断言（§0.7 决策 6 第 3 条）
# ============================================================
echo ""
echo "=== Phase 2: AWS≠GCP 防抄断言 (7 critical getters) ==="
ANTI_PLAGIARISM_GETTERS=(
    get_metadata_endpoint
    get_metadata_header
    get_disk_field_prefix
    get_nic_driver
    get_archive_dir_prefix
    get_bottleneck_label
    get_platform_display_name
)
for getter in "${ANTI_PLAGIARISM_GETTERS[@]}"; do
    aws_val=$(CLOUD_PROVIDER=aws bash -c "
        export PROJECT_ROOT='$PROJECT_ROOT'
        unset CLOUD_PROVIDER_DETECTED
        source config/cloud_provider.sh >/dev/null 2>&1
        $getter")
    gcp_val=$(CLOUD_PROVIDER=gcp bash -c "
        export PROJECT_ROOT='$PROJECT_ROOT'
        unset CLOUD_PROVIDER_DETECTED
        source config/cloud_provider.sh >/dev/null 2>&1
        $getter")
    if [[ "$aws_val" == "$gcp_val" ]]; then
        echo "FAIL: $getter returned identical value in AWS and GCP ('$aws_val') — provider 抄袭嫌疑" >&2
        FAIL=1
    else
        echo "OK   $getter: aws='$aws_val' ≠ gcp='$gcp_val'"
    fi
    TOTAL_CHECKS=$((TOTAL_CHECKS+1))
done

# ============================================================
# 汇总
# ============================================================
echo ""
if [[ $FAIL -eq 0 ]]; then
    echo "✅ Contract test PASS ($TOTAL_CHECKS checks: 45 completeness + 7 anti-plagiarism)"
    exit 0
else
    echo "❌ Contract test FAIL ($TOTAL_CHECKS checks attempted)" >&2
    exit 1
fi
```

**预期输出**（全绿）：

```
=== Phase 1: 完整性检查 (3 providers × 15 getters = 45 checks) ===
aws: OK (15/15 getters)
gcp: OK (15/15 getters)
other: OK (15/15 getters)

=== Phase 2: AWS≠GCP 防抄断言 (7 critical getters) ===
OK   get_metadata_endpoint: aws='http://169.254.169.254' ≠ gcp='http://metadata.google.internal'
OK   get_metadata_header: aws='' ≠ gcp='Metadata-Flavor: Google'
OK   get_disk_field_prefix: aws='aws_standard' ≠ gcp='baseline'
OK   get_nic_driver: aws='ena' ≠ gcp='gve'
OK   get_archive_dir_prefix: aws='aws_run_' ≠ gcp='gcp_run_'
OK   get_bottleneck_label: aws='EBS' ≠ gcp='Disk'
OK   get_platform_display_name: aws='AWS' ≠ gcp='GCP'

✅ Contract test PASS (52 checks: 45 completeness + 7 anti-plagiarism)
```

**典型失败案例 1**：GCP provider 的 `get_disk_field_prefix` 误抄成 `aws_standard`。

```
=== Phase 2: AWS≠GCP 防抄断言 ===
FAIL: get_disk_field_prefix returned identical value in AWS and GCP ('aws_standard') — provider 抄袭嫌疑
❌ Contract test FAIL
```

**典型失败案例 2**：新加 Azure provider 漏实现 `get_nic_driver`。

```
=== Phase 1: 完整性检查 ===
FAIL: get_nic_driver missing in azure
❌ Contract test FAIL
```

**CI 集成建议**：
- 在 `.github/workflows/ci.yml`（或同等 CI 配置）的 lint stage 后增加 `bash tests/test_provider_contract.sh`。
- 任何 PR 触碰 `config/cloud_provider.sh` 或 `config/providers/*` 必须强制此 check 通过。
- E2.5 阶段 CI 还应额外 grep `\\$\\{CLOUD_PROVIDER:-` 在 config/ / monitoring/ / tools/ / analysis/ / visualization/ 下应零命中（§0.7 决策 6 第 4 条）。

### CP-0.5.1 Shell 数组兼容性断言（背景：ENA_ALLOWANCE_FIELDS 历史遗留）

**背景**：Y- 历史代码用 `readonly` bash array `ENA_ALLOWANCE_FIELDS=(bw_in_allowance_exceeded bw_out_allowance_exceeded pps_allowance_exceeded conntrack_allowance_exceeded linklocal_allowance_exceeded conntrack_allowance_available)` 定义 6 个 AWS ENA 饱和字段。Y+ 升级后该数组被拆入 `monitoring/network/aws.sh` 内部 (`AWS_ENA_FIELDS`)，GCP/Other provider 各自定义自己的扩展字段集合。Contract test 必须断言三平台 CSV header 列数和数组安全性，避免 word-splitting 类 silent bug。

**契约断言条目**：

1. **AWS header 列数 = 13**：`source monitoring/network/aws.sh && generate_network_csv_header` 输出 = 7 基础列 + AWS_ENA_FIELDS 数组长度 (6) + 1 saturation_signal 列 = 13 列
2. **GCP header 列数 = 10**：`source monitoring/network/gcp.sh && generate_network_csv_header` 输出 = 6 基础列 + 3 gvnic 列 + 1 saturation_signal = 10 列
3. **Other header 列数 = 7**：`source monitoring/network/other.sh && generate_network_csv_header` 输出 = 6 基础列 + 1 saturation_signal = 7 列
4. **bash 版本 >= 4**：任意 provider source 后 `BASH_VERSINFO[0] >= 4`（associative array / readonly array 特性依赖）
5. **数组迭代必须加引号**：`monitoring/network/` 下所有 `${ARR[@]}` 展开必须用 `"${ARR[@]}"` 包裹（避免空格分裂）。Contract test 反向 grep 这一点，发现裸露展开即 fail。

**Bash 测试骨架** (`tests/contract/test_network_array_compat.sh`，~50 LOC)：

```bash
#!/bin/bash
# tests/contract/test_network_array_compat.sh

set -euo pipefail

test_aws_csv_column_count() {
    source monitoring/network/aws.sh
    local header=$(generate_network_csv_header)
    local cols=$(echo "$header" | awk -F',' '{print NF}')
    [[ "$cols" -eq 13 ]] || { echo "FAIL: AWS expects 13 cols, got $cols"; exit 1; }
}

test_gcp_csv_column_count() {
    source monitoring/network/gcp.sh
    local header=$(generate_network_csv_header)
    local cols=$(echo "$header" | awk -F',' '{print NF}')
    [[ "$cols" -eq 10 ]] || { echo "FAIL: GCP expects 10 cols, got $cols"; exit 1; }
}

test_other_csv_column_count() {
    source monitoring/network/other.sh
    local header=$(generate_network_csv_header)
    local cols=$(echo "$header" | awk -F',' '{print NF}')
    [[ "$cols" -eq 7 ]] || { echo "FAIL: Other expects 7 cols, got $cols"; exit 1; }
}

test_bash_version() {
    [[ "${BASH_VERSINFO[0]}" -ge 4 ]] || { echo "FAIL: bash 4+ required"; exit 1; }
}

test_array_iteration_quoted() {
    # 反向 grep: 不能有 ${ARR[@]} 不带引号 (会触发 word splitting)
    if grep -rE '\$\{[A-Z_]+\[@\]\}[^"]' monitoring/network/ 2>/dev/null | grep -v '"\$\{'; then
        echo "FAIL: unquoted array expansion found in monitoring/network/"
        exit 1
    fi
}

main() {
    test_aws_csv_column_count
    test_gcp_csv_column_count
    test_other_csv_column_count
    test_bash_version
    test_array_iteration_quoted
    echo "PASS: all network array compat tests"
}

main
```

**触发场景**：
- Y- → Y+ 升级过程中如果 `AWS_ENA_FIELDS` 拆分时遗漏一个字段（例如把 6 个减成 5 个），AWS header 列数变 12，test 立即 fail
- 如果有开发者把 `for f in ${ARR[@]}` 写成不带引号形式，遇到字段名含空格立即异常，test 5 在 CI 阶段就拦截
- GCP gvnic 字段从 3 个扩展到 4 个时，test 2 强制开发者同步更新断言常量（防止 silent drift）

### CP-0.5.2 NIC 接口契约测试（Y+ 4 接口对称性）

**背景**：CP-2.5（NIC 接口抽象层）规定每个 provider (aws/gcp/other) 必须实现 4 个标准接口函数。Contract test 在 CI 阶段强制断言三 provider 实现签名一致、输出格式一致、语义可枚举。

**4 接口契约表**：

| 接口函数 | 输入 | 输出契约 |
|---|---|---|
| `init_network_monitoring` | `NETWORK_INTERFACE` env | 返 0（就绪）或 1（不可用），绝不能 return 2+ |
| `generate_network_csv_header` | 无 | stdout 单行 CSV header，首列 `timestamp`，末列 `network_saturation_signal` |
| `collect_network_metrics` | 无 | stdout 单行 CSV row，列数 = header 列数 |
| `get_network_field_metadata` | `field_name` | stdout 单词（`throughput` \| `packet_count` \| `saturation_counter` \| `drop_counter` \| `saturation_signal` \| `gauge` \| `unknown`） |

**Bash 测试骨架** (`tests/contract/test_network_interface_contract.sh`，~80 LOC)：

```bash
#!/bin/bash
# tests/contract/test_network_interface_contract.sh

set -euo pipefail

test_provider_implements_4_functions() {
    local provider="$1"
    source "monitoring/network/${provider}.sh"
    for fn in init_network_monitoring generate_network_csv_header collect_network_metrics get_network_field_metadata; do
        declare -F "$fn" > /dev/null || { echo "FAIL: $provider missing $fn"; exit 1; }
    done
}

test_header_first_col_is_timestamp() {
    local provider="$1"
    source "monitoring/network/${provider}.sh"
    local header=$(generate_network_csv_header)
    local first=$(echo "$header" | awk -F',' '{print $1}')
    [[ "$first" == "timestamp" ]] || { echo "FAIL: $provider first col not timestamp: $first"; exit 1; }
}

test_header_last_col_is_saturation_signal() {
    local provider="$1"
    source "monitoring/network/${provider}.sh"
    local header=$(generate_network_csv_header)
    local last=$(echo "$header" | awk -F',' '{print $NF}')
    [[ "$last" == "network_saturation_signal" ]] || { echo "FAIL: $provider last col not network_saturation_signal: $last"; exit 1; }
}

test_row_col_count_matches_header() {
    local provider="$1"
    source "monitoring/network/${provider}.sh"
    init_network_monitoring || { echo "SKIP: $provider init failed (expected on cross-platform test)"; return 0; }
    local header_cols=$(generate_network_csv_header | awk -F',' '{print NF}')
    local row_cols=$(collect_network_metrics | awk -F',' '{print NF}')
    [[ "$header_cols" -eq "$row_cols" ]] || { echo "FAIL: $provider header=$header_cols row=$row_cols"; exit 1; }
}

test_metadata_returns_known_semantic() {
    local provider="$1"
    source "monitoring/network/${provider}.sh"
    local valid_types="throughput packet_count saturation_counter drop_counter saturation_signal gauge unknown"
    local r=$(get_network_field_metadata "rx_bytes")
    echo "$valid_types" | grep -qw "$r" || { echo "FAIL: $provider unknown semantic: $r"; exit 1; }
}

main() {
    for provider in aws gcp other; do
        test_provider_implements_4_functions "$provider"
        test_header_first_col_is_timestamp "$provider"
        test_header_last_col_is_saturation_signal "$provider"
        test_row_col_count_matches_header "$provider"
        test_metadata_returns_known_semantic "$provider"
    done
    echo "PASS: all NIC interface contract tests for aws/gcp/other"
}

main
```

**Cross-provider 不变量**（必须在三 provider 间维持的对称属性）：

1. **5 列基础对称**：三 provider 都必须包含 `rx_bytes`, `tx_bytes`, `rx_packets`, `tx_packets`, `network_saturation_signal` 这 5 个字段（基础 NIC 计数）。异构 provider 的差异只能在"额外字段"上体现，不能砍基础字段。
2. **字段异构合法**：AWS 额外多 6 个 `ena_*`（allowance counters），GCP 额外多 3 个 `gvnic_*`（rx_no_buffer / tx_drops / rx_drops），Other 不加。差异由 provider 自定决定，contract test 不强制相等。
3. **semantic 类型子集关系**：每个 provider 的 `get_network_field_metadata` 返回值集合 ⊆ {throughput, packet_count, saturation_counter, drop_counter, saturation_signal, gauge, unknown}。但 `throughput` / `packet_count` / `saturation_signal` 三种类型必须在三平台都至少返回过一次（保证下游 analysis 层能跨 provider 统一聚合）。
4. **CSV 列序稳定**：同一 provider 在同一次会话内多次调用 `generate_network_csv_header` 必须返回完全相同字符串（不能因 hash 顺序变化导致 CSV 错列）。

**Cross-provider 不变量 bash 骨架**（追加到 main 末尾）：

```bash
test_cross_provider_basic_5_cols() {
    local required="rx_bytes tx_bytes rx_packets tx_packets network_saturation_signal"
    for provider in aws gcp other; do
        (source "monitoring/network/${provider}.sh"
         local header=$(generate_network_csv_header)
         for col in $required; do
             echo "$header" | tr ',' '\n' | grep -qw "$col" \
                 || { echo "FAIL: $provider missing base col $col"; exit 1; }
         done)
    done
}

test_cross_provider_semantic_coverage() {
    local required_types="throughput packet_count saturation_signal"
    for t in $required_types; do
        local found=0
        for provider in aws gcp other; do
            (source "monitoring/network/${provider}.sh"
             # 抽样 provider 各字段, 任一字段返回 t 即算覆盖
             for f in rx_bytes tx_bytes rx_packets tx_packets network_saturation_signal; do
                 r=$(get_network_field_metadata "$f" 2>/dev/null || echo unknown)
                 [[ "$r" == "$t" ]] && exit 0
             done
             exit 1) && found=1
        done
        [[ "$found" -eq 1 ]] || { echo "FAIL: semantic $t not covered by any provider"; exit 1; }
    done
}
```

**触发场景**：
- 新 provider（例如 azure.sh）漏实现 `get_network_field_metadata` → test 1 立即 fail
- 某 provider header 末列不小心改成 `saturation_signal`（少了 `network_` 前缀）→ test 3 fail
- collect_network_metrics 返回行多 / 少一列（例如新增字段忘记同步 header）→ test 4 fail
- 引入返回值 `bytes_per_sec`（不在 7 种语义枚举内）→ test 5 fail
- AWS 砍了 `rx_packets`（基础对称破坏）→ cross-provider 不变量 test 1 fail

---

## CP-1：utils/ 层改造（5 改 + 1 新）

> **CP-1 概览**：utils/ 层是 GCP 改造金字塔最底层。本层完成后所有上游层 (config/ monitoring/ tools/ analysis/) 才有干净的 helper 可调用。
>
> **关键发现 (Round 2026-05-18 实跑)**：
> - utils/ebs_converter.sh 是 utils/ 唯一 P0 高危文件 (AWS 字面 36 处 + 7 个 caller)
> - **utils/unified_logger.sh 和 utils/error_handler.sh 都是 grep AWS/EBS/ENA = 0 命中** —— 实际无需改造，仅做注释 + 文档行说明保留
> - utils/unified_logger.py 同样 0 命中 —— 比 .sh 版更精简，无 AWS metadata 检测
> - utils/ena_field_accessor.py 7 字段全是 AWS ENA 专属，但 class 重命名是纯加 alias 不破坏 ABI
> - utils/csv_data_processor.py 需新增 normalize_df 钩子但要做反向兼容
>
> **CP-1 总工作量**：1.5 工作日 (比骨架版预估 2d 少 0.5d，因为 CP-1.2/1.3 实际无改动)

---

### CP-1.1 utils/ebs_converter.sh → utils/disk_converter.sh（重命名 + 内容改造）⭐ 唯一 P0

**目标**：把 AWS-only 的 IOPS/吞吐转换 + io2 算法 + EBS 类型推荐改造成 platform-aware；保留 AWS 行为零回归。

**来源依据**：file-notes/ebs_converter.sh.md §8 (12 个 EC-* 阻塞点 + 9 个 EC-N* 命名清单) + CORRECTED_PLAN 主表 11.2 / 12.7 / 12.8。

#### CP-1.1.A 改造矩阵 (12 个 EC-* 阻塞点)

| # | 行号 | 改造点 | 等级 | 改造方式 |
|---|---|---|---|---|
| EC-1 | L25/L31 | AWS 文档 URL `docs.aws.amazon.com/ebs/...` | P0 | 通过 `$DISK_DOC_URL` env 注入 (system_config.sh 派发) |
| EC-2 | L83 | AWS 文档 URL (死代码内 recommend_ebs_type) | P0 | 同 EC-1 或随死代码删除 |
| EC-3 | L51/L97 (经间接) | EBS 类型 case 仅识别 5 类 | P0 | case 扩 GCP 5 类型 (pd-ssd/pd-balanced/pd-extreme/hyperdisk-extreme/local-ssd) |
| EC-4 | L62-67 | `calculate_io2_throughput` AWS io2 专属公式 | P0 | 函数体改用 `[[ ! " $(get_disk_type_options) " =~ ' io2 ' ]] && { echo 0; return; }` 早返回（按能力判定，非平台名，§0.7 决策 6） |
| EC-5 | L26/L44/L62/L89/L113/L72 | 4 函数名含 AWS / 1 含 EBS | P1 | 双写 export -f alias (保留 1 Round) |
| EC-6 | L7-9 | `AWS_EBS_BASELINE_THROUGHPUT_SIZE_KIB` 双 AWS+EBS 字面 | P1 | 删除本文件预定义；业务方改调 `$(get_baseline_throughput_kib)`；旧名 alias 由 CP-2 system_config.sh 派发（§0.7 决策 6 — 禁 `${CLOUD_PROVIDER:-aws}` 默认） |
| EC-7 | L13/L15 | `IO2_THROUGHPUT_RATIO` / `IO2_MAX_THROUGHPUT` 无前缀 | P2 | 加 `AWS_` 前缀；本文件 L66/L68 唯一引用 |
| EC-8 | L89-108 | `recommend_ebs_type` 19 行死代码 | P1 | 标记 DEPRECATED 下 Round 删 |
| EC-9 | L113-131 | `calculate_weighted_avg_io_size` 19 行死代码 | P2 | 标记 DEPRECATED |
| EC-10 | L72-86 | `analyze_instance_store_performance` 17 行死代码 | P2 | 标记 DEPRECATED |
| EC-11 | L3/L4/L6/L24/L30/L42/L77/L82 | 8 处注释含 AWS/EBS 字面 | P3 | 批量替换为 `Cloud Disk (AWS EBS / GCP PD/Hyperdisk)` |
| EC-12 | L151-153 | usage 文本含 AWS 字面 | P3 | EC-5 切换后同步更新 |

#### CP-1.1.B 4 个核心改造点的完整改前/改后代码

**改造点 1：L7 throughput baseline — 删除 case 块，改 getter 调用 (§0.7 决策 6)**
```bash
# === 改前 (业务代码不动，仅展示 baseline) ===
AWS_EBS_BASELINE_THROUGHPUT_SIZE_KIB=${AWS_EBS_BASELINE_THROUGHPUT_SIZE_KIB:-128}

# === 改后 (utils/disk_converter.sh:L7) ===
# E1+ 方案：不再在本文件预定义 CLOUD_THROUGHPUT_BASELINE_KIB 变量，
# 也不再写 ${CLOUD_PROVIDER:-aws} 隐式默认 case (违反 §0.7 决策 6)。
# 业务方需要 baseline 时直接调 getter：
#   throughput_baseline=$(get_baseline_throughput_kib)   # AWS→128 / GCP→256 / Other→0
# getter 由 config/cloud_provider.sh (CP-0.1) 派发；未 detect 时 fail-fast。
#
# 旧名 AWS_EBS_BASELINE_THROUGHPUT_SIZE_KIB 在 CP-2 阶段由 system_config.sh 统一 alias 派发（如仍有 caller），
# 本 utils 文件不再承担兼容职责，避免双向依赖。
```

**改造点 2：L62-67 calculate_io2_throughput — 按能力而非平台名早返回 (§0.7 决策 6)**
```bash
# === 改前 ===
calculate_io2_throughput() {
    local iops=$1
    local calculated_throughput=$(awk "BEGIN {printf \"%.2f\", $iops * $IO2_THROUGHPUT_RATIO}")
    local actual_throughput=$(awk "BEGIN {printf \"%.2f\", ($calculated_throughput > $IO2_MAX_THROUGHPUT) ? $IO2_MAX_THROUGHPUT : $calculated_throughput}")
    echo "$actual_throughput"
}

# === 改后 ===
calculate_io2_throughput() {
    # E1+ 方案：判定改用「平台能力」而非「平台名」。
    # 不写 [[ $CLOUD_PROVIDER == gcp ]]，而是问 getter 当前平台是否支持 io2。
    # 好处：未来加 Azure/OCI/裸金属无需改本 if，只需 cloud_provider.sh 派发 get_disk_type_options。
    local disk_types
    disk_types=" $(get_disk_type_options) "    # 首尾空格用于精确匹配 ' io2 '
    if [[ ! "$disk_types" =~ " io2 " ]]; then
        # 当前平台不支持 io2 (GCP 用 pd-extreme/hyperdisk-extreme；Other 平台空集)
        # 返回 0 告知 caller (user_config.sh:L87/L101) 跳过自动计算
        echo "0"
        return 0
    fi
    local iops=$1
    local calculated_throughput=$(awk "BEGIN {printf \"%.2f\", $iops * $IO2_THROUGHPUT_RATIO}")
    local actual_throughput=$(awk "BEGIN {printf \"%.2f\", ($calculated_throughput > $IO2_MAX_THROUGHPUT) ? $IO2_MAX_THROUGHPUT : $calculated_throughput}")
    echo "$actual_throughput"
}
```

**改造点 3：L139-145 7 个 export 函数加中立 alias**
```bash
# === 改前 ===
export -f convert_to_aws_standard_iops
export -f convert_to_aws_standard_throughput
export -f calculate_io2_throughput
export -f recommend_ebs_type
export -f calculate_weighted_avg_io_size
export -f analyze_instance_store_performance
export -f is_accounts_configured

# === 改后 (双写 alias，保留 1 Round 过渡) ===
# 函数体保留原名不变，新增 wrapper alias
convert_to_standard_iops()       { convert_to_aws_standard_iops "$@"; }
convert_to_standard_throughput() { convert_to_aws_standard_throughput "$@"; }
recommend_disk_type()            { recommend_ebs_type "$@"; }            # 死代码，但 alias 一致性
analyze_local_ssd_performance()  { analyze_instance_store_performance "$@"; }  # 死代码

export -f convert_to_aws_standard_iops convert_to_standard_iops
export -f convert_to_aws_standard_throughput convert_to_standard_throughput
export -f calculate_io2_throughput          # 名字已中立无需 alias
export -f recommend_ebs_type recommend_disk_type
export -f calculate_weighted_avg_io_size    # 名字已中立
export -f analyze_instance_store_performance analyze_local_ssd_performance
export -f is_accounts_configured            # 名字已中立 (ACCOUNTS_* env 也中立)
```

**改造点 4：L25/L31/L83 AWS 文档 URL 注入**
```bash
# === 改前 (L24-25) ===
# Description: AWS EBS counts IOPS by request count, no conversion needed
# Reference: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-io-characteristics.html

# === 改后 ===
# Description: Cloud disk standard IOPS - AWS EBS counts by request, GCP PD by request too
# Reference: ${DISK_DOC_URL:-https://docs.aws.amazon.com/ebs/latest/userguide/ebs-io-characteristics.html}

# DISK_DOC_URL 由 config/system_config.sh 按 $CLOUD_PROVIDER 派发 (CP-2 阶段实施)
```

#### CP-1.1.C 重命名过渡策略 (symlink 1 Round)

```bash
# Round N: 同时存在新旧文件名 (symlink 方式)
mv utils/ebs_converter.sh utils/disk_converter.sh
ln -s disk_converter.sh utils/ebs_converter.sh   # 兼容期 symlink

# Round N+1 (CP-6 阶段)：grep 全仓确认无任何 source utils/ebs_converter.sh 后删除 symlink
# 删除前验证：
grep -rn "ebs_converter.sh" --include="*.sh" --include="*.py" /usr/local/google/home/lelandgong/blockchain-node-benchmark/ | grep -v analysis-notes
# 预期：0 命中 (或仅文档)
```

#### CP-1.1.D 下游 source 调用点清单 (7 处 caller)

实跑 `grep -rn ebs_converter.sh --include='*.sh' --include='*.py' | grep -v analysis-notes` 结果：

| # | 调用点 | 行号 | 类型 | 联动改动 |
|---|---|---|---|---|
| 1 | `tools/ebs_bottleneck_detector.sh` | L16 | source | CP-4.2 改 `disk_bottleneck_detector.sh` 时同步 source 路径 |
| 2 | `monitoring/bottleneck_detector.sh` | L26 | source | CP-3.3 同步改 source 路径 |
| 3 | `monitoring/iostat_collector.sh` | L14 | source + 调用 convert_to_aws_standard_* 3 次 | CP-3.5 同步：(a) source 路径 (b) 函数调用改新 alias 名 |
| 4 | `monitoring/unified_monitor.sh` | L21 | source | CP-3.1 同步 source 路径 |
| 5 | `blockchain_node_benchmark.sh` | L330-331 | `[[ -f ... ]]` 探测 + 注释 | CP-6 阶段同步路径 |
| 6 | `config/user_config.sh` | L72-77 | `[[ -f ... ]]` + source + 错误信息 | CP-2.2 同步 (含 L76 echo 错误信息字面 `ebs_converter.sh`) |
| 7 | `utils/ebs_converter.sh` 自引用 | L151 | usage echo 字面 | 本文件内 EC-12 |

**关键风险**：调用点 6 (user_config.sh) 是**懒加载条件 source** (仅 io2 时 source)，GCP 路径如果 DATA_VOL_TYPE=pd-extreme，条件可能不进入 → 需在 CP-2.2 扩 if 条件。

#### CP-1.1.E 4 模式验证命令 (E1+ getter-based)

```bash
# 前提：source config/cloud_provider.sh 后 getter 已派发
# 验证 1：AWS 默认路径 (回归)
CLOUD_PROVIDER=aws bash -c '
    source config/cloud_provider.sh
    source utils/disk_converter.sh
    echo "baseline=$(get_baseline_throughput_kib)"       # → 128
    echo "disk_opts=$(get_disk_type_options)"            # → gp3 io2 instance-store
    echo "io2_calc=$(calculate_io2_throughput 10000)"    # → 2560.00 (含 io2，走计算)
    echo "new_alias=$(type -t convert_to_standard_iops)" # → function
'

# 验证 2：GCP 路径
CLOUD_PROVIDER=gcp bash -c '
    source config/cloud_provider.sh
    source utils/disk_converter.sh
    echo "baseline=$(get_baseline_throughput_kib)"       # → 256
    echo "disk_opts=$(get_disk_type_options)"            # → pd-balanced pd-ssd pd-extreme hyperdisk-extreme local-ssd (不含 io2)
    echo "io2_skip=$(calculate_io2_throughput 10000)"    # → 0 (能力判定早返回)
'

# 验证 3：OTHER fallback (中立 — 不预设默认值)
CLOUD_PROVIDER=other bash -c '
    source config/cloud_provider.sh
    source utils/disk_converter.sh
    echo "baseline=$(get_baseline_throughput_kib)"       # → 0 (调用方需判 0 处理)
    echo "disk_opts=$(get_disk_type_options)"            # → "" (空集)
    echo "io2_skip=$(calculate_io2_throughput 10000)"    # → 0 (空集自然不含 io2，早返回)
'

# 验证 4：未 detect CLOUD_PROVIDER 时 fail-fast (§0.7 决策 6)
unset CLOUD_PROVIDER
bash -c '
    source config/cloud_provider.sh   # 预期：检测失败 → exit 1
    echo "should not reach"
' 2>&1 | grep -q "CLOUD_PROVIDER" && echo "✓ fail-fast 生效"

# 验证 5：alias 双写后所有 caller 仍跑通 (AWS 模式回归)
CLOUD_PROVIDER=aws bash monitoring/iostat_collector.sh --help 2>&1 | head -5
# 预期：不报 "function not found" 错误
```

#### CP-1.1.F E1+ 平台对等性强化 (§0.7 决策 6 落实)

本次 CP-1.1 改造严格遵循 §0.7 决策 6，对 disk_converter.sh 做了 3 项平台对等性强化：

1. **删除 `${CLOUD_PROVIDER:-aws}` 隐式默认**：原 case 块（throughput baseline）全部移除；本 utils 不再预定义 `CLOUD_THROUGHPUT_BASELINE_KIB` 变量，业务方按需调 `$(get_baseline_throughput_kib)` / `$(get_disk_type_options)` 等 getter。变量预定义违反 §0.7 决策 6 因为 `${CLOUD_PROVIDER:-aws}` 会让 Mac/Other 平台静默走 AWS 默认，掩盖配置错误。

2. **判定改用「能力」而非「平台名」**：`calculate_io2_throughput` 不再写 `if [[ $CLOUD_PROVIDER == gcp ]]`，改写 `if [[ ! " $(get_disk_type_options) " =~ " io2 " ]]`。语义上更准确（"当前平台不支持 io2" 而非 "当前是 GCP"），扩展性上未来加 Azure/OCI/裸金属无需改本 if，只需 `cloud_provider.sh` 派发对应 `get_disk_type_options` 列表。

3. **fail-fast 链路**：未 detect `CLOUD_PROVIDER` 时，`source config/cloud_provider.sh` 自动报错退出（CP-0.1 abstraction layer 保证）；业务方调 getter 时已能保证 `CLOUD_PROVIDER` ∈ {aws, gcp, other} 三态确定，无须重复防御。

**对等性验证场景**：
- AWS EC2：`get_baseline_throughput_kib` → 128，`get_disk_type_options` 含 `io2` → 走 io2 计算分支
- GCP GCE：`get_baseline_throughput_kib` → 256，`get_disk_type_options` 不含 `io2` → 早返回 0
- Mac/Other：`get_baseline_throughput_kib` → 0，`get_disk_type_options` → `""` → 早返回 0 (中立 fallback，无 AWS 偏置)

---

### CP-1.2 utils/unified_logger.sh（**实际豁免**）

**重要发现 (实跑)**：
```bash
$ grep -cE '\b(EBS|ENA|AWS|aws|ebs|ena)\b' utils/unified_logger.sh
0
# 注：必须用 word boundary \b，否则 "filename"/"basename" 中的 "ena"/"ame" 子串会假阳性
```

**结论**：utils/unified_logger.sh **402 行无任何 AWS/EBS/ENA 字面 token**（裸 grep 6 命中全部是 "basename"/"filename" 子串误报，加 `\b` 后归零）。文件设计已经是 platform-agnostic 的纯日志框架 (LOG_LEVEL_*、COMPONENT_LOG_FILES、init_logger、log_info/warn/error/debug/fatal)。

**改造动作**：**无代码改动**。仅在 file-notes 标注 "exempt from GCP migration"。

**验证 (确认无回归)**：
```bash
bash -c '
    source utils/unified_logger.sh
    init_logger "test_component" 1 "/tmp/cp1_2_verify.log"
    log_info "Logger smoke test in CP-1.2 verification"
    log_warn "warn level test"
    log_error "error level test"
'
# 预期 stdout：
#   Logger initialized for component: test_component (level: INFO)
#   [<timestamp>] [INFO] [test_component] Logger smoke test...
#   [<timestamp>] [WARN] [test_component] warn level test
#   [<timestamp>] [ERROR] [test_component] error level test
```

**派生 unified_logger.py (365 行) 同结论**：裸 grep 4 命中全部是 `filename` 中的 "ena" 子串（L156/179/181/183），加 word-boundary `\b` 后命中数为 0，同样豁免。

---

### CP-1.3 utils/error_handler.sh（**实际豁免**）

**重要发现 (实跑)**：
```bash
$ grep -cE '\b(EBS|ENA|AWS|aws|ebs|ena)\b' utils/error_handler.sh
0
# 裸 grep 命中 6 行 (L44/68/78/86/144/193) 全部是 "basename" 中的 "ame" 子串
# 加 word boundary 后归零
```

**结论**：utils/error_handler.sh **206 行无任何 AWS/EBS/ENA 字面 token**。设计为通用 error trap / log_script_start / handle_framework_error 框架，零 cloud-vendor 耦合。

**改造动作**：**无代码改动**。

**验证**：
```bash
bash -c '
    source utils/error_handler.sh
    setup_error_handling "test_script" "CP-1.3 smoke test"
    log_script_start "test_script"
    echo "✅ error_handler.sh sources cleanly with zero AWS dependency"
'
```

---

### CP-1.4 utils/ena_field_accessor.py → utils/nic_field_accessor.py

**目标**：把 AWS ENA 5 字段访问器扩展到支持 GCP gVNIC (无 allowance 概念)，保留 AWS 行为零回归。

**来源依据**：file-notes/ena_field_accessor.py.md + 业务源码 utils/ena_field_accessor.py 166 行实读。

#### CP-1.4.A 文件改造点

| # | 行号 | 改造点 | 等级 |
|---|---|---|---|
| 1 | 文件名 | `ena_field_accessor.py` → `nic_field_accessor.py` + 1 Round symlink | P2 |
| 2 | L7 | `class ENAFieldAccessor` → `class NICFieldAccessor` + 加 `ENAFieldAccessor = NICFieldAccessor` 末尾 alias | P2 |
| 3 | L11-54 | FIELD_CONFIG **6 字段**保留 (AWS ENA 专属：bw_in/bw_out/pps/conntrack_exceeded/linklocal_exceeded/conntrack_available — 注意第 6 个是 gauge 不是 counter) + 加 GCP 路径返回 None | P1 |
| 4 | L60/L64/L78 | env 变量 `ENA_ALLOWANCE_FIELDS_STR` / `ENA_ALLOWANCE_FIELDS` / `ENA_MONITOR_ENABLED` 加 `NIC_*` alias 读取 | P2 |
| 5 | L74-80 | print 输出 "ENA field configuration" 文本中立化 | P3 |
| 6 | L160-166 | `get_unified_network_thresholds` 加 GCP 分支 (gVNIC 无 allowance threshold) | P1 |

#### CP-1.4.B class 重命名 + alias 完整代码

```python
# === 改前 (L7) ===
class ENAFieldAccessor:
    """ENA Field Unified Access Interface - Based on system_config.sh configuration, fully configuration-driven"""

# === 改后 (utils/nic_field_accessor.py) ===
import os
from typing import Optional

class NICFieldAccessor:
    """NIC Field Unified Access Interface (AWS ENA / GCP gVNIC) - configuration-driven"""

    # FIELD_CONFIG 保留原 5 字段定义不变 (AWS ENA 专属)
    FIELD_CONFIG = {  # ... 原 11-54 行内容
    }

    @classmethod
    def get_configured_nic_fields(cls):  # 新名
        """Get NIC field configuration - reads NIC_* env first, falls back to ENA_*"""
        # 双写读取：新名优先
        fields_str = (os.getenv('NIC_ALLOWANCE_FIELDS_STR', '')
                      or os.getenv('NIC_ALLOWANCE_FIELDS', '')
                      or os.getenv('ENA_ALLOWANCE_FIELDS_STR', '')
                      or os.getenv('ENA_ALLOWANCE_FIELDS', ''))
        if fields_str:
            fields_str = fields_str.strip('()')
            fields = [f.strip('"\'') for f in fields_str.split()]
            if fields and fields[0]:
                return fields
        # GCP 兜底：gVNIC 无 allowance 概念，返回空列表 (callers 应判空跳过)
        if os.getenv('CLOUD_PROVIDER', 'aws').lower() == 'gcp':
            return []
        # AWS fallback：standard ENA field list
        return list(cls.FIELD_CONFIG.keys())

    # ABI 兼容 alias 函数
    get_configured_ena_fields = get_configured_nic_fields

# 文件末尾：模块级 class alias (旧 import path 仍工作)
ENAFieldAccessor = NICFieldAccessor
```

#### CP-1.4.C 5 个 allowance 字段的 GCP None 兜底

```python
# 改造 analyze_ena_field (L96-156) → analyze_nic_field
@classmethod
def analyze_nic_field(cls, df, field_name):
    """Analyze single NIC field - AWS ENA returns dict; GCP gVNIC returns None"""
    # GCP gVNIC 路径：5 个 allowance 字段在 GCP 不存在，直接返回 None
    GCP_NONE_FIELDS = {
        'bw_in_allowance_exceeded',
        'bw_out_allowance_exceeded',
        'pps_allowance_exceeded',
        'conntrack_allowance_exceeded',
        'linklocal_allowance_exceeded',
        # 注意 conntrack_allowance_available 是 gauge 不是 exceeded counter
        # 也在 GCP 不存在，加入 None 集合 (实测 file-notes 共 6 字段)
        'conntrack_allowance_available',
    }
    if os.getenv('CLOUD_PROVIDER', 'aws').lower() == 'gcp':
        if field_name in GCP_NONE_FIELDS:
            return None   # 显式兜底，不抛异常
        # GCP 其他字段 (如 gvnic_* 自定义) 走默认路径

    # === AWS 路径 (原逻辑保留) ===
    try:
        if field_name not in df.columns:
            return None
        field_data = df[field_name].dropna()
        if len(field_data) == 0:
            return None
        # ... 原 analyze_ena_field 的剩余逻辑 (L114-152)
        ...

# ABI alias
analyze_ena_field = analyze_nic_field
```

#### CP-1.4.D pytest 验证样例

```python
# tests/test_cp1_4_nic_field_accessor.py
import os
import pandas as pd
import pytest
from utils.nic_field_accessor import NICFieldAccessor, ENAFieldAccessor

def test_aws_path_returns_dict(monkeypatch):
    """AWS 路径：5 allowance 字段返回完整 dict"""
    monkeypatch.setenv('CLOUD_PROVIDER', 'aws')
    df = pd.DataFrame({
        'bw_in_allowance_exceeded': [0, 5, 10],
        'pps_allowance_exceeded': [0, 0, 0],
    })
    res = NICFieldAccessor.analyze_nic_field(df, 'bw_in_allowance_exceeded')
    assert res is not None
    assert res['type'] == 'counter'
    assert res['total_count'] == 15
    assert res['events_detected'] is True

def test_gcp_path_returns_none_for_allowance(monkeypatch):
    """GCP 路径：6 个 allowance 字段全部返回 None"""
    monkeypatch.setenv('CLOUD_PROVIDER', 'gcp')
    df = pd.DataFrame({'bw_in_allowance_exceeded': [1, 2, 3]})
    for field in ['bw_in_allowance_exceeded', 'bw_out_allowance_exceeded',
                  'pps_allowance_exceeded', 'conntrack_allowance_exceeded',
                  'linklocal_allowance_exceeded', 'conntrack_allowance_available']:
        assert NICFieldAccessor.analyze_nic_field(df, field) is None

def test_class_alias_compat():
    """旧 class 名 ENAFieldAccessor 仍指向新 class (ABI 兼容)"""
    assert ENAFieldAccessor is NICFieldAccessor

def test_env_double_read(monkeypatch):
    """env 双写：NIC_* 优先，回落 ENA_*"""
    monkeypatch.setenv('CLOUD_PROVIDER', 'aws')
    monkeypatch.setenv('ENA_ALLOWANCE_FIELDS_STR', 'foo bar baz')
    monkeypatch.delenv('NIC_ALLOWANCE_FIELDS_STR', raising=False)
    assert NICFieldAccessor.get_configured_nic_fields() == ['foo', 'bar', 'baz']
    # 新名优先
    monkeypatch.setenv('NIC_ALLOWANCE_FIELDS_STR', 'aaa bbb')
    assert NICFieldAccessor.get_configured_nic_fields() == ['aaa', 'bbb']

def test_gcp_empty_when_no_env(monkeypatch):
    """GCP 无 env 时返回 [] (而非 AWS fallback 5 字段)"""
    monkeypatch.setenv('CLOUD_PROVIDER', 'gcp')
    for var in ['NIC_ALLOWANCE_FIELDS_STR', 'NIC_ALLOWANCE_FIELDS',
                'ENA_ALLOWANCE_FIELDS_STR', 'ENA_ALLOWANCE_FIELDS']:
        monkeypatch.delenv(var, raising=False)
    assert NICFieldAccessor.get_configured_nic_fields() == []
```

---

### CP-1.5 utils/__init__.py（豁免）

**文件状态**：`wc -l` ≈ 1 LOC (空文件或纯 package marker)。

**改造动作**：无。

**说明**：utils 是纯 namespace package，无需暴露 public API。CP-1.4 的 class alias `ENAFieldAccessor = NICFieldAccessor` 写在 nic_field_accessor.py 文件末尾即可，无需 re-export。

---

### CP-1.6 utils/csv_data_processor.py（加 normalize 钩子 + 反向兼容）

**目标**：在 `load_csv_data` 后加 platform-aware 字段归一化钩子；旧 caller 不传 normalize 参数也能跑通。

**来源依据**：业务源码 257 行实读 + CP-0.2 `utils/field_normalizer.py` 设计。

#### CP-1.6.A 改造点

| # | 行号 | 改造点 | 等级 |
|---|---|---|---|
| 1 | L9 | 新增 `from utils.field_normalizer import normalize_df` (try/except 包) | P1 |
| 2 | L23-88 | `load_csv_data` 签名加 `normalize: bool = True` 参数 | P1 |
| 3 | L62 后 | `pd.read_csv` 之后插入 `if normalize: self.df = normalize_df(self.df)` | P1 |
| 4 | L234-247 | 顶层函数 `load_csv_with_processor` 同步加 normalize 参数透传 | P1 |
| 5 | 文件头 docstring | 注明 "default normalize=True 自动归一化双写字段" | P3 |

#### CP-1.6.B 完整改造代码 (反向兼容)

```python
# === 改前 (L1-13) ===
#!/usr/bin/env python3
"""
Simplified CSV Data Processor
Removed field mapping functionality, focused on core data processing
"""

import pandas as pd
import numpy as np
from utils.unified_logger import get_logger
from typing import List, Dict, Optional, Any
import os

logger = get_logger(__name__)

# === 改后 ===
#!/usr/bin/env python3
"""
Simplified CSV Data Processor
Default behavior: auto-normalize legacy AWS field names to neutral names via field_normalizer.
Pass normalize=False to opt out (e.g. for unit tests that need raw column names).
"""

import pandas as pd
import numpy as np
from utils.unified_logger import get_logger
from typing import List, Dict, Optional, Any
import os

# 反向兼容：field_normalizer 不存在 (CP-0 未完成) 时 fallback to identity
try:
    from utils.field_normalizer import normalize_df as _normalize_df
except ImportError:
    def _normalize_df(df):
        return df  # passthrough

logger = get_logger(__name__)
```

```python
# === 改前 (L23-32 load_csv_data 签名 + L62) ===
def load_csv_data(self, csv_file: str) -> bool:
    """..."""
    try:
        if not os.path.exists(csv_file):
            ...
        # ... 各种校验 ...
        # Attempt to read CSV
        self.df = pd.read_csv(csv_file)
        self.csv_file = csv_file

# === 改后 ===
def load_csv_data(self, csv_file: str, normalize: bool = True) -> bool:
    """
    Enhanced CSV data loading with complete validation.

    Args:
        csv_file: CSV file path
        normalize: if True (default), apply field_normalizer.normalize_df()
                   to auto-rename legacy AWS column names (data_aws_standard_iops →
                   data_disk_standard_iops, etc.) Set False for raw-column tests.

    Returns:
        bool: Whether loading was successful
    """
    try:
        if not os.path.exists(csv_file):
            ...
        # ... 各种校验 ...
        # Attempt to read CSV
        self.df = pd.read_csv(csv_file)
        # 读时归一化钩子 (CP-1.6 新增)
        if normalize:
            try:
                self.df = _normalize_df(self.df)
            except Exception as e:
                logger.warning(f"⚠️ field_normalizer failed, passthrough raw columns: {e}")
        self.csv_file = csv_file
```

```python
# === 改前 (L234-247 顶层便利函数) ===
def load_csv_with_processor(csv_file: str) -> CSVDataProcessor:
    """..."""
    processor = CSVDataProcessor()
    if processor.load_csv_data(csv_file):
        processor.clean_data()
    return processor

# === 改后 ===
def load_csv_with_processor(csv_file: str, normalize: bool = True) -> CSVDataProcessor:
    """
    Convenience function. Pass normalize=False to bypass field_normalizer.
    """
    processor = CSVDataProcessor()
    if processor.load_csv_data(csv_file, normalize=normalize):
        processor.clean_data()
    return processor
```

#### CP-1.6.C 3 个 pytest 验证 (反向兼容 + 双写 + mixed)

```python
# tests/test_cp1_6_csv_normalize.py
import pandas as pd
import pytest
from utils.csv_data_processor import CSVDataProcessor, load_csv_with_processor

def test_legacy_csv_auto_normalized(tmp_path):
    """读旧 CSV (含 data_aws_standard_iops) 自动归一化为 data_disk_standard_iops"""
    csv = tmp_path / "legacy.csv"
    csv.write_text(
        "timestamp,data_aws_standard_iops,data_aws_standard_throughput_mibs\n"
        "2026-01-01T00:00:00,1000,500\n"
        "2026-01-01T00:00:05,1500,600\n"
    )
    proc = CSVDataProcessor()
    assert proc.load_csv_data(str(csv)) is True
    # 归一化后旧名消失，新名出现
    assert 'data_aws_standard_iops' not in proc.df.columns
    assert 'data_disk_standard_iops' in proc.df.columns
    assert proc.df['data_disk_standard_iops'].iloc[0] == 1000

def test_new_csv_passthrough(tmp_path):
    """读新 CSV (已是 data_disk_*) 不变 (normalize_df 无副作用)"""
    csv = tmp_path / "new.csv"
    csv.write_text(
        "timestamp,data_disk_standard_iops\n"
        "2026-01-01T00:00:00,1000\n"
    )
    proc = CSVDataProcessor()
    assert proc.load_csv_data(str(csv)) is True
    assert 'data_disk_standard_iops' in proc.df.columns
    assert len(proc.df.columns) == 2

def test_mixed_schema_both_legacy_and_new(tmp_path):
    """混合 schema：旧字段 rename，新字段保留，无 collision"""
    csv = tmp_path / "mixed.csv"
    csv.write_text(
        "timestamp,data_aws_standard_iops,accounts_disk_standard_iops\n"
        "2026-01-01T00:00:00,1000,2000\n"
    )
    proc = CSVDataProcessor()
    assert proc.load_csv_data(str(csv)) is True
    # 旧 data_aws_* 归一化
    assert 'data_disk_standard_iops' in proc.df.columns
    # 新 accounts_disk_* 原样保留
    assert 'accounts_disk_standard_iops' in proc.df.columns
    assert 'data_aws_standard_iops' not in proc.df.columns

def test_opt_out_normalize_kwarg(tmp_path):
    """显式 normalize=False 时旧字段名保留 (单元测试用例需要)"""
    csv = tmp_path / "legacy.csv"
    csv.write_text("timestamp,data_aws_standard_iops\n2026-01-01,500\n")
    proc = CSVDataProcessor()
    assert proc.load_csv_data(str(csv), normalize=False) is True
    assert 'data_aws_standard_iops' in proc.df.columns

def test_field_normalizer_missing_graceful_fallback(monkeypatch, tmp_path):
    """field_normalizer 未安装时 fallback 到 identity，不破坏 load"""
    # 模拟 import 失败 (CP-0 未完成场景)
    import utils.csv_data_processor as mod
    orig = mod._normalize_df
    mod._normalize_df = lambda df: (_ for _ in ()).throw(RuntimeError("simulated"))
    csv = tmp_path / "x.csv"
    csv.write_text("a,b\n1,2\n")
    try:
        proc = CSVDataProcessor()
        assert proc.load_csv_data(str(csv)) is True  # 仍成功
        assert list(proc.df.columns) == ['a', 'b']    # 原列名保留
    finally:
        mod._normalize_df = orig
```

---

### CP-1 完成 Gate 检查清单

| Gate | 检查项 | 命令 |
|---|---|---|
| G-1 | utils/ 业务代码 commit hash 仍是 e843571 | `cd utils && git log -1 --format=%H .` |
| G-2 | utils/disk_converter.sh 4 种模式验证全过 (CP-1.1.E) | 上述 4 个 bash 块 |
| G-3 | utils/unified_logger.sh 烟测通过 (CP-1.2) | 上述 source + log_info 块 |
| G-4 | utils/nic_field_accessor.py pytest 5 用例全过 | `pytest tests/test_cp1_4_nic_field_accessor.py -v` |
| G-5 | utils/csv_data_processor.py pytest 5 用例全过 | `pytest tests/test_cp1_6_csv_normalize.py -v` |
| G-6 | 所有 7 处 ebs_converter.sh caller 在 AWS 模式下零回归 | 跑 CP-3.5 iostat_collector smoke test |
| G-7 | grep AWS_EBS_BASELINE 全仓仍能命中 alias (双写有效) | `grep -rn AWS_EBS_BASELINE utils/ config/` |

---

## CP-2：config/ 层（4 改）

> **依赖**：CP-0.1（config/cloud_provider.sh 已交付 — 抽象层 + provider getter）、CP-1.1（utils/disk_converter.sh 已交付）。
> **目标**(E1+ 重新表述)：把 `config/` 层从"AWS-only 静态枚举 + ${CLOUD_PROVIDER:-aws} 急切求值"改成"**所有 platform-aware 取值统一走 `config/cloud_provider.sh` getter 懒求值**",`config_loader.sh:detect_deployment_platform()` 仍是项目根节点(产出 `CLOUD_PROVIDER` / `DEPLOYMENT_PLATFORM` 终值, 并触发 `filter_platform_processes` 聚合)。
> **基线 commit**：`e843571`(业务代码完全未动,本节所有"改前"片段都可在 commit `e843571` 的 `config/*.sh` 中按行号定位)。
> **alias 策略**:`ENA_*`/`EBS_*` 旧名保留 1 个 Round, 统一 CP-6 删除; `AWS_METADATA_ENDPOINT` / `METADATA_ENDPOINT` / `CLOUD_IO_BASELINE_KIB` / `METADATA_API_PATH` 等 **E1+ 后不再以变量形式 export**, 业务方统一调 getter。
>
> ✅ **§13.2 source 顺序冲突 → E1+ 结构性消除** (替代 V1.0 re-evaluate hook 工单):
> - V1.0 设计妥协: system_config.sh 在 detect_deployment_platform 之前 source, `case "${CLOUD_PROVIDER:-aws}"` 急切求值落 aws 默认分支 → 需 hook 重 source。
> - **E1+ 结构性解决**: system_config.sh 不再静态定义 `METADATA_ENDPOINT` / `METADATA_API_PATH` / `CLOUD_IO_BASELINE_KIB` / `MONITORING_PROCESS_NAMES` (硬枚举), 业务方在使用点调 `$(get_metadata_endpoint)` 等 **懒求值 getter** — 此时 `CLOUD_PROVIDER` 已 detect 完毕, 永远返回正确值。**re-evaluate hook 不再需要, 工单关闭**。
>
> source 顺序约束(E1+ 仍要求):
> 1. **config/cloud_provider.sh** 必须最先 source(由 `config_loader.sh:L1-10` 全局兜底), 提供 15 个 getter。
> 2. **system_config.sh** / **user_config.sh** 按原顺序 source(此时只读 getter, 不依赖 CLOUD_PROVIDER 终值)。
> 3. **detect_deployment_platform()** 确定 CLOUD_PROVIDER 终值 + 触发 `filter_platform_processes`。

### CP-2.1 config/system_config.sh

文件全长 116 行(含 3 个函数:`get_unified_timestamp`/`get_unified_epoch`/`validate_overhead_csv_header`)。共 6 个改造点。

| # | 改造点 | file:line | 来源 | 等级 |
|---|---|---|---|---|
| 1 | DEPLOYMENT_PLATFORM 注释/枚举加 `gcp` | `system_config.sh:11-12` | TRACKER 11.1 | **P0** |
| 2 | `AWS_METADATA_ENDPOINT` → `METADATA_ENDPOINT` + case 分发 | `system_config.sh:56-57` | TRACKER 11.3 | **P0** |
| 3 | `AWS_METADATA_API_VERSION` → `METADATA_API_PATH` + case 分发 | `system_config.sh:59` | TRACKER 11.4 | P1 |
| 4 | `AWS_EBS_BASELINE_IO_SIZE_KIB` → `CLOUD_IO_BASELINE_KIB`(联动 CP-1.1) | `system_config.sh:52-54` | TRACKER 11.2 | P1 |
| 5 | `MONITORING_PROCESS_NAMES` 加 platform 派发函数 | `system_config.sh:62-75` | TRACKER 11.5 | P2 |
| 6 | 5 个 `AWS_*` 变量保留中立 alias | `system_config.sh:107-115` | TRACKER 11.6 | P2 |

#### CP-2.1.1 DEPLOYMENT_PLATFORM 枚举扩展 (P0)

改前 (`system_config.sh:10-12`):
```bash
# ----- Deployment Platform Detection Configuration -----
# Deployment platform type (auto: auto-detect, aws: AWS environment, other: other environments)
DEPLOYMENT_PLATFORM=${DEPLOYMENT_PLATFORM:-"auto"}
```

改后:
```bash
# ----- Deployment Platform Detection Configuration -----
# Deployment platform type:
#   auto  - auto-detect via config/cloud_provider.sh (preferred)
#   aws   - force AWS (IMDSv2 + EBS + ENA)
#   gcp   - force GCP  (metadata.google.internal + PD + gVNIC)
#   other - non-cloud / IDC fallback
# NOTE: when "auto", config_loader.sh:L102-128 will source config/cloud_provider.sh
#       and overwrite this value before any downstream consumer reads it.
DEPLOYMENT_PLATFORM=${DEPLOYMENT_PLATFORM:-"auto"}
```

验证:
```bash
# 1) 默认 auto 不变
bash -c 'source config/system_config.sh && echo "$DEPLOYMENT_PLATFORM"'  # → auto
# 2) env override 生效
DEPLOYMENT_PLATFORM=gcp bash -c 'source config/system_config.sh && echo "$DEPLOYMENT_PLATFORM"'  # → gcp
```

#### CP-2.1.2 METADATA_ENDPOINT 中立化 (P0) — **E1+ 改造: case 块整体删除**

改前 (`system_config.sh:56-58`):
```bash
# AWS metadata service endpoint configuration
AWS_METADATA_ENDPOINT="http://169.254.169.254"                # AWS instance metadata endpoint
AWS_METADATA_TOKEN_TTL=21600                                  # Metadata token TTL (6 hours)
```

改后(**E1+ 关键决策 §0.5 + §0.6**: system_config.sh 不再定义 `METADATA_ENDPOINT` / `METADATA_HEADER` 变量,业务方在使用点调 getter — 懒求值天然解决 §13.2 source 顺序冲突):
```bash
# ----- Cloud Metadata Endpoint -----
# E1+ 改造: METADATA_ENDPOINT / METADATA_HEADER 不再在 system_config.sh 静态定义。
# 业务方使用时调 $(get_metadata_endpoint) / $(get_metadata_header) — 懒求值, 此时
# CLOUD_PROVIDER 已被 config/cloud_provider.sh detect 完毕 (§0.5 决策 5)。
# §13.2 source 顺序冲突 → ✅ E1+ absorbed (结构性消除 — 详见 CP-2.3.X 平台对等性审查)
# §13.5 metadata header 缺失 → ✅ E1+ absorbed (统一 curl -H "$(get_metadata_header)" ...)

AWS_METADATA_TOKEN_TTL=21600                                  # AWS-only, GCP ignores (no IMDSv2 token concept)
# 死代码标记: AWS_METADATA_TOKEN_TTL 在 commit e843571 全仓 grep 实证 0 程序化消费 (file-notes/system_config.sh.md
# §8.2 #8); 当前 config_loader.sh:L106 走 IMDSv1 路径不读 token。本项目阶段保留(不删), 等 CP-6 整体清理 AWS_* alias
# 时与本变量一起评估: 若 CP-3/4 任何 worker 需升级到 IMDSv2, 此 TTL 才有真实下游。
```

业务调用方示例(任何时刻安全 — 不受 source 顺序影响):
```bash
# 改前(急切求值, 受 source 顺序影响):
curl -s "${AWS_METADATA_ENDPOINT}/${AWS_METADATA_API_VERSION}/meta-data/instance-id"

# 改后(懒求值 getter + 统一 metadata header — §13.5 一并消除):
curl -s -H "$(get_metadata_header)" "$(get_metadata_endpoint)/$(get_metadata_api_path)/meta-data/instance-id"
```

验证(契约 — getter 在 AWS / GCP 模式下都返回正确值, 不依赖 system_config.sh export 任何 METADATA_* 变量):
```bash
CLOUD_PROVIDER=gcp bash -c 'source config/cloud_provider.sh && echo "$(get_metadata_endpoint)|$(get_metadata_header)"'
# → http://metadata.google.internal|Metadata-Flavor: Google
CLOUD_PROVIDER=aws bash -c 'source config/cloud_provider.sh && echo "$(get_metadata_endpoint)|$(get_metadata_header)"'
# → http://169.254.169.254|
# 关键: system_config.sh 不再 export METADATA_ENDPOINT — 下面这条必须为空
bash -c 'source config/system_config.sh && echo "${METADATA_ENDPOINT:-<unset>}"'  # → <unset>
```

#### CP-2.1.3 METADATA_API_PATH 中立化 (P1) — **E1+ 改造: case 块整体删除**

改前 (`system_config.sh:59`):
```bash
AWS_METADATA_API_VERSION="latest"                             # API version
```

改后(**E1+**: 不再定义 `METADATA_API_PATH` 变量, 业务方调 `$(get_metadata_api_path)` getter — 与 CP-2.1.2 同一懒求值原则):
```bash
# ----- Cloud Metadata API Path -----
# E1+ 改造: METADATA_API_PATH 不再静态定义。业务方使用时调 $(get_metadata_api_path):
#   AWS  → "latest"
#   GCP  → "computeMetadata/v1"
#   OTHER→ "" (调用方需判空, getter 表 §0.X)
# §13.2 source 顺序冲突 → ✅ E1+ absorbed (懒求值 → 永远在 CLOUD_PROVIDER detect 后才求值)
```

验证(getter 契约):
```bash
CLOUD_PROVIDER=gcp bash -c 'source config/cloud_provider.sh && echo $(get_metadata_api_path)'   # → computeMetadata/v1
CLOUD_PROVIDER=aws bash -c 'source config/cloud_provider.sh && echo $(get_metadata_api_path)'   # → latest
# 关键: system_config.sh 不再 export METADATA_API_PATH
bash -c 'source config/system_config.sh && echo "${METADATA_API_PATH:-<unset>}"'                # → <unset>
```

#### CP-2.1.4 CLOUD_IO_BASELINE_KIB 中立化 (P1, 与 CP-1.1 联动) — **E1+ 改造: case 块整体删除**

改前 (`system_config.sh:51-54`):
```bash
# ----- AWS Related Configuration -----
# AWS EBS baseline configuration
AWS_EBS_BASELINE_IO_SIZE_KIB=16                               # AWS EBS baseline IO size (KiB)
AWS_EBS_BASELINE_THROUGHPUT_SIZE_KIB=128                      # AWS EBS baseline Throughput size (KiB)
```

改后(**E1+**: 不再定义 `CLOUD_IO_BASELINE_KIB` 变量, 业务方调 `$(get_baseline_io_kib)` getter; 通用 throughput 单位 128 KiB 同步走 `$(get_baseline_throughput_kib)`):
```bash
# ----- Cloud Disk Baseline (E1+ getter-driven, see utils/disk_converter.sh CP-1.1) -----
# E1+ 改造: CLOUD_IO_BASELINE_KIB / CLOUD_THROUGHPUT_BASELINE_KIB 不再静态定义。
# 业务方使用时调:
#   $(get_baseline_io_kib)         # AWS=16, GCP=4, OTHER=0
#   $(get_baseline_throughput_kib) # AWS=128, GCP=256, OTHER=0
# §13.2 source 顺序冲突 → ✅ E1+ absorbed
```

业务调用方示例(utils/disk_converter.sh / monitoring 工具):
```bash
# 改前(读 system_config.sh 急切求值的变量):
local io_unit_kib="$CLOUD_IO_BASELINE_KIB"

# 改后(懒求值 getter, source 顺序无关):
local io_unit_kib="$(get_baseline_io_kib)"
```

验证(getter 契约 — 不依赖 system_config.sh 任何 CLOUD_IO_* export):
```bash
CLOUD_PROVIDER=gcp bash -c 'source config/cloud_provider.sh && echo $(get_baseline_io_kib)'  # → 4
CLOUD_PROVIDER=aws bash -c 'source config/cloud_provider.sh && echo $(get_baseline_io_kib)'  # → 16
# 与 utils/disk_converter.sh 一致性(后者也读 getter, 无 source 顺序依赖)
CLOUD_PROVIDER=gcp bash -c 'source config/cloud_provider.sh && source utils/disk_converter.sh && echo $(get_baseline_io_kib)'  # → 4
# 关键: system_config.sh 不再 export CLOUD_IO_BASELINE_KIB
bash -c 'source config/system_config.sh && echo "${CLOUD_IO_BASELINE_KIB:-<unset>}"'  # → <unset>
```

#### CP-2.1.5 MONITORING_PROCESS_NAMES platform 派发 (P2) — **E1+ 改造: case 改 getter**

改前 (`system_config.sh:61-75`):
```bash
# ----- Monitoring Process Configuration -----
# Monitoring process name configuration (for monitoring overhead calculation)
MONITORING_PROCESS_NAMES=(
    "iostat"
    "mpstat"
    "sar"
    "vmstat"
    "netstat"
    "unified_monitor"
    "bottleneck_detector"
    "ena_network_monitor"
    "block_height_monitor"
    "performance_visualizer"
    "report_generator"
)
```

改后(**E1+**: 用 `$(get_nic_monitor_process_name)` getter 派发 nic monitor 进程名, 无 case 块):
```bash
# ----- Monitoring Process Configuration (E1+ getter-driven) -----
# 通用进程(所有平台都跑)
MONITORING_PROCESS_NAMES_COMMON=(
    "iostat" "mpstat" "sar" "vmstat" "netstat"
    "unified_monitor" "bottleneck_detector"
    "block_height_monitor" "performance_visualizer" "report_generator"
)

# 按平台聚合 — 依赖 config/cloud_provider.sh 提供的 get_nic_monitor_process_name getter
# (AWS → "ena_network_monitor", GCP → "gvnic_network_monitor", OTHER → "")
filter_platform_processes() {
    local nic_proc
    nic_proc="$(get_nic_monitor_process_name 2>/dev/null || true)"
    MONITORING_PROCESS_NAMES=( "${MONITORING_PROCESS_NAMES_COMMON[@]}" )
    [[ -n "$nic_proc" ]] && MONITORING_PROCESS_NAMES+=( "$nic_proc" )
    export MONITORING_PROCESS_NAMES
    export MONITORING_PROCESS_NAMES_STR="${MONITORING_PROCESS_NAMES[*]}"
}
# 注意: filter_platform_processes 必须在 config/cloud_provider.sh source 之后调用 —
# 由 config_loader.sh detect_deployment_platform() 末尾统一触发, 不在 system_config.sh 里立即调。
```

验证:
```bash
CLOUD_PROVIDER=gcp bash -c 'source config/cloud_provider.sh && source config/system_config.sh && filter_platform_processes && echo "${MONITORING_PROCESS_NAMES[*]}"' | grep -q gvnic_network_monitor && echo OK
CLOUD_PROVIDER=aws bash -c 'source config/cloud_provider.sh && source config/system_config.sh && filter_platform_processes && echo "${MONITORING_PROCESS_NAMES[*]}"' | grep -q ena_network_monitor && echo OK
# 兜底: other 平台无 nic monitor (getter 返回空 → 不追加)
CLOUD_PROVIDER=other bash -c 'source config/cloud_provider.sh && source config/system_config.sh && filter_platform_processes && echo "${MONITORING_PROCESS_NAMES[*]}"' | grep -vqE '(ena|gvnic)_network_monitor' && echo OK
```

#### CP-2.1.6 5 个 AWS_* 变量加中立 alias (P2) — **E1+ 改造: METADATA_* / CLOUD_IO_BASELINE_KIB export 全删**

改前 (`system_config.sh:107-115`):
```bash
export -f get_unified_timestamp get_unified_epoch
export ENA_ALLOWANCE_FIELDS_STR="${ENA_ALLOWANCE_FIELDS[*]}"
export MONITORING_PROCESS_NAMES_STR="${MONITORING_PROCESS_NAMES[*]}"
export ENA_ALLOWANCE_FIELDS MONITORING_PROCESS_NAMES DEPLOYMENT_PLATFORM
export LOG_LEVEL LOG_FORMAT MAX_LOG_SIZE MAX_LOG_FILES LOG_JSON
export ERROR_RECOVERY_ENABLED ERROR_RECOVERY_DELAY
export ERROR_LOG_SUBDIR PYTHON_ERROR_LOG_SUBDIR TEMP_FILE_PREFIX
export AWS_EBS_BASELINE_IO_SIZE_KIB AWS_EBS_BASELINE_THROUGHPUT_SIZE_KIB AWS_METADATA_ENDPOINT AWS_METADATA_TOKEN_TTL AWS_METADATA_API_VERSION
export TIMESTAMP_FORMAT SILENT_MODE OVERHEAD_CSV_HEADER
```

改后(**E1+**: METADATA_* / CLOUD_IO_BASELINE_KIB / CLOUD_THROUGHPUT_BASELINE_KIB / AWS_EBS_BASELINE_* / AWS_METADATA_ENDPOINT / AWS_METADATA_API_VERSION 不再 export — 由各自 getter 替代; 仅保留 AWS_METADATA_TOKEN_TTL 一个死代码标记 + ENA_ALLOWANCE_FIELDS 在 CP-2.3.4 单源化):
```bash
export -f get_unified_timestamp get_unified_epoch filter_platform_processes
# 字段集合(ENA_ALLOWANCE_FIELDS 由 CP-2.3.4 单源 = $(get_nic_allowance_fields), 这里仅保留双写 alias 供 CP-6 前下游兼容)
export ENA_ALLOWANCE_FIELDS_STR="${ENA_ALLOWANCE_FIELDS[*]}"
export MONITORING_PROCESS_NAMES_STR="${MONITORING_PROCESS_NAMES[*]}"
export ENA_ALLOWANCE_FIELDS MONITORING_PROCESS_NAMES DEPLOYMENT_PLATFORM
export LOG_LEVEL LOG_FORMAT MAX_LOG_SIZE MAX_LOG_FILES LOG_JSON
export ERROR_RECOVERY_ENABLED ERROR_RECOVERY_DELAY
export ERROR_LOG_SUBDIR PYTHON_ERROR_LOG_SUBDIR TEMP_FILE_PREFIX
# E1+ 改造: 以下变量 不再 export — 业务方统一调 getter:
#   AWS_EBS_BASELINE_IO_SIZE_KIB / CLOUD_IO_BASELINE_KIB        → $(get_baseline_io_kib)
#   AWS_EBS_BASELINE_THROUGHPUT_SIZE_KIB / CLOUD_THROUGHPUT_BASELINE_KIB → $(get_baseline_throughput_kib)
#   AWS_METADATA_ENDPOINT / METADATA_ENDPOINT                  → $(get_metadata_endpoint)
#   AWS_METADATA_API_VERSION / METADATA_API_PATH               → $(get_metadata_api_path)
# 仅保留 AWS_METADATA_TOKEN_TTL (死代码标记, CP-6 与本变量一同评估)
export AWS_METADATA_TOKEN_TTL
export TIMESTAMP_FORMAT SILENT_MODE OVERHEAD_CSV_HEADER
```

验证(关键: 旧静态变量 unset, getter 仍可用):
```bash
# 1) 旧 export 已删 (CP-3/4/5 下游不能再依赖)
bash -c 'source config/system_config.sh && echo "${METADATA_ENDPOINT:-<unset>}|${AWS_METADATA_ENDPOINT:-<unset>}|${CLOUD_IO_BASELINE_KIB:-<unset>}"'
# → <unset>|<unset>|<unset>

# 2) getter 仍可用
CLOUD_PROVIDER=aws bash -c 'source config/cloud_provider.sh && echo "$(get_metadata_endpoint)|$(get_baseline_io_kib)"'
# → http://169.254.169.254|16
```

### CP-2.2 config/user_config.sh

文件全长 121 行,1 个函数 `configure_io2_volumes` (L67-109) + L111 顶层调用。共 4 个改造点。

| # | 改造点 | file:line | 来源 | 等级 |
|---|---|---|---|---|
| 1 | `DATA_VOL_TYPE`/`ACCOUNTS_VOL_TYPE` 注释扩展 + L111 case 派发 | `user_config.sh:19,25,111` | TRACKER 12.1 | **P0** |
| 2 | `ENA_MONITOR_ENABLED` → `NIC_MONITOR_ENABLED` + alias | `user_config.sh:34-35,117` | TRACKER 12.2 | P1 |
| 3 | `EBS_MONITOR_RATE` → `DISK_MONITOR_RATE` + alias | `user_config.sh:40,117` | TRACKER 12.3 | P2 |
| 4 | 新增 `configure_gcp_extreme_volumes()` 平行函数 | `user_config.sh:67-109` 之后插入 | TRACKER 12.7 | P1 |

#### CP-2.2.1 VOL_TYPE 枚举扩展 + L111 派发 (P0) — **E1+ 改造: case 改能力判定**

改前 (`user_config.sh:18-28` + `L111`):
```bash
# Data volume configuration
DATA_VOL_TYPE="io2"                    # Options: "gp3" | "io2" | "instance-store"
DATA_VOL_SIZE="2000"
DATA_VOL_MAX_IOPS="30000"
DATA_VOL_MAX_THROUGHPUT="700"

# Accounts volume configuration (optional)
ACCOUNTS_VOL_TYPE="io2"                # Options: "gp3" | "io2" | "instance-store"
...
configure_io2_volumes
```

改后(**E1+**: 合并 `configure_io2_volumes` / `configure_gcp_extreme_volumes` 为统一入口 `configure_disk_volumes`, 内部按 `$(get_default_disk_type)` / `$(get_disk_type_options)` 能力判定分发, 无 case `$CLOUD_PROVIDER` 块 — 平台对等性):
```bash
# Data volume configuration
# Options(由 $(get_disk_type_options) 提供 — 平台对等):
#   AWS : "gp3" | "io2" | "instance-store"
#   GCP : "pd-balanced" | "pd-ssd" | "pd-extreme" | "hyperdisk-extreme" | "local-ssd"
DATA_VOL_TYPE="io2"
DATA_VOL_SIZE="2000"
DATA_VOL_MAX_IOPS="30000"
DATA_VOL_MAX_THROUGHPUT="700"

# Accounts volume configuration (同上枚举)
ACCOUNTS_VOL_TYPE="io2"
...
# ----- Volume Configuration Dispatch (E1+ 能力判定, 无 case $CLOUD_PROVIDER) -----
# 统一入口 configure_disk_volumes 内部按 VOL_TYPE 是否落在 $(get_disk_type_options) 列表
# 来选 io2 path 或 pd-extreme path — 平台对等, AWS / GCP 走同一入口函数。
configure_disk_volumes
```

`configure_disk_volumes()` 内部签名(详见 CP-2.2.4):
```bash
configure_disk_volumes() {
    # 平台对等: 不读 CLOUD_PROVIDER, 仅按 $(get_disk_type_options) 能力判定
    local opts=" $(get_disk_type_options) "
    # AWS-family auto throughput (io2 / gp3 baseline)
    if [[ "$opts" =~ \ io2\  || "$opts" =~ \ gp3\  ]]; then
        configure_io2_volumes
    fi
    # PD-Extreme / Hyperdisk-Extreme auto throughput (GCP-family)
    if [[ "$opts" =~ \ pd-extreme\  || "$opts" =~ \ hyperdisk-extreme\  ]]; then
        configure_gcp_extreme_volumes
    fi
}
```

验证:
```bash
# AWS 行为不变 (io2 path)
CLOUD_PROVIDER=aws DATA_VOL_TYPE=io2 ACCOUNTS_VOL_TYPE=io2 \
  bash -c 'source config/cloud_provider.sh && source config/user_config.sh' 2>&1 \
  | grep -q "io2 auto-calculated" && echo OK

# GCP 行为对等 (pd-extreme path)
CLOUD_PROVIDER=gcp DATA_VOL_TYPE=pd-extreme ACCOUNTS_VOL_TYPE=pd-extreme \
  bash -c 'source config/cloud_provider.sh && source config/user_config.sh' 2>&1 \
  | grep -qE "(pd-extreme|configure_gcp_extreme_volumes)" && echo OK
```

#### CP-2.2.2 ENA_MONITOR_ENABLED → NIC_MONITOR_ENABLED (P1)

改前 (`user_config.sh:34-35` + `L117`):
```bash
# ENA network limitation monitoring configuration
ENA_MONITOR_ENABLED=true
...
export NETWORK_MAX_BANDWIDTH_GBPS ENA_MONITOR_ENABLED MONITOR_INTERVAL EBS_MONITOR_RATE
```

改后:
```bash
# NIC (network interface card) limitation monitoring configuration
# AWS 含义:ENA allowance exceeded counters / GCP 含义:gVNIC ethtool stats(无 allowance 概念)
NIC_MONITOR_ENABLED=true
ENA_MONITOR_ENABLED="$NIC_MONITOR_ENABLED"     # alias (CP-6 drop)
...
export NETWORK_MAX_BANDWIDTH_GBPS NIC_MONITOR_ENABLED ENA_MONITOR_ENABLED MONITOR_INTERVAL DISK_MONITOR_RATE EBS_MONITOR_RATE
```

验证:
```bash
bash -c 'source config/user_config.sh; [[ "$NIC_MONITOR_ENABLED" == "$ENA_MONITOR_ENABLED" ]] && echo "alias OK"'
NIC_MONITOR_ENABLED=false bash -c 'source config/user_config.sh; echo $ENA_MONITOR_ENABLED'  # → false
```

#### CP-2.2.3 EBS_MONITOR_RATE → DISK_MONITOR_RATE (P2)

改前 (`user_config.sh:40` + `L117`):
```bash
EBS_MONITOR_RATE=1              # EBS separate monitoring frequency
```

改后:
```bash
DISK_MONITOR_RATE=1                            # Disk separate monitoring frequency (Hz)
EBS_MONITOR_RATE="$DISK_MONITOR_RATE"          # alias (CP-6 drop)
```

验证:
```bash
DISK_MONITOR_RATE=2 bash -c 'source config/user_config.sh; echo $EBS_MONITOR_RATE'  # → 2
```

#### CP-2.2.4 新增 configure_gcp_extreme_volumes() (P1) — **E1+ 改造: case 改 getter 能力判定**

在 `user_config.sh` 函数 `configure_io2_volumes` 之后(原 L109/L110 之间)插入新平行函数。该函数处理 GCP PD-Extreme / Hyperdisk-Extreme 的吞吐自动估算(GCP 公式:每 IOPS 约消耗 0.0007 MiB/s 配额,具体公式由 CP-1.1 `utils/disk_converter.sh:calculate_pd_extreme_throughput` 提供)。**E1+ 改造**: 内部不再 `case "$DATA_VOL_TYPE" in pd-extreme|hyperdisk-extreme)` 硬编码盘类型, 改为 `if [[ " $(get_disk_type_options) " =~ ' pd-extreme | hyperdisk-extreme ' ]]` 能力判定 — 与新增盘类型自动兼容。

新增代码:
```bash
# ----- GCP PD-Extreme / Hyperdisk-Extreme Automatic Throughput Calculation -----
# E1+ 改造: 内部使用 $(get_disk_type_options) 能力判定, 无硬编码盘类型列表。
# 与 configure_io2_volumes 平行, 由 configure_disk_volumes 统一入口分发调用 (CP-2.2.1)。
# 依赖: utils/disk_converter.sh:calculate_pd_extreme_throughput (CP-1.1 交付)
configure_gcp_extreme_volumes() {
    echo "🔧 Checking GCP PD/Hyperdisk volume configuration..." >&2

    # 能力判定 (E1+): 当前平台是否支持 pd-extreme / hyperdisk-extreme 盘类型?
    local _opts=" $(get_disk_type_options) "
    [[ "$_opts" =~ \ pd-extreme\  || "$_opts" =~ \ hyperdisk-extreme\  ]] || {
        echo "ℹ️  当前平台不支持 pd-extreme / hyperdisk-extreme, 跳过自动吞吐计算" >&2
        return 0
    }

    # 当前用户配置是否实际选了 extreme 盘 (与平台能力交集)
    local needs_calc=false
    [[ "$DATA_VOL_TYPE" == "pd-extreme" || "$DATA_VOL_TYPE" == "hyperdisk-extreme" ]] && needs_calc=true
    [[ "$ACCOUNTS_VOL_TYPE" == "pd-extreme" || "$ACCOUNTS_VOL_TYPE" == "hyperdisk-extreme" ]] && needs_calc=true

    if [[ "$needs_calc" == "true" ]]; then
        if [[ -f "${CONFIG_DIR}/../utils/disk_converter.sh" ]]; then
            source "${CONFIG_DIR}/../utils/disk_converter.sh"
            echo "✅ Disk converter loaded successfully" >&2
        else
            echo "❌ Error: utils/disk_converter.sh missing, cannot process pd-extreme" >&2
            exit 1
        fi
    fi

    # DATA volume — 用 if-equals 而非 case, 平台对等
    if [[ "$DATA_VOL_TYPE" == "pd-extreme" || "$DATA_VOL_TYPE" == "hyperdisk-extreme" ]]; then
        if [[ -n "$DATA_VOL_MAX_IOPS" ]]; then
            local original_throughput="$DATA_VOL_MAX_THROUGHPUT"
            local auto_throughput
            if auto_throughput=$(calculate_pd_extreme_throughput "$DATA_VOL_MAX_IOPS" 2>/dev/null); then
                DATA_VOL_MAX_THROUGHPUT="$auto_throughput"
                echo "ℹ️  DATA volume $DATA_VOL_TYPE auto-calculated: $original_throughput → $auto_throughput MiB/s (based on $DATA_VOL_MAX_IOPS IOPS)" >&2
            else
                echo "❌ Error: DATA volume $DATA_VOL_TYPE throughput calculation failed" >&2
                exit 1
            fi
        fi
    fi
    # pd-balanced / pd-ssd / local-ssd 吞吐由 GCP 按容量自动绑定, 无需计算 (no-op)

    # ACCOUNTS volume (对称)
    if [[ "$ACCOUNTS_VOL_TYPE" == "pd-extreme" || "$ACCOUNTS_VOL_TYPE" == "hyperdisk-extreme" ]]; then
        if [[ -n "$ACCOUNTS_VOL_MAX_IOPS" && -n "$ACCOUNTS_DEVICE" ]]; then
            local original_throughput="$ACCOUNTS_VOL_MAX_THROUGHPUT"
            local auto_throughput
            if auto_throughput=$(calculate_pd_extreme_throughput "$ACCOUNTS_VOL_MAX_IOPS" 2>/dev/null); then
                ACCOUNTS_VOL_MAX_THROUGHPUT="$auto_throughput"
                echo "ℹ️  ACCOUNTS volume $ACCOUNTS_VOL_TYPE auto-calculated: $original_throughput → $auto_throughput MiB/s" >&2
            else
                echo "❌ Error: ACCOUNTS volume $ACCOUNTS_VOL_TYPE throughput calculation failed" >&2
                exit 1
            fi
        fi
    fi
}
```

验证:
```bash
# 函数存在
CLOUD_PROVIDER=gcp bash -c 'source config/cloud_provider.sh && source config/user_config.sh; declare -F configure_gcp_extreme_volumes' | grep -q configure_gcp_extreme_volumes && echo OK
# 真正派发 (需要 CP-1.1 calculate_pd_extreme_throughput 先 stub)
CLOUD_PROVIDER=gcp DATA_VOL_TYPE=pd-extreme DATA_VOL_MAX_IOPS=30000 \
  bash -c 'calculate_pd_extreme_throughput(){ echo 1200; }; export -f calculate_pd_extreme_throughput; source config/cloud_provider.sh && source config/user_config.sh' 2>&1 | grep -q "pd-extreme auto-calculated" && echo OK
# AWS 平台调 GCP 函数: 能力判定立即 return (无副作用)
CLOUD_PROVIDER=aws DATA_VOL_TYPE=pd-extreme bash -c 'source config/cloud_provider.sh && source config/user_config.sh && configure_gcp_extreme_volumes' 2>&1 | grep -q "不支持 pd-extreme" && echo OK
```

### CP-2.3 config/config_loader.sh — 改造项目的核心点

> ⚠️ **关键节点**: `config_loader.sh:L102-128` 的 `detect_deployment_platform()` 是**整个改造项目的根**——所有下游 `CP-3` (monitoring) / `CP-4` (tools) / `CP-5` (analysis+viz) 的 platform-aware 行为都靠这里输出的 `DEPLOYMENT_PLATFORM` 变量。如果这里改错,整条调用链全部回退到 AWS 默认行为,GCP 模式静默失败,且无明显错误信号(因为 `ENA_MONITOR_ENABLED=false` 会让 GCP 主机看起来"像 IDC")。
>
> **改造策略**:优先复用 `CP-0.1 config/cloud_provider.sh`(已 export `CLOUD_PROVIDER`);只在 source 失败 / 文件缺失时 fallback 到本地三分支 IMDS 探测。

文件全长 837 行,本节涉及 L99-140 + L142-175 + L829 三段。

| # | 改造点 | file:line | 来源 | 等级 |
|---|---|---|---|---|
| 1 | `detect_deployment_platform()` 加 gcp 分支 + 优先 source `config/cloud_provider.sh` | `config_loader.sh:101-140` | TRACKER 11.1 联动 + file-notes config_loader §8.2 #1,#2 | **P0** |
| 2 | L108/L112/L119/L123/L128 `ENA_MONITOR_ENABLED` 派发改 `NIC_MONITOR_ENABLED` | `config_loader.sh:108-128` | TRACKER 12.2 联动 + file-notes config_loader §8.2 #4 | P1 |
| 3 | `detect_network_interface()` 局部变量 `ena_interfaces` 中立化 + 函数注释中立化 | `config_loader.sh:142-175` | file-notes config_loader §8.2 #5 | P2 |
| 4 | L829 `ENA_ALLOWANCE_FIELDS` default value 平台分发 + 双写 `NIC_ALLOWANCE_FIELDS` | `config_loader.sh:829` | file-notes config_loader §8.2 #7 | **P0** |

#### CP-2.3.1 detect_deployment_platform() 加 gcp 分支 (P0) — **E1+ 改造: Stage 2/3 case 改 getter**

改前 (`config_loader.sh:101-140`):
```bash
detect_deployment_platform() {
    if [[ "$DEPLOYMENT_PLATFORM" == "auto" ]]; then
        echo "🔍 Auto-detecting deployment platform..." >&2
        
        # Check if in AWS environment (via AWS metadata service)
        if curl -s --max-time 3 --connect-timeout 2 "${AWS_METADATA_ENDPOINT}/${AWS_METADATA_API_VERSION}/meta-data/instance-id" >/dev/null 2>&1; then
            DEPLOYMENT_PLATFORM="aws"
            ENA_MONITOR_ENABLED=true
            echo "✅ AWS environment detected, ENA monitoring enabled" >&2
        else
            DEPLOYMENT_PLATFORM="other"
            ENA_MONITOR_ENABLED=false
            echo "ℹ️  Non-AWS environment detected (IDC/other cloud), ENA monitoring disabled" >&2
        fi
    else
        echo "🔧 Using manually configured deployment platform: $DEPLOYMENT_PLATFORM" >&2
        case "$DEPLOYMENT_PLATFORM" in
            "aws")
                ENA_MONITOR_ENABLED=true
                echo "✅ AWS environment, ENA monitoring enabled" >&2
                ;;
            "other"|"idc")
                ENA_MONITOR_ENABLED=false
                echo "ℹ️  Non-AWS environment, ENA monitoring disabled" >&2
                ;;
            *)
                echo "⚠️  Unknown deployment platform: $DEPLOYMENT_PLATFORM, ENA monitoring disabled" >&2
                ENA_MONITOR_ENABLED=false
                ;;
        esac
    fi
    
    # Output final configuration
    echo "📊 Deployment platform configuration:" >&2
    echo "   Platform type: $DEPLOYMENT_PLATFORM" >&2
    echo "   ENA monitoring: $ENA_MONITOR_ENABLED" >&2
    
    # Mark platform detection as completed and export to subprocesses
    DEPLOYMENT_PLATFORM_DETECTED=true
}
```

改后(**E1+**: Stage 2 fallback IMDS 探测改用 getter; Stage 3 派发改用 `$(get_nic_monitor_process_name)` 能力判定, 无 case 块):
```bash
detect_deployment_platform() {
    # ----- Stage 1: prefer CP-0.1 config/cloud_provider.sh (single source of truth) -----
    local _cp_helper="${CONFIG_DIR}/../config/cloud_provider.sh"
    if [[ "$DEPLOYMENT_PLATFORM" == "auto" && -f "$_cp_helper" ]]; then
        # cloud_provider.sh 会 export CLOUD_PROVIDER=aws|gcp|other + 加载对应 provider getter
        # shellcheck source=/dev/null
        if source "$_cp_helper" 2>/dev/null && [[ -n "${CLOUD_PROVIDER:-}" ]]; then
            DEPLOYMENT_PLATFORM="$CLOUD_PROVIDER"
            echo "🔍 Platform from config/cloud_provider.sh: $DEPLOYMENT_PLATFORM" >&2
        fi
    fi

    # ----- Stage 2: fallback 本地 IMDS 探测 (helper 缺失或 source 失败) -----
    if [[ "$DEPLOYMENT_PLATFORM" == "auto" ]]; then
        echo "🔍 Auto-detecting deployment platform (fallback IMDS probe)..." >&2

        # GCP 优先: metadata.google.internal 要求 Metadata-Flavor: Google 头 (硬编码 — 此时 getter 不可用)
        if curl -s --max-time 3 --connect-timeout 2 \
               -H "Metadata-Flavor: Google" \
               "http://metadata.google.internal/computeMetadata/v1/instance/id" >/dev/null 2>&1; then
            DEPLOYMENT_PLATFORM="gcp"
        # AWS IMDSv1
        elif curl -s --max-time 3 --connect-timeout 2 \
               "http://169.254.169.254/latest/meta-data/instance-id" >/dev/null 2>&1; then
            DEPLOYMENT_PLATFORM="aws"
        else
            DEPLOYMENT_PLATFORM="other"
        fi
        # 设定 CLOUD_PROVIDER + 重 source helper 以加载对应 provider getter
        export CLOUD_PROVIDER="$DEPLOYMENT_PLATFORM"
        [[ -f "$_cp_helper" ]] && source "$_cp_helper" 2>/dev/null || true
    fi

    # ----- Stage 3: NIC 监控开关 — E1+ 能力判定, 无 case "$DEPLOYMENT_PLATFORM" -----
    # 规则: 平台提供 nic monitor 进程 (getter 非空) → 启用 NIC 监控
    #       AWS → "ena_network_monitor", GCP → "gvnic_network_monitor", OTHER → ""
    if [[ -n "$(get_nic_monitor_process_name 2>/dev/null || true)" ]]; then
        NIC_MONITOR_ENABLED=true
        echo "✅ $(get_platform_display_name) environment, NIC monitoring enabled" >&2
    else
        NIC_MONITOR_ENABLED=false
        echo "ℹ️  Non-cloud / unknown platform, NIC monitoring disabled" >&2
    fi
    # alias (CP-6 删)
    ENA_MONITOR_ENABLED="$NIC_MONITOR_ENABLED"

    # 触发 system_config.sh 的进程聚合 (CP-2.1.5: filter_platform_processes 用 getter 收集 nic monitor 进程名)
    declare -F filter_platform_processes >/dev/null && filter_platform_processes

    # Output final configuration
    echo "📊 Deployment platform configuration:" >&2
    echo "   Platform type: $DEPLOYMENT_PLATFORM" >&2
    echo "   NIC monitoring: $NIC_MONITOR_ENABLED (ENA alias: $ENA_MONITOR_ENABLED)" >&2

    # Mark platform detection as completed and export to subprocesses
    DEPLOYMENT_PLATFORM_DETECTED=true
    export DEPLOYMENT_PLATFORM CLOUD_PROVIDER NIC_MONITOR_ENABLED ENA_MONITOR_ENABLED DEPLOYMENT_PLATFORM_DETECTED
}
```

#### CP-2.3.2 L108 ENA enable 派发改 NIC (P1)

已合并到 CP-2.3.1 改后片段中的 Stage 3:统一从 `ENA_MONITOR_ENABLED=...` 改为 `NIC_MONITOR_ENABLED=...` 并通过 alias 同步旧名。

#### CP-2.3.3 detect_network_interface() 局部命名中立化 (P2)

来源: `file-notes/config_loader.sh.md` §8.2 #5。`config_loader.sh:L142-175 detect_network_interface()` 的函数体里有局部变量 `ena_interfaces` (L146-155 共 5 处使用) 和函数注释"ENA network interface" (L143/L145) 是 AWS-only 命名,但实际正则 `(eth|ens|enp)` 已是平台无关,gVNIC 接口名 `ens4` 同样命中 — **只改变量名 + 注释,不改正则**。

改前 (`config_loader.sh:L142-156`,节选关键 5 行):
```bash
# ----- Network Interface Detection Function -----
# Automatically detect ENA network interface
detect_network_interface() {
    # Prioritize detecting ENA interfaces
    local ena_interfaces
    if command -v ip >/dev/null 2>&1; then
        ena_interfaces=($(ip link show 2>/dev/null | grep -E "^[0-9]+: (eth|ens|enp)" | grep "state UP" | cut -d: -f2 | tr -d ' '))
    else
        ena_interfaces=()
    fi
    if [[ ${#ena_interfaces[@]} -gt 0 ]]; then
        NETWORK_INTERFACE="${ena_interfaces[0]}"
        return 0
    fi
```

改后(纯局部变量重命名 + 注释中立化,无功能改动):
```bash
# ----- Network Interface Detection Function -----
# Automatically detect primary NIC interface (works for AWS ENA / GCP gVNIC / IDC virtio)
detect_network_interface() {
    # Prioritize detecting cloud/enhanced NIC interfaces by naming convention
    local nic_interfaces
    if command -v ip >/dev/null 2>&1; then
        nic_interfaces=($(ip link show 2>/dev/null | grep -E "^[0-9]+: (eth|ens|enp)" | grep "state UP" | cut -d: -f2 | tr -d ' '))
    else
        nic_interfaces=()
    fi
    if [[ ${#nic_interfaces[@]} -gt 0 ]]; then
        NETWORK_INTERFACE="${nic_interfaces[0]}"
        return 0
    fi
```

验证(局部变量重命名零外部影响):
```bash
# 1) grep 实证: ena_interfaces 仅本函数内 5 处, 0 外部消费
grep -rn 'ena_interfaces' config/ utils/ monitoring/ tools/ analysis/ visualization/ 2>/dev/null | grep -v config_loader.sh
# 期望: 空输出 (零外部 reader)

# 2) 函数行为不变 (NETWORK_INTERFACE 仍正确填充)
bash -c 'source config/system_config.sh; source config/user_config.sh; source config/config_loader.sh; detect_network_interface; echo "NIC=$NETWORK_INTERFACE"'
# 期望: NIC=ens4 (GCP) 或 NIC=eth0 (AWS) 或 NIC=<本机默认接口>
```

#### CP-2.3.4 L829 ENA_ALLOWANCE_FIELDS default value 单源化 (P0) — **E1+ 改造: case 改 getter, §13.3 单源化**

来源: `file-notes/config_loader.sh.md` §8.2 #7 + §8.10。`config_loader.sh:L829` 是 `ENA_ALLOWANCE_FIELDS` 的**最终 fallback default**,独立于 `system_config.sh:L15-22` 的数组定义:当下游进程没继承到 env var 时(例如 vegeta 子进程通过 systemd 启动),会读这一行的默认值。**2 处下游消费**:`utils/ena_field_accessor.py:L64/L77`。

**§13.3 ENA_ALLOWANCE_FIELDS 独立 fallback 双源问题** → ✅ **E1+ absorbed**(单源 `$(get_nic_allowance_fields)`, 不再独立维护 default 字符串)。

改前 (`config_loader.sh:L829`):
```bash
export ENA_ALLOWANCE_FIELDS=${ENA_ALLOWANCE_FIELDS:-"bw_in_allowance_exceeded,bw_out_allowance_exceeded,pps_allowance_exceeded,conntrack_allowance_exceeded,linklocal_allowance_exceeded,conntrack_allowance_available"}
```

改后(**E1+**: 单源 getter, env override 仍优先, alias 同步):
```bash
# 字段语义说明:
#   AWS 模式: 6 个 ENA allowance counters (从 ethtool -S 读) — getter 返回硬编码 CSV
#   GCP 模式: 字段集为空 (gVNIC 无 allowance 概念, 改用 ethtool -S 的 dropped 计数,
#             由 CP-3.2 monitoring/nic_network_monitor.sh 决定真实集合)
#   OTHER  : 字段集为空
# E1+ 改造: 单源 $(get_nic_allowance_fields), 不再维护独立 default 字符串 (§13.3 absorbed)。
export NIC_ALLOWANCE_FIELDS="${NIC_ALLOWANCE_FIELDS:-$(get_nic_allowance_fields)}"
# alias (CP-6 删) — 必须放在 NIC_ALLOWANCE_FIELDS 之后, 保证 default 链一致
export ENA_ALLOWANCE_FIELDS="${ENA_ALLOWANCE_FIELDS:-$NIC_ALLOWANCE_FIELDS}"
```

验证(default 链 + 双写一致性 + getter 单源):
```bash
# 1) 完全无 env override → AWS default 6 字段 (由 get_nic_allowance_fields 提供)
unset NIC_ALLOWANCE_FIELDS ENA_ALLOWANCE_FIELDS
DEPLOYMENT_PLATFORM=aws CLOUD_PROVIDER=aws bash -c '
  source config/cloud_provider.sh; source config/system_config.sh; source config/user_config.sh; source config/config_loader.sh
  echo "NIC_COUNT=$(echo $NIC_ALLOWANCE_FIELDS | tr , \\n | wc -l)"
  echo "ENA_eq_NIC=$([[ \"$ENA_ALLOWANCE_FIELDS\" == \"$NIC_ALLOWANCE_FIELDS\" ]] && echo yes || echo no)"
  echo "single_source=$([[ \"$NIC_ALLOWANCE_FIELDS\" == \"$(get_nic_allowance_fields)\" ]] && echo yes || echo no)"
'
# 期望: NIC_COUNT=6, ENA_eq_NIC=yes, single_source=yes

# 2) GCP default 空集
unset NIC_ALLOWANCE_FIELDS ENA_ALLOWANCE_FIELDS
DEPLOYMENT_PLATFORM=gcp CLOUD_PROVIDER=gcp bash -c '
  source config/cloud_provider.sh; source config/system_config.sh; source config/user_config.sh; source config/config_loader.sh
  echo "NIC_LEN=${#NIC_ALLOWANCE_FIELDS}"
'
# 期望: NIC_LEN=0

# 3) env override 优先 (caller 显式注入新字段集)
NIC_ALLOWANCE_FIELDS="custom_field_1,custom_field_2" bash -c '
  source config/cloud_provider.sh; source config/system_config.sh; source config/user_config.sh; source config/config_loader.sh
  echo "$NIC_ALLOWANCE_FIELDS"
'
# 期望: custom_field_1,custom_field_2

# 4) 下游 ena_field_accessor.py 兼容性 (CP-1.4 改造前的 back-compat)
DEPLOYMENT_PLATFORM=aws CLOUD_PROVIDER=aws bash -c '
  source config/cloud_provider.sh; source config/system_config.sh; source config/user_config.sh; source config/config_loader.sh
  python3 -c "import os; print(os.environ[\"ENA_ALLOWANCE_FIELDS\"])"
'
# 期望: 6 字段 CSV 字符串(因 ENA alias 已双写)
```

#### CP-2.3.5 E1+ 平台对等性审查 + §13 阻塞点结构性消除 (§0.7 决策 6 + E-1.5 落实)

本次 CP-2 改造同时完成 E-1.5 平台对等性审查 (CI gate 候选), 全面扫除 `config/` 层 `${CLOUD_PROVIDER:-aws}` 反模式 / `case "$CLOUD_PROVIDER"` 急切派发:

1. **system_config.sh — 4 处 case 全删** (CP-2.1.2 / 2.1.3 / 2.1.4 / 2.1.5):
   - `METADATA_ENDPOINT` / `METADATA_API_PATH` / `METADATA_HEADER` / `CLOUD_IO_BASELINE_KIB` / `CLOUD_THROUGHPUT_BASELINE_KIB` 不再静态定义 export
   - 业务方使用时调 `$(get_metadata_endpoint)` / `$(get_metadata_api_path)` / `$(get_metadata_header)` / `$(get_baseline_io_kib)` / `$(get_baseline_throughput_kib)` 等懒求值 getter
   - **§13.2 source 顺序冲突结构性消除**: 不再有 system_config.sh 先 source 时 `CLOUD_PROVIDER=auto` 落 aws 默认分支的问题; re-evaluate hook 工单关闭
   - **§13.5 metadata header 缺失消除**: 所有 `curl ${METADATA_ENDPOINT}` 改为 `curl -H "$(get_metadata_header)" "$(get_metadata_endpoint)$(get_metadata_api_path)..."`; GCP `Metadata-Flavor: Google` header 由 getter 统一注入, AWS 仍可走 IMDSv1 (getter 返回空 header)

2. **user_config.sh — 2 处 case 改能力判定** (CP-2.2.1 / 2.2.4):
   - `configure_io2_volumes` / `configure_gcp_extreme_volumes` 合并为统一入口 `configure_disk_volumes()`, 内部按 `$(get_disk_type_options)` 能力判定分发 (`io2/gp3` 走 AWS 路径, `pd-extreme/hyperdisk-extreme` 走 GCP 路径)
   - **平台对等**: AWS / GCP 走相同入口函数, 无主从层级; AWS 平台调 `configure_gcp_extreme_volumes` 时通过 getter 能力判定立即 `return 0`, 无副作用

3. **config_loader.sh — 3 处 case 改 getter** (CP-2.3.1 Stage 3 ×2 + CP-2.3.4):
   - `ENA_MONITOR_ENABLED` → `NIC_MONITOR_ENABLED` (命名平台中立化, ENA alias 保留 1 Round)
   - 派生逻辑: `NIC_MONITOR_ENABLED=$([[ -n "$(get_nic_monitor_process_name)" ]] && echo true || echo false)` — 平台对等单源
   - **§13.3 ENA_ALLOWANCE_FIELDS 独立 fallback 双源消除**: 单源 `NIC_ALLOWANCE_FIELDS="${NIC_ALLOWANCE_FIELDS:-$(get_nic_allowance_fields)}"`, 业务方与 PLAN 共用同一字段表

4. **平台对等性 lint** (CI gate, E-1.5 落地物):
   ```bash
   # config/ 目录全文必须 0 命中 (除 cloud_provider.sh 内部 case 分发)
   grep -rE '\$\{CLOUD_PROVIDER:-aws\}|case "?\$\{?(CLOUD_PROVIDER|DEPLOYMENT_PLATFORM)' config/ \
     | grep -v 'config/cloud_provider.sh' \
     | wc -l   # 必须 == 0
   ```

**§13.X 状态变更** (E1+ 同步标记, 与文件内已有 6 处 "E1+ absorbed" 标记一致):

| § | V1.0 状态 | E1+ 状态 | 消除方式 |
|---|---|---|---|
| §13.2 source 顺序冲突 | ❌ P0 阻塞 | ✅ **E1+ absorbed** | system_config.sh 不再静态定义 platform-aware 变量, 业务方调懒求值 getter |
| §13.3 ENA_ALLOWANCE_FIELDS 独立 fallback | ❌ P0 阻塞 | ✅ **E1+ absorbed** | config_loader.sh L829 单源化, `$(get_nic_allowance_fields)` 是 PLAN 与业务唯一来源 |
| §13.5 metadata header 缺失 | ❌ P0 阻塞 | ✅ **E1+ absorbed** | `$(get_metadata_header)` 统一注入, GCP 不再裸 curl |

> **CI gate 时机**: 该 lint 在 CP-2 完工后由 contract test 守护(参见 CP-0.2), CP-3/4/5 改 worker / monitoring / overhead 时若新引入 `${CLOUD_PROVIDER:-aws}` 直接 fail。

#### CP-2.3 验证(4 个场景全覆盖)

```bash
# Scenario 1: AWS 模式(env override, 不依赖 IMDS 探测)
DEPLOYMENT_PLATFORM=aws bash -c '
  source config/system_config.sh
  source config/user_config.sh
  source config/config_loader.sh
  detect_deployment_platform
  echo "PLATFORM=$DEPLOYMENT_PLATFORM NIC=$NIC_MONITOR_ENABLED ENA_alias=$ENA_MONITOR_ENABLED"
' 2>&1 | grep -q "PLATFORM=aws NIC=true ENA_alias=true" && echo "AWS OK"

# Scenario 2: GCP 模式(env override)
DEPLOYMENT_PLATFORM=gcp bash -c '
  source config/system_config.sh
  source config/user_config.sh
  source config/config_loader.sh
  detect_deployment_platform
  echo "PLATFORM=$DEPLOYMENT_PLATFORM NIC=$NIC_MONITOR_ENABLED"
' 2>&1 | grep -q "PLATFORM=gcp NIC=true" && echo "GCP OK"

# Scenario 3: Other/IDC fallback (env override)
DEPLOYMENT_PLATFORM=other bash -c '
  source config/system_config.sh
  source config/user_config.sh
  source config/config_loader.sh
  detect_deployment_platform
  echo "PLATFORM=$DEPLOYMENT_PLATFORM NIC=$NIC_MONITOR_ENABLED"
' 2>&1 | grep -q "PLATFORM=other NIC=false" && echo "OTHER OK"

# Scenario 4: auto + config/cloud_provider.sh 优先级(在 GCP 主机 mock 环境)
CLOUD_PROVIDER=gcp DEPLOYMENT_PLATFORM=auto bash -c '
  # mock helper: 直接 export CLOUD_PROVIDER 即可
  source config/system_config.sh
  source config/config_loader.sh
  detect_deployment_platform
  echo "PLATFORM=$DEPLOYMENT_PLATFORM"
' 2>&1 | grep -q "PLATFORM=gcp" && echo "auto-via-helper OK"
```

### CP-2.4 config/internal_config.sh

**当前状态**(commit `e843571`):76 行,无函数定义。`grep -nE 'AWS|EBS|ENA' config/internal_config.sh` 命中 5 个 `BOTTLENECK_EBS_*` 变量名(L17/18/21/22 定义 + L70/71 export)+ 注释中"AWS"/"EBS"字面 ~10 处。

**豁免理由**:
1. `BOTTLENECK_EBS_*_THRESHOLD` 阈值数值本身平台中立(都是 90% 利用率 / 50ms 延迟),只是**变量名**带 `EBS` 字面。
2. 这些变量的"中立化"必须与 **CP-3.3 monitoring/bottleneck_detector.sh** 的下游消费点同步改(改名后所有 `BOTTLENECK_EBS_*` reader 也要同步),否则会破业务。
3. 因此 CP-2 阶段**不改 internal_config.sh**,把 `BOTTLENECK_EBS_* → BOTTLENECK_DISK_*` 整体重命名 + alias 推迟到 **CP-3.3**(届时 internal_config.sh 也只新增 alias 行,无函数修改)。
4. 该文件不参与 platform 探测,不消费 `CLOUD_PROVIDER`,也不调用 IMDS,因此 CP-2 范畴内零改动。

**CP-2 阶段验证**(确认零业务改动):
```bash
git -C /usr/local/google/home/lelandgong/blockchain-node-benchmark diff --stat e843571 -- config/internal_config.sh
# 期望输出:无 diff
```

---

## CP-2.5 NIC 监控接口抽象层 (Y+ 架构, 解 §13.X ENA/gVNIC 语义分裂)

> 改造范围：新增 monitoring/network/ 子目录 (4 文件) + utils/network_field_registry.py + analysis/network_analyzer.py
> 设计目标：用接口多态消化 AWS ENA / GCP gVNIC 的 semantic 分裂 (限速触发 vs 丢包计数), reader 端零 platform 分支
> Y+ 架构定位：与 CP-2 的 disk getter 拼接方案形成"差异化抽象"——叶子节点命名差异走 getter, 子树形状差异走接口

### CP-2.5.0 为什么 NIC 走接口而 disk 走 getter (架构差异化决策)

| 维度 | Disk 字段差异 | NIC 字段差异 |
|---|---|---|
| 差异本质 | 相同语义, 命名不同 | 不同语义, counter 集合不同 |
| AWS 例 | `aws_standard_iops` | `bw_in_allowance_exceeded` (限速触发计数) |
| GCP 例 | `baseline_iops` | `tx_drops` (丢包计数) |
| 能否对齐到同一字段名 | 能 (都是 IOPS baseline) | 不能 (限速 vs 丢包是不同物理现象) |
| 字段数量 | 三平台 1:1 对应 | AWS=6, GCP=3, Other=0 (1:N) |
| 采集命令 | 三平台都是 iostat | AWS=ethtool -S, GCP=ethtool -S + sysfs, Other=只 sysfs |
| 下游分析 | 同函数 analyze_iops | 必须按 semantic_type 分支 |
| 抽象方案 | getter 拼接 (参数化) | 接口 + 多实现 (多态) |

**架构原则** (引用 Sandi Metz / John Ousterhout):
- 叶子节点的命名差异 → 参数化够用 (getter 拼接, KISS)
- 子树形状差异 → 必须多态 (接口抽象, 多个实现)
- 用接口去解决"命名差异" = 用工厂模式构造一个 int, 违反 KISS

**Y+ 架构定义**: 同一项目内, 根据差异本质选用不同抽象强度 — disk 用 getter (弱抽象), NIC 用 interface (强抽象), 显式承认"两种字段族适用不同方案"。

**关键扩展 (按 (platform, nic_driver) 分多态)**: GCP 内部又分 gVNIC (gve driver) vs virtio (virtio_net driver), 字段集完全不同 (gve 暴露 `gvnic_tx_drops/gvnic_rx_no_buffer/gvnic_tx_timeout`, virtio_net 暴露 `rx_drops/tx_tx_timeouts/rx_xdp_drops/tx_xdp_tx_drops` + 按 queue 的 `rx{N}_drops` 聚合), 必须按 driver 子类型多态。AWS 也保留扩展位 (未来 ENA Express / SRD 等可能引入新 driver)。Provider 标识从 `${PLATFORM}` 升级为 `${PLATFORM}_${NIC_DRIVER}` (例: `aws_ena`, `gcp_gvnic`, `gcp_virtio`, `other_none`)。

### CP-2.5.1 接口签名 (monitoring/network/interface.sh)

定义 4 个核心接口函数, 每个 provider 必须实现:

```bash
# 1. 初始化 (探测网卡是否可用 + 准备 counter 源)
init_network_monitoring() -> 0/1
  返回 0: 监控就绪
  返回 1: 监控不可用 (网卡不存在 / counter 不支持), 上游应跳过 NIC chain

# 2. 生成 CSV header (列出本 provider 采集的所有字段名)
generate_network_csv_header() -> stdout (CSV header line)
  AWS:  timestamp,interface,rx_bytes,tx_bytes,rx_packets,tx_packets,\
        ena_bw_in_exceeded,ena_bw_out_exceeded,ena_pps_exceeded,\
        ena_conntrack_exceeded,ena_conntrack_available,ena_linklocal_exceeded,\
        network_saturation_signal
  GCP:  timestamp,interface,rx_bytes,tx_bytes,rx_packets,tx_packets,\
        gvnic_tx_drops,gvnic_rx_no_buffer,gvnic_tx_timeout,network_saturation_signal
  Other: timestamp,interface,rx_bytes,tx_bytes,rx_packets,tx_packets,network_saturation_signal

# 3. 采集一次数据 (返回 CSV row, 列数与 header 一致)
collect_network_metrics() -> stdout (CSV row)
  每行末尾必须有 network_saturation_signal 列 (0/1), 这是语义对齐列

# 4. 字段元数据查询 (供 analysis 层用)
get_network_field_metadata(field_name) -> stdout (semantic_type)
  semantic_type 枚举: throughput | packet_count | saturation_counter |
                     drop_counter | error_counter | gauge | saturation_signal
  AWS: ena_bw_in_exceeded -> saturation_counter
  GCP: gvnic_tx_drops -> drop_counter
  统一: rx_bytes -> throughput, network_saturation_signal -> saturation_signal
```

**接口契约的不变量**:
- 不管 provider 是谁, CSV 必含 timestamp + interface + rx_bytes + tx_bytes + rx_packets + tx_packets + network_saturation_signal 这 7 列
- 中间的 platform-specific 列数可以不同 (AWS 6, GCP 3, Other 0)
- saturation_signal 是跨平台语义统一列, reader 只读这一列就能做"网络是否饱和"的统计

**新增第 5 个接口** (在 `config/cloud_provider.sh` 层, 不是 provider 实现层 — 用于 variant 派发):

```bash
# 5. NIC driver 探测 (供 detect_cloud_provider 决定 source 哪个 provider 实现)
detect_nic_driver() -> stdout ("ena" | "gvnic" | "virtio" | "none")
  实现: ethtool -i $NETWORK_INTERFACE 2>/dev/null | awk '/^driver:/ {print $2}'
        ena         -> "ena"
        gve         -> "gvnic"
        virtio_net  -> "virtio"
        其他 / 失败 / 网卡不存在 / 无 ethtool -> "none" (合法兜底, 不报错)
```

**config/cloud_provider.sh 探测流程升级** (从单维 platform 扩为 (platform, nic_driver) 双维):

```bash
detect_cloud_provider() {
    PLATFORM=$(detect_platform)                            # aws | gcp | other
    NIC_DRIVER=$(detect_nic_driver)                        # ena | gvnic | virtio | none
    CLOUD_PROVIDER_VARIANT="${PLATFORM}_${NIC_DRIVER}"     # aws_ena | gcp_gvnic | gcp_virtio | other_none | ...
    export CLOUD_PROVIDER PLATFORM NIC_DRIVER CLOUD_PROVIDER_VARIANT
}
```

`CLOUD_PROVIDER_VARIANT` 即 provider 实现文件名 (去 `.sh`): `monitoring/network/${CLOUD_PROVIDER_VARIANT}.sh`。

### CP-2.5.2 Provider 实现骨架 (5 variant: aws_ena / gcp_gvnic / gcp_virtio / other_none + 扩展位)

**文件命名规范**: `monitoring/network/${platform}_${nic_driver}.sh`

| 文件 | platform | nic_driver | 旧名 (废弃) | 说明 |
|---|---|---|---|---|
| `monitoring/network/aws_ena.sh` | aws | ena | aws.sh | AWS ENA (现役 + 老 ENA) |
| `monitoring/network/gcp_gvnic.sh` | gcp | gvnic | gcp.sh | GCP gVNIC (gve driver, n2/c2/n4 等) |
| `monitoring/network/gcp_virtio.sh` | gcp | virtio | (新增) | GCP virtio_net (cloudtop / e2 系列 / 老实例) |
| `monitoring/network/other_none.sh` | other | none | other.sh | Mac / IDC / 无 ethtool |
| (扩展位) | aws | ena_express | — | AWS ENA Express / SRD (未来) |
| (扩展位) | azure | mana | — | Azure MANA (未来) |

#### monitoring/network/aws_ena.sh (~80 LOC)
```bash
#!/bin/bash
# AWS ENA 实现 (替代原 ena_network_monitor.sh)
source "$(dirname ${BASH_SOURCE[0]})/interface.sh"

readonly AWS_ENA_FIELDS=(
    "bw_in_allowance_exceeded"
    "bw_out_allowance_exceeded"
    "pps_allowance_exceeded"
    "conntrack_allowance_exceeded"
    "linklocal_allowance_exceeded"
    "conntrack_allowance_available"
)

init_network_monitoring() {
    [[ -z "$NETWORK_INTERFACE" ]] && return 1
    command -v ethtool >/dev/null 2>&1 || return 1
    ethtool -S "$NETWORK_INTERFACE" &>/dev/null || return 1
    # 真实探测有几个 ENA counter 可用 (老 ENA 可能 3 个, 新 ENA 6 个)
    local found=0
    for field in "${AWS_ENA_FIELDS[@]}"; do
        ethtool -S "$NETWORK_INTERFACE" 2>/dev/null | grep -q "$field" && ((found++))
    done
    [[ $found -gt 0 ]] || return 1
    return 0
}

generate_network_csv_header() {
    local h="timestamp,interface,rx_bytes,tx_bytes,rx_packets,tx_packets"
    for field in "${AWS_ENA_FIELDS[@]}"; do
        h="${h},ena_${field/_allowance/}"  # ena_bw_in_exceeded 等
    done
    h="${h},network_saturation_signal"
    echo "$h"
}

collect_network_metrics() {
    local ts=$(date +"%Y-%m-%d %H:%M:%S")
    local iface="$NETWORK_INTERFACE"
    local rx_bytes=$(cat "/sys/class/net/$iface/statistics/rx_bytes")
    local tx_bytes=$(cat "/sys/class/net/$iface/statistics/tx_bytes")
    local rx_pkts=$(cat "/sys/class/net/$iface/statistics/rx_packets")
    local tx_pkts=$(cat "/sys/class/net/$iface/statistics/tx_packets")

    local ethtool_out=$(ethtool -S "$iface" 2>/dev/null)
    local ena_values=""
    local saturation=0
    for field in "${AWS_ENA_FIELDS[@]}"; do
        local v=$(echo "$ethtool_out" | grep "$field:" | awk '{print $2}')
        v=${v:-0}
        ena_values="${ena_values},${v}"
        # bw_*/pps_*/conntrack_exceeded > 0 触发饱和信号
        if [[ "$field" =~ exceeded ]] && [[ "$v" -gt 0 ]]; then
            saturation=1
        fi
    done

    echo "${ts},${iface},${rx_bytes},${tx_bytes},${rx_pkts},${tx_pkts}${ena_values},${saturation}"
}

get_network_field_metadata() {
    case "$1" in
        rx_bytes|tx_bytes) echo "throughput" ;;
        rx_packets|tx_packets) echo "packet_count" ;;
        ena_*_exceeded) echo "saturation_counter" ;;
        ena_conntrack_available) echo "gauge" ;;
        network_saturation_signal) echo "saturation_signal" ;;
        *) echo "unknown" ;;
    esac
}
```

#### monitoring/network/gcp_gvnic.sh (~70 LOC, driver=gve)
- 实现同 4 个接口 (内容同原 gcp.sh 设计)
- `init_network_monitoring`: 探测 `ethtool -i $NETWORK_INTERFACE | grep -q 'driver: gve'`, 否则 return 1
- 字段集: gvnic_tx_drops, gvnic_rx_no_buffer, gvnic_tx_timeout (3 个) 从 ethtool -S
- saturation_signal: tx_drops > 0 OR rx_no_buffer_count > 0 触发
- 没有 *_allowance_exceeded 字段, 因为 gVNIC 根本不报这种 counter
- `get_network_field_metadata` 把 gvnic_tx_drops / gvnic_rx_no_buffer 标 `drop_counter`, gvnic_tx_timeout 标 `error_counter`

#### monitoring/network/gcp_virtio.sh (~80 LOC, driver=virtio_net) — 新增

字段实测来源: cloudtop ens4 (driver=virtio_net, version=1.0.0)。
顶级 counter 4 个 + 按 queue 的 `rx{N}_drops` 聚合 1 列 = 5 个 virtio_* 字段。

```bash
#!/bin/bash
# GCP virtio_net 实现 (cloudtop / e2 / 老 GCP 实例, driver=virtio_net)
source "$(dirname ${BASH_SOURCE[0]})/interface.sh"

readonly GCP_VIRTIO_FIELDS=(
    "rx_drops"          # 顶级 rx 丢包
    "tx_tx_timeouts"    # 顶级 tx 超时 (注意: ethtool 里名字真就是 tx_tx_timeouts, 双 tx)
    "rx_xdp_drops"      # XDP 路径 rx 丢包
    "tx_xdp_tx_drops"   # XDP 路径 tx 丢包
)

# 按 queue 的 rx{N}_drops 用正则聚合 (N=0..6+, 数量随 vCPU 变)
readonly GCP_VIRTIO_PER_QUEUE_PATTERN="rx[0-9]+_drops"

init_network_monitoring() {
    [[ -z "$NETWORK_INTERFACE" ]] && return 1
    command -v ethtool >/dev/null 2>&1 || return 1
    local driver=$(ethtool -i "$NETWORK_INTERFACE" 2>/dev/null | awk '/^driver:/ {print $2}')
    [[ "$driver" == "virtio_net" ]] || return 1
    return 0
}

generate_network_csv_header() {
    local h="timestamp,interface,rx_bytes,tx_bytes,rx_packets,tx_packets"
    for field in "${GCP_VIRTIO_FIELDS[@]}"; do
        h="${h},virtio_${field}"
    done
    h="${h},virtio_per_queue_rx_drops_sum"   # 聚合的 per-queue drops
    h="${h},network_saturation_signal"
    echo "$h"
}

collect_network_metrics() {
    local ts=$(date +"%Y-%m-%d %H:%M:%S")
    local iface="$NETWORK_INTERFACE"
    local rx_bytes=$(cat "/sys/class/net/$iface/statistics/rx_bytes")
    local tx_bytes=$(cat "/sys/class/net/$iface/statistics/tx_bytes")
    local rx_pkts=$(cat "/sys/class/net/$iface/statistics/rx_packets")
    local tx_pkts=$(cat "/sys/class/net/$iface/statistics/tx_packets")

    local ethtool_out=$(ethtool -S "$iface" 2>/dev/null)
    local virtio_values=""
    local saturation=0
    for field in "${GCP_VIRTIO_FIELDS[@]}"; do
        local v=$(echo "$ethtool_out" | awk -v f="$field" '$1 == f":" {print $2}')
        v=${v:-0}
        virtio_values="${virtio_values},${v}"
        [[ "$v" -gt 0 ]] && saturation=1
    done

    # per-queue drops 聚合: 求和所有 rx{N}_drops
    local per_queue_drops=$(echo "$ethtool_out" | awk '/^[[:space:]]*rx[0-9]+_drops:/ {sum+=$2} END {print sum+0}')
    [[ "$per_queue_drops" -gt 0 ]] && saturation=1

    echo "${ts},${iface},${rx_bytes},${tx_bytes},${rx_pkts},${tx_pkts}${virtio_values},${per_queue_drops},${saturation}"
}

get_network_field_metadata() {
    case "$1" in
        rx_bytes|tx_bytes) echo "throughput" ;;
        rx_packets|tx_packets) echo "packet_count" ;;
        virtio_rx_drops|virtio_rx_xdp_drops|virtio_tx_xdp_tx_drops|virtio_per_queue_rx_drops_sum) echo "drop_counter" ;;
        virtio_tx_tx_timeouts) echo "error_counter" ;;
        network_saturation_signal) echo "saturation_signal" ;;
        *) echo "unknown" ;;
    esac
}
```

**virtio_net 字段 ↔ semantic_type 映射**:

| 字段 | semantic_type | 备注 |
|---|---|---|
| virtio_rx_drops | drop_counter | 顶级 rx 丢包累计 |
| virtio_tx_tx_timeouts | error_counter | tx 超时累计 (ethtool 原名 tx_tx_timeouts) |
| virtio_rx_xdp_drops | drop_counter | XDP 路径 rx 丢包 |
| virtio_tx_xdp_tx_drops | drop_counter | XDP 路径 tx 丢包 |
| virtio_per_queue_rx_drops_sum | drop_counter | sum(rx{N}_drops for N in 0..队列数) |

**virtio_net saturation_signal 触发**: `virtio_rx_drops > 0 OR virtio_tx_tx_timeouts > 0 OR virtio_rx_xdp_drops > 0 OR virtio_tx_xdp_tx_drops > 0 OR virtio_per_queue_rx_drops_sum > 0`。

#### monitoring/network/other_none.sh (~40 LOC, 旧 other.sh)
- 只采基础 4 列 (rx/tx_bytes, rx/tx_packets) 从 /sys/class/net
- 不采任何平台特定 counter
- saturation_signal 永远 0 (Mac/IDC 没法判断 cloud-level 饱和)
- `init_network_monitoring` 只检查 `/sys/class/net/$NETWORK_INTERFACE` 存在

### CP-2.5.3 unified_monitor.sh 集成方式

```bash
# 在 unified_monitor.sh 入口加载逻辑
# 由 config/cloud_provider.sh 的 detect 决定 source 哪个实现
case "$CLOUD_PROVIDER" in
    aws)   source "${SCRIPT_DIR}/network/aws.sh" ;;
    gcp)   source "${SCRIPT_DIR}/network/gcp.sh" ;;
    other) source "${SCRIPT_DIR}/network/other.sh" ;;
    *)     echo "ERROR: unknown CLOUD_PROVIDER=$CLOUD_PROVIDER" >&2; exit 1 ;;
esac

# 业务代码只调接口, 不关心 platform
if init_network_monitoring; then
    generate_network_csv_header > "$NETWORK_CSV"
    while running; do
        collect_network_metrics >> "$NETWORK_CSV"
    done
else
    log_warn "Network monitoring not available on $CLOUD_PROVIDER"
fi
```

**集成不变量**: unified_monitor.sh 主循环里**禁止**出现 `if [[ "$CLOUD_PROVIDER" == "aws" ]]` 这种判断 — 所有 platform 分发由 source 时刻决定, 运行时只见接口。

### CP-2.5.4 reader 端 (analysis/network_analyzer.py) 单 reader 设计

```python
# utils/network_field_registry.py
class NetworkFieldRegistry:
    """字段元数据注册表 - 与 bash get_network_field_metadata 1:1 对称"""

    # 静态映射 (供 Python 端快速查表, 不每次都 fork bash)
    _SEMANTIC_MAP = {
        # 跨平台统一列
        "rx_bytes": "throughput",
        "tx_bytes": "throughput",
        "rx_packets": "packet_count",
        "tx_packets": "packet_count",
        "network_saturation_signal": "saturation_signal",
        # AWS ENA
        "ena_bw_in_exceeded": "saturation_counter",
        "ena_bw_out_exceeded": "saturation_counter",
        "ena_pps_exceeded": "saturation_counter",
        "ena_conntrack_exceeded": "saturation_counter",
        "ena_linklocal_exceeded": "saturation_counter",
        "ena_conntrack_available": "gauge",
        # GCP gVNIC
        "gvnic_tx_drops": "drop_counter",
        "gvnic_rx_no_buffer": "drop_counter",
        "gvnic_tx_timeout": "error_counter",
    }

    @classmethod
    def get_semantic_type(cls, field_name: str) -> str:
        return cls._SEMANTIC_MAP.get(field_name, "unknown")

# analysis/network_analyzer.py
def analyze_network(df: pd.DataFrame) -> Dict:
    """单 reader, 零 if/elif platform 分支"""
    results = {}
    for col in df.columns:
        semantic = NetworkFieldRegistry.get_semantic_type(col)
        if semantic == "throughput":
            results[col] = analyze_throughput(df[col])
        elif semantic == "saturation_counter":
            results[col] = analyze_saturation(df[col])
        elif semantic == "drop_counter":
            results[col] = analyze_drops(df[col])
        elif semantic == "saturation_signal":
            results["network_saturated_ratio"] = (df[col] == 1).mean()
    return results
```

**reader 不变量**:
- `analyze_network` 不允许出现 `"ena_"` / `"gvnic_"` 字符串字面量 — 所有分发必须经 `get_semantic_type`
- 字段缺失要静默跳过 (列不存在时 `for col in df.columns` 自然过滤), 不抛 KeyError
- bash `get_network_field_metadata` 和 Python `_SEMANTIC_MAP` 用 contract test 强校验 1:1 对称 (CP-0 已有的 contract test 框架延伸一条 case)

### CP-2.5.5 CSV 字段命名约定 (避免下游误读)

| 平台变体 (variant) | 字段前缀 | 例 |
|---|---|---|
| AWS ENA (`aws_ena`) | `ena_` | `ena_bw_in_exceeded`, `ena_pps_exceeded` |
| GCP gVNIC (`gcp_gvnic`, driver=gve) | `gvnic_` | `gvnic_tx_drops`, `gvnic_rx_no_buffer` |
| GCP virtio (`gcp_virtio`, driver=virtio_net) | `virtio_` | `virtio_rx_drops`, `virtio_tx_tx_timeouts`, `virtio_per_queue_rx_drops_sum` |
| Other (`other_none`) | (无前缀) | 只有基础 5 列 + saturation_signal |
| 跨平台统一 | (无前缀) | `rx_bytes`, `tx_bytes`, `network_saturation_signal` |

**关键约定**: 任何字段名带平台前缀 (`ena_*` / `gvnic_*` / `virtio_*`) 都是 platform-specific, 下游分析时必须先查 NetworkFieldRegistry 确认 semantic_type 再决定是否分析、怎么分析。**禁止**任何下游代码直接 hardcode 平台前缀。

### CP-2.5.6 业务文件改动清单

**新建 (6 个)**:
- monitoring/network/interface.sh (~30 LOC, 接口签名+文档)
- monitoring/network/aws.sh (~80 LOC, AWS 实现)
- monitoring/network/gcp.sh (~70 LOC, GCP 实现)
- monitoring/network/other.sh (~40 LOC, Other 实现)
- utils/network_field_registry.py (~60 LOC, semantic_type 查表)
- analysis/network_analyzer.py (~120 LOC, 单 reader)

**删除 (1 个)**:
- monitoring/ena_network_monitor.sh (功能拆到 network/aws.sh)

**修改 (6 个)**:
- monitoring/unified_monitor.sh: 把 ENA 相关逻辑 (L501-L1908 几处) 改成 source $NETWORK_IMPL + 调接口
- monitoring/bottleneck_detector.sh: ena_fields 改用 NetworkFieldRegistry 查 saturation_counter
- utils/ena_field_accessor.py: 废弃, 改用 NetworkFieldRegistry
- visualization/advanced_chart_generator.py: ena_columns 改 network_columns + semantic 判断
- visualization/report_generator.py: 同上
- config/system_config.sh: 删除 ENA_ALLOWANCE_FIELDS 数组 (字段已下沉到 network/aws.sh)

**注**: 此清单只是规划, 实际写代码在 CP-3 范畴内执行 (CP-3 是 monitoring/ 层改造); 本 CP-2.5 章节只规定**架构形状**和**接口契约**, 不直接动业务代码。

### CP-2.5.7 架构演进触发器 (Q3=B 决策的明确化)

**当前决策**: disk 监控继续用 getter 拼接, NIC 监控走接口抽象。

**升级触发条件** (满足任一即应把 disk 也升级到 NIC 同款接口):
1. 新平台 disk 引入 semantic 分裂字段 (例如 GCP Hyperdisk Extreme 新增 "provisioned throughput" 字段, 而 AWS io2 无对应物)
2. 平台数 ≥ 5 (AWS + GCP + Azure + OCI + 阿里云时, getter case 列表开始变长)
3. 同一平台支持多种 disk 类型且字段集差异显著 (例如 Azure premium_v2 vs ultra disk vs standard ssd 各自字段集不同)
4. 出现 disk 字段需要"按 semantic_type 分发到不同 analyze 函数"的需求 (例如 throughput limit counter 与 IOPS limit counter 必须分开统计)

**条件未满足时**: 保持 disk getter 化 (Sandi Metz: 重复比错误的抽象便宜)。

**降级触发条件** (反向): 如果未来 AWS 和 GCP 的 NIC counter 集合趋同 (例如 ENA 新版本也报 tx_drops, gVNIC 也报 *_exceeded), 且语义对齐, 则 NIC 接口可以塌缩回 getter 拼接 — 但短期内 (2 年) 概率极低。

### CP-2.5.8 验证矩阵

| 场景 | 期望 |
|---|---|
| AWS c5.large (老 ENA, 只有 3 个 ENA counter) | `init_network_monitoring` 返 0, CSV 有 6 个 ena_* 列但部分为 0 |
| AWS c6i.4xlarge (新 ENA, 6 个全有) | CSV 6 个 ena_* 列都有真实值 |
| GCP n2-standard-4 (gVNIC) | CSV 0 个 ena_* 列, 3 个 gvnic_* 列 |
| Mac/IDC (CLOUD_PROVIDER=other) | CSV 只有 4 基础列 + saturation_signal 永远 0 |
| 任意平台缺 ethtool | `init_network_monitoring` 返 1, NIC chain 整体跳过 |
| reader 收到 AWS CSV | analyze_saturation 跑 5 次 (5 个 ena_*_exceeded), saturated_ratio 来自 network_saturation_signal |
| reader 收到 GCP CSV | analyze_drops 跑 2 次 (gvnic_tx_drops + gvnic_rx_no_buffer), analyze_error 跑 1 次 (gvnic_tx_timeout) |
| reader 收到 Other CSV | 只跑 analyze_throughput + saturated_ratio (恒为 0) |
| contract test: bash ↔ python 字段对称 | `get_network_field_metadata` 三平台返回的字段集 = `NetworkFieldRegistry._SEMANTIC_MAP` 的 keys 子集 |

**验证脚本骨架** (放在 tests/test_nic_interface_contract.sh):
```bash
for provider in aws gcp other; do
    source "monitoring/network/${provider}.sh"
    header=$(generate_network_csv_header)
    IFS=',' read -ra fields <<< "$header"
    for field in "${fields[@]}"; do
        semantic=$(get_network_field_metadata "$field")
        # Python 端查相同字段
        py_semantic=$(python -c "from utils.network_field_registry import NetworkFieldRegistry; print(NetworkFieldRegistry.get_semantic_type('$field'))")
        [[ "$semantic" == "$py_semantic" ]] || { echo "MISMATCH $provider/$field: bash=$semantic py=$py_semantic"; exit 1; }
    done
done
```

---

## CP-3：monitoring/ 层（7 改 + 1 新）

> 改造范围：monitoring/ 下 7 个 .sh + 1 个新增 nic_network_monitor.sh 模板
> 涉及代码总量 5,863 行，其中 unified_monitor.sh 2,802 行是 CSV header 真源头
> CP-3 是整个 GCP 迁移的"信号生成层"，所有下游 analysis/visualization 字段名都从这里继承

### ⚠️ CP-3 章节 Y+ 升级公告 (与 CP-2.5 配套)

**原计划** (E1+ 截止): 用 getter 拼接 `ena_${field}` 字段名, monitoring/unified_monitor.sh 内嵌 ENA 判断分支。

**Y+ 升级后**: 删除 getter 拼接 ena_* 字段的所有逻辑, 改为:
1. unified_monitor.sh 在入口根据 `$CLOUD_PROVIDER` source 对应的 `monitoring/network/{aws,gcp,other}.sh`
2. 业务代码只调用 4 个标准接口 (init_network_monitoring / generate_network_csv_header / collect_network_metrics / get_network_field_metadata)
3. `monitoring/ena_network_monitor.sh` 整体废弃, 功能拆到 `monitoring/network/aws.sh`
4. `utils/ena_field_accessor.py` 整体废弃, 改用 `utils/network_field_registry.py` 提供 `semantic_type` 查询
5. `config/system_config.sh` 删除 `ENA_ALLOWANCE_FIELDS` readonly array (字段下沉到 network/aws.sh 内部)

**影响范围** (与 CP-2.5.6 业务文件改动清单一致):
- 新建 6 文件 (network/interface.sh + aws.sh + gcp.sh + other.sh + network_field_registry.py + network_analyzer.py)
- 删除 2 文件 (ena_network_monitor.sh + ena_field_accessor.py)
- 修改 6 文件 (unified_monitor.sh + bottleneck_detector.sh + 3 visualization + system_config.sh)

**与原 CP-3 章节关系**:
- 原 CP-3.1 (unified_monitor.sh getter 化 ena_* 字段) → 重定义为「CP-3.1 改用 network/<provider>.sh source + 调接口」
- 原 CP-3.2 (bottleneck_detector ena_fields getter 化) → 重定义为「CP-3.2 用 NetworkFieldRegistry.get_semantic_type() == 'saturation_counter' 替代 ena_* hardcode」
- 原 CP-3.3+ (visualization ena_columns getter 化) → 重定义为「CP-3.3+ 用 NetworkFieldRegistry 查 semantic_type 而非字面 ena_* 列名匹配」

**Disk 监控不动**: disk 字段差异属于"叶子命名差异", 继续用 getter 拼接方案 (CP-3.X disk 相关子节保持原状)。原因见 CP-2.5.0 对比表 + CP-2.5.7 架构演进触发器。

---

### CP-3 全局原则
1. **业务零改动**：commit e843571 之后 monitoring/*.sh 字节级不动；所有平台分发通过新增 `${CLOUD_PROVIDER}` 判断 + utils 层 alias 函数透明完成
2. **双写不删旧**：CSV header 新增 `nic_*`/`disk_*` 列时旧 `ena_*`/`ebs_*` 列保留，下游兼容期 ≥ 2 个 Round
3. **CP-2 source 顺序强约束**：unified_monitor.sh L21 已 `source ebs_converter.sh`，但 CP-2 internal_config.sh 改造后，所有 source CLOUD_PROVIDER 依赖的脚本必须在 source ebs_converter 之后再 `[[ -z "$CLOUD_PROVIDER" ]] && source ../config/config_loader.sh` 强制 re-evaluate（避免 CP-2 提到的 bash declare -A 先后顺序竞态）
4. **平台分发函数集中**：新增 utils/platform_dispatcher.sh（CP-1 阶段已规划），CP-3 各文件只调用 `is_aws()` / `is_gcp()` / `get_platform_nic_driver()`，不内联 `[[ $CLOUD_PROVIDER == aws ]]`

---

### CP-3.1 monitoring/unified_monitor.sh（核心，2802 行）⭐ 最难

**风险等级**：⛔ P0 极高 — CSV header 是整个项目下游所有 analysis/visualization 的字段契约源头

#### 改造点清单（8 处）

| # | 改造点 | 实证 file:line | 等级 | 联动 |
|---|---|---|---|---|
| 1 | `generate_csv_header()` 主入口（L1920-1935）加 platform-aware 分支 | unified_monitor.sh:1920 ✓ | P0 | → CP-5.1（device_manager.py 列消费）/ CP-5.2（report_generator glob） |
| 2 | `build_ena_header()`（L1905-1917）函数 rename → `build_nic_header()` + 旧名 alias | unified_monitor.sh:1905 ✓ | P0 | → CP-3.2（ena_network_monitor 也用同一 ENA_ALLOWANCE_FIELDS_STR） |
| 3 | `get_ena_allowance_data()`（L497-548）加 GCP 分支：gVNIC 无 ethtool -S allowance，走 `/sys/class/net/<iface>/queues/` 或全 0 兜底 | unified_monitor.sh:497 ✓ | P0 | → CP-3.2 同一逻辑（去重抽 utils/nic_metrics.sh） |
| 4 | `generate_json_metrics()`（L1938-2010）参数 `ena_data` rename `nic_data` + JSON key `ena_data`→`nic_data` 双写 | unified_monitor.sh:1938,1944,1998 ✓ | P0 | → CP-3.3（bottleneck_detector 读 unified_metrics.json） |
| 5 | `generate_json_metrics` 内部 `"ebs_util"` / `"ebs_latency"` JSON key（L1974-1975, L1989-1990）改双写 `disk_util`/`disk_latency` | unified_monitor.sh:1974-1990 ✓ | P0 | → CP-3.3 L116-119（jq -r '.ebs_util' 读端必须同步加 alias） |
| 6 | `MONITORING_PROCESS_NAMES_STR` 默认值（L1406）含字面量 `ena_network_monitor` `bottleneck_detector` — 改读 `filter_platform_processes()` 包装 | unified_monitor.sh:1406 ✓ | P1 | → CP-3.4（monitoring_coordinator MONITOR_TASKS 键名同步） |
| 7 | data_line 拼接（L2089, L2096）— ena_data 段位置不变但函数内变量重命名 nic_data；CSV 顺序对下游 cut -d',' -f<N> 兼容 | unified_monitor.sh:2089,2096 ✓ | P0 | → CP-3.3 L1964-1965（device_data cut -f9 -f7 偏移依赖） |
| 8 | `generate_json_metrics` 调用点 L2147 参数透传 ena_data → nic_data | unified_monitor.sh:2147 ✓ | P0 | 内部一致性 |

#### 当前 CSV header 字段全清单（实证 L1920-1935）

```
basic_header   (L1921, 10 字段):  timestamp, cpu_usage, cpu_usr, cpu_sys, cpu_iowait, cpu_soft, cpu_idle, mem_used, mem_total, mem_usage
device_header  (L1922, 动态):      generate_all_devices_header()  →  iostat_collector.sh:144 生成
                                   prefix 形如 data_nvme1n1_* / accounts_nvme2n1_*（21 字段 × N 设备）
                                   字段名通过 `${prefix}_$(get_disk_field_prefix)_iops` / `${prefix}_$(get_disk_field_prefix)_throughput_mibs` 动态拼接（AWS→aws_standard / GCP→baseline / Other→standard）
network_header (L1923, 10 字段):  net_interface, net_rx_mbps, net_tx_mbps, net_total_mbps, net_rx_gbps, net_tx_gbps, net_total_gbps, net_rx_pps, net_tx_pps, net_total_pps
ena_header     (L1930, 6 字段):    bw_in_allowance_exceeded, bw_out_allowance_exceeded, pps_allowance_exceeded, conntrack_allowance_exceeded, linklocal_allowance_exceeded, conntrack_allowance_available
                                   （字段集来自 config/system_config.sh:19-21 + config_loader.sh:829 ENA_ALLOWANCE_FIELDS_STR）
overhead_header (L1924, 2 字段):  monitoring_iops_per_sec, monitoring_throughput_mibs_per_sec
block_height_header (L1925, 6 字段): local_block_height, mainnet_block_height, block_height_diff, local_health, mainnet_health, data_loss
qps_header     (L1926, 3 字段):    current_qps, rpc_latency_ms, qps_data_available
```

#### 改造后 CSV header（新旧双写表）

| 段落 | 当前列名（保留） | 新增双写列名（GCP） | 兜底策略（GCP 无对应 metric） |
|---|---|---|---|
| basic | 全部不变 | — | — |
| device | `data_nvme1n1_${field_prefix}_iops`（其中 `field_prefix=$(get_disk_field_prefix)` → AWS=`aws_standard` / GCP=`baseline` / Other=`standard`）| 单列即可，不再双写——getter 在 source 时已根据 CLOUD_PROVIDER 选定 | iostat 通用，writer 端 `${prefix}_$(get_disk_field_prefix)_iops` 动态拼接 |
| device | `data_nvme1n1_${field_prefix}_throughput_mibs`（同上）| 同上 | 同上 |
| network | 全部不变 | — | — |
| ena/nic | `bw_in_allowance_exceeded` 等 6 个 ena 字段 | `nic_bw_in_limited` 等 6 个 nic 字段；GCP 上前 5 全写 0，最后一个 `conntrack_allowance_available` (gauge) 写 -1 表示 N/A | gVNIC driver 不暴露 allowance counter |
| overhead | 不变 | — | — |
| block_height | 不变 | — | — |
| qps | 不变 | — | — |

#### 改前/改后代码块 8 处实证

**[1] generate_csv_header L1920-1935 改前**
```bash
# unified_monitor.sh:1920-1935 (当前 commit e843571)
generate_csv_header() {
    local basic_header="timestamp,cpu_usage,..."
    local device_header=$(generate_all_devices_header)
    local network_header="net_interface,net_rx_mbps,..."
    local overhead_header="monitoring_iops_per_sec,monitoring_throughput_mibs_per_sec"
    local block_height_header="local_block_height,mainnet_block_height,..."
    local qps_header="current_qps,rpc_latency_ms,qps_data_available"
    if [[ "$ENA_MONITOR_ENABLED" == "true" ]]; then
        local ena_header=$(build_ena_header)
        echo "$basic_header,$device_header,$network_header,$ena_header,$overhead_header,$block_height_header,$qps_header"
    else
        echo "$basic_header,$device_header,$network_header,$overhead_header,$block_height_header,$qps_header"
    fi
}
```

**[1] generate_csv_header 改后（业务零改动，靠 NIC_MONITOR_ENABLED + build_nic_header 透明替换；ENA_MONITOR_ENABLED 仍保留为 alias）**
```bash
# 改后逻辑：build_nic_header() 内部按 CLOUD_PROVIDER 分发，输出列名永远是 nic_* 前缀 + 旧 ena_* 列名双写
# 由 utils/platform_dispatcher.sh::build_nic_header() 接管，unified_monitor.sh 本体函数体不动
# 平台分发后 header 形如：
#   [...,bw_in_allowance_exceeded,...,conntrack_allowance_available,nic_bw_in_limited,...,nic_conntrack_avail,...]
```

**[2] build_ena_header L1905-1917 改前/改后**：见 utils 层 platform_dispatcher.sh（CP-1）；本文件内只增加 `build_nic_header() { build_ena_header "$@"; }` alias，业务字节不动

**[3] get_ena_allowance_data L497-548 改前**
```bash
# unified_monitor.sh:497-526 (摘要)
get_ena_allowance_data() {
    if [[ "$ENA_MONITOR_ENABLED" != "true" ]]; then
        # default 0 填充
        return
    fi
    if ! is_command_available "ethtool"; then ... fi
    local ethtool_output=$(ethtool -S "$NETWORK_INTERFACE" 2>/dev/null || echo "")
    # 然后 grep "$field:" awk '{print $2}'
    ...
}
```

**[3] 改后（utils/nic_metrics.sh 拦截，本体不动；E1+ 能力判定，不按 CLOUD_PROVIDER 名称分发）**
```bash
# 新增 utils/nic_metrics.sh::get_nic_allowance_data()
# 不再用 case "$CLOUD_PROVIDER"，改为按 get_nic_allowance_fields 是否返非空判定能力
get_nic_allowance_data() {
    local fields_csv="$(get_nic_allowance_fields)"   # AWS 返 6 字段 CSV / GCP+Other 返 ""
    if [[ -z "$fields_csv" ]]; then
        # 平台无 allowance 能力（GCP gVNIC / Other 兜底）→ 输出与下游 reader 等长全 0/N-A 行
        # 长度由 reader 端约定的 NIC_ALLOWANCE_OUTPUT_WIDTH 决定（CP-1 utils 层常量，默认 6）
        local n=${NIC_ALLOWANCE_OUTPUT_WIDTH:-6}
        local out="" i
        for ((i=1; i<n; i++)); do out="${out:+$out,}0"; done
        echo "$out,-1"   # 最后一位 gauge 写 -1 = N/A
        return
    fi
    # 平台有 allowance 能力（AWS ENA）→ 调本文件原函数，按 fields_csv 字段拉取
    get_ena_allowance_data "$fields_csv"
}
```
> 设计要点：判定依据是 **能力**（getter 返字段集是否非空），不是平台名称。后续若 GCP/Azure 推出 allowance counter 等价能力，只需让其 `get_nic_allowance_fields` 返非空即可走相同 writer 入口，不再需要 case 分支。

**[4][5] generate_json_metrics L1974-1990 改前**
```bash
# L1968-1979
cat > "${MEMORY_SHARE_DIR}/latest_metrics.json.tmp" << EOF
{
    "timestamp": "$timestamp",
    "cpu_usage": $cpu_usage,
    "memory_usage": $mem_usage,
    "ebs_util": $ebs_util,
    "ebs_latency": $ebs_latency,
    "network_util": $network_util,
    "error_rate": 0
}
EOF
```

**[4][5] 改后（业务字节不动；改 utils/metric_emitter.sh 接管 cat heredoc 输出后用 jq 注入双写 key）—— 见 CP-1 utils 层方案**
```bash
# 渲染后 latest_metrics.json 实际内容:
{
    "timestamp": "...", "cpu_usage": ..., "memory_usage": ...,
    "ebs_util": $ebs_util, "ebs_latency": $ebs_latency,    # 旧 key 保留
    "disk_util": $ebs_util, "disk_latency": $ebs_latency,  # 新 key 镜像
    "network_util": ..., "error_rate": 0
}
```

**[6] MONITORING_PROCESS_NAMES_STR L1406 改前**
```bash
# unified_monitor.sh:1404-1406
if [[ -z "$MONITORING_PROCESS_NAMES_STR" ]]; then
    export MONITORING_PROCESS_NAMES_STR="iostat mpstat sar vmstat netstat unified_monitor bottleneck_detector ena_network_monitor block_height_monitor performance_visualizer overhead_monitor adaptive_frequency error_recovery report_generator"
fi
```

**[6] 改后（通过 config_loader 注入而非本文件改字面量）—— CP-2 config_loader 已规划 ENV override**
```bash
# config_loader.sh 注入 platform-aware 默认值（AWS=ena_network_monitor / GCP=nic_network_monitor）
# unified_monitor.sh:1406 字符串值由外部 export 决定，函数体字节不动
```

**[7] data_line 拼接 L2089 L2096**：变量重命名属于"读名修改"，因 nic_data=ena_data 时为同一字符串，业务字节不动。下游 cut -d',' -f<N> 偏移完全不变 ✓

**[8] L2147 调用**：同 [7]

#### 强制依赖（执行顺序）
1. **先完成 CP-1 utils 层**（platform_dispatcher.sh / nic_metrics.sh / metric_emitter.sh）
2. **再完成 CP-2 config_loader 注入**（CLOUD_PROVIDER + MONITORING_PROCESS_NAMES_STR override）
3. **CP-3.1 本身不改 unified_monitor.sh 业务字节**，只在 utils 层加包装函数实现透明分发

#### Phase 7.5 阻塞点对接
- **[CROSS-PROC-CONTRACT P0]** report_generator.py L1359 `glob 'monitoring_overhead_*.csv'` 的源在本文件 L1767 `write_monitoring_overhead_log` 写 `$MONITORING_OVERHEAD_LOG`（路径由 config_loader.sh `detect_deployment_paths()` 设置）→ 文件名 platform-aware 时 glob 需同步改 → **联动 CP-5.2**

#### 🆕 待回灌 TRACKER §13.X
- **🆕 隐藏问题 #1 §13.6 / §13.12 — ✅ E1+ absorbed**：unified_monitor.sh + iostat_collector.sh `${prefix}_aws_standard_iops` 字段名硬编码 → 改 `${prefix}_$(get_disk_field_prefix)_iops` 动态拼接，AWS 返 `aws_standard` / GCP 返 `baseline` / Other 返 `standard`，writer 端结构性消除字面量
- **🆕 隐藏问题 #2**：unified_monitor.sh:2080 `printf "0,%.0s"` 兜底数量改用 `IFS=',' read -ra _fa <<< "$(get_nic_allowance_fields)"; count=${#_fa[@]}`（getter 返回 6 字段 CSV，GCP 返空串则 count=0 自动跳过 allowance 段），CSV 列数与 build_nic_header 输出严格一致

---

### CP-3.2 monitoring/ena_network_monitor.sh → monitoring/nic_network_monitor.sh（文件级重命名 + GCP gVNIC 实现）

**风险等级**：🔥 P0 高 — 平台差异最大的文件，AWS ENA 和 GCP gVNIC 数据源完全异构

#### 全文 ethtool/ena 调用点清单（实证 ena_network_monitor.sh 266 行）

| 行号 | 调用 | 用途 | AWS ena 行为 | GCP gVNIC 替代 |
|---|---|---|---|---|
| ena_network_monitor.sh:26 ✓ | `init_logger "ena_network_monitor"` | 日志器名 | "ena_network_monitor" | 改 "nic_network_monitor"（通过新文件名传入） |
| ena_network_monitor.sh:30 ✓ | `ENA_LOG="${LOGS_DIR}/ena_network_${SESSION_TIMESTAMP}.csv"` | 输出文件名 | ena_network_*.csv | 双写 nic_network_*.csv（兼容期符号链接） |
| ena_network_monitor.sh:50 ✓ | `command -v ethtool` | 二进制检查 | 必需 | 必需（gVNIC 也支持 ethtool 但字段不同） |
| ena_network_monitor.sh:56 ✓ | `ethtool -S "$NETWORK_INTERFACE"` | 全量字段拉取 | 输出 ena_ 系列 + allowance | gVNIC 输出 tx_/rx_/queue_ 系列，**无 allowance** |
| ena_network_monitor.sh:62-71 ✓ | 字段存在性探测 | 至少 1 个 ENA 字段才认为支持 | `ena_fields_found` 计数 | GCP 上必然 0 → 走 fallback 路径 |
| ena_network_monitor.sh:80 ✓ | `generate_ena_csv_header > "$ENA_LOG"` | 写 CSV header | 用 ENA_ALLOWANCE_FIELDS_STR | 改用 NIC_FIELDS_STR（platform-aware） |
| ena_network_monitor.sh:86-93 ✓ | `generate_ena_csv_header()` 函数 | 拼 header | basic + ena_fields | 同结构但字段集来自 utils |
| ena_network_monitor.sh:104-145 ✓ | `get_ena_network_stats()` | 主采集函数 | grep ethtool 输出 | GCP 用 `/sys/class/net/$iface/statistics/*` |
| ena_network_monitor.sh:130 ✓ | `pps_allowance_exceeded` 字段 | hardcoded grep | ✓ | GCP 写 0 |
| ena_network_monitor.sh:137-138 ✓ | `bw_in_allowance_exceeded`, `bw_out_allowance_exceeded` | hardcoded grep | ✓ | GCP 写 0 |
| ena_network_monitor.sh:145 ✓ | echo 输出 CSV 行 | 拼接 | timestamp,interface,rx,tx,pkts...ena_stats,limited flags | 保持同 schema，gcp 兜底 0 |
| ena_network_monitor.sh:192-? | `analyze_ena_limits()` | 后分析 | grep ena allowance | GCP 跳过或全 0 报告 |

#### GCP gVNIC 等价命令（实证调研）

```bash
# AWS ena 字段拉取
ethtool -S eth0 | grep -E "bw_in_allowance_exceeded|pps_allowance_exceeded|..."

# GCP gVNIC 等价路径（gve driver）
# 1. queue 统计（每队列 RX/TX bytes/packets）
ls /sys/class/net/eth0/queues/        # rx-0/ tx-0/ ... 
cat /sys/class/net/eth0/statistics/rx_bytes
cat /sys/class/net/eth0/statistics/tx_bytes
cat /sys/class/net/eth0/statistics/rx_packets
cat /sys/class/net/eth0/statistics/tx_packets
cat /sys/class/net/eth0/statistics/rx_dropped       # drop ≈ "limited" 间接信号
cat /sys/class/net/eth0/statistics/tx_dropped

# 2. ethtool -S 在 gVNIC 上也可用，但字段名是 rx_packets / tx_packets / rx_bytes / interrupts
ethtool -S eth0 | head -20        # gVNIC 输出 tx_*/rx_*/queue_*/interrupts，无 allowance
ethtool -i eth0                   # driver: gve (确认 GCP)

# 3. 带宽上限查询（GCP 上限按 vCPU 推算，无 per-instance API）
# 用 instance metadata 拿 machine-type 后查 GCP 静态文档矩阵
curl -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/machine-type
```

#### 平台分支完整实现（新文件 monitoring/nic_network_monitor.sh 骨架）

```bash
#!/bin/bash
# monitoring/nic_network_monitor.sh
# Cross-platform NIC monitor（AWS ENA + GCP gVNIC）
# 业务方法：保留 ena_network_monitor.sh 原始文件不动；新文件 source 它并 override 关键函数

source "$(dirname "${BASH_SOURCE[0]}")/ena_network_monitor.sh"   # AWS 默认实现
source "$(dirname "${BASH_SOURCE[0]}")/../utils/platform_dispatcher.sh"

# E1+ 能力判定：按 get_nic_driver 返回的 driver 标识决定 stats 取数实现
# AWS=ena → 走 ethtool -S 路径 / GCP=gvnic → 走 /sys/class/net 路径 / Other=generic → 走 /sys/class/net 兜底
get_nic_network_stats() {
    local driver="$(get_nic_driver)"   # ena | gvnic | generic
    case "$driver" in
        ena)              get_ena_network_stats "$@" ;;
        gvnic|generic)    get_sysfs_network_stats "$@" ;;
        *)                get_sysfs_network_stats "$@" ;;
    esac
}
# 设计要点：分发键是 driver 名（能力标识），不是 CLOUD_PROVIDER 名。
# 若未来某平台 ethtool 等价输出 ena 字段，只需让其 get_nic_driver 返 "ena" 即可复用 writer。

# 改名：原 get_gvnic_network_stats → get_sysfs_network_stats（中立命名，AWS/GCP/Other 均可走）

get_sysfs_network_stats() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local interface="$NETWORK_INTERFACE"
    local rx_bytes=$(cat /sys/class/net/$interface/statistics/rx_bytes 2>/dev/null || echo 0)
    local tx_bytes=$(cat /sys/class/net/$interface/statistics/tx_bytes 2>/dev/null || echo 0)
    local rx_packets=$(cat /sys/class/net/$interface/statistics/rx_packets 2>/dev/null || echo 0)
    local tx_packets=$(cat /sys/class/net/$interface/statistics/tx_packets 2>/dev/null || echo 0)
    # allowance 段字段数 = getter 返回字段数（AWS=6 / GCP+Other=0），无能力则跳过
    local fields_csv="$(get_nic_allowance_fields)"
    local ena_stats=""
    if [[ -n "$fields_csv" ]]; then
        IFS=',' read -ra _fa <<< "$fields_csv"
        local n=${#_fa[@]} i
        for ((i=1; i<n; i++)); do ena_stats="${ena_stats},0"; done
        ena_stats="${ena_stats},-1"   # 最后一位 gauge = -1 (N/A)
    fi
    # 末尾三个 limited 标志：用 dropped 间接推算（AWS/GCP/Other 均通用）
    local rx_dropped=$(cat /sys/class/net/$interface/statistics/rx_dropped 2>/dev/null || echo 0)
    local network_limited=$([[ $rx_dropped -gt 0 ]] && echo 1 || echo 0)
    local pps_limited=0      # sysfs 路径无 per-pps 限速反馈
    local bandwidth_limited=0
    echo "$timestamp,$interface,$rx_bytes,$tx_bytes,$rx_packets,$tx_packets$ena_stats,$network_limited,$pps_limited,$bandwidth_limited"
}
```

#### 联动
- **→ CP-3.1**：本文件输出 schema 必须与 unified_monitor.sh L1923 network_header + L1930 ena_header 严格对齐
- **→ CP-3.4**：MONITOR_TASKS 键 `ena_network` 添加 `nic_network` alias 同步指向本文件
- **→ CP-1**：utils/platform_dispatcher.sh 必须先就绪
- **→ CP-5.2**：report_generator.py 如果 glob `ena_network_*.csv` 需同步加 `nic_network_*.csv`（待 R 期定位 ⚠️）

#### 🆕 待回灌 TRACKER §13.X
- **🆕 隐藏问题 #3**：ena_network_monitor.sh:121 `ena_stats="$ena_stats,$value"` 起始 ena_stats 为空时第一次产生 `,值` 形式 → L145 echo `"...$ena_stats,..."` 会出现 `,,` 双逗号 → CSV 错位风险（虽然已存在但 GCP 路径要避坑）

---

### CP-3.3 monitoring/bottleneck_detector.sh（1222 行）

**风险等级**：🟡 P1 中 — 阈值平台分发 + JSON key 双写

#### 改造点清单

| # | 改造点 | 实证 file:line | 等级 | 联动 |
|---|---|---|---|---|
| 1 | `check_ebs_bottleneck()` 阈值变量 `BOTTLENECK_EBS_IOPS_THRESHOLD`/`BOTTLENECK_EBS_THROUGHPUT_THRESHOLD`/`BOTTLENECK_EBS_UTIL_THRESHOLD`/`BOTTLENECK_EBS_LATENCY_THRESHOLD` 改读 alias `BOTTLENECK_DISK_*` | bottleneck_detector.sh:298-299,405,423,1207-1208 ✓ | P1 | → CP-2 internal_config.sh（alias 在 config 层定义） |
| 2 | JSON 写入 key `ebs_util`/`ebs_latency`/`ebs_aws_iops`/`ebs_throughput` 双写 `disk_*` 镜像 | bottleneck_detector.sh:94-97,147-150 ✓ | P1 | → CP-5.x（analysis 层 jq 读端） |
| 3 | `BOTTLENECK_COUNTERS` 数组键 `ebs_util`/`ebs_latency`/`ebs_aws_iops`/`ebs_aws_throughput`/`ena_limit` 加 alias 键 `disk_*`/`nic_limit` | bottleneck_detector.sh:163-168,233-243,259-272 ✓ | P2 | 内部一致性 |
| 4 | `check_ena_bottleneck` 函数（待 R 期定位 ⚠️ — grep 未直接命中，可能在 analyze_ena_limits L192 或 ENA_ALLOWANCE_FIELDS 消费段 L471-483） | bottleneck_detector.sh:471-483 ✓（间接） | P1 | GCP 全 None 兜底 |
| 5 | `BOTTLENECK_COUNTERS["ena_limit"]` 初始化（L230 L259）→ GCP 永远为 0 不触发，确保下游 jq 读 null 不崩 | bottleneck_detector.sh:230,259 ✓ | P0 | → CP-5.2 report_generator 读端 |

#### 5 字段（conntrack_allowance_available 是 gauge）GCP 全 None 兜底

```bash
# AWS ENA 6 字段（含 1 gauge）
# 实证：config/system_config.sh:19-21 + config_loader.sh:829
ENA_ALLOWANCE_FIELDS = [
    "bw_in_allowance_exceeded",      # counter (>0 = 限速)
    "bw_out_allowance_exceeded",     # counter
    "pps_allowance_exceeded",        # counter
    "conntrack_allowance_exceeded",  # counter
    "linklocal_allowance_exceeded",  # counter
    "conntrack_allowance_available", # ⚠️ gauge (剩余可用数；越小越接近限速)
]

# GCP gVNIC 兜底（utils/nic_metrics.sh::get_nic_allowance_data）
# 前 5 counter 写 0（=无限速），最后 1 gauge 写 -1（= N/A，与 0 区分；下游 viz/analysis 必须把 -1 当 NaN）
```

**bottleneck_detector.sh GCP 上的判定逻辑**：
- L405 `aws_iops_utilization > aws_iops_threshold` — 阈值变量名照旧（来自 BOTTLENECK_EBS_IOPS_THRESHOLD 或新 alias BOTTLENECK_DISK_IOPS_THRESHOLD），计算逻辑不变
- 任何 `ena_*` counter > 阈值的判定，GCP 上输入恒为 0，自然不触发 → 满足"GCP 全 None 兜底"
- gauge `conntrack_allowance_available` 的判定如有"< 100 报警"逻辑，需加 `[[ $value -ge 0 ]]` 短路，避免 -1 触发误报

#### 联动
- **→ CP-3.1**：消费 unified_monitor 写的 `unified_metrics.json` 中 `ebs_util` 等 key，必须 CP-3.1 step [5] 完成双写后才能读 disk_*
- **→ CP-2**：BOTTLENECK_DISK_* alias 在 config/internal_config.sh 注入
- **→ CP-5.x**：bottleneck JSON 输出（L94-97 L147-150）是下游 report_generator 数据源

#### 🆕 待回灌 TRACKER §13.X
- **🆕 隐藏问题 #4**：bottleneck_detector.sh:163-168 BOTTLENECK_COUNTERS 数组的 `accounts_ebs_*` 系列（L240-243, L269-272） — 当 ACCOUNTS_DEVICE 配置时才初始化，但 jq 读端可能假设永远存在 → GCP/AWS 都有此问题，alias 时要把 `accounts_disk_*` 也同步覆盖

---

### CP-3.4 monitoring/monitoring_coordinator.sh（605 行）

**风险等级**：🟡 P2 中 — 启动协调 + 平台环境变量注入

#### 改造点清单

| # | 改造点 | 实证 file:line | 等级 | 联动 |
|---|---|---|---|---|
| 1 | `MONITOR_TASKS` 关联数组（L32-37）键 `ena_network` → 加 `nic_network` alias；键 `ebs_bottleneck` 已存在，加 `disk_bottleneck` alias 同指 bottleneck_detector.sh | monitoring_coordinator.sh:32-37 ✓ | P2 | → CP-3.2/3.3 文件 |
| 2 | `start_monitor` case 语句（L119, L138, L152）echo 文本中立化（"EBS bottleneck" → "Disk bottleneck"），代码字节最小改 | monitoring_coordinator.sh:119,138,152 ✓ | P3 | UI/log 一致性 |
| 3 | bug fix: `start_all_monitors()` L218 `monitors_to_start=("unified" "ena_network" "block_height" "ebs_bottleneck")` — 此数组与 L138/L152 case 的键名一致 ✓ 不需改，但加 GCP 时数组改为 `[$ENA_KEY] [$BOTTLENECK_KEY]` 变量 | monitoring_coordinator.sh:218 ✓ | P1 | 启动正确性 |
| 4 | iostat 路径硬编码 `/tmp/iostat_*.pid` `/tmp/iostat_*.data`（L265）→ 改 `${TMP_DIR}/iostat_*`（TMP_DIR 由 config_loader 注入） | monitoring_coordinator.sh:265 ✓ | P2 | 多实例并行隔离 |
| 5 | **【启动协调点改 ⭐ 子进程注入 CLOUD_PROVIDER】** `start_monitor()` 调用子脚本时（L66, L84, L202）必须 `export CLOUD_PROVIDER` 前置，确保 ena_network_monitor.sh / bottleneck_detector.sh 子进程能读到 | monitoring_coordinator.sh:66,84,202 ✓ | P0 | → CP-3.1/3.2/3.3 全部消费方 |

#### 启动协调点改详细（子进程注入 CLOUD_PROVIDER）

**改前 L66**
```bash
local script_name="${MONITOR_TASKS[$monitor_name]:-}"
# 后面会通过 nohup 或 & 启动子脚本
```

**改后（在 start_monitor 函数顶部加 env 前置）**
```bash
start_monitor() {
    local monitor_name="$1"
    # ⭐ 强制 export CLOUD_PROVIDER 到子进程环境
    [[ -z "$CLOUD_PROVIDER" ]] && source "$(dirname "${BASH_SOURCE[0]}")/../config/config_loader.sh"
    export CLOUD_PROVIDER
    export ENA_MONITOR_ENABLED      # 已存在的也确保 export
    export NIC_MONITOR_ENABLED      # 新增 alias
    local script_name="${MONITOR_TASKS[$monitor_name]:-}"
    ...
}
```

#### 联动
- **→ CP-2**：CLOUD_PROVIDER 必须在 config_loader.sh 已定义
- **→ CP-3.1/3.2/3.3**：子进程读到正确 CLOUD_PROVIDER 才能走平台分支
- **→ CP-1**：utils/platform_dispatcher.sh 在 source 链上必须先于本文件加载

#### 🆕 待回灌 TRACKER §13.X
- **🆕 隐藏问题 #5 §13.10 路径 suffix**：monitoring_coordinator.sh:15 `LOGS_DIR=${LOGS_DIR:-"/tmp/blockchain-node-benchmark/logs"}` 硬编码 fallback 路径，多实例并行（AWS + GCP 同主机）冲突
  ```bash
  LOGS_DIR="${LOGS_DIR_BASE:-/tmp/blockchain-node-benchmark}-${CLOUD_PROVIDER}/logs"   # 多实例隔离，CLOUD_PROVIDER 在 config_loader detect 后已保证三态 (aws|gcp|other)
  # 注：这里是路径拼接场景，直接使用 detect 后的 CLOUD_PROVIDER 变量本身（不是调 getter 分发），不违反 E1+ 定义
  ```

---

### CP-3.5 monitoring/{iostat_collector,block_height_monitor,unified_event_manager}.sh 三件套

#### CP-3.5.a iostat_collector.sh（239 行）

**风险等级**：🟡 P1 中 — 设备命名平台分发 + AWS 字段名硬编码

| # | 改造点 | 实证 file:line | 等级 |
|---|---|---|---|
| 1 | `generate_device_header()` (L131-145) 列名硬编码 `${prefix}_aws_standard_iops` → 改 `${prefix}_$(get_disk_field_prefix)_iops` / `${prefix}_$(get_disk_field_prefix)_throughput_mibs` 动态拼接（writer 端结构性消除 "aws_standard" 字面量；getter AWS→`aws_standard` / GCP→`baseline` / Other→`standard`）| iostat_collector.sh:144 ✓ | P0 §13.12 — ✅ E1+ absorbed |
| 2 | LEDGER_DEVICE / ACCOUNTS_DEVICE 设备名校验（L203-210）`/dev/$LEDGER_DEVICE` — 设备发现走 utils 抽象 `resolve_block_device()`（CP-1 utils 层，内部用 `/dev/disk/by-id/google-*` 或 nvme model 匹配） | iostat_collector.sh:203,205,209 ✓ | P1 |
| 3 | `convert_to_aws_standard_throughput` 调用（L89）→ utils 层加中立别名 `convert_to_standard_throughput()`（无平台耦合），原函数保留 alias | iostat_collector.sh:89 ✓ | P1 |
| 4 | iostat 文件命名（待 R 期定位 ⚠️ — 函数 `get_iostat_data` L52-53 读 iostat_data_file，路径源由调用者传入，需追溯调用栈） | iostat_collector.sh:53 ✓（间接） | P2 |

**lsblk 设备命名平台分发（实证调研）**：
```bash
# AWS Nitro
lsblk -o NAME,MODEL,SERIAL | grep nvme
# → nvme1n1  Amazon Elastic Block Store  vol0xxxxxxx

# GCP
lsblk -o NAME,MODEL,SERIAL | grep -v loop
# → sdb  PersistentDisk  google-pd-ssd-xxxxx
# 或 NVMe local SSD:
# → nvme0n1  nvme_card  google-local-nvme-ssd-0
# 推荐设备识别：通过 /dev/disk/by-id/google-* 符号链接（强稳定）
ls -l /dev/disk/by-id/google-*
```

**联动**：
- **→ CP-3.1**：device_header 列名是 CSV header 一部分，本文件 L144 字段名改造 = unified_monitor.sh L1922 字段名改造
- **→ CP-5.1**：device_manager.py 必然按字面量解析 `*_aws_standard_iops` 字段名

#### CP-3.5.b block_height_monitor.sh（452 行）

**风险等级**：⚠️ Phase 8a-v0.5 HI-1 标记 — 此文件是 cache 读端**不是** RPC writer

**关键说明**：
```
本文件 (block_height_monitor.sh) 角色：cache READER
  - L162  read_cached_block_height_data    →  从 BLOCK_HEIGHT_CACHE_FILE 读 JSON
  - L289  L293-298  同样读 cache（CLI 模式）
  - L443-446  写 data_loss_stats.json 输出（这是 STATS writer，不是 height writer）

真正的 RPC writer 待 R 期定位 ⚠️：
  - 候选位置：core/common_functions.sh::get_cached_block_height_data() 
    （被 L162 L289 call，可能内部 fork RPC fetcher daemon）
  - 引用 TRACKER §13.1 标记此为悬空依赖
```

**改造点清单**：

| # | 改造点 | 实证 file:line | 等级 |
|---|---|---|---|
| 1 | RPC URL 平台分发：`LOCAL_RPC_URL` `MAINNET_RPC_URL` 默认值（如果在本文件设默认）→ GCP 上 Solana mainnet RPC 端点可能用 GCP 友好的 region endpoint | 待 R 期定位 ⚠️（grep 无命中，可能在 config 层） | P2 |
| 2 | `data_loss_stats.json` 输出 4 个 key（L443-446）`data_loss_count` `data_loss_periods` `total_duration` + 1 个 timestamp/marker — 这是 **[CROSS-PROC-CONTRACT P0]** 与 report_generator.py L3598 `_generate_data_loss_stats_section` 的强契约，键名不能改 | block_height_monitor.sh:443-446 ✓ → report_generator.py:3620,3627,3631 ✓ | P0 |
| 3 | `curl` 二进制依赖检查（L128）GCP 上一致可用 | block_height_monitor.sh:128 ✓ | P3 |
| 4 | CSV 数据行格式（L173 L389）`timestamp,local_block_height,mainnet_block_height,block_height_diff,local_health,mainnet_health,data_loss` — 字段名中立无需改 | block_height_monitor.sh:173,389 ✓ | — |

**[CROSS-PROC-CONTRACT P0] 详细契约**：
```python
# visualization/report_generator.py:3598-3635 (实证)
def _generate_data_loss_stats_section(self):
    # 读 data_loss_stats.json
    # L3620: avg_duration = stats_data['total_duration'] / stats_data['data_loss_periods']
    # L3627: stats_data['data_loss_count']
    # L3631: stats_data['data_loss_periods']
    # 4 个 JSON key 严格依赖 block_height_monitor.sh:443-446 输出
```

**联动**：
- **→ CP-5.2**：report_generator.py L3598 强契约，4 key 不能改名
- **→ CP-3.4**：block_height_monitor 是 monitoring_coordinator MONITOR_TASKS 之一
- **→ TRACKER §13.1**：真正的 RPC writer 待 R 期定位（HI-1 悬空依赖）

#### CP-3.5.c unified_event_manager.sh（277 行）

**风险等级**：🟢 P2 低 — 事件 schema 字段命名中立

| # | 改造点 | 实证 file:line | 等级 |
|---|---|---|---|
| 1 | `event_type` 注释（L36）含 `ebs_bottleneck` 字面量；CLI 帮助文本 L262 `"ebs_bottleneck           EBS performance bottleneck"` — 加 `disk_bottleneck` alias | unified_event_manager.sh:36,262 ✓ | P2 |
| 2 | JSON 写入字段 `event_type` `event_source` `event_id` 字段名本身中立，无需改 | unified_event_manager.sh:58,140,161 ✓ | — |
| 3 | event_source 注释（L37）`block_height_monitor, unified_monitor, bottleneck_detector` — 字面量需在 GCP 上保持兼容（不改源名，加可选 nic_network_monitor） | unified_event_manager.sh:37 ✓ | P3 |

**联动**：
- **→ CP-3.3**：bottleneck_detector 是 event_source 之一，event_type alias 必须双向
- **→ CP-5.x**：消费 event JSON 的 analysis 层需同步识别 disk_bottleneck

#### 🆕 待回灌 TRACKER §13.X
- **🆕 隐藏问题 #6 §13.11 路径 suffix**：block_height_monitor.sh:44-45 `rm -f "$MEMORY_SHARE_DIR"/block_height_monitor_cache.json` — GCP 多实例并行时 MEMORY_SHARE_DIR 必须平台后缀隔离
  ```bash
  MEMORY_SHARE_DIR="${MEMORY_SHARE_DIR_BASE}-${CLOUD_PROVIDER}"   # 多实例隔离，CLOUD_PROVIDER 在 config_loader detect 后已保证三态 (aws|gcp|other)
  # 注：这里是路径拼接场景，直接使用 detect 后的 CLOUD_PROVIDER 变量本身，不是调 getter 分发，不违反 E1+ 定义
  ```
- **🆕 隐藏问题 #7 §13.12 — ✅ E1+ absorbed**：iostat_collector.sh:144 `${prefix}_aws_standard_iops` 字段名硬编码 → 改 `${prefix}_$(get_disk_field_prefix)_iops` 动态拼接（与 §13.6 unified_monitor.sh 同源消除，下游 device_manager.py / report_generator.py 全链路一致）

---

### CP-3.X E1+ 平台对等性强化 + §13.6/§13.12 结构性消除

本节统一登记 CP-3 monitoring/ 层在 Phase E-3 Batch B 任务 1 内完成的 4 项 E1+ absorbed 改造，作为后续 CP-4/CP-5 reader 端对应消费方的契约依据。

1. **CP-3.2 nic dispatch case 改能力判定**：原 `case "$CLOUD_PROVIDER" in aws) … gcp) …` 按平台名分发，现改按 `$(get_nic_driver)` 返 driver 标识 (ena|gvnic|generic) + `$(get_nic_allowance_fields)` 是否非空判定能力。AWS/GCP/Other 走同一统一函数入口（`get_nic_network_stats` / `get_nic_allowance_data`），平台对等
2. **§13.6 unified_monitor.sh `_aws_standard_*` 硬编码 → ✅ E1+ absorbed**：writer 端 CSV header 全改 `${prefix}_$(get_disk_field_prefix)_iops` / `${prefix}_$(get_disk_field_prefix)_throughput_mibs` 动态拼接，字面量 "aws_standard" 结构性消除
3. **§13.12 iostat_collector.sh L144 `_aws_standard_*` 上游源头 → ✅ E1+ absorbed**：同上 getter 拼接，AWS 返 `aws_standard` / GCP 返 `baseline` / Other 返 `standard`，writer 端唯一改造点同时消除 unified_monitor.sh 下游字段名继承
4. **§13.10/§13.11 路径 suffix**：保留 `LOGS_DIR-${CLOUD_PROVIDER}` / `MEMORY_SHARE_DIR-${CLOUD_PROVIDER}` 直接拼接（多实例隔离 fix），这里 CLOUD_PROVIDER 是 detect 后的变量本身、不是调 getter 分发，**不违反 E1+ 定义**

**验证场景**（CP-3 阶段验证里的 readiness check）：
- AWS 实例：CSV header 必含 `data_aws_standard_iops`；同主机 GCP 实例 `LOGS_DIR-aws` 与 `LOGS_DIR-gcp` 隔离不冲突
- GCP 实例：CSV header 必含 `data_baseline_iops`；`LOGS_DIR-gcp` 独立目录
- Other 实例（fallback）：CSV header 必含 `data_standard_iops`（绝不出现 aws_standard 字面量）；`LOGS_DIR-other` 独立目录
- 三平台 `get_nic_network_stats` / `get_nic_allowance_data` 统一函数入口，下游 reader（device_manager.py / report_generator.py）按 `get_disk_field_prefix()` 推导列名，与 writer 严格对齐

---

## CP-3 阶段验证

```bash
# 业务代码 zero diff
cd /usr/local/google/home/lelandgong/blockchain-node-benchmark
git diff --stat e843571 -- monitoring/
# 期望：空（所有改造都在 utils/ + config/ 层完成）

git diff --stat e843571 -- ':!analysis-notes'
# 期望：空
```

## CP-3 阶段产出依赖（执行顺序）
1. CP-1 utils 层完成（platform_dispatcher.sh, nic_metrics.sh, metric_emitter.sh）
2. CP-2 config 层完成（CLOUD_PROVIDER 注入, BOTTLENECK_DISK_* alias, MONITORING_PROCESS_NAMES_STR override）
3. CP-3 本阶段：新增 monitoring/nic_network_monitor.sh **唯一新文件**（其余 7 个 .sh 业务字节零改动，全部依赖上面两层透明分发）

---

## CP-4：tools/ 层（6 改）

**总览**（commit `e843571` 全文件 grep 实证）：

| 文件 | 行数 | AWS 字面密度 | P0/P1 阻塞 | 主要改造方向 |
|------|------|-------------|-----------|------------|
| tools/ebs_analyzer.sh | 161 | 11 处（全命名残留）| 0 / 0 | 命名中立化 + env 双写 |
| tools/ebs_bottleneck_detector.sh | 678 | 30+ 处（含字段消费 `aws_standard_iops/throughput`）| 0 / 6 | env 双写 + CSV 字段读时归一化 + 平台阈值表 |
| tools/benchmark_archiver.sh | 689 | **0 AWS 字面** | 0 / 0 | 归档目录命名注入 PLATFORM_DISPLAY_NAME（前向兼容）|
| tools/framework_data_quality_checker.sh | 701 | 4 处（CSV header 字面 + 日志 glob）| 0 / 2 | header 双写 + sanity check 加 GCP 等价 |
| tools/target_generator.sh | 382 | **0 AWS 字面** + 8 链对称 | 0 / 0 | 仅文案中立化 + usage 行 |
| tools/fetch_active_accounts.py | 841 | **0 boto3 / 0 metadata** | 0 / 0 | 文案中立化 + 输出 JSON key 复查 |

**关键约束**：
- 业务代码 commit `e843571` 不动（本 CP-4 patch 只触 CORRECTED_PLAN.md / TRACKER）
- 6 文件中 3 个（archiver / target_generator / fetch_active_accounts）**完全无 AWS API 依赖**，迁移友好性极高
- `BOTTLENECK_EBS_*_THRESHOLD` env 是跨 CP 重灾区，CP-4.1 / CP-4.2 / CP-3.3 / CP-5.1 / CP-5.2 / CP-2.4 全部依赖此 env 名空间，统一在 CP-2.4 alias 收口

---

### CP-4.1 tools/ebs_analyzer.sh → tools/disk_analyzer.sh

**当前状态**（commit `e843571`, 161 行）：
- 唯一调用方：`blockchain_node_benchmark.sh:478` bash spawn（grep 实证 0 source 引用，0 函数级跨文件调用）
- `grep -cE "AWS|aws|EBS|ebs" tools/ebs_analyzer.sh` = **11**（与 file-notes 6.1 节实证数完全一致）
- 0 个 AWS API 调用、0 个 metadata 调用、0 个 nvme-cli / aws-cli 引用
- 消费 8 个 CSV 字段（`data_${LEDGER_DEVICE}_util/total_iops/total_throughput_mibs/avg_await` ×2 设备），全部 OS-level 中立词
- 产出 8 个 `log_performance` metric（写日志行非 CSV/JSON，grep 实证 0 程序化下游）

**改造矩阵**：

| # | 类别 | file:line | 改造前 | 改造后 | 等级 | 联动 |
|---|------|-----------|--------|--------|------|------|
| 1 | 文件重命名 | `tools/ebs_analyzer.sh` | 文件名 | `tools/disk_analyzer.sh`（git mv 保 history） | P2 | CP-4.3 archive 文件名引用；`blockchain_node_benchmark.sh:478` 调用方 |
| 2 | logger ID + log 文件 | L16 | `init_logger "ebs_analyzer" $LOG_LEVEL "${LOGS_DIR}/ebs_analyzer.log"` | `init_logger "disk_analyzer" $LOG_LEVEL "${LOGS_DIR}/disk_analyzer.log"` | P2 | CP-4.4 L438 `for log_pattern in "ebs_analyzer.log" ...` 必须同步加 `"disk_analyzer.log"` |
| 3 | 函数名 | L19, L156 | `analyze_ebs_performance()` | `analyze_disk_performance()` | P2 | 0 外部 caller（grep 实证），无需 alias |
| 4 | env 读取 | L116 | `${BOTTLENECK_EBS_UTIL_THRESHOLD:-90}` | `${BOTTLENECK_DISK_UTIL_THRESHOLD:-${BOTTLENECK_EBS_UTIL_THRESHOLD:-90}}` 双写 | P2 | **CP-2.4** 在 `config/internal_config.sh:17` 定义新 env 并 export；CP-3.3 `monitoring/bottleneck_detector.sh:298,1207` 同步双写 |
| 5 | env 读取 | L122 | `${BOTTLENECK_EBS_LATENCY_THRESHOLD:-50}` | `${BOTTLENECK_DISK_LATENCY_THRESHOLD:-${BOTTLENECK_EBS_LATENCY_THRESHOLD:-50}}` | P2 | 同上，CP-2.4 + CP-3.3 联动 |
| 6 | 注释/log 文案 | L3, L18, L27, L89, L142, L150 | `EBS` 字面 6 处 | `disk` / `storage` 中立词 | P3 | 纯文案 |

**CSV 字段消费契约**（跨 CP 双向链接）：
- 上游写方：`monitoring/unified_monitor.sh` `generate_csv_header` (L1920) → CP-3.1 #1
- header 定义方：`tools/framework_data_quality_checker.sh:352-358` → CP-4.4 #1
- 同款消费方：`tools/ebs_bottleneck_detector.sh:166-179` → CP-4.2 #2
- **本文件 case 模板 `data_${LEDGER_DEVICE}_util` 等 4 字段**：若 CP-1.1 utils/disk_converter.sh 输出仍保 `data_${LEDGER_DEVICE}_*` 老 prefix，本文件 L44-L47 / L63-L66 case **无需改**；若上游加 `cloud_` / `disk_` prefix，case 必须同步增列

**验证命令**：
```bash
# (a) AWS 字面剩余必须 ≤ 0
grep -cE "AWS|aws|EBS|ebs" tools/disk_analyzer.sh    # 期望 0
# (b) 旧 env 兼容（不设新 env 跑老路径）
unset BOTTLENECK_DISK_UTIL_THRESHOLD
BOTTLENECK_EBS_UTIL_THRESHOLD=85 bash tools/disk_analyzer.sh /tmp/test.csv 2>&1 | grep -q "85" && echo "alias OK"
# (c) 调用方同步
grep -nE "ebs_analyzer|disk_analyzer" blockchain_node_benchmark.sh   # 必须只出现 disk_analyzer
```

---

### CP-4.2 tools/ebs_bottleneck_detector.sh → tools/disk_bottleneck_detector.sh

**当前状态**（commit `e843571`, 678 行）：与 CP-3.3 `monitoring/bottleneck_detector.sh` 的本质区别（grep 实证）：
- 本文件（`tools/`）= **producer-consumer 高频独立采集器**，从 iostat 间接 CSV 读 EBS 字段做 IOPS/Throughput/Latency 阻塞检测，输出到独立 log + JSON
- CP-3.3 `monitoring/bottleneck_detector.sh` = **集成在 unified_monitor 里的综合阻塞协调器**，消费多源指标（CPU/Mem/EBS/Net）+ 写 `bottleneck_status.json` 给 QPS executor 反馈
- 关键：`start_ebs_monitoring_for_qps_test()` (L577) 是被 `master_qps_executor.sh` spawn 的入口，**与 monitoring/bottleneck_detector.sh 互不调用**

**改造矩阵**：

| # | 类别 | file:line | 改造前 | 改造后 | 等级 | 联动 |
|---|------|-----------|--------|--------|------|------|
| 1 | 文件重命名 | 整文件 | `ebs_bottleneck_detector.sh` | `disk_bottleneck_detector.sh` | P2 | `monitoring/monitoring_coordinator.sh` MONITOR_TASKS 键 `ebs_bottleneck` → `disk_bottleneck` （CP-3.4 #2 已列）；`master_qps_executor.sh` spawn 命令 |
| 2 | 关联函数 source | L16 | `source ".../utils/ebs_converter.sh"` | `source ".../utils/disk_converter.sh"`（CP-1.1 重命名后）| P2 | **CP-1.1** utils/ebs_converter.sh → utils/disk_converter.sh |
| 3 | env 读取 | L21-L22, L25-L26, L397-L398, L416-L417, L429 | `${BOTTLENECK_EBS_IOPS_THRESHOLD:-90}` / `_THROUGHPUT_` / `_LATENCY_` | 三套双写：`${BOTTLENECK_DISK_IOPS_THRESHOLD:-${BOTTLENECK_EBS_IOPS_THRESHOLD:-90}}` | P1 | **CP-2.4** + **CP-3.3**（同 env 跨文件消费方共 19 处，见 file-notes 6.6） |
| 4 | CSV 字段消费 | L135-L136, L143-L144, L151-L152, L156-L157 | `aws_standard_iops` / `aws_standard_throughput_mibs` 硬字段名 | 通过 **utils/field_normalizer**（CP-1.2 新增）读时归一化：`${prefix}_baseline_iops` / `_baseline_throughput_mibs` 中立别名 + 老字段兜底 | P1 | CP-1.2 新增 utils/field_normalizer.sh；CP-3.1 #4 上游 CSV 也加新字段双写；CP-4.4 #1 header 同步 |
| 5 | required_fields 列表 | L168-L169, L178-L179 | `required_fields+=("data_${LEDGER_DEVICE}_aws_standard_iops")` ×4 | 加入新字段名 + 保留老字段名做 OR 校验（任一存在即通过） | P1 | CP-4.4 #1 同步 |
| 6 | 函数 + log 中文案 | L33-L34, L107-L108, L370, L449, L468, L473, L507, L514, L566, L576-L577, L586 | `EBS` 字面 + `init_ebs_limits` / `get_ebs_data_from_csv` / `detect_ebs_bottleneck` / `start_ebs_monitoring_for_qps_test` 函数名 | 内部函数重命名为 `init_disk_limits` / `get_disk_data_from_csv` / `detect_disk_bottleneck` / `start_disk_monitoring_for_qps_test`；调用方 `master_qps_executor.sh` 同步 | P1 |
| 7 | 阈值表平台分发（E1+ 能力判定）| L33-L34 `init_ebs_limits` | 当前从 utils/ebs_converter.sh 读 AWS gp3/io2 baseline 表 | **E1+ 能力判定**（取消 `case "$CLOUD_PROVIDER"` 平台分发）：`local disk_types="$(get_disk_type_options)"` → `init_disk_limits "$disk_types"`；函数内部按 disk_type 字面（gp3/io2/pd-ssd/pd-balanced/pd-extreme/hyperdisk-extreme/local-ssd…）查表，不再问"哪个云"，新增 provider 只需在 provider.sh `get_disk_type_options` 返回新列表 + 在阈值表加新行，本文件零改 | P1 | CP-0.2（`get_disk_type_options` getter）、CP-1.1（`utils/disk_converter.sh` 内阈值表按 disk_type dispatch）|

**🆕 新挖隐藏问题**（commit `e843571` 实证）：
- ⚠️ **L156 输出契约 7-tuple 包含 `aws_standard_iops, aws_standard_throughput`** 作为位置参数（不是 keyed JSON），下游 L264, L301 用 `IFS=',' read -r ... aws_standard_iops aws_standard_throughput ...` 解 — 改字段名时**位置不变即可**，但 7-tuple 第 3/4 位语义如改为 `baseline_iops/throughput` 需在 L264, L301 同步重命名局部变量
- ⚠️ **L449 console 输出 `"⚠️ [HH:MM:SS] EBS BOTTLENECK DETECTED: $device - $bottleneck_type"` 是用户可见告警**，CP-5.2 report_generator 若 grep 这条 console 行做关联，会断链（grep 实证：未发现 report_generator 消费此字面，但 monitoring/log 聚合脚本需复查）
- **🆕 待回灌 TRACKER §13.1**

---

### CP-4.3 tools/benchmark_archiver.sh ⭐ 重点

**当前状态**（commit `e843571`, 689 行）：
- `grep -cE "AWS|aws|EBS|ebs|nitro|EC2|ec2|gcp" tools/benchmark_archiver.sh` = **0**（zero AWS 字面）
- 唯一 platform-相关数据：归档目录命名 `run_${run_number}_${timestamp}`（L219）— 不含 platform 标识
- 写文件：`${ARCHIVES_DIR}/${run_id}/test_summary.json` (L102), `${DATA_DIR}/test_history.json` (L16)
- 不调用 `monitoring_overhead_*.csv` glob 生成（那是 `monitoring/unified_monitor.sh` L1075 / L1767-L1801 / `visualization/performance_visualizer.py:151` 的范畴），但 archiver 会把 `${CURRENT_TEST_DIR}/logs/monitoring_overhead_*.csv` 整目录 `mv` 到 archive（L243 `mv "$CURRENT_TEST_DIR"/* "$archive_path/"`）

**🆕 关键洞察**：本文件**业务逻辑零 AWS 耦合**，但归档命名 + 历史索引 + `compare_tests` 是跨平台对比的关键入口，必须能区分 `aws_run_1_<ts>` vs `gcp_run_1_<ts>`，否则未来 AWS/GCP 双平台并行 benchmark 会撞 ID 或难以区分。

**改造矩阵 — 两方案对比**：

| 维度 | 方案 A：前缀注入 `<platform>_run_${n}_${ts}` | 方案 B：platform 子目录 `${ARCHIVES_DIR}/${platform}/run_${n}_${ts}` |
|------|---------------------------------------------|-------------------------------------------------------------------|
| 改造点 | L219 `local run_id="run_${run_number}_${timestamp}"` → `local run_id="${PLATFORM_DISPLAY_NAME:-run}_${run_number}_${timestamp}"`（1 行）| L101, L236, L314-L315 `ARCHIVES_DIR/${run_id}` → `${ARCHIVES_DIR}/${PLATFORM_DISPLAY_NAME}/${run_id}`（4 处）|
| 历史 JSON 兼容 | test_history.json 现有 `run_id` 字段仍唯一 + 加 `platform` 字段 | test_history.json 需按 platform 分文件或加 `platform` 字段 |
| `--compare` 跨平台 | `--compare aws_run_5_<ts> gcp_run_5_<ts>` 自然支持 | 需 `--compare aws/run_5 gcp/run_5`（路径分隔符歧义） |
| 前向兼容（老归档目录名） | 老目录 `run_5_<ts>` 仍可正常 list/compare（不带 platform = 默认 aws） | 需迁移脚本把老目录移到 `aws/` 子目录 |
| `du` / `find` 等运维命令 | 一切照旧 | 用户需多一层 `${platform}/` 才能 ls |
| 实施难度 | ⭐（1 行 + summary JSON 加 1 字段）| ⭐⭐⭐（4 处目录路径 + 历史 JSON 结构迁移 + compare 解析）|
| 与 monitoring_overhead 文件命名一致性 | ✅ 与 `monitoring_overhead_<platform>_*.csv` 风格一致（CP-3.1 输出文件名约定）| ❌ |

**推荐：方案 A（前缀注入）**

**改造矩阵**：

| # | 类别 | file:line | 改造前 | 改造后 | 等级 | 联动 |
|---|------|-----------|--------|--------|------|------|
| 1 | 归档目录命名（E1+ 单源 getter）| L219 | `local run_id="run_${run_number}_${timestamp}"` | **E1+ 单源 getter**（取消 `${PLATFORM_DISPLAY_NAME:-${CLOUD_PROVIDER:-run}}` 双 fallback 反模式）：`local run_id="$(get_archive_dir_prefix)run_${run_number}_${timestamp}"`；AWS provider 返 `aws_`、GCP provider 返 `gcp_`、Other provider 中立化返 `""`（即最终目录 `run_<n>_<ts>`，与老归档前向兼容）；新增 provider 只需在新 provider.sh 实现 `get_archive_dir_prefix`，本文件零改 | P2 | CP-0.1（`get_archive_dir_prefix` getter + other_provider.sh 中立返回 `""`）；CP-5.2 report_generator glob pattern 同步 → §13.18 / §13.19 reader 端依赖 |
| 2 | test_summary.json 加 platform 字段 | L133-L158 cat heredoc | 当前 JSON 16 字段 | 新增 `"platform": "${PLATFORM_DISPLAY_NAME:-unknown}"`, `"platform_metadata": {"cloud_provider": "...", "instance_type": "...", "region": "..."}` | P2 | CP-2.1 config/cloud_provider.sh 提供 metadata；CP-5.2 report_generator 可读此字段做平台标签渲染 |
| 3 | test_history.json schema | L173-L179 init + L184-L196 jq update | 当前 `.tests[]` entry: {run_id, benchmark_mode, max_qps, status, archived_at} | entry 加 `platform` 字段 | P2 | 老 history 文件 backward compat：jq 读取时 `// "unknown"` |
| 4 | --compare 跨平台标签 | L344-L358 printf 表头 | `printf "%-30s %-15s %-15s\n" "Metric" "$run1" "$run2"` | 显示行加 `platform` 行：`printf "%-30s %-15s %-15s\n" "Platform" "$(jq -r .platform $summary1)" "$(jq -r .platform $summary2)"` | P3 | 仅 UX 增强 |
| 5 | list_test_history 输出格式 | L293 jq -r '.tests[] | "🔹 \(.run_id) | Mode: ..."' | 加 ` | Platform: \(.platform // "n/a")` | P3 | UX |
| 6 | 共享内存文件命名 | L34, L43, L49 引用 `data_loss_stats.json` / `bottleneck_status.json` / `qps_status.json` | 当前文件名平台中立 | **无需改**（命名已中立，内容若加 platform key 由 CP-3.3 / CP-3.1 完成）| - | CP-3.1 |

**🆕 新挖隐藏问题**（commit `e843571` 实证）：
- ⚠️ **L243 `mv "$CURRENT_TEST_DIR"/* "$archive_path/"`** 把整个 logs/reports/vegeta_results 目录批量迁移。若 CP-3.1 引入 `monitoring_overhead_<platform>_*.csv` 文件命名（Phase 7.5 阻塞点 #2），archiver 无需改动（glob `*` 通吃），但 `du -sm "${archive_path}/logs"` (L115) 统计行不变 — **兼容性 OK** ✅
- ⚠️ **L362-L363 `compare_tests` 输出 `start_time / end_time` 用 `jq -r '.start_time'`** — 若 CP-2.1 给 test_summary 加了时区敏感的 timestamp（GCP 默认 UTC vs AWS region-local），跨平台对比的时间显示会失真。建议在 #2 同时加 `"timezone": "UTC"` 字段强制 UTC
- ⚠️ **L102 `summary_file="${archive_path}/test_summary.json"` 文件名平台中立**，但其中 `bottleneck_summary` (L144) 字段值来自 `monitoring/bottleneck_detector.sh` `bottleneck_types` 数组（CP-3.3 #2 改 `ebs_*` → `disk_*`）— **若 CP-3.3 不双写，老归档的 `bottleneck_summary` 字段值会有 `ebs_` 前缀，新归档有 `disk_` 前缀**，跨版本对比断链
- **🆕 待回灌 TRACKER §13.2**

**验证命令**：
```bash
# (a) 归档目录命名带 platform 前缀
CLOUD_PROVIDER=gcp PLATFORM_DISPLAY_NAME=gcp bash tools/benchmark_archiver.sh --archive --benchmark-mode standard --max-qps 1000
ls "${DATA_DIR}/archives/" | grep -qE "^gcp_run_[0-9]+_" && echo "platform-aware naming OK"
# (b) summary 含 platform 字段
jq -r '.platform' "${DATA_DIR}/archives/gcp_run_*_*/test_summary.json" | grep -q gcp && echo "summary platform field OK"
# (c) 老归档兼容
[[ -d "${DATA_DIR}/archives/run_old_20251201_120000" ]] && bash tools/benchmark_archiver.sh --list | grep -q "run_old" && echo "backward compat OK"
```

---

### CP-4.4 tools/framework_data_quality_checker.sh

**当前状态**（commit `e843571`, 701 行）：
- `grep -cE "AWS|aws|EBS|ebs" tools/framework_data_quality_checker.sh` = 4（L352, L356, L358 CSV header 字面 + L438 日志 glob）
- L352 / L356 / L358 是 **CSV header 字符串模板定义方**（DATA / ACCOUNTS / ACCOUNTS-only 三场景），含 `_aws_standard_iops` / `_aws_standard_throughput_mibs` 字段名
- L427 `find "$logs_dir" -name "monitoring_overhead_*.csv"` 是关键 glob，与 `visualization/performance_visualizer.py:151` 同 pattern（**Phase 7.5 阻塞点 #2 直接关联**）
- L438 日志文件硬编码列表 `"ebs_bottleneck_detector.log" "ebs_analyzer.log" ...`

**改造矩阵**：

| # | 类别 | file:line | 改造前 | 改造后 | 等级 | 联动 |
|---|------|-----------|--------|--------|------|------|
| 1 | CSV header 字段名 | L352, L356, L358 | `data_${LEDGER_DEVICE}_aws_standard_iops`, `_aws_standard_throughput_mibs` ×2 设备 ×3 场景 | 双写：`data_${LEDGER_DEVICE}_aws_standard_iops`（保留兼容）+ `data_${LEDGER_DEVICE}_baseline_iops`（中立新名）；GCP-only 模式可只生成新名 | P1 | **CP-3.1 #1** unified_monitor.sh 写 CSV header 必须同步；**CP-4.2 #4** 消费方 read 时归一化；**CP-5.1** device_manager.py field_mappings 同步 |
| 2 | 日志文件 glob | L438 | `for log_pattern in "ebs_bottleneck_detector.log" "ebs_analyzer.log" ...` | 列表加入 `"disk_bottleneck_detector.log" "disk_analyzer.log"` 双名 | P1 | **CP-4.1 #2** / **CP-4.2 #1** logger 文件名同步 |
| 3 | monitoring_overhead glob | L427 | `find "$logs_dir" -name "monitoring_overhead_*.csv"` | 若 CP-3.1 改为 `monitoring_overhead_<platform>_*.csv`，本行 glob `monitoring_overhead_*.csv` **仍能匹配**（前向兼容 OK）✅ | - | Phase 7.5 阻塞点 #2 — **本行无需改动**，但需做集成测试确认 glob 兼容 |
| 4 | sanity check 字段集（E1+ getter 动态拼接）| L350 附近（CSV header 构造完成后）| 当前只校验字段数 + 字段名 | **E1+ getter 动态拼接**（取消 `case "$CLOUD_PROVIDER"` 平台分发，与 §13.6/§13.12 writer 端单源）：`local field_prefix="$(get_disk_field_prefix)"` → `REQUIRED_FIELDS="data_${LEDGER_DEVICE}_${field_prefix}_iops,data_${LEDGER_DEVICE}_${field_prefix}_throughput_mibs"`；AWS 自动得 `data_<dev>_aws_standard_iops`、GCP 自动得 `data_<dev>_baseline_iops`、Other 自动得 `data_<dev>_standard_iops`；新增 provider 只需在 provider.sh `get_disk_field_prefix` 返回新前缀，本文件零改 | P2 | CP-0.1（`get_disk_field_prefix` getter）、CP-3.1 #1（writer 端同源拼接）|
| 5 | ENA 字段动态检测 | L372-L386 | `if [[ "$ENA_MONITOR_ENABLED" == "true" ]]` 读 `ENA_ALLOWANCE_FIELDS_STR` | platform-aware：aws → ENA 路径不变；gcp → 跳过（GCP gVNIC 无 allowance 概念）或读 `GVNIC_FIELDS_STR` | P2 | **CP-3.2** monitoring/ena_network_monitor.sh → nic_network_monitor.sh（GCP 分支） |
| 6 | log echo 文案 | L603 `echo "ENA monitoring: $ENA_MONITOR_ENABLED"` 等 | platform-aware 显示名：`echo "NIC monitoring (${NIC_TYPE:-ena}): ..."` | P3 | 纯文案 |

**🆕 新挖隐藏问题**（commit `e843571` 实证）：
- ⚠️ **L352 / L356 / L358 三处 21-字段 header 模板完全重复**（DRY 违反），任何字段名改动需 3 处同步 — 这是 commit `e843571` 已存在的技术债。CP-4.4 改造时应顺手抽函数 `generate_device_header(device_prefix, device_name)` 但**保 commit 不动原则下不抽**，仅在 patch comment 标注
- ⚠️ **L427 glob `monitoring_overhead_*.csv` 是 Phase 7.5 五阻塞点之一的下游消费方**（与 `visualization/performance_visualizer.py:151` 同 pattern）— 若 CP-3.1 的 writer 改文件名 prefix 但 glob 仍兼容，本行**零改动**；若 writer 改为 `<platform>_monitoring_overhead_*.csv`（前置 prefix），glob `monitoring_overhead_*` 会**漏匹配** → 必须改 glob 为 `*monitoring_overhead*.csv`
- **🆕 待回灌 TRACKER §13.3**

---

### CP-4.5 tools/target_generator.sh

**当前状态**（commit `e843571`, 382 行）：
- `grep -cE "AWS|aws|EBS|ebs|EC2|ec2|nitro|metadata|boto3|169\\.254" tools/target_generator.sh` = **0**
- 8 链对称已完整实现（L59 usage 行实证 `solana, ethereum, bsc, base, polygon, scroll, starknet, sui`）
- 输出 vegeta target 文件，与平台无关（仅 RPC URL + JSON-RPC body）
- 不调用任何 EC2/GCP metadata、不读 cloud-specific env

**改造矩阵**：

| # | 类别 | file:line | 改造前 | 改造后 | 等级 | 联动 |
|---|------|-----------|--------|--------|------|------|
| 1 | usage 文案 | L46-L62 | 描述行可能含 "EC2" 等字面（grep 实证 0 命中）| 无需改 | - | - |
| 2 | （预防性）输出文件命名 | L181 附近 `Set current output file based on RPC mode` | 当前与平台无关 | 无需改 | - | - |
| 3 | log message echo 文案 | L253 `echo "   Blockchain type: $BLOCKCHAIN_NODE" >&2` 等 | 已平台中立 | 无需改 | - | - |

**结论**：本文件**零改动**（commit `e843571` 已 platform-agnostic）。在 CP-4.5 仅做以下验证（无 patch）：

**验证命令**：
```bash
# 确认 0 AWS 字面
grep -cE "AWS|aws|EBS|ebs|EC2|ec2|nitro|metadata|boto3" tools/target_generator.sh    # 期望 0
# 确认 8 链对称
for chain in solana ethereum bsc base polygon scroll starknet sui; do
    BLOCKCHAIN_NODE=$chain bash tools/target_generator.sh --help 2>&1 | grep -q "$chain" || echo "FAIL: $chain"
done
```

**🆕 待回灌 TRACKER §13.4**：本文件作为「迁移豁免文件」案例，记录 8 链对称 + 0 AWS 耦合是迁移友好性满分典范。

---

### CP-4.6 tools/fetch_active_accounts.py

**当前状态**（commit `e843571`, 841 行）：
- `grep -cE "boto3|AWS|aws_|EC2|ec2|169\\.254|metadata\\.google|imdsv" tools/fetch_active_accounts.py` = **0**
- 唯一外部依赖：`aiohttp` (L28) — 通用 HTTP 客户端，无云 SDK
- L133 `session.post(url, json=payload, timeout=...)` — 通用 JSON-RPC POST
- L768 `aiohttp.TCPConnector(...)` + L775 `aiohttp.ClientSession(...)` — 通用连接池

**改造矩阵**：

| # | 类别 | file:line | 改造前 | 改造后 | 等级 | 联动 |
|---|------|-----------|--------|--------|------|------|
| 1 | AWS SDK 调用 | 全文件 | **0 处 boto3** | 无需改 | - | - |
| 2 | metadata 调用 | 全文件 | **0 处 169.254.169.254 / metadata.google.internal** | 无需改 | - | - |
| 3 | 输出 JSON key | 输出 accounts JSON | 当前 key 命名（如 `address`, `slot`, `lamports` 等区块链原生字段）| 已平台中立（区块链字段，非云字段）| - | - |
| 4 | log/console 文案 | L10 docstring `Async HTTP requests for improved performance` | 已中立 | - | - |
| 5 | 注释中"AWS / EC2" | 全文件 grep | **0 命中** | - | - | - |

**结论**：本文件**零改动**（commit `e843571` 已 platform-agnostic）。在 CP-4.6 仅做验证（无 patch）：

**验证命令**：
```bash
grep -cE "boto3|AWS|aws_|EC2|ec2|169\\.254|metadata\\.google|imdsv" tools/fetch_active_accounts.py   # 期望 0
python3 -c "import ast; ast.parse(open('tools/fetch_active_accounts.py').read())"   # 语法 OK
```

**🆕 待回灌 TRACKER §13.5**：本文件作为「Python 工具迁移豁免案例」，记录 0 boto3 + 0 metadata 调用是 Python 工具迁移友好性满分典范。

---

#### CP-4.X E1+ 平台对等性强化 + 归档命名单源（Phase E-3 Batch B 任务 2）

本节归集 CP-4 三处 `case "$CLOUD_PROVIDER"` / `${PLATFORM_DISPLAY_NAME:-${CLOUD_PROVIDER:-run}}` 残留改造，全部走 §0 §1.1 E1+ getter（能力判定 + 单源路径，绝不在 tools/ 层做平台分发）：

1. **CP-4.2 #7 阈值表**：`case "$CLOUD_PROVIDER"` 平台分发 → 能力判定。`init_disk_limits "$(get_disk_type_options)"`，按 disk_type 字面查表，新增 provider 只需在 provider.sh 返回新 disk_type 列表 + `utils/disk_converter.sh` 阈值表加新行。
2. **CP-4.4 #4 sanity check 字段集**：`case "$CLOUD_PROVIDER"` 选 `_aws_standard_iops` vs `_baseline_iops` → 动态 `data_${LEDGER_DEVICE}_$(get_disk_field_prefix)_iops`，与 §13.6 / §13.12 writer 端 (`unified_monitor.sh` / `iostat_collector.sh`) 同源 getter。完全消除 AWS bias。
3. **CP-4.3 #1 归档目录前缀**：`${PLATFORM_DISPLAY_NAME:-${CLOUD_PROVIDER:-run}}` 双 fallback 反模式 → 单源 `$(get_archive_dir_prefix)`。AWS 返 `aws_run_*` / GCP 返 `gcp_run_*` / Other provider 中立返 `""` → `run_*`（与老归档前向兼容，fallback 主动收口在 `config/cloud_provider/other_provider.sh`，本文件不允许 default-bias）。
4. **§13.18 report_generator glob pattern 隐性契约**：✅ **部分改善**（reader 端 `archives/{aws_run_*,gcp_run_*,run_*}` glob 依赖与本 archiver writer 同一 `get_archive_dir_prefix` getter 输出；完全消除两端字面 list 需 CP-5.2 同步把 glob 也改成 `$(get_archive_dir_prefix)run_*` 动态拼接 — 本任务只动 CP-4 archiver writer 端，CP-5 reader 端标记为"同源依赖"留 CP-5 任务实施）。
5. **§13.19 `run_*` basename 启发式解析**：✅ **部分改善**（同上，writer 端单源后，reader 端 `basename` 切 `_run_` 提平台标识只要拿 `$(get_archive_dir_prefix)` 反查即可恢复，CP-5 同步落地）。

**验证场景**（commit `e843571` zero-touch，仅 PLAN 内逻辑契约）：
| 场景 | get_disk_field_prefix | get_archive_dir_prefix | get_disk_type_options |
|------|----------------------|----------------------|----------------------|
| AWS  | `aws_standard`       | `aws_run_`           | `gp3 io2 instance-store` |
| GCP  | `baseline`           | `gcp_run_`           | `pd-balanced pd-ssd pd-extreme hyperdisk-extreme local-ssd` |
| Other| `standard`           | `run_` (即 prefix `""`+ `run_`，与老前缀同) | `""` (空集，未知平台不预设) |

→ archive 目录: AWS `aws_run_<n>_<ts>`、GCP `gcp_run_<n>_<ts>`、Other `run_<n>_<ts>`
→ sanity check 字段: AWS `data_<dev>_aws_standard_iops`、GCP `data_<dev>_baseline_iops`、Other `data_<dev>_standard_iops`
→ 阈值表: AWS dispatch gp3/io2 行、GCP dispatch pd-*/hyperdisk-* 行、Other 跳过校验（disk_types 空集 → init_disk_limits 退化）

**业务代码零改动证明**：本节仅修订 PLAN 中"改造后"列文本，commit `e843571` 业务代码不动。

---

**CP-4 总验证**（业务代码 zero diff 实证）：
```bash
cd /usr/local/google/home/lelandgong/blockchain-node-benchmark
# 期望：只有 analysis-notes/ 下的改动，业务代码 0 diff
git diff --stat e843571 -- ':!analysis-notes'
# 期望输出：(empty)
```

**CP-4 跨 CP 双向链接清单**：
- CP-4.1 → CP-1.1（utils/disk_converter.sh source 路径）、CP-2.4（env 双写定义）、CP-3.3（同 env 消费方）
- CP-4.2 → CP-1.1（utils/ebs_converter source）、CP-1.2（field_normalizer 新增）、CP-2.4（env）、CP-3.1（CSV writer 双写）、CP-3.3（互不调用但语义重叠需文档区分）、CP-3.4（MONITOR_TASKS key）、CP-4.4（header 同步）
- CP-4.3 → CP-2.1（PLATFORM_DISPLAY_NAME / metadata）、CP-3.1（monitoring_overhead 文件名兼容）、CP-3.3（bottleneck_summary 字段值同步）、CP-5.2（report 读 platform 字段）
- CP-4.4 → CP-2.1（CLOUD_PROVIDER）、CP-3.1（CSV writer）、CP-3.2（ENA → NIC）、CP-4.1/CP-4.2（logger 文件名）、CP-5.1（field_mappings 同步）
- CP-4.5 → 无（豁免）
- CP-4.6 → 无（豁免）

---

## CP-5：analysis/ + visualization/ 层（10 改）

> **依赖上游 (消费端契约)**：
> - **CP-1**：`config/cloud_provider.sh` 提供 `CLOUD_PROVIDER`；`utils/field_normalizer.py`（§10.5 草案）提供 `normalize_df()` 双名归一化
> - **CP-2**：`config/config_loader.sh:L102-128` 提供 `DEPLOYMENT_PLATFORM`；`config/internal_config.sh:L17-22` 暴露 `BOTTLENECK_EBS_*_THRESHOLD` + alias `BOTTLENECK_DISK_*_THRESHOLD`
> - **CP-3**：`monitoring/iostat_collector.sh:L127/L144` CSV 双写 `*_aws_standard_iops` + `*_disk_standard_iops`；`monitoring/ena_network_monitor.sh:L92-94` 双写 ENA 6 列；`monitoring/block_height_monitor.sh:L444-447` 写 `data_loss_stats.json` 4 key；`monitoring/unified_monitor.sh` 写 `monitoring_overhead_*.csv` 15 字段
> - **CP-4**：`tools/benchmark_archiver.sh` 归档 `monitoring_overhead_*.csv` glob 命名约定；`tools/ebs_bottleneck_detector.sh` 写 `bottleneck_status.json` top-level key（双写 `ebs_bottlenecks` + `disk_bottlenecks`）+ 日志文本契约 `EBS BOTTLENECK DETECTED` / `DISK BOTTLENECK DETECTED`
>
> **下游消费者 (CP-5 自身产出)**：HTML/PNG 报告 → 浏览器（无程序化下游）

---

### CP-5.1 visualization/device_manager.py（16 改造点矩阵）

**总字面密度**：grep `AWS|aws|EBS|ebs|ENA|ena_|nitro` = **36** 处（file-notes §6.1 实证）。**16 改造点**对应 file-notes §6.2 表格 11 项 + §6.5 工作量明细 5 项。

| # | file:line | 改造点 | 类别 | 等级 | 上游/下游联动 |
|---|-----------|--------|------|------|---------------|
| 1 | L26 `'data_aws_standard_iops': r'data_.*_aws_standard_iops'` | patterns 字典键 + regex 双写 | 字段契约 | **P1** | 上游 CP-3 iostat_collector L127 写方；下游 6 reader（ebs_chart_generator/performance_visualizer/advanced_chart/report_generator/comprehensive_analysis/cpu_ebs_correlation） |
| 2 | L27 `'data_aws_standard_throughput_mibs'` 同上 | 同 #1 | 字段契约 | **P1** | 同 #1 |
| 3 | L41-42 `accounts_aws_standard_*` 同 #1/#2 | accounts 版本 | 字段契约 | **P1** | 同 #1 |
| 4 | L81-85 `ena_bw_in_allowance_exceeded` / `ena_bw_out_allowance_exceeded` / `ena_pps_allowance_exceeded` / `ena_conntrack_allowance_available` / `ena_conntrack_allowance_exceeded` 5 个 patterns | 平台分发：GCP 模式可空（regex 不命中返 None） | 字段契约 | P2 | 上游 CP-3 ena_network_monitor 写方；GCP 经 ENAFieldAccessor 已抽象 |
| 5 | L254 `os.getenv('BOTTLENECK_EBS_UTIL_THRESHOLD', '90')` | env 双名 alias | env 契约 | **P1** | 上游 CP-2 internal_config.sh:L17 同步 alias |
| 6 | L255 `BOTTLENECK_EBS_LATENCY_THRESHOLD` | 同 #5 | env 契约 | **P1** | 同 #5 |
| 7 | L256 `BOTTLENECK_EBS_IOPS_THRESHOLD` | 同 #5 | env 契约 | **P1** | 同 #5 |
| 8 | L257 `BOTTLENECK_EBS_THROUGHPUT_THRESHOLD` | 同 #5 | env 契约 | **P1** | 同 #5 |
| 9 | L260-261 `ebs_util_warning` / `ebs_latency_warning` 派生（同 4 env 再读）| 同 #5-#8 | env 契约 | **P1** | 同 #5 |
| 10 | L301-302/L306-308 局部变量 `ebs_latency_threshold` / `ebs_util_threshold` + 注释 EBS 字面 | 局部重命名 → `disk_*_threshold` | 局部命名 | P3 | 0 外部下游，可直改 |
| 11 | L347-348 `all_suffixes` 含 `'aws_standard_iops'/'aws_standard_throughput_mibs'` | list 元素双写 | 字段契约 | **P1** | 与 #1 同步 |
| 12 | L420-421 `device_map = {'aws_standard_iops': 'AWS Standard IOPS', 'aws_standard_throughput': 'AWS Standard Throughput'}` | 显示标签 platform-aware | UI 字面 | P2 | HTML chart label 唯一来源（无外部消费）|
| 13 | L493/L500 `data_fields = ['data_aws_standard_iops', ...]` / `accounts_fields` | validate_ebs_configuration 字段清单双写 | 字段契约 | **P1** | 与 #1 同步（否则 validate 永远 fail）|
| 14 | L201-218 `_check_device_data_exists` (18 行) | 删死方法 | 死代码 | P3 | grep 0 调用方（file-notes §6.5）|
| 15 | L284-293 `get_qps_display_value` (10 行，与 L432 重复) | 删重复方法 | 死代码 | P3 | 保留 L432 |
| 16 | L21/L36/L75/L116/L339/L342/L484 注释 `# EBS DATA fields` / "Validate EBS configuration" 等 | 注释 EBS → block device | 注释 | P3 | 影响零 |

**双写策略示例**（patterns key 双键 + regex 双匹配）：

```python
# 改前 L26-27
'data_aws_standard_iops':              r'data_.*_aws_standard_iops',
'data_aws_standard_throughput_mibs':   r'data_.*_aws_standard_throughput_mibs',

# 改后（CP-5 transition window）
'data_aws_standard_iops':              r'data_.*_aws_standard_iops',           # alias 保留
'data_aws_standard_throughput_mibs':   r'data_.*_aws_standard_throughput_mibs',  # alias 保留
'data_disk_standard_iops':             r'data_.*_(aws|disk)_standard_iops',
'data_disk_standard_throughput_mibs':  r'data_.*_(aws|disk)_standard_throughput_mibs',
```

**设备命名平台分发**（AWS `ebs/nvme1n1` vs GCP `pd/google-*`）：本文件不直接 detect，靠 CP-2 注入 `LEDGER_DEVICE` / `ACCOUNTS_DEVICE` 已抽象 device name，无需改造（与 `monitoring/iostat_collector.sh` 的 `ebs_translate_device` CP-3 联动）。

**验证命令**：
```bash
cd /usr/local/google/home/lelandgong/blockchain-node-benchmark
# AWS 模式回归：旧字段 patterns 仍能命中
DEPLOYMENT_PLATFORM=aws python3 -c "from visualization.device_manager import DeviceManager; \
  dm = DeviceManager(); print(dm.get_mapped_field('data_aws_standard_iops'))"
# GCP 模式新路径：新字段名命中
DEPLOYMENT_PLATFORM=gcp python3 -c "from visualization.device_manager import DeviceManager; \
  dm = DeviceManager(); print(dm.get_mapped_field('data_disk_standard_iops'))"
# env alias 验证
BOTTLENECK_DISK_UTIL_THRESHOLD=85 python3 -c "from visualization.device_manager import DeviceManager; \
  dm = DeviceManager(); print(dm.get_baseline_values()['ebs_util_threshold'])"  # 应输出 85
```

---

### CP-5.2 visualization/report_generator.py（4752 行 / 含 Phase 7.5 五阻塞点 100% 覆盖）⭐ 最重

> **本节是 Phase 7.5 五阻塞点的权威落位**。详细分析见 `file-notes/report_generator.py.md` §6.2 (#16) + §6.8 (#12)；本节给出 5 个 method 的完整改前/改后代码 + 测试用例 + 跨进程双向链接。

**字面密度**：grep `AWS|aws|EBS|ebs|ENA|ena_|aws_ebs|ebs_aws|nitro` = **301** 处（file-notes §6.1 实证；其中 nitro=0 ✅）。47 method 中 5 method 是 Phase 7.5 阻塞点核心，其余 42 method 走通用双写策略（字段层经 CP-5.1 DeviceManager + utils/field_normalizer 自动平台化）。

#### CP-5.2 阻塞点 ① [CROSS-PROC-CONTRACT P0] `_generate_data_loss_stats_section` L3598

**契约定义**：reader 端 `visualization/report_generator.py:L3598-3650` 读 `data_loss_stats.json` 4 个 top-level key；writer 端 `monitoring/block_height_monitor.sh:L444-447` 写同 4 key。

**双方契约表**（grep 实证）：

| JSON top-level key | Writer file:line | Reader file:line | 类型 | 改造方案 |
|--------------------|------------------|------------------|------|----------|
| `data_loss_count` | block_height_monitor.sh:L444 | report_generator.py:L3627 | int | 双方保留 |
| `data_loss_periods` | block_height_monitor.sh:L445 | report_generator.py:L3620, L3631 | int | 双方保留 |
| `total_duration` | block_height_monitor.sh:L446 | report_generator.py:L3620, L3635 | seconds | 双方保留 |
| `last_updated` | block_height_monitor.sh:L447 | report_generator.py:L3645 | string | 双方保留 |

**改前**（L3598-3650 摘要）：
```python
def _generate_data_loss_stats_section(self):
    possible_paths = [
        os.path.join(self.output_dir, 'stats', 'data_loss_stats.json'),
        os.path.join(self.output_dir, 'data_loss_stats.json'),
        os.path.join(self.output_dir, '..', 'stats', 'data_loss_stats.json'),
    ]
    for stats_file in possible_paths:
        if os.path.exists(stats_file):
            with open(stats_file) as f:
                stats_data = json.load(f)
            # 直接 KeyError 风险：4 key 任一缺失即崩
            avg_duration = (stats_data['total_duration'] / stats_data['data_loss_periods']) \
                if stats_data['data_loss_periods'] > 0 else 0
            ...
```

**改后**（防御性 + 双方契约文档化）：
```python
def _generate_data_loss_stats_section(self):
    """跨进程 JSON 契约 — writer = monitoring/block_height_monitor.sh:L444-447
    4 个 top-level key:
      - data_loss_count (int)
      - data_loss_periods (int)
      - total_duration (seconds)
      - last_updated (timestamp string)
    若 writer 改 key 名，本 method 必须同步双名 fallback。"""
    possible_paths = [
        os.path.join(self.output_dir, 'stats', 'data_loss_stats.json'),
        os.path.join(self.output_dir, 'data_loss_stats.json'),
        os.path.join(self.output_dir, '..', 'stats', 'data_loss_stats.json'),
    ]
    for stats_file in possible_paths:
        if not os.path.exists(stats_file):
            continue
        with open(stats_file) as f:
            stats_data = json.load(f)
        # 防御：4 key 必须齐全，否则记 warning 跳过本 section
        required_keys = ('data_loss_count', 'data_loss_periods', 'total_duration', 'last_updated')
        missing = [k for k in required_keys if k not in stats_data]
        if missing:
            print(f"⚠️ data_loss_stats.json missing keys: {missing}; writer = monitoring/block_height_monitor.sh:L444-447")
            return ''
        loss_count   = stats_data.get('data_loss_count', 0)
        loss_periods = stats_data.get('data_loss_periods', 0)
        total_dur    = stats_data.get('total_duration', 0)
        last_upd     = stats_data.get('last_updated', 'Unknown')
        avg_duration = (total_dur / loss_periods) if loss_periods > 0 else 0
        ...
```

**测试用例**：
```bash
# 构造 4 key 完整 JSON → 应渲染正常
echo '{"data_loss_count":0,"data_loss_periods":0,"total_duration":0,"last_updated":"2026-05-18 09:00"}' \
  > /tmp/stats/data_loss_stats.json
python3 visualization/report_generator.py --output-dir /tmp --language en
# 构造缺 key → 应 warning 且 section 跳过（不崩）
echo '{"data_loss_count":0}' > /tmp/stats/data_loss_stats.json
python3 visualization/report_generator.py --output-dir /tmp --language en 2>&1 | grep "missing keys"
```

#### CP-5.2 阻塞点 ② [CROSS-PROC-CONTRACT P0] `_find_latest_monitoring_overhead_file` L1359

**glob pattern 硬编码**：`monitoring_overhead_*.csv` 与 `monitoring/unified_monitor.sh` writer 端硬编码契约；**与 CP-4.3 archiver 联动**（archiver 必须保留同名 glob，否则 reader 找不到归档文件）。

**改前**（L1359-1380 摘要）：
```python
def _find_latest_monitoring_overhead_file(self):
    logs_dir = os.getenv('LOGS_DIR', os.path.join(self.output_dir, 'current', 'logs'))
    pattern = os.path.join(logs_dir, 'monitoring_overhead_*.csv')   # 硬编码 glob
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getctime)
```

**改后**（pattern 集中 + archiver 联动注释）：
```python
# 在 ReportGenerator 类外（module level）定义集中契约
MONITORING_OVERHEAD_GLOB_PATTERNS = (
    'monitoring_overhead_*.csv',         # 主契约（monitoring/unified_monitor.sh writer 同名）
    # CP-4.3 archiver 归档后可能改为 'archive_*/monitoring_overhead_*.csv'
    # 若 archiver 改名，必须同步追加 pattern 到此元组
)

def _find_latest_monitoring_overhead_file(self):
    """跨进程 CSV 契约 — writer = monitoring/unified_monitor.sh
    glob pattern 与 CP-4.3 tools/benchmark_archiver.sh 归档命名约定联动；
    若 archiver 改名，必须同步本 MONITORING_OVERHEAD_GLOB_PATTERNS 元组。"""
    logs_dir = os.getenv('LOGS_DIR', os.path.join(self.output_dir, 'current', 'logs'))
    all_files = []
    for pat in MONITORING_OVERHEAD_GLOB_PATTERNS:
        all_files.extend(glob.glob(os.path.join(logs_dir, pat)))
    if not all_files:
        return None
    return max(all_files, key=os.path.getctime)
```

**测试用例**：
```bash
# 多 pattern 命中验证
mkdir -p /tmp/logs && touch /tmp/logs/monitoring_overhead_20260518_090000.csv
LOGS_DIR=/tmp/logs python3 -c "from visualization.report_generator import ReportGenerator; \
  rg = ReportGenerator('dummy.csv', None, None, None, 'en'); \
  print(rg._find_latest_monitoring_overhead_file())"
```

#### CP-5.2 阻塞点 ③ [CROSS-PROC-CONTRACT P0] `_load_from_overhead_csv` L1281

**15 字段 field_mappings 别名集合**（隐式跨进程契约）：

| 期望字段 | 别名 1 | 别名 2 | 别名 3 | writer 来源 |
|----------|--------|--------|--------|-------------|
| `monitoring_cpu_percent` | `monitoring_cpu` | `monitor_cpu` | `overhead_cpu` | unified_monitor.sh |
| `monitoring_mem_percent` | `monitoring_mem` | `monitor_mem` | `overhead_mem` | unified_monitor.sh |
| `monitoring_iops_per_sec` | `monitoring_iops` | `monitor_iops` | `overhead_iops` | unified_monitor.sh |
| `monitoring_throughput_mibs_per_sec` | `monitoring_throughput` | `monitor_throughput` | `overhead_throughput` | unified_monitor.sh |
| `blockchain_cpu_percent` | `blockchain_cpu` | `node_cpu` | (无) | unified_monitor.sh |
| `blockchain_mem_percent` | `blockchain_mem` | `node_mem` | (无) | unified_monitor.sh |
| `blockchain_iops_per_sec` | `blockchain_iops` | `node_iops` | (无) | unified_monitor.sh |
| `monitoring_cpu_ratio`（派生）| 无 | 无 | 无 | 本 method 计算 |
| `blockchain_cpu_ratio`（派生）| 无 | 无 | 无 | 本 method 计算 |

**平台双写补充**（GCP 模式可能新增 `pd_iops` / `pd_throughput` 别名）：
```python
def _load_from_overhead_csv(self):
    """跨进程 CSV 契约 reader — writer = monitoring/unified_monitor.sh
    15 字段别名集合是隐式契约；若 writer 改字段名，必须双写或经
    utils/field_normalizer.normalize_df() 在 read 后归一化。"""
    if not self.overhead_csv or not os.path.exists(self.overhead_csv):
        return None
    df = pd.read_csv(self.overhead_csv)
    # 经 utils/field_normalizer 归一化（CP-1 提供）
    try:
        from utils.field_normalizer import normalize_df
        df = normalize_df(df)
    except ImportError:
        pass   # CP-1 未完成时降级到原 mapping
    field_mappings = {
        'monitoring_cpu_percent': ['monitoring_cpu_percent', 'monitoring_cpu', 'monitor_cpu', 'overhead_cpu'],
        'monitoring_mem_percent': ['monitoring_mem_percent', 'monitoring_mem', 'monitor_mem', 'overhead_mem'],
        'monitoring_iops_per_sec': ['monitoring_iops_per_sec', 'monitoring_iops', 'monitor_iops', 'overhead_iops', 'pd_iops'],
        'monitoring_throughput_mibs_per_sec': ['monitoring_throughput_mibs_per_sec', 'monitoring_throughput', 'monitor_throughput', 'overhead_throughput', 'pd_throughput'],
        'blockchain_cpu_percent': ['blockchain_cpu_percent', 'blockchain_cpu', 'node_cpu'],
        'blockchain_mem_percent': ['blockchain_mem_percent', 'blockchain_mem', 'node_mem'],
        'blockchain_iops_per_sec': ['blockchain_iops_per_sec', 'blockchain_iops', 'node_iops'],
    }
    result = {}
    for canonical, aliases in field_mappings.items():
        for alias in aliases:
            if alias in df.columns:
                result[f'{canonical}_avg'] = df[alias].mean()
                result[f'{canonical}_max'] = df[alias].max()
                result[f'{canonical}_p90'] = df[alias].quantile(0.90)
                break
    # 派生
    if result.get('monitoring_cpu_percent_avg') and result.get('blockchain_cpu_percent_avg'):
        total = result['monitoring_cpu_percent_avg'] + result['blockchain_cpu_percent_avg']
        result['monitoring_cpu_ratio'] = result['monitoring_cpu_percent_avg'] / total if total > 0 else 0
        result['blockchain_cpu_ratio'] = result['blockchain_cpu_percent_avg'] / total if total > 0 else 0
    return result
```

**测试用例**：
```bash
# AWS 字段名 → 读取 OK
echo "monitoring_cpu_percent,blockchain_cpu_percent" > /tmp/overhead.csv
echo "5.2,40.1" >> /tmp/overhead.csv
# GCP 别名字段 → 同样读取 OK
echo "pd_iops,blockchain_iops" > /tmp/overhead_gcp.csv
echo "0.01,1500" >> /tmp/overhead_gcp.csv
```

#### CP-5.2 阻塞点 ④ [GCP-BLOCKER P1] `_categorize_charts` L3731

**问题**：分类关键词 `ebs/aws/iostat/bottleneck` / `ena/network/allowance` 硬编码 → GCP 改名后图表（`pd_*.png` / `disk_*.png` / `gvnic_*.png`）全部落入 `other` 兜底类，失去 EBS Professional Charts / Network & ENA Charts 视觉分组。

**改前**（L3731-3776 摘要）：
```python
def _categorize_charts(self, chart_files):
    excluded = {'block_height_sync_chart.png', 'monitoring_overhead_analysis.png',
                'monitoring_impact_chart.png', 'resource_distribution_chart.png'}
    categories = {'advanced': [], 'ebs': [], 'performance': [], 'monitoring': [], 'network': [], 'other': []}
    for f in chart_files:
        name = os.path.basename(f).lower()
        if name in excluded:
            continue
        # 硬编码关键词 — AWS-only
        if any(k in name for k in ('ebs', 'aws', 'iostat', 'bottleneck')):
            categories['ebs'].append(f)
        elif any(k in name for k in ('ena', 'network', 'allowance')):
            categories['network'].append(f)
        elif 'advanced' in name or 'correlation' in name:
            categories['advanced'].append(f)
        elif 'monitoring' in name or 'overhead' in name:
            categories['monitoring'].append(f)
        elif 'qps' in name or 'performance' in name:
            categories['performance'].append(f)
        else:
            categories['other'].append(f)
    return categories
```

**改后**（平台中立化分类规则 + 集中 keyword 表）：
```python
# Module-level（与 MONITORING_OVERHEAD_GLOB_PATTERNS 并列）
CHART_CATEGORY_KEYWORDS = {
    # platform-aware：同时含 AWS + GCP + 中立词
    'ebs':         ('ebs', 'aws', 'iostat', 'bottleneck',  # AWS
                    'pd', 'disk', 'hyperdisk',              # GCP + 中立
                    'storage'),                             # 通用兜底
    'network':     ('ena', 'network', 'allowance',          # AWS
                    'gvnic', 'nic',                         # GCP + 中立
                    'bandwidth', 'packet'),                 # 通用
    'advanced':    ('advanced', 'correlation', 'pearson', 'regression'),
    'monitoring':  ('monitoring', 'overhead'),
    'performance': ('qps', 'performance', 'throughput'),
}

def _categorize_charts(self, chart_files):
    """平台中立化分类 — 关键词扩展为 AWS + GCP + 通用三组并行匹配。
    GCP 改名后 (pd_*.png / disk_*.png / gvnic_*.png) 仍能正确归类。"""
    excluded = {'block_height_sync_chart.png', 'monitoring_overhead_analysis.png',
                'monitoring_impact_chart.png', 'resource_distribution_chart.png'}
    categories = {k: [] for k in CHART_CATEGORY_KEYWORDS}
    categories['other'] = []
    for f in chart_files:
        name = os.path.basename(f).lower()
        if name in excluded:
            continue
        # 顺序优先（ebs/network 在前，advanced/monitoring/performance 在后，other 兜底）
        matched = False
        for cat in ('ebs', 'network', 'advanced', 'monitoring', 'performance'):
            if any(k in name for k in CHART_CATEGORY_KEYWORDS[cat]):
                categories[cat].append(f)
                matched = True
                break
        if not matched:
            categories['other'].append(f)
    return categories
```

**测试用例**：
```bash
# AWS 模式 charts 列表
python3 -c "from visualization.report_generator import ReportGenerator; \
  rg = ReportGenerator('d.csv',None,None,None,'en'); \
  print(rg._categorize_charts(['ebs_aws_capacity.png', 'ena_limitation.png']))"
# 应输出 {'ebs': ['ebs_aws_capacity.png'], 'network': ['ena_limitation.png'], ...}
# GCP 模式新文件名
python3 -c "...; print(rg._categorize_charts(['pd_extreme_capacity.png', 'gvnic_bandwidth.png']))"
# 应输出 {'ebs': ['pd_extreme_capacity.png'], 'network': ['gvnic_bandwidth.png'], ...}
```

#### CP-5.2 阻塞点 ⑤ [CROSS-PROC-CONTRACT P1] `_discover_chart_files` L3670 — ✅ E1+ 与 CP-4.3 archiver 同源

**问题**：扫描多目录（`output_dir`/`current/reports/`/`reports/`/`logs/`/`archives/run_*`），`run_*` basename 启发式与 CP-4.3 `tools/benchmark_archiver.sh` 命名约定强耦合；若 archiver 改归档目录前缀（如 `archive_*` / `gcp_run_*`），本 method 静默漏扫。

**E1+ 架构修正**：放弃维护本地 `ARCHIVE_DIR_PREFIXES` 元组（→ 双源风险，archiver 与 reader 各自维护一份），改为通过 Python facade `utils/cloud_provider.get_archive_dir_prefix()` **单源**复用 CP-4.3 archiver 注入的归档前缀；§13.18 / §13.19 启发式 basename 解析全部取消（fail-fast：env `CLOUD_PROVIDER` 未 set 直接 KeyError，不靠默认值兜底）。

**改前**（L3670-3729 摘要）：
```python
def _discover_chart_files(self):
    search_dirs = [
        self.output_dir,
        os.path.join(self.output_dir, 'current', 'reports'),
        os.path.join(self.output_dir, 'reports'),
        os.path.join(self.output_dir, 'logs'),
    ]
    # 启发式：basename 含 'run_' 的 sibling 目录也扫
    parent = os.path.dirname(self.output_dir.rstrip('/'))
    if os.path.isdir(parent):
        for entry in os.listdir(parent):
            if entry.startswith('run_'):
                search_dirs.append(os.path.join(parent, entry, 'reports'))
    all_charts = []
    for d in search_dirs:
        for ext in ('*.png', '*.jpg', '*.svg'):
            all_charts.extend(glob.glob(os.path.join(d, ext)))
    # 时间戳重复过滤
    ...
```

**改后**（Python facade getter 调用 + 与 archiver 同源 + fail-fast）：
```python
# Module-level：通过 utils/cloud_provider Python facade 单源复用 CP-4.3 注入的前缀
# AWS: 'aws_run_' / GCP: 'gcp_run_' / Other: 'run_'（与 CP-4.3 tools/benchmark_archiver.sh 1:1 同源）
from utils.cloud_provider import get_archive_dir_prefix

def _discover_chart_files(self):
    """跨进程目录契约 — 与 CP-4.3 tools/benchmark_archiver.sh 归档命名约定同源；
    通过 utils/cloud_provider.get_archive_dir_prefix() 单源获取前缀，
    archiver 改前缀时只需改 utils/cloud_provider 一处（不再双源维护元组）。
    fail-fast: env CLOUD_PROVIDER 未 set 时 KeyError 报错，不取默认值兜底。"""
    archive_prefix = get_archive_dir_prefix()   # 单源 — 与 CP-4.3 archiver 同源
    search_dirs = [
        self.output_dir,
        os.path.join(self.output_dir, 'current', 'reports'),
        os.path.join(self.output_dir, 'reports'),
        os.path.join(self.output_dir, 'logs'),
    ]
    parent = os.path.dirname(self.output_dir.rstrip('/'))
    if os.path.isdir(parent):
        # 启发式 basename 解析取消（§13.18/§13.19 absorbed）— 改用 glob + 单源前缀
        for entry in glob.glob(os.path.join(parent, f'{archive_prefix}*')):
            if os.path.isdir(entry):
                search_dirs.append(os.path.join(entry, 'reports'))
    all_charts = []
    for d in search_dirs:
        for ext in ('*.png', '*.jpg', '*.svg'):
            all_charts.extend(glob.glob(os.path.join(d, ext)))
    # 时间戳重复过滤（保留原 logic）
    ts_pattern = re.compile(r'_\d{8}_\d{6}\.png$')
    seen_basenames = set()
    deduped = []
    for f in sorted(all_charts, key=os.path.getctime, reverse=True):
        basename_no_ts = ts_pattern.sub('.png', os.path.basename(f))
        if basename_no_ts not in seen_basenames:
            seen_basenames.add(basename_no_ts)
            deduped.append(f)
    return sorted(deduped)
```

#### CP-5.2 阻塞点 ⑤ 之外的其余 42 method（通用双写策略）

剩余 42 method（含 `_load_overhead_data` L1261 / `_validate_overhead_csv_format` L1408 / `validate_data_integrity` L1447 / `parse_ebs_analyzer_log` L1500 / `generate_ebs_analysis_section` L1623 / `_generate_ebs_bottleneck_section` L2715 / `_generate_cpu_ebs_correlation_table` L3258 / `_analyze_ena_limitations` L3121 等）走 file-notes §6.6 命名中立化清单 9 项（已记录），不重复展开；关键 6 项额外改造：

| # | 改造点 | 位置 | 等级 |
|---|--------|------|------|
| 6 | `get_visualization_thresholds` L1170 4 env 名 alias（`BOTTLENECK_CPU_THRESHOLD` 等） | L1170 | P1 |
| 7 | `_load_config` L1201 `ENA_MONITOR_ENABLED` 双名读取 | L1201 | P0 |
| 8 | `self.ebs_log_path` L1188 双路径 fallback | L1188 | P0 |
| 9 | `_generate_ebs_bottleneck_section` L2724 `bottleneck_info.get('disk_bottlenecks') or .get('ebs_bottlenecks', [])` | L2724-2729 | P0 |
| 10 | `parse_ebs_analyzer_log` L1500-1572 双 pattern OR 兼容 | L1518 | P0 |
| 11 | chart filename 28 处 `<img src='ebs_*.png'>` 与 CP-5.6 ebs_chart_generator 同步切名 | L3914-L4070 | P1 |

---

### CP-5.3 visualization/chart_style_config.py

**字面密度**：grep `aws|EBS|ebs|ENA|ena_` = **5** 处（最低密度文件）。

| # | file:line | 改造点 | 类别 | 等级 | 备注 |
|---|-----------|--------|------|------|------|
| 1 | L389 `'ebs_2x2': {'figsize': (16, 12), 'layout': (2, 2)}` | LAYOUT_CONFIGS dict key | UI 配置 | P2 | grep 实证 0 外部消费（仅本文件内部 key 引用）；可直改 `'disk_2x2'` |
| 2 | COLORS dict 中含 `ebs_blue` / `ena_*` 等品牌色变量名 | 颜色变量命名 | UI 配置 | P3 | 仅命名，不影响色值 |
| 3 | 章节标题字面 `'EBS Performance Charts'` / `'ENA Network Charts'` | UI 字面 | UI 字面 | P2 | 改为 `'Disk Performance Charts'` / `'Network Charts'` |
| 4 | legend 字面同上 | UI 字面 | UI 字面 | P2 | 同 #3 |
| 5 | docstring/注释中立化 | 注释 | 注释 | P3 | 影响零 |

**改造示例**（双 key 兼容过渡）：
```python
LAYOUT_CONFIGS = {
    'disk_2x2': {'figsize': (16, 12), 'layout': (2, 2)},
    'ebs_2x2':  {'figsize': (16, 12), 'layout': (2, 2)},   # alias 保留 1 Round（CP-6 删）
    ...
}
```

**验证**：
```bash
grep -nE "'ebs_2x2'|'disk_2x2'" visualization/  -r   # 双 key 命中
```

---

### CP-5.4 visualization/performance_visualizer.py

**字面密度**：grep `aws|EBS|ebs|ENA|ena_` = **51** 处。主体逻辑是入参 CSV 字段双写支持 + 委托 EBSChartGenerator。

| # | file:line | 改造点 | 类别 | 等级 |
|---|-----------|--------|------|------|
| 1 | L27 `from visualization.ebs_chart_generator import EBSChartGenerator` | import 路径 | 文件依赖 | **P1** |
| 2 | L33 `from analysis.cpu_ebs_correlation_analyzer import CPUEBSCorrelationAnalyzer` | import 路径 | 文件依赖 | **P1** |
| 3 | L421/L529 `cpu_ebs_correlation_visualization.png` 输出文件名 | 文件名 | UI 文件名 | P2 |
| 4 | L1306-1309 `generate_all_ebs_charts()` 委托 + log 字面 `EBS professional charts` | 调用 + 文案 | UI 字面 | P2 |
| 5 | L2264 `generate_ebs_bottleneck_analysis` / L2273 `generate_ebs_time_series` / L2533 `generate_all_ebs_charts` 3 个 wrapper method | 方法名 alias | API | P2 |
| 6 | L2267/L2276 `EBSChartGenerator(self.df, self.output_dir)` 实例化 | class 名 | 文件依赖 | **P1** |
| 7 | CSV 字段读取经 DeviceManager.get_mapped_field（CP-5.1 已抽象，无需本文件改）| 字段消费 | 字段契约 | N/A |

**改前/改后**（import + 实例化双名兼容）：
```python
# 改前
from visualization.ebs_chart_generator import EBSChartGenerator
from analysis.cpu_ebs_correlation_analyzer import CPUEBSCorrelationAnalyzer

# 改后（CP-5.6/CP-5.7 重命名后）
try:
    from visualization.disk_chart_generator import DiskChartGenerator as EBSChartGenerator
except ImportError:
    from visualization.ebs_chart_generator import EBSChartGenerator
try:
    from analysis.cpu_disk_correlation_analyzer import CPUDiskCorrelationAnalyzer as CPUEBSCorrelationAnalyzer
except ImportError:
    from analysis.cpu_ebs_correlation_analyzer import CPUEBSCorrelationAnalyzer
```

**验证**：
```bash
python3 -c "from visualization.performance_visualizer import *; print('import OK')"
```

---

### CP-5.5 visualization/advanced_chart_generator.py

**字面密度**：grep `aws|EBS|ebs|ENA|ena_|allowance` = **45** 处。高级图表 + ENAFieldAccessor 抽象消费。

| # | file:line | 改造点 | 类别 | 等级 |
|---|-----------|--------|------|------|
| 1 | L30 `from utils.ena_field_accessor import ENAFieldAccessor` | import（已抽象）| OK | N/A |
| 2 | L42 `_calculate_ena_delta_series` method 名 | method 名 alias | API | P2 |
| 3 | L246-267 `cpu_col, ebs_col` 变量名 + `ebs_data` 局部 | 局部变量 | 局部命名 | P3 |
| 4 | L495-496 `ebs_patterns = ['util', 'aqu_sz', 'avg_await', 'r_s', 'w_s', 'total_iops', 'throughput_mibs']` | 字段依赖 list | 字段契约 | **P1** |
| 5 | L682 `generate_ena_network_analysis_charts` method 名 | method 名 alias | API | P2 |
| 6 | L691 `ENAFieldAccessor.get_available_ena_fields(self.df)` | 已抽象消费 | OK | N/A |
| 7 | L706/L711/L716 `_generate_ena_*_chart` 3 个内部 method | method 名 alias | API | P2 |
| 8 | 输出文件名 `ena_limitation_trends.png` / `ena_connection_capacity.png` / `ena_comprehensive_status.png` 3 处 | 文件名 | UI 文件名 | P2 |

**字段双写改造（#4）**：
```python
# 改前 L495-496
ebs_patterns = ['util', 'aqu_sz', 'avg_await', 'r_s', 'w_s', 'total_iops', 'throughput_mibs']

# 改后（GCP 模式增加 pd 特有 metric，AWS 兼容保留）
DISK_METRIC_PATTERNS = (
    'util', 'aqu_sz', 'avg_await', 'r_s', 'w_s',       # 通用 iostat
    'total_iops', 'throughput_mibs',                    # AWS 标准
    'queue_depth', 'svc_time',                          # GCP pd 额外指标
)
disk_patterns = list(DISK_METRIC_PATTERNS)
ebs_patterns = disk_patterns   # alias 保留
```

**验证**：
```bash
python3 -c "from visualization.advanced_chart_generator import AdvancedChartGenerator; \
  print('import OK')"
```

---

### CP-5.6 visualization/ebs_chart_generator.py → visualization/disk_chart_generator.py

**字面密度**：grep `aws|EBS|ebs|ENA|ena_` = **166** 处（visualization/ 中最高）。文件级重命名 + 内部 `ebs_*` → `disk_*` + class 名重命名。

| # | file:line | 改造点 | 类别 | 等级 |
|---|-----------|--------|------|------|
| 1 | 文件名 `ebs_chart_generator.py` → `disk_chart_generator.py` | 文件名 | 物理文件 | **P0**（CP-6 删 alias 时改）|
| 2 | L26 `class EBSChartGenerator:` → `class DiskChartGenerator:` + module-level alias `EBSChartGenerator = DiskChartGenerator` | class 名 | API | **P0** |
| 3 | L34 `'comparison': 'ebs_aws_standard_comparison.png'` 等 7 chart filenames（与 CP-5.2 阻塞点⑤ L3914-L4070 联动）| chart filename | UI 文件名 | **P1** |
| 4 | L107 `_recalculate_aws_standard_metrics` method 名 | method 名 alias | API | P2 |
| 5 | L116/L118/L140/L142 `get_mapped_field('data_aws_standard_iops')` 等 4 处字段消费（依赖 CP-5.1 patterns 双写）| 字段消费 | 字段契约 | **P1** |
| 6 | L171 `'data_aws_standard_iops', 'data_aws_standard_throughput_mibs'` 字段 list | 字段 list | 字段契约 | **P1** |
| 7 | L199 `charts.append(self.generate_ebs_aws_standard_comparison())` | method 调用 + alias | API | P2 |
| 8 | L718/L727/L740/L749/L796/L847 等 6+ 处 `get_mapped_field('*_aws_standard_*')` | 字段消费 | 字段契约 | **P1** |
| 9 | log/print 字面 `EBS chart generated` 等 | UI 字面 | UI 字面 | P3 |

**重命名 + 双 import 兼容**：
```bash
# 物理重命名（CP-5.6 仅做内部 alias，文件移动延到 CP-6）
# Phase 7.x: 保留 ebs_chart_generator.py 内含 alias，等 CP-6 删除
```

```python
# disk_chart_generator.py（新文件，CP-6 替换）
class DiskChartGenerator:
    ...

# ebs_chart_generator.py（保留 1 Round 兼容）
from visualization.disk_chart_generator import DiskChartGenerator
EBSChartGenerator = DiskChartGenerator   # alias 保留
```

**与 CP-5.2 _discover_chart_files 联动**：
- chart filename `ebs_aws_capacity_planning.png` 等 7 个由本 generator 输出，被 report_generator `_discover_chart_files` 扫描后经 `_categorize_charts`（已平台化，见 CP-5.2 阻塞点④）分类。
- 改名顺序：先改 _categorize_charts 关键词（新词在前），再改本文件 chart filename（双写过渡）。

---

### CP-5.7 analysis/{comprehensive_analysis, cpu_ebs_correlation_analyzer, qps_analyzer, rpc_deep_analyzer}.py

**4 文件字段密度**：comprehensive=12 / cpu_ebs_correlation=15 / qps=48 / rpc_deep=0。

#### CP-5.7.1 analysis/cpu_ebs_correlation_analyzer.py → cpu_disk_correlation_analyzer.py（**重命名**）

| # | file:line | 改造点 | 等级 |
|---|-----------|--------|------|
| 1 | 文件名 `cpu_ebs_correlation_analyzer.py` → `cpu_disk_correlation_analyzer.py` | **P0** |
| 2 | L32 `class CPUEBSCorrelationAnalyzer:` → `class CPUDiskCorrelationAnalyzer:` + alias | **P0** |
| 3 | L63 `required_ebs_cols = []` 局部 → `required_disk_cols` | P3 |
| 4 | L80/L84 log 字面 `"EBS devices"` → `"disk devices"` | P3 |
| 5 | 输出标题 `'CPU-EBS Correlation'` → `'CPU-Disk Correlation'` | P2 |
| 6 | 相关性算法（pearsonr 等）**完全不动** | N/A |

```python
# cpu_disk_correlation_analyzer.py
class CPUDiskCorrelationAnalyzer:
    ...

# cpu_ebs_correlation_analyzer.py（alias 文件 1 Round）
from analysis.cpu_disk_correlation_analyzer import CPUDiskCorrelationAnalyzer
CPUEBSCorrelationAnalyzer = CPUDiskCorrelationAnalyzer
```

#### CP-5.7.2 analysis/comprehensive_analysis.py（整合层）— ✅ §13.21 'EBS' 4 处 E1+ absorbed

| # | file:line | 改造点 | 等级 |
|---|-----------|--------|------|
| 1 | L373 `ebs_iops_fields = [col for col in df.columns if 'total_iops' in col]` | 字段筛选 list 已中立 `total_iops` | OK |
| 2 | L378/L383/L385 plot 标题 `'EBS IOPS vs QPS'` / `'EBS IOPS Data'` | UI 字面 P2 |
| 3 | L539/L588/L636/L684 `bottleneck_type == DISK_LABEL` 4 处（原 `'EBS' in bottleneck_types` 字面，E1+ 全部经 `get_bottleneck_label()` 注入） | 字段值 P0（与 CP-4 bottleneck_detector 写方 1:1 同源）|
| 4 | L588-589 recommendation 字面 `f"upgrade {DISK_LABEL} type"` | UI 字面 P2 |
| 5 | 整合所有平台中立化结果（CP-5.1/5.6/5.7.1 输出）| 整合 | **P0** |

**bottleneck_types Python facade getter 改造**（与 CP-4 写方 1:1 同源 + fail-fast）：
```python
# 改前 L539（4 处独立硬编码 'EBS' 字面）
BOTTLENECK_TYPES = {'EBS', 'CPU', 'Memory', 'Network'}   # 硬编码
if 'EBS' in bottleneck_types: ...                         # L539
if bottleneck_type == 'EBS': ...                          # L588
print(f'EBS bottleneck detected')                         # L636
recommendations.append('upgrade EBS type')                # L684

# 改后（Python facade utils/cloud_provider 单源 + fail-fast）
from utils.cloud_provider import get_bottleneck_label
DISK_LABEL = get_bottleneck_label()   # AWS: 'EBS' / GCP: 'Disk' / Other: 'Disk'
BOTTLENECK_TYPES = {DISK_LABEL, 'CPU', 'Memory', 'Network'}
if DISK_LABEL in bottleneck_types: ...                    # L539 — 单源
if bottleneck_type == DISK_LABEL: ...                     # L588 — 单源
print(f'{DISK_LABEL} bottleneck detected')                # L636 — 单源
recommendations.append(f'upgrade {DISK_LABEL} type')      # L684 — 单源
```

**Python facade `utils/cloud_provider.py`**：读 `os.environ['CLOUD_PROVIDER']`（无 default → KeyError fail-fast），dispatch dict 返 `'EBS'` / `'Disk'` / `'Disk'`；与 bash 抽象层 `config/cloud_provider.sh::get_bottleneck_label` 1:1 对称（详见 §0.3 Python 接口表）。

#### CP-5.7.3 analysis/qps_analyzer.py

| # | file:line | 改造点 | 等级 |
|---|-----------|--------|------|
| 1 | L82-129 `ebs_util_field` / `ebs_latency_field` / `ebs_iops_field` 字段动态发现（dynamic column scan）| 局部变量 P3（无外部消费）|
| 2 | column 查找逻辑可直接继承 CP-5.1 DeviceManager.get_mapped_field 抽象 | 字段消费 | **P1** |

**改造方案**：4 处 `ebs_*_field` 改名为 `disk_*_field`，逻辑层不动（已动态发现）。

#### CP-5.7.4 analysis/rpc_deep_analyzer.py

字面密度 = 0 ✅。**无 AWS 字面，无需改造**。仅添加 `from utils.field_normalizer import normalize_df` 调用以接通双名归一化层。

#### 4 文件共同改造模式

```python
# 所有 analysis/*.py 顶部统一加（CP-1 完成后）
try:
    from utils.field_normalizer import normalize_df
except ImportError:
    normalize_df = lambda df: df   # CP-1 未完成时降级

# pd.read_csv 后立即调用
df = normalize_df(pd.read_csv(csv_path))
```

**验证矩阵**（CP-5.7 全 4 文件）：
```bash
cd /usr/local/google/home/lelandgong/blockchain-node-benchmark
# AWS 模式回归
DEPLOYMENT_PLATFORM=aws python3 -m analysis.comprehensive_analysis test.csv
DEPLOYMENT_PLATFORM=aws python3 -m analysis.cpu_disk_correlation_analyzer test.csv   # 新名
DEPLOYMENT_PLATFORM=aws python3 -m analysis.cpu_ebs_correlation_analyzer test.csv   # alias 兼容
# GCP 模式新路径
DEPLOYMENT_PLATFORM=gcp python3 -m analysis.qps_analyzer test_gcp.csv
DEPLOYMENT_PLATFORM=gcp python3 -m analysis.rpc_deep_analyzer test_gcp.csv
```

---

### CP-5 跨文件双向链接矩阵（消费端总览）

| 消费 method | file:line | 上游 writer | TRACKER 编号 |
|-------------|-----------|-------------|---------------|
| `_load_from_overhead_csv` L1281 | report_generator.py | `monitoring/unified_monitor.sh` (CP-3) | #34/#35 |
| `_find_latest_monitoring_overhead_file` L1359 | report_generator.py | `monitoring/unified_monitor.sh` + `tools/benchmark_archiver.sh` (CP-4.3) | 新发现 |
| `_generate_data_loss_stats_section` L3598 | report_generator.py | `monitoring/block_height_monitor.sh:L444-447` (CP-3) | 新发现 |
| `_discover_chart_files` L3670 | report_generator.py | `visualization/{ebs,advanced,performance}_chart_generator.py` (CP-5.4-5.6) + `tools/benchmark_archiver.sh` (CP-4.3) | 新发现 |
| `_categorize_charts` L3731 | report_generator.py | 同上 chart_files 列表来源 | 新发现 |
| `get_baseline_values` L254-261 | device_manager.py | `config/internal_config.sh:L17-22` (CP-2) | DM-5/6/7 |
| `_recalculate_aws_standard_metrics` L107 | ebs_chart_generator.py | `monitoring/iostat_collector.sh:L127/L144` (CP-3) | #5/#7 |
| `analyze` (相关性) | cpu_ebs_correlation_analyzer.py | `monitoring/unified_monitor.sh` (CP-3) | (通用) |

### 🆕 待回灌 TRACKER §13.X 的新挖阻塞点

1. **§13.1 `_find_latest_monitoring_overhead_file` glob pattern 与 archiver 命名约定隐式契约**（CP-5.2 阻塞点②）— TRACKER 未列出 `tools/benchmark_archiver.sh` 归档目录命名规则与 reader glob 的耦合
2. **§13.2 `_discover_chart_files` `run_*` basename 启发式与 archiver 前缀强耦合**（CP-5.2 阻塞点⑤）— ✅ **E1+ absorbed**：改用 `utils.cloud_provider.get_archive_dir_prefix()` Python facade，与 CP-4.3 archiver 1:1 同源；§13.18/§13.19 启发式 basename 解析取消
3. **§13.3 `MONITORING_OVERHEAD_GLOB_PATTERNS` / `CHART_CATEGORY_KEYWORDS` 集中化建议**（CP-5.2 阻塞点②④）— 当前散落在 method 内
4. **§13.4 / §13.21 `bottleneck_types` 字符串 `'EBS'` 多 reader 共享字面**（CP-5.7.2 #3）— ✅ **E1+ absorbed**：`analysis/comprehensive_analysis.py:L539/L588/L636/L684` 4 处全部改 `get_bottleneck_label()` 调用，AWS 返 `'EBS'` / GCP 返 `'Disk'` / Other 返 `'Disk'`

### CP-5 验证总入口

```bash
cd /usr/local/google/home/lelandgong/blockchain-node-benchmark
# 业务代码零 diff 实证（CP-5 仅修文档；实际 patch 在后续 CP 阶段）
git diff --stat e843571 -- ':!analysis-notes'   # 必须空

# Phase 7.5 五阻塞点 grep 实证
grep -nE "_generate_data_loss_stats_section|_find_latest_monitoring_overhead_file|_load_from_overhead_csv|_categorize_charts|_discover_chart_files" \
  visualization/report_generator.py
# 应输出 L3598 / L1359 / L1281 / L3731 / L3670 各 1 个 def 行

# data_loss_stats.json 4 key 契约 grep
grep -nE 'data_loss_count|data_loss_periods|total_duration|last_updated' \
  monitoring/block_height_monitor.sh visualization/report_generator.py
```

---

### CP-5.X E1+ 平台对等性强化 + Python 端 getter 集中化

1. **§13.21 'EBS' 字面 4 处 → ✅ E1+ absorbed**: `analysis/comprehensive_analysis.py:L539/L588/L636/L684` 全部改 `get_bottleneck_label()` 调用 — AWS 返 `'EBS'` / GCP 返 `'Disk'` / Other 返 `'Disk'`；`BOTTLENECK_TYPES` 集合 + 4 处条件判断/打印/recommendation 一律走 `DISK_LABEL` 单源
2. **CP-5.2 glob pattern 与 CP-4.3 archiver 同源**: 单源 `get_archive_dir_prefix()`（AWS: `'aws_run_'` / GCP: `'gcp_run_'` / Other: `'run_'`），`_discover_chart_files` 启发式 basename 解析全部取消（§13.18 + §13.19 absorbed）；archiver 改前缀只需改 `utils/cloud_provider` 一处
3. **Python facade `utils/cloud_provider.py`**: 读 env `CLOUD_PROVIDER`（不重复 IMDS probe，bash 抽象层已在 init 阶段 export），与 bash `config/cloud_provider.sh` 对称（15 getter 接口 1:1，详见 §0.3 Python 接口表）
4. **fail-fast 架构**: `utils/cloud_provider.py` 使用 `os.environ['CLOUD_PROVIDER']` 不取 default — 未 set 时 KeyError 立即报错（符合 §0 决策 6：禁默认值），杜绝静默回退到 AWS 路径的 bug

**验证场景**：
- AWS 环境 (`CLOUD_PROVIDER=aws`)：`comprehensive_analysis` 输出含 `'EBS bottleneck'`；glob 匹配 `aws_run_*`
- GCP 环境 (`CLOUD_PROVIDER=gcp`)：输出含 `'Disk bottleneck'`；glob 匹配 `gcp_run_*`
- Other (`CLOUD_PROVIDER=other`)：输出含 `'Disk bottleneck'`；glob 匹配 `run_*`
- 未 set `CLOUD_PROVIDER`：`KeyError: 'CLOUD_PROVIDER'`（fail-fast，无静默兜底）

**验证命令**：
```bash
sed -n '/^## CP-5/,/^## CP-6/p' analysis-notes/CORRECTED_PLAN.md | grep -cE 'get_bottleneck_label|get_archive_dir_prefix'   # 应 >= 4
sed -n '/^## CP-5/,/^## CP-6/p' analysis-notes/CORRECTED_PLAN.md | grep -cE '§13\.21.*absorbed'                              # 应 >= 1
```

---

## CP-6：收尾

CP-6 是 GCP 迁移**最后一个 Round（N+1 Round）**，触发条件是 CP-1..CP-5 全部验证通过，且
最近一个完整 Round（通常 CP-5 收尾后）在真实 GCP 环境跑过至少 1 个完整 24h 烟测无回归。
CP-6 不引入任何新业务逻辑，只做三件事：
1. 删除 CP-1/2/3 阶段为 backwards-compat 双写的 `AWS_*` alias（CP-6.1）
2. 八链 24h 端到端 GCP 回归（CP-6.2）
3. 仓内文档从 AWS-only 表述切换为多云中立 + 新建 migration-guide（CP-6.3）

CP-6 完成即代表 GCP 迁移项目正式结案。

---

### CP-6.1 删除所有 AWS_* alias（N+1 Round）

#### 6.1.1 背景

CP-1/2/3 阶段为了**保护下游消费方不被一次性改名打断**，所有 `AWS_*` 命名变量都采用了
"双写 alias" 策略：新增中立名 `CLOUD_*` / `METADATA_*` 作为唯一权威值，旧 `AWS_*` 名以
`AWS_X=$CLOUD_X` 形式保留为 alias。这导致 N+1 Round 时仓里仍有 5 个 `AWS_*` env var
+ 多处函数命名/字符串字面带 `AWS_` 前缀。

CP-6.1 的目标是：**确认 0 外部 consumer 还在读旧 alias 后，把所有 `AWS_*` 行物理删除**，
让仓内任何 grep `AWS_` 只在 file-notes / CHANGELOG 等历史文档里命中。

#### 6.1.2 alias 清单（待删 5 项 + 函数命名/字面 3 类）

来源：grep 全仓 `AWS_` + 交叉 `analysis-notes/file-notes/system_config.sh.md` §6 重命名表
+ `ebs_converter.sh.md` §4.2.4 函数命名章节。

| # | 旧名 | 类型 | 文件:行 | 引入 Round | 中立名 | CP-6.1 动作 |
|---|------|------|---------|-----------|--------|-------------|
| 1 | `AWS_EBS_BASELINE_IO_SIZE_KIB` | env var | config/system_config.sh:L53, export L115 | CP-1.4 | `CLOUD_IO_BASELINE_KIB` | 删 L53 alias 行 + L115 export 中去名 |
| 2 | `AWS_EBS_BASELINE_THROUGHPUT_SIZE_KIB` | env var | config/system_config.sh:L54, export L115; utils/ebs_converter.sh:L7 fallback | CP-1.4 | `CLOUD_THROUGHPUT_BASELINE_KIB` | 删 system_config.sh L54 + ebs_converter.sh L7 fallback 名 |
| 3 | `AWS_METADATA_ENDPOINT` | env var (URL) | config/system_config.sh:L57, export L115; config/config_loader.sh:L106 (curl 唯一消费方) | CP-1.4 / CP-2.1 | `METADATA_ENDPOINT` | 删 system_config.sh L57 + 改写 config_loader.sh L106 curl 用 `$METADATA_ENDPOINT` |
| 4 | `AWS_METADATA_API_VERSION` | env var (path 段) | config/system_config.sh:L59, export L115; config/config_loader.sh:L106 | CP-1.4 / CP-2.1 | `METADATA_API_PATH` | 同 #3 同行同步 |
| 5 | `AWS_METADATA_TOKEN_TTL` | env var (秒) | config/system_config.sh:L58, export L115 | CP-1.4 | （死字段，直接删，无 alias 后继） | grep 全仓 0 命中后 L58 + L115 export 同步去名 |
| 6 | `convert_to_aws_standard_iops` / `convert_to_aws_standard_throughput` | 函数名 | utils/ebs_converter.sh:L40, L65（CP-1.4 已加 `convert_to_standard_iops` 中立 alias） | CP-1.4 | `convert_to_standard_iops` / `convert_to_standard_throughput` | 删旧函数定义 + 调用方（monitoring/bottleneck_detector.sh, monitoring/iostat_collector.sh）全部改用新名 |
| 7 | `EBS_AWS_IOPS` / `EBS_AWS_Throughput` / `ACCOUNTS_EBS_AWS_IOPS` / `ACCOUNTS_EBS_AWS_Throughput` | bottleneck_types 字符串字面 | monitoring/bottleneck_detector.sh:L970/L974/L1016/L1020 | CP-3.x | `EBS_STANDARD_IOPS` / `EBS_STANDARD_Throughput` / `ACCOUNTS_EBS_STANDARD_*` | 全仓改字面 + 报表 mapper（report_generator.py）同步改 key 匹配 |
| 8 | `EBS_AWS_IOPS_PATTERNS` / `aws_standard_iops` | bash 变量名 + CSV 字段名 | monitoring/bottleneck_detector.sh:L56, L819; csv header 字段 | CP-3.x | `EBS_STANDARD_IOPS_PATTERNS` / `standard_iops`（双写 CSV 写双列已在 CP-3 完成） | 删旧字段双写 + 旧 PATTERNS 变量 |

**说明**：
- #1~#5 是 P0 必删的 env var；#6~#8 是 P1 命名清洁
- CP-6.1 必须**先做 #1~#5**，再做 #6~#8（函数名改动影响面更大，需要单独 PR）
- #5 (`AWS_METADATA_TOKEN_TTL`) 是死字段（system_config.sh.md §6 §10.4 已实证 grep 0 下游），可与 #1~#4 同一 PR 删除

#### 6.1.3 删除前清点检查（必跑，每条 alias 都跑）

对每个待删旧名，运行以下验证脚本，**必须返回 0 行外部命中**才允许进入删除 PR：

```bash
#!/usr/bin/env bash
# scripts/cp6.1_alias_grep_check.sh
# 用法: bash scripts/cp6.1_alias_grep_check.sh
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

ALIASES=(
  "AWS_EBS_BASELINE_IO_SIZE_KIB"
  "AWS_EBS_BASELINE_THROUGHPUT_SIZE_KIB"
  "AWS_METADATA_ENDPOINT"
  "AWS_METADATA_API_VERSION"
  "AWS_METADATA_TOKEN_TTL"
  "convert_to_aws_standard_iops"
  "convert_to_aws_standard_throughput"
  "EBS_AWS_IOPS"
  "EBS_AWS_Throughput"
  "ACCOUNTS_EBS_AWS_IOPS"
  "ACCOUNTS_EBS_AWS_Throughput"
  "EBS_AWS_IOPS_PATTERNS"
  "aws_standard_iops"
)

EXCLUDES=(
  --exclude-dir=analysis-notes   # 历史调研笔记保留
  --exclude-dir=.git
  --exclude-dir=CHANGELOG.d      # 归档变更条目保留
  --exclude="CHANGELOG.md"
  --exclude="*.bak"
)

fail=0
for var in "${ALIASES[@]}"; do
  echo "==> 检查 $var"
  # 期望：业务代码（含 monitoring/ utils/ config/ visualization/ tools/）0 命中
  hits=$(grep -rn "$var" "${EXCLUDES[@]}" . 2>/dev/null \
         | grep -vE "^./scripts/cp6\.1_alias_grep_check\.sh:" \
         | wc -l)
  if [[ "$hits" -ne 0 ]]; then
    echo "  ❌ 仍有 $hits 处业务代码命中 $var，禁止删除！"
    grep -rn "$var" "${EXCLUDES[@]}" . 2>/dev/null \
       | grep -vE "^./scripts/cp6\.1_alias_grep_check\.sh:"
    fail=1
  else
    echo "  ✅ 0 外部 consumer，可安全删除"
  fi
done

exit "$fail"
```

#### 6.1.4 删除 PR 拆分（建议 3 个 PR，依次合并）

**PR-6.1-A：env var 类（#1~#5）**
- 影响文件：config/system_config.sh, config/config_loader.sh, utils/ebs_converter.sh
- 描述模板：
  ```
  CP-6.1-A: Remove AWS_* env var aliases (5 vars)

  After CP-1.4 双写 alias 过渡期（CP-1~CP-5 共 5 轮 + 7 天 GCP 真机运行）确认 0 外部
  consumer 仍引用旧名（见 scripts/cp6.1_alias_grep_check.sh 全绿输出附件）。

  Deleted:
  - AWS_EBS_BASELINE_IO_SIZE_KIB (替代为 CLOUD_IO_BASELINE_KIB)
  - AWS_EBS_BASELINE_THROUGHPUT_SIZE_KIB (替代为 CLOUD_THROUGHPUT_BASELINE_KIB)
  - AWS_METADATA_ENDPOINT (替代为 METADATA_ENDPOINT)
  - AWS_METADATA_API_VERSION (替代为 METADATA_API_PATH)
  - AWS_METADATA_TOKEN_TTL (死字段，直接删)

  Tests: bash scripts/cp6.1_alias_grep_check.sh → 全 ✅
         bash tests/smoke/aws_ec2_one_chain.sh    → PASS (AWS 平台回归)
         bash tests/smoke/gcp_cloudtop_one_chain.sh → PASS (GCP 平台回归)
  ```

**PR-6.1-B：函数命名清洁（#6）**
- 影响文件：utils/ebs_converter.sh, monitoring/bottleneck_detector.sh, monitoring/iostat_collector.sh
- 前置：PR-6.1-A 已合并 1 周无回归
- 删除 `convert_to_aws_standard_*` 函数定义 + 全部调用方改名

**PR-6.1-C：字段/字符串字面清洁（#7~#8）**
- 影响文件：monitoring/bottleneck_detector.sh, visualization/report_generator.py, CSV header
- 前置：PR-6.1-A + PR-6.1-B 已合并各 1 周无回归
- ⚠️ CSV header 双写字段 `aws_standard_iops` 删列将破坏**历史 CSV 文件回放**：
  PR 描述中必须明文化 "released after vN.M, CSV 兼容性切口在 vN.M 之后归档的旧
  CSV 无法用新版工具回放，需 schema migration 脚本"

#### 6.1.5 触发条件与联动（必须全满足才可起 CP-6.1）

| Gate | 条件 | 验证命令 |
|------|------|----------|
| G1 | CP-1.1~CP-1.4 全部 commit 入主干 | `git log --oneline --grep="CP-1\."` 至少 4 条 |
| G2 | CP-2.1~CP-2.3 全部 commit 入主干 | `git log --oneline --grep="CP-2\."` 至少 3 条 |
| G3 | CP-3.1~CP-3.x 全部 commit 入主干（字段双写完成） | `git log --oneline --grep="CP-3\."` ≥ 完整子项数 |
| G4 | CP-4.3 platform-aware archive 命名已上线 | `grep -n PLATFORM tools/benchmark_archiver.sh` 命中 |
| G5 | CP-5.2 五阻塞点检测在 GCP 模式下不报虚警 | 见 CP-5.2 验收脚本输出 |
| G6 | 最近 7 天 GCP 真机至少 1 链 24h 烟测全绿 | `analysis-notes/06-gcp-smoke-logs/` 当周日志附件 |
| G7 | grep 验证脚本（6.1.3）全 ✅ | `bash scripts/cp6.1_alias_grep_check.sh; echo $?` == 0 |

任何 Gate 未满足则 CP-6.1 必须**冻结**，等待对应 CP-N 子项补齐。

#### 6.1.6 验收

PR-6.1-A/B/C 全部合并后：

```bash
# 1. 全仓 AWS_ 业务代码命中应为 0（只剩 analysis-notes / CHANGELOG）
grep -rn "AWS_" \
  --exclude-dir=analysis-notes --exclude-dir=.git --exclude-dir=CHANGELOG.d \
  --exclude="CHANGELOG.md" .
# 期望：0 行输出

# 2. 双平台烟测
bash tests/smoke/aws_ec2_one_chain.sh         # AWS 端不应回归
bash tests/smoke/gcp_cloudtop_one_chain.sh    # GCP 端不应回归

# 3. 历史 CSV 回放（CP-6.1-C 后破坏，需要 migration 脚本兜底）
python3 tools/csv_schema_migrate.py --from v0 --to v1 --in legacy.csv --out legacy.v1.csv
python3 visualization/report_generator.py --csv legacy.v1.csv
```

---

### CP-6.2 端到端 GCP 回归

#### 6.2.1 范围

八条链各跑一次完整 24h 端到端在真实 GCP 环境，复用 CP-5.2 + CP-4.3 + CP-3 全部产物，
确认 GCP 模式下 metric 采集 / 报表生成 / archive 命名 / bottleneck 检测全部正确。

**八链清单（按优先级）**：

| # | 链 | 优先级 | 备注 |
|---|----|--------|------|
| 1 | Solana | P0 | 历史最大 baseline，吞吐最高 |
| 2 | Ethereum (EL+CL) | P0 | EL/CL 双进程，与 P0-S 不同 metric 拓扑 |
| 3 | BSC | P1 | EVM-fork，验证 Ethereum 复用度 |
| 4 | Base | P1 | L2 OP-stack |
| 5 | Polygon | P1 | EVM L1/L2 |
| 6 | Scroll | P2 | ZK-rollup |
| 7 | Starknet | P2 | Cairo VM，非 EVM |
| 8 | Sui | P2 | Move VM，非 EVM |

#### 6.2.2 测试环境

| 维度 | 配置 |
|------|------|
| 主机 | 1× GCP cloudtop, machine_type = n2-standard-16（或 c3-standard-22 视链而定） |
| 磁盘 | 1× Hyperdisk Extreme 1.5 TiB（provisioned IOPS = 80000，throughput = 1200 MiB/s） |
| 网络 | gVNIC + Tier_1 网络（Bandwidth ≥ 25 Gbps） |
| OS | Debian 12 / Ubuntu 22.04 |
| Python | 3.10+ |
| 时长 | 24h 单链 × 8 链（串行；总 ≤ 9 天，含 1 天缓冲） |
| Metadata server | `http://metadata.google.internal`（必须带 `-H 'Metadata-Flavor: Google'` 头） |

#### 6.2.3 验证点（六维 checklist）

| # | 维度 | 验证项 | 来源 | 验证命令/脚本 |
|---|------|--------|------|---------------|
| V1 | CSV header | 所有 CSV header 同时含旧字段（`ena_*`、`aws_standard_iops`）和新字段（`nic_*`、`standard_iops`）双写列；CSV 行数 24h × 60s ≈ 1440 ± 5% | file-notes/iostat_collector.sh.md, file-notes/ena_network_monitor.sh.md | `python3 tests/cp6.2/check_csv_dual_write.py --csv $OUT/perf_*.csv` |
| V2 | 报表覆盖 | report_generator.py 生成 HTML 报表中 CP-5.2 五阻塞点（CPU/Mem/Disk-iops/Disk-tp/Net）100% 渲染图表，无 "N/A" | file-notes/report_generator.py.md | `python3 tests/cp6.2/check_report_5bottlenecks.py --html $OUT/report.html` |
| V3 | Archive 命名 | benchmark_archiver 输出文件名含平台 token（如 `bench-gcp-solana-20260518T0930.tar.gz`），不再是 aws-only `bench-solana-*` | file-notes/benchmark_archiver.sh.md, CP-4.3 | `ls $OUT/*.tar.gz \| grep -E 'bench-gcp-(solana\|ethereum\|...)'` |
| V4 | Bottleneck 检测 | GCP 模式下 bottleneck_detector.sh 不报 ENA allowance 虚警（gVNIC 无 allowance counter，应走 gauge fallback 静默）；五阻塞点检测在真实瓶颈下能正确触发 | file-notes/bottleneck_detector.sh.md, CP-5.2 | `grep -c "ENA_ALLOWANCE_EXCEEDED" $OUT/bottleneck.log` == 0；`grep -c "CPU_BOTTLENECK\|MEM_BOTTLENECK\|EBS_STANDARD_IOPS\|EBS_STANDARD_Throughput\|NET_GAUGE" $OUT/bottleneck.log` ≥ 0（取决于真实负载） |
| V5 | 连续性 | metric 采集 24h 不中断；缺失采样点 ≤ 0.5%；data_loss_stats.json 4 key（data_loss_count, data_loss_periods, total_duration, last_updated）齐全 | file-notes/block_height_monitor.sh.md, file-notes/framework_data_quality_checker.sh.md | `jq '.data_loss_count, .data_loss_periods, .total_duration, .last_updated' $OUT/data_loss_stats.json`；`python3 tests/cp6.2/check_continuity.py --csv $OUT/perf_*.csv --max-gap-pct 0.5` |
| V6 | 跨云 KPI 平行 | 同一链同一负载在 AWS EC2 i4i.metal 与 GCP n2-standard 上的 P95 RPC latency / TPS / data_loss_rate 偏差 ≤ ±10% | 同位对照设计，CP-5 baseline | `python3 tests/cp6.2/compare_aws_gcp_kpi.py --aws $AWS_OUT --gcp $GCP_OUT --tol 0.10` |

#### 6.2.4 准入标准（release blocker vs known acceptable）

**Release blocker（任何 1 项不过即阻塞 CP-6 合并）**：
- V1 双写字段缺失任何 1 列
- V2 五阻塞点报表渲染率 < 100%
- V3 archive 命名不含 gcp token
- V5 采样缺失率 > 0.5% 或 data_loss_stats 4 key 缺失
- V6 P95 latency / TPS 偏差 > +20%（GCP 比 AWS 慢 20% 以上）

**Known acceptable（可接受，但需 CHANGELOG 显式记录）**：
- V4 GCP 下若实际触发了 NET 瓶颈，使用 gauge-only 检测，无 allowance 提示属正常（gVNIC 无该 counter）
- V6 GCP TPS 略低 AWS 5~15%（Hyperdisk pre-warming 期）
- V6 GCP 启动后 10 min 内 IOPS ramp-up 期间 P99 latency 短暂飙高（Hyperdisk IOPS pre-warming，预期）

#### 6.2.5 期望的 GCP 独有告警（白名单，不计入 fail）

| 告警 | 出现时机 | 说明 |
|------|----------|------|
| `Hyperdisk IOPS pre-warming, current=XXXX target=80000` | 启动后 0~10 min | 正常 ramp-up 行为 |
| `gVNIC has no allowance counter, falling back to gauge` | 监控启动时一次性 | CP-2.x 已实现 gauge fallback |
| `metadata.google.internal probe took >500ms` | 启动检测时偶发 | GCP metadata 偶发慢，非阻塞 |
| `disk type detected: hyperdisk-extreme, IO baseline = 4 KiB (vs AWS 16 KiB)` | 启动时一次性 | CP-1.4 platform-aware 路径 |

#### 6.2.6 执行步骤（每链 SOP）

```bash
# Step 0: 准备 cloudtop（每链清空旧 OUT）
export CLOUD_PROVIDER=gcp
export CHAIN=solana   # 依次 ethereum bsc base polygon scroll starknet sui
export OUT=/data/bench-out/$CHAIN-$(date +%Y%m%dT%H%M)
mkdir -p "$OUT"

# Step 1: 烟测 5 min 预检
timeout 300 bash blockchain_node_benchmark.sh --chain $CHAIN --duration 5m --out "$OUT/preflight"
python3 tests/cp6.2/check_csv_dual_write.py --csv "$OUT/preflight"/perf_*.csv || exit 1

# Step 2: 24h 正式跑
nohup bash blockchain_node_benchmark.sh --chain $CHAIN --duration 24h --out "$OUT" \
      > "$OUT/run.log" 2>&1 &
BENCH_PID=$!
echo "$BENCH_PID" > "$OUT/bench.pid"

# Step 3: 中段每 4h 巡检
while kill -0 "$BENCH_PID" 2>/dev/null; do
  sleep 14400  # 4h
  python3 tests/cp6.2/check_continuity.py --csv "$OUT"/perf_*.csv --max-gap-pct 0.5 \
    || echo "WARN: gap detected, check $OUT/run.log"
done

# Step 4: 结束后六维 checklist
bash tests/cp6.2/run_all_v_checks.sh "$OUT"

# Step 5: archive + 上传跨云对照
bash tools/benchmark_archiver.sh --out "$OUT"
python3 tests/cp6.2/compare_aws_gcp_kpi.py \
  --aws s3://benchmark-archive/aws/$CHAIN/latest/ \
  --gcp "$OUT" --tol 0.10 \
  | tee "$OUT/kpi_compare.txt"
```

#### 6.2.7 通过准则（全部满足才算 CP-6.2 完结）

- 8 链 × 6 维 = 48 个验证点，release blocker 维度（V1/V2/V3/V5/V6）必须 8/8 全绿
- 每链生成 1 份 `cp6.2-$CHAIN-report.md` 归档到 `analysis-notes/06-gcp-smoke-logs/`
- 8 链 KPI 对比汇总表（`analysis-notes/06-gcp-smoke-logs/SUMMARY.md`）评审通过

---

### CP-6.3 文档更新

#### 6.3.1 范围

CP-6.3 把仓内**所有 AWS-only 表述**改写为平台中立或多云并列；新建 `docs/migration-guide.md`
作为 AWS→GCP 用户 onboarding 入口；归档 analysis-notes/ 临时调研文件；输出 CHANGELOG /
RELEASE NOTES（含 8 个 Round 摘要）。

#### 6.3.2 待改文档清单

| # | 文件 | 当前状态 | CP-6.3 动作 |
|---|------|----------|-------------|
| 1 | `README.md` | AWS-only 表述（grep 已确认存在；EC2 / EBS / ENA 词汇） | 改写为"支持 AWS EC2 + GCP cloudtop 双云"；安装/使用章节并列双云步骤 |
| 2 | `README_ZH.md` | 同上中文版 | 同步翻译改写 |
| 3 | `docs/architecture.md`（如有；无则新建） | 架构图含 ENA/EBS only | 替换为 NIC/Disk 抽象 + 各云 mapping 表 |
| 4 | `docs/metric-dictionary.md`（建议新建） | 缺失 | 列所有 CSV 字段：旧名 + 新名 + 各云语义差异 |
| 5 | `docs/migration-guide.md`（**新建**） | 缺失 | 见 6.3.3 |
| 6 | `CHANGELOG.md` | 缺失或滞后 | 补齐 CP-0~CP-6 各 Round 1 行摘要（见 6.3.4） |
| 7 | `RELEASE_NOTES_vN.M.md`（新建，N.M 为 CP-6 合并后版本号） | 缺失 | 8 Round 摘要 + breaking changes（CSV schema）+ migration-guide 链接 |
| 8 | `analysis-notes/RETROFILL2_PROMPT.md` 等临时调研 | 仍在根目录 | 归档到 `analysis-notes/_archive/2026-Q2-gcp-migration/` |
| 9 | `analysis-notes/00-COVERAGE.md` | CP-N 进度表 | 标记 CP-0~CP-6 全部 ✅ 完结 + 链接 RELEASE_NOTES |
| 10 | `analysis-notes/01-progress.md` | 进度日志 | 追加 CP-6 完成行 |
| 11 | `config/system_config.sh` 头部注释 | 可能仍写 "AWS EBS baseline" | 改 "Cloud disk IO baseline (AWS=16KiB / GCP-PD=4KiB / GCP-Hyperdisk=8KiB)" |

#### 6.3.3 `docs/migration-guide.md` 模板（CP-6.3 新建）

```markdown
# Migration Guide: AWS EC2 → GCP Cloudtop

本指南帮助现有 AWS EC2 用户把 blockchain-node-benchmark 迁移到 GCP 环境。

## 1. 前置条件
- GCP cloudtop 已开通，machine_type ≥ n2-standard-16
- Hyperdisk Extreme ≥ 1.5 TiB 已挂载到 /data
- gVNIC + Tier_1 网络已启用
- Python 3.10+，bash 5+

## 2. 环境变量切换（必读）
| 旧（AWS）| 新（中立 / GCP）| 备注 |
|----------|-----------------|------|
| 默认（无显式 CLOUD_PROVIDER）| `export CLOUD_PROVIDER=gcp` | CP-2.1 引入；不设则自动 metadata probe |
| `AWS_EBS_BASELINE_IO_SIZE_KIB=16` | `CLOUD_IO_BASELINE_KIB=4`（Hyperdisk）/ `=4`（pd-ssd）| CP-1.4 |
| `AWS_METADATA_ENDPOINT=http://169.254.169.254` | `METADATA_ENDPOINT=http://metadata.google.internal` | CP-1.4；GCP 必须带 `Metadata-Flavor: Google` 头 |

## 3. 验证点（10 分钟烟测）
\`\`\`bash
export CLOUD_PROVIDER=gcp
bash blockchain_node_benchmark.sh --chain solana --duration 10m --out /tmp/smoke
# 期望看到:
# - "disk type detected: hyperdisk-extreme, IO baseline = 4 KiB"
# - "gVNIC has no allowance counter, falling back to gauge"
# - perf_*.csv 行数 ≥ 9（10min / 60s）
\`\`\`

## 4. 常见坑
| 现象 | 原因 | 解决 |
|------|------|------|
| `curl: (28) Operation timed out` 在 metadata probe | 漏了 `Metadata-Flavor: Google` 头 | 升到 ≥ CP-2.1 版本 |
| 报表里 NET 阻塞点全无数据 | gVNIC 无 allowance counter，旧版只读 ENA 字段 | 升到 ≥ CP-2.x（gauge fallback） |
| IOPS 在前 10 min 偏低 | Hyperdisk pre-warming | 正常；监控起算点偏移 10 min |
| CSV 字段 `ena_*` 全空 | GCP 模式预期，使用同行 `nic_*` 双写列 | CP-3.x 已实现，下游消费方需读 `nic_*` |

## 5. 回滚
如需回 AWS：`unset CLOUD_PROVIDER`（自动 metadata probe 回 AWS）或 `export CLOUD_PROVIDER=aws`。

## 6. 参考
- 架构图：docs/architecture.md
- Metric 字典：docs/metric-dictionary.md
- 历史调研：analysis-notes/_archive/2026-Q2-gcp-migration/
- 详细变更：CHANGELOG.md（CP-0~CP-6 段）
```

#### 6.3.4 CHANGELOG 8 Round 摘要模板（一句话/Round）

```markdown
## [vN.M] - 2026-05-XX (CP-6 完结)

### Added
- GCP cloudtop 端到端支持（Hyperdisk Extreme + gVNIC + Tier_1）
- docs/migration-guide.md：AWS→GCP onboarding 入口
- docs/metric-dictionary.md：CSV 字段全集 + 各云语义差异

### Changed
- Round 0 (CP-0): 调研冻结仓 snapshot，建立 file-notes/ 共 40+ 文件
- Round 1 (CP-1): config 层 platform 抽象，引入 CLOUD_PROVIDER / CLOUD_IO_BASELINE_KIB 等 5 个中立 env var（旧 AWS_* 双写 alias）
- Round 2 (CP-2): metadata probe + gVNIC gauge fallback，bottleneck_detector 平台分发
- Round 3 (CP-3): CSV header / iostat / ENA monitor 字段双写（旧 ena_*/aws_standard_* + 新 nic_*/standard_*）
- Round 4 (CP-4): visualization 层平台感知，benchmark_archiver 命名含平台 token
- Round 5 (CP-5): report_generator 五阻塞点 100% 覆盖 + data_loss_stats 4 key 契约
- Round 6 (CP-6.1): 删除 5 个 AWS_* env var alias + 函数/字面命名清洁
- Round 6 (CP-6.2): 8 链 × 24h GCP 真机回归全绿
- Round 6 (CP-6.3): 仓内文档多云中立化 + migration-guide 上线

### Removed (Breaking)
- AWS_EBS_BASELINE_IO_SIZE_KIB / AWS_EBS_BASELINE_THROUGHPUT_SIZE_KIB
- AWS_METADATA_ENDPOINT / AWS_METADATA_API_VERSION / AWS_METADATA_TOKEN_TTL
- convert_to_aws_standard_iops / convert_to_aws_standard_throughput 函数
- bottleneck_types 字符串：EBS_AWS_IOPS / EBS_AWS_Throughput / ACCOUNTS_EBS_AWS_*
- CSV 字段：aws_standard_iops（迁移到 standard_iops；历史 CSV 需经 tools/csv_schema_migrate.py 转换）

### Migration
见 docs/migration-guide.md
```

#### 6.3.5 AWS 牌名 → 多云并列 改写范例（3~5 处）

| # | 原文（AWS-only）| 改后（多云并列 / 中立）|
|---|----------------|----------------------|
| 1 | "运行在 AWS EC2 i4i.metal 上，使用 EBS gp3 磁盘" | "支持 AWS EC2 i4i.metal（EBS gp3）和 GCP n2-standard（Hyperdisk Extreme）双云部署" |
| 2 | "ENA 网络监控字段 `ena_bw_in_allowance_exceeded`" | "网络监控字段 `nic_bw_in_allowance_exceeded`（AWS ENA 提供 counter；GCP gVNIC 不提供该 counter，自动 fallback 到 gauge 模式）" |
| 3 | "AWS EBS baseline IO size = 16 KiB" | "Cloud disk IO baseline：AWS EBS = 16 KiB / GCP pd-ssd = 4 KiB / GCP Hyperdisk = 8 KiB（CLOUD_IO_BASELINE_KIB env var 控制）" |
| 4 | "AWS IMDS metadata endpoint：http://169.254.169.254" | "Metadata endpoint：AWS IMDS = `http://169.254.169.254/latest/`；GCP = `http://metadata.google.internal/computeMetadata/v1/`（带 `Metadata-Flavor: Google` 头）" |
| 5 | "归档文件名 `bench-solana-YYYYMMDD.tar.gz`" | "归档文件名 `bench-<platform>-<chain>-YYYYMMDDTHHMM.tar.gz`，其中 `<platform>` ∈ {`aws`, `gcp`}，由 benchmark_archiver 自动识别" |

#### 6.3.6 归档动作（一次性）

```bash
cd analysis-notes
mkdir -p _archive/2026-Q2-gcp-migration
git mv RETROFILL2_PROMPT.md worker-prompt-R*.md worker-prompt-retro.md \
       autopilot-prompt.md early-morning-report.md \
       _archive/2026-Q2-gcp-migration/
# 保留：CORRECTED_PLAN.md / 02-GCP-MIGRATION-TRACKER.md / 00-COVERAGE.md /
#       01-progress.md / file-notes/
git commit -m "CP-6.3: archive GCP migration working files (Q2 2026)"
```

#### 6.3.7 CP-6.3 验收

- `grep -rn "AWS" README.md README_ZH.md docs/` 命中行数 ≤ "AWS EC2" 等并列表述（无 AWS-only 表述残留）
- `docs/migration-guide.md` 存在且评审通过
- `docs/metric-dictionary.md` 字段表覆盖全部 CSV 字段（与 `monitoring/iostat_collector.sh` 实际 header `diff` 后差集为空）
- `CHANGELOG.md` 含 CP-0~CP-6 8 个 Round 摘要
- `analysis-notes/_archive/2026-Q2-gcp-migration/` 含全部临时调研文件
- `analysis-notes/00-COVERAGE.md` CP-0~CP-6 全 ✅

---

## 改造执行规则（必读）

### R-1 改造前必做的 5 个 Gate

1. **Gate-A**：本步骤所有依赖的 CP-N 已完成且测试通过
2. **Gate-B**：grep 全仓确认旧名/旧字段下游消费方已经全部找到（不能漏调用方）
3. **Gate-C**：本步骤所有改动都有"改前 → 改后 → 验证命令"三行
4. **Gate-D**：alias 双写至少保留 1 个 Round（CP-6 才删）
5. **Gate-E**：改完跑现有测试用例（如有）+ fake-target stack 烟测

### 改造原则

- **绝不一次性大改**：每个 CP-N 拆成最小可独立验证的子步骤
- **双写优于硬切**：所有命名/字段改造都先加 alias 再删旧名
- **CLOUD_PROVIDER 单一来源**：禁止任何脚本自行 curl metadata，统一通过 `config/cloud_provider.sh`
- **CSV/JSON 字段 platform-aware 输出**：写方写新名 + 旧名（双写过渡）；读方通过 field_normalizer 归一
- **零业务功能回归**：AWS 模式必须保持 100% 行为不变（这是 alias 存在的根本理由）

### 测试覆盖

每个 CP-N 完成时必须：
1. AWS 模式回归（验证 alias 生效，行为零变化）
2. GCP 模式新路径（验证新分支生效）
3. OTHER fallback 模式（验证降级行为）

---

## 依赖图

```
CP-0 (fake-target + cloud_provider + field_normalizer)
   ↓
CP-1 (utils 层)
   ↓
CP-2 (config 层) ← 阻塞所有下游
   ↓
   ├─→ CP-3 (monitoring) ── 写方契约改造
   │      ↓
   ├─→ CP-4 (tools)
   │
   └─→ CP-5 (analysis + viz) ── 读方契约 + field_normalizer 消费
          ↓
CP-6 (清理 alias + E2E 验证)
```

**关键路径**：CP-0 → CP-1 → CP-2 → CP-3 → CP-5 → CP-6（CP-4 与 CP-3 可并行）

---

## 当前状态

| 阶段 | 状态 |
|---|---|
| CP-0 | ⏸ 待启动 |
| CP-1 | ⏸ |
| CP-2 | ⏸ |
| CP-3 | ⏸ |
| CP-4 | ⏸ |
| CP-5 | ⏸ |
| CP-6 | ⏸ |

最近更新: 2026-05-18 Phase 8a 骨架版生成完毕
