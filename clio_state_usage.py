"""Per-session/per-model usage accounting helpers."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


def record_model_usage(
    conn,
    session_id: str,
    *,
    model: Optional[str] = None,
    billing_provider: Optional[str] = None,
    billing_base_url: Optional[str] = None,
    billing_mode: Optional[str] = None,
    task: str = "",
    api_call_count: int = 0,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    reasoning_tokens: int = 0,
    estimated_cost_usd: Optional[float] = None,
    actual_cost_usd: Optional[float] = None,
    cost_status: Optional[str] = None,
    cost_source: Optional[str] = None,
) -> None:
    """Accumulate one API-call delta in the caller's write transaction."""
    row = conn.execute(
        "SELECT model, billing_provider, billing_base_url, billing_mode "
        "FROM sessions WHERE id = ?",
        (session_id,),
    ).fetchone()
    # Auxiliary tasks may use a different route.  Never silently attribute
    # missing aux route data to the main model.
    if task:
        effective = (model or "unknown", billing_provider or "", billing_base_url or "", billing_mode or "")
    else:
        effective = (
            model or (row[0] if row else None) or "unknown",
            billing_provider or (row[1] if row else None) or "",
            billing_base_url or (row[2] if row else None) or "",
            billing_mode or (row[3] if row else None) or "",
        )
    now = time.time()
    conn.execute(
        """INSERT INTO session_model_usage (
               session_id, model, billing_provider, billing_base_url,
               billing_mode, task, api_call_count, input_tokens, output_tokens,
               cache_read_tokens, cache_write_tokens, reasoning_tokens,
               estimated_cost_usd, actual_cost_usd, cost_status, cost_source,
               first_seen, last_seen
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(
               session_id, model, billing_provider, billing_base_url,
               billing_mode, task
           ) DO UPDATE SET
               api_call_count = api_call_count + excluded.api_call_count,
               input_tokens = input_tokens + excluded.input_tokens,
               output_tokens = output_tokens + excluded.output_tokens,
               cache_read_tokens = cache_read_tokens + excluded.cache_read_tokens,
               cache_write_tokens = cache_write_tokens + excluded.cache_write_tokens,
               reasoning_tokens = reasoning_tokens + excluded.reasoning_tokens,
               estimated_cost_usd = estimated_cost_usd + excluded.estimated_cost_usd,
               actual_cost_usd = actual_cost_usd + excluded.actual_cost_usd,
               cost_status = COALESCE(excluded.cost_status, cost_status),
               cost_source = COALESCE(excluded.cost_source, cost_source),
               last_seen = excluded.last_seen""",
        (
            session_id,
            effective[0], effective[1], effective[2], effective[3], task or "",
            int(api_call_count or 0), int(input_tokens or 0), int(output_tokens or 0),
            int(cache_read_tokens or 0), int(cache_write_tokens or 0),
            int(reasoning_tokens or 0), float(estimated_cost_usd or 0.0),
            float(actual_cost_usd or 0.0), cost_status, cost_source, now, now,
        ),
    )


def list_model_usage(conn, session_id: str) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM session_model_usage WHERE session_id = ? "
        "ORDER BY first_seen, model, task",
        (session_id,),
    ).fetchall()
    return [dict(row) for row in rows]


__all__ = ["record_model_usage", "list_model_usage"]
