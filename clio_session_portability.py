"""Safe, loss-minimizing session text portability helpers."""
from __future__ import annotations

import html
import json
import re
import time
from typing import Any, Dict, Iterable, List

_FORMATS = {"jsonl", "markdown", "md", "html"}
_MAX_SESSIONS = 1000
_MAX_MESSAGES = 100000


def serialize_session(session: Dict[str, Any], *, format: str = "jsonl") -> str:
    """Serialize one exported SessionDB payload.

    Markdown and HTML include a machine-readable canonical payload as well as a
    human-readable transcript, allowing an exact import round trip.
    """
    fmt = format.lower()
    if fmt not in _FORMATS:
        raise ValueError(f"unsupported session format: {format}")
    canonical = json.dumps(session, ensure_ascii=False, separators=(",", ":"))
    if fmt == "jsonl":
        return canonical + "\n"
    title = str(session.get("title") or session.get("id") or "Session")
    messages = session.get("messages") or []
    if fmt in {"markdown", "md"}:
        lines = [f"# {title}", "", f"<!-- clio-session-json:{canonical} -->", ""]
        for message in messages:
            lines += [f"## {str(message.get('role') or 'message').title()}", "", _display(message.get("content")), ""]
        return "\n".join(lines)
    blocks = []
    for message in messages:
        blocks.append(
            '<section class="message"><h2>%s</h2><pre>%s</pre></section>'
            % (html.escape(str(message.get("role") or "message").title()), html.escape(_display(message.get("content"))))
        )
    safe_json = canonical.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return "<!doctype html><meta charset=utf-8><title>%s</title><h1>%s</h1>%s<script type=application/json id=clio-session>%s</script>" % (
        html.escape(title), html.escape(title), "".join(blocks), safe_json
    )


def _display(value: Any) -> str:
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
            if isinstance(decoded, (list, dict)):
                return json.dumps(decoded, ensure_ascii=False, indent=2)
        except (ValueError, TypeError):
            pass
        return value
    return json.dumps(value, ensure_ascii=False, indent=2) if value is not None else ""


def deserialize_sessions(text: str, *, format: str = "jsonl") -> List[Dict[str, Any]]:
    fmt = format.lower()
    if fmt not in _FORMATS:
        raise ValueError(f"unsupported session format: {format}")
    if fmt == "jsonl":
        values = [json.loads(line) for line in text.splitlines() if line.strip()]
    elif fmt in {"markdown", "md"}:
        match = re.search(r"<!-- clio-session-json:(.*?) -->", text, re.S)
        if not match:
            raise ValueError("Markdown does not contain a Clio session payload")
        values = [json.loads(match.group(1))]
    else:
        match = re.search(r"<script type=application/json id=clio-session>(.*?)</script>", text, re.S | re.I)
        if not match:
            raise ValueError("HTML does not contain a Clio session payload")
        values = [json.loads(match.group(1))]
    if len(values) > _MAX_SESSIONS or any(not isinstance(v, dict) for v in values):
        raise ValueError("invalid session payload")
    if sum(len(v.get("messages") or []) for v in values) > _MAX_MESSAGES:
        raise ValueError("session payload contains too many messages")
    return values


def import_sessions(db, sessions: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Import exported rows atomically; existing IDs are never overwritten."""
    payloads = list(sessions)
    session_columns = {r[1] for r in db._conn.execute("PRAGMA table_info(sessions)")}
    message_columns = {r[1] for r in db._conn.execute("PRAGMA table_info(messages)")}
    imported: List[str] = []
    skipped: List[str] = []

    def _json_text(value: Any) -> Any:
        return json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value

    def _do(conn):
        pending_parents = []
        for raw in payloads:
            sid = str(raw.get("id") or "").strip()
            messages = raw.get("messages") or []
            if not sid or not isinstance(messages, list) or any(not isinstance(m, dict) for m in messages):
                raise ValueError("each session needs an id and object messages")
            if conn.execute("SELECT 1 FROM sessions WHERE id=?", (sid,)).fetchone():
                skipped.append(sid)
                continue
            source = str(raw.get("source") or "import")
            # Runtime ownership/handoff fields are intentionally excluded.
            excluded = {"messages", "parent_session_id", "handoff_state", "handoff_platform", "handoff_error", "id", "system_prompt_hash"}
            row = {k: _json_text(v) for k, v in raw.items() if k in session_columns and k not in excluded}
            row["source"] = source
            row["started_at"] = float(raw.get("started_at") or time.time())
            cols = ["id", *row.keys()]
            conn.execute(
                f"INSERT INTO sessions ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",
                [sid, *row.values()],
            )
            count = tools = 0
            for message in messages:
                m = {k: _json_text(v) for k, v in message.items() if k in message_columns and k not in {"id", "session_id"}}
                m.setdefault("role", "user")
                m.setdefault("timestamp", time.time())
                m["session_id"] = sid
                cols = list(m)
                conn.execute(
                    f"INSERT INTO messages ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",
                    list(m.values()),
                )
                count += 1
                tc = message.get("tool_calls")
                tools += len(tc) if isinstance(tc, list) else (1 if tc else 0)
            conn.execute("UPDATE sessions SET message_count=?, tool_call_count=? WHERE id=?", (count, tools, sid))
            parent = raw.get("parent_session_id")
            if isinstance(parent, str) and parent and parent != sid:
                pending_parents.append((parent, sid))
            imported.append(sid)
        for parent, child in pending_parents:
            if conn.execute("SELECT 1 FROM sessions WHERE id=?", (parent,)).fetchone():
                conn.execute("UPDATE sessions SET parent_session_id=? WHERE id=?", (parent, child))
        return {"ok": True, "imported": len(imported), "skipped": len(skipped), "imported_ids": imported, "skipped_ids": skipped}
    return db._execute_write(_do)
