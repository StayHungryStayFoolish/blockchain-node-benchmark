# S3-A2 — TronAdapter 新族实施报告

**Wave**: S3-A2 (第 2 个 wave,9 族中第 7 族新增)
**Baseline**: `faffecf` (S3-A 完成态)
**Status**: ✅ 全绿
**File 变更**: 5 个 (1 新 adapter + 1 chain template 修 meta + 1 mock_rpc_server 扩 + 1 测试 + 1 e2e sibling)

---

## 1. 范围

Tron 新族 (`adapter_family=tron`)。Tron 节点暴露两个 API:
- HTTP REST: `POST /wallet/<verb>` + JSON body (4 个核心 method)
- JSON-RPC 子集: `POST /jsonrpc` (EVM-compat,1 个 method `eth_blockNumber`)

不能套现有 jsonrpc 族,因 `/wallet/*` 完全不是 JSON-RPC envelope。

## 2. 设计决策

**dispatch by method name shape (TronAdapter.build_vegeta_target)**:
- method 以 `/wallet/` 或 `/walletsolidity/` 开头 → 拼 base + method, body 走 HTTP body template
- method 以 `eth_`/`net_`/`web3_` 开头 → 拼 base + `/jsonrpc`, body 走 JSON-RPC envelope
- 其他 → ValueError(显式拒,不静默)

**body 模板枚举 (5 个)**:
- `no_params` → `{}`
- `body_address_visible` → `{address, visible:true}` (getaccount)
- `body_value_txid_nopfx` → `{value: <txid_no_0x>}` (gettransactionbyid; 自动去 0x 前缀)
- `body_owner_contract_selector_parameter` → 5 字段 TRC20 balanceOf (triggerconstantcontract)
- `body_num` → `{num: <int>}` (getblockbynum, 预留)

**parse_block_height 双形态**:
- 主路径: Tron envelope `block_header.raw_data.number` (int)
- fallback: JSON-RPC `.result` 0x-hex (`_try_int` 处理)

**health_check**: `POST /wallet/getnowblock` body `{}`, parse_jq `.block_header.raw_data.number`

## 3. mock_rpc_server 扩展

- `do_POST` 加 path 分支: `/wallet/*` 走 `process_tron_http`, 否则走 `process_jsonrpc`
- `_TRON_VERB_HANDLERS` 6 个 verb: getnowblock / getaccount / gettransactionbyid / triggerconstantcontract / getblockbynum / getaccountresource
- `CHAIN_HANDLERS` 加 `tron: handle_evm` (供 JSON-RPC 子集复用 EVM handler)
- 13 → 14 链

## 4. 测试矩阵

**L1** (`python3 tests/test_chain_adapters.py`):
- 9 → **10/10 PASS**
- 新 test_10 `test_tron_adapter_shapes` 含 9 子断言: 4 HTTP body 形态 + JSON-RPC 路由 + 2 parse_block_height + health_check + unknown method raise
- test_1 `test_factory_registers_six_families` 期望集 6→7 (加 `tron`)

**L3** (`bash tools/e2e_smoke_tron_matrix.sh`):
- e2e harness PASS (端口 28557)
- 5 个 /wallet/ HTTP probe PASS (端口 28568): getnowblock / getaccount / gettransactionbyid / triggerconstantcontract + / 上 eth_blockNumber

**回归** (baseline 不变):
- `bash tools/e2e_smoke_8chain_matrix.sh` → **8/8 PASS**
- `bash tools/e2e_smoke_5evm_compat_matrix.sh` → **5/5 PASS**

## 5. chain template 改动

`config/chains/tron.json`:
- `_meta.adapter_family`: `jsonrpc` → `tron`
- `_meta.s3a2_normalized_at`, `_meta.s3a2_note` 加
- `param_formats`: 5 个 method 全部已在 adapter 支持枚举内 (无需修改)

## 6. 反向压测自检

| 项 | 状态 |
|----|------|
| 是否真改入口 (`/wallet/*` POST)? | ✅ curl probe 5/5 真返 Tron-shaped JSON |
| 是否伪 e2e (mock-only / SKIP_HTML)? | ⚠️ 是 mock 上的 e2e,真节点未跑 (此 wave 不涉及真节点) |
| 是否破坏 baseline? | ✅ 8/8 + 5/5 PASS, 零回归 |
| adapter ABC 抽象先于具体? | ✅ TronAdapter 继承 ChainAdapter, 走 register 装饰器 |
| feature-coverage defer 风险? | ✅ Tron 5/5 method 全实现, 无 defer |

## 7. 端口分配累计

- baseline: 28545-28551 + 28899 (8 链)
- S3-A: 28552-28556 (5 EVM-compat)
- **S3-A2: 28557 (e2e), 28568 (HTTP probe sibling)**
- 后续 wave 用 28557 之后段 (从 28558 起 — 注意避开 28568)

## 8. 文件清单

新增:
- `tools/chain_adapters/tron.py` (5804 字节)
- `tools/e2e_smoke_tron_matrix.sh` (6900 字节)

修改:
- `tools/chain_adapters/base.py` (加 `tron` 到 import 列表)
- `tools/mock_rpc_server.py` (do_POST 加路径分支 + 6 verb handler + tron 链注册)
- `tests/test_chain_adapters.py` (test_1 期望集扩 + test_10 新增 + main 列表加)
- `config/chains/tron.json` (`_meta.adapter_family` 改 + s3a2 备注)

## 9. 后续 wave

S3-A3 (AvaX 新族) → S3-A4 (Near) → S3-D (Bitcoin 4) → ... 共 7 wave。
