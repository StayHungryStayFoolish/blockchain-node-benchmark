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
| B2 36链 method 参数/响应规律(互联网+public endpoint) | ✅ 已完成(param位置语义代码实证 + publicnode double-check) | 本批 |
| B3 调研结论(现状/风险/方案) | ✅ 已完成(rpc-method-param-research.md 阶段3, R1-R5 风险 + 方案) | 本批 |
| C1 mixed weight 全链路追踪+修复 | 🔄 下一步 | - |
| C2 proxy per-method 404 定位+修复 | ⬜ 待 | - |
| A 完整端到端出 HTML(GKE Job + GCE 真机) | ⬜ 待 | - |

## B 阶段产出(给用户回来看)
- 用户核心担心【已 public endpoint 真机证实】: 参数位置传错 → RPC 报错拿不到正确响应(publicnode EVM eth_getBalance [latest,addr] → error -32602)。
- 框架靠 param_format 名编码参数位置(address_latest=[addr,latest] vs latest_address=[latest,addr] 相反); 53 种格式多单链特例; 同名method多format(eth_call等)。
- 三缺口: 全新参数形态需改代码 / 声明错无校验静默错 / 漏声明fallback single_address静默错。
- 最高优先低成本修复建议: 启动期 param_format 校验 fail-fast(防静默错)。待用户拍板。

## 执行日志(时间倒序, 最新在上)

### B 阶段完成
- B1 现状 + B2 参数位置语义(代码 jsonrpc.py _build_params 实证 + publicnode EVM 实打 double-check 位置错=报错)+ B3 风险清单 R1-R5 + 处理方案。全落 rpc-method-param-research.md。
- 关键证据: [addr,latest]→拿到余额 / [latest,addr]→error -32602 cannot unmarshal into Address。证实用户担心。
- 下一步: C1 mixed weight 全链路(生成端已确认未用=round-robin均权; 需查归因/报告端是否用 → 死字段?)。

### [开始] B 阶段启动
- 顺序定为 B→C→A, 建本追踪文档。
- 下一步: 加载 record-replay/fake-node/per-method-proxy skill; B2 调研 36 链 method 参数规律。
