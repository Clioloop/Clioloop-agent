"""Tests for the Clioloop self-hosted image-gen provider (managed gateway)."""

from __future__ import annotations

import base64

import pytest

import plugins.image_gen.clioloop as mod


class _FakeResponse:
    def __init__(self, *, content=b"", headers=None, json_data=None, status_code=200, text=""):
        self.content = content
        self.headers = headers or {}
        self._json = json_data
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            err = requests.HTTPError(f"HTTP {self.status_code}")
            err.response = self
            raise err

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setattr(mod, "read_managed_access_token", lambda: "olp_at_token")
    monkeypatch.setattr(mod, "build_vendor_gateway_url", lambda vendor: f"https://portal.example/api/gateway/{vendor}")
    monkeypatch.setattr(mod, "save_b64_image", lambda b64, **kw: f"/cache/{kw.get('prefix', 'img')}.{kw.get('extension', 'png')}")
    monkeypatch.setattr(mod, "save_url_image", lambda url, **kw: "/cache/from-url.png")
    return mod.ClioloopImageGenProvider()


def test_requires_prompt(provider):
    r = provider.generate("")
    assert r["error_type"] == "invalid_request"


def test_requires_managed_token(monkeypatch):
    monkeypatch.setattr(mod, "read_managed_access_token", lambda: None)
    r = mod.ClioloopImageGenProvider().generate("a cat")
    assert r["error_type"] == "auth_error"


def test_raw_image_bytes_response(provider, monkeypatch):
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _FakeResponse(content=b"\x89PNG...", headers={"content-type": "image/png"})

    monkeypatch.setattr(mod.requests, "post", fake_post)
    r = provider.generate("a red cube", steps=6)

    assert r.get("error") is None
    assert r["provider"] == "clioloop"
    assert r["image"].endswith(".png")
    # Routed through the managed gateway with the OAuth bearer + {prompt, steps}.
    assert captured["url"] == "https://portal.example/api/gateway/clioloop-image/generate"
    assert captured["headers"]["Authorization"] == "Bearer olp_at_token"
    assert captured["json"] == {"prompt": "a red cube", "steps": 6}


def test_json_base64_response(provider, monkeypatch):
    b64 = base64.b64encode(b"img").decode()
    monkeypatch.setattr(
        mod.requests,
        "post",
        lambda *a, **kw: _FakeResponse(headers={"content-type": "application/json"}, json_data={"image_base64": b64}),
    )
    r = provider.generate("a dog")
    assert r.get("error") is None
    assert r["image"].startswith("/cache/clioloop")


def test_json_url_response(provider, monkeypatch):
    monkeypatch.setattr(
        mod.requests,
        "post",
        lambda *a, **kw: _FakeResponse(headers={"content-type": "application/json"}, json_data={"image_url": "https://x/y.png"}),
    )
    r = provider.generate("a tree")
    assert r.get("error") is None
    assert r["image"] == "/cache/from-url.png"


def test_http_error_surfaces(provider, monkeypatch):
    monkeypatch.setattr(
        mod.requests,
        "post",
        lambda *a, **kw: _FakeResponse(status_code=402, text="payment required"),
    )
    r = provider.generate("a fish")
    assert r["error_type"] == "provider_error"
    assert "402" in r["error"]


def test_unrecognized_json_response(provider, monkeypatch):
    monkeypatch.setattr(
        mod.requests,
        "post",
        lambda *a, **kw: _FakeResponse(headers={"content-type": "application/json"}, json_data={"unexpected": True}),
    )
    r = provider.generate("a bird")
    assert r["error_type"] == "provider_error"
    assert "no recognizable image data" in r["error"]
