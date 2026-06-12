package extractor

import (
	"bytes"
	"net/http"
	"testing"
)

// happy path: single json-rpc
func TestJSONRPC_Single(t *testing.T) {
	e, err := NewJSONRPC("test", "^/$", "split")
	if err != nil {
		t.Fatal(err)
	}
	body := []byte(`{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}`)
	req, _ := http.NewRequest("POST", "http://localhost/", bytes.NewReader(body))
	rs, ok := e.Extract(req, body)
	if !ok || len(rs) != 1 {
		t.Fatalf("want 1 result, got ok=%v len=%d", ok, len(rs))
	}
	if rs[0].MethodName != "eth_blockNumber" {
		t.Errorf("method=%q", rs[0].MethodName)
	}
	if rs[0].RequestID != "1" {
		t.Errorf("id=%q", rs[0].RequestID)
	}
}

// happy path: batch json-rpc split
func TestJSONRPC_BatchSplit(t *testing.T) {
	e, _ := NewJSONRPC("test", "^/$", "split")
	body := []byte(`[
		{"jsonrpc":"2.0","method":"eth_blockNumber","id":1},
		{"jsonrpc":"2.0","method":"eth_getBalance","id":2}
	]`)
	req, _ := http.NewRequest("POST", "http://localhost/", bytes.NewReader(body))
	rs, ok := e.Extract(req, body)
	if !ok || len(rs) != 2 {
		t.Fatalf("want 2 results, got ok=%v len=%d", ok, len(rs))
	}
	if rs[0].BatchIdx != 0 || rs[1].BatchIdx != 1 {
		t.Errorf("batch idx wrong: %d %d", rs[0].BatchIdx, rs[1].BatchIdx)
	}
}

func TestJSONRPC_BatchReject(t *testing.T) {
	e, _ := NewJSONRPC("test", "^/$", "reject")
	body := []byte(`[{"method":"x","id":1}]`)
	req, _ := http.NewRequest("POST", "http://localhost/", bytes.NewReader(body))
	if _, ok := e.Extract(req, body); ok {
		t.Errorf("want ok=false for reject mode")
	}
}

func TestJSONRPC_BatchTag(t *testing.T) {
	e, _ := NewJSONRPC("test", "^/$", "tag_batch")
	body := []byte(`[{"method":"x","id":1},{"method":"y","id":2}]`)
	req, _ := http.NewRequest("POST", "http://localhost/", bytes.NewReader(body))
	rs, ok := e.Extract(req, body)
	if !ok || len(rs) != 1 || rs[0].MethodName != "__batch__" {
		t.Errorf("tag_batch failed: ok=%v rs=%+v", ok, rs)
	}
}

// error: URL mismatch
func TestJSONRPC_URLMismatch(t *testing.T) {
	e, _ := NewJSONRPC("test", "^/api/$", "split")
	body := []byte(`{"method":"x","id":1}`)
	req, _ := http.NewRequest("POST", "http://localhost/wrong", bytes.NewReader(body))
	if _, ok := e.Extract(req, body); ok {
		t.Errorf("want ok=false for URL mismatch")
	}
}

// error: empty body
func TestJSONRPC_EmptyBody(t *testing.T) {
	e, _ := NewJSONRPC("test", "^/$", "split")
	req, _ := http.NewRequest("POST", "http://localhost/", nil)
	if _, ok := e.Extract(req, nil); ok {
		t.Errorf("want ok=false for empty body")
	}
}

// error: invalid JSON
func TestJSONRPC_InvalidJSON(t *testing.T) {
	e, _ := NewJSONRPC("test", "^/$", "split")
	body := []byte(`{not json`)
	req, _ := http.NewRequest("POST", "http://localhost/", bytes.NewReader(body))
	if _, ok := e.Extract(req, body); ok {
		t.Errorf("want ok=false for invalid JSON")
	}
}

// happy: REST url_patterns
func TestREST_Match(t *testing.T) {
	e, err := NewREST("test", []map[string]string{
		{"pattern": "^/v2/accounts/[^/]+$", "method_name": "GET /v2/accounts/{address}"},
		{"pattern": "^/v2/blocks/[^/]+$", "method_name": "GET /v2/blocks/{round}"},
	})
	if err != nil {
		t.Fatal(err)
	}
	req, _ := http.NewRequest("GET", "http://localhost/v2/accounts/ABCD", nil)
	rs, ok := e.Extract(req, nil)
	if !ok || len(rs) != 1 || rs[0].MethodName != "GET /v2/accounts/{address}" {
		t.Errorf("rest match fail: ok=%v rs=%+v", ok, rs)
	}
}

// REST: HTTP method prefix filtering
func TestREST_HTTPMethodFilter(t *testing.T) {
	e, _ := NewREST("test", []map[string]string{
		{"pattern": "^/api$", "method_name": "POST /api"},
	})
	// GET should not match a POST-prefixed pattern.
	req, _ := http.NewRequest("GET", "http://localhost/api", nil)
	if _, ok := e.Extract(req, nil); ok {
		t.Errorf("GET should not match POST-prefixed pattern")
	}
	// POST matches.
	req2, _ := http.NewRequest("POST", "http://localhost/api", nil)
	if _, ok := e.Extract(req2, nil); !ok {
		t.Errorf("POST should match POST-prefixed pattern")
	}
}

// REST: no match
func TestREST_NoMatch(t *testing.T) {
	e, _ := NewREST("test", []map[string]string{
		{"pattern": "^/v2/accounts/[^/]+$", "method_name": "x"},
	})
	req, _ := http.NewRequest("GET", "http://localhost/unknown", nil)
	if _, ok := e.Extract(req, nil); ok {
		t.Errorf("want ok=false for unmatched URL")
	}
}

// REST: invalid regex
func TestREST_InvalidRegex(t *testing.T) {
	_, err := NewREST("test", []map[string]string{
		{"pattern": "[invalid", "method_name": "x"},
	})
	if err == nil {
		t.Errorf("want error for invalid regex")
	}
}

// REST: empty url_patterns
func TestREST_EmptyPatterns(t *testing.T) {
	_, err := NewREST("test", []map[string]string{})
	if err == nil {
		t.Errorf("want error for empty url_patterns")
	}
}

// Chain: multiple extractors, REST first, JSON-RPC fallback
func TestChain_HederaDual(t *testing.T) {
	rest, _ := NewREST("rest", []map[string]string{
		{"pattern": "^/api/v1/accounts/[^/]+$", "method_name": "GET_ACCOUNT"},
	})
	jrpc, _ := NewJSONRPC("jrpc", "^/$", "split")
	c := NewChain(rest, jrpc)
	if c.Len() != 2 {
		t.Errorf("len=%d", c.Len())
	}

	// REST matches first.
	req1, _ := http.NewRequest("GET", "http://localhost/api/v1/accounts/0.0.1234", nil)
	rs1, ok := c.Extract(req1, nil)
	if !ok || rs1[0].MethodName != "GET_ACCOUNT" {
		t.Errorf("REST should win: ok=%v rs=%+v", ok, rs1)
	}

	// JSON-RPC fallback
	body := []byte(`{"method":"eth_blockNumber","id":1}`)
	req2, _ := http.NewRequest("POST", "http://localhost/", bytes.NewReader(body))
	rs2, ok := c.Extract(req2, body)
	if !ok || rs2[0].MethodName != "eth_blockNumber" {
		t.Errorf("JSON-RPC fallback should win: ok=%v rs=%+v", ok, rs2)
	}
}

// Chain: all extractors miss
func TestChain_AllMiss(t *testing.T) {
	rest, _ := NewREST("rest", []map[string]string{{"pattern": "^/api$", "method_name": "x"}})
	c := NewChain(rest)
	req, _ := http.NewRequest("GET", "http://localhost/nope", nil)
	if _, ok := c.Extract(req, nil); ok {
		t.Errorf("want ok=false when all extractors miss")
	}
}

// stringifyID coverage
func TestStringifyID(t *testing.T) {
	cases := []struct {
		in   interface{}
		want string
	}{
		{nil, ""},
		{"abc", "abc"},
		{float64(42), "42"},
		{float64(3.14), "3.14"},
		{true, "true"},
	}
	for _, c := range cases {
		got := stringifyID(c.in)
		if got != c.want {
			t.Errorf("stringifyID(%v)=%q want %q", c.in, got, c.want)
		}
	}
}
