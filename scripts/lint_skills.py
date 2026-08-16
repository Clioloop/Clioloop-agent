#!/usr/bin/env python3
"""Validate Clio SKILL.md metadata and layout without importing application code."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REQUIRED = ("name", "description")
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,79}$")
VERSION = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def lint(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return [f"{path}:1: missing YAML front matter"]
    try:
        front, body = text[4:].split("\n---\n", 1)
    except ValueError:
        return [f"{path}: missing closing front matter delimiter"]
    values: dict[str, str] = {}
    for number, line in enumerate(front.splitlines(), 2):
        if not line.strip() or line[0].isspace():
            continue
        if ":" not in line:
            errors.append(f"{path}:{number}: malformed metadata line")
            continue
        key, value = line.split(":", 1)
        if key in values:
            errors.append(f"{path}:{number}: duplicate metadata key {key!r}")
        values[key] = value.strip().strip("\"'")
    for key in REQUIRED:
        if not values.get(key):
            errors.append(f"{path}: metadata.{key} is required")
    if values.get("name") and not NAME.fullmatch(values["name"]):
        errors.append(f"{path}: metadata.name is invalid")
    if values.get("version") and not VERSION.fullmatch(values["version"]):
        errors.append(f"{path}: metadata.version must be SemVer")
    if not re.search(r"^#\s+\S", body, re.MULTILINE):
        errors.append(f"{path}: body needs an H1 heading")
    if len(body.strip()) < 40:
        errors.append(f"{path}: body is too short")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", type=Path, default=[Path("skills")])
    args = parser.parse_args()
    files = sorted({p for root in args.paths for p in ([root] if root.is_file() else root.rglob("SKILL.md"))})
    errors = [error for path in files for error in lint(path)]
    if not files:
        errors.append("no SKILL.md files found")
    print("\n".join(errors) if errors else f"skill lint: {len(files)} file(s) passed")
    return bool(errors)

if __name__ == "__main__":
    sys.exit(main())
