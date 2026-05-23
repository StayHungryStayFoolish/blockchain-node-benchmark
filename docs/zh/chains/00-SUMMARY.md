# 28 链汇总 + Adapter 复用矩阵

> **此文件在 Phase 1 结束时完整填写,Phase 1 进行中逐条更新。**
> 当前状态:**🟡 Phase 0 骨架建好,Phase 1 调研待启动**

---

## 1. 28 链列表(按编号顺序)

| # | 链 | 族 | Adapter | 复用/新建 | 调研状态 | 文档 zh | 文档 en |
|---|---|---|---|---|---|---|---|
| 01 | Solana | Solana | SolanaAdapter | 已有 | 🟡 待调研 | — | — |
| 02 | Ethereum | EVM | EthereumAdapter | 已有 | 🟡 待调研 | — | — |
| 03 | BSC | EVM | EthereumAdapter | **复用** | 🟡 待调研 | — | — |
| 04 | Base | EVM | EthereumAdapter | **复用** | 🟡 待调研 | — | — |
| 05 | Polygon | EVM | EthereumAdapter | **复用** | 🟡 待调研 | — | — |
| 06 | Scroll | EVM | EthereumAdapter | **复用** | 🟡 待调研 | — | — |
| 07 | Starknet | Starknet | StarknetAdapter | 已有 | 🟡 待调研 | — | — |
| 08 | Sui | Move | SuiAdapter | 已有 | 🟡 待调研 | — | — |
| 09 | Bitcoin | Bitcoin/UTXO | BitcoinAdapter | **新建** | 🟡 待调研 | — | — |
| 10 | TON | TON | TonAdapter | **新建** | 🟡 待调研 | — | — |
| 11 | Cardano | Cardano/UTXO+ | CardanoAdapter | **新建** | 🟡 待调研 | — | — |
| 12 | Tron | Tron(双 API) | TronAdapter | **新建**(双 API) | 🟡 待调研 | — | — |
| 13 | Cosmos | Cosmos-SDK | CosmosAdapter | **新建** | 🟡 待调研 | — | — |
| 14 | Avalanche P/X | Avalanche | AvalanchePXAdapter | **新建**(非 C 链) | 🟡 待调研 | — | — |
| 15 | NEAR | NEAR | NearAdapter | **新建** | 🟡 待调研 | — | — |
| 16 | Polkadot | Substrate | SubstrateAdapter | **新建** | 🟡 待调研 | — | — |
| 17 | Aptos | Move | AptosAdapter | **新建** | 🟡 待调研 | — | — |
| 18 | XRP | XRPL | XrpAdapter | **新建** | 🟡 待调研 | — | — |
| 19 | Stellar | Stellar | StellarAdapter | **新建** | 🟡 待调研 | — | — |
| 20 | Algorand | Algorand | AlgorandAdapter | **新建** | 🟡 待调研 | — | — |
| 21 | Hedera | Hedera/HBAR | HederaAdapter | **新建** | 🟡 待调研 | — | — |
| 22 | Filecoin | Filecoin | FilecoinAdapter | **新建** | 🟡 待调研 | — | — |
| 23 | ICP | Internet Computer | IcpAdapter | **新建** | 🟡 待调研 | — | — |
| 24 | Monero | CryptoNote | MoneroAdapter | **新建** | 🟡 待调研 | — | — |
| 25 | Zcash | Bitcoin/UTXO | BitcoinAdapter | **复用** | 🟡 待调研 | — | — |
| 26 | Litecoin | Bitcoin/UTXO | BitcoinAdapter | **复用** | 🟡 待调研 | — | — |
| 27 | Dogecoin | Bitcoin/UTXO | BitcoinAdapter | **复用** | 🟡 待调研 | — | — |
| 28 | Bitcoin Cash | Bitcoin/UTXO | BitcoinAdapter | **复用** | 🟡 待调研 | — | — |

**统计**:
- 已有 adapter:4 个(Solana / Ethereum / Starknet / Sui)
- 新增 adapter:15 个(Bitcoin / Ton / Cardano / Tron / Cosmos / AvaxPX / Near / Substrate / Aptos / Xrp / Stellar / Algorand / Hedera / Filecoin / Icp / Monero)
- **adapter 总数 19 个**
- 复用 EthereumAdapter:4 条链(BSC / Base / Polygon / Scroll)
- 复用 BitcoinAdapter:4 条链(Zcash / LTC / DOGE / BCH)
- **链总数 28 条 = 19 个 adapter × N**

---

## 2. Adapter 复用矩阵

| Adapter | 适配链 | 链数 | 实现位置 | 状态 |
|---|---|---|---|---|
| SolanaAdapter | Solana | 1 | `tools/fetch_active_accounts.py:248` → 待迁 | 🟢 已有,需迁出 |
| EthereumAdapter | Ethereum, BSC, Base, Polygon, Scroll | 5 | `tools/fetch_active_accounts.py:287` → 待迁 | 🟢 已有,需迁出 |
| StarknetAdapter | Starknet | 1 | `tools/fetch_active_accounts.py:429` → 待迁 | 🟢 已有,需迁出 |
| SuiAdapter | Sui | 1 | `tools/fetch_active_accounts.py:513` → 待迁 | 🟢 已有,需迁出 |
| BitcoinAdapter | Bitcoin, Zcash, LTC, DOGE, BCH | 5 | `adapters/bitcoin.py`(新建) | 🔴 未建 |
| TonAdapter | TON | 1 | `adapters/ton.py`(新建) | 🔴 未建 |
| CardanoAdapter | Cardano | 1 | `adapters/cardano.py`(新建) | 🔴 未建 |
| TronAdapter(双 API) | Tron | 1 | `adapters/tron.py`(新建,内含 JSON-RPC + 原生分发) | 🔴 未建 |
| CosmosAdapter | Cosmos | 1 | `adapters/cosmos.py`(新建) | 🔴 未建 |
| AvalanchePXAdapter | Avalanche P/X | 1 | `adapters/avalanche_px.py`(新建) | 🔴 未建 |
| NearAdapter | NEAR | 1 | `adapters/near.py`(新建) | 🔴 未建 |
| SubstrateAdapter | Polkadot | 1 | `adapters/substrate.py`(新建) | 🔴 未建 |
| AptosAdapter | Aptos | 1 | `adapters/aptos.py`(新建) | 🔴 未建 |
| XrpAdapter | XRP | 1 | `adapters/xrp.py`(新建) | 🔴 未建 |
| StellarAdapter | Stellar | 1 | `adapters/stellar.py`(新建) | 🔴 未建 |
| AlgorandAdapter | Algorand | 1 | `adapters/algorand.py`(新建) | 🔴 未建 |
| HederaAdapter | Hedera | 1 | `adapters/hedera.py`(新建) | 🔴 未建 |
| FilecoinAdapter | Filecoin | 1 | `adapters/filecoin.py`(新建) | 🔴 未建 |
| IcpAdapter | ICP | 1 | `adapters/icp.py`(新建) | 🔴 未建 |
| MoneroAdapter | Monero | 1 | `adapters/monero.py`(新建) | 🔴 未建 |
| **合计** | **28 链** | **28** | **19 个 adapter** | — |

---

## 3. 协议族分布

| 协议族 | 链数 | 链列表 |
|---|---|---|
| EVM 家族 | 5 | Ethereum, BSC, Base, Polygon, Scroll |
| Bitcoin/UTXO | 5 | Bitcoin, Zcash, LTC, DOGE, BCH |
| Solana | 1 | Solana |
| Move | 2 | Sui, Aptos |
| Starknet | 1 | Starknet |
| Cosmos-SDK | 1 | Cosmos |
| Substrate | 1 | Polkadot |
| Tron | 1 | Tron(双 API) |
| TON | 1 | TON |
| Cardano | 1 | Cardano |
| Avalanche | 1 | Avalanche P/X |
| NEAR | 1 | NEAR |
| XRPL | 1 | XRP |
| Stellar | 1 | Stellar |
| Algorand | 1 | Algorand |
| Hedera | 1 | Hedera |
| Filecoin | 1 | Filecoin |
| ICP | 1 | ICP |
| CryptoNote(Monero) | 1 | Monero |

**总计**:18 个独立族(EVM/Bitcoin 各占多链),28 条链。

---

## 4. 加链零代码场景验证(H10)

完成 Phase 2 后,验收测试:**业务方加 1 条新 EVM 链(如 Arbitrum)**

预期操作:
1. 拷贝 `config/chains/03-bsc.json` → `config/chains/29-arbitrum.json`
2. 改 4 个字段:`chain` / `chain_id` / `rpc_endpoint` / `block_time_ms`
3. **0 行 Python**
4. 运行 `e2e_smoke arbitrum` → PASS

如果上述任一步失败 → H10 违反,**重构失败**。

---

## 5. 调研进度仪表盘

```
Phase 1.1 (8 已有链):    [ ] 0/8
Phase 1.2 (15 新链):     [ ] 0/15
Phase 1.3 (4 复用链):    [ ] 0/4
─────────────────────────────────
总进度:                  [ ] 0/28 (0%)
```

---

**最后更新**:2026-05-23(骨架建好,调研未开始)
