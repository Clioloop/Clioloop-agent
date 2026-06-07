"""Stub: managed-provider account info.

The managed-provider OAuth flow (originally powered by a third-party
subscription portal) was removed in the rebrand. This module preserves
the public symbol surface so legacy imports continue to resolve, but
every accessor returns a safe default indicating the managed provider
is not configured.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ManagedProviderAccountInfo:
    """Stand-in for the (removed) managed-provider account descriptor."""

    logged_in: bool = False
    source: str = ""
    fresh: bool = True
    inference_credential_present: bool = False
    inference_base_url: str = ""
    paid_service_access: Optional[bool] = None
    is_free_tier: bool = True
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ManagedProviderAccessInfo:
    """Stand-in for the (removed) paid-service descriptor."""

    enabled: bool = False
    service: str = ""
    tier: str = ""


def get_managed_provider_account_info(force_fresh: bool = False) -> ManagedProviderAccountInfo:
    """Return a default :class:`ManagedProviderAccountInfo`.

    The managed provider is not available in this build; every field
    defaults to its safe value. ``force_fresh`` is accepted for API
    parity with the legacy implementation and is ignored.
    """
    return ManagedProviderAccountInfo()


def get_managed_portal_account_info(force_fresh: bool = False) -> ManagedProviderAccountInfo:
    """Alias for callers that still refer to the managed portal layer."""
    return get_managed_provider_account_info(force_fresh=force_fresh)


def format_managed_provider_entitlement_message(
    account_info: Optional[ManagedProviderAccountInfo] = None,
    *,
    capability: str = "",
) -> str:
    """Return an empty message.

    The managed provider is not available; we do not advertise managed
    tools to users.
    """
    return ""


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
