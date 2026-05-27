# fake-node

**框架集成测试夹具**(NOT a PoC,NOT a benchmark target)。

## 是什么

一个长期复用的"假区块链节点"程序。给 framework 全链路(workload → proxy → monitor → analysis → report)提供:

1. **真形态的 RPC 响应**(byte-correct 重放真节点录的 fixtures)
2. **真磁盘 IO 活动**(非固定频率,模拟真节点的共识/落盘 IO)

## 不是什么

- **不是** weight 数值精度的 ground truth(等真节点)
- **不是** 真节点性能极限测试(等真节点)
- **不是** PoC 一次性脚本(永久测试基础设施)

## 何时用

framework 任何改动都跑一次,确认闭环没破:

| framework 改动 | fake-node 验什么 |
|---|---|
| 加新 chain adapter | adapter 拉起 fake-node 跑通 = 加链 0 代码 |
| 改 monitor | monitor 仍能采到 fake-node 的 CPU/MEM/IO |
| 改 proxy | proxy 能解 fake-node 返回的 method/payload |
| 改 analyzer / reporter | join + report 在 fake-node 数据上输出符合 schema |
| 接 36 链 | 一份 binary + 36 份 yaml = 36 个 fake-node 实例 |

## 设计

```
   workload → [proxy] → fake-node ─┬─ fixtures (按 method)
       ↑          ↑                 └─ IO worker (随机 size + interval)
   framework  framework           
   改这里     改这里              
       │          │              
       └──── ci_smoke.sh 跑一次 ────┘
              全链路闭环还在?
```

**1 套二进制 + N 个 yaml = N 链**:每条链一份 `configs/<chain>.yaml`,定义:
- methods: RPC method -> (fixture file, tier)
- tiers: tier -> 处理延迟(`1ms` / `10ms` / `50ms`)
- io: 非固定频率 IO worker 参数(min/max bytes, min/max interval, read ratio)

## 跑

```bash
# 1. 录 fixtures (一次性, ~10s, 公网)
bash scripts/record_solana_fixtures.sh

# 2. 编译
go build -o /tmp/fake_node fake_node.go

# 3. 起 fake-node
/tmp/fake_node -config configs/solana.yaml -fixtures-dir ./fixtures -port 19000

# 4. 测它
curl -s -X POST http://127.0.0.1:19000 \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"getSlot","params":[]}'
curl -s http://127.0.0.1:19000/stats

# 5. 一键 smoke (覆盖 7 步检测, 13 个断言)
bash scripts/ci_smoke.sh
```

## smoke 覆盖的 7 步检测

| step | 验什么 |
|---|---|
| 1 | binary 编译 |
| 2 | 5 个 fixtures 存在 (缺则自动录) |
| 3 | fake-node 启动 + ready |
| 4 | 5 method 响应 byte-correct (与 fixture size 一致) |
| 5 | 三档 latency 落在期望区间 (cheap < 50ms, mid 5-80ms, expensive 30-200ms) |
| 6 | IO worker 2s 内产出 ≥1 文件 |
| 7 | `/stats` counter 非零 (requests + io_writes) |

通过标准:`PASS=13 FAIL=0`,退出码 0。

## 加链(36 链对称的体现)

只需 2 步,**零代码**:

1. 复制 `configs/solana.yaml` 为 `configs/<chain>.yaml`,改 methods/tiers/io
2. 录 fixtures:`bash scripts/record_<chain>_fixtures.sh`(或手写一个,curl 该链 endpoint)

binary 不动。

## 文件清单

```
tools/fake-node/
├── README.md
├── go.mod
├── fake_node.go              # 主体 (~270 行)
├── configs/
│   └── solana.yaml           # Solana 配置 (示范)
├── scripts/
│   ├── record_solana_fixtures.sh  # 复用 poc-min 的 fixture recorder
│   └── ci_smoke.sh           # 7 步端到端 smoke (~120 行)
├── fixtures/                 # .gitignored, 现录现用
└── .gitignore
```

## 与 `tools/proxy/poc-min/` 的关系

- `poc-min/` 是 **PoC**(一次性试验 + ADR 验证),已闭环
- `fake-node/` 是 **测试夹具**(长期复用),framework 改动时反复跑
- 两者共用 `record_fixtures.sh` 的录制逻辑(fake-node 的 record script 是 thin wrapper)
- proxy(`poc-min/proxy.go`)可独立接 fake-node 跑全链路测试(端口配通即可)

## 关联

- NORTH-STAR NS-1(零代码加链)/ NS-3(36 链对称)
- ADR-0001 / 0002 / 0003 / 0004(用 fake-node 反复回归)
- 调研 07-per-method-resource-attribution-via-proxy
