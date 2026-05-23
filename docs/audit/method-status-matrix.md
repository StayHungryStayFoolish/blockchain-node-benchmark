# RPC Method Audit Status Matrix
**R1-PRIME 实证结果** — 基于 4 层证据(L1 文档判别 / L2 endpoint POST / L3 schema 比对 / L4 错误语义)
**Total methods audited**: 51
**Risk tier rules**:
- `tier-low` : L1 + L2(简单读取,无 schema drift 风险)
- `tier-mid` : L1 + L2 + L3(结构化读取,验框架访问字段在)
- `tier-high`: L1 + L2 + L3 + L4(写入/事件/模拟,验错误传递语义)

## Summary
| Verdict | Count |
|---|---:|
| 🟡 P1_NOT_IN_SPEC | 6 |
| 🟡 P1_RPC_ERROR | 16 |
| 🟢 PASS | 29 |

## solana

| Method | Tier | Verdict | L1 doc | L2 endpoint | L3 schema | L4 error |
|---|---|---|---|---|---|---|
| `getAccountInfo` | tier-mid | 🟢 PASS | ACTIVE | PASS | NEEDS_FULL_PAYLOAD | — |
| `getBalance` | tier-low | 🟢 PASS | ACTIVE | PASS | — | — |
| `getTokenAccountBalance` | tier-mid | 🟡 P1_RPC_ERROR | ACTIVE | RPC_ERROR | SKIPPED | — |
| `getLatestBlockhash` | tier-mid | 🟢 PASS | ACTIVE | PASS | NEEDS_FULL_PAYLOAD | — |
| `getBlockHeight` | tier-low | 🟢 PASS | ACTIVE | PASS | — | — |
| `getSignaturesForAddress` | tier-mid | 🟡 P1_RPC_ERROR | ACTIVE | RPC_ERROR | SKIPPED | — |
| `getTransaction` | tier-mid | 🟡 P1_RPC_ERROR | ACTIVE | RPC_ERROR | SKIPPED | — |

## ethereum

| Method | Tier | Verdict | L1 doc | L2 endpoint | L3 schema | L4 error |
|---|---|---|---|---|---|---|
| `eth_getBalance` | tier-low | 🟢 PASS | DOC_ERROR | PASS | — | — |
| `eth_getTransactionCount` | tier-low | 🟢 PASS | DOC_ERROR | PASS | — | — |
| `eth_blockNumber` | tier-low | 🟢 PASS | DOC_ERROR | PASS | — | — |
| `eth_gasPrice` | tier-low | 🟢 PASS | DOC_ERROR | PASS | — | — |
| `eth_getLogs` | tier-high | 🟡 P1_RPC_ERROR | DOC_ERROR | RPC_ERROR | SKIPPED | ERROR_THROWN_AT_RPC_LAYER |
| `eth_getTransactionByHash` | tier-mid | 🟡 P1_RPC_ERROR | DOC_ERROR | RPC_ERROR | SKIPPED | — |

## bsc

| Method | Tier | Verdict | L1 doc | L2 endpoint | L3 schema | L4 error |
|---|---|---|---|---|---|---|
| `eth_getBalance` | tier-low | 🟢 PASS | DOC_ERROR | PASS | — | — |
| `eth_getTransactionCount` | tier-low | 🟢 PASS | DOC_ERROR | PASS | — | — |
| `eth_blockNumber` | tier-low | 🟢 PASS | DOC_ERROR | PASS | — | — |
| `eth_gasPrice` | tier-low | 🟢 PASS | DOC_ERROR | PASS | — | — |
| `eth_getLogs` | tier-high | 🟡 P1_RPC_ERROR | DOC_ERROR | RPC_ERROR | SKIPPED | ERROR_THROWN_AT_RPC_LAYER |
| `eth_getTransactionByHash` | tier-mid | 🟡 P1_RPC_ERROR | DOC_ERROR | RPC_ERROR | SKIPPED | — |

## base

| Method | Tier | Verdict | L1 doc | L2 endpoint | L3 schema | L4 error |
|---|---|---|---|---|---|---|
| `eth_getBalance` | tier-low | 🟢 PASS | ACTIVE | PASS | — | — |
| `eth_getTransactionCount` | tier-low | 🟢 PASS | ACTIVE | PASS | — | — |
| `eth_blockNumber` | tier-low | 🟢 PASS | ACTIVE | PASS | — | — |
| `eth_gasPrice` | tier-low | 🟢 PASS | ACTIVE | PASS | — | — |
| `eth_getLogs` | tier-high | 🟡 P1_RPC_ERROR | ACTIVE | RPC_ERROR | SKIPPED | ERROR_THROWN_AT_RPC_LAYER |
| `eth_getTransactionByHash` | tier-mid | 🟡 P1_RPC_ERROR | ACTIVE | RPC_ERROR | SKIPPED | — |

## scroll

| Method | Tier | Verdict | L1 doc | L2 endpoint | L3 schema | L4 error |
|---|---|---|---|---|---|---|
| `eth_getBalance` | tier-low | 🟡 P1_NOT_IN_SPEC | NOT_IN_SPEC | PASS | — | — |
| `eth_getTransactionCount` | tier-low | 🟡 P1_NOT_IN_SPEC | NOT_IN_SPEC | PASS | — | — |
| `eth_blockNumber` | tier-low | 🟡 P1_NOT_IN_SPEC | NOT_IN_SPEC | PASS | — | — |
| `eth_gasPrice` | tier-low | 🟡 P1_NOT_IN_SPEC | NOT_IN_SPEC | PASS | — | — |
| `eth_getLogs` | tier-high | 🟡 P1_NOT_IN_SPEC | NOT_IN_SPEC | RPC_ERROR | SKIPPED | ERROR_THROWN_AT_RPC_LAYER |
| `eth_getTransactionByHash` | tier-mid | 🟡 P1_NOT_IN_SPEC | NOT_IN_SPEC | RPC_ERROR | SKIPPED | — |

## polygon

| Method | Tier | Verdict | L1 doc | L2 endpoint | L3 schema | L4 error |
|---|---|---|---|---|---|---|
| `eth_getBalance` | tier-low | 🟢 PASS | DOC_ERROR | PASS | — | — |
| `eth_getTransactionCount` | tier-low | 🟢 PASS | DOC_ERROR | PASS | — | — |
| `eth_blockNumber` | tier-low | 🟢 PASS | DOC_ERROR | PASS | — | — |
| `eth_gasPrice` | tier-low | 🟢 PASS | DOC_ERROR | PASS | — | — |
| `eth_getLogs` | tier-high | 🟡 P1_RPC_ERROR | DOC_ERROR | RPC_ERROR | SKIPPED | ERROR_THROWN_AT_RPC_LAYER |
| `eth_getTransactionByHash` | tier-mid | 🟡 P1_RPC_ERROR | DOC_ERROR | RPC_ERROR | SKIPPED | — |

## starknet

| Method | Tier | Verdict | L1 doc | L2 endpoint | L3 schema | L4 error |
|---|---|---|---|---|---|---|
| `starknet_getClassAt` | tier-mid | 🟢 PASS | DOC_ERROR | PASS | NEEDS_FULL_PAYLOAD | — |
| `starknet_getNonce` | tier-mid | 🟢 PASS | DOC_ERROR | PASS | SKIPPED | — |
| `starknet_getStorageAt` | tier-mid | 🟢 PASS | DOC_ERROR | PASS | SKIPPED | — |
| `starknet_blockNumber` | tier-low | 🟢 PASS | DOC_ERROR | PASS | — | — |
| `starknet_getEvents` | tier-high | 🟡 P1_RPC_ERROR | DOC_ERROR | RPC_ERROR | SKIPPED | ERROR_THROWN_AT_RPC_LAYER |
| `starknet_getTransactionByHash` | tier-mid | 🟡 P1_RPC_ERROR | DOC_ERROR | RPC_ERROR | SKIPPED | — |

## sui

| Method | Tier | Verdict | L1 doc | L2 endpoint | L3 schema | L4 error |
|---|---|---|---|---|---|---|
| `sui_getObject` | tier-mid | 🟢 PASS | SKIPPED | PASS | NEEDS_FULL_PAYLOAD | — |
| `sui_getTotalTransactionBlocks` | tier-low | 🟢 PASS | SKIPPED | PASS | — | — |
| `sui_getLatestCheckpointSequenceNumber` | tier-low | 🟢 PASS | SKIPPED | PASS | — | — |
| `suix_getReferenceGasPrice` | tier-low | 🟢 PASS | SKIPPED | PASS | — | — |
| `sui_getChainIdentifier` | tier-low | 🟢 PASS | SKIPPED | PASS | — | — |
| `suix_getOwnedObjects` | tier-mid | 🟡 P1_RPC_ERROR | SKIPPED | RPC_ERROR | SKIPPED | — |
| `sui_getTransactionBlock` | tier-mid | 🟡 P1_RPC_ERROR | SKIPPED | RPC_ERROR | SKIPPED | — |
| `suix_queryTransactionBlocks` | tier-mid | 🟡 P1_RPC_ERROR | SKIPPED | RPC_ERROR | SKIPPED | — |

## Detailed Issues (non-PASS)

### solana / `getTokenAccountBalance` — 🟡 P1_RPC_ERROR

- **Risk tier**: tier-mid
- **L1 doc**: ACTIVE — URL path in /http/, not /deprecated/
  - URL: https://solana.com/docs/rpc
- **L2 endpoint**: RPC_ERROR — code=-32602: Invalid param: not a Token account
  - Raw excerpt: `{"jsonrpc": "2.0", "error": {"code": -32602, "message": "Invalid param: not a Token account"}, "id": 1}`
- **L3 schema**: SKIPPED — L2 not PASS

### solana / `getSignaturesForAddress` — 🟡 P1_RPC_ERROR

- **Risk tier**: tier-mid
- **L1 doc**: ACTIVE — URL path in /http/, not /deprecated/
  - URL: https://solana.com/docs/rpc
- **L2 endpoint**: RPC_ERROR — code=-32602: `params` should have at least 1 argument(s)
  - Raw excerpt: `{"jsonrpc": "2.0", "error": {"code": -32602, "message": "`params` should have at least 1 argument(s)"}, "id": 1}`
- **L3 schema**: SKIPPED — L2 not PASS

### solana / `getTransaction` — 🟡 P1_RPC_ERROR

- **Risk tier**: tier-mid
- **L1 doc**: ACTIVE — URL path in /http/, not /deprecated/
  - URL: https://solana.com/docs/rpc
- **L2 endpoint**: RPC_ERROR — code=-32602: `params` should have at least 1 argument(s)
  - Raw excerpt: `{"jsonrpc": "2.0", "error": {"code": -32602, "message": "`params` should have at least 1 argument(s)"}, "id": 1}`
- **L3 schema**: SKIPPED — L2 not PASS

### ethereum / `eth_getLogs` — 🟡 P1_RPC_ERROR

- **Risk tier**: tier-high
- **L1 doc**: DOC_ERROR — HTTPError: HTTP Error 403: Forbidden
  - URL: https://ethereum.org/en/developers/docs/apis/json-rpc/
- **L2 endpoint**: RPC_ERROR — code=-32602: missing value for required argument 0
  - Raw excerpt: `{"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "missing value for required argument 0"}}`
- **L3 schema**: SKIPPED — L2 not PASS
- **L4 error semantics**: ERROR_THROWN_AT_RPC_LAYER — Bad params triggered JSON-RPC error (top-level error field) — framework needs to handle this

### ethereum / `eth_getTransactionByHash` — 🟡 P1_RPC_ERROR

- **Risk tier**: tier-mid
- **L1 doc**: DOC_ERROR — HTTPError: HTTP Error 403: Forbidden
  - URL: https://ethereum.org/en/developers/docs/apis/json-rpc/
- **L2 endpoint**: RPC_ERROR — code=-32602: missing value for required argument 0
  - Raw excerpt: `{"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "missing value for required argument 0"}}`
- **L3 schema**: SKIPPED — L2 not PASS

### bsc / `eth_getLogs` — 🟡 P1_RPC_ERROR

- **Risk tier**: tier-high
- **L1 doc**: DOC_ERROR — HTTPError: HTTP Error 404: Not Found
  - URL: https://docs.bnbchain.org/docs/rpc
- **L2 endpoint**: RPC_ERROR — code=-32005: limit exceeded
  - Raw excerpt: `{"jsonrpc": "2.0", "id": 1, "error": {"code": -32005, "message": "limit exceeded"}}`
- **L3 schema**: SKIPPED — L2 not PASS
- **L4 error semantics**: ERROR_THROWN_AT_RPC_LAYER — Bad params triggered JSON-RPC error (top-level error field) — framework needs to handle this

### bsc / `eth_getTransactionByHash` — 🟡 P1_RPC_ERROR

- **Risk tier**: tier-mid
- **L1 doc**: DOC_ERROR — HTTPError: HTTP Error 404: Not Found
  - URL: https://docs.bnbchain.org/docs/rpc
- **L2 endpoint**: RPC_ERROR — code=-32602: missing value for required argument 0
  - Raw excerpt: `{"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "missing value for required argument 0"}}`
- **L3 schema**: SKIPPED — L2 not PASS

### base / `eth_getLogs` — 🟡 P1_RPC_ERROR

- **Risk tier**: tier-high
- **L1 doc**: ACTIVE — 'eth_getLogs' found in execution-apis spec
  - URL: https://docs.base.org/chain/network-information
- **L2 endpoint**: RPC_ERROR — code=-32602: Invalid params
  - Raw excerpt: `{"jsonrpc": "2.0", "error": {"code": -32602, "message": "Invalid params", "data": "No more params"}, "id": 1}`
- **L3 schema**: SKIPPED — L2 not PASS
- **L4 error semantics**: ERROR_THROWN_AT_RPC_LAYER — Bad params triggered JSON-RPC error (top-level error field) — framework needs to handle this

### base / `eth_getTransactionByHash` — 🟡 P1_RPC_ERROR

- **Risk tier**: tier-mid
- **L1 doc**: ACTIVE — 'eth_getTransactionByHash' found in execution-apis spec
  - URL: https://docs.base.org/chain/network-information
- **L2 endpoint**: RPC_ERROR — code=-32602: Invalid params
  - Raw excerpt: `{"jsonrpc": "2.0", "error": {"code": -32602, "message": "Invalid params", "data": "No more params"}, "id": 1}`
- **L3 schema**: SKIPPED — L2 not PASS

### scroll / `eth_getBalance` — 🟡 P1_NOT_IN_SPEC

- **Risk tier**: tier-low
- **L1 doc**: NOT_IN_SPEC — 'eth_getBalance' NOT found in execution-apis spec body
  - URL: https://docs.scroll.io/en/developers/developer-quickstart/
- **L2 endpoint**: PASS — result returned

### scroll / `eth_getTransactionCount` — 🟡 P1_NOT_IN_SPEC

- **Risk tier**: tier-low
- **L1 doc**: NOT_IN_SPEC — 'eth_getTransactionCount' NOT found in execution-apis spec body
  - URL: https://docs.scroll.io/en/developers/developer-quickstart/
- **L2 endpoint**: PASS — result returned

### scroll / `eth_blockNumber` — 🟡 P1_NOT_IN_SPEC

- **Risk tier**: tier-low
- **L1 doc**: NOT_IN_SPEC — 'eth_blockNumber' NOT found in execution-apis spec body
  - URL: https://docs.scroll.io/en/developers/developer-quickstart/
- **L2 endpoint**: PASS — result returned

### scroll / `eth_gasPrice` — 🟡 P1_NOT_IN_SPEC

- **Risk tier**: tier-low
- **L1 doc**: NOT_IN_SPEC — 'eth_gasPrice' NOT found in execution-apis spec body
  - URL: https://docs.scroll.io/en/developers/developer-quickstart/
- **L2 endpoint**: PASS — result returned

### scroll / `eth_getLogs` — 🟡 P1_NOT_IN_SPEC

- **Risk tier**: tier-high
- **L1 doc**: NOT_IN_SPEC — 'eth_getLogs' NOT found in execution-apis spec body
  - URL: https://docs.scroll.io/en/developers/developer-quickstart/
- **L2 endpoint**: RPC_ERROR — code=-32602: missing value for required argument 0
  - Raw excerpt: `{"id": 1, "jsonrpc": "2.0", "error": {"code": -32602, "message": "missing value for required argument 0"}}`
- **L3 schema**: SKIPPED — L2 not PASS
- **L4 error semantics**: ERROR_THROWN_AT_RPC_LAYER — Bad params triggered JSON-RPC error (top-level error field) — framework needs to handle this

### scroll / `eth_getTransactionByHash` — 🟡 P1_NOT_IN_SPEC

- **Risk tier**: tier-mid
- **L1 doc**: NOT_IN_SPEC — 'eth_getTransactionByHash' NOT found in execution-apis spec body
  - URL: https://docs.scroll.io/en/developers/developer-quickstart/
- **L2 endpoint**: RPC_ERROR — code=-32602: missing value for required argument 0
  - Raw excerpt: `{"id": 1, "jsonrpc": "2.0", "error": {"code": -32602, "message": "missing value for required argument 0"}}`
- **L3 schema**: SKIPPED — L2 not PASS

### polygon / `eth_getLogs` — 🟡 P1_RPC_ERROR

- **Risk tier**: tier-high
- **L1 doc**: DOC_ERROR — HTTPError: HTTP Error 403: Forbidden
  - URL: https://docs.polygon.technology/pos/reference/rpc-endpoints/
- **L2 endpoint**: RPC_ERROR — code=-32602: missing value for required argument 0
  - Raw excerpt: `{"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "missing value for required argument 0"}}`
- **L3 schema**: SKIPPED — L2 not PASS
- **L4 error semantics**: ERROR_THROWN_AT_RPC_LAYER — Bad params triggered JSON-RPC error (top-level error field) — framework needs to handle this

### polygon / `eth_getTransactionByHash` — 🟡 P1_RPC_ERROR

- **Risk tier**: tier-mid
- **L1 doc**: DOC_ERROR — HTTPError: HTTP Error 403: Forbidden
  - URL: https://docs.polygon.technology/pos/reference/rpc-endpoints/
- **L2 endpoint**: RPC_ERROR — code=-32602: missing value for required argument 0
  - Raw excerpt: `{"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "missing value for required argument 0"}}`
- **L3 schema**: SKIPPED — L2 not PASS

### starknet / `starknet_getEvents` — 🟡 P1_RPC_ERROR

- **Risk tier**: tier-high
- **L1 doc**: DOC_ERROR — HTTPError: HTTP Error 404: Not Found
  - URL: https://docs.starknet.io/architecture-and-concepts/network-architecture/rpc-providers/
- **L2 endpoint**: RPC_ERROR — code=-32602: Invalid params
  - Raw excerpt: `{"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "Invalid params", "data": {"reason": "missing field: \"filter\""}}}`
- **L3 schema**: SKIPPED — L2 not PASS
- **L4 error semantics**: ERROR_THROWN_AT_RPC_LAYER — Bad params triggered JSON-RPC error (top-level error field) — framework needs to handle this

### starknet / `starknet_getTransactionByHash` — 🟡 P1_RPC_ERROR

- **Risk tier**: tier-mid
- **L1 doc**: DOC_ERROR — HTTPError: HTTP Error 404: Not Found
  - URL: https://docs.starknet.io/architecture-and-concepts/network-architecture/rpc-providers/
- **L2 endpoint**: RPC_ERROR — code=-32602: Invalid params
  - Raw excerpt: `{"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "Invalid params", "data": {"reason": "missing field: \"transaction_hash\""}}}`
- **L3 schema**: SKIPPED — L2 not PASS

### sui / `suix_getOwnedObjects` — 🟡 P1_RPC_ERROR

- **Risk tier**: tier-mid
- **L1 doc**: SKIPPED — Sui docs structure不易自动判别,L1 skipped, rely on L2
  - URL: https://docs.sui.io/sui-api-ref
- **L2 endpoint**: RPC_ERROR — code=-32602: Invalid params
  - Raw excerpt: `{"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "Invalid params", "data": "No more params"}}`
- **L3 schema**: SKIPPED — L2 not PASS

### sui / `sui_getTransactionBlock` — 🟡 P1_RPC_ERROR

- **Risk tier**: tier-mid
- **L1 doc**: SKIPPED — Sui docs structure不易自动判别,L1 skipped, rely on L2
  - URL: https://docs.sui.io/sui-api-ref
- **L2 endpoint**: RPC_ERROR — code=-32602: Invalid params
  - Raw excerpt: `{"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "Invalid params", "data": "No more params"}}`
- **L3 schema**: SKIPPED — L2 not PASS

### sui / `suix_queryTransactionBlocks` — 🟡 P1_RPC_ERROR

- **Risk tier**: tier-mid
- **L1 doc**: SKIPPED — Sui docs structure不易自动判别,L1 skipped, rely on L2
  - URL: https://docs.sui.io/sui-api-ref
- **L2 endpoint**: RPC_ERROR — code=-32602: Invalid params
  - Raw excerpt: `{"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "Invalid params", "data": "No more params"}}`
- **L3 schema**: SKIPPED — L2 not PASS

