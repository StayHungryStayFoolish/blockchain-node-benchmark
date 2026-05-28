// Command proxy 启动 per-method HTTP 反向代理。
//
// 用法:
//
//	proxy -chain=config/chains/ethereum.json -upstream=http://localhost:8545 -listen=:18545
//
// 环境变量:
//
//	PROXY_SINK_FORMAT  csv (默认) | jsonl | discard
//	PROXY_SINK_PATH    per-method sink 输出路径 (默认 ./proxy_per_method.csv)
//	PROXY_SELF_PATH    proxy 自报输出路径 (默认 ./proxy_self.csv)
package main

import (
	"context"
	"errors"
	"flag"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"proxy/internal/config"
	proxyhandler "proxy/internal/proxy"
	"proxy/internal/selfreport"
	"proxy/internal/sink"
)

func main() {
	chainPath := flag.String("chain", "", "path to chain template JSON (required)")
	upstream := flag.String("upstream", "", "upstream URL e.g. http://localhost:8545 (required)")
	listen := flag.String("listen", ":18545", "listen address")
	maxBody := flag.Int64("max-body", 1<<20, "max request body bytes to read (default 1MB)")
	selfInterval := flag.Duration("self-interval", time.Second, "self-report interval")
	flag.Parse()

	if *chainPath == "" || *upstream == "" {
		log.Fatalf("usage: proxy -chain=<file> -upstream=<url> [-listen=:18545]")
	}

	chain, err := config.LoadChain(*chainPath)
	if err != nil {
		log.Fatalf("load chain template: %v", err)
	}
	log.Printf("loaded %d extractor(s) from %s", chain.Len(), *chainPath)

	sk, err := sink.New("", "")
	if err != nil {
		log.Fatalf("init sink: %v", err)
	}
	defer sk.Close()

	h, err := proxyhandler.New(chain, sk, *upstream, *maxBody)
	if err != nil {
		log.Fatalf("init handler: %v", err)
	}

	rep := selfreport.New(os.Getenv("PROXY_SELF_PATH"), *selfInterval)
	if err := rep.Start(); err != nil {
		log.Fatalf("start self-report: %v", err)
	}
	defer rep.Stop()

	srv := &http.Server{
		Addr:              *listen,
		Handler:           h,
		ReadHeaderTimeout: 10 * time.Second,
	}

	idleClosed := make(chan struct{})
	go func() {
		sig := make(chan os.Signal, 1)
		signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
		<-sig
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = srv.Shutdown(ctx)
		close(idleClosed)
	}()

	log.Printf("proxy listening on %s -> %s", *listen, *upstream)
	if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Fatalf("listen: %v", err)
	}
	<-idleClosed
	log.Printf("proxy shut down cleanly")
}
