"""Optional Raft content-free wake bridge foundation."""
from __future__ import annotations
import os
import shutil
from typing import Any
from plugins.platforms._portable_bridge import PortableBridgeAdapter

_CONTENT_FIELDS = frozenset({"text", "body", "content", "message", "messages", "sender", "channel"})


def has_content_field(value: Any) -> bool:
    if isinstance(value, dict):
        return any(str(k).lower() in _CONTENT_FIELDS or has_content_field(v) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return any(has_content_field(v) for v in value)
    return False


class RaftAdapter(PortableBridgeAdapter):
    platform_name = "raft"

    async def accept_wake(self, payload: dict[str, Any]) -> bool:
        """Accept only content-free metadata; the agent reads bodies via Raft CLI."""
        if has_content_field(payload):
            return False
        event_id = str(payload.get("eventId") or payload.get("event_id") or "wake")
        self.outbox.append({"wake": event_id, "metadata": dict(payload)})
        return True


def validate_config(cfg) -> bool:
    return bool(os.getenv("RAFT_PROFILE") or (getattr(cfg, "extra", {}) or {}).get("profile"))


def check_requirements() -> bool:
    return bool(os.getenv("RAFT_PROFILE") and shutil.which(os.getenv("RAFT_CLI_PATH", "raft")))


def _env_enablement():
    profile = os.getenv("RAFT_PROFILE", "").strip()
    return {"profile": profile} if profile else None


def register(ctx) -> None:
    ctx.register_platform(
        name="raft", label="Raft", adapter_factory=RaftAdapter,
        check_fn=check_requirements, validate_config=validate_config,
        is_connected=validate_config, required_env=["RAFT_PROFILE"],
        install_hint="Install and authenticate the Raft CLI",
        env_enablement_fn=_env_enablement, emoji="🛶",
        platform_hint="A content-free Raft wake was received. Use the authenticated Raft CLI to read or send message bodies.",
    )
