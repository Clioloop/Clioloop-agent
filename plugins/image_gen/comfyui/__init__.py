"""ComfyUI local image generation backend.

Exposes a local ComfyUI instance (https://github.com/comfyanonymous/ComfyUI)
as an :class:`ImageGenProvider` implementation. ComfyUI is a node-based
Stable Diffusion pipeline that runs entirely on your own GPU — no API
keys, no per-image cost, no cloud dependency.

The provider communicates with the ComfyUI HTTP API:
  - POST /prompt       — queue a workflow
  - GET  /history/{id} — poll for completion
  - GET  /view         — retrieve the generated image

This plugin ships a built-in txt2img workflow template that maps the
Clio ``prompt`` + ``aspect_ratio`` parameters to ComfyUI's KSampler node.
Advanced users can override the workflow via the ``COMFYUI_WORKFLOW_JSON``
env var or the ``image_gen.comfyui.workflow_path`` config key (a path to
a JSON file exported from ComfyUI's UI).

Requirements:
  - A running ComfyUI server (default: http://127.0.0.1:8188)
  - At least one checkpoint model in ComfyUI's models/checkpoints/ directory
  - Set ``COMFYUI_URL`` to override the default server address
  - Set ``COMFYUI_CHECKPOINT`` to override which checkpoint model to use
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agent.image_gen_provider import (
    DEFAULT_ASPECT_RATIO,
    ImageGenProvider,
    error_response,
    resolve_aspect_ratio,
    save_url_image,
    success_response,
)

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
#  Configuration
# --------------------------------------------------------------------------- #

DEFAULT_SERVER_URL = "http://127.0.0.1:8188"
DEFAULT_CHECKPOINT = ""  # auto-detect if empty
DEFAULT_MODEL_ID = "comfyui-txt2img"

# Polling configuration
_POLL_INTERVAL = 1.0     # seconds between status checks
_POLL_TIMEOUT = 120      # max seconds to wait for a generation

# Aspect ratio → pixel dimensions (width × height).  We use 1024 as the
# base resolution, matching SDXL's native training resolution.  SD 1.5
# checkpoints will still work (ComfyUI auto-scales), though quality may
# be lower at non-native resolutions.
_DIMENSIONS: Dict[str, Tuple[int, int]] = {
    "landscape": (1024, 768),   # 4:3
    "square": (1024, 1024),     # 1:1
    "portrait": (768, 1024),     # 3:4
}


# --------------------------------------------------------------------------- #
#  Built-in txt2img workflow template
# --------------------------------------------------------------------------- #
# This is a minimal ComfyUI API-format workflow with 4 nodes:
#   1. Checkpoint loader (simple)
#   2. CLIP text encode (positive)
#   3. CLIP text encode (negative)
#   4. Empty latent image
#   5. KSampler
#   6. VAE decode
#   7. Save image
#
# The node IDs and links follow ComfyUI's standard API format.  We inject
# the prompt, dimensions, and seed at runtime.

def _build_txt2img_workflow(
    prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    checkpoint: str,
    seed: int,
    steps: int = 20,
    cfg: float = 7.0,
) -> Dict[str, Any]:
    """Build a minimal ComfyUI txt2img workflow in API JSON format."""
    return {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "euler_ancestral",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": checkpoint,
            },
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1,
            },
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": prompt,
                "clip": ["4", 1],
            },
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative_prompt,
                "clip": ["4", 1],
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["3", 0],
                "vae": ["4", 2],
            },
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["8", 0],
                "filename_prefix": "clio_comfyui",
            },
        },
    }


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #

def _get_server_url() -> str:
    """Resolve the ComfyUI server URL from env or config."""
    env_url = os.environ.get("COMFYUI_URL")
    if env_url:
        return env_url.rstrip("/")
    try:
        from clio_cli.config import load_config
        cfg = load_config() or {}
        section = cfg.get("image_gen", {})
        if isinstance(section, dict):
            comfyui_cfg = section.get("comfyui", {})
            if isinstance(comfyui_cfg, dict):
                url = comfyui_cfg.get("url")
                if url:
                    return str(url).rstrip("/")
    except Exception:
        pass
    return DEFAULT_SERVER_URL


def _get_checkpoint() -> str:
    """Resolve which checkpoint model to use."""
    env_ckpt = os.environ.get("COMFYUI_CHECKPOINT")
    if env_ckpt:
        return env_ckpt
    try:
        from clio_cli.config import load_config
        cfg = load_config() or {}
        section = cfg.get("image_gen", {})
        if isinstance(section, dict):
            comfyui_cfg = section.get("comfyui", {})
            if isinstance(comfyui_cfg, dict):
                ckpt = comfyui_cfg.get("checkpoint")
                if ckpt:
                    return str(ckpt)
    except Exception:
        pass
    return DEFAULT_CHECKPOINT


def _get_custom_workflow() -> Optional[Dict[str, Any]]:
    """Load a custom workflow from env var or config path, if set."""
    # 1. Inline JSON via COMFYUI_WORKFLOW_JSON
    inline = os.environ.get("COMFYUI_WORKFLOW_JSON")
    if inline:
        try:
            return json.loads(inline)
        except (json.JSONDecodeError, TypeError):
            logger.warning("COMFYUI_WORKFLOW_JSON is set but not valid JSON")

    # 2. File path via config
    try:
        from clio_cli.config import load_config
        cfg = load_config() or {}
        section = cfg.get("image_gen", {})
        if isinstance(section, dict):
            comfyui_cfg = section.get("comfyui", {})
            if isinstance(comfyui_cfg, dict):
                wf_path = comfyui_cfg.get("workflow_path")
                if wf_path:
                    p = Path(wf_path).expanduser()
                    if p.exists():
                        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass

    return None


def _load_negative_prompt() -> str:
    """Load a default negative prompt from config, if set."""
    try:
        from clio_cli.config import load_config
        cfg = load_config() or {}
        section = cfg.get("image_gen", {})
        if isinstance(section, dict):
            comfyui_cfg = section.get("comfyui", {})
            if isinstance(comfyui_cfg, dict):
                np = comfyui_cfg.get("negative_prompt")
                if np:
                    return str(np)
    except Exception:
        pass
    return "text, watermark, low quality, blurry, deformed"


# --------------------------------------------------------------------------- #
#  Provider
# --------------------------------------------------------------------------- #


class ComfyUIImageGenProvider(ImageGenProvider):
    """Local ComfyUI (Stable Diffusion) image generation backend.

    Talks to a ComfyUI server running on your machine or LAN. No API key
    required — ComfyUI is self-hosted.  Configure via:

    - ``COMFYUI_URL`` env var (default: http://127.0.0.1:8188)
    - ``COMFYUI_CHECKPOINT`` env var (which SD model to use)
    - ``image_gen.comfyui.workflow_path`` config (path to custom workflow JSON)
    - ``image_gen.comfyui.negative_prompt`` config (default negative prompt)
    """

    @property
    def name(self) -> str:
        return "comfyui"

    @property
    def display_name(self) -> str:
        return "ComfyUI"

    def is_available(self) -> bool:
        """Check if a ComfyUI server is reachable."""
        import httpx
        url = _get_server_url()
        try:
            resp = httpx.get(f"{url}/system_stats", timeout=3.0)
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": DEFAULT_MODEL_ID,
                "display": "ComfyUI txt2img (local Stable Diffusion)",
                "speed": "~5-30s (GPU dependent)",
                "strengths": "Local, free, no API key, custom workflows",
                "price": "Free (self-hosted)",
            },
        ]

    def default_model(self) -> Optional[str]:
        return DEFAULT_MODEL_ID

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "ComfyUI",
            "badge": "local",
            "tag": "Self-hosted Stable Diffusion via ComfyUI",
            "env_vars": [
                {
                    "key": "COMFYUI_URL",
                    "prompt": "ComfyUI server URL (default: http://127.0.0.1:8188)",
                    "url": "https://github.com/comfyanonymous/ComfyUI",
                },
                {
                    "key": "COMFYUI_CHECKPOINT",
                    "prompt": "Checkpoint model filename (e.g. sd_xl_base_1.0.safetensors)",
                    "url": "",
                },
            ],
        }

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        import httpx

        prompt = (prompt or "").strip()
        aspect = resolve_aspect_ratio(aspect_ratio)

        if not prompt:
            return error_response(
                error="Prompt is required and must be a non-empty string",
                error_type="invalid_argument",
                provider="comfyui",
                aspect_ratio=aspect,
            )

        server_url = _get_server_url()
        checkpoint = _get_checkpoint()
        negative_prompt = _load_negative_prompt()

        # Resolve dimensions from aspect ratio
        width, height = _DIMENSIONS.get(aspect, _DIMENSIONS["square"])

        # Build or load workflow
        custom_wf = _get_custom_workflow()
        if custom_wf:
            # Custom workflow — inject prompt into the first CLIPTextEncode
            # node we find (best-effort).  Advanced users should pre-configure
            # their workflow with the right node IDs.
            workflow = self._inject_prompt_into_custom_workflow(
                custom_wf, prompt, negative_prompt, width, height
            )
        elif not checkpoint:
            # No checkpoint specified — try to auto-detect from the server
            checkpoint = self._auto_detect_checkpoint(server_url)
            if not checkpoint:
                return error_response(
                    error=(
                        "No checkpoint model found. Set COMFYUI_CHECKPOINT env "
                        "var or image_gen.comfyui.checkpoint in config to specify "
                        "which model file to use. Ensure at least one .safetensors "
                        "or .ckpt file is in ComfyUI's models/checkpoints/ directory."
                    ),
                    error_type="config_error",
                    provider="comfyui",
                    prompt=prompt,
                    aspect_ratio=aspect,
                )
            workflow = _build_txt2img_workflow(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                checkpoint=checkpoint,
                seed=hash(prompt) & 0xFFFFFFFF,  # deterministic-ish seed
            )
        else:
            workflow = _build_txt2img_workflow(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                checkpoint=checkpoint,
                seed=hash(prompt) & 0xFFFFFFFF,
            )

        # Submit the prompt to ComfyUI
        try:
            client_id = str(uuid.uuid4())
            resp = httpx.post(
                f"{server_url}/prompt",
                json={"prompt": workflow, "client_id": client_id},
                timeout=10.0,
            )
            if resp.status_code != 200:
                body = resp.text[:300]
                return error_response(
                    error=f"ComfyUI rejected the workflow (HTTP {resp.status_code}): {body}",
                    error_type="api_error",
                    provider="comfyui",
                    model=DEFAULT_MODEL_ID,
                    prompt=prompt,
                    aspect_ratio=aspect,
                )
            result_data = resp.json()
        except httpx.ConnectError:
            return error_response(
                error=(
                    f"Could not connect to ComfyUI at {server_url}. "
                    "Ensure the server is running (python main.py) and "
                    "COMFYUI_URL is set correctly."
                ),
                error_type="connection_error",
                provider="comfyui",
                prompt=prompt,
                aspect_ratio=aspect,
            )
        except Exception as exc:
            logger.debug("ComfyUI submission failed", exc_info=True)
            return error_response(
                error=f"ComfyUI request failed: {exc}",
                error_type="api_error",
                provider="comfyui",
                model=DEFAULT_MODEL_ID,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        prompt_id = result_data.get("prompt_id")
        if not prompt_id:
            return error_response(
                error=f"ComfyUI did not return a prompt_id: {result_data}",
                error_type="empty_response",
                provider="comfyui",
                model=DEFAULT_MODEL_ID,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        # Poll for completion
        image_url = self._poll_for_result(server_url, prompt_id)
        if image_url is None:
            return error_response(
                error=(
                    f"ComfyUI generation timed out after {_POLL_TIMEOUT}s. "
                    "The workflow may be too complex or the GPU may be busy."
                ),
                error_type="timeout",
                provider="comfyui",
                model=DEFAULT_MODEL_ID,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        # Download and cache the image locally
        full_url = f"{server_url}{image_url}"
        try:
            saved_path = save_url_image(full_url, prefix="comfyui_txt2img")
        except Exception as exc:
            logger.warning(
                "ComfyUI image %s could not be cached (%s); falling back to bare URL.",
                full_url,
                exc,
            )
            image_ref = full_url
        else:
            image_ref = str(saved_path)

        extra: Dict[str, Any] = {
            "width": width,
            "height": height,
            "checkpoint": checkpoint or "custom",
            "server": server_url,
        }

        return success_response(
            image=image_ref,
            model=DEFAULT_MODEL_ID,
            prompt=prompt,
            aspect_ratio=aspect,
            provider="comfyui",
            extra=extra,
        )

    # -- Internal helpers --------------------------------------------------

    def _auto_detect_checkpoint(self, server_url: str) -> str:
        """Try to list available checkpoints from the ComfyUI server."""
        import httpx
        try:
            resp = httpx.get(f"{server_url}/object_info/CheckpointLoaderSimple", timeout=5.0)
            if resp.status_code != 200:
                return ""
            data = resp.json()
            info = data.get("CheckpointLoaderSimple", {})
            inputs = info.get("input", {}).get("required", {})
            ckpt_info = inputs.get("ckpt_name", [])
            if ckpt_info and isinstance(ckpt_info, list):
                models = ckpt_info[0] if isinstance(ckpt_info[0], list) else []
                if models:
                    return models[0]
        except Exception:
            pass
        return ""

    def _inject_prompt_into_custom_workflow(
        self,
        workflow: Dict[str, Any],
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
    ) -> Dict[str, Any]:
        """Best-effort injection of prompt/dimensions into a custom workflow.

        Scans all nodes for CLIPTextEncode and EmptyLatentImage, injecting
        into the first match of each.  For production use, pre-configure
        your workflow with correct node IDs and use ``COMFYUI_WORKFLOW_JSON``
        with templating.
        """
        wf = json.loads(json.dumps(workflow))  # deep copy
        injected_positive = False
        injected_negative = False
        injected_dims = False

        for node_id, node in wf.items():
            if not isinstance(node, dict):
                continue
            class_type = node.get("class_type", "")
            inputs = node.get("inputs", {})

            if class_type == "CLIPTextEncode" and not injected_positive:
                # First CLIPTextEncode = positive prompt
                inputs["text"] = prompt
                injected_positive = True
            elif class_type == "CLIPTextEncode" and injected_positive and not injected_negative:
                # Second CLIPTextEncode = negative prompt
                inputs["text"] = negative_prompt
                injected_negative = True
            elif class_type == "EmptyLatentImage" and not injected_dims:
                inputs["width"] = width
                inputs["height"] = height
                injected_dims = True

        return wf

    def _poll_for_result(self, server_url: str, prompt_id: str) -> Optional[str]:
        """Poll the ComfyUI /history endpoint until generation completes.

        Returns the image retrieval URL path (e.g. ``/view?filename=...``)
        on success, or ``None`` on timeout.
        """
        import httpx
        deadline = time.time() + _POLL_TIMEOUT

        while time.time() < deadline:
            try:
                resp = httpx.get(
                    f"{server_url}/history/{prompt_id}",
                    timeout=10.0,
                )
                if resp.status_code != 200:
                    time.sleep(_POLL_INTERVAL)
                    continue

                data = resp.json()
                if not data:
                    time.sleep(_POLL_INTERVAL)
                    continue

                # The history response is keyed by prompt_id
                entry = data.get(prompt_id, {})
                if not entry:
                    time.sleep(_POLL_INTERVAL)
                    continue

                # Check for errors
                status = entry.get("status", {})
                if isinstance(status, dict) and status.get("status_str") == "error":
                    logger.error("ComfyUI generation error: %s", status)
                    return None

                # Extract output images
                outputs = entry.get("outputs", {})
                for node_id, node_output in outputs.items():
                    if not isinstance(node_output, dict):
                        continue
                    images = node_output.get("images", [])
                    if images:
                        first = images[0]
                        filename = first.get("filename", "")
                        subfolder = first.get("subfolder", "")
                        img_type = first.get("type", "output")
                        if filename:
                            return (
                                f"/view?filename={filename}"
                                f"&subfolder={subfolder}"
                                f"&type={img_type}"
                            )
            except Exception:
                time.sleep(_POLL_INTERVAL)

        return None


# --------------------------------------------------------------------------- #
#  Plugin entry point
# --------------------------------------------------------------------------- #


def register(ctx) -> None:
    """Plugin entry point — wire ``ComfyUIImageGenProvider`` into the registry."""
    ctx.register_image_gen_provider(ComfyUIImageGenProvider())