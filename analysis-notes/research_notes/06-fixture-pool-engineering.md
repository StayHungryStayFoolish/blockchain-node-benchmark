# RPC 基准测试 Fixture 池工程实践调研报告

> 为 blockchain-node-benchmark 设计 `fixtures/`（仓库内基线池）+ `fixtures.d/`（gitignored 用户大池）双层 fixture 架构提供工业界依据。
> 范围：池容量、刷新频率、热/冷桶比、采样策略、安全护栏、漂移容忍度。

---

## 1. 业界 Fixture 池容量惯例

### 1.1 来源横向对比

| 项目 / 来源 | 池规模量级 | 主要 fixture 类型 | 备注 |
|---|---|---|---|
| paradigmxyz/rpc-bench | 地址 ~1k、区块 ~500、tx ~1k | accounts/blocks/txs.json | Cargo include_bytes! 加载 |
| ethereum/go-ethereum testdata | 单方法 50–200 条 | trace 用例固定 | 正确性优先 |
| paradigm flood (jsonrpcbench) | 10k 采样轮, 地址池 1k–10k | rng-seeded sampling | flood `--rate` + sampler |
| Cloudflare Web3 Gateway 公开统计 | top10 方法占 ~80% | eth_call/getBlockByNumber/getLogs/blockNumber | 池要按方法权重 |
| Chainstack benchmarks | 100–500 唯一请求 ×并发 | 区块/日志/call 三大类 | 强调缓存命中率 |
| Alchemy SLA dashboards | 内部数百万真实样本 | 不公开 | docs 推荐 client 缓存 N=1000 hot keys |
| Solana validator rpc-test | 几十账户/几十 slot | accounts/programs/signatures | test-validator 注入 |
| k6 Web3 案例 | 100–10k 预生成 | 通常 1k 阶 | data 文件 JSON/CSV |
| wrk + lua | 1–5k 行 payload list | ndjson | 内存常驻 |
| vegeta targets | 1k–100k targets | HTTP 行格式 | 推荐 ≤几 MB |

### 1.2 共性结论
- 公开基准 fixture **极少超过 10k 条记录/类**；真实回放才到百万级
- 仓库内嵌阈值约 **50 KB / 文件、200 KB / 目录**
- 热点集中度极高：top ~20 地址 / 合约通常承担 60–80% 调用（Zipf-like）
- 采样几乎都使用 **uniform + 可选权重**

---

## 2. 每链推荐池容量

设计前提：
- `fixtures/` 内嵌池：用作 CI / 冒烟基线，单文件 ≤ 50 KB，目录 ≤ 200 KB，git clone 增量 < 0.5 MB
- `fixtures.d/` 外部池：用作真实压测，按方法/链可达 50–500 KB，gitignore，允许 5–50 MB 总量
- 节点缓存命中模拟：池规模需 > 节点 LRU 工作集

### 2.1 EVM 链 (Ethereum/Polygon/BSC/Arbitrum/Optimism/Base)

| 文件 | 基线池 fixtures/ | 用户池 fixtures.d/ | 估算字节 |
|---|---|---|---|
| `addresses_hot.txt` | 50 (hot=10, warm=40) | 2 000–10 000 | 50×43B≈2 KB / 10k×43B≈430 KB |
| `addresses_cold.txt` | 100 | 5 000–50 000 | 100×43B≈4 KB |
| `tx_hashes.txt` | 100 | 5 000–50 000 | 100×67B≈7 KB |
| `blocks_range.json` | from-to 区段 + 20 离散 | 区段 + 500 | < 1 KB / 20–200 KB |
| `contracts_erc20.json` | 10 主流 | 200–2 000 | 1–5 KB / 100 KB |
| `topics_logs.json` | 5 (Transfer/Approval/Swap/...) | 50–200 | < 1 KB |
| `slots.json` | 8 个常见 slot | 100–500 | < 1 KB |

**EVM 基线合计 ≈ 15–25 KB**，用户池可扩到 **1–5 MB**。

### 2.2 Solana

| 文件 | 基线池 | 用户池 |
|---|---|---|
| `addresses_hot.txt` (pubkeys) | 50 | 2 000–10 000 |
| `signatures.txt` | 100 | 5 000–50 000 |
| `slots_range.json` | 区段 + 20 | 区段 + 500 |
| `programs.json` | 10 (Token/Memo/Serum/Raydium/Jupiter/Metaplex/...) | 100–500 |
| `token_mints.json` | 10 (USDC/USDT/WSOL/BONK) | 200–2 000 |

**Solana 基线合计 ≈ 15–20 KB**。

### 2.3 Bitcoin / UTXO 链

| 文件 | 基线 | 用户池 |
|---|---|---|
| `block_hashes.txt` | 50 | 5 000–50 000 |
| `block_heights.json` | 区段 + 20 | 区段 + 1 000 |
| `tx_ids.txt` | 100 | 5 000–50 000 |
| `addresses.txt` (谨慎用) | 20 | 500–5 000 |

### 2.4 容量决策矩阵

| 维度 | 阈值 | 行动 |
|---|---|---|
| 单文件 > 50 KB | 移至 `fixtures.d/<chain>/` |
| 目录 > 200 KB | 拆分；release artifact |
| clone 增量 > 0.5 MB | 强制 gitignore |
| 池 < 节点 LRU | 增大 cold 桶 |

---

## 3. 采样策略 Schema (chains/<chain>.json)

### 3.1 EVM 示例

```json
{
  "chain": "ethereum",
  "fixtures": {
    "baseline_dir": "fixtures/ethereum",
    "extended_dir": "fixtures.d/ethereum"
  },
  "pools": {
    "addresses_hot":   { "file": "addresses_hot.txt",   "format": "lines" },
    "addresses_cold":  { "file": "addresses_cold.txt",  "format": "lines" },
    "tx_hashes":       { "file": "tx_hashes.txt",       "format": "lines" },
    "blocks_range":    { "file": "blocks_range.json",   "format": "json"  },
    "contracts_erc20": { "file": "contracts_erc20.json","format": "json", "key": "address" },
    "topics_logs":     { "file": "topics_logs.json",    "format": "json", "key": "topic0" }
  },
  "methods": {
    "eth_blockNumber": { "weight": 10, "params": [] },
    "eth_getBalance": {
      "weight": 25,
      "sampler": {
        "kind": "hot_cold_mix",
        "hot_pool": "addresses_hot",
        "cold_pool": "addresses_cold",
        "hot_ratio": 0.2,
        "block_tag": "latest"
      },
      "params_template": ["${address}", "${block_tag}"]
    },
    "eth_call": {
      "weight": 30,
      "sampler": {
        "kind": "weighted",
        "pool": "contracts_erc20",
        "weights_field": "weight"
      },
      "calldata_templates": [
        { "name": "balanceOf", "data": "0x70a08231${address32}" },
        { "name": "totalSupply", "data": "0x18160ddd" }
      ],
      "params_template": [
        { "to": "${contract}", "data": "${calldata}" },
        "latest"
      ]
    },
    "eth_getLogs": {
      "weight": 5,
      "sampler": {
        "kind": "sequential",
        "pool": "blocks_range",
        "window_blocks": 128
      },
      "safety_max_block_range": 1024,
      "params_template": [
        { "fromBlock": "${from_hex}", "toBlock": "${to_hex}", "topics": ["${topic0}"] }
      ]
    },
    "debug_traceTransaction": {
      "weight": 0,
      "enabled": false,
      "sampler": { "kind": "uniform", "pool": "tx_hashes" }
    }
  },
  "sampling_defaults": {
    "kind": "uniform",
    "rng_seed": 1337,
    "hot_ratio": 0.2
  },
  "safety": {
    "eth_getLogs.safety_max_block_range": 1024,
    "debug_traceTransaction.enabled": false,
    "eth_call.max_gas": 50000000,
    "eth_feeHistory.max_block_count": 1024
  }
}
```

### 3.2 Solana 示例

```json
{
  "chain": "solana",
  "fixtures": {
    "baseline_dir": "fixtures/solana",
    "extended_dir": "fixtures.d/solana"
  },
  "pools": {
    "addresses_hot": { "file": "addresses_hot.txt", "format": "lines" },
    "signatures":    { "file": "signatures.txt",   "format": "lines" },
    "slots_range":   { "file": "slots_range.json", "format": "json"  },
    "programs":      { "file": "programs.json",    "format": "json", "key": "program_id" }
  },
  "methods": {
    "getSlot": { "weight": 10, "params": [] },
    "getAccountInfo": {
      "weight": 25,
      "sampler": { "kind": "hot_cold_mix", "hot_pool": "addresses_hot", "cold_pool": "addresses_cold", "hot_ratio": 0.2 },
      "params_template": ["${address}", { "encoding": "base64" }]
    },
    "getProgramAccounts": {
      "weight": 1,
      "sampler": { "kind": "weighted", "pool": "programs", "weights_field": "weight" },
      "requireFilters": true,
      "params_template": [
        "${program_id}",
        { "encoding": "base64", "filters": "${filters}" }
      ]
    }
  },
  "safety": {
    "getProgramAccounts.requireFilters": true,
    "getBlock.transactionDetails": "signatures",
    "getSignaturesForAddress.max_limit": 1000
  }
}
```

### 3.3 四种 sampler 语义

| kind | 行为 | 典型用途 |
|---|---|---|
| `uniform` | 等概率独立采样 | tx hashes、cold addresses |
| `weighted` | 按 `weights_field` 概率采样 | 合约调用、program |
| `sequential` | 按顺序步进，绕回 | `eth_getLogs` 区段扫描 |
| `hot_cold_mix` | 以 `hot_ratio` 概率取 hot 池，否则 cold | 账户/余额类，模拟真实流量 |

### 3.4 hot/cold 比建议

| 比例 | 场景 | 依据 |
|---|---|---|
| **0.20**（默认）| 通用 EVM/Solana 账户类 | Cloudflare/Alchemy Zipf-like top 20% = 80% 流量 |
| 0.50 | 缓存命中率上限测试 | 量节点 cache 上限 |
| 0.00 | cold-only 压测 | reth/geth 性能调优 |
| 1.00 | hot-only 微基准 | 量 RPC 框架开销 |

---

## 4. 安全护栏默认值 (safety_max_*)

| 字段 | 推荐默认 | 业界依据 |
|---|---|---|
| `eth_getLogs.safety_max_block_range` | **1024** (~3.4 小时主网) | Infura/Alchemy 硬限 10 000、Cloudflare 800；自托管 geth/reth 实测 > 2k 时 P99 显著恶化 |
| `eth_getLogs.safety_max_response_size_mb` | 10 | Alchemy/Infura 硬限 10–150 MB |
| `eth_feeHistory.max_block_count` | 1024 | EIP-1559 客户端通用上限 |
| `debug_traceTransaction.enabled` | **false** | P99 常达 10–60 s，启用需 `--allow-trace` |
| `debug_traceBlockByNumber.enabled` | false | 同上更重 |
| `eth_call.max_gas` | 50 000 000 | geth `--rpc.gascap` 默认 |
| `eth_call.timeout_ms` | 5000 | geth `--rpc.evmtimeout` 5s |
| `getProgramAccounts.requireFilters` | **true** | Triton/Helius/QuickNode 主网已强制 |
| `getProgramAccounts.max_response_mb` | 10 | 同上 |
| `getBlock.transactionDetails` | **"signatures"** | 默认最轻 |
| `getBlock.rewards` | false | rewards=true 触发额外 sysvar |
| `getSignaturesForAddress.max_limit` | 1000 | Solana 官方上限 |
| `scantxoutset.enabled` | **false** | 锁 UTXO 集数十秒，绝不应压测 |
| `dumptxoutset.enabled` | false | 几分钟级 |
| `gettxoutsetinfo.enabled` | false | 全 UTXO 扫描分钟级 |

**执行准则**：benchmark runner 在加载 chain.json 时**先校验** safety；若 method.weight > 0 且对应 safety 设为 false/超限，立刻 fail-fast。CLI flag `--unsafe-allow=debug_traceTransaction,scantxoutset` 临时解锁，写入 manifest。

---

## 5. 刷新频率建议

| 池层 | 触发方式 | 建议频率 | 工具 |
|---|---|---|---|
| `fixtures/`（仓库内基线）| **手动** + 季度提醒 | **每 1–3 个月**或硬分叉后 | `make refresh-baseline` 脚本 |
| `fixtures.d/`（用户大池）| **cron + git pre-push hook** | hot 池 **每天/小时**, cold 池 **每天**, blocks_range **每次跑前** | systemd timer / cron |
| 每次 benchmark run | runner 启动时校验 manifest.fetched_at | > N 小时 warn, > M 小时 fail | 内置校验 |

阈值默认：

| 池类型 | warn 阈值 | fail 阈值 | 理由 |
|---|---|---|---|
| `blocks_range.json` | 1 小时 | 24 小时 | EVM 12s/块、Solana 0.4s/slot |
| `tx_hashes.txt` | 24 小时 | 7 天 | 旧 tx 一直有效但热度衰减 |
| `addresses_hot.txt` | 7 天 | 30 天 | hot 集分布迁移较慢 |
| `contracts_erc20.json` | 30 天 | 180 天 | 极稳定 |
| `topics_logs.json` | 90 天 | 365 天 | 事件签名几乎不变 |

### 5.1 manifest.json 字段

```json
{
  "pool": "addresses_hot",
  "chain": "ethereum",
  "fetched_at": "2026-05-19T12:34:56Z",
  "latest_block_at_fetch": 22345678,
  "source": "rpc://archive.local:8545",
  "method": "trace_block + topN by tx count",
  "count": 10000,
  "sha256": "…",
  "schema_version": 1
}
```

---

## 6. Fetch 时间漂移容忍度

我们的架构**不是快照回放**（不要求 fixture 与某固定区块同步），仅需"近期"数据，因此漂移容忍可显著放宽。

### 6.1 业界对比

| 场景 | 漂移要求 | 我们 |
|---|---|---|
| 共识 fuzz / state diff（Hive, EF spectest）| 锚定 block hash, 0 容忍 | N/A |
| Replay 类基准（Erigon, reth bench live）| 锚定区间，小时级 | N/A |
| **吞吐/延迟基准（flood, k6, wrk）** | fixture "still valid", **小时–天级** | ✅ 本项目 |

### 6.2 推荐容忍矩阵

| 池 | 容忍漂移 | 失效信号 | 处理 |
|---|---|---|---|
| `blocks_range.json` 区段末端 | ≤ 6h (EVM) / ≤ 30min (Solana) | `toBlock > head` 或 `head - toBlock > N` | 自动滚动 to=head-12，warn |
| `tx_hashes.txt` | ≤ 7 天 | 抽检 5 条 `eth_getTransactionByHash` null 比例 > 1% | 重新抓取 |
| `addresses_hot.txt` | ≤ 14 天 | hot 桶平均 nonce/活跃度下降 > 30% | 重新抓取 |
| `contracts_erc20.json` | ≤ 90 天 | totalSupply revert 率 > 0 | 重新抓取 |
| `programs.json` (Solana) | ≤ 90 天 | program 不再 executable | 重新抓取 |
| `slots_range.json` (Solana) | ≤ 1 小时 | slot > absoluteSlot | 滚动 |

### 6.3 漂移检测在 runner 中

启动期一次性 sanity（不为每请求做）：
1. 读取所有 manifest.json
2. 调一次 `eth_blockNumber` / `getSlot` 拿 head
3. 对每个池按上表判断 `now - fetched_at` 与 `head - latest_block_at_fetch`
4. 抽检：随机取 3 条 tx_hashes / 3 个 addresses 调一次轻方法，统计失败率
5. 输出 `drift_report.json` 入运行 manifest

### 6.4 fixtures/ vs fixtures.d/ 的耦合

- `fixtures/`（仓库内）：容忍最宽（区段除外，区段在 runner 启动时按 head 重新计算 from/to 而不动文件）
- `fixtures.d/`（用户大池）：runner 不假定其存在；若存在则覆盖同名基线 pool

---

## 7. 汇总与落地

1. **基线总预算**：每条链 in-repo fixture **≤ 50 KB / 文件、≤ 200 KB / 目录**；全链合计 ≤ 1 MB
2. **采样默认**：`hot_ratio=0.2`，`rng_seed=1337`，sampler 默认 `uniform`；`eth_getLogs` 强制 `sequential` + `safety_max_block_range=1024`
3. **安全护栏**：`debug_trace*` / `scantxoutset` / `dumptxoutset` / `getProgramAccounts(无 filter)` 默认禁用；解锁需 CLI 显式 + 运行 manifest 留痕
4. **刷新**：仓库基线手动季度刷；`fixtures.d/` 由用户 cron
5. **漂移**：不锚定 block hash；runner 启动期一次性 sanity；区段 fixture 在运行时按 head 重写 from/to
6. **manifest**：每池一个 `manifest.json`，记录 `fetched_at` + `latest_block_at_fetch` + sha256

---

## 8. 引用

- paradigm flood: https://github.com/paradigmxyz/flood
- paradigm rpc-bench: https://github.com/paradigmxyz/rpc-bench
- go-ethereum testdata: https://github.com/ethereum/go-ethereum/tree/master/eth/tracers/internal/tracetest/testdata
- geth CLI: https://geth.ethereum.org/docs/fundamentals/command-line-options
- reth bench: https://github.com/paradigmxyz/reth/tree/main/bin/reth-bench
- Solana rpc-test: https://github.com/anza-xyz/agave/tree/master/rpc-test
- Solana getProgramAccounts: https://solana.com/docs/rpc/http/getprogramaccounts
- Solana getBlock: https://solana.com/docs/rpc/http/getblock
- Alchemy eth_getLogs: https://docs.alchemy.com/reference/eth-getlogs
- Infura: https://docs.infura.io/api/networks/ethereum/json-rpc-methods/eth_getlogs
- QuickNode: https://www.quicknode.com/docs/ethereum/eth_getLogs
- Chainstack EVM RPC latency: https://chainstack.com/evm-nodes-a-dive-into-the-most-popular-ethereum-clients/
- Cloudflare Web3: https://developers.cloudflare.com/web3/ethereum-gateway/
- Pocket Network: https://github.com/pokt-network/pocket-core
- k6 data: https://k6.io/docs/examples/data-parameterization/
- xk6-ethereum: https://github.com/distribworks/xk6-ethereum
- wrk Lua: https://github.com/wg/wrk/blob/master/SCRIPTING
- vegeta: https://github.com/tsenart/vegeta#-targets
- Bitcoin Core scantxoutset: https://developer.bitcoin.org/reference/rpc/scantxoutset.html
