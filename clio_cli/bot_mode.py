"""Command-line contracts for profile-backed Clio Bot Mode."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


def _emit(value: Any) -> None:
    if is_dataclass(value):
        value = asdict(value)
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str))


def _message(args: argparse.Namespace) -> str:
    inline = getattr(args, "message", None)
    raw_file = getattr(args, "file", None)
    if bool(inline) == bool(raw_file):
        raise ValueError("Exactly one of --message or --file is required")
    if inline:
        return str(inline)
    path = Path(raw_file).expanduser()
    if path.stat().st_size > 200_000:
        raise ValueError("Message file exceeds 200000 bytes")
    return path.read_text(encoding="utf-8")


def _cmd_bot(args: argparse.Namespace) -> None:
    from clio_bot_mode import (
        ensure_bot_chat,
        list_bot_roster,
        local_dm,
        read_bot_metadata,
        update_bot_metadata,
    )

    action = args.bot_action or "list"
    if action in {"list", "ls"}:
        _emit(list_bot_roster(include_hidden=bool(args.include_hidden)))
    elif action == "show":
        _emit({"profile": args.profile, **read_bot_metadata(args.profile)})
    elif action == "chat":
        _emit(ensure_bot_chat(args.profile))
    elif action == "dm":
        _emit(local_dm(args.profile, _message(args), sender=args.sender, timeout=args.timeout))
    elif action == "set":
        updates = {
            key: getattr(args, key)
            for key in ("display_name", "title", "description", "enabled", "hidden")
            if getattr(args, key) is not None
        }
        if args.groups is not None:
            updates["groups"] = [item.strip() for item in args.groups.split(",") if item.strip()]
        if not updates:
            raise ValueError("At least one metadata option is required")
        _emit(update_bot_metadata(args.profile, **updates))


def _cmd_group(args: argparse.Namespace) -> None:
    from clio_bot_mode import create_room, delete_room, get_room, list_rooms, send_room_message

    action = args.group_action or "list"
    if action in {"list", "ls"}:
        _emit(list_rooms())
    elif action == "create":
        _emit(create_room(args.name, args.members))
    elif action == "show":
        _emit(get_room(args.room_id))
    elif action in {"delete", "rm"}:
        _emit({"room_id": args.room_id, "deleted": delete_room(args.room_id)})
    elif action == "send":
        _emit(send_room_message(args.room_id, _message(args), thread_id=args.thread))


def _cmd_peer(args: argparse.Namespace) -> None:
    from clio_bot_mode import list_connected_bot_roster, load_peers, peer_dm, remove_peer, save_peer

    action = args.peer_action or "list"
    if action in {"list", "ls"}:
        _emit(load_peers())
    elif action in {"roster", "bots"}:
        _emit(
            list_connected_bot_roster(
                args.peers or None,
                include_local=not args.no_local,
                include_hidden=bool(args.include_hidden),
                timeout=args.timeout,
            )
        )
    elif action == "add":
        _emit({
            "name": args.name,
            **save_peer(
                args.name,
                args.url,
                key=args.key or "",
                note=args.note or "",
                allow_insecure=bool(args.allow_insecure),
            ),
        })
    elif action in {"remove", "rm"}:
        _emit({"name": args.name, "removed": remove_peer(args.name)})
    elif action == "dm":
        _emit(peer_dm(args.target, _message(args), sender=args.sender, timeout=args.timeout))


def _cmd_routine(args: argparse.Namespace) -> None:
    from clio_bot_mode import create_bot_routine, list_bot_routines

    action = args.routine_action or "list"
    if action in {"list", "ls"}:
        _emit(list_bot_routines(args.profile))
    elif action == "add":
        _emit(
            create_bot_routine(
                args.profile,
                name=args.name,
                prompt=_message(args),
                schedule=args.schedule,
                deliver=args.deliver,
            )
        )


def _guard(handler):
    def wrapped(args: argparse.Namespace) -> None:
        try:
            handler(args)
        except (FileNotFoundError, KeyError, OSError, RuntimeError, ValueError) as exc:
            print(f"Bot Mode error: {exc}", file=sys.stderr)
            raise SystemExit(2) from exc

    return wrapped


def _message_flags(parser: argparse.ArgumentParser) -> None:
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--message", help="Literal message text (prefer --file for Bot-authored content)")
    source.add_argument("--file", help="UTF-8 file containing the exact message")


def register_cli(subparsers: argparse._SubParsersAction) -> None:
    """Register ``bot``, ``group``, ``peer``, and ``routine`` commands."""
    bot = subparsers.add_parser("bot", help="List, configure, or message profile-backed Bots")
    bot_sub = bot.add_subparsers(dest="bot_action")
    bot_list = bot_sub.add_parser("list", aliases=["ls"], help="List the Bot roster")
    bot_list.add_argument("--include-hidden", action="store_true")
    bot_show = bot_sub.add_parser("show", help="Show Bot metadata")
    bot_show.add_argument("profile")
    bot_chat = bot_sub.add_parser("chat", help="Get/create the canonical Bot Chat")
    bot_chat.add_argument("profile", nargs="?", default="default")
    bot_dm = bot_sub.add_parser("dm", help="Deliver one turn to a Bot Chat")
    bot_dm.add_argument("profile")
    bot_dm.add_argument("--from", dest="sender", default="user")
    bot_dm.add_argument("--timeout", type=float, default=600.0)
    _message_flags(bot_dm)
    bot_set = bot_sub.add_parser("set", help="Update Bot metadata without changing SOUL.md")
    bot_set.add_argument("profile")
    bot_set.add_argument("--display-name")
    bot_set.add_argument("--title")
    bot_set.add_argument("--description")
    bot_set.add_argument("--groups", help="Comma-separated group labels")
    bot_set.add_argument("--enabled", action=argparse.BooleanOptionalAction, default=None)
    bot_set.add_argument("--hidden", action=argparse.BooleanOptionalAction, default=None)
    bot.set_defaults(func=_guard(_cmd_bot), include_hidden=False)

    group = subparsers.add_parser("group", help="Manage bounded Bot team rooms")
    group_sub = group.add_subparsers(dest="group_action")
    group_sub.add_parser("list", aliases=["ls"], help="List rooms")
    create = group_sub.add_parser("create", help="Create a room with 2-6 Bots")
    create.add_argument("name")
    create.add_argument("members", nargs="+")
    show = group_sub.add_parser("show", help="Show room state and visible transcript")
    show.add_argument("room_id")
    send = group_sub.add_parser("send", help="Run one bounded room deliberation")
    send.add_argument("room_id")
    send.add_argument("--thread")
    _message_flags(send)
    delete = group_sub.add_parser("delete", aliases=["rm"], help="Delete room coordinator state")
    delete.add_argument("room_id")
    group.set_defaults(func=_guard(_cmd_group))

    peer = subparsers.add_parser("peer", help="Manage authenticated Bot peer gateways")
    peer_sub = peer.add_subparsers(dest="peer_action")
    peer_sub.add_parser("list", aliases=["ls"], help="List peers (secrets omitted)")
    roster = peer_sub.add_parser("roster", aliases=["bots"], help="List Bots across local and peer connections")
    roster.add_argument("peers", nargs="*", help="Optional peer names (default: all registered peers)")
    roster.add_argument("--no-local", action="store_true", help="Omit Bots on this device")
    roster.add_argument("--include-hidden", action="store_true")
    roster.add_argument("--timeout", type=float, default=30.0)
    add = peer_sub.add_parser("add", help="Register an authenticated peer API server")
    add.add_argument("name")
    add.add_argument("url")
    add.add_argument("--key", help="Bearer key, stored in .env")
    add.add_argument("--note")
    add.add_argument(
        "--allow-insecure",
        action="store_true",
        help="Allow HTTP for a non-local peer on an explicitly trusted network",
    )
    remove = peer_sub.add_parser("remove", aliases=["rm"], help="Remove peer metadata")
    remove.add_argument("name")
    peer_send = peer_sub.add_parser("dm", help="Deliver one turn to peer/profile")
    peer_send.add_argument("target", help="peer/profile (profile defaults to default)")
    peer_send.add_argument("--from", dest="sender", default="user")
    peer_send.add_argument("--timeout", type=float, default=600.0)
    _message_flags(peer_send)
    peer.set_defaults(func=_guard(_cmd_peer))

    routine = subparsers.add_parser("routine", help="Manage profile-scoped Bot cron routines")
    routine_sub = routine.add_subparsers(dest="routine_action")
    routine_list = routine_sub.add_parser("list", aliases=["ls"], help="List Bot routines")
    routine_list.add_argument("--profile")
    routine_add = routine_sub.add_parser("add", help="Create a Bot routine")
    routine_add.add_argument("profile")
    routine_add.add_argument("name")
    routine_add.add_argument("schedule")
    routine_add.add_argument("--deliver", default="local")
    _message_flags(routine_add)
    routine.set_defaults(func=_guard(_cmd_routine), profile=None)


__all__ = ["register_cli"]
