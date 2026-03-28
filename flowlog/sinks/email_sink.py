"""
sinks/email_sink.py
-------------------
EmailSink — sends log records as emails via SMTP.

Each log record becomes an email with:
    - Subject: [LEVEL] logger_name — message (truncated)
    - Plain text body with full record details
    - HTML body with formatted layout

Supports TLS (port 587) and SSL (port 465).
Works with any SMTP provider — Gmail, Brevo, Outlook, etc.

Requires: nothing extra (smtplib is stdlib)
"""

from __future__ import annotations

import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flowlog.record import LogRecord
from flowlog.sinks.base import BaseSink
from flowlog.formatters import text as text_fmt


class EmailSink(BaseSink):
    """
    Sends log records as emails via SMTP.

    Args:
        smtp_host     : SMTP server hostname (e.g. smtp.brevo.com)
        smtp_port     : SMTP port. 587 for TLS, 465 for SSL.
        smtp_user     : SMTP login username.
        smtp_password : SMTP login password.
        from_addr     : Sender email address.
        to_addrs      : List of recipient email addresses.
        use_tls       : If True, use STARTTLS (port 587). If False, use SSL (port 465).
        min_level     : Numeric minimum level threshold.
        name          : Sink label.
    """

    def __init__(
        self,
        smtp_host:     str,
        smtp_port:     int,
        smtp_user:     str,
        smtp_password: str,
        from_addr:     str,
        to_addrs:      list[str],
        use_tls:       bool = True,
        min_level:     int  = 50,
        name:          str  = "email",
    ) -> None:
        super().__init__(min_level=min_level, name=name)

        if not smtp_host:
            raise ValueError("EmailSink requires smtp_host.")
        if not from_addr:
            raise ValueError("EmailSink requires from_addr.")
        if not to_addrs:
            raise ValueError("EmailSink requires at least one to_addr.")

        self.smtp_host     = smtp_host
        self.smtp_port     = smtp_port
        self.smtp_user     = smtp_user
        self.smtp_password = smtp_password
        self.from_addr     = from_addr
        self.to_addrs      = to_addrs
        self.use_tls       = use_tls

    def emit(self, record: LogRecord) -> None:
        try:
            msg = self._build_message(record)
            self._send(msg)
        except Exception as e:
            print(f"[flowlog EmailSink] Failed to send: {e}", file=sys.stderr)

    def _build_message(self, record: LogRecord) -> MIMEMultipart:
        subject = (
            f"[{record.level_name}] {record.logger_name} — "
            f"{record.message[:80]}{'...' if len(record.message) > 80 else ''}"
        )

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = self.from_addr
        msg["To"]      = ", ".join(self.to_addrs)

        # Plain text part
        plain = text_fmt.format(record, include_location=True)
        msg.attach(MIMEText(plain, "plain", "utf-8"))

        # HTML part
        html = self._build_html(record)
        msg.attach(MIMEText(html, "html", "utf-8"))

        return msg

    def _build_html(self, record: LogRecord) -> str:
        """Build a clean HTML email body."""
        import json

        level_colours = {
            "DEBUG":    "#95A5A6",
            "INFO":     "#3498DB",
            "AUDIT":    "#2980B9",
            "WEBHOOK":  "#9B59B6",
            "WARNING":  "#F39C12",
            "SECURITY": "#E74C3C",
            "ERROR":    "#C0392B",
            "DEPLOY":   "#2ECC71",
            "CRITICAL": "#E53935",
        }
        colour = level_colours.get(record.level_name, "#95A5A6")

        extra_html = ""
        if record.has_extra:
            extra_json = json.dumps(record.extra, indent=2, default=str)
            extra_html = f"""
            <tr>
                <td style="padding:8px 0;border-top:1px solid #eee">
                    <strong>Extra</strong><br>
                    <pre style="background:#f5f5f5;padding:8px;border-radius:4px;
                                font-size:12px;overflow-x:auto">{extra_json}</pre>
                </td>
            </tr>"""

        exc_html = ""
        if record.has_exception:
            exc_html = f"""
            <tr>
                <td style="padding:8px 0;border-top:1px solid #eee">
                    <strong>Exception</strong><br>
                    <pre style="background:#fff0f0;padding:8px;border-radius:4px;
                                font-size:12px;overflow-x:auto;color:#c0392b">{record.exc_info}</pre>
                </td>
            </tr>"""

        return f"""
<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
    <div style="border-left:4px solid {colour};padding-left:16px;margin-bottom:20px">
        <span style="background:{colour};color:#fff;padding:2px 8px;border-radius:3px;
                     font-size:12px;font-weight:bold">{record.level_name}</span>
        <span style="color:#666;font-size:12px;margin-left:8px">{record.timestamp_human}</span>
        <h2 style="margin:8px 0;font-size:16px">{record.message}</h2>
    </div>
    <table style="width:100%;border-collapse:collapse;font-size:14px">
        <tr>
            <td style="padding:4px 0;color:#666;width:100px">Logger</td>
            <td><code>{record.logger_name}</code></td>
        </tr>
        <tr>
            <td style="padding:4px 0;color:#666">Module</td>
            <td><code>{record.module}:{record.line_no}</code></td>
        </tr>
        <tr>
            <td style="padding:4px 0;color:#666">Function</td>
            <td><code>{record.func_name}</code></td>
        </tr>
        {extra_html}
        {exc_html}
    </table>
    <p style="color:#aaa;font-size:11px;margin-top:20px;border-top:1px solid #eee;
              padding-top:10px">Sent by flowlog</p>
</body>
</html>"""

    def _send(self, msg: MIMEMultipart) -> None:
        if self.use_tls:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.from_addr, self.to_addrs, msg.as_string())
        else:
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=10) as server:
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.from_addr, self.to_addrs, msg.as_string())