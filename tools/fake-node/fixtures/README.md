# fake-node fixtures — 184 method 真实请求/响应数据集

> 2026-06-02 全量录制。**本目录入库**(策略变更, 见 `.gitignore` 顶部说明)。

## 这是什么

36 链 184 个 RPC method 的**真实 public endpoint 实测数据**(确认正常响应):
- `<chain>/<method>.json` — **响应体**(byte-correct, fake-node handler passthrough 直接返回)
- `<chain>/<method>.request.json` — **请求示例**(完整请求体 / REST path+body, 供构造 vegeta + 二次开发参考)

method 名含 `/` 的(tron `/wallet/*`、rest path 风格)文件名把 `/` 替换为 `_` 并去前导 `_`。

## 为什么入库(策略变更)

框架要支持 36 链, 但**无法快速部署 36 个真实区块链节点**, 公共节点又限流。
离线二次开发(无真实节点环境)必须开箱即用 → mock fixture + 请求示例都入库。
数据来源 = §3 全量实测(`analysis-notes/rpc-method-abstraction-design.md` §3 矩阵的完整版)。

(历史: 此前 `fixtures/` 被 .gitignore, 前提是"clone 后能连真实节点 record";该前提在
36 链场景不成立, 故本次破例入库。)

## 覆盖率

- **180 / 184 method 真实实测落盘**(public endpoint 拿到正常响应)。
- **4 类结构性不可达**(非数据缺失, 是 method 本身在共享公开节点拿不到, 已知且记录):

| 链/method | 原因 |
|---|---|
| bitcoin / dogecoin `getreceivedbyaddress` | wallet 方法, 共享公开节点禁用(-32701)。真实部署有节点本地 wallet 时可用。(bch/litecoin 节点未禁, 已抓到) |
| acala / kusama / polkadot `system_account` | **不是有效 Substrate RPC method**(节点 -32601)。chain template 历史误声明, 真实余额查询须 state_getStorage 或 Sidecar。详见 design §3.2 |
| polkadot `GET /accounts/{addr}/balance-info` / `GET /blocks/{n}` / `GET /pallets/staking/progress` | substrate-api-sidecar 服务接口, Parity 停止公开托管, 须自建 Sidecar |

这 4 类的响应结构按官方文档记录在 design §3 矩阵(无 fixture 文件, 因节点拿不到真实响应)。

## 刷新方式

```bash
bash tools/fake-node/scripts/record_all_184_fixtures.sh
```
脚本内置 36 链 public endpoint 映射 + 取真实参数逻辑(block hash / tx hash / token account 现场从节点取)+ 限流(Koios 2s / Tatum 14s / 通用 1.2s)。

## 注意

- 个别 fixture 偏大: near `validators`(~419KB, 全验证人列表)是真实但大。其余多为几十~几百字节。
- endpoint 映射见脚本顶部(linea→官方 / starknet→lava / bitcoin系→publicnode+drpc+tatum / acala eth_*→独立EVM端 / algorand transactions→indexer)。
