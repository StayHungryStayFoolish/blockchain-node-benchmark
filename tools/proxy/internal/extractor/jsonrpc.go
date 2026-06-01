package extractor

import (
	"encoding/json"
	"net/http"
	"regexp"
	"strconv"
)

// JSONRPC 实现 spec §1.7 json_rpc 模式 (method_source=body.method,
// id_source=body.id 固定不变)。url_pattern 决定路由命中,
// batch_handling ∈ {reject, split, tag_batch} 控制 batch 行为。
type JSONRPC struct {
	name          string
	urlRegex      *regexp.Regexp
	batchHandling string // reject | split | tag_batch
}

const (
	BatchReject = "reject"
	BatchSplit  = "split"
	BatchTag    = "tag_batch"
)

func NewJSONRPC(name, urlPattern, batchHandling string) (*JSONRPC, error) {
	re, err := regexp.Compile(urlPattern)
	if err != nil {
		return nil, err
	}
	if batchHandling == "" {
		batchHandling = BatchSplit
	}
	switch batchHandling {
	case BatchReject, BatchSplit, BatchTag:
	default:
		batchHandling = BatchSplit
	}
	return &JSONRPC{
		name:          name,
		urlRegex:      re,
		batchHandling: batchHandling,
	}, nil
}

func (j *JSONRPC) Name() string { return j.name }

// jsonRPCRequest 用 json.Number 保留原始 id 表示(避免 int/float 丢精)。
type jsonRPCRequest struct {
	Method string      `json:"method"`
	ID     interface{} `json:"id"`
}

func (j *JSONRPC) Extract(req *http.Request, body []byte) ([]Result, bool) {
	if req.Method != http.MethodPost {
		return nil, false
	}
	if !j.urlRegex.MatchString(req.URL.Path) {
		return nil, false
	}
	if len(body) == 0 {
		return nil, false
	}

	// 嗅探单条 vs batch:第一个非空白字符 [ 即 batch
	for _, b := range body {
		if b == ' ' || b == '\t' || b == '\n' || b == '\r' {
			continue
		}
		if b == '[' {
			return j.extractBatch(body)
		}
		break
	}
	return j.extractSingle(body)
}

func (j *JSONRPC) extractSingle(body []byte) ([]Result, bool) {
	var r jsonRPCRequest
	if err := json.Unmarshal(body, &r); err != nil {
		return nil, false
	}
	if r.Method == "" {
		return nil, false
	}
	return []Result{{
		Protocol:   "json_rpc",
		MethodName: r.Method,
		RequestID:  stringifyID(r.ID),
		BatchIdx:   0,
	}}, true
}

func (j *JSONRPC) extractBatch(body []byte) ([]Result, bool) {
	switch j.batchHandling {
	case BatchReject:
		return nil, false
	case BatchTag:
		// 把整批当作 1 条 method="__batch__" 处理
		return []Result{{
			Protocol:   "json_rpc",
			MethodName: "__batch__",
			RequestID:  "",
			BatchIdx:   0,
		}}, true
	}
	// BatchSplit (默认)
	var batch []jsonRPCRequest
	if err := json.Unmarshal(body, &batch); err != nil {
		return nil, false
	}
	if len(batch) == 0 {
		return nil, false
	}
	results := make([]Result, 0, len(batch))
	for i, r := range batch {
		if r.Method == "" {
			continue
		}
		results = append(results, Result{
			Protocol:   "json_rpc",
			MethodName: r.Method,
			RequestID:  stringifyID(r.ID),
			BatchIdx:   i,
		})
	}
	if len(results) == 0 {
		return nil, false
	}
	return results, true
}

func stringifyID(id interface{}) string {
	switch v := id.(type) {
	case nil:
		return ""
	case string:
		return v
	case float64:
		// 整数 id 用 int 表示
		if v == float64(int64(v)) {
			return strconv.FormatInt(int64(v), 10)
		}
		return strconv.FormatFloat(v, 'f', -1, 64)
	case bool:
		return strconv.FormatBool(v)
	}
	// 兜底:JSON 序列化
	b, _ := json.Marshal(id)
	return string(b)
}
