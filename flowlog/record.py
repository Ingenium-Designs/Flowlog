"""
record.py
---------
Defines LogRecord — the single data object created for every log call.

Every formatter and every sink receives exactly one LogRecord.
Nothing else is passed around. This keeps the contract clean and
makes it trivial to add new formatters or sinks later without
touching the core dispatch logic.
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class LogRecord:
    """
    Immutable-ish snapshot of a single log event.

    Created once per log call by the Logger, then passed read-only
    to the Dispatcher, formatters, and sinks.

    Attributes:
        level_name   : String name of the level e.g. "ERROR"
        level_no     : Numeric value of the level e.g. 40
        message      : The log message string
        timestamp    : UTC datetime the record was created
        logger_name  : Name given to the Logger instance e.g. "riff.inventory"
        module       : Filename of the calling module e.g. "inventory.py"
        func_name    : Name of the calling function e.g. "update_listing"
        line_no      : Line number of the log call
        extra        : Optional dict of arbitrary contextual data
        exc_info     : Optional formatted exception traceback string
    """

    level_name:  str
    level_no:    int
    message:     str
    timestamp:   datetime
    logger_name: str
    module:      str
    func_name:   str
    line_no:     int
    extra:       dict[str, Any]        = field(default_factory=dict)
    exc_info:    str | None            = field(default=None)

    # ── Convenience properties ────────────────────────────────────────────────

    @property
    def timestamp_iso(self) -> str:
        """ISO 8601 UTC string e.g. '2026-03-28T14:32:01.443Z'"""
        return self.timestamp.strftime("%Y-%m-%dT%H:%M:%S.") + \
               f"{self.timestamp.microsecond // 1000:03d}Z"

    @property
    def timestamp_human(self) -> str:
        """Human-readable local-ish string e.g. '2026-03-28 14:32:01'"""
        return self.timestamp.strftime("%Y-%m-%d %H:%M:%S")

    @property
    def has_extra(self) -> bool:
        return bool(self.extra)

    @property
    def has_exception(self) -> bool:
        return self.exc_info is not None

    # ── Dict representation ───────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """
        Full dictionary representation of the record.
        Used by the JSON formatter and any sink that needs
        structured data rather than a formatted string.
        """
        data: dict[str, Any] = {
            "timestamp":   self.timestamp_iso,
            "level":       self.level_name,
            "level_no":    self.level_no,
            "logger":      self.logger_name,
            "module":      self.module,
            "function":    self.func_name,
            "line":        self.line_no,
            "message":     self.message,
        }
        if self.has_extra:
            data["extra"] = self.extra
        if self.has_exception:
            data["exception"] = self.exc_info
        return data

    def __repr__(self) -> str:
        return (
            f"LogRecord("
            f"level={self.level_name}, "
            f"message={self.message!r}, "
            f"ts={self.timestamp_iso})"
        )


# ── Factory function ──────────────────────────────────────────────────────────

def build_record(
    level_name:  str,
    level_no:    int,
    message:     str,
    logger_name: str,
    module:      str,
    func_name:   str,
    line_no:     int,
    extra:       dict[str, Any] | None = None,
    exc:         BaseException | None  = None,
) -> LogRecord:
    """
    Factory that creates a LogRecord with a UTC timestamp baked in.

    The Logger calls this — nothing else should construct LogRecords directly. 

    Args:
        level_name   : e.g. "ERROR"
        level_no     : e.g. 40
        message      : The log message
        logger_name  : Name of the logger instance
        module       : Calling filename
        func_name    : Calling function name
        line_no      : Calling line number
        extra        : Optional context dict
        exc          : Optional live exception — will be formatted to a string

    Returns:
        A fully populated LogRecord, timestamped in UTC.
    """
    exc_string: str | None = None
    if exc is not None:
        exc_string = "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        ).strip()

    return LogRecord(
        level_name  = level_name,
        level_no    = level_no,
        message     = message,
        timestamp   = datetime.now(tz=timezone.utc),
        logger_name = logger_name,
        module      = module,
        func_name   = func_name,
        line_no     = line_no,
        extra       = extra or {},
        exc_info    = exc_string,
    )