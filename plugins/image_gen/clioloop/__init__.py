"""Clioloop self-hosted image generation provider.

Routes ``image_generate`` calls through the Omni Loop Portal Tool Gateway to a
private image server (``POST /generate {prompt, steps}`` with ``X-API-Key``).
The customer authenticates with their managed-provider OAuth token; the portal
gates on the Pro plan, swaps in the house API key, and forwards the request to
the operator's tunneled image box. The raw token never reaches the agent.

Server-side config lives on the portal (see ``portal/src/lib/gateway.ts``,
vendor ``clioloop-image``): ``CLIOLOOP_IMAGE_UPSTREAM_URL`` + ``CLIOLOOP_IMAGE_KEY``.
"""

from __future__ import annotations

import base64
import logging
from typing import Any, Dict, List, Optional

import requests

from agent.image_gen_provider import (
    DEFAULT_ASPECT_RATIO,
    ImageGenProvider,
    error_response,
    save_b64_image,
    save_url_image,
    success_response,
)
from tools.managed_tool_gateway import (
    build_vendor_gateway_url,
    is_managed_tool_gateway_ready,
    read_managed_access_token,
)

logger = logging.getLogger(__name__)

VENDOR = "clioloop-image"
DEFAULT_MODEL = "clioloop-local"
DEFAULT_STEPS = 4
_PROVIDER = "clioloop"


def _ext_for_content_type(content_type: str) -> str:
    ct = (content_type or "").lower()
    if "jpeg" in ct or "jpg" in ct:
        return "jpg"
    if "webp" in ct:
        return "webp"
    return "png"


class ClioloopImageGenProvider(ImageGenProvider):
    """Self-hosted image generation via the managed Tool Gateway."""

    @property
    def name(self) -> str:
        return _PROVIDER

    @property
    def display_name(self) -> str:
        return "Clioloop (self-hosted)"

    def is_available(self) -> bool:
        # Available whenever the managed provider gateway is connected — the
        # actual upstream image server lives behind the portal, so there's no
        # agent-side key to check.
        try:
            return is_managed_tool_gateway_ready()
        except Exception:
            return False

    def list_models(self) -> List[Dict[str, Any]]:
        return [{"id": DEFAULT_MODEL, "name": "Clioloop self-hosted"}]

    @property
    def default_model(self) -> Optional[str]:
        return DEFAULT_MODEL

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        prompt = (prompt or "").strip()
        if not prompt:
            return error_response(error="prompt is required", error_type="invalid_request", provider=_PROVIDER)

        token = read_managed_access_token()
        if not token:
            return error_response(
                error="Connect the Omni Loop Portal (clio auth add managed) to use image generation.",
                error_type="auth_error",
                provider=_PROVIDER,
            )

        try:
            steps = int(kwargs.get("steps") or DEFAULT_STEPS)
        except (TypeError, ValueError):
            steps = DEFAULT_STEPS

        url = build_vendor_gateway_url(VENDOR).rstrip("/") + "/generate"
        try:
            resp = requests.post(
                url,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"prompt": prompt, "steps": steps},
                timeout=300,
            )
            resp.raise_for_status()
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else 0
            detail = ""
            try:
                detail = exc.response.text[:400] if exc.response is not None else ""
            except Exception:
                detail = ""
            return error_response(
                error=f"image gateway returned HTTP {status}: {detail}".strip(),
                error_type="provider_error",
                provider=_PROVIDER,
                prompt=prompt,
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            return error_response(
                error=f"could not reach the image gateway: {exc}",
                error_type="network_error",
                provider=_PROVIDER,
                prompt=prompt,
            )

        # Parse defensively — the server may return raw image bytes, or JSON
        # with a base64 payload or a URL.
        try:
            content_type = resp.headers.get("content-type", "")
            if content_type.startswith("image/"):
                path = save_b64_image(
                    base64.b64encode(resp.content).decode("ascii"),
                    prefix="clioloop",
                    extension=_ext_for_content_type(content_type),
                )
            else:
                data = resp.json()
                b64 = data.get("image_base64") or data.get("b64_json") or data.get("image")
                img_url = data.get("image_url") or data.get("url")
                if isinstance(b64, str) and b64:
                    if b64.startswith("data:"):
                        b64 = b64.split(",", 1)[-1]
                    path = save_b64_image(b64, prefix="clioloop")
                elif isinstance(img_url, str) and img_url:
                    path = save_url_image(img_url, prefix="clioloop")
                else:
                    return error_response(
                        error="image server returned no recognizable image data",
                        error_type="provider_error",
                        provider=_PROVIDER,
                        prompt=prompt,
                    )
        except Exception as exc:
            return error_response(
                error=f"could not decode the image response: {exc}",
                error_type="provider_error",
                provider=_PROVIDER,
                prompt=prompt,
            )

        return success_response(
            image=str(path),
            model=DEFAULT_MODEL,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            provider=_PROVIDER,
        )


def register(ctx) -> None:
    """Plugin entrypoint — register the provider with the agent."""
    ctx.register_image_gen_provider(ClioloopImageGenProvider())
