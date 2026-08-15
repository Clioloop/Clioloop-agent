"""Scoped registry for secret-provider adapters."""
from __future__ import annotations
import threading
from .base import SECRET_PROVIDER_API_VERSION, SecretProvider

_lock = threading.RLock()
_providers: dict[str, dict[str, SecretProvider]] = {}


def register_provider(owner: str, provider: SecretProvider, *, replace: bool = False) -> bool:
    if not isinstance(provider, SecretProvider) or provider.api_version != SECRET_PROVIDER_API_VERSION:
        return False
    with _lock:
        scope = _providers.setdefault(owner, {})
        if provider.name in scope and not replace:
            return False
        scope[provider.name] = provider
    return True


def get_provider(owner: str, name: str) -> SecretProvider | None:
    with _lock:
        return _providers.get(owner, {}).get(name)


def unregister_provider(owner: str, name: str, provider: SecretProvider | None = None) -> bool:
    with _lock:
        scope = _providers.get(owner, {})
        current = scope.get(name)
        if current is None or (provider is not None and current is not provider):
            return False
        scope.pop(name, None)
        if not scope:
            _providers.pop(owner, None)
        return True
