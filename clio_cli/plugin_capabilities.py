"""Capability declarations and auditable, fail-closed plugin consent records.

Capabilities constrain host APIs; they are not a Python sandbox. Legacy
``allow_*`` settings remain valid so existing Clio plugins keep working.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class CapabilitySpec:
    id: str
    legacy_path: tuple[str, ...]
    description: str


CAPABILITY_REGISTRY = {
    spec.id: spec for spec in (
        CapabilitySpec("tools.override", ("allow_tool_override",), "Replace a host tool"),
        CapabilitySpec("llm.provider_override", ("llm", "allow_provider_override"), "Select another LLM provider"),
        CapabilitySpec("llm.model_override", ("llm", "allow_model_override"), "Select another LLM model"),
        CapabilitySpec("llm.agent_id_override", ("llm", "allow_agent_id_override"), "Override LLM attribution"),
        CapabilitySpec("llm.profile_override", ("llm", "allow_profile_override"), "Use another auth profile"),
        CapabilitySpec("llm.task_override", ("llm", "allow_task_override"), "Use host auxiliary task lanes"),
        CapabilitySpec("gateway.platform_actions", ("allow_platform_actions",), "Act through a connected platform"),
        CapabilitySpec("secrets.register", ("allow_secret_sources",), "Register a scoped secret provider"),
        CapabilitySpec("network.egress", ("allow_network_egress",), "Request outbound network access"),
        CapabilitySpec("redaction.register", ("allow_redaction_patterns",), "Add safe secret redaction patterns"),
    )
}
VALID_CAPABILITY_IDS = frozenset(CAPABILITY_REGISTRY)


def parse_declared_capabilities(raw: Any, plugin_name: str = "?") -> list[str]:
    if not isinstance(raw, (list, tuple)):
        return []
    return list(dict.fromkeys(x.strip() for x in raw if isinstance(x, str) and x.strip() in VALID_CAPABILITY_IDS))


def capability_set_hash(capabilities: Iterable[str]) -> str:
    canonical = "\n".join(sorted(set(capabilities)))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _entry(plugin_id: str, config: Mapping[str, Any] | None = None) -> dict:
    try:
        if config is None:
            from clio_cli.config import load_config
            config = load_config() or {}
        entry = ((config.get("plugins") or {}).get("entries") or {}).get(plugin_id) or {}
        return entry if isinstance(entry, dict) else {}
    except Exception:
        return {}


def granted_capabilities(plugin_id: str, config: Mapping[str, Any] | None = None) -> frozenset[str]:
    raw = _entry(plugin_id, config).get("granted_capabilities")
    if not isinstance(raw, list):
        return frozenset()
    return frozenset(x for x in raw if isinstance(x, str) and x in VALID_CAPABILITY_IDS)


def _legacy_granted(entry: Mapping[str, Any], path: tuple[str, ...]) -> bool:
    node: Any = entry
    for key in path:
        if not isinstance(node, Mapping):
            return False
        node = node.get(key)
    return node is True


def plugin_capability_granted(plugin_id: str, capability: str, config: Mapping[str, Any] | None = None) -> bool:
    spec = CAPABILITY_REGISTRY.get(capability)
    if spec is None:
        return False
    entry = _entry(plugin_id, config)
    return capability in granted_capabilities(plugin_id, config) or _legacy_granted(entry, spec.legacy_path)


def consent_hash(plugin_id: str, config: Mapping[str, Any] | None = None) -> str | None:
    record = _entry(plugin_id, config).get("capabilities_consent")
    value = record.get("hash") if isinstance(record, dict) else None
    return value if isinstance(value, str) and len(value) == 64 else None


def declared_set_changed(plugin_id: str, declared: Iterable[str], config: Mapping[str, Any] | None = None) -> bool:
    return consent_hash(plugin_id, config) != capability_set_hash(declared)


def pending_capabilities(plugin_id: str, declared: Iterable[str], config: Mapping[str, Any] | None = None) -> list[str]:
    granted = granted_capabilities(plugin_id, config)
    return [cap for cap in declared if cap in VALID_CAPABILITY_IDS and cap not in granted]


def record_consent(plugin_id: str, granted: Iterable[str], declared: Iterable[str]) -> dict:
    """Persist a timestamped record of exactly what the operator reviewed."""
    from clio_cli.config import load_config, save_config
    cfg = load_config() or {}
    plugins = cfg.setdefault("plugins", {})
    entries = plugins.setdefault("entries", {})
    entry = entries.setdefault(plugin_id, {})
    old = set(entry.get("granted_capabilities") or [])
    accepted = {x for x in granted if x in VALID_CAPABILITY_IDS}
    entry["granted_capabilities"] = sorted(old | accepted)
    entry["capabilities_consent"] = {
        "hash": capability_set_hash(declared),
        "granted_at": datetime.now(timezone.utc).isoformat(),
        "declared": sorted(set(declared)),
        "granted": sorted(accepted),
    }
    # Mirror legacy gates while old enforcement sites migrate.
    for cap in accepted:
        node = entry
        path = CAPABILITY_REGISTRY[cap].legacy_path
        for key in path[:-1]:
            node = node.setdefault(key, {})
        node[path[-1]] = True
    save_config(cfg)
    return entry["capabilities_consent"]
