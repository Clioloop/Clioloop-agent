from unittest.mock import AsyncMock

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter
from gateway.run import GatewayRunner
from clio_cli.platform_dependencies import PlatformDependencyError


class _FatalAdapter(BasePlatformAdapter):
    def __init__(self):
        super().__init__(PlatformConfig(enabled=True, token="token"), Platform.TELEGRAM)

    async def connect(self) -> bool:
        self._set_fatal_error(
            "telegram_token_lock",
            "Another local Clio gateway is already using this Telegram bot token.",
            retryable=False,
        )
        return False

    async def disconnect(self) -> None:
        self._mark_disconnected()

    async def send(self, chat_id, content, reply_to=None, metadata=None):
        raise NotImplementedError

    async def get_chat_info(self, chat_id):
        return {"id": chat_id}


class _RuntimeRetryableAdapter(BasePlatformAdapter):
    def __init__(self):
        super().__init__(PlatformConfig(enabled=True, token="token"), Platform.WHATSAPP)

    async def connect(self) -> bool:
        return True

    async def disconnect(self) -> None:
        self._mark_disconnected()

    async def send(self, chat_id, content, reply_to=None, metadata=None):
        raise NotImplementedError

    async def get_chat_info(self, chat_id):
        return {"id": chat_id}


@pytest.mark.asyncio
async def test_runner_requests_clean_exit_for_nonretryable_startup_conflict(monkeypatch, tmp_path):
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(enabled=True, token="token")
        },
        sessions_dir=tmp_path / "sessions",
    )
    runner = GatewayRunner(config)

    monkeypatch.setattr(runner, "_create_adapter", lambda platform, platform_config: _FatalAdapter())

    ok = await runner.start()

    assert ok is True
    assert runner.should_exit_cleanly is True
    assert "already using this Telegram bot token" in runner.exit_reason


@pytest.mark.asyncio
async def test_runner_surfaces_missing_platform_dependency_as_fatal(monkeypatch, tmp_path):
    config = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="token")},
        sessions_dir=tmp_path / "sessions",
    )
    runner = GatewayRunner(config)
    runtime_updates = []
    error = PlatformDependencyError(
        platform_id="telegram",
        feature="platform.telegram",
        reason="automatic dependency installation failed",
        install_command="uv pip install 'python-telegram-bot[webhooks]==22.6'",
    )

    monkeypatch.setattr(runner, "_create_adapter", lambda *args: (_ for _ in ()).throw(error))
    monkeypatch.setattr(
        runner,
        "_update_platform_runtime_status",
        lambda platform, **status: runtime_updates.append((platform, status)),
    )

    ok = await runner.start()

    assert ok is True
    assert runner.should_exit_cleanly is True
    assert "Telegram support is unavailable" in runner.exit_reason
    assert runtime_updates[0][1]["error_code"] == "dependency_missing"
    assert runtime_updates[0][1]["platform_state"] == "fatal"


@pytest.mark.asyncio
async def test_runner_queues_retryable_runtime_fatal_for_reconnection(monkeypatch, tmp_path):
    """Retryable runtime fatal errors queue the platform for reconnection
    AND keep the gateway alive — the background reconnect watcher recovers
    the platform when the underlying issue clears.  (Previously this
    exited-with-failure to trigger a systemd restart; that converted
    transient failures into infinite restart loops.)
    """
    config = GatewayConfig(
        platforms={
            Platform.WHATSAPP: PlatformConfig(enabled=True, token="token")
        },
        sessions_dir=tmp_path / "sessions",
    )
    runner = GatewayRunner(config)
    adapter = _RuntimeRetryableAdapter()
    adapter._set_fatal_error(
        "whatsapp_bridge_exited",
        "WhatsApp bridge process exited unexpectedly (code 1).",
        retryable=True,
    )

    runner.adapters = {Platform.WHATSAPP: adapter}
    runner.delivery_router.adapters = runner.adapters
    runner.stop = AsyncMock()

    await runner._handle_adapter_fatal_error(adapter)

    # Gateway stays alive — watcher will retry in background
    runner.stop.assert_not_awaited()
    assert runner._exit_with_failure is False
    assert Platform.WHATSAPP in runner._failed_platforms
    assert runner._failed_platforms[Platform.WHATSAPP]["attempts"] == 0
