"""Runtime URL override helpers for chain adapters."""
from __future__ import annotations

import os
import re


_ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_ENV_DEFAULT_RE = re.compile(r"^\$\{([A-Z][A-Z0-9_]*):-([^}]*)\}$")


def first_url(*values: str | None) -> str:
    """Return the first non-empty URL value.

    If a value is an environment variable name, resolve it. This allows chain
    templates to keep stable defaults while user_config.sh provides runtime
    overrides for local sidecars, indexers, mirrors, or EVM companion RPCs.
    """
    for value in values:
        if not value:
            continue
        text = str(value).strip()
        if not text:
            continue
        env_value = os.environ.get(text)
        if env_value:
            return env_value
        if _ENV_NAME_RE.match(text):
            continue
        return text
    return ""


def resolve_value(value):
    """Resolve env placeholders while preserving template fallbacks.

    Supported forms:
      - "TARGET_ADDRESS" resolves to $TARGET_ADDRESS when set, otherwise the
        literal string is preserved.
      - "${TARGET_ADDRESS:-fallback}" resolves to $TARGET_ADDRESS when set,
        otherwise "fallback".
      - JSON-looking env values are decoded so array/object sample params can
        be overridden from user_config.sh.
    """
    if isinstance(value, str):
        match = _ENV_DEFAULT_RE.match(value)
        if match:
            env_name, fallback = match.groups()
            return _decode_env_value(os.environ.get(env_name) or fallback)
        env_value = os.environ.get(value)
        if env_value is not None:
            return _decode_env_value(env_value)
        return value
    if isinstance(value, list):
        return [resolve_value(item) for item in value]
    if isinstance(value, dict):
        return {key: resolve_value(item) for key, item in value.items()}
    return value


def resolve_param(params: dict, key: str, fallback=None):
    """Read a chain-template param with user_config.sh env override support."""
    if not isinstance(params, dict):
        return fallback
    return resolve_value(params.get(key, fallback))


def _decode_env_value(value: str):
    text = str(value)
    stripped = text.strip()
    if stripped.startswith(("[", "{")):
        try:
            import json
            return json.loads(stripped)
        except Exception:
            return text
    return text
