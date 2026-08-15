"""Durable async-delegation record primitives.

This module owns only persistence.  Executors and completion queues remain in
their existing tool modules; they can use these helpers without importing the
large ``clio_state`` facade.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Mapping, Optional

_JSON_FIELDS = {"event_json", "result_json", "task_json"}


def _json(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def upsert(conn, record: Mapping[str, Any]) -> None:
    now = float(record.get("updated_at") or time.time())
    dispatched = float(record.get("dispatched_at") or now)
    conn.execute(
        """INSERT INTO async_delegations (
               delegation_id, origin_session, origin_ui_session_id,
               parent_session_id, origin_session_id, state, dispatched_at,
               completed_at, updated_at, event_json, result_json, task_json,
               delivery_state, delivery_attempts, delivered_at,
               owner_pid, owner_started_at, delivery_claim, delivery_claimed_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(delegation_id) DO UPDATE SET
               origin_session = excluded.origin_session,
               origin_ui_session_id = excluded.origin_ui_session_id,
               parent_session_id = excluded.parent_session_id,
               origin_session_id = excluded.origin_session_id,
               state = excluded.state,
               completed_at = excluded.completed_at,
               updated_at = excluded.updated_at,
               event_json = COALESCE(excluded.event_json, event_json),
               result_json = COALESCE(excluded.result_json, result_json),
               task_json = COALESCE(excluded.task_json, task_json),
               delivery_state = excluded.delivery_state,
               delivery_attempts = excluded.delivery_attempts,
               delivered_at = excluded.delivered_at,
               owner_pid = excluded.owner_pid,
               owner_started_at = excluded.owner_started_at,
               delivery_claim = excluded.delivery_claim,
               delivery_claimed_at = excluded.delivery_claimed_at""",
        (
            str(record["delegation_id"]),
            str(record.get("origin_session") or record.get("session_key") or ""),
            str(record.get("origin_ui_session_id") or ""),
            record.get("parent_session_id"),
            str(record.get("origin_session_id") or ""),
            str(record.get("state") or record.get("status") or "running"),
            dispatched,
            record.get("completed_at"),
            now,
            _json(record.get("event_json", record.get("event"))),
            _json(record.get("result_json", record.get("result"))),
            _json(record.get("task_json", record.get("task"))),
            str(record.get("delivery_state") or "pending"),
            int(record.get("delivery_attempts") or 0),
            record.get("delivered_at"),
            record.get("owner_pid"),
            record.get("owner_started_at"),
            record.get("delivery_claim"),
            record.get("delivery_claimed_at"),
        ),
    )


def _decode(row) -> Dict[str, Any]:
    data = dict(row)
    for field in _JSON_FIELDS:
        raw = data.get(field)
        if raw:
            try:
                data[field[:-5]] = json.loads(raw)
            except (TypeError, ValueError):
                data[field[:-5]] = None
    return data


def get(conn, delegation_id: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        "SELECT * FROM async_delegations WHERE delegation_id = ?",
        (delegation_id,),
    ).fetchone()
    return _decode(row) if row else None


def list_records(
    conn,
    *,
    origin_session: Optional[str] = None,
    include_delivered: bool = True,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    where = []
    params: List[Any] = []
    if origin_session is not None:
        where.append("origin_session = ?")
        params.append(origin_session)
    if not include_delivered:
        where.append("delivery_state != 'delivered'")
    sql = "SELECT * FROM async_delegations"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY updated_at DESC LIMIT ?"
    params.append(max(1, min(int(limit), 1000)))
    return [_decode(row) for row in conn.execute(sql, params).fetchall()]


def claim_delivery(
    conn,
    delegation_id: str,
    claim_id: str,
    *,
    stale_after: float = 300.0,
    now: Optional[float] = None,
) -> bool:
    now = time.time() if now is None else float(now)
    cursor = conn.execute(
        """UPDATE async_delegations
           SET delivery_claim = ?, delivery_claimed_at = ?,
               delivery_attempts = delivery_attempts + 1, updated_at = ?
           WHERE delegation_id = ? AND delivery_state = 'pending'
             AND (delivery_claim IS NULL OR delivery_claimed_at < ?)""",
        (claim_id, now, now, delegation_id, now - stale_after),
    )
    return cursor.rowcount == 1


def release_delivery(conn, delegation_id: str, claim_id: str) -> bool:
    cursor = conn.execute(
        "UPDATE async_delegations SET delivery_claim = NULL, "
        "delivery_claimed_at = NULL, updated_at = ? "
        "WHERE delegation_id = ? AND delivery_state = 'pending' "
        "AND delivery_claim = ?",
        (time.time(), delegation_id, claim_id),
    )
    return cursor.rowcount == 1


def complete_delivery(conn, delegation_id: str, claim_id: str) -> bool:
    now = time.time()
    cursor = conn.execute(
        "UPDATE async_delegations SET delivery_state = 'delivered', "
        "delivered_at = ?, updated_at = ?, delivery_claim = NULL, "
        "delivery_claimed_at = NULL WHERE delegation_id = ? "
        "AND delivery_state = 'pending' AND delivery_claim = ?",
        (now, now, delegation_id, claim_id),
    )
    return cursor.rowcount == 1


def delete(conn, delegation_id: str) -> bool:
    return conn.execute(
        "DELETE FROM async_delegations WHERE delegation_id = ?", (delegation_id,)
    ).rowcount == 1


__all__ = [
    "upsert",
    "get",
    "list_records",
    "claim_delivery",
    "release_delivery",
    "complete_delivery",
    "delete",
]
