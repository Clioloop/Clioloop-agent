"""Small, dependency-free foundations shared by the plugin v2 host APIs."""
from __future__ import annotations

import copy
import json
import logging
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

logger = logging.getLogger(__name__)


class RegistrationHandle:
    """Idempotent host-owned lease for one plugin registration."""
    def __init__(self, owner: str, kind: str, key: str, disposer: Callable[[], None]):
        self.owner, self.kind, self.key = owner, kind, key
        self._disposer = disposer
        self._disposed = False
        self._lock = threading.Lock()

    @property
    def disposed(self) -> bool:
        return self._disposed

    def dispose(self) -> bool:
        with self._lock:
            if self._disposed:
                return False
            self._disposed = True
        try:
            self._disposer()
        except Exception:
            logger.warning("Failed disposing %s %s owned by %s", self.kind, self.key, self.owner, exc_info=True)
        return True


class OwnershipLedger:
    """Tracks leases by owner and disposes them deterministically in reverse order."""
    def __init__(self):
        self._by_owner: dict[str, list[RegistrationHandle]] = {}
        self._lock = threading.RLock()

    def own(self, owner: str, kind: str, key: str, disposer: Callable[[], None]) -> RegistrationHandle:
        handle = RegistrationHandle(owner, kind, key, disposer)
        with self._lock:
            self._by_owner.setdefault(owner, []).append(handle)
        return handle

    def adopt(self, owner: str, handle: RegistrationHandle) -> RegistrationHandle:
        """Track a handle created by another host registry (such as EventBus)."""
        if handle.owner != owner:
            raise ValueError("registration owner mismatch")
        with self._lock:
            self._by_owner.setdefault(owner, []).append(handle)
        return handle

    def dispose_owner(self, owner: str) -> int:
        with self._lock:
            handles = self._by_owner.pop(owner, [])
        for handle in reversed(handles):
            handle.dispose()
        return len(handles)

    def registrations(self, owner: str) -> tuple[RegistrationHandle, ...]:
        with self._lock:
            return tuple(self._by_owner.get(owner, ()))


@dataclass
class _Subscription:
    owner: str
    callback: Callable[..., Any]
    active: bool = True


class EventBus:
    """Isolated in-process bus; publishers can only emit in their namespace."""
    def __init__(self):
        self._subscriptions: dict[str, list[_Subscription]] = {}
        self._lock = threading.RLock()

    def subscribe(self, owner: str, event: str, callback: Callable[..., Any]) -> RegistrationHandle:
        if not event or ":" not in event or not callable(callback):
            raise ValueError("subscriptions require a fully-qualified event and callback")
        sub = _Subscription(owner, callback)
        with self._lock:
            self._subscriptions.setdefault(event, []).append(sub)

        def remove() -> None:
            sub.active = False
            with self._lock:
                current = self._subscriptions.get(event, [])
                self._subscriptions[event] = [item for item in current if item is not sub]
                if not self._subscriptions[event]:
                    self._subscriptions.pop(event, None)
        return RegistrationHandle(owner, "subscription", event, remove)

    def emit(self, owner: str, event: str, payload: Mapping[str, Any] | None = None) -> int:
        if not event or ":" in event:
            raise ValueError("emit accepts a non-empty bare event name")
        full_name = f"{owner}:{event}"
        with self._lock:
            listeners = tuple(self._subscriptions.get(full_name, ()))
        delivered = 0
        for sub in listeners:
            if not sub.active:
                continue
            try:
                sub.callback(**copy.deepcopy(dict(payload or {})))
                delivered += 1
            except Exception:
                logger.warning("Plugin event subscriber failed for %s", full_name, exc_info=True)
        return delivered


class NamespacedState:
    """A plugin-owned JSON object stored below a host-selected state root."""
    def __init__(self, root: Path, namespace: str):
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", namespace)
        self.path = root / f"{safe}.json"
        self._lock = threading.RLock()

    def read(self) -> dict[str, Any]:
        with self._lock:
            try:
                value = json.loads(self.path.read_text(encoding="utf-8"))
                return value if isinstance(value, dict) else {}
            except (OSError, ValueError):
                return {}

    def get(self, key: str, default: Any = None) -> Any:
        return self.read().get(key, default)

    def set(self, key: str, value: Any) -> None:
        data = self.read()
        data[key] = value
        self.replace(data)

    def replace(self, value: Mapping[str, Any]) -> None:
        encoded = json.dumps(dict(value), ensure_ascii=False, indent=2)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(f".{os.getpid()}.tmp")
            tmp.write_text(encoded, encoding="utf-8")
            os.replace(tmp, self.path)


class NamespacedConfig(Mapping[str, Any]):
    """Read-only view of ``plugins.entries.<id>.settings``."""
    def __init__(self, namespace: str):
        self.namespace = namespace

    def _data(self) -> dict[str, Any]:
        try:
            from clio_cli.config import load_config
            cfg = load_config() or {}
            value = (((cfg.get("plugins") or {}).get("entries") or {}).get(self.namespace) or {}).get("settings") or {}
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    def __getitem__(self, key: str) -> Any:
        return self._data()[key]

    def __iter__(self):
        return iter(self._data())

    def __len__(self) -> int:
        return len(self._data())


@dataclass(frozen=True)
class EgressRequest:
    plugin_id: str
    host: str
    port: int = 443
    protocol: str = "https"
    metadata: Mapping[str, Any] = field(default_factory=dict)


class EgressPolicy:
    """Host policy interface. Implementations must make an explicit decision."""
    def authorize(self, request: EgressRequest) -> bool:
        raise NotImplementedError


class DenyAllEgressPolicy(EgressPolicy):
    def authorize(self, request: EgressRequest) -> bool:
        return False


class AllowlistEgressPolicy(EgressPolicy):
    def __init__(self, hosts: set[str] | frozenset[str]):
        self.hosts = frozenset(host.lower().rstrip(".") for host in hosts)

    def authorize(self, request: EgressRequest) -> bool:
        return request.host.lower().rstrip(".") in self.hosts


class DenialCircuitBreaker:
    """Per-scope consecutive-denial breaker with bounded state."""
    def __init__(self, threshold: int = 3, max_scopes: int = 256):
        self.threshold = max(0, threshold)
        self.max_scopes = max(1, max_scopes)
        self._counts: dict[str, int] = {}
        self._lock = threading.Lock()

    def deny(self, scope: str) -> bool:
        with self._lock:
            if scope not in self._counts and len(self._counts) >= self.max_scopes:
                self._counts.pop(next(iter(self._counts)))
            self._counts[scope] = self._counts.get(scope, 0) + 1
            return self.threshold > 0 and self._counts[scope] >= self.threshold

    def allow(self, scope: str) -> None:
        with self._lock:
            self._counts.pop(scope, None)

    def count(self, scope: str) -> int:
        with self._lock:
            return self._counts.get(scope, 0)


def normalize_mcp_trust(value: Any) -> str:
    """MCP trust tier: legacy missing values are full; unknown values fail closed."""
    if value is None:
        return "full"
    normalized = str(value).strip().lower()
    return normalized if normalized in {"full", "read-only", "untrusted"} else "untrusted"


def mcp_call_requires_approval(trust: Any, read_only_hint: Any) -> bool:
    tier = normalize_mcp_trust(trust)
    if tier == "full":
        return False
    if tier == "read-only":
        return read_only_hint is not True
    return read_only_hint is not True
