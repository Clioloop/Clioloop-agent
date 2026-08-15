"""Profile-scoped emergency pause state for new work.

The ``ESTOP`` sentinel pauses dispatch only; it never kills in-flight work.
Metadata writes are atomic and durable where the filesystem supports fsync.
A corrupt, empty, or unreadable sentinel remains authoritative (fail safe).
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

SENTINEL_NAME = "ESTOP"
_log_lock = threading.Lock()
_logged_components: set[str] = set()


def _clio_home() -> Path:
    try:
        from clio_cli.config import get_clio_home

        return Path(get_clio_home())
    except Exception:
        return Path(os.path.expanduser(os.getenv("CLIO_HOME", "~/.clio")))


def sentinel_path() -> Path:
    return _clio_home() / SENTINEL_NAME


def is_engaged() -> bool:
    try:
        return sentinel_path().exists()
    except OSError:
        return True


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        fd = os.open(str(path), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass


def engage(reason: Optional[str] = None) -> Path:
    """Atomically create/update the pause sentinel and return its path."""
    path = sentinel_path()
    payload = {
        "engaged_at": datetime.now(timezone.utc).isoformat(),
        "reason": reason or None,
    }
    temp_name: Optional[str] = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{SENTINEL_NAME}.", dir=str(path.parent)
        )
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
            temp_name = None
            _fsync_directory(path.parent)
        finally:
            if temp_name:
                try:
                    os.unlink(temp_name)
                except OSError:
                    pass
    except OSError:
        # An empty sentinel is valid and still safer than silently resuming.
        try:
            path.touch(exist_ok=True)
        except OSError:
            pass
    return path


def disengage() -> bool:
    """Remove the pause sentinel; return whether an engagement was lifted."""
    path = sentinel_path()
    try:
        path.unlink()
        _fsync_directory(path.parent)
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def get_state() -> Optional[dict[str, Optional[str]]]:
    """Return pause metadata, or ``None`` only when definitely disengaged."""
    try:
        path = sentinel_path()
        if not path.exists():
            return None
    except OSError:
        return {"reason": None, "engaged_at": None}

    reason = None
    engaged_at = None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            reason = raw.get("reason") or None
            engaged_at = raw.get("engaged_at") or None
    except (OSError, ValueError, TypeError):
        pass
    return {"reason": reason, "engaged_at": engaged_at}


def paused_reply() -> Optional[str]:
    state = get_state()
    if state is None:
        return None
    reason = state.get("reason")
    detail = f" ({reason})" if reason else ""
    return (
        f"⏸️ Clio is paused{detail}. New work is on hold until the "
        "profile's ESTOP sentinel is removed."
    )


def check_paused(component: str, logger: logging.Logger) -> bool:
    """Cheap dispatch gate that logs once per component and engagement."""
    if not is_engaged():
        with _log_lock:
            _logged_components.discard(component)
        return False
    with _log_lock:
        first = component not in _logged_components
        if first:
            _logged_components.add(component)
    if first:
        state = get_state() or {}
        suffix = f" (reason: {state.get('reason')})" if state.get("reason") else ""
        logger.info("%s dispatch paused by ESTOP%s", component, suffix)
    return True


def _reset_log_state_for_tests() -> None:
    with _log_lock:
        _logged_components.clear()


__all__ = [
    "SENTINEL_NAME",
    "sentinel_path",
    "is_engaged",
    "engage",
    "disengage",
    "get_state",
    "paused_reply",
    "check_paused",
]
