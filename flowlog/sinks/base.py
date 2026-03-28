"""
sinks/base.py
-------------
BaseSink — the abstract contract that every sink must implement.

All sinks (terminal, file, Discord, email, etc.) inherit from this.
The Dispatcher only ever calls:
    sink.should_handle(record)  →  bool
    sink.emit(record)           →  None

That's the entire interface. Sinks are responsible for their own
formatting internally — the Dispatcher doesn't touch formatters.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from flowlog.levels import is_level_enabled
from flowlog.record import LogRecord


class BaseSink(ABC):
    """
    Abstract base class for all flowlog sinks.

    Subclasses must implement:
        emit(record) — write/send the log record somewhere

    Subclasses may override:
        should_handle(record) — default checks min_level only
        close()               — default is a no-op
    """

    def __init__(
        self,
        min_level: int = 0,
        name: str | None = None,
    ) -> None:
        """
        Args:
            min_level : Numeric minimum level for this sink.
                        Records below this threshold are silently dropped.
                        Default 0 means accept everything.
            name      : Optional human-readable label for this sink
                        (useful in error messages and config output).
        """
        self.min_level = min_level
        self.name = name or self.__class__.__name__
        self._enabled = True

    # ── Core interface ────────────────────────────────────────────────────────

    def should_handle(self, record: LogRecord) -> bool:
        """
        Returns True if this sink should process the given record.

        Default implementation checks:
            1. Sink is enabled
            2. Record level_no >= sink min_level

        Subclasses can override for custom filtering logic.
        """
        return self._enabled and is_level_enabled(record.level_no, self.min_level)

    @abstractmethod
    def emit(self, record: LogRecord) -> None:
        """
        Write or send the log record.

        This is called by the Dispatcher only after should_handle()
        returns True. Implementations should never raise — catch and
        handle errors internally (e.g. print a warning to stderr).
        """
        ...

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def close(self) -> None:
        """
        Clean up any resources held by this sink (file handles, connections).
        Called by the Logger on shutdown. Default is a no-op.
        """
        pass

    def enable(self) -> None:
        """Re-enable this sink after it has been disabled."""
        self._enabled = True

    def disable(self) -> None:
        """
        Temporarily disable this sink without removing it from the logger.
        Useful for silencing a noisy sink during bulk operations.
        """
        self._enabled = False

    # ── Repr ──────────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        status = "enabled" if self._enabled else "disabled"
        return (
            f"{self.__class__.__name__}("
            f"name={self.name!r}, "
            f"min_level={self.min_level}, "
            f"status={status})"
        )