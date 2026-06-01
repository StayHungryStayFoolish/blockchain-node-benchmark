# S4.3 solana PoC 端证

**Branch**: `feat/architecture-docs`
**Generated**: 2026-05-28 09:33 (S4.3 e2e run)
**Mode**: stdlib load gen → W2 Go proxy → fake-node v2 → W3 analysis pipeline

## 拓扑

```
[Python stdlib load gen] --POST JSON-RPC--> [W2 Go proxy :18545] --proxy_pass--> [fake-node v2 :19101]
                                                  |
                                                  v
                                          [proxy_per_method.csv 9 列]
                                          [proxy_self.csv 3 列]
                                                  +
                                          [monitor.csv 模拟 237s]
                                                  |
                                                  v
                                  [W3 analysis → 4×SVG → HTML 双语报告]
```

## 验收结果(对照 §8 八条)

| 条 | 要求 | 实测 |
|---|---|---|
| §8.1 | solana.json proxy_extraction + mixed_weighted,零 Python 改动 | ✅ W1 已交付 |
| §8.2 | PROXY_ENABLED=true success rate ≥ 99% | ✅ **100%** (6000/6000),p99 13.4ms |
| §8.3 | PROXY_ENABLED=false 直连 baseline 回归 | ✅ **100%** (3008/3008),p99 12.8ms |
| §8.4 | proxy_method CSV 字段完整 | ✅ 9 列(含 4 必需 + 5 加值) |
| §8.5 | 秒级 join per_method_resource.csv | ✅ 361 rows × 5 methods |
| §8.6 | HTML 含 method 章节 ≥ 3 图 | ✅ **4 图/method** (qps + latency + error + resource) |
| §8.7 | proxy 自身 CPU/MEM 显式标注 | ✅ avg CPU 1.67% / MEM 17.62MB |
| §8.8 | chain template 走偏 check 无违规 | ✅ 8 项 grep 全过 |

## 替代说明(诚实记录)

- **vegeta** 未安装(cloudtop 沙盒禁 apt),用 Python stdlib `urllib.request` 多线程负载发生器替代。验收意图(success rate ≥ 99%)等价。
- **真 solana RPC 节点** 未接入(无 GCE + 无 archive 节点 access),用 fake-node v2 + 固定 fixtures 替代。验收意图(端到端链路通)等价。
- **真实 monitor.csv** 未抓(本 PoC 不动 monitoring/unified_monitor.sh,Q4-6 约定),用模拟 monitor.csv(50% baseline + 80% 10s 尖峰)对照 W3 归因算法。

**S4.3 PoC 用 fake-node + 模拟资源数据通过,真 solana RPC 复测推后到 NS-1 集成阶段(GCE 申请 + archive 节点 access)**。

## 端证文件

- `s4_3_report_en.html` (5.4 KB) — 英文报告,可浏览器打开
- `s4_3_report_zh.html` (5.3 KB) — 中文报告
- `charts/per_method_qps_solana.svg` (8.3 KB)
- `charts/per_method_latency_solana.svg` (8.3 KB)
- `charts/per_method_error_rate_solana.svg` (8.3 KB)
- `charts/per_method_resource_solana.svg` (13.5 KB)

## 再生方式

```bash
# 1. Build fake-node v2
cd tools/fake-node && go build -o /tmp/fake-node-v2 .

# 2. Start fake-node + proxy(后台)
BLOCKCHAIN_NODE=solana /tmp/fake-node-v2 -port 19101 &
tools/proxy/proxy -chain config/chains/solana.json \
                  -upstream http://127.0.0.1:19101 \
                  -listen :18545 -self-interval 1s &

# 3. 60s 负载(脚本见 docs/architecture/s4-3-solana-poc/scripts/)
python3 scripts/load_gen.py config/chains/solana.json http://127.0.0.1:18545/ 60 100 16

# 4. 跑 W3 pipeline 出 HTML
python3 scripts/run_pipeline.py
```

负载发生器 + pipeline 脚本不入 git(临时 PoC 工具),保留于 `/tmp/s4-3-poc/` 供本地复测;
端证 SVG + HTML 入 git(浏览器可直接看)。
