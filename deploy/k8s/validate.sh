#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-blockchain-bench}"
DAEMONSET="${DAEMONSET:-blockchain-bench-collector}"
LABEL_SELECTOR="${LABEL_SELECTOR:-app.kubernetes.io/component=collector}"
TIMEOUT="${TIMEOUT:-120s}"

usage() {
    cat <<'USAGE'
Usage:
  deploy/k8s/validate.sh [--preflight|--post-deploy]

Modes:
  --preflight     Validate kubectl context and permissions before applying manifests.
  --post-deploy   Validate DaemonSet rollout, logs, and collector CSV output.
                  This is the default mode.

Environment overrides:
  NAMESPACE       Kubernetes namespace. Default: blockchain-bench
  DAEMONSET       Collector DaemonSet name. Default: blockchain-bench-collector
  LABEL_SELECTOR  Collector Pod label selector. Default: app.kubernetes.io/component=collector
  TIMEOUT         Rollout timeout. Default: 120s
USAGE
}

log() {
    printf '[INFO] %s\n' "$*"
}

warn() {
    printf '[WARN] %s\n' "$*" >&2
}

fail() {
    printf '[ERROR] %s\n' "$*" >&2
    exit 1
}

need_cmd() {
    command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

auth_can_i() {
    local verb="$1"
    local resource="$2"
    if kubectl auth can-i "$verb" "$resource" >/tmp/k8s-can-i.out 2>/tmp/k8s-can-i.err; then
        local result
        result="$(cat /tmp/k8s-can-i.out)"
        if [[ "$result" == "yes" ]]; then
            log "RBAC check passed: $verb $resource"
        else
            warn "RBAC check returned '$result': $verb $resource"
        fi
    else
        warn "RBAC check failed to run: $verb $resource ($(tr '\n' ' ' </tmp/k8s-can-i.err))"
    fi
}

run_preflight() {
    need_cmd kubectl

    log "Current kubectl context:"
    kubectl config current-context

    log "Cluster nodes:"
    kubectl get nodes -o wide

    auth_can_i create daemonsets.apps
    auth_can_i create clusterroles
    auth_can_i get nodes/proxy
    auth_can_i list pods
    auth_can_i list persistentvolumes

    log "Preflight complete. If required permissions are denied, have the cluster operator review deploy/k8s/02-serviceaccount-rbac.yaml and admission policy."
}

first_collector_pod() {
    kubectl get pods -n "$NAMESPACE" -l "$LABEL_SELECTOR" \
        -o jsonpath='{.items[0].metadata.name}' 2>/dev/null
}

csv_field_count() {
    awk -F',' '{print NF; exit}'
}

run_post_deploy() {
    need_cmd kubectl

    log "Checking namespace: $NAMESPACE"
    kubectl get namespace "$NAMESPACE" >/dev/null

    log "Checking DaemonSet rollout: $DAEMONSET"
    kubectl rollout status -n "$NAMESPACE" "ds/$DAEMONSET" --timeout="$TIMEOUT"

    log "Collector Pods:"
    kubectl get pods -n "$NAMESPACE" -l "$LABEL_SELECTOR" -o wide

    local pod
    pod="$(first_collector_pod)"
    [[ -n "$pod" ]] || fail "No collector pod found in namespace $NAMESPACE with selector $LABEL_SELECTOR"
    log "Using collector pod: $pod"

    log "Recent collector logs:"
    kubectl logs -n "$NAMESPACE" "$pod" --tail=20 || warn "Unable to read collector logs from pod $pod"

    log "Running collector --header inside the pod"
    local header
    header="$(kubectl exec -n "$NAMESPACE" "$pod" -- \
        python3 /opt/blockchain-bench/monitoring/cgroup_collector.py --header)"
    printf '%s\n' "$header"

    log "Running collector --data inside the pod"
    local data
    data="$(kubectl exec -n "$NAMESPACE" "$pod" -- \
        python3 /opt/blockchain-bench/monitoring/cgroup_collector.py --data)"
    printf '%s\n' "$data"

    local header_cols data_cols
    header_cols="$(printf '%s\n' "$header" | csv_field_count)"
    data_cols="$(printf '%s\n' "$data" | csv_field_count)"

    [[ "$header_cols" == "$data_cols" ]] || fail "Collector CSV field mismatch: header=$header_cols data=$data_cols"

    log "Collector CSV schema is consistent: $header_cols columns"
    log "Post-deploy validation complete. It is now safe to run the benchmark entry command from the selected runner."
}

MODE="--post-deploy"
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
elif [[ "${1:-}" == "--preflight" || "${1:-}" == "--post-deploy" ]]; then
    MODE="$1"
elif [[ $# -gt 0 ]]; then
    usage >&2
    exit 2
fi

case "$MODE" in
    --preflight)
        run_preflight
        ;;
    --post-deploy)
        run_post_deploy
        ;;
esac
