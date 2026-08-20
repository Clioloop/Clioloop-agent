"""Acceptance tests for Clio-native profile-backed Bot Mode."""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import threading
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

import clio_bot_mode as bots
from clio_state import SessionDB


class FakeProfiles:
    def __init__(self, homes: dict[str, Path]):
        self.homes = homes

    def profile_exists(self, name: str) -> bool:
        return name in self.homes

    def get_profile_dir(self, name: str) -> Path:
        return self.homes[name]

    def list_profiles(self):
        return [
            SimpleNamespace(
                name=name,
                model="test-model",
                provider="test-provider",
                gateway_running=False,
                is_default=name == "default",
            )
            for name in sorted(self.homes)
        ]


@pytest.fixture
def bot_env(tmp_path, monkeypatch):
    homes = {
        name: tmp_path / ("root" if name == "default" else f"root/profiles/{name}")
        for name in ("default", "alpha", "beta", "gamma", "delta", "epsilon")
    }
    for name, home in homes.items():
        home.mkdir(parents=True)
        (home / "profile.yaml").write_text(
            f"display_name: {name.title()}\nbot:\n  enabled: true\n",
            encoding="utf-8",
        )
    fake = FakeProfiles(homes)
    monkeypatch.setattr(bots, "_profiles_module", lambda: fake)
    return homes, tmp_path / "room-root"


def test_metadata_roster_and_canonical_session_are_profile_backed(bot_env):
    homes, _root = bot_env
    updated = bots.update_bot_metadata(
        "alpha",
        display_name="Research",
        title="Primary researcher",
        description="Finds evidence",
    )
    assert updated["display_name"] == "Research"
    assert updated["title"] == "Primary researcher"
    assert "bot:" in (homes["alpha"] / "profile.yaml").read_text(encoding="utf-8")

    roster = bots.list_bot_roster()
    alpha = next(item for item in roster if item["profile"] == "alpha")
    assert alpha["handle"] == "alpha"
    assert alpha["display_name"] == "Research"

    with ThreadPoolExecutor(max_workers=6) as pool:
        sessions = list(pool.map(lambda _index: bots.ensure_bot_chat("alpha"), range(12)))
    assert len({item["id"] for item in sessions}) == 1
    session_id = sessions[0]["id"]

    db = SessionDB(db_path=homes["alpha"] / "state.db")
    try:
        assert all(row["id"] != session_id for row in db.list_sessions_rich())
        assert any(row["id"] == session_id for row in db.list_sessions_rich(include_hidden=True))
        db.set_session_title(session_id, "Renamed but canonical")
        assert bots.ensure_bot_chat("alpha")["id"] == session_id
    finally:
        db.close()


def test_canonical_bot_chat_adopts_exact_legacy_title_without_forking(bot_env):
    homes, _root = bot_env
    db = SessionDB(db_path=homes["alpha"] / "state.db")
    try:
        legacy_id = db.create_session("legacy-bot-chat", source="cli")
        db.set_session_title(legacy_id, bots.BOT_CHAT_TITLE)
        ordinary_id = db.create_session("ordinary visible chat", source="cli")
    finally:
        db.close()

    adopted = bots.ensure_bot_chat("alpha")
    assert adopted["id"] == legacy_id
    assert bots.ensure_bot_chat("alpha")["id"] == legacy_id
    db = SessionDB(db_path=homes["alpha"] / "state.db")
    try:
        assert [row["id"] for row in db.list_sessions_rich()] == [ordinary_id]
        all_rows = db.list_sessions_rich(include_hidden=True)
        assert {row["id"] for row in all_rows} == {legacy_id, ordinary_id}
    finally:
        db.close()


def test_profile_rename_reconciles_room_and_canonical_session_by_stable_identity(bot_env):
    homes, root = bot_env
    room = bots.create_room("Rename", ["alpha", "beta"], root=root)
    original = bots.ensure_group_session("alpha", room["id"], room["name"])

    db = SessionDB(db_path=homes["alpha"] / "state.db")
    try:
        ordinary_id = db.create_session("ordinary", source="cli")
    finally:
        db.close()

    homes["researcher"] = homes.pop("alpha")
    reconciled = bots.get_room(room["id"], root=root)
    identity_id = bots.ensure_bot_identity("researcher")
    member = next(item for item in reconciled["members"] if item["identity_id"] == identity_id)
    assert member["profile"] == "researcher"
    assert member["handle"] == "researcher"

    rebound = bots.ensure_group_session("researcher", room["id"], room["name"])
    assert rebound["id"] == original["id"]
    db = SessionDB(db_path=homes["researcher"] / "state.db")
    try:
        ordinary = db.get_session(ordinary_id)
        assert ordinary is not None
        assert ordinary["owner_profile"] is None
        assert len(db.list_sessions_rich(include_hidden=True)) == 2
    finally:
        db.close()


def test_roster_reports_fresh_worker_activity_without_promoting_ordinary_sessions(bot_env):
    homes, _root = bot_env
    db = SessionDB(db_path=homes["alpha"] / "state.db")
    try:
        db.create_session("ordinary", source="cli")
        worker_id = db.create_session("worker", source="kanban")
        db.append_message(worker_id, "user", "work")
    finally:
        db.close()

    alpha = next(item for item in bots.list_bot_roster() if item["profile"] == "alpha")
    assert alpha["worker_active"] is True
    worker_session = alpha["worker_session"]
    assert worker_session is not None
    assert worker_session["id"] == worker_id
    assert worker_session["source"] == "kanban"


def test_local_dm_transport_never_shell_interpolates_message(bot_env, monkeypatch):
    homes, _root = bot_env
    captured = {}
    hostile = 'quotes " `backticks` $(touch /tmp/never)\nsecond line'

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        query_path = Path(command[command.index("--query-file") + 1])
        captured["payload"] = query_path.read_text(encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="verbatim reply\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = bots.local_dm("alpha", hostile, sender="beta")

    assert result["reply"] == "verbatim reply"
    assert isinstance(captured["command"], list)
    assert captured["kwargs"].get("shell") is None
    assert hostile in captured["payload"]
    assert hostile not in " ".join(captured["command"])
    query_path = Path(captured["command"][captured["command"].index("--query-file") + 1])
    assert not query_path.exists()
    assert captured["kwargs"]["cwd"] == str(Path(bots.__file__).resolve().parent)
    assert homes["alpha"] in query_path.parents


def test_room_mentions_passes_duplicates_and_watermarks(bot_env):
    _homes, root = bot_env
    room = bots.create_room("Review", ["alpha", "beta"], root=root)
    prompts: list[tuple[str, str]] = []
    calls = {"alpha": 0, "beta": 0}

    def responder(member, prompt, _session_id, _timeout):
        handle = member["handle"]
        prompts.append((handle, prompt))
        calls[handle] += 1
        if handle == "alpha" and calls[handle] == 1:
            return "Alpha finding"
        return "(pass)"

    first = bots.send_room_message(
        room["id"],
        "@alpha inspect this",
        responder=responder,
        root=root,
    )
    assert [message["author"] for message in first.messages] == ["user", "alpha"]
    assert first.suppressed == 0
    assert calls == {"alpha": 1, "beta": 0}

    second = bots.send_room_message(
        room["id"],
        "@alpha check the update",
        responder=responder,
        root=root,
    )
    assert [message["author"] for message in second.messages] == ["user"]
    assert second.suppressed == 1
    alpha_second_prompt = [prompt for handle, prompt in prompts if handle == "alpha"][-1]
    assert "check the update" in alpha_second_prompt
    assert "inspect this" not in alpha_second_prompt

    def duplicate(_member, _prompt, _session_id, _timeout):
        return "Alpha finding"

    third = bots.send_room_message(room["id"], "Run all", responder=duplicate, root=root)
    assert len(third.messages) == 1
    assert third.suppressed == 2


def test_room_caps_rounds_and_needs_user(bot_env):
    _homes, root = bot_env
    members = ["default", "alpha", "beta", "gamma", "delta", "epsilon"]
    room = bots.create_room("Worst case", members, root=root)

    counts = {member: 0 for member in members}

    def responder(member, _prompt, _session_id, _timeout):
        counts[member["profile"]] += 1
        return f"New value {counts[member['profile']]} from {member['handle']} @everyone"

    result = bots.send_room_message(room["id"], "Discuss", responder=responder, root=root)
    assert len([message for message in result.messages if message["author"] != "user"]) <= 10
    assert result.rounds <= 3
    assert result.state in {"message_cap", "round_cap"}

    room2 = bots.create_room("Decision", ["alpha", "beta"], root=root)
    decision = bots.send_room_message(
        room2["id"],
        "@alpha decide",
        responder=lambda *_args: "I need @user to choose A or B",
        root=root,
    )
    assert decision.needs_user is True
    assert bots.get_room(room2["id"], root=root)["state"] == "needs_user"


def test_room_handoff_routes_only_to_matching_epoch_and_session(bot_env, tmp_path):
    _homes, root = bot_env
    room = bots.create_room("Approval", ["alpha", "beta"], root=root)
    channel = tmp_path / "handoff.json"
    channel.write_text("{}", encoding="utf-8")
    request = {
        "request_id": "ask-1",
        "kind": "approval",
        "command": "rm example",
        "description": "Remove example",
        "choices": ["once", "session", "deny"],
        "_handoff_path": str(channel),
        "_handoff_token": "secret",
    }
    bots._publish_room_handoff(room["id"], 0, room["members"][0], "session-alpha", request, root)
    pending = bots.get_room(room["id"], root=root)["pending_user_action"]
    assert pending["session_id"] == "session-alpha"
    assert "_handoff_path" not in pending and "_handoff_token" not in pending

    with pytest.raises(ValueError, match="epoch and session_id are required"):
        bots.respond_room_user_action(room["id"], "ask-1", "once", root=root)
    with pytest.raises(bots.BotModeError, match="epoch and session"):
        bots.respond_room_user_action(
            room["id"], "ask-1", "once", epoch=1, session_id="session-alpha", root=root
        )
    with pytest.raises(bots.BotModeError, match="epoch and session"):
        bots.respond_room_user_action(
            room["id"], "ask-1", "once", epoch=0, session_id="wrong-session", root=root
        )

    result = bots.respond_room_user_action(
        room["id"], "ask-1", "once", epoch=0, session_id="session-alpha", root=root
    )
    assert result["accepted"] is True
    frame = json.loads(channel.read_text(encoding="utf-8"))
    assert frame == {
        "version": bots.BOT_HANDOFF_VERSION,
        "token": "secret",
        "state": "responded",
        "request_id": "ask-1",
        "response": "once",
    }
    current = bots.get_room(room["id"], root=root)
    assert current["pending_user_action"] is None
    assert current["messages"][-1]["handoff_request_id"] == "ask-1"


def test_room_failure_truth_and_attachment_profile_staging(bot_env, tmp_path):
    homes, root = bot_env
    source = tmp_path / "evidence.txt"
    source.write_text("evidence", encoding="utf-8")
    room = bots.create_room("Attachments", ["alpha", "beta"], root=root)
    staged: dict[str, Path] = {}

    def responder(member, prompt, _session_id, _timeout):
        path_line = next(line for line in prompt.splitlines() if "evidence.txt" in line)
        path = Path(path_line.rsplit(": ", 1)[1])
        staged[member["profile"]] = path
        if member["profile"] == "beta":
            raise RuntimeError("beta failed truthfully")
        return "Reviewed"

    result = bots.send_room_message(
        room["id"],
        "Review attachment",
        attachments=[{"path": str(source), "mime_type": "text/plain"}],
        responder=responder,
        root=root,
    )
    assert staged["alpha"] != staged["beta"]
    assert homes["alpha"] in staged["alpha"].parents
    assert homes["beta"] in staged["beta"].parents
    assert staged["alpha"].read_text(encoding="utf-8") == "evidence"
    assert any(item["state"] == "failed" and "beta failed" in item["error"] for item in (result.activity or []))
    assert all(message.get("author") != "beta" for message in result.messages)


def test_received_attachment_is_strict_confined_and_owner_only(bot_env, tmp_path, monkeypatch):
    homes, _root = bot_env
    payload = b"peer evidence"
    attachment = bots.stage_received_room_attachment(
        "alpha",
        "room-123",
        name="evidence.txt",
        mime_type="text/plain",
        size=len(payload),
        base64_data=base64.b64encode(payload).decode("ascii"),
    )
    staged = Path(attachment["path"])
    assert homes["alpha"].resolve() in staged.parents
    assert staged.read_bytes() == payload
    assert os.stat(staged).st_mode & 0o777 == 0o600
    assert os.stat(staged.parent).st_mode & 0o777 == 0o700

    invalid = {
        "name": "evidence.txt",
        "mime_type": "text/plain",
        "size": 1,
        "base64_data": "Zg==",
    }
    for override, message in (
        ({"base64_data": "Zh=="}, "canonical Base64"),
        ({"base64_data": "@@=="}, "strict Base64"),
        ({"size": 2}, "does not match"),
        ({"size": True}, "integer"),
        ({"name": "../escape.txt"}, "plain filename"),
        ({"mime_type": "application/zip"}, "Unsupported"),
        ({"mime_type": "text/plain; charset=utf-8"}, "invalid"),
    ):
        with pytest.raises(ValueError, match=message):
            bots.stage_received_room_attachment("alpha", "room-123", **(invalid | override))

    outside = tmp_path / "outside"
    outside.mkdir()
    (homes["beta"] / "tmp").symlink_to(outside, target_is_directory=True)
    with pytest.raises(bots.BotModeError, match="symlinked"):
        bots.stage_received_room_attachment("beta", "room-123", **invalid)
    assert list(outside.iterdir()) == []

    source = tmp_path / "sender.txt"
    source.write_bytes(payload)
    captured = {}

    def peer_request(url, key, **kwargs):
        captured.update(url=url, key=key, **kwargs)
        body = kwargs["body"]
        return {
            "attachment": {
                "name": body["name"],
                "mime_type": body["mime_type"],
                "size": body["size"],
                "path": "/receiver-local/random.txt",
            }
        }

    monkeypatch.setattr(bots, "load_peers", lambda: {"lab": {"url": "https://lab.example/base/"}})
    monkeypatch.setattr(bots, "peer_secret", lambda _name: "peer-secret")
    monkeypatch.setattr(bots, "_peer_request", peer_request)
    uploaded = bots.upload_peer_room_attachment(
        "lab",
        "alpha",
        "room-123",
        {"path": str(source), "name": "sender.txt", "mime_type": "text/plain"},
    )
    assert uploaded["path"] == "/receiver-local/random.txt"
    assert captured["url"] == "https://lab.example/base/api/bots/alpha/attachments"
    assert captured["key"] == "peer-secret"
    assert "path" not in captured["body"]
    assert base64.b64decode(captured["body"]["base64_data"], validate=True) == payload


def test_peer_requests_never_redirect_and_bound_response_reads(bot_env):
    class PeerHandler(BaseHTTPRequestHandler):
        requests: list[tuple[str, str | None]] = []

        def do_GET(self):  # noqa: N802 - stdlib handler contract
            type(self).requests.append((self.path, self.headers.get("Authorization")))
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "/credential-target")
                self.end_headers()
                return
            body = b"x" * (bots.PEER_MAX_RESPONSE_BYTES + 1)
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):  # noqa: A002
            pass

    server = HTTPServer(("127.0.0.1", 0), PeerHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with pytest.raises(urllib.error.HTTPError) as redirect_error:
            bots._peer_request(f"{base}/redirect", "peer-secret")
        assert redirect_error.value.code == 302
        with pytest.raises(bots.BotModeError, match="1 MiB"):
            bots._peer_request(f"{base}/large", "peer-secret")
    finally:
        server.shutdown()
        thread.join(timeout=5)
    assert PeerHandler.requests == [
        ("/redirect", "Bearer peer-secret"),
        ("/large", "Bearer peer-secret"),
    ]


def test_new_room_send_supersedes_stale_reply(bot_env):
    _homes, root = bot_env
    room = bots.create_room("Epoch", ["alpha", "beta"], root=root)
    entered = threading.Event()
    release = threading.Event()

    def slow(member, _prompt, _session_id, _timeout):
        if member["profile"] == "alpha":
            entered.set()
            release.wait(3)
            return "stale reply"
        return "PASS"

    holder = {}

    def run_first():
        holder["first"] = bots.send_room_message(
            room["id"],
            "@alpha first request",
            responder=slow,
            root=root,
            hard_timeout=5,
        )

    thread = threading.Thread(target=run_first)
    thread.start()
    assert entered.wait(2)
    second = bots.send_room_message(
        room["id"],
        "@beta second request",
        responder=slow,
        root=root,
    )
    release.set()
    thread.join(4)

    assert holder["first"].state == "superseded"
    assert second.epoch > holder["first"].epoch
    transcript = bots.get_room(room["id"], root=root)["messages"]
    assert all(message.get("content") != "stale reply" for message in transcript)


def test_room_bounds_and_pass_normalization(bot_env):
    _homes, root = bot_env
    assert bots.is_hidden_pass("")
    assert bots.is_hidden_pass("pass.")
    assert bots.is_hidden_pass("(PASS)")
    assert not bots.is_hidden_pass("I pass this to another Bot")
    with pytest.raises(ValueError, match="2-6"):
        bots.create_room("Too small", ["alpha"], root=root)
    with pytest.raises(ValueError, match="distinct"):
        bots.create_room("Duplicate", ["alpha", "alpha"], root=root)


def test_peer_tls_policy_and_remote_room_delivery(bot_env, monkeypatch):
    _homes, root = bot_env
    saved = {}
    monkeypatch.setattr("clio_cli.config.load_config", lambda: {})
    monkeypatch.setattr("clio_cli.config.save_config", lambda config: saved.update(config))
    monkeypatch.setattr("clio_cli.config.save_env_value", lambda *_args: True)
    with pytest.raises(ValueError, match="require HTTPS"):
        bots.save_peer("remote", "http://public.example")
    bots.save_peer("remote", "https://public.example", key="secret")
    assert saved["bot_peers"]["remote"]["url"] == "https://public.example"

    monkeypatch.setattr(bots, "load_peers", lambda: {"remote": {"url": "https://public.example"}})
    room = bots.create_room(
        "Hybrid",
        ["alpha", {"source": "remote", "profile": "research", "handle": "research-remote"}],
        root=root,
    )
    monkeypatch.setattr(
        bots,
        "peer_dm",
        lambda target, message, **kwargs: {"reply": f"remote reply from {target}"},
    )
    monkeypatch.setattr(bots, "run_profile_turn", lambda *_args, **_kwargs: "PASS")
    result = bots.send_room_message(room["id"], "@research-remote investigate", root=root)
    assert any("remote/research" in message["content"] for message in result.messages)


def test_connected_roster_uses_authenticated_peer_and_qualifies_collisions(bot_env, monkeypatch):
    class PeerHandler(BaseHTTPRequestHandler):
        auth = []

        def do_GET(self):  # noqa: N802 - stdlib handler contract
            type(self).auth.append(self.headers.get("Authorization"))
            assert self.path == "/api/bots?include_hidden=true"
            body = json.dumps(
                {
                    "object": "list",
                    "data": [
                        {"profile": "alpha", "display_name": "Remote Alpha"},
                        {"profile": "research", "display_name": "Research"},
                    ],
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):  # noqa: A002
            pass

    server = HTTPServer(("127.0.0.1", 0), PeerHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        monkeypatch.setattr(bots, "load_peers", lambda: {"lab": {"url": base, "label": "Lab"}})
        monkeypatch.setattr(bots, "peer_secret", lambda _name: "peer-secret")
        result = bots.list_connected_bot_roster(include_hidden=True)
    finally:
        server.shutdown()
        thread.join(timeout=5)

    by_key = {row["key"]: row for row in result["bots"]}
    assert by_key["local:alpha"]["handle"] == "alpha-this-device"
    assert by_key["lab:alpha"]["handle"] == "alpha-lab"
    assert by_key["lab:research"]["handle"] == "research-lab"
    assert result["errors"] == {}
    assert PeerHandler.auth == ["Bearer peer-secret"]


def test_connected_roster_keeps_healthy_sources_and_reports_peer_errors(bot_env, monkeypatch):
    monkeypatch.setattr(bots, "load_peers", lambda: {"offline": {"url": "http://127.0.0.1:1"}})
    monkeypatch.setattr(bots, "peer_secret", lambda _name: "peer-secret")
    result = bots.list_connected_bot_roster(timeout=0.1)
    assert any(row["source"] == "local" for row in result["bots"])
    assert "offline" in result["errors"]


def test_peer_roster_alias_dispatches(monkeypatch, capsys):
    from clio_cli.bot_mode import _cmd_peer

    monkeypatch.setattr(bots, "list_connected_bot_roster", lambda *args, **kwargs: {"bots": ["ok"]})
    _cmd_peer(
        argparse.Namespace(
            peer_action="bots",
            peers=[],
            no_local=True,
            include_hidden=False,
            timeout=1.0,
        )
    )
    assert json.loads(capsys.readouterr().out) == {"bots": ["ok"]}


def test_protocol_is_injected_only_for_canonical_bot_chat(bot_env):
    homes, _root = bot_env
    canonical = bots.ensure_bot_chat("alpha")
    db = SessionDB(db_path=homes["alpha"] / "state.db")
    try:
        agent = SimpleNamespace(
            _session_db=db,
            _session_db_created=True,
            session_id=canonical["id"],
            _bot_mode_protocol=True,
        )
        protocol = bots.bot_protocol_section_for_agent(agent)
        assert "canonical Bot Chat" in protocol
        assert "Clio Bot capability epoch:" in protocol

        ordinary_id = db.create_session("ordinary", source="cli")
        agent.session_id = ordinary_id
        assert bots.bot_protocol_section_for_agent(agent) == ""
        agent.session_id = canonical["id"]
        agent._bot_mode_protocol = False
        assert bots.bot_protocol_section_for_agent(agent) == ""
    finally:
        db.close()


def test_capability_fingerprint_changes_without_rewriting_soul(bot_env):
    homes, _root = bot_env
    soul = homes["alpha"] / "SOUL.md"
    soul.write_text("Original identity", encoding="utf-8")
    before = bots.capability_fingerprint("alpha")
    bots.update_bot_metadata("alpha", title="Changed title")
    after = bots.capability_fingerprint("alpha")
    assert before != after
    assert soul.read_text(encoding="utf-8") == "Original identity"
