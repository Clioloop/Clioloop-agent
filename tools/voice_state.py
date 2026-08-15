"""Small state machine shared by voice surfaces (CLI, TUI and plugins)."""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class VoicePhase(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    GENERATING = "generating"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"


def normalize_stop_phrase(value: str) -> str:
    return re.sub(r"[\s.!?,;:]+$", "", (value or "").strip().casefold())


def is_stop_phrase(transcript: str, phrases: Iterable[str] = ("stop",)) -> bool:
    """Whole-utterance matching prevents 'do not stop' false positives."""
    normalized = normalize_stop_phrase(transcript)
    return bool(normalized) and normalized in {
        normalize_stop_phrase(phrase) for phrase in phrases if normalize_stop_phrase(phrase)
    }


@dataclass
class VoiceTurnState:
    stop_phrases: tuple[str, ...] = ("stop",)
    phase: VoicePhase = VoicePhase.IDLE
    _cancel: threading.Event = field(default_factory=threading.Event, repr=False)
    interruption_reason: str = ""

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def transition(self, phase: VoicePhase) -> None:
        if self.cancelled and phase not in (VoicePhase.IDLE, VoicePhase.INTERRUPTED):
            return
        self.phase = phase

    def barge_in(self, transcript: str = "") -> bool:
        self.interruption_reason = "stop_phrase" if is_stop_phrase(
            transcript, self.stop_phrases
        ) else "barge_in"
        self._cancel.set()
        self.phase = VoicePhase.INTERRUPTED
        return self.interruption_reason == "stop_phrase"

    def reset(self) -> None:
        self._cancel.clear()
        self.interruption_reason = ""
        self.phase = VoicePhase.IDLE
