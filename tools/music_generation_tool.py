#!/usr/bin/env python3
"""
Music Generation Tool
======================

Single ``music_generate`` tool that dispatches to a plugin-registered
music generation provider. Mirrors the ``video_generate`` design:

- ``agent/music_gen_provider.py`` defines the :class:`MusicGenProvider` ABC.
- ``agent/music_gen_registry.py`` holds the active providers (populated by
  plugins at import time).
- Each provider lives under ``plugins/music_gen/<name>/``.

The tool itself is intentionally backend-agnostic and ships **no in-tree
provider** — turn on a backend by enabling a plugin (``clio plugins
enable music_gen/<name>``) and selecting it in ``clio tools`` → Music
Generation.

Unified surface
---------------
One tool covers the full Suno workflow:

    action                   "generate" | "extend" | "cover" | "add_vocals" | "stems"
                             default: "generate"

For action="generate":
    prompt                   text instruction or song description (required)
    lyrics                   custom lyrics with [Verse]/[Chorus] tags
    instrumental             bool — generate instrumental-only (no vocals)
    model                    "suno-v5" | "suno-v5_5"
    style                    genre/style tags (e.g. "synthwave, electronic")
    negative_tags            styles to avoid
    vocal_gender             "m" (male) or "f" (female)
    title                    custom track title
    style_weight             0.0–1.0 — style adherence
    weirdness                0.0–1.0 — creativity level
    auto_lyrics              bool — auto-generate lyrics (custom mode only)

For action="extend"|"cover"|"add_vocals"|"stems":
    parent_job_id            job ID from a previous music_generate response
    track_index              1 or 2 (which track to act on)
    track_id                 track ID (alternative to track_index)
    prompt                   lyrics/description (for extend/cover/add_vocals)
    style                    style tags (extend/cover/add_vocals)
    negative_tags            styles to avoid (extend/cover/add_vocals)
    title                    title for the result
    continue_at              timestamp for extend (where extension starts)
    audio_weight             0.0–1.0 for cover (how closely to follow source)

Providers ignore parameters they do not support. The tool layer does
**lightweight** validation and lets each provider do its own clamping
inside :meth:`MusicGenProvider.generate`.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from agent.music_gen_provider import (
    COMMON_OUTPUT_FORMATS,
    DEFAULT_OUTPUT_FORMAT,
    SUPPORTED_ACTIONS,
    error_response,
)
from tools.registry import registry, tool_error

logger = logging.getLogger(__name__)


MUSIC_GENERATE_SCHEMA: Dict[str, Any] = {
    "name": "music_generate",
    # Placeholder — the real description is built dynamically at
    # get_tool_definitions() time so it reflects the active backend's
    # actual capabilities.
    "description": "(rebuilt at get_definitions() time — see _build_dynamic_music_schema)",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": list(SUPPORTED_ACTIONS),
                "description": (
                    "What to do: 'generate' creates a new song, 'extend' continues "
                    "a completed track from a timestamp, 'cover' re-creates a track "
                    "in a new style, 'add_vocals' layers vocals onto an instrumental, "
                    "'stems' splits a track into vocals + instrumental. "
                    "Default: 'generate'."
                ),
                "default": "generate",
            },
            "prompt": {
                "type": "string",
                "description": (
                    "Text instruction describing the desired music: genre, "
                    "mood, instrumentation, style, tempo, etc. Be detailed and "
                    "descriptive — e.g. 'An epic cinematic orchestral piece "
                    "about a journey home, starts with solo piano, builds to "
                    "a massive wall of sound.' For action='add_vocals', this "
                    "is the lyrics to sing. For action='extend', this is the "
                    "extension content (lyrics or description)."
                ),
            },
            "lyrics": {
                "type": "string",
                "description": (
                    "Custom lyrics. Use section tags like "
                    "[Verse 1], [Chorus], [Bridge] to guide structure. "
                    "When provided for action='generate', switches to "
                    "custom mode (prompt=lyrics, max 5000 chars). "
                    "For follow-up actions, serves as the prompt/lyrics."
                ),
            },
            "instrumental": {
                "type": "boolean",
                "description": (
                    "When true, generate instrumental-only music "
                    "with no vocals. Only for action='generate'."
                ),
            },
            "model": {
                "type": "string",
                "description": (
                    "Model override: 'suno-v5' or 'suno-v5_5'. "
                    "Defaults to suno-v5_5."
                ),
            },
            "style": {
                "type": "string",
                "description": (
                    "Music style/genre tags (max 1000 chars). "
                    "e.g. 'synthwave, electronic, upbeat, 80s'. "
                    "For action='cover', this is the main lever for the "
                    "new style. For action='extend', sets the style of "
                    "the extension segment."
                ),
            },
            "negative_tags": {
                "type": "string",
                "description": (
                    "Styles to avoid (max 500 chars). "
                    "e.g. 'country, jazz, heavy metal'."
                ),
            },
            "vocal_gender": {
                "type": "string",
                "enum": ["m", "f"],
                "description": (
                    "Vocal gender: 'm' (male) or 'f' (female). "
                    "Only when vocals are generated. Ignored for instrumental."
                ),
            },
            "title": {
                "type": "string",
                "description": (
                    "Custom track title (max 80 chars). "
                    "If omitted, the provider auto-generates a title."
                ),
            },
            "style_weight": {
                "type": "number",
                "description": (
                    "Style adherence weight 0.0–1.0. Higher = more closely "
                    "follows the style tags. Only for action='generate'."
                ),
            },
            "weirdness": {
                "type": "number",
                "description": (
                    "Creativity/randomness level 0.0–1.0. Higher = more "
                    "experimental/unusual output. Only for action='generate'."
                ),
            },
            "auto_lyrics": {
                "type": "boolean",
                "description": (
                    "When true, auto-generate lyrics from the prompt. "
                    "Only works in custom mode (when lyrics param is also set). "
                    "If lyrics are provided and auto_lyrics is false, the "
                    "lyrics are used as-is."
                ),
            },
            # Follow-up action params
            "parent_job_id": {
                "type": "string",
                "description": (
                    "Required for action='extend', 'cover', 'add_vocals', "
                    "or 'stems'. The job_id from a previous music_generate "
                    "response. Identifies the completed generation to act on."
                ),
            },
            "track_index": {
                "type": "integer",
                "description": (
                    "For follow-up actions: which track from the parent "
                    "job to act on (1 or 2). Provide this OR track_id."
                ),
            },
            "track_id": {
                "type": "string",
                "description": (
                    "For follow-up actions: track ID from the parent's "
                    "all_tracks[].id. Provide this OR track_index."
                ),
            },
            # Extend-specific
            "continue_at": {
                "type": "integer",
                "description": (
                    "For action='extend': timestamp in seconds where the "
                    "extension begins. Default: end of the source track. "
                    "Must be less than the track's duration."
                ),
            },
            # Cover-specific
            "audio_weight": {
                "type": "number",
                "description": (
                    "For action='cover': 0.0–1.0, how closely the cover "
                    "follows the source audio. Higher = closer to original "
                    "melody; lower = more creative freedom."
                ),
            },
            "confirmed": {
                "type": "boolean",
                "description": (
                    "MUST be true to proceed with action='generate'. "
                    "VERY IMPORTANT: Before setting this to true, you "
                    "MUST ask the user to confirm all generation details "
                    "(model, mode, instrumental, style, vocal gender, "
                    "title) DIRECTLY IN YOUR RESPONSE TEXT — NOT through "
                    "the clarify tool. Present the options as a list in "
                    "your normal chat reply, wait for the user to respond, "
                    "THEN call with confirmed=true. If the user already "
                    "specified everything in their initial request, you "
                    "may set true immediately. Ignored for follow-up "
                    "actions (extend, cover, add_vocals, stems)."
                ),
                "default": False,
            },
        },
        "required": ["action", "confirmed"],
    },
}


# ---------------------------------------------------------------------------
# Config readers (mirror video_generation_tool.py)
# ---------------------------------------------------------------------------


def _read_music_gen_section() -> Dict[str, Any]:
    try:
        from clio_cli.config import load_config

        cfg = load_config()
        section = cfg.get("music_gen") if isinstance(cfg, dict) else None
        return section if isinstance(section, dict) else {}
    except Exception as exc:
        logger.debug("Could not read music_gen config: %s", exc)
        return {}


def _read_configured_music_provider() -> Optional[str]:
    value = _read_music_gen_section().get("provider")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _read_configured_music_model() -> Optional[str]:
    value = _read_music_gen_section().get("model")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


# ---------------------------------------------------------------------------
# Availability check
# ---------------------------------------------------------------------------


def check_music_generation_requirements() -> bool:
    """Return True when at least one registered provider reports available.

    Triggers plugin discovery (idempotent) so user-installed plugins are
    visible to the toolset gate.
    """
    try:
        from agent.music_gen_registry import list_providers
        from clio_cli.plugins import _ensure_plugins_discovered

        _ensure_plugins_discovered()
        for provider in list_providers():
            try:
                if provider.is_available():
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def _resolve_active_provider():
    """Return the active provider object or None.

    Forces plugin discovery before checking the registry — handles cases
    where a long-lived session was started before a plugin was installed.
    """
    try:
        from agent.music_gen_registry import get_active_provider
        from clio_cli.plugins import _ensure_plugins_discovered

        _ensure_plugins_discovered()
        provider = get_active_provider()
        if provider is None:
            _ensure_plugins_discovered(force=True)
            provider = get_active_provider()
        return provider
    except Exception as exc:
        logger.debug("music_gen provider resolution failed: %s", exc)
        return None


def _missing_provider_error(configured: Optional[str]) -> str:
    if configured:
        msg = (
            f"music_gen.provider='{configured}' is set but no plugin "
            f"registered that name. Run `clio plugins list` to see "
            f"installed music gen backends, or `clio tools` → Music "
            f"Generation to pick one."
        )
        return json.dumps(error_response(
            error=msg, error_type="provider_not_registered",
            provider=configured,
        ))
    msg = (
        "No music generation backend is configured. Run `clio tools` → "
        "Music Generation to enable one."
    )
    return json.dumps(error_response(
        error=msg, error_type="no_provider_configured",
    ))


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


def _coerce_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"true", "1", "yes", "on"}:
            return True
        if v in {"false", "0", "no", "off"}:
            return False
    return None


def _coerce_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _handle_music_generate(args: Dict[str, Any], **_kw: Any) -> str:
    action = (args.get("action") or "generate").strip().lower() or "generate"

    # Validate action
    if action not in SUPPORTED_ACTIONS:
        return tool_error(
            f"Invalid action '{action}'. Supported: {', '.join(SUPPORTED_ACTIONS)}"
        )

    prompt = (args.get("prompt") or "").strip()
    lyrics = _coerce_str(args.get("lyrics"))
    instrumental = _coerce_bool(args.get("instrumental"))
    model_override = _coerce_str(args.get("model"))
    style = _coerce_str(args.get("style"))
    negative_tags = _coerce_str(args.get("negative_tags"))
    vocal_gender = _coerce_str(args.get("vocal_gender"))
    title = _coerce_str(args.get("title"))
    style_weight = _coerce_float(args.get("style_weight"))
    weirdness = _coerce_float(args.get("weirdness"))
    auto_lyrics = _coerce_bool(args.get("auto_lyrics"))
    parent_job_id = _coerce_str(args.get("parent_job_id"))
    track_index = _coerce_int(args.get("track_index"))
    track_id = _coerce_str(args.get("track_id"))
    continue_at = _coerce_int(args.get("continue_at"))
    audio_weight = _coerce_float(args.get("audio_weight"))

    # Validate required params based on action
    if action == "generate":
        # Enforce confirmation protocol at code level — prevents models from
        # skipping the confirmation step described in the tool description.
        confirmed = _coerce_bool(args.get("confirmed"))
        if not confirmed:
            return tool_error(
                "⚠️ CONFIRMATION REQUIRED BEFORE GENERATING MUSIC.\n\n"
                "You MUST confirm the following details with the user "
                "DIRECTLY IN YOUR RESPONSE TEXT (NOT through the clarify "
                "tool) before calling this tool with confirmed=true:\n\n"
                "  1. Model: Suno V5 or V5.5?\n"
                "  2. Mode: description mode (auto lyrics) or custom lyrics mode?\n"
                "  3. Instrumental or with vocals?\n"
                "  4. Style/genre tags?\n"
                "  5. Vocal gender (if vocals): male or female?\n"
                "  6. Title for the track?\n\n"
                "Ask these questions in your normal chat response, wait "
                "for the user's answers, THEN re-call with confirmed=true.\n\n"
                "If the user has already specified all details in their "
                "initial request, you may set confirmed=true immediately."
            )
        if not prompt and not lyrics:
            return tool_error(
                "prompt (or lyrics) is required for action='generate'"
            )
    elif action in ("extend", "cover", "add_vocals", "stems"):
        # All follow-up actions require parent_job_id + track reference
        if not parent_job_id:
            return tool_error(
                f"parent_job_id is required for action='{action}'"
            )
        if track_index is None and not track_id:
            return tool_error(
                f"Either track_index (1 or 2) or track_id is required for action='{action}'"
            )
        # add_vocals additionally requires prompt (lyrics to sing)
        if action == "add_vocals" and not prompt and not lyrics:
            return tool_error(
                "prompt (or lyrics) is required for action='add_vocals' — "
                "it's the lyrics to sing."
            )
    # extend, cover, stems don't strictly require prompt (Suno can continue
    # from source material), but extend/cover can use it optionally.

    # Validate vocal_gender
    if vocal_gender and vocal_gender not in ("m", "f"):
        return tool_error(
            f"Invalid vocal_gender '{vocal_gender}'. Must be 'm' or 'f'."
        )

    # Resolve the active provider.
    configured = _read_configured_music_provider()
    provider = _resolve_active_provider()
    if provider is None:
        return _missing_provider_error(configured)

    # Resolve model: explicit arg wins, then config, then provider default.
    model = model_override or _read_configured_music_model() or provider.default_model()

    kwargs: Dict[str, Any] = {
        "model": model,
        "action": action,
        "lyrics": lyrics,
        "instrumental": instrumental,
        "style": style,
        "negative_tags": negative_tags,
        "vocal_gender": vocal_gender,
        "title": title,
        "style_weight": style_weight,
        "weirdness": weirdness,
        "auto_lyrics": auto_lyrics,
        "parent_job_id": parent_job_id,
        "track_index": track_index,
        "track_id": track_id,
        "continue_at": continue_at,
        "audio_weight": audio_weight,
    }
    # Drop None entries so providers see clean defaults.
    kwargs = {k: v for k, v in kwargs.items() if v is not None}

    try:
        result = provider.generate(prompt=prompt, **kwargs)
    except TypeError as exc:
        logger.warning(
            "music_gen provider '%s' rejected kwargs (signature too narrow): %s",
            getattr(provider, "name", "?"), exc,
        )
        return json.dumps(error_response(
            error=(
                f"Provider '{getattr(provider, 'name', '?')}' signature is "
                f"out of date with the music_generate schema. Report this "
                f"to the plugin author."
            ),
            error_type="provider_contract",
            provider=getattr(provider, "name", ""),
            model=model or "",
            prompt=prompt,
            action=action,
        ))
    except Exception as exc:
        logger.warning(
            "music_gen provider '%s' raised: %s",
            getattr(provider, "name", "?"), exc,
        )
        return json.dumps(error_response(
            error=f"Provider '{getattr(provider, 'name', '?')}' error: {exc}",
            error_type="provider_exception",
            provider=getattr(provider, "name", ""),
            model=model or "",
            prompt=prompt,
            action=action,
        ))

    if not isinstance(result, dict):
        return json.dumps(error_response(
            error="Provider returned a non-dict result",
            error_type="provider_contract",
            provider=getattr(provider, "name", ""),
            model=model or "",
            prompt=prompt,
            action=action,
        ))

    return json.dumps(result)


# ---------------------------------------------------------------------------
# Dynamic schema — reflect the active backend's actual capabilities
# ---------------------------------------------------------------------------


_GENERIC_DESCRIPTION = (
    "Generate high-quality music from a text prompt using the user's "
    "configured music generation backend (Suno V5 via Apiframe). Supports "
    "5 actions:\n"
    "• generate — create a new song from a text description or custom lyrics\n"
    "• extend — continue a completed track from a chosen timestamp\n"
    "• cover — re-generate a track in a new style while keeping the melody\n"
    "• add_vocals — layer AI vocals onto an instrumental track\n"
    "• stems — split a track into isolated vocals + instrumental\n\n"
    "FINE-TUNING (action='generate'): style tags, negative tags, vocal "
    "gender (m/f), title, style_weight (0-1), weirdness (0-1), auto_lyrics.\n\n"
    "FOLLOW-UP ACTIONS: Pass parent_job_id + track_index (1 or 2) from a "
    "previous response. Extend takes continue_at (timestamp). Cover takes "
    "audio_weight (0-1). Add vocals requires prompt (lyrics to sing).\n\n"
    "⚠️ COST: Each action costs ~$0.11 (direct) or €0.20 (managed portal). "
    "Suno returns 2 tracks per action. Both are in the `all_tracks` array "
    "with their file paths in `all_tracks[].audio`. You MUST deliver BOTH "
    "tracks to the user by including a separate MEDIA: tag for each track's "
    "audio path in your response.\n"
    "Example: MEDIA:/path/to/track1.mp3 and MEDIA:/path/to/track2.mp3\n\n"
    "██████████████████████████████████████████████████████████████████████\n"
    "███  MANDATORY CONFIRMATION PROTOCOL — READ THIS CAREFULLY  ███████████\n"
    "██████████████████████████████████████████████████████████████████████\n\n"
    "THIS IS VERY VERY VERY IMPORTANT. FAILURE TO FOLLOW THIS PROTOCOL "
    "WILL RESULT IN A TOOL ERROR AND WASTED TIME.\n\n"
    "BEFORE calling music_generate with action='generate', YOU MUST "
    "CONFIRM ALL OF THE FOLLOWING DETAILS WITH THE USER:\n\n"
    "  1. Model: Suno V5 or V5.5?\n"
    "  2. Mode: description mode (auto lyrics) or custom lyrics mode?\n"
    "  3. Instrumental or with vocals?\n"
    "  4. Style/genre tags (e.g. 'synthwave, upbeat, 80s')?\n"
    "  5. Vocal gender (if vocals): male or female?\n"
    "  6. Title for the track?\n\n"
    "HOW TO ASK — THIS IS CRITICAL:\n"
    "  • Ask the user DIRECTLY IN YOUR RESPONSE TEXT. Present the options "
    "as a clear list and let the user reply.\n"
    "  • DO NOT USE THE clarify TOOL FOR THIS. The confirmation must "
    "happen in your normal chat response, NOT through the clarify tool.\n"
    "  • DO NOT call music_generate until the user has confirmed.\n"
    "  • DO NOT set confirmed=true until you have presented the details "
    "and the user has agreed.\n\n"
    "EXCEPTION: If the user has ALREADY specified ALL of the above details "
    "in their initial request, you may set confirmed=true immediately "
    "without asking again.\n\n"
    "IF YOU CALL WITH confirmed=false OR OMIT IT, THE TOOL WILL RETURN "
    "AN ERROR. You MUST ask the user first, get their answers, THEN call "
    "with confirmed=true.\n\n"
    "For follow-up actions (extend, cover, add_vocals, stems), briefly "
    "describe what will happen and confirm with the user in your "
    "response text before calling.\n\n"
    "The backend and model family are user-configured via `clio tools` → "
    "Music Generation. Generations typically take 30 seconds to 2 minutes — "
    "the call blocks until the audio is ready. Returns either an HTTP URL "
    "or an absolute file path in the `audio` field (Track 1) and in "
    "`all_tracks[].audio` (all tracks); display each with markdown and "
    "include a MEDIA: tag for EVERY track to deliver all audio files to "
    "the user. The response includes job_id and all_tracks for chaining "
    "follow-up actions (extend, cover, stems)."
)


def _build_dynamic_music_schema() -> Dict[str, Any]:
    """Build a description that reflects the active backend's actual surface.

    Cheap: reads config (already memoized by the caller), asks the active
    provider for `capabilities()` and the active model's catalog entry,
    and formats a few lines of prose. Falls back to the generic
    description when no provider is configured or registered.
    """
    parts: List[str] = [_GENERIC_DESCRIPTION]

    configured = _read_configured_music_provider()
    configured_model = _read_configured_music_model()

    if not configured:
        parts.append(
            "\nNo music backend is configured. Calls will return an error "
            "until the user picks one via `clio tools` → Music Generation."
        )
        return {"description": "\n".join(parts)}

    try:
        from agent.music_gen_registry import get_provider
        from clio_cli.plugins import _ensure_plugins_discovered

        _ensure_plugins_discovered()
        provider = get_provider(configured)
    except Exception:
        provider = None

    if provider is None:
        parts.append(
            f"\nActive backend: {configured} (plugin not yet loaded — the "
            f"tool will retry discovery on first call)."
        )
        return {"description": "\n".join(parts)}

    try:
        caps = provider.capabilities() or {}
    except Exception:
        caps = {}
    try:
        models = provider.list_models() or []
    except Exception:
        models = []

    active_model = configured_model or (models[0].get("id") if models else "")
    active_model_meta = None
    for m in models:
        if m.get("id") == active_model:
            active_model_meta = m
            break

    parts.append(f"\nActive backend: {provider.display_name} ({provider.name})")
    if active_model:
        parts.append(f"Active model: {active_model}")
    if active_model_meta:
        if active_model_meta.get("display"):
            parts.append(f"  {active_model_meta['display']}")
        if active_model_meta.get("speed"):
            parts.append(f"  Speed: {active_model_meta['speed']}")
        if active_model_meta.get("strengths"):
            parts.append(f"  Strengths: {active_model_meta['strengths']}")
        if active_model_meta.get("price"):
            parts.append(f"  Price: {active_model_meta['price']}")
        if active_model_meta.get("max_duration"):
            parts.append(f"  Max duration: {active_model_meta['max_duration']}s")

    # Capabilities
    if caps:
        max_dur = caps.get("max_duration")
        min_dur = caps.get("min_duration")
        if max_dur and min_dur:
            parts.append(f"- Duration range: {min_dur}-{max_dur}s")
        elif max_dur:
            parts.append(f"- Max duration: {max_dur}s")

        if caps.get("supports_lyrics"):
            parts.append("- Custom lyrics: supported (use `lyrics` param with [Verse]/[Chorus] tags)")
        if caps.get("supports_instrumental"):
            parts.append("- Instrumental-only: supported (use `instrumental=true`)")
        if caps.get("supports_extend"):
            parts.append("- Extend action: supported (continue track from timestamp)")
        if caps.get("supports_cover"):
            parts.append("- Cover action: supported (re-style a track)")
        if caps.get("supports_add_vocals"):
            parts.append("- Add vocals action: supported (layer vocals on instrumental)")
        if caps.get("supports_stems"):
            parts.append("- Stems action: supported (split into vocals + instrumental)")
        if caps.get("supports_style"):
            parts.append("- Style/negative tags: supported")
        if caps.get("supports_vocal_gender"):
            parts.append("- Vocal gender selection: supported (m/f)")
        if caps.get("supports_title"):
            parts.append("- Custom title: supported")
        if caps.get("supports_style_weight"):
            parts.append("- Style weight: supported (0.0-1.0)")
        if caps.get("supports_weirdness"):
            parts.append("- Weirdness/creativity: supported (0.0-1.0)")

        formats = caps.get("output_formats")
        if formats:
            parts.append(f"- Output formats: {', '.join(formats)}")

    # List all available models if more than one
    if len(models) > 1:
        parts.append("\nAvailable models:")
        for m in models:
            marker = " ← active" if m.get("id") == active_model else ""
            display = m.get("display", m.get("id", "?"))
            speed = m.get("speed", "")
            price = m.get("price", "")
            parts.append(f"  {display} ({speed}, {price}){marker}")

    return {"description": "\n".join(parts)}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


registry.register(
    name="music_generate",
    toolset="music_gen",
    schema=MUSIC_GENERATE_SCHEMA,
    handler=_handle_music_generate,
    check_fn=check_music_generation_requirements,
    requires_env=[],
    is_async=False,
    emoji="🎵",
    dynamic_schema_overrides=_build_dynamic_music_schema,
)