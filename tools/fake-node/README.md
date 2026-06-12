# fake-node — long-lived test fixture for the blockchain-node-benchmark framework

**Purpose**: integration-test fixture for the framework, not a PoC and not a benchmark target. Run the framework-to-fake-node path after framework changes in monitoring, proxying, analysis, reporting, or chain adapters to verify the local closed loop.

**What it provides**:
- JSON-RPC over HTTP, returning method-specific fixtures recorded from real nodes.
- A non-fixed-rate disk I/O worker with randomized sizes and intervals, so monitoring has observable I/O.
- Multi-family handler architecture: `BLOCKCHAIN_NODE` env -> chain template -> `_meta.adapter_family` -> handler dispatch.
- One binary plus per-family YAML plus per-chain fixtures for 36-chain coverage.

**What it does not solve**:
- Exact workload-weight behavior of real nodes.
- Real-node performance limits.

Full local closed-loop testing flow:
- [Chinese: Local closed-loop testing and fake-node guide](../../docs/zh/local-closed-loop-testing.md)
- [English: Local closed-loop testing and fake-node guide](../../docs/en/local-closed-loop-testing.md)

---

## Adapter-Family Handler Model

The fake-node mirrors the framework adapter-family dispatch model instead of using a single monolithic handler.

Current implementation mirrors the framework `tools/chain_adapters/` architecture:
- `handlers/base.go` -> `Handler` interface + registry, mirroring `chain_adapters/base.py`.
- `handlers/<family>.go` -> per-protocol-family implementation. One handler can serve many chains in the same family.
- Entry path matches the framework: read `BLOCKCHAIN_NODE`, load `config/chains/<chain>.json`, read `_meta.adapter_family`, then dispatch.

---

## Chain-Addition Effort Matrix

| Scenario | Go change | Config change | Typical effort |
|----------|-----------|---------------|----------------|
| New chain in an implemented family, such as another EVM-like chain | **0 lines** | +1 chain template + fixture recording | < 30 minutes |
| New method inside an implemented family | 0 lines or small adapter extension | +1 family YAML method + fixture recording | 10-60 minutes |
| Brand-new protocol family | **+1 handler.go, usually ~150-300 lines** | +1 family YAML + per-chain fixtures | 1-2 engineering hours |

The effort mirrors the framework `tools/chain_adapters/<family>.py` model: one protocol family maps to one adapter module.

---

## 36 Chains -> 6 Protocol Families

Source of truth: `config/chains/*.json:_meta.adapter_family`.

Family assignment is based on RPC request envelope, parameter structure, endpoint routing, authentication/header requirements, response envelope, and block-height parsing. It is not based on brand, token, or ecosystem.

| Family | Chains | Coverage | Handler status |
|--------|-------:|----------|----------------|
| `jsonrpc` | 16 | solana, ethereum, bsc, base, polygon, scroll, arbitrum, optimism, linea, avalanche-c, avalanche-x, zksync-era, near, tron, sui, starknet | implemented |
| `bitcoin_jsonrpc` | 4 | bitcoin, bch, dogecoin, litecoin | implemented |
| `substrate` | 5 | polkadot, kusama, acala, astar, moonbeam | implemented |
| `tendermint` | 5 | cosmos-hub, osmosis, celestia, injective, sei | implemented |
| `rest` | 5 | algorand, aptos, cardano, tezos, ton | implemented |
| `hedera_dual` | 1 | hedera | implemented |
| **TOTAL** | **36** | 184 configured single/mixed RPC methods | **184/184 committed fixture coverage** |

Committed fixture coverage:

```bash
python3 tools/fake-node/check_fixture_coverage.py
```

---

## Usage

```bash
# Build
cd tools/fake-node && go build -o /tmp/fake-node-v2 .

# Run for a specific chain using the same env style as the framework
BLOCKCHAIN_NODE=solana   /tmp/fake-node-v2 -port 19101
BLOCKCHAIN_NODE=ethereum /tmp/fake-node-v2 -port 19102
BLOCKCHAIN_NODE=bitcoin  /tmp/fake-node-v2 -port 19103

# Or via flag, which overrides the env var
/tmp/fake-node-v2 -chain solana -port 19101

# Smoke and fixture coverage verification
bash tools/fake-node/scripts/ci_smoke.sh
python3 tools/fake-node/check_fixture_coverage.py
```

CLI flags:
- `-chain`: chain name; overrides `BLOCKCHAIN_NODE`; default `solana`.
- `-chains-dir`: directory of framework chain templates; default `../../config/chains`.
- `-configs-dir`: directory of per-family fake-node YAML; default `configs`.
- `-fixtures-dir`: fixtures root with per-chain subdirectories; default `./fixtures`.
- `-port`: listen port; default `19000`.

`BLOCKCHAIN_NODE` env handling matches the framework: default `solana`, lowercased.

---

## Directory Structure

```text
tools/fake-node/
├── fake_node.go              # main: env -> template -> family -> handler
├── handlers/
│   ├── base.go               # Handler interface + registry + NotImplementedHandler
│   ├── jsonrpc.go            # JSON-RPC family replay
│   ├── bitcoin_jsonrpc.go    # UTXO / Bitcoin-style replay
│   ├── rest.go               # REST family replay
│   ├── substrate.go          # Substrate / sidecar replay
│   ├── tendermint.go         # Tendermint / Cosmos REST-RPC replay
│   └── hedera_dual.go        # Hedera Mirror REST + JSON-RPC replay
├── configs/
│   ├── jsonrpc.yaml          # method list, tiers, and I/O config
│   ├── bitcoin_jsonrpc.yaml
│   ├── substrate.yaml
│   ├── tendermint.yaml
│   ├── rest.yaml
│   └── hedera_dual.yaml
├── fixtures/
│   ├── solana/
│   ├── ethereum/
│   ├── cosmos-hub/
│   └── <36 chain dirs>/      # 184 committed fake-node fixtures total
└── scripts/
    └── ci_smoke.sh
```

---

## Recording Fixtures

```bash
# Record all 36 chains using the same adapter path as Vegeta target generation.
tools/fake-node/record_rpc_fixtures.sh all

# Record one chain or a comma-separated chain list.
tools/fake-node/record_rpc_fixtures.sh solana
tools/fake-node/record_rpc_fixtures.sh solana,ethereum,bitcoin

# Committed coverage check.
python3 tools/fake-node/check_fixture_coverage.py

# Optional local authenticity check after recording request/response evidence.
python3 tools/fake-node/validate_fixture_authenticity.py --json
python3 tools/fake-node/check_fixture_coverage.py --strict
```

Recording uses `tools/chain_adapters/` to build the exact request envelope that the benchmark sends through Vegeta. The saved fixture is therefore matched to the production path, not to a separate ad-hoc curl script.

---

## Method-To-Fixture Matching

fake-node does not infer response structure from parameter names. Matching is scoped to:

```text
BLOCKCHAIN_NODE + request method + family YAML mapping -> fixtures/<chain>/<fixture>.json
```

This matters because two RPC methods may both accept `tx_hash` or `address` while returning completely different response structures. For example:

- `eth_getTransactionByHash(tx_hash)` returns an EVM transaction object.
- `GET /cosmos/tx/v1beta1/txs/{hash}` returns a Cosmos tx envelope.
- `avm.getTx(txID)` returns an Avalanche X-Chain transaction shape.

When adding a method, record that method's own `chain + method` fixture. Do not reuse a response just because the parameters look similar.

### Example 1: Add a Method to an Existing JSON-RPC Family

1. Declare the method and parameter format in the chain template:

```json
{
  "param_formats": {
    "eth_getTransactionReceipt": "transaction_hash"
  },
  "rpc_methods": {
    "mixed_weighted": [
      {"method": "eth_getTransactionReceipt", "weight": 10}
    ]
  },
  "params": {
    "target_tx_hash": "0x..."
  }
}
```

2. Add the method mapping in `tools/fake-node/configs/jsonrpc.yaml`:

```yaml
methods:
  eth_getTransactionReceipt:
    fixture: eth_getTransactionReceipt.json
    tier: expensive
```

3. Record and verify:

```bash
RPC_FIXTURE_MODES=mixed tools/fake-node/record_rpc_fixtures.sh <chain>
python3 tools/fake-node/check_fixture_coverage.py

# Optional local evidence audit:
python3 tools/fake-node/validate_fixture_authenticity.py --json
python3 tools/fake-node/check_fixture_coverage.py --strict
```

### Example 2: Add a Method to a REST Chain

1. Declare the logical method and HTTP path in the chain template:

```json
{
  "param_formats": {
    "GET /v1/accounts/{addr}/transactions": "path_addr"
  },
  "_meta": {
    "adapter_family": "rest",
    "rest_paths": {
      "GET /v1/accounts/{addr}/transactions": {
        "method": "GET",
        "path": "/v1/accounts/{address}/transactions"
      }
    }
  }
}
```

2. Add the fixture filename in the family YAML:

```yaml
methods:
  GET /v1/accounts/{addr}/transactions:
    fixture: GET__v1_accounts__addr__transactions.json
    tier: mid
```

3. Record the real response. If the request needs samples such as `tx_hash`, `block_hash`, `asset_id`, or `height`, add real queryable values to `params` first.

### When a New Family Is Required

If a new chain or method needs behavior that existing adapters cannot express, it is not only a configuration change. Extend code when you need:

- A new request envelope, such as a protocol that is neither JSON-RPC nor REST path/body.
- New authentication or header rules.
- Multiple protocol endpoints inside one chain where the existing family cannot route by method.
- A new block-height parsing mode.
- Chain-specific parameter encoding that cannot be represented by `param_formats`, `_meta.rest_paths`, or `param_spec`.
