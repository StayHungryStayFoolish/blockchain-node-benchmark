# RPC method 重构 — 需求罗盘(收敛前几轮对齐, 2026-06-02)

> 用途: 把多轮对话里逐步澄清/纠正的需求散点收敛成一份权威清单, 作为 §6 实施计划的输入。
> 每条标注来源(用户原话澄清 / 代码实证 / skill 沉淀), 区分"已锁定"与"待调研/待拍板"。

## 0. 北极星(不变, 来自 NORTH-STAR NS-1/2/3)
- NS-1: 36 链零代码加链(只配 JSON)。
- NS-2: mixed 模式按 method 维度归因节点端资源消耗(CPU/MEM/EBS/Net)+ 出图 + 双语 HTML。proxy 是核心载体, 不可绕过。
- NS-3: 零代码原则覆盖 adapter 层 + proxy 协议解析层(declarative DSL)。
- 本次重构 = NS-1/NS-3 从"零代码加链"延伸到"零代码加 method"。

## 1. 已锁定需求(用户多轮澄清 + 代码实证)

### R-A. account 真实获取逻辑必须遵守(用户澄清, 7 个月前设计)
- 框架执行时, **从被测节点取"当时时间点周边的真实链上账户地址"**, 基于这些真实地址用 rpc method 拼成符合 vegeta 的文件, 再压测。
- 代码实证: `tools/fetch_active_accounts.py` 就是这个逻辑(取真实 account → `tools/target_generator.sh` 拼 vegeta target)。
- **重构必须保留此逻辑**, 不破坏真实节点路径。

### R-B. 取 account 时顺手取其他 method 所需参数(用户澄清 + 代码实证可行)
- 取 account 时, **顺便从真实节点获取 tx_hash / block_hash / block_number 等其他 method 需要的参数**, 供后续构造 vegeta 文件。
- 代码实证(几乎零新增成本): fetch 取 account 过程**已经经手**这些数据 —— `fetch_active_accounts.py:378` getBlockByNumber 拿整个 block、`:395` `tx["hash"]` 已提 tx hash、solana `:256` signatures。**现在被丢弃只留 account**。需求 = 让 fetch **额外保留**这些已经手的输入到独立"输入池"。
- 纠正第二轮"输入供给层缺失"的措辞: 不是能力缺失, 是**供给能力已存在, 只是没保留输出**。

### R-C. fake-node 场景用真实请求/响应结构 mock(用户澄清 + fake-node 设计本意)
- 真实节点路径在 fake-node 场景**无法直接用**: 公共节点限流 + 无法快速部署 36 个真实区块链节点。
- 方案: 既然 §3 已全量实测 184 method 的**真实请求 + 响应结构**(都是确认正常响应的), 就**用这些真实结构 mock fake-node fixture + 构造 vegeta 文件**, 让本地/CI 测试绕开限流跑通。
- 代码实证(正是 fake-node 设计本意): `tools/fake-node/handlers/base.go:53` handler 是 fixture passthrough, fixture = `fixtures/<chain>/<method>.json` 真实响应字节。§3 实测响应 → 直接就是 fixture 内容。同时解决 skill 记载的"fixture 不全→404/数据退化 target=2"痛点。

### R-D. 两条输入路径分治, 共用同一套 DSL(收敛 R-A/B/C)
- **真实节点路径**(生产/真机 L3): fetch 扩展, 取 account 顺手保留 tx_hash/block_id 池 → 真实输入构造 vegeta。
- **fake-node 路径**(本地/CI): §3 实测真实请求/响应 mock fixture + 构造 vegeta → 不连真实节点。
- 两路径共用 §4 param_spec DSL(声明 method 参数怎么摆 + 输入从哪类池取), 只是输入池填充来源不同(真节点抓 vs §3 mock)。

### R-E. 参数构造 DSL 化(§4, 修真债 + 零代码加 method)
- 现状 param_format 枚举硬编码在 6 adapter, 新形态需改代码(R1)、声明错无校验(R2)、漏声明 fallback 静默(R3)。
- 用 param_spec DSL(transport × slot/field × source)替换, source 从输入池取值。与 param_format **并存**向后兼容(36 链不配 param_spec 行为不变)。

### R-F. 修复 34 个协议级真债(代码实证)
- tendermint 全 5 链 25 method: adapter 假设 POST jsonrpc, 实测链是 LCD REST GET path → 协议错配。
- near/tron/avalanche-x 9 method: 要 dict/REST body 给了 list。
- 这些是现状已坏的真债(节点必拒), 重构一并修。

### R-G. 工程纪律(skill + 用户偏好)
- 不留技术债; 整个调用链不断裂(target_generator/proxy/归因层契约不破); 向后兼容现有 36 链。
- 每 family 每阶段 L1 单测 + L2 模块集成 + L3 真机 e2e 三层验证(multi-stage-l3-mandatory)。
- L3 前置工具链(fixture + 输入池 + e2e harness)S0 一次性建好, 不拖到最后。
- 改命脉子系统前 token-level 精读该 family 全调用链; 真机硬证。

## 2. 待办前置(进 §6 实现前必做)

### T1. 完整重抓 184 method 响应 JSON 落盘 fixture(本次)
- §3 矩阵的响应是 trunc(300~440)截断的, **不能直接当 fixture**(坏 JSON)。
- 真实完整响应当时 curl 已拿到(只是打印截断), 需用 §3 沉淀的 endpoint 映射 + 取真实参数技巧重抓完整版。
- 落盘 `tools/fake-node/fixtures/<chain>/<method>.json`(byte-correct 完整响应)。
- 注意: fixtures 进 .gitignore(record-replay R1), 但本次因无法连真实节点, 需评估"mock fixture 是否破例入库 or 提供 record 脚本现生成"。

### T2. 调研 vegeta 是否区块链节点性能压测最优工具(用户提出)
- 现状框架用 vegeta 做压测发生器。用户问: vegeta 是不是区块链节点性能测试最好的工具?
- 需调研: vegeta 优劣 + 区块链 RPC 压测候选工具(k6 / wrk / bombardier / locust / 自研 + 区块链专用如 ethspam+versus / tsung 等)对比 → 给"保留 vegeta vs 换"的带推荐结论。
- 这是独立调研, 不阻塞 T1, 但影响 §6 是否要改压测发生器层。

## 3. 待用户拍板
- T1 fixture 入库策略(破例入库 vs record 脚本现生成)。
- T2 调研结论出来后: 是否换压测工具(影响重构范围)。
- §6 实施计划三阶段(输入供给/参数DSL/协议修复)顺序与 family 切分。

## 4. 范围演进留痕(防漂移)
- 第一轮分析: 以为重构 = 改 adapter 参数构造一层。
- 第二轮扩大: 挖到"输入供给"更上游(45 method 需非账户输入, 框架无源)。
- 用户澄清(本轮): 输入供给能力 7 个月前已设计(fetch 取 account 顺手经手 tx/block), 重构 = 扩展保留 + fake-node mock 两路径; 且提出 vegeta 工具选型调研。
- 当前认知: 重构 = 输入池(扩展 fetch + fake mock 两路径)+ 参数 DSL + 协议修复 + (可能)压测工具选型, 全程两路径共用 DSL。
