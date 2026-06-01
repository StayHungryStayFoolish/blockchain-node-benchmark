// Package handlers — jsonrpc family handler.
//
// Covers 16/36 chains: solana, ethereum, bsc, base, polygon, scroll, arbitrum,
//                       optimism, linea, avalanche-c/x, zksync-era, near, tron,
//                       sui, starknet.
//
// Behavior: byte-correct fixture passthrough. The fixture was recorded from a
// real mainnet node, so the response shape is by definition correct for the
// caller (framework's chain_adapters/jsonrpc.py). fake-node does NOT need to
// understand the response — just serve the bytes.
//
// What this handler validates at startup:
//   - chain template has chain_type set
//   - rpc_methods.mixed is a comma-separated method list (framework convention)
//
// What this handler does NOT validate (intentionally):
//   - method-name semantics (eth_* vs getAccountInfo etc.) — the fixture wiring
//     in configs/jsonrpc.yaml decides which fixture serves which method.

package handlers

import (
	"encoding/json"
	"fmt"
	"strings"
)

type JsonRpcHandler struct{}

func init() {
	Register(&JsonRpcHandler{})
}

func (h *JsonRpcHandler) Family() string {
	return "jsonrpc"
}

func (h *JsonRpcHandler) Validate(chainName string, tpl map[string]any) error {
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
		return fmt.Errorf("chain %s: rpc_methods.mixed missing or non-string", chainName)
	}
	parts := strings.Split(mixed, ",")
	if len(parts) == 0 {
		return fmt.Errorf("chain %s: rpc_methods.mixed has no entries", chainName)
	}
	return nil
}

func (h *JsonRpcHandler) Handle(method string, _ json.RawMessage, fixture []byte) ([]byte, error) {
	if len(fixture) == 0 {
		return nil, fmt.Errorf("jsonrpc handler: no fixture wired for method %q", method)
	}
	// Byte-correct passthrough. The fixture is a real recorded JSON-RPC response
	// from the upstream mainnet; serving it verbatim is correct by construction.
	return fixture, nil
}
