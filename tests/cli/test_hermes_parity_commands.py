from clio_cli.commands import (
    COMMANDS,
    GATEWAY_KNOWN_COMMANDS,
    SUBCOMMANDS,
    gateway_help_lines,
    slack_native_slashes,
    telegram_bot_commands,
)
from clio_cli.parity_commands import execute

PARITY = {
    "approvals", "battery", "blueprint", "egress", "export", "hatch",
    "heartbeat", "import", "loop", "memory", "moa", "pet", "refine",
    "subscription", "suggestions", "timestamps", "topup", "version", "wake",
}


def test_parity_commands_are_help_and_completion_backed():
    assert {f"/{name}" for name in PARITY} <= set(COMMANDS)
    assert SUBCOMMANDS["/approvals"] == ["manual", "smart", "off"]
    assert SUBCOMMANDS["/heartbeat"] == ["status", "pause", "resume", "clear"]


def test_gateway_and_messaging_surfaces_derive_from_registry():
    gateway_expected = PARITY - {"battery", "export", "hatch", "import", "pet", "timestamps", "wake"}
    assert gateway_expected <= GATEWAY_KNOWN_COMMANDS
    help_text = "\n".join(gateway_help_lines())
    assert all(f"`/{name}" in help_text for name in gateway_expected)
    telegram = {name for name, _ in telegram_bot_commands()}
    slack = {name for name, _description, _usage in slack_native_slashes()}
    assert gateway_expected <= telegram
    assert gateway_expected <= slack


def test_shared_handlers_use_real_automation_and_version_contracts():
    catalog = execute("suggestions").text
    assert "morning-brief" in catalog
    assert execute("version").text.startswith("Clio Agent ")
    assert "Usage:" in execute("moa").text
