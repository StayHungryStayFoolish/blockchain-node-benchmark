#!/usr/bin/env python3
"""Mock RPC Server for blockchain-node-benchmark e2e testing.

Supports HTTP POST (JSON-RPC 2.0) + WebSocket subscribe for all 8 chains:
- Solana (8899)
- EVM 5 chains: Ethereum / BSC / Base / Polygon / Scroll
- Starknet
- Sui

Source of truth for RPC methods: config/chains/<name>.json (since S1.1, replaces legacy UNIFIED_BLOCKCHAIN_CONFIG heredoc).

Usage:
    python3 mock_rpc_server.py --port 8899 --chain solana
    python3 mock_rpc_server.py --port 8545 --chain ethereum --latency-ms 5
    python3 mock_rpc_server.py --port 8899 --chain solana --ws-port 8900

Design:
- Pure stdlib (no aiohttp/websockets dep). Uses http.server + socket-level WS upgrade.
- Returns shape-correct fake responses (monotonic slot/block, fake balances, etc.)
- Latency configurable for stress testing
- Counts requests, prints periodic stats to stderr
- Supports both 'single' and 'mixed' rpc_methods modes
- Accepts both batch (list) and single (dict) JSON-RPC requests

This is NOT a real node — it just satisfies the wire protocol so the benchmark
framework can be exercised end-to-end without deploying real RPC binaries.
"""

import argparse
import asyncio
import base64
import hashlib
import json
import logging
import os
import struct
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from typing import Any, Dict, List, Optional, Tuple, Union

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [mock-rpc] %(levelname)s %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("mock-rpc")

# ─────────────────────────────────────────────────────────────────────
# Monotonic counters (shared across HTTP + WS threads)
# ─────────────────────────────────────────────────────────────────────

_STATE_LOCK = threading.Lock()
_SLOT_START = int(time.time())   # solana slot
_BLOCK_START = int(time.time()) // 12   # ~12s blocks for evm
_REQ_COUNT = 0
_REQ_COUNT_BY_METHOD: Dict[str, int] = {}
_SUBSCRIPTIONS: Dict[int, Dict[str, Any]] = {}
_NEXT_SUB_ID = 1


def _bump_slot() -> int:
    """Solana slot ≈ wall clock seconds (1 slot per second)."""
    return _SLOT_START + int(time.time() - _SLOT_START)


def _bump_block() -> int:
    """EVM block ≈ 12s blocks."""
    return _BLOCK_START + int(time.time() - _BLOCK_START * 12) // 12


def _count_request(method: str) -> None:
    global _REQ_COUNT
    with _STATE_LOCK:
        _REQ_COUNT += 1
        _REQ_COUNT_BY_METHOD[method] = _REQ_COUNT_BY_METHOD.get(method, 0) + 1


# ─────────────────────────────────────────────────────────────────────
# Per-chain response handlers
# ─────────────────────────────────────────────────────────────────────


def _fake_pubkey(seed: str) -> str:
    """Generate deterministic-looking base58 pubkey from seed."""
    h = hashlib.sha256(seed.encode()).digest()
    # base58 alphabet
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    num = int.from_bytes(h, "big")
    out = ""
    while num:
        num, rem = divmod(num, 58)
        out = alphabet[rem] + out
    return out[:44]  # Solana pubkey length


def _fake_tx_hash() -> str:
    """0x-prefixed 32-byte hex hash."""
    h = hashlib.sha256(f"tx-{time.time_ns()}".encode()).hexdigest()
    return "0x" + h


def _fake_address(prefix: str = "0x") -> str:
    h = hashlib.sha256(f"addr-{time.time_ns()}".encode()).hexdigest()
    return prefix + h[:40]


# ── Solana ──

def handle_solana(method: str, params: List[Any]) -> Any:
    slot = _bump_slot()
    if method == "getSlot":
        return slot
    if method == "getBlockHeight":
        return slot
    if method == "getBalance":
        return {"context": {"slot": slot}, "value": 1_000_000_000}  # 1 SOL
    if method == "getAccountInfo":
        return {
            "context": {"slot": slot},
            "value": {
                "data": ["", "base64"],
                "executable": False,
                "lamports": 1_000_000_000,
                "owner": "11111111111111111111111111111111",
                "rentEpoch": 361,
                "space": 0,
            },
        }
    if method == "getTokenAccountBalance":
        return {
            "context": {"slot": slot},
            "value": {"amount": "1000000", "decimals": 6, "uiAmount": 1.0, "uiAmountString": "1.0"},
        }
    if method == "getRecentBlockhash":
        return {
            "context": {"slot": slot},
            "value": {
                "blockhash": _fake_pubkey(f"bh-{slot}"),
                "feeCalculator": {"lamportsPerSignature": 5000},
            },
        }
    if method == "getLatestBlockhash":
        return {
            "context": {"slot": slot},
            "value": {"blockhash": _fake_pubkey(f"bh-{slot}"), "lastValidBlockHeight": slot + 150},
        }
    if method == "getSignaturesForAddress":
        return [
            {
                "signature": _fake_pubkey(f"sig-{slot}-{i}"),
                "slot": slot - i,
                "err": None,
                "memo": None,
                "blockTime": int(time.time()) - i,
                "confirmationStatus": "finalized",
            }
            for i in range(10)
        ]
    if method == "getTransaction":
        return {
            "slot": slot,
            "blockTime": int(time.time()),
            "meta": {"err": None, "fee": 5000, "preBalances": [1000000000], "postBalances": [999995000]},
            "transaction": {"message": {"accountKeys": [_fake_pubkey("acc1")]}, "signatures": [_fake_pubkey("sig1")]},
        }
    if method == "getVersion":
        return {"solana-core": "1.18.0-mock", "feature-set": 4215500110}
    if method == "getEpochInfo":
        return {"absoluteSlot": slot, "blockHeight": slot, "epoch": slot // 432000, "slotIndex": slot % 432000, "slotsInEpoch": 432000, "transactionCount": slot * 100}
    if method == "getHealth":
        return "ok"
    if method == "getIdentity":
        return {"identity": _fake_pubkey("mock-node-identity")}
    if method == "getGenesisHash":
        return _fake_pubkey("genesis")
    # Unknown method → None (signals "method not handled" to caller, matches
    # handle_evm behavior). Was previously `return {}` which the caller could
    # not distinguish from a legitimate empty-object response.
    return None


# ── EVM (ethereum, bsc, base, polygon, scroll) ──

# Real mainnet chain IDs (used for eth_chainId). Source: chainlist.org.
EVM_CHAIN_IDS = {
    "ethereum": "0x1",         # 1
    "bsc":      "0x38",        # 56  (BNB Smart Chain)
    "base":     "0x2105",      # 8453 (Base mainnet)
    "scroll":   "0x82750",     # 534352 (Scroll mainnet)
    "polygon":  "0x89",        # 137 (Polygon PoS)
}


def handle_evm(method: str, params: List[Any], chain: str = "ethereum") -> Any:
    block = _bump_block()
    if method == "eth_blockNumber":
        return hex(block)
    if method == "eth_chainId":
        # Real chain IDs per EVM L1/L2 — production callers (web3 clients,
        # MetaMask, etc.) reject txs if the chainId doesn't match the network.
        return EVM_CHAIN_IDS.get(chain, "0x1")
    if method == "eth_getBalance":
        return "0xde0b6b3a7640000"  # 1 ETH (10^18 wei)
    if method == "eth_getTransactionCount":
        return hex(block % 1000)
    if method == "eth_gasPrice":
        return hex(20 * 10**9)  # 20 gwei
    if method == "eth_maxPriorityFeePerGas":
        return hex(2 * 10**9)  # 2 gwei
    if method == "eth_getBlockByNumber":
        # params: [block_num_hex, include_full_txs]
        block_hex = params[0] if params else hex(block)
        include_txs = params[1] if len(params) > 1 else False
        txs = (
            [
                {
                    "hash": _fake_tx_hash(),
                    "from": _fake_address(),
                    "to": _fake_address(),
                    "value": "0xde0b6b3a7640000",
                    "gas": "0x5208",
                    "gasPrice": "0x4a817c800",
                    "input": "0x",
                    "nonce": "0x0",
                    "blockHash": _fake_tx_hash(),
                    "blockNumber": block_hex,
                    "transactionIndex": hex(i),
                }
                for i in range(5)
            ]
            if include_txs
            else [_fake_tx_hash() for _ in range(5)]
        )
        return {
            "number": block_hex,
            "hash": _fake_tx_hash(),
            "parentHash": _fake_tx_hash(),
            "timestamp": hex(int(time.time())),
            "gasLimit": "0x1c9c380",
            "gasUsed": "0x5208",
            "miner": _fake_address(),
            "difficulty": "0x0",
            "totalDifficulty": "0x0",
            "size": "0x220",
            "transactions": txs,
            "uncles": [],
            "logsBloom": "0x" + "00" * 256,
            "stateRoot": _fake_tx_hash(),
            "receiptsRoot": _fake_tx_hash(),
            "transactionsRoot": _fake_tx_hash(),
            "extraData": "0x",
            "mixHash": _fake_tx_hash(),
            "nonce": "0x0000000000000000",
        }
    if method == "eth_getBlockByHash":
        # v1.4.5 round-05 P2 (defensive): forward chain to the recursive
        # call. Currently eth_getBlockByNumber returns no chain-specific
        # fields so the behavioral diff is zero, BUT eth_chainId inside
        # handle_evm IS chain-dependent — if future work adds chain-specific
        # block fields (BSC validator, Polygon zkProof, Base sequencer)
        # silently dropping `chain` would route bsc/base/polygon/scroll
        # callers through the ethereum default. Fix the latent bug now per
        # no-deferred-bugs skill rather than wait for the regression.
        return handle_evm("eth_getBlockByNumber",
                          [hex(block), params[1] if len(params) > 1 else False],
                          chain=chain)
    if method == "eth_getTransactionByHash":
        return {
            "hash": params[0] if params else _fake_tx_hash(),
            "blockHash": _fake_tx_hash(),
            "blockNumber": hex(block),
            "from": _fake_address(),
            "to": _fake_address(),
            "value": "0xde0b6b3a7640000",
            "gas": "0x5208",
            "gasPrice": "0x4a817c800",
            "input": "0x",
            "nonce": "0x0",
            "transactionIndex": "0x0",
        }
    if method == "eth_getTransactionReceipt":
        return {
            "transactionHash": params[0] if params else _fake_tx_hash(),
            "blockHash": _fake_tx_hash(),
            "blockNumber": hex(block),
            "from": _fake_address(),
            "to": _fake_address(),
            "gasUsed": "0x5208",
            "cumulativeGasUsed": "0x5208",
            "status": "0x1",
            "logs": [],
            "logsBloom": "0x" + "00" * 256,
            "transactionIndex": "0x0",
        }
    if method == "eth_getLogs":
        return []
    if method == "eth_call":
        return "0x"
    if method == "eth_estimateGas":
        return "0x5208"
    if method == "eth_getCode":
        return "0x"
    if method == "eth_syncing":
        return False
    if method == "net_version":
        return "1"
    if method == "net_listening":
        return True
    if method == "net_peerCount":
        return hex(50)
    if method == "web3_clientVersion":
        return "Mock/v1.0.0-mock/linux-amd64/go1.21"
    return None


# ── Starknet ──

def handle_starknet(method: str, params: List[Any]) -> Any:
    block = _bump_block()
    if method == "starknet_blockNumber":
        return block
    if method == "starknet_chainId":
        return "0x534e5f4d41494e"  # SN_MAIN
    if method == "starknet_getClassAt":
        return {
            "sierra_program": ["0x1", "0x2"],
            "contract_class_version": "0.1.0",
            "entry_points_by_type": {"EXTERNAL": [], "L1_HANDLER": [], "CONSTRUCTOR": []},
            "abi": "[]",
        }
    if method == "starknet_getNonce":
        return hex(block % 1000)
    if method == "starknet_getStorageAt":
        return "0x0"
    if method == "starknet_getBlockWithTxs":
        return {
            "block_hash": _fake_tx_hash(),
            "parent_hash": _fake_tx_hash(),
            "block_number": block,
            "new_root": _fake_tx_hash(),
            "timestamp": int(time.time()),
            "sequencer_address": _fake_tx_hash(),
            "transactions": [],
            "status": "ACCEPTED_ON_L2",
        }
    if method == "starknet_getEvents":
        return {"events": [], "continuation_token": None}
    if method == "starknet_getTransactionByHash":
        return {
            "transaction_hash": params[0] if params else _fake_tx_hash(),
            "max_fee": "0x1000000",
            "version": "0x1",
            "signature": ["0x1", "0x2"],
            "nonce": "0x0",
            "type": "INVOKE",
            "sender_address": _fake_tx_hash(),
            "calldata": [],
        }
    if method == "starknet_syncing":
        return False
    # Unknown method → None (signals "method not handled") — see handle_evm.
    return None


# ── Sui ──

def handle_sui(method: str, params: List[Any]) -> Any:
    block = _bump_block()
    if method == "sui_getLatestCheckpointSequenceNumber":
        return str(block)
    if method == "sui_getTotalTransactionBlocks":
        return str(block * 100)
    if method == "sui_getObject":
        return {
            "data": {
                "objectId": params[0] if params else "0x1",
                "version": str(block),
                "digest": _fake_tx_hash(),
                "type": "0x2::coin::Coin<0x2::sui::SUI>",
                "owner": {"AddressOwner": _fake_address()},
                "previousTransaction": _fake_tx_hash(),
                "storageRebate": "100",
                "content": {"dataType": "moveObject", "fields": {"balance": "1000000000"}},
            }
        }
    if method == "sui_getObjectsOwnedByAddress":
        return [{"objectId": _fake_address(), "version": str(block), "digest": _fake_tx_hash()}]
    if method == "suix_getOwnedObjects":
        return {"data": [{"data": {"objectId": _fake_address(), "version": str(block), "digest": _fake_tx_hash()}}], "hasNextPage": False, "nextCursor": None}
    if method == "sui_getTransactionBlock":
        return {
            "digest": params[0] if params else _fake_tx_hash(),
            "transaction": {"data": {"messageVersion": "v1", "transaction": {"kind": "ProgrammableTransaction"}}},
            "effects": {"status": {"status": "success"}, "gasUsed": {"computationCost": "1000"}},
            "checkpoint": str(block),
            "timestampMs": str(int(time.time() * 1000)),
        }
    if method == "suix_queryTransactionBlocks":
        return {"data": [], "hasNextPage": False, "nextCursor": None}
    if method == "sui_getChainIdentifier":
        return "35834a8a"  # mock mainnet
    # Unknown method → None (signals "method not handled") — see handle_evm.
    return None


# ─────────────────────────────────────────────────────────────────────
# Chain dispatch
# ─────────────────────────────────────────────────────────────────────

CHAIN_HANDLERS = {
    "solana": handle_solana,
    "ethereum": handle_evm,
    "bsc": handle_evm,
    "base": handle_evm,
    "polygon": handle_evm,
    "scroll": handle_evm,
    "starknet": handle_starknet,
    "sui": handle_sui,
}


def handle_unknown(method: str, params: List[Any]) -> Dict[str, Any]:
    """Fallback handler for chains without a real implementation yet.

    Returns an echo envelope so smoke tests can verify the request reached
    the server, while making it OBVIOUS in logs/asserts that no real
    semantics happened. Gated by env MOCK_ALLOW_UNKNOWN=1 in dispatch().

    Shape: {"_mock_echo": true, "_method": <m>, "_params": <p>}
    Callers MUST treat _mock_echo=true as "not validated" — never used to
    claim semantic correctness, only liveness.
    """
    return {"_mock_echo": True, "_method": method, "_params": params}


def dispatch(chain: str, method: str, params: List[Any]) -> Tuple[Any, Optional[Dict[str, Any]]]:
    """Return (result, error). Exactly one is None."""
    handler = CHAIN_HANDLERS.get(chain)
    if handler is None:
        # Fallback path — only when MOCK_ALLOW_UNKNOWN=1 (explicit opt-in).
        # Default behavior unchanged: reject with -32601 so unknown chains
        # surface loudly in CI rather than silently passing as ethereum.
        if os.environ.get("MOCK_ALLOW_UNKNOWN") == "1":
            try:
                result = handle_unknown(method, params)
                return result, None
            except Exception as e:
                return None, {"code": -32603, "message": f"Echo handler error: {e}"}
        return None, {"code": -32601, "message": f"Chain '{chain}' not supported"}
    try:
        # handle_evm accepts chain= kwarg for eth_chainId differentiation;
        # other handlers don't, so we sniff signature with a fallback.
        if handler is handle_evm:
            result = handler(method, params, chain)
        else:
            result = handler(method, params)
        if result is None:
            return None, {"code": -32601, "message": f"Method '{method}' not implemented for chain '{chain}'"}
        return result, None
    except Exception as e:
        return None, {"code": -32603, "message": f"Internal error: {e}"}


def process_jsonrpc(chain: str, payload: Union[Dict, List], latency_ms: int = 0) -> Union[Dict, List]:
    """Process single or batch JSON-RPC request."""
    if latency_ms > 0:
        time.sleep(latency_ms / 1000.0)
    if isinstance(payload, list):
        return [process_jsonrpc(chain, item, 0) for item in payload]
    method = payload.get("method", "")
    params = payload.get("params", [])
    req_id = payload.get("id")
    _count_request(method)
    result, error = dispatch(chain, method, params)
    if error:
        return {"jsonrpc": "2.0", "id": req_id, "error": error}
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


# ─────────────────────────────────────────────────────────────────────
# HTTP server
# ─────────────────────────────────────────────────────────────────────


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class RPCHandler(BaseHTTPRequestHandler):
    chain = "solana"
    latency_ms = 0

    def log_message(self, format, *args):
        # Suppress per-request stderr noise; we have our own counter
        pass

    def _send_json(self, code: int, obj: Any) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        # Health endpoint
        if self.path in ("/", "/health"):
            self._send_json(200, {
                "status": "ok",
                "chain": self.chain,
                "request_count": _REQ_COUNT,
                "top_methods": dict(sorted(_REQ_COUNT_BY_METHOD.items(), key=lambda x: -x[1])[:5]),
            })
            return
        self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            payload = json.loads(body)
        except Exception as e:
            self._send_json(400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"Parse error: {e}"}})
            return
        response = process_jsonrpc(self.chain, payload, self.latency_ms)
        self._send_json(200, response)


# ─────────────────────────────────────────────────────────────────────
# WebSocket server (stdlib socket-level upgrade)
# ─────────────────────────────────────────────────────────────────────

WS_MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def _ws_accept_key(client_key: str) -> str:
    sha = hashlib.sha1((client_key + WS_MAGIC).encode()).digest()
    return base64.b64encode(sha).decode()


def _ws_encode_frame(payload: bytes, opcode: int = 0x1) -> bytes:
    """Encode a WebSocket frame (server → client, no mask)."""
    header = bytearray()
    header.append(0x80 | opcode)  # FIN + opcode
    length = len(payload)
    if length < 126:
        header.append(length)
    elif length < 65536:
        header.append(126)
        header.extend(struct.pack(">H", length))
    else:
        header.append(127)
        header.extend(struct.pack(">Q", length))
    return bytes(header) + payload


def _ws_decode_frame(sock) -> Optional[bytes]:
    """Decode one WebSocket frame from client. Returns payload bytes or None on close."""
    try:
        hdr = sock.recv(2)
        if len(hdr) < 2:
            return None
        b1, b2 = hdr[0], hdr[1]
        fin = b1 & 0x80
        opcode = b1 & 0x0F
        masked = b2 & 0x80
        length = b2 & 0x7F
        if opcode == 0x8:  # close
            return None
        if length == 126:
            ext = sock.recv(2)
            length = struct.unpack(">H", ext)[0]
        elif length == 127:
            ext = sock.recv(8)
            length = struct.unpack(">Q", ext)[0]
        mask_key = sock.recv(4) if masked else b""
        payload = b""
        remaining = length
        while remaining > 0:
            chunk = sock.recv(min(4096, remaining))
            if not chunk:
                return None
            payload += chunk
            remaining -= len(chunk)
        if masked:
            payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
        return payload
    except Exception:
        return None


class WSServer:
    def __init__(self, host: str, port: int, chain: str, latency_ms: int = 0):
        self.host = host
        self.port = port
        self.chain = chain
        self.latency_ms = latency_ms

    def serve_forever(self):
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen(50)
        log.info(f"WS listening on ws://{self.host}:{self.port}")
        while True:
            client, addr = sock.accept()
            t = threading.Thread(target=self._handle, args=(client,), daemon=True)
            t.start()

    def _handle(self, client):
        try:
            # Read HTTP upgrade request
            data = b""
            while b"\r\n\r\n" not in data:
                chunk = client.recv(4096)
                if not chunk:
                    return
                data += chunk
                if len(data) > 16384:
                    return
            headers_text = data.decode(errors="replace")
            lines = headers_text.split("\r\n")
            req_line = lines[0]
            headers = {}
            for line in lines[1:]:
                if ":" in line:
                    k, v = line.split(":", 1)
                    headers[k.strip().lower()] = v.strip()
            ws_key = headers.get("sec-websocket-key")
            if not ws_key:
                client.send(b"HTTP/1.1 400 Bad Request\r\n\r\n")
                return
            accept = _ws_accept_key(ws_key)
            response = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
            )
            client.send(response.encode())
            # Message loop
            while True:
                payload = _ws_decode_frame(client)
                if payload is None:
                    break
                try:
                    msg = json.loads(payload.decode())
                except Exception:
                    err = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
                    client.send(_ws_encode_frame(json.dumps(err).encode()))
                    continue
                # Handle subscriptions specially (return subscription id)
                method = msg.get("method", "")
                if "subscribe" in method.lower() and not method.endswith("unsubscribe"):
                    global _NEXT_SUB_ID
                    with _STATE_LOCK:
                        sub_id = _NEXT_SUB_ID
                        _NEXT_SUB_ID += 1
                    response = {"jsonrpc": "2.0", "id": msg.get("id"), "result": sub_id}
                    client.send(_ws_encode_frame(json.dumps(response).encode()))
                    # Fire a couple of fake notifications to validate the wire
                    threading.Thread(target=self._notify_loop, args=(client, sub_id, method), daemon=True).start()
                    continue
                if "unsubscribe" in method.lower():
                    response = {"jsonrpc": "2.0", "id": msg.get("id"), "result": True}
                    client.send(_ws_encode_frame(json.dumps(response).encode()))
                    continue
                # Regular JSON-RPC
                response = process_jsonrpc(self.chain, msg, self.latency_ms)
                client.send(_ws_encode_frame(json.dumps(response).encode()))
        except Exception as e:
            log.debug(f"WS client error: {e}")
        finally:
            try:
                client.close()
            except Exception:
                pass

    def _notify_loop(self, client, sub_id: int, method: str):
        """Send 3 fake subscription notifications then stop."""
        for i in range(3):
            time.sleep(1)
            try:
                if "slot" in method.lower() or "Slot" in method:
                    params = {"subscription": sub_id, "result": {"slot": _bump_slot(), "parent": _bump_slot() - 1, "root": _bump_slot() - 32}}
                elif "newHeads" in method or "head" in method.lower():
                    params = {"subscription": sub_id, "result": {"number": hex(_bump_block()), "hash": _fake_tx_hash(), "parentHash": _fake_tx_hash(), "timestamp": hex(int(time.time()))}}
                else:
                    params = {"subscription": sub_id, "result": {"value": f"notification-{i}"}}
                notification = {"jsonrpc": "2.0", "method": f"{method.replace('subscribe', 'Notification').replace('Subscribe', 'Notification')}", "params": params}
                client.send(_ws_encode_frame(json.dumps(notification).encode()))
            except Exception:
                break


# ─────────────────────────────────────────────────────────────────────
# Stats thread
# ─────────────────────────────────────────────────────────────────────


def _stats_loop(interval: int = 30):
    last_count = 0
    while True:
        time.sleep(interval)
        with _STATE_LOCK:
            cur = _REQ_COUNT
            top = dict(sorted(_REQ_COUNT_BY_METHOD.items(), key=lambda x: -x[1])[:5])
        rps = (cur - last_count) / interval
        log.info(f"stats: total={cur} rps={rps:.1f} top={top}")
        last_count = cur


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────


def main():
    p = argparse.ArgumentParser(description="Mock RPC server for blockchain-node-benchmark e2e testing.")
    p.add_argument("--host", default="127.0.0.1", help="bind address (default 127.0.0.1)")
    p.add_argument("--port", type=int, default=8899, help="HTTP port (default 8899 = solana convention)")
    p.add_argument("--ws-port", type=int, default=None, help="WebSocket port (default: HTTP port + 1)")
    p.add_argument("--chain", default="solana",
                   help="chain to mock; must be in CHAIN_HANDLERS unless MOCK_ALLOW_UNKNOWN=1 (then any chain → echo fallback)")
    p.add_argument("--latency-ms", type=int, default=0, help="artificial per-request latency in ms (default 0)")
    p.add_argument("--no-ws", action="store_true", help="disable WebSocket server")
    p.add_argument("--stats-interval", type=int, default=30, help="seconds between stats prints (default 30)")
    args = p.parse_args()

    # Startup gate — refuse unknown chain unless explicit opt-in.
    if args.chain not in CHAIN_HANDLERS and os.environ.get("MOCK_ALLOW_UNKNOWN") != "1":
        known = ", ".join(sorted(CHAIN_HANDLERS.keys()))
        print(f"ERROR: chain '{args.chain}' has no handler. Known: {known}. "
              f"Set MOCK_ALLOW_UNKNOWN=1 to use echo fallback.", file=sys.stderr)
        sys.exit(2)

    ws_port = args.ws_port if args.ws_port else (args.port + 1)

    # Configure handler class
    RPCHandler.chain = args.chain
    RPCHandler.latency_ms = args.latency_ms

    # Stats thread
    threading.Thread(target=_stats_loop, args=(args.stats_interval,), daemon=True).start()

    # HTTP server
    http_server = ThreadingHTTPServer((args.host, args.port), RPCHandler)
    http_thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    http_thread.start()
    log.info(f"HTTP listening on http://{args.host}:{args.port} (chain={args.chain})")

    # WebSocket server
    if not args.no_ws:
        ws = WSServer(args.host, ws_port, args.chain, args.latency_ms)
        ws_thread = threading.Thread(target=ws.serve_forever, daemon=True)
        ws_thread.start()

    log.info(f"Mock RPC server READY — chain={args.chain} http_port={args.port} ws_port={ws_port if not args.no_ws else 'disabled'} latency={args.latency_ms}ms")
    log.info("Send SIGINT (Ctrl-C) to stop")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        log.info(f"Shutting down. Final stats: total={_REQ_COUNT} top={dict(sorted(_REQ_COUNT_BY_METHOD.items(), key=lambda x: -x[1])[:10])}")


if __name__ == "__main__":
    main()
