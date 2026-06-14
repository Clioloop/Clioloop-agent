"""Tests for the Vidu video gen plugin."""

from __future__ import annotations

import json
from typing import Any, Dict, List

import pytest

from agent import video_gen_registry


@pytest.fixture(autouse=True)
def _reset_registry():
    video_gen_registry._reset_for_tests()
    yield
    video_gen_registry._reset_for_tests()


class _FakeResponse:
    def __init__(self, status: int = 200, payload: Dict[str, Any] | None = None):
        self.status_code = status
        self._payload = payload or {}
        self.text = json.dumps(self._payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError("err", request=None, response=self)  # type: ignore[arg-type]

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, get_payloads: List[Dict[str, Any]] | None = None):
        self.posts: List[Dict[str, Any]] = []
        self.gets: List[Dict[str, Any]] = []
        self.get_payloads = list(get_payloads or [
            {
                "state": "success",
                "credits": 35,
                "creations": [
                    {
                        "id": "creation-1",
                        "url": "https://vidu.example/video.mp4",
                        "cover_url": "https://vidu.example/cover.jpg",
                    }
                ],
            }
        ])

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def post(self, url, headers=None, json=None, timeout=None):
        self.posts.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return _FakeResponse(200, {
            "task_id": "task-123",
            "state": "created",
            "model": json["model"],
            "duration": json["duration"],
            "resolution": json["resolution"],
            "credits": 35,
        })

    def get(self, url, headers=None, timeout=None):
        self.gets.append({"url": url, "headers": headers, "timeout": timeout})
        payload = self.get_payloads.pop(0) if self.get_payloads else self.gets[-1]
        return _FakeResponse(200, payload)


@pytest.fixture
def vidu_provider(monkeypatch):
    monkeypatch.setenv("VIDU_API_KEY", "test-vidu-key")

    import plugins.video_gen.vidu as vidu_plugin

    captured: Dict[str, _FakeClient] = {}

    def _client_factory():
        captured["client"] = _FakeClient()
        return captured["client"]

    monkeypatch.setattr(vidu_plugin.httpx, "Client", _client_factory)
    monkeypatch.setattr(vidu_plugin.time, "sleep", lambda *_args, **_kwargs: None)
    provider = vidu_plugin.ViduVideoGenProvider()
    return provider, captured, vidu_plugin


def _last_post(captured) -> Dict[str, Any]:
    return captured["client"].posts[-1]


def test_vidu_provider_registers():
    from plugins.video_gen.vidu import DEFAULT_MODEL, ViduVideoGenProvider

    provider = ViduVideoGenProvider()
    video_gen_registry.register_provider(provider)

    assert video_gen_registry.get_provider("vidu") is provider
    assert provider.default_model() == DEFAULT_MODEL
    assert provider.display_name == "Vidu"


def test_text_to_video_payload_defaults_to_audio_and_540p(vidu_provider):
    provider, captured, _plugin = vidu_provider

    result = provider.generate("a robot walking through neon rain")

    assert result["success"] is True
    assert result["provider"] == "vidu"
    assert result["video"] == "https://vidu.example/video.mp4"
    assert _last_post(captured)["url"].endswith("/text2video")
    payload = _last_post(captured)["json"]
    assert payload["model"] == "viduq3-turbo"
    assert payload["prompt"] == "a robot walking through neon rain"
    assert payload["duration"] == 5
    assert payload["resolution"] == "540p"
    assert payload["audio"] is True
    assert payload["off_peak"] is False
    assert payload["aspect_ratio"] == "16:9"
    assert "images" not in payload


def test_image_to_video_payload_uses_images_array(vidu_provider):
    provider, captured, _plugin = vidu_provider

    result = provider.generate(
        "animate this frame",
        image_url="https://example.com/frame.png",
        duration=3,
        resolution="720p",
    )

    assert result["success"] is True
    assert result["modality"] == "image"
    assert _last_post(captured)["url"].endswith("/img2video")
    payload = _last_post(captured)["json"]
    assert payload["images"] == ["https://example.com/frame.png"]
    assert payload["duration"] == 3
    assert payload["resolution"] == "720p"
    assert "aspect_ratio" not in payload


def test_duration_clamps_to_10_seconds(vidu_provider):
    provider, captured, _plugin = vidu_provider

    provider.generate("x", duration=30)

    assert _last_post(captured)["json"]["duration"] == 10


def test_local_image_path_is_sent_as_data_uri(vidu_provider, tmp_path):
    provider, captured, _plugin = vidu_provider
    image_path = tmp_path / "frame.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\nfake")

    provider.generate("animate this", image_url=str(image_path))

    payload = _last_post(captured)["json"]
    assert payload["images"][0].startswith("data:image/png;base64,")


def test_polls_task_creations_endpoint(vidu_provider):
    provider, captured, _plugin = vidu_provider

    provider.generate("x")

    assert captured["client"].gets[-1]["url"].endswith("/tasks/task-123/creations")


def test_failed_generation_returns_error(monkeypatch):
    monkeypatch.setenv("VIDU_API_KEY", "test-vidu-key")

    import plugins.video_gen.vidu as vidu_plugin

    captured: Dict[str, _FakeClient] = {}

    def _client_factory():
        captured["client"] = _FakeClient(get_payloads=[{"state": "failed", "err_code": "bad_prompt"}])
        return captured["client"]

    monkeypatch.setattr(vidu_plugin.httpx, "Client", _client_factory)
    monkeypatch.setattr(vidu_plugin.time, "sleep", lambda *_args, **_kwargs: None)

    result = vidu_plugin.ViduVideoGenProvider().generate("x")

    assert result["success"] is False
    assert result["error_type"] == "api_error"
    assert "bad_prompt" in result["error"]


def test_managed_gateway_uses_bearer_token(monkeypatch):
    import plugins.video_gen.vidu as vidu_plugin

    class ManagedGateway:
        gateway_origin = "https://portal.example/api/gateway/vidu"
        managed_user_token = "managed-token"

    monkeypatch.delenv("VIDU_API_KEY", raising=False)
    monkeypatch.setattr(vidu_plugin, "_resolve_managed_vidu_gateway", lambda: ManagedGateway())

    base_url, headers, managed = vidu_plugin._resolve_vidu_client_config()

    assert managed is True
    assert base_url == "https://portal.example/api/gateway/vidu"
    assert headers["Authorization"] == "Bearer managed-token"
