"""Dangerous-command approval bridge for ACP."""

from __future__ import annotations

import asyncio
import uuid
from typing import Callable

from acp.schema import ContentToolCallContent, PermissionOption, TextContentBlock, ToolCallProgress


def make_approval_callback(request_permission: Callable, loop: asyncio.AbstractEventLoop, *, session_id: str, timeout: float = 60.0):
    def _callback(command: str, description: str, allow_permanent: bool = True):
        options = [
            PermissionOption(optionId="allow_once", name="Allow once", kind="allow_once"),
            PermissionOption(optionId="allow_session", name="Allow for session", kind="allow_once"),
        ]
        if allow_permanent:
            options.append(PermissionOption(optionId="allow_always", name="Always allow", kind="allow_always"))
        options.extend(
            [
                PermissionOption(optionId="deny", name="Deny", kind="reject_once"),
                PermissionOption(optionId="deny_always", name="Always deny", kind="reject_always"),
            ]
        )
        tool_call = ToolCallProgress(
            toolCallId=f"perm-check-{uuid.uuid4().hex}",
            sessionUpdate="tool_call_update",
            kind="execute",
            status="pending",
            title=f"{description}: {command}",
            rawInput={"command": command, "description": description},
            content=[
                ContentToolCallContent(
                    type="content",
                    content=TextContentBlock(type="text", text=f"$ {command}\n\n{description}"),
                )
            ],
        )
        coro = request_permission(session_id=session_id, tool_call=tool_call, options=options)
        future = None
        try:
            from agent.async_utils import asyncio as agent_asyncio

            future = agent_asyncio.run_coroutine_threadsafe(coro, loop)
            response = future.result(timeout=timeout)
        except TimeoutError:
            if future is not None:
                future.cancel()
            return "deny"
        except Exception:
            close = getattr(coro, "close", None)
            if close:
                close()
            return "deny"
        outcome = getattr(response, "outcome", None)
        option_id = str(getattr(outcome, "option_id", "") or "")
        if option_id == "allow_once":
            return "once"
        if option_id == "allow_session":
            return "session"
        if option_id == "allow_always":
            return "always"
        return "deny"

    return _callback

