"""Omni Loop Portal provider profile.

The portal speaks the OpenAI-compatible dialect (it proxies OpenRouter), so
reasoning config travels in ``extra_body.reasoning`` and every request
carries Clioloop's product-attribution tags for usage metering.
"""

from typing import Any

from agent.request_tags import request_tags
from providers import register_provider
from providers.base import ProviderProfile


class OmniLoopPortalProfile(ProviderProfile):
    """Omni Loop Portal — one OAuth login, 300+ models, attributed usage."""

    def build_extra_body(
        self, *, session_id: str | None = None, **context: Any
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"tags": request_tags()}
        if session_id:
            body["session_id"] = session_id
        return body

    def build_api_kwargs_extras(
        self,
        *,
        reasoning_config: dict | None = None,
        supports_reasoning: bool = False,
        **context: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """OpenRouter dialect: reasoning rides in extra_body.

        Defaults to medium effort for reasoning-capable models; an explicit
        ``enabled: False`` omits the field entirely (the portal forwards it
        verbatim, and some upstream routes 400 on a disabled-reasoning object).
        """
        if reasoning_config is None:
            if supports_reasoning:
                return {"reasoning": {"enabled": True, "effort": "medium"}}, {}
            return {}, {}
        if reasoning_config.get("enabled"):
            return {"reasoning": dict(reasoning_config)}, {}
        return {}, {}


register_provider(
    OmniLoopPortalProfile(
        name="managed",
        display_name="Omni Loop Portal",
        auth_type="oauth_device_code",
        aliases=("omni-loop-portal", "portal"),
    )
)
