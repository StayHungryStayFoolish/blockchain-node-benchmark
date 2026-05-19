# Bitcoin Core 与 Starknet RPC 方法资源消耗调研

> 收集日期：2026-05-19  来源：subagent 实证 8 次 web_search

## 一、Bitcoin Core 高频 RPC 方法资源画像

| 方法 | 主导资源 | 典型延迟 | 根因 | 需要 txindex | 来源 |
|---|---|---|---|---|---|
| getblockchaininfo | CPU 极低 | <1ms | 读内存链状态 | 否 | https://developer.bitcoin.org/reference/rpc/getblockchaininfo.html |
| getblockhash | CPU 低 | <1ms | 按高度查 chainActive | 否 | https://developer.bitcoin.org/reference/rpc/getblockhash.html |
| getblockheader | I/O 低 | 1–5ms | LevelDB 读 block index | 否 | https://developer.bitcoin.org/reference/rpc/getblockheader.html |
| getblock(verbosity=2) | I/O+CPU 中高 | 10–200ms | 读 .blk + 反序列化 + 解码全部 tx | 否 | https://developer.bitcoin.org/reference/rpc/getblock.html |
| **getrawtransaction** | **I/O 差异极大** | **1ms vs 数秒** | **有 txindex 直接定位；无则需走 mempool/utxo（对历史 tx 报错）** | **强烈推荐** | release-notes-0.17.0 |
| getrawmempool(verbose=true) | 内存+CPU | 10ms–1s | 序列化整个 mempool（可达数万条目） | 否 | bitcoin docs |
| getmempoolentry | 内存 低 | <1ms | mempool 哈希表查询 | 否 | bitcoin docs |
| sendrawtransaction | CPU 中 | 10–100ms | 脚本验签 + mempool 准入 | 否 | bitcoin docs |
| **scantxoutset** | **CPU+I/O 极高** | **数十秒到数分钟** | **遍历整个 chainstate（>1.5 亿 UTXO, >10GB）** | 否 | bitcoin docs |
| listunspent | I/O 中 | 取决于钱包大小 | 遍历钱包 UTXO | 否 | bitcoin docs |
| gettxout | I/O 低 | 1–5ms | chainstate LevelDB 单点 | 否 | bitcoin docs |
| estimatesmartfee | CPU 极低 | <1ms | 读内存 fee estimator | 否 | bitcoin docs |

### 1.1 getrawtransaction 配置陷阱

**默认行为**：节点只能查询 mempool 中的 tx 或当前 UTXO 集中有未花费输出的 tx。要查询任意历史 tx 必须 `txindex=1`，否则直接报错。txindex 需 ~50–80GB 额外磁盘空间。

来源：bitcoin/bitcoin release-notes-0.17.0

### 1.2 scantxoutset 高风险方法

扫描整个 UTXO set（chainstate ≈ 10–15GB，约 1.5 亿条目 / 2024 年），单次调用长时间占满 CPU 核 + 磁盘随机读高峰。Bitcoin Core 文档明确标注 "EXPERIMENTAL"。社区建议生产环境改用外部 electrum 类索引器。

## 二、Starknet RPC 方法资源画像

Pathfinder（Rust）vs Juno（Go）实现差异：

| 方法 | 主导资源 | 典型延迟 | 根因 | 实现差异 |
|---|---|---|---|---|
| starknet_blockNumber | CPU 极低 | <1ms | 内存读 | 一致 |
| starknet_getBlockWithTxs | I/O 中 | 20–200ms | 读区块 + 反序列化全部 tx | Pathfinder SQLite vs Juno Pebble |
| starknet_getStateUpdate | I/O 中高 | 50–500ms | state diff 可达 MB 级 | Juno 早期 trie 重建慢 |
| starknet_getStorageAt | I/O 低 | 1–10ms | Merkle trie 单点 | Pathfinder 历史状态查询优于 Juno |
| starknet_getTransactionByHash | I/O 低 | 1–10ms | 索引查 | 一致 |
| starknet_getTransactionReceipt | I/O 中 | 5–50ms | 含事件，事件多时显著 | 一致 |
| starknet_getClass | I/O 高 | 50ms-数百 ms | Cairo class 可达数 MB | 一致 |
| starknet_getClassHashAt | I/O 低 | 1–10ms | trie 查 | 一致 |
| **starknet_call** | **CPU 极高** | **10ms–数秒** | **Cairo VM 执行** | Pathfinder blockifier(Rust) vs Juno cgo（边界开销） |
| **starknet_estimateFee** | **CPU 极高** | **类似 call 或更高** | **完整执行 + 资源计量** | 批量 estimateFee 是已知压力源 |

来源：
- Pathfinder docs https://github.com/eqlabs/pathfinder
- Juno docs https://github.com/NethermindEth/juno
- Starknet JSON-RPC spec https://github.com/starkware-libs/starknet-specs

## 三、公开流量分布

- **Bitcoin**：**not found**。Bitcoin 是去中心化封闭生态，主流提供商（QuickNode、GetBlock、Blockstream Esplora）未发布方法级分布。
- **Starknet**：**not found**。Voyager、Starkscan、Alchemy/Infura Starknet 均未公开方法级 RPC 流量百分比。可间接推断钱包/浏览器场景下 `starknet_call`、`starknet_estimateFee`、`starknet_getTransactionReceipt`、`starknet_blockNumber` 占比最高。

## 四、监控指标

| 客户端 | per-method metric | 来源 |
|--------|---------------------|------|
| Bitcoin Core | **官方原生：not found**；社区 jvstein/bitcoin-prometheus-exporter 外挂（仅 RPC 调用计数，不区分方法的 CPU/延迟） | github.com/jvstein/bitcoin-prometheus-exporter |
| Pathfinder | `--monitor-address` 暴露 Prometheus，含 `rpc_method_calls_total{method=...}` 和延迟直方图 | github.com/eqlabs/pathfinder/blob/main/doc/rpc.md |
| Juno | `--metrics` 暴露 Prometheus，含 `juno_rpc_requests{method=...}` 计数器 | github.com/NethermindEth/juno |

**关键差异**：Bitcoin Core 原生不暴露 per-method metric，是 8 链中唯一需要"外挂 exporter 或代理拦截"的客户端——这强化了 §17 L7 sidecar 方案的必要性。

## 五、反直觉发现

1. **getrawtransaction 配置陷阱**：用户以为 O(1)，未开 txindex 时对历史 tx 直接失败；早期托管钱包过度调用 getblock 全块扫描自实现，反复打爆节点。
2. **getblock(verbosity=2) 比想象昂贵**：解码并 JSON 序列化整块全部 tx，大区块（>2MB）响应数十 MB，**带宽瓶颈而非 CPU**。
3. **scantxoutset 一次 ≈ 一次重启级 I/O 风暴**：共享节点上一个用户的扫描拖垮其他 RPC；公共服务商普遍禁用。
4. **Cake Wallet 类事件**：社区多次讨论钱包后端频繁 getrawtransaction/listunspent 风暴打爆公共节点的案例。具体 Cake Wallet 权威 post-mortem **not found**，仅 GitHub/reddit 讨论提及类似模式。
5. **Starknet starknet_call 比 eth_call 更不可预测**：Cairo VM + class 加载使同一函数延迟跨度更大；Pathfinder 因 Rust 原生 blockifier 在高并发下相对 Juno（cgo）更稳定（社区基准，非官方）。
6. **estimateFee 批量是 DoS 向量**：JSON-RPC batch 一次提交几十个 estimateFee = 几十次完整执行，所有 Starknet 公共网关均限速。
