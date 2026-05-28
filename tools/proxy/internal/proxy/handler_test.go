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

// fakeUpstream / buildHandler 都在 normal build,供 perf 子文件复用。
func fakeUpstream() *httptest.Server {
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(200)
		_, _ = w.Write([]byte(`{"jsonrpc":"2.0","result":"0x1","id":1}`))
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

// TestHandler_TransparentForward: proxy 不应改 status / body
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

// TestHandler_Unmatched: extractor 没匹配也不该挂请求
func TestHandler_Unmatched(t *testing.T) {
	up := fakeUpstream()
	defer up.Close()
	jrpc, _ := extractor.NewJSONRPC("jrpc", "^/api/$", "split") // 只匹配 /api/
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
