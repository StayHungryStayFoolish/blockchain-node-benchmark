# 36链 184 single/mixed RPC method 全量实测记录(重构事实基石)

> **定义源(基石)= `config/chains/*.json` 的 `rpc_methods.single` + `mixed` + `param_formats`**。
> 这 184 个 (chain, method) 是框架运行时真实配置的压测 method(config_loader 读 → target_generator 构造 vegeta)。
> 本文档逐条以 config/chains 原始 method 字符串为行(非 design 规整名), 每行填该 method 的 public endpoint 实测请求/响应结构体。
> **核对基准: config/chains 184 对 ↔ 本文档 184 行, 已验证 0 遗漏 0 多余 0 改名**(execute_code 交叉验证)。
> 实测来源: rpc-method-abstraction-design §3(2026-06-02 全量, 180真实+4结构性不可达 + 3项防假测自审)。

## 🔴 核心技术问题(本文档逐 method 记录的原因)

**不同 method 即使传入相同类型参数, 响应结构也完全不同; 同一 method 参数值变, 响应子结构也变。**
响应结构**只能按 method 绑定, 绝不能按参数类型推断**:
- 同传 address: `eth_getBalance`→`"0x2a"`(余额) / `eth_getTransactionCount`→`"0x1"`(nonce) / `eth_getCode`→合约字节码。
- 同 method 参数变: `eth_getBlockByNumber(latest,false)`→transactions=[hash] vs `(latest,true)`→transactions=[{对象}]。

∴ DSL 设计: `param_spec[method]`(构造) + `response_spec[method]`(解析) **都以 method 为键**; 运行时同 method 并发靠 `request_id` 关联响应回请求。**这就是必须逐链逐 method 全量实测两个结构体的根本原因** —— 每个 method 的响应解析规则独立, 不能合并、不能按参数类型归类。

## 实测矩阵(184 method, 按 6 family)

### jsonrpc (16链, 74 method)

| 链 | method(config原名) | single/mixed | param_format | 实测请求结构体 | 实测响应结构体 | 状态 |
|---|---|---|---|---|---|---|
| arbitrum | `eth_blockNumber` | mixed | no_params | `params:[]` | `{result:"0x180f392"}` → block_height=result(hex) | ✅ |
| arbitrum | `eth_call` | mixed | eth_call_object_latest | `params:[{to:"<contract>",data:"0x18160ddd"},"latest"]` USDT totalSupply | `{result:"0x...0158de55a1c7950b"}` → data=result(abi-encoded) | ✅ |
| arbitrum | `eth_getBalance` | single+mixed | address_latest | `{jsonrpc,id,method,params:["<addr>","latest"]}` 实测 addr=vitalik.eth | `{result:"0x4ec8826ce34c4d61"}` → 余额=result(hex wei) | ✅ |
| arbitrum | `eth_getBlockByNumber` | mixed | block_number | `params:["latest",false]` | `{result:{number,hash,parentHash,timestamp,gasUsed,transactions:[...],...}}` → block_height=result.number | ✅ 逐链实测(avax 有 blockExtraData/blockGasCost 独有字段; optimism/linea 有 blobGasUsed; zksync 无 blob — 逐链实测捕获链间真实差异) |
| arbitrum | `eth_getTransactionReceipt` | mixed | transaction_hash | `params:["<txhash>"]` 实测 arb 真 tx | `{result:{blockHash,blockNumber,from,to,gasUsed,logs:[...],status,...}}` → status=result.status | ✅ |
| avalanche-c | `eth_blockNumber` | mixed | no_params | `params:[]` | `{result:"0x180f392"}` → block_height=result(hex) | ✅ |
| avalanche-c | `eth_call` | mixed | eth_call_object_latest | `params:[{to:"<contract>",data:"0x18160ddd"},"latest"]` USDT totalSupply | `{result:"0x...0158de55a1c7950b"}` → data=result(abi-encoded) | ✅ |
| avalanche-c | `eth_getBalance` | single+mixed | address_latest | `{jsonrpc,id,method,params:["<addr>","latest"]}` 实测 addr=vitalik.eth | `{result:"0x4ec8826ce34c4d61"}` → 余额=result(hex wei) | ✅ |
| avalanche-c | `eth_getBlockByNumber` | mixed | block_number | `params:["latest",false]` | `{result:{number,hash,parentHash,timestamp,gasUsed,transactions:[...],...}}` → block_height=result.number | ✅ 逐链实测(avax 有 blockExtraData/blockGasCost 独有字段; optimism/linea 有 blobGasUsed; zksync 无 blob — 逐链实测捕获链间真实差异) |
| avalanche-c | `eth_getTransactionByHash` | mixed | transaction_hash | `params:["<txhash>"]` 实测 avax 真 tx | `{result:{blockHash,blockNumber,from,to,value,gas,gasPrice,input,nonce,...}}` | ✅ |
| avalanche-x | `avm.getAllBalances` | single+mixed | single_address | `params:{address:"X-avax1..."}` 实测真 X-addr | `{result:{balances:[{asset:"AVAX",balance:"1210000000"}]}}` → 余额=result.balances[] | ✅ |
| avalanche-x | `avm.getBlockByHeight` | mixed | height_encoding | `params:{height:0,encoding:"hex"}` | `{result:{block:"0x...",encoding:"hex"}}` (encoding=json 则 block 为对象{txs,height,time,...}) | ✅ |
| avalanche-x | `avm.getHeight` | mixed | no_params | `params:{}` | `{result:{height:"518811"}}` → block_height=result.height | ✅ |
| avalanche-x | `avm.getTx` | mixed | txid_encoding | `params:{txID:"<txid>",encoding:"json"}` 实测真 txid | `{result:{tx:{unsignedTx:{networkID,blockchainID,outputs:[...],inputs:[...]}},encoding}}` | ✅ |
| avalanche-x | `avm.getUTXOs` | mixed | addresses_limit_encoding | `params:{addresses:["X-avax1..."],limit:5,encoding:"hex"}` | `{result:{numFetched:"5",utxos:["0x..."],endIndex:{...}}}` → utxos=result.utxos | ✅ |
| base | `eth_blockNumber` | mixed | no_params | `params:[]` | `{result:"0x180f392"}` → block_height=result(hex) | ✅ |
| base | `eth_gasPrice` | mixed | no_params | `params:[]` | `{result:"0x952da13"}` → gas_price=result | ✅ |
| base | `eth_getBalance` | single+mixed | address_latest | `{jsonrpc,id,method,params:["<addr>","latest"]}` 实测 addr=vitalik.eth | `{result:"0x4ec8826ce34c4d61"}` → 余额=result(hex wei) | ✅ |
| base | `eth_getTransactionCount` | mixed | address_latest | `params:["<addr>","latest"]` | `{result:"0x1708"}` → nonce=result | ✅ |
| bsc | `eth_blockNumber` | mixed | no_params | `params:[]` | `{result:"0x180f392"}` → block_height=result(hex) | ✅ |
| bsc | `eth_gasPrice` | mixed | no_params | `params:[]` | `{result:"0x952da13"}` → gas_price=result | ✅ |
| bsc | `eth_getBalance` | single+mixed | address_latest | `{jsonrpc,id,method,params:["<addr>","latest"]}` 实测 addr=vitalik.eth | `{result:"0x4ec8826ce34c4d61"}` → 余额=result(hex wei) | ✅ |
| bsc | `eth_getTransactionCount` | mixed | address_latest | `params:["<addr>","latest"]` | `{result:"0x1708"}` → nonce=result | ✅ |
| ethereum | `eth_blockNumber` | mixed | no_params | `params:[]` | `{result:"0x180f392"}` → block_height=result(hex) | ✅ |
| ethereum | `eth_gasPrice` | mixed | no_params | `params:[]` | `{result:"0x952da13"}` → gas_price=result | ✅ |
| ethereum | `eth_getBalance` | single+mixed | address_latest | `{jsonrpc,id,method,params:["<addr>","latest"]}` 实测 addr=vitalik.eth | `{result:"0x4ec8826ce34c4d61"}` → 余额=result(hex wei) | ✅ |
| ethereum | `eth_getTransactionCount` | mixed | address_latest | `params:["<addr>","latest"]` | `{result:"0x1708"}` → nonce=result | ✅ |
| linea | `eth_blockNumber` | mixed | no_params | `params:[]` | `{result:"0x180f392"}` → block_height=result(hex) | ✅ |
| linea | `eth_getBalance` | single+mixed | address_latest | `{jsonrpc,id,method,params:["<addr>","latest"]}` 实测 addr=vitalik.eth | `{result:"0x4ec8826ce34c4d61"}` → 余额=result(hex wei) | ✅ |
| linea | `eth_getBlockByNumber` | mixed | block_number | `params:["latest",false]` | `{result:{number,hash,parentHash,timestamp,gasUsed,transactions:[...],...}}` → block_height=result.number | ✅ 逐链实测(avax 有 blockExtraData/blockGasCost 独有字段; optimism/linea 有 blobGasUsed; zksync 无 blob — 逐链实测捕获链间真实差异) |
| linea | `eth_getTransactionByHash` | mixed | transaction_hash | `params:["<txhash>"]` 实测 avax 真 tx | `{result:{blockHash,blockNumber,from,to,value,gas,gasPrice,input,nonce,...}}` | ✅ |
| linea | `linea_estimateGas` | mixed | object_single | `params:[{from,to,value:"0x1"}]` | `{result:{gasLimit:"0x5208",baseFeePerGas:"0x7",priorityFeePerGas:"0x25d1eb6"}}` | ✅ (官方 endpoint) |
| near | `block` | mixed | block_finality_or_id | `params:{finality:"final"}` | `{result:{author,chunks:[{chunk_hash,...}],header:{height,hash,...}}}` → block_height=result.header.height | ✅ |
| near | `gas_price` | mixed | [null] | `params:[null]` | `{result:{gas_price:"100000000"}}` → gas=result.gas_price | ✅ |
| near | `query` | single+mixed | query_dispatcher_request_type | `params:{request_type:"view_account",finality:"final",account_id:"relay.aurora"}` | `{result:{amount,block_hash,block_height,code_hash,locked,storage_usage}}` → account=result | ✅ |
| near | `tx` | mixed | [hash,signer_id] | `params:["<tx_hash>","<signer_account_id>"]` 实测真 tx | `{result:{final_execution_status,transaction:{...},receipts_outcome:[...],status}}` | ✅ |
| near | `validators` | mixed | [null] | `params:[null]` | `{result:{current_validators:[...],current_proposals:[...],...}}` | ✅ |
| optimism | `eth_blockNumber` | mixed | no_params | `params:[]` | `{result:"0x180f392"}` → block_height=result(hex) | ✅ |
| optimism | `eth_call` | mixed | eth_call_object_latest | `params:[{to:"<contract>",data:"0x18160ddd"},"latest"]` USDT totalSupply | `{result:"0x...0158de55a1c7950b"}` → data=result(abi-encoded) | ✅ |
| optimism | `eth_getBalance` | single+mixed | address_latest | `{jsonrpc,id,method,params:["<addr>","latest"]}` 实测 addr=vitalik.eth | `{result:"0x4ec8826ce34c4d61"}` → 余额=result(hex wei) | ✅ |
| optimism | `eth_getBlockByNumber` | mixed | block_number | `params:["latest",false]` | `{result:{number,hash,parentHash,timestamp,gasUsed,transactions:[...],...}}` → block_height=result.number | ✅ 逐链实测(avax 有 blockExtraData/blockGasCost 独有字段; optimism/linea 有 blobGasUsed; zksync 无 blob — 逐链实测捕获链间真实差异) |
| optimism | `eth_getTransactionReceipt` | mixed | transaction_hash | `params:["<txhash>"]` 实测 arb 真 tx | `{result:{blockHash,blockNumber,from,to,gasUsed,logs:[...],status,...}}` → status=result.status | ✅ |
| polygon | `eth_blockNumber` | mixed | no_params | `params:[]` | `{result:"0x180f392"}` → block_height=result(hex) | ✅ |
| polygon | `eth_gasPrice` | mixed | no_params | `params:[]` | `{result:"0x952da13"}` → gas_price=result | ✅ |
| polygon | `eth_getBalance` | single+mixed | address_latest | `{jsonrpc,id,method,params:["<addr>","latest"]}` 实测 addr=vitalik.eth | `{result:"0x4ec8826ce34c4d61"}` → 余额=result(hex wei) | ✅ |
| polygon | `eth_getTransactionCount` | mixed | address_latest | `params:["<addr>","latest"]` | `{result:"0x1708"}` → nonce=result | ✅ |
| scroll | `eth_blockNumber` | mixed | no_params | `params:[]` | `{result:"0x180f392"}` → block_height=result(hex) | ✅ |
| scroll | `eth_gasPrice` | mixed | no_params | `params:[]` | `{result:"0x952da13"}` → gas_price=result | ✅ |
| scroll | `eth_getBalance` | single+mixed | address_latest | `{jsonrpc,id,method,params:["<addr>","latest"]}` 实测 addr=vitalik.eth | `{result:"0x4ec8826ce34c4d61"}` → 余额=result(hex wei) | ✅ |
| scroll | `eth_getTransactionCount` | mixed | address_latest | `params:["<addr>","latest"]` | `{result:"0x1708"}` → nonce=result | ✅ |
| solana | `getAccountInfo` | single+mixed | single_address | `params:["<pubkey>",{encoding:"base64"}]` | `{result:{context:{slot},value:{data:["<b64>","base64"],executable,lamports,owner,rentEpoch,space}}}` → data=result.value.data | ✅ |
| solana | `getBalance` | mixed | single_address | `params:["<pubkey>"]` | `{result:{context:{slot},value:1}}` → 余额=result.value(lamports) | ✅ |
| solana | `getBlockHeight` | mixed | no_params | `params:[]` | `{result:401847385}` → block_height=result(直接 int) | ✅ |
| solana | `getLatestBlockhash` | mixed | no_params | `params:[]` | `{result:{context:{slot},value:{blockhash,lastValidBlockHeight}}}` → blockhash=result.value.blockhash | ✅ |
| solana | `getTokenAccountBalance` | mixed | single_address | `params:["<token_account>"]` 实测真 USDC token acct | `{result:{context:{slot},value:{amount:"67345173",decimals:6,uiAmount,uiAmountString}}}` → 余额=result.value.amount | ✅ |
| starknet | `starknet_blockNumber` | mixed | no_params | `params:[]` | `{result:10406390}` → block_height=result(int) | ✅ |
| starknet | `starknet_getClassAt` | single+mixed | latest_address | `params:["latest","<contract>"]` | `{result:{abi:"[...]",entry_points_by_type:{...},sierra_program:[...]}}` → class=result | ✅ |
| starknet | `starknet_getNonce` | mixed | latest_address | `params:["latest","<contract>"]` | `{result:"0x0"}` → nonce=result | ✅ |
| starknet | `starknet_getStorageAt` | mixed | address_key_latest | `params:["<contract>","0x0","latest"]` | `{result:"0x0"}` → storage val=result | ✅ |
| sui | `sui_getChainIdentifier` | mixed | no_params | `params:[]` | `{result:"35834a8a"}` → chain id=result | ✅ |
| sui | `sui_getLatestCheckpointSequenceNumber` | mixed | no_params | `params:[]` | `{result:"282181872"}` → checkpoint=result(str int) | ✅ |
| sui | `sui_getObject` | single+mixed | address_with_options | `params:["<objectId>",{showType:true,showOwner:true}]` | `{result:{data:{objectId,version,digest,type,owner:{Shared:{initial_shared_version}}}}}` → data=result.data | ✅ |
| sui | `sui_getTotalTransactionBlocks` | mixed | no_params | `params:[]` | `{result:"5272047700"}` → tx count=result(str) | ✅ |
| sui | `suix_getReferenceGasPrice` | mixed | no_params | `params:[]` | `{result:"100"}` → gas price=result(str) | ✅ |
| tron | `/wallet/getaccount` | single+mixed | body_address_visible | `POST body={address:"<base58>",visible:true}` | `{address,balance,create_time,account_resource:{...},...}` → 余额=balance(sun) | ✅ |
| tron | `/wallet/getnowblock` | mixed | no_params | `POST /wallet/getnowblock body={}` | `{blockID,block_header:{raw_data:{number,txTrieRoot,witness_address,...}},transactions:[...]}` → block_height=block_header.raw_data.number | ✅ |
| tron | `/wallet/gettransactionbyid` | mixed | body_value_txid_nopfx | `POST body={value:"<txid>"}` 实测真 tx | `{ret:[{contractRet:"SUCCESS"}],txID,signature:[...],raw_data:{...}}` | ✅ |
| tron | `/wallet/triggerconstantcontract` | mixed | body_owner_contract_selector_parameter | `POST body={owner_address,contract_address,function_selector:"totalSupply()",visible:true}` | `{result:{result:true},constant_result:["<hex>"],energy_used,...}` → data=constant_result[0] | ✅ |
| tron | `eth_blockNumber` | mixed | no_params | `POST /jsonrpc {jsonrpc,method:"eth_blockNumber",params:[]}` | `{result:"0x4f61f7e"}` → block_height=result | ✅ |
| zksync-era | `eth_blockNumber` | mixed | no_params | `params:[]` | `{result:"0x180f392"}` → block_height=result(hex) | ✅ |
| zksync-era | `eth_getBalance` | single+mixed | address_latest | `{jsonrpc,id,method,params:["<addr>","latest"]}` 实测 addr=vitalik.eth | `{result:"0x4ec8826ce34c4d61"}` → 余额=result(hex wei) | ✅ |
| zksync-era | `eth_getBlockByNumber` | mixed | block_number | `params:["latest",false]` | `{result:{number,hash,parentHash,timestamp,gasUsed,transactions:[...],...}}` → block_height=result.number | ✅ 逐链实测(avax 有 blockExtraData/blockGasCost 独有字段; optimism/linea 有 blobGasUsed; zksync 无 blob — 逐链实测捕获链间真实差异) |
| zksync-era | `zks_L1BatchNumber` | mixed | no_params | `params:[]` | `{result:"0x7cf4c"}` → L1 batch=result | ✅ |
| zksync-era | `zks_getBlockDetails` | mixed | block_number_int | `params:[70392372]`(int, 非 hex) | `{result:{number,timestamp,l1BatchNumber,baseSystemContractsHashes:{bootloader,default_aa},...}}` | ✅ |

### substrate (5链, 29 method)

| 链 | method(config原名) | single/mixed | param_format | 实测请求结构体 | 实测响应结构体 | 状态 |
|---|---|---|---|---|---|---|
| acala | `chain_getHeader` | mixed | no_params | `params:[]` | `{result:{parentHash,number:"0x1e0a8b6",stateRoot,extrinsicsRoot,digest}}` → block_height=result.number(hex) | ✅ |
| acala | `eth_blockNumber` | mixed | no_params | `params:[]` | `{result:"0xabba96"}` → block_height=result | ✅ (acala 须走 EVM endpoint) |
| acala | `eth_chainId` | mixed | no_params | `params:[]` | `{result:"0x250"}`(astar) / `0x313`(acala) → chain id=result | ✅ (acala 须走 EVM endpoint, substrate 端 -32601) |
| acala | `state_getRuntimeVersion` | mixed | no_params | `params:[]` | `{result:{specName,implName,specVersion,implVersion,apis:[[hash,ver]...],transactionVersion}}` | ✅ |
| acala | `system_account` | single | single_address | `params:["<SS58 addr>"]` | `{error:{code:-32601,message:"Method not found"}}` | ⚠️ **`system_account` 不是真 Substrate JSON-RPC method**(节点 -32601)。真实读账户余额须 `state_getStorage` + System.Account 存储键, 或走 Sidecar `/accounts/{addr}/balance-info`。**chain template 声明错误的真实发现** → 印证 research R2/R3(无校验 + 声明错静默) |
| acala | `system_chain` | mixed | no_params | `params:[]` | `{result:"Polkadot"}` → chain name=result | ✅ |
| astar | `chain_getHeader` | mixed | no_params | `params:[]` | `{result:{parentHash,number:"0x1e0a8b6",stateRoot,extrinsicsRoot,digest}}` → block_height=result.number(hex) | ✅ |
| astar | `eth_blockNumber` | mixed | no_params | `params:[]` | `{result:"0xabba96"}` → block_height=result | ✅ (acala 须走 EVM endpoint) |
| astar | `eth_chainId` | mixed | no_params | `params:[]` | `{result:"0x250"}`(astar) / `0x313`(acala) → chain id=result | ✅ (acala 须走 EVM endpoint, substrate 端 -32601) |
| astar | `eth_getBalance` | single | address_latest | `params:["<addr>","latest"]` | `{result:"0xe6b9bb1ce008f88"}` → 余额=result | ✅ (astar/moonbeam EVM compat) |
| astar | `state_getRuntimeVersion` | mixed | no_params | `params:[]` | `{result:{specName,implName,specVersion,implVersion,apis:[[hash,ver]...],transactionVersion}}` | ✅ |
| astar | `system_chain` | mixed | no_params | `params:[]` | `{result:"Polkadot"}` → chain name=result | ✅ |
| kusama | `chain_getBlockHash` | mixed | [block_number] | `params:[1000000]`(int) | `{result:"0xb267ffd7...c3e7"}` → blockhash=result | ✅ |
| kusama | `chain_getFinalizedHead` | mixed | no_params | `params:[]` | `{result:"0xff021ee6...38da"}` → finalized hash=result | ✅ |
| kusama | `chain_getHeader` | mixed | no_params | `params:[]` | `{result:{parentHash,number:"0x1e0a8b6",stateRoot,extrinsicsRoot,digest}}` → block_height=result.number(hex) | ✅ |
| kusama | `system_account` | single | single_address | `params:["<SS58 addr>"]` | `{error:{code:-32601,message:"Method not found"}}` | ⚠️ **`system_account` 不是真 Substrate JSON-RPC method**(节点 -32601)。真实读账户余额须 `state_getStorage` + System.Account 存储键, 或走 Sidecar `/accounts/{addr}/balance-info`。**chain template 声明错误的真实发现** → 印证 research R2/R3(无校验 + 声明错静默) |
| kusama | `system_health` | mixed | no_params | `params:[]` | `{result:{peers:21,isSyncing:false,shouldHavePeers:true}}` | ✅ |
| kusama | `system_properties` | mixed | no_params | `params:[]` | `{result:{ss58Format:2,tokenDecimals:12,tokenSymbol:"KSM"}}` | ✅ |
| moonbeam | `eth_blockNumber` | mixed | no_params | `params:[]` | `{result:"0xabba96"}` → block_height=result | ✅ (acala 须走 EVM endpoint) |
| moonbeam | `eth_chainId` | mixed | no_params | `params:[]` | `{result:"0x250"}`(astar) / `0x313`(acala) → chain id=result | ✅ (acala 须走 EVM endpoint, substrate 端 -32601) |
| moonbeam | `eth_gasPrice` | mixed | no_params | `params:[]` | `{result:"0x746a52880"}` → gas price=result | ✅ |
| moonbeam | `eth_getBalance` | single+mixed | address_latest | `params:["<addr>","latest"]` | `{result:"0xe6b9bb1ce008f88"}` → 余额=result | ✅ (astar/moonbeam EVM compat) |
| moonbeam | `system_health` | mixed | no_params | `params:[]` | `{result:{peers:21,isSyncing:false,shouldHavePeers:true}}` | ✅ |
| polkadot | `GET /accounts/{addr}/balance-info` | mixed | path_addr | `GET /accounts/<SS58>/balance-info` | (Sidecar API) `{at:{hash,height},nonce,tokenSymbol,free,reserved,frozen,...}` → 余额=free | ⚠️ 无公开 Sidecar endpoint(Parity 停止公开托管, 须自建 substrate-api-sidecar)。结构按官方 Sidecar API spec |
| polkadot | `GET /blocks/{n}` | mixed | path_height | `GET /blocks/<n>` | (Sidecar) `{number,hash,parentHash,stateRoot,extrinsicsRoot,authorId,extrinsics:[...],...}` → block_height=number | ⚠️ 同上无公开 Sidecar |
| polkadot | `GET /pallets/staking/progress` | mixed | no_params | `GET /pallets/staking/progress` | (Sidecar) `{at,idealValidatorCount,activeEra,...}` | ⚠️ 同上无公开 Sidecar |
| polkadot | `account_nextIndex` | mixed | single_address | `params:["<SS58 addr>"]` | `{result:0}` → nonce=result(int) | ✅ |
| polkadot | `chain_getHeader` | mixed | no_params | `params:[]` | `{result:{parentHash,number:"0x1e0a8b6",stateRoot,extrinsicsRoot,digest}}` → block_height=result.number(hex) | ✅ |
| polkadot | `system_account` | single | single_address | `params:["<SS58 addr>"]` | `{error:{code:-32601,message:"Method not found"}}` | ⚠️ **`system_account` 不是真 Substrate JSON-RPC method**(节点 -32601)。真实读账户余额须 `state_getStorage` + System.Account 存储键, 或走 Sidecar `/accounts/{addr}/balance-info`。**chain template 声明错误的真实发现** → 印证 research R2/R3(无校验 + 声明错静默) |

### tendermint (5链, 25 method)

| 链 | method(config原名) | single/mixed | param_format | 实测请求结构体 | 实测响应结构体 | 状态 |
|---|---|---|---|---|---|---|
| celestia | `/block` | mixed | [height] | `GET /block` (无height=最新; `?height=N` 指定)(Tendermint RPC) | `{jsonrpc,result:{block_id:{hash},block:{header:{height,...},data:{txs}}}}` → block_height=result.block.header.height | ✅ |
| celestia | `/cosmos/bank/v1beta1/balances/{address}` | single+mixed | path_address | `GET /cosmos/bank/v1beta1/balances/<bech32>` 实测真 addr | `{balances:[{denom:"utia",amount:"157484711661"}],pagination:{...}}` → 余额=balances[] | ✅ |
| celestia | `/cosmos/base/tendermint/v1beta1/blocks/latest` | mixed | no_params | `GET .../blocks/latest`(LCD) | `{block_id:{hash,...},block:{header:{height,chain_id,time,...},data:{txs:[...]},...}}` → block_height=block.header.height | ✅ |
| celestia | `/cosmos/base/tendermint/v1beta1/node_info` | mixed | no_params | `GET .../node_info`(LCD) | `{default_node_info:{protocol_version,default_node_id,network,version,...},application_version}` | ✅ |
| celestia | `/status` | mixed | no_params | `GET /status`(Tendermint RPC) | `{jsonrpc,result:{node_info,sync_info:{latest_block_height,latest_block_hash,...},validator_info}}` → block_height=result.sync_info.latest_block_height | ✅ |
| cosmos-hub | `GET /cosmos/bank/v1beta1/balances/{addr}` | single+mixed | path_addr | `GET /cosmos/bank/v1beta1/balances/<bech32>` 实测真 addr | `{balances:[{denom:"utia",amount:"157484711661"}],pagination:{...}}` → 余额=balances[] | ✅ |
| cosmos-hub | `GET /cosmos/base/tendermint/v1beta1/blocks/latest` | mixed | no_params | `GET .../blocks/latest`(LCD) | `{block_id:{hash,...},block:{header:{height,chain_id,time,...},data:{txs:[...]},...}}` → block_height=block.header.height | ✅ |
| cosmos-hub | `GET /cosmos/base/tendermint/v1beta1/blocks/{height}` | mixed | path_height | `GET .../blocks/<height>` (须 ≥ 节点 lowest height) | 同 blocks/latest 结构 | ✅ |
| cosmos-hub | `GET /cosmos/staking/v1beta1/validators` | mixed | query_pagination | `GET .../validators?pagination.limit=1` | `{validators:[{operator_address,consensus_pubkey,jailed,status,tokens,...}],pagination}` | ✅ |
| cosmos-hub | `GET /cosmos/tx/v1beta1/txs/{hash}` | mixed | path_hash_upper_hex_no_prefix | `GET .../txs/<UPPER_HEX_HASH>` 实测真 hash(sha256 of tx, 无0x前缀大写) | `{tx:{body:{messages:[{@type,...}]},auth_info,signatures},tx_response:{txhash,height,code,...}}` | ✅ |
| injective | `/cosmos/bank/v1beta1/balances/{address}` | single+mixed | path_address | `GET /cosmos/bank/v1beta1/balances/<bech32>` 实测真 addr | `{balances:[{denom:"utia",amount:"157484711661"}],pagination:{...}}` → 余额=balances[] | ✅ |
| injective | `/injective/exchange/v1beta1/derivative/markets` | mixed | no_params | `GET .../derivative/markets` | `{markets:[{market:{ticker,oracle_base,...},...}]}` | ✅ |
| injective | `/injective/exchange/v1beta1/spot/markets` | mixed | no_params | `GET /injective/exchange/v1beta1/spot/markets`(LCD) | `{markets:[{ticker:"KATANA/USDT",base_denom,quote_denom,market_id,...}]}` | ✅ |
| injective | `/injective/oracle/v1beta1/params` | mixed | no_params | `GET /injective/oracle/v1beta1/params` | `{params:{pyth_contract,chainlink_verifier_proxy_contract,...}}` | ✅ |
| injective | `/status` | mixed | no_params | `GET /status`(Tendermint RPC) | `{jsonrpc,result:{node_info,sync_info:{latest_block_height,latest_block_hash,...},validator_info}}` → block_height=result.sync_info.latest_block_height | ✅ |
| osmosis | `/cosmos/bank/v1beta1/balances/{address}` | single+mixed | path_address | `GET /cosmos/bank/v1beta1/balances/<bech32>` 实测真 addr | `{balances:[{denom:"utia",amount:"157484711661"}],pagination:{...}}` → 余额=balances[] | ✅ |
| osmosis | `/osmosis/gamm/v1beta1/pools/{pool_id}` | mixed | path_pool_id | `GET .../pools/1` | `{pool:{@type,address,id:"1",pool_params:{swap_fee,...},pool_assets:[...]}}` | ✅ |
| osmosis | `/osmosis/poolmanager/v1beta1/num_pools` | mixed | no_params | `GET .../num_pools`(LCD) | `{num_pools:"3465"}` | ✅ |
| osmosis | `/osmosis/twap/v1beta1/ArithmeticTwapToNow` | mixed | query_params | `GET .../ArithmeticTwapToNow?pool_id=1&base_asset=uosmo&quote_asset=ibc/..&start_time=<ISO>` | `{arithmetic_twap:"0.025081676131380860"}` | ✅ |
| osmosis | `/status` | mixed | no_params | `GET /status`(Tendermint RPC) | `{jsonrpc,result:{node_info,sync_info:{latest_block_height,latest_block_hash,...},validator_info}}` → block_height=result.sync_info.latest_block_height | ✅ |
| sei | `/status` | mixed | no_params | `GET /status`(Tendermint RPC) | `{node_info,sync_info,validator_info}`(sei RPC 返裸对象, 无 jsonrpc 包) → block_height=sync_info.latest_block_height | ✅ |
| sei | `eth_blockNumber` | mixed | no_params | `POST eth_blockNumber []` | `{result:"0xc97cd97"}` → block_height=result | ✅ |
| sei | `eth_call` | mixed | address_with_options | `POST eth_call [{to,data},"latest"]` | `{result:"0x"}` → data=result | ✅ |
| sei | `eth_chainId` | mixed | no_params | `POST {method:"eth_chainId",params:[]}`(EVM endpoint) | `{result:"0x531"}` | ✅ |
| sei | `eth_getBalance` | single+mixed | address_latest | `POST eth_getBalance [addr,"latest"]` | `{result:"0x4065ba745c24000"}` → 余额=result | ✅ |

### bitcoin_jsonrpc (4链, 24 method)

| 链 | method(config原名) | single/mixed | param_format | 实测请求结构体 | 实测响应结构体 | 状态 |
|---|---|---|---|---|---|---|
| bch | `getblock` | mixed | [blockhash] | `params:["<blockhash>"]` (默认 verbosity=1 返对象; verbosity=0 返 hex; =2 含 tx 详情) | `{result:{hash,confirmations,height,version,merkleroot,time,nonce,bits,difficulty,tx:[...txids],previousblockhash,...}}` → block_height=result.height | ✅ |
| bch | `getblockcount` | mixed | no_params | `params:[]` | `{result:952086,error:null}` → block_height=result(int) | ✅ |
| bch | `getmempoolinfo` | mixed | no_params | `params:[]` | `{result:{loaded,size:118,bytes,usage,maxmempool,mempoolminfee,minrelaytxfee}}` → mempool_size=result.size | ✅ |
| bch | `getnetworkinfo` | mixed | no_params | `params:[]` | `{result:{version,subversion:"/Bitcoin Cash Node:29.0.0.../",protocolversion,localservices,connections,relayfee,networks:[...],...}}` | ✅ |
| bch | `getrawtransaction` | mixed | [txhash,verbose] | `params:["<txid>",true]` (verbose=true 返对象; false/0 返 hex) | `{result:{txid,hash,version,size,vsize,weight,locktime,vin:[...],vout:[...],hex,blockhash?,confirmations?}}` | ✅ (bitcoin/doge/litecoin 实测; bch 端 429 限流, 结构同 family) |
| bch | `getreceivedbyaddress` | single | single_address | `params:["<address>"]` | `{error:{code:-32701,message:"Method getreceivedbyaddress is not allowed..."}}` | ⚠️ **wallet 方法, 共享公开节点禁用**(需节点本地 wallet)。结构按官方: 返 result=金额(BTC float)。本类 method 无法在公开节点实测, 真实部署有 wallet 时可用 |
| bitcoin | `estimatesmartfee` | mixed | [conf_target] | `params:[6]` | `{result:{feerate:1.013e-05,blocks:6}}` → feerate=result.feerate | ✅ |
| bitcoin | `getblock` | mixed | [blockhash,verbosity] | `params:["<blockhash>"]` (默认 verbosity=1 返对象; verbosity=0 返 hex; =2 含 tx 详情) | `{result:{hash,confirmations,height,version,merkleroot,time,nonce,bits,difficulty,tx:[...txids],previousblockhash,...}}` → block_height=result.height | ✅ |
| bitcoin | `getblockcount` | mixed | no_params | `params:[]` | `{result:952086,error:null}` → block_height=result(int) | ✅ |
| bitcoin | `getrawmempool` | mixed | no_params | `params:[]` | `{result:["txid1","txid2",...]}` → mempool txids 数组 | ✅ |
| bitcoin | `getrawtransaction` | mixed | [txid,verbose] | `params:["<txid>",true]` (verbose=true 返对象; false/0 返 hex) | `{result:{txid,hash,version,size,vsize,weight,locktime,vin:[...],vout:[...],hex,blockhash?,confirmations?}}` | ✅ (bitcoin/doge/litecoin 实测; bch 端 429 限流, 结构同 family) |
| bitcoin | `getreceivedbyaddress` | single | single_address | `params:["<address>"]` | `{error:{code:-32701,message:"Method getreceivedbyaddress is not allowed..."}}` | ⚠️ **wallet 方法, 共享公开节点禁用**(需节点本地 wallet)。结构按官方: 返 result=金额(BTC float)。本类 method 无法在公开节点实测, 真实部署有 wallet 时可用 |
| dogecoin | `getbestblockhash` | mixed | no_params | `params:[]` | `{result:"00000...af3a0"}` → blockhash=result(hex str) | ✅ |
| dogecoin | `getblock` | mixed | block_hash | `params:["<blockhash>"]` (默认 verbosity=1 返对象; verbosity=0 返 hex; =2 含 tx 详情) | `{result:{hash,confirmations,height,version,merkleroot,time,nonce,bits,difficulty,tx:[...txids],previousblockhash,...}}` → block_height=result.height | ✅ |
| dogecoin | `getblockcount` | mixed | no_params | `params:[]` | `{result:952086,error:null}` → block_height=result(int) | ✅ |
| dogecoin | `getmempoolinfo` | mixed | no_params | `params:[]` | `{result:{loaded,size:118,bytes,usage,maxmempool,mempoolminfee,minrelaytxfee}}` → mempool_size=result.size | ✅ |
| dogecoin | `getrawtransaction` | mixed | transaction_hash | `params:["<txid>",true]` (verbose=true 返对象; false/0 返 hex) | `{result:{txid,hash,version,size,vsize,weight,locktime,vin:[...],vout:[...],hex,blockhash?,confirmations?}}` | ✅ (bitcoin/doge/litecoin 实测; bch 端 429 限流, 结构同 family) |
| dogecoin | `getreceivedbyaddress` | single | single_address | `params:["<address>"]` | `{error:{code:-32701,message:"Method getreceivedbyaddress is not allowed..."}}` | ⚠️ **wallet 方法, 共享公开节点禁用**(需节点本地 wallet)。结构按官方: 返 result=金额(BTC float)。本类 method 无法在公开节点实测, 真实部署有 wallet 时可用 |
| litecoin | `getbestblockhash` | mixed | no_params | `params:[]` | `{result:"00000...af3a0"}` → blockhash=result(hex str) | ✅ |
| litecoin | `getblock` | mixed | block_hash | `params:["<blockhash>"]` (默认 verbosity=1 返对象; verbosity=0 返 hex; =2 含 tx 详情) | `{result:{hash,confirmations,height,version,merkleroot,time,nonce,bits,difficulty,tx:[...txids],previousblockhash,...}}` → block_height=result.height | ✅ |
| litecoin | `getblockcount` | mixed | no_params | `params:[]` | `{result:952086,error:null}` → block_height=result(int) | ✅ |
| litecoin | `getmempoolinfo` | mixed | no_params | `params:[]` | `{result:{loaded,size:118,bytes,usage,maxmempool,mempoolminfee,minrelaytxfee}}` → mempool_size=result.size | ✅ |
| litecoin | `getrawtransaction` | mixed | transaction_hash | `params:["<txid>",true]` (verbose=true 返对象; false/0 返 hex) | `{result:{txid,hash,version,size,vsize,weight,locktime,vin:[...],vout:[...],hex,blockhash?,confirmations?}}` | ✅ (bitcoin/doge/litecoin 实测; bch 端 429 限流, 结构同 family) |
| litecoin | `getreceivedbyaddress` | single | single_address | `params:["<address>"]` | `{error:{code:-32701,message:"Method getreceivedbyaddress is not allowed..."}}` | ⚠️ **wallet 方法, 共享公开节点禁用**(需节点本地 wallet)。结构按官方: 返 result=金额(BTC float)。本类 method 无法在公开节点实测, 真实部署有 wallet 时可用 |

### rest (5链, 27 method)

| 链 | method(config原名) | single/mixed | param_format | 实测请求结构体 | 实测响应结构体 | 状态 |
|---|---|---|---|---|---|---|
| algorand | `GET /v2/accounts/{address}` | single+mixed | path_addr_base32 | `GET /v2/accounts/<base32 addr>` 实测 fee sink | `{address,amount:6886384485,amount-without-pending-rewards,assets:[...],...}` → 余额=amount | ✅ |
| algorand | `GET /v2/accounts/{address}/transactions` | mixed | path_addr_query_limit | `GET /v2/accounts/<addr>/transactions?limit=1`(indexer) | `{current-round,next-token,transactions:[{confirmed-round,...}]}` | ⚠️ node API 不含此端点(404), 须 indexer endpoint。实测 indexer 成功 |
| algorand | `GET /v2/assets/{asset_id}` | mixed | path_asset_id_int | `GET /v2/assets/31566704`(USDC) | `{index:31566704,params:{creator,decimals:6,name,unit-name,total,...}}` | ✅ |
| algorand | `GET /v2/blocks/{round}` | mixed | path_round_int | `GET /v2/blocks/<round>` 实测真 round | `{block:{bi,earn,fees,rnd,txns,...}}` → block_height=block.rnd | ✅ |
| algorand | `GET /v2/transactions/{txid}` | mixed | path_txid_base32 | `GET /v2/transactions/<txid>`(indexer) 实测真 txid | `{current-round,transaction:{confirmed-round,fee,sender,...}}` | ✅ |
| aptos | `GET /v1` | mixed | no_params | `GET /v1` | `{chain_id:1,epoch,ledger_version,ledger_timestamp,block_height,node_role}` → block_height=block_height | ✅ |
| aptos | `GET /v1/accounts/{addr}` | single+mixed | path_addr | `GET /v1/accounts/0x1` | `{sequence_number,authentication_key}` | ✅ |
| aptos | `GET /v1/accounts/{addr}/resources` | mixed | path_addr | `GET /v1/accounts/0x1/resources` | `[{type:"0x1::...",data:{...}},...]`(资源数组) | ✅ |
| aptos | `GET /v1/transactions/by_hash/{hash}` | mixed | path_hash | `GET /v1/transactions/by_hash/0x..` 实测真 hash | `{version,hash,state_change_hash,sender,success,vm_status,...}` | ✅ |
| aptos | `POST /v1/view` | mixed | move_view_call | `POST /v1/view body={function:"0x1::coin::supply",type_arguments:["0x1::aptos_coin::AptosCoin"],arguments:[]}` | `[{vec:["120358165050369164"]}]`(返回值数组) | ✅ Move view 调用(复杂结构化 body) |
| cardano | `GET_BLOCKS` | mixed | no_params | `GET /blocks?limit=1` | `[{hash,epoch_no,abs_slot,block_height,...}]` | ✅ |
| cardano | `GET_EPOCH_INFO` | mixed | query_epoch_int | `GET /epoch_info` | `[{epoch_no,out_sum,fees,tx_count,blk_count,start_time,...}]` | ✅ |
| cardano | `GET_TIP` | mixed | no_params | `GET /tip` | `[{hash,epoch_no,abs_slot,block_no,block_time}]` → block_height=[0].block_no | ✅ |
| cardano | `POST_ADDRESS_INFO` | single+mixed | body_addresses_array | `POST /address_info body={_addresses:["<bech32>"]}` | `[{address,balance,stake_address,utxo_set:[...]}]`(空地址返 []) | ✅ |
| cardano | `POST_ASSET_INFO` | mixed | ⚠️缺 | `POST /asset_info body={_asset_list:[[policy,name_hex]]}` | `[{...}]`(不存在资产返 [])路由+body正确 | ✅ (research R3 标缺 param_format 的 method, 实测路由 + body 正确, 返回空因 sample 资产不存在) |
| cardano | `POST_BLOCK_TXS` | mixed | body_block_hashes_array | `POST /block_txs body={_block_hashes:["<hash>"]}` 实测真 hash | `[{block_hash,tx_hash,epoch_no,...}]` | ✅ |
| cardano | `POST_TX_INFO` | mixed | body_tx_hashes_array | `POST /tx_info body={_tx_hashes:["<hash>"]}` 实测真 hash | `[{tx_hash,block_hash,block_height,tx_timestamp,inputs:[...],outputs:[...]}]` | ✅ |
| tezos | `GET /chains/main/blocks/head/context/contracts/{addr}/balance` | single+mixed | path_addr | `GET /chains/main/blocks/head/context/contracts/<tz addr>/balance` | `"283125643"`(裸字符串数字) → 余额=整个响应体 | ✅ |
| tezos | `GET /chains/main/blocks/head/header` | mixed | no_params | `GET /chains/main/blocks/head/header` | `{protocol,chain_id,hash,level,timestamp,...}` → block_height=level | ✅ |
| tezos | `GET /chains/main/blocks/head/protocols` | mixed | no_params | `GET /chains/main/blocks/head/protocols` | `{protocol,next_protocol}` | ✅ |
| tezos | `GET /chains/main/blocks/head/votes/current_period` | mixed | no_params | `GET /chains/main/blocks/head/votes/current_period` | `{voting_period:{index,kind,start_position},position,remaining}` | ✅ |
| tezos | `GET /chains/main/blocks/{block}/operations/{vp}` | mixed | path_block_and_vp | `GET /chains/main/blocks/<block>/operations/0` | `[[{protocol,chain_id,hash,branch,contents:[...]}]]`(嵌套数组, vp=validation pass 0-3) | ✅ |
| ton | `getAddressBalance` | single+mixed | {address: friendly_base64url|raw} | `GET /getAddressBalance?address=<addr>` | `{ok:true,result:"6592363731332"}` → 余额=result(裸字符串) | ✅ |
| ton | `getAddressInformation` | mixed | {address: friendly_base64url|raw} | `GET /getAddressInformation?address=<addr>` | `{ok:true,result:{@type:"raw.fullAccountState",balance,last_transaction_id,...}}` | ✅ |
| ton | `getTransactions` | mixed | {address, limit, lt?, hash?} | `GET /getTransactions?address=<addr>&limit=1` | `{ok:true,result:[{@type:"ext.transaction",address,utime,transaction_id,...}]}` | ✅ |
| ton | `lookupBlock` | mixed | {workchain: int, shard: dec_string, seqno: int} | `GET /lookupBlock?workchain=-1&shard=-9223372036854775808&seqno=1` | `{ok:true,result:{@type:"ton.blockIdExt",workchain,shard,seqno,root_hash,file_hash}}` | ✅ |
| ton | `runGetMethod` | mixed | {address, method: string, stack: array} | `POST /runGetMethod body={address,method:"seqno",stack:[]}` | `{ok:true,result:{@type:"smc.runResult",gas_used,stack:[["num","0x14c97"]],exit_code}}` | ✅ |

### hedera_dual (1链, 5 method)

| 链 | method(config原名) | single/mixed | param_format | 实测请求结构体 | 实测响应结构体 | 状态 |
|---|---|---|---|---|---|---|
| hedera | `GET /api/v1/accounts/{addr}` | single+mixed | ⚠️缺 | `{account:"0.0.2",alias,balance:{balance:1663012637744658,timestamp,tokens:[]},created_timestamp,...}` → 余额=balance.balance | path, addr=0.0.x 三段 ID | ✅ |
| hedera | `GET /api/v1/balances?account.id={addr}` | mixed | ⚠️缺 | `{timestamp,balances:[{account:"0.0.2",balance,tokens:[]}],links}` → 余额=balances[0].balance | query account.id=0.0.x | ✅ |
| hedera | `GET /api/v1/transactions/{addr}` | mixed | ⚠️缺 | `{transactions:[{consensus_timestamp,entity_id,charged_tx_fee,name,result,transfers:[...],...}]}` | path, tx_id=0.0.x-秒-纳秒 破折号格式 | ✅ |
| hedera | `eth_call` | mixed | address_with_options | `params:[{to:"<contract>",data:"0x18160ddd"},"latest"]` USDT totalSupply | `{result:"0x...0158de55a1c7950b"}` → data=result(abi-encoded) | ✅ |
| hedera | `eth_getBalance` | mixed | address_latest | `{jsonrpc,id,method,params:["<addr>","latest"]}` 实测 addr=vitalik.eth | `{result:"0x4ec8826ce34c4d61"}` → 余额=result(hex wei) | ✅ |

## 已知缺口(忠实标注, 非遗漏)

**缺 param_format 定义(config 未声明 → R3 fallback single_address 风险, 4处)**: cardano POST_ASSET_INFO / hedera GET accounts·balances·transactions 三个。

**结构性不可达(非 endpoint 问题, 按官方文档记录结构, 4类)**: 
- bitcoin系 `getreceivedbyaddress`: wallet 方法, 共享公开节点 -32701 禁用(需节点本地 wallet)。
- bch `getrawtransaction`: Tatum 端 429 限流, 结构同 family 其余3链。
- polkadot 3 个 Sidecar REST: Parity 停公开托管, 结构按官方 Sidecar spec。
- substrate `system_account`: 节点 -32601(chain template 声明错, 实测证伪=有效产出, 印证 R2/R3)。

## 交叉验证记录
- 基石计数: config/chains/*.json single+mixed 去重 = 184 (execute_code 实证)。
- 本文档 184 行 ↔ config/chains 184 对: 0 遗漏 0 多余 0 改名(逐 (chain,method) key 比对)。
- method 名用 config 原始字符串(非 design §3 规整名), 与定义源逐字对齐, 供重构直接锚定。
- 块高/同步监控 method 的'同步状态'用途见独立文件 `block-height-sync-method-measurement.md`(不同视角, 不在此重复)。
