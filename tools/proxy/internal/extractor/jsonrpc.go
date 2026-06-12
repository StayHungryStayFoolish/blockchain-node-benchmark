package extractor

import (
	"encoding/json"
	"net/http"
	"regexp"
	"strconv"
)

// JSONRPC implements spec §1.7 json_rpc mode. method_source=body.method and
// id_source=body.id are fixed. url_pattern controls routing matches, and
// batch_handling controls batch behavior.
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

// jsonRPCRequest keeps ID as interface{} so stringifyID can preserve caller IDs.
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

	// Sniff single vs batch: the first non-space '[' means batch.
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
		// Treat the whole batch as one method="__batch__" record.
		return []Result{{
			Protocol:   "json_rpc",
			MethodName: "__batch__",
			RequestID:  "",
			BatchIdx:   0,
		}}, true
	}
	// BatchSplit is the default.
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
		// Render integer IDs without a decimal suffix.
		if v == float64(int64(v)) {
			return strconv.FormatInt(int64(v), 10)
		}
		return strconv.FormatFloat(v, 'f', -1, 64)
	case bool:
		return strconv.FormatBool(v)
	}
	// Fallback: JSON serialization.
	b, _ := json.Marshal(id)
	return string(b)
}
