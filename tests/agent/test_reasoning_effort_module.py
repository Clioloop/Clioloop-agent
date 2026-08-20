"""Contract tests for the canonical reasoning-effort vocabulary."""

import pytest

from agent.reasoning_effort import (
    EFFORT_LADDER,
    KIMI_K2_EFFORTS,
    KIMI_K3_EFFORTS,
    KIMI_K3_OVERRIDES,
    OPENAI_COMPAT_WIRE_EFFORTS,
    clamp_effort,
    kimi_supported_efforts,
    requested_effort,
)
from clio_constants import VALID_REASONING_EFFORTS


def test_ladder_covers_every_configurable_effort():
    assert set(VALID_REASONING_EFFORTS).issubset(EFFORT_LADDER)


def test_every_declared_wire_vocabulary_is_monotonic():
    import agent.reasoning_effort as module

    enabled_ladder = [level for level in EFFORT_LADDER if level != "none"]
    for name in dir(module):
        if not name.endswith("_EFFORTS"):
            continue
        supported = getattr(module, name)
        previous_rank = -1
        for level in enabled_ladder:
            resolved = clamp_effort(level, supported)
            rank = EFFORT_LADDER.index(resolved)
            assert rank >= previous_rank, (name, level, resolved)
            previous_rank = rank


def test_clamp_uses_nearest_weaker_level_without_disabling():
    assert clamp_effort("xhigh", ("none", "low", "medium", "high")) == "high"
    assert clamp_effort("minimal", ("none", "low", "high")) == "low"
    assert clamp_effort("none", ("none", "low", "high")) == "none"


def test_supported_and_bespoke_levels_pass_through():
    for level in OPENAI_COMPAT_WIRE_EFFORTS:
        assert clamp_effort(level, OPENAI_COMPAT_WIRE_EFFORTS) == level
    assert clamp_effort("turbo", ("low", "high")) == "turbo"


def test_vendor_override_wins():
    assert clamp_effort("medium", KIMI_K3_EFFORTS, KIMI_K3_OVERRIDES) == "high"
    assert clamp_effort("xhigh", KIMI_K3_EFFORTS, KIMI_K3_OVERRIDES) == "max"


@pytest.mark.parametrize(
    "model", ["k3", "k3-256k", "kimi-k3", "moonshotai/kimi-k3-cot"]
)
def test_kimi_k3_slugs(model):
    assert kimi_supported_efforts(model) is KIMI_K3_EFFORTS


@pytest.mark.parametrize("model", ["kimi-k2.6", "moonshotai/kimi-k2", None])
def test_kimi_k2_slugs(model):
    assert kimi_supported_efforts(model) is KIMI_K2_EFFORTS


def test_requested_effort_ignores_absent_and_disabled_configs():
    assert requested_effort({"enabled": True, "effort": "High"}) == "high"
    assert requested_effort({"enabled": False, "effort": "high"}) is None
    assert requested_effort({}) is None
