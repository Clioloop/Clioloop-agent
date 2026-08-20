"""Tests that switch_model does not inherit stale context_length overrides."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from run_agent import AIAgent
from agent.context_compressor import ContextCompressor


def _make_agent_with_compressor(config_context_length=None) -> Any:
    """Build a minimal AIAgent with a context_compressor, skipping __init__."""
    agent: Any = AIAgent.__new__(AIAgent)

    # Primary model settings
    agent.model = "primary-model"
    agent.provider = "openrouter"
    agent.base_url = "https://openrouter.ai/api/v1"
    agent.api_key = "sk-primary"
    agent.api_mode = "chat_completions"
    agent.client = MagicMock()
    agent.quiet_mode = True

    # Store the initial config_context_length override used at agent construction.
    agent._config_context_length = config_context_length
    setattr(agent, "_compression_threshold_config", 0.85)
    agent._compression_feasibility_checked = True

    # Context compressor with primary model values
    compressor = ContextCompressor(
        model="primary-model",
        threshold_percent=0.50,
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-primary",
        provider="openrouter",
        quiet_mode=True,
        config_context_length=config_context_length,
    )
    agent.context_compressor = compressor

    # For switch_model
    agent._primary_runtime = {}

    return agent


@patch("agent.model_metadata.get_model_context_length", return_value=131_072)
def test_switch_model_clears_previous_config_context_length(mock_ctx_len):
    """Switching models must not reuse the previous model.context_length override."""
    agent = _make_agent_with_compressor(config_context_length=32_768)

    assert agent.context_compressor.model == "primary-model"
    assert agent.context_compressor.context_length == 32_768  # From config override

    # Switch model
    agent.switch_model("new-model", "openrouter", api_key="sk-new", base_url="https://openrouter.ai/api/v1")

    # Verify the old config override is not passed to the new model.
    mock_ctx_len.assert_called_once()
    call_kwargs = mock_ctx_len.call_args.kwargs
    assert call_kwargs.get("config_context_length") is None

    # Verify compressor was updated from the newly resolved model metadata.
    assert agent.context_compressor.model == "new-model"
    assert agent.context_compressor.context_length == 131_072


def test_switch_model_without_config_context_length():
    """When switching models without config override, config_context_length should be None."""
    agent = _make_agent_with_compressor(config_context_length=None)

    with patch("agent.model_metadata.get_model_context_length", return_value=128_000) as mock_ctx_len:
        # Switch model
        agent.switch_model("new-model", "openrouter", api_key="sk-new", base_url="https://openrouter.ai/api/v1")

        # Verify get_model_context_length was called with None
        mock_ctx_len.assert_called_once()
        call_kwargs = mock_ctx_len.call_args.kwargs
        assert call_kwargs.get("config_context_length") is None


def test_switch_model_recalculates_and_restores_model_specific_threshold():
    """A Qwen-specific threshold must not leak into the next model."""
    agent = _make_agent_with_compressor(config_context_length=None)

    with patch(
        "agent.model_metadata.get_model_context_length",
        side_effect=[65_536, 128_000],
    ):
        agent.switch_model(
            "qwen3.8-27b-q5xl",
            "openrouter",
            api_key="sk-new",
            base_url="https://openrouter.ai/api/v1",
        )
        compressor = getattr(agent, "context_compressor")
        assert compressor.threshold_percent == 0.20
        # ContextCompressor keeps the global 64K minimum threshold floor.
        assert compressor.threshold_tokens == 64_000

        agent.switch_model(
            "ordinary-model",
            "openrouter",
            api_key="sk-new",
            base_url="https://openrouter.ai/api/v1",
        )

    compressor = getattr(agent, "context_compressor")
    assert compressor.threshold_percent == 0.85
    assert compressor.threshold_tokens == 108_800
    assert agent._compression_feasibility_checked is False


def test_runtime_limit_removes_stale_codex_threshold_policy():
    """Opting out at runtime must restore the configured baseline threshold."""
    agent = _make_agent_with_compressor(config_context_length=None)
    agent.model = "gpt-5.6-sol"
    agent.provider = "openai-codex"
    agent.base_url = "https://chatgpt.com/backend-api/codex"
    agent.context_compressor.threshold_percent = 820_000 / 872_000
    agent.context_compressor.threshold_tokens = 820_000
    agent._primary_runtime = {}

    from agent.conversation_loop import _update_context_engine_for_runtime_limit

    with patch(
        "agent.auxiliary_client._compression_threshold_for_model",
        return_value=None,
    ):
        _update_context_engine_for_runtime_limit(agent, 272_000)

    assert agent.context_compressor.threshold_percent == 0.85
    assert agent.context_compressor.threshold_tokens == 231_200
    assert agent._compression_feasibility_checked is False
    assert agent._primary_runtime["compressor_threshold_tokens"] == 231_200


def test_plugin_context_engine_restores_baseline_and_owns_absolute_budget():
    """Host policy removal must not leak or overwrite plugin budget logic."""

    class _PluginEngine:
        name = "plugin-engine"

        def __init__(self):
            self.threshold_percent = 820_000 / 872_000
            self.threshold_tokens = 820_000
            self.context_length = 872_000

        def update_model(self, **kwargs):
            self.context_length = kwargs["context_length"]
            # Simulate plugin-specific DAG/budget logic that is not a simple
            # percentage and must remain authoritative.
            self.threshold_tokens = 123_456

    engine = _PluginEngine()
    agent = SimpleNamespace(
        model="ordinary-model",
        provider="custom",
        base_url="https://example.com/v1",
        api_key="key",
        api_mode="chat_completions",
        context_compressor=engine,
        _context_engine_base_threshold_percent=0.31,
        _compression_feasibility_checked=True,
        _fallback_activated=False,
        _primary_runtime={},
    )

    from agent.agent_runtime_helpers import update_context_engine_runtime

    with patch(
        "agent.auxiliary_client._compression_threshold_for_model",
        return_value=None,
    ):
        update_context_engine_runtime(
            agent,
            400_000,
            sync_primary_runtime=True,
        )

    assert engine.threshold_percent == 0.31
    assert engine.context_length == 400_000
    assert engine.threshold_tokens == 123_456
    assert agent._compression_feasibility_checked is False
    assert agent._primary_runtime["compressor_threshold_tokens"] == 123_456
