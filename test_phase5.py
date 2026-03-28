"""
test_phase5.py
--------------
Tests for Phase 5 — Config loader.
Run with: python test_phase5.py
"""

import sys
import os
import json
import tempfile
from pathlib import Path

sys.path.insert(0, ".")

from flowlog.config import (
    load_config, FlowlogConfig, SinksConfig,
    TerminalConfig, FileConfig, DiscordConfig,
    EmailConfig, TelegramConfig, WhatsAppConfig,
)

PASS = "✓"
FAIL = "✗"
errors = 0


def check(label: str, condition: bool):
    global errors
    if condition:
        print(f"  {PASS}  {label}")
    else:
        print(f"  {FAIL}  {label}  <-- FAILED")
        errors += 1


# ── Defaults ──────────────────────────────────────────────────────────────────
print("\n── Default config (no files, no env) ──")
config = load_config(config_path=None, env_file=None)

check("logger_name defaults to 'flowlog'",       config.logger_name == "flowlog")
check("queue_size defaults to 1000",             config.queue_size == 1000)
check("terminal enabled by default",             config.sinks.terminal.enabled)
check("terminal min_level defaults to DEBUG",    config.sinks.terminal.min_level == "DEBUG")
check("terminal show_location defaults True",    config.sinks.terminal.show_location)
check("file_text disabled by default",           not config.sinks.file_text.enabled)
check("file_json disabled by default",           not config.sinks.file_json.enabled)
check("file_csv disabled by default",            not config.sinks.file_csv.enabled)
check("file_markdown disabled by default",       not config.sinks.file_markdown.enabled)
check("discord disabled by default",             not config.sinks.discord.enabled)
check("email disabled by default",               not config.sinks.email.enabled)
check("telegram disabled by default",            not config.sinks.telegram.enabled)
check("whatsapp disabled by default",            not config.sinks.whatsapp.enabled)

# ── JSON file config ──────────────────────────────────────────────────────────
print("\n── JSON file config ──")
with tempfile.TemporaryDirectory() as tmpdir:
    cfg_path = Path(tmpdir) / "flowlog.json"
    cfg_path.write_text(json.dumps({
        "logger_name": "myapp",
        "queue_size": 500,
        "sinks": {
            "terminal": {
                "enabled": True,
                "min_level": "WARNING",
                "show_location": False,
            },
            "file_text": {
                "enabled": True,
                "path": "logs/app.log",
                "min_level": "INFO",
                "max_bytes": 10485760,
                "backup_count": 3,
            },
            "discord": {
                "enabled": True,
                "min_level": "ERROR",
                "webhook_url": "https://discord.com/api/webhooks/test",
            },
        }
    }), encoding="utf-8")

    config = load_config(config_path=cfg_path, env_file=None)

    check("logger_name loaded from JSON",            config.logger_name == "myapp")
    check("queue_size loaded from JSON",             config.queue_size == 500)
    check("terminal min_level loaded",               config.sinks.terminal.min_level == "WARNING")
    check("terminal show_location False",            not config.sinks.terminal.show_location)
    check("file_text enabled from JSON",             config.sinks.file_text.enabled)
    check("file_text path correct",                  config.sinks.file_text.path == "logs/app.log")
    check("file_text min_level correct",             config.sinks.file_text.min_level == "INFO")
    check("file_text max_bytes correct",             config.sinks.file_text.max_bytes == 10485760)
    check("file_text backup_count correct",          config.sinks.file_text.backup_count == 3)
    check("discord enabled from JSON",               config.sinks.discord.enabled)
    check("discord webhook_url loaded",              "webhooks/test" in config.sinks.discord.webhook_url)
    check("email still disabled (not in JSON)",      not config.sinks.email.enabled)

# ── YAML file config ──────────────────────────────────────────────────────────
print("\n── YAML file config ──")
try:
    import yaml
    yaml_available = True
except ImportError:
    yaml_available = False

if yaml_available:
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = Path(tmpdir) / "flowlog.yaml"
        cfg_path.write_text("""
logger_name: riff.inventory
queue_size: 2000
sinks:
  terminal:
    enabled: true
    min_level: DEBUG
  file_json:
    enabled: true
    path: logs/riff.json
    min_level: INFO
  telegram:
    enabled: true
    min_level: CRITICAL
    bot_token: test-token-123
    chat_id: "456789"
""", encoding="utf-8")

        config = load_config(config_path=cfg_path, env_file=None)
        check("logger_name from YAML",           config.logger_name == "riff.inventory")
        check("queue_size from YAML",            config.queue_size == 2000)
        check("file_json enabled from YAML",     config.sinks.file_json.enabled)
        check("file_json path from YAML",        config.sinks.file_json.path == "logs/riff.json")
        check("telegram enabled from YAML",      config.sinks.telegram.enabled)
        check("telegram bot_token from YAML",    config.sinks.telegram.bot_token == "test-token-123")
        check("telegram chat_id from YAML",      config.sinks.telegram.chat_id == "456789")
else:
    print("  (skipping YAML tests — pyyaml not installed)")

# ── .env file overrides ───────────────────────────────────────────────────────
print("\n── .env file overrides ──")
with tempfile.TemporaryDirectory() as tmpdir:
    env_path = Path(tmpdir) / ".env"
    env_path.write_text(
        'FLOWLOG_LOGGER_NAME=env-app\n'
        'FLOWLOG_DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/env-test\n'
        'FLOWLOG_TELEGRAM_BOT_TOKEN=env-bot-token\n'
        'FLOWLOG_TELEGRAM_CHAT_ID=999888\n',
        encoding="utf-8",
    )

    # Clear any previously set env vars to isolate this test
    for key in ["FLOWLOG_LOGGER_NAME", "FLOWLOG_DISCORD_WEBHOOK_URL",
                "FLOWLOG_TELEGRAM_BOT_TOKEN", "FLOWLOG_TELEGRAM_CHAT_ID"]:
        os.environ.pop(key, None)

    config = load_config(config_path=None, env_file=env_path)
    check("logger_name from .env",              config.logger_name == "env-app")
    check("discord webhook_url from .env",      "env-test" in config.sinks.discord.webhook_url)
    check("telegram bot_token from .env",       config.sinks.telegram.bot_token == "env-bot-token")
    check("telegram chat_id from .env",         config.sinks.telegram.chat_id == "999888")

    # Clean up
    for key in ["FLOWLOG_LOGGER_NAME", "FLOWLOG_DISCORD_WEBHOOK_URL",
                "FLOWLOG_TELEGRAM_BOT_TOKEN", "FLOWLOG_TELEGRAM_CHAT_ID"]:
        os.environ.pop(key, None)

# ── Code overrides (highest priority) ────────────────────────────────────────
print("\n── Code overrides ──")
with tempfile.TemporaryDirectory() as tmpdir:
    cfg_path = Path(tmpdir) / "flowlog.json"
    cfg_path.write_text(json.dumps({
        "logger_name": "from-file",
        "sinks": {
            "discord": {"enabled": True, "webhook_url": "from-file-url"}
        }
    }), encoding="utf-8")

    config = load_config(
        config_path=cfg_path,
        env_file=None,
        overrides={
            "logger_name": "from-code",
            "sinks": {
                "discord": {"webhook_url": "from-code-url"}
            }
        }
    )
    check("Code override wins over file",        config.logger_name == "from-code")
    check("Code override wins for webhook_url",  config.sinks.discord.webhook_url == "from-code-url")
    check("File value preserved when not overridden", config.sinks.discord.enabled)

# ── Priority chain ────────────────────────────────────────────────────────────
print("\n── Priority chain (file < env < code) ──")
with tempfile.TemporaryDirectory() as tmpdir:
    cfg_path = Path(tmpdir) / "flowlog.json"
    cfg_path.write_text(json.dumps({"logger_name": "file-name"}), encoding="utf-8")
    env_path  = Path(tmpdir) / ".env"
    env_path.write_text("FLOWLOG_LOGGER_NAME=env-name\n", encoding="utf-8")

    os.environ.pop("FLOWLOG_LOGGER_NAME", None)

    # File only
    c1 = load_config(config_path=cfg_path, env_file=None)
    check("File sets logger_name",               c1.logger_name == "file-name")

    # Env overrides file
    c2 = load_config(config_path=cfg_path, env_file=env_path)
    check("Env overrides file",                  c2.logger_name == "env-name")

    # Code overrides env
    c3 = load_config(
        config_path=cfg_path, env_file=env_path,
        overrides={"logger_name": "code-name"}
    )
    check("Code overrides env",                  c3.logger_name == "code-name")

    os.environ.pop("FLOWLOG_LOGGER_NAME", None)

# ── Auto-discovery ────────────────────────────────────────────────────────────
print("\n── Auto-discovery ──")
original_cwd = os.getcwd()
with tempfile.TemporaryDirectory() as tmpdir:
    os.chdir(tmpdir)
    Path("flowlog.json").write_text(
        json.dumps({"logger_name": "auto-discovered"}),
        encoding="utf-8",
    )
    config = load_config(config_path=None, env_file=None)
    check("Auto-discovers flowlog.json in cwd",  config.logger_name == "auto-discovered")
    os.chdir(original_cwd)

# ── Missing file graceful handling ────────────────────────────────────────────
print("\n── Graceful handling ──")
config = load_config(config_path="/nonexistent/path/flowlog.yaml", env_file=None)
check("Missing config file returns defaults",    config.logger_name == "flowlog")

config = load_config(config_path=None, env_file="/nonexistent/.env")
check("Missing .env returns defaults",           config.logger_name == "flowlog")

# ── min_level case insensitivity ──────────────────────────────────────────────
print("\n── min_level case handling ──")
with tempfile.TemporaryDirectory() as tmpdir:
    cfg_path = Path(tmpdir) / "flowlog.json"
    cfg_path.write_text(json.dumps({
        "sinks": {"terminal": {"min_level": "warning"}}
    }), encoding="utf-8")
    config = load_config(config_path=cfg_path, env_file=None)
    check("Lowercase min_level uppercased",      config.sinks.terminal.min_level == "WARNING")

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'─' * 40}")
if errors == 0:
    print("  All tests passed. Phase 5 is solid.\n")
else:
    print(f"  {errors} test(s) failed.\n")
    sys.exit(1)