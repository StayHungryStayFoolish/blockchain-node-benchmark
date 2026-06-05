# RPC Method 重构 — 权威事实源(SSOT)

> ⚠️ 唯一权威。改代码只认本文件 + 代码更新 task(REFACTOR-TASK-STATUS.md)。
> 其余 analysis-notes/rpc-* 文档是【原料/分析过程】, 不直接指导改代码。
> 本文件每一条都经 token-level 审核 + 代码实证确认; 不确定的不进本文件(进 REFACTOR-UNCERTAIN.md)。
>
> 维护规则:
> - 现状列 = 代码 grep/read 实证(file:line), 不信旧文档表述。
> - 重构目标列 = 重构后应变成的样子(明确"未做")。
> - 已完成列 = 已落地且接进调用链 + L 验证过的(带 commit)。
> - 每条搬入前查 diff 防丢失; 涉及 skill 同步更新 skill。
> - **每个内容点搬入前必全范围搜索(grep -rl 穷举所有文件)+ token-level 读全 + 交叉确认无过时/矛盾, 才更新; 无法确认则停下问用户(用户 2026-06-04 定)。**
>
> 📋 旧文档收敛状态:
> - 原料(审核后搬入本SSOT, 全搬完即删/标存档): design / fulllink / callchain / requirements / param-research。
> - **SELF-EXEC-PROMPT-rpc-dsl.md 已删**(内容被本 SSOT 完整取代; 原是上下文续命 prompt + 落点索引, SSOT 全单元搬完后冗余; skill 5处引用是方法论案例不依赖该文件内容)。

---

## 0. 北极星(锁定, 不变)
> 来源: design §0(用户 2026-06-01 澄清)+ NORTH-STAR NS-1/2/3。审核确认: 清晰无矛盾, 权威定稿。

**总目标: 让框架兼容【使用者自己配的、我们没预置的】任意 RPC method —— 零代码。**
应用场景: 使用者按业务场景配一个 36 链里没有的新 method, 只填 chain template(声明参数怎么传 + 响应怎么解), 框架就能正确压测它 + 正确归因/分析, 不改代码。

两个抽象目标:
1. **参数结构抽象**: 不靠 param_format 预定义枚举名(新形态撞上没有的就得改 _build_params 代码), 而是一套通用的【声明式参数描述】(几个位置、每个位置类型、地址/区块/哈希填哪)→ 框架据此构造请求。
2. **响应结构抽象**: 用户配的新 method 返回什么结构, 框架声明式地知道怎么解析(从响应哪个字段提 block_height/account/data), 而非每个 method 在 parse 代码硬编码。

NS 对应(NORTH-STAR): NS-1 36链零代码加链 / NS-2 mixed 模式 per-method 资源归因(CPU/MEM/EBS/Net)+ 出图 + 双语HTML / NS-3 零代码原则覆盖 adapter + proxy 解析层。**本次重构 = NS-1/NS-3 从"零代码加链"延伸到"零代码加 method"。**

**为什么全量实测(方案B)**: 必须先摸全 36 链 184 method 的真实参数形态 + 真实响应结构(public endpoint 实测), 才能归纳 DSL 覆盖哪些情况。抽样不够(只验规律存在, 不保证 DSL 覆盖全部真实形态)。

## 0.1 现状抽象的不足(=重构动机, design §1)
- **参数**: 靠 (family, param_format) 二维, param_format 是预定义枚举名(实测 56 种, design 旧写53已订正)。新 method 形态不在枚举 → 必须改 _build_params 加分支(非零代码)= R1。
- **无校验**: 用户声明错 param_format(位置反/类型错)框架静默错(public endpoint 证实位置错=报错)= R2/R3。
- **响应**: 各 method parse 逻辑散在 adapter 代码, 非声明式。
- = 现状"预置好的能跑, 用户加全新的要改代码", 不满足目标。

## 1. 重构功能单元 × 三态 × 依赖
> 每个单元: 涉及代码文件:行号 / 现状(实证) / 重构目标(未做) / 依赖谁先做 / 完成判定 / 权威依据来源

### 单元 S1 — 输入供给层 InputProvider(缺口 #2/#3/#6-fetch/#10 + R-A/R-B/R-D)
**涉及代码**: tools/fetch_active_accounts.py(create_adapter def L661 / 分派体 L665-674: solana L665·ethereum,bsc,base,scroll,polygon L667·starknet L669·sui L671·else raise L673 / tx_hash·block 经手 L204·313·335 `{"signature":...}`/latest_block/transactionHash / 写盘 L816-818 单列account)、tools/target_generator.sh(读单列 L193-225: L193 文件检查→L225 `done < ACCOUNTS_OUTPUT_FILE` / round-robin L258-263: L258 account_index=0·L260 `method_index=$((account_index % method_count))`均权·L263 +1)、config_loader.sh(ACCOUNTS_OUTPUT_FILE 约定)。
**现状(代码实证 2026-06-04, grep+read_file double check 行号准确)**:
- create_adapter(def L661) 只 4 adapter 类覆盖部分 chain_type(L665 solana / L667 ethereum,bsc,base,scroll,polygon / L669 starknet / L671 sui / **L673 else raise**), **bitcoin/UTXO 无 adapter → raise(缺口#2)**。
- fetch 经手 tx_hash/block(L204 signature / L313 latest_block / L335 transactionHash)但写盘只 account 单列(缺口#3)。
- target_generator 读单列 account 喂所有 method(缺口#10)。**实证: audit 16 个 P1_RPC_ERROR, error.data.reason 精确点名缺 filter/transaction_hash → 不是推测, 是节点报错点名缺输入**。
- 写盘块 L816-818(open L816 / for top_accounts L817 / `f.write(f"{addr}\n")` L818)= 只落 account 单列, tx_hash/block 不落盘(缺口#3 落点)。
- 占位符污染(缺口连带): jsonrpc.py:84 tx_hash 无真值→全0占位→节点返null→per-method 归因偏低失真。
- **🔴 关键概念区分(消除常见误解, chain-template-guide L50)**: `transaction_hash`/`txid`/`block_number` 枚举**已存在于参数构造层**(param_formats 能构造 tx_hash/区块号参数), 但 —— **输入供给层只产 account 一池, 没有 tx_hash/block 池**。∴ 这些枚举能\"构造\"tx_hash 参数, 却**拿不到真实 tx_hash 值**(靠占位符兜底→节点报错)。即: **参数构造已支持, 真实输入供给没跟上**——S1 补的是后者(输入供给), 不是前者(枚举/构造)。
**重构目标(未做)**:
- 方案c分层: InputProvider(async抓输入,6 family)/ TargetBuilder(sync构造)解耦。
- fetch_inputs(chain_template)→ 多池 {account[],tx_hash[],block[],utxo[],...}(非单account)。
- 6 family 各实现(bitcoin UTXO/txid 无account 单独处理)。
- fetch 写盘改多池(account/tx_hash/block 各池)。**取值层职责见下方"三层职责架构"(取值在 build_vegeta_target, 非 target_generator)。**
- **🔴 R-A 硬约束: 真实节点路径必须保留不破坏**(7个月前设计: 从被测节点取真实链上account→拼vegeta压测; 重构只扩展不破坏这条 live path)。
- **🔴 R-D 两条输入路径分治, 共用同一 param_spec DSL**: ① 真节点路径(生产/真机L3): fetch 顺手保留 tx_hash/block 多池 ② fake-node 路径(本地/CI): 输入池从 fixture 的 `<method>.request.json` 真实参数提取(或占位)。两路径只是池填充来源不同(真节点抓 vs fixture), DSL 共用。
**🔴 三层职责架构(已确认: fulllink §7 整合方案c[已拍板] + 用户 2026-06-04 确认。校正 design S1.4 措辞不准)**:
- **fetch 层(InputProvider, async)**: 抓 + 分池存 → accounts.txt + tx_hash_pool.txt + block_id_pool.txt(按family各一套抓取逻辑, fetch_active_accounts.py 降为薄 wrapper 调 get_adapter(chain).fetch_*)。
- **target_generator.sh 层**: 只管 method 分配 + 权重(single/mixed round-robin/weight), **不改**(不碰取值, round-robin/TSV 管道契约不变, fulllink §7 L43)。
- **build_vegeta_target 层(TargetBuilder, sync)**: 拿到 method 后, **按 param_spec.source 从对应池取值 + 拼协议请求**(取值精确落点在此, 非 target_generator)。
- → 三层职责干净(抓存/分配/取值构造各管各的)= 不留债 + 优雅(满足用户硬约束)。**design S1.4 写"target_generator 取值"措辞不准, 以 §7 权威为准: 取值在 build_vegeta_target。**
**依赖**: build_vegeta_target 取值 与 S2(param_spec.source)+ B3(接口签名:单address槽→多源)**强耦合**——必须一并改。**∴ S1(InputProvider+取值)/S2/B3 是一个原子单元,不可拆**(拆=孤岛, 2026-06-03 教训)。
**完成判定**: L1 每family InputProvider 单测 + build_vegeta_target 从池取值单测 / L2 抓输入→分池→构造 target 链路通 / L3 整框架对 mock 跑 mixed,需 tx_hash 的 method 不再 -32602 + 真值非占位。
**待决(OQ)**: 输入池粒度——tx_hash/block 池够不够? contract_call/business_id 输入怎么供给(硬编已知合约 vs chain template 声明)?(fulllink §6 L157)
**🔴 输入需求精确分类(callchain §6.2 + fulllink L75 两文档交叉验证一致)**: 184 method 中 none/fixed 79(不需输入) + account 55(fetch已供) + **tx_hash 17 / block_id 17 / contract_call 6 / business(pool_id/asset_id/epoch/twap) 5 = ~45 需非account输入但框架无供给源**。这是 S1 范围量化。
**🔴 复用 fetch 别重复造(callchain §6.4)**: fetch 内部已查 getBlockByNumber(L313)/transactionHash(L335)/signatures(L256)= 已有抓 block/tx 能力, 只是产出只留 account。S1 = 让 fetch 额外产出 block/tx 池, **不新写一套**。
**🔴 输入供给是必先做的地基(callchain §6.5)**: 阶段1输入供给必须最先做; 否则 param_spec 声明了 tx_hash source 也没真值可填 → 退回占位符兜底 = 没真解决债。
**🔴 整合接口障碍(fulllink §10 L325)**: fetch 收到的 CHAIN_CONFIG 不含 _meta.adapter_family(被 jq del 掉=缺口#4)。§7 整合要按 adapter_family 分派 → 必须改 config_loader 保留 _meta.adapter_family 进 CHAIN_CONFIG, 或 InputProvider 另读 chain 文件取 family。这是阶段1整合的具体接口改动点。
**🔴 fetch method ≠ 压测 method(fulllink §9.2 L310)**: InputProvider 取输入用的 method(chain template `methods` 字段)与压测 method(`rpc_methods` 字段)不同, 整合时两个 method 来源都要保留。
**权威依据**: fulllink §7(整合方案c, 权威)+ §3/§9/§10 + design §6.2.2(S1.4措辞已校正)+ callchain §1/§2/§6 + R-A/R-B/R-D。行号以代码实证为准。

### 单元 S2 — 参数 DSL param_spec(缺口 #1/#4/#9)
**涉及代码**: 6 family adapter `_build_params`(jsonrpc.py L46+ / tendermint.py L43+ / substrate.py L33+ / bitcoin_jsonrpc.py L54+ / rest.py L62 用 _meta.rest_paths / hedera_dual.py L86 委派)、cli.py `_get_param_format` L28-56、config_loader.sh `get_param_format_from_json` L683-696、tools/chain_adapters/param_spec.py(草稿)。
**现状(代码实证 2026-06-04, read_file 逐行 + grep caller 验证)**:
- **真实参数构造链路(单一 live 链, 非两条并存)**: blockchain_node_benchmark.sh:161 → target_generator.sh(spawn 子进程, 管 method 分配+round-robin, 零云字面"安全岛") → L74/248/264 调 `python3 chain_adapters/cli.py build-target/build-targets-batch` → cli.py `_get_param_format`(L28-56, fallback `single_address`) → adapter.build_vegeta_target → `_build_params`。**构造在 python 侧, bash 只分配 method**。
- **6 family `_build_params` 现状**: 单 `address` 槽 + param_format 枚举 if-else + default 兜底 `[address]`。jsonrpc.py 14+ 枚举(no_params/single_address/address_latest/latest_address/address_storage_latest/address_key_latest/address_with_options/block_number/block_number_int/transaction_hash/eth_call_object_latest/object_single...)/ substrate(no_params/single_address/storage_key/block_hash/address_with_block)/ bitcoin(no_params/single_address/address_minconf/txid)/ tendermint(→dict: no_params/single_address/height_param/abci_balance_query)。**rest.py L62 不用 param_format, 用 `_meta.rest_paths[method]` {method,path,body} = 已是声明式 DSL 样板**(method 不在则 raise)。
- **🔴 占位污染落点(eth_call/object_single, jsonrpc.py L86-97 实证)**: `eth_call_object_latest` 返 `[{"to": address, "data": "0x70a08231"+"0"*64}, "latest"]` —— **to 直接复用账户地址当合约地址(错!) + data 写死 balanceOf selector + 全0占位**。`object_single` 返 `[{"from":address,"to":address,...}]`。→ 节点返错/无意义 → per-method 归因失真(缺口连带 jsonrpc.py:84 tx_hash 占位同理)。
- **🔴 eth_getLogs 无构造分支(P1_RPC_ERROR 根因)**: jsonrpc.py `_build_params` 无 getLogs/filter 分支 → 走 default `[address]` 把地址当 filter → 必 -32602(audit 16 个 P1_RPC_ERROR 缺 filter 的根因)。fetch_active_accounts.py L327-332 的 filter(topics:[])是 fetch 内部抓 tx_hash 用, 非压测 method 参数。
- **🔴 bash 侧两个 0-caller 函数(成因四分类: (a)重构转移+(c)调用链切换, 非(d)无意义死代码 — 处置≠简单删)**: (a) `generate_rpc_json`(target_generator.sh L67, body 已委托 python cli.py) (b) `get_param_format_from_json`(config_loader.sh L683-700)。**git 实证**: 两者**同在 commit 6866cba "S2: adapter skeleton(6 protocol families)" 失去 caller** = 框架引入 python chain_adapters 新体系那次重构把构造链从 bash 切到 python 留下的老路(成因 a/c, 不是凭空垃圾)。**功能等价性核查(不完全等价!)**: python `_get_param_format`(cli.py L28, 注释自承 `Mirrors config_loader.sh get_param_format_from_json`)读 config/chains/<chain>.json 文件**无缓存**; bash 版读 CHAIN_CONFIG(env)+ **有 `CACHED_PARAM_FORMAT_<method>` 进程内缓存**(L687-694)。→ **缓存是 bash 版独有、python 版未接管的功能点**(若 python 高频读文件性能不足, 缓存需补到 python 侧, 属"重构遗漏功能"风险, 清理前必确认不需要)。**处置**: S2 param_spec 接入 + 确认 python 已完全接管(含决定缓存是否补)后, 才连带清理两函数 + export 行(config_loader.sh L718)。对照: `get_current_rpc_methods`(L668) 仍 4 live caller(target_generator.sh L17/107/309/310) **保留**。
- **🔴 param_spec.py 草稿现状(0 caller 孤岛, double check 与 design §4 schema 完全一致)**: 244 行, `_VALID_TRANSPORTS`(5: jsonrpc_list/jsonrpc_dict/rest_path/rest_query/rest_body)= design §4.1 维度A / `_VALID_SOURCES`(6: account/literal/block_height/tx_hash/contract_call/config_object)= design §4.3 维度C(注释明确"服从权威源不私拆 block_hash/block_number, 设计问题记 §6.6.5 留 B2/C") / `_VALID_SHAPES`(3: evm_call/aptos_view/tron_trigger)= design §4.2 call_object。函数: ParamSpecError/PARAM_FORMAT_PRESETS(22枚举)/expand_preset/resolve_param_spec/validate_spec(R2启动期校验)。**真问题=0 caller + 缺 spec→params 构造器(孤岛), 非 schema 错**(草稿是按 design §4 权威建的)。
- **config_loader 现状演进(file-notes 笔记已过时, 代码实证)**: UNIFIED_BLOCKCHAIN_CONFIG 内嵌 heredoc **已废弃**(L589 注释 `legacy UNIFIED_BLOCKCHAIN_CONFIG heredoc`), 改读 config/chains/<name>.json(L501/588 `S1.1 (5bd01a6+)`), config/chains 实际 **36 链**(非笔记说的内嵌8链)。target_generator 产物 body 必须 **base64**(Vegeta target 格式约束); 下游 master_qps_executor.sh 只按路径消费 targets_{single,mixed}.json 不解析字段 → S2 改 body 构造不影响下游(降风险)。
**重构目标(未做)**:
- chain template 加 `param_spec.<method>`(design §4.2: transport × slots/fields × source 3维), 框架据此构造请求, 替代 param_format 枚举硬编码。
- **3 维 DSL**: transport(jsonrpc_list/jsonrpc_dict/rest_path/rest_query/rest_body 5种)× slot/field(list下标/dict键/path占位符)× source(account/literal/block_height/tx_hash/contract_call/config_object 6种)。覆盖 184 实测 14 类参数形态(design §4.3 验证)。
- **6 family `_build_params` 改造**: 优先读 param_spec(DSL), 无则 fallback param_format 枚举展开成等价 param_spec(单一构造路径, 非两套并存; param_spec.py PARAM_FORMAT_PRESETS 已做枚举→spec 桥)。
- **接口签名改造(与 S1 强耦合)**: build_vegeta_target 单 address 槽 → (method, inputs:dict, rpc_url, param_spec), 四处联动(target_generator TSV/cli.py解析/base签名/_build_params), 缺一断链。
- **R2/R3 校验(cli.py 启动期 fail-fast)**: param_spec 缺失/解析失败必告警退出, 禁静默退化 [address](6866cba 对称fallback假绿教训, design S2.5)。
- **统一 4 套按链分派**(缺口#1): Python侧(fetch create_adapter chain_type + chain_adapters adapter_family)+ Shell侧(config_loader MAINNET case + get_block_height)。Shell 侧走 D5 声明式收敛(纯 Shell+jq 读 chain template, 不 fork Python)。
- **保留 _meta.adapter_family**(缺口#4): config_loader L597 `del(._meta)` 改为保留 adapter_family + block_height_spec, 否则 fetch 按 family 分派拿不到。
- **mixed weight 真驱动**(缺口#9): config_loader L626/L540/L674 取 rpc_methods.mixed(均权)→ 改读 mixed_weighted 加权; target_generator round-robin(L260 `account_index % method_count` 均权)改加权。**算法(语义乙=百分比, 见§3决策)**: ① 加载校验 `sum(weight)==100` fail-fast ② 加权 round-robin = 按 weight 把 method 重复进轮询数组(weight=30 进30次), 数组长度=100, 对地址轮询取模 → 该 method 自然占 30% ③ weight 是百分比直接用, 框架不再归一化(总和已=100)。**配套**: 36链 weight 现全=1需补真实占比(见§3"36链weight现状"条)。**注释要求**: target_generator 加权逻辑处 + config/chains schema 处都加注释"weight=百分比占比,一链总和=100"。
- **design §4 schema 缺的维度(真读6 family + chains文档挖出, 需补进 param_spec)**: ① bitcoin HTTP Basic Auth header ② substrate 可选参数(block_hash?) ③ 同链多 endpoint(hedera _meta.json_rpc_url/algorand node vs indexer) ④ per-request 协议路由(hedera _is_jsonrpc_method 按前缀) ⑤ 占位符"counts as success"妥协(接真值池后消除) ⑥ 链级 DSL 字段(chains文档 §7/§9: protocol_kind/rollup_type/module_set/denom_format/dual_address/finality/auth header/response_path — 与 method级 param_spec 分层, 见 §3 决策待定)。
- **param_spec.py 草稿现状**: 244行, _VALID_TRANSPORTS(5)/_VALID_SOURCES(6)/_VALID_SHAPES(3) 已对照 design §4 修正; 真问题=0 caller 孤岛 + 缺 spec→params 构造器; docstring source 列表与 _VALID_SOURCES 不一致(待修)。
- **复杂参数真值地基**: contract_call/filter 的真值见 §5.2 calldata池 + §5.3 filter矩阵 + §5.4 safety守卫。
**完成判定**: L1 每family param_spec 构造单测(byte==§3实测) / L2 cli.py build-target shim 对每(chain×method) / L3 整框架跑 mixed weight 生效 + 新 method 零代码可配 + 老 _get_param_format/枚举退役。
**🔴 S1+S2+B3 原子单元批次执行计划(2026-06-05 落盘, 可接续锚点 — 每批独立 commit+L1, 防重构改一半被压缩)**:
- **批1 接口签名改造(向后兼容)**: base.py L34-41 `build_vegeta_target(method,address,rpc_url,param_format)` → `(method, inputs:dict, rpc_url, param_spec:dict)`; 6 adapter 同步改签名(jsonrpc.py:38 / rest.py:81 / tendermint / substrate / bitcoin_jsonrpc:36 / hedera_dual); cli.py L70+L106 两处调用改传 inputs dict(暂 `{"account":[address]}` 兼容)。**批1 L1 门**: F2 184/184 不退化 + R0 12组过。**批1 不改构造逻辑**(只改签名+透传), 占位基线仍=10。
- **批2 param_spec 构造器 + jsonrpc 接入**: param_spec.py 新增 `build_params_from_spec(spec, inputs)→list/dict`(按 spec.transport+slots/fields 从 inputs 各池取值, 是 PARAM_FORMAT_PRESETS 已声明结构的执行端); jsonrpc.py `_build_params` 改调 resolve_param_spec+build_params_from_spec(枚举退役为 preset)。**批2 L1 门**: jsonrpc 链每 method 构造 == §3 实测 byte。
- **批3 推广 5 family + 老枚举退役**: rest/tendermint/substrate/bitcoin/hedera 各接 param_spec 构造器; 6 adapter 老 `_build_params` if-else 删除(成 dead 后删, 成因d); cli.py `_get_param_format` 退役(resolve_param_spec 接管)。**批3 L1 门**: F2 L2 占位基线下降(真值池接入后) + R0 过 + ci_smoke 19/0。
  - **🔴 批3 真实分解(2026-06-05 实证 5 family method×param_format 分布)**: 不是简单"补 PRESET"。两套机制:
    - **批3a(jsonrpc 类, 能立即切)**: substrate(path_* 之外全在 PRESET)/ bitcoin(全在 PRESET)/ tendermint dict 类(补 jsonrpc_dict PRESET: single_address→{address}, height_param→{height}, abci_balance_query)。这些 transport=jsonrpc_list/dict, 走 build_params_from_spec。切构造器 + 删老 _build_params。
    - **批3b(REST 构造, 归 S3.8, 另一套机制)**: rest/hedera REST 侧 + 所有 `path_*`(path_addr/path_address/path_height/path_hash/path_pool_id/path_*_base32/path_*_int 等)+ `body_*`(body_addresses_array/body_tx_hashes_array/asset_policy_name)+ `query_*`(query_params/query_pagination/query_epoch_int)+ ton 自然语言枚举。**这些不走 list/dict 构造器, 走 rest.py 的 path 占位替换({addr}/{hash}/{height})+ body 模板 + query string 构造**(S3.8 REST 声明式构造)。rest.py 现仅替换 `{address}` 单槽 → 批3b 扩展为通用占位 + body/query。
  - **∴ 批3a 先做(jsonrpc 干净切), 批3b = S3.8 REST 构造统一(工作量大, 与 S3 REST 处理合并)**。
  - **🔴 批3b REST 声明式构造详细设计(2026-06-05 token-level 实证 rest_paths 全貌)**:
    - **现状两种 REST method 形态(实证)**: ① method 名本身是 path 模板(`GET /cosmos/bank/.../{addr}`, cosmos/celestia/injective/osmosis/sei 5链, **rest_paths 空**, param_format 声明占位类型 path_addr/path_hash/path_height/query_pagination) ② method 名是逻辑名 + rest_paths 映射 path(cardano GET_TIP→/tip, ton getAddressBalance, **rest_paths 有**)。
    - **🔴 占位污染(实证, 像 jsonrpc 占位污染的 REST 版)**: algorand/aptos/tezos/hedera 的 rest_paths path 把 `{txid}/{round}/{asset_id}/{hash}/{addr}` **全硬塞成 `{address}` 单槽**(method 名声明 {txid} 但 path 写 {address}) → 占位语义被抹平, 取值全来自 account 池(错: txid 不是 account)。**批3b 修复=path 占位恢复语义名 + rest.py 按占位名从 inputs 对应池取值**。
    - **统一构造规则(声明式 DSL, 占位名=取值池声明)**: param_format → param_spec transport(rest_path/rest_query/rest_body)+ 占位映射:
        `path_addr/path_address`→{addr}/{address} from account池 / `path_hash`→from tx_hash池 / `path_height/path_round_int`→from block_height池 / `path_asset_id_int/path_pool_id`→from business池(asset_id/pool_id) / `query_pagination/query_params/query_epoch_int`→query string / `no_params`→无占位 / `body_addresses_array`→POST body 模板 from account / `body_tx_hashes_array`→from tx_hash / `asset_policy_name`→from business(policy+asset_name) / ton 复杂(workchain/shard/seqno)。
    - **实现**: ① PARAM_FORMAT_PRESETS 补 path_*/query_*/body_* → rest_path/rest_query/rest_body transport 的 spec(声明占位+source池) ② rest.py 按 param_spec transport 构造: rest_path=占位替换(method名path模板, 占位名→inputs池取值) / rest_query=path+query string / rest_body=POST body 模板从池填 ③ rest.py 不再 _account_from_inputs 单槽, 按 spec 占位多源取值。
    - **完成判定**: F2 KNOWN-PENDING 大幅下降(rest 类转 healthy 或转 S1池待供给) + R0 test_10 KNOWN_BROKEN_CLI 12→大幅减 + ci_smoke 19/0。占位污染恢复语义名后 path 取值正确(txid 从 tx_hash 池非 account)。
    - **🔴 批3b 删 _resolve_path 引入的真问题(2026-06-05 用户反问"是否 token-level 确认"逼出的穷举实证, 我删码未做等价性核对)**: 老 _resolve_path 从 `config.rest_paths[method].body` 读 body 模板替换 `{address}`; 新 build_vegeta_target rest_body 分支从 `PRESET.body_template` 读(占位 `{account}` 等)。**两个 body 来源, 我切到 PRESET 未核对等价**。穷举核对结果:
      - cardano 4 个 body method(POST_ADDRESS_INFO/TX_INFO/BLOCK_TXS/ASSET_INFO): PRESET body_template 覆盖 ✅ 功能没断, **但 config.rest_paths.body(用 {address})成 dead 双源数据**(不再被读)→ 批3b收尾该清理 config 里的旧 body 或统一单源。
      - **🔴 ton runGetMethod: PRESET 无 body_template, config 有 body 模板 → 删 _resolve_path 后 body 不再构造**(ton 在 KNOWN_BROKEN_CLI broken 状态暂时掩盖了这个删除退化)→ 批3b收尾必修(补 ton PRESET body_template 或显式 param_spec)。
      - **教训**: 删码(_resolve_path)前必做老/新等价性穷举核对(token-level skill 铁律), 我图省事只 grep caller=0 就删, 漏了 body 来源迁移的等价性。门绿(R0/F2)没抓到因 ton 本在 broken 掩盖。
- **批4 S1 fetch 多池 + mixed weight 真驱动**: fetch_active_accounts.py create_adapter L673 补 bitcoin/UTXO adapter(缺口#2); 写盘 L816-818 改多池 account/tx_hash/block(缺口#3); config_loader L597 保留 _meta.adapter_family(缺口#4); config_loader L540/626/674 读 mixed_weighted + target_generator L260 加权 round-robin(缺口#9, 百分比语义见§3); 36链补真实占比(§3规则)。**批4 L2/L3 门**: fake-node mixed 真跑 weight 比例生效 + 需 tx_hash 的 method 不再占位。
**权威依据**: design §4(DSL)+ §6.2.3 S2 + fulllink §5阶段2 + callchain §4.2 调用链不断裂点表 + 184 实测文档 + §5.2/§5.3/§5.4 独有事实。

### 单元 S3 — 响应链 + 关联键 + 归因(缺口 #5/#6/#7/#8/#11/#12)
**涉及代码**: 4 family adapter body id=1(jsonrpc.py:42/104, substrate.py:29/49, tendermint.py:39/62, bitcoin_jsonrpc.py:40/67 共8处)、proxy(handler.go/sink.go/jsonrpc.go:88/rest.go:74)、analysis/per_method_attribution.py、visualization/per_method_charts.py:L241、report_generator.py:4303-4309、common_functions.sh get_block_height、lib/proxy_lifecycle.sh:143。
**现状(代码实证)**: proxy sink 9列(无req/resp_bytes, design §5.7 校准 Q4-9 文档过时); per-method 归因实测频次权重(design §5.7, 非Q4-7预设1/10/100); 响应主路径不解析body(handler.go:103 不缓冲); parse_block_height 仅 health check(生产 dead path)。
**重构目标(未做)**:
- **S3.1 重建 request_id 关联键**(缺口#5): 4 family 8处 body 硬编码 id=1 → 唯一 id(base.py helper); rest.go RequestID="" 需在 TargetBuilder 注入 header/query X-Request-Id + rest.go 读 req.Header(非body); batch 关联键=(RequestID,BatchIdx)复合。proxy Phase 0.5 启动时序绝不动(否则 vegeta 绕过 proxy)。
- **S3.2 response_spec 响应DSL**(缺口#6/#7): chain template 声明响应提取(design §5: envelope 5种×locator 3种×type 5种, 覆盖15类实测响应)。三端同源(param_spec/proxy_extraction/response_spec 都以 method 为键 + method 名串联)+ 交叉校验防 handler.go:77 __unmatched__ 静默消失。**响应DSL 仅 PROXY_RESPONSE_CAPTURE 开关开 + health check 用, 非压测主路径**(design §5.0/§5.6)。
- **S3.3 attribution 补四维**(缺口#8): per_method_attribution 读 unified CSV disk/net 列(数据已采)+ per_method_charts.py:L241 只画cpu→补 mem/EBS/Net 四维。⚠️ 用生产 unified CSV 真实列名 mem_used(非默认 mem_used_mb, 否则归因恒0静默, report L4305已修)。出图统一 matplotlib+UnifiedChartStyle(已定, 非自拼SVG)。
- **S3.4 减 proxy 基线**(缺口#11): attribution 读 proxy_self.csv 减 proxy 自身 cpu/mem(Q4-10/ADR-0004, 现生产3处采集消费0处=死数据)。
- **S3.5 块高归一**(缺口#12): get_block_height 8链case → 读 block_height_spec(五档 sync_strategy, 见块高实测文档)。Shell DSL化不fork Python(D5, 每秒高频防污染测量)。get_block_height 本地自查不打外部主网(D5.1, 防限流)。Python parse_block_height 是 dead path(仅测试一致性)。hex/dec 统一 _decode_height。CSV 6字段向后兼容(mainnet_block_height 改名 network_block_height 需同步3 reader)。块高契约: 五档产出落后量→block_height_time_exceeded.flag→bottleneck 场景C(不变)。
- **S3.7 协议错配修复**(34 method, callchain §2.1): tendermint 整族(adapter构造jsonrpc/配置LCD REST path)走 rest_paths declarative; polkadot 混协议走 hedera_dual 式 per-request 路由; near dict / tron REST body / avax dict。复用 rest.py + hedera_dual.py 现成范式, 不新造。按链非按family。
- **🔴 S3.8 REST path 占位参数路由(2026-06-05 fake-node 乙方案实测暴露)**: 带路径参数占位符的 REST method(`GET /api/v1/accounts/{addr}` / `{hash}` / `{height}` / `{block}` 等, hedera/algorand/aptos/cosmos/tezos/polkadot-sidecar 大量)—— ① **生产 rest.py `_resolve_path` 只替换 `{address}` 单槽**(L69), `{addr}`/`{hash}`/`{height}`/`{block}`/`{vp}` 等占位不替换 → 真值供给缺口(S1 多池 + S2 接口 inputs:dict 要补)。② **fake-node `resolvePathMethod` 三规则(exact/VERB_NAME/last-segment)都不匹配占位符路径** → 带占位的 REST method 在 fake-node path 模式 404(实测 hedera /api/v1/accounts/0.0.2 → 404, smoke 已标 KNOWN graceful 404)。S2/S3 REST 处理必须支持路径参数占位符的【构造端替换】+【fake-node 匹配端】两侧。
**完成判定**: L1 关联键/response_spec/四维单测 / L2 proxy全链路 id关联 / L3 整框架 mixed 四维归因出图 + 响应按method关联 + 块高36链 + 场景C触发。
**权威依据**: design §5/§6.2.4 S3 + fulllink §4/§8 + 块高实测文档 + §5.6 归因机制。

### 单元 S0 — 前置工具链(L3 地基)
**目标**: 防"L1+L2绿/L3未知"债累积(parallel-entry multi-stage L3 铁律), S0 一次性建好不拖到最后。
- **S0.1 mock 节点**: 复用 tools/fake-node/(184 fixture 已入库 commit 91f380b)+ mock_rpc_server.py。6 family 本地起 mock 返 fixture。
- **🔴 R-FN fake-node 按 method 返回对应响应结构(用户需求, 2026-06-05 补记 — 之前漏记)**: fake mode 必须按框架 single/mixed 配置, **压测时逐 method 请求返回该 method 对应的真实响应结构**(method A→A的响应/method B→B的响应), 使 fake-node 压测路径与真实节点一致 → per-method 资源监控+归因才有意义。**现状已实现机制**: 6 family handler 全 byte passthrough(jsonrpc/substrate/rest L58-81: `Handle(method,_,fixture)` 按 method 名选 `fixtures/<chain>/<method>.json` 字节原样返回, `len(fixture)==0` → 报错)。**∴ fixture 是 fake-node 跑通的硬前提**: 任一 method 缺 fixture, fake-node mixed 打到它即 `no fixture wired` 报错。fixture 补全不是锦上添花, 是 S0 前置必做(推翻旧"后置"描述)。
- **✅ R-FN 乙方案已落地(2026-06-05, fake-node method 单一真相源)**: 原 fake-node method 列表来自 `configs/<family>.yaml`(与 config/chains 漂移 89 method → mixed 大量 404)。**改 fake_node.go: method 列表改从 config/chains/<chain>.json 的 rpc_methods 加载**(新增 buildMethodsFromChainTemplate + fixtureNameFromMethod 双规则), yaml 降级为仅 tier 微调 + IO 配置源。**验证**: 36/36 链启动 loaded=N missing=0; ci_smoke PASS=19 FAIL=0(修了 5 个 yaml-only 幽灵 method 探测: polkadot system_chain→chain_getHeader / cosmos /status→blocks/latest / hedera eth_blockNumber→eth_getBalance + solana getSlot→getBlockHeight); bitcoin getreceivedbyaddress/estimatesmartfee 之前 404 现返 fixture。fake-node 单测+R0 老测未破坏。**遗留**: REST path 占位路由(见 S3.8)。
- **S0.2 workload**: vegeta(保留, 见§3决策)+ target_generator.sh, 对 mock 发 mixed。
- **S0.3 e2e harness**: 真 L3 = blockchain_node_benchmark.sh 无 skip + artifact-assert HTML/PNG(非 e2e_smoke --validate, 那是smoke)。
- **S0.4 baseline audit**: tests/test_chain_adapters.py(R0) 记改造前基线。
- **F1 adapter_family CI 门**(✅已完成 ci/check_adapter_family.sh, ⏸️待挂CI流程): 36链必有 _meta.adapter_family + 在6注册family内 + 缺失fail-fast。**非自动推断**(proto=rest 横跨3 family无法推断, 领域知识人工填+CI校验)。
- **F2 e2e method 构造验证**(GAP-B): e2e 现黑盒探活(mock硬编eth_blockNumber)不验method构造 → 补 method×chain build-target 断言 address进body/url + param顺序(parallel-entry Step4-bis, 防6866cba对称fallback)。依赖 B1/B3 接口定稿后做。
- **🔴 S0 fixture 覆盖(2026-06-05 反向核对最终确认, 推翻一切旧数字)**: **176/184 有 fixture, 真缺仅 8 个**(全是类B mock, 无类A补录)。**文件名双转换规则(实证, 之前误判4次的根因)**: ① method 带 HTTP 动词前缀(含空格, 如 `GET /v2/x`)→ 空格→`_` + `/`→`_`(得 `GET__v2_x`, 双下划线); ② method 以 `/` 开头无动词(如 `/status`)→ `/`→`_` 去前导`_`(得 `status`)。**核对必反向**(读真实 fixture 文件名 vs config method, 不凭规则推测正向 — injective/celestia/tron/algorand/aptos 全有 fixture, 误判缺失纯属转换规则猜错)。**真缺 8 个(全公开endpoint测不到→按官方文档mock, 用户拍板甲方案)**: ① bitcoin/dogecoin getreceivedbyaddress(wallet类禁, numeric标量, 官方结构已查 `{"result":0.05,"error":null,"id":"curltest"}`) ② acala/kusama/polkadot system_account(substrate state_getStorage 返 SCALE hex, 按 frame_system AccountInfo 结构 mock) ③ polkadot Sidecar REST(GET /accounts/{addr}/balance-info, GET /blocks/{n}, GET /pallets/staking/progress, 普通JSON)。**mock fixture 必须标来源(官方文档非实测), 禁凭印象编**。**SCALE 响应提取是 NS-3 DSL 真边界**(response_spec 提余额需客户端SCALE解码)→ system_account 标 KNOWN_BROKEN(fake-node byte passthrough 能重放✅, 框架声明式提取标边界), 不阻塞 fake-node。**完成判定**: 184/184 method 都有 fixture + fake-node mixed 全 method 不报 no-fixture + 一致性脚本(固化双规则)0 缺口。
**完成判定**: 6 family mock可起 + vegeta可打 + e2e真跑出HTML + baseline数字 + F1挂CI + F2 harness。**S0 不过不进 S1**。
**权威依据**: design §6.2.1 S0 + §6.5.3 治理缺口 + §6.6 S0执行记录。

## 2. 调用链依赖拓扑(改代码顺序)
> 哪些单元必须先于哪些做(防孤岛/断链)

```
S0 前置工具链(mock/workload/e2e/baseline/F1/F2)
  ↓ 不过不进 S1
S1 输入供给层(InputProvider 多池) ─┐
  ↓                                  │ S1+S2+B3 是原子单元不可拆
S2 参数 DSL(param_spec)─────────────┤ (build_vegeta_target 取值 + param_spec.source
  ↓ (接口签名 inputs:dict 一并改)    │  + 接口签名 单address→多源 强耦合, 拆=孤岛)
S3 响应链 + 关联键 + 归因 + 块高归一 + 协议错配
```
**强耦合(必须一并改, 缺一断链)**:
- **S1+S2.5+B3 共享 build_vegeta_target 接口瓶颈**: 单 address 槽 → inputs:dict, 分开改=N次改同一签名。
- **S1 必先于 S2**: 输入供给是地基, 否则 param_spec 声明 tx_hash source 也填不出真值→退回占位(callchain §6.5)。
- **fetch CHAIN_CONFIG 保留 _meta.adapter_family**(改 config_loader del._meta)是 S1 整合 + S2 family分派的前置(缺口#4)。
- **S3.7 协议错配**复用 S3.2 response_spec + rest_paths 范式, 按链处理。
- **块高 S3.5** 与 S2.2b Shell DSL化同走 D5(读 chain template 声明), 同源不冲突。
**family 分波(风险倒序)**: jsonrpc(16, 最稳先行)→ substrate → tendermint → bitcoin → rest → hedera_dual(殿后)。每波 L1+L2+L3 全过才 done。

## 3. 已锁定决策(带依据)
- **vegeta 保留**(不换): 开环恒定速率(避免 coordinated omission)+ 文件驱动异构 target + Go 零依赖, 命中区块链 HTTP 异构压测。候选 k6/wrk/bombardier/locust/ethspam 均不如。压测发生器层不动。撤销线: 单节点>50k QPS 或需多机分布式。依据 vegeta-vs-alternatives-research。
- **出图统一 matplotlib + UnifiedChartStyle**(2026-06-02 用户拍板): per-method 四维图参照 _generate_resource_distribution_chart, 不用自拼 SVG(避免 HTML 混排 SVG/PNG 体系割裂)。
- **block_height_spec 单一声明源收编三套**: 现状 Shell get_block_height(8链case live)+ Python parse_block_height(36 family dead)+ _meta.health_probe(5链 dead)三套并存; 不留债=block_height_spec 作单一声明源, 三套读同源(非新造第4套)。五档 sync_strategy(dual_height/slot_diff/sync_progress/peer_metrics/freshness)。
- **mixed weight 直接复用 mixed_weighted 零新增**(决策B): 36/36链已有 mixed_weighted(weight值都=1, 代码没读), S2.4 直接读它驱动, 不另造字段。
- **🔴 weight 语义 = 百分比占比, 总和必须 = 100**(2026-06-05 用户拍板, 语义乙): `mixed_weighted[].weight` 是该 method 在 mixed 压测流量中的【百分比占比】(整数), 一个链所有 method 的 weight 之和 **必须 = 100**(如 5 method 配 40/30/20/10/0 ❌不行,须凑满100; 典型 30/25/20/15/10)。**理由**: 贴合实际业务——使用时按不同 method 的真实调用占比配置(用户原话:"实际业务中会有多个方法,根据不同占比配置")。语义直观(直接读就是百分比), 注释必须写明"weight=百分比,总和=100"。**校验(硬约束5 fail-fast)**: 框架加载 chain.json 时校验 `sum(weight)==100`, 不等于 100 → 告警退出, 禁静默归一化(避免用户配错却被框架悄悄改)。**落地**: 加权 round-robin(weight=30 → 该 method 在轮询数组出现 30 次), 压测流量按占比确定可复现(不用随机抽样, vegeta 需可复现)。**配置端(百分比占比)与归因端(实测频次占比 `count(method)/total`)语义一致, 闭环**。
- **🔴 36链 weight 现状=占位1(和≠100)→ S2 配套补真实占比**(诚实标注, 非"字段已就绪"): 实证 36/36 链 mixed_weighted weight 全=1, 和=method数(4~7), **均 ≠ 100**。语义乙落地后, S2.4 必须给 36 链补真实百分比占比。**补占比规则(实施者照填, 免临场判断)**: (a) **有 §5.1 资源画像的链按画像粗分档**——重资源 method 给高占比体现真实压力侧重(如 solana getProgramAccounts 重 / EVM eth_call·eth_getLogs 重 / eth_blockNumber 虽轻但轮询量大, 参 research 03b 设计意图 40/30/20/10); (b) **无画像的链整数均分**——`base = 100 // n`, 余数 `100 - base*n` 累加给列表第一个 method(保证整数且和=100, 如 7 method = 16+14×6 或 15×6+10); (c) 填完每链脚本校验 `sum==100`。用户后续按真实业务调, 框架不锁死。**完成判定**: 36/36 链 sum(weight)==100 校验通过 + L3 mixed 跑起来不 fail-fast。**这是 S2 的配套工作项, 不做=校验 fail-fast 全链跑不起来**。
- **mainnet_block_height 改名否决**(默认): 改 network_block_height 断 performance_visualizer 等 reader 无兜底, 收益仅语义 → 保留旧名加注释(若必改需同步3 reader)。
- **param_format 枚举作 param_spec 预设快捷**(B1): 单一读取路径(param_spec有→用/无→PARAM_FORMAT_PRESETS展开/都无fail-fast), 避 parallel-entry。
- **D5 Shell DSL化不fork Python**: 块高每秒高频, Shell get_block_height 纯Shell+jq读block_height_spec, 不调Python(防fork污染节点资源基线测量)。
- **F1 adapter_family CI校验非自动推断**: proto=rest横跨3 family无法推断, 人工填+CI校验在6注册family内。
- **fixture + 请求示例入库**(用户2026-06-02拍板, 突破"fixtures不进git"铁律): 因无法部署36真节点+公共节点限流, clone后无法现录 → 入库供离线二次开发(写明破例理由防后续按旧铁律删)。
- **响应DSL定位瘦身**(design §5.0, 用户两次元问句推翻): 压测主路径不解析响应body(对NS-2资源归因零信息量), response_spec 仅 PROXY_RESPONSE_CAPTURE开关 + health check块高用。
- **🔴 链级DSL字段 = 独立两层 schema(决策乙, 2026-06-05 用户拍板)**: chains文档§7/§9积累 protocol_kind/rollup_type/module_set/denom_format/dual_address/finality/auth/response_path 等链级字段(design §4 没纳入), 收敛为"7必+1推+4缓"(moonbeam汇总)。**已决: config/chains/<链>.json 分两层 —— `chain_meta`(链级, 整链共享: endpoints/auth/protocol_kind/finality/response_path 等) + `param_spec`(method级, 每method一份: 参数怎么构造/响应怎么解析)。** 理由: 链级字段与具体 method 无关, 单层混放会与 method 名撞名+语义不清, 两层边界清晰、各自独立演进(符合"更优雅统一"诉求)。S2 param_spec.py 接入时按两层结构读 JSON。polkadot SCALE/UTXO method chaining 是 NS-3 零代码的真边界(纯DSL无法表达, 需sidecar/adapter, 标 KNOWN_BROKEN 不阻塞)。

## 4. 不留债硬约束(design §6.5.5 + 全程遵守)
1. **字段名全保留**(csv_schema_registry 单源, block段6字段): 不改名→8 consumer 零断裂; mainnet_block_height 改名=否决。
2. **block_height_diff = 最硬契约**(performance_visualizer required 无兜底 + 3 consumer): 列名+required不变, 五档产出落后量都填这列。
3. **配置债收敛单源**: BLOCK_HEIGHT_DIFF_THRESHOLD(internal_config L59=50) 与 rpc_deep_analyzer.py L35 SYNC_THRESHOLD=20 合一。
4. **接口签名联动改**: build_vegeta_target 单address槽→(method,inputs:dict), 四处一并改缺一断链。
5. **fallback fail-fast**: param_spec 缺失/解析失败必告警退出, 禁静默 [address](cli L55/jsonrpc L97/各adapter default, 6866cba教训)。
6. **D5 Shell不fork Python**: 块高每秒高频纯Shell+jq, 防fork污染测量。
7. **L3 每阶段全过才done**(parallel-entry多阶段): 每S阶段整框架e2e, 块高场景C契约必验。
8. **死代码处置四分类**(用户2026-06-04): grep 0 caller≠可删, 必读逻辑+查git+扩范围验等价, 分(a)我重构弄断(b)重构遗漏功能(c)调用链断裂(d)真无意义; bc修复接回不删。
9. **每个功能点真完成判定**: (a)生产主链真caller≥1 live (b)L3触达 (c)老路退役 (d)commit SHA。"建模块+单测"≠完成(param_spec.py孤岛教训)。

## 5. 独有事实合并节(从 research_notes 01-07 合并, 原文件待删, 来源标注)

> 本节合并 research_notes 早期调研的【独有内容】(两份实测文档 184+块高 没有的维度): 资源画像 / calldata 池 / fixture 工程 / safety 守卫 / per-method 归因机制。合并后原 research 文件删除(执行 A: 彻底单源)。**来源逐条标注供追溯**。⚠️ research 01-03b/05/06 头部的 "8 链 OUT-OF-SCOPE / 真 8 链" 标注是 8 链时代(v1.4, 2026-05-20)遗留, 现 36 链已全实测推翻, 合并时已剔除该过时标注。

### 5.1 per-method 资源画像(weight 配置依据, 来源 research 01/02/03/03b)
> 用途: NS-2 per-method 资源归因的 weight 粗粒度配置依据(Q4-7: 公开资料先配粗粒度 1/10/100 三档, 后期实测迭代)。**注: 流量占比数字是定性, 不作精确权重, 用户按实际校准**(research 02 §四原话)。

**EVM(research 01)**: eth_call(CPU+Mem, EVM全量执行, 1-100ms可到秒级) / eth_getLogs(CPU+Disk, bloom+receipt扫描, 10ms-数秒, 大范围退化全扫) / eth_estimateGas(极高, 二分重放eth_call, 实测7s vs eth_call 60ms) / debug_traceTransaction(CPU+RAM双重, 100ms-数十秒, archive) / eth_blockNumber(Memory, µs, 但流量榜第二=轮询心跳隐形QPS杀手) / eth_getBalance/getCode/getStorageAt(Disk-Random trie, sub-ms-ms)。Geth 默认不暴露 per-method metric(需改源码或代理拦截)→ 强化 proxy(NS-2)必要性。
**Solana(research 02)**: getProgramAccounts(CPU+Mem+Disk 极重, 全AccountsDB扫描无分页, 100ms-数十秒, OOM头号杀手, Helius/Triton/Alchemy 全限制; 来源 Solana issue#26210 + Helius "Why getProgramAccounts is hard") / **getBalance 反直觉略重于 getAccountInfo**(deserialize-then-discard 多一道) / getMultipleAccounts(N次查并发) / getBlock(Disk+Net) / getSlot/getBlockHeight(Memory <1ms 但占量大头)。
**Sui(research 02)**: sui_getObject(Disk单点) / multiGetObjects(>20 batch 超线性 cache驱逐) / queryEvents/queryTransactionBlocks(indexer扫描)。Mysten 限制: 50 item(multiGet)/1000 result(query)。
**Bitcoin(research 03)**: getblock(verbosity=2, I/O+CPU, 大块数十MB带宽瓶颈) / getrawtransaction(有txindex 1ms 无则历史tx报错, txindex需50-80GB) / scantxoutset(CPU+I/O极高, 数十秒-分钟, 遍历1.5亿UTXO, EXPERIMENTAL公开节点禁) / estimatesmartfee(Memory <1ms)。**Bitcoin Core 原生不暴露 per-method metric, 8链中唯一需外挂exporter/代理拦截**(强化 proxy 必要性)。
**Starknet(research 03)**: starknet_call(CPU极高 Cairo VM) / estimateFee(批量是DoS向量, 公网均限速) / getStateUpdate(state diff MB级)。**实现差异: Pathfinder(Rust, SQLite) vs Juno(Go, Pebble)**, Pathfinder 历史状态查询优于 Juno, 高并发更稳。
**EVM L2(research 03b)**: scroll(reth, eth_*完全兼容, ~50-200GB状态) / polygon(bor+heimdall双进程, ~3TB archive, 150TPS高IOPS)。出块快(scroll 3s/polygon 2s)放大 eth_blockNumber 轮询压力。**mock 复用 handle_evm**(mock_rpc_server.py CHAIN_HANDLERS), **mixed 权重默认 40/30/20/10**(设计意图, 代码实测是 round-robin 均权=R5缺口, mixed_weighted 实际 weight 都=1)。
**per-method metric 暴露端口(research 02 §五, 块高文档§93/§98 印证)**: Geth/Bitcoin Core/Erigon/Nethermind 默认**不**按 method 暴露(需改源码或代理拦截 → 强化 proxy NS-2 必要性); agave(solana :8899) / **sui-node :9184**(json_rpc_request_latency + state_sync highest_known_checkpoint) / **aptos-node :9101**(aptos_api_* + highest_advertised_data) **暴露 per-method 维度**。sui/aptos 网络最高仅在 metrics 端口(块高 peer_metrics 档)。

### 5.2 calldata 池构造(contract_call source 真值来源, 来源 research 04 §4)
> design §4 param_spec 声明 `source:contract_call` {to,data}, 但**没说 to/data 真值从哪来**。本节补: contract_call 的 calldata 真值来源 = 高频 selector + calldata 池。**这是 S1 contract_call 输入供给 + S2 param_spec contract_call source 的真值地基**。

**高频 ERC-20 selector**: totalSupply()=0x18160ddd / decimals()=0x313ce567 / symbol()=0x95d89b41 / name()=0x06fdde03 / balanceOf(address)=0x70a08231+32B padded addr / allowance=0xdd62ed3e+2×32B。
**ERC-721/1155**: ownerOf(uint256)=0x6352211e / tokenURI=0xc87b56dd / balanceOf(addr,id) 1155=0x00fdd58e。
**DeFi**: Uniswap V2 getReserves()=0x0902f1ac / V3 slot0()=0x3850c7bd / Chainlink latestRoundData()=0xfeaf968c / Aave V3 getReserveData=0x35ea6a75 / Multicall3 aggregate3=0x82ad56cb。
**calldata 池生成**: pad32 + selector + padded addr(纯 shell+jq, research 04 §4.4)。**fixture 来源**: Etherscan txlist / Dune ethereum.traces staticcall / The Graph subgraph / Alchemy enhanced API。
**eth_call state override(第3参)**: {to,data,from,gas,gasPrice,value} + state override {contract:{balance,code,stateDiff}}(research 04 §1.6, design §4 call_object 只有 to/data, 这是完整字段)。
**eth_getLogs filter 完整结构**(research 04 §1.8): {fromBlock,toBlock,address(单值或数组),topics(OR数组+null通配)} 或 {blockHash}。

### 5.3 复杂参数 filter 矩阵(jsonrpc_dict 嵌套, 来源 research 05)
> design §4 给了 transport 维度, 但没给复杂 dict/filter 的真实嵌套结构。本节补 S2 复杂参数实现的真值地基。

**solana getProgramAccounts**(research 05 §1.3): params=[programId, {commitment,encoding,dataSlice:{offset,length},filters:[{dataSize},{memcmp:{offset,bytes,encoding}}]}]。厂商约束: Helius 必须含 filter 否则-32602 / Triton dataSize 须第一位 / QuickNode dataSlice 缺失truncate。
**sui suix_queryEvents filter 字典**(§2.4): {All:[]}(killer) / {Transaction:digest} / {MoveModule:{package,module}} / {MoveEventType} / {Sender} / {TimeRange} / {And/Or:[...]}。
**starknet_getEvents 过滤矩阵**(§4.2): {filter:{from_block,to_block,address,keys(二维数组: 外层=event key位置, 内层=该位置OR列表),chunk_size≤100,continuation_token}}。address+key 全空+宽block range=killer。
**sui getObject options 成本**(§2.2): showType/showOwner(1.1×)/showContent(1.8-3×)/showDisplay(2-4×)/全true(4-6× killer)。
**aptos /v1/view**(05 §3.2): {function,type_arguments[],arguments[]}(Move view, design §4 rest_body call_object shape=aptos_view)。

### 5.4 safety 守卫默认值(node-killer 防护, 来源 research 04/05/06)
> 184 method 中部分是 node-killer(无filter的getProgramAccounts/scantxoutset/debug_trace等), 框架加载 chain.json 时先校验 safety, fail-fast。**这是 S2/S3 必须保留的守卫机制, design §4 没覆盖**。

| 守卫 | 默认值 | 依据 |
|---|---|---|
| eth_getLogs.safety_max_block_range | 1024 | Infura/Alchemy硬限10000, Cloudflare800, 自建geth>2k P99恶化 |
| eth_getLogs.max_response_size_mb | 10 | Alchemy/Infura 硬限 10-150MB |
| eth_feeHistory.max_block_count | 1024 | EIP-1559 通用上限 |
| debug_traceTransaction.enabled | **false** | P99 10-60s, 需 --allow-trace |
| eth_call.max_gas | 50000000 | geth --rpc.gascap |
| getProgramAccounts.requireFilters | **true** | Triton/Helius/QuickNode 主网已强制 |
| getBlock.transactionDetails | "signatures" | 默认最轻 |
| getSignaturesForAddress.max_limit | 1000 | Solana 官方上限 |
| scantxoutset/dumptxoutset/gettxoutsetinfo.enabled | **false** | 锁UTXO集分钟级, 绝不压测 |
| starknet_getEvents.require_address_or_key | true | 防全表扫描 |
**执行准则**: runner 加载 chain.json 先校验 safety; method.weight>0 且 safety=false/超限 → fail-fast。CLI `--unsafe-allow=...` 临时解锁写 manifest。

### 5.5 fixture 池工程(S1 输入池设计依据, 来源 research 06)
> S1 输入供给层(account/tx_hash/block/utxo/calldata 多池)的容量/采样/刷新工业界依据。

**双层架构**: `fixtures/`(仓库内基线, 入库, ≤50KB/文件≤200KB/目录, CI冒烟) + `fixtures.d/`(用户大池, gitignore, 5-50MB, 真实压测)。业界 fixture 极少超 10k/类。
**每链池**(EVM): addresses_hot(50, hot10+warm40)/cold(100) / tx_hashes(100) / blocks_range / contracts_erc20(10主流) / topics_logs(5) / slots(8)。基线≈15-25KB, 用户池1-5MB。
**4 种 sampler**(research 06 §3.3): uniform(等概率, tx/cold) / weighted(按weights_field, 合约/program) / sequential(顺序步进绕回, eth_getLogs区段) / hot_cold_mix(hot_ratio概率取hot否则cold, 账户类模拟真实流量)。**hot/cold 比默认 0.2**(Zipf top20%=80%流量, Cloudflare/Alchemy)。**业界工具来源**: ChainForge(chainbound)/ paradigm flood(jsonrpcbench)/ Versus(Infura, CSV-driven)/ paradigm rpc-bench。
**采样 schema**(chains/<chain>.json): pools{file,format} + methods{weight, sampler{kind,pool,hot_ratio}, params_template, calldata_templates}。**注: 这套 sampler/params_template 是 research 06(2026-05-19)的另一套设计, 与 design §4 param_spec(transport×slot×source)是不同维度** —— param_spec 管"参数怎么构造", sampler 管"从池里怎么采样"。两者互补, S1/S2 实现时 param_spec.source 指定取哪个池, sampler 指定怎么从池采样。
**刷新**: fixtures/ 手动季度刷; fixtures.d/ cron(hot池每天/小时, blocks_range每次跑前)。manifest.json 记 fetched_at + latest_block_at_fetch + sha256。**漂移容忍**: 不锚定block hash, 小时-天级(blocks_range≤6h EVM/30min Solana, tx_hashes≤7天, addresses_hot≤14天)。

### 5.6 per-method 归因机制(NS-2 核心, 来源 research 07)
> proxy 采集 method 时序 + 分析层加权 group_by 归因资源(Q4-7)。proxy sink 9 列(timestamp_ns/method_name/protocol/request_id/batch_idx/status_code/latency_ms/upstream/client_addr)。**响应业务内容对资源归因零信息量**(压测主路径不解析响应 body, 见 184 文档头 + design §5.0)。权重=实测频次(count/total_count, design §5.7 已迭代, 非预设1/10/100)。详见 research 07 + ADR-0001。

## 6. 链级 DSL 字段(从 36 链 chains 文档 §7/§9/§11 穷举, design §4 method级 DSL 没有的链级维度)

> **来源**: docs/{zh,en}/chains/*.md 各链 DSL ASK/决策节(32 文档穷举)。**design §4 param_spec 是 method 级**(参数怎么构造), 这里是**链级**(整链怎么声明: endpoint/auth/finality/链类型/模块集)。两者分层互补。chains 文档保留(每链调研背景), 本节汇总链级字段供 S2 schema 设计参考。
> **🔴 待决(§3 决策未锁, 影响 S2 schema 边界)**: 链级字段整合进 param_spec 顶层, 还是独立 chain-level schema 两层。moonbeam 汇总收敛为 "7必+1推+4缓"。

| 链级字段 | 语义 | 适用链 | 类型 |
|---|---|---|---|
| `endpoints`(对象) | 从 rpc_url:string 升级为多 endpoint 对象(node/indexer/evm/mirror 分离) | algorand(node+indexer)/avax-x(/ext/bc/X+/ext/info)/hedera(mirror+relay)/sei/substrate sidecar/tezos(rpc+indexer)/optimism/osmosis/kusama/dogecoin 等 | L1必 |
| `auth` | {header_name, header_value_env, required} 鉴权(env展开非明文) | algorand(X-Algo-API-Token)/bitcoin系(Basic Auth rpcuser/pass)/cardano(Blockfrost project_id)/bch | L1必 |
| `protocol_kind` | rest/jsonrpc/grpc/hybrid per-chain 协议类型(决定 POST/GET 路由) | aptos/tezos/ton/cosmos系 | L1必 |
| `rollup_type` | l1/optimistic/zk/validium/modular_da 链类型(决定 finality 等待策略) | zksync(zk三阶段commit/prove/execute)/linea/celestia(modular_da)/arbitrum/optimism | L1必 |
| `finality` | 查询级 finality 开关(非 EVM block tag) | near(optimistic/near-final/final)/zksync(三阶段)/cardano(confirmations=36)/tezos(is_bootstrapped) | L1必 |
| `response_path` | JSONPath-lite 响应提取路径(error_path 含 .error.cause.name) | aptos/near(.error.cause.name)/cosmos/tezos/ton/algorand | L1必 |
| `module_set` | cosmos 各链启用 module 集(plugin 据此装配 rpc_methods 子集, 避免每链抄) | injective(+5)/osmosis(+CLP)/celestia(+blob)/sei | 推荐 |
| `denom_format` | cosmos denom 形态枚举(bare/ibc/peggy/factory/erc20/cw20) | injective/osmosis/sei/acala | 推荐 |
| `dual_address` | 双地址绑定(bech32⇄hex, {primary,secondary,binding_endpoint}) | sei(sei1⇄0x)/acala/astar(substrate+EVM) | L1推 |
| `evm_layer` | {type:in_protocol/l2_separate, chain_id_evm, endpoint, parallelism, gas_token} | sei(occ)/acala(787)/astar/injective/moonbeam(priority) | 可缓 |
| `3part_id` | hedera 0.0.X 三段账户ID占位(path直嵌) | hedera | L1必(hedera) |
| `cashaddr` | bch 地址编码枚举(base58check/bech32/cashaddr) | bch | 链特定 |
| `bare_string_response` | 响应是裸 JSON string 非 object(解析器需容错) | tezos(balance="283125643"/chainid)/ton | 链特定 |
| `indexer_endpoint` | tx 查询需 indexer 反查(独立于 rpc) | tezos/aptos/algorand | L1必(部分链) |
| `modular_da` | DA 层标识(celestia 等模块化) | celestia/sei/astar | 可缓 |
| `precompiles_extra` | EVM 链独有 precompile 段 | moonbeam | 链特定 |
| `xcm` | {enabled, version} 跨链消息(substrate parachain) | moonbeam/acala/astar | 链特定 |
| `wasm_layer` | {enabled} WASM 双VM 标识(显式提示) | astar | 可缓 |

**🔴 NS-3 零代码硬边界(chains 文档实证, design §4 没承认)**: polkadot `state_getStorage` 取余额需 client-side blake2_128 哈希 + SCALE 解码 → **纯声明式 DSL 无法表达, 只能 sidecar REST 或写 adapter 代码**(polkadot §11.7)。bitcoin UTXO method chaining(前 method response→后 method param)同理。**"零代码加任意 method" 对 substrate raw storage / UTXO 链有真实例外**, S2 设计须承认此边界(用 sidecar/adapter 兜底, 标 KNOWN_BROKEN 不阻塞)。
