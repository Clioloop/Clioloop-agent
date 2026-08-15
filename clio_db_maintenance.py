"""Non-destructive SQLite diagnosis, recovery, repair and optimization."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional


def database_check(path: Path) -> Dict[str, Any]:
    path = Path(path)
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        rows = [r[0] for r in conn.execute("PRAGMA integrity_check").fetchall()]
        return {"ok": rows == ["ok"], "details": rows, "path": str(path)}
    finally:
        conn.close()


def recover_database(source: Path, destination: Optional[Path] = None) -> Path:
    """Copy a live database through SQLite's backup API; source is read-only."""
    source = Path(source)
    destination = Path(destination or source.with_suffix(source.suffix + ".recovered"))
    if destination.exists():
        raise FileExistsError(destination)
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    dst = sqlite3.connect(str(destination))
    try:
        src.backup(dst)
        result = dst.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise sqlite3.DatabaseError(f"recovered database failed integrity check: {result}")
    except BaseException:
        dst.close()
        destination.unlink(missing_ok=True)
        raise
    finally:
        src.close()
        try:
            dst.close()
        except Exception:
            pass
    return destination


def repair_database(source: Path, destination: Optional[Path] = None) -> Path:
    """Recover to a new file, reconcile safe counters, and rebuild FTS indexes."""
    destination = recover_database(source, destination or Path(str(source) + ".repaired"))
    conn = sqlite3.connect(str(destination))
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if {"sessions", "messages"} <= tables:
            conn.execute("UPDATE sessions SET message_count=(SELECT COUNT(*) FROM messages WHERE session_id=sessions.id)")
            for table in ("messages_fts", "messages_fts_trigram"):
                if table in tables:
                    conn.execute(f"INSERT INTO {table}({table}) VALUES('rebuild')")
        conn.commit()
    finally:
        conn.close()
    return destination


def optimize_database(source: Path, destination: Optional[Path] = None) -> Path:
    """Create and optimize a copy, never VACUUM the live source."""
    destination = recover_database(source, destination or Path(str(source) + ".optimized"))
    conn = sqlite3.connect(str(destination))
    try:
        conn.execute("PRAGMA optimize")
        conn.execute("VACUUM")
    finally:
        conn.close()
    return destination
