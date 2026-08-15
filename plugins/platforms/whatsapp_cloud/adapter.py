"""Official WhatsApp Cloud API foundation (feature-flagged, no eager I/O)."""
from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any, Mapping, Optional

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter, SendResult

GRAPH_API_BASE = "https://graph.facebook.com"
DEFAULT_API_VERSION = "v20.0"
MAX_WEBHOOK_BYTES = 3 * 1024 * 1024


def feature_enabled(env: Mapping[str, str] = os.environ) -> bool:
    return env.get("WHATSAPP_CLOUD_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def verify_webhook_signature(body: bytes, signature: str, app_secret: str) -> bool:
    """Constant-time verification of Meta's X-Hub-Signature-256 header."""
    if not app_secret or not signature.startswith("sha256=") or len(body) > MAX_WEBHOOK_BYTES:
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature[7:].lower(), expected.lower())


def parse_text_messages(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    """Pure, defensive webhook parser suitable for an aiohttp route wrapper."""
    parsed: list[dict[str, str]] = []
    for entry in payload.get("entry", []) if isinstance(payload, Mapping) else []:
        for change in entry.get("changes", []) if isinstance(entry, Mapping) else []:
            value = change.get("value", {}) if isinstance(change, Mapping) else {}
            for message in value.get("messages", []) if isinstance(value, Mapping) else []:
                if not isinstance(message, Mapping) or message.get("type") != "text":
                    continue
                text = message.get("text") or {}
                body = text.get("body") if isinstance(text, Mapping) else None
                sender = message.get("from")
                message_id = message.get("id")
                if all(isinstance(item, str) and item for item in (sender, message_id, body)):
                    parsed.append({"from": str(sender), "id": str(message_id), "text": str(body)})
    return parsed


class WhatsAppCloudAdapter(BasePlatformAdapter):
    """Outbound seam; webhook hosting is supplied by the gateway plugin host."""

    def __init__(self, config: PlatformConfig, *, http_client: Optional[Any] = None):
        super().__init__(config, Platform("whatsapp_cloud"))
        extra = config.extra or {}
        self.phone_number_id = str(extra.get("phone_number_id") or os.getenv("WHATSAPP_CLOUD_PHONE_NUMBER_ID", ""))
        self.access_token = str(extra.get("access_token") or os.getenv("WHATSAPP_CLOUD_ACCESS_TOKEN", ""))
        self.api_version = str(extra.get("api_version") or DEFAULT_API_VERSION)
        self._http_client = http_client

    async def connect(self) -> bool:
        return feature_enabled() and bool(self.phone_number_id and self.access_token)

    async def disconnect(self) -> None:
        return None

    async def get_chat_info(self, chat_id: str) -> dict[str, Any]:
        return {"name": chat_id, "type": "dm"}

    async def send(self, chat_id: str, content: str, reply_to=None, metadata=None) -> SendResult:
        return await self.send_message(chat_id, content, reply_to=reply_to, metadata=metadata)

    async def send_message(self, chat_id: str, text: str, **_kwargs) -> SendResult:
        if not feature_enabled():
            return SendResult(False, error="WhatsApp Cloud is feature-flagged off")
        if not self.phone_number_id or not self.access_token:
            return SendResult(False, error="WhatsApp Cloud credentials are incomplete")
        client = self._http_client
        owns_client = client is None
        if client is None:
            import httpx
            client = httpx.AsyncClient(timeout=30.0)
        try:
            response = await client.post(
                f"{GRAPH_API_BASE}/{self.api_version}/{self.phone_number_id}/messages",
                headers={"Authorization": f"Bearer {self.access_token}"},
                json={"messaging_product": "whatsapp", "to": chat_id, "type": "text", "text": {"body": text}},
            )
            response.raise_for_status()
            data = response.json()
            ids = data.get("messages") or []
            message_id = ids[0].get("id") if ids and isinstance(ids[0], dict) else None
            return SendResult(True, message_id=message_id, raw_response=data)
        except Exception as exc:
            return SendResult(False, error=str(exc), retryable=True)
        finally:
            if owns_client:
                await client.aclose()


def _configured() -> bool:
    return feature_enabled() and bool(
        os.getenv("WHATSAPP_CLOUD_PHONE_NUMBER_ID") and os.getenv("WHATSAPP_CLOUD_ACCESS_TOKEN")
    )


def register(ctx) -> None:
    ctx.register_platform(
        name="whatsapp_cloud",
        label="WhatsApp Cloud",
        adapter_factory=lambda cfg: WhatsAppCloudAdapter(cfg),
        check_fn=_configured,
        is_connected=lambda _cfg: _configured(),
        required_env=["WHATSAPP_CLOUD_PHONE_NUMBER_ID", "WHATSAPP_CLOUD_ACCESS_TOKEN"],
        allowed_users_env="WHATSAPP_CLOUD_ALLOWED_USERS",
        allow_all_env="WHATSAPP_CLOUD_ALLOW_ALL_USERS",
        emoji="💬",
    )
