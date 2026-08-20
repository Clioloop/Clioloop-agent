"""OpenRouter image generation over both supported API surfaces.

OpenRouter serves image-output chat models through ``/chat/completions`` and a
separate, larger image catalog through ``/images/models`` +
``/images/generations``.  The picker merges both live catalogs.  Generation
keeps the tested chat defaults on chat completions, routes curated dedicated
models to the Image API, and uses the live Image API catalog for models released
after this plugin.
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import os
import time
from pathlib import Path
from typing import Any

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

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "google/gemini-3-pro-image"
_CHAT_DEFAULTS = frozenset({DEFAULT_MODEL, "openai/gpt-5.4-image-2"})
_ASPECTS = {"landscape": "16:9", "square": "1:1", "portrait": "9:16"}
_ASPECT_PREFERENCES = {
    "landscape": ("16:9", "3:2", "4:3", "21:9", "2:1"),
    "portrait": ("9:16", "2:3", "3:4", "4:5", "1:2"),
    "square": ("1:1",),
}
_REQUEST_TIMEOUT = 300.0
_CONNECT_TIMEOUT = 20.0
_LIVE_TTL = 300.0
_STALE_MAX = 7 * 24 * 3600.0
_CATALOG_CACHE: dict[str, tuple[float, list[dict[str, Any]], list[dict[str, Any]]]] = {}

_GEMINI_RATIOS = (
    "1:1", "1:4", "1:8", "2:3", "3:2", "3:4", "4:1", "4:3",
    "4:5", "5:4", "8:1", "9:16", "16:9", "21:9",
)
_MAI_RATIOS = ("1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3", "auto")
_KREA_RATIOS = ("1:1", "4:3", "3:2", "16:9", "4:5", "2:3", "9:16")

# Curated parameter metadata is only a fallback.  ``GET /images/models`` is
# authoritative for which IDs are currently available.
_IMAGE_API_MODELS: dict[str, dict[str, Any]] = {
    "google/gemini-3.1-flash-lite-image": {
        "display": "Nano Banana 2 Lite", "ratios": _GEMINI_RATIOS,
        "resolutions": ("1K",), "max_n": 1, "max_refs": 14,
    },
    "google/gemini-3.1-flash-image": {
        "display": "Nano Banana 2", "ratios": _GEMINI_RATIOS,
        "resolutions": ("512", "1K", "2K", "4K"), "max_n": 1, "max_refs": 14,
    },
    "openai/gpt-image-2": {
        "display": "OpenAI GPT Image 2",
        "ratios": ("1:1", "3:2", "2:3", "4:3", "3:4", "16:9", "9:16", "21:9", "auto"),
        "quality": ("auto", "low", "medium", "high"),
        "background": ("auto", "opaque"), "compression": True,
        "max_n": 10, "max_refs": 16,
    },
    "openai/gpt-image-1-mini": {
        "display": "OpenAI GPT Image 1 Mini",
        "ratios": ("1:1", "3:2", "2:3", "auto"),
        "quality": ("auto", "low", "medium", "high"),
        "background": ("auto", "transparent", "opaque"), "compression": True,
        "max_n": 10, "max_refs": 16,
    },
    "microsoft/mai-image-2.5": {
        "display": "Microsoft MAI-Image-2.5", "ratios": _MAI_RATIOS,
        "max_n": 1, "max_refs": 1,
    },
    "microsoft/mai-image-2.5-pro": {
        "display": "Microsoft MAI-Image-2.5 Pro", "ratios": _MAI_RATIOS,
        "max_n": 1, "max_refs": 1,
    },
    "x-ai/grok-imagine-image-quality": {
        "display": "Grok Imagine (Image Quality)",
        "ratios": ("1:1", "3:4", "4:3", "9:16", "16:9", "2:3", "3:2", "1:2", "2:1", "auto"),
        "resolutions": ("1K", "2K"), "max_n": 1, "max_refs": 3,
    },
    "krea/krea-2-medium": {
        "display": "Krea 2 Medium", "ratios": _KREA_RATIOS,
        "resolutions": ("1K",), "seed": True, "max_n": 1, "max_refs": 1,
    },
    "krea/krea-2-medium-turbo": {
        "display": "Krea 2 Medium Turbo", "ratios": _KREA_RATIOS,
        "resolutions": ("1K",), "seed": True, "max_n": 1, "max_refs": 1,
    },
    "qwen/qwen-image-3-pro": {
        "display": "Qwen Image 3 Pro",
        "ratios": ("1:1", "1:2", "1:4", "2:1", "2:3", "3:2", "3:4", "4:1", "4:3", "4:5", "5:4", "9:16", "16:9"),
        "resolutions": ("1K", "2K"), "seed": True, "max_n": 6, "max_refs": 4,
    },
}
_UNKNOWN_META: dict[str, Any] = {"ratios": (), "max_n": 1, "max_refs": 16}


def _config() -> dict[str, Any]:
    try:
        from clio_cli.config import load_config

        cfg = load_config()
        section = cfg.get("image_gen") if isinstance(cfg, dict) else None
        return section if isinstance(section, dict) else {}
    except Exception:
        return {}


def _api_key() -> str:
    value = os.getenv("OPENROUTER_API_KEY", "").strip()
    if value:
        return value
    try:
        from clio_cli.config import get_env_value

        return str(get_env_value("OPENROUTER_API_KEY") or "").strip()
    except Exception:
        return ""


def _base_url() -> str:
    cfg = _config()
    scoped_value = cfg.get("openrouter")
    scoped: dict[str, Any] = scoped_value if isinstance(scoped_value, dict) else {}
    value = (
        os.getenv("OPENROUTER_IMAGE_BASE_URL", "").strip()
        or str(scoped.get("base_url") or "").strip()
        or DEFAULT_BASE_URL
    )
    return value.rstrip("/")


def check_requirements() -> bool:
    try:
        import requests  # noqa: F401
    except ImportError:
        return False
    return bool(_api_key())


def _image_ref(ref: str) -> str:
    ref = str(ref or "").strip()
    if ref.startswith(("http://", "https://", "data:")):
        return ref
    from agent.file_safety import get_read_block_error

    blocked = get_read_block_error(ref)
    if blocked:
        raise PermissionError(blocked)
    path = Path(ref).expanduser()
    raw = path.read_bytes()
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def _extract_chat_images(payload: dict[str, Any]) -> list[str]:
    output: list[str] = []
    choices = payload.get("choices") if isinstance(payload, dict) else None
    for choice in choices if isinstance(choices, list) else []:
        message = choice.get("message") if isinstance(choice, dict) else None
        images = message.get("images") if isinstance(message, dict) else None
        for image in images if isinstance(images, list) else []:
            image_url = image.get("image_url") if isinstance(image, dict) else None
            url = image_url.get("url") if isinstance(image_url, dict) else None
            if isinstance(url, str) and url.strip():
                output.append(url.strip())
    return output


def _fetch_catalogs(base_url: str, api_key: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (dedicated image models, chat image-output models).

    Fresh results replace the cache.  A transient failure serves the last good
    catalog for up to seven days so picker defaults do not disappear during an
    OpenRouter outage.
    """
    import requests

    cached = _CATALOG_CACHE.get(base_url)
    now = time.monotonic()
    if cached and now - cached[0] < _LIVE_TTL:
        return list(cached[1]), list(cached[2])

    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    dedicated: list[dict[str, Any]] = []
    chat: list[dict[str, Any]] = []
    try:
        response = requests.get(
            f"{base_url}/images/models", headers=headers,
            timeout=(_CONNECT_TIMEOUT, 30.0),
        )
        response.raise_for_status()
        body = response.json()
        for entry in body.get("data", []) if isinstance(body, dict) else []:
            if not isinstance(entry, dict):
                continue
            model_id = str(entry.get("id") or "").strip()
            if model_id:
                dedicated.append({
                    "id": model_id,
                    "display": _IMAGE_API_MODELS.get(model_id, {}).get(
                        "display", entry.get("name") or model_id
                    ),
                    "strengths": "OpenRouter Image API",
                    "surface": "images",
                })
    except Exception as exc:
        logger.debug("OpenRouter Image API catalog unavailable: %s", exc)

    try:
        response = requests.get(
            f"{base_url}/models", headers=headers,
            timeout=(_CONNECT_TIMEOUT, 30.0),
        )
        response.raise_for_status()
        body = response.json()
        for entry in body.get("data", []) if isinstance(body, dict) else []:
            if not isinstance(entry, dict):
                continue
            model_id = str(entry.get("id") or "").strip()
            arch_value = entry.get("architecture")
            arch: dict[str, Any] = arch_value if isinstance(arch_value, dict) else {}
            if (
                model_id
                and not model_id.startswith("openrouter/auto")
                and "image" in (arch.get("output_modalities") or [])
            ):
                chat.append({
                    "id": model_id,
                    "display": entry.get("name") or model_id,
                    "strengths": "Image output via chat completions",
                    "surface": "chat",
                })
    except Exception as exc:
        logger.debug("OpenRouter chat image catalog unavailable: %s", exc)

    if dedicated or chat:
        _CATALOG_CACHE[base_url] = (now, dedicated, chat)
        return dedicated, chat
    if cached and now - cached[0] < _STALE_MAX:
        return list(cached[1]), list(cached[2])
    return [], []


def _setting(name: str, explicit: Any = None) -> Any:
    if explicit is not None and not (isinstance(explicit, str) and not explicit.strip()):
        return explicit
    env = os.getenv(f"OPENROUTER_IMAGE_API_{name.upper()}", "").strip()
    if env:
        return env
    scoped = _config().get("openrouter")
    return scoped.get(name) if isinstance(scoped, dict) else None


def _select_surface(model: str, base_url: str, api_key: str) -> str:
    forced = str(_setting("surface") or "").strip().lower()
    if forced in {"images", "chat"}:
        return forced
    if model in _CHAT_DEFAULTS:
        return "chat"
    if model in _IMAGE_API_MODELS:
        return "images"
    dedicated, _ = _fetch_catalogs(base_url, api_key)
    return "images" if any(entry["id"] == model for entry in dedicated) else "chat"


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _build_image_payload(
    model: str,
    prompt: str,
    aspect: str,
    references: list[str],
    kwargs: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    meta = _IMAGE_API_MODELS.get(model, _UNKNOWN_META)
    payload: dict[str, Any] = {"model": model, "prompt": prompt}
    notes: list[str] = []
    ratios = tuple(meta.get("ratios") or ())
    exact = str(_setting("aspect_ratio", kwargs.get("aspect_ratio_exact")) or "").strip()
    if exact and (not ratios or exact in ratios):
        payload["aspect_ratio"] = exact
    elif ratios:
        payload["aspect_ratio"] = next(
            (candidate for candidate in _ASPECT_PREFERENCES[aspect] if candidate in ratios),
            "auto" if "auto" in ratios else ratios[0],
        )
    elif exact:
        notes.append("aspect_ratio omitted because this live model's enum is unknown")

    for field, meta_field in (
        ("resolution", "resolutions"),
        ("quality", "quality"),
        ("background", "background"),
        ("output_format", "output_format"),
    ):
        value = _setting(field, kwargs.get(field))
        if not isinstance(value, str) or not value.strip():
            continue
        value = value.strip()
        allowed = tuple(meta.get(meta_field) or ())
        if allowed and value in allowed:
            payload[field] = value
        else:
            notes.append(f"{field}={value!r} is unsupported by {model}; dropped")

    compression = _coerce_int(_setting("output_compression", kwargs.get("output_compression")))
    if compression is not None:
        if meta.get("compression"):
            payload["output_compression"] = max(0, min(100, compression))
        else:
            notes.append("output_compression is unsupported by this model; dropped")
    seed = _coerce_int(_setting("seed", kwargs.get("seed")))
    if seed is not None:
        if meta.get("seed"):
            payload["seed"] = seed
        else:
            notes.append("seed is unsupported by this model; dropped")
    count = _coerce_int(_setting("n", kwargs.get("n")))
    if count is not None:
        max_n = int(meta.get("max_n") or 1)
        payload["n"] = max(1, min(count, max_n))
        if count > max_n:
            notes.append(f"n={count} clamped to {max_n}")

    max_refs = int(meta.get("max_refs") or 0)
    usable = references[:max_refs] if max_refs else []
    if len(references) > len(usable):
        notes.append(f"reference images clamped from {len(references)} to {max_refs}")
    if usable:
        payload["input_references"] = [
            {"type": "image_url", "image_url": {"url": ref}} for ref in usable
        ]
    return payload, notes


def _save_entry(entry: dict[str, Any], prefix: str) -> str | None:
    b64 = entry.get("b64_json")
    if isinstance(b64, str) and b64.strip():
        media_type = str(entry.get("media_type") or "image/png").split(";", 1)[0]
        extension = {
            "image/png": "png", "image/jpeg": "jpg", "image/webp": "webp",
        }.get(media_type, "png")
        return str(save_b64_image(b64, prefix=prefix, extension=extension))
    url = entry.get("url")
    if isinstance(url, str) and url.strip():
        url = url.strip()
        if url.startswith("data:") and "," in url:
            return str(save_b64_image(url.split(",", 1)[1], prefix=prefix))
        try:
            return str(save_url_image(url, prefix=prefix))
        except Exception as exc:
            # Signed provider URLs can occasionally expire while they are being
            # materialised. Preserve the URL as a last-resort media reference,
            # matching the OpenAI/xAI provider contract.
            logger.warning(
                "OpenRouter image URL could not be cached (%s); falling back to URL",
                exc,
            )
            return url
    return None


class OpenRouterImageGenProvider(ImageGenProvider):
    @property
    def name(self) -> str:
        return "openrouter"

    @property
    def display_name(self) -> str:
        return "OpenRouter"

    def is_available(self) -> bool:
        return check_requirements()

    def capabilities(self) -> dict[str, Any]:
        return {
            "modalities": ["text", "image"],
            "max_reference_images": 16,
            "operations": ["generate", "edit"],
        }

    def list_models(self) -> list[dict[str, Any]]:
        dedicated, chat = _fetch_catalogs(_base_url(), _api_key())
        merged: dict[str, dict[str, Any]] = {entry["id"]: entry for entry in dedicated}
        for entry in chat:
            merged.setdefault(entry["id"], entry)
        if not merged:
            for model_id, meta in _IMAGE_API_MODELS.items():
                merged[model_id] = {
                    "id": model_id,
                    "display": meta.get("display", model_id),
                    "strengths": "OpenRouter Image API (offline catalog)",
                    "surface": "images",
                }
        # A partial catalog outage must not make the stable default disappear
        # from the picker. It is intentionally routed through chat completions.
        merged.setdefault(DEFAULT_MODEL, {
            "id": DEFAULT_MODEL,
            "display": "Gemini 3 Pro Image",
            "strengths": "Image output via chat completions",
            "surface": "chat",
        })
        priority = {DEFAULT_MODEL: 0, "openai/gpt-5.4-image-2": 1}
        return sorted(merged.values(), key=lambda item: (priority.get(item["id"], 2), item["id"]))

    def default_model(self) -> str:
        cfg = _config()
        scoped_value = cfg.get("openrouter")
        scoped: dict[str, Any] = scoped_value if isinstance(scoped_value, dict) else {}
        return (
            os.getenv("OPENROUTER_IMAGE_MODEL", "").strip()
            or str(scoped.get("model") or "").strip()
            or str(cfg.get("model") or "").strip()
            or DEFAULT_MODEL
        )

    def get_setup_schema(self) -> dict[str, Any]:
        return {
            "name": "OpenRouter (image)",
            "badge": "paid",
            "tag": "Full live Image API + chat image-output catalog",
            "env_vars": [{
                "key": "OPENROUTER_API_KEY",
                "prompt": "OpenRouter API key",
                "url": "https://openrouter.ai/keys",
            }],
        }

    def _generate_image_api(
        self,
        *,
        model: str,
        prompt: str,
        aspect: str,
        references: list[str],
        headers: dict[str, str],
        base_url: str,
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        import requests

        try:
            refs = [_image_ref(ref) for ref in references]
        except Exception as exc:
            return error_response(
                error=f"Could not load reference image: {exc}", error_type="io_error",
                provider=self.name, model=model, prompt=prompt, aspect_ratio=aspect,
            )
        payload, notes = _build_image_payload(model, prompt, aspect, refs, kwargs)
        try:
            response = requests.post(
                f"{base_url}/images/generations", headers=headers, json=payload,
                timeout=(_CONNECT_TIMEOUT, _REQUEST_TIMEOUT),
            )
            response.raise_for_status()
            body = response.json()
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
                error=f"OpenRouter Image API failed ({status}): {detail}",
                error_type="auth_error" if status in {401, 403} else "model_access" if status == 404 else "api_error",
                provider=self.name, model=model, prompt=prompt, aspect_ratio=aspect,
            )
        except requests.Timeout:
            return error_response(
                error=f"OpenRouter image generation timed out ({int(_REQUEST_TIMEOUT)}s)",
                error_type="timeout", provider=self.name, model=model,
                prompt=prompt, aspect_ratio=aspect,
            )
        except requests.RequestException as exc:
            return error_response(
                error=f"OpenRouter image request failed: {exc}", error_type="connection_error",
                provider=self.name, model=model, prompt=prompt, aspect_ratio=aspect,
            )
        except Exception as exc:
            return error_response(
                error=f"OpenRouter returned invalid JSON: {exc}", error_type="invalid_response",
                provider=self.name, model=model, prompt=prompt, aspect_ratio=aspect,
            )

        entries = body.get("data") if isinstance(body, dict) else None
        entries = [item for item in entries if isinstance(item, dict)] if isinstance(entries, list) else []
        try:
            saved = [path for path in (_save_entry(item, "openrouter_image_api") for item in entries) if path]
        except Exception as exc:
            return error_response(
                error=f"Could not save generated image: {exc}", error_type="io_error",
                provider=self.name, model=model, prompt=prompt, aspect_ratio=aspect,
            )
        if not saved:
            return error_response(
                error="OpenRouter Image API returned no image data", error_type="empty_response",
                provider=self.name, model=model, prompt=prompt, aspect_ratio=aspect,
            )
        extra: dict[str, Any] = {"endpoint": "images/generations"}
        if len(saved) > 1:
            extra["additional_images"] = saved[1:]
        if notes:
            extra["notes"] = notes
        usage = body.get("usage") if isinstance(body, dict) else None
        if isinstance(usage, dict):
            extra["usage"] = usage
        return success_response(
            image=saved[0], model=model, prompt=prompt, aspect_ratio=aspect,
            provider=self.name, extra=extra,
        )

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
        import requests

        prompt = str(prompt or "").strip()
        aspect = resolve_aspect_ratio(aspect_ratio)
        if not prompt:
            return error_response(
                error="Prompt is required and must be a non-empty string",
                error_type="invalid_argument", provider=self.name,
                aspect_ratio=aspect,
            )

        key = _api_key()
        base_url = _base_url()
        model = str(kwargs.get("model") or self.default_model()).strip()
        if not key:
            return error_response(
                error="OPENROUTER_API_KEY is not set", error_type="auth_required",
                provider=self.name, model=model, prompt=prompt, aspect_ratio=aspect,
            )
        references = (
            ([image_url] if image_url else [])
            + list(input_images or [])
            + list(reference_image_urls or [])
            + list(kwargs.get("reference_images") or [])
        )
        references = [str(ref).strip() for ref in references if str(ref).strip()]
        if action == "edit" and not references:
            return error_response(
                error="action='edit' requires at least one input image",
                error_type="invalid_argument", provider=self.name, model=model,
                prompt=prompt, aspect_ratio=aspect,
            )

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://clioloop.com",
            "X-Title": "Clio Agent",
        }
        if _select_surface(model, base_url, key) == "images":
            return self._generate_image_api(
                model=model, prompt=prompt, aspect=aspect, references=references,
                headers=headers, base_url=base_url, kwargs=kwargs,
            )

        if len(references) > 3:
            return error_response(
                error="OpenRouter chat image models accept at most 3 reference images",
                error_type="invalid_argument", provider=self.name, model=model,
                prompt=prompt, aspect_ratio=aspect,
            )
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        try:
            content.extend(
                {"type": "image_url", "image_url": {"url": _image_ref(ref)}}
                for ref in references
            )
            response = requests.post(
                f"{base_url}/chat/completions", headers=headers,
                json={
                    "model": model,
                    "modalities": ["image", "text"],
                    "messages": [{"role": "user", "content": content}],
                    "image_config": {"aspect_ratio": _ASPECTS[aspect]},
                },
                timeout=(_CONNECT_TIMEOUT, _REQUEST_TIMEOUT),
            )
            response.raise_for_status()
            images = _extract_chat_images(response.json())
            if not images:
                raise ValueError("response contained no generated images")
            saved = [
                image
                for image in (_save_entry({"url": url}, "openrouter") for url in images)
                if image
            ]
            if not saved:
                raise ValueError("response images could not be decoded")
            extra: dict[str, Any] = {
                "endpoint": "chat/completions",
                "modality": "image" if references else "text",
            }
            if len(saved) > 1:
                extra["additional_images"] = saved[1:]
            return success_response(
                image=saved[0], model=model, prompt=prompt, aspect_ratio=aspect,
                provider=self.name, extra=extra,
            )
        except requests.HTTPError as exc:
            error_response_obj = exc.response
            status = error_response_obj.status_code if error_response_obj is not None else 0
            try:
                body = error_response_obj.json() if error_response_obj is not None else {}
                error_body = body.get("error", {}) if isinstance(body, dict) else body
                detail = (
                    error_body.get("message", error_body)
                    if isinstance(error_body, dict)
                    else error_body
                )
            except Exception:
                detail = str(exc)
            return error_response(
                error=f"OpenRouter image generation failed ({status}): {detail}",
                error_type="auth_error" if status in {401, 403} else "api_error",
                provider=self.name, model=model, prompt=prompt, aspect_ratio=aspect,
            )
        except requests.Timeout:
            return error_response(
                error=f"OpenRouter image generation timed out ({int(_REQUEST_TIMEOUT)}s)",
                error_type="timeout", provider=self.name, model=model,
                prompt=prompt, aspect_ratio=aspect,
            )
        except Exception as exc:
            return error_response(
                error=f"OpenRouter image generation failed: {exc}", error_type="api_error",
                provider=self.name, model=model, prompt=prompt, aspect_ratio=aspect,
            )


def register(ctx) -> None:
    ctx.register_image_gen_provider(OpenRouterImageGenProvider())
