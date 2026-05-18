# 🌐 GCP Migration Tracker — blockchain-node-benchmark

> **强制规则（R20.2）**：每读完一个业务文件，必须 patch 本文件累加阻塞点 + 等价映射 + 命名清单。
>
> 这是 `early-morning-report.md` 的唯一数据源（R20.6）。
>
> baseline commit: `e843571`（未动业务代码）
> 最后更新: 2026-05-18 (Phase E-4: §13.X 9 个阻塞点经 E1+ 抽象层 absorbed + 新增 §14)
>
> **变更日志**：
> - v1.X — Phase 8a-v0.5 回灌 5 新阻塞点 (来源 CORRECTED_PLAN.md CP-0/1/2 subagent 核验) — 新增主表第 13 组 (13.1–13.5)，4×P0 + 1×P2；总览 P0 由 3→7、P2 由 10→11
> - v1.X+1 — Phase 8a-v1.0 回灌 16 新阻塞点 (来源 CP-3/4/5 subagent 核验) — 新增主表 13.6–13.21；CP-3 7 (iostat aws_standard / wc-w 兜底 / ENA CSV 双逗号 / accounts_ebs 条件初始化 / LOGS_DIR 冲突 / MEMORY_SHARE_DIR 多实例 / iostat 项目最深 bake-in) + CP-4 5 (ebs_bottleneck 7-tuple / archiver 时区 / framework_quality 21 字段 DRY / target_generator + fetch_active_accounts 豁免) + CP-5 4 (glob 契约 / run_* basename / keyword 集中化 / comprehensive 'EBS' 4 处)；总览 P0 由 7→9、P1 由 14→22、P2 由 11→14、P3 由 18→20
> - v1.X+2 — Phase E-4 (2026-05-18)：E1+ 抽象层 (config/cloud_provider.sh + 3 provider + 15 getter) absorbed §13.2/13.3/13.4/13.5/13.6/13.12/13.18/13.19/13.21 共 9 个阻塞点；总览 P0 由 9→4 (-5)、P1 由 22→19 (-3)、P2 由 14→13 (-1)、总阻塞由 65→56；新增 §14 抽象层架构契约说明

---

## 总览（实时累计）

| 维度 | 数量 |
|---|---|
| 已分析文件数 | 19 / 38 (50.0% 按文件 / 32.8% 按代码行 9537/29109) — performance_visualizer.py 2026-05-18；Phase 8a-v1.0 CP-3/4/5 subagent 核验回灌 +16 阻塞点 2026-05-18 |
| 🔴 P0 阻塞点（不改 GCP 跑不起来） | 4 (原 9，Phase E-4 经 E1+ 抽象层 absorbed 5: §13.2/13.3/13.5/13.6/13.12) |
| 🟠 P1 阻塞点（不改数据错） | 19 (原 22，Phase E-4 absorbed 3: §13.18/13.19/13.21) |
| 🟡 P2 阻塞点（命名误导） | 13 (原 14，Phase E-4 absorbed 1: §13.4) |
| 🟢 P3 阻塞点（死代码可清理 / 迁移豁免案例） | 20 |
| **✅ E1+ absorbed 阻塞点** | **9** (Phase E-4: §13.2/13.3/13.4/13.5/13.6/13.12/13.18/13.19/13.21；详见 §14) |
| GCP 等价映射条目数 | (待第二章累加) |
| 命名中立化条目数 | 17 (DM-1 至 DM-13 + UC-1 至 UC-4) |
| 新增文件预期 | (待第五章累加) |
| 删除死代码预期行数 | (待第六章累加) |
| **R20.7 字段产出条目数** | **(待 file-notes §6.7 累加)** |
| **R20.7 字段消费条目数** | **(待 file-notes §6.8 累加)** |
| **R20.7 输出文件命名条目数** | **25** (10.3 节累计 — +1 performance_visualizer.py `cpu_ebs_correlation_visualization.png`) |
| **R20.7 全局字段索引（去重后）** | **44** (10.1 节累计 — +2 performance_visualizer.py: `BLOCK_HEIGHT_DIFF_THRESHOLD` env 新发现 + `format_time_axis` 跨文件 module-level 函数契约) |
| **R20.7 极高风险字段数 🔴** | **5** (10.2 节: aws_standard_iops + ENA_ALLOWANCE_FIELDS_STR + ENA_MONITOR_ENABLED + DEPLOYMENT_PLATFORM + ENA_ALLOWANCE_FIELDS_STR 的 #34b 复合视角；user_config.sh #41 与既有 #13 同字段，不重复计数) |

---

## 范围声明（用户 2026-05-18 确认）

- **目标云**：AWS + GCP 双支持（不含 Azure）
- **GCP 磁盘类型**：pd-ssd / pd-balanced / pd-extreme / hyperdisk-extreme / local-ssd 全 5 种
- **GCP 网络**：gVNIC（替代 AWS ENA）+ Tier_1 networking
- **GCP Metadata**：metadata.google.internal + `Metadata-Flavor: Google` header
- **改造哲学**：用户只需在 `config/user_config.sh` 改 `CLOUD_PROVIDER=gcp` 即可切换；同一份代码两云通跑
- **激进路线（Q1=A + Q2=A，用户 2026-05-18 二次确认）**：
  - 全字段中立化（aws_*/ena_*/ebs_aws_* → network_*/nic_*/disk_standard_*），双写过渡期
  - 输出文件名 platform-aware（GCP→`disk_gcp_*.png` / AWS→`ebs_aws_*.png`）

---

## 一、阻塞点主表（按文件 + 等级排序）

> 每个 file-notes 6.2 节的每行都必须 append 到这里。

| # | 来源文件 | file:line | 类型 | 等级 | 阻塞描述 | 改造方案 | 已设计代码？ |
|---|---------|-----------|------|------|----------|----------|--------------|
| 1 | 来自 R4 worker `monitoring_coordinator.sh` 分析 (2026-05-18) | | | | | | |
| 1.1 | monitoring/monitoring_coordinator.sh | L35,L138,L218,L407 | 命名 | P2 | MONITOR_TASKS 键名/case/数组/pkill 含 `ena_network` AWS 字面 | 重命名 `nic_network` 或保留别名 + 新增 `gvnic_network` 键 | ❌ |
| 1.2 | monitoring/monitoring_coordinator.sh | L36,L152,L218,L406 | 命名 | P2 | MONITOR_TASKS 键名/case/数组/pkill 含 `ebs_bottleneck` AWS 字面 | 重命名 `disk_bottleneck` (保留 `ebs_bottleneck` 别名软迁移) | ❌ |
| 1.3 | monitoring/monitoring_coordinator.sh | L139,L148,L319 | 命名 | P3 | 注释/echo 文本含 ENA/EBS 字面 | echo 文本中立化（"NIC monitoring is disabled" / "block device not configured"）| ❌ |
| 1.4 | monitoring/monitoring_coordinator.sh | L140 | 变量名 | P3 | 引用 `$ENA_MONITOR_ENABLED`（本文件仅读不写）| 等待 user_config.sh 中立化 `ENA_MONITOR_ENABLED → NIC_MONITOR_ENABLED` 后同步改本行 | ❌ |
| 1.5 | monitoring/monitoring_coordinator.sh | L36 + L157 | 跨目录 spawn | P1 | `MONITOR_TASKS["ebs_bottleneck"]="ebs_bottleneck_detector.sh"` 但实际脚本在 **tools/** 不在 monitoring/（L157 用 `cd "${script_dir}/../tools"` 跨目录调用） | GCP 版若放别处会断；建议用 platform-aware lookup 函数定位脚本路径 | ❌ |
| 1.6 | monitoring/monitoring_coordinator.sh | L554-562 | 死代码 bug | P1（功能 bug 非 GCP）| `"start_all"` case L560 `start_monitor "bottleneck"` 引用未在 MONITOR_TASKS 中定义的 key（只有 "ebs_bottleneck"），永远落 L86 "Unknown monitoring task" 早退；但 L561 仍打印 "[OK] All monitoring tasks started" 误导用户。L558 多余参数 `${2:-follow_qps_test}` 被 start_monitor 静默忽略（签名只接 $1） | 删除整段 `start_all` case（与 `start` case 功能重复），或修复 `"bottleneck"` → `"ebs_bottleneck"`（改造后 `"disk_bottleneck"`）+ 删多余 $2 占位 | ❌ |
| 1.7 | monitoring/monitoring_coordinator.sh | L605 | 死代码 | P3 | `log_script_success` 在最末行无条件执行，但 `main()` 内 `start` case L494 是 `while true` 死循环 — `start` 命令下 L605 永远到不了；仅 `status/health/stop/help` 等同步命令能触达 | 移到 main() 内各 case 末尾或保留（无害）| ❌ |
| 1.8 | monitoring/monitoring_coordinator.sh | L265, L323-324 | portability bug（非 GCP）| P2 | iostat 状态文件路径硬编码 `/tmp/iostat_*.pid` `/tmp/iostat_*.data` 而非 `${TMP_DIR}/iostat_*.pid` — TMP_DIR 若被外部覆盖到非 /tmp 位置（如自定义工作目录）此处会失效 | 改为 `${TMP_DIR}/iostat_*.pid` / `${TMP_DIR}/iostat_*.data`，与 iostat_collector.sh 实际写入路径对齐 | ❌ |
| 8 | 来自 R8 worker `chart_style_config.py` 分析 (2026-05-18) | | | | | | |
| 8.1 | visualization/chart_style_config.py | L28 | 注释 | P3 | docstring 含 "io2 throughput / AWS environment detection" 字面 | 改 "cloud environment detection"（影响零） | ❌ |
| 8.2 | visualization/chart_style_config.py | L357 | 注释 | P3 | COLORMAPS `'latency'` 注释 "used by EBS charts" | 改 "used by disk performance charts" | ❌ |
| 8.3 | visualization/chart_style_config.py | L358 | 注释 | P3 | COLORMAPS `'utilization'` 注释 "used by EBS charts" | 同上 | ❌ |
| 8.4 | visualization/chart_style_config.py | L389 | 命名（dict key）| P2 | LAYOUT_CONFIGS 含 `'ebs_2x2'` key — **全仓 grep 无任何下游消费**（疑似死代码）| 直接删（无 alias 必要）或改名 `'disk_2x2'` | ❌ |
| 8.5 | visualization/chart_style_config.py | L671 | 注释（docstring）| P3 | `create_device_aware_layout` docstring 含 "EBS device" | 改 "block device" 或 "DATA/ACCOUNTS device" | ❌ |
| 10 | 来自 R8 worker `device_manager.py` 分析 (2026-05-18) | | | | | | |
| 10.1 | visualization/device_manager.py | L26-27 | 字段（patterns key）| P1 | `'data_aws_standard_iops'/'data_aws_standard_throughput_mibs'` 跨文件契约 key | 双写过渡：patterns 同加新键，regex 同时匹配 | ❌ |
| 10.2 | visualization/device_manager.py | L41-42 | 字段（patterns key）| P1 | accounts_ 版同上 | 同上 | ❌ |
| 10.3 | visualization/device_manager.py | L81-85 | 字段（patterns key）| P2 | 5 个 `ena_*_allowance_*` GCP 无字段等价 | GCP 模式 patterns 保留（None 兜底）| ❌ |
| 10.4 | visualization/device_manager.py | L254-257 | env 变量名 | P1 | 4 个 `BOTTLENECK_EBS_*_THRESHOLD` getenv 跨 9 文件契约 | alias 兼容：`os.getenv('DISK_*') or os.getenv('EBS_*', default)` | ❌ |
| 10.5 | visualization/device_manager.py | L260-261 | env 变量名 | P1 | 同 9.4（warning 派生 80%/40%）| 同 9.4 | ❌ |
| 10.6 | visualization/device_manager.py | L301-302/L306-308 | 局部变量名 | P3 | `ebs_latency_threshold/ebs_util_threshold` 局部 + 注释 | 直接改 `disk_*`（0 外部下游）| ❌ |
| 10.7 | visualization/device_manager.py | L347-348 | 字段（list 元素）| P1 | `all_suffixes` 含 `'aws_standard_iops'/'aws_standard_throughput_mibs'` 构建映射 | 双写：list 同含新旧 suffix | ❌ |
| 10.8 | visualization/device_manager.py | L420-421 | 显示字符串 | P2 | `'AWS Standard IOPS'/'AWS Standard Throughput'` 图表 label | platform-aware：`f'{disk_prefix()} Standard IOPS'` | ❌ |
| 10.9 | visualization/device_manager.py | L493/L500 | 字段消费清单 | P1 | validate 函数硬编码 `'data_aws_standard_iops'/'accounts_aws_standard_iops'` | 与 9.1 同步改名 | ❌ |
| 10.10 | visualization/device_manager.py | L21/L36/L75/L116/L339/L342/L484 | 注释 | P3 | 注释含 EBS/AWS 字面 | 替换 "EBS"→"block device", "AWS"→"cloud" | ❌ |
| 10.11 | visualization/device_manager.py | L88-89 | 字段（patterns key）| P3 | 注释自承 "Actual field name" 不匹配 expected — 跨进程契约 fragility | 中立化时与上游 unified_monitor 协商字段名 | ❌ |
| 10.12 | visualization/device_manager.py | L273-282 | 函数 bug（非 GCP）| P1 | `get_baseline_values` 无条件读 `accounts_baseline_iops/throughput`，ACCOUNTS 未配置时 KeyError（grep 调用方 = 0，bug 真实未触发）| 改为 `thresholds.get('accounts_baseline_iops')` 或前置 `is_accounts_configured()` 判断 | ❌ |
| 10.13 | visualization/device_manager.py | L201-218 | 死方法 | P3 | `_check_device_data_exists` grep 全仓 0 外部调用 | 删 | ❌ |
| 10.14 | visualization/device_manager.py | L239-242 vs L473-476 | 死代码（重复）| P3 | `create_chart_title` 与 `create_device_aware_title` 100% 重复 | 保留 L473，删 L239 | ❌ |
| 10.15 | visualization/device_manager.py | L284-293 vs L432-442 | 死代码（重复）| P3 | `get_qps_display_value` 与 `get_qps_actual_value` 几乎重复（仅差 dropna）| 保留 L432，删 L284 | ❌ |
| 10.16 | visualization/device_manager.py | L222/L265/L499 vs 外部 14 处 | 调用一致性 | P2 | 内部 `self.is_accounts_configured()` 不传 df，外部 `DeviceManager.is_accounts_configured(self.df)` 传 df — 历史数据场景下两路径返回值可能不同 | 内部统一传 `self.df`，或写明文档约定 | ❌ |
| 11 | 来自 retro worker `config/system_config.sh` 分析 (2026-05-18) | | | | | | |
| 11.1 | config/system_config.sh | L12 | 枚举 | P0 | DEPLOYMENT_PLATFORM 合法值 `auto/aws/other`，无 `gcp` — 下游 config_loader case 落 unknown 禁用 ENA | 扩展为 `auto/aws/gcp/azure/other`，config_loader.sh:L102-128 加 gcp 分支 (curl metadata.google.internal + Metadata-Flavor: Google) | ❌ |
| 11.2 | config/system_config.sh | L53 | 算法常量 | P1 | AWS_EBS_BASELINE_IO_SIZE_KIB=16 硬编码；GCP Hyperdisk Extreme=4 KiB；下游 ebs_converter.sh:L7 fallback 同值 — GCP IOPS/Throughput 公式系数错 | 新增中立别名 CLOUD_IO_BASELINE_KIB，config_loader case 分发 aws=16/gcp=4 | ❌ |
| 11.3 | config/system_config.sh | L57 | URL | P0 | AWS_METADATA_ENDPOINT 硬编码 `169.254.169.254`；下游 config_loader.sh:L106 curl probe 决定 platform，GCP 永远拿不到响应 → fallback "other" → ENA disabled | 新增 METADATA_ENDPOINT 中立变量 + case 分发；GCP 必须 `-H 'Metadata-Flavor: Google'` 头 | ❌ |
| 11.4 | config/system_config.sh | L59 | URL path 段 | P1 | AWS_METADATA_API_VERSION="latest" path 段；GCP 用 `computeMetadata/v1/` 路径结构不同 | case 分发，或抽到 metadata-helper 函数 | ❌ |
| 11.5 | config/system_config.sh | L71 | 进程名 | P2 | MONITORING_PROCESS_NAMES 含 `ena_network_monitor`；下游 unified_monitor:L556/L1406 word-split 后用于 overhead 统计 — GCP 模式始终 0 虚增列 | 新增 `filter_platform_processes()` 函数；GCP 模式剔除 ena_network_monitor / 加 gvnic_network_monitor | ❌ |
| 11.6 | config/system_config.sh | L53/L54/L57/L58/L59 | 命名 | P2 | 5 个变量 AWS_ 前缀 export；下游 7 处真实消费；ebs_converter.sh 已 fallback 同名锁定命名 | 全部加中立别名 (CLOUD_*/METADATA_*)，AWS_* 作 alias N+1 Round 删除 | ❌ |
| 11.7 | config/system_config.sh | L11/L14/L52/L56 | 注释 | P3 | 4 处注释专提 AWS/ENA 无 GCP 等价说明 | 改 "cloud" 中立化 | ❌ |
| 11.8 | config/system_config.sh | L58 | 死代码 | P3 | AWS_METADATA_TOKEN_TTL=21600 export 后 **0 程序化消费**（IMDSv2 token PUT 路径未启用，config_loader 直接 IMDSv1 GET） | 清理（或保留供未来 IMDSv2 升级时使用） | ❌ |
| 12 | 来自 retro worker `config/user_config.sh` 分析 (2026-05-18) | | | | | | |
| 12.1 | config/user_config.sh | L19 / L25 | 枚举（磁盘类型）| **P0** | `DATA_VOL_TYPE="io2"` / `ACCOUNTS_VOL_TYPE="io2"` 硬编码 AWS io2；GCP 无对应类型；下游 iostat_collector.sh:L152/L178 必须非空否则 log_error 退出 | (a) 注释扩展合法值含 pd-ssd/pd-balanced/pd-extreme/hyperdisk-extreme/local-ssd；(b) L111 调用点改 `configure_${CLOUD_PROVIDER}_volumes` 派发 | ❌ |
| 12.2 | config/user_config.sh | L35 + L117 | 命名（env var）| **P1** | `ENA_MONITOR_ENABLED=true` ENA 是 AWS 专有；14 处真实下游消费（TRACKER 10.1 #13）；GCP 模式继续 true 会触发 ena_network_monitor.sh 启动后 ethtool 取不到字段 → CSV 空列 / KeyError | 双写：L35 同时定义 `NIC_MONITOR_ENABLED` + `ENA_MONITOR_ENABLED="$NIC_MONITOR_ENABLED"` alias；config_loader.sh:L108 platform 检测后按需覆写 | ❌ |
| 12.3 | config/user_config.sh | L40 + L117 | 命名（env var）| **P2** | `EBS_MONITOR_RATE=1` 含 EBS 字面；2 处下游消费；GCP 语义同样适用，不改不会断 | 中立化 `DISK_MONITOR_RATE` + alias `EBS_MONITOR_RATE="$DISK_MONITOR_RATE"` | ❌ |
| 12.4 | config/user_config.sh | L12 / L13-14 | 命名 + 默认值 | **P1** | `LEDGER_DEVICE="nvme1n1"` / `ACCOUNTS_DEVICE="nvme2n1"` 默认值假设 AWS Nitro nvme 命名约定；GCP nvme 命名按 attach 顺序（Hyperdisk 通常 nvme0n*）；19 处下游消费（TRACKER 10.1 #34）含 CSV header 动态拼接 | (a) 注释说明 GCP 建议 `lsblk` 验证 + 推荐 by-id 稳定路径；(b) 可选 `auto_detect_devices()` 函数；变量名已中立无需改 | ❌ |
| 12.5 | config/user_config.sh | L21 / L22 / L27 / L28 | 注释 | **P3** | "Max IOPS for EBS volumes" / "auto-calculated for io2" 注释含 EBS / io2 字面 | 中立化注释 "cloud block volumes" / "io2/pd-extreme/hyperdisk-extreme" | ❌ |
| 12.6 | config/user_config.sh | L31 / L32 | 注释 | **P3** | `EC2 instance` AWS 专有 | 改 "Cloud VM ... EC2/GCE instance type" | ❌ |
| 12.7 | config/user_config.sh | L67-109 + L111 | 算法（函数）| **P1** | `configure_io2_volumes` 硬编码处理 io2；GCP pd-extreme/hyperdisk baseline IO=4 KiB（TRACKER 11.2）公式不同；无 GCP 分支 | L111 改 case 派发；新增 `configure_gcp_extreme_volumes()` 平行函数（依赖 utils/ebs_converter.sh 增 `calculate_pd_extreme_throughput`） | ❌ |
| 12.8 | config/user_config.sh | L70 / L72-77 | 命名（错误消息）| **P3** | 4 处 echo 文本 "EBS converter" / "ebs_converter.sh" 字面 | 待 utils/ebs_converter.sh → utils/disk_converter.sh 重命名后同步改 | ❌ |
| 13 | 来自 Phase 8a-v0.5 subagent 核验回灌 (2026-05-18, CP-0/1/2) — 5 新阻塞点 | | | | | | |
| 13.1 | monitoring/block_height_monitor.sh | L44-45 (cache reader); RPC writer 真位置待 R 期定位 | 跨进程契约（CROSS-PROC-CONTRACT, HI-1）| **P0** | CP-0.3 subagent 核验发现：`block_height_monitor.sh` 不是 RPC writer 而是 **cache 读端**（L44-45 读 cache.json）；之前以为是 RPC 直调点的设计全部错位；真 RPC writer 在别处（候选 `core/master_qps_executor.sh` 或外部 daemon） | R 期定位真 writer 后回填 file:line；fake-target stack mock 表 M3 行的 RPC 接口需重新归属 → 详见 PLAN CP-0.3 | ❌ |
| 13.2 | config/config_loader.sh | L72-78 (source system_config.sh) + L102-128 (detect_deployment_platform 后置) | source 顺序冲突 | **P0** | CP-2.3 subagent 实证：config_loader.sh L72-78 先 source system_config.sh，此时 `CLOUD_PROVIDER` 仍为 "auto"，导致 system_config.sh 内所有 `case "${CLOUD_PROVIDER:-...}"` 首次加载落 **aws 默认分支**；detect_deployment_platform 后置无人重新触发 case → CP-2.1.2/2.1.3/2.1.4/2.1.5（METADATA_ENDPOINT / METADATA_API_PATH / CLOUD_IO_BASELINE_KIB / MONITORING_PROCESS_NAMES）全部首次加载失效 | 在 config_loader.sh `detect_deployment_platform` 完成后加 re-evaluate hook，重 source system_config.sh；或改 system_config.sh 用 lazy getter 函数 → 详见 PLAN CP-2.3（伪代码已就绪） | ✅ E1+ absorbed (§14.1/§14.2: system_config.sh 不再静态定义 platform-aware 变量，业务方调懒求值 getter `get_metadata_endpoint` / `get_baseline_io_kib` 等，source 顺序冲突从根本消除) |
| 13.3 | config/config_loader.sh | L829 | 字段独立 fallback | **P0** | CP-2.3 subagent 发现：L829 `ENA_ALLOWANCE_FIELDS=${ENA_ALLOWANCE_FIELDS:-"..."}` **独立于** system_config.sh:L15-22 的数组定义，是 vegeta 子进程的兜底入口；仅改 system_config 不够 | L829 也要做平台分发 + 双写（旧名 `ENA_ALLOWANCE_FIELDS` + 新名 `NIC_ALLOWANCE_FIELDS`），与 system_config 同步 → 详见 PLAN CP-2.3.4 | ✅ E1+ absorbed (§14.1: config_loader.sh 单源化 `ENA_ALLOWANCE_FIELDS_STR=$(get_nic_allowance_fields)`，独立 fallback 消除) |
| 13.4 | config/config_loader.sh | `detect_network_interface` 函数体（5 处使用 `ena_interfaces` 局部变量 + 函数注释 "ENA network interface"）| 命名（局部变量 + 注释）| **P2** | CP-2.3 subagent：局部命名 `ena_interfaces` 误导，但正则 `(eth|ens|enp)` 已平台无关；grep 验证零外部 reader（纯局部）| 函数内统一改 `nic_interfaces` + 注释改 "NIC interface (ENA/gVNIC/virtio)"；无下游契约风险 → 详见 PLAN CP-2.3.3 | ✅ E1+ absorbed (§14.2: `get_nic_driver()` getter 集中化 + 局部命名一并 nic_interfaces) |
| 13.5 | config/system_config.sh + config/config_loader.sh (metadata curl 调用点) | system_config.sh metadata 变量段（CP-2.1 设计区） | header 字段缺失 | **P0** | CP-2.1 subagent 核验：GCP IMDS **强制要求** `Metadata-Flavor: Google` header，原设计只切 endpoint（11.3）漏掉 header；GCP 模式下所有 metadata 探测请求会被 GCE 拒绝 → fallback "other" → ENA disabled（与 11.3 复合后果） | 新增 `METADATA_HEADER` 中立变量（GCP="Metadata-Flavor: Google" / AWS=""）；所有 metadata curl 调用点 `curl -H "$METADATA_HEADER" ...`，shell 对空串 `-H ""` 自动跳过 → 详见 PLAN CP-2.1（与 11.3 配套落地） | ✅ E1+ absorbed (§14.2: 所有 metadata curl 调用点统一 `curl -H "$(get_metadata_header)" "$(get_metadata_endpoint)/$(get_metadata_api_path)"`) |
| 13.6 — 13.21 | 来自 Phase 8a-v1.0 subagent 核验回灌 (2026-05-18, CP-3/4/5) — 16 新阻塞点 | | | | | | |
| 13.6 | monitoring/unified_monitor.sh + monitoring/iostat_collector.sh | unified_monitor.sh:144 / iostat_collector.sh:144 | 字段（CSV header 字面） | **P0** | CP-3.1 subagent 实证：`${prefix}_aws_standard_iops` / `${prefix}_aws_standard_throughput_mibs` 字段名硬编码 "aws_standard"；即使在 GCP 上跑字段名仍是 aws_*；下游 device_manager.py / report_generator.py 全按字面量解析 → 跨平台字段断链 | CSV header 双写：`_aws_standard_*`（兼容保留）+ `_baseline_*`（中立新名）；读端经 utils/field_normalizer 归一化 → 详见 PLAN CP-3.1 §13.X #1 + CP-3.5.a #1 | ✅ E1+ absorbed (§14.2: CSV header 改 `${prefix}_$(get_disk_field_prefix)_iops` 动态拼接，AWS→aws_standard / GCP→pd_standard / Other→standard，单源消除硬编码) |
| 13.7 | monitoring/unified_monitor.sh | L2080 兜底分支 `printf "0,%.0s"` | 字段数一致性（CSV 列对齐） | **P1** | CP-3.1 subagent：兜底数量用 `wc -w` 计 `ENA_ALLOWANCE_FIELDS_STR` 字数；GCP 路径必须保证兜底字段数与 `build_nic_header` 输出列数严格一致，否则 CSV 错位、下游 parser 错位 | unit test 覆盖 + GCP 分支显式 `count=$(echo "$NIC_FIELDS_STR" \| wc -w)`；CSV 字段数断言入 framework_data_quality_checker → 详见 PLAN CP-3.1 §13.X #2 | ❌ |
| 13.8 | monitoring/ena_network_monitor.sh | L121 拼接起始 + L145 echo | CSV 数据行错位（双逗号） | **P1** | CP-3.2 subagent：`ena_stats="$ena_stats,$value"` 起始 `ena_stats` 为空时第一次产生 `,值` 形式；L145 echo `"...$ena_stats,..."` 会出现 `,,` 双逗号；虽 AWS 路径已存在但 GCP 重写要避坑 | 起始 `ena_stats` 用首字段不带逗号拼接，后续 append 才带逗号；或改用 array+IFS 拼接 → 详见 PLAN CP-3.2 §13.X #3 | ❌ |
| 13.9 | monitoring/bottleneck_detector.sh | L163-168 数组定义 + L240-243 / L269-272 条件初始化 | jq 读端 schema 假设 | **P1** | CP-3.3 subagent：`BOTTLENECK_COUNTERS` 中 `accounts_ebs_*` 系列仅当 ACCOUNTS_DEVICE 配置时初始化；jq 读端可能假设 key 永远存在；GCP/AWS 双方都存在此条件初始化问题 | alias 双写时把 `accounts_disk_*` 一并覆盖；jq 读端用 `// 0` 默认值；或无条件初始化为 0 → 详见 PLAN CP-3.3 §13.X #4 | ❌ |
| 13.10 | monitoring/monitoring_coordinator.sh | L15 `LOGS_DIR=${LOGS_DIR:-"/tmp/blockchain-node-benchmark/logs"}` | 多实例并行路径冲突 | **P1** | CP-3.4 subagent：硬编码 fallback 路径；AWS + GCP 同主机并行 benchmark 时两实例写同一 logs 目录 → 数据互相覆盖 | 改 `${TMP_BASE_DIR:-/tmp/blockchain-node-benchmark}-${CLOUD_PROVIDER}/logs`；与 iostat_collector / archiver 路径策略对齐 → 详见 PLAN CP-3.4 §13.X #5 | ❌ |
| 13.11 | monitoring/block_height_monitor.sh | L44-45 `rm -f "$MEMORY_SHARE_DIR"/block_height_monitor_cache.json` + `rm -f "$BASE_MEMORY_DIR"/node_health_*.cache` | 多实例并行路径冲突 | **P1** | CP-3.5.b subagent：MEMORY_SHARE_DIR / BASE_MEMORY_DIR 未 platform-suffixed；多实例并行启动 cache 互删 | platform-suffixed：`MEMORY_SHARE_DIR=${MEMORY_SHARE_DIR}-${CLOUD_PROVIDER}`；与 13.10 路径策略统一 → 详见 PLAN CP-3.5 §13.X #6 | ❌ |
| 13.12 | monitoring/iostat_collector.sh | L144 `${prefix}_aws_standard_iops` 字段名生成端 | 字段（项目最深 AWS bake-in） | **P0** | CP-3.5.a subagent：iostat_collector.sh:L144 是整个项目最深的 AWS bake-in 之一（writer 上游源头），影响下游 device_manager.py / report_generator.py / ebs_chart_generator.py 全链路；与 13.6 是同一字段在不同文件的 writer 端 | 与 13.6 同步：iostat_collector 字段生成端必须先做双写，下游 CSV header 才有新名可消费；列入 CP-3.5.a #1 P0 → 详见 PLAN CP-3.5.a §13.X #7 | ✅ E1+ absorbed (§14.2: 与 §13.6 同源消除，iostat_collector.sh:L144 字段生成端同样用 `${prefix}_$(get_disk_field_prefix)_iops`，writer 上游单源化) |
| 13.13 | tools/ebs_bottleneck_detector.sh | L156 输出 7-tuple + L264 / L301 read 解构端 | 跨进程位置参数契约 | **P1** | CP-4.2 subagent：L156 输出 7-tuple 包含 `aws_standard_iops, aws_standard_throughput` 作为位置参数（非 keyed JSON）；下游 L264 / L301 `IFS=',' read -r ... aws_standard_iops aws_standard_throughput ...` 解；改字段名时**位置不变即可**，但 7-tuple 第 3/4 位若改 `baseline_iops/throughput` 需在 L264/L301 同步重命名局部变量 | 位置参数保持，局部变量名同步改 alias；console 告警字面 `EBS BOTTLENECK DETECTED` 改 `DISK BOTTLENECK DETECTED` 加 alias log line 双发 → 详见 PLAN CP-4.2 §13.1 | ❌ |
| 13.14 | tools/benchmark_archiver.sh | L362-363 `compare_tests` 输出 `start_time / end_time` jq read | 时区跨平台对比失真 | **P2** | CP-4.3 subagent：若 CP-2.1 给 test_summary 加时区敏感 timestamp（GCP 默认 UTC vs AWS region-local），跨平台对比时间显示会失真；当前 archiver 业务零 AWS 耦合，但归档命名 + history index + compare 是跨平台关键入口 | test_summary.json 强制加 `"timezone": "UTC"` 字段；compare 显示统一 UTC；归档目录 `<platform>_run_${n}_${ts}` 前缀注入（方案 A）→ 详见 PLAN CP-4.3 §13.2 | ❌ |
| 13.15 | tools/framework_data_quality_checker.sh | L352 / L356 / L358 三处 21-字段 header 模板 | DRY 违反（技术债） | **P2** | CP-4.4 subagent：三处 21-字段 header 模板完全重复（DATA / ACCOUNTS / ACCOUNTS-only），任何字段名改动需 3 处同步；commit `e843571` 已存在的技术债；CP-4.4 改造时应抽函数 `generate_device_header(device_prefix, device_name)` 但「保 commit 不动」原则下不抽，仅在 patch comment 标注 + 文档登记 | 改造时同步 3 处；未来重构抽 `generate_device_header()` 共享函数；附 L427 glob `monitoring_overhead_*.csv` 兼容验证（writer 若改前置 prefix 会漏匹配） → 详见 PLAN CP-4.4 §13.3 | ❌ |
| 13.16 | tools/target_generator.sh | 全文件（382 行）| 迁移豁免案例（满分典范） | **P3** | CP-4.5 subagent 实证：`grep -cE "AWS\|aws\|EBS\|ebs\|EC2\|ec2\|nitro\|metadata\|boto3\|169\\.254"` = **0**；8 链对称完整（solana/ethereum/bsc/base/polygon/scroll/starknet/sui）；输出 vegeta target 与平台无关 | 本文件**零改动**；登记为「迁移友好性满分典范」；验证命令：`grep -c ... = 0` + 8 链 BLOCKCHAIN_NODE 烟测 → 详见 PLAN CP-4.5 §13.4 | ✅ (无需改) |
| 13.17 | tools/fetch_active_accounts.py | 全文件（841 行）| 迁移豁免案例（Python 工具满分典范） | **P3** | CP-4.6 subagent 实证：`grep -cE "boto3\|AWS\|aws_\|EC2\|ec2\|169\\.254\|metadata\\.google\|imdsv"` = **0**；唯一外部依赖 `aiohttp`（通用 HTTP，无云 SDK）；输出 JSON key 区块链原生字段（address/slot/lamports）已平台中立 | 本文件**零改动**；登记为「Python 工具迁移豁免案例」；验证：`grep -c ... = 0` + `ast.parse` 语法 OK → 详见 PLAN CP-4.6 §13.5 | ✅ (无需改) |
| 13.18 | visualization/report_generator.py | L1359 `_find_latest_monitoring_overhead_file` glob | 跨进程隐式契约 | **P1** | CP-5.2 subagent (阻塞点②)：本 method 的 glob pattern 与 `tools/benchmark_archiver.sh` 归档目录命名规则 + `monitoring/unified_monitor.sh` 写入文件名形成隐式契约；TRACKER 未列出此读端 glob ↔ writer 命名耦合 | glob pattern 集中至 `MONITORING_OVERHEAD_GLOB_PATTERNS` 常量；archiver 命名约定改动需同步本 glob；与 13.14 / 13.20 配套 → 详见 PLAN CP-5 §13.1 | ✅ E1+ absorbed (§14.6/CP-5.2: Python facade `utils/cloud_provider.py` 提供 `get_archive_dir_prefix()`，glob pattern 单源化到 `f"{get_archive_dir_prefix()}_*/..."`) |
| 13.19 | visualization/report_generator.py | L3670 `_discover_chart_files` `run_*` basename 启发式 | 跨 reader/writer 命名前缀契约 | **P1** | CP-5.2 subagent (阻塞点⑤)：`run_*` basename 启发式与 archiver 归档目录前缀强耦合；archiver 改前缀 `<platform>_run_${n}_${ts}`（13.14 方案 A）后此 basename 匹配会断；TRACKER 未记录 `ARCHIVE_DIR_PREFIXES` 跨 reader/writer 契约 | 抽 `ARCHIVE_DIR_PREFIXES = ('run_', 'aws_run_', 'gcp_run_')` 常量；reader/writer 双向引用同一常量；与 13.14 同步落地 → 详见 PLAN CP-5 §13.2 | ✅ E1+ absorbed (§14.6/CP-5.2: `run_*` basename 启发式同源化到 `get_archive_dir_prefix()` Python facade，reader/writer 双向引用同一 getter) |
| 13.20 | visualization/report_generator.py | L1359 + L3731 (`_categorize_charts`) 散落常量 | 关键字常量集中化（可维护性） | **P2** | CP-5.2 subagent (阻塞点②④)：`MONITORING_OVERHEAD_GLOB_PATTERNS` / `CHART_CATEGORY_KEYWORDS` 等关键字散落在 method 内；维护时易漏；跨平台改造需统一入口 | 提取为模块级常量字典；与 13.18 / 13.19 一起重构；patch comment 标注「保 commit 不动」原则下仅文档登记，未来重构落地 → 详见 PLAN CP-5 §13.3 | ❌ |
| 13.21 | analysis/comprehensive_analysis.py | L539 / L588 / L636 / L684 共 4 处 | 跨方法共享字面（字符串硬编码） | **P1** | CP-5.7.2 subagent (#3)：`bottleneck_types` 字符串 `'EBS'` 在 4 处独立硬编码；GCP 模式下显示 `'EBS'` 标签不符语义；改动需 4 处同步否则漏改 | 抽 `BOTTLENECK_TYPE_LABELS = {'aws': 'EBS', 'gcp': 'Disk'}` 常量；4 处统一 `BOTTLENECK_TYPE_LABELS[CLOUD_PROVIDER]`；与 13.13 console 文案同步 → 详见 PLAN CP-5 §13.4 | ✅ E1+ absorbed (§14.2/§14.6: `get_bottleneck_label()` Python facade 集中化，comprehensive_analysis.py L539/L588/L636/L684 共 4 处统一调用，'EBS' 字面消除) |
| _待 Phase 3 回填 12 文件 + cron 推 26 文件_ | | | | | | | |

**类型分类**：
- URL（文档链接 / endpoint）
- 算法（io2 throughput 等 AWS 专有公式）
- 枚举（磁盘类型 / 网络类型 case 值）
- 命名（AWS_ 前缀 / aws_ 字段名）
- 常量（baseline 数值如 IO_SIZE_KIB=16）
- 函数（recommend_ebs_type 等 AWS-only 函数）
- 进程（ena_network_monitor 等 AWS-only 进程）
- header（curl 请求头 Metadata-Flavor 差异）
- 字段（CSV/JSON 字段名差异）

---

## 二、GCP 等价物映射（全局唯一字典）

> 每个 file-notes 6.4 节的映射必须 merge 到这里，去重。

### 2.1 磁盘类型映射

| AWS 类型 | GCP 等价类型 | 关键性能差异 | 来源文件 |
|----------|--------------|--------------|----------|
| _待累加_ | | | |

### 2.2 网络监控映射

| AWS 网络概念 | GCP 等价 | 字段差异 | 来源文件 |
|--------------|----------|----------|----------|
| _待累加_ | | | |

### 2.3 Metadata Service 映射

| AWS Metadata | GCP Metadata | Header 差异 | 来源文件 |
|--------------|--------------|-------------|----------|
| _待累加_ | | | |

### 2.4 文档 URL 映射

| AWS 文档 | GCP 文档 | 主题 | 来源文件 |
|----------|----------|------|----------|
| _待累加_ | | | |

### 2.5 命令 / 工具映射

| AWS 工具 | GCP 等价 | 用途 | 来源文件 |
|----------|----------|------|----------|
| _待累加（如 aws-cli vs gcloud）_ | | | |

---

## 三、命名中立化清单

> 每个 file-notes 6.6 节必须 append 到这里。

| # | 旧名（AWS-only） | 新名（中立） | 别名保留？ | 影响范围（下游引用数）| 来源文件 |
|---|------------------|--------------|------------|------------------------|----------|
| DM-1 | `data_aws_standard_iops` (patterns key) | `data_disk_standard_iops` | ✅ 双写 | 7 文件 | visualization/device_manager.py:L26 |
| DM-2 | `data_aws_standard_throughput_mibs` (patterns key) | `data_disk_standard_throughput_mibs` | ✅ 双写 | 7 文件 | visualization/device_manager.py:L27 |
| DM-3 | `accounts_aws_standard_iops` (patterns key) | `accounts_disk_standard_iops` | ✅ 双写 | 7 文件 | visualization/device_manager.py:L41 |
| DM-4 | `accounts_aws_standard_throughput_mibs` (patterns key) | `accounts_disk_standard_throughput_mibs` | ✅ 双写 | 7 文件 | visualization/device_manager.py:L42 |
| DM-5 | `BOTTLENECK_EBS_UTIL_THRESHOLD` (env) | `BOTTLENECK_DISK_UTIL_THRESHOLD` | ✅ alias | 9 文件 | visualization/device_manager.py:L254/L260 |
| DM-6 | `BOTTLENECK_EBS_LATENCY_THRESHOLD` (env) | `BOTTLENECK_DISK_LATENCY_THRESHOLD` | ✅ alias | 9 文件 | visualization/device_manager.py:L255/L261 |
| DM-7 | `BOTTLENECK_EBS_IOPS_THRESHOLD` (env) | `BOTTLENECK_DISK_IOPS_THRESHOLD` | ✅ alias | 9 文件 | visualization/device_manager.py:L256 |
| DM-8 | `BOTTLENECK_EBS_THROUGHPUT_THRESHOLD` (env) | `BOTTLENECK_DISK_THROUGHPUT_THRESHOLD` | ✅ alias | 9 文件 | visualization/device_manager.py:L257 |
| DM-9 | `ebs_latency_threshold` / `ebs_util_threshold` (Python 局部) | `disk_*` | ❌ 直接改 | 0 外部 | visualization/device_manager.py:L301-302 |
| DM-10 | `'AWS Standard IOPS'` / `'AWS Standard Throughput'` (label) | `f'{disk_prefix()} Standard *'` | ❌ 直接改 | 仅图表 label | visualization/device_manager.py:L420/L421 |
| DM-11 | `get_ebs_device_data` (method) | `get_disk_device_data` | ✅ alias | 0 外部 grep 命中 | visualization/device_manager.py:L478 |
| DM-12 | `validate_ebs_configuration` (method) | `validate_disk_configuration` | ✅ alias | 0 外部 grep 命中 | visualization/device_manager.py:L483 |
| DM-13 | `build_field_mapping` 内 suffix `'aws_standard_*'` | `'disk_standard_*'` | ✅ 双写 | 7 文件 | visualization/device_manager.py:L347-348 |
| 2 | aws_standard_iops → disk_standard_iops (CSV 列) | R6 (本 worker 已识别 5 reader) | 跨 R3 (iostat_collector 写方改造) + R4/R5 全 reader (master_qps_executor + bottleneck_detector + ebs_chart_generator + report_generator + device_manager + 本文件) 都切到新名 | +1 Round (5 层 reader 全 grep `aws_standard_iops` 仅剩本注释占位时) | 全 reader grep 0 命中 + ebs_chart_generator.py L116/L118 等 field map alias 移除 |
| 3 | aws_standard_throughput_mibs → disk_standard_throughput_mibs | 同 #2 | 同 #2 | 同 #2 | 同 #2 |
| UC-1 | `ENA_MONITOR_ENABLED` (env) | `NIC_MONITOR_ENABLED` | ✅ 双写 alias L35 | 9 文件 / 14 处 | config/user_config.sh:L35 + L117 (retro 2026-05-18) |
| UC-2 | `EBS_MONITOR_RATE` (env) | `DISK_MONITOR_RATE` | ✅ 双写 alias L40 | 2 处 | config/user_config.sh:L40 + L117 |
| UC-3 | `configure_io2_volumes()` (函数名) | 保留 + 平行新增 `configure_gcp_extreme_volumes()` + L111 case 派发 `configure_${CLOUD_PROVIDER}_volumes` | ❌ 不改原名（io2 AWS 名实相符）| 仅 user_config.sh L111 调用点 | config/user_config.sh:L67-109 + L111 |
| UC-4 | 注释 `"EBS volumes"` / `"io2"` / `"EC2 instance"` / `"EBS converter"` (4 类注释字面) | 中立化为 "cloud block volumes" / "io2/pd-extreme/hyperdisk-extreme" / "Cloud VM (EC2/GCE)" / `<待 ebs_converter.sh 重命名后同步>` | ❌ 注释直接改 | 仅本文件 + 错误消息 | config/user_config.sh:L21/L22/L27/L28/L31/L32/L70/L72-77 |
| _待累加_ | | | | | |

---

## 四、CLOUD_PROVIDER 切换点清单

> 每个 file-notes 6.3 节必须 append 到这里。

| # | 文件 | 行号 | 切换内容 | 改造示例 |
|---|------|------|----------|----------|
| _待累加_ | | | | |

---

## 五、需新增的文件

> 框架现有结构需补的 GCP 等价实现。

| # | 新增文件路径 | 仿照的 AWS 对应文件 | 用途 | 预估行数 | 来源分析 |
|---|--------------|--------------------|------|----------|----------|
| _待累加（如 monitoring/gvnic_network_monitor.sh）_ | | | | | |

---

## 六、改造工作量预估（实时累加）

| 层 | 配置改动行数 | 业务改动行数 | 新增文件 | 累计 |
|----|--------------|--------------|----------|------|
| config/ | 0 | 0 | 0 | 0 |
| core/ | 0 | 0 | 0 | 0 |
| utils/ | 0 | 0 | 0 | 0 |
| monitoring/ | 0 | 0 | 0 | 0 |
| tools/ | 0 | 0 | 0 | 0 |
| analysis/ | 0 | 0 | 0 | 0 |
| visualization/ | 0 | 0 | 0 | 0 |
| **总计** | **0** | **0** | **0** | **0** |

---

## 七、改造执行依赖图（待全分析完成后绘制）

```
[ Phase A: config 层 ]
   └─ user_config.sh 加 CLOUD_PROVIDER
      └─ config_loader.sh::detect_deployment_platform 加 GCP 分支
         └─ system_config.sh 加 case 分发平台参数

[ Phase B: utils 基础层 ]
   └─ ebs_converter.sh → disk_converter.sh
      └─ ena_field_accessor.py → nic_field_accessor.py
         └─ unit_converter.py 加 GCP IO baseline

[ Phase C: monitoring 数据采集层 ]
   └─ 包装 ena_network_monitor.sh 加 platform gate
      └─ 新增 gvnic_network_monitor.sh
         └─ iostat_collector.sh / unified_monitor.sh 字段中立化

[ Phase D: tools / analysis / visualization ]
   └─ 命名中立化 + 报告渲染 platform-aware
```

_（每个箭头节点完成后，从 TRACKER 提取真实数据填充具体改造步骤）_

---

## 八、写入约定（R20.2 + R20.7.2 强制）

每个 file-notes 写完后立即 patch 本文件：
1. **一、阻塞点主表** append 该文件 6.2 节所有行
2. **二、等价映射** merge 该文件 6.4 节（去重，相同 AWS 概念只保留 1 行，多文件合并 来源 列）
3. **三、命名清单** append 该文件 6.6 节所有行
4. **四、切换点** append 该文件 6.3 节
5. **五、新增文件** append（如果该文件分析触发新文件需求）
6. **六、工作量** 累加该文件 6.5 节数字
7. **十、数据契约** append 该文件 6.7/6.8/6.9 + 更新 10.1 全局索引 + 10.2 风险评分 + 10.4 双写计划（R20.7.2）
8. **总览顶部** 重算 P0/P1/P2/P3 计数 + 已分析文件数 + R20.7 5 个新指标

---

## 九、TRACKER 完整性自检（R20.5 + R20.7.5 触发）

每轮末 R17.5 必须运行：
```bash
# 1. 已分析文件数 == COVERAGE.md FULL 数
# 2. 阻塞点总数 == sum(每个 file-notes 6.2 行数)
# 3. 命名清单条目数 == sum(每个 file-notes 6.6 行数)
# 4. R20.7 全局字段索引 == 字段产出条目数（去重后）
# 5. R20.7 字段消费总数 == 各 file-notes 6.8 行数之和
# 6. R20.7 输出文件命名总数 == 各 file-notes 6.9 行数之和
# 7. 任一不吻合 → 必有遗漏，本 Round 作废重做
```

---

## 十、数据契约维度（R20.7 ⭐ 用户激进路线 A+A）

> 字段名是跨进程契约。改 L1 不改 L3 → KeyError。本章是最关键的"改造前必读"。

### 10.1 全局字段索引（按字段名维护写方 + 读方双向链表）

| # | 字段名（AWS 命名）| 写方 file:line | 读方 file:line（多个用 ; 分隔）| 类型 | 中立等价名 | 双写过渡？|
|---|---------------------|-----------------|----------------------------------|------|------------|-----------|
| 1 | aws_standard_iops | utils/unit_converter.py:L263; monitoring/iostat_collector.sh:L119/121/123/127/144 (动态拼接 `${prefix}_aws_standard_iops`) | core/master_qps_executor.sh:L312/334/684 (R8 retro 2026-05-18 确认 = jq path 3 处 reader，含 6.10 安全性评估); monitoring/bottleneck_detector.sh:L36/56/872/899/1002; tools/ebs_bottleneck_detector.sh:L135/143/151/156-307; tools/framework_data_quality_checker.sh:L352-358; visualization/device_manager.py:L26/L41/L347-348/L420/L493/L500 (patterns + suffix + label + validate) | iops | disk_standard_iops | ✅ 必须双写 |
| 2 | aws_standard_gbps | utils/unit_converter.py:L174 | (无下游) | net | network_standard_gbps | ❌ 直接改 |
| 3 | aws_display_mbps | utils/unit_converter.py:L175 | (无下游) | net | network_display_mbps | ❌ 直接改 |
| 4 | aws_rx_gbps | utils/unit_converter.py:L222 | (无下游) | net | network_rx_gbps | ❌ 直接改 |
| 5 | aws_tx_gbps | utils/unit_converter.py:L223 | (无下游) | net | network_tx_gbps | ❌ 直接改 |
| 6a | MONITOR_TASKS["ena_network"] (bash assoc array key) | monitoring/monitoring_coordinator.sh:L35 (定义) + L138/L218/L407 (引用) | (本文件内自引用 4 处，**无外部读** — grep `MONITOR_TASKS\["ena_network"\]` 外部 = 0) | bash key | MONITOR_TASKS["nic_network"] 或保留 + 新增 `["gvnic_network"]` | ❌ 直接改本文件 4 处 |
| 6b | MONITOR_TASKS["ebs_bottleneck"] (bash assoc array key) | monitoring/monitoring_coordinator.sh:L36 (定义) + L152/L218/L406 (引用) | (本文件内自引用 4 处，无外部读) | bash key | MONITOR_TASKS["disk_bottleneck"] | ❌ 直接改 (可选保留 `ebs_bottleneck` 别名) |
| 6c | monitoring_status.json.coordinator_start_time | monitoring/monitoring_coordinator.sh:L50 (写) | **0 外部读** (grep `coordinator_start_time` 全仓 = 仅本文件) | JSON 字段 | (已中立) | N/A 死契约 |
| 6d | monitoring_status.json.active_monitors | monitoring/monitoring_coordinator.sh:L51,L345 (写) | **0 外部读** (grep 全仓 = 仅本文件) | JSON 字段 | (已中立) | N/A 死契约 |
| 6e | monitor_pids.txt 行 `name:pid` | monitoring/monitoring_coordinator.sh:L167 (写) | monitoring/monitoring_coordinator.sh:L183, L530-541 (本文件自读) | text/PID 表 | (格式中立；name 字段值仍含 ena/ebs 字面) | N/A — name 改归 6a/6b 项处理 |
| (注: 第 13 项 ENA_MONITOR_ENABLED 已含 monitoring_coordinator.sh:L140 新消费方，无需再加新行)
| 6 | aws_total_gbps | utils/unit_converter.py:L224/L447(test) | (无外部下游) | net | network_total_gbps | ❌ 直接改 |
| 7 | aws_standard_throughput_mibs | monitoring/iostat_collector.sh:L88/99/101/105/127/144 (动态拼接 `${prefix}_aws_standard_throughput_mibs`) | core/master_qps_executor.sh:L322/344/685 (R8 retro 2026-05-18 确认 = jq path 3 处 reader); tools/ebs_bottleneck_detector.sh:L136/156-307; tools/framework_data_quality_checker.sh:L352-358; visualization/device_manager.py:L27/L42/L347-348/L421 (patterns + suffix + label) | iops | disk_standard_throughput_mibs | ✅ 必须双写（R4 worker iostat_collector.sh 已精确化下游：4 个独立文件 / ~10 处字面；R8 worker device_manager.py 追加 visualization 层 patterns）|
| 8 | BOTTLENECK_EBS_UTIL_THRESHOLD | config/internal_config.sh:L17/L70 | tools/ebs_bottleneck_detector.sh; tools/ebs_analyzer.sh; core/master_qps_executor.sh; monitoring/bottleneck_detector.sh; monitoring/unified_monitor.sh; visualization/ebs_chart_generator.py; visualization/performance_visualizer.py:L1964/L1965 (R8 worker 精确化); visualization/device_manager.py:L254/L260 | disk | BOTTLENECK_DISK_UTIL_THRESHOLD | ✅ alias 兼容 |
| 9 | BOTTLENECK_EBS_LATENCY_THRESHOLD | config/internal_config.sh:L18/L71 | (同 #8 9 文件链); visualization/device_manager.py:L255/L261 (R8 worker 追加); visualization/performance_visualizer.py:L693 (R8 worker 精确化) | disk | BOTTLENECK_DISK_LATENCY_THRESHOLD | ✅ alias |
| 10 | BOTTLENECK_EBS_IOPS_THRESHOLD | config/internal_config.sh:L21/L71 | (同 #8); visualization/device_manager.py:L256 (R8 worker 追加) | disk | BOTTLENECK_DISK_IOPS_THRESHOLD | ✅ alias |
| 11 | BOTTLENECK_EBS_THROUGHPUT_THRESHOLD | config/internal_config.sh:L22/L71 | (同 #8); visualization/device_manager.py:L257 (R8 worker 追加) | disk | BOTTLENECK_DISK_THROUGHPUT_THRESHOLD | ✅ alias |
| 12 | ENA_ALLOWANCE_FIELDS_STR (env var, word-split 数组源) | config/system_config.sh:L109 (export) | monitoring/ena_network_monitor.sh:L63/92/118/217; monitoring/bottleneck_detector.sh:L471; monitoring/unified_monitor.sh:L501/516/532/1908/2079; tools/framework_data_quality_checker.sh:L376-377; utils/ena_field_accessor.py:L60/76 | net | NIC_ALLOWANCE_FIELDS_STR | ✅ 必须双写 |
| 13 | ENA_MONITOR_ENABLED (env var) | config/user_config.sh:L35; config/config_loader.sh:L108-128 (export) | monitoring/ena_network_monitor.sh:L38; monitoring/bottleneck_detector.sh:L450; monitoring/unified_monitor.sh:L498/1929/2066/2207; monitoring/monitoring_coordinator.sh:L140; tools/framework_data_quality_checker.sh:L373/603; visualization/advanced_chart_generator.py:L694; visualization/report_generator.py:L1201; utils/ena_field_accessor.py:L78 | net | NIC_MONITOR_ENABLED | ✅ 必须双写 |
| 14 | bw_in_allowance_exceeded (CSV col + ethtool 字段) | monitoring/ena_network_monitor.sh:L92-94/L137 (写 CSV col 7) | utils/ena_field_accessor.py:L12; visualization/device_manager.py:L76/L81; config/system_config.sh:L16; config/config_loader.sh:L829 | net | network_bw_in_dropped (GCP 用 dropped 代理；AWS 保留原名) | ⚠ 仅 AWS 模式写 |
| 15 | bw_out_allowance_exceeded (CSV col + ethtool 字段) | monitoring/ena_network_monitor.sh:L92-94/L138 (写 CSV col 8) | utils/ena_field_accessor.py:L19; visualization/device_manager.py:L77/L82; config/system_config.sh:L17; config/config_loader.sh:L829 | net | network_bw_out_dropped | ⚠ 仅 AWS 模式写 |
| 16 | pps_allowance_exceeded (CSV col + ethtool 字段) | monitoring/ena_network_monitor.sh:L92-94/L130 (写 CSV col 9) | utils/ena_field_accessor.py:L26; visualization/device_manager.py:L78/L83; config/system_config.sh:L18; config/config_loader.sh:L829 | net | network_pps_dropped | ⚠ 仅 AWS 模式写 |
| 17 | conntrack_allowance_exceeded / linklocal_allowance_exceeded / conntrack_allowance_available (CSV cols 10-12) | monitoring/ena_network_monitor.sh:L92-94 (动态写 CSV) | config/config_loader.sh:L829 (源定义); utils/ena_field_accessor.py:L60 (读 ENA_ALLOWANCE_FIELDS_STR 动态解析) | net | (GCP 无等价 — 模式下写空) | ⚠ AWS-only 字段 |
| 18 | ENA_LOG (readonly bash var → CSV 输出路径) | monitoring/ena_network_monitor.sh:L30 | monitoring/ena_network_monitor.sh:L80/L154/L169/L182/L187/L234 (self only) | net | NIC_LOG (本文件局部，0 外部引用) | ❌ 直接改 |
| 19 | network_limited / pps_limited / bandwidth_limited (CSV cols 13-15) | monitoring/ena_network_monitor.sh:L98/L125-127/L140-141/L145 | (无外部消费方 grep 命中：grep -rnE "['\"]network_limited['\"]\|['\"]pps_limited['\"]\|['\"]bandwidth_limited['\"]" → 0 结果) | net | network_limited / pps_limited / bandwidth_limited (已中立) | ✅ 已中立无需改 |
| 20 | bottleneck_status.json `.bottleneck_types[]` (JSON path) | monitoring/bottleneck_detector.sh:L138/L1096/L1116/L1133/L1139 (R-RETRO 2026-05-18 06:50 UTC 确认 = generate_bottleneck_status_json L138 heredoc + 4 场景调用点) | tools/benchmark_archiver.sh:L69 (jq 读，写入 test_summary.json 透传); core/master_qps_executor.sh:L403 (jq 读，分支判定); tools/framework_data_quality_checker.sh:L466-471 (validate schema) | meta | bottleneck_types (字段名已中立；值含 `EBS_AWS_IOPS`/`EBS_AWS_Throughput`/`ACCOUNTS_EBS_AWS_*`/`ENA_Network_Limit` AWS 字面 @ bottleneck_detector.sh:L970/L974/L1016/L1020/L1035) | ⚠ 跨 3 文件共享契约 + 值含 AWS 字面 |
| 21 | bottleneck_status.json `.bottleneck_values[]` | monitoring/bottleneck_detector.sh:L140/L1096/L1116/L1133/L1139 (R-RETRO 确认) | tools/benchmark_archiver.sh:L70 (透传) | meta | bottleneck_values (中立) | ⚠ 跨 2 文件 |
| 22 | bottleneck_status.json `.bottleneck_detected` | monitoring/bottleneck_detector.sh:L138/L1096/L1116/L1133/L1139 (R-RETRO 确认) | tools/benchmark_archiver.sh:L66 (布尔判定); tools/framework_data_quality_checker.sh:L466-471 (schema 校验) | meta | bottleneck_detected (中立) | ⚠ 跨 2 文件 |
| 23 | test_summary.json 全字段 (run_id/benchmark_mode/start_time/end_time/duration_minutes/max_successful_qps/bottleneck_*/test_parameters/data_size/archived_at) | tools/benchmark_archiver.sh:L133-159 (heredoc 写) | (无脚本/py 下游 grep 命中：grep -rnE "test_summary" → 0 个外部读者) | meta | (已全部中立) | ✅ 0 下游可直接改名 |
| 24 | test_history.json 全字段 (total_tests/latest_run/tests[]) | tools/benchmark_archiver.sh:L173-178 init + L184-196 jq | (无外部下游 grep 命中) | meta | (已全部中立) | ✅ 0 下游可直接改名 |
| 25 | substring `'total_iops'` (df 列名模式匹配) | tools/framework_data_quality_checker.sh:L352/356/358 (CSV header 定义); monitoring/iostat_collector.sh (待 R6 确认) | analysis/comprehensive_analysis.py:L373 (substring `in col`); analysis/qps_analyzer.py:L128/134 (endswith); tools/ebs_bottleneck_detector.sh:L134/142/167/177; tools/ebs_analyzer.sh:L45/64; visualization/ebs_chart_generator.py:L113/137/210/226/234/290/354; utils/unit_converter.py:L239/250 | iops | 已中立 ✅ (字段名本身无 aws/ebs 前缀) | ❌ 无需双写 |
| 26 | bottleneck_types element 字面 `'EBS'` (Python str in list) | analysis/qps_analyzer.py:L964 (写方：dict key in `bottleneck_weights = {'CPU':0.2,'Memory':0.25,'EBS':0.3,'Network':0.15,'RPC':0.1}`，本身是评分权重源) + analysis/qps_analyzer.py:L1022 (读方：`if 'EBS' in bottleneck_types`) — **R7 worker qps_analyzer.py 2026-05-18 实证：本文件既写又读 `'EBS'` 字面；但本文件不把 `'EBS'` 写到 bottlenecks dict 给外部下游（identify_bottlenecks @ L562-588 实际 dict keys = {'CPU','Memory','RPC_Latency'}），`bottleneck_types` 真正来源 = `bottlenecks.get('detected_bottlenecks', [])` @ L909 由 comprehensive_analysis.py 调用前注入**；真正含 `'EBS'` 的 list 由 monitoring/bottleneck_detector.sh 写到 bottleneck_status.json（TRACKER 10.1 #20 链） | analysis/comprehensive_analysis.py:L539/L588/L636 (硬编码 `if 'EBS' in bottleneck_types`)；analysis/qps_analyzer.py:L1022 (本文件读)；visualization/report_generator.py:L3815 (chart_title `.replace('Ebs', 'EBS')` 大小写规范化) | disk | 中立别名 `'Disk'` 或 platform-aware tuple `('EBS','PD','Disk')` | ✅ 必须双写（过渡期 qps_analyzer.py L964 加 `'PD': 0.3, 'Disk': 0.3` 三键齐写；L1022 改 `if any(t in bottleneck_types for t in ('EBS','PD','Disk'))`；上游 detector 端同步双写值）|
| 27 | dict key `bottleneck_factors` / `correlations` / `performance_level` / `performance_grade` / `comprehensive_score` / `max_qps` / `bottleneck_qps` (analyzer 返回 dict) | analysis/comprehensive_analysis.py:L257-294/L515-525/L843-849 (return dict + bottleneck_analysis_result.json L923) | analysis/comprehensive_analysis.py main() 本地消费; bottleneck_analysis_result.json 为终端产物（无下游解析方）| meta | 同名（无 AWS 字面）✅ | ❌ 无需改 |
| 28 | (ENA fields 间接消费 via ENAFieldAccessor) | (无写方 — visualization 渲染层消费) | visualization/advanced_chart_generator.py:L691/726/735/838/913/937/1011 (7 处调用 `get_available_ena_fields` / `analyze_ena_field`) | net | 经 NICFieldAccessor 抽象层（字段层归一化）| ✅ 本文件不直接 grep ena_ 字段名 — 改造 ENAFieldAccessor 即自动级联 |
| 29 | 字符串子串硬编码 `'exceeded' in field` / `'conntrack' in field` / `'available' in field` | (无写方 — 渲染层字符串匹配) | visualization/advanced_chart_generator.py:L734/839/936/984 (4 处 `in field`) | net | 改造时需 platform-aware：GCP 可能用 `dropped` 替代 `exceeded` | ⚠ 字符串硬编码 4 处，建议让 ENAFieldAccessor.analyze_ena_field 返回 type 标志（`'exceeded' / 'available' / 'gauge'`）解耦字符串依赖 |
| 31 | `ENA_ALLOWANCE_FIELDS` (env var, default value 不含 `_STR` 后缀) | config/config_loader.sh:L829 (`export ENA_ALLOWANCE_FIELDS=${ENA_ALLOWANCE_FIELDS:-"bw_in_..."}` — 默认值源，逗号分隔字符串语义) | utils/ena_field_accessor.py:L64 (fallback `os.getenv('ENA_ALLOWANCE_FIELDS', '')`); utils/ena_field_accessor.py:L77 (debug print); visualization/advanced_chart_generator.py:L694 (tip 字符串，非读取) | net | `NIC_ALLOWANCE_FIELDS` | ✅ 必须双写（独立于 #12 的 `_STR` 版本，#12 真正源在 system_config.sh:L109）|
| 30 | LAYOUT_CONFIGS dict key `'ebs_2x2'` (Python str literal) | visualization/chart_style_config.py:L389 (定义) | **0 外部读** (grep `get_subplot_layout\(['"]ebs_2x2\|LAYOUT_CONFIGS\[['"]ebs_2x2\|SUBPLOT_LAYOUTS\[` 全仓返回 0 命中) | layout key | `'disk_2x2'` (或直接删) | ❌ 直接删（无下游可破坏）|
| 31 | `CPUEBSCorrelationAnalyzer` (Python class name) | analysis/cpu_ebs_correlation_analyzer.py:L32 (class 定义) | visualization/performance_visualizer.py:L33 (import) + L131 (instantiate, **但实例方法零调用** — grep `correlation_analyzer\.` 全仓 0 命中) | meta/类名 | `CPUDiskCorrelationAnalyzer` (保留别名向后兼容) | ⚠ 类成员 dict key 已中立无需双写；仅类名 + import 别名 |
| 32 | `required_ebs_cols` (Python 局部变量名) | analysis/cpu_ebs_correlation_analyzer.py:L63/L69/L80/L84 (函数内局部) | (0 外部下游 — 局部变量作用域) | meta/变量名 | `required_disk_cols` | ❌ 直接改 (0 下游) |
| 33 | (analysis/cpu_ebs_correlation_analyzer.py 消费字段 = 全部中立 CPU + iostat 列) | (无写方 — 本文件是 reader) | analysis/cpu_ebs_correlation_analyzer.py:L62/L67-L69/L129-L142/L236-L246/L249-L268/L286-L306/L332-L358/L380-L398/L401-L466 (消费 cpu_iowait/usr/sys/idle/soft + data_*_util/aqu_sz/avg_await/r_s/w_s/rrqm_s/wrqm_s/rareq_sz/wareq_sz + accounts_* 同结构) | iostat/cpu | 字段名本身已中立 (cpu_/data_/accounts_ 前缀) | ❌ 无需改名 — 但本文件 9 处 `startswith('data_')` 形成与 iostat_collector 设备前缀的硬耦合 |

| 34 | `data_${LEDGER_DEVICE}_aws_standard_iops` / `accounts_${ACCOUNTS_DEVICE}_aws_standard_iops` (作为 CSV reader 视角) | (本文件不写 CSV — 上游 monitoring/iostat_collector.sh:L127/L144 写)| tools/ebs_bottleneck_detector.sh:L135 / L168 / L178 (CSV_FIELD_MAP lookup → 索引化读取) → L143 → L264/L301 (IFS read 解构) → L270/L307 (传 detect_ebs_bottleneck arg3) | disk | `disk_standard_iops` | ✅ 必须双写（与 #5 是同字段 reader 视角，本文件是第 5 个 reader；R6 worker 2026-05-18 实证 5 层契约链：iostat_collector → 本文件 + master_qps_executor.sh + bottleneck_detector.sh + ebs_chart_generator.py + report_generator.py + device_manager.py）|
| 35 | `data_${LEDGER_DEVICE}_aws_standard_throughput_mibs` (本文件 reader 视角) | (本文件不写)| tools/ebs_bottleneck_detector.sh:L136 / L169 / L179 → L144 → L264/L301 → L270/L307 (传 detect_ebs_bottleneck arg4) → L273/L310 (log_info echo) | disk | `disk_standard_throughput_mibs` | ✅ 必须双写（同 #34，同字段 reader）|
| 36 | `current_aws_iops` (detect_ebs_bottleneck 局部变量名，非 CSV 字段)| tools/ebs_bottleneck_detector.sh:L373 (函数 arg3) / L391 / L445 / L450 + L537/L539 (generate_monitoring_summary 局部 IFS read) | (0 外部 — 局部作用域)| meta/局部 | `current_disk_iops` | ❌ 直接改 (0 下游) — 但生成日志行 L445 含变量值（非字段名），无契约破坏 |
| 37 | `BOTTLENECK_EBS_IOPS_THRESHOLD` / `BOTTLENECK_EBS_THROUGHPUT_THRESHOLD` / `BOTTLENECK_EBS_LATENCY_THRESHOLD` (env 变量名) | (上游 config_loader.sh / internal_config.sh / 可能 user_config.sh — [GAP] 未在本 worker 范围)| tools/ebs_bottleneck_detector.sh:L21 / L22 / L25 / L26 / L397 / L398 / L416 / L417 / L429 (9 处) | disk/env | `BOTTLENECK_DISK_*_THRESHOLD` | ✅ env alias 一行兼容：`: ${BOTTLENECK_DISK_IOPS_THRESHOLD:=$BOTTLENECK_EBS_IOPS_THRESHOLD}` |
| 38 | `BOTTLENECK_LOG_FILE` (env 变量名，本文件**未定义**仅消费)| (上游 grep 全仓 `BOTTLENECK_LOG_FILE=` 0 命中 → [GAP-UNDEF])| tools/ebs_bottleneck_detector.sh:L511 / L529 / L611 / L616（仅在死代码 generate_monitoring_summary + stop_ebs_monitoring 内）| meta/env | `BOTTLENECK_DISK_LOG_FILE` 或直接删（随死代码删）| ❌ 与三函数死代码同删 (P3) |
| 39 | `DATA_VOL_TYPE` / `ACCOUNTS_VOL_TYPE` (env 字符串枚举, 当前值 `io2`) | config/user_config.sh:L19 + L25 + export L117 (retro 2026-05-18) | monitoring/iostat_collector.sh:L152/L178 (强校验 `[[ -n "$DATA_VOL_TYPE" ]]` 失败 log_error 退出) + utils/ebs_converter.sh:L51/L97 (case 分发) + monitoring/unified_monitor.sh (待 R4) = 3 文件 | disk/enum | 变量名已中立保留；**值域**扩展含 `pd-ssd/pd-balanced/pd-extreme/hyperdisk-extreme/local-ssd` | ⚠ 变量名 ❌；**值域 ✅** 必须扩 enum + 下游 case 加 GCP 分支 |
| 40 | `DATA_VOL_MAX_IOPS` / `ACCOUNTS_VOL_MAX_IOPS` / `DATA_VOL_MAX_THROUGHPUT` / `ACCOUNTS_VOL_MAX_THROUGHPUT` (env 整数, IOPS + MiB/s 阈值) | config/user_config.sh:L21/L22/L27/L28 + export L117 (retro) | 8/7/7/7 处下游（master_qps_executor + bottleneck_detector + ebs_bottleneck_detector + framework_data_quality_checker + iostat_collector + unified_monitor 等）= 跨 4-5 文件 | iops | 字段名已中立 ✅；唯一 issue = 字段值默认 `40000`/`1000` 是 AWS io2 上限，GCP 用户应填 pd-extreme/hyperdisk 实际值 | ❌ 字段名无需改；注释加 GCP 数值参考 |
| 41 | `ENA_MONITOR_ENABLED` (本 retro 确认 user_config.sh 是源头之一) | config/user_config.sh:L35 + export L117 (retro 2026-05-18 — 与 TRACKER #13 同字段，**双写方**: user_config 是默认值源 + config_loader 是 platform 覆写源) | 同 TRACKER #13（9 文件 / 14 处）| net | `NIC_MONITOR_ENABLED` | ✅ 双写（user_config.sh L35 同时定义 NIC_MONITOR_ENABLED + ENA_MONITOR_ENABLED alias；config_loader.sh:L108 检测后按 platform 覆写）|
| 42 | `EBS_MONITOR_RATE` (env 整数, 监控频率 Hz) | config/user_config.sh:L40 + export L117 (retro) | 2 处下游（monitoring/unified_monitor.sh + monitoring/iostat_collector.sh 待精确 grep）| disk | `DISK_MONITOR_RATE` | ✅ 双写 alias（下游低 2 处可一次性切）|
| 43 | `LEDGER_DEVICE` / `ACCOUNTS_DEVICE` (env 字符串, OS 块设备名) | config/user_config.sh:L12 + L13-14 + export L117 (retro; **默认值** `nvme1n1`/`nvme2n1` 来自 AWS Nitro 命名约定) | 8/11 文件下游（含 CSV header 动态拼接 `data_${LEDGER_DEVICE}_*` 已计入 TRACKER #34/#35）| disk | 变量名已中立 ✅；**默认值**应注释为 GCP 用户须 `lsblk` 验证（Hyperdisk 通常 `nvme0n*` 起算）| ⚠ 字段名 ❌；默认值 ⚠ 仅文档化 |
| 44 | JSON key `ebs_util` (写方视角；与 #5/#10/#34 形成第 6+ 层契约链) | monitoring/unified_monitor.sh:L1944-1985 (写 `${MEMORY_SHARE_DIR}/latest_metrics.json`) + monitoring/unified_monitor.sh:L1986-1998 (写 `${MEMORY_SHARE_DIR}/unified_metrics.json`) | core/master_qps_executor.sh:L670 (jq `.ebs_util // 0`) + L702 (写入 master decision JSON) + analysis/qps_analyzer.py:L82-167 (动态字段发现，4-layer fallback) | disk | `disk_util` | ✅ 必须双写（同 JSON 既写 `ebs_util` 又写 `disk_util`；读端 jq `.disk_util // .ebs_util`；R4 worker unified_monitor.sh 2026-05-18 实证 ≥3 文件 / 7+ 处下游）|
| 45 | JSON key `ebs_latency` | monitoring/unified_monitor.sh:L1944-1985 (同上) | core/master_qps_executor.sh:L355 (jq `.ebs_latency // 0`) + L356 (阈值比较 `> $BOTTLENECK_EBS_LATENCY_THRESHOLD`) + L359 (`bottleneck_reasons+=("EBS latency: ...")`) + L671/L703 (master decision JSON) + analysis/qps_analyzer.py:L97-121 (动态字段发现) | disk | `disk_latency` | ✅ 必须双写（同 #44 策略；额外注意阈值变量 `BOTTLENECK_EBS_LATENCY_THRESHOLD` 也需双读 — TRACKER #37 子项）|
| 46 | JSON sub-object `ena_data` | monitoring/unified_monitor.sh:L1986-1998 (写 `unified_metrics.json` 内 `"ena_data": {...}` 子对象) | tools/framework_data_quality_checker.sh:L520-521 (schema 校验 `validate_json_file ... "timestamp cpu_usage memory_usage detailed_data"` — 校验顶层不直读 ena_data，但下游 visualization 可能读) | net | `network_allowance_data` | ✅ 双写过渡（同 JSON 既写 ena_data 又写 network_allowance_data 子对象；读端归一化）|
| 47 | CSV 列 `ena_*_allowance_exceeded` (6 列：bw_in/bw_out/pps/conntrack/linklocal/exceeded + conntrack_available) | monitoring/unified_monitor.sh:L1904-1931 (build_ena_header 动态构造，按 `$ENA_ALLOWANCE_FIELDS_STR` 拼接) + L2064-2089 (log_performance_data ENA 条件分支写值) | tools/framework_data_quality_checker.sh:L376-377 (通过 `$ENA_ALLOWANCE_FIELDS_STR` 间接消费列名) + analysis/qps_analyzer.py 动态字段发现 + monitoring/ena_network_monitor.sh:L63/L92/L118/L217 (兄弟生产者读 ENA_ALLOWANCE_FIELDS_STR 知列名) | net | `nic_*_allowance_*` (或保持 `ena_*` AWS-only 别名) | ✅ 双写（列名通过 env 注入，改 env 即改列；读端走 utils/ena_field_accessor.py 抽象层）|
| 48 | log 日志文本 "AWS environment" / "Non-AWS environment" | monitoring/unified_monitor.sh:L2206-2210 (echo `"ENA monitoring: Enabled - AWS environment"` / `"Disabled - Non-AWS environment"`) | （仅人读 log 文本，0 程序化下游 — grep `"Non-AWS environment"` 全仓 = 1 命中即本文件）| meta/text | `"Cloud: $CLOUD_PROVIDER (ENA monitoring: Enabled/Disabled)"` | ❌ 直接替换（0 下游可破坏）|
| 49a | `data_aws_standard_iops` / `data_aws_standard_throughput_mibs` / `accounts_aws_standard_iops` / `accounts_aws_standard_throughput_mibs` (df 列, **第二写方**视角) | visualization/ebs_chart_generator.py:L126/L133/L148/L154 (`self.df[...] = ...` **重新计算覆盖**上游 iostat_collector 的旧值) | 同 TRACKER #5/#7（本文件 = 第 N 个 reader：26 处 `get_mapped_field` 调用 @ L116/L118/L140/L142/L171/L172/L718/L727/L740/L749/L796/L847/L859/L880/L890/L982/L992/L1013/L1023/L1044/L1045/L1054/L1055/L1071/L1086/L1102/L1143/L1167/L1255 + **2 处直字面 df 访问** @ L1238/L1243）| disk/iops | `data_disk_standard_*` | ✅ **隐式双写方契约**：本文件不仅消费 aws_standard_*，还重算并回写 df，改名时必须同步双写两个写方（iostat_collector + 本文件 L126/L133/L148/L154）；直字面 L1238/L1243 必须修复为 `get_mapped_field` 调用否则 KeyError（R8 worker ebs_chart_generator.py 2026-05-18 实证）|
| 49b | algorithm constant `16` (KiB IO baseline, hardcoded) | visualization/ebs_chart_generator.py:L125 (注释 "no scaling when avg_io > 16 KiB") + L127 (`avg_io_kib > 16` 条件) + L128 (`avg_io_kib / 16` scaling) + L149 同 accounts | (本文件 algorithm 内嵌；与 system_config.sh:L53 `AWS_EBS_BASELINE_IO_SIZE_KIB` 是同一概念但**未引用该常量** — 硬编码 magic number) | iops/algorithm | 引入 `utils/cloud_constants.py.IO_BASELINE_KIB`（aws=16, gcp=4 for pd-balanced/pd-ssd, gcp=8 for hyperdisk）| ✅ **必须 platform-aware**：本文件是该 algorithm 唯一硬编码点；GCP PD baseline 与 AWS 不同，直接改算法分支或引入常量 |
| 49c | `EBSChartGenerator` (Python class name) | visualization/ebs_chart_generator.py:L26 (class 定义) | visualization/performance_visualizer.py:L27 (import) + L2267/L2276/L2536 (3 处实例化) | meta/类名 | `DiskChartGenerator` (保留别名 `EBSChartGenerator = DiskChartGenerator` 1 行兼容) | ⚠ 单 reader 4 处，alias 兼容即可（R8 worker 2026-05-18）|
| 49d | `generate_all_ebs_charts` / `generate_ebs_performance_overview` / `generate_ebs_bottleneck_analysis` / `generate_ebs_aws_standard_comparison` / `generate_ebs_time_series` / `validate_ebs_integration` (6 个 public 方法名) | visualization/ebs_chart_generator.py:L180/L700/L829/L969/L1125/L1291 | (本文件内 L196-200 dispatcher 内部调用 5 个 + performance_visualizer 待 R8 file-notes 实证调用入口；`validate_ebs_integration` grep 全仓 0 外部调用 — **可能死方法**) | meta/方法名 | `generate_all_disk_charts` / `generate_disk_*` / `validate_disk_integration` | ⚠ 入口 `generate_all_ebs_charts` 需 alias（performance_visualizer 调用）；`validate_ebs_integration` 0 调用可直接改 |
| 49e | `_is_accounts_configured` (Python 死方法 @ L823-827) | visualization/ebs_chart_generator.py:L823 | **0 外部调用 + 0 本文件内调用**（grep `_is_accounts_configured\(` 全仓 1 命中 = 定义本身；本文件实际用 `self.device_manager.is_accounts_configured()`）| meta/死代码 | 直接删 5 行 | ❌ 死代码，与 GCP 改造无关 |
| 50 | `BLOCK_HEIGHT_DIFF_THRESHOLD` (env 变量，区块高度差阈值) | **[GAP]** 未在 config_loader.sh / internal_config.sh / system_config.sh / user_config.sh 中定义（grep 全仓写方 0 命中；仅 visualization/performance_visualizer.py:L2350 默认 `'50'`）| visualization/performance_visualizer.py:L2350（唯一 reader）；core/common_functions.sh 也 read 此 env（见 #355 文件总结行注释，但本字段类型表中未单列） | meta | **新发现 env**，命名已中立（无 AWS 字面），无需 alias；建议 config 层 internal_config.sh 补充默认值定义（避免漂移） | ❌ 字段名中立，无需双写；P3 优先级（仅补 config 默认值） | R8 worker performance_visualizer.py 2026-05-18 |
| 51 | `format_time_axis` (Python module-level function, visualization/performance_visualizer.py:L56-79) | visualization/performance_visualizer.py:L56 (def export) | visualization/report_generator.py:L29 (import) + L2678 (调用) — **唯一外部消费者**;本文件类内 10+ 处用 `UnifiedChartStyle.format_time_axis`(chart_style_config.py:L637 另一实现) | meta/函数名契约 | 与 chart_style_config.py 双实现合并 — 推荐废弃本文件 module-level 版本,全切到 `UnifiedChartStyle.format_time_axis`;过渡期保留 alias `format_time_axis_legacy = format_time_axis` | ✅ alias 1 行兼容 | R8 worker performance_visualizer.py 2026-05-18 — 类比 #49d EBSChartGenerator method 契约模式 |
| 52 | `bottleneck_info['ebs_bottlenecks']` (JSON top-level key, list of dicts) | `monitoring/bottleneck_detector.sh` (待 R4 精确写方,经 `bottleneck_status.json` 生产) | visualization/report_generator.py:L2724/L2725/L2729 (本文件唯一已知 reader: `if bottleneck_info and 'ebs_bottlenecks' in bottleneck_info: ebs_bottlenecks = bottleneck_info['ebs_bottlenecks']; for bottleneck in ebs_bottlenecks: ...`) | JSON list | `disk_bottlenecks` (保留 `ebs_bottlenecks` 别名) | ✅ 必须双写(reader 端 `.get('disk_bottlenecks') or .get('ebs_bottlenecks', [])` fallback;writer 端同写双 key) | R8 worker report_generator.py 2026-05-18 新发现 — 区别于 #20 `.bottleneck_types[]`,本字段是嵌套 list 含 device_type/type/severity/details/value 子结构 |
| 53 | `bottleneck.get('device_type'/'type'/'severity'/'details'/'value')` (嵌套 dict keys, item-level) | 同 #52 上游 | visualization/report_generator.py:L2730/L2745/L2746/L2747 (本文件 reader 嵌套消费 4 keys) | dict keys | 已全部中立 ✅ | ❌ 无需改 — 嵌套 dict keys 是设备/瓶颈语义,与云无关 | R8 worker report_generator.py 2026-05-18 |
| 54 | log file `ebs_bottleneck_detector.log` (跨工具日志文件路径硬编码 reader) | `tools/ebs_bottleneck_detector.sh` (写,见 §10.3 #14) | visualization/report_generator.py:L1188 (`self.ebs_log_path = os.path.join(os.getenv('LOGS_DIR', ...), 'ebs_bottleneck_detector.log')`) + L1500-L1572 (`parse_ebs_analyzer_log` 文本解析) — 唯一已知 reader | str (file path) | `disk_bottleneck_detector.log` (双路径 fallback) | ✅ 与 §10.3 #14 同步改名(本文件 reader 视角追加) | R8 worker report_generator.py 2026-05-18 — 文件名改名链第 2 reader(framework_data_quality_checker:L438 是第 1) |
| 55 | log text pattern `'EBS BOTTLENECK DETECTED'` (隐式 7 段文本契约) | `tools/ebs_bottleneck_detector.sh` (echo 写) | visualization/report_generator.py:L1518 (`if '⚠️' in line and 'EBS BOTTLENECK DETECTED' in line`) + L1521-L1527 (parse 设备名 + 类型 + Severity + IOPS:/Throughput: 子串) | str pattern | `DISK BOTTLENECK DETECTED` (双 pattern OR) | ✅ 必须双 pattern OR (`'EBS BOTTLENECK DETECTED' in line or 'DISK BOTTLENECK DETECTED' in line`);长期建议 log 改 JSON 结构化 | R8 worker report_generator.py 2026-05-18 — 强耦合上游 echo 文本,改名需双方同步 |
| 56 | `data_${LEDGER_DEVICE}_aws_standard_iops` / `accounts_${ACCOUNTS_DEVICE}_aws_standard_iops` / `*_aws_standard_throughput_mibs` (CSV 列后缀,本文件 = 第 10 reader 视角) | (本文件不写 CSV) | visualization/report_generator.py:L1761 (`endswith('_aws_standard_iops')`) + L1762 (`endswith('_aws_standard_throughput_mibs')`) + L1779/L1780 (ACCOUNTS 同模式) — 4 处 `endswith` pattern matching | disk/iops | `*_disk_standard_iops` / `*_disk_standard_throughput_mibs` | ✅ 必须双写(与 #5/#7/#34/#35/#49a 是同字段契约链,本文件追加 reader 视角) | R8 worker report_generator.py 2026-05-18 — 字段链已扩至 10 reader 文件,5+ 层契约不变 |

| 56 | `*_aws_standard_iops` / `*_aws_standard_throughput_mibs` (CSV 列, R8 report_generator 第 10 reader 视角) | 已计入 #5/#7(iostat_collector + ebs_chart_generator 双写方) | +1 reader 文件(report_generator.py:L1761-L1780, 4 处 endswith) → 总 10 文件 / 5+ 层契约链不变 | iops | `*_disk_standard_iops` / `*_disk_standard_throughput_mibs` | ✅ 必须双写（与 #5/#7/#34/#35/#49a 同源同优先级） | R8 worker report_generator.py 2026-05-18 |
| 57 | `bottleneck_status.json.performance_metrics.{ebs_util,ebs_latency,ebs_aws_iops,ebs_throughput}` (4 字段嵌套对象含 ebs/aws 字面 + 4 字段中立) | monitoring/bottleneck_detector.sh:L94-97 (create_performance_metrics_json heredoc) + L116-119 (jq 解析回写) + L147-150 (generate_bottleneck_status_json 嵌入) | 同 TRACKER #44/#45 reader 链：master_qps_executor.sh L355/L670/L703 + qps_analyzer.py L82-167 ≥3 文件 / 8+ 处；本字段是同 JSON 内嵌子对象，与顶层 #20/#21/#22 不同 path | disk | `disk_util` / `disk_latency` / `disk_standard_iops` / `disk_throughput` | ✅ 必须双写（同 JSON 同时写新旧两 key；reader jq `.disk_util // .ebs_util` fallback；与 #44/#45 同源同优先级） |
| 58 | `bottleneck_status.json.counters.{ebs_util,ebs_latency,ebs_aws_iops,ebs_aws_throughput,ena_limit,...}` (10 字段嵌套 dict，5 字段含 ebs/ena/aws 字面) | monitoring/bottleneck_detector.sh:L161-170 (generate_bottleneck_status_json 内嵌 counters 子对象) | **0 外部 reader** (grep `counters\.ebs_util\|counters\.ena_limit` 全仓 = 0；仅本文件自写不读) | disk/net/meta | `disk_util` / `disk_latency` / `disk_iops` / `disk_throughput` / `nic_limit` | ❌ 无需双写（0 下游可破坏；可直接改名） |
| 59 | `bottleneck_counters.json` 全字段 (10-16 key 动态 = `{cpu:N,memory:N,ebs_util:N,ebs_latency:N,ebs_aws_iops:N,ebs_aws_throughput:N,network:N,ena_limit:N,error_rate:N,rpc_*:N,accounts_ebs_*:N}`) | monitoring/bottleneck_detector.sh:L180-202 (save_bottleneck_counters 动态序列化) | monitoring/bottleneck_detector.sh:L205-218 (load_bottleneck_counters jq 反序列化) = **本文件自闭环 IPC，0 外部 reader** (grep `bottleneck_counters.json` 全仓 = 仅本文件) | disk/net/meta | 同 #58 | ✅ 双写过渡期（load 时同时尝试 disk_* 和 ebs_* 两 key 累加；避免新版加载旧 .json 丢 counter）|
| 60 | `bottleneck_status.json.ebs_baselines.{data_baseline_iops,data_baseline_throughput,accounts_baseline_iops,accounts_baseline_throughput}` (4 字段嵌套对象，dict key 含 ebs 字面) | monitoring/bottleneck_detector.sh:L154-159 | **0 外部 reader** (grep `ebs_baselines` 全仓 = 仅本文件 L154 定义) | disk | `disk_baselines.*` | ❌ 无需双写（0 下游；可直接改名或保留） |
| 61 | `ena_baseline.json` 全字段 (动态 = `$ENA_ALLOWANCE_FIELDS_STR` 列举字段) | monitoring/bottleneck_detector.sh:L502-518 (首次基线写入 JSON heredoc) | monitoring/bottleneck_detector.sh:L526-528 (jq 读历史基线) = **本文件自闭环 IPC，0 外部 reader** (grep `ena_baseline.json` 全仓 = 仅本文件) | net | `nic_baseline.json` 全字段 | ✅ 直接改 + 加 `[[ -f new \|\| -f old ]]` 路径 fallback |
| 62 | `BOTTLENECK_NETWORK_THRESHOLD` (env int %, retro 2026-05-18 ena_field_accessor) | (本文件不写 — 上游未在 ena_field_accessor scope 验证；grep `BOTTLENECK_NETWORK_THRESHOLD=` 全仓写方 [GAP] 待 R4 config 链确认) | utils/ena_field_accessor.py:L162 (`get_unified_network_thresholds` DEAD method `int(os.getenv('BOTTLENECK_NETWORK_THRESHOLD', '80'))`) — **本文件唯一 reader 在 DEAD method 内，0 外部消费**；建议 DEAD method 删除时此条目同步降级为 N/A | net/env | 已中立无 AWS 字面 ✅ | ❌ 无需双写（reader 在 DEAD method；字段名本身中立）| retro 2026-05-18 ena_field_accessor.py |
| 63 | `ENAFieldAccessor.analyze_ena_field()` 返回 dict 6 key (`field_name/display_name/type/unit/description/aws_description`) (retro 2026-05-18 ena_field_accessor) | utils/ena_field_accessor.py:L97-L122 (`analyze_ena_field` 运行时 dict 构造，每次调用 emit 6 key) + L85-L94 (`get_available_ena_fields` emit list of dict 含 `field/config` 2 key 复合形态) | **下游 13 处消费**：visualization/advanced_chart_generator.py L735 (`field_analysis['display_name']`) / L738 (display_name) / L838-839 (`'exceeded' in field` 字串判定) / L913 (analyze 调用) / L936-937 (`'available' in field`) / L984 (`'conntrack' in field`) / L1011-1013 (`type` 字段) / L1016 (display_name fallback) / L1018 (display_name) / L1028 (display_name) + visualization/report_generator.py L3187 (`field_analysis.get('aws_description', ...)` — **唯一 `aws_description` 消费方，仅 `self.language == 'en'` 分支**) / L3201 (`type == 'gauge'`) / L3212-L3214 (`type` 分支) | dict keys (runtime) | `display_name/type/unit/description` 已中立 ✅；`aws_description` → `cloud_description`（保留 alias 1 行兼容 report_generator:L3187）；`field_name` 值仍含 ena 字面但走 #14-17 字段名链 | ⚠ 字段名层：4 个 key 已中立无需改；`aws_description` ✅ 必须双写（reader 0 fallback，直读 KeyError 风险低因 `.get()` 调用）；`type` 值域 `{'counter','gauge'}` 已中立 ✅ | retro 2026-05-18 ena_field_accessor.py — 与 #28（间接消费经 ENAFieldAccessor）配对；本条具体到 dict key 粒度 |

**字段类型分类**：
- net（网络相关：ena_*, aws_*_gbps）
- disk（磁盘相关：ebs_*, aws_ebs_*, aws_standard_iops）
- iops（IO 性能：ebs_io2_*, aws_standard_*）
- meta（元数据：instance_id, region）
- 其他

#### 10.1 附注 — 零产出 / 零消费文件留痕（R6 worker 实证）

| 文件 | grep AWS 字面 | 产出 AWS 命名字段 | 消费 AWS 命名字段 | TRACKER 新行 | 备注 |
|------|----------------|--------------------|--------------------|--------------|------|
| `tools/fetch_active_accounts.py` | 0 | 0 | 0 | 不追加 | R6 2026-05-18：唯一输出 `active_accounts.txt` 已中立；唯一上游契约 = `CHAIN_CONFIG` env（chain_type/rpc_url/methods/system_addresses/params，全部 chain-agnostic 非 cloud-aware）；GCP 迁移 0 工作量 |
| `tools/framework_data_quality_checker.sh` | 15 行 / 25 token | 0（**schema validator，0 写文件**；唯一"产出"是期望串与下游 reader 视角等价）| `aws_standard_iops` × 4 (L352/L356/L358) + `ENA_MONITOR_ENABLED` × 2 (L373/L603) + `ENA_ALLOWANCE_FIELDS_STR` × 2 (L376/L377) + 日志白名单字面 `ebs_*.log` × 2 (L438) + `DEPLOYMENT_PLATFORM` × 1 (L602) | 不追加（已含 #34b/#35a/#43/#1/#7）；**仅 10.2 追加日志白名单风险行** | R6 2026-05-18：**独立 CLI 工具**（业务源码 0 调用，仅 5 处 .hermes/plans 文档提议；CI/Makefile 未集成）；本文件是"对称契约"的反向锚——上游 CSV/JSON schema 任一改名 = 本文件期望串硬编码 mismatch；改造 10 个 P0/P1/P2/P3 点，~15 行 patch 即可；L520-521 JSON 校验仅顶层（对 `ena_data` 子对象重命名宽容）|
| `core/common_functions.sh` | **0**（grep -cE `"AWS\|aws\|EBS\|ebs\|ENA\|ena_\|aws_ebs\|ebs_aws\|nitro\|nitroSystem"` = 0）| 0（jq -n L142-160 产 8 字段：`timestamp_ms/timestamp/local_block_height/mainnet_block_height/block_height_diff/local_health/mainnet_health/data_loss`，全部业务中性命名）| 0（读 env：`BLOCKCHAIN_NODE/MEMORY_SHARE_DIR/BLOCK_HEIGHT_DIFF_THRESHOLD` 全中立；位置参数由 caller block_height_monitor.sh 注入，无 AWS 命名）| 不追加 | retro 2026-05-18：本文件**唯一调用者** = `monitoring/block_height_monitor.sh` 7 处 subshell 调用（L141/L147/L154/L162/L174/L280/L289），其余 4 处 source 为 `[SOURCE-ONLY]`（master_qps_executor / blockchain_node_benchmark / bottleneck_detector / unified_monitor 0 函数调用）；产出 8 字段下游消费 14 hop 全部中立命名（block_height_monitor × 12 + framework_data_quality_checker × 2 派生 `data_loss_count/data_loss_periods`）；GCP 迁移**零行修改**（5 个核心文件中唯一"零接触"模块）|
| `tools/target_generator.sh` | **0**（grep -cE `"AWS\|aws\|EBS\|ebs\|ENA\|ena_\|aws_ebs\|ebs_aws\|nitro\|nitroSystem"` = 0；实跑命中 0 行）| 0（仅写 Vegeta protocol 字段 method/url/header/body @ L119-122，全是 protocol schema，无云字面；产物 `targets_{single,mixed}.json` 文件名已中立）| 0（读 env：`CHAIN_CONFIG/BLOCKCHAIN_NODE/RPC_MODE/LOCAL_RPC_URL/ACCOUNTS_OUTPUT_FILE/SINGLE_METHOD_TARGETS_FILE/MIXED_METHOD_TARGETS_FILE/CURRENT_RPC_METHODS_STRING/CHAIN_CONFIG.rpc_methods.<mode>` 全中立；按行读 ACCOUNTS_OUTPUT_FILE 纯字符串地址，无字段名）| 不追加 | R6 worker 2026-05-18：本文件**唯一调用方** = `blockchain_node_benchmark.sh:L143` spawn 子进程（非 source；L381-383 守卫确认）；唯一 source 依赖 = `config/config_loader.sh`（用 `get_current_rpc_methods` @ L760 + `get_param_format_from_json` @ L775，与云无关）；产物 `${TMP_DIR}/targets_{single,mixed}.json`（config_loader.sh:L243-244 定义）下游唯一消费者 = `core/master_qps_executor.sh` L107/113/251/253/825/827（仅按路径读，不解析字段名）；**GCP 迁移零行修改**——纯 RPC 业务"安全岛" |
| `monitoring/block_height_monitor.sh` | **0**（grep -cE `"AWS\|aws\|EBS\|ebs\|ENA\|ena_\|aws_ebs\|ebs_aws\|nitro"` = 0 实跑）| 0（emit 6 类载体：CSV header 7 字段 @ L389 `timestamp,local_block_height,mainnet_block_height,block_height_diff,local_health,mainnet_health,data_loss` + data_loss_stats.json 4 字段 @ L443-451 + block_height_time_exceeded.flag @ L198 + block_height_monitor.pid @ L408 + BLOCK_HEIGHT_DIFF_EVENT_ID spawn stdout @ L184 + CSV 数据行 @ L173-174，**全部 100% 业务中性命名**，0 含 aws_*/ena_*/ebs_aws_* 命名）| 0（消费 16 类 env/JSON：`BLOCKCHAIN_NODE/LOCAL_RPC_URL/MAINNET_RPC_URL/BLOCK_HEIGHT_*_THRESHOLD/BLOCK_HEIGHT_MONITOR_RATE/BLOCK_HEIGHT_DATA_FILE/BLOCK_HEIGHT_CACHE_FILE/MEMORY_SHARE_DIR/BASE_MEMORY_DIR/TMP_DIR/LOGS_DIR/USE_MEMORY_CACHE/CACHE_MAX_AGE/qps_test_status filesystem marker/common.get_cached_block_height_data 返回的 JSON 8 字段` 全中立；间接经 `core/common_functions.sh::get_block_height` 按 BLOCKCHAIN_NODE case 分发 RPC 与云无关）| 不追加 | retro 2026-05-18 06:31 UTC：本文件由 `monitoring/monitoring_coordinator.sh:L34` 关联数组 `["block_height"]="block_height_monitor.sh"` 登记 spawn + L408 pkill + L418 清 cache；产出 3 类下游消费 = (a) `block_height_time_exceeded.flag` → `bottleneck_detector.sh:L1075` 唯一消费者（关键 IPC，5 场景判定 B/C 输入） + `blockchain_node_benchmark.sh:L174` 启动前清理；(b) `data_loss_stats.json` 4 字段 → `framework_data_quality_checker.sh:L166-218/L455-463/L541` jq 校验 + `benchmark_archiver.sh:L34-39/L267` 归档 + `report_generator.py:L401/L3472/L3598-3606` HTML 展示；(c) CSV `block_height_diff` 列 → `rpc_deep_analyzer.py:L247-251` pandas sync 分析 + `framework_data_quality_checker.sh:L418/L527-528` schema 校验 + `unified_monitor.sh:L2053` tail -1。**GCP 迁移零行修改**——与 common_functions.sh 同属"零接触模块" |
| `utils/__init__.py` | **0**(grep -cE `"AWS\|aws\|EBS\|ebs\|ENA\|ena_\|aws_ebs\|ebs_aws\|nitro"` = 0 实跑；文件 30 bytes / 1 行注释 `# Utils package initialization`)| 0(0 函数 / 0 类 / 0 __all__ / 0 __version__ / 0 任何 module-level 元数据 / 0 任何写入语义；纯 PEP 328 package marker)| 0(grep `^import\|^from` = 0 命中；0 env 读取 / 0 文件读取 / 0 字段消费)| 不追加 | retrofill 2026-05-18 06:46 UTC：**纯 Python package marker 文件**，使 `utils/` 被解释器识别为 package(隐式 LIVE)；grep `from utils import\|^import utils$` 全仓 = 0(无任何代码直接 import 本模块)，所有 utils 使用都走 `from utils.X import Y` 子模块路径(9 个 .py 调用方：utils/unit_converter + utils/csv_data_processor + analysis/{cpu_ebs_correlation_analyzer,qps_analyzer,comprehensive_analysis,rpc_deep_analyzer} + visualization/{performance_visualizer,advanced_chart_generator,report_generator})；**GCP 迁移零行修改**——与 common_functions.sh / target_generator.sh / block_height_monitor.sh 同属"零接触模块"；唯一可选优化 = 补 POSIX 尾换行(B-1 极低，与 GCP 无关)|
| `utils/csv_data_processor.py` | **0**(grep -cE `"AWS\|aws\|EBS\|ebs\|ENA\|ena_\|aws_ebs\|ebs_aws\|nitro"` = 0 实跑 2026-05-18 06:53 UTC；L161 `'gbps'` 是带宽单位非 AWS EBS 类型) | 0(grep -nE `to_csv\|to_json\|json\.dump\|csv\.writer` = 0 命中；只读 CSV / 不写 CSV / 不落盘；`get_summary_info` DEAD 返回 dict 但 0 下游消费方) | 0(字段无关处理层：L161 numeric_keywords 子串模糊匹配 + L106 调用方传 prefix/suffix；任何上游字段改名本文件 0 行需改，仅"最坏失去类型转换、不会 KeyError") | 不追加 | retrofill 2026-05-18 06:54 UTC：**`CSVDataProcessor` 通用 pandas 工具类**(1 init + 7 method + 1 module factory)，被 visualization 层 2 子类继承 `PerformanceVisualizer(CSVDataProcessor)` @ performance_visualizer.py:101 + `AdvancedChartGenerator(CSVDataProcessor)` @ advanced_chart_generator.py:38；下游 grep 实证 5 处 self.* 调用(performance_visualizer:167/169 + advanced:120/125/127)；3 method LIVE(load_csv_data / get_device_columns_safe / clean_data) + 4 method DEAD + 1 工厂 DEAD + 1 elif 死分支 ~94 行清理空间；**GCP 迁移零行修改**——与 common_functions.sh / block_height_monitor.sh / target_generator.sh / utils/__init__.py 同属"零接触模块"安全岛；唯一耦合是方法签名改动需同步 2 子类(🟠 中风险) |
| `utils/error_handler.sh` | **0**(grep -cE `"AWS\|aws\|EBS\|ebs\|ENA\|ena_\|aws_ebs\|ebs_aws\|nitro\|nitroSystem"` = 0 实跑 2026-05-18 07:07 UTC；纯通用错误处理 + 日志生命周期工具，零云原生术语)| 0(grep `to_csv\|jq -n\|printf "%s,"\|json.dump` = 0 命中；唯一"写入"= L51 `log_info "$error_msg"` 纯文本 + L54/L55 echo stderr；error_msg 格式 L48 = `[$timestamp] ❌ $script_name:$line_number - $error_context (Exit code: $exit_code)` 5 变量全 OS/shell 通用元数据)| 0(grep `pd.read_csv\|jq -r\|awk -F,\|json.load` = 0 命中；消费的 env = `LOGS_DIR`/`FALLBACK_ERROR_LOG_DIR`/`DATA_DIR`/`TEMP_FILE_PATTERN` 全部 OS 路径 env 非字段契约；ERROR_LOG_DIR 是 export 链终点 grep `ERROR_LOG_FILE\|ERROR_LOG_DIR` 0 处外部读方)| 不追加 | retrofill 2026-05-18 07:07 UTC：**纯通用错误处理 + 脚本生命周期工具**(9 个公开函数：handle_framework_error / setup_error_handling / log_script_start/success / check_dependencies / safe_execute / cleanup_temp_files / check_disk_space / validate_config + cleanup_on_error 钩子)；3 个 source 入口(master_qps_executor.sh:L20 + monitoring_coordinator.sh:L10 + blockchain_node_benchmark.sh:L66)；4 函数 LIVE(setup_error_handling × 3 + log_script_start × 3 + log_script_success × 1 + handle_framework_error via trap) + 5 公开函数 + 1 钩子 DEAD/同名覆盖 ~80 行；输出文件 `framework_errors_$(date +%Y%m%d).log` 文件名 100% 中立(grep 全仓 0 程序化 reader)；**GCP 迁移零行修改**——与 common_functions.sh / block_height_monitor.sh / target_generator.sh / utils/__init__.py / utils/csv_data_processor.py 同属"零接触模块"安全岛；唯一可选优化 = 删 80 行死代码 + 修复 `set -euo pipefail` 污染(原 §4.3 Bug-6，与云无关)|
| `utils/unified_logger.py` | **0**(grep -cE `"AWS\|aws\|EBS\|ebs\|ENA\|ena_\|aws_ebs\|ebs_aws\|nitro"` = 0 实跑 2026-05-18 07:10 UTC retro 重跑；纯 stdlib `logging` 封装，零云术语) | 0(JSONFormatter L73-96 emit 11 字段 `timestamp/level/logger/message/module/function/line/exception/component/metric/performance` 全中立 + 4 特殊方法 emit dict 含 `metric/value/unit` `type/severity/details` `error_message/function/line` `analysis_type/result` 全中立；**JSONFormatter 间接 DEAD**——7 个消费者均未传 `config` 参 → DEFAULT_CONFIG L40 `'json_format': False` 永远生效 → 11 字段实际 0 emit；输出文件 `{name}_{YYYYMMDD}.log` 文件名由消费者 `__name__` 拼接，0 含 aws/ebs 字面) | 0(消费 6 个 env：LOGS_DIR LIVE（L177 _get_log_file_path 自读）+ 5 个 DEAD（LOG_LEVEL/LOG_FORMAT/LOG_JSON/LOG_CONSOLE/LOG_FILE @ L303-316 仅 setup_logging_from_env DEAD 函数引用）；消费 8 个 self.config[] key 全中立；消费 logging.LogRecord 标准 + 自定义 attr 全中立) | 不追加 | retro 2026-05-18 07:10 UTC：**纯 stdlib logging 封装库**(`UnifiedLogger` 类 + `get_logger` 工厂 + `ColoredFormatter`/`JSONFormatter` 2 个 stdlib Formatter 子类)；7 个 .py 外部消费者(utils/{unit_converter,csv_data_processor} + analysis/{cpu_ebs_correlation_analyzer,qps_analyzer,comprehensive_analysis,rpc_deep_analyzer} + visualization/advanced_chart_generator)只调 4 个基础方法(debug × 4 + info × 47 + warning × 20 + error × 35)；4 特殊方法 `performance/bottleneck/error_trace/analysis_result` + `critical` 全 DEAD(0 外部调用)；setup_logging_from_env + configure_root_logger + main 也全 DEAD；累计 ~142 行 DEAD 可选清理(7 公开 API + 1 main + JSONFormatter 间接 DEAD 27 行)；**GCP 迁移零行修改**——与 common_functions.sh / block_height_monitor.sh / target_generator.sh / utils/__init__.py / utils/csv_data_processor.py / utils/error_handler.sh 同属"零接触模块"安全岛(第 7 个)；日志层是平台无关基础设施，0 metadata API / 0 cloud provider 感知 |
| `utils/ebs_converter.sh` | **36**(grep -cE `"AWS\|aws\|EBS\|ebs\|ENA\|ena_\|aws_ebs\|ebs_aws\|nitro"` = 36 实跑 2026-05-18 07:05 UTC；密度集中在 注释 11 处 + 函数名 5 处 + 常量 3 处 + 文档 URL 3 处 + stdout/help 4 处 + 变量名 4 处 + 函数体引用 4 处 + 其他注释 2 处) | 7 个 bash 函数 export(L139-145)：`convert_to_aws_standard_iops` ⚠ / `convert_to_aws_standard_throughput` ⚠ / `calculate_io2_throughput` ⚠ / `recommend_ebs_type` [DEAD] ⚠ / `analyze_instance_store_performance` [DEAD] ⚠ / `calculate_weighted_avg_io_size` [DEAD] / `is_accounts_configured` ✅中立 + 3 个隐式常量(L7 `AWS_EBS_BASELINE_THROUGHPUT_SIZE_KIB` [DEAD] / L10 `IO2_THROUGHPUT_RATIO` / L14 `IO2_MAX_THROUGHPUT`) + stdout 类型字符串 "gp3"/"io2"/"instance-store"(L95/L102/L107，[DEAD] 函数内) | 0 (本文件无 source、无 read_file、无外部数据读入，纯叶子库) | 不追加(已在 §10.1 #5/#34 累计 `aws_standard_iops` 等下游索引；本文件 emit 端已覆盖) | retro 2026-05-18 07:05 UTC：**纯叶子库**(零上游、5 入度)；7 函数中 3 LIVE(convert_*×2 + calculate_io2_throughput) 仅 5 处下游、is_accounts_configured 31+ 处下游(已中立) + 3 DEAD(0 下游); P0 阻塞 = 文档 URL ×3(L25/L31/L83) + io2 专属算法(L62-67 `iops × 0.256`，GCP PD-Extreme 无对应) + EBS 类型枚举写死 gp3/io2/instance-store(L89-108，但函数 DEAD 优先清理); 改造工作量净 -11 行(配置 +20 / 业务 +25 / 删除 -45 / 注释 -11); **归一化层位置 = 本文件内 alias 即可**(下游 0 破坏性) |
| `utils/unified_logger.sh` | **0**(grep -cE `"AWS\|aws\|EBS\|ebs\|ENA\|ena_\|aws_ebs\|ebs_aws\|nitro"` = 0 实跑 2026-05-18 07:14 UTC retro；纯 bash 日志门面，零云术语 / 零 metadata 调用 / 零 SDK 引用) | 0(write_log L142-170 仅 emit 人类可读纯文本行 `${timestamp} [${level}] [${component}] ${message}` 到 stderr + `${LOGS_DIR}/${component}.log`；无 CSV 列定义 / 无 JSON 序列化 / 无 dict key 暴露给下游；唯一 dict `COMPONENT_LOG_FILES` L63 内部映射 0 外部读方；5 个 DEAD 函数 `get_log_file_path/log_bottleneck/log_error_trace/query_logs/generate_log_stats` 共 ~70 行可清理) | 0(仅消费 `LOGS_DIR`(L94/L296/L304 间接经 config_loader) + `LOGGER_COMPONENT`/`LOGGER_LEVEL`/`DEFAULT_LOG_LEVEL` 自定义中立变量；0 AWS 命名字段读取) | 不追加 | retro 2026-05-18 07:14 UTC：**纯 bash 日志门面**(8 公开函数：init_logger + log_{debug,info,warn,error,fatal} + log_performance + log_bottleneck/log_error_trace DEAD + log rotation 内部)；8 .sh 文件 source(unified_monitor 175 调用 / bottleneck_detector 28 / ebs_bottleneck_detector 40 / ena_network_monitor 14 / ebs_analyzer 15 / master_qps_executor 2 / error_handler 3 [SOURCE-ONLY init_logger] / iostat_collector 7 [SOURCE-ONLY init_logger])；输出文件仅 `${LOGS_DIR}/${component}.log` 后缀(L94/L296/L304/L370/L385/L392 共 6 处全 `.log`，0 含 aws/ebs 字面)；**GCP 迁移零行修改**——与 common_functions.sh / block_height_monitor.sh / target_generator.sh / utils/__init__.py / utils/csv_data_processor.py / utils/error_handler.sh / utils/unified_logger.py / utils/ena_field_accessor.py / utils/unit_converter.py 同属"零接触模块"安全岛(第 8 个 bash 实例)；日志层平台无关基础设施；唯一可选优化 = 删 ~70 行 DEAD code(非 GCP 强制) |

### 10.2 字段改名风险评分（按下游消费方数累加）

| 字段名 | 写方数 | 读方数 | 总下游影响范围 | 风险等级 | 中立化优先级 |
|--------|--------|--------|-----------------|----------|---------------|
| aws_standard_iops | 2 (Python + sh wrapper) | 9 文件 / ~16 处字面 | 🔴 极高 5 层契约链 | 🔴 极高 | P0 |
| aws_standard_throughput_mibs | 1 (sh) | 4 文件 / ~10 处字面（master_qps_executor + ebs_bottleneck_detector + framework_data_quality_checker；R4 worker iostat_collector.sh 精确化）| 🟠 高 | 🟠 高 | P1 |
| BOTTLENECK_EBS_*_THRESHOLD ×4 | 1 (env export) | 待 R4 grep | 🟡 中（变量名）| 🟡 中 | P2 |
| aws_standard_gbps | 1 | 0 | 🟢 死字段 | 🟢 低 | P2 |
| aws_display_mbps | 1 | 0 | 🟢 死字段 | 🟢 低 | P2 |
| aws_rx_gbps / aws_tx_gbps / aws_total_gbps | 1 | 0 | 🟢 死字段 | 🟢 低 | P2 |
| EBSC-1 `convert_to_aws_standard_iops` (函数符号) | 1 (utils/ebs_converter.sh:L26 + export L139) | 1 (monitoring/iostat_collector.sh:L121) | 🟢 低 1 hop | 🟢 低 | P1（本文件 alias 双 export 即可） — retro ebs_converter 2026-05-18 |
| EBSC-2 `convert_to_aws_standard_throughput` (函数符号) | 1 (utils/ebs_converter.sh:L44 + export L140) | 2 (iostat_collector.sh:L89 command-v 探测 + L99 调用) | 🟢 低 1 hop | 🟢 低 | P1（同 EBSC-1） — retro 2026-05-18 |
| EBSC-3 `calculate_io2_throughput` (函数符号 + io2 专属算法) | 1 (utils/ebs_converter.sh:L62 + export L141) | 2 (config/user_config.sh:L87 DATA_VOL_MAX_IOPS + L101 ACCOUNTS_VOL_MAX_IOPS) | 🟠 中（算法本身 io2 专属 + 2 处下游）| 🟠 中 | P0（GCP path 需 skip 或独立公式） — retro 2026-05-18 |
| EBSC-4 `IO2_THROUGHPUT_RATIO=0.256` (常量) | 1 (utils/ebs_converter.sh:L10) | 1 内部 (L64) + 0 外部 (grep .sh/.py 全仓 0) | 🟢 低（本文件闭环）| 🟢 低 | P1（值随 provider 变，直接改名 + 加 case 分发） — retro 2026-05-18 |
| EBSC-5 `IO2_MAX_THROUGHPUT=4000` (常量) | 1 (utils/ebs_converter.sh:L14) | 1 内部 (L65) + 0 外部 | 🟢 低 | 🟢 低 | P1（同 EBSC-4） — retro 2026-05-18 |
| EBSC-6 `AWS_EBS_BASELINE_THROUGHPUT_SIZE_KIB` (常量) | 2 重定义 (utils/ebs_converter.sh:L7 + config/system_config.sh:L54/L115 export) | 0 (grep .sh/.py 全仓 0 实质消费) | 🟢 死常量 | 🟢 低 | P1（删除本文件重复定义，system_config 双 export 旧+新一段时间） — retro 2026-05-18 |
| EBSC-7 `recommend_ebs_type` / `calculate_weighted_avg_io_size` / `analyze_instance_store_performance` (3 个 DEAD 函数) | 3 (export L142-144) | 0 | 🟢 死代码 | 🟢 低 | P0（直接删除 ~45 行，无双写需求） — retro 2026-05-18 |
| EBSC-8 stdout 类型字符串 "gp3"/"io2"/"instance-store" (L95/L102/L107) | 1 (recommend_ebs_type [DEAD]) | 0 实际（含在 DEAD 函数内）| 🟢 死字面（随 EBSC-7 删除归零）| 🟢 低 | P0（清理 EBSC-7 时同时消失） — retro 2026-05-18 |
| EBSC-9 AWS 文档 URL ×3 (L25/L31/L83) | 1 (utils/ebs_converter.sh 注释 + stdout) | 0 程序化（仅注释 + analyze_instance_store_performance stdout）| 🟢 低 | 🟢 低 | P0（抽 `DISK_DOC_URL` 配置 + case 分发） — retro 2026-05-18 |
| ENA_ALLOWANCE_FIELDS_STR | 1 (env export) | 5 文件 / 9 处 | 🔴 极高 | 🔴 极高 | P0 |
| ENA_MONITOR_ENABLED | 2 (user_config + config_loader) | 5 文件 / 11 处 | 🔴 极高 | 🔴 极高 | P0 |
| bw_in_allowance_exceeded (CSV col / ethtool field) | 1 (ena_network_monitor.sh:L92-94) | 4 (ena_field_accessor + device_manager + system_config + config_loader) | 🟠 高 | 🟠 高 | P0 (AWS-only 保留原名, GCP 写 dropped 代理) |
| bw_out_allowance_exceeded | 1 | 4 | 🟠 高 | 🟠 高 | P0 (同上) |
| pps_allowance_exceeded | 1 | 4 | 🟠 高 | 🟠 高 | P0 (同上) |
| conntrack/linklocal_allowance_* (3 字段) | 1 (动态写) | 2 | 🟢 低 | 🟢 低 | P0 (GCP 写空) |
| ENA_LOG (readonly local) | 1 | 0 外部 | 🟢 死 | 🟢 低 | P3 |
| bottleneck_status.json `.bottleneck_types[]` (JSON contract) | 1 (待 R4 确认) | 3 (benchmark_archiver + master_qps_executor + framework_data_quality_checker) | 🟠 高 (跨 3 文件) | 🟠 高 | P1 (字段名已中立；值含 "EBS" 字面需 detector 端中立化) |
| bottleneck_status.json `.bottleneck_values[]` | 1 (待 R4) | 1 (benchmark_archiver) | 🟢 低 | 🟢 低 | P2 |
| bottleneck_status.json `.bottleneck_detected` | 1 (待 R4) | 2 (benchmark_archiver + framework_data_quality_checker) | 🟢 低 | 🟢 低 | P2 |
| test_summary.json 全字段 | 1 (benchmark_archiver) | 0 (仅 --list/--compare 自查) | 🟢 死 | 🟢 低 | P3 (中立无需改) |
| test_history.json 全字段 | 1 (benchmark_archiver) | 0 | 🟢 死 | 🟢 低 | P3 (中立无需改) |
| MONITOR_TASKS["ena_network"] (bash key) | 1 (monitoring_coordinator) | 0 外部 (本文件内 4 自引用) | 🟢 低 | 🟢 低 | P2 (R4 worker monitoring_coordinator) |
| MONITOR_TASKS["ebs_bottleneck"] (bash key) | 1 (monitoring_coordinator) | 0 外部 (本文件内 4 自引用) | 🟢 低 | 🟢 低 | P2 (R4 worker monitoring_coordinator) |
| monitoring_status.json.coordinator_start_time / active_monitors | 1 (monitoring_coordinator) | 0 外部 | 🟢 死契约 | 🟢 低 | N/A (无需改) |
| monitor_pids.txt 行 `name:pid` 格式 | 1 (monitoring_coordinator) | 1 (本文件自读) | 🟢 死契约 | 🟢 低 | N/A (格式中立；name 含 AWS 字面归 6a/6b) |
| #25 substring `'total_iops'` (df col pattern) | 1 (framework_data_quality_checker.sh:L352-358) + iostat_collector.sh (待 R6) | 8 文件 / ~17 处（comprehensive_analysis.py:L373 + qps_analyzer.py:L128/134 + ebs_bottleneck_detector.sh:L134/142/167/177 + ebs_analyzer.sh:L45/64 + ebs_chart_generator.py:L113/137/210/226/234/290/354 + unit_converter.py:L239/250）| 🟠 高 | 🟢 低（字段名本身已中立）| P3 ❌ 无需双写 |
| #26 bottleneck_types element 字面 `'EBS'` (str in list) | 1 (analysis/qps_analyzer.py:L964 dict key + L1022 in 操作；**R7 worker 2026-05-18 实证**) | 4 (comprehensive_analysis.py:L539/L588/L636 硬编码 `if 'EBS' in ...` + qps_analyzer.py:L1022 + report_generator.py:L3815 chart_title replace) | 🟠 高（AWS 术语耦合点）| 🟠 高 | P1 ✅ 必须双写（qps_analyzer.py L964 加 `'PD': 0.3, 'Disk': 0.3`；L1022 改 `if any(t in bottleneck_types for t in ('EBS','PD','Disk'))`；归一化层 normalize_bottleneck_type() 负责映射）|
| #27 | dict keys `bottleneck_factors` / `correlations` / `performance_level` / `performance_grade` / `comprehensive_score` / `max_qps` / `bottleneck_qps` | 1 (comprehensive_analysis.py:L257-294/L515-525/L843-849 + L923 JSON dump) | 0 外部（self main() 消费 + bottleneck_analysis_result.json 终端产物 0 解析方）| 🟢 死内部 | 🟢 低 | P3 ❌ 无需改（已全部中立无 AWS 字面）|
| #30 | log_performance metric keys `DATA_avg_iostat_util` / `_max_iostat_util` / `_avg_iops` / `_max_iops` + ACCOUNTS_* (8 keys) | 1 (tools/ebs_analyzer.sh:L134-L137 ×2 设备名分支) | **0 程序化下游**（grep `_avg_iostat_util\|_max_iostat_util` 全仓 = 仅 utils/unified_logger.sh:L201 定义 + L354/372/390 doc/示例；写到 log 文件无程序化消费方）| disk | 已全部中立（iostat / IOPS 是 OS-level 通用词）| ❌ 无需改 |
| #31 ENA_ALLOWANCE_FIELDS (default value @ config_loader.sh:L829) | 1 (config_loader.sh:L829 default) | 2 (ena_field_accessor.py:L64 fallback + L77 debug print；advanced_chart_generator.py:L694 仅 tip) | 🟢 低 (独立 fallback 链) | 🟢 低 | P1 ✅ 双写（与 #12 `_STR` 版本独立，因 ena_field_accessor.py 兜底逻辑会先查 `_STR` 再查无后缀版本）|
| #30 LAYOUT_CONFIGS key `'ebs_2x2'` (chart_style_config.py:L389) | 1 (chart_style_config.py:L389) | 0 外部（grep 全仓 0 消费）| 🟢 死 dict key | 🟢 低 | P2 ❌ 无需双写 — 直接删或改 `'disk_2x2'` |
| #31 `CPUEBSCorrelationAnalyzer` (Python class name) | 1 (cpu_ebs_correlation_analyzer.py:L32) | 2 (performance_visualizer.py:L33 import + L131 instantiate；但实例方法零调用 — grep `correlation_analyzer\.` 全仓 0) | 🟢 低 (有效下游 0 — 类被构造但不调用任何方法) | 🟢 低 | P2 ✅ 保留别名 `CPUEBSCorrelationAnalyzer = CPUDiskCorrelationAnalyzer` 兼容 |
| #32 `required_ebs_cols` (cpu_ebs_correlation_analyzer.py L63/L69/L80/L84 局部变量) | 1 | 0 外部 | 🟢 死局部 | 🟢 低 | P3 ❌ 直接改名 |
| #33 cpu_ebs_correlation_analyzer.py 消费字段（cpu_iowait/usr/sys/idle/soft + data_*_*/accounts_*_* iostat 列）| 0 (本文件 reader) | 15 字段 / 9 处 `startswith('data_')` 硬耦合 | 🟢 字段名本身已中立 | 🟢 低 | N/A ❌ 已中立 — 但与 iostat_collector 设备前缀形成隐式契约 |
| #34a | `DEPLOYMENT_PLATFORM` (env var, 部署平台枚举) | config/system_config.sh:L12 + export L111 | config/config_loader.sh:L102/L107/L111/L116/L117/L127/L135/L823 (8) + tools/framework_data_quality_checker.sh:L602 (1) | enum | `CLOUD_PROVIDER` | ✅ 必须双写（已是事实标准变量名，需 fallback alias）|
| #34b | `ENA_ALLOWANCE_FIELDS_STR` (env var, word-split 源) | config/system_config.sh:L109 export（**真正源** — TRACKER #12 已含本文件，retro 确认）| monitoring/ena_network_monitor.sh:L63/L92/L118/L217 (4) + monitoring/bottleneck_detector.sh:L471 (1) + monitoring/unified_monitor.sh:L501/L516/L532/L1908/L2079 (5) + tools/framework_data_quality_checker.sh:L376/L377 (2) + utils/ena_field_accessor.py:L60/L76 (2) = 14 处 | net | `NIC_ALLOWANCE_FIELDS_STR` | ✅ 必须双写（与 TRACKER #12 同字段，retro 确认 system_config.sh 是真正写方）|
| #34c | `MONITORING_PROCESS_NAMES_STR` (env var, word-split 源) | config/system_config.sh:L110 export | monitoring/unified_monitor.sh:L556/L1404/L1406/L1841/L1842/L2695 (6) | meta | 字段名已中立，但**元素 `ena_network_monitor` 需 platform filter** | ⚠ 字段名 ❌；元素 ✅ filter |
| #34d | `MONITORING_PROCESS_NAMES` (bash 数组) | config/system_config.sh:L63-75 + export L111 | (无外部数组形态消费 — 全经 _STR 版本) | meta | 同上 | ⚠ 同上 |
| #34e | `AWS_EBS_BASELINE_IO_SIZE_KIB` (常量) | config/system_config.sh:L53 + export L115 | utils/ebs_converter.sh:L7 (同名 fallback 重定义，**非读消费**) | iops | `CLOUD_IO_BASELINE_KIB` (aws=16 / gcp=4) | ✅ 双写（防御性）|
| #34f | `AWS_EBS_BASELINE_THROUGHPUT_SIZE_KIB` (常量) | config/system_config.sh:L54 + export L115 | utils/ebs_converter.sh:L7 (同名 fallback) = 1 处 | iops | `CLOUD_THROUGHPUT_BASELINE_KIB` | ✅ 双写 |
| #34g | `AWS_METADATA_ENDPOINT` (URL) | config/system_config.sh:L57 + export L115 | config/config_loader.sh:L106 (curl probe instance-id, platform detection 核心) = 1 处 | meta | `METADATA_ENDPOINT` (aws=169.254.169.254 / gcp=metadata.google.internal) | ✅ 双写 |
| #34h | `AWS_METADATA_API_VERSION` (path 段) | config/system_config.sh:L59 + export L115 | config/config_loader.sh:L106 (同 #34g 一行 curl) = 1 处 | meta | `METADATA_API_PATH` (aws=latest / gcp=computeMetadata/v1) | ✅ 双写 |
| #34i | `AWS_METADATA_TOKEN_TTL` (IMDSv2 TTL) | config/system_config.sh:L58 + export L115 | **0 处真实消费** (IMDSv2 token PUT 路径未启用) | meta | 死字段 — 删除或保留供 IMDSv2 升级 | ❌ 死字段 |
| #34j | `OVERHEAD_CSV_HEADER` (CSV header 字符串, 20 字段) | config/system_config.sh:L92 + export L116 | monitoring/unified_monitor.sh:L214/L1580/L1784/L1785/L1786/L1788/L1814/L1853/L1854/L2506 = 10 处 | meta | 已全中立（20 字段无 AWS 字面）✅ | ❌ 无需改 |
| #34k | `TIMESTAMP_FORMAT` (date 格式串) | config/system_config.sh:L78 + export L116 | monitoring/iostat_collector.sh:L234 + monitoring/unified_monitor.sh:L2445 = 2 处 | meta | 已中立 ✅ | ❌ |
| #34l | `get_unified_timestamp` / `get_unified_epoch` (bash 函数) | config/system_config.sh:L80-86 + `export -f` L108 | core/common_functions.sh:L12 (同名 wrapper 覆盖) + 17 处实际调用方（bottleneck_detector + unified_event_manager ×4 + unified_monitor ×6 + block_height_monitor ×6）| meta | 已中立 ✅ | ❌ |
| #35a | `event_type` 值字面 `"ebs_bottleneck"` (JSON value, 非字段名) | monitoring/unified_event_manager.sh:L36 (注释示例) + L262 (help echo 文本) | **0 程序化生产者** (grep `record_event_start.*ebs_bottleneck` 全仓 = 0; grep `start "ebs_bottleneck"` 全仓 = 0); **0 程序化下游消费方** (tools/framework_data_quality_checker.sh:L543 仅 validate_json_file schema 校验不读值) | event_type value | `"disk_bottleneck"` (保留 `"ebs_bottleneck"` 别名) | ⚠ 仅当未来添加真实生产者时双写；当前 0/0 可直接改字面 |
| #35b | `event_id` / `event_source` / `event_details` / `current_qps` / `start_time` / `start_epoch` / `end_time` / `end_epoch` / `duration` / `status` (10 字段 unified_events.json) | monitoring/unified_event_manager.sh:L57-67 + L101-104 (record_event_*) | monitoring/unified_event_manager.sh:L100/L111-114/L177/L197/L212 (本文件闭环 jq 读) + monitoring/block_height_monitor.sh:L184 spawn stdout 捕获 event_id 后 L217 反向 spawn `end "$BLOCK_HEIGHT_DIFF_EVENT_ID"` | meta | 字段名 100% 已中立 ✅ | ❌ 无需改 |
| #35c | `action` / `timestamp` (2 字段 event_notification.json) | monitoring/unified_event_manager.sh:L138/L142 + L159/L164 | **0 程序化消费方** (grep 全仓: tools/benchmark_archiver.sh:L268 仅 `rm -f event_notification.json` 不读) | meta | 已中立 ✅ | ❌ 死契约 — notify_components_event_* 设计意图未实现 |
| #35d | `record_time_range` (bash 函数) | **NOT-FOUND-IN-CODE** — grep `record_time_range` 全仓唯一命中 = monitoring/unified_event_manager.sh:L124 调用点本身，**无任何定义** | monitoring/unified_event_manager.sh:L124 (dangling call) | meta/函数 | N/A — 功能 bug，与 GCP 无关；建议删 L123-124 或在 utils/ 加 stub | ❌ 不涉及改名 |

| #34a `DEPLOYMENT_PLATFORM` (env enum, 来源 system_config.sh:L12) | 1 | 9 (config_loader 8 + tools 1) | 🟠 高 (8 个 case 分支) | 🟠 高 | P0 ✅ 双写（CLOUD_PROVIDER alias 路径必须先建）|
| #34b `ENA_ALLOWANCE_FIELDS_STR` (system_config.sh:L109 真正源, 等同 TRACKER #12) | 1 | 14 / 5 文件 | 🔴 极高 | 🔴 极高 | P0 ✅ 必须双写（与 #12 同字段）|
| #34c `MONITORING_PROCESS_NAMES_STR` (元素含 `ena_network_monitor`) | 1 | 6 (unified_monitor 全部) | 🟠 高 (字段名中立，元素非中立) | 🟠 高 | P1 ✅ 字段名免改；元素 platform filter |
| #34e `AWS_EBS_BASELINE_IO_SIZE_KIB` | 1 | 0 (ebs_converter.sh:L7 仅 fallback 重定义非读) | 🟢 极低 | 🟢 低 | P2 ✅ 防御性双写（防 ebs_converter 反向覆盖）|
| #34f `AWS_EBS_BASELINE_THROUGHPUT_SIZE_KIB` | 1 | 1 (ebs_converter.sh:L7) | 🟢 低 | 🟢 低 | P2 ✅ 双写 |
| #34g `AWS_METADATA_ENDPOINT` | 1 | 1 (config_loader.sh:L106) **但是 platform detection 核心** | 🟠 高（关键单点）| 🟠 高 | P0 ✅ 双写 + case 分发 |
| #34h `AWS_METADATA_API_VERSION` | 1 | 1 (同 #34g 同行 curl) | 🟠 高（同上）| 🟠 高 | P0 ✅ 同 #34g 一起改 |
| #34i `AWS_METADATA_TOKEN_TTL` | 1 | 0 | 🟢 死字段 | 🟢 低 | P3 ❌ 删 (或保留供 IMDSv2) |
| #35a `event_type` 值 `"ebs_bottleneck"` (unified_event_manager.sh:L36/L262) | 0 程序化生产者 (仅注释+help echo) | 0 程序化消费方 (framework_data_quality_checker 仅 schema 校验不读值) | 🟢 极低 (0/0) | 🟢 低 | P2 ❌ 直接改字面 `disk_bottleneck` + 保留 `ebs_bottleneck` 别名（无下游可破坏）|
| #35b unified_events.json 10 字段 (event_id/event_source/event_details/current_qps/start_time/start_epoch/end_time/end_epoch/duration/status) | 1 (unified_event_manager.sh:L57-67 + L101-104) | 本文件闭环 7 处 jq 读 (L100/L111-114/L177/L197/L212) + block_height_monitor.sh:L184 spawn stdout 捕获 event_id | 🟢 极低 (字段名 100% 中立 + 仅 1 个跨文件 stdout 字符串契约) | 🟢 低 | N/A ❌ 无需改 |
| #35c event_notification.json 2 字段 (action/timestamp) | 1 (unified_event_manager.sh:L138/L142 + L159/L164) | 0 程序化消费方 (benchmark_archiver.sh:L268 仅 rm 不读) | 🟢 死契约 | 🟢 低 | P3 ❌ 死契约，建议删除 notify_components_event_* 整段或补真实 consumer |
| #35d `record_time_range` (bash 函数 dangling call) | **0 定义** (grep 全仓唯一命中 = 调用点本身) | unified_event_manager.sh:L124 (唯一调用点) | 🟢 极低 (运行时 stderr 报错被 flock 子 shell 吞掉，主流程不挂)| 🟢 低 | N/A 功能 bug — 与 GCP 无关，建议删 L123-124 或在 utils/ 加 stub |
| #36 | analysis/rpc_deep_analyzer.py **整文件零 AWS 字面字段** (grep `AWS\|aws\|EBS\|ebs\|ENA\|ena_\|nitro` = 0) | （本文件无写方）| comprehensive_analysis.py:L722-723 (仅读 `bottleneck_classification.recommendations`) | meta/dict | 全部已中立 ✅ | N/A — emit 7 大类 ~25 字段 100% 已中立，无需双写 (R7 worker rpc_deep_analyzer.py 2026-05-18) |
| #36a | analysis/rpc_deep_analyzer.py `primary_bottleneck` 枚举值 (L361/L398/L410/L419/L429/L442/L451) = `{'unknown','cpu','memory','rpc_processing','network_io','balanced'}` | analysis/rpc_deep_analyzer.py 自身 | comprehensive_analysis.py:L722 (仅读 recommendations 不读枚举值本身) | enum/value | **枚举中无 `'ebs'`/`'disk'` 字面**，`'network_io'` 已合并磁盘+网络 IO | N/A ❌ 无需改 — 可选未来拆 `'disk_io'`/`'network_io'`（非 GCP 阻塞，0 下游布尔判定）|

| #34 + #35 (`aws_standard_iops` / `aws_standard_throughput_mibs` — 本文件作为第 5 个 reader 视角) | 已计入 #5（写方 iostat_collector），本条仅累加 reader 视角 | +1 reader 文件（tools/ebs_bottleneck_detector.sh，~16 处字面）→ 总 5+ 层契约链不变 | 🔴 极高 5+ 层（不变）| 🔴 极高 | P0（与 #5 同优先级，必须双写）|
| #36 `current_aws_iops` (局部变量) | 1 (detect_ebs_bottleneck) | 0 外部 | 🟢 局部 | 🟢 低 | P3 ❌ 直接改名 |
| #37 `BOTTLENECK_EBS_*_THRESHOLD` env | 3-4 (config_loader / internal_config / 可能 user_config) | 1 文件 / 9 处（本文件 L21-L429）+ 文档若干 | 🟠 高（env 全局）| 🟠 高 | P2 ✅ env alias 一行兼容 |
| #38 `BOTTLENECK_LOG_FILE` env（仅死代码引用）| 0（本文件未定义；上游 grep 全仓 0 命中）| 4 处全在死代码内 | 🟢 死代码引用 | 🟢 低 | P3 ❌ 与死代码同删 |
| #39 `DATA_VOL_TYPE` / `ACCOUNTS_VOL_TYPE` (user_config.sh:L19/L25, retro 2026-05-18) | 1 (user_config) | 3 文件（iostat_collector + ebs_converter + unified_monitor）/ iostat_collector L152/L178 强校验失败即 log_error 退出 | 🟠 高（**值域**风险极高 — 字段名中立但 `io2` 字面阻塞 GCP）| 🟠 高（值域，非字段名）| P0 ✅ 值域扩 enum；字段名 ❌ 无需双写 |
| #40 `DATA_VOL_MAX_IOPS` / `ACCOUNTS_VOL_MAX_IOPS` / `DATA_VOL_MAX_THROUGHPUT` / `ACCOUNTS_VOL_MAX_THROUGHPUT` (user_config.sh:L21/L22/L27/L28, retro) | 1 (user_config) | 8/7/7/7 = 跨 4-5 文件 | 🟢 极低（字段名 100% 中立）| 🟢 低 | P3 ❌ 字段名免改；仅文档化 GCP 数值参考 |
| #41 `ENA_MONITOR_ENABLED` (user_config.sh:L35 是默认源 + config_loader 是 platform 覆写源, retro) | 2 (user_config + config_loader — 双写方确认) | 同 #13（9 文件 / 14 处）| 🔴 极高 | 🔴 极高 | P0 ✅ 必须双写（在归一化层 config_loader.sh:L108 实现）|
| #42 `EBS_MONITOR_RATE` (user_config.sh:L40, retro) | 1 (user_config) | 2 处下游（unified_monitor + iostat_collector 待精确 grep）| 🟢 低 | 🟢 低 | P2 ✅ 双写 alias（下游 2 处可一次性切，单 Round 拆 + 删）|
| #43 `LEDGER_DEVICE` / `ACCOUNTS_DEVICE` (user_config.sh:L12/L13-14, retro; **默认值** `nvme1n1`/`nvme2n1` 来自 AWS Nitro 命名约定) | 1 (user_config) | 8/11 文件下游（已计入 #34/#35 CSV header 链）| 🟠 高（默认值层）| 🟢 低（字段名层）| P1 ⚠ 字段名 ❌；默认值仅文档化 GCP 用户须 `lsblk` 验证 |
| #49a | `data_aws_standard_*` / `accounts_aws_standard_*` (本文件 = **第二写方** + 第 N 个 reader，R8 ebs_chart_generator) | +1 写方（visualization/ebs_chart_generator.py:L126/L133/L148/L154 重算覆写；与 iostat_collector 并列）| +28 reader 字面（本文件内 26 处 get_mapped_field + 2 处直字面 L1238/L1243）→ 已计入 #5/#7 9 文件链 | 🔴 极高（不变，本文件追加 reader/writer 视角不改变契约层数）| 🔴 极高 | P0（与 #5/#7 同优先级，必须双写）|
| #49b | algorithm constant `16` KiB IO baseline（visualization/ebs_chart_generator.py:L125/L127/L128/L149 硬编码 magic number）| 1（本文件唯一硬编码点）| 0 外部 reader（局部 algorithm）| 🔴 高（GCP PD baseline=4 KiB / Hyperdisk=8 KiB 与 AWS 16 KiB 不同，直接产生错误的 standard_iops 数值）| 🔴 高 | P0 ✅ 必须 platform-aware（引入 `utils/cloud_constants.py.IO_BASELINE_KIB`，或读 `os.getenv('CLOUD_IO_BASELINE_KIB', '16')`）|
| #49c | `EBSChartGenerator` (Python class name) | 1（visualization/ebs_chart_generator.py:L26）| 1 文件 / 4 处（performance_visualizer.py:L27/L2267/L2276/L2536）| 🟢 低 | 🟢 低 | P1 ✅ 类名 alias 1 行兼容 |
| #49d | 6 个 public 方法 `generate_all_ebs_charts` / `generate_ebs_*` / `validate_ebs_integration` | 1（ebs_chart_generator.py:L180/L700/L829/L969/L1125/L1291）| 1 文件 + 本文件内 5 处 dispatcher（generate_ebs_performance_overview 等被 generate_all_ebs_charts L196-200 调用）| 🟢 低 | 🟢 低 | P2 ⚠ 入口 `generate_all_ebs_charts` 需 alias；`validate_ebs_integration` 0 调用可直接改名 |
| #49e | `_is_accounts_configured` (Python 死方法 @ L823-827) | 1（ebs_chart_generator.py:L823）| 0（本文件内 0 调用 + 0 外部）| 🟢 死 | 🟢 低 | P3 ❌ 直接删 5 行（与 GCP 无关）|
| #44 `ebs_util` JSON key (写方: monitoring/unified_monitor.sh) | 1 (本文件 L1944-1985) | 3+ 文件 / 7+ 处 (master_qps_executor.sh:L670/L702 + analysis/qps_analyzer.py:L82-167) | 🔴 极高 (跨进程 JSON 契约 + 多 fallback 读) | 🔴 极高 | P0 ✅ 必须双写 (JSON 同写 ebs_util + disk_util) |
| #45 `ebs_latency` JSON key | 1 (本文件 L1944-1985) | 3+ 文件 / 8+ 处 (master_qps_executor.sh:L355/L356/L359/L671/L703 含阈值判断 + qps_analyzer.py:L97-121) | 🔴 极高 (有 bottleneck 判定逻辑) | 🔴 极高 | P0 ✅ 必须双写 + 阈值变量 BOTTLENECK_EBS_LATENCY_THRESHOLD 同步双读 |
| #46 `ena_data` JSON sub-object | 1 (本文件 L1986-1998) | 1+ (framework_data_quality_checker.sh:L520-521 顶层 schema 校验) | 🟠 高 (子对象 key + 潜在 visualization 读) | 🟠 高 | P1 ✅ 双写 |
| #47 `ena_*_allowance_exceeded` CSV 6 列 | 1 (本文件 L1904-1931 + L2064-2089) | 3+ (framework_data_quality_checker.sh:L376-377 + qps_analyzer.py 动态字段发现 + ena_network_monitor.sh:L63/L92/L118/L217 兄弟生产者) + **blockchain_node_benchmark.sh:L434 grep -q "ena_" 模式（4th reader, R-ROOT retro 2026-05-18, has_ena_fields 变量未被实际消费仅打 L436 stdout 日志）** | 🟠 高 (列名通过 env 注入间接传播 + R-ROOT 入口 grep 模式追加 1 reader) | 🟠 高 | P1 ✅ env 注入式双写（改 ENA_ALLOWANCE_FIELDS_STR 即改列名）+ R-ROOT 入口同步改 grep 模式为 platform-aware case 分发（见 file-notes/blockchain_node_benchmark.sh.md §8.3 改造示例）|
| #48 log 文本 "AWS environment"/"Non-AWS environment" | 1 (本文件 L2206-2210 echo) | 0 程序化 | 🟢 极低 | 🟢 低 | P3 ❌ 直接替换 |
| #49 `"ebs_bottleneck_detector.log"` / `"ebs_analyzer.log"` (log scan 白名单字面，tools/framework_data_quality_checker.sh:L438 唯一处) | 1 (本文件白名单数组字面) | 0（grep 字面消费方 = 0；白名单本身是 reader 端硬编码）| 🟠 高（**与 TRACKER 10.3 #14/#7 改名链强耦合**：若 tools/ebs_bottleneck_detector.sh / tools/ebs_analyzer.sh 重命名为 `disk_*.log` → 本行扫描不到 → log 错误检查静默失效，**不会报错只会漏**）| 🟠 高 | P1 ✅ 白名单同时含 `ebs_*.log` 和 `disk_*.log` 两个模式（R6 worker framework_data_quality_checker.sh 2026-05-18 新发现，独立于 #34/#35 字段链）|
| #52 `bottleneck_info['ebs_bottlenecks']` JSON top-level key (R8 report_generator 新发现) | 1 (bottleneck_detector 待 R4 确认) | 1 (visualization/report_generator.py:L2724/L2725/L2729 唯一 reader) | 🟠 高(跨进程 JSON 契约,嵌套 list of dicts 含 device_type/type/severity/details/value 子结构) | 🟠 高 | P0 ✅ 双名 fallback `.get('disk_bottlenecks') or .get('ebs_bottlenecks', [])`(本文件 reader 端 + writer 端同写) | R8 worker report_generator.py 2026-05-18 |
| #53 `bottleneck.get('device_type'/'type'/'severity'/'details'/'value')` 嵌套 dict keys | 同 #52 | 同 #52 | 🟢 低(键名已全部中立 — 设备/瓶颈语义无云字面) | 🟢 低 | N/A ❌ 无需改 | R8 worker 2026-05-18 |
| #54 `ebs_bottleneck_detector.log` 文件路径硬编码(R8 report_generator reader 视角) | 1 (tools/ebs_bottleneck_detector.sh 写) | 2 (本文件 L1188 + framework_data_quality_checker:L438 白名单已记录 #49) | 🟠 高(改名链第 2 reader,文件不存在则 EBS 章节静默空白)| 🟠 高 | P1 ✅ 双路径 fallback `for name in ('disk_bottleneck_detector.log','ebs_bottleneck_detector.log'): if os.path.exists(...)` | R8 worker report_generator.py 2026-05-18 — 与 §10.3 #14 同步 |
| #55 log text pattern `'EBS BOTTLENECK DETECTED'` 7 段隐式文本契约 | 1 (tools/ebs_bottleneck_detector.sh echo) | 1 (本文件 L1518 唯一 parser) | 🟠 高(强耦合上游 echo 文本,parse 失败即 warning 解析为空)| 🟠 高 | P1 ✅ 双 pattern OR;长期建议 log 改 JSON 结构化 | R8 worker report_generator.py 2026-05-18 |
| #56 `*_aws_standard_iops` / `*_aws_standard_throughput_mibs` CSV 列(R8 report_generator 第 10 reader 视角) | 已计入 #5/#7(iostat_collector + ebs_chart_generator 双写方) | +1 reader 文件(本文件 L1761-L1780,4 处 endswith)→ 总 10 文件 / 5+ 层契约链不变 | 🔴 极高(不变) | 🔴 极高 | P0(与 #5/#7 同优先级,必须双写) | R8 worker report_generator.py 2026-05-18 |
| #57 `bottleneck_status.json.performance_metrics.{ebs_util,ebs_latency,ebs_aws_iops,ebs_throughput}` (R-RETRO bottleneck_detector 新发现) | 1 (bottleneck_detector.sh:L94-97/L116-119/L147-150) | 同 #44/#45 reader 链 = ≥3 文件 / 8+ 处 (master_qps_executor + qps_analyzer + report_generator) | 🔴 极高 (跨进程 IPC + bottleneck 判定逻辑 + 阈值比较) | 🔴 极高 | P0 ✅ 必须双写 (同 JSON 写 disk_* + ebs_* 两 key) | R-RETRO bottleneck_detector.sh 2026-05-18 |
| #58 `bottleneck_status.json.counters.{ebs_util,ebs_latency,ebs_aws_iops,ebs_aws_throughput,ena_limit,...}` (10 字段嵌套 dict) | 1 (bottleneck_detector.sh:L161-170) | 0 外部 reader (本文件自写不读) | 🟢 死 dict | 🟢 低 | P3 ❌ 无需双写 — 可直接改名 | R-RETRO bottleneck_detector.sh 2026-05-18 |
| #59 `bottleneck_counters.json` 全字段 (10-16 key 动态) | 1 (bottleneck_detector.sh:L180-202) | 1 = 本文件 L205-218 自闭环 IPC + 0 外部 | 🟢 低 (但跨 Round 持久化需注意) | 🟢 低 | P2 ✅ load 时双 key 累加 (避免新版加载旧 .json 丢 counter) | R-RETRO bottleneck_detector.sh 2026-05-18 |
| #60 `bottleneck_status.json.ebs_baselines.*` (4 字段) | 1 (bottleneck_detector.sh:L154-159) | 0 外部 reader (grep `ebs_baselines` 全仓 = 仅本文件 L154) | 🟢 死字段 | 🟢 低 | P3 ❌ 直接改名 `disk_baselines` 或保留 | R-RETRO bottleneck_detector.sh 2026-05-18 |
| #61 `ena_baseline.json` 全字段 (动态) | 1 (bottleneck_detector.sh:L502-518) | 1 = 本文件 L526-528 自闭环 IPC + 0 外部 | 🟢 低 | 🟢 低 | P2 ✅ 直接改 `nic_baseline.json` + 加路径 fallback | R-RETRO bottleneck_detector.sh 2026-05-18 |
| #62 `BOTTLENECK_NETWORK_THRESHOLD` env (retro ena_field_accessor) | [GAP] 写方未在 ena_field_accessor scope 验证 | 1 (utils/ena_field_accessor.py:L162 唯一 reader，**在 DEAD method `get_unified_network_thresholds` 内**) | 🟢 极低（DEAD method reader）| 🟢 低 | P3 ❌ 无需双写（字段名已中立 + reader DEAD）；建议随 DEAD method 删除同步降级 | retro ena_field_accessor.py 2026-05-18 |
| #63 `ENAFieldAccessor.analyze_ena_field()` 返回 dict 6 key | 1 (utils/ena_field_accessor.py:L97-L122 运行时构造) | 13 处下游（advanced_chart_generator.py 12 处 display_name/type/字串判定 + report_generator.py 1 处 aws_description EN-only 分支 L3187 + 2 处 type 值域 L3201/L3212-L3214）| 🟠 高（`aws_description` 跨 2 文件 13 reader）| 🟠 高（值域 `type ∈ {counter,gauge}` 已中立；命名层 1/6 key 含 AWS 字面）| P1 ⚠ `aws_description` ✅ 必须双写 alias（reader 用 `.get()` 已防御性 fallback，writer L17/L24/L31/L38/L45/L52 同 emit `cloud_description`）；其余 5 key 已中立 ❌ 无需改 | retro ena_field_accessor.py 2026-05-18 — 与 §10.1 #28 配对（#28 抽象层 +#63 dict key 粒度）|
| 62 | 函数名 ABI `convert_to_aws_standard_iops` (bash exported function) | utils/ebs_converter.sh:L26 (定义) + L139 (`export -f`) | monitoring/iostat_collector.sh:L121 (唯一真实调用) | function ABI | `convert_to_standard_iops` | ✅ 双名 `export -f` 1 Round 过渡（本文件 L139 追加 alias 行）— retro ebs_converter.sh 2026-05-18 06:54 UTC |
| 63 | 函数名 ABI `convert_to_aws_standard_throughput` | utils/ebs_converter.sh:L44 + L140 export | monitoring/iostat_collector.sh:L99 (真调) + L89/L104 (command -v 探测) | function ABI | `convert_to_standard_throughput` | ✅ 双名 export | retro ebs_converter.sh 2026-05-18 |
| 64 | 函数名 ABI `calculate_io2_throughput` | utils/ebs_converter.sh:L62 + L141 export | config/user_config.sh:L87/L101 (2 处自动算 throughput) | function ABI | 保留名（已不含 EBS 字面，io2 是值域问题非命名问题）| ❌ 无需改名；§8.3 早返回 GCP 分支处理 | retro ebs_converter.sh 2026-05-18 |
| 65 | 函数名 ABI `recommend_ebs_type` / `calculate_weighted_avg_io_size` / `analyze_instance_store_performance` (3 个死函数) | utils/ebs_converter.sh:L89/L113/L72 + L142/L143/L144 export | **0 外部调用方**（grep 全仓 0 命中，本文件 export 但无 caller）| function ABI (dead) | 直接删 -55 行 | ❌ 死代码与 GCP 改造无关；建议下一 Round 删除 | retro ebs_converter.sh 2026-05-18 |
| 66 | 函数名 ABI `is_accounts_configured` (bash) + Python 版 device_manager.is_accounts_configured (类方法) | utils/ebs_converter.sh:L134 + L145 export (bash) + visualization/device_manager.py (Python 版) | 41 处下游（monitoring/ + tools/ + visualization/ebs_chart_generator.py:L136/L223/L407 经 device_manager 中转）| function ABI | 已中立 ✅ | ❌ 无需改名 — 名字 platform-agnostic | retro ebs_converter.sh 2026-05-18 |
| 67 | 常量 `IO2_THROUGHPUT_RATIO=0.256` / `IO2_MAX_THROUGHPUT=4000` (bash env, AWS io2 专属) | utils/ebs_converter.sh:L13/L15 | utils/ebs_converter.sh:L66/L68 (本文件 calculate_io2_throughput 唯一引用) | algorithm constant | `AWS_IO2_THROUGHPUT_RATIO` / `AWS_IO2_MAX_THROUGHPUT`（前缀澄清专属）| ❌ 直接改（本文件局部，0 外部 grep）；GCP 不需要此常量 | retro ebs_converter.sh 2026-05-18 |

**风险等级**：
- 🔴 极高 = 5+ 下游 → 必须双写过渡期，必须先建归一化层
- 🟠 高 = 2-4 下游 → 双写过渡期推荐
- 🟢 低 = 0-1 下游 → 可直接改名

### 10.3 输出文件命名清单（按文件分组的 platform-aware 改造点）

| # | 写命名的代码文件 | 行号 | 文件名/标题模板 | 输出类型 | 当前样例 | platform-aware 改造方案 |
|---|--------------------|------|------------------|----------|----------|--------------------------|
| 1 | monitoring/ena_network_monitor.sh | L26 | `${LOGS_DIR}/ena_network_monitor.log` | .log | `/tmp/.../ena_network_monitor.log` | case 分发：AWS → `ena_network_monitor.log` / GCP → `gvnic_network_monitor.log`，或统一改 `nic_network_monitor.log` |
| 2 | monitoring/ena_network_monitor.sh | L30 | `${LOGS_DIR}/ena_network_${SESSION_TIMESTAMP}.csv` (readonly ENA_LOG) | .csv | `/tmp/.../ena_network_20260518_120000.csv` | platform-aware：`${LOGS_DIR}/$(nic_log_prefix)_network_${SESSION_TIMESTAMP}.csv`，prefix 由新建 `utils/nic_log_prefix.sh` 提供 |
| 3 | monitoring/ena_network_monitor.sh | L256 | help text `ena_network_*.csv` | stdout | usage `Analyze ENA log` | 注释/help 文本中立化（不影响下游）|
| 4 | monitoring/monitoring_coordinator.sh | L23 | `${TMP_DIR}/monitoring_status.json` (readonly MONITOR_STATUS_FILE) | .json | `/tmp/.../monitoring_status.json` | **无需改** — 文件名已中立，无 AWS/EBS 字面 ✅ (R4 worker monitoring_coordinator 确认本文件无 platform-aware 输出文件命名改造点) |
| 5 | monitoring/monitoring_coordinator.sh | L26 | `${TMP_DIR}/monitor_pids.txt` (readonly MONITOR_PIDS_FILE) | .txt | `/tmp/.../monitor_pids.txt` | **无需改** — 文件名已中立 ✅ |
| 4 | analysis/comprehensive_analysis.py | L457 | `comprehensive_analysis_charts.png` (文件名 + savefig) | .png | `{OUTPUT_DIR}/comprehensive_analysis_charts.png` | ✅ 文件名已中立（无 aws/ebs 字面）；下游 visualization/report_generator.py:L4017 引用，改名需同步 |
| 5 | analysis/comprehensive_analysis.py | L757 | `comprehensive_analysis_report.md` (heredoc 写) | .md | `{OUTPUT_DIR}/comprehensive_analysis_report.md` | ✅ 文件名已中立；0 下游 grep 命中，可独立改名 |
| 6 | analysis/comprehensive_analysis.py | L923 | `bottleneck_analysis_result.json` (json.dump) | .json | `{OUTPUT_DIR}/bottleneck_analysis_result.json` | ✅ 文件名已中立；0 下游 grep 命中（终端产物），但内部 `detected_bottlenecks` value 含 `'EBS'` 字面需 platform-aware（见 §10.1 #26）|
| 7 | tools/ebs_analyzer.sh | L16 | `${LOGS_DIR}/ebs_analyzer.log` (init_logger 第 3 参) | .log | `/tmp/blockchain-node-benchmark/logs/ebs_analyzer.log` | 推荐**直接中立化**为 `disk_analyzer.log`（logger ID 同步改 `disk_analyzer`），或 case 分发：AWS → `ebs_analyzer.log` / GCP → `disk_analyzer.log`。下游 0 程序化消费方（仅人读 + tail/grep），可加软链兼容旧脚本 |
| 7 | visualization/chart_style_config.py | — | **无输出文件命名** | N/A | （本文件不调 savefig / to_csv / open(...,'w')；grep 实证 0 处）| ✅ 无需改 — R8 worker 2026-05-18 确认 |
| 8 | analysis/cpu_ebs_correlation_analyzer.py | L539/L96/L609 | **无文件落盘** — 仅 str 返回值 + stdout 含 `CPU-EBS Performance Correlation Complete Analysis Report` (heredoc) / `CPU-EBS Complete Correlation Analysis (18 methods)` (print) / `CPU-EBS Correlation Analyzer usage example` (print) | str/stdout | （本文件零 `to_csv`/`savefig`/`open`/`json.dump`；grep 实证 0 处） | ✅ 无文件名改造；但 3 处文本标题/print 字面需替换 `CPU-EBS` → `CPU-Disk`（R7 worker 2026-05-18） |
| 9 | analysis/qps_analyzer.py | L421 | `'performance_cliff_analysis.png'` (savefig) | .png | `{REPORTS_DIR}/performance_cliff_analysis.png` | ✅ 文件名已中立（无 AWS/EBS 字面）；下游 README.md/architecture-overview.md 仅文档引用，无程序化消费（R7 worker qps_analyzer.py 2026-05-18）|
| 10 | analysis/qps_analyzer.py | L769 | `'qps_performance_analysis.png'` (savefig) | .png | `{REPORTS_DIR}/qps_performance_analysis.png` | ✅ 已中立；下游 README.md L424 + architecture-overview.md L549 + docs/image/qps_performance_report.md L42 + 本文件 L1106/L1152 引用 |
| 11 | analysis/qps_analyzer.py | L1116 | `'qps_performance_report.md'` (open w + write) | .md | `{REPORTS_DIR}/qps_performance_report.md` | ✅ 已中立；本文件 L1153 print 引用，0 程序化下游 |
| 12 | analysis/qps_analyzer.py | L1193 | `'performance_cliff_analysis.json'` (json.dump) | .json | `{REPORTS_DIR}/performance_cliff_analysis.json` | ✅ 已中立；plan v2 L53/L275 引用作格式校验基准，0 程序化解析方 |
| 12b | analysis/rpc_deep_analyzer.py | — | **无文件落盘** | N/A | （本文件零 `to_csv`/`savefig`/`open`/`json.dump`；grep 实证 0 处；所有 emit 经返回值 dict + str 回流到 comprehensive_analysis.py 主报告）| ✅ 无文件名改造 — R7 worker 2026-05-18 |
| 13 | analysis/qps_analyzer.py | (logger via utils/unified_logger.sh:L370) | `qps_analyzer.log` (init_logger 注册) | .log | `${LOGS_DIR}/qps_analyzer.log` | ✅ 已中立 |
| 14 | monitoring/unified_event_manager.sh | L18 (readonly EVENT_LOG) | `${MEMORY_SHARE_DIR}/unified_events.json` | .json | `/tmp/blockchain-node-benchmark/memory_share/unified_events.json` | **无需改** — 文件名已中立 ✅ (R4 worker unified_event_manager 2026-05-18 确认；唯一外部读者 framework_data_quality_checker.sh:L543 仅 schema 校验) |
| 15 | monitoring/unified_event_manager.sh | L21 (readonly EVENT_LOCK) | `${MEMORY_SHARE_DIR}/event_manager.lock` | .lock | `/tmp/.../event_manager.lock` | **无需改** — 文件名已中立 ✅ (flock 文件，无下游) |
| 16 | monitoring/unified_event_manager.sh | L145/L167 | `${MEMORY_SHARE_DIR}/event_notification.json` | .json | `/tmp/.../event_notification.json` | **无需改** — 文件名已中立 ✅ (但内容为死契约：0 程序化读者，benchmark_archiver.sh:L268 仅 rm) |
| 17 | monitoring/unified_event_manager.sh | L262 (stdout help echo) | `"  ebs_bottleneck           EBS performance bottleneck"` | stdout | `$ ./unified_event_manager.sh help` 显示给用户 | platform-aware：改字面 `"  disk_bottleneck          Block-device performance bottleneck"` 或 case 分发 `$CLOUD_PROVIDER`（建议直改+别名，因 0 程序化生产者）|
| 18 | tools/fetch_active_accounts.py | L817-819 (`with open(args.output, "w") as f: f.write(f"{addr}\n")`) | `active_accounts.txt`（运行时 = `${TMP_DIR}/active_accounts.txt`，主入口 blockchain_node_benchmark.sh:L121 `--output "$ACCOUNTS_OUTPUT_FILE"`）| .txt 纯地址列表 | `/tmp/blockchain-node-benchmark/active_accounts.txt` | **无需改** — 文件名已中立 ✅；下游唯一程序化消费 = `tools/target_generator.sh:L270 done < "$ACCOUNTS_OUTPUT_FILE"` 按行读，不依赖字段名（R6 worker fetch_active_accounts.py 2026-05-18）|
| 18b | tools/framework_data_quality_checker.sh | — | **无文件落盘** — `grep -nE "^\s*[^#]*>.*\.(csv\|json\|log\|html\|md)" tools/framework_data_quality_checker.sh` = 0 命中；主流程是 L596-L658 stdout 报告（echo 序列 → 用户终端 / CI logs），exit code 0/1 反馈校验结果 | str/stdout | （本文件零 `>` 重定向到任何 `.csv/.json/.log/.html/.md`） | ✅ **无文件名改造**；但 stdout 报告 banner L598 `"🔍 Framework Data Validation Report"` 已中立 ✅，唯一含 AWS 字面行 = L603 `echo "ENA monitoring: $ENA_MONITOR_ENABLED"` 需改 `"NIC allowance monitoring:"` 或 case 分发 `$CLOUD_PROVIDER`（R6 worker framework_data_quality_checker.sh 2026-05-18）|
| 18c | tools/target_generator.sh | L263/L288/L306/L322/L325/L327 (写 `$CURRENT_OUTPUT_FILE`) | `$CURRENT_OUTPUT_FILE` (变量，运行时 = `$SINGLE_METHOD_TARGETS_FILE` 或 `$MIXED_METHOD_TARGETS_FILE`，定义于 config_loader.sh:L243-244 = `${TMP_DIR}/targets_single.json` / `${TMP_DIR}/targets_mixed.json`) | .json (Vegeta target lines, base64-body) | `/tmp/blockchain-node-benchmark/targets_single.json` 或 `targets_mixed.json` | **无需改** — 文件名 platform-agnostic ✅（无 AWS/EBS/GCP 字面）；下游唯一消费者 `core/master_qps_executor.sh` L107/113/251/253/825/827 仅按路径变量读，不解析 JSON 字段名；JSON 内字段 method/url/header/body 是 Vegeta protocol schema 不可改。R6 worker target_generator.sh 2026-05-18 |
| 18d | monitoring/block_height_monitor.sh | L389 (CSV 创建) + L173-174 (CSV 写) + L198 (flag 写) + L443-451 (json 写) + L408 (pid 写) | **5 类输出全 platform-agnostic** ✅：`${BLOCK_HEIGHT_DATA_FILE}` = `block_height_monitor_${SESSION_TIMESTAMP}.csv` (config_loader.sh:L241 定义) + `${MEMORY_SHARE_DIR}/data_loss_stats.json` + `${MEMORY_SHARE_DIR}/block_height_time_exceeded.flag` + `${TMP_DIR}/block_height_monitor.pid` + stdout banner "Block Height Monitor"/"Multi-Chain Block Height Monitor" | .csv/.json/.flag/.pid/stdout | `/tmp/.../logs/block_height_monitor_*.csv` 等 | **无需改** — 所有文件名 100% 业务中性，0 AWS/EBS/ENA/nitro 字面；下游消费方（bottleneck_detector / framework_data_quality_checker / benchmark_archiver / report_generator / rpc_deep_analyzer / unified_monitor）按路径变量+字段名读取，0 platform-aware 改造需求。retro worker block_height_monitor.sh 2026-05-18 06:31 UTC |
| 18e | utils/ebs_converter.sh | L83 (`echo "  Reference: https://docs.aws.amazon.com/ec2/latest/instancetypes/so.html"`) + L78 (`echo "Instance Store Performance (No AWS conversion needed):"`) + L149 (`echo "AWS EBS IOPS/Throughput Standard Conversion Script"` help 标题) + L151-154 (help 示例含 `convert_to_aws_standard_*` / `calculate_io2_throughput`) + L25/L31 (注释含 `https://docs.aws.amazon.com/ebs/latest/userguide/ebs-io-characteristics.html` ×2) | **不输出文件** — `grep -nE "echo.*\.(png\|csv\|json\|html\|log)"` 仅命中 L83 URL 引用（非文件输出，是 stdout 文本含 URL 字面）；本文件纯 bash 函数库，所有输出经返回值/stdout 给调用方 | stdout/inline | `analyze_instance_store_performance` 函数体 stdout + help 模式 stdout（仅 `bash ebs_converter.sh` 直接执行时显示） | **无文件名改造** — 本文件不写 .png/.csv/.json/.html/.log；stdout 文本层 5 处 AWS 字面（L78 / L83 / L149 / L152 / L153）需中立化：(1) L83 改为 `${DISK_DOC_URL:-...}` 引用 + system_config 按 CLOUD_PROVIDER case 分发；(2) L78 改 `"Local Disk Performance (No cloud-standard conversion needed):"`（或随 EBSC-7 DEAD 删除归零）；(3) L149 改 `"Cloud Disk IOPS/Throughput Standard Conversion Script"`；(4) L152-153 改使用中立函数名 alias（`convert_to_cloud_standard_*`）。L25/L31 注释 URL 同 L83 处理。**整体不影响下游程序契约**（0 下游 grep 这些 stdout 串）— retro worker ebs_converter.sh 2026-05-18 07:05 UTC |

| 14 | tools/ebs_bottleneck_detector.sh | L14 (init_logger 第 3 参) / L664 (echo "📝 Logging to:") / L668 (`exec > ... 2>&1`) | `${LOGS_DIR}/ebs_bottleneck_detector.log` | .log | `/tmp/blockchain-node-benchmark/logs/ebs_bottleneck_detector.log` | 推荐**直接中立化**为 `disk_bottleneck_detector.log`（logger ID 同步改 `disk_bottleneck_detector`）；下游 2 程序化消费者必须同步改：framework_data_quality_checker.sh:L438 + report_generator.py:L1188。或 case 分发：AWS → `ebs_*` / GCP → `disk_*`，加软链兼容旧 tail/grep 用户。R6 worker 2026-05-18 |
| 15 | tools/ebs_bottleneck_detector.sh | L550 (`} > "$summary_file"`，summary_file = `${data_file%.*}_summary.txt`) + L507 ("EBS High-Frequency Monitoring Summary" 标题) + L514 ("=== EBS Configuration ===" 段标题) | `${data_file%.*}_summary.txt` heredoc | .txt | 文件名云无关 ✅；但标题文本含 "EBS" 字面 | **整个 generate_monitoring_summary 函数 (L499-L574) 是死代码**（grep 全仓 0 外部调用）→ 推荐直接删除；若保留则标题改为 "Disk High-Frequency Monitoring Summary" / "=== Disk Configuration ===" |
| 16 | tools/ebs_bottleneck_detector.sh | L449 ("EBS BOTTLENECK DETECTED") / L623 ("EBS Bottleneck Detector") / L613 / L616 等 stdout echo | stdout 控制台文案 | stdout | 实时警报文案，非文件名 | 改为 "DISK BOTTLENECK DETECTED" / "Disk Bottleneck Detector"；不影响下游程序消费（无 grep 匹配），仅影响用户视觉 |
| 17 | tools/ebs_bottleneck_detector.sh 本身文件名 | 文件路径 | `ebs_bottleneck_detector.sh` | .sh | `tools/ebs_bottleneck_detector.sh` | 推荐重命名 `disk_bottleneck_detector.sh` + 软链兼容；同步改：monitoring_coordinator.sh:L36 (注册表 key+脚本名) / monitoring_coordinator.sh:L218 (启动清单) / master_qps_executor.sh:L574 (pgrep pattern) / master_qps_executor.sh:L578-L580 (路径 + spawn) / framework_data_quality_checker.sh:L438 + report_generator.py:L1188 (日志路径) + blockchain_node_benchmark.sh:L464 (注释) + internal_config.sh:L25 (注释)。R6 worker 2026-05-18 |
| 19a | visualization/ebs_chart_generator.py | L29 + L398 (savefig) | `ebs_aws_capacity_planning.png` (CHART_FILES['capacity']) | .png | `{REPORTS_DIR}/ebs_aws_capacity_planning.png` | **双字面 `ebs_aws_`**；改 `f'{cloud_disk_prefix()}_capacity_planning.png'`，prefix `aws=ebs_aws / gcp=disk_gcp / 中立=disk`；下游 visualization/report_generator.py 可能引用（待 R8 file-notes 实证），生成 HTML `<img src>` |
| 19b | visualization/ebs_chart_generator.py | L30 + L561 | `ebs_iostat_performance.png` | .png | 同上 dir | `f'{cloud_disk_prefix()}_iostat_performance.png'` |
| 19c | visualization/ebs_chart_generator.py | L31 + L695 | `ebs_bottleneck_correlation.png` | .png | 同上 | `f'{cloud_disk_prefix()}_bottleneck_correlation.png'` |
| 19d | visualization/ebs_chart_generator.py | L32 + L815 | `ebs_performance_overview.png` | .png | 同上 | `f'{cloud_disk_prefix()}_performance_overview.png'` |
| 19e | visualization/ebs_chart_generator.py | L33 + L961 | `ebs_bottleneck_analysis.png` | .png | 同上 | `f'{cloud_disk_prefix()}_bottleneck_analysis.png'` |
| 19f | visualization/ebs_chart_generator.py | L34 + L1120 | `ebs_aws_standard_comparison.png` | .png | 同上 | **双字面 `ebs_aws_`**；`f'{cloud_disk_prefix()}_standard_comparison.png'` |
| 19g | visualization/ebs_chart_generator.py | L35 + L1286 | `ebs_time_series_analysis.png` | .png | 同上 | `f'{cloud_disk_prefix()}_time_series_analysis.png'` |
| 19h | visualization/ebs_chart_generator.py | L218/L573/L606/L715/L735/L756/L844/L976/L1006/L1037/L1137 等 | fig.suptitle / set_title / set_xlabel / set_ylabel **35 处显示串**含 `AWS Standard IOPS` / `AWS Standard Throughput` / `EBS Performance Overview` / `EBS Bottleneck Analysis` 等 | matplotlib title/label | 用户视觉层 chart title 字面 | 用 `cloud_disk_prefix()` 或新建 `output_disk_label()` 函数化：`f'{output_disk_label()} Standard IOPS'`；**无下游程序契约**（仅人眼看图），可立即批量替换（R8 worker 2026-05-18 实证 35 处）|
| 18 | monitoring/unified_monitor.sh | L1944-1985 (写 `${MEMORY_SHARE_DIR}/latest_metrics.json`) | `latest_metrics.json` | .json | `/tmp/.../memory_share/latest_metrics.json` | **文件名无需改** ✅（已中立）；但 JSON 内含 `ebs_util` / `ebs_latency` key 必须 platform-aware 双写（见 §10.1 #44/#45）。R4 worker 2026-05-18 |
| 19 | monitoring/unified_monitor.sh | L1986-1998 (写 `${MEMORY_SHARE_DIR}/unified_metrics.json`) | `unified_metrics.json` | .json | `/tmp/.../memory_share/unified_metrics.json` | **文件名无需改** ✅；JSON 内含 `ena_data` 子对象 必须改名为 `network_allowance_data`（见 §10.1 #46）|
| 20 | monitoring/unified_monitor.sh | L2058-2090 (write `${PERFORMANCE_LOG}` via safe_write_csv) → 软链至 `performance_latest.csv` | `performance_*.csv` / `performance_latest.csv` | .csv | `${LOGS_DIR}/performance_${SESSION_TIMESTAMP}.csv` | **文件名无需改** ✅（中立）；CSV 内含 `ena_*_allowance_*` 列（动态注入，见 §10.1 #47）+ `data_*_aws_standard_iops` 列（见 §10.1 #5/#34）|
| 21 | monitoring/unified_monitor.sh | L2206-2210 (stdout echo) | inline log text `"ENA monitoring: Enabled - AWS environment"` | stdout | 启动日志 | platform-aware 改 `"Cloud: $CLOUD_PROVIDER (ENA monitoring: ...)"`（见 §10.1 #48）|
| 22 | monitoring/unified_monitor.sh | L2620 (`report_file=${LOGS_DIR}/error_recovery_report_${SESSION_TIMESTAMP}.txt`) | `error_recovery_report_*.txt` | .txt | `${LOGS_DIR}/error_recovery_report_20260518_120000.txt` | **文件名已中立** ✅（无 AWS 字面）|
| 23 | core/common_functions.sh | L22 (buffered_write) | `${file}.buffer` | .buffer | `block_height_data.csv.buffer` (调用方注入 `$file`) | **文件名已中立** ✅；本文件零 AWS 字面，buffered_write 通用计数器，无 platform-aware 改造需求（retro 2026-05-18） |
| 24 | core/common_functions.sh | L184 / L287 (get_block_height + check_node_health) | `${MEMORY_SHARE_DIR:-/tmp}/node_health_${url_hash}.cache` | .cache | `/tmp/.../node_health_a1b2c3d4....cache` (md5 of RPC URL) | **文件名已中立** ✅；内容仅 `"0"` / `"1"` 字符串字面，无 AWS 字面（retro 2026-05-18） |
| 25 | core/common_functions.sh | L176 (cleanup_block_height_cache glob) | `block_height_*.json` (find -name pattern) | .json glob | `${cache_dir}/block_height_<hash>.json` (调用方注入路径) | **文件名已中立** ✅；本文件不直接 *写* `block_height_*.json`（写的是调用方提供的 `$cache_file` 路径，L163），仅 cleanup 用此 glob 清理 5 min 以上旧文件；GCP 迁移 0 工作量（retro 2026-05-18） |
| 26 | visualization/performance_visualizer.py | L421/L529 (`create_correlation_visualization_chart`) | `cpu_ebs_correlation_visualization.png` | .png | `${REPORTS_DIR}/cpu_ebs_correlation_visualization.png` | **唯一含 ebs 字面的 PNG 输出** ⚠；platform-aware 改造：双输出 `cpu_disk_correlation_visualization.png` 或 `cpu_{ebs|pd|hyperdisk}_correlation_visualization.png`；其他 12 个 PNG (`performance_overview.png` / `util_threshold_analysis.png` / `await_threshold_analysis.png` / `device_performance_comparison.png` / `monitoring_overhead_analysis.png` / `smoothed_trend_analysis.png` / `qps_trend_analysis.png` / `resource_efficiency_analysis.png` / `performance_cliff_analysis.png` / `bottleneck_identification.png` / `block_height_sync_chart.png`) 文件名已中立 ✅；chart 标题含 EBS 字面 6 处（L328/L336/L348/L354/L1517/L1525）+ chart suptitle 1 处（L387）已纳入 §10.2 PV-N3/PV-N4；R8 worker 2026-05-18 |
| 27 | visualization/report_generator.py | L2040 (`f.write(html_content)`) | `performance_report_{en|zh}_${SESSION_TIMESTAMP}.html` | .html | `${REPORTS_DIR}/performance_report_en_20260518_120000.html` | ✅ **文件名已中立**(无 AWS 字面);双语 en/zh 物理隔离两个 HTML 文件;0 程序化下游(仅用户浏览器);唯一最终产物 — R8 worker report_generator.py 2026-05-18 |
| 28 | visualization/report_generator.py | L2516 (`plt.savefig`) | `resource_distribution_chart.png` | .png | `${REPORTS_DIR}/resource_distribution_chart.png` | ✅ **文件名已中立**;0 外部 reader(仅本文件 L2286 `<img src>` 自引用)— R8 worker 2026-05-18 |
| 29 | visualization/report_generator.py | L2705 (`plt.savefig`) | `monitoring_impact_chart.png` | .png | `${REPORTS_DIR}/monitoring_impact_chart.png` | ✅ **文件名已中立**;0 外部 reader(仅本文件 L2301 `<img src>` 自引用)— R8 worker 2026-05-18 |
| 30 | visualization/report_generator.py | L3914-L4070 (chart `'filename'` dict 28 处 reference,非写) | 28 个 `<img src>` 引用清单(7 处 `ebs_*` + 1 处 `ebs_aws_*` + 3 处 `ena_*` + 17 处中立) | .png references | HTML 内嵌 `<img src='ebs_*.png'>` 等 | ⚠ **chart filename references 不写但消费**:`ebs_aws_capacity_planning.png` / `ebs_aws_standard_comparison.png` / `ebs_iostat_performance.png` / `ebs_bottleneck_correlation.png` / `ebs_performance_overview.png` / `ebs_bottleneck_analysis.png` / `ebs_time_series_analysis.png` / `ena_limitation_trends.png` / `ena_connection_capacity.png` / `ena_comprehensive_status.png` — 与 ebs_chart_generator(§10.3 #19a-g)+ advanced_chart_generator 改名链强耦合;chart dict `filename` 值需改用 `f"{cloud_disk_prefix()}_*.png"` — R8 worker report_generator.py 2026-05-18 |
| 31 | visualization/report_generator.py | L3046 (HTML 文本 `<p>报告文件: ebs_bottleneck_analysis.txt</p>`) | `ebs_bottleneck_analysis.txt`(仅文本提示,本文件不写) | str/HTML inline | 显示给用户的报告文件名 | ⚠ 上游 `tools/ebs_bottleneck_detector.sh:L550` `${data_file%.*}_summary.txt`(死代码段)— 与 §10.3 #15 改名链耦合;改名时本行文本同步替换为 `disk_bottleneck_analysis.txt` — R8 worker 2026-05-18 |
| 32 | visualization/report_generator.py | L3051 (HTML 文本 `<p>报告文件: ebs_iops_conversion.json</p>`) | `ebs_iops_conversion.json`(仅文本提示,本文件不写) | str/HTML inline | 显示给用户的报告文件名 | ⚠ 上游写方待 R8 ebs_chart_generator / 其他确认;改名时本行文本同步 `disk_iops_conversion.json` — R8 worker 2026-05-18 |
| 33 | visualization/report_generator.py | L33-L1175 (TRANSLATIONS 翻译值 ~80 处含 `AWS`/`EBS`/`ENA` 字面) | 章节标题 + 表格标题 + 段落正文(`'EBS Performance Analysis Results'` / `'AWS EBS Baseline Performance Statistics'` / `'AWS Standard IOPS'` / `'EBS bottleneck analysis is based on AWS recommended performance metrics'` 等) | HTML title/header/<h2>/<p>/<td> | HTML 用户视觉层 | ⚠ **用户视觉层 80+ 处 AWS 字面**;改造方案:批量 sed 改 value(保留 key 名);或新增 `_output_disk_label()` / `_output_nic_label()` 实例方法注入 platform-aware 文本(`f"{self._disk_label} Performance Analysis Results"`)— R8 worker report_generator.py 2026-05-18 |
| 27 | blockchain_node_benchmark.sh (R-ROOT 主入口) | L735 (`generate_bottleneck_summary_report`) | `bottleneck_summary_${SESSION_TIMESTAMP}.md` | .md | `${REPORTS_DIR}/bottleneck_summary_20260518_120000.md` | **文件名已中立** ✅；内容标题 "# 🚨 Performance Bottleneck Detection Report" + jq 读字段全部已中立；下游 0 程序化消费方（grep `bottleneck_summary_` 全仓 = 仅本文件 self-reference + L837 find display）。无 platform-aware 改造点（R-ROOT retro 2026-05-18） |
| 28 | blockchain_node_benchmark.sh (R-ROOT) | L177-L178 | `$TMP_DIR/qps_test_status` (控制文件，写 "running" 字符串) | 无后缀 | `/tmp/.../qps_test_status` | **文件名已中立** ✅；跨 6 文件下游生命周期 marker（tools/ebs_bottleneck_detector + master_qps_executor + ena_network_monitor + unified_monitor + monitoring_coordinator + block_height_monitor）。无 platform-aware 改造（R-ROOT retro 2026-05-18） |
| 29 | blockchain_node_benchmark.sh (R-ROOT) | L182-L183 | `${TMP_DIR}/monitor_pids.txt` + `${TMP_DIR}/monitoring_status.json` (export 给子进程) | .txt + .json | `/tmp/.../monitor_pids.txt` / `/tmp/.../monitoring_status.json` | **文件名已中立** ✅；与 TRACKER §10.3 #4/#5 (monitoring_coordinator.sh 的同名 readonly 变量) 一致，本文件只 export 路径不创建文件。无 platform-aware 改造（R-ROOT retro 2026-05-18） |

| 30 | monitoring/bottleneck_detector.sh | L33 (BOTTLENECK_LOG) | `${LOGS_DIR}/bottleneck_detector.log` | .log | `${LOGS_DIR}/bottleneck_detector.log` | **文件名已中立** ✅ — 无需改 (R-RETRO bottleneck_detector.sh 2026-05-18) |
| 31 | monitoring/bottleneck_detector.sh | L76 (readonly BOTTLENECK_STATUS_FILE) | `${MEMORY_SHARE_DIR}/bottleneck_status.json` | .json | `${MEMORY_SHARE_DIR}/bottleneck_status.json` | **文件名已中立** ✅；但内部 JSON key 改名链见 §10.1 #20/#21/#22/#57/#58/#60 (跨 4 文件 reader)；本文件名 0 改造 (R-RETRO 2026-05-18) |
| 32 | monitoring/bottleneck_detector.sh | L77 (readonly BOTTLENECK_COUNTERS_FILE) | `${MEMORY_SHARE_DIR}/bottleneck_counters.json` | .json | `${MEMORY_SHARE_DIR}/bottleneck_counters.json` | **文件名已中立** ✅；内部 JSON key 改名见 §10.1 #59；本文件自闭环 IPC 0 外部 reader (R-RETRO 2026-05-18) |
| 33 | monitoring/bottleneck_detector.sh | L491 (`ena_baseline_file=`) | `${MEMORY_SHARE_DIR}/ena_baseline.json` | .json | `${MEMORY_SHARE_DIR}/ena_baseline.json` | ❌ **含 `ena_` 字面** — platform-aware 改造：改 `nic_baseline.json` + 加路径 fallback `[[ -f new \|\| -f old ]]`；本文件自闭环 0 外部 reader，可独立改 (R-RETRO bottleneck_detector.sh 2026-05-18 §10.1 #61) |
| 34 | utils/unified_logger.sh | L94 (DEAD) / L296 (DEAD) / L304 (DEAD) / L370 (here-doc 文档) / L385 (self-test) / L392 (self-test) | `${LOGS_DIR}/${component}_${log_type}_${timestamp}.log` / `${LOGS_DIR}/${component}_*.log` / `/tmp/test_logger.log` | .log | `/tmp/blockchain-node-benchmark/logs/<component>.log` | **文件名 100% 中立** ✅ — 输出仅 `.log` 后缀且 component 由 caller 动态注入（如 `unified_monitor.log` / `bottleneck_detector.log`），0 含 aws/ebs 字面；3 处 .log 模板属 DEAD code（get_log_file_path / query_logs 0 外部调用），可一并清理；2 处 `/tmp/test_logger.log` 是 self-test 路径不影响生产；本文件 0 platform-aware 改造点 (retro 2026-05-18 07:14 UTC) |

**输出类型分类**：
- chart.png（图表）
- report.html / report.md（报告）
- *.log（日志）
- *.csv / *.json（数据产物）

### 10.4 双写过渡期计划

| # | 字段对（旧 → 新）| 双写起始 Round | 计划切换 Round | 旧名删除 Round | 触发条件 |
|---|---------------------|-----------------|------------------|------------------|----------|
| 1 | aws_standard_gbps → network_standard_gbps | R(本) | 下游全切完 | +1 Round | 全读方 grep 0 |
| 2 | `data_aws_standard_iops` → `data_disk_standard_iops` (patterns dict key) | R8 (device_manager) | 当 visualization/ + analysis/ + tools/ 全部 reader 切换完 | +1 Round | grep `data_aws_standard_iops` 全仓 = 0 (device_manager.py:L26/L347/L420/L493 + 其他 visualization/analysis 文件全切) |
| 3 | `data_aws_standard_throughput_mibs` → `data_disk_standard_throughput_mibs` (patterns key) | R8 (device_manager) | 同 #2 | +1 Round | grep `data_aws_standard_throughput_mibs` 全仓 = 0 |
| 4 | `accounts_aws_standard_iops` / `accounts_aws_standard_throughput_mibs` (patterns key) | R8 (device_manager) | 同 #2 | +1 Round | grep `accounts_aws_standard_iops\|accounts_aws_standard_throughput_mibs` 全仓 = 0 |
| 5 | `BOTTLENECK_EBS_UTIL_THRESHOLD` → `BOTTLENECK_DISK_UTIL_THRESHOLD` (env var) | R8 (device_manager 追加 reader) | 当 config_loader.sh export 双名（alias）且所有 9 个 reader 切换完 | +1 Round | grep `BOTTLENECK_EBS_UTIL_THRESHOLD` 全仓 = 0；中间过渡期 `os.getenv('BOTTLENECK_DISK_UTIL_THRESHOLD') or os.getenv('BOTTLENECK_EBS_UTIL_THRESHOLD', default)` 模式生效 |
| 6 | `BOTTLENECK_EBS_LATENCY_THRESHOLD` → `BOTTLENECK_DISK_LATENCY_THRESHOLD` | R8 | 同 #5 | +1 Round | 同 #5 模式 |
| 7 | `BOTTLENECK_EBS_IOPS_THRESHOLD` → `BOTTLENECK_DISK_IOPS_THRESHOLD` | R8 | 同 #5 | +1 Round | 同 #5 模式 |
| 8 | `BOTTLENECK_EBS_THROUGHPUT_THRESHOLD` → `BOTTLENECK_DISK_THROUGHPUT_THRESHOLD` | R8 | 同 #5 | +1 Round | 同 #5 模式 |
| 9 | `'AWS Standard IOPS'` / `'AWS Standard Throughput'` (chart label 显示串) | R8 (device_manager:L420-421) | 立即（label 是终端展示，无下游契约）| 同 Round | label 改为 `f'{cloud_disk_prefix()} Standard IOPS'`，prefix 由 `utils/field_normalizer.py.output_prefix()` 提供 |
| 10 | `_check_device_data_exists` / `create_chart_title` (重复方法)（10.13 死代码 + 9.10 重复函数）| R8 立即删 | 同 Round | 同 Round | grep 调用方 = 0 已实证 |
| _待累加_ | | | | | |

### 10.5 读时归一化层设计草案

**建议位置**：`utils/field_normalizer.py`（新建）

```python
"""
平台无关字段读取层（R20.7 用户激进路线 A）。
所有读 CSV/JSON 的代码必须经过本层。
"""
import os
CLOUD_PROVIDER = os.environ.get('CLOUD_PROVIDER', 'aws')

# 中立字段名 → 各平台真实字段名映射
FIELD_MAP = {
    'aws': {
        'network_bw_in': 'ena_bw_in',
        'network_standard_gbps': 'aws_standard_gbps',
        'disk_standard_iops': 'aws_standard_iops',
        # ... 待累加
    },
    'gcp': {
        'network_bw_in': 'gvnic_bw_in',
        'network_standard_gbps': 'gvnic_standard_gbps',
        'disk_standard_iops': 'pd_standard_iops',
        # ... 待累加
    },
}

def read_field(df, neutral_name: str):
    """统一字段读取入口。"""
    platform_name = FIELD_MAP[CLOUD_PROVIDER].get(neutral_name, neutral_name)
    if platform_name in df.columns:
        return df[platform_name]
    # 双写过渡期 fallback：尝试中立名
    if neutral_name in df.columns:
        return df[neutral_name]
    raise KeyError(f"Field {neutral_name} (platform: {platform_name}) not in df")

def output_prefix() -> str:
    """输出文件名前缀（platform-aware）。"""
    return {'aws': 'ebs_aws', 'gcp': 'disk_gcp'}.get(CLOUD_PROVIDER, 'disk')
```

_（待 Phase 6 各 file-notes 累加完字段后，本草案具体填充）_

---

## §14 抽象层架构契约说明 (Phase E-1+ 落地)

> 本章定义 GCP 迁移的最终架构契约：所有 platform-aware 逻辑收敛到单一抽象层 `config/cloud_provider.sh` + `utils/cloud_provider.py`，业务方仅通过 15 个 getter 接口消费云特性。本章是 §13.2/13.3/13.4/13.5/13.6/13.12/13.18/13.19/13.21 共 9 个阻塞点被 absorbed 的根因解释，也是 CP-6+ 后续改造的合同基线。

### §14.1 抽象层入口

- **唯一入口**：`config/cloud_provider.sh`（注意：放在 `config/` 而非 `utils/`，与 `user_config.sh` / `system_config.sh` 同目录，强调"配置即合同"语义）
- **业务方接入**：所有业务文件只需 `source "${BENCHMARK_ROOT}/config/cloud_provider.sh"` 一行，即可获得全部 15 个 getter 函数
- **内部装载链**：cloud_provider.sh 先做 `${CLOUD_PROVIDER:?CLOUD_PROVIDER must be detected before sourcing}` fail-fast（详见 §14.5），然后 `source providers/${CLOUD_PROVIDER}_provider.sh`，三个 provider 文件各自实现 15 getter 的 provider-specific 返回值
- **替代静态变量**：原 system_config.sh 内 `METADATA_ENDPOINT` / `CLOUD_IO_BASELINE_KIB` / `ENA_ALLOWANCE_FIELDS_STR` 等静态 export 全部废弃，业务方改调懒求值 getter（如 `local endpoint=$(get_metadata_endpoint)`），source 顺序冲突（§13.2）从根本消除

### §14.2 15 getter 接口表

| # | Getter 名 | 返回类型 | AWS 示例 | GCP 示例 | Other 示例 | 用途 / 消费方 |
|---|----------|---------|---------|---------|-----------|--------------|
| 1 | get_metadata_endpoint | URL | 169.254.169.254 | metadata.google.internal | (empty) | config_loader.sh metadata curl |
| 2 | get_metadata_header | HTTP header | (empty) | Metadata-Flavor: Google | (empty) | 所有 metadata curl 调用点 (§13.5 absorbed) |
| 3 | get_metadata_api_path | path 片段 | latest/meta-data | computeMetadata/v1 | (empty) | config_loader.sh metadata 路径拼接 |
| 4 | get_baseline_throughput_kib | int | 16 | 4 | 0 | ebs_converter.sh IOPS/Throughput 公式系数 |
| 5 | get_baseline_io_kib | int | 16 | 4 | 0 | unified_monitor baseline 计算 |
| 6 | get_disk_field_prefix | str | aws_standard | pd_standard | standard | unified_monitor / iostat_collector CSV header 拼接 (§13.6/§13.12 absorbed) |
| 7 | get_disk_type_options | csv | gp3,io2,io1,st1 | pd-ssd,pd-balanced,pd-extreme,hyperdisk-extreme,local-ssd | (empty) | user_config.sh DATA_VOL_TYPE 合法值校验 |
| 8 | get_default_disk_type | str | gp3 | pd-ssd | (empty) | user_config.sh DATA_VOL_TYPE 缺省值 |
| 9 | get_nic_driver | str | ena | gvnic | virtio | config_loader.sh detect_network_interface (§13.4 absorbed) |
| 10 | get_nic_allowance_fields | space-list | bw_in_allowance_exceeded ... | (empty 或 gvnic 等价字段) | (empty) | config_loader.sh L829 单源 fallback (§13.3 absorbed) |
| 11 | get_nic_monitor_process_name | str | ena_network_monitor | gvnic_network_monitor | nic_network_monitor | system_config.sh MONITORING_PROCESS_NAMES |
| 12 | get_archive_dir_prefix | str | aws_run | gcp_run | run | benchmark_archiver / report_generator glob (§13.18/§13.19 absorbed) |
| 13 | get_bottleneck_label | str | EBS | Disk | Disk | ebs_bottleneck_detector console + comprehensive_analysis.py (§13.21 absorbed) |
| 14 | get_platform_display_name | str | AWS | GCP | Generic | 报告标题 / 图表 label |
| 15 | get_doc_url_base | URL | docs.aws.amazon.com/AWSEC2 | cloud.google.com/compute/docs | (empty) | 报错信息中的文档链接 |

> 与 `analysis-notes/CORRECTED_PLAN.md §0` 15 getter 表 1:1 同源；任何 getter 增减需双向同步。

### §14.3 三 provider 实现

| Provider 文件 | 行数 (LOC) | 职责 |
|--------------|-----------|------|
| config/cloud_provider/providers/aws_provider.sh | ~58 | 实现全 15 getter，返回 AWS-specific 值（169.254.169.254 / aws_standard / ena / EBS 等） |
| config/cloud_provider/providers/gcp_provider.sh | ~58 | 实现全 15 getter，返回 GCP-specific 值（metadata.google.internal / pd_standard / gvnic / Disk 等） |
| config/cloud_provider/providers/other_provider.sh | ~58 | 实现全 15 getter，**返回中立值**（disk_field_prefix='standard' 而非 'aws_standard'，default_disk_type='' 而非 'gp3'，baseline_io_kib=0 而非 16）— 详见 §14.7 |

每个 provider 文件结构对称：15 个 `get_xxx() { echo "..."; }` 函数定义；无任何 case 分支（分发已在 cloud_provider.sh 入口处由 source 完成）。

### §14.4 contract test (tests/test_provider_contract.sh)

- **基线断言**：对 3 个 provider 分别 source，验证 15 个 getter 全部定义存在（`declare -f get_xxx` 通过）
- **类型断言**：返回值类型正确（int 类 getter 验证 `[[ "$val" =~ ^[0-9]+$ ]]`，URL 类验证非空且不含空格）
- **AWS≠GCP 防抄断言**：对 7 个关键 getter 显式断言 AWS 与 GCP 返回值必须不同：
  1. get_metadata_endpoint (169.254.169.254 ≠ metadata.google.internal)
  2. get_metadata_header ('' ≠ 'Metadata-Flavor: Google')
  3. get_metadata_api_path (latest/meta-data ≠ computeMetadata/v1)
  4. get_baseline_io_kib (16 ≠ 4)
  5. get_disk_field_prefix (aws_standard ≠ pd_standard)
  6. get_nic_driver (ena ≠ gvnic)
  7. get_archive_dir_prefix (aws_run ≠ gcp_run)
- **执行时机**：CI 必跑 + 任何 provider 文件改动的 pre-commit hook
- **失败语义**：任一 getter 缺失或 AWS≡GCP 返回值雷同 → exit 1（防止开发期不小心把 AWS 实现复制到 GCP provider 后忘改）

### §14.5 fail-fast 设计（禁默认值）

- **入口断言**：cloud_provider.sh L1 即写 `: "${CLOUD_PROVIDER:?CLOUD_PROVIDER must be detected by config_loader.sh::detect_deployment_platform before sourcing cloud_provider.sh}"`
- **决策依据**：`CORRECTED_PLAN.md §0 决策 6` —— 禁止任何形式的默认值（如 `CLOUD_PROVIDER=${CLOUD_PROVIDER:-aws}`），原因是 §13.2 的根因就是"未检测 → 默认 aws 分支 → 静默错配置"。fail-fast 强制业务方在 source 前必先调用 `detect_deployment_platform`
- **provider 文件同样断言**：每个 provider 文件 L1 写 `[[ "${CLOUD_PROVIDER}" == "aws" ]] || return 0` 类哨兵（防止误 source）
- **业务方负担**：业务方在 entry-point 脚本里只需一次 `source config_loader.sh && detect_deployment_platform && source cloud_provider.sh`，后续所有子脚本 source cloud_provider.sh 时 `CLOUD_PROVIDER` 已就绪

### §14.6 Python facade (utils/cloud_provider.py)

- **目的**：Python 进程（report_generator.py / comprehensive_analysis.py / device_manager.py 等）无法 source bash 文件，需独立 facade
- **实现**：读 `os.environ['CLOUD_PROVIDER']`（由 entry-point bash 脚本透传） + dispatch dict
  ```python
  CLOUD_PROVIDER = os.environ['CLOUD_PROVIDER']  # KeyError fail-fast，无默认
  _PROVIDERS = {'aws': _AwsProvider(), 'gcp': _GcpProvider(), 'other': _OtherProvider()}
  def get_metadata_endpoint() -> str: return _PROVIDERS[CLOUD_PROVIDER].metadata_endpoint
  # ... 15 个 getter 1:1 对称 bash 版
  ```
- **对称性保障**：contract test 同时 source bash 与 import python，比较 15 getter 返回值逐一相等（AWS bash 版 vs AWS python 版 vs GCP bash 版 vs GCP python 版）
- **absorbed 阻塞点**：§13.18/§13.19（report_generator glob/run_* basename）→ `get_archive_dir_prefix()` Python facade；§13.21（comprehensive_analysis 'EBS' 4 处）→ `get_bottleneck_label()` Python facade

### §14.7 平台对等原则（无主从）

- **AWS/GCP/Other 三方完全对等**：抽象层不偏袒 AWS（虽然项目最初为 AWS 设计），不假设 GCP 是"次要支持"
- **Other provider 中立化**（关键设计）：避免把 AWS 当 fallback：
  - get_disk_field_prefix 返回 `'standard'`（**不是** `'aws_standard'`，防止 GCP 上误装 other provider 时字段名仍带 aws）
  - get_default_disk_type 返回 `''`（**不是** `'gp3'`，强制用户在 user_config.sh 显式声明，无 silent default）
  - get_baseline_io_kib 返回 `0`（**不是** `16`，下游业务必须显式处理 0 值避免 div-by-zero，silent AWS-tinted 错误算法消除）
  - get_metadata_endpoint 返回 `''`（**不是** `169.254.169.254`，curl 调用前必须显式 check empty）
- **代价与收益**：业务方在 Other 平台上必须显式判空（增加 ~5 处 if 分支），但换得"AWS 行为不会泄漏到未知平台"的安全保证

### §14.8 后续 CP-6+ 改造点预告

> §13.X 共 21 个阻塞点，Phase E-4 absorbed 9 个，剩余 12 个待 CP-6+ 落地。简要预告：

| §13.X | 等级 | 简要内容 | 预计 CP |
|------|------|---------|--------|
| §13.1 | P0 | block_height_monitor RPC writer 真位置定位 | CP-6.1 |
| §13.7 | P1 | unified_monitor.sh L2080 兜底 wc -w 一致性 | CP-6.2 |
| §13.8 | P1 | ena_network_monitor.sh CSV 双逗号修复 | CP-6.3 |
| §13.9 | P1 | bottleneck_detector.sh accounts_ebs 条件初始化 | CP-6.4 |
| §13.10 | P1 | monitoring_coordinator.sh LOGS_DIR 多实例冲突 | CP-6.5 |
| §13.11 | P1 | block_height_monitor MEMORY_SHARE_DIR 多实例 | CP-6.5 |
| §13.13 | P1 | ebs_bottleneck_detector.sh 7-tuple 位置参数契约 | CP-6.6 |
| §13.14 | P2 | benchmark_archiver.sh 时区跨平台 | CP-6.7 |
| §13.15 | P2 | framework_data_quality_checker.sh 21 字段 DRY | CP-6.8 |
| §13.16 | P3 | target_generator.sh 迁移豁免（无需改） | — (登记) |
| §13.17 | P3 | fetch_active_accounts.py 迁移豁免（无需改） | — (登记) |
| §13.20 | P2 | report_generator.py 关键字常量集中化 | CP-6.9 |

未 absorbed 的阻塞点共性：(1) 非平台 getter 能解决（如 7-tuple 位置参数 §13.13、CSV 双逗号 §13.8 是数据格式问题）；(2) 多实例并行 / 时区 / DRY 重构（§13.10/§13.11/§13.14/§13.15）属于工程质量提升；(3) 真位置定位待 R 期（§13.1）。这些将在 Phase F (CP-6+) 通过专用 patch 解决，不属于抽象层职责。

### §14.9 Y+ 升级影响公告 (与 CP-2.5 配套)

**变更点**: 原 §14 抽象层契约中 NIC 相关字段 (`ena_*_allowance_exceeded` 等) 从「getter 拼接 + 字段名 hardcode」升级为「接口抽象层 + 字段语义注册表」。

**§14 子节影响清单**:

| §14 子节 | 原契约 (E1+) | Y+ 升级后契约 |
|---|---|---|
| §14.1 (15 getter 表) | 含 `get_ena_bw_in_field` 等 6 个 NIC getter | NIC 6 个 getter 全删除, NIC 字段由 `monitoring/network/<provider>.sh::generate_network_csv_header()` 内部定义, 不再走 getter |
| §14.2-§14.5 (disk getter) | 保持 | 保持 (disk 不升级) |
| §14.6 (CPU getter) | 保持 | 保持 |
| §14.7 (Mem getter) | 保持 | 保持 |
| §14.8 (7 关键 getter AWS≠GCP 防抄断言) | 含 ena 字段断言 | ena 断言移除, 改用 NIC 接口契约测试 (见 §15) |

**新增依赖**:
- TRACKER 引用 `monitoring/network/interface.sh` 4 个接口签名 (init/header/collect/metadata)
- TRACKER 引用 `utils/network_field_registry.py::NetworkFieldRegistry.get_semantic_type()` 作为下游 reader 唯一查询入口

**字段统计变化**:
- 总 getter 数: 15 → 9 (删除 6 个 NIC getter)
- NIC 字段管控方式: 从「字段名 hardcode」改为「semantic_type 查询」
- AWS NIC 字段: 6 个 ena_*_exceeded → 由 aws.sh 内部 AWS_ENA_FIELDS 数组管理
- GCP NIC 字段: 0 个 (E1+ 错放在 getter 表) → 3 个 gvnic_* (由 gcp.sh 管理)
- Other NIC 字段: 0 个 → 0 个 (Other 不监控平台特定 NIC counter)

---

## §15 NIC 接口契约 (Y+ 架构核心契约, 与 CP-2.5 + CP-0.5.2 联动)

### §15.1 接口签名契约 (5 个核心函数)

每个 provider 实现文件 (monitoring/network/aws_ena.sh, gcp_gvnic.sh, gcp_virtio.sh, other_none.sh) 必须实现以下 4 个函数, `detect_nic_driver` 在 config/cloud_provider.sh 层 (variant 派发). 任何 provider 缺失任一函数即视为契约违反:

| 函数名 | 输入 | 输出契约 | 失败行为 |
|---|---|---|---|
| `init_network_monitoring` | env: NETWORK_INTERFACE | return 0 (就绪) 或 1 (不可用) | 返 2+ 视为 bug |
| `generate_network_csv_header` | 无 | stdout 单行 CSV header | 首列必须 timestamp, 末列必须 network_saturation_signal |
| `collect_network_metrics` | 无 | stdout 单行 CSV row | 列数必须 = header 列数, 否则下游 pandas 解析挂 |
| `get_network_field_metadata` | field_name (string) | stdout 单词 (semantic_type) | 返回值必须 ∈ {throughput, packet_count, saturation_counter, drop_counter, error_counter, saturation_signal, gauge, unknown} |
| **`detect_nic_driver`** (config 层) | **env: NETWORK_INTERFACE** | **stdout ∈ {"ena", "gvnic", "virtio", "none"}** | **"none" 是合法兜底 (无 ethtool / 网卡缺失 / 未知 driver), 返回非 4 值即 bug** |

### §15.2 跨 provider 不变量 (基础对称性)

无论 CLOUD_PROVIDER 是 aws / gcp / other, generate_network_csv_header 输出**必须**包含以下 5 列 (顺序可调, 但 timestamp 必首, saturation_signal 必末):

| 必含列 | semantic_type | 用途 |
|---|---|---|
| timestamp | (元数据) | 时序索引 |
| rx_bytes | throughput | 入向流量分析 |
| tx_bytes | throughput | 出向流量分析 |
| rx_packets | packet_count | 入向包率分析 |
| tx_packets | packet_count | 出向包率分析 |
| network_saturation_signal | saturation_signal | 跨平台对齐的"网卡饱和"语义 (0/1) |

### §15.3 provider 特异字段 (字段异构合法清单)

| Provider | Driver | 特异字段集 | 字段总数 | semantic_type 分布 |
|---|---|---|---|---|
| AWS | ena | ena_bw_in_exceeded, ena_bw_out_exceeded, ena_pps_exceeded, ena_conntrack_exceeded, ena_linklocal_exceeded, ena_conntrack_available | 6 | saturation_counter × 5 + gauge × 1 |
| GCP | gvnic | gvnic_tx_drops, gvnic_rx_no_buffer, gvnic_tx_timeout | 3 | drop_counter × 2 + error_counter × 1 |
| **GCP** | **virtio** | **virtio_rx_drops, virtio_tx_tx_timeouts, virtio_rx_xdp_drops, virtio_tx_xdp_tx_drops, virtio_per_queue_rx_drops_sum** | **5** | **drop_counter × 4 + error_counter × 1** |
| Other | none | (无特异字段) | 0 | (仅基础 5 列 + saturation_signal) |

**异构合法性**: AWS 字段 ≠ GCP 字段是设计意图 (不同 NIC 厂商暴露的 counter 物理上就不同), 下游 reader (analysis/network_analyzer.py) 必须用 `get_semantic_type` 查表后分组分析, 禁止字面量字符串匹配 `ena_*` 或 `gvnic_*` 或 `virtio_*`。

### §15.4 saturation_signal 计算规则 (跨平台对齐的关键)

`network_saturation_signal` 列的 0/1 取值由各 provider 内部计算:

| Provider | Driver | saturation_signal = 1 的触发条件 |
|---|---|---|
| AWS | ena | 任一 `ena_*_exceeded` counter > 0 (注: 是 counter 增量 > 0, 不是绝对值) |
| GCP | gvnic | `gvnic_tx_drops` > 0 OR `gvnic_rx_no_buffer` > 0 |
| **GCP** | **virtio** | **任一 `virtio_*` counter > 0 OR per-queue `rx{N}_drops` 聚合 (`virtio_per_queue_rx_drops_sum`) > 0** |
| Other | none | 永远 0 (因为无法判断 cloud-level 饱和, 不假装能判断) |

**统一语义**: 1 = "本采样周期内 NIC 触发了平台特定的饱和/丢包告警", 0 = "本周期 NIC 正常"。下游 analysis 直接对这一列做 `.mean()` 即得"网卡饱和占比", 不需要按 provider 分支。

---

**EOF — 这是 GCP 改造手册的唯一数据源**
