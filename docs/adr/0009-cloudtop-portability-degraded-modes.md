# ADR-0009 — Cloudtop 可移植性 + 多级降级模式

**日期**:2026-05-28
**状态**:Accepted (B-1 ~ B-5 全部落地)
**取代**:无
**作用域**:框架端到端可运行性(从 AWS EBS 单一假设 → 跨云 + 沙盒可降级)

---

## 背景(Context)

S4.4 之前框架在非 AWS EBS 环境(cloudtop、其它云、本地)上**无法跑通端到端流程**,具体断点如下(来自 A 阶段健康审计,blockchain_node_benchmark.sh quick mode 实测):

1. **vegeta hard gate**:`master_qps_executor.sh:242` 用 `command -v vegeta` 退出 1,无自助安装路径,用户不知道怎么装
2. **设备校验死链**:`iostat_collector.sh:validate_devices()` 检查 `/dev/$LEDGER_DEVICE`(默认 `nvme1n1`)不存在 → `unified_monitor` 启动失败 → `performance.csv` 不产 → analysis 失败 → 框架 exit 1
3. **analysis 无降级**:`blockchain_node_benchmark.sh:1017` perf.csv 缺失 → `❌ Data analysis failed, test terminated` exit 1。零 HTML、零图表
4. **fake-node hardcoded path**:`fake_node.go` 三个 flag 默认 `../../config/chains` 等相对路径,从非源目录起 binary 立即 fatal
5. **AWS 误判**:`config_loader.sh:137` 自带一套独立平台探测,只 AWS / non-AWS 二分,GCP 完全没分支,且用裸 IMDSv1 + 仅判 curl exit code → cloudtop 透明代理拦截后 200 → 误判 AWS
6. **W2 proxy 孤立**:已实现的 per-method RPC proxy(tools/proxy)从未被主入口启动,导致 W3 hook(`report_generator.py:4189`)永远找不到 `proxy_method.csv`,per-method 系统资源图无法产出

## 决策(Decision)

不一次性"在 cloudtop 上模拟 AWS EBS 环境",而是**分层引入降级模式 + 修正跨云探测**,让框架在缺设备 / 缺 vegeta / 缺 perf.csv / 任意一段缺失时**仍能继续到 HTML 产出**,同时**AWS EC2 真机零回归**。

五大改动:

### B-1 设备校验 STRICT vs DEGRADED 双模式(`iostat_collector.sh`, `unified_monitor.sh`)
- 新 env `STRICT_DEVICE_VALIDATION`(默认 false / 降级模式)
- 设备缺失:DEGRADED 模式 WARN + `DEVICE_VALIDATION_DEGRADED=1` + return 0(继续)
- iostat 数据列在 DEGRADED 模式填 NaN,column 数与正常态保持一致
- AWS EC2 用户可显式 `STRICT_DEVICE_VALIDATION=true` 恢复 hard fail

### B-2 analysis 降级 HTML(`blockchain_node_benchmark.sh`, `analysis/degraded_report.py`)
- perf.csv 缺失 / <2 行时,不再 exit 1,export `ANALYSIS_DEGRADED=1` 并调 `generate_degraded_report()`
- 新 `analysis/degraded_report.py`(Python stdlib only):读 vegeta JSON + block_height CSV 出最小可用 HTML
- 醒目橙底 banner、QPS sweep 表(QPS/Success/p50/p99/Max)、内嵌 SVG 区块高度图、Capabilities skipped 列表

### B-3 主入口接 W2 proxy(`blockchain_node_benchmark.sh`, `lib/proxy_lifecycle.sh`)
- 新 Phase 2.5 "Start RPC proxy" / Phase 4.5 "Stop RPC proxy"
- proxy 启动后**临时 export** `LOCAL_RPC_URL=http://localhost:18545`(原值存 `ORIGINAL_LOCAL_RPC_URL`),让 vegeta 流量经过 proxy
- export `PROXY_METHOD_CSV=$LOGS_DIR/proxy_method.csv` 让 W3 hook 读到
- `--no-proxy` / `NO_PROXY_LAYER=1` / `SKIP_RPC_PROXY=1` 三个开关跳过(向后兼容)
- proxy 不可用 → WARN 跳过(不致命,降级与 B-1/B-2 一致)
- **主入口侵入面 27 行**(50 行硬约束内),lifecycle 逻辑独立 `lib/proxy_lifecycle.sh`

### B-4 vegeta 一键安装(`core/master_qps_executor.sh`, `blockchain_node_benchmark.sh`)
- vegeta 缺失时打印 4 行明确引导(版本 v12.13.0+ / binary 下载链 / PATH 添加示例 / 一键命令)
- 新 `--install-vegeta` 子命令:自动下载 v12.13.0 binary,选址 `/usr/local/bin`(有 sudo)→ `~/.local/bin` → `./bin`
- hard gate 行为零回退(没装 vegeta 仍 exit 1,只是引导更友好)

### B-5a fake-node 路径解析重构(`tools/fake-node/fake_node.go`)
- 三个 flag 默认值基于 binary 所在目录(`runtime.Caller` + `os.Executable` + 字串 fallback 三级降级)
- 用户显式 flag 永远优先
- 7 个测试覆盖各级降级,binary 从 /tmp、go run、源目录三种场景实测通过

### B-5b GCP 探测真凶(`config/cloud_provider.sh`, `config/config_loader.sh`)
- **真因不在 `cloud_provider.sh`**,在 `config_loader.sh:137` 另一套独立探测函数(只 AWS / non-AWS 二分,无 GCP 分支)
- `detect_deployment_platform()` 改为委托给 `cloud_provider.sh::detect_platform()`,加显式 GCP 分支
- `cloud_provider.sh::detect_platform()` 加固:用内容正则校验(GCP `^[0-9]+$`,AWS `^i-[0-9a-f]+$`)代替裸 curl exit code,沙盒 HTML 错误页不再误判

## 影响(Consequences)

正向:
- cloudtop / GCP / 任意非 AWS EBS 环境上**端到端 quick mode 跑通**到 Phase 7
- 主入口侵入面合计 ~80 行(分 3 处加 hook,无重写)
- 6 个新测试文件,38 个测试用例,全部 PASS
- AWS EC2 真机零回归(STRICT 模式 + 委托函数都保留旧路径)

负向 / 已知遗留:
- Phase 7 报告生成在 cloudtop 上仍失败(pre-existing,与本次 5 件改动无关 — baseline `1f580d9` 也是这个状态;`comprehensive_analysis.py` 子分析在度量数据稀少时全 WARN)。B-2 的 degraded HTML 已经覆盖这个场景的最小可用产出
- 跨平台 ENA → gvnic 监控等价物未实现(GCP 探到后 `ENA_MONITOR_ENABLED=false`,gvnic 监控待 S6+ 引入)
- `test_s5_diag.sh:pod_device_mapper 未跳过` 1 FAIL pre-existing(baseline 已存在,与本次无关)

## 选型理由(Alternatives Considered)

| 候选 | 否决理由 |
|------|---------|
| 在 cloudtop 上 mock AWS EBS 设备(loop device + 假 IOPS) | 模拟与真机偏差大,且 NVMe 协议级模拟工程量 ≥ 整个降级方案 |
| 在 cloudtop 上要求用户手动配置 LEDGER_DEVICE | 违反 PoC "先试,能用就行";用户没有 NVMe 设备时无解 |
| 完全跳过 unified_monitor(只跑 vegeta + degraded report) | 丢失 CPU/mem/net 监控,信息量倒退;DEGRADED 模式保留了这部分 |
| W2 proxy 跑在前台阻塞 Phase 3 | 与 master_qps_executor 同步等待,会卡死整个测试流程 |
| W2 proxy 不改 LOCAL_RPC_URL,通过 master_qps_executor 加 PROXY_URL 参数 | 要重写 master_qps_executor 的 vegeta target 生成逻辑,违反"不改 978 行入口外的核心"原则 |

## 验证(Verification)

- B-1: 8 测试 PASS,cloudtop 实测 `init_monitoring rc=0` + DEGRADED 标志生效
- B-2: 6 测试 PASS,cloudtop 实测从空 perf.csv 产出 2958 字节 HTML(含 banner / 表 / SVG)
- B-3: 集成测试 PASS,cloudtop 端到端 quick 实测 Phase 2.5/4.5 log 出现 + `proxy_method.csv` 2 行真数据 + `PROXY_METHOD_CSV` env 透传到 Phase 7
- B-4: 6 mock 测试 PASS,真下载实测 vegeta v12.13.0 binary 10.9MB chmod +x
- B-5a: 7 Go 测试 PASS,binary 从 /tmp 起 + getSlot JSON-RPC 通
- B-5b: 6 mock 测试 PASS(含 GCP-priority-over-poisoned-AWS 回归用例),cloudtop 实测 `source config_loader.sh` 日志从 "AWS environment detected" → "GCP environment detected"
- 全量回归: Go 6 包(fake-node + proxy)+ Python 19 测试 + bash 12 测试,全 PASS(除 1 个 pre-existing FAIL,不在本次范围)
