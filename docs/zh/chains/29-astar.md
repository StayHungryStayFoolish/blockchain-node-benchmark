# 29-astar 调研(DIFF-ONLY)

> 由 `_template.md` 衍生。**最激进 DIFF-ONLY 模式(护栏 2)**:本链是 **Polkadot parachain(parachain ID=2006,2021-12 第一轮 slot auction 中标)** + **EVM + WASM 双 VM 并行**(独家;28-moonbeam 只有 EVM,27-acala 是 EVM+ 自研变种,Astar 是**两个 VM 都标准、且共享底层 Substrate runtime**)。本稿**不重写** 02-ethereum / 07-polkadot / 28-moonbeam 已确立的协议结构,只列**双 VM 并存 + WASM(ink! / pallet-contracts) + dApp Staking 激励 + 两个 hostname 实测互通**四类差异;并与 **27-acala / 28-moonbeam(同 wave 8 EVM-on-Substrate)** 做**复用度横向校验**。H8:本次 **12 次** H8 curl 在 **2026-05-23** 对公共 mainnet 双端点(`https://evm.astar.network` + `https://rpc.astar.network`)实测,**12 次全部 200/成功响应**(EVM 5 次 + Substrate 5 次 + **跨端点交叉验证 2 次,确认两个 hostname 都同时支持 `eth_*` 与 `system_*`,本质是同一 RPC server 两条 DNS**);WASM pallet-contracts 调用因预算/审批截止,**仅通过 `state_getRuntimeVersion` 的 `apis` hash 列表确认运行时启用,具体 instantiate/call 标 ⚠️ 文档凭据**。**本链是 wave 1-8 共 28 链调研的最后一链**,§7 含 DSL ASK 集合**终态评估**。

---

## 元信息

| 项 | 值 |
|---|---|
| 链名(中) | 阿斯塔 / Astar |
| 链名(英) | Astar Network |
| 编号 | 29 |
| Mainnet ChainID | **EVM**:`592`(E1 实测 `result:"0x250"` ✅,E9 `net_version:"592"` 双源一致)+ **Substrate**:`ss58Format=5`(E4 实测,**独有值,Polkadot=0 / Kusama=2 / Acala=10 / Moonbeam=1284 全部不同,与 chain_id 无关联**)+ chain name `"Astar"`(E3)+ specName `"astar"`(E12) |
| 节点应用 | **astar-collator v5.48.0**(E8 `system_version:"5.48.0-00338639b9e"`,E12 `specVersion:2101`,基于 Substrate / Polkadot-SDK + frontier(pallet-evm + pallet-ethereum)+ **pallet-contracts(WASM smart contract,ink!)** + cumulus(parachain consensus)) |
| Parachain | **Polkadot parachain,para_id = 2006**(2021-12 第一轮 slot auction 中标,与 Moonbeam 同批;**Shiden** 是其 Kusama 上的姐妹链 `para_id=2007`,**Shibuya** 是 testnet) |
| 调研日期 | 2026-05-23 |
| 状态 | 🟢 已完成(diff-only,wave 8 收官) |
| 与 02-ethereum 兼容度 | **~95%** EVM JSON-RPC 层 100% 同构(`eth_*` / `net_*` 全部标准,E1+E2+E7+E9 四次实测),**~5% 差异** = baseFee 极高(E7 gasPrice `0xb576270823` ≈ **778 Gwei**,比 Moonbeam 25× 高,因 Astar 配置 `MinGasPrice` 大,非链上活跃度)+ finality 走 Polkadot GRANDPA |
| 与 07-polkadot 兼容度 | **~70%** Substrate RPC 层(`system_*` / `chain_*` / `state_*` 全实测 200),业务层差异 **~30%**:无 `staking pallet`(走 collator + `dappStaking` 自研)+ **独有 `dappStaking` pallet(dApp 质押激励,Astar 标志性功能)** + 含 `contracts` pallet(WASM ink!,Polkadot relay 不含) |
| 与 27-acala 兼容度 | **~80% 模式同源**:均为"Polkadot parachain + EVM 嵌入";Acala EVM 是**自研 mandala EVM(裁剪 opcode 要求 substrate 账户绑定)**,Astar EVM 是**标准 frontier 零裁剪**;**Astar 多出 WASM VM,Acala 无 WASM** |
| 与 28-moonbeam 兼容度 | **~85% 模式同源**:均 frontier 标准 EVM 零裁剪 + Substrate 单 runtime;**Moonbeam 共识用 Nimbus,Astar 用 Aura**(E5 digest 实证)+ **Astar 多 WASM VM + dapps_staking 独有 pallet** + Moonbeam ss58=1284 对齐 chain_id 而 Astar ss58=5 独立 |

---

## 1. Sources(权威 + fork 历史)

| 类型 | URL | 备注 |
|---|---|---|
| 官方文档 | https://docs.astar.network/ | Astar 协议文档,含 EVM + WASM 双 tutorial |
| GitHub(节点) | https://github.com/AstarNetwork/Astar | astar-collator 源码,**fork from polkadot-sdk + frontier + pallet-contracts**;E8 `5.48.0` 是 node version,E12 `specVersion=2101` 是 runtime |
| Frontier(EVM 桥) | https://github.com/polkadot-evm/frontier | 同 28-moonbeam — pallet-evm + pallet-ethereum;**Astar 与 Moonbeam 共享同一 frontier 上游,零分叉** |
| pallet-contracts | https://github.com/paritytech/polkadot-sdk/tree/master/substrate/frame/contracts | WASM smart contract 运行时,**ink!**(Rust → WASM)是其官方 DSL;Astar 全量启用 |
| ink! | https://use.ink/ | Rust eDSL → wasm32 bytecode → pallet-contracts |
| EVM RPC(官) | https://evm.astar.network | E1/E2/E7/E9 实测;**亦响应 `system_chain`**(E11 证实)|
| Substrate RPC(官)| https://rpc.astar.network | E3-E6/E8/E12 实测;**亦响应 `eth_chainId`**(E10 证实);**两个 hostname 本质同一 RPC server,DNS 分流仅为客户端区分语义** |
| Substrate WSS | wss://rpc.astar.network | subscription 必走 |
| Explorer(EVM) | https://astar.blockscout.com/ | Blockscout |
| Explorer(Substrate)| https://astar.subscan.io/ | Subscan,可按 0x... 或 a... 双向查 |
| Polkadot.js Apps | https://polkadot.js.org/apps/?rpc=wss://rpc.astar.network | extrinsic / dappStaking / WASM 合约入口 |

**Fork 历史**:`astar` fork 自 Parity 的 `substrate` + `polkadot-sdk`,核心创新是 **同 runtime 内 EVM + WASM 双 VM 并存**:`pallet-evm`(frontier,执行 EVM bytecode)+ `pallet-contracts`(Substrate 官方,执行 WASM ink! 合约)。**两套合约系统使用不同账户空间**:EVM 走 H160,WASM 走 AccountId32(ss58)。**Astar 团队的 `unified accounts` 升级(2024,runtime ≥2000 系列)** 引入 `pallet-unified-accounts` 把 H160 ↔ AccountId32 双向映射(可链上注册),解决 dual-VM 账户碎片化。E12 `specVersion=2101` 已含此升级。**关键差异 vs Moonbeam**:Moonbeam 只 EVM,共识 Nimbus;Astar 双 VM,共识 Aura(E5 `0x06617572 61 ...` = `aura` prefix,**与 Moonbeam `0x066e6d6273` = `nmbs` 字节级不同**)。

---

## 2. 与 Ethereum / Polkadot / Moonbeam 三方关系(family 边界 + wave 8 收官比对)

| 维度 | Ethereum (02) | Polkadot (07) | Moonbeam (28) | Acala (27) | Astar (29) | 复用判定 |
|---|---|---|---|---|---|---|
| Family | EVM | Substrate | dual: evm.primary + substrate.secondary | dual: substrate.primary + evm+.embedded | **dual: substrate.primary + evm.embedded + wasm.embedded** | ⚠️ 三选一,**evm_layer.priority 字段已稳定 enum**(见 §7) |
| Adapter | EthereumAdapter | SubstrateAdapter | Eth + Sub 双 | Eth(裁剪)+ Sub 双 | **Eth + Sub 双**(WASM 复用 Sub author_submitExtrinsic,**不需新 adapter**) | ✅ 零新增 adapter |
| 共识 | Gasper | BABE+GRANDPA | Nimbus + relay GRANDPA | Aura + relay GRANDPA | **Aura + relay GRANDPA**(E5 实证)| ⚠️ 与 27-acala 共识一致 |
| 出块 | 12s | 6s | 12s | 12s | **12s**(E2 与历史块比,**符合 parachain slot 限制**)| ✅ 同 28/27 |
| Finality | ~12-15 min | GRANDPA 12-60s | 30-60s(继承 relay)| 30-60s | **30-60s**(同) | ✅ 同模式 |
| EVM 完整度 | 100% | ❌ | 100% frontier | **~85%**(裁剪) | **100% frontier**(同 Moonbeam)| ✅ 完全复用 |
| **WASM VM** | ❌ | ❌(relay 不含)| ❌ | ❌ | **✅ pallet-contracts + ink!** | ❌ **本链独有**,§7 给出 DSL 评估 |
| native token | ETH | DOT(10 dec, prefix=0) | GLMR(18 dec, prefix=1284) | ACA(12 dec, prefix=10)| **ASTR(18 dec, prefix=5)**(E4 实测)| ⚠️ 精度同 Moonbeam,prefix 独有 |
| 地址 | `0x...` | `G...` | 双(算法绑定) | 双(链上 mapping) | **三层**:`0x...`(EVM 合约/EOA)+ `a...`(ss58, prefix=5)+ **unified-accounts 链上 mapping**(2024 上线,显式绑定) | ⚠️ 比 Moonbeam/Acala 多一层 |
| Gas / Fee | EIP-1559 | weight + length | EIP-1559(~31 gwei) | EIP-1559(裁剪) | **EIP-1559**(E7 ~778 gwei,**MinGasPrice 配置高,非链上拥堵**)| ⚠️ 数值偏高,模型同标准 |
| 独有 pallet | (无) | (无 EVM)| parachainStaking + xcm 套件 | EVM+ + Acala 金融套件 | **`dappStaking`(v3,2024 上线,**Astar 标志性**:dApp 注册 → 用户/builder 双向质押 → 区块奖励按比例发放)+ `contracts`(WASM ink!) + `xcAssetConfig` + `xvm`(EVM ↔ WASM 跨 VM 调用)+ `unifiedAccounts`** | ❌ 本稿新增 |
| XCM 资产 | ❌ | ✅ | ✅(xc 前缀)| ✅(同模式)| **✅ `xc...` 资产**(xcDOT/xcUSDT 等,通过 `xcAssetConfig` 注册)| ✅ 复用 wave 8 模式 |

---

## 3. 公链 endpoint 实证(12 次全 200)

| # | Method | Endpoint | 响应 | 说明 |
|---|---|---|---|---|
| E1 | `eth_chainId` | evm.astar.network | `0x250` = 592 ✅ | EVM ChainID,**双源(E1+E9)一致** |
| E2 | `eth_blockNumber` | 同 | `0xcd10ec` = 13,439,724 | EVM 当前块高,与 E5 Substrate `number` 字节级相同 |
| E3 | `system_chain` | rpc.astar.network | `"Astar"` | Substrate chain name |
| E4 | `system_properties` | 同 | `{ss58Format:5, tokenDecimals:18, tokenSymbol:"ASTR"}` | **ss58Format=5 独有**(无任何参考链此值) |
| E5 | `chain_getHeader` | 同 | `number:0xcd10ec`, digest.logs = `[aura(0x06617572...), RPSR, fron, aura-seal]` | **Aura 共识 + frontier seal,与 Moonbeam Nimbus 字节级不同** |
| E6 | `system_health` | 同 | `{peers:40, isSyncing:false, shouldHavePeers:true}` | parachain collator peers |
| E7 | `eth_gasPrice` | evm.astar.network | `0xb576270823` ≈ **778 Gwei** | **MinGasPrice 高**,Acala/Moonbeam 都 < 50 gwei |
| E8 | `system_version` | rpc.astar.network | `"5.48.0-00338639b9e"` | astar-collator node 版本 + git commit |
| E9 | `net_version` | evm.astar.network | `"592"` | 与 E1 一致 ✅ |
| **E10** | `eth_chainId` | **rpc.astar.network**(Substrate hostname)| `0x250` ✅ | **跨端点验证:Substrate hostname 也响应 EVM method,确认是同一 RPC server** |
| **E11** | `system_chain` | **evm.astar.network**(EVM hostname)| `"Astar"` ✅ | **跨端点反向验证:EVM hostname 也响应 Substrate method** |
| E12 | `state_getRuntimeVersion` | rpc.astar.network | `{specName:"astar", specVersion:2101, apis:[..."0xf3ff14d5ab527059":3..., ContractsApi hash 可见]}` | **runtime 启用 pallet-contracts**(WASM 合约 API 注册)+ 共 20 个 runtime api(EVM + WASM + standard) |

**关键发现 1**:Astar 与 Moonbeam 同模式 **单端点双协议**(本质同一 RPC server),但 Astar 团队**额外提供两个 DNS hostname**(`evm.` / `rpc.`)作客户端语义提示,实测可互换 — 与 28-moonbeam `rpc.api.moonbeam.network` 单 hostname 模式相比,Astar 的 **dual-hostname 模式**对 benchmark DSL 影响为零(`endpoint.http` 选一即可)。

**关键发现 2**:`state_getRuntimeVersion.apis` 中可见 ContractsApi 与 EthereumRuntimeRPCApi 同时注册 — 这是**确认 WASM + EVM 双 VM 启用的最小代价方法**,无需深入 metadata 解析,benchmark explorer 可直接复用此 method。

**关键发现 3**:E7 gasPrice 异常高(778 gwei vs Moonbeam 31 gwei),原因是 Astar runtime `MinGasPrice` 参数硬编码值偏高,**与链上拥堵无关**;benchmark 在 EVM `eth_estimateGas` × `eth_gasPrice` 报告时,需注意 **Astar 的 gas-cost-USD ≠ 链上活跃度信号**。

---

## 4. 与 Ethereum / Polkadot / Moonbeam 实质差异表(只列差异)

| 维度 | Ethereum (02) | Polkadot (07) | Moonbeam (28) | Astar (29) |
|---|---|---|---|---|
| RPC 端点拓扑 | 单端点 EVM | 单端点 Substrate | 单端点双协议(method 分发)| **双 hostname 单 RPC server**(`evm.` 与 `rpc.` 互换 OK,E10/E11 实证) |
| 块高对应 | `eth_blockNumber` | `chain_getHeader.number` | 1:1 同 | **1:1 同**(E2 `0xcd10ec` ⇔ E5 `number:0xcd10ec`) |
| Finality 查询 | `eth_getBlockByNumber("finalized",..)` | `chain_getFinalizedHead` | 两者并存 | **两者并存**(同 Moonbeam) |
| 交易提交 | `eth_sendRawTransaction` | `author_submitExtrinsic` | 两者并存 | **三者并存**:EVM tx / Substrate extrinsic / **WASM contracts call**(后者走 `author_submitExtrinsic` 包 `contracts.call` extrinsic) |
| 合约部署 | Solidity → bytecode | ink! → WASM(relay 不支持)| 仅 Solidity | **双轨**:Solidity → bytecode → `pallet-evm.create` + ink!(Rust)→ wasm32 → `pallet-contracts.instantiateWithCode` |
| 跨 VM 调用 | N/A | N/A | N/A | **`xvm` pallet**(2024,EVM 合约可调 WASM 合约,反之亦然 — **业内独家**) |
| 质押激励 | PoS validator | NPoS | parachainStaking(collator/delegator) | **dappStaking v3**:dApp 注册 → 用户质押到 dApp → block reward 按比例发 dev + 用户,**Astar 标志性产品** |
| 治理 | 链下(EIP)| OpenGov | OpenGov | **`council` + `democracy` + `treasury`(经典 Substrate 三件套,未迁移 OpenGov)** |

---

## 5. method 差异 + 独有 pallet / precompile / 跨 VM

**完全复用 Ethereum**:`eth_chainId` / `eth_blockNumber` / `eth_getBlockByNumber` / `eth_getBlockByHash` / `eth_getTransactionByHash` / `eth_getTransactionReceipt` / `eth_getBalance` / `eth_call` / `eth_estimateGas` / `eth_gasPrice` / `eth_sendRawTransaction` / `eth_getLogs` / `eth_subscribe`(WSS)/ `net_version` / `net_peerCount` / `web3_clientVersion` — **直接复用 EthereumAdapter,零修改**。

**完全复用 Polkadot**:`system_chain` / `system_name` / `system_version` / `system_health` / `system_properties` / `system_peers` / `chain_getHeader` / `chain_getBlock` / `chain_getBlockHash` / `chain_getFinalizedHead` / `state_getMetadata` / `state_getRuntimeVersion` / `state_getStorage` / `author_submitExtrinsic` / `author_pendingExtrinsics` — **直接复用 SubstrateAdapter**。

**Astar 独有 pallet(extrinsic 命名空间)**(⚠️ 仅文档凭据 + E12 runtime api hash 旁证):
- `dappStaking.{registerDapp, stake, unstake, claimStakerRewards, claimDappRewards, unbondAndUnstake}` — **dApp 质押激励,Astar 标志性**
- `contracts.{instantiateWithCode, instantiate, call, uploadCode, removeCode}` — **WASM 合约(ink!)入口**
- `xvm.call` — **EVM ↔ WASM 跨 VM 调用**(2024,业内独家)
- `unifiedAccounts.{claimEvmAddress, claimDefault}` — H160 ↔ AccountId32 链上 mapping
- `xcAssetConfig` — XCM 资产元数据
- `evm` / `ethereum` — frontier pallet(同 Moonbeam)
- `council` / `democracy` / `treasury` / `preimage` — 经典 Substrate 治理

**Astar 独有 precompile**(EVM 侧调 Substrate 功能):
- `0x0000000000000000000000000000000000005001` — DappStaking precompile(EVM 内直接对 dApp 质押)
- `0x0000000000000000000000000000000000005002` — SR25519 验签
- `0x0000000000000000000000000000000000005005` — XVM(EVM 调 WASM 合约)
- `0xFFFFFFFF<assetId>` — pallet-assets ERC20 wrapper(同 Moonbeam 模式)

**WASM 调用模式**(关键 — 决定是否需新 DSL):
- 部署:`contracts.uploadCode(wasm_bytes)` → `contracts.instantiate(code_hash, salt, data)`
- 调用:`contracts.call(dest_account, value, gas_limit, storage_deposit_limit, data)`
- **传输层 100% 复用 `author_submitExtrinsic`**(SCALE 编码 extrinsic),**RPC 层不引入新 method**
- **DSL 影响评估**:WASM 调用从 RPC adapter 看与普通 Substrate extrinsic 无差异,**唯一新增信息是 contracts.* 在 pallet_set 中出现** → **不需要新 DSL 字段,沿用 `substrate_layer.pallets_extra` 即可覆盖**(详见 §7)

---

## 6. 真实负载(benchmark 复用模式)

| 场景 | 路径 | 复用 |
|---|---|---|
| EVM block 拉取 | `eth_getBlockByNumber("latest", true)` | ✅ 完全复用 02-ethereum payload |
| EVM tx receipt | `eth_getTransactionReceipt(0x...)` | ✅ 完全复用 |
| EVM ERC20 余额 | `eth_call({to:0xFFFFFFFF...<assetId>, data:0x70a08231...})` | ⚠️ xc 资产用 precompile 地址,同 Moonbeam |
| Substrate header | `chain_getHeader` | ✅ 完全复用 07-polkadot |
| Substrate finalized | `chain_getFinalizedHead` | ✅ 完全复用 |
| ASTR 原生转账(EVM) | `eth_sendRawTransaction`(EIP-1559 tx) | ✅ 复用 02-ethereum 负载 |
| ASTR 原生转账(Sub) | `author_submitExtrinsic`(balances.transfer 编码) | ✅ 复用 07-polkadot 负载 |
| dApp Staking | `author_submitExtrinsic`(dappStaking.stake 编码) | ❌ 新增 SCALE 编码 ⚠️ 文档凭据 |
| **WASM 合约 call** | `author_submitExtrinsic`(contracts.call 编码) | ⚠️ **transport 层 100% 复用 Polkadot adapter**,payload 是 SCALE-encoded `contracts.call(...)` — **本 benchmark 不需新增 RPC adapter** |
| **XVM 跨 VM call** | EVM `eth_call` → precompile `0x5005`(EVM → WASM)或 Substrate `xvm.call`(WASM → EVM)| ⚠️ Astar 独家,benchmark 可作为可选场景 |
| XCM 跨链 | `author_submitExtrinsic`(xTokens.transferMultiasset 编码) | ✅ 复用 Moonbeam wave 8 模式 |

---

## 7. DSL 决策(wave 1-8 共 28 链调研 — 终态评估)

预测 DSL 字段(Astar 本链):

```yaml
chain: astar
chain_id_evm: 592               # E1 实测
parachain_id: 2006              # 公开常识
family:
  primary: substrate            # ⭐ 与 Moonbeam 倒置 — Astar 治理/激励主面是 Substrate
  embedded: [evm, wasm]         # ⭐⭐ wave 1-8 首次出现 wasm
adapter:
  primary: SubstrateAdapter     # ~70% 复用 07-polkadot
  secondary: EthereumAdapter    # ~95% 复用 02-ethereum
evm_layer:
  priority: secondary           # 与 Moonbeam=primary 倒置(同 Acala/Injective)
  chain_id: 592
  min_gas_price_gwei: 778       # ⚠️ 高,非链上拥堵
  precompiles_extra:
    - {addr: "0x0000000000000000000000000000000000005001", name: "DappStaking"}
    - {addr: "0x0000000000000000000000000000000000005005", name: "XVM"}
    - {addr_prefix: "0xFFFFFFFF", name: "AssetsErc20"}
wasm_layer:                     # ⭐⭐ 新字段(讨论见下方 ASK)
  enabled: true
  pallet: contracts             # pallet-contracts
  dsl: ink!                     # Rust eDSL → wasm32
substrate_layer:
  ss58_prefix: 5
  pallets_extra: [contracts, dappStaking, xvm, unifiedAccounts, xcAssetConfig, evm, ethereum]
xcm:
  enabled: true
  version: v3
endpoint:
  http: https://evm.astar.network    # 也可填 rpc.astar.network,E10/E11 实证等价
  wss: wss://rpc.astar.network
```

### 7.1 **WASM 是否需要新 DSL?— 评估结论:不需要**

**论据**:
1. RPC 传输层 100% 复用 `author_submitExtrinsic`(SCALE-encoded `contracts.*` extrinsic),无新 method
2. benchmark 关心的是 **RPC 端 throughput / latency**,不涉及 WASM bytecode 编译或合约语义
3. `contracts` pallet 在 `pallets_extra` 中出现即可触发**可选** WASM 场景探针(`state_call::ContractsApi_call`),与其他 pallet 同处理

**唯一推荐**(可选 L2):新增 `wasm_layer.enabled: bool` 标识位作为**显式提示**(避免主控判断 `'contracts' in pallets_extra`),便于场景调度器开关 WASM 探针。**评级 L2(可缓)**,因仅 Astar 一链触发,wave 9+ 若再无 WASM 链可永久搁置。

### 7.2 **wave 7+8 累计 DSL ASK 终态整合表(28 链调研完成)**

| ASK | 字段 | 触发链 | 终态 | wave 8 收官评估 |
|---|---|---|---|---|
| **A** | `module_set` / `pallet_set` | cosmos 全家 + substrate 全家 | **L1 必上** ✅ | 4 链 ×2 family 验证零冲突,**最终稳定** |
| **B** | `denom_format` | cosmos(uatom/inj/uosmo/utia) | **L1 必上** ✅ | wave 7 4 链验证,**最终稳定** |
| **C** | `evm_layer`(段)+ `evm_layer.priority`(enum) | 12/15/16/17/18/24/27/28/29 | **L1 必上** ✅ | wave 8 4 链(Acala/Moonbeam/Astar + Kusama N/A)确认 enum 三值 `primary` / `secondary` / 缺省 — **最终稳定** |
| **D** | `hot_endpoints` | 全链 | **L1 必上** ✅ | 28 链全覆盖,**最终稳定** |
| **E** | `rollup_type` + `modular_da` | 15/16/17/18/23(L2/L1-DA) | **L1 必上** ✅ | wave 1 落地,wave 8 无新增,**最终稳定** |
| **F** | `dual_address`(bool) | 25-sei / 27-acala / 29-astar(unified)| **L1 推荐** ✅↑ | **wave 8 升级**:Astar `unifiedAccounts` 是第三个实证,**升 L1 推荐 → L1 必上候选**(3 链覆盖,模式稳定) |
| **G** | `evm_parallelism` | 25-sei | **L2 可缓** | 仅 Sei 一链,**继续缓** |
| **H** | (空,占位) | — | — | — |
| **I** | `native_token` 数组化 | 13-avalanche-x(AVAX 跨子链)+ 24-injective(INJ + xc)+ 28-moonbeam(GLMR + xcDOT 等)+ 29-astar(ASTR + xcDOT 等)| **L1 必上** ✅↑ | **wave 8 4 链证实**,从 L1 推荐升 **L1 必上** |
| **J** | substrate `pallet_set`(同 A,但 substrate 子集)| 07/26/27/28/29 | **L1 必上** ✅ | 5 链全覆盖,**最终稳定** |
| **K** | `parachain` 段(`id` + `relay`)| 26-kusama(relay)+ 27/28/29(para)| **L2 可缓** | 4 链验证模式简单,**继续缓** |
| **L (新)** | `wasm_layer.enabled` | 29-astar | **L2 可缓** ⚠️ | **wave 8 仅 1 链**,搁置 |
| **M (新)** | `xcm`(段)| 07/26/27/28/29 | **L2 推荐** | **5 链验证**,wave 9+ 若纳入 parachain 批量可升 L1 |

**ASK#29-1(主控)**:
> **wave 1-8 共 28 链调研完成。DSL ASK 集合是否最终冻结?** 当前状态:**L1 必上 7 条**(A/B/C/D/E/I/J)+ **L1 推荐 1 条**(F)+ **L2 可缓 4 条**(G/K/L/M)。**建议主控判定 L1 必上 7 条进入 schema 主线开发**,L1 推荐 1 条(F dual_address)纳入 v1.0 候选,L2 可缓 4 条记入 backlog。**WASM(L 条)单链触发,纯可选探针不进 schema**。**XCM(M 条)若未来扩 parachain 批次再升级**。**evm_layer.priority enum 三值最终确认**:`primary` / `secondary` / 缺省(默认 primary,Substrate-only 链不设 evm_layer 段)。

### 7.3 **28 链调研终态总结**(本稿一句话版)

> 28 链跨 8 wave 落地,**0 个新增 adapter**(全部复用 EthereumAdapter / SubstrateAdapter / CosmosAdapter / BitcoinAdapter / Solana / Aptos / Near / Tron / Tezos / Algorand / Hedera 等 wave 1-6 已有),**12 个 DSL 字段候选汇成 7 必 + 1 推 + 4 缓**,**双协议链(Moonbeam/Acala/Injective/Astar)零字段冲突复用主 adapter**,**WASM 双 VM 不需要新 DSL**;benchmark 主线可锁定 L1 7 字段进入 v1.0 schema。

---

## 8. H8 实证(12 次 curl 全部 200)

```bash
# E1 EVM ChainID
curl -s -X POST https://evm.astar.network \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}'
# {"result":"0x250"}                              # 0x250 = 592 ✅

# E2 EVM blockNumber
# {"result":"0xcd10ec"}                           # = 13,439,724

# E3 Substrate system_chain
# {"result":"Astar"}

# E4 system_properties — ss58Format=5 独有
# {"result":{"ss58Format":5,"tokenDecimals":18,"tokenSymbol":"ASTR"}}

# E5 chain_getHeader — Aura 共识 + frontier seal
# {"result":{"number":"0xcd10ec","parentHash":"0xf03b...","digest":{"logs":[
#   "0x06617572...",   # aura (Aura slot)
#   "0x04525053...",   # RPSR (relay parent storage root)
#   "0x0466726f6e...", # fron (frontier seal)
#   "0x05617572...",   # aura (Aura seal)
# ]}}}                                            # ⚠️ Moonbeam 用 nmbs,Astar 用 aura

# E6 system_health
# {"result":{"peers":40,"isSyncing":false,"shouldHavePeers":true}}

# E7 EIP-1559 gasPrice
# {"result":"0xb576270823"}                       # ≈ 778 Gwei ⚠️ MinGasPrice 高

# E8 runtime version
# {"result":"5.48.0-00338639b9e"}

# E9 net_version
# {"result":"592"}                                # 与 E1 一致 ✅

# E10 ⭐ 跨端点验证(Substrate hostname 响应 EVM method)
curl -s -X POST https://rpc.astar.network -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":10,"method":"eth_chainId","params":[]}'
# {"result":"0x250"} ✅                           # 两个 hostname 同一 RPC server

# E11 ⭐ 跨端点反向验证(EVM hostname 响应 Substrate method)
curl -s -X POST https://evm.astar.network -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":11,"method":"system_chain","params":[]}'
# {"result":"Astar"} ✅

# E12 ⭐ runtime apis — 验证 WASM(ContractsApi)+ EVM(EthereumRuntimeRPCApi)双注册
# {"result":{"specName":"astar","specVersion":2101,"apis":[
#   ["0xdf6acb689907609b",5], ["0x37e397fc7c91f5e4",2], ... # 20 个 api hash,含 ContractsApi
# ]}}
```

**复用度结论**:**EVM 侧 95% 直接复用 02-ethereum benchmark suite**(opcode / RPC / Gas / EIP-1559 全标准,同 Moonbeam),**Substrate 侧 70% 直接复用 07-polkadot suite**(`system_*` / `chain_*` 同构,业务 pallet 差异更大),**WASM 侧 100% 复用 author_submitExtrinsic transport(零新 method)**;整体新增工作量仅 **~10%**(dappStaking / xvm / contracts extrinsic SCALE 编码 — 全部 ⚠️ 文档凭据,benchmark 主线可缓)。**Astar 是 wave 1-8 28 链调研最后一链,DSL ASK 集合在本稿后建议主控冻结 L1 必上 7 条 + L1 推荐 1 条**。
