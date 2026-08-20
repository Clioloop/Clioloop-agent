from __future__ import annotations

import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

from clio_cli import process_identity as identity


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "v1:-:serve:12:100.0",
        "v1:abcdef123456:bad purpose:12:100.0",
        "v1:abcdef123456:serve:0:100.0",
        "v1:abcdef123456:serve:12:nan",
        "v2:abcdef123456:serve:12:100.0",
    ],
)
def test_parse_spawn_tag_rejects_incomplete_or_malformed_identity(raw):
    assert identity.parse_spawn_tag(raw) is None


def test_build_and_parse_spawn_tag_round_trip(monkeypatch, tmp_path):
    monkeypatch.setattr(identity, "_own_create_time", lambda: 1234.56789)
    monkeypatch.setattr(identity.os, "getpid", lambda: 42)

    raw = identity.build_spawn_tag("gateway", project_root=tmp_path)
    parsed = identity.parse_spawn_tag(raw)

    assert parsed == identity.SpawnTag(
        install=identity.install_id(tmp_path),
        purpose="gateway",
        spawner_pid=42,
        spawner_create=1234.568,
    )


def test_interprocess_lock_excludes_a_second_process(tmp_path):
    ledger = tmp_path / "spawn-ledger.json"
    code = """
import sys
from pathlib import Path
from clio_cli import process_identity as identity
identity._LOCK_TIMEOUT_SECONDS = 0.15
with identity._interprocess_lock(Path(sys.argv[1])) as locked:
    print(locked)
"""

    with identity._interprocess_lock(ledger) as locked:
        assert locked is True
        child = subprocess.run(
            [sys.executable, "-c", code, str(ledger)],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        assert child.stdout.strip() == "False"

    with identity._interprocess_lock(ledger) as locked_again:
        assert locked_again is True


def _entry(**overrides):
    entry = {
        "pid": 10,
        "create_time": 100.0,
        "purpose": "serve",
        "install": "abcdef123456",
        "profile": "123456abcdef",
        "spawner_pid": 9,
        "spawner_create": 90.0,
        "registered_at": 101.0,
        "argv": "clio serve",
    }
    entry.update(overrides)
    return entry


def test_ledger_validation_rejects_bool_numeric_fields():
    assert identity._valid_ledger_entry(_entry()) is True
    assert identity._valid_ledger_entry(_entry(spawner_pid=True)) is False
    assert identity._valid_ledger_entry(_entry(registered_at=True)) is False


@pytest.mark.parametrize("corrupt", ["", "{not-json", "{}"])
def test_register_quarantines_corrupt_or_truncated_ledger(monkeypatch, tmp_path, corrupt):
    ledger = tmp_path / "spawn-ledger.json"
    ledger.write_text(corrupt, encoding="utf-8")
    monkeypatch.setattr(identity, "_ledger_path", lambda project_root=None: ledger)
    monkeypatch.setattr(identity, "_own_create_time", lambda: 200.0)
    monkeypatch.setattr(identity, "install_id", lambda project_root=None: "abcdef123456")
    monkeypatch.setattr(identity, "profile_id", lambda profile_home=None: "123456abcdef")
    monkeypatch.setattr(identity, "_parent_identity", lambda: (9, 90.0))

    assert identity.register_self("serve", project_root=tmp_path) is True

    parked = list(tmp_path.glob("spawn-ledger.json.corrupt-*"))
    assert len(parked) == 1
    assert parked[0].read_text(encoding="utf-8") == corrupt
    entries = json.loads(ledger.read_text(encoding="utf-8"))
    assert len(entries) == 1
    assert entries[0]["purpose"] == "serve"
    assert entries[0]["create_time"] == 200.0


def test_ledger_entries_requires_positive_pid_create_time_match(monkeypatch, tmp_path):
    ledger = tmp_path / "spawn-ledger.json"
    ledger.write_text(
        json.dumps([_entry(pid=10), _entry(pid=11), _entry(pid=12)]),
        encoding="utf-8",
    )
    seen_roots = []
    monkeypatch.setattr(identity, "_ledger_path", lambda project_root=None: seen_roots.append(project_root) or ledger)
    monkeypatch.setattr(identity, "install_id", lambda project_root=None: "abcdef123456")
    monkeypatch.setattr(
        identity,
        "process_identity_matches",
        lambda pid, create_time, **kwargs: {10: True, 11: False, 12: None}[pid],
    )

    assert [entry["pid"] for entry in identity.ledger_entries(project_root=tmp_path)] == [10]
    assert seen_roots == [tmp_path]


def test_process_identity_matches_create_time_and_fails_closed(monkeypatch):
    class NoSuchProcess(Exception):
        pass

    class Proc:
        def __init__(self, pid):
            if pid == 404:
                raise NoSuchProcess()
            self.pid = pid

        def create_time(self):
            if self.pid == 13:
                raise PermissionError("denied")
            if self.pid == 14:
                return float("nan")
            return 100.0

    fake_psutil = types.SimpleNamespace(Process=Proc, NoSuchProcess=NoSuchProcess)
    monkeypatch.setitem(sys.modules, "psutil", fake_psutil)

    assert identity.process_identity_matches(10, 100.02) is True
    assert identity.process_identity_matches(10, 101.0) is False
    assert identity.process_identity_matches(404, 100.0) is False
    assert identity.process_identity_matches(13, 100.0) is None
    assert identity.process_identity_matches(14, 100.0) is None
    assert identity.process_identity_matches(10, 100.0, tolerance=-1) is None


def test_windows_job_attachment_is_idempotent(monkeypatch):
    calls = {"create": 0, "assign": 0, "close": 0}

    class FakeFunction:
        def __init__(self, fn):
            self.fn = fn

        def __call__(self, *args):
            return self.fn(*args)

    class FakeKernel32:
        def __init__(self):
            self.CreateJobObjectW = FakeFunction(self._create)
            self.SetInformationJobObject = FakeFunction(lambda *args: 1)
            self.AssignProcessToJobObject = FakeFunction(self._assign)
            self.GetCurrentProcess = FakeFunction(lambda: 456)
            self.CloseHandle = FakeFunction(self._close)

        def _create(self, *args):
            calls["create"] += 1
            return 123

        def _assign(self, *args):
            calls["assign"] += 1
            return 1

        def _close(self, *args):
            calls["close"] += 1
            return 1

    import ctypes

    monkeypatch.setattr(identity, "_IS_WINDOWS", True)
    monkeypatch.setattr(identity, "_JOB_HANDLE", None)
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: FakeKernel32(), raising=False)

    assert identity.attach_self_to_kill_on_close_job() is True
    assert identity.attach_self_to_kill_on_close_job() is True
    assert calls == {"create": 1, "assign": 1, "close": 0}
