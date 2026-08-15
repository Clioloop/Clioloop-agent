from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from clio_cli import observability as obs
from clio_cli.operations import collect_health, diagnose_database, support_bundle_data


class CaptureExporter:
    def __init__(self) -> None:
        self.records = []
        self.closed = False

    def export(self, records):
        self.records.extend(records)

    def shutdown(self):
        self.closed = True


def test_observability_is_noop_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("CLIO_OBSERVABILITY_ENABLED", raising=False)
    monkeypatch.setenv("CLIO_OBSERVABILITY_PATH", str(tmp_path / "events.jsonl"))
    obs.reset_for_tests()
    obs.event("agent.turn", attributes={"anything": "value"})
    with obs.span("tool.call", kind="tool", tool_name="terminal"):
        pass
    assert not (tmp_path / "events.jsonl").exists()


def test_span_contract_correlation_and_redaction(monkeypatch):
    monkeypatch.setenv("CLIO_OBSERVABILITY_ENABLED", "1")
    obs.reset_for_tests()
    exporter = CaptureExporter()
    obs.set_exporter(exporter)

    with obs.correlation(session_id="session-1", turn_id="turn-2", gateway_id="telegram"):
        with obs.span(
            "model.request",
            kind="model",
            model="example-model",
            attributes={
                "prompt": "do not store this",
                "api_key": "sk-super-secret-value-1234567890",
                "safe": "retry-1",
            },
        ):
            obs.event("model.first_token", tool_name="search")

    spans = [r for r in exporter.records if r["record_type"] == "span"]
    events = [r for r in exporter.records if r["record_type"] == "event"]
    assert len(spans) == 1
    span = spans[0]
    assert len(span["correlation"]["trace_id"]) == 32
    assert len(span["correlation"]["span_id"]) == 16
    assert span["correlation"]["session_id"] == "session-1"
    assert span["correlation"]["turn_id"] == "turn-2"
    assert span["correlation"]["model"] == "example-model"
    assert span["attributes"]["prompt"] == "[REDACTED]"
    assert span["attributes"]["api_key"] == "[REDACTED]"
    assert span["attributes"]["safe"] == "retry-1"
    correlated = next(r for r in events if r["name"] == "model.first_token")
    assert correlated["correlation"]["trace_id"] == span["correlation"]["trace_id"]
    assert correlated["correlation"]["tool_name"] == "search"


def test_instrument_decorator_records_failures_without_swallowing(monkeypatch):
    monkeypatch.setenv("CLIO_OBSERVABILITY_ENABLED", "1")
    obs.reset_for_tests()
    exporter = CaptureExporter()
    obs.set_exporter(exporter)

    @obs.instrument("cron.execute", kind="cron")
    def fail(job_id=None):
        raise RuntimeError("token=supersecret")

    try:
        fail(job_id="job-9")
    except RuntimeError:
        pass
    else:
        raise AssertionError("observability changed exception behavior")
    record = next(r for r in exporter.records if r["record_type"] == "span")
    assert record["status"] == "error"
    assert record["correlation"]["cron_id"] == "job-9"
    assert record["error_type"] == "RuntimeError"
    assert "supersecret" not in json.dumps(record)


def test_correlation_values_are_force_redacted(monkeypatch):
    monkeypatch.setenv("CLIO_OBSERVABILITY_ENABLED", "1")
    obs.reset_for_tests()
    exporter = CaptureExporter()
    obs.set_exporter(exporter)

    obs.event("agent.turn", session_id="token=supersecret")

    payload = json.dumps(exporter.records)
    assert "supersecret" not in payload
    assert "[REDACTED]" in payload


def _make_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE records(id INTEGER PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO records(value) VALUES ('ok')")
    try:
        conn.execute("CREATE VIRTUAL TABLE records_fts USING fts5(value)")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


def test_database_wal_fts_lock_and_growth_diagnostics(tmp_path):
    db = tmp_path / "sessions.db"
    _make_db(db)
    result = diagnose_database(db, root=tmp_path)
    assert result["path"] == "sessions.db"
    assert result["readable"] is True
    assert result["lock_state"] == "readable"
    assert result["quick_check"] == "ok"
    assert result["journal_mode"] == "wal"
    assert result["page_count"] > 0
    assert result["freelist_count"] >= 0
    assert result["bytes"] > 0
    assert isinstance(result["wal_bytes"], int)
    assert isinstance(result["fts_tables"], list)


def test_health_and_support_bundle_are_json_safe_and_local(monkeypatch, tmp_path):
    monkeypatch.setenv("CLIO_HOME", str(tmp_path))
    monkeypatch.delenv("CLIO_OBSERVABILITY_ENABLED", raising=False)
    _make_db(tmp_path / "state.db")
    health = collect_health(tmp_path, live=True)
    assert health["mode"] == "live"
    assert health["storage"]["count"] == 1
    assert "memory" in health and "disk" in health and "resources" in health
    assert "processes" in health and "logs" in health
    assert health["observability"]["enabled"] is False
    bundle = support_bundle_data(tmp_path)
    assert bundle["storage"]["root"] == "<CLIO_HOME>"
    assert bundle["disk"]["path"] == "<CLIO_HOME>"
    json.dumps(bundle)
