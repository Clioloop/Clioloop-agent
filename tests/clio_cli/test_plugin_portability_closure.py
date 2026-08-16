from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest


def test_portable_hook_inventory_has_payload_contracts():
    from clio_cli.plugins import HOOK_PAYLOAD_CONTRACTS, VALID_HOOKS, fire_plugin_hook

    assert set(HOOK_PAYLOAD_CONTRACTS) == VALID_HOOKS
    assert {"on_stream_start", "on_stream_delta", "on_stream_end", "on_interim_message"} <= VALID_HOOKS
    with pytest.raises(TypeError, match="stream_id"):
        fire_plugin_hook("on_stream_delta", delta="x")


def test_stream_callbacks_are_isolated_and_non_blocking(monkeypatch):
    from agent import plugin_stream_hooks as stream

    received: list[str] = []
    ready = threading.Event()

    def callback(**payload):
        received.append(payload["delta"])
        ready.set()

    monkeypatch.setattr(stream, "_callbacks", lambda hook: (callback,))
    assert stream.enqueue_plugin_stream_hook("on_stream_delta", stream_id="s", delta="x")
    assert ready.wait(1)
    assert received == ["x"]
    stream.shutdown_plugin_stream_hook_dispatcher()


def test_unload_restores_shadowed_host_entries_and_provider(tmp_path):
    from agent import image_gen_registry
    from agent.image_gen_provider import ImageGenProvider
    from clio_cli.plugins import PluginContext, PluginManager, PluginManifest

    class Provider(ImageGenProvider):
        def __init__(self, marker):
            self.marker = marker

        @property
        def name(self):
            return "closure-provider"

        def generate(self, *args, **kwargs):
            return {"marker": self.marker}

    image_gen_registry._reset_for_tests()
    previous_provider = Provider("previous")
    replacement_provider = Provider("replacement")
    image_gen_registry.register_provider(previous_provider)

    manager = PluginManager()
    manager._plugin_commands["closure-command"] = previous_command = {"old": True}
    context = PluginContext(PluginManifest("closure", key="closure", source="bundled"), manager)
    context.register_command("closure-command", lambda *_: "new")
    context.register_system_prompt_section("closure.section", "bounded")
    context.register_image_gen_provider(replacement_provider)

    assert image_gen_registry.get_provider("closure-provider") is replacement_provider
    assert manager.unload("closure")
    assert manager._plugin_commands["closure-command"] is previous_command
    assert "closure.section" not in manager._system_prompt_sections
    assert image_gen_registry.get_provider("closure-provider") is previous_provider
    image_gen_registry._reset_for_tests()


def test_provider_unregistration_is_identity_safe():
    from agent import (
        browser_registry, image_gen_registry, music_gen_registry,
        transcription_registry, tts_registry, video_gen_registry, web_search_registry,
    )

    for registry in (
        browser_registry, image_gen_registry, music_gen_registry,
        transcription_registry, tts_registry, video_gen_registry, web_search_registry,
    ):
        registry._reset_for_tests()
        provider = object()
        registry._providers["closure"] = provider
        assert not registry.unregister_provider("closure", object())
        assert registry._providers["closure"] is provider
        assert registry.unregister_provider("closure", provider)
        assert "closure" not in registry._providers


def test_context_reference_provider_resolves_and_unloads(tmp_path):
    from agent.context_references import (
        ContextReferenceProvider,
        get_context_reference_providers,
        preprocess_context_references,
    )
    from clio_cli.plugins import PluginContext, PluginManager, PluginManifest

    class IssueProvider(ContextReferenceProvider):
        prefix = "issue"

        async def resolve(self, value: str, cwd: Path) -> str:
            return f"issue={value};cwd={cwd.name}"

    manager = PluginManager()
    context = PluginContext(PluginManifest("refs", key="refs", source="bundled"), manager)
    assert context.register_context_reference(IssueProvider()) is not None
    result = preprocess_context_references(
        "inspect @issue:CLIO-42", cwd=tmp_path, context_length=1000
    )
    assert result.expanded and "issue=CLIO-42" in result.message
    assert manager.unload("refs")
    assert "issue" not in get_context_reference_providers()


def test_agent_package_and_index_validation(tmp_path):
    from clio_cli.agent_plugins import AgentPluginError, load_agent_plugin_package
    from clio_cli.plugin_index import parse_index

    root = tmp_path / "portable"
    skill = root / "skills" / "hello"
    skill.mkdir(parents=True)
    manifest = {
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        "name": "portable-test",
        "version": "1.0.0",
        "description": "Portable package",
        "exact_ref": "a" * 40,
    }
    (root / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
    (skill / "SKILL.md").write_text(
        "---\nname: hello\ndescription: Hello safely\n---\nBody\n", encoding="utf-8"
    )
    package = load_agent_plugin_package(root, tmp_path / "data")
    assert package.name == "portable-test"
    assert [item.name for item in package.skills] == ["hello"]
    assert package.exact_ref == "a" * 40

    manifest["exact_ref"] = "main"
    (root / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(AgentPluginError, match="immutable"):
        load_agent_plugin_package(root)

    entries = parse_index({"plugins": [
        {"name": "good", "repo": "owner/repo", "ref": "B" * 40, "subdir": "plugins/good"},
        {"name": "mutable", "repo": "owner/repo", "ref": "main"},
        {"name": "escape", "repo": "owner/repo", "ref": "c" * 40, "subdir": "../escape"},
    ]})
    assert [(entry.name, entry.ref, entry.subdir) for entry in entries] == [
        ("good", "b" * 40, "plugins/good")
    ]
