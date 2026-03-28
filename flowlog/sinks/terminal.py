"""
sinks/terminal.py
-----------------
TerminalSink — colour-coded log output to the terminal using rich.

Each level gets a distinct colour and style so logs are scannable
at a glance. The layout is compact but information-dense.

Example output (rendered with colour in a real terminal):

    14:32:01  ERROR     riff.inventory   Database connection lost
                        inventory.py:84  update_listing
"""

from __future__ import annotations

import sys
from flowlog.record import LogRecord
from flowlog.sinks.base import BaseSink

try:
    from rich.console import Console
    from rich.text import Text
    from rich.columns import Columns
    _RICH_AVAILABLE = True
except ImportError:
    _RICH_AVAILABLE = False


# ── Level colour map ──────────────────────────────────────────────────────────
# Maps level name → (label_style, message_style)
# rich style strings: colour names, bold, dim, italic, etc.
_LEVEL_STYLES: dict[str, tuple[str, str]] = {
    "DEBUG":    ("dim white",          "dim white"),
    "INFO":     ("bold cyan",          "white"),
    "AUDIT":    ("bold blue",          "bright_white"),
    "WEBHOOK":  ("bold magenta",       "bright_white"),
    "WARNING":  ("bold yellow",        "yellow"),
    "SECURITY": ("bold bright_red",    "bright_red"),
    "ERROR":    ("bold red",           "bright_white"),
    "DEPLOY":   ("bold bright_green",  "bright_green"),
    "CRITICAL": ("bold white on red",  "bold white on red"),
}


class TerminalSink(BaseSink):
    """
    Writes colour-coded log output to stdout (or stderr for ERROR+).

    Args:
        min_level        : Numeric minimum level threshold.
        stderr_threshold : Records at or above this level_no go to stderr.
                           Default 40 (ERROR and above).
        show_location    : Whether to show module/line/function beneath message.
        show_extra       : Whether to print the extra dict when present.
        force_plain      : If True, skip rich entirely and use plain print().
                           Auto-detected if rich is not installed.
    """

    def __init__(
        self,
        min_level:        int  = 0,
        stderr_threshold: int  = 40,
        show_location:    bool = True,
        show_extra:       bool = True,
        force_plain:      bool = False,
        name:             str  = "terminal",
    ) -> None:
        super().__init__(min_level=min_level, name=name)
        self.stderr_threshold = stderr_threshold
        self.show_location    = show_location
        self.show_extra       = show_extra
        self._use_rich        = _RICH_AVAILABLE and not force_plain

        if self._use_rich:
            self._stdout = Console(file=sys.stdout, highlight=False)
            self._stderr = Console(file=sys.stderr, highlight=False)

    # ── emit ──────────────────────────────────────────────────────────────────

    def emit(self, record: LogRecord) -> None:
        try:
            if self._use_rich:
                self._emit_rich(record)
            else:
                self._emit_plain(record)
        except Exception as e:
            # Never let a sink crash the application
            print(f"[flowlog TerminalSink error] {e}", file=sys.stderr)

    # ── Rich rendering ────────────────────────────────────────────────────────

    def _emit_rich(self, record: LogRecord) -> None:
        console = (
            self._stderr
            if record.level_no >= self.stderr_threshold
            else self._stdout
        )

        label_style, msg_style = _LEVEL_STYLES.get(
            record.level_name, ("white", "white")
        )

        # Time — always dim, keeps it subtle
        time_text = Text(record.timestamp_human.split(" ")[1], style="dim white")

        # Level badge — padded to 8 chars for alignment
        level_text = Text(f"{record.level_name:<8}", style=label_style)

        # Logger name
        logger_text = Text(f"{record.logger_name:<20}", style="dim cyan")

        # Message
        message_text = Text(record.message, style=msg_style)

        # Primary row: time | level | logger | message
        console.print(
            time_text, level_text, logger_text, message_text,
            sep="  ",
            end="\n",
        )

        # Location line (indented under the message)
        if self.show_location:
            location = Text(
                f"{'':30}{record.module}:{record.line_no}  {record.func_name}",
                style="dim white",
            )
            console.print(location)

        # Extra context
        if self.show_extra and record.has_extra:
            import json
            extra_str = json.dumps(record.extra, default=str)
            extra_text = Text(
                f"{'':30}extra: {extra_str}",
                style="dim magenta",
            )
            console.print(extra_text)

        # Exception traceback
        if record.has_exception:
            console.print(
                Text(record.exc_info, style="dim red")
            )

    # ── Plain fallback ────────────────────────────────────────────────────────

    def _emit_plain(self, record: LogRecord) -> None:
        target = (
            sys.stderr
            if record.level_no >= self.stderr_threshold
            else sys.stdout
        )
        line = (
            f"{record.timestamp_human.split(' ')[1]}  "
            f"{record.level_name:<8}  "
            f"{record.logger_name:<20}  "
            f"{record.message}"
        )
        print(line, file=target)
        if self.show_location:
            print(
                f"{'':30}{record.module}:{record.line_no}  {record.func_name}",
                file=target,
            )
        if record.has_exception:
            print(record.exc_info, file=target)