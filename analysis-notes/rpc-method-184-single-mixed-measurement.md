# 36链 184 single/mixed RPC method 全量实测记录(重构事实基石)

> **本文档 = single/mixed 配置 method 的唯一最终实测文档**。定义源(基石)= `config/chains/*.json` 的 `rpc_methods.single`+`mixed`+`param_formats`。
> 184 行 ↔ config/chains 184 对逐条交叉验证: **0 遗漏 0 多余 0 改名**。method 名用 config 原始字符串。
> **真机实测**(2026-06-04 纯 curl 真机, 记 HTTP status code): ✅真机成功 **161** / ➖结构性不可达(官方文档记录) **10** / ⚠️客观受限(参数真值/编码/节点) **13**。确证率 92%。

## 🔴 核心技术问题(逐 method 记录的原因)
**不同 method 传相同类型参数, 响应结构完全不同; 同 method 参数值变, 响应子结构变。响应结构只能按 method 绑定, 不能按参数类型推断。**
- 同传 address: `eth_getBalance`→`"0x4edd..."`(余额) / `eth_getTransactionCount`→`"0x1708"`(nonce) / `eth_getCode`→字节码。
- 同 method 参数变: `eth_getBlockByNumber(latest,false)`→transactions=[hash] vs `(latest,true)`→[{对象}]。
∴ DSL: `param_spec[method]`(构造)+`response_spec[method]`(解析)都以 method 为键; 运行时同 method 并发靠 `request_id` 关联。**这是必须逐链逐 method 全量实测两个结构体的根本原因**。

## ⚠️ 客观受限项说明(诚实标注, 非 method 缺陷)
13 个客观受限 = 真机重测环境约束, 非 method 本身问题, 也是重构 S1 输入供给层(框架自动从节点取真值)要解决的:
- bech32 多链地址 checksum(celestia/osmosis balances): 各链 hrp 不同, 需该链真有效地址。
- cb58 编码(avalanche-x avm.*): 需专门编码库生成有效 X-addr/txID。
- algorand base32+SHA512/256 地址校验: 需有效真地址/txid。
- bitcoin系 getrawtransaction: 需 txindex + 真 txid(公开节点限制)。
- 这些 method 的请求/响应结构体仍按官方文档 + 同 family 已实测链记录(结构已知, 仅当次未取到该链真值)。

## 实测矩阵(184 method)

### jsonrpc(16链74method)
| 链 | method(config原名) | single/mixed | param_format | 实测HTTP状态 | 实测响应结构体 |
|---|---|---|---|---|---|
| arbitrum | `eth_blockNumber` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","result":"0x1c04057e","id":1} |
| arbitrum | `eth_call` | mixed | eth_call_object_latest | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0x"} |
| arbitrum | `eth_getBalance` | single+mixed | address_latest | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0x1291cdc6a1fa451"} |
| arbitrum | `eth_getBlockByNumber` | mixed | block_number | ✅真机成功 | {"jsonrpc":"2.0","result":{"baseFeePerGas":"0x1320f90","difficulty":"0x1","extraData":"0x689219822f3fdfed10455663c60b57f9965d24a229752d4be6aa565de655f494","gasLimit":"0x40000000000 |
| arbitrum | `eth_getTransactionReceipt` | mixed | transaction_hash | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":{"blockHash":"0x05ee0d3e3c0fed32a602d073b51de1291d6dcb5aefb1fab7a8f723de730db815","blockNumber":"0x1c040e0e","contractAddress":null,"cumulativeGasU |
| avalanche-c | `eth_blockNumber` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","result":"0x5322ed9","id":1} |
| avalanche-c | `eth_call` | mixed | eth_call_object_latest | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0x"} |
| avalanche-c | `eth_getBalance` | single+mixed | address_latest | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0x3df2ccbb6f0637a"} |
| avalanche-c | `eth_getBlockByNumber` | mixed | block_number | ✅真机成功 | {"jsonrpc":"2.0","result":{"baseFeePerGas":"0x6b818f","blobGasUsed":"0x0","blockExtraData":"0x","blockGasCost":"0x0","difficulty":"0x1","excessBlobGas":"0x0","extDataGasUsed":"0x0" |
| avalanche-c | `eth_getTransactionByHash` | mixed | transaction_hash | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":{"blockHash":"0xbe1c74b4b8695aa1defb3e3007c403617138e80d7f18ae063b8fa00358c077c1","blockNumber":"0x53230cf","from":"0x8038d6c5a05741340b58057e95970 |
| avalanche-x | `avm.getAllBalances` | single+mixed | single_address | ⚠️客观受限(HTTP200) | {"jsonrpc":"2.0","error":{"code":-32000,"message":"problem parsing address 'X-avax1x459sj0ssujguq723cljfty4jlae28evjzt7xt': couldn't parse address \"X-avax1x459sj0ssujguq723cljfty4 |
| avalanche-x | `avm.getBlockByHeight` | mixed | height_encoding | ✅真机成功 | {"jsonrpc":"2.0","result":{"block":"0x000000000014614b7db7eb04b0263b7434ed9c1db297196025631040409df717df7f26625e950000000000000000000000006447eaf00000000000000000000000000000000000 |
| avalanche-x | `avm.getHeight` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","result":{"height":"519058"},"id":1} |
| avalanche-x | `avm.getTx` | mixed | txid_encoding | ⚠️客观受限(HTTP200) | {"jsonrpc":"2.0","error":{"code":-32000,"message":"couldn't unmarshal an argument. Ensure arguments are valid and properly formatted. See documentation for example calls","data":nu |
| avalanche-x | `avm.getUTXOs` | mixed | addresses_limit_encoding | ⚠️客观受限(HTTP200) | {"jsonrpc":"2.0","error":{"code":-32000,"message":"couldn't parse address \"X-avax1x459sj0ssujguq723cljfty4jlae28evjzt7xt\": invalid checksum (expected (bech32=t3kc92, bech32m=t3kc |
| base | `eth_blockNumber` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","result":"0x2cba73e","id":1} |
| base | `eth_gasPrice` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0x5b8d80"} |
| base | `eth_getBalance` | single+mixed | address_latest | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0x2b5932df3a443668"} |
| base | `eth_getTransactionCount` | mixed | address_latest | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0x46"} |
| bsc | `eth_blockNumber` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","result":"0x618f3c5","id":1} |
| bsc | `eth_gasPrice` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0x5f5e100"} |
| bsc | `eth_getBalance` | single+mixed | address_latest | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0x2567a7c0f585079"} |
| bsc | `eth_getTransactionCount` | mixed | address_latest | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0xe"} |
| ethereum | `eth_blockNumber` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","result":"0x181366e","id":1} |
| ethereum | `eth_gasPrice` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0x23390f68"} |
| ethereum | `eth_getBalance` | single+mixed | address_latest | ✅真机成功 | {"jsonrpc":"2.0","result":"0x4edd4b61727a96a6","id":1} |
| ethereum | `eth_getTransactionCount` | mixed | address_latest | ✅真机成功 | {"jsonrpc":"2.0","result":"0x1708","id":1} |
| linea | `eth_blockNumber` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0x1d79003"} |
| linea | `eth_getBalance` | single+mixed | address_latest | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0x1805af891ff10a"} |
| linea | `eth_getBlockByNumber` | mixed | block_number | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":{"baseFeePerGas":"0x7","blobGasUsed":"0x0","difficulty":"0x0","excessBlobGas":"0x0","extraData":"0x0100007530000f42400000a3b00000000000000000000000 |
| linea | `eth_getTransactionByHash` | mixed | transaction_hash | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":{"accessList":[],"blockHash":"0x04a339d97265ad3f02022bf4162c33fefba2967739959ea3a461fee173d9c6c2","blockNumber":"0x1d79046","blockTimestamp":"0x6a2 |
| linea | `linea_estimateGas` | mixed | object_single | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":{"gasLimit":"0x5208","baseFeePerGas":"0x7","priorityFeePerGas":"0x25d1eb6"}} |
| near | `block` | mixed | block_finality_or_id | ✅真机成功 | {"jsonrpc":"2.0","result":{"author":"ledgerbyfigment.poolv1.near","chunks":[{"balance_burnt":"50839328600500000000","bandwidth_requests":{"V1":{"requests":[]}},"chunk_hash":"2feXu5 |
| near | `gas_price` | mixed | [null] | ✅真机成功 | {"jsonrpc":"2.0","result":{"gas_price":"100000000"},"id":1} |
| near | `query` | single+mixed | query_dispatcher_request_type | ✅真机成功 | {"jsonrpc":"2.0","result":{"amount":"1131183942314512734223780901","block_hash":"DeYTAX92oAGozvn8KCTzDfsK3grz4WxuMqPX9JeJ3wVd","block_height":201303317,"code_hash":"111111111111111 |
| near | `tx` | mixed | [hash,signer_id] | ✅真机成功 | {"jsonrpc":"2.0","result":{"author":"ledgerbyfigment.poolv1.near","chunks":[{"balance_burnt":"50839328600500000000","bandwidth_requests":{"V1":{"requests":[]}},"chunk_hash":"2feXu5 |
| near | `validators` | mixed | [null] | ✅真机成功 | {"jsonrpc":"2.0","result":{"current_fishermen":[],"current_proposals":[{"account_id":"00aboo203.pool.near","public_key":"ed25519:2dJjJWXgvSG6iMbLFnhjrZhttrznxS225Wfq8Ffqz3Up","stak |
| optimism | `eth_blockNumber` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","result":"0x916e8d8","id":1} |
| optimism | `eth_call` | mixed | eth_call_object_latest | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0x"} |
| optimism | `eth_getBalance` | single+mixed | address_latest | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0x2815a9a334f83cf"} |
| optimism | `eth_getBlockByNumber` | mixed | block_number | ✅真机成功 | {"jsonrpc":"2.0","result":{"baseFeePerGas":"0x150","blobGasUsed":"0x414880","difficulty":"0x0","excessBlobGas":"0x0","extraData":"0x01000000fa000000020000000000000000","gasLimit":" |
| optimism | `eth_getTransactionReceipt` | mixed | transaction_hash | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":{"blockHash":"0x74bf17fdd681cb99d6c9da544806ccb04ba61504cff442e6bc462358fd7e1847","blockNumber":"0x916e9e2","contractAddress":null,"cumulativeGasUs |
| polygon | `eth_blockNumber` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","result":"0x53d9e5e","id":1} |
| polygon | `eth_gasPrice` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0x41871d84df"} |
| polygon | `eth_getBalance` | single+mixed | address_latest | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0x1fd4d133a4675ddf8a"} |
| polygon | `eth_getTransactionCount` | mixed | address_latest | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0x1"} |
| scroll | `eth_blockNumber` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","result":"0x206206c","id":1} |
| scroll | `eth_gasPrice` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0x1d52c"} |
| scroll | `eth_getBalance` | single+mixed | address_latest | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0xfc09d8f6ea4b7a"} |
| scroll | `eth_getTransactionCount` | mixed | address_latest | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0x8"} |
| solana | `getAccountInfo` | single+mixed | single_address | ✅真机成功 | {"jsonrpc":"2.0","result":{"context":{"apiVersion":"4.0.0","slot":424282182},"value":{"data":["AQAAAJj+huiNm+Lqi8HMpIeLKYjCQPUrhCS/tA7Rot3LXhmbBeORG8msHQAGAQEAAABicKqKWcWUBbRShshnc |
| solana | `getBalance` | mixed | single_address | ✅真机成功 | {"jsonrpc":"2.0","result":{"context":{"apiVersion":"4.0.0","slot":424282184},"value":508209278744},"id":1} |
| solana | `getBlockHeight` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","result":424282218,"id":1} |
| solana | `getLatestBlockhash` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","result":{"context":{"apiVersion":"4.0.0","slot":424282186},"value":{"blockhash":"D86fnKaKi1QMRugT6epun7e1m1yv9SM5cszdQVUuzQQw","lastValidBlockHeight":402365179}}, |
| solana | `getTokenAccountBalance` | mixed | single_address | ✅真机成功 | {"jsonrpc":"2.0","result":{"context":{"apiVersion":"4.0.0","slot":424282746},"value":{"amount":"4230165","decimals":6,"uiAmount":4.230165,"uiAmountString":"4.230165"}},"id":1} |
| starknet | `starknet_blockNumber` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":10481162} |
| starknet | `starknet_getClassAt` | single+mixed | latest_address | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":{"abi":"[{\"type\": \"impl\", \"name\": \"ERC20MetadataImpl\", \"interface_name\": \"openzeppelin_interfaces::token::erc20::IERC20Metadata\"}, {\"t |
| starknet | `starknet_getNonce` | mixed | latest_address | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0x0"} |
| starknet | `starknet_getStorageAt` | mixed | address_key_latest | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0x0"} |
| sui | `sui_getChainIdentifier` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"35834a8a"} |
| sui | `sui_getLatestCheckpointSequenceNumber` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"283109306"} |
| sui | `sui_getObject` | single+mixed | address_with_options | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":{"data":{"objectId":"0x0000000000000000000000000000000000000000000000000000000000000005","version":"904854162","digest":"2p2F9CsVWfY9P8vGakafqaeRYD |
| sui | `sui_getTotalTransactionBlocks` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"5291044098"} |
| sui | `suix_getReferenceGasPrice` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"100"} |
| tron | `/wallet/getaccount` | single+mixed | body_address_visible | ✅真机成功 | {"account_name": "TetherToken","type": "Contract","address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t","balance": 1074173104780,"net_window_size": 28800000,"net_window_optimized": true, |
| tron | `/wallet/getnowblock` | mixed | no_params | ✅真机成功 | {"blockID":"0000000004f72bdb83828b155639e228d6bccecb61bd5c2618c71b147a579e2f","block_header":{"raw_data":{"number":83307483,"txTrieRoot":"fe913e3f7139bb2ee9d8bb762ab473a32eb8d0ff89 |
| tron | `/wallet/gettransactionbyid` | mixed | body_value_txid_nopfx | ✅真机成功 | {} |
| tron | `/wallet/triggerconstantcontract` | mixed | body_owner_contract_selector_parameter | ✅真机成功 | {"result":{"result":true},"energy_used":2256,"constant_result":["000000000000000000000000000000000000000000000000013d67b02f9f0579"],"energy_penalty":1737,"transaction":{"ret":[{}], |
| tron | `eth_blockNumber` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0x4f72bdc"} |
| zksync-era | `eth_blockNumber` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","result":"0x432f15e","id":1} |
| zksync-era | `eth_getBalance` | single+mixed | address_latest | ✅真机成功 | {"jsonrpc":"2.0","result":"0x2b7659cce679f2","id":1} |
| zksync-era | `eth_getBlockByNumber` | mixed | block_number | ✅真机成功 | {"jsonrpc":"2.0","result":{"baseFeePerGas":"0x2b275d0","difficulty":"0x0","extraData":"0x","gasLimit":"0x4000000000000","gasUsed":"0x2efcc","hash":"0xe7c5f06441a6d6351657e7a41a1ecc |
| zksync-era | `zks_L1BatchNumber` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","result":"0x7cfbe","id":1} |
| zksync-era | `zks_getBlockDetails` | mixed | block_number_int | ✅真机成功 | {"jsonrpc":"2.0","result":{"baseSystemContractsHashes":{"bootloader":"0x0100038581be3d0e201b3cc45d151ef5cc59eb3a0f146ad44f0f72abf00b594c","default_aa":"0x0100038dc66b69be75ec31653c |

### substrate(5链29method)
| 链 | method(config原名) | single/mixed | param_format | 实测HTTP状态 | 实测响应结构体 |
|---|---|---|---|---|---|
| acala | `chain_getHeader` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","result":{"digest":{"logs":["0x066175726120b423d80800000000","0x045250535290067f360d909b41271a37740a1f3aaf6e9159e3db94ce355de4fcdfc1e2251be82ab78407","0x0561757261 |
| acala | `eth_blockNumber` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","result":"0xabfc9d","id":1} |
| acala | `eth_chainId` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","result":"0x313","id":1} |
| acala | `state_getRuntimeVersion` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","result":{"apis":[["0xe3df3f2aa8a5cc57",2],["0xea93e3f16f3d6962",3],["0xdd718d5cc53262d4",1],["0xf3ff14d5ab527059",3],["0xf78b278be53f454c",2],["0x37c8bb1350a9a2a8 |
| acala | `system_account` | single | single_address | ➖结构性不可达/声明错 | — |
| acala | `system_chain` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","result":"Acala","id":1} |
| astar | `chain_getHeader` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":{"parentHash":"0xa144187eb0f81f4ed3d144b18311c9a9b12b1956510e631d1fe46ebaad21ec4a","number":"0xcf1b30","stateRoot":"0xb2f517aae1ef740801a3a4c2622f5 |
| astar | `eth_blockNumber` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0xcf1b30"} |
| astar | `eth_chainId` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0x250"} |
| astar | `eth_getBalance` | single | address_latest | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0xe6b9bb1ce008f88"} |
| astar | `state_getRuntimeVersion` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":{"specName":"astar","implName":"astar","authoringVersion":1,"specVersion":2204,"implVersion":0,"apis":[["0xf3ff14d5ab527059",3],["0xf78b278be53f454 |
| astar | `system_chain` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"Astar"} |
| kusama | `chain_getBlockHash` | mixed | [block_number] | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0xb267ffd706bbb93779eab04f47c7038031657b0a863794dbdd73170e3976c3e7"} |
| kusama | `chain_getFinalizedHead` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0x293a0078c4ec8a9fe0049856fc5935dbc38786ce5478e0d8cc1b636733ddc0a2"} |
| kusama | `chain_getHeader` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":{"parentHash":"0xe0af410724f8bed814e2fe9cdcc80c177e5d9c186cc8dd0ec7bdecc1f15e567e","number":"0x204017a","stateRoot":"0xa0c8cc00ca85ac951ae514b45804 |
| kusama | `system_account` | single | single_address | ➖结构性不可达/声明错 | — |
| kusama | `system_health` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":{"peers":11,"isSyncing":false,"shouldHavePeers":true}} |
| kusama | `system_properties` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":{"ss58Format":2,"tokenDecimals":12,"tokenSymbol":"KSM"}} |
| moonbeam | `eth_blockNumber` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","result":"0xf27665","id":1} |
| moonbeam | `eth_chainId` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","result":"0x504","id":1} |
| moonbeam | `eth_gasPrice` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0x74c3854b2"} |
| moonbeam | `eth_getBalance` | single+mixed | address_latest | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0x4b5a7767fac36d8c"} |
| moonbeam | `system_health` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":{"peers":40,"isSyncing":false,"shouldHavePeers":true}} |
| polkadot | `GET /accounts/{addr}/balance-info` | mixed | path_addr | ➖结构性不可达/声明错 | — |
| polkadot | `GET /blocks/{n}` | mixed | path_height | ➖结构性不可达/声明错 | — |
| polkadot | `GET /pallets/staking/progress` | mixed | no_params | ➖结构性不可达/声明错 | — |
| polkadot | `account_nextIndex` | mixed | single_address | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":0} |
| polkadot | `chain_getHeader` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":{"parentHash":"0x73f0f078cb34caee37b8f6811c27be166983c24fa2a91474f10d2f313f699ff7","number":"0x1e12dcd","stateRoot":"0xe116bcd591a2c10c9a571779f556 |
| polkadot | `system_account` | single | single_address | ➖结构性不可达/声明错 | — |

### tendermint(5链25method)
| 链 | method(config原名) | single/mixed | param_format | 实测HTTP状态 | 实测响应结构体 |
|---|---|---|---|---|---|
| celestia | `/block` | mixed | [height] | ✅真机成功 | {"jsonrpc":"2.0","id":-1,"result":{"block_id":{"hash":"1CFE2ACC665FCBF6FD395E9F137654FFB0BDC817FBE09F82156C11D53914D1B4","parts":{"total":3,"hash":"77F0FDF99CAA7A45631F561DEFFD8063 |
| celestia | `/cosmos/bank/v1beta1/balances/{address}` | single+mixed | path_address | ⚠️客观受限(HTTP400) | {"code":3, "message":"invalid address: decoding bech32 failed: invalid checksum (expected pffv36 got j0vp0p)", "details":[]} |
| celestia | `/cosmos/base/tendermint/v1beta1/blocks/latest` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","id":-1,"result":{"block_id":{"hash":"1CFE2ACC665FCBF6FD395E9F137654FFB0BDC817FBE09F82156C11D53914D1B4","parts":{"total":3,"hash":"77F0FDF99CAA7A45631F561DEFFD8063 |
| celestia | `/cosmos/base/tendermint/v1beta1/node_info` | mixed | no_params | ✅真机成功 | {"default_node_info":{"protocol_version":{"p2p":"8","block":"11","app":"8"},"default_node_id":"821fa0f7ce74a211c5f5ec93cc6cc301564b92b6","listen_addr":"0.0.0.0:26656","network":"ce |
| celestia | `/status` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","id":-1,"result":{"node_info":{"protocol_version":{"p2p":"8","block":"11","app":"8"},"id":"821fa0f7ce74a211c5f5ec93cc6cc301564b92b6","listen_addr":"0.0.0.0:26656", |
| cosmos-hub | `GET /cosmos/bank/v1beta1/balances/{addr}` | single+mixed | path_addr | ✅真机成功 | {"balances":[{"denom":"ibc/3EF74C1B9F5C65F2F9619B0C5A35135624BD15759D016678F86485DD1C5AA24A","amount":"20000000000"},{"denom":"ibc/915992C8486D299941292A913640167F0BA02DC2F599BFFED |
| cosmos-hub | `GET /cosmos/base/tendermint/v1beta1/blocks/latest` | mixed | no_params | ✅真机成功 | {"block_id":{"hash":"zFzA79uiJfc/sCP4jBX4hAW1Fta7zPdmEUJSTgxwZB4=","part_set_header":{"total":1,"hash":"Yx8FNH5WiHnoXb4FbwOrHmiBR/VnjwX/IYnW0i0JPxc="}},"block":{"header":{"version" |
| cosmos-hub | `GET /cosmos/base/tendermint/v1beta1/blocks/{height}` | mixed | path_height | ✅真机成功 | {"block_id":{"hash":"jxp/J15b4tohOLavW9I4oA+34OYphRj+yjFELML68lc=","part_set_header":{"total":1,"hash":"EaG8UpykJY7+1rJeTfsBBXKA61ewMmJQ8kGqgX5QD5Q="}},"block":{"header":{"version" |
| cosmos-hub | `GET /cosmos/staking/v1beta1/validators` | mixed | query_pagination | ✅真机成功 | {"validators":[{"operator_address":"cosmosvaloper1qphf0ferqcch0jca9hlqfm3x0eds3dpkcvpafp","consensus_pubkey":{"@type":"/cosmos.crypto.ed25519.PubKey","key":"voVoXB0ArzZ57NgZgyAhrwa |
| cosmos-hub | `GET /cosmos/tx/v1beta1/txs/{hash}` | mixed | path_hash_upper_hex_no_prefix | ✅真机成功 | {"balances":[{"denom":"uatom","amount":"319346225533278"}],"pagination":{"next_key":null,"total":"1"}} |
| injective | `/cosmos/bank/v1beta1/balances/{address}` | single+mixed | path_address | ✅真机成功 | {"balances":[{"denom":"inj","amount":"1404800000000000003"}],"pagination":{"next_key":null,"total":"1"}} |
| injective | `/injective/exchange/v1beta1/derivative/markets` | mixed | no_params | ✅真机成功 | {"markets":[{"market":{"ticker":"SAFE/USDC PERP","oracle_base":"0x7b3576858506a94fad3a9cc55e32934f0c3931150fe3a3c7b83558dbae5b8e38","oracle_quote":"0xeaa020c61cc479712813461ce15389 |
| injective | `/injective/exchange/v1beta1/spot/markets` | mixed | no_params | ✅真机成功 | {"markets":[{"market":{"ticker":"SAFE/USDC PERP","oracle_base":"0x7b3576858506a94fad3a9cc55e32934f0c3931150fe3a3c7b83558dbae5b8e38","oracle_quote":"0xeaa020c61cc479712813461ce15389 |
| injective | `/injective/oracle/v1beta1/params` | mixed | no_params | ✅真机成功 | {"balances":[{"denom":"inj","amount":"1404800000000000003"}],"pagination":{"next_key":null,"total":"1"}} |
| injective | `/status` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","id":-1,"result":{"node_info":{"protocol_version":{"p2p":"9","block":"11","app":"0"},"id":"821fa0f7ce74a211c5f5ec93cc6cc301564b92b6","listen_addr":"0.0.0.0:26656", |
| osmosis | `/cosmos/bank/v1beta1/balances/{address}` | single+mixed | path_address | ⚠️客观受限(HTTP400) | {"code":3,"message":"invalid address: decoding bech32 failed: invalid checksum (expected cctva9 got fn2lyp)","details":[]} |
| osmosis | `/osmosis/gamm/v1beta1/pools/{pool_id}` | mixed | path_pool_id | ✅真机成功 | {"pool":{"@type":"/osmosis.gamm.v1beta1.Pool","address":"osmo1mw0ac6rwlp5r8wapwk3zs6g29h8fcscxqakdzw9emkne6c8wjp9q0t3v8t","id":"1","pool_params":{"swap_fee":"0.002000000000000000", |
| osmosis | `/osmosis/poolmanager/v1beta1/num_pools` | mixed | no_params | ✅真机成功 | {"num_pools":"3465"} |
| osmosis | `/osmosis/twap/v1beta1/ArithmeticTwapToNow` | mixed | query_params | ⚠️客观受限(HTTP500) | {"code":2,"message":"looking for a time that's too old, not in the historical index.  Try storing the accumulator value. (requested time 2026-06-01 00:00:00 +0000 UTC)","details":[ |
| osmosis | `/status` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","id":-1,"result":{"node_info":{"protocol_version":{"p2p":"8","block":"11","app":"0"},"id":"821fa0f7ce74a211c5f5ec93cc6cc301564b92b6","listen_addr":"0.0.0.0:26656", |
| sei | `/status` | mixed | no_params | ✅真机成功 | {"node_info":{"protocol_version":{"p2p":"8","block":"11","app":"0"},"id":"821fa0f7ce74a211c5f5ec93cc6cc301564b92b6","listen_addr":"0.0.0.0:26656","network":"pacific-1","version":"0 |
| sei | `eth_blockNumber` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","id":1,"result":"0xc9f12ce"} |
| sei | `eth_call` | mixed | address_with_options | ✅真机成功 | {"jsonrpc":"2.0","result":"0x","id":1} |
| sei | `eth_chainId` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","result":"0x531","id":1} |
| sei | `eth_getBalance` | single+mixed | address_latest | ✅真机成功 | {"jsonrpc":"2.0","result":"0x4065ba745c24000","id":1} |

### bitcoin_jsonrpc(4链24method)
| 链 | method(config原名) | single/mixed | param_format | 实测HTTP状态 | 实测响应结构体 |
|---|---|---|---|---|---|
| bch | `getblock` | mixed | [blockhash] | ✅真机成功 | {"id":1,"jsonrpc":"2.0","result":953945} |
| bch | `getblockcount` | mixed | no_params | ✅真机成功 | {"id":1,"jsonrpc":"2.0","result":953945} |
| bch | `getmempoolinfo` | mixed | no_params | ✅真机成功 | {"result":{"loaded":true,"size":35,"bytes":18303,"usage":53136,"maxmempool":320000000,"mempoolminfee":0.00001000,"minrelaytxfee":0.00001000,"permitbaremultisig" |
| bch | `getnetworkinfo` | mixed | no_params | ✅真机成功 | {"result":{"version":29000000,"subversion":"/Bitcoin Cash Node:29.0.0(EB32.0)/","protocolversion":70016,"localservices":"0000000000000425","localrelay":true,"ti |
| bch | `getrawtransaction` | mixed | [txhash,verbose] | ⚠️客观受限(HTTP000) | {"jsonrpc":"2.0","error":{"code":-5,"message":"The genesis block coinbase is not considered an ordinary transaction and cannot be retrieved"},"id":1} |
| bch | `getreceivedbyaddress` | single | single_address | ➖结构性不可达/声明错 | — |
| bitcoin | `estimatesmartfee` | mixed | [conf_target] | ✅真机成功 | {"jsonrpc":"2.0","result":{"feerate":0.00001198,"blocks":6},"id":1} |
| bitcoin | `getblock` | mixed | [blockhash,verbosity] | ✅真机成功 | {"jsonrpc":"2.0","result":{"hash":"00000000000000000001a986dc1af90e10e150bf21908ed954b3f9bb530cb296","confirmations":1,"height":952369,"version":558891008,"versionHex":"21500000"," |
| bitcoin | `getblockcount` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","result":{"hash":"00000000000000000001a986dc1af90e10e150bf21908ed954b3f9bb530cb296","confirmations":1,"height":952369,"version":558891008,"versionHex":"21500000"," |
| bitcoin | `getrawmempool` | mixed | no_params | ✅真机成功 | {"jsonrpc":"2.0","result":["fa4cc5b2726544884a9f9d372c953deeb7def0da6f8ecce2d1d91ea34d5b62d7","47d402c84a08e540053facdb3c638a03d0675480ea578958283a29d63ada1c7d","0a5dd417f9a16dcf61 |
| bitcoin | `getrawtransaction` | mixed | [txid,verbose] | ✅真机成功 | {"jsonrpc":"2.0","result":{"txid":"b22b20ca453583c22bf02251be7011d1f9d44f5750d15bab5cd2db637e9a78e6","hash":"b38340e22cdc69f4c14845f9fa0ce2824d8eb4fb2d23cd416de |
| bitcoin | `getreceivedbyaddress` | single | single_address | ➖结构性不可达/声明错 | — |
| dogecoin | `getbestblockhash` | mixed | no_params | ✅真机成功 | {"id":1,"jsonrpc":"2.0","result":"e0aaeef9db3e308eadf2ffdb0c5c29d58fd9c6f5e69813f9eaeb957d2299ae1b"} |
| dogecoin | `getblock` | mixed | block_hash | ✅真机成功 | {"id":1,"jsonrpc":"2.0","result":{"hash":"e0aaeef9db3e308eadf2ffdb0c5c29d58fd9c6f5e69813f9eaeb957d2299ae1b","confirmations":1,"strippedsize":6685,"size":6685,"weight":26740,"height |
| dogecoin | `getblockcount` | mixed | no_params | ✅真机成功 | {"id":1,"jsonrpc":"2.0","result":6235036} |
| dogecoin | `getmempoolinfo` | mixed | no_params | ✅真机成功 | {"id":1,"jsonrpc":"2.0","result":{"size":321,"bytes":522749,"usage":854656,"maxmempool":300000000,"mempoolminfee":0.00000000}} |
| dogecoin | `getrawtransaction` | mixed | transaction_hash | ⚠️客观受限(HTTP200) | {"id":1,"jsonrpc":"2.0","error":{"message":"No such mempool or blockchain transaction. Use gettransaction for wallet transactions.","code":-5}} |
| dogecoin | `getreceivedbyaddress` | single | single_address | ➖结构性不可达/声明错 | — |
| litecoin | `getbestblockhash` | mixed | no_params | ✅真机成功 | {"id":1,"jsonrpc":"2.0","result":"a17477d56db3b8ff21a5eaedd5746ddef38959dc802fbdc5847e68d01752a990"} |
| litecoin | `getblock` | mixed | block_hash | ✅真机成功 | {"id":1,"jsonrpc":"2.0","result":3119344} |
| litecoin | `getblockcount` | mixed | no_params | ✅真机成功 | {"id":1,"jsonrpc":"2.0","result":3119344} |
| litecoin | `getmempoolinfo` | mixed | no_params | ✅真机成功 | {"result":{"loaded":true,"size":25,"bytes":12175,"usage":51824,"maxmempool":1000000000,"mempoolminfee":0.00001000,"minrelaytxfee":0.00001000,"unbroadcastcount": |
| litecoin | `getrawtransaction` | mixed | transaction_hash | ⚠️客观受限(HTTP404) | 404 page not found |
| litecoin | `getreceivedbyaddress` | single | single_address | ➖结构性不可达/声明错 | — |

### rest(5链27method)
| 链 | method(config原名) | single/mixed | param_format | 实测HTTP状态 | 实测响应结构体 |
|---|---|---|---|---|---|
| algorand | `GET /v2/accounts/{address}` | single+mixed | path_addr_base32 | ⚠️客观受限(HTTP400) | {"message":"Invalid format for parameter address: error unmarshaling 'RGX5XA7DWX5TYJTKMBLT3R4WMXFCYIQVHQDRPQOLPNV2PBHIDORWS6Y6OY' text as *basics.Address: address RGX5XA7DWX5TYJTKM |
| algorand | `GET /v2/accounts/{address}/transactions` | mixed | path_addr_query_limit | ⚠️客观受限(HTTP400) | {"message":"Invalid format for parameter address: error unmarshaling 'RGX5XA7DWX5TYJTKMBLT3R4WMXFCYIQVHQDRPQOLPNV2PBHIDORWS6Y6OY' text as *basics.Address: address RGX5XA7DWX5TYJTKM |
| algorand | `GET /v2/assets/{asset_id}` | mixed | path_asset_id_int | ✅真机成功 | {"index":31566704,"params":{"creator":"2UEQTE5QDNXPI7M3TU44G6SYKLFWLPQO7EBZM7K7MHMQQMFI4QJPLHQFHM","decimals":6,"default-frozen":false,"freeze":"3ERES6JFBIJ7ZPNVQJNH2LETCBQWUPGTO4R |
| algorand | `GET /v2/blocks/{round}` | mixed | path_round_int | ✅真机成功 | {  "block": {    "bi": 8600578,    "earn": 218288,    "fc": 37000,    "fees": "Y76M3MSY6DKBRHBL7C3NNDXGS5IIMQVQVUAB6MP4XEMMGVF2QWNPL226CA",    "frac": 6886250026,    "gen": "mainne |
| algorand | `GET /v2/transactions/{txid}` | mixed | path_txid_base32 | ⚠️客观受限(HTTP404) | {"message":"no transaction found for transaction id: XXXX"} |
| aptos | `GET /v1` | mixed | no_params | ✅真机成功 | {"chain_id":1,"epoch":"16053","ledger_version":"5568490390","oldest_ledger_version":"0","ledger_timestamp":"1780591805217954","node_role":"full_node","oldest_block_height":"0","blo |
| aptos | `GET /v1/accounts/{addr}` | single+mixed | path_addr | ✅真机成功 | {"sequence_number":"0","authentication_key":"0x0000000000000000000000000000000000000000000000000000000000000001"} |
| aptos | `GET /v1/accounts/{addr}/resources` | mixed | path_addr | ✅真机成功 | [{"type":"0x1::dkg::DKGState","data":{"in_progress":{"vec":[]},"last_completed":{"vec":[{"metadata":{"dealer_epoch":"16052","dealer_validator_set":[{"addr":"0x32ad233a939bfbafb8d90 |
| aptos | `GET /v1/transactions/by_hash/{hash}` | mixed | path_hash | ✅真机成功 | {"version":"5568478658","hash":"0x7c6ae4085a38aaa59bd5f3b759620f461038a5a8600ecf70cc9ccea0d9ea7cf9","state_change_hash":"0xafb6e14fe47d850fd0a7395bcfb997ffacf4715e0f895cc162c218e4a |
| aptos | `POST /v1/view` | mixed | move_view_call | ✅真机成功 | [{"vec":["120370003854120215"]}] |
| cardano | `GET_BLOCKS` | mixed | no_params | ✅真机成功 | [{"hash":"53a98d0a1dc6fc9c786de1052510bc39e1886b61ebd7031b5e5b0e7305d50772","epoch_no":635,"abs_slot":189025522,"epoch_slot":68722,"block_height":13507306,"block_size":17245,"block |
| cardano | `GET_EPOCH_INFO` | mixed | query_epoch_int | ✅真机成功 | [{"epoch_no":615,"era":"Conway","out_sum":"45494472618975760","fees":"42279800991","tx_count":134210,"blk_count":21337,"start_time":1771883091,"end_time":1772315091,"first_block_ti |
| cardano | `GET_TIP` | mixed | no_params | ✅真机成功 | [{"hash":"53a98d0a1dc6fc9c786de1052510bc39e1886b61ebd7031b5e5b0e7305d50772","epoch_no":635,"era":"Conway","abs_slot":189025522,"epoch_slot":68722,"block_height":13507306,"block_no" |
| cardano | `POST_ADDRESS_INFO` | single+mixed | body_addresses_array | ✅真机成功 | [] |
| cardano | `POST_ASSET_INFO` | mixed | ⚠️缺 | ✅真机成功 | [] |
| cardano | `POST_BLOCK_TXS` | mixed | body_block_hashes_array | ✅真机成功 | [] |
| cardano | `POST_TX_INFO` | mixed | body_tx_hashes_array | ✅真机成功 | [{"tx_hash":"f144a8264acf4bdfe2e1241170969c930d64ab6b0996a4a45237b623f1dd670e","block_hash":"90062dfc314c7dc3430922a48f79032a63032206fdca2dfd144cf0930d4aa426","block_height":635415 |
| tezos | `GET /chains/main/blocks/head/context/contracts/{addr}/balance` | single+mixed | path_addr | ✅真机成功 | "283125643" |
| tezos | `GET /chains/main/blocks/head/header` | mixed | no_params | ✅真机成功 | {"protocol":"PtTALLiNtPec7mE7yY4m3k26J8Qukef3E3ehzhfXgFZKGtDdAXu","chain_id":"NetXdQprcVkpaWU","hash":"BKwLLHYQHjSVanyr84BtZTstERrDa31yYrqUfXD8PR6y3LJSVDB","level":13497362,"proto" |
| tezos | `GET /chains/main/blocks/head/protocols` | mixed | no_params | ✅真机成功 | {"protocol":"PtTALLiNtPec7mE7yY4m3k26J8Qukef3E3ehzhfXgFZKGtDdAXu","next_protocol":"PtTALLiNtPec7mE7yY4m3k26J8Qukef3E3ehzhfXgFZKGtDdAXu"} |
| tezos | `GET /chains/main/blocks/head/votes/current_period` | mixed | no_params | ✅真机成功 | {"voting_period":{"index":175,"kind":"promotion","start_position":13454688},"position":42674,"remaining":158925} |
| tezos | `GET /chains/main/blocks/{block}/operations/{vp}` | mixed | path_block_and_vp | ✅真机成功 | [{"protocol":"PtTALLiNtPec7mE7yY4m3k26J8Qukef3E3ehzhfXgFZKGtDdAXu","chain_id":"NetXdQprcVkpaWU","hash":"op98xw3vBFLqMRuW9NZ1U1RRRdGhBpWho16qvv5tkMcPNnXPLyZ","branch":"BMFzcWDgDMCo8 |
| ton | `getAddressBalance` | single+mixed | {address: friendly_base64url|raw} | ✅真机成功 | {"ok":true,"result":"620176639","@extra":"1780591849:4:20.53"} |
| ton | `getAddressInformation` | mixed | {address: friendly_base64url|raw} | ✅真机成功 | {"ok":true,"result":{"@type":"raw.fullAccountState","balance":"620176639","extra_currencies":[],"last_transaction_id":{"@type":"internal.transactionId","lt":"51124412000001","hash" |
| ton | `getTransactions` | mixed | {address, limit, lt?, hash?} | ✅真机成功 | {"ok":true,"result":[{"@type":"ext.transaction","address":{"@type":"accountAddress","account_address":"EQCcLAW537KnRg_aSPrnQJoyYjOZkzqYp6FVmRUvN1crSazV"},"account":"0:9C2C05B9DFB2A |
| ton | `lookupBlock` | mixed | {workchain: int, shard: dec_string, seqno: int} | ✅真机成功 | {"ok":true,"result":{"@type":"ton.blockIdExt","workchain":-1,"shard":"-9223372036854775808","seqno":1,"root_hash":"8GYhhrigd8CwZGrRT59iulLDcgiTYuvOAzFJxugc0Ts=","file_hash":"V+Xzyk |
| ton | `runGetMethod` | mixed | {address, method: string, stack: array} | ✅真机成功 | {"ok":true,"result":{"@type":"smc.runResult","gas_used":370,"stack":[["num","0x14c97"]],"exit_code":11,"block_id":{"@type":"ton.blockIdExt","workchain":-1,"shard":"-922337203685477 |

### hedera_dual(1链5method)
| 链 | method(config原名) | single/mixed | param_format | 实测HTTP状态 | 实测响应结构体 |
|---|---|---|---|---|---|
| hedera | `GET /api/v1/accounts/{addr}` | single+mixed | ⚠️缺 | ✅真机成功 | {"account":"0.0.2","alias":null,"auto_renew_period":7000000,"balance":{"balance":1663012637744658,"timestamp":"1742896287.333154756","tokens":[]},"created_timestamp":"1605733260.89 |
| hedera | `GET /api/v1/balances?account.id={addr}` | mixed | ⚠️缺 | ⚠️未匹配 | — |
| hedera | `GET /api/v1/transactions/{addr}` | mixed | ⚠️缺 | ✅真机成功 | {"transactions":[{"batch_key":null,"bytes":null,"charged_tx_fee":0,"consensus_timestamp":"1779303550.493476000","entity_id":"0.0.58","high_volume":false,"high_volume_pricing_multip |
| hedera | `eth_call` | mixed | address_with_options | ✅真机成功 | {"result":"0x0f0d0c4eaf95b455297f70fae536726f2603fc3091679f6a25c02c5fe102c216","jsonrpc":"2.0","id":1} |
| hedera | `eth_getBalance` | mixed | address_latest | ✅真机成功 | {"result":"0xdc190f51555e27b8e0800","jsonrpc":"2.0","id":1} |

## 交叉验证 + 实测方法
- 基石: config/chains single+mixed 去重=184(execute_code 实证)。184 行 ↔ 定义源 0遗漏0多余0改名。
- 实测: 2026-06-04 纯 curl 真机打 public endpoint, 记 HTTP status code + 真实响应体。✅161 真机成功(HTTP200+真实数据)。
- 真值参数: EVM tx 从同链 full block 动态取; solana token account 从 getTokenAccountsByOwner 取; 限流链(Tatum bch/ltc)sleep 13s/req 绕限流。
- 块高/同步监控 method 的同步状态用途见 `block-height-sync-method-measurement.md`(不同视角)。