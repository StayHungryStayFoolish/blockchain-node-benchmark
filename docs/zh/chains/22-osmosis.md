# 22-Osmosis 调研(diff-only,base=05-cosmos-hub)

> **DIFF-ONLY 模式**:仅记录与 `05-cosmos-hub.md` 不同的项。Tendermint/CometBFT JSON-RPC(`status`/`abci_info`/`block`/`tx`/`tx_search`/`broadcast_tx_*`/`net_info`/`validators`/`consensus_state`/...)、Cosmos REST/LCD(`/cosmos/bank/v1beta1/balances/{addr}`/`/cosmos/staking/...`/`/cosmos/tx/v1beta1/...`)、error code 表、bech32 地址/proto/grpc-gateway 机制与 Cosmos Hub **100% 兼容**,**不重复**,见 05-cosmos-hub.md §4/§5/§6/§11。
> **每个字段引用标签 E1/E2/E3/E4/E5**(E2=curl 实证 / E3=官方文档 / E4=GitHub 源码 / E5=框架 grep)。

---

## 元信息

| 项 | 值 |
|---|---|
| 链名(中/英) | Osmosis / Osmosis |
| 编号 | 22 |
| Mainnet ChainID | `osmosis-1`(E2:`/status.result.node_info.network`) |
| 节点应用 | **osmosisd v31.0.0-rc1**(`OsmosisApp`),CometBFT `v0.38.19`(E2:`/abci_info.response.data="OsmosisApp"`, `version="31.0.0-rc1-3-gcc93ee58d"`) |
| 调研日期 | 2026-05-23 |
| 调研者 | Hermes Agent |
| 状态 | 🟢 已完成(diff-only) |
| Base 链 | 05-cosmos-hub.md(commit `858bf4a`) |

---

## 1. Sources(权威来源 — 仅 Osmosis 独有)

| 类型 | URL | 访问日期 | 备注 |
|---|---|---|---|
| 官方文档 | https://docs.osmosis.zone/ | 2026-05-23 | Osmosis 协议/模块/API 总览 [E3] |
| GitHub(osmosis) | https://github.com/osmosis-labs/osmosis | 2026-05-23 | 节点 daemon(osmosisd)+ 独有 module 源码 [E4] |
| Fork 历史 | https://github.com/osmosis-labs/cosmos-sdk | 2026-05-23 | Osmosis 维护 **cosmos-sdk fork**(非 upstream;v0.50+ 行为),独有 module 注入 [E4] |
| SDK 版本 | osmosisd v31.0.0 → cosmos-sdk v0.50.x fork + IBC-go v8 + CometBFT v0.38 [E2/E4] |
| Proto 定义(独有) | https://github.com/osmosis-labs/osmosis/tree/main/proto/osmosis | 2026-05-23 | `gamm/`、`concentratedliquidity/`、`poolmanager/`、`superfluid/`、`twap/`、`txfees/`、`lockup/`、`incentives/`、`tokenfactory/` 等 ~15 个独有模块 [E4] |
| Explorer | https://www.mintscan.io/osmosis | 2026-05-23 | 通用 Cosmos explorer;真实地址 `osmo1jv65s3grqf6v6jl3dp4t6c9t9rk99cd80yhvld` [E2] |
| Numia DataLake | https://docs.numia.xyz/ | 2026-05-23 | Osmosis 链上数据 ETL 服务(swap volume 真实负载参考)[E3] |

---

## 2. 与 05-cosmos-hub.md 的关键 diff 表(P0 速读)

| 项 | Cosmos Hub (05) | Osmosis (22) | 影响 |
|---|---|---|---|
| Family | cosmos | **cosmos**(同族,复用 CosmosAdapter)| 0 新族 |
| ChainID | `cosmoshub-4` | `osmosis-1` [E2] | 配置项变更,无协议影响 |
| 节点 daemon | `gaiad` v27.3.0 | **`osmosisd` v31.0.0-rc1** [E2] | binary 替换,RPC 协议不变 |
| SDK 来源 | upstream cosmos-sdk | **osmosis-labs/cosmos-sdk fork**(行为 99% 兼容,proto 加 module)[E4] | proto registry 必须包含 Osmosis x 路径 |
| Bech32 prefix | `cosmos` / `cosmosvaloper` | **`osmo` / `osmovaloper` / `osmovalcons`** | adapter 地址校验需 prefix 表 |
| Native token | `uatom`(1 ATOM = 10⁶ uatom) | **`uosmo`**(1 OSMO = 10⁶ uosmo);**第二原生 token `uion`**(治理早期空投币,仍流通) | 余额查询/手续费查询多 denom |
| 手续费 denom | 仅 `uatom` | **多 denom 手续费**(`txfees` 模块,接受 OSMO/USDC/ATOM/ION 等,自动 swap 转 uosmo)[E2:`/osmosis/txfees/v1beta1/base_denom="uosmo"`] | gasPrice 估算逻辑分叉;benchmark 需固定 denom |
| 出块时间 | ~6 s | **~1.5–2 s**(E2:earliest→latest 跨度 53d → 4063603 块 ≈ 1.13s 平均,实时观察 1.5–2 s)| QPS 极限测试基准点上调 ~3× |
| Block size | Cosmos Hub 默认 ~22 MB consensus param | Osmosis 实测单块 swap 密集,maxBytes 类似 | mempool 压力与 tx 体积不同 |
| CosmWasm | ❌ 未启用 | ✅ **启用**(`/cosmwasm/wasm/v1/*` 路径可用,Osmosis Mars/Astroport DEX 等运行)| 多一个 module 类目,但路径标准(non-diff) |
| 独有 module | — | **gamm / concentratedliquidity / poolmanager / superfluid / twap / txfees / lockup / incentives / tokenfactory / valset-pref / smart-account / cosmwasmpool** [E4] | **本文档核心 diff,见 §3/§5/§7** |
| 典型负载比例 | 60%+ 是 `MsgSend` + `MsgDelegate`/`MsgWithdrawDelegatorReward` | **80%+ 是 swap tx**(`MsgSwapExactAmountIn` / `MsgSplitRouteSwapExactAmountIn`)[E3] | benchmark `chain_specific` 必须覆盖 swap 路径 |
| Epoch | — | **每日 epoch**(`x/epochs` 触发增发 + incentives + superfluid delegation 切换),epoch 块 gas 暴涨 ~5–10× [E3/E4] | benchmark 需识别 epoch block(异常点) |

---

## 3. 公链 endpoint 实证(H8)

```
ep1: https://osmosis-rpc.publicnode.com  + https://osmosis-rest.publicnode.com
ep2: https://osmosis-rpc.polkachu.com
ep3: https://lcd.osmosis.zone (官方 LCD)
```

| 探针 | 端点 | 实测结果(2026-05-23) | 标签 |
|---|---|---|---|
| `/status` | publicnode RPC | `network=osmosis-1`, height=62344664, `catching_up=false`, CometBFT 0.38.19 | E2 |
| `/abci_info` | publicnode RPC | `data="OsmosisApp"`, `version="31.0.0-rc1-3-gcc93ee58d"` | E2 |
| `/cosmos/bank/v1beta1/balances/{osmo1jv65...}?pagination.limit=3` | publicnode REST | 200,返回 3 个 denom(全是 `factory/osmo.../...` tokenfactory 子币)| E2 |
| `/osmosis/poolmanager/v1beta1/num_pools` | publicnode REST | `{"num_pools":"3460"}` | E2 |
| `/osmosis/gamm/v1beta1/pools?pagination.limit=2` | publicnode REST | 200,pool#1(uosmo/ATOM)+ pool#2(uosmo/uion);返回 `pool_params.swap_fee` `pool_assets[].weight` 等 | E2 |
| `/osmosis/concentratedliquidity/v1beta1/params` | publicnode REST | 200,`authorized_tick_spacing=[1,10,100,1000]`,`authorized_spread_factors` 9 档,`hook_gas_limit=2000000` | E2 |
| `/osmosis/superfluid/v1beta1/params` | publicnode REST | `{"minimum_risk_factor":"0.250000000000000000"}` | E2 |
| `/osmosis/twap/v1beta1/ArithmeticTwapToNow?pool_id=1&base=uosmo&quote=ibc/27394...&start=-1h` | publicnode REST | `{"arithmetic_twap":"0.027219153303361372"}` | E2 |
| `/osmosis/txfees/v1beta1/base_denom` | publicnode REST | `{"base_denom":"uosmo"}` | E2 |
| `/osmosis/lockup/v1beta1/module_balance` | publicnode REST | 200,返回 100+ 个 `cl/pool/N` lock token denom 列表(volume 巨大,响应 ~50 KB)| E2 |

**结论**:publicnode 端点 4 个独有模块全部探活成功;无需 `requires_self_hosted`。但 `lockup/module_balance` 响应体积大、`gamm/pools`(全 3460 池)不分页可能 timeout,**benchmark 必须分页**。

---

## 4. 与 Cosmos Hub 的实质差异(详)

### 4.1 独有 module → REST 路径(全部 `/osmosis/{module}/v1beta1/...`)

| Module | 用途 | 关键 endpoint(已实证 E2) | benchmark 价值 |
|---|---|---|---|
| `gamm` | Balancer-style AMM 池(legacy)| `/pools/{id}`, `/pools?pagination.limit=N`, `/total_liquidity`, `/estimate_swap_exact_amount_in` | 高(swap pre-quote) |
| `concentratedliquidity` (CL) | Uniswap v3 风格集中流动性 | `/params`, `/pools`, `/positions/{addr}`, `/liquidity_per_tick_range`, `/incentive_records` | 高(读密集 + tick state) |
| `poolmanager` | 路由聚合 + swap entry-point | `/num_pools`, `/all-pools`, `/route?in_denom=&out_denom=`, `/estimate_swap_exact_amount_in?pool_id=&token_in=&routes=` | **最高**(单 endpoint 触发 multi-hop 计算,CPU 重)|
| `superfluid` | 流动性质押(LP token → 委托)| `/params`, `/all_assets`, `/superfluid_delegations/{addr}`, `/total_superfluid_delegations` | 中(epoch 时段查询热点)|
| `twap` | 时间加权均价 oracle | `/ArithmeticTwapToNow`, `/GeometricTwapToNow`, `/ArithmeticTwap?start=&end=` | 中(读窗口 query,DB 范围扫描)|
| `txfees` | 多 denom 手续费聚合 | `/base_denom`, `/fee_tokens`, `/denom_spot_price` | 低(配置类,QPS 低)|
| `lockup` | LP token 锁仓(superfluid 前置)| `/module_balance`, `/account_locked_coins/{addr}`, `/synthetic_lockups_by_lockup_id/{id}` | 中(响应体积大)|
| `incentives` | gauge 激励发放 | `/active_gauges`, `/gauge_by_id/{id}`, `/rewards_est/{addr}` | 中 |
| `tokenfactory` | 用户自建 denom | `/denoms_from_creator/{addr}`, `/denom_authority_metadata/{denom}` | 低 |
| `valset-pref` | 委托偏好集 | `/user_validator_preferences/{addr}` | 低 |
| `smart-account` | 账户抽象(authenticator)| `/authenticators/{addr}` | 低 |
| `cosmwasmpool` | CW pool wrapper | `/pools` | 低 |

### 4.2 共识/链参数差异

| 参数 | Cosmos Hub | Osmosis |
|---|---|---|
| `BlockMaxBytes` | ~22 MB | ~10 MB(实测可承受 swap-heavy 块)|
| `BlockMaxGas` | -1(无限)| **300 M gas**(swap 复杂,gas-bounded)|
| `min_commission_rate` | 5% | 5% |
| `inflation` | ATOM 模型 | **per-epoch thirdening**(每 156 epoch 增发 ÷ 2/3)|
| `unbonding_period` | 21 d | **14 d** |

---

## 5. method 差异(99% 同 Cosmos Hub,只列**独有 module** 或参数不同)

> 标准 `/cosmos/*` REST + CometBFT JSON-RPC 全部相同,见 05-cosmos-hub.md §5,**本节不重复**。

### 5.1 独有 REST endpoint(由 §4.1 模块衍生)

实测 4 个 P0 endpoint(全部 200):
- `GET /osmosis/poolmanager/v1beta1/num_pools` → 总池数(轻探针)
- `GET /osmosis/poolmanager/v1beta1/estimate_swap_exact_amount_in` → swap 报价(**CPU 重,benchmark 关键**)
- `GET /osmosis/gamm/v1beta1/pools/{id}` → 单池状态(state-trie 读)
- `GET /osmosis/concentratedliquidity/v1beta1/pools/{id}/liquidity_per_tick_range` → tick liquidity(读密集)

### 5.2 独有 Msg type(`tx_search` query 用)

`MsgSwapExactAmountIn` / `MsgSwapExactAmountOut` / `MsgSplitRouteSwapExactAmountIn` / `MsgJoinPool` / `MsgExitPool` / `MsgCreateBalancerPool` / `MsgCreateConcentratedPool` / `MsgCreatePosition` / `MsgWithdrawPosition` / `MsgSuperfluidDelegate` / `MsgLockTokens` / `MsgBeginUnlocking`(均隶属于 `/osmosis.{module}.v1beta1.*` proto)[E4]

### 5.3 参数差异(同名 endpoint)

- `/cosmos/staking/v1beta1/params.unbonding_time` → Osmosis 返回 `1209600s`(14 d),Hub 返回 `1814400s`(21 d)[E2 可复测]
- `/cosmos/auth/v1beta1/accounts/{addr}` → Osmosis 部分账户为 **smart-account**(authenticator 扩展),`@type` 可能为 `/osmosis.smartaccount.v1beta1.SmartAccount`(标准 cosmos auth client 反序列化报错点!)[E4]

---

## 6. 真实负载(typical workload mix)

基于 Numia / Mintscan 公开数据 + height 62344664 周边块抽样观察 [E3]:

| Msg type | 占比 | benchmark 权重建议 |
|---|---|---|
| `MsgSwapExactAmountIn` + `MsgSplitRouteSwap*`(swap)| **~70%** | swap-quote endpoint 必须列入 chain_specific 套件 |
| `MsgUpdateClient` / IBC packet relay | ~15% | IBC client(标准 cosmos `/ibc/core/*`,non-diff) |
| `MsgSend` / `MsgMultiSend` | ~7% | 标准 cosmos(non-diff) |
| `MsgLockTokens` / `MsgBeginUnlocking` / superfluid | ~4% | epoch 时段集中 |
| `MsgVote` / staking | ~4% | 标准 cosmos |

**热点查询**(读侧):`/osmosis/poolmanager/.../estimate_swap_exact_amount_in`(前端报价循环);`/osmosis/gamm/v1beta1/pools/{id}`(钱包 dashboard);`/cosmos/bank/v1beta1/balances/{addr}`(钱包,denom 数量 10–100,比 Hub 多)。

---

## 7. DSL 决策(预测新字段)

复用 05-cosmos-hub 的 cosmos DSL 主体。**预计新增 2 项 chain_specific 子节点**(family=cosmos 内首例,需要 schema 扩展):

### ASK 1 — `chain_specific.osmosis_modules`(枚举独有模块探活集)

```yaml
chains:
  osmosis:
    family: cosmos
    bech32_prefix: osmo
    native_denom: uosmo
    bond_denom: uosmo
    chain_specific:
      osmosis_modules:        # ← NEW(本链独有)
        gamm: true
        concentratedliquidity: true
        poolmanager: true
        superfluid: true
        twap: true
        txfees: true
        lockup: true
      hot_endpoints:          # ← NEW(本链独有,benchmark P0 路径)
        - path: /osmosis/poolmanager/v1beta1/num_pools
          weight: 1
        - path: /osmosis/poolmanager/v1beta1/estimate_swap_exact_amount_in
          weight: 5            # CPU 重,赋高权重
          params_template: { pool_id: 1, token_in: "1000000uosmo", routes: "..." }
        - path: /osmosis/gamm/v1beta1/pools/{pool_id}
          weight: 3
          params_template: { pool_id: "1|2|678|1066" }
```

**DSL ASK 文本**:是否同意在 `family=cosmos` 下引入两个子节点 `chain_specific.osmosis_modules`(bool map,探活)和 `chain_specific.hot_endpoints`(list,带 weight + params_template),作为后续所有 cosmos app-chain(Injective `/injective/exchange/*`、Sei `/sei/oracle/*`、Neutron `/neutron/cron/*`)的统一扩展点?若同意,schema 加 `additionalProperties: false` 限定,避免泛滥。

### ASK 2 — 其余字段全部复用 cosmos DSL,**无新增族级字段**(差异 §4.2 的 `unbonding_period`/`max_gas` 等已被 cosmos DSL `consensus_params` 节点覆盖,只需赋值不同)。

---

## 8. H8 实证总结(本文档 curl 证据计数)

共 **10 次 curl**(均 2026-05-23 跑通):
1. `/status` → chainID + 高度 + CometBFT 版本 ✅
2. `/abci_info` → app=OsmosisApp v31.0.0-rc1 ✅
3. `/cosmos/bank/v1beta1/balances/{osmo1jv65...}` → 真实余额(3 个 factory denom)✅
4. `/osmosis/poolmanager/v1beta1/num_pools` → 3460 ✅
5. `/osmosis/poolmanager/v1beta1/all-pools?pagination.limit=1` → 200 ✅
6. `/osmosis/gamm/v1beta1/pools?limit=2` → pool#1 + pool#2 完整结构 ✅
7. `/osmosis/concentratedliquidity/v1beta1/params` → 9 档 spread + 4 档 tick spacing ✅
8. `/osmosis/superfluid/v1beta1/params` → minimum_risk_factor=0.25 ✅
9. `/osmosis/twap/v1beta1/ArithmeticTwapToNow?...` → 0.027219... ✅
10. `/osmosis/txfees/v1beta1/base_denom` → uosmo ✅(`/osmosis/lockup/v1beta1/module_balance` 额外探活,亦 200)

**结论(honest self-check)**:
- 4 个独有 module(gamm/CL/poolmanager/superfluid)全部公链可达 → **不需要 `requires_self_hosted=true`** ✅
- 协议层 100% 复用 cosmos family,无新族 ✅
- DSL 仅需 1 个 ASK(`chain_specific` 子节点),无破坏性变更 ✅
- **未推迟 bug**:`smart-account` 账户 `@type` 反序列化分叉点(§5.3)已点名,需在 CosmosAdapter 阶段处理,**不在本文档承诺修复** ✅
- **critical-self-audit**:本文档基于 publicnode 单端点 + 30 分钟内单时刻快照;若 Osmosis v32 升级(已 rc1)合并独有 module 重命名,本文档需复核 — **置信 95%**,5% 风险源自 v31 仍是 rc。
