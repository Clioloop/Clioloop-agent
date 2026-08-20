"""xAI Grok Imagine image generation and editing backend."""

from __future__ import annotations

import base64
import logging
import mimetypes
import os
import time
from pathlib import Path
from typing import Any

import requests

from agent.image_gen_provider import (
    DEFAULT_ASPECT_RATIO,
    DEFAULT_IMAGE_ACTION,
    ImageGenProvider,
    error_response,
    resolve_aspect_ratio,
    save_b64_image,
    save_url_image,
    success_response,
)
from tools.xai_http import clio_xai_user_agent, resolve_xai_http_credentials

logger = logging.getLogger(__name__)

_MODELS: dict[str, dict[str, Any]] = {
    "grok-imagine-image": {
        "display": "Grok Imagine Image",
        "speed": "~5-10s",
        "strengths": "Fast, high-quality",
    },
    "grok-imagine-image-2.0": {
        "display": "Grok Imagine Image 2.0",
        "speed": "~10-20s",
        "strengths": "Typography/layout-aware; strongest quality",
    },
    "grok-imagine-image-quality": {
        "display": "Grok Imagine Image (Quality)",
        "speed": "~10-20s",
        "strengths": "High fidelity and detail",
        "input_modalities": ["text", "image"],
    },
}
DEFAULT_MODEL = "grok-imagine-image"
DEFAULT_EDIT_MODEL = "grok-imagine-image-quality"
DEFAULT_RESOLUTION = "1k"
_LIVE_CACHE: tuple[dict[str, dict[str, Any]], float] | None = None
_LIVE_TTL = 300.0
_STALE_MAX = 7 * 24 * 3600.0
_XAI_ASPECT_RATIOS = {
    "landscape": "16:9", "square": "1:1", "portrait": "9:16",
}
_XAI_RESOLUTIONS = {"1k", "2k"}


def _load_xai_config() -> dict[str, Any]:
    try:
        from clio_cli.config import load_config

        cfg = load_config()
        section = cfg.get("image_gen") if isinstance(cfg, dict) else None
        xai = section.get("xai") if isinstance(section, dict) else None
        return xai if isinstance(xai, dict) else {}
    except Exception:
        return {}


def _fetch_live_models() -> dict[str, dict[str, Any]]:
    creds = resolve_xai_http_credentials()
    api_key = str(creds.get("api_key") or "").strip()
    if not api_key:
        raise RuntimeError("no xAI credentials")
    base_url = str(creds.get("base_url") or "https://api.x.ai/v1").strip().rstrip("/")
    response = requests.get(
        f"{base_url}/image-generation-models",
        headers={
            "Authorization": f"Bearer {api_key}",
            "User-Agent": clio_xai_user_agent(),
        },
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    entries = payload.get("models") or payload.get("data") or []
    result: dict[str, dict[str, Any]] = {}
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        model_id = str(entry.get("id") or entry.get("name") or "").strip()
        if model_id:
            result[model_id] = {
                "input_modalities": entry.get("input_modalities") or [],
                "aliases": entry.get("aliases") or [],
            }
    return result


def _live_models() -> dict[str, dict[str, Any]]:
    global _LIVE_CACHE
    now = time.monotonic()
    if _LIVE_CACHE is not None and now - _LIVE_CACHE[1] < _LIVE_TTL:
        return _LIVE_CACHE[0]
    stale = _LIVE_CACHE
    try:
        live = _fetch_live_models()
    except Exception as exc:
        logger.debug("xAI live image catalog unavailable: %s", exc)
        if stale is not None and now - stale[1] < _STALE_MAX:
            return stale[0]
        live = {}
    if live:
        _LIVE_CACHE = (live, now)
    return live


def _catalog() -> dict[str, dict[str, Any]]:
    live = _live_models()
    # Keep curated models first so the stable default remains the first picker
    # row; append genuinely new live IDs afterwards.
    merged: dict[str, dict[str, Any]] = {
        model_id: dict(meta) for model_id, meta in _MODELS.items()
    }
    for model_id, live_meta in live.items():
        meta: dict[str, Any] = dict(merged.get(model_id) or {
            "display": model_id,
            "speed": "",
            "strengths": "New xAI Imagine model (live catalog)",
        })
        meta["input_modalities"] = (
            live_meta.get("input_modalities")
            or meta.get("input_modalities")
            or []
        )
        merged[model_id] = meta
    return merged


def _selected_model(caller_model: str | None = None) -> str:
    config = _load_xai_config()
    candidates = (
        caller_model,
        os.getenv("XAI_IMAGE_MODEL", "").strip(),
        config.get("model"),
        DEFAULT_MODEL,
    )
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return DEFAULT_MODEL


def _edit_model(caller_model: str | None = None) -> str:
    catalog = _catalog()
    selected = _selected_model(caller_model)
    modalities = catalog.get(selected, {}).get("input_modalities") or []
    if "image" in modalities:
        return selected
    configured = _load_xai_config().get("edit_model")
    if isinstance(configured, str) and configured.strip():
        return configured.strip()
    return os.getenv("XAI_IMAGE_EDIT_MODEL", "").strip() or DEFAULT_EDIT_MODEL


def _resolution() -> str:
    value = _load_xai_config().get("resolution")
    return value if isinstance(value, str) and value in _XAI_RESOLUTIONS else DEFAULT_RESOLUTION


def _resolve_model() -> tuple[str, dict[str, Any]]:
    """Compatibility helper returning the selected model and known metadata."""
    model_id = _selected_model()
    return model_id, dict(_MODELS.get(model_id, {}))


def _resolve_resolution() -> str:
    """Compatibility alias retained for callers and provider tests."""
    return _resolution()


def _image_field(source: str) -> dict[str, str]:
    source = source.strip()
    if source.lower().startswith(("http://", "https://", "data:")):
        return {"url": source, "type": "image_url"}
    from agent.file_safety import get_read_block_error

    blocked = get_read_block_error(source)
    if blocked:
        raise PermissionError(blocked)
    path = Path(source).expanduser()
    raw = path.read_bytes()
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(raw).decode("ascii")
    return {"url": f"data:{mime};base64,{encoded}", "type": "image_url"}


class XAIImageGenProvider(ImageGenProvider):
    @property
    def name(self) -> str:
        return "xai"

    @property
    def display_name(self) -> str:
        return "xAI (Grok)"

    def is_available(self) -> bool:
        return bool(resolve_xai_http_credentials().get("api_key"))

    def list_models(self) -> list[dict[str, Any]]:
        return [
            {
                "id": model_id,
                "display": meta.get("display", model_id),
                "speed": meta.get("speed", ""),
                "strengths": meta.get("strengths", ""),
            }
            for model_id, meta in _catalog().items()
        ]

    def default_model(self) -> str:
        return DEFAULT_MODEL

    def get_setup_schema(self) -> dict[str, Any]:
        return {
            "name": "xAI Grok Imagine (image)",
            "badge": "paid",
            "tag": "Live Grok Imagine catalog; generation and image editing",
            "env_vars": [],
            "post_setup": "xai_grok",
        }

    def capabilities(self) -> dict[str, Any]:
        return {
            "modalities": ["text", "image"],
            "operations": ["generate", "edit"],
            "max_reference_images": 3,
        }

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        *,
        image_url: str | None = None,
        reference_image_urls: list[str] | None = None,
        input_images: list[str] | None = None,
        action: str = DEFAULT_IMAGE_ACTION,
        **kwargs: Any,
    ) -> dict[str, Any]:
        prompt = str(prompt or "").strip()
        aspect = resolve_aspect_ratio(aspect_ratio)
        model_id = _selected_model(kwargs.get("model"))
        if not prompt:
            return error_response(
                error="Prompt is required and must be a non-empty string",
                error_type="invalid_argument", provider=self.name,
                model=model_id, aspect_ratio=aspect,
            )

        creds = resolve_xai_http_credentials()
        api_key = str(creds.get("api_key") or "").strip()
        provider_name = str(creds.get("provider") or "xai").strip() or "xai"
        if not api_key:
            return error_response(
                error="No xAI credentials found. Configure xAI OAuth in `clio model` or set XAI_API_KEY.",
                error_type="missing_api_key", provider=provider_name,
                model=model_id, prompt=prompt, aspect_ratio=aspect,
            )

        refs = (
            ([image_url] if image_url else [])
            + list(input_images or [])
            + list(reference_image_urls or [])
            + list(kwargs.get("reference_images") or [])
        )
        refs = [str(ref).strip() for ref in refs if str(ref).strip()]
        if action == "edit" and not refs:
            return error_response(
                error="action='edit' requires at least one input image",
                error_type="invalid_argument", provider=provider_name,
                prompt=prompt, aspect_ratio=aspect,
            )
        if len(refs) > 3:
            return error_response(
                error="xAI image editing supports at most 3 source images",
                error_type="too_many_references", provider=provider_name,
                prompt=prompt, aspect_ratio=aspect,
            )

        resolution = _resolution()
        payload: dict[str, Any]
        if refs:
            model_id = _edit_model(kwargs.get("model"))
            try:
                image_fields = [_image_field(ref) for ref in refs]
            except Exception as exc:
                return error_response(
                    error=f"Could not load source image for editing: {exc}",
                    error_type="io_error", provider=provider_name, model=model_id,
                    prompt=prompt, aspect_ratio=aspect,
                )
            payload = {"model": model_id, "prompt": prompt}
            payload["image" if len(image_fields) == 1 else "images"] = (
                image_fields[0] if len(image_fields) == 1 else image_fields
            )
            endpoint = "images/edits"
        else:
            payload = {
                "model": model_id,
                "prompt": prompt,
                "aspect_ratio": _XAI_ASPECT_RATIOS[aspect],
                "resolution": resolution,
            }
            endpoint = "images/generations"

        base_url = str(creds.get("base_url") or "https://api.x.ai/v1").strip().rstrip("/")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": clio_xai_user_agent(),
        }
        try:
            response = requests.post(
                f"{base_url}/{endpoint}", headers=headers, json=payload, timeout=120,
            )
            response.raise_for_status()
            result = response.json()
        except requests.HTTPError as exc:
            response = exc.response
            status = response.status_code if response is not None else 0
            try:
                body = response.json() if response is not None else {}
                detail = body.get("error", {}) if isinstance(body, dict) else body
                detail = detail.get("message", detail) if isinstance(detail, dict) else detail
            except Exception:
                detail = response.text[:300] if response is not None else str(exc)
            return error_response(
                error=f"xAI image generation failed ({status}): {detail}",
                error_type="api_error", provider=provider_name, model=model_id,
                prompt=prompt, aspect_ratio=aspect,
            )
        except requests.Timeout:
            return error_response(
                error="xAI image generation timed out (120s)", error_type="timeout",
                provider=provider_name, model=model_id, prompt=prompt,
                aspect_ratio=aspect,
            )
        except requests.ConnectionError as exc:
            return error_response(
                error=f"xAI connection error: {exc}", error_type="connection_error",
                provider=provider_name, model=model_id, prompt=prompt,
                aspect_ratio=aspect,
            )
        except Exception as exc:
            return error_response(
                error=f"xAI returned invalid JSON: {exc}", error_type="invalid_response",
                provider=provider_name, model=model_id, prompt=prompt,
                aspect_ratio=aspect,
            )

        data = result.get("data") if isinstance(result, dict) else None
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            return error_response(
                error="xAI returned no image data", error_type="empty_response",
                provider=provider_name, model=model_id, prompt=prompt,
                aspect_ratio=aspect,
            )
        first = data[0]
        try:
            if first.get("b64_json"):
                image = str(save_b64_image(first["b64_json"], prefix=f"xai_{model_id}"))
            elif first.get("url"):
                url = str(first["url"])
                try:
                    image = str(save_url_image(url, prefix=f"xai_{model_id}"))
                except Exception as exc:
                    logger.warning(
                        "xAI image URL could not be cached (%s); falling back to URL",
                        exc,
                    )
                    image = url
            else:
                raise ValueError("response contained neither b64_json nor URL")
        except Exception as exc:
            return error_response(
                error=f"Could not save xAI image: {exc}", error_type="io_error",
                provider=provider_name, model=model_id, prompt=prompt,
                aspect_ratio=aspect,
            )
        extra: dict[str, Any] = {"endpoint": endpoint}
        if not refs:
            extra["resolution"] = resolution
        return success_response(
            image=image, model=model_id, prompt=prompt, aspect_ratio=aspect,
            provider="xai",
            extra=extra,
        )


def register(ctx: Any) -> None:
    ctx.register_image_gen_provider(XAIImageGenProvider())
