"""OpenAI image generation backend — ChatGPT/Codex OAuth variant.

Identical model catalog and tier semantics to the ``openai`` image-gen plugin
(``gpt-image-2`` at low/medium/high quality), but routes the request through
the Codex Responses API ``image_generation`` tool instead of the
``images.generate`` REST endpoint. This lets users who are already
authenticated with Codex/ChatGPT generate images without configuring a
separate ``OPENAI_API_KEY``.

Selection precedence for the tier (first hit wins):

1. ``OPENAI_IMAGE_MODEL`` env var (escape hatch for scripts / tests)
2. ``image_gen.openai-codex.model`` in ``config.yaml``
3. ``image_gen.model`` in ``config.yaml`` (when it's one of our tier IDs)
4. :data:`DEFAULT_MODEL` — ``gpt-image-2-medium``

Output is saved as PNG under ``$CLIO_HOME/cache/images/``.
"""

from __future__ import annotations

import base64
import binascii
import io
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlsplit

from agent.image_gen_provider import (
    DEFAULT_ASPECT_RATIO,
    DEFAULT_IMAGE_ACTION,
    MAX_INPUT_IMAGES,
    VALID_IMAGE_ACTIONS,
    ImageGenProvider,
    error_response,
    resolve_aspect_ratio,
    save_b64_image,
    success_response,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Model catalog — mirrors the ``openai`` plugin so the picker UX is identical.
# ---------------------------------------------------------------------------

API_MODEL = "gpt-image-2"

_MODELS: Dict[str, Dict[str, Any]] = {
    "gpt-image-2-low": {
        "display": "GPT Image 2 (Low)",
        "speed": "~15s",
        "strengths": "Fast iteration, lowest cost",
        "quality": "low",
    },
    "gpt-image-2-medium": {
        "display": "GPT Image 2 (Medium)",
        "speed": "~40s",
        "strengths": "Balanced — default",
        "quality": "medium",
    },
    "gpt-image-2-high": {
        "display": "GPT Image 2 (High)",
        "speed": "~2min",
        "strengths": "Highest fidelity, strongest prompt adherence",
        "quality": "high",
    },
}

DEFAULT_MODEL = "gpt-image-2-medium"

_SIZES = {
    "landscape": "1536x1024",
    "square": "1024x1024",
    "portrait": "1024x1536",
}

# Codex Responses surface used for the request. The chat model itself is only
# the host that calls the ``image_generation`` tool; the actual image work is
# done by ``API_MODEL``.
_CODEX_CHAT_MODEL = "gpt-5.4"
_CODEX_BASE_URL = "https://chatgpt.com/backend-api/codex"
_CODEX_INSTRUCTIONS = (
    "You are an assistant that must fulfill image generation and editing requests by "
    "using the image_generation tool when provided. For edits, preserve every subject, "
    "identity, face, wardrobe, and object the user asks to keep unchanged."
)
_MAX_INPUT_IMAGE_BYTES = 10 * 1024 * 1024
_SUPPORTED_INPUT_FORMATS = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "WEBP": "image/webp",
    "GIF": "image/gif",
}


# ---------------------------------------------------------------------------
# Config + auth helpers
# ---------------------------------------------------------------------------


def _load_image_gen_config() -> Dict[str, Any]:
    """Read ``image_gen`` from config.yaml (returns {} on any failure)."""
    try:
        from clio_cli.config import load_config

        cfg = load_config()
        section = cfg.get("image_gen") if isinstance(cfg, dict) else None
        return section if isinstance(section, dict) else {}
    except Exception as exc:
        logger.debug("Could not load image_gen config: %s", exc)
        return {}


def _resolve_model() -> Tuple[str, Dict[str, Any]]:
    """Decide which tier to use and return ``(model_id, meta)``."""
    import os

    env_override = os.environ.get("OPENAI_IMAGE_MODEL")
    if env_override and env_override in _MODELS:
        return env_override, _MODELS[env_override]

    cfg = _load_image_gen_config()
    sub = cfg.get("openai-codex") if isinstance(cfg.get("openai-codex"), dict) else {}
    candidate: Optional[str] = None
    if isinstance(sub, dict):
        value = sub.get("model")
        if isinstance(value, str) and value in _MODELS:
            candidate = value
    if candidate is None:
        top = cfg.get("model")
        if isinstance(top, str) and top in _MODELS:
            candidate = top

    if candidate is not None:
        return candidate, _MODELS[candidate]

    return DEFAULT_MODEL, _MODELS[DEFAULT_MODEL]


def _read_codex_access_token() -> Optional[str]:
    """Return a usable Codex OAuth token, or None.

    Delegates to the canonical reader in ``agent.auxiliary_client`` so token
    expiry, credential pool selection, and JWT decoding stay in one place.
    """
    try:
        from agent.auxiliary_client import _read_codex_access_token as _reader

        token = _reader()
        if isinstance(token, str) and token.strip():
            return token.strip()
        return None
    except Exception as exc:
        logger.debug("Could not resolve Codex access token: %s", exc)
        return None


def _validate_image_bytes(raw: bytes, *, declared_mime: Optional[str] = None) -> str:
    """Validate supported raster bytes and return the canonical MIME type."""
    if not raw:
        raise ValueError("input image is empty")
    if len(raw) > _MAX_INPUT_IMAGE_BYTES:
        raise ValueError(
            f"input image exceeds the {_MAX_INPUT_IMAGE_BYTES // (1024 * 1024)} MB limit"
        )
    try:
        from PIL import Image

        with Image.open(io.BytesIO(raw)) as image:
            image_format = str(image.format or "").upper()
            if image_format == "GIF" and int(getattr(image, "n_frames", 1)) > 1:
                raise ValueError("animated GIF input images are not supported")
            image.verify()
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"input is not a valid supported image: {exc}") from exc
    mime = _SUPPORTED_INPUT_FORMATS.get(image_format)
    if not mime:
        raise ValueError(
            "input image format is unsupported; use PNG, JPEG, WebP, or a non-animated GIF"
        )
    if declared_mime:
        normalized = declared_mime.lower().replace("image/jpg", "image/jpeg")
        if normalized != mime:
            raise ValueError(
                f"input image MIME type {declared_mime!r} does not match its {image_format} bytes"
            )
    return mime


def _input_image_reference(reference: str) -> str:
    """Convert one local/URL/data reference to a Responses ``image_url`` value."""
    ref = str(reference or "").strip()
    if not ref:
        raise ValueError("input image reference must be a non-empty string")

    parsed = urlsplit(ref)
    scheme = parsed.scheme.lower()
    if scheme in {"http", "https"}:
        if not parsed.hostname:
            raise ValueError("input image URL has no hostname")
        if parsed.username or parsed.password:
            raise ValueError("input image URLs containing credentials are not supported")
        return ref

    if scheme == "data":
        header, separator, payload = ref.partition(",")
        if not separator or not header.lower().startswith("data:image/") or ";base64" not in header.lower():
            raise ValueError("input data URL must be base64-encoded image data")
        declared_mime = header[5:].split(";", 1)[0].lower()
        try:
            raw = base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("input image data URL contains invalid base64") from exc
        mime = _validate_image_bytes(raw, declared_mime=declared_mime)
        return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"

    if scheme == "file":
        if parsed.netloc not in {"", "localhost"}:
            raise ValueError("remote file:// input image references are not supported")
        path = Path(unquote(parsed.path)).expanduser().resolve()
    elif scheme:
        raise ValueError(f"unsupported input image URL scheme: {scheme}")
    else:
        path = Path(ref).expanduser().resolve()

    if not path.is_file():
        raise ValueError("local input image does not exist or is not a regular file")
    if path.stat().st_size > _MAX_INPUT_IMAGE_BYTES:
        raise ValueError(
            f"input image exceeds the {_MAX_INPUT_IMAGE_BYTES // (1024 * 1024)} MB limit"
        )
    raw = path.read_bytes()
    mime = _validate_image_bytes(raw)
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def _build_responses_payload(
    *,
    prompt: str,
    size: str,
    quality: str,
    input_image_urls: Optional[List[str]] = None,
    action: str = DEFAULT_IMAGE_ACTION,
) -> Dict[str, Any]:
    """Build the Codex Responses request body for image generation/editing."""
    content: List[Dict[str, Any]] = [{"type": "input_text", "text": prompt}]
    content.extend(
        {"type": "input_image", "image_url": image_url, "detail": "auto"}
        for image_url in (input_image_urls or [])
    )
    tool: Dict[str, Any] = {
        "type": "image_generation",
        "model": API_MODEL,
        "size": size,
        "quality": quality,
        "output_format": "png",
        "background": "opaque",
        "partial_images": 1,
        "action": action,
    }
    return {
        "model": _CODEX_CHAT_MODEL,
        "store": False,
        "instructions": _CODEX_INSTRUCTIONS,
        "input": [{
            "type": "message",
            "role": "user",
            "content": content,
        }],
        "tools": [tool],
        "tool_choice": {
            "type": "allowed_tools",
            "mode": "required",
            "tools": [{"type": "image_generation"}],
        },
        "stream": True,
    }


def _extract_image_b64(value: Any) -> Optional[str]:
    """Return the newest image b64 embedded in a Responses event payload."""
    found: Optional[str] = None
    if isinstance(value, dict):
        if value.get("type") == "image_generation_call":
            result = value.get("result")
            if isinstance(result, str) and result:
                found = result
        partial = value.get("partial_image_b64")
        if isinstance(partial, str) and partial:
            found = partial
        for child in value.values():
            nested = _extract_image_b64(child)
            if nested:
                found = nested
    elif isinstance(value, list):
        for child in value:
            nested = _extract_image_b64(child)
            if nested:
                found = nested
    return found


def _iter_sse_json(response: Any):
    """Yield JSON payloads from an SSE response without OpenAI SDK parsing.

    The ChatGPT/Codex backend can emit image-generation events newer than the
    pinned Python SDK understands. Parsing raw SSE keeps this provider tolerant
    of those event-shape changes.
    """
    event_name: Optional[str] = None
    data_lines: List[str] = []

    def flush():
        nonlocal event_name, data_lines
        if not data_lines:
            event_name = None
            return None
        raw = "\n".join(data_lines).strip()
        event = event_name
        event_name = None
        data_lines = []
        if not raw or raw == "[DONE]":
            return None
        payload = json.loads(raw)
        if isinstance(payload, dict) and event and "type" not in payload:
            payload["type"] = event
        return payload

    for line in response.iter_lines():
        if isinstance(line, bytes):
            line = line.decode("utf-8", errors="replace")
        line = str(line)
        if line == "":
            payload = flush()
            if payload is not None:
                yield payload
            continue
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event_name = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:"):].lstrip())

    payload = flush()
    if payload is not None:
        yield payload


def _collect_image_b64(
    token: str,
    *,
    prompt: str,
    size: str,
    quality: str,
    input_image_urls: Optional[List[str]] = None,
    action: str = DEFAULT_IMAGE_ACTION,
) -> Optional[str]:
    """Stream a Codex Responses image_generation call and return the b64 image."""
    import httpx
    from agent.auxiliary_client import _codex_cloudflare_headers

    headers = _codex_cloudflare_headers(token)
    headers.update({
        "Accept": "text/event-stream",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    payload = _build_responses_payload(
        prompt=prompt,
        size=size,
        quality=quality,
        input_image_urls=input_image_urls,
        action=action,
    )
    timeout = httpx.Timeout(300.0, connect=30.0, read=300.0, write=30.0, pool=30.0)

    image_b64: Optional[str] = None
    with httpx.Client(timeout=timeout, headers=headers) as http:
        with http.stream("POST", f"{_CODEX_BASE_URL}/responses", json=payload) as response:
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                exc.response.read()
                body = exc.response.text[:500]
                raise RuntimeError(
                    f"Codex Responses API returned HTTP {exc.response.status_code}: {body}"
                ) from exc
            for event in _iter_sse_json(response):
                found = _extract_image_b64(event)
                if found:
                    image_b64 = found

    return image_b64


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class OpenAICodexImageGenProvider(ImageGenProvider):
    """gpt-image-2 routed through ChatGPT/Codex OAuth instead of an API key."""

    @property
    def name(self) -> str:
        return "openai-codex"

    @property
    def display_name(self) -> str:
        return "OpenAI (Codex auth)"

    def is_available(self) -> bool:
        if not _read_codex_access_token():
            return False
        try:
            import httpx  # noqa: F401
        except ImportError:
            return False
        return True

    def capabilities(self) -> Dict[str, Any]:
        return {
            "modalities": ["text", "image"],
            "operations": ["generate", "edit"],
            "max_reference_images": MAX_INPUT_IMAGES,
        }

    def list_models(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": model_id,
                "display": meta["display"],
                "speed": meta["speed"],
                "strengths": meta["strengths"],
                "price": "varies",
            }
            for model_id, meta in _MODELS.items()
        ]

    def default_model(self) -> Optional[str]:
        return DEFAULT_MODEL

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "OpenAI (Codex auth)",
            "badge": "free",
            "tag": "gpt-image-2 generation + multi-reference editing via ChatGPT/Codex OAuth",
            "env_vars": [],
            "post_setup_hint": (
                "Sign in with `clio auth codex` (or `clio setup` → Codex) "
                "if you haven't already. No API key needed."
            ),
        }

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        prompt = (prompt or "").strip()
        aspect = resolve_aspect_ratio(aspect_ratio)

        if not prompt:
            return error_response(
                error="Prompt is required and must be a non-empty string",
                error_type="invalid_argument",
                provider="openai-codex",
                aspect_ratio=aspect,
            )

        raw_images = kwargs.get("input_images")
        if raw_images is None:
            input_images: List[str] = []
        elif not isinstance(raw_images, list):
            return error_response(
                error="input_images must be an array of image paths or URLs",
                error_type="invalid_argument",
                provider="openai-codex",
                prompt=prompt,
                aspect_ratio=aspect,
            )
        else:
            input_images = list(raw_images)
        if len(input_images) > MAX_INPUT_IMAGES:
            return error_response(
                error=f"input_images accepts at most {MAX_INPUT_IMAGES} images",
                error_type="invalid_argument",
                provider="openai-codex",
                prompt=prompt,
                aspect_ratio=aspect,
            )
        if any(not isinstance(value, str) or not value.strip() for value in input_images):
            return error_response(
                error="every input_images item must be a non-empty string",
                error_type="invalid_argument",
                provider="openai-codex",
                prompt=prompt,
                aspect_ratio=aspect,
            )

        action = kwargs.get("action", DEFAULT_IMAGE_ACTION)
        if not isinstance(action, str) or action.strip().lower() not in VALID_IMAGE_ACTIONS:
            return error_response(
                error=f"action must be one of: {', '.join(VALID_IMAGE_ACTIONS)}",
                error_type="invalid_argument",
                provider="openai-codex",
                prompt=prompt,
                aspect_ratio=aspect,
            )
        action = action.strip().lower()
        if action == "edit" and not input_images:
            return error_response(
                error="action='edit' requires at least one input image",
                error_type="invalid_argument",
                provider="openai-codex",
                prompt=prompt,
                aspect_ratio=aspect,
            )

        try:
            input_image_urls = [_input_image_reference(value) for value in input_images]
        except ValueError as exc:
            return error_response(
                error=f"Invalid input image: {exc}",
                error_type="invalid_argument",
                provider="openai-codex",
                prompt=prompt,
                aspect_ratio=aspect,
            )

        if not _read_codex_access_token():
            return error_response(
                error=(
                    "No Codex/ChatGPT OAuth credentials available. Run "
                    "`clio auth codex` (or `clio setup` → Codex) to sign in."
                ),
                error_type="auth_required",
                provider="openai-codex",
                aspect_ratio=aspect,
            )

        try:
            import httpx  # noqa: F401
        except ImportError:
            return error_response(
                error="httpx Python package not installed (pip install httpx)",
                error_type="missing_dependency",
                provider="openai-codex",
                aspect_ratio=aspect,
            )

        tier_id, meta = _resolve_model()
        size = _SIZES.get(aspect, _SIZES["square"])

        token = _read_codex_access_token()
        if not token:
            return error_response(
                error=(
                    "No Codex/ChatGPT OAuth credentials available. Run "
                    "`clio auth codex` (or `clio setup` → Codex) to sign in."
                ),
                error_type="auth_required",
                provider="openai-codex",
                model=tier_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        try:
            b64 = _collect_image_b64(
                token,
                prompt=prompt,
                size=size,
                quality=meta["quality"],
                input_image_urls=input_image_urls,
                action=action,
            )
        except Exception as exc:
            logger.debug("Codex image generation failed", exc_info=True)
            return error_response(
                error=f"OpenAI image generation via Codex auth failed: {exc}",
                error_type="api_error",
                provider="openai-codex",
                model=tier_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        if not b64:
            return error_response(
                error="Codex response contained no image_generation_call result",
                error_type="empty_response",
                provider="openai-codex",
                model=tier_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        try:
            saved_path = save_b64_image(b64, prefix=f"openai_codex_{tier_id}")
        except Exception as exc:
            return error_response(
                error=f"Could not save image to cache: {exc}",
                error_type="io_error",
                provider="openai-codex",
                model=tier_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        return success_response(
            image=str(saved_path),
            model=tier_id,
            prompt=prompt,
            aspect_ratio=aspect,
            provider="openai-codex",
            extra={
                "size": size,
                "quality": meta["quality"],
                "action": action,
                "input_image_count": len(input_image_urls),
            },
        )


# ---------------------------------------------------------------------------
# Plugin entry point
# ---------------------------------------------------------------------------


def register(ctx) -> None:
    """Plugin entry point — register the Codex-backed image-gen provider."""
    ctx.register_image_gen_provider(OpenAICodexImageGenProvider())
