"""
dispatcher.py
-------------
The Dispatcher is the heart of flowlog.

It receives a LogRecord and fans it out to every registered sink
that passes the should_handle() check. Local sinks (terminal, file)
are called synchronously — they're fast and blocking is fine.
Remote sinks (Discord, email, Telegram, WhatsApp) are pushed onto
a background thread queue so the application never waits for a
network call.

Architecture:
    Logger.error("msg")
        │
        ▼
    Dispatcher.dispatch(record)
        │
        ├── for each sync sink  → sink.emit(record)     (blocking, fast)
        └── for each async sink → queue.put(record)     (non-blocking)
                                        │
                                        ▼
                                  Worker thread
                                  drains queue → sink.emit(record)
"""

from __future__ import annotations

import queue
import sys
import threading
from typing import TYPE_CHECKING

from flowlog.sinks.base import BaseSink

if TYPE_CHECKING:
    from flowlog.record import LogRecord


# Sentinel value pushed onto the queue to tell the worker thread to stop
_STOP = object()


class Dispatcher:
    """
    Fans out a LogRecord to all registered sinks.

    Sinks are registered as either:
        sync  — called directly in the logging thread (terminal, file)
        async — queued to a background worker thread (Discord, email, etc.)

    Args:
        queue_size : Max items in the async queue before it blocks.
                     Default 1000 — should never be hit in normal use.
    """

    def __init__(self, queue_size: int = 1000) -> None:
        self._sync_sinks:  list[BaseSink] = []
        self._async_sinks: list[BaseSink] = []

        # Background thread infrastructure
        self._queue:  queue.Queue  = queue.Queue(maxsize=queue_size)
        self._worker: threading.Thread | None = None
        self._running = False

    # ── Sink registration ─────────────────────────────────────────────────────

    def add_sink(self, sink: BaseSink, *, asynchronous: bool = False) -> None:
        """
        Register a sink with the dispatcher.

        Args:
            sink        : Any BaseSink subclass.
            asynchronous: If True, this sink's emit() is called from the
                          background worker thread rather than the calling
                          thread. Use for any sink that makes network calls.
        """
        if asynchronous:
            self._async_sinks.append(sink)
            self._ensure_worker_running()
        else:
            self._sync_sinks.append(sink)

    def remove_sink(self, sink: BaseSink) -> None:
        """Remove a sink from whichever list it's in."""
        if sink in self._sync_sinks:
            self._sync_sinks.remove(sink)
        if sink in self._async_sinks:
            self._async_sinks.remove(sink)

    @property
    def all_sinks(self) -> list[BaseSink]:
        """All registered sinks — sync and async combined."""
        return self._sync_sinks + self._async_sinks

    # ── Dispatch ──────────────────────────────────────────────────────────────

    def dispatch(self, record: LogRecord) -> None:
        """
        Fan out a LogRecord to all eligible sinks.

        Sync sinks are called immediately.
        Async sinks are pushed onto the background queue.

        This method is designed to never raise — errors in individual
        sinks are caught and printed to stderr.
        """
        # Sync sinks — called directly
        for sink in self._sync_sinks:
            try:
                if sink.should_handle(record):
                    sink.emit(record)
            except Exception as e:
                print(
                    f"[flowlog] Sync sink '{sink.name}' raised: {e}",
                    file=sys.stderr,
                )

        # Async sinks — check eligibility here to avoid unnecessary queue items
        eligible_async = [
            sink for sink in self._async_sinks
            if sink.should_handle(record)
        ]
        if eligible_async:
            try:
                self._queue.put_nowait((record, eligible_async))
            except queue.Full:
                print(
                    f"[flowlog] Async queue full — dropping record: {record.message}",
                    file=sys.stderr,
                )

    # ── Background worker ─────────────────────────────────────────────────────

    def _ensure_worker_running(self) -> None:
        """Start the background worker thread if it isn't already running."""
        if self._running and self._worker and self._worker.is_alive():
            return

        self._running = True
        self._worker = threading.Thread(
            target=self._worker_loop,
            name="flowlog-worker",
            daemon=True,  # dies automatically when the main program exits
        )
        self._worker.start()

    def _worker_loop(self) -> None:
        """
        Background thread — drains the queue and calls emit() on async sinks.

        Runs until _STOP is received or the thread is otherwise killed.
        Being a daemon thread, it will be killed automatically on program exit.
        """
        while True:
            try:
                item = self._queue.get(timeout=1.0)

                if item is _STOP:
                    break

                record, sinks = item
                for sink in sinks:
                    try:
                        sink.emit(record)
                    except Exception as e:
                        print(
                            f"[flowlog] Async sink '{sink.name}' raised: {e}",
                            file=sys.stderr,
                        )
                self._queue.task_done()

            except queue.Empty:
                # Timeout — loop back and check again
                continue
            except Exception as e:
                print(f"[flowlog] Worker thread error: {e}", file=sys.stderr)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def flush(self) -> None:
        """
        Block until all queued async records have been processed.
        Useful in tests or at graceful shutdown to ensure nothing is dropped.
        """
        self._queue.join()

    def shutdown(self, timeout: float = 5.0) -> None:
        """
        Gracefully stop the dispatcher.

        Flushes the async queue, signals the worker to stop,
        and closes all sinks.

        Args:
            timeout : Seconds to wait for the worker thread to finish.
        """
        # Flush pending async items
        if self._running and self._worker:
            self._queue.put(_STOP)
            self._worker.join(timeout=timeout)
            self._running = False

        # Close all sinks
        for sink in self.all_sinks:
            try:
                sink.close()
            except Exception as e:
                print(
                    f"[flowlog] Error closing sink '{sink.name}': {e}",
                    file=sys.stderr,
                )

    # ── Repr ──────────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"Dispatcher("
            f"sync={len(self._sync_sinks)}, "
            f"async={len(self._async_sinks)}, "
            f"running={self._running})"
        )