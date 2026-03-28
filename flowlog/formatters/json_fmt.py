"""
formatters/json_fmt.py
----------------------
JSON formatter.

Output example (pretty=False, single line per record):
    {"timestamp": "2026-03-28T14:32:01.443Z", "level": "ERROR", ...}

Output example (pretty=True, human-readable):
    {
      "timestamp": "2026-03-28T14:32:01.443Z",
      "level": "ERROR",
      ...
    }

The JSON sink writes one record per line (pretty=False) by default,
which makes the output trivially parseable by log ingestion tools
like Grafana Loki, Datadog, or a simple `jq` pipe.
"""

import json
from flowlog.record import LogRecord


def format(record: LogRecord, *, pretty: bool = False) -> str:
    """
    Format a LogRecord as a JSON string.

    Args:
        record : The log record to format.
        pretty : If True, output is indented (2 spaces) for human reading.
                 If False (default), output is a single compact line.

    Returns:
        A JSON string (no trailing newline).
    """
    data = record.to_dict()

    if pretty:
        return json.dumps(data, indent=2, default=str)
    else:
        return json.dumps(data, separators=(",", ":"), default=str)