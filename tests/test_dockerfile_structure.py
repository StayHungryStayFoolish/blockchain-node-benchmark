#!/usr/bin/env python3
"""L1: Dockerfile structural correctness.

Production-grade verification of Dockerfile WITHOUT requiring docker build.
Catches the most common pre-build defects: wrong base image, missing apt
packages, broken COPY paths, ENV typos, ENTRYPOINT syntax.

For real-build validation see B-2 (requires docker on GCE).
"""
import re
import unittest
from pathlib import Path

REPO = Path(__file__).parent.parent
DOCKERFILE = REPO / 'Dockerfile'


class DockerfileStructure(unittest.TestCase):
    def setUp(self):
        self.text = DOCKERFILE.read_text()
        # split into directives (ignore comments + blank lines)
        self.lines = [
            ln.rstrip() for ln in self.text.splitlines()
            if ln.strip() and not ln.lstrip().startswith('#')
        ]

    def test_exactly_one_from(self):
        froms = [ln for ln in self.lines if ln.upper().startswith('FROM ')]
        self.assertEqual(len(froms), 1, f"expected 1 FROM, got: {froms}")

    def test_base_image_is_slim_python_311(self):
        from_line = next(ln for ln in self.lines if ln.upper().startswith('FROM '))
        self.assertIn('python:3.11-slim', from_line,
                      f"FROM should pin python:3.11-slim, got: {from_line}")

    def test_apt_install_includes_required_packages(self):
        # bash for monitoring_coordinator.sh, tini for PID 1 signals,
        # curl for liveness probes, ca-certificates for HTTPS to apiserver.
        required = {'bash', 'curl', 'tini', 'ca-certificates'}
        # Find the RUN apt-get install block (multi-line continuations).
        full = self.text
        for pkg in required:
            self.assertRegex(full, rf'\b{re.escape(pkg)}\b',
                             f"apt package missing: {pkg}")

    def test_apt_cache_cleaned(self):
        # `rm -rf /var/lib/apt/lists/*` after apt-get install — shrinks image.
        self.assertIn('rm -rf /var/lib/apt/lists/*', self.text,
                      "apt cache not cleaned (image bloat)")

    def test_workdir_is_opt_blockchain_bench(self):
        # 04-daemonset.yaml expects collector at /opt/blockchain-bench/...
        self.assertIn('WORKDIR /opt/blockchain-bench', self.text)

    def test_copy_repo_to_workdir(self):
        # We need the entire repo in the image (multiple shell + python files
        # cross-reference each other; selective COPY is fragile).
        self.assertRegex(self.text,
                         r'COPY\s+\.\s+/opt/blockchain-bench')

    def test_pythonpath_includes_monitoring(self):
        # kubelet_stats_client / pod_device_mapper / k8s_api_client sibling
        # imports require monitoring/ on path.
        self.assertRegex(self.text,
                         r'ENV\s+PYTHONPATH=.*monitoring')

    def test_pythonunbuffered_for_logs(self):
        # K8s log scraping is line-based; unbuffered Python flushes immediately.
        self.assertIn('PYTHONUNBUFFERED=1', self.text)

    def test_entrypoint_uses_tini(self):
        # tini as PID 1 ensures SIGTERM during rolling-update reaches python.
        self.assertRegex(self.text,
                         r'ENTRYPOINT\s+\["?/usr/bin/tini')

    def test_healthcheck_uses_header_not_data(self):
        # --header is the read-only no-IO smoke (safe for HEALTHCHECK).
        # --data is the actual collector exec (privileged, slow — not for HC).
        hc_line = next((ln for ln in self.lines
                        if ln.upper().startswith('HEALTHCHECK')), None)
        self.assertIsNotNone(hc_line, "no HEALTHCHECK directive")
        assert hc_line is not None  # for type checker after assertIsNotNone
        hc_idx = self.lines.index(hc_line)
        hc_block = ' '.join(self.lines[hc_idx:hc_idx + 3])
        self.assertIn('--header', hc_block,
                      "HEALTHCHECK should use --header (no IO), not --data")

    def test_no_pip_install_pollution(self):
        # We deliberately avoid pip install — the monitoring stack is stdlib.
        # Any pip install in this Dockerfile is a regression.
        # Strip comments first so doc strings discussing "no pip install" don't trip us.
        non_comment = '\n'.join(self.lines).lower()
        self.assertNotIn('pip install', non_comment,
                         "monitoring stack is pure stdlib; pip install means scope creep")

    def test_dockerignore_exists(self):
        ignore = REPO / '.dockerignore'
        self.assertTrue(ignore.exists(), ".dockerignore missing — image bloat risk")
        text = ignore.read_text()
        for must_ignore in ('.git', '__pycache__', 'analysis-notes/'):
            self.assertIn(must_ignore, text,
                          f".dockerignore must exclude {must_ignore}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
