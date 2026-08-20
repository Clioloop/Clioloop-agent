"""Focused regressions for anti-growth compression and overflow feedback."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from agent.context_compressor import (
    COMPRESSED_SUMMARY_METADATA_KEY,
    SUMMARY_PREFIX,
    ContextCompressor,
    salvage_grown_transcript,
)
from agent.conversation_compression import compress_context
from agent.conversation_loop import _guard_uncompressed_context_overflow
from agent.manual_compression_feedback import summarize_manual_compression


def test_salvage_caps_only_marked_summaries_and_prunes_stale_sidecars():
    original = [{"role": "user", "content": "o" * 50_000}]
    quoted_live_turn = SUMMARY_PREFIX + " quoted by the user " + "q" * 9_000
    candidate = [
        {
            "role": "user",
            "content": SUMMARY_PREFIX + "s" * 10_000,
            COMPRESSED_SUMMARY_METADATA_KEY: True,
        },
        {"role": "assistant", "content": "old", "reasoning": "r" * 5_000},
        {"role": "tool", "tool_call_id": "old", "content": "x" * 1_000},
        {"role": "tool", "tool_call_id": "new-1", "content": "y" * 1_000},
        {"role": "tool", "tool_call_id": "new-2", "content": "z" * 1_000},
        {"role": "user", "content": quoted_live_turn},
        {"role": "assistant", "content": "new", "reasoning": "keep me"},
    ]

    salvaged = salvage_grown_transcript(original, candidate)

    assert salvaged is not None
    assert "summary truncated so compression can shrink" in salvaged[0]["content"]
    assert "END OF CONTEXT SUMMARY" in salvaged[0]["content"]
    assert "reasoning" not in salvaged[1]
    assert salvaged[2]["content"] == (
        "[Old tool output cleared to save context space]"
    )
    assert salvaged[3]["content"] == "y" * 1_000
    assert salvaged[4]["content"] == "z" * 1_000
    assert salvaged[5]["content"] == quoted_live_turn
    assert salvaged[6]["reasoning"] == "keep me"
    assert candidate[1]["reasoning"].startswith("r")  # input was copied


def test_salvage_drops_synthetic_todo_only_as_last_resort():
    original = [{"role": "user", "content": "o" * 2_000}]
    candidate = [
        {"role": "user", "content": "c" * 1_800},
        {
            "role": "user",
            "content": "todo" * 300,
            "_todo_snapshot_synthetic": True,
        },
    ]

    salvaged = salvage_grown_transcript(original, candidate)

    assert salvaged == [{"role": "user", "content": "c" * 1_800}]


def test_builtin_compressor_refuses_oversized_generated_summary_and_rolls_back():
    with patch(
        "agent.context_compressor.get_model_context_length", return_value=100_000
    ):
        compressor = ContextCompressor(
            model="test/model",
            protect_first_n=1,
            protect_last_n=1,
            quiet_mode=True,
        )
    messages = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"}
        for i in range(6)
    ]

    with (
        patch.object(compressor, "_find_tail_cut_by_tokens", return_value=5),
        patch.object(
            compressor,
            "_generate_summary",
            return_value=SUMMARY_PREFIX + " huge" * 10_000,
        ),
    ):
        result = compressor.compress(messages, current_tokens=1_000)

    assert result is messages
    assert compressor._last_compress_refused_would_grow is True
    assert compressor.compression_count == 0
    assert compressor._previous_summary is None
    assert compressor._ineffective_compression_count == 1


class _GrowingEngine:
    compression_count = 0
    _last_compress_aborted = False
    _last_compress_refused_would_grow = False
    _last_summary_error = None
    _last_aux_model_failure_model = None
    _last_aux_model_failure_error = None

    def __init__(self):
        self.rejections = []

    def compress(self, messages, **_kwargs):
        return [{"role": "user", "content": "larger" * 10_000}]

    def record_rejected_compaction(self, *, rollback_candidate=False):
        self.rejections.append(rollback_candidate)


def test_commit_boundary_refuses_growing_plugin_candidate_without_rotation():
    engine = _GrowingEngine()
    agent = SimpleNamespace(
        _compression_feasibility_checked=True,
        session_id="session-a",
        model="test/model",
        _emit_status=MagicMock(),
        _emit_warning=MagicMock(),
        _session_db=None,
        _memory_manager=None,
        context_compressor=engine,
        _todo_store=SimpleNamespace(format_for_injection=lambda: ""),
        _cached_system_prompt="cached prompt",
        _build_system_prompt=MagicMock(return_value="rebuilt prompt"),
    )
    messages = [{"role": "user", "content": "small"}]

    result, system_prompt = compress_context(agent, messages, "system")

    assert result is messages
    assert system_prompt == "cached prompt"
    assert agent.session_id == "session-a"
    assert engine._last_compress_refused_would_grow is True
    assert engine.rejections == [True]
    assert "would have grown" in agent._emit_warning.call_args.args[0]
    agent._build_system_prompt.assert_not_called()


def test_overflow_warning_deduplicates_and_rearms_after_request_fits():
    agent = SimpleNamespace(
        compression_enabled=False,
        context_compressor=SimpleNamespace(context_length=1_000),
        session_id="session-a",
        _emit_warning=MagicMock(),
    )

    assert _guard_uncompressed_context_overflow(agent, 1_001) is True
    assert _guard_uncompressed_context_overflow(agent, 2_000) is False
    assert agent._emit_warning.call_count == 1
    assert "compression.enabled: false" in agent._emit_warning.call_args.args[0]
    assert _guard_uncompressed_context_overflow(agent, 1_000) is False
    assert _guard_uncompressed_context_overflow(agent, 1_001) is True
    assert agent._emit_warning.call_count == 2


def test_manual_feedback_distinguishes_refusal_abort_and_redacted_fallback():
    before = [{"role": "user", "content": "one"}]

    refused = summarize_manual_compression(
        before,
        before,
        100,
        100,
        compression_state=SimpleNamespace(
            _last_compress_refused_would_grow=True,
            _last_compress_aborted=False,
            _last_summary_fallback_used=False,
        ),
    )
    aborted = summarize_manual_compression(
        before,
        before,
        100,
        100,
        compression_state=SimpleNamespace(
            _last_compress_refused_would_grow=False,
            _last_compress_aborted=True,
            _last_summary_fallback_used=False,
            _last_summary_error="Authorization: Bearer sk-test-secret-token",
        ),
    )
    fallback = summarize_manual_compression(
        before * 3,
        before,
        300,
        120,
        compression_state=SimpleNamespace(
            _last_compress_refused_would_grow=False,
            _last_compress_aborted=False,
            _last_summary_fallback_used=True,
            _last_summary_dropped_count=2,
            _last_summary_error="provider unavailable",
        ),
    )

    assert refused["refused_would_grow"] is True
    assert "would grow" in refused["headline"]
    assert aborted["aborted"] is True
    assert "sk-test-secret-token" not in aborted["note"]
    assert fallback["fallback_used"] is True
    assert "removed 2 message(s)" in fallback["note"]