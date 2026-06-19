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


def sms_enabled() -> bool:
    return bool(os.environ.get("TWILIO_ACCOUNT_SID") and os.environ.get("TWILIO_AUTH_TOKEN")
                and os.environ.get("TWILIO_FROM"))


def send_sms(to: str, body: str) -> bool:
    """Send an SMS via Twilio's REST API (stdlib only). Logs in dev if unconfigured."""
    if not sms_enabled():
        print(f"[notify:dev sms] to={to}\n{body}")
        return False
    import base64
    import urllib.parse
    import urllib.request
    sid = os.environ["TWILIO_ACCOUNT_SID"]
    tok = os.environ["TWILIO_AUTH_TOKEN"]
    data = urllib.parse.urlencode({"From": os.environ["TWILIO_FROM"], "To": to, "Body": body}).encode()
    req = urllib.request.Request(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json", data=data)
    req.add_header("Authorization", "Basic " + base64.b64encode(f"{sid}:{tok}".encode()).decode())
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status in (200, 201)


def send_otp(dest: str, code: str, channel: str = "email") -> bool:
    """Deliver a 2FA one-time code via the chosen channel (email now; SMS via Twilio)."""
    body = (f"Your ModelPilot verification code is {code}\n\n"
            "It expires in 10 minutes. If you didn't request it, you can ignore this message.")
    if channel == "sms":
        return send_sms(dest, body)
    return send_email(dest, "Your ModelPilot verification code", body)


def send_budget_alert(email: str, level: str, spend: float, budget: float,
                      scope: str = "", product: str = "ModelPilot") -> bool:
    """Budget warn/over email. `scope` (e.g. 'team "platform"') and `product`
    ('Outlay') generalize it beyond the legacy monthly spend budget; defaults keep
    the original ModelPilot monthly-budget caller working unchanged."""
    pct = (100 * spend / budget) if budget else 0
    what = f"budget for {scope}" if scope else "monthly spend budget"
    link = "/app/outlay/budgets" if product == "Outlay" else "/app"
    if level == "over":
        subject = f"{product}: projected to exceed your {scope or 'spend'} budget"
        lead = (f"Your {product} spend is ${spend:,.2f}, which is over your "
                f"${budget:,.2f} {what} ({pct:.0f}%).")
    else:
        subject = f"{product}: approaching your {scope or 'spend'} budget"
        lead = (f"Your {product} spend is ${spend:,.2f} "
                f"({pct:.0f}% of your ${budget:,.2f} {what}).")
    body = (f"{lead}\n\nReview and adjust:\n{base_url()}{link}\n\n— {product}")
    return send_email(email, subject, body)
