# 02 — Ethereum 调研稿

> **版本**:v1.0(初稿,Phase 1.1a)
> **调研日期**:2026-05-23
> **作者**:Hermes Agent(基于 token-level + 调研先行 + E1 实证)
> **状态**:🟢 待 user review(P1-USER-REVIEW 卡点)

---

## §1 基本信息

| 项 | 值 | 信源(E1) |
|---|---|---|
| 链族 | EVM(Ethereum Virtual Machine) | 官方 https://ethereum.org/developers/docs/apis/json-rpc/(E1 访问 2026-05-23) |
| 共识 | PoS(2022 Merge 后) | 官方文档 |
| 客户端代表 | Geth / Nethermind / Besu / Erigon / Reth | 官方 client list |
| Mainnet RPC URL | `https://ethereum-rpc.publicnode.com`(无需 API key 公共节点) | 用户偏好;框架 `config_loader.sh:375-377`(待 grep 验) |
| 框架已支持 | ✅(`fetch_active_accounts.py:287-461` EthereumAdapter) | E1 read_file 确认 |
| 是否本族唯一代表 | ❌(BSC/Base/Polygon/Scroll/Arbitrum 等大量 EVM 兼容链共用) | 框架内已确认 BSC/Base/Polygon/Scroll 全部用同一 EthereumAdapter |

---

## §2 地址格式 / 解析规则

| 项 | 值 | E1 信源 |
|---|---|---|
| 地址长度 | 20 字节(40 hex char + `0x` 前缀 = 42 char) | EIP-55 |
| 字符集 | `0x` + `[0-9a-fA-F]{40}` | 标准 |
| 校验和 | EIP-55 mixed-case checksum(可选,大部分客户端接受 lowercase) | EIP-55 |
| 框架 system_addresses | `0x0000000000000000000000000000000000000000`、`0x000000000000000000000000000000000000dead` | `config_loader.sh:455-458`(E1 read_file 确认) |
| 框架 target_address(USDT 合约) | `0xdAC17F958D2ee523a2206206994597C13D831ec7` | `config_loader.sh:446` |
| 合约 vs EOA 判别 | `eth_getCode(addr, "latest") != "0x"` → 合约,否则 EOA | EthereumAdapter `_is_contract_address` L300-307 |

**与 Solana 差异**:Solana 地址是 base58 编码 32 字节(~44 字符),Ethereum 是 hex 编码 20 字节(42 字符)— 长度短一半。

---

## §3 RPC method 现行状态(每条 E1 实证)

### 框架 EthereumAdapter 实际调用的 method 清单

| Method | 用途 | 框架调用点(E1) | 官方 spec 状态(E1) |
|---|---|---|---|
| `eth_getCode` | 合约地址判别 | `fetch_active_accounts.py:304` | ✅ 现行(execution-apis spec) |
| `eth_blockNumber` | 取最新 block | `fetch_active_accounts.py:312, 346` + `config_loader.sh:461 mixed` | ✅ 现行 |
| `eth_getLogs` | 合约 log 抓取 | `fetch_active_accounts.py:332` + `config_loader.sh:452 methods.get_logs` | ✅ 现行 |
| `eth_getBlockByNumber` | EOA tx 抓取(逐块扫) | `fetch_active_accounts.py:378` | ✅ 现行 |
| `eth_getTransactionByHash` | tx 详情 | `fetch_active_accounts.py:404` + `config_loader.sh:453 methods.get_transaction` | ✅ 现行 |
| `eth_getBalance` | 余额查询(mixed 模式) | `config_loader.sh:460-461` `single` + `mixed` | ✅ 现行 |
| `eth_getTransactionCount` | nonce/tx 计数(mixed 模式) | `config_loader.sh:461` `mixed` | ✅ 现行 |
| `eth_gasPrice` | gas 价格(mixed 模式) | `config_loader.sh:461` `mixed` | ✅ 现行 |

**全部 8 个 method 在 Ethereum Execution APIs spec(https://ethereum.github.io/execution-apis/)现行 method 列表中均存在**(E1: browser_console DOM 提取 61 个 method 名,含全部 8 个)。

### 与 Solana 对比 — 关键差异

| 维度 | Solana | Ethereum |
|---|---|---|
| mixed 模式 method 数 | 5 个 | **4 个**(少 1 个) |
| 废弃 method 残留 | ❌ `getRecentBlockhash` 已废弃但未清理(P0 bug) | ✅ **无 deprecated method 残留** |
| API spec 权威源 | https://solana.com/docs/rpc | https://ethereum.github.io/execution-apis/ |
| RPC 协议版本 | JSON-RPC 2.0(自定义 method 名空间) | JSON-RPC 2.0(`eth_` namespace + `net_` + `web3_`) |

**结论**:Ethereum 段无 deprecation 问题,**与 Solana 完全相反**。

---

## §4 system addresses(应过滤)

| 地址 | 含义 | E1 信源 |
|---|---|---|
| `0x0000000000000000000000000000000000000000` | Zero address(铸币/销毁惯例 from 字段) | `config_loader.sh:456` |
| `0x000000000000000000000000000000000000dead` | Dead address(惯例销毁地址) | `config_loader.sh:457` |

**问题**:框架只列 2 个 system address,**但实际 Ethereum 生态还有大量惯例过滤地址应考虑**:
- USDT/USDC/WETH 等合约自身地址(交易频次极高,可能扭曲 active accounts 统计)
- Beacon Deposit Contract(`0x00000000219ab540356cBB839Cbe05303d7705Fa`)
- WETH(`0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2`)

**Open Question(待 user review 决定)**:framework 是否应内置更大白名单?Phase 2.x 设计 plugin 时讨论。

---

## §5 mixed 模式权重(若启用)

**框架当前实现**:无 mixed 权重 — `mixed` 字段是逗号分隔字符串,被 target_generator 等权循环:

```
config_loader.sh:461 → "eth_getBalance,eth_getTransactionCount,eth_blockNumber,eth_gasPrice"
                                    ↓ split by ','
CURRENT_RPC_METHODS_ARRAY = [eth_getBalance, eth_getTransactionCount, eth_blockNumber, eth_gasPrice]
                                    ↓ target_generator.sh:184/300-306 等权循环
vegeta targets file
```

**建议(Phase 2.x plugin 设计阶段)**:与 Solana 同步引入 weighted mixed schema,Ethereum 实际生产负载预估:
- `eth_getBalance`: 0.30(余额查询最高频)
- `eth_getTransactionCount`: 0.20(nonce 查询)
- `eth_blockNumber`: 0.30(高频心跳)
- `eth_gasPrice`: 0.10(交易前查询)
- `eth_call`: 0.10(合约只读,**框架当前未配,应加**)

总和 = 1.00 ✅

**注**:权重数字为初稿建议(E5 SPECULATED),未基于真实 mainnet 流量统计,需 Phase 2.x 与交易所对齐。

---

## §6 框架内 Ethereum 调用链(已 E1 实证)

```
[启动] BLOCKCHAIN_NODE=ethereum
   ↓
[config_loader.sh:660] validate_blockchain_node → 通过(ethereum 在 supported list)
   ↓
[config_loader.sh:381-383] case ethereum → MAINNET_RPC_URL=https://mainnet.publicnode.com(或类似)
   ↓
[config_loader.sh:440-468] UNIFIED_BLOCKCHAIN_CONFIG.blockchains.ethereum
   - methods.get_logs = "eth_getLogs"
   - methods.get_transaction = "eth_getTransactionByHash"
   - rpc_methods.single = "eth_getBalance"
   - rpc_methods.mixed = "eth_getBalance,eth_getTransactionCount,eth_blockNumber,eth_gasPrice"
   ↓
[fetch_active_accounts.py:287-461] EthereumAdapter
   - _single_request → _is_contract_address(eth_getCode)
                      → 合约: _fetch_contract_logs_fixed(eth_blockNumber, eth_getLogs)
                      → EOA:  _fetch_eoa_transactions_simple(eth_blockNumber, eth_getBlockByNumber 逐块扫)
   - fetch_transaction → eth_getTransactionByHash
   - extract_accounts_from_transaction → 从 tx.from / tx.to 取地址
   ↓
[target_generator.sh:184/300-306] 读 CURRENT_RPC_METHODS_ARRAY 循环
   ↓
[vegeta targets file] → vegeta 真发 mainnet 节点
```

**与 Solana 调用链对比**:
- Solana 是 **统一 `getSignaturesForAddress` + `getTransaction`**,无合约/EOA 区分
- Ethereum **必须区分合约/EOA**,合约走 `eth_getLogs`,EOA 走逐块扫 `eth_getBlockByNumber`(性能开销大)
- EthereumAdapter 多出 `_fetch_block_transactions` 辅助方法,**是 EOA 模式 RPC 调用最密集的点**

---

## §7 chain-specific 调优(框架内已实现)

`fetch_active_accounts.py:316-321` 按 `chain_type` 调 block_range:

| chain_type | block_range | 原因 |
|---|---|---|
| `bsc` | 50 | BSC node 限制更严(单次 eth_getLogs 区间上限较小) |
| `ethereum` | 100 | 中等 |
| 其他(base/polygon/scroll) | 200 | 宽松 |

**Open Question**:这套阈值是否经过真实测试?是凭经验拍的还是 mainnet RPC 限流测出的?(无 E1 证据 → E5 SPECULATED)

---

## §8 Phase 2.1 实施改造点 / Caller-Reader 影响清单

**调研先行铁律 — 这一节强制存在(参 token-level-careful-edit Case-K)**

| # | 改造点 | 待改内容 | Caller/Reader 影响 |
|---|---|---|---|
| 1 | `config/config_loader.sh:440-468` Ethereum 段拆出到 `config/chains/ethereum.json` | 保留 `chain_type / params / methods / system_addresses / rpc_methods / param_formats` schema | `generate_auto_config()` L704+ 必须改为 importlib-like 动态加载 JSON,**不能硬编码** |
| 2 | `fetch_active_accounts.py:287-461` EthereumAdapter 拆出到 `adapters/ethereum.py` | 类签名保持 `class EthereumAdapter(BlockchainAdapter)` 不变 | 拆出时**不能改方法名**(`_single_request / fetch_transaction / extract_accounts_from_transaction` + 私有 `_is_contract_address / _fetch_contract_logs_fixed / _fetch_eoa_transactions_simple / _fetch_block_transactions`)|
| 3 | `chain_type` 字段必须保留向后兼容 | EthereumAdapter L316-321 用 `self.chain_type.lower() == "bsc" / "ethereum"` 做 block_range 分支 | BSC/Polygon/Base/Scroll 4 链复用同一 adapter,**chain_type 字段是 hot-path 关键 dispatch key**,改名会破 4 链全跑 |
| 4 | `config_loader.sh:660` validate_blockchain_node hardcoded list 必须迁移 | `local supported_blockchains=("solana" "ethereum" "bsc" "base" "scroll" "polygon" "starknet" "sui")` | Phase 2.0 设计阶段决定:plugin 自描述能力(扫 `config/chains/*.json` 自动 enumerate)vs 中央 manifest |
| 5 | mixed 模式权重 schema(若引入)| 引入 `mixed_weights` JSON 字段 | target_generator.sh:184/300-306 需新增权重采样逻辑(当前是等权 round-robin)|

**§8.5 Phase 2.1 caller/reader 表(token-level Gate 3)**

| 改造点 | Caller(谁调用此函数/读此数据) | Reader(谁消费此输出) | 改完是否 OK |
|---|---|---|---|
| 拆出 ethereum.json | `generate_auto_config()` `config_loader.sh:704+` | `target_generator.sh:184` 读 `CURRENT_RPC_METHODS_ARRAY` | **需同步改**(动态加载) |
| 拆出 EthereumAdapter | `fetch_active_accounts.py main` 调度 adapter 实例化 | adapter 输出 active accounts 列表给 `target_generator.sh` | **可一对一拆出**(类签名不变) |
| chain_type 保留 | EthereumAdapter L316-321 `if chain_type == "bsc"` | BSC/Polygon/Base/Scroll 4 链共用 | **不可改名** |

---

## §9 真实信源覆盖与时间戳

| 信源类型 | URL/路径 | 访问日期(UTC) | 状态 |
|---|---|---|---|
| 官方 Spec | https://ethereum.github.io/execution-apis/ | 2026-05-23 | E1 ✅ DOM 提取 61 个 method 含全部 8 个 |
| 官方文档入口 | https://ethereum.org/developers/docs/apis/json-rpc/ | 2026-05-23 | E1 ✅ 已访问 |
| 框架代码 | `fetch_active_accounts.py:287-461`、`config_loader.sh:440-468` | 2026-05-23 | E1 ✅ read_file 实证 |
| 实测 publicnode | (待 Phase 2.x 实施时跑 curl) | — | E5 待实测 |

---

## §10 接口契约 placeholder(Phase 2.x 完工时填)

```python
class EthereumAdapter(BlockchainAdapter):
    """Ethereum + EVM 兼容链 adapter(BSC/Base/Polygon/Scroll 复用)"""

    chain_type: str  # "ethereum" / "bsc" / "base" / "polygon" / "scroll" — hot path dispatch key

    async def _single_request(self, address: str, limit: int, verbose: bool) -> list[dict]:
        """统一入口,合约/EOA 分支"""

    async def _is_contract_address(self, address: str) -> bool:
        """eth_getCode(addr, latest) != '0x'"""

    async def _fetch_contract_logs_fixed(self, address: str, limit: int, verbose: bool) -> list[dict]:
        """eth_blockNumber + eth_getLogs(按 chain_type 调 block_range)"""

    async def _fetch_eoa_transactions_simple(self, address: str, limit: int, verbose: bool) -> list[dict]:
        """eth_blockNumber + 逐块 eth_getBlockByNumber 扫"""

    async def _fetch_block_transactions(self, block_num: int, target_address: str, remaining_limit: int) -> list[dict]:
        """单 block 扫 tx,匹配 from/to == target"""

    async def fetch_transaction(self, tx_hash: str) -> dict | None:
        """eth_getTransactionByHash"""

    def extract_accounts_from_transaction(self, tx_data: dict, target_address: str) -> set[str]:
        """从 tx.from / tx.to 提取地址(Solana 是从 accountKeys)"""
```

**注**:行号区间 L287-461 是当前 baseline(`b2c0ccc`)实际位置,Phase 2.1 拆出后此 placeholder 应更新为 `adapters/ethereum.py:1-N`。

---

## §11 Open Questions(待 user review 决定)

1. **mixed 权重**:Phase 2.x 是否引入加权 mixed?(Solana 同问)
2. **system_addresses 扩展**:Ethereum 是否应内置 WETH/USDT/USDC/Beacon Deposit 等高频合约白名单?
3. **block_range 阈值**:`bsc=50 / ethereum=100 / others=200` 是否经实测验证?Phase 2.x 是否做 mainnet RPC 限流测?
4. **chain_type 是否应保留**:Phase 2.x plugin 自描述时,`chain_type` 字段是否还有必要?或改为 plugin metadata 的 `family: "evm"` + `subfamily: "ethereum"`?
5. **EOA 逐块扫的成本问题**:`_fetch_eoa_transactions_simple` 在大 limit 下会触发数百次 `eth_getBlockByNumber`,**实际 mainnet 跑是否会被 publicnode 限流?**框架是否需做并发 throttle?

---

## §12 Changelog

| 日期(UTC) | 作者 | 变更 |
|---|---|---|
| 2026-05-23 | Hermes Agent | 初稿,基于 token-level + 调研先行 + E1 实证(Ethereum Execution APIs spec + 框架代码) |
