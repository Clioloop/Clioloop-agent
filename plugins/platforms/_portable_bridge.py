"""Shared no-network foundation for optional bridge-style platforms."""
from __future__ import annotations

from typing import Any
from gateway.config import Platform
from gateway.platforms.base import BasePlatformAdapter, SendResult


class PortableBridgeAdapter(BasePlatformAdapter):
    """Lifecycle/outbox shell. Concrete integrations may attach a sidecar.

    The foundation never opens a remote connection by itself; this makes plugin
    discovery and requirement checks safe and permits transport-mocked tests.
    """
    platform_name = "bridge"

    def __init__(self, config):
        super().__init__(config, Platform(self.platform_name))
        self.outbox: list[dict[str, Any]] = []

    async def connect(self) -> bool:
        self._running = True
        self._mark_connected()
        return True

    async def disconnect(self) -> None:
        self._running = False
        self._mark_disconnected()

    async def send(self, chat_id: str, content: str, reply_to=None, metadata=None) -> SendResult:
        item = {"chat_id": str(chat_id), "content": str(content), "reply_to": reply_to,
                "metadata": dict(metadata or {})}
        self.outbox.append(item)
        return SendResult(success=True, message_id=str(len(self.outbox)))

    async def get_chat_info(self, chat_id: str) -> dict[str, Any]:
        return {"name": str(chat_id), "type": "channel"}
