"""Profile-scoped Telegram Bot Room delivery child contracts."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from gateway import profile_telegram_delivery as delivery
from gateway.platforms.base import SendResult
from gateway.platforms.telegram import TelegramAdapter


def test_target_environment_replaces_inherited_controller_token(monkeypatch, tmp_path):
    home = tmp_path / "profiles" / "alpha"
    home.mkdir(parents=True)
    (home / ".env").write_text("TELEGRAM_BOT_TOKEN=target-token\n", encoding="utf-8")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "controller-token")

    delivery._load_target_profile_environment(home)

    assert os.environ["CLIO_HOME"] == str(home)
    assert os.environ["TELEGRAM_BOT_TOKEN"] == "target-token"


def test_target_environment_without_token_fails_closed(monkeypatch, tmp_path):
    home = tmp_path / "profiles" / "alpha"
    home.mkdir(parents=True)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "controller-token")

    delivery._load_target_profile_environment(home)

    assert "TELEGRAM_BOT_TOKEN" not in os.environ


@pytest.mark.anyio
async def test_delivery_uses_adapter_formatting_and_strict_topic_without_mirroring(
    monkeypatch,
    tmp_path,
):
    home = tmp_path / "profiles" / "alpha"
    home.mkdir(parents=True)
    (home / ".env").write_text("TELEGRAM_BOT_TOKEN=target-token\n", encoding="utf-8")
    (home / "config.yaml").write_text("telegram: {}\n", encoding="utf-8")
    captured = {}

    class FakeBot:
        async def initialize(self):
            captured["initialized"] = True

        async def shutdown(self):
            captured["shutdown"] = True

    monkeypatch.setattr(delivery, "_build_bot", lambda _token, _extra: FakeBot())

    async def fake_send(self, chat_id, content, *, metadata=None, **_kwargs):
        captured.update(chat_id=chat_id, content=content, metadata=metadata)
        return SendResult(
            success=True,
            message_id="42",
            raw_response={"thread_fallback": False},
        )

    monkeypatch.setattr(TelegramAdapter, "send", fake_send)

    assert await delivery._deliver(home, "-100200", "9", "reply **with** markdown") is True
    assert captured == {
        "initialized": True,
        "shutdown": True,
        "chat_id": "-100200",
        "content": "reply **with** markdown",
        "metadata": {
            "telegram_strict_thread": True,
            "message_thread_id": "9",
        },
    }


@pytest.mark.anyio
async def test_delivery_rejects_adapter_thread_fallback(monkeypatch, tmp_path):
    home = tmp_path / "profiles" / "alpha"
    home.mkdir(parents=True)
    (home / ".env").write_text("TELEGRAM_BOT_TOKEN=target-token\n", encoding="utf-8")

    class FakeBot:
        async def initialize(self):
            return None

        async def shutdown(self):
            return None

    monkeypatch.setattr(delivery, "_build_bot", lambda _token, _extra: FakeBot())

    async def fake_send(*_args, **_kwargs):
        return SendResult(
            success=True,
            message_id="42",
            raw_response={"thread_fallback": True},
        )

    monkeypatch.setattr(TelegramAdapter, "send", fake_send)

    assert await delivery._deliver(home, "-100200", "9", "reply") is False
