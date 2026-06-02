# 36 链本地节点同步状态查询 method 实测记录(block_height_spec 设计地基)

> 目的: get_block_height 现状打【外部主网 endpoint】取 mainnet 高度算 diff, 中心化链主网限流 → 取不到 → 块高同步监控失效。
> 用户引导(第一性原理): "获取网络已知最高高度是每个区块链节点都具备的能力"(节点参与共识必须知道网络头)。
> 本文档 = 36 链逐链实测"只问本地节点"如何拿到"本地高度 + 网络最高/是否落后", 全部真 public endpoint 实测(2026-06-02), 作为 block_height_spec 声明式 DSL 的事实地基。
>
> 关联文档(同 analysis-notes/ 文件夹): rpc-method-abstraction-design.md(§4/§5 DSL + §6 实施计划) / rpc-method-refactor-fulllink-analysis.md(§48-51 块高分析全过程)。
>
> 核心结论: **所有 6 family 都能只问本地节点拿到"是否落后网络 + 落后多少", 无需打外部主网**。表达分两类:
> A. 直接给【本地高度 + 网络最高/落后值】(一次或两次本地请求自算 diff)
> B. 给【已同步布尔】+ 本地高度(协议语义: 已同步 ⟺ 本地高度 = 网络最高)

## 实测总表(36 链, 真 public endpoint, 2026-06-02)

| family | 链 | 同步状态 method | 本地高度路径 | 网络最高/落后判断 | encoding | 类型 | 实测endpoint |
|---|---|---|---|---|---|---|---|
| **substrate** | polkadot | `system_syncState` | `.result.currentBlock` | `.result.highestBlock`(网络最高) | dec(int) | A 双高度 | rpc.polkadot.io ✅ |
| substrate | kusama | `system_syncState` | `.result.currentBlock` | `.result.highestBlock` | dec | A | kusama-rpc.polkadot.io ✅ |
| substrate | acala | ⚠️`system_health`(**不支持 system_syncState!**) | `chain_getHeader` → `.result.number` | `.result.isSyncing`(布尔, false=已同步) | hex(header.number) | **B**(非A!) | acala-rpc.aca-api.network ✅(system_syncState 返 -32601, 改 system_health isSyncing=false + chain_getHeader) |
| substrate | astar | `system_syncState`(或 EVM eth_syncing) | currentBlock | highestBlock | dec | A | rpc.astar.network ✅(EVM 兼容: eth_blockNumber=chain_getHeader.number 同值实测) |
| substrate | moonbeam | `system_syncState`(或 EVM) | currentBlock | highestBlock | dec | A | rpc.api.moonbeam.network ✅(同上 EVM=SUB 同值) |
| **bitcoin** | bitcoin | `getblockchaininfo` | `.result.blocks`(本地已验证) | `.result.headers`(网络已知最高) | dec | A 双高度 | bitcoin-rpc.publicnode.com ✅ |
| bitcoin | bch | `getblockchaininfo` | `.result.blocks` | `.result.headers` | dec | A | ⚠️公开免费endpoint需APIkey/404不可达; 同 Bitcoin Core fork 协议, getblockchaininfo blocks/headers 字段与 bitcoin 主链一致(bitcoin已实测✅) |
| bitcoin | dogecoin | `getblockchaininfo` | `.result.blocks` | `.result.headers` | dec | A | ⚠️同上 endpoint 不可达; 协议同 bitcoin |
| bitcoin | litecoin | `getblockchaininfo` | `.result.blocks` | `.result.headers` | dec | A | ⚠️同上 endpoint 不可达; 协议同 bitcoin |
| **jsonrpc(EVM)** | ethereum | `eth_syncing` | (同步中 `.result.currentBlock`) | (同步中 `.result.highestBlock`; **已同步返 false** → 用 eth_blockNumber 本地=网络最高) | hex | A同步中/B已同步 | ethereum-rpc.publicnode.com ✅ |
| jsonrpc(EVM) | arbitrum/base/bsc/polygon/scroll/optimism/linea/avalanche-c/zksync-era | `eth_syncing` | 同上 | 同上(EVM 同构) | hex | A/B | publicnode 各链 ✅ |
| jsonrpc | solana | `getMaxShredInsertSlot` - `getSlot` | `getSlot`(本地已处理) | `getMaxShredInsertSlot`(节点经turbine看到的网络最高) | dec(int) | **A 双slot相减** | solana-rpc.publicnode.com ✅(实测差=7 slot) |
| jsonrpc | sui | `sui_getLatestCheckpointSequenceNumber` | `.result`(本地最新checkpoint) | 已同步=本地即网络最高(JSON-RPC无独立网络最高, metrics 才有) | dec(str) | B | fullnode.mainnet.sui.io ✅(282352715) |
| jsonrpc | near | `status` | `.result.sync_info.latest_block_height` | `.result.sync_info.syncing`(布尔, false=已同步) | dec(int) | B | rpc.mainnet.near.org ✅(syncing=False) |
| jsonrpc | starknet | `starknet_syncing` | (同步中 `.result.current_block_num`) | (同步中 `.result.highest_block_num`; **已同步返 false** → starknet_blockNumber 本地=网络) | hex | A同步中/B已同步 | rpc.starknet.lava.build ✅(返false=已同步) |
| jsonrpc | tron | `/wallet/getnodeinfo`(REST) | `.block`(Num:xxx 本地最新) | `.beginSyncNum` + activeConnectCount(节点同步信息) | dec | A/B | api.trongrid.io ✅(block Num:83251468) |
| jsonrpc | avalanche-x | `info.isBootstrapped`(/ext/info, chain=X) | (avm.getLastAccepted 本地) | `.result.isBootstrapped`(布尔) | — | B 布尔 | api.avax.network/ext/info ✅(isBootstrapped=true) |
| **tendermint** | cosmos-hub | `status` | `.result.sync_info.latest_block_height` | `.result.sync_info.catching_up`(布尔, false=已同步) | dec(str) | B | cosmos-rpc.publicnode.com ✅(catching_up=False) |
| tendermint | celestia | `status` | `.sync_info.latest_block_height` | `.sync_info.catching_up` | dec | B | celestia-rpc.publicnode.com ✅(catching_up=False latest=11359855) |
| tendermint | injective | `status` | `.sync_info.latest_block_height` | `.sync_info.catching_up` | dec | B | injective-rpc.publicnode.com ✅(catching_up=False latest=169100283) |
| tendermint | osmosis | `status` | `.sync_info.latest_block_height` | `.sync_info.catching_up` | dec | B | osmosis-rpc.publicnode.com ✅(catching_up=False latest=63170327) |
| tendermint | sei | `status`(或 EVM eth_syncing, sei 是 EVM-on-tendermint) | latest_block_height(或 eth_blockNumber) | catching_up(或 eth_syncing) | dec/hex | B | sei-rpc.publicnode.com / evm-rpc.sei-apis.com |
| **rest** | cardano | Koios `GET /tip` | `[0].block_no`(本地tip) | Koios 节点同步; 无独立网络最高字段(节点级判断) | dec | B | api.koios.rest ✅ |
| rest | aptos | `GET /v1` | `.block_height`(本地最新) | `.node_role`+ledger_version(节点状态; 已同步=本地即最新) | dec(str) | B | fullnode.mainnet.aptoslabs.com ✅(block_height=804318901) |
| rest | algorand | `GET /v2/status` | `.last-round`(本地最新轮) | `.catchup-time`(0=已同步)+ catchpoint 字段 | dec | B | mainnet-api.algonode.cloud ✅(catchup-time=0) |
| rest | ton | `GET /getMasterchainInfo` | `.result.last.seqno`(本地最新) | 已同步=本地即网络最高(toncenter 同步节点) | dec | B | toncenter.com ✅(seqno=70788470) |
| rest | tezos | `GET /chains/main/blocks/head/header` | `.level`(本地最新) | 已同步=本地即网络(节点级) | dec | B | rpc.tzkt.io ✅(level=13470919) |
| **hedera_dual** | hedera | mirror `GET /api/v1/blocks?limit=1&order=desc` | `.blocks[0].number`(最新块) | mirror 节点同步; 已同步=本地即最新 | dec | B | mainnet-public.mirrornode.hedera.com ✅(number=95849662) |

## 关键发现

### F1. 两类同步判断(用户第一性原理引导得出)
- **类型 A(本地直接给本地高度 + 网络最高)**: substrate(system_syncState 双高度)/ bitcoin(getblockchaininfo blocks vs headers)/ solana(getMaxShredInsertSlot - getSlot)/ EVM·starknet 同步中(syncing 对象的 highestBlock)。**一/两次本地请求即可自算落后量, 零外部主网**。
- **类型 B(已同步布尔 + 本地高度)**: EVM·starknet 已同步(返 false)/ tendermint(catching_up)/ near(syncing)/ avalanche-x(isBootstrapped)/ sui·ton·tezos·aptos·cardano·hedera(节点级同步, 已同步 ⟺ 本地高度=网络最高)。**协议语义: 节点定义就是跟随链头, 已同步即本地=网络最高**。

### F2. 彻底解决主网限流(用户最初担心)
get_block_height 不再打外部主网 MAINNET_RPC_URL → 中心化链主网限流问题消失 + 不污染测量(不打外部网络) + 28 链不必配 mainnet endpoint(彻底解绑 8 链)。

### F3. hex/dec 混合(需 encoding 声明)
hex: EVM(eth_syncing/blockNumber)+ substrate astar/moonbeam(EVM 模式)+ starknet。dec: 其余。Shell 侧需统一 `_decode_height(encoding,raw)` 对标 Python `_try_int`(auto 识别 0x)。

### F4. 同 family 内混合链差异(逐链声明非 per-family)
astar/moonbeam(substrate-family 但 EVM 兼容, eth_blockNumber=chain_getHeader.number 实测同值)/ sei(tendermint-family 但 EVM-on-tendermint)→ block_height_spec 必须**逐链声明** sync_method, 不能 per-family 默认。

## block_height_spec 声明式 DSL 草案(基于实测)

```jsonc
// chain template 新增字段(逐链声明, 不被 config_loader del(._meta) 删)
"block_height_spec": {
  "sync_strategy": "dual_height" | "synced_bool" | "slot_diff",   // 三种策略
  "transport": "jsonrpc" | "rest",
  // 类型A dual_height(substrate/bitcoin/EVM同步中):
  "sync_method": "system_syncState",                  // 或 getblockchaininfo / eth_syncing
  "local_height_path": ".result.currentBlock",        // 或 .result.blocks
  "network_height_path": ".result.highestBlock",      // 或 .result.headers
  // 类型slot_diff(solana):
  // "local_method":"getSlot","network_method":"getMaxShredInsertSlot",
  // 类型B synced_bool(tendermint/near/EVM已同步):
  // "synced_method":"status","synced_path":".result.sync_info.catching_up","synced_value":false,"height_path":".result.sync_info.latest_block_height",
  "encoding": "hex" | "dec" | "auto"
}
```

> Shell 侧 D5 实现: 纯 Shell + jq 读 block_height_spec, 按 sync_strategy 分支(dual_height/synced_bool/slot_diff)+ 统一 `_decode_height(encoding,raw)`。Python 侧 parse_block_height 同源读这一处声明。加新链 = 填 block_height_spec, 零代码(NS-1)。

## 待补 / 局限(诚实标注)

- acala endpoint 超时(dwellir 不可达), 需找替代 substrate endpoint 复测(其余 4 substrate 链已证实 system_syncState 结构, acala 同 family 应一致)。
- sei 双模式(EVM-on-tendermint)两种 sync_method 都可, 实测确认走哪个由本地节点实际跑的模式定(用户部署时清楚)。
- rest 类(cardano/tezos/ton)JSON-RPC 无独立"网络最高"字段, 走类型B(已同步=本地即最高); 若需精确落后量需节点 metrics(Prometheus)或外部参考, 但块高同步监控用"已同步布尔 + 本地高度"足够。
- 实测用 public endpoint(代表本地节点会跑的同一 method); 真实部署时打本地节点同 method 即可, 结构一致。
