# 28 链 Plugin 重构 — 战略目标与硬约束

> **此文件是 chain-as-plugin 重构的"锚",每个 cron tick / compaction / 新 session 必须先读此文件再继续。**
> **目的:防止战略目标在长任务中漂移,违反任一硬约束 = 重构失败,必须回滚。**

---

## 1. 战略目标(锁死,不可漂移)

让**交易所业务方加一条新链 = 只丢 1 个 JSON 配置文件**,不碰任何代码。

- 当前痛点:加新链需改 `config_loader.sh` 880 行 shell 的 3 处 + `tools/fetch_active_accounts.py` 工厂函数硬 dispatch + 测试 fixture
- 重构后:`config/chains/<chain>.json` 一个文件搞定;若新链协议族已有 adapter,**零代码**;若是全新族,**业务方提 PR 加 1 个 adapter 文件**

---

## 2. 覆盖范围(28 条公链)

详见 `00-SUMMARY.md`,本文件只列分类:

| 类别 | 数量 | 说明 |
|---|---|---|
| 8 已有链 | 8 | Solana / Ethereum / BSC / Base / Polygon / Scroll / Starknet / Sui — 回归保护 |
| 15 新核心 adapter 链 | 15 | 每条需新 adapter 模块 |
| 4 Bitcoin 复用链 | 4 | Zcash / LTC / DOGE / BCH — 复用 BitcoinAdapter |
| 1 Tron 双 API | (含在 15 内) | 必须同时支持 `/jsonrpc` 和 `/wallet/*` |

---

## 3. 硬约束(违反则重构失败)

| # | 约束 | 验证手段 |
|---|---|---|
| H1 | 8 已有链 e2e_smoke matrix 100% PASS,不破任何现有测试 | `python3 -m unittest tests.X -v` + e2e_smoke 8/8 |
| H2 | adapter 也必须插件化,`importlib` 动态加载,不可硬 dispatch | grep 验证无 `if chain == "X"` 写死分发 |
| H3 | Tron 必须双 API(JSON-RPC + 原生 `/wallet/*`),支持 TRC20 | curl 实测 USDT-TRC20 balance |
| H4 | 跨云对等不破(AWS/GCP 都能跑全 28 链) | 跨云对照测试 |
| H5 | 不新引 PyPI 包,如必须则同步更新 `requirements.txt` + `install_deps.sh` | git diff 检查 |
| H6 | 真名铁律:`LEDGER_DEVICE`(默认 nvme1n1)+ `ACCOUNTS_DEVICE`(默认 nvme2n1)语义不变 | grep 验证 |
| H7 | 文档双语对齐(`docs/zh/chains/` ↔ `docs/en/chains/` 一一对应) | 文件名+目录结构 mirror |
| H8 | 每条链的调研 md 必须含**真实证据**(curl 实测输出 + 官方文档 URL + 访问日期) | review 抽查 |
| H9 | fixture "各池独立最近 N 块"原则保留 | 不可改 fixture 共享逻辑 |
| H10 | 业务方加新链 = JSON only(同族 adapter 已存在时) | 验收:新加 1 个 EVM 链全程 0 行 Python |

---

## 4. 文档规范

### 4.1 双语对齐

- `docs/zh/chains/01-solana.md` ↔ `docs/en/chains/01-solana.md`
- 内容**对应**,中文版可有更详细的本地化说明,但**章节标题、表格结构必须一致**
- 文件编号 01-28 按 `00-SUMMARY.md` 链顺序

### 4.2 调研模板

详见 `_template.md`,10 段固定结构:

1. Sources(官方文档 URL + 访问日期)
2. Protocol Family(协议族 / 共识 / 账户模型)
3. Public RPC(公共 endpoint + auth + rate limit)
4. Account Model(账户模型 / UTXO vs Account)
5. Core RPC Methods(本框架监控所需的 method 列表)
6. Address Format(地址格式 / checksum / 长度)
7. Signature Lookup(签名/交易哈希格式)
8. Mixed Set(`mixed` mode 测试权重建议)
9. Mock Notes(mock_rpc_server 实现要点)
10. Adapter Reuse Decision(adapter 复用决策 + 理由)

### 4.3 真实证据要求

每条链必须含:
- ✅ 至少 1 个 `curl ... | jq` 实测输出
- ✅ 官方文档 URL + 访问日期(YYYY-MM-DD)
- ✅ 主网真实数据(block height / tx hash / address)
- ❌ 不可凭印象写 schema/method,**调研先行(R20.7)**

---

## 5. 28 链 Checklist(完成一条打 ✅)

### 8 已有链(Phase 1.1)
- [ ] 01-solana
- [ ] 02-ethereum
- [ ] 03-bsc
- [ ] 04-base
- [ ] 05-polygon
- [ ] 06-scroll
- [ ] 07-starknet
- [ ] 08-sui

### 15 新核心 adapter 链(Phase 1.2)
- [ ] 09-bitcoin
- [ ] 10-ton
- [ ] 11-cardano
- [ ] 12-tron(双 API)
- [ ] 13-cosmos
- [ ] 14-avalanche-p-x(非 C 链)
- [ ] 15-near
- [ ] 16-polkadot
- [ ] 17-aptos
- [ ] 18-xrp
- [ ] 19-stellar
- [ ] 20-algorand
- [ ] 21-hedera
- [ ] 22-filecoin
- [ ] 23-icp
- [ ] 24-monero

### 4 Bitcoin 复用链(Phase 1.3)
- [ ] 25-zcash
- [ ] 26-litecoin
- [ ] 27-dogecoin
- [ ] 28-bitcoin-cash

---

## 6. 失败回滚

任何硬约束 H1-H10 违反 → 该 Phase 必须**完整回滚**(`git reset --hard`),不可"先继续后修"。

参考 skill:`no-deferred-bugs` + memory 第 6 项铁律。

---

**最后更新**:2026-05-23 by Hermes Agent
**对应 v 标签**:v1.4.7
**baseline commit**:`b2c0ccc`
