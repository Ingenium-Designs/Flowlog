"""
formatters/text.py
------------------
Plain text formatter.

Output example:
    [2026-03-28 14:32:01] [ERROR   ] [riff.inventory] Database connection lost
    Module: inventory.py | Function: update_listing | Line: 84
    Extra: {"host": "db.riff.internal", "retry": 3}
    Exception:
        ConnectionError: Could not reach database
        ...traceback...
"""

import json
from flowlog.record import LogRecord


def format(record: LogRecord, *, include_location: bool = True) -> str:
    """
    Format a LogRecord as a plain text string.

    Args:
        record           : The log record to format.
        include_location : Whether to include module/function/line info.
                           Set False for minimal single-line output.

    Returns:
        A formatted multi-line string (no trailing newline).
    """
    # ── Primary line ──────────────────────────────────────────────────────────
    line = (
        f"[{record.timestamp_human}] "
        f"[{record.level_name:<8}] "
        f"[{record.logger_name}] "
        f"{record.message}"
    )

    parts = [line]

    # ── Location line ─────────────────────────────────────────────────────────
    if include_location:
        parts.append(
            f"  Module: {record.module} | "
            f"Function: {record.func_name} | "
            f"Line: {record.line_no}"
        )

    # ── Extra context ─────────────────────────────────────────────────────────
    if record.has_extra:
        extra_str = json.dumps(record.extra, default=str)
        parts.append(f"  Extra: {extra_str}")

    # ── Exception traceback ───────────────────────────────────────────────────
    if record.has_exception:
        parts.append("  Exception:")
        for exc_line in record.exc_info.splitlines():
            parts.append(f"    {exc_line}")

    return "\n".join(parts)