#!/usr/bin/env python3
"""
Multi-blockchain active account fetcher - Async

This module provides functionality to fetch active accounts from various blockchain networks
including Solana, Ethereum, BSC, Base, Scroll, Polygon, Starknet, and Sui.

Features:
- Unified pagination strategy: <1000 no pagination, ≥1000 with pagination
- Async HTTP requests for improved performance
- Connection pooling and session reuse
- Multi-chain adapter pattern for extensibility
- Environment variable configuration support

Usage:
    python3 fetch_active_accounts_async.py -c 100 -v

Author: Blockchain Node Benchmark Team
"""

# =====================================================================
# Multi-blockchain active account fetcher
# Supports Solana, Ethereum, BSC, Base, Scroll, Polygon, Starknet, Sui
# Unified pagination strategy: < 1000 no pagination, ≥ 1000 with pagination
# =====================================================================

import asyncio
import aiohttp
import os
import argparse
import sys
import time
import json
from collections import Counter
from pathlib import Path


def replace_env_vars(obj):
    """Recursively replace environment variable placeholders in configuration"""
    if isinstance(obj, dict):
        return {k: replace_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [replace_env_vars(item) for item in obj]
    elif isinstance(obj, str):
        # Check if it's an environment variable placeholder
        if obj in os.environ:
            env_value = os.environ[obj]
            # Automatic type conversion
            if env_value.lower() in ('true', 'false'):
                return env_value.lower() == 'true'
            try:
                return int(env_value)
            except ValueError:
                try:
                    return float(env_value)
                except ValueError:
                    return env_value
        return obj
    else:
        return obj


def load_chain_config():
    """Load blockchain configuration from environment variables"""
    chain_config_str = os.environ.get("CHAIN_CONFIG")
    if not chain_config_str:
        raise ValueError("CHAIN_CONFIG environment variable is required")

    try:
        config = json.loads(chain_config_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in CHAIN_CONFIG: {e}")

    # Recursively replace environment variable placeholders
    config = replace_env_vars(config)

    # Validate required fields
    if not config.get("chain_type"):
        raise ValueError("chain_type is required in CHAIN_CONFIG")
    if not config.get("rpc_url"):
        raise ValueError("rpc_url is required in CHAIN_CONFIG")

    # Set default values
    if "params" not in config:
        config["params"] = {}

    default_params = {
        "account_count": 1000,
        "output_file": "active_accounts.txt",
        "max_signatures": 50000,
        "tx_batch_size": 100,
        "semaphore_limit": 10,
        "target_address": ""
    }

    for key, default_value in default_params.items():
        if key not in config["params"]:
            config["params"][key] = default_value

    return config


def parse_args(config):
    """Parse command line arguments"""
    params = config.get("params", {})

    parser = argparse.ArgumentParser(description=f"Fetch active {config.get('chain_type', 'blockchain')} accounts")
    parser.add_argument("-c", "--count", type=int, default=params.get("account_count", 1000),
                        help=f"Number of accounts to fetch (default: {params.get('account_count', 1000)})")
    parser.add_argument("-o", "--output", type=str, default=params.get("output_file", "active_accounts.txt"),
                        help=f"Output file (default: {params.get('output_file', 'active_accounts.txt')})")
    parser.add_argument("-u", "--rpc-url", type=str, default=config.get("rpc_url", ""),
                        help=f"RPC URL (default: from config)")
    parser.add_argument("-t", "--target", type=str, default=params.get("target_address", ""),
                        help=f"Target address to analyze (default: from config)")
    parser.add_argument("-m", "--max-signatures", type=int, default=params.get("max_signatures", 50000),
                        help=f"Maximum signatures to fetch (default: {params.get('max_signatures', 50000)})")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable verbose output")
    return parser.parse_args()


async def request_jsonrpc(session, url, method, params=None, retries=3):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or []
    }

    for attempt in range(retries):
        try:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as response:
                response.raise_for_status()
                result = await response.json()

                if "error" in result:
                    error_code = result["error"].get("code", 0)
                    error_msg = result["error"].get("message", "")

                    if error_code == -32005:  # limit exceeded
                        raise Exception(f"Rate limit exceeded: {error_msg}")
                    elif error_code == -32603:  # invalid input
                        raise Exception(f"Invalid parameters: {error_msg}")
                    else:
                        raise Exception(f"RPC Error: {result['error']}")

                return result
        except Exception as e:
            if attempt == retries - 1:
                raise e
            print(f"Request failed (attempt {attempt + 1}/{retries}): {e}")
            await asyncio.sleep(0.5 * (2 ** attempt))  # Async exponential backoff


class BlockchainAdapter:
    """Blockchain adapter base class - Unified pagination framework"""

    def __init__(self, config):
        self.config = config
        self.rpc_url = config["rpc_url"]
        self.methods = config["methods"]
        self.chain_type = config["chain_type"]
        self.system_addresses = set(config.get("system_addresses", []))
        self.session = None  # Async session reuse

    async def fetch_signatures(self, address, cursor=None, limit=1000, verbose=False):
        """Unified account fetching entry point"""
        if verbose:
            print(f"Fetching {self.chain_type} signatures for {address}, target: {limit} transactions")

        # Simplified pagination strategy
        if limit < 1000:
            return await self._fetch_without_pagination(address, limit, verbose)
        else:
            return await self._fetch_with_pagination(address, limit, verbose)

    async def _fetch_without_pagination(self, address, limit, verbose):
        """Non-paginated fetch: single request"""
        if verbose:
            print(f"Using single request strategy (target: {limit})")

        target_transactions = limit * 5
        return await self._single_request(address, target_transactions, verbose)

    async def _fetch_with_pagination(self, address, limit, verbose):
        """Paginated fetch: multiple requests"""
        if verbose:
            print(f"Using pagination strategy (target: {limit})")

        all_results = []
        seen_digests = set()
        target_transactions = limit * 8
        batch_size = 500

        while len(all_results) < target_transactions:
            batch_results = await self._single_request(address, batch_size, verbose)
            if not batch_results:
                break

            # Deduplicate and add
            new_count = 0
            for tx in batch_results:
                digest = tx.get("signature")
                if digest and digest not in seen_digests:
                    all_results.append(tx)
                    seen_digests.add(digest)
                    new_count += 1

            if verbose:
                print(f"Batch added {new_count} new transactions (total: {len(all_results)})")

            if len(all_results) >= target_transactions or new_count == 0:
                break

            await asyncio.sleep(0.2)  # Async inter-batch delay, reduce wait time

        return all_results[:target_transactions]

    async def _single_request(self, address, limit, verbose):
        """Single request method implemented by each chain"""
        raise NotImplementedError("Subclasses must implement _single_request")

    async def fetch_transaction(self, signature):
        """Fetch transaction details - Each adapter must implement"""
        raise NotImplementedError("Subclasses must implement fetch_transaction")

    def extract_accounts_from_transaction(self, tx_data, target_address):
        """Extract account addresses from transaction data - Each adapter must implement"""
        raise NotImplementedError("Subclasses must implement extract_accounts_from_transaction")

    def _is_valid_account(self, address, target_address):
        """Unified address validation logic"""
        if not address or not isinstance(address, str):
            return False

        # Exclude target address and system addresses
        if address == target_address or address in self.system_addresses:
            return False

        # Exclude obviously invalid addresses
        if len(address) < 10:
            return False

        return True


class SolanaAdapter(BlockchainAdapter):
    """Solana blockchain adapter"""

    async def _single_request(self, address, limit, verbose):
        """Solana single request implementation"""
        params = [address, {"limit": min(limit, 1000)}]

        try:
            result = await request_jsonrpc(self.session, self.rpc_url, self.methods["get_signatures"], params)
            return result.get("result", [])
        except Exception as e:
            if verbose:
                print(f"Solana request failed: {e}")
            return []

    async def fetch_transaction(self, signature):
        """Fetch Solana transaction details"""
        params = [signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}]
        result = await request_jsonrpc(self.session, self.rpc_url, self.methods["get_transaction"], params)
        return result.get("result")

    def extract_accounts_from_transaction(self, tx_data, target_address):
        """Extract account addresses from Solana transaction"""
        accounts = set()
        if not tx_data or "transaction" not in tx_data:
            return accounts

        try:
            account_keys = tx_data["transaction"]["message"]["accountKeys"]
            for account in account_keys:
                pubkey_str = account.get('pubkey') if isinstance(account, dict) else str(account)
                if self._is_valid_account(pubkey_str, target_address):
                    accounts.add(pubkey_str)
        except (AttributeError, KeyError, TypeError):
            pass

        return accounts


class EthereumAdapter(BlockchainAdapter):
    """Ethereum and EVM chain adapter"""

    async def _single_request(self, address, limit, verbose):
        """Ethereum single request implementation"""
        # Check if it's a contract address
        is_contract = await self._is_contract_address(address)

        if is_contract:
            return await self._fetch_contract_logs_fixed(address, limit, verbose)
        else:
            return await self._fetch_eoa_transactions_simple(address, limit, verbose)

    async def _is_contract_address(self, address):
        """Check if it's a contract address"""
        try:
            params = [address, "latest"]
            result = await request_jsonrpc(self.session, self.rpc_url, "eth_getCode", params)
            return result.get("result", "0x") != "0x"
        except Exception:
            return False

    async def _fetch_contract_logs_fixed(self, address, limit, verbose):
        """Fixed contract log fetching"""
        try:
            latest_result = await request_jsonrpc(self.session, self.rpc_url, "eth_blockNumber", [])
            latest_block = int(latest_result["result"], 16)

            # Adjust query range based on chain type
            if self.chain_type.lower() == "bsc":
                block_range = 50  # BSC has stricter limits
            elif self.chain_type.lower() == "ethereum":
                block_range = 100  # Ethereum moderate
            else:
                block_range = 200  # Other chains more lenient

            start_block = max(0, latest_block - block_range)

            params = [{
                "address": address,
                "fromBlock": f"0x{start_block:x}",
                "toBlock": f"0x{latest_block:x}",
                "topics": []
            }]

            result = await request_jsonrpc(self.session, self.rpc_url, self.methods["get_logs"], params)
            logs = result.get("result", [])

            return [{"signature": log.get("transactionHash")}
                    for log in logs[:limit] if log.get("transactionHash")]

        except Exception as e:
            if verbose:
                print(f"Ethereum contract logs failed: {e}")
            return []

    async def _fetch_eoa_transactions_simple(self, address, limit, verbose):
        """Simplified EOA transaction fetching"""
        try:
            latest_result = await request_jsonrpc(self.session, self.rpc_url, "eth_blockNumber", [])
            latest_block = int(latest_result["result"], 16)
            start_block = max(0, latest_block - 100)  # Reduce query range

            transactions = []
            # Fetch multiple blocks concurrently to improve performance
            block_tasks = []
            for block_num in range(start_block, latest_block + 1):
                if len(transactions) >= limit:
                    break
                task = self._fetch_block_transactions(block_num, address, limit - len(transactions))
                block_tasks.append(task)
            
            # Execute block fetching concurrently
            block_results = await asyncio.gather(*block_tasks, return_exceptions=True)
            
            for result in block_results:
                if isinstance(result, list):
                    transactions.extend(result)
                    if len(transactions) >= limit:
                        break

            return transactions[:limit]

        except Exception as e:
            if verbose:
                print(f"Ethereum EOA scan failed: {e}")
            return []

    async def _fetch_block_transactions(self, block_num, target_address, remaining_limit):
        """Fetch transactions from a single block"""
        try:
            block_result = await request_jsonrpc(self.session, self.rpc_url, "eth_getBlockByNumber", [f"0x{block_num:x}", True])
            block_data = block_result.get("result")

            if not block_data or not block_data.get("transactions"):
                return []

            transactions = []
            target_addr = target_address.lower()
            
            for tx in block_data.get("transactions", []):
                if len(transactions) >= remaining_limit:
                    break
                    
                tx_from = tx.get("from", "").lower()
                tx_to = tx.get("to", "").lower()

                if tx_from == target_addr or tx_to == target_addr:
                    transactions.append({"signature": tx["hash"]})

            return transactions
        except Exception:
            return []

    async def fetch_transaction(self, tx_hash):
        """Fetch Ethereum transaction details"""
        params = [tx_hash]
        result = await request_jsonrpc(self.session, self.rpc_url, self.methods["get_transaction"], params)
        return result.get("result")

    def extract_accounts_from_transaction(self, tx_data, target_address):
        """Extract addresses from Ethereum transaction"""
        accounts = set()
        if not tx_data:
            return accounts

        try:
            from_addr = tx_data.get("from")
            to_addr = tx_data.get("to")

            if from_addr and self._is_valid_account(from_addr.lower(), target_address):
                accounts.add(from_addr.lower())

            if to_addr and self._is_valid_account(to_addr.lower(), target_address):
                accounts.add(to_addr.lower())

        except (AttributeError, KeyError, TypeError):
            pass

        return accounts


class StarknetAdapter(BlockchainAdapter):
    """StarkNet adapter"""

    async def _single_request(self, address, limit, verbose):
        """StarkNet single request implementation"""
        params = [{
            "from_block": {"block_number": 0},
            "to_block": "latest",
            "address": address,
            "keys": [],
            "chunk_size": min(limit, 1000)
        }]

        try:
            result = await request_jsonrpc(self.session, self.rpc_url, self.methods.get("get_events_native", "starknet_getEvents"), params)
            events = result.get("result", {}).get("events", [])

            tx_hashes = []
            seen = set()
            for event in events:
                tx_hash = event.get("transaction_hash")
                if tx_hash and tx_hash not in seen:
                    tx_hashes.append({"signature": tx_hash})
                    seen.add(tx_hash)
                    if len(tx_hashes) >= limit:
                        break

            return tx_hashes

        except Exception as e:
            if verbose:
                print(f"StarkNet request failed: {e}")
            return []

    async def fetch_transaction(self, tx_hash):
        """Fetch StarkNet transaction details"""
        params = [tx_hash]
        result = await request_jsonrpc(self.session, self.rpc_url, "starknet_getTransactionByHash", params)
        return result.get("result")

    def extract_accounts_from_transaction(self, tx_data, target_address):
        """Extract addresses from StarkNet transaction"""
        accounts = set()
        if not tx_data:
            return accounts

        try:
            # Contract address
            contract_address = tx_data.get("contract_address")
            if contract_address and self._is_valid_starknet_account(contract_address, target_address):
                accounts.add(contract_address.lower())

            # Sender address
            sender_address = tx_data.get("sender_address")
            if sender_address and self._is_valid_starknet_account(sender_address, target_address):
                accounts.add(sender_address.lower())

            # Addresses in calldata
            calldata = tx_data.get("calldata", [])
            if isinstance(calldata, list):
                for data_item in calldata:
                    if self._is_valid_starknet_account(data_item, target_address):
                        accounts.add(data_item.lower())

        except (AttributeError, KeyError, TypeError):
            pass

        return accounts

    def _is_valid_starknet_account(self, address, target_address):
        """Validate StarkNet address"""
        if not self._is_valid_account(address, target_address):
            return False

        try:
            if isinstance(address, str) and address.startswith("0x"):
                addr_len = len(address)
                # Exclude Ethereum address length, keep StarkNet addresses
                return addr_len != 42 and 60 <= addr_len <= 66
            return False
        except (ValueError, TypeError):
            return False


class SuiAdapter(BlockchainAdapter):
    """Sui blockchain adapter"""

    async def _single_request(self, address, limit, verbose):
        """Return to simple and effective query strategy"""
        if '::' in address:
            # USDC type address - use token query
            package_address = address.split('::')[0]
            module_name = address.split('::')[1] if len(address.split('::')) > 1 else None
            return await self._fetch_token_transactions(package_address, module_name, limit, verbose)
        else:
            # Regular type address
            return await self._fetch_simple_global_search(address, limit, verbose)

    async def _fetch_token_transactions(self, package_address, module_name, limit, verbose):
        """Token transaction fetching"""
        combinations = [
            {"module": module_name, "function": None},
            {"module": None, "function": None}
        ]

        for combo in combinations:
            try:
                params = [
                    {
                        "filter": {
                            "MoveFunction": {
                                "package": package_address,
                                "module": combo["module"],
                                "function": combo["function"]
                            }
                        }
                    },
                    None,
                    min(600, limit),
                    True
                ]

                result = await request_jsonrpc(self.session, self.rpc_url, self.methods["get_transactions"], params)
                result_data = result.get("result", {})
                transactions = result_data.get("data", [])

                if transactions:
                    if verbose:
                        print(f"Token combo {combo} found {len(transactions)} transactions")
                    return [{"signature": tx.get("digest")}
                            for tx in transactions if tx.get("digest")]

            except Exception as e:
                if verbose:
                    print(f"Token combo {combo} failed: {e}")
                continue

        return []

    async def _fetch_simple_global_search(self, address, limit, verbose):
        """Simple global search"""
        try:
            params = [{}, None, min(200, limit), True]

            result = await request_jsonrpc(self.session, self.rpc_url, self.methods["get_transactions"], params)
            result_data = result.get("result", {})
            transactions = result_data.get("data", [])

            if verbose:
                print(f"Global search found {len(transactions)} transactions with filter: None")

            return [{"signature": tx.get("digest")}
                    for tx in transactions if tx.get("digest")]

        except Exception as e:
            if verbose:
                print(f"Global search failed: {e}")
            return []

    async def fetch_transaction(self, digest):
        """Fetch transaction details"""
        params = [
            digest,
            {
                "showInput": True,
                "showRawInput": False,
                "showEffects": True,
                "showEvents": False,
                "showObjectChanges": True,
                "showBalanceChanges": True
            }
        ]

        try:
            result = await request_jsonrpc(self.session, self.rpc_url, self.methods["get_transaction"], params)
            return result.get("result")
        except Exception:
            return None

    def extract_accounts_from_transaction(self, tx_data, target_address):
        """Extract account addresses from transaction"""
        accounts = set()
        if not tx_data:
            return accounts

        try:
            # Extract addresses from balance changes
            balance_changes = tx_data.get("balanceChanges", [])
            for change in balance_changes:
                owner = change.get("owner", {})
                if "AddressOwner" in owner:
                    addr = owner["AddressOwner"]
                    if self._is_valid_account(addr, target_address):
                        accounts.add(addr)

            # Extract addresses from object changes
            object_changes = tx_data.get("objectChanges", [])
            for change in object_changes:
                owner = change.get("owner", {})
                if isinstance(owner, dict) and "AddressOwner" in owner:
                    addr = owner["AddressOwner"]
                    if self._is_valid_account(addr, target_address):
                        accounts.add(addr)

            # Extract from transaction sender
            transaction = tx_data.get("transaction", {})
            if transaction:
                sender = transaction.get("data", {}).get("sender")
                if sender and self._is_valid_account(sender, target_address):
                    accounts.add(sender)

        except (AttributeError, KeyError, TypeError):
            pass

        return accounts

    def _is_valid_account(self, address, target_address):
        """Simplified address validation"""
        if not address or not isinstance(address, str):
            return False

        # Exclude target address and system addresses
        if address == target_address or address in self.system_addresses:
            return False

        # Basic validation
        if not address.startswith('0x') or len(address) < 10:
            return False

        return True


def create_adapter(config):
    """Create corresponding adapter based on configuration"""
    chain_type = config["chain_type"].lower()

    if chain_type == "solana":
        return SolanaAdapter(config)
    elif chain_type in ["ethereum", "bsc", "base", "scroll", "polygon"]:
        return EthereumAdapter(config)
    elif chain_type == "starknet":
        return StarknetAdapter(config)
    elif chain_type == "sui":
        return SuiAdapter(config)
    else:
        raise ValueError(f"Unsupported chain type: {chain_type}")


async def fetch_all_signatures(adapter, address, limit_total, verbose=False):
    """Fixed batch fetching of all transaction signatures for specified address"""
    sigs = []
    cursor = None

    while len(sigs) < limit_total:
        try:
            if adapter.chain_type == "solana":
                batch = await adapter.fetch_signatures(address, cursor=cursor, limit=500, verbose=verbose)
                if not batch:
                    if verbose:
                        print("All available signatures retrieved.")
                    break
                sigs.extend(batch)
                # Set next page cursor
                if batch:
                    cursor = batch[-1]["signature"] if isinstance(batch[-1], dict) else batch[-1]
            else:
                batch = await adapter.fetch_signatures(address, limit=limit_total - len(sigs), verbose=verbose)
                if not batch:
                    if verbose:
                        print("All available signatures retrieved.")
                    break
                sigs.extend(batch)
                break  # Most chains fetch once

            if verbose:
                print(f"Retrieved {len(sigs)} / {limit_total} signatures...")

        except Exception as e:
            print(f"Error retrieving signatures after {len(sigs)} signatures: {e}")
            break

    return [s["signature"] if isinstance(s, dict) else s for s in sigs[:limit_total]]


async def fetch_and_count(adapter, signatures, target_address, counter, verbose=False):
    """Concurrently fetch transaction details and count associated accounts"""
    params = adapter.config.get("params", {})
    batch_size = params.get("tx_batch_size", 200)  # Increase batch size for efficiency
    semaphore_limit = params.get("semaphore_limit", 30)  # Increase concurrency

    sem = asyncio.Semaphore(semaphore_limit)
    system_addresses = adapter.system_addresses.copy()
    system_addresses.add(target_address)

    # Global deduplication set
    all_unique_accounts = set()

    async def fetch_tx(sig):
        async with sem:
            try:
                tx = await adapter.fetch_transaction(sig)
                return tx
            except Exception as e:
                if verbose:
                    print(f"Failed to get transaction {sig}: {e}")
                return None

    for i in range(0, len(signatures), batch_size):
        batch_sigs = signatures[i:i + batch_size]
        tasks = [fetch_tx(sig) for sig in batch_sigs]
        txs = await asyncio.gather(*tasks, return_exceptions=True)

        for tx in txs:
            if not tx or isinstance(tx, Exception):
                continue

            try:
                accounts = adapter.extract_accounts_from_transaction(tx, target_address)
                for account in accounts:
                    # Multiple validation and deduplication
                    if (account and
                            account not in system_addresses and
                            account != target_address and
                            account not in all_unique_accounts):
                        all_unique_accounts.add(account)
                        counter[account] += 1

            except Exception as e:
                if verbose:
                    print(f"Error processing transaction: {e}")
                continue

        if verbose:
            print(f"Processed {min(i + batch_size, len(signatures))}/{len(signatures)} transactions")
            print(f"Unique accounts found so far: {len(all_unique_accounts)}")


async def main():
    # Create global async session
    connector = aiohttp.TCPConnector(
        limit=100,  # Connection pool size
        limit_per_host=50,  # Connections per host
        keepalive_timeout=30,  # Keep connection time
        enable_cleanup_closed=True
    )
    
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            # Load blockchain configuration
            config = load_chain_config()
            print(f"Loaded configuration for {config['chain_type']} blockchain")

            # Create adapter and set session
            adapter = create_adapter(config)
            adapter.session = session  # Set shared session

            # Parse command line arguments
            args = parse_args(config)

            # Create output directory
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            print(f"Fetching {args.count} active {config['chain_type']} accounts...")
            print(f"RPC URL: {args.rpc_url}")
            print(f"Target address: {args.target}")

            target_address = args.target

            # Fetch transaction signatures
            print("Retrieving transaction signatures...")
            estimated_tx_count = max(args.count * 10, 100)
            actual_limit = min(estimated_tx_count, args.max_signatures)
            sigs = await fetch_all_signatures(adapter, target_address, actual_limit, args.verbose)
            print(f"Retrieved {len(sigs)} signatures for analysis.")

            if not sigs:
                print("No signatures found. Exiting.")
                return

            # Count account occurrence frequency
            counter = Counter()
            await fetch_and_count(adapter, sigs, target_address, counter, args.verbose)

            # Get most active accounts
            top_accounts = counter.most_common(args.count)

            # Write to file
            with open(args.output, "w", encoding="utf-8") as f:
                for addr, _ in top_accounts:
                    f.write(f"{addr}\n")

            print(f"Successfully wrote {len(top_accounts)} accounts to {args.output}")

            # Display top 5 accounts
            if args.verbose:
                print("\nTop 5 most active accounts:")
                for i, (addr, count) in enumerate(top_accounts[:5]):
                    print(f"{i + 1}. {addr} (interactions: {count})")

        except Exception as e:
            print(f"Error during execution: {e}")
            return


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nOperation interrupted by user.")
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
