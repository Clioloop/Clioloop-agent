#!/usr/bin/env python3
"""
Todo Tool Module - Planning & Task Management (Optimized Version)
"""

import json
from typing import Dict, Any, List, Optional

# Valid status values for todo items
VALID_STATUSES = {"pending", "in_progress", "completed", "cancelled"}


class TodoStore:
    """
    In-memory todo list. One instance per AIAgent (one per session).
    """

    def __init__(self):
        self._items: List[Dict[str, str]] = []

    def write(self, todos: List[Dict[str, Any]], merge: bool = False) -> List[Dict[str, str]]:
        """
        Write todos. Returns the full current list after writing.
        """
        if not merge:
            # Replace mode: new list entirely
            self._items = [self._validate(t) for t in self._dedupe_by_id(todos)]
        else:
            # Merge mode: update existing items by id, append new ones
            existing = {item["id"]: item for item in self._items}
            new_items = []
            
            for t in self._dedupe_by_id(todos):
                item_id = str(t.get("id", "")).strip()
                if not item_id:
                    continue

                if item_id in existing:
                    # Update fields in-place with strict clean boundaries
                    if "content" in t and t["content"]:
                        existing[item_id]["content"] = str(t["content"]).strip()
                    if "status" in t and t["status"]:
                        status = str(t["status"]).strip().lower()
                        if status in VALID_STATUSES:
                            existing[item_id]["status"] = status
                else:
                    # Validate and prepare append queue
                    validated = self._validate(t)
                    existing[validated["id"]] = validated
                    new_items.append(validated)

            # Rebuild maintaining exact original insertion order + new appends
            seen = set()
            rebuilt = []
            for item in self._items:
                if item["id"] not in seen:
                    rebuilt.append(existing[item["id"]])
                    seen.add(item["id"])
            
            # Append new valid tasks at the end
            for item in new_items:
                if item["id"] not in seen:
                    rebuilt.append(item)
                    seen.add(item["id"])
                    
            self._items = rebuilt
        return self.read()

    def read(self) -> List[Dict[str, str]]:
        """Return a copy of the current list."""
        return [item.copy() for item in self._items]

    def has_items(self) -> bool:
        """Check if there are any items in the list."""
        return bool(self._items)

    def format_for_injection(self) -> Optional[str]:
        """
        Render the todo list for post-compression injection using memory-efficient generators.
        """
        if not self._items:
            return None

        markers = {
            "completed": "[x]",
            "in_progress": "[>]",
            "pending": "[ ]",
            "cancelled": "[~]",
        }

        # Memory efficient streaming structure for active tasks
        active_generator = (
            item for item in self._items 
            if item["status"] in {"pending", "in_progress"}
        )

        lines = ["[Your active task list was preserved across context compression]"]
        has_active = False
        
        for item in active_generator:
            has_active = True
            marker = markers.get(item["status"], "[?]")
            lines.append(f"- {marker} {item['id']}. {item['content']} ({item['status']})")

        return "\n".join(lines) if has_active else None

    @staticmethod
    def _validate(item: Dict[str, Any]) -> Dict[str, str]:
        """Validate and normalize a todo item."""
        item_id = str(item.get("id", "")).strip() or "?"
        content = str(item.get("content", "")).strip() or "(no description)"
        status = str(item.get("status", "pending")).strip().lower()
        if status not in VALID_STATUSES:
            status = "pending"

        return {"id": item_id, "content": content, "status": status}

    @staticmethod
    def _dedupe_by_id(todos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Collapse duplicate ids, keeping the last occurrence in its position."""
        last_index: Dict[str, int] = {}
        for i, item in enumerate(todos):
            item_id = str(item.get("id", "")).strip() or "?"
            last_index[item_id] = i
        return [todos[i] for i in sorted(last_index.values())]


def todo_tool(
    todos: Optional[List[Dict[str, Any]]] = None,
    merge: bool = False,
    store: Optional[TodoStore] = None,
) -> str:
    """Single entry point for the todo tool."""
    if store is None:
        return tool_error("TodoStore not initialized")

    if todos is not None:
        items = store.write(todos, merge)
    else:
        items = store.read()

    summary = {"total": len(items), "pending": 0, "in_progress": 0, "completed": 0, "cancelled": 0}
    for i in items:
        status = i["status"]
        if status in summary:
            summary[status] += 1

    return json.dumps({"todos": items, "summary": summary}, ensure_ascii=False)


def check_todo_requirements() -> bool:
    return True

# =============================================================================
# OpenAI Function-Calling Schema
# =============================================================================
TODO_SCHEMA = {
    "name": "todo",
    "description": (
        "Manage your task list for the current session. Use for complex tasks "
        "with 3+ steps or when the user provides multiple tasks. "
        "Call with no parameters to read the current list.\n\n"
        "Writing:\n"
        "- Provide 'todos' array to create/update items\n"
        "- merge=false (default): replace the entire list with a fresh plan\n"
        "- merge=true: update existing items by id, add any new ones\n\n"
        "Each item: {id: string, content: string, "
        "status: pending|in_progress|completed|cancelled}\n"
        "List order is priority. Only ONE item in_progress at a time.\n"
        "Mark items completed immediately when done. If something fails, "
        "cancel it and add a revised item.\n\n"
        "Always returns the full current list."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "description": "Task items to write. Omit to read current list.",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Unique item identifier"},
                        "content": {"type": "string", "description": "Task description"},
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed", "cancelled"],
                            "description": "Current status"
                        }
                    },
                    "required": ["id", "content", "status"]
                }
            },
            "merge": {
                "type": "boolean",
                "description": "true: update existing items by id, add new ones. false (default): replace entire list.",
                "default": False
            }
        },
        "required": []
    }
}

from tools.registry import registry, tool_error

registry.register(
    name="todo",
    toolset="todo",
    schema=TODO_SCHEMA,
    handler=lambda args, **kw: todo_tool(
        todos=args.get("todos"), merge=args.get("merge", False), store=kw.get("store")),
    check_fn=check_todo_requirements,
    emoji="📋",
)
