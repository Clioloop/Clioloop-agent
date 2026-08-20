from __future__ import annotations

import os
import subprocess
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from clio_cli import config
from clio_cli import main as cli_main
from clio_cli import process_identity as identity


class _NoSuchProcess(Exception):
    pass


def _holder(
    pid: int,
    create_time: float,
    purpose: str | None,
    reapable: bool,
    reason: str,
) -> identity.HolderClassification:
    return identity.HolderClassification(pid, create_time, purpose, reapable, reason)


def test_console_shim_parent_is_detected(monkeypatch, tmp_path):
    shim = tmp_path / "clio.exe"
    shim.write_bytes(b"")

    class Parent:
        def exe(self):
            return str(shim)

    class Current:
        def parent(self):
            return Parent()

    fake_psutil = types.SimpleNamespace(Process=lambda pid: Current())
    monkeypatch.setitem(sys.modules, "psutil", fake_psutil)
    monkeypatch.setattr(cli_main, "_is_windows", lambda: True)
    monkeypatch.setattr(cli_main, "_venv_scripts_dir", lambda: tmp_path)
    monkeypatch.setattr(cli_main, "_clio_exe_shims", lambda scripts: [shim])

    assert cli_main._current_install_venv_console_shim() == shim


def test_shim_holder_probe_uses_executable_path_and_creation_time(monkeypatch, tmp_path):
    shim = tmp_path / "clio.exe"
    shim.write_bytes(b"")
    matching = SimpleNamespace(
        info={"pid": 4242, "exe": str(shim), "name": "clio.exe", "create_time": 123.5}
    )
    unrelated = SimpleNamespace(
        info={
            "pid": 4243,
            "exe": str(tmp_path / "python.exe"),
            "name": "python.exe",
            "create_time": 124.5,
        }
    )
    fake_psutil = types.SimpleNamespace(
        process_iter=lambda attrs: iter([matching, unrelated]),
        NoSuchProcess=_NoSuchProcess,
    )
    monkeypatch.setitem(sys.modules, "psutil", fake_psutil)
    monkeypatch.setattr(cli_main, "_is_windows", lambda: True)
    monkeypatch.setattr(cli_main, "_clio_exe_shims", lambda scripts: [shim])

    assert cli_main._probe_windows_clio_shim_holders(tmp_path) == [
        (4242, 123.5, "clio.exe")
    ]


def test_lazy_process_enumeration_error_is_not_a_partial_roster(monkeypatch, tmp_path):
    shim = tmp_path / "clio.exe"
    shim.write_bytes(b"")

    def rows():
        yield SimpleNamespace(
            info={"pid": 4242, "exe": str(shim), "name": "clio.exe", "create_time": 123.5}
        )
        raise PermissionError("enumeration denied")

    fake_psutil = types.SimpleNamespace(
        process_iter=lambda attrs: rows(),
        NoSuchProcess=_NoSuchProcess,
    )
    monkeypatch.setitem(sys.modules, "psutil", fake_psutil)
    monkeypatch.setattr(cli_main, "_is_windows", lambda: True)
    monkeypatch.setattr(cli_main, "_clio_exe_shims", lambda scripts: [shim])

    with pytest.raises(cli_main._WindowsUpdateProbeError, match="enumerate"):
        cli_main._probe_windows_clio_shim_holders(tmp_path)


def test_handoff_marks_one_worker_and_uses_current_checkout(monkeypatch, tmp_path):
    shim = tmp_path / "venv" / "Scripts" / "clio.exe"
    checkout = tmp_path / "checkout"
    calls = []
    monkeypatch.setattr(cli_main, "PROJECT_ROOT", checkout)
    monkeypatch.setattr(cli_main, "_current_install_venv_console_shim", lambda: shim)
    monkeypatch.setattr(cli_main.sys, "argv", ["clio", "update", "--yes"])
    monkeypatch.delenv(cli_main._UPDATE_SYNC_REEXEC_ENV, raising=False)
    monkeypatch.setattr(cli_main.subprocess, "Popen", lambda *args, **kwargs: calls.append((args, kwargs)))

    assert cli_main._handoff_windows_update_from_console_shim() is True
    args, kwargs = calls[0]
    assert args[0] == [sys.executable, "-m", "clio_cli.main", "update", "--yes"]
    assert kwargs["cwd"] == checkout
    assert kwargs["env"][cli_main._UPDATE_SYNC_REEXEC_ENV] == "1"
    assert cli_main._UPDATE_SYNC_REEXEC_ENV not in os.environ


def test_sync_reexec_marker_is_consumed_without_recursion(monkeypatch):
    wait = MagicMock()
    handoff = MagicMock(return_value=True)
    implementation = MagicMock()
    monkeypatch.setattr(config, "is_managed", lambda: False)
    monkeypatch.setattr(config, "detect_install_method", lambda root: "git")
    monkeypatch.setattr(cli_main, "_is_windows", lambda: True)
    monkeypatch.setattr(cli_main, "_wait_for_windows_update_handoff_parent", wait)
    monkeypatch.setattr(cli_main, "_handoff_windows_update_from_console_shim", handoff)
    monkeypatch.setattr(cli_main, "_install_hangup_protection", lambda gateway_mode: {})
    monkeypatch.setattr(cli_main, "_finalize_update_output", lambda state: None)
    monkeypatch.setattr(cli_main, "_cmd_update_impl", implementation)
    monkeypatch.setenv(cli_main._UPDATE_SYNC_REEXEC_ENV, "1")
    args = SimpleNamespace(check=False, gateway=False)

    cli_main.cmd_update(args)

    wait.assert_called_once_with()
    handoff.assert_not_called()
    implementation.assert_called_once_with(args, gateway_mode=False)
    assert cli_main._UPDATE_SYNC_REEXEC_ENV not in os.environ


def test_prepare_reaps_ledger_classified_orphan_only(monkeypatch, tmp_path):
    orphan = _holder(50, 500.0, "gateway", True, "spawner is dead")
    probes = iter([[(50, 500.0, "clio-gateway.exe")], []])
    run = MagicMock(return_value=subprocess.CompletedProcess([], 0, "", ""))
    monkeypatch.setattr(cli_main, "_is_windows", lambda: True)
    monkeypatch.setattr(cli_main, "_venv_scripts_dir", lambda: tmp_path)
    monkeypatch.setattr(cli_main, "_probe_windows_clio_shim_holders", lambda scripts: next(probes))
    monkeypatch.setattr(identity, "classify_update_holders", lambda holders, project_root: [orphan])
    monkeypatch.setattr(identity, "process_identity_matches", lambda pid, create: True)
    monkeypatch.setattr(cli_main.subprocess, "run", run)

    cli_main._prepare_windows_dependency_sync()

    run.assert_called_once_with(
        ["taskkill", "/PID", "50", "/F"],
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_mixed_orphan_and_unknown_holder_fails_closed(monkeypatch, tmp_path, capsys):
    orphan = _holder(50, 500.0, "serve", True, "spawner is dead")
    unknown = _holder(60, 600.0, None, False, "no matching ledger identity")
    probes = iter(
        [
            [(50, 500.0, "clio.exe"), (60, 600.0, "clio.exe")],
            [(60, 600.0, "clio.exe")],
        ]
    )
    classifications = iter([[orphan, unknown], [unknown]])
    run = MagicMock(return_value=subprocess.CompletedProcess([], 0, "", ""))
    monkeypatch.setattr(cli_main, "_is_windows", lambda: True)
    monkeypatch.setattr(cli_main, "_venv_scripts_dir", lambda: tmp_path)
    monkeypatch.setattr(cli_main, "_probe_windows_clio_shim_holders", lambda scripts: next(probes))
    monkeypatch.setattr(
        identity,
        "classify_update_holders",
        lambda holders, project_root: next(classifications),
    )
    monkeypatch.setattr(identity, "process_identity_matches", lambda pid, create: True)
    monkeypatch.setattr(cli_main.subprocess, "run", run)

    with pytest.raises(SystemExit) as excinfo:
        cli_main._prepare_windows_dependency_sync()

    assert excinfo.value.code == 2
    assert run.call_args.args[0] == ["taskkill", "/PID", "50", "/F"]
    assert "PID 60" in capsys.readouterr().out


def test_unknown_holder_alone_fails_closed_without_taskkill(monkeypatch, tmp_path):
    unknown = _holder(60, 600.0, None, False, "no matching ledger identity")
    monkeypatch.setattr(cli_main, "_is_windows", lambda: True)
    monkeypatch.setattr(cli_main, "_venv_scripts_dir", lambda: tmp_path)
    monkeypatch.setattr(
        cli_main,
        "_probe_windows_clio_shim_holders",
        lambda scripts: [(60, 600.0, "clio.exe")],
    )
    monkeypatch.setattr(
        identity, "classify_update_holders", lambda holders, project_root: [unknown]
    )
    run = MagicMock()
    monkeypatch.setattr(cli_main.subprocess, "run", run)

    with pytest.raises(SystemExit) as excinfo:
        cli_main._prepare_windows_dependency_sync()

    assert excinfo.value.code == 2
    run.assert_not_called()


def test_probe_error_fails_closed_with_exit_two(monkeypatch, tmp_path):
    monkeypatch.setattr(cli_main, "_is_windows", lambda: True)
    monkeypatch.setattr(cli_main, "_venv_scripts_dir", lambda: tmp_path)
    monkeypatch.setattr(
        cli_main,
        "_probe_windows_clio_shim_holders",
        MagicMock(side_effect=cli_main._WindowsUpdateProbeError("access denied")),
    )

    with pytest.raises(SystemExit) as excinfo:
        cli_main._prepare_windows_dependency_sync()

    assert excinfo.value.code == 2


def test_dependency_install_runs_from_current_checkout(monkeypatch, tmp_path):
    run = MagicMock(return_value=subprocess.CompletedProcess([], 0))
    monkeypatch.setattr(cli_main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(cli_main.subprocess, "run", run)

    cli_main._run_install_with_heartbeat(["uv", "pip", "install", "-e", ".[all]"])

    assert run.call_args.kwargs["cwd"] == tmp_path
