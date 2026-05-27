// mock_rpc_v2.go — fixture-backed mock with per-method latency tiers.
//
// 升级 mock_rpc.go v1:
//   v1: 任何 method 返回 {"result":1000}
//   v2: 从 fixtures/<method>.json 读真录 response,按 cheap/mid/expensive 三档 sleep
//
// 用途: 录-放 PoC, 模拟"便宜 method 1ms / 中等 method 10ms / 昂贵 method 50ms"
//       (对应 ADR-0001 weight 1/10/100 三档)
//
// 用法:
//   go run mock_rpc_v2.go \
//     -port 18899 \
//     -fixtures ./fixtures \
//     -sleep-cheap 1ms \
//     -sleep-mid 10ms \
//     -sleep-expensive 50ms
//
// method -> tier 映射 (硬编码, 与 record_fixtures.sh 一致):
//   cheap     : getSlot, getBalance
//   mid       : getLatestBlockhash
//   expensive : getBlock, getTransaction
//
//go:build ignore

package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"
)

type rpcReq struct {
	JSONRPC string      `json:"jsonrpc"`
	ID      interface{} `json:"id"`
	Method  string      `json:"method"`
}

var (
	tierCheap     = map[string]bool{"getSlot": true, "getBalance": true}
	tierMid       = map[string]bool{"getLatestBlockhash": true}
	tierExpensive = map[string]bool{"getBlock": true, "getTransaction": true}
)

func main() {
	port := flag.String("port", "18899", "listen port")
	fixturesDir := flag.String("fixtures", "./fixtures", "fixtures directory")
	sleepCheap := flag.Duration("sleep-cheap", 1*time.Millisecond, "cheap method sleep")
	sleepMid := flag.Duration("sleep-mid", 10*time.Millisecond, "mid method sleep")
	sleepExpensive := flag.Duration("sleep-expensive", 50*time.Millisecond, "expensive method sleep")
	flag.Parse()

	// 启动时把所有 fixtures load 进内存
	fixtures := make(map[string][]byte)
	entries, err := os.ReadDir(*fixturesDir)
	if err != nil {
		log.Fatalf("read fixtures dir: %v", err)
	}
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".json") {
			continue
		}
		method := strings.TrimSuffix(e.Name(), ".json")
		data, err := os.ReadFile(filepath.Join(*fixturesDir, e.Name()))
		if err != nil {
			log.Fatalf("read %s: %v", e.Name(), err)
		}
		fixtures[method] = data
		log.Printf("loaded fixture: %s (%d bytes)", method, len(data))
	}
	if len(fixtures) == 0 {
		log.Fatalf("no fixtures loaded from %s", *fixturesDir)
	}

	sleepFor := func(method string) time.Duration {
		switch {
		case tierCheap[method]:
			return *sleepCheap
		case tierMid[method]:
			return *sleepMid
		case tierExpensive[method]:
			return *sleepExpensive
		default:
			return *sleepCheap
		}
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		body, err := io.ReadAll(r.Body)
		if err != nil {
			http.Error(w, err.Error(), 400)
			return
		}
		defer r.Body.Close()

		var req rpcReq
		if err := json.Unmarshal(body, &req); err != nil {
			http.Error(w, err.Error(), 400)
			return
		}

		fixture, ok := fixtures[req.Method]
		if !ok {
			http.Error(w, fmt.Sprintf("no fixture for method: %s", req.Method), 404)
			return
		}

		// 模拟节点处理延迟
		time.Sleep(sleepFor(req.Method))

		// 把 fixture 的 id 替换成请求的 id (粗略, 直接字符串替换)
		// 真 PoC 应该 decode-modify-encode, 这里图简单
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(200)
		_, _ = w.Write(fixture)
	})

	srv := &http.Server{Addr: ":" + *port, Handler: mux}
	log.Printf("mock_rpc_v2 listening on :%s, fixtures=%d, sleep=cheap:%s/mid:%s/expensive:%s",
		*port, len(fixtures), *sleepCheap, *sleepMid, *sleepExpensive)
	log.Fatal(srv.ListenAndServe())
}
