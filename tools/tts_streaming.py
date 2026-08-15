"""Provider-neutral foundations for low-latency, interruptible TTS.

This module deliberately does not change Clio's configured TTS provider.  A
registered streamer is used only when it matches the selected provider; every
other provider keeps the existing whole-file/synchronous path via the caller's
fallback callback.
"""
from __future__ import annotations

import re
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Iterable, Iterator, Mapping, Optional

SPEECH_INTERRUPTED_NOTE = (
    "[Note: the user interrupted your previous spoken reply before it finished.]"
)
_THINK_BLOCK_RE = re.compile(r"<think[\s>].*?</think>", re.DOTALL | re.IGNORECASE)
_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+|\n\s*\n")


class SentenceChunker:
    """Incrementally turn arbitrary model deltas into speakable clauses."""

    def __init__(self, min_chars: int = 20) -> None:
        self.min_chars = max(1, int(min_chars))
        self._buffer = ""

    @property
    def pending(self) -> str:
        return self._buffer

    def feed(self, delta: str) -> list[str]:
        self._buffer = _THINK_BLOCK_RE.sub("", self._buffer + (delta or ""))
        if re.search(r"<think(?:\s|>)", self._buffer, re.IGNORECASE) and not re.search(
            r"</think>", self._buffer, re.IGNORECASE
        ):
            return []
        ready: list[str] = []
        search_from = 0
        while match := _BOUNDARY_RE.search(self._buffer, search_from):
            candidate = self._buffer[: match.end()]
            if len(candidate.strip()) < self.min_chars:
                search_from = match.end()
                continue
            ready.append(candidate.strip())
            self._buffer = self._buffer[match.end() :]
            search_from = 0
        return ready

    def flush(self) -> list[str]:
        tail = _THINK_BLOCK_RE.sub("", self._buffer).strip()
        self._buffer = ""
        return [tail] if tail else []


class StreamingTTSProvider(ABC):
    """A provider yielding raw PCM chunks for one sentence."""

    sample_rate = 24000
    channels = 1
    sample_width = 2

    @classmethod
    def available(cls, config: Mapping[str, object]) -> bool:
        return True

    @abstractmethod
    def stream(self, text: str) -> Iterator[bytes]:
        raise NotImplementedError


_PROVIDERS: dict[str, type[StreamingTTSProvider]] = {}


def register_streaming_provider(name: str):
    """Register an optional streaming implementation without changing defaults."""
    key = name.strip().lower()

    def decorate(cls: type[StreamingTTSProvider]) -> type[StreamingTTSProvider]:
        _PROVIDERS[key] = cls
        return cls

    return decorate


def resolve_streaming_provider(
    tts_config: Mapping[str, object], *, provider: Optional[str] = None
) -> Optional[StreamingTTSProvider]:
    """Resolve only the configured provider; never silently change voices."""
    selected = str(provider or tts_config.get("provider") or "").strip().lower()
    streaming = tts_config.get("streaming")
    if isinstance(streaming, Mapping) and streaming.get("enabled") is False:
        return None
    cls = _PROVIDERS.get(selected)
    if cls is None or not cls.available(tts_config):
        return None
    return cls()  # provider-specific config may be captured by custom factories


@dataclass(frozen=True)
class StreamResult:
    sentences: int = 0
    chunks: int = 0
    used_fallback: bool = False
    interrupted: bool = False


def stream_sentences(
    deltas: Iterable[str],
    *,
    provider: Optional[StreamingTTSProvider],
    write_chunk: Callable[[bytes], None],
    fallback: Callable[[str], None],
    interrupted: Optional[threading.Event] = None,
    min_chars: int = 20,
) -> StreamResult:
    """Speak deltas sentence-by-sentence, falling back before audio is emitted.

    Provider failure before a sentence emits PCM invokes ``fallback`` for that
    sentence.  Failure after audible output does not replay it, avoiding doubled
    speech.  The optional event implements barge-in with no provider coupling.
    """
    chunker = SentenceChunker(min_chars=min_chars)
    sentences = chunks = 0
    used_fallback = False
    for delta in deltas:
        for sentence in chunker.feed(delta):
            if interrupted is not None and interrupted.is_set():
                return StreamResult(sentences, chunks, used_fallback, True)
            sentences += 1
            emitted = False
            try:
                if provider is None:
                    raise RuntimeError("no compatible streaming provider")
                for chunk in provider.stream(sentence):
                    if interrupted is not None and interrupted.is_set():
                        return StreamResult(sentences, chunks, used_fallback, True)
                    if chunk:
                        write_chunk(bytes(chunk))
                        chunks += 1
                        emitted = True
            except Exception:
                if not emitted:
                    fallback(sentence)
                    used_fallback = True
    for sentence in chunker.flush():
        if interrupted is not None and interrupted.is_set():
            return StreamResult(sentences, chunks, used_fallback, True)
        sentences += 1
        emitted = False
        try:
            if provider is None:
                raise RuntimeError("no compatible streaming provider")
            for chunk in provider.stream(sentence):
                if chunk:
                    write_chunk(bytes(chunk))
                    chunks += 1
                    emitted = True
        except Exception:
            if not emitted:
                fallback(sentence)
                used_fallback = True
    return StreamResult(sentences, chunks, used_fallback, False)


class InterruptionLatch:
    """Thread-safe, one-shot barge-in state with expiry."""

    def __init__(self, ttl_seconds: float = 120.0) -> None:
        self.ttl_seconds = ttl_seconds
        self._at: Optional[float] = None
        self._lock = threading.Lock()

    def mark(self) -> None:
        with self._lock:
            self._at = time.monotonic()

    def take(self) -> bool:
        with self._lock:
            at, self._at = self._at, None
        return at is not None and time.monotonic() - at < self.ttl_seconds


speech_interrupted = InterruptionLatch()
