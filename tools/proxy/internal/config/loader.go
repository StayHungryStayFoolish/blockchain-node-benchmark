// Package config 读 chain template JSON 的 proxy_extraction 字段,
// 实例化 extractor.Chain。schema 见 spec §1.7。
package config

import (
	"encoding/json"
	"fmt"
	"os"

	"proxy/internal/extractor"
)

// proxyExtraction 对应 spec §1.7 顶层。
type proxyExtraction struct {
	Extractors []rawExtractor `json:"extractors"`
}

type rawExtractor struct {
	Protocol      string              `json:"protocol"`
	MethodSource  string              `json:"method_source,omitempty"`
	IDSource      string              `json:"id_source,omitempty"`
	ParamsSource  string              `json:"params_source,omitempty"`
	URLPattern    string              `json:"url_pattern,omitempty"`
	BatchHandling string              `json:"batch_handling,omitempty"`
	Auth          map[string]string   `json:"auth,omitempty"`
	URLPatterns   []map[string]string `json:"url_patterns,omitempty"`
}

type chainTemplate struct {
	ProxyExtraction proxyExtraction `json:"proxy_extraction"`
}

// LoadChain 从 chain template JSON 文件读出 extractor chain。
func LoadChain(path string) (*extractor.Chain, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read chain template: %w", err)
	}
	var c chainTemplate
	if err := json.Unmarshal(data, &c); err != nil {
		return nil, fmt.Errorf("parse chain template JSON: %w", err)
	}
	if len(c.ProxyExtraction.Extractors) == 0 {
		return nil, fmt.Errorf("chain template %s has no proxy_extraction.extractors", path)
	}
	es := make([]extractor.Extractor, 0, len(c.ProxyExtraction.Extractors))
	for i, raw := range c.ProxyExtraction.Extractors {
		e, err := buildExtractor(i, raw)
		if err != nil {
			return nil, fmt.Errorf("extractor[%d]: %w", i, err)
		}
		es = append(es, e)
	}
	return extractor.NewChain(es...), nil
}

func buildExtractor(idx int, raw rawExtractor) (extractor.Extractor, error) {
	name := fmt.Sprintf("%s[%d]", raw.Protocol, idx)
	switch raw.Protocol {
	case "json_rpc":
		if raw.URLPattern == "" {
			return nil, fmt.Errorf("json_rpc missing url_pattern")
		}
		return extractor.NewJSONRPC(name, raw.URLPattern, raw.BatchHandling)
	case "rest":
		if len(raw.URLPatterns) == 0 {
			return nil, fmt.Errorf("rest missing url_patterns")
		}
		return extractor.NewREST(name, raw.URLPatterns)
	default:
		return nil, fmt.Errorf("unknown protocol: %q (only json_rpc/rest allowed, see spec §1.7)", raw.Protocol)
	}
}
