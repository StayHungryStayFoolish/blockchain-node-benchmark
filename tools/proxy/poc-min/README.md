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

## 验收(2026-05-27)

详见 `REPORT.md` §4。4 条全 PASS,Q4-10 接近撤销线需阶段 4 真节点复测。
