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

## 阶段2: 36链规律 + public endpoint 验证 (待做)
(空 — k8s/404 解决后填)

## 阶段3: 现状评估 + 风险清单 + 处理方案 (待做)
(空)
