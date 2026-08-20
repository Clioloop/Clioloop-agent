from __future__ import annotations

import json
import pytest

from agent import image_gen_registry
from agent.image_gen_provider import ImageGenProvider


@pytest.fixture(autouse=True)
def _reset_registry():
    image_gen_registry._reset_for_tests()
    yield
    image_gen_registry._reset_for_tests()


class _FakeCodexProvider(ImageGenProvider):
    @property
    def name(self) -> str:
        return "codex"

    def capabilities(self):
        return {
            "modalities": ["text", "image"],
            "operations": ["generate", "edit"],
            "max_reference_images": 4,
        }

    def generate(self, prompt, aspect_ratio="landscape", **kwargs):
        return {
            "success": True,
            "image": "/tmp/codex-test.png",
            "model": "gpt-5.2-codex",
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "provider": "codex",
        }


class TestPluginDispatch:
    def test_dispatch_routes_to_codex_provider(self, monkeypatch, tmp_path):
        from tools import image_generation_tool
        from agent import image_gen_registry as registry_module
        from clio_cli import plugins as plugins_module

        monkeypatch.setenv("CLIO_HOME", str(tmp_path))
        (tmp_path / "config.yaml").write_text("image_gen:\n  provider: codex\n")
        image_gen_registry.register_provider(_FakeCodexProvider())

        monkeypatch.setattr(image_generation_tool, "_read_configured_image_provider", lambda: "codex")
        monkeypatch.setattr(plugins_module, "_ensure_plugins_discovered", lambda: None)
        monkeypatch.setattr(registry_module, "get_provider", lambda name: _FakeCodexProvider() if name == "codex" else None)

        dispatched = image_generation_tool._dispatch_to_plugin_provider("draw cat", "square")
        payload = json.loads(dispatched)

        assert payload["success"] is True
        assert payload["provider"] == "codex"
        assert payload["image"] == "/tmp/codex-test.png"
        assert payload["aspect_ratio"] == "square"

    def test_dispatch_forwards_input_images_and_edit_action(self, monkeypatch):
        from tools import image_generation_tool
        from agent import image_gen_registry as registry_module
        from clio_cli import plugins as plugins_module

        provider = _FakeCodexProvider()
        captured = {}

        def fake_generate(prompt, aspect_ratio="landscape", **kwargs):
            captured.update({"prompt": prompt, "aspect_ratio": aspect_ratio, **kwargs})
            return {"success": True, "image": "/tmp/edited.png", "provider": "codex"}

        provider.generate = fake_generate
        monkeypatch.setattr(image_generation_tool, "_read_configured_image_provider", lambda: "codex")
        monkeypatch.setattr(image_generation_tool, "_read_configured_image_model", lambda: "gpt-image-high")
        monkeypatch.setattr(plugins_module, "_ensure_plugins_discovered", lambda *a, **kw: None)
        monkeypatch.setattr(registry_module, "get_provider", lambda name: provider)

        dispatched = image_generation_tool._dispatch_to_plugin_provider(
            "move them to a beach",
            "portrait",
            input_images=["/tmp/base.png", "https://example.com/ref.jpg"],
            action="edit",
        )
        assert dispatched is not None
        payload = json.loads(dispatched)

        assert payload["success"] is True
        assert captured == {
            "prompt": "move them to a beach",
            "aspect_ratio": "portrait",
            "input_images": ["/tmp/base.png", "https://example.com/ref.jpg"],
            "action": "edit",
            "model": "gpt-image-high",
        }

    def test_dispatch_rejects_references_for_text_only_provider(self, monkeypatch):
        from tools import image_generation_tool
        from agent import image_gen_registry as registry_module
        from clio_cli import plugins as plugins_module

        class _TextOnlyProvider(_FakeCodexProvider):
            def capabilities(self):
                return {"modalities": ["text"], "operations": ["generate"], "max_reference_images": 0}

        provider = _TextOnlyProvider()
        monkeypatch.setattr(image_generation_tool, "_read_configured_image_provider", lambda: "codex")
        monkeypatch.setattr(plugins_module, "_ensure_plugins_discovered", lambda *a, **kw: None)
        monkeypatch.setattr(registry_module, "get_provider", lambda name: provider)

        dispatched = image_generation_tool._dispatch_to_plugin_provider(
            "edit", "square", input_images=["/tmp/base.png"], action="edit",
        )
        assert dispatched is not None
        payload = json.loads(dispatched)
        assert payload["success"] is False
        assert payload["error_type"] == "reference_images_unsupported"

    def test_dispatch_reports_missing_registered_provider(self, monkeypatch, tmp_path):
        from tools import image_generation_tool
        from clio_cli import plugins as plugins_module

        monkeypatch.setenv("CLIO_HOME", str(tmp_path))
        (tmp_path / "config.yaml").write_text("image_gen:\n  provider: missing-codex\n")

        monkeypatch.setattr(image_generation_tool, "_read_configured_image_provider", lambda: "missing-codex")
        monkeypatch.setattr(plugins_module, "_ensure_plugins_discovered", lambda: None)

        dispatched = image_generation_tool._dispatch_to_plugin_provider("draw cat", "landscape")
        payload = json.loads(dispatched)

        assert payload["success"] is False
        assert payload["error_type"] == "provider_not_registered"
        assert "image_gen.provider='missing-codex'" in payload["error"]

    def test_dispatch_force_refreshes_plugins_when_provider_initially_missing(self, monkeypatch, tmp_path):
        from tools import image_generation_tool
        from clio_cli import plugins as plugins_module
        from agent import image_gen_registry as registry_module

        monkeypatch.setenv("CLIO_HOME", str(tmp_path))
        (tmp_path / "config.yaml").write_text("image_gen:\n  provider: codex\n")

        monkeypatch.setattr(image_generation_tool, "_read_configured_image_provider", lambda: "codex")

        calls = []
        provider_state = {"provider": None}

        def fake_ensure_plugins_discovered(force=False):
            calls.append(force)
            if force:
                provider_state["provider"] = _FakeCodexProvider()

        monkeypatch.setattr(plugins_module, "_ensure_plugins_discovered", fake_ensure_plugins_discovered)
        monkeypatch.setattr(registry_module, "get_provider", lambda name: provider_state["provider"])

        dispatched = image_generation_tool._dispatch_to_plugin_provider("draw hammy", "portrait")
        payload = json.loads(dispatched)

        assert calls == [False, True]
        assert payload["success"] is True
        assert payload["provider"] == "codex"
        assert payload["aspect_ratio"] == "portrait"
