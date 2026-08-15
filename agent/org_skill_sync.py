"""Generic organization-skill synchronization contract.

This module owns no identity provider and no hosted endpoint. Integrations map
their organization, authorization and object store to this small contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Protocol, runtime_checkable


@dataclass(frozen=True)
class OrgSkillRef:
    organization: str
    name: str
    revision: str | None = None

    def __post_init__(self) -> None:
        if not self.organization.strip() or not self.name.strip():
            raise ValueError("organization and skill name are required")


@dataclass(frozen=True)
class OrgSkillObject:
    ref: OrgSkillRef
    files: Mapping[str, bytes]
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OrgSkillChange:
    ref: OrgSkillRef
    base_revision: str | None
    files: Mapping[str, bytes]
    message: str = ""
    idempotency_key: str | None = None


@dataclass(frozen=True)
class OrgSkillSyncResult:
    ref: OrgSkillRef
    status: str
    conflicts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in {"unchanged", "updated", "proposed", "conflict"}:
            raise ValueError(f"unsupported org skill sync status: {self.status}")


@runtime_checkable
class OrgSkillSyncProvider(Protocol):
    """Transport-neutral pull/propose contract; authorization stays server-side."""

    @property
    def name(self) -> str: ...

    def check_requirements(self) -> bool: ...

    def list(self, organization: str) -> Iterable[OrgSkillRef]: ...

    def pull(self, ref: OrgSkillRef) -> OrgSkillObject: ...

    def propose(self, change: OrgSkillChange) -> OrgSkillSyncResult: ...


_PROVIDERS: dict[str, OrgSkillSyncProvider] = {}


def register_org_skill_sync_provider(provider: OrgSkillSyncProvider) -> None:
    if not isinstance(provider, OrgSkillSyncProvider):
        raise TypeError("provider does not satisfy OrgSkillSyncProvider")
    name = str(provider.name or "").strip().lower()
    if not name:
        raise ValueError("org skill sync provider name is required")
    _PROVIDERS[name] = provider


def get_org_skill_sync_provider(name: str) -> OrgSkillSyncProvider | None:
    return _PROVIDERS.get(str(name or "").strip().lower())


def unregister_org_skill_sync_provider(name: str, provider: OrgSkillSyncProvider | None = None) -> bool:
    key = str(name or "").strip().lower()
    current = _PROVIDERS.get(key)
    if current is None or (provider is not None and current is not provider):
        return False
    del _PROVIDERS[key]
    return True
