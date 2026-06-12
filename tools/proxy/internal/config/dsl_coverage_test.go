// DSL coverage smoke — 36-chain dry-run extract verification.
//
// Load every chain template and construct
// a fixture HTTP request; Chain.Extract must return a non-empty method_name.
//
// Coverage below 32/36 should trigger extractor fallback review
package config

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
)

// buildFixtureRequest constructs an HTTP request that should match the chain extractor.
//
// Strategy:
//   - json_rpc: POST body = {"jsonrpc":"2.0","id":1,"method":<first_mixed_method>,"params":[]}
//   - rest:     GET url = sample path from the first url_pattern
//
// Returning nil means no fixture request could be derived; this is treated as
// unsupported fixture derivation rather than an extractor bug.
func buildFixtureRequest(chainPath string) (*http.Request, error) {
	raw, err := os.ReadFile(chainPath)
	if err != nil {
		return nil, err
	}
	var tpl map[string]any
	if err := json.Unmarshal(raw, &tpl); err != nil {
		return nil, err
	}

	pe, ok := tpl["proxy_extraction"].(map[string]any)
	if !ok {
		return nil, fmt.Errorf("no proxy_extraction")
	}
	extractors, ok := pe["extractors"].([]any)
	if !ok || len(extractors) == 0 {
		return nil, fmt.Errorf("no extractors")
	}
	first, ok := extractors[0].(map[string]any)
	if !ok {
		return nil, fmt.Errorf("extractor[0] not object")
	}
	proto, _ := first["protocol"].(string)

	switch proto {
	case "json_rpc":
		method := pickFirstMethod(tpl)
		if method == "" {
			method = "ping" // fallback; extractor only requires body.method to exist
		}
		body := fmt.Sprintf(`{"jsonrpc":"2.0","id":1,"method":%q,"params":[]}`, method)
		req, _ := http.NewRequest("POST", "http://127.0.0.1/", bytes.NewReader([]byte(body)))
		req.Header.Set("Content-Type", "application/json")
		return req, nil
	case "rest":
		urlPatterns, ok := first["url_patterns"].([]any)
		if !ok || len(urlPatterns) == 0 {
			return nil, fmt.Errorf("rest: no url_patterns")
		}
		fp, ok := urlPatterns[0].(map[string]any)
		if !ok {
			return nil, fmt.Errorf("rest: url_patterns[0] not object")
		}
		pat, _ := fp["pattern"].(string)
		methodName, _ := fp["method_name"].(string)
		// HTTP verb priority: explicit method field > method_name prefix > GET.
		httpMethod := strings.ToUpper(strings.TrimSpace(fmt.Sprint(fp["method"])))
		if httpMethod == "" || httpMethod == "<NIL>" {
			httpMethod = "" // reset before trying method_name prefix inference
			for _, v := range []string{"GET ", "POST ", "PUT ", "DELETE ", "PATCH ", "HEAD ", "OPTIONS "} {
				if strings.HasPrefix(methodName, v) {
					httpMethod = strings.TrimSpace(v)
					break
				}
			}
		}
		if httpMethod == "" {
			httpMethod = "GET"
		}
		sample := patternToSamplePath(pat)
		req, err := http.NewRequest(httpMethod, "http://127.0.0.1"+sample, nil)
		if err != nil {
			return nil, fmt.Errorf("NewRequest(%q, %q): %w", httpMethod, sample, err)
		}
		return req, nil
	default:
		return nil, fmt.Errorf("unknown protocol: %s", proto)
	}
}

// pickFirstMethod reads rpc_methods.mixed_weighted[0], or the first mixed item,
// or single as a fallback.
func pickFirstMethod(tpl map[string]any) string {
	rm, ok := tpl["rpc_methods"].(map[string]any)
	if !ok {
		return ""
	}
	if mw, ok := rm["mixed_weighted"].([]any); ok && len(mw) > 0 {
		if first, ok := mw[0].(map[string]any); ok {
			if m, ok := first["method"].(string); ok && m != "" {
				return m
			}
		}
	}
	if mixed, ok := rm["mixed"].(string); ok && mixed != "" {
		parts := strings.Split(mixed, ",")
		if len(parts) > 0 {
			return strings.TrimSpace(parts[0])
		}
	}
	if single, ok := rm["single"].(string); ok && single != "" {
		return single
	}
	return ""
}

// patternToSamplePath converts a regex pattern into a literal sample path.
// Simplified strategy:
//   - ^/api$        → /api
//   - ^/v1/(.+)$    → /v1/sample
//   - ^/$           → /
//   - other regexes -> strip anchors/groups and keep a literal sample
func patternToSamplePath(pat string) string {
	// Strip simple anchors.
	p := strings.TrimPrefix(pat, "^")
	p = strings.TrimSuffix(p, "$")
	// Replace capture groups with sample placeholders.
	p = strings.ReplaceAll(p, "(.+)", "sample")
	p = strings.ReplaceAll(p, "(.*)", "sample")
	p = strings.ReplaceAll(p, "([^/]+)", "sample")
	p = strings.ReplaceAll(p, "(\\d+)", "1")
	// Bare character classes without capture groups.
	p = strings.ReplaceAll(p, "[^/]+", "sample")
	p = strings.ReplaceAll(p, "[^/]*", "sample")
	p = strings.ReplaceAll(p, "\\d+", "1")
	p = strings.ReplaceAll(p, "\\w+", "sample")
	// Strip other regex meta.
	p = strings.ReplaceAll(p, "\\.", ".")
	if !strings.HasPrefix(p, "/") {
		p = "/" + p
	}
	return p
}

func TestProxyDSLCoverage_All36Chains(t *testing.T) {
	matches, err := filepath.Glob("../../../../config/chains/*.json")
	if err != nil || len(matches) == 0 {
		t.Skipf("chain templates not found: %v", err)
	}
	sort.Strings(matches)

	type result struct {
		chain     string
		loadOK    bool
		extractOK bool
		method    string
		reason    string
	}
	var results []result

	for _, m := range matches {
		chain := strings.TrimSuffix(filepath.Base(m), ".json")
		r := result{chain: chain}

		c, err := LoadChain(m)
		if err != nil {
			r.reason = "load: " + err.Error()
			results = append(results, r)
			continue
		}
		r.loadOK = true

		req, err := buildFixtureRequest(m)
		if err != nil {
			r.reason = "fixture: " + err.Error()
			results = append(results, r)
			continue
		}
		if req == nil {
			r.reason = "fixture: nil request"
			results = append(results, r)
			continue
		}

		// Read the body into a byte buffer, matching proxy runtime behavior.
		var body []byte
		if req.Body != nil {
			buf := new(bytes.Buffer)
			_, _ = buf.ReadFrom(req.Body)
			body = buf.Bytes()
		}

		out, ok := c.Extract(req, body)
		if !ok || len(out) == 0 {
			r.reason = "extract: no match"
			results = append(results, r)
			continue
		}
		if out[0].MethodName == "" {
			r.reason = "extract: empty method_name"
			results = append(results, r)
			continue
		}
		r.extractOK = true
		r.method = out[0].MethodName
		results = append(results, r)
	}

	// Report
	var pass, fail []result
	for _, r := range results {
		if r.extractOK {
			pass = append(pass, r)
		} else {
			fail = append(fail, r)
		}
	}
	t.Logf("=== DSL coverage: %d/%d PASS ===", len(pass), len(results))
	for _, r := range pass {
		t.Logf("  PASS %-25s method=%s", r.chain, r.method)
	}
	for _, r := range fail {
		t.Logf("  FAIL %-25s %s", r.chain, r.reason)
	}

	// Coverage threshold: >= 32/36
	if len(pass) < 32 {
		t.Errorf("DSL coverage %d/%d < 32/36 threshold; trigger proxy extractor fallback evaluation", len(pass), len(results))
	}
}
