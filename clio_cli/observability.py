"""Privacy-first, dependency-free observability contracts.

Observability is a no-op unless ``CLIO_OBSERVABILITY_ENABLED=1``.  The default
sink is a bounded local JSONL file; remote export is possible only when an
application explicitly installs an :class:`OTLPExporter` implementation.  This
module never opens a network connection and never records prompts/tool input.
"""
from __future__ import annotations

import contextvars
import functools
import inspect
import json
import os
import re
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Optional, Protocol, Sequence, runtime_checkable

_SCHEMA_VERSION = 1
_REDACTED = "[REDACTED]"
_SENSITIVE_KEYS = frozenset({
    "prompt", "messages", "message", "content", "context", "input", "output",
    "arguments", "args", "kwargs", "authorization", "password", "secret",
    "token", "api_key", "apikey", "cookie", "headers", "body", "query",
})
_CORRELATION_KEYS = (
    "trace_id", "span_id", "parent_span_id", "session_id", "turn_id", "model",
    "tool_name", "cron_id", "delegation_id", "gateway_id",
)


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def enabled() -> bool:
    """Return whether capture is enabled.  Off by default."""
    return _truthy(os.getenv("CLIO_OBSERVABILITY_ENABLED"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _new_id(nbytes: int) -> str:
    return uuid.uuid4().hex[: nbytes * 2]


def _redact_text(value: str) -> str:
    try:
        from agent.redact import redact_sensitive_text
        text = redact_sensitive_text(value, force=True)
        # Also cover short assignment-style secrets that intentionally fall
        # below the main redactor's entropy/length thresholds.
        return re.sub(
            r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|token|secret|password|authorization)"
            r"(\s*[:=]\s*)[^\s,;]+",
            lambda match: f"{match.group(1)}{match.group(2)}{_REDACTED}",
            text,
        )
    except Exception:
        # A telemetry redaction failure must fail closed, never pass through
        # the value that could not be inspected.
        return _REDACTED


def redact(value: Any, *, key: str = "", depth: int = 0) -> Any:
    """Recursively redact telemetry values using a deny-by-default policy.

    Prompt-like fields are removed wholesale. Strings are always passed through
    Clio's force-mode secret redactor and bounded to prevent accidental payload
    capture or unbounded local growth.
    """
    normalized = key.lower().replace("-", "_")
    if normalized in _SENSITIVE_KEYS or normalized.endswith(("_token", "_secret", "_password", "_prompt")):
        return _REDACTED
    if depth > 5:
        return "[TRUNCATED]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        text = _redact_text(value)
        return text[:1024] + ("…" if len(text) > 1024 else "")
    if isinstance(value, Mapping):
        return {str(k)[:80]: redact(v, key=str(k), depth=depth + 1) for k, v in list(value.items())[:64]}
    if isinstance(value, (list, tuple, set)):
        return [redact(v, depth=depth + 1) for v in list(value)[:64]]
    return f"<{type(value).__name__}>"


@dataclass(frozen=True)
class Correlation:
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    parent_span_id: Optional[str] = None
    session_id: Optional[str] = None
    turn_id: Optional[str] = None
    model: Optional[str] = None
    tool_name: Optional[str] = None
    cron_id: Optional[str] = None
    delegation_id: Optional[str] = None
    gateway_id: Optional[str] = None

    def merged(self, **values: Any) -> "Correlation":
        clean = {k: str(v)[:256] for k, v in values.items() if k in _CORRELATION_KEYS and v not in (None, "")}
        return replace(self, **clean)


@dataclass(frozen=True)
class EventRecord:
    name: str
    timestamp: str
    correlation: Correlation = field(default_factory=Correlation)
    attributes: Mapping[str, Any] = field(default_factory=dict)
    severity: str = "info"
    schema_version: int = _SCHEMA_VERSION
    record_type: str = "event"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["correlation"] = redact(data["correlation"])
        data["attributes"] = redact(dict(self.attributes))
        return data


@dataclass(frozen=True)
class SpanRecord:
    name: str
    started_at: str
    ended_at: str
    duration_ms: float
    status: str
    correlation: Correlation
    attributes: Mapping[str, Any] = field(default_factory=dict)
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    schema_version: int = _SCHEMA_VERSION
    record_type: str = "span"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["correlation"] = redact(data["correlation"])
        data["attributes"] = redact(dict(self.attributes))
        if data.get("error_message"):
            # Exceptions frequently quote provider payloads. Error type and
            # span status are enough for telemetry; fail closed on the text.
            data["error_message"] = _REDACTED
        return data


@dataclass(frozen=True)
class MetricRecord:
    name: str
    value: float
    timestamp: str
    unit: str = "1"
    correlation: Correlation = field(default_factory=Correlation)
    attributes: Mapping[str, Any] = field(default_factory=dict)
    schema_version: int = _SCHEMA_VERSION
    record_type: str = "metric"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["correlation"] = redact(data["correlation"])
        data["attributes"] = redact(dict(self.attributes))
        return data


@runtime_checkable
class OTLPExporter(Protocol):
    """Optional exporter boundary. Implementations own transport and batching.

    Clio deliberately ships no active network implementation. Exporters are
    installed explicitly with :func:`set_exporter`; failures are swallowed so
    telemetry can never break an agent call path.
    """
    def export(self, records: Sequence[Mapping[str, Any]]) -> None: ...

    def shutdown(self) -> None: ...


class LocalJSONLExporter:
    """Thread-safe, bounded local exporter with one backup rotation."""
    def __init__(self, path: Path | str, *, max_bytes: int = 10 * 1024 * 1024) -> None:
        self.path = Path(path).expanduser()
        self.max_bytes = max(64 * 1024, int(max_bytes))
        self._lock = threading.Lock()

    def export(self, records: Sequence[Mapping[str, Any]]) -> None:
        if not records:
            return
        payload = "".join(json.dumps(redact(dict(r)), ensure_ascii=False, separators=(",", ":")) + "\n" for r in records)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            try:
                if self.path.exists() and self.path.stat().st_size + len(payload.encode("utf-8")) > self.max_bytes:
                    backup = self.path.with_suffix(self.path.suffix + ".1")
                    backup.unlink(missing_ok=True)
                    self.path.replace(backup)
            except OSError:
                pass
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(payload)
            try:
                self.path.chmod(0o600)
            except OSError:
                pass

    def shutdown(self) -> None:
        return None


_context: contextvars.ContextVar[Correlation] = contextvars.ContextVar("clio_observation_context", default=Correlation())
_exporter: Optional[OTLPExporter] = None
_default_exporter: Optional[LocalJSONLExporter] = None
_export_lock = threading.Lock()


def current_correlation() -> Correlation:
    return _context.get()


@contextmanager
def correlation(**values: Any) -> Iterator[Correlation]:
    """Attach correlation fields to all records in this context."""
    merged = current_correlation().merged(**values)
    token = _context.set(merged)
    try:
        yield merged
    finally:
        _context.reset(token)


def set_exporter(exporter: Optional[OTLPExporter]) -> Optional[OTLPExporter]:
    """Install an explicit exporter, returning the previous exporter."""
    global _exporter
    previous, _exporter = _exporter, exporter
    return previous


def exporter_configured() -> bool:
    """Return whether an application explicitly installed an exporter."""
    return _exporter is not None


def _local_path() -> Path:
    configured = os.getenv("CLIO_OBSERVABILITY_PATH")
    if configured:
        return Path(configured)
    home = Path(os.getenv("CLIO_HOME", "~/.clio")).expanduser()
    return home / "observability" / "events.jsonl"


def _emit(record: EventRecord | SpanRecord | MetricRecord) -> None:
    if not enabled():
        return
    global _default_exporter
    try:
        payload = record.to_dict()
        target = _exporter
        if target is None:
            with _export_lock:
                if _default_exporter is None:
                    max_bytes = int(os.getenv("CLIO_OBSERVABILITY_MAX_BYTES", str(10 * 1024 * 1024)))
                    _default_exporter = LocalJSONLExporter(_local_path(), max_bytes=max_bytes)
                target = _default_exporter
        target.export([payload])
    except Exception:
        # Instrumentation must never affect the observed operation.
        return


def event(name: str, *, severity: str = "info", attributes: Optional[Mapping[str, Any]] = None, **correlation_values: Any) -> None:
    if not enabled():
        return
    corr = current_correlation().merged(**correlation_values)
    _emit(EventRecord(name=name[:160], timestamp=_utc_now(), correlation=corr, attributes=attributes or {}, severity=severity[:16]))


def metric(name: str, value: float, *, unit: str = "1", attributes: Optional[Mapping[str, Any]] = None, **correlation_values: Any) -> None:
    if not enabled():
        return
    corr = current_correlation().merged(**correlation_values)
    _emit(MetricRecord(name=name[:160], value=float(value), unit=unit[:32], timestamp=_utc_now(), correlation=corr, attributes=attributes or {}))


def log(name: str, message: str, *, severity: str = "info", **correlation_values: Any) -> None:
    """Export a redacted structured health/operation log, never raw prompts."""
    event(name, severity=severity, attributes={"log_message": _redact_text(str(message))[:1024]}, **correlation_values)


class Span:
    def __init__(self, name: str, *, kind: str = "internal", attributes: Optional[Mapping[str, Any]] = None, **values: Any) -> None:
        self.name, self.kind = name[:160], kind[:32]
        self.attributes = dict(attributes or {})
        self.values = values
        self.correlation = current_correlation()
        self._token: contextvars.Token[Correlation] | None = None
        self._started_wall = ""
        self._started_mono = 0.0
        self._active = False

    def __enter__(self) -> "Span":
        if not enabled():
            return self
        parent = current_correlation()
        trace_id = parent.trace_id or _new_id(16)
        span_id = _new_id(8)
        self.correlation = parent.merged(**self.values, trace_id=trace_id, parent_span_id=parent.span_id, span_id=span_id)
        self._token = _context.set(self.correlation)
        self._started_wall, self._started_mono, self._active = _utc_now(), time.monotonic(), True
        event(self.name + ".start", attributes={"kind": self.kind})
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        if not self._active:
            return False
        ended = _utc_now()
        duration = max(0.0, (time.monotonic() - self._started_mono) * 1000)
        status = "error" if exc_type else "ok"
        attrs = {"kind": self.kind, **self.attributes}
        _emit(SpanRecord(
            name=self.name, started_at=self._started_wall, ended_at=ended,
            duration_ms=round(duration, 3), status=status, correlation=self.correlation,
            attributes=attrs, error_type=getattr(exc_type, "__name__", None),
            error_message=str(exc) if exc is not None else None,
        ))
        metric("clio.operation.duration", duration, unit="ms", attributes={"operation": self.name, "kind": self.kind, "status": status})
        if self._token is not None:
            _context.reset(self._token)
        self._active = False
        return False


def span(name: str, *, kind: str = "internal", attributes: Optional[Mapping[str, Any]] = None, **correlation_values: Any) -> Span:
    return Span(name, kind=kind, attributes=attributes, **correlation_values)


def _call_correlation(func: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any], kind: str, operation: str) -> dict[str, Any]:
    """Extract only safe IDs/labels; never arbitrary argument payloads."""
    values: dict[str, Any] = {}
    try:
        bound = inspect.signature(func).bind_partial(*args, **kwargs).arguments
    except Exception:
        bound = kwargs
    aliases = {
        "session_id": "session_id", "turn_id": "turn_id", "task_id": "turn_id",
        "effective_task_id": "turn_id", "model": "model", "job_id": "cron_id",
        "subagent_id": "delegation_id", "gateway_id": "gateway_id",
    }
    for source, target in aliases.items():
        if bound.get(source) not in (None, ""):
            values[target] = bound[source]
    agent = bound.get("agent") or bound.get("parent_agent")
    if agent is not None:
        for source, target in (("session_id", "session_id"), ("model", "model"), ("_model", "model")):
            candidate = getattr(agent, source, None)
            if candidate not in (None, "") and target not in values:
                values[target] = candidate
    if kind == "tool":
        values.setdefault("tool_name", operation)
    elif kind == "cron":
        job = bound.get("job")
        job_id = job.get("id") if isinstance(job, Mapping) else None
        values.setdefault("cron_id", bound.get("job_id") or job_id)
    elif kind == "delegation":
        values.setdefault("delegation_id", bound.get("subagent_id"))
    elif kind == "gateway" and args:
        values.setdefault("gateway_id", getattr(args[0], "name", None))
    return values


def instrument(operation: str, *, kind: str = "internal") -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Instrument sync or async call paths; effectively free while disabled."""
    def decorate(func: Callable[..., Any]) -> Callable[..., Any]:
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                if not enabled():
                    return await func(*args, **kwargs)
                values = _call_correlation(func, args, kwargs, kind, operation)
                with span(operation, kind=kind, **values):
                    return await func(*args, **kwargs)
            return async_wrapper
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not enabled():
                return func(*args, **kwargs)
            values = _call_correlation(func, args, kwargs, kind, operation)
            with span(operation, kind=kind, **values):
                return func(*args, **kwargs)
        return wrapper
    return decorate


def reset_for_tests() -> None:
    """Reset process-local sink state (test helper; does not alter config)."""
    global _default_exporter, _exporter
    _default_exporter = None
    _exporter = None
    _context.set(Correlation())


__all__ = [
    "Correlation", "EventRecord", "SpanRecord", "MetricRecord", "OTLPExporter",
    "LocalJSONLExporter", "enabled", "redact", "correlation", "current_correlation",
    "set_exporter", "exporter_configured", "event", "metric", "log", "span", "instrument",
]
