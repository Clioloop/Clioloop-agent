"""Profile-local gateway routing persistence helpers."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional


def save_gateway_routing_entry(
    conn,
    session_key: str,
    source_json: str,
    *,
    scope: str = "default",
    now: Optional[float] = None,
) -> None:
    """Upsert one route inside its scope.

    ``scope`` is part of the conflict key so tenants and Clio profiles cannot
    overwrite each other's route when they happen to reuse a session key.
    """
    conn.execute(
        """INSERT INTO gateway_routing (scope, session_key, source_json, updated_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(scope, session_key) DO UPDATE SET
             source_json = excluded.source_json,
             updated_at = excluded.updated_at""",
        (scope or "default", session_key, source_json, now or time.time()),
    )


def load_gateway_routing_entries(conn, *, scope: str = "default") -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT session_key, source_json, updated_at, scope "
        "FROM gateway_routing WHERE scope = ? ORDER BY updated_at ASC",
        (scope or "default",),
    ).fetchall()
    return [dict(row) for row in rows]


def delete_gateway_routing_entry(
    conn, session_key: str, *, scope: str = "default"
) -> bool:
    cursor = conn.execute(
        "DELETE FROM gateway_routing WHERE scope = ? AND session_key = ?",
        (scope or "default", session_key),
    )
    return cursor.rowcount > 0


def repair_gateway_routing(conn, *, scope: str = "default") -> Dict[str, int]:
    """Remove only provably malformed route JSON; never guess ownership."""
    rows = conn.execute(
        "SELECT session_key, source_json FROM gateway_routing WHERE scope = ?",
        (scope or "default",),
    ).fetchall()
    invalid = []
    for row in rows:
        try:
            value = json.loads(row["source_json"])
            if not isinstance(value, dict):
                raise ValueError("route must be an object")
        except (TypeError, ValueError, json.JSONDecodeError):
            invalid.append(row["session_key"])
    for key in invalid:
        conn.execute(
            "DELETE FROM gateway_routing WHERE scope = ? AND session_key = ?",
            (scope or "default", key),
        )
    return {"checked": len(rows), "removed": len(invalid), "kept": len(rows) - len(invalid)}


__all__ = [
    "save_gateway_routing_entry",
    "load_gateway_routing_entries",
    "delete_gateway_routing_entry",
    "repair_gateway_routing",
]
