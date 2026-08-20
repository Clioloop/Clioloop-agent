"""Persistent, profile-scoped MCP tool-schema cache for lazy server startup.

The cache stores only schemas and an opaque SHA-256 fingerprint.  Connection
credentials participate in the fingerprint (so rotations invalidate stale
schemas) but their plaintext is never persisted.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import logging
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_CACHE_FILENAME = "mcp_schema_cache.json"
_CACHE_FORMAT_VERSION = 2
_PROTOCOL_VERSION = "2025-03-26"
_SECRET_KEY = re.compile(
    r"(?:secret|token|password|authorization|api[_-]?key|cookie|client[_-]?key)",
    re.IGNORECASE,
)
_cache_lock = threading.Lock()


def _cache_path() -> Path:
    from clio_constants import get_clio_home

    return get_clio_home() / "cache" / _CACHE_FILENAME


def _clio_version() -> str:
    try:
        return importlib.metadata.version("clioloop-agent")
    except importlib.metadata.PackageNotFoundError:
        return "source"


def _fingerprint_value(value: Any, *, key: str = "") -> Any:
    """Canonicalize config while replacing credential values with digests."""
    if _SECRET_KEY.search(key):
        encoded = json.dumps(value, sort_keys=True, default=str).encode("utf-8")
        return {"secret_sha256": hashlib.sha256(encoded).hexdigest()}
    if isinstance(value, dict):
        return {
            str(k): _fingerprint_value(v, key=str(k))
            for k, v in sorted(value.items(), key=lambda item: str(item[0]))
            if str(k) not in {"enabled", "lazy"}
        }
    if isinstance(value, (list, tuple)):
        return [_fingerprint_value(v, key=key) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def config_fingerprint(config: dict) -> str:
    """Hash the complete connection identity without exposing credentials."""
    payload = {
        "cache_format": _CACHE_FORMAT_VERSION,
        "clio_version": _clio_version(),
        "mcp_protocol": _PROTOCOL_VERSION,
        "config": _fingerprint_value(config if isinstance(config, dict) else {}),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _load_all() -> Dict[str, Any]:
    path = _cache_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.debug("Could not read MCP schema cache %s: %s", path, exc)
        return {}


def _save_all(data: Dict[str, Any]) -> None:
    from utils import atomic_json_write

    atomic_json_write(_cache_path(), data, mode=0o600)


def get_cached_entry(server_name: str, fingerprint: str) -> Optional[dict]:
    """Return a matching unexpired cache entry, otherwise ``None``."""
    with _cache_lock:
        entry = _load_all().get(server_name)
    if not isinstance(entry, dict) or entry.get("fingerprint") != fingerprint:
        return None
    ttl_ms = entry.get("ttl_ms")
    written_at = entry.get("written_at")
    if isinstance(ttl_ms, (int, float)) and isinstance(written_at, (int, float)):
        if ttl_ms <= 0 or (time.time() - written_at) * 1000.0 >= float(ttl_ms):
            return None
    return entry


def has_cached_entry(server_name: str, fingerprint: str) -> bool:
    return get_cached_entry(server_name, fingerprint) is not None


def write_cache_entry(
    server_name: str,
    fingerprint: str,
    *,
    tools: List[dict],
    utility_tools: Optional[List[dict]] = None,
    ttl_ms: Optional[float] = None,
    cache_scope: Optional[str] = None,
) -> None:
    """Atomically persist a secret-free schema manifest after live discovery."""
    entry: Dict[str, Any] = {
        "fingerprint": fingerprint,
        "tools": tools,
        "utility_tools": utility_tools or [],
    }
    if isinstance(ttl_ms, (int, float)):
        entry["ttl_ms"] = ttl_ms
        entry["written_at"] = time.time()
    if cache_scope:
        entry["cache_scope"] = str(cache_scope)
    with _cache_lock:
        data = _load_all()
        if "written_at" not in entry and data.get(server_name) == entry:
            return
        data[server_name] = entry
        _save_all(data)


def clear_cache_entry(server_name: str) -> None:
    with _cache_lock:
        data = _load_all()
        if server_name in data:
            del data[server_name]
            _save_all(data)


def tools_from_cache_entry(entry: dict) -> List[dict]:
    tools = entry.get("tools")
    return list(tools) if isinstance(tools, list) else []


def utility_tools_from_cache_entry(entry: dict) -> List[dict]:
    tools = entry.get("utility_tools")
    return list(tools) if isinstance(tools, list) else []
