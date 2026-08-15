"""Fireworks AI generic OpenAI-compatible provider."""
from providers import register_provider
from providers.base import ProviderProfile

fireworks = ProviderProfile(
    name="fireworks",
    aliases=("fireworks-ai", "fw"),
    display_name="Fireworks AI",
    description="Fast production inference",
    signup_url="https://app.fireworks.ai/settings/users/api-keys",
    env_vars=("FIREWORKS_API_KEY",),
    base_url="https://api.fireworks.ai/inference/v1",
    default_headers={"HTTP-Referer": "https://clioloop.com", "X-Title": "Clio Agent"},
    fallback_models=("accounts/fireworks/models/kimi-k2p6", "accounts/fireworks/models/glm-5p2"),
)
register_provider(fireworks)
