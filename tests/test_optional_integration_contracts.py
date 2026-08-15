from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent.media_jobs import MediaJob, MediaKind, MediaOperation, batch_job
from agent.org_skill_sync import (
    OrgSkillRef,
    OrgSkillSyncProvider,
    get_org_skill_sync_provider,
    register_org_skill_sync_provider,
    unregister_org_skill_sync_provider,
)
from cron.providers import register_cron_provider, resolve_cron_provider, unregister_cron_provider


def test_media_batch_edit_extend_contracts():
    job = batch_job(MediaKind.IMAGE, ["a", "b"])
    assert job.operation is MediaOperation.BATCH and job.count == 2
    MediaJob(MediaOperation.UPSCALE, MediaKind.IMAGE, inputs=("in.png",))
    MediaJob(MediaOperation.EDIT, MediaKind.IMAGE, inputs=("in.png",), prompt="blue")
    MediaJob(MediaOperation.EXTEND, MediaKind.VIDEO, inputs=("in.mp4",))
    with pytest.raises(ValueError):
        MediaJob(MediaOperation.EXTEND, MediaKind.IMAGE, inputs=("in.png",))


def test_org_skill_contract_is_structural():
    ref = OrgSkillRef("acme", "deploy", "v1")
    provider = SimpleNamespace(
        name="mock", check_requirements=lambda: True,
        list=lambda _org: [ref], pull=lambda _ref: None, propose=lambda _change: None,
    )
    assert isinstance(provider, OrgSkillSyncProvider)
    register_org_skill_sync_provider(provider)
    assert get_org_skill_sync_provider("mock") is provider
    assert unregister_org_skill_sync_provider("mock", provider)


def test_cron_provider_registration_and_fail_safe():
    class MockCron:
        name = "mock-chronos"
        def check_requirements(self): return True
        def reconcile(self, jobs: list[dict]): return None
        def cancel(self, job_id: str): return None

    provider = MockCron()
    register_cron_provider(provider)
    try:
        assert resolve_cron_provider("mock-chronos") is provider
        assert resolve_cron_provider("missing") is None
    finally:
        unregister_cron_provider("mock-chronos", provider)
