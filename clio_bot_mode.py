"""Clio-native Bot Mode services.

A Bot is a Clio profile.  This module provides the profile metadata, canonical
session identity, local/peer direct-message transport, routines, and bounded
team-room coordinator used by the CLI, API surfaces, and desktop plugin.

The implementation is deliberately local first:

* profile identity remains in ``profile.yaml``;
* Bot/Group conversations remain ordinary rows in that profile's ``state.db``;
* routines remain ordinary profile-scoped Clio cron jobs;
* room coordination state is one small atomic JSON document at the Clio root;
* remote delivery composes over the authenticated ``api_server`` platform.

No user-authored ``SOUL.md`` file is ever changed by Bot Mode.
"""

from __future__ import annotations

import base64
import binascii
import contextlib
import hashlib
import ipaddress
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence

BOT_CHAT_TITLE = "Bot Chat"
BOT_CANONICAL_KEY = "bot.chat"
BOT_PROTOCOL_VERSION = 1
BOT_METADATA_VERSION = 1
ROOM_STORE_VERSION = 1
ROOM_MIN_MEMBERS = 2
ROOM_MAX_MEMBERS = 6
ROOM_MAX_ROUNDS = 3
ROOM_MAX_VISIBLE_PER_SEND = 10
ROOM_HISTORY_LIMIT = 24
ROOM_MAX_ATTACHMENTS = 12
ROOM_MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024
ROOM_REMOTE_ATTACHMENT_BYTES = 7 * 1024 * 1024
PEER_MAX_RESPONSE_BYTES = 1024 * 1024
ROOM_SOFT_TIMEOUT_SECONDS = 90.0
ROOM_HARD_TIMEOUT_SECONDS = 300.0
WORKER_ACTIVE_SECONDS = 120.0

_PROFILE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_SOURCE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_HANDLE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,127}$")
_MENTION_RE = re.compile(r"(?<![\w@])@([a-zA-Z0-9][a-zA-Z0-9_-]{0,127})")
_PASS_RE = re.compile(r"^\s*\(?\s*pass\s*\)?\s*[.!]?\s*$", re.I)
_ROOM_STAGING_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,127}$")
_MIME_RE = re.compile(r"^[a-z0-9][a-z0-9!#$&^_.+-]{0,63}/[a-z0-9][a-z0-9!#$&^_.+-]{0,63}$")
_ROOM_ATTACHMENT_MIME_TYPES = frozenset(
    {"application/pdf", "image/png", "image/jpeg", "image/webp", "text/plain", "text/markdown"}
)
_ROOM_LOCK = threading.RLock()
_CRON_LOCK = threading.RLock()


class BotModeError(RuntimeError):
    """Expected Bot Mode usage or delivery failure."""


@dataclass(frozen=True)
class BotAddress:
    """Stable identity for one Bot on one source."""

    profile: str
    source: str = "local"
    source_label: str = "This device"

    @property
    def key(self) -> str:
        return f"{self.source}:{self.profile}"

    @property
    def base_handle(self) -> str:
        return "clio" if self.profile == "default" else self.profile

    def handle(self, duplicated_names: Iterable[str] = ()) -> str:
        duplicate_set = {str(item).lower() for item in duplicated_names}
        if self.base_handle.lower() not in duplicate_set and self.source == "local":
            return self.base_handle
        suffix = _slug(self.source_label if self.source_label else self.source)
        return f"{self.base_handle}-{suffix}"


@dataclass(frozen=True)
class RoomTurnResult:
    room_id: str
    epoch: int
    rounds: int
    state: str
    needs_user: bool
    messages: List[Dict[str, Any]]
    suppressed: int = 0
    activity: Optional[List[Dict[str, Any]]] = None


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9_-]+", "-", str(value or "").strip().lower()).strip("-_")
    return slug or "source"


def _validate_profile(name: str) -> str:
    normalized = str(name or "").strip().lower()
    if not _PROFILE_RE.fullmatch(normalized):
        raise ValueError(f"Invalid profile name: {name!r}")
    return normalized


def _validate_source(name: str) -> str:
    normalized = str(name or "local").strip().lower()
    if not _SOURCE_RE.fullmatch(normalized):
        raise ValueError(f"Invalid Bot source: {name!r}")
    return normalized


def _validate_room_staging_id(room_id: str) -> str:
    normalized = str(room_id or "").strip().lower()
    if not _ROOM_STAGING_RE.fullmatch(normalized):
        raise ValueError("Invalid Bot room attachment identifier")
    return normalized


def _validate_attachment_name(name: Any) -> str:
    if not isinstance(name, str):
        raise ValueError("Attachment name must be a string")
    normalized = name.strip()
    if (
        not normalized
        or len(normalized) > 200
        or normalized in {".", ".."}
        or Path(normalized).name != normalized
        or "/" in normalized
        or "\\" in normalized
        or any(ord(character) < 32 or ord(character) == 127 for character in normalized)
    ):
        raise ValueError("Attachment name must be a plain filename of at most 200 characters")
    return normalized


def _validate_attachment_mime(mime_type: Any) -> str:
    if not isinstance(mime_type, str):
        raise ValueError("Attachment MIME type must be a string")
    normalized = mime_type.strip().lower()
    if not _MIME_RE.fullmatch(normalized):
        raise ValueError("Attachment MIME type is invalid")
    if normalized not in _ROOM_ATTACHMENT_MIME_TYPES and not normalized.startswith("image/"):
        raise ValueError(f"Unsupported room attachment type: {normalized}")
    return normalized


def _profiles_module():
    from clio_cli import profiles

    return profiles


def clio_root_for_home(home: Path) -> Path:
    """Return the root ``~/.clio`` for a default or named profile home."""
    resolved = Path(home).expanduser().resolve()
    if resolved.parent.name == "profiles":
        return resolved.parent.parent
    return resolved


def profile_name_for_home(home: Path) -> str:
    resolved = Path(home).expanduser().resolve()
    return resolved.name if resolved.parent.name == "profiles" else "default"


def profile_home(profile: str) -> Path:
    profile = _validate_profile(profile)
    profiles = _profiles_module()
    if not profiles.profile_exists(profile):
        raise FileNotFoundError(f"Profile '{profile}' does not exist")
    return Path(profiles.get_profile_dir(profile))


def _read_yaml_mapping(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        import yaml

        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return dict(value) if isinstance(value, dict) else {}
    except Exception:
        return {}


def _atomic_yaml(path: Path, value: Mapping[str, Any]) -> None:
    import yaml

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = yaml.safe_dump(dict(value), sort_keys=False, default_flow_style=False)
    fd, raw_tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp = Path(raw_tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def read_bot_metadata(profile: str) -> Dict[str, Any]:
    """Read optional Bot metadata, returning safe defaults for legacy profiles."""
    profile = _validate_profile(profile)
    home = profile_home(profile)
    raw = _read_yaml_mapping(home / "profile.yaml")
    bot: Dict[str, Any] = dict(raw["bot"]) if isinstance(raw.get("bot"), dict) else {}
    groups: List[Any] = list(bot["groups"]) if isinstance(bot.get("groups"), list) else []
    return {
        "version": int(bot.get("version") or BOT_METADATA_VERSION),
        "identity_id": str(bot.get("identity_id") or "").strip(),
        "enabled": bot.get("enabled", True) is not False,
        "display_name": str(raw.get("display_name") or bot.get("display_name") or profile).strip() or profile,
        "title": str(bot.get("title") or "").strip(),
        "description": str(bot.get("description") or raw.get("description") or "").strip(),
        "hidden": bool(bot.get("hidden", False)),
        "avatar": bot.get("avatar") if isinstance(bot.get("avatar"), dict) else {},
        "groups": [str(group) for group in groups if str(group).strip()],
        "created_at": bot.get("created_at"),
        "updated_at": bot.get("updated_at"),
    }


def ensure_bot_identity(profile: str) -> str:
    """Return a durable profile-Bot identity that survives profile renames."""
    profile = _validate_profile(profile)
    path = profile_home(profile) / "profile.yaml"
    with _ROOM_LOCK:
        raw = _read_yaml_mapping(path)
        bot: Dict[str, Any] = dict(raw["bot"]) if isinstance(raw.get("bot"), dict) else {}
        identity_id = str(bot.get("identity_id") or "").strip()
        if not identity_id:
            identity_id = f"bot-{uuid.uuid4().hex}"
            bot["identity_id"] = identity_id
            bot.setdefault("version", BOT_METADATA_VERSION)
            raw["bot"] = bot
            _atomic_yaml(path, raw)
    return identity_id


def _latest_worker_session(home: Path) -> Optional[Dict[str, Any]]:
    """Return the freshest kanban/tool worker heartbeat for one profile."""
    db_path = Path(home) / "state.db"
    if not db_path.is_file():
        return None
    try:
        from clio_state import SessionDB

        db = SessionDB(db_path=db_path)
        try:
            for session in db.list_sessions_rich(
                limit=50,
                order_by_last_active=True,
                include_hidden=True,
            ):
                source = str(session.get("source") or "").strip().lower()
                if source not in {"kanban", "tool"}:
                    continue
                last_active = float(session.get("last_active") or session.get("started_at") or 0)
                return {
                    "id": session["id"],
                    "source": source,
                    "title": session.get("title") or "",
                    "last_active": last_active,
                }
        finally:
            db.close()
    except Exception:
        return None
    return None


def update_bot_metadata(profile: str, **updates: Any) -> Dict[str, Any]:
    """Atomically update Bot metadata while preserving unrelated profile data."""
    profile = _validate_profile(profile)
    home = profile_home(profile)
    path = home / "profile.yaml"
    with _ROOM_LOCK:
        raw = _read_yaml_mapping(path)
        bot: Dict[str, Any] = dict(raw["bot"]) if isinstance(raw.get("bot"), dict) else {}
        now = time.time()
        bot.setdefault("version", BOT_METADATA_VERSION)
        bot.setdefault("created_at", now)
        allowed = {"enabled", "title", "description", "hidden", "avatar", "groups"}
        for key, value in updates.items():
            if key == "display_name":
                display = str(value or "").strip()
                raw["display_name"] = display or profile
            elif key in allowed:
                if key in {"title", "description"}:
                    bot[key] = str(value or "").strip()
                elif key in {"enabled", "hidden"}:
                    bot[key] = bool(value)
                elif key == "avatar":
                    if not isinstance(value, dict):
                        raise ValueError("avatar must be an object")
                    bot[key] = dict(value)
                elif key == "groups":
                    if not isinstance(value, (list, tuple)):
                        raise ValueError("groups must be a list")
                    bot[key] = sorted({str(item).strip() for item in value if str(item).strip()})
        bot["updated_at"] = now
        raw["bot"] = bot
        _atomic_yaml(path, raw)
    return read_bot_metadata(profile)


def list_bot_roster(*, include_hidden: bool = False, source: str = "local", source_label: str = "This device") -> List[Dict[str, Any]]:
    """List profile-backed Bots with deterministic source-qualified handles."""
    source = _validate_source(source)
    records: List[Dict[str, Any]] = []
    for info in _profiles_module().list_profiles():
        meta = read_bot_metadata(info.name)
        if not meta["enabled"] or (meta["hidden"] and not include_hidden):
            continue
        address = BotAddress(info.name, source, source_label)
        identity_id = ensure_bot_identity(info.name)
        worker_session = _latest_worker_session(profile_home(info.name))
        worker_active = bool(
            worker_session
            and float(worker_session.get("last_active") or 0) >= time.time() - WORKER_ACTIVE_SECONDS
        )
        records.append(
            {
                "profile": info.name,
                "source": source,
                "source_label": source_label,
                "key": address.key,
                "identity_id": identity_id,
                "handle": address.handle(),
                "display_name": meta["display_name"],
                "title": meta["title"],
                "description": meta["description"],
                "hidden": meta["hidden"],
                "avatar": meta["avatar"],
                "groups": meta["groups"],
                "model": getattr(info, "model", None),
                "provider": getattr(info, "provider", None),
                "gateway_running": bool(getattr(info, "gateway_running", False)),
                "worker_session": worker_session,
                "worker_active": worker_active,
                "is_default": bool(getattr(info, "is_default", False)),
            }
        )
    return records


def source_qualified_roster(sources: Mapping[str, Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Merge cached/live source inventories and disambiguate duplicate handles."""
    rows: List[Dict[str, Any]] = []
    base_counts: Dict[str, int] = {}
    for source, payload in sources.items():
        label = str(payload.get("label") or source)
        for raw in payload.get("bots") or []:
            profile = _validate_profile(str(raw.get("profile") or raw.get("name") or ""))
            address = BotAddress(profile, _validate_source(source), label)
            row = {**dict(raw), "profile": profile, "source": address.source, "source_label": label, "key": address.key}
            row["_base_handle"] = address.base_handle
            rows.append(row)
            base_counts[address.base_handle] = base_counts.get(address.base_handle, 0) + 1
    duplicates = {name for name, count in base_counts.items() if count > 1}
    for row in rows:
        address = BotAddress(row["profile"], row["source"], row["source_label"])
        row["handle"] = address.handle(duplicates)
        row.pop("_base_handle", None)
    return sorted(rows, key=lambda row: (str(row.get("display_name") or row["profile"]).lower(), row["source"]))


def ensure_canonical_session(
    profile: str,
    *,
    canonical_key: str = BOT_CANONICAL_KEY,
    title: str = BOT_CHAT_TITLE,
    identity_kind: str = "bot",
    hidden: bool = True,
) -> Dict[str, Any]:
    """Atomically get/create one canonical session in a profile's state DB."""
    profile = _validate_profile(profile)
    home = profile_home(profile)
    from clio_state import SessionDB

    with _ROOM_LOCK:
        db = SessionDB(db_path=home / "state.db")
        try:
            owner_kind = "profile_bot" if identity_kind == "bot" else "bot_group"
            owner_ref = ensure_bot_identity(profile)
            db.reconcile_canonical_session_owner(
                owner_profile=profile,
                canonical_key=str(canonical_key),
                identity_kind=identity_kind,
                owner_kind=owner_kind,
                owner_ref=owner_ref,
            )
            return db.get_or_create_canonical_session(
                owner_profile=profile,
                canonical_key=str(canonical_key),
                title=title,
                source="bot" if identity_kind == "bot" else "bot_group",
                identity_kind=identity_kind,
                hidden=hidden,
                owner_kind=owner_kind,
                owner_ref=owner_ref,
            )
        finally:
            db.close()


def ensure_bot_chat(profile: str, *, hidden: bool = True) -> Dict[str, Any]:
    return ensure_canonical_session(profile, hidden=hidden)


def ensure_group_session(profile: str, room_id: str, room_name: str) -> Dict[str, Any]:
    room_id = _slug(room_id)
    return ensure_canonical_session(
        profile,
        canonical_key=f"group:{room_id}",
        title=f"Group: {room_name}"[:100],
        identity_kind="group",
        hidden=False,
    )


def capability_fingerprint(home_or_profile: str | os.PathLike[str] | Path) -> str:
    """Fingerprint only user-controlled Bot capabilities; unchanged state is stable."""
    try:
        raw = Path(home_or_profile).expanduser()
        if raw.is_dir() or "/" in str(home_or_profile):
            home = raw.resolve()
            profile = profile_name_for_home(home)
        else:
            profile = _validate_profile(str(home_or_profile))
            home = profile_home(profile)
        surface: Dict[str, Any] = {"protocol": BOT_PROTOCOL_VERSION, "profile": profile}
        profile_yaml = _read_yaml_mapping(home / "profile.yaml")
        surface["bot"] = profile_yaml.get("bot") if isinstance(profile_yaml.get("bot"), dict) else {}
        config = _read_yaml_mapping(home / "config.yaml")
        surface["agent"] = {"bot_mode_protocol": (config.get("agent") or {}).get("bot_mode_protocol", True)} if isinstance(config.get("agent"), dict) else {}
        surface["skills_config"] = config.get("skills") if isinstance(config.get("skills"), dict) else {}
        surface["tools"] = config.get("tools") if isinstance(config.get("tools"), dict) else {}
        surface["mcp_servers"] = config.get("mcp_servers") if isinstance(config.get("mcp_servers"), dict) else {}
        surface["peers"] = sorted((_read_yaml_mapping(clio_root_for_home(home) / "config.yaml").get("bot_peers") or {}).keys())
        soul = home / "SOUL.md"
        surface["soul"] = hashlib.sha256(soul.read_bytes()).hexdigest() if soul.is_file() else ""
        skills = home / "skills"
        surface["installed_skills"] = sorted(
            str(item.parent.relative_to(skills)) for item in skills.glob("**/SKILL.md")
        ) if skills.is_dir() else []
        surface["roster"] = [row["profile"] for row in list_bot_roster(include_hidden=True)]
        blob = json.dumps(surface, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()[:16]
    except Exception:
        return "unavailable"


def protocol_epoch_line(home: Path) -> str:
    return f"Clio Bot capability epoch: {capability_fingerprint(home)}"


def stored_prompt_capability_stale(prompt: str, home: Path) -> bool:
    match = re.search(r"Clio Bot capability epoch: ([0-9a-f]{16})", prompt or "")
    if not match:
        return False
    current = capability_fingerprint(home)
    return current != "unavailable" and match.group(1) != current


def _agent_home(agent: Any) -> Optional[Path]:
    db = getattr(agent, "_session_db", None)
    path = getattr(db, "db_path", None)
    if path:
        return Path(path).resolve().parent
    try:
        from clio_constants import get_clio_home

        return Path(get_clio_home()).resolve()
    except Exception:
        return None


def _agent_is_canonical(agent: Any) -> bool:
    # During AIAgent construction no session row has been bound yet. Avoid a
    # speculative DB read: it breaks cold-start prompt stability and turns a
    # generic MagicMock/session adapter into a false Bot match.
    if not bool(getattr(agent, "_session_db_created", False)):
        return False
    db = getattr(agent, "_session_db", None)
    session_id = getattr(agent, "session_id", None)
    if not db or not session_id:
        return False
    try:
        row = db.get_session(session_id)
        return bool(row and row.get("canonical_key") == BOT_CANONICAL_KEY and row.get("identity_kind") == "bot")
    except Exception:
        return False


def bot_protocol_section_for_agent(agent: Any) -> str:
    """Return the protocol only for the profile's canonical Bot Chat."""
    if not getattr(agent, "_bot_mode_protocol", True) or not _agent_is_canonical(agent):
        return ""
    home = _agent_home(agent)
    if home is None:
        return ""
    me = profile_name_for_home(home)
    handle = "clio" if me == "default" else me
    roster = list_bot_roster(include_hidden=True)
    teammates = [f"@{row['handle']}" for row in roster if row["profile"] != me]
    peer_names = sorted((_read_yaml_mapping(clio_root_for_home(home) / "config.yaml").get("bot_peers") or {}).keys())
    peer_text = ""
    if peer_names:
        peer_text = (
            " Registered peer gateways: " + ", ".join(peer_names) + ". Use `clio peer dm <peer>/<profile> --file <path>` for cross-machine delivery."
        )
    return (
        "## Messaging other Clio Bots\n"
        "This is your canonical Bot Chat. Other Bots and the user may send attributed messages here. "
        f"Your handle is @{handle}. A teammate message begins `Message from Clio Bot <sender> (@<handle>):`; "
        "reply to that teammate rather than pretending it came directly from the user. For a local handoff, "
        "write the exact message to a file first, then run `clio bot dm <profile> --from <your-profile> --file <path>`; "
        "never interpolate teammate text into a shell command. Mention handles are validated against the live roster. "
        f"Teammates now: {', '.join(teammates) if teammates else '(none)'}.{peer_text}\n"
        + protocol_epoch_line(home)
    )


def maybe_refresh_bot_prompt(agent: Any, stored_prompt: str, system_message: Optional[str]) -> bool:
    """Refresh a stale canonical prompt once per capability change."""
    if not _agent_is_canonical(agent):
        return False
    home = _agent_home(agent)
    if home is None:
        return False
    needs_upgrade = "## Messaging other Clio Bots" not in (stored_prompt or "")
    if not needs_upgrade and not stored_prompt_capability_stale(stored_prompt, home):
        return False
    agent._cached_system_prompt = agent._build_system_prompt(system_message)
    try:
        agent._session_db.update_system_prompt(agent.session_id, agent._cached_system_prompt)
        agent._session_db.set_canonical_capability(
            agent.session_id,
            fingerprint=capability_fingerprint(home),
            epoch=int(time.time()),
        )
    except Exception:
        pass
    return True


def _safe_message_text(message: str, *, max_chars: int = 200_000) -> str:
    text = str(message or "")
    if not text.strip():
        raise ValueError("Message must not be empty")
    if "\x00" in text:
        raise ValueError("Message contains a NUL byte")
    if len(text) > max_chars:
        raise ValueError(f"Message exceeds {max_chars} characters")
    return text


def run_profile_turn(profile: str, session_id: str, message: str, *, timeout: float = 600.0) -> str:
    """Run one finalized CLI turn using argv + a 0600 query file (never a shell)."""
    profile = _validate_profile(profile)
    message = _safe_message_text(message)
    home = profile_home(profile)
    temp_dir = home / "tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    fd, raw_path = tempfile.mkstemp(prefix="bot-dm-", suffix=".txt", dir=str(temp_dir))
    path = Path(raw_path)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(message)
            handle.flush()
            os.fsync(handle.fileno())
        command = [
            sys.executable,
            "-m",
            "clio_cli.main",
            "--profile",
            profile,
            "chat",
            "--resume",
            session_id,
            "--quiet",
            "--query-file",
            str(path),
            "--source",
            "bot",
        ]
        env = os.environ.copy()
        env["CLIO_BOT_CHILD"] = "1"
        result = subprocess.run(
            command,
            cwd=str(Path(__file__).resolve().parent),
            env=env,
            capture_output=True,
            text=True,
            timeout=max(1.0, timeout),
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "Bot turn failed").strip()
            raise BotModeError(detail[-2000:])
        output = result.stdout.strip()
        # Quiet mode may append a stable session-id diagnostic. It is metadata,
        # not part of the Bot's reply.
        lines = output.splitlines()
        if lines and re.fullmatch(r"Session(?: ID)?:\s*\S+", lines[-1], re.I):
            lines.pop()
        return "\n".join(lines).strip()
    except subprocess.TimeoutExpired as exc:
        raise BotModeError(f"Bot turn timed out after {timeout:g}s") from exc
    finally:
        path.unlink(missing_ok=True)


def local_dm(target_profile: str, message: str, *, sender: str = "user", timeout: float = 600.0) -> Dict[str, Any]:
    target_profile = _validate_profile(target_profile)
    sender = _validate_profile(sender) if sender != "user" else "user"
    session = ensure_bot_chat(target_profile)
    sender_handle = "user" if sender == "user" else ("clio" if sender == "default" else sender)
    if sender == "user":
        attributed = f"Message from the user (@user):\n\n{_safe_message_text(message)}"
    else:
        attributed = f"Message from Clio Bot {sender} (@{sender_handle}):\n\n{_safe_message_text(message)}"
    reply = run_profile_turn(target_profile, session["id"], attributed, timeout=timeout)
    return {"profile": target_profile, "session_id": session["id"], "sender": sender, "reply": reply}


def _room_store_path(root: Optional[Path] = None) -> Path:
    if root is not None:
        return Path(root) / "bot_rooms.json"
    from clio_constants import get_clio_home

    return clio_root_for_home(Path(get_clio_home())) / "bot_rooms.json"


def _load_room_store(root: Optional[Path] = None) -> Dict[str, Any]:
    path = _room_store_path(root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("rooms"), dict):
            return payload
    except Exception:
        pass
    return {"version": ROOM_STORE_VERSION, "rooms": {}}


def _reconcile_room_store(store: Dict[str, Any]) -> bool:
    """Rebind persisted local room members using their durable Bot identity."""
    try:
        roster = list_bot_roster(include_hidden=True)
    except Exception:
        return False
    by_identity = {
        str(row.get("identity_id")): row
        for row in roster
        if row.get("source") == "local" and row.get("identity_id")
    }
    by_profile = {
        str(row.get("profile")): row for row in roster if row.get("source") == "local"
    }
    changed = False
    for room in store.get("rooms", {}).values():
        if not isinstance(room, dict):
            continue
        for member in room.get("members") or []:
            if not isinstance(member, dict) or member.get("source", "local") != "local":
                continue
            identity_id = str(member.get("identity_id") or "")
            current = by_identity.get(identity_id) if identity_id else by_profile.get(str(member.get("profile") or ""))
            if current is None:
                continue
            old_profile = str(member.get("profile") or "")
            old_handle = str(member.get("handle") or "")
            replacements = {
                "identity_id": current["identity_id"],
                "profile": current["profile"],
                "handle": current["handle"],
                "source_label": current["source_label"],
            }
            if any(member.get(key) != value for key, value in replacements.items()):
                member.update(replacements)
                changed = True
            new_profile = str(current["profile"])
            new_handle = str(current["handle"])
            if old_profile == new_profile and old_handle == new_handle:
                continue
            for record in [*(room.get("messages") or []), *(room.get("activity") or [])]:
                if not isinstance(record, dict) or record.get("source", "local") != "local":
                    continue
                owned = record.get("profile") == old_profile
                if owned:
                    record["profile"] = new_profile
                if owned and record.get("author") == old_handle:
                    record["author"] = new_handle
                if owned and record.get("member") == old_handle:
                    record["member"] = new_handle
            watermarks = room.get("watermarks")
            if isinstance(watermarks, dict) and old_handle != new_handle:
                for key in list(watermarks):
                    if key.startswith(f"{old_handle}\x1f"):
                        watermarks[f"{new_handle}{key[len(old_handle):]}"] = watermarks.pop(key)
            changed = True
    return changed


def _save_room_store(store: Mapping[str, Any], root: Optional[Path] = None) -> None:
    path = _room_store_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(dict(store), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    fd, raw_tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp = Path(raw_tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _normalize_member(raw: str | Mapping[str, Any]) -> Dict[str, str]:
    if isinstance(raw, str):
        profile = _validate_profile(raw)
        return {
            "profile": profile,
            "source": "local",
            "source_label": "This device",
            "handle": "clio" if profile == "default" else profile,
            "identity_id": ensure_bot_identity(profile),
        }
    profile = _validate_profile(str(raw.get("profile") or raw.get("name") or ""))
    source = _validate_source(str(raw.get("source") or "local"))
    source_label = str(raw.get("source_label") or raw.get("device") or source).strip() or source
    handle = _slug(str(raw.get("handle") or ("clio" if profile == "default" else profile)))
    if not _HANDLE_RE.fullmatch(handle):
        raise ValueError(f"Invalid Bot handle: {handle!r}")
    identity_id = str(raw.get("identity_id") or "").strip()
    if source == "local":
        identity_id = ensure_bot_identity(profile)
    return {
        "profile": profile,
        "source": source,
        "source_label": source_label,
        "handle": handle,
        **({"identity_id": identity_id} if identity_id else {}),
    }


def create_room(name: str, members: Sequence[str | Mapping[str, Any]], *, root: Optional[Path] = None) -> Dict[str, Any]:
    clean_name = re.sub(r"\s+", " ", str(name or "")).strip()
    if not clean_name or len(clean_name) > 80:
        raise ValueError("Room name must be 1-80 characters")
    normalized = [_normalize_member(member) for member in members]
    by_key = {f"{member['source']}:{member['profile']}": member for member in normalized}
    if not ROOM_MIN_MEMBERS <= len(by_key) <= ROOM_MAX_MEMBERS:
        raise ValueError(f"A room requires {ROOM_MIN_MEMBERS}-{ROOM_MAX_MEMBERS} distinct Bots")
    handles = [member["handle"] for member in by_key.values()]
    if len(set(handles)) != len(handles):
        raise ValueError("Room member handles must be unique; use source-qualified handles")
    # Fail before writing a room record: a local member must resolve to a real,
    # Bot-enabled profile, otherwise the room would be durably stranded.
    for member in by_key.values():
        if member["source"] == "local":
            profile_home(member["profile"])
            if not read_bot_metadata(member["profile"])["enabled"]:
                raise ValueError(f"Profile {member['profile']!r} is not Bot-enabled")
        elif member["source"] not in load_peers():
            raise ValueError(f"No Bot peer named {member['source']!r}")
    room_id = f"room-{uuid.uuid4().hex[:12]}"
    now = time.time()
    room = {
        "id": room_id,
        "name": clean_name,
        "members": list(by_key.values()),
        "created_at": now,
        "updated_at": now,
        "active_epoch": 0,
        "state": "idle",
        "needs_user": False,
        "messages": [],
        "watermarks": {},
        "activity": [],
    }
    with _ROOM_LOCK:
        store = _load_room_store(root)
        store["rooms"][room_id] = room
        _save_room_store(store, root)
    for member in room["members"]:
        if member["source"] == "local":
            ensure_group_session(member["profile"], room_id, clean_name)
    return room


def list_rooms(*, root: Optional[Path] = None) -> List[Dict[str, Any]]:
    with _ROOM_LOCK:
        store = _load_room_store(root)
        if _reconcile_room_store(store):
            _save_room_store(store, root)
        rooms = list(store["rooms"].values())
    return sorted((dict(room) for room in rooms), key=lambda room: float(room.get("updated_at") or 0), reverse=True)


def get_room(room_id: str, *, root: Optional[Path] = None) -> Dict[str, Any]:
    with _ROOM_LOCK:
        store = _load_room_store(root)
        if _reconcile_room_store(store):
            _save_room_store(store, root)
        room = store["rooms"].get(str(room_id))
    if not isinstance(room, dict):
        raise KeyError(room_id)
    result = dict(room)
    # One user send plus at most ROOM_MAX_VISIBLE_PER_SEND Bot replies.
    result["visible_messages"] = list(result.get("messages") or [])[-(ROOM_MAX_VISIBLE_PER_SEND + 1):]
    return result


def delete_room(room_id: str, *, root: Optional[Path] = None) -> bool:
    with _ROOM_LOCK:
        store = _load_room_store(root)
        existed = store["rooms"].pop(str(room_id), None) is not None
        if existed:
            _save_room_store(store, root)
    return existed


def _mentions(text: str, handles: Iterable[str]) -> List[str]:
    known = {handle.lower(): handle for handle in handles}
    found: List[str] = []
    for raw in _MENTION_RE.findall(text or ""):
        handle = known.get(raw.lower())
        if handle and handle not in found:
            found.append(handle)
    return found


def _normalize_new_value(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


def is_hidden_pass(text: Any) -> bool:
    """Return whether a Bot reply is protocol silence, not visible content."""
    reply = str(text or "").strip()
    return not reply or bool(_PASS_RE.fullmatch(reply))


def _watermark_key(handle: str, thread_id: Optional[str]) -> str:
    return f"{handle}\x1f{thread_id or ''}"


def _max_seq(messages: Sequence[Mapping[str, Any]]) -> int:
    return max((int(item.get("seq") or 0) for item in messages), default=0)


def _unseen_delta(
    room: Mapping[str, Any], member: Mapping[str, str], thread_id: Optional[str]
) -> tuple[List[Dict[str, Any]], int]:
    messages = list(room.get("messages") or [])
    key = _watermark_key(member["handle"], thread_id)
    watermark = int((room.get("watermarks") or {}).get(key) or 0)
    delta = [
        dict(item)
        for item in messages
        if int(item.get("seq") or 0) > watermark
        and item.get("author") != member["handle"]
        and (not thread_id or item.get("thread_id") in {None, thread_id})
    ]
    return delta, _max_seq(messages)


def _prepare_attachments(attachments: Optional[Sequence[Mapping[str, Any]]]) -> List[Dict[str, Any]]:
    if not attachments:
        return []
    if len(attachments) > ROOM_MAX_ATTACHMENTS:
        raise ValueError(f"At most {ROOM_MAX_ATTACHMENTS} attachments are allowed")
    clean: List[Dict[str, Any]] = []
    for item in attachments:
        if not isinstance(item, Mapping):
            raise ValueError("Each room attachment must be an object")
        path = str(item.get("path") or "").strip()
        if not path:
            raise ValueError("Room attachment path is required")
        source = Path(path).expanduser().resolve()
        if not source.is_file():
            raise ValueError(f"Room attachment does not exist: {source}")
        name = _validate_attachment_name(item.get("name") or source.name)
        mime = _validate_attachment_mime(item.get("mime_type") or item.get("mime") or "")
        size = source.stat().st_size
        if size > ROOM_MAX_ATTACHMENT_BYTES:
            raise ValueError(f"Attachment {name!r} exceeds the 25 MiB limit")
        clean.append({"name": name, "path": str(source), "mime_type": mime, "size": size})
    return clean


def _room_staging_root(profile: str, room_id: str) -> Path:
    """Create an owner-only, non-symlink staging directory for one profile/room."""
    home = profile_home(profile).expanduser().resolve()
    destination = home
    for component in ("tmp", "bot_rooms", _validate_room_staging_id(room_id)):
        destination = destination / component
        if destination.is_symlink():
            raise BotModeError(f"Refusing symlinked Bot room attachment directory: {destination}")
        destination.mkdir(mode=0o700, exist_ok=True)
        resolved = destination.resolve()
        if resolved != home and home not in resolved.parents:
            raise BotModeError("Bot room attachment directory escapes the target profile")
        os.chmod(resolved, 0o700)
        destination = resolved
    return destination


def _attachment_suffix(name: str) -> str:
    suffix = Path(name).suffix.lower()
    return suffix if re.fullmatch(r"\.[a-z0-9]{1,15}", suffix) else ""


def _write_staged_attachment(destination_root: Path, name: str, payload: bytes) -> Path:
    """Write bytes to a random, exclusively-created owner-only file."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    for _attempt in range(10):
        destination = destination_root / f"{uuid.uuid4().hex}{_attachment_suffix(name)}"
        try:
            fd = os.open(destination, flags, 0o600)
        except FileExistsError:
            continue
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(destination, 0o600)
            return destination
        except Exception:
            destination.unlink(missing_ok=True)
            raise
    raise BotModeError("Could not allocate a random Bot room attachment path")


def stage_received_room_attachment(
    profile: str,
    room_id: str,
    *,
    name: Any,
    mime_type: Any,
    size: Any,
    base64_data: Any,
) -> Dict[str, Any]:
    """Strictly decode and stage one authenticated peer attachment.

    No sender-provided path is accepted or used. The returned path is meaningful
    only on this receiving host and always lives below the target profile.
    """
    profile = _validate_profile(profile)
    room_id = _validate_room_staging_id(room_id)
    clean_name = _validate_attachment_name(name)
    clean_mime = _validate_attachment_mime(mime_type)
    if isinstance(size, bool) or not isinstance(size, int):
        raise ValueError("Attachment size must be an integer")
    if size < 0 or size > ROOM_REMOTE_ATTACHMENT_BYTES:
        raise ValueError("Remote Bot room attachments are limited to 7 MiB each")
    if not isinstance(base64_data, str):
        raise ValueError("Attachment base64_data must be a string")
    max_encoded = 4 * ((ROOM_REMOTE_ATTACHMENT_BYTES + 2) // 3)
    if len(base64_data) > max_encoded:
        raise ValueError("Remote Bot room attachment Base64 payload exceeds the 7 MiB limit")
    try:
        encoded = base64_data.encode("ascii", "strict")
        payload = base64.b64decode(encoded, validate=True)
    except (UnicodeEncodeError, binascii.Error, ValueError) as exc:
        raise ValueError("Attachment base64_data is not strict Base64") from exc
    if base64.b64encode(payload).decode("ascii") != base64_data:
        raise ValueError("Attachment base64_data is not canonical Base64")
    if len(payload) != size:
        raise ValueError(f"Attachment declared size {size} does not match decoded size {len(payload)}")
    destination = _write_staged_attachment(
        _room_staging_root(profile, room_id),
        clean_name,
        payload,
    )
    return {
        "name": clean_name,
        "mime_type": clean_mime,
        "size": size,
        "path": str(destination),
    }


def _stage_attachments_for_member(
    room_id: str,
    member: Mapping[str, str],
    attachments: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """Copy attachments into the receiving profile instead of sharing paths."""
    if not attachments:
        return []
    if member["source"] != "local":
        return [
            upload_peer_room_attachment(
                member["source"],
                member["profile"],
                room_id,
                item,
            )
            for item in attachments
        ]
    destination_root = _room_staging_root(member["profile"], room_id)
    staged: List[Dict[str, Any]] = []
    for item in attachments:
        source = Path(str(item.get("path") or "")).expanduser().resolve()
        if not source.is_file():
            raise ValueError(f"Room attachment does not exist: {source}")
        with source.open("rb") as handle:
            payload = handle.read(ROOM_MAX_ATTACHMENT_BYTES + 1)
        if len(payload) > ROOM_MAX_ATTACHMENT_BYTES:
            raise ValueError(f"Attachment {item['name']!r} exceeds the 25 MiB limit")
        destination = _write_staged_attachment(destination_root, str(item["name"]), payload)
        row = dict(item)
        row["size"] = len(payload)
        row["path"] = str(destination)
        staged.append(row)
    return staged


def _room_prompt(room: Mapping[str, Any], member: Mapping[str, str], transcript: Sequence[Mapping[str, Any]], attachments: Sequence[Mapping[str, Any]], thread_id: Optional[str], round_number: int) -> str:
    lines = [
        f"You are @{member['handle']} in Clio team room {room['name']!r}.",
        f"Round {round_number}/{ROOM_MAX_ROUNDS}. Reply briefly only if you add new value.",
        "Reply with exactly PASS if you have nothing new. Mention @user only for a genuine user decision.",
        "Mention another room handle to make that Bot eligible in the next round.",
    ]
    if thread_id:
        lines.append(f"Thread: {thread_id}")
    lines.append("Unseen room messages since your previous turn:")
    if not transcript:
        lines.append("(none)")
    for message in transcript[-ROOM_HISTORY_LIMIT:]:
        lines.append(f"[{message.get('author', 'unknown')}] {message.get('content', '')}")
    if attachments:
        lines.append("Attachments (local references; inspect only if needed):")
        for item in attachments:
            lines.append(f"- {item['name']} ({item['mime_type']}, {item['size']} bytes): {item['path']}")
    return "\n".join(lines)


RoomResponder = Callable[[Mapping[str, str], str, str, float], Any]


def _default_room_responder(member: Mapping[str, str], prompt: str, session_id: str, hard_timeout: float) -> str:
    if member["source"] == "local":
        return run_profile_turn(member["profile"], session_id, prompt, timeout=hard_timeout)
    result = peer_dm(
        f"{member['source']}/{member['profile']}",
        prompt,
        sender="user",
        timeout=hard_timeout,
    )
    return str(result.get("reply") or "")


def _invoke_bounded(responder: RoomResponder, member: Mapping[str, str], prompt: str, session_id: str, hard_timeout: float) -> tuple[Any, float, bool]:
    started = time.monotonic()
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="clio-room-turn")
    future = pool.submit(responder, member, prompt, session_id, hard_timeout)
    timed_out = False
    try:
        value = future.result(timeout=hard_timeout)
    except FutureTimeout:
        timed_out = True
        future.cancel()
        value = None
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return value, time.monotonic() - started, timed_out


def send_room_message(
    room_id: str,
    message: str,
    *,
    attachments: Optional[Sequence[Mapping[str, Any]]] = None,
    thread_id: Optional[str] = None,
    responder: Optional[RoomResponder] = None,
    root: Optional[Path] = None,
    soft_timeout: float = ROOM_SOFT_TIMEOUT_SECONDS,
    hard_timeout: float = ROOM_HARD_TIMEOUT_SECONDS,
) -> RoomTurnResult:
    """Run a bounded serial room deliberation with epoch supersession.

    Only unseen room deltas are delivered to each member. Every attempt is
    durably reflected in the private ``activity`` feed, while passes, duplicate
    replies, failures, and timeouts remain absent from the visible transcript.
    A newer user send changes the epoch; the old run checks that epoch before
    and after every Bot call and cannot land a stale reply.
    """
    message = _safe_message_text(message, max_chars=100_000)
    clean_attachments = _prepare_attachments(attachments)
    soft_timeout = max(0.01, float(soft_timeout))
    hard_timeout = max(soft_timeout, float(hard_timeout))
    responder = responder or _default_room_responder

    with _ROOM_LOCK:
        store = _load_room_store(root)
        if _reconcile_room_store(store):
            _save_room_store(store, root)
        room = store["rooms"].get(room_id)
        if not isinstance(room, dict):
            raise KeyError(room_id)
        if any(member.get("source") != "local" for member in room.get("members") or []):
            oversized = [
                str(item["name"])
                for item in clean_attachments
                if int(item["size"]) > ROOM_REMOTE_ATTACHMENT_BYTES
            ]
            if oversized:
                raise ValueError(
                    "Remote Bot room attachments are limited to 7 MiB each; "
                    f"too large: {', '.join(oversized)}"
                )
        epoch = int(room.get("active_epoch") or 0) + 1
        room["active_epoch"] = epoch
        room["state"] = "running"
        room["needs_user"] = False
        now = time.time()
        user_record = {
            "id": f"msg-{uuid.uuid4().hex[:12]}",
            "seq": _max_seq(room.get("messages") or []) + 1,
            "author": "user",
            "content": message,
            "created_at": now,
            "epoch": epoch,
            "thread_id": thread_id,
            "attachments": clean_attachments,
        }
        room.setdefault("messages", []).append(user_record)
        room["messages"] = room["messages"][-200:]
        room.setdefault("activity", [])
        room["updated_at"] = now
        _save_room_store(store, root)

    members = list(room["members"])
    handles = [member["handle"] for member in members]
    direct = _mentions(message, handles)
    eligible = set(handles if "@everyone" in message.lower() or not direct else direct)
    produced: List[Dict[str, Any]] = [user_record]
    seen_values = {
        _normalize_new_value(str(item.get("content") or ""))
        for item in room.get("messages", [])[-50:]
        if item.get("author") != "user"
    }
    suppressed = 0
    visible_bot_count = 0
    rounds_run = 0
    state = "settled"
    activity_run: List[Dict[str, Any]] = []

    for round_number in range(1, ROOM_MAX_ROUNDS + 1):
        rounds_run = round_number
        round_added = 0
        next_mentions: set[str] = set()
        for member in members:
            if member["handle"] not in eligible:
                continue
            if visible_bot_count >= ROOM_MAX_VISIBLE_PER_SEND:
                state = "message_cap"
                break

            activity_id = f"act-{uuid.uuid4().hex[:12]}"
            with _ROOM_LOCK:
                store = _load_room_store(root)
                current = store["rooms"].get(room_id)
                if not isinstance(current, dict) or int(current.get("active_epoch") or 0) != epoch:
                    state = "superseded"
                    break
                delta, delivered_through = _unseen_delta(current, member, thread_id)
                watermark_key = _watermark_key(member["handle"], thread_id)
                delivered_from = int((current.get("watermarks") or {}).get(watermark_key) or 0)
                current.setdefault("watermarks", {})[watermark_key] = delivered_through
                started_activity = {
                    "id": activity_id,
                    "epoch": epoch,
                    "round": round_number,
                    "member": member["handle"],
                    "profile": member["profile"],
                    "source": member["source"],
                    "state": "running",
                    "started_at": time.time(),
                    "delivered_from": delivered_from,
                    "delivered_through": delivered_through,
                }
                current.setdefault("activity", []).append(started_activity)
                current["activity"] = current["activity"][-500:]
                _save_room_store(store, root)

            error_text = ""
            try:
                if member["source"] == "local":
                    session = ensure_group_session(member["profile"], room_id, room["name"])
                    session_id = session["id"]
                else:
                    session_id = f"remote:{member['source']}:{member['profile']}:{room_id}"
                staged_attachments = _stage_attachments_for_member(
                    room_id,
                    member,
                    clean_attachments,
                )
                prompt = _room_prompt(
                    current,
                    member,
                    delta,
                    staged_attachments,
                    thread_id,
                    round_number,
                )
                raw_reply, elapsed, timed_out = _invoke_bounded(
                    responder, member, prompt, session_id, hard_timeout
                )
            except Exception as exc:
                raw_reply, elapsed, timed_out = None, 0.0, False
                error_text = str(exc)

            # Safe cancellation boundary after an expensive Bot call. A stale
            # reply is neither made visible nor written as current-epoch activity.
            with _ROOM_LOCK:
                latest = _load_room_store(root)["rooms"].get(room_id) or {}
            if int(latest.get("active_epoch") or 0) != epoch:
                state = "superseded"
                break

            reply_meta: Dict[str, Any] = {}
            if isinstance(raw_reply, dict):
                if raw_reply.get("error"):
                    error_text = str(raw_reply["error"])
                    reply = ""
                else:
                    reply = str(raw_reply.get("reply") or raw_reply.get("content") or "")
                    reply_meta = {
                        key: value
                        for key, value in raw_reply.items()
                        if key not in {"reply", "content", "error"}
                    }
            else:
                reply = str(raw_reply or "")
            reply = reply.strip()
            normalized = _normalize_new_value(reply)

            if timed_out or elapsed > hard_timeout:
                outcome = "timeout"
                error_text = error_text or f"Bot turn exceeded {hard_timeout:g}s"
                visible = False
            elif error_text:
                outcome = "failed"
                visible = False
            elif is_hidden_pass(reply):
                outcome = "pass"
                visible = False
            elif not normalized or normalized in seen_values:
                outcome = "duplicate"
                visible = False
            else:
                outcome = "reply"
                visible = True

            finished_activity = {
                "id": f"{activity_id}-done",
                "attempt_id": activity_id,
                "epoch": epoch,
                "round": round_number,
                "member": member["handle"],
                "profile": member["profile"],
                "source": member["source"],
                "state": outcome,
                "elapsed_seconds": elapsed,
                "late": elapsed > soft_timeout,
                "finished_at": time.time(),
                **({"error": error_text[:2000]} if error_text else {}),
                **({"metadata": reply_meta} if reply_meta else {}),
            }
            activity_run.append(finished_activity)

            with _ROOM_LOCK:
                store = _load_room_store(root)
                current = store["rooms"].get(room_id)
                if not isinstance(current, dict) or int(current.get("active_epoch") or 0) != epoch:
                    state = "superseded"
                    break
                current.setdefault("activity", []).append(finished_activity)
                current["activity"] = current["activity"][-500:]
                if not visible:
                    current["updated_at"] = finished_activity["finished_at"]
                    _save_room_store(store, root)
                    suppressed += 1
                    continue

                seen_values.add(normalized)
                record = {
                    "id": f"msg-{uuid.uuid4().hex[:12]}",
                    "seq": _max_seq(current.get("messages") or []) + 1,
                    "author": member["handle"],
                    "profile": member["profile"],
                    "source": member["source"],
                    "content": reply,
                    "created_at": time.time(),
                    "epoch": epoch,
                    "round": round_number,
                    "thread_id": thread_id,
                    "late": elapsed > soft_timeout,
                }
                current.setdefault("messages", []).append(record)
                current["messages"] = current["messages"][-200:]
                current["needs_user"] = bool(current.get("needs_user")) or "@user" in reply.lower()
                current["updated_at"] = record["created_at"]
                _save_room_store(store, root)

            produced.append(record)
            visible_bot_count += 1
            round_added += 1
            if "@everyone" in reply.lower():
                next_mentions.update(handles)
            else:
                next_mentions.update(_mentions(reply, handles))

        if state in {"superseded", "message_cap"}:
            break
        if round_added == 0:
            state = "settled"
            break
        if not next_mentions:
            state = "settled"
            break
        eligible = set(next_mentions)
        if round_number == ROOM_MAX_ROUNDS:
            state = "round_cap"

    with _ROOM_LOCK:
        store = _load_room_store(root)
        current = store["rooms"].get(room_id)
        if isinstance(current, dict) and int(current.get("active_epoch") or 0) == epoch:
            current["state"] = "needs_user" if current.get("needs_user") else state
            current["updated_at"] = time.time()
            _save_room_store(store, root)
            needs_user = bool(current.get("needs_user"))
        else:
            needs_user = False
            state = "superseded"

    return RoomTurnResult(
        room_id=room_id,
        epoch=epoch,
        rounds=rounds_run,
        state=state,
        needs_user=needs_user,
        messages=produced,
        suppressed=suppressed,
        activity=activity_run,
    )


@contextlib.contextmanager
def _cron_for_profile(profile: str) -> Iterator[Any]:
    home = profile_home(profile)
    with _CRON_LOCK:
        from cron import jobs

        old = (jobs.CRON_DIR, jobs.JOBS_FILE, jobs.OUTPUT_DIR)
        jobs.CRON_DIR = home / "cron"
        jobs.JOBS_FILE = jobs.CRON_DIR / "jobs.json"
        jobs.OUTPUT_DIR = jobs.CRON_DIR / "output"
        try:
            yield jobs
        finally:
            jobs.CRON_DIR, jobs.JOBS_FILE, jobs.OUTPUT_DIR = old


def routine_name(profile: str, name: str) -> str:
    profile = _validate_profile(profile)
    clean = re.sub(r"\s+", " ", str(name or "")).strip()
    if not clean:
        raise ValueError("Routine name is required")
    return f"[bot:{profile}] {clean}"


def list_bot_routines(profile: Optional[str] = None) -> List[Dict[str, Any]]:
    profiles = [_validate_profile(profile)] if profile else [item.name for item in _profiles_module().list_profiles()]
    result: List[Dict[str, Any]] = []
    for name in profiles:
        with _cron_for_profile(name) as jobs:
            for job in jobs.list_jobs(True):
                if str(job.get("name") or "").startswith(f"[bot:{name}]"):
                    result.append({**job, "bot_profile": name})
    return result


def create_bot_routine(profile: str, *, name: str, prompt: str, schedule: str, deliver: str = "local") -> Dict[str, Any]:
    profile = _validate_profile(profile)
    prompt = _safe_message_text(prompt)
    with _cron_for_profile(profile) as jobs:
        job = jobs.create_job(
            prompt=prompt,
            schedule=schedule,
            name=routine_name(profile, name),
            deliver=deliver,
            profile=profile,
        )
    return {**job, "bot_profile": profile}


def _peer_key_env(name: str) -> str:
    return f"CLIO_PEER_{name.upper().replace('-', '_')}_KEY"


def load_peers() -> Dict[str, Dict[str, Any]]:
    from clio_cli.config import load_config

    config = load_config() or {}
    peers = config.get("bot_peers")
    return dict(peers) if isinstance(peers, dict) else {}


def _peer_host_is_local_or_private(hostname: str) -> bool:
    host = str(hostname or "").strip().lower().rstrip(".")
    if host in {"localhost", "::1"} or host.endswith(".localhost"):
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return host.endswith(".local")
    return bool(address.is_loopback or address.is_private or address.is_link_local)


def save_peer(
    name: str,
    url: str,
    *,
    key: str = "",
    note: str = "",
    allow_insecure: bool = False,
) -> Dict[str, Any]:
    name = _validate_source(name)
    parsed = urllib.parse.urlsplit(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("Peer URL must be an http(s) base URL without embedded credentials")
    if parsed.scheme == "http" and not allow_insecure and not _peer_host_is_local_or_private(parsed.hostname or ""):
        raise ValueError("Non-local Bot peers require HTTPS; pass --allow-insecure only for an explicitly trusted network")
    clean_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))
    from clio_cli.config import load_config, save_config, save_env_value

    config = load_config() or {}
    raw_peers = config.get("bot_peers")
    peers: Dict[str, Any] = dict(raw_peers) if isinstance(raw_peers, dict) else {}
    peers[name] = {"url": clean_url, **({"note": note.strip()} if note.strip() else {})}
    config["bot_peers"] = peers
    save_config(config)
    if key:
        save_env_value(_peer_key_env(name), key)
    return peers[name]


def remove_peer(name: str) -> bool:
    name = _validate_source(name)
    from clio_cli.config import load_config, save_config

    config = load_config() or {}
    peers = dict(config.get("bot_peers") or {}) if isinstance(config.get("bot_peers"), dict) else {}
    existed = peers.pop(name, None) is not None
    if existed:
        config["bot_peers"] = peers
        save_config(config)
    return existed


def peer_secret(name: str) -> str:
    env_name = _peer_key_env(name)
    try:
        from clio_cli.config import load_env

        value = load_env().get(env_name) or os.environ.get(env_name, "")
    except Exception:
        value = os.environ.get(env_name, "")
    return str(value or "").strip()


class _NoPeerRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Never replay a peer bearer credential to a redirect destination."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ANN201
        return None


def _peer_request(url: str, key: str, *, method: str = "GET", body: Optional[Mapping[str, Any]] = None, timeout: float = 30.0) -> Dict[str, Any]:
    data = json.dumps(dict(body)).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "clio-peer/1"},
    )
    opener = urllib.request.build_opener(_NoPeerRedirectHandler())
    with opener.open(request, timeout=timeout) as response:  # noqa: S310 - explicitly registered peer URL
        payload_bytes = response.read(PEER_MAX_RESPONSE_BYTES + 1)
    if len(payload_bytes) > PEER_MAX_RESPONSE_BYTES:
        raise BotModeError("Peer response exceeds the 1 MiB limit")
    payload = payload_bytes.decode("utf-8", "replace")
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise BotModeError("Peer returned a non-object response")
    return parsed


def upload_peer_room_attachment(
    peer_name: str,
    profile: str,
    room_id: str,
    attachment: Mapping[str, Any],
    *,
    timeout: float = 60.0,
) -> Dict[str, Any]:
    """Upload one local room file to an authenticated peer without redirects."""
    peer_name = _validate_source(peer_name)
    profile = _validate_profile(profile)
    room_id = _validate_room_staging_id(room_id)
    peer = load_peers().get(peer_name)
    if not isinstance(peer, dict) or not peer.get("url"):
        raise BotModeError(f"No peer named '{peer_name}'")
    parsed = urllib.parse.urlsplit(str(peer["url"]).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        raise BotModeError(f"Peer '{peer_name}' has an invalid URL")
    key = peer_secret(peer_name)
    if not key:
        raise BotModeError(f"No API key configured for peer '{peer_name}' ({_peer_key_env(peer_name)})")

    source = Path(str(attachment.get("path") or "")).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"Room attachment does not exist: {source}")
    name = _validate_attachment_name(attachment.get("name") or source.name)
    mime_type = _validate_attachment_mime(attachment.get("mime_type") or "")
    with source.open("rb") as handle:
        payload = handle.read(ROOM_REMOTE_ATTACHMENT_BYTES + 1)
    if len(payload) > ROOM_REMOTE_ATTACHMENT_BYTES:
        raise ValueError(f"Remote Bot room attachment {name!r} exceeds the 7 MiB per-file limit")

    base = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))
    try:
        result = _peer_request(
            f"{base}/api/bots/{urllib.parse.quote(profile, safe='')}/attachments",
            key,
            method="POST",
            body={
                "room_id": room_id,
                "name": name,
                "mime_type": mime_type,
                "size": len(payload),
                "base64_data": base64.b64encode(payload).decode("ascii"),
            },
            timeout=max(0.1, float(timeout)),
        )
    except urllib.error.HTTPError as exc:
        detail = exc.read(1001)[:1000].decode("utf-8", "replace")
        raise BotModeError(
            f"Peer rejected room attachment (HTTP {exc.code}); redirects are not followed: {detail}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise BotModeError(f"Could not upload room attachment to peer '{peer_name}': {exc}") from exc

    received = result.get("attachment")
    if not isinstance(received, dict) or not isinstance(received.get("path"), str) or not received["path"]:
        raise BotModeError(f"Peer '{peer_name}' returned no receiver-local attachment path")
    if (
        received.get("name") != name
        or received.get("mime_type") != mime_type
        or received.get("size") != len(payload)
    ):
        raise BotModeError(f"Peer '{peer_name}' returned mismatched attachment metadata")
    return {
        "name": name,
        "mime_type": mime_type,
        "size": len(payload),
        "path": received["path"],
    }


def fetch_peer_roster(
    name: str,
    *,
    include_hidden: bool = False,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """Fetch one registered peer's authenticated, source-stamped Bot inventory."""
    name = _validate_source(name)
    peer = load_peers().get(name)
    if not isinstance(peer, dict) or not peer.get("url"):
        raise BotModeError(f"No peer named '{name}'")
    key = peer_secret(name)
    if not key:
        raise BotModeError(f"No API key configured for peer '{name}' ({_peer_key_env(name)})")
    base = str(peer["url"]).rstrip("/")
    query = "?include_hidden=true" if include_hidden else ""
    try:
        payload = _peer_request(f"{base}/api/bots{query}", key, timeout=max(0.1, float(timeout)))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:1000]
        raise BotModeError(f"Peer rejected roster request (HTTP {exc.code}): {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise BotModeError(f"Could not read Bot roster from peer '{name}': {exc}") from exc

    raw_bots = payload.get("data")
    if not isinstance(raw_bots, list):
        raw_bots = payload.get("bots")
    if not isinstance(raw_bots, list):
        raise BotModeError(f"Peer '{name}' returned no Bot roster")
    label = str(peer.get("label") or peer.get("note") or name).strip() or name
    bots: List[Dict[str, Any]] = []
    for raw in raw_bots:
        if not isinstance(raw, dict):
            continue
        profile = _validate_profile(str(raw.get("profile") or raw.get("name") or ""))
        bots.append(
            {
                **raw,
                "profile": profile,
                "source": name,
                "source_label": label,
                "key": f"{name}:{profile}",
            }
        )
    return {"source": name, "label": label, "url": base, "bots": bots}


def list_connected_bot_roster(
    peer_names: Optional[Sequence[str]] = None,
    *,
    include_local: bool = True,
    include_hidden: bool = False,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """Merge connection inventories and report offline peers without hiding healthy sources."""
    selected = list(peer_names) if peer_names is not None else sorted(load_peers())
    sources: Dict[str, Mapping[str, Any]] = {}
    errors: Dict[str, str] = {}
    if include_local:
        sources["local"] = {
            "label": "This device",
            "bots": list_bot_roster(include_hidden=include_hidden),
        }
    for raw_name in selected:
        try:
            name = _validate_source(raw_name)
            sources[name] = fetch_peer_roster(
                name,
                include_hidden=include_hidden,
                timeout=timeout,
            )
        except (BotModeError, OSError, ValueError) as exc:
            errors[str(raw_name)] = str(exc)
    return {
        "bots": source_qualified_roster(sources),
        "sources": [
            {
                "id": name,
                "label": str(payload.get("label") or name),
                "bot_count": len(payload.get("bots") or []),
            }
            for name, payload in sources.items()
        ],
        "errors": errors,
    }


def peer_dm(target: str, message: str, *, sender: str = "user", timeout: float = 600.0) -> Dict[str, Any]:
    peer_name, separator, profile = str(target or "").strip().partition("/")
    peer_name = _validate_source(peer_name)
    profile = _validate_profile(profile) if separator and profile else "default"
    peers = load_peers()
    peer = peers.get(peer_name)
    if not isinstance(peer, dict) or not peer.get("url"):
        raise BotModeError(f"No peer named '{peer_name}'")
    key = peer_secret(peer_name)
    if not key:
        raise BotModeError(f"No API key configured for peer '{peer_name}' ({_peer_key_env(peer_name)})")
    message = _safe_message_text(message)
    base = str(peer["url"]).rstrip("/")
    try:
        result = _peer_request(
            f"{base}/api/bots/{urllib.parse.quote(profile, safe='')}/dm",
            key,
            method="POST",
            body={"message": message, "sender": sender},
            timeout=timeout,
        )
    except urllib.error.HTTPError as exc:
        if exc.code not in {404, 405} or profile != "default":
            detail = exc.read().decode("utf-8", "replace")[:1000]
            raise BotModeError(f"Peer rejected DM (HTTP {exc.code}): {detail}") from exc
        # Compatibility fallback for older single-profile API servers.
        listing = _peer_request(f"{base}/api/sessions?limit=200", key)
        session_id = next(
            (str(row.get("id")) for row in listing.get("data") or [] if isinstance(row, dict) and row.get("title") == BOT_CHAT_TITLE),
            "",
        )
        if not session_id:
            created = _peer_request(
                f"{base}/api/sessions",
                key,
                method="POST",
                body={"title": BOT_CHAT_TITLE, "source": "bot_peer_dm"},
            )
            session_id = str((created.get("session") or {}).get("id") or "")
        result = _peer_request(
            f"{base}/api/sessions/{urllib.parse.quote(session_id, safe='')}/chat",
            key,
            method="POST",
            body={"message": f"Message from Clio Bot {sender} (@{sender}):\n\n{message}"},
            timeout=timeout,
        )
    reply = result.get("reply")
    if reply is None and isinstance(result.get("message"), dict):
        reply = result["message"].get("content")
    return {"peer": peer_name, "profile": profile, "reply": str(reply or ""), "session_id": result.get("session_id")}


__all__ = [
    "BOT_CANONICAL_KEY",
    "BOT_CHAT_TITLE",
    "BOT_PROTOCOL_VERSION",
    "ROOM_MAX_ATTACHMENTS",
    "ROOM_MAX_ATTACHMENT_BYTES",
    "ROOM_REMOTE_ATTACHMENT_BYTES",
    "BotAddress",
    "BotModeError",
    "RoomTurnResult",
    "capability_fingerprint",
    "create_bot_routine",
    "create_room",
    "delete_room",
    "ensure_bot_chat",
    "ensure_canonical_session",
    "ensure_group_session",
    "fetch_peer_roster",
    "get_room",
    "list_bot_roster",
    "list_bot_routines",
    "list_connected_bot_roster",
    "list_rooms",
    "load_peers",
    "local_dm",
    "maybe_refresh_bot_prompt",
    "peer_dm",
    "read_bot_metadata",
    "remove_peer",
    "run_profile_turn",
    "save_peer",
    "send_room_message",
    "stage_received_room_attachment",
    "source_qualified_roster",
    "update_bot_metadata",
    "upload_peer_room_attachment",
]
