# Sync Health Registry Audit

Generated from local chain templates and adapter health probes. This audit does not contact public RPC endpoints.

## Summary

- Total chains: 36
- Current modes: {'absolute_gap': 24, 'conditional_gap': 10, 'freshness_only': 1, 'reported_lag': 1}
- Calibration status: {'implemented': 36}

## Chain Matrix

| Chain | Family | Current | Recommended | Unit | Probe Kind | Status | Notes |
|---|---|---|---|---|---|---|---|
| acala | substrate | absolute_gap | absolute_gap | block | numeric_height | implemented | Adapter compares chain_getHeader.number as the Substrate height cursor documented in local chain evidence. system_syncState remains a future conditional_gap enhancement only after per-chain fixture verification. |
| algorand | rest | absolute_gap | absolute_gap | round | numeric_height | implemented | Adapter health probe returns a numeric height/cursor that can be compared across local and target endpoints. |
| aptos | rest | absolute_gap | absolute_gap | block | numeric_height | implemented | Adapter health probe returns a numeric height/cursor that can be compared across local and target endpoints. |
| arbitrum | jsonrpc | conditional_gap | conditional_gap | block | conditional_sync_state | implemented | Health probe uses local eth_syncing. false maps to lag 0; syncing objects map to highestBlock-currentBlock and reuse BLOCK_HEIGHT_DIFF_THRESHOLD. |
| astar | substrate | absolute_gap | absolute_gap | block | numeric_height | implemented | Adapter compares chain_getHeader.number as the Substrate height cursor documented in local chain evidence. system_syncState remains a future conditional_gap enhancement only after per-chain fixture verification. |
| avalanche-c | jsonrpc | conditional_gap | conditional_gap | block | conditional_sync_state | implemented | Health probe uses local eth_syncing. false maps to lag 0; syncing objects map to highestBlock-currentBlock and reuse BLOCK_HEIGHT_DIFF_THRESHOLD. |
| avalanche-x | jsonrpc | absolute_gap | absolute_gap | block | numeric_height | implemented | Adapter health probe returns a numeric height/cursor that can be compared across local and target endpoints. |
| base | jsonrpc | conditional_gap | conditional_gap | block | conditional_sync_state | implemented | Health probe uses local eth_syncing. false maps to lag 0; syncing objects map to highestBlock-currentBlock and reuse BLOCK_HEIGHT_DIFF_THRESHOLD. |
| bch | bitcoin_jsonrpc | absolute_gap | absolute_gap | block | unknown | implemented | Health probe uses getblockchaininfo.blocks as the comparable cursor; headers and initialblockdownload remain available for future local-only sync enrichment. |
| bitcoin | bitcoin_jsonrpc | absolute_gap | absolute_gap | block | unknown | implemented | Health probe uses getblockchaininfo.blocks as the comparable cursor; headers and initialblockdownload remain available for future local-only sync enrichment. |
| bsc | jsonrpc | conditional_gap | conditional_gap | block | conditional_sync_state | implemented | Health probe uses local eth_syncing. false maps to lag 0; syncing objects map to highestBlock-currentBlock and reuse BLOCK_HEIGHT_DIFF_THRESHOLD. |
| cardano | rest | absolute_gap | absolute_gap | block | numeric_height | implemented | Adapter health probe returns a numeric height/cursor that can be compared across local and target endpoints. |
| celestia | tendermint | absolute_gap | absolute_gap | block | numeric_height | implemented | Adapter health probe returns a numeric height/cursor that can be compared across local and target endpoints. |
| cosmos-hub | tendermint | absolute_gap | absolute_gap | block | numeric_height | implemented | Adapter health probe returns a numeric height/cursor that can be compared across local and target endpoints. |
| dogecoin | bitcoin_jsonrpc | absolute_gap | absolute_gap | block | unknown | implemented | Health probe uses getblockchaininfo.blocks as the comparable cursor; headers and initialblockdownload remain available for future local-only sync enrichment. |
| ethereum | jsonrpc | conditional_gap | conditional_gap | block | conditional_sync_state | implemented | Health probe uses local eth_syncing. false maps to lag 0; syncing objects map to highestBlock-currentBlock and reuse BLOCK_HEIGHT_DIFF_THRESHOLD. |
| hedera | hedera_dual | freshness_only | freshness_only | timestamp_seconds | monotonic_timestamp | implemented | Hedera Mirror probe returns a consensus timestamp cursor, not canonical block height. |
| injective | tendermint | absolute_gap | absolute_gap | block | numeric_height | implemented | Adapter health probe returns a numeric height/cursor that can be compared across local and target endpoints. |
| kusama | substrate | absolute_gap | absolute_gap | block | numeric_height | implemented | Adapter compares chain_getHeader.number as the Substrate height cursor documented in local chain evidence. system_syncState remains a future conditional_gap enhancement only after per-chain fixture verification. |
| linea | jsonrpc | conditional_gap | conditional_gap | block | conditional_sync_state | implemented | Health probe uses local eth_syncing. false maps to lag 0; syncing objects map to highestBlock-currentBlock and reuse BLOCK_HEIGHT_DIFF_THRESHOLD. |
| litecoin | bitcoin_jsonrpc | absolute_gap | absolute_gap | block | unknown | implemented | Health probe uses getblockchaininfo.blocks as the comparable cursor; headers and initialblockdownload remain available for future local-only sync enrichment. |
| moonbeam | substrate | absolute_gap | absolute_gap | block | numeric_height | implemented | Adapter compares chain_getHeader.number as the Substrate height cursor documented in local chain evidence. system_syncState remains a future conditional_gap enhancement only after per-chain fixture verification. |
| near | jsonrpc | absolute_gap | absolute_gap | block | numeric_height | implemented | Adapter health probe returns a numeric height/cursor that can be compared across local and target endpoints. |
| optimism | jsonrpc | conditional_gap | conditional_gap | block | conditional_sync_state | implemented | Health probe uses local eth_syncing. false maps to lag 0; syncing objects map to highestBlock-currentBlock and reuse BLOCK_HEIGHT_DIFF_THRESHOLD. |
| osmosis | tendermint | absolute_gap | absolute_gap | block | numeric_height | implemented | Adapter health probe returns a numeric height/cursor that can be compared across local and target endpoints. |
| polkadot | substrate | absolute_gap | absolute_gap | block | numeric_height | implemented | Adapter compares chain_getHeader.number as the Substrate height cursor documented in local chain evidence. system_syncState remains a future conditional_gap enhancement only after per-chain fixture verification. |
| polygon | jsonrpc | conditional_gap | conditional_gap | block | conditional_sync_state | implemented | Health probe uses local eth_syncing. false maps to lag 0; syncing objects map to highestBlock-currentBlock and reuse BLOCK_HEIGHT_DIFF_THRESHOLD. |
| scroll | jsonrpc | conditional_gap | conditional_gap | block | conditional_sync_state | implemented | Health probe uses local eth_syncing. false maps to lag 0; syncing objects map to highestBlock-currentBlock and reuse BLOCK_HEIGHT_DIFF_THRESHOLD. |
| sei | tendermint | absolute_gap | absolute_gap | block | numeric_height | implemented | Adapter health probe returns a numeric height/cursor that can be compared across local and target endpoints. |
| solana | jsonrpc | reported_lag | reported_lag | slot | boolean_or_reported_health | implemented | Health probe uses Solana getHealth. A healthy result maps to lag 0; unhealthy responses with numSlotsBehind map to slot lag and reuse BLOCK_HEIGHT_DIFF_THRESHOLD. |
| starknet | jsonrpc | absolute_gap | absolute_gap | block | numeric_height | implemented | Adapter health probe returns a numeric height/cursor that can be compared across local and target endpoints. |
| sui | jsonrpc | absolute_gap | absolute_gap | block | numeric_height | implemented | Adapter health probe returns a numeric height/cursor that can be compared across local and target endpoints. |
| tezos | rest | absolute_gap | absolute_gap | block | numeric_height | implemented | Adapter health probe returns a numeric height/cursor that can be compared across local and target endpoints. |
| ton | rest | absolute_gap | absolute_gap | block | numeric_height | implemented | Adapter health probe returns a numeric height/cursor that can be compared across local and target endpoints. |
| tron | jsonrpc | absolute_gap | absolute_gap | block | numeric_height | implemented | Adapter health probe returns a numeric height/cursor that can be compared across local and target endpoints. |
| zksync-era | jsonrpc | conditional_gap | conditional_gap | block | conditional_sync_state | implemented | Health probe uses local eth_syncing. false maps to lag 0; syncing objects map to highestBlock-currentBlock and reuse BLOCK_HEIGHT_DIFF_THRESHOLD. |

## Next Calibration Rules

- Keep `absolute_gap` when the same numeric height/slot/round can be queried from local and target RPC endpoints.
- Use `conditional_gap` only after a chain's local node exposes a reliable highest-known network height or sync object.
- Use `reported_lag` only when the local node directly reports lag in a documented unit.
- Use `freshness_only` for monotonic cursors or liveness signals that are not canonical block heights.
- Continue reusing `BLOCK_HEIGHT_TIME_THRESHOLD` for sustained unhealthy/stale states.
