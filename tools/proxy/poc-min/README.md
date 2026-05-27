# tools/proxy/poc-min/

最小 PoC:JSON-RPC method 提取代理(Q4-8 / Q4-9 / Q4-10)。

## 范围

**仅验机制,不验性能上限**。详见 `REPORT.md`。

## 文件

- `mock_rpc.go` — 同进程 mock solana RPC server(任何 method 返回 `{"result":1000}`)
- `proxy.go` — 反向代理:body 提 method + 透传 + CSV sink
- `bench.go` — 并发 client + p50/95/99 统计
- `REPORT.md` — 实测数据 + 撤销线对比 + 阶段 4 建议

## 跑

```bash
cd tools/proxy/poc-min

# 三个独立进程
go run mock_rpc.go -port 18899 &
go run proxy.go   -listen :18890 -upstream http://127.0.0.1:18899 -log /tmp/poc_proxy.csv &
go run bench.go   -url http://127.0.0.1:18890 -qps 10000 -dur 30s -conc 200
```

或直接编译:
```bash
go build -o /tmp/poc_mock  mock_rpc.go
go build -o /tmp/poc_proxy proxy.go
go build -o /tmp/poc_bench bench.go
```

## 验收

- **v1 最小 PoC**(2026-05-27,见 `REPORT.md`):4 条全 PASS,Q4-10 接近撤销线
- **v2 录-放 PoC**(2026-05-27,见 `REPORT_v2.md`):4 条全 PASS,per-method 资源归因端到端跑通

## 范围分层

- **v1**:仅验机制(proxy + sink),单 method 单进程
- **v2**:全链路(proxy + sink + monitor + 离线归因),mixed weighted workload,5 method
- **真节点机会**:补 ADR-0001 weight 精度 + ADR-0004 真节点 CPU 占比撤销线判定

## 跑

```bash
cd tools/proxy/poc-min

# v1 (单 method 性能)
go run mock_rpc.go -port 18899 &
go run proxy.go   -listen :18890 -upstream http://127.0.0.1:18899 -log /tmp/poc_proxy.csv &
go run bench.go   -url http://127.0.0.1:18890 -qps 10000 -dur 30s -conc 200

# v2 (录-放, mixed workload, per-method 归因)
bash scripts/record_fixtures.sh                       # 一次性录 fixtures (10s, 必跑)
go run mock_rpc_v2.go -port 18899 -fixtures ./fixtures &
go run proxy.go       -listen :18890 -upstream http://127.0.0.1:18899 -log /tmp/poc_proxy_v2.csv &

# 启动后拿真 pid: pgrep -P <bash_wrapper_pid> poc_proxy / poc_mock_v2
python3 scripts/mini_monitor.py --proxy-pid <P> --node-pid <N> --out /tmp/poc_monitor.csv --duration 65 &
go run bench_v2.go    -url http://127.0.0.1:18890 -dur 60s -conc 50 \
    -weights 'getSlot:1,getBalance:1,getLatestBlockhash:1,getBlock:0.1,getTransaction:1'

# 等 monitor 跑完
python3 scripts/offline_join.py --proxy-csv /tmp/poc_proxy_v2.csv --monitor-csv /tmp/poc_monitor.csv
```

或直接编译 v1 + v2 二进制:
```bash
go build -o /tmp/poc_mock      mock_rpc.go
go build -o /tmp/poc_mock_v2   mock_rpc_v2.go
go build -o /tmp/poc_proxy     proxy.go
go build -o /tmp/poc_bench     bench.go
go build -o /tmp/poc_bench_v2  bench_v2.go
```
