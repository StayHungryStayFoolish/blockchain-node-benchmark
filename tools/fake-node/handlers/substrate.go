// Package handlers — substrate family handler.
//
// Covers 5/36 chains: polkadot, kusama, acala, astar, moonbeam.
//
// Behavior: byte-correct fixture passthrough. Substrate JSON-RPC responses
// (`chain_getBlockHash`, `state_getStorage`, `system_chain`, etc.) often
// contain SCALE-encoded hex strings (e.g. `"result":"0x4d3a..."`); the
// upstream framework's chain_adapters/substrate.py is the decoder side. From
// fake-node's perspective, the hex blob is opaque bytes — record once from
// real Polkadot mainnet, replay verbatim.
//
// Why fixture-passthrough is correct:
//   1. The framework (the caller) was designed against real mainnet
//      responses;  serving the same bytes by definition matches.
//   2. SCALE decoding is the framework's problem, not the mock's.
//   3. Hot fields (block_number, finalized_head_hash) are stale by design —
//      benchmarks measure transport / parsing perf, not consensus liveness.

package handlers

import (
	"encoding/json"
	"fmt"
	"strings"
)

type SubstrateHandler struct{}

func init() {
	Register(&SubstrateHandler{})
}

func (h *SubstrateHandler) Family() string {
	return "substrate"
}

func (h *SubstrateHandler) Validate(chainName string, tpl map[string]any) error {
	ct, ok := tpl["chain_type"].(string)
	if !ok || ct == "" {
		return fmt.Errorf("chain %s: chain_type missing or non-string", chainName)
	}
	rpcMethods, ok := tpl["rpc_methods"].(map[string]any)
	if !ok {
		return fmt.Errorf("chain %s: rpc_methods missing", chainName)
	}
	mixed, ok := rpcMethods["mixed"].(string)
	if !ok || mixed == "" {
		return fmt.Errorf("chain %s: rpc_methods.mixed missing", chainName)
	}
	// Substrate methods follow namespace_camelCase (system_*, chain_*, state_*).
	// REST-style "GET /path" entries are handled by REST adapters, so warn
	// instead of failing startup when older templates contain mixed method names.
	for _, m := range strings.Split(mixed, ",") {
		m = strings.TrimSpace(m)
		if !strings.Contains(m, "_") {
			fmt.Printf("WARN: chain %s: method %q does not look like substrate (expected namespace_method) — check chain template adapter routing\n", chainName, m)
		}
	}
	return nil
}

func (h *SubstrateHandler) Handle(method string, _ json.RawMessage, fixture []byte) ([]byte, error) {
	if len(fixture) == 0 {
		return nil, fmt.Errorf("substrate handler: no fixture wired for method %q", method)
	}
	return fixture, nil
}
