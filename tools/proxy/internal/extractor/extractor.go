// Package extractor defines per-method extractor interfaces and factories.
//
// spec §1.7 defines two protocols:
//   - json_rpc: extracts method/id/params from the HTTP body
//   - rest:     matches method_name from URL path and HTTP method using regex
//
// Multiple extractors are tried in declaration order; the first match wins.
package extractor

import (
	"net/http"
)

// Result is one extraction result. One HTTP request may produce multiple results
// when json_rpc batch handling is split.
type Result struct {
	Protocol   string // "json_rpc" | "rest"
	MethodName string // stable method identifier used for attribution joins
	RequestID  string // stringified json_rpc request id; empty for rest
	BatchIdx   int    // zero-based batch item index; 0 for non-batch requests
}

// Extractor is the per-method extractor interface.
// Extract returns (results, ok). ok=false means this extractor does not match
// the request and the caller should try the next extractor.
type Extractor interface {
	Name() string
	Extract(req *http.Request, body []byte) ([]Result, bool)
}

// Chain tries multiple extractors in declaration order.
type Chain struct {
	extractors []Extractor
}

func NewChain(es ...Extractor) *Chain {
	return &Chain{extractors: es}
}

func (c *Chain) Extract(req *http.Request, body []byte) ([]Result, bool) {
	for _, e := range c.extractors {
		if rs, ok := e.Extract(req, body); ok {
			return rs, true
		}
	}
	return nil, false
}

func (c *Chain) Len() int { return len(c.extractors) }
