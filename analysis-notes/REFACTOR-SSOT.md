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
> - **SELF-EXEC-PROMPT-rpc-dsl.md = 待删原料**(已加降级标记, RPC事实过时仅作搬运索引; 待 SSOT 全单元搬完确认覆盖后删; skill 5处引用是方法论案例不依赖文件内容)。

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
*(待审核搬入 — 待逐行精读 design §4/fulllink 阶段2/callchain §4/chain-template §2.1/param-research §2 + research_notes 04/05 独有点后补)*
**S2 文件核对进度(机械计数门槛)**: 已 read_file 逐行 = code现状(6 family+cli+config_loader+target_generator) ✅ / design §4 ✅ / param_spec.py ✅ / file-notes×2 ✅ / research_notes 04 ✅(独有点: §4 calldata池/§3 getLogs provider限制/§2 资源画像)/ research_notes 05 ✅(独有点: getProgramAccounts/queryEvents/getEvents 复杂filter矩阵 + Node-killer safety_max)。**待逐行真读(此前仅grep, 不算精读)**: fulllink 阶段2 / callchain §4 / chain-template §2.1 / param-research §2。**X=7/N=11, 未核完**。

### 单元 S3 — 响应链 + 关联键 + 归因(缺口 #5/#6/#7/#8/#11/#12)
*(待审核搬入)*

### 单元 S0 — 前置工具链(L3 地基)
*(待审核搬入: F1已完成/fixture审计/F2)*

## 2. 调用链依赖拓扑(改代码顺序)
> 哪些单元必须先于哪些做(防孤岛/断链)

*(待审核搬入)*

## 3. 已锁定决策(带依据)
*(待审核搬入: vegeta保留/出图matplotlib/块高单一声明源/mixed weight/字段名否决改名 等)*

## 4. 不留债硬约束
*(待审核搬入)*

## 5. 独有事实合并节(从 research_notes 01-07 合并, 原文件待删, 来源标注)

> 本节合并 research_notes 早期调研的【独有内容】(两份实测文档 184+块高 没有的维度): 资源画像 / calldata 池 / fixture 工程 / safety 守卫 / per-method 归因机制。合并后原 research 文件删除(执行 A: 彻底单源)。**来源逐条标注供追溯**。⚠️ research 01-03b/05/06 头部的 "8 链 OUT-OF-SCOPE / 真 8 链" 标注是 8 链时代(v1.4, 2026-05-20)遗留, 现 36 链已全实测推翻, 合并时已剔除该过时标注。

### 5.1 per-method 资源画像(weight 配置依据, 来源 research 01/02/03/03b)
> 用途: NS-2 per-method 资源归因的 weight 粗粒度配置依据(Q4-7: 公开资料先配粗粒度 1/10/100 三档, 后期实测迭代)。**注: 流量占比数字是定性, 不作精确权重, 用户按实际校准**(research 02 §四原话)。

**EVM(research 01)**: eth_call(CPU+Mem, EVM全量执行, 1-100ms可到秒级) / eth_getLogs(CPU+Disk, bloom+receipt扫描, 10ms-数秒, 大范围退化全扫) / eth_estimateGas(极高, 二分重放eth_call, 实测7s vs eth_call 60ms) / debug_traceTransaction(CPU+RAM双重, 100ms-数十秒, archive) / eth_blockNumber(Memory, µs, 但流量榜第二=轮询心跳隐形QPS杀手) / eth_getBalance/getCode/getStorageAt(Disk-Random trie, sub-ms-ms)。Geth 默认不暴露 per-method metric(需改源码或代理拦截)→ 强化 proxy(NS-2)必要性。
**Solana(research 02)**: getProgramAccounts(CPU+Mem+Disk 极重, 全AccountsDB扫描无分页, 100ms-数十秒, OOM头号杀手, Helius/Triton/Alchemy 全限制) / getBalance(略重于getAccountInfo, deserialize-then-discard) / getMultipleAccounts(N次查并发) / getBlock(Disk+Net) / getSlot/getBlockHeight(Memory <1ms 但占量大头)。
**Sui(research 02)**: sui_getObject(Disk单点) / multiGetObjects(>20 batch 超线性 cache驱逐) / queryEvents/queryTransactionBlocks(indexer扫描)。Mysten 限制: 50 item(multiGet)/1000 result(query)。
**Bitcoin(research 03)**: getblock(verbosity=2, I/O+CPU, 大块数十MB带宽瓶颈) / getrawtransaction(有txindex 1ms 无则历史tx报错, txindex需50-80GB) / scantxoutset(CPU+I/O极高, 数十秒-分钟, 遍历1.5亿UTXO, EXPERIMENTAL公开节点禁) / estimatesmartfee(Memory <1ms)。**Bitcoin Core 原生不暴露 per-method metric, 8链中唯一需外挂exporter/代理拦截**(强化 proxy 必要性)。
**Starknet(research 03)**: starknet_call(CPU极高 Cairo VM) / estimateFee(批量是DoS向量, 公网均限速) / getStateUpdate(state diff MB级)。
**EVM L2(research 03b)**: scroll(reth, eth_*完全兼容, ~50-200GB状态) / polygon(bor+heimdall双进程, ~3TB archive, 150TPS高IOPS)。出块快(scroll 3s/polygon 2s)放大 eth_blockNumber 轮询压力。

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
**4 种 sampler**(research 06 §3.3): uniform(等概率, tx/cold) / weighted(按weights_field, 合约/program) / sequential(顺序步进绕回, eth_getLogs区段) / hot_cold_mix(hot_ratio概率取hot否则cold, 账户类模拟真实流量)。**hot/cold 比默认 0.2**(Zipf top20%=80%流量, Cloudflare/Alchemy)。
**采样 schema**(chains/<chain>.json): pools{file,format} + methods{weight, sampler{kind,pool,hot_ratio}, params_template, calldata_templates}。**注: 这套 sampler/params_template 是 research 06(2026-05-19)的另一套设计, 与 design §4 param_spec(transport×slot×source)是不同维度** —— param_spec 管"参数怎么构造", sampler 管"从池里怎么采样"。两者互补, S1/S2 实现时 param_spec.source 指定取哪个池, sampler 指定怎么从池采样。
**刷新**: fixtures/ 手动季度刷; fixtures.d/ cron(hot池每天/小时, blocks_range每次跑前)。manifest.json 记 fetched_at + latest_block_at_fetch + sha256。**漂移容忍**: 不锚定block hash, 小时-天级(blocks_range≤6h EVM/30min Solana, tx_hashes≤7天, addresses_hot≤14天)。

### 5.6 per-method 归因机制(NS-2 核心, 来源 research 07)
> proxy 采集 method 时序 + 分析层加权 group_by 归因资源(Q4-7)。proxy sink 9 列(timestamp_ns/method_name/protocol/request_id/batch_idx/status_code/latency_ms/upstream/client_addr)。**响应业务内容对资源归因零信息量**(压测主路径不解析响应 body, 见 184 文档头 + design §5.0)。权重=实测频次(count/total_count, design §5.7 已迭代, 非预设1/10/100)。详见 research 07 + ADR-0001。
