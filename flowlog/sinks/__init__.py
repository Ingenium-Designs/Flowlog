from flowlog.sinks.base import BaseSink
from flowlog.sinks.terminal import TerminalSink
from flowlog.sinks.file_sink import FileSink
from flowlog.sinks.discord_sink import DiscordSink
from flowlog.sinks.email_sink import EmailSink
from flowlog.sinks.telegram_sink import TelegramSink
from flowlog.sinks.whatsapp_sink import WhatsAppSink

__all__ = [
    "BaseSink",
    "TerminalSink",
    "FileSink",
    "DiscordSink",
    "EmailSink",
    "TelegramSink",
    "WhatsAppSink",
]
