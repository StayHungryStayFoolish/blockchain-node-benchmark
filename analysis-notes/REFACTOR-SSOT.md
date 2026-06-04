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

### 单元 S1 — 输入供给层 InputProvider(缺口 #2/#3/#6-fetch/#10 + R-B)
**涉及代码**: tools/fetch_active_accounts.py(create_adapter L665-668 / tx_hash 经手 L204·335·395 `{"signature":...}` / 写盘 L817-819 单列account)、tools/target_generator.sh(读单列 L193-225 / round-robin L246-262)、config_loader.sh(ACCOUNTS_OUTPUT_FILE 约定)。
**现状(代码实证 2026-06-04)**:
- create_adapter 只 4 adapter 类覆盖部分 chain_type(L665 solana / L667 ethereum,bsc,base,scroll,polygon / starknet / sui), **bitcoin/UTXO 无 adapter → raise(缺口#2)**。
- fetch 经手 tx_hash(L204/335/395 `{"signature":...}`)但写盘只 account 单列(缺口#3)。
- target_generator 读单列 account 喂所有 method(缺口#10)。
- 占位符污染(缺口连带): jsonrpc.py:84 tx_hash 无真值→全0占位→节点返null→per-method 归因偏低失真。
**重构目标(未做)**:
- 方案c分层: InputProvider(async抓输入,6 family)/ TargetBuilder(sync构造)解耦。
- fetch_inputs(chain_template)→ 多池 {account[],tx_hash[],block[],utxo[],...}(非单account)。
- 6 family 各实现(bitcoin UTXO/txid 无account 单独处理)。
- fetch 写盘改多池;target_generator 多池按 param_spec.source 取(不再一池喂全部)。
**依赖**: S1.4(多池消费)与 S2(param_spec)+ B3(build_vegeta_target 接口签名)**强耦合**——多池多参数必须一并改接口签名。**∴ S1.4/S2/B3 是一个原子单元,不可拆**(拆=孤岛, 2026-06-03 教训)。
**完成判定**: L1 每family InputProvider 单测 / L2 抓输入→构造 target 链路通 / L3 整框架对 mock 跑 mixed,需 tx_hash 的 method 不再 -32602 + 真值非占位。
**权威依据**: design §6.2.2 + fulllink §3/§9.1 + R-B(requirements)。

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
