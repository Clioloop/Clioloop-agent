"""Per-turn retry/restart bookkeeping for the conversation loop.

A fresh state object is created for every provider request iteration.  Recovery
branches are one-shot by default and :meth:`claim` gives new branches a single
bounded mechanism instead of another free-running local counter.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields


@dataclass
class TurnRetryState:
    # Provider/auth recovery guards.
    codex_auth_retry_attempted: bool = False
    anthropic_auth_retry_attempted: bool = False
    managed_auth_retry_attempted: bool = False
    managed_paid_entitlement_refresh_attempted: bool = False
    copilot_auth_retry_attempted: bool = False

    # Payload/format recovery guards.
    thinking_sig_retry_attempted: bool = False
    invalid_encrypted_content_retry_attempted: bool = False
    image_shrink_retry_attempted: bool = False
    multimodal_tool_content_retry_attempted: bool = False
    oauth_1m_beta_retry_attempted: bool = False
    llama_cpp_grammar_retry_attempted: bool = False

    # Transport/rate-limit recovery.
    primary_recovery_attempted: bool = False
    has_retried_429: bool = False

    # Signals consumed after the inner attempt.
    restart_with_compressed_messages: bool = False
    restart_with_length_continuation: bool = False

    _attempts: dict[str, int] = field(default_factory=dict, init=False, repr=False)

    def claim(self, name: str, *, limit: int = 1) -> bool:
        """Claim a recovery attempt, returning false once its bound is reached."""
        valid = {item.name for item in fields(self) if not item.name.startswith("_")}
        if name not in valid:
            raise KeyError(f"unknown turn retry guard: {name}")
        bound = max(0, int(limit))
        # Existing loop branches still assign guard booleans directly while
        # they migrate to claim().  Treat that assignment as one consumed
        # attempt rather than accidentally granting a second recovery.
        used = self._attempts.get(name, int(bool(getattr(self, name, False))))
        if used >= bound:
            return False
        self._attempts[name] = used + 1
        if isinstance(getattr(self, name), bool):
            setattr(self, name, True)
        return True

    def attempts_for(self, name: str) -> int:
        return self._attempts.get(name, int(bool(getattr(self, name, False))))

    def __iter__(self):
        for item in fields(self):
            if not item.name.startswith("_"):
                yield item.name, getattr(self, item.name)


__all__ = ["TurnRetryState"]
