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
	"runtime"
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

// buildMethodsFromChainTemplate 是乙方案(2026-06-05 用户拍板)的核心:
// fake-node 的 method 列表【单一真相源 = config/chains/<chain>.json 的 rpc_methods】,
// 不再用 family yaml 的 methods 段(那是 parallel-entry 漂移源 — yaml 与 config 各自维护,
// 实测漂移 89 个 method: config 配了但 yaml 没声明 → fake-node mixed 打过去 404)。
//
// 规则:
//   - method 列表 = rpc_methods.single + rpc_methods.mixed_weighted[].method(去重)
//   - fixture 文件名 = 双转换规则(与 ci/check_fixture_coverage.py fixture_name() 一致):
//       带 HTTP 动词前缀(含空格, 如 "GET /v2/x")→ 空格→_ 且 /→_  ("GET__v2_x")
//       以 / 开头无动词(如 "/status")→ /→_ 去前导_  ("status")
//       否则原样(eth_getBalance / system_account)
//   - tier = yaml 若声明了该 method 则取其 tier, 否则默认 "mid"(yaml 降级为可选 tier 微调源)
func fixtureNameFromMethod(method string) string {
	if strings.Contains(method, " ") {
		// 带 HTTP 动词前缀: "GET /v2/x" → "GET__v2_x"
		return strings.ReplaceAll(strings.ReplaceAll(method, " ", "_"), "/", "_") + ".json"
	}
	// "/status" → "status" ; "eth_getBalance"/"system_account" 原样
	return strings.TrimPrefix(strings.ReplaceAll(method, "/", "_"), "_") + ".json"
}

func buildMethodsFromChainTemplate(tpl chainTemplate, yamlMethods map[string]MethodSpec) (map[string]MethodSpec, error) {
	rm, ok := tpl["rpc_methods"].(map[string]any)
	if !ok {
		return nil, fmt.Errorf("chain template: rpc_methods missing or not an object")
	}
	out := make(map[string]MethodSpec)
	add := func(method string) {
		if method == "" {
			return
		}
		if _, exists := out[method]; exists {
			return
		}
		tier := "mid" // default; yaml 可微调
		if ys, ok := yamlMethods[method]; ok && ys.Tier != "" {
			tier = ys.Tier
		}
		out[method] = MethodSpec{Fixture: fixtureNameFromMethod(method), Tier: tier}
	}
	// single
	if s, ok := rm["single"].(string); ok {
		add(s)
	}
	// mixed_weighted[].method
	if mw, ok := rm["mixed_weighted"].([]any); ok {
		for _, item := range mw {
			if m, ok := item.(map[string]any); ok {
				if name, ok := m["method"].(string); ok {
					add(name)
				}
			}
		}
	}
	if len(out) == 0 {
		return nil, fmt.Errorf("chain template rpc_methods produced 0 methods (single+mixed_weighted both empty?)")
	}
	return out, nil
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
func loadFixtures(methods map[string]MethodSpec, fixturesDir, chain string) (map[string][]byte, error) {
	out := make(map[string][]byte)
	chainDir := filepath.Join(fixturesDir, chain)
	loaded, missing := 0, 0
	for method, spec := range methods {
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
		// Two dispatch modes:
		//   1. JSON-RPC envelope (default): POST body has {"method": "..."},
		//      used by jsonrpc / bitcoin_jsonrpc / substrate / tendermint(POST) /
		//      hedera_dual(eth_* methods)
		//   2. Path-based: URL is something other than just "/", and the path
		//      (or first segment) is the method NAME, used by rest / tendermint(GET) /
		//      hedera_dual(REST/Mirror side, paths under /api/v1/...).
		//
		// ADR-0005 (2026-05-28): Path-based mode was added to support 4 new
		// adapter families (rest/substrate/tendermint/hedera_dual). Without it,
		// fake-node v2 could only serve jsonrpc envelope traffic, which made
		// ~20/36 chains unreachable.

		var method string
		var params json.RawMessage

		if isPathBasedRequest(r) {
			m, ok := resolvePathMethod(r, methods)
			if !ok {
				http.Error(w, fmt.Sprintf("path-based dispatch: no method matches URL %q (declared methods: %d)", r.URL.Path, len(methods)), 404)
				totalErrors.Add(1)
				return
			}
			method = m
			// Read body (may be empty for GET, may be JSON for POST) — passed
			// to handler.Handle() opaquely.
			body, err := io.ReadAll(r.Body)
			if err != nil {
				http.Error(w, err.Error(), 400)
				totalErrors.Add(1)
				return
			}
			defer r.Body.Close()
			params = json.RawMessage(body)
		} else {
			// JSON-RPC envelope mode
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
			method = req.Method
			params = req.Params
		}

		spec, ok := methods[method]
		if !ok {
			http.Error(w, fmt.Sprintf("unsupported method: %s", method), 404)
			totalErrors.Add(1)
			return
		}

		fixture, hasFixture := fixtures[method]
		if !hasFixture {
			http.Error(w, fmt.Sprintf("method %s declared but no fixture loaded for this chain", method), 404)
			totalErrors.Add(1)
			return
		}

		// Per-tier sleep (simulates node processing time)
		if d, ok := tiers[spec.Tier]; ok {
			time.Sleep(d)
		}

		// Dispatch to handler — this is the v2 switch-case point.
		resp, err := handler.Handle(method, params, fixture)
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

// isPathBasedRequest returns true if the URL path is non-trivial (not "/"),
// indicating a path-routed REST/path-style request rather than JSON-RPC envelope.
func isPathBasedRequest(r *http.Request) bool {
	p := strings.TrimSpace(r.URL.Path)
	return p != "" && p != "/"
}

// resolvePathMethod maps the request URL to a declared method NAME.
// Strategy (cheapest first):
//   1. Exact match: r.URL.Path == declared method's path component
//   2. Substring match: any declared method whose path-fragment appears in URL
//   3. Verb+path match for METHOD-style names (e.g. "GET_TIP" matches GET /tip)
//
// For path-based REST families we expect each method NAME in configs/<family>.yaml
// to be either:
//   - "VERB_RESOURCE" (e.g. "GET_TIP", "POST_ADDRESS_INFO") — match on RESOURCE
//     against URL path's last segment
//   - or matches the fixture-derived natural method (e.g. "status" → /status)
//
// This is a tolerant matcher because chain templates use 3 different naming
// styles historically (REST verb-path, JSON-RPC namespace_method, plain word).
func resolvePathMethod(r *http.Request, methods map[string]MethodSpec) (string, bool) {
	urlPath := strings.ToLower(strings.TrimPrefix(r.URL.Path, "/"))
	// Strip query string
	if i := strings.Index(urlPath, "?"); i >= 0 {
		urlPath = urlPath[:i]
	}
	// Try exact match against method names that ARE paths (e.g. "status", "abci_info").
	for m := range methods {
		if strings.EqualFold(m, urlPath) {
			return m, true
		}
	}
	// Try VERB_NAME style: split "GET_TIP" → verb=GET, name=tip, match if url ends with /tip.
	for m := range methods {
		parts := strings.SplitN(m, "_", 2)
		if len(parts) == 2 {
			verb := strings.ToUpper(parts[0])
			name := strings.ToLower(parts[1])
			if (verb == "GET" || verb == "POST") && (urlPath == name || strings.HasSuffix(urlPath, "/"+name)) {
				if verb == r.Method {
					return m, true
				}
			}
		}
	}
	// Try last-segment match: "/api/v1/network/nodes" → suffix "nodes" matches "GET_NETWORK_NODES"?
	segments := strings.Split(urlPath, "/")
	lastSeg := segments[len(segments)-1]
	for m := range methods {
		mLower := strings.ToLower(m)
		if strings.HasSuffix(mLower, "_"+lastSeg) || strings.Contains(mLower, lastSeg) {
			return m, true
		}
	}
	return "", false
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

// ---- default path resolution (binary-location-aware) ----
//
// 默认 flag 值需要满足两类用例:
//   (a) 从源目录 (tools/fake-node/) `go run` 或 `./fake-node` — 历史用法,
//       相对路径 "../../config/chains" / "configs" / "./fixtures" 即可工作。
//   (b) Binary 被 cp 或 build -o 到任意目录 (如 /tmp/fake-node-v2) 后启动 —
//       cwd 不再是源目录,相对路径会 fail。
//
// 解决策略 (优先级从高到低):
//   1. runtime.Caller(0) — go 编译时把源文件绝对路径嵌入 binary。只要源仓库
//      还在原位,无论 binary 跑哪儿都能找到资源。对 (b) 用例是主路径。
//   2. os.Executable() — binary 自身位置,适用于"binary 和资源同目录部署"
//      场景 (e.g. 容器/打包发行)。检测到资源相对 binary dir 存在则用之。
//   3. 相对路径 fallback — 兼容 (a) 用例 + `go run` (临时 build dir 下
//      runtime.Caller 仍返回源路径,但保险起见保留)。
//
// 任一 helper 失败 (e.g. runtime.Caller 不可用),自动降级到下一级。

// sourceDir 返回 fake_node.go 所在目录的绝对路径 (编译时嵌入)。
// 若 runtime.Caller 失败或路径不再存在,返回空串。
func sourceDir() string {
	_, file, _, ok := runtime.Caller(0)
	if !ok || file == "" {
		return ""
	}
	dir := filepath.Dir(file)
	if _, err := os.Stat(dir); err != nil {
		return "" // 源目录已移动/删除
	}
	return dir
}

// executableDir 返回当前 binary 所在目录的绝对路径。
// 失败返回空串。
func executableDir() string {
	exe, err := os.Executable()
	if err != nil {
		return ""
	}
	resolved, err := filepath.EvalSymlinks(exe)
	if err != nil {
		resolved = exe
	}
	return filepath.Dir(resolved)
}

// resolveDefaultPath 按 (sourceDir, executableDir, fallback) 优先级解析路径。
// relFromSource: 相对 tools/fake-node/ 的路径 (e.g. "../../config/chains")
// relFromExe:    相对 binary 目录的路径 (e.g. "config/chains"),用于打包部署
// fallback:      纯相对路径,最后兜底 (向后兼容 `go run` from source dir)
func resolveDefaultPath(relFromSource, relFromExe, fallback string) string {
	if src := sourceDir(); src != "" {
		p := filepath.Clean(filepath.Join(src, relFromSource))
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}
	if exe := executableDir(); exe != "" {
		p := filepath.Clean(filepath.Join(exe, relFromExe))
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}
	return fallback
}

func defaultChainsDir() string {
	return resolveDefaultPath("../../config/chains", "config/chains", "../../config/chains")
}

func defaultConfigsDir() string {
	return resolveDefaultPath("configs", "configs", "configs")
}

func defaultFixturesDir() string {
	return resolveDefaultPath("fixtures", "fixtures", "./fixtures")
}

func main() {
	chainFlag := flag.String("chain", "", "chain name (overrides BLOCKCHAIN_NODE env; default: solana)")
	chainsDir := flag.String("chains-dir", defaultChainsDir(), "directory of chain template JSONs")
	configsDir := flag.String("configs-dir", defaultConfigsDir(), "directory of per-family fake-node YAML configs")
	fixturesDir := flag.String("fixtures-dir", defaultFixturesDir(), "fixtures root (per-chain subdirs)")
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

	// 乙方案(2026-06-05): method 列表【单一真相源 = config/chains rpc_methods】,
	// 不用 yaml 的 methods 段(消除 yaml↔config 漂移)。yaml 仅供 tier 微调 + IO。
	methods, err := buildMethodsFromChainTemplate(tpl, cfg.Methods)
	if err != nil {
		log.Fatalf("build methods from chain template (%s): %v", chain, err)
	}
	log.Printf("methods source = config/chains/%s.json rpc_methods: %d methods (yaml tier override: %d declared)",
		chain, len(methods), len(cfg.Methods))

	fixtures, err := loadFixtures(methods, *fixturesDir, chain)
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
	mux.HandleFunc("/", handleRPC(handler, fixtures, tiers, methods))
	mux.HandleFunc("/stats", handleStats)

	srv := &http.Server{Addr: ":" + *port, Handler: mux}
	log.Printf("fake-node v2 listening on :%s (chain=%s family=%s)", *port, chain, family)
	log.Fatal(srv.ListenAndServe())
}
