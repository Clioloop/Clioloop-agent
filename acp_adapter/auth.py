"""ACP authentication helpers."""

from __future__ import annotations

from acp.schema import AuthMethodAgent, TerminalAuthMethod

TERMINAL_SETUP_AUTH_METHOD_ID = "terminal-setup"
_TERMINAL_DESCRIPTION = (
    "Open Clio' interactive model/provider setup in a terminal. "
    "Use this when Clio has not been configured on this machine yet."
)


def detect_provider() -> str | None:
    try:
        from clio_cli.runtime_provider import resolve_runtime_provider

        runtime = resolve_runtime_provider()
    except Exception:
        return None
    provider = str((runtime or {}).get("provider") or "").strip().lower()
    api_key = str((runtime or {}).get("api_key") or "").strip()
    if not provider or not api_key:
        return None
    return provider


def has_provider() -> bool:
    return detect_provider() is not None


def build_auth_methods():
    provider = detect_provider()
    terminal = TerminalAuthMethod(
        id=TERMINAL_SETUP_AUTH_METHOD_ID,
        name="Configure Clio provider",
        description=_TERMINAL_DESCRIPTION,
        args=["--setup"],
        type="terminal",
    )
    if not provider:
        return [terminal]
    return [
        AuthMethodAgent(
            id=provider,
            name=f"{provider} runtime credentials",
            description="Use the model/provider credentials already configured for Clio.",
        ),
        terminal,
    ]
