# RPC method 参数构造 重构前调用链分析(token-level 精读, 2026-06-02)

> 方法: 加载 skill(blockchain-node-benchmark-architecture / token-level-careful-edit / parallel-entry-trap)+ memory + 沉淀文档, GREP-EVIDENCE 锚定真实入口, 逐文件 token-level 精读 6 family adapter + cli.py + target_generator, **用真实 adapter 构造结果 vs §3 实测正确请求对比判定真债**(非 grep 分支推断, 避免 parallel-entry-trap E6 顶层误报)。
> 结论先行: 重构有真价值(修真债 + 实现 DSL 北极星), 但**当前 adapter 已有大量真债**, 重构 = 修债 + 抽象 二合一, 必须分 family、保调用链不断、向后兼容。

## 1. 完整调用链(token-level 实证, 每环文件:行)

```
master_qps_executor.sh (设 BLOCKCHAIN_NODE env)
   │
   ▼
tools/target_generator.sh generate_targets() L234-268
   │  single: 所有账户用 CURRENT_RPC_METHODS_ARRAY[0]; mixed: account_index % method_count round-robin
   │  组 TSV(method\taddress) 管道喂给 ↓
   ▼
tools/chain_adapters/cli.py  cmd_build_targets_batch() L80-111
   │  L88 os.environ["BLOCKCHAIN_NODE"]=chain  (always override)
   │  L105 pf_cache[method] = _get_param_format(chain, method)   ← 查 param_formats, fallback "single_address"(L55) = R3 根源
   │  L106 adapter.build_vegeta_target(method, address, rpc_url, param_format)
   ▼
tools/chain_adapters/base.py  get_adapter(chain) L119-136
   │  按 _meta.adapter_family 派发到 6 family adapter; 接口固定 build_vegeta_target(method, address, rpc_url, param_format)
   │  ⚠️ 接口只有【单个 address 槽】= 现状硬约束(多参数 method 靠占位符塞)
   ▼
<family>.py build_vegeta_target → _build_params(param_format, address)
   │  jsonrpc/substrate/bitcoin: param_format if-else → list; default fallback [address]
   │  tendermint: param_format if-else → dict; default {address:addr}
   │  rest: 不用 param_format, 用 _meta.rest_paths[method] {method,path,body} 替换 {address}  ← 已是声明式 DSL
   │  hedera_dual: 按 method 前缀 _is_jsonrpc_method 路由到 rest/jsonrpc 子 adapter
   ▼
_vegeta_post_json / _vegeta_get → vegeta target JSON {method,url,header,body(b64)}
   ▼
vegeta attack → (PROXY_ENABLED 时) proxy:18545 透传记 method 时序 → 节点
   ▼
proxy sink CSV(9列) → analysis/per_method_attribution.py 频次权重归因 → 图 → HTML
```

**关键事实**:
- 参数构造的唯一可变输入 = `(method, address, param_format)`, **address 是单槽**。多参数/对象参数 method 现状靠"把 address 当唯一业务值 + param_format 名编码其余位置 + 占位符兜底"。
- rest family 的 `_meta.rest_paths` 已经是任务北极星想要的声明式 DSL 样板(同 proxy_extraction)。
- 校验缺失: cli.py `_get_param_format` 漏声明 fallback `single_address`(R3), 无任何"param_format 合法性 / 与 method 匹配"校验(R2)。

## 2. 🔴 真债清单(真实 adapter 构造结果 vs §3 实测正确请求, 逐条对比判定)

> 判定法: `get_adapter(ch).build_vegeta_target(method,addr,url,fmt)` 实跑 → 解码 vegeta body → 对比 §3 实测的真实正确请求。**不是 grep 有无分支**(那会误报: substrate no_params 用 `in (...)` 语法, grep `==` 漏匹配)。

### 2.1 协议级错配(🔴 最严重, 构造的请求协议完全错, 节点必拒)

| family | 链/method | adapter 实际构造 | §3 实测正确 | 根因 |
|---|---|---|---|---|
| jsonrpc | near/query | `POST {method:"query",params:["addr"]}` | `params:{request_type,finality,account_id}` dict | near 用 dict 参数, jsonrpc.py 只产 list |
| jsonrpc | near/gas_price | `params:["addr"]` | `params:[null]` | 无 [null] 分支 |
| jsonrpc | near/block | `params:["addr"]` | `params:{finality:"final"}` dict | 同 dict |
| jsonrpc | near/tx | `params:["addr"]` | `params:[tx_hash, signer_id]` | 双参数, 单 address 槽塞不下 |
| jsonrpc | tron//wallet/* (3个) | `POST / {jsonrpc,method:"/wallet/getaccount",params:["addr"]}` | `POST /wallet/getaccount {address,visible}` HTTP REST | tron /wallet/* 是 REST POST 对象 body, 非 jsonrpc envelope |
| jsonrpc | avalanche-x/avm.getBlockByHeight,getTx,getUTXOs (3个) | `params:["addr"]` | `params:{height,encoding}` / `{txID,encoding}` / `{addresses,limit,encoding}` dict | avm.* 用 dict 参数 |
| **tendermint** | **全 5 链 25 method** | `POST / {jsonrpc,method:"GET /cosmos/...",params:{address}}` | LCD REST `GET /cosmos/bank/v1beta1/balances/{addr}` | **tendermint.py 假设 POST jsonrpc dict, 但实测链全是 Cosmos LCD REST GET path** — adapter 实现的协议 ≠ chain template 配置的协议 |

协议级错配合计: jsonrpc 9 + tendermint 25 = **34 method 现状构造的请求节点无法识别**。

### 2.2 参数不完整(⚠️ 中等, 请求语法合法但缺参/类型错, 拿 null 或非预期响应)

| 链/method | adapter 构造 | 正确 | 问题 |
|---|---|---|---|
| kusama/chain_getBlockHash | `["addr字符串"]` | `[1000000]` int | 类型(地址串当 block number) |
| bitcoin/getrawtransaction | `["addr"]` | `["txid", true]` | 缺 verbose 第二参(返 hex 不返对象) |
| bitcoin/getblock | `["addr"]` | `["blockhash"]`(可选 verbosity) | 结构基本对, 缺可选 verbosity |
| bitcoin/estimatesmartfee | `["addr"]` | `[6]` int conf_target | 类型(地址串当 conf_target) |
| jsonrpc transaction_hash/block_number_int/eth_call_object_latest | 占位符兜底(0x000.. / int(addr) fallback 1 / data写死balanceOf) | 真 tx_hash/真 block/真 call data | jsonrpc.py L79-95 实证: 多参数靠占位, 压测发合法请求但节点返 null = 非真实业务负载 |

### 2.3 误报澄清(grep 显示"无分支"但机制正常, 非债)

- **rest family 27 项**: rest 不用 param_format, 用 `_meta.rest_paths[method]` 字典(rest.py L62-79 实证), 26 项 rest_paths 齐全 = 机制正常。仅 tezos/operations/{vp} 1 项 rest_paths 缺(真小缺口)。
- **hedera_dual 5 项**: 委派 rest + jsonrpc 子 adapter(hedera_dual.py L86-101), rest_paths + json_rpc_url 齐 = 正常。
- **substrate/bitcoin/tendermint 的 no_params/single_address**: `in ("no_params","")` 语法, default 兜底也合理(如 substrate no_params→[]), 这些是对的。

## 3. 债务根因(一句话)

现状 = **6 family 各自硬编码 param_format 枚举 + 单 address 槽 + default 兜底**。当 method 的真实参数形态(dict / 多参数 / REST body / 特定类型)不在该 family 的有限枚举内 → default 静默产错请求。**tendermint 更严重 = 整个 adapter 假设的协议(POST jsonrpc)与实测配置(LCD REST)不符**。这正是任务北极星(声明式 DSL 让任意 method 零代码)要根治的, 也是 research R1/R2/R3 的真实爆发。

## 4. 重构方案(不留债 + 调用链不断 + 向后兼容)

### 4.1 核心思路: 用 §4 参数 DSL 替换 param_format 枚举, 单 address 槽升级为多 source 槽

- chain template 新增 `param_spec.<method>`(§4 设计: transport × slot/field × source), 声明式描述参数。
- adapter `_build_params` 改为: **优先读 param_spec(DSL), 无 param_spec 时 fallback 现有 param_format 枚举**(向后兼容 36 链现状)。
- 接口扩展: build_vegeta_target 的单 address 升级为可注入多业务值(block/tx_hash/call_data), 但**保持 address 参数向后兼容**(DSL 未声明时行为不变)。

### 4.2 必须保的调用链不断裂点(parallel-entry-trap 防护)

| 环节 | 改什么 | 不能断什么 |
|---|---|---|
| cli.py _get_param_format | 增 _get_param_spec 读 param_spec; 无则回退 param_format | 现有 param_format 路径必须保留(36 链在用) |
| cli.py build_targets_batch | 传 param_spec 给 adapter | TSV(method\taddress)契约不变(target_generator 不改) |
| adapter build_vegeta_target | 增 param_spec 分支 | 现有 param_format 分支保留; 接口签名向后兼容(加可选参数) |
| target_generator.sh | **不改**(只传 method+address, DSL 在 adapter 层解析) | round-robin / TSV 管道契约 |
| proxy / per_method_attribution | **不改**(只看 method 名 + status + latency) | NS-2 归因不受参数构造影响 |

### 4.3 落地顺序(按 family 风险倒序 + 每 family L3 验证)

1. **先修协议错配真债**(tendermint 25 + near/tron/avax 9)—— 这些现状就是坏的, 优先级最高。
2. tendermint: adapter 需支持 LCD REST GET path 模式(可借 rest family 机制, 或 param_spec transport=rest_path)。
3. jsonrpc: 加 dict 参数支持(near/avm)+ REST body 支持(tron)+ 多参数槽(near/tx)。
4. substrate/bitcoin: 补类型(int)+ 可选第二参。
5. 每 family 改完跑: L1 单测(test_chain_adapters.py R0)+ L2 cli.py build-targets-batch 真构造对比 §3 实测 + L3 真机 --fake-node 端到端出 targets + 真压测验证。

### 4.4 向后兼容验证(改前必须能回答)
- 现有 36 链不配 param_spec → 行为与现在完全一致(param_format 枚举路径保留)。
- 配了 param_spec 的 method → 按 DSL 构造, 与 §3 实测正确请求 byte 一致。
- R2/R3 校验: 启动期校验 param_spec/param_format 声明完整性, fail-fast(可选, 防静默错)。

## 5. 给用户的结论

1. **重构有真价值, 不是为抽象而抽象**: 当前 adapter 有 **34 个 method 协议级构造错 + 若干参数不完整**(token-level 实测确认, 非推断), 这是已存在的真债, 也正是"用户配新 method 会崩"担心的根源。
2. **DSL 不是新增负担, 是根治**: 把硬编码 param_format 升级成声明式 param_spec, 既修现有债, 又实现"零代码加 method"北极星。
3. **不留债 + 链不断的保证**: 重构在现有 adapter 上渐进改(W-4), param_spec 与 param_format 并存(向后兼容), target_generator/proxy/归因层不动, 每 family L1+L2+L3 三层验证。
4. **范围决策点(待用户拍板)**: (a) 是否先单独修 34 个协议错配真债(不引入 DSL, 快速止血), 再做 DSL 抽象?还是 (b) 直接用 DSL 一次性既修债又抽象?我倾向 (b)——因为这些债的根因就是"无声明式参数能力", 单独修等于再写一遍硬编码, DSL 落地时又要重改。但 (b) 工作量大、风险高, 需分 family 严格 L3。
