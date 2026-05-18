# CP-3 Disk Y+ Test Report — 2026-05-18 夜间

夜间自主推进 P1 路径产物。详细执行报告见 `early-morning-report-20260519.md`。

## 测试矩阵

| Level | 项 | 结果 |
|---|---|---|
| L1 | bash -n 6 文件 | ✅ 全通 |
| L2 | 真 iostat 4 采样 | ✅ 数据非零, 21 列对齐 |
| L2 | 4 variant override 测试 | ✅ aws_ebs=21, gcp_pd=21, gcp_hyperdisk=22, other_local=19 |
| L3 | network + disk 并行 8s | ✅ 0 bad rows, 监控无干扰 |
| L4 | mock RPC 480 请求 + 监控 | ✅ 100% 成功, CSV 完整 |

## Mock RPC 验证

| 链 | Method 数 | 测试结果 |
|---|---|---|
| Solana | 10 + WS subscribe | ✅ |
| Ethereum (EVM) | 19 | ✅ |
| Starknet | 9 | ✅ |
| Sui | 8 | ✅ |
| **合计** | **46 + WS** | **100% 通过** |

## Y+ 不变量

```
✅ aws_ebs:        header_cols=21 == row_cols=21
✅ gcp_pd:         header_cols=21 == row_cols=21
✅ gcp_hyperdisk:  header_cols=22 == row_cols=22
✅ other_local:    header_cols=19 == row_cols=19
```

字段数允许跨 variant 不等，但同 variant 内 header 必等 row（这是 Y+ 架构的核心契约）。

## 真机环境信息

- 平台：cloudtop (leland.c.googlers.com)
- CPU/Mem：e2-standard-8
- 磁盘：sda 150G PersistentDisk (pd-ssd)
- iostat：sysstat 12.7.5 ✅
- CLOUD_PROVIDER auto-detect：**gcp**
- DISK_VARIANT auto-detect：**gcp_pd**

## 输出文件示例

L4 e2e 产物：
- `network_l4_20260518_181152.csv`  16 行 / 12 列
- `disk_l4_20260518_181152.csv`     17 行 / 43 列（含 LEDGER + ACCOUNTS 双设备）

## 已知未做项

- ⏸ Phase D GCE VM 真机验证（需 gcloud auth，明早做）
- ⏸ disk_monitor.sh 接入 unified_monitor.sh 主链路（保持并行，类似 CP-2 策略）
- ⏸ TRACKER + PLAN 文档同步
