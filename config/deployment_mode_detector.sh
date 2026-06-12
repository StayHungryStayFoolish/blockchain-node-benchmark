#!/bin/bash
# =====================================================================
# Blockchain Node Benchmark Framework - Deployment Mode Detector
# =====================================================================
# Purpose: Detect runtime environment (VM / Docker / K8s), orthogonal to
#          DEPLOYMENT_PLATFORM (cloud provider: gcp / aws / other).
#
# Output: DEPLOYMENT_MODE env var ∈ {vm_bare, vm_systemd, docker,
#         k8s_eks, k8s_gke, k8s_other}
#
# Detection order:
#   1. Explicit DEPLOYMENT_MODE env (user override)  → trust it
#   2. /proc/1/cgroup contains "kubepods"            → k8s_*
#      2a. /etc/eks-release exists                   → k8s_eks
#      2b. /etc/gke-* exists OR GCE metadata "gke"   → k8s_gke
#      2c. else                                      → k8s_other
#   3. /.dockerenv exists                            → docker
#   4. systemctl available AND known node unit found → vm_systemd
#   5. default                                       → vm_bare
#
# Side effects (env vars exported):
#   DEPLOYMENT_MODE              one of the 6 modes above
#   DEPLOYMENT_MODE_DETECTED     true (sentinel for idempotency)
#   DEPLOYMENT_MODE_SOURCE       "env" | "kubepods" | "dockerenv" | "systemd" | "default"
#
# Idempotent: safe to source multiple times. Re-runs only if env is unset.
#
# Companion to baseline detect_deployment_platform() in config_loader.sh.
# That function answers "which cloud?"; this one answers "which runtime?".
# Together they form a (platform, mode) matrix used by cloud_variants/ and
# runtime_paths.sh.
# =====================================================================

# Default: auto-detect unless user override
DEPLOYMENT_MODE=${DEPLOYMENT_MODE:-"auto"}

# Blockchain process names are also used as systemd unit-name prefixes during
# deployment-mode auto-detection. In most real deployments the process binary
# and unit prefix overlap, for example `agave-validator.service` ->
# `agave-validator` or `geth.service` -> `geth`.
#
# Keep this fallback so deployment_mode_detector.sh still works in standalone
# tests and direct sourcing.
if ! declare -p BLOCKCHAIN_PROCESS_NAMES >/dev/null 2>&1; then
    BLOCKCHAIN_PROCESS_NAMES=()
fi

detect_deployment_mode() {
    # Idempotency guard
    if [[ "${DEPLOYMENT_MODE_DETECTED:-}" == "true" && "${DEPLOYMENT_MODE:-auto}" != "auto" ]]; then
        echo "🔧 Deployment mode already detected: $DEPLOYMENT_MODE (source=$DEPLOYMENT_MODE_SOURCE)" >&2
        return 0
    fi

    # Step 1: explicit override (anything other than "auto")
    if [[ "$DEPLOYMENT_MODE" != "auto" ]]; then
        DEPLOYMENT_MODE_SOURCE="env"
        echo "🔧 Using manually configured deployment mode: $DEPLOYMENT_MODE" >&2
        _deployment_mode_validate || return 1
        _deployment_mode_export
        return 0
    fi

    echo "🔍 Auto-detecting deployment mode..." >&2

    # Step 2: K8s detection via /proc/1/cgroup (works for both cgroup v1 and v2)
    # kubepods appears in path for all CRI runtimes (containerd, cri-o, docker-shim)
    if [[ -r /proc/1/cgroup ]] && grep -q "kubepods" /proc/1/cgroup 2>/dev/null; then
        # Sub-classify K8s flavor
        if [[ -f /etc/eks-release ]]; then
            DEPLOYMENT_MODE="k8s_eks"
        elif compgen -G "/etc/gke-*" >/dev/null 2>&1; then
            DEPLOYMENT_MODE="k8s_gke"
        elif _deployment_mode_is_gke_metadata; then
            DEPLOYMENT_MODE="k8s_gke"
        else
            DEPLOYMENT_MODE="k8s_other"
        fi
        DEPLOYMENT_MODE_SOURCE="kubepods"
        echo "✅ K8s environment detected: $DEPLOYMENT_MODE" >&2
        _deployment_mode_export
        return 0
    fi

    # Step 3: Docker detection
    # /.dockerenv is the canonical marker; works for Docker Engine + Podman compat layer
    if [[ -f /.dockerenv ]]; then
        DEPLOYMENT_MODE="docker"
        DEPLOYMENT_MODE_SOURCE="dockerenv"
        echo "✅ Docker environment detected" >&2
        _deployment_mode_export
        return 0
    fi

    # Step 4: VM with systemd (look for node units we care about)
    #
    # Regex anatomy:
    #   ^\s*${unit}([-@]|\.service)
    #
    #   ^\s*           — systemctl list-units indents each row with 2 spaces
    #   ${unit}        — literal binary name, regex-escaped by shell
    #   ([-@]|\.service) — next char MUST be one of:
    #     -            → suffix variant: solana-validator-mainnet.service,
    #                                    geth-1.service, bor-validator.service
    #                    (covers ops conventions like <binary>-<env>.service)
    #     @            → systemd template instance: solana-validator@mainnet.service
    #     \.service    → bare unit: geth.service
    #
    # Anti-collision: requiring the trailing class means `geth` will NOT
    #   match lines starting with `bsc-geth` or `scroll-geth` (those have
    #   their own array entries). See tests/test_deployment_mode_detector.sh
    #   for the full 19-case matrix.
    #
    # Known limitation:
    #   This step only detects systemd-managed binaries. Raw process
    #   invocation (`./solana-validator &`) falls through to vm_bare. Users
    #   running unmanaged processes must manually `export DEPLOYMENT_MODE=vm_systemd`.
    #   Downstream impact is zero (runtime_paths.sh treats vm_bare and vm_systemd
    #   identically — both resolve to /proc and /sys), only telemetry label.
    if command -v systemctl >/dev/null 2>&1; then
        local unit
        local unit_prefix
        for unit in "${BLOCKCHAIN_PROCESS_NAMES[@]}"; do
            [[ -n "$unit" ]] || continue
            unit_prefix="${unit%.service}"
            [[ -n "$unit_prefix" ]] || continue
            # systemctl list-units exits 0 even when no match; check output
            # Prefix tolerance: systemd marks failed/not-loaded units with ● (U+25CF),
            # × (U+00D7), ↻ (U+21BB) etc. Plain \s does NOT match these UTF-8 glyphs,
            # so we accept any leading non-alphanumeric run.
            if systemctl list-units --all --no-legend --no-pager 2>/dev/null \
                    | grep -qE "^[^a-zA-Z0-9]*${unit_prefix}([-@]|\.service)" ; then
                DEPLOYMENT_MODE="vm_systemd"
                DEPLOYMENT_MODE_SOURCE="systemd:${unit_prefix}"
                echo "✅ VM + systemd environment detected (unit=$unit_prefix)" >&2
                _deployment_mode_export
                return 0
            fi
        done
    fi

    # Step 5: default to vm_bare
    DEPLOYMENT_MODE="vm_bare"
    DEPLOYMENT_MODE_SOURCE="default"
    echo "ℹ️  Default: assuming bare VM (no K8s, no Docker, no recognized systemd unit)" >&2
    _deployment_mode_export
    return 0
}

# Helper: GCE metadata "gke" check (used inside K8s nodes when /etc/gke-* missing)
# Uses GCP metadata server header (Metadata-Flavor: Google), 3s timeout per user's
# memory note (cloudtop sudo unavailable, network calls must be bounded).
_deployment_mode_is_gke_metadata() {
    local md_url="http://metadata.google.internal/computeMetadata/v1/instance/attributes/cluster-name"
    local result
    result=$(curl -s --max-time 3 --connect-timeout 2 \
        -H "Metadata-Flavor: Google" "$md_url" 2>/dev/null) || return 1
    [[ -n "$result" ]] && return 0
    return 1
}

# Helper: validate user-supplied DEPLOYMENT_MODE against allowed set
_deployment_mode_validate() {
    case "$DEPLOYMENT_MODE" in
        vm_bare|vm_systemd|docker|k8s_eks|k8s_gke|k8s_other)
            return 0
            ;;
        *)
            echo "❌ Invalid DEPLOYMENT_MODE: '$DEPLOYMENT_MODE'" >&2
            echo "   Allowed: vm_bare | vm_systemd | docker | k8s_eks | k8s_gke | k8s_other" >&2
            return 1
            ;;
    esac
}

# Helper: export final state
_deployment_mode_export() {
    DEPLOYMENT_MODE_DETECTED=true
    export DEPLOYMENT_MODE DEPLOYMENT_MODE_DETECTED DEPLOYMENT_MODE_SOURCE
    echo "📦 DEPLOYMENT_MODE=$DEPLOYMENT_MODE (source=$DEPLOYMENT_MODE_SOURCE)" >&2
}

# When sourced from config_loader.sh, do NOT auto-execute. The loader calls
# detect_deployment_mode explicitly at its detector dispatch point (L310).
# When executed directly (./deployment_mode_detector.sh), run the detector
# and print final state — useful for ops debugging.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if ! detect_deployment_mode; then
        # Validation failed (invalid DEPLOYMENT_MODE override) — propagate exit 1
        exit 1
    fi
    echo
    echo "Final state:"
    echo "  DEPLOYMENT_MODE=$DEPLOYMENT_MODE"
    echo "  DEPLOYMENT_MODE_SOURCE=$DEPLOYMENT_MODE_SOURCE"
    echo "  DEPLOYMENT_MODE_DETECTED=$DEPLOYMENT_MODE_DETECTED"
fi
