"""Local validator/translator for portable Agent Plugins directory packages.

The format is code-free: ``plugin.json`` metadata plus optional ``skills/`` and
``mcp.json``.  Discovery never fetches schemas or imports package code.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

PLUGIN_SCHEMA_V1 = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
_NAME = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
_SHA = re.compile(r"^[0-9a-fA-F]{40}$")
_ALLOWED = {
    "$schema", "name", "version", "description", "author", "homepage",
    "repository", "license", "keywords", "extensions", "package", "exact_ref",
    "dependencies", "entry_points",
}


class AgentPluginError(ValueError):
    pass


@dataclass(frozen=True)
class AgentPluginDiagnostic:
    scope: str
    message: str


@dataclass(frozen=True)
class AgentPluginSkill:
    name: str
    description: str
    root: Path
    skill_md: Path
    frontmatter: Mapping[str, Any]


@dataclass(frozen=True)
class AgentPluginPackage:
    name: str
    version: str
    description: str
    root: Path
    data_root: Path
    manifest: Mapping[str, Any]
    skills: tuple[AgentPluginSkill, ...]
    mcp_servers: Mapping[str, dict[str, Any]]
    diagnostics: tuple[AgentPluginDiagnostic, ...]
    package: Mapping[str, Any]
    exact_ref: str
    dependencies: Mapping[str, str]
    entry_points: Mapping[str, str]


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=True))
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AgentPluginError(f"{label} is not valid readable JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise AgentPluginError(f"{label} must contain a JSON object")
    return value


def read_agent_plugin_manifest(root: Path) -> tuple[dict[str, Any], tuple[AgentPluginDiagnostic, ...]]:
    root = Path(root)
    path = root / "plugin.json"
    if not _inside(path, root) or not path.is_file():
        raise AgentPluginError("plugin.json must be a regular file within the plugin root")
    value = _object(path, "plugin.json")
    diagnostics: list[AgentPluginDiagnostic] = []
    for field in sorted(set(value) - _ALLOWED):
        diagnostics.append(AgentPluginDiagnostic("manifest", f"ignored unknown top-level field: {field}"))
        value.pop(field)
    if value.get("$schema") != PLUGIN_SCHEMA_V1:
        raise AgentPluginError("plugin.json declares an unsupported or missing Agent Plugins schema")
    name = value.get("name")
    if not isinstance(name, str) or not 1 <= len(name) <= 64 or not _NAME.fullmatch(name):
        raise AgentPluginError("plugin.json name does not satisfy v1 constraints")
    for key in ("version", "description", "homepage", "repository", "license"):
        if key in value and not isinstance(value[key], str):
            raise AgentPluginError(f"plugin.json {key} must be a string")
    package = value.get("package") or {}
    if not isinstance(package, dict):
        raise AgentPluginError("plugin.json package must be an object")
    exact_ref = value.get("exact_ref") or package.get("exact_ref") or ""
    if exact_ref and (not isinstance(exact_ref, str) or not _SHA.fullmatch(exact_ref)):
        raise AgentPluginError("exact_ref must be an immutable 40-character commit SHA")
    for key in ("dependencies", "entry_points"):
        mapping = value.get(key) or {}
        if not isinstance(mapping, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in mapping.items()):
            raise AgentPluginError(f"plugin.json {key} must map strings to strings")
    return value, tuple(diagnostics)


def _frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        return {}, text
    import yaml
    header, body = text[4:].split("\n---\n", 1)
    value = yaml.safe_load(header) or {}
    return (value if isinstance(value, dict) else {}), body


def load_agent_plugin_package(root: Path, data_root: Path | None = None) -> AgentPluginPackage:
    root = Path(root).resolve()
    manifest, manifest_diags = read_agent_plugin_manifest(root)
    diagnostics = list(manifest_diags)
    skills: list[AgentPluginSkill] = []
    skills_root = root / "skills"
    if skills_root.is_dir() and _inside(skills_root, root):
        for child in sorted(skills_root.iterdir()):
            skill_md = child / "SKILL.md"
            if not child.is_dir() or not skill_md.is_file() or not _inside(skill_md, root):
                continue
            try:
                frontmatter, _body = _frontmatter(skill_md)
                name = frontmatter.get("name")
                description = frontmatter.get("description")
                if name != child.name or not isinstance(description, str) or not description:
                    raise ValueError("frontmatter name/description invalid")
                skills.append(AgentPluginSkill(name, description, child, skill_md, frontmatter))
            except Exception as exc:
                diagnostics.append(AgentPluginDiagnostic(f"skill:{child.name}", str(exc)))
    mcp: dict[str, dict[str, Any]] = {}
    mcp_file = root / "mcp.json"
    if mcp_file.is_file() and _inside(mcp_file, root):
        raw = _object(mcp_file, "mcp.json")
        servers = raw.get("mcpServers", raw.get("servers", {}))
        if isinstance(servers, dict):
            mcp = {str(k): dict(v) for k, v in servers.items() if isinstance(v, dict)}
    package = manifest.get("package") or {}
    return AgentPluginPackage(
        name=manifest["name"], version=str(manifest.get("version") or ""),
        description=str(manifest.get("description") or ""), root=root,
        data_root=Path(data_root or (root / ".data")), manifest=manifest,
        skills=tuple(skills), mcp_servers=mcp, diagnostics=tuple(diagnostics),
        package=package, exact_ref=str(manifest.get("exact_ref") or package.get("exact_ref") or ""),
        dependencies=dict(manifest.get("dependencies") or {}),
        entry_points=dict(manifest.get("entry_points") or {}),
    )
