"""Chronos external one-shot cron provider foundation.

This portable seam targets a user-configured scheduler endpoint. It contains no
Nous-specific URLs, credentials, audiences or JWT assumptions. Omni deployments
may point it at an existing authenticated portal route.
"""
from __future__ import annotations
import os
from typing import Any, Callable


class ChronosCronProvider:
    name = "chronos"

    def __init__(self, transport: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None):
        self._transport = transport
        self._armed: dict[str, str] = {}

    @staticmethod
    def _endpoint() -> str:
        base = os.getenv("CHRONOS_ENDPOINT") or os.getenv("OMNI_PORTAL_URL") or ""
        return base.strip().rstrip("/")

    def check_requirements(self) -> bool:
        if not (self._endpoint() and os.getenv("CHRONOS_CALLBACK_URL", "").strip()):
            return False
        if self._transport is not None:
            return True
        try:
            import httpx  # noqa: F401
        except ImportError:
            return False
        return bool(os.getenv("CHRONOS_TOKEN", "").strip())

    def _request(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self._transport is not None:
            return self._transport(action, payload)
        import httpx
        response = httpx.post(
            f"{self._endpoint()}/{action.lstrip('/')}",
            headers={"Authorization": f"Bearer {os.environ['CHRONOS_TOKEN']}"},
            json=payload,
            timeout=15,
        )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise RuntimeError("Chronos returned a non-object response")
        return body

    def arm(self, job: dict[str, Any]) -> None:
        job_id = str(job.get("id") or "").strip()
        fire_at = str(job.get("next_run_at") or "").strip()
        if not job_id or not fire_at:
            return
        payload = {"job_id": job_id, "fire_at": fire_at,
                   "callback_url": os.environ["CHRONOS_CALLBACK_URL"],
                   "idempotency_key": f"{job_id}:{fire_at}"}
        self._request("cron/provision", payload)
        self._armed[job_id] = fire_at

    def cancel(self, job_id: str) -> None:
        self._request("cron/cancel", {"job_id": str(job_id)})
        self._armed.pop(str(job_id), None)

    def reconcile(self, jobs: list[dict[str, Any]]) -> None:
        desired = {str(j["id"]): str(j["next_run_at"]) for j in jobs
                   if j.get("enabled", True) and j.get("state") != "paused" and j.get("next_run_at")}
        for job in jobs:
            job_id = str(job.get("id") or "")
            if job_id in desired and self._armed.get(job_id) != desired[job_id]:
                self.arm(job)
        for job_id in set(self._armed) - set(desired):
            self.cancel(job_id)


def check_requirements() -> bool:
    return ChronosCronProvider().check_requirements()


def register(ctx) -> None:
    ctx.register_cron_provider(ChronosCronProvider())
