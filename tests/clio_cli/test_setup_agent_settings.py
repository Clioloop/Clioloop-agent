"""Tests for agent-settings copy in the interactive setup wizard."""

import pytest

from clio_cli.setup import (
    _apply_default_agent_settings,
    _get_section_config_summary,
    setup_agent_settings,
)


def _stub_remaining_agent_prompts(monkeypatch, max_turns_answer):
    prompt_answers = iter([max_turns_answer, "all", "0.5"])
    monkeypatch.setattr(
        "clio_cli.setup.prompt", lambda *args, **kwargs: next(prompt_answers)
    )
    monkeypatch.setattr("clio_cli.setup.prompt_choice", lambda *args, **kwargs: 4)
    monkeypatch.setattr("clio_cli.setup.save_env_value", lambda *args, **kwargs: None)
    monkeypatch.setattr("clio_cli.setup.remove_env_value", lambda *args, **kwargs: None)
    monkeypatch.setattr("clio_cli.setup.save_config", lambda *args, **kwargs: None)


def test_setup_agent_settings_uses_displayed_max_iterations_value(tmp_path, monkeypatch, capsys):
    """The helper text should match the value shown in the prompt.

    After PR#18413 max_turns is read exclusively from config.yaml — the
    .env `CLIO_MAX_ITERATIONS` fallback was removed because it was
    shadowing the user's current config (see the 60-vs-500 incident).
    """
    monkeypatch.setenv("CLIO_HOME", str(tmp_path))

    config = {
        "agent": {"max_turns": 60},
        "display": {"tool_progress": "all"},
        "compression": {"threshold": 0.50},
        "session_reset": {"mode": "both", "idle_minutes": 1440, "at_hour": 4},
    }

    prompt_answers = iter(["60", "all", "0.5"])

    monkeypatch.setattr("clio_cli.setup.prompt", lambda *args, **kwargs: next(prompt_answers))
    monkeypatch.setattr("clio_cli.setup.prompt_choice", lambda *args, **kwargs: 4)
    monkeypatch.setattr("clio_cli.setup.save_env_value", lambda *args, **kwargs: None)
    monkeypatch.setattr("clio_cli.setup.remove_env_value", lambda *args, **kwargs: None)
    monkeypatch.setattr("clio_cli.setup.save_config", lambda *args, **kwargs: None)

    setup_agent_settings(config)

    out = capsys.readouterr().out
    assert "Press Enter to keep 60." in out
    assert "Default is 90" not in out


def test_setup_agent_settings_prefers_config_over_stale_env(tmp_path, monkeypatch, capsys):
    """Config.yaml wins even when a stale .env value disagrees.

    Regression guard for the bug where `.env CLIO_MAX_ITERATIONS=60`
    from an old `clio setup` run shadowed `agent.max_turns: 500` in
    config.yaml. The wizard must now display the config value.
    """
    monkeypatch.setenv("CLIO_HOME", str(tmp_path))

    config = {
        "agent": {"max_turns": 500},  # user bumped this in config.yaml
        "display": {"tool_progress": "all"},
        "compression": {"threshold": 0.50},
        "session_reset": {"mode": "both", "idle_minutes": 1440, "at_hour": 4},
    }

    prompt_answers = iter(["500", "all", "0.5"])

    # Simulate stale .env value — the wizard must ignore this.
    monkeypatch.setattr(
        "clio_cli.setup.get_env_value",
        lambda key: "60" if key == "CLIO_MAX_ITERATIONS" else "",
    )
    monkeypatch.setattr("clio_cli.setup.prompt", lambda *args, **kwargs: next(prompt_answers))
    monkeypatch.setattr("clio_cli.setup.prompt_choice", lambda *args, **kwargs: 4)
    monkeypatch.setattr("clio_cli.setup.save_env_value", lambda *args, **kwargs: None)

    removed_keys: list[str] = []
    monkeypatch.setattr(
        "clio_cli.setup.remove_env_value",
        lambda key: (removed_keys.append(key), True)[1],
    )
    monkeypatch.setattr("clio_cli.setup.save_config", lambda *args, **kwargs: None)

    setup_agent_settings(config)

    out = capsys.readouterr().out
    # Config value wins
    assert "Press Enter to keep 500." in out
    assert "Press Enter to keep 60." not in out
    # And the stale .env entry gets cleaned up
    assert "CLIO_MAX_ITERATIONS" in removed_keys


@pytest.mark.parametrize(
    ("entered", "expected", "label"),
    [
        ("unlimited", None, "unlimited"),
        ("NONE", None, "unlimited"),
        ("null", None, "unlimited"),
        ("infinite", None, "unlimited"),
        ("infinity", None, "unlimited"),
        ("inf", None, "unlimited"),
        ("∞", None, "unlimited"),
        ("0", None, "unlimited"),
        ("-1", None, "unlimited"),
        ("275", 275, "275"),
    ],
)
def test_setup_agent_settings_accepts_unlimited_spellings_and_finite_values(
    entered, expected, label, monkeypatch, capsys
):
    config = {
        "agent": {"max_turns": None},
        "display": {"tool_progress": "all"},
        "compression": {"threshold": 0.50},
        "session_reset": {"mode": "none"},
    }
    _stub_remaining_agent_prompts(monkeypatch, entered)

    setup_agent_settings(config)

    output = capsys.readouterr().out
    assert "Press Enter to keep unlimited." in output
    assert f"Max iterations set to {label}" in output
    assert config["agent"]["max_turns"] == expected


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        ({}, None),
        ({"agent": {"max_turns": None}}, None),
        ({"agent": {"max_turns": 275}}, 275),
    ],
)
def test_fresh_and_quick_setup_defaults_do_not_add_a_finite_turn_cap(
    config, expected, monkeypatch, capsys
):
    monkeypatch.setattr("clio_cli.setup.save_config", lambda *args, **kwargs: None)
    monkeypatch.setattr("clio_cli.setup.remove_env_value", lambda *args, **kwargs: None)

    _apply_default_agent_settings(config)

    assert config["agent"]["max_turns"] == expected
    output = capsys.readouterr().out
    expected_label = "unlimited" if expected is None else str(expected)
    assert f"Max iterations: {expected_label}" in output
    assert "Max iterations: 150" not in output


def test_setup_section_summary_displays_null_as_unlimited():
    assert (
        _get_section_config_summary({"agent": {"max_turns": None}}, "agent")
        == "max turns: unlimited"
    )
