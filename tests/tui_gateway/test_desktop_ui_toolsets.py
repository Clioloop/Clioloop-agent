from unittest.mock import patch

from tui_gateway import server


def test_desktop_surface_injects_desktop_ui_toolset(monkeypatch):
    monkeypatch.setenv("CLIO_DESKTOP", "1")
    monkeypatch.delenv("CLIO_TUI_TOOLSETS", raising=False)
    with (
        patch("clio_cli.config.load_config", return_value={}),
        patch("clio_cli.tools_config._get_platform_tools", return_value={"file", "terminal"}),
    ):
        enabled = server._load_enabled_toolsets()
    assert enabled is not None
    assert "desktop_ui" in enabled
    assert "file" in enabled


def test_plain_tui_does_not_pay_desktop_schema(monkeypatch):
    monkeypatch.delenv("CLIO_DESKTOP", raising=False)
    monkeypatch.delenv("CLIO_TUI_TOOLSETS", raising=False)
    with (
        patch("clio_cli.config.load_config", return_value={}),
        patch("clio_cli.tools_config._get_platform_tools", return_value={"file", "terminal"}),
    ):
        enabled = server._load_enabled_toolsets()
    assert enabled is not None
    assert "desktop_ui" not in enabled


def test_ui_runtime_id_resolves_from_durable_session_key():
    original = dict(server._sessions)
    try:
        server._sessions.clear()
        server._sessions["runtime-a"] = {"session_key": "stored-a"}
        assert server._ui_sid_for_session_key("stored-a") == "runtime-a"
        assert server._ui_sid_for_session_key("runtime-a") == "runtime-a"
        assert server._ui_sid_for_session_key("missing") == ""
    finally:
        server._sessions.clear()
        server._sessions.update(original)
