"""Render Clio tool calls as ACP tool-call updates."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from acp.schema import (
    ContentToolCallContent,
    FileEditToolCallContent,
    TextContentBlock,
    ToolCallLocation,
    ToolCallProgress,
    ToolCallStart,
)

from acp_adapter.edit_approval import EditProposal

TOOL_KIND_MAP = {
    "read_file": "read",
    "search_files": "search",
    "terminal": "execute",
    "process": "execute",
    "execute_code": "execute",
    "patch": "edit",
    "write_file": "edit",
    "web_search": "fetch",
    "web_extract": "fetch",
    "browser_navigate": "fetch",
    "browser_click": "fetch",
    "browser_type": "fetch",
    "todo": "other",
    "skill_view": "read",
    "skill_manage": "edit",
}


def make_tool_call_id() -> str:
    return f"tc-{uuid.uuid4().hex}"


def get_tool_kind(tool_name: str) -> str:
    return TOOL_KIND_MAP.get(tool_name, "other")


def _text_block(text: str) -> ContentToolCallContent:
    return ContentToolCallContent(type="content", content=TextContentBlock(type="text", text=text))


def _json_text(value: Any) -> str:
    try:
        return json.dumps(value, indent=2, ensure_ascii=False)
    except Exception:
        return str(value)


def build_tool_title(tool_name: str, args: dict[str, Any] | None = None) -> str:
    args = args or {}
    if tool_name == "terminal":
        cmd = str(args.get("command") or "")
        title = f"terminal: {cmd}" if cmd else "terminal"
        return title if len(title) < 110 else title[:100] + "..."
    if tool_name == "read_file":
        return f"read: {args.get('path', '')}".strip()
    if tool_name == "patch":
        return f"patch: {args.get('path', '')}".strip()
    if tool_name == "write_file":
        return f"write: {args.get('path', '')}".strip()
    if tool_name == "search_files":
        return f"search: {args.get('pattern', '')}".strip()
    if tool_name == "web_search":
        return f"search: {args.get('query', '')}".strip()
    if tool_name == "web_extract":
        urls = args.get("urls") or args.get("url") or ""
        if isinstance(urls, list):
            urls = ", ".join(str(u) for u in urls[:2])
        return f"extract: {urls}"
    if tool_name == "todo":
        todos = args.get("todos") or []
        count = len(todos) if isinstance(todos, list) else 0
        return f"todo ({count} item{'s' if count != 1 else ''})"
    if tool_name == "browser_navigate":
        return f"navigate: {args.get('url', '')}"
    if tool_name == "skill_view":
        name = args.get("name") or ""
        fp = args.get("file_path")
        return f"skill view ({name}/{fp})" if fp else f"skill view ({name})"
    if tool_name == "execute_code":
        code = str(args.get("code") or "").strip().splitlines()
        first = code[0] if code else ""
        return f"python: {first}" if first else "python"
    if tool_name == "skill_manage":
        name = args.get("name") or ""
        action = args.get("action") or "manage"
        fp = args.get("file_path")
        return f"skill {action}: {name}/{fp}" if fp else f"skill {action}: {name}"
    return tool_name


def extract_locations(tool_name: str | dict[str, Any], args: dict[str, Any] | None = None, result: Any = None) -> list[ToolCallLocation]:
    if isinstance(tool_name, dict):
        args = tool_name
        tool_name = ""
    args = args or {}
    locations: list[ToolCallLocation] = []
    path = args.get("path") or args.get("file_path")
    if path:
        locations.append(ToolCallLocation(path=str(path), line=args.get("line", args.get("offset"))))
    if tool_name == "search_files":
        data = _parse_json(result)
        for match in (data.get("matches") or []) if isinstance(data, dict) else []:
            if isinstance(match, dict) and match.get("path"):
                locations.append(ToolCallLocation(path=str(match["path"]), line=match.get("line")))
    return locations


def build_tool_start(
    tool_call_id: str,
    tool_name: str,
    args: dict[str, Any] | None = None,
    *,
    edit_diff: EditProposal | None = None,
) -> ToolCallStart:
    args = args or {}
    kind = get_tool_kind(tool_name)
    content = None
    if edit_diff is not None:
        content = [
            FileEditToolCallContent(
                type="diff",
                path=edit_diff.path,
                oldText=edit_diff.old_text,
                newText=edit_diff.new_text,
            )
        ]
    elif tool_name in {"patch", "write_file"}:
        content = [_text_block(f"Approval prompt shows the diff for {args.get('path', '')}.")]
    elif tool_name in {"terminal", "search_files", "todo", "skill_view", "browser_navigate"}:
        content = [_text_block(_format_start_text(tool_name, args))]
    elif tool_name == "execute_code":
        content = [_text_block(f"```python\n{args.get('code', '')}\n```")]
    elif tool_name == "skill_manage" and (
        (args.get("old_text") is not None and args.get("new_text") is not None)
        or (args.get("old_string") is not None and args.get("new_string") is not None)
    ):
        path = f"skills/{args.get('name')}/{args.get('file_path')}"
        content = [
            FileEditToolCallContent(
                type="diff",
                path=path,
                oldText=args.get("old_text", args.get("old_string")),
                newText=args.get("new_text", args.get("new_string")),
            )
        ]
    elif tool_name not in {"read_file", "web_extract"}:
        content = [_text_block(_json_text(args))]
    return ToolCallStart(
        toolCallId=tool_call_id,
        sessionUpdate="tool_call",
        title=build_tool_title(tool_name, args),
        kind=kind,
        content=content,
        locations=extract_locations(tool_name, args),
    )


def _format_start_text(tool_name: str, args: dict[str, Any]) -> str:
    if tool_name == "terminal":
        return f"$ {args.get('command', '')}"
    if tool_name == "search_files":
        return _json_text(args)
    if tool_name == "todo":
        todos = args.get("todos") or []
        return "\n".join(str(t.get("content", "")) for t in todos if isinstance(t, dict)) or _json_text(args)
    if tool_name == "skill_view":
        return str(args.get("name") or "")
    if tool_name == "browser_navigate":
        return _json_text({"url": args.get("url", "")})
    return _json_text(args)


def _parse_json(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return value
    try:
        return json.loads(text)
    except Exception:
        head = text.split("\n\n[Hint:", 1)[0].strip()
        if head != text:
            try:
                return json.loads(head)
            except Exception:
                pass
        return value


def _failed(tool_name: str, result: Any) -> bool:
    if isinstance(result, str) and result.startswith("Error executing tool"):
        return True
    data = _parse_json(result)
    if isinstance(data, dict):
        if data.get("success") is False or data.get("ok") is False:
            return True
        if tool_name in {"read_file", "web_extract", "patch", "write_file", "skill_manage"} and data.get("error"):
            return True
        try:
            if int(data.get("exit_code") or data.get("returncode") or 0) != 0:
                return True
        except Exception:
            pass
        if str(data.get("status") or "").lower() in {"failed", "error"}:
            return True
        if tool_name == "web_extract":
            for item in data.get("results") or []:
                if isinstance(item, dict) and item.get("error"):
                    return True
    return False


def _result_text(tool_name: str, result: Any, function_args: dict[str, Any] | None = None) -> str:
    data = _parse_json(result)
    args = function_args or {}
    if tool_name == "todo" and isinstance(data, dict):
        todos = data.get("todos") or []
        counts = {"completed": 0, "in_progress": 0, "pending": 0}
        lines = []
        for todo in todos:
            if not isinstance(todo, dict):
                continue
            status = str(todo.get("status") or "pending")
            content = str(todo.get("content") or "")
            if status == "completed":
                counts["completed"] += 1
                lines.append(f"✅ {content}")
            elif status == "in_progress":
                counts["in_progress"] += 1
                lines.append(f"- 🔄 {content}")
            else:
                counts["pending"] += 1
                lines.append(f"- {content}")
        lines.append(f"**Progress:** {counts['completed']} completed, {counts['in_progress']} in progress, {counts['pending']} pending")
        return "\n".join(lines)
    if tool_name == "execute_code" and isinstance(data, dict):
        code = data.get("exit_code", data.get("returncode", 0))
        return f"Exit code: {code}\n\n{data.get('output', '')}"
    if tool_name == "read_file":
        path = args.get("path") or (data.get("path") if isinstance(data, dict) else "")
        if isinstance(data, dict):
            return f"Read {path}\n\n```\n{data.get('content', '')}\n```"
        text = str(result)
        if len(text) > 5500:
            return text[:5200] + "\n\n[truncated]"
        return text
    if tool_name == "search_files" and isinstance(data, dict):
        if isinstance(data.get("files"), list):
            files = data.get("files") or []
            suffix = " use offset to page." if data.get("truncated") else ""
            return "File search results\n" + f"Found {data.get('total_count', len(files))} files; showing {len(files)}.{suffix}\n" + "\n".join(str(f) for f in files)
        lines = []
        for m in data.get("matches", []):
            if isinstance(m, dict):
                lines.append(f"{m.get('path')}:{m.get('line')}: {m.get('content')}")
        if data.get("truncated"):
            lines.append("Results truncated.")
        return f"Search results\nFound {data.get('total_count', len(lines))} matches\n" + ("\n".join(lines) or _json_text(data))
    if tool_name == "skill_view" and isinstance(data, dict):
        first_heading = str(data.get("content") or "").splitlines()[0].lstrip("# ").strip()
        return f"**Skill loaded** `{data.get('name', 'skill')}`\n\n{data.get('description', '')}\n\n{first_heading}\n\nFull skill content is available to the agent."
    if tool_name == "skill_manage" and isinstance(data, dict):
        return f"**✅ Skill updated** `{args.get('action', 'update')}` `{args.get('name', '')}` {args.get('file_path', '')}\n\n{data.get('message', '')}"
    if tool_name == "process" and isinstance(data, dict) and isinstance(data.get("processes"), list):
        rows = data["processes"]
        return f"Processes: {len(rows)}\n" + "\n".join(f"`{p.get('session_id')}` {p.get('status')} {p.get('pid')} {p.get('command')}" for p in rows if isinstance(p, dict))
    if tool_name == "delegate_task" and isinstance(data, dict):
        results = data.get("results") or []
        lines = [f"Delegation results: {len(results)} task"]
        for r in results:
            if isinstance(r, dict):
                tools = ", ".join(str(t.get("tool")) for t in r.get("tool_trace", []) if isinstance(t, dict))
                lines.append(f"{r.get('summary')} ({r.get('model')}) Tools: {tools}")
        return "\n".join(lines)
    if tool_name == "session_search" and isinstance(data, dict):
        return "Recent sessions\n" + "\n".join(f"{r.get('title')} - {r.get('preview')}" for r in data.get("results") or [] if isinstance(r, dict))
    if tool_name == "memory" and isinstance(data, dict):
        return f"Memory {args.get('action', 'update')} saved\n{args.get('content', '')}\n{data.get('usage', '')}"
    if tool_name == "web_extract" and isinstance(data, dict):
        for r in data.get("results") or []:
            if isinstance(r, dict) and r.get("error"):
                return f"Web extract failed: {r.get('url')} - {r.get('error')}"
    if tool_name in {"patch", "write_file"} and isinstance(data, dict):
        target = ", ".join(data.get("files_modified") or [Path(str(args.get("path", ""))).name])
        return f"✅ {tool_name} completed\n{target}".strip()
    if isinstance(data, dict) and "output" in data:
        return str(data["output"])
    if isinstance(data, dict):
        return _format_generic_dict(tool_name, data)
    if isinstance(data, list):
        return f"{tool_name}: {len(data)} items\n" + "\n".join(_format_generic_dict("", x) if isinstance(x, dict) else str(x) for x in data[:10])
    text = str(result)
    if len(text) > 5500:
        return text[:5200] + "\n\n[truncated]"
    return text


def _format_generic_dict(tool_name: str, data: dict[str, Any], indent: int = 0) -> str:
    prefix = f"{tool_name} result\n" if tool_name else ""
    pad = "  " * indent
    lines = []
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{pad}**{key}:**")
            lines.append(_format_generic_dict("", value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{pad}**{key}:** {len(value)} items")
            for item in value[:3]:
                lines.append(f"{pad}- {_format_generic_dict('', item, indent + 1) if isinstance(item, dict) else item}")
        else:
            lines.append(f"{pad}**{key}:** {value}")
    return prefix + "\n".join(lines)


def build_tool_complete(
    tool_call_id: str,
    tool_name: str,
    result: Any = None,
    *,
    function_args: dict[str, Any] | None = None,
    snapshot: Any = None,
) -> ToolCallProgress:
    status = "failed" if _failed(tool_name, result) else "completed"
    content = None
    raw_output = None
    if tool_name == "web_extract" and not _failed(tool_name, result):
        content = None
    else:
        content = [_text_block(_result_text(tool_name, result, function_args))]
    return ToolCallProgress(
        toolCallId=tool_call_id,
        sessionUpdate="tool_call_update",
        status=status,
        kind=get_tool_kind(tool_name),
        title=build_tool_title(tool_name, function_args),
        content=content,
        rawOutput=raw_output,
        locations=extract_locations(tool_name, function_args, result),
    )
