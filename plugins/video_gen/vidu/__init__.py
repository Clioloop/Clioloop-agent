"""Vidu video generation backend.

Surface: text-to-video and image-to-video through Vidu's async API. The
managed Omni Loop Portal path uses the same provider with ``use_gateway``
enabled, so subscribers are metered by the portal before the Vidu task is
created.
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from agent.video_gen_provider import (
    VideoGenProvider,
    error_response,
    success_response,
)

logger = logging.getLogger(__name__)


DEFAULT_VIDU_BASE_URL = "https://api.vidu.com/ent/v2"
DEFAULT_MODEL = "viduq3-turbo"
DEFAULT_DURATION = 5
MAX_DURATION = 10
DEFAULT_ASPECT_RATIO = "16:9"
DEFAULT_RESOLUTION = "540p"
DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_POLL_INTERVAL_SECONDS = 5

VALID_ASPECT_RATIOS = {"16:9", "9:16", "3:4", "4:3", "1:1"}
VALID_RESOLUTIONS = {"540p", "720p", "1080p"}


def _load_video_gen_section() -> Dict[str, Any]:
    try:
        from clio_cli.config import load_config

        cfg = load_config()
        section = cfg.get("video_gen") if isinstance(cfg, dict) else None
        return section if isinstance(section, dict) else {}
    except Exception as exc:
        logger.debug("Could not load video_gen config: %s", exc)
        return {}


def _env_or_config(key: str) -> str:
    value = os.getenv(key)
    if value is None:
        try:
            from clio_cli.config import get_env_value

            value = get_env_value(key)
        except Exception:
            value = None
    return (value or "").strip()


def vidu_key_is_configured() -> bool:
    return bool(_env_or_config("VIDU_API_KEY"))


def _resolve_model(explicit: Optional[str]) -> str:
    candidates: List[Optional[str]] = [explicit, os.getenv("VIDU_VIDEO_MODEL")]
    cfg = _load_video_gen_section()
    vidu_cfg = cfg.get("vidu") if isinstance(cfg.get("vidu"), dict) else {}
    if isinstance(vidu_cfg, dict):
        candidates.append(vidu_cfg.get("model"))
    top = cfg.get("model")
    if isinstance(top, str):
        candidates.append(top)

    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return DEFAULT_MODEL


def _resolve_timeout() -> Tuple[int, int]:
    cfg = _load_video_gen_section()
    timeout = cfg.get("timeout_seconds")
    poll = cfg.get("poll_interval_seconds")
    try:
        timeout_seconds = int(timeout)
    except (TypeError, ValueError):
        timeout_seconds = DEFAULT_TIMEOUT_SECONDS
    try:
        poll_interval = int(poll)
    except (TypeError, ValueError):
        poll_interval = DEFAULT_POLL_INTERVAL_SECONDS
    return max(30, timeout_seconds), max(1, poll_interval)


def _clamp_duration(duration: Optional[int]) -> int:
    if duration is None:
        return DEFAULT_DURATION
    try:
        value = int(duration)
    except (TypeError, ValueError):
        value = DEFAULT_DURATION
    return max(1, min(MAX_DURATION, value))


def _normalize_aspect_ratio(aspect_ratio: str) -> str:
    value = (aspect_ratio or DEFAULT_ASPECT_RATIO).strip()
    return value if value in VALID_ASPECT_RATIOS else DEFAULT_ASPECT_RATIO


def _normalize_resolution(resolution: str) -> str:
    value = (resolution or DEFAULT_RESOLUTION).strip().lower()
    return value if value in VALID_RESOLUTIONS else DEFAULT_RESOLUTION


def _image_ref_to_vidu_image(value: str) -> str:
    ref = (value or "").strip()
    if not ref:
        return ""
    lower = ref.lower()
    if lower.startswith(("http://", "https://", "data:image/")):
        return ref

    path = Path(ref).expanduser()
    if not path.is_file():
        return ref

    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if not mime.startswith("image/"):
        return ref

    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _resolve_managed_vidu_gateway():
    from tools.tool_backend_helpers import force_gateway, prefers_gateway

    if (
        vidu_key_is_configured()
        and not prefers_gateway("video_gen")
        and not force_gateway("vidu")
    ):
        return None
    from tools.managed_tool_gateway import resolve_managed_tool_gateway

    return resolve_managed_tool_gateway("vidu")


def _resolve_vidu_client_config() -> Tuple[str, Dict[str, str], bool]:
    managed_gateway = _resolve_managed_vidu_gateway()
    if managed_gateway is not None:
        return (
            managed_gateway.gateway_origin.rstrip("/"),
            {
                "Authorization": f"Bearer {managed_gateway.managed_user_token}",
                "Content-Type": "application/json",
            },
            True,
        )

    api_key = _env_or_config("VIDU_API_KEY")
    base_url = (_env_or_config("VIDU_BASE_URL") or DEFAULT_VIDU_BASE_URL).rstrip("/")
    if not api_key:
        return "", {}, False
    return (
        base_url,
        {"Authorization": f"Token {api_key}", "Content-Type": "application/json"},
        False,
    )


def _is_available() -> bool:
    return vidu_key_is_configured() or _resolve_managed_vidu_gateway() is not None


def _build_payload(
    *,
    prompt: str,
    model: str,
    image_url: Optional[str],
    duration: Optional[int],
    aspect_ratio: str,
    resolution: str,
    audio: Optional[bool],
    seed: Optional[int],
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": model,
        "duration": _clamp_duration(duration),
        "resolution": _normalize_resolution(resolution),
        "audio": True if audio is None else bool(audio),
        "off_peak": False,
    }
    if prompt:
        payload["prompt"] = prompt
    if seed is not None:
        payload["seed"] = int(seed)
    if image_url:
        payload["images"] = [_image_ref_to_vidu_image(image_url)]
    else:
        payload["aspect_ratio"] = _normalize_aspect_ratio(aspect_ratio)
    return payload


def _submit_task(
    client: httpx.Client,
    base_url: str,
    headers: Dict[str, str],
    endpoint: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    response = client.post(
        f"{base_url}/{endpoint}",
        headers=headers,
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict):
        raise RuntimeError("Vidu returned a non-object task response")
    if not body.get("task_id"):
        raise RuntimeError("Vidu task response did not include task_id")
    return body


def _poll_task(
    client: httpx.Client,
    base_url: str,
    headers: Dict[str, str],
    task_id: str,
    *,
    timeout_seconds: int,
    poll_interval: int,
) -> Dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_body: Dict[str, Any] = {"state": "created"}
    while time.monotonic() < deadline:
        response = client.get(
            f"{base_url}/tasks/{task_id}/creations",
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        body = response.json()
        if isinstance(body, dict):
            last_body = body
        state = str(last_body.get("state") or "").lower()
        if state in {"success", "failed"}:
            return last_body
        time.sleep(poll_interval)
    return {"state": "timeout", "last": last_body}


class ViduVideoGenProvider(VideoGenProvider):
    """Vidu Q3 Turbo backend for text-to-video and image-to-video."""

    @property
    def name(self) -> str:
        return "vidu"

    @property
    def display_name(self) -> str:
        return "Vidu"

    def is_available(self) -> bool:
        try:
            return _is_available()
        except Exception:
            return False

    def list_models(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": DEFAULT_MODEL,
                "display": "Vidu Q3 Turbo",
                "speed": "~60-300s",
                "strengths": "Cost-effective text-to-video and image-to-video with native audio.",
                "price": "metered by duration/resolution",
                "tier": "cheap",
                "modalities": ["text", "image"],
            },
        ]

    def default_model(self) -> Optional[str]:
        return DEFAULT_MODEL

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "Vidu",
            "badge": "paid",
            "tag": "Q3 Turbo - text-to-video and image-to-video with native audio",
            "env_vars": [
                {
                    "key": "VIDU_API_KEY",
                    "prompt": "Vidu API key",
                    "url": "https://platform.vidu.com/",
                },
            ],
        }

    def capabilities(self) -> Dict[str, Any]:
        return {
            "modalities": ["text", "image"],
            "aspect_ratios": sorted(VALID_ASPECT_RATIOS),
            "resolutions": sorted(VALID_RESOLUTIONS),
            "max_duration": MAX_DURATION,
            "min_duration": 1,
            "supports_audio": True,
            "supports_negative_prompt": False,
            "max_reference_images": 0,
        }

    def generate(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        image_url: Optional[str] = None,
        reference_image_urls: Optional[List[str]] = None,
        duration: Optional[int] = None,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        resolution: str = DEFAULT_RESOLUTION,
        negative_prompt: Optional[str] = None,
        audio: Optional[bool] = None,
        seed: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        prompt = (prompt or "").strip()
        if not prompt:
            return error_response(
                error="prompt is required for Vidu video generation",
                error_type="missing_prompt",
                provider="vidu",
                prompt=prompt,
            )
        if reference_image_urls:
            return error_response(
                error="Vidu Q3 Turbo provider supports image_url, not reference_image_urls.",
                error_type="reference_images_unsupported",
                provider="vidu",
                prompt=prompt,
            )

        base_url, headers, managed = _resolve_vidu_client_config()
        if not base_url:
            return error_response(
                error=(
                    "No Vidu backend available. Either set VIDU_API_KEY "
                    "or sign in to the Omni Loop Portal Subscription for managed gateway access."
                ),
                error_type="auth_required",
                provider="vidu",
                prompt=prompt,
            )

        model_id = _resolve_model(model)
        image_url_norm = (image_url or "").strip() or None
        endpoint = "img2video" if image_url_norm else "text2video"
        modality = "image" if image_url_norm else "text"
        payload = _build_payload(
            prompt=prompt,
            model=model_id,
            image_url=image_url_norm,
            duration=duration,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            audio=audio,
            seed=seed,
        )
        timeout_seconds, poll_interval = _resolve_timeout()

        try:
            with httpx.Client() as client:
                task = _submit_task(client, base_url, headers, endpoint, payload)
                task_id = str(task["task_id"])
                result = _poll_task(
                    client,
                    base_url,
                    headers,
                    task_id,
                    timeout_seconds=timeout_seconds,
                    poll_interval=poll_interval,
                )
        except Exception as exc:
            logger.warning("Vidu video gen failed: %s", exc, exc_info=True)
            return error_response(
                error=f"Vidu video generation failed: {exc}",
                error_type="api_error",
                provider="vidu",
                model=model_id,
                prompt=prompt,
                aspect_ratio=payload.get("aspect_ratio", ""),
            )

        state = str(result.get("state") or "").lower()
        if state == "timeout":
            return error_response(
                error=f"Timed out waiting for Vidu generation after {timeout_seconds}s",
                error_type="timeout",
                provider="vidu",
                model=model_id,
                prompt=prompt,
                aspect_ratio=payload.get("aspect_ratio", ""),
            )
        if state == "failed":
            return error_response(
                error=f"Vidu video generation failed: {result.get('err_code') or 'unknown error'}",
                error_type="api_error",
                provider="vidu",
                model=model_id,
                prompt=prompt,
                aspect_ratio=payload.get("aspect_ratio", ""),
            )

        creations = result.get("creations")
        video_url = ""
        cover_url = ""
        if isinstance(creations, list) and creations:
            first = creations[0]
            if isinstance(first, dict):
                video_url = str(first.get("url") or "")
                cover_url = str(first.get("cover_url") or "")
        if not video_url:
            return error_response(
                error="Vidu generation completed without a video URL",
                error_type="empty_response",
                provider="vidu",
                model=model_id,
                prompt=prompt,
                aspect_ratio=payload.get("aspect_ratio", ""),
            )

        return success_response(
            video=video_url,
            model=model_id,
            prompt=prompt,
            modality=modality,
            aspect_ratio=str(payload.get("aspect_ratio") or ""),
            duration=int(payload["duration"]),
            provider="vidu",
            extra={
                "task_id": task_id,
                "cover_url": cover_url,
                "resolution": payload["resolution"],
                "audio": payload["audio"],
                "managed_gateway": managed,
            },
        )


def register(ctx) -> None:
    ctx.register_video_gen_provider(ViduVideoGenProvider())
