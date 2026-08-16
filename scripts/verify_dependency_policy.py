#!/usr/bin/env python3
"""Enforce reviewed direct-dependency policy for Python and npm workspaces."""
from __future__ import annotations
import argparse, json, re, sys, tomllib
from pathlib import Path

NAME = re.compile(r"^([A-Za-z0-9_.-]+)")
EXACT = re.compile(r"^[A-Za-z0-9_.-]+(?:\[[^]]+\])?==[^,;\s]+(?:\s*;.*)?$")

def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--root", type=Path, default=Path(".")); args = ap.parse_args()
    root = args.root.resolve(); policy = json.loads((root / "config/dependency-policy.json").read_text(encoding="utf-8"))
    errors: list[str] = []
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    allowed = set(policy["python"]["allowed_ranges"])
    groups = {"project.dependencies": project["project"].get("dependencies", [])}
    groups.update({f"project.optional-dependencies.{k}": v for k,v in project["project"].get("optional-dependencies", {}).items()})
    for group, deps in groups.items():
        for dep in deps:
            if dep.startswith("clioloop-agent["):
                continue
            name_match = NAME.match(dep); name = name_match.group(1).lower() if name_match else dep
            if not EXACT.match(dep) and name not in allowed:
                errors.append(f"{group}: {dep!r} is not exact-pinned or allowlisted")
    forbidden = set(policy["npm"]["forbid_tags"]); allowed_tags = set(policy["npm"]["allowed_tags"])
    for package in sorted(root.glob("**/package.json")):
        if "node_modules" in package.parts:
            continue
        data = json.loads(package.read_text(encoding="utf-8"))
        for section in ("dependencies", "devDependencies", "optionalDependencies"):
            for name, spec in data.get(section, {}).items():
                if spec in forbidden and name not in allowed_tags:
                    errors.append(f"{package.relative_to(root)}:{section}.{name}: forbidden tag {spec!r}")
    print("\n".join(errors) if errors else "dependency policy: passed")
    return bool(errors)
if __name__ == "__main__": sys.exit(main())
