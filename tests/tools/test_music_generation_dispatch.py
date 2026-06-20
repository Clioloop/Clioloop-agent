"""Tests for the unified ``music_generate`` tool dispatch surface.

Covers:
- Basic generate action (backward compat — no action field defaults to generate)
- All 5 actions (generate, extend, cover, add_vocals, stems)
- Parameter passing (style, negative_tags, vocal_gender, title, etc.)
- Follow-up action validation (parent_job_id, track_index/track_id)
- Error handling (missing prompt, missing parent_job_id, bad action)
- Provider exceptions
- Schema correctness (new fields present, dead fields removed)
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import pytest

from agent import music_gen_registry
from agent.music_gen_provider import MusicGenProvider


@pytest.fixture(autouse=True)
def _reset_registry():
    music_gen_registry._reset_for_tests()
    yield
    music_gen_registry._reset_for_tests()


class _RecordingProvider(MusicGenProvider):
    """Captures the kwargs the tool layer hands it."""

    def __init__(self, name: str = "fake"):
        self._name = name
        self.last_kwargs: Dict[str, Any] = {}
        self.last_prompt: str = ""

    @property
    def name(self) -> str:
        return self._name

    def list_models(self) -> List[Dict[str, Any]]:
        return [{"id": "suno-v5"}]

    def default_model(self) -> Optional[str]:
        return "suno-v5"

    def generate(self, prompt, **kwargs):
        self.last_prompt = prompt
        self.last_kwargs = dict(kwargs)
        action = kwargs.get("action", "generate")
        return {
            "success": True,
            "audio": "/tmp/fake_audio.mp3",
            "model": kwargs.get("model", "suno-v5"),
            "prompt": prompt,
            "action": action,
            "duration": 120,
            "instrumental": kwargs.get("instrumental", False),
            "provider": self._name,
            "job_id": "fake-job-123",
            "track_id": "track-abc",
            "track_index": 1,
            "all_tracks": [
                {"id": "track-abc", "audio": "/tmp/fake1.mp3", "title": "Test", "duration": 120, "track_index": 1},
                {"id": "track-def", "audio": "/tmp/fake2.mp3", "title": "Test", "duration": 118, "track_index": 2},
            ],
            "parent_job_id": kwargs.get("parent_job_id", ""),
            "follow_up_hint": "Can extend, cover, or stems.",
        }


class _RaisingProvider(MusicGenProvider):
    @property
    def name(self) -> str:
        return "raises"

    def generate(self, prompt, **kwargs):
        raise RuntimeError("boom")


class TestUnifiedDispatch:
    def _run(self, args: Dict[str, Any], *, configured: Optional[str] = None) -> Dict[str, Any]:
        from tools import music_generation_tool
        import clio_cli.plugins as plugins_module

        saved = music_generation_tool._read_configured_music_provider
        music_generation_tool._read_configured_music_provider = lambda: configured  # type: ignore
        saved_discover = plugins_module._ensure_plugins_discovered
        plugins_module._ensure_plugins_discovered = lambda *_a, **_k: None  # type: ignore
        try:
            raw = music_generation_tool._handle_music_generate(args)
        finally:
            music_generation_tool._read_configured_music_provider = saved  # type: ignore
            plugins_module._ensure_plugins_discovered = saved_discover  # type: ignore
        return json.loads(raw)

    # --- Error cases ---

    def test_no_provider_returns_clear_error(self):
        result = self._run({"confirmed": True, "prompt": "a song"})
        assert result["success"] is False
        assert result["error_type"] == "no_provider_configured"

    def test_unknown_provider_returns_clear_error(self):
        result = self._run({"confirmed": True, "prompt": "a song"}, configured="ghost")
        assert result["success"] is False
        assert result["error_type"] == "provider_not_registered"

    def test_provider_exception_caught(self):
        music_gen_registry.register_provider(_RaisingProvider())
        result = self._run({"confirmed": True, "prompt": "x"}, configured="raises")
        assert result["success"] is False
        assert result["error_type"] == "provider_exception"

    def test_invalid_action_rejected(self):
        result = self._run({"confirmed": True, "prompt": "x", "action": "remix"})
        assert "error" in result
        assert "remix" in result["error"].lower() or "Invalid" in result["error"]

    # --- Generate action ---

    def test_generate_default_action(self):
        """When action is omitted, defaults to 'generate'."""
        provider = _RecordingProvider("rec")
        music_gen_registry.register_provider(provider)
        result = self._run({"confirmed": True, "prompt": "upbeat synthwave"}, configured="rec")
        assert result["success"] is True
        assert provider.last_kwargs["action"] == "generate"

    def test_generate_explicit_action(self):
        provider = _RecordingProvider("rec")
        music_gen_registry.register_provider(provider)
        result = self._run({"confirmed": True, "prompt": "a song", "action": "generate"}, configured="rec")
        assert result["success"] is True
        assert provider.last_kwargs["action"] == "generate"

    def test_generate_prompt_required(self):
        """When confirmed=true but no prompt/lyrics, prompt error is returned."""
        provider = _RecordingProvider("rec")
        music_gen_registry.register_provider(provider)
        result = self._run({"action": "generate", "confirmed": True})
        assert "error" in result
        assert "prompt" in result["error"].lower()

    def test_generate_with_lyrics(self):
        provider = _RecordingProvider("rec")
        music_gen_registry.register_provider(provider)
        result = self._run({
            "action": "generate",
            "confirmed": True,
            "prompt": "a song",
            "lyrics": "[Verse]\nHello world\n[Chorus]\nYeah",
        }, configured="rec")
        assert result["success"] is True
        assert provider.last_kwargs["lyrics"] == "[Verse]\nHello world\n[Chorus]\nYeah"

    def test_generate_instrumental(self):
        provider = _RecordingProvider("rec")
        music_gen_registry.register_provider(provider)
        result = self._run({
            "action": "generate",
            "confirmed": True,
            "prompt": "ambient",
            "instrumental": True,
        }, configured="rec")
        assert result["success"] is True
        assert provider.last_kwargs["instrumental"] is True

    def test_generate_with_style(self):
        provider = _RecordingProvider("rec")
        music_gen_registry.register_provider(provider)
        result = self._run({
            "action": "generate",
            "confirmed": True,
            "prompt": "a song",
            "style": "synthwave, electronic",
        }, configured="rec")
        assert result["success"] is True
        assert provider.last_kwargs["style"] == "synthwave, electronic"

    def test_generate_with_negative_tags(self):
        provider = _RecordingProvider("rec")
        music_gen_registry.register_provider(provider)
        result = self._run({
            "action": "generate",
            "confirmed": True,
            "prompt": "a song",
            "negative_tags": "country, jazz",
        }, configured="rec")
        assert result["success"] is True
        assert provider.last_kwargs["negative_tags"] == "country, jazz"

    def test_generate_with_vocal_gender(self):
        provider = _RecordingProvider("rec")
        music_gen_registry.register_provider(provider)
        result = self._run({
            "action": "generate",
            "confirmed": True,
            "prompt": "a song",
            "vocal_gender": "f",
        }, configured="rec")
        assert result["success"] is True
        assert provider.last_kwargs["vocal_gender"] == "f"

    def test_generate_with_mixed_vocal_gender(self):
        """vocal_gender='mixed' should be accepted by the tool layer."""
        provider = _RecordingProvider("rec")
        music_gen_registry.register_provider(provider)
        result = self._run({
            "action": "generate",
            "confirmed": True,
            "prompt": "a song",
            "vocal_gender": "mixed",
        }, configured="rec")
        assert result["success"] is True
        assert provider.last_kwargs["vocal_gender"] == "mixed"

    def test_generate_with_title(self):
        provider = _RecordingProvider("rec")
        music_gen_registry.register_provider(provider)
        result = self._run({
            "action": "generate",
            "confirmed": True,
            "prompt": "a song",
            "title": "My Song",
        }, configured="rec")
        assert result["success"] is True
        assert provider.last_kwargs["title"] == "My Song"

    def test_generate_with_style_weight(self):
        provider = _RecordingProvider("rec")
        music_gen_registry.register_provider(provider)
        result = self._run({
            "action": "generate",
            "confirmed": True,
            "prompt": "a song",
            "style_weight": 0.8,
        }, configured="rec")
        assert result["success"] is True
        assert provider.last_kwargs["style_weight"] == 0.8

    def test_generate_with_weirdness(self):
        provider = _RecordingProvider("rec")
        music_gen_registry.register_provider(provider)
        result = self._run({
            "action": "generate",
            "confirmed": True,
            "prompt": "a song",
            "weirdness": 0.5,
        }, configured="rec")
        assert result["success"] is True
        assert provider.last_kwargs["weirdness"] == 0.5

    def test_generate_with_auto_lyrics(self):
        provider = _RecordingProvider("rec")
        music_gen_registry.register_provider(provider)
        result = self._run({
            "action": "generate",
            "confirmed": True,
            "prompt": "a song",
            "lyrics": "[Verse]\nTest",
            "auto_lyrics": True,
        }, configured="rec")
        assert result["success"] is True
        assert provider.last_kwargs["auto_lyrics"] is True

    def test_generate_invalid_vocal_gender(self):
        provider = _RecordingProvider("rec")
        music_gen_registry.register_provider(provider)
        result = self._run({
            "action": "generate",
            "confirmed": True,
            "prompt": "a song",
            "vocal_gender": "x",
        }, configured="rec")
        assert "error" in result
        assert "vocal_gender" in result["error"].lower()

    def test_generate_response_has_job_id(self):
        provider = _RecordingProvider("rec")
        music_gen_registry.register_provider(provider)
        result = self._run({"confirmed": True, "prompt": "a song"}, configured="rec")
        assert result["success"] is True
        assert result["job_id"] == "fake-job-123"
        assert result["track_id"] == "track-abc"
        assert len(result["all_tracks"]) == 2

    # --- Extend action ---

    def test_extend_requires_parent_job_id(self):
        provider = _RecordingProvider("rec")
        music_gen_registry.register_provider(provider)
        result = self._run({
            "action": "extend",
            "track_index": 1,
        }, configured="rec")
        assert "error" in result
        assert "parent_job_id" in result["error"]

    def test_extend_requires_track_index_or_id(self):
        provider = _RecordingProvider("rec")
        music_gen_registry.register_provider(provider)
        result = self._run({
            "action": "extend",
            "parent_job_id": "job-123",
        }, configured="rec")
        assert "error" in result
        assert "track_index" in result["error"].lower() or "track_id" in result["error"].lower()

    def test_extend_with_track_index(self):
        provider = _RecordingProvider("rec")
        music_gen_registry.register_provider(provider)
        result = self._run({
            "action": "extend",
            "parent_job_id": "job-123",
            "track_index": 1,
            "continue_at": 120,
        }, configured="rec")
        assert result["success"] is True
        assert provider.last_kwargs["action"] == "extend"
        assert provider.last_kwargs["parent_job_id"] == "job-123"
        assert provider.last_kwargs["track_index"] == 1
        assert provider.last_kwargs["continue_at"] == 120

    def test_extend_with_track_id(self):
        provider = _RecordingProvider("rec")
        music_gen_registry.register_provider(provider)
        result = self._run({
            "action": "extend",
            "parent_job_id": "job-123",
            "track_id": "track-abc",
            "prompt": "extended lyrics",
        }, configured="rec")
        assert result["success"] is True
        assert provider.last_kwargs["track_id"] == "track-abc"

    # --- Cover action ---

    def test_cover_with_style(self):
        provider = _RecordingProvider("rec")
        music_gen_registry.register_provider(provider)
        result = self._run({
            "action": "cover",
            "parent_job_id": "job-123",
            "track_index": 1,
            "style": "acoustic folk",
            "audio_weight": 0.8,
        }, configured="rec")
        assert result["success"] is True
        assert provider.last_kwargs["action"] == "cover"
        assert provider.last_kwargs["style"] == "acoustic folk"
        assert provider.last_kwargs["audio_weight"] == 0.8

    # --- Add vocals action ---

    def test_add_vocals_requires_prompt(self):
        provider = _RecordingProvider("rec")
        music_gen_registry.register_provider(provider)
        result = self._run({
            "action": "add_vocals",
            "parent_job_id": "job-123",
            "track_index": 1,
        }, configured="rec")
        assert "error" in result
        assert "prompt" in result["error"].lower() or "lyrics" in result["error"].lower()

    def test_add_vocals_with_prompt(self):
        provider = _RecordingProvider("rec")
        music_gen_registry.register_provider(provider)
        result = self._run({
            "action": "add_vocals",
            "parent_job_id": "job-123",
            "track_index": 1,
            "prompt": "[Verse]\nLa la la",
        }, configured="rec")
        assert result["success"] is True
        assert provider.last_kwargs["action"] == "add_vocals"

    # --- Stems action ---

    def test_stems_no_prompt_required(self):
        """Stems only needs parent_job_id + track_index, no prompt."""
        provider = _RecordingProvider("rec")
        music_gen_registry.register_provider(provider)
        result = self._run({
            "action": "stems",
            "parent_job_id": "job-123",
            "track_index": 1,
        }, configured="rec")
        assert result["success"] is True
        assert provider.last_kwargs["action"] == "stems"

    # --- Schema tests ---

    def test_vocal_gender_enum_includes_mixed(self):
        """vocal_gender enum should include 'm', 'f', and 'mixed'."""
        from tools.music_generation_tool import MUSIC_GENERATE_SCHEMA
        props = MUSIC_GENERATE_SCHEMA["parameters"]["properties"]
        assert "vocal_gender" in props
        enum = props["vocal_gender"]["enum"]
        assert "m" in enum
        assert "f" in enum
        assert "mixed" in enum

    def test_action_field_in_schema(self):
        from tools.music_generation_tool import MUSIC_GENERATE_SCHEMA
        props = MUSIC_GENERATE_SCHEMA["parameters"]["properties"]
        assert "action" in props
        assert "generate" in props["action"]["enum"]
        assert "extend" in props["action"]["enum"]
        assert "cover" in props["action"]["enum"]
        assert "add_vocals" in props["action"]["enum"]
        assert "stems" in props["action"]["enum"]

    def test_new_params_in_schema(self):
        from tools.music_generation_tool import MUSIC_GENERATE_SCHEMA
        props = MUSIC_GENERATE_SCHEMA["parameters"]["properties"]
        # New generation params
        assert "style" in props
        assert "negative_tags" in props
        assert "vocal_gender" in props
        assert "title" in props
        assert "style_weight" in props
        assert "weirdness" in props
        assert "auto_lyrics" in props
        # Follow-up params
        assert "parent_job_id" in props
        assert "track_index" in props
        assert "track_id" in props
        assert "continue_at" in props
        assert "audio_weight" in props

    def test_dead_params_removed_from_schema(self):
        """Duration, output_format, seed, image_url were never supported by Suno."""
        from tools.music_generation_tool import MUSIC_GENERATE_SCHEMA
        props = MUSIC_GENERATE_SCHEMA["parameters"]["properties"]
        assert "duration" not in props
        assert "output_format" not in props
        assert "seed" not in props
        assert "image_url" not in props

    def test_action_and_confirmed_are_required(self):
        from tools.music_generation_tool import MUSIC_GENERATE_SCHEMA
        required = MUSIC_GENERATE_SCHEMA["parameters"]["required"]
        assert "action" in required
        assert "confirmed" in required
        # prompt is NOT in required (it's conditionally required based on action)
        assert "prompt" not in required


class TestApiframeRequestBuilding:
    """Unit tests for the Apiframe provider's request body builders.

    These test the internal _build_generate_body and _build_action_body
    methods without making any API calls.
    """

    def _get_provider(self):
        from plugins.music_gen.apiframe import ApiframeMusicGenProvider
        return ApiframeMusicGenProvider()

    def test_generate_basic_description_mode(self):
        p = self._get_provider()
        body = p._build_generate_body(
            prompt="upbeat electronic track",
            resolved_model="suno-v5",
            lyrics=None,
            instrumental=None,
            style=None,
            negative_tags=None,
            vocal_gender=None,
            title=None,
            style_weight=None,
            weirdness=None,
            auto_lyrics=None,
        )
        assert body["model"] == "suno"
        assert body["prompt"] == "upbeat electronic track"
        assert body["sunoParams"]["custom_mode"] is False
        assert body["sunoParams"]["model_version"] == "V5"

    def test_generate_custom_mode_with_lyrics(self):
        p = self._get_provider()
        body = p._build_generate_body(
            prompt="a song",
            resolved_model="suno-v5",
            lyrics="[Verse]\nHello world",
            instrumental=None,
            style=None,
            negative_tags=None,
            vocal_gender=None,
            title=None,
            style_weight=None,
            weirdness=None,
            auto_lyrics=None,
        )
        assert body["sunoParams"]["custom_mode"] is True
        assert body["prompt"] == "[Verse]\nHello world"
        # Regression: "prompt" must NOT be inside sunoParams (causes 400 error)
        assert "prompt" not in body["sunoParams"]

    def test_generate_instrumental(self):
        p = self._get_provider()
        body = p._build_generate_body(
            prompt="ambient",
            resolved_model="suno-v5",
            lyrics=None,
            instrumental=True,
            style=None,
            negative_tags=None,
            vocal_gender=None,
            title=None,
            style_weight=None,
            weirdness=None,
            auto_lyrics=None,
        )
        assert body["sunoParams"]["instrumental"] is True

    def test_generate_with_all_params(self):
        p = self._get_provider()
        body = p._build_generate_body(
            prompt="a song",
            resolved_model="suno-v5_5",
            lyrics=None,
            instrumental=False,
            style="synthwave, electronic",
            negative_tags="country, jazz",
            vocal_gender="f",
            title="My Song",
            style_weight=0.8,
            weirdness=0.3,
            auto_lyrics=None,
        )
        sp = body["sunoParams"]
        assert sp["model_version"] == "V5_5"
        assert sp["style"] == "synthwave, electronic"
        assert sp["negative_tags"] == "country, jazz"
        assert sp["vocal_gender"] == "f"
        assert sp["title"] == "My Song"
        assert sp["style_weight"] == 0.8
        assert sp["weirdness_constraint"] == 0.3

    def test_generate_prompt_truncated_in_description_mode(self):
        p = self._get_provider()
        long_prompt = "x" * 600
        body = p._build_generate_body(
            prompt=long_prompt,
            resolved_model="suno-v5",
            lyrics=None,
            instrumental=None,
            style=None,
            negative_tags=None,
            vocal_gender=None,
            title=None,
            style_weight=None,
            weirdness=None,
            auto_lyrics=None,
        )
        assert len(body["prompt"]) == 500

    def test_generate_lyrics_not_truncated_in_custom_mode(self):
        p = self._get_provider()
        long_lyrics = "[Verse]\n" + "x" * 600
        body = p._build_generate_body(
            prompt="a song",
            resolved_model="suno-v5",
            lyrics=long_lyrics,
            instrumental=None,
            style=None,
            negative_tags=None,
            vocal_gender=None,
            title=None,
            style_weight=None,
            weirdness=None,
            auto_lyrics=None,
        )
        assert len(body["prompt"]) == len(long_lyrics)

    def test_generate_invalid_vocal_gender_ignored(self):
        p = self._get_provider()
        body = p._build_generate_body(
            prompt="a song",
            resolved_model="suno-v5",
            lyrics=None,
            instrumental=None,
            style=None,
            negative_tags=None,
            vocal_gender="x",  # invalid
            title=None,
            style_weight=None,
            weirdness=None,
            auto_lyrics=None,
        )
        assert "vocal_gender" not in body["sunoParams"]

    def test_generate_mixed_vocal_gender_not_sent_to_suno(self):
        """vocal_gender='mixed' should NOT be sent to Suno API.
        Suno only accepts 'm' or 'f'. When 'mixed', we omit the param
        so Suno naturally generates both male and female vocals."""
        p = self._get_provider()
        body = p._build_generate_body(
            prompt="a song",
            resolved_model="suno-v5",
            lyrics=None,
            instrumental=None,
            style=None,
            negative_tags=None,
            vocal_gender="mixed",
            title=None,
            style_weight=None,
            weirdness=None,
            auto_lyrics=None,
        )
        assert "vocal_gender" not in body["sunoParams"]

    def test_generate_style_weight_clamped(self):
        p = self._get_provider()
        body = p._build_generate_body(
            prompt="a song",
            resolved_model="suno-v5",
            lyrics=None,
            instrumental=None,
            style=None,
            negative_tags=None,
            vocal_gender=None,
            title=None,
            style_weight=5.0,  # out of range
            weirdness=None,
            auto_lyrics=None,
        )
        assert body["sunoParams"]["style_weight"] == 1.0

    def test_generate_weirdness_clamped(self):
        p = self._get_provider()
        body = p._build_generate_body(
            prompt="a song",
            resolved_model="suno-v5",
            lyrics=None,
            instrumental=None,
            style=None,
            negative_tags=None,
            vocal_gender=None,
            title=None,
            style_weight=None,
            weirdness=-1.0,  # out of range
            auto_lyrics=None,
        )
        assert body["sunoParams"]["weirdness_constraint"] == 0.0

    # --- Action body builder ---

    def test_action_extend_body(self):
        p = self._get_provider()
        body = p._build_action_body(
            action="extend",
            parent_job_id="job-123",
            track_index=1,
            track_id=None,
            prompt="extended lyrics",
            lyrics=None,
            style="rock",
            negative_tags=None,
            title=None,
            continue_at=120,
            audio_weight=None,
        )
        assert body["parentJobId"] == "job-123"
        assert body["action"] == "extend"
        assert body["index"] == 1
        assert body["continueAt"] == 120.0
        assert body["prompt"] == "extended lyrics"
        assert body["style"] == "rock"

    def test_action_extend_with_track_id(self):
        p = self._get_provider()
        body = p._build_action_body(
            action="extend",
            parent_job_id="job-123",
            track_index=None,
            track_id="track-abc",
            prompt="",
            lyrics=None,
            style=None,
            negative_tags=None,
            title=None,
            continue_at=None,
            audio_weight=None,
        )
        assert body["trackId"] == "track-abc"
        assert "index" not in body

    def test_action_cover_body(self):
        p = self._get_provider()
        body = p._build_action_body(
            action="cover",
            parent_job_id="job-123",
            track_index=2,
            track_id=None,
            prompt="new lyrics",
            lyrics=None,
            style="acoustic folk",
            negative_tags="metal",
            title="Cover Version",
            continue_at=None,
            audio_weight=0.7,
        )
        assert body["action"] == "cover"
        assert body["index"] == 2
        assert body["style"] == "acoustic folk"
        assert body["negative_tags"] == "metal"
        assert body["title"] == "Cover Version"
        assert body["audio_weight"] == 0.7

    def test_action_add_vocals_body(self):
        p = self._get_provider()
        lyrics = "[Verse]\nLa la la"
        body = p._build_action_body(
            action="add_vocals",
            parent_job_id="job-123",
            track_index=1,
            track_id=None,
            prompt="",
            lyrics=lyrics,
            style=None,
            negative_tags=None,
            title=None,
            continue_at=None,
            audio_weight=None,
        )
        assert body["action"] == "add_vocals"
        assert body["prompt"] == lyrics

    def test_action_stems_body_minimal(self):
        p = self._get_provider()
        body = p._build_action_body(
            action="stems",
            parent_job_id="job-123",
            track_index=1,
            track_id=None,
            prompt="",
            lyrics=None,
            style=None,
            negative_tags=None,
            title=None,
            continue_at=None,
            audio_weight=None,
        )
        assert body["parentJobId"] == "job-123"
        assert body["action"] == "stems"
        assert body["index"] == 1
        # Stems should not have any extra params
        assert "prompt" not in body
        assert "style" not in body
        assert "continueAt" not in body

    def test_action_cover_audio_weight_clamped(self):
        p = self._get_provider()
        body = p._build_action_body(
            action="cover",
            parent_job_id="job-123",
            track_index=1,
            track_id=None,
            prompt="",
            lyrics=None,
            style=None,
            negative_tags=None,
            title=None,
            continue_at=None,
            audio_weight=2.0,  # out of range
        )
        assert body["audio_weight"] == 1.0


class TestApiframeProvider:
    """Tests for the Apiframe provider's interface methods."""

    def _get_provider(self):
        from plugins.music_gen.apiframe import ApiframeMusicGenProvider
        return ApiframeMusicGenProvider()

    def test_provider_name(self):
        p = self._get_provider()
        assert p.name == "music_gen"

    def test_provider_display_name(self):
        p = self._get_provider()
        assert p.display_name == "Music Generation"

    def test_provider_models(self):
        p = self._get_provider()
        models = p.list_models()
        assert len(models) == 2
        ids = [m["id"] for m in models]
        assert "suno-v5" in ids
        assert "suno-v5_5" in ids

    def test_provider_default_model(self):
        p = self._get_provider()
        assert p.default_model() == "suno-v5_5"

    def test_provider_capabilities(self):
        p = self._get_provider()
        caps = p.capabilities()
        assert caps["supports_lyrics"] is True
        assert caps["supports_instrumental"] is True
        assert caps["supports_extend"] is True
        assert caps["supports_cover"] is True
        assert caps["supports_add_vocals"] is True
        assert caps["supports_stems"] is True
        assert caps["supports_style"] is True
        assert caps["supports_vocal_gender"] is True

    def test_provider_rejects_unknown_model(self):
        p = self._get_provider()
        result = p.generate("test", model="unknown-model")
        assert result["success"] is False
        assert result["error_type"] == "invalid_model"

    def test_provider_follow_up_requires_parent_job_id(self):
        p = self._get_provider()
        result = p.generate("test", action="extend", track_index=1)
        assert result["success"] is False
        assert result["error_type"] == "missing_required_param"

    def test_provider_follow_up_requires_track_reference(self):
        p = self._get_provider()
        result = p.generate("test", action="extend", parent_job_id="job-123")
        assert result["success"] is False
        assert result["error_type"] == "missing_required_param"

    def test_provider_follow_up_stems_no_prompt_needed(self):
        """Stems action should not require prompt — it's just a split."""
        p = self._get_provider()
        # This should get past validation and fail at the API call stage
        # (since we have no API key), not at param validation.
        result = p.generate("", action="stems", parent_job_id="job-123", track_index=1)
        # Will fail because no API key — but NOT with missing_required_param
        assert result["error_type"] != "missing_required_param"


class TestConfirmationEnforcement:
    """Tests for the code-level confirmation enforcement on action='generate'."""

    def _run(self, args: Dict[str, Any], *, configured: Optional[str] = None) -> Dict[str, Any]:
        from tools import music_generation_tool
        import clio_cli.plugins as plugins_module

        saved = music_generation_tool._read_configured_music_provider
        music_generation_tool._read_configured_music_provider = lambda: configured  # type: ignore
        saved_discover = plugins_module._ensure_plugins_discovered
        plugins_module._ensure_plugins_discovered = lambda *_a, **_k: None  # type: ignore
        try:
            raw = music_generation_tool._handle_music_generate(args)
        finally:
            music_generation_tool._read_configured_music_provider = saved  # type: ignore
            plugins_module._ensure_plugins_discovered = saved_discover  # type: ignore
        return json.loads(raw)

    def test_generate_without_confirmed_returns_error(self):
        """action='generate' without confirmed must return an error."""
        provider = _RecordingProvider("rec")
        music_gen_registry.register_provider(provider)
        result = self._run({"prompt": "a song"}, configured="rec")
        assert result.get("success") is False or "error" in result
        assert "CONFIRMATION REQUIRED" in result.get("error", "")
    
    def test_generate_with_confirmed_false_returns_error(self):
        """action='generate' with confirmed=false must return an error."""
        provider = _RecordingProvider("rec")
        music_gen_registry.register_provider(provider)
        result = self._run({"prompt": "a song", "confirmed": False}, configured="rec")
        assert "CONFIRMATION REQUIRED" in result.get("error", "")

    def test_generate_with_confirmed_true_proceeds(self):
        """action='generate' with confirmed=true should reach the provider."""
        provider = _RecordingProvider("rec")
        music_gen_registry.register_provider(provider)
        result = self._run({"prompt": "a song", "confirmed": True}, configured="rec")
        assert result["success"] is True

    def test_generate_with_confirmed_string_true_proceeds(self):
        """confirmed='true' (string) should also work via _coerce_bool."""
        provider = _RecordingProvider("rec")
        music_gen_registry.register_provider(provider)
        result = self._run({"prompt": "a song", "confirmed": "true"}, configured="rec")
        assert result["success"] is True

    def test_follow_up_actions_dont_require_confirmed(self):
        """Follow-up actions (extend, cover, etc.) should NOT require confirmed."""
        provider = _RecordingProvider("rec")
        music_gen_registry.register_provider(provider)
        # extend without confirmed — should succeed
        result = self._run({
            "action": "extend",
            "parent_job_id": "job-123",
            "track_index": 1,
            "continue_at": 60,
        }, configured="rec")
        assert result["success"] is True
        # stems without confirmed — should succeed
        result = self._run({
            "action": "stems",
            "parent_job_id": "job-123",
            "track_index": 1,
        }, configured="rec")
        assert result["success"] is True

    def test_confirmed_field_in_schema(self):
        """The schema must have a 'confirmed' boolean property."""
        from tools.music_generation_tool import MUSIC_GENERATE_SCHEMA
        props = MUSIC_GENERATE_SCHEMA["parameters"]["properties"]
        assert "confirmed" in props
        assert props["confirmed"]["type"] == "boolean"

    def test_confirmation_error_mentions_all_details(self):
        """The error message should mention all 5 confirmation details."""
        provider = _RecordingProvider("rec")
        music_gen_registry.register_provider(provider)
        result = self._run({"prompt": "a song"}, configured="rec")
        error = result.get("error", "")
        assert "Mode" in error
        assert "Instrumental" in error
        assert "Style" in error
        assert "Vocal gender" in error
        assert "Title" in error


class TestFileNamingPrefix:
    """Tests that audio files are saved with clio_music_ prefix."""

    def test_save_b64_default_prefix_is_clio_music(self):
        from agent.music_gen_provider import save_b64_audio
        import base64, tempfile, os
        # Create a tiny fake audio bytes
        b64 = base64.b64encode(b"fake_audio_data").decode()
        path = save_b64_audio(b64)
        assert path.name.startswith("clio_music_")
        assert path.name.endswith(".mp3")
        path.unlink(missing_ok=True)

    def test_save_bytes_default_prefix_is_clio_music(self):
        from agent.music_gen_provider import save_bytes_audio
        path = save_bytes_audio(b"fake_audio_data")
        assert path.name.startswith("clio_music_")
        assert path.name.endswith(".mp3")
        path.unlink(missing_ok=True)

    def test_save_url_uses_clio_music_prefix(self):
        """Verify the save_url_audio function has clio_music as default prefix."""
        import inspect
        from agent.music_gen_provider import save_url_audio
        sig = inspect.signature(save_url_audio)
        assert sig.parameters["prefix"].default == "clio_music"

    def test_custom_prefix_still_works(self):
        """Custom prefix should override the default."""
        from agent.music_gen_provider import save_bytes_audio
        path = save_bytes_audio(b"fake", prefix="custom_prefix")
        assert path.name.startswith("custom_prefix_")
        path.unlink(missing_ok=True)


class TestGatewayAutoAppendDedup:
    """Tests for the gateway auto-append media tag deduplication."""

    def _make_messages(self, tool_result_json: str, tool_name: str = "music_generate"):
        """Build a minimal message list with one tool call + result."""
        return [
            {
                "role": "assistant",
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": tool_name, "arguments": "{}"},
                }],
            },
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "content": tool_result_json,
            },
        ]

    def test_music_generate_json_parsed_for_tracks(self):
        """The collector should parse music_generate JSON and extract all track paths."""
        from gateway.run import _collect_auto_append_media_tags
        import json as _json

        tool_result = _json.dumps({
            "success": True,
            "audio": "/tmp/track1.mp3",
            "all_tracks": [
                {"audio": "/tmp/track1.mp3", "track_index": 1},
                {"audio": "/tmp/track2.mp3", "track_index": 2},
            ],
        })
        messages = self._make_messages(tool_result)
        tags, _ = _collect_auto_append_media_tags(messages)
        # Should contain both tracks
        assert "MEDIA:/tmp/track1.mp3" in tags
        assert "MEDIA:/tmp/track2.mp3" in tags

    def test_dedup_against_existing_media_in_response(self):
        """When the agent already included track 1, only track 2 should be appended."""
        from gateway.run import _collect_auto_append_media_tags, _TOOL_MEDIA_RE
        import json as _json

        tool_result = _json.dumps({
            "success": True,
            "audio": "/tmp/track1.mp3",
            "all_tracks": [
                {"audio": "/tmp/track1.mp3", "track_index": 1},
                {"audio": "/tmp/track2.mp3", "track_index": 2},
            ],
        })
        messages = self._make_messages(tool_result)
        tags, _ = _collect_auto_append_media_tags(messages)

        # Simulate the dispatch-site dedup logic
        final_response = "Here is your song!\nMEDIA:/tmp/track1.mp3"
        existing_paths: set = set()
        for match in _TOOL_MEDIA_RE.finditer(final_response):
            existing_paths.add(match.group(1).strip().rstrip('\",}'))
        seen: set = set()
        unique_tags = []
        for tag in tags:
            path = tag.replace("MEDIA:", "", 1).strip()
            if path not in existing_paths and path not in seen:
                seen.add(path)
                unique_tags.append(tag)
        # Only track 2 should be in unique_tags
        assert "MEDIA:/tmp/track2.mp3" in unique_tags
        assert "MEDIA:/tmp/track1.mp3" not in unique_tags

    def test_both_tracks_appended_when_none_in_response(self):
        """When the agent included 0 MEDIA tags, both tracks should be appended."""
        from gateway.run import _collect_auto_append_media_tags, _TOOL_MEDIA_RE
        import json as _json

        tool_result = _json.dumps({
            "success": True,
            "audio": "/tmp/track1.mp3",
            "all_tracks": [
                {"audio": "/tmp/track1.mp3", "track_index": 1},
                {"audio": "/tmp/track2.mp3", "track_index": 2},
            ],
        })
        messages = self._make_messages(tool_result)
        tags, _ = _collect_auto_append_media_tags(messages)

        final_response = "Here is your song!"
        existing_paths: set = set()
        for match in _TOOL_MEDIA_RE.finditer(final_response):
            existing_paths.add(match.group(1).strip().rstrip('\",}'))
        seen: set = set()
        unique_tags = []
        for tag in tags:
            path = tag.replace("MEDIA:", "", 1).strip()
            if path not in existing_paths and path not in seen:
                seen.add(path)
                unique_tags.append(tag)
        assert len(unique_tags) == 2
        assert "MEDIA:/tmp/track1.mp3" in unique_tags
        assert "MEDIA:/tmp/track2.mp3" in unique_tags

    def test_no_duplicates_when_both_in_response(self):
        """When the agent included both tracks, nothing should be appended."""
        from gateway.run import _collect_auto_append_media_tags, _TOOL_MEDIA_RE
        import json as _json

        tool_result = _json.dumps({
            "success": True,
            "audio": "/tmp/track1.mp3",
            "all_tracks": [
                {"audio": "/tmp/track1.mp3", "track_index": 1},
                {"audio": "/tmp/track2.mp3", "track_index": 2},
            ],
        })
        messages = self._make_messages(tool_result)
        tags, _ = _collect_auto_append_media_tags(messages)

        final_response = "Here are both tracks!\nMEDIA:/tmp/track1.mp3\nMEDIA:/tmp/track2.mp3"
        existing_paths: set = set()
        for match in _TOOL_MEDIA_RE.finditer(final_response):
            existing_paths.add(match.group(1).strip().rstrip('\",}'))
        seen: set = set()
        unique_tags = []
        for tag in tags:
            path = tag.replace("MEDIA:", "", 1).strip()
            if path not in existing_paths and path not in seen:
                seen.add(path)
                unique_tags.append(tag)
        assert len(unique_tags) == 0

    def test_failed_result_not_collected(self):
        """Failed tool results should not produce media tags."""
        from gateway.run import _collect_auto_append_media_tags
        import json as _json

        tool_result = _json.dumps({
            "success": False,
            "error": "API key not set",
        })
        messages = self._make_messages(tool_result)
        tags, _ = _collect_auto_append_media_tags(messages)
        assert len(tags) == 0

    def test_tts_still_works_with_new_collector(self):
        """TTS tool results with explicit MEDIA: tags should still be collected."""
        from gateway.run import _collect_auto_append_media_tags

        tool_result = "Generated audio: MEDIA:/tmp/tts_output.ogg"
        messages = self._make_messages(tool_result, tool_name="text_to_speech")
        tags, _ = _collect_auto_append_media_tags(messages)
        assert "MEDIA:/tmp/tts_output.ogg" in tags
