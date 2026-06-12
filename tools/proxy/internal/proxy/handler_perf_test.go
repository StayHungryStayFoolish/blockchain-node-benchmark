//go:build perf

// Package proxyhandler perf tests require the build tag: go test -tags=perf.
// The race detector skews QPS results, so the performance gate is isolated
// from the default make test path.
package proxyhandler

import (
	"bytes"
	"io"
	"net/http"
	"net/http/httptest"
	"sort"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

// BenchmarkHandler_JSONRPC_Throughput: go test -tags=perf -bench=Throughput ./internal/proxy/
func BenchmarkHandler_JSONRPC_Throughput(b *testing.B) {
	up := fakeUpstream()
	defer up.Close()
	h := buildHandler(b, up.URL)
	srv := httptest.NewServer(h)
	defer srv.Close()

	body := []byte(`{"jsonrpc":"2.0","method":"eth_blockNumber","id":1}`)
	client := &http.Client{
		Timeout:   5 * time.Second,
		Transport: &http.Transport{MaxIdleConnsPerHost: 256, MaxConnsPerHost: 256},
	}
	b.ResetTimer()
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			resp, err := client.Post(srv.URL+"/", "application/json", bytes.NewReader(body))
			if err != nil {
				b.Fatal(err)
			}
			_, _ = io.Copy(io.Discard, resp.Body)
			_ = resp.Body.Close()
		}
	})
}

// TestPerformanceGate rollback threshold: >= 5k QPS @ p99 < 10ms
// Run: go test -tags=perf -run=TestPerformanceGate ./internal/proxy/
// Failures should trigger fallback proxy/extractor review.
func TestPerformanceGate(t *testing.T) {
	up := fakeUpstream()
	defer up.Close()
	h := buildHandler(t, up.URL)
	srv := httptest.NewServer(h)
	defer srv.Close()

	body := []byte(`{"jsonrpc":"2.0","method":"eth_blockNumber","id":1}`)
	const (
		workers   = 32
		duration  = 3 * time.Second
		qpsTarget = 5000.0
		p99Target = 10 * time.Millisecond
	)

	var (
		count atomic.Int64
		latMu sync.Mutex
		lats  = make([]time.Duration, 0, 100_000)
	)
	deadline := time.Now().Add(duration)
	wg := sync.WaitGroup{}
	for i := 0; i < workers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			client := &http.Client{
				Timeout:   5 * time.Second,
				Transport: &http.Transport{MaxIdleConnsPerHost: 32, MaxConnsPerHost: 32},
			}
			for time.Now().Before(deadline) {
				start := time.Now()
				resp, err := client.Post(srv.URL+"/", "application/json", bytes.NewReader(body))
				if err != nil {
					return
				}
				_, _ = io.Copy(io.Discard, resp.Body)
				_ = resp.Body.Close()
				lat := time.Since(start)
				count.Add(1)
				latMu.Lock()
				lats = append(lats, lat)
				latMu.Unlock()
			}
		}()
	}
	wg.Wait()

	total := count.Load()
	qps := float64(total) / duration.Seconds()
	sort.Slice(lats, func(i, j int) bool { return lats[i] < lats[j] })
	p99 := time.Duration(0)
	if len(lats) > 0 {
		p99 = lats[int(float64(len(lats))*0.99)]
	}

	t.Logf("RESULT: total=%d QPS=%.0f p99=%s (target QPS>=%.0f p99<%s)",
		total, qps, p99, qpsTarget, p99Target)

	if qps < qpsTarget {
		t.Errorf("QPS gate FAIL: %.0f < %.0f → trigger envoy fallback (see proxy extractor fallback)", qps, qpsTarget)
	}
	if p99 > p99Target {
		t.Errorf("p99 gate FAIL: %s > %s → trigger envoy fallback (see proxy extractor fallback)", p99, p99Target)
	}
}
