"""Transactional email for the console (password reset). Pluggable: sends via
SMTP when configured, otherwise logs the message so flows still work in dev and
on instances without an email provider (the reset link is printed to the server
log and, for convenience, returned to the admin who triggered it).

Env: SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD, SMTP_FROM,
     CONSOLE_BASE_URL (for building links).
"""

import os
import smtplib
from email.message import EmailMessage


def enabled() -> bool:
    return bool(os.environ.get("SMTP_HOST"))


def base_url() -> str:
    return os.environ.get("CONSOLE_BASE_URL", "http://127.0.0.1:8700").rstrip("/")


def reset_link(token: str) -> str:
    return f"{base_url()}/reset?token={token}"


def send_email(to: str, subject: str, body: str) -> bool:
    if not enabled():
        print(f"[notify:dev] to={to} subject={subject!r}\n{body}")
        return False
    msg = EmailMessage()
    msg["From"] = os.environ.get("SMTP_FROM", "ModelPilot <no-reply@modelpilot.app>")
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=10) as s:
        s.starttls()
        if os.environ.get("SMTP_USER"):
            s.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
        s.send_message(msg)
    return True


def send_reset(email: str, token: str) -> bool:
    link = reset_link(token)
    body = (f"Reset your ModelPilot password by opening this link (valid for 1 hour):\n\n{link}\n\n"
            "If you didn't request this, you can ignore this email.")
    return send_email(email, "Reset your ModelPilot password", body)
