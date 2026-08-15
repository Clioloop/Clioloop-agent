"""Secret-excluding, traversal-safe profile bundles."""
from __future__ import annotations

import json
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any

_SAFE_DIRS = {"skills", "plugins", "cron", "memories", "themes"}
_SAFE_FILES = {"config.json", "profile.json"}
_SECRET = re.compile(r"(^|[_.-])(secret|token|password|credential|api[_-]?key|auth|\.env)([_.-]|$)", re.I)
_SECRET_KEY = re.compile(r"secret|token|password|credential|api.?key|private.?key", re.I)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("<redacted>" if _SECRET_KEY.search(str(k)) else _redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def export_profile_bundle(profile_home: Path, destination: Path) -> Path:
    root, destination = Path(profile_home).resolve(), Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "x", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps({"format": "clio-profile", "version": 1}))
        for path in root.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            rel = path.relative_to(root)
            if rel.parts[0] not in _SAFE_DIRS and rel.as_posix() not in _SAFE_FILES:
                continue
            if any(_SECRET.search(part) for part in rel.parts):
                continue
            if rel.as_posix() in _SAFE_FILES:
                try:
                    zf.writestr(rel.as_posix(), json.dumps(_redact(json.loads(path.read_text())), indent=2))
                    continue
                except (ValueError, OSError):
                    continue  # fail closed for unparseable config
            zf.write(path, rel.as_posix())
    return destination


def import_profile_bundle(bundle: Path, profile_home: Path, *, overwrite: bool = False) -> int:
    root = Path(profile_home).resolve()
    root.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(bundle) as zf:
        names = set(zf.namelist())
        if "manifest.json" not in names:
            raise ValueError("not a Clio profile bundle")
        for info in zf.infolist():
            if info.is_dir() or info.filename == "manifest.json":
                continue
            rel = Path(info.filename)
            if rel.is_absolute() or ".." in rel.parts or not rel.parts:
                raise ValueError("unsafe bundle path")
            if rel.parts[0] not in _SAFE_DIRS and rel.as_posix() not in _SAFE_FILES:
                continue
            if any(_SECRET.search(part) for part in rel.parts):
                continue
            target = (root / rel).resolve()
            if root not in target.parents:
                raise ValueError("unsafe bundle path")
            if target.exists() and not overwrite:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            count += 1
    return count
