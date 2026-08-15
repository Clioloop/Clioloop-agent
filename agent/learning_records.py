"""Durable learning suggestions and refinement audit records.

The store is deliberately small and profile-scoped.  Records are proposals,
never implicit mutations: callers explicitly accept/dismiss suggestions and
complete/fail refinements.  Every rewrite uses fsync + atomic replace.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from clio_constants import get_clio_home
from utils import atomic_replace

_KINDS = {"suggestion", "refinement"}
_STATUSES = {"pending", "accepted", "dismissed", "running", "completed", "failed"}
_lock = threading.RLock()


def records_path() -> Path:
    return get_clio_home() / "learning" / "records.json"


def _load(path: Optional[Path] = None) -> list[dict[str, Any]]:
    target = path or records_path()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = raw.get("records", []) if isinstance(raw, dict) else raw
    return [dict(row) for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _save(rows: Iterable[Mapping[str, Any]], path: Optional[Path] = None) -> None:
    target = path or records_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".learning-", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"version": 1, "records": list(rows)}, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        atomic_replace(tmp, target)
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def add_record(
    kind: str,
    title: str,
    *,
    detail: str = "",
    source: str = "user",
    metadata: Optional[Mapping[str, Any]] = None,
    dedup_key: Optional[str] = None,
) -> dict[str, Any]:
    """Create a pending record, deduplicating unresolved proposals."""
    kind, title = str(kind).strip().lower(), str(title).strip()
    if kind not in _KINDS or not title:
        raise ValueError("kind must be suggestion/refinement and title is required")
    with _lock:
        rows = _load()
        if dedup_key:
            for row in rows:
                if row.get("dedup_key") == dedup_key and row.get("status") in {"pending", "running"}:
                    return row
        now = time.time()
        row = {
            "id": uuid.uuid4().hex[:16], "kind": kind, "title": title,
            "detail": str(detail).strip(), "source": str(source).strip() or "user",
            "status": "pending", "created_at": now, "updated_at": now,
            "metadata": dict(metadata or {}), "dedup_key": dedup_key,
        }
        rows.append(row)
        _save(rows)
        return row


def list_records(*, kind: Optional[str] = None, status: Optional[str] = None) -> list[dict[str, Any]]:
    rows = _load()
    if kind is not None:
        rows = [r for r in rows if r.get("kind") == kind]
    if status is not None:
        rows = [r for r in rows if r.get("status") == status]
    return rows


def update_record(record_id: str, status: str, *, note: str = "") -> Optional[dict[str, Any]]:
    """Apply an explicit lifecycle transition and return the changed record."""
    status = str(status).strip().lower()
    if status not in _STATUSES:
        raise ValueError(f"unsupported learning status: {status}")
    with _lock:
        rows = _load()
        found = None
        for row in rows:
            if row.get("id") == record_id:
                row["status"] = status
                row["updated_at"] = time.time()
                if note:
                    row["resolution_note"] = str(note)
                found = row
                break
        if found is not None:
            _save(rows)
        return found


def delete_record(record_id: str) -> bool:
    with _lock:
        rows = _load()
        kept = [row for row in rows if row.get("id") != record_id]
        if len(kept) == len(rows):
            return False
        _save(kept)
        return True


__all__ = ["add_record", "list_records", "update_record", "delete_record", "records_path"]
