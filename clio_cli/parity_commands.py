"""Shared implementations for portable Hermes-parity slash commands.

The classic CLI and gateway both call :func:`execute`; command behavior must
live here rather than drifting into surface-specific formatter code.
"""
from __future__ import annotations

import hashlib
import os
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SlashResult:
    text: str = ""
    agent_seed: str | None = None
    config_updates: dict[str, Any] = field(default_factory=dict)


def _load_config() -> dict[str, Any]:
    from clio_cli.config import load_config

    cfg = load_config() or {}
    return cfg if isinstance(cfg, dict) else {}


def _set_config(path: str, value: Any) -> None:
    from clio_cli.config import save_config

    cfg = _load_config()
    node = cfg
    parts = path.split(".")
    for key in parts[:-1]:
        child = node.get(key)
        if not isinstance(child, dict):
            child = {}
            node[key] = child
        node = child
    node[parts[-1]] = value
    save_config(cfg)


def _config_value(path: str, default: Any = None) -> Any:
    value: Any = _load_config()
    for part in path.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    return default if value is None else value


def _toggle(path: str, arg: str, *, default: bool = False) -> SlashResult:
    current = bool(_config_value(path, default))
    if arg in {"", "toggle"}:
        enabled = not current
    elif arg == "status":
        return SlashResult(f"{path}: {'on' if current else 'off'}")
    elif arg in {"on", "off"}:
        enabled = arg == "on"
    else:
        command = path.rsplit(".", 1)[-1]
        return SlashResult(f"Usage: /{command} [on|off|status]")
    _set_config(path, enabled)
    return SlashResult(
        f"{path}: {'on' if enabled else 'off'}",
        config_updates={path: enabled},
    )


def _portal(kind: str) -> SlashResult:
    from clio_cli.auth import DEFAULT_MANAGED_PORTAL_URL
    from clio_cli.portal_account import get_managed_provider_account_info

    info = get_managed_provider_account_info(force_fresh=True)
    url = str((info.raw or {}).get("portal_url") or DEFAULT_MANAGED_PORTAL_URL).rstrip("/")
    if not info.logged_in:
        return SlashResult(
            f"Omni Loop Portal is not connected. Run `clio auth add managed` or visit {url}."
        )
    plan = str((info.raw or {}).get("plan") or ("free" if info.is_free_tier else "paid"))
    suffix = "billing" if kind == "topup" else "pricing"
    return SlashResult(f"Omni Loop Portal plan: {plan}. Manage {kind}: {url}/{suffix}")


def _catalog_text() -> str:
    from cron.automation import CATALOG

    return "Automation blueprints:\n" + "\n".join(
        f"- {blueprint.key}: {blueprint.description}" for blueprint in CATALOG
    )


def _resolve_learning_record(rows: list[dict[str, Any]], ref: str) -> dict[str, Any] | None:
    ref = ref.strip()
    if ref.isdigit():
        index = int(ref) - 1
        return rows[index] if 0 <= index < len(rows) else None
    lowered = ref.lower()
    return next(
        (
            row
            for row in rows
            if str(row.get("id", "")) == ref
            or str(row.get("title", "")).lower() == lowered
        ),
        None,
    )


def _suggestions(args: str) -> SlashResult:
    from agent import learning_records

    tokens = shlex.split(args)
    sub = tokens[0].lower() if tokens else ""
    pending = learning_records.list_records(kind="suggestion", status="pending")
    if sub == "catalog":
        return SlashResult(_catalog_text())
    if not sub:
        if not pending:
            return SlashResult(
                "No pending automation suggestions. Browse starter blueprints with "
                "`/blueprint <name>`:\n" + _catalog_text()
            )
        lines = ["Automation suggestions — accept or dismiss by number:"]
        for index, row in enumerate(pending, 1):
            schedule = str((row.get("metadata") or {}).get("job_spec", {}).get("schedule") or "?")
            lines.append(f"- {index}. {row.get('title', '(untitled)')} [{schedule}]")
        return SlashResult("\n".join(lines))
    if sub not in {"accept", "dismiss", "reject"} or len(tokens) < 2:
        return SlashResult(
            "Usage: /suggestions [catalog|accept <number|id>|dismiss <number|id>]"
        )
    row = _resolve_learning_record(pending, " ".join(tokens[1:]))
    if row is None:
        return SlashResult("No matching pending automation suggestion.")
    if sub in {"dismiss", "reject"}:
        learning_records.update_record(str(row["id"]), "dismissed")
        return SlashResult(f"Dismissed suggestion: {row.get('title', row['id'])}")
    spec = (row.get("metadata") or {}).get("job_spec")
    if not isinstance(spec, dict):
        return SlashResult("That suggestion has no runnable automation specification.")
    from cron.jobs import create_job

    job = create_job(**spec)
    learning_records.update_record(
        str(row["id"]), "accepted", note=f"cron job {job.get('id', '')}"
    )
    return SlashResult(
        f"Scheduled '{job.get('name') or row.get('title')}' ({job.get('schedule', '')})."
    )


def _pet_root() -> Path:
    from clio_constants import get_clio_home

    return get_clio_home() / "pets"


def _pet(args: str) -> SlashResult:
    tokens = shlex.split(args)
    sub = tokens[0].lower() if tokens else "toggle"
    root = _pet_root()
    installed = sorted(path.stem for path in root.glob("*.txt")) if root.exists() else []
    active = str(_config_value("display.pet.slug", "") or "")
    enabled = bool(_config_value("display.pet.enabled", False))
    if sub == "list":
        if not installed:
            return SlashResult("No ASCII mascots installed. Create one with `/hatch <description>`.")
        return SlashResult(
            "Installed ASCII mascots:\n"
            + "\n".join(f"- {'* ' if slug == active else ''}{slug}" for slug in installed)
        )
    if sub in {"off", "disable"}:
        _set_config("display.pet.enabled", False)
        return SlashResult("Terminal mascot: off", config_updates={"display.pet.enabled": False})
    if sub in {"toggle", "status"}:
        if sub == "status":
            return SlashResult(
                f"Terminal mascot: {'on' if enabled else 'off'}"
                + (f" ({active})" if active else " (none selected)")
            )
        if not active or active not in installed:
            return SlashResult("No mascot selected. Create one with `/hatch <description>`.")
        enabled = not enabled
        _set_config("display.pet.enabled", enabled)
        return SlashResult(
            f"Terminal mascot: {'on' if enabled else 'off'} ({active})",
            config_updates={"display.pet.enabled": enabled},
        )
    slug = re.sub(r"[^a-z0-9-]+", "-", sub).strip("-")
    if slug not in installed:
        return SlashResult(f"Mascot '{slug}' is not installed. Run `/pet list`.")
    _set_config("display.pet.slug", slug)
    _set_config("display.pet.enabled", True)
    art = (root / f"{slug}.txt").read_text(encoding="utf-8").rstrip()
    return SlashResult(
        f"Terminal mascot selected: {slug}\n{art}",
        config_updates={"display.pet.slug": slug, "display.pet.enabled": True},
    )


def _hatch(description: str) -> SlashResult:
    description = description.strip()
    if not description:
        return SlashResult("Usage: /hatch <description>")
    slug = re.sub(r"[^a-z0-9-]+", "-", description.lower()).strip("-")[:32] or "mascot"
    digest = hashlib.sha256(description.encode("utf-8")).digest()
    eyes = ("o", "O", "^", "•")[digest[0] % 4]
    ears = (("/\\", "/\\"), ("/\"", "\"\\"), ("/ᐠ", "ᐟ\\"))[digest[1] % 3]
    art = f" {ears[0]}___{ears[1]}\n( {eyes} w {eyes} )\n >  {slug[:12]}  <\n"
    root = _pet_root()
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"{slug}.txt"
    target.write_text(art, encoding="utf-8")
    try:
        target.chmod(0o600)
    except OSError:
        pass
    _set_config("display.pet.slug", slug)
    _set_config("display.pet.enabled", True)
    return SlashResult(
        f"Hatched ASCII mascot '{slug}' at {target}:\n{art.rstrip()}",
        config_updates={"display.pet.slug": slug, "display.pet.enabled": True},
    )


def execute(
    command: str,
    args: str = "",
    *,
    session_id: str = "",
    agent: Any = None,
    fusion_config: Any = None,
) -> SlashResult:
    """Execute a parity command without surface-specific presentation."""
    command = command.lower().strip()
    args = (args or "").strip()
    low = args.lower()

    if command == "version":
        from clio_cli import __version__

        return SlashResult(f"Clio Agent {__version__}")

    if command == "export":
        from clio_cli.profiles import export_profile, get_active_profile_name

        tokens = shlex.split(args)
        name = get_active_profile_name()
        if tokens and not tokens[0].startswith("-"):
            name = tokens.pop(0)
        output = f"{name}.tar.gz"
        for option in ("-o", "--output"):
            if option in tokens:
                index = tokens.index(option)
                if index + 1 >= len(tokens):
                    return SlashResult(f"Usage: /export [profile] [{option} output.tar.gz]")
                output = tokens[index + 1]
        return SlashResult(f"Exported profile to {export_profile(name, output)}")

    if command == "import":
        from clio_cli.profiles import import_profile

        tokens = shlex.split(args)
        if not tokens:
            return SlashResult("Usage: /import <archive.tar.gz> [--name <name>]")
        name = None
        if "--name" in tokens:
            index = tokens.index("--name")
            if index + 1 >= len(tokens):
                return SlashResult("Usage: /import <archive.tar.gz> [--name <name>]")
            name = tokens[index + 1]
        return SlashResult(f"Imported profile to {import_profile(tokens[0], name=name)}")

    if command in {"subscription", "topup"}:
        return _portal(command)

    if command == "approvals":
        from tools.approval import _get_approval_mode

        if not args or low == "status":
            return SlashResult(f"Approval mode: {_get_approval_mode()}")
        if low not in {"manual", "smart", "off"}:
            return SlashResult("Usage: /approvals [manual|smart|off]")
        _set_config("approvals.mode", low)
        return SlashResult(f"Approval mode: {low}", config_updates={"approvals.mode": low})

    if command == "battery":
        return _toggle("display.battery", low)
    if command == "timestamps":
        return _toggle("display.timestamps", low)
    if command == "wake":
        return _toggle("voice.wake_word", low)

    if command == "egress":
        if low not in {"", "status"}:
            return SlashResult("Usage: /egress [status]")
        proxy = os.getenv("CLIO_EGRESS_PROXY") or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
        allow_hosts = _config_value("plugins.egress.allow_hosts", [])
        detail = f"; plugin allowlist: {', '.join(map(str, allow_hosts))}" if allow_hosts else ""
        return SlashResult(
            f"Egress proxy: {proxy}{detail}"
            if proxy
            else "Egress proxy: not configured; terminal backend network policy remains authoritative."
            + detail
        )

    if command == "heartbeat":
        from clio_cli.heartbeat import HeartbeatManager, parse_interval

        if not session_id:
            return SlashResult("Heartbeat requires an active session.")
        manager = HeartbeatManager(session_id)
        if not args or low == "status":
            return SlashResult(manager.status_line())
        if low == "pause":
            manager.pause()
            return SlashResult(manager.status_line())
        if low == "resume":
            manager.resume()
            return SlashResult(manager.status_line())
        if low in {"clear", "stop"}:
            manager.clear()
            return SlashResult("Heartbeat cleared.")
        words = args.split()
        if words and words[0].lower() == "every":
            words = words[1:]
        if len(words) < 2:
            return SlashResult("Usage: /heartbeat every <interval> <prompt>")
        interval_words = 2 if len(words) >= 3 and words[0].replace(".", "", 1).isdigit() else 1
        seconds = parse_interval(" ".join(words[:interval_words]))
        if seconds is None or seconds < 0:
            return SlashResult("Invalid heartbeat interval (minimum 60s).")
        prompt = " ".join(words[interval_words:]).strip()
        if not prompt:
            return SlashResult("Usage: /heartbeat every <interval> <prompt>")
        manager.set(prompt, seconds)
        return SlashResult(manager.status_line())

    if command == "loop":
        from clio_cli.loops import LoopManager, parse_loop_args

        if not session_id:
            return SlashResult("Loop requires an active session.")
        manager = LoopManager(session_id)
        if not args or low == "status":
            return SlashResult(manager.status_line())
        if low == "pause":
            manager.pause()
            return SlashResult(manager.status_line())
        if low == "resume":
            manager.resume()
            return SlashResult(manager.status_line())
        if low in {"clear", "stop"}:
            manager.clear()
            return SlashResult("Loop cleared.")
        parsed = parse_loop_args(args)
        if parsed.get("error"):
            return SlashResult(f"Loop error: {parsed['error']}")
        manager.set(
            parsed["prompt"],
            interval_seconds=parsed["interval_seconds"],
            times=parsed["times"],
            until=parsed["until"],
        )
        return SlashResult(manager.status_line())

    if command == "suggestions":
        return _suggestions(args)

    if command == "blueprint":
        from cron.automation import create_from_blueprint

        if not args:
            return SlashResult(_catalog_text())
        tokens = shlex.split(args)
        values = dict(token.split("=", 1) for token in tokens[1:] if "=" in token)
        try:
            job = create_from_blueprint(tokens[0], values)
        except (KeyError, ValueError) as exc:
            return SlashResult(f"Blueprint error: {exc}")
        return SlashResult(
            f"Created cron job {job.get('id') or job.get('name')}: {job.get('schedule')}"
        )

    if command == "memory":
        if low not in {"", "status"}:
            return SlashResult("Usage: /memory [status]")
        from clio_constants import get_clio_home

        root = get_clio_home() / "memories"
        count = sum(path.is_file() for path in root.rglob("*")) if root.exists() else 0
        return SlashResult(f"Memory store: {root} ({count} files)")

    if command == "refine":
        from agent.learn_prompt import build_refinement_prompt
        from agent.learning_records import add_record

        record = add_record(
            "refinement",
            args or "Conversation refinement",
            detail="Review requested from /refine",
            source="slash-command",
        )
        return SlashResult(
            f"Refinement review queued ({record['id']}).",
            build_refinement_prompt(args),
        )

    if command == "moa":
        if not args:
            return SlashResult("Usage: /moa <prompt>")
        from agent.fusion_engine import FusionConfig, get_fusion_config, set_fusion_config

        cfg = fusion_config
        if cfg is None and agent is not None:
            cfg = get_fusion_config(agent)
        if cfg is None:
            cfg = FusionConfig.from_dict(_load_config().get("fusion") or {})
        if not cfg.is_complete():
            return SlashResult("Model Fusion is not configured. Run `/fusion` first, then retry `/moa <prompt>`.")
        cfg.enabled = True
        if agent is not None:
            set_fusion_config(agent, cfg)
        return SlashResult("Model Fusion prompt queued.", args)

    if command == "pet":
        return _pet(args)
    if command == "hatch":
        return _hatch(args)

    return SlashResult(f"Unsupported command: /{command}")
