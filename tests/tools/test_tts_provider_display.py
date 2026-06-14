"""TTS provider-display branding.

The managed Omni Loop Portal gateway is a self-hosted Supertonic server that
speaks the OpenAI ``/v1/audio/speech`` dialect, so the config provider stays
``"openai"``. The tool result/log must surface ``"Omni Loop Portal"`` when the
gateway actually serves the request, while a user's own direct OpenAI key keeps
showing ``"openai"``.
"""

import tools.tts_tool as tts_tool


def test_openai_via_managed_gateway_shows_portal_brand(monkeypatch):
    monkeypatch.setattr(tts_tool, "prefers_gateway", lambda section: section == "tts")
    assert tts_tool._provider_display("openai") == "Omni Loop Portal"


def test_openai_direct_key_keeps_openai(monkeypatch):
    monkeypatch.setattr(tts_tool, "prefers_gateway", lambda section: False)
    assert tts_tool._provider_display("openai") == "openai"


def test_other_providers_are_never_rebranded(monkeypatch):
    # Even with the gateway preferred, non-openai providers pass through as-is.
    monkeypatch.setattr(tts_tool, "prefers_gateway", lambda section: True)
    assert tts_tool._provider_display("edge") == "edge"
    assert tts_tool._provider_display("elevenlabs") == "elevenlabs"
