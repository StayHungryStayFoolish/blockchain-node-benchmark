# 从现有代码迁移到新架构 (Migration Plan, Stage 1-C)

**版本**:阶段 1-C 草稿
**关联**:[per-method-proxy-architecture-zh.md](./per-method-proxy-architecture-zh.md)(1-A) + [chain-template-zero-code-spec-zh.md](./chain-template-zero-code-spec-zh.md)(1-B) + [NORTH-STAR.md](../NORTH-STAR.md)
**baseline**:`15441ad` (Stage 1-3: Y+ NIC abstraction layer)
**head**:`7921b71` (main)
**适用范围**:阶段 4 PoC(solana 1 链 a+b 全闭环)→ 阶段 5(36 链全覆盖)

---

## 0. 北极星回顾(迁移要解决什么)

NS-1 = **支持 36 链(零代码加链)**
NS-2 = **mixed RPC method 权重 + per-method 资源归因 + method 级图表 + 双语 HTML 报告**
NS-3 = **零代码加链原则覆盖 adapter + proxy 协议解析层**

当前现状(实测 main `7921b71`)与北极星的 4 道差距:

| 差距 | 当前现状 | 北极星目标 | 违反 NS- |
|---|---|---|---|
| G1 | `fetch_active_accounts.py` 3+1 if/elif 硬编码 8 链(`create_adapter()` L665-678 + `fetch_all_signatures()` L684 嵌套) | 通过 adapter 接口 dispatch,加链 0 Python | NS-1 + NS-3 |
| G2 | `config_loader.sh` L371-405 `case` 硬编码 8 链 RPC URL(solana / ethereum / bsc / base / polygon / scroll / starknet / sui) | 从 `_meta.rpc_url_dev` 字段读 | NS-1 + NS-3 |
| G3 | 无 per-method proxy 层,vegeta 直接打节点,无法做 method 级 CPU/MEM 归因 | proxy 拦截 + method 级 trace + monitor 双向对齐 | NS-2 |
| G4 | `test_chain_adapters.py L404` `assert len(KNOWN_BROKEN_CLI) == 24` magic number | 动态从 `_meta.known_broken_mixed` 字段算 | NS-1(测试侧硬编码) |

本文档描述 **阶段 4 PoC**(solana 1 链)和 **阶段 5**(36 链 rollout)如何在不破坏 12 healthy 链现状的前提下,用 **Strangler Fig 模式**逐步消除上述 4 道差距。

---

## 1. 迁移原则(R0 零号规则)

**老测保护(R0 v1.4.4)**:任何阶段的任何 PR,**12 healthy 链 L1 全过**是合并红线;退化任一即回滚。

**Strangler Fig 模式**:每个差距分 3 步走 ——

1. **建新**:新接口/新字段/新组件就位,与旧路径**并存**(不删旧)
2. **切流量**:配置开关 `USE_NEW=true` 把新链/新 method 切到新路径(老链继续走旧路径)
3. **拆旧**:CI hook 验证旧路径 0 引用(`ci/check_parallel_entry.sh` 模式),然后物理删除

**parallel-entry-trap 防线**(v1.4.5 hook 已就位,见 `ci/check_parallel_entry.sh`):新文件必须在主流程**至少出现一次**作为 source/import;否则 CI 拒并。

---

## 2. 阶段 4 PoC 范围与不变式

### 2.1 范围(solana 1 链 a+b 全闭环)

**a 部分:消除 G1(fetcher 硬编码)**

1. `tools/chain_adapters/base.py`:加第 4 个 @abstractmethod `fetch_active_addresses(self, count: int, rpc_url: str) -> list[str]`
2. `tools/chain_adapters/jsonrpc.py` Solana 子类实现 `fetch_active_addresses()`(把 `SolanaAdapter._fetch_signatures` 迁过来)
3. `tools/fetch_active_accounts.py`:
   - **第 1 处**:`create_adapter()` L665 → 改为 `from tools.chain_adapters import get_adapter; return get_adapter(chain_type)`(读 `_meta.adapter_family` 自动 dispatch)
   - **第 2 处**:`fetch_all_signatures()` L684 嵌套 `if adapter.chain_type == "solana"` → 改为调用 `adapter.fetch_active_addresses()`(若 adapter 不支持,raise NotImplementedError 走 fallback)
4. **不删** 旧 `SolanaAdapter` / `EthereumAdapter` 等具体类,只是不再被 fetcher 直接 import。`get_adapter()` 仍能 instantiate 它们(因为 `_REGISTRY` 已注册)。

**b 部分:per-method proxy POC**(具体设计见 1-A)

- 新增 `proxy/` 目录:1 个 forward proxy(http/sgrpc/grpc/ws 协议解析层,**封闭枚举**对应 7 adapter family)
- 把 solana 一条 mixed workload 走 vegeta → proxy → 节点
- monitor 侧加 method 级 trace 对齐(时间窗 + correlation_id 双重)
- 输出 method 级 CPU/MEM 图(PNG)到双语 HTML 报告

### 2.2 PoC 8 条硬验收(对齐 1-B §6.4)

| # | 验收条件 | 实证方法 |
|---|---|---|
| 1 | `config/chains/solana.json` 通过 `validate_chain_template.py`(阶段 4 新建) | exit=0 + stdout PASS |
| 2 | Solana adapter 实现 `fetch_active_addresses()` | `grep "def fetch_active_addresses" tools/chain_adapters/jsonrpc.py` |
| 3 | `tools/fetch_active_accounts.py` **两处** `if chain_type == "solana"` 全消除 | `grep -c "chain_type == \"solana\"" tools/fetch_active_accounts.py` = 0(只准 Changelog 提及) |
| 4 | 加 mock 第 37 链 `dummy.json`(jsonrpc 族),`fetch_active_accounts.py --chain dummy` 不报错 | exit=0 + 真返地址 list |
| 5 | 加 dummy.json 时 `git diff --stat` **0 行 .py / .sh 改动** | `git diff --stat HEAD~1 -- '*.py' '*.sh' | wc -l` = 0 |
| 6 | 12 healthy 链 L1 全过(R0 v1.4.4 红线) | `python3 tests/test_chain_adapters.py` PASS |
| 7 | proxy 收 1 条 mixed workload,method 级 CPU 图 PNG 生成,引到双语 HTML | 真 PNG 文件存在 + HTML `<img>` 标签 src 指向 PNG |
| 8 | proxy 故障时(kill 进程)benchmark 主流程不卡死,降级到 direct-to-node | kill proxy + 跑 benchmark + exit=0 |

**任一 ❌**:阶段 4 失败,**触发阶段 5 启动撤销**(见 1-B §6.4 #5)。

### 2.3 不变式(阶段 4 期间)

| ID | 不变式 | 验证 |
|---|---|---|
| INV-1 | 12 healthy 链 L1 全过 | 每次 commit 跑 `tests/test_chain_adapters.py` |
| INV-2 | `KNOWN_BROKEN_CLI` 集合**只缩不增**(R0 v1.4.4) | `tests/test_chain_adapters.py` L343-348 注释 + L404 `assert len(KNOWN_BROKEN_CLI) == 24` + L486-572 `unexpected_new_broken` / `unexpectedly_healthy` 双向门 |
| INV-3 | `_REGISTRY` 7 族不变(不准 PoC 期间增 family) | `python3 -c "from tools.chain_adapters import list_adapters; assert list_adapters() == ['bitcoin_jsonrpc','hedera_dual','jsonrpc','ogmios','rest','substrate','tendermint']"` |
| INV-4 | `ci/check_parallel_entry.sh` 0 violation | 每次 commit 自动跑(pre-commit hook v1.4.5) |
| INV-5 | adapter 接口 3 → 4 abstract,但 base.py 提供 default `fetch_active_addresses` 返回 `[]` 或 raise NotImplementedError(老 adapter 不强制实现) | `grep "@abstractmethod" tools/chain_adapters/base.py` |

---

## 3. 阶段 5 rollout 计划(36 链全覆盖)

### 3.1 Wave 切分(按 adapter family 分批)

PoC PASS 后,按 family 分波,每波**独立 PR + 独立 L3 验**:

| Wave | family | 链数 | 优先级 | 风险 |
|---|---|---|---|---|
| W1 | jsonrpc | 16 | P0(覆盖最大) | 低(已有 SolanaAdapter / EthereumAdapter 经验) |
| W2 | substrate | 5 | P1 | 中(协议特殊,L1 PASS 但 L3 全未跑) |
| W3 | tendermint | 5 | P1 | 中(同 W2) |
| W4 | rest | 4 | P2 | 中(tezos `operations` MULTI_PLACEHOLDER 待处理,1-B §1.5 path_addr) |
| W5 | bitcoin_jsonrpc | 4 | P2 | 中(认证差异,litecoin 等) |
| W6 | ogmios | 1 | P3(cardano L3 待跑) | 高(协议唯一,实测样本 0) |
| W7 | hedera_dual | 1 | P3 | 高(双协议,1-B §6.4 双 curl 验证已上 ledger) |

**每波 PR 要求**:
1. 该 family 所有链 `_meta.rpc_url_dev` 字段填入(消除 G2 `config_loader.sh` case)
2. 该 family adapter 实现 `fetch_active_addresses()`(若 12 healthy 中含此 family)
3. L1 / L2 / L3 全过(R0 v1.4.4)
4. `KNOWN_BROKEN_CLI` 数字相应缩小(不准增)
5. 若某链 L3 红 → 入 `_meta.known_broken_mixed`,**不阻塞**其他链合并

### 3.2 G4 测试侧硬编码消除

`tests/test_chain_adapters.py` L404 `assert len(KNOWN_BROKEN_CLI) == 24` 是 magic number。阶段 5 末:

```python
# 改为从 _meta 动态算
expected_broken = sum(
    1 for f in glob("config/chains/*.json")
    if json.load(open(f)).get("_meta", {}).get("known_broken_mixed", {}).get("status") in ("BROKEN", "PENDING")
)
assert len(KNOWN_BROKEN_CLI) == expected_broken
```

这样**任何 chain template 改 `known_broken_mixed` 字段,测试自动跟进**,无需手改 magic number。

### 3.3 G2 `config_loader.sh` case 拆除

PoC 期间不动(R0 风险)。阶段 5 W7 完成后:

```bash
# 当前 (L371-405)
case "${BLOCKCHAIN_NODE,,}" in
    solana) MAINNET_RPC_URL="https://api.mainnet-beta.solana.com" ;;
    # ... 8 链 ...
esac

# 改为
MAINNET_RPC_URL=$(python3 -c "
import json
tpl = json.load(open(f'config/chains/${BLOCKCHAIN_NODE,,}.json'))
print(tpl.get('_meta', {}).get('rpc_url_dev', ''))
")
[[ -z "$MAINNET_RPC_URL" ]] && { echo "❌ no rpc_url_dev for ${BLOCKCHAIN_NODE}"; exit 1; }
```

**前置条件**:36 chain template 的 `_meta.rpc_url_dev` 字段全填(用现有 case 数据 + 公开 RPC 调研填齐 28 漏链)。

### 3.4 Wave 节奏

- 不抢节奏:每波 1 个 PR,L3 全过才进下一波
- 任何 wave 退化 12 healthy → 立即 revert + 触发**阶段 5 撤销**(1-B §6.4 #5)
- 32 chain → 36 chain 调研 md 不在阶段 5 范围(那是 P1-2 持续输出,阶段 5 只动 schema + adapter)

---

## 4. 风险与回滚

### 4.1 主要风险

| 风险 | 触发条件 | 缓解 |
|---|---|---|
| R-1 PoC G1 改 fetcher 误伤 12 healthy | `tests/test_chain_adapters.py` 红 | 立刻 revert,**不准 cherry-pick 部分**(全有或全无) |
| R-2 proxy 引入新协议解析 bug | mixed workload 数据丢/重复/乱序 | proxy 出 trace 必跟 vegeta + monitor 对齐(三方对齐验证) |
| R-3 G2 拆 case 后某链 `_meta.rpc_url_dev` 字段缺失 → benchmark 失败 | `config_loader.sh` exit 1 | 前置 pre-commit hook 校验所有 chain JSON 有 `rpc_url_dev` 字段 |
| R-4 36 chain `known_broken_mixed` 字段格式漂移 → G4 测试侧改坏 | `test_chain_adapters.py` assert 红 | `_meta.known_broken_mixed` schema 锁死(`{status, evidence_date, live_http_test}`,1-B §1.6 已规定) |
| R-5 ogmios/hedera_dual 唯链 wave 实证不足 → 阶段 5 末段重做 | W6/W7 L3 红 | wave 顺序按风险倒序排:高风险孤族先做 PoC,失败成本最低 |

### 4.2 回滚策略

| 阶段 | 回滚方法 |
|---|---|
| 阶段 4 PoC 失败 | `git revert <PoC merge SHA>`,触发**阶段 5 撤销**(1-B §6.4 #5);返回 1-A/1-B 设计修订 |
| 阶段 5 Wn 失败 | `git revert <Wn SHA>`,该 family 标记 P2 推后,其余 wave 继续 |
| G2 拆 case 后某链回退 | 临时 `_meta.rpc_url_dev` 设回 case 中的旧 URL;不准回退到 case 硬编码方案 |

### 4.3 撤销条件(继承 1-B §6.4 #5)

**阶段 4 PoC 8 条硬验收任一 ❌ → 阶段 5 不准启动**。已合并的 PoC 代码 revert 回 main `7921b71`(本文档 baseline)。

---

## 5. 时间预估(speculative,E5)

**E5 SPECULATED — 无历史数据,凭直觉,实际可能 ±2x**:

| 阶段 | 任务 | 预估工时 |
|---|---|---|
| 阶段 4 PoC a 部分(G1) | adapter 接口加 + fetcher 改 + dummy.json 验 | 3-5h |
| 阶段 4 PoC b 部分(proxy POC) | proxy + method trace + report 引用 | 6-10h |
| 阶段 4 PoC 8 条验收 | 跑 + 修 + commit | 2-3h |
| 阶段 5 W1(jsonrpc 16 链) | rpc_url_dev 填 + L3 全跑 | 4-6h |
| 阶段 5 W2-W7(20 链 + 5 wave) | 每 wave 2-3h | 12-18h |
| 阶段 5 G2 + G4 拆除 | case → JSON dispatch + magic number → 动态 | 2-3h |
| **总计** | | **29-45h** |

时间预估**仅供 cronjob repeat 次数估算**,不作硬截止。

---

## 6. 与 1-A / 1-B 的交叉引用

| 本文档章节 | 关联 |
|---|---|
| §0 G1-G4 差距 | 1-B §0(NS-3 反例) + 1-B §6.1(违规清单) |
| §1 Strangler Fig | 1-B §6.4 #5(阶段 5 启动撤销) |
| §2.1 a 部分 | 1-B §2.2(新增第 4 个 @abstractmethod `fetch_active_addresses`) |
| §2.1 b 部分 | 1-A 全文(per-method proxy 架构) |
| §2.2 8 条验收 | 1-B §6.4(防止技术债的硬约束 5 条) |
| §2.3 INV-3 7 族 | 1-B §2.1(实测 7 族 + 36 链分布) |
| §3.1 Wave 切分 | 1-B §2.3(7 族实现状态) |

---

## 7. 范围外(本文档不覆盖)

1. **32 → 36 链调研稿持续输出**(P1-2 持续阶段,与阶段 4-5 并行,不互相阻塞)
2. **proxy 实现细节**(协议解析层 / sidecar vs gateway / 服务发现等) → 1-A 范围
3. **monitor / report 引擎重写** → 非本阶段,沿用现有(若 method 级图集成 ROI 低则推迟到 stage 6)
4. **K8s / cgroup 集成层 v1.4.4 修复** → 已 land 7921b71,不在迁移路径
5. **fetcher 28 漏链补支持**(非 solana/eth/bsc/base/scroll/polygon/starknet/sui) → 阶段 5 W2-W7 顺带做(随该 family adapter 实现 `fetch_active_addresses`)

---

## 8. ADR 记录(本迁移引入的不可逆决策)

| ADR | 决策 | 理由 |
|---|---|---|
| ADR-1C-1 | 阶段 4 PoC 必选 solana 链(不可换 ethereum) | solana 是 fetcher 硬编码主体(L665 单独分支);改 solana 验证 dispatch 正确性最强 |
| ADR-1C-2 | adapter 接口扩到 4 abstract(加 `fetch_active_addresses`),但 base.py 提供 default 实现 | 不强制 24 known-broken 链 adapter 实现新方法,避免推 G1 时连带破坏 INV-2 |
| ADR-1C-3 | G2 拆 `config_loader.sh` case **晚于** G1(W7 之后) | case 是 RPC URL 硬编码,失败模式 = benchmark 无法启动(影响面大);G1 是 fetcher 硬编码,失败模式 = 某链 fetcher 报错(影响面小,可定位)。先低风险后高风险 |
| ADR-1C-4 | 36 链 `_meta.rpc_url_dev` 字段填齐 = 阶段 5 G2 前置条件,不准跳过 | 否则 case 拆除后 fallback 无来源,需要再回 case |
| ADR-1C-5 | 不引入 schema 版本号 / migration tool(JSON v2→v3) | 阶段 6 引入,本阶段 schema **追加字段**(向后兼容),不删字段 |
