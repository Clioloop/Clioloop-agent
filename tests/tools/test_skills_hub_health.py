"""Tests for Skills Hub source health check (check_source_health)."""

import time
import pytest
from concurrent.futures import ThreadPoolExecutor


# ── Helpers ─────────────────────────────────────────────────────────────────


class _MockSource:
    """Minimal mock SkillSource for testing."""

    def __init__(self, sid: str, skills=None, exc: Exception | None = None,
                 rate_limited: bool = False, delay: float = 0):
        self._sid = sid
        self._skills = skills or []
        self._exc = exc
        self._rate_limited = rate_limited
        self._delay = delay
        self.is_rate_limited = rate_limited

    def source_id(self) -> str:
        return self._sid

    def search(self, query: str, limit: int = 10):
        if self._delay:
            time.sleep(self._delay)
        if self._exc:
            raise self._exc
        return self._skills

    def fetch(self, identifier):
        return None

    def inspect(self, identifier):
        return None


# ── Tests ───────────────────────────────────────────────────────────────────


def test_healthy_source():
    """A source that returns skills is marked healthy."""
    from tools.skills_hub import check_source_health

    src = _MockSource("test-healthy", skills=[{"name": "a"}, {"name": "b"}])
    results = check_source_health([src])
    assert len(results) == 1
    assert results[0]["source_id"] == "test-healthy"
    assert results[0]["status"] == "healthy"
    assert results[0]["skill_count"] == 2
    assert results[0]["error"] == ""
    assert results[0]["latency_ms"] >= 0


def test_unreachable_source():
    """A source that raises is marked unreachable with an error message."""
    from tools.skills_hub import check_source_health

    src = _MockSource("test-down", exc=ConnectionError("network error"))
    results = check_source_health([src])
    assert len(results) == 1
    assert results[0]["source_id"] == "test-down"
    assert results[0]["status"] == "unreachable"
    assert results[0]["skill_count"] == 0
    assert "network error" in results[0]["error"]


def test_rate_limited_source():
    """A source with is_rate_limited=True is marked rate_limited."""
    from tools.skills_hub import check_source_health

    src = _MockSource("gh", skills=[{"name": "a"}], rate_limited=True)
    results = check_source_health([src])
    assert len(results) == 1
    assert results[0]["status"] == "rate_limited"


def test_empty_source_is_healthy():
    """A source that returns zero skills (empty repo) is still 'healthy'."""
    from tools.skills_hub import check_source_health

    src = _MockSource("empty", skills=[])
    results = check_source_health([src])
    assert results[0]["status"] == "healthy"
    assert results[0]["skill_count"] == 0


def test_multiple_sources_sorted():
    """Results are sorted by source_id for deterministic output."""
    from tools.skills_hub import check_source_health

    sources = [
        _MockSource("zzz", skills=[{"name": "a"}]),
        _MockSource("aaa", skills=[{"name": "b"}]),
        _MockSource("mmm", skills=[{"name": "c"}]),
    ]
    results = check_source_health(sources)
    ids = [r["source_id"] for r in results]
    assert ids == ["aaa", "mmm", "zzz"]


def test_has_timestamp():
    """Each result has an ISO timestamp."""
    from tools.skills_hub import check_source_health

    src = _MockSource("ts", skills=[{"name": "a"}])
    results = check_source_health([src])
    assert "last_check" in results[0]
    assert "T" in results[0]["last_check"]  # ISO format


def test_do_health_import():
    """do_health is importable from clio_cli.skills_hub."""
    from clio_cli.skills_hub import do_health
    assert callable(do_health)