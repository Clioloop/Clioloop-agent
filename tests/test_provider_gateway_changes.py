"""Focused regression coverage for the provider/gateway parity fixes."""

from __future__ import annotations

import base64
import importlib
import json
import urllib.request
from unittest.mock import MagicMock

import pytest

from clio_cli import providers as cli_providers
from gateway.config import PlatformConfig
from gateway.platforms.telegram import (
    TelegramAdapter,
    _POLLING_GENERATION_CONTEXT,
)
from providers import get_provider_profile
from providers.base import ProviderProfile

codex_plugin = importlib.import_module("plugins.image_gen.openai-codex")

_PNG_HEX = (
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000d49444154789c6300010000000500010d0a2db40000000049454e44"
    "ae426082"
)


def _b64_png() -> str:
    return base64.b64encode(bytes.fromhex(_PNG_HEX)).decode()


class _Response:
    def __init__(self, payload: dict):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return json.dumps(self._payload).encode()


def test_provider_profile_custom_base_controls_model_discovery(monkeypatch):
    profile = ProviderProfile(
        name="test",
        base_url="https://default.example/v1",
        models_url="https://catalog.example/models",
    )
    captured = {}

    def _urlopen(request, timeout):
        captured.update(url=request.full_url, timeout=timeout)
        return _Response({"data": [{"id": "proxy-model"}]})

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen)
    assert profile.fetch_models(
        api_key="secret",
        base_url="https://proxy.example/v1/",
        timeout=3.0,
    ) == ["proxy-model"]
    assert captured == {"url": "https://proxy.example/v1/models", "timeout": 3.0}


def test_provider_profile_default_base_keeps_explicit_models_url(monkeypatch):
    profile = ProviderProfile(
        name="test",
        base_url="https://default.example/v1",
        models_url="https://catalog.example/models",
    )
    captured = {}

    def _urlopen(request, timeout):
        captured["url"] = request.full_url
        return _Response({"data": []})

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen)
    assert profile.fetch_models(
        api_key="secret", base_url="https://default.example/v1/"
    ) == []
    assert captured["url"] == "https://catalog.example/models"


def test_anthropic_and_custom_profiles_honor_caller_base(monkeypatch):
    urls = []

    def _urlopen(request, timeout):
        urls.append(request.full_url)
        return _Response({"data": [{"id": "remote-model"}]})

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen)
    anthropic = get_provider_profile("anthropic")
    custom = get_provider_profile("custom")
    assert anthropic.fetch_models(
        api_key="secret", base_url="https://proxy.example/anthropic/v1"
    ) == ["remote-model"]
    assert custom.fetch_models(base_url="http://localhost:11434/v1") == [
        "remote-model"
    ]
    assert urls == [
        "https://proxy.example/anthropic/v1/models",
        "http://localhost:11434/v1/models",
    ]
    assert get_provider_profile("copilot-acp").fetch_models(
        base_url="http://unused.example/v1"
    ) is None


def test_model_catalog_forwards_resolved_base_url(monkeypatch):
    from clio_cli import models

    profile = ProviderProfile(
        name="plugin-only",
        base_url="https://default.example/v1",
        fallback_models=("fallback",),
    )
    profile.fetch_models = MagicMock(return_value=["live-model"])
    monkeypatch.setattr("providers.get_provider_profile", lambda _name: profile)
    monkeypatch.setattr(
        "clio_cli.auth.resolve_api_key_provider_credentials",
        lambda _name: {
            "api_key": "secret",
            "base_url": "https://proxy.example/v1",
        },
    )

    assert models.provider_model_ids("plugin-only", force_refresh=True) == [
        "live-model"
    ]
    profile.fetch_models.assert_called_once_with(
        api_key="secret", base_url="https://proxy.example/v1"
    )


def test_plugin_only_provider_resolves_for_model_switch(monkeypatch):
    profile = ProviderProfile(
        name="plugin-only",
        display_name="Plugin Only",
        api_mode="anthropic_messages",
        base_url="https://plugin.example/v1",
        env_vars=("PLUGIN_ONLY_KEY",),
    )
    monkeypatch.setattr("providers.get_provider_profile", lambda _name: profile)

    resolved = cli_providers.get_provider("plugin-only")
    assert resolved is not None
    assert resolved.transport == "anthropic_messages"
    assert resolved.api_key_env_vars == ("PLUGIN_ONLY_KEY",)
    assert resolved.base_url == "https://plugin.example/v1"


def test_endpointless_plugin_profile_does_not_preempt_custom(monkeypatch):
    profile = ProviderProfile(name="custom", base_url="")
    monkeypatch.setattr("providers.get_provider_profile", lambda _name: profile)
    assert cli_providers.get_provider("custom:local") is None


def test_codex_extraction_prefers_final_over_later_partial():
    payload = {
        "output": [
            {"type": "image_generation_call", "result": "final-image"},
            {"partial_image_b64": "later-partial"},
        ]
    }
    assert codex_plugin._extract_image_b64(payload) == "final-image"


def test_codex_partial_only_retries_then_refuses_to_save(monkeypatch, tmp_path):
    monkeypatch.setenv("CLIO_HOME", str(tmp_path))
    monkeypatch.setattr(
        codex_plugin, "_read_codex_access_token", lambda: "codex-token"
    )
    calls = []

    def _partial(*args, **kwargs):
        calls.append((args, kwargs))
        return {"b64": _b64_png(), "source": "partial"}

    monkeypatch.setattr(codex_plugin, "_collect_image_b64", _partial)
    result = codex_plugin.OpenAICodexImageGenProvider().generate("a cat")
    assert len(calls) == 2
    assert result["success"] is False
    assert result["error_type"] == "incomplete_image"
    assert result["partial_pixel_size"] == "1x1"
    assert result["requested_size"] == "1536x1024"


def test_codex_retry_accepts_final_and_reports_pixels(monkeypatch, tmp_path):
    monkeypatch.setenv("CLIO_HOME", str(tmp_path))
    monkeypatch.setattr(
        codex_plugin, "_read_codex_access_token", lambda: "codex-token"
    )
    attempts = iter(
        [
            {"b64": _b64_png(), "source": "partial"},
            {"b64": _b64_png(), "source": "final"},
        ]
    )
    monkeypatch.setattr(
        codex_plugin, "_collect_image_b64", lambda *a, **kw: next(attempts)
    )
    result = codex_plugin.OpenAICodexImageGenProvider().generate("a cat")
    assert result["success"] is True
    assert result["image_source"] == "final"
    assert result["pixel_size"] == "1x1"
    assert result["requested_size"] == "1536x1024"


def _telegram_adapter() -> TelegramAdapter:
    return TelegramAdapter(PlatformConfig(enabled=True, token="test-token"))


@pytest.mark.asyncio
async def test_telegram_polling_progress_is_generation_scoped():
    adapter = _telegram_adapter()
    adapter._polling_network_error_count = 3
    adapter._send_path_degraded = True
    first, first_event = adapter._begin_polling_generation()
    second, second_event = adapter._begin_polling_generation()
    adapter._record_polling_progress(first)
    assert not first_event.is_set() and not second_event.is_set()
    assert adapter._polling_network_error_count == 3
    adapter._record_polling_progress(second)
    assert second_event.is_set()
    assert adapter._polling_network_error_count == 0
    assert adapter._send_path_degraded is False


@pytest.mark.asyncio
async def test_telegram_instrumented_get_updates_records_success():
    adapter = _telegram_adapter()

    class _Request:
        async def do_request(self):
            return 200, b'{"ok": true, "result": []}'

        def parse_json_payload(self, payload):
            return json.loads(payload)

    request = adapter._instrument_polling_request(_Request())
    generation, event = adapter._begin_polling_generation()
    token = _POLLING_GENERATION_CONTEXT.set(generation)
    try:
        assert await request.do_request() == (200, b'{"ok": true, "result": []}')
    finally:
        _POLLING_GENERATION_CONTEXT.reset(token)
    assert event.is_set()


@pytest.mark.asyncio
async def test_telegram_start_polling_tags_generation_context():
    adapter = _telegram_adapter()
    seen = {}

    async def _start_polling(**kwargs):
        seen.update(kwargs)
        seen["generation"] = _POLLING_GENERATION_CONTEXT.get()

    adapter._app = MagicMock()
    adapter._app.updater.start_polling = _start_polling
    adapter._polling_error_callback_ref = object()
    generation = await adapter._start_polling_generation(drop_pending_updates=True)
    assert seen["generation"] == generation
    assert seen["drop_pending_updates"] is True
    assert seen["error_callback"] is adapter._polling_error_callback_ref
