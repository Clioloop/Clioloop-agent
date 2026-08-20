"""Canonical turn-limit resolver tests shared by every agent surface."""

import sys
from datetime import datetime
from types import SimpleNamespace
from typing import cast

import pytest

from clio_cli.config import (
    TURN_LIMIT_UNLIMITED,
    format_turn_limit,
    resolve_config_turn_limit,
    resolve_turn_limit,
)


@pytest.mark.parametrize(("raw", "expected"), [
    (1, 1),
    (" 42 ", 42),
    (None, TURN_LIMIT_UNLIMITED),
    (0, TURN_LIMIT_UNLIMITED),
    (-3, TURN_LIMIT_UNLIMITED),
    ("unlimited", TURN_LIMIT_UNLIMITED),
    ("NONE", TURN_LIMIT_UNLIMITED),
    ("inf", TURN_LIMIT_UNLIMITED),
])
def test_resolve_turn_limit_matrix(raw, expected):
    assert resolve_turn_limit(raw) == expected


def test_invalid_value_uses_explicit_default():
    assert resolve_turn_limit("not-a-limit", default=17) == 17


@pytest.mark.parametrize(("config", "expected"), [
    ({}, sys.maxsize),
    ({"max_turns": 31}, 31),
    ({"agent": {"max_turns": 47}, "max_turns": 31}, 47),
    ({"agent": {"max_turns": None}, "max_turns": 31}, sys.maxsize),
    ({"agent": None, "max_turns": 31}, 31),
])
def test_config_resolution_default_legacy_and_null(config, expected):
    assert resolve_config_turn_limit(config) == expected


def test_surface_env_override_is_opt_in(monkeypatch):
    monkeypatch.setenv("CLIO_MAX_ITERATIONS", "5")
    assert resolve_config_turn_limit({"agent": {"max_turns": 22}}) == 22
    assert resolve_config_turn_limit(
        {"agent": {"max_turns": 22}}, env_value="7"
    ) == 7


def test_format_unlimited_hides_internal_sentinel():
    assert format_turn_limit(None) == "unlimited"
    assert format_turn_limit(TURN_LIMIT_UNLIMITED) == "unlimited"
    assert format_turn_limit(8) == "8"


@pytest.mark.parametrize("raw_limit", [None, TURN_LIMIT_UNLIMITED])
def test_clio_config_show_labels_null_and_sentinel_unlimited(
    raw_limit, monkeypatch, capsys
):
    from clio_cli import config as config_module

    shown_config = {
        **config_module.DEFAULT_CONFIG,
        "agent": {
            **config_module.DEFAULT_CONFIG["agent"],
            "max_turns": raw_limit,
        },
    }
    monkeypatch.setattr(config_module, "load_config", lambda: shown_config)
    monkeypatch.setattr(config_module, "load_env", lambda: {})
    monkeypatch.setattr(config_module, "get_env_value", lambda _key: "")
    monkeypatch.setattr("clio_cli.auth.get_anthropic_key", lambda: "")

    config_module.show_config()

    output = capsys.readouterr().out
    assert "Max turns:    unlimited" in output
    assert str(TURN_LIMIT_UNLIMITED) not in output


@pytest.mark.parametrize("raw_limit", [None, TURN_LIMIT_UNLIMITED])
def test_classic_slash_config_labels_null_and_sentinel_unlimited(
    raw_limit, capsys
):
    from cli import ClioCLI

    shell = SimpleNamespace(
        api_key=None,
        agent=None,
        model="test-model",
        base_url="https://example.invalid/v1",
        max_turns=raw_limit,
        enabled_toolsets=[],
        verbose=False,
        session_start=datetime(2026, 1, 1),
    )
    ClioCLI.show_config(cast(ClioCLI, shell))

    output = capsys.readouterr().out
    assert "Max Turns:  unlimited" in output
    assert str(TURN_LIMIT_UNLIMITED) not in output
