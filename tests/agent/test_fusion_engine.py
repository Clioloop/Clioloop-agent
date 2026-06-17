"""Tests for the Fusion thin client (agent/fusion_engine.py).

The Fusion engine now runs server-side on the Omni Loop Portal; this module is a
thin client. These tests cover config parsing/serialization, UI helpers, the
local gate, and the start/step protocol that drives the portal — with httpx and
the managed-token/portal-base helpers mocked. No prompt or pipeline text lives
in the client, so none is asserted here.
"""

from __future__ import annotations

import sys
import types

import pytest

from agent import fusion_engine as fusion


# ---------------------------------------------------------------------------
# Config parsing + serialization
# ---------------------------------------------------------------------------

def test_parse_fusion_args_extended_form():
    cfg = fusion.parse_fusion_args(["advisors=a/x,b/y", "reviewers=r/z", "judge=j/m"])
    assert cfg is not None
    assert cfg.advisors == ["a/x", "b/y"]
    assert cfg.reviewers == ["r/z"]
    assert cfg.judge == "j/m"
    assert cfg.enabled is True
    assert cfg.is_complete()


def test_parse_fusion_args_planners_alias_and_mode():
    cfg = fusion.parse_fusion_args(["fast", "planners=a", "reviewers=b"])
    assert cfg is not None
    assert cfg.mode == "fast"
    assert cfg.advisors == ["a"]
    assert cfg.reviewers == ["b"]


def test_parse_fusion_args_clamps_to_max_per_group():
    many = ",".join(f"m{i}" for i in range(10))
    cfg = fusion.parse_fusion_args([f"advisors={many}", f"reviewers={many}"])
    assert cfg is not None
    assert len(cfg.advisors) == fusion.FUSION_MAX_MODELS_PER_GROUP
    assert len(cfg.reviewers) == fusion.FUSION_MAX_MODELS_PER_GROUP


def test_parse_fusion_args_legacy_three_token_form():
    cfg = fusion.parse_fusion_args(["m1", "m2", "judge"])
    assert cfg is not None
    assert cfg.advisors == ["m1", "m2"]
    assert cfg.reviewers == ["m1", "m2"]
    assert cfg.judge == "judge"


def test_parse_fusion_args_incomplete_returns_none():
    assert fusion.parse_fusion_args(["advisors=a"]) is None
    assert fusion.parse_fusion_args([]) is None


def test_config_dict_round_trip_and_legacy_back_compat():
    cfg = fusion.FusionConfig(advisors=["a"], reviewers=["b"], judge="j", mode="full")
    assert fusion.FusionConfig.from_dict(cfg.to_dict()) == cfg
    legacy = fusion.FusionConfig.from_dict({"model_1": "x", "model_2": "y", "judge": "z"})
    assert legacy.advisors == ["x", "y"]
    assert legacy.reviewers == ["x", "y"]
    assert legacy.judge == "z"


def test_model_open_tag_and_label():
    assert fusion.model_open_tag("openai/gpt-oss-120b:free") == "(free)"
    assert fusion.model_open_tag("anthropic/claude") == "(openrouter)"
    assert fusion.model_open_tag("llama3") == "(open)"
    assert fusion.label_model("anthropic/claude") == "anthropic/claude (openrouter)"


def test_fusion_is_active_requires_enabled_and_complete():
    agent = types.SimpleNamespace()
    agent._fusion_config = fusion.FusionConfig(advisors=["a"], reviewers=["b"], enabled=True)
    assert fusion.fusion_is_active(agent) is True
    agent._fusion_config.enabled = False
    assert fusion.fusion_is_active(agent) is False


# ---------------------------------------------------------------------------
# Protocol harness
# ---------------------------------------------------------------------------

class FakeResp:
    def __init__(self, status: int, payload: dict):
        self.status_code = status
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class FakeClient:
    """Yields queued responses in order; records posted bodies."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.requests = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, url, headers=None, json=None):
        self.requests.append((url, json))
        return self._responses.pop(0)


class FakeAgent:
    def __init__(self):
        self.model = "vendor/main"
        self.tools = [
            {"type": "function", "function": {"name": "read_file", "description": "Read a file."}},
            {"type": "function", "function": {"name": "image_generate", "description": "Make an image."}},
        ]
        self.valid_tool_names = {"read_file", "image_generate"}
        self.calls = []

    def run_conversation(self, message, **kwargs):
        # Capture the toolset visible at call time so hide/restore can be asserted.
        self.calls.append({
            "message": message,
            "kwargs": kwargs,
            "tool_names": [t["function"]["name"] for t in self.tools],
            # Snapshot the draft-suppression flag as seen by the local turn so
            # tests can assert it is on only for work/revise and off for finalize.
            "hide_draft": bool(getattr(self, "_fusion_hide_draft", False)),
        })
        if kwargs.get("internal_turn"):
            return {"final_response": "WORK DRAFT"}
        return {"final_response": "FINAL ANSWER", "messages": [], "api_calls": 1}


@pytest.fixture
def wire(monkeypatch):
    """Allow fusion, provide a token + base, and inject a fake httpx with queued responses."""
    monkeypatch.setattr(fusion, "fusion_gate_check", lambda force_fresh=False: (True, ""))
    monkeypatch.setattr(fusion, "_managed_access_token", lambda: "tok")
    monkeypatch.setattr(fusion, "_portal_base_url", lambda: "https://portal.test")

    state = {"client": None}

    def install(responses):
        client = FakeClient(responses)
        fake_httpx = types.ModuleType("httpx")
        fake_httpx.Timeout = lambda *a, **k: None
        fake_httpx.Client = lambda timeout=None: client
        monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
        state["client"] = client
        return client

    return install, state


def _cfg():
    return fusion.FusionConfig(
        advisors=["vendor/a"], reviewers=["vendor/r"], enabled=True, mode="full"
    )


# ---------------------------------------------------------------------------
# run_fusion_turn
# ---------------------------------------------------------------------------

def test_misconfigured_config_runs_normal_turn():
    agent = FakeAgent()
    out = fusion.run_fusion_turn(agent, "hello", config=fusion.FusionConfig())
    assert out["final_response"] == "FINAL ANSWER"
    assert len(agent.calls) == 1
    assert agent.calls[0]["kwargs"].get("internal_turn") in (None, False)


def test_gate_denied_returns_reason(monkeypatch):
    agent = FakeAgent()
    monkeypatch.setattr(fusion, "fusion_gate_check", lambda force_fresh=False: (False, "nope"))
    out = fusion.run_fusion_turn(agent, "do the thing", config=_cfg())
    assert out["failed"] is True
    assert out["final_response"] == "nope"
    assert agent.calls == []


def test_auto_gate_skips_panel_for_tiny_message(wire):
    install, state = wire
    agent = FakeAgent()
    cfg = fusion.FusionConfig(advisors=["a"], reviewers=["b"], enabled=True, mode="auto")
    out = fusion.run_fusion_turn(agent, "hi there", config=cfg)
    assert out["final_response"] == "FINAL ANSWER"
    # No portal client was installed/used for a trivially small message.
    assert state["client"] is None


def test_full_protocol_start_work_finalize(wire):
    install, state = wire
    agent = FakeAgent()
    meta = {"version": 2, "main_model": "vendor/main"}
    install([
        FakeResp(200, {
            "action": "work", "session_id": "s1",
            "message": "WORK PROMPT", "events": [{"phase": "planning", "text": "planning…"}],
        }),
        FakeResp(200, {
            "action": "finalize", "message": "FINALIZE PROMPT",
            "hide_image_tool": False, "fusion": meta, "events": [],
        }),
    ])
    progress_phases = []
    out = fusion.run_fusion_turn(
        agent, "build the feature", config=_cfg(),
        progress=lambda e: progress_phases.append(e.phase),
    )
    assert out["final_response"] == "FINAL ANSWER"
    assert out["fusion"] == meta
    # One internal work turn + one visible finalize turn.
    assert agent.calls[0]["kwargs"].get("internal_turn") is True
    assert agent.calls[0]["message"] == "WORK PROMPT"
    assert agent.calls[1]["kwargs"].get("internal_turn") in (None, False)
    assert agent.calls[1]["message"] == "FINALIZE PROMPT"
    # The work draft was posted back to /step.
    assert any("/step" in url and body.get("draft") == "WORK DRAFT"
               for url, body in state["client"].requests)
    assert "planning" in progress_phases


def test_draft_is_hidden_during_work_but_not_finalize(wire):
    install, state = wire
    agent = FakeAgent()
    install([
        FakeResp(200, {"action": "work", "session_id": "s1", "message": "W", "events": []}),
        FakeResp(200, {"action": "finalize", "message": "F", "hide_image_tool": False, "events": []}),
    ])
    fusion.run_fusion_turn(agent, "build the feature", config=_cfg())
    # Work turn ran with the draft hidden; finalize streamed the fused answer.
    assert agent.calls[0]["kwargs"].get("internal_turn") is True
    assert agent.calls[0]["hide_draft"] is True
    assert agent.calls[1]["hide_draft"] is False
    # Flag is always cleared once the turn returns.
    assert getattr(agent, "_fusion_hide_draft", False) is False


def test_draft_hidden_flag_cleared_when_work_turn_raises(wire):
    install, state = wire

    class BoomAgent(FakeAgent):
        def run_conversation(self, message, **kwargs):
            if kwargs.get("internal_turn"):
                raise RuntimeError("boom")
            return super().run_conversation(message, **kwargs)

    agent = BoomAgent()
    install([
        FakeResp(200, {"action": "work", "session_id": "s1", "message": "W", "events": []}),
    ])
    # The work turn raises; run_fusion_turn falls back to a normal turn, but the
    # draft-suppression flag must not leak into that (visible) fallback turn.
    out = fusion.run_fusion_turn(agent, "build the feature", config=_cfg())
    assert out["final_response"] == "FINAL ANSWER"
    assert getattr(agent, "_fusion_hide_draft", False) is False
    # The fallback (normal) turn ran with the draft visible.
    assert agent.calls[-1]["hide_draft"] is False


def test_finalize_hides_image_tool_during_local_turn(wire):
    install, state = wire
    agent = FakeAgent()
    install([
        FakeResp(200, {"action": "work", "session_id": "s1", "message": "W", "events": []}),
        FakeResp(200, {"action": "finalize", "message": "F", "hide_image_tool": True, "events": []}),
    ])
    fusion.run_fusion_turn(agent, "render an image", config=_cfg())
    finalize_call = agent.calls[1]
    assert "image_generate" not in finalize_call["tool_names"]
    # Tools are restored after the turn.
    assert "image_generate" in agent.valid_tool_names


def test_deliver_action_returns_final_response(wire):
    install, state = wire
    agent = FakeAgent()
    install([
        FakeResp(200, {"action": "work", "session_id": "s1", "message": "W", "events": []}),
        FakeResp(200, {"action": "deliver", "final_response": "DRAFT+footer",
                       "fusion": {"degraded": "fusion budget reached"}, "events": []}),
    ])
    out = fusion.run_fusion_turn(agent, "long task", config=_cfg())
    assert out["final_response"] == "DRAFT+footer"
    assert out["completed"] is True
    # Only the work turn ran locally; deliver does not start a new turn.
    assert len(agent.calls) == 1


def test_start_fallback_runs_normal_turn(wire):
    install, state = wire
    agent = FakeAgent()
    install([FakeResp(200, {"action": "fallback", "events": []})])
    out = fusion.run_fusion_turn(agent, "build the feature", config=_cfg())
    assert out["final_response"] == "FINAL ANSWER"
    assert len(agent.calls) == 1
    assert agent.calls[0]["kwargs"].get("internal_turn") in (None, False)


def test_403_returns_plan_message(wire):
    install, state = wire
    agent = FakeAgent()
    install([FakeResp(403, {"error": {"message": "Fusion is a Pro-plan feature"}})])
    out = fusion.run_fusion_turn(agent, "build the feature", config=_cfg())
    assert out["failed"] is True
    assert "Pro-plan" in out["final_response"]
    assert agent.calls == []


def test_404_old_portal_falls_back(wire):
    install, state = wire
    agent = FakeAgent()
    install([FakeResp(404, {})])
    out = fusion.run_fusion_turn(agent, "build the feature", config=_cfg())
    assert out["final_response"] == "FINAL ANSWER"
    assert len(agent.calls) == 1


def test_no_token_falls_back(monkeypatch):
    agent = FakeAgent()
    monkeypatch.setattr(fusion, "fusion_gate_check", lambda force_fresh=False: (True, ""))
    monkeypatch.setattr(fusion, "_managed_access_token", lambda: None)
    out = fusion.run_fusion_turn(agent, "build the feature", config=_cfg())
    assert out["final_response"] == "FINAL ANSWER"
    assert len(agent.calls) == 1
