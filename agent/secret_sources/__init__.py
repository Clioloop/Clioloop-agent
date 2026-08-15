"""External and plugin-provided scoped secret integrations.

Legacy Bitwarden functions remain available from ``.bitwarden``. New providers
implement the read-only, non-interactive :class:`SecretProvider` contract.
"""

from .base import ErrorKind, FetchResult, SecretProvider
from .command import CommandSecretProvider
from .environment import EnvironmentSecretProvider
from .onepassword import OnePasswordSecretProvider
from .registry import get_provider, register_provider, unregister_provider

__all__ = [
    "CommandSecretProvider", "EnvironmentSecretProvider", "ErrorKind",
    "FetchResult", "OnePasswordSecretProvider", "SecretProvider",
    "get_provider", "register_provider", "unregister_provider",
]
