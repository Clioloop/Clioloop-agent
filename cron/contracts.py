"""Durable cron observability backend contracts.

This augments (rather than replaces) jobs.json.  It provides an execution history,
a monitor notepad for small operator/check state, and explicit retention policies.
Integration is opt-in with ``CLIO_CRON_RELIABILITY_ENABLED``.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Mapping, Optional

from gateway.reliability import ReliabilityStore, feature_enabled


class CronBackend:
    def __init__(self, path: Optional[Path | str] = None, *, store: Optional[ReliabilityStore] = None):
        self.store = store or ReliabilityStore(path)
        self._initialize()

    def _initialize(self) -> None:
        with self.store._transaction() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS cron_executions (
                    execution_id TEXT PRIMARY KEY, job_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE, status TEXT NOT NULL,
                    scheduled_at TEXT, started_at REAL NOT NULL, finished_at REAL,
                    output_path TEXT, error TEXT, delivery_error TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS cron_history_job
                    ON cron_executions(job_id, started_at DESC);
                CREATE TABLE IF NOT EXISTS cron_monitor_notepad (
                    namespace TEXT NOT NULL, note_key TEXT NOT NULL, value_json TEXT NOT NULL,
                    updated_at REAL NOT NULL, expires_at REAL,
                    PRIMARY KEY(namespace, note_key)
                );
                CREATE TABLE IF NOT EXISTS cron_retention_policies (
                    record_type TEXT PRIMARY KEY, max_age_seconds REAL,
                    max_records INTEGER, updated_at REAL NOT NULL
                );
                """
            )

    def begin_execution(
        self,
        job_id: str,
        *,
        idempotency_key: str,
        scheduled_at: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> tuple[str, bool]:
        """Create a history row once; returns ``(execution_id, created)``."""
        if not job_id or not idempotency_key:
            raise ValueError("job_id and idempotency_key are required")
        now = self.store.clock()
        execution_id = uuid.uuid4().hex
        with self.store._transaction() as conn:
            existing = conn.execute(
                "SELECT execution_id FROM cron_executions WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if existing:
                return str(existing["execution_id"]), False
            conn.execute(
                "INSERT INTO cron_executions(execution_id,job_id,idempotency_key,status,scheduled_at,started_at,metadata_json) "
                "VALUES(?,?,?,'running',?,?,?)",
                (execution_id, job_id, idempotency_key, scheduled_at, now, json.dumps(dict(metadata or {}), sort_keys=True)),
            )
        return execution_id, True

    def finish_execution(
        self,
        execution_id: str,
        *,
        success: bool,
        output_path: Optional[str] = None,
        error: Optional[str] = None,
        delivery_error: Optional[str] = None,
    ) -> bool:
        """Idempotently finish only a running execution."""
        with self.store._transaction() as conn:
            return bool(conn.execute(
                "UPDATE cron_executions SET status=?, finished_at=?, output_path=?, error=?, delivery_error=? "
                "WHERE execution_id=? AND status='running'",
                (
                    "ok" if success else "error", self.store.clock(), output_path,
                    str(error)[:4000] if error else None,
                    str(delivery_error)[:4000] if delivery_error else None,
                    execution_id,
                ),
            ).rowcount)

    def execution_history(self, job_id: Optional[str] = None, *, limit: int = 100) -> list[Mapping[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        with self.store._connect() as conn:
            if job_id:
                rows = conn.execute(
                    "SELECT * FROM cron_executions WHERE job_id=? ORDER BY started_at DESC LIMIT ?",
                    (job_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM cron_executions ORDER BY started_at DESC LIMIT ?", (limit,)
                ).fetchall()
        return [dict(row) for row in rows]

    def put_note(
        self,
        namespace: str,
        key: str,
        value: Any,
        *,
        ttl: Optional[float] = None,
    ) -> None:
        if not namespace or not key or (ttl is not None and ttl <= 0):
            raise ValueError("namespace/key required and ttl must be positive")
        now = self.store.clock()
        with self.store._transaction() as conn:
            conn.execute(
                "INSERT INTO cron_monitor_notepad VALUES(?,?,?,?,?) "
                "ON CONFLICT(namespace,note_key) DO UPDATE SET value_json=excluded.value_json, "
                "updated_at=excluded.updated_at, expires_at=excluded.expires_at",
                (namespace, key, json.dumps(value, sort_keys=True), now, now + ttl if ttl else None),
            )

    def get_note(self, namespace: str, key: str, default: Any = None) -> Any:
        now = self.store.clock()
        with self.store._transaction() as conn:
            row = conn.execute(
                "SELECT value_json,expires_at FROM cron_monitor_notepad WHERE namespace=? AND note_key=?",
                (namespace, key),
            ).fetchone()
            if row is None:
                return default
            if row["expires_at"] is not None and float(row["expires_at"]) <= now:
                conn.execute(
                    "DELETE FROM cron_monitor_notepad WHERE namespace=? AND note_key=?", (namespace, key)
                )
                return default
            return json.loads(row["value_json"])

    def set_retention(
        self, record_type: str, *, max_age_seconds: Optional[float] = None, max_records: Optional[int] = None
    ) -> None:
        if record_type not in {"executions", "notepad", "webhooks"}:
            raise ValueError("unsupported record type")
        if max_age_seconds is None and max_records is None:
            raise ValueError("at least one retention bound is required")
        if max_age_seconds is not None and max_age_seconds <= 0:
            raise ValueError("max_age_seconds must be positive")
        if max_records is not None and max_records < 0:
            raise ValueError("max_records cannot be negative")
        with self.store._transaction() as conn:
            conn.execute(
                "INSERT INTO cron_retention_policies VALUES(?,?,?,?) "
                "ON CONFLICT(record_type) DO UPDATE SET max_age_seconds=excluded.max_age_seconds, "
                "max_records=excluded.max_records, updated_at=excluded.updated_at",
                (record_type, max_age_seconds, max_records, self.store.clock()),
            )

    def ensure_default_retention(self) -> None:
        """Install conservative bounds once without overriding operator policy."""
        defaults = {
            "executions": (30 * 86400.0, 10000),
            "notepad": (30 * 86400.0, None),
            "webhooks": (14 * 86400.0, None),
        }
        now = self.store.clock()
        with self.store._transaction() as conn:
            for record_type, (max_age, max_records) in defaults.items():
                conn.execute(
                    "INSERT OR IGNORE INTO cron_retention_policies VALUES(?,?,?,?)",
                    (record_type, max_age, max_records, now),
                )

    def apply_retention(self) -> Mapping[str, int]:
        """Apply configured age/count bounds in a single transaction."""
        deleted = {"executions": 0, "notepad": 0, "webhooks": 0}
        now = self.store.clock()
        with self.store._transaction() as conn:
            policies = {row["record_type"]: row for row in conn.execute("SELECT * FROM cron_retention_policies")}
            p = policies.get("executions")
            if p:
                if p["max_age_seconds"] is not None:
                    deleted["executions"] += conn.execute(
                        "DELETE FROM cron_executions WHERE started_at < ?", (now - float(p["max_age_seconds"]),)
                    ).rowcount
                if p["max_records"] is not None:
                    deleted["executions"] += conn.execute(
                        "DELETE FROM cron_executions WHERE execution_id IN (SELECT execution_id FROM cron_executions "
                        "ORDER BY started_at DESC LIMIT -1 OFFSET ?)", (int(p["max_records"]),)
                    ).rowcount
            p = policies.get("notepad")
            if p:
                cutoff = now - float(p["max_age_seconds"]) if p["max_age_seconds"] is not None else None
                if cutoff is not None:
                    deleted["notepad"] += conn.execute(
                        "DELETE FROM cron_monitor_notepad WHERE updated_at < ? OR (expires_at IS NOT NULL AND expires_at<=?)",
                        (cutoff, now),
                    ).rowcount
            p = policies.get("webhooks")
            if p and p["max_age_seconds"] is not None:
                deleted["webhooks"] += conn.execute(
                    "DELETE FROM outbound_webhooks WHERE status IN ('delivered','dead') AND created_at < ?",
                    (now - float(p["max_age_seconds"]),),
                ).rowcount
        return deleted


def integration_enabled() -> bool:
    return feature_enabled("CLIO_CRON_RELIABILITY_ENABLED")


def integration_backend() -> Optional[CronBackend]:
    if not integration_enabled():
        return None
    try:
        return CronBackend()
    except Exception:
        return None
