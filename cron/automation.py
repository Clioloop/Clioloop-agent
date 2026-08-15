"""Portable automation foundations shared by CLI and future UI surfaces.

This is intentionally additive to ``cron.jobs``: blueprints compile to normal
``create_job`` kwargs, monitor probes return deterministic change records, and
history/notepad delegate to the existing durable stores.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import subprocess
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class BlueprintSlot:
    name: str
    type: str = "text"  # text | time | enum
    label: str = ""
    default: Optional[str] = None
    options: tuple[str, ...] = ()
    required: bool = True


@dataclass(frozen=True)
class AutomationBlueprint:
    key: str
    title: str
    description: str
    schedule_template: str
    prompt_template: str
    slots: tuple[BlueprintSlot, ...] = field(default_factory=tuple)
    deliver: str = "origin"


CATALOG = (
    AutomationBlueprint(
        "morning-brief", "Morning briefing", "Daily concise briefing.",
        "{minute} {hour} * * *", "Produce a concise morning briefing for the user.",
        (BlueprintSlot("time", "time", "What time?", "08:00"),),
    ),
    AutomationBlueprint(
        "weekly-review", "Weekly review", "Weekly recap and forward plan.",
        "{minute} {hour} * * {dow}", "Review the past week and propose priorities for next week.",
        (BlueprintSlot("time", "time", "What time?", "18:00"),
         BlueprintSlot("day", "enum", "Which day?", "sunday", ("sunday", "monday", "friday", "saturday"))),
    ),
    AutomationBlueprint(
        "custom-reminder", "Custom reminder", "Recurring reminder in your words.",
        "{minute} {hour} * * *", "Remind the user: {what}",
        (BlueprintSlot("what", "text", "Remind me to"), BlueprintSlot("time", "time", "What time?", "09:00")),
    ),
)

_DAY = {"sunday": "0", "monday": "1", "tuesday": "2", "wednesday": "3", "thursday": "4", "friday": "5", "saturday": "6"}


def get_blueprint(key: str) -> Optional[AutomationBlueprint]:
    key = str(key).strip().lower()
    return next((item for item in CATALOG if item.key == key), None)


def blueprint_schema(blueprint: AutomationBlueprint) -> dict[str, Any]:
    return {"key": blueprint.key, "title": blueprint.title, "description": blueprint.description,
            "fields": [asdict(slot) for slot in blueprint.slots]}


def fill_blueprint(blueprint: AutomationBlueprint, values: Mapping[str, Any]) -> dict[str, Any]:
    known = {slot.name for slot in blueprint.slots}
    unknown = set(values) - known - {"deliver"}
    if unknown:
        raise ValueError(f"unknown blueprint slot(s): {', '.join(sorted(unknown))}")
    resolved: dict[str, str] = {}
    for slot in blueprint.slots:
        value = values.get(slot.name, slot.default)
        if value in (None, "") and slot.required:
            raise ValueError(f"missing required slot: {slot.name}")
        value = "" if value is None else str(value).strip()
        if slot.type == "enum" and slot.options and value not in slot.options:
            raise ValueError(f"invalid {slot.name}: choose {', '.join(slot.options)}")
        if slot.type == "time":
            parts = value.split(":")
            if len(parts) != 2 or not all(p.isdigit() for p in parts):
                raise ValueError(f"invalid time for {slot.name}: {value}")
            hour, minute = map(int, parts)
            if not 0 <= hour <= 23 or not 0 <= minute <= 59:
                raise ValueError(f"invalid time for {slot.name}: {value}")
            resolved.update(hour=str(hour), minute=str(minute))
        resolved[slot.name] = value
    if "day" in resolved:
        resolved["dow"] = _DAY.get(resolved["day"].lower(), resolved["day"])
    try:
        schedule = blueprint.schedule_template.format(**resolved)
        prompt = blueprint.prompt_template.format(**resolved)
    except KeyError as exc:
        raise ValueError(f"unresolved blueprint slot: {exc.args[0]}") from exc
    return {"schedule": schedule, "prompt": prompt, "name": blueprint.title,
            "deliver": str(values.get("deliver") or blueprint.deliver), "blueprint": blueprint.key}


def create_from_blueprint(key: str, values: Mapping[str, Any]) -> dict[str, Any]:
    blueprint = get_blueprint(key)
    if blueprint is None:
        raise KeyError(f"unknown blueprint: {key}")
    spec = fill_blueprint(blueprint, values)
    from cron.jobs import create_job
    job = create_job(**{k: v for k, v in spec.items() if k != "blueprint"})
    job["blueprint"] = key
    return job


def monitor_probe(*, command: Optional[str] = None, url: Optional[str] = None,
                  previous: Optional[str] = None, timeout: float = 30.0) -> dict[str, Any]:
    """Run exactly one bounded source and return hash/change/diff without side effects."""
    if bool(command) == bool(url):
        raise ValueError("exactly one of command or url is required")
    if command:
        proc = subprocess.run(command, shell=True, capture_output=True, timeout=timeout, check=False)
        output = (proc.stdout + proc.stderr).decode("utf-8", errors="replace")
        if proc.returncode:
            raise RuntimeError(f"monitor command failed ({proc.returncode}): {output[-1000:]}")
    else:
        with urllib.request.urlopen(str(url), timeout=timeout) as response:  # noqa: S310 - explicit user URL
            output = response.read(1024 * 1024).decode("utf-8", errors="replace")
    digest = hashlib.sha256(output.encode("utf-8")).hexdigest()
    previous = previous if previous is not None else None
    changed = previous is None or previous != output
    diff = ""
    if previous is not None and changed:
        diff = "\n".join(difflib.unified_diff(previous.splitlines(), output.splitlines(), "before", "after", lineterm=""))[-8000:]
    return {"changed": changed, "sha256": digest, "output": output, "diff": diff}


def history(*, job_id: Optional[str] = None, limit: int = 100, path=None) -> list[Mapping[str, Any]]:
    from cron.contracts import CronBackend
    return CronBackend(path).execution_history(job_id, limit=limit)


def notepad(action: str, job_id: str, *, key: Optional[str] = None, value: Optional[str] = None) -> Any:
    from cron import notepad as store
    action = action.lower()
    if action == "list": return store.list_notes(job_id)
    if action == "get": return store.get_note(job_id, key or "")
    if action == "set": return store.set_note(job_id, key or "", value or "")
    if action in {"delete", "remove"}: return store.delete_note(job_id, key or "")
    if action == "clear": return store.clear_notepad(job_id)
    raise ValueError(f"unsupported notepad action: {action}")


__all__ = ["BlueprintSlot", "AutomationBlueprint", "CATALOG", "get_blueprint", "blueprint_schema",
           "fill_blueprint", "create_from_blueprint", "monitor_probe", "history", "notepad"]
