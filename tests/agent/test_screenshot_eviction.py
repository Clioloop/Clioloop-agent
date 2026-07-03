"""Tests for OpenAI-format computer-use screenshot eviction.

Parallels agent.anthropic_adapter._evict_old_screenshots but for the
chat_completions transport (role:"tool" messages with image_url parts).
"""

from __future__ import annotations

from agent.screenshot_eviction import evict_openai_screenshots


def _img_tool_msg(tag: str) -> dict:
    return {
        "role": "tool",
        "tool_call_id": tag,
        "content": [
            {"type": "text", "text": f"capture {tag}"},
            {"type": "image_url",
             "image_url": {"url": f"data:image/png;base64,IMG_{tag}"}},
        ],
    }


def _has_image(msg: dict) -> bool:
    return any(
        isinstance(p, dict) and p.get("type") == "image_url"
        for p in msg.get("content", [])
    )


def test_keeps_most_recent_n_and_strips_older():
    msgs = [{"role": "user", "content": "go"}]
    msgs += [_img_tool_msg(str(i)) for i in range(6)]

    out = evict_openai_screenshots(msgs, max_keep=3)

    tool_msgs = [m for m in out if m.get("role") == "tool"]
    kept = [m for m in tool_msgs if _has_image(m)]
    # Only the last 3 screenshots survive.
    assert len(kept) == 3
    assert _has_image(out[-1]) and _has_image(out[-2]) and _has_image(out[-3])
    # The oldest were replaced with a text placeholder.
    assert not _has_image(out[1])
    assert any(
        p.get("text") == "[screenshot removed to save context]"
        for p in out[1]["content"]
    )


def test_noop_when_under_limit_returns_same_list():
    msgs = [_img_tool_msg("a"), _img_tool_msg("b")]
    out = evict_openai_screenshots(msgs, max_keep=3)
    # Unchanged → same object (copy-on-write only touches stripped messages).
    assert out is msgs


def test_does_not_mutate_input_history():
    msgs = [_img_tool_msg(str(i)) for i in range(5)]
    snapshot_first = msgs[0]["content"]
    evict_openai_screenshots(msgs, max_keep=2)
    # The canonical history object is untouched (still has its image).
    assert msgs[0]["content"] is snapshot_first
    assert _has_image(msgs[0])


def test_text_summary_preserved_on_stripped_message():
    msgs = [_img_tool_msg(str(i)) for i in range(4)]
    out = evict_openai_screenshots(msgs, max_keep=1)
    stripped = out[0]
    # The text part survives so the model keeps the summary context.
    assert any(p.get("text") == "capture 0" for p in stripped["content"])
    assert not _has_image(stripped)


def test_ignores_non_tool_image_messages():
    # A user message with an image must not count toward / be stripped by the
    # tool-result eviction policy.
    msgs = [
        {"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,U"}},
        ]},
        _img_tool_msg("a"),
        _img_tool_msg("b"),
    ]
    out = evict_openai_screenshots(msgs, max_keep=1)
    # User image untouched; only the older of the two tool images stripped.
    assert _has_image(out[0])
    assert not _has_image(out[1])
    assert _has_image(out[2])


# ---------------------------------------------------------------------------
# Codex / Responses transport wiring — the July 2026 request dumps showed
# 745KB SOM screenshots riding along verbatim in `function_call_output`
# items because only the Chat Completions transport evicted.
# ---------------------------------------------------------------------------

def test_codex_convert_messages_evicts_old_screenshots():
    from agent.transports.codex import ResponsesApiTransport

    msgs = [{"role": "user", "content": "go"}]
    for i in range(6):
        msgs.append({
            "role": "assistant", "content": None,
            "tool_calls": [{
                "id": f"call_{i}", "type": "function",
                "function": {"name": "computer_use", "arguments": "{}"},
            }],
        })
        msgs.append(_img_tool_msg(f"call_{i}"))

    transport = ResponsesApiTransport()
    items = transport.convert_messages(msgs, is_codex_backend=True)

    blob = str(items)
    # Newest 3 screenshots survive the conversion; older ones are gone.
    for tag in ("IMG_call_5", "IMG_call_4", "IMG_call_3"):
        assert tag in blob
    for tag in ("IMG_call_0", "IMG_call_1", "IMG_call_2"):
        assert tag not in blob
    assert "[screenshot removed to save context]" in blob


def test_codex_build_kwargs_evicts_old_screenshots():
    from agent.transports.codex import ResponsesApiTransport

    msgs = [{"role": "system", "content": "sys"},
            {"role": "user", "content": "go"}]
    for i in range(5):
        msgs.append({
            "role": "assistant", "content": None,
            "tool_calls": [{
                "id": f"call_{i}", "type": "function",
                "function": {"name": "computer_use", "arguments": "{}"},
            }],
        })
        msgs.append(_img_tool_msg(f"call_{i}"))

    transport = ResponsesApiTransport()
    kwargs = transport.build_kwargs("gpt-5.5", msgs, is_codex_backend=True)

    blob = str(kwargs["input"])
    assert "IMG_call_4" in blob
    assert "IMG_call_0" not in blob and "IMG_call_1" not in blob
