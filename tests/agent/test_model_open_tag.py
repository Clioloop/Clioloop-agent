"""Tags for the managed model picker: (free) / (open) / (openrouter)."""

from agent.fusion_engine import label_model, model_open_tag


def test_free_managed_model():
    assert model_open_tag("openai/gpt-oss-120b:free") == "(free)"


def test_free_openrouter_suffix():
    assert model_open_tag("tencent/hy3-preview:free") == "(free)"


def test_open_weight_bare_id():
    assert model_open_tag("qwen3-coder:480b") == "(open)"


def test_paid_openrouter():
    assert model_open_tag("anthropic/claude-opus-4.8") == "(openrouter)"


def test_zero_pricing_marks_free():
    pricing = {"mystery-model": {"prompt": "0", "completion": "0"}}
    assert model_open_tag("mystery-model", pricing) == "(free)"


def test_nonzero_pricing_open():
    pricing = {"qwen3-coder:480b": {"prompt": "0.2", "completion": "1.8"}}
    assert model_open_tag("qwen3-coder:480b", pricing) == "(open)"


def test_free_wins_over_openrouter():
    # A ":free" OpenRouter variant is (free), not (openrouter).
    assert model_open_tag("vendor/model:free") == "(free)"


def test_blank_id():
    assert model_open_tag("") == ""


def test_label_model_includes_tag():
    assert label_model("openai/gpt-oss-120b:free") == "openai/gpt-oss-120b:free (free)"
    assert label_model("anthropic/claude-opus-4.8") == "anthropic/claude-opus-4.8 (openrouter)"
