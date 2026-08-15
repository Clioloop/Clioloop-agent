"""1Password CLI adapter for op:// references."""
from __future__ import annotations
import shutil
import subprocess
from pathlib import Path
from typing import Mapping
from .base import ErrorKind, FetchResult, SecretProvider


class OnePasswordSecretProvider(SecretProvider):
    name = "onepassword"
    scheme = "op"

    def __init__(self, binary: str = "op", timeout: float = 15.0):
        self.binary, self.timeout = binary, timeout

    def fetch(self, refs: Mapping[str, str], *, scope: frozenset[str], home: Path) -> FetchResult:
        error = self.validate_scope(refs, scope)
        if error:
            return FetchResult(error=error, error_kind=ErrorKind.REF_INVALID)
        if shutil.which(self.binary) is None:
            return FetchResult(error="1Password CLI is not installed", error_kind=ErrorKind.BINARY_MISSING)
        values = {}
        for target, ref in refs.items():
            if not isinstance(ref, str) or not ref.startswith("op://"):
                return FetchResult(error=f"invalid 1Password reference for {target}", error_kind=ErrorKind.REF_INVALID)
            try:
                run = subprocess.run([self.binary, "read", ref], cwd=home, capture_output=True,
                                     text=True, timeout=self.timeout, shell=False, check=False)
            except subprocess.TimeoutExpired:
                return FetchResult(error="1Password CLI timed out", error_kind=ErrorKind.TIMEOUT)
            except Exception as exc:
                return FetchResult(error=str(exc), error_kind=ErrorKind.INTERNAL)
            if run.returncode:
                return FetchResult(error="1Password CLI could not resolve reference", error_kind=ErrorKind.AUTH_FAILED)
            values[target] = run.stdout.rstrip("\r\n")
        return FetchResult(secrets=values)
