"""ACP display strings brand the managed subscription as Omni Loop Portal."""

from acp_adapter.server import _provider_label


def test_managed_renders_portal_brand():
    assert _provider_label("managed") == "Omni Loop Portal"


def test_none_falls_back_to_openrouter():
    # Display fallback for an unset provider (mirrors the old `or 'openrouter'`).
    assert _provider_label(None) in {"OpenRouter", "openrouter"}


def test_unknown_slug_passthrough():
    assert _provider_label("totally-custom") == "totally-custom"
