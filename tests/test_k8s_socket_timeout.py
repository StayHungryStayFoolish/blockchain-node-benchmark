#!/usr/bin/env python3
"""k8s_api_client._do_get catches bare socket.timeout.

On Python 3.8/3.9 SSL handshake timeouts can bubble as bare socket.timeout
(NOT wrapped in URLError). We must catch it explicitly so retry logic in _get()
can see it as a transient error.
"""
import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / 'monitoring'))

import k8s_api_client  # noqa: E402
from k8s_api_client import K8sApiClient, K8sApiError  # noqa: E402


class SocketTimeoutHandling(unittest.TestCase):
    def setUp(self):
        # Force the client to a synthetic config so it doesn't try to read
        # serviceaccount files. K8S_TOKEN keeps token resolution silent.
        self._patches = [
            mock.patch.dict('os.environ', {
                'K8S_API_SERVER': 'http://127.0.0.1:9999',
                'K8S_TOKEN': 'fake',
                'K8S_INSECURE_TLS': '1',
            }),
        ]
        for p in self._patches:
            p.start()
        self.client = K8sApiClient(timeout=1)

    def tearDown(self):
        for p in self._patches:
            p.stop()

    def test_bare_socket_timeout_caught_as_k8s_api_error(self):
        """urlopen raising bare socket.timeout → K8sApiError, not unhandled."""
        with mock.patch.object(k8s_api_client.urlrequest, 'urlopen',
                               side_effect=socket.timeout('mocked SSL handshake timeout')):
            with self.assertRaises(K8sApiError) as ctx:
                self.client._do_get('http://127.0.0.1:9999/api/v1/nodes')
            self.assertEqual(ctx.exception.status, 0)
            self.assertIn('timeout', str(ctx.exception).lower())

    def test_bare_timeout_error_caught_as_k8s_api_error(self):
        """Python 3.10+ TimeoutError alias also caught."""
        with mock.patch.object(k8s_api_client.urlrequest, 'urlopen',
                               side_effect=TimeoutError('mocked')):
            with self.assertRaises(K8sApiError) as ctx:
                self.client._do_get('http://127.0.0.1:9999/api/v1/nodes')
            self.assertEqual(ctx.exception.status, 0)
            self.assertIn('timeout', str(ctx.exception).lower())

    def test_url_error_path_still_works(self):
        """Regression: URLError wrapping a timeout still produces K8sApiError."""
        from urllib import error as urlerror
        with mock.patch.object(k8s_api_client.urlrequest, 'urlopen',
                               side_effect=urlerror.URLError(TimeoutError('wrapped'))):
            with self.assertRaises(K8sApiError) as ctx:
                self.client._do_get('http://127.0.0.1:9999/api/v1/nodes')
            self.assertEqual(ctx.exception.status, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
