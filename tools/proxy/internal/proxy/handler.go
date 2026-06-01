// Package proxyhandler 把请求透明转发到 upstream,
// 同时调用 extractor.Chain 提取 method_name,
// 把 (method_name, latency, status...) 写入 sink。
package proxyhandler

import (
	"bytes"
	"io"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"time"

	"proxy/internal/extractor"
	"proxy/internal/sink"
)

// Handler 是 HTTP 反向代理 + per-method 采集器。
type Handler struct {
	chain   *extractor.Chain
	sink    sink.Sink
	rp      *httputil.ReverseProxy
	upURL   string
	maxBody int64 // body 最大读取字节,防 OOM;0 = 不限
}

// New 构造 Handler。upstream 必须是合法 URL (e.g. http://localhost:8545)。
func New(chain *extractor.Chain, sk sink.Sink, upstream string, maxBody int64) (*Handler, error) {
	u, err := url.Parse(upstream)
	if err != nil {
		return nil, err
	}
	rp := httputil.NewSingleHostReverseProxy(u)
	rp.ErrorLog = log.New(io.Discard, "", 0)
	rp.Transport = &http.Transport{ // 调连接池防 loopback 高并发瓶颈
		MaxIdleConns: 512, MaxIdleConnsPerHost: 256, MaxConnsPerHost: 512,
		IdleConnTimeout: 90 * time.Second, DisableCompression: true,
	}
	return &Handler{
		chain:   chain,
		sink:    sk,
		rp:      rp,
		upURL:   upstream,
		maxBody: maxBody,
	}, nil
}

// ServeHTTP 实现 http.Handler。
func (h *Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	start := time.Now()

	// 读 body,然后还原(reverse proxy 需要)
	var body []byte
	if r.Body != nil {
		var lr io.Reader = r.Body
		if h.maxBody > 0 {
			lr = io.LimitReader(r.Body, h.maxBody)
		}
		b, err := io.ReadAll(lr)
		_ = r.Body.Close()
		if err == nil {
			body = b
		}
		r.Body = io.NopCloser(bytes.NewReader(body))
	}

	// 抓取 status (透明 ResponseWriter 包装)
	srw := &statusRecorder{ResponseWriter: w, code: http.StatusOK}
	h.rp.ServeHTTP(srw, r)

	latencyMS := time.Since(start).Milliseconds()
	results, ok := h.chain.Extract(r, body)
	if !ok {
		// extractor 没匹配也记一条 method_name="__unmatched__"
		// 这样 W3 分析层能看出 chain template 漏配
		_ = h.sink.Write(sink.Record{
			TimestampNS: start.UnixNano(),
			MethodName:  "__unmatched__",
			Protocol:    "",
			StatusCode:  srw.code,
			LatencyMS:   latencyMS,
			Upstream:    h.upURL,
			ClientAddr:  r.RemoteAddr,
		})
		return
	}
	for _, res := range results {
		_ = h.sink.Write(sink.Record{
			TimestampNS: start.UnixNano(),
			MethodName:  res.MethodName,
			Protocol:    res.Protocol,
			RequestID:   res.RequestID,
			BatchIdx:    res.BatchIdx,
			StatusCode:  srw.code,
			LatencyMS:   latencyMS,
			Upstream:    h.upURL,
			ClientAddr:  r.RemoteAddr,
		})
	}
}

// statusRecorder 透明记录 status code,不缓冲 body (大 response 直接 stream)。
type statusRecorder struct {
	http.ResponseWriter
	code int
}

func (s *statusRecorder) WriteHeader(code int) {
	s.code = code
	s.ResponseWriter.WriteHeader(code)
}
