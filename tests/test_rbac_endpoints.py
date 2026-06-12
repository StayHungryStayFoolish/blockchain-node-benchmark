#!/usr/bin/env python3
"""L1: RBAC manifest contains endpoints + all originally required resources."""
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).parent.parent
RBAC = REPO / 'deploy/k8s/02-serviceaccount-rbac.yaml'


class RBACEndpointsTest(unittest.TestCase):
    def setUp(self):
        with open(RBAC) as f:
            self.docs = list(yaml.safe_load_all(f))
        self.cr = next(d for d in self.docs if d and d.get('kind') == 'ClusterRole')

    def test_three_documents(self):
        """File has ServiceAccount + ClusterRole + ClusterRoleBinding."""
        kinds = [d.get('kind') for d in self.docs if d]
        self.assertIn('ServiceAccount', kinds)
        self.assertIn('ClusterRole', kinds)
        self.assertIn('ClusterRoleBinding', kinds)

    def test_endpoints_resource_present(self):
        """list_namespaced_endpoints needs 'endpoints' verb."""
        resources = self.cr['rules'][0]['resources']
        self.assertIn('endpoints', resources)

    def test_original_resources_preserved(self):
        """Adding endpoints must not regress pods/pvc/pv/namespaces/nodes."""
        resources = self.cr['rules'][0]['resources']
        for required in ('pods', 'persistentvolumeclaims', 'persistentvolumes',
                         'namespaces', 'nodes'):
            self.assertIn(required, resources, f'regression: {required} missing')

    def test_read_only_verbs(self):
        """Defense: no write verbs on monitoring SA."""
        for rule in self.cr['rules']:
            for verb in rule['verbs']:
                self.assertIn(verb, ('get', 'list', 'watch'),
                              f'write verb {verb!r} leaked into monitoring RBAC')

    def test_no_secrets(self):
        """Defense: monitoring SA must not request secrets."""
        for rule in self.cr['rules']:
            self.assertNotIn('secrets', rule.get('resources', []))


if __name__ == '__main__':
    unittest.main(verbosity=2)
