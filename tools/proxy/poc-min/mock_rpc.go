// mock_rpc.go — minimal solana-like JSON-RPC mock server.
// Returns {"jsonrpc":"2.0","id":<id>,"result":1000} for any method.
// Used to isolate PoC measurement to proxy overhead, not real node behavior.
//
// Run: go run mock_rpc.go -port 18899
//
// Part of Q4-8 PoC. See:
//   - docs/architecture/per-method-proxy-architecture-zh.md
//   - analysis-notes/research_notes/07-per-method-resource-attribution-via-proxy.md
//
//go:build ignore

package main

import (
	"encoding/json"
	"flag"
	"io"
	"log"
	"net/http"
)

type rpcReq struct {
	JSONRPC string      `json:"jsonrpc"`
	ID      interface{} `json:"id"`
	Method  string      `json:"method"`
}

type rpcResp struct {
	JSONRPC string      `json:"jsonrpc"`
	ID      interface{} `json:"id"`
	Result  int64       `json:"result"`
}

func main() {
	port := flag.String("port", "18899", "listen port")
	flag.Parse()

	mux := http.NewServeMux()
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		body, err := io.ReadAll(r.Body)
		if err != nil {
			http.Error(w, err.Error(), 400)
			return
		}
		defer r.Body.Close()

		var req rpcReq
		if err := json.Unmarshal(body, &req); err != nil {
			http.Error(w, err.Error(), 400)
			return
		}

		resp := rpcResp{JSONRPC: "2.0", ID: req.ID, Result: 1000}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(resp)
	})

	srv := &http.Server{Addr: ":" + *port, Handler: mux}
	log.Printf("mock_rpc listening on :%s", *port)
	log.Fatal(srv.ListenAndServe())
}
