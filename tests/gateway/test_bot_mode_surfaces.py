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
from gateway.run import GatewayRunner, _profile_bot_delivery_env
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
async def test_bound_telegram_profile_username_maps_to_internal_room_handle(monkeypatch):
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
        captured.update(room_id=room_id, message=message)
        return RoomTurnResult(room_id, 1, 1, "settled", False, [], 0, [])

    monkeypatch.setattr(clio_bot_mode, "send_room_message", send)
    runner: Any = GatewayRunner.__new__(GatewayRunner)
    runner.adapters = {
        Platform.TELEGRAM: SimpleNamespace(_message_mentions_bot=lambda _raw: False)
    }

    assert await runner._handle_bound_telegram_bot_room_message(
        _telegram_group_event("@Review_Profile_Bot inspect this"),
        {
            "room_id": "room-1",
            "profile_bot_usernames": {"reviewer": "Review_Profile_Bot"},
        },
    ) == ""
    assert captured["message"] == "@reviewer inspect this"


@pytest.mark.anyio
async def test_bound_telegram_controller_and_profile_username_select_both(monkeypatch):
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
        captured.update(room_id=room_id, message=message)
        return RoomTurnResult(room_id, 1, 1, "settled", False, [], 0, [])

    monkeypatch.setattr(clio_bot_mode, "send_room_message", send)
    runner: Any = GatewayRunner.__new__(GatewayRunner)
    runner.adapters = {
        Platform.TELEGRAM: SimpleNamespace(_message_mentions_bot=lambda _raw: True)
    }

    assert await runner._handle_bound_telegram_bot_room_message(
        _telegram_group_event("@Review_Profile_Bot investigate", raw_message=object()),
        {
            "room_id": "room-1",
            "controller_handle": "clio",
            "profile_bot_usernames": {"reviewer": "Review_Profile_Bot"},
        },
    ) == ""
    assert captured["message"] == "@clio @reviewer investigate"


@pytest.mark.anyio
async def test_bound_telegram_stale_profile_username_mapping_fails_closed(monkeypatch):
    monkeypatch.setattr(
        clio_bot_mode,
        "get_room",
        lambda _room_id: {"id": "room-1", "members": [{"handle": "clio"}]},
    )

    def unexpected_send(*_args, **_kwargs):
        raise AssertionError("invalid alias mapping must not fan out to the room")

    monkeypatch.setattr(clio_bot_mode, "send_room_message", unexpected_send)
    runner: Any = GatewayRunner.__new__(GatewayRunner)
    runner.adapters = {
        Platform.TELEGRAM: SimpleNamespace(_message_mentions_bot=lambda _raw: False)
    }

    notice = await runner._handle_bound_telegram_bot_room_message(
        _telegram_group_event("@Review_Profile_Bot inspect this"),
        {
            "room_id": "room-1",
            "profile_bot_usernames": {"reviewer": "Review_Profile_Bot"},
        },
    )
    assert "binding is invalid" in notice


def test_telegram_room_mention_rewrite_is_boundary_safe():
    runner: Any = GatewayRunner.__new__(GatewayRunner)
    text = (
        "email x@Review_Profile_Bot.example and /status@Review_Profile_Bot "
        "then @Review_Profile_Bot"
    )

    assert runner._rewrite_telegram_room_mentions(
        text,
        {"Review_Profile_Bot": "reviewer"},
    ) == (
        "email x@Review_Profile_Bot.example and /status@Review_Profile_Bot "
        "then @reviewer"
    )


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


@pytest.mark.anyio
async def test_profile_bot_delivery_uses_selected_profile_and_stdin(monkeypatch, tmp_path):
    captured: dict[str, Any] = {}

    class FakeProcess:
        returncode = 0

        async def communicate(self, payload):
            captured["payload"] = payload
            return None, None

    async def fake_create(*command, **kwargs):
        captured["command"] = list(command)
        captured["kwargs"] = kwargs
        return FakeProcess()

    target_home = tmp_path / "custom-root" / "profiles" / "alpha"
    target_home.mkdir(parents=True)
    monkeypatch.setenv("CLIO_HOME", "/controller")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "controller-token")
    monkeypatch.setenv("OPENAI_API_KEY", "controller-key")
    monkeypatch.setenv("CLIO_BOT_HANDOFF_TOKEN", "handoff-token")
    monkeypatch.setenv("PYTHONPATH", "/untrusted/imports")
    monkeypatch.setenv("HTTPS_PROXY", "http://user:secret@proxy.invalid")
    monkeypatch.setenv("PATH", "/safe/path")
    monkeypatch.setattr(clio_bot_mode, "profile_home", lambda _profile: target_home)
    monkeypatch.setattr("gateway.run.asyncio.create_subprocess_exec", fake_create)

    runner: Any = GatewayRunner.__new__(GatewayRunner)
    content = 'reply with "quotes" and $(shell)\nsecond line'
    assert await runner._send_telegram_room_reply_as_profile(
        profile="alpha",
        chat_id="-200",
        thread_id="9",
        content=content,
    ) is True

    command = captured["command"]
    assert command[1:3] == ["-m", "gateway.profile_telegram_delivery"]
    assert command[3:] == [
        "--clio-home",
        str(target_home.resolve()),
        "--chat-id",
        "-200",
        "--thread-id",
        "9",
    ]
    assert content not in " ".join(command)
    assert captured["payload"] == content.encode("utf-8")
    child_env = captured["kwargs"]["env"]
    assert child_env["PATH"] == "/safe/path"
    assert child_env["CLIO_HOME"] == str(target_home.resolve())
    assert "TELEGRAM_BOT_TOKEN" not in child_env
    assert "OPENAI_API_KEY" not in child_env
    assert "CLIO_BOT_HANDOFF_TOKEN" not in child_env
    assert "PYTHONPATH" not in child_env
    assert "HTTPS_PROXY" not in child_env


def test_profile_bot_delivery_env_preserves_runtime_but_strips_credentials(monkeypatch, tmp_path):
    target_home = tmp_path / "profiles" / "alpha"
    target_home.mkdir(parents=True)
    monkeypatch.setenv("HOME", "/home/tester")
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.setenv("CUSTOM_SESSION_COOKIE", "secret")
    monkeypatch.setenv("TELEGRAM_PROXY", "socks5://secret")

    child = _profile_bot_delivery_env(target_home)

    assert child["HOME"] == "/home/tester"
    assert child["LANG"] == "C.UTF-8"
    assert child["CLIO_HOME"] == str(target_home.resolve())
    assert "CUSTOM_SESSION_COOKIE" not in child
    assert "TELEGRAM_PROXY" not in child


@pytest.mark.anyio
async def test_bound_room_profile_delivery_posts_each_reply_as_its_own_bot(monkeypatch):
    room = {
        "id": "room-1",
        "active_epoch": 7,
        "members": [
            {"handle": "clio", "profile": "default", "source": "local"},
            {"handle": "reviewer", "profile": "reviewer", "source": "local"},
        ],
    }
    turn = RoomTurnResult(
        "room-1",
        7,
        1,
        "settled",
        False,
        [
            {
                "author": "clio",
                "profile": "default",
                "source": "local",
                "content": "@reviewer First",
            },
            {
                "author": "reviewer",
                "profile": "reviewer",
                "source": "local",
                "content": "@clio Second",
            },
        ],
        0,
        [],
    )
    monkeypatch.setattr(clio_bot_mode, "get_room", lambda _room_id: room)
    monkeypatch.setattr(clio_bot_mode, "send_room_message", lambda *_args, **_kwargs: turn)
    delivered: list[dict[str, Any]] = []

    async def fake_send(**kwargs):
        delivered.append(kwargs)
        return True

    runner: Any = GatewayRunner.__new__(GatewayRunner)
    runner.adapters = {Platform.TELEGRAM: SimpleNamespace(_message_mentions_bot=lambda _raw: False)}
    runner._send_telegram_room_reply_as_profile = fake_send

    result = await runner._handle_bound_telegram_bot_room_message(
        _telegram_group_event("review"),
        {
            "room_id": "room-1",
            "delivery": "profile_bots",
            "profile_bot_usernames": {
                "clio": "Controller_Profile_Bot",
                "reviewer": "Review_Profile_Bot",
            },
            "render_profile_bot_mentions": True,
        },
    )

    assert result == ""
    assert [item["profile"] for item in delivered] == ["default", "reviewer"]
    assert [item["content"] for item in delivered] == [
        "@Review_Profile_Bot First",
        "@Controller_Profile_Bot Second",
    ]
    assert all(item["chat_id"] == "-200" and item["thread_id"] == "9" for item in delivered)


@pytest.mark.anyio
async def test_bound_room_streams_tool_names_from_profile_bot_without_reasoning(monkeypatch):
    room = {
        "id": "room-1",
        "active_epoch": 8,
        "members": [
            {"handle": "reviewer", "profile": "reviewer", "source": "local"},
        ],
    }
    captured = {}

    def send_room(room_id, _message, **kwargs):
        captured["hard_timeout"] = kwargs["hard_timeout"]
        callback = kwargs["progress_callback"]
        member = room["members"][0]
        callback(member, {"event": "tool.started", "name": "search_files"})
        callback(
            member,
            {
                "event": "tool.completed",
                "name": "search_files",
                "duration": 4.2,
                "is_error": False,
            },
        )
        callback(member, {"event": "reasoning.available", "name": "_thinking"})
        callback(member, {"event": "tool.started", "name": "terminal"})
        callback(
            member,
            {
                "event": "tool.completed",
                "name": "terminal",
                "duration": 1.0,
                "is_error": True,
            },
        )
        return RoomTurnResult(room_id, 8, 1, "settled", False, [], 0, [])

    monkeypatch.setattr(clio_bot_mode, "get_room", lambda _room_id: room)
    monkeypatch.setattr(clio_bot_mode, "send_room_message", send_room)
    delivered = []

    async def fake_send(**kwargs):
        delivered.append(kwargs)
        return True

    runner: Any = GatewayRunner.__new__(GatewayRunner)
    runner.adapters = {Platform.TELEGRAM: SimpleNamespace(_message_mentions_bot=lambda _raw: False)}
    runner._send_telegram_room_reply_as_profile = fake_send

    result = await runner._handle_bound_telegram_bot_room_message(
        _telegram_group_event("@reviewer inspect"),
        {
            "room_id": "room-1",
            "show_tool_progress": True,
            "turn_timeout_seconds": 1800.0,
        },
    )

    assert result == ""
    assert captured["hard_timeout"] == 1800.0
    assert [item["profile"] for item in delivered] == ["reviewer", "reviewer", "reviewer"]
    assert [item["content"] for item in delivered] == [
        "🛠 Using tool: `search_files`",
        "🛠 Using tool: `terminal`",
        "⚠ Tool failed: `terminal`",
    ]
    assert all("reason" not in item["content"].lower() for item in delivered)


@pytest.mark.anyio
async def test_bound_room_profile_delivery_failure_notice_never_impersonates_reply(monkeypatch):
    room = {
        "id": "room-1",
        "active_epoch": 4,
        "members": [{"handle": "alpha", "profile": "alpha", "source": "local"}],
    }
    turn = RoomTurnResult(
        "room-1",
        4,
        1,
        "settled",
        False,
        [
            {
                "author": "alpha",
                "profile": "alpha",
                "source": "local",
                "content": "private failed reply",
            }
        ],
        0,
        [{"state": "failed", "error": "private backend detail"}],
    )
    monkeypatch.setattr(clio_bot_mode, "get_room", lambda _room_id: room)
    monkeypatch.setattr(clio_bot_mode, "send_room_message", lambda *_args, **_kwargs: turn)
    runner: Any = GatewayRunner.__new__(GatewayRunner)
    runner.adapters = {Platform.TELEGRAM: SimpleNamespace(_message_mentions_bot=lambda _raw: False)}

    async def fail_delivery(**_kwargs):
        return False

    runner._send_telegram_room_reply_as_profile = fail_delivery
    notice = await runner._handle_bound_telegram_bot_room_message(
        _telegram_group_event("review"),
        {"room_id": "room-1", "delivery": "profile_bots"},
    )

    assert "@alpha" in notice
    assert "private failed reply" not in notice
    assert "private backend detail" not in notice
    assert "[alpha]" not in notice


@pytest.mark.anyio
async def test_profile_delivery_fails_closed_without_impersonating_remote_or_failed_bots(monkeypatch):
    room = {
        "id": "room-1",
        "active_epoch": 3,
        "members": [
            {"handle": "alpha", "profile": "alpha", "source": "local"},
            {"handle": "remote", "profile": "remote", "source": "peer"},
        ],
    }
    monkeypatch.setattr(clio_bot_mode, "get_room", lambda _room_id: room)
    attempts: list[str] = []

    async def fake_send(**kwargs):
        attempts.append(kwargs["profile"])
        return False

    runner: Any = GatewayRunner.__new__(GatewayRunner)
    runner._send_telegram_room_reply_as_profile = fake_send
    result = SimpleNamespace(room_id="room-1", epoch=3)
    failures, superseded = await runner._deliver_telegram_room_replies_as_profiles(
        room=room,
        result=result,
        messages=[
            {"author": "alpha", "profile": "alpha", "source": "local", "content": "private-a"},
            {"author": "remote", "profile": "remote", "source": "peer", "content": "private-b"},
        ],
        chat_id="-200",
        thread_id=None,
    )

    assert superseded is False
    assert failures == ["alpha", "remote"]
    assert attempts == ["alpha"]


@pytest.mark.anyio
async def test_profile_delivery_stops_before_stale_epoch(monkeypatch):
    room = {
        "id": "room-1",
        "active_epoch": 5,
        "members": [{"handle": "alpha", "profile": "alpha", "source": "local"}],
    }
    monkeypatch.setattr(
        clio_bot_mode,
        "get_room",
        lambda _room_id: {**room, "active_epoch": 6},
    )
    runner: Any = GatewayRunner.__new__(GatewayRunner)

    async def unexpected_send(**_kwargs):
        raise AssertionError("stale replies must not be delivered")

    runner._send_telegram_room_reply_as_profile = unexpected_send
    failures, superseded = await runner._deliver_telegram_room_replies_as_profiles(
        room=room,
        result=SimpleNamespace(room_id="room-1", epoch=5),
        messages=[
            {"author": "alpha", "profile": "alpha", "source": "local", "content": "stale"}
        ],
        chat_id="-200",
        thread_id=None,
    )

    assert failures == []
    assert superseded is True


@pytest.mark.anyio
async def test_profile_delivery_rechecks_epoch_after_inflight_send(monkeypatch):
    epoch = {"value": 5}
    room = {
        "id": "room-1",
        "active_epoch": 5,
        "members": [{"handle": "alpha", "profile": "alpha", "source": "local"}],
    }
    monkeypatch.setattr(
        clio_bot_mode,
        "get_room",
        lambda _room_id: {**room, "active_epoch": epoch["value"]},
    )
    runner: Any = GatewayRunner.__new__(GatewayRunner)
    attempts = {"count": 0}

    async def superseding_send(**_kwargs):
        attempts["count"] += 1
        epoch["value"] = 6
        return True

    runner._send_telegram_room_reply_as_profile = superseding_send
    failures, superseded = await runner._deliver_telegram_room_replies_as_profiles(
        room=room,
        result=SimpleNamespace(room_id="room-1", epoch=5),
        messages=[
            {"author": "alpha", "profile": "alpha", "source": "local", "content": "old"},
            {"author": "alpha", "profile": "alpha", "source": "local", "content": "older"},
        ],
        chat_id="-200",
        thread_id=None,
    )

    assert failures == []
    assert superseded is True
    assert attempts["count"] == 1
