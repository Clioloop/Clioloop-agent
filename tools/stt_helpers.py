"""Pure STT config helpers: language precedence, VAD and safe trim planning."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional


def resolve_stt_language(
    config: Mapping[str, object], provider: str, *, legacy_env: Optional[str] = None
) -> Optional[str]:
    section = config.get(provider)
    candidates = []
    if isinstance(section, Mapping):
        candidates.extend((section.get("language"), section.get("language_code")))
    candidates.extend((config.get("language"), legacy_env))
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def vad_enabled(config: Mapping[str, object], provider: str = "local") -> bool:
    section = config.get(provider)
    value = section.get("vad", True) if isinstance(section, Mapping) else True
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return True if value is None else bool(value)


@dataclass(frozen=True)
class SilenceTrimPlan:
    input_path: str
    output_path: str
    filter: str


def cloud_trim_plan(
    path: str,
    config: Mapping[str, object],
    *,
    threshold_db: float = -42.0,
    duration_seconds: float = 0.25,
) -> Optional[SilenceTrimPlan]:
    """Return an ffmpeg filter plan, never execute a process or network call."""
    enabled = config.get("cloud_trim_silence", True)
    if isinstance(enabled, str):
        enabled = enabled.strip().lower() not in {"0", "false", "no", "off"}
    if not enabled or not path:
        return None
    src = Path(path)
    output = src.with_name(f"{src.stem}-trimmed.m4a")
    noise = max(-96.0, min(-1.0, float(threshold_db)))
    duration = max(0.05, min(5.0, float(duration_seconds)))
    audio_filter = (
        f"silenceremove=start_periods=1:start_duration={duration}:"
        f"start_threshold={noise}dB:stop_periods=-1:stop_duration={duration}:"
        f"stop_threshold={noise}dB"
    )
    return SilenceTrimPlan(str(src), str(output), audio_filter)