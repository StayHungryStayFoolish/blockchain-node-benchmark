#!/usr/bin/env python3
"""
Static validation for deploy/k8s/*.yaml — runs without a real cluster.

Verifies:
  1. All YAML files parse (incl. multi-doc).
  2. Every K8s object has apiVersion + kind + metadata.name.
  3. Cross-references resolve:
       - DaemonSet.serviceAccountName  → existing ServiceAccount in same NS
       - DaemonSet.envFrom.configMapRef → existing ConfigMap in same NS
       - ClusterRoleBinding.subjects    → existing ServiceAccount
       - ClusterRoleBinding.roleRef     → existing ClusterRole
       - DaemonSet.volumeMounts[].name  → matching volume in DaemonSet.spec.volumes
  4. Container probes exec correct collector commands.
  5. RBAC has expected minimum verbs (get/list/watch on pods/pvc/pv).

Run:
  python3 tests/test_k8s_manifests.py
  # or
  python3 -m pytest tests/test_k8s_manifests.py -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Dict, List, Tuple

# yaml is in stdlib of PyYAML — should already be in the project venv
try:
    import yaml
except ImportError as e:  # pragma: no cover
    print(f"PyYAML not installed — {e}. Install with: pip install pyyaml")
    sys.exit(2)


ROOT = Path(__file__).resolve().parent.parent
K8S_DIR = ROOT / "deploy" / "k8s"


def load_all_docs() -> List[dict]:
    """Load every YAML doc across all *.yaml files in deploy/k8s/.

    K8s convention: one file may contain multiple `---`-separated docs
    (e.g. ServiceAccount + ClusterRole + ClusterRoleBinding together).
    """
    docs: List[dict] = []
    for p in sorted(K8S_DIR.glob("*.yaml")):
        with p.open() as f:
            for d in yaml.safe_load_all(f):
                if d is not None:
                    d["_source_file"] = p.name
                    docs.append(d)
    return docs


class TestYAMLParses(unittest.TestCase):
    def test_all_files_parse(self):
        docs = load_all_docs()
        self.assertGreaterEqual(len(docs), 6,
                                 "Expected ≥ 6 objects "
                                 "(NS, SA, CR, CRB, CM, DS)")

    def test_every_doc_has_apiversion_kind_name(self):
        for d in load_all_docs():
            self.assertIn("apiVersion", d,
                          f"missing apiVersion in {d.get('_source_file')}")
            self.assertIn("kind", d,
                          f"missing kind in {d.get('_source_file')}")
            self.assertIn("metadata", d,
                          f"missing metadata in {d.get('_source_file')}")
            self.assertIn("name", d["metadata"],
                          f"missing metadata.name in "
                          f"{d.get('_source_file')}/{d.get('kind')}")


class TestKindCoverage(unittest.TestCase):
    """Every required Kubernetes manifest kind must be present."""

    REQUIRED_KINDS = {"Namespace", "ServiceAccount", "ClusterRole",
                      "ClusterRoleBinding", "ConfigMap", "DaemonSet"}

    def test_all_required_kinds_present(self):
        kinds = {d["kind"] for d in load_all_docs()}
        missing = self.REQUIRED_KINDS - kinds
        self.assertFalse(missing,
                          f"Missing K8s kinds: {missing}. Found: {kinds}")


class TestCrossReferences(unittest.TestCase):
    """Verify every cross-object reference resolves."""

    def setUp(self):
        self.docs = load_all_docs()
        self.by_kind: Dict[str, List[dict]] = {}
        for d in self.docs:
            self.by_kind.setdefault(d["kind"], []).append(d)

    def _names(self, kind: str) -> set:
        return {d["metadata"]["name"] for d in self.by_kind.get(kind, [])}

    def test_namespace_referenced_by_namespaced_objects(self):
        """SA/CM/DS should live in the namespace we created."""
        ns_name = next(iter(self._names("Namespace")))
        for kind in ("ServiceAccount", "ConfigMap", "DaemonSet"):
            for d in self.by_kind.get(kind, []):
                self.assertEqual(d["metadata"].get("namespace"), ns_name,
                                 f"{kind}/{d['metadata']['name']} not in NS {ns_name}")

    def test_daemonset_serviceaccount_exists(self):
        for ds in self.by_kind.get("DaemonSet", []):
            sa_name = ds["spec"]["template"]["spec"].get("serviceAccountName")
            self.assertIsNotNone(sa_name,
                                  "DaemonSet missing serviceAccountName")
            self.assertIn(sa_name, self._names("ServiceAccount"),
                          f"DS refs missing SA: {sa_name}")

    def test_daemonset_configmap_envfrom_resolves(self):
        for ds in self.by_kind.get("DaemonSet", []):
            for c in ds["spec"]["template"]["spec"]["containers"]:
                for env in c.get("envFrom", []):
                    cm = env.get("configMapRef", {}).get("name")
                    if cm:
                        self.assertIn(cm, self._names("ConfigMap"),
                                      f"DS refs missing ConfigMap: {cm}")

    def test_clusterrolebinding_resolves(self):
        for crb in self.by_kind.get("ClusterRoleBinding", []):
            # role ref
            role = crb["roleRef"]
            self.assertEqual(role["kind"], "ClusterRole")
            self.assertIn(role["name"], self._names("ClusterRole"),
                          f"CRB refs missing CR: {role['name']}")
            # subjects
            for sub in crb["subjects"]:
                if sub["kind"] == "ServiceAccount":
                    self.assertIn(sub["name"], self._names("ServiceAccount"),
                                  f"CRB refs missing SA: {sub['name']}")

    def test_daemonset_volumemounts_match_volumes(self):
        for ds in self.by_kind.get("DaemonSet", []):
            spec = ds["spec"]["template"]["spec"]
            volume_names = {v["name"] for v in spec.get("volumes", [])}
            for c in spec["containers"]:
                for vm in c.get("volumeMounts", []):
                    self.assertIn(vm["name"], volume_names,
                                  f"volumeMount '{vm['name']}' has no volume")


class TestProbes(unittest.TestCase):
    """Liveness uses --header (cheap), readiness uses --data (real check)."""

    def setUp(self):
        self.docs = load_all_docs()
        self.ds = next(d for d in self.docs if d["kind"] == "DaemonSet")
        self.container = self.ds["spec"]["template"]["spec"]["containers"][0]

    def test_liveness_probe_uses_header(self):
        live = self.container["livenessProbe"]["exec"]["command"]
        self.assertIn("--header", live,
                      "livenessProbe should use --header (cheap)")

    def test_readiness_probe_uses_data(self):
        rdy = self.container["readinessProbe"]["exec"]["command"]
        self.assertIn("--data", rdy,
                      "readinessProbe should use --data (real check)")

    def test_probes_reference_collector_script(self):
        for kind in ("livenessProbe", "readinessProbe"):
            cmd = self.container[kind]["exec"]["command"]
            joined = " ".join(cmd)
            self.assertIn("cgroup_collector.py", joined,
                          f"{kind} doesn't reference cgroup_collector.py")


class TestRBACMinimum(unittest.TestCase):
    """ClusterRole must grant the read-only verbs required by the collector."""

    def test_cluster_role_has_required_resources(self):
        docs = load_all_docs()
        cr = next(d for d in docs if d["kind"] == "ClusterRole")
        all_resources = set()
        all_verbs = set()
        for rule in cr["rules"]:
            all_resources.update(rule.get("resources", []))
            all_verbs.update(rule.get("verbs", []))
        # Resources required by the collector
        for required in ("pods", "persistentvolumeclaims",
                          "persistentvolumes", "nodes", "nodes/proxy"):
            self.assertIn(required, all_resources,
                          f"ClusterRole missing resource: {required}")
        # Read-only verbs minimum
        for v in ("get", "list"):
            self.assertIn(v, all_verbs,
                          f"ClusterRole missing verb: {v}")
        # Defense: must NOT grant write verbs (read-only collector)
        for forbidden in ("create", "update", "delete", "patch"):
            self.assertNotIn(forbidden, all_verbs,
                              f"ClusterRole grants forbidden verb: {forbidden}")


class TestDaemonSetSecurity(unittest.TestCase):
    """Critical security and runtime settings."""

    def setUp(self):
        self.docs = load_all_docs()
        self.ds = next(d for d in self.docs if d["kind"] == "DaemonSet")
        self.pod_spec = self.ds["spec"]["template"]["spec"]
        self.container = self.pod_spec["containers"][0]

    def test_host_pid_enabled(self):
        """Need hostPID=true to read /proc/<host_pid>/cgroup."""
        self.assertTrue(self.pod_spec.get("hostPID"),
                        "hostPID must be true to read host /proc")

    def test_host_network_disabled(self):
        """Should NOT be on hostNetwork — avoids NodeLocal DNS conflict."""
        # K8s default is false; explicit false or absent both OK
        self.assertFalse(self.pod_spec.get("hostNetwork", False),
                          "hostNetwork should be false")

    def test_tolerates_all_taints(self):
        """DaemonSet must run on every node, incl. control-plane."""
        tols = self.pod_spec.get("tolerations", [])
        # 'operator: Exists' with no key/value tolerates everything
        has_blanket = any(t.get("operator") == "Exists" and "key" not in t
                           for t in tols)
        self.assertTrue(has_blanket,
                        "Missing blanket toleration (operator: Exists)")

    def test_host_volumes_present(self):
        """Need /host/proc /host/sys /host/dev mounts."""
        volume_paths = {v["hostPath"]["path"]
                        for v in self.pod_spec.get("volumes", [])
                        if "hostPath" in v}
        for required in ("/proc", "/sys", "/dev"):
            self.assertIn(required, volume_paths,
                          f"Missing hostPath volume: {required}")

    def test_resource_limits_present(self):
        """Be a good citizen on nodes running blockchain workloads."""
        res = self.container.get("resources", {})
        self.assertIn("limits", res, "Container missing resource limits")
        self.assertIn("requests", res, "Container missing resource requests")
        self.assertIn("cpu", res["limits"])
        self.assertIn("memory", res["limits"])

    def test_image_pull_policy_explicit(self):
        """imagePullPolicy should be explicit, not relying on :latest default."""
        self.assertIn("imagePullPolicy", self.container,
                      "imagePullPolicy must be explicit")


class TestConfigMapKeys(unittest.TestCase):
    """ConfigMap must export the env vars required by the collector."""

    REQUIRED_KEYS = {"HOST_PROC", "HOST_SYS", "DEPLOYMENT_MODE",
                     "TARGET_CGROUP", "COLLECTION_INTERVAL_SEC"}

    def test_required_keys_present(self):
        docs = load_all_docs()
        cm = next(d for d in docs if d["kind"] == "ConfigMap")
        data_keys = set(cm.get("data", {}).keys())
        missing = self.REQUIRED_KEYS - data_keys
        self.assertFalse(missing,
                          f"ConfigMap missing keys: {missing}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
