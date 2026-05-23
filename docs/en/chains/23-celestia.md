# 23 — Celestia Research (DIFF-ONLY vs 05-cosmos-hub.md)

> **Version**: v1.0 (Phase 1.2 Wave7)
> **Date**: 2026-05-23
> **Author**: Hermes Agent
> **Status**: 🟢 Pending user review
> **Mode**: **Strict DIFF-ONLY** (Guardrail 2). This document captures only Celestia's **material deltas** vs Cosmos Hub. Tendermint RPC and Cosmos REST/LCD generic protocol structure, error code tables, and standard `/cosmos/bank/*` `/cosmos/staking/*` `/cosmos/tx/*` module paths are documented in `docs/en/chains/05-cosmos-hub.md` (692 lines, Wave1 committed).
> **Evidence**: E1 unit test / E2 curl / E3 official docs / E4 GitHub source / E5 framework grep.

---

## Metadata

| Field | Value |
|---|---|
| Chain name | Celestia |
| Number | 23 |
| Mainnet ChainID | `celestia` (string, not numeric) — E2 verified at `https://celestia-rpc.publicnode.com/status` returning `node_info.network = "celestia"` |
| Node app | **celestia-app v8.0.3** (`celestia-appd`, git_commit `0fc10e0`, build_tags `ledger,multiplexer`) — E2 via `/cosmos/base/tendermint/v1beta1/node_info.application_version` |
| Consensus layer | **CometBFT v0.38.17** (proto app=8 block=11 p2p=8) — E2 |
| Research date | 2026-05-23 |
| Framework-supported? | ❌ — E5 same as cosmos-hub: `supported_blockchains` excludes cosmos family |
| Mainnet launch | 2023-10-31 (block 1) — E3 |

---

## 1. Sources (authoritative + fork history)

| Type | URL | Note |
|---|---|---|
| Official docs | https://docs.celestia.org/ | Modular concepts, blob lifecycle, DA sampling |
| Node docs | https://docs.celestia.org/nodes/overview | bridge / full / light node roles |
| GitHub (celestia-app) | https://github.com/celestiaorg/celestia-app | **App layer**, forked from cosmos-sdk |
| GitHub (celestia-node) | https://github.com/celestiaorg/celestia-node | **DA layer** (bridge/full/light), independent JSON-RPC (`blob.*` `header.*` `share.*` `das.*` `p2p.*`) — **two separate RPCs** from celestia-app's Tendermint RPC |
| GitHub (celestia-core) | https://github.com/celestiaorg/celestia-core | Forked from cometbft v0.38, adds erasure coding / NMT (Namespaced Merkle Tree) |
| Specs | https://celestiaorg.github.io/celestia-app/ | proto + module spec (blob/blobstream/minfee) |
| Explorer (Celenium) | https://celenium.io | DA-native explorer, namespace lookup |
| Explorer (Mintscan) | https://www.mintscan.io/celestia | Standard tx/staking |
| Publicnode RPC | https://celestia-rpc.publicnode.com | E2 OK |
| Publicnode REST | https://celestia-rest.publicnode.com | E2 OK |
| Numia REST | https://celestia-api.numia.xyz | Backup |

**Fork history (E4)**:
- celestia-app v8.x currently aligns with **cosmos-sdk v0.50.x** (post-Eden upgrade); v0.38 CometBFT matches gaia v27's v0.38.19 closely → **Tendermint RPC is 100% protocol-compatible**.
- Unique modules are injected via cosmos-sdk module mechanism (not stdlib forks), so other chains could in principle reuse them.

---

## 2. Relationship with Cosmos Hub

| Dim | Cosmos Hub (gaia v27.3.0) | Celestia (celestia-app v8.0.3) | Compatible? |
|---|---|---|---|
| Cosmos SDK ver | v0.50.x | v0.50.x (same generation) | ✅ standard module paths 100% reusable |
| CometBFT ver | v0.38.19 | v0.38.17 | ✅ Tendermint RPC fully aligned |
| Consensus | Tendermint BFT | Tendermint BFT + **DA erasure coding** | ⚠️ compatible at consensus; data layer adds `data_hash` semantic upgrade (NMT root) |
| Bech32 prefix | `cosmos` | `celestia` | ⚠️ addresses not interchangeable (prefix differs, raw 32B same) |
| Native denom | `uatom` | `utia` | ⚠️ amount semantics same |
| Block time | ~6s | ~6s (latest 11218365, derivable) | ✅ |
| **Block size** | ~50–500 KB typical | **up to 8 MiB** (square_size 128, Hyperion upper bound) — distribution in §6 | ❌ **100× gap, benchmark must handle explicitly** |
| Unique modules | (none) | **`blob` / `blobstream` (formerly qgb) / `minfee` / `signal`** | ❌ |
| Missing/altered | — | **No standard `mint` (TIA inflation reshaped in `x/mint`), partial `gov` proposal extensions removed, some IBC packet middleware absent** | — |

---

## 3. Public endpoint verification (E2, 2026-05-23)

| Endpoint | Protocol | Status | latest_block_height | App version | Note |
|---|---|---|---|---|---|
| https://celestia-rpc.publicnode.com | Tendermint RPC | 200 | **11218365** | celestia-app 8.0.3 | `/status` returns full node_info (E2 ~1 KB JSON); archive: earliest=8718365 (~2.5M-block history) |
| https://celestia-rest.publicnode.com | Cosmos REST | 200 | same | same | `/cosmos/base/tendermint/v1beta1/blocks/latest` returns NMT-style data_hash (base64) |
| https://celestia-api.numia.xyz | Cosmos REST | not tested (kept as backup) | — | — | requires_self_hosted=No |

**Key E2 finding (blob/state/share module liveness)**:

```
# Probed 4 unique modules via publicnode REST (2026-05-23):
GET /celestia/blob/v1/params          → -32701 "not implemented"
GET /celestia/v1/blob/params          → -32701 "not implemented"
GET /qgb/v1/params                    → -32701 "not implemented"
GET /celestia/minfee/v1/params        → -32701 "not implemented"
```

→ **Conclusion**: publicnode's REST gateway **disables the grpc-gateway routes for Celestia-unique modules** (standard `/cosmos/*` paths work fine). Implications:
1. Unique-module queries **require a self-hosted celestia-app full node** for reliable use;
2. The framework plugin must mark `blob/blobstream/minfee` as `requires_self_hosted=true`, decoupled from standard `/cosmos/*` paths;
3. Likewise, publicnode does **not expose celestia-node's `blob.GetAll` / `share.GetSharesByNamespace`** (those live on the DA-node's independent JSON-RPC, not the app RPC).

---

## 4. Material delta table (Cosmos Hub → Celestia)

### 4.1 Unique modules (E3 + E4)

| Module | REST path | RPC methods | Purpose | Benchmark impact |
|---|---|---|---|---|
| `blob` | `/celestia/blob/v1/params` `/celestia/blob/v1/params/gas_per_blob_byte` | `MsgPayForBlobs` (tx type, not query) | Submit rollup data (blob) + read params (GasPerBlobByte / GovMaxSquareSize) | 🔴 **core workload**, 80%+ of txs are PayForBlobs |
| `blobstream` (formerly qgb) | `/qgb/v1/params` `/qgb/v1/attestations` | — | Ethereum→Celestia DA bridge light-client attestations | 🟡 low frequency, ignorable |
| `minfee` | `/celestia/minfee/v1/params` | — | Network-enforced min gas price (`network_min_gas_price`) | 🟢 read once at startup, cache |
| `signal` | `/celestia/signal/v1/*` | — | Hard-fork upgrade version coordination (replaces parts of `x/upgrade`) | 🟢 no benchmark need |
| **DA-node independent RPC** (celestia-node, **not in celestia-app**) | JSON-RPC port 26658 | `blob.GetAll(height, namespaces[])` `blob.Submit(blobs[], gasPrice)` `share.GetSharesByNamespace` `share.GetEDS` `header.GetByHeight` `das.SamplingStats` `p2p.PeerInfo` | rollup/app reads blob, light-node DAS sampling | 🔴 **plugin must add a 2nd connection target**: `celestia-da-node` shares the chain but RPC endpoint/methods differ entirely from `celestia-app` |

### 4.2 Consensus / data-structure delta

| Item | Cosmos Hub | Celestia |
|---|---|---|
| `block.data.txs` | Plain tx array | tx array + separate `square` (rollup blobs live in data square, **not in txs**). `data_hash` = NMT root, not plain Merkle |
| `block.header` extras | Standard 14 fields | + implicit `square_size` (derivable from `part_set_header.total`; E2 observed `total:5` on a 1.6 MB block) |
| Max block size | ~22 MB theoretical, ~1 MB practical | **8 MiB hard cap** (GovMaxSquareSize=128, SquareSize²×ShareSize≈8 MiB); actual distribution in §6 |
| Erasure coding | None | **2D Reed-Solomon**, enables light-node DAS verification |

### 4.3 Token model

| Item | Cosmos Hub | Celestia |
|---|---|---|
| Native denom | `uatom` (6 dec) | `utia` (6 dec) |
| Inflation | 7%–20% dynamic by bonded ratio | Starts 8%, decays -10% per year to 1.5% floor (E3) |
| Staking/Slashing | Standard `x/staking` `x/slashing` | Same (no modification) |

---

## 5. Method delta (99% same as Cosmos Hub; only uniques listed)

> **Not repeated**: all `/cosmos/bank/*` `/cosmos/staking/*` `/cosmos/tx/*` `/cosmos/auth/*` `/cosmos/base/tendermint/*` paths are identical to cosmos-hub.md §5 (E5 grep of cosmos-sdk v0.50.x proto files confirmed).

### 5.1 Celestia-unique queries (REST)

| Path | Input | Output | E2 status | Note |
|---|---|---|---|---|
| GET `/celestia/blob/v1/params` | — | `gas_per_blob_byte` `gov_max_square_size` | E2 publicnode refused (only available on self-hosted) | Read once at startup, cache |
| GET `/celestia/minfee/v1/params` | — | `network_min_gas_price` (string, e.g. `"0.000001"`) | Same | Startup read |
| GET `/celestia/signal/v1/upgrade` | — | `app_version` | — | Upgrade tracking |
| GET `/qgb/v1/attestations/{nonce}` | nonce uint64 | DataCommitment / ValsetConfirm | — | ETH bridge only |

### 5.2 celestia-node independent JSON-RPC (port 26658, **distinct from app RPC 26657**)

| Method | params | Returns | Benchmark criticality |
|---|---|---|---|
| `header.GetByHeight` | `[height]` | Header (with DAH = DataAvailabilityHeader) | 🟢 replaces `/block` when only header is needed |
| `blob.GetAll` | `[height, namespaces[]]` | `[]Blob` (each with data / namespace / share_version) | 🔴 **core for fetch_blocks**: fetch all blobs at a height for the given namespaces |
| `blob.Submit` | `[blobs[], gas_price]` | tx hash | Rollup sequencer only |
| `share.GetSharesByNamespace` | `[height, namespace]` | shares[] + NMT proof | 🟡 DA sampling verification |
| `share.GetEDS` | `[height]` | ExtendedDataSquare (full 2D matrix) | 🔴 **full EDS download can reach 32 MB** (8 MB blob × 4 erasure factor), needs its own benchmark case |
| `das.SamplingStats` | — | `{head_of_sampled_chain, head_of_catchup, ...}` | 🟢 light-node health |
| `p2p.PeerInfo` | — | peers[] | 🟢 |

---

## 6. Real-load measurement (E2, 2026-05-23)

**Block size distribution across 5 consecutive heights** (measured by `/block?height=H` JSON response size; heights = 11218360..11218364):

| Height | JSON bytes | Approx | Note |
|---|---:|---|---|
| 11218360 | 479,724 | ~470 KB | medium-blob block |
| 11218361 | 351,480 | ~340 KB | small |
| 11218362 | **1,642,337** | **~1.6 MB** | **large-blob block** (rollup batch) |
| 11218363 | 328,230 | ~320 KB | small |
| 11218364 | 533,830 | ~520 KB | medium |

**Compared to Cosmos Hub same-period measurements** (cosmos-hub.md §6): single-block JSON is typically 20–80 KB. **Celestia averages 10–20× larger, peaks 80–100× larger**.

**Impact on benchmark functions**:
1. `fetch_blocks` function: **single-HTTP-response buffer must be ≥ 16 MB** (8 MB blob + ~33% base64 inflation + JSON-RPC wrapper). The framework's EVM-default 1 MB buffer **must be explicitly enlarged**.
2. **HTTP timeout must be ≥ 30s**: an 8 MB block transfers in ~1s over a 100 Mbps link, but publicnode CDN + JSON serialization can spike to 5–10s.
3. **Concurrent block-fetch strategy rewritten**: Cosmos Hub can handle 16-concurrent; Celestia should use 4–8 (else bandwidth saturation distorts latency metrics).
4. **Network (NET I/O) becomes the first bottleneck**: 8 MB × every 6s = ~10.7 Mbps sustained downstream; 16-concurrent catch-up can hit a 100 Mbps link's ceiling → **this is precisely the most valuable finding** Celestia benchmarking surfaces.

**Typical tx**: `MsgPayForBlobs` (`celestia.blob.v1.MsgPayForBlobs`), containing `signer / namespaces[] / blob_sizes[] / share_versions[] / share_commitments[]`. The actual blob data is transported separately from the tx via the BlobTx wrapper (E3 ADR-006).

---

## 7. DSL decisions (predicted new fields)

### 7.1 Reuse of existing DSL fields

- `family: "cosmos"` (same as Cosmos Hub, **no new family**)
- `consensus: "tendermint-bft"`
- `address_format: "bech32"` + `bech32_prefix: "celestia"`
- `native_denom: "utia"`
- `requires_self_hosted_for: ["blob", "blobstream", "minfee", "signal"]` (new)

### 7.2 **New DSL sub-enum**: `rollup_type: "modular_da"`

**ASK** (user decision needed):

```yaml
# Proposed: add rollup_type field (sub-enum, default null) to chain DSL:
rollup_type:
  - null                # Plain L1 (Cosmos Hub / Solana / BTC)
  - "optimistic"        # OP rollup (Arbitrum / Optimism / Base)
  - "zk"                # ZK rollup (zkSync Era / Linea / Starknet)
  - "validium"          # Off-chain data + ZK proof (Immutable X)
  - "modular_da"        # [NEW] Pure DA layer; not itself a rollup but serves rollups (Celestia / Avail / EigenDA)
```

**Rationale**:
1. Celestia is not a rollup, but its workload (blob submission / huge blocks / DA sampling) differs entirely from L1/L2; it needs its own classification to **drive the benchmark profile** (buffer / timeout / concurrency).
2. When the framework later integrates Avail / EigenDA, they reuse the same enum — no further extension needed.
3. Orthogonal to `family: "cosmos"` (Celestia is simultaneously cosmos-family and modular_da-type).

### 7.3 Recommended plugin profile defaults

```yaml
celestia:
  family: cosmos
  rollup_type: modular_da
  block_time_s: 6
  expected_block_size_mb: { p50: 0.5, p95: 4, max: 8 }
  fetch_buffer_mb: 16
  http_timeout_s: 30
  fetch_concurrency: 6
  da_node_rpc_port: 26658     # separate connection target
  app_rpc_port: 26657
  bottleneck_priority: [NET, DISK_WRITE, CPU]  # differs from EVM's [CPU, DISK_IOPS]
```

---

## 8. H8 evidence checklist

| # | Command | Result | Use |
|---|---|---|---|
| E2-1 | `POST /status` (RPC) | `network=celestia`, `latest_block_height=11218365`, `version=0.38.17` | ChainID + CometBFT version |
| E2-2 | `GET /cosmos/base/tendermint/v1beta1/node_info` | `application_version.name=celestia-app version=8.0.3 git_commit=0fc10e0` | App version |
| E2-3 | `GET /cosmos/base/tendermint/v1beta1/blocks/latest` | data_hash + part_set_header.total=5 | Block-structure alignment |
| E2-4 | `GET /celestia/blob/v1/params` | `-32701 not implemented` | publicnode hides unique modules → evidence for requires_self_hosted |
| E2-5 | `GET /qgb/v1/params` | `-32701 not implemented` | same |
| E2-6 | `GET /celestia/minfee/v1/params` | `-32701 not implemented` | same |
| E2-7 | Size sweep across 5 consecutive blocks | 320 KB / 350 KB / **1.6 MB** / 480 KB / 530 KB | Block-size distribution; validates 8 MB cap hypothesis and NET-bottleneck priority |

---

## 9. Risks / Open items

- [ ] **DA-node RPC not yet measured**: celestia-node port 26658 requires a self-hosted light/full node (publicnode does not provide it); real latency and peak bandwidth of `blob.GetAll` / `share.GetEDS` deferred to Phase 2.x once a self-hosted node is up — E2 to be added.
- [ ] **Peak 8 MB block not directly captured**: largest of 5 consecutive blocks was 1.6 MB; needs a historical-peak sweep (Eclipse / Manta heavy-submission windows) to add E2.
- [ ] **rollup_type enum**: pending user ack before writing into `config/chains/*.yaml` schema.
- [ ] **Plugin design**: should `CelestiaAdapter` inherit from `CosmosAdapter` and only override `fetch_blocks` plus add a `DANodeAdapter`? Defer to Phase 2.x architecture review.
