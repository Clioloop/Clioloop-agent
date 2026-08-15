"""``clio journey`` command: inspect and safely mutate learned nodes."""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import tempfile
from typing import Any, Optional


def _payload() -> dict[str, Any]:
    from agent.learning_graph import build_learning_graph
    return build_learning_graph()


def _show(args: argparse.Namespace) -> int:
    payload = _payload()
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    nodes = sorted(payload["nodes"], key=lambda row: (row.get("timestamp") or 0, row["id"]))
    if not nodes:
        print("No learning yet. Learned profile skills and memories will appear here.")
        return 0
    stats = payload["stats"]
    print(f"Journey: {stats['learned_skills']} learned skills, {stats['memory_nodes']} memories")
    for node in nodes:
        glyph = "◆" if node["kind"] == "memory" else "●"
        print(f"{glyph} {node['id']}  {node.get('label', '')}")
    return 0


def _detail(args: argparse.Namespace) -> int:
    from agent.learning_mutations import node_detail
    result = node_detail(args.node)
    if not result.get("ok"):
        print(result.get("message", "not found"))
        return 1
    print(result["content"])
    return 0


def _delete(args: argparse.Namespace) -> int:
    from agent.learning_mutations import delete_node
    result = delete_node(args.node)
    print(result.get("message", "failed"))
    return 0 if result.get("ok") else 1


def _editor(initial: str, suffix: str) -> Optional[str]:
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "vi"
    path = ""
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=suffix, delete=False) as handle:
            handle.write(initial)
            path = handle.name
        if subprocess.call([*shlex.split(editor), path]) != 0:
            return None
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except OSError as exc:
        print(f"editor failed: {exc}")
        return None
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass


def _edit(args: argparse.Namespace) -> int:
    from agent.learning_mutations import edit_node, node_detail
    detail = node_detail(args.node)
    if not detail.get("ok"):
        print(detail.get("message", "not found"))
        return 1
    content = args.content
    if content is None:
        content = _editor(detail["content"], ".md" if detail["kind"] == "skill" else ".txt")
    if content is None or content.strip() == detail["content"].strip():
        print("no changes")
        return 0
    result = edit_node(args.node, content)
    print(result.get("message", "failed"))
    return 0 if result.get("ok") else 1


def register_cli(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Print graph payload as JSON")
    parser.set_defaults(func=_show)
    sub = parser.add_subparsers(dest="journey_action")
    show = sub.add_parser("list", help="List learned skill and memory node ids")
    show.add_argument("--json", action="store_true")
    show.set_defaults(func=_show)
    inspect = sub.add_parser("inspect", help="Print a node's editable content")
    inspect.add_argument("node")
    inspect.set_defaults(func=_detail)
    edit = sub.add_parser("edit", help="Edit a node (memory atomically; skill through skill manager)")
    edit.add_argument("node")
    edit.add_argument("--content", help="Replacement content; omit to open $EDITOR")
    edit.set_defaults(func=_edit)
    delete = sub.add_parser("delete", help="Delete memory or safely archive a learned skill")
    delete.add_argument("node")
    delete.set_defaults(func=_delete)


__all__ = ["register_cli"]
