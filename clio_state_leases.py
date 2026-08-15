"""Atomic per-session turn lease primitives.

Callers resolve a session id to a logical lineage key before invoking these
functions.  Keeping the SQL here makes ownership/expiry semantics identical for
CLI, gateway, cron and delegated turns.
"""

from __future__ import annotations

import time
from typing import Optional


def try_acquire(
    conn,
    session_key: str,
    holder: str,
    *,
    ttl_seconds: float,
    now: Optional[float] = None,
) -> bool:
    if not session_key or not holder:
        return False
    now = time.time() if now is None else float(now)
    expires = now + max(float(ttl_seconds), 0.001)
    # Delete only expired rows; then INSERT OR IGNORE is the atomic contender.
    conn.execute(
        "DELETE FROM session_turn_leases WHERE session_key = ? AND expires_at < ?",
        (session_key, now),
    )
    conn.execute(
        "INSERT OR IGNORE INTO session_turn_leases "
        "(session_key, holder, acquired_at, expires_at) VALUES (?, ?, ?, ?)",
        (session_key, holder, now, expires),
    )
    row = conn.execute(
        "SELECT holder FROM session_turn_leases WHERE session_key = ?",
        (session_key,),
    ).fetchone()
    return row is not None and row[0] == holder


def refresh(
    conn,
    session_key: str,
    holder: str,
    *,
    ttl_seconds: float,
    now: Optional[float] = None,
) -> bool:
    now = time.time() if now is None else float(now)
    cursor = conn.execute(
        "UPDATE session_turn_leases SET expires_at = ? "
        "WHERE session_key = ? AND holder = ? AND expires_at >= ?",
        (now + max(float(ttl_seconds), 0.001), session_key, holder, now),
    )
    return cursor.rowcount == 1


def release(conn, session_key: str, holder: str) -> bool:
    cursor = conn.execute(
        "DELETE FROM session_turn_leases WHERE session_key = ? AND holder = ?",
        (session_key, holder),
    )
    return cursor.rowcount == 1


def current_holder(conn, session_key: str, *, now: Optional[float] = None):
    now = time.time() if now is None else float(now)
    row = conn.execute(
        "SELECT holder FROM session_turn_leases "
        "WHERE session_key = ? AND expires_at >= ?",
        (session_key, now),
    ).fetchone()
    return row[0] if row else None


__all__ = ["try_acquire", "refresh", "release", "current_holder"]
