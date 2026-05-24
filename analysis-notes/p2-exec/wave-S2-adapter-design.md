# Wave S2 — Adapter 骨架设计稿

**Phase**: S2 (adapter-first, 设计学合规版)
**Baseline HEAD**: `9e341b2` (S0.7-norm)
**目标**: 6 族 ABC + reference impl + 单测,完全替换 target_generator.sh 与 common_functions.sh 的硬编码 case 链型分支

## 1. 设计学原则 (R20 + AP11)

- **抽象先于具体**: ABC 必须在任何 chain handler 之前完成
- **DIP**: target_generator.sh 依赖 ChainAdapter 接口,不依赖具体协议
- **OCP**: 加新链 = 加 chain template + 选 adapter 族(或新增 adapter 族);不改 target_generator
- **ISP**: ABC 只暴露 4 个方法,不让某些族实现不需要的接口
- **YAGNI**: 不预设 batch RPC / streaming / WebSocket — 它们当前没人用

## 2. 协议族识别 (6 族)

通过分析 36 链调研稿 + baseline 实现,识别出 6 个不可合并的协议族:

| 族 | 代表链 | 协议特征 | reference impl |
|---|---|---|---|
| **JsonRpc** | ethereum, bsc, polygon, base, scroll, arbitrum, optimism, zksync-era, linea, solana, sui, starknet, near, avalanche-c, tron | POST JSON-RPC 2.0 标准包 | `JsonRpcAdapter` |
| **Rest** | aptos, hedera, algorand, ton | HTTP GET/POST + RESTful path | `RestAdapter` |
| **Tendermint** | cosmos-hub, osmosis, celestia, injective, sei | Tendermint RPC (类 JSON-RPC 但 params 是 object 非 array) | `TendermintAdapter` |
| **BitcoinJsonRpc** | bitcoin, litecoin, dogecoin, bch | JSON-RPC 但需 HTTP Basic Auth + params 是 positional | `BitcoinJsonRpcAdapter` |
| **Substrate** | polkadot, kusama, acala, moonbeam, astar | Substrate JSON-RPC (state_*, chain_*) | `SubstrateAdapter` |
| **Ogmios** | cardano | Ogmios WebSocket(降级为 HTTP POST JSON 包) | `OgmiosAdapter` |

**协议族归属表(36 链)**:

```
JsonRpc      (15): arbitrum avalanche-c avalanche-x base bsc ethereum linea near optimism polygon scroll solana starknet sui tron zksync-era
Rest         (4):  algorand aptos hedera ton
Tendermint   (5):  celestia cosmos-hub injective osmosis sei
BitcoinJsonRpc(4): bch bitcoin dogecoin litecoin
Substrate    (5):  acala astar kusama moonbeam polkadot
Ogmios       (1):  cardano
─────────────────
Tezos (1) 待定 — 调研稿说"主要 REST API + 少量 JSON-RPC",归 Rest 族,
但其 baking-node block_height 走 /chains/main/blocks/head,无 JSON-RPC
─────────────────
Tezos        (1):  tezos  ← 归 Rest 族
─────────────────
合计 36 ✓
```

## 3. ABC 接口签名

```python
# tools/chain_adapters/base.py
from abc import ABC, abstractmethod
from typing import Optional

class ChainAdapter(ABC):
    """Per-chain protocol adapter. Stateless. Returns vegeta-compatible dicts."""

    @property
    @abstractmethod
    def protocol_family(self) -> str:
        """One of: jsonrpc | rest | tendermint | bitcoin_jsonrpc | substrate | ogmios"""

    @abstractmethod
    def build_vegeta_target(
        self, method: str, address: str, rpc_url: str, param_format: str,
    ) -> dict:
        """Return vegeta target: {method, url, header, body(base64)}.

        method        — RPC method name from chain template (e.g. "eth_getBalance")
        address       — pre-resolved real address from accounts list
        rpc_url       — LOCAL_RPC_URL
        param_format  — from chain template params field (e.g. "address_latest")
        """

    @abstractmethod
    def health_check_request(self, rpc_url: str) -> dict:
        """Return curl args for health probe: {method, url, headers, body, expect_jq, parse_jq}"""

    @abstractmethod
    def parse_block_height(self, response_text: str) -> Optional[int]:
        """Parse block height from health response. Returns None on failure."""
```

## 4. 接入点 (最小侵入性)

**改造点 1: `tools/target_generator.sh` L67-124 `generate_rpc_json()`**

旧:bash 硬编码 7 个 param_format case + JSON-RPC 包格式
新:`generate_rpc_json` 调用 Python 桥 `tools/chain_adapters/cli.py build-target ...`,返回 vegeta target JSON 字符串

```bash
generate_rpc_json() {
    local method="$1" address="$2"
    python3 "${TOOL_DIR}/chain_adapters/cli.py" build-target \
        --chain "$BLOCKCHAIN_NODE" \
        --method "$method" \
        --address "$address" \
        --rpc-url "$LOCAL_RPC_URL"
}
```

**改造点 2: `core/common_functions.sh` L180-281 `get_block_height()`**

旧:bash case 6 个链型 case 块(curl + jq + 格式校验)
新:`get_block_height` 调用 `tools/chain_adapters/cli.py health-probe --chain ... --rpc-url ...`,返回 decimal int 或 N/A

**为何用 Python 桥而非纯 bash adapter**: bash 不支持多态/继承,做 6 族 ABC 会退化成 sourcable 函数+case dispatch,绕一圈回到硬编码。Python 是当前 repo 已有依赖(tools/mock_rpc_server.py / normalize_chain_templates.py 都是 Python)。

## 5. Chain Template 新字段

每个 `config/chains/<name>.json` 增加:

```json
{
  "_meta": {
    "adapter_family": "jsonrpc"   // 6 族之一,必填
  }
}
```

S0.7-norm 已经在 20 个非 jsonrpc 链上加 `adapter_required: true`,本步 S2 把它细化为 `adapter_family` 显式枚举(可推断:`adapter_required=false → jsonrpc`,其余 20 链按上表归族)。

## 6. 反转条件(S2 完成自检不通过则退回)

- 若 6 族 ABC 抽象不出共同 `build_vegeta_target` 签名(某族需额外参数)→ 加可选参数(用 kwargs),不退回族数
- 若 6 族 reference impl 单测在 baseline 8 链 vegeta target 字节级对比有任何差异 → 必须修复 adapter 直到对比通过,不允许 defer
- 若 master_qps_executor.sh 端到端跑 baseline 8 链回归失败 → 必须修复,不允许 fallback 到旧硬编码路径

## 7. 验收门(S2.5)

- [ ] 6 adapter class 实现完整(JsonRpc/Rest/Tendermint/BitcoinJsonRpc/Substrate/Ogmios)
- [ ] 36 chain template 全部 `_meta.adapter_family` 填好
- [ ] `tools/chain_adapters/cli.py build-target` 对 baseline 8 链 vegeta target 字节级 == 原 bash 路径输出
- [ ] target_generator.sh / common_functions.sh 改造完成,新路径
- [ ] L1 单测: 每族 ≥ 1 测试用例
- [ ] L2 集成测: baseline 8 链生成 target 走完 mock RPC server,200 OK
- [ ] L3 e2e: `BLOCKCHAIN_NODE=solana ./blockchain_node_benchmark.sh --quick --single` 真跑通,产物与 baseline 一致

## 8. 时间盒

- S2.2 adapter 实现: 90 分钟
- S2.3 单测 + 接入点改造: 60 分钟
- S2.4 baseline 回归: 30 分钟
- S2.5 commit + push + 自检: 15 分钟
- **S2 合计: ~3.5 小时**

S3 36 链填实 wave A-H 估 ~6 小时(每 wave 30-50 分钟)。
S4 全栈 + 加链验收 估 ~1 小时。
**总剩余: ~10.5 小时**,在 8 小时窗口内可能不够,但用户已说"跑到完成为止" — 不卡 8 小时。
