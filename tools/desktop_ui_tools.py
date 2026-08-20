"""Clio Desktop UI tools.

These tools are exposed only through the ``desktop_ui`` toolset.  They emit
session-addressed renderer actions through :mod:`tools.desktop_ui`; no Electron
objects or desktop state leak into the agent core.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from tools import desktop_ui
from tools.registry import registry, tool_error


def desktop_ui_available() -> bool:
    return os.getenv("CLIO_DESKTOP", "").strip().lower() in {"1", "true", "yes", "on"}


def _normalize_preview_target(value: str) -> str:
    target = (value or "").strip()
    if not target:
        return ""
    if re.match(r"^(?:localhost|127\.0\.0\.1|\[::1\])(?::\d+)?(?:/.*)?$", target, re.I):
        return "http://" + target
    if re.match(r"^[\w.-]+\.[a-z]{2,}(?::\d+)?(?:/.*)?$", target, re.I):
        return "https://" + target
    return target


def _emit(action: str, payload: dict[str, Any], label: str) -> str:
    try:
        ok = desktop_ui.emit(action, payload)
    except Exception as exc:
        return tool_error(f"Could not {label}: {exc}")
    if not ok:
        return tool_error(f"{label.capitalize()} is only available in Clio Desktop")
    return json.dumps({"success": True, "action": action, **payload}, ensure_ascii=False)


def _request(action: str, payload: dict[str, Any], label: str) -> str:
    try:
        result = desktop_ui.request(action, payload)
    except Exception as exc:
        return tool_error(f"Could not {label}: {exc}")
    return json.dumps({"success": True, "action": action, "result": result}, ensure_ascii=False)


def open_preview(url: str, label: str = "") -> str:
    target = _normalize_preview_target(url)
    if not target:
        return tool_error("url is required")
    return _emit("preview.open", {"url": target, "label": (label or "").strip()}, "open the preview")


def close_preview(url: str = "") -> str:
    target = _normalize_preview_target(url)
    return _emit("preview.close", {"url": target}, "close the preview")


def read_preview(start: int = 0, count: int = 12000) -> str:
    start = max(0, int(start or 0))
    count = max(1, min(int(count or 12000), 20000))
    return _request("preview.read", {"start": start, "count": count}, "read the preview")


def read_terminal(start: int = 0, count: int = 12000) -> str:
    start = max(0, int(start or 0))
    count = max(1, min(int(count or 12000), 20000))
    return _request("terminal.read", {"start": start, "count": count}, "read the terminal pane")


def close_terminal(task_id: str = "") -> str:
    return _emit("terminal.close", {"task_id": (task_id or "").strip()}, "close the terminal tab")


def focus_pane(pane: str) -> str:
    pane = (pane or "").strip().lower()
    allowed = {"chat", "files", "preview", "review", "sessions", "terminal"}
    if pane not in allowed:
        return tool_error(f"pane must be one of: {', '.join(sorted(allowed))}")
    return _emit("pane.focus", {"pane": pane}, "focus the pane")


def react_to_message(message_id: str, emoji: str) -> str:
    message_id = (message_id or "").strip()
    emoji = (emoji or "").strip()
    if not message_id or not emoji:
        return tool_error("message_id and emoji are required")
    if len(emoji) > 16:
        return tool_error("emoji must be a single emoji or short grapheme sequence")
    return _emit("message.react", {"message_id": message_id, "emoji": emoji}, "react to the message")


def read_window_below() -> str:
    return _request("window.read_below", {}, "identify the window below Clio")


def tour(action: str, steps: list[dict[str, Any]] | None = None) -> str:
    action = (action or "targets").strip().lower()
    if action not in {"targets", "show", "start", "stop"}:
        return tool_error("action must be targets, show, start, or stop")
    clean_steps: list[dict[str, str]] = []
    for raw in list(steps or [])[:20]:
        if not isinstance(raw, dict):
            continue
        target = str(raw.get("target") or "").strip()
        text = str(raw.get("text") or raw.get("content") or "").strip()
        title = str(raw.get("title") or "").strip()
        if target and text:
            clean_steps.append({"target": target, "text": text, "title": title})
    payload: dict[str, Any] = {"action": action, "steps": clean_steps}
    if action == "targets":
        return _request("tour.targets", {}, "discover tour targets")
    if action in {"show", "start"} and not clean_steps:
        return tool_error("steps are required for show/start")
    return _emit("tour.control", payload, "control the guided tour")


def apply_layout(preset: str, panes: list[str] | None = None) -> str:
    preset = (preset or "default").strip().lower()
    allowed = {"coding", "default", "focus", "research", "review"}
    if preset not in allowed:
        return tool_error(f"preset must be one of: {', '.join(sorted(allowed))}")
    clean_panes = [str(p).strip().lower() for p in list(panes or []) if str(p).strip()]
    return _emit("layout.apply", {"preset": preset, "panes": clean_panes}, "apply the layout")


_SCHEMAS: dict[str, dict[str, Any]] = {
    "open_preview": {
        "name": "open_preview",
        "description": "Open a web URL, localhost server, or file path in the Clio Desktop preview pane.",
        "parameters": {"type": "object", "properties": {"url": {"type": "string"}, "label": {"type": "string"}}, "required": ["url"]},
    },
    "close_preview": {
        "name": "close_preview",
        "description": "Close the Clio Desktop preview pane, or close the tab matching an optional URL or file path.",
        "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": []},
    },
    "read_preview": {
        "name": "read_preview",
        "description": "Read the active Clio Desktop preview identity and available rendered text using bounded character offsets.",
        "parameters": {"type": "object", "properties": {"start": {"type": "integer", "minimum": 0, "default": 0}, "count": {"type": "integer", "minimum": 1, "maximum": 20000, "default": 12000}}, "required": []},
    },
    "read_terminal": {
        "name": "read_terminal",
        "description": "Read the visible text from the active Clio Desktop terminal pane using bounded character offsets.",
        "parameters": {"type": "object", "properties": {"start": {"type": "integer", "minimum": 0, "default": 0}, "count": {"type": "integer", "minimum": 1, "maximum": 20000, "default": 12000}}, "required": []},
    },
    "close_terminal": {
        "name": "close_terminal",
        "description": "Close a Clio Desktop terminal tab without killing its process.",
        "parameters": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": []},
    },
    "focus_pane": {
        "name": "focus_pane",
        "description": "Reveal and focus a Clio Desktop pane.",
        "parameters": {"type": "object", "properties": {"pane": {"type": "string", "enum": ["chat", "files", "preview", "review", "sessions", "terminal"]}}, "required": ["pane"]},
    },
    "react_to_message": {
        "name": "react_to_message",
        "description": "Add or replace a short emoji reaction on a Clio Desktop message when reactions are enabled.",
        "parameters": {"type": "object", "properties": {"message_id": {"type": "string"}, "emoji": {"type": "string"}}, "required": ["message_id", "emoji"]},
    },
    "read_window_below": {
        "name": "read_window_below",
        "description": "Read metadata for the OS window immediately below the Clio Desktop window; never captures pixels.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "tour": {
        "name": "tour",
        "description": "Discover Clio Desktop tour targets or show, start, and stop a guided in-app tour.",
        "parameters": {"type": "object", "properties": {"action": {"type": "string", "enum": ["targets", "show", "start", "stop"], "default": "targets"}, "steps": {"type": "array", "maxItems": 20, "items": {"type": "object", "properties": {"target": {"type": "string"}, "title": {"type": "string"}, "text": {"type": "string"}}, "required": ["target", "text"]}}}, "required": []},
    },
    "apply_layout": {
        "name": "apply_layout",
        "description": "Apply a Clio Desktop pane layout preset for the current window.",
        "parameters": {"type": "object", "properties": {"preset": {"type": "string", "enum": ["coding", "default", "focus", "research", "review"], "default": "default"}, "panes": {"type": "array", "items": {"type": "string"}}}, "required": []},
    },
}

_HANDLERS = {
    "open_preview": lambda a: open_preview(a.get("url", ""), a.get("label", "")),
    "close_preview": lambda a: close_preview(a.get("url", "")),
    "read_preview": lambda a: read_preview(a.get("start", 0), a.get("count", 12000)),
    "read_terminal": lambda a: read_terminal(a.get("start", 0), a.get("count", 12000)),
    "close_terminal": lambda a: close_terminal(a.get("task_id", "")),
    "focus_pane": lambda a: focus_pane(a.get("pane", "")),
    "react_to_message": lambda a: react_to_message(a.get("message_id", ""), a.get("emoji", "")),
    "read_window_below": lambda a: read_window_below(),
    "tour": lambda a: tour(a.get("action", "targets"), a.get("steps")),
    "apply_layout": lambda a: apply_layout(a.get("preset", "default"), a.get("panes")),
}

for _name, _schema in _SCHEMAS.items():
    registry.register(
        name=_name,
        toolset="desktop_ui",
        schema=_schema,
        handler=lambda args, _tool_name=_name, **_kw: _HANDLERS[_tool_name](args),
        check_fn=desktop_ui_available,
        emoji="🖥️",
    )
