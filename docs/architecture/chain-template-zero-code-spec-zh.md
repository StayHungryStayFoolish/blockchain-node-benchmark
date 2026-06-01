# Chain Template 零代码加链规范 (NS-3 SSOT)

**版本**:阶段 1-B 草稿
**关联北极星**:[NORTH-STAR.md](../NORTH-STAR.md) NS-3 零代码加链
**关联架构**:[per-method-proxy-architecture-zh.md](./per-method-proxy-architecture-zh.md)
**关联未决**:[OPEN-QUESTIONS.md](./OPEN-QUESTIONS.md) OQ-2 / OQ-3 / OQ-9
**适用范围**:`config/chains/*.json` (当前 36 文件) + `tools/chain_adapters/` (当前 7 族)

---

## 0. 北极星回顾(本文档为何存在)

NS-3 = **"加链 100% 0 Python"**。意思是:加一条新链(如假设的第 37 条 `mantle` EVM L2),只需:

1. 新增 `config/chains/mantle.json` 一份 JSON 模板
2. 在 `tools/chain_adapters/` 选一个**已有 adapter 族**(jsonrpc / substrate / tendermint / rest / bitcoin_jsonrpc / ogmios / hedera_dual)挂上去
3. **零 Python 代码改动**完成主流程跑通(fetcher 取真账户 + vegeta 压测 + monitor 出图)

如果做不到 1+2+3,就是 NS-3 违规(parallel entry trap 复发风险)。

**反例(当前现状违规处,实测于 main `7921b71`)**:
- `tools/fetch_active_accounts.py L665-678` `create_adapter()` 函数 3 个 if/elif 分支(solana / Eth族 5 链合并 / starknet / sui),覆盖 8 链;另 L684 `fetch_all_signatures()` 内嵌 `if adapter.chain_type == "solana"` 分支 → 加第 37 条要改 Python
- `config/config_loader.sh L371-405` 8 链 `case` 硬编码 RPC URL(solana / ethereum / bsc / base / polygon / scroll / starknet / sui)→ 加第 37 条要改 shell
- `tests/test_chain_adapters.py L404` `assert len(KNOWN_BROKEN_CLI) == 24` magic number → 修 broken 链需手改测试
- 见 [OPEN-QUESTIONS.md OQ-9](./OPEN-QUESTIONS.md)

本规范就是把"零代码加链"的**契约**写死,任何违反这个契约的新代码,pre-commit hook + L3 e2e 会拒。

---

## 1. Chain Template 完整 Schema

### 1.1 顶层字段(8 个,顺序无关,缺一报错)

```json
{
  "chain_type": "<string>",
  "rpc_url": "<string | placeholder>",
  "params": { ... },
  "methods": { ... },
  "rpc_methods": { "single": "...", "mixed": "..." },
  "param_formats": { "<method_name>": "<format_tag>", ... },
  "system_addresses": [ "<addr1>", "<addr2>", ... ],
  "_meta": { ... }
}
```

### 1.2 字段定义表

| 字段 | 类型 | 必填 | 含义 | 示例 |
|---|---|---|---|---|
| `chain_type` | string | ✓ | 链唯一标识,与文件名一致(`solana.json` → `"solana"`) | `"solana"` |
| `rpc_url` | string | ✓ | 节点入口 URL;**生产环境必须用占位符** `LOCAL_RPC_URL`,由 `config_loader.sh` 注入真实地址 | `"LOCAL_RPC_URL"` |
| `params` | object | ✓ | fetcher 通用参数(account_count / output_file / target_address / max_signatures / tx_batch_size / semaphore_limit),**所有链必须有这 6 个 key** | 见 §1.3 |
| `methods` | object | ✓ | adapter 专用方法配置(可空 `{}`,例如 hedera/tezos 无此需求) | `{"get_signatures": {...}}` |
| `rpc_methods` | object | ✓ | vegeta 压测目标 method 选择;必须有 `single` (单一 method) 和 `mixed` (逗号分隔的 method 列表) 两个 key | 见 §1.4 |
| `param_formats` | object | ✓ | 每个被压测 method 的参数构造 tag;**key 必须与 `rpc_methods.mixed` 列出的 method 一一对应** | 见 §1.5 |
| `system_addresses` | array | ✓ | adapter 取不到真账户时的兜底地址(可空 `[]` 但 key 必须存在) | `["11111111111111111111111111111111", ...]` |
| `_meta` | object | ✓ | 元信息(adapter_family / 来源 / 升级痕迹等),**`adapter_family` 必填** | 见 §1.6 |

### 1.3 `params` 子字段(6 必填)

| key | 类型 | 含义 |
|---|---|---|
| `account_count` | int | fetcher 默认抓取的活跃账户数 |
| `output_file` | string | fetcher 输出文件名(相对 `tmp/` 或绝对路径) |
| `target_address` | string | 单 method 测试默认地址(可与 `system_addresses[0]` 一致) |
| `max_signatures` | int | (Solana 专用,其他链填 0) 单地址抓多少签名 |
| `tx_batch_size` | int | fetcher 并发批次大小 |
| `semaphore_limit` | int | fetcher 协程并发上限 |

**约定**:所有链 6 个 key 都必须出现,即使不用 (`max_signatures: 0`)。fetcher 通过 schema 校验,缺 key 直接报错。

### 1.4 `rpc_methods` 格式

```json
{
  "single": "getAccountInfo",
  "mixed": "getAccountInfo,getBalance,getTokenAccountBalance,getLatestBlockhash,getBlockHeight"
}
```

- `single`:压测 single workload 时只发这一个 method
- `mixed`:逗号分隔的 method 列表,压测 mixed workload 时按 NS-2 权重分配(具体权重数字阶段 4 PoC 后定,见 [NORTH-STAR.md NS-2](../NORTH-STAR.md))
- **`mixed` 列出的每个 method 必须在 `param_formats` 里有对应 key**(schema 校验)

### 1.5 `param_formats` 格式

key = method 名;value = **格式 tag**(string),由 adapter 解析。

```json
{
  "getAccountInfo": "single_address",
  "getBalance": "single_address",
  "getLatestBlockhash": "no_params"
}
```

**预定义格式 tag**(adapter 必须实现):

| tag | 含义 | 适用 adapter 族 |
|---|---|---|
| `single_address` | 取一个账户地址作参数 | jsonrpc / rest / 所有 |
| `address_latest` | `[address, "latest"]` (EVM 习惯) | jsonrpc (EVM 系) |
| `no_params` | 空参数 `[]` | 所有 |
| `path_addr` | REST 路径模板带 `{addr}` 占位 | rest |
| `mirror_account_query` | hedera mirror 节点账户查询 | hedera_dual |
| ... | (扩展时新增,**新 tag 必须在 adapter 注册**) | |

**约定**:格式 tag 是 **enum**,加新 tag = 改 adapter Python 代码 (NS-3 例外允许,因为属于"协议层扩展"而非"加链")。

### 1.6 `_meta` 子字段

| key | 必填 | 含义 |
|---|---|---|
| `adapter_family` | ✓ | 选 7 族之一:`jsonrpc` / `substrate` / `tendermint` / `rest` / `bitcoin_jsonrpc` / `ogmios` / `hedera_dual`(见 §2.1 实测) |
| `source` | ✓ | 配置来源,例如 `"research-md"` / `"manual"` |
| `baseline_sha` | ✓ | 配置抽取时的 git SHA(可追溯) |
| `note` | 推荐 | 任何需要后人注意的事项 |
| `rest_paths` | 条件必填 | 若 adapter_family 含 rest,定义 `<method_key>` 到 `{method, path}` 的映射 |
| `health_probe` | 推荐 | health check 用的轻量 endpoint,格式 `{method, path, parse_jq}` |
| `known_broken_mixed` | 条件必填 | 若该链 mixed workload 已知 upstream 问题,记 `{status, evidence_date, live_http_test}` |
| `original_*` | 可选 | 抽取时的原始记录(归档用) |
| `proxy_extraction` | 推荐(NS-3) | per-method proxy 抽取规则,见 §1.7 |

### 1.7 `proxy_extraction`(NS-3 proxy 层契约,**新加链必填**)

per-method 资源归因 proxy 需要从每个 RPC 请求里抽取 method 名;此字段定义抽取规则的 declarative DSL。**严格 declarative,禁止内嵌 lua/python**(违 NS-3 + Q4-4)。

**Schema**:

```jsonc
{
  "proxy_extraction": {
    "extractors": [
      {
        "protocol": "json_rpc",         // 枚举: "json_rpc" | "rest"
        "method_source": "body.method", // JSON path,提取 method 名
        "id_source":     "body.id",     // 可选,提取 request id 做 latency 配对
        "params_source": "body.params", // 可选,统计 params 大小 / 复杂度
        "url_pattern":   "^/$",         // 正则,匹配 request URL;不匹配则跳过此 extractor
        "batch_handling": "split",      // 枚举: "reject" | "split" | "tag_batch",默认 "split"
        "auth": {                       // 可选,默认 {"type": "none"}
          "type": "none"                // "none" | "basic" | "bearer"
        }
      },
      {
        "protocol": "rest",
        "url_patterns": [                                   // list,每条带 method_name
          {"pattern": "^/v2/accounts/[A-Z2-7]+$",   "method_name": "GET_ACCOUNT"},
          {"pattern": "^/v2/transactions/[A-Z2-7]+$", "method_name": "GET_TRANSACTION"}
        ]
      }
    ]
  }
}
```

**字段语义**:

| 字段 | 类型 | 必填 | 含义 |
|---|---|---|---|
| `extractors` | array | ✓ | 抽取规则列表,**按顺序匹配第一条命中的 extractor**;空数组 = 该链不接 proxy(`PROXY_ENABLED=0` 模式)|
| `extractors[].protocol` | enum | ✓ | 仅支持 `json_rpc` / `rest` 两种(**封闭枚举**) |
| `extractors[].url_pattern` / `url_patterns` | string / array | ✓ | `json_rpc` 用单个 `url_pattern`(默认 `^/$`);`rest` 用 `url_patterns` list,每条带 `method_name` |
| `extractors[].method_source` | JSON path | json_rpc 必填 | 从 request body 取 method 名,通常 `body.method` |
| `extractors[].batch_handling` | enum | json_rpc 推荐 | `reject` 拒绝 batch 返 400 / `split` 拆成多条记录 / `tag_batch` 整 batch 当一条;**EVM 系必须 `split`**(reject 会破坏现有用户) |
| `extractors[].auth.type` | enum | 可选 | `none`(默认)/ `basic`(Bitcoin family 常见)/ `bearer` |

**2 模式覆盖 36 链证明**(代表链):

| family (链数) | 代表链 | extractor 配置 |
|---|---|---|
| jsonrpc (16) | arbitrum | 1 个 `json_rpc` extractor,`method_source: body.method`,`batch_handling: split` |
| rest (5) | algorand | 1 个 `rest` extractor,5 条 `url_patterns`(对应 5 个 REST 端点) |
| substrate (5) | acala | 1 个 `json_rpc` extractor(Substrate 是 JSON-RPC 2.0 之上的 method 命名空间) |
| tendermint (5) | celestia | 1 个 `json_rpc` extractor(Tendermint RPC 也是 JSON-RPC 2.0) |
| bitcoin_jsonrpc (4) | bch | 1 个 `json_rpc` extractor,`auth: {"type": "basic"}` |
| hedera_dual (1) | hedera | **2 个 extractor**:`rest`(mirror node `/api/v1/...`)+ `json_rpc`(EVM relay `/`)— extractors 数组天然支持多协议链 |

**100% 覆盖 36 链,0 BLOCKER,0 envoy 兜底**。

**关键设计决策**(与 OQ-5 初稿 4 模式的差异):

1. **2 模式而非 4 模式**:`json_rpc` 吞掉 `bitcoin_rpc` + `substrate` + `tendermint`(都是 JSON-RPC 2.0,仅 auth/method namespace 差异)
2. **删 `grpc` 模式**:36 链零 gRPC adapter family,YAGNI
3. **删 `ogmios` 模式**:cardano 已实测使用 `rest` family(见 `cardano.json _meta.adapter_family = "rest"`),0 chain 使用 ogmios
4. **`extractors` 永远是数组**:为支持 hedera 类双协议链(无需新机制),单协议链填 1 条即可
5. **`url_patterns` 用 list 而非单 regex**:algorand 5 个 endpoint 用 5 条独立 pattern 比 1 个复杂 regex 可读
6. **`batch_handling` 必填**:EVM batch JSON-RPC 是真实生产模式,proxy 必须明确处理策略

**违反契约的行为**(pre-commit hook 拒):

- `extractors[].protocol` 出现 `json_rpc` / `rest` 之外的值
- 出现 `proxy_extraction_lua` / `proxy_extraction_python` 字段
- json_rpc extractor 缺 `method_source`
- rest extractor 的 `url_patterns` 缺 `method_name`

### 1.8 `rpc_methods.mixed_weighted`(NS-2 权重契约,**mixed mode 推荐填**)

NS-2 要求 mixed mode 支持 weight 配置以模拟真实业务流量(`getBalance` 60% / `getBlock` 30% / `getLogs` 10%)。**向后兼容老 `mixed` 字符串字段**:旧用户配置不动,新增 `mixed_weighted` 字段时优先生效。

**Schema**:

```jsonc
{
  "rpc_methods": {
    "single": "eth_getBalance",
    "mixed":  "eth_getBalance,eth_getTransactionCount,eth_blockNumber,eth_gasPrice",  // 老字段保留
    "mixed_weighted": [                                                                 // 新字段(可选)
      {"method": "eth_getBalance",          "weight": 40},
      {"method": "eth_getTransactionCount", "weight": 30},
      {"method": "eth_blockNumber",         "weight": 20},
      {"method": "eth_gasPrice",            "weight": 10}
    ]
  }
}
```

**字段语义**:

| 字段 | 类型 | 必填 | 含义 |
|---|---|---|---|
| `mixed_weighted` | array | 可选(优先级高于 `mixed`) | 每条 `{method, weight}`;`method` 必须出现在 `param_formats` |
| `mixed_weighted[].weight` | int | ✓ | 整数权重,**不要求总和=100**(target_generator 按比例归一化) |

**weight 数值规则**:

1. 必须为正整数(>= 1)
2. 不要求总和 = 100,target_generator 内部按 `weight_i / sum(weights)` 归一化
3. 配置时建议总和 = 100(可读性)但非硬性
4. 权重源参考 `analysis-notes/research_notes/01-06/` 各 method "典型业务流量比例"

**优先级规则**(target_generator 实现):

```
if "mixed_weighted" in rpc_methods:
    use mixed_weighted  # 新模式,按权重生成 vegeta target
else:
    use mixed (legacy)  # 老模式,均匀分布
```

**违反契约的行为**(pre-commit hook 拒):

- `mixed_weighted[].method` 不在 `param_formats` key 中
- `mixed_weighted[].weight` <= 0 或非整数
- `mixed_weighted` 和 `mixed` 列出的 method 集合不一致(允许子集,不允许超集)

---

## 2. Adapter Family 契约(7 族封闭枚举)

### 2.1 7 族列表(实测 `tools/chain_adapters/` + 36 JSON `_meta.adapter_family` 分布)

| family | 协议特征 | 当前链数 | 代表链 | 文件 |
|---|---|---|---|---|
| `jsonrpc` | 标准 JSON-RPC 2.0,EVM / Solana / Sui / Starknet 等 | 16 | ethereum / bsc / polygon / base / scroll / solana / sui / starknet / aptos / algorand 等 | `jsonrpc.py` (5589 bytes) |
| `substrate` | Substrate / Polkadot 系 `state_*` / `chain_*` method | 5 | polkadot / kusama 等 | `substrate.py` (2429 bytes) |
| `tendermint` | Cosmos SDK / Tendermint RPC | 5 | cosmoshub 等 | `tendermint.py` (3103 bytes) |
| `rest` | 纯 REST,GET/POST 路径 | 4 | tezos 等 | `rest.py` (5275 bytes) |
| `bitcoin_jsonrpc` | Bitcoin Core JSON-RPC(认证 + 方法集差异) | 4 | bitcoin / litecoin 等 | `bitcoin_jsonrpc.py` (3090 bytes) |
| `ogmios` | Cardano Ogmios WebSocket-style | 1 | cardano | `ogmios.py` (2374 bytes) |
| `hedera_dual` | Mirror REST + JSON-RPC Relay 双协议 | 1 | hedera | `hedera_dual.py` (5040 bytes) |

**注**:实际 family 名以 `__init__.py` 工厂函数 `get_adapter(chain_name)` 读取 `_meta.adapter_family` 字段为准;每个 adapter 通过 `protocol_family` 方法返回 family 标识(非 class 属性,见 `base.py`)。完整 16+5+5+4+4+1+1 = **36 链对称覆盖**。

**封闭原则**:7 族即全部,新链**必须**归入其中之一,否则不准并入 main。

**新增 adapter family 的代价(NS-3 例外)**:
- 协议结构性差异 → 允许新建 adapter,记 ADR
- 仅参数差异 → 必须用现有 family + 新 `param_format` tag,**不准新建 adapter**

### 2.2 Adapter 必须实现的接口(Python 契约)

基类 `ChainAdapter` 在 `base.py` 定义,**当前 3 个 @abstractmethod**(实测 grep `^\s*@abstractmethod` `base.py` L34/L44/L53):

```python
class ChainAdapter:  # ABC in base.py
    @abstractmethod
    def build_vegeta_target(self, method: str, address: str, ...) -> dict:
        """根据 method + param_format 构造 vegeta target 一条 request"""

    @abstractmethod
    def health_check_request(self, rpc_url: str) -> dict:
        """节点健康检查(从 _meta.health_probe 读)"""

    @abstractmethod
    def parse_block_height(self, response_text: str) -> Optional[int]:
        """解析 block height(monitor 用)"""
```

**`protocol_family` 不是方法**,而是 `@register("family_name")` 装饰器**注入的 class attribute**(见 `base.py` L110-117 `register()`:`cls.protocol_family = family`)。每个 adapter 在文件顶部用 `@register("jsonrpc")` 等装饰器声明自己的 family,启动时 `base.py` 末尾 `from . import jsonrpc, rest, tendermint, bitcoin_jsonrpc, substrate, ogmios, hedera_dual` 触发注册,7 族 → `_REGISTRY` 字典。运行时 `get_adapter(chain_name)` 读 chain JSON 的 `_meta.adapter_family` 字段查表实例化。

**NS-3 强化(阶段 4 PoC 引入)**:为消除 `fetch_active_accounts.py` 硬编码 if/elif,需新增**第 4 个 @abstractmethod**:

```python
    def fetch_active_addresses(self, count: int, rpc_url: str) -> list[str]:
        """活跃账户抓取(替代 fetch_active_accounts.py 的硬编码 if/elif,OQ-9 a 方案)"""
```

此方法**当前未实现**(阶段 4 PoC 落地),详见 §6.1 与 [OPEN-QUESTIONS.md OQ-9](./OPEN-QUESTIONS.md)。

### 2.3 当前 7 族实现状态

| family | 实现状态 | L1 测试 | L3 e2e 验证链(12 healthy 子集) |
|---|---|---|---|
| `jsonrpc` | ✓ | PASS | ethereum / bsc / polygon / base / scroll / solana / sui / starknet / aptos / algorand |
| `substrate` | ✓ | PASS | (12 healthy 不含,在 24 known-broken 队列) |
| `tendermint` | ✓ | PASS | (12 healthy 不含) |
| `rest` | ✓ | PASS | (待实证) |
| `bitcoin_jsonrpc` | ✓ | PASS | (12 healthy 不含) |
| `ogmios` | ✓ | PASS | (12 healthy 不含,cardano L3 待跑) |
| `hedera_dual` | ✓ S3-E.3 升级 | PASS | hedera |

12 healthy / 24 known-broken 完整列表 + 各 family 当前 e2e 状态详见 [CURRENT-STATE.md](./CURRENT-STATE.md)。

---

## 3. 加新链 36 链 → 37 链 完整流程(范例:mantle)

### Step 1:写 JSON 模板

```bash
# 1. 选 adapter_family
#    mantle = EVM L2(Optimism 衍生),协议结构与 ethereum 一致 → jsonrpc 族

# 2. 复制最近模板
cp config/chains/ethereum.json config/chains/mantle.json

# 3. 改字段(只改 chain_type / params / methods / rpc_methods / param_formats / system_addresses / _meta)
```

模板示例:

```json
{
  "chain_type": "mantle",
  "rpc_url": "LOCAL_RPC_URL",
  "params": {
    "account_count": 100,
    "output_file": "mantle_addresses.txt",
    "target_address": "0x0000000000000000000000000000000000000000",
    "max_signatures": 0,
    "tx_batch_size": 50,
    "semaphore_limit": 10
  },
  "methods": {},
  "rpc_methods": {
    "single": "eth_getBalance",
    "mixed": "eth_getBalance,eth_getTransactionCount,eth_blockNumber,eth_gasPrice"
  },
  "param_formats": {
    "eth_getBalance": "address_latest",
    "eth_getTransactionCount": "address_latest",
    "eth_blockNumber": "no_params",
    "eth_gasPrice": "no_params"
  },
  "system_addresses": [
    "0x0000000000000000000000000000000000000000",
    "0x000000000000000000000000000000000000dead"
  ],
  "_meta": {
    "source": "manual",
    "baseline_sha": "<current_sha>",
    "adapter_family": "jsonrpc",
    "note": "Mantle L2 (Optimism stack EVM)"
  }
}
```

### Step 2:验证 schema

```bash
python3 tools/validate_chain_template.py config/chains/mantle.json
# 输出: PASS / FAIL + 缺失/多余字段提示
```

### Step 3:跑 L1 / L2 / L3

```bash
# L1: adapter 单测(测试存在: tests/test_chain_adapters.py)
python3 tests/test_chain_adapters.py

# L2: fetcher + monitor 集成(参考: tests/integration_s2_s3_full_chain.sh /
#     tests/smoke_mock_rpc_8chains.sh,新链需扩展或新建对应 smoke 脚本)
bash tests/integration_s2_s3_full_chain.sh

# L3: vegeta + monitor + report 全链路(真入口: blockchain_node_benchmark.sh)
BLOCKCHAIN_NODE=mantle bash blockchain_node_benchmark.sh
```

**通过条件**:L1+L2+L3 全绿 → 加入 12 healthy 链;任一红 → 进入 24 known-broken 队列,记 `_meta.known_broken_mixed`。

### Step 4:**0 Python 改动验证**(NS-3 硬指标)

```bash
git diff --stat origin/main..HEAD
# 必须只看到:
#   config/chains/mantle.json | XX ++++++++
# 不能看到任何 .py / .sh 改动
```

如果出现 .py / .sh 改动 → **NS-3 违规**,pre-commit hook 拒绝。

---

## 4. Schema 校验工具(必备)

### 4.1 `tools/validate_chain_template.py`(待建)

**功能**:
1. 检查 8 顶层字段齐全
2. 检查 `params` 6 子字段齐全
3. 检查 `rpc_methods.mixed` 列出的所有 method 在 `param_formats` 有对应 key
4. 检查 `_meta.adapter_family` 在 7 族 enum 内
5. 检查 `param_formats` 所有 value (格式 tag) 在 adapter family 已实现 tag enum 内
6. 若 `_meta.adapter_family` 含 rest → 检查 `_meta.rest_paths` 存在且每个 method 有 `{method, path}`

### 4.2 pre-commit hook 集成

`ci/check_chain_template.sh`(待建):

```bash
#!/bin/bash
# 任何 config/chains/*.json 改动触发
for f in $(git diff --cached --name-only | grep '^config/chains/.*\.json$'); do
    python3 tools/validate_chain_template.py "$f" || exit 1
done
```

### 4.3 L3 e2e 校验(36 链对称)

`tests/test_36chain_symmetry.py`(待建):
- 36 个 JSON 都过 schema 校验
- 12 healthy 链都能跑通 single workload
- 24 known-broken 链都有合法的 `_meta.known_broken_mixed` 记录

---

## 5. NS-3 边界:什么属于"加链",什么不属于

### 5.1 属于"加链"(零 Python 强制)

- 加第 N 条 EVM 兼容链(BSC 变种 / L2 等) → 复用 jsonrpc 族
- 加第 N 条 Sui 衍生链 → 复用 jsonrpc 族(sui 当前归 jsonrpc)
- 加第 N 条 Tezos 衍生链 → 复用 rest 族(tezos 当前归 rest)
- 修改某链的 `param_formats` / `rpc_methods.mixed` / `system_addresses` → 配置改动

### 5.2 不属于"加链"(允许改 Python,但走 ADR)

- 新增 `param_format` tag(例如 `address_block_range`)→ 改 adapter,记 ADR
- 新增 adapter family(出现协议结构性新形态)→ 新建 adapter 文件,记 ADR
- 修改 fetcher / monitor / report 通用逻辑 → 改 Python,但**不准引入 chain-specific 分支**

### 5.3 永远禁止(NS-3 死线)

- `if chain_type == "xxx":` 形态的 chain-specific 分支
- `case "$CHAIN_TYPE" in xxx) ... ;;` 形态的 shell 分支
- `KNOWN_BROKEN_CLI = {...}` 形态的硬编码集合(应改为 schema 字段)
- 任何"加第 N 条链需要改 .py / .sh"的工作流

**强制手段**:
- pre-commit hook `ci/check_parallel_entry.sh` v1.4.5 已有 5 check
- 阶段 5 加 check #6: `git diff --stat` 在 chain-only PR 上拒绝 .py / .sh 改动

---

## 6. 迁移路径(消除当前 NS-3 违规)

### 6.1 当前违规清单(OQ-9 实证)

| 文件 | 违规形态 | 阶段 5 方案 |
|---|---|---|
| `tools/fetch_active_accounts.py L665-678 create_adapter()` + L684 `fetch_all_signatures()` 嵌套 | 3+1 if/elif 分支硬编码 8 链 | 移到 `ChainAdapter.fetch_active_addresses()` |
| `config/config_loader.sh L371-405` | 8 链 case 硬编码 RPC URL | 移到 `_meta.rpc_url_dev` 字段 + 通用 loader |
| `tests/test_chain_adapters.py:404` | `assert len(KNOWN_BROKEN_CLI) == 24` | 改为读 `_meta.known_broken_mixed` 字段动态算 |

### 6.2 迁移阶段映射

- **阶段 1** (本阶段):写规范(本文档) + 1-C migration 文档,**不动代码**(遵守 W-5 代码冻结)
- **阶段 4 PoC**:solana 1 链验证新 adapter 接口(`fetch_active_addresses`) + 完成 §8 PoC 验收 8 条
- **阶段 5**:36 链全部 rollout,§6.1 三处违规一次性消除
- **OQ-9 (d)**:阶段 1 PR merge 后,单独 PR 给 fetcher / config_loader 临时注释 `# TODO(NS-3 / OQ-9): 阶段 5 消除`

### 6.3 为何此 defer 合法(no-deferred-bugs cross-class 4 条件逐条验证)

本节存在的原因:`no-deferred-bugs` skill 明确警告"transparency-record defer"(把违规公开记账但不修)是第 5 次违规模板。本文档 §6.1 列出 3 处当前 ownership 内的 NS-3 违规,§6.2 将其推到阶段 4/5 修复 —— 这必须通过 skill 的 cross-class defer 4 条件,否则 §6.2 = 违规。

**逐条验证**:

| 条件 | 验证 | 状态 |
|---|---|---|
| (1) 不同 class(不是"同 class 更难的实例") | 阶段 1 = SSOT 文档写作 / §6.1 三处 = Python+Shell 代码改造。`架构文档` 与 `adapter 接口重构` 是不同工种、不同 PR、不同 review 角度 | ✅ |
| (2) 真 follow-up(不是 TODO 注释 / "我会记得") | OQ-9 已记录在 `OPEN-QUESTIONS.md`(file+line+影响+方案 a/b/c/d 候选);本文档 todo `calib-4-poc-impl` / `calib-5-36chain-rollout` 在 session todo 列;OQ-9 (d) 临时注释 PR 是独立 tracked 工作项 | ✅ |
| (3) commit msg / 文档显式公开缺口 | §6.1 表格列出 3 处违规(文件+行号+形态);§6.2 时间线公开;`README.md` / `README_ZH.md` L15/L51/L277 已标注 "Evolving 36 chain template / 8 e2e";`CURRENT-STATE.md` 写明 12 healthy / 24 known-broken | ✅ |
| (4) 当前 PR 验证不被削弱 | **关键条件 — 见 §6.4 强化** | ⚠️ → ✅ via §6.4 |

### 6.4 条件 (4) 强化:阶段 4 PoC 作为本文档可执行性硬证据

**风险定性**:本文档声称 "NS-3 = 加链 100% 0 Python"(§0),但 §6.1 列出代码层 NS-3 实际是破的(fetcher / config_loader / KNOWN_BROKEN_CLI 三处)。如果阶段 4 PoC 没有强制硬验证,**本文档 = 规范写完但生产是另一回事**,与 [parallel-entry-trap](../../.hermes/skills/software-development/parallel-entry-trap/) 同构(文档/代码失配,文档自证不被代码佐证)。

**强化条款**(写入本规范,与 §8 PoC 验收 8 条互锁):

1. **硬 due date**:§6.1 三处违规消除的 due date = **阶段 5 36 链 rollout PR 合并前**。不是"future stage 模糊承诺",是 git 可验证的 milestone(阶段 5 rollout PR 不准 merge,如果三处违规仍在)。
2. **阶段 4 PoC 是文档可执行性验证点**:§8 列的 8 条验收**全过**才允许 rollout 36 链;少一条 = PoC 不通过 = 本文档 NS-3 声明形同虚设,必须暂停阶段 5 并回头检讨。
3. **阶段 4 PoC 的 §8 第 3、5 条** 是 `fetch_active_accounts.py` 重构的硬验证:
   - §8 #3:Solana 不再有 `if chain_type == "solana"` 分支
   - §8 #5:加 mock 第 37 链 dummy.json 时 `git diff --stat` 0 行 .py / .sh 改动

   这两条机器可验证,主观打分无法绕过。
4. **CI hook 加固**:阶段 4 PoC PR 必须新增 pre-commit check `ci/check_chain_only_pr.sh`,在 PR 标记为 "chain-add-only" 时拒绝 .py / .sh 改动(具体实现见 §4.2 框架)。
5. **本规范的撤销条件**:如果阶段 4 PoC 8 条**任一未过**,本文档 NS-3 章节(§0、§5、§8)必须改为"NS-3 是目标,当前未达成",而非维持"加链 100% 0 Python"的现在时声明。文档不准超前于实证。

### 6.5 与 no-deferred-bugs 5 次违规模板的对照(自审)

为防止本节自身又是 transparency-record defer 的新变体,逐条与 skill 5 次违规模板对照:

| skill 违规模板 | 本节 §6.3+§6.4 是否中招 |
|---|---|
| 第 1 次:决策菜单 "fix N / defer M" | 否 — 没有给用户菜单,§6.2 是规范说明 |
| 第 2 次:降级验证作为推荐 | 否 — §6.4 强化的是验收硬度,不是降级 |
| 第 3 次:降级作为co-equal middle option | 否 — 无 option |
| 第 4 次:feature-coverage v1 80% / v2 95% | 否 — NS-3 目标 100% 不下调,只是分阶段实施 |
| 第 5 次:transparency-record 记账即免责 | **风险点 — §6.4 用"硬 due date + 机器验证 + 撤销条件"防止退化为单纯记账** |

第 5 次风险残留:如果阶段 4 PoC 真的过不了 8 条,而我又找借口绕过 §6.4 #5(撤销条件),那就是再次违规。**§6.4 #5 是 skill 合规的最后一道闸**,必须在阶段 4 报告时无条件执行。

---

## 7. 范围边界(本文档**不**包含)

为避免走偏,以下显式不在本文档范围:

1. **proxy 的协议解析层**(per-method 资源归因) → 见 [per-method-proxy-architecture-zh.md](./per-method-proxy-architecture-zh.md)
2. **NS-2 mixed RPC 权重算法**(40/30/20/10/...) → 见 NORTH-STAR.md NS-2 §2.3
3. **adapter Python 内部实现细节**(代码结构 / 测试组织) → 见各 adapter `.py` 文件 file-notes(阶段 6 补)
4. **vegeta target 文件生成器**(`build_targets.py`) → 调用 adapter 接口,实现细节非本规范
5. **fetcher 失败重试 / 节点降级**策略 → 工程实现,非 schema 契约
6. **多链 e2e 编排**(`blockchain_node_benchmark.sh` + `tests/run_all_s2_s5.sh` 等)→ 工程脚本,非 schema 契约
7. **配置版本号 / migration 工具**(JSON schema v2 → v3) → 阶段 6 引入
8. **报告生成器读取 chain template** → 已有,只读不写,不属于"加链"

---

## 8. 验收清单(本规范 PoC 通过条件)

阶段 4 PoC(solana 1 链)若声称"NS-3 规范落地",必须满足:

1. ✅ `config/chains/solana.json` 通过 `validate_chain_template.py`
2. ✅ Solana adapter 实现 `fetch_active_addresses()` 接口
3. ✅ `tools/fetch_active_accounts.py` 不再有 `if chain_type == "solana"` 分支(通过 adapter dispatch)—— **两处都消除**:`create_adapter()` L665 + `fetch_all_signatures()` L684 嵌套
4. ✅ 加 mock 第 37 链 `dummy.json`(jsonrpc 族),跑 schema 校验 PASS
5. ✅ 加 dummy.json 时 `git diff --stat` **0 行 .py / .sh 改动**
6. ✅ 12 healthy 链 L1 全过(不能因为 adapter 重构破坏现状)
7. ✅ pre-commit hook `check_chain_template.sh` 集成 + 故意写错误 JSON 测试拒绝
8. ✅ L3 e2e solana 跑通 single + mixed workload(老 baseline 对照)

少一条 = PoC 不通过 = 不准 rollout 36 链。

**与 §6.4 #5 撤销条件互锁**:8 条任一未过 → 本文档 §0、§5、§8 的 "NS-3 = 加链 100% 0 Python" 现在时声明必须改为"NS-3 是目标,当前未达成"。文档不准超前于实证。阶段 4 PoC 报告时无条件执行此撤销,不准找借口绕过。

---

## 9. ADR 索引

本文档**待沉淀**的 ADR(阶段 1 merge 时一起补):

- **ADR-002**:为何 7 族封闭 + 不允许任意新建 adapter
- **ADR-003**:为何 `param_format` 是 enum 字符串而非自由 dict
- **ADR-004**:为何 `fetch_active_addresses` 必须移到 adapter(NS-3 强制)
- **ADR-005**:为何 schema 校验放在 pre-commit + L3,而非 runtime

---

## 10. 与 1-A / 1-C 的关系

- **1-A** (`per-method-proxy-architecture-zh.md`) 定义**运行时架构**(数据流 / proxy / 字段算账)
- **1-B** (本文档) 定义**配置契约**(加链 schema / NS-3 边界)
- **1-C** (`migration-from-legacy-zh.md`) 定义**迁移路径**(从当前 v1.4.5 → 阶段 5 末态)

三份合在一起 = 阶段 1 输出 = main 分支永久参考点(锁北极星)。
