// Package sink 是 per-method 采集结果的持久化层。
//
// CSV schema (列顺序锁定):
//
//	timestamp_ns, method_name, protocol, request_id, batch_idx,
//	status_code, latency_ms, upstream, client_addr
//
// 环境变量:
//
//	PROXY_SINK_FORMAT  csv (默认) | jsonl | discard
//	PROXY_SINK_PATH    输出路径;默认 ./proxy_per_method.csv 或 .jsonl
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
	TimestampNS int64  `json:"timestamp_ns"`
	MethodName  string `json:"method_name"`
	Protocol    string `json:"protocol"`
	RequestID   string `json:"request_id"`
	BatchIdx    int    `json:"batch_idx"`
	StatusCode  int    `json:"status_code"`
	LatencyMS   int64  `json:"latency_ms"`
	Upstream    string `json:"upstream"`
	ClientAddr  string `json:"client_addr"`
}

type Sink interface {
	Write(r Record) error
	Close() error
}

var csvHeader = []string{
	"timestamp_ns", "method_name", "protocol", "request_id", "batch_idx",
	"status_code", "latency_ms", "upstream", "client_addr",
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
