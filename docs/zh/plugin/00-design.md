# Chain-as-Plugin 框架设计稿(v1.4.7)

**状态**:DRAFT,等 user review 后实施
**日期**:2026-05-23
**作者**:Hermes Agent(决策门户:`decision-with-tradeoffs` + R1-PRIME 实证 baseline)
**前置**:R1-PRIME audit 已 commit(`bc6a3ae`、`8402291`),8 链 method-level 实证完成

---

## 0. 目的与边界

### 0.1 设计目标(可验收)

| 目标 | 验收口径 |
|---|---|
| G1. 业务方加新链**只需丢 JSON**(覆盖率 ≥ 80% 链) | 复用 family 的新链:0 行 Python,1 个 `config/chains/<chain>.json` |
| G2. 加新 family(SVM / EVM / StarkVM / MoveVM 之外)**只需写 1 个 adapter + 1 个 JSON** | 新增 `adapters/<family>.py` + `config/chains/<chain>.json`,不改 `fetch_active_accounts.py` |
| G3. 现有 8 链全部从 `here-doc` 迁出后**功能等价**(行为零回归) | 8 链 e2e_smoke matrix 全 PASS;`generate_auto_config` 输出与迁移前 diff = 空 |
| G4. CHAIN_CONFIG 环境变量协议**完全兼容**当前 `fetch_active_accounts.py` / `target_generator.sh` / `mock_rpc_server.py` | 这 3 个消费者**不改读取逻辑**(只改 `create_adapter()` 派遣) |
| G5. plugin 加载有**显式失败模式**(unknown chain 抛错,不静默退默认) | `load_chain("xxx")` 找不到 JSON 抛 `ChainNotRegisteredError` |

### 0.2 非目标(本期不做)

- ❌ Plugin 热加载(进程内 reload):每次跑测前从盘上读 JSON,无需热加载
- ❌ Plugin 远端拉取(URL/git):JSON 全部 in-tree,版本跟随 git
- ❌ Plugin 间依赖图:每条链独立,无 inherit / extends
- ❌ Plugin 沙箱:adapter 是 in-process Python,信任 repo 内代码

### 0.3 反转条件(什么时候应该改方案)

| 信号 | 反转动作 |
|---|---|
| P1-2 调研发现 ≥ 3 链 schema 装不下(非 family 异构) | 加 `extras: {...}` free-form 字段,但要写 schema 文档说明 |
| 用户改主意要求"加链 0 Python" 全覆盖 28 链 | 引入 family-agnostic generic adapter(本期不做,因为 Cosmos/Aptos/Cardano 模型差异太大) |
| `chain_type` 派遣性能成 bottleneck | 改 `__init_subclass__` 注册,但本期单进程跑测,无此压力 |

---

## 1. 现状分析(为什么要拆 plugin)

### 1.1 现有 8 链 here-doc 字段矩阵(轴 1 实证)

来自 `config/config_loader.sh` `UNIFIED_BLOCKCHAIN_CONFIG` 解析:

| 字段 | 8 链覆盖 | 用途 |
|---|---|---|
| `chain_type` | 全 ✓ | adapter 派遣 key |
| `rpc_url` | 全 ✓ | endpoint(运行时替换为 `LOCAL_RPC_URL`) |
| `params.{account_count, output_file, target_address, max_signatures, tx_batch_size, semaphore_limit}` | 全 ✓ | adapter runtime 参数 |
| `methods.get_transaction` | 全 ✓ | adapter 抓 tx 用的 method 名 |
| `methods.get_signatures` | solana 独占 | SolanaAdapter |
| `methods.get_logs` | EVM 5 链 | EthereumAdapter |
| `methods.get_events_native` | starknet 独占 | StarknetAdapter |
| `methods.get_owned_objects`, `get_transactions` | sui 独占 | SuiAdapter |
| `rpc_methods.{single, mixed}` | 全 ✓ | target_generator.sh 生成 vegeta target |
| `param_formats.<method>` | 全 ✓ | target_generator.sh 构造 params(map free-form) |
| `system_addresses` | 全 ✓ | adapter 过滤系统地址 |

**结论**:**没有任何字段是某 family 强制独占**(`methods.*` 子键虽是 family-specific 但都收在同一个 `methods` 容器里)。schema 可以做成**严格必填 + family-aware 可选 + free-form param map**。

### 1.2 现有下游消费者(轴 2 实证)

```
┌──────────────────────────────────────────────────────────────┐
│ config/config_loader.sh                                       │
│  └ UNIFIED_BLOCKCHAIN_CONFIG (here-doc JSON, 8 链一锅)        │
│  └ generate_auto_config() 注入 LOCAL_RPC_URL 等               │
│  └ export CHAIN_CONFIG=<chain 子 JSON>                       │
└──────────────────────────────────────────────────────────────┘
        │
        ▼ 环境变量 CHAIN_CONFIG (JSON string)
        │
   ┌────┴───────────────────────────────┐
   ▼                ▼                   ▼
┌──────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ fetch_active │ │ target_generator │ │ mock_rpc_server  │
│ _accounts.py │ │   .sh            │ │   .py            │
│              │ │                  │ │ (mock data only, │
│ create_      │ │ jq .rpc_methods  │ │  不读 config)    │
│  adapter()   │ │ jq .param_       │ │                  │
│  ⚠️ 硬编码    │ │  formats         │ │                  │
│  chain_type  │ │                  │ │                  │
│  → Adapter   │ │                  │ │                  │
│  分支         │ │                  │ │                  │
└──────────────┘ └──────────────────┘ └──────────────────┘
```

**唯一硬编码点** = `tools/fetch_active_accounts.py:663-674` 的 `create_adapter()` 5 分支大 if-else。这是 **chain-as-plugin 的唯一真正阻碍**。其他消费者读 JSON 不分链,**已经是 plugin 友好**。

---

## 2. 设计:Plugin 框架

### 2.1 目录结构

```
blockchain-node-benchmark/
├── config/
│   ├── config_loader.sh           # 改:从 chains/*.json 加载,移除 UNIFIED_BLOCKCHAIN_CONFIG here-doc
│   └── chains/                    # 新增
│       ├── solana.json
│       ├── ethereum.json
│       ├── bsc.json
│       ├── base.json
│       ├── scroll.json
│       ├── polygon.json
│       ├── starknet.json
│       ├── sui.json
│       └── _schema.json           # JSON Schema(可选,人工 review 用)
│
├── tools/
│   ├── fetch_active_accounts.py   # 改:create_adapter() 走 registry
│   ├── adapters/                  # 新增
│   │   ├── __init__.py            # ADAPTER_REGISTRY 暴露
│   │   ├── _base.py               # ChainAdapter ABC
│   │   ├── solana.py              # SolanaAdapter(从 fetch_active_accounts.py 迁出)
│   │   ├── ethereum.py            # EthereumAdapter
│   │   ├── starknet.py            # StarknetAdapter
│   │   └── sui.py                 # SuiAdapter
│   └── plugin_loader.py           # 新增:load_chain(name) / list_chains() / family_of(name)
│
└── docs/
    ├── zh/plugin/
    │   ├── 00-design.md           # 本文档
    │   ├── 01-adding-a-chain.md   # how-to:加新链(JSON only / 新 family)
    │   └── 02-schema.md           # JSON schema 字段说明
    └── en/plugin/                 # 同上
```

### 2.2 `config/chains/<chain>.json` schema

**示例**(solana.json,基于 R1-PRIME 修正后状态):

```json
{
  "$schema": "../_schema.json",
  "chain_id": "solana",
  "chain_type": "solana",
  "family": "svm",
  "official_rpc": "https://api.mainnet-beta.solana.com",
  "doc_base": "https://solana.com/docs/rpc",
  "rpc_url_var": "LOCAL_RPC_URL",
  "params": {
    "account_count": "ACCOUNT_COUNT",
    "output_file": "ACCOUNTS_OUTPUT_FILE",
    "target_address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "max_signatures": "ACCOUNT_MAX_SIGNATURES",
    "tx_batch_size": "ACCOUNT_TX_BATCH_SIZE",
    "semaphore_limit": "ACCOUNT_SEMAPHORE_LIMIT"
  },
  "methods": {
    "get_signatures": "getSignaturesForAddress",
    "get_transaction": "getTransaction"
  },
  "system_addresses": [
    "11111111111111111111111111111111",
    "..."
  ],
  "rpc_methods": {
    "single": "getAccountInfo",
    "mixed": "getAccountInfo,getBalance,getTokenAccountBalance,getLatestBlockhash,getBlockHeight"
  },
  "param_formats": {
    "getAccountInfo": "single_address",
    "getBalance": "single_address",
    "getTokenAccountBalance": "single_address",
    "getLatestBlockhash": "no_params",
    "getBlockHeight": "no_params"
  }
}
```

### 2.3 Schema 字段约束

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `chain_id` | string | ✓ | 文件名(不带 `.json`)= chain_id,用于 plugin loader 查找 |
| `chain_type` | string | ✓ | adapter 派遣 key(可 = chain_id 也可 = family 别名) |
| `family` | enum: svm/evm/starkvm/movevm/utxo/cosmos/...  | ✓ | adapter 实现类映射;新 family 必须在 `adapters/<family>.py` 实现 ChainAdapter |
| `official_rpc` | URL | ✓ | 官方推荐 mainnet endpoint(audit 工具用) |
| `doc_base` | URL | ✓ | 文档基址(audit L1_doc 用) |
| `rpc_url_var` | string | ✓ | 运行时替换 token(默认 `LOCAL_RPC_URL`) |
| `params` | object | ✓ | adapter runtime params,key 自由 |
| `methods` | object | ✓ | adapter 用的 method 名映射(至少有 `get_transaction`) |
| `system_addresses` | array<string> | ✓ | 过滤系统地址,可空数组 |
| `rpc_methods.single` | string | ✓ | benchmark 单 method 模式 |
| `rpc_methods.mixed` | string | ✓ | benchmark mixed 模式(逗号分隔 method list) |
| `param_formats` | object | ✓ | mixed 内每 method 的 param 模板;key = method 名,value = format enum |
| `param_formats.<method>` | enum: `no_params/single_address/address_latest/latest_address/address_storage_latest/address_key_latest/address_with_options` | ✓ | 见 `target_generator.sh:77-108` |

**严格性**:
- ❌ 不允许额外字段(JSON Schema `additionalProperties: false`)— 防字段拼写错静默忽略
- ✅ `params` / `methods` / `param_formats` 内部 key 自由(因为各链不一样)

### 2.4 `tools/adapters/_base.py` ABC 接口

```python
from abc import ABC, abstractmethod
from typing import List, Optional

class ChainAdapter(ABC):
    """所有 family adapter 的契约。每 family 一个实现类。"""

    chain_type: str  # 子类必须设(用作 registry key 之一,validation 用)
    family: str      # 同上

    def __init__(self, config: dict):
        self.config = config
        self.chain_type = config["chain_type"]
        self.family = config["family"]
        self.target_address = config["params"]["target_address"]
        # ...

    @abstractmethod
    async def fetch_signatures(self, address: str, cursor=None, limit=500, verbose=False) -> List[dict]:
        """抓 tx signatures(或等价单位 — sui 的 digest,starknet 的 hash)。"""

    @abstractmethod
    async def fetch_transaction(self, sig_or_hash: str, verbose=False) -> Optional[dict]:
        """按 signature/hash 抓单 tx detail。"""

    @abstractmethod
    def extract_accounts_from_transaction(self, tx: dict) -> List[str]:
        """从 tx detail 抽出涉及的 account 地址。"""

    # 可选 hooks(默认实现):
    def filter_system_addresses(self, addrs: List[str]) -> List[str]:
        sys_set = set(self.config.get("system_addresses", []))
        return [a for a in addrs if a not in sys_set]
```

### 2.5 `tools/plugin_loader.py`

```python
"""Chain plugin loader. 单一职责:从 config/chains/*.json 加载 + adapter 派遣。"""
from __future__ import annotations
import json, importlib, os
from pathlib import Path
from typing import Dict

REPO = Path(__file__).resolve().parent.parent
CHAINS_DIR = REPO / "config" / "chains"
ADAPTERS_PKG = "tools.adapters"

# family → module name 映射(显式声明,避免 importlib 猜)
FAMILY_MODULES = {
    "svm": "solana",        # 当前只有 solana 一员
    "evm": "ethereum",      # ethereum/bsc/base/scroll/polygon 共用
    "starkvm": "starknet",
    "movevm": "sui",
}

class ChainNotRegisteredError(LookupError):
    pass

class UnknownFamilyError(LookupError):
    pass

def list_chains() -> list[str]:
    """返回所有已注册 chain_id(目录扫描)。"""
    return sorted(p.stem for p in CHAINS_DIR.glob("*.json") if not p.stem.startswith("_"))

def load_chain(chain_id: str) -> dict:
    """加载 chain JSON 配置 + 校验必填字段。"""
    path = CHAINS_DIR / f"{chain_id}.json"
    if not path.exists():
        raise ChainNotRegisteredError(
            f"Chain '{chain_id}' not found. Available: {list_chains()}"
        )
    cfg = json.loads(path.read_text())
    _validate(cfg, chain_id)
    return cfg

def _validate(cfg: dict, chain_id: str):
    """最小字段校验(JSON Schema 强校验可后续加)。"""
    required = ["chain_type", "family", "official_rpc", "rpc_url_var",
                "params", "methods", "rpc_methods", "param_formats", "system_addresses"]
    missing = [k for k in required if k not in cfg]
    if missing:
        raise ValueError(f"Chain '{chain_id}' missing fields: {missing}")
    if cfg["family"] not in FAMILY_MODULES:
        raise UnknownFamilyError(
            f"Chain '{chain_id}' family='{cfg['family']}' not in {list(FAMILY_MODULES)}. "
            f"Add tools/adapters/<family>.py + register in FAMILY_MODULES."
        )

def create_adapter(cfg: dict):
    """从 cfg 派遣 adapter 实例。替代旧 create_adapter() 5 分支大 if-else。"""
    family = cfg["family"]
    module_name = FAMILY_MODULES.get(family)
    if not module_name:
        raise UnknownFamilyError(f"family='{family}' not registered")
    mod = importlib.import_module(f"{ADAPTERS_PKG}.{module_name}")
    # 约定:每 family module 暴露 ADAPTER_CLASS
    return mod.ADAPTER_CLASS(cfg)
```

### 2.6 `tools/fetch_active_accounts.py` 改动

```python
# OLD (L661-674):
def create_adapter(config):
    chain_type = config["chain_type"].lower()
    if chain_type == "solana":
        return SolanaAdapter(config)
    elif chain_type in ["ethereum", "bsc", "base", "scroll", "polygon"]:
        return EthereumAdapter(config)
    elif chain_type == "starknet":
        return StarknetAdapter(config)
    elif chain_type == "sui":
        return SuiAdapter(config)
    else:
        raise ValueError(f"Unsupported chain type: {chain_type}")

# NEW:
from tools.plugin_loader import create_adapter as _plugin_create_adapter
def create_adapter(config):
    return _plugin_create_adapter(config)
```

**另一处** `fetch_all_signatures()` L684 `if adapter.chain_type == "solana"` 也需改 — Solana 的 cursor 语义不同。**修法**:把 cursor 推进逻辑移到 adapter 内的 `next_cursor(batch)` 方法,`fetch_all_signatures()` 只调 `adapter.next_cursor(batch)`,**外层不再 if chain_type**。

### 2.7 `config/config_loader.sh` 改动

**移除**:`UNIFIED_BLOCKCHAIN_CONFIG=$(cat <<'EOF' ... EOF)` here-doc(L402-651,~250 行)

**新增** loader 函数:

```bash
load_chain_config() {
    local chain_id="$1"
    local chain_file="${HERE_DIR}/chains/${chain_id}.json"
    if [[ ! -f "$chain_file" ]]; then
        echo "❌ Chain '${chain_id}' not registered. Available:" >&2
        ls "${HERE_DIR}/chains/" | grep -v '^_' | sed 's/.json$//' >&2
        return 1
    fi
    # 注入 LOCAL_RPC_URL 等运行时变量(原来由 generate_auto_config 做)
    jq --arg url "$LOCAL_RPC_URL" '.rpc_url = $url' "$chain_file"
}

# generate_auto_config 改为:
# CHAIN_CONFIG=$(load_chain_config "$BLOCKCHAIN_NODE")
# export CHAIN_CONFIG
```

**保留**:`get_param_format_from_json()`、`get_current_rpc_methods()`(消费 `CHAIN_CONFIG` 的逻辑不变)

### 2.8 测试策略(P2-4 执行)

| 层 | 验证内容 | 通过条件 |
|---|---|---|
| L1 单测 | `plugin_loader.load_chain("solana")` 等 8 链全 OK,unknown 链抛 `ChainNotRegisteredError` | 8 + 1 = 9 case PASS |
| L1 单测 | `create_adapter()` 派遣到正确 class | 8 链 isinstance check |
| L2 集成 | 8 链 `target_generator.sh` 跑通,生成的 target.json 与迁移前 byte-identical | `diff -r` 空 |
| L2 集成 | 8 链 `fetch_active_accounts.py --count 5 --max-sigs 10` 跑通 | 不抛错,有 output |
| L3 e2e | 8 链 e2e_smoke matrix(`tests/e2e_smoke/` 已有) | 全 PASS |
| L3 e2e | 迁移前后 audit 结果 diff = 空(同 endpoint 同 method) | matrix 一致 |

---

## 3. 迁移路径(P2-1 ~ P2-5 子任务拆分)

### 3.1 P2-1:框架落地 + 8 链 JSON 拆分

1. 写 `tools/adapters/_base.py` ChainAdapter ABC
2. 写 `tools/plugin_loader.py`
3. 把 4 个现有 adapter class 从 `fetch_active_accounts.py` 迁出到 `tools/adapters/{solana,ethereum,starknet,sui}.py`,每文件末尾 `ADAPTER_CLASS = XxxAdapter`
4. 改 `fetch_active_accounts.py`:`create_adapter()` 走 plugin_loader,`fetch_all_signatures()` 用 `adapter.next_cursor()` 替换 `if chain_type == "solana"`
5. 把 here-doc 拆成 `config/chains/{solana,ethereum,bsc,base,scroll,polygon,starknet,sui}.json` 8 份(加 `family` 字段)
6. 改 `config/config_loader.sh`:移除 here-doc,加 `load_chain_config()`
7. L1+L2+L3 全跑通(P2-4),**byte-identical** 验证

### 3.2 P2-2 / P2-3:加新链(本期不属于 P2-DESIGN)

- 15 新核心 adapter 链(Aptos / Cosmos / Cardano 等):每链 1 JSON,可能加 1 family adapter
- 4 Bitcoin 复用链:全部走 utxo family,只丢 JSON

### 3.3 P2-5:commit + push

按 logical commit 拆:
- C3:plugin loader + ABC + 8 adapter 迁出(纯重构,行为零变)
- C4:8 链 JSON 拆分 + config_loader.sh 重写
- C5:fetch_active_accounts.py 接 plugin_loader
- C6:e2e_smoke 验证 + 文档更新

---

## 4. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| `fetch_active_accounts.py:684 if chain_type == "solana"` 等隐藏分支没找全 | 中 | 行为回归 | search_files 全文 grep `chain_type ==` / `chain_type.lower()` 再过 audit Q3 |
| JSON 拆分后 jq 解析与 here-doc 不一致(空格/编码) | 低 | 字节级 diff 失败 | 迁移脚本 jq round-trip + `diff` 验证 |
| `adapter.next_cursor()` 接口对 sui 不适用(sui 用 cursor object) | 中 | sui adapter 改不动 | 接口 v0 设为 `Optional[Any]`,each adapter 自由返(只要 self 能消费) |
| `_schema.json` 没写 → 加链人写错字段不报错 | 中 | plugin 静默挂 | `_validate()` 必填字段硬检查;Schema 可后续加 |
| target_generator.sh 的 jq query 路径与新 JSON 不兼容 | 低 | bench 跑不起 | P2-4 L2 集成 byte-identical 校验会发现 |

---

## 5. 决策门(decision-with-tradeoffs)

### D1:family 显式声明 vs 自动推断
- **推荐 显式声明**(`family` 字段必填)
- 理由:① audit/loader 错误信息友好(指明缺哪 family);② 加新链时强制思考归属
- 反转条件:family 数量 > 12 之后管理成本高,考虑自动推断
- 残余风险:写 JSON 时填错 family,在 `_validate()` 抛 UnknownFamilyError 兜底

### D2:adapter 派遣机制 — registry dict vs `__init_subclass__`
- **推荐 显式 FAMILY_MODULES dict**(`plugin_loader.py:14`)
- 理由:① import-time 副作用少,debug 友好;② 不依赖 import 顺序;③ list 出来直接知道支持哪些 family
- 反转条件:family 数 > 20 维护成本高,改 `__init_subclass__` 自注册
- 残余风险:加新 family 要改 plugin_loader.py(1 行),不算"0 改动"

### D3:JSON 字段严格性 — `additionalProperties: false` 还是允许 extras
- **推荐 严格**(JSON Schema `additionalProperties: false`)
- 理由:防字段拼写错被静默忽略(典型 bug:`rpcUrl` 写成 `rpc_url` 反之)
- 反转条件:P1-2 调研发现 ≥ 3 链需要 family-specific 扩展字段,改用 `extras: { ... }` 沙箱
- 残余风险:正常 — 严格性比灵活性更重要(失败要响)

### D4:rpc_url 注入时机 — 加载时 vs 消费时
- **推荐 加载时**(`load_chain_config()` 用 jq 注入 `LOCAL_RPC_URL`)
- 理由:与现有 `generate_auto_config()` 行为一致,下游 consumer 无感
- 反转条件:无(此为兼容性约束)

### D5:迁移路径 — 一次性 vs 渐进
- **推荐 一次性**(8 链一起拆,单 PR)
- 理由:① 8 链都已有 here-doc,部分迁移会留双源真值地狱;② byte-identical diff 一次过比 8 次过省事
- 反转条件:8 链中有 ≥ 2 链 e2e_smoke 已 broken,先修 broken 再迁
- 残余风险:diff 大,review 难;缓解 = 拆 4 个 logical commit(loader / adapter 迁出 / JSON 拆分 / 接线)

---

## 6. 验收清单(P2-1 完成判定)

- [ ] `tools/adapters/_base.py` + 4 adapter file 全部就位
- [ ] `tools/plugin_loader.py` 8 链都能 `load_chain()` + `create_adapter()`
- [ ] `tools/plugin_loader.py` unknown chain 抛 `ChainNotRegisteredError` + 给出可用列表
- [ ] `config/chains/*.json` 8 文件 + `_schema.json`(可选)
- [ ] `config/config_loader.sh` 移除 here-doc,改 `load_chain_config()`
- [ ] `tools/fetch_active_accounts.py` 不再有 `if chain_type ==` 硬编码
- [ ] L1 + L2 + L3 测试全 PASS
- [ ] 8 链 audit 重跑:matrix diff = 空(method/endpoint 没变)
- [ ] 8 链 target_generator 输出:与迁移前 byte-identical
- [ ] critical-self-audit-after-fix 三问通过(caller blind / reader blind / 能跑)

---

## 7. 历史

| 日期 | 作者 | 变更 |
|---|---|---|
| 2026-05-23 | Hermes Agent | DRAFT v1,等 user review |
