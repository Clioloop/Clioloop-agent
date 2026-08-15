"""Tests for cron-only model/provider/reasoning defaults."""

from __future__ import annotations

import sys


def _install_scheduler_stubs(monkeypatch, observed: dict):
    import cron.scheduler as sched

    class FakeAgent:
        def __init__(self, **kwargs):
            observed.update(kwargs)

        def run_conversation(self, *_args, **_kwargs):
            return {"final_response": "done", "messages": []}

        def get_activity_summary(self):
            return {"seconds_since_activity": 0.0}

        def close(self):
            return None

    fake_run_agent = type(sys)("run_agent")
    fake_run_agent.AIAgent = FakeAgent
    monkeypatch.setitem(sys.modules, "run_agent", fake_run_agent)
    monkeypatch.setattr(
        "clio_cli.runtime_provider.resolve_runtime_provider",
        lambda **kwargs: {
            "provider": kwargs.get("requested") or "main-provider",
            "api_key": "test-key",
            "base_url": "http://test.local",
            "api_mode": "chat_completions",
        },
    )
    monkeypatch.setattr(sched, "_build_job_prompt", lambda job, prerun_script=None: "hi")
    monkeypatch.setattr(sched, "_resolve_origin", lambda job: None)
    monkeypatch.setattr(sched, "_resolve_delivery_target", lambda job: None)
    monkeypatch.setattr(sched, "_resolve_cron_enabled_toolsets", lambda job, cfg: None)
    monkeypatch.setattr(sched, "_resolve_cron_disabled_toolsets", lambda cfg: [])
    monkeypatch.setenv("CLIO_CRON_TIMEOUT", "0")


def test_cron_defaults_override_interactive_model_provider_and_reasoning(tmp_path, monkeypatch):
    import cron.scheduler as sched

    home = tmp_path / "clio"
    home.mkdir()
    (home / "config.yaml").write_text(
        """
model:
  default: gpt-5.6-sol
  provider: openai-codex
agent:
  reasoning_effort: xhigh
cron:
  model: gpt-5.6-luna
  provider: openai-codex
  reasoning_effort: medium
""".lstrip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(sched, "_clio_home", home)
    observed: dict = {}
    _install_scheduler_stubs(monkeypatch, observed)

    success, _output, response, error = sched.run_job(
        {"id": "cron-defaults", "name": "Cron defaults", "prompt": "ping"}
    )

    assert success is True, error
    assert response == "done"
    assert observed["model"] == "gpt-5.6-luna"
    assert observed["provider"] == "openai-codex"
    assert observed["reasoning_config"] == {"enabled": True, "effort": "medium"}


def test_per_job_model_and_provider_still_take_precedence(tmp_path, monkeypatch):
    import cron.scheduler as sched

    home = tmp_path / "clio"
    home.mkdir()
    (home / "config.yaml").write_text(
        """
model:
  default: gpt-5.6-sol
  provider: openai-codex
agent:
  reasoning_effort: xhigh
cron:
  model: gpt-5.6-luna
  provider: openai-codex
  reasoning_effort: medium
""".lstrip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(sched, "_clio_home", home)
    observed: dict = {}
    _install_scheduler_stubs(monkeypatch, observed)

    success, *_ = sched.run_job(
        {
            "id": "cron-pinned",
            "name": "Pinned cron",
            "prompt": "ping",
            "model": "pinned-model",
            "provider": "pinned-provider",
        }
    )

    assert success is True
    assert observed["model"] == "pinned-model"
    assert observed["provider"] == "pinned-provider"
    assert observed["reasoning_config"] == {"enabled": True, "effort": "medium"}
