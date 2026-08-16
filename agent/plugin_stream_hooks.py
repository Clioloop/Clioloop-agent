"""Non-blocking per-consumer observers for portable LLM stream hooks."""
from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger(__name__)
_STOP = object()
_QUEUE_SIZE = 1024


@dataclass
class _Dispatcher:
    hook: str
    callback: Callable[..., Any]
    events: queue.Queue
    thread: threading.Thread | None = None


_lock = threading.Lock()
_dispatchers: dict[tuple[str, int], _Dispatcher] = {}


def _callbacks(hook: str) -> tuple[Callable[..., Any], ...]:
    try:
        from clio_cli.plugins import iter_hook_callbacks
        return iter_hook_callbacks(hook)
    except Exception:
        return ()


def _worker(dispatcher: _Dispatcher) -> None:
    while True:
        item = dispatcher.events.get()
        try:
            if item is _STOP:
                return
            try:
                dispatcher.callback(**dict(item))
            except Exception:
                logger.warning("stream hook %s failed", dispatcher.hook, exc_info=True)
        finally:
            dispatcher.events.task_done()


def _request_stop(dispatcher: _Dispatcher) -> None:
    """Guarantee a stop marker even when a slow observer filled its queue."""
    try:
        dispatcher.events.put_nowait(_STOP)
    except queue.Full:
        try:
            dispatcher.events.get_nowait()
            dispatcher.events.task_done()
        except queue.Empty:
            pass
        try:
            dispatcher.events.put_nowait(_STOP)
        except queue.Full:
            pass


def _for_hook(hook: str) -> list[_Dispatcher]:
    callbacks = _callbacks(hook)
    with _lock:
        active = {id(cb) for cb in callbacks}
        for key in list(_dispatchers):
            if key[0] == hook and key[1] not in active:
                _request_stop(_dispatchers.pop(key))
        result = []
        for callback in callbacks:
            key = (hook, id(callback))
            dispatcher = _dispatchers.get(key)
            if dispatcher is None:
                dispatcher = _Dispatcher(hook, callback, queue.Queue(maxsize=_QUEUE_SIZE))
                dispatcher.thread = threading.Thread(target=_worker, args=(dispatcher,), daemon=True,
                                                     name=f"clio-plugin-stream:{hook}")
                dispatcher.thread.start()
                _dispatchers[key] = dispatcher
            result.append(dispatcher)
        return result


def enqueue_plugin_stream_hook(hook_name: str, **payload: Any) -> bool:
    if hook_name not in {"on_stream_start", "on_stream_delta", "on_stream_end", "on_interim_message"}:
        raise ValueError(f"not a stream hook: {hook_name}")
    queued = False
    for dispatcher in _for_hook(hook_name):
        try:
            dispatcher.events.put_nowait(dict(payload))
            queued = True
        except queue.Full:
            try:
                dispatcher.events.get_nowait(); dispatcher.events.task_done()
                dispatcher.events.put_nowait(dict(payload)); queued = True
            except queue.Empty:
                pass
    return queued


def has_stream_observer_hooks() -> bool:
    return any(_callbacks(name) for name in ("on_stream_start", "on_stream_delta", "on_stream_end"))


def shutdown_plugin_stream_hook_dispatcher(timeout: float = 1.0) -> None:
    with _lock:
        current = list(_dispatchers.values())
        _dispatchers.clear()
    for dispatcher in current:
        _request_stop(dispatcher)
        if dispatcher.thread:
            dispatcher.thread.join(timeout)
