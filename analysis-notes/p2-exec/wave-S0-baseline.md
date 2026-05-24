# Wave S0: Baseline 抽样 + 设计

- 起时:2026-05-23 ~22:00
- 终时:2026-05-23 ~22:30
- skill 自检:agent-autonomy / honest-self-check-no-fake-evidence / parallel-entry-trap / decision-with-tradeoffs

## 实证发现

### 真实代码架构
- `config/config_loader.sh` (887 行) — 内嵌 `UNIFIED_BLOCKCHAIN_CONFIG` heredoc (line 407-678) 含 8 链 JSON
- `core/master_qps_executor.sh` — QPS benchmark 主引擎
- `tools/audit_rpc_methods.py` — 独立 audit 工具(本任务不动)
- `tools/mock_rpc_server.py` — 已有 mock RPC server(L3 e2e 工具链已有 ✅)
- **0 个 `core/*adapter*.py`**(我之前记忆错误 — 不是面向对象架构,是 shell + JSON)
- **0 个 `config/chain_*.sh`**(同上,method 全在内嵌 JSON 中)

### 北极星(README + master_qps_executor 实证)
**QPS Performance Benchmark Framework** — 8 链 single/mixed RPC method 真实负载测试,quick/standard/intensive 3 模式

### 现有 chain template 结构(实证 line 410-444)
```json
{
  "chain_type": "solana",
  "rpc_url": "LOCAL_RPC_URL",
  "params": { ... },
  "methods": { ... },
  "system_addresses": [ ... ],
  "rpc_methods": {
    "single": "getAccountInfo",
    "mixed": "getAccountInfo,getBalance,..."
  },
  "param_formats": { ... }
}
```

### 关键 hook 点(必改)
| Hook | 行 | 改造方向 |
|---|---|---|
| `MAINNET_RPC_URL` case | 371-405 | 改读 `chain.json.mainnet_rpc_url` |
| `UNIFIED_BLOCKCHAIN_CONFIG` heredoc | 407-678 | 删除,改读 `config/chains/*.json` |
| `validate_blockchain_node` 白名单 | 661-679 | 改动态扫 `config/chains/*.json` |
| `generate_auto_config` | 710-784 | 改 `jq` 读单 chain.json |

## parallel-entry-trap 自检
- ❌ 不新建 `core/test_spec/*.yaml`(并行体系)
- ✅ 复用 `config/chains/*.json` + `jq` + `CHAIN_CONFIG` API,纯重构

## L3 e2e 工具链(S0 末必须就位)
| 工具 | 状态 | 备注 |
|---|---|---|
| mock RPC server | ✅ 已存在 `tools/mock_rpc_server.py` | 需 S3 扩展支持 28 链 method |
| e2e harness script | ❌ 不存在,S1.1 新建 `tests/e2e_chain_smoke.sh` | |
| baseline snapshot | ❌ 不存在,S1.2 跑 8 链各 1 次 → `tests/fixtures/baseline_<chain>.log` | |

## 设计敲定(自决)
- 28 链 JSON 拆 `config/chains/<chain>.json`
- 每 JSON 加 `_comment` 字段(jq 自动忽略)
- 加 `scripts/validate_chain_configs.sh`(jq parse + schema 校验)
- pre-commit hook 调用上面脚本

## 反转条件
- L3 e2e 失败 > 1 链 → 停 S1
- public endpoint 不可达 > 3 链 → 停 S2
- jq parse 失败 → 停 commit
