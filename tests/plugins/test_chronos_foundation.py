from __future__ import annotations

import importlib.util
from pathlib import Path


def _chronos():
    path = Path(__file__).resolve().parents[2] / "plugins/cron_providers/chronos/__init__.py"
    spec = importlib.util.spec_from_file_location("optional_chronos", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_chronos_inert_without_config(monkeypatch):
    for key in ("CHRONOS_ENDPOINT", "OMNI_PORTAL_URL", "CHRONOS_CALLBACK_URL", "CHRONOS_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    assert _chronos().ChronosCronProvider().check_requirements() is False


def test_chronos_reconcile_is_idempotent_and_mocked(monkeypatch):
    monkeypatch.setenv("CHRONOS_ENDPOINT", "https://scheduler.invalid")
    monkeypatch.setenv("CHRONOS_CALLBACK_URL", "https://agent.invalid")
    calls = []
    provider = _chronos().ChronosCronProvider(lambda action, payload: calls.append((action, payload)) or {"ok": True})
    jobs = [{"id": "j1", "next_run_at": "2026-08-16T12:00:00Z", "enabled": True}]
    provider.reconcile(jobs); provider.reconcile(jobs)
    assert [call[0] for call in calls] == ["cron/provision"]
    assert calls[0][1]["idempotency_key"] == "j1:2026-08-16T12:00:00Z"
    provider.reconcile([])
    assert calls[-1] == ("cron/cancel", {"job_id": "j1"})
