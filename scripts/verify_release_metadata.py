#!/usr/bin/env python3
"""Check CI shard, provenance and project license metadata."""
from __future__ import annotations
import json, sys, tomllib
from pathlib import Path

root = Path(__file__).resolve().parents[1]
errors: list[str] = []
def load(name: str):
    try: return json.loads((root/name).read_text(encoding="utf-8"))
    except Exception as exc: errors.append(f"{name}: {exc}"); return {}
prov = load("config/provenance.json"); shards = load("config/ci-shards.json")
if not (root/"LICENSE").is_file(): errors.append("LICENSE is missing")
project = tomllib.loads((root/"pyproject.toml").read_text(encoding="utf-8"))["project"]
package = json.loads((root/"package.json").read_text(encoding="utf-8"))
for source, value in (("pyproject.toml", project.get("license")), ("package.json", package.get("license")), ("provenance", prov.get("license"))):
    if value != "MIT": errors.append(f"{source}: expected MIT license declaration")
for item in prov.get("upstreams", []):
    for field in ("name", "repository", "revision", "license", "usage"):
        if not item.get(field): errors.append(f"provenance upstream missing {field}")
ids = [item.get("id") for item in shards.get("shards", [])]
if len(ids) != len(set(ids)) or None in ids: errors.append("CI shard ids must be present and unique")
for item in shards.get("shards", []):
    if not item.get("command") and not item.get("paths"): errors.append(f"CI shard {item.get('id')} has no command or paths")
print("\n".join(errors) if errors else "release metadata: passed")
sys.exit(bool(errors))
