"""Notice/re-prompt-only runtime stall guard contracts."""

from agent.agent_runtime_helpers import trailing_continue_intent
from agent.tool_guardrails import (
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
