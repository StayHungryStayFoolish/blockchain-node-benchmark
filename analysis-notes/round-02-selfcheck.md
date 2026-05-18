# Round 2 Self-Check Report

**Round 范围**：config 4 文件 + 主入口 1 文件 = 2,124 行
**已读**：2,124 / 2,124 = 100%
**新增文件笔记**：5 个 (`user_config.sh.md` / `system_config.sh.md` / `internal_config.sh.md` / `config_loader.sh.md` / `blockchain_node_benchmark.sh.md`)
**新增调用链**：`call-chains/main-pipeline.md`（10 节点，6 READ + 4 UNREAD）

---

## R13 五问自检

| 问 | 答 | 详情 |
|---|---|---|
| 1. R0 禁用话术（"应该是/大概"等）出现次数？| **0** | 所有论断都有 file:line 或 [DOC]/[GAP] 标签 |
| 2. 论断缺 R12 标签（[CODE]/[DOC]/[CROSS]/[NOT-FOUND]/[GAP]）的条数？| **0** | 所有关键事实都打了标签 |
| 3. R7 单次 ≤500 行违反？| **0** | config_loader (836) 分 2 段；blockchain_node_benchmark (978) 分 2 段；其余 ≤120 行单段 |
| 4. 对未读文件做论断？| **0** | 所有 UNREAD 节点（master_qps_executor / monitoring_coordinator / fetch_active_accounts 等）已标 [GAP] 进 next round |
| 5. 修正上轮的几条误判？| **1** | 重新确认"5 场景"，已在 Round 1 末尾回滚（详 R16 第 2 项）|

✅ 前 4 项全 0，本轮合格。

---

## R16 强制自抽查（5 处 + 回看上轮）

### 抽查 1：DEPLOYMENT_PLATFORM 入口
- 笔记位置：`file-notes/system_config.sh.md § 4.1`
- 笔记声称：`config/system_config.sh:12 DEPLOYMENT_PLATFORM=${DEPLOYMENT_PLATFORM:-"auto"}`
- 真实原文 (L11-12)：
  ```
  # Deployment platform type (auto: auto-detect, aws: AWS environment, other: other environments)
  DEPLOYMENT_PLATFORM=${DEPLOYMENT_PLATFORM:-"auto"}
  ```
- 一致性：✅ 完全一致
- 处置：通过

### 抽查 2：8 链白名单
- 笔记位置：`file-notes/config_loader.sh.md § 4.1`
- 笔记声称：`L620 8 链白名单：solana/ethereum/bsc/base/scroll/polygon/starknet/sui`
- 真实原文 (L619-620)：
  ```
  # Supported blockchain list
  local supported_blockchains=("solana" "ethereum" "bsc" "base" "scroll" "polygon" "starknet" "sui")
  ```
- 一致性：✅ 完全一致（8 链顺序也完全一致）
- 处置：通过

### 抽查 3：AWS 自动探测唯一路径
- 笔记位置：`file-notes/config_loader.sh.md § 4.3`
- 笔记声称：`L106 curl 仅探测 AWS metadata，不会探测 GCP → GCP 上会被识别为 other`
- 真实原文 (L105-106)：
  ```
  # Check if in AWS environment (via AWS metadata service)
  if curl -s --max-time 3 --connect-timeout 2 "${AWS_METADATA_ENDPOINT}/${AWS_METADATA_API_VERSION}/meta-data/instance-id" >/dev/null 2>&1; then
  ```
- 一致性：✅ 完全一致（注释明确 "AWS environment"）
- 处置：通过

### 抽查 4：master_qps_executor.sh 调用点
- 笔记位置：`file-notes/blockchain_node_benchmark.sh.md § 3 + call-chains/main-pipeline.md 节点 6`
- 笔记声称：`blockchain_node_benchmark.sh:271 spawn core/master_qps_executor.sh`
- 真实原文 (L270-272)：
  ```
  # Call master_qps_executor.sh
  "${SCRIPT_DIR}/core/master_qps_executor.sh" "${executor_args[@]}"
  local test_result=$?
  ```
- 一致性：✅ 完全一致（确认在 core/ 不在 utils/）
- 处置：通过

### 抽查 5：BOTTLENECK_*_THRESHOLD 数量
- 笔记位置：`file-notes/internal_config.sh.md § 4.1`
- 笔记声称：`L13-22 真实定义 8 个 BOTTLENECK_*_THRESHOLD`
- 真实原文 (L17-19) 抽样：
  ```
  BOTTLENECK_EBS_UTIL_THRESHOLD=90          # EBS utilization exceeding 90% is considered a bottleneck
  BOTTLENECK_EBS_LATENCY_THRESHOLD=50       # EBS latency exceeding 50ms is considered a bottleneck
  BOTTLENECK_NETWORK_THRESHOLD=80           # Network utilization exceeding 80% is considered a bottleneck
  ```
- 一致性：✅ 完全一致（前 3 个）；上下文 L14-22 累计 8 个变量验证（CPU + MEM + EBS_UTIL + EBS_LATENCY + NET + ERR + EBS_IOPS + EBS_THROUGHPUT）
- 处置：通过
- ⚠️ [GAP] 留待 Round 4：bottleneck_detector.sh 真实读了几个？

### 抽查 6（R16 第 2 项必查）：回看上轮"5 场景"修正
- Round 1 末尾我把"4 场景" → 反向"修正"为错的，然后用户纠正，又回滚为正确的"5 场景"
- 当前笔记位置：`docs-notes/monitoring-mechanism-zh.md § 2.4` + `round-01-selfcheck.md` 表第 3 行
- 重新读原文 (`monitoring-mechanism-zh.md:386-388`)：
  ```
  
  **五种场景判断逻辑**:
  
  ```
- 当前笔记表述："5 种场景判断（A-Resource / A-RPC / B / C / D）[DOC] L387-445"
- 一致性：✅ 与原文 L387 "**五种场景**" 完全一致
- 处置：通过（回滚成功，未再翻烧饼）

---

## 抽查总结

**6/6 通过** ✅

- 0 处发现 ❌
- 0 处发现 ⚠️ 需 patch
- 1 处保留 [GAP] 待 Round 4 代码裁决（BOTTLENECK threshold 真实消费数量）

**本轮无需作废重做。**

---

## 本轮关键发现汇总

### 1. R15 验证成功：文档 vs 代码全部一致
| 论断 | docs 表述 | 代码原文 | 一致 |
|---|---|---|---|
| DEPLOYMENT_PLATFORM | configuration-guide:132 `auto` 默认 | system_config.sh:12 `${DEPLOYMENT_PLATFORM:-"auto"}` | ✅ |
| AWS metadata 端点 | 文档未提具体值 | system_config.sh:57 `http://169.254.169.254` | ✅ |
| 8 链支持 | blockchain-testing 列 8 | config_loader.sh:620 + 331-360 + 362-608 三处对称 | ✅ |
| AWS_EBS_BASELINE_IO_SIZE_KIB=16 | monitoring:113-118 公式 | system_config.sh:53 `=16` | ✅ |
| 79 CSV 字段 (主) | data-arch:86 | 本轮未读到，留 Round 4 | [GAP] |

### 2. GCP 迁移核心触点（已 file:line 锁定）
| Patch | 位置 | 状态 |
|---|---|---|
| auto 检测加 GCP 分支 | config_loader.sh:106 | [CODE] 确认 |
| case 加 gcp 分支 | config_loader.sh:117-130 | [CODE] 确认 |
| CLOUD_IO_UNIT_KIB 替代 AWS_EBS_BASELINE_IO_SIZE_KIB | system_config.sh:53 | [CODE] 确认 |
| AWS_METADATA_* 命名中立化 | system_config.sh:57-59 | [CODE] 确认 |
| MONITORING_PROCESS_NAMES 含 ena_network_monitor | system_config.sh:71 | [CODE] 确认 |
| ENA_MONITOR_ENABLED 硬编码 true | user_config.sh:35（被 config_loader.sh:108/119/123 覆写）| [CODE] 确认 |

### 3. 命名中立化触点
- internal_config.sh:17/18/21/22 共 4 个 `BOTTLENECK_EBS_*` 变量 → 加 alias `BOTTLENECK_DISK_*`
- 整个 blockchain_node_benchmark.sh **完全平台中立**（仅 L436 一处把 ena_ 字段当 AWS 日志）

### 4. fake-stack 必须注入的环境变量
- `BASE_MEMORY_DIR=/tmp/fake-shm`（覆盖硬编码 /dev/shm，supports macOS）
- `DEPLOYMENT_PLATFORM=other`（避免 curl AWS metadata 3 秒超时）
- `BLOCKCHAIN_BENCHMARK_DATA_DIR=/tmp/fake-data`（避免污染真实路径）

### 5. 新增 GAP 待后续 Round 验证
| GAP # | 描述 | 责任 Round |
|---|---|---|
| G2.1 | bottleneck_detector.sh 真实读了几个 threshold？8/7/6/5？ | Round 4 |
| G2.2 | UNIFIED_BLOCKCHAIN_CONFIG 占位字符串如何替换为真实值？ | Round 3 |
| G2.3 | performance_latest.csv symlink 由谁建？ | Round 4 |
| G2.4 | bottleneck_qps vs max_qps 语义？哪个大？ | Round 3 |
| G2.5 | iostat_collector.sh 何处做 AWS EBS baseline conversion？ | Round 4 |
| G2.6 | ENA_ALLOWANCE_FIELDS 注释说"自动调整"，调整逻辑在哪？ | Round 4 |
| G2.7 | clear_config_cache 在切换链时是否清得干净？ | Round 5 |
| G2.8 | core/common_functions.sh 在 core/ 不在 utils/ —— 都有些什么？ | Round 3 |

### 6. 与 Round 1 文档矛盾的代码裁决进度
| 矛盾点 | Round 1 [DOC] 表述 | Round 2 [CODE] 部分裁决 | 待 Round 4 终决 |
|---|---|---|---|
| 瓶颈维度数 (arch 6 / monitoring 7 / 列举 8) | 矛盾 | internal_config.sh 定义 **8 个 threshold** | bottleneck_detector.sh 实际消费数 |
| 瓶颈场景数 (主表 5 / 副表 4) | 主表 5 权威 | 本轮未涉及 bottleneck 逻辑代码 | bottleneck_detector.sh case 分支数 |
| CSV 字段数 (78 vs 79) | 79 含 timestamp | 本轮 grep `timestamp`/`cpu_usage`/`mem_usage` 是必需字段 | unified_monitor.sh CSV header 定义 |

---

## 进度统计 (累计)

- Round 1: 5/42 文件 (11.9%), 2,715 行
- Round 2: 5 文件 + 2,124 行
- **累计**: 10/42 文件 (23.8%), 4,839 行
- 剩余: 32 文件, ~24,419 行（按 docs 估算 29,258 减去已读 4,839）

---

## 下一步

**等用户回复"开 Round 3 还是先暂停"**

Round 3 计划：core/ 目录 2 文件 ~1,270 行
- `core/master_qps_executor.sh` （主 QPS 执行器，写 qps_status.json，是 G2.4 G2.2 的裁决文件）
- `core/common_functions.sh` （框架共享函数，blockchain_node_benchmark.sh:67 source）
