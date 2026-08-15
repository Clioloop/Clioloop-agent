from clio_cli.commands import COMMANDS, SUBCOMMANDS, gateway_help_lines, resolve_command
from clio_cli.init_command import build_init_prompt_for_cwd


def test_high_value_commands_are_canonical_and_help_backed():
    expected = {"pause", "resume", "verify", "context", "diff", "focus", "init", "prompt", "journey", "learn"}
    assert expected <= {command.name for command in __import__("clio_cli.commands", fromlist=["COMMAND_REGISTRY"]).COMMAND_REGISTRY}
    assert resolve_command("/ctx").name == "context"
    assert resolve_command("compose").name == "prompt"
    assert resolve_command("learning").name == "journey"
    assert SUBCOMMANDS["/verify"] == ["build", "test", "all"]
    assert "/pause" not in COMMANDS  # gateway-only operator control
    assert any(line.startswith("`/pause") for line in gateway_help_lines())


def test_init_prompt_preserves_existing_instructions(tmp_path):
    (tmp_path / "AGENTS.md").write_text("# Local rules\nKeep this.\n", encoding="utf-8")
    prompt = build_init_prompt_for_cwd(str(tmp_path), "focus on tests")
    assert "UPDATE the existing AGENTS.md" in prompt
    assert "Keep this." in prompt
    assert "focus on tests" in prompt
    assert str(tmp_path / "AGENTS.md") in prompt
