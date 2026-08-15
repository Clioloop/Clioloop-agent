from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest

from agent.context_compressor import ContextCompressor
from agent.native_compaction import native_compaction_context_management
from agent.prompt_cache_boundary import (
    clear_stable_prefixes,
    find_stable_prefix,
    register_stable_prefix,
)
from agent.prompt_cache_scope import resolve_prompt_cache_scope
from agent.prompt_caching import apply_anthropic_cache_control


@pytest.fixture(autouse=True)
def _cache_registry():
    clear_stable_prefixes()
    yield
    clear_stable_prefixes()


def test_cache_boundary_prefers_longest_proper_prefix_and_does_not_mutate():
    register_stable_prefix("stable ")
    register_stable_prefix("stable scaffold ")
    source = [{"role": "user", "content": "stable scaffold volatile"}]
    before = copy.deepcopy(source)

    wire = apply_anthropic_cache_control(source)

    assert source == before
    assert wire[0]["content"][0]["text"] == "stable scaffold "
    assert wire[0]["content"][1] == {"type": "text", "text": "volatile"}
    assert find_stable_prefix("stable scaffold ") == "stable "


def test_cache_scope_survives_rotation_and_is_memoized():
    class DB:
        calls = 0

        def get_compression_lineage(self, session_id):
            self.calls += 1
            return ["root", session_id]

    db = DB()
    agent = SimpleNamespace(session_id="rotated", _session_db=db)
    assert resolve_prompt_cache_scope(agent) == "root"
    assert resolve_prompt_cache_scope(agent) == "root"
    assert db.calls == 1


def test_native_compaction_is_strictly_feature_and_route_gated():
    base = dict(
        model="gpt-5.6",
        base_url="https://api.openai.com/v1",
        compression_enabled=True,
        codex_responses_compact_threshold=200_000,
        context_compressor=SimpleNamespace(threshold_tokens=100_000),
    )
    disabled = SimpleNamespace(**base, codex_responses_native_compaction=False)
    assert native_compaction_context_management(disabled, is_codex_backend=False) is None

    enabled = SimpleNamespace(**base, codex_responses_native_compaction=True)
    payload = native_compaction_context_management(enabled, is_codex_backend=False)
    assert payload == [{"type": "compaction", "compact_threshold": 91_808}]

    enabled.model = "gpt-5.2"
    assert native_compaction_context_management(enabled, is_codex_backend=False) is None
    enabled.model = "gpt-5.6"
    enabled.base_url = "https://api.openai.com.evil.test/v1"
    assert native_compaction_context_management(enabled, is_codex_backend=False) is None


def _compressor() -> ContextCompressor:
    compressor = ContextCompressor(
        model="test",
        config_context_length=40_000,
        protect_first_n=0,
        protect_last_n=2,
        quiet_mode=True,
    )
    compressor._micro_compact_enabled = True
    return compressor


def _tool_history():
    return [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "old ask"},
        {
            "role": "assistant",
            "content": "calling",
            "tool_calls": [
                {"id": "call-1", "type": "function", "function": {"name": "read", "arguments": "{}"}}
            ],
        },
        {"role": "tool", "tool_call_id": "call-1", "content": "result"},
        {"role": "assistant", "content": "done"},
        {"role": "user", "content": "new ask"},
        {"role": "assistant", "content": "new answer"},
    ]


def test_micro_compaction_dry_run_has_no_mutation_or_state_change():
    compressor = _compressor()
    compressor._micro_summarize_one = lambda span: "summary"
    messages = _tool_history()
    before = copy.deepcopy(messages)

    preview = compressor._micro_compact(messages, dry_run=True)

    assert messages == before
    assert compressor._micro_compact_cursor == 0
    assert len(preview) < len(messages)


def test_micro_compaction_preserves_tool_call_pairs_atomically():
    compressor = _compressor()
    seen = []
    compressor._micro_summarize_one = lambda span: seen.extend(span) or "summary"

    result = compressor._micro_compact(_tool_history())

    # The complete old call/result chain was summarized together, never split.
    assert {message.get("role") for message in seen} == {"assistant", "tool"}
    surviving_calls = {
        call["id"]
        for message in result
        for call in (message.get("tool_calls") or [])
    }
    surviving_results = {
        message["tool_call_id"] for message in result if message.get("role") == "tool"
    }
    assert surviving_calls == surviving_results
    assert any(message.get("_micro_compact_marker") for message in result)
    assert any(message.get("content") == "old ask" for message in result)


def test_micro_compaction_failure_rolls_back_messages_and_cursor():
    compressor = _compressor()

    def fail(_span):
        raise RuntimeError("summarizer unavailable")

    compressor._micro_summarize_one = fail
    messages = _tool_history()
    before = copy.deepcopy(messages)

    assert compressor._micro_compact(messages) == before
    assert messages == before
    assert compressor._micro_compact_cursor == 0


def test_incomplete_tool_pair_is_not_compacted():
    compressor = _compressor()
    compressor._micro_summarize_one = lambda span: "must not run"
    messages = _tool_history()
    messages.pop(3)  # remove call-1's result
    before = copy.deepcopy(messages)

    assert compressor._micro_compact(messages) == before
