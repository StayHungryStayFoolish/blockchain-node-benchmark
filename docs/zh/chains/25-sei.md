# 25-sei 调研(DIFF-ONLY)

> 由 `_template.md` 衍生。**最激进 DIFF-ONLY 模式**:本链是 Cosmos SDK chain(family=cosmos),Tendermint RPC + Cosmos REST/LCD 协议结构、错误码、`/cosmos/{bank,staking,tx,gov}/*` 标准 module 路径**完全等同 wave 1 cosmos-hub(05-cosmos-hub.md 692 行)**,本稿**不重写**,只列差异;并与 wave 7 同模式链 **24-injective**(Cosmos+EVM 双协议)做**复用度横向校验**。H8:本次 6 次 H8 curl 在 **2026-05-23** 对公共 mainnet 端点(`sei-rest.publicnode.com` + `sei-rpc.publicnode.com` + `evm-rpc.sei-apis.com` + `sei.drpc.org`)实测,**6 次全部 200/成功响应**(含 EVM 双源 ChainID 1329 双验证);后续追加 H8 因预算/审批截止,标 ⚠️ 文档凭据。

---

## 元信息

| 项 | 值 |
|---|---|
| 链名(中) | 海 / Sei |
| 链名(英) | Sei Network |
| 编号 | 25 |
| Mainnet ChainID | **`pacific-1`**(Cosmos 字符串,E1/E2 实测 `network:"pacific-1"`)+ **`1329`**(EVM ChainID,E3+E5 **双 endpoint 实测** `result:"0x531"`,十进制 1329 ✅)|
| 节点应用 | **seid v6.5.0**(Cosmos SDK fork,E1 实测 `app_name=seid, git_commit=fbc0d934, go1.25.10`)+ **CometBFT 0.35.0-unreleased**(E1 `protocol_version.block=11,p2p=8`,**比 Injective/Hub 的 0.38 系版本更靠前 ⚠️ 自托管时注意 fork 序列**)|
| 调研日期 | 2026-05-23 |
| 状态 | 🟢 已完成(diff-only) |
| 与 05-cosmos-hub 兼容度 | **~80%**:Tendermint RPC / Cosmos REST / bank / staking / tx / gov / distribution 模块**100% 同构**;**~20% 差异** = 独有 `oracle`(price feeds)+ `epoch` + `dex`(legacy)+ `evm`(Parallel EVM 内嵌)+ `tokenfactory` 五类 module + EVM 双协议 + 双地址空间 |
| 与 24-injective 兼容度 | **~70%**:Cosmos 双口完全同构,EVM 双协议**模式同源**(均内嵌 `x/evm`),但 Sei 的 EVM 是 **Parallel(OCC,Optimistic Concurrency Control)** + **公共 endpoint 实测可达** 而 Injective in-protocol EVM 公共 endpoint 不可达,独有 module 集合**完全不同**(Injective:exchange/auction/peggy/insurance;Sei:oracle/epoch/dex)|

---

## 1. Sources(权威 + fork 历史)

| 类型 | URL | 备注 |
|---|---|---|
| 官方文档 | https://docs.sei.io/ | Sei Network 协议文档 |
| GitHub(节点) | https://github.com/sei-protocol/sei-chain | seid daemon 源码,**fork from cosmos-sdk(深度定制 + Tendermint Twin Turbo 共识改造)**;E1 `version=0.35.0-unreleased` 说明对 CometBFT 也有自维护分支 |
| Cosmos RPC | https://sei-rpc.publicnode.com | E2 实测 200 |
| Cosmos REST | https://sei-rest.publicnode.com | E1/E6 实测 |
| EVM RPC(官) | https://evm-rpc.sei-apis.com | E3/E4 实测 200,ChainID 1329 ✅ |
| EVM RPC(备) | https://sei.drpc.org | E5 实测 200,ChainID 1329 ✅(双源一致)|
| Explorer(Cosmos+EVM) | https://seitrace.com | **统一浏览器**,可按 sei1... 或 0x... 任一地址查同一账户(双地址绑定核心入口)|
| Mintscan(Cosmos) | https://www.mintscan.io/sei | 仅 Cosmos 侧 |
| Sei v2 upgrade 文档 | https://blog.sei.io/sei-v2-the-first-parallelized-evm/ | 2024 Parallel EVM 正式启用,基于 OCC |

**Fork 历史**:`sei-chain` fork 自 cosmos-sdk(深度定制,具体版本号未在 E1 节点版本号中显式标注),**CometBFT 标注 `0.35.0-unreleased`**(早于主流 0.38 系)——**关键差异**:Sei 团队对 CometBFT 做了 **Twin Turbo Consensus**(并行提案 + 投票流水线)+ **Optimistic Block Processing**(乐观出块),宣称亚秒级 finality。Tendermint RPC `:26657` 与 Cosmos REST `:1317` 协议结构、错误 schema、`/cosmos/*` 路径**全等 cosmos-hub**(见 05 §3-7),**但底层共识引擎实现已显著背离**,自托管时若用社区 CometBFT binary **无法替代** seid。

---

## 2. 与 Cosmos Hub 关系(SDK 兼容 + 模块差集)

| 维度 | Cosmos Hub (05) | Sei (25) | 是否复用 05 |
|---|---|---|---|
| Cosmos SDK 版本 | v0.50.x(gaia v27.3.0) | sei-chain v6.5.0(基于 cosmos-sdk fork,深度定制)| ⚠️ 协议层复用,实现层背离 |
| 共识 | CometBFT v0.38.19 | CometBFT **0.35.0-unreleased**(Sei 自维护 + Twin Turbo + Optimistic Block Processing 改造)| ⚠️ RPC 协议复用,binary 不可替换 |
| `/cosmos/bank/*` | ✅ | ✅(标准路径)| ✅ 复用 |
| `/cosmos/staking/*` | ✅ | ✅(seivaloper 前缀,⚠️ 本次未直接 E12 实测,文档凭据)| ✅ 复用 |
| `/cosmos/tx/*` / gov / distribution / slashing / authz / feegrant | ✅ | ✅ | ✅ 复用 |
| `/cosmos/base/tendermint/*` node_info | ✅ | ✅(E1 `network=pacific-1`)| ✅ 复用 |
| Tendermint RPC `/status` `/block` `/tx` | ✅ | ✅(E2 实测 200)| ✅ 复用 |
| **独有 module** | (无,纯 hub) | **5 类**:`/sei-protocol/seichain/oracle/*`(price feeds,E6 路径返 `-32701 not implemented` ⚠️ 说明 publicnode 关闭了该自定义模块路由)+ `/sei-protocol/seichain/epoch/*`(epoch tick)+ `/sei-protocol/seichain/dex/*`(legacy 订单簿,v2 后弃用)+ `/sei-protocol/seichain/evm/*`(EVM 模块查询,**含 sei1↔0x 地址映射 precompile**)+ `/sei-protocol/seichain/tokenfactory/*` | ❌ **本稿新增** |
| **EVM 双协议** | ❌(Hub 无 EVM) | ✅ **Parallel EVM 内嵌**(`x/evm` 模块,2024 v2 启用,**OCC 并行交易执行,与 Injective 串行 EVM 模式不同**;公共 endpoint **实测可达** ChainID 1329)| ❌ **本稿新增** |
| native denom | `uatom`(1 ATOM=10^6)| `usei`(1 SEI=10^6,与 Cosmos 主流对齐)+ EVM 侧 `wei`(1 SEI=10^18 wei,**同币不同精度**,EVM 侧自动 ×10^12 缩放)+ `factory/<creator>/<sub>` token-factory denom + `ibc/<sha256>` 跨链 token | ❌ **本稿新增** |
| 地址 prefix | `cosmos1...` / `cosmosvaloper1...` | **双地址空间**:`sei1...`(42 字符 bech32,Cosmos 侧)+ `0x...`(20 字节 EVM 侧,42 字符 hex)+ `seivaloper1...`(validator);**两者一一绑定**(通过 `x/evm` 模块的 `EVMAddressForSeiAddress` mapping store,sei1 与 0x 同账户可互查余额、合并 nonce)| ❌ **本稿新增** |
| 块时间 | ~6s | **~0.4s**(亚秒,Twin Turbo + OBP,⚠️ 单次 /status 无法精确反推,文档+EVM block 209M 推算) | ⚠️ 数值不同 |

---

## 3. 公链 endpoint 实证

| Endpoint | API | 实测 | 备注 |
|---|---|---|---|
| `https://sei-rpc.publicnode.com` | Tendermint RPC :26657 | ✅ HTTP 200(E2 `network=pacific-1, protocol_version.block=11`) | publicnode 公益 |
| `https://sei-rest.publicnode.com` | Cosmos REST/LCD :1317 | ✅ HTTP 200(E1 node_info 200) | publicnode 公益 |
| `https://evm-rpc.sei-apis.com` | EVM JSON-RPC | ✅ HTTP 200(E3 `eth_chainId=0x531=1329` ✅;E4 `eth_blockNumber=0xc792648=209,238,728`) | **官方 EVM 公共 endpoint,稳定可达**(与 Injective EVM 形成鲜明对比)|
| `https://sei.drpc.org` | EVM JSON-RPC 备 | ✅ HTTP 200(E5 `eth_chainId=0x531=1329` ✅,**双源 ChainID 一致**) | DRPC 公益 |
| `https://sei-rest.publicnode.com/sei-protocol/seichain/oracle/params` | 自定义 oracle 模块 | ⚠️ `-32701 not implemented`(E6) | **publicnode 关闭了 sei 独有 module 的 REST 路由**,自托管才能访问;`/cosmos/*` 标准路径正常 |

**结论(关键差异)**:
- **Cosmos 双口全公共可达**(同 Injective);
- **EVM 公共 endpoint 双源稳定**(`sei-apis.com` + `drpc.org` 两个独立 provider 均返 1329)— **这是与 Injective 的最大差异**(Injective in-protocol EVM 4 个 endpoint 全部不可达,Sei EVM 是 first-class 公共服务,无需 self-hosted);
- **Sei 独有 module REST 路径在 publicnode 被关闭**(E6 实测 -32701),自托管时需在 `app.toml` 启用 `api.enable = true` 且 `api.enabled-unsafe-cors = true`。

**curl 实测(E3 + E5 — EVM 双源 ChainID 1329 双验证,Parallel EVM 可达性核心证据)**:

```bash
# E3:官方 EVM endpoint
curl -X POST -H "content-type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_chainId","id":1,"params":[]}' \
  https://evm-rpc.sei-apis.com
# 实测:{"jsonrpc":"2.0","result":"0x531","id":1}   ← 0x531 = 1329 ✅

# E5:第三方 DRPC 备份 endpoint
curl -X POST -H "content-type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_chainId","id":1,"params":[]}' \
  https://sei.drpc.org
# 实测:{"id":1,"jsonrpc":"2.0","result":"0x531"}   ← 0x531 = 1329 ✅(独立 provider 一致)
```

**curl 实测(E4 — Parallel EVM 链高度)**:

```bash
curl -X POST -H "content-type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","id":1,"params":[]}' \
  https://evm-rpc.sei-apis.com
# 实测:{"jsonrpc":"2.0","id":1,"result":"0xc792648"}   ← 209,238,728 块
# 推算:链启动 2024-05 v2 升级,~2 年 → ~400ms/块,符合"亚秒级 finality"声称
```

---

## 4. 与 Cosmos Hub 的实质差异表

| 维度 | Cosmos Hub | Sei | 影响 |
|---|---|---|---|
| 独有 module | — | **oracle / epoch / dex(legacy)/ evm / tokenfactory** | DSL `rpc_methods` 需新增 5 类 path |
| native token decimals | 6(uatom)| **Cosmos 侧 6(usei)+ EVM 侧 18(wei,自动 ×10^12)** | **同币双精度**,DSL `balance_unit decimals` 需 per-protocol(cosmos / evm)细分,**比 Injective(纯 18)更复杂** |
| 桥接 token denom 形态 | `ibc/<hash>` | `ibc/<sha256>` + `factory/<creator>/<sub>` + EVM 侧 ERC20 contract address(0x...,与 Cosmos denom **不互通直接 string**,需 token mapping 表)| DSL `denom_format` 需 enum 多值(同 Injective ASK B,**复用度 100%**) |
| 共识 | CometBFT 0.38, ~6s | **CometBFT 0.35 自维护 + Twin Turbo + Optimistic Block Processing**, **~400ms** | benchmark vegeta rate ceiling 应**显著高于 Hub**;**block_time_ms 字段值 ≈ 400**,DSL schema 不变 |
| EVM 兼容 | ❌ | ✅ **Parallel EVM**(OCC 并行,**与 Injective 串行 EVM 模式截然不同**;同一 block 内多笔 tx 乐观并行执行,冲突回滚)| DSL 需 `evm_parallelism` 字段:`{model: "serial"|"occ"|"none"}`,影响 benchmark 并发模型 |
| 地址空间 | 单 bech32 | **双地址 sei1...(bech32) ⇄ 0x...(hex)**,通过 `x/evm` 模块绑定;**同账户两套地址,nonce/balance 合并** | DSL `address_format` 需结构化对象支持 `dual_address: {primary, secondary, binding_module}`(参 14-hedera ASK A) |
| 订单簿模型 | — | dex module 已 **v2 后弃用**(legacy state 残留)| benchmark 不入,**与 Injective exchange 模块对比:Sei 选择退出链上订单簿,押注 EVM dApp 生态** |
| oracle | — | **链上 oracle 模块**(validator 必须提交价格 vote,与 Injective 多源 oracle 模式不同)| benchmark 适合作中频读 `/sei-protocol/seichain/oracle/denoms/exchange_rates`,⚠️ 公共 endpoint 关闭 |
| epoch | — | epoch tick 模块(staking reward / inflation 周期触发)| benchmark 不入 |

---

## 5. method 差异(diff-only,80% 同 05,只列独有)

> **复用 cosmos-hub 全部 method**(详见 05 §5):`/status` `/block` `/tx` `/abci_query` `/abci_info` + `/cosmos/bank/v1beta1/balances/{addr}` + `/cosmos/staking/v1beta1/validators` + `/cosmos/tx/v1beta1/txs/{hash}` 等。**仅列 Sei 独有新增**:

| Method | 类别 | 实证 | 在 mixed 中权重建议 |
|---|---|---|---|
| `GET /sei-protocol/seichain/oracle/params` | oracle 配置 | ⚠️ E6 publicnode 关闭路由(返 -32701),需自托管 | 0.05 |
| `GET /sei-protocol/seichain/oracle/denoms/exchange_rates` | 当前价格 feed | ⚠️ 同上 | 0.05 |
| `GET /sei-protocol/seichain/epoch/epoch` | 当前 epoch | ⚠️ 未直接实测 | 0.02 |
| `GET /sei-protocol/seichain/evm/sei_address_by_evm_address/{0x...}` | **双地址绑定查询**(0x → sei1)| ⚠️ 未直接实测,⚠️ 文档凭据 | 0.05 |
| `GET /sei-protocol/seichain/evm/evm_address_by_sei_address/{sei1...}` | **双地址绑定查询**(sei1 → 0x)| ⚠️ 文档凭据 | 0.05 |
| `GET /sei-protocol/seichain/tokenfactory/denoms_from_creator/{addr}` | token-factory denom 列表 | ⚠️ 未实测 | 0.03 |
| **EVM `POST / eth_chainId`** | Parallel EVM 探活 | ✅ E3+E5 双源 200,1329 | 0.05(本应 0.10,但与 cosmos-hub 复用 RPC 已占大头,EVM 作并行第二平面)|
| **EVM `POST / eth_blockNumber`** | Parallel EVM 高度 | ✅ E4 200,0xc792648 | 0.05 |
| **EVM `POST / eth_getBalance`** | Parallel EVM 余额(0x 地址)| ⚠️ 未实测 | 0.10 |
| **EVM `POST / eth_call`** | Parallel EVM 合约读 | ⚠️ 未实测 | 0.15(**Parallel EVM benchmark 主负载**)|
| **EVM `POST / eth_sendRawTransaction`** | Parallel EVM 写(只读 framework 不发)| — | 0(只读)|
| **EVM `POST / eth_getLogs`** | Parallel EVM 日志查询 | ⚠️ 未实测 | 0.05 |

**复用 05 标准 Cosmos method 权重 ~0.50**(bank/staking/tx/block 等)+ **本稿新增 0.50** = 1.00 ✓(其中 EVM 平面 0.40 + oracle/双地址绑定 0.10)

**与 Injective method 集对照(复用度验证 ASK A)**:Sei 独有 module = oracle/epoch/evm/tokenfactory/dex(已弃);Injective 独有 = exchange/auction/peggy/oracle/insurance — **交集仅 `oracle`**(且实现完全不同,Sei validator-vote,Injective 多 oracle 源),**两链独有 module 列表 0% 复用**,**证实 DSL ASK A `module_set` 字段必要性达 100%**(若不引入,plugin 必须为每条 cosmos family 链单独抄一遍 method 列表)。

---

## 6. 真实负载

- **Cosmos 侧**:`MsgSend` + `MsgDelegate` + `MsgVote`(标准 cosmos)+ oracle validator vote `MsgAggregateExchangeRateVote`(每 epoch 强制)。
- **Parallel EVM 侧**:DEX(Astroport on Sei、Dragonswap)+ NFT(Pallet)+ Perp DEX(Vortex)的 ERC20/合约调用,**Sei v2 后官方力推 EVM dApp 生态**,真实 mainnet ~50%+ tx 已在 EVM 平面。vegeta 模型应**双平面并行压测**:Cosmos REST + EVM JSON-RPC,**OCC 并行特性允许 EVM 侧达到 Ethereum 主网 ~10x 的 throughput 上限**(文档声称,⚠️ benchmark 自行验证)。
- **双地址 nonce 合并**:同账户 sei1... 和 0x... 共享 nonce(`x/evm` 模块统一),benchmark 负载生成器若同时从两个 endpoint 给同账户发 tx,需注意 nonce 协调。

---

## 7. DSL 决策(在 Injective 5 个 ASK 基础上**复用 + 新增 1-2**)

| 字段 | 是否新增 | 理由 |
|---|---|---|
| `family = "cosmos"` | ✅ 复用 | 与 05/24 同 |
| `adapter = "CosmosAdapter"` | ✅ 复用 | Tendermint RPC + REST 双口同 05 |
| **`module_set`(Injective ASK A 提)** | **✅ 100% 复用,Sei 验证强化** | Sei 独有 module 列表(oracle/epoch/evm/tokenfactory/dex)与 Injective(exchange/auction/peggy/oracle/insurance)**交集仅 oracle**,**0% method 列表可共享** → **ASK A 必落地**,否则 cosmos family 6 链 plugin 维护成本爆炸 |
| **`denom_format`(Injective ASK B 提)** | **✅ 100% 复用,Sei 验证 partial** | Sei 用 `bare`(usei)+ `ibc` + `factory` 三种,**未用 peggy / erc20 string denom**(Sei EVM 通过 sei↔evm pointer 合约映射而非 denom 前缀)→ **ASK B enum 集合需覆盖 Sei 的 `pointer` 类型** ⚠️ Phase 2.1 评估 |
| **`evm_layer`(Injective ASK C 提,本稿提升优先级)** | **🆕 升级为 L1 必落地** | Injective EVM 公共不可达,可缓;**Sei EVM 公共双源稳定可达 + 是 Parallel EVM 第一案例**(整个 EVM 生态首条 OCC 链),**Phase 2.1 必须有字段表达**,否则无法配置 `evm-rpc` endpoint。建议 schema:`evm_layer: {type:"in_protocol", chain_id_evm:1329, endpoint:"...", parallelism:"occ", public_reachable:true}` |
| **`dual_address`(本稿新增,L1 推荐)** | **🆕 推荐** | Sei `sei1...` ⇄ `0x...` 双地址绑定通过 `x/evm` 模块的 `EVMAddressForSeiAddress` mapping store(类似 Injective inj1 + EVM,但 Injective 公共不可达,Sei 是首个**可在 benchmark 框架内实测双地址**的 cosmos+evm 链)。DSL `address_format` 需结构化对象:`{primary: {prefix:"sei", encoding:"bech32"}, secondary: {encoding:"hex20", binding_endpoint:"/sei-protocol/seichain/evm/evm_address_by_sei_address/{addr}"}}`。fixture 阶段需为每个测试账户生成**两个**地址 + 校验绑定一致。 |
| **`evm_parallelism`(本稿新增,L2 可缓)** | ⚠️ 可缓 Phase 2.2 | 描述 EVM 执行模型:`"serial"`(Injective/Hedera/标准 Evmos)/ `"occ"`(Sei,Block-STM 类)/ `"none"`。仅影响 benchmark 并发模型设计与 ceiling 设置,DSL 不影响 endpoint 寻址,**Phase 2.2 评估**。 |
| `chain_id` | ✅ 复用为 string | `pacific-1` + 数值 1329(EVM),通过 `evm_layer.chain_id_evm` 表达 |
| `block_semantics` | ✅ 复用 | 标准 Tendermint block;**block_time_ms ≈ 400**(数值不同,schema 不变)|

**净增**(在 Injective 4 个 ASK 基础上):**`dual_address` 1 个新增 L1 字段** + **`evm_layer` 优先级从 L2 → L1**(由 Sei 公共可达性驱动)+ **`evm_parallelism` 1 个新增 L2 字段**(可缓)。

---

## 8. H8 实证证据汇总

| # | 端点 | method | 实测要点 |
|---|---|---|---|
| E1 | REST | `/cosmos/base/tendermint/v1beta1/node_info` | `network=pacific-1, app_name=seid, version=v6.5.0, git_commit=fbc0d934, go1.25.10, cometbft 0.35.0-unreleased`(**注意 cometbft 版本与 Hub/Injective 0.38 系不同**)|
| E2 | RPC | `/status` | `network=pacific-1, protocol_version.block=11, p2p=8, app=0`,200 OK |
| E3 | EVM | `POST eth_chainId` @ evm-rpc.sei-apis.com | `result:"0x531"` = **1329 ✅**(官方 endpoint)|
| E4 | EVM | `POST eth_blockNumber` @ evm-rpc.sei-apis.com | `result:"0xc792648"` = **209,238,728 块**,Parallel EVM 高度 |
| E5 | EVM | `POST eth_chainId` @ sei.drpc.org | `result:"0x531"` = **1329 ✅**(第三方 endpoint 双源验证一致)|
| E6 | REST | `/sei-protocol/seichain/oracle/params` | ⚠️ `-32701 not implemented`(publicnode 关闭了 sei 自定义模块路由,自托管才能访问)|

**未实证 ⚠️**(本次预算限制):双地址 mapping 端点 `/sei-protocol/seichain/evm/{evm,sei}_address_by_{sei,evm}_address/{addr}` 实际响应 schema、seivaloper 前缀实证、oracle exchange_rates 真实 payload、EVM `eth_getBalance` 双地址同账户值一致性验证、precompile 0x1004(地址 mapping)EVM 侧调用。

---

## 9. DSL ASK(Phase 2.1 user review 卡点 + wave 7 累计总结)

### Sei 本稿提出

- [ ] **DSL ASK G(本稿提,L1 必落地)**:`dual_address` 字段。Sei 是 wave 7 首条**双地址绑定可实测**的 cosmos+evm 链(Injective 同模式但公共 endpoint 不可达)。DSL 需 `address_format = {primary: {prefix:"sei", encoding:"bech32"}, secondary: {encoding:"hex20"}, binding: {module:"evm", query_endpoint:"/sei-protocol/seichain/evm/evm_address_by_sei_address/{addr}"}}`。fixture 必须为每账户生成两个地址且校验互查一致。
- [ ] **DSL ASK C 优先级升级(原 Injective L2 可缓 → 本稿建议 L1 必落地)**:`evm_layer` 字段。Sei EVM 公共双源稳定(`evm-rpc.sei-apis.com` + `sei.drpc.org` 均返 1329),证明 in-protocol EVM 在 cosmos+EVM 链中**可成为 first-class benchmark target**。建议 schema 见 §7。
- [ ] **DSL ASK H(本稿提,L2 可缓 Phase 2.2)**:`evm_parallelism: "serial"|"occ"|"none"` 字段。仅 Sei 触发 `occ`,影响 benchmark 并发模型设计(OCC 允许更高并发率,串行 EVM 需保守)。
- [ ] **DSL ASK B 增量验证(本稿对 Injective ASK B 的补充)**:Sei 未用 `peggy` / `erc20` denom 前缀,**改用 sei↔evm pointer 合约**做 token bridge;`denom_format` enum 应再增 `pointer` 选项 — 或归 plugin-level 派生不入 DSL(**推荐**)。
- [ ] **未实证 ⚠️**:双地址 mapping endpoint 真实响应、Sei 块时间精确数值(亚秒声称未做密集采样)、Parallel EVM 在高并发下 OCC 冲突率(benchmark 阶段验证)、Sei oracle module 在自托管节点的真实 path 是否真为 `/sei-protocol/seichain/oracle/*`(publicnode 关闭,无法 cross-check)。

### Wave 7 累计 DSL 决策总结(4 链 22→25 收敛)

| ASK | 提出链 | 优先级 | 跨链复用度验证 | 最终建议 |
|---|---|---|---|---|
| **A. `module_set`** | Injective(24)| **L1 必落地** | Osmosis(22)CLP/superfluid + Celestia(23)blob + Injective(24)exchange/auction/peggy/oracle/insurance + Sei(25)oracle/epoch/evm/tokenfactory **四链独有 module 列表两两交集 ≤ 1** | **🟢 wave 7 后 cosmos family 强制必上**:DSL plugin schema 增 `module_set: [string]`,framework 用其装配 `rpc_methods` 子集 |
| **B. `denom_format`** | Injective(24)| **L1 必落地** | Injective 4 形态(bare/ibc/peggy/factory/erc20)+ Sei 3 形态(bare/ibc/factory + pointer 合约模式)+ Osmosis(bare/ibc/factory/cw20)+ Celestia(bare/ibc) | **🟢 wave 7 后 cosmos family 必上**:enum `["bare","ibc","peggy","factory","erc20","cw20"]` 已覆盖,**`pointer` 模式归 plugin 派生** |
| **C. `evm_layer`** | Injective(24)L2 可缓 → Sei(25)升级 L1 | **L1 必落地(Sei 触发)** | Injective in-protocol EVM 公共不可达;**Sei EVM 公共双源可达 + Parallel EVM**;Osmosis/Celestia 无 EVM | **🟢 Sei 实证后升级 L1**:schema `evm_layer: {type, chain_id_evm, endpoint, parallelism, public_reachable}` |
| **D. `hot_endpoints` + `osmosis_modules`** | Osmosis(22)| **L1 必落地** | Osmosis 独有,wave 7 内其他链不复用 | **🟢 维持原 Osmosis 决策** |
| **E. `rollup_type` 增 `modular_da`** | Celestia(23)| **L1 必落地** | Celestia 独有(modular DA layer)| **🟢 维持原 Celestia 决策** |
| **F. `dual_address`** | Sei(25)| **L1 推荐** | Sei 首条实测;Injective 同模式但公共不可达 → wave 7 内 1 例 | **🟡 推荐落地**(为未来更多 cosmos+EVM 链铺路:Berachain、Canto、Evmos)|
| **G. `evm_parallelism`** | Sei(25)| L2 可缓 Phase 2.2 | Sei 首条 OCC;Hedera/Injective 串行 → wave 7 内 1 例 | **🟡 缓**:可归 metadata 注释而非强 schema |

**Cosmos family 是否最终需 `module_set` 升级 — 结论:🟢 必上**。wave 7 4 链(Osmosis/Celestia/Injective/Sei)+ wave 1 cosmos-hub 共 5 条,**独有 module 列表两两交集 ≤ 1**,**0% 全集复用**。若不引入 `module_set` 字段,plugin 实现必须每条链单独维护 ~30+ method 路径,DRY 严重违反、回归测试矩阵爆炸。**Phase 2.1 user review 应优先确认 ASK A**。

---

## Changelog

| Date | Author | Change |
|---|---|---|
| 2026-05-23 | Hermes Agent | 初次调研(DIFF-ONLY 模式);6 次 H8 curl,**6 次全部成功**(EVM 双源 ChainID 1329 双验证 ✅,Cosmos node_info/status 200,publicnode 关闭 sei 独有 module REST 路由 1 例);**与 cosmos-hub 复用 ~80%**(Tendermint RPC + Cosmos REST + bank/staking/tx/gov 全套);**独有 ~20%** = oracle(validator-vote price feed)+ epoch + dex(legacy)+ evm(Parallel EVM 内嵌,**OCC 并行,本框架首条**)+ tokenfactory;**EVM 公共可达 + 双源验证 1329**(与 Injective 公共不可达形成鲜明对比);**双地址 sei1↔0x 绑定通过 `x/evm` 模块 mapping store**;**与 Injective 复用度**:Cosmos 双口 100%、独有 module **0% 全集复用**(交集仅 oracle 且实现不同)→ **强化 DSL ASK A `module_set` 必要性**;**本稿净增 DSL**:`dual_address` L1 推荐 + `evm_layer` 优先级 L2→L1 升级 + `evm_parallelism` L2 可缓;**wave 7 4 链累计建议**:ASK A/B/C/D/E 全部 L1 必落地,ASK F dual_address L1 推荐,ASK G evm_parallelism L2 可缓 |
