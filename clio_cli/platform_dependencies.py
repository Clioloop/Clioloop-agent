"""Shared dependency readiness for configured messaging platforms.

Setup surfaces must not accept credentials and report success for a platform
whose adapter cannot be imported.  This module is deliberately small and has
no UI dependencies so desktop APIs, CLI/TUI setup, updates, and the gateway
runtime all enforce the same contract.
"""

from __future__ import annotations

import importlib
import logging
import threading
from typing import Mapping

from tools.lazy_deps import FeatureUnavailable, ensure, feature_install_command

logger = logging.getLogger(__name__)


_PLATFORM_FEATURES: dict[str, str] = {
    "telegram": "platform.telegram",
}

_PLATFORM_CREDENTIALS: dict[str, tuple[str, ...]] = {
    "telegram": ("TELEGRAM_BOT_TOKEN",),
}

_PLATFORM_IMPORTS: dict[str, str] = {
    "telegram": "telegram",
}

_PLATFORM_REPAIR_COMMANDS: dict[str, str] = {
    "telegram": "clio update",
}

_PROVISION_LOCKS: dict[str, threading.Lock] = {
    platform_id: threading.Lock() for platform_id in _PLATFORM_FEATURES
}


class PlatformDependencyError(RuntimeError):
    """A configured platform cannot load its required Python SDK."""

    def __init__(
        self,
        *,
        platform_id: str,
        feature: str,
        reason: str,
        install_command: str | None,
    ) -> None:
        self.platform_id = platform_id
        self.feature = feature
        self.reason = reason
        self.install_command = install_command
        super().__init__(self._format())

    def _format(self) -> str:
        label = self.platform_id.replace("_", " ").title()
        message = f"{label} support is unavailable: {self.reason}."
        if self.install_command:
            message += f" Repair with: {self.install_command}"
        return message


def platform_feature(platform_id: str) -> str | None:
    return _PLATFORM_FEATURES.get(platform_id.strip().lower())


def configured_platforms(env: Mapping[str, str]) -> list[str]:
    """Return known platforms with a non-empty credential in ``env``."""

    configured: list[str] = []
    for platform_id, keys in _PLATFORM_CREDENTIALS.items():
        if any(str(env.get(key, "")).strip() for key in keys):
            configured.append(platform_id)
    return configured


def ensure_platform_ready(platform_id: str, *, prompt: bool = False) -> None:
    """Install/verify the SDK required by ``platform_id``.

    Unknown/plugin platforms are a no-op; plugins retain ownership of their
    own installation contract.  Known built-ins raise a typed, actionable
    error instead of degrading into a misleading adapter-less gateway.
    """

    normalized = platform_id.strip().lower()
    feature = platform_feature(normalized)
    if not feature:
        return

    try:
        # Desktop and dashboard can issue overlapping setup/save requests.
        # Serialize resolver work per platform so two requests cannot mutate the
        # same venv concurrently.
        with _PROVISION_LOCKS[normalized]:
            ensure(feature, prompt=prompt)
            module_name = _PLATFORM_IMPORTS.get(normalized)
            if module_name:
                importlib.import_module(module_name)
    except FeatureUnavailable as exc:
        # Full resolver detail belongs in logs.  The public exception remains
        # actionable without exposing credentials or dumping pages of pip text.
        logger.error("Dependency provisioning failed for %s: %s", normalized, exc)
        reason = exc.reason
        if reason.startswith("pip install failed:"):
            reason = "automatic dependency installation failed"
        raise PlatformDependencyError(
            platform_id=normalized,
            feature=feature,
            reason=reason,
            install_command=_PLATFORM_REPAIR_COMMANDS.get(normalized)
            or feature_install_command(feature),
        ) from exc
    except ImportError as exc:
        logger.error("Dependency import failed for %s: %s", normalized, exc)
        raise PlatformDependencyError(
            platform_id=normalized,
            feature=feature,
            reason="the installed SDK could not be imported",
            install_command=_PLATFORM_REPAIR_COMMANDS.get(normalized)
            or feature_install_command(feature),
        ) from exc


def repair_configured_platforms(
    env: Mapping[str, str], *, prompt: bool = False
) -> dict[str, str]:
    """Reconcile dependencies for configured platforms without raising."""

    results: dict[str, str] = {}
    for platform_id in configured_platforms(env):
        try:
            ensure_platform_ready(platform_id, prompt=prompt)
            results[platform_id] = "ready"
        except PlatformDependencyError as exc:
            results[platform_id] = f"failed: {exc}"
    return results
