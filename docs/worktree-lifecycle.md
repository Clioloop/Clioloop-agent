# Worktree lifecycle

Clio can create isolated Git worktrees for parallel agent sessions and can now
inspect or reclaim stale worktrees without treating cleanup as a blind delete.

## Commands

```bash
clio worktree list
clio worktree prune --dry-run
clio worktree prune
clio worktree prune --trees-only
clio worktree prune --branches-only
```

The classic CLI also exposes `/worktree list` and `/worktree prune`.

`list` shows the repository, branch, path, status, and the reason each tree is
kept or considered reclaimable. Run `prune --dry-run` before an attended
cleanup to inspect the frozen decision set.

## Safety rules

The pruner fails safe. It keeps a worktree when it is:

- the current or main worktree;
- dirty, locked, or owned by an active Clio/Kanban task;
- on a protected branch;
- carrying commits not reachable from a protected branch;
- not confidently identified as merged;
- affected by a failed Git or GitHub probe.

For rebase-merged pull requests, Clio may use authenticated `gh` metadata as a
secondary signal. A missing CLI, network error, or ambiguous response means
**keep**, never delete. Worktree creation also allows enough time for a busy
disk and removes partial artifacts after a failed add.

Cleanup is repository-scoped and profile-aware. It does not run automatically;
operators choose when to list, dry-run, and prune.

## Terminal keyboard compatibility

The interactive CLI and Ink TUI negotiate enhanced keyboard protocols without
sending Kitty's push sequence to Ghostty. CSI-u aliases include NumLock and
CapsLock modifier-bit variants, keeping navigation and command shortcuts stable
when lock keys are active.
