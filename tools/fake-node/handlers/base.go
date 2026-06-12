// Package handlers — per-protocol-family request dispatch for fake-node.
//
// Design rationale: mirrors tools/chain_adapters/ in the framework.
//   Framework's get_adapter(chain_name) reads config/chains/<chain>.json:_meta.adapter_family
//   and looks up an adapter class in a registry. fake-node v2 does the same:
//   each handler registers itself by adapter_family name; main() reads BLOCKCHAIN_NODE
//   env, loads the chain template, extracts adapter_family, and looks up the handler.
//
// The handler registry intentionally mirrors tools/chain_adapters/base.py:
// chain templates select a protocol family with _meta.adapter_family, and both
// the benchmark adapters and fake-node handlers dispatch on that family name.
//
// 36-chain breakdown by adapter_family:
//   jsonrpc          16 chains  (solana, ethereum/bsc/base/polygon/.../arbitrum, sui, starknet, near, tron)
//   substrate         5 chains  (polkadot, kusama, acala, astar, moonbeam)
//   tendermint        5 chains  (cosmos-hub, osmosis, celestia, injective, sei)
//   rest              4 chains  (algorand, aptos, tezos, ton)
//   bitcoin_jsonrpc   4 chains  (bitcoin, bch, dogecoin, litecoin)
//   ogmios            1 chain   (cardano)
//   hedera_dual       1 chain   (hedera)

package handlers

import (
	"encoding/json"
	"fmt"
)

// Handler is the per-family request processor.
//
// Each protocol family (jsonrpc, substrate, tendermint, ...) implements this.
// fake-node's main() picks the right handler from the registry based on the
// chain template's _meta.adapter_family field.
type Handler interface {
	// Family returns the adapter_family name (e.g. "jsonrpc"). Must match
	// _meta.adapter_family in config/chains/*.json.
	Family() string

	// Validate is called once at startup per chain. It checks the chain template
	// matches what this handler expects (e.g. JSON-RPC handler requires methods
	// to be JSON-RPC-style names). Return error to fail fast at startup.
	Validate(chainName string, chainTemplate map[string]any) error

	// Handle processes a single RPC request. `method` is the JSON-RPC method
	// (or REST path, or whatever the family uses). `fixture` is the pre-loaded
	// byte-correct response from fixtures/<chain>/<method>.json. The handler
	// may transform or pass through.
	//
	// For most families (jsonrpc, bitcoin_jsonrpc, ...) this is a byte-correct
	// passthrough of `fixture`. Substrate / REST / Ogmios may need light shaping.
	Handle(method string, params json.RawMessage, fixture []byte) ([]byte, error)
}

// _REGISTRY mirrors chain_adapters/base.py:107.
// Populated by handlers via Register() in their package init().
var _REGISTRY = map[string]Handler{}

// Register adds a handler to the registry. Call from package init() of each
// handler implementation. Duplicate family names panic at init time (fail fast).
func Register(h Handler) {
	family := h.Family()
	if _, dup := _REGISTRY[family]; dup {
		panic(fmt.Sprintf("handler family %q registered twice", family))
	}
	_REGISTRY[family] = h
}

// Get returns the handler for the given adapter_family, or error if unknown.
// Mirrors get_adapter() in chain_adapters/base.py:119.
func Get(family string) (Handler, error) {
	h, ok := _REGISTRY[family]
	if !ok {
		registered := make([]string, 0, len(_REGISTRY))
		for k := range _REGISTRY {
			registered = append(registered, k)
		}
		return nil, fmt.Errorf("unknown adapter_family %q (registered: %v)", family, registered)
	}
	return h, nil
}

// List returns all registered family names (for debugging / startup logging).
func List() []string {
	out := make([]string, 0, len(_REGISTRY))
	for k := range _REGISTRY {
		out = append(out, k)
	}
	return out
}

// NotImplementedHandler is a stub handler for protocol families we have not
// yet implemented. It registers and validates successfully, but Handle()
// returns a clear error so the smoke test fails loudly (NOT silently passes).
//
// Use case: at v2 ship time we cover jsonrpc + bitcoin_jsonrpc (20/36 chains).
// The remaining 5 families (substrate, tendermint, rest, ogmios, hedera_dual)
// register NotImplementedHandler stubs so:
//   - fake-node binary supports all 36 chains for *startup*
//   - any RPC call against an unimplemented family fails with a clear message
//   - smoke / CI flags the gap explicitly instead of mysteriously passing
type NotImplementedHandler struct {
	FamilyName string
	Reason     string
}

func (n *NotImplementedHandler) Family() string {
	return n.FamilyName
}

func (n *NotImplementedHandler) Validate(chainName string, _ map[string]any) error {
	// Allow startup so operators can spin up fake-node for a stub family
	// for inspection / debugging. Real RPC calls will still error.
	return nil
}

func (n *NotImplementedHandler) Handle(method string, _ json.RawMessage, _ []byte) ([]byte, error) {
	return nil, fmt.Errorf("adapter_family %q not yet implemented in fake-node v2 (method=%s, reason=%s)",
		n.FamilyName, method, n.Reason)
}
