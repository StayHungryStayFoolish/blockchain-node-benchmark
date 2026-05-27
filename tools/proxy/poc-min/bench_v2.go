// bench_v2.go — mixed-method weighted workload bench.
//
// v1: 只打 getBalance, ticker QPS
// v2: 按 weight 加权混打多 method, worker-pool 模式 (不限 QPS, 打满 conc)
//
// 用法:
//   go run bench_v2.go \
//     -url http://127.0.0.1:18890 \
//     -dur 60s \
//     -conc 50 \
//     -weights 'getSlot:1,getBalance:1,getLatestBlockhash:1,getBlock:0.1,getTransaction:1'
//
// weight 解释: 按权重选 method, sum = 1 不必,会自动归一化
// 例: 'getBlock:0.1' 意为每 100 个请求只有 ~3 个是 getBlock (因为它 expensive)
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
	"math/rand"
	"net/http"
	"sort"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

type methodSpec struct {
	name   string
	weight float64
	body   []byte
}

func buildBody(method string) []byte {
	// 与 record_fixtures.sh 一致的 params, 简化版
	params := map[string]string{
		"getSlot":            "[]",
		"getBalance":         `["83astBRguLMdt2h5U1Tpdq5tjFoJ6noeGwaY3mDLVcri"]`,
		"getLatestBlockhash": "[]",
		"getBlock":           `[100000000,{"encoding":"json","maxSupportedTransactionVersion":0}]`,
		"getTransaction":     `["5VERv8NMvzbJMEkV8xnrLkEaWRtSz9CosKDYjCJjBRnbJLgp8uirBgmQpjKhoR4tjF3ZpRzrFmBV6UjKdiSZkQUW",{"encoding":"json","maxSupportedTransactionVersion":0}]`,
	}
	p, ok := params[method]
	if !ok {
		p = "[]"
	}
	return []byte(fmt.Sprintf(`{"jsonrpc":"2.0","id":1,"method":"%s","params":%s}`, method, p))
}

func parseWeights(s string) []methodSpec {
	var out []methodSpec
	for _, kv := range strings.Split(s, ",") {
		kv = strings.TrimSpace(kv)
		if kv == "" {
			continue
		}
		parts := strings.SplitN(kv, ":", 2)
		if len(parts) != 2 {
			log.Fatalf("bad weight spec: %s", kv)
		}
		w, err := strconv.ParseFloat(parts[1], 64)
		if err != nil {
			log.Fatalf("bad weight number: %s", parts[1])
		}
		out = append(out, methodSpec{name: parts[0], weight: w, body: buildBody(parts[0])})
	}
	// 归一化 + 累积分布
	var sum float64
	for _, m := range out {
		sum += m.weight
	}
	cumu := 0.0
	for i := range out {
		cumu += out[i].weight / sum
		out[i].weight = cumu // 复用字段存累积概率
	}
	return out
}

func pickMethod(specs []methodSpec, rng *rand.Rand) *methodSpec {
	r := rng.Float64()
	for i := range specs {
		if r <= specs[i].weight {
			return &specs[i]
		}
	}
	return &specs[len(specs)-1]
}

func main() {
	url := flag.String("url", "http://127.0.0.1:18890", "target URL")
	dur := flag.Duration("dur", 60*time.Second, "duration")
	conc := flag.Int("conc", 50, "concurrent workers")
	weightsStr := flag.String("weights", "getSlot:1,getBalance:1,getLatestBlockhash:1,getBlock:0.1,getTransaction:1", "method:weight,...")
	flag.Parse()

	specs := parseWeights(*weightsStr)
	log.Printf("methods (累积分布):")
	for _, s := range specs {
		log.Printf("  %s: cumul=%.3f", s.name, s.weight)
	}

	client := &http.Client{
		Timeout: 30 * time.Second,
		Transport: &http.Transport{
			MaxIdleConns:        *conc * 2,
			MaxIdleConnsPerHost: *conc * 2,
			IdleConnTimeout:     90 * time.Second,
		},
	}

	ctx, cancel := context.WithTimeout(context.Background(), *dur)
	defer cancel()

	type slot struct {
		method  string
		latency time.Duration
		ok      bool
	}
	results := make(chan slot, 1<<20)

	var done int64
	var wg sync.WaitGroup
	for i := 0; i < *conc; i++ {
		wg.Add(1)
		go func(id int) {
			defer wg.Done()
			rng := rand.New(rand.NewSource(int64(id) + time.Now().UnixNano()))
			for {
				select {
				case <-ctx.Done():
					return
				default:
				}
				m := pickMethod(specs, rng)
				start := time.Now()
				req, _ := http.NewRequest("POST", *url, bytes.NewReader(m.body))
				req.Header.Set("Content-Type", "application/json")
				resp, err := client.Do(req)
				lat := time.Since(start)
				ok := false
				if err == nil {
					_, _ = io.Copy(io.Discard, resp.Body)
					_ = resp.Body.Close()
					ok = resp.StatusCode == 200
				}
				results <- slot{method: m.name, latency: lat, ok: ok}
				atomic.AddInt64(&done, 1)
			}
		}(i)
	}

	// progress
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
				log.Printf("progress: done=%d", atomic.LoadInt64(&done))
			}
		}
	}()

	wg.Wait()
	progCancel()
	close(results)

	// 按 method 分组统计
	byMethod := make(map[string][]time.Duration)
	okByMethod := make(map[string]int)
	errByMethod := make(map[string]int)
	for r := range results {
		byMethod[r.method] = append(byMethod[r.method], r.latency)
		if r.ok {
			okByMethod[r.method]++
		} else {
			errByMethod[r.method]++
		}
	}

	pct := func(lats []time.Duration, p float64) time.Duration {
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

	fmt.Println("---- bench_v2 result ----")
	fmt.Printf("dur=%s conc=%d total_done=%d\n", *dur, *conc, done)
	fmt.Printf("actual_qps=%.1f\n", float64(done)/dur.Seconds())
	fmt.Println()
	fmt.Printf("%-22s %8s %8s %8s %10s %10s %10s\n", "method", "count", "ok", "err", "p50", "p95", "p99")
	for _, s := range specs {
		lats := byMethod[s.name]
		sort.Slice(lats, func(i, j int) bool { return lats[i] < lats[j] })
		fmt.Printf("%-22s %8d %8d %8d %10s %10s %10s\n",
			s.name, len(lats), okByMethod[s.name], errByMethod[s.name],
			pct(lats, 0.50), pct(lats, 0.95), pct(lats, 0.99))
	}
}
