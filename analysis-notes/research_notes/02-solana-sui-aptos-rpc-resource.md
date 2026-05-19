# Solana / Sui / Aptos RPC 方法资源消耗研究

> 收集日期：2026-05-19  来源：subagent 实证 8 次 web_search

## 一、Solana RPC 方法资源画像（Top 12）

| 方法 | 主导资源 | 典型延迟 | 一句话根因 | 有状态? |
|------|----------|----------|-------------|---------|
| getAccountInfo | Memory + Disk-Random | ms | AccountsDB 单点查 + deserialize | 是 |
| getBalance | Memory + Disk-Random | ms | 实质是 getAccountInfo 后取 lamports，**反直觉地略重于 getAccountInfo**（多一次反序列化丢弃） | 是 |
| getMultipleAccounts | Memory + Disk-Random | 数 ms-数十 ms | N 次 AccountsDB 查询，常并发 | 是 |
| **getProgramAccounts** | **CPU + Memory + Disk-Random（极重）** | **100ms - 数十秒** | **全 AccountsDB 扫描 + memcmp/dataSlice 过滤；无原生分页**；历史 OOM 头号杀手 | 是 |
| getBlock | Disk-Sequential + Network | 10-200 ms | Blockstore RocksDB 读 + JSON 序列化 | 否 |
| getBlockHeight / getSlot | Memory | <1ms | 内存读 chain head | 否 |
| getTransaction | Disk-Random | ms-10ms | Blockstore tx 索引查 | 否 |
| getSignaturesForAddress | Disk-Random + CPU | 10ms-数百 ms | tx index 扫描 + 过滤 | 否 |
| getTokenAccountBalance | Memory + Disk-Random | ms | 同 getAccountInfo + SPL 解码 | 是 |
| sendTransaction | CPU + Network | ms（本地）| 签名校验 + gossip + leader forward | 是 |
| simulateTransaction | CPU + Memory | ms-100ms | 在当前 bank 上完整执行（不广播） | 是 |
| getEpochInfo | Memory | <1ms | 常量计算 | 否 |
| getRecentBlockhash (deprecated) | Memory | <1ms | 已被 getLatestBlockhash 替代 | 否 |

来源汇总：
- Solana RPC docs https://docs.solana.com/api/http
- Helius 性能博客 https://www.helius.dev/blog
- agave validator https://github.com/anza-xyz/agave

### 1.1 getProgramAccounts 深度剖析（关键风险点）

**为什么是 Solana 节点 OOM/IO 头号杀手**：
1. **全 AccountsDB 扫描**：遍历所有由该 program 拥有的账户（可能数百万到上亿）
2. **无原生分页**：必须一次性返回结果集
3. **memcmp/dataSlice 过滤是后过滤**：先扫全集再筛
4. **deserialize cost**：每个 account 需反序列化判断
5. **历史事件**：曾导致主网 validator 反复 OOM，Helius/Triton/Alchemy 全部限制或禁用此方法

**消耗模型**（per call）：
```
cost ≈ N(accounts owned by program) × (RocksDB read + deserialize)
     ≈ 10^5 - 10^7 × ~10µs
     ≈ 1s - 100s
memory_peak ≈ N × avg_account_size ≈ 数百 MB 到数 GB
```

来源：Solana GitHub issue #26210, Helius 博客 "Why getProgramAccounts is hard"

## 二、Sui RPC 方法资源画像（Top 10）

| 方法 | 主导资源 | 典型延迟 | 一句话根因 |
|------|----------|----------|-------------|
| sui_getObject | Disk-Random | ms | RocksDB object_store 单点 |
| sui_multiGetObjects | Disk-Random + CPU | 数 ms-数十 ms | N 次查询，**>20 个 batch 时超线性，cache 驱逐** |
| sui_getTransactionBlock | Disk-Random | ms-10ms | tx_store 单点 |
| sui_queryTransactionBlocks | Disk-Random + CPU | 10ms-数百 ms | indexer DB 扫描 + 过滤 |
| sui_getOwnedObjects | Disk-Random | ms-100ms | owner_index 扫描，object 多时大 |
| sui_getCheckpoint | Disk-Random | ms | checkpoint_store 查 |
| sui_getLatestCheckpointSequenceNumber | Memory | <1ms | 内存读 head |
| suix_getBalance | Memory + Disk-Random | ms | coin_index 聚合 |
| suix_getCoins | Disk-Random + CPU | ms-数十 ms | coin_index 扫描 |
| suix_queryEvents | Disk-Random + CPU | 10ms-数百 ms | event_index 扫描 |

**Mysten 限制**：50 item 上限 (multiGet)、1000 result 上限 (query)
来源：https://docs.sui.io / Mysten Labs docs

## 三、Aptos REST API 方法资源画像（Top 10）

Aptos 走 REST 而非 JSON-RPC（独特）。

| 端点 | 主导资源 | 典型延迟 | 根因 |
|------|----------|----------|------|
| GET /accounts/{addr} | Disk-Random | ms | state_store 单点 |
| GET /accounts/{addr}/resource/{type} | Disk-Random + CPU | ms | resource 解码 |
| GET /transactions/by_hash/{hash} | Disk-Random | ms-10ms | tx_index 查 |
| GET /transactions/by_version/{ver} | Disk-Random | ms-10ms | version 索引 |
| GET /transactions (list) | Disk-Sequential | 10ms-100ms | range scan |
| POST /transactions/simulate | CPU + Memory | 10ms-数百 ms | 完整 VM 执行 |
| GET /blocks/by_height/{h} | Disk-Random | ms | block_store |
| GET /events/by_handle/... | Disk-Sequential | **O(n) 扫描非 O(1)** | sequence number 扫描，名字误导 |
| GET /accounts/{addr}/transactions | Disk-Random + CPU | 10ms-数百 ms | account_tx_index 扫 |
| GET /info | Memory | <1ms | 内存读 |

**Aptos Labs 公共节点限速**：50 req/s
来源：https://aptos.dev / Aptos Labs docs

## 四、公网流量分布

| 来源 | 关键数据 |
|------|----------|
| Helius (Solana) | getAccountInfo + sendTransaction 合占 60-70% |
| QuickNode (Solana) | getBalance / getAccountInfo 占主导 |
| Mysten 公共 fullnode | sui_getObject + sui_multiGetObjects 合占 ~50% |
| Aptos Labs | indexer (GraphQL) 流量 > REST fullnode |

**精确百分比报表**：Helius/Mysten/Aptos Labs 均未公开发布——subagent 的占比数字来自定性表述，**不应作为精确权重数据使用**。建议在 chains.d/ 用户覆盖默认权重时基于自身实际流量校准。

## 五、节点客户端 Prometheus 指标

| 客户端 | 端点 | per-method metric |
|--------|------|---------------------|
| agave-validator (Solana) | :8899/metrics 风格 | `rpc_service`, `rpc_request_time`, `accounts_db_scan` 系列计数器 |
| sui-node | :9184 | `json_rpc_request_latency_seconds` + indexer 直方图 |
| aptos-node | :9101 | `aptos_api_*` + `aptos_storage_*` |

三个客户端都暴露 per-method 维度（与 Geth 不暴露形成对比）。

## 六、5 条反直觉发现

1. **getBalance 比 getAccountInfo 略重**：deserialize-then-discard 多一道
2. **simulateTransaction 在稳态下可能比 sendTransaction 更便宜**：跳过 gossip/leader forward
3. **Sui multiGetObjects > 20 batch 超线性**：RocksDB block-cache 驱逐
4. **Aptos /events by sequence 是 O(n) 扫描非 O(1) 查找**：API 命名误导
5. **getSlot/getBlockHeight 看似 trivial 但占请求量大头**：subscription-vs-poll 成本倒挂
