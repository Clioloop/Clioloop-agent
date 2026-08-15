"""Pure, hierarchical gateway profile-route matching.

Importing this module performs no profile reads, network calls, or config writes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional

_SAFE_PROFILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


class ProfileRouteRejected(RuntimeError):
    """An explicit route targets a profile this runtime cannot serve."""


@dataclass(frozen=True)
class ProfileRoute:
    platform: str
    profile: str
    name: str = ""
    guild_id: Optional[str] = None
    chat_id: Optional[str] = None
    thread_id: Optional[str] = None
    enabled: bool = True

    @property
    def specificity(self) -> int:
        return (2 if self.guild_id else 0) + (4 if self.chat_id else 0) + (8 if self.thread_id else 0)

    def matches(
        self, platform: str, *, guild_id: Optional[str] = None,
        chat_id: Optional[str] = None, thread_id: Optional[str] = None,
        parent_chat_id: Optional[str] = None,
    ) -> bool:
        return bool(
            self.enabled
            and self.platform.casefold() == platform.casefold()
            and (not self.guild_id or self.guild_id == guild_id)
            and (not self.chat_id or self.chat_id in {chat_id, parent_chat_id})
            and (not self.thread_id or self.thread_id == thread_id)
        )


def parse_profile_routes(rows: Iterable[Mapping[str, Any]]) -> list[ProfileRoute]:
    routes: list[ProfileRoute] = []
    for row in rows or ():
        platform = str(row.get("platform") or "").strip().lower()
        profile = str(row.get("profile") or "").strip()
        if not platform or not _SAFE_PROFILE.fullmatch(profile):
            continue
        routes.append(ProfileRoute(
            platform=platform, profile=profile, name=str(row.get("name") or ""),
            guild_id=str(row["guild_id"]) if row.get("guild_id") is not None else None,
            chat_id=str(row["chat_id"]) if row.get("chat_id") is not None else None,
            thread_id=str(row["thread_id"]) if row.get("thread_id") is not None else None,
            enabled=row.get("enabled", True) is not False,
        ))
    return sorted(routes, key=lambda route: route.specificity, reverse=True)


def match_profile_route(routes: Iterable[ProfileRoute], platform: str, **scope) -> Optional[ProfileRoute]:
    return next((route for route in routes if route.matches(platform, **scope)), None)
