"""Shared screenshot-eviction policy for outbound message histories.

Computer-use captures attach a base64 screenshot to every (now default-SOM)
tool result. Each image costs well over a thousand tokens and they accumulate
across a task — left unchecked they inflate every subsequent request, which is
exactly what drove the 27s API turns observed on the YouTube task. The model
only needs the most recent few screenshots to reason about current state; older
ones can be replaced with a placeholder.

The Anthropic adapter has its own evictor that runs on already-converted
Anthropic ``tool_result``/``image`` blocks (see
``agent.anthropic_adapter._evict_old_screenshots``). This module provides the
equivalent for the OpenAI Chat Completions format — ``role: "tool"`` messages
whose ``content`` is a list containing ``{"type": "image_url", ...}`` parts —
used by the ~16 OpenAI-compatible providers (managed portal, OpenRouter, …).
"""

from __future__ import annotations

from typing import Any, Dict, List

# Keep this in sync with anthropic_adapter._evict_old_screenshots.
MAX_KEEP_IMAGES = 3

_PLACEHOLDER = {"type": "text", "text": "[screenshot removed to save context]"}


def _has_image_part(content: Any) -> bool:
    return isinstance(content, list) and any(
        isinstance(p, dict) and p.get("type") == "image_url" for p in content
    )


def evict_openai_screenshots(
    messages: List[Dict[str, Any]], max_keep: int = MAX_KEEP_IMAGES
) -> List[Dict[str, Any]]:
    """Return a message list with all but the most recent ``max_keep``
    tool-result screenshots replaced by a text placeholder.

    Copy-on-write: the input list and any unchanged messages are returned as-is
    (so this is safe to call on the canonical history); only messages whose
    images are evicted are shallow-copied. Walks from the end so the freshest
    screenshots are the ones kept.
    """
    # Identify, from the end, which message indices carry tool-result images
    # beyond the keep window.
    strip_indices: set[int] = set()
    seen = 0
    for idx in range(len(messages) - 1, -1, -1):
        msg = messages[idx]
        if not isinstance(msg, dict) or msg.get("role") != "tool":
            continue
        if not _has_image_part(msg.get("content")):
            continue
        seen += 1
        if seen > max_keep:
            strip_indices.add(idx)

    if not strip_indices:
        return messages

    out: List[Dict[str, Any]] = []
    for idx, msg in enumerate(messages):
        if idx not in strip_indices:
            out.append(msg)
            continue
        new_msg = dict(msg)
        new_msg["content"] = [
            _PLACEHOLDER if (isinstance(p, dict) and p.get("type") == "image_url") else p
            for p in msg["content"]
        ]
        out.append(new_msg)
    return out
