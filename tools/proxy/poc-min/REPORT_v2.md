# 录-放 PoC 报告 — per-method 资源归因端到端验证

**日期**:2026-05-27
**位置**:`tools/proxy/poc-min/`(v2 增量,v1 报告见 `REPORT.md`)
**关联决策**:Q4-7 / Q4-8 / Q4-9 / Q4-10(NORTH-STAR §3)
**关联 ADR**:0001 / 0002 / 0003 / 0004
**关联调研**:`analysis-notes/research_notes/07-per-method-resource-attribution-via-proxy.md`

---

## 0. 与最小 PoC(v1)的区别

| 维度 | v1 最小 PoC | v2 录-放 PoC |
|---|---|---|
| mock RPC | 固定 `{"result":1000}` | 5 个 method 真录 fixtures 重放 + 三档 sleep |
| workload | 单 method `getBalance` | mixed 加权(5 method 按 weight 混打) |
| monitor | 无 | mini_monitor.py 1Hz 采 proxy + mock CPU/MEM |
| 离线归因 | 无 | offline_join.py per-method CPU/MEM 分摊报表 |
| 验证范围 | proxy 机制 + sink 容量 | 全链路:proxy → CSV → monitor → join → per-method 报表 |

## 1. 为什么是"录-放"不是真节点

**用户决策(2026-05-27)**:
1. 自建 solana 节点暂不可用
2. 公网 mainnet endpoint(`https://api.mainnet-beta.solana.com`)频繁请求会限流
3. 折中方案:每 method 真实请求 1 次,录 response 到 fixtures,本地 mock 重放无限次

**优势**:不依赖外部资源 / 可反复跑 / 工程精度可控
**局限**(必须诚实标出):mock 节点的 CPU 消耗 ≠ 真 solana 节点的 CPU 消耗
  - mock 是"读 fixture + sleep",真节点是"查数据库 + 序列化 + 共识协议"
  - 因此 ADR-0004 撤销线"proxy CPU > 节点 10%"**仍未真实验证**,等真节点机会再补

## 2. 测试拓扑

```
bench_v2 (conc=50, 60s, mixed weighted) ─POST─▶ proxy:18890 ─POST─▶ mock_rpc_v2:18899
                                                    │                       │
                                                    │ write CSV             │ load fixtures
                                                    ▼                       ▼
                                          /tmp/poc_proxy_v2.csv   fixtures/<method>.json
                                                    │
                                                    └────────┐  ┌──── mini_monitor.py
                                                             │  │     (1Hz, proxy+mock CPU/MEM)
                                                             ▼  ▼
                                                       offline_join.py
                                                       (按 1s 窗口 + weight 分摊)
                                                             │
                                                             ▼
                                                    per-method CPU/MEM 报表
```

环境:cloudtop e2-standard-8 / 8 vCPU / Go 1.26.2 / Python 3.13 / 60s 测试

## 3. 录 fixtures

`scripts/record_fixtures.sh` 一次性脚本,从 `api.mainnet-beta.solana.com` 录 5 个 method:

| method | tier | response size | params |
|---|---|---|---|
| getSlot | cheap (1ms) | 44 B | `[]` |
| getBalance | cheap (1ms) | 102 B | `[<addr>]` |
| getLatestBlockhash | mid (10ms) | 188 B | `[]` |
| getBlock | expensive (50ms) | **3.5 MB** | `[100000000, {...}]` |
| getTransaction | expensive (50ms) | 39 B (`result:null`,signature 太老) | `[<sig>, {...}]` |

限流避险:每 method 间 `sleep 2`,5 method 共 10s,**单次录制零限流风险**。

## 4. mock_rpc_v2 三档 sleep

对应 ADR-0001 weight 1/10/100 三档:
- cheap(getSlot, getBalance):sleep 1ms
- mid(getLatestBlockhash):sleep 10ms
- expensive(getBlock, getTransaction):sleep 50ms

启动时把所有 fixture 读入内存,每请求 = `sleep(tier) + write(fixture)`。

## 5. mini_monitor.py

设计依据:ADR-0001 选项 C("monitor 独立采集")+ ADR-0004(proxy 自报 vs /proc 双采)

**架构判断**:repo 已有 `monitoring/unified_monitor.sh`(2847 行)是生产 monitor,但依赖整个 repo 的 config/utils 链,且 mock 场景下 EBS/Net 是 0 没意义。
**决策**:写 80 行 Python mini-monitor 替代,只采 CPU + MEM,1Hz。
**机制等价性**:与 unified_monitor.sh 都是"外部独立进程采指标按 CSV 写盘",ADR-0001 选项 C 的设计不受影响。
**生产路径**:NS-2 真上线时用 unified_monitor.sh,mini-monitor 只为 PoC。

## 6. bench_v2 mixed workload

worker-pool 模式(无 ticker 限速),按 weight 加权随机选 method。

本次测试 weight:`getSlot:1,getBalance:1,getLatestBlockhash:1,getBlock:0.1,getTransaction:1`

(getBlock weight 调低到 0.1 因为 3.5MB response,避免网络 IO 主导)

## 7. 实测结果

### 7.1 bench_v2 输出

```
dur=1m0s conc=50 total_done=161042
actual_qps=2684.0

method                    count       ok      err        p50        p95        p99
getSlot                   38960    38960        0   2.51ms   5.65ms   8.59ms
getBalance                39423    39423        0   2.51ms   5.64ms   8.48ms
getLatestBlockhash        39417    39417        0  11.58ms  14.66ms  17.21ms
getBlock                   3987     3987        0  58.59ms  65.34ms  69.71ms
getTransaction            39255    39255        0  51.66ms  54.68ms  57.09ms
```

✅ **3 档 latency 完美对齐**(cheap ~2.5ms / mid ~11.5ms / expensive ~52-59ms)
✅ **0 错**,161k 请求全 200 OK
✅ **mixed workload 比例符合 weight**(getBlock 占 2.5%,其余各 ~24%)

### 7.2 monitor 资源数据

稳态:
- **proxy CPU = ~172%(1.72 core)**
- **mock CPU = ~56%(0.56 core)**
- **proxy / mock 比例 = 3.07x**(mock 被 proxy 烧出来的 3 倍)

这印证 ADR-0004 "mock 节点放大占比"的预测 — **mock 场景下 proxy 占比被严重放大**,真节点资源密集时比例会反过来。**ADR-0004 撤销线判定仍待真节点验证**。

### 7.3 per-method 资源归因报表(offline_join 输出)

```
matched_buckets=61 / window=1s / weights={getSlot:1, getBalance:1, getLatestBlockhash:10, getBlock:100, getTransaction:100}

method                      calls    avg_qps      cpu_sec   cpu_per_kreq   rss_avg_mb
getBalance                  39423      646.3         0.20         0.0050         0.21
getLatestBlockhash          39417      646.2         2.00         0.0507         2.08
getTransaction              39255      643.5        19.94         0.5079        20.72
getSlot                     38960      638.7         0.20         0.0051         0.20
getBlock                     3987       65.4         1.96         0.4925         2.07
TOTAL                      161042     2640.0        24.30
```

**解读**:
- `getTransaction`:24% calls,被分摊 **82% CPU**(19.94/24.30)— weight=100 × 大量调用
- `getBlock`:2.5% calls,分摊 8% CPU — weight=100 但量小
- `getSlot` + `getBalance`:48% calls,只分摊 1.6% CPU — weight=1
- `getLatestBlockhash`:24% calls,分摊 8% CPU — weight=10

**机制正确**,加权分摊数学符合预期。

## 8. 4 条验收

| # | 验收项 | 结论 |
|---|---|---|
| 1 | record_fixtures 从公网录 5 method,0 限流 | ✅ 5/5 PASS,总耗时 10s |
| 2 | mock_v2 byte-correct 重放 + 三档 latency 生效 | ✅ p50 2.5/11.5/52-59ms 完美对齐 |
| 3 | bench_v2 mixed weighted workload,0 错 | ✅ 161k req 0 err |
| 4 | offline_join 出 per-method 资源归因表 | ✅ 5 method 全归因,加权数学正确 |

## 9. 4 个已知局限(必须诚实标出)

1. **weight 是预设不是实测**:ADR-0001 撤销线"误差 > 20%"未验证,因为没有真节点 ground truth
2. **mock 节点 CPU ≠ 真节点 CPU**:ADR-0004 撤销线"proxy CPU > 节点 10%"判定仍待
3. **getTransaction 录到 `result:null`**:signature 太老,但对 PoC 不影响(mock 是 byte 重放,内容无关紧要)
4. **mini-monitor 简化**:只 CPU+MEM,无 EBS/Net,生产用 unified_monitor.sh

## 10. PoC 结论

✅ **录-放 PoC 端到端跑通**:proxy → CSV → monitor → join → per-method 归因报表全闭环
✅ **ADR-0001 机制验证完成**:加权 group_by + 时间窗 join 数学正确,工程实现 ~300 行 Go + ~150 行 Python
✅ **ADR-0002 / 0003 在 mixed workload 下稳定**:5 method 混打 60s 0 错
⚠️ **ADR-0001 weight 精度 + ADR-0004 真节点 CPU 占比**:**待真节点机会**,本 PoC 仅验机制

## 11. 下一步建议

- **不建议立即进阶段 5**(36 链 weight + protocol dispatcher),因为 ADR-0001/0004 真精度未验,扩到 36 链等于在未验机制上加层
- **建议优先 3 选 1**:
  - (a) **等真节点机会**(用户自建 / 临时 hosted)补撤销线判定
  - (b) **PoC v3 加 EBS/Net 维度**(用 stress-ng 模拟节点真实负载,比 mock 接近真节点)
  - (c) **接 unified_monitor.sh 替换 mini-monitor**,提前对齐生产 monitor 接口,降低后续工程债

## 文件清单

```
tools/proxy/poc-min/
├── README.md                # v1 + v2 入口
├── REPORT.md                # v1 最小 PoC 报告
├── REPORT_v2.md             # 本文件
├── go.mod
├── mock_rpc.go              # v1 mock
├── mock_rpc_v2.go           # v2 fixtures + 三档 sleep (124 行)
├── proxy.go                 # 不变,v1 v2 共用
├── bench.go                 # v1 bench (单 method)
├── bench_v2.go              # v2 bench (mixed weighted) (216 行)
├── fixtures/
│   ├── getSlot.json         # 44 B
│   ├── getBalance.json      # 102 B
│   ├── getLatestBlockhash.json  # 188 B
│   ├── getBlock.json        # 3.5 MB
│   └── getTransaction.json  # 39 B
└── scripts/
    ├── record_fixtures.sh   # 一次性公网录制 (72 行)
    ├── mini_monitor.py      # 1Hz 双进程 CPU/MEM (75 行)
    └── offline_join.py      # per-method 归因 (155 行)
```

Go 增量:340 行(mock_rpc_v2 + bench_v2)
Python:230 行(mini_monitor + offline_join)
Shell:72 行(record_fixtures)
**总增量 ~640 行**,无第三方依赖(Go std + Python std)
