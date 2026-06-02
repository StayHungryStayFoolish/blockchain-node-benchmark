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
