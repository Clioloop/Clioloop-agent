"""Regression tests for gateway per-turn env reload preserving config authority.

Issue #19158: a per-turn environment reload may restore a stale
CLIO_MAX_ITERATIONS value. Turn-limit consumers now resolve config.yaml
directly, so the stale compatibility variable must not regain authority.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from gateway import run as gateway_run


def test_reload_runtime_env_keeps_config_resolver_authoritative(
    tmp_path: Path, monkeypatch
) -> None:
    clio_home = tmp_path / ".clio"
    clio_home.mkdir()
    (clio_home / "config.yaml").write_text(
        yaml.safe_dump({"agent": {"max_turns": 9000}}),
        encoding="utf-8",
    )
    (clio_home / ".env").write_text(
        "CLIO_MAX_ITERATIONS=90\nOPENROUTER_API_KEY=fresh-key\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(gateway_run, "_clio_home", clio_home)
    monkeypatch.setenv("CLIO_MAX_ITERATIONS", "9000")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    gateway_run._reload_runtime_env_preserving_config_authority()

    assert os.environ["OPENROUTER_API_KEY"] == "fresh-key"
    assert os.environ["CLIO_MAX_ITERATIONS"] == "90"
    assert gateway_run._configured_max_iterations({"agent": {"max_turns": 9000}}) == 9000


def test_reload_runtime_env_keeps_env_max_iterations_when_config_omits_key(
    tmp_path: Path, monkeypatch
) -> None:
    clio_home = tmp_path / ".clio"
    clio_home.mkdir()
    (clio_home / "config.yaml").write_text(yaml.safe_dump({"agent": {}}), encoding="utf-8")
    (clio_home / ".env").write_text("CLIO_MAX_ITERATIONS=123\n", encoding="utf-8")

    monkeypatch.setattr(gateway_run, "_clio_home", clio_home)
    monkeypatch.delenv("CLIO_MAX_ITERATIONS", raising=False)

    gateway_run._reload_runtime_env_preserving_config_authority()

    assert os.environ["CLIO_MAX_ITERATIONS"] == "123"
