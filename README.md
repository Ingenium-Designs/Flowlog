# flowlog

A from-scratch Python logging package with multi-sink fan-out, 9 log levels, background thread dispatch, and flexible configuration.

```bash
pip install flowlog
```

---

## Quick start

```python
from flowlog import Logger

log = Logger("myapp")

log.debug("Connecting to database")
log.info("Server started on port 8080")
log.audit("User 42 deleted listing 130099")
log.warning("Response time above threshold")
log.security("Failed login attempt from 91.2.3.4")
log.error("Database query timed out", extra={"timeout_ms": 5000})
log.deploy("v2.3.1 pushed to production")
log.critical("System is down", exc=some_exception)
```

---

## Log levels

| Level | Number | Use case |
| --- | --- | --- |
| `DEBUG` | 10 | Dev noise, loop ticks, variable dumps |
| `INFO` | 20 | Normal operation events |
| `AUDIT` | 25 | Compliance trail — user actions, data changes |
| `WEBHOOK` | 28 | Inbound/outbound integration events |
| `WARNING` | 30 | Unexpected but app still running |
| `SECURITY` | 35 | Failed logins, suspicious activity |
| `ERROR` | 40 | Something broke, needs attention |
| `DEPLOY` | 45 | Deployments, migrations, releases |
| `CRITICAL` | 50 | System down, immediate action needed |

---

## Sinks

Each sink has its own minimum level threshold. One log call fans out to every eligible sink simultaneously. Remote sinks (Discord, email, Telegram, WhatsApp) dispatch on a background thread — your app never waits for a network call.

| Sink | Format | Notes |
| --- | --- | --- |
| Terminal | Colour-coded | `rich` powered, ERROR+ routes to stderr |
| File (text) | Plain text | Optional log rotation |
| File (JSON) | NDJSON | One record per line — Grafana/Loki ready |
| File (CSV) | CSV | Header row auto-written on first create |
| File (Markdown) | Markdown | Collapsible extra + exception blocks |
| Discord | Embed | Colour-coded by level |
| Email | HTML + plain text | Works with any SMTP provider |
| Telegram | HTML | Via Bot API |
| WhatsApp | Plain text | Via Twilio |

---

## Configuration

Config layers merge in order — highest priority wins:

```text
YAML / JSON file  →  .env file  →  code at init time
```

## flowlog.yaml

```yaml
logger_name: myapp
sinks:
  terminal:
    min_level: DEBUG
  file_text:
    enabled: true
    path: logs/app.log
    min_level: INFO
    max_bytes: 10485760
  discord:
    enabled: true
    min_level: ERROR
    webhook_url: ""          # set via FLOWLOG_DISCORD_WEBHOOK_URL
  telegram:
    enabled: true
    min_level: CRITICAL
    bot_token: ""            # set via FLOWLOG_TELEGRAM_BOT_TOKEN
    chat_id: ""              # set via FLOWLOG_TELEGRAM_CHAT_ID
```

## .env

```text
FLOWLOG_DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
FLOWLOG_TELEGRAM_BOT_TOKEN=123456:ABC...
FLOWLOG_TELEGRAM_CHAT_ID=987654321
FLOWLOG_EMAIL_PASSWORD=your-smtp-password
```

## Or inline in code

```python
log = Logger("myapp", config={
    "sinks": {
        "terminal": {"min_level": "WARNING"},
        "file_json": {"enabled": True, "path": "logs/app.json"},
    }
})
```

---

## Environment variables

| Variable | Sink |
| --- | --- |
| `FLOWLOG_LOGGER_NAME` | Logger name |
| `FLOWLOG_DISCORD_WEBHOOK_URL` | Discord webhook URL |
| `FLOWLOG_EMAIL_PASSWORD` | SMTP password |
| `FLOWLOG_TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `FLOWLOG_TELEGRAM_CHAT_ID` | Telegram chat ID |
| `FLOWLOG_WHATSAPP_ACCOUNT_SID` | Twilio account SID |
| `FLOWLOG_WHATSAPP_AUTH_TOKEN` | Twilio auth token |

---

## Optional extras

```bash
pip install flowlog               # core (terminal + file + config)
pip install flowlog[whatsapp]     # + Twilio WhatsApp
pip install flowlog[all]          # everything
pip install flowlog[dev]          # + pytest, twine, build
```

---

## Runtime sink management

```python
from flowlog import Logger
from flowlog.sinks import FileSink

log = Logger("myapp")

# Add a sink at runtime
log.add_sink(FileSink("logs/audit.csv", fmt="csv", min_level=25))

# Remove a sink
log.remove_sink(some_sink)

# Graceful shutdown — flushes async queue before exit
log.shutdown()

# Or use as a context manager
with Logger("myapp") as log:
    log.info("Running")
# shutdown() called automatically
```

---

## Extra context and exceptions

```python
log.error(
    "Database query failed",
    extra={"query": "SELECT ...", "duration_ms": 4200},
)

try:
    do_something_risky()
except Exception as e:
    log.critical("Unhandled exception", exc=e)
```

---

## License

MIT — see [LICENSE](LICENSE)
