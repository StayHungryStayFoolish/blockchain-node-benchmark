// Package handlers — bitcoin_jsonrpc family handler.
//
// Covers 4/36 chains: bitcoin, bch, dogecoin, litecoin.
//
// Why separate from jsonrpc:
//   - Bitcoin JSON-RPC uses HTTP Basic Auth (rpcuser:rpcpassword) per node convention.
//     fake-node accepts the Authorization header but does not validate it
//     (we are not a real node; we are a fixture server).
//   - Bitcoin RPC method names are lowercase (getblockcount, getrawtransaction)
//     unlike Ethereum (eth_*) or Solana (camelCase getAccountInfo).
//   - Bitcoin responses always wrap in {"result":..., "error":..., "id":...}
//     with explicit error field, unlike Ethereum which uses HTTP 200 + result-only
//     for success.
//
// For fake-node's purposes (fixture passthrough) the family is functionally
// identical to jsonrpc. The separation exists so framework chain_adapters/
// can distinguish them and apply auth-header logic in real-node mode.

package handlers

import (
	"encoding/json"
	"fmt"
)

type BitcoinJsonRpcHandler struct{}

func init() {
	Register(&BitcoinJsonRpcHandler{})
}

func (h *BitcoinJsonRpcHandler) Family() string {
	return "bitcoin_jsonrpc"
}

func (h *BitcoinJsonRpcHandler) Validate(chainName string, tpl map[string]any) error {
	ct, ok := tpl["chain_type"].(string)
	if !ok || ct == "" {
		return fmt.Errorf("chain %s: chain_type missing", chainName)
	}
	return nil
}

func (h *BitcoinJsonRpcHandler) Handle(method string, _ json.RawMessage, fixture []byte) ([]byte, error) {
	if len(fixture) == 0 {
		return nil, fmt.Errorf("bitcoin_jsonrpc handler: no fixture wired for method %q", method)
	}
	return fixture, nil
}
