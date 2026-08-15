"""Passive verification evidence classification and durable ledger.

Only commands present in a detected recipe are evidence.  This module never
runs commands and never upgrades a targeted check into a full-project claim.
"""

from __future__ import annotations

import re
import shlex
import sqlite3
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from agent.verify.recipes import detect_recipe

_DB_LOCK = threading.Lock()
_MAX_OUTPUT_CHARS = 2000
_SPLIT_RE = re.compile(r"\s*(?:&&|\|\||;)\s*")


@dataclass(frozen=True)
class VerificationEvidence:
    command: str
    canonical_command: str
    kind: str
    scope: str
    status: str
    exit_code: int
    cwd: str
    root: str
    session_id: str
    output_summary: str = ""


def _db_path() -> Path:
    try:
        from clio_cli.config import get_clio_home

        return Path(get_clio_home()) / "verification_evidence.db"
    except Exception:
        return Path.home() / ".clio" / "verification_evidence.db"


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=5.0)
    try:
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS verification_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                session_id TEXT NOT NULL,
                root TEXT NOT NULL,
                cwd TEXT NOT NULL,
                command TEXT NOT NULL,
                canonical_command TEXT NOT NULL,
                kind TEXT NOT NULL,
                scope TEXT NOT NULL,
                status TEXT NOT NULL,
                exit_code INTEGER NOT NULL,
                output_summary TEXT NOT NULL
            )
            """
        )
        connection.commit()
        return connection
    except Exception:
        connection.close()
        raise


def _tokens(command: str) -> list[list[str]]:
    result: list[list[str]] = []
    for segment in _SPLIT_RE.split(command.strip()):
        try:
            parsed = shlex.split(segment)
        except ValueError:
            continue
        while parsed and parsed[0] in {"env", "command", "time"}:
            parsed = parsed[1:]
        while parsed and "=" in parsed[0] and not parsed[0].startswith("-"):
            parsed = parsed[1:]
        if parsed:
            result.append(parsed)
    return result


def _scope(args: list[str]) -> str:
    for arg in args:
        if arg.startswith("-") or "=" in arg:
            continue
        if "/" in arg or "::" in arg or arg.endswith(
            (".py", ".js", ".jsx", ".ts", ".tsx")
        ):
            return "targeted"
    return "full"


def _summary(output: str) -> str:
    text = (output or "").strip()
    if len(text) <= _MAX_OUTPUT_CHARS:
        return text
    head = _MAX_OUTPUT_CHARS // 2
    tail = _MAX_OUTPUT_CHARS - head
    return f"{text[:head]}\n... output omitted ...\n{text[-tail:]}"


def classify_verification_command(
    command: str,
    *,
    cwd: str | Path | None = None,
    session_id: str | None = None,
    exit_code: int = 0,
    output: str = "",
) -> Optional[VerificationEvidence]:
    """Classify a command against the workspace's detected recipe."""
    if not isinstance(command, str) or not command.strip():
        return None
    root = Path(cwd or ".").resolve()
    recipe = detect_recipe(root)
    if recipe is None:
        return None
    segments = _tokens(command)
    for canonical in recipe.verification_commands:
        try:
            needle = shlex.split(canonical)
        except ValueError:
            continue
        for segment in segments:
            if segment[: len(needle)] != needle:
                continue
            trailing = segment[len(needle) :]
            return VerificationEvidence(
                command=command,
                canonical_command=canonical,
                kind=recipe.kind,
                scope=_scope(trailing),
                status="passed" if int(exit_code) == 0 else "failed",
                exit_code=int(exit_code),
                cwd=str(root),
                root=str(root),
                session_id=str(session_id or "default"),
                output_summary=_summary(output),
            )
    return None


def record_terminal_result(
    *,
    command: str,
    cwd: str | Path | None,
    session_id: str | None,
    exit_code: int,
    output: str = "",
) -> Optional[dict[str, Any]]:
    """Persist a classified foreground terminal result, if applicable."""
    evidence = classify_verification_command(
        command,
        cwd=cwd,
        session_id=session_id,
        exit_code=exit_code,
        output=output,
    )
    if evidence is None:
        return None
    created_at = datetime.now(timezone.utc).isoformat()
    with _DB_LOCK:
        connection = _connect()
        try:
            cursor = connection.execute(
                """
                INSERT INTO verification_events(
                    created_at, session_id, root, cwd, command,
                    canonical_command, kind, scope, status, exit_code,
                    output_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    evidence.session_id,
                    evidence.root,
                    evidence.cwd,
                    evidence.command,
                    evidence.canonical_command,
                    evidence.kind,
                    evidence.scope,
                    evidence.status,
                    evidence.exit_code,
                    evidence.output_summary,
                ),
            )
            event_id = int(cursor.lastrowid or 0)
            # Keep a bounded per-session/workspace history.
            connection.execute(
                """
                DELETE FROM verification_events
                WHERE session_id = ? AND root = ? AND id NOT IN (
                    SELECT id FROM verification_events
                    WHERE session_id = ? AND root = ?
                    ORDER BY id DESC LIMIT 100
                )
                """,
                (
                    evidence.session_id,
                    evidence.root,
                    evidence.session_id,
                    evidence.root,
                ),
            )
            connection.commit()
        finally:
            connection.close()
    return {"id": event_id, "created_at": created_at, **asdict(evidence)}


__all__ = [
    "VerificationEvidence",
    "classify_verification_command",
    "record_terminal_result",
]
