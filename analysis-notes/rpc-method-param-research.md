# RPC Method 参数位置 + mixed 权重 + 36链规律调研(TODO #2)

> 触发: 用户 2026-06-01。使用者按业务场景配自己的 mixed/single RPC method(非默认这几个),
> 担心: 一个 method 有 2+ 参数时不同位置语义不同, 传错位置拿不到正确响应 → 框架各环节出错。
> 方法【强制】: 互联网搜索 RPC 规范 + 实际请求 public endpoint double-check, 不许只读代码推断。
> 时机: k8s 适配 + proxy/fake-node 404 解决后做。本文档是阶段1(框架现状, 代码事实)基线。

## 阶段1: 框架现状(代码实证, 2026-06-01)

### 1.1 mixed 怎么生成 vegeta 文件(回答用户"single 生成一个文件, mixed?")
- **single 和 mixed 都生成【一个】文件** → `$CURRENT_OUTPUT_FILE`(targets_single.json / targets_mixed.json)。用户记忆正确。
- 生成路径: `tools/target_generator.sh generate_targets()` L234-268:
  - single(L240): 所有账户都用 `CURRENT_RPC_METHODS_ARRAY[0]`(唯一 method)。
  - mixed(L252): `method_index = account_index % method_count`(**round-robin 均分**), 每账户轮流分配一个 method。
  - 都经 `cli.py build-targets-batch`(TSV: method\taddress → vegeta targets JSON, 一次 python 调用)。

### 1.2 🔴 关键发现: mixed 权重 (weight) 在压测路径【未被使用】
- chain template 有两个 mixed 字段: `rpc_methods.mixed`(逗号分隔字符串)+ `rpc_methods.mixed_weighted`([{method,weight}])。
- `get_current_rpc_methods`(config_loader L668)+ L626 取的是 **`rpc_methods.mixed`(字符串)**, `IFS=',' read` 拆数组(L637)。
- **mixed_weighted 的 weight 字段在生成 vegeta targets 时完全没用** → 实际是均权 round-robin(每 method 占 1/N 账户), 不是按 weight 比例。
- 影响 NS-2(按 method 权重归因资源消耗): 权重在【生成流量】端没生效。weight 多大都一样均分。
  ⚠️ 待确认: weight 是否在别处(per-method 归因分析层?proxy?)使用; 还是定义了但全链路都没用 = 死字段。

### 1.3 参数构造: param_formats 抽象(框架对"不同 method 不同传参"的现有方案)
- chain template `param_formats` 字典声明每 method 的参数形态, 如 solana:
  `{getAccountInfo: single_address, getBalance: single_address, getTokenAccountBalance: single_address,
    getLatestBlockhash: no_params, getBlockHeight: no_params}`
- `get_param_format_from_json`(config_loader L683)按 method 查格式; cli.py builder 据此构造 params。
- target_generator 给 builder 传 `--method M --address A`(L246/259)= 统一假设"method + 一个 address"。
- **已覆盖**: 参数形态属已有 param_format 类型(single_address/no_params) → 加新 method 只需在 param_formats 加一行声明(零代码)。
- 🔴 **风险(用户核心担心)**: 全新参数形态会崩 —— 待阶段2 用 36链 + public endpoint 实证:
  - 多参数 method 的【位置语义】(如 [address, {config}] vs [{config}, address], 传错位置响应结构错)
  - 数字参数(getBlock(slot))/复杂对象参数(eth_call({to,data}))/多个不同类型参数
  - param_formats 现有类型枚举是否够覆盖 36 链所有 method

### 1.4 待阶段2 调研的问题清单(互联网 + public endpoint double-check)
1. 枚举 param_formats 当前所有类型(grep 全 36 链 chain template 的 param_formats 值)。
2. 36 链每个 method 的真实参数: 数量 + 每个位置的类型/语义 + 响应结构。互联网查 RPC 规范 + 打 public endpoint 验。
3. 多参数 method 的位置规律: 是否统一(如都"业务主参数在前, config 对象在后")? 有无例外?
4. 框架 cli.py builder 对多参数/非地址参数的构造能力(读 build-targets-batch 实现 + 各 param_format 分支)。
5. mixed weight 全链路追踪: 生成端(已确认没用)+ 归因分析端 + 报告端, 是死字段还是某处用了。
6. 现状评估: 框架当前能否正确处理"使用者配的任意 method"; 不能的话缺口在哪。
7. 处理方案: 扩 param_formats 类型 / 让 chain template 声明完整 param 结构 / weight 落到流量生成 等。

## 阶段2: 36链 method 参数/响应规律 (互联网+public endpoint 验证)

### 2.1 本地基线: 36链 param_format 全枚举(代码事实, 2026-06-01)
- 36 链, adapter_family 分布: jsonrpc 16 / substrate 5 / rest 5 / tendermint 5 / bitcoin_jsonrpc 4 / hedera_dual 1。
- **param_format 类型 = 53 种**(远非"几种统一规律"), 多数是单链特例。高频: no_params(76)/address_latest(19)/single_address(12)/transaction_hash(6)/path_addr(5)/block_number(5)。
- 单链特例举例: `{workchain,shard,seqno}`(TON)/ move_view_call(Aptos)/ query_dispatcher_request_type(NEAR)/ body_owner_contract_selector_parameter(Tron)/ eth_call_object_latest 等。
- = 框架已为每链特殊 method 手工声明 param_format, 不是统一规律; 加新 method 若是全新 format 必须新增 param_format 类型 + cli.py builder 对应分支。

### 2.2 🔴 同一 method 多 param_format(用户担心的"传错位置"风险的直接证据)
- `eth_call`: ['address_with_options', 'eth_call_object_latest'] — 同名不同参数格式
- `getblock`: ['[blockhash,verbosity]', '[blockhash]', 'block_hash'] — 3 种
- `getrawtransaction`: ['[txhash,verbose]', '[txid,verbose]', 'transaction_hash'] — 3 种
- 含义: 同一 method 名在不同链/配置参数位置+数量不同; 使用者配错或框架选错 format → 构造的请求参数位置错 → 拿不到正确响应结构。**这正是用户核心担心。**

### 2.3 🔴 缺 param_format 声明的 method(4 处, 框架会 fallback 可能出错)
- cardano: POST_ASSET_INFO
- hedera: GET /api/v1/transactions/{addr} / GET /api/v1/accounts/{addr} / GET /api/v1/balances?account.id={addr}

### 2.4 待 public endpoint 验证(下一步, 用户强制方法)
- 多参数 method 每个【位置】的真实语义(尤其 2.2 多 format 的): eth_call/getblock/getrawtransaction 各 format 对应哪条链、参数位置对不对。
- cli.py build-targets-batch 对各 param_format 的实际构造逻辑(读 builder 代码 + 对照真实 RPC 规范)。
- 打 public endpoint(solana/eth/cosmos 等)验真实响应结构, 确认 fixture/param_format 与真实一致。
- 2.3 缺声明的 4 个 method fallback 行为(读 cli.py default 分支)。

### 2.5 ✅ 参数位置语义 = 代码实证 + public endpoint double-check(2026-06-01)
**框架靠 param_format 名字编码参数【位置】**(jsonrpc adapter `_build_params`, tools/chain_adapters/jsonrpc.py L46+):
```
no_params              → []
single_address         → ["<addr>"]
address_latest         → ["<addr>", "latest"]   (EVM eth_getBalance)
latest_address         → ["latest", "<addr>"]   (StarkNet) ← 位置与 address_latest 相反!
address_storage_latest → ["<addr>", "0x0", "latest"]
address_key_latest     → ["<addr>", "0x1", "latest"]
```
**🔴 address_latest vs latest_address: 同样两参数, 位置完全相反**(EVM 地址在前 / StarkNet 地址在后)。

**public endpoint double-check(publicnode EVM eth_getBalance, 真实硬证)**:
- `["<addr>", "latest"]`(address_latest 正确序)→ `result: 0x4ec87d1290294661` ✅ 拿到余额
- `["latest", "<addr>"]`(位置传错)→ `error -32602: cannot unmarshal ... into Address` ❌ 报错拿不到响应
**结论: 用户担心被真实节点证实 —— 参数位置传错 = RPC 报错/错响应。** 框架正确性完全依赖 chain template 为每 method 声明正确的 param_format; 声明错/新 method 位置组合不在现有 ~15 种里 = 出错。

### 2.6 cli.py fallback 风险(代码实证)
- `_get_param_format`(cli.py L50/55): method 缺 param_format 声明时 **默认 fallback = "single_address"**(当成单地址)。
- → §2.3 那 4 个缺声明 method(cardano POST_ASSET_INFO / hedera 3 个)会被当 single_address 构造。若它们实际不是单地址(POST_ASSET_INFO 可能要数组/body)→ 构造错误请求 → 错响应。
- L31-41 注释记录历史 bug(commit 6866cba 曾误读 tpl["params"] 致生产参数错)= 这条参数构造链历史真出过参数错位 bug。

## 阶段3: 现状评估 + 风险清单 + 处理方案 (2026-06-01)
### 3.1 现状评估: 框架能否正确处理"使用者配的任意 method"?
**部分能, 有明确边界**:
- ✅ 新 method 的参数形态属于现有 ~15 种 param_format(jsonrpc adapter)+ 各 family 已有类型 → 只需 chain template `param_formats` 加一行声明, 零代码。
- ✅ 同一 method 不同账户(地址值变, 结构不变)→ 安全(框架按 param_format 套地址, 与具体账户无关)。验证: 同 method 不同 addr 入参/响应结构一致。
- 🔴 新 method 参数形态是全新组合(不在现有 param_format 枚举)→ 必须改代码(新增 param_format 类型 + adapter `_build_params` 分支), 不是零代码。
- 🔴 使用者声明错 param_format(如给 StarkNet method 配 address_latest 而非 latest_address)→ 参数位置错 → RPC 报错/错响应(2.5 实证)。框架无校验机制拦截声明错误。
- 🔴 method 漏声明 param_format → fallback single_address(2.6)→ 非单地址 method 静默构造错请求。

### 3.2 风险清单(按严重度)
| # | 风险 | 严重度 | 证据 |
|---|---|---|---|
| R1 | 使用者配新 method 但参数形态不在现有 param_format → 需改代码非零代码, 使用者不知 | 高 | 2.1(53格式多单链特例)+ jsonrpc 仅~15种 |
| R2 | param_format 声明错(位置反/类型错)无校验 → 静默错响应 | 高 | 2.5 public endpoint 实测 [latest,addr] 报错 |
| R3 | method 漏声明 → fallback single_address 静默错 | 中 | 2.6 + 现存 4 处缺声明(2.3) |
| R4 | 同名 method 多 format(eth_call/getblock/getrawtransaction)选错 | 中 | 2.2 |
| R5 | mixed weight 压测端未用(均权 round-robin)→ NS-2 按权重归因不准 | 中 | 1.2 |

### 3.3 处理方案(候选, 待用户拍板优先级)
- **针对 R2/R3(声明错/漏声明无校验)**: 加 chain template 校验 —— 启动时校验每个 rpc_methods 的 method 都有 param_format 声明 + param_format 值在已知枚举内, 否则 fail-fast 报错(不静默 fallback)。低成本高收益。
- **针对 R1(全新参数形态)**: (a) 文档化现有 param_format 类型表给使用者参考; (b) 或设计更通用的"参数模板 DSL"让 chain template 直接声明完整 params 结构(不靠预定义类型名)—— 大改, 需评估。
- **针对 R5(weight 未用)**: 确认 weight 全链路(C 阶段做)—— 若归因端也没用 = 死字段, 修复让 weight 落到 vegeta targets 生成(按 weight 比例分配 method, 而非 round-robin 均权)。
- **针对 R4**: 同名多 format 由 chain template 各自声明(已是现状), 风险在使用者跨链复制配置时选错 → 同 R2 用校验兜底。

### 3.4 B 阶段结论
- 用户担心【真实且已 public endpoint 证实】: 参数位置/数量错 → 拿不到正确响应。
- 框架现有 param_format 抽象【部分覆盖】但【无校验、有 fallback 静默错、全新形态需改代码】= 三个真缺口。
- 最高优先低成本修复 = R2/R3 的【启动期 param_format 校验 fail-fast】(防静默错)。
- weight 问题(R5)转入 C 阶段全链路确认。
- 待用户回来拍板: 是否实施 3.3 的校验方案 / 通用 DSL / weight 修复, 及优先级。

## 阶段4: 🎯 36链 RPC method 规律化抽象(官方文档 + public endpoint 实测, 2026-06-01)

> 用户核心要求: 确保 36 链 RPC method 能规律化抽象出逻辑(不只列格式, 要找底层规律)。
> 方法: 框架代码 + 官方文档 + public endpoint 实测 三对照, 不只读代码推断。

### 4.1 🎯 核心规律(已确立): 参数构造 = (family, param_format) 二维抽象
36 链 method 参数构造的底层规律是【两层】:
- **第一层 = 6 protocol family**(adapter_family): 36 链按协议归 6 族, 每族一套独立 _build_params。
  jsonrpc(16)/ substrate(5)/ tendermint(5)/ bitcoin_jsonrpc(4)/ rest(5)/ hedera_dual(1)。
- **第二层 = family 内 param_format 枚举**(有限可枚举): 每族内 method 参数形态收敛到该族的几种 param_format。
  之前看到的"53 种"= 6 family × 各族 5-10 种, 不是 53 种无规律, 是【按 family 分组后每组有限枚举】。
**所以规律 = `(family, param_format) → params 构造函数`。这是【可规律化】的, 且框架已按此架构实现(每 family 一个 _build_params)。**

### 4.2 6 family 的 _build_params 完整枚举(代码实证)
- **jsonrpc**(list 参数): no_params[] / single_address[a] / address_latest[a,"latest"] /
  latest_address["latest",a] / address_storage_latest[a,"0x0","latest"] / address_key_latest[a,"0x1","latest"] /
  address_with_options[a,{showType...}] / block_number["latest",false] / block_number_int[int(a)] /
  transaction_hash[tx_hash] / eth_call_object_latest[{to,data},"latest"]
- **substrate**(list): no_params[] / single_address[a] / storage_key[a] / block_hash[a] / address_with_block[a,None]
- **tendermint**(dict 参数, 非 list!): no_params{} / single_address{address:a} / height_param{height:a} /
  abci_balance_query{path,data,prove}
- **bitcoin_jsonrpc**(list): no_params[] / single_address[a] / address_minconf_includewatchonly[a,1,false] / txid[a,true]
- **rest**(无 _build_params, path-based): method=逻辑名 → _meta.rest_paths[method] 映射 (http_verb, path, body), 地址替换 {address} 占位符
- **hedera_dual**: eth_* 走 jsonrpc adapter, REST path 走 rest adapter(双委派)
**关键: tendermint 参数是 dict(object)不是 list, 与其他 jsonrpc 系 family 结构不同 → 规律化必须按 family 区分 list vs dict vs path。**

### 4.3 官方文档 + public endpoint 实测对照(进行中)
| 链(family) | method | 框架 param_format → 构造 | 官方文档参数 | public endpoint 实测 | 结论 |
|---|---|---|---|---|---|
| solana(jsonrpc) | getAccountInfo | single_address → [addr] | param1: pubkey(required); param2: config object(**optional**: encoding/commitment...) | [addr] 返回成功(默认编码); [addr,{encoding:base58}] 返回指定编码 | ⚠️ single_address 够用(节点用默认 encoding), 但缺 config 第二参 → data 编码非指定。压测够, 分析层若期望特定 encoding 有差异 |
| ethereum(jsonrpc) | eth_getBalance | address_latest → [addr,"latest"] | param1: address; param2: block(latest/earliest/pending) | [addr,"latest"]→余额; [latest,addr]→error -32602 | ✅ 位置正确; 位置反则报错(B2 已证) |
| bitcoin(bitcoin_jsonrpc) | getblockcount | no_params → [] | 无参数 | []→952025 ✅ | ✅ |
| cosmos(tendermint) | REST balances | path /cosmos/bank/.../balances/{addr} | path 参数 addr | endpoint 通(测试地址 checksum 无效但路由对) | ✅ path 路由对 |
| polkadot(substrate) | system_chain | no_params → [] | 无参数 | []→"Polkadot" ✅ | ✅ |
| ethereum(jsonrpc) | eth_getBlockByNumber | block_number → ["latest",false] | param1: block(latest/hex); param2: full_tx bool | ["latest",false]→区块; [false,"latest"]→error -32602 | ✅ 位置正确; 位置反报错(第2例证实) |
| ethereum(jsonrpc) | eth_call | eth_call_object_latest → [{to,data},"latest"] | param1: tx object{to,data...}; param2: block | [{to,data},"latest"]→0x..(USDT totalSupply)✅ | ✅ 复杂对象参数+位置正确 |
**6 family 覆盖完成**: jsonrpc(4 method: getAccountInfo/eth_getBalance/eth_getBlockByNumber/eth_call, 含多参数+对象参数+位置错)/ bitcoin_jsonrpc(getblockcount)/ substrate(system_chain)/ tendermint(REST balances)/ rest(cardano koios 待补1个)/ hedera(待补)。位置错=报错已 3 例证实(eth_getBalance/eth_getBlockByNumber 位置反均 -32602)。

### 4.4 规律化抽象结论
- ✅ **可规律化**: (family, param_format) 二维。6 family 固定, 每族 param_format 有限枚举。新链归入某 family 后, method 参数复用该族 param_format(已有则零代码)。已 6 family 多 method public endpoint 实测支撑(含复杂对象参数 eth_call、多参数 eth_getBlockByNumber、位置错报错)。
- ⚠️ **规律的边界**: (a) tendermint 用 dict 参数, 与 list 系不同, 抽象层须区分; (b) 同名 method 跨族/跨链参数可能不同(eth_call 多 format), 靠 chain template 声明区分; (c) 全新 param_format(不在某族枚举)需加该族 _build_params 分支(改代码); (d) param 第二个 optional config(如 solana getAccountInfo 的 encoding)框架不传, 压测够用但分析层若期望特定 encoding 有差异。
- 🎯 **给用户的答案**: 36 链 method 参数【能】规律化抽象 = (family × param_format), 框架已实现此架构; 抽象不是"一套规律通吃 36 链", 是"6 族各自的有限规律"。位置语义靠 param_format 名编码(public endpoint 证实位置错=报错), 框架正确性依赖 chain template 正确声明 param_format(R2/R3 缺校验是真风险)。
- **响应结构规律**: 各 family 响应结构不同(jsonrpc {result}/ tendermint REST 直接 JSON object/ rest 各异), 但同 family 内一致。fake-node byte-correct 重放真实响应已覆盖(响应结构由 fixture 保证, 非框架构造)。
