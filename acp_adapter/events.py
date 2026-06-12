"""Callbacks that translate Clio agent events into ACP session updates."""

from __future__ import annotations

import asyncio
import json
from collections import deque
from typing import Any

from acp.schema import AgentMessageChunk, AgentPlanUpdate, AgentThoughtChunk, PlanEntry, TextContentBlock

from acp_adapter.tools import build_tool_complete, build_tool_start, make_tool_call_id


def _send_update(conn, session_id: str, loop: asyncio.AbstractEventLoop, update) -> None:
    coro = conn.session_update(session_id=session_id, update=update)
    try:
        from agent.async_utils import asyncio as agent_asyncio

        agent_asyncio.run_coroutine_threadsafe(coro, loop)
    except Exception:
        close = getattr(coro, "close", None)
        if close:
            close()


def _coerce_args(args: Any) -> dict[str, Any]:
    if isinstance(args, dict):
        return args
    if isinstance(args, str):
        try:
            parsed = json.loads(args)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {} if args is None else {"value": args}


def _push_tool_id(tool_call_ids: dict, name: str, tc_id: str) -> None:
    existing = tool_call_ids.get(name)
    if existing is None:
        tool_call_ids[name] = deque([tc_id])
    elif isinstance(existing, deque):
        existing.append(tc_id)
    else:
        tool_call_ids[name] = deque([existing, tc_id])


def _pop_tool_id(tool_call_ids: dict, name: str) -> str | None:
    existing = tool_call_ids.get(name)
    if existing is None:
        return None
    if isinstance(existing, deque):
        tc_id = existing.popleft()
        if not existing:
            tool_call_ids.pop(name, None)
        return tc_id
    tool_call_ids.pop(name, None)
    return existing


def make_tool_progress_cb(conn, session_id: str, loop: asyncio.AbstractEventLoop, tool_call_ids: dict, tool_call_meta: dict | None = None):
    tool_call_meta = tool_call_meta if tool_call_meta is not None else {}

    def _cb(event: str, tool_name: str, message: str | None = None, args: Any = None):
        if event not in {"tool.started", "tool.start", "started"}:
            return
        parsed = _coerce_args(args)
        tc_id = make_tool_call_id()
        _push_tool_id(tool_call_ids, tool_name, tc_id)
        snapshot = None
        if tool_name in {"write_file", "patch"}:
            try:
                from agent.display import capture_local_edit_snapshot

                snapshot = capture_local_edit_snapshot(parsed)
            except Exception:
                snapshot = None
        tool_call_meta[tc_id] = {"args": parsed, "snapshot": snapshot}
        _send_update(conn, session_id, loop, build_tool_start(tc_id, tool_name, parsed))

    return _cb


def make_step_cb(conn, session_id: str, loop: asyncio.AbstractEventLoop, tool_call_ids: dict, tool_call_meta: dict | None = None):
    tool_call_meta = tool_call_meta if tool_call_meta is not None else {}

    def _cb(step_index: int, prev_tools: list[Any] | None):
        for info in prev_tools or []:
            if isinstance(info, str):
                name, result, args = info, None, None
            elif isinstance(info, dict):
                name, result, args = info.get("name"), info.get("result"), info.get("arguments")
            else:
                continue
            if not name:
                continue
            tc_id = _pop_tool_id(tool_call_ids, str(name))
            if not tc_id:
                continue
            meta = tool_call_meta.pop(tc_id, {}) if isinstance(tool_call_meta, dict) else {}
            function_args = args if isinstance(args, dict) else meta.get("args")
            update = build_tool_complete(tc_id, str(name), result=result, function_args=function_args, snapshot=meta.get("snapshot"))
            _send_update(conn, session_id, loop, update)
            if str(name) == "todo":
                _send_update(conn, session_id, loop, _build_plan_update_from_todo_result(result))

    return _cb


def make_thinking_cb(conn, session_id: str, loop: asyncio.AbstractEventLoop):
    def _cb(text: str):
        if not text:
            return
        _send_update(conn, session_id, loop, AgentThoughtChunk(content=TextContentBlock(type="text", text=text), sessionUpdate="agent_thought_chunk"))

    return _cb


def make_message_cb(conn, session_id: str, loop: asyncio.AbstractEventLoop):
    def _cb(text: str):
        if not text:
            return
        _send_update(conn, session_id, loop, AgentMessageChunk(content=TextContentBlock(type="text", text=text), sessionUpdate="agent_message_chunk"))

    return _cb


def _build_plan_update_from_todo_result(result: Any) -> AgentPlanUpdate:
    data = result
    if isinstance(result, str):
        try:
            data = json.loads(result)
        except Exception:
            head = result.split("\n\n[Hint:", 1)[0].strip()
            try:
                data = json.loads(head)
            except Exception:
                data = {}
    todos = data.get("todos") if isinstance(data, dict) else None
    entries = []
    for todo in todos or []:
        if not isinstance(todo, dict):
            continue
        status = str(todo.get("status") or "pending")
        content = str(todo.get("content") or "")
        if status == "cancelled":
            content = f"[cancelled] {content}"
            status = "completed"
        if status not in {"pending", "in_progress", "completed"}:
            status = "pending"
        entries.append(PlanEntry(content=content, status=status, priority="medium"))
    return AgentPlanUpdate(entries=entries, sessionUpdate="plan")
