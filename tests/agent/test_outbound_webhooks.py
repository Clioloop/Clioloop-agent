"""Durable signed outbound lifecycle webhook contracts."""

from __future__ import annotations

import hashlib
import hmac
import json
from types import SimpleNamespace

import pytest


def test_lifecycle_webhook_filters_redacts_signs_and_delivers(tmp_path, monkeypatch):
    from agent.outbound_webhooks import LifecycleWebhookManager, OutboundEndpoint

    monkeypatch.setattr("clio_constants.get_clio_home", lambda: tmp_path)
    sent = []
    manager = LifecycleWebhookManager(
        [
            OutboundEndpoint("https://example.invalid/session", frozenset({"on_session_end"})),
            OutboundEndpoint("https://example.invalid/all", frozenset({"*"})),
        ],
        "test-secret",
        sender=lambda url, body, headers: sent.append((url, body, headers)) or 204,
        poll_interval=60,
    )
    try:
        queued = manager.emit(
            "on_session_end",
            {
                "session_id": "s1",
                "api_key": "must-not-persist",
                "message": "token ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890",
                "opaque": SimpleNamespace(value="converted"),
            },
        )
        assert len(queued) == 2
        result = manager.dispatcher.flush(timeout=2, max_items=4)
        assert result["drained"] is True
        assert len(sent) == 2
    finally:
        manager.shutdown(1)

    assert {item[0] for item in sent} == {
        "https://example.invalid/session",
        "https://example.invalid/all",
    }
    for _url, body, headers in sent:
        payload = json.loads(body)
        assert payload["event"] == "on_session_end"
        assert payload["data"]["api_key"] == "[REDACTED]"
        assert payload["data"]["message"] != "token " + "ghp_" + ("A" * 36)
        assert "..." in payload["data"]["message"]
        assert payload["data"]["opaque"]
        assert headers["X-Clio-Event"] == "on_session_end"
        assert headers["X-Clio-Delivery"]
        expected = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
        assert headers["X-Clio-Signature-256"] == "sha256=" + expected
        assert headers["Idempotency-Key"]


def test_event_filter_and_enqueue_idempotency(tmp_path, monkeypatch):
    from agent.outbound_webhooks import LifecycleWebhookManager, OutboundEndpoint

    monkeypatch.setattr("clio_constants.get_clio_home", lambda: tmp_path)
    manager = LifecycleWebhookManager(
        [OutboundEndpoint("https://example.invalid/hook", frozenset({"on_session_start"}))],
        "secret",
        sender=lambda *_args: 204,
        poll_interval=60,
    )
    try:
        assert manager.emit("post_tool_call", {"tool": "read_file"}) == []
        queued = manager.emit("on_session_start", {"session_id": "s1"})
        assert len(queued) == 1
        rows = manager.store.list_webhooks()
        assert len(rows) == 1
        assert rows[0]["id"] == queued[0]
    finally:
        manager.shutdown(1)


def test_disabled_config_has_zero_dispatcher_and_plugin_hook_still_runs(monkeypatch):
    from agent import outbound_webhooks
    from clio_cli import plugins

    monkeypatch.setattr(outbound_webhooks, "_configured", False)
    monkeypatch.setattr(outbound_webhooks, "_manager", None)
    monkeypatch.setattr(outbound_webhooks, "_load_outbound_config", lambda: {})
    assert outbound_webhooks.configure_from_config(force=True) is None

    emitted = []
    plugin_results = ["plugin-result"]
    monkeypatch.setattr(
        plugins,
        "get_plugin_manager",
        lambda: SimpleNamespace(invoke_hook=lambda event, **kwargs: plugin_results),
    )
    monkeypatch.setattr(
        outbound_webhooks,
        "emit_hook_event",
        lambda event, **kwargs: emitted.append((event, kwargs)) or [],
    )
    assert plugins.invoke_hook("on_session_start", session_id="s1") == plugin_results
    assert emitted == [("on_session_start", {"session_id": "s1"})]


def test_outbound_config_coexists_with_shell_hooks_without_warning(caplog):
    from agent.outbound_webhooks import _normalize_endpoints
    from agent.shell_hooks import iter_configured_hooks

    config = {
        "hooks": {
            "outbound": {
                "enabled": True,
                "endpoints": [{"url": "https://events.example/hook"}],
            }
        }
    }
    assert iter_configured_hooks(config) == []
    assert "unknown hook event" not in caplog.text
    endpoints = _normalize_endpoints(config["hooks"]["outbound"])
    assert [endpoint.url for endpoint in endpoints] == ["https://events.example/hook"]


@pytest.mark.parametrize(
    "url",
    [
        "https://user:password@example.invalid/hook",
        "https://example.invalid:bad/hook",
        "file:///tmp/hook",
        "https://example.invalid/hook\nInjected: yes",
    ],
)
def test_webhook_urls_reject_credentials_invalid_ports_and_controls(url, tmp_path):
    from agent.outbound_webhooks import _normalize_endpoints
    from gateway.reliability import ReliabilityStore, SignedWebhookQueue

    assert _normalize_endpoints({"endpoints": [{"url": url}]}) == []
    queue = SignedWebhookQueue(ReliabilityStore(tmp_path / "reliability.db"), "secret")
    with pytest.raises(ValueError, match="valid http"):
        queue.enqueue(url, {"event": "test"}, idempotency_key="one")


def test_signed_webhook_redirect_handler_refuses_redirects():
    from gateway.reliability import _NoWebhookRedirectHandler

    handler = _NoWebhookRedirectHandler()
    redirect = getattr(handler, "redirect_request")
    assert redirect(None, None, 307, "redirect", {}, "https://other.invalid") is None
