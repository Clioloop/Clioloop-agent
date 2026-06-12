"""ACP server implementation."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from functools import partial
from typing import Any

import acp
from acp.schema import (
    AgentCapabilities,
    AgentMessageChunk,
    AgentPlanUpdate,
    AgentThoughtChunk,
    AuthenticateResponse,
    AvailableCommand,
    AvailableCommandInput,
    AvailableCommandsUpdate,
    ForkSessionResponse,
    Implementation,
    InitializeResponse,
    ListSessionsResponse,
    LoadSessionResponse,
    ModelInfo,
    NewSessionResponse,
    PlanEntry,
    PromptResponse,
    ResumeSessionResponse,
    SessionCapabilities,
    SessionForkCapabilities,
    SessionInfo,
    SessionInfoUpdate,
    SessionListCapabilities,
    SessionModelState,
    SessionMode,
    SessionModeState,
    SessionResumeCapabilities,
    SetSessionConfigOptionResponse,
    SetSessionModeResponse,
    SetSessionModelResponse,
    TextContentBlock,
    UnstructuredCommandInput,
    Usage,
    UsageUpdate,
    UserMessageChunk,
)

from acp_adapter.auth import TERMINAL_SETUP_AUTH_METHOD_ID, build_auth_methods, detect_provider
from acp_adapter.events import (
    _build_plan_update_from_todo_result,
    make_message_cb,
    make_step_cb,
    make_thinking_cb,
    make_tool_progress_cb,
)
from acp_adapter.permissions import make_approval_callback
from acp_adapter.session import SessionManager
from acp_adapter.tools import build_tool_complete, build_tool_start

try:
    from clio_cli import __version__ as CLIO_VERSION
except Exception:
    CLIO_VERSION = "0.1.0"

log = logging.getLogger(__name__)
_LIST_SESSIONS_PAGE_SIZE = 50


def _mode_state(current: str = "default") -> SessionModeState:
    return SessionModeState(
        currentModeId=current,
        availableModes=[
            SessionMode(id="default", name="Default"),
            SessionMode(id="accept_edits", name="Accept Edits"),
            SessionMode(id="dont_ask", name="Don't Ask"),
        ],
    )


def _safe_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


class ClioACPAgent:
    def __init__(self, session_manager: SessionManager | None = None):
        self.session_manager = session_manager or SessionManager()
        self._conn = None

    def on_connect(self, conn) -> None:
        self._conn = conn

    async def initialize(self, protocol_version: int, **kwargs) -> InitializeResponse:
        return InitializeResponse(
            protocolVersion=acp.PROTOCOL_VERSION,
            agentInfo=Implementation(name="clio-agent", version=CLIO_VERSION),
            agentCapabilities=AgentCapabilities(
                loadSession=True,
                sessionCapabilities=SessionCapabilities(
                    fork=SessionForkCapabilities(),
                    list=SessionListCapabilities(),
                    resume=SessionResumeCapabilities(),
                ),
            ),
            authMethods=build_auth_methods(),
        )

    async def authenticate(self, method_id: str, **kwargs):
        provider = detect_provider()
        mid = (method_id or "").strip().lower()
        if provider and mid in {provider.lower(), TERMINAL_SETUP_AUTH_METHOD_ID}:
            return AuthenticateResponse()
        return None

    def _model_state(self, state) -> SessionModelState | None:
        provider = _safe_str(getattr(state.agent, "provider", None)) or _safe_str((state.runtime or {}).get("provider"))
        model = _safe_str(state.model) or _safe_str(getattr(state.agent, "model", None))
        if not model:
            return None
        current_id = f"{provider}:{model}" if provider else str(model)
        available: list[ModelInfo] = []
        try:
            from clio_cli.models import curated_models_for_provider

            for mid, desc in curated_models_for_provider(provider):
                model_id = f"{provider}:{mid}" if provider else mid
                description = f"Provider: {provider}\n{desc or ''}".strip() if provider else (desc or None)
                available.append(ModelInfo(modelId=model_id, name=mid, description=description))
        except Exception:
            pass
        if not any(item.model_id == current_id for item in available):
            description = f"Provider: {provider}" if provider else None
            available.insert(0, ModelInfo(modelId=current_id, name=str(model), description=description))
        return SessionModelState(currentModelId=current_id, availableModels=available)

    async def new_session(self, cwd: str | None = None, mcp_servers=None, **kwargs) -> NewSessionResponse:
        state = self.session_manager.create_session(cwd=cwd)
        await self._register_session_mcp_servers(state, mcp_servers)
        await self._send_available_commands_update(state.session_id)
        return NewSessionResponse(
            sessionId=state.session_id,
            modes=_mode_state(state.mode),
            models=self._model_state(state),
            configOptions=None,
        )

    async def load_session(self, session_id: str, mcp_servers=None, **kwargs) -> LoadSessionResponse | None:
        state = self.session_manager.get_session(session_id)
        if not state:
            return None
        await self._register_session_mcp_servers(state, mcp_servers)
        try:
            await self._replay_session_history(state)
        except Exception:
            log.warning("history replay raised during session/load", exc_info=True)
        return LoadSessionResponse(modes=_mode_state(state.mode), models=self._model_state(state), configOptions=None)

    async def resume_session(self, session_id: str, cwd: str | None = None, mcp_servers=None, **kwargs) -> ResumeSessionResponse | None:
        state = self.session_manager.get_session(session_id)
        if not state:
            state = self.session_manager.create_session(cwd=cwd)
        await self._register_session_mcp_servers(state, mcp_servers)
        try:
            await self._replay_session_history(state)
        except Exception:
            log.warning("history replay raised during session/resume", exc_info=True)
        return ResumeSessionResponse(modes=_mode_state(state.mode), models=self._model_state(state), configOptions=None)

    async def fork_session(self, session_id: str, cwd: str | None = None, mcp_servers=None, **kwargs) -> ForkSessionResponse | None:
        state = self.session_manager.fork_session(session_id, cwd=cwd)
        if state is None:
            return None
        await self._register_session_mcp_servers(state, mcp_servers)
        return ForkSessionResponse(sessionId=state.session_id, modes=_mode_state(state.mode), models=self._model_state(state), configOptions=None)

    async def cancel(self, session_id: str, **kwargs) -> None:
        state = self.session_manager.get_session(session_id)
        if state is not None:
            state.cancel_event.set()

    async def set_config_option(
        self,
        option_id: str | None = None,
        session_id: str = "",
        value=None,
        config_id: str | None = None,
        **kwargs,
    ) -> SetSessionConfigOptionResponse:
        option_id = option_id or config_id
        state = self.session_manager.get_session(session_id)
        if state and option_id == "edit_approval_policy":
            state.mode = "accept_edits" if value == "workspace_session" else str(value or "default")
            self.session_manager.save_session(session_id)
        return SetSessionConfigOptionResponse(configOptions=[])

    async def set_session_mode(self, session_id: str, mode_id: str, **kwargs) -> SetSessionModeResponse:
        state = self.session_manager.get_session(session_id)
        if state:
            state.mode = mode_id
            self.session_manager.save_session(session_id)
        return SetSessionModeResponse()

    async def set_session_model(self, session_id: str, model_id: str, **kwargs) -> SetSessionModelResponse:
        state = self.session_manager.get_session(session_id)
        if state:
            self._cmd_model(model_id, state)
            self.session_manager.save_session(session_id)
        return SetSessionModelResponse()

    async def list_sessions(self, cwd: str | None = None, cursor: str | None = None, **kwargs) -> ListSessionsResponse:
        infos = self.session_manager.list_sessions(cwd=cwd)
        if cursor:
            positions = [idx for idx, item in enumerate(infos) if item.get("session_id") == cursor]
            if not positions:
                return ListSessionsResponse(sessions=[], nextCursor=None)
            infos = infos[positions[0] + 1 :]
        page = infos[:_LIST_SESSIONS_PAGE_SIZE]
        next_cursor = page[-1]["session_id"] if len(infos) > len(page) and page else None
        return ListSessionsResponse(
            sessions=[
                SessionInfo(
                    sessionId=item["session_id"],
                    cwd=item.get("cwd") or os.getcwd(),
                    title=item.get("title"),
                    updatedAt=str(item.get("updated_at")) if item.get("updated_at") is not None else None,
                )
                for item in page
            ],
            nextCursor=next_cursor,
        )

    def _available_commands(self) -> list[AvailableCommand]:
        descriptions = {
            "help": "List available commands",
            "model": "Show or switch model",
            "tools": "Show enabled tools",
            "context": "Show context usage",
            "reset": "Clear this session history",
            "compact": "Compress context",
            "steer": "Add steering guidance",
            "queue": "Show queued work",
            "version": "Show Clio version",
        }
        commands = []
        for name in ["help", "model", "tools", "context", "reset", "compact", "steer", "queue", "version"]:
            input_spec = None
            if name == "model":
                input_spec = AvailableCommandInput(root=UnstructuredCommandInput(hint="model name to switch to"))
            commands.append(AvailableCommand(name=name, description=descriptions[name], input=input_spec))
        return commands

    async def _send_available_commands_update(self, session_id: str) -> None:
        if self._conn is None:
            return
        await self._conn.session_update(
            session_id=session_id,
            update=AvailableCommandsUpdate(
                sessionUpdate="available_commands_update",
                availableCommands=self._available_commands(),
            ),
        )

    def _build_usage_update(self, state) -> UsageUpdate:
        size = int(getattr(getattr(state.agent, "context_compressor", None), "context_length", 0) or 0)
        try:
            from agent.model_metadata import estimate_request_tokens_rough

            used = int(
                estimate_request_tokens_rough(
                    state.history,
                    getattr(state.agent, "_cached_system_prompt", None),
                    getattr(state.agent, "tools", None),
                )
            )
        except Exception:
            used = 0
        return UsageUpdate(sessionUpdate="usage_update", size=max(size, 0), used=max(used, 0))

    async def _send_usage_update(self, state) -> None:
        if self._conn is None:
            return
        await self._conn.session_update(session_id=state.session_id, update=self._build_usage_update(state))

    def _usage_from_result(self, result: dict[str, Any]) -> Usage | None:
        total = result.get("total_tokens")
        prompt = result.get("prompt_tokens")
        completion = result.get("completion_tokens")
        if total is None and prompt is None and completion is None:
            return None
        prompt = int(prompt or 0)
        completion = int(completion or 0)
        return Usage(
            inputTokens=prompt,
            outputTokens=completion,
            totalTokens=int(total if total is not None else prompt + completion),
            thoughtTokens=result.get("reasoning_tokens"),
            cachedReadTokens=result.get("cache_read_tokens"),
        )

    async def prompt(self, session_id: str, prompt, **kwargs) -> PromptResponse:
        state = self.session_manager.get_session(session_id)
        if state is None:
            return PromptResponse(stopReason="refusal")
        text = self._prompt_text(prompt).strip()
        if not text:
            return PromptResponse(stopReason="end_turn")
        conn = self._conn
        loop = asyncio.get_running_loop()
        tool_call_ids = {}
        tool_call_meta = {}
        if conn is not None:
            state.agent.tool_progress_callback = make_tool_progress_cb(conn, session_id, loop, tool_call_ids, tool_call_meta)
            state.agent.step_callback = make_step_cb(conn, session_id, loop, tool_call_ids, tool_call_meta)
            state.agent.reasoning_callback = make_thinking_cb(conn, session_id, loop)
            state.agent.thinking_callback = None
            state.agent.stream_delta_callback = make_message_cb(conn, session_id, loop)
            state.agent.streaming_callback = state.agent.stream_delta_callback
            if hasattr(conn, "request_permission"):
                state.agent.approval_callback = make_approval_callback(conn.request_permission, loop, session_id=session_id)

        if text.startswith("/"):
            command_result = self._handle_slash_command(text, state)
            if command_result is not None:
                if conn is not None:
                    await conn.session_update(
                        session_id=session_id,
                        update=AgentMessageChunk(
                            sessionUpdate="agent_message_chunk",
                            content=TextContentBlock(type="text", text=command_result),
                        ),
                    )
                    await self._send_usage_update(state)
                self.session_manager.save_session(session_id)
                return PromptResponse(stopReason="end_turn")

        prior_session_id = os.environ.get("CLIO_SESSION_ID")
        os.environ["CLIO_SESSION_ID"] = session_id
        try:
            run_fn = getattr(state.agent, "run_conversation", None)
            if run_fn is None:
                run_fn = getattr(state.agent, "run", None)
            if run_fn is None:
                result = {"final_response": "", "messages": state.history}
            else:
                call = partial(
                    run_fn,
                    text,
                    conversation_history=state.history,
                    task_id=session_id,
                    cancellation_event=state.cancel_event,
                )
                result = await loop.run_in_executor(None, call)
        finally:
            if prior_session_id is None:
                os.environ.pop("CLIO_SESSION_ID", None)
            else:
                os.environ["CLIO_SESSION_ID"] = prior_session_id

        if not isinstance(result, dict):
            result = {"final_response": str(result or ""), "messages": []}
        messages = result.get("messages")
        if messages:
            state.history = list(messages)
        else:
            state.history.append({"role": "user", "content": text})
            if result.get("final_response"):
                state.history.append({"role": "assistant", "content": result["final_response"]})

        await asyncio.sleep(0)
        final_response = str(result.get("final_response") or "")
        if conn is not None and final_response:
            response_transformed = bool(result.get("response_transformed"))
            already_streamed = any(
                getattr(call.kwargs.get("update"), "session_update", None) == "agent_message_chunk"
                and getattr(getattr(call.kwargs.get("update"), "content", None), "text", None) == final_response
                for call in getattr(conn.session_update, "call_args_list", [])
            )
            if response_transformed or not already_streamed:
                await conn.session_update(
                    session_id=session_id,
                    update=AgentMessageChunk(
                        sessionUpdate="agent_message_chunk",
                        content=TextContentBlock(type="text", text=final_response),
                    ),
                )
            await self._send_usage_update(state)

        self.session_manager.save_session(session_id)
        await self._maybe_auto_title(state, text, final_response)
        stop_reason = "cancelled" if state.cancel_event.is_set() else "end_turn"
        return PromptResponse(stopReason=stop_reason, usage=self._usage_from_result(result))

    def _prompt_text(self, prompt) -> str:
        value = getattr(prompt, "content", prompt)
        if isinstance(value, list):
            parts = []
            for item in value:
                if getattr(item, "type", None) == "text":
                    parts.append(getattr(item, "text", ""))
                else:
                    parts.append(str(getattr(item, "text", item)))
            return "\n".join(parts)
        return str(getattr(value, "text", value))

    async def _maybe_auto_title(self, state, user_text: str, final_response: str) -> None:
        if not user_text or not final_response:
            return

        def _title_callback(title: str) -> None:
            if self._conn is None:
                return
            coro = self._conn.session_update(
                session_id=state.session_id,
                update=SessionInfoUpdate(sessionUpdate="session_info_update", title=title),
            )
            try:
                asyncio.run_coroutine_threadsafe(coro, asyncio.get_running_loop())
            except RuntimeError:
                pass

        try:
            from agent.title_generator import maybe_auto_title

            maybe_auto_title(
                self.session_manager._get_db(),
                state.session_id,
                user_text,
                final_response,
                state.history,
                title_callback=_title_callback,
            )
        except Exception:
            pass

    async def _replay_session_history(self, state) -> None:
        if self._conn is None:
            return
        pending_tool_calls: dict[str, str] = {}
        for msg in state.history:
            role = msg.get("role")
            content = msg.get("content")
            if role == "system":
                continue
            if role == "user" and content:
                await self._conn.session_update(
                    session_id=state.session_id,
                    update=UserMessageChunk(
                        sessionUpdate="user_message_chunk",
                        content=TextContentBlock(type="text", text=str(content)),
                    ),
                )
                continue
            if role == "assistant":
                reasoning = str(msg.get("reasoning_content") or msg.get("reasoning") or "").strip()
                if reasoning:
                    await self._conn.session_update(
                        session_id=state.session_id,
                        update=AgentThoughtChunk(
                            sessionUpdate="agent_thought_chunk",
                            content=TextContentBlock(type="text", text=reasoning),
                        ),
                    )
                if content:
                    await self._conn.session_update(
                        session_id=state.session_id,
                        update=AgentMessageChunk(
                            sessionUpdate="agent_message_chunk",
                            content=TextContentBlock(type="text", text=str(content)),
                        ),
                    )
                for call in msg.get("tool_calls") or []:
                    function = call.get("function") or {}
                    name = function.get("name") or call.get("name") or "tool"
                    args = self._json_obj(function.get("arguments"))
                    tc_id = call.get("id") or f"replay-{len(pending_tool_calls)+1}"
                    pending_tool_calls[tc_id] = name
                    await self._conn.session_update(
                        session_id=state.session_id,
                        update=build_tool_start(tc_id, str(name), args),
                    )
                continue
            if role == "tool":
                tc_id = msg.get("tool_call_id") or ""
                name = msg.get("name") or pending_tool_calls.get(tc_id) or "tool"
                result = msg.get("content")
                await self._conn.session_update(
                    session_id=state.session_id,
                    update=build_tool_complete(tc_id, str(name), result=result),
                )
                if str(name) == "todo":
                    await self._conn.session_update(
                        session_id=state.session_id,
                        update=_build_plan_update_from_todo_result(result),
                    )

    def _json_obj(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
        return {}

    async def _register_session_mcp_servers(self, state, mcp_servers) -> None:
        if not mcp_servers:
            return
        configs = {}
        for server in mcp_servers:
            name = getattr(server, "name", None) or getattr(server, "id", None) or "mcp"
            if getattr(server, "command", None):
                configs[name] = {
                    "command": server.command,
                    "args": list(getattr(server, "args", None) or []),
                    "env": {item.name: item.value for item in (getattr(server, "env", None) or [])},
                }
            elif getattr(server, "url", None):
                configs[name] = {
                    "url": server.url,
                    "headers": {item.name: item.value for item in (getattr(server, "headers", None) or [])},
                }
        if not configs:
            return
        from tools.mcp_tool import register_mcp_servers
        from model_tools import get_tool_definitions

        try:
            register_mcp_servers(configs)
        except Exception:
            log.warning("failed to register ACP MCP servers", exc_info=True)
            return
        enabled = list(getattr(state.agent, "enabled_toolsets", None) or ["clio-acp"])
        for name in configs:
            toolset = f"mcp-{str(name).replace('/', '_')}"
            if toolset not in enabled:
                enabled.append(toolset)
        state.agent.enabled_toolsets = enabled
        disabled = getattr(state.agent, "disabled_toolsets", None)
        state.agent.tools = get_tool_definitions(
            enabled_toolsets=enabled,
            disabled_toolsets=disabled,
            quiet_mode=True,
        )
        state.agent.valid_tool_names = {
            tool.get("function", {}).get("name")
            for tool in state.agent.tools
            if isinstance(tool, dict)
        }
        invalidate = getattr(state.agent, "_invalidate_system_prompt", None)
        if callable(invalidate):
            invalidate()
        else:
            state.agent._cached_system_prompt = None

    def _handle_slash_command(self, text: str, state) -> str | None:
        parts = text.strip().split(maxsplit=1)
        command = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        if command == "/help":
            return "\n".join(f"/{cmd.name} - {cmd.description}" for cmd in self._available_commands())
        if command == "/model":
            return self._cmd_model(arg, state) if arg else f"Current model: {state.model or getattr(state.agent, 'model', '')}"
        if command == "/tools":
            tools = getattr(state.agent, "tools", None) or []
            names = [tool.get("function", {}).get("name") for tool in tools if isinstance(tool, dict)]
            return "Enabled tools: " + (", ".join(filter(None, names)) or "none")
        if command == "/context":
            if not state.history:
                return "Context is empty."
            counts = {}
            for msg in state.history:
                role = msg.get("role") or "unknown"
                counts[role] = counts.get(role, 0) + 1
            lines = [f"{len(state.history)} messages", *[f"{role}: {count}" for role, count in sorted(counts.items())]]
            compressor = getattr(state.agent, "context_compressor", None)
            if compressor is not None:
                usage = self._build_usage_update(state)
                if usage.size:
                    pct = usage.used / usage.size * 100
                    lines.append(f"Context usage: ~{usage.used:,} / {usage.size:,} tokens ({pct:.1f}%)")
                    threshold = int(getattr(compressor, "threshold_tokens", 0) or 0)
                    if threshold:
                        threshold_pct = round(threshold / usage.size * 100)
                        if usage.used >= threshold:
                            lines.append(f"Compression: due now (threshold ~{threshold:,}, {threshold_pct}%). Run /compact.")
                        else:
                            remaining = threshold - usage.used
                            lines.append(f"Compression: ~{remaining:,} tokens until threshold (~{threshold:,}, {threshold_pct}%)")
                            lines.append("Tip: run /compact")
            return "\n".join(lines)
        if command == "/reset":
            state.history.clear()
            self.session_manager.save_session(state.session_id)
            return "Session history cleared."
        if command == "/version":
            return f"Clio {CLIO_VERSION}"
        if command == "/compact":
            return self._cmd_compact(state)
        if command in {"/steer", "/queue"}:
            return f"{command[1:]} is not available in ACP yet."
        return None

    def _cmd_compact(self, state) -> str:
        if not state.history:
            return "Context is empty."
        compressor = getattr(state.agent, "_compress_context", None)
        if compressor is None:
            return "Context compression is not available."
        try:
            from agent.model_metadata import estimate_request_tokens_rough

            before_tokens = int(estimate_request_tokens_rough(state.history, getattr(state.agent, "_cached_system_prompt", None), getattr(state.agent, "tools", None)))
        except Exception:
            before_tokens = 0
        before_count = len(state.history)
        old_db = getattr(state.agent, "_session_db", None)
        state.agent._session_db = None
        try:
            new_history, new_system = compressor(
                list(state.history),
                getattr(state.agent, "_cached_system_prompt", None),
                approx_tokens=before_tokens,
                task_id=state.session_id,
            )
        finally:
            state.agent._session_db = old_db
        state.history = list(new_history or [])
        state.agent._cached_system_prompt = new_system
        try:
            from agent.model_metadata import estimate_request_tokens_rough

            after_tokens = int(estimate_request_tokens_rough(state.history, new_system, getattr(state.agent, "tools", None)))
        except Exception:
            after_tokens = 0
        self.session_manager.save_session(state.session_id)
        return f"Context compressed: {before_count} -> {len(state.history)} messages\n~{before_tokens:,} -> ~{after_tokens:,} tokens"

    def _cmd_model(self, arg: str, state) -> str:
        if not arg:
            return f"Current model: {state.model or getattr(state.agent, 'model', '')}"
        try:
            from clio_cli.models import detect_provider_for_model, parse_model_input

            current_provider = _safe_str(getattr(state.agent, "provider", None)) or _safe_str((state.runtime or {}).get("provider"))
            requested_provider, model = parse_model_input(arg, current_provider)
            requested_provider = requested_provider or detect_provider_for_model(model, current_provider) or current_provider
            requested_provider = _safe_str(requested_provider)
        except Exception:
            requested_provider = None
            model = arg.split(":", 1)[-1]
        state.model = model
        state.agent = self.session_manager._make_agent(
            state.cwd,
            requested_provider=requested_provider,
            model=model,
        )
        state.runtime = {
            "provider": _safe_str(getattr(state.agent, "provider", None)) or requested_provider,
            "base_url": _safe_str(getattr(state.agent, "base_url", None)),
            "api_mode": _safe_str(getattr(state.agent, "api_mode", None)),
        }
        return f"Model switched to {model}\nProvider: {state.runtime.get('provider') or 'default'}"
