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
