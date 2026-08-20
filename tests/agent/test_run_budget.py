"""Wall-clock run-budget behavior and loop integration."""

from unittest.mock import patch

from agent.run_budget import TurnRunBudget, append_wrap_up_notice
from clio_cli._parser import build_top_level_parser
from tests.run_agent.test_tool_call_guardrail_runtime import _make_agent, _mock_response


def test_budget_math_wrap_threshold_and_timeout_clamp():
    now = [100.0]
    budget = TurnRunBudget(10.0, clock=lambda: now[0])
    assert budget.remaining == 10.0
    assert budget.should_wrap_up is False
    now[0] = 108.0
    assert budget.should_wrap_up is True
    assert budget.bound_timeout(90.0) == 2.0
    budget.mark_wrap_up()
    assert budget.should_wrap_up is False
    now[0] = 110.1
    assert budget.expired is True


def test_wrap_notice_preserves_roles_and_is_idempotent():
    messages = [
        {"role": "user", "content": "do work"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "1"}]},
        {"role": "tool", "tool_call_id": "1", "content": "result"},
    ]
    assert append_wrap_up_notice(messages) is True
    assert append_wrap_up_notice(messages) is True
    assert messages[-1]["role"] == "tool"
    assert messages[-1]["content"].count("[Clio run-budget notice:") == 1


def test_loop_injects_wrap_notice_once_before_api_call(monkeypatch):
    class Budget:
        expired = False
        should_wrap_up = True

        def mark_wrap_up(self):
            self.should_wrap_up = False

    monkeypatch.setattr("agent.run_budget.TurnRunBudget", lambda _seconds: Budget())
    agent = _make_agent("web_search")
    setattr(agent, "run_budget_seconds", 30.0)
    assert agent.client is not None
    agent.client.chat.completions.create.return_value = _mock_response(content="finished")

    with (
        patch.object(agent, "_persist_session"),
        patch.object(agent, "_save_trajectory"),
        patch.object(agent, "_cleanup_task_resources"),
    ):
        result = agent.run_conversation("complete the task")

    assert result["final_response"] == "finished"
    request = agent.client.chat.completions.create.call_args.kwargs
    sent = "\n".join(str(item.get("content", "")) for item in request["messages"])
    assert sent.count("[Clio run-budget notice:") == 1


def test_expired_budget_starts_no_model_call(monkeypatch):
    class ExpiredBudget:
        expired = True
        should_wrap_up = False

    monkeypatch.setattr("agent.run_budget.TurnRunBudget", lambda _seconds: ExpiredBudget())
    agent = _make_agent("web_search")
    setattr(agent, "run_budget_seconds", 1.0)
    assert agent.client is not None

    with (
        patch.object(agent, "_persist_session"),
        patch.object(agent, "_save_trajectory"),
        patch.object(agent, "_cleanup_task_resources"),
    ):
        result = agent.run_conversation("complete the task")

    assert result["api_calls"] == 0
    assert "wall-clock budget expired" in result["final_response"]
    agent.client.chat.completions.create.assert_not_called()


def test_cli_run_budget_flag_is_float():
    parser, _subparsers, _chat = build_top_level_parser()
    args = parser.parse_args(["chat", "--run-budget", "12.5", "-q", "hello"])
    assert args.run_budget == 12.5
