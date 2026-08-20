"""ACP session state and persistence."""

from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from clio_state import SessionDB


@dataclass
class SessionState:
    session_id: str
    cwd: str
    agent: Any
    history: list[dict[str, Any]] = field(default_factory=list)
    model: str = ""
    mode: str = "default"
    cancel_event: Any = None
    runtime: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.cancel_event is None:
            import threading

            self.cancel_event = threading.Event()


def _translate_acp_cwd(cwd: str | None) -> str:
    value = cwd or os.getcwd()
    try:
        import clio_constants

        is_wsl = bool(getattr(clio_constants, "_wsl_detected", False))
    except Exception:
        is_wsl = False
    if is_wsl and len(value) >= 3 and value[1] == ":" and value[2] in {"\\", "/"}:
        drive = value[0].lower()
        tail = value[3:].replace("\\", "/")
        return f"/mnt/{drive}/{tail}".rstrip("/")
    return value


def _windows_to_wsl(cwd: str) -> str:
    if len(cwd) >= 3 and cwd[1] == ":" and cwd[2] in {"\\", "/"}:
        drive = cwd[0].lower()
        tail = cwd[3:].replace("\\", "/")
        return f"/mnt/{drive}/{tail}".rstrip("/")
    return cwd


def _cwd_matches(left: str, right: str) -> bool:
    return _translate_acp_cwd(left) == _translate_acp_cwd(right) or _windows_to_wsl(left) == _windows_to_wsl(right)


def _register_task_cwd(task_id: str, cwd: str) -> None:
    try:
        from tools.terminal_tool import register_task_env_overrides

        register_task_env_overrides(task_id, {"cwd": _translate_acp_cwd(cwd)})
    except Exception:
        pass


def _json_scalar(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return None


class SessionManager:
    def __init__(self, agent_factory: Callable[..., Any] | None = None, db: SessionDB | None = None):
        self.agent_factory = agent_factory
        if db is None and agent_factory is not None:
            tmp = tempfile.NamedTemporaryFile(prefix="clio-acp-test-", suffix=".db", delete=False)
            tmp.close()
            db = SessionDB(Path(tmp.name))
        self._db = db
        self._sessions: dict[str, SessionState] = {}
        self._known_ids: set[str] = set()
        import threading

        self._lock = threading.RLock()

    def _get_db(self) -> SessionDB:
        if self._db is None:
            self._db = SessionDB()
        return self._db

    def _enabled_toolsets(self, cfg: dict[str, Any]) -> list[str]:
        enabled = ["clio-acp"]
        for name, server in (cfg.get("mcp_servers") or {}).items():
            if isinstance(server, dict) and server.get("enabled") is False:
                continue
            toolset = f"mcp-{name}"
            if toolset not in enabled:
                enabled.append(toolset)
        return enabled

    def _make_agent(
        self,
        cwd: str | None = None,
        *,
        requested_provider: str | None = None,
        model: str | None = None,
        runtime: dict[str, Any] | None = None,
    ) -> Any:
        if self.agent_factory is not None:
            agent = self.agent_factory()
            if getattr(agent, "_print_fn", None) is None:
                agent._print_fn = lambda *args, **kwargs: print(*args, file=sys.stderr, **kwargs)
            return agent
        from run_agent import AIAgent
        from clio_cli.runtime_provider import resolve_runtime_provider
        from clio_cli.config import load_config, resolve_config_turn_limit

        runtime = dict(runtime or resolve_runtime_provider(requested=requested_provider))
        cfg = load_config()
        configured_model = (
            model
            or runtime.get("model")
            or runtime.get("default_model")
            or (cfg.get("model") or {}).get("default")
        )
        agent = AIAgent(
            provider=runtime.get("provider"),
            model=configured_model,
            api_key=runtime.get("api_key"),
            base_url=runtime.get("base_url"),
            api_mode=runtime.get("api_mode"),
            max_iterations=resolve_config_turn_limit(cfg),
            enabled_toolsets=self._enabled_toolsets(cfg),
        )
        if getattr(agent, "_print_fn", None) is None:
            agent._print_fn = lambda *args, **kwargs: print(*args, file=sys.stderr, **kwargs)
        return agent

    def create_session(self, cwd: str | None = None, **kwargs) -> SessionState:
        translated = _translate_acp_cwd(cwd)
        session_id = f"acp-{uuid.uuid4().hex}"
        runtime = {}
        agent = self._make_agent(translated)
        for key in ("provider", "base_url", "api_mode"):
            value = _json_scalar(getattr(agent, key, None))
            if value:
                runtime[key] = value
        model = _json_scalar(getattr(agent, "model", None)) or ""
        state = SessionState(
            session_id=session_id,
            cwd=translated,
            agent=agent,
            model=model,
            runtime=runtime,
        )
        with self._lock:
            self._sessions[session_id] = state
            self._known_ids.add(session_id)
        _register_task_cwd(session_id, translated)
        self._get_db().create_session(
            session_id,
            source="acp",
            model=state.model or None,
            model_config={"cwd": translated, "mode": state.mode, "runtime": state.runtime},
            cwd=translated,
        )
        return state

    def get_session(self, session_id: str) -> SessionState | None:
        with self._lock:
            state = self._sessions.get(session_id)
        if state is not None:
            return state
        row = self._get_db().get_session(session_id)
        if not row or row.get("source") != "acp":
            return None
        try:
            meta = json.loads(row.get("model_config") or "{}")
        except Exception:
            meta = {}
        runtime = meta.get("runtime") if isinstance(meta.get("runtime"), dict) else None
        model = row.get("model") or meta.get("model") or ""
        state = SessionState(
            session_id=session_id,
            cwd=meta.get("cwd") or row.get("cwd") or os.getcwd(),
            agent=self._make_agent(meta.get("cwd") or row.get("cwd"), model=model or None, runtime=runtime),
            history=self._get_db().get_messages_as_conversation(session_id),
            model=model,
            mode=meta.get("mode") or "default",
            runtime=runtime or {},
        )
        with self._lock:
            self._sessions[session_id] = state
            self._known_ids.add(session_id)
        return state

    def fork_session(self, session_id: str, cwd: str | None = None) -> SessionState | None:
        original = self.get_session(session_id)
        if original is None:
            return None
        forked = self.create_session(cwd=cwd or original.cwd)
        forked.history = copy.deepcopy(original.history)
        return forked

    def update_cwd(self, session_id: str, cwd: str) -> SessionState | None:
        state = self.get_session(session_id)
        if state is None:
            return None
        state.cwd = _translate_acp_cwd(cwd)
        self.save_session(session_id)
        return state

    def list_sessions(self, cwd: str | None = None) -> list[dict[str, Any]]:
        cwd_filter = cwd
        rows = self._get_db().list_sessions_rich(
            source="acp",
            limit=10000,
            include_children=True,
            min_message_count=1,
            project_compression_tips=False,
            include_archived=False,
        )
        seen: set[str] = set()
        items: list[dict[str, Any]] = []

        for row in rows:
            sid = row.get("id")
            if not sid or sid in seen or sid not in self._known_ids:
                continue
            seen.add(sid)
            try:
                meta = json.loads(row.get("model_config") or "{}")
            except Exception:
                meta = {}
            item_cwd = meta.get("cwd") or row.get("cwd") or os.getcwd()
            if cwd_filter and not _cwd_matches(item_cwd, cwd_filter):
                continue
            title = row.get("title") or row.get("preview") or None
            items.append(
                {
                    "session_id": sid,
                    "cwd": item_cwd,
                    "title": title,
                    "updated_at": row.get("last_active") or row.get("started_at"),
                }
            )

        for state in list(self._sessions.values()):
            if not state.history or state.session_id in seen:
                continue
            if cwd_filter and not _cwd_matches(state.cwd, cwd_filter):
                continue
            seen.add(state.session_id)
            title = next((m.get("content") for m in state.history if m.get("role") == "user" and m.get("content")), None)
            items.append(
                {
                    "session_id": state.session_id,
                    "cwd": state.cwd,
                    "title": title,
                    "updated_at": None,
                }
            )

        def _sort_key(item: dict[str, Any]) -> float:
            try:
                return float(item.get("updated_at") or 0)
            except Exception:
                return 0.0

        return sorted(items, key=_sort_key, reverse=True)

    def save_session(self, session_id: str) -> None:
        state = self.get_session(session_id)
        if state is None:
            return
        self._persist(state)

    def _persist(self, state: SessionState) -> None:
        db = self._get_db()
        runtime = dict(state.runtime or {})
        for key in ("provider", "base_url", "api_mode"):
            value = _json_scalar(getattr(state.agent, key, None))
            if value:
                runtime[key] = value
        model_config = json.dumps(
            {"cwd": state.cwd, "mode": state.mode, "runtime": runtime},
            ensure_ascii=False,
        )
        db.update_session_meta(state.session_id, model_config, model=state.model or None)
        try:
            db.replace_messages(state.session_id, state.history)
        except Exception:
            pass

    def remove_session(self, session_id: str) -> bool:
        with self._lock:
            self._sessions.pop(session_id, None)
            self._known_ids.discard(session_id)
        return bool(self._get_db().delete_session(session_id))

    def cleanup(self) -> None:
        ids = [s.session_id for s in list(self._sessions.values())]
        for sid in ids:
            self.remove_session(sid)
