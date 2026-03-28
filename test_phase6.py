"""
test_phase6.py
--------------
Tests for Phase 6 — Remote sinks (Discord, Email, Telegram, WhatsApp).

Network calls are mocked — no real credentials needed.
Run with: python test_phase6.py
"""

import sys
import json
import smtplib
from unittest.mock import MagicMock, patch, call
from email.mime.multipart import MIMEMultipart

sys.path.insert(0, ".")

from flowlog.record import build_record
from flowlog.sinks.discord_sink import DiscordSink
from flowlog.sinks.email_sink import EmailSink
from flowlog.sinks.telegram_sink import TelegramSink
from flowlog.sinks.whatsapp_sink import WhatsAppSink

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


# ── Shared test records ───────────────────────────────────────────────────────

basic = build_record(
    level_name="ERROR", level_no=40, message="Database connection lost",
    logger_name="riff.inventory", module="inventory.py",
    func_name="update_listing", line_no=84,
    extra={"host": "db.riff.internal"},
)

critical = build_record(
    level_name="CRITICAL", level_no=50, message="System is down",
    logger_name="riff", module="app.py", func_name="main", line_no=1,
)

try:
    raise RuntimeError("Boom")
except RuntimeError as e:
    exc_record = build_record(
        level_name="CRITICAL", level_no=50, message="Unhandled exception",
        logger_name="riff", module="app.py", func_name="main", line_no=1,
        exc=e,
    )

# ── DiscordSink ───────────────────────────────────────────────────────────────
print("\n── DiscordSink ──")

with patch("flowlog.sinks.discord_sink.requests") as mock_requests:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_requests.post.return_value = mock_response

    sink = DiscordSink(webhook_url="https://discord.com/api/webhooks/test", min_level=0)
    check("DiscordSink instantiates",          sink is not None)
    check("min_level stored correctly",        sink.min_level == 0)
    check("should_handle ERROR",               sink.should_handle(basic))

    sink.emit(basic)
    check("requests.post called once",         mock_requests.post.call_count == 1)

    # Inspect the payload
    call_kwargs = mock_requests.post.call_args
    payload = call_kwargs[1]["json"]
    embed = payload["embeds"][0]

    check("Payload has embeds",                "embeds" in payload)
    check("Embed title contains level name",   "ERROR" in embed["title"])
    check("Embed title contains logger name",  "riff.inventory" in embed["title"])
    check("Embed description is message",      embed["description"] == "Database connection lost")
    check("Embed colour set",                  embed["color"] == 0xC0392B)
    check("Embed has fields",                  len(embed["fields"]) > 0)
    check("Module field present",              any(f["name"] == "Module" for f in embed["fields"]))
    check("Extra field present",               any(f["name"] == "Extra"  for f in embed["fields"]))
    check("Footer has timestamp",              "footer" in embed)

    # Test with exception record
    mock_requests.post.reset_mock()
    sink.emit(exc_record)
    exc_payload = mock_requests.post.call_args[1]["json"]
    exc_embed   = exc_payload["embeds"][0]
    check("Exception field present",           any(f["name"] == "Exception" for f in exc_embed["fields"]))

    # Test missing webhook_url raises
    try:
        DiscordSink(webhook_url="")
        check("Empty webhook_url raises ValueError", False)
    except ValueError:
        check("Empty webhook_url raises ValueError", True)

    # Test level gating
    sink_gated = DiscordSink(webhook_url="https://discord.com/api/webhooks/test", min_level=50)
    check("should_handle blocks ERROR with min=50", not sink_gated.should_handle(basic))
    check("should_handle passes CRITICAL",          sink_gated.should_handle(critical))

# ── EmailSink ─────────────────────────────────────────────────────────────────
print("\n── EmailSink ──")

with patch("flowlog.sinks.email_sink.smtplib.SMTP") as mock_smtp_cls:
    mock_smtp = MagicMock()
    mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp_cls.return_value.__exit__  = MagicMock(return_value=False)

    sink = EmailSink(
        smtp_host="smtp.brevo.com",
        smtp_port=587,
        smtp_user="harry@ingeniumdesigns.co.uk",
        smtp_password="secret",
        from_addr="logs@ingeniumdesigns.co.uk",
        to_addrs=["harry@ingeniumdesigns.co.uk"],
        min_level=0,
    )
    check("EmailSink instantiates",           sink is not None)
    check("should_handle ERROR",              sink.should_handle(basic))

    sink.emit(basic)
    check("SMTP context manager entered",     mock_smtp_cls.called)

    # Verify the message was built correctly
    msg = sink._build_message(basic)
    check("Message is MIMEMultipart",         isinstance(msg, MIMEMultipart))
    check("Subject contains level name",      "ERROR" in msg["Subject"])
    check("Subject contains logger name",     "riff.inventory" in msg["Subject"])
    check("From addr set correctly",          msg["From"] == "logs@ingeniumdesigns.co.uk")
    check("To addr set correctly",            "harry@ingeniumdesigns.co.uk" in msg["To"])

    # Check HTML part contains key info
    parts   = msg.get_payload()
    html_part = next((p for p in parts if p.get_content_type() == "text/html"), None)
    html_body = html_part.get_payload(decode=True).decode("utf-8")
    check("HTML body contains message",       "Database connection lost" in html_body)
    check("HTML body contains logger name",   "riff.inventory" in html_body)
    check("HTML body contains level colour",  "#C0392B" in html_body)
    check("HTML body contains extra",         "db.riff.internal" in html_body)

    # Check plain text part
    plain_part = next((p for p in parts if p.get_content_type() == "text/plain"), None)
    plain_body = plain_part.get_payload(decode=True).decode("utf-8")
    check("Plain text body contains message", "Database connection lost" in plain_body)

    # Validation errors
    try:
        EmailSink(smtp_host="", smtp_port=587, smtp_user="u", smtp_password="p",
                  from_addr="a@b.com", to_addrs=["c@d.com"])
        check("Empty smtp_host raises ValueError", False)
    except ValueError:
        check("Empty smtp_host raises ValueError", True)

    try:
        EmailSink(smtp_host="smtp.test.com", smtp_port=587, smtp_user="u",
                  smtp_password="p", from_addr="a@b.com", to_addrs=[])
        check("Empty to_addrs raises ValueError", False)
    except ValueError:
        check("Empty to_addrs raises ValueError", True)

# ── TelegramSink ──────────────────────────────────────────────────────────────
print("\n── TelegramSink ──")

with patch("flowlog.sinks.telegram_sink.requests") as mock_requests:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_requests.post.return_value = mock_response

    sink = TelegramSink(
        bot_token="123456:ABC-test-token",
        chat_id="987654321",
        min_level=0,
    )
    check("TelegramSink instantiates",         sink is not None)
    check("should_handle ERROR",               sink.should_handle(basic))
    check("URL contains bot token",            "123456" in sink._url)

    sink.emit(basic)
    check("requests.post called",             mock_requests.post.call_count == 1)

    payload = mock_requests.post.call_args[1]["json"]
    check("chat_id correct",                   payload["chat_id"] == "987654321")
    check("parse_mode is HTML",                payload["parse_mode"] == "HTML")
    check("text contains level name",          "ERROR" in payload["text"])
    check("text contains logger name",         "riff.inventory" in payload["text"])
    check("text contains message",             "Database connection lost" in payload["text"])
    check("text contains emoji",               "❌" in payload["text"])
    check("text contains extra",               "db.riff.internal" in payload["text"])

    # Test exception record
    mock_requests.post.reset_mock()
    sink.emit(exc_record)
    exc_payload = mock_requests.post.call_args[1]["json"]
    check("Exception traceback in text",       "RuntimeError" in exc_payload["text"])

    # Validation
    try:
        TelegramSink(bot_token="", chat_id="123")
        check("Empty bot_token raises ValueError", False)
    except ValueError:
        check("Empty bot_token raises ValueError", True)

    try:
        TelegramSink(bot_token="tok", chat_id="")
        check("Empty chat_id raises ValueError", False)
    except ValueError:
        check("Empty chat_id raises ValueError", True)

# ── WhatsAppSink ──────────────────────────────────────────────────────────────
print("\n── WhatsAppSink ──")

import flowlog.sinks.whatsapp_sink as _wa_module
mock_twilio_cls = MagicMock()
_wa_module.TwilioClient = mock_twilio_cls
_wa_module._TWILIO_AVAILABLE = True

if True:
    mock_twilio_cls = _wa_module.TwilioClient
    mock_client   = MagicMock()
    mock_twilio_cls.return_value = mock_client

    sink = WhatsAppSink(
        account_sid="ACtest123",
        auth_token="authtest456",
        from_number="whatsapp:+14155238886",
        to_number="whatsapp:+447700900000",
        min_level=0,
    )
    check("WhatsAppSink instantiates",         sink is not None)
    check("should_handle ERROR",               sink.should_handle(basic))

    sink.emit(basic)
    check("Twilio messages.create called",     mock_client.messages.create.call_count == 1)

    call_kwargs = mock_client.messages.create.call_args[1]
    check("from_ number correct",             call_kwargs["from_"] == "whatsapp:+14155238886")
    check("to number correct",                call_kwargs["to"] == "whatsapp:+447700900000")
    check("body contains level name",         "ERROR" in call_kwargs["body"])
    check("body contains logger name",        "riff.inventory" in call_kwargs["body"])
    check("body contains message",            "Database connection lost" in call_kwargs["body"])
    check("body contains emoji",              "❌" in call_kwargs["body"])
    check("body contains extra",              "db.riff.internal" in call_kwargs["body"])

    # Validation
    try:
        WhatsAppSink(account_sid="", auth_token="tok",
                     from_number="whatsapp:+1", to_number="whatsapp:+2")
        check("Empty account_sid raises ValueError", False)
    except ValueError:
        check("Empty account_sid raises ValueError", True)

    try:
        WhatsAppSink(account_sid="sid", auth_token="tok",
                     from_number="", to_number="whatsapp:+2")
        check("Empty from_number raises ValueError", False)
    except ValueError:
        check("Empty from_number raises ValueError", True)

# ── All sinks importable from flowlog.sinks ───────────────────────────────────
print("\n── Imports ──")
from flowlog.sinks import (
    BaseSink, TerminalSink, FileSink,
    DiscordSink, EmailSink, TelegramSink, WhatsAppSink
)
check("All 7 sinks importable from flowlog.sinks", True)

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'─' * 40}")
if errors == 0:
    print("  All tests passed. Phase 6 is solid.\n")
else:
    print(f"  {errors} test(s) failed.\n")
    sys.exit(1)