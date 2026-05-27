// Package handlers — NotImplemented stubs for the 5 protocol families not yet
// wired in fake-node v2.
//
// These exist so:
//   1. fake-node binary can be started against ANY of the 36 chains without
//      "unknown family" startup panic — operators can spin it up for inspection.
//   2. RPC calls against unimplemented families fail with a clear error
//      ("adapter_family X not yet implemented") rather than silently passing
//      or returning empty JSON.
//   3. Smoke tests can iterate over all 36 chains and explicitly report which
//      ones fail at the RPC stage vs which ones pass startup but lack handlers.
//
// Coverage map after R1:
//   IMPLEMENTED (20/36 chains):
//     jsonrpc         → 16 chains
//     bitcoin_jsonrpc → 4 chains
//   NOT IMPLEMENTED (16/36 chains, registered as stubs):
//     substrate       → 5 chains (polkadot family)
//     tendermint      → 5 chains (cosmos family)
//     rest            → 4 chains (algorand/aptos/tezos/ton)
//     ogmios          → 1 chain  (cardano)
//     hedera_dual     → 1 chain  (hedera)
//
// Stubs MUST be replaced before staging-environment usage; tracked under
// docs/architecture/OPEN-QUESTIONS.md and the no-deferred-bugs skill.
// They are explicitly NOT a "we'll do it later" defer of a P0 bug — this is
// scope split at design time, with each stub registering as a known gap.

package handlers

func init() {
	for _, fam := range []struct {
		name   string
		reason string
	}{
		{"substrate", "polkadot/kusama family — needs SCALE codec or fixture-passthrough policy decision"},
		{"tendermint", "cosmos family — needs gRPC + REST dual-mode handling"},
		{"rest", "algorand/aptos/tezos/ton — needs per-chain REST path routing"},
		{"ogmios", "cardano — needs websocket fixture replay"},
		{"hedera_dual", "hedera — needs Mirror Node REST + gRPC consensus dual path"},
	} {
		Register(&NotImplementedHandler{FamilyName: fam.name, Reason: fam.reason})
	}
}
