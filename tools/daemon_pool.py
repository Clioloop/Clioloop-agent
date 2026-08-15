"""Daemon-worker variant of :class:`concurrent.futures.ThreadPoolExecutor`.

Used only where an expired operation is explicitly abandoned.  Unlike stdlib
workers these threads are not registered for unconditional interpreter-exit
joining, so a wedged backend cannot prevent Clio from exiting.
"""

from __future__ import annotations

import threading
import weakref
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures.thread import _worker


class DaemonThreadPoolExecutor(ThreadPoolExecutor):
    def _adjust_thread_count(self) -> None:
        if self._idle_semaphore.acquire(timeout=0):
            return

        def weakref_callback(_, queue=self._work_queue):
            queue.put(None)  # type: ignore[arg-type]

        count = len(self._threads)
        if count >= self._max_workers:
            return
        worker = threading.Thread(
            name=f"{self._thread_name_prefix or self}_{count}",
            target=_worker,
            args=(
                weakref.ref(self, weakref_callback),
                self._work_queue,
                self._initializer,
                self._initargs,
            ),
            daemon=True,
        )
        worker.start()
        self._threads.add(worker)  # type: ignore[attr-defined]


__all__ = ["DaemonThreadPoolExecutor"]
