// proxy.go — minimal JSON-RPC method-extracting reverse proxy.
//
// What it does:
//   1. Listens on -listen (default :18890)
//   2. For each incoming POST:
//      - reads body fully (must to peek method)
//      - extracts top-level "method" field via streaming json decoder
//      - forwards body unchanged to -upstream (default http://127.0.0.1:18899)
//      - appends one CSV row: ts_ns,method,upstream_status,duration_ns
//   3. Passes upstream response back to caller unchanged
//
// CSV format (Q4-9 sink decision):
//   ts_ns,method,status,latency_ns
//
// Run: go run proxy.go -listen :18890 -upstream http://127.0.0.1:18899 -log /tmp/poc_proxy.csv
//
// PoC scope: solana getBalance only (any method actually accepted, no validation).
// NOT in scope: per-method resource attribution, weight, sampling, batched req.
//
//go:build ignore

package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"sync"
	"time"
)

var (
	csvFile *os.File
	csvMu   sync.Mutex
)

func extractMethod(body []byte) string {
	// Streaming decode to find top-level "method" without full unmarshal.
	dec := json.NewDecoder(bytes.NewReader(body))
	// Expect '{'
	tok, err := dec.Token()
	if err != nil {
		return ""
	}
	if d, ok := tok.(json.Delim); !ok || d != '{' {
		return ""
	}
	for dec.More() {
		keyTok, err := dec.Token()
		if err != nil {
			return ""
		}
		key, _ := keyTok.(string)
		if key == "method" {
			valTok, err := dec.Token()
			if err != nil {
				return ""
			}
			if s, ok := valTok.(string); ok {
				return s
			}
			return ""
		}
		// Skip value
		var skip json.RawMessage
		if err := dec.Decode(&skip); err != nil {
			return ""
		}
	}
	return ""
}

func writeCSV(tsNs int64, method string, status int, latencyNs int64) {
	csvMu.Lock()
	defer csvMu.Unlock()
	fmt.Fprintf(csvFile, "%d,%s,%d,%d\n", tsNs, method, status, latencyNs)
}

func main() {
	listen := flag.String("listen", ":18890", "listen address")
	upstream := flag.String("upstream", "http://127.0.0.1:18899", "upstream URL")
	logPath := flag.String("log", "/tmp/poc_proxy.csv", "CSV log path")
	flag.Parse()

	var err error
	csvFile, err = os.Create(*logPath)
	if err != nil {
		log.Fatalf("open csv: %v", err)
	}
	defer csvFile.Close()
	fmt.Fprintln(csvFile, "ts_ns,method,status,latency_ns")

	client := &http.Client{
		Timeout: 10 * time.Second,
		Transport: &http.Transport{
			MaxIdleConns:        2000,
			MaxIdleConnsPerHost: 2000,
			IdleConnTimeout:     90 * time.Second,
		},
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		tsNs := start.UnixNano()

		body, err := io.ReadAll(r.Body)
		if err != nil {
			http.Error(w, err.Error(), 400)
			return
		}
		_ = r.Body.Close()

		method := extractMethod(body)

		req, _ := http.NewRequestWithContext(r.Context(), "POST", *upstream, bytes.NewReader(body))
		req.Header.Set("Content-Type", "application/json")

		resp, err := client.Do(req)
		if err != nil {
			writeCSV(tsNs, method, 0, time.Since(start).Nanoseconds())
			http.Error(w, err.Error(), 502)
			return
		}
		defer resp.Body.Close()

		respBody, _ := io.ReadAll(resp.Body)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(resp.StatusCode)
		_, _ = w.Write(respBody)

		writeCSV(tsNs, method, resp.StatusCode, time.Since(start).Nanoseconds())
	})

	srv := &http.Server{
		Addr:    *listen,
		Handler: mux,
	}
	log.Printf("proxy listening on %s, upstream=%s, log=%s", *listen, *upstream, *logPath)
	log.Fatal(srv.ListenAndServe())
}
