"""DeepInfra generic OpenAI-compatible provider."""
from providers import register_provider
from providers.base import ProviderProfile

deepinfra = ProviderProfile(
    name="deepinfra",
    aliases=("deep-infra", "deepinfra-ai"),
    display_name="DeepInfra",
    description="DeepInfra open-model inference",
    signup_url="https://deepinfra.com/dash/api_keys",
    env_vars=("DEEPINFRA_API_KEY", "DEEPINFRA_BASE_URL"),
    base_url="https://api.deepinfra.com/v1/openai",
    default_max_tokens=None,
)
register_provider(deepinfra)
