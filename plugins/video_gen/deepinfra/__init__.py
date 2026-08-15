"""DeepInfra OpenAI-compatible video job provider."""
from __future__ import annotations
import os
import time
from typing import Any

from agent.video_gen_provider import VideoGenProvider, error_response, save_bytes_video, success_response

DEFAULT_BASE_URL = "https://api.deepinfra.com/v1/openai"


def check_requirements() -> bool:
    try:
        import openai  # noqa: F401
    except ImportError:
        return False
    return bool(os.getenv("DEEPINFRA_API_KEY", "").strip())


class DeepInfraVideoGenProvider(VideoGenProvider):
    @property
    def name(self) -> str: return "deepinfra"

    @property
    def display_name(self) -> str: return "DeepInfra"

    def is_available(self) -> bool: return check_requirements()

    def list_models(self):
        model = self.default_model()
        return [{"id": model, "display": model.split("/")[-1], "modalities": ["text", "image"]}] if model else []

    def default_model(self): return os.getenv("DEEPINFRA_VIDEO_MODEL", "").strip() or None

    def capabilities(self):
        return {"modalities": ["text", "image"], "max_duration": 10, "min_duration": 1,
                "supports_negative_prompt": True, "operations": ["generate", "batch", "extend"]}

    def generate(self, prompt: str, *, model=None, image_url=None, reference_image_urls=None,
                 duration=None, aspect_ratio="16:9", resolution="720p", negative_prompt=None,
                 audio=None, seed=None, **kwargs: Any):
        key = os.getenv("DEEPINFRA_API_KEY", "").strip()
        model_id = model or self.default_model()
        if not key:
            return error_response(error="DEEPINFRA_API_KEY is not set", error_type="missing_credentials", provider=self.name)
        if not model_id:
            return error_response(error="Set DEEPINFRA_VIDEO_MODEL", error_type="no_model", provider=self.name)
        try:
            import openai
            client = openai.OpenAI(api_key=key, base_url=os.getenv("DEEPINFRA_BASE_URL", DEFAULT_BASE_URL).rstrip("/"))
            extra = {k: v for k, v in {"image_url": image_url, "negative_prompt": negative_prompt,
                                       "aspect_ratio": aspect_ratio, "seed": seed}.items() if v is not None}
            call = {"model": model_id, "prompt": prompt, "size": resolution, "extra_body": extra}
            if duration: call["seconds"] = str(duration)
            job = client.videos.create(**call)
            deadline = time.monotonic() + float(os.getenv("DEEPINFRA_VIDEO_TIMEOUT", "900"))
            while getattr(job, "status", None) not in {"completed", "succeeded", "failed", "error", "cancelled"}:
                if time.monotonic() >= deadline: raise TimeoutError("video job timed out")
                time.sleep(5); job = client.videos.retrieve(job.id)
            if getattr(job, "status", None) not in {"completed", "succeeded"}:
                raise RuntimeError(str(getattr(job, "error", None) or f"job status {job.status}"))
            raw = client.videos.download_content(job.id).read()
            path = save_bytes_video(raw, prefix="deepinfra")
            return success_response(video=str(path), model=model_id, prompt=prompt,
                                    modality="image" if image_url else "text", aspect_ratio=aspect_ratio,
                                    duration=duration or 0, provider=self.name)
        except Exception as exc:
            return error_response(error=f"DeepInfra video generation failed: {exc}", error_type="api_error",
                                  provider=self.name, model=model_id or "", prompt=prompt, aspect_ratio=aspect_ratio)


def register(ctx) -> None:
    ctx.register_video_gen_provider(DeepInfraVideoGenProvider())
