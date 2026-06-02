# RPC Method & 响应结构 抽象设计(声明式 DSL — 兼容用户配置任意 method)

> **状态**: 设计+全量实测进行中(2026-06-01 立项)。这是长期工程的专门文档。
> 相关: rpc-method-param-research.md(规律发现, 阶段1-4, 已确立 family×param_format 二维规律)是本文档的前置调研。
> 本文档 = 全量实测矩阵(184 method)+ 参数/响应抽象 DSL 设计。

## 0. 🎯 目标(用户 2026-06-01 澄清, 这是北极星)
**让框架兼容【使用者自己配的、我们没预置的】任意 RPC method —— 零代码。**
应用场景: 使用者按业务场景配一个 36 链里没有的新 method, 只填 chain template
(声明参数怎么传 + 响应怎么解), 框架就能正确压测它 + 正确归因/分析, 不改代码。

两个抽象目标:
1. **参数结构抽象**: 不靠 param_format 预定义枚举名(新形态撞上没有的就得改 _build_params 代码),
   而是一套通用的【声明式参数描述】, 用户在 chain template 描述 method 参数
   (几个位置、每个位置类型、地址/区块/哈希填哪)→ 框架据此构造请求。
2. **响应结构抽象**: 用户配的新 method 返回什么结构, 框架声明式地知道怎么解析
   (从响应哪个字段提区块高度/账户/数据), 而非每个 method 在 parse 代码硬编码。

**为什么需要全量实测(方案B)**: 必须先摸全 36 链 184 个 method 的真实参数形态 + 真实响应结构
(public endpoint 实测拿到), 才能归纳出 DSL 要覆盖哪些情况、怎么设计才能兼容未来用户任意配置。
抽样(每 family 1-2 个)不够 —— 那只能验规律存在, 不能保证 DSL 覆盖全部真实形态。

## 1. 现状抽象的不足(rpc-method-param-research.md 已证)
- 参数: 靠 (family, param_format) 二维, param_format 是预定义枚举名(53 种)。新 method 若参数形态不在某族枚举 → 必须改 _build_params 加分支(非零代码)。R1 风险。
- 无校验: 用户声明错 param_format(位置反/类型错)框架静默错(public endpoint 证实位置错=报错)。R2/R3。
- 响应: 各 method parse 逻辑(提 block_height/account 等)散在 adapter 代码, 非声明式。
- = 现状是"预置好的能跑, 用户加全新的要改代码", 不满足目标。

## 2. 方法论(用户强制)
- **每个 method 必须**: 读官方文档理解参数+响应 → public endpoint 实测拿真实请求/响应 → 记录进矩阵。
- 不许只读框架代码推断。不许抽样代替全量。
- public endpoint 实测注意: 限流(sleep)、需真实地址/哈希做参数、记录真实响应 JSON 结构。

## 3. 36链 184 method 全量实测矩阵(逐链逐 method 填)
> 格式(每 method 必记, 这是 DSL 设计的原始数据):
> 链 | family | method | mode | **请求结构体(完整 JSON body, 含每个参数位置的真实值类型)** |
>   **响应结构体(完整 JSON 响应的字段结构, 标出关键字段如 block_height/account/data 的路径)** |
>   官方文档参数说明 | endpoint | 状态
> 状态: ⬜未测 / ✅实测拿到请求+响应结构体 / ⚠️endpoint不可达(需替代/录制)
> **关键: 必须记完整的【请求结构体】和【响应结构体】, 不只是"测了能跑"。**
>   请求结构体 → 归纳参数 DSL; 响应结构体 → 归纳响应解析 DSL。两者都要逐 method 落矩阵。

### 进度: 127 / 184 method 实测 (jsonrpc + bitcoin_jsonrpc + substrate 完成)
(矩阵逐 family 分批填, 见下方各 family 节)

### 3.1 jsonrpc family (16 链, 74 method slots) — 全量实测完成

**公开 endpoint 映射(本批实测所用)**:
| 链 | public endpoint | 备注 |
|---|---|---|
| ethereum | https://ethereum-rpc.publicnode.com | ✅ |
| arbitrum | https://arbitrum-one-rpc.publicnode.com | ✅ |
| avalanche-c | https://avalanche-c-chain-rpc.publicnode.com | ✅ |
| base | https://base-rpc.publicnode.com | ✅ |
| bsc | https://bsc-rpc.publicnode.com | ✅ |
| linea | https://rpc.linea.build | ⚠️ publicnode 不支持 linea_estimateGas, 换官方 endpoint |
| optimism | https://optimism-rpc.publicnode.com | ✅ |
| polygon | https://polygon-bor-rpc.publicnode.com | ✅ |
| scroll | https://scroll-rpc.publicnode.com | ✅ |
| zksync-era | https://mainnet.era.zksync.io | ✅ 官方 |
| solana | https://solana-rpc.publicnode.com | ✅ (getTokenLargestAccounts 受限, 改用 getTokenAccountsByOwner 取真实 token account) |
| sui | https://fullnode.mainnet.sui.io:443 | ✅ 官方 |
| starknet | https://rpc.starknet.lava.build | ⚠️ blastapi 公开端已停用, 换 lava |
| near | https://rpc.mainnet.near.org | ✅ 官方 |
| tron | https://api.trongrid.io | ✅ 官方 (/wallet/* REST + /jsonrpc) |
| avalanche-x | https://api.avax.network/ext/bc/X | ✅ 官方 X-Chain |

**EVM 子族实测(ethereum/arbitrum/avalanche-c/base/bsc/linea/optimism/polygon/scroll/zksync-era — eth_* method 跨链复用同构, 用 ethereum 为主样本 + 各链独有 method 单独实测)**

| 链 | method | param_format | **请求结构体(真实 body)** | **响应结构体(真实, 关键字段路径)** | 官方文档参数 | 状态 |
|---|---|---|---|---|---|---|
| ethereum | eth_getBalance | address_latest | `{jsonrpc,id,method,params:["<addr>","latest"]}` 实测 addr=vitalik.eth | `{result:"0x4ec8826ce34c4d61"}` → 余额=result(hex wei) | p1=address(20B hex); p2=block tag(latest/earliest/pending/hex) | ✅ |
| ethereum | eth_getTransactionCount | address_latest | `params:["<addr>","latest"]` | `{result:"0x1708"}` → nonce=result | p1=address; p2=block tag | ✅ |
| ethereum | eth_blockNumber | no_params | `params:[]` | `{result:"0x180f392"}` → block_height=result(hex) | 无参数 | ✅ |
| ethereum | eth_gasPrice | no_params | `params:[]` | `{result:"0x952da13"}` → gas_price=result | 无参数 | ✅ |
| ethereum/arbitrum/optimism/linea/avalanche-c/zksync | eth_getBlockByNumber | block_number | `params:["latest",false]` | `{result:{number,hash,parentHash,timestamp,gasUsed,transactions:[...],...}}` → block_height=result.number | p1=block(latest/hex); p2=full_tx bool | ✅ |
| arbitrum/optimism | eth_call | eth_call_object_latest | `params:[{to:"<contract>",data:"0x18160ddd"},"latest"]` USDT totalSupply | `{result:"0x...0158de55a1c7950b"}` → data=result(abi-encoded) | p1=tx object{to,data,from?,value?}; p2=block | ✅ |
| arbitrum/optimism | eth_getTransactionReceipt | transaction_hash | `params:["<txhash>"]` 实测 arb 真 tx | `{result:{blockHash,blockNumber,from,to,gasUsed,logs:[...],status,...}}` → status=result.status | p1=tx hash(32B) | ✅ |
| avalanche-c/linea | eth_getTransactionByHash | transaction_hash | `params:["<txhash>"]` 实测 avax 真 tx | `{result:{blockHash,blockNumber,from,to,value,gas,gasPrice,input,nonce,...}}` | p1=tx hash | ✅ |
| linea | linea_estimateGas | eth_call_object(单对象) | `params:[{from,to,value:"0x1"}]` | `{result:{gasLimit:"0x5208",baseFeePerGas:"0x7",priorityFeePerGas:"0x25d1eb6"}}` | p1=tx call object; Linea 专有, 返 3 段 gas | ✅ (官方 endpoint) |
| zksync-era | zks_L1BatchNumber | no_params | `params:[]` | `{result:"0x7cf4c"}` → L1 batch=result | 无参数, zkSync 专有 | ✅ |
| zksync-era | zks_getBlockDetails | block_number_int | `params:[70392372]`(int, 非 hex) | `{result:{number,timestamp,l1BatchNumber,baseSystemContractsHashes:{bootloader,default_aa},...}}` | p1=block number(integer); zkSync 专有 | ✅ |
| base/bsc/polygon/scroll | eth_getBalance/eth_getTransactionCount/eth_blockNumber/eth_gasPrice | 同 ethereum | 同 ethereum(EVM 同构, 各链 connectivity probe 全 OK) | 同 ethereum 结构 | 同 EVM 标准 | ✅ |

**非 EVM jsonrpc 子族实测**

| 链 | method | param_format | **请求结构体(真实)** | **响应结构体(真实, 关键字段)** | 官方参数 | 状态 |
|---|---|---|---|---|---|---|
| solana | getBlockHeight | no_params | `params:[]` | `{result:401847385}` → block_height=result(直接 int) | 无参数 | ✅ |
| solana | getLatestBlockhash | no_params | `params:[]` | `{result:{context:{slot},value:{blockhash,lastValidBlockHeight}}}` → blockhash=result.value.blockhash | 无参数(可选 config) | ✅ |
| solana | getBalance | single_address | `params:["<pubkey>"]` | `{result:{context:{slot},value:1}}` → 余额=result.value(lamports) | p1=pubkey(base58 str); p2=config obj(optional) | ✅ |
| solana | getAccountInfo | single_address | `params:["<pubkey>",{encoding:"base64"}]` | `{result:{context:{slot},value:{data:["<b64>","base64"],executable,lamports,owner,rentEpoch,space}}}` → data=result.value.data | p1=pubkey; p2=config{encoding,commitment...}(optional) | ✅ |
| solana | getTokenAccountBalance | single_address | `params:["<token_account>"]` 实测真 USDC token acct | `{result:{context:{slot},value:{amount:"67345173",decimals:6,uiAmount,uiAmountString}}}` → 余额=result.value.amount | p1=token account pubkey; p2=commitment(optional) | ✅ |
| sui | sui_getChainIdentifier | no_params | `params:[]` | `{result:"35834a8a"}` → chain id=result | 无参数 | ✅ |
| sui | suix_getReferenceGasPrice | no_params | `params:[]` | `{result:"100"}` → gas price=result(str) | 无参数 | ✅ |
| sui | sui_getLatestCheckpointSequenceNumber | no_params | `params:[]` | `{result:"282181872"}` → checkpoint=result(str int) | 无参数 | ✅ |
| sui | sui_getTotalTransactionBlocks | no_params | `params:[]` | `{result:"5272047700"}` → tx count=result(str) | 无参数 | ✅ |
| sui | sui_getObject | address_with_options | `params:["<objectId>",{showType:true,showOwner:true}]` | `{result:{data:{objectId,version,digest,type,owner:{Shared:{initial_shared_version}}}}}` → data=result.data | p1=objectId(hex); p2=options{showType,showOwner,showContent...} | ✅ |
| starknet | starknet_blockNumber | no_params | `params:[]` | `{result:10406390}` → block_height=result(int) | 无参数 | ✅ |
| starknet | starknet_getNonce | latest_address(block在前) | `params:["latest","<contract>"]` | `{result:"0x0"}` → nonce=result | p1=block_id("latest"/{block_number}); p2=contract address | ✅ |
| starknet | starknet_getStorageAt | address_storage_latest | `params:["<contract>","0x0","latest"]` | `{result:"0x0"}` → storage val=result | p1=contract addr; p2=storage key; p3=block_id | ✅ |
| starknet | starknet_getClassAt | latest_address(block在前) | `params:["latest","<contract>"]` | `{result:{abi:"[...]",entry_points_by_type:{...},sierra_program:[...]}}` → class=result | p1=block_id; p2=contract address | ✅ |
| near | block | dict{finality} | `params:{finality:"final"}` | `{result:{author,chunks:[{chunk_hash,...}],header:{height,hash,...}}}` → block_height=result.header.height | dict: {finality}/{block_id} | ✅ |
| near | gas_price | list[null] | `params:[null]` | `{result:{gas_price:"100000000"}}` → gas=result.gas_price | p1=block_id 或 null(最新) | ✅ |
| near | validators | list[null] | `params:[null]` | `{result:{current_validators:[...],current_proposals:[...],...}}` | p1=block_id 或 null | ✅ |
| near | query | dict{request_type,...} | `params:{request_type:"view_account",finality:"final",account_id:"relay.aurora"}` | `{result:{amount,block_hash,block_height,code_hash,locked,storage_usage}}` → account=result | dict dispatcher: request_type 决定子查询(view_account/view_access_key/call_function/view_state...) + finality + 业务参数 | ✅ |
| near | tx | list[tx_hash,signer] | `params:["<tx_hash>","<signer_account_id>"]` 实测真 tx | `{result:{final_execution_status,transaction:{...},receipts_outcome:[...],status}}` | p1=tx hash; p2=sender account_id | ✅ |
| tron | /wallet/getnowblock | HTTP POST(无 body) | `POST /wallet/getnowblock body={}` | `{blockID,block_header:{raw_data:{number,txTrieRoot,witness_address,...}},transactions:[...]}` → block_height=block_header.raw_data.number | HTTP REST, 空 body | ✅ |
| tron | /wallet/getaccount | HTTP POST{address,visible} | `POST body={address:"<base58>",visible:true}` | `{address,balance,create_time,account_resource:{...},...}` → 余额=balance(sun) | body: {address, visible:bool} | ✅ |
| tron | /wallet/triggerconstantcontract | HTTP POST 对象 | `POST body={owner_address,contract_address,function_selector:"totalSupply()",visible:true}` | `{result:{result:true},constant_result:["<hex>"],energy_used,...}` → data=constant_result[0] | body: {owner_address,contract_address,function_selector,parameter?,visible} | ✅ |
| tron | /wallet/gettransactionbyid | HTTP POST{value} | `POST body={value:"<txid>"}` 实测真 tx | `{ret:[{contractRet:"SUCCESS"}],txID,signature:[...],raw_data:{...}}` | body: {value: txid hex} | ✅ |
| tron | eth_blockNumber | jsonrpc(/jsonrpc 路径) | `POST /jsonrpc {jsonrpc,method:"eth_blockNumber",params:[]}` | `{result:"0x4f61f7e"}` → block_height=result | 标准 eth_*, 走 tron 的 /jsonrpc 子路径 | ✅ |
| avalanche-x | avm.getHeight | dict{} | `params:{}` | `{result:{height:"518811"}}` → block_height=result.height | dict 空 | ✅ |
| avalanche-x | avm.getBlockByHeight | dict{height,encoding} | `params:{height:0,encoding:"hex"}` | `{result:{block:"0x...",encoding:"hex"}}` (encoding=json 则 block 为对象{txs,height,time,...}) | dict: {height:int, encoding:"hex"/"json"} | ✅ |
| avalanche-x | avm.getAllBalances | dict{address} | `params:{address:"X-avax1..."}` 实测真 X-addr | `{result:{balances:[{asset:"AVAX",balance:"1210000000"}]}}` → 余额=result.balances[] | dict: {address: bech32 X-addr} | ✅ |
| avalanche-x | avm.getUTXOs | dict{addresses[],limit,encoding} | `params:{addresses:["X-avax1..."],limit:5,encoding:"hex"}` | `{result:{numFetched:"5",utxos:["0x..."],endIndex:{...}}}` → utxos=result.utxos | dict: {addresses:[], limit, encoding} | ✅ |
| avalanche-x | avm.getTx | dict{txID,encoding} | `params:{txID:"<txid>",encoding:"json"}` 实测真 txid | `{result:{tx:{unsignedTx:{networkID,blockchainID,outputs:[...],inputs:[...]}},encoding}}` | dict: {txID, encoding:"hex"/"json"} | ✅ |

**jsonrpc family 实测小结(DSL 原始数据要点)**:
- **参数容器三态**: (a) list 参数 = EVM eth_*/solana/sui/starknet/bitcoin系/near 部分; (b) dict 参数 = near(query/block)/avalanche-x(avm.*); (c) HTTP REST 对象 body = tron(/wallet/*)。**同一 jsonrpc family 内三种参数容器并存** → 参数 DSL 必须能声明"容器类型(list/dict/rest-body)"。
- **位置语义实证**: address_latest=[addr,"latest"](EVM); latest_address=["latest",addr](starknet getNonce/getClassAt, block 在前); address_storage_latest=[addr,key,block]。位置错 = RPC -32602 报错(research §2.5 已证, 本批 starknet 复证 block/addr 顺序)。
- **响应 block_height 提取路径各异**: EVM=result(hex) / solana getBlockHeight=result(int) / near=result.header.height / tron=block_header.raw_data.number / avalanche-x=result.height。**响应 DSL 必须声明 JSON path + 类型(hex/int/str)**。
- **dict 参数的 dispatcher 语义**: near query 用 request_type 字段在一个 method 内分派多种子查询 → 参数 DSL 需支持"固定键 + 动态业务键"混合。
### 3.2 substrate family (5 链, 29 method slots) — 全量实测完成

**公开 endpoint 映射**:
| 链 | public endpoint | 备注 |
|---|---|---|
| polkadot | https://polkadot-rpc.publicnode.com | ✅ Substrate JSON-RPC |
| kusama | https://kusama-rpc.publicnode.com | ✅ |
| acala | https://acala-rpc.aca-api.network (substrate) + https://eth-rpc-acala.aca-api.network (EVM) | ⚠️ eth_* 须走独立 EVM endpoint |
| astar | https://evm.astar.network | ✅ substrate + EVM 同端点 |
| moonbeam | https://moonbeam-rpc.publicnode.com | ✅ substrate + EVM 同端点 |

**协议特征**: Substrate JSON-RPC 2.0, **list 参数**。三链(acala/astar/moonbeam)是 EVM-compat parachain, 混 eth_* method。polkadot 另配 Sidecar REST path 风格 method(走 substrate-api-sidecar 服务, 非节点直连)。

| 链 | method | param_format | **请求结构体(真实)** | **响应结构体(真实, 关键字段)** | 官方参数 | 状态 |
|---|---|---|---|---|---|---|
| acala/astar/kusama/moonbeam/polkadot | system_chain | no_params | `params:[]` | `{result:"Polkadot"}` → chain name=result | 无参数 | ✅ |
| acala/astar/kusama/polkadot | chain_getHeader | no_params | `params:[]` | `{result:{parentHash,number:"0x1e0a8b6",stateRoot,extrinsicsRoot,digest}}` → block_height=result.number(hex) | 无参数(可选 block_hash) | ✅ |
| acala/astar | state_getRuntimeVersion | no_params | `params:[]` | `{result:{specName,implName,specVersion,implVersion,apis:[[hash,ver]...],transactionVersion}}` | 无参数 | ✅ |
| kusama | chain_getFinalizedHead | no_params | `params:[]` | `{result:"0xff021ee6...38da"}` → finalized hash=result | 无参数 | ✅ |
| kusama/moonbeam | system_health | no_params | `params:[]` | `{result:{peers:21,isSyncing:false,shouldHavePeers:true}}` | 无参数 | ✅ |
| kusama | system_properties | no_params | `params:[]` | `{result:{ss58Format:2,tokenDecimals:12,tokenSymbol:"KSM"}}` | 无参数 | ✅ |
| kusama | chain_getBlockHash | [block_number] | `params:[1000000]`(int) | `{result:"0xb267ffd7...c3e7"}` → blockhash=result | p1=block number(int, optional→最新) | ✅ |
| polkadot | account_nextIndex | single_address | `params:["<SS58 addr>"]` | `{result:0}` → nonce=result(int) | p1=SS58 account address | ✅ |
| acala/kusama/polkadot | system_account | single_address | `params:["<SS58 addr>"]` | `{error:{code:-32601,message:"Method not found"}}` | (chain template 声明的) p1=SS58 address | ⚠️ **`system_account` 不是真 Substrate JSON-RPC method**(节点 -32601)。真实读账户余额须 `state_getStorage` + System.Account 存储键, 或走 Sidecar `/accounts/{addr}/balance-info`。**chain template 声明错误的真实发现** → 印证 research R2/R3(无校验 + 声明错静默) |
| astar/moonbeam | eth_getBalance | address_latest | `params:["<addr>","latest"]` | `{result:"0xe6b9bb1ce008f88"}` → 余额=result | EVM 标准 | ✅ (astar/moonbeam EVM compat) |
| acala/astar/moonbeam | eth_chainId | no_params | `params:[]` | `{result:"0x250"}`(astar) / `0x313`(acala) → chain id=result | 无参数 | ✅ (acala 须走 EVM endpoint, substrate 端 -32601) |
| acala/astar/moonbeam | eth_blockNumber | no_params | `params:[]` | `{result:"0xabba96"}` → block_height=result | 无参数 | ✅ (acala 须走 EVM endpoint) |
| moonbeam | eth_gasPrice | no_params | `params:[]` | `{result:"0x746a52880"}` → gas price=result | 无参数 | ✅ |
| polkadot | GET /accounts/{addr}/balance-info | path_addr (Sidecar REST) | `GET /accounts/<SS58>/balance-info` | (Sidecar API) `{at:{hash,height},nonce,tokenSymbol,free,reserved,frozen,...}` → 余额=free | Sidecar path, addr 占位 | ⚠️ 无公开 Sidecar endpoint(Parity 停止公开托管, 须自建 substrate-api-sidecar)。结构按官方 Sidecar API spec |
| polkadot | GET /blocks/{n} | path_height (Sidecar REST) | `GET /blocks/<n>` | (Sidecar) `{number,hash,parentHash,stateRoot,extrinsicsRoot,authorId,extrinsics:[...],...}` → block_height=number | Sidecar path, n=block number | ⚠️ 同上无公开 Sidecar |
| polkadot | GET /pallets/staking/progress | no_params (Sidecar REST) | `GET /pallets/staking/progress` | (Sidecar) `{at,idealValidatorCount,activeEra,...}` | Sidecar path, 无参 | ⚠️ 同上无公开 Sidecar |

**substrate family 实测小结**:
- **Substrate JSON-RPC 2.0 + list 参数**。块高字段 = result.number(hex, chain_getHeader)。
- **🔴 重大发现: `system_account` 是错误声明**(节点返 -32601)。3 条链(acala/kusama/polkadot)的 chain template 都把它当 single_address balance 查询, 但它不是有效 RPC method。真实余额查询须 state_getStorage(storage key)或 Sidecar REST。**直接印证 research R2(声明错无校验)+ R3 风险, 是 DSL 校验/声明能力必须解决的真实案例**。
- **EVM-compat parachain 双端点问题**: acala 的 substrate 端 与 EVM 端是两个 endpoint, eth_* 须走 EVM 端(substrate 端 -32601); astar/moonbeam 单端点兼容两套。**参数 DSL/endpoint 路由需考虑同链多 RPC 命名空间**。
- **polkadot Sidecar REST path**: 3 个 method 是 substrate-api-sidecar 服务的 REST 接口(非节点直连 JSON-RPC), 无公开托管端点。这类 method 的"参数=path 占位 + 响应=Sidecar JSON"形态与 rest family 一致, 是 DSL path-based 参数的又一形态。
### 3.3 tendermint family (5 链)
(待填)
### 3.4 bitcoin_jsonrpc family (4 链, 24 method slots) — 全量实测完成

**公开 endpoint 映射**:
| 链 | public endpoint | 备注 |
|---|---|---|
| bitcoin | https://bitcoin-rpc.publicnode.com | ✅ 免认证 |
| dogecoin | https://dogecoin.drpc.org | ✅ 免认证 |
| litecoin | https://litecoin-mainnet.gateway.tatum.io | ⚠️ Tatum 免费 5 req/min, 实测时降速 14s/req 绕限流 |
| bch | https://bitcoin-cash-mainnet.gateway.tatum.io | ⚠️ 同 Tatum 限流 |

**协议特征**: Bitcoin Core JSON-RPC 1.0(`jsonrpc:"1.0"`, 注意 doge 节点返 `2.0`)。**list 参数**。带 HTTP Basic Auth(公开节点免认证, 真实部署需 rpcuser/rpcpassword)。

| 链 | method | param_format | **请求结构体(真实)** | **响应结构体(真实, 关键字段)** | 官方参数 | 状态 |
|---|---|---|---|---|---|---|
| bitcoin/bch/dogecoin/litecoin | getblockcount | no_params | `params:[]` | `{result:952086,error:null}` → block_height=result(int) | 无参数 | ✅ |
| bitcoin/dogecoin/litecoin | getbestblockhash | no_params | `params:[]` | `{result:"00000...af3a0"}` → blockhash=result(hex str) | 无参数 | ✅ |
| bitcoin/bch/dogecoin/litecoin | getblock | [blockhash] / [blockhash,verbosity] | `params:["<blockhash>"]` (默认 verbosity=1 返对象; verbosity=0 返 hex; =2 含 tx 详情) | `{result:{hash,confirmations,height,version,merkleroot,time,nonce,bits,difficulty,tx:[...txids],previousblockhash,...}}` → block_height=result.height | p1=blockhash(hex); p2=verbosity(0/1/2 optional) | ✅ |
| bitcoin/bch/dogecoin/litecoin | getrawtransaction | [txid,verbose] | `params:["<txid>",true]` (verbose=true 返对象; false/0 返 hex) | `{result:{txid,hash,version,size,vsize,weight,locktime,vin:[...],vout:[...],hex,blockhash?,confirmations?}}` | p1=txid(hex); p2=verbose(bool/int optional) | ✅ (bitcoin/doge/litecoin 实测; bch 端 429 限流, 结构同 family) |
| bitcoin | getrawmempool | no_params | `params:[]` | `{result:["txid1","txid2",...]}` → mempool txids 数组 | 无参数(可选 verbose bool) | ✅ |
| bitcoin | estimatesmartfee | [conf_target] | `params:[6]` | `{result:{feerate:1.013e-05,blocks:6}}` → feerate=result.feerate | p1=conf_target(int blocks); p2=estimate_mode(optional) | ✅ |
| bitcoin/bch/dogecoin/litecoin | getreceivedbyaddress | single_address | `params:["<address>"]` | `{error:{code:-32701,message:"Method getreceivedbyaddress is not allowed..."}}` | p1=address; p2=minconf(optional) | ⚠️ **wallet 方法, 共享公开节点禁用**(需节点本地 wallet)。结构按官方: 返 result=金额(BTC float)。本类 method 无法在公开节点实测, 真实部署有 wallet 时可用 |
| bch | getnetworkinfo | no_params | `params:[]` | `{result:{version,subversion:"/Bitcoin Cash Node:29.0.0.../",protocolversion,localservices,connections,relayfee,networks:[...],...}}` | 无参数 | ✅ |
| bch/dogecoin/litecoin | getmempoolinfo | no_params | `params:[]` | `{result:{loaded,size:118,bytes,usage,maxmempool,mempoolminfee,minrelaytxfee}}` → mempool_size=result.size | 无参数 | ✅ |

**bitcoin_jsonrpc family 实测小结**:
- **统一 list 参数 + Bitcoin Core 1.0 envelope**。响应统一 `{result,error,id}`, block_height 路径统一 = result(getblockcount) 或 result.height(getblock)。最规律的 family。
- **verbosity/verbose 第二参控制响应形态**(hex vs 对象): getblock verbosity 0/1/2、getrawtransaction verbose bool。**参数 DSL 需支持"可选枚举型控制参数"**(影响响应结构)。
- **wallet 类 method(getreceivedbyaddress)在共享公开节点结构性不可达**(-32701)= 真实约束, 非 endpoint 问题。这类需节点本地 wallet, 全 4 链同。
- doge 节点 envelope 返 `jsonrpc:"2.0"`(请求发 1.0), 实测节点对 envelope 版本宽容。
### 3.5 rest family (5 链)
(待填)
### 3.6 hedera_dual family (1 链)
(待填)

## 4. 参数结构抽象 DSL 设计(全量实测后归纳)
(空 — 待矩阵填全后, 从真实形态归纳出能兼容任意 method 的声明式参数 DSL)

## 5. 响应结构抽象 DSL 设计(全量实测后归纳)
(空 — 待矩阵填全后, 归纳响应解析 DSL: 怎么声明从响应提取 block_height/account/data 等)

## 6. 实现方案(设计审过后)
### 6.1 代码重构面评估(2026-06-01, DSL 落地要动的层)
**参数构造链(参数 DSL 落点)**:
- `tools/chain_adapters/{jsonrpc,substrate,tendermint,bitcoin_jsonrpc,rest,hedera_dual}.py` 各自的 `_build_params`/`build_vegeta_target` — 现在是 param_format 枚举 if-else, DSL 化后改成读 chain template 的声明式参数描述构造。
- `tools/chain_adapters/cli.py` `_get_param_format`(L28-56)— param_format 读取入口, fallback single_address。DSL 后改读新声明字段。
- `tools/chain_adapters/base.py` — Handler 接口契约, 可能加 DSL 解析公共方法。
**响应解析链(响应 DSL 落点)**:
- 同 6 个 adapter 的 `parse_block_height` / `extract_accounts_from_transaction`(solana 在 jsonrpc 系)— 现硬编码响应字段路径, DSL 后改读声明式响应字段路径。
**chain template schema(DSL 声明处)**:
- 现有字段: `param_formats`(method→枚举名)/ `_meta.rest_paths`(rest 的 path+body)/ `proxy_extraction`(proxy method 提取 DSL, 已是声明式!可借鉴)/ `params` / `rpc_methods`。
- DSL 新增: 参数描述字段(替代/扩展 param_formats)+ 响应字段路径描述。**proxy_extraction 已是 declarative DSL(protocol/method_source/params_source 等), 是设计参考样板。**
**向后兼容**: 现有 36 链 param_format 不能破坏 — DSL 与 param_format 并存或 DSL 覆盖枚举(枚举作 DSL 的预设快捷)。
**fake-node 侧(响应 fixture)**: tools/fake-node/ handlers(7 go)+ record_*.sh(5 个)— 实测拿到的响应结构体可同时更新 fixture, 让 fake-node 数据更真(顺带解 A 阶段 fake-node 数据退化)。
### 6.2 实现(设计审过后, 待办)
(空)

## 7. 执行日志(时间倒序)
### 2026-06-01 立项
- 用户澄清目标: 不是验现有 method 能跑, 是设计 DSL 让用户配任意新 method 零代码兼容。
- 确认 36 链 184 method 需全量实测(public endpoint + 官方文档)。
- 建本文档。前置规律(family×param_format)见 rpc-method-param-research.md 阶段4。
- 下一步: 逐 family 实测填矩阵(从 jsonrpc 16 链开始)。
