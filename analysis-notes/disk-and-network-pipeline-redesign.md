# Disk & Network Pipeline Redesign — Master Plan

**版本**: v1.3  
**日期**: 2026-05-19  
**作者**: Hermes Agent (with lelandgong)  
**适用范围**: blockchain-node-benchmark 全部 8 链 (Solana / Ethereum / Bitcoin / Sui / Aptos / Bsc / Base / Starknet)  
**目标平台**: AWS EC2 + GCP Compute Engine + EKS + GKE (含 Autopilot/Fargate)  
**Baseline commit**: `15441ad` (Stage 1-3 Y+ NIC abstraction)  
**回滚点**: `e843571` / tag `pre-stage1-business-code`  
**预估工时**: 60h (S1 revert 0.5h + S2-S7 重做 20.5h + S8 chain-as-plugin 7h + S9 L7 监控 10h + S10 权重 schema 4h + **S11 RPC 参数扩展 6h** + **S12 fixtures + sampler + safety 12h**)  
**验收**: cloudtop 90% + kind v1 (1.30) 5% + kind v2 (1.35) 5%

**Changelog**:
- **v1.3 (2026-05-19)**: 用户 YYY 确认后，新增三大章节（基于 3 subagent 并行调研报告 04/05/06）：
  - §20 RPC 参数构造扩展（chain-as-plugin 友好）— 15 个新 `param_format`（EVM 10 + Solana 3 + Starknet 2），复用 baseline `case` 分派模式与 `param_formats` JSON 映射，**增量扩展不重写**
  - §21 Fixtures 池规范 — `fixtures/`（入 repo baseline，单文件 ≤50 KB / 目录 ≤200 KB / 全链 ≤1 MB）+ `fixtures.d/`（gitignored 大池，5–50 MB）双层架构 + manifest.json + 漂移容忍矩阵 + 8 链池规模表
  - §22 采样器与安全护栏 — 4 种 sampler（uniform / weighted / sequential / hot_cold_mix，默认 `hot_ratio=0.2`）+ 22 项 `safety_max_*` 默认值（含 `eth_getLogs.max_block_range=1024` / `getProgramAccounts.requireFilters=true` / `debug_trace*.enabled=false` 等）+ `--unsafe-allow` CLI flag
  - 新增 `analysis-notes/research_notes/` 三份调研报告（04 EVM 复杂参数 / 05 多链复杂参数 / 06 fixture 池工程实践）
  - **关键澄清**（用户主动）：fixture 池**不锁 anchor block** — 各池独立抓"最近 N 块"，时间漂移在分钟-小时级可接受。设计目标是"真实查询体验"而非"学术级 snapshot 自洽"
  - 工时 42h → 60h（+18h：S11 6h + S12 12h，S13 4h 并入 S12）
- v1.2 (2026-05-19): 用户 YYYY 确认，新增三大章节：
  - §17 RPC Method 级资源归因监控（L7 透明代理方案 D，三层架构：Python 代理 + cgroup join + 节点 Prometheus 兜底，零新依赖，8 链通用）
  - §18 Chain-as-Plugin 重构（`config/chains/*.json` 一链一文件 + `chains.d/` 用户覆盖 + jq schema 校验，加新链零代码改动）
  - §19 Mixed 模式权重 schema + 8 链默认值（基于 research_notes/ 公开数据 + 诚实标注 not-found 项）
  - 新增 `analysis-notes/research_notes/` 三份调研报告（01 EVM / 02 Solana-Sui-Aptos / 03 Bitcoin-Starknet）
  - 工时 21h → 42h（+15h 新功能 + 6h 工时上调含 8 链迁移与权重表）
- v1.1 (2026-05-19): 加入"§A. Shell 数组跨进程铁律"（用户实证教训），§10a 数组定义改为强制 `_STR` 镜像，§7 CI guard 新增第 3 条规则
- v1.0 (2026-05-19): 初版 16 章节

---

## §A. Shell 数组跨进程铁律 (用户实证教训，2026-05-19)

### A.1 问题
Bash 的 `export` **只能导出标量字符串**（POSIX env 模型本质是 `char**`）。`declare -a` / `declare -A` / `NAME=(...)` 形式的数组**无法**通过 `export` 跨进程传递。

**实证**（已在 /tmp/parent.sh + /tmp/child.sh 验证）：
```bash
# 父进程
export MY_ARRAY=("a" "b" "c")
bash /tmp/child.sh   # 子进程 bash 调用

# 子进程内
echo "${MY_ARRAY[@]}"   # 输出: <EMPTY>
declare -p MY_ARRAY     # 输出: not found
```

**两种消费方语义截然不同**：
- ✅ `source config/x.sh`（同 shell 进程）→ 数组可见
- ❌ `bash config/x.sh` / `python3 ...` 读 env → 数组**全空**

### A.2 项目现有约定（已实证）
仓库 `config/` 中已有 5 处数组定义，**全部配套 `_STR` 镜像导出**：

| 文件 | 行号 | 数组 | 镜像 export |
|---|---|---|---|
| `config_loader.sh` | L23 / L826 | `BLOCKCHAIN_PROCESS_NAMES` | `BLOCKCHAIN_PROCESS_NAMES_STR="${...[*]}"` |
| `system_config.sh` | L15 / L110 | `ENA_ALLOWANCE_FIELDS` | `ENA_ALLOWANCE_FIELDS_STR` |
| `system_config.sh` | L63 / L111 | `MONITORING_PROCESS_NAMES` | `MONITORING_PROCESS_NAMES_STR` |
| `config_loader.sh` | L148 | `ena_interfaces` | ⚠️ 无镜像（仅同文件 L155 使用，未来跨文件会爆） |

### A.3 强制约定（plan 全篇适用）
1. **任何新增 indexed array** 必须配套同名 `_STR` 镜像 export：
   ```bash
   FOO_FIELDS=("a" "b" "c")
   export FOO_FIELDS_STR="${FOO_FIELDS[*]}"
   ```
2. **跨进程消费方**用 `IFS=' ' read -ra arr <<< "$FOO_FIELDS_STR"` 还原
3. **Associative array (`declare -A`)** 不能 `${ARR[*]}` 一把抽出 → **改用 JSON 文件**（`jq` 读，Python `json.load` 读）或两份 parallel arrays
4. **消费方约定文档化**：每个 `config/*.sh` 顶部注释明确"消费方必须 `source` 而非 `bash`"，且 CI guard 检查
5. **现有 `ena_interfaces` 必须在 S2 顺手加固** `_STR` 镜像（plan 已记入 S2 任务清单）

### A.4 4 种修正方案对照
| # | 方案 | 优点 | 缺点 | 适用 |
|---|---|---|---|---|
| A | source（不 export 数组） | 最简单 | 需文档化"必须 source" | 配置 .sh ↔ .sh |
| B | `_STR` 字符串镜像 + 分隔符还原 | 跨进程可用 | 值不能含分隔符 | **项目主推** |
| C | `declare -p` 序列化 + eval | 完整保留类型 | 临时文件/eval 风险 | 复杂结构 |
| D | JSON 文件 + jq/python | 多语言通用 | 多一层解析 | bash ↔ python (cgroup_collector.py 必用) |

### A.5 为什么这条放在 §A 而不是 §10a
此铁律不只影响 K8s 配置（§10a），还影响：
- §3.3 部署模式 detector 的 NIC 列表数组
- §10b 云变体 `aws_ena.sh` 的 ENA 字段数组
- §10c K8s 版本兼容矩阵
- 任何未来新增的 `config/*.sh`

所以前置为 §A，**优先级高于所有阶段**。

---

## §0. 前言：为什么需要这次重做

### 0.1 触发事件
2026-05-17 夜跑 + 2026-05-18 早班连续发生两起"伪完成"事故：
- **CP-2 network_monitor 重做**：开发者把 ENA 字段动态化新代码放在 `utils/network/ena_network_monitor.sh`，单元测试 L1-L4 全绿，commit 入 main，但 `monitoring/unified_monitor.sh` L35-36 仍 `source monitoring_coordinator.sh` 旧路径 → 主流程从未调用新代码。
- **CP-3 disk_monitor 重做**：同样套路。新文件 `utils/disk/cgroup_disk_collector.sh`，新人 `grep config/*.sh` 找 GCP 改造会 0 命中 → 误判项目"还没做 GCP"。主链路 source 未切换。

诊断后定性为 **并行入口陷阱** (parallel-entry-trap)，已升级为独立 skill (`software-development/parallel-entry-trap`)。

### 0.2 暴露出的更深层问题
顺藤摸瓜审计发现 **5 类根本性缺口**：

| # | 类别 | 严重度 | 影响 |
|---|---|---|---|
| 1 | GCP 全平台覆盖不足 | 🔴 阻断 | gVNIC / IDPF / Tier_1 / Local SSD 未单独处理 |
| 2 | K8s 部署模式 0 支持 | 🔴 阻断 | EKS/GKE 客户无法跑 (8 链 ≥3 链在 K8s 部署) |
| 3 | cgroup 采集器缺失 | 🟡 高危 | Pod 内运行时 IOPS/Memory 字段全错 |
| 4 | IMDSv1/v2 split-brain | 🟡 高危 | AWS 强制 IMDSv2 客户脚本静默失败 |
| 5 | K8s API 硬编码 | 🟡 高危 | K8s 版本升级 (1.27→1.35) 后字段路径失效 |

### 0.3 设计哲学
本次重做坚持 **R0 零号规则** + **彻底兼容 > 修修补补**：
- ❌ 不接受 "AWS 跑通即可，GCP 后续补"
- ❌ 不接受 "VM 跑通即可，K8s 后续补"
- ❌ 不接受 "1.30 跑通即可，1.35 后续补"
- ✅ 同框架公平对比：AWS / GCP 字段对等 + 各自最优监控
- ✅ 多部署模式对等：VM bare / VM systemd / Docker / K8s EKS / K8s GKE 全支持
- ✅ 多 K8s 版本对等：1.27-1.35 双兼容 (cgroup v1 + v2)

### 0.4 决策快照 (12 个 resolved)
| # | 决策 | 选项 | 终值 |
|---|---|---|---|
| 1 | DEPLOYMENT_MODE 默认 | auto / vm_bare / vm_systemd | `vm_bare` (b) |
| 2 | skill 升级时机 | 先写后并行 / 并行 | 并行 (a) |
| 3 | revert 时机 | 立即 / 写完 plan 后 | 写完 plan 后 (a) |
| 4 | 执行监督 | 全程在场 / 夜跑 | 全程在场 (a) |
| 5 | K8s 版本支持范围 | A 激进 / **B 务实** / C 保守 | **B (1.27-1.35)** |
| 6 | K8s API 配置化 | α 单文件 / **β 5 分组** | **β** |
| 7-12 | (见早班讨论 39 项清单) | - | 全部 resolved |

---

## §1. 范围与目标

### 1.1 In Scope
- **磁盘监控管线** (disk pipeline)：iostat / cgroup io.stat / EBS 字段 / GCP PD 字段 / Local SSD
- **网络监控管线** (network pipeline)：sar / ENA allowance / gVNIC dropped / IDPF / cgroup network (skip — 无)
- **部署模式探测器** (deployment-mode detector)：auto 探测 + 5 mode 分发
- **K8s 兼容性 shim** (k8s-compat)：API 端点 / 字段映射 / cgroup 路径 v1↔v2
- **8 链 RPC 健康检查** (rpc-health)：保持现有架构，仅升级 endpoint discovery
- **CI 守门** (parallel-entry-trap guard)：每 commit 跑 grep 主链路 source 链

### 1.2 Out of Scope
- VM 双天花板 (vm-level IOPS/throughput cap)：仅留 config hook，不实现
- Kafka / message-queue 监控：不在本期
- 上链业务级 metrics (slot lag, peer count)：保持现状不动
- Windows 节点：8 链均 Linux only
- Bare-metal 跨数据中心同步：cloudtop + EKS/GKE 验收足够

### 1.3 验收标准
| 环境 | 权重 | 通过条件 |
|---|---|---|
| cloudtop (GCP e2-standard-8 / cgroup v2) | 90% | 主流程端到端走新代码 (bash -x 实证) + 8 链 RPC mock 全绿 |
| kind K8s 1.30 (cgroup v1) | 5% | DaemonSet 起，Pod IOPS/Memory 字段全出 |
| kind K8s 1.35 (cgroup v2) | 5% | 同上 + cgroup 路径自动切换 |

### 1.4 不验收即失败
- ❌ 单元测试全绿但 `grep -r unified_monitor.sh monitoring/` 仍指向旧代码
- ❌ `bash -x unified_monitor.sh 2>&1 | grep ena_network_monitor` 无输出
- ❌ AWS 路径有 ENA allowance，GCP 路径 0 个 gVNIC dropped 字段
- ❌ K8s 模式下 IOPS 取了节点级而非 Pod 级

---

## §2. 现状审计：5 类缺口详解

### 2.1 缺口 #1: GCP 全平台覆盖不足

#### 2.1.1 现状
| 维度 | AWS 覆盖 | GCP 覆盖 |
|---|---|---|
| NIC 驱动 | ENA (`ena_*` 字段) | ❌ gVNIC / IDPF 字段缺失 |
| 磁盘类型 | EBS gp3/io2 | ❌ PD-SSD/Hyperdisk/Local SSD 缺失 |
| 元数据 | IMDSv1 (脚本仅这条) | ❌ metadata.google.internal header 模型缺失 |
| 网络 Tier | N/A | ❌ Tier_1 网络性能升级未识别 |
| 实例类型探测 | `aws ec2 describe-instances` | ❌ `gcloud compute instances describe` 缺失 |

#### 2.1.2 业务铁律 (实证已记忆)
- **AWS EBS SSD**：256 KiB 拆分，`AWS_iops = (r/s+w/s) × ceil(areq_sz/256)`
- **AWS EBS HDD**：1024 KiB 拆分
- **GCP PD/Hyperdisk**：完全不拆，`GCP_iops = r/s + w/s` (passthrough)
- **GCP Local SSD 单块上限** (cloud.google.com/compute/docs/disks/local-ssd 实证 2026-05-19)：read 170k IOPS / write 90k IOPS / read 660 MB/s / write 350 MB/s
- **拒绝 Gemini 错估数字**：390k/170k/1560/800 (高估 2-2.4 倍)，必须在 `config/cloud_variants/gcp_local_ssd.sh` 注释中显式标注

### 2.2 缺口 #2: K8s 部署模式 0 支持

#### 2.2.1 现状
代码库假设所有目标节点是 "裸 VM + iostat/sar 节点级" 部署。但 8 链中实际：
- Bsc / Base / Starknet：客户常用 EKS DaemonSet 模式
- Ethereum 归档节点：客户常用 GKE Autopilot
- Sui / Aptos：客户常用 EKS + Karpenter

K8s 模式下：
- iostat 看节点级，无法区分 Pod
- `df -h` 看 hostPath，看不到 PVC
- ENA 字段在节点级，多 Pod 共享时无归因

#### 2.2.2 EKS vs GKE 差异 (11 维度对比)
| # | 维度 | EKS | GKE |
|---|---|---|---|
| 1 | CNI 模型 | VPC CNI (underlay, Pod = ENI IP) | Calico/Dataplane V2 (overlay) |
| 2 | Pod IP | VPC 直接路由 | NAT 出节点 |
| 3 | 每节点最大 Pod | ENI × IP / ENI (实例族决定) | 110 (默认) |
| 4 | 节点 OS | AL2 / AL2023 / Bottlerocket | COS / Ubuntu |
| 5 | CSI 路径 | `/var/lib/kubelet/plugins/ebs.csi.aws.com/` | `/var/lib/kubelet/plugins/pd.csi.storage.gke.io/` |
| 6 | metadata endpoint | 169.254.169.254 | metadata.google.internal (169.254.169.254) |
| 7 | NIC 探测 | 多 ENI (Pod 分配) | 单 NIC (overlay) |
| 8 | 自动化产品 | Fargate (无节点访问) | Autopilot (无节点访问) |
| 9 | 节点 systemd unit | kubelet.service | kubelet.service (相同) |
| 10 | cgroup driver | systemd (1.32+ 默认) | systemd (1.32+ 默认) |
| 11 | RBAC | aws-auth ConfigMap → EKS Access Entries | Google IAM |

**结论**：差异中等，2-3 处适配 (NIC 探测 / CSI 路径 / Autopilot/Fargate 跳过)。

### 2.3 缺口 #3: cgroup 采集器缺失

#### 2.3.1 4 大指标可行性矩阵
| 指标 | VM 节点级 | Pod 级 cgroup | 备注 |
|---|---|---|---|
| CPU | iostat | cpu.stat ✅ | 等价精确 |
| Memory | free / /proc/meminfo | memory.stat ✅ | Pod 级更细 |
| IOPS | iostat | io.stat ✅ | 完全等价 (rios/wios) |
| Throughput | iostat | io.stat ✅ | 完全等价 (rbytes/wbytes) |
| Network 字节 | sar | ⚠️ 部分 (依赖 CNI) | Pod 级有，但瓶颈字段无 |
| ENA allowance | ethtool ena | ❌ Pod 级 N/A | 必须节点级 |
| gVNIC dropped | ethtool -S | ❌ Pod 级 N/A | 必须节点级 |
| Disk latency | iostat await | ❌ Pod 级 cgroup 不暴露 | 内核限制 |
| Disk util% | iostat util | ❌ 同上 | 内核限制 |
| Queue depth | iostat aqu-sz | ❌ 同上 | 内核限制 |

#### 2.3.2 cgroup v2 io.stat 6 字段 (kernel.org 实证)
```
rbytes  wbytes  rios  wios  dbytes  dios
```
- `rbytes/wbytes` ≈ iostat rkB/s × interval
- `rios/wios` ≈ iostat r/s + w/s
- `dbytes/dios` = discard 操作 (SSD trim)

### 2.4 缺口 #4: IMDSv1/v2 split-brain

#### 2.4.1 现状
代码全部用 `curl http://169.254.169.254/latest/meta-data/...` (IMDSv1)。AWS 2024 起强制 IMDSv2 (token-based)，客户脚本静默 401。

#### 2.4.2 GCP 不同流派 (实证)
GCP metadata 是 **header 模型**：
```bash
curl -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/...
```
不需要 token，但需要 header (SSRF 防护)。

### 2.5 缺口 #5: K8s API 硬编码

#### 2.5.1 K8s 数据源 7 类稳定性分级
| 级别 | 数据源 | 稳定性 | 风险 |
|---|---|---|---|
| K1 | kubelet /stats/summary | 半 GA (v1beta1) | 中 |
| K2 | kubelet /metrics/cadvisor | 实现细节 | 中 |
| K3 | core /api/v1/pods | GA | 极低 |
| K4 | core /api/v1/nodes | GA | 极低 |
| K5 | storage /api/v1/persistentvolumeclaims | GA | 极低 |
| K6 | metrics.k8s.io/v1beta1 | beta (~7 年稳) | 低 |
| K7 | /sys/fs/cgroup/ 路径 | 实现细节 | 高 (v1↔v2 已变) |

#### 2.5.2 实证支持 (kubernetes.io/docs/reference/using-api/deprecation-policy)
- Rule #1: "Once added to API group, can NOT be removed regardless of track"
- Rule #4a: "No current plans for major version revision that removes GA APIs"

#### 2.5.3 2.5 年内 breaking change
| 版本 | 变化 | 影响 |
|---|---|---|
| 1.24 | dockershim 移除 | containerd 强制 |
| 1.27 | storage.k8s.io/v1beta1 移除 | PVC 切 v1 |
| 1.29 | hostUsers 字段 | userns 支持 |
| 1.32 | cgroup driver 自动检测 | systemd 默认 |
| 1.33 | EndpointSlices 替代 Endpoints | service discovery |
| 1.34 | AppArmor deprecate | annotation → field |
| 1.35 | **cgroup v1 移除** | v1 节点拒绝 |

#### 2.5.4 EKS/GKE 支持周期
- EKS: 14 月标准 + 12 月扩展 = **26 月** (docs.aws.amazon.com line 25)
- GKE: 14 月标准 + 10 月扩展 = **24 月** (cloud.google.com versioning line 247-267)
- 客户实际跨度: **1.27-1.35 / 2.5 年 / 9 minor**

---


## §3. 目标架构总览

### 3.1 分层架构图
```
┌─────────────────────────────────────────────────────────────┐
│ 入口层 (unified_monitor.sh / main_pipeline.sh)              │
│   ✅ 单一真相源, 主流程必经                                   │
└──────────────────────┬──────────────────────────────────────┘
                       │ source (CI guard 强制)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 部署模式探测层 (deployment_mode_detector.sh)                 │
│   auto / vm_bare / vm_systemd / docker / k8s_eks / k8s_gke  │
└──────────────────────┬──────────────────────────────────────┘
                       │
            ┌──────────┼──────────┬──────────┐
            ▼          ▼          ▼          ▼
       ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
       │ VM     │ │ Docker │ │ K8s    │ │ K8s    │
       │ 采集器 │ │ 采集器 │ │ EKS    │ │ GKE    │
       └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘
           │          │           │          │
           └──────────┴───────────┴──────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 云变体层 (cloud_variants/)                                    │
│   aws_ebs.sh / aws_ena.sh / gcp_pd.sh / gcp_gvnic.sh /       │
│   gcp_local_ssd.sh / gcp_idpf.sh                             │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ K8s API 兼容层 (utils/k8s_compat.sh + config/k8s_*.sh)       │
│   path / endpoint / field_name / version_shim               │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 关键设计决策
- **单一入口** (避免并行入口陷阱)：unified_monitor.sh 是唯一入口，CI guard 验证
- **5 mode 分发**：DEPLOYMENT_MODE 由 detector 自动确定，可手工 override
- **云变体插件化**：每个 (cloud, resource) 组合一个 .sh，detector 选择 source
- **K8s API 全配置化**：5 文件分组 + shim 函数层
- **fail-soft 回退**：探测失败 → 降级 → 警告 → 继续 (不阻断 benchmark)

### 3.3 部署模式自动探测瀑布
```
1. 显式 DEPLOYMENT_MODE env → 用之
2. /proc/1/cgroup 含 "kubepods" → k8s_*
3. 区分 EKS/GKE: /etc/eks-release 存在 → eks; /etc/gke-* 存在 → gke
4. /.dockerenv 存在 → docker
5. systemctl 可用 + 业务 unit 存在 → vm_systemd
6. 默认 → vm_bare
```

---

## §4. 文件结构变更

### 4.1 新增文件 (待创建)
```
config/
├── deployment_mode_detector.sh      # 部署模式自动探测
├── k8s_paths.sh                     # HOST_PROC/HOST_SYS/cgroup 路径模板
├── k8s_api_endpoints.sh             # kubelet/api-server endpoint 模板
├── k8s_field_names.sh               # JSON 字段名映射
├── k8s_compat.sh                    # 版本/兼容矩阵
└── cloud_variants/
    ├── aws_ebs.sh
    ├── aws_ena.sh
    ├── gcp_pd.sh
    ├── gcp_gvnic.sh
    ├── gcp_local_ssd.sh             # 含 170k/90k/660/350 + 拒绝注释
    └── gcp_idpf.sh

utils/
└── k8s_compat.sh                    # shim 函数层 (cgroup v1↔v2 适配)

monitoring/
└── cgroup_collector.py              # 4 mode 自动探测 + io.stat 解析

deploy/k8s/
├── 01-namespace.yaml
├── 02-serviceaccount-rbac.yaml
├── 03-configmap.yaml
└── 04-daemonset.yaml

ci/
└── check_parallel_entry.sh          # CI guard: grep 主链路 source 链
```

### 4.2 现有需修改 (主链路切换 + 字段动态化)
```
monitoring/unified_monitor.sh        L204  source 切到 cgroup_collector.py
monitoring/monitoring_coordinator.sh L35-36 改 wrapper 转发新代码
utils/unit_converter.py              L253  AWS 256K/1024K 拆分逻辑
visualization/ebs_chart_generator.py L127  添加 GCP PD 图表
config/config_loader.sh              L106  加载 deployment_mode_detector
```

### 4.3 删除 (并行入口陷阱产物)
```
utils/network/ena_network_monitor.sh   # 内容合并进 cloud_variants/aws_ena.sh
utils/disk/cgroup_disk_collector.sh    # 内容合并进 monitoring/cgroup_collector.py
```

---

## §5. 阶段拆分 (S1-S12)

### S1: 回滚 + 安全网 (0.5h)
1. `git revert --no-commit e62cf60^..8ee32ba` (闭区间，含起点；revert 昨晚 2 commit：CP-3 feat + docs)
2. `git commit -m "revert: CP-3 disk Y+ (parallel-entry trap)"` 单合并 commit
3. tag `pre-stage2-redesign` 留新回滚点（v1.3 plan 已 tag 为 `pre-stage1-redesign-v1.3`，本 tag 表示"S1 已完成，从 baseline 重启 S2"）
4. 验证 `git log --oneline -5` 显示干净 + `ls monitoring/disk_*.sh monitoring/disk/` 应为 No such file
5. `bash -n monitoring/unified_monitor.sh && bash -n monitoring/iostat_collector.sh && bash -n config/config_loader.sh` 三项语法健全
6. `grep -rn "disk_monitor.sh\|disk_unified_entry.sh\|monitoring/disk/" .` 应 0 命中（无死引用）

**⚠️ 坑 #1 git rev-range 闭/开区间**：`git revert A..B` 是**开区间**（不含 A 自身），如果想 revert A 到 B 之间的所有 commit（含两端），必须用 `A^..B`（A 的 parent 到 B）。曾经按 `e62cf60..8ee32ba` 跑只 revert 了 docs commit。
**⚠️ 坑 #2 `git reset --hard` 审批拦截**：cloudtop 上 `git reset --hard` 会被 user-approval 拦截；要 abort 进行中的 revert/cherry-pick 用 `git revert --abort` / `git cherry-pick --abort` 替代。
**⚠️ 坑 #3 `unified_monitor.sh --dry-run`**：baseline 不支持该 flag。dry-run 用 `bash -n` 做语法验证；运行时验证需要在 S2+ 加入 detector 后才能跑（cloudtop 上 sudo 不可用，跑 iostat/sar 受限）。

### S2: 部署模式 detector + HOST_PROC env (3h)
1. 写 `config/deployment_mode_detector.sh` (6 步瀑布)
2. 写 `config/k8s_paths.sh` (HOST_PROC=${HOST_PROC:-/proc} 等)
3. 改 `config/config_loader.sh` L106 加载 detector
4. 单元测试：mock 5 mode 各跑一次
5. 验收：cloudtop 跑出 `vm_bare`，kind 跑出 `k8s_*`

### S3: cgroup 采集器 (4h)
1. 写 `monitoring/cgroup_collector.py` (4 mode 自动探测)
2. 实现 io.stat 解析 (rbytes/wbytes/rios/wios/dbytes/dios)
3. 实现 memory.stat 解析 (anon/file/kernel/slab/sock/swap)
4. 实现 cpu.stat 解析 (usage_usec/throttled_usec/nr_periods/nr_throttled)
5. fail-soft：cgroup v1 → 走 `<root>/{blkio,memory,cpu,cpuacct}/<path>/`，4 mode = {v2, v1, unmounted, unresolved}
6. 单元测试：cgroup v1 + v2 各跑一次（synthetic 临时目录 + parser 单测）
7. 验收：4 mode 全覆盖 + cloudtop 真实 `--debug` 输出非零 + meta_source ∈ {v2,v1,unmounted,unresolved} + 19 字段 schema 不变

**⚠️ §S3.7 验收 "iostat 误差 <5%" 的设计假设是错的**（v1.3 plan 笔误）。iostat 显示 block-layer 物理 IO（merge/queued 之后），cgroup io.stat 是 bio-layer 累计（merge 之前，含 page cache writeback 多次计数）。实测 cloudtop sda kB_wrtn=258GB vs cgroup root wbytes=792GB，差 ~3x 属正常。两者**语义不同**，不能直接比对。
**⚠️ 坑 #7 cgroup v2 root io.stat 数据可见性**：非 root 用户的 user.slice 子 scope 不暴露 io.stat（叶子 scope only），所以默认 `TARGET_CGROUP=$(resolve self)` 时 IO 字段会全是 0；要取真实数据必须 `TARGET_CGROUP=/`（root）或 systemd unit scope（如 `/system.slice/geth.service`）。S6 业务集成阶段会按链 systemd unit 配置正确 TARGET_CGROUP。
**⚠️ 坑 #8 cgroup v2 io.stat 包含 discard bytes**：collector 单独输出 `cgroup_io_dbytes/dios` 字段方便排查 TRIM/discard 流量（NVMe SSD 上常见）。

### S4: K8s DaemonSet manifest (2h)
1. 写 `deploy/k8s/01-04-*.yaml`
2. RBAC: nodes/proxy + pods + persistentvolumeclaims 读权限
3. hostPath mount: /proc, /sys, /dev → /host_proc, /host_sys, /host_dev
4. 验收：kind apply -f 后 DaemonSet 起，Pod log 输出 cgroup 数据

### S5: Pod→Device 映射 + kubelet stats (3h)
1. 写 Pod→PVC→PV→device-name 映射 (3 跳查询)
2. 集成 kubelet /stats/summary (K1)
3. 集成 /api/v1/pods (K3) RPC endpoint discovery
4. 验收：kind 内跑 RPC mock，能正确归因 IOPS 到 Pod

### S6: 瓶颈归因 + 8 链业务集成 (4h)
1. 实现 ENA allowance / gVNIC dropped → Pod 归因 (基于流量比例)
2. 实现 Local SSD 170k/90k 上限判定
3. 8 链业务 binary 探测 + RPC 健康检查
4. 验收：cloudtop 跑 8 链 mock，瓶颈归因报告全出

### S7: 版本兼容性 shim + CI guard (4h)
1. 写 `utils/k8s_compat.sh` (cgroup v1↔v2 路径切换)
2. 写 `config/k8s_compat.sh` (1.27-1.35 版本矩阵)
3. 写 `ci/check_parallel_entry.sh` (grep 主链路 source 链)
4. pre-commit hook 集成
5. 验收：kind 1.30 (v1) + kind 1.35 (v2) 各跑一次全通

### S8: Chain-as-Plugin 重构 (7h) — 新增 §18
**先做，避免技术债**：在 S9/S10 之前完成，让监控与权重直接基于新架构。
1. 写 `config/chains/_schema.json` (JSON-Schema draft-07，含 mixed 权重约束)
2. 拆 `config_loader.sh` heredoc → 8 个 `config/chains/<chain>.json` 文件
3. 改 `config_loader.sh` L331+L362 → 30 行 jq 调度逻辑（§18.5）
4. 创建 `config/chains.d/` + README + `.gitignore` 规则
5. 兼容 §A._STR 镜像约定（BLOCKCHAIN_PROCESS_NAMES 等导出）
6. e2e 测试：8 链各跑一次 single + mixed，确认无回归
7. 加新链验证：建一个 `chains.d/sei.json` 跑通即合格

### S9: RPC Method 级监控 (10h) — 新增 §17
1. 写 `tools/rpc_proxy.py` (Python ~200 LOC，asyncio + aiohttp，单 + batch + REST 三模式)
2. 写 `tools/rpc_method_join.py` (~100 LOC，cgroup × method 时间窗口加权归因)
3. 写 `tools/rpc_count_reconcile.py` (~50 LOC，5 链 Prometheus 兜底对账)
4. 集成进 `monitoring/unified_monitor.sh`（RPC_PROXY_LISTEN 非空时自动启动代理）
5. per-method 报告生成（CSV + markdown 汇总）
6. 8 链 e2e 测试（5k QPS @ <1ms p99 added latency 验证）
7. 失败模式验证（代理 kill / cgroup 不可读 / 超载采样降级）

### S10: Mixed 权重 Schema + 默认值 (4h) — 新增 §19
1. 在 §18.3 schema 基础上加 mixed 权重约束（minProperties=3，单值 0-1）
2. 在 `config_loader.sh` 加权和校验（±0.01 容差）
3. 填充 8 链默认权重 JSON（每条带 `_comment` 标注来源）
4. 写 `config/chains.d/README.md`（含覆盖示例与 prod 流量分析建议）
5. e2e 测试：8 链各跑一次 mixed，看代理日志确认 method 命中率符合权重

### S11: RPC 参数 case-dispatch 扩展 (6h) — 新增 §20
1. 在 `target_generator.sh:124` 之后追加 15 个新 `case` 分支（EVM 10 + Solana 3 + Starknet 2），全部纯 shell + jq 实现
2. `get_tip_block` 启动期缓存 12s 写 `/tmp/.tip_cache.$$`，避免每请求查 head
3. 升级 `chains/<chain>.json` schema：每 method 加 `pools{}` + `safety{}` 字段；jq schema 校验 hook 更新
4. 8 链 chains/*.json 填充新 method 的 `param_format` + `pools` 引用 + `_comment` 标注来源
5. e2e 测试：8 链各跑一次 `eth_getLogs` / `getProgramAccounts` / `starknet_getEvents` 等复杂方法，确认 JSON-RPC payload schema 合法（jq + provider mock 校验）

### S12: Fixtures 池 + sampler + safety 护栏 (12h) — 新增 §21 + §22
1. 落地双层架构：`fixtures/`（入 repo，CI/冒烟）+ `fixtures.d/`（gitignored，真实压测）+ `.gitignore` 规则（30 min）
2. 写 `tools/build_fixtures.sh`（统筹入口）+ `tools/write_manifest.py`（manifest.json 汇总，含 sha256 + fetched_at + latest_block_at_fetch）（1.5h）
3. 新增 3 个 fetcher：`tools/fetch_tx_hashes.py` / `fetch_blocks.py` / `fetch_contracts.py`，复用 baseline `BlockchainAdapter` 模式（4h）
4. 8 链 `fixtures/<chain>/*` baseline 数据填充（每链 ~10 min 抓取脚本，含 manifest）（1.5h）
5. 实现 4 种 sampler（`uniform` / `weighted` / `sequential` / `hot_cold_mix`）+ chain.json `sampler{}` schema + jq 取样公式（2h）
6. 实现 22 项 `safety_max_*` 默认值表 + chain.json `safety{}` schema + runner 启动期 fail-fast 校验 + `--unsafe-allow` CLI flag + manifest 留痕（2h）
7. 运行期 drift sanity：启动一次性扫所有 `manifest.json` + 调 1 次 `eth_blockNumber`/`getSlot` 判 warn/fail + 输出 `drift_report.json`（0.5h）
8. e2e 一致性测试：8 链各跑一次完整 mixed 流程（fixture load → sample → safety guard → param build → RPC call → method 命中验证）（0.5h）

### 总工时
| 阶段 | 工时 | 累计 | 备注 |
|---|---|---|---|
| S1 | 0.5h | 0.5h | revert + 安全网 |
| S2 | 3h | 3.5h | 部署模式 detector |
| S3 | 4h | 7.5h | cgroup 采集器 |
| S4 | 2h | 9.5h | K8s DaemonSet manifest |
| S5 | 3h | 12.5h | Pod→Device 映射 |
| S6 | 4h | 16.5h | 瓶颈归因 + 8 链业务 |
| S7 | 4h | 20.5h | 版本兼容 shim + CI guard |
| **S8** | **7h** | **27.5h** | **§18 chain-as-plugin 重构** |
| **S9** | **10h** | **37.5h** | **§17 RPC method 级监控** |
| **S10** | **4h** | **42h** | **§19 权重 schema + 8 链默认值** |
| **S11** | **6h** | **48h** | **§20 RPC 参数 case-dispatch 扩展（15 个新 param_format）** |
| **S12** | **12h** | **60h** | **§21 + §22 fixtures 双层架构 + sampler + safety 护栏** |
| **合计** | | **60h** | (v1.2 42h → v1.3 60h，+18h：S11 6h + S12 12h) |

**关键顺序约束**：
- S8 必须在 S9/S10 之前完成（用户决策 4，避免技术债）
- S9 与 S10 可并行（S10 只改 schema/JSON，不动 S9 代码）
- **S11 必须在 S12 之前完成**：S12 的 sampler + safety 依赖 S11 落定的 `param_format` 列表
- **S11/S12 必须在 S8 之后**：依赖 chain-as-plugin schema 已升级到位

---


## §6. 各阶段验收命令

### S1 验收
```bash
git log --oneline -5
# 应看到 revert commits + baseline 15441ad
```

### S2 验收
```bash
# cloudtop
bash config/deployment_mode_detector.sh
# 期望输出: DEPLOYMENT_MODE=vm_bare

# kind
kubectl apply -f deploy/k8s/
kubectl exec daemonset/bnb-collector -- bash config/deployment_mode_detector.sh
# 期望输出: DEPLOYMENT_MODE=k8s_*
```

### S3 验收
```bash
# cloudtop io.stat vs iostat
python3 monitoring/cgroup_collector.py --interval 10 --duration 60 > /tmp/cgroup.json
iostat -x 10 60 > /tmp/iostat.txt
python3 -c "
import json
d = json.load(open('/tmp/cgroup.json'))
# 比对 rbytes 总量 与 iostat rkB/s × 60 × 1024
# 误差应 <5%
"
```

### S4 验收
```bash
kubectl apply -f deploy/k8s/
kubectl wait --for=condition=ready pod -l app=bnb-collector --timeout=60s
kubectl logs daemonset/bnb-collector | grep "cgroup.*rbytes"
# 期望有 cgroup 数据输出
```

### S5 验收
```bash
# kind 内跑 RPC mock
kubectl apply -f tools/mock_rpc_server.yaml
kubectl exec -it bnb-collector-xxx -- python3 monitoring/pod_device_mapper.py
# 期望输出: Pod=mock-solana-0 PVC=data-0 Device=/dev/nvme1n1 IOPS=12345
```

### S6 验收
```bash
# 8 链 mock 全跑
./tools/mock_rpc_server.py --chains all &
bash monitoring/unified_monitor.sh --bottleneck-report
# 期望报告含: ENA allowance attribution / Local SSD 170k cap / RPC health 8/8
```

### S7 验收
```bash
# CI guard
bash ci/check_parallel_entry.sh
# 期望: PASS (主链路 source 新代码)

# 双 cgroup 版本
kind create cluster --image kindest/node:v1.30.0  # cgroup v1
kubectl apply -f deploy/k8s/ && <S4 验收>
kind delete cluster && kind create cluster --image kindest/node:v1.35.0  # cgroup v2
kubectl apply -f deploy/k8s/ && <S4 验收>
```

---

## §7. CI Guard 实现 (防并行入口陷阱回归)

### 7.1 ci/check_parallel_entry.sh 内容
```bash
#!/usr/bin/env bash
# CI guard: 验证主链路 source 链未出现"并行入口"
set -euo pipefail

MAIN_ENTRIES=(
  monitoring/unified_monitor.sh
  monitoring/main_pipeline.sh
)

REQUIRED_NEW=(
  monitoring/cgroup_collector.py
  config/deployment_mode_detector.sh
  config/cloud_variants/
)

FAIL=0
for entry in "${MAIN_ENTRIES[@]}"; do
  for required in "${REQUIRED_NEW[@]}"; do
    if ! grep -rE "(source|import|exec).*${required##*/}" "$entry" > /dev/null; then
      echo "FAIL: $entry 未引用 $required"
      FAIL=1
    fi
  done
done

# 验证旧路径已删除
FORBIDDEN_OLD=(
  utils/network/ena_network_monitor.sh
  utils/disk/cgroup_disk_collector.sh
)
for forbidden in "${FORBIDDEN_OLD[@]}"; do
  if [[ -e "$forbidden" ]]; then
    echo "FAIL: 并行入口残留: $forbidden"
    FAIL=1
  fi
done

# 规则 3 (新增, v1.1): config/*.sh 不能被 `bash` 子进程调用 (会丢数组, 见 §A)
if grep -rnE 'bash\s+config/[a-z_]+\.sh' monitoring/ utils/ deploy/ 2>/dev/null; then
  echo "FAIL: config/*.sh 被当成可执行调用 → 数组跨进程丢失 (见 §A)"
  FAIL=1
fi

# 规则 4 (新增, v1.1): config/ 中每个 indexed array 必须有 _STR 镜像
for cfg in config/*.sh; do
  # 提取数组名 (匹配 NAME=(...) 形式, 排除函数局部 local)
  while IFS= read -r array_name; do
    [[ -z "$array_name" ]] && continue
    # 检查是否有 ${array_name}_STR export
    if ! grep -qE "export\s+${array_name}_STR=" "$cfg"; then
      echo "FAIL: $cfg 定义数组 $array_name 但缺少 ${array_name}_STR 镜像 (违反 §A.3)"
      FAIL=1
    fi
  done < <(grep -oE '^[[:space:]]*[A-Z_][A-Z0-9_]*=\(' "$cfg" | sed 's/=.*$//' | tr -d ' ')
done

[[ $FAIL -eq 0 ]] && echo "PASS: 无并行入口陷阱"
exit $FAIL
```

### 7.2 pre-commit hook
```bash
# .git/hooks/pre-commit
#!/usr/bin/env bash
bash ci/check_parallel_entry.sh || {
  echo "Commit 被拒：并行入口陷阱"
  exit 1
}
```

---

## §8. 风险与缓解

| # | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| 1 | cgroup v1 节点 io.stat 字段不全 | 中 | 高 | shim 函数回退 /sys/fs/cgroup/blkio/ |
| 2 | Autopilot/Fargate 无节点访问 | 高 | 中 | detector 识别 → 标记 "limited mode" + 跳过 hostPath 采集 |
| 3 | EKS VPC CNI 多 ENI Pod 归因复杂 | 中 | 中 | 用 Pod IP 反查 ENI (aws ec2 describe-network-interfaces) |
| 4 | GKE Dataplane V2 (eBPF) sar 字段变 | 低 | 中 | gvnic 字段标准化，dropped 用 eBPF map 读 |
| 5 | K8s 1.36+ 未来变化 | 低 | 高 | k8s_compat.sh 版本矩阵设计为可扩展 |
| 6 | 工时超 21h | 中 | 中 | S6/S7 可独立并行 subagent，分工压缩到 16h |
| 7 | 8 链 mock RPC 不真实 | 低 | 低 | mock_rpc_server.py 已实现 stdlib only，validation 通过 |

---

## §9. 兼容性矩阵 (4 级)

### 9.1 部署模式 × 云
| | AWS EC2 | GCP CE | EKS | GKE | EKS Fargate | GKE Autopilot |
|---|---|---|---|---|---|---|
| vm_bare | ✅ | ✅ | - | - | - | - |
| vm_systemd | ✅ | ✅ | - | - | - | - |
| docker | ✅ | ✅ | - | - | - | - |
| k8s_eks | - | - | ✅ | - | ⚠️ limited | - |
| k8s_gke | - | - | - | ✅ | - | ⚠️ limited |

### 9.2 K8s 版本 × cgroup 版本
| K8s 版本 | cgroup v1 | cgroup v2 | 默认 |
|---|---|---|---|
| 1.27 | ✅ | ✅ | v1 |
| 1.28 | ✅ | ✅ | v1 |
| 1.29 | ✅ | ✅ | v2 |
| 1.30 | ✅ | ✅ | v2 |
| 1.31 | ✅ | ✅ | v2 |
| 1.32 | ✅ | ✅ | v2 |
| 1.33 | ✅ | ✅ | v2 |
| 1.34 | ✅ | ✅ | v2 |
| 1.35 | ❌ deprecated | ✅ | v2 |

### 9.3 链 × 部署模式 (客户实际部署)
| 链 | vm_bare | vm_systemd | docker | EKS | GKE |
|---|---|---|---|---|---|
| Solana | ✅ 主流 | ✅ | - | - | - |
| Ethereum | ✅ | ✅ | ✅ | - | ✅ 归档 |
| Bitcoin | ✅ 主流 | ✅ | - | - | - |
| Sui | ✅ | - | ✅ | ✅ | - |
| Aptos | ✅ | - | ✅ | ✅ | - |
| Bsc | ✅ | ✅ | ✅ | ✅ | ✅ |
| Base | ✅ | - | ✅ | ✅ | - |
| Starknet | ✅ | - | ✅ | ✅ | - |

---


## §10a. K8s API 全配置化 — 5 文件结构

### 10a.1 config/k8s_paths.sh
```bash
# 文件系统路径模板 (受 DaemonSet hostPath mount 影响)
export HOST_PROC="${HOST_PROC:-/proc}"
export HOST_SYS="${HOST_SYS:-/sys}"
export HOST_DEV="${HOST_DEV:-/dev}"
export HOST_ROOT="${HOST_ROOT:-/}"

# cgroup 路径模板 (v1 + v2)
export CGROUP_V2_ROOT="${HOST_SYS}/fs/cgroup"
export CGROUP_V1_BLKIO="${HOST_SYS}/fs/cgroup/blkio"
export CGROUP_V1_MEMORY="${HOST_SYS}/fs/cgroup/memory"
export CGROUP_V1_CPU="${HOST_SYS}/fs/cgroup/cpu"

# K8s Pod cgroup slice 模板
export POD_CGROUP_SLICE_V2_TEMPLATE="${CGROUP_V2_ROOT}/kubepods.slice/kubepods-{qos}.slice/kubepods-{qos}-pod{uid}.slice"
export POD_CGROUP_SLICE_V1_TEMPLATE="${CGROUP_V1_BLKIO}/kubepods.slice/kubepods-{qos}.slice/kubepods-{qos}-pod{uid}.slice"
```

### 10a.2 config/k8s_api_endpoints.sh
```bash
# kubelet 端点 (节点本地)
export KUBELET_STATS_SUMMARY="https://localhost:10250/stats/summary"
export KUBELET_METRICS_CADVISOR="https://localhost:10250/metrics/cadvisor"
export KUBELET_METRICS_RESOURCE="https://localhost:10250/metrics/resource"

# api-server 端点 (通过 service account token)
export APISERVER="https://kubernetes.default.svc.cluster.local"
export API_PODS="${APISERVER}/api/v1/pods"
export API_NODES="${APISERVER}/api/v1/nodes"
export API_PVC="${APISERVER}/api/v1/persistentvolumeclaims"
```

### 10a.3 config/k8s_field_names.sh
```bash
# 消费方约定：MUST `source` this file, NOT `bash`. 数组跨进程会丢 (见 §A)
# kubelet /stats/summary JSON 字段路径 (jq 表达式)
export FIELD_POD_NAME='.pods[].podRef.name'
export FIELD_POD_NS='.pods[].podRef.namespace'
export FIELD_POD_UID='.pods[].podRef.uid'
export FIELD_POD_CPU_USAGE='.pods[].cpu.usageNanoCores'
export FIELD_POD_MEMORY_USAGE='.pods[].memory.usageBytes'

# cgroup io.stat 字段 (v2) — 遵循 §A.3 强制 _STR 镜像约定
CGROUP_V2_IO_FIELDS=("rbytes" "wbytes" "rios" "wios" "dbytes" "dios")
export CGROUP_V2_IO_FIELDS_STR="${CGROUP_V2_IO_FIELDS[*]}"
# 跨进程消费方还原: IFS=' ' read -ra arr <<< "$CGROUP_V2_IO_FIELDS_STR"
```

### 10a.4 config/k8s_compat.sh
```bash
# 消费方约定：MUST `source` this file, NOT `bash`.
# Associative array 无法 _STR 镜像 (key/value 关系丢失) → 走 §A.4 方案 D (JSON)
# 真实文件: config/k8s_compat.json (本 .sh 仅做加载 + helper)

K8S_COMPAT_JSON="${BASH_SOURCE%/*}/k8s_compat.json"

# helper: 查询某 (version, feature) 的状态
k8s_feature_status() {
  local version="$1" feature="$2"
  jq -r --arg v "$version" --arg f "$feature" '.[$v][$f] // "unknown"' "$K8S_COMPAT_JSON"
}

detect_k8s_version() {
  kubectl version -o json 2>/dev/null | jq -r '.serverVersion.minor' | sed 's/+//'
}
```

**config/k8s_compat.json** (新增配套文件):
```json
{
  "1.27": {"dockershim": "removed", "storage_v1beta1": "removed"},
  "1.29": {"hostUsers": "alpha"},
  "1.32": {"cgroup_driver": "auto-detect"},
  "1.33": {"endpoints": "deprecated"},
  "1.34": {"apparmor": "deprecated"},
  "1.35": {"cgroup_v1": "removed"}
}
```

### 10a.5 utils/k8s_compat.sh (shim 函数层)
```bash
#!/usr/bin/env bash
source config/k8s_paths.sh
source config/k8s_compat.sh

detect_cgroup_version() {
  if [[ -f "${CGROUP_V2_ROOT}/cgroup.controllers" ]]; then
    echo "v2"
  else
    echo "v1"
  fi
}

# 统一接口：读取 Pod IO 字节
pod_io_bytes() {
  local pod_uid="$1" qos="$2"
  local version
  version=$(detect_cgroup_version)

  if [[ "$version" == "v2" ]]; then
    local path="${POD_CGROUP_SLICE_V2_TEMPLATE/\{qos\}/$qos}"
    path="${path/\{uid\}/$pod_uid}"
    awk '$2 ~ /^rbytes=/ {sub("rbytes=","",$2); r+=$2} $3 ~ /^wbytes=/ {sub("wbytes=","",$3); w+=$3} END {print r,w}' "$path/io.stat"
  else
    local path="${POD_CGROUP_SLICE_V1_TEMPLATE/\{qos\}/$qos}"
    path="${path/\{uid\}/$pod_uid}"
    awk '/Read/ {r+=$3} /Write/ {w+=$3} END {print r,w}' "$path/blkio.throttle.io_service_bytes"
  fi
}
```

---

## §10b. 云变体模板示例 — gcp_local_ssd.sh

### 10b.1 关键铁律：拒绝 Gemini 错估数字
```bash
#!/usr/bin/env bash
# GCP Local SSD 单块官方性能上限
# ─────────────────────────────────────────────────────────────
# 数据来源: cloud.google.com/compute/docs/disks/local-ssd
# 实证日期: 2026-05-19
# ─────────────────────────────────────────────────────────────
# ⚠️ 拒绝 Gemini 错估数字 (高估 2-2.4 倍):
#   ❌ 390k read IOPS  (实际 170k)
#   ❌ 170k write IOPS (实际 90k)
#   ❌ 1560 MB/s read  (实际 660 MB/s)
#   ❌ 800 MB/s write  (实际 350 MB/s)
# ─────────────────────────────────────────────────────────────

export GCP_LOCAL_SSD_READ_IOPS_PER_DISK=170000
export GCP_LOCAL_SSD_WRITE_IOPS_PER_DISK=90000
export GCP_LOCAL_SSD_READ_MBPS_PER_DISK=660
export GCP_LOCAL_SSD_WRITE_MBPS_PER_DISK=350

# 瓶颈判定函数
check_local_ssd_saturation() {
  local read_iops="$1" write_iops="$2" disk_count="$3"
  local read_cap=$((GCP_LOCAL_SSD_READ_IOPS_PER_DISK * disk_count))
  local write_cap=$((GCP_LOCAL_SSD_WRITE_IOPS_PER_DISK * disk_count))

  local read_util=$((read_iops * 100 / read_cap))
  local write_util=$((write_iops * 100 / write_cap))

  if [[ $read_util -gt 80 || $write_util -gt 80 ]]; then
    echo "WARN: Local SSD bottleneck (read=${read_util}% write=${write_util}%)"
  fi
}
```

### 10b.2 其余云变体文件 (骨架)
- `aws_ebs.sh`: 256 KiB SSD / 1024 KiB HDD 拆分逻辑
- `aws_ena.sh`: ethtool -S 字段 (bw_in_allowance_exceeded 等)
- `gcp_pd.sh`: passthrough IOPS / pd-ssd / pd-balanced / hyperdisk
- `gcp_gvnic.sh`: ethtool -S 字段 (rx_dropped 等)
- `gcp_idpf.sh`: Intel IDPF 字段 (新一代 SmartNIC)

---

## §10c. K8s 版本兼容性 shim 实现

### 10c.1 cgroup 路径切换
已在 §10a.5 utils/k8s_compat.sh 实现 `detect_cgroup_version` + `pod_io_bytes`。

### 10c.2 API 字段切换
```bash
# K8s 1.33 起 EndpointSlices 替代 Endpoints
get_service_endpoints() {
  local svc="$1" ns="$2"
  local k8s_minor
  k8s_minor=$(detect_k8s_version)

  if [[ $k8s_minor -ge 33 ]]; then
    kubectl get endpointslices -n "$ns" -l "kubernetes.io/service-name=$svc" -o json
  else
    kubectl get endpoints "$svc" -n "$ns" -o json
  fi
}
```

### 10c.3 验收：双 cgroup 版本通过
- kind v1.30 (cgroup v1): `pod_io_bytes` 走 blkio.throttle.io_service_bytes
- kind v1.35 (cgroup v2): `pod_io_bytes` 走 io.stat

---

## §11. 执行检查清单 (开工前)

- [ ] 用户已确认 plan
- [ ] tag `pre-stage1-redesign` 已打
- [ ] cloudtop 端 `bash -x` baseline 已跑通
- [ ] kind v1.30 + v1.35 集群已就绪
- [ ] subagent 并发上限 = 3
- [ ] CI guard pre-commit hook 已安装
- [ ] 每阶段完成后跑 `bash ci/check_parallel_entry.sh`
- [ ] 自评"完成"前必跑端到端 bash -x 实证主流程走新代码
- [ ] 不在 utils/ 留新入口文件 (用 config/ + wrapper symlink)

---

## §12. 不变量 (永不违反)

1. **主链路唯一**: `monitoring/unified_monitor.sh` 是唯一入口，CI guard 强制
2. **R0 铁律**: 硬件性能数字必须官方文档实证，注释写明 URL + 日期
3. **AWS vs GCP IO 计量**: AWS 拆分 256K/1024K，GCP 不拆，必须分别实现
4. **K8s GA API 永不删**: 优先用 GA API (K3/K4/K5)，半 GA 谨慎用
5. **cgroup 路径不能硬编码**: 必须走 `${HOST_SYS}` env + shim 函数
6. **8 链对称**: 每个新功能必须 8 链均通过验收
7. **fail-soft**: 探测失败 → 降级 → 警告 → 继续，不阻断 benchmark
8. **自评禁令**: 完成报告必须用证据式（命令 + 输出 + diff），禁用"应该 / 大概 / 估计"

---

## §13. 完成报告模板 (S1-S12 每阶段必填)

### 模板
```markdown
# S{N} 完成报告

## 1. 实证 (主流程走新代码)
$ bash -x monitoring/unified_monitor.sh 2>&1 | grep <new_code_marker>
<期望输出>

## 2. CI guard
$ bash ci/check_parallel_entry.sh
PASS

## 3. 验收命令输出
<S{N} 验收命令的 stdout/stderr>

## 4. diff stat
$ git diff --stat HEAD~1
<具体改了哪些文件 + 行数>

## 5. 已知缺陷 / TODO
<必须诚实列出, 不可"看起来都好">
```

---

## §14. 历史决策 (12 个 resolved)

| # | 时间 | 决策 | 选择 |
|---|---|---|---|
| 1 | 早班 | DEPLOYMENT_MODE 默认 | vm_bare (b) |
| 2 | 早班 | skill 升级时机 | 并行 (a) |
| 3 | 早班 | revert 时机 | 写完 plan 后 (a) |
| 4 | 早班 | 执行监督 | 全程在场 (a) |
| 5 | 今天 | K8s 版本范围 | B 务实 1.27-1.35 |
| 6 | 今天 | K8s API 配置化 | β 5 分组 |
| 7-12 | 早班 | (39 项清单详见早班讨论) | 全部 resolved |

---

## §15. 后续 (post-redesign roadmap)

- v2.0: VM 双天花板 (vm-level IOPS/throughput cap)，目前留 config hook
- v2.1: Kafka / message-queue 监控
- v2.2: 上链业务级 metrics (slot lag, peer count)
- v2.3: Azure VM 支持 (低优先, 客户需求小)
- v3.0: eBPF-based 网络监控 (Cilium Hubble 集成)

---

## §17. RPC Method 级资源归因监控 (L7 透明代理方案 D)

> **状态**：用户已确认 YYYY，纳入主 plan v1.2。
> **目标**：8 链全覆盖 per-method 资源消耗监控，零新二进制依赖，5k QPS benchmark 量级够用。
> **方案**：L7 透明代理 + cgroup 时间窗口 join + 节点客户端 Prometheus 兜底（三层）。

### §17.1 设计动机：为什么不用现有 Prometheus

研究素材：`analysis-notes/research_notes/01-evm-rpc-resource.md`、`02-solana-sui-aptos-rpc-resource.md`、`03-bitcoin-starknet-rpc-resource.md`

8 链 per-method metric 暴露能力实证对比：

| 链 | 客户端 | per-method metric? | 缺口 |
|----|--------|---------------------|------|
| Ethereum | Geth | ❌ 仅聚合 `rpc/requests` `rpc/duration/all` | 高 |
| Ethereum | Erigon | ⚠️ 源码内有但官方文档不枚举 | 中 |
| Ethereum | Nethermind | ⚠️ 通用计数器 `nethermind_jsonrpc_requests` 无 method label | 中 |
| BSC | bsc-geth | ❌ 同 Geth | 高 |
| Base | op-geth | ❌ 同 Geth | 高 |
| Solana | agave-validator | ✅ `rpc_service`, `rpc_request_time` | 低 |
| Sui | sui-node | ✅ `json_rpc_request_latency_seconds` | 低 |
| Aptos | aptos-node | ✅ `aptos_api_*` | 低 |
| Bitcoin | bitcoin-core | ❌ 原生零 metric，仅 jvstein 社区 exporter（无 method 维度） | 极高 |
| Starknet | Pathfinder | ✅ `rpc_method_calls_total{method=...}` | 低 |
| Starknet | Juno | ✅ `juno_rpc_requests{method=...}` | 低 |

**结论**：6/11 客户端无可用 per-method metric → 必须自建数据源。

### §17.2 三层架构

```
Client (benchmark)
   │ HTTP/JSON-RPC
   ▼
┌─────────────────────────────────────────────┐
│ Layer 1: L7 RPC Proxy (Python ~200 LOC)     │ ← 主数据源（所有链通用）
│   - 解析 JSON-RPC method 字段                │
│   - 记录 (timestamp, method, latency, size)  │
│   - 透传到 Layer 3                           │
│   - 输出: /tmp/rpc_proxy.log (line per req)  │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│ Layer 2: cgroup 时间窗口 Join                │ ← 资源归因
│   - 每秒采样 cgroup v2 io.stat / cpu.stat    │
│   - per-second bucket: 该秒内所有 method 列表│
│   - join: method × cgroup metric             │
│   - 输出: per_method_resource.csv             │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│ Layer 3: Node Client (Solana/Sui/etc.)      │ ← 兜底校验
│   - 若客户端暴露 per-method metric           │
│   - 与 Layer 1 计数对账 (差异 <5% 算合格)    │
└─────────────────────────────────────────────┘
```

### §17.3 L7 代理实现规格 (`tools/rpc_proxy.py`)

**约束**：
- Python stdlib only（无 Envoy/nginx/HAProxy 新依赖）
- 单文件 ~200 行，asyncio + aiohttp（aiohttp 项目已用过，非新依赖）
- 性能预算：5k QPS @ <1ms p99 added latency（benchmark 量级够用，生产请用 Envoy）

**核心数据结构**：
```python
# 每请求一行 JSON：
{
  "ts": 1730000000.123,     # 请求开始时间 (epoch float)
  "ts_end": 1730000000.145, # 请求完成时间
  "method": "eth_call",      # 解析自 JSON-RPC body.method
  "params_hash": "a1b2c3",   # SHA256(params) 前 6 位，匿名分桶
  "req_bytes": 245,          # 请求字节
  "resp_bytes": 1024,        # 响应字节
  "status": 200,             # HTTP status
  "rpc_error": null          # JSON-RPC error.code (若有)
}
```

**输出文件**：`/tmp/rpc_proxy/<date>/<chain>.jsonl`，按日 rotate。

**关键算法**（method 解析）：
```python
async def parse_method(body: bytes) -> str:
    try:
        j = json.loads(body)
        # 单请求
        if isinstance(j, dict):
            return j.get("method", "unknown")
        # batch 请求：返回逗号拼接 (后续 join 时按权重拆分)
        if isinstance(j, list):
            return ",".join(req.get("method", "unknown") for req in j)
    except Exception:
        return "parse_error"
```

**REST API 链特殊处理（Aptos）**：
Aptos 走 REST 而非 JSON-RPC，method 解析改为 URL 路径模板化：
```python
# /accounts/0xabc.../resource/0x1::coin::CoinStore → "GET /accounts/{addr}/resource/{type}"
```
URL 路径模板列表在 `config/chains/aptos.json` 的 `rest_paths` 字段定义。

### §17.4 cgroup 时间窗口 Join 算法

**前提**：节点进程跑在已知 cgroup 路径下（K8s pod 自动满足，非 K8s 需在 systemd unit 显式声明）。

**采样**（已在 §10a 框架内，复用）：
- 每 1s 读 `/sys/fs/cgroup/<path>/io.stat` 6 字段（rbytes/wbytes/rios/wios/dbytes/dios）
- 每 1s 读 `/sys/fs/cgroup/<path>/cpu.stat`（usage_usec）
- 输出 `cgroup_metrics.csv`，每秒一行

**Join 逻辑**（`tools/rpc_method_join.py`，~100 LOC）：
```python
# 输入：rpc_proxy.jsonl + cgroup_metrics.csv
# 输出：per_method_resource.csv
#
# 算法（每秒桶）：
#   bucket_rpcs = [r for r in rpc_log if int(r.ts) == sec]
#   bucket_methods = Counter(r.method for r in bucket_rpcs)
#   for method, count in bucket_methods.items():
#       weight = count / sum(bucket_methods.values())
#       method_io_bytes += cgroup.iobytes[sec] * weight
#       method_cpu_usec += cgroup.cpu[sec] * weight
```

**精度声明**：
- 这是**统计归因**而非**因果追踪**——同一秒多个 method 时按调用次数加权分摊
- 适用场景：mixed 模式下识别"哪类 method 是资源主导"
- **不适用**：单笔请求归因（需要 eBPF level，已超出 200 LOC 预算，纳入 §15 post-redesign roadmap）
- 误差预期：稳态下 ±10%；burst 场景下 ±30%（与 §17.5 兜底层对账）

### §17.5 节点客户端 Prometheus 兜底（5/11 客户端可用）

对 Solana/Sui/Aptos/Pathfinder/Juno 这 5 个暴露 per-method metric 的客户端：

1. 启动 benchmark 前抓取 baseline metric
2. 结束后再抓一次，diff 得到 per-method 调用次数
3. 与 L7 代理统计的 `method count` 对账
4. 差异 < 5% 算合格；> 5% 触发告警（可能 L7 代理漏请求或客户端有内部 RPC）

**对账脚本**：`tools/rpc_count_reconcile.py`，~50 LOC。

对 Ethereum/BSC/Base/Bitcoin 这 4 个无 per-method metric 的链：
- 跳过 Layer 3，只用 Layer 1+2 数据
- 在报告中显式标注"无客户端校验，仅代理数据"

### §17.6 chain-as-plugin 集成点

L7 代理的链特定配置全部从 `config/chains/<chain>.json` 读取：
```json
{
  "rpc_protocol": "json-rpc",       // 或 "rest"
  "rpc_endpoint": "http://localhost:8545",
  "proxy_listen": "127.0.0.1:18545",
  "rest_paths": [...],              // 仅 protocol=rest 时
  "method_aliases": { ... }         // 别名归一（如 net_version → eth_chainId 同桶）
}
```

启动命令：`tools/rpc_proxy.py --chain ethereum`，配置自动加载。详见 §18。

### §17.7 工时

- L7 代理 (Python ~200 LOC + asyncio): 4h
- cgroup join 算法 + CSV 输出: 2h
- per-method 报告生成 + 兜底对账: 2h
- 8 链 e2e 测试: 2h
- **小计：10h**

### §17.8 失败模式与降级

| 故障 | 降级行为 |
|------|----------|
| L7 代理崩溃 | benchmark 仍可直连节点（proxy URL 是可选 hop） |
| cgroup 路径不可读 | 跳过 join，只输出 RPC 调用统计（无资源归因） |
| 5k QPS 超载 | 自动开启采样模式（1/10 请求），日志显式标注 |
| JSON 解析失败 | 计入 `parse_error` 桶，不阻塞透传 |

---

## §18. Chain-as-Plugin 重构（用户称"特别完美"，采纳）

> **状态**：用户已确认 YYYY，纳入主 plan v1.2。
> **目标**：加新链零代码改动；私有链/客户定制走 `chains.d/` 不污染主仓库。
> **核心**：把现有 `config/config_loader.sh` heredoc 中心化的 8 链定义拆为 `config/chains/<chain>.json` 一链一文件。

### §18.1 现状问题（实证）

`config/config_loader.sh` 现状（baseline `15441ad` 实测）：

| 位置 | 内容 | 加新链需改 |
|------|------|-------------|
| L23 | `BLOCKCHAIN_PROCESS_NAMES=(...)` indexed array | ✅ 加进程名 |
| L40 | `RPC_MODE="single"` 全局默认 | ✅ 若需新 mode |
| L331 | `case "$BLOCKCHAIN_NAME"` switch | ✅ 加 case 分支 |
| L362 | `UNIFIED_BLOCKCHAIN_CONFIG=$(cat <<EOF ... 8 链大 JSON ... EOF)` | ✅ 加 JSON 节点 |
| L826 | `_STR` 镜像导出 | ✅ 加镜像行 |

**结论**：加新链需改 5 处，3 个文件 → 高度容易遗漏、易并入冲突、私有链强制污染主仓库。

### §18.2 新架构

```
config/
├── chains/                          ← 内置 8 链（每链一 JSON）
│   ├── _schema.json                 ← jq 校验 schema
│   ├── ethereum.json
│   ├── bsc.json
│   ├── base.json
│   ├── solana.json
│   ├── sui.json
│   ├── aptos.json
│   ├── bitcoin.json
│   └── starknet.json
├── chains.d/                        ← 用户/私有链覆盖（gitignored）
│   ├── README.md                    ← "把私有链 JSON 放这里"
│   └── (空，用户填)
└── config_loader.sh                 ← 改 30 行调度逻辑
```

### §18.3 单链 JSON Schema（`config/chains/_schema.json`）

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Chain Definition v1",
  "type": "object",
  "required": ["name", "version", "process", "rpc"],
  "properties": {
    "name": { "type": "string", "pattern": "^[a-z][a-z0-9_]*$" },
    "version": { "type": "string", "const": "1.0" },

    "process": {
      "type": "object",
      "required": ["names"],
      "properties": {
        "names": { "type": "array", "items": { "type": "string" } },
        "cgroup_path_hint": { "type": "string" }
      }
    },

    "rpc": {
      "type": "object",
      "required": ["protocol", "endpoint", "methods"],
      "properties": {
        "protocol": { "enum": ["json-rpc", "rest"] },
        "endpoint": { "type": "string" },
        "proxy_listen": { "type": "string" },
        "methods": {
          "type": "object",
          "required": ["single", "mixed"],
          "properties": {
            "single": { "type": "string" },
            "mixed": {
              "type": "object",
              "patternProperties": {
                "^[a-zA-Z_][a-zA-Z0-9_]*$": {
                  "type": "number",
                  "minimum": 0.0,
                  "maximum": 1.0
                }
              }
            }
          }
        },
        "rest_paths": { "type": "array" },
        "method_aliases": { "type": "object" }
      }
    },

    "metrics": {
      "type": "object",
      "properties": {
        "prometheus_endpoint": { "type": "string" },
        "per_method_supported": { "type": "boolean" },
        "metric_name_template": { "type": "string" }
      }
    }
  }
}
```

**校验时机**：`config_loader.sh` 加载每个 chain JSON 前用 `jq` 跑 schema 校验，失败立即报错退出。详见 §18.5。

### §18.4 示例：`config/chains/ethereum.json`

```json
{
  "name": "ethereum",
  "version": "1.0",
  "process": {
    "names": ["geth", "erigon", "nethermind"],
    "cgroup_path_hint": "/sys/fs/cgroup/system.slice/geth.service"
  },
  "rpc": {
    "protocol": "json-rpc",
    "endpoint": "http://localhost:8545",
    "proxy_listen": "127.0.0.1:18545",
    "methods": {
      "single": "eth_blockNumber",
      "mixed": {
        "eth_call": 0.45,
        "eth_blockNumber": 0.20,
        "eth_getBlockByNumber": 0.10,
        "eth_getBalance": 0.08,
        "eth_getLogs": 0.05,
        "eth_chainId": 0.05,
        "eth_getTransactionReceipt": 0.04,
        "eth_getTransactionByHash": 0.03
      }
    },
    "method_aliases": {
      "net_version": "eth_chainId"
    }
  },
  "metrics": {
    "prometheus_endpoint": "http://localhost:6060/debug/metrics/prometheus",
    "per_method_supported": false,
    "metric_name_template": "rpc/requests"
  }
}
```

(其余 7 链 JSON 在 S8 阶段一并落地，权重默认值见 §19。)

### §18.5 `config_loader.sh` 30 行调度逻辑

替换原 L331 `case` + L362 heredoc，新逻辑：

```bash
# §18 chain-as-plugin loader (~30 LOC)
CHAIN_NAME="${BLOCKCHAIN_NAME:-ethereum}"

# 1. 优先级：chains.d/ 覆盖 chains/
if [[ -f "${CONFIG_DIR}/chains.d/${CHAIN_NAME}.json" ]]; then
    CHAIN_JSON="${CONFIG_DIR}/chains.d/${CHAIN_NAME}.json"
    log_info "Loading user override: ${CHAIN_JSON}"
elif [[ -f "${CONFIG_DIR}/chains/${CHAIN_NAME}.json" ]]; then
    CHAIN_JSON="${CONFIG_DIR}/chains/${CHAIN_NAME}.json"
else
    log_error "Unknown chain: ${CHAIN_NAME} (no JSON in chains/ or chains.d/)"
    exit 1
fi

# 2. Schema 校验（jq 实现，零新依赖；项目已有 jq）
if ! jq --argfile schema "${CONFIG_DIR}/chains/_schema.json" \
       'if (. | type) == "object" then . else error("not object") end' \
       "${CHAIN_JSON}" > /dev/null; then
    log_error "Chain JSON schema invalid: ${CHAIN_JSON}"
    exit 1
fi

# 3. 字段提取（jq 一次性导出环境变量）
export BLOCKCHAIN_PROCESS_NAMES_STR="$(jq -r '.process.names | join(" ")' "${CHAIN_JSON}")"
export RPC_PROTOCOL="$(jq -r '.rpc.protocol' "${CHAIN_JSON}")"
export RPC_ENDPOINT="$(jq -r '.rpc.endpoint' "${CHAIN_JSON}")"
export RPC_PROXY_LISTEN="$(jq -r '.rpc.proxy_listen // empty' "${CHAIN_JSON}")"
export RPC_SINGLE_METHOD="$(jq -r '.rpc.methods.single' "${CHAIN_JSON}")"
export RPC_MIXED_METHODS_JSON="$(jq -c '.rpc.methods.mixed' "${CHAIN_JSON}")"
export PROMETHEUS_ENDPOINT="$(jq -r '.metrics.prometheus_endpoint // empty' "${CHAIN_JSON}")"
export PER_METHOD_SUPPORTED="$(jq -r '.metrics.per_method_supported // false' "${CHAIN_JSON}")"

# 4. 兼容 §A._STR 镜像约定（indexed array 形式给消费者）
read -r -a BLOCKCHAIN_PROCESS_NAMES <<< "${BLOCKCHAIN_PROCESS_NAMES_STR}"
```

### §18.6 加新链流程（用户体验）

加 Sei（不在内置 8 链）：

1. 用户创建 `config/chains.d/sei.json`（拷贝 ethereum.json 改值）
2. `jq . config/chains.d/sei.json` 自检 JSON 合法
3. `BLOCKCHAIN_NAME=sei ./benchmark.sh` 直接跑
4. **零代码改动，零主仓库 PR**

私有链亦同——`chains.d/` 已 gitignored。

### §18.7 §A 数组铁律遵循点

- `BLOCKCHAIN_PROCESS_NAMES` 通过 `_STR` 镜像跨进程（jq -r '... | join(" ")' 落地）
- `RPC_MIXED_METHODS_JSON` 走 JSON 文件方案 D（associative array 转 JSON 字符串）
- 所有跨子进程变量先 export 后用 → 与 §A.3 表对齐

### §18.8 工时

- `_schema.json` 设计 + jq 校验逻辑: 1h
- 8 链 JSON 拆分 + 内容迁移: 2h
- `config_loader.sh` 30 行重构: 1h
- `chains.d/` README + 加新链文档: 0.5h
- e2e 测试（每链跑一次 single + mixed）: 2.5h
- **小计：7h**（原估 3h，因含 8 链迁移上调）

---

## §19. Mixed 模式权重配比 Schema + 默认值

> **状态**：用户已确认 YYYY，纳入主 plan v1.2。
> **目标**：开箱即用的行业平均权重；客户可在 `chains.d/<chain>.json` 完全覆盖。

### §19.1 设计原则

1. **默认值非"科学精确"**：subagent 调研发现 Helius/Alchemy/Cloudflare 等均未公开精确百分比报表。默认值是基于公开排序 + 社区经验 + 反直觉发现的**合理近似**，不应当作 ground truth。
2. **默认值在 chains/*.json 内**：用户改私有配置走 `chains.d/`，主仓库不污染
3. **Schema 强约束**：权重和必须 ≈ 1.0（±0.01 容差），单值 0.0–1.0
4. **method_aliases 归一化**：流量等价的不同 method 合并到同一桶（如 `net_version` → `eth_chainId`）
5. **诚实标注**：每个权重值在 JSON 注释（`_comment` 字段）说明来源

### §19.2 Schema 增强（在 §18.3 基础上）

```json
"mixed": {
  "type": "object",
  "additionalProperties": {
    "type": "number",
    "minimum": 0.0,
    "maximum": 1.0
  },
  "minProperties": 3
}
```

加权和校验在 `config_loader.sh` 加载后跑：
```bash
total=$(echo "${RPC_MIXED_METHODS_JSON}" | jq '[.[]] | add')
diff=$(awk "BEGIN { print ($total - 1.0 < 0) ? -($total - 1.0) : ($total - 1.0) }")
if awk "BEGIN { exit !($diff > 0.01) }"; then
    log_error "Mixed method weights must sum to 1.0 (±0.01), got ${total}"
    exit 1
fi
```

### §19.3 8 链默认权重（基于 research_notes/）

来源：`analysis-notes/research_notes/01-evm-rpc-resource.md` Cloudflare 排序 + reddit 经验值

#### Ethereum / BSC / Base (EVM 同源)
```json
"mixed": {
  "eth_call": 0.45,
  "eth_blockNumber": 0.20,
  "eth_getBlockByNumber": 0.10,
  "eth_getBalance": 0.08,
  "eth_getLogs": 0.05,
  "eth_chainId": 0.05,
  "eth_getTransactionReceipt": 0.04,
  "eth_getTransactionByHash": 0.03
}
```
依据：Cloudflare ETH Gateway Top 10 排序 + Infura 用户自报"eth_call 占大头"。
覆盖了从轻量 (eth_blockNumber/eth_chainId) 到重量 (eth_getLogs) 的资源分布。

#### Solana (来源 02-solana-sui-aptos-rpc-resource.md)
```json
"mixed": {
  "getAccountInfo": 0.35,
  "getBalance": 0.15,
  "sendTransaction": 0.15,
  "getMultipleAccounts": 0.10,
  "getSlot": 0.10,
  "getBlock": 0.05,
  "getTransaction": 0.05,
  "getSignaturesForAddress": 0.03,
  "simulateTransaction": 0.02
}
```
依据：Helius 公开"getAccountInfo + sendTransaction 合占 60-70%"定性数据。**故意未包含 getProgramAccounts**（已知节点杀手，用户若要测请走 single 模式）。

#### Sui
```json
"mixed": {
  "sui_getObject": 0.30,
  "sui_multiGetObjects": 0.20,
  "sui_getTransactionBlock": 0.15,
  "sui_getOwnedObjects": 0.10,
  "suix_getBalance": 0.10,
  "sui_queryTransactionBlocks": 0.05,
  "sui_getLatestCheckpointSequenceNumber": 0.05,
  "suix_queryEvents": 0.05
}
```
依据：Mysten 公共 fullnode "sui_getObject + multiGetObjects ~50%" 定性。

#### Aptos (REST API)
```json
"mixed": {
  "GET /accounts/{addr}": 0.30,
  "GET /accounts/{addr}/resource/{type}": 0.20,
  "GET /transactions/by_hash/{hash}": 0.15,
  "GET /blocks/by_height/{h}": 0.10,
  "POST /transactions/simulate": 0.10,
  "GET /transactions/by_version/{ver}": 0.05,
  "GET /events/by_handle/{handle}": 0.05,
  "GET /info": 0.05
}
```
依据：Aptos Labs indexer 流量 > fullnode 的间接推断（fullnode 实际占比较低，但本表针对 fullnode benchmark 场景）。

#### Bitcoin
```json
"mixed": {
  "getblockchaininfo": 0.30,
  "getrawtransaction": 0.20,
  "getblock": 0.15,
  "getblockhash": 0.10,
  "gettxout": 0.10,
  "getmempoolentry": 0.05,
  "estimatesmartfee": 0.05,
  "getrawmempool": 0.05
}
```
依据：**未找到公开权重数据**（research_notes/03 显式标注 not found）。基于钱包/explorer 常见调用模式的工程估算，**建议用户自行用 chains.d/ 覆盖**。**故意未包含 scantxoutset**（资源杀手，single 模式专测）。

#### Starknet
```json
"mixed": {
  "starknet_call": 0.30,
  "starknet_estimateFee": 0.20,
  "starknet_getTransactionReceipt": 0.15,
  "starknet_blockNumber": 0.10,
  "starknet_getBlockWithTxs": 0.10,
  "starknet_getStorageAt": 0.05,
  "starknet_getTransactionByHash": 0.05,
  "starknet_chainId": 0.05
}
```
依据：subagent 间接推断"钱包/浏览器场景 starknet_call/estimateFee/getTransactionReceipt 占比最高"。

### §19.4 客户覆盖示例

客户运行 prod 流量分析得出自己的真实权重，放 `config/chains.d/ethereum.json`：
```json
{
  "name": "ethereum",
  "version": "1.0",
  "process": { "names": ["geth"] },
  "rpc": {
    "protocol": "json-rpc",
    "endpoint": "http://prod-node:8545",
    "methods": {
      "single": "eth_call",
      "mixed": {
        "eth_call": 0.70,
        "eth_getLogs": 0.20,
        "eth_blockNumber": 0.05,
        "eth_chainId": 0.05
      }
    }
  },
  "metrics": { "prometheus_endpoint": "http://prod-node:6060/debug/metrics/prometheus" }
}
```
完全覆盖默认值，schema 校验通过即生效。

### §19.5 工时

- 权重 schema 加强 + 加权和校验逻辑: 0.5h
- 8 链默认权重 JSON 填充 + _comment 标注来源: 1.5h
- 用户文档（`chains.d/README.md` + 覆盖示例）: 0.5h
- e2e 测试（8 链各跑一次 mixed 看代理日志命中率）: 1.5h
- **小计：4h**（原估 2h，因含 8 链权重表 + 文档上调）

---

## §20. RPC 参数构造扩展 (chain-as-plugin 友好 + 池采样)

> **设计起源**：v1.2 §17 完成 RPC method 级监控后，§18 完成 chain-as-plugin 重构，§19 完成 mixed 权重配比；但 baseline `target_generator.sh:67-124` 的 7 种 `param_format` 只覆盖单 address 类参数（`single_address` / `address_latest` / `address_storage_latest` 等），无法构造 `eth_getLogs` 的 `{fromBlock, toBlock, address, topics}`、`eth_call` 的 calldata、Solana `getProgramAccounts` 的 filters、Starknet `getEvents` 的二维 keys 等复杂参数。
>
> **用户洞察 (2026-05-19)**：
> 1. 参数策略必须 **chain-as-plugin 友好** — 加新链不能再写 Python 硬编码，否则违反 §18 零代码承诺
> 2. 参数池必须 **贴合生产** — 单点常量地址会被节点缓存命中，必须有池 + 采样
> 3. 应**复用 baseline 现有 case-dispatch 模式**，不要重写 — baseline 已有 `CHAIN_CONFIG` JSON 注入 + 4 链 `BlockchainAdapter` + 7 种 `param_format`，只需扩展 case 分支
>
> **澄清 (2026-05-19)**：不需要 snapshot 锁 anchor block，"近期数据"即可 — 各 fixture 池独立抓取最近 N 块，时间漂移在小时-天级可接受。

### §20.1 现状审计（5 项实证发现）

| 现有能力 | 位置 | 状态 |
|---|---|---|
| `CHAIN_CONFIG` JSON 环境变量统一注入 | `fetch_active_accounts.py:65` | ✅ 已就位 |
| BlockchainAdapter 基类 + 4 链 adapter (Solana/Eth/Starknet/Sui) | `fetch_active_accounts.py:156-660` | ✅ 已就位 |
| 7 种 `param_format` 枚举 | `target_generator.sh:77-109` | ✅ 已就位 |
| `param_formats` per-method 映射在 chain config JSON 里 | `config_loader.sh:392/423/...` (8 链全有) | ✅ 已就位 |
| `get_param_format_from_json` 从 CHAIN_CONFIG 读取 | `config_loader.sh:775-810` | ✅ 已就位 |
| **多类型 fixture 池**（仅有 address 池） | `target_generator.sh:134` ACCOUNTS_OUTPUT_FILE | ❌ **缺失** |
| **复杂参数 template 化** | `case` 硬编码 7 类 | ❌ **缺失** |
| **采样策略 + 安全护栏** | 顺序读 file | ❌ **缺失** |

**结论**：baseline 已经做了大半工作，**v1.3 是增量扩展不是重写**。

### §20.2 新增 param_format 列表（共 15 个，覆盖 8 链）

#### EVM 系（10 个）
| 名称 | 适用方法 | 参数模板 |
|---|---|---|
| `address_block_range` | `eth_getLogs` | `[{address, fromBlock, toBlock}]` |
| `topic_block_range` | `eth_getLogs` | `[{address, fromBlock, toBlock, topics:[Transfer]}]` |
| `multi_topic_filter` | `eth_getLogs` | `[{address, fromBlock, toBlock, topics:[t0, null, [t2a,t2b]]}]` |
| `block_hash_logs` | `eth_getLogs` | `[{blockHash}]`（避开 range 限制） |
| `call_balanceof` | `eth_call` | `[{to, data:0x70a08231+pad32(holder)}, "latest"]` |
| `call_slot0` | `eth_call` | `[{to:univ3_pool, data:0x3850c7bd}, "latest"]` |
| `call_with_state_override` | `eth_call` | `[{...}, "latest", {addr:{balance:"0x..."}}]` |
| `fee_history_window` | `eth_feeHistory` | `[blockCount, "latest", percentiles]` |
| `block_full_tx` | `eth_getBlockByNumber` | `[blockNum, true]` |
| `historical_balance` | `eth_getBalance` | `[addr, archive_block]`（强制 archive 路径） |

#### Solana（3 个）
| 名称 | 适用方法 | 参数模板 |
|---|---|---|
| `program_accounts_filtered` | `getProgramAccounts` | `[pid, {filters:[{dataSize}, {memcmp}], encoding:"base64", dataSlice}]` |
| `multi_accounts_batch` | `getMultipleAccounts` | `[[pk1...pkN≤100], {encoding:"base64", dataSlice}]` |
| `signatures_for_address` | `getSignaturesForAddress` | `[addr, {limit≤1000, before, until, commitment}]` |

#### Starknet（2 个）
| 名称 | 适用方法 | 参数模板 |
|---|---|---|
| `events_2d_keys` | `starknet_getEvents` | `[{filter:{from_block, to_block, address, keys:[[k0a,k0b], [k1]], chunk_size≤100}}]` |
| `call_selector` | `starknet_call` | `[{contract_address, entry_point_selector, calldata}, "latest"]` |

> **Sui / Aptos / Bitcoin**：v1.3 baseline 阶段不引入复杂 fixture 池，由 chain config JSON 内的 `params` 直接给固定值，留 v1.4+ 扩展。

### §20.3 case-dispatch 扩展模板（追加到 target_generator.sh:124 之后）

**关键约束**：纯 shell + jq，零新依赖；`get_tip_block` 启动时缓存 12s 写 `/tmp/.tip_cache.$$`。

```bash
case "$param_format" in
  # ============ 现有 7 种（保留不动）============
  single_address) ... ;;
  address_latest) ... ;;
  # ...

  # ============ v1.3 新增 ============
  address_block_range)
    addr=$(shuf -n1 "$ADDR_POOL")
    tip=$(get_tip_block)
    range=${SAFETY_MAX_BLOCK_RANGE:-1024}
    from=$((tip - range))
    jq -nc --arg a "$addr" \
           --arg f "$(printf '0x%x' $from)" \
           --arg t "$(printf '0x%x' $tip)" \
       '[{address:$a, fromBlock:$f, toBlock:$t}]'
    ;;

  topic_block_range)
    addr=$(shuf -n1 "$TOKEN_POOL")
    tip=$(get_tip_block); range=${SAFETY_MAX_BLOCK_RANGE:-1024}
    from=$((tip - range))
    jq -nc --arg a "$addr" \
           --arg f "$(printf '0x%x' $from)" \
           --arg t "$(printf '0x%x' $tip)" \
       '[{address:$a, fromBlock:$f, toBlock:$t,
          topics:["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"]}]'
    ;;

  call_balanceof)
    token=$(shuf -n1 "$TOKEN_POOL")
    holder=$(shuf -n1 "$ADDR_POOL")
    pad(){ printf '%064s' "${1#0x}" | tr ' ' 0; }
    data="0x70a08231$(pad $holder)"
    jq -nc --arg to "$token" --arg d "$data" \
       '[{to:$to,data:$d},"latest"]'
    ;;

  program_accounts_filtered)
    pid=$(shuf -n1 "$PROGRAM_POOL")
    mint=$(shuf -n1 "$TOKEN_MINT_POOL")
    jq -nc --arg pid "$pid" --arg mc "$mint" \
       '[$pid, {commitment:"confirmed", encoding:"base64",
                dataSlice:{offset:0,length:0},
                filters:[{dataSize:165},
                         {memcmp:{offset:0, bytes:$mc, encoding:"base58"}}]}]'
    ;;

  events_2d_keys)
    contract=$(shuf -n1 "$STARKNET_CONTRACT_POOL")
    key0=$(shuf -n1 "$STARKNET_EVENT_KEY_POOL")
    tip=$(get_tip_block)
    range=${STARKNET_GETEVENTS_BLOCK_RANGE_MAX:-1024}
    from=$((tip - range))
    jq -nc --arg c "$contract" --arg k "$key0" \
           --argjson f $from --argjson t $tip \
       '[{filter:{from_block:{block_number:$f}, to_block:{block_number:$t},
                  address:$c, keys:[[$k]], chunk_size:100}}]'
    ;;

  # ... 其余 10 个 case 见 research_notes/04 + 05
esac
```

完整 15 个 case 实现参考 `analysis-notes/research_notes/04-evm-complex-params.md §6.2` + `05-multichain-complex-params.md §5.1`。

### §20.4 chain config JSON schema 扩展（chains/<chain>.json）

**保持 chain-as-plugin 承诺**：所有参数生产细节由 JSON 描述，shell 只解析不硬编码新链规则。

```json
{
  "chain": "ethereum",
  "methods": {
    "eth_getLogs": {
      "param_format": "topic_block_range",
      "pools": {
        "address": "TOKEN_POOL",
        "topic": "topics_logs"
      },
      "safety": {
        "max_block_range": 1024,
        "max_response_size_mb": 10
      }
    },
    "eth_call": {
      "param_format": "call_balanceof",
      "pools": {
        "to": "TOKEN_POOL",
        "from": "ADDR_POOL"
      },
      "safety": {
        "max_gas": 50000000,
        "timeout_ms": 5000
      }
    },
    "debug_traceTransaction": {
      "param_format": "trace_tx_calltracer",
      "pools": { "tx_hash": "TX_HASH_POOL" },
      "safety": { "enabled": false }
    }
  },
  "pool_files": {
    "ADDR_POOL":           "fixtures/ethereum/addresses_hot.txt",
    "TOKEN_POOL":          "fixtures/ethereum/contracts_erc20.json",
    "TX_HASH_POOL":        "fixtures/ethereum/tx_hashes.txt",
    "topics_logs":         "fixtures/ethereum/topics_logs.json"
  }
}
```

加新链（如 Aptos）只需写一份 `chains/aptos.json` + 落 `fixtures/aptos/*` 数据文件，**不改任何 .sh / .py 代码**。

### §20.5 工时

- 扩展 7→22 个 case 实现（含 8 链分支） + jq 渲染器: 3h
- chain config JSON schema 升级（增 `pools` + `safety` 字段） + jq 校验 hook: 2h
- 8 链 chains/*.json 填默认值 + _comment 标注来源: 1h
- **小计：S11 = 6h**

---

## §21. Fixtures 池规范（fixtures/ + fixtures.d/ 双层架构）

### §21.1 双层架构

```
blockchain-node-benchmark/
├── fixtures/                     # 入 repo, baseline 池 (CI / 冒烟用)
│   ├── ethereum/
│   │   ├── addresses_hot.txt     # 50 条
│   │   ├── addresses_cold.txt    # 100 条
│   │   ├── tx_hashes.txt         # 100 条
│   │   ├── blocks_range.json     # 区段 + 20 离散
│   │   ├── contracts_erc20.json  # 10 主流 token
│   │   ├── topics_logs.json      # 5 个 event sig
│   │   └── manifest.json         # 抓取元数据
│   ├── solana/
│   │   ├── addresses_hot.txt     # 50 pubkey
│   │   ├── signatures.txt        # 100 sig
│   │   ├── slots_range.json
│   │   ├── programs.json         # 10 (Token/Memo/Serum/Raydium/...)
│   │   ├── token_mints.json
│   │   └── manifest.json
│   └── ... (8 链全有)
└── fixtures.d/                   # gitignored, 用户大池 (真实压测用)
    ├── ethereum/
    │   ├── addresses_hot.txt     # 10 000+
    │   ├── tx_hashes.txt         # 50 000+
    │   └── ...
    └── ...
```

`.gitignore` 加 `fixtures.d/`。runner 启动时优先 `fixtures.d/<chain>/` 同名文件，缺失则回退 `fixtures/<chain>/`。

### §21.2 推荐池规模（按链）

| 文件 | 基线 fixtures/ | 用户 fixtures.d/ | 字节估算 |
|---|---|---|---|
| **EVM** |  |  |  |
| `addresses_hot.txt` | 50 | 2 000–10 000 | 2 KB / 430 KB |
| `addresses_cold.txt` | 100 | 5 000–50 000 | 4 KB |
| `tx_hashes.txt` | 100 | 5 000–50 000 | 7 KB |
| `blocks_range.json` | 区段 + 20 | 区段 + 500 | < 1 KB |
| `contracts_erc20.json` | 10 | 200–2 000 | 1 KB |
| `topics_logs.json` | 5 | 50–200 | < 1 KB |
| **Solana** |  |  |  |
| `addresses_hot.txt` | 50 | 2 000–10 000 | 2.3 KB |
| `signatures.txt` | 100 | 5 000–50 000 | 9 KB |
| `programs.json` | 10 | 100–500 | 1–3 KB |
| `token_mints.json` | 10 | 200–2 000 | 1 KB |
| **Bitcoin** |  |  |  |
| `block_hashes.txt` | 50 | 5 000–50 000 | 3 KB |
| `tx_ids.txt` | 100 | 5 000–50 000 | 7 KB |
| **Starknet** |  |  |  |
| `contract_pool.txt` | 10 | 200–2 000 | 1 KB |
| `event_keys.txt` | 5 | 50–200 | < 1 KB |

**约束**：baseline 单文件 ≤ 50 KB，目录 ≤ 200 KB，全链合计 ≤ 1 MB。

### §21.3 manifest.json 规范

```json
{
  "chain": "ethereum",
  "fetched_at": "2026-05-19T16:42:00Z",
  "latest_block_at_fetch": 22345678,
  "source_rpc": "https://eth-mainnet.example.com",
  "pools": {
    "addresses_hot":   {"count": 50,  "fetched_at": "...", "sha256": "..."},
    "tx_hashes":       {"count": 100, "fetched_at": "...", "sha256": "..."},
    "blocks_range":    {"count": 20,  "fetched_at": "...", "sha256": "..."},
    "contracts_erc20": {"count": 10,  "fetched_at": "...", "sha256": "..."}
  },
  "schema_version": 1
}
```

**用途**：runner 启动期一次性校验 `now - fetched_at` 和 `head - latest_block_at_fetch`，按 §21.5 阈值 warn/fail。**不参与压测逻辑，只做审计**。

### §21.4 fixture fetcher 拓扑

```bash
tools/build_fixtures.sh                    # NEW, 统筹入口
  ├─ python3 tools/fetch_active_accounts.py    # baseline 已有，仅扩展 manifest 输出
  ├─ python3 tools/fetch_tx_hashes.py          # NEW, 复用 BlockchainAdapter 模式
  ├─ python3 tools/fetch_blocks.py             # NEW
  ├─ python3 tools/fetch_contracts.py          # NEW (EVM only)
  └─ python3 tools/write_manifest.py           # NEW, 汇总 manifest.json
```

每个 fetcher 内部独立：
1. 查 `latest_block` / `latest_slot`
2. 在 `[latest - window, latest]` 区间抓数据
3. 写入 `fixtures.d/<chain>/<pool>.txt|json`
4. 在 manifest 里登记一行

**取数原则**（用户澄清 2026-05-19）：
- 各池**独立抓取最近 N 块**，不共享 anchor，不强制交叉引用
- 时间漂移在分钟-小时级可接受（"差不多近期"即可）
- 这与生产真实流量行为一致（也有时间漂移），强行锁 snapshot 反而远离真实

### §21.5 漂移容忍矩阵

| 池 | warn 阈值 | fail 阈值 | 失效检测 |
|---|---|---|---|
| `blocks_range.json` 区段末端 | 1 小时 (EVM) / 30 min (Solana) | 24 小时 | `toBlock > head` |
| `tx_hashes.txt` | 24 小时 | 7 天 | 抽检 5 条 `getTransactionByHash` null 率 > 1% |
| `addresses_hot.txt` | 7 天 | 30 天 | hot 桶 nonce 下降 > 30% |
| `contracts_erc20.json` | 30 天 | 180 天 | `totalSupply` revert 率 > 0 |
| `topics_logs.json` | 90 天 | 365 天 | 事件签名几乎不变 |
| `programs.json` (Solana) | 90 天 | 180 天 | program 不再 executable |
| `slots_range.json` (Solana) | 1 小时 | 24 小时 | slot > absoluteSlot |

**runner 启动期 sanity**（不为每请求做，避免 RPC 开销）：
1. 读取所有 `manifest.json`
2. 调一次 `eth_blockNumber` / `getSlot` 拿 head
3. 按上表判断 warn/fail，写入 `drift_report.json`

### §21.6 刷新频率

| 池层 | 触发方式 | 建议频率 |
|---|---|---|
| `fixtures/`（仓库内基线）| 手动 `make refresh-baseline` + PR review | 每 1–3 个月或硬分叉后 |
| `fixtures.d/`（用户大池）| cron + git pre-push hook | hot 池每天/小时，cold 池每天，blocks_range 每次跑前 |

### §21.7 工时

- 双层架构 `fixtures/` + `fixtures.d/` + `.gitignore` 落地: 0.5h
- `tools/build_fixtures.sh` 统筹脚本 + `write_manifest.py`: 1.5h
- 3 个新 fetcher (`fetch_tx_hashes.py` / `fetch_blocks.py` / `fetch_contracts.py`) 复用 BlockchainAdapter: 4h
- 8 链 `fixtures/<chain>/*` baseline 数据填充（每链 ~10 min 抓取脚本）: 1.5h
- **小计：S12 = 7.5h**（实际申请 **8h**，含 0.5h 一致性 e2e）

---

## §22. 采样器与安全护栏

### §22.1 四种 sampler 语义

| kind | 行为 | 典型用途 | jq 取样 |
|---|---|---|---|
| `uniform` | 等概率独立 | tx hashes、cold addresses | `.pool[($seed % length)]` |
| `weighted` | 按 `weights_field` 概率 | 合约调用、program | `reduce ... cumulative` |
| `sequential` | 顺序步进绕回 | `eth_getLogs` 区段扫描 | `.pool[$i % length]` |
| `hot_cold_mix` | `hot_ratio` 概率 hot 池, 否则 cold | 账户/余额类，模拟真实流量 | `if rnd < r then hot else cold end` |

**默认**：`hot_ratio=0.2`（Zipf-like, top 20% = 80% 流量, Cloudflare/Alchemy 公开数据一致）；`rng_seed=1337` 保证可复现。

### §22.2 sampler 配置 schema（chains/<chain>.json）

```json
{
  "methods": {
    "eth_getBalance": {
      "param_format": "single_address",
      "sampler": {
        "kind": "hot_cold_mix",
        "hot_pool": "addresses_hot",
        "cold_pool": "addresses_cold",
        "hot_ratio": 0.2
      }
    },
    "eth_call": {
      "param_format": "call_balanceof",
      "sampler": {
        "kind": "weighted",
        "pool": "contracts_erc20",
        "weights_field": "weight"
      }
    },
    "eth_getLogs": {
      "param_format": "topic_block_range",
      "sampler": { "kind": "sequential", "pool": "blocks_range", "window_blocks": 128 }
    }
  },
  "sampling_defaults": {
    "kind": "uniform",
    "rng_seed": 1337,
    "hot_ratio": 0.2
  }
}
```

### §22.3 安全护栏 (safety_max_*) 默认值表

| 字段 | 推荐默认 | 业界依据 |
|---|---|---|
| `eth_getLogs.safety_max_block_range` | **1024** (~3.4 小时主网) | Infura/Alchemy 硬限 10 000、Cloudflare 800；自托管 geth/reth 实测 > 2k 时 P99 显著恶化 |
| `eth_getLogs.safety_max_response_size_mb` | 10 | Alchemy/Infura 硬限 10–150 MB |
| `eth_feeHistory.max_block_count` | 1024 | EIP-1559 客户端通用上限 |
| `eth_call.max_gas` | 50 000 000 | geth `--rpc.gascap` 默认 |
| `eth_call.timeout_ms` | 5000 | geth `--rpc.evmtimeout` 5s |
| `debug_traceTransaction.enabled` | **false** | P99 常达 10–60 s |
| `debug_traceBlockByNumber.enabled` | false | 同上更重 |
| `getProgramAccounts.requireFilters` | **true** | Triton/Helius/QuickNode 主网强制 |
| `getProgramAccounts.max_response_mb` | 10 | 同上 |
| `getProgramAccounts.encoding` | `base64`（禁 `jsonParsed`） | jsonParsed 触发解码 2-4× |
| `getBlock.transactionDetails` | **"signatures"** | 默认最轻，full 放大 10-100× |
| `getBlock.rewards` | false | rewards=true 触发额外 sysvar |
| `getSignaturesForAddress.max_limit` | 1000 | Solana 官方上限 |
| `getMultipleAccounts.max_batch_size` | 100 | Solana 官方硬限 |
| `simulateTransaction.enabled` | **false** | 每次重放一笔交易 |
| `scantxoutset.enabled` | **false** | Bitcoin Core 锁 UTXO 集数十秒 |
| `dumptxoutset.enabled` | false | 几分钟级 |
| `gettxoutsetinfo.enabled` | false | 全 UTXO 扫描分钟级 |
| `starknet_getEvents.chunk_size_max` | 100 | Infura/Alchemy/Nethermind 强制 |
| `starknet_getEvents.block_range_max` | 10 000 | killer 阈值 |
| `starknet_getEvents.require_address_or_key` | **true** | 全空 filter 是 killer |
| `starknet_estimateFee.enabled` | **false** | 每次跑模拟器 |

### §22.4 通用守卫实现

runner 加载 chain.json 时**先校验** safety；若 `method.weight > 0` 且对应 safety 设为 false/超限，立刻 fail-fast。

CLI flag 临时解锁（写入运行 manifest 留痕）：
```bash
hermes-rpc-bench --chain ethereum \
  --unsafe-allow=debug_traceTransaction,scantxoutset
```

通用守卫模板：
```bash
guard_method() {
  local chain="$1" method="$2"
  local enabled_var="${chain^^}_$(echo "$method" | tr '[:lower:]' '[:upper:]' | tr -c '[:alnum:]' '_')_ENABLED"
  if [[ "${!enabled_var:-true}" == "false" ]]; then
    [[ "$FORCE_UNSAFE_ALLOW" == *"$method"* ]] || return 1
  fi
  local rps_var="${chain^^}_$(echo "$method" | tr '[:lower:]' '[:upper:]' | tr -c '[:alnum:]' '_')_SAFETY_MAX_RPS"
  local cap="${!rps_var:-}"
  [[ -n "$cap" && "$CURRENT_RPS" -gt "$cap" ]] && return 1
  return 0
}
```

### §22.5 工时

- sampler 4 种实现 + jq 公式: 2h
- safety_max_* 22 项默认值表 + chain.json schema 升级 + fail-fast 校验: 1.5h
- `--unsafe-allow` CLI flag + manifest 留痕: 0.5h
- **小计：S13 = 4h** （并入 S12 同阶段共 12h，不单独算 S13）

---

## §16. References

- 实证文档:
  - `/tmp/gcp_network_research/` — gVNIC / IDPF / Tier_1
  - `/tmp/metadata_research/` — IMDSv1/v2 + GCP metadata
  - `/tmp/eks_vs_gke/` — 11 维度对比
  - `/tmp/cgroup_research/` — kernel.org cgroup-v2 io.stat 6 字段
  - `/tmp/k8s_api_stability/` — Rule #1/#4a deprecation policy
  - `/tmp/k8s_version_research/` — EKS/GKE 支持周期 + 在售版本表
- **RPC method 调研**（v1.2 新增）:
  - `analysis-notes/research_notes/01-evm-rpc-resource.md` — Ethereum/BSC/Base，含 Cloudflare Gateway Top 10 实测
  - `analysis-notes/research_notes/02-solana-sui-aptos-rpc-resource.md` — Solana getProgramAccounts 深度剖析
  - `analysis-notes/research_notes/03-bitcoin-starknet-rpc-resource.md` — Bitcoin txindex/scantxoutset + Starknet Pathfinder/Juno 差异
- **RPC 复杂参数 + fixture 池调研**（v1.3 新增，3 subagent 并行产出）:
  - `analysis-notes/research_notes/04-evm-complex-params.md` — EVM Top 15 method JSON schema + eth_getLogs provider 限制 + calldata 池构造 + 15 新 param_format 实现
  - `analysis-notes/research_notes/05-multichain-complex-params.md` — Solana/Sui/Aptos/Starknet 复杂参数矩阵 + commitment/encoding 成本 + node-killer 清单 + safety_max_* 默认值
  - `analysis-notes/research_notes/06-fixture-pool-engineering.md` — 业界 fixture 池工程实践（paradigm flood / ChainForge / k6 / Alchemy SLA）+ hot/cold 比 + 漂移容忍 + 双层架构
- skill: `software-development/parallel-entry-trap`
- skill: `software-development/systematic-debugging`
- 早班讨论记录: 39 项清单 (A 组 10 项 disk / B 组 8 项 network / C 组 5 项 IMDS / D 组 7 项 K8s / E 组 4 项 cgroup / F 组 6 项自动降级 / G 组 5 项横切)

---

**END OF MASTER PLAN v1.3 — 等待用户审阅 §20/§21/§22 + 全文一致性，确认后启动 S1**
