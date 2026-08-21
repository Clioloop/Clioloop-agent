"""Bot child stdout must contain only the finalized reply payload."""

from types import SimpleNamespace

import cli
import clio_bot_mode
from cli import _install_bot_child_tool_progress, _reasoning_display_enabled


def test_reasoning_display_follows_config_for_normal_cli(monkeypatch):
    monkeypatch.delenv("CLIO_BOT_CHILD", raising=False)

    assert _reasoning_display_enabled(True) is True
    assert _reasoning_display_enabled(False) is False


def test_reasoning_display_is_forced_off_for_bot_child(monkeypatch):
    monkeypatch.setenv("CLIO_BOT_CHILD", "1")

    assert _reasoning_display_enabled(True) is False


def test_bot_child_cli_never_registers_reasoning_renderer(monkeypatch):
    monkeypatch.setenv("CLIO_BOT_CHILD", "1")
    monkeypatch.setitem(cli.CLI_CONFIG["display"], "show_reasoning", True)

    shell = cli.ClioCLI(compact=True)
    shell.verbose = True

    assert shell.show_reasoning is False
    assert shell._current_reasoning_callback() is None


def test_bot_child_tool_progress_callback_emits_tools_but_not_reasoning(monkeypatch, tmp_path):
    event_path = tmp_path / "events.jsonl"
    event_path.write_bytes(b"")
    monkeypatch.setenv("CLIO_BOT_CHILD", "1")
    monkeypatch.setenv("CLIO_BOT_EVENT_PATH", str(event_path))
    monkeypatch.setenv("CLIO_BOT_EVENT_TOKEN", "token")
    agent = SimpleNamespace(
        tool_progress_callback=None,
        tool_start_callback=object(),
        tool_complete_callback=object(),
    )

    assert _install_bot_child_tool_progress(agent) is True
    agent.tool_progress_callback("reasoning.available", "_thinking", "private", None)
    agent.tool_progress_callback("tool.started", "search_files", "preview", {"path": "/private"})
    agent.tool_progress_callback(
        "tool.completed",
        "search_files",
        None,
        None,
        duration=3.0,
        is_error=False,
        result="private result",
    )

    events, _ = clio_bot_mode._drain_bot_child_events(event_path, "token", 0)
    assert events == [
        {"event": "tool.started", "name": "search_files"},
        {
            "event": "tool.completed",
            "name": "search_files",
            "duration": 3.0,
            "is_error": False,
        },
    ]
    assert agent.tool_start_callback is None
    assert agent.tool_complete_callback is None
