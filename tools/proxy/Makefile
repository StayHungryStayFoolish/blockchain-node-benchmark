.PHONY: build test perf bench clean lint

BIN := proxy
PKG := ./...

build:
	go build -o $(BIN) ./cmd/proxy

test:
	go test -race -count=1 $(PKG)

# perf 测试需要 -tags=perf (不带 -race, 因为 race detector 慢 5-10x 会让测试失真)
perf:
	go test -tags=perf -count=1 -run=TestPerformanceGate ./internal/proxy/

bench:
	go test -tags=perf -bench=. -benchmem -run=^$$ $(PKG)

lint:
	gofmt -l . && go vet $(PKG)

clean:
	rm -f $(BIN)
