"""Focused tests for classic CLI model-picker fuzzy filtering."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from cli import ClioCLI


def _bare_cli() -> ClioCLI:
    cli_obj = ClioCLI.__new__(ClioCLI)
    cli_obj.provider = "openai"
    cli_obj.model = "gpt-current"
    cli_obj.base_url = ""
    cli_obj.api_key = ""
    cli_obj._invalidate = MagicMock()
    return cli_obj


def test_filter_is_case_insensitive_subsequence_and_preserves_indices():
    entries = [
        "claude-sonnet-4-6",
        "GPT-5.4 Mini  (openrouter)",
        "gemini-3-pro",
    ]

    assert ClioCLI._filter_model_picker_entries(entries, "g54m") == [
        (1, "GPT-5.4 Mini  (openrouter)"),
    ]


def test_filter_empty_query_preserves_catalog_order():
    entries = ["model-b", "model-a"]

    assert ClioCLI._filter_model_picker_entries(entries, "  ") == [
        (0, "model-b"),
        (1, "model-a"),
    ]


def test_filter_returns_empty_list_when_no_model_matches():
    assert ClioCLI._filter_model_picker_entries(["claude", "gemini"], "gpt") == []


def test_filter_update_resets_selection_and_scroll():
    cli_obj = _bare_cli()
    cli_obj._model_picker_state = {
        "filter": "old",
        "selected": 7,
        "_scroll_offset": 5,
    }

    with patch.object(cli_obj, "_invalidate") as invalidate:
        cli_obj._update_model_picker_filter("gpt")

    assert cli_obj._model_picker_state == {
        "filter": "gpt",
        "selected": 0,
        "_scroll_offset": 0,
    }
    invalidate.assert_called_once_with(min_interval=0.0)


def test_filtered_selection_uses_original_raw_model_id():
    cli_obj = _bare_cli()
    cli_obj._model_picker_state = {
        "stage": "model",
        "selected": 0,
        "filter": "g54m",
        "provider_data": {"slug": "managed"},
        "model_list": [
            "claude-sonnet-4-6  (open)",
            "openai/gpt-5.4-mini  (openrouter)",
        ],
        "model_ids": ["claude-sonnet-4-6", "openai/gpt-5.4-mini"],
        "user_provs": None,
        "custom_provs": None,
    }
    cli_obj._close_model_picker = MagicMock()
    cli_obj._apply_model_switch_result = MagicMock()
    result = SimpleNamespace(success=True)

    with patch("clio_cli.model_switch.switch_model", return_value=result) as switch_model:
        cli_obj._handle_model_picker_selection()

    assert switch_model.call_args.kwargs["raw_input"] == "openai/gpt-5.4-mini"
    assert switch_model.call_args.kwargs["explicit_provider"] == "managed"
    cli_obj._close_model_picker.assert_called_once_with()
    cli_obj._apply_model_switch_result.assert_called_once_with(result, False)


def test_no_matches_keeps_back_and_cancel_actions_available():
    cli_obj = _bare_cli()
    cli_obj._model_picker_state = {
        "stage": "model",
        "selected": 0,
        "filter": "no-match",
        "provider_data": {"slug": "openai"},
        "providers": [{"slug": "openai"}],
        "model_list": ["gpt-5.4"],
        "model_ids": ["gpt-5.4"],
    }
    cli_obj._close_model_picker = MagicMock()

    cli_obj._handle_model_picker_selection()

    assert cli_obj._model_picker_state["stage"] == "provider"
    assert cli_obj._model_picker_state["filter"] == ""
    assert cli_obj._model_picker_state["selected"] == 0
    cli_obj._close_model_picker.assert_not_called()
