"""Fail-closed regressions for the attended worktree lifecycle command."""

from __future__ import annotations

import argparse
from pathlib import Path

from clio_cli import worktree_cmd, worktree_gc


def _tree(path: Path, *, head: str = "abc") -> worktree_gc.TreeRecord:
    return worktree_gc.TreeRecord(
        name=path.name,
        path=str(path),
        branch="topic",
        head=head,
        age_days=2.0,
        size_mb=None,
        verdict="prune",
        reason="test candidate",
    )


def test_reclaim_rejects_candidate_outside_managed_directory(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    outside = tmp_path / "outside"
    (repo / ".worktrees").mkdir(parents=True)
    outside.mkdir()
    calls: list[list[str]] = []
    monkeypatch.setattr(worktree_gc, "resolve_repo_root", lambda _path: str(repo))
    monkeypatch.setattr(
        worktree_gc,
        "_git",
        lambda args, **_kwargs: calls.append(list(args)) or worktree_gc._completed(args, returncode=0),
    )

    actions = worktree_gc.reclaim_worktrees(str(repo), records=[_tree(outside)])

    assert actions == ["kept outside (path is outside the managed .worktrees directory)"]
    assert not any(call[:2] == ["worktree", "remove"] for call in calls)


def test_reclaim_rejects_symlinked_managed_directory(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    outside = tmp_path / "outside"
    repo.mkdir()
    outside.mkdir()
    (repo / ".worktrees").symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(worktree_gc, "resolve_repo_root", lambda _path: str(repo))

    actions = worktree_gc.reclaim_worktrees(str(repo), records=[_tree(outside / "candidate")])

    assert actions == ["kept all worktrees (.worktrees is symlinked or could not be resolved)"]


def test_reclaim_revalidates_exact_head_before_remove(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    candidate = repo / ".worktrees" / "candidate"
    candidate.mkdir(parents=True)
    stale = _tree(candidate, head="old")
    fresh = _tree(candidate, head="new")
    calls: list[list[str]] = []
    monkeypatch.setattr(worktree_gc, "resolve_repo_root", lambda _path: str(repo))
    monkeypatch.setattr(worktree_gc, "discover_current_paths", lambda: set())
    monkeypatch.setattr(worktree_gc, "_kanban_owned_paths", lambda: set())
    monkeypatch.setattr(worktree_gc, "_repo_is_shallow", lambda _path: False)
    monkeypatch.setattr(worktree_gc, "_audit_tree", lambda *_args, **_kwargs: fresh)
    monkeypatch.setattr(
        worktree_gc,
        "_git",
        lambda args, **_kwargs: calls.append(list(args)) or worktree_gc._completed(args, returncode=0),
    )

    actions = worktree_gc.reclaim_worktrees(str(repo), records=[stale])

    assert actions == ["kept candidate (state changed: test candidate)"]
    assert not any(call[:2] == ["worktree", "remove"] for call in calls)


def test_cli_registration_and_slash_registry(monkeypatch):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    worktree_cmd.register_cli(subparsers)
    args = parser.parse_args(["worktree", "prune", "--dry-run", "--repo", "/repo"])
    assert args.func is worktree_cmd.cmd_worktree
    assert args.worktree_action == "prune"
    assert args.dry_run is True
    assert args.repo == "/repo"

    from clio_cli.commands import resolve_command

    definition = resolve_command("worktree")
    assert definition is not None
    assert definition.cli_only is True
    assert definition.subcommands == ("list", "prune")

    monkeypatch.setattr(worktree_gc, "resolve_repo_root", lambda _path: None)
    code, lines = worktree_cmd.execute_worktree_slash("/worktree prune --dry-run --repo /repo")
    assert code == 1
    assert lines == ["Not inside a git repository."]