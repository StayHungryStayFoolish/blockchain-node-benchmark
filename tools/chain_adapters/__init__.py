"""Chain adapter package — protocol-family abstraction for vegeta target generation
and health probing.

Design:
    - ABC `ChainAdapter` defines 4 methods: protocol_family, build_vegeta_target,
      health_check_request, parse_block_height
    - 6 concrete subclasses, one per protocol family
    - `get_adapter(chain_name)` factory reads config/chains/<chain>.json:_meta.adapter_family
      and dispatches

Why Python (not bash):
    bash cannot do polymorphism without case-dispatch — which is exactly what
    adapter pattern is meant to replace. Python is already used by mock_rpc_server.py
    and normalize_chain_templates.py in this repo.

Why HTTP/REST clients construct vegeta targets (not actually call HTTP):
    Vegeta runs the actual load. Adapters only build the request envelope.
"""
from .base import ChainAdapter, get_adapter, list_adapters

__all__ = ["ChainAdapter", "get_adapter", "list_adapters"]
