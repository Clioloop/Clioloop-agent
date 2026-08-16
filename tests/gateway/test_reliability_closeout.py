import sqlite3

import pytest

from cron.contracts import CronBackend
from gateway.config import GatewayConfig
from gateway.delivery import DeliveryRouter, DeliveryTarget
from gateway.reliability import (
    OutboundWebhookDispatcher,
    ReliabilityStore,
    SignedWebhookQueue,
)


class FakeClock:
    def __init__(self, value=1000.0):
        self.value = value

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


def test_closeout_operator_apis_dispatch_and_retention_defaults(tmp_path):
    clock = FakeClock()
    store = ReliabilityStore(tmp_path / "reliability.db", clock=clock)
    queue = SignedWebhookQueue(store, "test-secret", clock=clock)

    item_id = queue.enqueue(
        "https://example.invalid/hook",
        {"event": "complete", "token": "do-not-expose"},
        idempotency_key="hook-1",
    )
    assert queue.dispatch_one(lambda *_: 503, max_attempts=1) is False
    listed = store.list_webhooks(status="dead", limit=5000)
    assert listed == [
        {
            "id": item_id,
            "idempotency_key": "hook-1",
            "url": "https://example.invalid/hook",
            "status": "dead",
            "attempts": 1,
            "available_at": 1001.0,
            "last_error": "HTTP 503",
            "created_at": 1000.0,
            "delivered_at": None,
        }
    ]
    assert "body" not in listed[0]

    assert store.retry_webhook(item_id)
    sent = []
    dispatcher = OutboundWebhookDispatcher(
        queue,
        sender=lambda url, body, headers: sent.append((url, body, headers)) or 204,
        batch_size=2,
    )
    assert dispatcher.flush(timeout=1) == {"processed": 1, "delivered": 1, "drained": True}
    assert len(sent) == 1
    assert store.list_webhooks(status="delivered")[0]["id"] == item_id
    assert dispatcher.drain(timeout=1)["drained"] is True
    assert dispatcher.notify() is False
    assert dispatcher.shutdown(timeout=1)["worker_stopped"] is True

    lease = store.acquire_turn_lease("expired", "worker", ttl=2)
    assert lease is not None
    second_id = queue.enqueue(
        "https://example.invalid/recover", {"event": "recover"}, idempotency_key="hook-2"
    )
    with store._transaction() as conn:
        conn.execute(
            "UPDATE outbound_webhooks SET status='sending', lease_owner='gone', lease_expires_at=? WHERE id=?",
            (clock() + 2, second_id),
        )
    clock.advance(3)
    assert store.recover_expired() == {"webhooks": 1, "turn_leases": 1}

    delivered = store.claim_delivery("old-delivered", "worker")
    failed = store.claim_delivery("old-failed", "worker")
    active = store.claim_delivery("active", "worker")
    assert store.complete_delivery(delivered)
    assert store.fail_delivery(failed, "failed")
    clock.advance(10)
    assert store.prune_delivery_ledger(delivered_before=clock(), failed_before=clock()) == 2
    with sqlite3.connect(store.path) as conn:
        assert conn.execute("SELECT delivery_key FROM delivery_ledger").fetchall() == [(active.key,)]

    cron = CronBackend(store=store)
    cron.set_retention("executions", max_age_seconds=60, max_records=7)
    cron.ensure_default_retention()
    cron.ensure_default_retention()
    with store._connect() as conn:
        policies = {
            row["record_type"]: (row["max_age_seconds"], row["max_records"])
            for row in conn.execute("SELECT * FROM cron_retention_policies")
        }
    assert policies == {
        "executions": (60.0, 7),
        "notepad": (30 * 86400.0, None),
        "webhooks": (14 * 86400.0, None),
    }


@pytest.mark.asyncio
async def test_delivery_router_ledger_deduplicates_by_target(tmp_path, monkeypatch):
    monkeypatch.setenv("CLIO_DELIVERY_RELIABILITY_ENABLED", "1")
    monkeypatch.setenv("CLIO_RELIABILITY_DB", str(tmp_path / "delivery.db"))
    monkeypatch.setattr("gateway.delivery.get_clio_home", lambda: tmp_path)
    router = DeliveryRouter(GatewayConfig())
    target = DeliveryTarget.parse("local")

    first = await router.deliver(
        "only once", [target], job_id="job", metadata={"idempotency_key": "cron:job:slot"}
    )
    duplicate = await router.deliver(
        "only once", [target], job_id="job", metadata={"idempotency_key": "cron:job:slot"}
    )

    assert first["local"]["success"] is True
    assert duplicate["local"] == {
        "success": True,
        "deduplicated": True,
        "in_progress": False,
    }
    assert router._reliability_store is not None
    with router._reliability_store._connect() as conn:
        row = conn.execute("SELECT status, attempts FROM delivery_ledger").fetchone()
    assert tuple(row) == ("delivered", 1)


def test_cron_tick_uses_pre_advance_slot_and_skips_duplicate(tmp_path, monkeypatch):
    import cron.contracts as contracts
    import cron.scheduler as scheduler

    class History:
        def __init__(self):
            self.keys = set()
            self.begun = []
            self.finished = []

        def begin_execution(self, job_id, *, idempotency_key, scheduled_at, metadata):
            self.begun.append((job_id, idempotency_key, scheduled_at, metadata))
            created = idempotency_key not in self.keys
            self.keys.add(idempotency_key)
            return "execution-1", created

        def finish_execution(self, execution_id, **kwargs):
            self.finished.append((execution_id, kwargs))

    history = History()
    runs = []
    deliveries = []

    monkeypatch.setattr(contracts, "integration_backend", lambda: history)
    monkeypatch.setattr(
        scheduler,
        "get_due_jobs",
        lambda: [{"id": "job-1", "name": "Job", "next_run_at": "2026-08-16T03:00:00Z"}],
    )
    monkeypatch.setattr(scheduler, "advance_next_run", lambda *_: None)
    monkeypatch.setattr(
        scheduler,
        "run_job",
        lambda job: runs.append(job.copy()) or (True, "output", "response", None),
    )
    monkeypatch.setattr(scheduler, "save_job_output", lambda *_: tmp_path / "output.md")
    monkeypatch.setattr(
        scheduler,
        "_deliver_result",
        lambda job, *_args, **_kwargs: deliveries.append(job.copy()) or None,
    )
    monkeypatch.setattr(scheduler, "mark_job_run", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(scheduler, "load_config", lambda: {})
    monkeypatch.setattr(
        scheduler,
        "_get_lock_paths",
        lambda: (tmp_path / "locks", tmp_path / "locks" / "tick.lock"),
    )

    assert scheduler.tick(verbose=False) == 1
    assert scheduler.tick(verbose=False) == 1
    assert len(runs) == 1
    assert history.begun[0][1:3] == (
        "cron:job-1:2026-08-16T03:00:00Z",
        "2026-08-16T03:00:00Z",
    )
    assert deliveries[0]["_reliability_delivery_key"] == history.begun[0][1]
    assert len(history.finished) == 1
