"""Non-shell command adapter: command stdout resolves one scoped secret."""
from __future__ import annotations
import os
import shlex
import subprocess
from pathlib import Path
from typing import Mapping, Sequence
from .base import ErrorKind, FetchResult, SecretProvider


class CommandSecretProvider(SecretProvider):
    name = "command"
    scheme = "cmd"

    def __init__(self, command: Sequence[str] | None = None, timeout: float = 10.0):
        self.command = tuple(command or ())
        self.timeout = timeout

    def fetch(self, refs: Mapping[str, str], *, scope: frozenset[str], home: Path) -> FetchResult:
        error = self.validate_scope(refs, scope)
        if error:
            return FetchResult(error=error, error_kind=ErrorKind.REF_INVALID)
        output = {}
        safe_env = {k: v for k, v in os.environ.items() if k in {"PATH", "HOME", "USER", "TMPDIR", "SYSTEMROOT"}}
        for target, ref in refs.items():
            argv = self.command or tuple(shlex.split(ref.removeprefix("cmd://")))
            if not argv:
                return FetchResult(error="empty secret command", error_kind=ErrorKind.NOT_CONFIGURED)
            try:
                run = subprocess.run(argv, cwd=home, env=safe_env, capture_output=True, text=True,
                                     timeout=self.timeout, shell=False, check=False)
            except FileNotFoundError:
                return FetchResult(error=f"secret command not found: {argv[0]}", error_kind=ErrorKind.BINARY_MISSING)
            except subprocess.TimeoutExpired:
                return FetchResult(error="secret command timed out", error_kind=ErrorKind.TIMEOUT)
            except Exception as exc:
                return FetchResult(error=str(exc), error_kind=ErrorKind.INTERNAL)
            if run.returncode:
                return FetchResult(error=f"secret command exited {run.returncode}", error_kind=ErrorKind.AUTH_FAILED)
            output[target] = run.stdout.rstrip("\r\n")
        return FetchResult(secrets=output)
