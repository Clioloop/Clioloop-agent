"""Focused compatibility tests for durable delegation."""
from __future__ import annotations

import json
import queue
from types import SimpleNamespace
from unittest.mock import MagicMock

from clio_state import SessionDB
from tools import async_delegation
from tools.delegate_tool import DELEGATE_TASK_SCHEMA, _run_single_child, delegate_task
from tools.delegation_output_schema import validate_output


def _parent(db=None):
    return SimpleNamespace(
        session_id="session-1",
        _session_db=db,
        _delegate_depth=0,
        _active_children=[],
        _active_children_lock=__import__("threading").Lock(),
        platform="cli",
        providers_allowed=None,
        providers_ignored=None,
        providers_order=None,
        provider_sort=None,
        base_url="https://example.invalid",
        api_key="test",
        provider="openrouter",
        api_mode="chat_completions",
        model="test-model",
        _print_fn=None,
        tool_progress_callback=None,
        thinking_callback=None,
    )


def test_action_and_output_contract_schema():
    props = DELEGATE_TASK_SCHEMA["parameters"]["properties"]
    assert props["action"]["enum"] == ["spawn", "list", "status", "steer", "stop"]
    assert props["background"]["type"] == "boolean"
    assert props["output_schema"]["type"] == "object"
    assert props["tasks"]["items"]["properties"]["output_schema"]["type"] == "object"


def test_dispatch_persists_result_and_claims_exactly_once(tmp_path, monkeypatch):
    db = SessionDB(tmp_path / "state.db")
    monkeypatch.setattr(async_delegation, "get_clio_home", lambda: tmp_path)
    events = queue.Queue()
    from tools.process_registry import process_registry
    monkeypatch.setattr(process_registry, "completion_queue", events)

    response = async_delegation.dispatch(
        tasks=[{"goal": "persist me"}],
        runner=lambda: json.dumps({
            "results": [{
                "task_index": 0, "status": "completed", "summary": "done",
                "tokens": {"input": 2, "output": 3, "reasoning": 1},
                "cost_usd": 0.25,
            }]
        }),
        parent_agent=_parent(db),
        max_workers=1,
    )
    assert response["status"] == "dispatched"
    event = events.get(timeout=3)
    row = db.get_async_delegation(response["delegation_id"])
    assert row is not None
    assert row["state"] == "completed"
    assert row["result"]["results"][0]["summary"] == "done"
    assert event["tokens"] == {"input": 2, "output": 3, "reasoning": 1}
    assert event["cost_usd"] == 0.25
    claim = async_delegation.claim_event_delivery(event, "test", db=db)
    assert claim
    assert async_delegation.claim_event_delivery(event, "other", db=db) is None
    assert async_delegation.complete_event_delivery(event, claim, db=db)
    delivered = db.get_async_delegation(response["delegation_id"])
    assert delivered is not None
    assert delivered["delivery_state"] == "delivered"
    db.close()


def test_structured_output_retries_once_and_returns_parsed_value(monkeypatch):
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "integer"}},
        "required": ["answer"],
        "additionalProperties": False,
    }
    child = MagicMock()
    child._delegate_output_schema = schema
    child._delegate_subagent_id = "subagent-test"
    child._delegate_role = "leaf"
    child._delegate_transcript_path = None
    child._delegate_worktree_path = None
    child.model = "test-model"
    child.session_prompt_tokens = 1
    child.session_completion_tokens = 2
    child.session_reasoning_tokens = 0
    child.messages = []
    child.run_conversation.side_effect = [
        {"final_response": '{"answer":"bad"}', "completed": True, "api_calls": 1},
        {"final_response": '{"answer":42}', "completed": True, "api_calls": 1},
    ]
    parent = _parent()
    result = _run_single_child(0, "answer", child, parent)
    assert result["schema_valid"] is True
    assert result["schema_retries"] == 1
    assert result["structured_output"] == {"answer": 42}
    assert child.run_conversation.call_count == 2
    assert "failed the OUTPUT CONTRACT" in child.run_conversation.call_args_list[1].kwargs["user_message"]
    assert validate_output('{"answer":42}', schema)[0] is True


def test_background_acp_arguments_reuse_synchronous_path(monkeypatch):
    captured = {}

    def fake_dispatch(**kwargs):
        captured["runner"] = kwargs["runner"]
        return {"status": "dispatched", "delegation_id": "deleg_test", "count": 1}

    child = MagicMock()
    monkeypatch.setattr("tools.async_delegation.dispatch", fake_dispatch)
    def fake_build(**kwargs):
        captured["build"] = kwargs
        return child

    monkeypatch.setattr("tools.delegate_tool._build_child_agent", fake_build)
    monkeypatch.setattr("tools.delegate_tool._run_single_child", lambda *args, **kwargs: {
        "task_index": 0, "status": "completed", "summary": "ok", "api_calls": 1,
        "duration_seconds": 0.1,
    })
    dispatched = json.loads(delegate_task(
        goal="ACP task", background=True, acp_command="copilot",
        acp_args=["--acp", "--stdio"], parent_agent=_parent(),
    ))
    assert dispatched["status"] == "dispatched"
    sync = json.loads(captured["runner"]())
    assert sync["results"][0]["summary"] == "ok"
    assert captured["build"]["override_acp_command"] == "copilot"
    assert captured["build"]["override_acp_args"] == ["--acp", "--stdio"]


def test_legacy_synchronous_call_stays_blocking_and_result_shaped(monkeypatch):
    child = MagicMock()
    build = MagicMock(return_value=child)
    monkeypatch.setattr("tools.delegate_tool._build_child_agent", build)
    monkeypatch.setattr("tools.delegate_tool._run_single_child", lambda *args, **kwargs: {
        "task_index": 0, "status": "completed", "summary": "legacy", "api_calls": 1,
        "duration_seconds": 0.1,
    })
    dispatch = MagicMock()
    monkeypatch.setattr("tools.async_delegation.dispatch", dispatch)
    result = json.loads(delegate_task(goal="old call", parent_agent=_parent()))
    assert result["results"][0]["summary"] == "legacy"
    assert "delegation_id" not in result
    dispatch.assert_not_called()
    assert build.call_args.kwargs["override_acp_command"] is None
    assert build.call_args.kwargs["output_schema"] is None
