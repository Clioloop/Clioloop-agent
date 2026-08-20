"""Opt-in durable outbound lifecycle webhooks.

All Clio lifecycle hooks flow through ``clio_cli.plugins.invoke_hook``. This
module mirrors selected events into the existing durable reliability outbox
without adding a model tool or network activity when disabled.
"""

from __future__ import annotations

import atexit
import os
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class OutboundEndpoint:
    url: str
    events: frozenset[str]

    def accepts(self, event: str) -> bool:
        return not self.events or "*" in self.events or event in self.events


def _sanitize_payload(value: Any, *, depth: int = 0) -> Any:
    """Redact secret keys and token-like strings before durable queueing."""
    from agent.redact import redact_sensitive_text
    from gateway.reliability import redact_payload

    if depth > 8:
        return "[TRUNCATED]"
    value = redact_payload(value)
    if isinstance(value, Mapping):
        return {
            str(key): _sanitize_payload(item, depth=depth + 1)
            for key, item in list(value.items())[:100]
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize_payload(item, depth=depth + 1) for item in list(value)[:100]]
    if isinstance(value, str):
        return redact_sensitive_text(value[:20_000], force=True)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return redact_sensitive_text(str(value)[:20_000], force=True)


class LifecycleWebhookManager:
    def __init__(
        self,
        endpoints: list[OutboundEndpoint],
        secret: str,
        *,
        sender=None,
        poll_interval: float = 0.5,
        batch_size: int = 16,
        max_attempts: int = 8,
    ) -> None:
        from clio_constants import get_clio_home
        from gateway.reliability import (
            OutboundWebhookDispatcher,
            ReliabilityStore,
            SignedWebhookQueue,
        )

        self.endpoints = endpoints
        self.store = ReliabilityStore(get_clio_home() / "gateway" / "reliability.db")
        self.queue = SignedWebhookQueue(self.store, secret)
        self.dispatcher = OutboundWebhookDispatcher(
            self.queue,
            sender=sender,
            poll_interval=poll_interval,
            batch_size=batch_size,
            max_attempts=max_attempts,
        )
        self.dispatcher.start()

    def emit(self, event: str, payload: Mapping[str, Any]) -> list[str]:
        delivery_id = uuid.uuid4().hex
        envelope = {
            "event": event,
            "delivery_id": delivery_id,
            "created_at": time.time(),
            "data": _sanitize_payload(dict(payload)),
        }
        queued: list[str] = []
        for index, endpoint in enumerate(self.endpoints):
            if not endpoint.accepts(event):
                continue
            queued.append(
                self.queue.enqueue(
                    endpoint.url,
                    envelope,
                    idempotency_key=f"{delivery_id}:{index}",
                )
            )
        if queued:
            self.dispatcher.notify()
        return queued

    def shutdown(self, timeout: float = 3.0) -> Mapping[str, int | bool]:
        return self.dispatcher.shutdown(timeout)


_manager_lock = threading.Lock()
_manager: Optional[LifecycleWebhookManager] = None
_configured = False


def _load_outbound_config() -> dict[str, Any]:
    try:
        from clio_cli.config import load_config_readonly

        hooks = (load_config_readonly() or {}).get("hooks")
        if not isinstance(hooks, dict):
            return {}
        outbound = hooks.get("outbound")
        return dict(outbound) if isinstance(outbound, dict) else {}
    except Exception:
        return {}


def _secret_from_config(config: Mapping[str, Any]) -> str:
    env_name = str(config.get("secret_env") or "CLIO_OUTBOUND_WEBHOOK_SECRET").strip()
    value = os.environ.get(env_name, "")
    if value:
        return value
    try:
        from clio_cli.config import load_env

        return str((load_env() or {}).get(env_name) or "")
    except Exception:
        return ""


def _normalize_endpoints(config: Mapping[str, Any]) -> list[OutboundEndpoint]:
    from gateway.reliability import valid_webhook_url

    raw = config.get("endpoints")
    if isinstance(raw, str):
        raw = [{"url": raw}]
    elif isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    endpoints: list[OutboundEndpoint] = []
    for item in raw:
        if isinstance(item, str):
            item = {"url": item}
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not valid_webhook_url(url):
            continue
        events_raw = item.get("events")
        if isinstance(events_raw, str):
            events = frozenset(part.strip() for part in events_raw.split(",") if part.strip())
        elif isinstance(events_raw, list):
            events = frozenset(str(part).strip() for part in events_raw if str(part).strip())
        else:
            events = frozenset()
        endpoints.append(OutboundEndpoint(url=url, events=events))
    return endpoints


def configure_from_config(*, force: bool = False, sender=None) -> Optional[LifecycleWebhookManager]:
    """Build the process-local dispatcher once; disabled config is a no-op."""
    global _configured, _manager
    with _manager_lock:
        if _configured and not force:
            return _manager
        if _manager is not None:
            _manager.shutdown(1.0)
            _manager = None
        _configured = True
        config = _load_outbound_config()
        if config.get("enabled") is not True:
            return None
        endpoints = _normalize_endpoints(config)
        secret = _secret_from_config(config)
        if not endpoints or not secret:
            return None
        try:
            poll_interval = max(0.05, float(config.get("poll_interval", 0.5)))
            batch_size = max(1, min(int(config.get("batch_size", 16)), 128))
            max_attempts = max(1, min(int(config.get("max_attempts", 8)), 32))
        except (TypeError, ValueError):
            return None
        _manager = LifecycleWebhookManager(
            endpoints,
            secret,
            sender=sender,
            poll_interval=poll_interval,
            batch_size=batch_size,
            max_attempts=max_attempts,
        )
        return _manager


def emit_hook_event(event: str, **payload: Any) -> list[str]:
    """Queue one redacted hook event; never fail the agent path."""
    try:
        manager = configure_from_config()
        return manager.emit(str(event), payload) if manager is not None else []
    except Exception:
        return []


def shutdown_outbound_webhooks() -> None:
    global _manager
    with _manager_lock:
        manager, _manager = _manager, None
    if manager is not None:
        try:
            manager.shutdown(3.0)
        except Exception:
            pass


atexit.register(shutdown_outbound_webhooks)
