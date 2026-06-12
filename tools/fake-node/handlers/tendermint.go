// Package handlers — tendermint family handler.
//
// Covers 5/36 chains: cosmos-hub, osmosis, celestia, injective, sei.
//
// Behavior: byte-correct fixture passthrough on Tendermint RPC requests.
// Tendermint RPC has two equivalent surfaces:
//   - JSON-RPC over POST `/`     (params is OBJECT, not array, e.g. abci_query)
//   - GET path style              (e.g. `/status`, `/abci_info`, `/block`)
//
// The framework's chain_adapters/tendermint.py uses POST JSON-RPC form,
// but the GET shorthand is identical in payload. fake-node serves the same
// recorded mainnet fixture either way — body is identical bytes.

package handlers

import (
	"encoding/json"
	"fmt"
)

type TendermintHandler struct{}

func init() {
	Register(&TendermintHandler{})
}

func (h *TendermintHandler) Family() string {
	return "tendermint"
}

func (h *TendermintHandler) Validate(chainName string, tpl map[string]any) error {
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
	return nil
}

func (h *TendermintHandler) Handle(method string, _ json.RawMessage, fixture []byte) ([]byte, error) {
	if len(fixture) == 0 {
		return nil, fmt.Errorf("tendermint handler: no fixture wired for method %q", method)
	}
	return fixture, nil
}
