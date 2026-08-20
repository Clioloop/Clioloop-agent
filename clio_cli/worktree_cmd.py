"""Command presentation for ``clio worktree`` and ``/worktree``."""

from __future__ import annotations

import argparse
import shlex
from typing import Optional

from clio_cli import worktree_gc


def _fmt_size(size_mb: Optional[int]) -> str:
    if size_mb is None:
        return "?"
    if size_mb >= 1024:
        return f"{size_mb / 1024:.1f}G"
    return f"{size_mb}M"


def _audit_lines(repo_root: str) -> list[str]:
    records = worktree_gc.audit_worktrees(repo_root)
    branches = worktree_gc.audit_branches(repo_root)
    lines: list[str] = []
    if records:
        lines.append(f"{'TREE':30} {'BRANCH':24} {'AGE':>6} {'SIZE':>6} {'VERDICT':>7}  REASON")
        for record in sorted(records, key=lambda item: (item.verdict != "prune", -(item.size_mb or 0), item.name)):
            lines.append(
                f"{record.name[:30]:30} {record.branch[:24]:24} "
                f"{record.age_days:5.1f}d {_fmt_size(record.size_mb):>6} "
                f"{record.verdict.upper():>7}  {record.reason}"
            )
        total_mb = sum(record.size_mb or 0 for record in records)
        reclaimable_mb = sum(record.size_mb or 0 for record in records if record.verdict == "prune")
        lines.append(
            f"{len(records)} tree(s), {_fmt_size(total_mb)} total; "
            f"{_fmt_size(reclaimable_mb)} currently reclaimable."
        )
    else:
        lines.append("No worktrees found under .worktrees/.")

    deletable = [record for record in branches if record.verdict == "delete"]
    kept = [record for record in branches if record.verdict == "keep"]
    lines.append(
        f"Local branches: {len(branches)} audited, {len(deletable)} safely deletable, "
        f"{len(kept)} protected/unique/in-use."
    )
    lines.append("Preview reclamation with: clio worktree prune --dry-run")
    return lines


def execute_worktree(args) -> tuple[int, list[str]]:
    requested_repo = getattr(args, "repo", None)
    repo_root = worktree_gc.resolve_repo_root(requested_repo)
    if repo_root is None:
        hint = " (or pass --repo <path>)" if not requested_repo else ""
        return 1, [f"Not inside a git repository{hint}."]

    action = str(getattr(args, "worktree_action", None) or "list").lower()
    if action in {"list", "ls", "audit"}:
        return 0, _audit_lines(repo_root)
    if action not in {"prune", "gc", "clean"}:
        return 2, [f"Unknown worktree action: {action}"]

    dry_run = bool(getattr(args, "dry_run", False))
    trees_only = bool(getattr(args, "trees_only", False))
    branches_only = bool(getattr(args, "branches_only", False))
    if trees_only and branches_only:
        return 2, ["--trees-only and --branches-only cannot be used together."]

    lines: list[str] = []
    actions: list[str] = []
    if not branches_only:
        tree_records = worktree_gc.audit_worktrees(repo_root, with_sizes=False)
        actions.extend(
            worktree_gc.reclaim_worktrees(
                repo_root,
                dry_run=dry_run,
                records=tree_records,
            )
        )
        preserved = [record for record in tree_records if record.verdict == "keep"]
        if preserved:
            lines.append(f"Preserved {len(preserved)} worktree(s):")
            lines.extend(f"  {record.name}: {record.reason}" for record in preserved)

    if not trees_only:
        branch_records = worktree_gc.audit_branches(repo_root)
        actions.extend(
            worktree_gc.reclaim_branches(
                repo_root,
                dry_run=dry_run,
                records=branch_records,
            )
        )
        preserved_branches = [record for record in branch_records if record.verdict == "keep"]
        if preserved_branches:
            lines.append(f"Preserved {len(preserved_branches)} local branch(es).")

    if actions:
        lines.extend(f"  {action_line}" for action_line in actions)
        lines.append(f"{len(actions)} action(s) {'planned' if dry_run else 'completed'}.")
    else:
        lines.append("Nothing to reclaim; remaining worktrees/branches are dirty, unique, protected, or in use.")
    return 0, lines


def cmd_worktree(args) -> int:
    code, lines = execute_worktree(args)
    for line in lines:
        print(line)
    return code


def register_cli(subparsers) -> argparse.ArgumentParser:
    """Register the attended worktree audit/reclamation command."""
    parser = subparsers.add_parser(
        "worktree",
        help="Audit and safely reclaim Clio git worktrees and merged branches",
        description=(
            "Audit .worktrees/ and local branches conservatively. Reclamation "
            "is explicit and keeps dirty, unique, active, locked, shallow, or "
            "otherwise unverifiable state."
        ),
    )
    parser.add_argument("--repo", metavar="PATH", help="Repository checkout to audit (default: current directory)")
    actions = parser.add_subparsers(dest="worktree_action")
    list_parser = actions.add_parser("list", aliases=["ls", "audit"], help="Show worktree and branch safety verdicts")
    prune_parser = actions.add_parser(
        "prune",
        aliases=["gc", "clean"],
        help="Remove only worktrees and branches that pass all safety checks",
    )
    prune_parser.add_argument("--dry-run", action="store_true", help="Print actions without changing the repository")
    scope = prune_parser.add_mutually_exclusive_group()
    scope.add_argument("--trees-only", action="store_true", help="Reclaim worktrees but leave local branches alone")
    scope.add_argument("--branches-only", action="store_true", help="Reclaim local branches but leave worktrees alone")
    for action_parser in (list_parser, prune_parser):
        action_parser.add_argument("--repo", metavar="PATH", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
        action_parser.set_defaults(func=cmd_worktree)
    parser.set_defaults(func=cmd_worktree, worktree_action="list")
    return parser


def execute_worktree_slash(command: str) -> tuple[int, list[str]]:
    """Parse the deliberately small ``/worktree`` surface without exiting."""
    try:
        tokens = shlex.split(command)
    except ValueError as exc:
        return 2, [f"Invalid /worktree arguments: {exc}"]
    tokens = tokens[1:] if tokens and tokens[0].lstrip("/").lower() == "worktree" else tokens
    values: dict[str, object] = {
        "worktree_action": "list",
        "repo": None,
        "dry_run": False,
        "trees_only": False,
        "branches_only": False,
    }
    saw_action = False
    index = 0
    while index < len(tokens):
        token = tokens[index]
        lowered = token.lower()
        if lowered in {"list", "ls", "audit", "prune", "gc", "clean"} and not saw_action:
            values["worktree_action"] = lowered
            saw_action = True
        elif lowered == "--dry-run":
            values["dry_run"] = True
        elif lowered == "--trees-only":
            values["trees_only"] = True
        elif lowered == "--branches-only":
            values["branches_only"] = True
        elif lowered == "--repo":
            index += 1
            if index >= len(tokens):
                return 2, ["--repo requires a path."]
            values["repo"] = tokens[index]
        elif lowered.startswith("--repo="):
            values["repo"] = token.split("=", 1)[1]
        else:
            return 2, [f"Unknown /worktree argument: {token}"]
        index += 1
    return execute_worktree(argparse.Namespace(**values))
