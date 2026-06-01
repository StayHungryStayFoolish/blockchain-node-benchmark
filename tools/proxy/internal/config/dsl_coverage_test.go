// S4.4 DSL coverage smoke — 36 链 dry-run extract verification.
//
// 升级 TestLoadChain_All36Chains(只验 load)到:对每条链 load + 构造
// 一个 fixture HTTP request → 调 Chain.Extract → 验出 method_name 非空。
//
// Plan: docs/plans/2026-05-28-s4-ns2-implementation.md §6 Task S4.4.1/2/3
// 验收: 覆盖率 ≥ 32/36 → OK; < 32/36 → 触发 ADR-0007 兜底评估
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

// buildFixtureRequest 给定 chain template,构造一个能被该 chain extractor 匹配的 HTTP 请求。
//
// 策略:
//   - json_rpc: POST body = {"jsonrpc":"2.0","id":1,"method":<first_mixed_method>,"params":[]}
//   - rest:     GET url = <first url_pattern 的样本路径>
//
// 失败容忍:返回 nil 表示无法构造(测试中算"协议未实现的 fixture 推导",非 extractor bug)。
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
			method = "ping" // fallback; extractor 只看 body.method 存在,不验合法性
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
		// HTTP verb 推导优先级:显式 method 字段 > method_name 前缀(GET / POST / ...)> GET 兜底
		httpMethod := strings.ToUpper(strings.TrimSpace(fmt.Sprint(fp["method"])))
		if httpMethod == "" || httpMethod == "<NIL>" {
			httpMethod = "" // 重置后再走 method_name 前缀推导
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

// pickFirstMethod 从 rpc_methods.mixed_weighted[0] 或 rpc_methods.mixed 第一个或 .single 取 method。
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

// patternToSamplePath 把 regex pattern 转成一个能 match 的字面量样本。
// 简化策略(够覆盖现有 4 个 rest 链 + hedera dual):
//   - ^/api$        → /api
//   - ^/v1/(.+)$    → /v1/sample
//   - ^/$           → /
//   - 其它复杂 regex → 去掉 ^ $ 和 () 取字面量,补一个 /sample 后缀
func patternToSamplePath(pat string) string {
	// 简单去掉锚点
	p := strings.TrimPrefix(pat, "^")
	p = strings.TrimSuffix(p, "$")
	// 把 capture group 替换成占位
	p = strings.ReplaceAll(p, "(.+)", "sample")
	p = strings.ReplaceAll(p, "(.*)", "sample")
	p = strings.ReplaceAll(p, "([^/]+)", "sample")
	p = strings.ReplaceAll(p, "(\\d+)", "1")
	// 裸 character class(无 capture group):覆盖 algorand/aptos/hedera/tezos 等 rest 链
	p = strings.ReplaceAll(p, "[^/]+", "sample")
	p = strings.ReplaceAll(p, "[^/]*", "sample")
	p = strings.ReplaceAll(p, "\\d+", "1")
	p = strings.ReplaceAll(p, "\\w+", "sample")
	// 去掉其它 regex meta
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

		// 把 body 读到 byte buffer(模拟 proxy runtime 行为)
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
	t.Logf("=== S4.4 DSL coverage: %d/%d PASS ===", len(pass), len(results))
	for _, r := range pass {
		t.Logf("  PASS %-25s method=%s", r.chain, r.method)
	}
	for _, r := range fail {
		t.Logf("  FAIL %-25s %s", r.chain, r.reason)
	}

	// 验收:≥ 32/36
	if len(pass) < 32 {
		t.Errorf("S4.4 coverage %d/%d < 32/36 threshold; trigger ADR-0007 envoy+Lua fallback eval", len(pass), len(results))
	}
}
