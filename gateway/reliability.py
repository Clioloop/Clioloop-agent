"""Opt-in durable reliability primitives for gateway and automation workers.

The module is deliberately stdlib-only and has no import-time side effects.  Existing
execution paths remain unchanged unless ``CLIO_RELIABILITY_CONTROL_ENABLED`` (or a
more specific integration flag) is enabled.  SQLite transactions use BEGIN IMMEDIATE
so lease/claim decisions remain atomic across processes.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import os
import re
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Optional

_TRUE = {"1", "true", "yes", "on"}
_SECRET_KEY = re.compile(r"(?:secret|token|password|authorization|api[_-]?key|cookie)", re.I)


def feature_enabled(name: str = "CLIO_RELIABILITY_CONTROL_ENABLED") -> bool:
    return os.getenv(name, "").strip().lower() in _TRUE


def default_state_path() -> Path:
    override = os.getenv("CLIO_RELIABILITY_DB", "").strip()
    if override:
        return Path(override).expanduser()
    try:
        from clio_constants import get_clio_home

        return get_clio_home() / "reliability.db"
    except Exception:
        return Path.home() / ".clio" / "reliability.db"


@dataclass(frozen=True)
class Lease:
    key: str
    owner: str
    token: int
    expires_at: float


@dataclass(frozen=True)
class DeliveryClaim:
    key: str
    owner: str
    token: int
    acquired: bool
    delivered: bool = False


class ReliabilityStore:
    """Durable turn leases, delivery claims, pause state and queue storage."""

    def __init__(self, path: Optional[Path | str] = None, *, clock: Callable[[], float] = time.time):
        self.path = Path(path or default_state_path())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), timeout=10.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @contextlib.contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self._transaction() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS turn_leases (
                    lease_key TEXT PRIMARY KEY, owner TEXT NOT NULL,
                    fencing_token INTEGER NOT NULL, expires_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS delivery_ledger (
                    delivery_key TEXT PRIMARY KEY, owner TEXT NOT NULL,
                    fencing_token INTEGER NOT NULL, status TEXT NOT NULL,
                    lease_expires_at REAL NOT NULL, attempts INTEGER NOT NULL,
                    payload_digest TEXT, delivered_at REAL, last_error TEXT,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS control_state (
                    scope TEXT PRIMARY KEY, paused INTEGER NOT NULL DEFAULT 0,
                    reason TEXT, changed_by TEXT, updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS restart_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, process_key TEXT NOT NULL,
                    occurred_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS restart_events_lookup
                    ON restart_events(process_key, occurred_at);
                CREATE TABLE IF NOT EXISTS outbound_webhooks (
                    id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE,
                    url TEXT NOT NULL, body BLOB NOT NULL, status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0, available_at REAL NOT NULL,
                    lease_owner TEXT, lease_expires_at REAL, last_error TEXT,
                    created_at REAL NOT NULL, delivered_at REAL
                );
                CREATE INDEX IF NOT EXISTS webhook_due
                    ON outbound_webhooks(status, available_at);
                """
            )

    def acquire_turn_lease(self, key: str, owner: str, *, ttl: float = 60.0) -> Optional[Lease]:
        if not key or not owner or ttl <= 0:
            raise ValueError("key/owner must be non-empty and ttl must be positive")
        now = self.clock()
        with self._transaction() as conn:
            row = conn.execute("SELECT * FROM turn_leases WHERE lease_key=?", (key,)).fetchone()
            if row is None:
                token = 1
                conn.execute(
                    "INSERT INTO turn_leases VALUES (?, ?, ?, ?, ?)",
                    (key, owner, token, now + ttl, now),
                )
            elif row["owner"] == owner:
                token = int(row["fencing_token"])
                conn.execute(
                    "UPDATE turn_leases SET expires_at=?, updated_at=? WHERE lease_key=?",
                    (now + ttl, now, key),
                )
            elif float(row["expires_at"]) <= now:
                token = int(row["fencing_token"]) + 1
                conn.execute(
                    "UPDATE turn_leases SET owner=?, fencing_token=?, expires_at=?, updated_at=? WHERE lease_key=?",
                    (owner, token, now + ttl, now, key),
                )
            else:
                return None
        return Lease(key, owner, token, now + ttl)

    def renew_turn_lease(self, lease: Lease, *, ttl: float = 60.0) -> Optional[Lease]:
        if ttl <= 0:
            raise ValueError("ttl must be positive")
        now = self.clock()
        with self._transaction() as conn:
            changed = conn.execute(
                "UPDATE turn_leases SET expires_at=?, updated_at=? "
                "WHERE lease_key=? AND owner=? AND fencing_token=? AND expires_at>?",
                (now + ttl, now, lease.key, lease.owner, lease.token, now),
            ).rowcount
        return Lease(lease.key, lease.owner, lease.token, now + ttl) if changed else None

    def release_turn_lease(self, lease: Lease) -> bool:
        with self._transaction() as conn:
            return bool(conn.execute(
                "DELETE FROM turn_leases WHERE lease_key=? AND owner=? AND fencing_token=?",
                (lease.key, lease.owner, lease.token),
            ).rowcount)

    def claim_delivery(
        self, key: str, owner: str, *, ttl: float = 60.0, payload: bytes | str | None = None
    ) -> DeliveryClaim:
        """Atomically claim a delivery.

        Completed keys never reacquire.  Expired or explicitly failed claims can be
        retried with a new fencing token, preventing stale workers from completing
        a reclaimed delivery.
        """
        if not key or not owner or ttl <= 0:
            raise ValueError("key/owner must be non-empty and ttl must be positive")
        now = self.clock()
        raw = payload.encode() if isinstance(payload, str) else payload
        digest = hashlib.sha256(raw).hexdigest() if raw is not None else None
        with self._transaction() as conn:
            row = conn.execute("SELECT * FROM delivery_ledger WHERE delivery_key=?", (key,)).fetchone()
            if row is None:
                token = 1
                conn.execute(
                    "INSERT INTO delivery_ledger VALUES (?, ?, ?, 'claimed', ?, 1, ?, NULL, NULL, ?)",
                    (key, owner, token, now + ttl, digest, now),
                )
                return DeliveryClaim(key, owner, token, True)
            if row["status"] == "delivered":
                return DeliveryClaim(key, owner, int(row["fencing_token"]), False, True)
            if row["status"] == "claimed" and float(row["lease_expires_at"]) > now:
                return DeliveryClaim(key, owner, int(row["fencing_token"]), False)
            token = int(row["fencing_token"]) + 1
            conn.execute(
                "UPDATE delivery_ledger SET owner=?, fencing_token=?, status='claimed', "
                "lease_expires_at=?, attempts=attempts+1, payload_digest=COALESCE(?, payload_digest), "
                "last_error=NULL, updated_at=? WHERE delivery_key=?",
                (owner, token, now + ttl, digest, now, key),
            )
            return DeliveryClaim(key, owner, token, True)

    def complete_delivery(self, claim: DeliveryClaim) -> bool:
        now = self.clock()
        with self._transaction() as conn:
            return bool(conn.execute(
                "UPDATE delivery_ledger SET status='delivered', delivered_at=?, updated_at=? "
                "WHERE delivery_key=? AND owner=? AND fencing_token=? AND status='claimed'",
                (now, now, claim.key, claim.owner, claim.token),
            ).rowcount)

    def fail_delivery(self, claim: DeliveryClaim, error: str) -> bool:
        now = self.clock()
        with self._transaction() as conn:
            return bool(conn.execute(
                "UPDATE delivery_ledger SET status='failed', last_error=?, updated_at=? "
                "WHERE delivery_key=? AND owner=? AND fencing_token=? AND status='claimed'",
                (str(error)[:2000], now, claim.key, claim.owner, claim.token),
            ).rowcount)

    def set_paused(self, paused: bool, *, reason: str = "", changed_by: str = "operator", scope: str = "global") -> None:
        now = self.clock()
        with self._transaction() as conn:
            conn.execute(
                "INSERT INTO control_state(scope, paused, reason, changed_by, updated_at) VALUES(?,?,?,?,?) "
                "ON CONFLICT(scope) DO UPDATE SET paused=excluded.paused, reason=excluded.reason, "
                "changed_by=excluded.changed_by, updated_at=excluded.updated_at",
                (scope, int(paused), reason[:1000], changed_by[:200], now),
            )

    def pause_state(self, scope: str = "global") -> Mapping[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM control_state WHERE scope=?", (scope,)).fetchone()
        return dict(row) if row else {"scope": scope, "paused": 0, "reason": None, "changed_by": None, "updated_at": None}

    def is_paused(self, scope: str = "global") -> bool:
        return bool(self.pause_state(scope)["paused"])


def global_automation_paused(path: Optional[Path | str] = None) -> bool:
    """Default-safe integration probe: false unless reliability control is enabled."""
    if not feature_enabled():
        return False
    try:
        return ReliabilityStore(path).is_paused()
    except Exception:
        return False


class DrainController:
    """Thread-safe readiness/drain accounting for process lifecycle integration."""

    def __init__(self) -> None:
        self._lock = threading.Condition()
        self._active: set[str] = set()
        self._ready = False
        self._draining = False
        self._reason = "starting"

    def set_ready(self, ready: bool, reason: str = "") -> None:
        with self._lock:
            self._ready = bool(ready)
            self._reason = reason
            self._lock.notify_all()

    def begin(self, turn_id: Optional[str] = None) -> Optional[str]:
        with self._lock:
            if not self._ready or self._draining:
                return None
            token = turn_id or uuid.uuid4().hex
            self._active.add(token)
            return token

    def finish(self, token: str) -> None:
        with self._lock:
            self._active.discard(token)
            self._lock.notify_all()

    def start_drain(self, reason: str = "shutdown") -> None:
        with self._lock:
            self._draining = True
            self._ready = False
            self._reason = reason
            self._lock.notify_all()

    def wait_drained(self, timeout: float) -> bool:
        deadline = time.monotonic() + max(0.0, timeout)
        with self._lock:
            while self._active:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._lock.wait(remaining)
            return True

    def snapshot(self) -> Mapping[str, Any]:
        with self._lock:
            return {"ready": self._ready and not self._draining, "draining": self._draining, "active": len(self._active), "reason": self._reason}


class RestartLoopGuard:
    """Persisted sliding-window restart-loop circuit breaker."""

    def __init__(self, store: ReliabilityStore, process_key: str = "gateway"):
        self.store, self.process_key = store, process_key

    def record_and_allow(self, *, max_restarts: int = 5, window_seconds: float = 300.0) -> bool:
        if max_restarts < 1 or window_seconds <= 0:
            raise ValueError("invalid restart guard limits")
        now = self.store.clock()
        with self.store._transaction() as conn:
            cutoff = now - window_seconds
            conn.execute("DELETE FROM restart_events WHERE occurred_at < ?", (cutoff,))
            count = conn.execute(
                "SELECT COUNT(*) FROM restart_events WHERE process_key=? AND occurred_at>=?",
                (self.process_key, cutoff),
            ).fetchone()[0]
            if count >= max_restarts:
                return False
            conn.execute("INSERT INTO restart_events(process_key, occurred_at) VALUES(?,?)", (self.process_key, now))
            return True

    def reset(self) -> None:
        with self.store._transaction() as conn:
            conn.execute("DELETE FROM restart_events WHERE process_key=?", (self.process_key,))


class StallWatchdog:
    """Heartbeat watchdog primitive; callers choose whether/how to interrupt."""

    def __init__(self, timeout: float, *, clock: Callable[[], float] = time.monotonic):
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.timeout, self.clock = timeout, clock
        self._lock = threading.Lock()
        self._heartbeats: dict[str, tuple[float, str]] = {}

    def heartbeat(self, key: str, detail: str = "") -> None:
        with self._lock:
            self._heartbeats[key] = (self.clock(), detail)

    def clear(self, key: str) -> None:
        with self._lock:
            self._heartbeats.pop(key, None)

    def stalled(self) -> list[Mapping[str, Any]]:
        now = self.clock()
        with self._lock:
            return [
                {"key": key, "stalled_for": now - at, "detail": detail}
                for key, (at, detail) in self._heartbeats.items()
                if now - at >= self.timeout
            ]


def redact_payload(value: Any) -> Any:
    """Recursively remove obvious credentials before durable queue storage."""
    if isinstance(value, Mapping):
        return {str(k): ("[REDACTED]" if _SECRET_KEY.search(str(k)) else redact_payload(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_payload(v) for v in value]
    if isinstance(value, tuple):
        return [redact_payload(v) for v in value]
    return value


class SignedWebhookQueue:
    """Durable HMAC-SHA256 webhook outbox with leases and bounded backoff."""

    def __init__(self, store: ReliabilityStore, secret: bytes | str, *, clock: Optional[Callable[[], float]] = None):
        raw = secret.encode() if isinstance(secret, str) else secret
        if not raw:
            raise ValueError("webhook signing secret is required")
        self.store, self.secret, self.clock = store, raw, clock or store.clock

    def enqueue(self, url: str, payload: Any, *, idempotency_key: str, available_at: Optional[float] = None) -> str:
        if not url.startswith(("https://", "http://")) or not idempotency_key:
            raise ValueError("valid http(s) URL and idempotency key required")
        body = json.dumps(redact_payload(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        now = self.clock()
        item_id = uuid.uuid4().hex
        with self.store._transaction() as conn:
            existing = conn.execute(
                "SELECT id FROM outbound_webhooks WHERE idempotency_key=?", (idempotency_key,)
            ).fetchone()
            if existing:
                return str(existing["id"])
            conn.execute(
                "INSERT INTO outbound_webhooks(id,idempotency_key,url,body,status,available_at,created_at) "
                "VALUES(?,?,?,?,'pending',?,?)",
                (item_id, idempotency_key, url, body, now if available_at is None else available_at, now),
            )
        return item_id

    def _claim_due(self, owner: str, lease_seconds: float) -> Optional[sqlite3.Row]:
        now = self.clock()
        with self.store._transaction() as conn:
            row = conn.execute(
                "SELECT * FROM outbound_webhooks WHERE "
                "((status='pending' AND available_at<=?) OR (status='sending' AND lease_expires_at<=?)) "
                "ORDER BY available_at, created_at LIMIT 1",
                (now, now),
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                "UPDATE outbound_webhooks SET status='sending', lease_owner=?, lease_expires_at=?, attempts=attempts+1 WHERE id=?",
                (owner, now + lease_seconds, row["id"]),
            )
            return conn.execute("SELECT * FROM outbound_webhooks WHERE id=?", (row["id"],)).fetchone()

    def dispatch_one(
        self,
        sender: Callable[[str, bytes, Mapping[str, str]], int],
        *,
        owner: str = "webhook-worker",
        lease_seconds: float = 30.0,
        max_attempts: int = 8,
        base_backoff: float = 1.0,
    ) -> Optional[bool]:
        claim_owner = f"{owner}:{uuid.uuid4().hex}"
        row = self._claim_due(claim_owner, lease_seconds)
        if row is None:
            return None
        now = self.clock()
        body = bytes(row["body"])
        timestamp = str(int(now))
        signature = hmac.new(self.secret, timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": str(row["idempotency_key"]),
            "X-Clio-Timestamp": timestamp,
            "X-Clio-Signature": "sha256=" + signature,
        }
        try:
            status_code = int(sender(str(row["url"]), body, headers))
            if not 200 <= status_code < 300:
                raise RuntimeError(f"HTTP {status_code}")
        except Exception as exc:
            attempts = int(row["attempts"])
            terminal = attempts >= max_attempts
            with self.store._transaction() as conn:
                conn.execute(
                    "UPDATE outbound_webhooks SET status=?, available_at=?, lease_owner=NULL, lease_expires_at=NULL, last_error=? "
                    "WHERE id=? AND lease_owner=? AND status='sending'",
                    (
                        "dead" if terminal else "pending",
                        now + min(base_backoff * (2 ** max(0, attempts - 1)), 3600.0),
                        str(exc)[:2000], row["id"], claim_owner,
                    ),
                )
            return False
        with self.store._transaction() as conn:
            changed = conn.execute(
                "UPDATE outbound_webhooks SET status='delivered', delivered_at=?, lease_owner=NULL, lease_expires_at=NULL, last_error=NULL "
                "WHERE id=? AND lease_owner=? AND status='sending'",
                (now, row["id"], claim_owner),
            ).rowcount
        return bool(changed)
