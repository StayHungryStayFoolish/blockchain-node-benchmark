#!/bin/bash
# =====================================================================
# lib/proxy_lifecycle.sh
# W2 RPC proxy lifecycle helpers used by blockchain_node_benchmark.sh.
#
# Public API:
#   proxy_should_skip            — return 0 (true) if proxy phase should be skipped
#   start_rpc_proxy              — Phase 2.5 implementation
#   stop_rpc_proxy               — Phase 4.5 implementation
#
# Required env (set by main entry):
#   SCRIPT_DIR, LOGS_DIR, LOCAL_RPC_URL, BLOCKCHAIN_NODE
#
# Exports on success:
#   PROXY_ENABLED=1
#   PROXY_PID=<pid>
#   PROXY_LISTEN_PORT=18545
#   PROXY_METHOD_CSV=$LOGS_DIR/proxy_method.csv
#   ORIGINAL_LOCAL_RPC_URL=<previous LOCAL_RPC_URL>
#   LOCAL_RPC_URL=http://localhost:18545   (so vegeta traffic flows through proxy)
#
# Skip switches (back-compat):
#   --no-proxy CLI flag (consumed by main entry, exports SKIP_RPC_PROXY=1)
#   NO_PROXY_LAYER=1 or SKIP_RPC_PROXY=1
#   (Intentionally NOT using NO_PROXY which is an HTTP-client convention.)
# =====================================================================

PROXY_LISTEN_PORT="${PROXY_LISTEN_PORT:-18545}"

proxy_should_skip() {
    if [[ "${NO_PROXY_LAYER:-0}" == "1" || "${SKIP_RPC_PROXY:-0}" == "1" ]]; then
        return 0
    fi
    return 1
}

_proxy_log_path() {
    echo "${LOGS_DIR}/rpc_proxy.log"
}

_proxy_binary_path() {
    echo "${SCRIPT_DIR}/tools/proxy/proxy"
}

_proxy_try_build() {
    local src_dir="${SCRIPT_DIR}/tools/proxy"
    if [[ ! -d "$src_dir" ]]; then
        return 1
    fi
    if ! command -v go >/dev/null 2>&1; then
        return 1
    fi
    echo "🔨 Attempting to build proxy binary..." >&2
    ( cd "$src_dir" && go build -o proxy ./cmd/proxy ) >/dev/null 2>&1
    return $?
}

start_rpc_proxy() {
    if proxy_should_skip; then
        echo "⏭️  RPC proxy disabled (NO_PROXY_LAYER/SKIP_RPC_PROXY set) — skipping Phase 2.5"
        return 0
    fi

    local bin
    bin="$(_proxy_binary_path)"
    if [[ ! -x "$bin" ]]; then
        if ! _proxy_try_build; then
            echo "⚠️  Proxy binary not found at $bin and build failed — skipping proxy (per-method attribution disabled)"
            return 0
        fi
    fi

    local chain_file="${SCRIPT_DIR}/config/chains/${BLOCKCHAIN_NODE:-solana}.json"
    if [[ ! -f "$chain_file" ]]; then
        echo "⚠️  Chain template not found: $chain_file — skipping proxy"
        return 0
    fi

    local sink_csv="${LOGS_DIR}/proxy_method.csv"
    local self_csv="${LOGS_DIR}/proxy_self.csv"
    local log_file
    log_file="$(_proxy_log_path)"

    # Clear any stale sink so the > 1 line check in stop is meaningful.
    rm -f "$sink_csv" "$self_csv" 2>/dev/null || true

    echo "🚀 Starting RPC proxy: listen=:${PROXY_LISTEN_PORT} upstream=${LOCAL_RPC_URL} chain=${BLOCKCHAIN_NODE:-solana}"

    PROXY_SINK_FORMAT="csv" \
    PROXY_SINK_PATH="$sink_csv" \
    PROXY_SELF_PATH="$self_csv" \
    nohup "$bin" \
        -chain="$chain_file" \
        -upstream="$LOCAL_RPC_URL" \
        -listen=":${PROXY_LISTEN_PORT}" \
        >"$log_file" 2>&1 &
    local pid=$!

    # Health-check: tcp-connect to :PROXY_LISTEN_PORT for up to 5 seconds.
    local healthy=0 i
    for i in 1 2 3 4 5; do
        sleep 1
        if ! kill -0 "$pid" 2>/dev/null; then
            break
        fi
        if (exec 3<>"/dev/tcp/127.0.0.1/${PROXY_LISTEN_PORT}") 2>/dev/null; then
            exec 3<&- 3>&- 2>/dev/null || true
            healthy=1
            break
        fi
    done

    if [[ $healthy -ne 1 ]]; then
        echo "⚠️  Proxy failed to become healthy on :${PROXY_LISTEN_PORT} (see $log_file) — continuing without proxy"
        kill -TERM "$pid" 2>/dev/null || true
        return 0
    fi

    export PROXY_ENABLED=1
    export PROXY_PID=$pid
    export PROXY_METHOD_CSV="$sink_csv"
    export ORIGINAL_LOCAL_RPC_URL="$LOCAL_RPC_URL"
    export LOCAL_RPC_URL="http://localhost:${PROXY_LISTEN_PORT}"
    echo "✅ RPC proxy healthy (pid=$pid). Traffic redirected: LOCAL_RPC_URL=$LOCAL_RPC_URL"
    echo "   PROXY_METHOD_CSV=$PROXY_METHOD_CSV"
}

stop_rpc_proxy() {
    if [[ "${PROXY_ENABLED:-0}" != "1" ]]; then
        return 0
    fi

    echo "🛑 Stopping RPC proxy (pid=${PROXY_PID})"
    if [[ -n "${PROXY_PID:-}" ]] && kill -0 "$PROXY_PID" 2>/dev/null; then
        kill -TERM "$PROXY_PID" 2>/dev/null || true
        local waited=0
        while kill -0 "$PROXY_PID" 2>/dev/null && [[ $waited -lt 5 ]]; do
            sleep 1
            waited=$((waited + 1))
        done
        if kill -0 "$PROXY_PID" 2>/dev/null; then
            echo "   Proxy did not exit after SIGTERM, sending SIGKILL"
            kill -9 "$PROXY_PID" 2>/dev/null || true
        fi
    fi

    # Restore upstream URL for any later phases.
    if [[ -n "${ORIGINAL_LOCAL_RPC_URL:-}" ]]; then
        export LOCAL_RPC_URL="$ORIGINAL_LOCAL_RPC_URL"
        echo "   Restored LOCAL_RPC_URL=$LOCAL_RPC_URL"
    fi

    local sink_csv="${PROXY_METHOD_CSV:-${LOGS_DIR}/proxy_method.csv}"
    if [[ -f "$sink_csv" ]]; then
        local lines
        lines=$(wc -l < "$sink_csv" 2>/dev/null || echo 0)
        if [[ "$lines" -gt 1 ]]; then
            echo "✅ proxy_method.csv produced: $sink_csv ($lines lines)"
        else
            echo "⚠️  proxy_method.csv exists but has only $lines line(s) — per-method data may be empty"
        fi
    else
        echo "⚠️  proxy_method.csv not found at $sink_csv — per-method attribution unavailable"
    fi

    # Mark phase 2.5 as inactive so cleanup_framework doesn't try twice.
    export PROXY_ENABLED=0
}
