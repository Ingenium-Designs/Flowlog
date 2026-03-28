"""
sinks/telegram_sink.py
----------------------
TelegramSink — sends log records to a Telegram chat via Bot API.

Messages are sent as HTML-formatted Telegram messages with
level emoji, logger name, message, and optional extra context.

Setup:
    1. Create a bot via @BotFather — get your bot_token
    2. Get your chat_id (user, group, or channel)
    3. Add the bot to the target chat

Requires: requests
    pip install flowlog[telegram]
"""

from __future__ import annotations

import sys
from flowlog.record import LogRecord
from flowlog.sinks.base import BaseSink

try:
    import requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False


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

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramSink(BaseSink):
    """
    Sends log records to a Telegram chat via Bot API.

    Args:
        bot_token  : Telegram bot token from @BotFather.
        chat_id    : Target chat, group, or channel ID.
        min_level  : Numeric minimum level threshold.
        name       : Sink label.
    """

    def __init__(
        self,
        bot_token: str,
        chat_id:   str,
        min_level: int = 50,
        name:      str = "telegram",
    ) -> None:
        super().__init__(min_level=min_level, name=name)

        if not _REQUESTS_AVAILABLE:
            raise ImportError(
                "requests is required for TelegramSink. "
                "Run: pip install flowlog[telegram]"
            )
        if not bot_token:
            raise ValueError("TelegramSink requires a bot_token.")
        if not chat_id:
            raise ValueError("TelegramSink requires a chat_id.")

        self.bot_token = bot_token
        self.chat_id   = str(chat_id)
        self._url      = _TELEGRAM_API.format(token=bot_token)

    def emit(self, record: LogRecord) -> None:
        try:
            text = self._build_message(record)
            response = requests.post(
                self._url,
                json={
                    "chat_id":    self.chat_id,
                    "text":       text,
                    "parse_mode": "HTML",
                },
                timeout=10,
            )
            response.raise_for_status()
        except Exception as e:
            print(f"[flowlog TelegramSink] Failed to send: {e}", file=sys.stderr)

    def _build_message(self, record: LogRecord) -> str:
        import json
        emoji = _LEVEL_EMOJI.get(record.level_name, "•")

        lines = [
            f"{emoji} <b>{record.level_name}</b> — <code>{record.logger_name}</code>",
            f"<b>{record.message}</b>",
            f"",
            f"<i>{record.module}:{record.line_no} · {record.func_name}</i>",
            f"<i>{record.timestamp_human}</i>",
        ]

        if record.has_extra:
            extra_str = json.dumps(record.extra, default=str)
            lines.append(f"\n<code>{extra_str}</code>")

        if record.has_exception:
            # Telegram messages cap at 4096 chars — truncate if needed
            exc = record.exc_info[:800] + "..." \
                if len(record.exc_info) > 800 else record.exc_info
            lines.append(f"\n<pre>{exc}</pre>")

        return "\n".join(lines)