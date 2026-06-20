"""Outlay console — data layer (SQLite).

VENDOR / INTERNAL: runs on OUR infrastructure (alongside brain + ingest). Not
part of the shipped `modelpilot` package; never migrated to the customer repo.

Owns the SaaS control plane: accounts + auth, deployments, per-account settings
(routing mode), plan/trial/billing state, and savings *metering* (aggregate
dollars only — never prompt text). Billing model: a customer's bill is
`rate` (default 20%) of the realized savings we deliver. The brain reads
entitlement + mode from here; the gateway reports realized savings here.

Stdlib only (sqlite3, hmac, hashlib, secrets) — no auth/crypto dependencies.
"""

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from datetime import datetime, timezone

TRIAL_DAYS = 7
DEFAULT_RATE = 0.20            # we bill 20% of realized savings (Pay-as-you-go)
# Pricing tiers: Pay-as-you-go (20% of savings), and two subscription tiers that
# unlock per-customer tuning on the customer's own (local) prompt data at 15%.
TIERS = ("payg", "self_optimize", "managed")
TIER_RATES = {"payg": 0.20, "self_optimize": 0.15, "managed": 0.15}
TIER_LABELS = {"payg": "Pay-as-you-go", "self_optimize": "Self-optimize", "managed": "Managed"}
DAY = 86_400
SESSION_TTL = 14 * DAY
MODES = ("guidance", "autopilot")
RISK_LEVELS = ("conservative", "balanced", "aggressive")

# Aggregate-only metering. These keys must NEVER appear in a meter payload; if
# they do we refuse it (defense in depth — only dollars + counts are billed on).
FORBIDDEN_METER_KEYS = {
    "messages", "prompt", "prompts", "content", "text", "output", "outputs",
    "completion", "api_key", "apikey", "x-api-key", "authorization", "secret",
}


def _db_path() -> str:
    return os.environ.get("CONSOLE_DB", "console.db")


def connect(path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or _db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    company TEXT,
    pw_hash TEXT NOT NULL,
    pw_salt TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'customer',     -- 'customer' | 'admin'
    status TEXT NOT NULL DEFAULT 'active',      -- 'active' | 'suspended'
    created_at REAL NOT NULL,
    tos_accepted_at REAL                        -- when the owner accepted Terms + Privacy
);
CREATE TABLE IF NOT EXISTS deployments (
    deployment_id TEXT PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    label TEXT,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id),  -- the org they belong to
    email TEXT UNIQUE NOT NULL,
    pw_hash TEXT NOT NULL, pw_salt TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',                   -- admin | member | billing
    status TEXT NOT NULL DEFAULT 'active',                 -- invited | active | removed
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_member_acct ON members(account_id);
CREATE TABLE IF NOT EXISTS settings (
    account_id INTEGER PRIMARY KEY REFERENCES accounts(id),
    mode TEXT NOT NULL DEFAULT 'guidance',
    telemetry_opt_in INTEGER NOT NULL DEFAULT 1,
    min_model TEXT NOT NULL DEFAULT '',
    risk TEXT NOT NULL DEFAULT 'balanced',
    monthly_budget REAL NOT NULL DEFAULT 0,       -- 0 = no cap (dollars of model spend/cycle)
    budget_alert_pct REAL NOT NULL DEFAULT 0.8,
    autopilot_pct INTEGER NOT NULL DEFAULT 100    -- gradual rollout: % of eligible traffic to auto-route in autopilot
);
CREATE TABLE IF NOT EXISTS personas (
    account_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL DEFAULT 0,         -- 0 = the account owner; else members.id
    persona TEXT NOT NULL DEFAULT '',             -- 'finance' | 'eng' : which experience this person sees
    PRIMARY KEY (account_id, member_id)
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    account_id INTEGER NOT NULL,
    actor TEXT,                                   -- email of the person who acted
    action TEXT NOT NULL,                         -- e.g. 'login', 'connection.save', 'member.invite'
    detail TEXT                                   -- freeform context (who/what)
);
CREATE TABLE IF NOT EXISTS plans (
    account_id INTEGER PRIMARY KEY REFERENCES accounts(id),
    plan TEXT NOT NULL DEFAULT 'trial',         -- 'trial' | 'paid'
    rate REAL NOT NULL DEFAULT 0.20,
    trial_started_at REAL NOT NULL,
    converted_at REAL,
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    stripe_item_id TEXT
);
CREATE TABLE IF NOT EXISTS meter (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deployment_id TEXT NOT NULL,
    ts REAL NOT NULL,
    category TEXT,
    requests INTEGER NOT NULL DEFAULT 0,
    routed INTEGER NOT NULL DEFAULT 0,
    escalations INTEGER NOT NULL DEFAULT 0,
    baseline_cost REAL NOT NULL DEFAULT 0,
    actual_cost REAL NOT NULL DEFAULT 0,
    realized_savings REAL NOT NULL DEFAULT 0,
    opportunity_saved REAL NOT NULL DEFAULT 0,   -- additional savings available, not yet captured (caching/batch)
    caching_saved REAL NOT NULL DEFAULT 0,       -- measured savings captured via auto-applied caching (goodwill, NOT billed)
    stripe_reported INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_meter_dep ON meter(deployment_id);
CREATE INDEX IF NOT EXISTS idx_meter_ts ON meter(ts);
CREATE TABLE IF NOT EXISTS proofs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deployment_id TEXT NOT NULL,
    ts REAL NOT NULL,
    comparisons INTEGER NOT NULL DEFAULT 0,   -- judged side-by-side comparisons
    non_inferior INTEGER NOT NULL DEFAULT 0    -- of those, how many were non-inferior
);
CREATE INDEX IF NOT EXISTS idx_proofs_dep ON proofs(deployment_id);
CREATE TABLE IF NOT EXISTS resets (
    token TEXT PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    created_at REAL NOT NULL,
    used INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    deployment_id TEXT NOT NULL,
    kind TEXT NOT NULL,                         -- 'floor' (Track A) | 'rule' (Track C)
    category TEXT NOT NULL,
    payload TEXT NOT NULL,                       -- JSON: proposed floor tier / rule spec
    stats TEXT NOT NULL DEFAULT '{}',           -- JSON: samples, non-inferior rate, etc.
    status TEXT NOT NULL DEFAULT 'pending',      -- 'pending' | 'approved' | 'rejected'
    created_at REAL NOT NULL,
    decided_at REAL,
    decided_by INTEGER,                          -- admin account id (audit trail)
    note TEXT                                     -- optional reviewer note
);
CREATE INDEX IF NOT EXISTS idx_prop_acct ON proposals(account_id, status);
CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    deployment_id TEXT NOT NULL,
    name TEXT,
    prefix TEXT NOT NULL,                        -- display: mp_live_ab12cd34…
    key_hash TEXT NOT NULL UNIQUE,               -- sha256 of the full key
    created_at REAL NOT NULL,
    last_used_at REAL,
    revoked_at REAL
);
CREATE INDEX IF NOT EXISTS idx_key_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_key_acct ON api_keys(account_id);
CREATE TABLE IF NOT EXISTS budget_alerts (
    account_id INTEGER NOT NULL,
    cycle_start REAL NOT NULL,
    level TEXT NOT NULL,                          -- 'warn' | 'over'
    sent_at REAL NOT NULL,
    PRIMARY KEY (account_id, cycle_start, level)
);
CREATE TABLE IF NOT EXISTS request_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    deployment_id TEXT NOT NULL,
    ts REAL NOT NULL,
    category TEXT, original_model TEXT, routed_model TEXT,
    applied INTEGER DEFAULT 0, escalated INTEGER DEFAULT 0, action TEXT,
    status_code INTEGER,
    input_tokens INTEGER DEFAULT 0, output_tokens INTEGER DEFAULT 0,
    baseline_cost REAL DEFAULT 0, actual_cost REAL DEFAULT 0, realized_saved REAL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_rlog_acct ON request_logs(account_id, ts);
CREATE TABLE IF NOT EXISTS webhooks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    url TEXT NOT NULL,
    secret TEXT NOT NULL,
    events TEXT NOT NULL DEFAULT 'all',          -- 'all' or comma-separated event types
    active INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_webhook_acct ON webhooks(account_id);
CREATE TABLE IF NOT EXISTS sso_configs (
    account_id INTEGER PRIMARY KEY REFERENCES accounts(id),
    enabled INTEGER NOT NULL DEFAULT 0,
    domain TEXT,                                  -- email domain that routes to this IdP
    client_id TEXT, client_secret TEXT,
    auth_url TEXT, token_url TEXT, userinfo_url TEXT,
    default_role TEXT NOT NULL DEFAULT 'member',
    scim_token_hash TEXT                          -- sha256 of the SCIM bearer token
);
CREATE INDEX IF NOT EXISTS idx_sso_domain ON sso_configs(domain);
CREATE TABLE IF NOT EXISTS otp_codes (
    account_id INTEGER PRIMARY KEY REFERENCES accounts(id),  -- one live code per account
    code_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    expires_at REAL NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER,            -- intentionally NOT FK-cascaded: cancel reasons survive deletion
    ts REAL NOT NULL,
    kind TEXT NOT NULL,            -- 'dashboard' | 'cancel' | 'estimator'
    rating TEXT,                   -- 'up' | 'down' | NULL
    comment TEXT
);
CREATE TABLE IF NOT EXISTS outlay_reports (
    account_id INTEGER PRIMARY KEY,   -- one current report per account (upserted)
    ts REAL NOT NULL,
    report TEXT NOT NULL              -- the serialized Outlay report (JSON)
);
CREATE TABLE IF NOT EXISTS pilot_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    name TEXT, email TEXT NOT NULL, company TEXT, title TEXT, tools TEXT, message TEXT
);
CREATE TABLE IF NOT EXISTS outlay_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    ts REAL NOT NULL,
    total_usd REAL NOT NULL,          -- spend in the window at each data refresh
    forecast_usd REAL NOT NULL        -- forecast for open work, for trend context
);
CREATE TABLE IF NOT EXISTS outlay_connections (
    account_id INTEGER PRIMARY KEY,   -- one connection config per account (upserted)
    github_owner TEXT,
    github_repo TEXT,
    github_token TEXT,                -- read-only PAT; encrypted at rest (secret_box)
    anthropic_key TEXT,               -- admin key; encrypted at rest (secret_box)
    cursor_key TEXT,                  -- Cursor admin key; encrypted at rest (secret_box)
    synced_at REAL,                   -- last *successful* sync
    last_attempt_at REAL,             -- last sync attempt (success or failure)
    last_sync_error TEXT,             -- friendly error from the last failed attempt; NULL when healthy
    auto_sync_hours INTEGER NOT NULL DEFAULT 0  -- 0 = manual; else re-sync every N hours
);
CREATE TABLE IF NOT EXISTS outlay_budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    scope_type TEXT NOT NULL,         -- 'overall' | 'team' | 'class'
    scope_id TEXT,                    -- team id / work-type; NULL for overall
    limit_usd REAL NOT NULL,
    period_days INTEGER NOT NULL DEFAULT 30
);
"""

WEBHOOK_EVENTS = ("budget.warn", "budget.over", "proposal.pending", "account.suspended")

# Columns added after the proposals table first shipped — applied to existing DBs.
_MIGRATIONS = [
    "ALTER TABLE proposals ADD COLUMN decided_by INTEGER",
    "ALTER TABLE proposals ADD COLUMN note TEXT",
    "ALTER TABLE settings ADD COLUMN monthly_budget REAL NOT NULL DEFAULT 0",
    "ALTER TABLE settings ADD COLUMN budget_alert_pct REAL NOT NULL DEFAULT 0.8",
    "ALTER TABLE resets ADD COLUMN member_id INTEGER",
    "ALTER TABLE accounts ADD COLUMN tos_accepted_at REAL",
    "ALTER TABLE accounts ADD COLUMN twofa_enabled INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE accounts ADD COLUMN twofa_channel TEXT",
    "ALTER TABLE accounts ADD COLUMN twofa_dest TEXT",
    "ALTER TABLE plans ADD COLUMN tier TEXT NOT NULL DEFAULT 'payg'",
    "ALTER TABLE settings ADD COLUMN autopilot_pct INTEGER NOT NULL DEFAULT 100",
    "ALTER TABLE meter ADD COLUMN opportunity_saved REAL NOT NULL DEFAULT 0",
    "ALTER TABLE meter ADD COLUMN caching_saved REAL NOT NULL DEFAULT 0",
    "ALTER TABLE outlay_budgets ADD COLUMN last_status TEXT",
    "ALTER TABLE outlay_connections ADD COLUMN tracker TEXT NOT NULL DEFAULT 'github'",
    "ALTER TABLE outlay_connections ADD COLUMN jira_base_url TEXT",
    "ALTER TABLE outlay_connections ADD COLUMN jira_email TEXT",
    "ALTER TABLE outlay_connections ADD COLUMN jira_token TEXT",
    "ALTER TABLE outlay_connections ADD COLUMN jira_jql TEXT",
    "ALTER TABLE outlay_connections ADD COLUMN linear_key TEXT",
    "ALTER TABLE outlay_connections ADD COLUMN auto_sync_hours INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE outlay_connections ADD COLUMN cursor_key TEXT",
    "ALTER TABLE outlay_connections ADD COLUMN last_sync_error TEXT",
    "ALTER TABLE outlay_connections ADD COLUMN last_attempt_at REAL",
    "ALTER TABLE pilot_requests ADD COLUMN title TEXT",
]

OTP_TTL = 600          # one-time code lifetime (seconds)
OTP_MAX_ATTEMPTS = 5   # wrong tries before a code is burned

TEAM_ROLES = ("admin", "member", "billing")

RESET_TTL = 3600  # password-reset token lifetime (seconds)


def init_db(path: str | None = None) -> None:
    conn = connect(path)
    try:
        conn.executescript(SCHEMA)
        for stmt in _MIGRATIONS:
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass  # column already exists
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Secrets / password hashing / signed session cookies (stdlib only)
# --------------------------------------------------------------------------- #

def _secret(path: str | None = None) -> bytes:
    """Process/HMAC secret for signing session cookies. Prefer CONSOLE_SECRET;
    else persist a random one next to the DB so restarts don't log everyone out."""
    env = os.environ.get("CONSOLE_SECRET")
    if env:
        return env.encode()
    side = (path or _db_path()) + ".secret"
    try:
        with open(side) as f:
            return bytes.fromhex(f.read().strip())
    except OSError:
        s = secrets.token_bytes(32)
        try:
            with open(side, "w") as f:
                f.write(s.hex())
        except OSError:
            pass
        return s


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000)
    return digest.hex(), salt


def verify_password(password: str, pw_hash: str, salt: str) -> bool:
    cand, _ = hash_password(password, salt)
    return hmac.compare_digest(cand, pw_hash)


def make_session(account_id: int, role: str, team_role: str = "owner",
                 member_id: int = 0, path: str | None = None) -> str:
    payload = f"{account_id}:{role}:{team_role}:{member_id}:{int(time.time())}"
    sig = hmac.new(_secret(path), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def read_session(token: str, path: str | None = None) -> dict | None:
    try:
        account_id, role, team_role, member_id, issued, sig = token.rsplit(":", 5)
    except (ValueError, AttributeError):
        return None
    payload = f"{account_id}:{role}:{team_role}:{member_id}:{issued}"
    expected = hmac.new(_secret(path), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    if time.time() - float(issued) > SESSION_TTL:
        return None
    return {"account_id": int(account_id), "role": role, "team_role": team_role,
            "member_id": int(member_id), "issued": float(issued)}


# --------------------------------------------------------------------------- #
# Accounts
# --------------------------------------------------------------------------- #

class StoreError(ValueError):
    pass


def create_account(email: str, password: str, company: str = "", role: str = "customer",
                   path: str | None = None, now: float | None = None,
                   consent: bool = False) -> dict:
    """Create an account + its deployment + default settings + a started trial.
    `consent=True` records that the owner accepted the Terms + Privacy Policy."""
    email = (email or "").strip().lower()
    if "@" not in email or len(email) < 5:
        raise StoreError("Enter a valid email address.")
    if len(password or "") < 8:
        raise StoreError("Password must be at least 8 characters.")
    now = now or time.time()
    pw_hash, salt = hash_password(password)
    conn = connect(path)
    try:
        try:
            cur = conn.execute(
                "INSERT INTO accounts(email, company, pw_hash, pw_salt, role, status, created_at,"
                " tos_accepted_at) VALUES(?,?,?,?,?, 'active', ?, ?)",
                (email, company.strip(), pw_hash, salt, role, now, now if consent else None))
        except sqlite3.IntegrityError:
            raise StoreError("An account with that email already exists.")
        account_id = cur.lastrowid
        dep = "dep_" + secrets.token_hex(12)
        conn.execute("INSERT INTO deployments(deployment_id, account_id, label, created_at)"
                     " VALUES(?,?,?,?)", (dep, account_id, "default", now))
        conn.execute("INSERT INTO settings(account_id) VALUES(?)", (account_id,))
        conn.execute("INSERT INTO plans(account_id, plan, rate, trial_started_at)"
                     " VALUES(?, 'trial', ?, ?)", (account_id, DEFAULT_RATE, now))
        conn.commit()
    finally:
        conn.close()
    return get_account(account_id, path)


def get_account(account_id: int, path: str | None = None) -> dict | None:
    conn = connect(path)
    try:
        row = conn.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_account_by_email(email: str, path: str | None = None) -> dict | None:
    conn = connect(path)
    try:
        row = conn.execute("SELECT * FROM accounts WHERE email=?",
                           ((email or "").strip().lower(),)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def authenticate(email: str, password: str, path: str | None = None) -> dict | None:
    acct = get_account_by_email(email, path)
    if not acct or acct["status"] != "active":
        return None
    if not verify_password(password, acct["pw_hash"], acct["pw_salt"]):
        return None
    return acct


# --------------------------------------------------------------------------- #
# Two-factor authentication (email/SMS one-time codes)
# --------------------------------------------------------------------------- #

def get_2fa(account_id: int, path: str | None = None) -> dict:
    acct = get_account(account_id, path)
    if not acct:
        return {"enabled": False, "channel": None, "dest": None}
    return {"enabled": bool(acct.get("twofa_enabled")),
            "channel": acct.get("twofa_channel"), "dest": acct.get("twofa_dest")}


def set_2fa(account_id: int, channel: str, dest: str, path: str | None = None) -> None:
    conn = connect(path)
    try:
        conn.execute("UPDATE accounts SET twofa_enabled=1, twofa_channel=?, twofa_dest=? WHERE id=?",
                     (channel, dest, account_id))
        conn.commit()
    finally:
        conn.close()


def disable_2fa(account_id: int, path: str | None = None) -> None:
    conn = connect(path)
    try:
        conn.execute("UPDATE accounts SET twofa_enabled=0, twofa_channel=NULL, twofa_dest=NULL WHERE id=?",
                     (account_id,))
        conn.execute("DELETE FROM otp_codes WHERE account_id=?", (account_id,))
        conn.commit()
    finally:
        conn.close()


def issue_otp(account_id: int, path: str | None = None, now: float | None = None) -> str:
    """Generate a fresh 6-digit code, store it hashed (replacing any prior), and
    return the plaintext for the caller to deliver via the chosen channel."""
    now = now or time.time()
    code = f"{secrets.randbelow(1_000_000):06d}"
    salt = secrets.token_hex(16)
    code_hash = hashlib.pbkdf2_hmac("sha256", code.encode(), bytes.fromhex(salt), 50_000).hex()
    conn = connect(path)
    try:
        conn.execute(
            "INSERT INTO otp_codes(account_id, code_hash, salt, expires_at, attempts) VALUES(?,?,?,?,0)"
            " ON CONFLICT(account_id) DO UPDATE SET code_hash=excluded.code_hash,"
            " salt=excluded.salt, expires_at=excluded.expires_at, attempts=0",
            (account_id, code_hash, salt, now + OTP_TTL))
        conn.commit()
    finally:
        conn.close()
    return code


def verify_otp(account_id: int, code: str, path: str | None = None, now: float | None = None) -> bool:
    now = now or time.time()
    conn = connect(path)
    try:
        row = conn.execute("SELECT code_hash, salt, expires_at, attempts FROM otp_codes WHERE account_id=?",
                           (account_id,)).fetchone()
        if not row:
            return False
        if now > row["expires_at"] or row["attempts"] >= OTP_MAX_ATTEMPTS:
            conn.execute("DELETE FROM otp_codes WHERE account_id=?", (account_id,))
            conn.commit()
            return False
        calc = hashlib.pbkdf2_hmac("sha256", (code or "").strip().encode(),
                                   bytes.fromhex(row["salt"]), 50_000).hex()
        if hmac.compare_digest(calc, row["code_hash"]):
            conn.execute("DELETE FROM otp_codes WHERE account_id=?", (account_id,))
            conn.commit()
            return True
        conn.execute("UPDATE otp_codes SET attempts=attempts+1 WHERE account_id=?", (account_id,))
        conn.commit()
        return False
    finally:
        conn.close()


def make_pending_2fa(account_id: int, path: str | None = None) -> str:
    """Short-lived signed marker carried between the password step and the OTP step."""
    payload = f"p2fa:{account_id}:{int(time.time())}"
    sig = hmac.new(_secret(path), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def read_pending_2fa(token: str, path: str | None = None, max_age: int = 600) -> int | None:
    try:
        marker, aid, issued, sig = token.split(":")
    except (ValueError, AttributeError):
        return None
    if marker != "p2fa":
        return None
    payload = f"{marker}:{aid}:{issued}"
    good = hmac.new(_secret(path), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(good, sig) or time.time() - int(issued) > max_age:
        return None
    return int(aid)


def list_accounts(path: str | None = None) -> list[dict]:
    conn = connect(path)
    try:
        rows = conn.execute("SELECT * FROM accounts ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def set_status(account_id: int, status: str, path: str | None = None) -> None:
    conn = connect(path)
    try:
        conn.execute("UPDATE accounts SET status=? WHERE id=?", (status, account_id))
        conn.commit()
    finally:
        conn.close()


def set_role(account_id: int, role: str, path: str | None = None) -> None:
    conn = connect(path)
    try:
        conn.execute("UPDATE accounts SET role=? WHERE id=?", (role, account_id))
        conn.commit()
    finally:
        conn.close()


def delete_account(account_id: int, path: str | None = None) -> None:
    """Permanently delete an account and ALL its data: deployments, settings,
    plan, metering, proofs, proposals, API keys, request logs, webhooks, budget
    alerts, password resets, team members, and SSO config. Irreversible.
    (Does not touch Stripe — cancel the subscription before calling this.)"""
    conn = connect(path)
    try:
        deps = [r["deployment_id"] for r in conn.execute(
            "SELECT deployment_id FROM deployments WHERE account_id=?", (account_id,)).fetchall()]
        if deps:
            placeholders = ",".join("?" for _ in deps)
            conn.execute(f"DELETE FROM meter WHERE deployment_id IN ({placeholders})", deps)
            conn.execute(f"DELETE FROM proofs WHERE deployment_id IN ({placeholders})", deps)
        # tables keyed directly by account_id
        for tbl in ("api_keys", "request_logs", "proposals", "webhooks", "budget_alerts",
                    "resets", "members", "sso_configs", "settings", "plans", "deployments"):
            conn.execute(f"DELETE FROM {tbl} WHERE account_id=?", (account_id,))
        conn.execute("DELETE FROM accounts WHERE id=?", (account_id,))
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Feedback + activation funnel (first-party, privacy-clean product metrics)
# --------------------------------------------------------------------------- #

def record_feedback(account_id: int | None, kind: str, rating: str | None = None,
                    comment: str | None = None, path: str | None = None,
                    now: float | None = None) -> None:
    """Store a lightweight feedback signal (dashboard thumbs / cancel reason).
    No prompt content — just a rating + free-text the user chose to write."""
    now = now or time.time()
    conn = connect(path)
    try:
        conn.execute("INSERT INTO feedback(account_id, ts, kind, rating, comment) VALUES(?,?,?,?,?)",
                     (account_id, now, kind, rating, (comment or "").strip()[:2000]))
        conn.commit()
    finally:
        conn.close()


def list_feedback(limit: int = 50, path: str | None = None) -> list[dict]:
    conn = connect(path)
    try:
        rows = conn.execute(
            "SELECT f.id, f.account_id, f.ts, f.kind, f.rating, f.comment, a.email"
            " FROM feedback f LEFT JOIN accounts a ON a.id=f.account_id"
            " ORDER BY f.ts DESC LIMIT ?", (int(limit),)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def save_outlay_report(account_id: int, report: dict, path: str | None = None,
                       now: float | None = None) -> None:
    """Upsert the account's current Outlay report (the serialized engine output)."""
    now = now or time.time()
    conn = connect(path)
    try:
        conn.execute("INSERT OR REPLACE INTO outlay_reports(account_id, ts, report) VALUES(?,?,?)",
                     (account_id, now, json.dumps(report)))
        conn.commit()
    finally:
        conn.close()


def get_outlay_report(account_id: int, path: str | None = None) -> dict | None:
    """The account's current Outlay report, or None if they haven't run one yet."""
    conn = connect(path)
    try:
        r = conn.execute("SELECT ts, report FROM outlay_reports WHERE account_id=?",
                         (account_id,)).fetchone()
    finally:
        conn.close()
    if not r:
        return None
    data = json.loads(r["report"])
    data["_generated_ts"] = r["ts"]
    return data


def add_pilot_request(email: str, name: str = "", company: str = "", tools: str = "",
                      message: str = "", title: str = "", path: str | None = None,
                      now: float | None = None) -> int:
    """Store an inbound design-partner pilot request (from the public form)."""
    conn = connect(path)
    try:
        cur = conn.execute(
            "INSERT INTO pilot_requests(ts, name, email, company, title, tools, message) "
            "VALUES(?,?,?,?,?,?,?)",
            (now or time.time(), (name or "").strip()[:200], (email or "").strip()[:200],
             (company or "").strip()[:200], (title or "").strip()[:200],
             (tools or "").strip()[:300], (message or "").strip()[:4000]))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_pilot_requests(path: str | None = None) -> list[dict]:
    conn = connect(path)
    try:
        rows = conn.execute("SELECT * FROM pilot_requests ORDER BY ts DESC").fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def delete_outlay_report(account_id: int, path: str | None = None) -> None:
    """Clear an account's current report + spend history (used to drop sample data)."""
    conn = connect(path)
    try:
        conn.execute("DELETE FROM outlay_reports WHERE account_id=?", (account_id,))
        conn.execute("DELETE FROM outlay_history WHERE account_id=?", (account_id,))
        conn.commit()
    finally:
        conn.close()


def record_outlay_snapshot(account_id: int, report: dict, path: str | None = None,
                           now: float | None = None) -> None:
    """Append a spend snapshot to history on a genuine data refresh (run / sync) —
    powers the dashboard's trend delta and sparkline. Not called on estimate re-saves."""
    total = (report.get("spend", {}) or {}).get("total_usd", 0.0)
    fc = (report.get("forecast", {}) or {}).get("expected_usd", 0.0)
    conn = connect(path)
    try:
        conn.execute("INSERT INTO outlay_history(account_id, ts, total_usd, forecast_usd)"
                     " VALUES(?,?,?,?)", (account_id, now or time.time(), total, fc))
        conn.commit()
    finally:
        conn.close()


def outlay_history(account_id: int, limit: int = 12, path: str | None = None) -> list[dict]:
    """Recent spend snapshots, oldest→newest (for sparkline + delta-vs-last)."""
    conn = connect(path)
    try:
        rows = conn.execute(
            "SELECT ts, total_usd, forecast_usd FROM outlay_history WHERE account_id=?"
            " ORDER BY ts DESC LIMIT ?", (account_id, limit)).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in reversed(rows)]


def save_outlay_connection(account_id: int, github_owner: str | None = None,
                           github_repo: str | None = None, github_token: str | None = None,
                           anthropic_key: str | None = None, tracker: str | None = None,
                           jira_base_url: str | None = None, jira_email: str | None = None,
                           jira_token: str | None = None, jira_jql: str | None = None,
                           linear_key: str | None = None, cursor_key: str | None = None,
                           auto_sync_hours: int | None = None,
                           path: str | None = None) -> None:
    """Upsert a customer's connection config. Secrets left blank are preserved;
    other blank fields are cleared. Supports GitHub / Jira / Linear trackers."""
    cur = get_outlay_connection(account_id, path) or {}

    def _txt(v):  # non-secret: blank clears
        return (v.strip() if isinstance(v, str) else v) or None

    def _sec(v, key):  # secret: blank preserves (cur is already decrypted)
        return (v or "").strip() or cur.get(key)

    asy = cur.get("auto_sync_hours") or 0 if auto_sync_hours is None else int(auto_sync_hours)
    from . import secret_box
    enc = secret_box.encrypt
    conn = connect(path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO outlay_connections"
            "(account_id, tracker, github_owner, github_repo, github_token, anthropic_key,"
            " cursor_key, jira_base_url, jira_email, jira_token, jira_jql, linear_key,"
            " synced_at, auto_sync_hours)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (account_id, _txt(tracker) or cur.get("tracker") or "github",
             _txt(github_owner), _txt(github_repo), enc(_sec(github_token, "github_token")),
             enc(_sec(anthropic_key, "anthropic_key")), enc(_sec(cursor_key, "cursor_key")),
             _txt(jira_base_url), _txt(jira_email), enc(_sec(jira_token, "jira_token")),
             _txt(jira_jql), enc(_sec(linear_key, "linear_key")), cur.get("synced_at"), asy))
        conn.commit()
    finally:
        conn.close()


_OUTLAY_SECRETS = ("github_token", "anthropic_key", "cursor_key", "jira_token", "linear_key")


def get_outlay_connection(account_id: int, path: str | None = None) -> dict | None:
    from . import secret_box
    conn = connect(path)
    try:
        r = conn.execute("SELECT * FROM outlay_connections WHERE account_id=?",
                         (account_id,)).fetchone()
    finally:
        conn.close()
    if not r:
        return None
    d = dict(r)
    for k in _OUTLAY_SECRETS:  # decrypt for use (and to preserve on re-save)
        d[k] = secret_box.decrypt(d.get(k))
    return d


def mark_outlay_synced(account_id: int, path: str | None = None,
                       now: float | None = None) -> None:
    """Record a successful sync: stamp synced_at + last_attempt_at, clear any error."""
    ts = now or time.time()
    conn = connect(path)
    try:
        conn.execute("UPDATE outlay_connections SET synced_at=?, last_attempt_at=?,"
                     " last_sync_error=NULL WHERE account_id=?", (ts, ts, account_id))
        conn.commit()
    finally:
        conn.close()


def mark_outlay_sync_error(account_id: int, message: str, path: str | None = None,
                           now: float | None = None) -> None:
    """Record a failed sync attempt so the UI can surface why refreshing stopped."""
    conn = connect(path)
    try:
        conn.execute("UPDATE outlay_connections SET last_attempt_at=?, last_sync_error=?"
                     " WHERE account_id=?", (now or time.time(), (message or "")[:300], account_id))
        conn.commit()
    finally:
        conn.close()


def list_due_outlay_connections(now: float | None = None,
                                path: str | None = None) -> list[int]:
    """Account ids whose auto-sync is on and is due (never synced, or older than
    its interval). Returns ids only; callers fetch+decrypt the full connection."""
    now = now or time.time()
    conn = connect(path)
    try:
        rows = conn.execute(
            "SELECT account_id, synced_at, auto_sync_hours FROM outlay_connections"
            " WHERE auto_sync_hours > 0").fetchall()
    finally:
        conn.close()
    return [r["account_id"] for r in rows
            if not r["synced_at"] or r["synced_at"] <= now - r["auto_sync_hours"] * 3600]


def add_outlay_budget(account_id: int, scope_type: str, scope_id: str | None,
                      limit_usd: float, period_days: int = 30, path: str | None = None) -> None:
    conn = connect(path)
    try:
        conn.execute(
            "INSERT INTO outlay_budgets(account_id, scope_type, scope_id, limit_usd, period_days)"
            " VALUES(?,?,?,?,?)",
            (account_id, scope_type, (scope_id or "").strip() or None,
             float(limit_usd), int(period_days)))
        conn.commit()
    finally:
        conn.close()


def list_outlay_budgets(account_id: int, path: str | None = None) -> list[dict]:
    conn = connect(path)
    try:
        rows = conn.execute("SELECT * FROM outlay_budgets WHERE account_id=? ORDER BY id",
                            (account_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_outlay_budget(account_id: int, budget_id: int, path: str | None = None) -> None:
    conn = connect(path)
    try:
        conn.execute("DELETE FROM outlay_budgets WHERE id=? AND account_id=?",
                     (int(budget_id), account_id))
        conn.commit()
    finally:
        conn.close()


def set_outlay_budget_status(budget_id: int, status: str, path: str | None = None) -> None:
    """Persist a budget's last evaluated status (for alert-on-transition)."""
    conn = connect(path)
    try:
        conn.execute("UPDATE outlay_budgets SET last_status=? WHERE id=?", (status, int(budget_id)))
        conn.commit()
    finally:
        conn.close()


def activation_funnel(path: str | None = None) -> dict:
    """Counts of accounts at each activation stage — the 'are customers reaching
    value' funnel. signed_up -> set_up (made a key) -> routed (sent traffic) ->
    proven (got measured savings) -> paid (converted)."""
    conn = connect(path)
    try:
        one = lambda q: conn.execute(q).fetchone()[0]
        return {
            "signed_up": one("SELECT COUNT(*) FROM accounts"),
            "set_up": one("SELECT COUNT(DISTINCT account_id) FROM api_keys"),
            "routed": one("SELECT COUNT(DISTINCT d.account_id) FROM meter m"
                          " JOIN deployments d ON d.deployment_id=m.deployment_id WHERE m.routed>0"),
            "proven": one("SELECT COUNT(DISTINCT d.account_id) FROM meter m"
                          " JOIN deployments d ON d.deployment_id=m.deployment_id"
                          " WHERE m.realized_savings>0"),
            "paid": one("SELECT COUNT(*) FROM plans WHERE plan='paid'"),
        }
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Team members (additive: the account owner stays on `accounts`; invited
# teammates live here with a per-account role). Members never get vendor-admin.
# --------------------------------------------------------------------------- #

def create_member(account_id: int, email: str, role: str = "member",
                  path: str | None = None, now: float | None = None) -> dict:
    """Invite a teammate. Created with a random unusable password ('invited');
    they set their own via the reset/invite link. Returns the member row."""
    email = (email or "").strip().lower()
    if "@" not in email:
        raise StoreError("Enter a valid email address.")
    if role not in TEAM_ROLES:
        raise StoreError(f"role must be one of {TEAM_ROLES}")
    if get_account_by_email(email, path):
        raise StoreError("That email already owns an account.")
    now = now or time.time()
    pw_hash, salt = hash_password(secrets.token_urlsafe(16))  # placeholder until they set one
    conn = connect(path)
    try:
        try:
            cur = conn.execute(
                "INSERT INTO members(account_id, email, pw_hash, pw_salt, role, status, created_at)"
                " VALUES(?,?,?,?,?, 'invited', ?)", (account_id, email, pw_hash, salt, role, now))
        except sqlite3.IntegrityError:
            raise StoreError("That email is already a member.")
        mid = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return get_member(mid, path)


def get_member(member_id: int, path: str | None = None) -> dict | None:
    conn = connect(path)
    try:
        row = conn.execute("SELECT * FROM members WHERE id=?", (member_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_member_by_email(email: str, path: str | None = None) -> dict | None:
    conn = connect(path)
    try:
        row = conn.execute("SELECT * FROM members WHERE email=?",
                           ((email or "").strip().lower(),)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_members(account_id: int, path: str | None = None) -> list[dict]:
    conn = connect(path)
    try:
        rows = conn.execute("SELECT id, account_id, email, role, status, created_at FROM members"
                            " WHERE account_id=? AND status!='removed' ORDER BY created_at",
                            (account_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def set_member_role(member_id: int, account_id: int, role: str, path: str | None = None) -> None:
    if role not in TEAM_ROLES:
        raise StoreError(f"role must be one of {TEAM_ROLES}")
    conn = connect(path)
    try:
        conn.execute("UPDATE members SET role=? WHERE id=? AND account_id=?",
                     (role, member_id, account_id))
        conn.commit()
    finally:
        conn.close()


def remove_member(member_id: int, account_id: int, path: str | None = None) -> None:
    conn = connect(path)
    try:
        conn.execute("UPDATE members SET status='removed' WHERE id=? AND account_id=?",
                     (member_id, account_id))
        conn.commit()
    finally:
        conn.close()


def set_member_password(member_id: int, new_password: str, path: str | None = None) -> None:
    if len(new_password or "") < 8:
        raise StoreError("Password must be at least 8 characters.")
    pw_hash, salt = hash_password(new_password)
    conn = connect(path)
    try:
        conn.execute("UPDATE members SET pw_hash=?, pw_salt=?, status='active' WHERE id=?",
                     (pw_hash, salt, member_id))
        conn.commit()
    finally:
        conn.close()


def authenticate_member(email: str, password: str, path: str | None = None) -> dict | None:
    m = get_member_by_email(email, path)
    if not m or m["status"] == "removed":
        return None
    if not verify_password(password, m["pw_hash"], m["pw_salt"]):
        return None
    acct = get_account(m["account_id"], path)
    if not acct or acct["status"] != "active":
        return None
    return m


# --------------------------------------------------------------------------- #
# Deployments
# --------------------------------------------------------------------------- #

def deployments_for(account_id: int, path: str | None = None) -> list[dict]:
    conn = connect(path)
    try:
        rows = conn.execute("SELECT * FROM deployments WHERE account_id=? ORDER BY created_at",
                            (account_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def create_deployment(account_id: int, label: str = "", path: str | None = None,
                      now: float | None = None) -> dict:
    """Add another deployment (e.g. a second app / environment) to an account.
    Savings across all of an account's deployments roll up to one bill."""
    now = now or time.time()
    dep = "dep_" + secrets.token_hex(12)
    conn = connect(path)
    try:
        conn.execute("INSERT INTO deployments(deployment_id, account_id, label, created_at)"
                     " VALUES(?,?,?,?)", (dep, account_id, (label or "deployment").strip(), now))
        conn.commit()
    finally:
        conn.close()
    return {"deployment_id": dep, "account_id": account_id, "label": label, "created_at": now}


def rename_deployment(deployment_id: str, account_id: int, label: str,
                      path: str | None = None) -> None:
    """Relabel a deployment (scoped to the owning account)."""
    conn = connect(path)
    try:
        conn.execute("UPDATE deployments SET label=? WHERE deployment_id=? AND account_id=?",
                     ((label or "").strip(), deployment_id, account_id))
        conn.commit()
    finally:
        conn.close()


def account_for_deployment(deployment_id: str, path: str | None = None) -> dict | None:
    conn = connect(path)
    try:
        row = conn.execute(
            "SELECT a.* FROM accounts a JOIN deployments d ON d.account_id=a.id"
            " WHERE d.deployment_id=?", (deployment_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Settings (mode, telemetry, profile knobs)
# --------------------------------------------------------------------------- #

def get_settings(account_id: int, path: str | None = None) -> dict:
    conn = connect(path)
    try:
        row = conn.execute("SELECT * FROM settings WHERE account_id=?", (account_id,)).fetchone()
        if not row:
            conn.execute("INSERT INTO settings(account_id) VALUES(?)", (account_id,))
            conn.commit()
            row = conn.execute("SELECT * FROM settings WHERE account_id=?", (account_id,)).fetchone()
        return dict(row)
    finally:
        conn.close()


def record_audit(account_id: int, action: str, actor: str = "", detail: str = "",
                 path: str | None = None, now: float | None = None) -> None:
    """Append a security-relevant event to the account's audit trail."""
    conn = connect(path)
    try:
        conn.execute(
            "INSERT INTO audit_log(ts, account_id, actor, action, detail) VALUES(?,?,?,?,?)",
            (now or time.time(), account_id, (actor or "")[:200], (action or "")[:80],
             (detail or "")[:500]))
        conn.commit()
    finally:
        conn.close()


def list_audit(account_id: int, limit: int = 200, path: str | None = None) -> list[dict]:
    conn = connect(path)
    try:
        rows = conn.execute(
            "SELECT * FROM audit_log WHERE account_id=? ORDER BY ts DESC, id DESC LIMIT ?",
            (account_id, limit)).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


PERSONAS = ("finance", "eng")


def get_persona(account_id: int, member_id: int = 0, path: str | None = None) -> str:
    """The chosen experience ('finance'|'eng'|'') for this person (member_id 0 = owner)."""
    conn = connect(path)
    try:
        row = conn.execute("SELECT persona FROM personas WHERE account_id=? AND member_id=?",
                           (account_id, member_id)).fetchone()
        return (row["persona"] if row else "") or ""
    finally:
        conn.close()


def set_persona(account_id: int, persona: str, member_id: int = 0, path: str | None = None) -> None:
    """Set this person's experience (per member — finance and eng are separate logins)."""
    if persona not in PERSONAS:
        raise StoreError(f"persona must be one of {PERSONAS}")
    conn = connect(path)
    try:
        conn.execute(
            "INSERT INTO personas(account_id, member_id, persona) VALUES(?,?,?) "
            "ON CONFLICT(account_id, member_id) DO UPDATE SET persona=excluded.persona",
            (account_id, member_id, persona))
        conn.commit()
    finally:
        conn.close()


def update_settings(account_id: int, *, mode: str | None = None,
                    telemetry_opt_in: bool | None = None, min_model: str | None = None,
                    risk: str | None = None, monthly_budget: float | None = None,
                    budget_alert_pct: float | None = None, autopilot_pct: int | None = None,
                    path: str | None = None) -> dict:
    if mode is not None and mode not in MODES:
        raise StoreError(f"mode must be one of {MODES}")
    if mode == "guidance" and get_plan(account_id, path).get("plan") == "paid":
        raise StoreError("guidance mode is only available during the free trial; paid plans use autopilot")
    if risk is not None and risk not in RISK_LEVELS:
        raise StoreError(f"risk must be one of {RISK_LEVELS}")
    cur = get_settings(account_id, path)
    new = {
        "mode": cur["mode"] if mode is None else mode,
        "telemetry_opt_in": cur["telemetry_opt_in"] if telemetry_opt_in is None else int(telemetry_opt_in),
        "min_model": cur["min_model"] if min_model is None else min_model,
        "risk": cur["risk"] if risk is None else risk,
        "monthly_budget": cur["monthly_budget"] if monthly_budget is None else max(0.0, float(monthly_budget)),
        "budget_alert_pct": (cur["budget_alert_pct"] if budget_alert_pct is None
                             else min(1.0, max(0.0, float(budget_alert_pct)))),
        "autopilot_pct": (cur.get("autopilot_pct", 100) if autopilot_pct is None
                          else min(100, max(0, int(autopilot_pct)))),
    }
    conn = connect(path)
    try:
        conn.execute("UPDATE settings SET mode=?, telemetry_opt_in=?, min_model=?, risk=?,"
                     " monthly_budget=?, budget_alert_pct=?, autopilot_pct=? WHERE account_id=?",
                     (new["mode"], new["telemetry_opt_in"], new["min_model"], new["risk"],
                      new["monthly_budget"], new["budget_alert_pct"], new["autopilot_pct"], account_id))
        conn.commit()
    finally:
        conn.close()
    return get_settings(account_id, path)


# --------------------------------------------------------------------------- #
# API keys (named, scoped to a deployment, hashed at rest, revocable)
# --------------------------------------------------------------------------- #

KEY_PREFIX = "mp_live_"


def create_api_key(account_id: int, deployment_id: str, name: str = "",
                   path: str | None = None, now: float | None = None) -> dict:
    """Mint a key. Returns the FULL key once (never recoverable) plus its row.
    Only the sha256 hash + a display prefix are stored."""
    if not account_for_deployment(deployment_id, path):
        raise StoreError("unknown deployment")
    now = now or time.time()
    full = KEY_PREFIX + secrets.token_urlsafe(24)
    prefix = full[:16]
    key_hash = hashlib.sha256(full.encode()).hexdigest()
    conn = connect(path)
    try:
        conn.execute("INSERT INTO api_keys(account_id, deployment_id, name, prefix, key_hash,"
                     " created_at) VALUES(?,?,?,?,?,?)",
                     (account_id, deployment_id, (name or "key").strip(), prefix, key_hash, now))
        conn.commit()
    finally:
        conn.close()
    return {"full_key": full, "prefix": prefix, "name": name}


def list_api_keys(account_id: int, path: str | None = None) -> list[dict]:
    conn = connect(path)
    try:
        rows = conn.execute(
            "SELECT id, deployment_id, name, prefix, created_at, last_used_at, revoked_at"
            " FROM api_keys WHERE account_id=? ORDER BY created_at DESC", (account_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def revoke_api_key(key_id: int, account_id: int, path: str | None = None,
                   now: float | None = None) -> bool:
    now = now or time.time()
    conn = connect(path)
    try:
        cur = conn.execute("UPDATE api_keys SET revoked_at=? WHERE id=? AND account_id=?"
                           " AND revoked_at IS NULL", (now, key_id, account_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def resolve_api_key(full_key: str, path: str | None = None, now: float | None = None) -> dict | None:
    """Validate a presented key. Returns {account_id, deployment_id, key_id} or None
    (unknown/revoked). Updates last_used_at on success."""
    if not full_key or not full_key.startswith(KEY_PREFIX):
        return None
    now = now or time.time()
    key_hash = hashlib.sha256(full_key.strip().encode()).hexdigest()
    conn = connect(path)
    try:
        row = conn.execute("SELECT * FROM api_keys WHERE key_hash=? AND revoked_at IS NULL",
                           (key_hash,)).fetchone()
        if not row:
            return None
        conn.execute("UPDATE api_keys SET last_used_at=? WHERE id=?", (now, row["id"]))
        conn.commit()
        return {"account_id": row["account_id"], "deployment_id": row["deployment_id"],
                "key_id": row["id"]}
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Spend budget + alerts (dollars of model spend per cycle)
# --------------------------------------------------------------------------- #

def budget_status(account_id: int, path: str | None = None, now: float | None = None) -> dict:
    """This cycle's model spend vs the configured monthly budget."""
    now = now or time.time()
    s = get_settings(account_id, path)
    budget = s.get("monthly_budget") or 0.0
    spend = savings_summary(account_id, since=cycle_start(now), path=path)["actual"]
    pct = (spend / budget) if budget else 0.0
    return {"budget": budget, "spend": spend, "pct": pct,
            "alert_pct": s.get("budget_alert_pct") or 0.8,
            "warn": bool(budget) and pct >= (s.get("budget_alert_pct") or 0.8),
            "over": bool(budget) and pct >= 1.0, "enabled": bool(budget)}


def budget_alert_pending(account_id: int, path: str | None = None, now: float | None = None):
    """If a budget threshold was just crossed and we haven't emailed for it this
    cycle, return the level ('over'|'warn') to alert on; else None."""
    now = now or time.time()
    st = budget_status(account_id, path, now)
    if not st["enabled"]:
        return None
    level = "over" if st["over"] else ("warn" if st["warn"] else None)
    if level is None:
        return None
    cyc = cycle_start(now)
    conn = connect(path)
    try:
        # 'over' supersedes a prior 'warn'; don't resend the same level in a cycle.
        seen = {r["level"] for r in conn.execute(
            "SELECT level FROM budget_alerts WHERE account_id=? AND cycle_start=?",
            (account_id, cyc)).fetchall()}
        if level in seen or (level == "warn" and "over" in seen):
            return None
        conn.execute("INSERT OR IGNORE INTO budget_alerts(account_id, cycle_start, level, sent_at)"
                     " VALUES(?,?,?,?)", (account_id, cyc, level, now))
        conn.commit()
    finally:
        conn.close()
    return {"level": level, **st}


# --------------------------------------------------------------------------- #
# Plans / trial / entitlement
# --------------------------------------------------------------------------- #

def get_plan(account_id: int, path: str | None = None) -> dict:
    conn = connect(path)
    try:
        row = conn.execute("SELECT * FROM plans WHERE account_id=?", (account_id,)).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def trial_status(account_id: int, path: str | None = None, now: float | None = None) -> dict:
    now = now or time.time()
    plan = get_plan(account_id, path)
    if not plan:
        return {"active": False, "days_left": 0, "ends_at": 0}
    ends_at = plan["trial_started_at"] + TRIAL_DAYS * DAY
    days_left = max(0, int((ends_at - now) // DAY) + (1 if (ends_at - now) % DAY else 0))
    return {"active": now < ends_at, "days_left": max(0, days_left),
            "ends_at": ends_at, "started_at": plan["trial_started_at"]}


def extend_trial(account_id: int, days: int = 7, path: str | None = None,
                 now: float | None = None) -> None:
    """Push the trial end out by `days` from now (admin grant)."""
    now = now or time.time()
    new_start = now - TRIAL_DAYS * DAY + days * DAY
    conn = connect(path)
    try:
        conn.execute("UPDATE plans SET trial_started_at=?, plan='trial', converted_at=NULL"
                     " WHERE account_id=?", (new_start, account_id))
        conn.commit()
    finally:
        conn.close()


def convert_to_paid(account_id: int, *, stripe_customer_id: str | None = None,
                    stripe_subscription_id: str | None = None, stripe_item_id: str | None = None,
                    path: str | None = None, now: float | None = None) -> None:
    now = now or time.time()
    conn = connect(path)
    try:
        conn.execute(
            "UPDATE plans SET plan='paid', converted_at=?,"
            " stripe_customer_id=COALESCE(?, stripe_customer_id),"
            " stripe_subscription_id=COALESCE(?, stripe_subscription_id),"
            " stripe_item_id=COALESCE(?, stripe_item_id)"
            " WHERE account_id=?",
            (now, stripe_customer_id, stripe_subscription_id, stripe_item_id, account_id))
        # Paid plans are autopilot-only (guidance is a trial-only "try it first" mode).
        conn.execute("UPDATE settings SET mode='autopilot' WHERE account_id=?", (account_id,))
        conn.commit()
    finally:
        conn.close()


def set_rate(account_id: int, rate: float, path: str | None = None) -> None:
    conn = connect(path)
    try:
        conn.execute("UPDATE plans SET rate=? WHERE account_id=?", (max(0.0, rate), account_id))
        conn.commit()
    finally:
        conn.close()


def get_tier(account_id: int, path: str | None = None) -> str:
    return get_plan(account_id, path).get("tier") or "payg"


def set_tier(account_id: int, tier: str, path: str | None = None) -> None:
    """Set the pricing tier and align the savings rate (payg=20%, sub tiers=15%)."""
    if tier not in TIERS:
        raise StoreError(f"tier must be one of {TIERS}")
    conn = connect(path)
    try:
        conn.execute("UPDATE plans SET tier=?, rate=? WHERE account_id=?",
                     (tier, TIER_RATES[tier], account_id))
        conn.commit()
    finally:
        conn.close()


def entitlement(deployment_id: str, path: str | None = None, now: float | None = None) -> dict:
    """Server-authoritative entitlement for a deployment, consumed by the brain.

    Returns whether routing is entitled at all, and whether decisions should be
    *applied* (autopilot) vs. only recommended (guidance/shadow). Lapsed/suspended
    accounts pass traffic through unrouted — never blocked.
    """
    now = now or time.time()
    acct = account_for_deployment(deployment_id, path)
    if not acct:
        return {"entitled": False, "apply": False, "mode": "off", "reason": "unknown deployment"}
    if acct["status"] != "active":
        return {"entitled": False, "apply": False, "mode": "off", "reason": "account suspended"}
    plan = get_plan(acct["id"], path)
    settings = get_settings(acct["id"], path)
    mode = settings["mode"]
    if plan.get("plan") == "paid":
        entitled = True
        reason = "paid"
        mode = "autopilot"  # paid plans are autopilot-only; guidance is trial-only
    else:
        ts = trial_status(acct["id"], path, now)
        entitled = ts["active"]
        reason = f"trial ({ts['days_left']}d left)" if entitled else "trial ended"
    apply = entitled and mode == "autopilot"
    # Gradual rollout: in autopilot, the customer can ramp what share of eligible
    # traffic is actually auto-routed (build trust first, then expand to 100%).
    apply_pct = int(settings.get("autopilot_pct", 100)) if apply else 0
    return {"entitled": entitled, "apply": apply, "apply_pct": apply_pct, "mode": mode,
            "reason": reason, "account_id": acct["id"], "plan": plan.get("plan", "trial")}


# --------------------------------------------------------------------------- #
# Metering + savings + billing
# --------------------------------------------------------------------------- #

def record_meter(deployment_id: str, *, requests: int = 0, routed: int = 0,
                 escalations: int = 0, baseline_cost: float = 0.0, actual_cost: float = 0.0,
                 realized_savings: float | None = None, opportunity_saved: float = 0.0,
                 caching_saved: float = 0.0, category: str | None = None,
                 ts: float | None = None, path: str | None = None) -> dict:
    """Record one aggregate metering report from a gateway. Dollars + counts only.

    `realized_savings` defaults to baseline_cost - actual_cost (never negative for
    billing). `opportunity_saved` is additional savings available but not yet
    captured (caching/Batch API). `caching_saved` is savings we DID capture by
    auto-applying caching. Both are shown for visibility and NEVER billed. Raises if
    the deployment is unknown."""
    if not account_for_deployment(deployment_id, path):
        raise StoreError("unknown deployment")
    if realized_savings is None:
        realized_savings = max(0.0, baseline_cost - actual_cost)
    ts = ts or time.time()
    conn = connect(path)
    try:
        cur = conn.execute(
            "INSERT INTO meter(deployment_id, ts, category, requests, routed, escalations,"
            " baseline_cost, actual_cost, realized_savings, opportunity_saved, caching_saved)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (deployment_id, ts, category, int(requests), int(routed), int(escalations),
             float(baseline_cost), float(actual_cost), float(realized_savings),
             max(0.0, float(opportunity_saved)), max(0.0, float(caching_saved))))
        meter_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "realized_savings": realized_savings, "meter_id": meter_id}


def mark_meter_reported(meter_id: int, path: str | None = None) -> None:
    """Mark a meter row as pushed to Stripe so the sync backstop never re-bills it."""
    conn = connect(path)
    try:
        conn.execute("UPDATE meter SET stripe_reported=1 WHERE id=?", (int(meter_id),))
        conn.commit()
    finally:
        conn.close()


def _account_savings(conn, account_id: int, since: float | None, until: float | None) -> dict:
    clause, params = "d.account_id=?", [account_id]
    if since is not None:
        clause += " AND m.ts>=?"; params.append(since)
    if until is not None:
        clause += " AND m.ts<?"; params.append(until)
    row = conn.execute(
        f"SELECT COALESCE(SUM(m.requests),0) AS requests,"
        f" COALESCE(SUM(m.routed),0) AS routed,"
        f" COALESCE(SUM(m.escalations),0) AS escalations,"
        f" COALESCE(SUM(m.baseline_cost),0) AS baseline,"
        f" COALESCE(SUM(m.actual_cost),0) AS actual,"
        f" COALESCE(SUM(m.realized_savings),0) AS savings,"
        f" COALESCE(SUM(m.opportunity_saved),0) AS opportunity,"
        f" COALESCE(SUM(m.caching_saved),0) AS caching"
        f" FROM meter m JOIN deployments d ON d.deployment_id=m.deployment_id"
        f" WHERE {clause}", params).fetchone()
    return dict(row)


def savings_summary(account_id: int, since: float | None = None, until: float | None = None,
                    path: str | None = None) -> dict:
    conn = connect(path)
    try:
        return _account_savings(conn, account_id, since, until)
    finally:
        conn.close()


def savings_by_category(account_id: int, since: float | None = None, path: str | None = None) -> list[dict]:
    clause, params = "d.account_id=?", [account_id]
    if since is not None:
        clause += " AND m.ts>=?"; params.append(since)
    conn = connect(path)
    try:
        rows = conn.execute(
            f"SELECT COALESCE(m.category,'(unlabeled)') AS category,"
            f" SUM(m.requests) AS requests, SUM(m.routed) AS routed,"
            f" SUM(m.escalations) AS escalations, SUM(m.realized_savings) AS savings"
            f" FROM meter m JOIN deployments d ON d.deployment_id=m.deployment_id"
            f" WHERE {clause} GROUP BY m.category ORDER BY savings DESC", params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def record_proof(deployment_id: str, comparisons: int, non_inferior: int,
                 ts: float | None = None, path: str | None = None) -> dict:
    """Record an aggregate side-by-side proof report (counts only — never the
    compared text). `comparisons` = judged pairs, `non_inferior` = how many the
    judge rated non-inferior at the cheaper model."""
    if not account_for_deployment(deployment_id, path):
        raise StoreError("unknown deployment")
    ts = ts or time.time()
    conn = connect(path)
    try:
        conn.execute("INSERT INTO proofs(deployment_id, ts, comparisons, non_inferior)"
                     " VALUES(?,?,?,?)", (deployment_id, ts, int(comparisons), int(non_inferior)))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


def proof_summary(account_id: int, since: float | None = None, path: str | None = None) -> dict:
    clause, params = "d.account_id=?", [account_id]
    if since is not None:
        clause += " AND p.ts>=?"; params.append(since)
    conn = connect(path)
    try:
        row = conn.execute(
            f"SELECT COALESCE(SUM(p.comparisons),0) comparisons,"
            f" COALESCE(SUM(p.non_inferior),0) non_inferior"
            f" FROM proofs p JOIN deployments d ON d.deployment_id=p.deployment_id"
            f" WHERE {clause}", params).fetchone()
    finally:
        conn.close()
    comp, ni = row["comparisons"], row["non_inferior"]
    return {"comparisons": comp, "non_inferior": ni,
            "rate": (ni / comp) if comp else None}


# --------------------------------------------------------------------------- #
# Password management + reset tokens
# --------------------------------------------------------------------------- #

def set_password(account_id: int, new_password: str, path: str | None = None) -> None:
    if len(new_password or "") < 8:
        raise StoreError("Password must be at least 8 characters.")
    pw_hash, salt = hash_password(new_password)
    conn = connect(path)
    try:
        conn.execute("UPDATE accounts SET pw_hash=?, pw_salt=? WHERE id=?",
                     (pw_hash, salt, account_id))
        conn.commit()
    finally:
        conn.close()


def create_reset(email: str, path: str | None = None, now: float | None = None) -> tuple[dict, str] | None:
    """Single-use reset/invite token for an account owner OR a team member.
    Returns (principal, token) or None — callers must not reveal which."""
    now = now or time.time()
    acct = get_account_by_email(email, path)
    member = None
    if acct and acct["status"] == "active":
        principal, account_id, member_id = acct, acct["id"], None
    else:
        member = get_member_by_email(email, path)
        if not member or member["status"] == "removed":
            return None
        principal, account_id, member_id = member, member["account_id"], member["id"]
    token = secrets.token_urlsafe(32)
    conn = connect(path)
    try:
        conn.execute("INSERT INTO resets(token, account_id, created_at, used, member_id)"
                     " VALUES(?,?,?,0,?)", (token, account_id, now, member_id))
        conn.commit()
    finally:
        conn.close()
    return principal, token


def consume_reset(token: str, new_password: str, path: str | None = None,
                  now: float | None = None) -> bool:
    """Validate an unused, unexpired token and set the password (account or member)."""
    now = now or time.time()
    conn = connect(path)
    try:
        row = conn.execute("SELECT * FROM resets WHERE token=?", (token,)).fetchone()
        if not row or row["used"] or (now - row["created_at"]) > RESET_TTL:
            return False
        row = dict(row)
        conn.execute("UPDATE resets SET used=1 WHERE token=?", (token,))
        conn.commit()
    finally:
        conn.close()
    if row.get("member_id"):
        set_member_password(row["member_id"], new_password, path)
    else:
        set_password(row["account_id"], new_password, path)
    return True


# --------------------------------------------------------------------------- #
# Per-customer tuning proposals (Track A floors / Track C rules) — admin review
# --------------------------------------------------------------------------- #

PROPOSAL_KINDS = ("floor", "rule")


def should_autoapprove(kind: str, stats: dict | None, min_samples: int, min_ni: float) -> bool:
    """Auto-approval is only for judge-validated *floor* drops with enough samples
    and a high non-inferiority rate. Rules (qualitative) always need a human."""
    if kind != "floor":
        return False
    stats = stats or {}
    samples = stats.get("samples") or 0
    rate = stats.get("non_inferior_rate")
    return samples >= min_samples and rate is not None and rate >= min_ni


def submit_proposal(deployment_id: str, kind: str, category: str, payload: dict,
                    stats: dict | None = None, path: str | None = None,
                    now: float | None = None, autoapprove: dict | None = None) -> dict:
    """A gateway proposes a per-customer tuning change (auto-derived from the
    customer's own traffic, validated by their judge — only the *proposal*
    reaches us: category + tiers/rule-spec + stats, never prompt text). Supersedes
    any earlier still-pending proposal of the same (account, kind, category).

    `autoapprove` (optional `{min_samples, min_ni}`) approves qualifying floor
    proposals on arrival, recording an auto note in the audit trail."""
    if kind not in PROPOSAL_KINDS:
        raise StoreError(f"kind must be one of {PROPOSAL_KINDS}")
    acct = account_for_deployment(deployment_id, path)
    if not acct:
        raise StoreError("unknown deployment")
    now = now or time.time()
    auto = bool(autoapprove and should_autoapprove(
        kind, stats, autoapprove.get("min_samples", 30), autoapprove.get("min_ni", 0.95)))
    status, decided_at, note = "pending", None, None
    if auto:
        s = stats or {}
        status, decided_at = "approved", now
        note = (f"auto-approved ({int(s.get('samples', 0))} samples, "
                f"{(100*(s.get('non_inferior_rate') or 0)):.0f}% non-inferior)")
    conn = connect(path)
    try:
        conn.execute("DELETE FROM proposals WHERE account_id=? AND kind=? AND category=?"
                     " AND status='pending'", (acct["id"], kind, category))
        cur = conn.execute(
            "INSERT INTO proposals(account_id, deployment_id, kind, category, payload, stats,"
            " status, created_at, decided_at, decided_by, note) VALUES(?,?,?,?,?,?,?,?,?,NULL,?)",
            (acct["id"], deployment_id, kind, category, json.dumps(payload),
             json.dumps(stats or {}), status, now, decided_at, note))
        pid = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "account_id": acct["id"], "proposal_id": pid, "auto_approved": auto}


def _row_proposal(r: dict) -> dict:
    return {**r, "payload": json.loads(r["payload"]), "stats": json.loads(r["stats"] or "{}")}


def list_proposals(account_id: int | None = None, status: str | None = "pending",
                   path: str | None = None) -> list[dict]:
    clause, params = [], []
    if account_id is not None:
        clause.append("account_id=?"); params.append(account_id)
    if status is not None:
        clause.append("status=?"); params.append(status)
    where = (" WHERE " + " AND ".join(clause)) if clause else ""
    conn = connect(path)
    try:
        rows = conn.execute(
            f"SELECT * FROM proposals{where} ORDER BY created_at DESC", params).fetchall()
        return [_row_proposal(dict(r)) for r in rows]
    finally:
        conn.close()


def count_pending_proposals(path: str | None = None) -> int:
    conn = connect(path)
    try:
        return conn.execute("SELECT COUNT(*) c FROM proposals WHERE status='pending'").fetchone()["c"]
    finally:
        conn.close()


def decide_proposal(proposal_id: int, status: str, decided_by: int | None = None,
                    note: str | None = None, path: str | None = None,
                    now: float | None = None) -> bool:
    """Approve/reject a pending proposal, recording who decided and an optional
    note (audit trail)."""
    if status not in ("approved", "rejected"):
        raise StoreError("status must be approved or rejected")
    now = now or time.time()
    conn = connect(path)
    try:
        cur = conn.execute(
            "UPDATE proposals SET status=?, decided_at=?, decided_by=?, note=?"
            " WHERE id=? AND status='pending'",
            (status, now, decided_by, (note or None), proposal_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def proposal_history(account_id: int, limit: int = 25, path: str | None = None) -> list[dict]:
    """Decided proposals for an account (audit trail), newest decision first,
    with the deciding admin's email resolved."""
    conn = connect(path)
    try:
        rows = conn.execute(
            "SELECT p.*, a.email AS decided_by_email FROM proposals p"
            " LEFT JOIN accounts a ON a.id=p.decided_by"
            " WHERE p.account_id=? AND p.status!='pending'"
            " ORDER BY p.decided_at DESC LIMIT ?", (account_id, limit)).fetchall()
        return [_row_proposal(dict(r)) for r in rows]
    finally:
        conn.close()


def approved_floors(account_id: int, path: str | None = None) -> dict:
    """Approved per-category floor overrides for this account (Track A). Format
    matches taxonomy.floor_tier's `floors` arg: {category: tier}."""
    floors = {}
    for p in list_proposals(account_id, status="approved", path=path):
        if p["kind"] == "floor":
            tier = p["payload"].get("proposed_tier")
            if tier is not None:
                floors[p["category"]] = int(tier)
    return floors


def approved_rules(account_id: int, path: str | None = None) -> list[dict]:
    """Approved per-customer classification rules (Track C), newest first."""
    return [p["payload"] for p in list_proposals(account_id, status="approved", path=path)
            if p["kind"] == "rule"]


def approved_policy_for_deployment(deployment_id: str, path: str | None = None) -> dict:
    acct = account_for_deployment(deployment_id, path)
    if not acct:
        return {"floors": {}, "rules": []}
    # Per-customer LEARNED floors are the Self-optimize / Managed benefit — only
    # served to those tiers. Pay-as-you-go gets the global calibrated floors (no
    # per-customer tuning). Customer-authored rules (Track C) are available to all.
    tier = get_tier(acct["id"], path)
    floors = approved_floors(acct["id"], path) if tier in ("self_optimize", "managed") else {}
    return {"floors": floors, "rules": approved_rules(acct["id"], path)}


# --------------------------------------------------------------------------- #
# Request logs (opt-in, per-request METADATA only — never prompt text)
# --------------------------------------------------------------------------- #

_LOG_COLS = ("ts", "category", "original_model", "routed_model", "applied", "escalated",
             "action", "status_code", "input_tokens", "output_tokens",
             "baseline_cost", "actual_cost", "realized_saved")


def record_logs(deployment_id: str, rows: list[dict], path: str | None = None) -> dict:
    """Store a batch of per-request metadata rows for a deployment."""
    acct = account_for_deployment(deployment_id, path)
    if not acct:
        raise StoreError("unknown deployment")
    conn = connect(path)
    try:
        conn.executemany(
            "INSERT INTO request_logs(account_id, deployment_id, ts, category, original_model,"
            " routed_model, applied, escalated, action, status_code, input_tokens, output_tokens,"
            " baseline_cost, actual_cost, realized_saved)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(acct["id"], deployment_id, r.get("ts") or 0, r.get("category"),
              r.get("original_model"), r.get("routed_model"), int(bool(r.get("applied"))),
              int(bool(r.get("escalated"))), r.get("action"), r.get("status_code"),
              int(r.get("input_tokens") or 0), int(r.get("output_tokens") or 0),
              float(r.get("baseline_cost") or 0), float(r.get("actual_cost") or 0),
              float(r.get("realized_saved") or 0)) for r in (rows or [])])
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "stored": len(rows or [])}


def recent_logs(account_id: int, limit: int = 100, path: str | None = None) -> list[dict]:
    conn = connect(path)
    try:
        rows = conn.execute(
            "SELECT * FROM request_logs WHERE account_id=? ORDER BY ts DESC, id DESC LIMIT ?",
            (account_id, limit)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def logs_count(account_id: int, path: str | None = None) -> int:
    conn = connect(path)
    try:
        return conn.execute("SELECT COUNT(*) c FROM request_logs WHERE account_id=?",
                            (account_id,)).fetchone()["c"]
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Webhooks (HMAC-signed event delivery to customer endpoints)
# --------------------------------------------------------------------------- #

def create_webhook(account_id: int, url: str, events: str = "all",
                   path: str | None = None, now: float | None = None) -> dict:
    if not (url or "").startswith(("http://", "https://")):
        raise StoreError("webhook url must be http(s)")
    now = now or time.time()
    secret = "whsec_" + secrets.token_urlsafe(24)
    conn = connect(path)
    try:
        cur = conn.execute("INSERT INTO webhooks(account_id, url, secret, events, active, created_at)"
                           " VALUES(?,?,?,?,1,?)", (account_id, url.strip(), secret,
                                                    (events or "all").strip(), now))
        wid = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return {"id": wid, "secret": secret, "url": url}


def list_webhooks(account_id: int, path: str | None = None) -> list[dict]:
    conn = connect(path)
    try:
        rows = conn.execute("SELECT * FROM webhooks WHERE account_id=? ORDER BY created_at DESC",
                            (account_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_webhook(webhook_id: int, account_id: int, path: str | None = None) -> bool:
    conn = connect(path)
    try:
        cur = conn.execute("DELETE FROM webhooks WHERE id=? AND account_id=?", (webhook_id, account_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def _matching_webhooks(account_id: int, event_type: str, path: str | None = None) -> list[dict]:
    out = []
    for w in list_webhooks(account_id, path):
        if not w["active"]:
            continue
        ev = w["events"]
        if ev == "all" or event_type in {e.strip() for e in ev.split(",")}:
            out.append(w)
    return out


def sign_payload(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def deliver_event(account_id: int, event_type: str, data: dict, path: str | None = None,
                  post_fn=None) -> int:
    """Fire `event_type` to the account's subscribed webhooks (HMAC-signed,
    best-effort, off-thread). Returns how many were dispatched. `post_fn` (tests)
    receives (url, body_bytes, headers) synchronously instead of HTTP."""
    hooks = _matching_webhooks(account_id, event_type, path)
    if not hooks:
        return 0
    body = json.dumps({"event": event_type, "ts": time.time(), "data": data},
                      separators=(",", ":")).encode()

    def _send(url, secret):
        headers = {"content-type": "application/json", "user-agent": "Outlay-Webhook",
                   "x-outlay-event": event_type, "x-outlay-signature": sign_payload(secret, body)}
        if post_fn is not None:
            post_fn(url, body, headers)
            return
        import urllib.request
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            urllib.request.urlopen(req, timeout=5).close()
        except Exception:  # noqa: BLE001 — delivery is best-effort
            pass

    for w in hooks:
        if post_fn is not None:
            _send(w["url"], w["secret"])
        else:
            import threading
            threading.Thread(target=_send, args=(w["url"], w["secret"]), daemon=True).start()
    return len(hooks)


# --------------------------------------------------------------------------- #
# SSO (OIDC) + SCIM provisioning (per account)
# --------------------------------------------------------------------------- #

def get_sso(account_id: int, path: str | None = None) -> dict:
    conn = connect(path)
    try:
        row = conn.execute("SELECT * FROM sso_configs WHERE account_id=?", (account_id,)).fetchone()
        return dict(row) if row else {"account_id": account_id, "enabled": 0}
    finally:
        conn.close()


def set_sso(account_id: int, *, enabled: bool | None = None, domain: str | None = None,
            client_id: str | None = None, client_secret: str | None = None,
            auth_url: str | None = None, token_url: str | None = None,
            userinfo_url: str | None = None, default_role: str | None = None,
            path: str | None = None) -> dict:
    cur = get_sso(account_id, path)
    conn = connect(path)
    try:
        if "id" not in cur and not cur.get("client_id"):
            conn.execute("INSERT OR IGNORE INTO sso_configs(account_id) VALUES(?)", (account_id,))
        new = {
            "enabled": int(cur.get("enabled") or 0) if enabled is None else int(enabled),
            "domain": (cur.get("domain") if domain is None else domain.strip().lower()) or None,
            "client_id": cur.get("client_id") if client_id is None else client_id.strip(),
            "client_secret": cur.get("client_secret") if client_secret is None else client_secret.strip(),
            "auth_url": cur.get("auth_url") if auth_url is None else auth_url.strip(),
            "token_url": cur.get("token_url") if token_url is None else token_url.strip(),
            "userinfo_url": cur.get("userinfo_url") if userinfo_url is None else userinfo_url.strip(),
            "default_role": (cur.get("default_role") or "member") if default_role is None
                            else (default_role if default_role in TEAM_ROLES else "member"),
        }
        conn.execute("UPDATE sso_configs SET enabled=?, domain=?, client_id=?, client_secret=?,"
                     " auth_url=?, token_url=?, userinfo_url=?, default_role=? WHERE account_id=?",
                     (new["enabled"], new["domain"], new["client_id"], new["client_secret"],
                      new["auth_url"], new["token_url"], new["userinfo_url"], new["default_role"],
                      account_id))
        conn.commit()
    finally:
        conn.close()
    return get_sso(account_id, path)


def sso_by_domain(domain: str, path: str | None = None) -> dict | None:
    domain = (domain or "").strip().lower()
    if not domain:
        return None
    conn = connect(path)
    try:
        row = conn.execute("SELECT * FROM sso_configs WHERE domain=? AND enabled=1", (domain,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def rotate_scim_token(account_id: int, path: str | None = None) -> str:
    """Mint a SCIM bearer token (shown once; stored hashed)."""
    token = "scim_" + secrets.token_urlsafe(24)
    get_sso(account_id, path)  # ensure a row exists
    conn = connect(path)
    try:
        conn.execute("INSERT OR IGNORE INTO sso_configs(account_id) VALUES(?)", (account_id,))
        conn.execute("UPDATE sso_configs SET scim_token_hash=? WHERE account_id=?",
                     (hashlib.sha256(token.encode()).hexdigest(), account_id))
        conn.commit()
    finally:
        conn.close()
    return token


def resolve_scim_token(token: str, path: str | None = None) -> int | None:
    if not token or not token.startswith("scim_"):
        return None
    h = hashlib.sha256(token.strip().encode()).hexdigest()
    conn = connect(path)
    try:
        row = conn.execute("SELECT account_id FROM sso_configs WHERE scim_token_hash=?", (h,)).fetchone()
        return row["account_id"] if row else None
    finally:
        conn.close()


def provision_member(account_id: int, email: str, role: str | None = None,
                     path: str | None = None) -> dict:
    """JIT/SCIM provisioning: return the existing active member or create one
    (active). Used by SSO login and SCIM."""
    email = (email or "").strip().lower()
    existing = get_member_by_email(email, path)
    if existing and existing["account_id"] == account_id:
        if existing["status"] == "removed":
            conn = connect(path)
            try:
                conn.execute("UPDATE members SET status='active' WHERE id=?", (existing["id"],))
                conn.commit()
            finally:
                conn.close()
        return get_member(existing["id"], path)
    if existing:  # belongs to another org
        raise StoreError("email already belongs to another account")
    m = create_member(account_id, email, role or "member", path)
    # SSO/SCIM members are active immediately (no password; they sign in via IdP)
    conn = connect(path)
    try:
        conn.execute("UPDATE members SET status='active' WHERE id=?", (m["id"],))
        conn.commit()
    finally:
        conn.close()
    return get_member(m["id"], path)


def cycle_start(now: float | None = None) -> float:
    now = now or time.time()
    dt = datetime.fromtimestamp(now, tz=timezone.utc)
    return datetime(dt.year, dt.month, 1, tzinfo=timezone.utc).timestamp()


def bill_estimate(account_id: int, path: str | None = None, now: float | None = None) -> dict:
    """Current-cycle bill = rate * realized savings this calendar month.

    During the trial the bill is $0 (free), but we also surface what it *would*
    be, so the value is concrete at conversion time."""
    now = now or time.time()
    plan = get_plan(account_id, path)
    rate = plan.get("rate", DEFAULT_RATE)
    cyc = cycle_start(now)
    cycle = savings_summary(account_id, since=cyc, until=None, path=path)
    lifetime = savings_summary(account_id, path=path)
    would_bill = round(rate * cycle["savings"], 2)
    is_paid = plan.get("plan") == "paid"
    return {
        "rate": rate,
        "cycle_start": cyc,
        "cycle_savings": cycle["savings"],
        "lifetime_savings": lifetime["savings"],
        "bill": would_bill if is_paid else 0.0,
        "would_bill": would_bill,
        "is_paid": is_paid,
        "net_customer_value": round(cycle["savings"] - (would_bill if is_paid else 0.0), 2),
    }


def revenue_overview(path: str | None = None, now: float | None = None) -> dict:
    """Vendor-side revenue + savings rollup across all accounts (admin)."""
    now = now or time.time()
    cyc = cycle_start(now)
    accounts = list_accounts(path)
    total_savings = total_revenue = cycle_savings = cycle_revenue = 0.0
    total_baseline = cycle_baseline = 0.0
    n_trial = n_paid = n_suspended = 0
    for a in accounts:
        if a["status"] == "suspended":
            n_suspended += 1
        plan = get_plan(a["id"], path)
        rate = plan.get("rate", DEFAULT_RATE)
        life = savings_summary(a["id"], path=path)
        cyc_sum = savings_summary(a["id"], since=cyc, path=path)
        total_savings += life["savings"]; total_baseline += life["baseline"]
        cycle_savings += cyc_sum["savings"]; cycle_baseline += cyc_sum["baseline"]
        if plan.get("plan") == "paid":
            n_paid += 1
            total_revenue += rate * life["savings"]
            cycle_revenue += rate * cyc_sum["savings"]
        else:
            n_trial += 1
    return {
        "n_accounts": len(accounts), "n_trial": n_trial, "n_paid": n_paid,
        "n_suspended": n_suspended,
        # Keep sub-cent precision: money() still displays cents, but the
        # tokens-saved view (and parity with per-account rows) needs the real
        # value — rounding to 2 here collapsed sub-cent savings to $0.00 / 0 tokens.
        "total_savings_delivered": round(total_savings, 6),
        "total_revenue": round(total_revenue, 6),
        "cycle_savings": round(cycle_savings, 6),
        "cycle_revenue": round(cycle_revenue, 6),
        # bill-cut % across all customers (early-confidence metric, like the dashboard)
        "cycle_pct": round(100 * cycle_savings / cycle_baseline) if cycle_baseline else 0,
        "total_pct": round(100 * total_savings / total_baseline) if total_baseline else 0,
    }
