"""Stub: managed-provider subscription features.

The managed-provider subscription / tool-gateway flow (originally
powered by a third-party subscription portal) was removed in the
rebrand. This module preserves the public symbol surface so legacy
imports continue to resolve, but every accessor returns a safe
default indicating the feature is not available.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ManagedFeatureState:
    """Stand-in for a single managed-tool feature descriptor.

    Accepts positional and keyword arguments for compatibility with
    the legacy constructor used in the test suite.
    """

    key: str = ""
    label: str = ""
    available: bool = False
    active: bool = False
    managed_by_provider: bool = False
    included_by_default: bool = False
    current_provider: str = ""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Positional/keyword construction (legacy tests use both forms).
        field_names = (
            "key", "label", "available", "active",
            "managed_by_provider", "included_by_default", "current_provider",
        )
        for name, value in zip(field_names, args):
            setattr(self, name, value)
        # Legacy field name — keep accepting it as a write alias.
        if "managed_by_managed" in kwargs:
            setattr(self, "managed_by_provider", kwargs.pop("managed_by_managed"))
        for name, value in kwargs.items():
            setattr(self, name, value)

    @property
    def managed_by_managed(self) -> bool:  # pragma: no cover (legacy)
        return self.managed_by_provider


@dataclass
class ManagedSubscriptionFeatures:
    """Stand-in for the (removed) subscription-features bundle.

    Exposes ``.web`` / ``.browser`` / ``.image_gen`` / ``.video_gen`` /
    ``.tts`` / ``.modal`` as :class:`ManagedFeatureState` instances so
    callers that reach for these attributes in their tool-availability
    summaries keep working. The managed provider is not available, so
    every feature reports ``managed_by_provider=False``,
    ``available=False``, and ``active=False``.
    """

    provider_auth_present: bool = False
    account_info: Any = None
    items: list[ManagedFeatureState] = field(default_factory=list)
    features: dict[str, ManagedFeatureState] = field(default_factory=dict)
    web: ManagedFeatureState = field(
        default_factory=lambda: ManagedFeatureState(
            key="web", label="Web tools", available=False, active=False,
            managed_by_provider=False, included_by_default=False, current_provider="",
        )
    )
    browser: ManagedFeatureState = field(
        default_factory=lambda: ManagedFeatureState(
            key="browser", label="Browser automation", available=False, active=False,
            managed_by_provider=False, included_by_default=False, current_provider="",
        )
    )
    image_gen: ManagedFeatureState = field(
        default_factory=lambda: ManagedFeatureState(
            key="image_gen", label="Image generation", available=False, active=False,
            managed_by_provider=False, included_by_default=False, current_provider="",
        )
    )
    video_gen: ManagedFeatureState = field(
        default_factory=lambda: ManagedFeatureState(
            key="video_gen", label="Video generation", available=False, active=False,
            managed_by_provider=False, included_by_default=False, current_provider="",
        )
    )
    tts: ManagedFeatureState = field(
        default_factory=lambda: ManagedFeatureState(
            key="tts", label="Text-to-speech", available=False, active=False,
            managed_by_provider=False, included_by_default=False, current_provider="",
        )
    )
    modal: ManagedFeatureState = field(
        default_factory=lambda: ManagedFeatureState(
            key="modal", label="Modal execution", available=False, active=False,
            managed_by_provider=False, included_by_default=False, current_provider="",
        )
    )

    def items(self) -> list[ManagedFeatureState]:  # type: ignore[override]
        return [self.web, self.browser, self.image_gen, self.video_gen, self.tts, self.modal]

    # Legacy attribute alias — read-only.
    @property
    def managed_auth_present(self) -> bool:  # pragma: no cover (legacy)
        return self.provider_auth_present


def get_managed_subscription_features(*args: Any, **kwargs: Any) -> ManagedSubscriptionFeatures:
    """Return a default :class:`ManagedSubscriptionFeatures`.

    The managed provider is not available; every feature is unavailable.
    Accepts any args/kwargs for API parity with the legacy
    implementation (config, force_fresh, ...).
    """
    return ManagedSubscriptionFeatures()


def ensure_managed_provider_access(*args: Any, **kwargs: Any) -> bool:
    """Stub — always returns ``False`` (managed provider is not available)."""
    return False


def get_managed_provider_account_info(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Stub — returns an empty dict for legacy callers."""
    return {}


def get_managed_portal_account_info(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Alias for callers that still refer to the managed portal layer."""
    return get_managed_provider_account_info(*args, **kwargs)


def managed_provider_tools_enabled(*args: Any, **kwargs: Any) -> bool:
    """Stub — always returns ``False`` (managed provider is not available)."""
    return False


MANAGED_FEATURE_COVERAGE_CATEGORY: str = ""


def apply_managed_defaults(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Stub — returns an empty mapping (no managed defaults)."""
    return {}


__all__ = [
    "ManagedFeatureState",
    "ManagedSubscriptionFeatures",
    "get_managed_subscription_features",
    "ensure_managed_provider_access",
    "get_managed_provider_account_info",
    "get_managed_portal_account_info",
    "managed_provider_tools_enabled",
    "MANAGED_FEATURE_COVERAGE_CATEGORY",
    "apply_managed_defaults",
]

managed_tools_enabled = managed_provider_tools_enabled
