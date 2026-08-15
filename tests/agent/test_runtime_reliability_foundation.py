"""Focused contracts for the runtime reliability foundation."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from concurrent.futures.thread import _threads_queues
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import httpx
import pytest

from agent import estop
from agent.bounded_response import read_streaming_error_body
from agent.deadline import (
    MAX_SAFE_TIMEOUT_S,
    DeadlineExpired,
    clamp_timeout,
    resolve_timeout,
    run_bounded_async,
    run_bounded_sync,
)
from agent.turn_finalizer import (
    build_turn_result,
    ensure_assistant_tail,
    last_reasoning_for_turn,
)
from agent.turn_retry_state import TurnRetryState
from agent.verification_evidence import (
    classify_verification_command,
    record_terminal_result,
)
from agent.verify.recipes import detect_recipe
from tools.daemon_pool import DaemonThreadPoolExecutor


def test_timeout_resolution_precedence_and_clamp(monkeypatch):
    monkeypatch.setattr(
        "agent.deadline._timeouts_section", lambda: {"tools": {"batch": 9}}
    )
    monkeypatch.setenv("CLIO_TEST_TIMEOUT", "4")
    assert resolve_timeout("tools.batch", default=2, env_var="CLIO_TEST_TIMEOUT") == 9

    monkeypatch.setattr("agent.deadline._timeouts_section", lambda: {})
    assert resolve_timeout("tools.batch", default=2, env_var="CLIO_TEST_TIMEOUT") == 4
    assert clamp_timeout(10**20) == MAX_SAFE_TIMEOUT_S
    assert clamp_timeout(0) is None
    assert clamp_timeout(float("nan")) is None


def test_bounded_sync_times_out_without_joining_worker():
    release = threading.Event()
    start = time.monotonic()
    result = run_bounded_sync(lambda: release.wait(30), 0.03, label="wedged")
    elapsed = time.monotonic() - start
    try:
        assert result.timed_out is True
        assert elapsed < 1
        with pytest.raises(DeadlineExpired, match="wedged"):
            result.raise_if_timed_out()
    finally:
        release.set()


def test_bounded_async_returns_completion_and_timeout():
    async def scenario():
        complete = await run_bounded_async(asyncio.sleep(0, result="ok"), 1)
        timeout = await run_bounded_async(asyncio.sleep(30), 0.02, label="slow")
        await asyncio.sleep(0)
        return complete, timeout

    complete, timeout = asyncio.run(scenario())
    assert complete.value == "ok" and not complete.timed_out
    assert timeout.timed_out and timeout.value is None


class _StreamingResponse:
    def __init__(self, chunks, *, stall=False):
        self._chunks = chunks
        self._stall = stall
        self.closed = False
        self._release = threading.Event()

    def iter_bytes(self):
        yield from self._chunks
        if self._stall:
            self._release.wait(30)

    def close(self):
        self.closed = True
        self._release.set()


def test_error_body_is_byte_capped_and_closed():
    response = _StreamingResponse([b"abcdef", b"ghij"])
    assert read_streaming_error_body(
        cast(httpx.Response, response), max_bytes=7, timeout_s=1
    ) == "abcdefg"
    assert response.closed


def test_error_body_stall_returns_partial_by_deadline():
    response = _StreamingResponse([b"partial"], stall=True)
    start = time.monotonic()
    assert read_streaming_error_body(
        cast(httpx.Response, response), timeout_s=0.03
    ) == "partial"
    assert time.monotonic() - start < 1
    assert response.closed


def test_gemini_error_builder_accepts_bounded_body_text():
    from agent.gemini_native_adapter import gemini_http_error

    response = httpx.Response(429, headers={"Retry-After": "3"})
    error = gemini_http_error(
        response,
        body_text=json.dumps(
            {"error": {"status": "RESOURCE_EXHAUSTED", "message": "quota"}}
        ),
    )
    assert error.status_code == 429
    assert "quota" in str(error)


def test_estop_is_atomic_resumable_and_corrupt_sentinel_fails_safe(tmp_path, monkeypatch):
    path = tmp_path / "ESTOP"
    monkeypatch.setattr(estop, "sentinel_path", lambda: path)
    estop._reset_log_state_for_tests()

    assert estop.get_state() is None
    estop.engage("maintenance")
    assert estop.is_engaged()
    state = estop.get_state()
    assert state is not None and state["reason"] == "maintenance"
    assert "maintenance" in (estop.paused_reply() or "")
    assert estop.disengage() is True
    assert estop.disengage() is False

    path.write_text("not-json", encoding="utf-8")
    assert estop.is_engaged()
    assert estop.get_state() == {"reason": None, "engaged_at": None}


def test_estop_dispatch_gate_logs_once(tmp_path, monkeypatch, caplog):
    path = tmp_path / "ESTOP"
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(estop, "sentinel_path", lambda: path)
    estop._reset_log_state_for_tests()
    logger = logging.getLogger("test.runtime.estop")
    with caplog.at_level(logging.INFO, logger=logger.name):
        assert estop.check_paused("cron", logger)
        assert estop.check_paused("cron", logger)
    assert sum("paused" in row.getMessage() for row in caplog.records) == 1


def test_retry_state_claim_is_bounded_and_respects_direct_assignment():
    retry = TurnRetryState()
    assert retry.claim("codex_auth_retry_attempted") is True
    assert retry.claim("codex_auth_retry_attempted") is False
    assert retry.attempts_for("codex_auth_retry_attempted") == 1

    retry.has_retried_429 = True
    assert retry.claim("has_retried_429") is False
    with pytest.raises(KeyError):
        retry.claim("does_not_exist")


def _agent_stub():
    values = {
        "model": "m",
        "provider": "p",
        "base_url": "u",
        "session_id": "s",
        "_response_was_previewed": True,
        "context_compressor": SimpleNamespace(last_prompt_tokens=13),
    }
    for name in (
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
        "reasoning_tokens",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "estimated_cost_usd",
    ):
        values[f"session_{name}"] = 7
    values["session_cost_status"] = "known"
    values["session_cost_source"] = "provider"
    return SimpleNamespace(**values)


def test_finalizer_closes_tool_tail_and_builds_canonical_result():
    messages = [
        {"role": "user", "content": "old"},
        {"role": "assistant", "reasoning": "old reasoning", "content": "old"},
        {"role": "user", "content": "new"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "1"}],
            "reasoning": "current reasoning",
            "_db_persisted": True,
        },
    ]
    assert ensure_assistant_tail(messages, "delivered") is True
    assert messages[-1]["content"] == "delivered"
    assert "_db_persisted" not in messages[-1]
    assert last_reasoning_for_turn(messages) == "current reasoning"

    result = build_turn_result(
        _agent_stub(),
        final_response="delivered",
        messages=messages,
        api_call_count=2,
        completed=True,
        turn_exit_reason="text_response",
        failed=False,
        interrupted=False,
    )
    assert result["input_tokens"] == 7
    assert result["last_prompt_tokens"] == 13
    assert result["last_reasoning"] == "current reasoning"
    assert result["response_previewed"] is True


def test_finalizer_does_not_rewrite_interrupted_turn():
    messages = [{"role": "tool", "content": "partial"}]
    assert not ensure_assistant_tail(messages, "not delivered", interrupted=True)
    assert messages[-1]["role"] == "tool"


def test_finalizer_persists_transformed_ordinary_assistant_tail():
    messages = [
        {"role": "user", "content": "question"},
        {"role": "assistant", "content": "raw", "_db_persisted": True},
    ]
    assert ensure_assistant_tail(messages, "transformed")
    assert messages[-1] == {"role": "assistant", "content": "transformed"}


def test_recipe_detection_and_evidence_scope(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    recipe = detect_recipe(tmp_path)
    assert recipe is not None and recipe.test == ("pytest",)

    evidence = classify_verification_command(
        "pytest -q tests/test_api.py", cwd=tmp_path, session_id="turn-1", exit_code=1
    )
    assert evidence is not None
    assert evidence.canonical_command == "pytest"
    assert evidence.scope == "targeted"
    assert evidence.status == "failed"


def test_verification_evidence_persists_bounded_output(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (root / "tests").mkdir()
    db = tmp_path / "evidence.db"
    monkeypatch.setattr("agent.verification_evidence._db_path", lambda: db)

    event = record_terminal_result(
        command="pytest",
        cwd=root,
        session_id="s",
        exit_code=0,
        output="x" * 5000,
    )
    assert event is not None and event["id"] > 0
    assert event["status"] == "passed"
    assert "output omitted" in event["output_summary"]
    assert db.exists()


def test_daemon_pool_workers_are_reused_and_not_atexit_registered():
    pool = DaemonThreadPoolExecutor(max_workers=2)
    try:
        first = pool.submit(
            lambda: (threading.get_ident(), threading.current_thread())
        ).result(timeout=2)
        time.sleep(0.02)
        second = pool.submit(threading.get_ident).result(timeout=2)
        assert first[0] == second
        assert first[1].daemon is True
        assert first[1] not in _threads_queues
    finally:
        pool.shutdown(wait=True)


def test_tool_executor_timeout_resolver_preserves_unbounded_default(monkeypatch):
    from agent.tool_executor import _resolve_concurrent_tool_timeout

    monkeypatch.setattr("agent.deadline._timeouts_section", lambda: {})
    monkeypatch.delenv("CLIO_CONCURRENT_TOOL_TIMEOUT_S", raising=False)
    assert _resolve_concurrent_tool_timeout() is None
    monkeypatch.setenv("CLIO_CONCURRENT_TOOL_TIMEOUT_S", "0.5")
    assert _resolve_concurrent_tool_timeout() == 0.5
