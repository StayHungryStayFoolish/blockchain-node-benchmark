// Package handlers — rest family handler (ADR-0005).
//
// Covers 5/36 chains: cardano (ADR-0005 corrected from ogmios), algorand,
// aptos, tezos, ton.
//
// Behavior: byte-correct fixture passthrough on path-routed REST requests.
// `method` passed to Handle() is the logical method NAME from chain template
// (e.g. "GET_TIP", "POST_ADDRESS_INFO") — fake-node's serving layer resolves
// path→fixture file based on rest_paths in the chain template; this handler
// just emits the fixture bytes.
//
// What this handler validates at startup:
//   - chain template has _meta.rest_paths (per ADR-0005 cardano + 4 existing chains)
//   - rpc_methods.mixed is a comma-separated method-NAME list, each name keys into rest_paths.
//
// What this handler does NOT validate (intentionally):
//   - body schema correctness — Koios/Aptos/etc. body shape lives in chain
//     template rest_paths[*].body and is handled by chain_adapters/rest.py:87
//     (ADR-0005 fix). fake-node just serves the recorded fixture.

package handlers

import (
	"encoding/json"
	"fmt"
	"strings"
)

type RestHandler struct{}

func init() {
	Register(&RestHandler{})
}

func (h *RestHandler) Family() string {
	return "rest"
}

func (h *RestHandler) Validate(chainName string, tpl map[string]any) error {
	meta, ok := tpl["_meta"].(map[string]any)
	if !ok {
		return fmt.Errorf("chain %s: _meta missing", chainName)
	}
	rpcMethods, ok := tpl["rpc_methods"].(map[string]any)
	if !ok {
		return fmt.Errorf("chain %s: rpc_methods missing", chainName)
	}
	mixed, ok := rpcMethods["mixed"].(string)
	if !ok || mixed == "" {
		return fmt.Errorf("chain %s: rpc_methods.mixed missing", chainName)
	}
	restPaths, hasPaths := meta["rest_paths"].(map[string]any)
	if !hasPaths || len(restPaths) == 0 {
		// Some rest-family chains carry adapter_family=rest but never had
		// _meta.rest_paths populated (S0 template normalization gap, tracked
		// in OPEN-QUESTIONS as part of step-9 36-chain rollout). Warn — do not
		// fatal — so fake-node startup parity is preserved across the 36-chain
		// matrix and operators can inspect via /stats while the template gap
		// is fixed in the dedicated wave.
		fmt.Printf("WARN: chain %s: _meta.rest_paths missing (template gap — step-9 36-chain rollout will populate)\n", chainName)
		return nil
	}
	// Each method NAME in mixed should key into rest_paths. Missing entries are
	// warn-only (some chains have "known_broken_mixed" methods intentionally,
	// e.g. tezos /operations/{vp} which RestAdapter v1 cannot satisfy — see
	// tezos.json:_meta.known_broken_mixed). These are tracked, not surprises.
	for _, name := range strings.Split(mixed, ",") {
		name = strings.TrimSpace(name)
		if _, present := restPaths[name]; !present {
			fmt.Printf("WARN: chain %s: rpc_methods.mixed entry %q not in _meta.rest_paths (likely known_broken_mixed — see chain template)\n", chainName, name)
		}
	}
	return nil
}

func (h *RestHandler) Handle(method string, _ json.RawMessage, fixture []byte) ([]byte, error) {
	if len(fixture) == 0 {
		return nil, fmt.Errorf("rest handler: no fixture wired for method %q", method)
	}
	return fixture, nil
}
