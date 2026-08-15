"""Actual Computer OpenAI-compatible provider."""
from providers import register_provider
from providers.base import ProviderProfile

actual = ProviderProfile(
    name="actual",
    aliases=("actual-computer", "actualcomputer", "aci"),
    display_name="Actual Computer",
    description="Actual Computer hosted or local inference",
    signup_url="https://actual.inc",
    env_vars=("ACTUAL_API_KEY", "ACTUAL_BASE_URL"),
    base_url="https://api.actual.inc/v1",
    api_mode="codex_responses",
)
register_provider(actual)
