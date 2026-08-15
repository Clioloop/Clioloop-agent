"""Prompt builder for the canonical ``/init`` project-instructions command."""

from __future__ import annotations

import os
from pathlib import Path


def build_init_prompt_for_cwd(cwd: str | None = None, extra: str = "") -> str:
    """Build a normal agent turn that safely creates or updates ``AGENTS.md``."""
    root = Path(cwd or os.getenv("TERMINAL_CWD") or os.getcwd()).resolve()
    target = root / "AGENTS.md"
    existing: str | None = None
    try:
        if target.is_file():
            existing = target.read_text(encoding="utf-8", errors="replace")
    except OSError:
        existing = None

    action = "UPDATE the existing AGENTS.md" if existing is not None else "generate an AGENTS.md"
    prompt = f"""[/init] {action} project-instructions file for {root}.

Inspect this repository with read-only tools first: manifests, lockfiles, CI,
README/docs, tests, lint configuration, and representative source. Then write
{target} with write_file. Keep it concise (target under 100 lines), concrete,
and repository-specific. Include exact setup/build/test/lint commands you
verified, observed conventions, and genuine pitfalls. Never invent commands or
add generic best-practice filler. Confirm the exact path when done."""
    if existing is not None:
        prompt += (
            "\n\nThis is an update: preserve the user's wording, sections, and rules; "
            "make only surgical additions or corrections. Current content:\n"
            "<<<EXISTING_AGENTS_MD\n" + existing + "\nEXISTING_AGENTS_MD"
        )
    if extra.strip():
        prompt += "\n\nUser notes (override defaults where needed):\n" + extra.strip()
    return prompt


__all__ = ["build_init_prompt_for_cwd"]
