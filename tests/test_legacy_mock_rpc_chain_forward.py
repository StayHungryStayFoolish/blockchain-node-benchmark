#!/usr/bin/env python3
"""legacy_mock_rpc_server.handle_evm eth_getBlockByHash forwards chain param.

Verifies chain kwarg propagation through the recursive call so future
chain-specific block fields do not silently default to ethereum.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / 'tools'))

import legacy_mock_rpc_server as mrs  # noqa: E402


class EthGetBlockByHashForwardsChain(unittest.TestCase):
    def test_recursive_call_receives_chain(self):
        """eth_getBlockByHash → handle_evm('eth_getBlockByNumber', ..., chain=X)"""
        # Spy on handle_evm by wrapping; ensure inner call gets chain kwarg
        original = mrs.handle_evm
        seen_calls = []

        def spy(method, params, chain="ethereum"):
            seen_calls.append((method, chain))
            return original(method, params, chain)

        with mock.patch.object(mrs, 'handle_evm', side_effect=spy):
            # Outer call: eth_getBlockByHash on bsc
            result = mrs.handle_evm(
                "eth_getBlockByHash",
                ["0xabc123", False],
                chain="bsc",
            )

        # Should have seen 2 calls: outer (eth_getBlockByHash, bsc)
        # and inner recursive (eth_getBlockByNumber, bsc) — the fix.
        self.assertEqual(len(seen_calls), 2, f"got calls: {seen_calls}")
        self.assertEqual(seen_calls[0], ("eth_getBlockByHash", "bsc"))
        self.assertEqual(seen_calls[1], ("eth_getBlockByNumber", "bsc"))
        self.assertIsInstance(result, dict)
        self.assertIn("number", result)

    def test_chain_id_still_correct_per_chain(self):
        """Regression: eth_chainId continues to return per-chain real IDs."""
        # Real EVM mainnet chain IDs from EVM_CHAIN_IDS
        for chain, expected in [
            ("ethereum", "0x1"),
            ("bsc", "0x38"),
            ("polygon", "0x89"),
            ("base", "0x2105"),
            ("scroll", "0x82750"),
        ]:
            with self.subTest(chain=chain):
                actual = mrs.handle_evm("eth_chainId", [], chain=chain)
                self.assertEqual(actual, expected,
                                 f"{chain} chainId regression")

    def test_unknown_chain_defaults_to_ethereum(self):
        """Defensive: unknown chain still returns 0x1 (EVM_CHAIN_IDS.get default)."""
        result = mrs.handle_evm("eth_chainId", [], chain="zzz_unknown")
        self.assertEqual(result, "0x1")

    def test_get_block_by_hash_propagates_to_all_evm_chains(self):
        """End-to-end: eth_getBlockByHash on each chain returns a block dict."""
        for chain in ("ethereum", "bsc", "polygon", "base", "scroll"):
            with self.subTest(chain=chain):
                result = mrs.handle_evm(
                    "eth_getBlockByHash", ["0xabc", False], chain=chain
                )
                self.assertIsInstance(result, dict)
                self.assertIn("number", result)
                self.assertIn("hash", result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
