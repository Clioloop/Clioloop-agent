"""Omni Loop Portal account info.

Queries the portal's ``/api/account/info`` endpoint (Bearer-authenticated
with the managed provider's OAuth access token) to report plan/entitlement
status — free vs paid tier, card verification, monthly usage.

Degrades gracefully: when the user is not logged into the portal, or the
portal is unreachable, every accessor returns a safe default indicating the
managed provider is not configured (the historical stub behaviour).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

_ACCOUNT_CACHE_TTL_SECONDS = 60.0
_account_cache: Optional[tuple[float, "ManagedProviderAccountInfo"]] = None


@dataclass
class ManagedProviderAccountInfo:
    """Account descriptor for the Omni Loop Portal managed provider."""

    logged_in: bool = False
    source: str = ""
    fresh: bool = True
    inference_credential_present: bool = False
    inference_base_url: str = ""
    paid_service_access: Optional[bool] = None
    is_free_tier: bool = True
    #: Bundled service availability — {"web": bool, "browser": bool,
    #: "image_gen": bool, "video_gen": bool, "tts": bool}.
    features: dict[str, bool] = field(default_factory=dict)
    #: Tool-gateway entitlement strings (vendor slugs + extras like
    #: "fal-video"); empty when the plan has no gateway access.
    tool_gateway_entitlements: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def tool_gateway_entitled(self) -> bool:
        """True when the account can use the portal's tool gateway at all."""
        return bool(self.tool_gateway_entitlements)

    def tool_gateway_entitled_for(self, entitlement: str) -> bool:
        """True when the account holds a specific gateway entitlement."""
        return entitlement in self.tool_gateway_entitlements


@dataclass
class ManagedProviderAccessInfo:
    """Paid-service descriptor for the Omni Loop Portal managed provider."""

    enabled: bool = False
    service: str = ""
    tier: str = ""


def _fetch_account_info(timeout_seconds: float = 10.0) -> ManagedProviderAccountInfo:
    """Hit the portal's /api/account/info with the stored OAuth credential."""
    from clio_cli.auth import (
        DEFAULT_MANAGED_PORTAL_URL,
        get_provider_auth_state,
        resolve_managed_access_token,
    )
    import os

    import httpx

    state = get_provider_auth_state("managed") or {}
    if not state.get("access_token"):
        return ManagedProviderAccountInfo()

    token = resolve_managed_access_token(timeout_seconds=timeout_seconds)
    portal_base_url = (
        str(state.get("portal_base_url") or "").strip()
        or os.getenv("CLIO_PORTAL_BASE_URL")
        or os.getenv("MANAGED_PORTAL_BASE_URL")
        or DEFAULT_MANAGED_PORTAL_URL
    ).rstrip("/")

    with httpx.Client(timeout=httpx.Timeout(timeout_seconds)) as client:
        response = client.get(
            f"{portal_base_url}/api/account/info",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
    if response.status_code != 200:
        logger.debug("portal account info returned %s", response.status_code)
        return ManagedProviderAccountInfo()

    data = response.json()
    if not isinstance(data, dict) or not data.get("logged_in"):
        return ManagedProviderAccountInfo()

    is_free = bool(data.get("is_free_tier", data.get("plan") in (None, "", "free")))
    return ManagedProviderAccountInfo(
        logged_in=True,
        source="device_code",
        fresh=True,
        inference_credential_present=True,
        inference_base_url=str(
            data.get("inference_base_url") or state.get("inference_base_url") or ""
        ),
        paid_service_access=bool(data.get("paid_service_access", not is_free)),
        is_free_tier=is_free,
        features={
            str(key): bool(value)
            for key, value in (data.get("features") or {}).items()
        },
        tool_gateway_entitlements=[
            str(item)
            for item in ((data.get("tool_gateway") or {}).get("entitlements") or [])
            if str(item).strip()
        ],
        raw=data,
    )


def get_managed_provider_account_info(force_fresh: bool = False) -> ManagedProviderAccountInfo:
    """Return the Omni Loop Portal account info for the current login.

    Results are cached for ~60s; pass ``force_fresh=True`` to bypass the
    cache (used right after purchases/upgrades). Any failure — not logged
    in, network error, malformed response — returns the safe default.
    """
    global _account_cache
    now = time.monotonic()
    if not force_fresh and _account_cache is not None:
        cached_at, cached_info = _account_cache
        if now - cached_at < _ACCOUNT_CACHE_TTL_SECONDS:
            return cached_info

    try:
        info = _fetch_account_info()
    except Exception as exc:
        logger.debug("portal account info fetch failed: %s", exc)
        info = ManagedProviderAccountInfo()
        info.fresh = False

    _account_cache = (now, info)
    return info


def get_managed_portal_account_info(force_fresh: bool = False) -> ManagedProviderAccountInfo:
    """Alias for callers that still refer to the managed portal layer."""
    return get_managed_provider_account_info(force_fresh=force_fresh)


def format_managed_provider_entitlement_message(
    account_info: Optional[ManagedProviderAccountInfo] = None,
    *,
    capability: str = "",
) -> str:
    """Human-readable upgrade hint for free-tier users (empty when paid)."""
    if account_info is None:
        account_info = get_managed_provider_account_info()
    if not account_info.logged_in or not account_info.is_free_tier:
        return ""

    from clio_cli.auth import DEFAULT_MANAGED_PORTAL_URL

    portal_url = (
        str(account_info.raw.get("portal_url") or "").strip()
        or DEFAULT_MANAGED_PORTAL_URL
    ).rstrip("/")
    what = capability or "paid models"
    return (
        f"Your Omni Loop Portal account is on the Free plan — {what} require "
        f"a paid plan. Upgrade at {portal_url}/pricing"
    )


def format_managed_portal_entitlement_message(
    account_info: Optional[ManagedProviderAccountInfo] = None,
    *,
    capability: str = "",
) -> str:
    """Alias for callers that still refer to the managed portal layer."""
    return format_managed_provider_entitlement_message(
        account_info=account_info,
        capability=capability,
    )


__all__ = [
    "ManagedProviderAccountInfo",
    "ManagedProviderAccessInfo",
    "get_managed_provider_account_info",
    "get_managed_portal_account_info",
    "format_managed_provider_entitlement_message",
    "format_managed_portal_entitlement_message",
]
