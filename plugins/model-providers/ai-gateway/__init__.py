"""Vercel AI Gateway provider."""
from providers import register_provider
from providers.base import ProviderProfile

ai_gateway = ProviderProfile(
    name="ai-gateway",
    aliases=("vercel", "vercel-ai-gateway", "ai_gateway", "aigateway"),
    display_name="Vercel AI Gateway",
    env_vars=("AI_GATEWAY_API_KEY",),
    base_url="https://ai-gateway.vercel.sh/v1",
    default_headers={"HTTP-Referer": "https://clioloop.com", "X-Title": "Clio Agent"},
)
register_provider(ai_gateway)
