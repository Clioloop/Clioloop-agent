"""Canonical reasoning-effort vocabulary and provider-wire clamping.

Clio exposes ``minimal`` through ``xhigh`` as user-configurable reasoning
levels. Provider APIs expose overlapping, model-specific subsets of that
ladder, and a few use ``max`` as a wire-only ceiling. Keeping those mappings
at each call site caused the main transport, auxiliary client, and provider
profiles to disagree.

This module owns only vocabulary normalization. Wire shape remains local to
the transport/profile (``reasoning.effort``, top-level
``reasoning_effort``, Gemini ``thinkingLevel``, and so on).
"""

from __future__ import annotations

import re
from typing import Optional, Sequence

# Low -> high. ``max`` remains a provider-wire/backwards-compatibility level;
# it is intentionally not added to clio_constants.VALID_REASONING_EFFORTS.
# Likewise, Clio does not accept an invented ``ultra`` setting.
EFFORT_LADDER: tuple[str, ...] = (
    "none",
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
)

OPENAI_COMPAT_WIRE_EFFORTS: tuple[str, ...] = (
    "none",
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
)

# OpenAI Responses model vocabularies. ``minimal`` is rejected by both;
# ``max`` is accepted only by GPT-5.6-family models.
CODEX_GPT56_EFFORTS: tuple[str, ...] = (
    "none",
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
)
CODEX_LEGACY_EFFORTS: tuple[str, ...] = (
    "none",
    "low",
    "medium",
    "high",
    "xhigh",
)
CODEX_RESPONSES_EFFORTS = CODEX_GPT56_EFFORTS

XAI_GROK46_EFFORTS: tuple[str, ...] = ("low", "medium", "high", "xhigh")
XAI_LEGACY_EFFORTS: tuple[str, ...] = ("low", "medium", "high")
ACTUAL_RELAY_EFFORTS: tuple[str, ...] = ("none", "low", "medium", "high", "max")

KIMI_K3_EFFORTS: tuple[str, ...] = ("low", "high", "max")
KIMI_K2_EFFORTS: tuple[str, ...] = ("low", "medium", "high")
KIMI_K3_OVERRIDES: dict[str, str] = {"medium": "high", "xhigh": "max"}
_KIMI_K3_SLUG_RE = re.compile(r"(?:^|[^a-z0-9])k3(?:[^a-z0-9]|$)")

TOKENHUB_EFFORTS: tuple[str, ...] = ("low", "medium", "high")
DEEPSEEK_V4_EFFORTS: tuple[str, ...] = ("low", "medium", "high", "max")
DEEPSEEK_V4_OVERRIDES: dict[str, str] = {"xhigh": "max"}
SOLAR_EFFORTS: tuple[str, ...] = ("low", "medium", "high")
GEMINI_FLASH_EFFORTS: tuple[str, ...] = ("low", "medium", "high")
GEMINI_PRO_EFFORTS: tuple[str, ...] = ("low", "high")

ANTHROPIC_47_EFFORTS: tuple[str, ...] = (
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
)
ANTHROPIC_LEGACY_ADAPTIVE_EFFORTS: tuple[str, ...] = (
    "low",
    "medium",
    "high",
    "max",
)
ANTHROPIC_LEGACY_ADAPTIVE_OVERRIDES: dict[str, str] = {"xhigh": "max"}


def codex_supported_efforts(model: Optional[str]) -> tuple[str, ...]:
    """Return the Responses effort vocabulary for an OpenAI model."""
    if "gpt-5.6" in (model or "").lower():
        return CODEX_GPT56_EFFORTS
    return CODEX_LEGACY_EFFORTS


def xai_supported_efforts(model: Optional[str]) -> tuple[str, ...]:
    """Return xAI's model-aware effort vocabulary."""
    if "grok-4.6" in (model or "").lower():
        return XAI_GROK46_EFFORTS
    return XAI_LEGACY_EFFORTS


def kimi_supported_efforts(model: Optional[str]) -> tuple[str, ...]:
    """Return Kimi K3 or K2-era effort vocabulary for a model slug.

    K3 plan variants such as ``k3-256k`` are boundary-matched along with
    ``k3`` and ``kimi-k3-*`` without misclassifying K2-era names.
    """
    slug = (model or "").strip().lower().split("/")[-1]
    if _KIMI_K3_SLUG_RE.search(slug):
        return KIMI_K3_EFFORTS
    return KIMI_K2_EFFORTS


def clamp_effort(
    effort: Optional[str],
    supported: Optional[Sequence[str]],
    overrides: Optional[dict[str, str]] = None,
) -> Optional[str]:
    """Clamp an explicit effort to a provider's supported wire levels.

    Supported values pass through. Otherwise the nearest weaker level is
    selected so normalization does not silently increase cost. If no weaker
    level exists, the provider's weakest enabled level is used. ``none`` is
    never selected as a degradation target because that would disable
    reasoning. Unknown custom levels pass through unchanged for backwards
    compatibility with bespoke providers.
    """
    requested = str(effort or "").strip().lower()
    if not requested or not supported:
        return effort

    supported_norm = tuple(
        level
        for raw in supported
        if (level := str(raw).strip().lower()) in EFFORT_LADDER
    )
    if not supported_norm or requested in supported_norm:
        return requested if requested else effort

    if overrides:
        mapped = str(overrides.get(requested) or "").strip().lower()
        if mapped in supported_norm:
            return mapped

    if requested not in EFFORT_LADDER:
        return effort

    enabled = tuple(level for level in supported_norm if level != "none")
    if not enabled:
        return effort

    requested_rank = EFFORT_LADDER.index(requested)
    weaker = tuple(
        level for level in enabled if EFFORT_LADDER.index(level) < requested_rank
    )
    if weaker:
        return max(weaker, key=EFFORT_LADDER.index)
    return min(enabled, key=EFFORT_LADDER.index)


def requested_effort(reasoning_config: Optional[dict]) -> Optional[str]:
    """Extract an explicit enabled effort, or return ``None`` when unset."""
    if not isinstance(reasoning_config, dict):
        return None
    if reasoning_config.get("enabled") is False:
        return None
    effort = str(reasoning_config.get("effort") or "").strip().lower()
    return effort or None


def normalize_reasoning_config(
    reasoning_config: Optional[dict],
    supported: Optional[Sequence[str]],
    overrides: Optional[dict[str, str]] = None,
) -> Optional[dict]:
    """Copy a reasoning config and clamp its explicit effort for a wire."""
    if not isinstance(reasoning_config, dict):
        return reasoning_config
    effort = requested_effort(reasoning_config)
    if effort is None:
        return dict(reasoning_config)
    normalized = dict(reasoning_config)
    normalized["effort"] = clamp_effort(effort, supported, overrides)
    return normalized
