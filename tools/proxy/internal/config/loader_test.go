package config

import (
	"os"
	"path/filepath"
	"testing"
)

func writeJSON(t *testing.T, dir, name, content string) string {
	t.Helper()
	p := filepath.Join(dir, name)
	if err := os.WriteFile(p, []byte(content), 0644); err != nil {
		t.Fatal(err)
	}
	return p
}

func TestLoadChain_JSONRPC(t *testing.T) {
	dir := t.TempDir()
	p := writeJSON(t, dir, "eth.json", `{
		"proxy_extraction": {
			"extractors": [
				{"protocol": "json_rpc",
				 "method_source": "body.method",
				 "id_source": "body.id",
				 "params_source": "body.params",
				 "url_pattern": "^/$",
				 "batch_handling": "split"}
			]
		}
	}`)
	c, err := LoadChain(p)
	if err != nil {
		t.Fatal(err)
	}
	if c.Len() != 1 {
		t.Errorf("len=%d", c.Len())
	}
}

func TestLoadChain_HederaDual(t *testing.T) {
	dir := t.TempDir()
	p := writeJSON(t, dir, "hedera.json", `{
		"proxy_extraction": {
			"extractors": [
				{"protocol": "rest",
				 "url_patterns": [{"pattern":"^/api/v1/accounts/[^/]+$","method_name":"GET_ACCOUNT"}]},
				{"protocol": "json_rpc",
				 "method_source": "body.method",
				 "id_source": "body.id",
				 "params_source": "body.params",
				 "url_pattern": "^/$",
				 "batch_handling": "split"}
			]
		}
	}`)
	c, err := LoadChain(p)
	if err != nil {
		t.Fatal(err)
	}
	if c.Len() != 2 {
		t.Errorf("len=%d", c.Len())
	}
}

func TestLoadChain_UnknownProtocol(t *testing.T) {
	dir := t.TempDir()
	p := writeJSON(t, dir, "bad.json", `{
		"proxy_extraction": {"extractors": [{"protocol": "graphql"}]}
	}`)
	if _, err := LoadChain(p); err == nil {
		t.Errorf("want error for unknown protocol")
	}
}

func TestLoadChain_NoExtractors(t *testing.T) {
	dir := t.TempDir()
	p := writeJSON(t, dir, "empty.json", `{"proxy_extraction": {"extractors": []}}`)
	if _, err := LoadChain(p); err == nil {
		t.Errorf("want error for empty extractors")
	}
}

func TestLoadChain_FileNotFound(t *testing.T) {
	if _, err := LoadChain("/nonexistent/chain.json"); err == nil {
		t.Errorf("want error for missing file")
	}
}

func TestLoadChain_RestMissingPatterns(t *testing.T) {
	dir := t.TempDir()
	p := writeJSON(t, dir, "bad.json", `{
		"proxy_extraction": {"extractors": [{"protocol": "rest"}]}
	}`)
	if _, err := LoadChain(p); err == nil {
		t.Errorf("want error for rest without url_patterns")
	}
}

func TestLoadChain_JSONRPCMissingURLPattern(t *testing.T) {
	dir := t.TempDir()
	p := writeJSON(t, dir, "bad.json", `{
		"proxy_extraction": {"extractors": [{"protocol": "json_rpc"}]}
	}`)
	if _, err := LoadChain(p); err == nil {
		t.Errorf("want error for json_rpc without url_pattern")
	}
}

// 真实 36 链 chain template loadability smoke
func TestLoadChain_All36Chains(t *testing.T) {
	matches, err := filepath.Glob("../../../../config/chains/*.json")
	if err != nil || len(matches) == 0 {
		t.Skipf("chain templates not found in expected location: %v", err)
	}
	for _, m := range matches {
		t.Run(filepath.Base(m), func(t *testing.T) {
			if _, err := LoadChain(m); err != nil {
				t.Errorf("load failed: %v", err)
			}
		})
	}
}
