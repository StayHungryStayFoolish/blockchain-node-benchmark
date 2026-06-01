# ADR-0003: sink 格式 — CSV(ts_ns, method, status, latency_ns)

## 状态
Accepted(2026-05-27,commit `9e52ead`)

## 背景

ADR-0002 定下 proxy 实现,但 method 调用日志的 **sink 格式**是开放问题(OQ-4)。

**关键变化**:OQ-4 初始倾向 JSONL,07 §4 R9-R12 反方论证翻盘成 CSV。本 ADR 记录翻盘理由。

约束:
- 必须能高 QPS 写入(目标 10k+ / 链)
- 必须能离线 join(monitor 数据 + proxy 数据 按 ts 窗口 group by method)
- 必须低体积(撤销线 100GB/天)
- 必须 SQL/pandas/awk 友好(分析路径多样)

## 选项

- **选项 A:JSONL**(初始默认倾向)
  - 优:schema-less,加字段不破现有 reader
  - 劣:R9 嵌套字段对 proxy 是负担(params 不归 proxy 解);R10 比 CSV 大 ~30%;R11 高 QPS 下文件大小快;R12 加字段场景下游 SQL/pandas 都接 CSV
- **选项 B(选定):CSV**(ts_ns, method, status, latency_ns)
  - 4 列定长,append-only,grep/awk/sed/pandas/duckdb 都 1 行能读
  - 加字段 = 末尾追加列,reader 用 named columns 不破
- **选项 C:Parquet**
  - 优:列存,压缩,大数据分析友好
  - 劣:写需要 schema 锁,append 复杂;Go 生态 Parquet writer 不如 Python 成熟;**离线分析才用 Parquet,在线 sink 不合适**
- **选项 D:OpenTelemetry trace + 后端**(Jaeger / Tempo)
  - 优:可视化好,生态成熟
  - 劣:运维负担重(span 后端服务),且 trace 不是为"算资源归因"设计;over-engineering

## 决策

**选 B (CSV)**。理由翻盘自 07 §4 R9-R12:
- **R9**:嵌套字段(params / context / id)不归 proxy 解,proxy 只关心 method 名,**核心 4 列足够 PoC**
- **R10**:同样数据 CSV 比 JSONL 节省 ~30% 体积
- **R11**:10k QPS 下,JSONL 单链单日体积约 30GB+,CSV 约 20GB;低 QPS 链可忽略,**高 QPS 必须用 CSV**
- **R12**:下游分析全是 SQL/pandas/duckdb,**全部原生支持 CSV**,JSONL 还要先 flatten

**格式分层**:
- **PoC 最小实现(已落地,`tools/proxy/poc-min/proxy.go`)**:4 列 `ts_ns,method,status,latency_ns`
- **架构目标(阶段 4 完整 PoC 接入)**:6 列 `timestamp,method,req_bytes,resp_bytes,latency_ms,status`(详见 07 §4)
- **加列原则**:reader 按 header 名取,不按位置硬编码;新增列追加在末尾

## 后果

**正面**:
- 体积小(约 -30% vs JSONL)
- 工具链友好(grep/awk/sed/pandas/duckdb 即开即用)
- 写入快(无序列化嵌套)
- 加字段方便(append 列,reader 按 header 取)

**负面**:
- **不存 params**:若未来要按 params 维度归因(如 `getBalance(addr=X)` 按地址拆),要扩列或换格式
- **不存 jsonrpc id**:无法追单笔请求与 client 关联(对资源归因不影响)
- **schema 变更要约定**:加列必须在头部 header 同步,reader 不能位置硬编码

**撤销线**:体积 > **100GB/天**/单链 → 撤销转 Parquet + 按小时 roll

**后续工作**:
- 阶段 4 实测:真节点 + 真 workload,记体积曲线
- 若撤销线触发,加 Parquet writer(单独 binary 或 sidecar)
- 加 reader contract test 防 header 漂移

## 关联

- NORTH-STAR.md §3 Q4-9
- analysis-notes/research_notes/07-per-method-resource-attribution-via-proxy.md §4 R9-R12(翻盘理由)
- tools/proxy/poc-min/proxy.go(`writeCSV` 函数)
- tools/proxy/poc-min/REPORT.md(实测体积估算)
- OPEN-QUESTIONS.md(OQ-4 已锁 + "关键变化"注解;07 §4 R9-R12 的翻盘理由原文保留在 OQ-4 段)
