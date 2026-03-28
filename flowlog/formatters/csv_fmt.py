"""
formatters/csv_fmt.py
---------------------
CSV formatter.

Each log record becomes one CSV row. The header row is written
separately by the CSV sink on file creation — the formatter
only produces data rows.

Column order:
    timestamp, level, level_no, logger, module, function, line, message, extra, exception

Extra dict is serialised as a JSON string in its column so it
doesn't break the CSV structure. Empty columns are empty strings.

Example row:
    2026-03-28T14:32:01.443Z,ERROR,40,riff.inventory,inventory.py,
    update_listing,84,Database connection lost,"{""host"": ""db.riff.internal""}",
"""

import csv
import io
import json
from flowlog.record import LogRecord


# The canonical column order — used by both the formatter and the sink
# when writing the header row.
COLUMNS = [
    "timestamp",
    "level",
    "level_no",
    "logger",
    "module",
    "function",
    "line",
    "message",
    "extra",
    "exception",
]


def format(record: LogRecord) -> str:
    """
    Format a LogRecord as a single CSV data row string.

    Uses Python's csv module to handle quoting and escaping correctly —
    no manual string concatenation that could break on commas in messages.

    Returns:
        A single CSV row string (no trailing newline).
    """
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)

    writer.writerow([
        record.timestamp_iso,
        record.level_name,
        record.level_no,
        record.logger_name,
        record.module,
        record.func_name,
        record.line_no,
        record.message,
        json.dumps(record.extra, default=str) if record.has_extra else "",
        record.exc_info if record.has_exception else "",
    ])

    # csv.writer always appends \r\n — strip it so the sink controls line endings
    return buf.getvalue().rstrip("\r\n")


def header_row() -> str:
    """
    Returns the CSV header row string.
    Called once by the CSV sink when creating a new file.
    """
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(COLUMNS)
    return buf.getvalue().rstrip("\r\n")