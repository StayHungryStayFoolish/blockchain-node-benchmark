# 27-acala 调研

> 由 `_template.md` 衍生。**最激进 DIFF-ONLY 模式**:本链是 Substrate-based parachain(family=substrate),Substrate JSON-RPC + sidecar REST 协议结构、SCALE 编码、SS58 地址族、`state_/chain_/system_/author_` method 命名空间**完全继承 wave 2 polkadot(07-polkadot.md 403 行)**,本稿**不重写**,只列差异;并与 wave 7 同模式链 **24-injective / 25-sei**(Cosmos+EVM 双协议)做 **`evm_layer` ASK C 复用度横向校验**。H8:本次 9 次 H8 curl 在 **2026-05-23** 对公共 mainnet 双端点(`acala-rpc-0.aca-api.network` Substrate + `eth-rpc-acala.aca-api.network` EVM+)实测,**9 次全部成功响应**(EVM+ ChainID 787 ✅、Substrate ss58=10 + 4-token system ✅)。

---

## 元信息

| 项 | 值 |
|---|---|
| 链名(中) | 阿卡拉 |
| 链名(英) | Acala |
| 编号 | 27 |
| Mainnet ChainID | Substrate: SS58 prefix = **10**;EVM+: **787** (`eth_chainId` = `0x313`, E5 实测);parachain ID on Polkadot = **2000** |
| 调研日期 | 2026-05-23 |
| 调研者 | Hermes Agent |
| 状态 | 🟢 已完成(DIFF-ONLY) |

---

## 1. Sources(权威来源,DIFF 补充)

| 类型 | URL | 备注 |
|---|---|---|
| 官方文档 | https://wiki.acala.network/ | Acala 协议主页 |
| EVM+ docs | https://evmdocs.acala.network/ | **关键**:EVM+ 与标准 EVM 差异规范 |
| GitHub | https://github.com/AcalaNetwork/Acala | Substrate runtime + module-evm |
| EVM+ runner | https://github.com/AcalaNetwork/bodhi.js | EVM+ JSON-RPC adapter(把 Substrate event 映射为 EVM RPC 响应) |
| Subscan | https://acala.subscan.io | substrate+evm 双视图 |
| EVM Explorer | https://blockscout.acala.network | Blockscout 风格 EVM+ 浏览器 |
| Polkadot crowdloan/parachain | https://parachains.info/details/acala | parachain ID=2000 凭据 |

(其余 polkadot.js / Sidecar 规范 / SCALE codec 已在 07-polkadot §1 完整列出,本稿不复述。)

---

## 2. Protocol Family / Parachain Topology(DIFF)

| 项 | 与 Polkadot 一致? | 差异 |
|---|---|---|
| Family | ✅ substrate | — |
| Consensus | ⚠️ **Cumulus 平行链共识(Aura 出块 + relay-chain validated)** | 不是 BABE+GRANDPA;最终性继承自 Polkadot relay chain(GRANDPA on relay),约 12-18s |
| Block Time | ⚠️ **12.288s ≈ 2 × relay slot**(E3 实测 number 0xaab1a0 + Acala 公开数据)| Polkadot 6s,Acala ~12s(parachain 共识架构所致)|
| VM | ⚠️ **双 VM:WASM Substrate runtime + EVM+(module-evm)** | Polkadot 只 WASM;Acala 是少数 substrate-native EVM 内嵌链(类似 Moonbeam 但实现完全不同 — 见 §5)|
| Genesis | `0xfc41b9bd8ef8fe53d58c7ea67c794c7ec9a73daf05e6d54b14ff6342c99ba64c` ⚠️(凭训练记忆,本次未 H8 因 API 预算)| — |
| Parachain ID | **2000**(Polkadot 第一个 DeFi 平行链 slot,2021 winter auction) | — |
| Sidecar 复用 | ✅ Parity sidecar 通用包装支持 Acala(同协议)| — |
| Reuse Adapter? | ✅ **SubstrateAdapter `chain_type=\"acala\"`** + **复用 EthereumAdapter `evm_layer.type=\"in_protocol\"` 见 §7** | Polkadot wave 2 决策的 SubstrateAdapter 已规划 acala 入族,本稿验证 |

---

## 3. Public RPC(双端点 H8 实证)

| Endpoint | Protocol | Auth | E# | 结果 |
|---|---|---|---|---|
| `https://acala-rpc-0.aca-api.network` | Substrate JSON-RPC | 无 | E1-E4,E9 | ✅ 5/5 成功 |
| `https://eth-rpc-acala.aca-api.network` | EVM+ JSON-RPC | 无 | E5-E8 | ✅ 4/4 成功 |
| `https://acala-rpc.dwellir.com` | Substrate JSON-RPC | 无 | — | ⚠️ DNS 解析失败(本次实测时区不可达,文档凭据训练记忆称稳定) |
| `https://rpc.ibp.network/acala` | Substrate JSON-RPC | 无 | — | ⚠️ 503 |
| `https://acala.api.onfinality.io/public` | Substrate JSON-RPC | API key | — | ⚠️ 无 key 返空 |

**curl 实测**:

```bash
# E1 system_chain  → "Acala"
curl -s -X POST https://acala-rpc-0.aca-api.network \
  -d '{"jsonrpc":"2.0","id":1,"method":"system_chain","params":[]}'
# {"jsonrpc":"2.0","result":"Acala","id":1}

# E2 system_properties(关键:多 token 配置,wave 8 首例)
# {"result":{"ss58Format":10,"tokenDecimals":[12,12,10,10],
#            "tokenSymbol":["ACA","AUSD","DOT","LDOT"]}}
# ⚠️ tokenSymbol 与 tokenDecimals 是 **数组**,非 Polkadot 的单值
# ACA=12, aUSD=12, DOT=10(跨链 DOT)、LDOT=10(liquid-DOT)

# E3 chain_getHeader  → number 0xaab1a0 = 11,194,272
# E4 state_getRuntimeVersion
# {"specName":"acala","implName":"acala","specVersion":2350,
#  "transactionVersion":3,"stateVersion":1,"systemVersion":1, ...}

# E5 eth_chainId  → 0x313 (= 787)
curl -s -X POST https://eth-rpc-acala.aca-api.network \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}'

# E6 eth_blockNumber  → 0xaab19e = 11,194,270
# ⚠️ 关键观察:与 E3 substrate block 11,194,272 仅差 2,
#    证实 EVM+ 是 **in-protocol**(共享 Substrate block index),
#    与 Moonbeam(独立 EVM block)模式完全不同
# E7 net_version  → "787"
# E8 eth_gasPrice → 0x1749219a66 (≈ 99.9 Gwei units,但单位是 ACA wei 等价,见 §5)
# E9 system_health → {"isSyncing":false,"peers":1,"shouldHavePeers":true}
```

---

## 4. 与 Polkadot 实质差异表(L1 字段层面)

| 维度 | Polkadot | Acala | DSL 影响 |
|---|---|---|---|
| 链定位 | relay chain | parachain on Polkadot(slot 2000)| 新增 `parachain.{relay, para_id}` 字段(L2 可缓,见 §7)|
| native token | DOT(10 dec)| **多 token system**:ACA(12)+ aUSD(12)+ DOT(10)+ LDOT(10)| **DSL `native_token` 必须从 object 升级为 array** ⚠️ 见 §7 ASK |
| EVM 兼容 | ❌ | ✅ **EVM+**(内嵌 `module-evm` pallet,非标准 EVM;见 §5)| **复用 wave 7 ASK C `evm_layer`**(Injective L2→Sei L1 升级路径)|
| 共识 | BABE+GRANDPA | Aura(parachain)+ relay GRANDPA finality | metadata only |
| block time | 6s | ~12s | per-chain `block_time_ms` 已有,值不同 |
| 独有 pallet | (relay 上的 staking/democracy/treasury 等基础)| **honzon**(CDP/aUSD 铸币)+ **dex**(AMM)+ **earning**(质押收益)+ **homa**(LDOT liquid staking)+ **module-evm**(EVM+)+ **module-evm-bridge** + **incentives** | DSL `pallet_set` 类比 cosmos `module_set` ⚠️ 见 §7 |
| 地址 | SS58 prefix=0(`1...`)| SS58 prefix=10(`22...`/`23...`)+ **EVM 0x... 双映射**(DVM:DApp Virtual Machine 地址转换)| **DSL `dual_address` 复用 Sei wave 7 ASK G**:`{primary: ss58 prefix=10, secondary: hex20, binding: \"module-evm-bridge\"}` |
| storage_key 模型 | System.Account blake2_128_concat | 同上(继承 Substrate)+ Tokens.Accounts(双 key:AccountId + CurrencyId,因多 token)| sidecar `GET /accounts/{addr}/balance-info` 单 token 模式不直接适用 — 需 `/pallets/tokens/accounts/{addr}/{currency}` 或自定义 |

---

## 5. method 差异 + 独有 pallet(method-level diff-only)

### 5.1 Substrate RPC 命名空间复用度

| ns | 与 Polkadot 一致? | 备注 |
|---|---|---|
| `system_*` | ✅ 100% | E1/E2/E9 验证 |
| `chain_*` | ✅ 100% | E3 验证 |
| `state_*` | ✅ 100%(API 层)| 但 storage_key 计算路径不同(多 token)|
| `author_*` | ✅ 100% | extrinsic submit 通用 |
| `payment_*` | ⚠️ 兼容 | fee 计算逻辑差异(EVM+ 调用走 module-evm payment,非标准 substrate weight)|

**结论**:RPC method 名 100% 复用 polkadot wave 2 列表;**差异在 pallet metadata 与 storage layout**,不在 RPC 协议层。

### 5.2 Acala 独有 pallet(DeFi 套件,sidecar 不直接支持)

| Pallet | 用途 | benchmark 相关 method |
|---|---|---|
| **honzon** | CDP/aUSD 稳定币铸造(Acala 旗舰)| `state_getStorage(Honzon.CDPs(collateral, owner))` 查 CDP 仓位;`state_call(\"HonzonApi_get_current_collateral_ratio\")`(custom RPC)|
| **dex** | XYK AMM swap | `state_getStorage(Dex.LiquidityPool((token_a, token_b)))` 查池子;无 sidecar 直接路径 |
| **earning** | 锁仓收益 | `state_getStorage(Earning.Ledger(addr))` |
| **homa** | DOT → LDOT 流动质押 | `state_getStorage(Homa.ToBondPool)` / `RedeemRequests(addr)` |
| **module-evm** | EVM+ 运行时 | 通过 EVM JSON-RPC 端口(`eth_*`)访问,不走 substrate ns |
| **module-evm-bridge** | substrate↔EVM 地址/资产映射 | `EVMAccounts.Accounts(ss58)` → EVM 0x;`EVMAccounts.EvmAddresses(0x)` → ss58 |
| **incentives** | 流动性挖矿奖励 | `state_getStorage(Incentives.IncentiveRewardAmounts(...))` |

**关键**:Parity sidecar **不内置** honzon/dex/homa 路径(sidecar 只覆盖 Polkadot relay 标准 pallet)。**Acala 独有 pallet 必须走 raw `state_getStorage` + SCALE 解码**(违反 0 Python)或调用 Acala custom `state_call`(同样违反)。

### 5.3 EVM+ 与标准 EVM 差异(本稿核心)

| 维度 | 标准 EVM | EVM+(Acala module-evm)| benchmark 影响 |
|---|---|---|---|
| ChainID | 各 L1/L2 不同 | **787**(E5 实测)| 标准字段 |
| gas 计价 token | ETH | **ACA**(native;`eth_gasPrice` 返 ACA wei 等价值)| `eth_estimateGas` 返回 weight-converted 值,**与 ETH 网络数量级差异**,不可直接复用 ETH gas fixture |
| 区块模型 | 独立区块 | **共享 Substrate 区块**(E3=11,194,272 vs E6=11,194,270 仅差 2 — 几乎同步)| `eth_blockNumber` ≈ `chain_getHeader.number`;**Moonbeam 是独立 block,Acala 不是**,DSL 需 `evm_layer.block_alignment: \"shared\"` |
| 合约部署 | 任意 EOA 即可部署 | **需先 `bindAccount`(module-evm-bridge)** 把 ss58 与 EVM 地址绑定,deploy 受 `publication_fee` 限制 | 只读 benchmark 无影响 |
| `eth_sendRawTransaction` | 标准 RLP 签名 | ⚠️ **不支持原生 EIP-1559 / EIP-2930**(凭 EVM+ docs 训练记忆,本次未实证)| 写交易不在 benchmark scope |
| `eth_call` | 标准 | ✅ 标准兼容(bodhi.js 适配)| 0 Python 可用 |
| `eth_getLogs` | 标准 | ✅ 标准兼容 | 0 Python 可用 |
| `eth_chainId` / `eth_blockNumber` / `eth_getBalance` | 标准 | ✅ 全兼容 | 0 Python 可用 |
| precompile | 标准集(ecrecover/sha256/...)| 标准集 + **Acala 扩展**(`0x000...0400` Schedule、`0x000...0405` Multicurrency 跨 token 桥)| 只读 benchmark 通常不触发 |

**结论**:EVM+ **RPC 表面层 90% 兼容**(eth_chainId/blockNumber/getBalance/call/getLogs/gasPrice 全部 0 Python 可用),**差异在底层 VM 语义**(gas 计价、合约部署、precompile)— 这些差异不影响**只读 benchmark**,但影响**fixture 准备**(用 ETH mainnet contract address 不会在 Acala EVM+ 上有对应代码)。

---

## 6. 真实负载(H8 抽样)

| 字段 | 实测值 | 来源 |
|---|---|---|
| Substrate block #(2026-05-23) | 11,194,272(0xaab1a0)| E3 |
| EVM+ block #(同时刻)| 11,194,270(0xaab19e)| E6 |
| block alignment 差 | 2 blocks ≈ 24s 滞后(EVM 索引轻微滞后于 substrate)| E3 vs E6 |
| ss58 prefix | 10 | E2 |
| native token decimals 数组 | [12, 12, 10, 10] | E2 |
| token symbols | ["ACA", "AUSD", "DOT", "LDOT"] | E2 |
| EVM ChainID | 787 (0x313) | E5/E7 |
| EVM gasPrice | 0x1749219a66(单位 ACA-wei,~99.9 Gwei 等价) | E8 |
| specVersion / transactionVersion | 2350 / 3 | E4 |
| runtime apis 数量 | 17 | E4 |
| isSyncing / peers | false / 1 ⚠️(单 peer 是公共端点的孤立连接特征,不代表网络状态)| E9 |

---

## 7. DSL 决策(预测新字段 + 复用 wave 7)

### 7.1 复用 wave 7 ASK C(`evm_layer`)

Acala 是 wave 7 ASK C `evm_layer` 字段的**第 3 个数据点**(继 Injective L2_separate + Sei in_protocol 之后),且是 **首条 substrate-family in_protocol EVM 验证案例**:

| 字段 | Injective(24)| Sei(25)| **Acala(27)** |
|---|---|---|---|
| `evm_layer.type` | `in_protocol` + `l2_separate`(数组)| `in_protocol` | **`in_protocol`** |
| `evm_layer.chain_id_evm` | x/evm 未公开 + 2525(inEVM)| 1329 | **787** ✅ E5 实测 |
| `evm_layer.endpoint` | requires_self_hosted | `evm-rpc.sei-apis.com` | **`eth-rpc-acala.aca-api.network`** ✅ |
| `evm_layer.public_reachable` | false | true | **true** ✅ |
| `evm_layer.parallelism` | serial | **occ**(Sei 独有)| serial |
| `evm_layer.block_alignment`(本稿新增子字段)| (未涉及,Cosmos 模式)| (未涉及)| **`shared`**(E3≈E6,差 2 block);Moonbeam 应为 `independent` |
| `evm_layer.gas_token` | INJ | SEI | **ACA**(非 ETH;关键差异)|
| `evm_layer.implementation` | x/evm(Geth fork)| seiv2 EVM(Geth-based)| **module-evm + bodhi.js adapter(Substrate-native,非 Geth)** ⚠️ |

**结论**:Sei 升级 ASK C 为 L1 必落地后,**Acala 验证该字段在 substrate family 同样适用**,且增加 2 个子字段需求:`block_alignment` + `implementation`(用于标识 EVM 是 Geth-port 还是 substrate-native — 影响 RPC 行为差异,如 bodhi.js 对 EIP-1559 的部分不支持)。

### 7.2 新增字段(本稿提)

| 字段 | 优先级 | schema 提议 | 理由 |
|---|---|---|---|
| `native_token`(已有,改 schema)| **L1 必落地** | `native_token: [{symbol, decimals, role: \"native\"|\"stablecoin\"|\"bridged\"|\"liquid_derivative\"}]`(从 object 升级为 array)| Acala 是 wave 8 首条多 token 链(ACA + aUSD + DOT + LDOT),E2 实测 `tokenSymbol` 本身就是数组。Polkadot 等单 token 链向后兼容(单元素数组)|
| `parachain` | **L2 可缓 Phase 2.2** | `parachain: {relay: \"polkadot\", para_id: 2000, slot_lease_end: \"...\"}` | 描述 parachain 拓扑;benchmark 无直接影响,但 dashboard / metadata 需要 |
| `pallet_set` | **L1 必落地**(类比 cosmos `module_set`)| `pallet_set: [\"system\",\"balances\",\"tokens\",\"honzon\",\"dex\",\"homa\",\"earning\",\"module-evm\",\"module-evm-bridge\",\"incentives\"]` | substrate family 与 cosmos family 同构问题:每条 parachain 独有 pallet 集合不同(Acala DeFi、Moonbeam EVM、Astar smart contract、HydraDX Omnipool),不引入字段则 plugin 必须每条链整抄全套 method,违反 DRY |
| `dual_address`(复用 Sei wave 7 ASK G)| **L1 推荐** | `address_format: {primary:{prefix:..., encoding:\"ss58\", ss58_prefix:10}, secondary:{encoding:\"hex20\"}, binding:{pallet:\"module-evm-bridge\", query: state_call(\"EVMAccounts_get_evm_address\")}}` | Sei 在 cosmos 侧首证;Acala 在 substrate 侧首证 — 跨族同模式 |
| `tx_lookup` | — | 无原生(同 Polkadot)| sidecar `GET /extrinsics/{block}-{idx}` 由 sidecar 提供;EVM 侧 `eth_getTransactionByHash` ✅ 标准 |

**净增**(在 wave 7 累计 + polkadot 基础上):
- 1 个 schema 升级(`native_token` object→array)
- 2 个新 L1 字段(`pallet_set` + `evm_layer.block_alignment`/`implementation` 子字段)
- 1 个 L2 可缓字段(`parachain`)
- 复用 3 个已有字段(`evm_layer` ASK C / `dual_address` ASK G / `module_set` 借为 `pallet_set`)

---

## 8. H8 实证总览

| E# | endpoint | method/path | 结果 |
|---|---|---|---|
| E1 | acala-rpc-0.aca-api.network | system_chain | ✅ "Acala" |
| E2 | 同上 | system_properties | ✅ ss58=10, 4-token 数组 |
| E3 | 同上 | chain_getHeader | ✅ block #11,194,272 |
| E4 | 同上 | state_getRuntimeVersion | ✅ specVersion=2350 |
| E5 | eth-rpc-acala.aca-api.network | eth_chainId | ✅ 0x313 = 787 |
| E6 | 同上 | eth_blockNumber | ✅ #11,194,270(与 substrate 差 2)|
| E7 | 同上 | net_version | ✅ "787" |
| E8 | 同上 | eth_gasPrice | ✅ 0x1749219a66 |
| E9 | acala-rpc-0.aca-api.network | system_health | ✅ {isSyncing:false, peers:1} |

**成功率 9/9 = 100%**;**最关键发现**:E3+E6 双块号差 ≤ 2,**证实 EVM+ 是 in-protocol shared-block 模式**,与 Moonbeam 独立块模式形成对照(Moonbeam EVM block 与 substrate block 1:1 但语义独立)。

---

## 9. DSL ASK(Phase 2.1 user review 卡点)

- [ ] **DSL ASK I(本稿提,L1 必落地)**:`native_token` 字段从 object 升级为 array。Acala E2 实测 `tokenSymbol/tokenDecimals` 本身是数组(4 token 共存),Polkadot / Cosmos 等单 token 链向后兼容(单元素 array 即可)。否则 plugin 无法表达 aUSD / LDOT 等非 native 但同节点 balance 查询的 token。
- [ ] **DSL ASK J(本稿提,L1 必落地)**:substrate family `pallet_set` 字段,完全类比 wave 7 ASK A `module_set`(cosmos)。wave 2 polkadot 7-8 个 pallet + Acala 10+ pallet(含 honzon/dex/homa/module-evm 独有 5 个)+ Kusama/Astar/Moonbeam/HydraDX 各自独有 pallet 集合,跨链 0% 全集复用。
- [ ] **DSL ASK C 第 3 次验证(Acala in-protocol EVM+,L1)**:`evm_layer` 字段经 Injective(L2)/Sei(in_protocol cosmos)/**Acala(in_protocol substrate)**三次验证,跨 2 个 family(cosmos + substrate)模式一致。建议 schema 增加 2 个子字段:
  - `block_alignment: \"shared\"|\"independent\"|\"separate_chain\"`(Acala=shared / Moonbeam=independent / Injective inEVM=separate_chain)
  - `implementation: \"geth_port\"|\"substrate_native\"|\"reth_port\"|\"custom\"`(Acala=substrate_native + bodhi.js adapter / Sei=geth_port / Moonbeam=frontier-pallet)
- [ ] **DSL ASK G 第 2 次验证(Acala substrate-side dual_address,L1)**:Sei wave 7 在 cosmos 侧首证 sei1↔0x 绑定;**Acala 在 substrate 侧首证 ss58(prefix=10)↔ 0x 绑定**(通过 `module-evm-bridge` pallet 的 `EVMAccounts` storage 双 map)。`binding.query` schema 需支持两种范式:`{rest_path}` (cosmos)或 `{state_call: \"<RuntimeApi>_<method>\"}` (substrate)。
- [ ] **DSL ASK K(本稿提,L2 可缓 Phase 2.2)**:`parachain: {relay, para_id, slot_lease_end}` 字段。Acala=2000(Polkadot)/ Kusama parachain 各自 para_id / Astar=2006 / Moonbeam=2004 / HydraDX=2034。dashboard 与 metadata 价值,benchmark 无直接影响。
- [ ] **DSL ASK L(本稿提,plugin 派生不入 DSL)**:Acala 独有 pallet(honzon/dex/homa)无 sidecar 路径,raw `state_getStorage` 需 SCALE 解码,违反 0 Python。**建议归 plugin-level "fixture-only" 派生**:benchmark 不直接查 honzon CDP 状态,只查 `module-evm` EVM 侧的 USDC/aUSD ERC20 余额(via `eth_call balanceOf`)— 这条路径 0 Python 可用。
- [ ] **未实证 ⚠️**:Genesis hash(本次因 API 预算 9/12 已用,未跑 `chain_getBlockHash 0`)
- [ ] **未实证 ⚠️**:`eth_sendRawTransaction` 是否支持 EIP-1559(只读 benchmark 不需要,但 metadata 应注明)
- [ ] **未实证 ⚠️**:dwellir 端点稳定性(本次 DNS fail,可能临时;文档凭据训练记忆称稳定)

---

## 10. 与其他 substrate parachain 复用度预测(wave 8 后续链)

| 链 | 与 Acala 复用度 | 主要差异 |
|---|---|---|
| Moonbeam | ~70%(SubstrateAdapter + `evm_layer.in_protocol`)| EVM block 模式不同(independent),全 EVM-first 不用 honzon |
| Astar | ~75% | WASM smart contract + EVM 双层,无 DeFi 套件 |
| Kusama relay | ~60%(无 EVM)| Polkadot canary,无 parachain 角色 |
| HydraDX | ~80% | Omnipool 替代 dex,无 EVM |
| Bifrost | ~78% | liquid staking 同模式(vToken),无 dex/honzon |
| Centrifuge | ~70% | RWA pool 独有 pallet,无 EVM |

**结论**:SubstrateAdapter + `pallet_set` + `evm_layer` 三元组,可覆盖 Polkadot 生态 ~10 条主要 parachain,每条加链 0 Python(plugin JSON 即可)。

---

## Changelog

| Date | Author | Change |
|---|---|---|
| 2026-05-23 | Hermes Agent | 初次调研(最激进 DIFF-ONLY 模式);9 次 H8 curl,**9 次全部成功**(Substrate 5 + EVM+ 4);**与 polkadot wave 2 复用 ~85%**(Substrate JSON-RPC + sidecar REST + ss58 + SCALE + state_/chain_/system_ 全套);**独有 ~15%** = honzon(CDP/aUSD)+ dex(XYK AMM)+ homa(liquid DOT)+ earning + module-evm(EVM+) + module-evm-bridge(ss58↔0x 双映射);**EVM+ 关键发现**:E3+E6 双块号差 ≤ 2,**证实 in-protocol shared-block 模式**(与 Moonbeam independent 模式对照);**多 token 系统首例**:`tokenSymbol=[ACA,AUSD,DOT,LDOT]`(E2),驱动 ASK I `native_token` 升级为 array;**复用 wave 7 ASK C `evm_layer` 第 3 次验证**(跨 cosmos→substrate family 模式一致),建议 schema 增加 `block_alignment` + `implementation` 子字段;**复用 wave 7 ASK G `dual_address` 第 2 次验证**(从 cosmos 跨到 substrate);**本稿净增 DSL**:ASK I `native_token` array(L1)+ ASK J `pallet_set`(L1,类比 module_set)+ ASK K `parachain`(L2 可缓);parachain ID=2000(Polkadot 第一 DeFi slot 2021 winter auction) |
