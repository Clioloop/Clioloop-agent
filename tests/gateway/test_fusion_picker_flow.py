"""Phase-machine flow test for the Telegram /fusion picker.

Drives _handle_fusion_picker_callback through:
  how-many-planners → pick planners → how-many-reviewers → pick reviewers
and asserts on_fusion_complete receives the right (advisors, reviewers).
"""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


def _install_fake_telegram(monkeypatch):
    fake_telegram = types.ModuleType("telegram")
    fake_telegram.Update = SimpleNamespace(ALL_TYPES=())
    fake_telegram.Bot = object
    fake_telegram.Message = object
    # Keyboards must be constructible (the picker builds them on every render).
    fake_telegram.InlineKeyboardButton = lambda *a, **k: ("btn", a, k)
    fake_telegram.InlineKeyboardMarkup = lambda *a, **k: ("kbd", a, k)

    fake_error = types.ModuleType("telegram.error")
    fake_error.NetworkError = type("NetworkError", (Exception,), {})
    fake_error.BadRequest = type("BadRequest", (Exception,), {})
    fake_error.TimedOut = type("TimedOut", (Exception,), {})
    fake_telegram.error = fake_error

    fake_constants = types.ModuleType("telegram.constants")
    fake_constants.ParseMode = SimpleNamespace(MARKDOWN_V2="MarkdownV2")
    fake_constants.ChatType = SimpleNamespace(
        GROUP="group", SUPERGROUP="supergroup", CHANNEL="channel", PRIVATE="private",
    )
    fake_telegram.constants = fake_constants

    fake_ext = types.ModuleType("telegram.ext")
    for name in ("Application", "CommandHandler", "CallbackQueryHandler", "MessageHandler"):
        setattr(fake_ext, name, object)
    fake_ext.ContextTypes = SimpleNamespace(DEFAULT_TYPE=object)
    fake_ext.filters = object

    fake_request = types.ModuleType("telegram.request")
    fake_request.HTTPXRequest = object

    monkeypatch.setitem(sys.modules, "telegram", fake_telegram)
    monkeypatch.setitem(sys.modules, "telegram.error", fake_error)
    monkeypatch.setitem(sys.modules, "telegram.constants", fake_constants)
    monkeypatch.setitem(sys.modules, "telegram.ext", fake_ext)
    monkeypatch.setitem(sys.modules, "telegram.request", fake_request)


@pytest.fixture
def adapter(monkeypatch):
    _install_fake_telegram(monkeypatch)
    from gateway.config import PlatformConfig
    from gateway.platforms.telegram import TelegramAdapter

    a = TelegramAdapter(PlatformConfig(enabled=True, token="fake-token"))
    # format_message is pure-ish; stub to avoid markdown escaping noise.
    a.format_message = lambda text: text
    return a


@pytest.mark.asyncio
async def test_full_picker_flow_collects_groups(adapter):
    chat_id = "chat-1"
    models = ["m0", "m1", "m2", "m3", "m4"]
    completed = {}

    async def on_complete(cid, advisors, reviewers):
        completed["args"] = (cid, list(advisors), list(reviewers))
        return "🔮 Fusion configured."

    adapter._fusion_picker_state[chat_id] = {
        "msg_id": 1,
        "models": models,
        "session_key": "s1",
        "on_fusion_complete": on_complete,
        "phase": "planner_count",
        "planner_count": 0,
        "advisors": [],
        "reviewer_count": 0,
        "reviewers": [],
        "page": 0,
    }

    query = SimpleNamespace(answer=AsyncMock(), edit_message_text=AsyncMock())

    async def click(data):
        await adapter._handle_fusion_picker_callback(query, data, chat_id)

    # 3 planners → pick m0,m1,m2 ; 2 reviewers → pick m1,m3.
    await click("fc:3")
    assert adapter._fusion_picker_state[chat_id]["phase"] == "planner_pick"
    await click("fm:0")
    await click("fm:1")
    await click("fm:2")
    assert adapter._fusion_picker_state[chat_id]["phase"] == "reviewer_count"
    await click("fc:2")
    assert adapter._fusion_picker_state[chat_id]["phase"] == "reviewer_pick"
    await click("fm:1")
    await click("fm:3")

    assert completed["args"] == (chat_id, ["m0", "m1", "m2"], ["m1", "m3"])
    # State cleared after completion.
    assert chat_id not in adapter._fusion_picker_state


@pytest.mark.asyncio
async def test_picker_back_steps_through_phases(adapter):
    chat_id = "chat-2"
    adapter._fusion_picker_state[chat_id] = {
        "msg_id": 1, "models": ["m0", "m1"], "session_key": "s",
        "on_fusion_complete": AsyncMock(),
        "phase": "planner_count", "planner_count": 0, "advisors": [],
        "reviewer_count": 0, "reviewers": [], "page": 0,
    }
    query = SimpleNamespace(answer=AsyncMock(), edit_message_text=AsyncMock())

    async def click(data):
        await adapter._handle_fusion_picker_callback(query, data, chat_id)

    await click("fc:2")          # planner_count=2 → planner_pick
    await click("fm:0")          # advisors=[m0]
    state = adapter._fusion_picker_state[chat_id]
    assert state["advisors"] == ["m0"]
    await click("fb")            # pop m0, still planner_pick
    assert adapter._fusion_picker_state[chat_id]["advisors"] == []
    await click("fb")            # back to planner_count
    assert adapter._fusion_picker_state[chat_id]["phase"] == "planner_count"


@pytest.mark.asyncio
async def test_picker_cancel_clears_state(adapter):
    chat_id = "chat-3"
    adapter._fusion_picker_state[chat_id] = {
        "msg_id": 1, "models": ["m0"], "session_key": "s",
        "on_fusion_complete": AsyncMock(),
        "phase": "planner_count", "planner_count": 0, "advisors": [],
        "reviewer_count": 0, "reviewers": [], "page": 0,
    }
    query = SimpleNamespace(answer=AsyncMock(), edit_message_text=AsyncMock())
    await adapter._handle_fusion_picker_callback(query, "fx", chat_id)
    assert chat_id not in adapter._fusion_picker_state
