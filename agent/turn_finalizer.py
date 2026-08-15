"""Small, dependency-light turn-finalization invariants.

The conversation loop still owns provider/plugin side effects.  This module
owns the reusable correctness seams: closing a delivered turn with an assistant
row and assembling one canonical result/usage envelope.
"""

from __future__ import annotations

from typing import Any, MutableSequence


_USAGE_ATTRS = {
    "input_tokens": "session_input_tokens",
    "output_tokens": "session_output_tokens",
    "cache_read_tokens": "session_cache_read_tokens",
    "cache_write_tokens": "session_cache_write_tokens",
    "reasoning_tokens": "session_reasoning_tokens",
    "prompt_tokens": "session_prompt_tokens",
    "completion_tokens": "session_completion_tokens",
    "total_tokens": "session_total_tokens",
    "estimated_cost_usd": "session_estimated_cost_usd",
    "cost_status": "session_cost_status",
    "cost_source": "session_cost_source",
}


def ensure_assistant_tail(
    messages: MutableSequence[dict[str, Any]],
    final_response: Any,
    *,
    interrupted: bool = False,
) -> bool:
    """Enforce ``delivered response => assistant transcript tail``.

    Returns true when the transcript was changed.  Interrupted turns are left
    to the existing interrupted-tool-sequence closer because an interrupt does
    not imply that ``final_response`` was delivered as a completed answer.
    """
    if interrupted or not isinstance(final_response, str) or not final_response:
        return False
    tail = messages[-1] if messages else None
    if not isinstance(tail, dict) or tail.get("role") != "assistant":
        messages.append({"role": "assistant", "content": final_response})
        return True
    if tail.get("content") != final_response:
        tail["content"] = final_response
        # Incremental persistence may have already flushed the provider row.
        # This also covers post-loop footer/plugin transforms of an ordinary
        # text assistant message, not only a pure tool-call tail.
        tail.pop("_db_persisted", None)
        return True
    return False


def collect_turn_usage(agent: Any) -> dict[str, Any]:
    """Collect the canonical, non-overlapping session usage fields unchanged."""
    usage = {
        result_key: getattr(agent, attr_name, 0)
        for result_key, attr_name in _USAGE_ATTRS.items()
    }
    compressor = getattr(agent, "context_compressor", None)
    usage["last_prompt_tokens"] = (
        getattr(compressor, "last_prompt_tokens", 0) or 0
    )
    return usage


def last_reasoning_for_turn(messages: list[dict[str, Any]]) -> Any:
    """Return newest reasoning without crossing the current user boundary."""
    for message in reversed(messages):
        if not isinstance(message, dict):
            continue
        if message.get("role") == "user":
            break
        if message.get("role") == "assistant" and message.get("reasoning"):
            return message["reasoning"]
    return None


def build_turn_result(
    agent: Any,
    *,
    final_response: Any,
    messages: list[dict[str, Any]],
    api_call_count: int,
    completed: bool,
    turn_exit_reason: str,
    failed: bool,
    interrupted: bool,
    response_transformed: bool = False,
) -> dict[str, Any]:
    """Build the canonical turn result while preserving role and usage fields."""
    result = {
        "final_response": final_response,
        "last_reasoning": last_reasoning_for_turn(messages),
        "messages": messages,
        "api_calls": api_call_count,
        "completed": completed,
        "turn_exit_reason": turn_exit_reason,
        "failed": failed,
        "partial": False,
        "interrupted": interrupted,
        "response_transformed": response_transformed,
        "response_previewed": getattr(agent, "_response_was_previewed", False),
        "model": getattr(agent, "model", None),
        "provider": getattr(agent, "provider", None),
        "base_url": getattr(agent, "base_url", None),
        **collect_turn_usage(agent),
        "session_id": getattr(agent, "session_id", None),
    }
    return result


__all__ = [
    "ensure_assistant_tail",
    "collect_turn_usage",
    "last_reasoning_for_turn",
    "build_turn_result",
]
