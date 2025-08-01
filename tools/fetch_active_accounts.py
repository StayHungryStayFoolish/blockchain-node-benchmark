#!/usr/bin/env python3

# =====================================================================
# Solana 活跃账户获取脚本
# 用于获取 Solana 网络上的活跃账户列表
# =====================================================================

import asyncio
import os
import argparse
import sys
from collections import Counter
from pathlib import Path

# 检查依赖项
try:
    from solana.rpc.async_api import AsyncClient
    from solders.pubkey import Pubkey
    from solders.signature import Signature
    from solders.transaction_status import EncodedConfirmedTransactionWithStatusMeta
    from solana.exceptions import SolanaRpcException
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
except ImportError:
    print("Error: Required dependencies not found.")
    print("Please install the required packages:")
    print("  pip install solana tenacity")
    sys.exit(1)

# 默认配置
# 默认配置 - 优先从环境变量读取，支持config.sh配置
DEFAULT_ACCOUNT_COUNT = int(os.environ.get("ACCOUNT_COUNT", "1000"))
DEFAULT_OUTPUT_FILE = os.environ.get("ACCOUNT_OUTPUT_FILE", "address.txt")
DEFAULT_RPC_URL = os.environ.get("LOCAL_RPC_URL") or os.environ.get("RPC_URL", "http://localhost:8899")
DEFAULT_TARGET_ADDRESS = os.environ.get("ACCOUNT_TARGET_ADDRESS", "TSLvdd1pWpHVjahSpsvCXUbgwsL3JAcvokwaKt1eokM")  # 示例目标地址
DEFAULT_MAX_SIGNATURES = int(os.environ.get("ACCOUNT_MAX_SIGNATURES", "50000"))
DEFAULT_TX_BATCH_SIZE = int(os.environ.get("ACCOUNT_TX_BATCH_SIZE", "100"))
DEFAULT_SEMAPHORE_LIMIT = int(os.environ.get("ACCOUNT_SEMAPHORE_LIMIT", "10"))

# 系统地址黑名单
SYSTEM_ADDRESSES = {
    "11111111111111111111111111111111",  # 系统程序
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",  # SPL代币程序
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",  # 关联代币账户程序
    "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s",  # 元数据程序
    "SysvarRent111111111111111111111111111111111",  # 系统变量-租金
    "ComputeBudget111111111111111111111111111111",  # 计算预算程序
}

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="Fetch active Solana accounts")
    parser.add_argument("-c", "--count", type=int, default=DEFAULT_ACCOUNT_COUNT,
                        help=f"Number of accounts to fetch (default: {DEFAULT_ACCOUNT_COUNT})")
    parser.add_argument("-o", "--output", type=str, default=DEFAULT_OUTPUT_FILE,
                        help=f"Output file (default: {DEFAULT_OUTPUT_FILE})")
    parser.add_argument("-u", "--rpc-url", type=str, default=DEFAULT_RPC_URL,
                        help=f"Solana RPC URL (default: {DEFAULT_RPC_URL})")
    parser.add_argument("-t", "--target", type=str, default=DEFAULT_TARGET_ADDRESS,
                        help=f"Target address to analyze (default: {DEFAULT_TARGET_ADDRESS})")
    parser.add_argument("-m", "--max-signatures", type=int, default=DEFAULT_MAX_SIGNATURES,
                        help=f"Maximum signatures to fetch (default: {DEFAULT_MAX_SIGNATURES})")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable verbose output")
    
    return parser.parse_args()

# 重试装饰器
def create_retry_decorator():
    return retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type((SolanaRpcException, asyncio.TimeoutError)),
        reraise=True
    )

@create_retry_decorator()
async def fetch_signatures_with_retry(client, address, before=None, limit=1000):
    """获取地址的交易签名，带重试机制"""
    return await client.get_signatures_for_address(address, before=before, limit=limit)

@create_retry_decorator()
async def get_transaction_with_retry(client, sig: Signature):
    """获取交易详情，带重试机制"""
    return await client.get_transaction(
        sig,
        encoding="jsonParsed",
        max_supported_transaction_version=0
    )

async def fetch_all_signatures(client, address, limit_total, verbose=False):
    """分批获取指定地址的所有交易签名"""
    sigs = []
    before = None
    while len(sigs) < limit_total:
        try:
            resp = await fetch_signatures_with_retry(client, address, before=before, limit=1000)
            batch = resp.value
            if not batch:
                if verbose:
                    print("All available signatures retrieved.")
                break
            sigs.extend(batch)
            before = batch[-1].signature
            if verbose:
                print(f"Retrieved {len(sigs)} / {limit_total} signatures...")
        except Exception as e:
            print(f"Error retrieving signatures after {len(sigs)} signatures: {e}")
            break
    return [s.signature for s in sigs[:limit_total]]

async def fetch_and_count(client, signatures, target, counter, batch_size=DEFAULT_TX_BATCH_SIZE, 
                         semaphore_limit=DEFAULT_SEMAPHORE_LIMIT, verbose=False):
    """并发获取交易详情并统计关联账户"""
    sem = asyncio.Semaphore(semaphore_limit)
    system_addresses = SYSTEM_ADDRESSES.copy()
    system_addresses.add(str(target))  # 添加目标地址到黑名单

    async def fetch_tx(sig: Signature):
        async with sem:
            try:
                resp = await get_transaction_with_retry(client, sig)
                return resp.value
            except Exception as e:
                if verbose:
                    print(f"Failed to get transaction {sig}: {e}")
                return None

    for i in range(0, len(signatures), batch_size):
        batch_sigs = signatures[i:i + batch_size]
        tasks = [fetch_tx(sig) for sig in batch_sigs]
        txs = await asyncio.gather(*tasks)

        for tx in txs:
            if not isinstance(tx, EncodedConfirmedTransactionWithStatusMeta) or tx.transaction is None or tx.transaction.transaction is None:
                continue

            try:
                # 处理账户密钥
                account_keys = tx.transaction.transaction.message.account_keys

                for account in account_keys:
                    # 提取 pubkey 字符串
                    if hasattr(account, 'pubkey'):
                        # 如果是 ParsedAccount 对象，提取 pubkey 属性
                        pubkey_str = str(account.pubkey)
                    else:
                        # 如果直接是 Pubkey 对象
                        pubkey_str = str(account)

                    # 过滤系统地址和目标地址
                    if pubkey_str not in system_addresses:
                        counter[pubkey_str] += 1

            except (AttributeError, KeyError) as e:
                if verbose:
                    print(f"Skipping malformed transaction... Error: {e}")
                continue

        if verbose:
            print(f"Processed {min(i + batch_size, len(signatures))}/{len(signatures)} transactions")

async def main():
    """主函数"""
    args = parse_args()
    
    # 创建输出目录
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Fetching {args.count} active Solana accounts...")
    print(f"RPC URL: {args.rpc_url}")
    print(f"Target address: {args.target}")
    
    # 创建 RPC 客户端
    client = AsyncClient(args.rpc_url, timeout=30)
    
    try:
        # 解析目标地址
        target_address = Pubkey.from_string(args.target)
        
        # 获取交易签名
        print("Retrieving transaction signatures...")
        sigs = await fetch_all_signatures(client, target_address, args.max_signatures, args.verbose)
        print(f"Retrieved {len(sigs)} signatures for analysis.")
        
        if not sigs:
            print("No signatures found. Exiting.")
            await client.close()
            return
        
        # 统计账户出现频率
        counter = Counter()
        await fetch_and_count(client, sigs, target_address, counter, 
                             DEFAULT_TX_BATCH_SIZE, DEFAULT_SEMAPHORE_LIMIT, args.verbose)
        
        # 获取最活跃的账户
        top_accounts = counter.most_common(args.count)
        
        # 写入文件
        with open(args.output, "w") as f:
            for addr, _ in top_accounts:
                f.write(f"{addr}\n")
        
        print(f"Successfully wrote {len(top_accounts)} accounts to {args.output}")
        
        # 显示前5个账户
        if args.verbose:
            print("\nTop 5 most active accounts:")
            for i, (addr, count) in enumerate(top_accounts[:5]):
                print(f"{i + 1}. {addr} (interactions: {count})")
    
    finally:
        # 关闭客户端
        await client.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nOperation interrupted by user.")
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
