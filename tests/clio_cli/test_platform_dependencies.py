from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from clio_cli import platform_dependencies as deps
from tools.lazy_deps import FeatureUnavailable


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_official_all_extra_includes_pinned_telegram_sdk():
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as handle:
        optional = tomllib.load(handle)["project"]["optional-dependencies"]

    assert optional["telegram"] == ["python-telegram-bot[webhooks]==22.6"]
    assert "clioloop-agent[telegram]" in optional["all"]


def test_configured_platforms_detects_token_without_exposing_value():
    env = {"TELEGRAM_BOT_TOKEN": "secret-token", "UNRELATED": "value"}

    assert deps.configured_platforms(env) == ["telegram"]


def test_ensure_platform_ready_uses_shared_lazy_feature(monkeypatch):
    calls = []
    monkeypatch.setattr(deps, "ensure", lambda feature, prompt=False: calls.append((feature, prompt)))

    deps.ensure_platform_ready("telegram", prompt=True)

    assert calls == [("platform.telegram", True)]


def test_ensure_platform_ready_sanitizes_resolver_failure(monkeypatch):
    def fail(feature, prompt=False):
        raise FeatureUnavailable(feature, ("python-telegram-bot==22.6",), "pip install failed: noisy resolver output")

    monkeypatch.setattr(deps, "ensure", fail)

    with pytest.raises(deps.PlatformDependencyError) as raised:
        deps.ensure_platform_ready("telegram")

    message = str(raised.value)
    assert "automatic dependency installation failed" in message
    assert "noisy resolver output" not in message
    assert "clio update" in message


def test_repair_configured_platforms_reports_failure(monkeypatch):
    error = deps.PlatformDependencyError(
        platform_id="telegram",
        feature="platform.telegram",
        reason="lazy installs disabled",
        install_command="uv pip install 'python-telegram-bot[webhooks]==22.6'",
    )
    monkeypatch.setattr(deps, "ensure_platform_ready", lambda *args, **kwargs: (_ for _ in ()).throw(error))

    result = deps.repair_configured_platforms({"TELEGRAM_BOT_TOKEN": "configured"})

    assert result["telegram"].startswith("failed: Telegram support is unavailable")
