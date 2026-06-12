package proxyhandler

import (
	"bytes"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"

	"proxy/internal/extractor"
	"proxy/internal/sink"
)

type captureSink struct {
	records []sink.Record
}

func (c *captureSink) Write(r sink.Record) error {
	c.records = append(c.records, r)
	return nil
}

func (c *captureSink) Close() error { return nil }

// fakeUpstream and buildHandler stay in normal builds for reuse by perf tests.
func fakeUpstream() *httptest.Server {
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(200)
		_, _ = w.Write([]byte(`{"jsonrpc":"2.0","result":"0x1","id":1}`))
	}))
}

func fakeUpstreamBody(status int, response string) *httptest.Server {
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(status)
		_, _ = w.Write([]byte(response))
	}))
}

func buildHandler(t testing.TB, up string) *Handler {
	jrpc, err := extractor.NewJSONRPC("jrpc", "^/$", "split")
	if err != nil {
		t.Fatal(err)
	}
	sk, _ := sink.New("discard", "")
	h, err := New(extractor.NewChain(jrpc), sk, up, 1<<20)
	if err != nil {
		t.Fatal(err)
	}
	return h
}

// TestHandler_TransparentForward: proxy must not change status or body.
func TestHandler_TransparentForward(t *testing.T) {
	up := fakeUpstream()
	defer up.Close()
	h := buildHandler(t, up.URL)
	srv := httptest.NewServer(h)
	defer srv.Close()

	body := []byte(`{"jsonrpc":"2.0","method":"eth_blockNumber","id":1}`)
	resp, err := http.Post(srv.URL+"/", "application/json", bytes.NewReader(body))
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		t.Errorf("status=%d", resp.StatusCode)
	}
	got, _ := io.ReadAll(resp.Body)
	if !bytes.Contains(got, []byte(`"result":"0x1"`)) {
		t.Errorf("body lost: %s", got)
	}
}

// TestHandler_Unmatched: unmatched extractor requests should still forward.
func TestHandler_Unmatched(t *testing.T) {
	up := fakeUpstream()
	defer up.Close()
	jrpc, _ := extractor.NewJSONRPC("jrpc", "^/api/$", "split") // only matches /api/
	sk, _ := sink.New("discard", "")
	h, _ := New(extractor.NewChain(jrpc), sk, up.URL, 1<<20)
	srv := httptest.NewServer(h)
	defer srv.Close()

	resp, err := http.Get(srv.URL + "/")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		t.Errorf("unmatched should still forward, got %d", resp.StatusCode)
	}
}

func TestHandler_JSONRPCErrorMarksRPCFailure(t *testing.T) {
	up := fakeUpstreamBody(200, `{"jsonrpc":"2.0","error":{"code":-32602,"message":"Invalid params"},"id":1}`)
	defer up.Close()
	jrpc, _ := extractor.NewJSONRPC("jrpc", "^/$", "split")
	sk := &captureSink{}
	h, _ := New(extractor.NewChain(jrpc), sk, up.URL, 1<<20)
	srv := httptest.NewServer(h)
	defer srv.Close()

	body := []byte(`{"jsonrpc":"2.0","method":"eth_getBalance","params":[],"id":1}`)
	resp, err := http.Post(srv.URL+"/", "application/json", bytes.NewReader(body))
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	_, _ = io.ReadAll(resp.Body)

	if len(sk.records) != 1 {
		t.Fatalf("want 1 sink record, got %d", len(sk.records))
	}
	rec := sk.records[0]
	if !rec.TransportSuccess {
		t.Fatalf("transport should be successful for HTTP 200: %+v", rec)
	}
	if rec.RPCSuccess {
		t.Fatalf("rpc_success should be false for JSON-RPC error: %+v", rec)
	}
	if rec.RPCErrorCode != "-32602" || rec.RPCErrorMessage != "Invalid params" {
		t.Fatalf("unexpected rpc error fields: %+v", rec)
	}
}

func TestHandler_JSONRPCBatchMatchesErrorByID(t *testing.T) {
	up := fakeUpstreamBody(200, `[
		{"jsonrpc":"2.0","result":"0x1","id":"a"},
		{"jsonrpc":"2.0","error":{"code":-32000,"message":"boom"},"id":"b"}
	]`)
	defer up.Close()
	jrpc, _ := extractor.NewJSONRPC("jrpc", "^/$", "split")
	sk := &captureSink{}
	h, _ := New(extractor.NewChain(jrpc), sk, up.URL, 1<<20)
	srv := httptest.NewServer(h)
	defer srv.Close()

	body := []byte(`[
		{"jsonrpc":"2.0","method":"eth_blockNumber","id":"a"},
		{"jsonrpc":"2.0","method":"eth_getBalance","id":"b"}
	]`)
	resp, err := http.Post(srv.URL+"/", "application/json", bytes.NewReader(body))
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	_, _ = io.ReadAll(resp.Body)

	if len(sk.records) != 2 {
		t.Fatalf("want 2 sink records, got %d", len(sk.records))
	}
	if !sk.records[0].RPCSuccess {
		t.Fatalf("first batch item should succeed: %+v", sk.records[0])
	}
	if sk.records[1].RPCSuccess || sk.records[1].RPCErrorCode != "-32000" {
		t.Fatalf("second batch item should fail with mapped error: %+v", sk.records[1])
	}
}
