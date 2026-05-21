# 03b. EVM L2 (Scroll / Polygon) RPC 资源消耗调研

**版本**: v1.4.1 (2026-05-20)
**关联 plan**: `disk-and-network-pipeline-redesign.md` §A.5.6 / §11 / §17
**真 8 链来源**: `config/config_loader.sh:660` `supported_blockchains`

---

## 背景

v1.3/v1.4 plan 误将 Bitcoin/Aptos 列入 8 链清单,S0.2 验证暴露真相:
baseline 真 8 链是 **solana / ethereum / bsc / base / scroll / polygon / starknet / sui**。
本文档补齐原调研漏掉的 Scroll/Polygon 两条 EVM L2/侧链。

---

## §1. Scroll

### 1.1 客户端
- 主流: `reth` (Rust, 性能优于 geth, 默认)
- 备选: `l2geth` (Scroll fork of go-ethereum, 兼容)

### 1.2 RPC method 与 ethereum 完全兼容
全部走 `eth_*` 命名空间(来自 `config_loader.sh` UNIFIED_BLOCKCHAIN_CONFIG):
- single: `eth_getBalance`
- mixed: `eth_getBalance,eth_getTransactionCount,eth_blockNumber,eth_gasPrice`

### 1.3 资源特征
| 维度 | Scroll | 备注 |
|------|--------|------|
| 出块时间 | ~3s | L2 sequencer 决定 |
| 状态体积 | ~50-200 GB | 远小于 ethereum mainnet |
| 链上 gas 模式 | EIP-1559 | 与 ethereum 一致 |
| 历史归档 | 需 archive 模式才有完整 trace | 受 sequencer batch 重放限制 |
| 特有: zk-proof 校验 | reth 不直接验证 zk-proof, 仅校验 batch hash | benchmark 只关注 RPC, 不涉及 |

### 1.4 mock 实现
**与 ethereum 共用** `handle_evm` (mock_rpc_server.py:387 行 CHAIN_HANDLERS)。
port=18804。

---

## §2. Polygon (PoS)

### 2.1 客户端
- 主流: `bor` (Polygon fork of geth, 业务执行层)
- 配套: `heimdall` (cosmos-sdk 共识层, validator 必装, RPC 不暴露 method 维度)

### 2.2 RPC method 与 ethereum 兼容
与 ethereum 同,走 `eth_*`:
- single: `eth_getBalance`
- mixed: `eth_getBalance,eth_getTransactionCount,eth_blockNumber,eth_gasPrice`

### 2.3 资源特征
| 维度 | Polygon | 备注 |
|------|---------|------|
| 出块时间 | ~2s | 高吞吐侧链 |
| 状态体积 | 主网 ~3 TB (archive) / ~600 GB (full pruned) | 与 ethereum mainnet 同级别 |
| TPS | ~150 (历史平均) / 65k 峰值 | 高 IOPS 压力 |
| 链上 gas 模式 | EIP-1559 | 与 ethereum 一致 |
| 特有: bor+heimdall 双进程 | 资源监控需同时观察两个进程 | benchmark 主要走 bor RPC |

### 2.4 mock 实现
**与 ethereum 共用** `handle_evm`。port=18805。

---

## §3. benchmark 建议(对 Scroll/Polygon)

| 项 | Scroll | Polygon |
|----|--------|---------|
| single 工作集 | hot 50 + cold 500 地址 | 同 |
| mixed 权重默认 | 与 ethereum 同 (40/30/20/10) | 同 |
| IOPS 重点 | reth state cache miss → 4KiB 读 | bor + heimdall 同时争盘 |
| fixture 池 | 复用 ethereum 池(EVM 地址格式同) | 同 |
| AWS EBS | gp3 16k IOPS / 1000 MB/s | 同 |
| GCP Hyperdisk Balanced | 80k IOPS / 1200 MB/s | 同 |

---

## §4. 与原 03-bitcoin-starknet 文档关系

- Starknet 部分**仍然有效**:见原 `03-bitcoin-starknet-rpc-resource.md` 后半部分
- Bitcoin 部分**OUT-OF-SCOPE**:不在 baseline,原文件已归档 `_archive_v1.4/`
- 本文件**新增**:补齐真 8 链遗漏的 Scroll/Polygon
