"""Notice/re-prompt-only runtime stall guard contracts."""

from agent.agent_runtime_helpers import trailing_continue_intent
from agent.tool_guardrails import (
    IDENTICAL_RESULT_STUB_MIN_CHARS,
    STALL_GUARD_IDENTICAL_CALL_THRESHOLD,
    ToolCallGuardrailController,
    is_stall_guard_repeatable,
)


def _observe(controller, count, *, tool="web_search", args=None, result="same"):
    return [
        controller.observe_identical_call(tool, args or {"query": "x"}, result)
        for _ in range(count)
    ]


def test_identical_call_notice_starts_on_third_and_never_blocks():
    controller = ToolCallGuardrailController()
    notices = _observe(controller, STALL_GUARD_IDENTICAL_CALL_THRESHOLD + 1)

    assert notices[:2] == [None, None]
    assert notices[2] is not None
    assert notices[3] is not None
    assert "Clio note" in notices[2]
    assert "3rd" in notices[2]
    assert "4th" in notices[3]
    assert controller.before_call("web_search", {"query": "x"}).allows_execution


def test_identical_call_streak_resets_on_tool_args_result_and_turn():
    controller = ToolCallGuardrailController()
    assert _observe(controller, 2)[-1] is None
    assert controller.observe_identical_call("read_file", {"path": "/a"}, "same") is None
    assert _observe(controller, 2)[-1] is None
    assert controller.observe_identical_call("web_search", {"query": "x"}, "changed") is None
    assert controller.observe_identical_call("web_search", {"query": "y"}, "changed") is None
    controller.reset_for_turn()
    assert _observe(controller, 2)[-1] is None


def test_poll_and_get_result_tools_are_exempt():
    controller = ToolCallGuardrailController()
    for tool in ("process", "bfl_flux3_get_result", "vendor_get_result", "job_poll"):
        assert is_stall_guard_repeatable(tool)
        assert all(
            notice is None
            for notice in _observe(
                controller,
                STALL_GUARD_IDENTICAL_CALL_THRESHOLD + 2,
                tool=tool,
                args={"id": "job-1"},
                result="pending",
            )
        )


def test_raw_result_identity_survives_existing_warning_suffixes():
    controller = ToolCallGuardrailController()
    args = {"path": "/tmp/x"}
    notice = None
    for index in range(3):
        raw = "contents"
        notice = controller.observe_identical_call("read_file", args, raw)
        controller.after_call("read_file", args, raw, failed=False)
        if index < 2:
            assert notice is None
    assert notice is not None
    assert "Clio note" in notice


# ── result-reference stubbing ─────────────────────────────────────────────


def test_second_large_byte_identical_result_becomes_reference_stub():
    controller = ToolCallGuardrailController()
    result = "x" * IDENTICAL_RESULT_STUB_MIN_CHARS
    args = {"query": "runtime tools"}

    first = controller.observe_call(
        "web_search", args, result, tool_call_id="call-1"
    )
    second = controller.observe_call(
        "web_search", args, result, tool_call_id="call-2"
    )

    assert first.stub is None
    assert second.stub is not None
    assert "byte-identical" in second.stub
    assert "tool_call_id call-1" in second.stub
    assert "runtime tools" in second.stub
    assert len(second.stub) < len(result)


def test_changed_errors_small_and_multimodal_results_are_not_stubbed():
    controller = ToolCallGuardrailController()
    large = "x" * IDENTICAL_RESULT_STUB_MIN_CHARS
    args = {"id": "job-1"}

    assert controller.observe_call("process", args, large).stub is None
    assert controller.observe_call("process", args, "y" + large).stub is None

    controller.reset_for_turn()
    assert controller.observe_call("process", args, large, failed=True).stub is None
    assert controller.observe_call("process", args, large, failed=True).stub is None

    controller.reset_for_turn()
    small = "z" * (IDENTICAL_RESULT_STUB_MIN_CHARS - 1)
    assert controller.observe_call("process", args, small).stub is None
    assert controller.observe_call("process", args, small).stub is None

    controller.reset_for_turn()
    assert controller.observe_call("process", args, large).stub is None
    assert controller.observe_call("process", args, [{"type": "image"}]).stub is None
    assert controller.observe_call("process", args, large).stub is None


def test_repeatable_pollers_stub_unchanged_payload_without_loop_notice():
    controller = ToolCallGuardrailController()
    result = "pending\n" * IDENTICAL_RESULT_STUB_MIN_CHARS
    observations = [
        controller.observe_call(
            "job_poll", {"id": "job-1"}, result, tool_call_id=f"call-{index}"
        )
        for index in range(4)
    ]

    assert observations[0].stub is None
    assert all(item.stub is not None for item in observations[1:])
    assert all(item.notice is None for item in observations)


def test_result_stub_carries_persisted_path_and_parser_round_trips():
    from tools.tool_result_storage import (
        _build_persisted_message,
        extract_persisted_path,
    )

    path = "/tmp/clio-spill/call-1.txt"
    persisted = _build_persisted_message("preview", True, 50_000, path)
    assert extract_persisted_path(persisted) == path
    assert extract_persisted_path("ordinary result") is None

    controller = ToolCallGuardrailController()
    controller.record_persisted_result("call-1", path)
    result = "x" * IDENTICAL_RESULT_STUB_MIN_CHARS
    controller.observe_call("web_search", {"q": "x"}, result, tool_call_id="call-1")
    stub = controller.observe_call(
        "web_search", {"q": "x"}, result, tool_call_id="call-2"
    ).stub
    assert stub is not None
    assert path in stub


def test_trailing_continue_intent_is_narrow_and_tail_anchored():
    assert trailing_continue_intent("Found the config. Let me now update it.")
    assert trailing_continue_intent("Tests pass. I'll now run the linter")
    assert trailing_continue_intent("Step one is done. Next: I check the logs")
    assert not trailing_continue_intent(
        "I will now explain the tradeoffs. First, caching is stable. Second, roles alternate."
    )
    assert not trailing_continue_intent(("Full analysis. " * 40) + "Let me now summarize.")
    assert not trailing_continue_intent("All tests pass and the branch is ready.")
    assert not trailing_continue_intent(None)
