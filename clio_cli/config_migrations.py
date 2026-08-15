"""Small, table-driven helpers for additive config migrations.

Historical Clio migrations remain callable through ``clio_cli.config``.  This
module provides the registry used by new migrations so future schema changes
are ordered, idempotent, independently testable, and do not materialize the
entire default tree into ``config.yaml``.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Mapping, MutableMapping, Tuple

Config = Dict[str, Any]
MigrationFn = Callable[[MutableMapping[str, Any]], bool]


@dataclass(frozen=True, order=True)
class ConfigMigration:
    """One migration whose version is the schema version after it runs."""

    version: int
    apply: MigrationFn
    name: str = ""


def _phase1_state_defaults(config: MutableMapping[str, Any]) -> bool:
    """Keep v26 additive: defaults are supplied at read time, not persisted.

    The registered no-op intentionally establishes the modular migration
    boundary without rewriting hand-curated existing files.  Returning False
    states that no user-owned value changed; the caller may still update the
    top-level version stamp using its existing compatibility path.
    """
    return False


MIGRATIONS: Tuple[ConfigMigration, ...] = (
    ConfigMigration(27, _phase1_state_defaults, "modular-state-defaults"),
)


def validate_registry(migrations: Iterable[ConfigMigration] = MIGRATIONS) -> None:
    versions = [migration.version for migration in migrations]
    if versions != sorted(versions) or len(versions) != len(set(versions)):
        raise ValueError("config migrations must have unique ascending versions")


def run_additive_migrations(
    current_version: int,
    raw_config: Mapping[str, Any],
    *,
    target_version: int,
    migrations: Iterable[ConfigMigration] = MIGRATIONS,
) -> tuple[Config, tuple[str, ...]]:
    """Apply applicable migrations to a copy and report changed step names.

    Running the function twice is idempotent when migration functions follow
    the contract: only mutate legacy values and return True when they did so.
    Unknown future versions are left untouched.
    """
    ordered = tuple(migrations)
    validate_registry(ordered)
    result: Config = copy.deepcopy(dict(raw_config))
    applied = []
    for migration in ordered:
        if current_version < migration.version <= target_version:
            if migration.apply(result):
                applied.append(migration.name or f"v{migration.version}")
    return result, tuple(applied)


__all__ = [
    "ConfigMigration",
    "MIGRATIONS",
    "run_additive_migrations",
    "validate_registry",
]
