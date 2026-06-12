.PHONY: build test perf bench clean lint

BIN := proxy
PKG := ./...

build:
	go build -o $(BIN) ./cmd/proxy

test:
	go test -race -count=1 $(PKG)

# Perf tests require -tags=perf without -race because the race detector skews QPS.
perf:
	go test -tags=perf -count=1 -run=TestPerformanceGate ./internal/proxy/

bench:
	go test -tags=perf -bench=. -benchmem -run=^$$ $(PKG)

lint:
	gofmt -l . && go vet $(PKG)

clean:
	rm -f $(BIN)
