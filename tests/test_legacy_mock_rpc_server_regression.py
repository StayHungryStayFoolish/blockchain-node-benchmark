#!/usr/bin/env python3
"""Regression tests for legacy_mock_rpc_server.py fixes.

Covers previously observed bugs:

P1a (L160 dead expression): `range(min(10, len(params) and 10 or 10))`
     evaluated to range(10) always — the `len(params) and 10 or 10` chain
     is a vestigial copy-paste. Replaced with bare `range(10)`.

P1b (L180/340/380 None semantics): handle_solana/handle_starknet/handle_sui
     returned `{}` for unknown methods, which dispatch() couldn't distinguish
     from a legitimate empty-object response. handle_evm correctly returned
     `None`. Unified to None everywhere → dispatch() emits a proper
     "method not implemented" JSON-RPC error (-32601).

P1c (L190 eth_chainId hardcoded "0x1"): All 5 EVM chains (ethereum/bsc/base/
     scroll/polygon) returned `0x1` (mainnet ETH chain ID), breaking any
     production caller that validates chainId. Now uses a per-chain lookup.

Run this file with python3
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

import legacy_mock_rpc_server as mrs  # noqa: E402


class TestSolanaSignaturesShape(unittest.TestCase):
    """P1a: getSignaturesForAddress must return exactly 10 items regardless of params."""

    def test_no_params(self):
        result, error = mrs.dispatch("solana", "getSignaturesForAddress", [])
        self.assertIsNone(error)
        self.assertEqual(len(result), 10)

    def test_with_address_param(self):
        result, error = mrs.dispatch("solana", "getSignaturesForAddress",
                                     ["some-address"])
        self.assertIsNone(error)
        self.assertEqual(len(result), 10)

    def test_with_two_params(self):
        result, error = mrs.dispatch("solana", "getSignaturesForAddress",
                                     ["addr", {"limit": 5}])
        self.assertIsNone(error)
        # We intentionally return 10 regardless — caller's limit is advisory.
        self.assertEqual(len(result), 10)


class TestUnknownMethodSemantics(unittest.TestCase):
    """P1b: unknown methods must produce a -32601 error, not silently {}."""

    def test_solana_unknown_method_is_error(self):
        result, error = mrs.dispatch("solana", "totallyMadeUpMethod", [])
        self.assertIsNone(result)
        self.assertIsNotNone(error)
        self.assertEqual(error["code"], -32601)
        self.assertIn("not implemented", error["message"])

    def test_starknet_unknown_method_is_error(self):
        result, error = mrs.dispatch("starknet", "starknet_madeUp", [])
        self.assertIsNone(result)
        self.assertEqual(error["code"], -32601)

    def test_sui_unknown_method_is_error(self):
        result, error = mrs.dispatch("sui", "sui_madeUp", [])
        self.assertIsNone(result)
        self.assertEqual(error["code"], -32601)

    def test_evm_unknown_method_is_error(self):
        """EVM was already correct; guard against regression."""
        result, error = mrs.dispatch("ethereum", "eth_madeUp", [])
        self.assertIsNone(result)
        self.assertEqual(error["code"], -32601)

    def test_legitimate_empty_object_still_works(self):
        """Methods that legitimately return {} (none currently) — if we add
        one in the future, it must NOT be confused with 'method not found'.
        Here we just check a method that returns an empty list works."""
        result, error = mrs.dispatch("ethereum", "eth_getLogs", [{}])
        self.assertIsNone(error)
        self.assertEqual(result, [])

    def test_known_method_returning_falsy_not_treated_as_error(self):
        """eth_syncing returns False; must propagate as result, not error."""
        result, error = mrs.dispatch("ethereum", "eth_syncing", [])
        self.assertIsNone(error)
        self.assertIs(result, False)


class TestEvmChainId(unittest.TestCase):
    """P1c: eth_chainId must return the real chainId per EVM chain."""

    def test_ethereum_mainnet(self):
        result, error = mrs.dispatch("ethereum", "eth_chainId", [])
        self.assertIsNone(error)
        self.assertEqual(result, "0x1")  # 1

    def test_bsc(self):
        result, error = mrs.dispatch("bsc", "eth_chainId", [])
        self.assertIsNone(error)
        self.assertEqual(result, "0x38")  # 56
        self.assertEqual(int(result, 16), 56)

    def test_base(self):
        result, error = mrs.dispatch("base", "eth_chainId", [])
        self.assertIsNone(error)
        self.assertEqual(result, "0x2105")  # 8453
        self.assertEqual(int(result, 16), 8453)

    def test_scroll(self):
        result, error = mrs.dispatch("scroll", "eth_chainId", [])
        self.assertIsNone(error)
        self.assertEqual(result, "0x82750")  # 534352
        self.assertEqual(int(result, 16), 534352)

    def test_polygon(self):
        result, error = mrs.dispatch("polygon", "eth_chainId", [])
        self.assertIsNone(error)
        self.assertEqual(result, "0x89")  # 137
        self.assertEqual(int(result, 16), 137)

    def test_all_5_evm_chainids_unique(self):
        """No two EVM chains share a chainId."""
        chainids = set()
        for chain in ("ethereum", "bsc", "base", "scroll", "polygon"):
            result, _ = mrs.dispatch(chain, "eth_chainId", [])
            chainids.add(result)
        self.assertEqual(len(chainids), 5)

    def test_evm_recursive_call_does_not_break(self):
        """handle_evm internally calls handle_evm('eth_getBlockByNumber',...)
        recursively without passing chain — must still work (eth_getBlockByNumber
        doesn't depend on chain, just defaults to ethereum)."""
        result, error = mrs.dispatch("bsc", "eth_getBlockByHash", ["0xabc"])
        self.assertIsNone(error)
        self.assertIn("number", result)
        self.assertIn("hash", result)


class TestBackwardCompat(unittest.TestCase):
    """Smoke: legacy mock chains can still dispatch their core methods."""

    def test_solana_getSlot(self):
        result, error = mrs.dispatch("solana", "getSlot", [])
        self.assertIsNone(error)
        self.assertIsInstance(result, int)

    def test_evm_eth_blockNumber_all_5(self):
        for chain in ("ethereum", "bsc", "base", "scroll", "polygon"):
            result, error = mrs.dispatch(chain, "eth_blockNumber", [])
            self.assertIsNone(error, f"{chain}: {error}")
            self.assertTrue(result.startswith("0x"))

    def test_starknet_blockNumber(self):
        result, error = mrs.dispatch("starknet", "starknet_blockNumber", [])
        self.assertIsNone(error)
        self.assertIsInstance(result, int)

    def test_sui_checkpoint(self):
        result, error = mrs.dispatch("sui", "sui_getLatestCheckpointSequenceNumber", [])
        self.assertIsNone(error)
        self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
