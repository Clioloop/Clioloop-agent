"""OpenRouter image-output chat-completions provider.

Only the generic OpenRouter contract is implemented. No vendor-specific portal
or authentication endpoint is embedded here.
"""
from __future__ import annotations
import base64
import mimetypes
import os
from pathlib import Path
from typing import Any

from agent.image_gen_provider import (
    DEFAULT_ASPECT_RATIO, ImageGenProvider, error_response, resolve_aspect_ratio,
    save_b64_image, save_url_image, success_response,
)

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "google/gemini-3-pro-image"
_ASPECTS = {"landscape": "16:9", "square": "1:1", "portrait": "9:16"}


def check_requirements() -> bool:
    try:
        import requests  # noqa: F401
    except ImportError:
        return False
    return bool(os.getenv("OPENROUTER_API_KEY", "").strip())


def _image_ref(ref: str) -> str:
    ref = str(ref or "").strip()
    if ref.startswith(("http://", "https://", "data:")):
        return ref
    path = Path(ref).expanduser()
    raw = path.read_bytes()
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def _extract_images(payload: dict[str, Any]) -> list[str]:
    out = []
    for choice in payload.get("choices", []) if isinstance(payload, dict) else []:
        for image in (choice.get("message") or {}).get("images", []):
            url = (image.get("image_url") or {}).get("url") if isinstance(image, dict) else None
            if url: out.append(str(url))
    return out


class OpenRouterImageGenProvider(ImageGenProvider):
    @property
    def name(self) -> str: return "openrouter"

    @property
    def display_name(self) -> str: return "OpenRouter"

    def is_available(self) -> bool: return check_requirements()

    def capabilities(self):
        return {"modalities": ["text", "image"], "max_reference_images": 3,
                "operations": ["generate", "batch", "edit"]}

    def list_models(self):
        model = self.default_model()
        return [{"id": model, "display": model}]

    def default_model(self):
        return os.getenv("OPENROUTER_IMAGE_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL

    def get_setup_schema(self):
        return {"name": "OpenRouter (image)", "badge": "paid", "tag": "Image output via chat completions",
                "env_vars": [{"key": "OPENROUTER_API_KEY", "prompt": "OpenRouter API key",
                              "url": "https://openrouter.ai/keys"}]}

    def generate(self, prompt: str, aspect_ratio: str = DEFAULT_ASPECT_RATIO, *,
                 image_url: str | None = None, reference_image_urls: list[str] | None = None, **kwargs: Any):
        import requests
        key = os.getenv("OPENROUTER_API_KEY", "").strip()
        aspect = resolve_aspect_ratio(aspect_ratio)
        model = str(kwargs.get("model") or self.default_model())
        if not key:
            return error_response(error="OPENROUTER_API_KEY is not set", error_type="auth_required",
                                  provider=self.name, model=model, prompt=prompt, aspect_ratio=aspect)
        refs = ([image_url] if image_url else []) + list(reference_image_urls or kwargs.get("reference_images") or [])
        content = [{"type": "text", "text": prompt}]
        try:
            content.extend({"type": "image_url", "image_url": {"url": _image_ref(ref)}} for ref in refs[:3])
            response = requests.post(
                os.getenv("OPENROUTER_IMAGE_BASE_URL", DEFAULT_BASE_URL).rstrip("/") + "/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                         "HTTP-Referer": "https://clioloop.com", "X-Title": "Clio Agent"},
                json={"model": model, "modalities": ["image", "text"],
                      "messages": [{"role": "user", "content": content}],
                      "image_config": {"aspect_ratio": _ASPECTS[aspect]}}, timeout=300,
            )
            response.raise_for_status()
            images = _extract_images(response.json())
            if not images: raise ValueError("response contained no generated images")
            first = images[0]
            output = str(save_b64_image(first.split(",", 1)[1], prefix="openrouter")) if first.startswith("data:") else str(save_url_image(first, prefix="openrouter"))
            return success_response(image=output, model=model, prompt=prompt, aspect_ratio=aspect,
                                    provider=self.name, extra={"modality": "image" if refs else "text"})
        except Exception as exc:
            return error_response(error=f"OpenRouter image generation failed: {exc}", error_type="api_error",
                                  provider=self.name, model=model, prompt=prompt, aspect_ratio=aspect)


def register(ctx) -> None:
    ctx.register_image_gen_provider(OpenRouterImageGenProvider())
