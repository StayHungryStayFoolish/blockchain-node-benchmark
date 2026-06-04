# RPC Method 重构 — 代码更新 Task 完成状态

> 配合 REFACTOR-SSOT.md(权威事实源)。本文件只跟踪【代码 task 完成状态】。
> 完成判定(硬标准, 防孤岛): (a)新代码在生产主链被 caller 真调用(grep caller≥1 live)
>   (b)L1单测 / L2模块集成 / L3整框架e2e 触达 (c)老路径删或收编 (d)commit SHA。
> 状态: ⬜未做 / 🔄进行中 / ✅完成(带证据) / ⏸️阻塞(等依赖或等用户)

---

## 已完成(独立有效, 已核实)
| Task | 状态 | 证据 |
|---|---|---|
| F1 adapter_family CI 治理门 | ✅ 脚本完成(commit 1bd3fa7) / ⏸️ 待挂进 CI 流程 | ci/check_adapter_family.sh, 36链全过, 负向测试过 |

## 在建(未接调用链, 不算完成)
| Task | 状态 | 缺什么 |
|---|---|---|
| param_spec.py 模块 | 🔄 草稿(commit 13c26a8/4d4c42e/fee1086) | ❌缺 spec→params 构造器; ❌0 caller; 属 S2, 待 B1+B2+B3 一起接 |

## 待做(按 SSOT 拓扑顺序填, 暂留位)
*(待 SSOT 审核完, 把功能单元按依赖顺序搬来这里, 逐个标状态)*

## 最终验证
| Task | 状态 |
|---|---|
| L3 fake-node 在 GCE 全流程实测 | ⬜ |
| L3 fake-node 在 GKE 全流程实测 | ⬜ |
