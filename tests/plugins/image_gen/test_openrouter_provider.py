"""Focused tests for the optional OpenRouter image provider."""

from __future__ import annotations

from unittest.mock import MagicMock


def _response(payload):
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    return response


def test_picker_catalog_preserves_default_during_partial_live_outage(monkeypatch):
    from plugins.image_gen import openrouter

    live_model = {
        "id": "vendor/live-image",
        "display": "Live Image",
        "strengths": "OpenRouter Image API",
        "surface": "images",
    }
    monkeypatch.setattr(openrouter, "_fetch_catalogs", lambda *_: ([live_model], []))

    models = openrouter.OpenRouterImageGenProvider().list_models()

    assert models[0]["id"] == openrouter.DEFAULT_MODEL
    assert any(model["id"] == "vendor/live-image" for model in models)


def test_picker_catalog_has_curated_offline_fallback(monkeypatch):
    from plugins.image_gen import openrouter

    monkeypatch.setattr(openrouter, "_fetch_catalogs", lambda *_: ([], []))

    model_ids = {
        model["id"] for model in openrouter.OpenRouterImageGenProvider().list_models()
    }

    assert openrouter.DEFAULT_MODEL in model_ids
    assert "openai/gpt-image-2" in model_ids


def test_chat_generation_uses_image_output_contract(monkeypatch):
    import requests
    from plugins.image_gen import openrouter

    response = _response({
        "choices": [{
            "message": {
                "images": [{"image_url": {"url": "data:image/png;base64,aW1hZ2U="}}],
            },
        }],
    })
    post = MagicMock(return_value=response)
    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(openrouter, "_api_key", lambda: "test-openrouter-key")
    monkeypatch.setattr(openrouter, "_base_url", lambda: "https://router.test/v1")
    monkeypatch.setattr(openrouter, "_select_surface", lambda *_: "chat")
    monkeypatch.setattr(openrouter, "save_b64_image", lambda *_args, **_kwargs: "/tmp/chat.png")

    result = openrouter.OpenRouterImageGenProvider().generate("draw a cat", "portrait")

    assert result["success"] is True
    assert result["image"] == "/tmp/chat.png"
    assert result["endpoint"] == "chat/completions"
    request = post.call_args
    assert request.args[0] == "https://router.test/v1/chat/completions"
    assert request.kwargs["json"]["modalities"] == ["image", "text"]
    assert request.kwargs["json"]["image_config"] == {"aspect_ratio": "9:16"}
    assert request.kwargs["headers"]["Authorization"] == "Bearer test-openrouter-key"


def test_dedicated_generation_routes_and_clamps_model_parameters(monkeypatch):
    import requests
    from plugins.image_gen import openrouter

    response = _response({"data": [{"b64_json": "aW1hZ2U="}], "usage": {"images": 1}})
    post = MagicMock(return_value=response)
    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(openrouter, "_api_key", lambda: "test-openrouter-key")
    monkeypatch.setattr(openrouter, "_base_url", lambda: "https://router.test/v1")
    monkeypatch.setattr(openrouter, "_select_surface", lambda *_: "images")
    monkeypatch.setattr(openrouter, "save_b64_image", lambda *_args, **_kwargs: "/tmp/api.png")

    result = openrouter.OpenRouterImageGenProvider().generate(
        "draw a poster",
        "portrait",
        model="openai/gpt-image-2",
        quality="high",
        n=50,
    )

    assert result["success"] is True
    assert result["endpoint"] == "images/generations"
    assert result["usage"] == {"images": 1}
    request = post.call_args
    assert request.args[0] == "https://router.test/v1/images/generations"
    assert request.kwargs["json"] == {
        "model": "openai/gpt-image-2",
        "prompt": "draw a poster",
        "aspect_ratio": "9:16",
        "quality": "high",
        "n": 10,
    }
    assert "n=50 clamped to 10" in result["notes"]


def test_signed_url_cache_failure_preserves_media_reference(monkeypatch):
    from plugins.image_gen import openrouter

    monkeypatch.setattr(
        openrouter,
        "save_url_image",
        MagicMock(side_effect=OSError("temporary download failure")),
    )

    url = "https://images.example/signed.png"
    assert openrouter._save_entry({"url": url}, "openrouter") == url


def test_empty_prompt_is_rejected_before_credentials(monkeypatch):
    from plugins.image_gen import openrouter

    monkeypatch.setattr(openrouter, "_api_key", lambda: "")

    result = openrouter.OpenRouterImageGenProvider().generate("   ")

    assert result["success"] is False
    assert result["error_type"] == "invalid_argument"
