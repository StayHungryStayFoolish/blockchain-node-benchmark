// fake-node — a long-lived test fixture that stands in for a real blockchain node.
//
// 用途: framework 集成测试夹具 (NOT a PoC, NOT a benchmark target).
//   每次 framework 改动 (monitor / proxy / analyzer / reporter / chain adapter)
//   都跑一次 framework → fake-node 全链路, 验闭环.
//
// 提供:
//   - JSON-RPC over HTTP, 按 method 返回对应 fixture (byte-correct, 真节点录的)
//   - 非固定频率磁盘 IO worker (随机大小, 随机间隔), 让 monitor 有真 IO 可观察
//   - YAML 驱动: 1 套二进制 + N 个 config = N 链 (Solana / Ethereum / ...)
//
// 不解决:
//   - weight 数值精度 (等真节点)
//   - 真节点性能极限 (等真节点)
//
// 用法:
//   ./fake-node -config configs/solana.yaml -port 19000 -fixtures-dir ./fixtures
//
// 设计: 见 tools/fake-node/README.md

package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"log"
	"math/rand"
	"net/http"
	"os"
	"path/filepath"
	"sync/atomic"
	"time"

	"gopkg.in/yaml.v3"
)

type MethodSpec struct {
	Fixture string `yaml:"fixture"` // fixture filename, relative to fixtures-dir
	Tier    string `yaml:"tier"`    // "cheap" | "mid" | "expensive"
}

type IOSpec struct {
	Enabled      bool   `yaml:"enabled"`
	WorkDir      string `yaml:"work_dir"`        // default /tmp/fake-node-io
	MinBytes     int    `yaml:"min_bytes"`       // default 8 * 1024 (8KB)
	MaxBytes     int    `yaml:"max_bytes"`       // default 1024 * 1024 (1MB)
	MinIntervalMs int   `yaml:"min_interval_ms"` // default 50
	MaxIntervalMs int   `yaml:"max_interval_ms"` // default 500
	ReadRatio    float64 `yaml:"read_ratio"`     // 0.0-1.0, share of cycles doing read instead of write
}

type Config struct {
	Chain   string                 `yaml:"chain"`
	Methods map[string]MethodSpec  `yaml:"methods"`
	Tiers   map[string]string      `yaml:"tiers"` // tier -> duration like "1ms" / "50ms"
	IO      IOSpec                 `yaml:"io"`
}

type rpcReq struct {
	JSONRPC string      `json:"jsonrpc"`
	ID      interface{} `json:"id"`
	Method  string      `json:"method"`
}

// stats counters (atomic, cheap)
var (
	totalRequests atomic.Int64
	totalErrors   atomic.Int64
	ioWrites      atomic.Int64
	ioReads       atomic.Int64
	ioBytesW      atomic.Int64
	ioBytesR      atomic.Int64
)

func loadConfig(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var cfg Config
	if err := yaml.Unmarshal(data, &cfg); err != nil {
		return nil, err
	}
	// defaults
	if cfg.IO.WorkDir == "" {
		cfg.IO.WorkDir = "/tmp/fake-node-io"
	}
	if cfg.IO.MinBytes == 0 {
		cfg.IO.MinBytes = 8 * 1024
	}
	if cfg.IO.MaxBytes == 0 {
		cfg.IO.MaxBytes = 1024 * 1024
	}
	if cfg.IO.MinIntervalMs == 0 {
		cfg.IO.MinIntervalMs = 50
	}
	if cfg.IO.MaxIntervalMs == 0 {
		cfg.IO.MaxIntervalMs = 500
	}
	return &cfg, nil
}

func loadFixtures(cfg *Config, fixturesDir string) (map[string][]byte, error) {
	out := make(map[string][]byte)
	for method, spec := range cfg.Methods {
		path := filepath.Join(fixturesDir, spec.Fixture)
		data, err := os.ReadFile(path)
		if err != nil {
			return nil, fmt.Errorf("load fixture for %s (%s): %w", method, path, err)
		}
		out[method] = data
		log.Printf("  loaded fixture: %s -> %s (%d bytes, tier=%s)", method, spec.Fixture, len(data), spec.Tier)
	}
	return out, nil
}

func parseTiers(raw map[string]string) (map[string]time.Duration, error) {
	out := make(map[string]time.Duration)
	for k, v := range raw {
		d, err := time.ParseDuration(v)
		if err != nil {
			return nil, fmt.Errorf("tier %s: %w", k, err)
		}
		out[k] = d
	}
	return out, nil
}

// runIOWorker performs non-fixed-frequency disk IO until ctx cancellation.
// Goal: give the framework's monitor real IO activity to observe, with
// a non-uniform pattern (random size, random interval) that mimics real
// blockchain node behavior (consensus rounds, ledger compaction, etc.).
func runIOWorker(cfg IOSpec, rng *rand.Rand, stop <-chan struct{}) {
	if !cfg.Enabled {
		log.Printf("io worker: disabled")
		return
	}
	if err := os.MkdirAll(cfg.WorkDir, 0o755); err != nil {
		log.Printf("io worker: mkdir %s failed: %v -- io disabled", cfg.WorkDir, err)
		return
	}
	log.Printf("io worker: dir=%s size=[%d, %d] interval=[%dms, %dms] read_ratio=%.2f",
		cfg.WorkDir, cfg.MinBytes, cfg.MaxBytes, cfg.MinIntervalMs, cfg.MaxIntervalMs, cfg.ReadRatio)

	for {
		// random interval
		intervalMs := cfg.MinIntervalMs + rng.Intn(cfg.MaxIntervalMs-cfg.MinIntervalMs+1)
		select {
		case <-stop:
			return
		case <-time.After(time.Duration(intervalMs) * time.Millisecond):
		}

		// random size
		size := cfg.MinBytes + rng.Intn(cfg.MaxBytes-cfg.MinBytes+1)
		doRead := rng.Float64() < cfg.ReadRatio

		// pick a target file (rotate among 8 to avoid one growing forever)
		fname := filepath.Join(cfg.WorkDir, fmt.Sprintf("io-%d.bin", rng.Intn(8)))

		if doRead {
			data, err := os.ReadFile(fname)
			if err == nil {
				ioReads.Add(1)
				ioBytesR.Add(int64(len(data)))
			}
			// silent on miss (file may not exist yet)
		} else {
			buf := make([]byte, size)
			rng.Read(buf)
			if err := os.WriteFile(fname, buf, 0o644); err != nil {
				log.Printf("io worker: write %s failed: %v", fname, err)
				continue
			}
			ioWrites.Add(1)
			ioBytesW.Add(int64(size))
		}
	}
}

func handleRPC(fixtures map[string][]byte, tiers map[string]time.Duration, methods map[string]MethodSpec) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		body, err := io.ReadAll(r.Body)
		if err != nil {
			http.Error(w, err.Error(), 400)
			totalErrors.Add(1)
			return
		}
		defer r.Body.Close()

		var req rpcReq
		if err := json.Unmarshal(body, &req); err != nil {
			http.Error(w, err.Error(), 400)
			totalErrors.Add(1)
			return
		}

		spec, ok := methods[req.Method]
		if !ok {
			http.Error(w, fmt.Sprintf("unsupported method: %s", req.Method), 404)
			totalErrors.Add(1)
			return
		}

		fixture, ok := fixtures[req.Method]
		if !ok {
			http.Error(w, fmt.Sprintf("no fixture for method: %s", req.Method), 500)
			totalErrors.Add(1)
			return
		}

		// per-tier sleep (simulates node processing time)
		if d, ok := tiers[spec.Tier]; ok {
			time.Sleep(d)
		}

		totalRequests.Add(1)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(200)
		_, _ = w.Write(fixture)
	}
}

func handleStats(w http.ResponseWriter, _ *http.Request) {
	stats := map[string]int64{
		"total_requests": totalRequests.Load(),
		"total_errors":   totalErrors.Load(),
		"io_writes":      ioWrites.Load(),
		"io_reads":       ioReads.Load(),
		"io_bytes_w":     ioBytesW.Load(),
		"io_bytes_r":     ioBytesR.Load(),
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(stats)
}

func main() {
	configPath := flag.String("config", "configs/solana.yaml", "YAML config path")
	fixturesDir := flag.String("fixtures-dir", "./fixtures", "fixtures directory")
	port := flag.String("port", "19000", "listen port")
	flag.Parse()

	cfg, err := loadConfig(*configPath)
	if err != nil {
		log.Fatalf("load config: %v", err)
	}
	log.Printf("fake-node chain=%s methods=%d", cfg.Chain, len(cfg.Methods))

	fixtures, err := loadFixtures(cfg, *fixturesDir)
	if err != nil {
		log.Fatalf("load fixtures: %v", err)
	}

	tiers, err := parseTiers(cfg.Tiers)
	if err != nil {
		log.Fatalf("parse tiers: %v", err)
	}
	for t, d := range tiers {
		log.Printf("  tier %s = %s", t, d)
	}

	stop := make(chan struct{})
	defer close(stop)
	rng := rand.New(rand.NewSource(time.Now().UnixNano()))
	go runIOWorker(cfg.IO, rng, stop)

	mux := http.NewServeMux()
	mux.HandleFunc("/", handleRPC(fixtures, tiers, cfg.Methods))
	mux.HandleFunc("/stats", handleStats)

	srv := &http.Server{Addr: ":" + *port, Handler: mux}
	log.Printf("fake-node listening on :%s (chain=%s)", *port, cfg.Chain)
	log.Fatal(srv.ListenAndServe())
}
