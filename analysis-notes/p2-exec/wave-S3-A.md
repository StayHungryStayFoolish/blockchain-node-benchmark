# S3-A 实现报告 — EVM-compat 5 链(JsonRpc 复用)

**日期**: 2026-05-24
**Wave**: S3-A(S3 第 1 wave,9 wave 中)
**复用 JsonRpcAdapter**: 是
**新族数**: 0(都在 jsonrpc 族下)
**链数**: 5 — arbitrum, optimism, zksync-era, linea, avalanche-c

---

## 设计决策

S3-A 是 9 wave 中**风险最低**的 — 5 链都是 EVM 100% 兼容,JsonRpcAdapter 直接复用,
只需扩 4 个标准 EVM JSON-RPC param format,不引入新族。

### 决策矩阵

| 选项 | 路径 | 风险 | 选择 |
|------|------|------|------|
| A | 扩 JsonRpcAdapter 加 EVM 标准 format,5 链复用 | 低,format 数 7→12 | ✅ 选 |
| B | 给 5 链各做独立 EVM* adapter | 高,代码重复 5x | 否 |
| C | 复用现有 7 format 不扩 | 否,zks_/linea_/eth_call 不能正确生成 vegeta target | 否 |

**A 路依赖**:JsonRpc 族能容纳 EVM 标准 format。S2 设计审计已确认(family 边界 = 协议族,不是单链;EVM 是 JSON-RPC 子集)。

---

## 实施清单

### 1. adapter 扩展 `tools/chain_adapters/jsonrpc.py`

**新增 4 个 format**(在 baseline 7 + Sui `address_with_options` 之上):

| Format | 形态 | 用途 |
|--------|------|------|
| `block_number` | `["latest", false]` | `eth_getBlockByNumber` 标 EVM |
| `block_number_int` | `[<int>]` | `zks_getBlockDetails` 用 int 不是 "latest" |
| `transaction_hash` | `[<tx_hash>]` | `eth_getTransactionByHash/Receipt` |
| `eth_call_object_latest` | `[{to, data}, "latest"]` | `eth_call` 标 EVM 形态 |
| `object_single` | `[{from, to, value, ...}]` | `linea_estimateGas` 单 obj 不带 latest |

### 2. chain template fix(`config/chains/*.json`)

| 链 | 修改 |
|----|------|
| arbitrum | `eth_call: address_with_options → eth_call_object_latest` |
| optimism | 同上 |
| avalanche-c | 同上 |
| zksync-era | `zks_getBlockDetails: block_number → block_number_int` |
| linea | `linea_estimateGas: address_with_options → object_single` |

`_meta.s3_a_fix` 记录改动语义。

### 3. mock_rpc_server 扩展(`tools/mock_rpc_server.py`)

- `handle_evm`: 新增 `zks_L1BatchNumber` / `zks_L1ChainId` / `zks_getBlockDetails` / `linea_estimateGas` 4 个 method
- `CHAIN_HANDLERS`: 注册 5 新链全部用 `handle_evm`

### 4. L3 e2e 矩阵新增(`tools/e2e_smoke_5evm_compat_matrix.sh`)

独立 sibling 脚本(不修改 `e2e_smoke_8chain_matrix.sh`),5 链端口 28552–28556。

### 5. L1 单测扩展(`tests/test_chain_adapters.py`)

7 group → 9 group:
- `test_jsonrpc_s3a_new_formats`: 新 5 format 的 vegeta body 断言
- `test_evm_compat_5chains_standard_enum`: 5 链 param_formats ⊂ adapter 标准枚举

---

## 验收

| 维度 | 状态 |
|------|------|
| L1 单测 9/9 PASS | ✅ |
| baseline 48 vegeta target 字节级零回归 | ✅ |
| L3 baseline 8 链 e2e 全 PASS | ✅ |
| L3 新 5 链 e2e 全 PASS | ✅ |
| adapter 标准枚举闭合(12 format) | ✅ |

---

## 已知限制

| 限制 | 影响 | 缓解 |
|------|------|------|
| `transaction_hash` placeholder hash 节点返 null | mock 下不影响,真节点返 `result: null` 是合法响应 | S4 阶段 plugin 预生成真 tx hash 列表注入 |
| `eth_call_object_latest` data 是 `balanceOf(0x0)` 静态 selector | mock 返 `"0x"`(空 result),真节点同样合法返 0 余额 | S4 阶段 plugin 预生成真合约 + 真账户 padded address |
| `block_number_int` `address` 字段被复用为 int | 通过签名 `param_format + address` 单参表达,但语义有点扭曲 | 接受;ChainAdapter ABC 未来若扩 `params: dict` 可清理 |

---

## 关键发现

- chain template 中 Sui 的 `address_with_options` format 名被错填到 EVM 链 `eth_call` —— S1 normalize 时按 method 名做 naive 映射的偏差。S3-A 修正。
- zksync-era 文档说 `zks_getBlockDetails` 用 int 不是 "latest" hex,这是 zks 命名 `block_number` 与 EVM `block_number` 字面同名但语义不同的细节,设计上必须拆 2 个 format(`block_number` vs `block_number_int`)。
- 5 链中 4 个用 `eth_call` 但 linea 用自己的 `linea_estimateGas`(object 单元素,无 latest)—— 又一个 param shape 微差异。`object_single` 命名通用化覆盖未来类似 case。

---

## 下一 wave

- **S3-A2**: TronAdapter 新族(HTTP `/wallet/*` POST + body 占位)
- **S3-A3**: AvaXAdapter 新族(`avm.*` namespace + cb58 ID)
- **S3-A4**: NearAdapter 新族(account_id 字符串 + query dispatcher + logical_method)
- 然后 S3-D / S3-C / S3-B / S3-E / S3-F
