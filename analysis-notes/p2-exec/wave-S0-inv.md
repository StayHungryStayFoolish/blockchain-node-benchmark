# wave-S0-inv:27 新链 + TON 调研抽取(2026-05-24)

## 目标
把 36 链(8 baseline + 27 新调研 + 1 TON)的 chain template JSON 全部落盘到 `config/chains/*.json`,作为 S1 拆 8 链 + S2 wave 1-8 的输入。

## 决策
- 方案 T3(用户拍板):27 链 inventory 由 3 批 subagent 并行抽取(B+/A+A/Y+ 架构,Y=read-only md 抽取),同时 TON 独立 subagent 跑实证调研
- 对齐 mixed_methods 数量:每链 4-5 个,与 baseline 8 链(solana 5 / ethereum 5)对齐
- 加 `_meta` 字段标识来源(`source:"research-md"` vs `source:"baseline-config_loader-sh"`),baseline_sha=`ffbeeee`

## 执行(2026-05-24)
**Stage 1:3 批 subagent 并行(100 秒)**
- Batch 1(9 链):bitcoin/aptos/cosmos-hub/cardano/polkadot/near/tron/algorand/tezos —— 100.67s
- Batch 2(9 链):avalanche-c/avalanche-x/hedera/arbitrum/optimism/zksync-era/linea/litecoin/dogecoin —— 79.77s
- Batch 3(9 链):bch/osmosis/celestia/injective/sei/kusama/acala/moonbeam/astar —— 77.79s
- 解析:27/27 JSON 全部 jq -c 可解析 ✅

**Stage 2:TON 独立 subagent(363 秒)**
- 实证 7 个候选 endpoint,4 个 E2 200 OK + 3 个 FAIL(Ankr 403 / publicnode 404 / ORBS 404)
- 产出 `docs/zh/chains/30-ton.md`(29918 bytes,11 节齐全)
- target_address EQCD39VS...(Telegram 团队钱包,1.59M TON,真实活跃)+ 真实 tx 三元组样本
- TON 独立 family,需新建 `TONAdapter`(异构点:masterchain/workchain 分片 + 地址三态 + tx 三元组 + TVM stack 类型化)

**Stage 3:36 链 template 落盘**
- 写入 `config/chains/*.json` 28 个新文件(27 + ton)
- 跳过 0 个(既有 8 baseline 不动)
- 最终 36 文件齐全 ✅

## 产物
- `config/chains/*.json` 36 个(8 baseline + 27 新调研 + 1 ton),共 ~52KB
- `docs/zh/chains/30-ton.md` 29918 bytes
- `/tmp/all_27_chains.jsonl` 备份(可丢)

## 实证(E5)
| 项 | 数值 |
|---|---|
| 27 链 subagent 解析率 | 27/27 (100%) |
| TON endpoint 实测率 | 7/7,4 PASS / 3 FAIL(已标 verified=FAIL+notes) |
| _meta 字段齐全率 | 36/36 (100%) |
| mixed_methods 数量对齐 baseline | 36/36 在 4-5 范围 |
| JSON parse 率(`json.load`) | 36/36 (100%) |

## 已知风险(待 S1-S2 处理)
1. **param_formats 风格不统一**:bitcoin 用 `[blockhash,verbosity]`,evm 用 `address_latest`,REST 用 `path_addr` —— S1 必须做 normalization 一遍
2. **6 链 target_address 空或零地址**:litecoin/celestia/sei/acala/moonbeam/astar —— S2 wave 内必须补
3. **部分链 requires_self_hosted**:celestia(blob)、injective(EVM L2)、linea(标准 EOA 但 baseFee 锁 7 wei) —— wave 内决策跳过 vs mock
4. **kusama 用 wss://(WebSocket-only 备用)** —— adapter 不支持 WS,公链只剩 1 个 HTTP endpoint,需观察 RPS
5. **TON 公链 1 RPS 限流** —— L3 必须 mock,生产必须 self-host

## 4 护栏检查
- ① 每 wave commit:本 wave **未 commit**(等 S0-tools 一起 commit 进 S1.3)
- ② 复用链 diff-only:8 baseline 文件未触碰 ✅
- ③ 超时 fail-fast:3 批 + TON 总 463 秒,无超时 ✅
- ④ 决策反转停手报告:本 wave 无反转 ✅

## 下一步
S0-tools(L3 前置工具链):
1. mock_rpc_server 扩展(覆盖 27 新链 + TON 新方法集)
2. e2e_chain_smoke.sh harness(36 链批量 smoke)
3. baseline 8 链 snapshot(diff=0 验证 reference)

## skill 自检
- `parallel-entry-trap`:✅ 未引入新模板路径,所有 27 链直接走 `config/chains/*.json` 既有路径
- `critical-self-audit-after-fix`:✅ 已列 5 个已知风险并归类
- `honest-self-check-no-fake-evidence`:✅ subagent 输出有 7/7 实测证据,FAIL endpoint 真实标注未隐藏
- `decision-with-tradeoffs`:✅ T1/T2/T3 出表 + 推荐 + 用户拍板

## 时间
2026-05-24 ~01:00 起,~01:10 完成(10 分钟,纯并行加速)
