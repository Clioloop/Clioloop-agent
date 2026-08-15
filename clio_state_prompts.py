"""Content-addressed persisted system-prompt helpers."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Optional


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8", errors="surrogatepass")).hexdigest()


def store(conn, prompt: Optional[str]) -> Optional[str]:
    if prompt is None:
        return None
    digest = prompt_hash(prompt)
    conn.execute(
        "INSERT OR IGNORE INTO system_prompts (hash, prompt) VALUES (?, ?)",
        (digest, prompt),
    )
    return digest


def collect_unreferenced(conn) -> int:
    cursor = conn.execute(
        "DELETE FROM system_prompts WHERE NOT EXISTS ("
        "SELECT 1 FROM sessions "
        "WHERE sessions.system_prompt_hash = system_prompts.hash)"
    )
    return max(cursor.rowcount, 0)


def migrate_inline_prompts(conn) -> int:
    """Move legacy inline snapshots to the content-addressed table once."""
    rows = conn.execute(
        "SELECT id, system_prompt FROM sessions "
        "WHERE system_prompt IS NOT NULL AND system_prompt_hash IS NULL"
    ).fetchall()
    migrated = 0
    for row in rows:
        digest = store(conn, row[1])
        conn.execute(
            "UPDATE sessions SET system_prompt = NULL, system_prompt_hash = ? "
            "WHERE id = ? AND system_prompt_hash IS NULL",
            (digest, row[0]),
        )
        migrated += 1
    return migrated


def hydrate_row(row) -> Dict[str, Any]:
    data = dict(row)
    resolved = data.pop("_system_prompt_resolved", None)
    if "system_prompt" in data and resolved is not None:
        data["system_prompt"] = resolved
    return data


__all__ = [
    "prompt_hash",
    "store",
    "collect_unreferenced",
    "migrate_inline_prompts",
    "hydrate_row",
]
