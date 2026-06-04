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
*(待审核搬入)*

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
