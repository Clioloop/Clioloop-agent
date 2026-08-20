"""Cross-surface Bot Mode RPC and gateway command contracts."""

from __future__ import annotations

from dataclasses import asdict
from types import SimpleNamespace
from typing import Any

import pytest

import clio_bot_mode
from clio_bot_mode import RoomTurnResult
from clio_cli.commands import resolve_command
from gateway.run import GatewayRunner
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

    assert rpc("bot.rooms.list")["result"]["rooms"][0]["id"] == "room-1"
    assert rpc("bot.rooms.create", {"name": "New", "members": ["alpha", "beta"]})["result"]["room"]["name"] == "New"
    assert rpc("bot.rooms.get", {"room_id": "room-1"})["result"]["room"]["id"] == "room-1"
    assert rpc("bot.rooms.send", {"room_id": "room-1", "message": "review"})["result"] == asdict(turn)
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
    runner = GatewayRunner.__new__(GatewayRunner)
    event: Any = SimpleNamespace(text="/botroom send room-1 | review")
    result = await runner._handle_botroom_command(event)
    assert "[alpha] finding" in result
    assert "3 pass/duplicate/failed" in result
    assert "private" not in result
