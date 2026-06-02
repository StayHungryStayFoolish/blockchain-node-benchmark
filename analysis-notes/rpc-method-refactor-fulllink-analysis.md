# RPC method 重构 — 全链路深度分析 + 重构设计(token-level 精读, 2026-06-02 第三轮扩大)

> 用户要求: 加载全 skill+memory+沉淀文档, token-level 精读, 批判性思维, **从框架入口**分析
> 36 链模板如何解析、每个 method 如何使用、参数如何构造、响应结构在开关打开时如何使用、
> 重构后如何按 method 传参 + 响应结构如何对应 method 请求。本文档是比前两轮(callchain-analysis)
> 更全面的版本, 替代之前零散分析。

## 0. 框架完整数据流(从入口 token-level 实证, 每环 file:line)

```
blockchain_node_benchmark.sh main()  L1080+
  │ 解析 --single/--mixed → RPC_MODE (L914-920, export 给子进程)
  ▼
Phase 0.5 (L1095): start_rpc_proxy (PROXY_ENABLED 时, 必须先于 Phase 1 —
  │   否则 targets 把 LOCAL_RPC_URL=8899 固化, vegeta 绕过 proxy, P0-3 修复)
  ▼
Phase 1: prepare_benchmark_data()  L131
  │ ① fetch_active_accounts.py (L138, 仅传 --output/--count/--verbose,
  │    靠 CHAIN_CONFIG env 知道抓哪条链 — config_loader 注入)
  │    → 产出 ACCOUNTS_OUTPUT_FILE (纯 account 地址, 一行一个, L817-819)
  │ ② target_generator.sh (L161) 读 accounts → cli.py build-targets-batch
  │    → 产出 vegeta targets JSON (SINGLE/MIXED_METHOD_TARGETS_FILE)
  ▼
Phase 2: start_monitoring_system (L188, unified_monitor 等, 常驻采资源时序)
  ▼
Phase 3: master_qps_executor.sh (L261, --$RPC_MODE)
  │ vegeta attack -rate=$qps -targets=file (L798) → [proxy →] 节点
  ▼
proxy sink CSV (9列 method 时序) + monitor CSV (资源时序)
  ▼
analysis/per_method_attribution.py (频次权重 join) → 图 → HTML
```

## 1. 🔴🔴 重大架构发现: 框架有【两套独立 adapter 体系】(批判性分析挖出, 前两轮文档未点破)

token-level 实证, 框架里"按链分派"的逻辑**实现了两次, 互不知道对方, 分类维度还不同**:

| 维度 | fetch 内部 adapter | tools/chain_adapters |
|---|---|---|
| 基类 | `BlockchainAdapter`(fetch_active_accounts.py:156) | `ChainAdapter` ABC(base.py:29) |
| 子类 | SolanaAdapter/EthereumAdapter/StarknetAdapter/SuiAdapter(**4 个**, L248/287/429/513) | jsonrpc/substrate/tendermint/bitcoin_jsonrpc/rest/hedera_dual(**6 family**) |
| 分派维度 | **chain_type**(create_adapter L661-674, 仅 8 链硬编码) | **adapter_family**(get_adapter, _meta.adapter_family) |
| 职责 | **取输入**(从节点抓 account 地址) | **构造请求**(把 method+address 拼 vegeta target) |
| 是否 import 对方 | 否(完全独立, fetch 不 import chain_adapters) | 否 |
| 覆盖 | 仅 8 链(4 adapter) | 36 链(6 family) |

**这是 parallel-entry-trap 的教科书案例**: 两套"按链分派"逻辑并存。后果:
- fetch 只支持 8 链取 account(其余 `raise ValueError` OQ-11), 但 chain_adapters 支持 36 链构造请求 →
  **28 链能构造 vegeta target 但 fetch 不出 account = 实际跑不起来**(这正是 README "8 链 e2e / 28 链 blocked on fetcher" 的根因)。
- 重构输入供给层时**必须决策: 统一两套 adapter, 还是明确边界各管一段**。

## 2. 每个 method 如何使用(36 链模板解析 → method 取值 → 参数构造)

### 2.1 chain template 如何被解析(三个消费者各读不同字段)
| 消费者 | 读 chain template 哪些字段 | 用途 |
|---|---|---|
| config_loader.sh | 全部(注入 CHAIN_CONFIG env + 设 BLOCKCHAIN_NODE) | 运行时配置 |
| fetch_active_accounts.py | `chain_type` / `rpc_url` / `methods`(get_signatures/get_transaction)/ `params` / `system_addresses` | 取 account |
| target_generator.sh + cli.py | `rpc_methods.single` / `rpc_methods.mixed` / `param_formats.<method>` | 构造 vegeta target |
| chain_adapters/<family>.py | `_meta.adapter_family` / `_meta.rest_paths` | 派发 + 参数构造 |
| proxy (Go) | `proxy_extraction.extractors[]` | 解析请求提 method 名 |

**关键: 同一 chain template 被 5 个消费者各读各的字段**, 没有单一"method spec"。重构要引入 param_spec 时,
必须确认它和这 5 个消费者的关系(尤其 proxy_extraction 已是 method 提取 DSL, param_spec 是 method 构造 DSL, 两者对称)。

### 2.2 method 如何取值(single vs mixed)
- single: `CURRENT_RPC_METHODS_ARRAY[0]`(target_generator L242), 所有 account 都用这一个 method。
- mixed: `account_index % method_count` round-robin(L260), 每 account 轮流分配一个 method。
  **mixed_weighted 的 weight 字段未用**(research R5, 用 rpc_methods.mixed 逗号串, 均权)。

### 2.3 参数如何构造(已在 callchain-analysis 详述, 此处汇总关键约束)
- 接口: `build_vegeta_target(method, address, rpc_url, param_format)` — **单 address 槽**。
- 6 family 三种容器: jsonrpc/substrate/bitcoin = list(`_build_params`) / tendermint = dict / rest = path(`rest_paths`)。
- 🔴 34 个 method 协议级错配(tendermint 25 + near/tron/avax 9, 见 callchain-analysis §2.1)。
- 🔴 ~45 个 method 需非 account 输入(tx_hash 17/block_id 17/contract_call 6/business 5), 框架无供给源(§3 输入供给)。

## 3. 输入供给层(account 顺手取 tx_hash/block_id 的真实可行性 + 落点)

### 3.1 fetch 已经手 tx_hash 只是丢弃(R-B 铁证, token-level)
- `fetch_all_signatures`(L677)取的 `sigs` = **transaction hash 列表**(L710 返回 signature)。
- main L802 `sigs = await fetch_all_signatures(...)` 拿到全部 tx hash。
- main L811 用 sigs 取 tx 详情 extract account, **L814-819 只写 account, sigs(tx hash)丢弃**。
- → **取 account 时 tx_hash 已在手**, 重构 = 额外保留 sigs 到 tx_hash 池文件, 几乎零新增节点请求。
- EthereumAdapter 还经手整个 block(L378 getBlockByNumber)→ block_hash/block_number 也已在手。

### 3.2 输入池设计(重构落点)
fetch 输出从单一 accounts.txt 扩展为多输入池(按 method 输入需求分类, §0 数据流的 Phase 1 产出):
```
ACCOUNTS_OUTPUT_FILE        account 地址(现状, 保留)
+ tx_hash_pool.txt          tx hash(从 sigs 保留, fetch 已有)
+ block_id_pool.txt         block hash / number(从 EthereumAdapter block 遍历保留)
+ (contract_call/business_id 输入: 部分可硬编已知合约, 部分 chain template 声明)
```
target_generator 按 method 的输入需求类型(param_spec 声明)从对应池取值, 替代"所有 method 都喂 account"。

### 3.3 fake-node 路径(无真实节点时, 用 §3 fixture)
- fake-node 已入库 184 method fixture(commit 91f380b)。
- fake-node 路径下, 输入池可从 fixture 的 request 示例提取(`<method>.request.json` 里的真实参数), 或固定占位。
- 两路径共用 param_spec DSL, 只是输入池填充来源不同(真节点抓 vs fixture)。

## 4. 响应结构在配置开关打开时如何使用(用户重点问的, token-level 厘清)

### 4.1 现状: 压测主路径不使用响应结构(§5.0 已确认)
- proxy 不缓冲响应 body(handler.go:103), per-method 归因只用 method/status/latency。
- parse_block_height 只用于 health check(cli.py:126), 不在压测热路径。
- → **响应结构当前在压测时不被使用**。

### 4.2 重构后: 响应结构在【PROXY_RESPONSE_CAPTURE 开关打开时】如何对应 method 请求
这是用户问的核心。设计:
- 开关 off(默认): 行为不变, 不记录响应, 零开销。
- 开关 on: proxy tee 响应 body → 独立 sink, **按 request_id 关联请求(method)和响应**。
  proxy sink 9 列已有 `request_id`(sink.go:41), 响应记录文件用同一 request_id 关联 →
  **响应结构天然对应 method 请求**(via request_id, 不需额外映射)。
- 响应记录后的用途: (a) 喂响应 DSL(§5)提取语义字段验证; (b) 转 fake-node fixture; (c) 调试/验证节点返回正确性。
- **关键: request_id 是 method 请求 ↔ 响应结构的关联键**(proxy 已有, 重构复用), 这解决了用户"响应结构如何对应 method 请求"的疑问。

### 4.3 响应结构对应 method 的两层关系(重构后完整图)
```
请求构造端:  param_spec[method] → 构造请求(transport/slot/source) → vegeta target
                                          │ request_id
压测执行端:  vegeta → proxy(记 request_id, method, status, latency)→ 节点
                                          │ request_id (开关 on 时)
响应记录端:  proxy tee 响应 body → response_sink[request_id] = 响应结构
                                          │
响应解析端:  response_spec[method] → 从响应结构提取语义字段(block_height/balance/...)
```
method 请求 ↔ 响应结构的对应 = **param_spec(构造) + request_id(关联) + response_spec(解析)** 三段式。

## 5. 重构设计(三阶段, 基于以上全链路事实)

### 阶段 1: 输入供给层(前置地基, 解决两套 adapter + 输入池)
- 1a. **统一/明确两套 adapter 边界**(§1): 决策点 — fetch 的 4 chain_type adapter 与 chain_adapters 6 family 是否合并。
  倾向: fetch 改为读 chain_adapters 的 family 分派(消除 OQ-11 8 链硬编码, fetch 支持 36 链取输入)。
- 1b. fetch 扩展产多输入池(tx_hash/block_id, 复用已经手数据 §3.1)。
- 1c. fake-node 路径用入库 fixture 的 request 示例填输入池。
- L3 验证: 真节点取 account+tx+block 三池 + fake-node 路径出 targets。

### 阶段 2: 参数构造 DSL(§4 param_spec)
- 2a. chain template 加 param_spec(transport×slot/field×source, source 从输入池取值)。
- 2b. 6 adapter `_build_params` 改为优先读 param_spec, fallback param_format(向后兼容)。
- 2c. cli.py 加 _get_param_spec + 启动期校验(R2/R3 fail-fast)。
- L3 验证: 每 family 配 param_spec 的 method 构造请求 byte 等于 §3 实测正确请求。

### 阶段 3: 协议错配修复 + 响应记录开关 + 响应 DSL
- 3a. 修 34 个协议错配(tendermint LCD REST / near dict / tron REST / avax dict)。
- 3b. PROXY_RESPONSE_CAPTURE 开关(§4.2, request_id 关联)。
- 3c. response_spec(§5)提取语义字段(开关 on / health check 用)。
- L3 验证: tendermint/near/tron/avax 真实请求节点返正常响应; 开关 on 记录响应且 request_id 对应正确。

### 跨阶段铁律(skill)
- 每阶段每 family L1+L2+L3(multi-stage-l3-mandatory)。
- target_generator round-robin / TSV 契约、proxy 9 列、归因层 — 不破坏(向后兼容)。
- 两套 adapter 边界决策(§1)是阶段 1 的核心岔路, 需用户拍板。

## 6. 待用户拍板的关键决策(本轮新增, 前文档未暴露)
1. **两套 adapter 体系(§1)**: 统一(fetch 改用 family 分派)还是保持两套明确边界? 这决定阶段 1 工作量和 OQ-11 是否一并解。
2. **输入池粒度**: tx_hash/block_id 池够不够? contract_call/business_id 输入怎么供给(硬编已知合约 vs chain template 声明)?
3. **mixed weight R5**: 是否本次一并修(round-robin → 按 weight 分配)?
4. 响应记录开关的响应文件是否也入库(像 fixture 一样)供离线分析?


## 7. 两套 adapter 整合方案(第四轮扩大: 使用点 + 时机 + 整合, token-level 实证)

### 7.1 两套 adapter 的全部使用点(grep 实证, 已锁定)
| | fetch 内部 adapter | chain_adapters |
|---|---|---|
| 唯一生产 caller | `fetch_active_accounts.py:782` create_adapter(自包含, 无外部 import) | `target_generator.sh:74/248/264` → `cli.py build-target(s-batch)` |
| 外部入口 | `blockchain_node_benchmark.sh:138`(子进程调整个脚本) | `target_generator.sh`(子进程调 cli.py) |
| **调用时机** | **Phase 1 第①步**(prepare_benchmark_data, 取 account) | **Phase 1 第②步**(account → 构造 vegeta target) |
| 测试 caller | 无独立单测 | `tests/test_chain_adapters.py` |

**时机关系**: 同一 Phase 1 流水线, fetch adapter(①取 account)→ chain_adapters(②account 构造 target), 上下游非竞争。

### 7.2 两套接口契约对比(精读实证)
| 维度 | fetch BlockchainAdapter (L156) | chain_adapters ChainAdapter (base.py:29) |
|---|---|---|
| 抽象方法 | `_single_request`(取 tx 列表)/ `fetch_transaction`(取 tx 详情)/ `extract_accounts_from_transaction` | `build_vegeta_target` / `health_check_request` / `parse_block_height` |
| 同步性 | **async**(aiohttp 网络 I/O) | **sync**(纯字符串构造) |
| 状态 | 有(session 复用 + 分页 cursor + seen_digests) | 无状态 |
| 职责 | **抓输入**(从节点取 account/tx/block/logs) | **构造请求 + 解析响应** |
| 分派维度 | **chain_type**(create_adapter 4 类: solana/ethereum系/starknet/sui, 仅 8 链) | **adapter_family**(get_adapter 6 family, 36 链) |
| 数据 | EthereumAdapter 已经手 block_number(L313/347)/tx_hash(L335)/logs | — |

### 7.3 🎯 整合方案: 不合并成一个类, 而是"统一分派维度 + 分层各管一职"(不留债 + 优雅)

**批判性结论: 两套 adapter 职责真不同(async 抓数据 vs sync 构造请求), 强行合并成一个类 = 违反单一职责 + async/sync 混杂, 反而留债。** 优雅整合 = **统一分派维度(都按 family)+ 保持职责分层**:

```
统一后的 adapter 体系(单一分派, 双层职责):
  get_adapter(chain) [按 _meta.adapter_family 单一分派, 36链]
       │
       ├─ InputProvider 层 (async, 抓输入)        ← 整合自 fetch BlockchainAdapter
       │    fetch_accounts() / fetch_tx_hashes() / fetch_block_ids()
       │    按 family 实现(jsonrpc/substrate/.../hedera 各一套抓取逻辑)
       │
       └─ TargetBuilder 层 (sync, 构造请求 + 解析)  ← 现 chain_adapters ChainAdapter
            build_vegeta_target(param_spec) / parse_response(response_spec)
```

**核心改动**:
1. **消除 chain_type 分派**: fetch 的 create_adapter(4 类 chain_type)废弃, 改为 `get_adapter(chain).input_provider`
   按 adapter_family 分派(与 chain_adapters 统一到同一个 family 注册表)。一举解决 OQ-11(8 链硬编码)
   + 两套 adapter 分类冲突 + 28 链 blocked on fetcher。
2. **InputProvider 作为 family adapter 的一个 async mixin/子组件**: 每个 family adapter 除了现有 sync 的
   build_vegeta_target, 再实现 async 的 fetch_accounts/fetch_tx_hashes/fetch_block_ids(从 fetch 现有 4 个
   chain_type 实现迁移 + 补全到 6 family)。同一 family 下所有链共享抓取逻辑(jsonrpc 16 链一套)。
3. **单一注册表**: 两套合用 base.py 的 `@register(family)` + `_REGISTRY`, 一个 get_adapter 入口。
4. **职责分层不破坏**: async 抓取 与 sync 构造 仍是两个方法组(InputProvider / TargetBuilder), 只是挂在
   同一个 family adapter 类下, 不混成一个方法。fetch_active_accounts.py 改为薄 CLI wrapper 调
   get_adapter(chain).fetch_*(异步), 不再自带 4 个 adapter 类。

### 7.4 为什么这样不留债 + 优雅(对照备选)
| 方案 | 评价 |
|---|---|
| (a) 保持两套不动 | ❌ 留债: chain_type/family 双分派永久并存, OQ-11 不解, 28 链永远 blocked |
| (b) 强行合并成一个 adapter 类(一个方法既抓又构造) | ❌ 留债: async/sync 混杂, 单一职责破坏, 抓取(网络)和构造(纯函数)耦合难测 |
| **(c) 统一 family 分派 + InputProvider/TargetBuilder 分层(本方案)** | ✅ 单一分派消歧 + 职责清晰分层 + 一个注册表 + fetch 降为薄 wrapper + 解 OQ-11 + 解 28 链 blocked |

### 7.5 整合的调用时机(重构后, 不变 Phase 顺序)
```
Phase 1 ①: fetch_active_accounts.py(薄wrapper) → get_adapter(chain).fetch_accounts()/fetch_tx_hashes()/fetch_block_ids()
              → 产出 accounts.txt + tx_hash_pool.txt + block_id_pool.txt(InputProvider 层, async)
Phase 1 ②: target_generator.sh → cli.py → get_adapter(chain).build_vegeta_target(param_spec, 输入从对应池取)
              → vegeta targets(TargetBuilder 层, sync)
```
**Phase 顺序不变, target_generator/proxy/归因契约不变**(向后兼容); 只是两套 adapter 的"分派入口"统一成一个 get_adapter, fetch 不再自带独立 adapter 体系。

### 7.6 整合落地的验证点(防 parallel-entry 复发)
- L1: 6 family 各自 InputProvider 单测(fetch_accounts/tx_hashes/block_ids 返回正确类型)。
- L2: fetch_active_accounts.py 薄 wrapper 调 get_adapter().fetch_* 真出 3 个池文件。
- L3: 真节点跑 Phase 1 全链路(fetch 36 链任一 → 3 池 → target 构造 → 压测), 验"28 链不再 blocked"。
- 回归: 现有 8 链 fetch 行为 byte 等价(InputProvider 迁移自原 4 chain_type 实现, 逻辑不变)。
- 删除: create_adapter + 4 个 chain_type adapter 类删除后, grep 确认无残留 caller(Step 5 disable 验证)。


## 8. 构造 vegeta 文件的代码逻辑(第五轮: 有几套 + 构造↔识别闭环, 用户点的关键)

### 8.1 构造 vegeta target 的代码路径(grep 实证: 一套构造逻辑, 两个 CLI 入口)
| 路径 | 性质 |
|---|---|
| `chain_adapters/<family>.py build_vegeta_target` → `_vegeta_post_json`/`_vegeta_get`(base.py:67/78) | **唯一真实构造逻辑**, 6 family 全经此 |
| `cli.py cmd_build_targets_batch`(L80)← target_generator `generate_targets`(L248/264) | **生产入口**(批量 TSV) |
| `cli.py cmd_build_target`(L59)← target_generator `generate_rpc_json`(L66, 标注 "legacy callers/debugging") | legacy/debug 入口, 生产不用 |
| `framework_data_quality_checker.sh validate_vegeta_file`(L239) | **只校验不构造** |

**结论: 构造逻辑只有一套(build_vegeta_target), 但有 single/batch 两个 CLI 入口。** batch 是生产, single 是 legacy。
两入口走同一 build_vegeta_target → 行为一致(低风险), 但 legacy 入口是 parallel-entry 轻度嫌疑(若未来漂移)→
重构时建议 single 入口改为调 batch 的同一构造或直接删 legacy(消除潜在漂移)。

### 8.2 vegeta target 完整结构(base.py 实证)
```
POST family: {"method":"POST", "url":rpc_url, "header":{"Content-Type":["application/json"]}, "body":_b64('{"jsonrpc","method":"X","params":[...]}')}
GET  family: {"method":"GET",  "url":full_url_with_path, "header":{}}   ← 无 body, method 信息在 url path
```

### 8.3 🔴🔴 构造↔识别闭环(用户核心担心的根: "构造错→拿不到响应"的真因)
proxy 从请求识别 method 决定响应能否归到 method(token-level 实证):
| family | vegeta target 带 method 信息的方式 | proxy extractor 识别 method | 闭环条件 |
|---|---|---|---|
| jsonrpc/substrate/bitcoin/tendermint(POST) | **body 里 `{"method":"X"}`** | jsonrpc.go:49 读 `body.method`(method_source=body.method) | build 的 body.method 正确即闭环 |
| rest/tendermint(GET path)/hedera mirror | **URL path**(body 无 method 字段) | rest.go 匹配 `url_pattern`(method_source=url path) | 🔴 **build 构造的 path 必须能被 proxy_extraction 的 url_pattern 匹配** |
| tron(/wallet/* POST) | path + body | 取决于 proxy_extraction 配 jsonrpc/rest | 🔴 协议错配(§2.1)在此咬合 |

**核心洞察(用户点破的"顾此失彼"风险)**: 框架有【三处独立声明同一 method 的形态】, 必须三方对齐, 缺一则"前面通了但拿不到响应":
1. **构造端** param_spec / build_vegeta_target → 决定 vegeta target 的 url + body
2. **识别端** proxy_extraction(extractors[]: method_source / url_pattern)→ 决定 proxy 从请求提哪个 method 名
3. **解析端** response_spec → 决定从响应提语义字段

**漂移即断链**: 若 build 构造的 rest path = `/v2/accounts/{addr}` 但 proxy_extraction url_pattern = `^/v2/accounts/[^/]+$`(正则要匹配实际带值的 path)不一致 → proxy 识别不出 method → per-method CSV 该 method 缺失 → 响应(开关 on 时)也归不到正确 method。**这正是"构造对应 method 的 vegeta 文件"与"响应对应 method"必须同源的根因。**

### 8.4 重构必须保证的三端同源(不留债关键)
param_spec(构造)、proxy_extraction(识别)、response_spec(解析)**应从同一份 method 声明派生或强制一致性校验**:
- 方案: chain template 里 method 的 url/path 形态**单一权威声明**, param_spec 用它构造、proxy_extraction 用它生成识别 pattern、response_spec 挂同一 method key。
- 启动期校验: 对每个 method, 校验 build_vegeta_target 产出的 url/body 能被该链 proxy_extraction 的 extractor 匹配(构造↔识别闭环自检), 不匹配 fail-fast。
- 这是比单纯"param_spec 替换 param_format"更完整的目标: **三端同源 + 闭环自检**, 否则 §2.1 的 34 个协议错配修了构造端, proxy_extraction 端没同步改照样断链。

### 8.5 第五轮结论更新(回答用户"有几套构造逻辑")
- 构造 vegeta 文件逻辑 = **一套**(build_vegeta_target), single/batch 两入口(batch 生产 / single legacy 待清理)。
- 但 method 形态在框架里有**三处独立声明**(param_spec 构造 / proxy_extraction 识别 / response_spec 解析), 这三处不对齐 = "前面通了但拿不到响应"。重构必须三端同源 + 闭环校验。
- 验证补充(L3): 不只验"target 构造对", 还要验"proxy 能从该 target 识别出正确 method"(proxy_method.csv 出现该 method)+ "响应(开关on)按 request_id 归到该 method"。三端闭环都过才算该 method 重构完成。


## 9. 第六轮 token-level 逐行精读补充(自查: 前五轮混用 grep, 本轮补全跳过的关键代码)

### 9.0 自查: 前五轮哪些是 grep 推断而非 token-level 实证
诚实承认前五轮混用了 grep 锚定 + 部分精读, 以下结论是推断未逐行验证, 本轮补:
- "补全 InputProvider 到 6 family"= 推断(只读了 fetch 的 Solana/Ethereum, 没读 Starknet/Sui, 完全没读 substrate/tendermint/bitcoin/rest/hedera 该怎么抓)。
- proxy extractor 只 grep 关键行未读全文。
- config_loader 怎么注入 CHAIN_CONFIG / 设 BLOCKCHAIN_NODE 没读。

### 9.1 🔴 fetch 4 adapter 的 account 抓取逻辑逐行精读 — 差异巨大, "补全6family"是从零设计非简单补全
| adapter | 取 tx 列表的机制(_single_request) | 提 account(extract_accounts) |
|---|---|---|
| Solana(L251) | `getSignaturesForAddress`(config methods.get_signatures)→ signatures | tx.transaction.message.accountKeys → pubkey |
| Ethereum(L290) | 合约: `eth_getLogs`(methods.get_logs)取 transactionHash; EOA: 遍历 `eth_getBlockByNumber` 匹配 from/to | tx.from / tx.to |
| Starknet(L432) | `starknet_getEvents`(from_block/to_block/address/keys/chunk_size)→ event.transaction_hash | contract_address / sender_address / calldata 里的地址 |
| Sui(L516) | `suix_queryTransactionBlocks`(MoveFunction filter package/module/function)→ tx.digest | (后续行) |

**重大发现(token-level 才暴露)**: 4 个 family 的"取活跃账户"机制**完全不同**(getSignaturesForAddress / getLogs+遍历block / getEvents / queryTransactionBlocks), 不是同一套套模板。所以"补全到 6 family"的真实工作量 = **为 substrate/tendermint/bitcoin/rest/hedera 各设计一套全新的活跃账户抓取逻辑**:
- **bitcoin_jsonrpc**: UTXO 模型, **无 account 概念** → 要从 block 的 tx vout 提地址(scriptPubKey→address), 与 EVM/Solana 账户模型根本不同。
- **tendermint**: cosmos, 要查 tx events(/tx_search 或 LCD txs by events)提 sender/recipient。
- **substrate**: 要查 system events 或 block extrinsics 提 AccountId。
- **rest**(algorand/aptos/cardano/tezos/ton): 每链 REST API 取活跃账户方式各异(algorand indexer / cardano koios / ...)。
- **hedera**: mirror REST /accounts 或 /transactions 提 account。

**这是比"补全"严重得多的真实复杂度**: 5 个新 family 的 InputProvider 抓取逻辑要从零设计 + 各自 public endpoint 实测验证。这影响阶段 1 工作量评估(远大于"迁移现有 4 类")。

### 9.2 fetch 用的 method ≠ 压测的 method(token-level 新发现)
fetch 抓取用的 method(getSignaturesForAddress / eth_getLogs / eth_getBlockByNumber / starknet_getEvents / suix_queryTransactionBlocks)**不在压测的 rpc_methods 列表里** —— 它们是"取输入专用 method", 来自 config 的 `methods` 字段(get_signatures/get_transaction/get_logs), 与 `rpc_methods.single/mixed`(压测 method)是**两个不同的字段**。
- 含义: InputProvider(取输入)和 TargetBuilder(压测)用的 method 集不同, 整合时两个 method 来源都要保留(chain template 的 `methods` 取输入 + `rpc_methods` 压测)。
- 这修正了 §7.3 整合方案: InputProvider 层不只是"按 family 抓 account", 还要按 family 知道"用哪个 method 抓"(读 chain template methods 字段)。

### 9.3 待继续 token-level 精读(本轮 context 限制, 下轮补)
- config_loader.sh 怎么构造 CHAIN_CONFIG env + 设 BLOCKCHAIN_NODE(InputProvider 整合接口)。
- proxy extractor jsonrpc.go / rest.go 全文(三端同源的识别端细节)。
- Sui adapter L559+ 剩余 + replace_env_vars(params 占位符替换)。
- master_qps_executor 完整压测循环(rate 爬坡 + 多 QPS 档)。
- report_generator per_method section 完整渲染链(响应入库后如何用)。


## 10. 第六轮续 token-level 精读: config_loader + proxy extractor(整合接口 + 识别端闭环细节)

### 10.1 CHAIN_CONFIG 构造链(config_loader.sh 逐行精读)— 整合的真实接口障碍
- L597: `CHAIN_CONFIG=$(jq -c 'del(._meta)' "$chain_file")` —— **CHAIN_CONFIG = chain template 去掉 _meta**。
- 🔴 **整合障碍**: fetch 收到的 CHAIN_CONFIG **不含 _meta.adapter_family**(被 jq del 掉了)。fetch 现靠 `chain_type` 字段分派(create_adapter), 而 §7 整合方案要按 adapter_family 分派 → **必须改 config_loader 保留 _meta.adapter_family 进 CHAIN_CONFIG, 或 InputProvider 另读 chain 文件取 family**。这是阶段 1 整合的具体接口改动点(前几轮没发现)。
- L626: `CURRENT_RPC_METHODS_STRING = CHAIN_CONFIG | jq .rpc_methods.<mode>` → L637 IFS=',' split 成 ARRAY → 传 target_generator(round-robin 那段)。
- L674 get_current_rpc_methods 同样取 `rpc_methods.<mode>` 逗号串 —— **再次确认 mixed 取 rpc_methods.mixed 不是 mixed_weighted(R5 weight 未用), 三处代码一致(L540/626/674)**。
- L454 MAINNET_RPC_URL 8 链 case 硬编码(OQ-11 的 config_loader 半); L501 validate 已 discover from config/chains/*.json(模板驱动)→ 双重原则并存确认。

### 10.2 proxy jsonrpc extractor 逐行精读(jsonrpc.go)— 识别端闭环硬细节
- L53-59 Extract: 先 `req.Method==POST` + **`urlRegex.MatchString(req.URL.Path)`** 双校验, 任一不过 return false。
- 🔴 **关键闭环**: **即使 jsonrpc(读 body.method), 也先过 url_pattern 校验**(L57)。若 build_vegeta_target 构造的 url path 与 proxy_extraction 的 url_pattern(solana=`^/$`)不一致 → return false → method 提取失败 → per-method CSV 缺该 method。**三端同源(§8.3)连 jsonrpc 都适用, 不只 rest**。
- L82-90: body.method → MethodName; body.id → RequestID(stringifyID)。**RequestID = jsonrpc body 的 id 字段** = 响应关联键(§4.2)。
- 🔴 **新发现**: vegeta target 的 body 里 `"id":1`(base.py 所有 _vegeta_post_json 固定 id=1)→ **所有请求 RequestID 都是 "1"**! 若开关 on 记录响应按 request_id 关联, **同一压测所有请求 id 都是 1 → request_id 无法区分不同请求的响应**。这是响应入库(用户拍板要做)的真实障碍: 要么 build 时给每请求唯一 id, 要么响应关联改用别的键(时间戳+method)。**这是响应记录开关落地的关键坑, token-level 才挖出。**
- L93-125 batch: BatchSplit(默认)拆批每条一个 Result; BatchReject/BatchTag 两种其他策略。

### 10.3 第六轮新增的两个真实障碍(影响实施, 前几轮 grep 没发现)
1. **CHAIN_CONFIG 删 _meta** → 整合按 family 分派要先改 config_loader 保留 adapter_family(§10.1)。
2. **vegeta target 固定 id=1** → 响应入库按 request_id 关联失效, 需给每请求唯一 id 或改关联键(§10.2)。

### 10.4 仍待 token-level 精读(下轮)
- proxy rest.go extractor 全文(rest 识别端 url_pattern 匹配细节)。
- master_qps_executor 完整压测循环(rate 爬坡逻辑 + proxy 串联点)。
- report_generator _generate_per_method_section 完整渲染链(响应入库后如何被分析/出图用)。
- per_method_attribution.py 完整(频次权重 + 响应是否参与)。


## 11. 第七轮 token-level 精读: rest extractor + 压测循环 + report渲染链(响应入库闭环硬结论)

### 11.1 proxy rest.go 逐行精读 — RequestID 根本不设(响应入库障碍升级)
- L64-79 Extract: 遍历 patterns, 校 httpMethod(verb)+ regex.MatchString(path)→ 返 method_name。
- 🔴 **L74 `RequestID: ""`** —— rest 协议**根本不设 RequestID**(空)。比 jsonrpc 的 id=1 更严重:
  - jsonrpc/substrate/bitcoin/tendermint(POST): RequestID = body.id = **全是 "1"**(base.py 固定)→ 无法区分。
  - rest/tendermint(GET)/hedera mirror: RequestID = **""** → 根本没有关联键。
- **响应入库(用户拍板)的硬障碍坐实**: 当前 proxy RequestID 机制**完全无法支撑"响应结构对应 method 请求"**。
  必须重构: (a) build_vegeta_target 给每请求注入唯一 id(jsonrpc body.id 用递增/uuid; rest 加 query 参数或 header)+
  (b) proxy extractor 提取该唯一 id 作 RequestID + (c) 响应记录按该 id 关联。**三处都要改, 否则响应入库后对应不上 method。**

### 11.2 master_qps_executor 压测循环逐行精读 — 压测层完全不碰响应 body
- L798 vegeta attack -targets=file(url 决定打 proxy 还是节点, Phase0.5 固化)。
- L806-808 vegeta 输出 → `vegeta report -type=json` → result_file。
- L820-824 只从 vegeta report 提 requests/status_codes/latencies **聚合统计**(总数/状态码分布/延迟), **不碰单个响应 body**。
- **确认: 响应入库只能在 proxy 层做**(vegeta + master_qps_executor 都不接触响应 body)。

### 11.3 report_generator per_method 渲染链逐行精读 — 归因/出图完全不消费响应结构
- L4298 `read_proxy_csv` → 只读 proxy 9 列 CSV(method/status/latency), **不读响应内容**。
- L4301/4303 compute_per_method_qps/resource: 归因 = **proxy method 时序 + monitor 资源时序 join**, 响应 body 零参与。
- L4324-4327 write_qps/resource_csv: 产 per_method CSV(供外部)。
- 🔴 **确认: 现有 report/attribution 链完全不消费响应结构** → **响应入库后, 现有分析/出图链不会自动使用它**。

### 11.4 🎯 响应入库闭环硬结论(第七轮, 修正前几轮"响应喂 response DSL"的乐观说法)
响应入库要真正可用, 需新建一整条链(不是"记下来就行"):
1. **关联键重建**(§11.1): build 注入唯一 id + proxy 提取 + 响应按 id 关联 — 三处改, 否则响应对应不上 method。
2. **响应只能 proxy 层捕获**(§11.2): vegeta/executor 不碰 body, 开关 on 时 proxy tee。
3. **新建响应消费链**(§11.3): 现有 report/attribution 不读响应 → response_spec 提取 + 响应校验/分析是**全新增**, 现链不接。用途 = 调试/验证节点返回/录 fixture, 不是喂现有归因(归因不需要响应)。
4. **响应文件入库**(用户拍板): 按 (chain, method, 唯一id/timestamp) 组织, 像 fixture 一样入库。

### 11.5 七轮分析完整性自评(token-level 已覆盖的全链路)
逐行精读已覆盖: 入口Phase编排 / prepare_benchmark_data / fetch 4 adapter完整(Solana/Ethereum/Starknet/Sui)/
config_loader CHAIN_CONFIG构造+rpc_methods提取 / 6 family build_vegeta_target+_build_params / base.py vegeta构造 /
cli.py 两入口 / proxy jsonrpc+rest extractor全文 / master_qps_executor压测循环 / report per_method渲染链。
**剩 per_method_attribution.py 完整频次权重(已知核心逻辑, §11.3 确认不碰响应)+ fetch Sui尾部/replace_env_vars(占位符)未逐行。**

### 11.6 七轮累计挖出的、影响实施的真实障碍清单(grep 阶段全没有)
1. 两套 adapter 分派维度冲突(chain_type vs family)→ 整合方案 c(§7)
2. 6 family account 抓取从零设计(bitcoin UTXO 无 account 等)→ 阶段1 真实工作量(§9.1)
3. fetch method ≠ 压测 method(两个字段)→ InputProvider 要读 methods 字段(§9.2)
4. CHAIN_CONFIG 删 _meta → 整合按 family 要先改 config_loader(§10.1)
5. vegeta 固定 id=1 + rest RequestID="" → 响应入库关联键必须重建(§10.2 + §11.1)
6. 压测层/report 层都不消费响应 → 响应消费链全新增(§11.2/11.3)
7. 三端同源(param_spec/proxy_extraction/response_spec)连 jsonrpc 都依赖 url_pattern(§8.3/10.2)
8. mixed weight R5 三处代码确认未用(§10.1)


## 12. 第八轮 token-level 精读: attribution完整 + proxy handler + sink(归因维度缺口 + 响应入库精确落点)

### 12.1 per_method_attribution.py 完整逐行精读 — 🔴 归因只 CPU/MEM 两维, EBS/Net 缺失
- L13-16 归因公式: `weight = method_count/total_count`(实测频次); `cpu = total_cpu*weight`; `mem = total_mem*weight`。
- L62-68 **PerMethodResourceRow 只有 cpu_pct / mem_mb 两个资源字段** —— **没有 EBS/Network 的 per-method 归因**!
- L202-240 compute_per_method_resource: 只算 cpu_pct/mem_mb(L236-237)。
- 🔴🔴 **重大缺口(token-level 才发现)**: **NS-2 明写要归因 CPU/MEM/EBS/Network 四维, 但 attribution 实现只做了 CPU/MEM 两维**。EBS(磁盘 iops/throughput)和 Network 的 per-method 归因**完全没实现**。
  - 这是 NS-2 的真实未完成项(monitor CSV 有 EBS/Net 列, 但 attribution 没把它们按 method weight 分摊)。
  - 重构(用户要"更完善")应补全: PerMethodResourceRow 加 disk_iops/disk_throughput/net_rx/net_tx 等, compute 按同样 weight 分摊。
- L74-80 read_proxy_csv 跳过 `__unmatched__` —— 与 §12.3 handler 呼应。
- L226-227 缺监控数据的秒跳过(避免误报 0)。

### 12.2 归因不用 request_id 做关联(只用秒窗)
- L214-217 method_count 按 `timestamp_ns//1e9`(秒)聚合, **不用 request_id**。
- 含义: 归因层靠"秒级时间窗 + method 频次", request_id 对归因无用。request_id 只在"响应入库关联响应↔请求"时才需要(§11.1), 而那条链是全新增的。

### 12.3 proxy handler.go 完整精读 — 响应入库的精确代码落点
- L68-70 `statusRecorder` 包装 ResponseWriter, `rp.ServeHTTP(srw, r)` 把响应**流式写客户端**。
- L103-112 statusRecorder **只重写 WriteHeader 截 status code, 没重写 Write, body 直接经 embedded ResponseWriter 流走不缓冲**。
- L73 Extract 在转发后调用(提 method); L88-100 sink.Write 写 9 列记录(含 res.RequestID, §11 已证全 1/空)。
- L74-86 extractor 不匹配 → 写 `__unmatched__` 记录 → attribution(§12.1)跳过 → **该 method 静默从归因消失**(三端不同源的代价精确机制)。
- 🎯 **响应入库精确落点**: 给 statusRecorder **加 Write([]byte) 方法 tee**(开关 on 时同时写客户端 + 缓冲), ServeHTTP 末尾把缓冲的响应 body 写 response_sink, 用 request_id 关联(需先解 §11.1 唯一 id)。

### 12.4 proxy sink.go 完整精读 — 响应 sink 落点
- Record 9 字段(无 response body); Sink 接口 Write/Close; 三 format(csv/jsonl/discard, PROXY_SINK_FORMAT)。
- 🎯 **响应入库 sink 落点**: **新增独立 response_sink**(并列 fileSink, 写 proxy_responses.jsonl), **不扩 Record 9 列**(扩列污染主 CSV schema, 违 Q4-6 + csv-schema-decoupling 20 reader 连锁)。response_sink 也需 mutex 线程安全。

### 12.5 第八轮新增的真实发现
1. 🔴🔴 **per-method 归因只 CPU/MEM 两维, NS-2 要的 EBS/Network 缺失** — 重构要补全四维归因(用户要"更完善"的直接落点)。
2. 响应入库精确落点 = handler statusRecorder 加 Write tee + 新增 response_sink(不动 9 列主 CSV)。
3. `__unmatched__` → attribution 跳过 = 三端不同源时 method 静默从归因消失的精确机制(§8.3 代价坐实)。
4. 归因不用 request_id(只秒窗), request_id 仅为响应↔请求关联存在(全新增链)。

## 13. 八轮 token-level 全链路精读最终覆盖清单
✅ 入口 main + Phase 编排 / prepare_benchmark_data / fetch 4 adapter 完整 + create_adapter + main /
config_loader CHAIN_CONFIG 构造 + rpc_methods 提取 + 8链case / 6 family build_vegeta_target + _build_params /
base.py vegeta 构造 + 注册表 / cli.py 5 子命令 + _get_param_format / proxy jsonrpc+rest extractor 全文 /
proxy handler.go 全文 / proxy sink.go 全文 / master_qps_executor 压测循环 / report per_method 渲染链 /
per_method_attribution.py 全文。
**九大真实障碍/缺口(grep 阶段全无), 见 §11.6 + §12.5。** 这是出 §6 实施计划的完整事实地基。


## 14. 第九轮 token-level 精读: per_method_charts + 监控采集数据源(四维归因补全可行性)

### 14.1 per_method_charts.py 逐行精读 — 出图坐实只 CPU 一维
- L3-7 docstring + L259-282 generate_all_charts: 产 **4 张图 = qps / latency / error_rate / resource**。
- L279-282 resource 图 `plot_resource_stacked`: L241 只取 `r.cpu_pct`, L252/282 标题 "CPU% (attributed)" / "CPU Attribution"。
- 🔴 **坐实链条**: attribution 只算 CPU/MEM(§12.1)→ resource 图**只画 CPU**(连 MEM 单独图都没出)→ **EBS/Network per-method 图完全不存在**。NS-2 四维要求 vs 实现一维出图, token-level 全链路坐实。

### 14.2 监控采集数据源逐行精读 — EBS/Network 列【已就绪】(补四维归因好消息)
- unified_monitor.sh get_network_data(L418): 采 rx_mbps/tx_mbps/total_mbps/rx_pps/tx_pps/...(L475 输出 10 网络字段)。
- disk 列: source disk_converter.sh(L21), iostat 采 disk iops/throughput/util(disk 段 21 字段, 含 disk_r_s/disk_w_s/disk_total_iops)。
- ✅ **monitor CSV 已采 CPU/MEM/EBS(disk)/Network 全四维数据** —— 补全 per-method 四维归因**不需要新增采集**, 只需:
  1. read_monitor_csv 多读 disk/net 列(现只读 cpu_usage/mem_used, attribution.py L94-98)。
  2. PerMethodResourceRow 加 disk_iops/disk_throughput/net_rx_mbps/net_tx_mbps 字段。
  3. compute_per_method_resource 按同一 weight 分摊这些列(像 cpu_pct*weight)。
  4. per_method_charts 加 disk/net 归因图。
- **这是 NS-2 "更完善"的低风险高价值补全**(数据源就绪, 只扩分析+出图层, 不动采集)。

### 14.3 第九轮结论
- per-method 归因/出图当前只 CPU 一维(MEM 算了但没单独出图, EBS/Net 完全没算没画)。
- 但监控采集层 CPU/MEM/EBS/Network 四维数据**全部就绪** → 补全 NS-2 四维归因 = 纯分析+出图层扩展, 数据源零改动, 低风险。
- 这把 §12.5 的"EBS/Net 归因缺失"从"重大缺口"细化为"低风险可补"(数据源就绪是关键前提, token-level 才确认)。

## 15. 九轮 token-level 精读 — 全链路 + 周边覆盖总清单
核心链(八轮)+ 本轮周边: per_method_charts 出图全文 + unified_monitor 采集数据源(CPU/MEM/EBS/Net 四维列)。
**仍可继续扩大的周边**(对核心重构非阻塞, 但用户要持续扩大): proxy config loader(proxy_extraction 加载/校验)、
proxy selfreport(Q4-10 自报基线)、cli.py health-probe 完整、replace_env_vars 占位符替换、
fetch Sui adapter 尾部、target_generator read_accounts 完整、config_loader MAINNET_RPC_URL 8链case 全文。


## 16. 第十轮 token-level 精读: proxy config loader + target_generator 输入消费端

### 16.1 proxy config loader.go 逐行精读 — 三端同源识别端配置源确认
- L34 LoadChain: 从 chain template 读 `proxy_extraction.extractors` → 建 extractor chain。
- L59-72 buildExtractor: **只支持 2 protocol = json_rpc(需 url_pattern)/ rest(需 url_patterns)**, 其余报错。
- L43-44 无 extractors 直接报错(每链必配 proxy_extraction)。
- 🎯 **三端同源实现路径坐实**: param_spec(新增, 构造)+ proxy_extraction(现有, 识别)+ response_spec(新增, 解析)
  **都在同一 chain template JSON, 但是三个独立字段**。重构必须保证三者从单一 method 声明派生或交叉校验,
  否则漂移 → method 静默从归因消失(§12.3 `__unmatched__` 机制)。proxy_extraction 只 2 protocol(json_rpc/rest)→
  tendermint 25 method 协议错配(§2.1)在 proxy_extraction 端也要确认配的是 rest(LCD path)还是 json_rpc。

### 16.2 target_generator generate_targets 逐行精读 — 输入消费端精确落点
- L220-225 read accounts: **只读 ACCOUNTS_OUTPUT_FILE 一个文件**(account 地址), 逐行进 accounts[]。
- L240-268(§前轮已读): single 用 accounts[0..] 配 method[0]; mixed round-robin。
- 🎯 **输入池消费端改动落点**: 重构加 tx_hash_pool/block_id_pool 后, generate_targets L220-225(读单一 accounts)
  + L246-262(喂 method+address)要改成 **按 param_spec 的 source 类型, 该 method 从对应池取值**
  (account→accounts池 / tx_hash→tx_hash池 / block_id→block_id池 / contract_call→固定/声明)。
  现在所有 method 都喂 account(§3 输入供给缺口的消费端根因, token-level 精确定位)。

### 16.3 第十轮结论
- 三端(param_spec/proxy_extraction/response_spec)同在 chain template 三独立字段, 重构核心 = 三者单一来源/交叉校验。
- 输入池消费端精确落点 = target_generator generate_targets L220-262(现只读 accounts 一池喂所有 method)。

## 17. 十轮 token-level 精读完整性最终自评(诚实)
**已逐行精读(核心闭环 + 关键周边)**: 入口/fetch 4 adapter全/config_loader CHAIN_CONFIG+rpc_methods/
6 family build+_build_params/base.py/cli.py/proxy jsonrpc+rest extractor/proxy handler/proxy sink/
proxy config loader/master_qps_executor压测循环/report per_method渲染链/attribution全文/charts出图/
unified_monitor采集数据源/target_generator输入消费端。
**剩余未逐行(真边缘, 对核心重构非阻塞)**: proxy selfreport(Q4-10自报基线)/cli.py health-probe/
replace_env_vars占位符/fetch Sui adapter尾部/config_loader MAINNET_RPC_URL 8链case全文。
**累计 10 个真实障碍/缺口**(§11.6 八个 + §12.5 EBS/Net归因缺失 + §14.2 数据源就绪降风险 + §16 三端同源+输入消费端落点)。
这是 grep 阶段完全不可能得到的事实地基, 足以支撑出零技术债的 §6 实施计划。


## 18. 第十一轮 token-level 精读: proxy selfreport + Sui尾部 + replace_env_vars(我武断标"边缘"实为缺口)

### 18.1 🔴 proxy selfreport.go — 第11个真实缺口(我之前武断标"边缘", 一读即真缺口)
- selfreport.go 完整: 每秒读 /proc/self/stat(utime+stime)+ /proc/self/status(VmRSS)→ 写 `proxy_self.csv`(timestamp_ns, cpu_pct, mem_mb)= proxy 自身资源开销。
- main.go:60 selfreport.New 启动; lib/proxy_lifecycle.sh:143 引用路径 → **proxy 确实在生成 proxy_self.csv**。
- 🔴🔴 **批判性 grep 验证(grep -rn proxy_self analysis/ visualization/ core/ monitoring/ = 空)**: **没有任何分析代码消费 proxy_self.csv / 减 proxy 基线**。
- **Q4-10 设计 vs 实现差距**: Q4-10 锁"proxy 自报基线 + **分析层从节点资源减去 proxy 基线后再归因 method**"。但 attribution.py compute_per_method_resource(§12.1)只用 `monitor.cpu_pct × weight`, **没减 proxy_self.csv 的 proxy 自身开销** → per-method 归因的 CPU/MEM **偏高**(proxy 进程开销被算进了 method)。
- 这是 parallel-entry 近亲: **proxy_self.csv 采了但生产分析链没接 = 死数据**。NS-2/Q4-10 未完成项。
- **自我批判**: 我前几轮把 selfreport 标"边缘非阻塞"是**没读就预判**, 违反 token-level。一读即发现是真缺口。**"没读的不能判定边缘"** — 教训。

### 18.2 fetch Sui adapter 尾部 + replace_env_vars(逐行精读, 确认非缺口但记录事实)
- Sui(L516-599): suix_queryTransactionBlocks(MoveFunction filter / 全局搜索)→ digest(tx hash)→ fetch_transaction(showObjectChanges/showBalanceChanges)→ extract。**确认 Sui 抓取独有逻辑**(印证 §9.1 6 family 补全从零设计)。
- replace_env_vars: 递归替换 CHAIN_CONFIG 里值=env 变量名的字符串(如 "account_count":"ACCOUNT_COUNT" → os.environ 读 + 类型转换)。**印证 skill ref "params 字段值是 env 占位符, 直连测拿字面量"的坑**。重构 InputProvider 整合后此占位符机制要保留(config_loader 注入 ACCOUNT_* env)。

### 18.3 第十一轮结论 + 11 个缺口
新增第 11 缺口: **proxy_self.csv 采了但归因没减 proxy 基线**(Q4-10 未完成, per-method CPU/MEM 偏高)。
**11 个真实障碍/缺口总清单**(grep 阶段零):
1. 两套 adapter 分派冲突(chain_type vs family)→ 整合方案 c
2. 6 family account 抓取从零设计(bitcoin UTXO 无 account / 各家机制不同)
3. fetch method ≠ 压测 method(methods vs rpc_methods 两字段)
4. CHAIN_CONFIG 删 _meta → 整合按 family 要先改 config_loader
5. vegeta 固定 id=1 + rest RequestID="" → 响应入库关联键必须重建
6. 压测层 + report 层都不消费响应 → 响应消费链全新增
7. 三端同源(param_spec/proxy_extraction/response_spec 三独立字段)
8. per-method 归因缺 EBS/Network 两维(数据源就绪, 低风险补)
9. mixed weight R5 配置 weight 未驱动生成端(round-robin 均权)
10. 输入池消费端(target_generator)只读 accounts 一池喂所有 method
11. **proxy_self.csv 采了没减基线 → 归因 CPU/MEM 偏高(Q4-10 未完成)**

### 18.4 诚实自评(用户问"完全吃透了么")
- 我前几轮有"没读就标边缘"的武断(selfreport 就是反例, 一读即第11缺口)。本轮已纠正, 逐行读完。
- **仍未逐行**: cli.py health-probe(cmd_health_probe + 各 family health_check_request 已在 adapter 读过)/ config_loader MAINNET_RPC_URL 8链 case 全文(OQ-11 已知)/ proxy main.go 完整 / extractor chain.go(NewChain 组合逻辑)/ extractor.go(Result 结构 + Chain.Extract 遍历)。
- **下一步继续**: 读 extractor chain.go + extractor.go(Chain 如何遍历多 extractor, 影响 hedera_dual 双 extractor + 三端同源识别细节)+ proxy main.go(启动参数 + maxBody)+ health 链。


## 19. 第十二轮 token-level 精读: extractor.go(Chain) + proxy main.go(启动编排) — proxy 子系统读透

### 19.1 extractor.go 完整(Result + Chain 遍历)— hedera_dual 双 extractor 机制坐实
- Result 结构: Protocol / MethodName / RequestID(注释 L18 明确 "rest 模式为空")/ BatchIdx。
- **Chain.Extract: 按声明顺序遍历 extractor, 第一个 ok=true 即停**(命中优先级=声明顺序)。
- 🎯 **hedera_dual 双 extractor 机制坐实**: hedera chain template 配 2 extractor(rest + json_rpc), Chain 顺序尝试 —— eth_* 请求 rest 不匹配(path 不中)→ 落 json_rpc 匹配。**双协议靠 url_pattern 互斥 + 顺序命中实现**。
- 🔴 **风险(三端同源延伸)**: Chain "第一个 ok 即停" → 若 rest extractor 的 url_pattern 写太宽(误匹配 eth_* path), 会抢先错误命中 → method 提取错。**多 extractor 链(hedera_dual + 任何未来双协议链)的 proxy_extraction 必须 url_pattern 精确互斥**, 顺序也重要。重构三端同源校验要覆盖"多 extractor 不重叠匹配"。

### 19.2 proxy main.go 完整(启动编排)— 响应入库接入点
- flag: -chain(单文件, Q4-2 单链启动切链重启坐实)/ -upstream / -listen(:18545)/ **-max-body(默认 1MB, 请求 body 读取上限)** / -self-interval。
- 组装: L43 LoadChain → L49 sink.New(默认csv)→ L55 handler.New → L60 selfreport.Start → L66 http.Server。
- 🎯 **响应入库启动接入点**: 响应 sink 在 L49 附近新增(respSink := sink.NewResponse + 开关 env)+ 传 handler.New。main.go 是组装点。
- 🔴 **响应入库 OOM 防护**: L35 maxBody 1MB 是**请求** body 上限; 响应入库时**响应 body 也要类似上限**(near validators 419KB / solana getBlock MB 级 / aptos resources MB 级 → 响应缓冲要限大小或采样, 否则高QPS下 OOM)。这是 §11/§12 响应入库设计要补的防护(token-level main.go maxBody 才联想到)。

### 19.3 proxy 子系统 token-level 全读透
proxy/internal: extractor.go + jsonrpc.go + rest.go + handler.go + sink.go + config/loader.go + selfreport.go + cmd/proxy/main.go **全部逐行精读完毕**。

## 20. 十二轮 token-level 精读 — 最终完整性自评(诚实)
**已逐行精读全部核心 + proxy 子系统全文 + 关键周边**:
- Python: blockchain_node_benchmark.sh 入口 + fetch_active_accounts.py(4 adapter 全 + create_adapter + main + replace_env_vars)+ config_loader.sh(CHAIN_CONFIG + rpc_methods + 缓存)+ target_generator.sh(generate_targets 输入消费)+ cli.py(5 子命令 + _get_param_format)+ 6 family adapter(build_vegeta_target + _build_params)+ base.py + master_qps_executor.sh(压测循环)+ per_method_attribution.py 全文 + per_method_charts.py 全文 + unified_monitor.sh 采集源。
- Go(proxy 全子系统): extractor.go + jsonrpc.go + rest.go + handler.go + sink.go + config/loader.go + selfreport.go + main.go。
**仍未逐行(确认真边缘 — 已读其依赖/接口足以判定)**: cli.py cmd_health_probe(health_check_request 已在 6 adapter 读过)/ config_loader MAINNET_RPC_URL 8链 case 全文(OQ-11 已知模式)/ per_method_report.py(渲染 HTML 文案, 不涉逻辑)/ 各 *_test.go(测试)。

**累计 11 个真实障碍/缺口(§18.3)**, 每个都有精确代码落点。这是从框架入口到响应归因的完整闭环、grep 阶段完全不可能得到的事实地基, 足以支撑零技术债 + 优雅的 §6 实施计划。


## 21. 🔴🔴🔴 第十三轮重大发现: 框架"按链处理 RPC"有【4 套独立分派】, 非 2 套(我前面武断"读透"时漏了 2 套)

用户第三次追问"完全吃透了么"逼我读 cli.py health-probe 的 caller, 顺藤摸到 block_height_monitor → common_functions.sh, 挖出我前面完全漏掉的**第 3、4 套按链分派**。

### 21.1 cli.py 5 子命令 caller 核实
- build-target(legacy)/ build-targets-batch(生产)→ target_generator(已知)。
- **health-probe / parse-height: grep 生产代码无 caller, 只测试调** → 生产块高/健康检查**不走 cli.py**。
- 那生产块高检查走哪? → 顺藤摸到 block_height_monitor.sh:145/151 `source common_functions.sh && get_block_height`。

### 21.2 🔴 第三套 + 第四套按链分派(token-level 实证, 前面完全漏)
框架"按链处理 RPC"实际有 **4 套独立分派, 维度各异、互不知道**:
| # | 位置 | 分派维度 | 覆盖 | 职责 | 我之前 |
|---|---|---|---|---|---|
| 1 | fetch create_adapter(L661) | chain_type | 8链(4 adapter) | 取 account | §1 已发现 |
| 2 | chain_adapters get_adapter | adapter_family | 36链(6 family) | 构造 target + parse_block_height + health_check_request | §1 已发现 |
| 3 | config_loader MAINNET_RPC_URL case(L454) | BLOCKCHAIN_NODE | 8链 case | 设 mainnet endpoint | OQ-11 提过半 |
| 4 | **common_functions get_block_height case(L194)** | BLOCKCHAIN_NODE | **8链 case** | **块高监控/健康检查** | 🔴 **完全漏!本轮挖** |

### 21.3 🔴 第 12 缺口: 块高提取逻辑重复实现两次(chain_adapters 36链 vs common_functions 8链 case)
- common_functions.sh get_block_height(L180-281): case 8链, 每 case 重复硬编码 method + 块高提取
  (solana getBlockHeight / EVM eth_blockNumber+hex转十进制 / starknet starknet_blockNumber / sui sui_getTotalTransactionBlocks), L270 其余链 `Unsupported blockchain type`。
- **这与 chain_adapters 的 parse_block_height + health_check_request 完全重复**(同 method 同提取逻辑), 但各写各的。
- **块高监控(block_height_monitor.sh, NS-2 监控组件)用的是 common_functions 的 8 链 case 版, 完全不用 chain_adapters 的 36 链版** → parallel-entry: 块高提取实现两次, 监控用落后的 8 链版 → **28 链块高监控不支持**(与 README "8链e2e" 同根)。

### 21.4 整合范围重大修正(影响方案 c)
§7 整合方案 c(统一 family 分派)之前只覆盖 2 套 adapter。**实际要覆盖 4 套**:
1. fetch(取 account)→ InputProvider 按 family(§7)
2. chain_adapters(构造+解析)→ TargetBuilder(现成)
3. config_loader MAINNET case → 改读 chain template(OQ-11)
4. **common_functions get_block_height case → 改用 chain_adapters parse_block_height**(消除块高提取重复, 块高监控支持 36 链)
**4 套统一到 chain_adapters 的 family 分派 + chain template 声明**, 才是真正"不留技术债"的整合。否则块高监控/endpoint 这两套继续 8 链硬编码。

### 21.5 自我批判(用户第三次追问才挖出)
- 我第十二轮说"proxy 全读透 + 真边缘已读依赖足以判定" = **又一次武断**。cli.py health-probe 的 caller 我没追 → 漏了 block_height_monitor → common_functions 第三/四套分派。
- **教训坐实**: "读了 X 文件"≠"吃透 X 的调用全景"。cli.py 读了, 但没追它每个子命令的 caller → 漏掉一整条块高监控链 + 两套按链分派。**精读必须追到每个公共函数/CLI 子命令的真实 caller, 否则就是局部读。**
- 缺口从 11 个增至 **12 个**(新增: 块高提取重复实现 + 第三/四套按链分派未纳入整合)。

### 21.6 仍需继续(诚实, 不再说"够了")
- common_functions.sh check_node_health 全文(L284-317)+ 该文件其余函数。
- block_height_monitor.sh 完整(它怎么用 get_block_height + 写什么 CSV + 谁消费)。
- config_loader MAINNET_RPC_URL case 全文(第三套, 确认 8 链 + endpoint 来源)。
- 其余 monitoring/ 组件是否还有第 5 套按链分派(unified_monitor/network_monitor 等)。


## 22. 第十四轮 token-level 精读: 全仓按链分派点穷举 + config_loader MAINNET case 全文(4套确认 + endpoint 分散)

### 22.1 全仓按链分派点穷举(grep 全 case/if 分派 + 逐个核实 caller)— 生产 4 套确认
grep 全仓 `case blockchain_type / chain_type == / in [solana...]`, 逐个核实 caller:
| 分派点 | 生产? | 归属 |
|---|---|---|
| fetch_active_accounts.py L665 create_adapter | ✅ 生产 | 套1(取 account, chain_type 8链) |
| fetch L316 EthereumAdapter 内 bsc/ethereum 微调 | ✅ 生产 | 套1 内部(block_range 调参) |
| chain_adapters get_adapter | ✅ 生产 | 套2(family 36链) |
| config_loader.sh L454 MAINNET case | ✅ 生产 | 套3(8链 endpoint) |
| common_functions.sh L194 get_block_height case | ✅ 生产 | 套4(8链 块高监控) |
| **audit_rpc_methods.py L116 if/elif** | ❌ **无 caller(grep 生产代码空)** | 独立审计工具, 非生产链, 不计入 |
**结论: 生产按链分派确为 4 套(§21.2), audit_rpc_methods 是独立工具排除。无第 5 套。**

### 22.2 config_loader MAINNET_RPC_URL case 全文(套3)— 第五处 endpoint 声明 + 失效迁移历史
- L454-490: case 8链, **内嵌 8 条真实 mainnet endpoint URL**(solana api.mainnet-beta / eth llamarpc / bsc dataseed / base mainnet.base.org / polygon publicnode / scroll rpc.scroll.io / starknet lava / sui fullnode), L485 其余链兜底 solana。
- 注释记录 endpoint 失效迁移(polygon polygon-rpc.com 停服→publicnode; starknet blastapi 停→lava)→ 与我建 fixture 时遇到的失效一致(framework 早踩过)。
- 🔴 **第 12.5 缺口延伸: endpoint 声明分散在 5 处**:
  1. chain template `rpc_url` = LOCAL_RPC_URL 占位符(运行时注入)
  2. config_loader MAINNET case = 8 链真实 mainnet URL(套3)
  3. 我建的 record_all_184_fixtures.py = 36 链 endpoint 映射(本次新增)
  4. proxy -upstream flag(运行时传)
  5. (block_height_monitor 用 MAINNET_RPC_URL/LOCAL_RPC_URL = 复用套3/注入)
- 整合应统一: chain template 增 `mainnet_rpc_url` 字段(OQ-11 候选a), 套3/fixture/proxy 都从 chain template 读, 36 链 endpoint 单一来源。

### 22.3 第十四轮结论
- 生产按链分派 = **4 套**(确认无遗漏, audit 工具排除)。
- endpoint 声明分散 5 处, 整合到 chain template 单一来源(配合 OQ-11)。
- 整合方案 c 最终覆盖面: 4 套按链分派 + 5 处 endpoint → 统一到 chain template(family + mainnet_rpc_url + param_spec + proxy_extraction + response_spec)单一来源 + chain_adapters family 分派单一入口。这才是用户要的"更统一/不留债"。

## 23. 十四轮 token-level 精读 — 截至目前缺口总账(12 个)
1. 两套→实为分派 4 套(fetch/chain_adapters/config_loader MAINNET/common_functions block_height)
2. 6 family account 抓取从零设计(bitcoin UTXO 无 account)
3. fetch method ≠ 压测 method
4. CHAIN_CONFIG 删 _meta → 整合按 family 要先改 config_loader
5. vegeta id=1 + rest RequestID="" → 响应入库关联键重建
6. 压测/report 不消费响应 → 响应消费链全新增
7. 三端同源 + hedera 多 extractor url_pattern 互斥
8. per-method 归因缺 EBS/Network(数据源就绪低风险补)
9. mixed weight R5 未驱动生成端
10. 输入池消费端只读 accounts 一池
11. proxy_self.csv 采了没减基线(Q4-10 未完成)
12. **块高提取重复实现两次(chain_adapters 36链 vs common_functions 8链 case)+ endpoint 分散 5 处**

### 仍需继续(诚实)
- common_functions.sh check_node_health 全文 + 该文件其余函数全文。
- block_height_monitor.sh 完整(消费 get_block_height + 写什么 + 谁读)。
- 其余 monitoring 组件(unified_monitor 主体 / network_monitor / ena_network_monitor)是否还有按 method/链 的隐藏逻辑。
- audit_rpc_methods.py(虽非生产, 但它的 8 链审计逻辑可能揭示更多 method 形态)。


## 24. 第十五轮 token-level 精读(逐行读真实文件, 非grep非缓存): common_functions全文 + block_height_monitor核心链

### 24.1 common_functions.sh 全文逐行(317行读完)— 套4 是块高监控+健康检查共同底座
- L19-75 buffered_write: 带 buffer 安全写盘(块高数据写盘用, buffer_size 默认 10)。
- L78-104 get_cached_block_height_data: 块高缓存(max_age 1s)未过期返缓存。
- L105-168 get_cached 后半: 取 local+mainnet 块高(get_block_height 套4)+ 健康 → 算 block_height_diff=mainnet-local → data_loss 判定 → 写 JSON 缓存(local/mainnet block_height/diff/health/data_loss)。
- L170-177 cleanup_block_height_cache: 删 5 分钟前缓存。
- L180-281 get_block_height(套4, §21 已读): case 8链, 每 case 重复硬编码 method+块高提取。
- L284-317 check_node_health: **复用 get_block_height**(L306)判健康(取到块高=healthy), 60s 缓存。
- 🎯 **完整理解(前面没看到的业务耦合)**: 套4(get_block_height)是**块高监控 + 健康检查的共同底座**, check_node_health 不是独立逻辑而是调 get_block_height → 两者都只 8 链。

### 24.2 block_height_monitor.sh 核心链逐行(464行, 读 L1-230)— NS-2 块高监控端到端
- L10 source config_loader(拿 LOCAL_RPC_URL/MAINNET_RPC_URL/阈值)+ L18 source csv_schema_registry(block 段 header 单源)。
- L142-159 get_local/mainnet_block_height + check_node_health: **全委托 common_functions(套4)** → 坐实块高监控完全依赖套4(8链)。
- L162-178 monitor_block_height_diff: 取块高缓存数据 → 解析 → **buffered_write 写 CSV**(L177: timestamp,local_block_height,mainnet_block_height,block_height_diff,local_health,mainnet_health,data_loss = block 段 7 字段)。
- L180-229 告警: diff > BLOCK_HEIGHT_DIFF_THRESHOLD 告警 + 持续超 BLOCK_HEIGHT_TIME_THRESHOLD 升 CRITICAL(写 block_height_time_exceeded.flag, 系统级瓶颈判定用)+ unified_event_manager 记事件。

### 24.3 完整理解块高监控链(套3↔套4↔监控的真实业务耦合, 前面完全没看到)
```
block_height_monitor.sh
  → common_functions get_block_height(套4, 8链case)  ← 用 LOCAL_RPC_URL(注入) + MAINNET_RPC_URL(套3, 8链case)
  → block_height_diff = mainnet - local(节点同步落后程度)
  → 写 block_height CSV(7字段) + 超阈值告警 + flag(系统级瓶颈判定)
```
- **块高监控同时依赖套3(MAINNET URL 8链)+ 套4(get_block_height 8链)** → 整链只支持 8 链。
- 块高提取(套4)与 chain_adapters parse_block_height(36链)**重复实现**, 监控用 8链版。
- 🔴 **重构整合必须把套4 替换为 chain_adapters parse_block_height + health_check_request**(36链), 块高监控才支持 36 链; 同时套3 MAINNET URL 移入 chain template(§22.2)。否则 NS-2 块高监控永远卡 8 链。

### 24.4 第十五轮结论 + 仍需继续
- common_functions 全文 + block_height_monitor 核心链逐行读完, 完整理解套3↔套4↔块高监控耦合。
- 缺口 #12(块高提取重复)细化: 不只重复, 是块高监控整链(监控+健康+告警)绑死 8 链, 重构要换底座到 chain_adapters。
- **仍需继续(逐行真实读)**: block_height_monitor.sh L230-464(start_monitoring/CSV header writer/状态输出)/ unified_monitor.sh 主体(是否有按链/按method隐藏逻辑)/ network_monitor.sh / ena_network_monitor.sh / monitoring_coordinator.sh / unified_event_manager.sh。


## 25. 第十六轮 token-level 精读(逐行真实文件): block_height_monitor全文464行 + unified_monitor block段

### 25.1 block_height_monitor.sh 全文 464 行读完
- L232-272 data_loss 告警 + DATA_LOSS 统计(count/periods/total_duration → data_loss_stats.json)。
- L287-335 show_status: 展示块高状态(同样 source common_functions get_cached)。
- L337-374 stop_monitor: kill PID + 清缓存。
- L376-434 start_monitoring: **CSV header 走 csv_registry_segment_header block 单源 + fallback 7字段**(L392-401); 监控循环 `while [[ -f "$TMP_DIR/qps_test_status" ]]`(统一生命周期信号, skill §8.1, 改循环=AP3)→ monitor_block_height_diff + sleep。
- L437-451 main: check_dependencies + parse_args + start_monitoring。
- L452-464 update_data_loss_stats: 写 data_loss_stats.json。
- **完整理解**: block_height_monitor 走统一 qps_test_status 信号, CSV header registry 单源, 数据来自套3+套4(8链)。

### 25.2 unified_monitor.sh block 段 — 复用 block_height_monitor 输出, 不是第5套(好消息)
- generate_csv_header(L1925-1965): unified CSV 完整段 = basic+device+network+[ena]+overhead+block_height+qps+cgroup+cloud_provider, 各段 header 走 csv_registry 单源。
- 🎯 **block 段数据采集(L2132-2145)**: **不是自己取块高, 而是 `tail -1 BLOCK_HEIGHT_DATA_FILE`(L2136)读 block_height_monitor 写的 CSV 最后一行 → cut 取 6 字段(L2139)**; 无文件填默认 0,0,0,1,1,0(L2141 优雅降级, skill §8.1)。
- 🎯 **确认: unified_monitor 不是第5套按链分派** —— 它是数据汇聚者(读 block_height_monitor 的 CSV 输出), 块高真正取数还是套4(get_block_height)。

### 25.3 第十六轮结论 — 按链分派确为 4 套, 无第 5 套(已穷举验证)
- 块高数据流完整: block_height_monitor(套4 取数 8链 + 写 block CSV 7字段)→ unified_monitor tail 读入 unified CSV block 段(6字段, 跳 timestamp)。
- unified_monitor 复用块高输出, 不自己按链取 → 无第 5 套。
- **生产按链分派最终确认 = 4 套**(§22.1 grep 穷举 + 本轮 unified_monitor 逐行验证一致): fetch create_adapter / chain_adapters get_adapter / config_loader MAINNET case / common_functions get_block_height。

### 25.4 监控层是否还有按 method 隐藏逻辑(待续逐行)
- block_height 段已确认: 不按 method, 只本地 vs 主网块高差。
- per-method 归因(attribution)已读: 只 CPU/MEM(§12.1)。
- **仍待逐行**: unified_monitor.sh 其余主体(2885 行, 已读 header+block 段, 未读 cgroup 采集/basic 采集/主循环)/ network_monitor.sh / ena_network_monitor.sh / monitoring_coordinator.sh(组件编排, 决定启哪些监控)/ unified_event_manager.sh。重点看 monitoring_coordinator 怎么编排(skill §8.1 提到硬编码 5 组件)。


## 26. 第十七轮 token-level 精读(逐行真实文件): monitoring_coordinator 编排 + network_monitor

### 26.1 monitoring_coordinator.sh 编排核心逐行
- L33-38 MONITOR_TASKS 映射: unified→unified_monitor.sh / block_height→block_height_monitor.sh / ena_network→ena_network_monitor.sh / network→network_monitor.sh / disk_bottleneck→disk_bottleneck_detector.sh / iostat(由 unified 管)。
- L227-240 start_all_monitors: **硬编码 5 组件** `("unified" "ena_network" "network" "block_height" "disk_bottleneck")`(skill §8.1), for 循环各启 + sleep 1。
- L242-267 stop_all_monitors: 遍历 MONITOR_TASKS stop + pkill 兜底。
- 🎯 **编排关系**: start_monitoring_system(主入口)→ monitoring_coordinator start → start_all_monitors → 启 5 组件(含 block_height_monitor)。
- 🎯 **对重构(好消息)**: 块高监控换底座(套4 get_block_height → chain_adapters parse_block_height/health_check_request 36链)**是 block_height_monitor.sh 脚本内部改动, 不影响 coordinator 编排**(coordinator 只管启脚本不管内部取块高)。编排层契约不破 → 降低块高监控重构风险。

### 26.2 network_monitor.sh 逐行(L1-90)— 按 cloud_provider 分派, 非第5套按链
- L5-7 注释: Y+ 架构, **按 (CLOUD_PROVIDER, NIC_DRIVER) 路由** aws_ena/gcp_gvnic/gcp_virtio/other_none。
- L42 source network_unified_entry.sh(自动探测平台/驱动)→ 4 接口(init/collect/header)。
- L55-91 cmd_start: init_network_monitoring(失败回退 other_none)→ 写 PID + CSV header → collect_network_metrics 循环写 network CSV。
- 🎯 **确认: network_monitor 按 cloud_provider/NIC_driver 分派(provider 抽象, 已 declarative variant 路由), 与按链/按method无关 → 不是第5套按链分派**。

### 26.3 第十七轮结论 — 监控层 token-level 读透
- 监控层(block_height_monitor / unified_monitor block段 / monitoring_coordinator / network_monitor)全部逐行读透。
- **按链分派最终穷举确认 = 4 套**(无第5套): fetch create_adapter / chain_adapters get_adapter / config_loader MAINNET case / common_functions get_block_height。
- 监控层其余分派维度: network 按 cloud_provider(provider 抽象, 非按链); unified 数据汇聚(读各监控 CSV)。
- 块高监控换底座是脚本内部改动, 编排层契约不破。

## 27. 十七轮 token-level 全链路 + 周边精读 — 累计覆盖与缺口(诚实总账)
**逐行读透**: Python 全链路(入口/fetch全/config_loader/target_generator/cli/6 adapter/base/master_qps/attribution/charts/unified_monitor block段) + Go proxy 全子系统(8文件) + common_functions 全文 + block_height_monitor 全文 + monitoring_coordinator 编排 + network_monitor + 监控采集源。
**仍未逐行(评估真边缘, 但按教训不再武断, 列出待读)**: unified_monitor 其余主体(basic/cgroup 采集/主循环, 2885行已读 header+block 段)/ ena_network_monitor.sh / unified_event_manager.sh / disk_bottleneck_detector.sh / network_unified_entry.sh + monitoring/network/*.sh(provider variant)/ audit_rpc_methods.py。
**12 个真实缺口**(§23 总账, 块高监控#12 已细化为整链绑8链)。这是从入口到响应归因到监控的完整闭环 token-level 事实地基。
