"""
sinks/file_sink.py
------------------
FileSink — writes log records to a file in any supported format.

Supports:
    - Plain text   (.log, .txt)
    - JSON         (.json)      — one record per line (NDJSON)
    - CSV          (.csv)       — header written on first create
    - Markdown     (.md)        — structured human-readable report

Also supports optional log rotation:
    - max_bytes   : rotate when file exceeds this size (0 = never)
    - backup_count: how many rotated files to keep (default 5)

Rotated files are named: mylog.log.1, mylog.log.2, ...
The most recent backup is always .1
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Literal

from flowlog.record import LogRecord
from flowlog.sinks.base import BaseSink
from flowlog.formatters import text, json_fmt, csv_fmt, markdown


# Supported format literals — used for type hints and validation
FormatType = Literal["text", "json", "csv", "markdown"]


class FileSink(BaseSink):
    """
    Writes log records to a file.

    Args:
        path         : Path to the log file. Parent dirs are created if needed.
        fmt          : Output format — "text", "json", "csv", or "markdown".
        min_level    : Numeric minimum level threshold.
        max_bytes    : Rotate file when it exceeds this many bytes. 0 = never.
        backup_count : Number of rotated backup files to keep.
        encoding     : File encoding (default utf-8).
        name         : Optional sink label.

    Example:
        FileSink("logs/app.log",  fmt="text",     min_level=10)
        FileSink("logs/app.json", fmt="json",     min_level=20)
        FileSink("logs/audit.csv",fmt="csv",      min_level=25)
        FileSink("logs/report.md",fmt="markdown", min_level=30)
    """

    _VALID_FORMATS = {"text", "json", "csv", "markdown"}

    def __init__(
        self,
        path:         str | Path,
        fmt:          FormatType = "text",
        min_level:    int        = 0,
        max_bytes:    int        = 0,
        backup_count: int        = 5,
        encoding:     str        = "utf-8",
        name:         str | None = None,
    ) -> None:
        super().__init__(min_level=min_level, name=name or f"file:{path}")

        if fmt not in self._VALID_FORMATS:
            raise ValueError(
                f"Invalid format '{fmt}'. "
                f"Choose from: {sorted(self._VALID_FORMATS)}"
            )

        self.path         = Path(path)
        self.fmt          = fmt
        self.max_bytes    = max_bytes
        self.backup_count = backup_count
        self.encoding     = encoding
        self._file        = None

        # Ensure parent directory exists
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # Open the file and write CSV header if needed
        self._open()

    # ── emit ──────────────────────────────────────────────────────────────────

    def emit(self, record: LogRecord) -> None:
        try:
            if self.max_bytes and self._should_rotate():
                self._rotate()
            self._write(self._format(record))
        except Exception as e:
            print(f"[flowlog FileSink error] {self.path}: {e}", file=sys.stderr)

    # ── Formatting ────────────────────────────────────────────────────────────

    def _format(self, record: LogRecord) -> str:
        if self.fmt == "text":
            return text.format(record) + "\n\n"
        elif self.fmt == "json":
            return json_fmt.format(record) + "\n"
        elif self.fmt == "csv":
            return csv_fmt.format(record) + "\n"
        elif self.fmt == "markdown":
            return markdown.format(record) + "\n\n"
        # Should never reach here due to __init__ validation
        raise ValueError(f"Unknown format: {self.fmt}")

    # ── File I/O ──────────────────────────────────────────────────────────────

    def _open(self) -> None:
        """Open (or re-open) the log file in append mode."""
        is_new_file = not self.path.exists() or self.path.stat().st_size == 0

        self._file = open(self.path, "a", encoding=self.encoding)

        # Write CSV header once when creating a fresh file
        if self.fmt == "csv" and is_new_file:
            self._write(csv_fmt.header_row() + "\n")

    def _write(self, content: str) -> None:
        if self._file and not self._file.closed:
            self._file.write(content)
            self._file.flush()

    # ── Rotation ──────────────────────────────────────────────────────────────

    def _should_rotate(self) -> bool:
        """Returns True if the current file has exceeded max_bytes."""
        try:
            return self.path.stat().st_size >= self.max_bytes
        except FileNotFoundError:
            return False

    def _rotate(self) -> None:
        """
        Rotate log files. Oldest backup is deleted if backup_count is exceeded.

        Before:  app.log  app.log.1  app.log.2
        After:   app.log  app.log.1  app.log.2  app.log.3
                 (new)    (was app)  (was .1)   (was .2)
        """
        self.close()

        # Shift existing backups: .4 → deleted, .3 → .4, .2 → .3, .1 → .2
        for i in range(self.backup_count - 1, 0, -1):
            src  = Path(f"{self.path}.{i}")
            dest = Path(f"{self.path}.{i + 1}")
            if src.exists():
                if dest.exists():
                    dest.unlink()
                src.rename(dest)

        # Move current log to .1
        backup = Path(f"{self.path}.1")
        if backup.exists():
            backup.unlink()
        if self.path.exists():
            self.path.rename(backup)

        # Open a fresh file
        self._open()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def close(self) -> None:
        if self._file and not self._file.closed:
            self._file.flush()
            self._file.close()