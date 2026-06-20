"""
Music Generation Provider ABC
==============================

Defines the pluggable-backend interface for music generation. Providers register
instances via ``PluginContext.register_music_gen_provider()``; the active one
(selected via ``music_gen.provider`` in ``config.yaml``) services every
``music_generate`` tool call.

Providers live in ``<repo>/plugins/music_gen/<name>/`` (built-in, auto-loaded
as ``kind: backend``) or ``~/.clio/plugins/music_gen/<name>/`` (user, opt-in
via ``plugins.enabled``).

Mirrors the ``image_gen`` and ``video_gen`` provider designs so all three
surfaces stay learnable together.

Unified surface
---------------
One tool — ``music_generate`` — covers the full Suno workflow:

- **generate** — text-to-music (description or custom lyrics), instrumental
- **extend** — continue a completed track from a chosen timestamp
- **cover** — re-generate a track in a new style while keeping the melody
- **add_vocals** — layer AI vocals onto an instrumental track
- **stems** — split a track into isolated vocals + instrumental

Response shape
--------------
All providers return a dict built by :func:`success_response` /
:func:`error_response`. Keys:

    success          bool
    audio            str | None      URL or absolute file path (primary track)
    model            str             provider-specific model identifier
    prompt           str              echoed prompt
    action           str              which action was performed
    duration         int             seconds (0 if not applicable)
    instrumental    bool             whether the track is instrumental
    provider         str             provider name (for diagnostics)
    job_id           str             Apiframe job ID (for follow-up actions)
    track_id          str             ID of the primary track
    track_index       int             1 or 2 (which of the parent's tracks)
    all_tracks        list            [{id, audio, title, duration, track_index}, ...]
    parent_job_id     str             only for follow-up actions
    follow_up_hint    str             suggestions for next actions
    error            str              only when success=False
    error_type       str              only when success=False
"""

from __future__ import annotations

import abc
import base64
import datetime
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# Common output formats across providers.
COMMON_OUTPUT_FORMATS: Tuple[str, ...] = ("mp3", "wav")
DEFAULT_OUTPUT_FORMAT = "mp3"

# Common durations (seconds). Providers clamp to their supported range.
# Suno V5 = ~2-4 min clips; Lyria 3 Clip = 30s, Lyria 3 Pro = full songs.
COMMON_DURATIONS: Tuple[int, ...] = (30, 60, 120, 180, 240)
DEFAULT_DURATION = 0  # 0 = provider default

# Supported actions
SUPPORTED_ACTIONS: Tuple[str, ...] = (
    "generate",
    "extend",
    "cover",
    "add_vocals",
    "stems",
)


# ---------------------------------------------------------------------------
# ABC
# ---------------------------------------------------------------------------


class MusicGenProvider(abc.ABC):
    """Abstract base class for a music generation backend.

    Subclasses must implement :meth:`generate`. Everything else has sane
    defaults — override only what your provider needs.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Stable short identifier used in ``music_gen.provider`` config.

        Lowercase, no spaces. Examples: ``apiframe``, ``google_lyria``.
        """

    @property
    def display_name(self) -> str:
        """Human-readable label shown in ``clio tools``. Defaults to ``name.title()``."""
        return self.name.title()

    def is_available(self) -> bool:
        """Return True when this provider can service calls.

        Typically checks for a required API key and optional-dependency
        import. Default: True.
        """
        return True

    def list_models(self) -> List[Dict[str, Any]]:
        """Return catalog entries for ``clio tools`` model picker.

        Each entry::

            {
                "id": "suno-v5",                    # required
                "display": "Suno V5",              # optional; defaults to id
                "speed": "~30s",                   # optional
                "strengths": "Full songs, vocals", # optional
                "price": "$0.10/song",             # optional
                "max_duration": 240,               # optional, seconds
            }

        Default: empty list (provider has no user-selectable models).
        """
        return []

    def get_setup_schema(self) -> Dict[str, Any]:
        """Return provider metadata for the ``clio tools`` picker."""
        return {
            "name": self.display_name,
            "badge": "",
            "tag": "",
            "env_vars": [],
        }

    def default_model(self) -> Optional[str]:
        """Return the default model id, or None if not applicable."""
        models = self.list_models()
        if models:
            return models[0].get("id")
        return None

    def capabilities(self) -> Dict[str, Any]:
        """Return what this provider supports.

        Returned dict (all keys optional)::

            {
                "max_duration": 240,            # seconds
                "min_duration": 5,
                "supports_lyrics": True,         # custom lyrics input
                "supports_instrumental": True,   # instrumental-only mode
                "supports_extend": True,         # extend action
                "supports_cover": True,          # cover action
                "supports_add_vocals": True,    # add_vocals action
                "supports_stems": True,          # stems action
                "supports_style": True,          # style/negative_tags
                "supports_vocal_gender": True,   # male/female selection
                "supports_title": True,          # custom track title
                "supports_style_weight": True,   # style_weight param
                "supports_weirdness": True,      # weirdness_constraint param
                "supports_auto_lyrics": True,    # auto_lyrics param
                "supports_audio_weight": True,   # cover audio_weight param
                "supports_continue_at": True,    # extend continue_at param
                "output_formats": ["mp3"],
            }

        Used by the tool layer for soft validation and by ``clio tools``
        for the picker. Default: minimal.
        """
        return {
            "max_duration": 240,
            "min_duration": 5,
            "supports_lyrics": True,
            "supports_instrumental": True,
            "supports_extend": True,
            "supports_cover": True,
            "supports_add_vocals": True,
            "supports_stems": True,
            "supports_style": True,
            "supports_vocal_gender": True,
            "supports_title": True,
            "supports_style_weight": True,
            "supports_weirdness": True,
            "supports_auto_lyrics": True,
            "supports_audio_weight": True,
            "supports_continue_at": True,
            "output_formats": list(COMMON_OUTPUT_FORMATS),
        }

    @abc.abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        action: str = "generate",
        # Generation params
        lyrics: Optional[str] = None,
        instrumental: Optional[bool] = None,
        style: Optional[str] = None,
        negative_tags: Optional[str] = None,
        vocal_gender: Optional[str] = None,
        title: Optional[str] = None,
        style_weight: Optional[float] = None,
        weirdness: Optional[float] = None,
        auto_lyrics: Optional[bool] = None,
        # Follow-up action params
        parent_job_id: Optional[str] = None,
        track_index: Optional[int] = None,
        track_id: Optional[str] = None,
        # Extend-specific
        continue_at: Optional[int] = None,
        # Cover-specific
        audio_weight: Optional[float] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Generate music from a text prompt or perform a follow-up action.

        ``action`` determines what the provider does:

        - ``"generate"`` — text-to-music or custom lyrics → 2 new tracks
        - ``"extend"`` — continue a completed track from a timestamp → 2 new tracks
        - ``"cover"`` — re-generate in a new style, keeping melody → 2 new tracks
        - ``"add_vocals"`` — layer vocals onto an instrumental → 2 new tracks
        - ``"stems"`` — split into isolated vocals + instrumental → 2 files

        For ``generate`` and ``add_vocals``, ``prompt`` is required.
        For follow-up actions (extend/cover/add_vocals/stems),
        ``parent_job_id`` and one of ``track_index``/``track_id`` are required.

        Implementations should return the dict from :func:`success_response`
        or :func:`error_response`. ``kwargs`` may contain forward-compat
        parameters future versions of the schema will expose —
        implementations MUST ignore unknown keys (no TypeError).
        """


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _music_cache_dir() -> Path:
    """Return ``$CLIO_HOME/cache/music/``, creating parents as needed."""
    from clio_constants import get_clio_home

    path = get_clio_home() / "cache" / "music"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_b64_audio(
    b64_data: str,
    *,
    prefix: str = "clio_music",
    extension: str = "mp3",
) -> Path:
    """Decode base64 audio data and write it under ``$CLIO_HOME/cache/music/``.

    Returns the absolute :class:`Path` to the saved file.

    Filename format: ``<prefix>_<YYYYMMDD_HHMMSS>_<short-uuid>.<ext>``.
    """
    raw = base64.b64decode(b64_data)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    short = uuid.uuid4().hex[:8]
    path = _music_cache_dir() / f"{prefix}_{ts}_{short}.{extension}"
    path.write_bytes(raw)
    return path


def save_bytes_audio(
    raw: bytes,
    *,
    prefix: str = "clio_music",
    extension: str = "mp3",
) -> Path:
    """Write raw audio bytes (e.g. an HTTP download body) to the cache."""
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    short = uuid.uuid4().hex[:8]
    path = _music_cache_dir() / f"{prefix}_{ts}_{short}.{extension}"
    path.write_bytes(raw)
    return path


def save_url_audio(
    url: str,
    *,
    prefix: str = "clio_music",
    timeout: float = 120.0,
    max_bytes: int = 50 * 1024 * 1024,
) -> Path:
    """Download an audio URL and write it under ``$CLIO_HOME/cache/music/``.

    Used by providers whose API returns an ephemeral URL instead of inline
    base64 — those URLs frequently expire before a downstream consumer
    (Telegram ``send_audio``, browser fetch) can resolve them, so we
    materialise the bytes locally at tool-completion time.

    Returns the absolute :class:`Path` to the saved file.  Raises on any
    network / HTTP / oversize / non-audio-content-type error so callers can
    fall back to returning the bare URL with a clear error message.
    """
    import requests

    response = requests.get(url, timeout=timeout, stream=True)
    response.raise_for_status()

    # Infer extension from the response content-type, falling back to the
    # URL suffix.  Defaults to ``mp3``.
    content_type = (response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
    extension = _AUDIO_CONTENT_TYPES.get(content_type)
    if extension is None:
        url_path = url.split("?", 1)[0].lower()
        for ext in ("mp3", "wav", "ogg", "m4a", "flac", "aac"):
            if url_path.endswith(f".{ext}"):
                extension = ext
                break
    if extension is None:
        extension = "mp3"

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    short = uuid.uuid4().hex[:8]
    path = _music_cache_dir() / f"{prefix}_{ts}_{short}.{extension}"

    bytes_written = 0
    with path.open("wb") as fh:
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            bytes_written += len(chunk)
            if bytes_written > max_bytes:
                fh.close()
                try:
                    path.unlink()
                except OSError:
                    pass
                raise ValueError(
                    f"Audio at {url} exceeds {max_bytes // (1024 * 1024)}MB cap; refusing to cache."
                )
            fh.write(chunk)

    if bytes_written == 0:
        try:
            path.unlink()
        except OSError:
            pass
        raise ValueError(f"Audio at {url} returned 0 bytes; refusing to cache.")

    return path


_AUDIO_CONTENT_TYPES = {
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/wave": "wav",
    "audio/x-wav": "wav",
    "audio/ogg": "ogg",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/flac": "flac",
    "audio/aac": "aac",
    "application/octet-stream": None,  # ambiguous — fall back to URL suffix
}


def success_response(
    *,
    audio: str,
    model: str,
    prompt: str,
    action: str = "generate",
    duration: int = 0,
    instrumental: bool = False,
    provider: str,
    job_id: str = "",
    track_id: str = "",
    track_index: int = 0,
    all_tracks: Optional[List[Dict[str, Any]]] = None,
    parent_job_id: str = "",
    follow_up_hint: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a uniform success response dict.

    ``audio`` may be an HTTP URL or an absolute filesystem path.
    ``all_tracks`` is a list of dicts with keys: id, audio, title, duration,
    track_index.
    """
    payload: Dict[str, Any] = {
        "success": True,
        "audio": audio,
        "model": model,
        "prompt": prompt,
        "action": action,
        "duration": int(duration) if duration else 0,
        "instrumental": bool(instrumental),
        "provider": provider,
        "job_id": job_id,
        "track_id": track_id,
        "track_index": int(track_index) if track_index else 0,
        "all_tracks": all_tracks or [],
        "parent_job_id": parent_job_id,
        "follow_up_hint": follow_up_hint,
    }
    if extra:
        for k, v in extra.items():
            payload.setdefault(k, v)
    return payload


def error_response(
    *,
    error: str,
    error_type: str = "provider_error",
    provider: str = "",
    model: str = "",
    prompt: str = "",
    action: str = "",
) -> Dict[str, Any]:
    """Build a uniform error response dict."""
    return {
        "success": False,
        "audio": None,
        "error": error,
        "error_type": error_type,
        "model": model,
        "prompt": prompt,
        "action": action,
        "provider": provider,
    }