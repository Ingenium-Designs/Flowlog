"""
logger.py
---------
The Logger class — the single public interface for flowlog.

Usage:
    from flowlog import Logger

    log = Logger("myapp")
    log.info("Server started")
    log.error("DB connection lost", extra={"host": "db.internal"})
    log.critical("System down", exc=some_exception)

Or with config:
    log = Logger(config="flowlog.yaml")
    log = Logger(config={"logger_name": "riff", "sinks": {...}})

The Logger:
    1. Captures the calling frame (module, function, line)
    2. Builds a LogRecord via build_record()
    3. Passes it to the Dispatcher for fan-out to all sinks
"""

from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path
from typing import Any, cast

from flowlog.levels import (
    ALL_LEVELS, get_level,
    DEBUG, INFO, AUDIT, WEBHOOK,
    WARNING, SECURITY, ERROR, DEPLOY, CRITICAL,
)
from flowlog.record import build_record, LogRecord
from flowlog.dispatcher import Dispatcher
from flowlog.config import load_config, FlowlogConfig
from flowlog.sinks.file_sink import FormatType


class Logger:
    """
    The main flowlog Logger.

    Args:
        name   : Logger instance name e.g. "riff.inventory".
                 Overrides config logger_name if provided.
        config : Configuration source. One of:
                   - None          → defaults + auto-discover flowlog.yaml/json
                   - str / Path    → path to a YAML or JSON config file
                   - dict          → inline config overrides
                   - FlowlogConfig → pre-built config object

    Examples:
        # Zero config — terminal only, DEBUG and above
        log = Logger()

        # Named logger with auto-discovered config file
        log = Logger("riff.inventory")

        # Explicit config file
        log = Logger(config="flowlog.yaml")

        # Inline overrides
        log = Logger("myapp", config={
            "sinks": {
                "terminal": {"min_level": "WARNING"},
                "file_text": {"enabled": True, "path": "logs/app.log"},
            }
        })
    """

    def __init__(
        self,
        name:   str | None = None,
        config: str | Path | dict | FlowlogConfig | None = None,
    ) -> None:
        # ── Build config ──────────────────────────────────────────────────────
        if isinstance(config, FlowlogConfig):
            self._config = config
        elif isinstance(config, dict):
            self._config = load_config(config_path=None, overrides=config)
        elif isinstance(config, (str, Path)):
            self._config = load_config(config_path=config)
        else:
            self._config = load_config()

        # Name argument overrides config
        self._name = name or self._config.logger_name

        # ── Build dispatcher + sinks from config ──────────────────────────────
        self._dispatcher = Dispatcher(queue_size=self._config.queue_size)
        self._build_sinks()

    # ── Sink builder ──────────────────────────────────────────────────────────

    def _build_sinks(self) -> None:
        """Instantiate and register all enabled sinks from config."""
        cfg = self._config.sinks

        # Terminal
        if cfg.terminal.enabled:
            from flowlog.sinks.terminal import TerminalSink
            self._dispatcher.add_sink(TerminalSink(
                min_level     = get_level(cfg.terminal.min_level).level_no,
                show_location = cfg.terminal.show_location,
                show_extra    = cfg.terminal.show_extra,
            ))

        # File sinks
        from flowlog.sinks.file_sink import FileSink
        for attr, fmt in [
            ("file_text",     "text"),
            ("file_json",     "json"),
            ("file_csv",      "csv"),
            ("file_markdown", "markdown"),
        ]:
            fc = getattr(cfg, attr)
            if fc.enabled and fc.path:
                self._dispatcher.add_sink(FileSink(
                    path         = fc.path,
                    fmt          = cast(FormatType, fmt),
                    min_level    = get_level(fc.min_level).level_no,
                    max_bytes    = fc.max_bytes,
                    backup_count = fc.backup_count,
                ))

        # Discord
        if cfg.discord.enabled and cfg.discord.webhook_url:
            try:
                from flowlog.sinks.discord_sink import DiscordSink
                self._dispatcher.add_sink(
                    DiscordSink(
                        webhook_url = cfg.discord.webhook_url,
                        min_level   = get_level(cfg.discord.min_level).level_no,
                    ),
                    asynchronous=True,
                )
            except ImportError as e:
                print(f"[flowlog] Discord sink skipped: {e}", file=sys.stderr)

        # Email
        if cfg.email.enabled and cfg.email.smtp_host:
            try:
                from flowlog.sinks.email_sink import EmailSink
                self._dispatcher.add_sink(
                    EmailSink(
                        smtp_host     = cfg.email.smtp_host,
                        smtp_port     = cfg.email.smtp_port,
                        smtp_user     = cfg.email.smtp_user,
                        smtp_password = cfg.email.smtp_password,
                        from_addr     = cfg.email.from_addr,
                        to_addrs      = cfg.email.to_addrs,
                        use_tls       = cfg.email.use_tls,
                        min_level     = get_level(cfg.email.min_level).level_no,
                    ),
                    asynchronous=True,
                )
            except (ImportError, ValueError) as e:
                print(f"[flowlog] Email sink skipped: {e}", file=sys.stderr)

        # Telegram
        if cfg.telegram.enabled and cfg.telegram.bot_token:
            try:
                from flowlog.sinks.telegram_sink import TelegramSink
                self._dispatcher.add_sink(
                    TelegramSink(
                        bot_token = cfg.telegram.bot_token,
                        chat_id   = cfg.telegram.chat_id,
                        min_level = get_level(cfg.telegram.min_level).level_no,
                    ),
                    asynchronous=True,
                )
            except (ImportError, ValueError) as e:
                print(f"[flowlog] Telegram sink skipped: {e}", file=sys.stderr)

        # WhatsApp
        if cfg.whatsapp.enabled and cfg.whatsapp.account_sid:
            try:
                from flowlog.sinks.whatsapp_sink import WhatsAppSink
                self._dispatcher.add_sink(
                    WhatsAppSink(
                        account_sid = cfg.whatsapp.account_sid,
                        auth_token  = cfg.whatsapp.auth_token,
                        from_number = cfg.whatsapp.from_number,
                        to_number   = cfg.whatsapp.to_number,
                        min_level   = get_level(cfg.whatsapp.min_level).level_no,
                    ),
                    asynchronous=True,
                )
            except (ImportError, ValueError) as e:
                print(f"[flowlog] WhatsApp sink skipped: {e}", file=sys.stderr)

    # ── Core log method ───────────────────────────────────────────────────────

    def _log(
        self,
        level_name: str,
        message:    str,
        extra:      dict[str, Any] | None = None,
        exc:        BaseException | None  = None,
    ) -> None:
        """
        Internal log method called by all public level methods.

        Captures the calling frame automatically so module/function/line
        always reflect the actual call site, not this internal method.
        """
        level    = ALL_LEVELS[level_name]
        frame    = inspect.stack()[2]  # [0]=_log, [1]=debug/info/etc, [2]=caller
        module   = os.path.basename(frame.filename)
        func     = frame.function
        line     = frame.lineno

        record = build_record(
            level_name  = level_name,
            level_no    = level.level_no,
            message     = message,
            logger_name = self._name,
            module      = module,
            func_name   = func,
            line_no     = line,
            extra       = extra,
            exc         = exc,
        )
        self._dispatcher.dispatch(record)

    # ── Public logging methods — all 9 levels ─────────────────────────────────

    def debug(self, message: str, extra: dict | None = None, exc: BaseException | None = None) -> None:
        """Log at DEBUG level (10) — dev noise, loop ticks, variable dumps."""
        self._log("DEBUG", message, extra, exc)

    def info(self, message: str, extra: dict | None = None, exc: BaseException | None = None) -> None:
        """Log at INFO level (20) — normal operation events."""
        self._log("INFO", message, extra, exc)

    def audit(self, message: str, extra: dict | None = None, exc: BaseException | None = None) -> None:
        """Log at AUDIT level (25) — compliance trail, user actions, data changes."""
        self._log("AUDIT", message, extra, exc)

    def webhook(self, message: str, extra: dict | None = None, exc: BaseException | None = None) -> None:
        """Log at WEBHOOK level (28) — inbound/outbound integration events."""
        self._log("WEBHOOK", message, extra, exc)

    def warning(self, message: str, extra: dict | None = None, exc: BaseException | None = None) -> None:
        """Log at WARNING level (30) — unexpected but app still running."""
        self._log("WARNING", message, extra, exc)

    def security(self, message: str, extra: dict | None = None, exc: BaseException | None = None) -> None:
        """Log at SECURITY level (35) — failed logins, suspicious activity."""
        self._log("SECURITY", message, extra, exc)

    def error(self, message: str, extra: dict | None = None, exc: BaseException | None = None) -> None:
        """Log at ERROR level (40) — something broke, needs attention."""
        self._log("ERROR", message, extra, exc)

    def deploy(self, message: str, extra: dict | None = None, exc: BaseException | None = None) -> None:
        """Log at DEPLOY level (45) — deployments, migrations, releases."""
        self._log("DEPLOY", message, extra, exc)

    def critical(self, message: str, extra: dict | None = None, exc: BaseException | None = None) -> None:
        """Log at CRITICAL level (50) — system down, data loss, immediate action."""
        self._log("CRITICAL", message, extra, exc)

    # ── Dynamic log method ────────────────────────────────────────────────────

    def log(
        self,
        level:   str | int,
        message: str,
        extra:   dict | None = None,
        exc:     BaseException | None = None,
    ) -> None:
        """
        Log at any level by name or number.

        Examples:
            log.log("ERROR", "Something broke")
            log.log(40, "Something broke")
            log.log("AUDIT", "User 42 deleted listing", extra={"listing_id": 42})
        """
        resolved = get_level(level)
        self._log(resolved.name, message, extra, exc)

    # ── Sink management ───────────────────────────────────────────────────────

    def add_sink(self, sink, *, asynchronous: bool = False) -> None:
        """Add a sink to this logger at runtime."""
        self._dispatcher.add_sink(sink, asynchronous=asynchronous)

    def remove_sink(self, sink) -> None:
        """Remove a sink from this logger at runtime."""
        self._dispatcher.remove_sink(sink)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def flush(self) -> None:
        """Block until all queued async log records have been dispatched."""
        self._dispatcher.flush()

    def shutdown(self, timeout: float = 5.0) -> None:
        """
        Flush and shut down the logger gracefully.
        Call this at application exit to ensure no records are dropped.
        """
        self._dispatcher.shutdown(timeout=timeout)

    # ── Context manager support ───────────────────────────────────────────────

    def __enter__(self) -> "Logger":
        return self

    def __exit__(self, *args) -> None:
        self.shutdown()

    # ── Repr ──────────────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._name

    @property
    def sink_count(self) -> int:
        return len(self._dispatcher.all_sinks)

    def __repr__(self) -> str:
        return (
            f"Logger(name={self._name!r}, "
            f"sinks={self.sink_count})"
        )