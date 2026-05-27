// fake-node v2 — long-lived test fixture standing in for a real blockchain node.
//
// v2 改动 (2026-05-27, R1 — 范式纠正):
//   v1 范式 (单文件单链, configs/<chain>.yaml 全配, 自创"零代码加链"声明)
//     与 framework 既有 chain_type/_meta.adapter_family switch 约定不一致。
//     用户质问: "BLOCKCHAIN_NODE 变量存在, fake-node 难道不能 switch case?
//                36 链本身就不是完全相同, 怎么可能一个 fake-node 复用?"
//   v2 范式: BLOCKCHAIN_NODE env → config/chains/<x>.json → _meta.adapter_family
//            → handlers/<family>.go (switch-case via registry),
//            与 framework chain_adapters/get_adapter() 同构。
//
// GREP-EVIDENCE (per parallel-entry-trap skill, loaded-but-violated gate):
//   - config/config_loader.sh:17     BLOCKCHAIN_NODE env (default solana, lowercased)
//   - tools/chain_adapters/base.py:107 _REGISTRY: dict[family → AdapterClass]
//   - tools/chain_adapters/base.py:126 family = tpl["_meta"]["adapter_family"]
//   - config/chains/*.json _meta.adapter_family 7 families covering 36 chains
//
// 加链工作量诚实矩阵 (取代 v1 的"零代码加链"绝对声明):
//   | 场景                                 | Go 改动            | 配置改动             |
//   |--------------------------------------|--------------------|----------------------|
//   | 已实现协议族新成员 (如 + 新 EVM 链) | 0                  | +1 config/chains JSON|
//   | 协议族内特殊调优                     | 0                  | +1 fake-node YAML    |
//   | 全新协议族 (5/7 仍 stub)             | +1 handler ~200 行 | +1 family YAML       |
//   与 framework chain_adapters/<family>.py 工作量对称.

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
	"strings"
	"sync/atomic"
	"time"

	"gopkg.in/yaml.v3"

	"fake-node/handlers"
)

// ---- YAML config (per-family handler tunables) ----

type MethodSpec struct {
	Fixture string `yaml:"fixture"` // fixture filename, relative to fixtures-dir/<chain>/
	Tier    string `yaml:"tier"`    // "cheap" | "mid" | "expensive"
}

type IOSpec struct {
	Enabled       bool    `yaml:"enabled"`
	WorkDir       string  `yaml:"work_dir"`
	MinBytes      int     `yaml:"min_bytes"`
	MaxBytes      int     `yaml:"max_bytes"`
	MinIntervalMs int     `yaml:"min_interval_ms"`
	MaxIntervalMs int     `yaml:"max_interval_ms"`
	ReadRatio     float64 `yaml:"read_ratio"`
}

type Config struct {
	Family  string                `yaml:"family"`  // must match handler.Family()
	Methods map[string]MethodSpec `yaml:"methods"` // method_name → fixture + tier
	Tiers   map[string]string     `yaml:"tiers"`   // tier → duration "1ms" / "50ms"
	IO      IOSpec                `yaml:"io"`
}

// ---- Chain template (config/chains/<chain>.json — framework's source of truth) ----

type chainTemplate map[string]any

func loadChainTemplate(chainsDir, chain string) (chainTemplate, string, error) {
	path := filepath.Join(chainsDir, chain+".json")
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, "", fmt.Errorf("read chain template %s: %w", path, err)
	}
	var tpl chainTemplate
	if err := json.Unmarshal(data, &tpl); err != nil {
		return nil, "", fmt.Errorf("parse chain template %s: %w", path, err)
	}
	meta, ok := tpl["_meta"].(map[string]any)
	if !ok {
		return nil, "", fmt.Errorf("chain %s: _meta missing", chain)
	}
	family, ok := meta["adapter_family"].(string)
	if !ok || family == "" {
		return nil, "", fmt.Errorf("chain %s: _meta.adapter_family missing", chain)
	}
	return tpl, family, nil
}

// ---- YAML loading ----

func loadConfig(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var cfg Config
	if err := yaml.Unmarshal(data, &cfg); err != nil {
		return nil, err
	}
	// IO defaults
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

// loadFixtures loads fixture bytes per method. The family yaml lists the UNION
// of methods used across the family — a single chain typically uses a subset.
// Missing fixtures are warned (not fatal) so a chain's fixtures dir only needs
// the methods it actually uses. RPC calls to a method with no fixture return
// 404 at request time.
func loadFixtures(cfg *Config, fixturesDir, chain string) (map[string][]byte, error) {
	out := make(map[string][]byte)
	chainDir := filepath.Join(fixturesDir, chain)
	loaded, missing := 0, 0
	for method, spec := range cfg.Methods {
		path := filepath.Join(chainDir, spec.Fixture)
		data, err := os.ReadFile(path)
		if err != nil {
			if os.IsNotExist(err) {
				log.Printf("  fixture missing (skipped): %s/%s (method %s will 404)", chain, spec.Fixture, method)
				missing++
				continue
			}
			return nil, fmt.Errorf("load fixture for %s (%s): %w", method, path, err)
		}
		out[method] = data
		log.Printf("  loaded fixture: %s -> %s (%d bytes, tier=%s)", method, spec.Fixture, len(data), spec.Tier)
		loaded++
	}
	log.Printf("loadFixtures: chain=%s loaded=%d missing=%d", chain, loaded, missing)
	if loaded == 0 {
		// NOT fatal — allow stub families (NotImplementedHandler) and chains-with-no-fixtures-yet
		// to start. All RPC calls will 404 at request time. This is intentional: loud failure
		// at request time is better than silent stub-with-no-coverage passing as healthy.
		log.Printf("loadFixtures: WARNING chain=%s has zero fixtures; ALL RPC calls will 404", chain)
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

// ---- stats counters ----

var (
	totalRequests atomic.Int64
	totalErrors   atomic.Int64
	ioWrites      atomic.Int64
	ioReads       atomic.Int64
	ioBytesW      atomic.Int64
	ioBytesR      atomic.Int64
)

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
		intervalMs := cfg.MinIntervalMs + rng.Intn(cfg.MaxIntervalMs-cfg.MinIntervalMs+1)
		select {
		case <-stop:
			return
		case <-time.After(time.Duration(intervalMs) * time.Millisecond):
		}
		size := cfg.MinBytes + rng.Intn(cfg.MaxBytes-cfg.MinBytes+1)
		doRead := rng.Float64() < cfg.ReadRatio
		fname := filepath.Join(cfg.WorkDir, fmt.Sprintf("io-%d.bin", rng.Intn(8)))

		if doRead {
			data, err := os.ReadFile(fname)
			if err == nil {
				ioReads.Add(1)
				ioBytesR.Add(int64(len(data)))
			}
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

type rpcReq struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      interface{}     `json:"id"`
	Method  string          `json:"method"`
	Params  json.RawMessage `json:"params"`
}

func handleRPC(handler handlers.Handler, fixtures map[string][]byte, tiers map[string]time.Duration, methods map[string]MethodSpec) http.HandlerFunc {
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

		fixture, hasFixture := fixtures[req.Method]
		if !hasFixture {
			http.Error(w, fmt.Sprintf("method %s declared but no fixture loaded for this chain", req.Method), 404)
			totalErrors.Add(1)
			return
		}

		// Per-tier sleep (simulates node processing time)
		if d, ok := tiers[spec.Tier]; ok {
			time.Sleep(d)
		}

		// Dispatch to handler — this is the v2 switch-case point.
		resp, err := handler.Handle(req.Method, req.Params, fixture)
		if err != nil {
			http.Error(w, err.Error(), 500)
			totalErrors.Add(1)
			return
		}

		totalRequests.Add(1)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(200)
		_, _ = w.Write(resp)
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

func resolveChain(flagChain string) string {
	if flagChain != "" {
		return strings.ToLower(strings.TrimSpace(flagChain))
	}
	if env := os.Getenv("BLOCKCHAIN_NODE"); env != "" {
		// Mirror config_loader.sh:20 — lowercase to match framework convention.
		return strings.ToLower(strings.TrimSpace(env))
	}
	return "solana" // mirror config_loader.sh:17 default
}

func main() {
	chainFlag := flag.String("chain", "", "chain name (overrides BLOCKCHAIN_NODE env; default: solana)")
	chainsDir := flag.String("chains-dir", "../../config/chains", "directory of chain template JSONs")
	configsDir := flag.String("configs-dir", "configs", "directory of per-family fake-node YAML configs")
	fixturesDir := flag.String("fixtures-dir", "./fixtures", "fixtures root (per-chain subdirs)")
	port := flag.String("port", "19000", "listen port")
	flag.Parse()

	chain := resolveChain(*chainFlag)
	log.Printf("fake-node v2 starting: chain=%s (resolution: flag=%q env=%q)",
		chain, *chainFlag, os.Getenv("BLOCKCHAIN_NODE"))
	log.Printf("registered handlers: %v", handlers.List())

	// Load chain template → extract adapter_family.
	tpl, family, err := loadChainTemplate(*chainsDir, chain)
	if err != nil {
		log.Fatalf("load chain template: %v", err)
	}
	log.Printf("chain %s → adapter_family=%s", chain, family)

	// Get the handler for this family (or fail loudly).
	handler, err := handlers.Get(family)
	if err != nil {
		log.Fatalf("dispatch: %v", err)
	}

	// Per-handler startup validation against the chain template.
	if err := handler.Validate(chain, tpl); err != nil {
		log.Fatalf("handler %s validate(%s): %v", family, chain, err)
	}

	// Load per-family YAML config for fixtures wiring + IO + tiers.
	cfgPath := filepath.Join(*configsDir, family+".yaml")
	cfg, err := loadConfig(cfgPath)
	if err != nil {
		log.Fatalf("load config %s: %v", cfgPath, err)
	}
	if cfg.Family != "" && cfg.Family != family {
		log.Fatalf("config family mismatch: yaml says %q but chain dispatches %q", cfg.Family, family)
	}
	log.Printf("config %s: %d methods, family=%s", cfgPath, len(cfg.Methods), family)

	fixtures, err := loadFixtures(cfg, *fixturesDir, chain)
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
	mux.HandleFunc("/", handleRPC(handler, fixtures, tiers, cfg.Methods))
	mux.HandleFunc("/stats", handleStats)

	srv := &http.Server{Addr: ":" + *port, Handler: mux}
	log.Printf("fake-node v2 listening on :%s (chain=%s family=%s)", *port, chain, family)
	log.Fatal(srv.ListenAndServe())
}
