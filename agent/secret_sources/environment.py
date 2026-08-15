"""Explicit allowlist adapter over a supplied environment mapping."""
from __future__ import annotations
import os
from pathlib import Path
from typing import Mapping
from .base import ErrorKind, FetchResult, SecretProvider


class EnvironmentSecretProvider(SecretProvider):
    name = "environment"
    scheme = "env"

    def __init__(self, environ: Mapping[str, str] | None = None):
        self.environ = environ if environ is not None else os.environ

    def fetch(self, refs: Mapping[str, str], *, scope: frozenset[str], home: Path) -> FetchResult:
        error = self.validate_scope(refs, scope)
        if error:
            return FetchResult(error=error, error_kind=ErrorKind.REF_INVALID)
        result = {}
        for target, ref in refs.items():
            name = ref.removeprefix("env://")
            if name in self.environ:
                result[target] = self.environ[name]
        return FetchResult(secrets=result)
