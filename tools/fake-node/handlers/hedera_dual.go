// Package handlers — hedera_dual family handler.
//
// Covers 1/36 chain: hedera.
//
// Hedera is the only dual-protocol chain in the 36-chain set: requests must
// be routed per-method between two upstream surfaces:
//   - Mirror REST (mainnet-public.mirrornode.hedera.com) — path-routed GETs
//   - JSON-RPC Relay (mainnet.hashio.io/api)            — POST + JSON-RPC envelope
//
// The framework's chain_adapters/hedera_dual.py decides which side each method
// goes to based on method-name pattern (eth_* → JSON-RPC, anything else → REST).
// fake-node serves whichever fixture was recorded for that method — no protocol
// switching logic needed at this layer; the fixture file path encodes the side
// (fixtures/hedera/mirror/* vs fixtures/hedera/jsonrpc/*).
//
// Dual-protocol chains need live endpoint smoke coverage in addition to
// schema-only tests, because routing and response envelopes differ by method.

package handlers

import (
	"encoding/json"
	"fmt"
)

type HederaDualHandler struct{}

func init() {
	Register(&HederaDualHandler{})
}

func (h *HederaDualHandler) Family() string {
	return "hedera_dual"
}

func (h *HederaDualHandler) Validate(chainName string, tpl map[string]any) error {
	meta, ok := tpl["_meta"].(map[string]any)
	if !ok {
		return fmt.Errorf("chain %s: _meta missing", chainName)
	}
	// hedera_dual requires both REST path map and JSON-RPC URL declaration.
	if _, ok := meta["rest_paths"]; !ok {
		return fmt.Errorf("chain %s (hedera_dual): _meta.rest_paths missing", chainName)
	}
	if _, ok := meta["json_rpc_url"]; !ok {
		return fmt.Errorf("chain %s (hedera_dual): _meta.json_rpc_url missing (required to route eth_* methods)", chainName)
	}
	return nil
}

func (h *HederaDualHandler) Handle(method string, _ json.RawMessage, fixture []byte) ([]byte, error) {
	if len(fixture) == 0 {
		return nil, fmt.Errorf("hedera_dual handler: no fixture wired for method %q", method)
	}
	return fixture, nil
}
