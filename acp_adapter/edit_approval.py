"""Pre-edit approval bridge for ACP sessions."""

from __future__ import annotations

import contextvars
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from acp.schema import FileEditToolCallContent, ToolCallProgress

_edit_approval_requester: contextvars.ContextVar[Callable[["EditProposal"], bool] | None] = (
    contextvars.ContextVar("clio_acp_edit_approval_requester", default=None)
)


@dataclass
class EditProposal:
    tool_name: str
    path: str
    old_text: str | None
    new_text: str
    arguments: dict[str, Any]


def set_edit_approval_requester(requester: Callable[[EditProposal], bool] | None) -> None:
    _edit_approval_requester.set(requester)


def clear_edit_approval_requester() -> None:
    _edit_approval_requester.set(None)


def build_acp_edit_tool_call(proposal: EditProposal) -> ToolCallProgress:
    return ToolCallProgress(
        toolCallId="edit-approval",
        sessionUpdate="tool_call_update",
        kind="edit",
        status="pending",
        title=f"{proposal.tool_name}: {proposal.path}",
        rawInput={"tool": proposal.tool_name, "arguments": proposal.arguments},
        content=[
            FileEditToolCallContent(
                type="diff",
                path=proposal.path,
                oldText=proposal.old_text,
                newText=proposal.new_text,
            )
        ],
    )


def _read_text(path: str) -> str | None:
    try:
        p = Path(path)
        if p.exists() and p.is_file():
            return p.read_text(encoding="utf-8")
    except Exception:
        return None
    return None


def _proposal_for(tool_name: str, args: dict[str, Any]) -> EditProposal | None:
    if tool_name == "write_file":
        path = str(args.get("path") or "")
        if not path:
            return None
        return EditProposal(tool_name, path, _read_text(path), str(args.get("content") or ""), dict(args))
    if tool_name == "patch":
        path = str(args.get("path") or "")
        if not path:
            return None
        before = _read_text(path)
        old = str(args.get("old_string") or "")
        new = str(args.get("new_string") or "")
        after = before
        if before is not None and old:
            after = before.replace(old, new, 1)
        return EditProposal(tool_name, path, before, after if after is not None else new, dict(args))
    return None


def _is_sensitive(path: str, new_text: str | None = None) -> bool:
    name = Path(path).name.lower()
    if name in {".env", ".env.local", ".envrc"} or name.endswith(".pem") or name.endswith(".key"):
        return True
    text = (new_text or "").upper()
    return "SECRET=" in text or "API_KEY=" in text or "TOKEN=" in text


def should_auto_approve_edit(proposal: EditProposal, policy: str, cwd: str | None = None) -> bool:
    if _is_sensitive(proposal.path, proposal.new_text):
        return False
    normalized = (policy or "").strip().lower()
    if normalized in {"dont_ask", "always", "auto", "accept_all"}:
        return True
    if normalized != "workspace_session":
        return False
    try:
        target = Path(proposal.path).resolve()
        workspace = Path(cwd or ".").resolve()
        if target == workspace or workspace in target.parents:
            return True
        tmp = Path(tempfile.gettempdir()).resolve()
        return target == tmp or tmp in target.parents
    except Exception:
        return False


def maybe_require_edit_approval(tool_name: str, function_args: dict[str, Any]) -> str | None:
    requester = _edit_approval_requester.get()
    if requester is None or tool_name not in {"write_file", "patch"}:
        return None
    proposal = _proposal_for(tool_name, function_args)
    if proposal is None:
        return None
    try:
        approved = bool(requester(proposal))
    except Exception:
        approved = False
    if approved:
        return None
    return json.dumps({"error": "Edit approval denied"}, ensure_ascii=False)

