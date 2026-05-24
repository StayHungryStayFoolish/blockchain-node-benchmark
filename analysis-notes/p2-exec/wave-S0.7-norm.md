# Wave S0.7-norm — 28 链 schema normalize + cache var name bash 合法化

**baseline**: S1 commit `70e88ed`
**完成时间**: 2026-05-24
**目标**: 把 S0-inv 抽出的 28 链 chain template(调研格式)normalize 成 baseline 7 字段格式,**消除"调研 schema vs baseline schema"双源 parallel-entry-trap**;附带修复带 `-` 链名(`avalanche-c` / `cosmos-hub` / `zksync-era` / `avalanche-x`)在 `config_loader.sh` cache var name 处的 bash 语法错误。

## 决策与执行回顾

### 路线选择(A vs B vs C)

| 选项 | 走法 | 选 | 理由 |
|------|------|-----|------|
| **A** | 一次性 normalize 全 28 链 + 单脚本可复跑 | ✅ | 0 技术债,后续 wave 0 schema 负担 |
| B | wave A 内逐链改 6 个,defer 余下 22 个 | ✗ | 每 wave 重复一遍转换逻辑 = 隐性 parallel-entry-trap 变种 |
| C | 暂停 S2,先回 S0.7 做 schema 校准 | ≈A | 实质同 A,只是 phase 命名问题 |

最终走 A,作为 S0.7 一个独立 wave 完成。

### 字段映射(调研 → baseline)

| baseline 字段 | 调研字段 | 转换规则 |
|---------------|----------|----------|
| `chain_type` | `chain_type` | 复用 |
| `rpc_url` | — | 常量 `"LOCAL_RPC_URL"`(同 baseline 8 链)|
| `rpc_methods.single` | `single_method` | 字符串 |
| `rpc_methods.mixed` | `mixed_methods[]` | `,`.join |
| `methods` | — | `{}`(framework 别名,新链 S3 用到再补)|
| `param_formats` | `param_formats` | 复用 |
| `params` | `target_address` | 标准 6-key 模板 + `target_address` 真值 |
| `system_addresses` | `system_addresses` | 复用 |

调研专有字段(`chain` / `public_endpoints` / `single_method` / `mixed_methods` / `rpc_protocol` / `target_address` / `notes`)**保留到 `_meta.original_*`**,转换可追溯。

## 重要发现

### Finding 1: `cosmos.json` 0 字节 ≠ 文件缺失

S2 wave A 入口校验时报 `cosmos.json` 0 字节缺失。实际是 S0-inv 抽稿时按调研稿文件名 `05-cosmos-hub.md` 命名,生成的是 `cosmos-hub.json`(1886B 完整)。**校验脚本写死 `cosmos` 名字误判。**

教训:wave 入口校验时 chain 名要按真实文件名(`ls config/chains/*.json`),不能预设。

### Finding 2: 20/28 链标 `adapter_required = true`(71%)

| 链 | 真接口 | adapter_required |
|----|--------|-----|
| EVM L2(arbitrum/optimism/linea/zksync-era/avalanche-c) | 纯 JSON-RPC | ❌(可直跑) |
| EVM L1 变种(kusama/near) | 纯 JSON-RPC | ❌ |
| Cosmos 系(cosmos-hub/osmosis/celestia/injective/sei) | Tendermint RPC + REST 双栈 | ✅ |
| UTXO 系(bitcoin/litecoin/dogecoin/bch) | JSON-RPC 1.0 + Esplora REST | ✅ |
| 其他(aptos/cardano/polkadot/tezos/algorand/tron/ton/hedera + Substrate 系) | REST / 各种 | ✅ |

`adapter_required = true` **不是技术债,是真实业务边界**:framework master_qps_executor 只发 JSON-RPC POST,REST 链需 adapter。S3 阶段统一加 adapter,本 wave 只 normalize schema。

### Finding 3: bash cache var name bug — 文件名带 `-` 全挂

`config_loader.sh:494` `export "$cache_var_name"=...`,cache var name 含 `-` 时 bash 报 `invalid variable name`。baseline 8 链都是单 token,没暴露;normalize 后 4 个新链(`avalanche-c` / `avalanche-x` / `cosmos-hub` / `zksync-era`)立刻挂掉。

**修法**:cache var name 用 `${blockchain_node_lower//-/_}` 替换 `-` 为 `_`,3 处:
- L494 `cache_var_name="CACHED_CHAIN_CONFIG_${blockchain_node_var_safe}"`
- L466 `rpc_cache_var_name="CACHED_RPC_METHODS_${...//-/_}_${rpc_mode_lower}"`
- L535 同上(另一处出现)

文件名不动,chain_type 字段不动,影响最小。

## 改造文件

| 文件 | 变更 |
|------|------|
| `tools/normalize_chain_templates.py` | **NEW** 215 行,一次性 normalizer + 幂等检测 |
| `config/chains/<chain>.json` × 28 | 全量 rewrite(28 新链,baseline 8 不动)|
| `config/config_loader.sh` | 3 处 cache var name 加 `//-/_` 替换 |
| `analysis-notes/p2-exec/wave-S0.7-norm.md` | **NEW** 本报告 |

## 验证(全 PASS)

### L1 36 链全跑 `source loader && generate_auto_config`

```
baseline 8 链:  8/8  unchanged  (字节级 == snapshot)
新 28 链:       28/28 keys complete (chain_type/methods/param_formats/params/
                                     rpc_methods/rpc_url/system_addresses 全在)
```

### 反转策略已具备

```bash
git diff HEAD~1 config/chains/   # 看完整 normalize diff
git checkout HEAD~1 -- config/chains/  # 回滚到 normalize 前
```

normalize 脚本幂等,再跑无副作用。

## 下一步(回到 S2 wave A)

S2 wave A = wave1+2 = Bitcoin / Aptos / Cosmos-Hub / Cardano / Polkadot / NEAR(6 链)。

注:wave A 6 链中:
- `bitcoin` `cardano` `aptos` `polkadot` 4 链 `adapter_required = true` → 只验证 L1+L2 配置层,L3 mock route 在 S3 adapter 层做(本 wave 不算回归)
- `near` `cosmos-hub` 2 链:near 纯 JSON-RPC ✅、cosmos-hub `adapter_required` → 同上

wave A 每链 3 步:
1. **mock handler 增量**(若为纯 JSON-RPC 链,加 handler 到 `CHAIN_HANDLERS`)
2. **L1+L2 验证**(配置 + smoke)
3. **L3 验证仅对非 adapter_required 链**(目前 wave A 只有 `near` 一条)
4. **commit + push**

`adapter_required` 链的 L3 mock 跑通推迟到 S3 adapter 层,**不算 defer**(是真实业务边界顺序问题)。
