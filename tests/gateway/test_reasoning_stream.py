"""Tests for live gateway reasoning followed by a separate answer block."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from gateway.reasoning_stream import ReasoningStreamBridge
from gateway.run import _reasoning_display_allowed


class _RecordingConsumer:
    def __init__(self) -> None:
        self.events = []

    def on_delta(self, text: str) -> None:
        self.events.append(("delta", text))

    def on_segment_break(self) -> None:
        self.events.append(("break", None))


def test_reasoning_streams_before_answer_in_separate_segment() -> None:
    consumer = _RecordingConsumer()
    bridge = ReasoningStreamBridge(consumer)

    bridge.on_reasoning_delta("First thought. ")
    bridge.on_reasoning_delta("Second thought.")
    bridge.on_response_delta("Final ")
    bridge.on_response_delta("answer.")

    assert consumer.events == [
        ("delta", "💭 **Reasoning:**\n\n"),
        ("delta", "First thought. "),
        ("delta", "Second thought."),
        ("break", None),
        ("delta", "Final "),
        ("delta", "answer."),
    ]
    assert bridge.reasoning_started is True
    assert bridge.response_started is True


def test_answer_without_reasoning_keeps_normal_stream_shape() -> None:
    consumer = _RecordingConsumer()
    bridge = ReasoningStreamBridge(consumer)

    bridge.on_response_delta("Direct answer")

    assert consumer.events == [("delta", "Direct answer")]
    assert bridge.reasoning_started is False


def test_late_reasoning_cannot_leak_below_answer() -> None:
    consumer = _RecordingConsumer()
    bridge = ReasoningStreamBridge(consumer)

    bridge.on_reasoning_delta("Before")
    bridge.on_response_delta("Answer")
    bridge.on_reasoning_delta("Too late")

    assert consumer.events[-1] == ("delta", "Answer")
    assert ("delta", "Too late") not in consumer.events


def test_empty_deltas_are_ignored() -> None:
    consumer = MagicMock()
    bridge = ReasoningStreamBridge(consumer)

    bridge.on_reasoning_delta("")
    bridge.on_response_delta("")

    consumer.on_delta.assert_not_called()
    consumer.on_segment_break.assert_not_called()


def test_reasoning_display_is_hidden_in_shared_chats_but_preserved_in_dms() -> None:
    assert _reasoning_display_allowed(SimpleNamespace(chat_type="group"), True) is False
    assert _reasoning_display_allowed(SimpleNamespace(chat_type="forum"), True) is False
    assert _reasoning_display_allowed(SimpleNamespace(chat_type="dm"), True) is True
    assert _reasoning_display_allowed(SimpleNamespace(chat_type="dm"), False) is False
