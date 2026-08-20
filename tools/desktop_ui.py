"""Session-scoped bridge between Clio model tools and the desktop renderer.

Desktop affordances are capabilities of a GUI session, not process-global
state.  Tool handlers resolve the current renderer session from
``gateway.session_context`` and hand an action to callbacks installed by the
TUI/desktop gateway.  CLI, cron, and messaging sessions have no UI session id,
so calls fail closed instead of targeting whichever window happened to connect
last.
"""
from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from gateway.session_context import get_session_env

EmitCallback = Callable[[str, str, dict[str, Any]], bool]
RequestCallback = Callable[[str, str, dict[str, Any], float], Any]

_lock = threading.RLock()
_emit_callback: EmitCallback | None = None
_request_callback: RequestCallback | None = None


def configure_bridge(
    *,
    emit_callback: EmitCallback | None,
    request_callback: RequestCallback | None = None,
) -> None:
    """Install or clear the host bridge.

    Registration is process-wide, while routing is session-scoped through the
    ``CLIO_UI_SESSION_ID`` ContextVar.  Re-registering is safe during gateway
    reloads and tests.
    """
    global _emit_callback, _request_callback
    with _lock:
        _emit_callback = emit_callback
        _request_callback = request_callback


def current_ui_session_id() -> str:
    """Return the runtime GUI session id, or an empty string off the GUI."""
    return get_session_env("CLIO_UI_SESSION_ID", "").strip()


def emit(action: str, payload: dict[str, Any] | None = None) -> bool:
    """Emit a fire-and-forget action to the current desktop window."""
    sid = current_ui_session_id()
    with _lock:
        callback = _emit_callback
    if not sid or callback is None:
        return False
    return bool(callback(action, sid, dict(payload or {})))


def request(
    action: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout: float = 8.0,
) -> Any:
    """Request a bounded snapshot from the current desktop window."""
    sid = current_ui_session_id()
    with _lock:
        callback = _request_callback
    if not sid or callback is None:
        raise RuntimeError("desktop UI requests are only available in Clio Desktop")
    bounded = max(0.1, min(float(timeout), 30.0))
    return callback(action, sid, dict(payload or {}), bounded)
