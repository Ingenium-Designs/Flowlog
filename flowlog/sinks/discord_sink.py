"""
sinks/discord_sink.py
---------------------
DiscordSink — posts log records to a Discord channel via webhook.

Each log record becomes a Discord embed with:
    - Colour coded by level
    - Title = level name + logger name
    - Description = the log message
    - Fields for module, function, line, and extra context
    - Footer with timestamp

Requires: requests
    pip install flowlog[discord]
"""

from __future__ import annotations

import sys
from datetime import timezone
from flowlog.record import LogRecord
from flowlog.sinks.base import BaseSink

try:
    import requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False


# Discord embed colour per level (decimal RGB)
_LEVEL_COLOURS: dict[str, int] = {
    "DEBUG":    0x95A5A6,   # grey
    "INFO":     0x3498DB,   # blue
    "AUDIT":    0x2980B9,   # darker blue
    "WEBHOOK":  0x9B59B6,   # purple
    "WARNING":  0xF39C12,   # orange
    "SECURITY": 0xE74C3C,   # red
    "ERROR":    0xC0392B,   # dark red
    "DEPLOY":   0x2ECC71,   # green
    "CRITICAL": 0xFF0000,   # bright red
}


class DiscordSink(BaseSink):
    """
    Posts log records to a Discord channel via webhook.

    Args:
        webhook_url : Discord webhook URL.
        min_level   : Numeric minimum level threshold.
        username    : Display name for the bot in Discord.
        name        : Sink label.
    """

    def __init__(
        self,
        webhook_url: str,
        min_level:   int = 40,
        username:    str = "flowlog",
        name:        str = "discord",
    ) -> None:
        super().__init__(min_level=min_level, name=name)

        if not _REQUESTS_AVAILABLE:
            raise ImportError(
                "requests is required for DiscordSink. "
                "Run: pip install flowlog[discord]"
            )
        if not webhook_url:
            raise ValueError("DiscordSink requires a webhook_url.")

        self.webhook_url = webhook_url
        self.username    = username

    def emit(self, record: LogRecord) -> None:
        try:
            payload = self._build_payload(record)
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
        except Exception as e:
            print(f"[flowlog DiscordSink] Failed to send: {e}", file=sys.stderr)

    def _build_payload(self, record: LogRecord) -> dict:
        colour = _LEVEL_COLOURS.get(record.level_name, 0x95A5A6)

        fields = [
            {"name": "Module",   "value": f"`{record.module}`",    "inline": True},
            {"name": "Function", "value": f"`{record.func_name}`", "inline": True},
            {"name": "Line",     "value": str(record.line_no),     "inline": True},
        ]

        if record.has_extra:
            import json
            fields.append({
                "name":   "Extra",
                "value":  f"```json\n{json.dumps(record.extra, indent=2, default=str)}\n```",
                "inline": False,
            })

        if record.has_exception:
            # Truncate to Discord's 1024 char field limit
            exc_preview = record.exc_info[:900] + "..." \
                if len(record.exc_info) > 900 else record.exc_info
            fields.append({
                "name":   "Exception",
                "value":  f"```\n{exc_preview}\n```",
                "inline": False,
            })

        embed = {
            "title":       f"{record.level_name} — {record.logger_name}",
            "description": record.message,
            "color":       colour,
            "fields":      fields,
            "footer":      {"text": f"flowlog • {record.timestamp_human}"},
        }

        return {
            "username": self.username,
            "embeds":   [embed],
        }