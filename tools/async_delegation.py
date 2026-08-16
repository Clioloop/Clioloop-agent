"""Durable background execution for :mod:`tools.delegate_tool`.

The execution rail is intentionally small: daemon workers run the existing
synchronous delegate implementation, persist lifecycle/result records through
``SessionDB``'s clio_state_delegations facade, and publish one completion onto
the shared process completion queue.  Persistence is committed before queue
publication, making restart replay and exactly-one delivery claims possible.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from clio_constants import get_clio_home

logger = logging.getLogger(__name__)
_records: Dict[str, Dict[str, Any]] = {}
_records_lock = threading.Lock()
_slots_lock = threading.Lock()
_active_slots = 0


def _process_started_at(pid: int) -> Optional[int]:
    """Return Linux process start ticks, protecting against PID reuse."""
    try:
        return int(Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split()[21])
    except Exception:
        return None


def _owner_is_alive(pid: Any, started_at: Any) -> bool:
    try:
        os.kill(int(pid), 0)
    except (OSError, TypeError, ValueError):
        return False
    current = _process_started_at(int(pid))
    return started_at is None or current is None or int(started_at) == current


def _open_db(db=None) -> Tuple[Any, bool]:
    if db is not None:
        return db, False
    from clio_state import SessionDB
    return SessionDB(), True


def _open_worker_db(db=None) -> Tuple[Any, bool]:
    """Use an independent connection when a parent-owned DB may be closed."""
    db_path = getattr(db, "db_path", None)
    if db_path is None:
        return _open_db(db)
    try:
        from clio_state import SessionDB
        return SessionDB(db_path), True
    except Exception:
        logger.exception("Could not open an independent delegation state connection")
        return db, False


def _close_db(db, owned: bool) -> None:
    if owned:
        try:
            db.close()
        except Exception:
            pass


def _transcript_paths(delegation_id: str, tasks: List[Dict[str, Any]]) -> List[str]:
    root = get_clio_home() / "cache" / "delegation" / "live" / delegation_id
    root.mkdir(parents=True, exist_ok=True)
    paths: List[str] = []
    for index, task in enumerate(tasks):
        path = root / f"task-{index}.jsonl"
        path.write_text(json.dumps({
            "event": "dispatched", "at": time.time(), "task_index": index,
            "goal": task.get("goal"), "context": task.get("context"),
        }, ensure_ascii=False) + "\n", encoding="utf-8")
        paths.append(str(path))
    return paths


def _append_results(paths: List[str], result: Dict[str, Any]) -> None:
    children = result.get("results") if isinstance(result, dict) else None
    for index, path in enumerate(paths):
        payload = children[index] if isinstance(children, list) and index < len(children) else result
        try:
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps({"event": "completed", "at": time.time(), "result": payload}, ensure_ascii=False, default=str) + "\n")
        except Exception:
            logger.debug("Could not append delegation transcript %s", path, exc_info=True)


def dispatch(
    *,
    tasks: List[Dict[str, Any]],
    runner: Callable[[], Any],
    parent_agent: Any,
    max_workers: int,
) -> Dict[str, Any]:
    """Persist and start one bounded background delegation unit."""
    global _active_slots
    with _slots_lock:
        if _active_slots >= max(1, int(max_workers)):
            return {
                "status": "rejected",
                "error": f"Background delegation capacity reached ({max_workers} running).",
            }
        _active_slots += 1

    delegation_id = f"deleg_{uuid.uuid4().hex[:12]}"
    dispatched_at = time.time()
    try:
        paths = _transcript_paths(delegation_id, tasks)
    except Exception:
        paths = []
    db = getattr(parent_agent, "_session_db", None)
    record = {
        "delegation_id": delegation_id,
        "origin_session": str(getattr(parent_agent, "session_id", "") or ""),
        "parent_session_id": getattr(parent_agent, "session_id", None),
        "origin_session_id": str(getattr(parent_agent, "session_id", "") or ""),
        "state": "running",
        "status": "running",
        "dispatched_at": dispatched_at,
        "updated_at": dispatched_at,
        "task": {"tasks": tasks, "transcript_paths": paths},
        "delivery_state": "pending",
        "owner_pid": os.getpid(),
        "owner_started_at": _process_started_at(os.getpid()),
        "transcript_paths": paths,
        "db": db,
    }
    with _records_lock:
        _records[delegation_id] = record
    durable, owned = _open_db(db)
    try:
        durable.upsert_async_delegation(record)
    except Exception:
        with _records_lock:
            _records.pop(delegation_id, None)
        with _slots_lock:
            _active_slots -= 1
        _close_db(durable, owned)
        logger.exception("Failed to persist background delegation")
        return {"status": "rejected", "error": "Could not persist background delegation."}
    _close_db(durable, owned)

    def worker() -> None:
        global _active_slots
        try:
            raw = runner()
            result: Dict[str, Any]
            if isinstance(raw, str):
                try:
                    result = json.loads(raw)
                except ValueError:
                    result = {"status": "error", "error": raw}
            elif isinstance(raw, dict):
                result = raw
            else:
                result = {"status": "error", "error": f"Unexpected delegation result: {type(raw).__name__}"}
            child_results = result.get("results") or []
            status = "completed" if child_results and any(
                child.get("status") == "completed" for child in child_results if isinstance(child, dict)
            ) else str(result.get("status") or "error")
        except Exception as exc:
            logger.exception("Background delegation %s failed", delegation_id)
            result = {"status": "error", "error": f"{type(exc).__name__}: {exc}", "results": []}
            status = "error"
        completed_at = time.time()
        result["transcript_paths"] = paths
        _append_results(paths, result)
        event = {
            "type": "async_delegation",
            "delegation_id": delegation_id,
            "session_key": record["origin_session"],
            "parent_session_id": record["parent_session_id"],
            "status": status,
            "tasks": tasks,
            "results": result.get("results") or [],
            "transcript_paths": paths,
            "tokens": _aggregate_tokens(result),
            "cost_usd": _aggregate_cost(result),
            "dispatched_at": dispatched_at,
            "completed_at": completed_at,
            "error": result.get("error"),
        }
        persisted = False
        durable, owned = _open_worker_db(db)
        try:
            durable.upsert_async_delegation({
                **record, "state": status, "status": status,
                "completed_at": completed_at, "updated_at": completed_at,
                "event": event, "result": result, "delivery_state": "pending",
            })
            persisted = True
        except Exception:
            logger.exception("Delegation %s completed but result persistence failed", delegation_id)
        finally:
            _close_db(durable, owned)
        with _records_lock:
            if delegation_id in _records:
                _records[delegation_id].update({
                    "state": status, "status": status, "completed_at": completed_at,
                    "result": result, "event": event,
                })
        try:
            if persisted:
                from tools.process_registry import process_registry
                process_registry.completion_queue.put(event)
        except Exception:
            logger.exception("Delegation %s persisted but completion enqueue failed", delegation_id)
        finally:
            with _slots_lock:
                _active_slots = max(0, _active_slots - 1)

    threading.Thread(target=worker, name=f"delegate-{delegation_id}", daemon=True).start()
    return {
        "status": "dispatched", "mode": "background",
        "delegation_id": delegation_id, "count": len(tasks),
        "transcript_paths": paths,
        "note": "The durable result will be delivered as a new completion turn; do not poll.",
    }


def _aggregate_tokens(result: Dict[str, Any]) -> Dict[str, int]:
    totals = {"input": 0, "output": 0, "reasoning": 0}
    for child in result.get("results") or []:
        if not isinstance(child, dict):
            continue
        tokens = child.get("tokens") or {}
        for key in totals:
            try:
                totals[key] += int(tokens.get(key, 0) or 0)
            except (TypeError, ValueError):
                pass
    return totals


def _aggregate_cost(result: Dict[str, Any]) -> float:
    total = 0.0
    for child in result.get("results") or []:
        if isinstance(child, dict):
            try:
                total += float(child.get("cost_usd", 0) or 0)
            except (TypeError, ValueError):
                pass
    return total


def list_records(*, db=None, origin_session: Optional[str] = None) -> List[Dict[str, Any]]:
    durable, owned = _open_db(db)
    try:
        return durable.list_async_delegations(origin_session=origin_session)
    finally:
        _close_db(durable, owned)


def status(delegation_id: str, *, db=None) -> Optional[Dict[str, Any]]:
    with _records_lock:
        live = _records.get(delegation_id)
        if live:
            return {k: v for k, v in live.items() if k != "db"}
    durable, owned = _open_db(db)
    try:
        return durable.get_async_delegation(delegation_id)
    finally:
        _close_db(durable, owned)


def claim_completion_delivery(delegation_id: str, claim_id: str, *, db=None) -> bool:
    durable, owned = _open_db(db)
    try:
        return durable.claim_async_delegation_delivery(delegation_id, claim_id)
    finally:
        _close_db(durable, owned)


def release_completion_delivery(delegation_id: str, claim_id: str, *, db=None) -> bool:
    durable, owned = _open_db(db)
    try:
        return durable.release_async_delegation_delivery(delegation_id, claim_id)
    finally:
        _close_db(durable, owned)


def complete_completion_delivery(delegation_id: str, claim_id: str, *, db=None) -> bool:
    durable, owned = _open_db(db)
    try:
        return durable.complete_async_delegation_delivery(delegation_id, claim_id)
    finally:
        _close_db(durable, owned)


def claim_event_delivery(event: Dict[str, Any], consumer: str, *, db=None) -> Optional[str]:
    if event.get("type") != "async_delegation":
        return ""
    claim = f"{consumer}:{os.getpid()}:{uuid.uuid4().hex}"
    return claim if claim_completion_delivery(str(event.get("delegation_id") or ""), claim, db=db) else None


def complete_event_delivery(event: Dict[str, Any], claim: str, *, db=None) -> bool:
    return bool(claim) and complete_completion_delivery(str(event.get("delegation_id") or ""), claim, db=db)


def release_event_delivery(event: Dict[str, Any], claim: str, *, db=None) -> bool:
    return bool(claim) and release_completion_delivery(str(event.get("delegation_id") or ""), claim, db=db)


def recover_abandoned_delegations(*, db=None) -> int:
    """Mark running rows whose owner process vanished as outcome ``unknown``."""
    durable, owned = _open_db(db)
    recovered = 0
    try:
        for row in durable.list_async_delegations():
            if row.get("state") not in {"running", "finalizing"}:
                continue
            if _owner_is_alive(row.get("owner_pid"), row.get("owner_started_at")):
                continue
            now = time.time()
            error = "Delegation owner exited before recording a terminal result; outcome unknown."
            event = {
                "type": "async_delegation", "delegation_id": row["delegation_id"],
                "session_key": row.get("origin_session", ""), "status": "unknown",
                "error": error, "completed_at": now,
            }
            durable.upsert_async_delegation({
                **row, "state": "unknown", "completed_at": now, "updated_at": now,
                "event": event, "result": {"status": "unknown", "error": error},
                "delivery_state": "pending",
            })
            recovered += 1
        return recovered
    finally:
        _close_db(durable, owned)


def restore_undelivered_completions(target_queue, *, db=None) -> int:
    recover_abandoned_delegations(db=db)
    restored = 0
    for row in list_records(db=db):
        event = row.get("event")
        if row.get("delivery_state") == "pending" and isinstance(event, dict):
            target_queue.put({**event, "restored": True})
            restored += 1
    return restored


def active_count() -> int:
    with _records_lock:
        return sum(1 for record in _records.values() if record.get("state") == "running")
