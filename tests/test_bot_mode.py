"""Acceptance tests for Clio-native profile-backed Bot Mode."""

from __future__ import annotations

import json
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
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


def test_protocol_is_injected_only_for_canonical_bot_chat(bot_env):
    homes, _root = bot_env
    canonical = bots.ensure_bot_chat("alpha")
    db = SessionDB(db_path=homes["alpha"] / "state.db")
    try:
        agent = SimpleNamespace(
            _session_db=db,
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
