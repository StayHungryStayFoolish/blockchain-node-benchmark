# EVM RPC 方法参数构造研究报告（v1.3 设计参考）

> 面向 blockchain-node-benchmark RPC 压测框架，覆盖 Top 15 方法 schema、资源画像、provider 限制、calldata 池构造、开源工具调研、param_format 扩展建议。所有 JSON 样例均与 EIP-1474 / Geth/Erigon/Reth 实现兼容。

---

## 1. Top 15 EVM RPC 方法 JSON 参数 Schema

下列方法按生产压测中调用占比排序，含完整 JSON 参数样例。

### 1.1 eth_blockNumber
无参数。轻量心跳类调用。
```json
{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}
```

### 1.2 eth_getBalance
```json
{"jsonrpc":"2.0","method":"eth_getBalance",
 "params":["0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae","latest"],"id":1}
```
- params[0]: 20-byte address (hex, 0x-prefixed)
- params[1]: block tag — `latest` | `earliest` | `pending` | `safe` | `finalized` | `0x<hex>` | `{"blockHash":"0x..."}` (EIP-1898)

### 1.3 eth_getTransactionCount
```json
{"jsonrpc":"2.0","method":"eth_getTransactionCount",
 "params":["0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae","pending"],"id":1}
```
Schema 同 getBalance；`pending` 标签触发 txpool 扫描，成本高于 `latest`。

### 1.4 eth_getCode
```json
{"jsonrpc":"2.0","method":"eth_getCode",
 "params":["0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48","latest"],"id":1}
```

### 1.5 eth_getStorageAt
```json
{"jsonrpc":"2.0","method":"eth_getStorageAt",
 "params":["0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
           "0x0000000000000000000000000000000000000000000000000000000000000003",
           "latest"],"id":1}
```

### 1.6 eth_call
```json
{"jsonrpc":"2.0","method":"eth_call",
 "params":[{
   "to":"0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
   "data":"0x70a08231000000000000000000000000de0b295669a9fd93d5f28d9ec85e40f4cb697bae",
   "from":"0x0000000000000000000000000000000000000000",
   "gas":"0x100000",
   "gasPrice":"0x0",
   "value":"0x0"
 },"latest"],"id":1}
```
- 支持 state override (3rd arg, Geth/Reth/Erigon):
```json
"params":[{...callObj}, "latest", {
   "0xContract":{"balance":"0x...","code":"0x...",
                 "stateDiff":{"0x...slot":"0x...value"}}}]
```

### 1.7 eth_estimateGas
Schema 同 eth_call 第 1 个参数；block tag 可选。生产中常省略 `from` 或填零地址；填真实 `from` 会触发余额校验路径。

### 1.8 eth_getLogs
```json
{"jsonrpc":"2.0","method":"eth_getLogs","params":[{
   "fromBlock":"0x1200000",
   "toBlock":"0x1200064",
   "address":["0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"],
   "topics":[
     "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
     null,
     ["0x000000000000000000000000de0b295669a9fd93d5f28d9ec85e40f4cb697bae"]
   ]
}],"id":1}
```
- `address` 可为单值或数组；`topics` 支持 OR 数组与 `null` 通配。
- 替代形式：`{"blockHash":"0x..."}`（单块过滤，避开范围限制）。

### 1.9 eth_feeHistory
```json
{"jsonrpc":"2.0","method":"eth_feeHistory",
 "params":["0x20","latest",[10,25,50,75,90]],"id":1}
```
- params[0]: blockCount (hex, ≤1024 in Geth, 实际多数 provider 限 ≤300)
- params[1]: newestBlock
- params[2]: reward percentiles (空数组则不返回 reward)

### 1.10 eth_getBlockByNumber
```json
{"jsonrpc":"2.0","method":"eth_getBlockByNumber",
 "params":["0x1200000",true],"id":1}
```
- params[1] = `true`: 内联完整交易（payload 大幅膨胀，约 50-200KB/block）
- `false`: 仅返回 tx hash 数组

### 1.11 eth_getBlockByHash
Schema 同上，params[0] 为 32-byte block hash。

### 1.12 eth_getTransactionByHash
```json
{"jsonrpc":"2.0","method":"eth_getTransactionByHash",
 "params":["0x88df016429689c079f3b2f6ad39fa052532c56795b733da78a91ebe6a713944b"],"id":1}
```

### 1.13 eth_getTransactionReceipt
```json
{"jsonrpc":"2.0","method":"eth_getTransactionReceipt",
 "params":["0x88df016429689c079f3b2f6ad39fa052532c56795b733da78a91ebe6a713944b"],"id":1}
```

### 1.14 eth_getProof（EIP-1186）
```json
{"jsonrpc":"2.0","method":"eth_getProof","params":[
   "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
   ["0x0000000000000000000000000000000000000000000000000000000000000003",
    "0x0000000000000000000000000000000000000000000000000000000000000004"],
   "latest"
],"id":1}
```
归档节点亲和；rollup/cross-chain 证明类客户端高频使用。

### 1.15 debug_traceTransaction
```json
{"jsonrpc":"2.0","method":"debug_traceTransaction","params":[
   "0x88df016429689c079f3b2f6ad39fa052532c56795b733da78a91ebe6a713944b",
   {
     "tracer":"callTracer",
     "tracerConfig":{"withLog":true,"onlyTopCall":false},
     "timeout":"30s"
   }
],"id":1}
```
- 可选 tracer: `callTracer`、`prestateTracer`、`4byteTracer`、`noopTracer`、自定义 JS。
- 同族：`debug_traceBlockByNumber`、`debug_traceCall`、`trace_block`（Parity 风格 Erigon 支持）。

参考：[ethereum.org JSON-RPC spec](https://ethereum.org/en/developers/docs/apis/json-rpc/)，[Geth debug API](https://geth.ethereum.org/docs/interacting-with-geth/rpc/ns-debug)。

---

## 2. 各方法资源成本画像

| 方法 | CPU | Mem | Disk I/O | Net Out | Archive Only | 备注 |
|---|---|---|---|---|---|---|
| eth_blockNumber | 极低 | 极低 | 0 | ~80B | 否 | header in-mem |
| eth_getBalance(latest) | 低 | 低 | 1-2 trie node | ~100B | 否 | 历史块需 archive |
| eth_getBalance(historical) | 中 | 中 | 数十 trie node | ~100B | 是 | snapshot 失效 |
| eth_getTransactionCount(pending) | 中 | 中 | txpool 扫描 | ~80B | 否 | mempool 锁竞争 |
| eth_getCode | 低 | 低 | 1 code lookup | 100B-24KB | 否 | EIP-170 上限 |
| eth_getStorageAt | 中 | 低 | 3-4 trie node | ~100B | latest 否 | hist 是 |
| **eth_call** | **高** | **高** | **冷态多次 trie I/O** | 64B-数 MB | 视块而定 | EVM 全量执行；state override 进一步增 mem |
| **eth_estimateGas** | **极高** | **高** | 同 eth_call×二分 | ~80B | 否 | 64-bit 二分 7-30 次 call |
| **eth_getLogs** | **高** | **高** | **bloom + 全 receipt 扫描** | KB-MB | 大范围是 | 索引压力大；Erigon `--ots` 较好 |
| eth_feeHistory | 中 | 中 | 顺序 header+receipt | KB | 否 | blockCount 线性 |
| eth_getBlockByNumber(full) | 中 | 中 | 1 block + N tx | 50-300KB | 否 | full=true 显著放大 |
| eth_getBlockByHash | 中 | 中 | hash→num 索引+block | 同上 | 否 | |
| eth_getTransactionByHash | 低 | 低 | tx index | ~500B | 否 | |
| eth_getTransactionReceipt | 中 | 中 | receipt + logs | 0.5-50KB | 否 | post-Byzantium 含 status |
| **eth_getProof** | **高** | **高** | trie 遍历到根 | 5-50KB | 多数 hist 是 | Merkle path 大 |
| **debug_traceTransaction** | **极高** | **极高** | 重放整 block 前序 tx | 1KB-100MB | **是** | prestateTracer 最重 |

---

## 3. eth_getLogs 块范围限制（各 Provider）

| Provider | 默认上限 | 带 topic filter | 无 filter | 响应大小限制 | 来源 |
|---|---|---|---|---|---|
| Alchemy | 10,000 blocks | 10,000 | 2,000 | 150MB / 10,000 logs | [docs.alchemy.com/reference/eth-getlogs](https://docs.alchemy.com/reference/eth-getlogs) |
| Infura | 10,000 blocks | 10,000 | 10,000 | 10,000 logs | [docs.infura.io](https://docs.infura.io/api/networks/ethereum/json-rpc-methods/eth_getlogs) |
| QuickNode | 10,000 blocks (默认) | 可调 | 5 sec timeout | 10,000 results | [quicknode.com/docs/ethereum/eth_getLogs](https://www.quicknode.com/docs/ethereum/eth_getLogs) |
| Cloudflare Web3 | 1,024 blocks | 1,024 | 1,024 | 较保守 | [developers.cloudflare.com/web3](https://developers.cloudflare.com/web3/ethereum-gateway/) |
| Ankr | 3,000 blocks | 3,000 | 3,000 | — | [ankr.com docs](https://www.ankr.com/docs/) |
| BlockPI | 1,024 | 1,024 | 1,024 | — | blockpi 文档 |
| 自建 Geth (默认) | 无硬限 | 无 | `--rpc.evmtimeout 5s` 触发 | — | geth |
| 自建 Erigon | 无硬限 | 无 | timeout | — | erigon |

**推荐 `safety_max_block_range` 默认值**：
- 通用基准：**2000**（兼容 Alchemy 无 topic 场景 + Cloudflare 上限附近）
- 带 topic 高强度：**5000**
- 自建 archive 上限实验：**10000**（同时设置 `request_timeout=30s`）
- 极端 stress 探边：步进 1k→2k→5k→10k→20k，记录每档 p99 / error rate

---

## 4. eth_call calldata 池构造

### 4.1 高频 ERC-20 selector
| Function | Selector | Calldata 模板 |
|---|---|---|
| `totalSupply()` | `0x18160ddd` | `0x18160ddd` |
| `decimals()` | `0x313ce567` | `0x313ce567` |
| `symbol()` | `0x95d89b41` | `0x95d89b41` |
| `name()` | `0x06fdde03` | `0x06fdde03` |
| `balanceOf(address)` | `0x70a08231` | `0x70a08231` + 32B-padded addr |
| `allowance(address,address)` | `0xdd62ed3e` | selector + 2×32B addr |

### 4.2 ERC-721/1155
| Function | Selector |
|---|---|
| `ownerOf(uint256)` | `0x6352211e` |
| `tokenURI(uint256)` | `0xc87b56dd` |
| `balanceOf(address,uint256)` (1155) | `0x00fdd58e` |

### 4.3 DeFi 高价值
| Protocol | Function | Selector |
|---|---|---|
| Uniswap V2 Pair | `getReserves()` | `0x0902f1ac` |
| Uniswap V3 Pool | `slot0()` | `0x3850c7bd` |
| Uniswap V3 Quoter | `quoteExactInputSingle(...)` | `0xf7729d43` |
| Chainlink Aggregator | `latestRoundData()` | `0xfeaf968c` |
| Aave V3 Pool | `getReserveData(address)` | `0x35ea6a75` |
| Compound cToken | `exchangeRateStored()` | `0x182df0f5` |
| Multicall3 | `aggregate3((address,bool,bytes)[])` | `0x82ad56cb` |

### 4.4 calldata 池生成（pure shell + jq）
```bash
pad32(){ printf '%064s' "${1#0x}" | tr ' ' 0; }
build_balanceof(){ echo "0x70a08231$(pad32 "$1")"; }

TOKENS=(0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48 \
        0xdac17f958d2ee523a2206206994597c13d831ec7 \
        0x6b175474e89094c44da98b954eedeac495271d0f)
WALLETS_FILE=hot_wallets.txt
> calldata_pool.jsonl
while read -r W; do
  for T in "${TOKENS[@]}"; do
    D=$(build_balanceof "$W")
    jq -nc --arg to "$T" --arg data "$D" \
       '{to:$to, data:$data}' >> calldata_pool.jsonl
  done
done < "$WALLETS_FILE"
```

### 4.5 行业 fixture 来源
- **Etherscan**：`/api?module=account&action=txlist` 拉取活跃地址；token holder 排行榜
- **Dune Analytics**：SQL `SELECT "to","data" FROM ethereum.traces WHERE call_type='staticcall' AND success ORDER BY block_time DESC LIMIT 1e5`
- **The Graph**：subgraph `uniswap-v3` / `compound-v2` 的 GraphQL 拉取 top accounts/pools
- **Alchemy enhanced API**：`alchemy_getTokenBalances` + `alchemy_getAssetTransfers`

---

## 5. 开源 RPC Benchmark 工具调研

### 5.1 ChainForge (chainbound)
- 仓库：https://github.com/chainbound/chainforge
- 池：启动时拉取 latest N=512 blocks 与其内交易 hash
- 刷新：默认 `pool_refresh_interval = 30s`

### 5.2 paradigm flood (jsonrpcbench)
- 仓库：https://github.com/paradigmxyz/flood
- 默认 10k 采样轮，地址池 1k–10k

### 5.3 Versus (Infura)
- 仓库：https://github.com/INFURA/versus
- 池：CSV-driven，用户预生成调用集，复现性强

### 5.4 推荐池设计（综合）
| 维度 | 推荐值 |
|---|---|
| 池大小 | 5,000-50,000 条记录/方法 |
| 刷新频率 | 每 12s（1 block）增量；每 5 min 整池重生 |
| Hot/Cold | 70% hot (tip-128)、20% warm (tip-10k)、10% cold (随机历史) |
| 去重 | hash 256-bit 去重，避免缓存命中失真 |

---

## 6. v1.3 param_format 扩展建议

baseline `target_generator.sh:67-124` 采用 case 分派。以下扩展全部保持**纯 shell + jq，零新依赖**。

### 6.1 新增 param_format 列表

| 名称 | 适用方法 | 描述 |
|---|---|---|
| `address_block_range` | eth_getLogs | 单 address + fromBlock/toBlock 滑动窗口 |
| `topic_block_range` | eth_getLogs | address + topics[0]=Transfer + 滑动窗口 |
| `multi_topic_filter` | eth_getLogs | 含 OR-list 与 null 通配，模拟 indexer |
| `block_hash_logs` | eth_getLogs | `{"blockHash":"0x..."}` 形态，避开范围 |
| `call_balanceof` | eth_call / estimateGas | ERC-20 balanceOf calldata |
| `call_slot0` | eth_call | Uniswap V3 slot0() |
| `call_multicall3` | eth_call | aggregate3 批量 calldata |
| `call_with_state_override` | eth_call | 含 stateDiff override |
| `fee_history_window` | eth_feeHistory | blockCount + percentile 列表 |
| `block_full_tx` | eth_getBlockByNumber | block + `true` 内联 tx |
| `proof_address_slots` | eth_getProof | address + N 个 slot |
| `trace_tx_calltracer` | debug_traceTransaction | tracer=callTracer + withLog |
| `trace_block_prestate` | debug_traceBlockByNumber | tracer=prestateTracer |
| `tx_hash_pool` | getTransactionByHash/Receipt | 池化 tx hash 抽样 |
| `historical_balance` | eth_getBalance | tip-K 历史块（archive 压测） |

### 6.2 case 分派模板（追加到 target_generator.sh:124 行后）

完整 shell + jq 实现见原报告，关键样例：

```bash
case "$param_format" in
  address_block_range)
    addr=$(shuf -n1 "$ADDR_POOL")
    tip=$(get_tip_block)
    range=${SAFETY_MAX_BLOCK_RANGE:-2000}
    from=$((tip - range))
    jq -nc --arg a "$addr" \
           --arg f "$(printf '0x%x' $from)" \
           --arg t "$(printf '0x%x' $tip)" \
       '[{address:$a, fromBlock:$f, toBlock:$t}]'
    ;;
  call_balanceof)
    token=$(shuf -n1 "$TOKEN_POOL")
    holder=$(shuf -n1 "$ADDR_POOL")
    pad(){ printf '%064s' "${1#0x}" | tr ' ' 0; }
    data="0x70a08231$(pad $holder)"
    jq -nc --arg to "$token" --arg d "$data" \
       '[{to:$to,data:$d},"latest"]'
    ;;
  trace_tx_calltracer)
    tx=$(shuf -n1 "$TX_HASH_POOL")
    jq -nc --arg t "$tx" \
       '[$t,{tracer:"callTracer",tracerConfig:{withLog:true,onlyTopCall:false},timeout:"30s"}]'
    ;;
  historical_balance)
    addr=$(shuf -n1 "$ADDR_POOL")
    tip=$(get_tip_block)
    delta=$(( (RANDOM * RANDOM) % 1000000 + 1 ))
    bn=$(printf '0x%x' $((tip - delta)))
    jq -nc --arg a "$addr" --arg b "$bn" '[$a,$b]'
    ;;
esac
```

### 6.3 池文件约定
| 环境变量 | 内容 |
|---|---|
| `ADDR_POOL` | EOA & holder 地址，每行 1 条，10k+ 推荐 |
| `TOKEN_POOL` | 主流 ERC-20 合约地址，100-500 条 |
| `CONTRACT_POOL` | 任意 verified contracts |
| `UNIV3_POOL_LIST` | Uniswap V3 池地址 |
| `BLOCKHASH_POOL` | 最近 50k 个 block hash |
| `TX_HASH_POOL` | 最近 100k 个 tx hash |
| `SAFETY_MAX_BLOCK_RANGE` | 默认 2000 |

### 6.4 池刷新脚本（cron/systemd timer）
```bash
refresh_pools(){
  local tip=$(get_tip_block)
  for off in $(seq 0 5); do
    bn=$(printf '0x%x' $((tip - off)))
    blk=$(curl -s -X POST -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_getBlockByNumber\",\"params\":[\"$bn\",true],\"id\":1}" "$RPC")
    echo "$blk" | jq -r '.result.hash' >> "$BLOCKHASH_POOL"
    echo "$blk" | jq -r '.result.transactions[].hash' >> "$TX_HASH_POOL"
    echo "$blk" | jq -r '.result.transactions[].from,.result.transactions[].to' \
       | grep -E '^0x[0-9a-fA-F]{40}$' >> "$ADDR_POOL"
  done
  for f in "$BLOCKHASH_POOL" "$TX_HASH_POOL" "$ADDR_POOL"; do
    sort -u "$f" | tail -n 100000 > "$f.tmp" && mv "$f.tmp" "$f"
  done
}
```

---

## 参考来源

1. ethereum.org JSON-RPC: https://ethereum.org/en/developers/docs/apis/json-rpc/
2. EIP-1474 / EIP-1186 / EIP-1898
3. Alchemy eth_getLogs limits: https://docs.alchemy.com/reference/eth-getlogs
4. Infura JSON-RPC: https://docs.infura.io/api/networks/ethereum/json-rpc-methods
5. QuickNode docs: https://www.quicknode.com/docs/ethereum/eth_getLogs
6. Cloudflare Web3 Gateway: https://developers.cloudflare.com/web3/ethereum-gateway/
7. ChainForge: https://github.com/chainbound/chainforge
8. paradigm flood: https://github.com/paradigmxyz/flood
9. Versus (Infura): https://github.com/INFURA/versus
10. Etherscan API / Dune / The Graph
