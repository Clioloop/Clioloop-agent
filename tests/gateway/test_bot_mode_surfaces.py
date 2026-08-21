"""Cross-surface Bot Mode RPC and gateway command contracts."""

from __future__ import annotations

from dataclasses import asdict
from types import SimpleNamespace
from typing import Any

import pytest

import clio_bot_mode
from clio_bot_mode import RoomTurnResult
from clio_cli.commands import resolve_command
from gateway.platforms.base import MessageEvent, MessageType, Platform
from gateway.run import GatewayRunner
from gateway.session import SessionSource
from tui_gateway import server


def rpc(method: str, params: dict | None = None) -> dict:
    response = server.handle_request({"id": method, "method": method, "params": params or {}})
    assert response is not None
    return response


def test_tui_rpc_exposes_complete_bot_room_lifecycle(monkeypatch):
    room = {"id": "room-1", "name": "Review", "members": []}
    monkeypatch.setattr(clio_bot_mode, "list_rooms", lambda: [room])
    monkeypatch.setattr(clio_bot_mode, "create_room", lambda name, members: {**room, "name": name, "members": members})
    monkeypatch.setattr(clio_bot_mode, "get_room", lambda room_id: {**room, "id": room_id})
    monkeypatch.setattr(clio_bot_mode, "delete_room", lambda room_id: room_id == "room-1")
    turn = RoomTurnResult(
        room_id="room-1",
        epoch=2,
        rounds=1,
        state="settled",
        needs_user=False,
        messages=[{"author": "user", "content": "review"}],
        suppressed=1,
        activity=[],
    )
    monkeypatch.setattr(clio_bot_mode, "send_room_message", lambda *_args, **_kwargs: turn)
    monkeypatch.setattr(
        clio_bot_mode,
        "respond_room_user_action",
        lambda room_id, request_id, response, **_kwargs: {
            "room_id": room_id,
            "request_id": request_id,
            "response": response,
            "accepted": True,
        },
    )

    assert rpc("bot.rooms.list")["result"]["rooms"][0]["id"] == "room-1"
    assert rpc("bot.rooms.create", {"name": "New", "members": ["alpha", "beta"]})["result"]["room"]["name"] == "New"
    assert rpc("bot.rooms.get", {"room_id": "room-1"})["result"]["room"]["id"] == "room-1"
    assert rpc("bot.rooms.send", {"room_id": "room-1", "message": "review"})["result"] == asdict(turn)
    assert rpc(
        "bot.rooms.respond",
        {
            "room_id": "room-1",
            "request_id": "ask-1",
            "response": "once",
            "epoch": 2,
            "session_id": "session-alpha",
        },
    )["result"]["accepted"] is True
    assert rpc("bot.rooms.delete", {"room_id": "room-1"})["result"]["deleted"] is True


def test_botroom_is_central_gateway_command():
    command = resolve_command("botroom")
    assert command is not None
    assert command.gateway_only is True
    assert {"list", "create", "show", "send", "delete"} <= set(command.subcommands)


@pytest.mark.anyio
async def test_gateway_botroom_send_returns_only_visible_attributed_messages(monkeypatch):
    turn = RoomTurnResult(
        room_id="room-1",
        epoch=1,
        rounds=2,
        state="settled",
        needs_user=False,
        messages=[
            {"author": "user", "content": "review"},
            {"author": "alpha", "content": "finding"},
        ],
        suppressed=3,
        activity=[{"state": "failed", "error": "private"}],
    )
    monkeypatch.setattr(clio_bot_mode, "send_room_message", lambda *_args, **_kwargs: turn)
    runner: Any = GatewayRunner.__new__(GatewayRunner)
    event: Any = SimpleNamespace(text="/botroom send room-1 | review")
    result = await runner._handle_botroom_command(event)
    assert "[alpha] finding" in result
    assert "3 pass/duplicate/failed" in result
    assert "private" not in result


def _telegram_group_event(text: str, *, message_type=MessageType.TEXT, raw_message=None) -> MessageEvent:
    return MessageEvent(
        text=text,
        message_type=message_type,
        source=SessionSource(
            platform=Platform.TELEGRAM,
            chat_id="-200",
            chat_type="group",
            user_id="111",
            user_name="User",
            thread_id="9",
        ),
        raw_message=raw_message,
    )


def test_gateway_resolves_only_plain_bound_telegram_group_messages():
    runner: Any = GatewayRunner.__new__(GatewayRunner)
    adapter = SimpleNamespace(
        bot_room_binding_for_chat=lambda chat_id: {
            "room_id": "room-1",
            "controller_handle": "clio",
        } if str(chat_id) == "-200" else None
    )
    runner.adapters = {Platform.TELEGRAM: adapter}

    assert runner._telegram_bot_room_binding_for_event(_telegram_group_event("hello")) == {
        "room_id": "room-1",
        "controller_handle": "clio",
    }
    assert runner._telegram_bot_room_binding_for_event(
        _telegram_group_event("/status", message_type=MessageType.COMMAND)
    ) is None
    dm = _telegram_group_event("hello")
    dm.source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="-200",
        chat_type="dm",
        user_id="111",
    )
    assert runner._telegram_bot_room_binding_for_event(dm) is None


@pytest.mark.anyio
async def test_bound_telegram_room_routes_plain_text_media_and_formats_only_visible_bots(
    monkeypatch,
    tmp_path,
):
    image = tmp_path / "review.png"
    image.write_bytes(b"png")
    captured: dict[str, Any] = {}
    room = {
        "id": "room-1",
        "members": [{"handle": "clio"}, {"handle": "reviewer"}],
    }
    monkeypatch.setattr(clio_bot_mode, "get_room", lambda room_id: room)

    def send(room_id, message, **kwargs):
        captured.update(room_id=room_id, message=message, kwargs=kwargs)
        return RoomTurnResult(
            room_id=room_id,
            epoch=1,
            rounds=2,
            state="settled",
            needs_user=False,
            messages=[
                {"author": "user", "content": message},
                {"author": "clio", "content": "Initial answer"},
                {"author": "reviewer", "content": "Cross-check"},
            ],
            suppressed=2,
            activity=[{"state": "failed", "error": "private path"}],
        )

    monkeypatch.setattr(clio_bot_mode, "send_room_message", send)
    runner: Any = GatewayRunner.__new__(GatewayRunner)
    runner.adapters = {
        Platform.TELEGRAM: SimpleNamespace(_message_mentions_bot=lambda _raw: False)
    }
    event = _telegram_group_event("review this")
    event.media_urls = [str(image), str(tmp_path / "ignored.mp3")]
    event.media_types = ["image/png", "audio/mpeg"]

    result = await runner._handle_bound_telegram_bot_room_message(
        event,
        {"room_id": "room-1", "controller_handle": "clio"},
    )

    assert captured["room_id"] == "room-1"
    assert captured["message"] == "review this"
    assert captured["kwargs"]["thread_id"] == "9"
    assert captured["kwargs"]["attachments"] == [
        {"path": str(image), "name": "review.png", "mime_type": "image/png"}
    ]
    assert result == "[clio] Initial answer\n\n[reviewer] Cross-check"
    assert "private path" not in result


@pytest.mark.anyio
async def test_bound_telegram_controller_mention_selects_only_controller(monkeypatch):
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        clio_bot_mode,
        "get_room",
        lambda _room_id: {
            "id": "room-1",
            "members": [{"handle": "clio"}, {"handle": "reviewer"}],
        },
    )

    def send(room_id, message, **_kwargs):
        captured["message"] = message
        return RoomTurnResult(room_id, 1, 1, "settled", False, [], 0, [])

    monkeypatch.setattr(clio_bot_mode, "send_room_message", send)
    runner: Any = GatewayRunner.__new__(GatewayRunner)
    runner.adapters = {
        Platform.TELEGRAM: SimpleNamespace(_message_mentions_bot=lambda _raw: True)
    }
    event = _telegram_group_event("please answer", raw_message=object())

    assert await runner._handle_bound_telegram_bot_room_message(
        event,
        {"room_id": "room-1", "controller_handle": "clio"},
    ) == ""
    assert captured["message"] == "@clio please answer"


@pytest.mark.anyio
async def test_bound_telegram_room_suppresses_superseded_turn(monkeypatch):
    monkeypatch.setattr(
        clio_bot_mode,
        "get_room",
        lambda _room_id: {"id": "room-1", "members": [{"handle": "clio"}]},
    )
    monkeypatch.setattr(
        clio_bot_mode,
        "send_room_message",
        lambda room_id, _message, **_kwargs: RoomTurnResult(
            room_id,
            2,
            1,
            "superseded",
            False,
            [{"author": "clio", "content": "stale"}],
            0,
            [],
        ),
    )
    runner: Any = GatewayRunner.__new__(GatewayRunner)
    runner.adapters = {
        Platform.TELEGRAM: SimpleNamespace(_message_mentions_bot=lambda _raw: False)
    }

    assert await runner._handle_bound_telegram_bot_room_message(
        _telegram_group_event("newer wins"),
        {"room_id": "room-1"},
    ) == ""
