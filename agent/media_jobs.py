"""Portable media job contracts shared by image/video provider plugins.

The contracts intentionally describe work, not any vendor queue. Providers may
execute synchronously or translate a job to their own async API. No job is sent
anywhere merely by constructing it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable


class MediaOperation(str, Enum):
    GENERATE = "generate"
    BATCH = "batch"
    UPSCALE = "upscale"
    EDIT = "edit"
    EXTEND = "extend"


class MediaKind(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


@dataclass(frozen=True)
class MediaJob:
    """Provider-neutral request for one media operation."""

    operation: MediaOperation
    kind: MediaKind
    prompt: str = ""
    inputs: tuple[str, ...] = ()
    count: int = 1
    provider: str | None = None
    model: str | None = None
    options: Mapping[str, Any] = field(default_factory=dict)
    idempotency_key: str | None = None

    def __post_init__(self) -> None:
        if self.count < 1 or self.count > 100:
            raise ValueError("media job count must be between 1 and 100")
        if self.operation in {MediaOperation.UPSCALE, MediaOperation.EDIT, MediaOperation.EXTEND} and not self.inputs:
            raise ValueError(f"{self.operation.value} requires at least one input")
        if self.operation is MediaOperation.EXTEND and self.kind is not MediaKind.VIDEO:
            raise ValueError("extend is only valid for video jobs")
        if self.operation is MediaOperation.BATCH and self.count < 2:
            raise ValueError("batch jobs require count >= 2")


@dataclass(frozen=True)
class MediaArtifact:
    uri: str
    kind: MediaKind
    mime_type: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MediaJobResult:
    job_id: str
    status: str
    artifacts: tuple[MediaArtifact, ...] = ()
    error: str | None = None
    provider_payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in {"queued", "running", "succeeded", "failed", "cancelled"}:
            raise ValueError(f"unsupported media job status: {self.status}")
        if self.status == "failed" and not self.error:
            raise ValueError("failed media jobs require an error")


@runtime_checkable
class MediaJobProvider(Protocol):
    """Optional queue seam implemented by media backends with job APIs."""

    @property
    def name(self) -> str: ...

    def supports_operation(self, operation: MediaOperation, kind: MediaKind) -> bool: ...

    def submit_job(self, job: MediaJob) -> MediaJobResult: ...

    def get_job(self, job_id: str) -> MediaJobResult: ...

    def cancel_job(self, job_id: str) -> bool: ...


def batch_job(kind: MediaKind, prompts: Sequence[str], **kwargs: Any) -> MediaJob:
    """Build one validated batch job while retaining prompts portably."""
    cleaned = tuple(str(p).strip() for p in prompts if str(p).strip())
    if len(cleaned) < 2:
        raise ValueError("at least two non-empty prompts are required")
    options = dict(kwargs.pop("options", {}) or {})
    options["prompts"] = cleaned
    return MediaJob(operation=MediaOperation.BATCH, kind=kind, count=len(cleaned), options=options, **kwargs)
