"""Focused regressions for CLI operations and shareable computer captures."""

from __future__ import annotations

import base64
import os

import pytest


def test_oneshot_skill_parser_and_prompt_partial_success(monkeypatch, caplog):
    from clio_cli._parser import build_top_level_parser
    import clio_cli.oneshot as oneshot

    parser, _, _ = build_top_level_parser()
    args = parser.parse_args(
        ["-z", "hello", "--skills", "alpha,beta", "-s", "alpha", "-s", "missing"]
    )
    assert args.skills == ["alpha,beta", "alpha", "missing"]

    observed = {}

    def fake_build(names):
        observed["names"] = names
        return "SKILLS PROMPT", ["alpha", "beta"], ["missing"]

    monkeypatch.setattr(
        "agent.skill_commands.build_preloaded_skills_prompt", fake_build
    )
    with caplog.at_level("WARNING"):
        prompt = oneshot._build_preloaded_skills_prompt(args.skills)

    assert prompt == "SKILLS PROMPT"
    assert observed["names"] == ["alpha", "beta", "missing"]
    assert "Unknown skill(s) requested, skipping: missing" in caplog.text


def test_oneshot_skill_prompt_rejects_all_missing(monkeypatch):
    import clio_cli.oneshot as oneshot

    monkeypatch.setattr(
        "agent.skill_commands.build_preloaded_skills_prompt",
        lambda _names: ("", [], ["missing"]),
    )
    with pytest.raises(ValueError, match="Unknown skill.*missing"):
        oneshot._build_preloaded_skills_prompt("missing")


def test_whoami_dispatch_reports_unrestricted_cli(monkeypatch, capsys):
    from cli import ClioCLI

    cli = ClioCLI.__new__(ClioCLI)
    monkeypatch.setattr("getpass.getuser", lambda: "alice")

    assert cli.process_command("/whoami") is True
    output = capsys.readouterr().out
    assert "You:            cli (local terminal)" in output
    assert "User:           alice" in output
    assert "Tier:           unrestricted" in output
    assert "Slash commands: all available" in output


def test_checkpoint_global_listing_and_format(tmp_path, monkeypatch):
    from tools import checkpoint_manager as checkpoint_mod

    base = tmp_path / "checkpoints"
    monkeypatch.setattr(checkpoint_mod, "CHECKPOINT_BASE", base)
    manager = checkpoint_mod.CheckpointManager(enabled=True, max_snapshots=50)
    projects = []
    for name in ("a", "b"):
        project = tmp_path / name
        project.mkdir()
        (project / "file.txt").write_text(name, encoding="utf-8")
        manager.new_turn()
        assert manager.ensure_checkpoint(str(project), f"checkpoint-{name}")
        projects.append(project)

    checkpoints = manager.list_all_checkpoints()
    assert {item["workdir"] for item in checkpoints} == {str(p) for p in projects}
    rendered = checkpoint_mod.format_checkpoint_list(checkpoints, "all directories")
    assert f"[{projects[0].name}]" in rendered
    assert f"[{projects[1].name}]" in rendered


def _capture_result():
    from tools.computer_use.backend import CaptureResult

    png_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAFElEQVR42m"
        "NoIBEwjGoY1TB8NQAAJYSAELxv8c8AAAAASUVORK5CYII="
    )
    return CaptureResult(
        mode="som",
        width=16,
        height=16,
        png_b64=png_b64,
        png_bytes_len=len(base64.b64decode(png_b64)),
    )


def test_capture_path_uses_active_profile_and_cleanup_is_bounded(tmp_path, monkeypatch):
    from tools.computer_use import tool as computer_tool

    profile_home = tmp_path / "profile"
    monkeypatch.setattr("clio_constants.get_clio_home", lambda: profile_home)
    cap = _capture_result()
    paths = [computer_tool._persist_capture_image(cap) for _ in range(25)]

    cache = profile_home / "cache" / "images"
    remaining = list(cache.glob("computer_use_*.*"))
    assert len(remaining) == computer_tool._MAX_CAPTURE_FILES
    assert paths[-1] and paths[-1].startswith(str(cache))
    assert os.path.exists(paths[-1])


def test_capture_response_exposes_shareable_path(tmp_path, monkeypatch):
    from tools.computer_use import tool as computer_tool

    profile_home = tmp_path / "profile"
    monkeypatch.setattr("clio_constants.get_clio_home", lambda: profile_home)
    monkeypatch.setattr(computer_tool, "_should_route_through_aux_vision", lambda: False)

    response = computer_tool._capture_response(_capture_result())
    assert isinstance(response, dict)
    path = response["meta"]["screenshot_path"]
    assert os.path.exists(path)
    summary = next(part["text"] for part in response["content"] if part["type"] == "text")
    assert path in summary
