"""Tests for Arcee Trinity Large Thinking per-model overrides.

Arcee Trinity Large Thinking is a reasoning model that wants:
- Fixed temperature=0.5 (vs the global default)
- Compression threshold=0.75 (delay compression to preserve reasoning context)

The helpers must match the bare model name, including when it arrives via
OpenRouter as ``arcee-ai/trinity-large-thinking``, but must NOT hit sibling
Arcee models like trinity-large-preview or trinity-mini.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch

from agent.auxiliary_client import (
    _compression_threshold_for_model,
    _fixed_temperature_for_model,
    _is_arcee_trinity_thinking,
)


@pytest.mark.parametrize(
    "model",
    [
        "trinity-large-thinking",
        "arcee-ai/trinity-large-thinking",
        "Arcee-AI/Trinity-Large-Thinking",  # case-insensitive
        "  trinity-large-thinking  ",  # whitespace tolerant
    ],
)
def test_is_arcee_trinity_thinking_matches(model: str) -> None:
    assert _is_arcee_trinity_thinking(model) is True


@pytest.mark.parametrize(
    "model",
    [
        None,
        "",
        "trinity-large-preview",
        "arcee-ai/trinity-large-preview:free",
        "trinity-mini",
        "arcee-ai/trinity-mini",
        "trinity-large",  # prefix-only must not match
        "claude-sonnet-4.6",
        "gpt-5.4",
    ],
)
def test_is_arcee_trinity_thinking_rejects_non_matches(model) -> None:
    assert _is_arcee_trinity_thinking(model) is False


def test_fixed_temperature_for_trinity_thinking() -> None:
    assert _fixed_temperature_for_model("trinity-large-thinking") == 0.5
    assert _fixed_temperature_for_model("arcee-ai/trinity-large-thinking") == 0.5


def test_fixed_temperature_sibling_arcee_models_unaffected() -> None:
    # Preview and mini do not pin temperature — caller chooses its default.
    assert _fixed_temperature_for_model("trinity-large-preview") is None
    assert _fixed_temperature_for_model("trinity-mini") is None


def test_compression_threshold_for_trinity_thinking() -> None:
    assert _compression_threshold_for_model("trinity-large-thinking") == 0.75
    assert _compression_threshold_for_model("arcee-ai/trinity-large-thinking") == 0.75


def test_compression_threshold_for_local_qwen38_harness() -> None:
    assert _compression_threshold_for_model("qwen3.8-27b-q5xl") == 0.20
    assert _compression_threshold_for_model("local/qwen3.8-27b-q5xl") == 0.20


def test_compression_threshold_for_codex_sol_max_context() -> None:
    with patch(
        "agent.model_metadata._codex_max_context_opted_in", return_value=True
    ):
        threshold = _compression_threshold_for_model(
            "gpt-5.6-sol", "openai-codex", context_length=872_000
        )
    assert threshold is not None
    assert threshold == 820_000 / 872_000
    assert int(872_000 * threshold) == 820_000


@pytest.mark.parametrize(
    ("context_length", "expected_tokens"),
    [
        (900_000, 820_000),
        (872_000, 820_000),
        (800_000, 748_000),
    ],
)
def test_codex_sol_threshold_tracks_live_account_ceiling(
    context_length: int,
    expected_tokens: int,
) -> None:
    with patch(
        "agent.model_metadata._codex_max_context_opted_in", return_value=True
    ):
        threshold = _compression_threshold_for_model(
            "openai-codex:gpt-5.6-sol",
            "openai-codex",
            context_length=context_length,
        )
    assert threshold is not None
    assert int(context_length * threshold) == expected_tokens


def test_codex_sol_threshold_is_provider_and_opt_in_scoped() -> None:
    with patch(
        "agent.model_metadata._codex_max_context_opted_in", return_value=False
    ):
        assert (
            _compression_threshold_for_model("gpt-5.6-sol", "openai-codex")
            is None
        )
    with patch(
        "agent.model_metadata._codex_max_context_opted_in", return_value=True
    ):
        assert (
            _compression_threshold_for_model("gpt-5.6-sol", "openrouter")
            is None
        )


def test_compression_threshold_default_none_for_other_models() -> None:
    # None means "leave the user's config value unchanged".
    assert _compression_threshold_for_model(None) is None
    assert _compression_threshold_for_model("") is None
    assert _compression_threshold_for_model("trinity-large-preview") is None
    assert _compression_threshold_for_model("claude-sonnet-4.6") is None
    assert _compression_threshold_for_model("kimi-k2") is None
