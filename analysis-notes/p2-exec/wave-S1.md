# Wave S1 — baseline 8 链 loader 改造(零破坏切源)

**baseline**: `5bd01a6`(继承自 S0-tools)
**完成时间**: 2026-05-24
**改造目标**: 把 baseline 8 链的配置真源从 `config_loader.sh` 内嵌 `UNIFIED_BLOCKCHAIN_CONFIG` heredoc 切换到 `config/chains/*.json` 文件,**消除 parallel-entry-trap 隐患**(原 heredoc 与新 JSON 双源 = drift 风险);同时改 `validate_blockchain_node()` 让支持的链列表 **自动从 `config/chains/` 发现**,达成"加链 = 落 1 个 JSON"的关键步。

## 决策摘要

| 议题 | 选项 | 决策 | 反转条件 |
|------|------|------|----------|
| heredoc 处置 | A 删除 / B 保留作 fallback | **A 删除** | 若有外部脚本 source 后 `$UNIFIED_BLOCKCHAIN_CONFIG`,立即 revert |
| 改造范围 | 仅 loader / loader+validate | **loader + validate** | — |
| 缓存兼容 | 改 / 不改 | **不改** `CACHED_CHAIN_CONFIG_*` 变量名 | — |

## E1/E5 自检

- **E1 完整度**:三层验证全过,无 defer。
- **E5 反例**:loader 改造仅对 8 baseline 链验证;27 新链 + TON 的真跑通到 S2/S3 才会测。本 wave 不声明 36 链全好。
- **风险前置 grep**:全仓 grep `UNIFIED_BLOCKCHAIN_CONFIG` = 0 外部 source 依赖,A 方案安全。
- **缓存语义不变**:`CACHED_CHAIN_CONFIG_<chain>` 变量名照旧,缓存命中行为不变,只是 cache miss 时改读文件。

## 改造点(共 3 处)

### 1. `config/config_loader.sh` — 删除 heredoc(L407-654,-248 行)

整块 `UNIFIED_BLOCKCHAIN_CONFIG=$(cat <<'EOF' ... EOF\n)` 删除。bash -n 通过,无残留代码引用(注释里"legacy ... heredoc"作历史指示)。

### 2. `config/config_loader.sh` — 改 `generate_auto_config` jq 输入源

```diff
-        local jq_query=".blockchains.\"$blockchain_node_lower\""
-        CHAIN_CONFIG=$(echo "$UNIFIED_BLOCKCHAIN_CONFIG" | jq -c "$jq_query")
+        local chains_dir="${CONFIG_LOADER_DIR:-$(dirname "${BASH_SOURCE[0]}")}/chains"
+        local chain_file="$chains_dir/${blockchain_node_lower}.json"
+        if [[ ! -f "$chain_file" ]]; then
+            CHAIN_CONFIG=""
+        else
+            CHAIN_CONFIG=$(jq -c 'del(._meta)' "$chain_file")
+        fi
```

`del(._meta)` 是关键:`config/chains/*.json` 比 baseline 多了 `_meta` 字段(标 source/research_doc/extracted_at/baseline_sha),loader 输出去掉这字段后与 baseline heredoc 字节级一致。

### 3. `config/config_loader.sh` — 改 `validate_blockchain_node` 自动发现

```diff
-    local supported_blockchains=("solana" "ethereum" "bsc" "base" "scroll" "polygon" "starknet" "sui")
-    for supported in "${supported_blockchains[@]}"; do
-        if [[ "$blockchain_node_lower" == "$supported" ]]; then return 0; fi
-    done
+    local chains_dir="${CONFIG_LOADER_DIR:-$(dirname "${BASH_SOURCE[0]}")}/chains"
+    local target_file="$chains_dir/${blockchain_node_lower}.json"
+    if [[ -f "$target_file" ]]; then return 0; fi
+    # 错误诊断时也自动扫已知链(诊断输出友好)
```

加链工作流从此 **彻底不用碰这个文件**,只要扔一个 `config/chains/<name>.json` 进去。

### 4. `tools/mock_rpc_server.py` — 头部注释指向修正

```diff
-Source of truth for RPC methods: config/config_loader.sh L388-600 (UNIFIED_BLOCKCHAIN_CONFIG).
+Source of truth for RPC methods: config/chains/<name>.json (since S1.1, replaces legacy UNIFIED_BLOCKCHAIN_CONFIG heredoc).
```

## 三层验证(全 PASS)

### L1 配置层(8 链 source loader + 比 CHAIN_CONFIG)

每条链 subshell 跑 `BLOCKCHAIN_NODE=<chain> source config_loader.sh && generate_auto_config`,然后把 `$CHAIN_CONFIG` 与 `tests/snapshots/baseline_8chains/<chain>.json`(S0-tools 落盘)做字节级 canonical 比较:

```
✅ solana       loaded == baseline (1061B canonical)
✅ ethereum     loaded == baseline (822B  canonical)
✅ bsc          loaded == baseline (817B  canonical)
✅ base         loaded == baseline (818B  canonical)
✅ scroll       loaded == baseline (820B  canonical)
✅ polygon      loaded == baseline (821B  canonical)
✅ starknet     loaded == baseline (817B  canonical)
✅ sui          loaded == baseline (980B  canonical)
=== L1 结果: 8/8 PASS ===
```

**金标准**:loader 输出 == baseline heredoc 输出。0 drift。

### L2 运行时(mock 8 链 + 既有 e2e_smoke 8 链 matrix)

```
=== tests/smoke_mock_rpc_8chains.sh ===                  rc=0  8/8 PASS
=== tools/e2e_smoke_8chain_matrix.sh ===                 rc=0  8/8 PASS (276s)
```

### L3 e2e 全栈(新 chain-template 驱动 matrix,8 链 ONLY 过滤)

```
=== tools/e2e_smoke_chain_matrix.sh ONLY=<8 baseline> ===  rc=0  8/8 PASS (74s)
  ▸ base/bsc/ethereum/polygon/scroll/solana/starknet/sui   全 PASS,带 CHAIN_CONFIG gate
```

CHAIN_CONFIG gate 8 次全过 → 证明新 harness 的"配置 ↔ mock 一致性闸门"在 baseline 8 链上 0 假阴/假阳。

## 文件变更

| 文件 | 变更 |
|------|------|
| `config/config_loader.sh` | -248 行(删 heredoc)+ 32 行(改 loader)+ 18 行(改 validate)+ 注释 |
| `tools/mock_rpc_server.py` | -1 + 1 行(头注释指向更新) |

净行数:887 → 662(-225 行 / -25%)

## 下一步(S2 wave A)

S2 wave A = wave1+2 = Bitcoin / Aptos / Cosmos-Hub / Cardano / Polkadot / NEAR(6 链)。每链 4 步:

1. **chain template normalize** — 比 docs/zh/chains 调研稿,确认 `config/chains/<chain>.json` 字段对齐 baseline shape
2. **mock handler 增量** — 加 6 chain-family 真 handler 到 `CHAIN_HANDLERS` dict(必要时复用)
3. **L1+L2+L3 验** — pytest L1 / smoke L2 / chain_matrix L3
4. **commit + push**

护栏(沿用):每 wave 1 commit / 8 baseline diff-only / 90s 超时 fail-fast / 决策反转停手报告。
