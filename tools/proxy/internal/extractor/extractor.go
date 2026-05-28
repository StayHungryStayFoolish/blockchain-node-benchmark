// Package extractor 定义 per-method 提取器的接口和工厂。
//
// spec §1.7 锁定 2 个 protocol:
//   - json_rpc: 从 HTTP body 抽 method/id/params
//   - rest:     从 URL path + method 用 regex 匹配 method_name
//
// 多个 extractor 串接尝试,第一个返回 ok 即停(命中优先级 = 声明顺序)。
package extractor

import (
	"net/http"
)

// Result 是单次提取结果。一次 HTTP 请求可能产生多个 Result(json_rpc batch=split)。
type Result struct {
	Protocol   string // "json_rpc" | "rest"
	MethodName string // 用于归因 join 的稳定 method 标识
	RequestID  string // json_rpc 模式的请求 id (string 化);rest 模式为空
	BatchIdx   int    // batch 中第几条 (0 起);非 batch 为 0
}

// Extractor 是 per-method 提取器接口。
// Extract 返回 (results, ok)。ok=false 表示这个 extractor 不匹配当前请求,
// 调用方应尝试下一个 extractor。
type Extractor interface {
	Name() string
	Extract(req *http.Request, body []byte) ([]Result, bool)
}

// Chain 把多个 extractor 串成一条匹配链,按声明顺序尝试。
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
