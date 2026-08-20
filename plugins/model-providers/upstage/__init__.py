"""Upstage Solar generic provider with reasoning-effort translation."""
from typing import Any
from providers import register_provider
from providers.base import ProviderProfile

class UpstageProfile(ProviderProfile):
    def build_api_kwargs_extras(self, *, reasoning_config=None, model=None, **_context) -> tuple[dict[str, Any], dict[str, Any]]:
        if any(marker in (model or "").lower() for marker in ("solar-mini", "syn-pro")):
            return {}, {}
        if isinstance(reasoning_config, dict) and reasoning_config.get("enabled") is False:
            return {}, {}
        effort = (
            (reasoning_config or {}).get("effort", "medium")
            if isinstance(reasoning_config, dict)
            else "medium"
        )
        effort = str(effort).strip().lower()
        if effort == "minimal":
            return {}, {}

        from agent.reasoning_effort import SOLAR_EFFORTS, clamp_effort

        mapped = clamp_effort(effort, SOLAR_EFFORTS)
        if mapped not in SOLAR_EFFORTS:
            mapped = "high"
        return {}, {"reasoning_effort": mapped}

upstage = UpstageProfile(
    name="upstage", aliases=("solar",), display_name="Upstage Solar",
    signup_url="https://console.upstage.ai/api-keys",
    env_vars=("UPSTAGE_API_KEY", "UPSTAGE_BASE_URL"),
    base_url="https://api.upstage.ai/v1", fallback_models=("solar-pro3",),
)
register_provider(upstage)
