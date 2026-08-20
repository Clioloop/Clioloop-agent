"""Focused regressions for destructive CLI/config safety behavior."""

import sys
from argparse import Namespace
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml


def _isolate_config(config, tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    monkeypatch.setattr(config, "is_managed", lambda: False)
    monkeypatch.setattr(config, "get_config_path", lambda: config_path)
    monkeypatch.setattr(config, "ensure_clio_home", lambda: None)
    return config_path


def test_config_set_coerces_by_schema_without_corrupting_string_enum(
    tmp_path, monkeypatch
):
    from clio_cli import config

    config_path = _isolate_config(config, tmp_path, monkeypatch)
    config.set_config_value("approvals.mode", "off")
    config.set_config_value("agent.max_turns", "-12")

    saved = yaml.safe_load(config_path.read_text())
    assert saved["approvals"]["mode"] == "off"
    assert saved["approvals"]["mode"] is not False
    assert saved["agent"]["max_turns"] == -12


@pytest.mark.parametrize(
    "key",
    ["", ".agent", "agent.", "agent..max_turns", " agent.max_turns", "agent. max_turns"],
)
def test_config_set_rejects_malformed_dotted_keys(key, tmp_path, monkeypatch):
    from clio_cli import config

    config_path = _isolate_config(config, tmp_path, monkeypatch)
    with pytest.raises(SystemExit) as exc:
        config.set_config_value(key, "1")
    assert exc.value.code == 1
    assert not config_path.exists()


def test_sessions_missing_target_exits_nonzero(tmp_path, monkeypatch, capsys):
    from clio_cli import main as main_module

    monkeypatch.setenv("CLIO_HOME", str(tmp_path / "clio"))
    monkeypatch.setattr(sys, "argv", ["clio", "sessions", "delete", "missing", "--yes"])
    monkeypatch.setattr(main_module, "_try_termux_fast_tui_launch", lambda: False)
    monkeypatch.setattr(main_module, "_try_termux_fast_cli_launch", lambda: False)

    with pytest.raises(SystemExit) as exc:
        main_module.main()
    assert exc.value.code == 1
    assert "not found" in capsys.readouterr().out


def test_backup_reports_parent_path_error_without_traceback(tmp_path, monkeypatch, capsys):
    from clio_cli import backup

    clio_home = tmp_path / "clio"
    clio_home.mkdir()
    (clio_home / "config.yaml").write_text("model: test\n")
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("file")
    monkeypatch.setattr(backup, "get_default_clio_root", lambda: clio_home)

    with pytest.raises(SystemExit) as exc:
        backup.run_backup(Namespace(output=str(blocker / "backup.zip")))
    assert exc.value.code == 1
    assert "Error: cannot write backup" in capsys.readouterr().out


def test_backup_reports_archive_open_error_and_removes_partial(tmp_path, monkeypatch, capsys):
    from clio_cli import backup

    clio_home = tmp_path / "clio"
    clio_home.mkdir()
    (clio_home / "config.yaml").write_text("model: test\n")
    output = tmp_path / "backup.zip"
    monkeypatch.setattr(backup, "get_default_clio_root", lambda: clio_home)

    with patch.object(backup.zipfile, "ZipFile", side_effect=PermissionError("denied")):
        with pytest.raises(SystemExit) as exc:
            backup.run_backup(Namespace(output=str(output)))
    assert exc.value.code == 1
    assert "Error: cannot create backup" in capsys.readouterr().out
    assert not output.exists()


def test_undo_empty_history_is_safe_noop(capsys):
    from cli import ClioCLI

    shell = SimpleNamespace(_pending_resume_sessions=None, conversation_history=[])
    result = ClioCLI.process_command(shell, "/undo")

    assert result is True
    assert "No messages to undo" in capsys.readouterr().out


def test_frozen_yolo_cannot_claim_to_disable_process_bypass(capsys):
    from cli import ClioCLI
    import tools.approval as approval

    session_id = "frozen-yolo-safety-test"
    approval.clear_session(session_id)
    try:
        with patch.object(approval, "_YOLO_MODE_FROZEN", True):
            ClioCLI._toggle_yolo(SimpleNamespace(session_id=session_id))
        assert approval.is_session_yolo_enabled(session_id) is False
        assert "locked ON" in capsys.readouterr().out
    finally:
        approval.clear_session(session_id)


def test_show_config_masks_live_agent_credential_not_stale_seed(capsys):
    from cli import ClioCLI

    shell = SimpleNamespace(
        api_key="stale-constructor-secret-0000",
        agent=SimpleNamespace(api_key="live-agent-secret-9999"),
        model="test-model",
        base_url="https://example.invalid/v1",
        max_turns=1,
        enabled_toolsets=[],
        verbose=False,
        session_start=datetime(2026, 1, 1),
    )
    ClioCLI.show_config(shell)
    output = capsys.readouterr().out

    assert "live-age...9999" in output
    assert "stale-co" not in output
    assert "live-agent-secret-9999" not in output