"""Cua-driver backend (macOS, Windows, Linux).

Speaks MCP over stdio to `cua-driver`. The Python `mcp` SDK is async, so we
run a dedicated asyncio event loop on a background thread and marshal sync
calls through it.

The same `cua-driver call <tool>` surface (click, type_text, hotkey, drag,
scroll, screenshot, launch_app, list_apps, list_windows, get_window_state,
move_cursor, wait) works identically across macOS, Windows, and Linux —
cua-driver's PARITY matrix marks the action tools VERIFIED on macOS and
Windows in the cross-platform Rust port (`cua-driver-rs`).

Linux is the most recent runtime (X11 today, Wayland via XWayland; pure-
Wayland progress tracked upstream). It is enabled in
`check_computer_use_requirements` alongside macOS and Windows. The plumbing
in this file is OS-agnostic; per-host gaps (no DISPLAY, missing AT-SPI,
etc.) surface as specific blocked checks via `clio computer-use doctor`
rather than failing silently.

Install:
  - **macOS**:
      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/trycua/cua/main/libs/cua-driver/scripts/install.sh)"
  - **Windows** (PowerShell):
      irm https://raw.githubusercontent.com/trycua/cua/main/libs/cua-driver/scripts/install.ps1 | iex

After install, `cua-driver` is on $PATH and supports `cua-driver mcp` (stdio
transport) which is what we invoke.

The macOS path uses private SkyLight SPIs (SLEventPostToPid,
SLPSPostEventRecordTo, _AXObserverAddNotificationAndCheckRemote) that aren't
Apple-public and can break on OS updates. The Windows path in cua-driver-rs
uses stable Win32 APIs (SendInput + UI Automation) — not subject to the
same SPI breakage class.
"""

from __future__ import annotations

import asyncio
import base64
import concurrent.futures
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

from tools.computer_use.backend import (
    ActionResult,
    CaptureResult,
    ComputerUseBackend,
    UIElement,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Update checking
# ---------------------------------------------------------------------------
#
# cua-driver ships a native `check-update` verb (and a `check_for_update` MCP
# tool) that compares the installed binary against the latest GitHub release —
# the source of truth — and caches the result (~20h). We prefer that over a
# hardcoded version floor, which would rot and can't know what "latest" is.
#
# There is intentionally no version *pin* knob: the upstream installer always
# fetches the latest release, so a `CLIO_CUA_DRIVER_VERSION` env var would
# only have *looked* like it pinned. For a reproducible version, point
# `CLIO_CUA_DRIVER_CMD` at a specific binary instead.

_CUA_DRIVER_CMD = os.environ.get("CLIO_CUA_DRIVER_CMD", "cua-driver")
_CUA_DRIVER_ARGS = ["mcp"]  # stdio MCP transport (fallback when the
                            # driver doesn't expose `manifest` — see
                            # `_resolve_mcp_invocation` below)

# Capture (get_window_state / screenshot) renders AND transfers an image —
# with SOM the default it draws numbered overlays on every step, which is far
# heavier than a click. The generic 15s call timeout was tripping on slower
# Windows hosts (observed ~22s capture hangs), blinding the agent for the rest
# of the task. Give captures more headroom; clicks/keys keep the fast default
# so they still fail fast and trigger reconnect.
_CAPTURE_TIMEOUT = 30.0

# list_windows enumerates EVERY top-level window (including minimized /
# background ones). On a busy Windows box that can exceed the default 15s
# call_tool ceiling — the source of the observed `list_windows failed:` /
# `capture failed:` TimeoutErrors. Give the enumeration a wider budget than a
# normal action (it's read-only and can't damage anything by running long).
_LIST_WINDOWS_TIMEOUT = 25.0

# Whole-screen / desktop capture. cua-driver is a window-oriented driver —
# its `get_window_state` / `screenshot` tools capture a single window (by
# pid + window_id), and there is no MCP tool that captures the entire virtual
# desktop or an arbitrary monitor as one image. But the OS shell surfaces
# themselves (the desktop backdrop and the taskbar/menu-bar) are real windows
# that show up in `list_windows`, so "show me my screen" / "click the taskbar"
# is reachable by targeting those windows. When `app` is one of these
# sentinels, capture() resolves to the desktop/shell window instead of an
# application window.
_SCREEN_CAPTURE_SENTINELS = {"screen", "desktop", "fullscreen", "full screen", "all"}

# Known shell/desktop window identifiers across platforms. Matched
# case-insensitively as a substring against both the window's app_name and
# its title (cua-driver surfaces the Win32 class name / app name here).
#   Windows: Progman / WorkerW back the desktop; Shell_TrayWnd is the taskbar.
#   macOS:   Finder owns the desktop; the menu bar / Dock are the shell.
_DESKTOP_WINDOW_NAMES = (
    "progman", "workerw", "program manager",  # Windows desktop
    "shell_traywnd", "taskbar",               # Windows taskbar
    "finder", "desktop", "dock",              # macOS desktop / shell
)


# Env var cua-driver reads to gate its anonymous usage telemetry (PostHog).
# Setting it to "0" disables telemetry; absence => the binary's own default
# (telemetry ON upstream).
_CUA_TELEMETRY_ENV_VAR = "CUA_DRIVER_RS_TELEMETRY_ENABLED"


def _cua_telemetry_disabled() -> bool:
    """True when Clio should disable cua-driver telemetry for this user.

    Reads ``computer_use.cua_telemetry`` from config.yaml. Default is False
    (telemetry off). Any failure to read config fails SAFE — toward the
    privacy-preserving default of telemetry disabled.
    """
    try:
        from clio_cli.config import load_config

        cfg = load_config() or {}
        cu = cfg.get("computer_use") or {}
        # opt-in flag: True => user wants telemetry => do NOT disable.
        return not bool(cu.get("cua_telemetry", False))
    except Exception:
        # Config unreadable — default to disabling telemetry (fail safe).
        return True


def _configured_max_image_dimension() -> Optional[int]:
    """Longest-side cap (px) for the screenshots cua-driver emits.

    Smaller images mean faster, cheaper vision round-trips. Since SOM is now
    the default capture mode, a screenshot is sent on most steps, so the cap
    matters: 1280px PNGs ran ~2.7MB and drove 15-27s vision turns. Default
    1024 roughly halves the bytes while keeping numbered overlays legible.
    Reads ``computer_use.max_image_dimension`` from config.yaml. Return None
    (or config 0) to leave cua-driver's own default (1568) untouched.
    """
    try:
        from clio_cli.config import load_config

        cfg = load_config() or {}
        cu = cfg.get("computer_use") or {}
        val = cu.get("max_image_dimension", 1024)
        if val in (None, 0, "0"):
            return None
        return int(val)
    except Exception:
        return 1024


def cua_driver_child_env(base_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Return the environment dict for spawning cua-driver.

    Starts from ``base_env`` (defaults to ``os.environ``) and, when telemetry
    is disabled (the default), injects ``CUA_DRIVER_RS_TELEMETRY_ENABLED=0``.
    When the user has opted in, the var is left untouched so cua-driver uses
    its own default. Used by every cua-driver spawn site (MCP backend, status,
    doctor, install) so the policy is applied consistently.
    """
    env = dict(base_env if base_env is not None else os.environ)
    if _cua_telemetry_disabled():
        env[_CUA_TELEMETRY_ENV_VAR] = "0"
    return env


def _resolve_mcp_invocation(
    driver_cmd: str,
    *,
    timeout: float = 6.0,
) -> Tuple[str, List[str]]:
    """Return ``(command, args)`` that spawn cua-driver's stdio MCP server.

    Surface 8 of the cua-driver integration: instead of hardcoding
    ``["mcp"]`` we ask the driver itself via ``cua-driver manifest``
    (trycua/cua#1961). The manifest carries a stable ``mcp_invocation``
    pointer with both ``command`` and ``args``, so a future cua-driver
    that renames or relocates the subcommand keeps working without a
    Clio patch.

    Falls back to ``(driver_cmd, ["mcp"])`` for older drivers that don't
    expose ``manifest``, or any indeterminate failure — the wrapper must
    not refuse to start just because the discovery hop failed.
    """
    try:
        proc = subprocess.run(
            [driver_cmd, "manifest"],
            capture_output=True, text=True, timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
    except Exception:
        return driver_cmd, list(_CUA_DRIVER_ARGS)
    out = (proc.stdout or "").strip()
    if proc.returncode != 0 or not out:
        return driver_cmd, list(_CUA_DRIVER_ARGS)
    try:
        manifest = json.loads(out)
    except (ValueError, TypeError):
        return driver_cmd, list(_CUA_DRIVER_ARGS)
    if not isinstance(manifest, dict):
        return driver_cmd, list(_CUA_DRIVER_ARGS)
    invocation = manifest.get("mcp_invocation")
    if not isinstance(invocation, dict):
        return driver_cmd, list(_CUA_DRIVER_ARGS)
    args = invocation.get("args")
    command = invocation.get("command")
    if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        return driver_cmd, list(_CUA_DRIVER_ARGS)
    if not isinstance(command, str) or not command:
        # The driver knows the subcommand but didn't surface its own path.
        # Keep our resolved driver_cmd; the args are still authoritative.
        return driver_cmd, args
    return command, args

# Regex to parse element lines from get_window_state AX tree markdown.
#
# Handles two output formats from different cua-driver versions:
#   Classic:  "  - [N] AXRole \"label\""
#   New:       "[N] AXRole (order) id=Label"
#
# Group 1: element index
# Group 2: AX role
# Group 3: quoted label (classic format)
# Group 4: id= label (new format)
_ELEMENT_LINE_RE = re.compile(
    r'^\s*(?:-\s+)?\[(\d+)\]\s+(\w+)(?:\s+"([^"]*)"|(?:\s+\(\d+\))?\s+id=([^\s\[\]]*))?' ,
    re.MULTILINE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_macos() -> bool:
    return sys.platform == "darwin"


def cua_driver_binary_available() -> bool:
    """True if `cua-driver` is on $PATH or CLIO_CUA_DRIVER_CMD resolves."""
    return bool(shutil.which(_CUA_DRIVER_CMD))


def cua_driver_update_check(*, timeout: float = 8.0) -> Optional[Dict[str, Any]]:
    """Run ``cua-driver check-update --json`` and return its parsed state.

    The payload mirrors the ``check_for_update`` MCP tool:
    ``{current_version, latest_version, update_available, ...}``.

    Returns ``None`` (callers should stay quiet) when the result is
    indeterminate: the binary is missing, the driver is too old to support
    the verb (it predates trycua/cua#1734), the GitHub check failed (an
    ``error`` field is set), or the output didn't parse. Best-effort; never
    raises.
    """
    try:
        proc = subprocess.run(
            [_CUA_DRIVER_CMD, "check-update", "--json"],
            capture_output=True, text=True, timeout=timeout,
            # Some older drivers don't have the verb and fall through to a
            # stdin-reading mode rather than erroring — DEVNULL gives them EOF
            # so they exit fast instead of blocking until the timeout.
            stdin=subprocess.DEVNULL,
            env=cua_driver_child_env(),
        )
    except Exception:
        return None
    out = (proc.stdout or "").strip()
    if not out:
        # Older drivers don't have the verb: usage goes to stderr, stdout empty.
        return None
    try:
        data = json.loads(out)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or data.get("error"):
        # A failed check (exit 1) carries its reason in `error` — indeterminate.
        return None
    return data


def cua_driver_update_nudge() -> Optional[str]:
    """One-line "an update is available" message, or ``None`` when up to date,
    indeterminate, or the driver is too old to report."""
    state = cua_driver_update_check()
    if not state or not state.get("update_available"):
        return None
    latest = state.get("latest_version") or "?"
    current = state.get("current_version") or "?"
    return (
        f"cua-driver {latest} is available (you have {current}); "
        f"update with `clio computer-use install --upgrade`."
    )


_update_checked = False


def _auto_upgrade_driver_enabled() -> bool:
    """Whether to auto-upgrade cua-driver on a detected version mismatch.

    ON by default: a stale driver is the usual cause of platform-specific
    input regressions, and production machines sat on old builds for days
    while the nudge went unread. Opt out with
    ``computer_use.auto_upgrade_driver: false`` in config.yaml. The upgrade
    runs off-thread between actions and replaces our own installed binary,
    so the blast radius is the driver itself.
    """
    try:
        from clio_cli.config import load_config

        cfg = load_config() or {}
        cu = cfg.get("computer_use") or {}
        return bool(cu.get("auto_upgrade_driver", True))
    except Exception:
        return False


def _maybe_nudge_update() -> None:
    """Emit an update nudge at most once per process, off-thread so the
    (cached, ~20h) GitHub poll never blocks the first computer_use action.

    A stale driver is the usual cause of platform-specific click/drag
    regressions (the 0.6.5→0.6.8 drift behind the misclick reports), so the
    nudge is a WARNING, not info — and when the user has opted in, the
    upgrade runs automatically."""
    global _update_checked
    if _update_checked:
        return
    _update_checked = True

    def _run() -> None:
        try:
            state = cua_driver_update_check()
        except Exception:
            return
        if not state or not state.get("update_available"):
            return
        latest = state.get("latest_version") or "?"
        current = state.get("current_version") or "?"
        if _auto_upgrade_driver_enabled():
            logger.warning(
                "computer_use: upgrading cua-driver %s → %s "
                "(computer_use.auto_upgrade_driver is on)…", current, latest,
            )
            try:
                subprocess.run(
                    [sys.executable, "-m", "clio_cli.main",
                     "computer-use", "install", "--upgrade"],
                    capture_output=True, text=True, timeout=300,
                    stdin=subprocess.DEVNULL, env=cua_driver_child_env(),
                )
            except Exception as e:
                logger.warning("computer_use: auto-upgrade failed: %s", e)
            return
        logger.warning(
            "computer_use: cua-driver %s is available (you have %s); update "
            "with `clio computer-use install --upgrade` (stale drivers cause "
            "click/drag misfires). Set computer_use.auto_upgrade_driver: true "
            "to upgrade automatically.", latest, current,
        )

    threading.Thread(
        target=_run, name="cua-driver-update-check", daemon=True
    ).start()


def cua_driver_install_hint() -> str:
    if sys.platform == "win32":
        installer = (
            '  irm https://raw.githubusercontent.com/trycua/cua/main/'
            'libs/cua-driver/scripts/install.ps1 | iex'
        )
    else:
        installer = (
            '  /bin/bash -c "$(curl -fsSL '
            'https://raw.githubusercontent.com/trycua/cua/main/'
            'libs/cua-driver/scripts/install.sh)"'
        )
    return (
        "cua-driver is not installed. Install with one of:\n"
        "  clio computer-use install\n"
        "Or run the upstream installer directly:\n"
        f"{installer}\n"
        "Or run `clio tools` and enable the Computer Use toolset to install it automatically."
    )


def _parse_elements_from_tree(markdown: str) -> List[UIElement]:
    """Parse UIElement list from get_window_state AX tree markdown.

    Last-resort fallback for cua-driver builds that don't carry the
    canonical ``structuredContent.elements`` array (see
    ``_parse_elements_from_structured`` — Surface 2 of #47072 prefers
    that path).

    Handles both the classic ``"label"``-quoted format and the newer
    ``id=Label`` format introduced in cua-driver v0.1.6. Bounds always
    come back ``(0, 0, 0, 0)`` because the markdown surface doesn't
    carry them — yet another reason to prefer the structured path.
    """
    elements = []
    for m in _ELEMENT_LINE_RE.finditer(markdown):
        # group(3) = quoted label (classic); group(4) = id= label (new)
        label = m.group(3) or m.group(4) or ""
        elements.append(UIElement(
            index=int(m.group(1)),
            role=m.group(2),
            label=label,
            bounds=(0, 0, 0, 0),
        ))
    return elements


def _parse_elements_from_structured(raw_elements: List[Dict[str, Any]]) -> List[UIElement]:
    """Surface 2 of the cua-driver integration: read the canonical
    ``structuredContent.elements`` array cua-driver-rs emits on every
    ``get_window_state`` response (trycua/cua#1961).

    Each entry has at minimum ``element_index``, ``role``, ``label``;
    ``frame`` (``{x, y, w, h}``) is included whenever the AT-SPI /
    AXFrame call returned usable bounds. Older code parsed the same
    information out of the markdown tree via a regex (lossy: bounds
    were always ``(0, 0, 0, 0)``) — this path preserves the real
    frame so downstream consumers (e.g. ``UIElement.center()``) work
    against pixel coordinates instead of just the index lookup.

    Unknown / malformed entries are skipped rather than failing the
    whole walk — the wrapper degrades to "fewer elements" rather than
    "no elements" on a bad row.
    """
    elements: List[UIElement] = []
    for raw in raw_elements:
        if not isinstance(raw, dict):
            continue
        idx = raw.get("element_index")
        if not isinstance(idx, int):
            continue
        role = raw.get("role") if isinstance(raw.get("role"), str) else ""
        label = raw.get("label") if isinstance(raw.get("label"), str) else ""
        frame = raw.get("frame") if isinstance(raw.get("frame"), dict) else None
        bounds: Tuple[int, int, int, int] = (0, 0, 0, 0)
        if frame:
            try:
                bounds = (
                    int(frame.get("x", 0)),
                    int(frame.get("y", 0)),
                    int(frame.get("w", 0)),
                    int(frame.get("h", 0)),
                )
            except (TypeError, ValueError):
                bounds = (0, 0, 0, 0)
        # Surface 6: opaque element_token. cua-driver-rs format is
        # `s{snapshot_hex}:{index}`. We treat it as a black-box string —
        # the driver owns the parse + LRU semantics.
        raw_token = raw.get("element_token")
        token = raw_token if isinstance(raw_token, str) and raw_token else None
        elements.append(UIElement(
            index=idx,
            role=role,
            label=label,
            bounds=bounds,
            element_token=token,
        ))
    return elements


def _parse_page_scroll_metrics(data: Any) -> Optional[Dict[str, Any]]:
    """Extract the JSON metrics object page_scroll's JS returns.

    The driver relays execute_javascript results as a string (sometimes
    wrapped in prose or quoted, depending on the browser bridge), or as an
    already-decoded dict. Find the first JSON object in the payload; None
    when there isn't one.
    """
    if isinstance(data, dict):
        return data
    if not isinstance(data, str) or not data.strip():
        return None
    text = data.strip()
    # Direct parse first; then a doubly-encoded string; then the first
    # {...} block embedded in prose.
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, str):
            inner = json.loads(parsed)
            if isinstance(inner, dict):
                return inner
    except (ValueError, TypeError):
        pass
    m = re.search(r"\{[^{}]*\}", text)
    if m:
        try:
            parsed = json.loads(m.group(0))
            if isinstance(parsed, dict):
                return parsed
        except ValueError:
            pass
    return None


def _image_dimensions_from_bytes(raw: bytes) -> Tuple[int, int]:
    """Best-effort PNG/JPEG dimension sniffing without extra dependencies."""
    if raw.startswith(b"\x89PNG\r\n\x1a\n") and len(raw) >= 24:
        width = int.from_bytes(raw[16:20], "big")
        height = int.from_bytes(raw[20:24], "big")
        if width > 0 and height > 0:
            return width, height

    if raw.startswith(b"\xff\xd8"):
        i = 2
        n = len(raw)
        while i + 9 < n:
            if raw[i] != 0xFF:
                i += 1
                continue
            marker = raw[i + 1]
            i += 2
            if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
                continue
            if i + 2 > n:
                break
            segment_len = int.from_bytes(raw[i:i + 2], "big")
            if segment_len < 2 or i + segment_len > n:
                break
            if marker in {
                0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
            }:
                if segment_len >= 7:
                    height = int.from_bytes(raw[i + 3:i + 5], "big")
                    width = int.from_bytes(raw[i + 5:i + 7], "big")
                    if width > 0 and height > 0:
                        return width, height
                break
            i += segment_len

    return 0, 0


def _split_tree_text(full_text: str) -> Tuple[str, str]:
    """Split get_window_state text into (summary_line, tree_markdown)."""
    lines = full_text.split("\n", 1)
    summary = lines[0]
    tree = lines[1] if len(lines) > 1 else ""
    return summary, tree


def _parse_key_combo(keys: str) -> Tuple[Optional[str], List[str]]:
    """Parse a key string like 'cmd+s' into (key, modifiers).

    Returns (key, modifiers) where key is the non-modifier key and modifiers
    is a list of modifier names (cmd, shift, option, ctrl).
    """
    # win/super/meta are modifiers too — without them "win+down" parses to a
    # bare "down" press and OS shortcuts (minimize, show desktop) never fire.
    MODIFIER_NAMES = {"cmd", "command", "shift", "option", "alt", "ctrl",
                      "control", "fn", "win", "super", "meta"}
    KEY_ALIASES = {"command": "cmd", "alt": "option", "control": "ctrl"}

    parts = [p.strip().lower() for p in re.split(r'[+\-]', keys) if p.strip()]
    modifiers = []
    key = None
    for part in parts:
        normalized = KEY_ALIASES.get(part, part)
        if normalized in MODIFIER_NAMES:
            modifiers.append(normalized)
        else:
            key = part  # last non-modifier wins
    return key, modifiers


# ---------------------------------------------------------------------------
# Asyncio bridge — one long-lived loop on a background thread
# ---------------------------------------------------------------------------

class _AsyncBridge:
    """Runs one asyncio loop on a daemon thread; marshals coroutines from the caller."""

    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._ready.clear()

        def _run() -> None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._ready.set()
            try:
                self._loop.run_forever()
            finally:
                try:
                    self._loop.close()
                except Exception:
                    pass

        self._thread = threading.Thread(target=_run, daemon=True, name="cua-driver-loop")
        self._thread.start()
        if not self._ready.wait(timeout=5.0):
            raise RuntimeError("cua-driver asyncio bridge failed to start")

    def run(self, coro, timeout: Optional[float] = 30.0) -> Any:
        from agent.async_utils import safe_schedule_threadsafe
        if not self._loop or not self._thread or not self._thread.is_alive():
            if asyncio.iscoroutine(coro):
                coro.close()
            raise RuntimeError("cua-driver bridge not started")
        fut = safe_schedule_threadsafe(coro, self._loop)
        if fut is None:
            raise RuntimeError("cua-driver bridge not started")
        return fut.result(timeout=timeout)

    def stop(self) -> None:
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=2.0)
        self._thread = None
        self._loop = None


# ---------------------------------------------------------------------------
# MCP session (lazy, shared across tool calls)
# ---------------------------------------------------------------------------

class _CuaDriverSession:
    """Holds the mcp ClientSession. Spawned lazily; re-entered on drop.

    Lifecycle ownership: a single long-running coroutine
    (`_lifecycle_coro`) opens both the stdio_client and ClientSession
    contexts, populates capabilities, sets `_ready_event`, and then waits
    on `_shutdown_event`. When shutdown is signalled the same coroutine
    closes the contexts — keeping anyio's cancel-scope task-identity
    invariant intact (the bridge schedules each `bridge.run(coro)` as a
    NEW task, so opening contexts in one and closing them in another
    raises "Attempted to exit cancel scope in a different task").
    Tool calls run in their own short-lived tasks; they only touch the
    session object, never the surrounding contexts.
    """

    def __init__(self, bridge: _AsyncBridge) -> None:
        self._bridge = bridge
        self._session = None
        self._lock = threading.Lock()
        self._started = False
        # Surface 4 of the cua-driver integration: per-tool
        # capability-token sets, populated from `tools/list` at session
        # init. Keys are tool names (e.g. "click", "get_window_state");
        # values are sets of capability strings (e.g.
        # "accessibility.element_tokens", "input.keyboard.type.terminal_safe").
        # Empty until the session starts; consumers should call
        # `supports_capability` rather than reading directly.
        self._capabilities: Dict[str, set] = {}
        self._capability_version: str = ""
        # Lifecycle plumbing — see class docstring above.
        self._ready_event = threading.Event()
        self._shutdown_event: Optional[asyncio.Event] = None  # created on bridge loop
        self._lifecycle_future = None  # concurrent.futures.Future
        self._setup_error: Optional[BaseException] = None
        # Invoked once after a successful reconnect (NOT on the first start)
        # so the owner can re-establish session-scoped state — cua-driver's
        # start_session identity + config overrides are lost when the daemon
        # dies, and a bare transport reconnect would silently degrade them.
        # Set by CuaDriverBackend. Runs while _reconnecting is True so the
        # re-init calls can't recurse into another reconnect.
        self.on_reconnect: Optional[Callable[[], None]] = None
        self._reconnecting = False

    def _require_started(self) -> None:
        if not self._started:
            raise RuntimeError("cua-driver session not started")

    async def _lifecycle_coro(self) -> None:
        """Long-lived owner of the stdio MCP contexts. Opens, signals
        ready, blocks on shutdown, then cleans up. enter + exit happen
        in the SAME asyncio task, so anyio's cancel-scope invariant
        holds — fixing the "Attempted to exit cancel scope in a
        different task than it was entered in" warning emitted by the
        previous _aenter/_aexit split.
        """
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from tools.environments.local import _sanitize_subprocess_env

        # Build the shutdown event on the loop's thread so the asyncio
        # primitive belongs to the correct loop.
        self._shutdown_event = asyncio.Event()

        try:
            if not cua_driver_binary_available():
                raise RuntimeError(cua_driver_install_hint())

            # Surface 8: ask cua-driver itself which subcommand spawns
            # the MCP server, instead of hardcoding ["mcp"]. Falls back
            # transparently for older drivers / any discovery failure.
            command, args = _resolve_mcp_invocation(_CUA_DRIVER_CMD)
            params = StdioServerParameters(
                command=command,
                args=args,
                # Apply the telemetry policy first (default: disabled), then
                # sanitize Clio-managed secrets out of the child env.
                env=_sanitize_subprocess_env(cua_driver_child_env()),
            )

            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    # Populate capabilities + capability_version BEFORE
                    # exposing the session to callers, so the first
                    # tool call already sees them.
                    await self._populate_capabilities(session)
                    self._session = session
                    self._ready_event.set()
                    # Hold the contexts open until stop() / restart asks
                    # us to wind down. Tool calls run as their own tasks
                    # on the same loop and touch self._session directly.
                    await self._shutdown_event.wait()
        except BaseException as e:
            # Capture both ordinary errors and anyio CancelledError.
            # The caller (start()) inspects this to surface setup
            # failures to the synchronous world.
            self._setup_error = e
            self._ready_event.set()
            raise
        finally:
            # Clearing _session before the contexts unwind would let a
            # racing call_tool see None during teardown — but the
            # outer context-manager exits AFTER this block, so set to
            # None here is fine: stop() has already flipped _started.
            self._session = None

    async def _populate_capabilities(self, session: Any) -> None:
        """Surface 4: cache per-tool capability sets + capability_version
        from tools/list. Soft prerequisite — discovery failure leaves
        the map empty and supports_capability degrades to False."""
        try:
            tools_list = await session.list_tools()
            for tool in getattr(tools_list, "tools", []) or []:
                tool_name = getattr(tool, "name", None)
                if not isinstance(tool_name, str):
                    continue
                caps = getattr(tool, "capabilities", None)
                if caps is None:
                    # Some MCP SDKs forward custom fields via
                    # `model_extra` (Pydantic v2) instead of attributes.
                    extra = getattr(tool, "model_extra", None) or {}
                    caps = extra.get("capabilities")
                if isinstance(caps, list):
                    self._capabilities[tool_name] = {
                        c for c in caps if isinstance(c, str)
                    }
                else:
                    self._capabilities[tool_name] = set()
            # capability_version is a top-level sibling of `tools` on the
            # tools/list response. cua-driver-core/src/tool.rs:354 emits
            # it; cua-driver-core/src/protocol.rs:150 leaves it OUT of
            # initialize — so we discover here, not there.
            cv = getattr(tools_list, "capability_version", None)
            if cv is None:
                extra = getattr(tools_list, "model_extra", None) or {}
                cv = extra.get("capability_version")
            if isinstance(cv, str):
                self._capability_version = cv
        except Exception as e:
            logger.debug("cua-driver tools/list capability discovery failed: %s", e)

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._bridge.start()
            self._start_lifecycle_locked()
            self._started = True

    def _start_lifecycle_locked(self) -> None:
        """Spawn the lifecycle owner and wait for it to reach ready.
        Caller must hold self._lock."""
        # Reset per-session state.
        self._ready_event = threading.Event()
        self._setup_error = None
        self._shutdown_event = None
        # Fire-and-forget schedule on the bridge loop. The future tracks
        # completion of the WHOLE lifecycle (open → wait → close), not
        # just the open step — start() waits on _ready_event separately.
        loop = self._bridge._loop
        if loop is None:
            raise RuntimeError("cua-driver bridge not started")
        self._lifecycle_future = asyncio.run_coroutine_threadsafe(
            self._lifecycle_coro(), loop
        )
        if not self._ready_event.wait(timeout=15.0):
            # Best-effort: signal shutdown if the future is still alive.
            self._signal_shutdown_locked()
            raise RuntimeError("cua-driver session never reached ready (timeout 15s)")
        # If setup failed, the lifecycle coroutine set _setup_error
        # before setting _ready_event. Re-raise it on the caller's thread.
        if self._setup_error is not None:
            raise RuntimeError(
                f"cua-driver session setup failed: {self._setup_error}"
            ) from self._setup_error

    def stop(self) -> None:
        with self._lock:
            if not self._started:
                return
            self._started = False
            self._stop_lifecycle_locked()

    def _stop_lifecycle_locked(self) -> None:
        """Signal shutdown + wait for the lifecycle coroutine to unwind.
        Caller must hold self._lock."""
        self._signal_shutdown_locked()
        fut = self._lifecycle_future
        if fut is None:
            return
        try:
            # 5s budget for context unwind (stdio_client teardown).
            fut.result(timeout=5.0)
        except concurrent.futures.TimeoutError:
            logger.warning("cua-driver session shutdown timed out (5s)")
        except Exception as e:
            # Real shutdown errors (not the previous cancel-scope race
            # which is now structurally impossible) still get surfaced.
            logger.warning("cua-driver shutdown error: %s", e)
        finally:
            self._lifecycle_future = None

    def _signal_shutdown_locked(self) -> None:
        """Set the asyncio shutdown event from the caller's thread."""
        loop = self._bridge._loop
        event = self._shutdown_event
        if loop is not None and event is not None and loop.is_running():
            try:
                loop.call_soon_threadsafe(event.set)
            except RuntimeError:
                # Loop closed — nothing to signal.
                pass

    async def _call_tool_async(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        result = await self._session.call_tool(name, args)
        return _extract_tool_result(result)

    # ── Capability detection (Surface 4 of #47072) ────────────────────
    def supports_capability(self, capability: str, tool: Optional[str] = None) -> bool:
        """Return True when the connected cua-driver advertises the given
        capability token (trycua/cua#1961 capability vocabulary).

        When ``tool`` is given, scope the check to that specific tool's
        advertised capability set. When omitted, return True if ANY tool
        advertises the capability — useful for "is this feature available
        anywhere on the driver" probes.

        Always returns False before the session is started (so consumers
        on a dead/uninitialised wrapper degrade rather than crash).
        """
        if tool is not None:
            return capability in self._capabilities.get(tool, set())
        return any(capability in caps for caps in self._capabilities.values())

    def _has_tool(self, name: str) -> bool:
        """Return True when ``tools/list`` advertised a tool by this name.

        Used to route capture(): cua-driver dropped the standalone
        ``screenshot`` tool and folded full-window PNG capture into
        ``get_window_state`` (whose own description notes it "Also captures
        a PNG screenshot of the specified window"). Older drivers that still
        expose ``screenshot`` keep using it; newer ones fall through to
        ``get_window_state``.

        Returns False when discovery hasn't populated the map yet — callers
        treat that as "unknown" and probe defensively rather than trusting it.
        """
        return name in self._capabilities

    @property
    def capabilities_discovered(self) -> bool:
        """True once ``tools/list`` populated the per-tool map. When False,
        ``_has_tool`` answers are not trustworthy (discovery failed or the
        session hasn't started) and capture() should probe defensively."""
        return bool(self._capabilities)

    @property
    def capability_version(self) -> str:
        """Driver-advertised capability vocabulary version (empty string
        when the driver predates the field — older builds had no version)."""
        return self._capability_version

    @staticmethod
    def _is_closed_session_error(exc: Exception) -> bool:
        """Return True for MCP/stdio failures that are recoverable by reconnecting.

        Covers two distinct death signatures observed when cua-driver exits:
          * stdio transport teardown — anyio ``ClosedResourceError`` /
            ``BrokenResourceError`` / ``EndOfStream`` or a plain
            ``BrokenPipeError`` / ``EOFError`` (e.g. writing to a dead stdin).
          * a clean in-flight failure — when the read stream closes mid-request
            the MCP SDK answers every pending request with a ``JSONRPCError``
            carrying code ``CONNECTION_CLOSED`` (-32000), surfaced as an
            ``McpError`` (mcp/shared/session.py). The class name is generic, so
            we match on the error code / message rather than the type name.
        """
        name = exc.__class__.__name__
        module = getattr(exc.__class__, "__module__", "")
        if (
            name in {"ClosedResourceError", "BrokenResourceError", "EndOfStream"}
            or (module.startswith("anyio") and "Resource" in name)
            or isinstance(exc, (BrokenPipeError, EOFError))
        ):
            return True
        # McpError("Connection closed") — the dead-driver signal for a request
        # that was in flight when the transport dropped. Inspect defensively so
        # an SDK shape change (missing `.error`, renamed constant) degrades to
        # "not recoverable" rather than crashing the detector.
        err = getattr(exc, "error", None)
        if err is not None:
            try:
                from mcp.types import CONNECTION_CLOSED as _CC
            except Exception:
                _CC = -32000
            if getattr(err, "code", None) == _CC:
                return True
            msg = getattr(err, "message", None)
            if isinstance(msg, str) and "connection closed" in msg.lower():
                return True
        return False

    async def _ping_async(self) -> Any:
        return await self._session.send_ping()

    def ping_alive(self, timeout: float = 2.0) -> bool:
        """Best-effort liveness probe. Returns True only if the driver answers
        a ``ping`` within ``timeout``; any failure/timeout/dead-session returns
        False. Used to tell a genuinely-slow op apart from a dead daemon when a
        ``call_tool`` times out — a dead daemon never answers, so the ping also
        times out and we conclude the session must be rebuilt."""
        if not self._started or self._session is None:
            return False
        try:
            self._bridge.run(self._ping_async(), timeout=timeout)
            return True
        except Exception:
            return False

    def _restart_session_locked(self) -> None:
        """Recreate the MCP session after the daemon/stdin transport was closed.
        Caller must hold self._lock (the reconnect-once retry path holds it)."""
        if self._reconnecting:
            # Re-entrancy guard: the on_reconnect callback re-issues
            # start_session/set_config through call_tool; those must never
            # trigger another reconnect from inside this one.
            return
        if self._started:
            try:
                self._stop_lifecycle_locked()
            except Exception as e:
                logger.debug("cua-driver session cleanup before reconnect failed: %s", e)
        self._started = False
        # Clear stale capability state; the next start populates from scratch.
        self._capabilities = {}
        self._capability_version = ""
        self._start_lifecycle_locked()
        self._started = True
        # Re-establish session-scoped state on the fresh transport. Runs with
        # the guard set so nested call_tool failures don't recurse; best-effort
        # so a re-init hiccup never defeats the reconnect itself.
        if self.on_reconnect is not None:
            self._reconnecting = True
            try:
                self.on_reconnect()
            except Exception as e:
                logger.debug("cua-driver post-reconnect re-init failed: %s", e)
            finally:
                self._reconnecting = False

    def call_tool(self, name: str, args: Dict[str, Any], timeout: float = 15.0) -> Dict[str, Any]:
        # 15s ceiling (was 30): a slow/blocked cua-driver op — e.g.
        # get_window_state on a busy app, or an interaction on a window whose
        # UI thread is momentarily stalled — should fail fast with a clear
        # error instead of hanging the agent.
        self._require_started()
        try:
            return self._bridge.run(self._call_tool_async(name, args), timeout=timeout)
        except Exception as e:
            # While re-initialising a fresh transport (start_session/set_config
            # re-issued by the on_reconnect callback), don't attempt to recover
            # again — surface the error and let the outer call_tool own retries.
            if self._reconnecting:
                raise
            recover = self._is_closed_session_error(e)
            if not recover and isinstance(e, (TimeoutError, concurrent.futures.TimeoutError)):
                # A timeout is ambiguous: the daemon may be dead (the
                # between-tasks case — the request hangs forever and only our
                # bridge timeout fires) or the op may be genuinely slow. Probe
                # liveness with a short ping: no answer ⇒ dead ⇒ rebuild; an
                # answer ⇒ slow op ⇒ propagate (preserve fail-fast, no 2× cost).
                if not self.ping_alive():
                    logger.warning(
                        "cua-driver unresponsive during %s (ping failed); reconnecting once",
                        name,
                    )
                    recover = True
            if not recover:
                raise
            # Daemon restart closes the cached stdio channel. Reconnect once and
            # retry exactly one more time — never loop, to avoid hammering a
            # genuinely dead daemon.
            logger.warning("cua-driver MCP session closed during %s; reconnecting once", name)
            with self._lock:
                self._restart_session_locked()
            return self._bridge.run(self._call_tool_async(name, args), timeout=timeout)


def _extract_tool_result(mcp_result: Any) -> Dict[str, Any]:
    """Convert an mcp CallToolResult into a plain dict.

    cua-driver returns a mix of text parts, image parts, and structuredContent.
    We flatten into:
      {
        "data": <text or parsed json>,
        "images": [b64, ...],
        "image_mime_types": [mime, ...],   # parallel to `images`, "" when absent
        "structuredContent": <dict|None>,
        "isError": bool,
      }
    structuredContent is populated from the MCP result's structuredContent field
    (MCP spec §2024-11-05+) and takes precedence for structured data like
    list_windows window arrays.

    `image_mime_types` is the explicit `mimeType` cua-driver emits on every
    image part as of trycua/cua#1961 (Surface 7 of
    the cua-driver integration). Each entry corresponds index-for-index
    with `images`; an empty string entry signals the part carried no
    mimeType (older cua-driver build), and the caller should fall back to
    base64-prefix sniffing.
    """
    data: Any = None
    images: List[str] = []
    image_mime_types: List[str] = []
    is_error = bool(getattr(mcp_result, "isError", False))
    structured: Optional[Dict] = getattr(mcp_result, "structuredContent", None) or None
    text_chunks: List[str] = []
    for part in getattr(mcp_result, "content", []) or []:
        ptype = getattr(part, "type", None)
        if ptype == "text":
            text_chunks.append(getattr(part, "text", "") or "")
        elif ptype == "image":
            b64 = getattr(part, "data", None)
            if b64:
                images.append(b64)
                mime = getattr(part, "mimeType", None) or ""
                image_mime_types.append(mime)
    if text_chunks:
        joined = "\n".join(t for t in text_chunks if t)
        try:
            data = json.loads(joined) if joined.strip().startswith(("{", "[")) else joined
        except json.JSONDecodeError:
            data = joined
    return {
        "data": data,
        "images": images,
        "image_mime_types": image_mime_types,
        "structuredContent": structured,
        "isError": is_error,
    }


def _image_from_tool_result(out: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """Pull a (png_b64, mime_type) pair out of a flattened tool result.

    cua-driver delivers window screenshots in two shapes depending on tool +
    transport:

      * As an MCP ``image`` content part — surfaced by ``_extract_tool_result``
        in ``out["images"]`` with a parallel ``image_mime_types`` entry. This
        is what ``get_window_state`` emits over the stdio MCP transport.
      * As a base64 field inside ``structuredContent`` —
        ``screenshot_png_b64`` (+ ``screenshot_mime_type``). This is what
        ``get_window_state`` returns when its structured payload carries the
        image instead of a content part (newer driver builds; also the shape
        seen via the ``cua-driver call`` CLI surface).

    Checking both makes capture() robust to either delivery shape, so the
    image never silently drops just because the driver moved it between the
    content list and structuredContent. Returns ``(None, None)`` when neither
    location carries an image.
    """
    images = out.get("images") or []
    if images and images[0]:
        mimes = out.get("image_mime_types") or []
        mime = mimes[0] if mimes and mimes[0] else None
        return images[0], mime

    structured = out.get("structuredContent") or {}
    b64 = structured.get("screenshot_png_b64") or structured.get("png_b64")
    if b64:
        mime = (
            structured.get("screenshot_mime_type")
            or structured.get("mime_type")
            or None
        )
        return b64, mime

    return None, None


# ---------------------------------------------------------------------------
# The backend itself
# ---------------------------------------------------------------------------

class CuaDriverBackend(ComputerUseBackend):
    """Default computer-use backend. Cross-platform via cua-driver MCP."""

    def __init__(self) -> None:
        self._bridge = _AsyncBridge()
        self._session = _CuaDriverSession(self._bridge)
        # Sticky context — updated by capture(), used by action tools.
        self._active_pid: Optional[int] = None
        self._active_window_id: Optional[int] = None
        self._last_app: Optional[str] = None  # last app name targeted via capture/focus_app
        # Coordinate mapping context (updated by capture()): the active
        # window's screen-global rect (x, y, w, h) from list_windows, and the
        # dimensions of the screenshot the model actually saw. cua-driver
        # screenshots are a window crop (downscaled to max_image_dimension)
        # whose origin is the window's top-left, but its click/drag/scroll
        # coordinates are SCREEN-GLOBAL points. So a raw pixel the model picks
        # off the screenshot must be mapped: screen = win_origin + px * win/img.
        # Without this, coordinate clicks land offset by the window origin and
        # mis-scaled under HiDPI (the "off-screen / misclick" bug). Element
        # index actions are unaffected — cua-driver resolves them server-side.
        self._active_window_rect: Optional[Tuple[int, int, int, int]] = None
        self._active_image_size: Optional[Tuple[int, int]] = None
        # Surface 6 of the cua-driver integration: per-snapshot
        # `element_index -> element_token` map populated on capture().
        # Action tools (click/scroll/set_value/...) attach the matching
        # token alongside `element_index` so cua-driver detects "stale"
        # explicitly instead of silently re-resolving to a different
        # element. Cleared whenever a fresh capture overwrites the
        # snapshot context.
        self._snapshot_tokens: Dict[int, str] = {}
        # Per-instance cua-driver session id. cua-driver's MCP server
        # instructions ask every consumer to declare a stable session
        # at the start of a run (start_session) and tear it down at
        # the end (end_session). Doing so:
        #   - Gets a distinct agent-cursor color per Clio run, with
        #     overlay rendering visualising where actions land
        #     (without moving the real OS cursor).
        #   - Isolates per-session config + recording ownership so
        #     concurrent Clio runs / subagents don't step on each
        #     other.
        # We mint a UUID4-based id once per CuaDriverBackend instance —
        # one Clio run = one backend = one session — and pass it as
        # `session` on every cua-driver tool call. Sessions are an
        # additive feature on the cua-driver side: when our id is
        # unknown to the driver (older builds), the tool calls
        # degrade to the anonymous / unsynced path documented in the
        # MCP server instructions.
        self._session_id: str = f"clio-{uuid.uuid4().hex[:12]}"
        # Re-establish session identity + config whenever the session layer
        # rebuilds a dead transport, so a recovered driver keeps this run's
        # cursor identity and screenshot-cap config instead of silently
        # degrading to the anonymous/default path.
        self._session.on_reconnect = self._post_connect_init

    # ── Lifecycle ──────────────────────────────────────────────────
    def _post_connect_init(self) -> None:
        """Declare session identity + apply config on a freshly-connected
        transport. Shared by start() (first connect) and the session's
        on_reconnect hook (after a dead-daemon rebuild). Each step is
        best-effort — cua-driver accepts anonymous/default calls, so a
        failure here degrades rather than aborts."""
        # Declare the run's session identity to cua-driver. From the
        # cua-driver server instructions: "start_session(session) once
        # at the start of a run → declares THIS run's identity (a
        # stable id you choose). Pass that same `session` on every
        # action below. It owns your agent cursor (a distinct color
        # per id) and follows the run across apps/windows."
        try:
            self._session.call_tool("start_session", {"session": self._session_id})
        except Exception as e:
            logger.debug("cua-driver start_session failed (continuing anonymous): %s", e)

        # Cap the screenshot resolution cua-driver emits at the source, so the
        # (now rare, AX-first) screenshot captures send a smaller image to the
        # model — faster vision round-trips. Configurable via
        # computer_use.max_image_dimension; 0/None leaves cua-driver's default.
        try:
            dim = _configured_max_image_dimension()
            if dim:
                self.set_config(max_image_dimension=int(dim))
        except Exception as e:
            logger.debug("cua-driver set max_image_dimension failed: %s", e)

    def start(self) -> None:
        _maybe_nudge_update()
        # The MCP client SDK (`mcp`) is an optional dependency (the
        # `computer-use` / `mcp` extras), not part of Clio' minimal core.
        # Lazy-install it on first use — the same pattern every other optional
        # backend uses — so users never hit an opaque `No module named 'mcp'`
        # at invoke time. Auto-install is gated by `security.allow_lazy_installs`
        # (default on); when it's disabled or fails, ensure() raises
        # FeatureUnavailable carrying an actionable `uv pip install mcp==…`
        # hint, which surfaces via the backend-unavailable path in tool.py.
        from tools.lazy_deps import ensure as _lazy_ensure
        _lazy_ensure("tool.computer_use", prompt=False)
        # A just-installed package may not be importable until the import
        # machinery's caches are refreshed within this process.
        import importlib
        importlib.invalidate_caches()
        self._session.start()
        self._post_connect_init()

    def stop(self) -> None:
        # Tear the cua-driver session down before disconnecting so the
        # driver can clean up per-session state (cursor overlay, recording
        # ownership, config overrides). Best-effort — even if it fails,
        # the connection drop below releases the daemon-side state via
        # the session_end hook cua-driver registers internally.
        if self._session._started:
            try:
                self._session.call_tool("end_session", {"session": self._session_id})
            except Exception as e:
                logger.debug("cua-driver end_session failed (continuing teardown): %s", e)
        try:
            self._session.stop()
        finally:
            self._bridge.stop()

    def is_available(self) -> bool:
        # cua-driver runs on macOS, Windows, and Linux. The Linux path is
        # the most recent addition (X11 + Wayland both supported upstream
        # as of mid-2026). Override the platform check at your own risk:
        # other Unix-likes haven't been exercised end-to-end.
        if sys.platform not in ("darwin", "win32", "linux"):
            return False
        return cua_driver_binary_available()

    # ── Capture ────────────────────────────────────────────────────
    def capture(self, mode: str = "som", app: Optional[str] = None) -> CaptureResult:
        """Capture the frontmost on-screen window (optionally filtered by app name).

        Maps clio `capture(mode, app)` → cua-driver `list_windows` +
        `get_window_state` (ax/som) or `screenshot` (vision).
        """
        # Step 1: enumerate on-screen windows to find target pid/window_id.
        # Surface 3 of the cua-driver integration: read the canonical
        # `structuredContent.windows` array directly. Pre-fix the wrapper
        # also kept a text-line regex (`_WINDOW_LINE_RE`) as a fallback for
        # cua-driver builds that predated structuredContent; the supersede
        # PR's effective minimum (trycua/cua#1961 + #1908) is well past
        # that, so the fallback is gone — the wrapper now treats the
        # structured shape as the only contract.
        # on_screen_only=False so minimized / background windows are
        # enumerable and targetable (e.g. capture(app="Telegram") after it's
        # been minimized). Target selection below still prefers on-screen
        # windows, so the default frontmost-capture behaviour is unchanged.
        raw_windows = self._list_windows_raw(on_screen_only=False)
        windows = []
        for w in raw_windows:
            # cua-driver on Linux/X11 surfaces compositor-side windows (the
            # mutter guard, GNOME Shell, the agent-cursor overlay) with a null
            # pid/window_id and a null app_name. They aren't actionable via the
            # pid+window_id API, so skip them rather than crashing on int(None)
            # / None.lower() further down.
            if w.get("pid") is None or w.get("window_id") is None:
                continue
            windows.append({
                "app_name": w.get("app_name") or "",
                "pid": int(w["pid"]),
                "window_id": int(w["window_id"]),
                "off_screen": not w.get("is_on_screen", True),
                "title": w.get("title") or "",
                "z_index": w.get("z_index") or 0,
                # Screen-global window rect — used to map model image pixels to
                # cua-driver's screen-global click coordinates.
                "x": w.get("x"),
                "y": w.get("y"),
                "width": w.get("width"),
                "height": w.get("height"),
            })
        # Sort by z_index descending (lowest z_index = frontmost on macOS).
        windows.sort(key=lambda w: w["z_index"])

        if not windows:
            return CaptureResult(mode=mode, width=0, height=0, png_b64=None,
                                 elements=[], app="", window_title="", png_bytes_len=0)

        # Filter by app name (case-insensitive substring) if requested.
        # When the filter matches nothing, surface that explicitly instead of
        # silently capturing the frontmost window — on macOS the `app_name`
        # returned by list_windows is the localized name (e.g. "計算機"), so
        # `app="Calculator"` legitimately matches no windows on a non-English
        # system and the caller needs to retry with the localized name.
        if app and app.strip().lower() in _SCREEN_CAPTURE_SENTINELS:
            # Whole-screen / desktop request. cua-driver has no virtual-desktop
            # capture tool, so resolve to the OS shell/desktop window (the
            # desktop backdrop or the taskbar/menu-bar), which list_windows
            # does surface. This makes "show me my screen" and "click the
            # taskbar" work; a single image still can't span multiple monitors
            # — that's a driver limitation, not a wrapper one.
            def _is_desktop_window(w: Dict[str, Any]) -> bool:
                haystack = f"{w.get('app_name', '')} {w.get('title', '')}".lower()
                return any(name in haystack for name in _DESKTOP_WINDOW_NAMES)

            desktop = [w for w in windows if _is_desktop_window(w)]
            if not desktop:
                return CaptureResult(
                    mode=mode, width=0, height=0, png_b64=None,
                    elements=[], app="",
                    window_title=(
                        f"<no desktop/shell window found for app={app!r}; "
                        f"cua-driver captures one window at a time and exposes "
                        f"no whole-virtual-desktop or per-monitor capture. "
                        f"Call list_apps / capture(app='<AppName>') to target a "
                        f"specific window instead. On Windows the taskbar is "
                        f"'Shell_TrayWnd' and the desktop is 'Progman'.>"
                    ),
                    png_bytes_len=0,
                )
            # Prefer the desktop backdrop (Progman/WorkerW/Finder) over the
            # taskbar when both are present, so a bare "screen" capture shows
            # the full desktop rather than just the task strip.
            windows = sorted(
                desktop,
                key=lambda w: 0 if any(
                    n in f"{w.get('app_name', '')} {w.get('title', '')}".lower()
                    for n in ("progman", "workerw", "program manager", "finder", "desktop")
                ) else 1,
            )
        elif app:
            app_lower = app.lower()
            filtered = [w for w in windows if app_lower in w["app_name"].lower()]
            if not filtered:
                return CaptureResult(
                    mode=mode, width=0, height=0, png_b64=None,
                    elements=[], app="",
                    window_title=(
                        f"<no on-screen window matched app={app!r}; "
                        f"call list_apps to see available app names "
                        f"(macOS reports localized names, e.g. '計算機' "
                        f"instead of 'Calculator')>"
                    ),
                    png_bytes_len=0,
                )
            windows = filtered

        # Pick first on-screen window (sorted by z_index / z-order above).
        target = next((w for w in windows if not w["off_screen"]), windows[0])
        self._active_pid = target["pid"]
        self._active_window_id = target["window_id"]
        app_name = target["app_name"]
        # Remember the target's screen rect for image→screen coordinate mapping.
        self._active_window_rect = (
            (int(target["x"]), int(target["y"]),
             int(target["width"]), int(target["height"]))
            if all(target.get(k) is not None
                   for k in ("x", "y", "width", "height"))
            else None
        )
        self._active_image_size = None  # set once the screenshot dims are known
        # Record the resolved app name so capture_after= follow-ups can re-target
        # the same app rather than falling back to the frontmost window.
        if app or not self._last_app:
            self._last_app = app_name

        # Step 2: capture.
        png_b64: Optional[str] = None
        image_mime_type: Optional[str] = None
        elements: List[UIElement] = []
        width = height = 0
        window_title = ""

        if mode == "vision":
            # Plain screenshot, no AX walk. cua-driver dropped the standalone
            # `screenshot` tool (≥0.5.x) and folded full-window PNG capture
            # into `get_window_state`. Route accordingly:
            #   * Driver advertises `screenshot` (older builds) → use it; it's
            #     the cheapest path (no AX tree walked server-side).
            #   * Otherwise (current drivers) → call `get_window_state` but
            #     DISCARD the AX tree/elements, returning only the PNG. Vision
            #     mode's whole contract is "just the pixels, no element noise",
            #     so we drop everything but the image.
            # When capability discovery hasn't run (empty map), we don't trust
            # a negative `_has_tool` answer — we still try `screenshot` first
            # and fall back if the driver rejects it, so the path self-heals on
            # any driver version.
            use_screenshot = (
                self._session._has_tool("screenshot")
                or not self._session.capabilities_discovered
            )
            sc_out: Optional[Dict[str, Any]] = None
            if use_screenshot:
                sc_out = self._session.call_tool(
                    "screenshot",
                    {
                        "window_id": self._active_window_id,
                        "format": "jpeg",
                        "quality": 85,
                        "session": self._session_id,
                    },
                    timeout=_CAPTURE_TIMEOUT,
                )
                png_b64, image_mime_type = _image_from_tool_result(sc_out)
                if not png_b64:
                    # Driver had no usable `screenshot` (e.g. "Unknown tool:
                    # screenshot" on ≥0.5.x, or an empty image part). Fall
                    # through to the get_window_state path below.
                    sc_out = None

            if sc_out is None:
                gws_out = self._session.call_tool(
                    "get_window_state",
                    {
                        "pid": self._active_pid,
                        "window_id": self._active_window_id,
                        "session": self._session_id,
                    },
                    timeout=_CAPTURE_TIMEOUT,
                )
                png_b64, image_mime_type = _image_from_tool_result(gws_out)
                # Still grab the window title — it's cheap and useful in the
                # vision response — but deliberately leave `elements` empty so
                # vision stays free of AX-tree noise.
                text = gws_out["data"] if isinstance(gws_out["data"], str) else ""
                _, tree = _split_tree_text(text)
                wt = re.search(r'AXWindow\s+"([^"]+)"', tree)
                if wt:
                    window_title = wt.group(1)
        else:
            # get_window_state: AX tree (+ screenshot only for 'som').
            # Pass capture_mode through so 'ax' skips rendering/transferring a
            # screenshot entirely (the fast, text-only navigation path);
            # 'som' still gets the numbered-overlay screenshot. Without this we
            # fell back to cua-driver's default (som) and produced an image
            # even for 'ax'.
            gws_out = self._session.call_tool(
                "get_window_state",
                {
                    "pid": self._active_pid,
                    "window_id": self._active_window_id,
                    "session": self._session_id,
                    "capture_mode": mode,
                },
                timeout=_CAPTURE_TIMEOUT,
            )
            text = gws_out["data"] if isinstance(gws_out["data"], str) else ""
            summary, tree = _split_tree_text(text)

            # Parse element count from summary e.g. "✅ AppName — 42 elements, turn 3..."
            m = re.search(r'(\d+)\s+elements?', summary)

            # Surface 2 of the cua-driver integration: prefer the
            # canonical structuredContent.elements array (trycua/cua#1961).
            # Falls back to markdown regex parsing for cua-driver builds
            # that didn't carry the structured shape — those bounds come
            # back (0,0,0,0); the structured path preserves real frames.
            sc_elements = (gws_out.get("structuredContent") or {}).get("elements")
            if isinstance(sc_elements, list) and sc_elements:
                elements = _parse_elements_from_structured(sc_elements)
            else:
                elements = _parse_elements_from_tree(tree) if tree else []

            # Surface 6: refresh the snapshot-token cache from this
            # capture. Tokens are tied to a specific cua-driver snapshot
            # — when a fresh capture lands, the prior snapshot's tokens
            # are stale, so we overwrite the whole map (and clear it
            # entirely when the new capture carries none).
            self._snapshot_tokens = {
                e.index: e.element_token
                for e in elements
                if e.element_token
            }

            # Image may arrive as an MCP image part or inside
            # structuredContent (screenshot_png_b64) depending on the driver
            # build — _image_from_tool_result handles both. In 'ax' mode we
            # never want pixels: drop any image an older driver returns so the
            # response stays text-only (fast, no per-step screenshot).
            if mode == "ax":
                png_b64, image_mime_type = None, None
            else:
                png_b64, image_mime_type = _image_from_tool_result(gws_out)

            # Extract window title from the AX tree first AXWindow line.
            wt = re.search(r'AXWindow\s+"([^"]+)"', tree)
            if wt:
                window_title = wt.group(1)

        png_bytes_len = 0
        if png_b64:
            try:
                raw = base64.b64decode(png_b64, validate=False)
                png_bytes_len = len(raw)
                detected_width, detected_height = _image_dimensions_from_bytes(raw)
                if detected_width and detected_height:
                    width = detected_width
                    height = detected_height
            except Exception:
                png_bytes_len = len(png_b64) * 3 // 4

        # Record the screenshot dims the model will see, so raw coordinates it
        # picks off this image map correctly onto the window's screen rect.
        self._active_image_size = (width, height) if (width and height) else None

        return CaptureResult(
            mode=mode,
            width=width,
            height=height,
            png_b64=png_b64,
            elements=elements,
            app=app_name,
            window_title=window_title,
            png_bytes_len=png_bytes_len,
            image_mime_type=image_mime_type,
            window_rect=self._active_window_rect,
        )

    # ── Pointer ────────────────────────────────────────────────────
    def _to_screen_xy(self, x: int, y: int) -> Tuple[int, int]:
        """Map a pixel the model picked off the last capture's screenshot to the
        SCREEN-GLOBAL coordinate cua-driver clicks in.

        cua-driver returns a window-cropped screenshot (origin = the window's
        top-left, downscaled to max_image_dimension) but expects screen-global
        points for x/y. Translate by the window origin and rescale by
        window/image, then clamp into the window rect so a bad guess can't fling
        the cursor off-screen. If we don't have both the window rect and the
        image size, pass the value through unchanged (defensive)."""
        rect = self._active_window_rect
        img = self._active_image_size
        if not rect or not img:
            return int(x), int(y)
        wx, wy, ww, wh = rect
        iw, ih = img
        if not (ww and wh and iw and ih):
            return int(x), int(y)
        sx = wx + x * (ww / iw)
        sy = wy + y * (wh / ih)
        # Clamp into the captured window's screen rect.
        sx = min(max(sx, wx), wx + ww)
        sy = min(max(sy, wy), wy + wh)
        return int(round(sx)), int(round(sy))

    def click(
        self,
        *,
        element: Optional[int] = None,
        x: Optional[int] = None,
        y: Optional[int] = None,
        button: str = "left",
        click_count: int = 1,
        modifiers: Optional[List[str]] = None,
    ) -> ActionResult:
        pid = self._active_pid
        if pid is None:
            return ActionResult(ok=False, action="click",
                                message="No active window — call capture() first.")

        # Choose tool by click_count only — single-vs-double — and pass the
        # button through to `click`'s `button` enum (Surface 5 of
        # the cua-driver integration). cua-driver-rs gained an explicit
        # `button: "left"|"right"|"middle"` arg on `click` in trycua/cua#1961
        # which rejects unknown buttons; before that, `middle` was silently
        # mapped to a left-click via name-routing through `right_click`.
        # `right_click`/`middle_click` MCP tools are deprecated aliases —
        # kept around but no longer invoked from here.
        button_norm = (button or "left").lower()
        if button_norm not in {"left", "right", "middle"}:
            return ActionResult(ok=False, action="click",
                                message=f"unknown button {button!r} — expected left, right, middle.")
        tool = "double_click" if click_count == 2 else "click"

        args: Dict[str, Any] = {"pid": pid, "button": button_norm}
        if element is not None:
            if self._active_window_id is None:
                return ActionResult(ok=False, action=tool,
                                    message="No active window_id for element_index click.")
            args["element_index"] = element
            args["window_id"] = self._active_window_id
        elif x is not None and y is not None:
            args["x"], args["y"] = self._to_screen_xy(x, y)
        else:
            return ActionResult(ok=False, action=tool,
                                message="click requires element= or x/y.")
        if modifiers:
            args["modifier"] = modifiers

        res = self._action(tool, args)

        # Double-click is the gesture most often reported as "didn't take"
        # (e.g. opening a desktop icon). It can fail transiently — a stale
        # element snapshot, or the OS swallowing one of the two events under
        # load. Retry the identical call once before giving up. This is
        # coordinate-space-agnostic (we re-send the same args, not a guessed
        # pixel) so it can't make a good target worse.
        if tool == "double_click" and not res.ok:
            logger.debug("double_click failed (%s); retrying once", res.message)
            res = self._action(tool, args)

        return res

    def drag(
        self,
        *,
        from_element: Optional[int] = None,
        to_element: Optional[int] = None,
        from_xy: Optional[Tuple[int, int]] = None,
        to_xy: Optional[Tuple[int, int]] = None,
        button: str = "left",
        modifiers: Optional[List[str]] = None,
    ) -> ActionResult:
        pid = self._active_pid
        if pid is None:
            return ActionResult(ok=False, action="drag",
                                message="No active window — call capture() first.")
        args: Dict[str, Any] = {"pid": pid}
        if from_element is not None and to_element is not None:
            if self._active_window_id is None:
                return ActionResult(ok=False, action="drag",
                                    message="No active window_id for element-based drag.")
            args["from_element"] = from_element
            args["to_element"] = to_element
            args["window_id"] = self._active_window_id
        elif from_xy is not None and to_xy is not None:
            args["from_x"], args["from_y"] = self._to_screen_xy(from_xy[0], from_xy[1])
            args["to_x"], args["to_y"] = self._to_screen_xy(to_xy[0], to_xy[1])
        else:
            return ActionResult(ok=False, action="drag",
                                message="drag requires from_element/to_element or from_coordinate/to_coordinate.")
        return self._action("drag", args)

    def scroll(
        self,
        *,
        direction: str,
        amount: int = 3,
        element: Optional[int] = None,
        x: Optional[int] = None,
        y: Optional[int] = None,
        modifiers: Optional[List[str]] = None,
        by: Optional[str] = None,
        verify: bool = True,
    ) -> ActionResult:
        pid = self._active_pid
        if pid is None:
            return ActionResult(ok=False, action="scroll",
                                message="No active window — call capture() first.")
        args: Dict[str, Any] = {
            "pid": pid,
            "direction": direction,
            "amount": max(1, min(50, amount)),
        }
        if by in ("line", "page"):
            args["by"] = by
        # Always pin the target window. cua-driver's scroll delivers wheel
        # events to the pid's focused region; with a multi-window pid (every
        # browser) that's ambiguous, and some driver builds outright refuse
        # ("Provide window_id"). The window we captured is the one the model
        # is reasoning about — send it on every path, not just element ones.
        # (An earlier fix aimed x/y at the window centre instead, but the
        # driver's scroll schema carries no x/y at all — those args are
        # silently dropped, so window_id is the targeting that actually
        # holds. Explicit coordinates are still forwarded below for any
        # future driver that grows wheel-at-point support.)
        if self._active_window_id is not None:
            args["window_id"] = self._active_window_id
        if element is not None and self._active_window_id is not None:
            args["element_index"] = element
        elif x is not None and y is not None:
            args["x"], args["y"] = self._to_screen_xy(x, y)

        # Wheel scrolls fail *silently*: the driver reports success even when
        # the events landed on a non-scrollable region (focused address bar,
        # comment box, taskbar) and nothing moved. Fingerprint the window's
        # AX state around the scroll so the model gets an explicit
        # moved=true/false instead of discovering the failure two captures
        # later. Skipped for element-targeted scrolls: the fingerprint's
        # get_window_state takes a fresh driver-side snapshot, which can
        # mark the element_token this very scroll carries as stale.
        verify = verify and element is None
        before = self._viewport_fingerprint() if verify else None
        res = self._action("scroll", args)
        if verify and res.ok and before is not None:
            after = self._viewport_fingerprint()
            if after is not None:
                moved = after != before
                res.meta["moved"] = moved
                if not moved:
                    hint = (
                        "viewport did not change after the scroll — the wheel "
                        "likely landed on a non-scrollable region. Try "
                        "element=<a scrollable container from capture>, a "
                        "coordinate over the pane you want to move, by='page', "
                        "or click inside the pane first to move focus."
                    )
                    res.message = f"{res.message} | {hint}" if res.message else hint
        return res

    def _viewport_fingerprint(self) -> Optional[str]:
        """Hash of the active window's AX state (roles + labels + frames).

        Used to detect whether a wheel scroll actually moved anything: any
        viewport movement shifts element frames (or swaps elements entirely),
        changing the hash. Returns None when no fingerprint could be taken —
        callers treat that as "unknown", never as evidence of movement.
        Text-only AX walk (capture_mode='ax'): no screenshot is rendered or
        transferred, so this is the cheap path, same as ax-mode capture.
        """
        if self._active_pid is None:
            return None
        args: Dict[str, Any] = {
            "pid": self._active_pid,
            "session": self._session_id,
            "capture_mode": "ax",
        }
        if self._active_window_id is not None:
            args["window_id"] = self._active_window_id
        try:
            out = self._session.call_tool("get_window_state", args,
                                          timeout=_CAPTURE_TIMEOUT)
        except Exception as e:
            logger.debug("scroll-verify get_window_state failed: %s", e)
            return None
        if out.get("isError"):
            return None
        sc_elements = (out.get("structuredContent") or {}).get("elements")
        if isinstance(sc_elements, list) and sc_elements:
            elements = _parse_elements_from_structured(sc_elements)
            sig = ";".join(
                f"{e.role}|{e.label}|{e.bounds[0]},{e.bounds[1]}"
                for e in elements
            )
        else:
            data = out.get("data")
            sig = data if isinstance(data, str) and data else ""
        if not sig:
            return None
        return hashlib.sha1(sig.encode("utf-8", "replace")).hexdigest()

    # ── Keyboard ───────────────────────────────────────────────────
    def type_text(self, text: str) -> ActionResult:
        pid = self._active_pid
        if pid is None:
            return ActionResult(ok=False, action="type_text",
                                message="No active window — call capture() first.")
        return self._action("type_text", {"pid": pid, "text": text})

    def key(self, keys: str) -> ActionResult:
        pid = self._active_pid
        if pid is None:
            return ActionResult(ok=False, action="key",
                                message="No active window — call capture() first.")

        key_name, modifiers = _parse_key_combo(keys)
        if not key_name:
            return ActionResult(ok=False, action="key",
                                message=f"Could not parse key from '{keys}'.")

        if modifiers:
            # hotkey requires at least one modifier + one key.
            return self._action("hotkey", {"pid": pid, "keys": modifiers + [key_name]})
        else:
            return self._action("press_key", {"pid": pid, "key": key_name})

    # ── Value setter ────────────────────────────────────────────────
    def set_value(self, value: str, element: Optional[int] = None) -> ActionResult:
        """Set a value on an element. Handles AXPopUpButton selects natively."""
        pid = self._active_pid
        window_id = self._active_window_id
        if pid is None or window_id is None:
            return ActionResult(ok=False, action="set_value",
                                message="No active window — call capture() first.")
        if element is None:
            return ActionResult(ok=False, action="set_value",
                                message="set_value requires element= (element index).")
        args: Dict[str, Any] = {
            "pid": pid,
            "window_id": window_id,
            "element_index": element,
            "value": value,
        }
        return self._action("set_value", args)

    # ── Introspection ──────────────────────────────────────────────
    def list_apps(self) -> List[Dict[str, Any]]:
        out = self._session.call_tool("list_apps", {"session": self._session_id})
        data = out["data"]
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("apps", [])
        # list_apps returns plain text — parse app lines.
        if isinstance(data, str):
            apps = []
            for line in data.splitlines():
                m = re.search(r'(.+?)\s+\(pid\s+(\d+)\)', line)
                if m:
                    apps.append({"name": m.group(1).strip(), "pid": int(m.group(2))})
            return apps
        return []

    def _list_windows_raw(self, on_screen_only: bool = False) -> List[Dict[str, Any]]:
        """Call the cua-driver `list_windows` MCP tool and return the raw window
        dicts. Uses a wider timeout than a normal action and retries once on a
        slow-op timeout: enumeration on a busy Windows host regularly overran
        the 15s default, surfacing as `list_windows failed:` / `capture
        failed:` and blinding the agent. call_tool already recovers a
        dead/closed daemon; this only adds headroom + one retry for a live-but-
        slow enumeration."""
        args = {"on_screen_only": bool(on_screen_only), "session": self._session_id}
        try:
            out = self._session.call_tool(
                "list_windows", args, timeout=_LIST_WINDOWS_TIMEOUT)
        except (TimeoutError, concurrent.futures.TimeoutError):
            logger.warning("cua-driver list_windows timed out; retrying once")
            out = self._session.call_tool(
                "list_windows", args, timeout=_LIST_WINDOWS_TIMEOUT)
        return (out.get("structuredContent") or {}).get("windows") or []

    def list_windows(self, on_screen_only: bool = False) -> List[Dict[str, Any]]:
        """Enumerate ALL top-level windows (incl. minimized / background by
        default) so the agent can see and target every window, not just the
        frontmost one. Returns ``[{app, pid, window_id, title, on_screen}]``."""
        raw = self._list_windows_raw(on_screen_only)
        result: List[Dict[str, Any]] = []
        for w in raw:
            if w.get("pid") is None or w.get("window_id") is None:
                continue
            app_name = w.get("app_name") or ""
            title = w.get("title") or ""
            # Hide the driver's own surfaces (cua-driver.exe, the
            # Cua.AgentCursorOverlay window): they show up on every
            # enumeration, aren't controllable, and models kept trying to
            # target them.
            if "cua-driver" in app_name.lower() or title.startswith("Cua."):
                continue
            result.append({
                "app": app_name,
                "pid": int(w["pid"]),
                "window_id": int(w["window_id"]),
                "title": title,
                "on_screen": bool(w.get("is_on_screen", True)),
            })
        return result

    def minimize(self, *, pid: Optional[int] = None,
                 window_id: Optional[int] = None) -> ActionResult:
        """Minimize a window. cua-driver has no minimize tool, so route the OS
        minimize shortcut to the window (best-effort: bring it to front first so
        the shell shortcut targets it). If this proves unreliable for an app,
        the agent can capture the window and click its minimize button by
        element index instead."""
        pid = pid if pid is not None else self._active_pid
        window_id = window_id if window_id is not None else self._active_window_id
        if pid is None:
            return ActionResult(ok=False, action="minimize",
                                message="No window — call capture()/list_windows first.")
        # Activate the target so the shell minimize shortcut lands on it.
        self.bring_to_front(pid=pid, window_id=window_id)
        if sys.platform == "darwin":
            combo = "cmd+m"
        elif sys.platform == "win32":
            combo = "win+down"
        else:
            combo = "super+h"
        # hotkey requires `keys` as an array (["win", "down"]), same as key().
        # A bare combo string used to fail with "Missing required array field
        # keys." on every platform.
        key_name, modifiers = _parse_key_combo(combo)
        args: Dict[str, Any] = {"keys": modifiers + [key_name], "pid": pid}
        if window_id is not None:
            args["window_id"] = window_id
        res = self._action("hotkey", args)
        return ActionResult(ok=res.ok, action="minimize", message=res.message, meta=res.meta)

    def focus_app(self, app: str, raise_window: bool = False) -> ActionResult:
        """Target an app for subsequent actions. By default selects the window
        without stealing focus; when ``raise_window`` is set, bring it to the
        front (used to restore/activate a minimized or background window so it
        can be controlled).
        """
        raw_windows = self._list_windows_raw(on_screen_only=False)
        windows = []
        for w in raw_windows:
            # Skip compositor windows with a null pid/window_id/app_name
            # (Linux/X11 surfaces these; they aren't actionable).
            if w.get("pid") is None or w.get("window_id") is None:
                continue
            windows.append({
                "app_name": w.get("app_name") or "",
                "pid": int(w["pid"]),
                "window_id": int(w["window_id"]),
                "z_index": w.get("z_index") or 0,
            })
        windows.sort(key=lambda w: w["z_index"])

        app_lower = app.lower()
        matched = [w for w in windows if app_lower in w["app_name"].lower()]
        # Don't silently fall back to the frontmost window when the filter
        # matches nothing — that hides the real failure (often a localized
        # macOS app name mismatch, e.g. caller passed "Calculator" but
        # list_windows returns "計算機").
        target = matched[0] if matched else None
        if target:
            self._active_pid = target["pid"]
            self._active_window_id = target["window_id"]
            self._last_app = target["app_name"]  # preserve for capture_after= follow-ups
            if raise_window:
                self.bring_to_front(pid=target["pid"], window_id=target["window_id"])
            return ActionResult(
                ok=True, action="focus_app",
                message=(
                    f"Targeted {target['app_name']} (pid {self._active_pid}, "
                    f"window {self._active_window_id})"
                    + (" and brought it to front."
                       if raise_window else " without raising window.")
                ),
            )
        return ActionResult(ok=False, action="focus_app",
                            message=f"No window found for app '{app}'.")

    # ── App lifecycle ────────────────────────────────────────────────
    #
    # cua-driver exposes launch_app / kill_app / bring_to_front as a
    # complete set. focus_app() above is a *window-selector* (no
    # process state change); these methods drive the process layer.

    def launch_app(
        self,
        *,
        bundle_id: Optional[str] = None,
        name: Optional[str] = None,
        urls: Optional[List[str]] = None,
        additional_arguments: Optional[List[str]] = None,
        creates_new_application_instance: bool = False,
    ) -> Dict[str, Any]:
        """Idempotent launch. Returns ``{pid, bundle_id, name, windows[]}``
        so callers can skip an extra ``list_windows`` round-trip before
        ``get_window_state``.

        ``creates_new_application_instance=True`` forces a new instance
        even if the app is already running — use it when concurrent
        runs may touch the same app so each session gets its own
        isolated window.

        ⚠ ``additional_arguments`` / ``creates_new_application_instance``
        are NOT in the driver's launch_app schema as of 0.7.0 and are
        silently dropped (the driver ignores unknown args). They're kept
        for forward-compat only — code that needs command-line flags must
        use ``open_app`` (which spawns directly when flags are given)."""
        if not bundle_id and not name:
            raise ValueError("launch_app requires either bundle_id or name")
        args: Dict[str, Any] = {"session": self._session_id}
        if bundle_id:
            args["bundle_id"] = bundle_id
        if name:
            args["name"] = name
        if urls:
            args["urls"] = list(urls)
        if additional_arguments:
            args["additional_arguments"] = list(additional_arguments)
        if creates_new_application_instance:
            args["creates_new_application_instance"] = True
        out = self._session.call_tool("launch_app", args)
        return out["structuredContent"] or {"data": out["data"]}

    # Common executable names per browser family, for resolving a friendly
    # name ("chrome") to a spawnable command on PATH (Linux) — the driver's
    # launch_app resolves names itself but cannot carry command-line flags
    # (its schema has no additional_arguments; unknown args are silently
    # dropped, verified against 0.6.5 and 0.7.0).
    _APP_COMMAND_ALIASES: Dict[str, List[str]] = {
        "chrome": ["google-chrome", "google-chrome-stable", "chrome"],
        "chromium": ["chromium", "chromium-browser"],
        "edge": ["microsoft-edge", "microsoft-edge-stable", "msedge"],
        "msedge": ["microsoft-edge", "microsoft-edge-stable", "msedge"],
        "brave": ["brave-browser", "brave"],
        "firefox": ["firefox"],
        "opera": ["opera"],
        "vivaldi": ["vivaldi"],
    }

    def open_app(
        self,
        *,
        app: str,
        url: Optional[str] = None,
        args: Optional[List[str]] = None,
        new_instance: bool = False,
    ) -> ActionResult:
        """Model-facing launch. `app` may be a display name, executable
        name, or path. When command-line `args` (or `new_instance`) are
        requested, the process is spawned directly on this host — the
        driver's `launch_app` tool cannot carry flags — otherwise the
        driver resolves and launches the app itself. Either way the new
        app becomes the active target for subsequent actions."""
        flags_note = ""
        if args or new_instance:
            res = self._spawn_app(app, url, list(args or []), new_instance)
            if res is not None:
                return res
            # Spawn path couldn't resolve an executable — fall through to
            # the driver launch, which cannot apply the flags.
            flags_note = (
                " WARNING: could not resolve an executable to apply the "
                "launch flags; the app was launched WITHOUT them."
            )
        try:
            out = self.launch_app(name=app, urls=[url] if url else None)
        except Exception as e:
            return ActionResult(
                ok=False, action="open_app",
                message=f"launch failed for {app!r}: "
                        f"{type(e).__name__}: {e}".rstrip(": "),
            )
        pid = out.get("pid") if isinstance(out, dict) else None
        windows = (out.get("windows") if isinstance(out, dict) else None) or []
        meta: Dict[str, Any] = {"pid": pid, "windows": []}
        for w in windows:
            if not isinstance(w, dict):
                continue
            meta["windows"].append({
                "window_id": w.get("window_id") or w.get("id"),
                "title": w.get("title") or "",
            })
        if pid is not None:
            self._active_pid = int(pid)
            self._retarget_window_state(int(pid), None)
        titles = ", ".join(repr(w["title"]) for w in meta["windows"]
                           if w.get("title")) or "(no windows yet)"
        return ActionResult(
            ok=True, action="open_app",
            message=(f"Launched {app} (pid {pid}); windows: {titles}. "
                     f"It is now the active target.{flags_note}"),
            meta=meta,
        )

    def _resolve_app_command(self, app: str) -> Optional[str]:
        """Resolve `app` to something spawnable, or None."""
        # Explicit path (or something on PATH) wins.
        if os.path.sep in app or (os.path.altsep and os.path.altsep in app):
            return app if os.path.exists(app) else None
        if shutil.which(app):
            return app
        key = app.lower().removesuffix(".exe").replace(" ", "-")
        for candidate in self._APP_COMMAND_ALIASES.get(key, []):
            if shutil.which(candidate):
                return candidate
        return None

    def _spawn_app(self, app: str, url: Optional[str],
                   args: List[str], new_instance: bool) -> Optional[ActionResult]:
        """Launch `app` directly with command-line args (driver launch_app
        can't carry them). Returns None when no executable could be
        resolved, so the caller can fall back to the driver. cua-driver
        always runs on this same host, so a local spawn lands on the same
        desktop the driver controls."""
        tail = args + ([url] if url else [])
        try:
            if sys.platform == "win32":
                # `start` resolves App Paths names (chrome, msedge, …) and
                # detaches. The empty "" is the window title slot.
                subprocess.Popen(
                    ["cmd", "/c", "start", "", app, *tail],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            elif sys.platform == "darwin":
                cmd = ["open", "-a", app]
                if new_instance:
                    cmd.append("-n")
                if url:
                    cmd.append(url)
                if args:
                    cmd += ["--args", *args]
                subprocess.Popen(
                    cmd, stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            else:
                command = self._resolve_app_command(app)
                if command is None:
                    return None
                subprocess.Popen(
                    [command, *tail], stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
        except OSError as e:
            return ActionResult(
                ok=False, action="open_app",
                message=f"launch failed for {app!r}: {type(e).__name__}: {e}",
            )
        target = self._wait_for_app_window(app)
        if target is not None:
            self._active_pid = target["pid"]
            self._active_window_id = target["window_id"]
            if target.get("app_name"):
                self._last_app = target["app_name"]
            self._retarget_window_state(target["pid"], target["window_id"])
            return ActionResult(
                ok=True, action="open_app",
                message=(f"Launched {app} with args (pid {target['pid']}, "
                         f"window {target['title']!r}). It is now the "
                         f"active target."),
                meta={"pid": target["pid"], "windows": [
                    {"window_id": target["window_id"],
                     "title": target["title"]},
                ]},
            )
        return ActionResult(
            ok=True, action="open_app",
            message=(f"Launched {app} with args; no window observed yet — "
                     f"wait a moment and call list_windows."),
            meta={"pid": None, "windows": []},
        )

    def _wait_for_app_window(self, app: str,
                             timeout: float = 6.0) -> Optional[Dict[str, Any]]:
        """Poll window enumeration until a window matching `app` appears.
        Returns {pid, window_id, app_name, title} or None."""
        import time as _time

        base = app.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        base = base.lower().removesuffix(".exe").replace(" ", "")
        deadline = _time.monotonic() + timeout
        while True:
            try:
                raw = self._list_windows_raw(on_screen_only=False)
            except Exception:
                raw = []
            for w in raw:
                if w.get("pid") is None or w.get("window_id") is None:
                    continue
                name = (w.get("app_name") or "").lower()
                name_flat = name.removesuffix(".exe").replace(" ", "")
                if base and (base in name_flat or name_flat in base):
                    return {
                        "pid": int(w["pid"]),
                        "window_id": int(w["window_id"]),
                        "app_name": w.get("app_name") or "",
                        "title": w.get("title") or "",
                    }
            if _time.monotonic() >= deadline:
                return None
            _time.sleep(0.25)

    def kill_app(self, *, pid: int) -> ActionResult:
        """Terminate by pid. Equivalent to ``kill -9`` on POSIX,
        ``taskkill /F`` on Windows."""
        return self._action("kill_app", {"pid": int(pid)})

    def bring_to_front(self, *, pid: int,
                       window_id: Optional[int] = None) -> ActionResult:
        """Activate a window so subsequent foreground-dispatched input
        lands on it. cua-driver's docstring notes this is the cheaper
        path than per-call SetForegroundWindow flashes."""
        args: Dict[str, Any] = {"pid": int(pid)}
        if window_id is not None:
            args["window_id"] = int(window_id)
        res = self._action("bring_to_front", args)
        if res.ok:
            # The just-raised window is now the action target: retarget the
            # active-window state so capture_after= follow-ups and subsequent
            # type/key/scroll land on it instead of whatever was captured
            # last. Pre-fix, focus_window(chrome)+capture_after returned the
            # previous capture's app (the desktop) and typed into the old pid.
            self._active_pid = int(pid)
            if window_id is not None:
                self._active_window_id = int(window_id)
            self._retarget_window_state(int(pid), window_id)
        return res

    def _retarget_window_state(self, pid: int,
                               window_id: Optional[int]) -> None:
        """Best-effort refresh of `_last_app`/`_active_window_id`/
        `_active_window_rect` from window enumeration after the action
        target changed (bring_to_front / launch_app). Never raises: when
        enumeration fails the pid is still set and the stale rect is
        cleared so coordinate mapping can't use the wrong window's frame."""
        self._active_window_rect = None
        self._active_image_size = None
        try:
            raw_windows = self._list_windows_raw(on_screen_only=False)
        except Exception:
            return
        match = None
        for w in raw_windows:
            if w.get("pid") is None or int(w["pid"]) != pid:
                continue
            if window_id is not None and w.get("window_id") is not None \
                    and int(w["window_id"]) != window_id:
                continue
            match = w
            if window_id is not None:
                break
            if w.get("is_on_screen", True):
                break
        if match is None:
            return
        if match.get("window_id") is not None:
            self._active_window_id = int(match["window_id"])
        if match.get("app_name"):
            self._last_app = match["app_name"]
        if all(match.get(k) is not None
               for k in ("x", "y", "width", "height")):
            self._active_window_rect = (
                int(match["x"]), int(match["y"]),
                int(match["width"]), int(match["height"]),
            )

    # ── Pointer + display introspection ─────────────────────────────

    def move_cursor(self, x: int, y: int) -> ActionResult:
        """Move the agent-cursor *overlay* to a screen point. This is a
        visual hint — it does NOT move the real OS pointer (cua-driver
        explicitly avoids stealing pointer focus). The overlay glides
        smoothly to the target, so consumers use it before a click to
        give a visible "where the agent is going" cue."""
        sx, sy = self._to_screen_xy(x, y)
        return self._action("move_cursor", {"x": sx, "y": sy})

    def get_cursor_position(self) -> Tuple[int, int]:
        """Return the *real* OS cursor position in screen points
        (origin top-left)."""
        out = self._session.call_tool(
            "get_cursor_position", {"session": self._session_id}
        )
        sc = out.get("structuredContent") or {}
        return int(sc.get("x", 0)), int(sc.get("y", 0))

    def get_screen_size(self) -> Dict[str, Any]:
        """Return the logical size of the main display in points plus
        its backing scale factor. Shape:
        ``{width, height, backing_scale_factor}``."""
        out = self._session.call_tool(
            "get_screen_size", {"session": self._session_id}
        )
        return out.get("structuredContent") or {}

    def zoom(self, *, window_id: int, x: float, y: float, w: float, h: float,
             pid: Optional[int] = None) -> Dict[str, Any]:
        """Return a higher-resolution crop of a sub-region of a window for a
        closer look at a specific element. cua-driver's `zoom` takes a bounding
        box as opposite corners (x1,y1)-(x2,y2) plus pid/window_id — we accept a
        rect (x,y,w,h) and convert."""
        return self._session.call_tool("zoom", {
            "pid": int(pid) if pid is not None else self._active_pid,
            "window_id": int(window_id),
            "x1": float(x), "y1": float(y),
            "x2": float(x + w), "y2": float(y + h),
            "session": self._session_id,
        })

    # ── Agent cursor (overlay) ──────────────────────────────────────
    #
    # Sessions (start_session/end_session, wired in start/stop) own the
    # cursor. These knobs tune its appearance + behavior per-session.
    # All accept an optional `cursor_id` to address a specific cursor
    # when the run drives multiple (rare); the default is this run's
    # session id.

    def set_agent_cursor_enabled(self, enabled: bool, *,
                                 cursor_id: Optional[str] = None) -> ActionResult:
        """Toggle the agent cursor overlay's visibility for this run."""
        args: Dict[str, Any] = {"enabled": bool(enabled)}
        if cursor_id:
            args["cursor_id"] = cursor_id
        return self._action("set_agent_cursor_enabled", args)

    def set_agent_cursor_motion(self, *,
                                glide_ms: Optional[float] = None,
                                dwell_ms: Optional[float] = None,
                                idle_hide_ms: Optional[float] = None,
                                cursor_id: Optional[str] = None) -> ActionResult:
        """Tune the overlay's motion timings — glide duration, post-click
        dwell, idle-hide delay. Each None means "leave at current value"."""
        args: Dict[str, Any] = {}
        if glide_ms is not None:
            args["glide_ms"] = float(glide_ms)
        if dwell_ms is not None:
            args["dwell_ms"] = float(dwell_ms)
        if idle_hide_ms is not None:
            args["idle_hide_ms"] = float(idle_hide_ms)
        if cursor_id:
            args["cursor_id"] = cursor_id
        return self._action("set_agent_cursor_motion", args)

    def set_agent_cursor_style(self, *,
                               gradient_colors: Optional[List[str]] = None,
                               bloom_color: Optional[str] = None,
                               image_path: Optional[str] = None,
                               cursor_id: Optional[str] = None) -> ActionResult:
        """Customise the cursor body. ``gradient_colors`` are CSS hex
        strings tip→tail; ``bloom_color`` is the radial halo; an
        ``image_path`` (.svg/.png/.ico) replaces the silhouette
        entirely. Empty values revert to the palette default."""
        args: Dict[str, Any] = {}
        if gradient_colors is not None:
            args["gradient_colors"] = list(gradient_colors)
        if bloom_color is not None:
            args["bloom_color"] = bloom_color
        if image_path is not None:
            args["image_path"] = image_path
        if cursor_id:
            args["cursor_id"] = cursor_id
        return self._action("set_agent_cursor_style", args)

    def get_agent_cursor_state(self, *,
                               cursor_id: Optional[str] = None) -> Dict[str, Any]:
        """Return ``{x, y, config: {cursor_color, cursor_icon, ...},
        enabled}`` for this run's cursor (or the named ``cursor_id``)."""
        args: Dict[str, Any] = {"session": self._session_id}
        if cursor_id:
            args["cursor_id"] = cursor_id
        out = self._session.call_tool("get_agent_cursor_state", args)
        return out.get("structuredContent") or {}

    # ── Recording / replay ──────────────────────────────────────────

    def start_recording(self, *, output_dir: str,
                        record_video: bool = False) -> Dict[str, Any]:
        """Enable trajectory recording (per-turn screenshots + action
        JSON) to ``output_dir``. ``record_video=True`` ALSO captures
        the main display to ``<output_dir>/recording.mp4`` (H.264).
        Recording ownership is keyed by this run's session id so
        concurrent runs don't fight over the recorder."""
        out = self._session.call_tool("start_recording", {
            "output_dir": output_dir,
            "record_video": bool(record_video),
            "session": self._session_id,
        })
        return out.get("structuredContent") or {}

    def stop_recording(self) -> Dict[str, Any]:
        """Disable recording and finalise the mp4 (if video was on).
        Returns the recorder's final state including ``last_video_path``."""
        out = self._session.call_tool("stop_recording", {
            "session": self._session_id,
        })
        return out.get("structuredContent") or {}

    def get_recording_state(self) -> Dict[str, Any]:
        """Return the current recorder state without changing it.
        Shape: ``{recording, enabled, output_dir, next_turn,
        last_video_path, last_error, owner, video_active}``."""
        out = self._session.call_tool(
            "get_recording_state", {"session": self._session_id}
        )
        return out.get("structuredContent") or {}

    def replay_trajectory(self, *, trajectory_dir: str,
                          dry_run: bool = False,
                          speed_factor: float = 1.0) -> Dict[str, Any]:
        """Replay a prior recording's turn stream by re-invoking each
        turn's tool call in lexical order. ``dry_run=True`` logs without
        actually firing the tools."""
        return self._session.call_tool("replay_trajectory", {
            "trajectory_dir": trajectory_dir,
            "dry_run": bool(dry_run),
            "speed_factor": float(speed_factor),
            "session": self._session_id,
        })

    def install_ffmpeg(self) -> Dict[str, Any]:
        """Bootstrap ffmpeg for ``start_recording(record_video=True)``
        on Linux / Windows. macOS records natively via ScreenCaptureKit
        and doesn't need ffmpeg."""
        return self._session.call_tool(
            "install_ffmpeg", {"session": self._session_id}
        )

    # ── Config ──────────────────────────────────────────────────────

    def get_config(self) -> Dict[str, Any]:
        """Return the current cua-driver runtime config."""
        out = self._session.call_tool(
            "get_config", {"session": self._session_id}
        )
        return out.get("structuredContent") or {}

    def set_config(self, **config) -> ActionResult:
        """Set cua-driver config keys. Common keys include
        ``max_image_dimension`` (image-output resizing), recording
        flags, etc. Unknown keys are passed through verbatim — cua-driver
        validates against its own schema."""
        return self._action("set_config", dict(config))

    # ── Lower-level introspection ───────────────────────────────────

    def get_accessibility_tree(self) -> Dict[str, Any]:
        """Return a lightweight snapshot of running regular apps +
        on-screen visible windows with bounds, z-order, owner pid.
        Roughly the data ``list_windows`` exposes, in one call. Most
        callers should prefer ``capture()`` / ``focus_app()`` which
        already use this shape internally."""
        out = self._session.call_tool(
            "get_accessibility_tree", {"session": self._session_id}
        )
        return out.get("structuredContent") or {"data": out["data"]}

    # ── Browser page tool ───────────────────────────────────────────

    def page(self, *, pid: Optional[int] = None, action: str,
             **page_args: Any) -> Dict[str, Any]:
        """Interact with a browser page loaded in a running app (Chrome,
        Safari, Edge, ...). cua-driver routes through CDP / Apple Events
        / AX tree depending on the target. ``action`` + ``page_args``
        shape depends on the requested operation (``execute_javascript``
        takes ``javascript``, ``query_dom`` takes ``css_selector``, ...);
        see cua-driver's ``page`` tool description for the full grammar.

        ``pid`` defaults to the window captured last (the one the model is
        reasoning about); pass it explicitly to target another browser."""
        if pid is None:
            pid = self._active_pid
        if pid is None:
            return {"data": "No active window — call capture() first "
                            "(or pass pid= from list_windows).",
                    "isError": True}
        args: Dict[str, Any] = {
            "pid": int(pid),
            "action": action,
            "session": self._session_id,
        }
        # Pin the window only when we're implicitly targeting the captured
        # one — an explicit pid may belong to a different window entirely.
        if pid == self._active_pid and self._active_window_id is not None:
            args.setdefault("window_id", self._active_window_id)
        args.update(page_args)
        return self._session.call_tool("page", args, timeout=_CAPTURE_TIMEOUT)

    # JS run inside the page for page_scroll. Deterministic pixel scrolling
    # with exact metrics back — the wheel path can't tell the model whether
    # more content exists; this can. Placeholders are filled with
    # json.dumps'd values so selector strings can't break out of the JS.
    _PAGE_SCROLL_JS = """
(() => {
  const sel = %(selector)s;
  let el = null;
  if (sel) {
    el = document.querySelector(sel);
    if (!el) return JSON.stringify({error: "no element matches selector: " + sel});
  }
  const doc = document.scrollingElement || document.documentElement;
  const target = el || doc;
  const horizontal = %(direction)s === "left" || %(direction)s === "right";
  const vh = el ? el.clientHeight : window.innerHeight;
  const vw = el ? el.clientWidth : window.innerWidth;
  const beforeTop = target.scrollTop, beforeLeft = target.scrollLeft;
  let amount = %(amount_px)s;
  if (amount === null) amount = Math.max(1, Math.round((horizontal ? vw : vh) * 0.8));
  const dir = %(direction)s, to = %(to)s;
  if (to === "top") target.scrollTop = 0;
  else if (to === "bottom") target.scrollTop = target.scrollHeight;
  else if (horizontal) target.scrollLeft = beforeLeft + (dir === "left" ? -amount : amount);
  else target.scrollTop = beforeTop + (dir === "up" ? -amount : amount);
  const st = target.scrollTop, sh = target.scrollHeight;
  return JSON.stringify({
    scrolled_px: Math.round(horizontal ? target.scrollLeft - beforeLeft : st - beforeTop),
    scroll_top: Math.round(st),
    scroll_height: Math.round(sh),
    viewport_height: Math.round(vh),
    at_top: st <= 1,
    at_bottom: st + vh >= sh - 2,
    content_below_px: Math.max(0, Math.round(sh - vh - st))
  });
})()
""".strip()

    def page_scroll(
        self,
        *,
        pid: Optional[int] = None,
        direction: str = "down",
        amount_px: Optional[int] = None,
        selector: Optional[str] = None,
        to: Optional[str] = None,
    ) -> ActionResult:
        """Scroll the browser page (or a CSS-selected scroll container) by an
        exact pixel amount and return scroll metrics: how far it moved, the
        current offset, total scrollable height, and whether the bottom was
        reached. The reliable path for feeds and long forms — unlike wheel
        events it cannot miss the scrollable region, and the metrics tell
        the model whether content remains below the fold."""
        js = self._PAGE_SCROLL_JS % {
            "selector": json.dumps(selector),
            "direction": json.dumps(direction),
            "amount_px": json.dumps(amount_px),
            "to": json.dumps(to if to in ("top", "bottom") else None),
        }
        try:
            out = self.page(pid=pid, action="execute_javascript", javascript=js)
        except Exception as e:
            logger.exception("page_scroll failed")
            return ActionResult(ok=False, action="page_scroll",
                                message=f"cua-driver error: {e}")
        if out.get("isError"):
            msg = out.get("data") if isinstance(out.get("data"), str) else "page JS failed"
            return ActionResult(ok=False, action="page_scroll", message=str(msg))
        metrics = _parse_page_scroll_metrics(out.get("data"))
        if metrics is None:
            # JS ran but returned something we can't parse (older driver
            # wrapping, browser quirk). The scroll itself likely happened —
            # report ok with the raw payload rather than a false failure.
            raw = out.get("data")
            return ActionResult(ok=True, action="page_scroll",
                                message=f"scrolled (unparsed result: {str(raw)[:200]})")
        if "error" in metrics:
            return ActionResult(ok=False, action="page_scroll",
                                message=str(metrics["error"]))
        parts = [f"scrolled {metrics.get('scrolled_px', 0)}px {direction}"]
        below = metrics.get("content_below_px")
        if metrics.get("at_bottom"):
            parts.append("reached the bottom (infinite feeds may load more "
                         "after a moment — scroll again or wait)")
        elif isinstance(below, (int, float)) and below > 0:
            parts.append(f"{int(below)}px of content remains below")
        if metrics.get("scrolled_px") == 0 and not metrics.get("at_bottom") \
                and not metrics.get("at_top"):
            parts.append("nothing moved — the target may not be the "
                         "scrollable container; pass selector= for the "
                         "scrolling pane")
        return ActionResult(ok=True, action="page_scroll",
                            message="; ".join(parts), meta=metrics)

    # ── Generic escape hatch ────────────────────────────────────────

    def call_tool(self, name: str, args: Optional[Dict[str, Any]] = None,
                  *, timeout: float = 15.0) -> Dict[str, Any]:
        """Call any cua-driver MCP tool by name with arbitrary args.
        ``session`` is injected (preserves the caller's explicit one
        via setdefault). For tools the wrapper doesn't already type-
        wrap, this is the supported escape hatch — preferred over
        reaching for ``self._session.call_tool`` directly because it
        keeps the session-id contract consistent with everything else."""
        payload = dict(args) if args else {}
        payload.setdefault("session", self._session_id)
        return self._session.call_tool(name, payload, timeout=timeout)

    # ── Internal ───────────────────────────────────────────────────
    def _maybe_attach_element_token(self, tool: str, args: Dict[str, Any]) -> None:
        """Surface 6: when the wrapper is about to call a token-capable
        tool with `element_index`, look up the matching `element_token`
        from the last snapshot and attach it. cua-driver-rs's contract
        for combined args is documented in trycua/cua#1961:

          "element_token takes precedence over element_index when both
           supplied. Returns an explicit 'stale' error if the snapshot
           has been superseded."

        Gated on the per-tool capability claim so we don't send the
        field to drivers that predate the surface (which would reject
        the schema with `additionalProperties: false`).
        """
        idx = args.get("element_index")
        if not isinstance(idx, int):
            return
        token = self._snapshot_tokens.get(idx)
        if not token:
            return
        if not self._session.supports_capability(
            "accessibility.element_tokens", tool=tool
        ):
            return
        args["element_token"] = token

    def _action(self, name: str, args: Dict[str, Any]) -> ActionResult:
        # Attach the snapshot's element_token whenever the call carries
        # an element_index and the target tool advertises support.
        self._maybe_attach_element_token(name, args)
        # Carry this run's session id so the cua-driver agent cursor
        # and per-session state (config overrides, recording ownership)
        # stay tied to this run. setdefault preserves any explicit
        # session a caller already supplied.
        args.setdefault("session", self._session_id)
        try:
            out = self._session.call_tool(name, args)
        except Exception as e:
            logger.exception("cua-driver %s call failed", name)
            return ActionResult(ok=False, action=name, message=f"cua-driver error: {e}")
        ok = not out["isError"]
        message = ""
        data = out["data"]
        if isinstance(data, dict):
            message = str(data.get("message", ""))
        elif isinstance(data, str):
            message = data
        return ActionResult(ok=ok, action=name, message=message,
                            meta=data if isinstance(data, dict) else {})
