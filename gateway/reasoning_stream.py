"""Bridge model reasoning deltas into the gateway's message stream.

The agent exposes reasoning and visible assistant text through separate callbacks.
This bridge serializes both onto one ``GatewayStreamConsumer`` queue so reasoning
is rendered live first, then the visible answer starts in a fresh message.
"""

from __future__ import annotations

from typing import Any


class ReasoningStreamBridge:
    """Stream reasoning first and split the visible answer into a new message."""

    _HEADER = "💭 **Reasoning:**\n\n"

    def __init__(self, consumer: Any) -> None:
        self.consumer = consumer
        self.reasoning_started = False
        self.response_started = False

    def on_reasoning_delta(self, text: str) -> None:
        """Queue a reasoning delta, adding the heading on the first delta."""
        if not text or self.response_started:
            return
        if not self.reasoning_started:
            self.reasoning_started = True
            self.consumer.on_delta(self._HEADER)
        self.consumer.on_delta(text)

    def on_response_delta(self, text: str) -> None:
        """Queue visible text, starting a fresh message after reasoning."""
        if not text:
            return
        if self.reasoning_started and not self.response_started:
            self.consumer.on_segment_break()
        self.response_started = True
        self.consumer.on_delta(text)


__all__ = ["ReasoningStreamBridge"]
