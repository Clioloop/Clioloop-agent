"""Bot child stdout must contain only the finalized reply payload."""

import cli
from cli import _reasoning_display_enabled


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
