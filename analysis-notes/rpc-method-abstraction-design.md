# RPC Method & 响应结构 抽象设计(声明式 DSL — 兼容用户配置任意 method)

> **状态**: 设计+全量实测进行中(2026-06-01 立项)。这是长期工程的专门文档。
> 相关: rpc-method-param-research.md(规律发现, 阶段1-4, 已确立 family×param_format 二维规律)是本文档的前置调研。
> 本文档 = 全量实测矩阵(184 method)+ 参数/响应抽象 DSL 设计。

## 0. 🎯 目标(用户 2026-06-01 澄清, 这是北极星)
**让框架兼容【使用者自己配的、我们没预置的】任意 RPC method —— 零代码。**
应用场景: 使用者按业务场景配一个 36 链里没有的新 method, 只填 chain template
(声明参数怎么传 + 响应怎么解), 框架就能正确压测它 + 正确归因/分析, 不改代码。

两个抽象目标:
1. **参数结构抽象**: 不靠 param_format 预定义枚举名(新形态撞上没有的就得改 _build_params 代码),
   而是一套通用的【声明式参数描述】, 用户在 chain template 描述 method 参数
   (几个位置、每个位置类型、地址/区块/哈希填哪)→ 框架据此构造请求。
2. **响应结构抽象**: 用户配的新 method 返回什么结构, 框架声明式地知道怎么解析
   (从响应哪个字段提区块高度/账户/数据), 而非每个 method 在 parse 代码硬编码。

**为什么需要全量实测(方案B)**: 必须先摸全 36 链 184 个 method 的真实参数形态 + 真实响应结构
(public endpoint 实测拿到), 才能归纳出 DSL 要覆盖哪些情况、怎么设计才能兼容未来用户任意配置。
抽样(每 family 1-2 个)不够 —— 那只能验规律存在, 不能保证 DSL 覆盖全部真实形态。

## 1. 现状抽象的不足(rpc-method-param-research.md 已证)
- 参数: 靠 (family, param_format) 二维, param_format 是预定义枚举名(53 种)。新 method 若参数形态不在某族枚举 → 必须改 _build_params 加分支(非零代码)。R1 风险。
- 无校验: 用户声明错 param_format(位置反/类型错)框架静默错(public endpoint 证实位置错=报错)。R2/R3。
- 响应: 各 method parse 逻辑(提 block_height/account 等)散在 adapter 代码, 非声明式。
- = 现状是"预置好的能跑, 用户加全新的要改代码", 不满足目标。

## 2. 方法论(用户强制)
- **每个 method 必须**: 读官方文档理解参数+响应 → public endpoint 实测拿真实请求/响应 → 记录进矩阵。
- 不许只读框架代码推断。不许抽样代替全量。
- public endpoint 实测注意: 限流(sleep)、需真实地址/哈希做参数、记录真实响应 JSON 结构。

## 3. 36链 184 method 全量实测矩阵(逐链逐 method 填)
> 格式: 链 | family | method | mode(single/mixed) | 参数(位置×类型×语义) | 官方文档确认 | public endpoint 实测响应结构 | 备注
> 状态标记: ⬜未测 / 🔄进行 / ✅实测拿到响应 / ⚠️endpoint不可达(需替代)

### 进度: 0 / 184 method 实测
(矩阵逐 family 分批填, 见下方各 family 节)

### 3.1 jsonrpc family (16 链)
(待填)
### 3.2 substrate family (5 链)
(待填)
### 3.3 tendermint family (5 链)
(待填)
### 3.4 bitcoin_jsonrpc family (4 链)
(待填)
### 3.5 rest family (5 链)
(待填)
### 3.6 hedera_dual family (1 链)
(待填)

## 4. 参数结构抽象 DSL 设计(全量实测后归纳)
(空 — 待矩阵填全后, 从真实形态归纳出能兼容任意 method 的声明式参数 DSL)

## 5. 响应结构抽象 DSL 设计(全量实测后归纳)
(空 — 待矩阵填全后, 归纳响应解析 DSL: 怎么声明从响应提取 block_height/account/data 等)

## 6. 实现方案(设计审过后)
(空 — chain template schema 扩展 + adapter 支持 DSL + 向后兼容现有 param_format)

## 7. 执行日志(时间倒序)
### 2026-06-01 立项
- 用户澄清目标: 不是验现有 method 能跑, 是设计 DSL 让用户配任意新 method 零代码兼容。
- 确认 36 链 184 method 需全量实测(public endpoint + 官方文档)。
- 建本文档。前置规律(family×param_format)见 rpc-method-param-research.md 阶段4。
- 下一步: 逐 family 实测填矩阵(从 jsonrpc 16 链开始)。
