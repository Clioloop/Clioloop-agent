"""Per-turn wall-clock budget primitives.

A run budget is independent from Clio's iteration, cron, goal, and delegation
limits. It is disabled when unset or non-positive. At 80% the conversation loop
adds one append-only wrap-up notice; at 100% it stops starting new model calls.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

WRAP_UP_FRACTION = 0.8


def normalize_run_budget(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(seconds) or seconds <= 0:
        return None
    return seconds


@dataclass
class TurnRunBudget:
    seconds: Optional[float]
    clock: Callable[[], float] = time.monotonic
    started_at: float = field(init=False)
    wrap_up_injected: bool = False

    def __post_init__(self) -> None:
        self.seconds = normalize_run_budget(self.seconds)
        self.started_at = self.clock()

    @property
    def enabled(self) -> bool:
        return self.seconds is not None

    @property
    def elapsed(self) -> float:
        return max(0.0, self.clock() - self.started_at)

    @property
    def remaining(self) -> Optional[float]:
        if self.seconds is None:
            return None
        return max(0.0, self.seconds - self.elapsed)

    @property
    def expired(self) -> bool:
        remaining = self.remaining
        return remaining is not None and remaining <= 0

    @property
    def should_wrap_up(self) -> bool:
        return bool(
            self.seconds is not None
            and not self.wrap_up_injected
            and self.elapsed >= self.seconds * WRAP_UP_FRACTION
        )

    def mark_wrap_up(self) -> None:
        self.wrap_up_injected = True

    def bound_timeout(self, requested: float, *, floor: float = 0.1) -> float:
        """Clamp a watchdog wait to the time left in this turn."""
        remaining = self.remaining
        if remaining is None:
            return requested
        return max(floor, min(float(requested), remaining))


def append_wrap_up_notice(messages: list[dict]) -> bool:
    """Append guidance without introducing an invalid message-role transition."""
    notice = (
        "\n\n[Clio run-budget notice: the turn has used 80% of its wall-clock budget. "
        "Stop expanding scope. Finish the highest-value in-progress work, verify what "
        "you can, and return a concise truthful result before the deadline.]"
    )
    for message in reversed(messages):
        if not isinstance(message, dict):
            continue
        if message.get("role") not in {"tool", "user"}:
            continue
        content = message.get("content", "")
        if isinstance(content, str):
            if "[Clio run-budget notice:" not in content:
                message["content"] = content + notice
            return True
        if isinstance(content, list):
            content.append({"type": "text", "text": notice})
            return True
    return False


def bound_agent_timeout(agent, requested: float, *, floor: float = 0.1) -> float:
    budget = getattr(agent, "_turn_run_budget", None)
    bound = getattr(budget, "bound_timeout", None)
    if callable(bound):
        result: Any = bound(requested, floor=floor)
        return float(result)
    return requested
