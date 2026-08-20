"""Positive process identity for long-lived Clio processes.

Long-lived processes self-register a PID *and process creation time* in an
install-scoped ledger under the machine Clio root.  Spawners can additionally
stamp children with ``CLIO_SPAWN`` so the ledger records the supervising
process's identity.  Updaters may only act on entries whose complete identity
can be revalidated; missing or unreadable identity is an unknown state and
must fail closed.

The ledger is shared by profiles because every profile uses the same source
install and virtual environment.  Each entry still carries a profile id, and
the on-disk directory is scoped by install id.  Read/modify/write operations
use a stdlib, cross-platform interprocess lock plus same-directory atomic
replacement.  Corrupt ledgers are quarantined rather than interpreted as an
empty roster.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import platform
import re
import tempfile
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import IO, Any, Iterator, Optional, cast

logger = logging.getLogger(__name__)

SPAWN_ENV_VAR = "CLIO_SPAWN"
_TAG_VERSION = "v1"
LEDGER_FILENAME = "spawn-ledger.json"
REAPABLE_PURPOSES = frozenset({"serve", "dashboard", "gateway"})
_PURPOSE_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
_IS_WINDOWS = platform.system() == "Windows"
_CREATE_TIME_TOLERANCE = 0.05
_SPAWNER_TIME_TOLERANCE = 2.0
_LOCK_TIMEOUT_SECONDS = 5.0
_LOCK_POLL_SECONDS = 0.025

# The job handle must remain open for this process's lifetime.  Closing it is
# what asks Windows to terminate every process still assigned to the job.
_JOB_HANDLE: object | None = None
_JOB_LOCK = threading.Lock()
_LEDGER_THREAD_LOCK = threading.RLock()


@dataclass(frozen=True)
class SpawnTag:
    install: str
    purpose: str
    spawner_pid: int
    spawner_create: Optional[float]


@dataclass
class LedgerEntry:
    pid: int
    create_time: float
    purpose: str
    install: str
    profile: str
    spawner_pid: Optional[int]
    spawner_create: Optional[float]
    registered_at: float
    argv: str


@dataclass(frozen=True)
class HolderClassification:
    """Ledger-backed decision for one process holding an install shim."""

    pid: int
    create_time: float
    purpose: Optional[str]
    reapable: bool
    reason: str


class ProcessIdentityProbeError(RuntimeError):
    """Raised when process/ledger state cannot be proved safely."""


def _canonical_path(path: Path) -> str:
    try:
        value = str(path.resolve())
    except OSError:
        value = os.path.abspath(str(path))
    return os.path.normcase(value)


def install_id(project_root: Optional[Path] = None) -> str:
    """Return a stable, path-scoped identifier for one Clio installation."""
    if project_root is None:
        try:
            from clio_cli.main import PROJECT_ROOT as root

            project_root = Path(root)
        except Exception:
            project_root = Path(__file__).resolve().parent.parent
    canonical = _canonical_path(Path(project_root))
    return hashlib.sha256(canonical.encode("utf-8", "replace")).hexdigest()[:12]


def profile_id(profile_home: Optional[Path] = None) -> str:
    """Return a non-reversible id for the active profile directory."""
    if profile_home is None:
        try:
            from clio_constants import get_clio_home

            profile_home = Path(get_clio_home())
        except Exception:
            profile_home = Path(os.environ.get("CLIO_HOME") or Path.home() / ".clio")
    canonical = _canonical_path(Path(profile_home))
    return hashlib.sha256(canonical.encode("utf-8", "replace")).hexdigest()[:12]


def _own_create_time() -> Optional[float]:
    try:
        import psutil

        value = float(psutil.Process(os.getpid()).create_time())
        return value if math.isfinite(value) and value > 0 else None
    except Exception:
        return None


def build_spawn_tag(purpose: str, *, project_root: Optional[Path] = None) -> str:
    """Build the ``CLIO_SPAWN`` value a spawner puts in a child environment."""
    if not _PURPOSE_RE.fullmatch(purpose):
        raise ValueError(f"invalid process purpose: {purpose!r}")
    create = _own_create_time()
    create_part = f"{create:.3f}" if create is not None else "-"
    return ":".join(
        (_TAG_VERSION, install_id(project_root), purpose, str(os.getpid()), create_part)
    )


def spawn_env(purpose: str, *, project_root: Optional[Path] = None) -> dict[str, str]:
    """Return an environment fragment for a Clio child process."""
    return {SPAWN_ENV_VAR: build_spawn_tag(purpose, project_root=project_root)}


def parse_spawn_tag(raw: object) -> Optional[SpawnTag]:
    """Parse a spawn tag, returning ``None`` for every malformed shape."""
    if not isinstance(raw, str):
        return None
    parts = raw.split(":")
    if len(parts) != 5 or parts[0] != _TAG_VERSION:
        return None
    _, install, purpose, pid_text, create_text = parts
    if not install or not _PURPOSE_RE.fullmatch(purpose):
        return None
    if not re.fullmatch(r"[0-9a-f]{12}", install):
        return None
    try:
        pid = int(pid_text)
    except ValueError:
        return None
    if pid <= 0:
        return None
    create: Optional[float] = None
    if create_text != "-":
        try:
            create = float(create_text)
        except ValueError:
            return None
        if not math.isfinite(create) or create <= 0:
            return None
    return SpawnTag(install, purpose, pid, create)


def _ledger_path(project_root: Optional[Path] = None) -> Path:
    """Return the machine-root, install-scoped ledger path."""
    try:
        from clio_constants import get_default_clio_root

        root = Path(get_default_clio_root())
    except Exception:
        root = Path(os.environ.get("CLIO_HOME") or Path.home() / ".clio")
        if root.parent.name == "profiles":
            root = root.parent.parent
    return root / "runtime" / "process-identity" / install_id(project_root) / LEDGER_FILENAME


def _lock_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".lock")


def _try_lock(handle: IO[bytes]) -> bool:
    if _IS_WINDOWS:
        import msvcrt

        handle.seek(0)
        locking = getattr(msvcrt, "locking", None)
        lock_mode = getattr(msvcrt, "LK_NBLCK", None)
        if not callable(locking) or lock_mode is None:
            return False
        try:
            locking(handle.fileno(), lock_mode, 1)
            return True
        except OSError:
            return False

    import fcntl

    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (BlockingIOError, OSError):
        return False


def _unlock(handle: IO[bytes]) -> None:
    if _IS_WINDOWS:
        import msvcrt

        handle.seek(0)
        locking = getattr(msvcrt, "locking", None)
        unlock_mode = getattr(msvcrt, "LK_UNLCK", None)
        if not callable(locking) or unlock_mode is None:
            raise OSError("msvcrt byte-range locking is unavailable")
        locking(handle.fileno(), unlock_mode, 1)
        return

    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def _interprocess_lock(path: Path) -> Iterator[bool]:
    """Acquire the ledger's process-safe lock, yielding whether it succeeded."""
    lock_path = _lock_path(path)
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = lock_path.open("a+b")
        try:
            os.chmod(lock_path, 0o600)
        except OSError:
            pass
        if _IS_WINDOWS:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
    except OSError:
        yield False
        return

    acquired = False
    deadline = time.monotonic() + _LOCK_TIMEOUT_SECONDS
    try:
        while not acquired:
            acquired = _try_lock(handle)
            if acquired or time.monotonic() >= deadline:
                break
            time.sleep(_LOCK_POLL_SECONDS)
        yield acquired
    finally:
        if acquired:
            try:
                _unlock(handle)
            except OSError:
                logger.debug("process identity lock release failed", exc_info=True)
        handle.close()


def _valid_optional_create(value: object) -> bool:
    return value is None or (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and float(value) > 0
    )


def _valid_ledger_entry(entry: object) -> bool:
    if not isinstance(entry, dict):
        return False
    values = cast(dict[str, object], entry)
    pid = values.get("pid")
    create = values.get("create_time")
    purpose = values.get("purpose")
    install = values.get("install")
    profile = values.get("profile")
    spawner_pid = values.get("spawner_pid")
    registered_at = values.get("registered_at")
    return (
        isinstance(pid, int)
        and not isinstance(pid, bool)
        and pid > 0
        and isinstance(create, (int, float))
        and not isinstance(create, bool)
        and math.isfinite(float(create))
        and float(create) > 0
        and isinstance(purpose, str)
        and bool(_PURPOSE_RE.fullmatch(purpose))
        and isinstance(install, str)
        and bool(re.fullmatch(r"[0-9a-f]{12}", install))
        and isinstance(profile, str)
        and bool(re.fullmatch(r"[0-9a-f]{12}", profile))
        and (
            spawner_pid is None
            or (
                isinstance(spawner_pid, int)
                and not isinstance(spawner_pid, bool)
                and spawner_pid > 0
            )
        )
        and _valid_optional_create(values.get("spawner_create"))
        and isinstance(registered_at, (int, float))
        and not isinstance(registered_at, bool)
        and math.isfinite(float(registered_at))
        and float(registered_at) > 0
        and isinstance(values.get("argv"), str)
    )


def _read_ledger(path: Path) -> Optional[list[dict]]:
    """Return entries, ``[]`` when absent, or ``None`` for corruption."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except (OSError, UnicodeError):
        return None
    # An existing zero-byte file is evidence of a truncated write, not an
    # authoritative empty roster. Quarantine it like every corrupt shape.
    if not text.strip():
        return None
    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(parsed, list) or not all(_valid_ledger_entry(e) for e in parsed):
        return None
    return parsed


def _quarantine_ledger(path: Path) -> Optional[Path]:
    """Atomically park a corrupt ledger without overwriting older evidence."""
    stamp = f"{int(time.time() * 1000)}-{os.getpid()}"
    parked = path.with_name(f"{path.name}.corrupt-{stamp}")
    try:
        os.replace(path, parked)
        logger.warning("process identity ledger was unreadable; moved to %s", parked)
        return parked
    except FileNotFoundError:
        return None
    except OSError:
        logger.warning("process identity ledger could not be quarantined", exc_info=True)
        return None


def _atomic_write_ledger(path: Path, entries: list[dict]) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = -1
    tmp_name = ""
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = -1
            json.dump(entries, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(tmp_name, 0o600)
        except OSError:
            pass
        os.replace(tmp_name, path)
        return True
    except OSError:
        logger.debug("process identity ledger write failed", exc_info=True)
        return False
    finally:
        if fd >= 0:
            os.close(fd)
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
            except OSError:
                logger.debug("temporary process ledger cleanup failed", exc_info=True)


def process_identity_matches(
    pid: int,
    create_time: object,
    *,
    tolerance: float = _CREATE_TIME_TOLERANCE,
) -> Optional[bool]:
    """Validate ``pid + create_time``; return ``None`` when it is unprovable."""
    if (
        not isinstance(pid, int)
        or isinstance(pid, bool)
        or pid <= 0
        or not isinstance(create_time, (int, float))
        or isinstance(create_time, bool)
        or not math.isfinite(float(create_time))
        or float(create_time) <= 0
        or not isinstance(tolerance, (int, float))
        or isinstance(tolerance, bool)
        or not math.isfinite(float(tolerance))
        or float(tolerance) < 0
    ):
        return None
    try:
        import psutil
    except Exception:
        return None
    try:
        proc = psutil.Process(pid)
        actual = float(proc.create_time())
        if not math.isfinite(actual) or actual <= 0:
            return None
        return abs(actual - float(create_time)) <= tolerance
    except psutil.NoSuchProcess:
        return False
    except Exception:
        return None


def _parent_identity() -> tuple[Optional[int], Optional[float]]:
    """Best-effort identity of this process's actual parent."""
    try:
        import psutil

        parent = psutil.Process(os.getpid()).parent()
        if parent is None or int(parent.pid) <= 0:
            return None, None
        create = float(parent.create_time())
        if not math.isfinite(create) or create <= 0:
            return None, None
        return int(parent.pid), create
    except Exception:
        return None, None


def register_self(purpose: str, *, project_root: Optional[Path] = None) -> bool:
    """Register this long-lived process with complete, positive identity."""
    if not _PURPOSE_RE.fullmatch(purpose):
        return False
    own_create = _own_create_time()
    if own_create is None:
        return False

    own_install = install_id(project_root)
    tag = parse_spawn_tag(os.environ.get(SPAWN_ENV_VAR))
    if tag is not None and tag.purpose == purpose and tag.install == own_install:
        spawner_pid = tag.spawner_pid
        spawner_create = tag.spawner_create
    else:
        spawner_pid, spawner_create = _parent_identity()

    entry = LedgerEntry(
        pid=os.getpid(),
        create_time=own_create,
        purpose=purpose,
        install=own_install,
        profile=profile_id(),
        spawner_pid=spawner_pid,
        spawner_create=spawner_create,
        registered_at=time.time(),
        argv=" ".join(os.fsdecode(arg) for arg in __import__("sys").argv[:8])[:1024],
    )

    path = _ledger_path(project_root)
    with _LEDGER_THREAD_LOCK, _interprocess_lock(path) as locked:
        if not locked:
            return False
        entries = _read_ledger(path)
        if entries is None:
            if _quarantine_ledger(path) is None and path.exists():
                # Never overwrite an unreadable roster we could not preserve.
                return False
            entries = []
        retained: list[dict] = []
        for existing in entries:
            pid = existing["pid"]
            if pid == entry.pid:
                continue
            alive = process_identity_matches(pid, existing["create_time"])
            if alive is False:
                continue
            # Unknown entries are retained, never silently erased.
            retained.append(existing)
        retained.append(asdict(entry))
        written = _atomic_write_ledger(path, retained)
    if written and _IS_WINDOWS:
        # Best effort: the positive ledger remains useful even when an older
        # Windows build or restrictive policy refuses Job Object attachment.
        attach_self_to_kill_on_close_job()
    return written


def ledger_entries(*, project_root: Optional[Path] = None) -> list[dict]:
    """Return live, fully validated entries for this source installation.

    Corrupt, un-lockable, stale, PID-reused, or access-denied entries produce
    no authority to act.  In particular, ``None`` from process validation is
    excluded rather than treated as alive.
    """
    wanted = install_id(project_root)
    path = _ledger_path(project_root)
    with _LEDGER_THREAD_LOCK, _interprocess_lock(path) as locked:
        if not locked:
            return []
        entries = _read_ledger(path)
        if entries is None:
            _quarantine_ledger(path)
            return []
    return [
        entry
        for entry in entries
        if entry["install"] == wanted
        and process_identity_matches(entry["pid"], entry["create_time"]) is True
    ]


def spawner_is_dead(entry: dict) -> Optional[bool]:
    """Return True/False only when the recorded spawner identity proves it."""
    pid = entry.get("spawner_pid")
    create = entry.get("spawner_create")
    if not isinstance(pid, int) or pid <= 0 or create is None:
        return None
    alive = process_identity_matches(pid, create, tolerance=_SPAWNER_TIME_TOLERANCE)
    return None if alive is None else not alive


def classify_update_holders(
    holders: list[tuple[int, float]],
    *,
    project_root: Optional[Path] = None,
) -> list[HolderClassification]:
    """Classify install-shim holders using only positive ledger identity.

    A holder is reapable only when its PID/create-time pair matches exactly one
    entry for this install, its purpose is a backend purpose, and its recorded
    spawner is positively proved dead. REPLs, scripts, unknown entries, and
    backends with a live or incomplete spawner identity remain blockers.

    Probe failures are deliberately different from an ordinary unknown
    classification: callers must abort rather than treating access denied, a
    corrupt ledger, or an unavailable create-time probe as absence.
    """
    wanted = install_id(project_root)
    path = _ledger_path(project_root)
    with _LEDGER_THREAD_LOCK, _interprocess_lock(path) as locked:
        if not locked:
            raise ProcessIdentityProbeError("could not lock the process identity ledger")
        entries = _read_ledger(path)
        if entries is None:
            raise ProcessIdentityProbeError("process identity ledger is unreadable")

    classified: list[HolderClassification] = []
    for pid, create_time in holders:
        if (
            not isinstance(pid, int)
            or isinstance(pid, bool)
            or pid <= 0
            or not isinstance(create_time, (int, float))
            or isinstance(create_time, bool)
            or not math.isfinite(float(create_time))
            or float(create_time) <= 0
        ):
            raise ProcessIdentityProbeError("holder PID/create time is invalid")

        alive = process_identity_matches(pid, create_time)
        if alive is None:
            raise ProcessIdentityProbeError(f"could not revalidate holder PID {pid}")
        if alive is False:
            classified.append(
                HolderClassification(pid, float(create_time), None, False, "holder exited")
            )
            continue

        matches = [
            entry
            for entry in entries
            if entry["install"] == wanted
            and entry["pid"] == pid
            and abs(float(entry["create_time"]) - float(create_time))
            <= _CREATE_TIME_TOLERANCE
        ]
        if len(matches) != 1:
            reason = "no matching ledger identity" if not matches else "ambiguous ledger identity"
            classified.append(
                HolderClassification(pid, float(create_time), None, False, reason)
            )
            continue

        entry = matches[0]
        purpose = str(entry["purpose"])
        if purpose not in REAPABLE_PURPOSES:
            classified.append(
                HolderClassification(
                    pid,
                    float(create_time),
                    purpose,
                    False,
                    "interactive or non-backend purpose",
                )
            )
            continue

        spawner_pid = entry.get("spawner_pid")
        spawner_create = entry.get("spawner_create")
        if not isinstance(spawner_pid, int) or spawner_pid <= 0 or spawner_create is None:
            classified.append(
                HolderClassification(
                    pid,
                    float(create_time),
                    purpose,
                    False,
                    "missing spawner identity",
                )
            )
            continue
        spawner_alive = process_identity_matches(
            spawner_pid,
            spawner_create,
            tolerance=_SPAWNER_TIME_TOLERANCE,
        )
        if spawner_alive is None:
            raise ProcessIdentityProbeError(
                f"could not revalidate spawner for holder PID {pid}"
            )
        classified.append(
            HolderClassification(
                pid,
                float(create_time),
                purpose,
                not spawner_alive,
                "spawner is dead" if not spawner_alive else "spawner is alive",
            )
        )
    return classified


def attach_self_to_kill_on_close_job() -> bool:
    """Attach this process to a Windows ``KILL_ON_JOB_CLOSE`` job object.

    Best-effort and idempotent.  ``BREAKAWAY_OK`` preserves explicit detached
    relaunch paths, while ordinary children remain in the job and die with it.
    """
    global _JOB_HANDLE
    if not _IS_WINDOWS:
        return False
    with _JOB_LOCK:
        if _JOB_HANDLE is not None:
            return True
        try:
            import ctypes
            from ctypes import wintypes

            win_dll = cast(Any, getattr(ctypes, "WinDLL", None))
            if win_dll is None:
                return False
            kernel32 = win_dll("kernel32", use_last_error=True)
            handle_type = wintypes.HANDLE
            kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
            kernel32.CreateJobObjectW.restype = handle_type
            kernel32.SetInformationJobObject.argtypes = [
                handle_type,
                ctypes.c_int,
                ctypes.c_void_p,
                wintypes.DWORD,
            ]
            kernel32.SetInformationJobObject.restype = wintypes.BOOL
            kernel32.AssignProcessToJobObject.argtypes = [handle_type, handle_type]
            kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
            kernel32.GetCurrentProcess.restype = handle_type
            kernel32.CloseHandle.argtypes = [handle_type]
            kernel32.CloseHandle.restype = wintypes.BOOL

            class IO_COUNTERS(ctypes.Structure):
                _fields_ = [
                    (name, ctypes.c_ulonglong)
                    for name in (
                        "ReadOperationCount",
                        "WriteOperationCount",
                        "OtherOperationCount",
                        "ReadTransferCount",
                        "WriteTransferCount",
                        "OtherTransferCount",
                    )
                ]

            class BASIC_LIMITS(ctypes.Structure):
                _fields_ = [
                    ("PerProcessUserTimeLimit", ctypes.c_longlong),
                    ("PerJobUserTimeLimit", ctypes.c_longlong),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD),
                ]

            class EXTENDED_LIMITS(ctypes.Structure):
                _fields_ = [
                    ("BasicLimitInformation", BASIC_LIMITS),
                    ("IoInfo", IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t),
                ]

            JOB_OBJECT_LIMIT_BREAKAWAY_OK = 0x0800
            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
            JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9

            job = kernel32.CreateJobObjectW(None, None)
            if not job:
                return False
            info = EXTENDED_LIMITS()
            info.BasicLimitInformation.LimitFlags = (
                JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_BREAKAWAY_OK
            )
            if not kernel32.SetInformationJobObject(
                job,
                JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                ctypes.byref(info),
                ctypes.sizeof(info),
            ):
                kernel32.CloseHandle(job)
                return False
            if not kernel32.AssignProcessToJobObject(job, kernel32.GetCurrentProcess()):
                kernel32.CloseHandle(job)
                return False
            _JOB_HANDLE = job
            return True
        except Exception:
            logger.debug("Windows kill-on-close job attachment failed", exc_info=True)
            return False
