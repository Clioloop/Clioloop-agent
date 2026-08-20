"""Authenticated desktop RPC helpers for backend-local browsing and updates.

The Electron renderer reaches these helpers through the already-authenticated
``/api/ws`` TUI gateway.  Paths are resolved and read on the gateway host, never
on the Electron host.  Every request carries a canonical connection/profile
route and directory reads additionally require a short-lived browse grant that
was minted by ``project.discover`` for that exact route and root.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import os
import re
import secrets
import subprocess
import sys
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Optional
from urllib.parse import quote

_ROUTE_CONNECTION_MAX = 512
_ROUTE_PROFILE_MAX = 64
_ROOTS_MAX = 64
_PATH_MAX = 16_384
_GRANT_TTL_SECONDS = 15 * 60
_GRANT_LIMIT = 512
_UPDATE_OPERATION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class RouteScopeError(ValueError):
    """The caller supplied an unknown, mismatched, or unavailable route."""


@dataclass(frozen=True)
class RouteScope:
    connection_id: str
    profile: str
    route_key: str
    profile_home: Path


def _route_component(value: str) -> str:
    # Matches JavaScript encodeURIComponent (not urllib.quote's default '/' safe
    # set), which is the canonical route encoder used by Desktop.
    return quote(value, safe="-_.!~*'()")


def canonical_route_key(connection_id: str, profile: str) -> str:
    """Return Desktop's canonical key for one connection/profile backend."""
    return (
        profile
        if connection_id == "local"
        else f"connection:{_route_component(connection_id)}::profile:{_route_component(profile)}"
    )


def _resolve_profile_home(profile: str, launch_home: Path) -> Path:
    from clio_cli import profiles as profiles_mod

    try:
        canonical = profiles_mod.normalize_profile_name(profile)
        profiles_mod.validate_profile_name(canonical)
    except (TypeError, ValueError) as exc:
        raise RouteScopeError(f"unknown profile: {profile}") from exc

    # A custom CLIO_HOME is the launch backend's default route even though it
    # cannot be represented by a named profile directory.
    try:
        launch_profile = profiles_mod.get_active_profile_name()
    except Exception:
        launch_profile = "default"

    # A gateway process is launched with one CLIO_HOME. Desktop opens the
    # owning socket for each profile, so this RPC must never use a caller-
    # provided profile name to hop sideways into another profile's data.
    # Custom/Docker homes are represented as ``default`` on the Desktop wire.
    if canonical != launch_profile and not (
        launch_profile == "custom" and canonical == "default"
    ):
        raise RouteScopeError("requested profile is not served by this gateway")
    return launch_home.resolve()


def validate_route_scope(
    params: Mapping[str, Any],
    *,
    launch_home: Path,
    transport: object | None = None,
) -> RouteScope:
    """Validate and bind a Desktop backend route, failing closed on mismatch."""
    connection_id = str(params.get("connection_id") or "").strip()
    profile = str(params.get("profile") or "").strip()
    route_key = str(params.get("route_key") or "").strip()

    if not connection_id or len(connection_id) > _ROUTE_CONNECTION_MAX:
        raise RouteScopeError("connection_id is required")
    if not profile or len(profile) > _ROUTE_PROFILE_MAX:
        raise RouteScopeError("profile is required")
    if not route_key or route_key != canonical_route_key(connection_id, profile):
        raise RouteScopeError("unknown or mismatched backend route")

    home = _resolve_profile_home(profile, Path(launch_home))

    # One authenticated WS is pinned to one exact route on first use. A later
    # attempt to reinterpret it as another connection or profile fails closed.
    bind_route = getattr(transport, "bind_backend_route", None)
    if callable(bind_route) and not bool(bind_route(route_key)):
        raise RouteScopeError("authenticated gateway route changed")

    return RouteScope(
        connection_id=connection_id,
        profile=profile,
        route_key=route_key,
        profile_home=home,
    )


@dataclass(frozen=True)
class BrowseGrant:
    expires_at: float
    root: Path
    route_key: str


class BrowseGrantRegistry:
    """Bounded, expiring grants for route-scoped backend directory reads."""

    def __init__(
        self,
        *,
        ttl_seconds: float = _GRANT_TTL_SECONDS,
        limit: int = _GRANT_LIMIT,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl_seconds = max(1.0, float(ttl_seconds))
        self._limit = max(1, int(limit))
        self._now = now
        self._lock = threading.Lock()
        self._grants: OrderedDict[str, BrowseGrant] = OrderedDict()

    def issue(self, scope: RouteScope, root: Path) -> str:
        resolved = Path(root).resolve(strict=True)
        if not resolved.is_dir():
            raise RouteScopeError(f"project root is not a directory: {root}")
        token = secrets.token_urlsafe(24)
        with self._lock:
            self._prune_locked()
            self._grants[token] = BrowseGrant(
                expires_at=self._now() + self._ttl_seconds,
                root=resolved,
                route_key=scope.route_key,
            )
            while len(self._grants) > self._limit:
                self._grants.popitem(last=False)
        return token

    def resolve(self, scope: RouteScope, token: str, requested: str) -> tuple[Path, Path]:
        raw_token = str(token or "").strip()
        raw_path = str(requested or "").strip()
        if not raw_token or not raw_path or len(raw_path) > _PATH_MAX:
            raise RouteScopeError("browse_token and path are required")

        with self._lock:
            self._prune_locked()
            grant = self._grants.get(raw_token)
            if grant is None or grant.route_key != scope.route_key:
                raise RouteScopeError("unknown or expired project browse grant")
            self._grants.move_to_end(raw_token)

        try:
            candidate = Path(os.path.expanduser(raw_path)).resolve(strict=True)
            common = Path(os.path.commonpath((str(grant.root), str(candidate))))
        except (OSError, RuntimeError, ValueError) as exc:
            raise RouteScopeError("project path is unavailable") from exc
        if common != grant.root:
            raise RouteScopeError("project path escapes the granted root")
        if not candidate.is_dir():
            raise RouteScopeError("project path is not a directory")
        return grant.root, candidate

    def clear(self) -> None:
        with self._lock:
            self._grants.clear()

    def _prune_locked(self) -> None:
        now = self._now()
        expired = [token for token, grant in self._grants.items() if grant.expires_at <= now]
        for token in expired:
            self._grants.pop(token, None)


BROWSE_GRANTS = BrowseGrantRegistry()


def _normalized_existing_roots(roots: object) -> list[Path]:
    if roots is None:
        return []
    if not isinstance(roots, list) or len(roots) > _ROOTS_MAX:
        raise RouteScopeError(f"roots must be a list with at most {_ROOTS_MAX} entries")

    normalized: list[Path] = []
    seen: set[str] = set()
    for value in roots:
        if not isinstance(value, str) or not value.strip() or len(value) > _PATH_MAX:
            raise RouteScopeError("every project root must be a non-empty path")
        try:
            path = Path(os.path.expanduser(value.strip())).resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise RouteScopeError(f"project root is unavailable: {value}") from exc
        if not path.is_dir():
            raise RouteScopeError(f"project root is not a directory: {value}")
        key = os.path.normcase(str(path))
        if key not in seen:
            seen.add(key)
            normalized.append(path)
    return normalized


def _registered_project_roots(scope: RouteScope) -> list[tuple[str, str, Path]]:
    db_path = scope.profile_home / "projects.db"
    if not db_path.is_file():
        return []

    from clio_projects import ProjectsDB

    database = ProjectsDB(db_path)
    try:
        rows = database.list_projects()
    finally:
        database.close()

    result: list[tuple[str, str, Path]] = []
    for project in rows:
        project_id = str(project.get("id") or "").strip()
        project_name = str(project.get("name") or "").strip()
        for workspace in project.get("workspaces") or []:
            raw = str(workspace.get("path") or "").strip()
            if not raw:
                continue
            try:
                root = Path(os.path.expanduser(raw)).resolve(strict=True)
            except (OSError, RuntimeError):
                continue
            if root.is_dir():
                result.append((project_id, project_name or root.name or str(root), root))
    return result


def discover_projects(scope: RouteScope, roots: object) -> dict[str, Any]:
    """Discover configured + explicitly focused project roots on this backend."""
    candidates = _registered_project_roots(scope)
    candidates.extend(("", root.name or str(root), root) for root in _normalized_existing_roots(roots))

    projects: list[dict[str, Any]] = []
    seen: set[str] = set()
    for registered_id, name, root in candidates:
        root_key = os.path.normcase(str(root))
        if root_key in seen:
            continue
        seen.add(root_key)
        digest = hashlib.sha256(f"{scope.route_key}\0{root}".encode("utf-8")).hexdigest()[:16]
        projects.append(
            {
                "id": registered_id or f"path:{digest}",
                "name": name,
                "path": str(root),
                "browse_token": BROWSE_GRANTS.issue(scope, root),
            }
        )

    projects.sort(key=lambda item: (str(item["name"]).casefold(), str(item["path"])))
    return {
        "connection_id": scope.connection_id,
        "profile": scope.profile,
        "route_key": scope.route_key,
        "projects": projects,
    }


def read_project_tree(
    scope: RouteScope,
    *,
    browse_token: str,
    path: str,
    limit: int = 2_000,
) -> dict[str, Any]:
    """List one granted backend directory without following symlink escapes."""
    root, directory = BROWSE_GRANTS.resolve(scope, browse_token, path)
    bounded_limit = max(1, min(int(limit or 2_000), 2_000))
    entries: list[dict[str, Any]] = []
    truncated = False

    try:
        with os.scandir(directory) as scan:
            for index, entry in enumerate(scan):
                if index >= bounded_limit:
                    truncated = True
                    break
                try:
                    is_directory = entry.is_dir(follow_symlinks=False)
                except OSError:
                    is_directory = False
                entries.append(
                    {
                        "name": entry.name,
                        "path": str(directory / entry.name),
                        "isDirectory": is_directory,
                    }
                )
    except OSError as exc:
        return {
            "connection_id": scope.connection_id,
            "profile": scope.profile,
            "route_key": scope.route_key,
            "root": str(root),
            "path": str(directory),
            "entries": [],
            "error": exc.__class__.__name__,
            "truncated": False,
        }

    entries.sort(key=lambda item: (not bool(item["isDirectory"]), str(item["name"]).casefold()))
    return {
        "connection_id": scope.connection_id,
        "profile": scope.profile,
        "route_key": scope.route_key,
        "root": str(root),
        "path": str(directory),
        "entries": entries,
        "truncated": truncated,
    }


class UpdateCoordinator:
    """Idempotent, bounded cache for potentially concurrent update requests."""

    def __init__(self, *, limit: int = 64) -> None:
        self._limit = max(1, int(limit))
        self._lock = threading.Lock()
        self._runs: OrderedDict[str, concurrent.futures.Future[dict[str, Any]]] = OrderedDict()

    def run(self, key: str, work: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        operation = str(key or "").strip()
        if not _UPDATE_OPERATION_RE.fullmatch(operation):
            raise RouteScopeError("operation_id is required and must be a safe identifier")

        owner = False
        with self._lock:
            future = self._runs.get(operation)
            if future is None:
                # Keep the cache truly bounded. Prefer evicting the oldest
                # completed result; if every slot is active, reject new work
                # rather than growing without limit behind a hung operation.
                while len(self._runs) >= self._limit:
                    completed_key = next(
                        (run_key for run_key, run in self._runs.items() if run.done()),
                        None,
                    )
                    if completed_key is None:
                        raise RouteScopeError("too many update operations in progress")
                    self._runs.pop(completed_key, None)
                future = concurrent.futures.Future()
                self._runs[operation] = future
                owner = True
            else:
                self._runs.move_to_end(operation)

        if owner:
            try:
                result = work()
                if not isinstance(result, dict):
                    result = {"ok": False, "error": "update-not-confirmed"}
            except Exception as exc:  # turn execution failures into explicit target failures
                result = {"ok": False, "error": "update-failed", "message": str(exc)}
            future.set_result(result)

        return future.result()

    def clear(self) -> None:
        with self._lock:
            self._runs.clear()


UPDATE_COORDINATOR = UpdateCoordinator()


def update_operation_key(scope: RouteScope, operation_id: str) -> str:
    """Validate a client operation id and bind it to the exact backend route."""
    operation = str(operation_id or "").strip()
    if not _UPDATE_OPERATION_RE.fullmatch(operation):
        raise RouteScopeError("operation_id is required and must be a safe identifier")
    digest = hashlib.sha256(f"{scope.route_key}\0{operation}".encode("utf-8")).hexdigest()
    return f"update:{digest}"


def perform_backend_update(
    scope: RouteScope,
    *,
    branch: Optional[str] = None,
    timeout: int = 900,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    """Apply one backend update and return only confirmed/manual/failure states."""
    from clio_cli.config import detect_install_method, recommended_update_command_for_method

    install_method = detect_install_method(Path(__file__).resolve().parents[1])
    command = recommended_update_command_for_method(install_method)
    if install_method not in {"git", "pip"}:
        return {
            "ok": False,
            "manual": True,
            "command": command,
            "message": f"Update {scope.connection_id} manually: {command}",
        }

    argv = [sys.executable, "-m", "clio_cli.main", "update", "--yes", "--keep-stash"]
    if branch:
        normalized_branch = str(branch).strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}", normalized_branch):
            raise RouteScopeError("invalid update branch")
        argv.extend(["--branch", normalized_branch])

    env = os.environ.copy()
    # The updater's dashboard reaper must spare the process serving this RPC;
    # the Desktop will reconnect/restart it after receiving the confirmed result.
    env["CLIO_DESKTOP_CHILD_PID"] = str(os.getpid())
    completed = runner(
        argv,
        capture_output=True,
        text=True,
        timeout=max(30, min(int(timeout), 1_800)),
        cwd=str(Path(__file__).resolve().parents[1]),
        env=env,
    )
    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
    detail = output[-4_000:] if output else "Update command completed without output."
    if completed.returncode != 0:
        return {"ok": False, "error": "update-failed", "message": detail}
    return {"ok": True, "message": detail}
