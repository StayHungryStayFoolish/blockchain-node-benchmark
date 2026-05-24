#!/usr/bin/env python3
"""L1: mock_rpc_server unknown-chain echo fallback (S0-tools step 4).

Verifies the MOCK_ALLOW_UNKNOWN=1 gate:
  1. Default (env unset) → dispatch returns -32601 for unknown chain
  2. With env set        → dispatch returns echo envelope {_mock_echo: true, ...}
  3. handle_unknown returns the correct shape directly
  4. Known chains are unaffected by the gate
"""
import os
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / 'tools'))

import mock_rpc_server as mrs  # noqa: E402


class UnknownChainEchoFallback(unittest.TestCase):
    def setUp(self):
        # Ensure env starts clean for each test
        self._prev = os.environ.pop("MOCK_ALLOW_UNKNOWN", None)

    def tearDown(self):
        if self._prev is not None:
            os.environ["MOCK_ALLOW_UNKNOWN"] = self._prev
        else:
            os.environ.pop("MOCK_ALLOW_UNKNOWN", None)

    def test_default_unknown_chain_rejected(self):
        """Without MOCK_ALLOW_UNKNOWN, unknown chain → -32601."""
        result, err = mrs.dispatch("bitcoin", "getblockcount", [])
        self.assertIsNone(result)
        self.assertIsNotNone(err)
        self.assertEqual(err["code"], -32601)
        self.assertIn("bitcoin", err["message"])

    def test_env_set_unknown_chain_echoes(self):
        """With MOCK_ALLOW_UNKNOWN=1, unknown chain → echo envelope."""
        os.environ["MOCK_ALLOW_UNKNOWN"] = "1"
        result, err = mrs.dispatch("ton", "getMasterchainInfo", [{"workchain": -1}])
        self.assertIsNone(err)
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("_mock_echo"))
        self.assertEqual(result["_method"], "getMasterchainInfo")
        self.assertEqual(result["_params"], [{"workchain": -1}])

    def test_handle_unknown_shape(self):
        """handle_unknown returns the documented envelope shape."""
        out = mrs.handle_unknown("foo_bar", [1, 2, 3])
        self.assertEqual(out, {"_mock_echo": True, "_method": "foo_bar", "_params": [1, 2, 3]})

    def test_known_chain_not_affected_by_gate(self):
        """Setting MOCK_ALLOW_UNKNOWN=1 must NOT change known-chain behavior."""
        os.environ["MOCK_ALLOW_UNKNOWN"] = "1"
        result, err = mrs.dispatch("ethereum", "eth_blockNumber", [])
        self.assertIsNone(err)
        self.assertIsNotNone(result)
        # eth_blockNumber returns a hex string like "0x8d6dd31"
        self.assertIsInstance(result, str)
        self.assertTrue(result.startswith("0x"))


if __name__ == '__main__':
    unittest.main(verbosity=2)
