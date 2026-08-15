"""DeepInfra image generation over its OpenAI-compatible endpoint."""
from __future__ import annotations
import logging
import os
from typing import Any

from agent.image_gen_provider import (
    DEFAULT_ASPECT_RATIO, ImageGenProvider, error_response, resolve_aspect_ratio,
    save_b64_image, save_url_image, success_response,
)

logger = logging.getLogger(__name__)
DEFAULT_BASE_URL = "https://api.deepinfra.com/v1/openai"
_SIZES = {"landscape": "1536x1024", "square": "1024x1024", "portrait": "1024x1536"}


def check_requirements() -> bool:
    try:
        import openai  # noqa: F401
    except ImportError:
        return False
    return bool(os.getenv("DEEPINFRA_API_KEY", "").strip())


class DeepInfraImageGenProvider(ImageGenProvider):
    @property
    def name(self) -> str: return "deepinfra"

    @property
    def display_name(self) -> str: return "DeepInfra"

    def is_available(self) -> bool: return check_requirements()

    def capabilities(self) -> dict[str, Any]:
        return {"modalities": ["text"], "max_reference_images": 0,
                "operations": ["generate", "batch"]}

    def list_models(self):
        model = os.getenv("DEEPINFRA_IMAGE_MODEL", "").strip()
        return [{"id": model, "display": model.split("/")[-1]}] if model else []

    def default_model(self):
        return os.getenv("DEEPINFRA_IMAGE_MODEL", "").strip() or None

    def get_setup_schema(self):
        return {"name": "DeepInfra", "badge": "paid", "tag": "OpenAI-compatible image generation",
                "env_vars": [{"key": "DEEPINFRA_API_KEY", "prompt": "DeepInfra API key",
                              "url": "https://deepinfra.com/dash/api_keys"}]}

    def generate(self, prompt: str, aspect_ratio: str = DEFAULT_ASPECT_RATIO, **kwargs: Any):
        aspect = resolve_aspect_ratio(aspect_ratio)
        model = str(kwargs.get("model") or self.default_model() or "").strip()
        if kwargs.get("image_url") or kwargs.get("reference_image_urls"):
            return error_response(error="DeepInfra image provider is text-to-image only",
                                  error_type="modality_unsupported", provider=self.name,
                                  prompt=prompt, aspect_ratio=aspect)
        if not prompt or not prompt.strip():
            return error_response(error="prompt is required", error_type="invalid_argument",
                                  provider=self.name, aspect_ratio=aspect)
        key = os.getenv("DEEPINFRA_API_KEY", "").strip()
        if not key:
            return error_response(error="DEEPINFRA_API_KEY is not set", error_type="auth_required",
                                  provider=self.name, prompt=prompt, aspect_ratio=aspect)
        if not model:
            return error_response(error="Set DEEPINFRA_IMAGE_MODEL to an image-capable model",
                                  error_type="no_model_available", provider=self.name,
                                  prompt=prompt, aspect_ratio=aspect)
        try:
            import openai
            client = openai.OpenAI(api_key=key, base_url=os.getenv("DEEPINFRA_BASE_URL", DEFAULT_BASE_URL).rstrip("/"))
            response = client.images.generate(model=model, prompt=prompt, size=_SIZES[aspect], n=1)
            data = getattr(response, "data", None) or []
            if not data:
                raise ValueError("empty image response")
            item = data[0]
            if getattr(item, "b64_json", None):
                image = str(save_b64_image(item.b64_json, prefix="deepinfra"))
            elif getattr(item, "url", None):
                image = str(save_url_image(item.url, prefix="deepinfra"))
            else:
                raise ValueError("response had neither b64_json nor url")
            return success_response(image=image, model=model, prompt=prompt, aspect_ratio=aspect, provider=self.name)
        except Exception as exc:
            logger.debug("DeepInfra image generation failed", exc_info=True)
            return error_response(error=f"DeepInfra image generation failed: {exc}", error_type="api_error",
                                  provider=self.name, model=model, prompt=prompt, aspect_ratio=aspect)


def register(ctx) -> None:
    ctx.register_image_gen_provider(DeepInfraImageGenProvider())
