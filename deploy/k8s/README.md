# Blockchain Node Benchmark — Kubernetes Deployment

DaemonSet that runs `monitoring/cgroup_collector.py` on every node, reading
host `/proc` + `/sys` + cgroupfs counters via hostPath volumes.

## Files

| File | Purpose |
|---|---|
| `01-namespace.yaml`         | Dedicated `blockchain-bench` namespace + PSS=privileged |
| `02-serviceaccount-rbac.yaml` | SA + read-only ClusterRole (pods/PVC/PV/nodes/proxy) |
| `03-configmap.yaml`         | `HOST_PROC` / `HOST_SYS` / `COLLECTION_INTERVAL_SEC` defaults |
| `04-daemonset.yaml`         | DaemonSet — hostPID, privileged, 4 hostPath mounts, probes |

## Prerequisites

- Kubernetes 1.24+ (PSS labels)
- A registry holding the collector image — see "Image" below
- `kubectl` configured with apply rights on the cluster

## Image

The DaemonSet expects `blockchain-node-benchmark/collector:v1.3`. Either:

1. **Build + push to your registry** (production):
   ```bash
   # In repo root (must contain config/ monitoring/ utils/)
   docker build -t REGISTRY/blockchain-node-benchmark/collector:v1.3 \
       -f deploy/k8s/Dockerfile .
   docker push REGISTRY/blockchain-node-benchmark/collector:v1.3
   # then sed the image ref in 04-daemonset.yaml
   ```

2. **Development hot-reload via hostPath** (recommended for iterative work):
   On each node, `git clone` this repo at `/opt/blockchain-bench`, then
   patch the DaemonSet to add:
   ```yaml
   volumes:
     - name: repo
       hostPath: { path: /opt/blockchain-bench, type: Directory }
   containers:
     - volumeMounts:
         - { name: repo, mountPath: /opt/blockchain-bench }
   ```
   `git pull` on the node then `kubectl rollout restart ds/...` picks up
   new code in ~30 seconds without rebuilding any image.

## Apply

```bash
kubectl apply -f deploy/k8s/
kubectl rollout status -n blockchain-bench ds/blockchain-bench-collector
kubectl logs -f -n blockchain-bench ds/blockchain-bench-collector
```

Expected first log line (the CSV header):
```
cgroup_io_rbytes,cgroup_io_wbytes,...,cgroup_meta_source
```

Then one CSV row every `COLLECTION_INTERVAL_SEC` (default 5s).

## Tear Down

```bash
kubectl delete -f deploy/k8s/
# Or, to keep the namespace but remove workload:
kubectl delete ds,cm,sa,rolebinding -n blockchain-bench --all
```

## Static Validation

Before applying to a real cluster, run the static-validation suite (19 tests
covering YAML parse, kind coverage, cross-references, RBAC minimums, probe
commands, security settings, ConfigMap keys):

```bash
python3 tests/test_k8s_manifests.py
```

Should print `OK` with 19 tests passing.

## Pitfalls (from plan §S4)

1. **02-serviceaccount-rbac.yaml is a 3-document file** (SA + ClusterRole +
   ClusterRoleBinding via `---` separators). Some YAML linters complain
   "expected a single document"; K8s and `kubectl apply` handle multi-doc
   files natively. Don't split them.

2. **`privileged: true` is required on cgroup v1 nodes** (older RHEL,
   EKS 1.21- Bottlerocket) because blkio.* files are root-only without
   capability grants. Modern v2-only clusters can drop privileged and
   keep just `CAP_SYS_PTRACE` + `CAP_DAC_READ_SEARCH`.

3. **`hostPID: true` is required** to resolve `/proc/<host_pid>/cgroup`
   when `TARGET_CGROUP` resolves through a host PID. Without it the
   collector only sees its own container's PIDs in the Pod's PID namespace
   and `/proc/1/cgroup` points at the container's slice, not the host
   workload's slice.

4. **`terminationMessagePolicy: FallbackToLogsOnError`** ensures that if
   the collector crashes during pod startup, the last 80 lines of stderr
   appear in `kubectl get pod -o yaml`'s `.status.containerStatuses[].
   lastState.terminated.message` — vital for debugging when `kubectl logs`
   returns nothing.

5. **cgroup v2 user.slice scopes DO NOT expose `io.stat`** — only leaf
   systemd unit scopes do. For production attribution set `TARGET_CGROUP`
   to a specific unit (e.g. `/system.slice/geth.service`), not `/`.
   Default `/` reports node-wide totals, useful for sanity but not
   per-workload attribution.

## Verified

- Static validation: 19/19 tests pass on cloudtop (`tests/test_k8s_manifests.py`)
- Real cluster apply: **pending** (will be verified on GKE in S6/S7 stage)
