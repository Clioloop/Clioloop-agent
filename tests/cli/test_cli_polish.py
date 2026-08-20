"""Focused regression tests for the classic CLI polish surfaces."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from cli import ClioCLI


def _bare_cli() -> ClioCLI:
    cli_obj = ClioCLI.__new__(ClioCLI)
    cli_obj.config = {}
    cli_obj.console = MagicMock()
    cli_obj.agent = None
    cli_obj.conversation_history = []
    cli_obj.session_id = "session-123"
    cli_obj._pending_input = MagicMock()
    return cli_obj


def test_status_reports_effective_runtime_fields():
    cli_obj = _bare_cli()
    console = MagicMock()
    cli_obj.console = console
    cli_obj.agent = SimpleNamespace(
        model="openai/gpt-5.4-mini",
        reasoning_config={"enabled": True, "effort": "high"},
        session_total_tokens=321,
        session_api_calls=4,
    )
    cli_obj.model = "openai/gpt-5.4"
    cli_obj.provider = "openai"
    cli_obj.show_reasoning = True
    cli_obj.session_start = datetime(2026, 4, 9, 19, 24)
    cli_obj._agent_running = False
    cli_obj._session_db = MagicMock()
    cli_obj._session_db.get_session.return_value = None
    cli_obj._get_status_bar_snapshot = MagicMock(return_value={
        "context_tokens": 80_000,
        "context_length": 100_000,
        "context_percent": 80,
    })
    cli_obj._is_session_yolo_active = MagicMock(return_value=False)

    with (
        patch("cli.display_clio_home", return_value="~/.clio"),
        patch("tools.approval._get_approval_mode", return_value="smart"),
    ):
        cli_obj._show_session_status()

    output = "\n".join(str(call.args[0]) for call in console.print.call_args_list)
    assert "Model: openai/gpt-5.4-mini (OpenRouter)" in output
    assert "Reasoning: high (display: on)" in output
    assert "Approvals: smart" in output
    assert "Context: 20% left · 80,000 / 100,000 tokens used" in output


def test_help_command_forwards_filter_argument():
    cli_obj = _bare_cli()

    with patch.object(cli_obj, "show_help") as show_help:
        cli_obj.process_command("/help Reasoning")

    show_help.assert_called_once_with("Reasoning")


def test_help_filter_only_renders_matching_commands():
    cli_obj = _bare_cli()
    cli_obj._command_available = MagicMock(return_value=True)
    rendered: list[str] = []
    chat_console = MagicMock()
    chat_console.print.side_effect = lambda value, **_kwargs: rendered.append(str(value))

    with (
        patch("cli._cprint", side_effect=lambda value: rendered.append(str(value))),
        patch("cli.ChatConsole", return_value=chat_console),
        patch("cli._ensure_skill_commands", return_value={}),
        patch("cli.get_skill_bundles", return_value={}),
    ):
        cli_obj.show_help("reasoning")

    output = "\n".join(rendered)
    assert "/reasoning" in output
    assert "/model" not in output
    assert "Filtered by 'reasoning'" in output


def test_help_skills_lists_installed_skill_commands():
    cli_obj = _bare_cli()
    rendered: list[str] = []
    chat_console = MagicMock()
    chat_console.print.side_effect = lambda value, **_kwargs: rendered.append(str(value))
    skills = {
        "/review-pr": {"description": "Review a pull request"},
    }

    with (
        patch("cli._cprint", side_effect=lambda value: rendered.append(str(value))),
        patch("cli.ChatConsole", return_value=chat_console),
        patch("cli._ensure_skill_commands", return_value=skills),
    ):
        cli_obj.show_help("skills")

    output = "\n".join(rendered)
    assert "Skill Commands" in output
    assert "/review-pr" in output
    assert "Review a pull request" in output
