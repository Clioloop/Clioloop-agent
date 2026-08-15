"""Scoped, synchronous and non-interactive secret-provider contract."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Mapping

SECRET_PROVIDER_API_VERSION = 1


class ErrorKind(str, Enum):
    NOT_CONFIGURED = "not_configured"
    BINARY_MISSING = "binary_missing"
    AUTH_FAILED = "auth_failed"
    REF_INVALID = "ref_invalid"
    TIMEOUT = "timeout"
    INTERNAL = "internal"


@dataclass
class FetchResult:
    secrets: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    error_kind: ErrorKind | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


class SecretProvider(ABC):
    """Read-only provider. Values may only be returned inside declared scope."""
    api_version = SECRET_PROVIDER_API_VERSION
    name = ""
    scheme: str | None = None

    @abstractmethod
    def fetch(self, refs: Mapping[str, str], *, scope: frozenset[str], home: Path) -> FetchResult:
        """Resolve env-name to provider-ref mappings without raising/prompting."""

    @staticmethod
    def validate_scope(refs: Mapping[str, str], scope: frozenset[str]) -> str | None:
        outside = sorted(set(refs) - set(scope))
        return f"secret request exceeds scope: {', '.join(outside)}" if outside else None
