# =====================================================================
# blockchain-node-benchmark/collector  —  K8s DaemonSet image
# =====================================================================
# Production-grade image for `deploy/k8s/04-daemonset.yaml`.
#
# Design:
#   - Pure-stdlib monitoring stack (verified by ast.walk of cgroup_collector.py,
#     pod_device_mapper.py, kubelet_stats_client.py, k8s_api_client.py —
#     zero third-party PyPI deps). So we use python:3.11-slim with NO pip install.
#   - Multi-arch capable (linux/amd64 + linux/arm64) — Docker BuildKit picks
#     base automatically. Override with --platform if needed.
#   - Read-only root filesystem compatible. /opt/blockchain-bench is mounted
#     ro by the DaemonSet (config in 04-daemonset.yaml securityContext).
#   - No CMD baked — the DaemonSet sets the command per pod (cgroup_collector
#     vs monitoring_coordinator diagnostics). Image is a "binary host", not
#     a "service entry point".
#
# Build (local kind):
#   docker build -t blockchain-node-benchmark/collector:latest .
#   kind load docker-image blockchain-node-benchmark/collector:latest
#
# Build (GAR push):
#   IMAGE=us-central1-docker.pkg.dev/PROJECT/REPO/collector:latest
#   docker build -t "$IMAGE" .
#   docker push "$IMAGE"
# =====================================================================

FROM python:3.11-slim

# Image labels for provenance (Kubernetes/GAR tooling reads these)
LABEL org.opencontainers.image.title="blockchain-node-benchmark/collector"
LABEL org.opencontainers.image.description="DaemonSet collector for cgroup + K8s pod monitoring"
LABEL org.opencontainers.image.source="https://github.com/StayHungryStayFoolish/blockchain-node-benchmark"
LABEL org.opencontainers.image.licenses="Apache-2.0"

# bash needed for monitoring_coordinator.sh and the test scripts.
# curl useful for liveness probes / debugging from inside pod.
# tini for proper PID 1 signal handling (DaemonSet pods get SIGTERM
# on rolling update; without tini the python child orphans).
RUN apt-get update && apt-get install -y --no-install-recommends \
        bash \
        curl \
        tini \
        ca-certificates \
        jq \
        bc \
        gawk \
        sysstat \
        net-tools \
        netcat-openbsd \
        ethtool \
        procps \
        iproute2 \
        coreutils \
    && rm -rf /var/lib/apt/lists/*

# Copy the entire repo to /opt/blockchain-bench. The DaemonSet mounts this
# read-only, then bind-mounts host /proc /sys /dev under /host/* per
# 04-daemonset.yaml convention.
WORKDIR /opt/blockchain-bench
COPY . /opt/blockchain-bench/

# Make all .sh scripts executable (git might lose the +x bit on Windows
# checkouts; defensive chmod).
RUN find /opt/blockchain-bench -name '*.sh' -exec chmod +x {} \;

# Default PYTHONPATH so cross-file imports work (kubelet_stats_client
# imports k8s_api_client as a sibling module).
ENV PYTHONPATH=/opt/blockchain-bench/monitoring:/opt/blockchain-bench
ENV PYTHONUNBUFFERED=1

# Health-check command — verify the collector can at least print the
# cgroup header (no IO, no privileges needed). Pod readiness probe in
# 04-daemonset.yaml uses --data which IS privileged; this is for local
# `docker run` smoke tests.
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python3 /opt/blockchain-bench/monitoring/cgroup_collector.py --header > /dev/null

# tini is PID 1; the DaemonSet template's `command:` becomes tini's argv[1+].
ENTRYPOINT ["/usr/bin/tini", "--"]
# Default CMD just verifies the image works; real DaemonSet overrides this.
CMD ["python3", "/opt/blockchain-bench/monitoring/cgroup_collector.py", "--header"]
