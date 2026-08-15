"""Focused compatibility and security-contract tests for the plugin v2 foundation."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from agent.redact import (
    _remove_redaction_patterns,
    redact_sensitive_text,
    register_redaction_patterns,
)
from agent.secret_sources import CommandSecretProvider, EnvironmentSecretProvider
from agent.secret_sources.base import ErrorKind
from clio_cli.plugin_capabilities import (
    capability_set_hash,
    declared_set_changed,
    granted_capabilities,
    pending_capabilities,
    plugin_capability_granted,
)
from clio_cli.plugin_runtime import (
    AllowlistEgressPolicy,
    DenialCircuitBreaker,
    EgressRequest,
    EventBus,
    NamespacedState,
)
from clio_cli.plugins import LoadedPlugin, PluginContext, PluginManager, PluginManifest


def _manifest(tmp_path: Path, data: dict) -> PluginManifest:
    directory = tmp_path / data.get("name", "demo")
    directory.mkdir()
    manifest_file = directory / "plugin.yaml"
    manifest_file.write_text(yaml.safe_dump(data), encoding="utf-8")
    parsed = PluginManager()._parse_manifest(manifest_file, directory, "user", "")
    assert parsed is not None
    return parsed


def test_manifest_v1_defaults_and_v2_fields(tmp_path):
    v1 = _manifest(tmp_path, {"name": "legacy", "requires_env": ["TOKEN"]})
    assert v1.manifest_version == 1
    assert v1.capabilities == []
    assert v1.trust == "third-party"

    v2 = _manifest(tmp_path, {
        "name": "modern",
        "manifest_version": 2,
        "api_version": 1,
        "requires_plugins": ["base", {"id": "other", "version_range": ">=2"}],
        "capabilities": ["network.egress", "not-a-capability"],
        "emits": ["ready"],
        "listens": ["base:ready"],
    })
    assert v2.manifest_version == 2
    assert v2.api_version == 1
    assert v2.requires_plugins == [
        {"id": "base", "version_range": None},
        {"id": "other", "version_range": ">=2"},
    ]
    assert v2.capabilities == ["network.egress"]


def test_capability_grants_consent_and_declaration_binding():
    declared = ["tools.override", "network.egress"]
    config = {"plugins": {"entries": {"demo": {
        "granted_capabilities": ["network.egress", "bogus"],
        "allow_tool_override": True,
        "capabilities_consent": {"hash": capability_set_hash(declared)},
    }}}}
    assert granted_capabilities("demo", config) == frozenset({"network.egress"})
    assert plugin_capability_granted("demo", "tools.override", config)
    assert not plugin_capability_granted("demo", "unknown", config)
    assert pending_capabilities("demo", declared, config) == ["tools.override"]
    assert not declared_set_changed("demo", declared, config)
    assert declared_set_changed("demo", declared + ["redaction.register"], config)


def test_v2_capabilities_require_matching_operator_consent(tmp_path, monkeypatch):
    home = tmp_path / "home"
    plugins = home / "plugins"
    plugin = plugins / "guarded"
    plugin.mkdir(parents=True)
    (plugin / "plugin.yaml").write_text(yaml.safe_dump({
        "name": "guarded", "manifest_version": 2,
        "capabilities": ["network.egress"],
    }), encoding="utf-8")
    (plugin / "__init__.py").write_text(
        "def register(ctx):\n    raise RuntimeError('must not execute')\n", encoding="utf-8"
    )
    (home / "config.yaml").write_text(
        yaml.safe_dump({"plugins": {"enabled": ["guarded"]}}), encoding="utf-8"
    )
    monkeypatch.setenv("CLIO_HOME", str(home))
    monkeypatch.setattr("clio_cli.plugins.get_bundled_plugins_dir", lambda: tmp_path / "none")
    monkeypatch.setattr(PluginManager, "_scan_entry_points", lambda self: [])
    manager = PluginManager()
    manager.discover_and_load()
    loaded = manager._plugins["guarded"]
    assert not loaded.enabled
    assert "capability approval required" in (loaded.error or "")
    assert loaded.module is None


def test_event_state_isolation_and_safe_unload(tmp_path):
    bus = EventBus()
    seen = []
    handle = bus.subscribe("consumer", "producer:ready", lambda **payload: seen.append(payload))
    assert bus.emit("producer", "ready", {"items": [1]}) == 1
    assert seen == [{"items": [1]}]
    with pytest.raises(ValueError):
        bus.emit("producer", "other:ready", {})
    handle.dispose()
    assert bus.emit("producer", "ready", {}) == 0

    left = NamespacedState(tmp_path, "left")
    right = NamespacedState(tmp_path, "right")
    left.set("value", 1)
    assert left.get("value") == 1
    assert right.get("value") is None

    manager = PluginManager()
    manager._state_root = tmp_path
    manifest = PluginManifest(name="owned", key="owned", source="user")
    ctx = PluginContext(manifest, manager)
    calls = []
    ctx.register_hook("post_tool_call", lambda **_: calls.append(1))
    ctx.on_unload(lambda: calls.append(2))
    manager._plugins["owned"] = LoadedPlugin(manifest=manifest, enabled=True)
    assert manager.unload("owned")
    manager.invoke_hook("post_tool_call")
    assert calls == [2]


def test_redaction_extension_accepts_token_shape_and_rejects_unsafe_regex():
    source = "test:security"
    try:
        assert register_redaction_patterns(
            [r"acme_[A-Za-z0-9]{10,}", r"xx.*", r"aa(a+)+"], source=source
        ) == 1
        raw = "acme_1234567890ABC"
        assert redact_sensitive_text(raw, force=True) != raw
    finally:
        _remove_redaction_patterns(source)
    assert redact_sensitive_text("acme_1234567890ABC", force=True) == "acme_1234567890ABC"


def test_secret_providers_are_scoped_and_non_shell(tmp_path):
    env = EnvironmentSecretProvider({"SOURCE": "value"})
    assert env.fetch({"TARGET": "env://SOURCE"}, scope=frozenset({"TARGET"}), home=tmp_path).secrets == {"TARGET": "value"}
    denied = env.fetch({"OTHER": "env://SOURCE"}, scope=frozenset({"TARGET"}), home=tmp_path)
    assert denied.error_kind is ErrorKind.REF_INVALID

    command = CommandSecretProvider([sys.executable, "-c", "print('secret-value')"])
    result = command.fetch({"TOKEN": "unused"}, scope=frozenset({"TOKEN"}), home=tmp_path)
    assert result.ok and result.secrets == {"TOKEN": "secret-value"}


def test_denial_breaker_egress_and_mcp_trust(monkeypatch):
    breaker = DenialCircuitBreaker(threshold=2, max_scopes=2)
    assert not breaker.deny("plugin:a")
    assert breaker.deny("plugin:a")
    breaker.allow("plugin:a")
    assert breaker.count("plugin:a") == 0

    policy = AllowlistEgressPolicy({"api.example.com"})
    assert policy.authorize(EgressRequest("demo", "API.EXAMPLE.COM"))
    assert not policy.authorize(EgressRequest("demo", "evil.example"))

    import tools.mcp_tool as mcp
    monkeypatch.setitem(mcp._server_trust_levels, "srv", "untrusted")
    monkeypatch.setitem(mcp._tool_read_only_hints, "srv", {"read": True, "write": False})
    assert mcp._trust_gate_check("srv", "read") is None
    assert "requires operator approval" in (mcp._trust_gate_check("srv", "write") or "")
    monkeypatch.setattr(mcp, "_mcp_trust_approval_callback", lambda server, tool: True)
    assert mcp._trust_gate_check("srv", "write") is None
    assert mcp._normalize_server_trust("invalid") == "untrusted"
    assert mcp._normalize_server_trust(None) == "full"


def test_vercel_adapter_result_and_transient_error_contract(monkeypatch):
    import tools.environments.vercel_sandbox as vercel_module
    from tools.environments.vercel_sandbox import (
        _extract_result_output,
        _extract_result_returncode,
        _extract_snapshot_id,
        _is_transient_vercel_error,
    )

    result = SimpleNamespace(output=lambda: b"ok", exit_code=0)
    assert _extract_result_output(result) == "ok"
    assert _extract_result_returncode(result) == 0
    assert _extract_snapshot_id({"snapshotId": "snap_1"}) == "snap_1"
    class Transient(RuntimeError):
        status_code = 503

    assert _is_transient_vercel_error(Transient("retry"))
    assert not _is_transient_vercel_error(ValueError("bad config"))

    captured = {}

    class FakeEnvironment:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(vercel_module, "VercelSandboxEnvironment", FakeEnvironment)
    from tools.terminal_tool import _create_environment

    env = _create_environment(
        "vercel", "node22", "/vercel/sandbox", 45,
        container_config={"container_cpu": 2, "container_memory": 4096},
        task_id="task-1",
    )
    assert isinstance(env, FakeEnvironment)
    assert captured["runtime"] == "node22"
    assert captured["cpu"] == 2
    assert captured["task_id"] == "task-1"
