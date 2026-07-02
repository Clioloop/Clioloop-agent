"""Entry point for the `computer_use` tool.

Universal (any-model) desktop control across macOS, Windows, and Linux via
cua-driver's background computer-use primitive. Replaces #4562's
Anthropic-native `computer_20251124` approach — the schema here is standard
OpenAI function-calling so every tool-capable model can drive it.

Linux is the most recent runtime (X11 + Wayland, via cua-driver-rs's
AT-SPI tree path); it is enabled here alongside macOS and Windows. When a
host's display server or accessibility stack isn't reachable, cua-driver's
`health_report` (surfaced by `clio computer-use doctor`) reports the
exact blocked check rather than the toolset silently failing.

Return contract
---------------
For text-only results (wait, key, list_apps, focus_app, failures, etc.):
  JSON string.

For captures / actions with `capture_after=True`:
  A dict wrapped as the OpenAI-style multi-part tool-message content:

      {
        "_multimodal": True,
        "content": [
            {"type": "text", "text": "<human-readable summary + SOM index>"},
            {"type": "image_url",
             "image_url": {"url": "data:image/png;base64,<b64>"}},
        ],
        "text_summary": "<text used for fallback string content>",
      }

  run_agent.py's tool-message builder inspects `_multimodal` and emits a
  list-shaped `content` for OpenAI-compatible providers. The Anthropic
  adapter splices the base64 image into a `tool_result` block (see
  `agent/anthropic_adapter.py`). Every provider that supports multi-part
  tool content gets the image; text-only providers see the summary only.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import struct
import sys
import threading
from typing import Any, Dict, List, Optional, Tuple

from tools.computer_use.backend import (
    ActionResult,
    CaptureResult,
    ComputerUseBackend,
    UIElement,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Approval & safety
# ---------------------------------------------------------------------------

_approval_callback = None


def set_approval_callback(cb) -> None:
    """Register a callback for computer_use approval prompts (used by CLI).

    Matches the terminal_tool._approval_callback pattern. The callback
    receives (action, args, summary) and returns one of:
      "approve_once" | "approve_session" | "always_approve" | "deny".
    """
    global _approval_callback
    _approval_callback = cb


# Synonyms models commonly emit for the canonical action names. Normalizing
# here keeps the schema enum tight while accepting reasonable variation
# instead of hard-failing with "unknown action" (e.g. some models trained on
# other computer-use tools emit `press` for a key press or `screenshot` for a
# capture).
_ACTION_ALIASES: Dict[str, str] = {
    "press": "key",
    "keypress": "key",
    "key_press": "key",
    "press_key": "key",
    "hotkey": "key",
    "screenshot": "capture",
    "screen_capture": "capture",
    "screencap": "capture",
    "snapshot": "capture",
    "left_click": "click",
    "leftclick": "click",
    "tap": "click",
    "double-click": "double_click",
    "doubleclick": "double_click",
    "dblclick": "double_click",
    "right-click": "right_click",
    "rightclick": "right_click",
    "middle-click": "middle_click",
    "middleclick": "middle_click",
    "type_text": "type",
    "typetext": "type",
    "input_text": "type",
    "enter_text": "type",
    "list_applications": "list_apps",
    "list_apps_running": "list_apps",
    "focus": "focus_app",
    "activate": "focus_app",
    "browser": "page",
    "browser_page": "page",
}

# Synonyms for the `page` sub-action (page_action). Models trained on other
# browser tools emit the cua-driver verb names or generic ones.
_PAGE_ACTION_ALIASES: Dict[str, str] = {
    "get_text": "read",
    "text": "read",
    "read_page": "read",
    "extract": "read",
    "query_dom": "query",
    "dom": "query",
    "find": "query",
    "click_element": "click",
    "execute_javascript": "js",
    "eval": "js",
    "evaluate": "js",
    "javascript": "js",
    "scroll_page": "scroll",
}

# `page` sub-actions that only read page state — exempt from the approval
# gate, like capture/list_apps.
_PAGE_READONLY = frozenset({"read", "query"})


# Actions that read, not mutate. Always allowed.
_SAFE_ACTIONS = frozenset({"capture", "wait", "list_apps", "list_windows"})

# Actions that mutate user-visible state. Go through approval.
# `page` is here because scroll/click/js mutate the page; the read-only
# sub-actions (see _PAGE_READONLY) are exempted at the approval gate.
_DESTRUCTIVE_ACTIONS = frozenset({
    "click", "double_click", "right_click", "middle_click",
    "drag", "scroll", "page", "type", "key", "set_value", "focus_app",
    "focus_window", "minimize",
})

# Hard-blocked key combinations. Mirrored from #4562 — these are destructive
# regardless of approval level (e.g. logout kills the session Clio runs in).
_BLOCKED_KEY_COMBOS = {
    frozenset({"cmd", "shift", "backspace"}),   # empty trash
    frozenset({"cmd", "option", "backspace"}),   # force delete
    frozenset({"cmd", "ctrl", "q"}),             # lock screen
    frozenset({"cmd", "shift", "q"}),            # log out
    frozenset({"cmd", "option", "shift", "q"}),  # force log out
    # Windows secure/session shortcuts. The Windows driver accepts Win-key
    # combos, and Alt is canonicalized to option below, so block the
    # destructive variants before any backend sees them.
    frozenset({"win", "l"}),
    frozenset({"ctrl", "option", "delete"}),
    frozenset({"ctrl", "option", "del"}),
    frozenset({"option", "f4"}),
}

_KEY_ALIASES = {
    "command": "cmd", "control": "ctrl", "alt": "option", "⌘": "cmd", "⌥": "option",
    "windows": "win", "super": "win", "meta": "win",
}


def _canon_key_combo(keys: str) -> frozenset:
    parts = [p.strip().lower() for p in re.split(r"\s*\+\s*", keys) if p.strip()]
    parts = [_KEY_ALIASES.get(p, p) for p in parts]
    return frozenset(parts)


# Dangerous text patterns for the `type` action. Same list as #4562.
_BLOCKED_TYPE_PATTERNS = [
    re.compile(r"curl\s+[^|]*\|\s*bash", re.IGNORECASE),
    re.compile(r"curl\s+[^|]*\|\s*sh", re.IGNORECASE),
    re.compile(r"wget\s+[^|]*\|\s*bash", re.IGNORECASE),
    re.compile(r"\bsudo\s+rm\s+-[rf]", re.IGNORECASE),
    re.compile(r"\brm\s+-rf\s+/\s*$", re.IGNORECASE),
    re.compile(r":\s*\(\)\s*\{\s*:\|:\s*&\s*\}", re.IGNORECASE),  # fork bomb
]


def _is_blocked_type(text: str) -> Optional[str]:
    for pat in _BLOCKED_TYPE_PATTERNS:
        if pat.search(text):
            return pat.pattern
    return None


# ---------------------------------------------------------------------------
# Backend selection — env-swappable for tests
# ---------------------------------------------------------------------------

# Per-process cached backend; lazily instantiated on first call.
_backend_lock = threading.Lock()
_backend: Optional[ComputerUseBackend] = None
# Session-scoped approval state.
_session_auto_approve = False
_always_allow: set = set()  # action names the user unlocked for the session


def _get_backend() -> ComputerUseBackend:
    global _backend
    with _backend_lock:
        if _backend is None:
            backend_name = os.environ.get("CLIO_COMPUTER_USE_BACKEND", "cua").lower()
            if backend_name in {"cua", "cua-driver", ""}:
                from tools.computer_use.cua_backend import CuaDriverBackend
                _backend = CuaDriverBackend()
            elif backend_name == "noop":  # pragma: no cover
                _backend = _NoopBackend()
            else:
                raise RuntimeError(f"Unknown CLIO_COMPUTER_USE_BACKEND={backend_name!r}")
            try:
                _backend.start()
            except Exception:
                # Don't cache a backend whose start() failed (e.g. a lazy
                # dependency install was declined / failed). The next call
                # retries cleanly instead of returning a half-initialised
                # backend.
                _backend = None
                raise
        return _backend


def shutdown_backend() -> None:
    """Tear down the cached computer-use backend, if any.

    Stops the cua-driver MCP subprocess + its asyncio bridge thread and clears
    the process-global singleton. A no-op (and import-light) when computer-use
    was never used this process. Called from the agent's close() path so the
    cua-driver child does not linger as an orphan across agent lifecycles — a
    real problem on Windows, where these accumulate.
    """
    global _backend
    with _backend_lock:
        if _backend is not None:
            try:
                _backend.stop()
            except Exception:
                pass
        _backend = None


def reset_backend_for_tests() -> None:  # pragma: no cover
    """Test helper — tear down the cached backend and session approval state."""
    global _session_auto_approve, _always_allow
    shutdown_backend()
    _session_auto_approve = False
    _always_allow = set()


class _NoopBackend(ComputerUseBackend):  # pragma: no cover
    """Test/CI stub. Records calls; returns trivial results."""

    def __init__(self) -> None:
        self.calls: List[Tuple[str, Dict[str, Any]]] = []
        self._started = False

    def start(self) -> None: self._started = True
    def stop(self) -> None: self._started = False
    def is_available(self) -> bool: return True

    def capture(self, mode: str = "som", app: Optional[str] = None) -> CaptureResult:
        self.calls.append(("capture", {"mode": mode, "app": app}))
        return CaptureResult(mode=mode, width=1024, height=768, png_b64=None,
                             elements=[], app=app or "", window_title="")

    def click(self, **kw) -> ActionResult:
        self.calls.append(("click", kw))
        return ActionResult(ok=True, action="click")

    def drag(self, **kw) -> ActionResult:
        self.calls.append(("drag", kw))
        return ActionResult(ok=True, action="drag")

    def scroll(self, **kw) -> ActionResult:
        self.calls.append(("scroll", kw))
        return ActionResult(ok=True, action="scroll")

    def type_text(self, text: str) -> ActionResult:
        self.calls.append(("type", {"text": text}))
        return ActionResult(ok=True, action="type")

    def key(self, keys: str) -> ActionResult:
        self.calls.append(("key", {"keys": keys}))
        return ActionResult(ok=True, action="key")

    def list_apps(self) -> List[Dict[str, Any]]:
        self.calls.append(("list_apps", {}))
        return []

    def list_windows(self, on_screen_only: bool = False) -> List[Dict[str, Any]]:
        self.calls.append(("list_windows", {"on_screen_only": on_screen_only}))
        return []

    def minimize(self, *, pid: Optional[int] = None,
                 window_id: Optional[int] = None) -> ActionResult:
        self.calls.append(("minimize", {"pid": pid, "window_id": window_id}))
        return ActionResult(ok=True, action="minimize")

    def bring_to_front(self, *, pid: int,
                       window_id: Optional[int] = None) -> ActionResult:
        self.calls.append(("bring_to_front", {"pid": pid, "window_id": window_id}))
        return ActionResult(ok=True, action="bring_to_front")

    def focus_app(self, app: str, raise_window: bool = False) -> ActionResult:
        self.calls.append(("focus_app", {"app": app, "raise": raise_window}))
        return ActionResult(ok=True, action="focus_app")

    def set_value(self, value: str, element: Optional[int] = None) -> ActionResult:
        self.calls.append(("set_value", {"value": value, "element": element}))
        return ActionResult(ok=True, action="set_value")

    def page(self, *, pid: Optional[int] = None, action: str,
             **page_args: Any) -> Dict[str, Any]:
        self.calls.append(("page", {"pid": pid, "action": action, **page_args}))
        return {"data": "", "isError": False}

    def page_scroll(self, **kw) -> ActionResult:
        self.calls.append(("page_scroll", kw))
        return ActionResult(ok=True, action="page_scroll")


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def handle_computer_use(args: Dict[str, Any], **kwargs) -> Any:
    """Main entry point — dispatched by tools.registry.

    Returns either a JSON string (text-only) or a dict marked `_multimodal`
    (image + summary) which run_agent.py wraps into the tool message.
    """
    action = (args.get("action") or "").strip().lower()
    if not action:
        return json.dumps({"error": "missing `action`"})
    # Accept common synonyms so model variation doesn't hard-fail.
    action = _ACTION_ALIASES.get(action, action)

    # Safety: validate actions before approval prompt.
    if action == "type":
        text = args.get("text", "")
        pat = _is_blocked_type(text)
        if pat:
            return json.dumps({
                "error": f"blocked pattern in type text: {pat!r}",
                "hint": "Dangerous shell patterns cannot be typed via computer_use.",
            })

    if action == "key":
        keys = args.get("keys", "")
        combo = _canon_key_combo(keys)
        for blocked in _BLOCKED_KEY_COMBOS:
            if blocked.issubset(combo) and len(blocked) <= len(combo):
                return json.dumps({
                    "error": f"blocked key combo: {sorted(blocked)}",
                    "hint": "Destructive system shortcuts are hard-blocked.",
                })

    # Approval gate (destructive actions only). Read-only page sub-actions
    # (text extraction, DOM queries) don't mutate anything — treat them
    # like capture/list_apps.
    needs_approval = action in _DESTRUCTIVE_ACTIONS
    if action == "page" and _canon_page_action(args) in _PAGE_READONLY:
        needs_approval = False
    if needs_approval:
        err = _request_approval(action, args)
        if err is not None:
            return err

    # Dispatch to backend.
    try:
        backend = _get_backend()
    except Exception as e:
        return json.dumps({
            "error": f"computer_use backend unavailable: {e}",
            "hint": "If the cua-driver binary is missing, run `clio computer-use install`. "
                    "If a Python dependency is missing, the error above shows the exact install command.",
        })

    try:
        return _dispatch(backend, action, args)
    except Exception as e:
        logger.exception("computer_use %s failed", action)
        return json.dumps({"error": f"{action} failed: {e}"})


def _request_approval(action: str, args: Dict[str, Any]) -> Optional[str]:
    """Return None if approved, or a JSON error string if denied."""
    global _session_auto_approve, _always_allow
    if _session_auto_approve:
        return None
    if action in _always_allow:
        return None
    cb = _approval_callback
    if cb is None:
        # No CLI approval wired — default allow. Gateway approval is handled
        # one layer out via the normal tool-approval infra.
        return None
    summary = _summarize_action(action, args)
    try:
        verdict = cb(action, args, summary)
    except Exception as e:
        logger.warning("approval callback failed: %s", e)
        verdict = "deny"
    if verdict == "approve_once":
        return None
    if verdict == "approve_session" or verdict == "always_approve":
        _always_allow.add(action)
        if verdict == "always_approve":
            _session_auto_approve = True
        return None
    return json.dumps({"error": "denied by user", "action": action})


def _canon_page_action(args: Dict[str, Any]) -> str:
    """Resolve the `page` sub-action, accepting common synonyms."""
    sub = str(args.get("page_action") or args.get("subaction") or "").strip().lower()
    return _PAGE_ACTION_ALIASES.get(sub, sub)


def _summarize_action(action: str, args: Dict[str, Any]) -> str:
    if action in {"click", "double_click", "right_click", "middle_click"}:
        if args.get("element") is not None:
            return f"{action} element #{args['element']}"
        coord = args.get("coordinate")
        if coord:
            return f"{action} at {tuple(coord)}"
        return action
    if action == "drag":
        src = args.get("from_element") or args.get("from_coordinate")
        dst = args.get("to_element") or args.get("to_coordinate")
        return f"drag {src} → {dst}"
    if action == "scroll":
        unit = " pages" if args.get("by") == "page" else ""
        return f"scroll {args.get('direction', '?')} x{args.get('amount', 3)}{unit}"
    if action == "page":
        sub = _canon_page_action(args)
        if sub == "scroll":
            if args.get("to") in ("top", "bottom"):
                return f"page scroll to {args['to']}"
            px = args.get("amount_px")
            return (f"page scroll {args.get('direction', 'down')}"
                    + (f" {px}px" if px else ""))
        if sub in {"click", "query"}:
            return f"page {sub} {str(args.get('selector', ''))[:60]!r}"
        if sub == "js":
            js = str(args.get("javascript", ""))
            return f"page js {js[:60]!r}" + ("..." if len(js) > 60 else "")
        return f"page {sub or '?'}"
    if action == "type":
        text = args.get("text", "")
        return f"type {text[:60]!r}" + ("..." if len(text) > 60 else "")
    if action == "key":
        return f"key {args.get('keys', '')!r}"
    if action == "focus_app":
        return f"focus {args.get('app', '')!r}" + (" (raise)" if args.get("raise_window") else "")
    return action


def _coerce_point(val: Any) -> Optional[Tuple[int, int]]:
    """Coerce a [x, y]-ish value to an (x, y) tuple, or None."""
    if isinstance(val, (list, tuple)) and len(val) >= 2:
        try:
            return (int(val[0]), int(val[1]))
        except (TypeError, ValueError):
            return None
    return None


def _normalize_drag_args(
    args: Dict[str, Any]
) -> Tuple[Optional[int], Optional[int], Optional[Tuple[int, int]], Optional[Tuple[int, int]]]:
    """Resolve drag source/target across the many shapes models emit.

    Canonical params are from_element/to_element and from_coordinate/
    to_coordinate, but models frequently use from/to, start/end, or
    source/target — and pass either an element index (int) or a coordinate
    ([x, y]). Resolve all of them to (from_element, to_element, from_xy,
    to_xy).
    """
    from_keys = ("from_element", "source_element", "start_element")
    to_keys = ("to_element", "target_element", "end_element")
    from_coord_keys = (
        "from_coordinate", "source_coordinate", "start_coordinate", "from_coord",
    )
    to_coord_keys = (
        "to_coordinate", "target_coordinate", "end_coordinate", "to_coord",
    )
    # Generic from/to that may carry either an element int or a coordinate.
    from_generic = ("from", "source", "start")
    to_generic = ("to", "target", "end")

    def first_int(keys) -> Optional[int]:
        for k in keys:
            v = args.get(k)
            if isinstance(v, bool):
                continue
            if isinstance(v, int):
                return v
            if isinstance(v, str) and v.strip().lstrip("-").isdigit():
                return int(v)
        return None

    def first_point(keys) -> Optional[Tuple[int, int]]:
        for k in keys:
            pt = _coerce_point(args.get(k))
            if pt is not None:
                return pt
        return None

    from_element = first_int(from_keys)
    to_element = first_int(to_keys)
    from_xy = first_point(from_coord_keys)
    to_xy = first_point(to_coord_keys)

    # Generic from/to: int -> element, list -> coordinate.
    if from_element is None and from_xy is None:
        from_element = first_int(from_generic)
        if from_element is None:
            from_xy = first_point(from_generic)
    if to_element is None and to_xy is None:
        to_element = first_int(to_generic)
        if to_element is None:
            to_xy = first_point(to_generic)

    # `coordinate` as the source paired with `to_coordinate`/`to` as target.
    if from_element is None and from_xy is None:
        from_xy = _coerce_point(args.get("coordinate"))

    return from_element, to_element, from_xy, to_xy


def _dispatch(backend: ComputerUseBackend, action: str, args: Dict[str, Any]) -> Any:
    capture_after = bool(args.get("capture_after"))
    # Post-action verification defaults to the fast AX tree (text, no
    # screenshot). The model can opt back into a screenshot for visual
    # verification with capture_after_mode='som' (or 'vision').
    follow_mode = str(args.get("capture_after_mode", "ax"))
    if follow_mode not in {"som", "vision", "ax"}:
        follow_mode = "ax"

    if action == "capture":
        mode = str(args.get("mode", "som"))
        if mode not in {"som", "vision", "ax"}:
            return json.dumps({"error": f"bad mode {mode!r}; use som|vision|ax"})
        cap = backend.capture(mode=mode, app=args.get("app"))
        return _capture_response(cap, max_elements=_coerce_max_elements(args.get("max_elements")))

    if action == "wait":
        seconds = float(args.get("seconds", 1.0))
        res = backend.wait(seconds)
        return _text_response(res)

    if action == "list_apps":
        apps = backend.list_apps()
        return json.dumps({"apps": apps, "count": len(apps)})

    if action == "focus_app":
        app = args.get("app")
        if not app:
            return json.dumps({"error": "focus_app requires `app`"})
        res = backend.focus_app(app, raise_window=bool(args.get("raise_window")))
        return _maybe_follow_capture(backend, res, capture_after, follow_mode)

    if action == "list_windows":
        wins = backend.list_windows(
            on_screen_only=bool(args.get("on_screen_only", False))
        )
        return json.dumps({"windows": wins, "count": len(wins)})

    if action == "focus_window":
        pid = args.get("pid")
        wid = args.get("window_id")
        app = args.get("app")
        if pid is not None:
            res = backend.bring_to_front(
                pid=int(pid),
                window_id=int(wid) if wid is not None else None,
            )
        elif app:
            res = backend.focus_app(app, raise_window=True)
        else:
            return json.dumps({
                "error": "focus_window requires pid (+ window_id) or app",
            })
        return _maybe_follow_capture(backend, res, capture_after, follow_mode)

    if action == "minimize":
        pid = args.get("pid")
        wid = args.get("window_id")
        app = args.get("app")
        if pid is None and app:
            backend.focus_app(app)  # resolve to active pid/window_id
        res = backend.minimize(
            pid=int(pid) if pid is not None else None,
            window_id=int(wid) if wid is not None else None,
        )
        return _maybe_follow_capture(backend, res, capture_after, follow_mode)

    if action in {"click", "double_click", "right_click", "middle_click"}:
        button = args.get("button")
        click_count = 1
        if action == "double_click":
            click_count = 2
        elif action == "right_click":
            button = "right"
        elif action == "middle_click":
            button = "middle"
        else:
            button = button or "left"
        element = args.get("element")
        coord = args.get("coordinate") or (None, None)
        x, y = (coord[0], coord[1]) if coord and coord[0] is not None else (None, None)
        res = backend.click(
            element=element if element is not None else None,
            x=x, y=y, button=button or "left", click_count=click_count,
            modifiers=args.get("modifiers"),
        )
        # If a double_click by element didn't take but the model also gave a
        # coordinate (off the SOM screenshot), retry by pixel — that path is
        # coordinate-space-correct (mapped via _to_screen_xy) and rescues the
        # common "open the icon" gesture when element resolution misses.
        if (
            not res.ok
            and click_count == 2
            and element is not None
            and x is not None
            and y is not None
        ):
            res = backend.click(
                element=None, x=x, y=y, button=button or "left",
                click_count=2, modifiers=args.get("modifiers"),
            )
        return _maybe_follow_capture(backend, res, capture_after, follow_mode)

    if action == "drag":
        from_element, to_element, from_xy, to_xy = _normalize_drag_args(args)
        has_source = from_element is not None or from_xy is not None
        has_target = to_element is not None or to_xy is not None
        if not (has_source and has_target):
            return json.dumps({
                "error": "drag needs a source AND a target.",
                "hint": "By visible element: drag from_element=3 to_element=7. "
                        "By pixel: drag from_coordinate=[120,340] "
                        "to_coordinate=[800,340]. Run capture(mode='som') first "
                        "to get element numbers.",
            })
        res = backend.drag(
            from_element=from_element,
            to_element=to_element,
            from_xy=from_xy,
            to_xy=to_xy,
            button=args.get("button", "left"),
            modifiers=args.get("modifiers"),
        )
        return _maybe_follow_capture(backend, res, capture_after, follow_mode)

    if action == "scroll":
        coord = args.get("coordinate") or (None, None)
        by = args.get("by")
        res = backend.scroll(
            direction=args.get("direction", "down"),
            amount=int(args.get("amount", 3)),
            element=args.get("element"),
            x=coord[0] if coord and coord[0] is not None else None,
            y=coord[1] if coord and coord[1] is not None else None,
            modifiers=args.get("modifiers"),
            by=by if by in ("line", "page") else None,
        )
        return _maybe_follow_capture(backend, res, capture_after, follow_mode)

    if action == "page":
        return _dispatch_page(backend, args, capture_after, follow_mode)

    if action == "type":
        res = backend.type_text(args.get("text", ""))
        return _maybe_follow_capture(backend, res, capture_after, follow_mode)

    if action == "key":
        res = backend.key(args.get("keys", ""))
        return _maybe_follow_capture(backend, res, capture_after, follow_mode)

    if action == "set_value":
        value = args.get("value")
        if value is None:
            return json.dumps({"error": "set_value requires `value`"})
        res = backend.set_value(value=str(value), element=args.get("element"))
        return _maybe_follow_capture(backend, res, capture_after, follow_mode)

    return json.dumps({"error": f"unknown action {action!r}"})


# Default / max cap on text returned by page read/query/js. Feed pages
# (Facebook, X, …) can carry hundreds of KB of visible text; uncapped
# extraction would blow the session context in one call.
_PAGE_DEFAULT_MAX_CHARS = 10_000
_PAGE_MAX_MAX_CHARS = 100_000

_PAGE_UNAVAILABLE_HINT = (
    "Browser page access needs a supported bridge: Chromium browsers "
    "(Chrome/Edge/Brave/Electron) on Windows/Linux need to be launched with "
    "--remote-debugging-port=9222 for scroll/click/js; macOS drives "
    "Safari/Chrome via Apple Events (see enable_javascript_apple_events). "
    "Text extraction (page_action='read'/'query') may still work via the "
    "accessibility tree. Otherwise fall back to action='scroll' (wheel) + "
    "capture."
)


def _coerce_page_max_chars(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return _PAGE_DEFAULT_MAX_CHARS
    if n < 1:
        return _PAGE_DEFAULT_MAX_CHARS
    return min(n, _PAGE_MAX_MAX_CHARS)


def _page_response(out: Dict[str, Any], sub: str, max_chars: int) -> str:
    """Normalize a raw cua-driver `page` result into the model-facing JSON."""
    is_err = bool(out.get("isError"))
    data = out.get("structuredContent") or out.get("data")
    if isinstance(data, (dict, list)):
        text = json.dumps(data, ensure_ascii=False)
    else:
        text = str(data) if data is not None else ""
    payload: Dict[str, Any] = {"ok": not is_err, "page_action": sub}
    if len(text) > max_chars:
        payload["result"] = text[:max_chars]
        payload["truncated"] = True
        payload["total_chars"] = len(text)
        payload["note"] = (
            f"result truncated to {max_chars} of {len(text)} chars; raise "
            "max_chars or narrow with selector="
        )
    else:
        payload["result"] = text
    if is_err:
        payload["hint"] = _PAGE_UNAVAILABLE_HINT
    return json.dumps(payload)


def _dispatch_page(backend: ComputerUseBackend, args: Dict[str, Any],
                   capture_after: bool, follow_mode: str) -> Any:
    """Route action='page' to the browser-page bridge.

    Sub-actions: scroll (deterministic pixel scroll + metrics), read (visible
    text), query (DOM query by CSS), click (CSS click), js (arbitrary JS).
    """
    sub = _canon_page_action(args)
    if sub not in {"scroll", "read", "query", "click", "js"}:
        return json.dumps({
            "error": f"unknown page_action {sub or '(missing)'!r}",
            "hint": "use page_action='scroll'|'read'|'query'|'click'|'js'",
        })
    pid = args.get("pid")
    pid = int(pid) if pid is not None else None
    max_chars = _coerce_page_max_chars(args.get("max_chars"))

    if sub == "scroll":
        res = backend.page_scroll(
            pid=pid,
            direction=str(args.get("direction", "down")),
            amount_px=(int(args["amount_px"])
                       if args.get("amount_px") is not None else None),
            selector=args.get("selector"),
            to=args.get("to"),
        )
        if not res.ok:
            res.message = (f"{res.message} | {_PAGE_UNAVAILABLE_HINT}"
                           if res.message else _PAGE_UNAVAILABLE_HINT)
        return _maybe_follow_capture(backend, res, capture_after, follow_mode)

    if sub == "read":
        out = backend.page(pid=pid, action="get_text")
        return _page_response(out, sub, max_chars)

    if sub == "query":
        selector = args.get("selector") or args.get("css_selector")
        if not selector:
            return json.dumps({"error": "page query requires `selector`"})
        page_args: Dict[str, Any] = {"css_selector": str(selector)}
        attributes = args.get("attributes")
        if isinstance(attributes, list) and attributes:
            page_args["attributes"] = [str(a) for a in attributes]
        out = backend.page(pid=pid, action="query_dom", **page_args)
        return _page_response(out, sub, max_chars)

    if sub == "click":
        selector = args.get("selector")
        if not selector:
            return json.dumps({"error": "page click requires `selector`"})
        out = backend.page(pid=pid, action="click_element",
                           selector=str(selector))
        is_err = bool(out.get("isError"))
        data = out.get("data")
        res = ActionResult(
            ok=not is_err, action="page_click",
            message=str(data)[:500] if isinstance(data, str) else "",
        )
        if is_err:
            res.message = (f"{res.message} | {_PAGE_UNAVAILABLE_HINT}"
                           if res.message else _PAGE_UNAVAILABLE_HINT)
        return _maybe_follow_capture(backend, res, capture_after, follow_mode)

    # sub == "js"
    javascript = args.get("javascript") or args.get("js")
    if not javascript:
        return json.dumps({"error": "page js requires `javascript`"})
    out = backend.page(pid=pid, action="execute_javascript",
                       javascript=str(javascript))
    return _page_response(out, sub, max_chars)


# ---------------------------------------------------------------------------
# Response shaping
# ---------------------------------------------------------------------------

def _text_response(res: ActionResult) -> str:
    payload: Dict[str, Any] = {"ok": res.ok, "action": res.action}
    if res.message:
        payload["message"] = res.message
    if res.meta:
        payload["meta"] = res.meta
    return json.dumps(payload)


# Default cap for the AX `elements` array returned by capture. Dense UIs
# (Electron apps, Obsidian, JetBrains IDEs) can publish 500+ AX nodes, which
# can exhaust session context after a single capture. The model-facing
# `max_elements` argument lets callers raise this when they need the full tree.
_DEFAULT_MAX_ELEMENTS = 100
# Hard upper bound on caller-supplied `max_elements`. Without this, a tool
# call passing a very large integer would silently disable the safeguard and
# reintroduce the original unbounded behavior.
_MAX_ALLOWED_MAX_ELEMENTS = 1000
_MIN_PROVIDER_IMAGE_DIMENSION = 8


def _image_dimensions_from_b64(image_b64: str) -> Optional[Tuple[int, int]]:
    """Return (width, height) for common inline screenshot formats.

    Some providers reject images below 8x8 before the model sees the tool
    result. Inspecting the encoded bytes here lets computer_use fall back to
    its AX/SOM text payload instead of sending an unusable placeholder.
    """
    if not image_b64:
        return None
    try:
        raw = base64.b64decode(image_b64, validate=False)
    except Exception:
        return None

    # PNG: signature + IHDR width/height.
    if raw.startswith(b"\x89PNG\r\n\x1a\n") and len(raw) >= 24:
        try:
            width, height = struct.unpack(">II", raw[16:24])
            return int(width), int(height)
        except Exception:
            return None

    # JPEG: scan for SOF markers that carry dimensions.
    if raw.startswith(b"\xff\xd8") and len(raw) > 4:
        i = 2
        while i + 9 < len(raw):
            if raw[i] != 0xFF:
                i += 1
                continue
            marker = raw[i + 1]
            i += 2
            while marker == 0xFF and i < len(raw):
                marker = raw[i]
                i += 1
            if marker in {0xD8, 0xD9}:
                continue
            if marker == 0xDA:
                break
            if i + 2 > len(raw):
                break
            segment_len = int.from_bytes(raw[i:i + 2], "big")
            if segment_len < 2 or i + segment_len > len(raw):
                break
            if marker in {
                0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
            } and segment_len >= 7:
                height = int.from_bytes(raw[i + 3:i + 5], "big")
                width = int.from_bytes(raw[i + 5:i + 7], "big")
                return int(width), int(height)
            i += segment_len
    return None


def _coerce_max_elements(value: Any) -> int:
    """Validate the caller-supplied ``max_elements``.

    Falls back to :data:`_DEFAULT_MAX_ELEMENTS` for missing / non-integer /
    sub-1 inputs so the cap can never be silently disabled by a malformed
    tool-call argument. Clamps oversized values to
    :data:`_MAX_ALLOWED_MAX_ELEMENTS` so a caller cannot bypass the
    safeguard by passing a very large integer.
    """
    if value is None:
        return _DEFAULT_MAX_ELEMENTS
    try:
        n = int(value)
    except (TypeError, ValueError):
        return _DEFAULT_MAX_ELEMENTS
    if n < 1:
        return _DEFAULT_MAX_ELEMENTS
    if n > _MAX_ALLOWED_MAX_ELEMENTS:
        return _MAX_ALLOWED_MAX_ELEMENTS
    return n


def _compute_scroll_state(
    elements: List[UIElement],
    window_rect: Optional[Tuple[int, int, int, int]],
) -> Optional[Dict[str, Any]]:
    """Detect content extending past the visible viewport.

    AT-SPI/UIA/AX trees include nodes that are scrolled out of view; their
    frames land outside the window rect. Counting them gives the model the
    signal it otherwise lacks — "this form/page continues below the fold" —
    without any extra driver round-trip.

    Element frames are screen-global on most driver builds but some AT-SPI
    toolkits report window-local coordinates; disambiguate by majority vote
    on which interpretation fits the elements horizontally (the x-axis
    rarely scrolls). Returns None when there is no positive evidence of
    off-viewport content — absence of a scroll_state is NOT proof the page
    ends (some browsers prune far-off-screen AX nodes).
    """
    if not window_rect or not elements:
        return None
    wx, wy, ww, wh = window_rect
    if ww <= 0 or wh <= 0:
        return None
    sized = [e for e in elements if e.bounds[2] > 0 and e.bounds[3] > 0]
    if not sized:
        return None

    slack = 2
    fit_global = sum(
        1 for e in sized
        if wx - slack <= e.bounds[0] and e.bounds[0] + e.bounds[2] <= wx + ww + slack
    )
    fit_local = sum(
        1 for e in sized
        if -slack <= e.bounds[0] and e.bounds[0] + e.bounds[2] <= ww + slack
    )
    # Tie goes to screen-global — the documented cua-driver frame space.
    origin_x, origin_y = (wx, wy) if fit_global >= fit_local else (0, 0)
    bottom = origin_y + wh
    right = origin_x + ww

    below = [e for e in sized if e.bounds[1] >= bottom - 1]
    above = [e for e in sized if e.bounds[1] + e.bounds[3] <= origin_y + 1]
    beside = [e for e in sized if e.bounds[0] >= right - 1]
    scrollbars = [e.index for e in elements if "scroll" in e.role.lower()]

    if not below and not above and not beside and not scrollbars:
        return None
    state: Dict[str, Any] = {}
    if below:
        state["content_below"] = len(below)
        sample = [
            f"#{e.index} {e.role} {e.label[:40]!r}" for e in below[:3]
        ]
        state["below_sample"] = sample
    if above:
        state["content_above"] = len(above)
    if beside:
        state["content_right"] = len(beside)
    if scrollbars:
        state["scrollbar_elements"] = scrollbars[:8]
    return state


def _scroll_state_summary(state: Dict[str, Any]) -> Optional[str]:
    parts: List[str] = []
    below = state.get("content_below")
    if below:
        sample = ", ".join(state.get("below_sample", [])[:3])
        parts.append(
            f"⚠ {below} element(s) extend BELOW the visible area"
            + (f" (e.g. {sample})" if sample else "")
            + " — scroll down before assuming the page/form ends here"
        )
    above = state.get("content_above")
    if above:
        parts.append(f"{above} element(s) are above the viewport (scroll up to reach)")
    if not parts:
        return None
    return "  " + "; ".join(parts)


def _capture_response(cap: CaptureResult, max_elements: int = _DEFAULT_MAX_ELEMENTS) -> Any:
    total_elements = len(cap.elements)
    visible_elements = cap.elements[:max_elements]
    truncated_elements = max(0, total_elements - len(visible_elements))
    image_dimensions = _image_dimensions_from_b64(cap.png_b64 or "") if cap.png_b64 else None
    response_width = image_dimensions[0] if image_dimensions else cap.width
    response_height = image_dimensions[1] if image_dimensions else cap.height
    image_too_small = bool(
        image_dimensions
        and (
            image_dimensions[0] < _MIN_PROVIDER_IMAGE_DIMENSION
            or image_dimensions[1] < _MIN_PROVIDER_IMAGE_DIMENSION
        )
    )

    # Index only what's actually surfaced in the response — otherwise the
    # human-readable summary references element indices the model cannot
    # find in the JSON `elements` array (e.g. max_elements=10 vs the default
    # 40-line index window).
    element_index = _format_elements(visible_elements)
    summary_lines = [
        f"capture mode={cap.mode} {response_width}x{response_height}"
        + (f" app={cap.app}" if cap.app else "")
        + (f" window={cap.window_title!r}" if cap.window_title else ""),
        f"{total_elements} interactable element(s):",
    ]
    if element_index:
        summary_lines.extend(element_index)
    # Off-viewport content warning — computed over the FULL element list
    # (not the max_elements-truncated view) so a long form's below-the-fold
    # fields register even when the response is capped.
    scroll_state = _compute_scroll_state(cap.elements, cap.window_rect)
    scroll_state_line = _scroll_state_summary(scroll_state) if scroll_state else None
    if scroll_state_line:
        summary_lines.append(scroll_state_line)
    # Multimodal and AX paths both reference `summary`; build it once up-front
    # so the aux-vision routing branch (which fires before either path is
    # selected) has a valid value to hand to _route_capture_through_aux_vision.
    # The AX path appends the "truncated to N of M" note to summary_lines
    # below and rebuilds; the multimodal path keeps this version untouched.
    if image_too_small:
        summary_lines.append(
            f"  (screenshot omitted: {image_dimensions[0]}x{image_dimensions[1]} "
            f"is below the {_MIN_PROVIDER_IMAGE_DIMENSION}x{_MIN_PROVIDER_IMAGE_DIMENSION} "
            "provider minimum)"
        )
    summary = "\n".join(summary_lines)

    if cap.png_b64 and cap.mode != "ax" and not image_too_small:
        # Decide whether to hand the screenshot to the auxiliary.vision
        # pipeline (text-only result) or keep the multimodal envelope (main
        # model handles vision natively). Issue #24015: previously the
        # multimodal envelope was returned unconditionally, so non-vision
        # main models tripped HTTP 404 / 400 at the provider boundary even
        # when auxiliary.vision was explicitly configured to handle this.
        if _should_route_through_aux_vision():
            routed = _route_capture_through_aux_vision(cap, summary)
            if routed is not None:
                return routed
            # Aux routing was requested but failed (vision node down, aux call
            # raised, empty analysis, etc.). Routing being requested means the
            # main model may not be able to consume images; falling through to
            # the multimodal envelope can break the capture with a provider
            # error. Degrade to the AX/SOM text payload instead so element
            # indices remain usable while vision is unavailable.
            summary_lines.append(
                "  (vision unavailable: the auxiliary vision model could not "
                "be reached; screenshot omitted. Element-index actions still "
                "work — drive via the element list above.)"
            )
            if truncated_elements:
                summary_lines.append(
                    f"  (response truncated to {len(visible_elements)} of "
                    f"{total_elements} elements; raise max_elements or pass "
                    "app= to narrow)"
                )
            payload = {
                "mode": cap.mode,
                "width": response_width,
                "height": response_height,
                "app": cap.app,
                "window_title": cap.window_title,
                "elements": [_element_to_dict(e) for e in visible_elements],
                "total_elements": total_elements,
                "summary": "\n".join(summary_lines),
                "vision_unavailable": True,
            }
            if scroll_state:
                payload["scroll_state"] = scroll_state
            if truncated_elements:
                payload["truncated_elements"] = truncated_elements
            return json.dumps(payload)

        # Prefer the explicit MIME type cua-driver attaches to its image
        # parts (Surface 7 of the cua-driver integration — trycua/cua#1961
        # made `mimeType` part of every MCP image-part response). Fall back
        # to base64-prefix sniffing for older cua-driver builds that didn't
        # carry the field. JPEG base64 starts with /9j/; PNG with iVBOR.
        _mime = cap.image_mime_type
        if not _mime:
            _b64_prefix = cap.png_b64[:8]
            _mime = "image/jpeg" if _b64_prefix.startswith("/9j/") else "image/png"
        # The multimodal response carries the screenshot, not the AX
        # elements array, so a "response truncated to N of M elements"
        # note would be inaccurate — skip it on this branch.
        return {
            "_multimodal": True,
            "content": [
                {"type": "text", "text": summary},
                {"type": "image_url",
                 "image_url": {"url": f"data:{_mime};base64,{cap.png_b64}"}},
            ],
            "text_summary": summary,
            "meta": {"mode": cap.mode, "width": response_width, "height": response_height,
                     "elements": total_elements, "png_bytes": cap.png_bytes_len,
                     **({"scroll_state": scroll_state} if scroll_state else {})},
        }
    # AX-only (or image-missing fallback): text path actually carries the
    # `elements` array, so the truncation note applies here.
    if truncated_elements:
        summary_lines.append(
            f"  (response truncated to {len(visible_elements)} of {total_elements} elements; "
            f"raise max_elements or pass app= to narrow)"
        )
    summary = "\n".join(summary_lines)
    payload: Dict[str, Any] = {
        "mode": cap.mode,
        "width": response_width,
        "height": response_height,
        "app": cap.app,
        "window_title": cap.window_title,
        "elements": [_element_to_dict(e) for e in visible_elements],
        "total_elements": total_elements,
        "summary": summary,
    }
    if scroll_state:
        payload["scroll_state"] = scroll_state
    if truncated_elements:
        payload["truncated_elements"] = truncated_elements
    return json.dumps(payload)


# ---------------------------------------------------------------------------
# auxiliary.vision routing for captured screenshots (#24015)
# ---------------------------------------------------------------------------

# Longest image side handed to the aux vision model. Full-resolution desktop
# captures tokenize heavily and can overflow small local-model context windows;
# ~1456px keeps SOM badges legible while cutting per-capture vision latency.
_MAX_VISION_DIM = 1456


def _shrink_capture_for_vision(raw: bytes, ext: str,
                               max_dim: int = _MAX_VISION_DIM) -> bytes:
    """Downscale encoded image bytes so the longest side is <= max_dim.

    Returns the original bytes unchanged when the image already fits or when
    Pillow is unavailable/fails — no worse than the pre-shrink behavior.
    """
    try:
        from io import BytesIO
        from PIL import Image
        img = Image.open(BytesIO(raw))
        if max(img.size) <= max_dim:
            return raw
        img.thumbnail((max_dim, max_dim))
        out = BytesIO()
        img.save(out, format="JPEG" if ext == ".jpg" else "PNG")
        return out.getvalue()
    except Exception as exc:
        logger.debug("computer_use: vision downscale skipped: %s", exc)
        return raw

def _should_route_through_aux_vision() -> bool:
    """Return True when ``_capture_response`` should hand the PNG to aux vision.

    Reads the active main provider/model and the loaded config and asks the
    routing helper. Any failure (config import, runtime override missing,
    etc.) returns False so the existing multimodal envelope continues to be
    returned — fail open on the routing decision so a broken config can
    never silently drop the screenshot for vision-capable main models.
    """
    try:
        from agent.auxiliary_client import _read_main_model, _read_main_provider
        from clio_cli.config import load_config
        from tools.computer_use.vision_routing import (
            should_route_capture_to_aux_vision,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("computer_use: aux-vision routing import failed: %s", exc)
        return False
    try:
        provider = _read_main_provider()
        model = _read_main_model()
        cfg = load_config()
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("computer_use: aux-vision routing config read failed: %s", exc)
        return False
    try:
        return bool(should_route_capture_to_aux_vision(provider, model, cfg))
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("computer_use: aux-vision routing decision failed: %s", exc)
        return False


def _route_capture_through_aux_vision(
    cap: CaptureResult,
    summary: str,
) -> Optional[str]:
    """Pre-analyse the captured PNG via ``vision_analyze`` and return a text result.

    The captured base64 PNG is materialised to ``$CLIO_HOME/cache/vision/``
    and handed to ``vision_analyze_tool`` with a generic describe prompt.
    The resulting text description is merged into the existing AX/SOM
    summary so the main model receives a single text payload that mentions
    every interactable element AND a description of what the screenshot
    looked like.

    Returns:
      A JSON-encoded text response on success.
      ``None`` on failure (caller falls back to the multimodal envelope).
    """
    if not cap.png_b64:
        return None
    try:
        import base64 as _base64
        import os as _os
        import uuid as _uuid

        from clio_constants import get_clio_dir
        from model_tools import _run_async
        from tools.vision_tools import vision_analyze_tool
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("computer_use: aux-vision import failed: %s", exc)
        return None

    temp_image_path = None
    try:
        try:
            raw = _base64.b64decode(cap.png_b64, validate=False)
        except Exception as exc:
            logger.debug("computer_use: failed to decode capture base64: %s", exc)
            return None

        # Pick an extension that matches the on-disk bytes so vision_analyze's
        # MIME sniffing returns the right content-type.
        # Surface 7: prefer the explicit MIME type cua-driver supplied.
        _mime_for_ext = cap.image_mime_type or ""
        if _mime_for_ext == "image/jpeg" or (not _mime_for_ext and cap.png_b64[:8].startswith("/9j/")):
            ext = ".jpg"
        else:
            ext = ".png"
        cache_dir = get_clio_dir("cache/vision", "temp_vision_images")
        cache_dir.mkdir(parents=True, exist_ok=True)
        temp_image_path = cache_dir / f"computer_use_{_uuid.uuid4().hex}{ext}"
        raw = _shrink_capture_for_vision(raw, ext)
        temp_image_path.write_bytes(raw)

        prompt = (
            "Describe what is visible in this desktop application screenshot in "
            "concise but specific terms. Mention the app name and window "
            "title if visible, the overall layout, any labelled buttons, "
            "menus or text fields, and any prominent text content the user "
            "would need to know about. Do not invent details that are not "
            "actually visible.\n\n"
            f"AX/SOM index for cross-reference:\n{summary}"
        )

        result_json = _run_async(
            vision_analyze_tool(str(temp_image_path), prompt)
        )
    except Exception as exc:
        logger.warning(
            "computer_use: auxiliary.vision pre-analysis failed (%s); "
            "returning to caller without aux analysis",
            exc,
        )
        return None
    finally:
        if temp_image_path is not None:
            try:
                _os.unlink(str(temp_image_path))
            except Exception:
                pass

    analysis_text = ""
    if isinstance(result_json, str):
        try:
            parsed = json.loads(result_json)
            if isinstance(parsed, dict):
                analysis_text = str(parsed.get("analysis") or "").strip()
        except (TypeError, json.JSONDecodeError):
            analysis_text = result_json.strip()

    if not analysis_text:
        return None

    return json.dumps({
        "mode": cap.mode,
        "width": cap.width,
        "height": cap.height,
        "app": cap.app,
        "window_title": cap.window_title,
        "elements": [_element_to_dict(e) for e in cap.elements],
        "summary": summary,
        "vision_analysis": analysis_text,
        "vision_analysis_routed_via": "auxiliary.vision",
    })


def _maybe_follow_capture(
    backend: ComputerUseBackend, res: ActionResult, do_capture: bool,
    mode: str = "ax",
) -> Any:
    if not do_capture:
        return _text_response(res)
    # Skip the follow-up capture when the action itself failed: showing a
    # normal-looking screenshot after a failure misleads the model into thinking
    # the action succeeded. Return the error text instead.
    if not res.ok:
        return _text_response(res)
    try:
        # Preserve the app context established by the preceding capture/focus_app so
        # that capture_after=True re-captures the same app rather than the frontmost
        # window (which may have changed if the action caused a focus shift).
        # Default to the fast AX tree (no screenshot); the caller passes
        # mode='som'/'vision' only when a visual check is needed.
        last_app = getattr(backend, "_last_app", None)
        cap = backend.capture(mode=mode, app=last_app)
    except Exception as e:
        logger.warning("follow-up capture failed: %s", e)
        return _text_response(res)
    # Combine action summary with the capture.
    resp = _capture_response(cap)
    if isinstance(resp, dict) and resp.get("_multimodal"):
        prefix = f"[{res.action}] ok={res.ok}" + (f" — {res.message}" if res.message else "")
        resp["content"][0]["text"] = prefix + "\n\n" + resp["content"][0]["text"]
        resp["text_summary"] = prefix + "\n\n" + resp["text_summary"]
        return resp
    # Fallback: action + text capture merged.
    try:
        data = json.loads(resp)
    except (TypeError, json.JSONDecodeError):
        data = {"capture": resp}
    data["action"] = res.action
    data["ok"] = res.ok
    if res.message:
        data["message"] = res.message
    return json.dumps(data)


def _format_elements(elements: List[UIElement], max_lines: int = 40) -> List[str]:
    out: List[str] = []
    for e in elements[:max_lines]:
        label = e.label.replace("\n", " ")[:60]
        out.append(f"  #{e.index} {e.role} {label!r} @ {e.bounds}"
                   + (f" [{e.app}]" if e.app else ""))
    if len(elements) > max_lines:
        out.append(f"  ... +{len(elements) - max_lines} more (call capture with app= to narrow)")
    return out


def _element_to_dict(e: UIElement) -> Dict[str, Any]:
    return {
        "index": e.index,
        "role": e.role,
        "label": e.label,
        "bounds": list(e.bounds),
        "app": e.app,
    }


# ---------------------------------------------------------------------------
# Availability check (used by the tool registry check_fn)
# ---------------------------------------------------------------------------

def check_computer_use_requirements() -> bool:
    """Return True iff computer_use can run on this host.

    Conditions: macOS, Windows, or Linux + cua-driver binary installed (or
    override via env). cua-driver runs on all three; the Linux path is
    headed/X11 today (Wayland via XWayland), pure-Wayland progress tracked
    upstream. Linux users see specific blocked checks via
    `clio computer-use doctor` if their session is incomplete (e.g. no
    DISPLAY set).
    """
    if sys.platform not in ("darwin", "win32", "linux"):
        return False
    from tools.computer_use.cua_backend import cua_driver_binary_available
    return cua_driver_binary_available()


def get_computer_use_schema() -> Dict[str, Any]:
    from tools.computer_use.schema import COMPUTER_USE_SCHEMA
    return COMPUTER_USE_SCHEMA
