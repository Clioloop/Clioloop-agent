"""Pluggable cron-provider seam.

The built-in scheduler remains the default. Optional providers (for example an
external one-shot scheduler) register here and are selected explicitly through
``cron.provider`` or ``CLIO_CRON_PROVIDER``. Resolution always fails safe to the
built-in provider.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class CronProvider(Protocol):
    @property
    def name(self) -> str: ...
    def check_requirements(self) -> bool: ...
    def reconcile(self, jobs: list[dict[str, Any]]) -> None: ...
    def cancel(self, job_id: str) -> None: ...


_PROVIDERS: dict[str, CronProvider] = {}


def register_cron_provider(provider: CronProvider) -> None:
    if not isinstance(provider, CronProvider):
        raise TypeError("cron provider does not satisfy CronProvider")
    name = str(provider.name or "").strip().lower()
    if not name:
        raise ValueError("cron provider name is required")
    _PROVIDERS[name] = provider


def unregister_cron_provider(name: str, provider: CronProvider | None = None) -> bool:
    current = _PROVIDERS.get(name)
    if current is None or (provider is not None and current is not provider):
        return False
    del _PROVIDERS[name]
    return True


def get_cron_provider(name: str) -> CronProvider | None:
    return _PROVIDERS.get(str(name or "").strip().lower())


def configured_provider_name() -> str:
    env = os.getenv("CLIO_CRON_PROVIDER", "").strip().lower()
    if env:
        return env
    try:
        from clio_cli.config import load_config
        cfg = load_config()
        section = cfg.get("cron", {}) if isinstance(cfg, dict) else {}
        return str(section.get("provider") or "").strip().lower() if isinstance(section, dict) else ""
    except Exception:
        return ""


def resolve_cron_provider(name: str | None = None) -> CronProvider | None:
    """Return an explicitly selected, available provider; otherwise ``None``.

    ``None`` means callers must preserve the current in-process ticker.
    """
    selected = (name or configured_provider_name()).strip().lower()
    if not selected or selected in {"builtin", "local"}:
        return None
    provider = get_cron_provider(selected)
    if provider is None:
        logger.warning("Unknown cron provider %r; using built-in scheduler", selected)
        return None
    try:
        return provider if provider.check_requirements() else None
    except Exception as exc:
        logger.warning("Cron provider %s unavailable (%s); using built-in scheduler", selected, exc)
        return None
