#!/usr/bin/env python3
"""Skill Evolution Engine for ClioLoop.

Analyzes the skill library and evolves it by:
  - Detecting overlapping / duplicate skills
  - Merging them into unified class-level skills
  - Archiving stale / unused skills
  - Suggesting new skills based on conversation history

Usage:
    /evolve              — Full analysis + auto-merge + report
    /evolve --dry-run    — Analysis only, no changes
    /evolve --report     — Print a skill health report
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _skill_dirs() -> List[Path]:
    """Return all directories that may contain user skills."""
    dirs: List[Path] = []
    # Primary user skill store
    primary = Path.home() / ".clio" / "skills"
    if primary.exists():
        dirs.append(primary)
    # External dirs from config
    try:
        from clio_cli.config import cfg_get
        ext = cfg_get("skills.external_dirs", [])
        for d in ext:
            p = Path(d).expanduser()
            if p.exists():
                dirs.append(p)
    except Exception:
        pass
    return dirs


def _all_skills() -> List[Dict[str, Any]]:
    """Enumerate every skill with its metadata."""
    skills: List[Dict[str, Any]] = []
    seen: set = set()
    for base in _skill_dirs():
        for entry in sorted(base.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            # entry may be a category dir (e.g. "web-development") or a direct skill dir
            # Check if entry itself has SKILL.md
            if (entry / "SKILL.md").exists():
                _collect_skill(entry, skills, seen)
            else:
                # It's a category — look one level deeper
                for sub in sorted(entry.iterdir()):
                    if sub.is_dir() and not sub.name.startswith("."):
                        _collect_skill(sub, skills, seen)
    return skills


def _collect_skill(path: Path, skills: List[Dict[str, Any]], seen: set) -> None:
    """Append a skill dict to skills list."""
    skill_md = path / "SKILL.md"
    if not skill_md.exists():
        return
    key = str(path.resolve())
    if key in seen:
        return
    seen.add(key)
    stat = skill_md.stat()
    content = ""
    try:
        content = skill_md.read_text(encoding="utf-8", errors="replace")
    except Exception:
        pass
    # Parse frontmatter
    name = path.name
    description = ""
    category = ""
    if content.startswith("---"):
        end = content.find("---", 3)
        if end > 0:
            fm = content[3:end]
            for line in fm.splitlines():
                line = line.strip()
                if line.startswith("name:"):
                    name = line.split(":", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("description:"):
                    description = line.split(":", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("category:"):
                    category = line.split(":", 1)[1].strip().strip('"').strip("'")
    refs = list((path / "references").glob("*")) if (path / "references").exists() else []
    tmpls = list((path / "templates").glob("*")) if (path / "templates").exists() else []
    scripts = list((path / "scripts").glob("*")) if (path / "scripts").exists() else []
    skills.append({
        "path": path,
        "name": name,
        "description": description,
        "category": category,
        "dir_name": path.name,
        "content": content,
        "size": len(content),
        "mtime": stat.st_mtime,
        "atime": stat.st_atime,
        "ref_count": len(refs),
        "tmpl_count": len(tmpls),
        "script_count": len(scripts),
        "support_total": len(refs) + len(tmpls) + len(scripts),
    })


def _text_similarity(a: str, b: str) -> float:
    """Simple Jaccard similarity on word sets (0.0 – 1.0)."""
    words_a = set(re.findall(r"[a-z]{3,}", a.lower()))
    words_b = set(re.findall(r"[a-z]{3,}", b.lower()))
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union) if union else 0.0


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def find_overlaps(skills: List[Dict[str, Any]], threshold: float = 0.35) -> List[Tuple[int, int, float]]:
    """Return pairs of skill indices whose content similarity >= threshold."""
    overlaps: List[Tuple[int, int, float]] = []
    for i in range(len(skills)):
        for j in range(i + 1, len(skills)):
            sim = _text_similarity(skills[i]["content"], skills[j]["content"])
            if sim >= threshold:
                overlaps.append((i, j, round(sim, 2)))
    # Also check description similarity as a secondary signal
    for i in range(len(skills)):
        for j in range(i + 1, len(skills)):
            if any(o[0] == i and o[1] == j for o in overlaps):
                continue
            sim = _text_similarity(skills[i]["description"], skills[j]["description"])
            if sim >= 0.5:
                overlaps.append((i, j, round(sim, 2)))
    return sorted(overlaps, key=lambda x: -x[2])


def find_stale(skills: List[Dict[str, Any]], days: int = 90) -> List[int]:
    """Return indices of skills not modified in `days` days with zero support files."""
    cutoff = datetime.now(tz=timezone.utc).timestamp() - (days * 86400)
    stale: List[int] = []
    for i, s in enumerate(skills):
        if s["mtime"] < cutoff and s["support_total"] == 0:
            stale.append(i)
    return stale


def find_undersized(skills: List[Dict[str, Any]]) -> List[int]:
    """Return indices of skills with very thin content (< 100 chars body)."""
    thin: List[int] = []
    for i, s in enumerate(skills):
        body = s["content"]
        # Strip frontmatter
        if body.startswith("---"):
            end = body.find("---", 3)
            if end > 0:
                body = body[end + 3:]
        if len(body.strip()) < 100:
            thin.append(i)
    return thin


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def merge_skills(skills: List[Dict[str, Any]], idx_a: int, idx_b: int, dry_run: bool = False) -> Optional[str]:
    """Merge skill B into skill A. Returns a summary string or None."""
    a, b = skills[idx_a], skills[idx_b]
    if dry_run:
        return f"Would merge '{b['name']}' into '{a['name']}'"

    target_dir = a["path"]
    source_dir = b["path"]

    # Copy support files from B that don't exist in A
    copied = 0
    for subdir in ("references", "templates", "scripts", "assets"):
        src_sub = source_dir / subdir
        if not src_sub.exists():
            continue
        dst_sub = target_dir / subdir
        dst_sub.mkdir(exist_ok=True)
        for f in src_sub.iterdir():
            if not f.is_file():
                continue
            dst_file = dst_sub / f.name
            if not dst_file.exists():
                shutil.copy2(f, dst_file)
                copied += 1

    # Append B's unique content to A's SKILL.md
    b_body = b["content"]
    if b_body.startswith("---"):
        end = b_body.find("---", 3)
        if end > 0:
            b_body = b_body[end + 3:].strip()

    if b_body:
        with open(target_dir / "SKILL.md", "a", encoding="utf-8") as fh:
            fh.write(f"\n\n---\n\n## Merged from: {b['name']}\n\n{b_body}")

    # Move B to archive
    archive_dir = source_dir.parent / "_archived"
    archive_dir.mkdir(exist_ok=True)
    archive_target = archive_dir / source_dir.name
    if archive_target.exists():
        shutil.rmtree(archive_target)
    shutil.move(str(source_dir), str(archive_target))

    return f"Merged '{b['name']}' → '{a['name']}' ({copied} files copied)"


def archive_skill(skill: Dict[str, Any], dry_run: bool = False) -> Optional[str]:
    """Move a skill to the _archived directory."""
    if dry_run:
        return f"Would archive '{skill['name']}'"
    archive_dir = skill["path"].parent / "_archived"
    archive_dir.mkdir(exist_ok=True)
    target = archive_dir / skill["path"].name
    if target.exists():
        shutil.rmtree(target)
    shutil.move(str(skill["path"]), str(target))
    return f"Archived '{skill['name']}'"


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def build_report(
    skills: List[Dict[str, Any]],
    overlaps: List[Tuple[int, int, float]],
    stale: List[int],
    thin: List[int],
    actions: List[str],
) -> str:
    """Build a human-readable evolution report."""
    lines: List[str] = []
    lines.append("🧠 Skill Evolution Report")
    lines.append("=" * 40)
    lines.append(f"Total skills: {len(skills)}")

    # Category breakdown
    cats: Counter = Counter()
    for s in skills:
        cat = s["category"] or s["path"].parent.name
        cats[cat] += 1
    lines.append(f"\n📁 By category:")
    for cat, count in cats.most_common():
        lines.append(f"   {cat}: {count}")

    # Overlaps
    if overlaps:
        lines.append(f"\n🔀 Overlapping pairs ({len(overlaps)}):")
        for i, j, sim in overlaps[:10]:
            lines.append(f"   [{sim:.0%}] {skills[i]['name']} ↔ {skills[j]['name']}")
        if len(overlaps) > 10:
            lines.append(f"   ... and {len(overlaps) - 10} more")

    # Stale
    if stale:
        lines.append(f"\n🕐 Stale skills ({len(stale)}):")
        for idx in stale[:10]:
            age_days = (datetime.now(tz=timezone.utc).timestamp() - skills[idx]["mtime"]) / 86400
            lines.append(f"   {skills[idx]['name']} ({age_days:.0d} days old)")

    # Thin
    if thin:
        lines.append(f"\n📉 Undersized skills ({len(thin)}):")
        for idx in thin[:10]:
            lines.append(f"   {skills[idx]['name']} ({skills[idx]['size']} chars)")

    # Actions taken
    if actions:
        lines.append(f"\n✅ Actions taken ({len(actions)}):")
        for a in actions:
            lines.append(f"   {a}")
    else:
        lines.append("\n✅ No changes needed — skill library is healthy.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_evolve(dry_run: bool = False, report_only: bool = False) -> str:
    """Run the full skill evolution pipeline. Returns the report string.
    
    Only scans user-created skills in ~/.clio/skills/ — never touches
    the bundled/built-in skills in the repo.
    """
    skills = _all_skills()
    if not skills:
        return "🧠 No user skills found in ~/.clio/skills/. Create some skills first, then run /evolve to optimize them."

    overlaps = find_overlaps(skills)
    stale = find_stale(skills)
    thin = find_undersized(skills)
    actions: List[str] = []

    if report_only:
        return build_report(skills, overlaps, stale, thin, actions)

    # Auto-merge high-similarity pairs (>= 0.6)
    merged_indices: set = set()
    for i, j, sim in overlaps:
        if sim >= 0.6 and i not in merged_indices and j not in merged_indices:
            result = merge_skills(skills, i, j, dry_run=dry_run)
            if result:
                actions.append(result)
                merged_indices.add(j)

    # Archive stale skills
    for idx in stale:
        if idx not in merged_indices:
            result = archive_skill(skills[idx], dry_run=dry_run)
            if result:
                actions.append(result)

    return build_report(skills, overlaps, stale, thin, actions)


if __name__ == "__main__":
    import sys
    dry = "--dry-run" in sys.argv
    report = "--report" in sys.argv
    print(run_evolve(dry_run=dry, report_only=report))
