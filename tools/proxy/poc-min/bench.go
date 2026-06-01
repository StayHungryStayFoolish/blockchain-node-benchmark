// bench.go — minimal concurrent JSON-RPC client.
//
// Targets a fixed QPS for a fixed duration, reports p50/p95/p99 + error count.
//
// Run: go run bench.go -url http://127.0.0.1:18890 -qps 10000 -dur 30s -conc 200
//
//go:build ignore

package main

import (
	"bytes"
	"context"
	"flag"
	"fmt"
	"io"
	"log"
	"net/http"
	"sort"
	"sync"
	"sync/atomic"
	"time"
)

const reqBody = `{"jsonrpc":"2.0","id":1,"method":"getBalance","params":["83astBRguLMdt2h5U1Tpdq5tjFoJ6noeGwaY3mDLVcri"]}`

func main() {
	url := flag.String("url", "http://127.0.0.1:18890", "target URL")
	qps := flag.Int("qps", 10000, "target QPS")
	dur := flag.Duration("dur", 30*time.Second, "duration")
	conc := flag.Int("conc", 200, "concurrent workers")
	flag.Parse()

	client := &http.Client{
		Timeout: 5 * time.Second,
		Transport: &http.Transport{
			MaxIdleConns:        *conc * 2,
			MaxIdleConnsPerHost: *conc * 2,
			IdleConnTimeout:     90 * time.Second,
		},
	}

	ctx, cancel := context.WithTimeout(context.Background(), *dur)
	defer cancel()

	// QPS ticker: 1 / qps interval. For 10k qps that's 100us.
	interval := time.Second / time.Duration(*qps)

	type slot struct {
		latency time.Duration
		ok      bool
	}
	results := make(chan slot, *qps*int(dur.Seconds())+1000)

	var sent int64
	var done int64

	// Job channel: producer ticks at QPS, workers consume.
	jobs := make(chan struct{}, 1024)

	var wg sync.WaitGroup
	for i := 0; i < *conc; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for range jobs {
				start := time.Now()
				req, _ := http.NewRequest("POST", *url, bytes.NewReader([]byte(reqBody)))
				req.Header.Set("Content-Type", "application/json")
				resp, err := client.Do(req)
				lat := time.Since(start)
				ok := false
				if err == nil {
					_, _ = io.Copy(io.Discard, resp.Body)
					_ = resp.Body.Close()
					ok = resp.StatusCode == 200
				}
				results <- slot{latency: lat, ok: ok}
				atomic.AddInt64(&done, 1)
			}
		}()
	}

	// Producer
	go func() {
		t := time.NewTicker(interval)
		defer t.Stop()
		for {
			select {
			case <-ctx.Done():
				close(jobs)
				return
			case <-t.C:
				select {
				case jobs <- struct{}{}:
					atomic.AddInt64(&sent, 1)
				default:
					// drop if workers can't keep up
				}
			}
		}
	}()

	// Progress
	progCtx, progCancel := context.WithCancel(context.Background())
	defer progCancel()
	go func() {
		t := time.NewTicker(5 * time.Second)
		defer t.Stop()
		for {
			select {
			case <-progCtx.Done():
				return
			case <-t.C:
				log.Printf("progress: sent=%d done=%d", atomic.LoadInt64(&sent), atomic.LoadInt64(&done))
			}
		}
	}()

	wg.Wait()
	progCancel()
	close(results)

	var lats []time.Duration
	var okCount, errCount int
	for r := range results {
		lats = append(lats, r.latency)
		if r.ok {
			okCount++
		} else {
			errCount++
		}
	}
	sort.Slice(lats, func(i, j int) bool { return lats[i] < lats[j] })

	pct := func(p float64) time.Duration {
		if len(lats) == 0 {
			return 0
		}
		i := int(float64(len(lats))*p) - 1
		if i < 0 {
			i = 0
		}
		if i >= len(lats) {
			i = len(lats) - 1
		}
		return lats[i]
	}

	fmt.Println("---- bench result ----")
	fmt.Printf("target_qps=%d duration=%s conc=%d\n", *qps, *dur, *conc)
	fmt.Printf("sent=%d done=%d ok=%d err=%d\n", sent, done, okCount, errCount)
	fmt.Printf("actual_qps=%.1f\n", float64(done)/dur.Seconds())
	fmt.Printf("p50=%s p95=%s p99=%s p999=%s max=%s\n",
		pct(0.50), pct(0.95), pct(0.99), pct(0.999), pct(1.0))
}
