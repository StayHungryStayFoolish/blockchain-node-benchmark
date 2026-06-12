# Blockchain Node Benchmark — Kubernetes Deployment

DaemonSet that runs `monitoring/cgroup_collector.py` on every node, reading
host `/proc` + `/sys` + cgroupfs counters via hostPath volumes.

## Support Status

This directory provides the Kubernetes monitoring deployment path for nodes
running in GKE, EKS, or self-managed Kubernetes clusters. It is intended for
operators who already manage the target cluster and have the permissions needed
to deploy node-level monitoring workloads.

Current repository validation covers:

- DaemonSet, ConfigMap, ServiceAccount, ClusterRole, and ClusterRoleBinding
  static structure.
- runtime path resolution for VM, Docker, and Kubernetes modes.
- cgroup v1/v2 collector behavior.
- Kubernetes API client, Pod/PVC/PV/device mapping, and kubelet
  `/stats/summary` fallback with mocked API servers.
- integration from `config/config_loader.sh` into `monitoring/cgroup_collector.py`.

Not covered in this repository because no live cluster is available here:

- real `kubectl apply` on GKE, EKS, or a self-managed Kubernetes cluster.
- provider admission-policy behavior for privileged or hostPath workloads.
- production RBAC approval in a customer cluster.
- live PV-to-host-device mapping against real cloud volumes.

Treat this as a ready-to-adapt deployment template plus test harness, not as a
claim that a specific managed cluster has already been validated end to end.

## Before Running the Framework Entry Command

For VM or bare-metal Linux targets, users can configure `config/user_config.sh`
and run `./blockchain_node_benchmark.sh --quick` directly.

For GKE, EKS, or self-managed Kubernetes targets, there is an extra
cluster-side setup step. The framework entry command does **not** apply these
manifests, create a ServiceAccount, grant RBAC, mount host paths, or start a
DaemonSet automatically. Those actions must be reviewed and performed by the
cluster operator before benchmark traffic is started.

Minimum Kubernetes workflow:

1. Build and push the collector image, or edit `04-daemonset.yaml` to use an
   image already available in your registry.
2. Review `03-configmap.yaml` and set `DEPLOYMENT_MODE` to `k8s_gke`,
   `k8s_eks`, or `k8s_other`.
3. Keep `HOST_PROC`, `HOST_SYS`, `HOST_ROOT`, and `TARGET_CGROUP` aligned with
   the DaemonSet host mounts and the target node/container you want to observe.
4. Have the cluster operator approve the ServiceAccount, RBAC, `hostPath`,
   `hostPID`, and `securityContext` settings.
5. Apply `deploy/k8s/` and verify the DaemonSet logs emit the cgroup CSV header
   plus periodic data rows.
6. Run the benchmark entry command from the selected runner only after the
   collector path has been verified.

This separation is intentional: the benchmark framework can generate workload
and reports, but it should not silently change Kubernetes cluster permissions or
node-level security settings.

## Kubernetes Operator Runbook

Use this command flow for GKE, EKS, and self-managed Kubernetes. The commands
show what to run, what should happen, and when it is safe to continue.

### 1. Confirm the target cluster

```bash
kubectl config current-context
kubectl get nodes -o wide
kubectl auth can-i create daemonsets.apps --all-namespaces
kubectl auth can-i create clusterroles
kubectl auth can-i get nodes/proxy

# Or run the bundled preflight helper:
deploy/k8s/validate.sh --preflight
```

What happens:

- `current-context` confirms which cluster will receive the collector.
- `get nodes` confirms the target nodes are visible and Linux nodes exist.
- `auth can-i` gives an early signal for RBAC and kubelet stats-summary access.

Next step:

- If any required permission is denied, have the cluster operator review
  `02-serviceaccount-rbac.yaml` and the cluster admission policy before
  applying the manifests.

### 2. Build and publish the collector image

```bash
export REGISTRY="REGISTRY_OR_REPOSITORY"
export IMAGE="${REGISTRY}/blockchain-node-benchmark/collector:latest"

docker build -t "${IMAGE}" -f deploy/k8s/Dockerfile .
docker push "${IMAGE}"
```

What happens:

- The collector image packages this repository at `/opt/blockchain-bench`.
- The DaemonSet will use the image to run `monitoring/cgroup_collector.py` on
  every Kubernetes node.

Next step:

- Patch `04-daemonset.yaml` to use the image you published:

```bash
sed -i.bak "s#blockchain-node-benchmark/collector:latest#${IMAGE}#g" \
  deploy/k8s/04-daemonset.yaml
```

### 3. Select the Kubernetes deployment mode

```bash
# Choose exactly one:
MODE="k8s_gke"      # GKE Standard or approved GKE privileged workload path
# MODE="k8s_eks"    # EKS
# MODE="k8s_other"  # Self-managed Kubernetes or other providers

kubectl apply -f deploy/k8s/01-namespace.yaml
kubectl -n blockchain-bench create configmap blockchain-bench-config \
  --from-literal=HOST_PROC=/host/proc \
  --from-literal=HOST_SYS=/host/sys \
  --from-literal=HOST_ROOT=/host \
  --from-literal=DEPLOYMENT_MODE="${MODE}" \
  --from-literal=DEPLOYMENT_PLATFORM=auto \
  --from-literal=COLLECTION_INTERVAL_SEC=5 \
  --from-literal=TARGET_CGROUP=/ \
  --from-literal=LOG_LEVEL=1 \
  --dry-run=client -o yaml | kubectl apply -f -
```

What happens:

- `DEPLOYMENT_MODE` tells the collector which runtime path to use.
- `TARGET_CGROUP=/` records whole-node cgroup counters. For per-workload
  attribution, replace it with the target Pod or systemd cgroup path after you
  identify the correct path on the node.

Next step:

- Keep `HOST_PROC`, `HOST_SYS`, and `HOST_ROOT` aligned with the hostPath mounts
  in `04-daemonset.yaml`.

### 4. Apply RBAC and the DaemonSet

```bash
kubectl apply -f deploy/k8s/02-serviceaccount-rbac.yaml
kubectl apply -f deploy/k8s/04-daemonset.yaml

kubectl rollout status -n blockchain-bench ds/blockchain-bench-collector
kubectl get pods -n blockchain-bench -o wide
```

What happens:

- Kubernetes creates one collector Pod per eligible Linux node.
- The collector reads host `/proc`, `/sys`, `/dev`, and `/` through hostPath
  mounts and emits cgroup metrics as CSV rows.

Next step:

- If Pods are blocked by admission policy, check whether the cluster allows
  `hostPID`, `hostPath`, and the configured `securityContext`.

### 5. Verify collector output before running benchmark traffic

```bash
# Recommended bundled validation:
deploy/k8s/validate.sh --post-deploy

# Equivalent manual checks:
kubectl logs -n blockchain-bench ds/blockchain-bench-collector --tail=20

POD="$(kubectl get pods -n blockchain-bench \
  -l app.kubernetes.io/component=collector \
  -o jsonpath='{.items[0].metadata.name}')"

kubectl exec -n blockchain-bench "${POD}" -- \
  python3 /opt/blockchain-bench/monitoring/cgroup_collector.py --header

kubectl exec -n blockchain-bench "${POD}" -- \
  python3 /opt/blockchain-bench/monitoring/cgroup_collector.py --data
```

What happens:

- `logs` should show the CSV header followed by periodic data rows.
- `--header` verifies the collector schema.
- `--data` verifies the host mounts and cgroup counters are readable.
- `deploy/k8s/validate.sh --post-deploy` runs the rollout, logs, `--header`,
  `--data`, and CSV column-count checks in one command.

Next step:

- Only continue to benchmark execution after `--data` returns one CSV row with
  the same number of columns as the header.

### 6. Run the benchmark entry command

Run the benchmark from the selected runner after the collector path is healthy.
For example, on a Linux runner with access to the target node RPC endpoint:

```bash
# In config/user_config.sh, configure at least:
#   LOCAL_RPC_URL
#   BLOCKCHAIN_NODE
#   BLOCKCHAIN_PROCESS_NAMES
#   CLOUD_PROVIDER / CLOUD_REGION / INSTANCE_TYPE if you want report metadata

./blockchain_node_benchmark.sh --quick
```

What happens:

- The framework generates Vegeta traffic, proxy method attribution, monitoring
  CSV files, charts, and the HTML report.
- In Kubernetes mode, the cluster-side collector supplies the cgroup/container
  resource signal; the benchmark entry command still owns workload generation
  and report generation.

Next step:

- Review the generated HTML report and verify that cgroup or Kubernetes-related
  resource fields are populated. Empty fields usually mean the collector was not
  deployed, `TARGET_CGROUP` does not match the workload, or the benchmark runner
  cannot consume the expected monitoring output.

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
- Permission to run a DaemonSet with hostPath mounts for `/proc`, `/sys`, `/dev`,
  and `/`.
- Permission to use `hostPID` and the required `securityContext` for the
  collector workload.
- A ServiceAccount/RBAC setup that can read Pods, PVCs, PVs, Nodes, Endpoints,
  and `nodes/proxy` for kubelet stats-summary access.

The manifests include the required Kubernetes objects, but cluster operators
should review and approve them according to their own policy. This project does
not attempt to teach cluster permission administration; it assumes the operator
can apply or adapt the manifests.

## Provider Notes

- **GKE Standard**: expected to be the easiest GKE mode for this DaemonSet
  because node-level monitoring commonly needs host mounts and privileged or
  capability-based access.
- **GKE Autopilot**: privileged containers and host namespace access are
  restricted by default. If your cluster is Autopilot, review your organization's
  privileged workload policy before using this DaemonSet.
- **EKS**: DaemonSet ServiceAccount permissions apply to Pods on every node.
  Keep the provided RBAC read-only and narrow, and have the platform owner
  review it before deployment.
- **Self-managed Kubernetes**: ensure hostPath mounts, cgroup visibility, and
  kubelet stats-summary access are enabled by cluster policy.

Official references:

- Kubernetes DaemonSet: https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/
- Kubernetes node metrics and Summary API: https://kubernetes.io/docs/reference/instrumentation/node-metrics/
- Kubernetes security context: https://kubernetes.io/docs/tasks/configure-pod-container/security-context/
- GKE Autopilot security measures: https://cloud.google.com/kubernetes-engine/docs/concepts/autopilot-security
- Amazon EKS RBAC hardening: https://docs.aws.amazon.com/eks/latest/userguide/rbac-hardening.html

## Image

The DaemonSet expects `blockchain-node-benchmark/collector:latest` by default. Either:

1. **Build + push to your registry** (production):
   ```bash
   # In repo root (must contain config/ monitoring/ utils/)
   docker build -t REGISTRY/blockchain-node-benchmark/collector:latest \
       -f deploy/k8s/Dockerfile .
   docker push REGISTRY/blockchain-node-benchmark/collector:latest
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

## Pitfalls

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
- Real cluster apply: pending; verify on your GKE cluster before production use
