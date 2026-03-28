"""
config.py
---------
Layered configuration loader for flowlog.

Priority order (highest wins):
    1. Code — values passed directly at Logger init time
    2. Environment variables — from .env file or shell environment
    3. YAML / JSON file — a flowlog.yaml, flowlog.json, or custom path

This means a shared flowlog.yaml can live in the repo, secrets
(.env) override it per-environment, and anything passed in code
overrides everything.

Config structure (YAML example):

    logger_name: myapp
    queue_size: 1000

    sinks:
      terminal:
        enabled: true
        min_level: DEBUG
        show_location: true
        show_extra: true

      file_text:
        enabled: true
        path: logs/app.log
        min_level: INFO
        max_bytes: 10485760    # 10 MB
        backup_count: 5

      file_json:
        enabled: false
        path: logs/app.json
        min_level: INFO

      file_csv:
        enabled: false
        path: logs/audit.csv
        min_level: AUDIT

      file_markdown:
        enabled: false
        path: logs/report.md
        min_level: WARNING

      discord:
        enabled: false
        min_level: ERROR
        webhook_url: ""        # set via FLOWLOG_DISCORD_WEBHOOK_URL

      email:
        enabled: false
        min_level: CRITICAL
        smtp_host: ""
        smtp_port: 587
        smtp_user: ""
        smtp_password: ""      # set via FLOWLOG_EMAIL_PASSWORD
        from_addr: ""
        to_addrs: []

      telegram:
        enabled: false
        min_level: CRITICAL
        bot_token: ""          # set via FLOWLOG_TELEGRAM_BOT_TOKEN
        chat_id: ""

      whatsapp:
        enabled: false
        min_level: CRITICAL
        account_sid: ""        # set via FLOWLOG_WHATSAPP_ACCOUNT_SID
        auth_token: ""         # set via FLOWLOG_WHATSAPP_AUTH_TOKEN
        from_number: ""
        to_number: ""

Environment variable reference:
    FLOWLOG_LOGGER_NAME
    FLOWLOG_DISCORD_WEBHOOK_URL
    FLOWLOG_EMAIL_PASSWORD
    FLOWLOG_TELEGRAM_BOT_TOKEN
    FLOWLOG_TELEGRAM_CHAT_ID
    FLOWLOG_WHATSAPP_ACCOUNT_SID
    FLOWLOG_WHATSAPP_AUTH_TOKEN
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
    _DOTENV_AVAILABLE = True
except ImportError:
    _DOTENV_AVAILABLE = False

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False


# ── Sink config dataclasses ───────────────────────────────────────────────────

@dataclass
class TerminalConfig:
    enabled:       bool = True
    min_level:     str  = "DEBUG"
    show_location: bool = True
    show_extra:    bool = True


@dataclass
class FileConfig:
    enabled:      bool = False
    path:         str  = ""
    min_level:    str  = "INFO"
    fmt:          str  = "text"
    max_bytes:    int  = 0
    backup_count: int  = 5


@dataclass
class DiscordConfig:
    enabled:     bool = False
    min_level:   str  = "ERROR"
    webhook_url: str  = ""


@dataclass
class EmailConfig:
    enabled:       bool      = False
    min_level:     str       = "CRITICAL"
    smtp_host:     str       = ""
    smtp_port:     int       = 587
    smtp_user:     str       = ""
    smtp_password: str       = ""
    from_addr:     str       = ""
    to_addrs:      list[str] = field(default_factory=list)
    use_tls:       bool      = True


@dataclass
class TelegramConfig:
    enabled:   bool = False
    min_level: str  = "CRITICAL"
    bot_token: str  = ""
    chat_id:   str  = ""


@dataclass
class WhatsAppConfig:
    enabled:       bool = False
    min_level:     str  = "CRITICAL"
    account_sid:   str  = ""
    auth_token:    str  = ""
    from_number:   str  = ""
    to_number:     str  = ""


@dataclass
class SinksConfig:
    terminal:      TerminalConfig = field(default_factory=TerminalConfig)
    file_text:     FileConfig     = field(default_factory=lambda: FileConfig(fmt="text"))
    file_json:     FileConfig     = field(default_factory=lambda: FileConfig(fmt="json"))
    file_csv:      FileConfig     = field(default_factory=lambda: FileConfig(fmt="csv"))
    file_markdown: FileConfig     = field(default_factory=lambda: FileConfig(fmt="markdown"))
    discord:       DiscordConfig  = field(default_factory=DiscordConfig)
    email:         EmailConfig    = field(default_factory=EmailConfig)
    telegram:      TelegramConfig = field(default_factory=TelegramConfig)
    whatsapp:      WhatsAppConfig = field(default_factory=WhatsAppConfig)


@dataclass
class FlowlogConfig:
    """
    Top-level configuration object for a flowlog Logger instance.
    All fields have sensible defaults — zero config needed to get started.
    """
    logger_name: str         = "flowlog"
    queue_size:  int         = 1000
    sinks:       SinksConfig = field(default_factory=SinksConfig)


# ── Loader ────────────────────────────────────────────────────────────────────

def load_config(
    config_path: str | Path | None = None,
    env_file:    str | Path | None = ".env",
    overrides:   dict[str, Any]   | None = None,
) -> FlowlogConfig:
    """
    Load and merge flowlog configuration from all sources.

    Args:
        config_path : Path to a YAML or JSON config file.
                      If None, looks for flowlog.yaml then flowlog.json
                      in the current directory.
        env_file    : Path to a .env file. Defaults to ".env" in cwd.
                      Pass None to skip .env loading entirely.
        overrides   : Dict of values to apply last (highest priority).
                      Keys match the FlowlogConfig structure.

    Returns:
        A fully populated FlowlogConfig with all layers merged.
    """
    # Step 1 — load .env into os.environ
    _load_env_file(env_file)

    # Step 2 — load file config (YAML or JSON)
    file_data = _load_file_config(config_path)

    # Step 3 — build base config from file data
    config = _build_config(file_data)

    # Step 4 — apply environment variable overrides
    _apply_env_overrides(config)

    # Step 5 — apply code-level overrides (highest priority)
    if overrides:
        _apply_dict_overrides(config, overrides)

    return config


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load_env_file(env_file: str | Path | None) -> None:
    """Load a .env file into os.environ if it exists."""
    if env_file is None:
        return
    path = Path(env_file)
    if not path.exists():
        return
    if _DOTENV_AVAILABLE:
        load_dotenv(path, override=False)  # don't overwrite already-set env vars
    else:
        # Minimal fallback parser for KEY=VALUE lines
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key   = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value


def _load_file_config(config_path: str | Path | None) -> dict:
    """Load YAML or JSON config file, returning a dict (empty if not found)."""
    if config_path is not None:
        path = Path(config_path)
    else:
        # Auto-discover in current directory
        for candidate in ["flowlog.yaml", "flowlog.yml", "flowlog.json"]:
            candidate_path = Path(candidate)
            if candidate_path.exists():
                path = candidate_path
                break
        else:
            return {}

    if not path.exists():
        return {}

    with open(path, encoding="utf-8") as f:
        if path.suffix in (".yaml", ".yml"):
            if not _YAML_AVAILABLE:
                raise ImportError(
                    "PyYAML is required to load YAML config files. "
                    "Run: pip install pyyaml"
                )
            return yaml.safe_load(f) or {}
        elif path.suffix == ".json":
            return json.load(f) or {}
        else:
            raise ValueError(
                f"Unsupported config file format: {path.suffix}. "
                "Use .yaml, .yml, or .json"
            )


def _build_config(data: dict) -> FlowlogConfig:
    """Build a FlowlogConfig from a raw dict (file data)."""
    config = FlowlogConfig()

    if "logger_name" in data:
        config.logger_name = str(data["logger_name"])
    if "queue_size" in data:
        config.queue_size = int(data["queue_size"])

    sinks_data = data.get("sinks", {})

    # Terminal
    if t := sinks_data.get("terminal"):
        config.sinks.terminal = TerminalConfig(
            enabled       = bool(t.get("enabled",       True)),
            min_level     = str(t.get("min_level",      "DEBUG")).upper(),
            show_location = bool(t.get("show_location", True)),
            show_extra    = bool(t.get("show_extra",    True)),
        )

    # File sinks
    for attr, fmt in [
        ("file_text",     "text"),
        ("file_json",     "json"),
        ("file_csv",      "csv"),
        ("file_markdown", "markdown"),
    ]:
        key = attr.replace("_", " ").replace(" ", "_")
        if f := sinks_data.get(attr) or sinks_data.get(key):
            setattr(config.sinks, attr, FileConfig(
                enabled      = bool(f.get("enabled",      False)),
                path         = str(f.get("path",          "")),
                min_level    = str(f.get("min_level",     "INFO")).upper(),
                fmt          = fmt,
                max_bytes    = int(f.get("max_bytes",     0)),
                backup_count = int(f.get("backup_count",  5)),
            ))

    # Discord
    if d := sinks_data.get("discord"):
        config.sinks.discord = DiscordConfig(
            enabled     = bool(d.get("enabled",     False)),
            min_level   = str(d.get("min_level",   "ERROR")).upper(),
            webhook_url = str(d.get("webhook_url", "")),
        )

    # Email
    if e := sinks_data.get("email"):
        config.sinks.email = EmailConfig(
            enabled       = bool(e.get("enabled",       False)),
            min_level     = str(e.get("min_level",     "CRITICAL")).upper(),
            smtp_host     = str(e.get("smtp_host",     "")),
            smtp_port     = int(e.get("smtp_port",     587)),
            smtp_user     = str(e.get("smtp_user",     "")),
            smtp_password = str(e.get("smtp_password", "")),
            from_addr     = str(e.get("from_addr",     "")),
            to_addrs      = list(e.get("to_addrs",     [])),
            use_tls       = bool(e.get("use_tls",      True)),
        )

    # Telegram
    if tg := sinks_data.get("telegram"):
        config.sinks.telegram = TelegramConfig(
            enabled   = bool(tg.get("enabled",   False)),
            min_level = str(tg.get("min_level", "CRITICAL")).upper(),
            bot_token = str(tg.get("bot_token", "")),
            chat_id   = str(tg.get("chat_id",   "")),
        )

    # WhatsApp
    if wa := sinks_data.get("whatsapp"):
        config.sinks.whatsapp = WhatsAppConfig(
            enabled     = bool(wa.get("enabled",     False)),
            min_level   = str(wa.get("min_level",   "CRITICAL")).upper(),
            account_sid = str(wa.get("account_sid", "")),
            auth_token  = str(wa.get("auth_token",  "")),
            from_number = str(wa.get("from_number", "")),
            to_number   = str(wa.get("to_number",   "")),
        )

    return config


def _apply_env_overrides(config: FlowlogConfig) -> None:
    """
    Apply environment variable overrides to an existing config.
    Env vars only set values — they never enable/disable a sink.
    """
    if v := os.environ.get("FLOWLOG_LOGGER_NAME"):
        config.logger_name = v

    if v := os.environ.get("FLOWLOG_DISCORD_WEBHOOK_URL"):
        config.sinks.discord.webhook_url = v

    if v := os.environ.get("FLOWLOG_EMAIL_PASSWORD"):
        config.sinks.email.smtp_password = v

    if v := os.environ.get("FLOWLOG_TELEGRAM_BOT_TOKEN"):
        config.sinks.telegram.bot_token = v

    if v := os.environ.get("FLOWLOG_TELEGRAM_CHAT_ID"):
        config.sinks.telegram.chat_id = v

    if v := os.environ.get("FLOWLOG_WHATSAPP_ACCOUNT_SID"):
        config.sinks.whatsapp.account_sid = v

    if v := os.environ.get("FLOWLOG_WHATSAPP_AUTH_TOKEN"):
        config.sinks.whatsapp.auth_token = v


def _apply_dict_overrides(config: FlowlogConfig, overrides: dict) -> None:
    """Apply a flat or nested dict of overrides to an existing config."""
    if "logger_name" in overrides:
        config.logger_name = str(overrides["logger_name"])
    if "queue_size" in overrides:
        config.queue_size = int(overrides["queue_size"])

    if sinks := overrides.get("sinks"):
        if terminal := sinks.get("terminal"):
            for k, v in terminal.items():
                if hasattr(config.sinks.terminal, k):
                    setattr(config.sinks.terminal, k, v)
        for attr in ["file_text", "file_json", "file_csv", "file_markdown"]:
            if f := sinks.get(attr):
                for k, v in f.items():
                    if hasattr(getattr(config.sinks, attr), k):
                        setattr(getattr(config.sinks, attr), k, v)
        for attr in ["discord", "email", "telegram", "whatsapp"]:
            if s := sinks.get(attr):
                for k, v in s.items():
                    if hasattr(getattr(config.sinks, attr), k):
                        setattr(getattr(config.sinks, attr), k, v)