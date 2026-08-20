"""Profile-scoped MCP schema cache and invoke-time lazy-start tests."""

from __future__ import annotations

import asyncio
import json
import os

from tools.registry import registry


def test_schema_cache_fingerprint_ttl_permissions_and_secret_redaction(tmp_path, monkeypatch):
    from tools import mcp_schema_cache as cache

    path = tmp_path / "mcp-schema-cache.json"
    monkeypatch.setattr(cache, "_cache_path", lambda: path)
    config = {
        "command": "server",
        "args": ["--stdio"],
        "env": {"API_TOKEN": "super-secret", "PUBLIC_MODE": "safe"},
        "headers": {"Authorization": "Bearer private"},
        "lazy": True,
    }
    fingerprint = cache.config_fingerprint(config)
    cache.write_cache_entry(
        "demo",
        fingerprint,
        tools=[
            {
                "name": "lookup",
                "description": "Lookup an item",
                "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}}},
            }
        ],
        ttl_ms=1_000,
    )

    raw = path.read_text(encoding="utf-8")
    assert "super-secret" not in raw
    assert "Bearer private" not in raw
    assert cache.get_cached_entry("demo", fingerprint) is not None
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600

    data = json.loads(raw)
    data["demo"]["written_at"] = 0
    path.write_text(json.dumps(data), encoding="utf-8")
    assert cache.get_cached_entry("demo", fingerprint) is None
    assert cache.config_fingerprint({**config, "command": "other"}) != fingerprint


def test_valid_lazy_cache_registers_schema_without_starting_server(tmp_path, monkeypatch):
    from tools import mcp_schema_cache as cache
    from tools import mcp_tool

    path = tmp_path / "mcp-schema-cache.json"
    monkeypatch.setattr(cache, "_cache_path", lambda: path)
    server_name = "lazy_cache_acceptance"
    tool_name = f"mcp_{server_name}_lookup"
    config = {"command": "fake-server", "lazy": True, "timeout": 3}
    cache.write_cache_entry(
        server_name,
        cache.config_fingerprint(config),
        tools=[
            {
                "name": "lookup",
                "description": "Lookup an item",
                "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}}},
                "annotations": {"readOnlyHint": True},
            }
        ],
    )
    monkeypatch.setattr(mcp_tool, "_MCP_AVAILABLE", True)
    monkeypatch.setattr(
        mcp_tool,
        "_ensure_mcp_loop",
        lambda: (_ for _ in ()).throw(AssertionError("lazy cache must not start MCP")),
    )
    mcp_tool._servers.pop(server_name, None)
    mcp_tool._lazy_server_configs.pop(server_name, None)

    try:
        names = mcp_tool.register_mcp_servers({server_name: config})
        assert tool_name in names
        assert server_name not in mcp_tool._servers
        assert server_name in mcp_tool._lazy_server_configs
        entry = registry.get_entry(tool_name)
        assert entry is not None
        assert entry.schema["parameters"]["properties"]["id"]["type"] == "string"
        assert registry.get_max_result_size(tool_name) == 50_000
    finally:
        registry.deregister(tool_name)
        mcp_tool._lazy_server_configs.pop(server_name, None)
        mcp_tool._lazy_server_fingerprints.pop(server_name, None)
        mcp_tool._lazy_server_tool_names.pop(server_name, None)
        mcp_tool._forget_mcp_tool_server(tool_name)


def test_first_invocation_connect_is_deduplicated(monkeypatch):
    from tools import mcp_tool

    server_name = "lazy_connect_acceptance"
    tool_name = f"mcp_{server_name}_lookup"
    config = {"command": "fake-server", "lazy": True, "connect_timeout": 2}
    calls = []

    async def discover(name, received):
        calls.append((name, received))
        server = mcp_tool.MCPServerTask(name)
        server.session = object()
        server._registered_tool_names = [tool_name]
        mcp_tool._servers[name] = server
        return [tool_name]

    def run_on_loop(factory, timeout):
        return asyncio.run(factory())

    monkeypatch.setattr(mcp_tool, "_discover_and_register_server", discover)
    monkeypatch.setattr(mcp_tool, "_ensure_mcp_loop", lambda: None)
    monkeypatch.setattr(mcp_tool, "_run_on_mcp_loop", run_on_loop)
    mcp_tool._lazy_server_configs[server_name] = config
    mcp_tool._lazy_server_tool_names[server_name] = [tool_name]
    mcp_tool._servers.pop(server_name, None)

    try:
        assert mcp_tool._ensure_lazy_server_connected(server_name) is True
        assert mcp_tool._ensure_lazy_server_connected(server_name) is True
        assert len(calls) == 1
    finally:
        mcp_tool._servers.pop(server_name, None)
        mcp_tool._lazy_server_configs.pop(server_name, None)
        mcp_tool._lazy_server_fingerprints.pop(server_name, None)
        mcp_tool._lazy_server_tool_names.pop(server_name, None)
