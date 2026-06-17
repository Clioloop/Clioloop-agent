"""Tests for the clio_cli models module."""

from unittest.mock import patch

from clio_cli.models import (
    OPENROUTER_MODELS, fetch_openrouter_models, model_ids, detect_provider_for_model,
    get_openrouter_model_metadata,
    union_with_portal_free_recommendations,
    union_with_portal_paid_recommendations,
)
import clio_cli.models as _models_mod

LIVE_OPENROUTER_MODELS = [
    ("anthropic/claude-opus-4.6", "recommended"),
    ("qwen/qwen3.7-max", ""),
    ("nvidia/nemotron-3-super-120b-a12b:free", "free"),
]



class TestModelIds:
    def test_returns_non_empty_list(self):
        with patch("clio_cli.models.fetch_openrouter_models", return_value=LIVE_OPENROUTER_MODELS):
            ids = model_ids()
        assert isinstance(ids, list)
        assert len(ids) > 0

    def test_ids_match_fetched_catalog(self):
        with patch("clio_cli.models.fetch_openrouter_models", return_value=LIVE_OPENROUTER_MODELS):
            ids = model_ids()
        expected = [mid for mid, _ in LIVE_OPENROUTER_MODELS]
        assert ids == expected

    def test_all_ids_contain_provider_slash(self):
        """Model IDs should follow the provider/model format."""
        with patch("clio_cli.models.fetch_openrouter_models", return_value=LIVE_OPENROUTER_MODELS):
            for mid in model_ids():
                assert "/" in mid, f"Model ID '{mid}' missing provider/ prefix"

    def test_no_duplicate_ids(self):
        with patch("clio_cli.models.fetch_openrouter_models", return_value=LIVE_OPENROUTER_MODELS):
            ids = model_ids()
        assert len(ids) == len(set(ids)), "Duplicate model IDs found"





class TestOpenRouterModels:
    def test_structure_is_list_of_tuples(self):
        for entry in OPENROUTER_MODELS:
            assert isinstance(entry, tuple) and len(entry) == 2
            mid, desc = entry
            assert isinstance(mid, str) and len(mid) > 0
            assert isinstance(desc, str)


class TestFetchOpenRouterModels:
    def test_live_fetch_recomputes_free_tags(self, monkeypatch):
        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"data":[{"id":"anthropic/claude-opus-4.8","pricing":{"prompt":"0.000015","completion":"0.000075"}},{"id":"qwen/qwen3.7-max","pricing":{"prompt":"0.000000325","completion":"0.00000195"}},{"id":"nvidia/nemotron-3-super-120b-a12b:free","pricing":{"prompt":"0","completion":"0"}}]}'

        monkeypatch.setattr(_models_mod, "_openrouter_catalog_cache", None)
        with patch("clio_cli.models.urllib.request.urlopen", return_value=_Resp()):
            models = fetch_openrouter_models(force_refresh=True)

        assert models == [
            ("anthropic/claude-opus-4.8", ""),
            ("qwen/qwen3.7-max", ""),
            ("nvidia/nemotron-3-super-120b-a12b:free", "free"),
        ]

    def test_falls_back_to_static_snapshot_on_fetch_failure(self, monkeypatch):
        monkeypatch.setattr(_models_mod, "_openrouter_catalog_cache", None)
        with patch("clio_cli.models.urllib.request.urlopen", side_effect=OSError("boom")):
            models = fetch_openrouter_models(force_refresh=True)

        assert models == OPENROUTER_MODELS

    def test_keeps_models_without_tool_support_and_records_warning_metadata(self, monkeypatch):
        """The picker shows all text models, with metadata for no-tool warnings."""
        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                # opus-4.6 advertises tools
                # nano-image has explicit supported_parameters that OMITS tools
                # qwen3.7-max advertises tools
                return (
                    b'{"data":['
                    b'{"id":"anthropic/claude-opus-4.6","name":"Claude Opus","architecture":{"output_modalities":["text"]},"pricing":{"prompt":"0.000015","completion":"0.000075"},'
                    b'"supported_parameters":["temperature","tools","tool_choice"]},'
                    b'{"id":"google/gemini-3-pro-image-preview","name":"Gemini Image","architecture":{"output_modalities":["text"]},"pricing":{"prompt":"0.00001","completion":"0.00003"},'
                    b'"supported_parameters":["temperature","response_format"]},'
                    b'{"id":"qwen/qwen3.7-max","name":"Qwen Max","architecture":{"output_modalities":["text"]},"pricing":{"prompt":"0.000000325","completion":"0.00000195"},'
                    b'"supported_parameters":["tools","temperature"]}'
                    b']}'
                )

        # Include the image-only id in the curated list so it has a chance to be surfaced.
        monkeypatch.setattr(
            _models_mod,
            "OPENROUTER_MODELS",
            [
                ("anthropic/claude-opus-4.6", ""),
                ("google/gemini-3-pro-image-preview", ""),
                ("qwen/qwen3.7-max", ""),
            ],
        )
        monkeypatch.setattr(_models_mod, "_openrouter_catalog_cache", None)
        monkeypatch.setattr(_models_mod, "_openrouter_catalog_metadata_cache", None)
        with patch("clio_cli.models.urllib.request.urlopen", return_value=_Resp()):
            models = fetch_openrouter_models(force_refresh=True)

        ids = [mid for mid, _ in models]
        assert "anthropic/claude-opus-4.6" in ids
        assert "qwen/qwen3.7-max" in ids
        assert "google/gemini-3-pro-image-preview" in ids

        meta = get_openrouter_model_metadata()
        assert meta["anthropic/claude-opus-4.6"]["supports_tools"] is True
        assert meta["google/gemini-3-pro-image-preview"]["supports_tools"] is False
        assert dict(models)["google/gemini-3-pro-image-preview"] == "limited: no tool support"

    def test_filters_out_non_text_output_models(self, monkeypatch):
        """Non-text outputs are not useful for chat/model pickers."""
        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return (
                    b'{"data":['
                    b'{"id":"openai/gpt-chat","architecture":{"output_modalities":["text"]},'
                    b'"pricing":{"prompt":"0.1","completion":"0.2"}},'
                    b'{"id":"image/only","architecture":{"output_modalities":["image"]},'
                    b'"pricing":{"prompt":"0.1","completion":"0.2"}}'
                    b']}'
                )

        monkeypatch.setattr(_models_mod, "_openrouter_catalog_cache", None)
        monkeypatch.setattr(_models_mod, "_openrouter_catalog_metadata_cache", None)
        with patch("clio_cli.models.urllib.request.urlopen", return_value=_Resp()):
            models = fetch_openrouter_models(force_refresh=True)

        assert [mid for mid, _ in models] == ["openai/gpt-chat"]

    def test_permissive_when_supported_parameters_missing(self, monkeypatch):
        """Models missing the supported_parameters field keep appearing in the picker.

        Some OpenRouter-compatible gateways (managed provider, private mirrors, older
        catalog snapshots) don't populate supported_parameters. Treating missing
        as 'unknown → allow' prevents the picker from silently emptying on
        those gateways.
        """
        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                # No supported_parameters field at all on either entry.
                return (
                    b'{"data":['
                    b'{"id":"anthropic/claude-opus-4.8","pricing":{"prompt":"0.000015","completion":"0.000075"}},'
                    b'{"id":"qwen/qwen3.7-max","pricing":{"prompt":"0.000000325","completion":"0.00000195"}}'
                    b']}'
                )

        monkeypatch.setattr(_models_mod, "_openrouter_catalog_cache", None)
        with patch("clio_cli.models.urllib.request.urlopen", return_value=_Resp()):
            models = fetch_openrouter_models(force_refresh=True)

        ids = [mid for mid, _ in models]
        assert "anthropic/claude-opus-4.8" in ids
        assert "qwen/qwen3.7-max" in ids


class TestOpenRouterToolSupportHelper:
    """Unit tests for _openrouter_model_supports_tools (Kilo port #9068)."""

    def test_tools_in_supported_parameters(self):
        from clio_cli.models import _openrouter_model_supports_tools
        assert _openrouter_model_supports_tools(
            {"id": "x", "supported_parameters": ["temperature", "tools"]}
        ) is True

    def test_tools_missing_from_supported_parameters(self):
        from clio_cli.models import _openrouter_model_supports_tools
        assert _openrouter_model_supports_tools(
            {"id": "x", "supported_parameters": ["temperature", "response_format"]}
        ) is False

    def test_supported_parameters_absent_is_permissive(self):
        """Missing field → allow (so older / non-OR gateways still work)."""
        from clio_cli.models import _openrouter_model_supports_tools
        assert _openrouter_model_supports_tools({"id": "x"}) is True

    def test_supported_parameters_none_is_permissive(self):
        from clio_cli.models import _openrouter_model_supports_tools
        assert _openrouter_model_supports_tools({"id": "x", "supported_parameters": None}) is True

    def test_supported_parameters_malformed_is_permissive(self):
        """Malformed (non-list) value → allow rather than silently drop."""
        from clio_cli.models import _openrouter_model_supports_tools
        assert _openrouter_model_supports_tools(
            {"id": "x", "supported_parameters": "tools,temperature"}
        ) is True

    def test_non_dict_item_is_permissive(self):
        from clio_cli.models import _openrouter_model_supports_tools
        assert _openrouter_model_supports_tools(None) is True
        assert _openrouter_model_supports_tools("anthropic/claude-opus-4.6") is True

    def test_empty_supported_parameters_list_drops_model(self):
        """Explicit empty list → no tools → drop."""
        from clio_cli.models import _openrouter_model_supports_tools
        assert _openrouter_model_supports_tools(
            {"id": "x", "supported_parameters": []}
        ) is False


class TestFindOpenrouterSlug:
    def test_exact_match(self):
        from clio_cli.models import _find_openrouter_slug
        with patch("clio_cli.models.fetch_openrouter_models", return_value=LIVE_OPENROUTER_MODELS):
            assert _find_openrouter_slug("anthropic/claude-opus-4.6") == "anthropic/claude-opus-4.6"

    def test_bare_name_match(self):
        from clio_cli.models import _find_openrouter_slug
        with patch("clio_cli.models.fetch_openrouter_models", return_value=LIVE_OPENROUTER_MODELS):
            result = _find_openrouter_slug("claude-opus-4.6")
        assert result == "anthropic/claude-opus-4.6"

    def test_case_insensitive(self):
        from clio_cli.models import _find_openrouter_slug
        with patch("clio_cli.models.fetch_openrouter_models", return_value=LIVE_OPENROUTER_MODELS):
            result = _find_openrouter_slug("Anthropic/Claude-Opus-4.6")
        assert result is not None

    def test_unknown_returns_none(self):
        from clio_cli.models import _find_openrouter_slug
        with patch("clio_cli.models.fetch_openrouter_models", return_value=LIVE_OPENROUTER_MODELS):
            assert _find_openrouter_slug("totally-fake-model-xyz") is None


class TestDetectProviderForModel:
    def test_anthropic_model_detected(self):
        """claude-opus-4-6 should resolve to anthropic provider."""
        with patch("clio_cli.models.fetch_openrouter_models", return_value=LIVE_OPENROUTER_MODELS):
            result = detect_provider_for_model("claude-opus-4-6", "openai-codex")
        assert result is not None
        assert result[0] == "anthropic"

    def test_deepseek_model_detected(self):
        """deepseek-chat should resolve to deepseek provider."""
        result = detect_provider_for_model("deepseek-chat", "openai-codex")
        assert result is not None
        # Provider is deepseek (direct) or openrouter (fallback) depending on creds
        assert result[0] in {"deepseek", "openrouter"}

    def test_current_provider_model_returns_none(self):
        """Models belonging to the current provider should not trigger a switch."""
        assert detect_provider_for_model("gpt-5.3-codex", "openai-codex") is None

    def test_short_alias_resolves_to_static_model(self):
        """Short aliases (e.g. sonnet) should resolve without network lookups."""
        with patch(
            "clio_cli.models.fetch_openrouter_models",
            side_effect=AssertionError("network lookup should not run"),
        ):
            result = detect_provider_for_model("sonnet", "auto")
        assert result is not None
        assert result[0] == "anthropic"
        assert result[1].startswith("claude-sonnet")

    def test_openrouter_slug_match(self):
        """Models in the OpenRouter catalog should be found."""
        with patch("clio_cli.models.fetch_openrouter_models", return_value=LIVE_OPENROUTER_MODELS):
            result = detect_provider_for_model("anthropic/claude-opus-4.6", "openai-codex")
        assert result is not None
        assert result[0] == "openrouter"
        assert result[1] == "anthropic/claude-opus-4.6"

    def test_bare_name_gets_openrouter_slug(self, monkeypatch):
        for env_var in (
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_TOKEN",
            "CLAUDE_CODE_TOKEN",
            "CLAUDE_CODE_OAUTH_TOKEN",
        ):
            monkeypatch.delenv(env_var, raising=False)
        """Bare model names should get mapped to full OpenRouter slugs."""
        with patch("clio_cli.models.fetch_openrouter_models", return_value=LIVE_OPENROUTER_MODELS):
            result = detect_provider_for_model("claude-opus-4.6", "openai-codex")
        assert result is not None
        # Should find it on OpenRouter with full slug
        assert result[1] == "anthropic/claude-opus-4.6"

    def test_unknown_model_returns_none(self):
        """Completely unknown model names should return None."""
        with patch("clio_cli.models.fetch_openrouter_models", return_value=LIVE_OPENROUTER_MODELS):
            assert detect_provider_for_model("nonexistent-model-xyz", "openai-codex") is None

    def test_aggregator_not_suggested(self):
        """openrouter should never be auto-suggested as target provider."""
        with patch("clio_cli.models.fetch_openrouter_models", return_value=LIVE_OPENROUTER_MODELS):
            result = detect_provider_for_model("claude-opus-4-6", "openai-codex")
        assert result is not None
        assert result[0] not in {"openrouter",}
