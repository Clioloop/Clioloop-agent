"""Audit log for dashboard-auth events.

Profile-aware location: ``$CLIO_HOME/logs/dashboard-auth.log``.
Format: one JSON object per line. Token-like kwargs are dropped before
serialisation so we never leak refresh tokens or JWTs to disk.
"""
from __future__ import annotations

import json
import pytest

from clio_cli.dashboard_auth.audit import audit_log, AuditEvent


@pytest.fixture
def profile_home(tmp_path, monkeypatch):
    """Redirect $CLIO_HOME and ~ to a tmp dir for the duration of the test."""
    home = tmp_path / ".clio"
    home.mkdir()
    monkeypatch.setenv("CLIO_HOME", str(home))
    # Some code paths fall back to Path.home() — patch that too.
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    return home


def test_audit_writes_jsonlines(profile_home):
    audit_log(AuditEvent.LOGIN_START, provider="managed", ip="1.2.3.4")
    audit_log(
        AuditEvent.LOGIN_SUCCESS,
        provider="managed", user_id="u1",
        email="a@b.com", ip="1.2.3.4",
    )

    path = profile_home / "logs" / "dashboard-auth.log"
    assert path.exists(), f"audit log not created at {path}"
    lines = path.read_text().strip().splitlines()
    assert len(lines) == 2

    second = json.loads(lines[1])
    assert second["event"] == "login_success"
    assert second["provider"] == "managed"
    assert second["user_id"] == "u1"
    assert second["email"] == "a@b.com"
    assert "ts" in second  # ISO-8601 timestamp


def test_audit_redacts_token_like_fields(profile_home):
    audit_log(
        AuditEvent.LOGIN_SUCCESS,
        provider="managed", access_token="should-not-appear",
        refresh_token="also-not", code="not-this", state="nope",
    )
    raw = (profile_home / "logs" / "dashboard-auth.log").read_text()
    for forbidden in ("should-not-appear", "also-not", "not-this", "nope"):
        assert forbidden not in raw, f"token-like value leaked into audit log: {forbidden}"


def test_audit_all_event_types_have_string_values():
    for ev in AuditEvent:
        assert isinstance(ev.value, str)
        assert ev.value


def test_audit_write_failure_does_not_raise(monkeypatch, tmp_path):
    """A broken audit log must not crash auth."""
    # Point CLIO_HOME at a file (not a dir) so mkdir/open will fail.
    broken = tmp_path / "not-a-dir"
    broken.write_text("blocking file")
    monkeypatch.setenv("CLIO_HOME", str(broken))
    # Should NOT raise.
    audit_log(AuditEvent.LOGIN_FAILURE, provider="managed", reason="x")


def test_audit_creates_logs_dir_if_missing(tmp_path, monkeypatch):
    home = tmp_path / ".clio"
    home.mkdir()
    monkeypatch.setenv("CLIO_HOME", str(home))
    # logs/ deliberately does not exist
    audit_log(AuditEvent.LOGIN_START, provider="managed")
    assert (home / "logs").is_dir()
    assert (home / "logs" / "dashboard-auth.log").exists()
