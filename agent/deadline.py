"""Shared deadline, bounded-execution, and process-tree primitives.

Timeouts are resolved from ``timeouts`` in Clio's config, then an optional
legacy environment variable, then the caller's default.  Every value crosses
the same platform-safe clamp before it reaches a thread or process wait.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

MAX_SAFE_TIMEOUT_S = 31_536_000.0  # one year; safely below platform time_t limits


class DeadlineExpired(TimeoutError):
    """A wall-clock deadline enforced by Clio expired."""

    def __init__(self, label: str, timeout_s: float):
        super().__init__(f"deadline expired after {timeout_s:.3g}s: {label}")
        self.label = label
        self.timeout_s = timeout_s


@dataclass(frozen=True, kw_only=True)
class BoundedResult:
    """Result of a bounded operation; operation exceptions are not captured."""

    timed_out: bool
    value: Any
    elapsed_s: float
    timeout_s: Optional[float]
    label: str

    def raise_if_timed_out(self) -> Any:
        if self.timed_out:
            raise DeadlineExpired(self.label, float(self.timeout_s or 0.0))
        return self.value


def clamp_timeout(timeout: Optional[float]) -> Optional[float]:
    """Return a wait-safe timeout; non-positive/invalid values mean unbounded."""
    if timeout is None or isinstance(timeout, bool):
        return None
    try:
        value = float(timeout)
    except (TypeError, ValueError):
        logger.warning("invalid timeout %r; treating as unbounded", timeout)
        return None
    if not math.isfinite(value):
        if math.isinf(value) and value > 0:
            return MAX_SAFE_TIMEOUT_S
        logger.warning("invalid timeout %r; treating as unbounded", timeout)
        return None
    if value <= 0:
        return None
    return min(value, MAX_SAFE_TIMEOUT_S)


def _timeouts_section() -> dict[str, Any]:
    try:
        from clio_cli.config import load_config_readonly

        section = load_config_readonly().get("timeouts")
        return section if isinstance(section, dict) else {}
    except Exception:
        logger.debug("timeout config read failed; using fallback", exc_info=True)
        return {}


def _lookup_dotted(section: dict[str, Any], key: str) -> Any:
    node: Any = section
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _coerce_resolved(raw: Any) -> tuple[bool, Optional[float]]:
    if isinstance(raw, bool):
        return False, None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return False, None
    if math.isnan(value):
        return False, None
    return True, clamp_timeout(value)


def resolve_timeout(
    key: str,
    *,
    default: Optional[float],
    env_var: Optional[str] = None,
) -> Optional[float]:
    """Resolve ``timeouts.<key>`` > legacy env var > default, then clamp it."""
    raw = _lookup_dotted(_timeouts_section(), key)
    if raw is not None:
        valid, value = _coerce_resolved(raw)
        if valid:
            return value
        logger.warning("timeouts.%s has invalid value %r; ignoring", key, raw)

    if env_var:
        env_raw = os.getenv(env_var, "").strip()
        if env_raw:
            valid, value = _coerce_resolved(env_raw)
            if valid:
                return value
            logger.warning("%s has invalid value %r; ignoring", env_var, env_raw)

    return clamp_timeout(default)


def _consume_detached(task: "asyncio.Future[Any]") -> None:
    try:
        task.exception()
    except (asyncio.CancelledError, Exception):
        pass


async def _run_abandon_cleanup(callback: Callable[[], Awaitable[Any]]) -> None:
    try:
        await callback()
    except Exception:
        logger.debug("deadline abandonment cleanup failed", exc_info=True)


async def run_bounded_async(
    awaitable: Awaitable[Any],
    timeout: Optional[float],
    *,
    label: str = "operation",
    on_abandon: Optional[Callable[[], Awaitable[Any]]] = None,
) -> BoundedResult:
    """Run an awaitable to a wall-clock bound without waiting for cancellation.

    A daemon ``threading.Timer`` owns expiry rather than an asyncio timer.  On
    expiry the inner task is cancelled and detached, so cancellation-shielded
    teardown cannot keep the caller waiting forever.
    """
    timeout_s = clamp_timeout(timeout)
    started = time.monotonic()
    if timeout_s is None:
        value = await awaitable
        return BoundedResult(
            timed_out=False,
            value=value,
            elapsed_s=time.monotonic() - started,
            timeout_s=None,
            label=label,
        )

    loop = asyncio.get_running_loop()
    task = asyncio.ensure_future(awaitable)
    expired: asyncio.Future[None] = loop.create_future()

    def _mark_expired() -> None:
        if not expired.done():
            expired.set_result(None)

    def _expire() -> None:
        try:
            loop.call_soon_threadsafe(_mark_expired)
        except RuntimeError:
            pass

    timer = threading.Timer(timeout_s, _expire)
    timer.daemon = True
    timer.start()
    try:
        try:
            done, _ = await asyncio.wait(
                {task, expired}, return_when=asyncio.FIRST_COMPLETED
            )
        except asyncio.CancelledError:
            task.cancel()
            task.add_done_callback(_consume_detached)
            raise

        if task in done:
            if not expired.done():
                expired.cancel()
            return BoundedResult(
                timed_out=False,
                value=await task,
                elapsed_s=time.monotonic() - started,
                timeout_s=timeout_s,
                label=label,
            )

        task.cancel()
        task.add_done_callback(_consume_detached)
        if on_abandon is not None:
            cleanup = asyncio.create_task(_run_abandon_cleanup(on_abandon))
            cleanup.add_done_callback(_consume_detached)
        logger.warning("deadline %r expired after %.3gs; task abandoned", label, timeout_s)
        return BoundedResult(
            timed_out=True,
            value=None,
            elapsed_s=time.monotonic() - started,
            timeout_s=timeout_s,
            label=label,
        )
    finally:
        timer.cancel()


def run_bounded_sync(
    fn: Callable[[], Any],
    timeout: Optional[float],
    *,
    label: str = "operation",
    on_timeout: Optional[Callable[[], None]] = None,
) -> BoundedResult:
    """Run a synchronous callable in a daemon worker and abandon it on expiry."""
    timeout_s = clamp_timeout(timeout)
    started = time.monotonic()
    if timeout_s is None:
        return BoundedResult(
            timed_out=False,
            value=fn(),
            elapsed_s=time.monotonic() - started,
            timeout_s=None,
            label=label,
        )

    done = threading.Event()
    box: dict[str, Any] = {}

    def _worker() -> None:
        try:
            box["value"] = fn()
        except BaseException as exc:
            box["exception"] = exc
        finally:
            done.set()

    worker = threading.Thread(target=_worker, name=f"deadline-{label}", daemon=True)
    worker.start()
    if not done.wait(timeout_s):
        if on_timeout is not None:
            try:
                on_timeout()
            except Exception:
                logger.debug("deadline timeout callback failed", exc_info=True)
        logger.warning("deadline %r expired after %.3gs; worker abandoned", label, timeout_s)
        return BoundedResult(
            timed_out=True,
            value=None,
            elapsed_s=time.monotonic() - started,
            timeout_s=timeout_s,
            label=label,
        )
    if "exception" in box:
        raise box["exception"]
    return BoundedResult(
        timed_out=False,
        value=box.get("value"),
        elapsed_s=time.monotonic() - started,
        timeout_s=timeout_s,
        label=label,
    )


def _snapshot_process_tree(pid: int) -> tuple[Any, list[Any]]:
    import psutil

    parent = psutil.Process(int(pid))
    return parent, parent.children(recursive=True)


def signal_process_tree(pid: int, sig: int) -> bool:
    """Signal a process and a pre-snapshotted descendant tree.

    Descendants are captured before the parent is signalled so reparenting
    cannot make them disappear from the walk.  A process-group signal covers
    ordinary descendants; identity-aware psutil handles descendants that made
    their own sessions.
    """
    if sys.platform == "win32":
        # Windows cannot express POSIX signal semantics for a tree.  taskkill is
        # the one reliable whole-tree primitive; callers use terminate/kill.
        return kill_process_tree(pid)

    try:
        parent, descendants = _snapshot_process_tree(pid)
    except Exception:
        parent, descendants = None, []

    signalled = False
    try:
        pgid = os.getpgid(pid)
    except (OSError, ProcessLookupError, PermissionError):
        pgid = None
    try:
        if pgid is not None and pgid == pid:
            os.killpg(pgid, sig)
        else:
            os.kill(pid, sig)
        signalled = True
    except (OSError, ProcessLookupError, PermissionError):
        pass

    for child in descendants:
        try:
            if child.is_running():
                child.send_signal(sig)
                signalled = True
        except Exception:
            pass
    # If psutil resolved the target but an os-level race hid it, report only a
    # real signal, never mere discovery.
    _ = parent
    return signalled


def kill_process_tree(pid: int, *, sig: Optional[int] = None) -> bool:
    """Hard-kill ``pid`` and all descendants, portably."""
    if sys.platform == "win32":
        try:
            from clio_cli._subprocess_compat import windows_hide_flags

            flags = windows_hide_flags()
        except Exception:
            flags = 0
        try:
            result = subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                timeout=15,
                check=False,
                creationflags=flags,
            )
            return result.returncode == 0
        except Exception:
            return False
    return signal_process_tree(pid, sig or signal.SIGKILL)


def terminate_process_tree(pid: int, *, grace_s: float = 5.0) -> bool:
    """Terminate a whole process tree, escalating survivors after ``grace_s``."""
    if sys.platform == "win32":
        return kill_process_tree(pid)

    try:
        parent, descendants = _snapshot_process_tree(pid)
    except Exception:
        parent, descendants = None, []
    sent = signal_process_tree(pid, signal.SIGTERM)
    if not sent:
        return False

    grace = clamp_timeout(grace_s)
    if grace is None:
        return True
    try:
        import psutil

        tracked = [p for p in [parent, *descendants] if p is not None]
        _, alive = psutil.wait_procs(tracked, timeout=grace)
        for proc in alive:
            try:
                proc.kill()
            except Exception:
                pass
    except Exception:
        # The identity-aware wait is best effort.  A final group/tree kill is
        # safe for the original PID and catches same-session survivors.
        kill_process_tree(pid)
    return True


__all__ = [
    "MAX_SAFE_TIMEOUT_S",
    "BoundedResult",
    "DeadlineExpired",
    "clamp_timeout",
    "resolve_timeout",
    "run_bounded_async",
    "run_bounded_sync",
    "signal_process_tree",
    "terminate_process_tree",
    "kill_process_tree",
]
