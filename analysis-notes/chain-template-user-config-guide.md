# Chain Template 配置指南(面向使用者 — 如何配置 RPC method)

> **本文档受众 = chain template 的【使用者】**(配置自己业务 RPC method 的人), 不是框架开发者。
> 目标: 回答"框架支持哪些请求/响应形态 + 我加一个 method 该改 template 哪些字段 + 照哪个模板填"。
>
> 🔴 **字段状态标注铁律(每个字段都标, 防止误以为已支持)**:
> - ✅ **已生效**: 当前框架代码已支持, 改了立即生效。
> - ⏳ **设计预览(待 §6 实施)**: DSL 设计已定但代码未落地, 见 `rpc-method-abstraction-design.md` §6 实施计划。**现在配了不生效**。
>
> 关联文档: 设计依据 `rpc-method-abstraction-design.md` / 块高实测 `block-height-sync-method-measurement.md` / 全链路分析 `rpc-method-refactor-fulllink-analysis.md`。

---

## 第一部分: 当前已支持(✅ 改了立即生效)

### 1.1 chain template 顶层字段速查

| 字段 | 状态 | 作用 | 加 method 要改? |
|---|---|---|---|
| `_meta.adapter_family` | ✅ | 声明本链协议族(6 选 1, 决定请求怎么发) | 加同族 method 不用改 |
| `rpc_methods.single` | ✅ | 单 method 压测模式用哪个 method | 改这个换压测 method |
| `rpc_methods.mixed` | ✅ | 混合模式 method 列表(逗号分隔) | 加 method 加到这里 |
| `rpc_methods.mixed_weighted` | ✅(配置)⏳(生效) | 各 method 权重 `[{method,weight}]` | ⚠️ 当前权重未驱动流量(缺口#9, §6 修), 现在配了是均权 |
| `param_formats` | ✅ | 每个 method 用哪种参数格式(枚举名) | **加 method 必改这里** |
| `proxy_extraction.extractors` | ✅ | proxy 怎么从流量识别 method(per-method 归因用) | 加 method 一般不用改(按 family 通配) |

### 1.2 ✅ 当前支持的参数格式(param_formats 枚举名 — 加 method 选一个; GREP-EVIDENCE 实证全枚举)

框架现在用 `param_formats: {"<method>": "<枚举名>"}` 声明每个 method 的参数怎么构造。**6 family 各自支持的枚举名(代码实证, tools/chain_adapters/<family>.py:_build_params)**:

**jsonrpc family(16 链, 16 个枚举 — 最丰富)**:
| 枚举名 | 参数形态 | 例 |
|---|---|---|
| `no_params` | 无参 | eth_blockNumber → `[]` |
| `single_address` | 单地址 | eth_getBalance → `["<addr>"]` |
| `address_latest` | 地址+标签(地址在前) | `["<addr>","latest"]` |
| `latest_address` | 标签+地址(**顺序相反**) | starknet → `["latest","<addr>"]` |
| `address_storage_latest` / `address_key_latest` | 地址+存储/键+标签(3位) | `["<addr>","0x0","latest"]` |
| `address_with_options` | 地址+选项对象 | solana getAccountInfo → `["<addr>",{encoding}]` |
| `block_number` / `block_number_int` | 区块号(hex/int) | eth_getBlockByNumber |
| `transaction_hash` | 交易哈希 | eth_getTransactionByHash → `["<txhash>"]` |
| `eth_call_object_latest` | call 对象+标签 | eth_call → `[{to,data},"latest"]` |
| `object_single` | 单对象 | (各链特殊) |

**bitcoin family(4 链)**: `no_params` / `single_address` / `address_minconf_includewatchonly` / `txid`
**substrate family(5 链)**: `no_params` / `single_address` / `storage_key` / `block_hash` / `address_with_block`
**tendermint family(5 链)**: `no_params` / `single_address` / `height_param` / `abci_balance_query`
**rest / hedera_dual**: 走 `_meta.rest_paths` path 路由声明(本身已是声明式)。

> 🔴 **重要区分(GREP-EVIDENCE 纠正常见误解)**: `transaction_hash` / `txid` / `block_number` 枚举**已存在**(参数构造层面支持 tx_hash/区块号)。但 —— **当前框架的输入供给层只产 account 一池, 没有 tx_hash / block 池**(缺口#3: fetch 把经手的 tx_hash 丢了)。所以这些枚举能"构造"tx_hash 参数, 但**拿不到真实 tx_hash 值**(靠占位符兜底 → 节点可能报错)。即: **参数构造已支持, 真实输入供给没跟上**。§6 S1 输入供给层补全后才真正可用。
>
> ⚠️ **真正需要改代码的情况**: 新 method 参数形态**不在上述任一枚举内**(全新位置组合/类型)→ 当前必须改 `_build_params` 加枚举分支。§6 param_spec DSL 化后改 JSON 即可。

### 1.3 ✅ 当前加一个【参数形态已支持】的 method — 操作步骤

假设加 `eth_getStorageAt`(参数 = 地址+存储键+标签, 已有 `address_key_latest` 枚举覆盖):
1. 编辑 `config/chains/<你的链>.json`
2. `rpc_methods.mixed` 加上 `eth_getStorageAt`(逗号分隔)
3. `param_formats` 加 `"eth_getStorageAt": "address_key_latest"`
4. 完成 —— **零代码**。(proxy_extraction 按 family 通配自动识别)

若参数形态**不在枚举内** → 当前要改代码(§6 后改 JSON 即可)。

### 1.4 ✅ 当前响应处理现状(诚实)

**当前框架压测主路径【不解析响应 body】** —— per-method 资源归因(NS-2)只用 proxy 记的 method_name/status_code/latency, 不看响应内容。唯一解析响应的地方 = **块高健康检查**(各 adapter 的 parse_block_height, 当前 8 链硬编码在 `common_functions.sh`)。
所以**当前没有"响应结构配置"字段** —— 响应解析是写死在代码里的, 加链的块高提取当前要改 `common_functions.sh` 的 case(缺口#12, §6 改为声明式)。

---

## 第二部分: 设计预览(⏳ 待 §6 实施后生效 — 现在配了不生效)

> 以下字段是"零代码加任意 method"的 DSL 设计, **代码尚未实现**。设计依据见 `rpc-method-abstraction-design.md` §4/§5。
> 实施后, 上面第一部分的"参数形态不在枚举内要改代码""响应/块高要改代码"的限制将消除。

### 2.1 ⏳ param_spec(参数声明式 DSL — 替代 param_formats 枚举)

支持 **5 种参数注入位置**(覆盖 6 family 所有实测形态):
| 注入位置 | 适用 | 声明方式 |
|---|---|---|
| list 位置索引 | jsonrpc/bitcoin/substrate | 按位置声明 type + source |
| list 内嵌 object | solana getAccountInfo / sui getObject | 某位置是 dict 对象 |
| dict 键 | tendermint | 参数是 dict |
| URL path 占位符 | rest(`{addr}`/`{height}`) | path 模板 + 变量来源 |
| 双模式路由 | hedera_dual | jsonrpc body + mirror REST path |

每个参数位置声明三要素: **type**(string/int/object/array)+ **source**(从哪个输入池取: account/tx_hash/block/...)+ **order**(精确顺序, 因 EVM `[addr,latest]` 与 starknet `[latest,addr]` 顺序相反)。

### 2.2 ⏳ response_spec(响应声明式 DSL)

支持 **5 种 envelope**(jsonrpc_result/tendermint_rpc/ok_result/raw/array_root)+ **3 种值类型**(hex/dec/string 等)。
**对应键 = method**(每个 method 独立声明响应怎么解析, 不按参数类型 —— 因为同传 address 的 getBalance/getCode 响应完全不同)。

### 2.3 ⏳ block_height_spec(块高/同步监控声明式 DSL)

**3 种同步策略**(36 链实测分类, 详见 block-height-sync-method-measurement.md):
| 策略 | 适用 | 声明 |
|---|---|---|
| `dual_height` | substrate/bitcoin/EVM同步中 | 本地高度路径 + 网络最高路径(一个 method 拿全) |
| `slot_diff` | solana | getSlot + getMaxShredInsertSlot 相减 |
| `synced_bool` | tendermint/near/EVM已同步 | 已同步布尔 + 本地高度 |

⏳ 实施后块高监控**只问本地节点**(不打外部主网, 解决限流), 加链填 block_height_spec 即可, 零代码。

---

## 第三部分: "我要加 method, 该怎么办"决策树

```
我要加的 method 参数形态是?
├─ 在 §1.2 枚举表内(no_params/single_address/address_latest/...)
│   → ✅ 现在就能零代码: 改 rpc_methods + param_formats(§1.3 步骤)
└─ 不在枚举内(需 tx_hash/filter/全新位置)
    → 当前要改代码; ⏳ §6 实施后改 param_spec JSON 即可

我要这个 method 的响应被解析(提块高/余额等)?
├─ 只要块高健康检查 → 当前 8 链硬编码(改 common_functions.sh); ⏳ §6 后填 block_height_spec
└─ 要提其他语义字段 → ⏳ §6 后填 response_spec(当前压测主路径不解析响应)
```

## 第四部分: 待补充(本文档自身的 TODO)

- [ ] §6 实施完成后, 把第二部分的 ⏳ 改为 ✅, 补完整可复制 JSON 模板(每 family 一个)。
- [ ] 补 6 family 各自的 param_formats 完整枚举表(当前 §1.2 以 jsonrpc 为主)。
- [ ] 补一个端到端完整例子(从零加一个新链 + 新 method 的全过程截图级步骤)。
- [ ] 中英双语(框架报告是双语, 用户文档宜同步)。
