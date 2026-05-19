# 多链 RPC 复杂参数研究报告 (Solana / Sui / Aptos / Starknet)

> 为 blockchain-node-benchmark v1.3 的 `target_generator.sh` 提供四链生产级压测参数模板, 并给出 `param_format` case-dispatch 扩展建议与 node-killer 防护清单。所有 JSON 样例均来自各链官方 / 主流厂商文档。

---

## 1. Solana — Top 12 RPC 方法

### 1.1 方法清单 (按 RU/CU 成本与压测代表性排序)

| # | method | 典型成本 | 压测意义 | killer 风险 |
|---|---|---|---|---|
| 1 | `getProgramAccounts` (gPA) | 极高 | 全量扫描 + 过滤 | ⚠⚠⚠ 默认禁用 |
| 2 | `getMultipleAccounts` (gMA) | 中-高 | 批量读 (≤100 pubkey) | ⚠ batch_size 上限 |
| 3 | `getAccountInfo` | 低 | 单点读基线 | — |
| 4 | `getBalance` | 极低 | 心跳/对照组 | — |
| 5 | `getSlot` | 极低 | 心跳 | — |
| 6 | `getBlock` | 高 | 区块体 + tx 解码 | ⚠⚠ rewards/full tx |
| 7 | `getBlockHeight` | 极低 | 心跳 | — |
| 8 | `getTransaction` | 中 | 单 tx 详情 | ⚠ maxSupportedTransactionVersion |
| 9 | `getSignaturesForAddress` | 高 | 地址历史扫描 | ⚠⚠ limit≤1000 |
| 10 | `getTokenAccountsByOwner` | 高 | SPL 拥有者扫描 | ⚠⚠ programId 过滤 |
| 11 | `getRecentPrioritizationFees` | 中 | 费用建模 | ⚠ pubkey 数组长度 |
| 12 | `simulateTransaction` | 高 | 写路径模拟 | ⚠⚠⚠ 默认禁用 |

### 1.2 Commitment 等级成本

| commitment | 平均延迟 | 推荐档位 |
|---|---|---|
| `processed` | 1.0× | light 档 |
| `confirmed` | 1.3–1.6× | standard 默认 |
| `finalized` | 1.8–2.5× | strict 档 |

### 1.3 `getProgramAccounts` 深度参数矩阵

```json
{
  "jsonrpc": "2.0", "id": 1,
  "method": "getProgramAccounts",
  "params": [
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    {
      "commitment": "confirmed",
      "encoding": "base64",
      "dataSlice": { "offset": 0, "length": 0 },
      "minContextSlot": 0,
      "withContext": true,
      "filters": [
        { "dataSize": 165 },
        { "memcmp": { "offset": 0, "bytes": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "encoding": "base58" } }
      ]
    }
  ]
}
```

**字段组合矩阵 (压测必覆盖)**:
| filters | encoding | dataSlice | 预期成本 | 备注 |
|---|---|---|---|---|
| 仅 `dataSize` | `base64` | `{offset:0,length:0}` | 中 | 只数账户数 |
| `dataSize` + 1×`memcmp` | `base64` | `{offset:0,length:128}` | 中-高 | 标准业务模式 |
| `dataSize` + 2×`memcmp` | `base64+zstd` | none | 高 | 复合索引 |
| 仅 `memcmp(offset>0)` | `jsonParsed` | none | 极高 | jsonParsed 触发解码 |
| **无 filters** | `base64` | none | 极高/拒绝 | **node-killer, 默认 off** |

**厂商额外约束**:
- Helius: 必须包含至少一个 filter, 否则返回 `-32602`
- Triton One: 强制 `dataSize` 在 filters 第一位以走索引
- QuickNode: `dataSlice` 缺失时 >10 MB 响应会 truncate

### 1.4 `getMultipleAccounts`

```json
{ "jsonrpc": "2.0", "id": 1, "method": "getMultipleAccounts",
  "params": [["vines1vzrYbzLMRdu58ou5XTby4qAqVRLmqo36NKPTg","4fYNw3dojWmQ4dXtSGE9epjRGy9pFSx62YypT7avPYvA"],
    { "commitment": "confirmed", "encoding": "base64", "dataSlice": {"offset":0,"length":0} }] }
```

**硬上限**: `pubkeys` 数组 ≤ **100**. 压测档位: `1 / 5 / 25 / 50 / 100`。

### 1.5 `getSignaturesForAddress`

```json
{ "jsonrpc":"2.0","id":1,"method":"getSignaturesForAddress",
  "params":["Vote111111111111111111111111111111111111111",
    {"limit":1000,"before":null,"until":null,"commitment":"confirmed"}] }
```

`limit` 硬上限 1000. 不带 `before` 时每次都扫尾部.

### 1.6 `getBlock`

```json
{ "jsonrpc":"2.0","id":1,"method":"getBlock",
  "params":[430, {"encoding":"json","maxSupportedTransactionVersion":0,
                  "transactionDetails":"full","rewards":false,"commitment":"confirmed"}] }
```

`transactionDetails`: `full | accounts | signatures | none` 四档成本差异巨大。`rewards=true` + `full` 在投票节点上接近 node-killer。

### 1.7 `getTransaction`

```json
{ "jsonrpc":"2.0","id":1,"method":"getTransaction",
  "params":["<sig_base58>", {"encoding":"jsonParsed","commitment":"confirmed","maxSupportedTransactionVersion":0}] }
```

`encoding`: `json | jsonParsed | base58 | base64` — `jsonParsed` 触发 IDL 反序列化, 成本 2-4×。

### 1.8 `simulateTransaction` (默认 OFF)

```json
{ "jsonrpc":"2.0","id":1,"method":"simulateTransaction",
  "params":["<base64_tx>",
    {"encoding":"base64","commitment":"processed","sigVerify":false,
     "replaceRecentBlockhash":true,
     "accounts":{"encoding":"base64","addresses":["..."]}}] }
```

⚠ 在压测中相当于"每次都重放一笔交易"; 默认 `enabled:false`。

---

## 2. Sui — Top 8 RPC 方法

### 2.1 方法清单
| # | method | 成本 | 用途 |
|---|---|---|---|
| 1 | `sui_getObject` | 低-高 | 取对象 (options 字段决定成本) |
| 2 | `sui_multiGetObjects` | 中-高 | 批量对象 (≤50) |
| 3 | `sui_getCheckpoint` | 中 | checkpoint 详情 |
| 4 | `sui_getTransactionBlock` | 中-高 | tx 详情 |
| 5 | `suix_queryEvents` | 高 | 事件检索 |
| 6 | `suix_queryTransactionBlocks` | 高 | tx 检索 |
| 7 | `suix_getOwnedObjects` | 高 | 地址持有对象扫描 |
| 8 | `sui_getLatestCheckpointSequenceNumber` | 极低 | 心跳 |

### 2.2 `sui_getObject` — options 字段成本

```json
{ "jsonrpc":"2.0","id":1,"method":"sui_getObject",
  "params":["0x1a2b...deadbeef",
    {"showType":true,"showOwner":true,"showPreviousTransaction":false,
     "showDisplay":false,"showContent":true,"showBcs":false,"showStorageRebate":true}] }
```

| options 组合 | 平均成本 |
|---|---|
| 全 false (仅 ref) | 1.0× |
| `showType+showOwner` | 1.1× |
| `+ showContent` | 1.8–3.0× |
| `+ showDisplay` | 2.0–4.0× |
| `+ showBcs` | 1.5× |
| **全 true** | 4–6× (killer 候选) |

### 2.3 `sui_multiGetObjects`

硬上限 **50** 对象/次. 压测档位: `1 / 10 / 25 / 50`。

### 2.4 `suix_queryEvents` — filter 字典

```json
{ "jsonrpc":"2.0","id":1,"method":"suix_queryEvents",
  "params":[{ "MoveEventType":"0x2::coin::CoinMetadata<0x2::sui::SUI>" },
            null, 50, true] }
```

| filter | 样例 | 成本 |
|---|---|---|
| `{ "All": [] }` | 全表 | 极高, killer |
| `{ "Transaction": "<digest>" }` | 单 tx | 低 |
| `{ "MoveModule": {"package":"0x2","module":"coin"} }` | 模块级 | 中 |
| `{ "MoveEventType": "0x2::coin::CoinMetadata<...>" }` | 精确类型 | 中 |
| `{ "Sender": "0x..." }` | 发送者 | 中-高 |
| `{ "TimeRange": {"startTime":"...","endTime":"..."} }` | 时间段 | 高, killer |
| `{ "And": [f1, f2] }` / `{ "Or": [...] }` | 组合 | 视成员 |

`limit` 上限 **1000**, 但生产 RPC 多数限制 50–200。

### 2.5 `suix_queryTransactionBlocks`

```json
{ "jsonrpc":"2.0","id":1,"method":"suix_queryTransactionBlocks",
  "params":[
    { "filter":{"FromAddress":"0xabc..."},
      "options":{"showInput":false,"showEffects":true,"showEvents":false,
                 "showObjectChanges":false,"showBalanceChanges":true} },
    null, 50, true] }
```

`options.showObjectChanges` + `showEvents` 同时开启是已知 killer 组合。

### 2.6 `suix_getOwnedObjects`

```json
{ "jsonrpc":"2.0","id":1,"method":"suix_getOwnedObjects",
  "params":["0xowner...",
    { "filter":{"StructType":"0x2::coin::Coin<0x2::sui::SUI>"},
      "options":{"showType":true,"showOwner":true,"showContent":false} },
    null, 50] }
```

大地址 (DeepBook / Cetus pool) 持有数万对象, 必须强制 `filter`。

---

## 3. Aptos — Top 8 REST 端点

Aptos 的"RPC"实际上是 REST + JSON. 端点遵循 `/v1/...` 路径。

### 3.1 端点清单
| # | METHOD | PATH | 成本 | 用途 |
|---|---|---|---|---|
| 1 | POST | `/v1/view` | 中-极高 | 调用 Move view function |
| 2 | GET | `/v1/accounts/{addr}/resources` | 中-高 | 地址全资源 |
| 3 | GET | `/v1/accounts/{addr}/resource/{type}` | 低 | 单资源 |
| 4 | GET | `/v1/accounts/{addr}/modules` | 中 | 已发布模块 |
| 5 | GET | `/v1/transactions/by_hash/{hash}` | 低 | 单 tx |
| 6 | GET | `/v1/transactions?start=&limit=` | 中-高 | tx 翻页, limit ≤ 100 |
| 7 | GET | `/v1/blocks/by_height/{h}?with_transactions=true` | 高 | 区块+tx |
| 8 | POST | `/v1/transactions/simulate` | 高 | 模拟 (默认 OFF) |

### 3.2 `/v1/view` — view function payload

```json
{
  "function": "0x1::coin::balance",
  "type_arguments": ["0x1::aptos_coin::AptosCoin"],
  "arguments": ["0xabc...def"]
}
```

复杂示例 (LiquidSwap pool 报价):
```json
{
  "function": "0x190d44266241744264b964a37b8f09863167a12d3e70cda39376cfb4e3561e12::scripts::get_amount_out",
  "type_arguments": [
    "0x1::aptos_coin::AptosCoin",
    "0xf22bede237a07e121b56d91a491eb7bcdfd1f5907926a9e58338f964a01b17fa::asset::USDC",
    "0x190d44266241744264b964a37b8f09863167a12d3e70cda39376cfb4e3561e12::curves::Uncorrelated"
  ],
  "arguments": ["1000000"]
}
```

`?ledger_version=<v>` 指定历史快照 — 历史 view 比 latest 贵 3–10×。

### 3.3 其他端点

- `/v1/accounts/{addr}/resources?limit=100&start=0` — limit 上限 9999 但生产硬阈值 100, 大地址 (validator / 0x1) 返回数十 MB
- `/v1/transactions?start=1000000&limit=25` — limit 上限 100, 高 start 命中 archive
- `/v1/blocks/by_height/12345678?with_transactions=true` — 是 killer 开关, 默认 `false`
- `/v1/transactions/simulate` — 默认 OFF

---

## 4. Starknet — Top 8 RPC 方法

### 4.1 方法清单
| # | method | 成本 | 用途 |
|---|---|---|---|
| 1 | `starknet_getEvents` | 高-极高 | 事件检索 |
| 2 | `starknet_call` | 中-高 | view call |
| 3 | `starknet_getStorageAt` | 低 | 存储槽 |
| 4 | `starknet_getClassAt` / `getClassHashAt` | 中 | 合约类 |
| 5 | `starknet_getBlockWithTxs` | 高 | 区块 + tx |
| 6 | `starknet_getBlockWithTxHashes` | 中 | 区块轻量 |
| 7 | `starknet_getTransactionReceipt` | 中 | tx 回执 + events |
| 8 | `starknet_estimateFee` | 高 | 费用估算 (默认 OFF) |

### 4.2 `starknet_getEvents` — 完整过滤矩阵

```json
{
  "jsonrpc":"2.0","id":1,"method":"starknet_getEvents",
  "params":[{
    "filter":{
      "from_block":{"block_number":500000},
      "to_block":"latest",
      "address":"0x049d36570d4e46f48e99674bd3fcc8463d9bf7e7e9b8b3f7f9b3f8b3f8b3f8b3",
      "keys":[ ["0x99cd8bde557814842a3121e8ddfd433a539b8c9f14bf31ebf108d12e6196e9"] ],
      "chunk_size":100,
      "continuation_token":null
    }
  }]
}
```

**关键约束**:
- `keys` 是 **二维数组** — 外层下标对应 event 的 key 位置, 内层是该位置上的 OR 列表
- `chunk_size` 多数 provider (Infura / Alchemy / Nethermind) 强制 ≤ 100
- `address` 可选 — **缺失 + 宽 block range = node-killer**

**压测矩阵**:
| 配置 | 风险 |
|---|---|
| 单合约 + 1 key + 1000 块跨度 + chunk_size=100 | 标准 |
| 单合约 + 无 key + 10000 块跨度 | 高, 警告档 |
| 无 address + 无 key + `from=0, to=latest` | **killer, 默认 OFF** |

### 4.3 `starknet_call`

```json
{ "jsonrpc":"2.0","id":1,"method":"starknet_call",
  "params":[{ "contract_address":"0x049d...",
              "entry_point_selector":"0x39e11d48192e4333233c7eb19d10ad67c362bb28580c604d67884c85da39695",
              "calldata":["0xabc..."] },
            "latest"] }
```

### 4.4 `starknet_estimateFee` (默认 OFF)

每次都跑模拟器, 压测时极易耗尽 sequencer worker pool。

---

## 5. v1.3 `param_format` 扩展建议

baseline `target_generator.sh:67-124` 采用 `case "$param_format" in ... esac` 分派; 以下扩展全部保持 **纯 shell + jq，零新依赖**。

### 5.1 case-dispatch 扩展模式 (按链分函数)

```sh
# --- Solana 复杂参数族 ---
build_solana_params() {
  local method="$1" addr="$2"
  case "$method" in
    getProgramAccounts)
      jq -nc --arg pid "$addr" --arg cm "$COMMITMENT" --argjson ds "$DATA_SIZE" \
            --arg mc "$MEMCMP_BYTES" --argjson off "$MEMCMP_OFFSET" '
        [$pid, {
          commitment:$cm, encoding:"base64",
          dataSlice:{offset:0,length:0},
          filters:[ {dataSize:$ds}, {memcmp:{offset:$off,bytes:$mc,encoding:"base58"}} ]
        }]' ;;
    getMultipleAccounts)
      printf '%s\n' "$PUBKEYS" | shuf -n "$BATCH" | jq -R . | jq -sc --arg cm "$COMMITMENT" '
        [., {commitment:$cm, encoding:"base64", dataSlice:{offset:0,length:128}}]' ;;
    getSignaturesForAddress)
      jq -nc --arg a "$addr" --arg cm "$COMMITMENT" --argjson lim "$LIMIT" \
            --arg before "$BEFORE_CURSOR" '
        [$a, ({limit:$lim, commitment:$cm} + (if $before=="" then {} else {before:$before} end))]' ;;
    getBlock)
      jq -nc --argjson slot "$SLOT" --arg cm "$COMMITMENT" --arg td "$TX_DETAILS" --argjson rw "$REWARDS" '
        [$slot, {encoding:"json", maxSupportedTransactionVersion:0,
                 transactionDetails:$td, rewards:$rw, commitment:$cm}]' ;;
    *) jq -nc --arg a "$addr" '[$a]' ;;
  esac
}

# --- Sui ---
build_sui_params() {
  local method="$1" obj="$2"
  case "$method" in
    sui_getObject)
      jq -nc --arg o "$obj" --argjson sc "$SUI_SHOW_CONTENT" --argjson sd "$SUI_SHOW_DISPLAY" '
        [$o, {showType:true, showOwner:true, showContent:$sc, showDisplay:$sd,
              showBcs:false, showStorageRebate:true}]' ;;
    sui_multiGetObjects)
      printf '%s\n' "$OBJ_IDS" | shuf -n "$BATCH" | jq -R . | jq -sc \
        '[., {showType:true, showOwner:true, showContent:false}]' ;;
    suix_queryEvents)
      jq -nc --arg etype "$EVENT_TYPE" --argjson lim "$LIMIT" \
        '[{MoveEventType:$etype}, null, $lim, true]' ;;
  esac
}

# --- Aptos (REST: 输出 method + path + body 三元组) ---
build_aptos_request() {
  local ep="$1" addr="$2"
  case "$ep" in
    view)
      printf 'POST\t/v1/view\t'
      jq -nc --arg fn "$VIEW_FN" --argjson ta "$VIEW_TYPE_ARGS" --argjson a "$VIEW_ARGS" '
        {function:$fn, type_arguments:$ta, arguments:$a}' ;;
    resources)
      printf 'GET\t/v1/accounts/%s/resources?limit=%d\t\n' "$addr" "$LIMIT" ;;
    block_by_height)
      printf 'GET\t/v1/blocks/by_height/%d?with_transactions=%s\t\n' "$HEIGHT" "$WITH_TX" ;;
  esac
}

# --- Starknet ---
build_starknet_params() {
  local method="$1"
  case "$method" in
    starknet_getEvents)
      jq -nc --arg addr "$CONTRACT" --argjson fb "$FROM_BLOCK" --argjson tb "$TO_BLOCK" \
             --argjson keys "$KEYS_2D" --argjson cs "$CHUNK_SIZE" '
        [{filter:{
          from_block:{block_number:$fb}, to_block:{block_number:$tb},
          address:$addr, keys:$keys, chunk_size:$cs
        }}]' ;;
    starknet_call)
      jq -nc --arg addr "$CONTRACT" --arg sel "$SELECTOR" --argjson cd "$CALLDATA" '
        [{contract_address:$addr, entry_point_selector:$sel, calldata:$cd}, "latest"]' ;;
  esac
}
```

### 5.2 配置面 (config/blockchain_methods.conf)

```sh
# Solana
SOLANA_COMMITMENT_DIST="processed:30,confirmed:60,finalized:10"
SOLANA_GMA_BATCH_SIZES="1,5,25,50,100"
SOLANA_GPA_REQUIRE_FILTER=true
SOLANA_GPA_ENABLED=false
SOLANA_GPA_SAFETY_MAX_RPS=2
SOLANA_GBLOCK_TX_DETAILS_DIST="none:40,signatures:30,accounts:20,full:10"
SOLANA_SIMULATE_TX_ENABLED=false

# Sui
SUI_GETOBJECT_OPTIONS_DIST="ref:30,meta:40,content:25,full:5"
SUI_MULTIGET_BATCH_SIZES="1,10,25,50"
SUI_QUERYEVENTS_REQUIRE_FILTER=true
SUI_GETOWNED_REQUIRE_FILTER=true
SUI_GETOWNED_ENABLED=false

# Aptos
APTOS_RESOURCES_LIMIT_DEFAULT=25
APTOS_RESOURCES_SAFETY_MAX_LIMIT=200
APTOS_BLOCKS_WITH_TX_DIST="false:80,true:20"
APTOS_VIEW_HISTORICAL_LEDGER_ENABLED=false

# Starknet
STARKNET_GETEVENTS_CHUNK_SIZE_MAX=100
STARKNET_GETEVENTS_REQUIRE_ADDRESS_OR_KEY=true
STARKNET_GETEVENTS_BLOCK_RANGE_MAX=10000
STARKNET_ESTIMATE_FEE_ENABLED=false
```

---

## 6. Node-killer 方法清单 (默认 OFF + safety_max_*)

| chain | method / 端点 | killer 触发 | 默认 | safety_max_* |
|---|---|---|---|---|
| Solana | `getProgramAccounts` (无 filter) | filters=[] | OFF | `safety_max_rps=2`, `require_filter=true` |
| Solana | `getProgramAccounts` (jsonParsed) | encoding=jsonParsed && !dataSlice | OFF | `safety_max_rps=5` |
| Solana | `simulateTransaction` | 任何形式 | OFF | `safety_max_rps=5` |
| Solana | `getBlock`(full + rewards=true) | transactionDetails=full && rewards=true | OFF | `safety_max_rps=10` |
| Solana | `getTokenAccountsByOwner` | owner 资产>10k | OFF | `safety_max_owner_size=10000` |
| Solana | `getSignaturesForAddress` (limit=1000) | limit≥500 && before=null | 限流 | `safety_max_rps=20` |
| Sui | `sui_getObject` (showContent+showDisplay+showBcs) | 三项全开 | OFF | `safety_max_rps=10` |
| Sui | `suix_queryEvents` filter=`All:[]` | 全表 | OFF | `require_filter=true` |
| Sui | `suix_getOwnedObjects` 无 filter | filter=null | OFF | `require_filter=true` |
| Sui | `suix_queryTransactionBlocks` showObjectChanges+showEvents | 两项同开 | 限流 | `safety_max_rps=15` |
| Aptos | `/v1/view` historical | ledger_version << latest | OFF | `safety_max_rps=10` |
| Aptos | `/v1/blocks/by_height?with_transactions=true` | flag=true | 限流 | `safety_max_rps=10` |
| Aptos | `/v1/accounts/{0x1}/resources` | 系统地址 + limit>50 | OFF | `safety_max_limit=200` |
| Aptos | `/v1/transactions/simulate` | 任何 | OFF | `safety_max_rps=5` |
| Starknet | `starknet_getEvents` (无 address + 无 key) | filter 全空 | OFF | `require_address_or_key=true` |
| Starknet | `starknet_getEvents` block_range > 10000 | to-from>10000 | OFF | `safety_max_block_range=10000` |
| Starknet | `starknet_estimateFee` | 任何 | OFF | `safety_max_rps=5` |

### 6.1 通用守卫模板

```sh
guard_method() {
  local chain="$1" method="$2"
  local enabled_var="${chain^^}_$(echo "$method" | tr '[:lower:]' '[:upper:]' | tr -c '[:alnum:]' '_')_ENABLED"
  if [[ "${!enabled_var:-true}" == "false" ]]; then
    [[ "$FORCE_KILLER_MODE" == "true" ]] || return 1
  fi
  local rps_var="${chain^^}_$(echo "$method" | tr '[:lower:]' '[:upper:]' | tr -c '[:alnum:]' '_')_SAFETY_MAX_RPS"
  local cap="${!rps_var:-}"
  [[ -n "$cap" && "$CURRENT_RPS" -gt "$cap" ]] && return 1
  return 0
}
```

---

## 7. 引用 (官方文档)

### Solana
- JSON-RPC API 总览: https://solana.com/docs/rpc/http
- commitment 语义: https://solana.com/docs/rpc#configuring-state-commitment
- getProgramAccounts: https://solana.com/docs/rpc/http/getprogramaccounts
- getMultipleAccounts: https://solana.com/docs/rpc/http/getmultipleaccounts
- Helius gPA 注意事项: https://docs.helius.dev/solana-rpc-nodes/getprogramaccounts
- QuickNode gPA: https://www.quicknode.com/docs/solana/getProgramAccounts

### Sui
- Sui JSON-RPC 总览: https://docs.sui.io/sui-api-ref

### Aptos
- Fullnode REST API: https://aptos.dev/en/build/apis/fullnode-rest-api
- OpenAPI 参考: https://aptos.dev/en/build/apis/fullnode-rest-api-reference

### Starknet
- JSON-RPC 规范: https://github.com/starkware-libs/starknet-specs
- API openrpc: https://github.com/starkware-libs/starknet-specs/blob/master/api/starknet_api_openrpc.json
