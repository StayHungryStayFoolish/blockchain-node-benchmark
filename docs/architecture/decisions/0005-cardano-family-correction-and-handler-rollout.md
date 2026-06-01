# ADR-0005: Cardano 协议族归位 + fake-node v2 多 family handler 引入

## 状态

Accepted (2026-05-28)

## 背景

### 触发条件

1. **三方矛盾(schema vs 调研稿 §10 vs 调研稿 §11.8)** — `config/chains/cardano.json` 当前 `_meta.adapter_family=ogmios`,但:
   - `docs/zh/chains/06-cardano.md` §10 决策表选 "新建 CardanoAdapter, family=cardano-eutxo"
   - 同文 §11.8 推 Koios REST(HTTP REST + JSON,与 algorand/aptos/tezos/ton 同 `rest` family)
   - 二者都不是 `ogmios`(Ogmios 是 WebSocket JSON-RPC,Dandelion 公共端点已下线,自部署成本~500GB SSD)
   - normalize 脚本误判,装上即挂(Python `OgmiosAdapter._build_params` 不识别 `POST /address_info` 这种 REST key,fallback 错误)

2. **ogmios family 0 用户** — grep 36 链 `_meta.adapter_family` 分布:
   ```
   16  jsonrpc            [arbitrum, avalanche-c, avalanche-x, base, bsc, ethereum, linea,
                          near, optimism, polygon, scroll, solana, starknet, sui, tron, zksync-era]
    5  substrate          [acala, astar, kusama, moonbeam, polkadot]
    5  tendermint         [celestia, cosmos-hub, injective, osmosis, sei]
    4  rest               [algorand, aptos, tezos, ton]
    4  bitcoin_jsonrpc    [bch, bitcoin, dogecoin, litecoin]
    1  ogmios             [cardano]      ← 错配,真正应该是 rest
    1  hedera_dual        [hedera]
   ```
   `ogmios` 是 dangling 0-user family,按 `parallel-entry-trap` 规范属于 trap(新人看了以为 cardano 装上能跑)。

3. **framework `tools/chain_adapters/rest.py` POST body bug** — L87 POST 分支 body 永远传空 `{}`,不读 chain template 的 body_template 字段;cardano `POST /address_info` 需要 `{"_addresses": ["..."]}`,无 body 则 Koios 返回 400。这是 ogmios → rest 迁移的必经依赖。

4. **fake-node v2 当前只有 jsonrpc + bitcoin_jsonrpc + NotImplementedHandler stub**,5 个 family(substrate / tendermint / rest / hedera_dual + 原 ogmios)挂在 stub 上,任一 RPC 调用就 fail。要让 16 链 (除 jsonrpc 16 + bitcoin_jsonrpc 4 = 已覆盖 20 链外) 跑通 smoke,必须引入 4 个真 handler。

### 为什么本轮一起做

- (1) + (3) 是同一条 cardano 路径的两段(协议归位 + framework 修 bug),拆分会造成"改了 chain config 但 framework 不支持 body"的死状态
- (2) 是 (1) 的副产品(ogmios family 被腾空后必须删,留着是 trap)
- (4) 是 (1) 的同结构问题(framework + fake-node 双侧 family 支持必须对齐)

## 选项

### 选项 A — Cardano family 选择

| 候选 | family | 优点 | 缺点 |
|---|---|---|---|
| A1 | `cardano-eutxo`(新建独立族,调研稿 §10 选项) | 数据模型语义最准 | EUTXO 是 reader 层概念,**transport 层** Koios = 纯 REST,新建 family 重复造轮子;Python 需新 adapter,Go 需新 handler,~400 LOC |
| **A2** | `rest`(加入既有 family,调研稿 §11.8 推荐) | 复用 algorand/aptos/tezos/ton 的 RestAdapter + 即将引入的 Go rest handler;EUTXO 数据模型差异在 reader 层 / analysis 层处理(本框架 benchmark 阶段不需要 EUTXO 解析) | rest.py POST body bug 必须本轮修(否则 cardano 跑不通) |
| A3 | 保持 `ogmios`(0 用户),走 Ogmios WebSocket | 与原 normalize 脚本对齐 | Dandelion 下线;Vegeta 不支持 WS;自部署 500GB SSD;**违反 §11.8 推荐与 parallel-entry-trap 0-user 规范** |

### 选项 B — Ogmios family 处置

| 候选 | 决策 | 优点 | 缺点 |
|---|---|---|---|
| **B1** | **删除** ogmios family(0 链使用后) | 消除 dangling family trap;Python `OgmiosAdapter` 删除约 80 LOC | 若未来真有链需要 Ogmios(无),重新加;低概率 |
| B2 | 保留 stub | 给"未来 Ogmios 链"留位 | 0-user dangling family = parallel-entry-trap 6th offense 违反 |

### 选项 C — fake-node 5 family handler 引入

| 候选 | 决策 | 优点 | 缺点 |
|---|---|---|---|
| **C1** | 引入 4 个 handler(rest / substrate / tendermint / hedera_dual)+ 删除 ogmios | substrate 用 hex replay 通用化~120 LOC;tendermint REST 复用 rest.py 模板~100 LOC;hedera_dual ~150 LOC;rest ~100 LOC;**总 ~470 Go LOC** 覆盖 16 链(从 20/36 → 36/36 RPC-ready) | 4 family × N 链的 fixture 需要 record 真 mainnet 响应,~1.5h 网络 RTT 实测 |
| C2 | 只引入 rest handler(只够 cardano + algorand/aptos/tezos/ton),其他 stub | 工作量小 ~100 LOC | substrate/tendermint/hedera_dual 仍挂 stub,违反"全部跑通"承诺;违反 `no-deferred-bugs`(defer feat coverage = 4th offense) |

## 决策

**全部按 A2 + B1 + C1 + 修复 rest.py POST body bug,本轮一起做。**

一句话理由:**ogmios family 是错配也是 0 用户 trap,cardano 协议归位到 rest 是调研稿 §11.8 推荐选项 + 工程量最小路径;同步修 rest.py body bug + 引入 4 family handler 让 16 链 (剩余 cardano + 5 substrate + 5 tendermint + 1 hedera) 同 PR 跑通,避免 cascade 跨 PR**。

## 后果

### 正面

1. **36/36 链 fake-node smoke ready** — jsonrpc 16 + bitcoin_jsonrpc 4 + rest 5(cardano + algorand/aptos/tezos/ton)+ substrate 5 + tendermint 5 + hedera_dual 1 = 36
2. **`_REGISTRY` 7 → 6 family** — 删 ogmios,从此 chain template `_meta.adapter_family` 取值受限于 6 个真实在用,新人不会装上 ogmios
3. **rest.py POST body bug 修复** — 同 PR 兜底,future-proof for any 新 REST 链(如未来加 sui REST API)
4. **NS-3 进度** — proxy 协议解析层零代码扩展验证,新增 family 走 chain template + Go handler 两件套不动 proxy

### 负面

1. **本 PR diff 大** — 1 个 ADR + 1 个 cardano.json 改写 + 1 个 rest.py bug fix + 4 个 Go handler + ~12 个 fixture json + 1 个 smoke 脚本扩展 + 5 个调研稿加 §"caller/reader 改造点"
2. **fixture 时效性** — Koios `/tip` 等 hot field 会过时,fake-node fixture 需注释 "snapshot at 2026-05-28,数值字段对生产无效"

### 后续工作

1. CURRENT-STATE.md 更新 fake-node RPC-ready 从 20/36 → 36/36
2. OPEN-QUESTIONS.md OQ-9 标 RESOLVED:"ogmios family 是否保留 stub" → 删
3. 未来若引入 starknet/avalanche-c/avalanche-x/scroll/polygon/base 等调研稿,follow Phase N caller/reader 改造点模板(本 ADR 在 cardano 上验证可行)
4. ci_smoke.sh 拓展到 16 链(本 ADR 范围内),其余 20 链 jsonrpc/bitcoin_jsonrpc 已 cover

## 参考

- `docs/zh/chains/06-cardano.md` §10/§11.8
- `tools/chain_adapters/base.py:107` (_REGISTRY)
- `tools/chain_adapters/rest.py:87` (POST body bug)
- `tools/fake-node/handlers/base.go:60` (Handler/Register dispatch)
- `tools/fake-node/fake_node.go:300` (BLOCKCHAIN_NODE entry)
- skills: `parallel-entry-trap` (0-user family trap), `no-deferred-bugs` (rest.py body bug 不挂 OQ), `architecture-governance` (本 ADR 模式)
