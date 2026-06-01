package sink

import (
	"encoding/csv"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestCSVSink_WriteAndRead(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "out.csv")
	s, err := New("csv", path)
	if err != nil {
		t.Fatal(err)
	}
	rec := Record{
		TimestampNS: 1700000000000000000, MethodName: "eth_blockNumber",
		Protocol: "json_rpc", RequestID: "1", BatchIdx: 0,
		StatusCode: 200, LatencyMS: 5,
		Upstream: "http://x:8545", ClientAddr: "1.1.1.1:443",
	}
	if err := s.Write(rec); err != nil {
		t.Fatal(err)
	}
	if err := s.Close(); err != nil {
		t.Fatal(err)
	}

	f, _ := os.Open(path)
	defer f.Close()
	rows, _ := csv.NewReader(f).ReadAll()
	if len(rows) != 2 { // header + 1 row
		t.Fatalf("want 2 rows, got %d", len(rows))
	}
	if rows[0][0] != "timestamp_ns" || rows[0][1] != "method_name" {
		t.Errorf("bad header: %v", rows[0])
	}
	if rows[1][1] != "eth_blockNumber" || rows[1][6] != "5" {
		t.Errorf("bad row: %v", rows[1])
	}
}

func TestCSVSink_AppendKeepsHeader(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "out.csv")
	s1, _ := New("csv", path)
	_ = s1.Write(Record{MethodName: "a"})
	_ = s1.Close()
	// 第二次 open 不应再写 header
	s2, _ := New("csv", path)
	_ = s2.Write(Record{MethodName: "b"})
	_ = s2.Close()

	data, _ := os.ReadFile(path)
	if strings.Count(string(data), "method_name") != 1 {
		t.Errorf("header should appear exactly once, got data:\n%s", data)
	}
}

func TestJSONLSink(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "out.jsonl")
	s, err := New("jsonl", path)
	if err != nil {
		t.Fatal(err)
	}
	_ = s.Write(Record{MethodName: "x", LatencyMS: 7})
	_ = s.Close()

	data, _ := os.ReadFile(path)
	if !strings.Contains(string(data), `"method_name":"x"`) {
		t.Errorf("jsonl missing field: %s", data)
	}
}

func TestDiscardSink(t *testing.T) {
	s, err := New("discard", "")
	if err != nil {
		t.Fatal(err)
	}
	if err := s.Write(Record{MethodName: "x"}); err != nil {
		t.Errorf("discard write err: %v", err)
	}
	_ = s.Close()
}

func TestUnknownFormat(t *testing.T) {
	if _, err := New("xml", ""); err == nil {
		t.Errorf("want error for unknown format")
	}
}

func TestEnvDefaults(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("PROXY_SINK_FORMAT", "jsonl")
	t.Setenv("PROXY_SINK_PATH", filepath.Join(dir, "env.jsonl"))
	s, err := New("", "")
	if err != nil {
		t.Fatal(err)
	}
	_ = s.Write(Record{MethodName: "envtest"})
	_ = s.Close()
	data, _ := os.ReadFile(filepath.Join(dir, "env.jsonl"))
	if !strings.Contains(string(data), "envtest") {
		t.Errorf("env-driven path not used: %s", data)
	}
}
