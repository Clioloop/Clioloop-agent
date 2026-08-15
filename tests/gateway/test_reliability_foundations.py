import hashlib
import hmac
import json
import threading
import time

from cron.contracts import CronBackend
from gateway.reliability import (
    DrainController,
    ReliabilityStore,
    RestartLoopGuard,
    SignedWebhookQueue,
    StallWatchdog,
    global_automation_paused,
)


class FakeClock:
    def __init__(self, value=1000.0):
        self.value = value

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


def test_turn_lease_reclaim_uses_fencing_and_rejects_stale_owner(tmp_path):
    clock = FakeClock()
    store = ReliabilityStore(tmp_path / "r.db", clock=clock)

    first = store.acquire_turn_lease("session:1", "worker-a", ttl=10)
    assert first is not None
    assert store.acquire_turn_lease("session:1", "worker-b", ttl=10) is None
    renewed = store.acquire_turn_lease("session:1", "worker-a", ttl=10)
    assert renewed is not None and renewed.token == first.token

    clock.advance(11)
    second = store.acquire_turn_lease("session:1", "worker-b", ttl=10)
    assert second is not None and second.token == first.token + 1
    assert store.renew_turn_lease(first, ttl=10) is None
    assert store.release_turn_lease(first) is False
    assert store.release_turn_lease(second) is True


def test_delivery_claim_is_idempotent_and_stale_completion_is_fenced(tmp_path):
    clock = FakeClock()
    store = ReliabilityStore(tmp_path / "r.db", clock=clock)

    first = store.claim_delivery("telegram:message:9", "a", ttl=5, payload="hello")
    assert first.acquired
    assert not store.claim_delivery("telegram:message:9", "b", ttl=5).acquired
    clock.advance(6)
    second = store.claim_delivery("telegram:message:9", "b", ttl=5)
    assert second.acquired and second.token > first.token
    assert store.complete_delivery(first) is False
    assert store.complete_delivery(second) is True

    duplicate = store.claim_delivery("telegram:message:9", "c")
    assert duplicate.acquired is False and duplicate.delivered is True


def test_failed_delivery_can_be_reclaimed_without_waiting_for_expiry(tmp_path):
    store = ReliabilityStore(tmp_path / "r.db")
    first = store.claim_delivery("d", "a")
    assert store.fail_delivery(first, "injected transport failure")
    second = store.claim_delivery("d", "b")
    assert second.acquired and second.token == first.token + 1


def test_global_pause_is_persisted_but_default_safe(tmp_path, monkeypatch):
    db = tmp_path / "r.db"
    monkeypatch.setenv("CLIO_RELIABILITY_DB", str(db))
    store = ReliabilityStore(db)
    store.set_paused(True, reason="maintenance", changed_by="test")

    monkeypatch.delenv("CLIO_RELIABILITY_CONTROL_ENABLED", raising=False)
    assert global_automation_paused() is False
    monkeypatch.setenv("CLIO_RELIABILITY_CONTROL_ENABLED", "true")
    assert global_automation_paused() is True
    store.set_paused(False)
    assert global_automation_paused() is False


def test_drain_readiness_wait_and_stall_watchdog():
    drain = DrainController()
    assert drain.begin("early") is None
    drain.set_ready(True)
    assert drain.begin("turn") == "turn"
    drain.start_drain("restart")
    assert drain.begin("late") is None

    finished = threading.Event()

    def complete():
        time.sleep(0.01)
        drain.finish("turn")
        finished.set()

    thread = threading.Thread(target=complete)
    thread.start()
    assert drain.wait_drained(1)
    thread.join()
    assert finished.is_set()
    assert drain.snapshot() == {"ready": False, "draining": True, "active": 0, "reason": "restart"}

    clock = FakeClock()
    watchdog = StallWatchdog(5, clock=clock)
    watchdog.heartbeat("turn", "waiting on provider")
    clock.advance(6)
    assert watchdog.stalled()[0]["key"] == "turn"
    watchdog.clear("turn")
    assert watchdog.stalled() == []


def test_restart_loop_guard_persists_window(tmp_path):
    clock = FakeClock()
    store = ReliabilityStore(tmp_path / "r.db", clock=clock)
    guard = RestartLoopGuard(store)
    assert guard.record_and_allow(max_restarts=2, window_seconds=30)
    assert guard.record_and_allow(max_restarts=2, window_seconds=30)
    assert guard.record_and_allow(max_restarts=2, window_seconds=30) is False
    clock.advance(31)
    assert guard.record_and_allow(max_restarts=2, window_seconds=30)


def test_webhook_failure_retry_hmac_redaction_and_enqueue_idempotency(tmp_path):
    clock = FakeClock()
    store = ReliabilityStore(tmp_path / "r.db", clock=clock)
    queue = SignedWebhookQueue(store, "signing-secret", clock=clock)
    item_id = queue.enqueue(
        "https://example.invalid/hook",
        {"event": "done", "api_key": "must-not-persist", "nested": {"token": "nope"}},
        idempotency_key="event-1",
    )
    assert queue.enqueue(
        "https://different.invalid/ignored", {"event": "other"}, idempotency_key="event-1"
    ) == item_id

    calls = []

    def failing_sender(url, body, headers):
        calls.append((url, body, headers))
        raise OSError("injected network failure")

    assert queue.dispatch_one(failing_sender, base_backoff=2) is False
    assert queue.dispatch_one(failing_sender, base_backoff=2) is None
    clock.advance(2)

    def successful_sender(url, body, headers):
        calls.append((url, body, headers))
        return 204

    assert queue.dispatch_one(successful_sender, base_backoff=2) is True
    assert queue.dispatch_one(successful_sender) is None
    _, body, headers = calls[-1]
    assert json.loads(body) == {
        "api_key": "[REDACTED]",
        "event": "done",
        "nested": {"token": "[REDACTED]"},
    }
    expected = hmac.new(
        b"signing-secret", headers["X-Clio-Timestamp"].encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    assert headers["X-Clio-Signature"] == "sha256=" + expected
    assert headers["Idempotency-Key"] == "event-1"


def test_cron_history_notepad_and_retention_contracts(tmp_path):
    clock = FakeClock()
    store = ReliabilityStore(tmp_path / "r.db", clock=clock)
    cron = CronBackend(store=store)

    execution_id, created = cron.begin_execution(
        "job-1", idempotency_key="job-1:scheduled:1", scheduled_at="2026-01-01T00:00:00Z"
    )
    duplicate_id, duplicate_created = cron.begin_execution(
        "job-1", idempotency_key="job-1:scheduled:1"
    )
    assert (duplicate_id, duplicate_created) == (execution_id, False)
    assert created and cron.finish_execution(execution_id, success=True, output_path="out.md")
    assert cron.finish_execution(execution_id, success=False) is False
    assert cron.execution_history("job-1")[0]["status"] == "ok"

    cron.put_note("monitor", "cursor", {"page": 3}, ttl=5)
    assert cron.get_note("monitor", "cursor") == {"page": 3}
    clock.advance(6)
    assert cron.get_note("monitor", "cursor", "missing") == "missing"

    cron.set_retention("executions", max_age_seconds=5)
    assert cron.apply_retention()["executions"] == 1
    assert cron.execution_history("job-1") == []
