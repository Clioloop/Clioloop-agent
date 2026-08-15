"""Vertex AI generic OpenAI-compatible provider foundation.

Operators supply a short-lived OAuth access token and the regional OpenAI
compatibility base URL; Clio does not read service-account files implicitly.
"""
from providers import register_provider
from providers.base import ProviderProfile

vertex = ProviderProfile(
    name="vertex",
    aliases=("google-vertex", "vertex-ai", "gcp-vertex"),
    display_name="Google Vertex AI",
    description="Gemini via Vertex OpenAI-compatible endpoint",
    env_vars=("VERTEX_ACCESS_TOKEN", "VERTEX_BASE_URL"),
    base_url="https://aiplatform.googleapis.com",
    supports_health_check=False,
    supports_vision=True,
)
register_provider(vertex)
