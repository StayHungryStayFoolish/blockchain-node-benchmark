package extractor

import (
	"fmt"
	"net/http"
	"regexp"
	"strings"
)

// REST 实现 spec §1.7 rest 模式。第一个 URL.Path 匹配的 pattern 决定 method_name。
// 若 method_name 形如 "GET /xxx" "POST /xxx" 则前缀 HTTP verb 也参与过滤
// (兼容 chain template _meta.rest_paths key 约定)。
type REST struct {
	name     string
	patterns []restPattern
}

type restPattern struct {
	regex      *regexp.Regexp
	methodName string
	httpMethod string // "" = 任意, "GET" / "POST" = 限定
}

// httpMethodPrefix 检测 method_name 是否以 HTTP verb 前缀开头,返回 (verb, ok)。
func httpMethodPrefix(s string) (string, bool) {
	for _, v := range []string{"GET ", "POST ", "PUT ", "DELETE ", "PATCH ", "HEAD ", "OPTIONS "} {
		if strings.HasPrefix(s, v) {
			return strings.TrimSpace(v), true
		}
	}
	return "", false
}

func NewREST(name string, patterns []map[string]string) (*REST, error) {
	if len(patterns) == 0 {
		return nil, fmt.Errorf("rest extractor %q: url_patterns must be non-empty", name)
	}
	out := make([]restPattern, 0, len(patterns))
	for i, p := range patterns {
		patStr := p["pattern"]
		methodName := p["method_name"]
		if patStr == "" {
			return nil, fmt.Errorf("rest extractor %q: url_patterns[%d].pattern empty", name, i)
		}
		if methodName == "" {
			return nil, fmt.Errorf("rest extractor %q: url_patterns[%d].method_name empty", name, i)
		}
		re, err := regexp.Compile(patStr)
		if err != nil {
			return nil, fmt.Errorf("rest extractor %q: url_patterns[%d] invalid regex: %w", name, i, err)
		}
		verb, _ := httpMethodPrefix(methodName)
		out = append(out, restPattern{
			regex:      re,
			methodName: methodName,
			httpMethod: verb,
		})
	}
	return &REST{name: name, patterns: out}, nil
}

func (r *REST) Name() string { return r.name }

func (r *REST) Extract(req *http.Request, _ []byte) ([]Result, bool) {
	path := req.URL.Path
	for _, p := range r.patterns {
		if p.httpMethod != "" && p.httpMethod != req.Method {
			continue
		}
		if p.regex.MatchString(path) {
			return []Result{{
				Protocol:   "rest",
				MethodName: p.methodName,
				RequestID:  "",
				BatchIdx:   0,
			}}, true
		}
	}
	return nil, false
}
