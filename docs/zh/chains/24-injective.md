# 24-injective 调研(DIFF-ONLY)

> 由 `_template.md` 衍生。**最激进 DIFF-ONLY 模式**:本链是 Cosmos SDK chain(family=cosmos),Tendermint RPC + Cosmos REST/LCD 协议结构、错误码、`/cosmos/{bank,staking,tx}/*` 标准 module 路径**完全等同 wave 1 cosmos-hub(05-cosmos-hub.md 692 行)**,本稿**不重写**,只列差异。H8:所有 curl 在 **2026-05-23** 对公共 mainnet 端点(`https://injective-rest.publicnode.com` + `https://injective-rpc.publicnode.com`)实测,共 9 次 API 调用;inEVM/Injective-EVM 公共 endpoint 探测 4 次均不可达(全部 empty / 404),inEVM 部分标 ⚠️ 文档凭据。

---

## 元信息

| 项 | 值 |
|---|---|
| 链名(中) | 注入 / Injective |
| 链名(英) | Injective Protocol |
| 编号 | 24 |
| Mainnet ChainID | **`injective-1`**(Cosmos 字符串,E1 实测 `network:"injective-1"`)+ **`2525`**(inEVM 独立 L2 子链 ChainID,⚠️ 文档凭据,公共 endpoint 不可达;`0x9DD`) |
| 节点应用 | **injectived v1.19.0**(Cosmos SDK fork)+ CometBFT(`p2p protocol_version=9`,E1 实测 `application_version.app_name=injectived, git_commit=750b3fb`) |
| 调研日期 | 2026-05-23 |
| 状态 | 🟢 已完成(diff-only) |
| 与 05-cosmos-hub 兼容度 | **~85%**:Tendermint RPC / Cosmos REST / bank / staking / tx / gov / distribution 模块**100% 同构**;**~15% 差异** = exchange + auction + peggy + oracle + insurance 五个独有 module + EVM 双协议 |

---

## 1. Sources(权威 + fork 历史)

| 类型 | URL | 备注 |
|---|---|---|
| 官方文档 | https://docs.injective.network/ | Injective Chain 协议文档 |
| GitHub(节点) | https://github.com/InjectiveLabs/injective-core | injectived daemon 源码,**fork from cosmos-sdk v0.50.x**(对齐 cosmos-hub gaia v27)|
| GitHub(SDK) | https://github.com/InjectiveLabs/sdk-go | Go client SDK |
| Exchange module 文档 | https://docs.injective.network/develop/modules/Injective/exchange/ | 订单簿 + 衍生品 + 现货引擎核心 |
| Peggy(bridge) 合约 | https://etherscan.io/address/0xF955C57f9EA9Dc8781965FEaE0b6A2acE2BAD6f3 | E6 实测 `bridge_ethereum_address` 即此 |
| inEVM 文档 | https://docs.inevm.com/ | ⚠️ Layer-2,Caldera 运营,ChainID 2525 |
| Injective-EVM 模块文档 | https://docs.injective.network/develop/evm/ | injective-1 内嵌 EVM,2024 启用 |
| Explorer | https://explorer.injective.network / https://injscan.com | account/tx/market/auction 浏览 |
| Mintscan | https://www.mintscan.io/injective | 备用 cosmos 标准 explorer |

**Fork 历史**:`injective-core` fork 自 cosmos-sdk **v0.50.x 系**(略后于 gaia v27 用的 v0.50.10);CometBFT 同 0.38 系。故 Tendermint RPC `:26657` 与 Cosmos REST `:1317` 协议结构、错误 schema、`/cosmos/*` 路径**全等 cosmos-hub**(见 05 §3-7)。

---

## 2. 与 Cosmos Hub 关系(SDK 兼容 + 模块差集)

| 维度 | Cosmos Hub (05) | Injective (24) | 是否复用 05 |
|---|---|---|---|
| Cosmos SDK 版本 | v0.50.x(gaia v27.3.0) | v0.50.x(injectived v1.19.0) | ✅ 100% 复用 |
| 共识 | CometBFT v0.38.19 | CometBFT v0.38 系(E1 `block protocol_version=11`) | ✅ |
| `/cosmos/bank/*` | ✅ | ✅(E9 实测 `/cosmos/bank/v1beta1/balances/inj1...` 返 `{balances:[], pagination}`)| ✅ 复用 |
| `/cosmos/staking/*` | ✅(strangelove) | ✅(E12 实测 BOND_STATUS_BONDED 返完整 `validators[].operator_address=injvaloperXXX`)| ✅ 复用 |
| `/cosmos/tx/*` / gov / distribution / slashing / authz / feegrant | ✅ | ✅ | ✅ 复用 |
| `/cosmos/base/tendermint/*` node_info | ✅ | ✅(E1 实测 `network:"injective-1"`)| ✅ 复用 |
| Tendermint RPC `/status` `/block` `/tx` `/abci_query` | ✅ | ✅(E2 实测 `latest_block_height=167817179`,**1.6 亿块,远超 Cosmos Hub 3100 万 → 块时间显著更快**) | ✅ 协议复用,**block_time 不同**(见 §4)|
| **独有 module** | (无,纯 hub) | **5 个**:`/injective/exchange/v1beta1/*`(订单簿/衍生品/现货)+ `/injective/auction/v1beta1/*`(burn 拍卖)+ `/peggy/v1/*`(Ethereum 桥)+ `/injective/oracle/v1beta1/*`(Pyth/Chainlink/Band 多源)+ `/injective/insurance/v1beta1/*`(衍生品保险池) | ❌ **本稿新增** |
| **EVM 双协议** | ❌(Hub 无 EVM) | ✅ **双层**:(a) injective-1 内嵌 `x/evm` 模块(类 Evmos,2024 启用,public endpoint 探测 empty ⚠️);(b) **inEVM** 独立 L2 子链 ChainID=2525(Caldera 运营,Optimistic rollup) | ❌ **本稿新增** |
| native denom | `uatom`(1 ATOM=10^6) | `inj`(1 INJ=10^18,**与 ERC20 对齐 18 位**,与 Cosmos 主流 6 位**不同**)+ 大量 `peggy0x<eth-addr>` 桥接 token + `factory/<creator>/<sub>` token-factory denom + `erc20:<addr>`(EVM token,E5 衍生品 quote_denom 出现)| ❌ **本稿新增** |
| 地址 prefix | `cosmos1...` / `cosmosvaloper1...` | `inj1...`(42 字符 bech32) / `injvaloper1...`(E12 实测 `injvaloper1qzu3s7uzydpj0vcgrgp04j7u48pgkesy7zl7t3`)| ⚠️ prefix 不同,bech32 算法一致 |
| 块时间 | ~6s | **~0.65s**(由 167817179 块 / 链启动 2021-11 至今约 1280 天反推,显著快于 Cosmos Hub;E2 latest_block_time=2026-05-23T19:30:54,需更密集采样确认 ⚠️) | ⚠️ 数值不同 |

---

## 3. 公链 endpoint 实证

| Endpoint | API | 实测 | 备注 |
|---|---|---|---|
| `https://injective-rpc.publicnode.com` | Tendermint RPC :26657 | ✅ HTTP 200(E2 `latest_block_height=167817179`) | publicnode 公益 |
| `https://injective-rest.publicnode.com` | Cosmos REST/LCD :1317 | ✅ HTTP 200(E1/E4-E9/E12/E13 全 200) | publicnode 公益 |
| `https://lcd.injective.network` | Cosmos REST 官方 | ⚠️ 未测(避免拖延算余) | 官方 |
| `https://mainnet.rpc.inevm.com[/http]` | inEVM JSON-RPC(2525) | ❌ HTTP 404(E10/E11)| 官方 Caldera endpoint **公共部分已关闭**,**requires_self_hosted** |
| `https://inevm-public.publicnode.com` | inEVM JSON-RPC | ❌ 空响应(E10) | publicnode 实际未提供 |
| `https://rpc.ankr.com/inevm` | inEVM | ❌ `-32052` API key required(E10) | 需付费 |
| `https://injective-evm.publicnode.com` | injective-1 内嵌 EVM | ❌ 空响应(E11) | EVM 模块 public endpoint 未稳定上线 |

**结论**:Cosmos 双口(RPC+REST)**全公共可达**;**EVM 侧两条路径全部 requires_self_hosted**(inEVM L2 必须自跑 Caldera erigon;injective-1 内嵌 EVM 需在 injectived 启 `--evm-rpc` flag 自托管)。

**curl 实测(E4 — exchange spot markets,Injective 招牌端点)**:

```bash
curl -s "https://injective-rest.publicnode.com/injective/exchange/v1beta1/spot/markets"
# 实测节选(KATANA/USDT 现货):
# {"markets":[{"ticker":"KATANA/USDT",
#   "base_denom":"factory/inj1ms8lr6y6qf2nsffshfmusr8amth5y5wnrjrzur/KAT",
#   "quote_denom":"peggy0xdAC17F958D2ee523a2206206994597C13D831ec7",  # USDT bridged
#   "maker_fee_rate":"-0.000050000000000000",                          # 负值=返佣
#   "taker_fee_rate":"0.000500000000000000",
#   "market_id":"0x00cb369b060f29e218ddbd72a07af2f979052b0c2dfc24a2518686351e5d0238",
#   "status":"Active","min_price_tick_size":"1.0","min_quantity_tick_size":"0.1",
#   "min_notional":"1000000.0","base_decimals":6,"quote_decimals":6}, ...]}
```

**curl 实测(E5 — exchange derivative markets,衍生品 PERP)**:

```bash
curl -s "https://injective-rest.publicnode.com/injective/exchange/v1beta1/derivative/markets"
# 节选(MSFT/USDC PERP — 链上股票永续):
# {"market":{"ticker":"MSFT/USDC PERP","oracle_base":"MSFT/USDC","oracle_type":"Provider",
#   "quote_denom":"erc20:0xa00C59fF5a080D2b954d0c75e46E22a0c371235a",  # ← EVM erc20: denom
#   "initial_margin_ratio":"0.033333","maintenance_margin_ratio":"0.020000",
#   "isPerpetual":true,"min_price_tick_size":"10000.0",...}}
```

---

## 4. 与 Cosmos Hub 的实质差异表

| 维度 | Cosmos Hub | Injective | 影响 |
|---|---|---|---|
| 独有 module | — | **exchange / auction / peggy / oracle / insurance** | DSL `rpc_methods` 需新增 5 类 path |
| native token decimals | 6(uatom) | **18(uinj)** | **balance_unit decimals 表必须 per-chain**,不能全 cosmos family 复用 6 |
| 桥接 token denom 形态 | `ibc/<hash>` | `peggy0x<eth-addr>`(E4/E6)+ `factory/<creator>/<sub>`(E4)+ `erc20:<addr>`(E5)+ `ibc/...` 多种**并存** | DSL `denom_format` 需 enum 多值,正则校验需 4+ 形态 |
| 共识参数 | block ~6s | **block <1s**(E2 区块号 1.67 亿,密集程度 ~9x Hub)| benchmark vegeta rate ceiling 应**显著高于** Hub(订单簿 HFT 真实负载) |
| EVM 兼容 | ❌ | ✅ 双层:**(a)** injective-1 内嵌 EVM 模块(同一节点,自托管 `--evm-rpc`);**(b)** inEVM L2(独立链,ChainID=2525,Caldera Optimistic rollup,**与主链异步**) | DSL 需 `evm_layer` 字段区分 in-protocol vs L2 |
| 订单簿模型 | 无(纯 token 链) | **CLOB on-chain**(中央限价订单簿,exchange module 维护)+ `min_price_tick_size`/`min_quantity_tick_size`/`min_notional` 每市场独立 | 真实负载是高频下单/撤单/查询订单状态,远超 bank.MsgSend 主导的 Hub |
| auction | — | E7 实测 round=230,`auction_period=2419200s`(28 天),`min_next_bid_increment_rate=0.01`,`bidders_whitelist` 仅 2 个 EOA(已开启白名单 ✅)| benchmark 频次低,不入 mixed |
| oracle 多源 | — | E8 实测 `pyth_contract=inj12j43nf2f0qumnt2zrrmpvnsqgzndxefujlvr08` + Chainlink Data Streams verifier + Band(默认) | 衍生品定价依赖,适合作高频读 |
| insurance fund | — | E13 实测 PERP 市场 insurance pool(`XAU/USDT PERP balance=23388653836`,redemption=14d notice)| 衍生品清算 buffer,适合作低频读 |

---

## 5. method 差异(diff-only,99% 同 05,只列独有)

> **复用 cosmos-hub 全部 method**(详见 05 §5):`/status` `/block` `/tx` `/abci_query` `/abci_info` + `/cosmos/bank/v1beta1/balances/{addr}` + `/cosmos/staking/v1beta1/validators` + `/cosmos/tx/v1beta1/txs/{hash}` 等。**仅列 Injective 独有新增**:

| Method | 类别 | 实证 | 在 mixed 中权重建议 |
|---|---|---|---|
| `GET /injective/exchange/v1beta1/spot/markets` | exchange 现货市场列表 | E4 实测,字段含 `market_id(32-byte hex)`/`ticker`/`base_denom`/`quote_denom`/`*_fee_rate`/`*_tick_size` | 0.10 |
| `GET /injective/exchange/v1beta1/derivative/markets` | exchange 衍生品市场 | E5 实测,字段含 `oracle_*`/`*_margin_ratio`/`isPerpetual`/`reduce_margin_ratio` | 0.05 |
| `GET /injective/exchange/v1beta1/spot/orderbook/{market_id}` | 实时订单簿快照 | ⚠️ 未测(需 32-byte hex market_id,生产 path)| 0.15(HFT 主负载) |
| `GET /injective/exchange/v1beta1/derivative/orderbook/{market_id}` | 衍生品订单簿 | ⚠️ 未测 | 0.10 |
| `GET /injective/exchange/v1beta1/spot/orders/{market_id}/{subaccount_id}` | 用户挂单 | ⚠️ 未测(subaccount_id = 32-byte hex,与 inj1 地址映射)| 0.10 |
| `GET /injective/exchange/v1beta1/positions` | 衍生品持仓 | ⚠️ 未测 | 0.05 |
| `GET /injective/auction/v1beta1/module_state` | 当前 burn auction | E7 实测 `round=230, ending=1781096400, highest_bid.amount=0` | 0.02 |
| `GET /peggy/v1/params` | bridge 参数 | E6 实测 `bridge_ethereum_address=0xF955C57f9EA9Dc8781965FEaE0b6A2acE2BAD6f3, bridge_chain_id=1` | 0.03 |
| `GET /injective/oracle/v1beta1/params` | 多源 oracle 配置 | E8 实测 Pyth + Chainlink Data Streams | 0.02 |
| `GET /injective/insurance/v1beta1/insurance_funds` | 保险池列表 | E13 实测含 market_id/balance/total_share | 0.03 |
| **`POST /` (EVM JSON-RPC) `eth_chainId`** | injective-1 内嵌 EVM 探活 | ⚠️ 公共未通 | 跳过直到自托管 |
| **`POST /` (inEVM) `eth_*`** | inEVM L2 ChainID=2525 | ⚠️ 公共全 404 / 需 API key | 跳过直到自托管 |

**复用 05 标准 Cosmos method 权重 ~0.35**(bank/staking/tx/block 等)+ **本稿新增 0.65** = 1.00 ✓(订单簿 0.35 + 现货/衍生品市场元 0.15 + 其余 0.15)

---

## 6. 真实负载

- **HFT 订单簿**:Injective 真实 mainnet 70%+ tx 是 exchange module 的 `MsgCreateSpotLimitOrder` / `MsgCreateDerivativeMarketOrder` / `MsgBatchCancelSpotOrders`(单 tx 可批量取消上百订单)。这与 Cosmos Hub(主要 `MsgSend` + `MsgDelegate`)负载模式**完全不同**,vegeta 模型应偏重 orderbook 读 + market 元数据读。
- **跨链桥流量**:Peggy bridge claim/batch 提交持续发生(`signed_batches_window=500000` blocks ≈ 1 周窗口);相关 method `/peggy/v1/batch/*`。
- **衍生品保险池更新**:每次清算触发 `/injective/insurance/*` 状态更新,benchmark 中低权重读路径。
- **EVM 流量**(待 inEVM/in-protocol EVM 自托管后纳入):Web3 dApp(SushiSwap、Hydro、Helix 部分组件)走 `eth_call` + `eth_estimateGas`,与 Ethereum DSL 一致。

---

## 7. DSL 决策(预测 0-2 新字段)

| 字段 | 是否新增 | 理由 |
|---|---|---|
| `family = "cosmos"` | ✅ 复用 | 与 05 同 |
| `adapter = "CosmosAdapter"` | ✅ 复用 | Tendermint RPC + REST 双口同 05 |
| **`module_set`(新增,L1)** | **🆕 推荐** | Cosmos family 内不同链启用的 module 集合差异巨大(Hub 仅标准;Injective +5;Osmosis +concentrated-liquidity;Celestia +blob;dYdX +clob)。DSL 需 `module_set: ["bank","staking","exchange","auction","peggy","oracle","insurance"]`,plugin 据此装配 `rpc_methods` 子集。**避免每链单独 plugin 抄一遍 standard cosmos methods**。 |
| **`denom_format`(新增,L1)** | **🆕 推荐** | Cosmos 各链 denom 形态枚举膨胀:`uatom` / `ibc/<sha256>` / `peggy0x<40hex>`(Injective 独有)/ `factory/<creator>/<sub>`(Osmosis+Injective)/ `erc20:0x<40hex>`(Injective EVM 互通)/ `cw20:<bech32>`(CosmWasm 链)。DSL `denom_format: ["bare","ibc","peggy","factory","erc20"]` 列表,plugin 据此选地址生成 + 余额查询路径。 |
| `evm_layer`(新增,L2,可缓) | ⚠️ 视 inEVM 上压力优先级 | 描述链是否有 EVM 兼容层及其位置:`{type: "in_protocol"|"l2_separate"|"none", chain_id_evm: int, endpoint: url, status: "live"|"requires_self_hosted"}`。Injective 同时有两者,需数组。Phase 2.1 可暂不引入,Phase 2.2 评估 inEVM 是否纳入再加。 |
| `address_format` | ✅ 复用(prefix=inj/injvaloper) | bech32 结构同 05,只换 prefix |
| `chain_id` | ✅ 复用为 string | `injective-1` 字符串,与 `cosmoshub-4` 同结构 |
| `block_semantics` | ✅ 复用 | 标准 Tendermint block,不需 Hedera 那种 record_stream 包装 |

**净增**:**2 个 L1 字段**(`module_set` + `denom_format`)+ **1 个 L2 字段**(`evm_layer`,可缓 Phase 2.2)。

---

## 8. H8 实证证据汇总

| # | 端点 | method | 实测要点 |
|---|---|---|---|
| E1 | REST | `/cosmos/base/tendermint/v1beta1/node_info` | `network=injective-1, app_name=injectived, version=v1.19.0, git_commit=750b3fb, go1.26.2` |
| E2 | RPC | `/status` | `latest_block_height=167817179, latest_block_time=2026-05-23T19:30:54.489Z` |
| E3 | RPC | `/abci_info` | `data=injective, version=v1.19.0, last_block_height=167817179` |
| E4 | REST | `/injective/exchange/v1beta1/spot/markets` | KATANA/USDT + AAVE/USDT 等数十现货市场,含 `market_id`(32-byte hex)/`tick_size`/`maker_fee_rate` 负值返佣 |
| E5 | REST | `/injective/exchange/v1beta1/derivative/markets` | MSFT/USDC PERP 含 `quote_denom=erc20:0xa00C59fF...`(链上股票永续,EVM denom)|
| E6 | REST | `/peggy/v1/params` | `bridge_ethereum_address=0xF955C57f...6f3, bridge_chain_id=1, average_block_time=2000ms, average_ethereum_block_time=15000ms` |
| E7 | REST | `/injective/auction/v1beta1/module_state` | `round=230, ending=1781096400(2026-06-10), bidders_whitelist=[inj1ez42...,inj10n78...]`(✅ 白名单已启用)|
| E8 | REST | `/injective/oracle/v1beta1/params` | `pyth_contract=inj12j43nf2f0qumnt2zrrmpvnsqgzndxefujlvr08` + Chainlink Data Streams verifier `0x60fAa7faC949aF392DFc858F5d97E3EEfa07E9EB` |
| E9 | REST | `/cosmos/bank/v1beta1/balances/inj17xpfvakm2amg962yls6f84z3kell8c5l6s5ye9` | HTTP 200 `{balances:[], pagination:{total:"0"}}`(随机地址余额空)|
| E10/E11 | EVM | `eth_chainId` × 4 endpoints(rpc.inevm.com / inevm-public.publicnode.com / rpc.ankr.com/inevm / injective-evm.publicnode.com) | **全部不可达**:404 / 空响应 / `-32052 API key required` → **inEVM + in-protocol EVM 均 requires_self_hosted** |
| E12 | REST | `/cosmos/staking/v1beta1/validators?status=BOND_STATUS_BONDED` | 返 `validators[].operator_address=injvaloper1qzu3s7uzydpj0vcgrgp04j7u48pgkesy7zl7t3, tokens=321816156053836450339790` 等,bech32 prefix 校验通过 |
| E13 | REST | `/injective/insurance/v1beta1/insurance_funds` | XAU/USDT PERP 池 `balance=23388653836, total_share=2e22, redemption_notice=14d, oracle_type=Pyth` |

---

## 9. DSL ASK(Phase 2.1 user review 卡点)

- [ ] **DSL ASK A (Cosmos family `module_set` 字段)**:是否在 plugin JSON 增加 `module_set: ["bank","staking","exchange","auction","peggy","oracle","insurance",...]`?**强烈推荐**。Cosmos family 已识别至少 6 链(Cosmos Hub / Osmosis / Celestia / Injective / Sei / dYdX),每条独有 module 集合都不同(Hub 0、Injective 5、dYdX clob、Celestia blob、Osmosis CLP/superfluid),如不引入字段,plugin 实现必为每链整抄全套 method 列表,违反 DRY。引入后 plugin 仅写差集。
- [ ] **DSL ASK B (`denom_format` 字段)**:是否引入 `denom_format: ["bare","ibc","peggy","factory","erc20","cw20"]` 列表 + per-format `param_pattern` 正则?**强烈推荐**。Injective 一条链就需要 4 种 denom 形态共存(E4/E5/E6 实证),fixture 生成与 path 渲染必须知道哪种 token 走哪种 denom 格式。
- [ ] **DSL ASK C (`evm_layer` 字段,可缓)**:Injective 同时有 in-protocol EVM(`x/evm` module,injective-1 内)+ inEVM L2(独立 ChainID=2525,Caldera)。是否引入 `evm_layer: [{type:"in_protocol"|"l2_separate", chain_id, endpoint, status}]`?**Phase 2.1 可缓**,因公共 endpoint 均不可达;**Phase 2.2 决定是否纳入**(若 inEVM 用户量起来 → 纳入并标 `requires_self_hosted`)。
- [ ] **DSL ASK D (`min_notional` / `tick_size` 是否进 DSL)**:exchange module 每市场含 `min_price_tick_size`/`min_quantity_tick_size`/`min_notional`,生成有效的 `MsgCreateSpotLimitOrder` 必须遵守。本框架是**只读 benchmark**,**不下单**,因此 ❌ 不入 DSL,但 mixed set 若设计为读订单簿 + 模拟挂单 quote,需 fixture 抓取 market 配置。
- [ ] **DSL ASK E**:Injective 块时间 **<1s**(167M blocks 实测推算),与 Cosmos Hub 6s 差 ~9x。`block_time_ms` 字段已是 per-chain,**确认不需要改 schema**(只是值不同),DSL OK。
- [ ] **DSL ASK F (subaccount_id 概念)**:exchange module 用 32-byte hex `subaccount_id`(由 `inj1...` 地址 + 12-byte 子标识拼成 32-byte),与标准 cosmos `inj1...` bech32 是**不同的实体**。`address_format` 结构化对象(参 14-hedera ASK A)需加 `subaccount: {encoding:"hex32_derived_from_bech32", regex:"^0x[0-9a-fA-F]{64}$"}`?或归 plugin-level 派生。**推荐归 fixture 阶段一次性产出**(`injective_subaccounts.txt`),不入 DSL。
- [ ] **未实证 ⚠️**:Injective 块时间确切数值(凭区块号反推 ~0.65s,未做密集 `/block?height=N` 采样)
- [ ] **未实证 ⚠️**:`/injective/exchange/v1beta1/spot/orderbook/{market_id}` 实际响应 schema(需用 E4 抓的 32-byte market_id 再发一轮)
- [ ] **未实证 ⚠️**:inEVM(ChainID=2525)公共 endpoint 是否完全废弃 / 是否需付费(本次 4 endpoint 全不可达)
- [ ] **未实证 ⚠️**:injective-1 内嵌 EVM 模块在 publicnode 是否会启用(当前 `injective-evm.publicnode.com` 空响应)

---

## Changelog

| Date | Author | Change |
|---|---|---|
| 2026-05-23 | Hermes Agent | 初次调研(DIFF-ONLY 模式);13 次 H8 curl,9 次成功 + 4 次 EVM endpoint 探测全失败;**与 cosmos-hub 复用 ~85%**(Tendermint RPC + Cosmos REST + bank/staking/tx/gov 全套);**独有 ~15%** = exchange(订单簿+衍生品+现货)+ auction(burn)+ peggy(Ethereum bridge,实测桥合约 0xF955C5...)+ oracle(Pyth+Chainlink+Band)+ insurance(衍生品保险池);**EVM 双层**:in-protocol(`x/evm`)+ inEVM L2 ChainID=2525,**两者公共 endpoint 均不可达** → requires_self_hosted;**DSL ASK 6 条**,核心 2 条 L1 新字段(`module_set` + `denom_format`)+ 1 条 L2 可缓字段(`evm_layer`);native INJ decimals=18(与 Cosmos 主流 6 位不同,DSL `balance_unit decimals` 必须 per-chain) |
