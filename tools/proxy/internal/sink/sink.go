// Package sink persists per-method collection records.
//
// CSV schema (column order is stable):
//
//	timestamp_ns, method_name, protocol, request_id, batch_idx,
//	status_code, transport_success, rpc_success, rpc_error_code,
//	rpc_error_message, latency_ms, upstream, client_addr
//
// Environment variables:
//
//	PROXY_SINK_FORMAT  csv (default) | jsonl | discard
//	PROXY_SINK_PATH    output path; defaults to ./proxy_per_method.csv or .jsonl
package sink

import (
	"encoding/csv"
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"sync"
)

type Record struct {
	TimestampNS      int64  `json:"timestamp_ns"`
	MethodName       string `json:"method_name"`
	Protocol         string `json:"protocol"`
	RequestID        string `json:"request_id"`
	BatchIdx         int    `json:"batch_idx"`
	StatusCode       int    `json:"status_code"`
	TransportSuccess bool   `json:"transport_success"`
	RPCSuccess       bool   `json:"rpc_success"`
	RPCErrorCode     string `json:"rpc_error_code"`
	RPCErrorMessage  string `json:"rpc_error_message"`
	LatencyMS        int64  `json:"latency_ms"`
	Upstream         string `json:"upstream"`
	ClientAddr       string `json:"client_addr"`
}

type Sink interface {
	Write(r Record) error
	Close() error
}

var csvHeader = []string{
	"timestamp_ns", "method_name", "protocol", "request_id", "batch_idx",
	"status_code", "transport_success", "rpc_success", "rpc_error_code",
	"rpc_error_message", "latency_ms", "upstream", "client_addr",
}

func New(format, path string) (Sink, error) {
	if format == "" {
		format = os.Getenv("PROXY_SINK_FORMAT")
	}
	if format == "" {
		format = "csv"
	}
	if path == "" {
		path = os.Getenv("PROXY_SINK_PATH")
	}
	switch format {
	case "csv":
		if path == "" {
			path = "./proxy_per_method.csv"
		}
		return newFile(path, true)
	case "jsonl":
		if path == "" {
			path = "./proxy_per_method.jsonl"
		}
		return newFile(path, false)
	case "discard":
		return discardSink{}, nil
	default:
		return nil, fmt.Errorf("unknown PROXY_SINK_FORMAT: %q (csv|jsonl|discard)", format)
	}
}

type fileSink struct {
	mu    sync.Mutex
	f     *os.File
	w     *csv.Writer
	isCSV bool
}

func newFile(path string, isCSV bool) (*fileSink, error) {
	f, err := os.OpenFile(path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0644)
	if err != nil {
		return nil, fmt.Errorf("open sink: %w", err)
	}
	s := &fileSink{f: f, isCSV: isCSV}
	if isCSV {
		s.w = csv.NewWriter(f)
		if st, _ := f.Stat(); st != nil && st.Size() == 0 {
			_ = s.w.Write(csvHeader)
			s.w.Flush()
		}
	}
	return s, nil
}

func (s *fileSink) Write(r Record) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.isCSV {
		err := s.w.Write([]string{
			strconv.FormatInt(r.TimestampNS, 10), r.MethodName, r.Protocol,
			r.RequestID, strconv.Itoa(r.BatchIdx), strconv.Itoa(r.StatusCode),
			strconv.FormatBool(r.TransportSuccess), strconv.FormatBool(r.RPCSuccess),
			r.RPCErrorCode, r.RPCErrorMessage,
			strconv.FormatInt(r.LatencyMS, 10), r.Upstream, r.ClientAddr,
		})
		if err != nil {
			return err
		}
		s.w.Flush()
		return s.w.Error()
	}
	b, err := json.Marshal(r)
	if err != nil {
		return err
	}
	_, err = s.f.Write(append(b, '\n'))
	return err
}

func (s *fileSink) Close() error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.w != nil {
		s.w.Flush()
	}
	return s.f.Close()
}

type discardSink struct{}

func (discardSink) Write(Record) error { return nil }
func (discardSink) Close() error       { return nil }
