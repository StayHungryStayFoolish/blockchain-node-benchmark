# Mock Fixture Manifest — 公开 endpoint 测不到、按官方文档 mock 的 method

> 2026-06-05 生成。这 8 个 method 在公开节点测不到真实响应(wallet 类被禁 / SCALE 需客户端解码 / public sidecar WS 不可用),
> 按官方文档结构 mock。用户拍板甲方案(SCALE 也 mock,fake-node byte passthrough 不需理解内容)+ 乙执行(结构正确 + 诚实标注,不在边角抠精确字节)。
>
> **这些 fixture 的响应值是按官方文档结构构造的占位,不是真机实测。** fake-node byte passthrough 能正常重放(让 mixed 模式跑通),
> 但其中 SCALE 编码的 system_account 标 KNOWN_BROKEN —— 框架声明式 response_spec 无法从 SCALE hex 提取余额(NS-3 DSL 真边界,需客户端 SCALE 解码或 sidecar/adapter 兜底)。

## A 组:bitcoin 系 getreceivedbyaddress(wallet-class,公开节点禁)

| chain | method | 来源 | mock 说明 | 框架可解析 |
|---|---|---|---|---|
| bitcoin | getreceivedbyaddress | Bitcoin Core 官方 RPC 文档 https://developer.bitcoin.org/reference/rpc/getreceivedbyaddress.html | numeric 标量响应 `{"result":0.05,"error":null,"id":1}`(jsonrpc 1.0 风格)。公开节点返 -32701/-32601(wallet 子系统禁用) | ✅ 普通数值 |
| dogecoin | getreceivedbyaddress | Dogecoin Core(Bitcoin Core fork,无 include_immature_coinbase 第三参) | 同上,DOGE 单位,对齐 dogecoin 现有 fixture 的 2.0 风格 | ✅ 普通数值 |

## B 组:substrate system_account(state_getStorage 返 SCALE hex,🔴 KNOWN_BROKEN)

| chain | method | 来源 | mock 说明 | 框架可解析 |
|---|---|---|---|---|
| acala | system_account | Substrate frame_system pallet 官方 storage 定义(polkadot.js docs)。storage key = `twox128("System")+twox128("Account")+blake2_128_concat(AccountId)` | 响应 = SCALE 编码 hex 字符串 `{"jsonrpc":"2.0","result":"0x<scale>","id":1}`。AccountInfo 结构 = {nonce(u32), consumers(u32), providers(u32), sufficients(u32), data:{free(u128), reserved, frozen, flags}}。hex 是按该结构构造的合理样例 | 🔴 KNOWN_BROKEN(需客户端 SCALE 解码) |
| kusama | system_account | 同上 | 同上 | 🔴 KNOWN_BROKEN |
| polkadot | system_account | 同上 | 同上 | 🔴 KNOWN_BROKEN |

## C 组:polkadot Sidecar REST(public sidecar WS 不可用,按 OpenAPI schema mock)

| chain | method | 来源 | mock 说明 | 框架可解析 |
|---|---|---|---|---|
| polkadot | GET /accounts/{addr}/balance-info | Substrate API Sidecar OpenAPI v20.14.1 https://paritytech.github.io/substrate-api-sidecar/dist/ | 普通 JSON {at, nonce, tokenSymbol, free, reserved, frozen, miscFrozen, feeFrozen, locks}。实测 public sidecar 返 500 WebSocket not connected(后端 WS 挂),只能 mock | ✅ 普通 JSON(response_spec 可提 free) |
| polkadot | GET /blocks/{n} | 同上 | 普通 JSON {number, hash, parentHash, stateRoot, extrinsicsRoot, authorId, logs, extrinsics} | ✅ 普通 JSON |
| polkadot | GET /pallets/staking/progress | 同上 | 普通 JSON {at, activeEra, forceEra, eraProgress, sessionProgress} | ✅ 普通 JSON |

## 复核 TODO(乙执行的诚实标注)

按乙方案,B/C 组的具体响应值是官方结构骨架 + 合理占位,非精确实测。若后续要提高严谨度:
- B 组 SCALE hex:可用 polkadot.js / subxt 对真实账户编码出精确 hex 替换
- C 组 Sidecar:可在 parity public sidecar 恢复或自建 sidecar 后真机实测替换
这些是 KNOWN_BROKEN / 边界项,不影响主链 method 的归因精度,故按乙不阻塞实施。
