"""Wake-provider registry and profile-aware phrase routing abstraction."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable, Mapping, Optional


@dataclass(frozen=True)
class WakeMatch:
    phrase: str
    profile: str = "default"
    confidence: float = 1.0


class WakeProvider(ABC):
    @abstractmethod
    def feed(self, pcm: bytes) -> Optional[WakeMatch]:
        """Consume mono 16-kHz PCM and return a match when detected."""

    def close(self) -> None:
        return None


_WAKE_PROVIDERS: dict[str, type[WakeProvider]] = {}


def register_wake_provider(name: str, provider: type[WakeProvider]) -> None:
    _WAKE_PROVIDERS[name.strip().lower()] = provider


def create_wake_provider(name: str, **kwargs) -> WakeProvider:
    try:
        cls = _WAKE_PROVIDERS[name.strip().lower()]
    except KeyError as exc:
        raise ValueError(f"unknown wake provider: {name}") from exc
    return cls(**kwargs)


def route_wake_phrase(
    heard: str,
    profile_phrases: Mapping[str, str],
    *,
    default_profile: str = "default",
) -> WakeMatch:
    normalized = " ".join((heard or "").casefold().split())
    for profile, phrase in profile_phrases.items():
        if normalized == " ".join(str(phrase).casefold().split()):
            return WakeMatch(phrase=str(phrase), profile=str(profile))
    return WakeMatch(phrase=heard, profile=default_profile, confidence=0.0)


def profile_phrase_map(rows: Iterable[Mapping[str, object]]) -> dict[str, str]:
    """Shape-guard profile config without reading or mutating real profiles."""
    result: dict[str, str] = {}
    for row in rows:
        if row.get("enabled") is not True:
            continue
        profile = str(row.get("profile") or "").strip()
        phrase = str(row.get("phrase") or "").strip()
        if profile and phrase:
            result[profile] = phrase
    return result
