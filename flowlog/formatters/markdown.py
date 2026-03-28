"""
formatters/markdown.py
----------------------
Markdown formatter.

Produces structured Markdown output suitable for human-readable
log reports. Each record is rendered as a section with a level
badge, timestamp, message, and optional detail blocks.

Output example:

    ## ⚠ ERROR — 2026-03-28 14:32:01
    **Logger:** `riff.inventory` | **Module:** `inventory.py:84` | **Function:** `update_listing`

    Database connection lost

    <details><summary>Extra context</summary>

    ```json
    {
      "host": "db.riff.internal",
      "retry": 3
    }
    ```

    </details>

    <details><summary>Exception traceback</summary>

    ```
    ConnectionError: Could not reach database
    ...
    ```

    </details>

    ---
"""

import json
from flowlog.record import LogRecord


# ── Level → Markdown heading emoji ───────────────────────────────────────────
_LEVEL_EMOJI: dict[str, str] = {
    "DEBUG":    "🔍",
    "INFO":     "ℹ️",
    "AUDIT":    "📋",
    "WEBHOOK":  "🔗",
    "WARNING":  "⚠️",
    "SECURITY": "🔒",
    "ERROR":    "❌",
    "DEPLOY":   "🚀",
    "CRITICAL": "🚨",
}


def format(record: LogRecord, *, divider: bool = True) -> str:
    """
    Format a LogRecord as a Markdown section string.

    Args:
        record  : The log record to format.
        divider : If True, appends a horizontal rule (---) at the end.
                  Set False when stitching multiple records into one file
                  and adding dividers externally.

    Returns:
        A Markdown string (no trailing newline).
    """
    emoji = _LEVEL_EMOJI.get(record.level_name, "•")
    parts: list[str] = []

    # ── Heading ───────────────────────────────────────────────────────────────
    parts.append(
        f"## {emoji} {record.level_name} — {record.timestamp_human}"
    )

    # ── Meta line ─────────────────────────────────────────────────────────────
    parts.append(
        f"**Logger:** `{record.logger_name}` | "
        f"**Module:** `{record.module}:{record.line_no}` | "
        f"**Function:** `{record.func_name}`"
    )

    # ── Message ───────────────────────────────────────────────────────────────
    parts.append("")
    parts.append(record.message)

    # ── Extra context (collapsible) ───────────────────────────────────────────
    if record.has_extra:
        extra_json = json.dumps(record.extra, indent=2, default=str)
        parts.append("")
        parts.append("<details><summary>Extra context</summary>")
        parts.append("")
        parts.append("```json")
        parts.append(extra_json)
        parts.append("```")
        parts.append("")
        parts.append("</details>")

    # ── Exception traceback (collapsible) ─────────────────────────────────────
    if record.has_exception:
        parts.append("")
        parts.append("<details><summary>Exception traceback</summary>")
        parts.append("")
        parts.append("```")
        parts.append(record.exc_info)
        parts.append("```")
        parts.append("")
        parts.append("</details>")

    # ── Divider ───────────────────────────────────────────────────────────────
    if divider:
        parts.append("")
        parts.append("---")

    return "\n".join(parts)