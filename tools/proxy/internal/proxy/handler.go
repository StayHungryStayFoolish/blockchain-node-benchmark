// Package proxyhandler forwards requests transparently to upstream, extracts
// method_name through extractor.Chain, and writes method/latency/status records
// to the sink.
package proxyhandler

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"time"

	"proxy/internal/extractor"
	"proxy/internal/sink"
)

// Handler is an HTTP reverse proxy plus per-method collector.
type Handler struct {
	chain   *extractor.Chain
	sink    sink.Sink
	rp      *httputil.ReverseProxy
	upURL   string
	maxBody int64 // maximum body bytes to read; 0 means unlimited
}

// New constructs a Handler. upstream must be a valid URL.
func New(chain *extractor.Chain, sk sink.Sink, upstream string, maxBody int64) (*Handler, error) {
	u, err := url.Parse(upstream)
	if err != nil {
		return nil, err
	}
	rp := httputil.NewSingleHostReverseProxy(u)
	rp.ErrorLog = log.New(io.Discard, "", 0)
	rp.Transport = &http.Transport{ // tune connection pooling for loopback load
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

// ServeHTTP implements http.Handler.
func (h *Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	start := time.Now()

	// Read the body and restore it for the reverse proxy.
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

	// Capture status and a limited response prefix through a transparent
	// ResponseWriter wrapper. The body is not persisted; it is only parsed into
	// success/failure summary fields for per-method reporting.
	srw := &statusRecorder{
		ResponseWriter: w,
		code:           http.StatusOK,
		maxBody:        h.maxBody,
	}
	h.rp.ServeHTTP(srw, r)

	latencyMS := time.Since(start).Milliseconds()
	results, ok := h.chain.Extract(r, body)
	transportSuccess := isTransportSuccess(srw.code)
	if !ok {
		// Record unmatched requests as method_name="__unmatched__".
		// This lets downstream attribution identify missing chain-template mappings
		rpcStatus := methodRPCStatus{
			Success: transportSuccess,
		}
		if !transportSuccess {
			rpcStatus.ErrorCode = fmt.Sprintf("http_%d", srw.code)
			rpcStatus.ErrorMessage = http.StatusText(srw.code)
		}
		_ = h.sink.Write(sink.Record{
			TimestampNS:      start.UnixNano(),
			MethodName:       "__unmatched__",
			Protocol:         "",
			StatusCode:       srw.code,
			TransportSuccess: transportSuccess,
			RPCSuccess:       rpcStatus.Success,
			RPCErrorCode:     rpcStatus.ErrorCode,
			RPCErrorMessage:  rpcStatus.ErrorMessage,
			LatencyMS:        latencyMS,
			Upstream:         h.upURL,
			ClientAddr:       r.RemoteAddr,
		})
		return
	}
	rpcStatuses := classifyRPCStatuses(results, srw.body.Bytes(), srw.code, transportSuccess)
	for _, res := range results {
		rpcStatus := rpcStatuses[statusKey(res)]
		_ = h.sink.Write(sink.Record{
			TimestampNS:      start.UnixNano(),
			MethodName:       res.MethodName,
			Protocol:         res.Protocol,
			RequestID:        res.RequestID,
			BatchIdx:         res.BatchIdx,
			StatusCode:       srw.code,
			TransportSuccess: transportSuccess,
			RPCSuccess:       rpcStatus.Success,
			RPCErrorCode:     rpcStatus.ErrorCode,
			RPCErrorMessage:  rpcStatus.ErrorMessage,
			LatencyMS:        latencyMS,
			Upstream:         h.upURL,
			ClientAddr:       r.RemoteAddr,
		})
	}
}

// statusRecorder records the status code and buffers a limited response prefix.
type statusRecorder struct {
	http.ResponseWriter
	code    int
	body    bytes.Buffer
	maxBody int64
}

func (s *statusRecorder) WriteHeader(code int) {
	s.code = code
	s.ResponseWriter.WriteHeader(code)
}

func (s *statusRecorder) Write(p []byte) (int, error) {
	if s.maxBody == 0 || int64(s.body.Len()) < s.maxBody {
		remaining := len(p)
		if s.maxBody > 0 {
			remaining = int(s.maxBody) - s.body.Len()
			if remaining > len(p) {
				remaining = len(p)
			}
		}
		if remaining > 0 {
			_, _ = s.body.Write(p[:remaining])
		}
	}
	return s.ResponseWriter.Write(p)
}

type methodRPCStatus struct {
	Success      bool
	ErrorCode    string
	ErrorMessage string
}

func isTransportSuccess(code int) bool {
	return code >= 200 && code < 400
}

func classifyRPCStatuses(
	results []extractor.Result,
	responseBody []byte,
	statusCode int,
	transportSuccess bool,
) map[string]methodRPCStatus {
	out := make(map[string]methodRPCStatus, len(results))
	defaultStatus := methodRPCStatus{Success: transportSuccess}
	if !transportSuccess {
		defaultStatus.ErrorCode = fmt.Sprintf("http_%d", statusCode)
		defaultStatus.ErrorMessage = http.StatusText(statusCode)
	}
	for _, res := range results {
		out[statusKey(res)] = defaultStatus
	}
	if !transportSuccess || len(responseBody) == 0 {
		return out
	}

	hasJSONRPC := false
	for _, res := range results {
		if res.Protocol == "json_rpc" {
			hasJSONRPC = true
			break
		}
	}
	if hasJSONRPC {
		applyJSONRPCStatus(out, results, responseBody)
		return out
	}

	// REST APIs mostly communicate failure through HTTP status. For 2xx/3xx
	// responses, only treat explicit JSON error/errors fields as RPC failure.
	if restStatus, ok := classifyRESTBody(responseBody); ok {
		for _, res := range results {
			out[statusKey(res)] = restStatus
		}
	}
	return out
}

func statusKey(res extractor.Result) string {
	return fmt.Sprintf("%s/%d", res.RequestID, res.BatchIdx)
}

func applyJSONRPCStatus(
	out map[string]methodRPCStatus,
	results []extractor.Result,
	responseBody []byte,
) {
	var raw any
	if err := json.Unmarshal(responseBody, &raw); err != nil {
		st := methodRPCStatus{
			Success:      false,
			ErrorCode:    "invalid_json_response",
			ErrorMessage: "response body is not valid JSON",
		}
		for _, res := range results {
			if res.Protocol == "json_rpc" {
				out[statusKey(res)] = st
			}
		}
		return
	}
	switch v := raw.(type) {
	case []any:
		statusByID := make(map[string]methodRPCStatus, len(v))
		for _, item := range v {
			obj, ok := item.(map[string]any)
			if !ok {
				continue
			}
			statusByID[stringifyJSONRPCID(obj["id"])] = statusFromJSONRPCObject(obj)
		}
		for _, res := range results {
			if res.Protocol != "json_rpc" {
				continue
			}
			if st, ok := statusByID[res.RequestID]; ok {
				out[statusKey(res)] = st
			}
		}
	case map[string]any:
		st := statusFromJSONRPCObject(v)
		for _, res := range results {
			if res.Protocol == "json_rpc" {
				out[statusKey(res)] = st
			}
		}
	}
}

func statusFromJSONRPCObject(obj map[string]any) methodRPCStatus {
	if errVal, ok := obj["error"]; ok && errVal != nil {
		code, msg := parseErrorValue(errVal)
		return methodRPCStatus{Success: false, ErrorCode: code, ErrorMessage: msg}
	}
	return methodRPCStatus{Success: true}
}

func classifyRESTBody(responseBody []byte) (methodRPCStatus, bool) {
	var obj map[string]any
	if err := json.Unmarshal(responseBody, &obj); err != nil {
		return methodRPCStatus{}, false
	}
	for _, key := range []string{"error", "errors"} {
		if val, ok := obj[key]; ok && hasErrorValue(val) {
			code, msg := parseErrorValue(val)
			return methodRPCStatus{Success: false, ErrorCode: code, ErrorMessage: msg}, true
		}
	}
	return methodRPCStatus{Success: true}, true
}

func parseErrorValue(val any) (string, string) {
	switch v := val.(type) {
	case map[string]any:
		code := stringifyJSONRPCID(v["code"])
		msg := ""
		if m, ok := v["message"].(string); ok {
			msg = m
		}
		return code, msg
	case []any:
		return "errors", fmt.Sprintf("%d error item(s)", len(v))
	case string:
		return "error", v
	default:
		return "error", fmt.Sprint(v)
	}
}

func hasErrorValue(val any) bool {
	switch v := val.(type) {
	case nil:
		return false
	case string:
		return v != ""
	case []any:
		return len(v) > 0
	default:
		return true
	}
}

func stringifyJSONRPCID(id any) string {
	switch v := id.(type) {
	case nil:
		return ""
	case string:
		return v
	case float64:
		if v == float64(int64(v)) {
			return fmt.Sprintf("%d", int64(v))
		}
		return fmt.Sprintf("%v", v)
	case bool:
		return fmt.Sprintf("%t", v)
	default:
		b, _ := json.Marshal(id)
		return string(b)
	}
}
