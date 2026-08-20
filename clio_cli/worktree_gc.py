"""Fail-safe audit and attended reclamation for Clio worktrees.

This module backs ``clio worktree list|prune`` and ``/worktree``.  It is
intentionally conservative: an incomplete git/GitHub/kanban/liveness probe is
never evidence that a tree or branch is disposable.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import re
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

logger = logging.getLogger(__name__)

PROTECTED_BRANCHES = frozenset({"main", "master", "develop", "development", "dev", "trunk", "production"})
_MAX_PATCH_EQUIVALENCE_COMMITS = 50
_CLIO_LOCK_RE = re.compile(r"\bclio pid=(\d+)\b")
_KANBAN_TREE_RE = re.compile(r"^t_[0-9a-f]+$")


@dataclass(frozen=True)
class TreeRecord:
    name: str
    path: str
    branch: str
    head: str
    age_days: float
    size_mb: Optional[int]
    verdict: str  # prune | keep
    reason: str
    lock_state: str = "unlocked"


@dataclass(frozen=True)
class BranchRecord:
    name: str
    head: str
    verdict: str  # delete | keep
    reason: str


def _completed(
    args: Sequence[str],
    *,
    returncode: int,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(list(args), returncode, stdout, stderr)


def _git(args: Sequence[str], *, cwd: str | Path, timeout: int = 15) -> subprocess.CompletedProcess[str]:
    """Run git without a shell; all execution failures become non-zero results."""
    command = ["git", *args]
    try:
        return subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return _completed(command, returncode=124, stderr=f"timed out after {timeout}s")
    except (OSError, ValueError) as exc:
        return _completed(command, returncode=127, stderr=str(exc))


def resolve_repo_root(path: str | Path | None = None) -> Optional[str]:
    """Resolve any checkout/worktree path to its primary worktree root."""
    cwd = Path(path or os.environ.get("TERMINAL_CWD") or os.getcwd()).expanduser()
    listed = _git(["worktree", "list", "--porcelain"], cwd=cwd, timeout=10)
    if listed.returncode != 0:
        return None
    for line in listed.stdout.splitlines():
        if line.startswith("worktree "):
            candidate = line[len("worktree ") :].strip()
            try:
                return str(Path(candidate).resolve())
            except (OSError, ValueError):
                return None
    return None


def _resolved(path: str | Path) -> Optional[Path]:
    try:
        return Path(path).expanduser().resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return None


def _same_path(left: str | Path, right: str | Path) -> bool:
    left_path = _resolved(left)
    right_path = _resolved(right)
    return left_path is not None and right_path is not None and left_path == right_path


def _managed_worktrees_root(repo_root: str | Path) -> Optional[Path]:
    """Return the real, non-symlinked ``.worktrees`` root or fail closed."""
    root = Path(repo_root) / ".worktrees"
    try:
        if root.is_symlink():
            return None
        return root.resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return None


def _is_managed_worktree_path(path: str | Path, worktrees_root: Path) -> bool:
    """Only immediate children of the canonical managed directory are eligible."""
    resolved = _resolved(path)
    return resolved is not None and resolved.parent == worktrees_root


def discover_current_paths() -> set[Path]:
    """Return worktree roots currently owned by this process/session."""
    candidates: list[str] = []
    terminal_cwd = os.environ.get("TERMINAL_CWD")
    if terminal_cwd:
        candidates.append(terminal_cwd)
    try:
        candidates.append(os.getcwd())
    except OSError:
        pass

    cli_module = sys.modules.get("cli")
    active = getattr(cli_module, "_active_worktree", None) if cli_module else None
    if isinstance(active, dict) and active.get("path"):
        candidates.append(str(active["path"]))

    roots: set[Path] = set()
    for candidate in candidates:
        probe = _git(["rev-parse", "--show-toplevel"], cwd=candidate, timeout=5)
        if probe.returncode == 0 and probe.stdout.strip():
            resolved = _resolved(probe.stdout.strip())
            if resolved is not None:
                roots.add(resolved)
        else:
            resolved = _resolved(candidate)
            if resolved is not None:
                roots.add(resolved)
    return roots


def _directory_size_mb(root: Path) -> Optional[int]:
    """Portable, non-symlink-following directory size calculation."""
    total = 0
    try:
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            base = Path(dirpath)
            dirnames[:] = [name for name in dirnames if not (base / name).is_symlink()]
            for name in filenames:
                item = base / name
                try:
                    if not item.is_symlink():
                        total += item.stat().st_size
                except OSError:
                    return None
    except OSError:
        return None
    return (total + (1024 * 1024 - 1)) // (1024 * 1024)


def _repo_is_shallow(repo_root: str) -> Optional[bool]:
    result = _git(["rev-parse", "--is-shallow-repository"], cwd=repo_root, timeout=5)
    if result.returncode != 0:
        return None
    value = result.stdout.strip().lower()
    if value not in {"true", "false"}:
        return None
    return value == "true"


def _pid_is_live(pid: int) -> Optional[bool]:
    if pid == os.getpid():
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None
    return True


def _worktree_lock_state(repo_root: str, worktree_path: str) -> str:
    """Return unlocked/live/dead/foreign/unknown for one git worktree lock."""
    result = _git(["worktree", "list", "--porcelain"], cwd=repo_root, timeout=10)
    if result.returncode != 0:
        return "unknown"

    target = _resolved(worktree_path)
    current: Optional[Path] = None
    saw_target = False
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            current = _resolved(line[len("worktree ") :].strip())
            saw_target = current is not None and current == target
            continue
        if not saw_target or not (line == "locked" or line.startswith("locked ")):
            continue
        reason = line[len("locked") :].strip()
        match = _CLIO_LOCK_RE.search(reason)
        if not match:
            return "foreign"
        live = _pid_is_live(int(match.group(1)))
        if live is True:
            return "live"
        if live is False:
            return "dead"
        return "unknown"
    return "unlocked"


def _status_is_dirty(worktree_path: str) -> Optional[bool]:
    result = _git(["status", "--porcelain", "--untracked-files=all"], cwd=worktree_path, timeout=10)
    if result.returncode != 0:
        return None
    return bool(result.stdout.strip())


def _branch_and_head(worktree_path: str) -> tuple[Optional[str], Optional[str]]:
    branch = _git(["symbolic-ref", "--quiet", "--short", "HEAD"], cwd=worktree_path, timeout=5)
    head = _git(["rev-parse", "--verify", "HEAD^{commit}"], cwd=worktree_path, timeout=5)
    if branch.returncode != 0 or head.returncode != 0:
        return None, None
    branch_name = branch.stdout.strip()
    head_sha = head.stdout.strip()
    if not branch_name or not head_sha:
        return None, None
    return branch_name, head_sha


def _local_baseline_refs(worktree_path: str, current_branch: str) -> Optional[list[str]]:
    result = _git(
        ["for-each-ref", "--format=%(refname)", "refs/heads"],
        cwd=worktree_path,
        timeout=10,
    )
    if result.returncode != 0:
        return None
    current_ref = f"refs/heads/{current_branch}"
    return [line.strip() for line in result.stdout.splitlines() if line.strip() and line.strip() != current_ref]


def _has_unique_commits(worktree_path: str, branch: str) -> tuple[Optional[bool], str]:
    """Detect commits not reachable from a durable remote/local baseline."""
    remotes = _git(
        ["for-each-ref", "--format=%(refname)", "refs/remotes"],
        cwd=worktree_path,
        timeout=10,
    )
    if remotes.returncode != 0:
        return None, "could not enumerate remote refs"

    remote_refs = [line.strip() for line in remotes.stdout.splitlines() if line.strip()]
    if remote_refs:
        result = _git(["rev-list", "--count", "HEAD", "--not", "--remotes"], cwd=worktree_path, timeout=15)
    else:
        local_refs = _local_baseline_refs(worktree_path, branch)
        if local_refs is None:
            return None, "could not enumerate local baseline refs"
        if not local_refs:
            return None, "no remote or independent local baseline"
        result = _git(["rev-list", "--count", "HEAD", "--not", *local_refs], cwd=worktree_path, timeout=15)

    if result.returncode != 0:
        return None, "could not compare commit reachability"
    try:
        count = int(result.stdout.strip())
    except ValueError:
        return None, "invalid commit reachability result"
    return count > 0, f"{count} unique commit(s)"


def _default_upstream(cwd: str) -> Optional[str]:
    for candidate in ("origin/HEAD", "origin/main", "origin/master"):
        probe = _git(["rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}"], cwd=cwd, timeout=5)
        if probe.returncode == 0 and probe.stdout.strip():
            return candidate
    return None


def _patches_merged_upstream(worktree_path: str) -> tuple[Optional[bool], str]:
    upstream = _default_upstream(worktree_path)
    if upstream is None:
        return None, "no default upstream ref"
    ahead = _git(["rev-list", "--count", f"{upstream}..HEAD"], cwd=worktree_path, timeout=10)
    if ahead.returncode != 0:
        return None, "could not count commits ahead of upstream"
    try:
        count = int(ahead.stdout.strip())
    except ValueError:
        return None, "invalid upstream commit count"
    if count == 0:
        return True, f"fully merged into {upstream}"
    if count > _MAX_PATCH_EQUIVALENCE_COMMITS:
        return False, f"{count} commits ahead (comparison limit exceeded)"

    cherry = _git(["cherry", upstream, "HEAD"], cwd=worktree_path, timeout=30)
    if cherry.returncode != 0:
        return None, "git cherry failed"
    lines = [line.strip() for line in cherry.stdout.splitlines() if line.strip()]
    if lines and all(line.startswith("-") for line in lines):
        return True, f"all {len(lines)} commit(s) patch-equivalent upstream"
    return False, f"{sum(line.startswith('+') for line in lines)} commit(s) not patch-equivalent upstream"


def _merged_pr_state(worktree_path: str, branch: str, head: str, timeout: int = 15) -> Optional[bool]:
    """Return PR merged state; ``None`` means the probe failed and must KEEP."""
    command = [
        "gh",
        "pr",
        "list",
        "--head",
        branch,
        "--state",
        "merged",
        "--json",
        "number,headRefOid",
        "--limit",
        "20",
    ]
    try:
        result = subprocess.run(
            command,
            cwd=worktree_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout or "[]")
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, list):
        return None
    for item in payload:
        if not isinstance(item, dict) or "headRefOid" not in item:
            return None
        if item.get("headRefOid") == head:
            return True
    return False


def _kanban_owned_paths() -> set[Path]:
    """Read worktree paths referenced by every Clio kanban board, read-only."""
    paths: set[Path] = set()
    try:
        from clio_cli import kanban_db

        board_rows = kanban_db.list_boards(include_archived=True)
        slugs = [str(row.get("slug") or "default") for row in board_rows if isinstance(row, dict)]
        if "default" not in slugs:
            slugs.append("default")
        db_paths = {kanban_db.kanban_db_path(board=slug) for slug in slugs}
    except Exception:
        return paths

    for db_path in db_paths:
        if not db_path.is_file():
            continue
        try:
            uri = f"{db_path.resolve().as_uri()}?mode=ro"
            connection = sqlite3.connect(uri, uri=True, timeout=1)
            try:
                rows = connection.execute(
                    "SELECT workspace_path FROM tasks "
                    "WHERE workspace_kind = 'worktree' AND workspace_path IS NOT NULL"
                ).fetchall()
            finally:
                connection.close()
        except (OSError, sqlite3.Error, ValueError):
            continue
        for (raw_path,) in rows:
            if raw_path:
                resolved = _resolved(str(raw_path))
                if resolved is not None:
                    paths.add(resolved)
    return paths


def _audit_tree(
    repo_root: str,
    entry: Path,
    *,
    with_size: bool,
    current_paths: set[Path],
    kanban_paths: set[Path],
    shallow: Optional[bool],
) -> TreeRecord:
    try:
        age_days = max(0.0, (time.time() - entry.stat().st_mtime) / 86400.0)
    except OSError:
        age_days = 0.0
    size_mb = _directory_size_mb(entry) if with_size else None
    path = str(entry)

    def keep(reason: str, *, branch: str = "", head: str = "", lock_state: str = "unlocked") -> TreeRecord:
        return TreeRecord(entry.name, path, branch, head, age_days, size_mb, "keep", reason, lock_state)

    resolved_entry = _resolved(entry)
    if entry.is_symlink():
        return keep("symlinked worktree directory; refusing to inspect")
    if resolved_entry is None:
        return keep("could not resolve worktree path")
    if resolved_entry in current_paths:
        return keep("current/active worktree")
    if resolved_entry in kanban_paths or _KANBAN_TREE_RE.fullmatch(entry.name):
        return keep("kanban-owned worktree")
    if shallow is None:
        return keep("could not determine whether repository is shallow")
    if shallow:
        return keep("shallow repository; history safety cannot be verified")

    branch, head = _branch_and_head(path)
    if branch is None or head is None:
        return keep("detached/unreadable HEAD")
    if branch in PROTECTED_BRANCHES:
        return keep("protected branch", branch=branch, head=head)

    lock_state = _worktree_lock_state(repo_root, path)
    if lock_state in {"live", "foreign", "unknown"}:
        reasons = {
            "live": "live Clio session lock",
            "foreign": "foreign/unrecognized worktree lock",
            "unknown": "could not verify worktree lock owner",
        }
        return keep(reasons[lock_state], branch=branch, head=head, lock_state=lock_state)

    dirty = _status_is_dirty(path)
    if dirty is None:
        return keep("could not verify working-tree status", branch=branch, head=head, lock_state=lock_state)
    if dirty:
        return keep("uncommitted changes (tracked, staged, or untracked)", branch=branch, head=head, lock_state=lock_state)

    unique, unique_reason = _has_unique_commits(path, branch)
    if unique is None:
        return keep(unique_reason, branch=branch, head=head, lock_state=lock_state)
    if unique:
        merged, merged_reason = _patches_merged_upstream(path)
        if merged is None:
            return keep(merged_reason, branch=branch, head=head, lock_state=lock_state)
        if not merged:
            pr_merged = _merged_pr_state(path, branch, head)
            if pr_merged is None:
                return keep(
                    "unique commits; merged-PR probe failed/unavailable",
                    branch=branch,
                    head=head,
                    lock_state=lock_state,
                )
            if not pr_merged:
                return keep(
                    f"{unique_reason}; no matching merged PR",
                    branch=branch,
                    head=head,
                    lock_state=lock_state,
                )
            merged_reason = "matching GitHub PR is merged at this exact head"
        reason = merged_reason
    else:
        reason = "clean; all commits reachable from another durable ref"

    return TreeRecord(entry.name, path, branch, head, age_days, size_mb, "prune", reason, lock_state)


def audit_worktrees(
    repo_root: str,
    *,
    with_sizes: bool = True,
    current_paths: Optional[Iterable[str | Path]] = None,
    kanban_paths: Optional[Iterable[str | Path]] = None,
) -> list[TreeRecord]:
    """Classify all directories under the primary checkout's ``.worktrees``."""
    canonical = resolve_repo_root(repo_root)
    if canonical is None:
        return []
    worktrees_dir = _managed_worktrees_root(canonical)
    if worktrees_dir is None or not worktrees_dir.is_dir():
        return []

    current = discover_current_paths() if current_paths is None else {
        resolved for item in current_paths if (resolved := _resolved(item)) is not None
    }
    kanban = _kanban_owned_paths() if kanban_paths is None else {
        resolved for item in kanban_paths if (resolved := _resolved(item)) is not None
    }
    shallow = _repo_is_shallow(canonical)

    try:
        entries = sorted((entry for entry in worktrees_dir.iterdir() if entry.is_dir()), key=lambda item: item.name)
    except OSError:
        return []
    return [
        _audit_tree(
            canonical,
            entry,
            with_size=with_sizes,
            current_paths=current,
            kanban_paths=kanban,
            shallow=shallow,
        )
        for entry in entries
    ]


def _active_branches(repo_root: str) -> Optional[set[str]]:
    result = _git(["worktree", "list", "--porcelain"], cwd=repo_root, timeout=10)
    if result.returncode != 0:
        return None
    active: set[str] = set()
    for line in result.stdout.splitlines():
        if line.startswith("branch refs/heads/"):
            active.add(line[len("branch refs/heads/") :].strip())
    return active


def _audit_branch(repo_root: str, name: str, head: str, upstream: str, active: set[str]) -> BranchRecord:
    def keep(reason: str) -> BranchRecord:
        return BranchRecord(name, head, "keep", reason)

    if name in PROTECTED_BRANCHES:
        return keep("protected branch")
    if name in active:
        return keep("checked out in a worktree")

    ancestor = _git(["merge-base", "--is-ancestor", name, upstream], cwd=repo_root, timeout=10)
    if ancestor.returncode == 0:
        return BranchRecord(name, head, "delete", f"fully merged into {upstream}")
    if ancestor.returncode not in {1}:
        return keep("could not verify merge ancestry")

    ahead = _git(["rev-list", "--count", f"{upstream}..{name}"], cwd=repo_root, timeout=10)
    if ahead.returncode != 0:
        return keep("could not count commits ahead of upstream")
    try:
        count = int(ahead.stdout.strip())
    except ValueError:
        return keep("invalid upstream commit count")
    if count == 0:
        return BranchRecord(name, head, "delete", f"no commits beyond {upstream}")
    if count > _MAX_PATCH_EQUIVALENCE_COMMITS:
        return keep(f"{count} commits ahead (comparison limit exceeded)")

    cherry = _git(["cherry", upstream, name], cwd=repo_root, timeout=30)
    if cherry.returncode != 0:
        return keep("git cherry failed")
    lines = [line.strip() for line in cherry.stdout.splitlines() if line.strip()]
    if lines and all(line.startswith("-") for line in lines):
        return BranchRecord(name, head, "delete", "all commits patch-equivalent upstream")

    pr_merged = _merged_pr_state(repo_root, name, head)
    if pr_merged is None:
        return keep("unique commits; merged-PR probe failed/unavailable")
    if pr_merged:
        return BranchRecord(name, head, "delete", "matching GitHub PR is merged at this exact head")
    unique = sum(line.startswith("+") for line in lines)
    return keep(f"{unique} unique commit(s); no matching merged PR")


def audit_branches(repo_root: str) -> list[BranchRecord]:
    """Classify local branches using reachability, patch IDs, and exact-head PR state."""
    canonical = resolve_repo_root(repo_root)
    if canonical is None:
        return []
    active = _active_branches(canonical)
    listed = _git(
        ["for-each-ref", "--format=%(objectname) %(refname:short)", "refs/heads"],
        cwd=canonical,
        timeout=10,
    )
    if listed.returncode != 0:
        return []
    rows: list[tuple[str, str]] = []
    for line in listed.stdout.splitlines():
        head, separator, name = line.strip().partition(" ")
        if separator and head and name:
            rows.append((name, head))

    if active is None:
        return [BranchRecord(name, head, "keep", "could not enumerate checked-out branches") for name, head in rows]
    shallow = _repo_is_shallow(canonical)
    if shallow is not False:
        reason = "shallow repository; history safety cannot be verified" if shallow else "could not verify repository history"
        return [BranchRecord(name, head, "keep", reason) for name, head in rows]
    upstream = _default_upstream(canonical)
    if upstream is None:
        return [BranchRecord(name, head, "keep", "no default upstream ref") for name, head in rows]

    workers = max(1, min(8, len(rows), os.cpu_count() or 4))
    if workers == 1:
        return [_audit_branch(canonical, name, head, upstream, active) for name, head in rows]
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers, thread_name_prefix="clio-worktree-gc") as pool:
            return list(pool.map(lambda row: _audit_branch(canonical, row[0], row[1], upstream, active), rows))
    except Exception as exc:
        logger.debug("Parallel branch audit failed; retrying serially: %s", exc)
        return [_audit_branch(canonical, name, head, upstream, active) for name, head in rows]


def reclaim_worktrees(
    repo_root: str,
    *,
    dry_run: bool = False,
    records: Optional[Iterable[TreeRecord]] = None,
    current_paths: Optional[Iterable[str | Path]] = None,
    kanban_paths: Optional[Iterable[str | Path]] = None,
) -> list[str]:
    """Remove only trees that pass a fresh safety audit immediately before removal."""
    canonical = resolve_repo_root(repo_root)
    if canonical is None:
        return ["kept all worktrees (repository root could not be resolved)"]
    worktrees_root = _managed_worktrees_root(canonical)
    if worktrees_root is None:
        return ["kept all worktrees (.worktrees is symlinked or could not be resolved)"]
    frozen = list(records) if records is not None else audit_worktrees(
        canonical,
        with_sizes=False,
        current_paths=current_paths,
        kanban_paths=kanban_paths,
    )
    current = discover_current_paths() if current_paths is None else {
        resolved for item in current_paths if (resolved := _resolved(item)) is not None
    }
    kanban = _kanban_owned_paths() if kanban_paths is None else {
        resolved for item in kanban_paths if (resolved := _resolved(item)) is not None
    }
    shallow = _repo_is_shallow(canonical)
    actions: list[str] = []

    for record in frozen:
        if record.verdict != "prune":
            continue
        if not _is_managed_worktree_path(record.path, worktrees_root):
            actions.append(f"kept {record.name} (path is outside the managed .worktrees directory)")
            continue
        if dry_run:
            actions.append(f"would remove worktree {record.name} ({record.reason})")
            continue
        entry = Path(record.path)
        if not entry.is_dir():
            actions.append(f"kept {record.name} (path disappeared before revalidation)")
            continue
        fresh = _audit_tree(
            canonical,
            entry,
            with_size=False,
            current_paths=current,
            kanban_paths=kanban,
            shallow=shallow,
        )
        if fresh.verdict != "prune" or fresh.branch != record.branch or fresh.head != record.head:
            actions.append(f"kept {record.name} (state changed: {fresh.reason})")
            continue
        if fresh.lock_state == "dead":
            unlocked = _git(["worktree", "unlock", fresh.path], cwd=canonical, timeout=10)
            if unlocked.returncode != 0:
                actions.append(f"kept {record.name} (could not clear dead Clio lock)")
                continue

        removed = _git(["worktree", "remove", fresh.path, "--force"], cwd=canonical, timeout=60)
        if removed.returncode != 0:
            actions.append(f"failed to remove {record.name}: {removed.stderr.strip() or 'git worktree remove failed'}")
            continue
        actions.append(f"removed worktree {record.name}")

        if fresh.branch and fresh.branch not in PROTECTED_BRANCHES:
            active = _active_branches(canonical)
            if active is None or fresh.branch in active:
                actions.append(f"kept branch {fresh.branch} (could not prove it is inactive)")
                continue
            deleted = _git(["branch", "-D", fresh.branch], cwd=canonical, timeout=10)
            if deleted.returncode == 0:
                actions.append(f"deleted branch {fresh.branch}")
            else:
                actions.append(f"kept branch {fresh.branch} ({deleted.stderr.strip() or 'delete failed'})")

    if not dry_run:
        _git(["worktree", "prune"], cwd=canonical, timeout=15)
    return actions


def reclaim_branches(
    repo_root: str,
    *,
    dry_run: bool = False,
    records: Optional[Iterable[BranchRecord]] = None,
) -> list[str]:
    """Delete branch refs only after a second, exact-head safety audit."""
    canonical = resolve_repo_root(repo_root)
    if canonical is None:
        return ["kept all branches (repository root could not be resolved)"]
    frozen = list(records) if records is not None else audit_branches(canonical)
    actions: list[str] = []
    for record in frozen:
        if record.verdict != "delete":
            continue
        if dry_run:
            actions.append(f"would delete branch {record.name} ({record.reason})")
            continue
        fresh_by_name = {item.name: item for item in audit_branches(canonical)}
        fresh = fresh_by_name.get(record.name)
        if fresh is None or fresh.verdict != "delete" or fresh.head != record.head:
            reason = fresh.reason if fresh is not None else "branch disappeared"
            actions.append(f"kept branch {record.name} (state changed: {reason})")
            continue
        result = _git(["branch", "-D", record.name], cwd=canonical, timeout=10)
        if result.returncode == 0:
            actions.append(f"deleted branch {record.name}")
        else:
            actions.append(f"kept branch {record.name} ({result.stderr.strip() or 'delete failed'})")
    return actions


def worktrees_summary(repo_root: str) -> tuple[int, Optional[int]]:
    canonical = resolve_repo_root(repo_root)
    if canonical is None:
        return 0, None
    directory = Path(canonical) / ".worktrees"
    if directory.is_symlink() or not directory.is_dir():
        return 0, 0
    try:
        entries = [entry for entry in directory.iterdir() if entry.is_dir()]
    except OSError:
        return 0, None
    return len(entries), _directory_size_mb(directory)
