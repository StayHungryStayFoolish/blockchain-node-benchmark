#!/usr/bin/env python3
"""
k8s_api_client.py — minimal stdlib-only Kubernetes API client
=============================================================

Purpose
-------
A tiny K8s API HTTP client built on urllib.request — no `kubernetes`
PyPI dependency. Designed to run inside a DaemonSet pod where:
  - Token: /var/run/secrets/kubernetes.io/serviceaccount/token
  - CA:    /var/run/secrets/kubernetes.io/serviceaccount/ca.crt
  - API:   https://kubernetes.default.svc

Outside of a pod (dev/test), env overrides let you point at a kind
cluster or use a fake server in unit tests:
  K8S_API_SERVER     — override API URL (default: https://kubernetes.default.svc)
  K8S_TOKEN_FILE     — override token path
  K8S_CA_FILE        — override CA path
  K8S_TOKEN          — raw token (skip file read; used by tests)
  K8S_INSECURE_TLS=1 — skip TLS verification (tests / dev only)

Why stdlib only
---------------
The baseline framework intentionally avoids non-stdlib Python deps (see
utils/unified_logger.py, utils/csv_data_processor.py). Adding `kubernetes`
PyPI for a few REST calls would bloat the DaemonSet image by ~50 MB and
introduce a non-trivial dep tree (urllib3, websocket-client, requests).
stdlib gets us the same coverage in ~150 lines.

API surface
-----------
  client = K8sApiClient()
  pods   = client.list_namespaced_pods("blockchain-bench")
  pod    = client.get_pod("blockchain-bench", "geth-node-0")
  pvc    = client.get_pvc("blockchain-bench", "geth-data")
  pv     = client.get_pv("pvc-abc-123")
  node   = client.get_node("gke-node-1")
  stats  = client.kubelet_stats_summary("gke-node-1")
  ep     = client.list_namespaced_endpoints("blockchain-bench")

Each returns a dict (parsed JSON). On error, raises K8sApiError with the
HTTP status + body — never silently returns None.

References
----------
- Service account auth: kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/
- Kubelet stats summary: kubernetes.io/docs/reference/instrumentation/node-metrics/
- Apiserver proxy:      kubernetes.io/docs/tasks/extend-kubernetes/http-proxy-access-api/
"""

from __future__ import annotations

import json
import os
import ssl
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from urllib import request as urlrequest
from urllib import error as urlerror
from urllib.parse import quote


DEFAULT_API_SERVER = "https://kubernetes.default.svc"
DEFAULT_TOKEN_FILE = "/var/run/secrets/kubernetes.io/serviceaccount/token"
DEFAULT_CA_FILE = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
DEFAULT_TIMEOUT_SEC = 10


class K8sApiError(Exception):
    """Raised on any non-2xx API response or network failure."""

    def __init__(self, status: int, body: str, url: str):
        self.status = status
        self.body = body
        self.url = url
        super().__init__(f"K8s API error {status} on {url}: {body[:200]}")


def _env(name: str, default: str = "") -> str:
    v = os.environ.get(name, "")
    return v if v else default


class K8sApiClient:
    """Stateless HTTP client. Re-reads env on each instantiation."""

    def __init__(
        self,
        api_server: Optional[str] = None,
        token: Optional[str] = None,
        token_file: Optional[str] = None,
        ca_file: Optional[str] = None,
        insecure_tls: Optional[bool] = None,
        timeout: float = DEFAULT_TIMEOUT_SEC,
    ):
        self.api_server = (
            api_server or _env("K8S_API_SERVER", DEFAULT_API_SERVER)
        ).rstrip("/")
        self.token_file = token_file or _env("K8S_TOKEN_FILE", DEFAULT_TOKEN_FILE)
        self.ca_file = ca_file or _env("K8S_CA_FILE", DEFAULT_CA_FILE)
        # Token can be passed in, set via env, or read from file
        if token is not None:
            self._token = token
        elif _env("K8S_TOKEN"):
            self._token = _env("K8S_TOKEN")
        else:
            self._token = self._read_token_file()
        # TLS
        if insecure_tls is not None:
            self._insecure = insecure_tls
        else:
            self._insecure = _env("K8S_INSECURE_TLS", "").lower() in ("1", "true", "yes")
        self.timeout = timeout

    # -----------------------------------------------------------------
    # Token + TLS context
    # -----------------------------------------------------------------

    def _read_token_file(self) -> str:
        """Read SA token from disk. Returns empty string if file missing."""
        p = Path(self.token_file)
        if not p.is_file():
            return ""
        try:
            return p.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    def _make_ssl_context(self) -> ssl.SSLContext:
        if self._insecure:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return ctx
        ca = Path(self.ca_file)
        if ca.is_file():
            return ssl.create_default_context(cafile=str(ca))
        # No CA file → default truststore (e.g. test env hitting localhost)
        return ssl.create_default_context()

    # -----------------------------------------------------------------
    # Core HTTP GET
    # -----------------------------------------------------------------

    def _get(self, path: str) -> Dict[str, Any]:
        """GET <api_server><path>. Returns parsed JSON dict.

        Raises K8sApiError on non-2xx or network failure.
        """
        url = f"{self.api_server}{path}"
        req = urlrequest.Request(url, method="GET")
        if self._token:
            req.add_header("Authorization", f"Bearer {self._token}")
        req.add_header("Accept", "application/json")
        ctx = self._make_ssl_context() if url.startswith("https") else None
        try:
            with urlrequest.urlopen(req, timeout=self.timeout, context=ctx) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                # urllib raises on >=400, so this is a 2xx
                return json.loads(body) if body else {}
        except urlerror.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                pass
            raise K8sApiError(e.code, err_body, url) from e
        except urlerror.URLError as e:
            raise K8sApiError(0, str(e.reason), url) from e

    # -----------------------------------------------------------------
    # Object accessors (typed wrappers)
    # -----------------------------------------------------------------

    def list_namespaced_pods(self, namespace: str) -> Dict[str, Any]:
        return self._get(f"/api/v1/namespaces/{quote(namespace)}/pods")

    def get_pod(self, namespace: str, name: str) -> Dict[str, Any]:
        return self._get(
            f"/api/v1/namespaces/{quote(namespace)}/pods/{quote(name)}"
        )

    def get_pvc(self, namespace: str, name: str) -> Dict[str, Any]:
        return self._get(
            f"/api/v1/namespaces/{quote(namespace)}/persistentvolumeclaims/{quote(name)}"
        )

    def get_pv(self, name: str) -> Dict[str, Any]:
        return self._get(f"/api/v1/persistentvolumes/{quote(name)}")

    def get_node(self, name: str) -> Dict[str, Any]:
        return self._get(f"/api/v1/nodes/{quote(name)}")

    def list_namespaced_endpoints(self, namespace: str) -> Dict[str, Any]:
        return self._get(f"/api/v1/namespaces/{quote(namespace)}/endpoints")

    def kubelet_stats_summary(self, node_name: str) -> Dict[str, Any]:
        """Call kubelet's /stats/summary via apiserver proxy.

        This avoids the direct :10250 connection (which needs node IP +
        kubelet cert trust), routing through apiserver which only needs
        nodes/proxy RBAC verb.
        """
        return self._get(
            f"/api/v1/nodes/{quote(node_name)}/proxy/stats/summary"
        )


# ---------------------------------------------------------------------
# CLI / smoke test
# ---------------------------------------------------------------------

def _print_summary(client: K8sApiClient, namespace: str) -> int:
    """Quick smoke: list pods in NS, print count + first 5 names + stats."""
    try:
        pods = client.list_namespaced_pods(namespace)
    except K8sApiError as e:
        print(f"❌ failed: {e}", file=sys.stderr)
        return 1
    items = pods.get("items", [])
    print(f"Pods in namespace '{namespace}': {len(items)}")
    for p in items[:5]:
        meta = p.get("metadata", {})
        spec = p.get("spec", {})
        node = spec.get("nodeName", "?")
        print(f"  {meta.get('name'):40s} node={node}")
    return 0


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(
        description="Minimal stdlib K8s API client smoke test"
    )
    ap.add_argument("--namespace", "-n", default="default")
    ap.add_argument("--insecure", action="store_true")
    args = ap.parse_args()
    client = K8sApiClient(insecure_tls=args.insecure)
    return _print_summary(client, args.namespace)


if __name__ == "__main__":
    sys.exit(main())
