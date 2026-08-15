"""Minimal A2A adapter shell; network hosting remains opt-in and external."""
from __future__ import annotations

import os

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter, SendResult

from .security import resolve_bind_host


class A2AAdapter(BasePlatformAdapter):
    def __init__(self, config: PlatformConfig):
        super().__init__(config, Platform("a2a"))
        self.bind_host = resolve_bind_host()
        self.outbox = []

    async def connect(self) -> bool:
        return _enabled()

    async def disconnect(self) -> None:
        return None

    async def get_chat_info(self, chat_id: str) -> dict:
        return {"name": chat_id, "type": "dm"}

    async def send(self, chat_id: str, content: str, reply_to=None, metadata=None) -> SendResult:
        return await self.send_message(chat_id, content, reply_to=reply_to, metadata=metadata)

    async def send_message(self, chat_id: str, text: str, **_kwargs) -> SendResult:
        # Foundation intentionally has no implicit remote transport. Plugin
        # hosts may drain this outbox through an authenticated JSON-RPC server.
        self.outbox.append({"peer": chat_id, "text": text})
        return SendResult(True, message_id=str(len(self.outbox)))


def _enabled() -> bool:
    return os.getenv("A2A_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def register(ctx) -> None:
    ctx.register_platform(
        name="a2a",
        label="Agent-to-Agent (A2A)",
        adapter_factory=lambda cfg: A2AAdapter(cfg),
        check_fn=_enabled,
        is_connected=lambda _cfg: _enabled(),
        emoji="🤝",
    )