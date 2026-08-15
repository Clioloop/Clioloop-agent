from __future__ import annotations

import argparse
from pathlib import Path

import pytest


def test_learning_graph_nodes_edges_and_empty_density(tmp_path, monkeypatch):
    from agent import learning_graph as graph

    skill = tmp_path / "skills" / "ops" / "alpha" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: alpha\ncategory: ops\nrelated_skills: [beta]\n---\n", encoding="utf-8")
    beta = skill.parent.parent / "beta" / "SKILL.md"
    beta.parent.mkdir()
    beta.write_text("---\nname: beta\ncategory: ops\n---\n", encoding="utf-8")
    monkeypatch.setattr(graph, "_load_usage", lambda: {})
    nodes = graph.build_skill_nodes([("profile", tmp_path / "skills")])
    assert set(nodes) == {"alpha", "beta"}
    assert graph.build_edges(nodes) == [("alpha", "beta")]
    assert graph.density_stats({}, []) ["isolated_pct"] == 0.0


def test_learning_records_are_durable_and_deduplicated(tmp_path, monkeypatch):
    from agent import learning_records as records

    path = tmp_path / "records.json"
    monkeypatch.setattr(records, "records_path", lambda: path)
    first = records.add_record("suggestion", "Add checks", dedup_key="checks")
    assert records.add_record("suggestion", "Duplicate", dedup_key="checks")["id"] == first["id"]
    assert records.update_record(first["id"], "accepted")["status"] == "accepted"
    assert records.list_records(status="accepted")[0]["title"] == "Add checks"
    assert records.delete_record(first["id"])


def test_learn_and_refine_prompts_preserve_safety_contract():
    from agent.learn_prompt import build_learn_prompt, build_refinement_prompt

    assert "untrusted data" in build_learn_prompt("https://example.invalid/input")
    assert "do not invent" in build_learn_prompt("x")
    assert "only approved" in build_refinement_prompt("tests")


def test_memory_journey_edit_and_delete_are_atomic(tmp_path, monkeypatch):
    import clio_constants
    from agent import learning_graph, learning_mutations
    from tools.memory_tool import MemoryStore

    home = tmp_path / ".clio"
    memories = home / "memories"
    memories.mkdir(parents=True)
    path = memories / "MEMORY.md"
    MemoryStore._write_file(path, ["first memory", "second memory"])
    monkeypatch.setattr(clio_constants, "get_clio_home", lambda: home)
    monkeypatch.setattr(learning_graph, "get_clio_home", lambda: home)

    detail = learning_mutations.node_detail("memory:memory:1")
    assert detail["ok"] and detail["content"] == "second memory"
    assert learning_mutations.edit_node("memory:memory:1", "updated memory")["ok"]
    assert MemoryStore._read_file(path) == ["first memory", "updated memory"]
    assert learning_mutations.delete_node("memory:memory:0")["ok"]
    assert MemoryStore._read_file(path) == ["updated memory"]


def test_heartbeat_due_tick_coalesces(monkeypatch):
    from clio_cli import heartbeat

    saved = []
    monkeypatch.setattr(heartbeat, "load_heartbeat", lambda _sid: None)
    monkeypatch.setattr(heartbeat, "save_heartbeat", lambda _sid, state: saved.append(state.to_json()))
    monkeypatch.setattr(heartbeat.time, "time", lambda: 1000.0)
    mgr = heartbeat.HeartbeatManager("s")
    state = mgr.set("check status", 60)
    assert mgr.due_prompt(now=1059) is None
    prompt = mgr.due_prompt(now=1060)
    assert "check status" in prompt
    assert mgr.due_prompt(now=1060) is None
    assert state.fire_count == 1 and saved


def test_loop_parsing_and_tick_budget(monkeypatch):
    from clio_cli import loops

    monkeypatch.setattr(loops, "load_loop", lambda _sid: None)
    monkeypatch.setattr(loops, "save_loop", lambda *_args: None)
    monkeypatch.setattr(loops, "min_interval_seconds", lambda: 5)
    parsed = loops.parse_loop_args("10s inspect --times 1 --until green")
    assert parsed == {"interval_seconds": 10, "prompt": "inspect", "times": 1, "until": "green", "error": None}
    mgr = loops.LoopManager("s")
    state = mgr.set("inspect", interval_seconds=10, times=1)
    state.next_due_at = 0
    assert "inspect" in mgr.fire_tick()
    decision = mgr.complete_tick("not complete")
    assert decision["status"] == "done" and state.ticks_fired == 1


def test_goal_gate_precedes_judge_and_wait_does_not_spend_turn(monkeypatch):
    from clio_cli import goals

    monkeypatch.setattr(goals, "load_goal", lambda _sid: None)
    monkeypatch.setattr(goals, "save_goal", lambda *_args: None)
    mgr = goals.GoalManager("s", default_max_turns=5)
    mgr.set("ship")
    mgr.add_gate("test-command", max_retries=2)
    monkeypatch.setattr(goals, "workspace_fingerprint", lambda *_args, **_kwargs: "fp")
    monkeypatch.setattr(goals, "run_gate", lambda *_args, **_kwargs: (False, 1, "failed"))
    monkeypatch.setattr(goals, "judge_goal", lambda *_args, **_kwargs: pytest.fail("judge must not run"))
    decision = mgr.evaluate_after_turn("claimed done")
    assert decision["verdict"] == "gate_failed" and mgr.state.turns_used == 1
    mgr.wait_for_seconds(60, "build running")
    before = mgr.state.turns_used
    assert mgr.evaluate_after_turn("ignored")["status"] == "waiting"
    assert mgr.state.turns_used == before


def test_gate_runner_success_and_failure():
    from clio_cli.goals import GoalGate, run_gate

    assert run_gate(GoalGate("printf ok"))[0] is True
    passed, code, output = run_gate(GoalGate("printf bad >&2; exit 7"))
    assert not passed and code == 7 and "bad" in output


def test_blueprint_validation_and_local_monitor():
    from cron.automation import fill_blueprint, get_blueprint, monitor_probe

    spec = fill_blueprint(get_blueprint("weekly-review"), {"time": "18:30", "day": "friday"})
    assert spec["schedule"] == "30 18 * * 5"
    with pytest.raises(ValueError):
        fill_blueprint(get_blueprint("morning-brief"), {"time": "25:00"})
    same = monitor_probe(command="printf stable", previous="stable")
    assert same["changed"] is False and same["diff"] == ""


def test_cron_notepad_round_trip_and_prompt_render(tmp_path, monkeypatch):
    from cron import notepad

    monkeypatch.setattr(notepad, "NOTEPAD_FILE", tmp_path / "notepad.db")
    note = notepad.set_note("job1", "cursor", "42")
    assert note["value"] == "42"
    assert notepad.get_note("job1", "cursor") == "42"
    assert "cursor: 42" in notepad.render_notepad_section("job1")
    assert notepad.delete_note("job1", "cursor")
    assert notepad.render_notepad_section("job1") == ""


def test_journey_parser_and_cron_helper_dispatch(monkeypatch, capsys):
    from clio_cli.journey import register_cli
    from clio_cli import cron as cron_cli

    parser = argparse.ArgumentParser()
    register_cli(parser)
    args = parser.parse_args(["list", "--json"])
    monkeypatch.setattr("clio_cli.journey._payload", lambda: {"nodes": [], "edges": [], "clusters": [], "memory": [], "stats": {"learned_skills": 0, "memory_nodes": 0}})
    assert args.func(args) == 0
    monkeypatch.setattr("cron.automation.monitor_probe", lambda **_kwargs: {"changed": False})
    ns = argparse.Namespace(cron_command="monitor", monitor_command="printf ok", url=None, previous=None, timeout=1)
    assert cron_cli.cron_command(ns) == 0
    assert "changed" in capsys.readouterr().out
