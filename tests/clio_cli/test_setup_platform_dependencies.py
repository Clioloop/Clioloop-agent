from __future__ import annotations


def test_cli_telegram_setup_prepares_dependency_before_reading_credentials(monkeypatch):
    import clio_cli.platform_dependencies as platform_deps
    import clio_cli.setup as setup

    calls = []
    monkeypatch.setattr(
        platform_deps,
        "ensure_platform_ready",
        lambda platform_id, prompt=False: calls.append((platform_id, prompt)),
    )
    monkeypatch.setattr(setup, "print_header", lambda *args: None)
    monkeypatch.setattr(setup, "get_env_value", lambda key: "configured-token")
    monkeypatch.setattr(setup, "print_info", lambda *args: None)
    monkeypatch.setattr(setup, "prompt_yes_no", lambda *args, **kwargs: False)

    setup._setup_telegram()

    assert calls == [("telegram", True)]


def test_cli_telegram_setup_stops_before_credentials_when_dependency_fails(monkeypatch):
    import clio_cli.platform_dependencies as platform_deps
    import clio_cli.setup as setup

    error = platform_deps.PlatformDependencyError(
        platform_id="telegram",
        feature="platform.telegram",
        reason="automatic dependency installation failed",
        install_command="uv pip install 'python-telegram-bot[webhooks]==22.6'",
    )
    monkeypatch.setattr(
        platform_deps,
        "ensure_platform_ready",
        lambda *args, **kwargs: (_ for _ in ()).throw(error),
    )
    monkeypatch.setattr(setup, "print_header", lambda *args: None)
    monkeypatch.setattr(
        setup,
        "get_env_value",
        lambda key: (_ for _ in ()).throw(AssertionError("credentials read after dependency failure")),
    )
    messages = []
    monkeypatch.setattr(setup, "print_error", messages.append)

    setup._setup_telegram()

    assert messages and "Telegram support is unavailable" in messages[0]
