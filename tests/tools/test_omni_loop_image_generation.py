from __future__ import annotations

import json
from pathlib import Path

from tools.managed_tool_gateway import ManagedToolGatewayConfig


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


class _Response:
    def __init__(self, *, headers=None, content=b"", payload=None, status_code=200, text=""):
        self.headers = headers or {}
        self.content = content
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(response=self)


def _gateway():
    return ManagedToolGatewayConfig(
        vendor="clioloop-image",
        gateway_origin="https://portal.example.com/api/gateway/clioloop-image",
        managed_user_token="managed-token",
        managed_mode=True,
    )


def test_omni_loop_relative_image_url_is_fetched_through_gateway(monkeypatch, tmp_path):
    from tools import image_generation_tool

    monkeypatch.setenv("CLIO_HOME", str(tmp_path))
    monkeypatch.setattr(image_generation_tool, "_resolve_omni_loop_image_gateway", _gateway)

    calls = {}

    def fake_post(url, *, headers, json, timeout):
        calls["post"] = {
            "url": url,
            "headers": headers,
            "json": json,
            "timeout": timeout,
        }
        return _Response(
            headers={"content-type": "application/json"},
            payload={"image_url": "/images/generated.png"},
        )

    def fake_get(url, *, headers, timeout):
        calls["get"] = {
            "url": url,
            "headers": headers,
            "timeout": timeout,
        }
        return _Response(headers={"content-type": "image/png"}, content=PNG_BYTES)

    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setattr("requests.get", fake_get)

    result = json.loads(image_generation_tool.omni_loop_image_generate_tool("draw a lighthouse"))

    assert result["success"] is True
    assert result["provider"] == "omni-loop"
    assert result["model"] == "clioloop-local"
    assert calls["post"]["url"] == "https://portal.example.com/api/gateway/clioloop-image/generate"
    assert calls["post"]["headers"]["Authorization"] == "Bearer managed-token"
    assert calls["post"]["json"] == {"prompt": "draw a lighthouse", "steps": 4}
    assert calls["get"]["url"] == "https://portal.example.com/api/gateway/clioloop-image/images/generated.png"
    assert calls["get"]["headers"]["Authorization"] == "Bearer managed-token"

    image_path = Path(result["image"])
    assert image_path.is_file()
    assert image_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_omni_loop_raw_image_response_is_saved(monkeypatch, tmp_path):
    from tools import image_generation_tool

    monkeypatch.setenv("CLIO_HOME", str(tmp_path))
    monkeypatch.setattr(image_generation_tool, "_resolve_omni_loop_image_gateway", _gateway)

    def fake_post(url, *, headers, json, timeout):
        return _Response(headers={"content-type": "image/png"}, content=PNG_BYTES)

    monkeypatch.setattr("requests.post", fake_post)

    result = json.loads(image_generation_tool.omni_loop_image_generate_tool("draw a moon", "square"))

    assert result["success"] is True
    assert result["aspect_ratio"] == "square"
    assert Path(result["image"]).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_legacy_clioloop_provider_dispatches_to_omni_loop(monkeypatch):
    from tools import image_generation_tool

    monkeypatch.setattr(image_generation_tool, "_read_configured_image_provider", lambda: "clioloop")
    monkeypatch.setattr(
        image_generation_tool,
        "omni_loop_image_generate_tool",
        lambda prompt, aspect_ratio: json.dumps(
            {
                "success": True,
                "image": "/tmp/omni.png",
                "provider": "omni-loop",
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
            }
        ),
    )

    result = json.loads(image_generation_tool._dispatch_to_plugin_provider("draw a bridge", "portrait"))

    assert result["success"] is True
    assert result["provider"] == "omni-loop"
    assert result["prompt"] == "draw a bridge"
    assert result["aspect_ratio"] == "portrait"


def test_direct_fal_provider_is_inactive_for_image_generation(monkeypatch):
    from tools import image_generation_tool

    monkeypatch.setattr(image_generation_tool, "_read_configured_image_provider", lambda: "fal")
    monkeypatch.setattr(image_generation_tool, "_configured_image_uses_gateway", lambda: False)

    result = json.loads(image_generation_tool._dispatch_to_plugin_provider("draw a forest", "landscape"))

    assert result["success"] is False
    assert result["error_type"] == "provider_inactive"
    assert "Direct FAL image generation is no longer active" in result["error"]
