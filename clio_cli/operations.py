"""Read-only operational health and storage diagnostics for Clio.

All probes are bounded and local: no service restart, config write, exporter, or
remote request is performed.  The resulting dictionaries are suitable for the
monitoring CLI and redacted support bundles.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from clio_cli.observability import (
    event,
    exporter_configured,
    log as observation_log,
    metric,
    redact,
)

_WARN_DISK_PERCENT = 90.0
_WARN_MEMORY_PERCENT = 90.0
_WARN_WAL_BYTES = 256 * 1024 * 1024
_WARN_DB_BYTES = 2 * 1024 * 1024 * 1024


def _home(path: Path | str | None = None) -> Path:
    return Path(path or os.getenv("CLIO_HOME", "~/.clio")).expanduser()


def _iso_mtime(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z")
    except OSError:
        return None


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def discover_databases(clio_home: Path | str | None = None, *, limit: int = 100) -> list[Path]:
    root = _home(clio_home)
    if not root.exists():
        return []
    found: list[Path] = []
    try:
        for pattern in ("*.db", "*.sqlite", "*.sqlite3"):
            found.extend(root.rglob(pattern))
    except OSError:
        pass
    unique = {p.resolve(strict=False): p for p in found if p.is_file()}
    return sorted(unique.values(), key=lambda p: str(p))[: max(1, limit)]


def diagnose_database(path: Path | str, *, root: Path | str | None = None) -> dict[str, Any]:
    """Inspect SQLite/WAL/FTS/read-lock/growth signals via a read-only handle."""
    db = Path(path)
    base = _home(root) if root is not None else db.parent
    try:
        label = str(db.resolve(strict=False).relative_to(base.resolve(strict=False)))
    except ValueError:
        label = db.name
    result: dict[str, Any] = {
        "path": label,
        "bytes": _safe_size(db),
        "wal_bytes": _safe_size(Path(str(db) + "-wal")),
        "shm_bytes": _safe_size(Path(str(db) + "-shm")),
        "modified_at": _iso_mtime(db),
        "status": "ok",
        "readable": False,
        "lock_state": "unknown",
        "quick_check": None,
        "journal_mode": None,
        "page_count": None,
        "page_size": None,
        "freelist_count": None,
        "allocated_bytes": None,
        "free_bytes_estimate": None,
        "free_ratio_percent": None,
        "wal_to_db_ratio": None,
        "growth_signals": [],
        "fts_tables": [],
    }
    if not db.exists():
        result.update(status="error", error="database missing")
        return result
    conn: sqlite3.Connection | None = None
    try:
        uri = f"file:{db.resolve().as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=0.1)
        conn.execute("PRAGMA busy_timeout=100")
        result["readable"] = True
        result["lock_state"] = "readable"
        row = conn.execute("PRAGMA quick_check(1)").fetchone()
        result["quick_check"] = str(row[0]) if row else "no result"
        result["journal_mode"] = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
        result["page_count"] = int(conn.execute("PRAGMA page_count").fetchone()[0])
        result["page_size"] = int(conn.execute("PRAGMA page_size").fetchone()[0])
        result["freelist_count"] = int(conn.execute("PRAGMA freelist_count").fetchone()[0])
        result["allocated_bytes"] = result["page_count"] * result["page_size"]
        result["free_bytes_estimate"] = result["freelist_count"] * result["page_size"]
        result["free_ratio_percent"] = round(
            (result["freelist_count"] / result["page_count"]) * 100, 2
        ) if result["page_count"] else 0.0
        result["wal_to_db_ratio"] = round(
            result["wal_bytes"] / max(result["bytes"], 1), 3
        )
        fts = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND lower(COALESCE(sql,'')) LIKE '%virtual table%using fts%' ORDER BY name"
        ).fetchall()
        result["fts_tables"] = [str(row[0]) for row in fts]
        if result["quick_check"] != "ok":
            result["status"] = "error"
    except sqlite3.OperationalError as exc:
        text = str(exc).lower()
        result["lock_state"] = "busy" if "locked" in text or "busy" in text else "unreadable"
        result["status"] = "error"
        result["error"] = str(exc)[:300]
    except (OSError, sqlite3.DatabaseError) as exc:
        result["status"] = "error"
        result["error"] = str(exc)[:300]
    finally:
        if conn is not None:
            conn.close()
    if result["wal_bytes"] >= _WARN_WAL_BYTES:
        result["growth_signals"].append("large_wal")
        if result["status"] == "ok":
            result["status"] = "warning"
            result["warning"] = "large WAL; checkpoint health should be reviewed"
    if result["bytes"] >= _WARN_DB_BYTES:
        result["growth_signals"].append("large_database")
        if result["status"] == "ok":
            result["status"] = "warning"
            result["warning"] = "large database; review retention and growth"
    if (result.get("free_ratio_percent") or 0) >= 30:
        result["growth_signals"].append("high_freelist_ratio")
    return result


def database_diagnostics(clio_home: Path | str | None = None) -> dict[str, Any]:
    root = _home(clio_home)
    databases = [diagnose_database(path, root=root) for path in discover_databases(root)]
    total = sum(int(item["bytes"]) + int(item["wal_bytes"]) + int(item["shm_bytes"]) for item in databases)
    return {
        "root": str(root),
        "count": len(databases),
        "total_bytes": total,
        "warning_count": sum(item["status"] == "warning" for item in databases),
        "error_count": sum(item["status"] == "error" for item in databases),
        "databases": databases,
        "largest": sorted(
            ({"path": d["path"], "bytes": d["bytes"] + d["wal_bytes"] + d["shm_bytes"]} for d in databases),
            key=lambda item: item["bytes"], reverse=True,
        )[:10],
    }


def memory_pressure() -> dict[str, Any]:
    result: dict[str, Any] = {"status": "unknown", "total_bytes": None, "available_bytes": None, "used_percent": None}
    try:
        values: dict[str, int] = {}
        with Path("/proc/meminfo").open(encoding="ascii") as handle:
            for line in handle:
                key, _, raw = line.partition(":")
                if key in {"MemTotal", "MemAvailable"}:
                    values[key] = int(raw.strip().split()[0]) * 1024
        total, available = values["MemTotal"], values["MemAvailable"]
        used = round((1.0 - available / total) * 100, 2) if total else 0.0
        result.update(total_bytes=total, available_bytes=available, used_percent=used,
                      status="warning" if used >= _WARN_MEMORY_PERCENT else "ok")
        return result
    except (OSError, KeyError, ValueError, ZeroDivisionError):
        pass
    try:
        import psutil  # type: ignore[import-not-found]
        vm = psutil.virtual_memory()
        result.update(total_bytes=int(vm.total), available_bytes=int(vm.available), used_percent=round(float(vm.percent), 2),
                      status="warning" if float(vm.percent) >= _WARN_MEMORY_PERCENT else "ok")
    except Exception:
        result["detail"] = "memory availability probe unsupported"
    return result


def disk_pressure(path: Path | str | None = None) -> dict[str, Any]:
    target = _home(path)
    try:
        probe = target if target.exists() else target.parent
        usage = shutil.disk_usage(probe)
        used = round((usage.used / usage.total) * 100, 2) if usage.total else 0.0
        status = "critical" if usage.free < 256 * 1024 * 1024 else ("warning" if used >= _WARN_DISK_PERCENT else "ok")
        return {"status": status, "path": str(probe), "total_bytes": usage.total, "used_bytes": usage.used,
                "free_bytes": usage.free, "used_percent": used}
    except OSError as exc:
        return {"status": "unknown", "path": str(target), "error": str(exc)[:300]}


def resource_limits() -> dict[str, Any]:
    result: dict[str, Any] = {"supported": False, "limits": {}}
    try:
        import resource
        names = ("RLIMIT_NOFILE", "RLIMIT_NPROC", "RLIMIT_AS", "RLIMIT_CORE", "RLIMIT_STACK")
        limits: dict[str, Any] = {}
        for name in names:
            key = getattr(resource, name, None)
            if key is None:
                continue
            soft, hard = resource.getrlimit(key)
            infinity = resource.RLIM_INFINITY
            limits[name.removeprefix("RLIMIT_").lower()] = {
                "soft": "unlimited" if soft == infinity else soft,
                "hard": "unlimited" if hard == infinity else hard,
            }
        result.update(supported=True, limits=limits)
    except (ImportError, OSError, ValueError):
        result["detail"] = "resource limits unavailable on this platform"
    return result


def log_health(clio_home: Path | str | None = None) -> dict[str, Any]:
    root = _home(clio_home) / "logs"
    logs: list[dict[str, Any]] = []
    try:
        paths: Iterable[Path] = root.glob("*.log") if root.exists() else ()
        for path in sorted(paths, key=lambda p: p.name)[:50]:
            logs.append({"name": path.name, "bytes": _safe_size(path), "modified_at": _iso_mtime(path)})
    except OSError:
        pass
    total = sum(item["bytes"] for item in logs)
    return {"count": len(logs), "total_bytes": total, "largest": sorted(logs, key=lambda x: x["bytes"], reverse=True)[:10]}


def process_health(clio_home: Path | str | None = None) -> dict[str, Any]:
    root = _home(clio_home)
    pid_files: list[dict[str, Any]] = []
    try:
        candidates = list(root.rglob("*.pid"))[:50] if root.exists() else []
    except OSError:
        candidates = []
    for path in candidates:
        try:
            pid = int(path.read_text(encoding="ascii").strip())
            alive = pid > 0 and (Path(f"/proc/{pid}").exists() if sys.platform.startswith("linux") else _pid_alive(pid))
            pid_files.append({"name": path.name, "pid": pid, "alive": alive})
        except (OSError, ValueError):
            pid_files.append({"name": path.name, "pid": None, "alive": False})
    return {"pid": os.getpid(), "pid_files": pid_files, "stale_pid_files": sum(not item["alive"] for item in pid_files)}


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


def collect_health(clio_home: Path | str | None = None, *, live: bool = False) -> dict[str, Any]:
    """Collect a stable, JSON-serializable health snapshot."""
    root = _home(clio_home)
    started = time.monotonic()
    storage = database_diagnostics(root)
    memory = memory_pressure()
    disk = disk_pressure(root)
    data: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mode": "live" if live else "snapshot",
        "system": {"platform": platform.system(), "release": platform.release(), "python": platform.python_version(), "pid": os.getpid()},
        "memory": memory,
        "disk": disk,
        "resources": resource_limits(),
        "storage": storage,
        "logs": log_health(root),
        "observability": {
            "enabled": os.getenv("CLIO_OBSERVABILITY_ENABLED", "").lower() in {"1", "true", "yes", "on"},
            "mode": "explicit-exporter" if exporter_configured() else "local-only",
        },
    }
    if live:
        data["processes"] = process_health(root)
    data["duration_ms"] = round((time.monotonic() - started) * 1000, 2)
    statuses = [str(memory.get("status")), str(disk.get("status"))]
    if storage["error_count"]:
        statuses.append("error")
    elif storage["warning_count"]:
        statuses.append("warning")
    data["status"] = "error" if "error" in statuses or "critical" in statuses else ("warning" if "warning" in statuses else "ok")
    # Health metric/log export uses the same disabled-by-default local API.
    metric("clio.health.disk.used", float(disk.get("used_percent") or 0), unit="percent")
    metric("clio.health.memory.used", float(memory.get("used_percent") or 0), unit="percent")
    metric("clio.health.storage.bytes", float(storage["total_bytes"]), unit="By")
    event("clio.health.snapshot", severity="warning" if data["status"] != "ok" else "info",
          attributes={"status": data["status"], "live": live, "database_count": storage["count"]})
    observation_log(
        "clio.health.log",
        f"status={data['status']} databases={storage['count']} storage_bytes={storage['total_bytes']}",
        severity="warning" if data["status"] != "ok" else "info",
    )
    return data


def support_bundle_data(clio_home: Path | str | None = None) -> dict[str, Any]:
    """Return richer, force-redacted operations data for support bundles."""
    data = collect_health(clio_home, live=True)
    # Absolute home paths disclose usernames and are unnecessary for triage.
    data["disk"]["path"] = "<CLIO_HOME>"
    data["storage"]["root"] = "<CLIO_HOME>"
    return redact(data)


def format_health(data: dict[str, Any]) -> str:
    memory, disk, storage = data["memory"], data["disk"], data["storage"]
    lines = [
        f"Clio health: {str(data['status']).upper()} ({data['mode']})",
        f"  memory: {memory.get('status')} ({memory.get('used_percent', 'n/a')}% used)",
        f"  disk: {disk.get('status')} ({disk.get('used_percent', 'n/a')}% used, {disk.get('free_bytes', 'n/a')} bytes free)",
        f"  databases: {storage['count']} ({storage['total_bytes']} bytes; {storage['warning_count']} warnings, {storage['error_count']} errors)",
        f"  logs: {data['logs']['count']} ({data['logs']['total_bytes']} bytes)",
        f"  observability: {'enabled' if data['observability']['enabled'] else 'off (default)'} / {data['observability']['mode']}",
    ]
    if data.get("processes"):
        lines.append(f"  stale pid files: {data['processes']['stale_pid_files']}")
    limits = data["resources"].get("limits", {})
    if limits:
        nofile = limits.get("nofile", {})
        lines.append(f"  open-file limit: {nofile.get('soft', 'n/a')} soft / {nofile.get('hard', 'n/a')} hard")
    return "\n".join(lines)


def run_monitor(args: argparse.Namespace) -> int:
    data = collect_health(live=bool(getattr(args, "live", False)))
    if getattr(args, "json", False):
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(format_health(data))
        if getattr(args, "databases", False):
            for db in data["storage"]["databases"]:
                print(f"  db {db['status']}: {db['path']} ({db['bytes']} bytes, WAL {db['wal_bytes']}, FTS {len(db['fts_tables'])}, lock {db['lock_state']})")
    return 1 if data["status"] == "error" else 0


__all__ = [
    "discover_databases", "diagnose_database", "database_diagnostics", "memory_pressure",
    "disk_pressure", "resource_limits", "log_health", "process_health", "collect_health",
    "support_bundle_data", "format_health", "run_monitor",
]
