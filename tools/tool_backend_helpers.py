"""Shared helpers for tool backend selection."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from utils import is_truthy_value


_DEFAULT_BROWSER_PROVIDER = "local"
_DEFAULT_MODAL_MODE = "auto"
_VALID_MODAL_MODES = {"auto", "direct", "managed"}


def _portal_account_info(*, force_fresh: bool = False):
    """Fetch Omni Loop Portal Subscription account info via the module attribute.

    Looked up through ``clio_cli.portal_account`` (not a direct import) so
    tests can monkeypatch ``get_managed_portal_account_info`` at that path.
    Falls back to a no-kwargs call for legacy patched accessors.
    """
    from clio_cli import portal_account

    accessor = portal_account.get_managed_portal_account_info
    try:
        return accessor(force_fresh=force_fresh)
    except TypeError:
        return accessor()


def managed_tools_enabled(*, force_fresh: bool = False) -> bool:
    """Subscription gate for the Omni Loop Portal tool gateway.

    True when the user is logged into the portal AND the account is entitled
    to gateway services (any paid plan, or a free plan whose entitlements
    include at least one gateway vendor). Never raises — returns False on
    any failure so availability scans stay safe.
    """
    try:
        info = _portal_account_info(force_fresh=force_fresh)
    except Exception:
        return False
    if not getattr(info, "logged_in", False):
        return False
    return bool(
        getattr(info, "paid_service_access", False)
        or getattr(info, "tool_gateway_entitled", False)
    )


def managed_tool_gateway_unavailable_message(
    capability: str = "the Omni Loop Portal Subscription Tool Gateway",
    *,
    force_fresh: bool = False,
) -> str:
    """Actionable guidance when a gateway capability is unavailable."""
    try:
        info = _portal_account_info(force_fresh=force_fresh)
    except Exception:
        info = None
    if info is None or not getattr(info, "logged_in", False):
        return (
            f"{capability} requires an Omni Loop Portal Subscription login. "
            "Connect with: clio setup --portal"
        )
    portal_url = str((getattr(info, "raw", {}) or {}).get("portal_url") or "").rstrip("/")
    upgrade = f" Upgrade at {portal_url}/pricing" if portal_url else " Upgrade your plan in the portal."
    return f"{capability} is not included in your Omni Loop Portal Subscription plan.{upgrade}"


def normalize_browser_cloud_provider(value: object | None) -> str:
    """Return a normalized browser provider key."""
    provider = str(value or _DEFAULT_BROWSER_PROVIDER).strip().lower()
    return provider or _DEFAULT_BROWSER_PROVIDER


def coerce_modal_mode(value: object | None) -> str:
    """Return the requested modal mode when valid, else the default."""
    mode = str(value or _DEFAULT_MODAL_MODE).strip().lower()
    if mode in _VALID_MODAL_MODES:
        return mode
    return _DEFAULT_MODAL_MODE


def normalize_modal_mode(value: object | None) -> str:
    """Return a normalized modal execution mode."""
    return coerce_modal_mode(value)


def has_direct_modal_credentials() -> bool:
    """Return True when direct Modal credentials/config are available."""
    try:
        modal_file_exists = (Path.home() / ".modal.toml").exists()
    except (PermissionError, OSError):
        modal_file_exists = False
    return bool(
        (os.getenv("MODAL_TOKEN_ID") and os.getenv("MODAL_TOKEN_SECRET"))
        or modal_file_exists
    )


def resolve_modal_backend_state(
    modal_mode: object | None,
    *,
    has_direct: bool,
    managed_ready: bool,
    managed_enabled: bool | None = None,
) -> Dict[str, Any]:
    """Resolve direct vs managed Modal backend selection.

    Semantics:
    - ``direct`` means direct-only
    - ``managed`` means managed-only
    - ``auto`` prefers managed when available, then falls back to direct
    """
    requested_mode = coerce_modal_mode(modal_mode)
    normalized_mode = normalize_modal_mode(modal_mode)
    if managed_enabled is None:
        managed_enabled = managed_tools_enabled()
    managed_mode_blocked = (
        requested_mode == "managed" and not managed_enabled
    )

    if normalized_mode == "managed":
        selected_backend = "managed" if managed_enabled and managed_ready else None
    elif normalized_mode == "direct":
        selected_backend = "direct" if has_direct else None
    else:
        selected_backend = "managed" if managed_enabled and managed_ready else "direct" if has_direct else None

    return {
        "requested_mode": requested_mode,
        "mode": normalized_mode,
        "has_direct": has_direct,
        "managed_ready": managed_ready,
        "managed_mode_blocked": managed_mode_blocked,
        "selected_backend": selected_backend,
    }


def resolve_openai_audio_api_key() -> str:
    """Prefer the voice-tools key, but fall back to the normal OpenAI key."""
    return (
        os.getenv("VOICE_TOOLS_OPENAI_KEY", "")
        or os.getenv("OPENAI_API_KEY", "")
    ).strip()


def prefers_gateway(config_section: str) -> bool:
    """Return True when the user opted into the Tool Gateway for this tool.

    Reads ``<section>.use_gateway`` from config.yaml.  Never raises.
    """
    try:
        from clio_cli.config import load_config
        section = (load_config() or {}).get(config_section)
        if isinstance(section, dict):
            return is_truthy_value(section.get("use_gateway"), default=False)
    except Exception:
        pass
    return False


def force_gateway(vendor: str, *, force_fresh: bool = False) -> bool:
    """Return True when subscription users should route this paid tool via the portal.

    A personal vendor key may still exist in the environment, but managed
    subscription usage must be metered by the Omni Loop Portal whenever the
    portal has a gateway for that vendor. Never raises: tools can safely call
    this during availability checks and fall back to their normal direct-key
    behavior when managed state cannot be resolved.
    """
    if not managed_tools_enabled(force_fresh=force_fresh):
        return False
    try:
        from tools.managed_tool_gateway import resolve_managed_tool_gateway

        return resolve_managed_tool_gateway(vendor) is not None
    except Exception:
        return False


def fal_key_is_configured() -> bool:
    """Return True when FAL_KEY is set to a non-whitespace value.

    Consults both ``os.environ`` and ``~/.clio/.env`` (via
    ``clio_cli.config.get_env_value`` when available) so tool-side
    checks and CLI setup-time checks agree.  A whitespace-only value
    is treated as unset everywhere.
    """
    value = os.getenv("FAL_KEY")
    if value is None:
        # Fall back to the .env file for CLI paths that may run before
        # dotenv is loaded into os.environ.
        try:
            from clio_cli.config import get_env_value

            value = get_env_value("FAL_KEY")
        except Exception:
            value = None
    return bool(value and value.strip())
