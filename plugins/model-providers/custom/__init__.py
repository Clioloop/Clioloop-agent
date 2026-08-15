"""Custom / Ollama (local) provider profile.

Covers any endpoint registered as provider="custom", including local
Ollama instances and llama.cpp servers (Bonsai, Qwen, etc.). Key quirks:
  - ollama_num_ctx → extra_body.options.num_ctx (local context window)
  - reasoning_config disabled → extra_body.think = False (Ollama)
    AND chat_template_kwargs.enable_thinking = False (llama.cpp / Bonsai)
  - reasoning_config enabled → chat_template_kwargs.enable_thinking = True
    (so llama.cpp reasoning models like Bonsai know to think)
"""

from typing import Any

from providers import register_provider
from providers.base import ProviderProfile


class CustomProfile(ProviderProfile):
    """Custom/Ollama local provider — think=false, num_ctx, and
    llama.cpp chat_template_kwargs.enable_thinking support."""

    def build_api_kwargs_extras(
        self,
        *,
        reasoning_config: dict | None = None,
        ollama_num_ctx: int | None = None,
        **ctx: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        extra_body: dict[str, Any] = {}

        # Ollama context window
        if ollama_num_ctx:
            options = extra_body.get("options", {})
            options["num_ctx"] = ollama_num_ctx
            extra_body["options"] = options

        # Handle reasoning/thinking for both Ollama and llama.cpp backends
        if reasoning_config and isinstance(reasoning_config, dict):
            _effort = (reasoning_config.get("effort") or "").strip().lower()
            _enabled = reasoning_config.get("enabled", True)
            if _effort == "none" or _enabled is False:
                # Ollama-style: think = false
                extra_body["think"] = False
                # llama.cpp / Bonsai: chat_template_kwargs.enable_thinking = false
                # This is the verified mechanism to disable thinking in
                # llama-server's Jinja chat template for reasoning models.
                ctk = extra_body.get("chat_template_kwargs", {})
                ctk["enable_thinking"] = False
                extra_body["chat_template_kwargs"] = ctk
            else:
                # Reasoning is enabled — tell llama.cpp to enable thinking
                ctk = extra_body.get("chat_template_kwargs", {})
                ctk["enable_thinking"] = True
                extra_body["chat_template_kwargs"] = ctk

        return extra_body, {}

    def fetch_models(
        self,
        *,
        api_key: str | None = None,
        timeout: float = 8.0,
    ) -> list[str] | None:
        """Custom/Ollama: base_url is user-configured; fetch if set."""
        if not self.base_url:
            return None
        return super().fetch_models(api_key=api_key, timeout=timeout)


custom = CustomProfile(
    name="custom",
    aliases=(
        "ollama",
        "local",
        "vllm",
        "llamacpp",
        "llama.cpp",
        "llama-cpp",
    ),
    env_vars=(),  # No fixed key — custom endpoint
    base_url="",  # User-configured
)

register_provider(custom)
