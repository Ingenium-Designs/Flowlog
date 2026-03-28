"""
sinks/whatsapp_sink.py
----------------------
WhatsAppSink — sends log records via WhatsApp using Twilio's API.

Messages are sent as plain text with level emoji and key details.
Twilio requires both numbers to use the format: whatsapp:+44...

Setup:
    1. Sign up at twilio.com — get account_sid and auth_token
    2. Enable WhatsApp sandbox or a production WhatsApp sender
    3. Use the format whatsapp:+<number> for both from/to

Requires: twilio
    pip install flowlog[whatsapp]
"""

from __future__ import annotations

import sys
from flowlog.record import LogRecord
from flowlog.sinks.base import BaseSink

try:
    from twilio.rest import Client as TwilioClient
    _TWILIO_AVAILABLE = True
except ImportError:
    _TWILIO_AVAILABLE = False


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


class WhatsAppSink(BaseSink):
    """
    Sends log records via WhatsApp using Twilio's API.

    Args:
        account_sid  : Twilio account SID.
        auth_token   : Twilio auth token.
        from_number  : Sender WhatsApp number, e.g. whatsapp:+14155238886
        to_number    : Recipient WhatsApp number, e.g. whatsapp:+447700900000
        min_level    : Numeric minimum level threshold.
        name         : Sink label.
    """

    def __init__(
        self,
        account_sid:  str,
        auth_token:   str,
        from_number:  str,
        to_number:    str,
        min_level:    int = 50,
        name:         str = "whatsapp",
    ) -> None:
        super().__init__(min_level=min_level, name=name)

        if not _TWILIO_AVAILABLE:
            raise ImportError(
                "twilio is required for WhatsAppSink. "
                "Run: pip install flowlog[whatsapp]"
            )
        if not account_sid or not auth_token:
            raise ValueError("WhatsAppSink requires account_sid and auth_token.")
        if not from_number or not to_number:
            raise ValueError("WhatsAppSink requires from_number and to_number.")

        self.from_number = from_number
        self.to_number   = to_number
        self._client     = TwilioClient(account_sid, auth_token)

    def emit(self, record: LogRecord) -> None:
        try:
            body = self._build_message(record)
            self._client.messages.create(
                body=body,
                from_=self.from_number,
                to=self.to_number,
            )
        except Exception as e:
            print(f"[flowlog WhatsAppSink] Failed to send: {e}", file=sys.stderr)

    def _build_message(self, record: LogRecord) -> str:
        import json
        emoji = _LEVEL_EMOJI.get(record.level_name, "•")

        lines = [
            f"{emoji} *{record.level_name}* — {record.logger_name}",
            f"{record.message}",
            f"",
            f"{record.module}:{record.line_no} · {record.func_name}",
            f"{record.timestamp_human}",
        ]

        if record.has_extra:
            extra_str = json.dumps(record.extra, default=str)
            lines.append(f"\nExtra: {extra_str}")

        if record.has_exception:
            exc = record.exc_info[:500] + "..." \
                if len(record.exc_info) > 500 else record.exc_info
            lines.append(f"\n{exc}")

        return "\n".join(lines)