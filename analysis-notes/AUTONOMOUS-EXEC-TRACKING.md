# 自主执行追踪: B→C→A (2026-06-01 用户休息期间自主推进)

> 用户授权: 自定顺序, 按文档/skill/memory 执行, 全程记录本文档追踪。
> 顺序决策: B(RPC method 参数+36链规律+fake-node数据)→ C(mixed weight + proxy 404)→ A(完整端到端出HTML)。
> 理由: 依赖链 — A 依赖 fake-node 数据丰富(B 的产出)+ weight/proxy 修复(C); B 是地基。
> 方法纪律: B 必须互联网搜索 + public endpoint double-check(用户强制); 改前 token-level Gate3;
>   每完成一块 commit; 落盘本文档 + rpc-method-param-research.md + EXEC-TRACKER。
> 真机环境: GKE bench-k8s-test(§18.9) + GCE instance-20260429-041108(§30, 同 payment-network)。

## 状态总览
| 阶段 | 状态 | commit |
|---|---|---|
| B1 框架现状(阶段1) | ✅ 已完成(rpc-method-param-research.md 阶段1) | 3524d48 |
| B2 36链 method 参数/响应规律(互联网+public endpoint) | ✅ 已完成(param位置语义代码实证 + publicnode double-check) | ec575c9 |
| B3 调研结论(现状/风险/方案) | ✅ 已完成(rpc-method-param-research.md 阶段3, R1-R5 风险 + 方案) | ec575c9 |
| C1 mixed weight 全链路追踪 | ✅ 已完成(两种weight厘清, 见下) | 本批 |
| C2 proxy per-method 404 定位 | ✅ 已完成(proxy 无 bug, 404 是历史 fixture 状态) | 本批 |
| A 完整端到端出 HTML(GKE Job + GCE 真机) | ⏸️ 部分(挖出更深设计问题, 待用户定方向) | - |

## A 阶段结论: 触及 fake-node 数据设计本质, 非简单补 fixture(2026-06-01)
**A 目标**: 解 fake-node 数据退化(target=2)让完整 benchmark 出 HTML。深挖后发现比预期复杂:
- **fixture 多样化做了但不可移植**: 改 getTransaction.json → 24 accountKeys(本地验 fetch 能提多账户)。
  但 `tools/fake-node/fixtures/` 被 .gitignore 忽略(record-replay skill R1: fixtures 不进 git, clone 后 record_*.sh 现录)。
  → 手工改 fixture 只本地有效, GKE/GCE/clone 不存在。正解 = 改 record 脚本/生成逻辑产多样数据(更深工程)。
- **fetch params 占位符机制**: chain template solana.json `params` 值是占位符字符串("semaphore_limit":"ACCOUNT_SEMAPHORE_LIMIT" 等),
  全仓无 envsubst 替换逻辑。我直连跑 fetch(跳过框架 env 设置)→ 占位符未替换 → int() 炸。
  但正常框架流程 Phase1 fetch 能取 7000+ signatures(--fake-node 实测过)= 正常流程占位符被正确处理。
  → 我直连测试方式的误区, 非 fetch bug。我加的 int() 改动在占位符场景错误, 已回退。
- **诚实结论**: A 的"补 fixture"是浅层解, 真正让完整 benchmark 在多环境跑出 HTML 需要:
  (a) fake-node 数据生成多样化(改 record/生成逻辑, 不是手工改单个 fixture);
  (b) 或用真节点/真实录制数据替代 byte-correct 单一 fixture。
  这是 fake-node 测试夹具的数据丰富度工程, 比 k8s 适配大, 待用户回来定方向。
- **本地 fixture 改动保留(未 commit, 因 .gitignore)**: getTransaction.json 24 账户在本地, 供后续本地验证用。

## 执行日志(时间倒序, 最新在上)

### A 阶段(部分)
- fixture 多样化(getTransaction.json 24 账户)本地验 fetch 提多账户。但 fixtures 被 gitignore 不可移植。
- 挖出 fetch params 占位符机制(chain template params 是 env 变量名占位符, 直连测试未替换炸)= 测试方式误区非 bug, int() 改动已回退。
- 诚实结论: A 真解 = fake-node 数据生成多样化工程(改 record 逻辑)或真节点数据, 非手工补 fixture。待用户定方向。

### C2 完成(proxy per-method 404)

## C2 结论: proxy per-method 404 = proxy 无 bug(2026-06-01 本地实测)
- proxy handler.go: 纯 `httputil.NewSingleHostReverseProxy` 透传(L34/70), 不改 method/params/path, 只记录 upstream status 给 per-method CSV。代码审查确认无 404 逻辑。
- **本地实测(起 fake-node:8899 + proxy:18545)**: 经 proxy 打 getSignaturesForAddress → HTTP 200 + 正常结果; 直连 fake-node 同样 200 + 相同结果。**proxy 透传正确, 不 404。**
- **结论**: 容器那次 getSignaturesForAddress 404 = 历史状态(skill §3: getSignaturesForAddress.json fixture 之前缺, 后续会话补全; 容器那次跑的是补全前状态), **非 proxy bug、非现在代码 bug**。现 fixture 齐, proxy+fake-node 全链路 200。
- 连带澄清: 本地 --fake-node QPS test failed ≠ 404 导致(404 早不存在); 是 fake-node byte-correct 数据退化(target=2)。两件事分清。
- §24.2 "proxy per-method 404 TODO" 可关闭(无 bug)。

## C1 结论: mixed weight 全链路(2026-06-01, 纠正"死字段"初判)
**两个不同的 weight, 必须区分**:
1. **chain template `mixed_weighted` weight(配置目标权重)**: 生成端 target_generator round-robin 均权分配 method, **未按此 weight** → 缺口。
2. **归因端 weight(per_method_attribution.py L14/231)**: = `method_count/total_count` = 运行时【实测】每 method 流量占比, 按此把 CPU/MEM 分摊。**在用, 是实测值不是配置值。**
**结论(精确, 非死字段)**:
- 归因逻辑本身【正确】(按实际打出的流量占比归因资源, 合理)。
- 真缺口 = 【配置 weight → 生成端流量比例】这一环断了: round-robin 均权 → 实际打出的 method 比例 ≠ 用户配的 mixed_weighted weight → 归因端如实反映"均权"但那不是用户想要的分布。
- 修法(温和, 明确): 生成端按 mixed_weighted 的 weight 比例分配 method(而非 round-robin 均权), 让实际流量比例 = 配置 weight, 归因端自然得到正确权重分布。NS-2"按权重归因"才真生效。
- 严重度: 中(归因机制对, 只是流量比例没按配置)。待用户拍板是否修 + 优先级。

## B 阶段产出(给用户回来看)
- 用户核心担心【已 public endpoint 真机证实】: 参数位置传错 → RPC 报错拿不到正确响应(publicnode EVM eth_getBalance [latest,addr] → error -32602)。
- 框架靠 param_format 名编码参数位置(address_latest=[addr,latest] vs latest_address=[latest,addr] 相反); 53 种格式多单链特例; 同名method多format(eth_call等)。
- 三缺口: 全新参数形态需改代码 / 声明错无校验静默错 / 漏声明fallback single_address静默错。
- 最高优先低成本修复建议: 启动期 param_format 校验 fail-fast(防静默错)。待用户拍板。

## 执行日志(时间倒序, 最新在上)

### C1 完成(mixed weight 全链路)
- 全仓追 weight: 生成端(target_generator round-robin 均权, 未用配置 weight)+ 归因端(per_method_attribution 用实测 weight=count/total)。
- 纠正初判: weight 非死字段 —— 归因端用实测 weight(对); 缺口在配置 weight 未驱动生成端流量比例。
- 修法: 生成端按 mixed_weighted weight 分配 method 替代 round-robin。中严重度, 待拍板。
- 下一步: C2 proxy per-method 404 定位。

### B 阶段完成
- B1 现状 + B2 参数位置语义(代码 jsonrpc.py _build_params 实证 + publicnode EVM 实打 double-check 位置错=报错)+ B3 风险清单 R1-R5 + 处理方案。全落 rpc-method-param-research.md。
- 关键证据: [addr,latest]→拿到余额 / [latest,addr]→error -32602 cannot unmarshal into Address。证实用户担心。
- 下一步: C1 mixed weight 全链路(生成端已确认未用=round-robin均权; 需查归因/报告端是否用 → 死字段?)。

### [开始] B 阶段启动
- 顺序定为 B→C→A, 建本追踪文档。
- 下一步: 加载 record-replay/fake-node/per-method-proxy skill; B2 调研 36 链 method 参数规律。
