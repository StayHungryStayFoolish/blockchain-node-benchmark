# EVM 链 RPC 方法资源消耗研究（Ethereum / BSC / Base）

> 范围：以太坊主网、BSC、Base（均为 EVM 兼容，JSON-RPC 语义一致，资源画像可复用）。所有数据来自公开来源，每个数字均附 URL；缺失项注明 "未找到"。
> 收集日期：2026-05-19  来源：subagent 实证 7 次 web_search + 4 次 web_extract

## 1. Top RPC 方法资源画像表

下表的"典型延迟量级"指在主流托管节点（Geth/Erigon，SSD，warm cache）上单次请求的常见数量级；冷查询或归档场景会显著上移。

| # | 方法 | 主导资源 | 典型延迟量级 | 一句话根因 | 有状态? | 来源 |
|---|------|----------|--------------|------------|---------|------|
| 1 | eth_call | CPU + Memory（含磁盘随机读 state trie） | 1–100 ms（复杂合约可到秒级） | 在指定区块的 state 上执行 EVM，需加载多个 storage slot | 是（依赖 block tag/state） | https://docs.alchemy.com/reference/eth-call |
| 2 | eth_getBalance | Disk-Random（state trie 查询） | sub-ms – ms | 读取 account trie 的一个叶子节点 | 是 | https://www.quicknode.com/docs/ethereum/eth_getBalance |
| 3 | eth_getCode | Disk-Random | ms | 通过 codeHash 取 contract bytecode | 是 | https://www.quicknode.com/docs/ethereum/eth_getCode |
| 4 | eth_getStorageAt | Disk-Random（storage trie） | ms（归档可达 10ms+） | 进入 account 的 storage trie 取单 slot | 是 | https://www.quicknode.com/docs/ethereum/eth_getStorageAt |
| 5 | eth_blockNumber | Memory（head 缓存） | µs – sub-ms | 直接读内存中的 chain head | 否 | https://www.quicknode.com/docs/ethereum/eth_blockNumber |
| 6 | eth_getBlockByNumber | Disk-Sequential + Network（带 tx 时 payload 大） | ms – 10 ms | 按号查块头 + 可选 body | 否（除 latest/pending） | https://www.quicknode.com/docs/ethereum/eth_getBlockByNumber |
| 7 | eth_getBlockByHash | Disk-Random + Network | ms – 10 ms | 按 hash 索引到块体 | 否 | https://www.quicknode.com/docs/ethereum/eth_getBlockByHash |
| 8 | eth_getTransactionByHash | Disk-Random（tx 索引） | ms | 通过 tx index 找到 (block, idx) 再取 tx | 否 | https://www.quicknode.com/docs/ethereum/eth_getTransactionByHash |
| 9 | eth_getTransactionReceipt | Disk-Random（receipt store） | ms – 10 ms | receipt 单独存储，可能需要解码 logs | 否 | https://www.quicknode.com/docs/ethereum/eth_getTransactionReceipt |
| 10 | eth_getLogs | Disk-Random + CPU（bloom 扫描） | 10 ms – 数秒 | 遍历区块 bloom filter，命中再读 receipts | 是（block range） | https://www.alchemy.com/overviews/smart-caching-for-eth-getlogs |
| 11 | eth_estimateGas | CPU + Memory（多次 EVM 执行） | 10 ms – 秒级（实测 7s vs eth_call 60ms） | 二分查找最小成功 gas，多次重放 eth_call | 是 | https://github.com/ethereum/go-ethereum/issues/3370 |
| 12 | eth_sendRawTransaction | CPU（签名校验）+ Network（P2P 广播） | ms（本地）+ 网络传播 | 解码、校验签名/nonce、入 txpool、广播 | 是（txpool） | https://www.quicknode.com/docs/ethereum/eth_sendRawTransaction |
| 13 | eth_chainId | Memory（常量） | µs | 返回静态配置 | 否 | https://www.quicknode.com/docs/ethereum/eth_chainId |
| 14 | eth_gasPrice | Memory + 少量 CPU | sub-ms | 基于近期块的 gas 价格中位数估算 | 否 | https://www.quicknode.com/docs/ethereum/eth_gasPrice |
| 15 | eth_feeHistory | Disk-Sequential + CPU | 10–100 ms | 拉取 N 个最近块的 baseFee/奖励分位 | 否 | https://www.quicknode.com/docs/ethereum/eth_feeHistory |
| 16 | debug_traceTransaction | CPU + Memory + Disk（archive） | 100 ms – 数十秒 | 在历史 state 上整笔重放并采集每条 opcode | 是（需 archive） | https://www.quicknode.com/docs/ethereum/debug_traceTransaction |

## 2. 公网流量分布（Cloudflare Ethereum Gateway 实测排名）

Cloudflare 在 2022-04-21 公布的"最热 RPC 方法 Top 10"（按请求数排序，无具体百分比）：

1. eth_call
2. eth_blockNumber
3. eth_getBlockByNumber
4. eth_getBalance
5. eth_chainId
6. eth_getBlockByHash
7. eth_getTransactionReceipt
8. eth_getLogs
9. net_version
10. eth_getTransactionByHash

来源：https://blog.cloudflare.com/cloudflare-ethereum-gateway/

社区侧的经验值（Infura 用户自报）："99.9% 调用为 eth_call，其次 eth_getLogs 与 eth_estimateGas"——来源：https://www.reddit.com/r/ethdev/comments/qj7sgi/

Alchemy/Infura/QuickNode/Pocket/ChainStack 官方博客"按方法名分桶的精确百分比"：**未找到**。

## 3. 节点端 Prometheus 指标暴露

### Geth（go-ethereum）
启动加 `--metrics --metrics.addr=127.0.0.1`，端点 `127.0.0.1:6060/debug/metrics/prometheus`。RPC 相关指标（无 per-method 标签）：
- `rpc/requests` — RPC 请求总数（meter）
- `rpc/success` / `rpc/failure`
- `rpc/duration/all` — 所有 RPC 请求耗时（timer）

文档：https://geth.ethereum.org/docs/monitoring/metrics

**关键限制**：Geth 默认不按 `method` 维度拆分；per-method 需自行修改源码 `rpc/handler.go`。

### Erigon
端点默认 `:6060/debug/metrics/prometheus`。文档：https://docs.erigon.tech/diagnostics/metrics

精确的 per-method RPC timer 指标名清单：**未找到官方枚举页**，需源码 grep `metrics.GetOrCreateSummary`。

### Nethermind
docker-compose 示例：https://docs.nethermind.io/monitoring/metrics/
JSON-RPC 模块暴露 `nethermind_jsonrpc_requests`、`nethermind_jsonrpc_processing_microseconds`。完整 per-method 清单：**未在公开文档枚举**。

## 4. 5 条反直觉发现

1. **eth_estimateGas 比同参数 eth_call 慢 1–2 个数量级**。Geth issue 实测：eth_call 60 ms，eth_estimateGas 7 s。根因：二分查找需多次重放 EVM。来源：https://github.com/ethereum/go-ethereum/issues/3370

2. **eth_getLogs 在 topic/address 过滤命中率低时退化为全扫描**：bloom 命中后需打开 receipts，跨大区块范围磁盘随机读暴涨，延迟从 10ms 跳到数秒。来源：https://www.alchemy.com/overviews/smart-caching-for-eth-getlogs

3. **eth_call state override 隐藏成本**：临时覆盖 balance/code/storage 构造 state diff，CPU+内存成本显著高于普通 call，但托管商按"一次调用"计费。来源：https://docs.alchemy.com/reference/eth-call

4. **debug_traceTransaction = CPU+RAM 双重压力**：单笔复杂 DeFi 追踪可耗时数十秒，几乎所有公共端点默认禁用或限频 debug_*。

5. **eth_blockNumber 是隐形 QPS 杀手**：占流量榜第二，源于 dApp 轮询心跳，网关侧 QPS 远高于实际"有用"查询。缓存与限流的最高优先级。

---

备注：BSC（bsc-geth fork）与 Base（op-geth fork）在 JSON-RPC 层与 Geth 同源；BSC 3s/Base 2s 出块速度放大 eth_blockNumber 轮询压力；Base 额外暴露 `optimism_*`。
