from __future__ import annotations

import pytest

from agent.fusion_engine import FusionConfig
from gateway.config import GatewayConfig, Platform
from gateway.platforms.base import MessageEvent
from gateway.session import SessionSource, build_session_key


def _source() -> SessionSource:
    return SessionSource(
        platform=Platform.TELEGRAM,
        user_id="u1",
        chat_id="c1",
        user_name="tester",
        chat_type="dm",
    )


@pytest.mark.asyncio
async def test_fusion_status_uses_current_chat_model_copy():
    from gateway.run import GatewayRunner

    source = _source()
    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig()
    runner._session_fusion_configs = {
        build_session_key(source): FusionConfig(
            advisors=["advisor-a", "advisor-b"],
            reviewers=["reviewer-a"],
            judge="main-worker",
            enabled=True,
        )
    }

    result = await GatewayRunner._handle_fusion_command(
        runner,
        MessageEvent(text="/fusion status", source=source, message_id="m1"),
    )

    assert "Planners" in result
    assert "Reviewers" in result
    assert "Main model:" in result
    assert "current chat model" in result
    assert "/model" in result
    assert "main-worker" not in result


@pytest.mark.asyncio
async def test_fusion_gate_subcommand_reports_plan_gate(monkeypatch):
    from agent import fusion_engine
    from gateway.run import GatewayRunner

    source = _source()
    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig()
    runner._session_fusion_configs = {}
    monkeypatch.setattr(
        fusion_engine,
        "fusion_gate_check",
        lambda force_fresh=True: (False, "Fusion is only available on Max."),
    )

    result = await GatewayRunner._handle_fusion_command(
        runner,
        MessageEvent(text="/fusion gate", source=source, message_id="m1"),
    )

    assert result == "Fusion is only available on Max."
