"""Bounded best-effort reads for streaming HTTP error response bodies."""

from __future__ import annotations

import logging
import threading
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_ERROR_BODY_MAX_BYTES = 64 * 1024
DEFAULT_ERROR_BODY_TIMEOUT_S = 10.0


def _safe_close(response: httpx.Response) -> None:
    try:
        response.close()
    except Exception:
        pass


def read_streaming_error_body(
    response: httpx.Response,
    *,
    max_bytes: int = DEFAULT_ERROR_BODY_MAX_BYTES,
    timeout_s: float = DEFAULT_ERROR_BODY_TIMEOUT_S,
) -> str:
    """Return at most ``max_bytes`` of a streaming error body by ``timeout_s``.

    The socket drain runs in a daemon worker because a wall-clock check between
    chunks cannot interrupt a transport blocked waiting for its next chunk.
    Closing the response on timeout asks the transport to unblock; the caller
    immediately receives the bytes that had arrived by the deadline.  This is
    an error-diagnostic path, so transport and close errors never replace the
    original HTTP failure.
    """
    try:
        byte_cap = max(0, int(max_bytes))
    except (TypeError, ValueError):
        byte_cap = DEFAULT_ERROR_BODY_MAX_BYTES
    try:
        wait_s = max(0.0, float(timeout_s))
    except (TypeError, ValueError):
        wait_s = DEFAULT_ERROR_BODY_TIMEOUT_S

    chunks: list[bytes] = []
    chunks_lock = threading.Lock()
    done = threading.Event()

    def _drain() -> None:
        total = 0
        try:
            if byte_cap == 0:
                return
            for chunk in response.iter_bytes():
                if not chunk:
                    continue
                remaining = byte_cap - total
                if remaining <= 0:
                    break
                piece = bytes(chunk[:remaining])
                with chunks_lock:
                    chunks.append(piece)
                total += len(piece)
                if len(piece) < len(chunk) or total >= byte_cap:
                    break
        except Exception:
            logger.debug("bounded error-body read failed", exc_info=True)
        finally:
            done.set()

    worker = threading.Thread(
        target=_drain,
        name="bounded-http-error-body",
        daemon=True,
    )
    worker.start()
    finished = done.wait(wait_s)
    if not finished:
        logger.debug("bounded error-body read timed out after %.3gs", wait_s)
    _safe_close(response)

    # A cooperative close normally releases the worker.  Never wait beyond a
    # tiny scheduling yield: a broken transport must remain abandoned.
    if not finished:
        done.wait(0.01)
    with chunks_lock:
        body = b"".join(chunks)
    return body[:byte_cap].decode("utf-8", errors="replace")


def read_error_body_or_default(
    response: httpx.Response,
    *,
    max_bytes: int = DEFAULT_ERROR_BODY_MAX_BYTES,
    timeout_s: float = DEFAULT_ERROR_BODY_TIMEOUT_S,
) -> Optional[str]:
    text = read_streaming_error_body(
        response,
        max_bytes=max_bytes,
        timeout_s=timeout_s,
    )
    return text or None


__all__ = [
    "DEFAULT_ERROR_BODY_MAX_BYTES",
    "DEFAULT_ERROR_BODY_TIMEOUT_S",
    "read_streaming_error_body",
    "read_error_body_or_default",
]
