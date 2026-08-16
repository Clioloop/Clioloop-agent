"""Offline-first community plugin index, cache and fuzzy search."""
from __future__ import annotations
import difflib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from clio_constants import get_clio_home

INDEX_CACHE_TTL = 86400
SEED_INDEX_PATH = Path(__file__).parent / "data" / "plugin_index.json"
_REPO = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?/[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?$")
_REF = re.compile(r"^[0-9a-fA-F]{40}$")


def _safe_subdir(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        return ""
    parts = value.replace("\\", "/").strip("/").split("/")
    return "/".join(parts) if all(part not in ("", ".", "..") for part in parts) else ""


@dataclass(frozen=True)
class PluginIndexEntry:
    name: str
    repo: str
    ref: str
    description: str = ""
    author: str = ""
    tags: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    subdir: str | None = None

    @property
    def install_identifier(self) -> str:
        return f"{self.repo}/{self.subdir}" if self.subdir else self.repo

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in vars(self).items() if v not in (None, "", [])}


def parse_index(raw: Any) -> list[PluginIndexEntry]:
    items = raw.get("plugins", []) if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        raise ValueError("plugin index must contain a plugins list")
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name, repo, ref = item.get("name"), item.get("repo"), item.get("ref")
        subdir = _safe_subdir(item.get("subdir"))
        if (not isinstance(name, str) or not name.strip() or not isinstance(repo, str)
                or not _REPO.fullmatch(repo) or not isinstance(ref, str)
                or not _REF.fullmatch(ref) or subdir == ""):
            continue
        out.append(PluginIndexEntry(
            name=name.strip(), repo=repo, ref=ref.lower(),
            description=str(item.get("description") or ""), author=str(item.get("author") or ""),
            tags=[str(x) for x in item.get("tags") or []],
            capabilities=[str(x) for x in item.get("capabilities") or []],
            subdir=subdir,
        ))
    return out


def load_index(*, offline: bool = True, refresh: bool = False) -> tuple[list[PluginIndexEntry], str]:
    """Load cache then bundled seed. Network refresh is deliberately caller-owned."""
    cache = get_clio_home() / "cache" / "plugin_index.json"
    if cache.is_file() and (refresh or time.time() - cache.stat().st_mtime <= INDEX_CACHE_TTL):
        try:
            return parse_index(json.loads(cache.read_text(encoding="utf-8"))), "cache"
        except (OSError, ValueError):
            pass
    try:
        return parse_index(json.loads(SEED_INDEX_PATH.read_text(encoding="utf-8"))), "seed"
    except (OSError, ValueError):
        return [], "seed"


def search_index(entries: list[PluginIndexEntry], term: str = "", *, capability: str | None = None) -> list[PluginIndexEntry]:
    pool = entries
    if capability:
        pool = [e for e in pool if capability.lower() in {c.lower() for c in e.capabilities}]
    term = term.strip().lower()
    if not term:
        return sorted(pool, key=lambda e: e.name)
    def score(e: PluginIndexEntry) -> float:
        name = e.name.lower()
        if term == name: return 100
        if term in name: return 80
        if any(term in t.lower() for t in e.tags): return 60
        if term in e.description.lower(): return 50
        return difflib.SequenceMatcher(None, term, name).ratio() * 40
    return [e for e in sorted(pool, key=lambda e: (-score(e), e.name)) if score(e) >= 20]


def resolve_name(entries: list[PluginIndexEntry], name: str):
    exact = [e for e in entries if e.name.lower() == name.lower()]
    if len(exact) == 1: return exact[0], exact
    partial = [e for e in entries if name.lower() in e.name.lower()]
    return (partial[0], partial) if len(partial) == 1 else (None, exact or partial)
