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


def send_email(to: str, subject: str, body: str, attachments: list | None = None) -> bool:
    """Send a plain-text email, optionally with file attachments. `attachments` is a
    list of (filename, content_str, mime_subtype) — e.g. ('outlay-focus.csv', csv, 'csv')."""
    if not enabled():
        extra = f" +{len(attachments)} attachment(s)" if attachments else ""
        print(f"[notify:dev] to={to} subject={subject!r}{extra}\n{body}")
        return False
    msg = EmailMessage()
    msg["From"] = os.environ.get("SMTP_FROM", "Outlay <no-reply@outlay-ai.com>")
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    for fname, content, subtype in (attachments or []):
        msg.add_attachment((content or "").encode("utf-8"), maintype="text",
                           subtype=subtype or "plain", filename=fname)
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
    body = (f"Reset your Outlay password by opening this link (valid for 1 hour):\n\n{link}\n\n"
            "If you didn't request this, you can ignore this email.")
    return send_email(email, "Reset your Outlay password", body)


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
    body = (f"Your Outlay verification code is {code}\n\n"
            "It expires in 10 minutes. If you didn't request it, you can ignore this message.")
    if channel == "sms":
        return send_sms(dest, body)
    return send_email(dest, "Your Outlay verification code", body)


def send_pilot_request(lead: dict) -> bool:
    """Notify the team of an inbound design-partner pilot request."""
    body = (f"New Outlay pilot request:\n\n"
            f"Name:    {lead.get('name') or '—'}\n"
            f"Email:   {lead.get('email') or '—'}\n"
            f"Company: {lead.get('company') or '—'}\n"
            f"Title:   {lead.get('title') or '—'}\n"
            f"Tools:   {lead.get('tools') or '—'}\n\n"
            f"Message:\n{lead.get('message') or '—'}\n")
    to = os.environ.get("PILOT_INBOX") or os.environ.get("SMTP_FROM_ADDR") or "hello@outlay-ai.com"
    return send_email(to, f"Pilot request — {lead.get('company') or lead.get('email')}", body)


def send_slack(webhook_url: str, text: str) -> bool:
    """Post a message to a Slack (or Teams-compatible) incoming webhook. Best-effort
    — alerting must never break the path that triggered it."""
    if not webhook_url or not text:
        return False
    import json as _json
    import urllib.request
    body = _json.dumps({"text": text}).encode()
    req = urllib.request.Request(webhook_url, data=body,
                                 headers={"content-type": "application/json"}, method="POST")
    try:
        urllib.request.urlopen(req, timeout=5).close()
        return True
    except Exception:  # noqa: BLE001
        return False


def send_anomaly_alert(email: str, anomalies: list, product: str = "Outlay") -> bool:
    """Email the owner when newly-detected runaway tickets appear — a ticket
    burning far more than its work-type median is the guardrail that binds."""
    if not anomalies:
        return False
    n = len(anomalies)
    rows = "\n".join(
        f"  - {a.get('ticket_id')} ({a.get('task_class')}): ${a.get('cost_usd', 0):,.2f}"
        f" — {a.get('ratio', 0):.0f}x its work-type median"
        for a in anomalies[:8])
    subject = f"{product}: {n} runaway ticket{'s' if n != 1 else ''} detected"
    body = (f"{n} ticket{'s' if n != 1 else ''} {'are' if n != 1 else 'is'} costing far more than "
            f"{'their' if n != 1 else 'its'} work-type peers:\n\n{rows}\n\n"
            f"Review them:\n{base_url()}/app/outlay\n\n— {product}")
    return send_email(email, subject, body)


def send_sync_failure_alert(email: str, fails: int, last_error: str = "",
                            since: str = "", product: str = "Outlay") -> bool:
    """Email the owner when auto-sync has failed repeatedly — stale data is the
    #1 silent failure (you trust numbers that quietly stopped updating)."""
    subject = f"{product}: auto-sync is failing — your spend data is going stale"
    stale = f" Your data hasn't refreshed since {since}." if since else ""
    body = (f"{product} couldn't refresh your spend data on the last {fails} attempts."
            f"{stale}\n\n"
            f"Most recent error:\n  {last_error or 'unknown'}\n\n"
            f"This usually means a tracker/API token was rotated or revoked. Until it's "
            f"fixed, the dashboard shows the last good numbers — not current spend.\n\n"
            f"Fix the connection:\n{base_url()}/app/outlay/connect\n\n— {product}")
    return send_email(email, subject, body)


def send_budget_alert(email: str, level: str, spend: float, budget: float,
                      scope: str = "", product: str = "Outlay") -> bool:
    """Budget warn/over email. `scope` (e.g. 'team "platform"') and `product`
    ('Outlay') generalize it beyond the legacy monthly spend budget; defaults keep
    the original Outlay monthly-budget caller working unchanged."""
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
