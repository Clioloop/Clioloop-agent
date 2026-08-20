"""Kimi / Moonshot provider profiles.

Kimi has dual endpoints:
  - sk-kimi-* keys → api.kimi.com/coding (Anthropic Messages API)
  - legacy keys → api.moonshot.ai/v1 (OpenAI chat completions)

This module covers the chat_completions path (/v1 endpoint).
"""

from typing import Any

from providers import register_provider
from providers.base import OMIT_TEMPERATURE, ProviderProfile


class KimiProfile(ProviderProfile):
    """Kimi/Moonshot — temperature omitted, thinking + reasoning_effort."""

    def build_api_kwargs_extras(
        self,
        *,
        reasoning_config: dict | None = None,
        model: str | None = None,
        **context,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Kimi uses extra_body.thinking + top-level reasoning_effort."""
        extra_body = {}
        top_level = {}

        if not reasoning_config or not isinstance(reasoning_config, dict):
            # No config → thinking enabled, model/server default effort.
            from agent.reasoning_effort import KIMI_K3_EFFORTS, kimi_supported_efforts

            supported = kimi_supported_efforts(model)
            extra_body["thinking"] = {"type": "enabled"}
            top_level["reasoning_effort"] = (
                "high" if supported is KIMI_K3_EFFORTS else "medium"
            )
            return extra_body, top_level

        enabled = reasoning_config.get("enabled", True)
        if enabled is False:
            extra_body["thinking"] = {"type": "disabled"}
            return extra_body, top_level

        # Enabled: clamp Clio's effort to the selected Kimi generation's
        # documented wire vocabulary. K3 plan slugs (for example k3-256k)
        # use low/high/max; K2-era models use low/medium/high.
        from agent.reasoning_effort import (
            KIMI_K3_EFFORTS,
            KIMI_K3_OVERRIDES,
            clamp_effort,
            kimi_supported_efforts,
        )

        extra_body["thinking"] = {"type": "enabled"}
        supported = kimi_supported_efforts(model)
        overrides = KIMI_K3_OVERRIDES if supported is KIMI_K3_EFFORTS else None
        effort = (reasoning_config.get("effort") or "").strip().lower()
        if effort:
            clamped = clamp_effort(effort, supported, overrides)
            if clamped in supported:
                top_level["reasoning_effort"] = clamped
        if "reasoning_effort" not in top_level:
            top_level["reasoning_effort"] = (
                "high" if supported is KIMI_K3_EFFORTS else "medium"
            )

        return extra_body, top_level


kimi = KimiProfile(
    name="kimi-coding",
    aliases=("kimi", "moonshot", "kimi-for-coding"),
    env_vars=("KIMI_API_KEY", "KIMI_CODING_API_KEY"),
    base_url="https://api.moonshot.ai/v1",
    fixed_temperature=OMIT_TEMPERATURE,
    default_max_tokens=32000,
    default_headers={"User-Agent": "clio-agent/1.0"},
    default_aux_model="kimi-k2-turbo-preview",
)

kimi_cn = KimiProfile(
    name="kimi-coding-cn",
    aliases=("kimi-cn", "moonshot-cn"),
    env_vars=("KIMI_CN_API_KEY",),
    base_url="https://api.moonshot.cn/v1",
    fixed_temperature=OMIT_TEMPERATURE,
    default_max_tokens=32000,
    default_headers={"User-Agent": "clio-agent/1.0"},
    default_aux_model="kimi-k2-turbo-preview",
)

register_provider(kimi)
register_provider(kimi_cn)
