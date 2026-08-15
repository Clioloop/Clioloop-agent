"""Modular configuration-default helpers.

The large legacy default mapping still originates in :mod:`clio_cli.config` so
existing imports and downstream monkeypatches remain compatible.  This module
owns additive Phase-1 defaults and returns a defensive merged copy.  New
settings should be added here rather than growing the compatibility mapping.

``DEFAULT_CONFIG`` and the env-var registries are exposed lazily for callers
that import them from this module.  Laziness avoids an import cycle while
preserving object identity with the long-standing ``clio_cli.config`` API.
"""

from __future__ import annotations

import copy
from typing import Any, Dict

# Additive defaults introduced after the compatibility mapping was split.  Keep
# this mapping sparse: the old mapping remains authoritative for existing keys.
ADDITIVE_DEFAULTS: Dict[str, Any] = {
    "state": {
        "migration_backups": True,
        "turn_lease_ttl_seconds": 120,
    },
}


def _deep_fill(target: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
    """Fill absent leaves without replacing compatibility-backed values."""
    for key, value in defaults.items():
        if key not in target:
            target[key] = copy.deepcopy(value)
        elif isinstance(target[key], dict) and isinstance(value, dict):
            _deep_fill(target[key], value)
    return target


def merge_compat_defaults(legacy: Dict[str, Any]) -> Dict[str, Any]:
    """Return a detached default mapping with additive defaults filled in.

    The input is never mutated.  This makes reloads and tests deterministic and
    ensures a caller cannot mutate the compatibility source through an alias.
    """
    if not isinstance(legacy, dict):
        raise TypeError("legacy config defaults must be a mapping")
    return _deep_fill(copy.deepcopy(legacy), ADDITIVE_DEFAULTS)


def __getattr__(name: str):
    """Compatibility-export registries from :mod:`clio_cli.config` lazily."""
    if name in {
        "DEFAULT_CONFIG",
        "ENV_VARS_BY_VERSION",
        "REQUIRED_ENV_VARS",
        "OPTIONAL_ENV_VARS",
    }:
        from clio_cli import config as _config

        return getattr(_config, name)
    raise AttributeError(name)


__all__ = [
    "ADDITIVE_DEFAULTS",
    "DEFAULT_CONFIG",
    "ENV_VARS_BY_VERSION",
    "REQUIRED_ENV_VARS",
    "OPTIONAL_ENV_VARS",
    "merge_compat_defaults",
]
