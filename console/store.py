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

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import struct
import time
from datetime import datetime, timezone

_log = logging.getLogger("outlay.store")

# Each account's current report is stored as one JSON blob (outlay_reports.report).
# That's fine today but grows with the per-ticket row tail — a known scale ceiling at
# millions of events/month. We don't truncate (finance needs the full tail), but we
# DO watch the blob size so the ceiling is observable long before it bites: above this
# soft limit we log a warning and flag it on /admin/health. Tunable via env.
OUTLAY_REPORT_SOFT_LIMIT_BYTES = int(os.environ.get("OUTLAY_REPORT_SOFT_LIMIT_BYTES", 5_000_000))

TRIAL_DAYS = 14
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

# Value-level scan (complements the key-name denylist): refuse a payload whose string
# VALUES look like a credential, so a secret slipped under an innocuous field name
# (e.g. {"note": "sk-ant-..."}) is still caught. Patterns are high-signal prefixes +
# JWTs + long Bearer/hex blobs — chosen to avoid false-positives on dollars/counts/ids.
_SECRET_VALUE_RE = __import__("re").compile(
    r"(sk-[A-Za-z0-9-]{16,}"          # OpenAI/Anthropic-style keys
    r"|sk-ant-[A-Za-z0-9_-]{8,}"
    r"|gh[pousr]_[A-Za-z0-9]{20,}"    # GitHub tokens
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"  # Slack tokens
    r"|AKIA[0-9A-Z]{12,}"             # AWS access key id
    r"|AIza[0-9A-Za-z_-]{20,}"        # Google API key
    r"|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}"  # JWT
    r"|[Bb]earer\s+[A-Za-z0-9._-]{16,})")


def _looks_secret_value(s) -> bool:
    return isinstance(s, str) and bool(_SECRET_VALUE_RE.search(s))


def forbidden_payload_reason(obj, path: str = "") -> str | None:
    """Return a human reason if `obj` (at any nesting depth) carries a forbidden KEY
    NAME (prompt/output/secret fields) or a string VALUE that looks like a credential;
    else None. The boundary that keeps prompts/outputs/keys out of vendor storage."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in FORBIDDEN_METER_KEYS:
                return f"forbidden key '{str(path + '.' + str(k)).lstrip('.')}'"
            hit = forbidden_payload_reason(v, f"{path}.{k}")
            if hit:
                return hit
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hit = forbidden_payload_reason(v, f"{path}[{i}]")
            if hit:
                return hit
    elif _looks_secret_value(obj):
        return f"value at '{path.lstrip('.') or '(root)'}' looks like a credential"
    return None


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
    persona TEXT NOT NULL DEFAULT '',             -- 'business' | 'eng' : which experience this person sees
    PRIMARY KEY (account_id, member_id)
);
CREATE TABLE IF NOT EXISTS dashboard_views (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL DEFAULT 0,         -- whose saved view (per-person personalization)
    name TEXT NOT NULL,                           -- e.g. "Board readout", "Platform deep-dive"
    lens TEXT NOT NULL DEFAULT '{}',              -- JSON: {group_by, top_n} (the Home lens)
    is_default INTEGER NOT NULL DEFAULT 0         -- 1 = the view that loads on Home for this person
);
CREATE INDEX IF NOT EXISTS idx_dashviews ON dashboard_views(account_id, member_id);
CREATE TABLE IF NOT EXISTS dashboard_prefs (
    account_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL DEFAULT 0,
    layout TEXT NOT NULL DEFAULT '{}',            -- JSON: {order:[card keys], hidden:[card keys]}
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
CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    webhook_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    status TEXT NOT NULL,                        -- 'delivered' | 'failed'
    attempts INTEGER NOT NULL DEFAULT 1,
    status_code INTEGER,                         -- HTTP status of the last attempt, if any
    error TEXT,                                  -- short error from the last failed attempt
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_whd_acct ON webhook_deliveries(account_id, id);
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
CREATE TABLE IF NOT EXISTS login_throttle (
    email TEXT PRIMARY KEY,            -- per-identity failed-login tracking (owners + members)
    fails INTEGER NOT NULL DEFAULT 0,
    locked_until REAL                 -- unix ts the lockout lifts; NULL = not locked
);
CREATE TABLE IF NOT EXISTS webauthn_credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id),  -- the org
    member_id INTEGER NOT NULL DEFAULT 0,                 -- 0 = the account owner; else the member
    credential_id TEXT UNIQUE NOT NULL,                   -- base64url, the authenticator's credential id
    public_key TEXT NOT NULL,                             -- base64url COSE public key (not secret)
    sign_count INTEGER NOT NULL DEFAULT 0,                -- clone-detection counter
    label TEXT,                                           -- user-friendly name ("MacBook Touch ID")
    created_at REAL NOT NULL,
    last_used_at REAL
);
CREATE INDEX IF NOT EXISTS idx_webauthn_principal ON webauthn_credentials (account_id, member_id);
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
CREATE TABLE IF NOT EXISTS outlay_program_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    program_id INTEGER NOT NULL,
    ts REAL NOT NULL,
    spent_usd REAL NOT NULL           -- the program's cumulative spend at each data refresh (pacing substrate)
);
CREATE INDEX IF NOT EXISTS idx_program_history ON outlay_program_history (account_id, program_id, ts);
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
CREATE TABLE IF NOT EXISTS cron_runs (
    job TEXT PRIMARY KEY,             -- 'sync-due' | 'digest-due'
    last_run_at REAL NOT NULL,        -- when the scheduler last hit this endpoint
    detail TEXT                       -- JSON summary of the last run
);
CREATE TABLE IF NOT EXISTS outlay_programs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    name TEXT NOT NULL,                          -- e.g. "Platform"
    members TEXT NOT NULL DEFAULT '[]',          -- JSON: [{scope_type, scope_id}] (team/project/class/overall)
    limit_usd REAL NOT NULL,
    period_days INTEGER NOT NULL DEFAULT 90,
    enforce_mode TEXT NOT NULL DEFAULT 'alert',  -- 'alert' (detect+notify) | 'hard' (gateway blocks/route-down)
    action TEXT NOT NULL DEFAULT 'block',        -- when 'hard' + over: 'block' | 'downgrade'
    floor_model TEXT,                            -- target model for 'downgrade'
    last_status TEXT
);
CREATE INDEX IF NOT EXISTS idx_program_acct ON outlay_programs(account_id);
CREATE TABLE IF NOT EXISTS outlay_commitment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    provider TEXT NOT NULL DEFAULT '',           -- 'anthropic' | 'openai' | ...
    kind TEXT NOT NULL DEFAULT 'committed_spend', -- 'committed_spend' | 'provisioned'
    amount_usd REAL NOT NULL,                    -- the committed amount over the term
    used_to_date_usd REAL NOT NULL DEFAULT 0,    -- consumption to date (customer-input metadata)
    start_ts REAL NOT NULL,
    end_ts REAL NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_commitment_acct ON outlay_commitment(account_id);
CREATE TABLE IF NOT EXISTS outlay_work_key (
    account_id INTEGER NOT NULL,
    api_key_id TEXT NOT NULL,
    classification TEXT NOT NULL,        -- 'work' | 'non_work'
    PRIMARY KEY (account_id, api_key_id)
);
CREATE TABLE IF NOT EXISTS outlay_work_enforce (
    account_id INTEGER NOT NULL,
    team_id TEXT NOT NULL,
    block_non_work INTEGER NOT NULL DEFAULT 0,  -- opt-in: block flagged/labeled non-work for this team
    block_unknown INTEGER NOT NULL DEFAULT 0,   -- opt-in (stricter): also block untracked/unknown
    PRIMARY KEY (account_id, team_id)
);
CREATE TABLE IF NOT EXISTS outlay_program_enforcement (
    program_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    day TEXT NOT NULL,                -- 'YYYY-MM-DD' (UTC) bucket
    count INTEGER NOT NULL DEFAULT 0, -- enforcement actions (block + route-down) that day
    PRIMARY KEY (program_id, day)
);
"""

WEBHOOK_EVENTS = ("budget.warn", "budget.over", "program.warn", "program.over",
                  "anomaly.detected", "proposal.pending", "account.suspended")

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
    "ALTER TABLE outlay_history ADD COLUMN breakdown TEXT",  # JSON: top team/class spend per snapshot → movers
    "ALTER TABLE outlay_connections ADD COLUMN identity_map TEXT",  # JSON: identifier/domain → team
    "ALTER TABLE outlay_connections ADD COLUMN alerted_anomalies TEXT",  # JSON: ticket ids already alerted
    "ALTER TABLE accounts ADD COLUMN digest_weekly INTEGER NOT NULL DEFAULT 1",  # weekly spend digest on/off
    "ALTER TABLE accounts ADD COLUMN digest_last_at REAL",  # last weekly digest send time
    "ALTER TABLE outlay_connections ADD COLUMN anomaly_threshold REAL",  # runaway flag multiple (default 3x)
    "ALTER TABLE outlay_connections ADD COLUMN muted_tickets TEXT",  # JSON: ticket ids muted from anomalies
    "ALTER TABLE outlay_connections ADD COLUMN slack_webhook TEXT",  # Slack/Teams incoming webhook for alerts
    "ALTER TABLE outlay_connections ADD COLUMN sync_fail_count INTEGER NOT NULL DEFAULT 0",  # consecutive auto-sync failures
    "ALTER TABLE outlay_connections ADD COLUMN sync_alerted_at REAL",  # last stale/failed-sync alert sent (de-dupe)
    "ALTER TABLE accounts ADD COLUMN retention_days INTEGER NOT NULL DEFAULT 0",  # 0 = keep history forever; else purge snapshots older than N days
    "ALTER TABLE accounts ADD COLUMN close_pack_monthly INTEGER NOT NULL DEFAULT 0",  # email the monthly close pack (FOCUS CSV + summary)
    "ALTER TABLE accounts ADD COLUMN close_pack_last_at REAL",  # last close-pack send time
    "ALTER TABLE api_keys ADD COLUMN expires_at REAL",  # optional key expiry; NULL = never
    "ALTER TABLE webhook_deliveries ADD COLUMN payload TEXT",  # exact signed body, for durable redelivery
    "ALTER TABLE webhook_deliveries ADD COLUMN next_attempt_at REAL",  # when a failed delivery is due to retry; NULL = terminal
    "ALTER TABLE outlay_programs ADD COLUMN enforced_count INTEGER NOT NULL DEFAULT 0",  # times the gateway blocked/route-down'd for this program
    "ALTER TABLE outlay_programs ADD COLUMN last_enforced_at REAL",  # last enforcement action
    "ALTER TABLE accounts ADD COLUMN demo_mode INTEGER NOT NULL DEFAULT 0",  # 1 = this (gated) account is showing seeded demo data
    "ALTER TABLE outlay_connections ADD COLUMN identity_names TEXT",  # JSON {identifier: display name} for usage-by-person
    "ALTER TABLE outlay_connections ADD COLUMN identity_titles TEXT",  # JSON {identifier: job title} (eng direct reports)
    "ALTER TABLE outlay_programs ADD COLUMN start_ts REAL",  # program timeline start (unix); NULL → treat as created/now
    "ALTER TABLE outlay_programs ADD COLUMN end_ts REAL",  # program timeline end (unix); NULL → start + period_days
    # Gov-readiness security hardening:
    "ALTER TABLE accounts ADD COLUMN session_epoch INTEGER NOT NULL DEFAULT 0",  # bump to invalidate all sessions (logout-everywhere / password change)
    "ALTER TABLE accounts ADD COLUMN totp_secret TEXT",  # base32 TOTP secret (encrypted at rest); set when channel='totp'
    "ALTER TABLE members ADD COLUMN session_epoch INTEGER NOT NULL DEFAULT 0",  # same, per invited member
    # Per-member MFA (TOTP) so an org require_mfa policy can compel invited teammates, not just owners/admins.
    "ALTER TABLE members ADD COLUMN twofa_enabled INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE members ADD COLUMN twofa_channel TEXT",          # 'totp' (members are authenticator-only)
    "ALTER TABLE members ADD COLUMN totp_secret TEXT",            # base32 TOTP secret, encrypted at rest
    "ALTER TABLE settings ADD COLUMN require_mfa INTEGER NOT NULL DEFAULT 0",  # admin policy: every member must have MFA enrolled
    "ALTER TABLE settings ADD COLUMN session_idle_min INTEGER NOT NULL DEFAULT 0",  # idle timeout (minutes); 0 = default
    "ALTER TABLE settings ADD COLUMN session_max_hours INTEGER NOT NULL DEFAULT 0",  # absolute session lifetime (hours); 0 = default
    "ALTER TABLE settings ADD COLUMN security_webhook TEXT",  # incident/breach notification webhook (customer's SOC/SIEM)
    "ALTER TABLE settings ADD COLUMN data_region TEXT",  # surfaced data-residency region label
    "ALTER TABLE accounts ADD COLUMN name TEXT",  # owner's display name (optional); falls back to email alias
    "ALTER TABLE members ADD COLUMN name TEXT",   # invited member's display name (optional)
]

OTP_TTL = 600          # one-time code lifetime (seconds)
OTP_MAX_ATTEMPTS = 5   # wrong tries before a code is burned

TEAM_ROLES = ("admin", "member", "billing")

RESET_TTL = 3600  # password-reset token lifetime (seconds)


# Cron jobs we expect a scheduler to drive, and the max age (seconds) before we
# call a job stale. Both endpoints are meant to run daily; 36h tolerates one miss.
CRON_JOBS = {"sync-due": 36 * 3600, "digest-due": 36 * 3600}


def mark_cron_run(job: str, detail=None, now: float | None = None,
                  path: str | None = None) -> None:
    """Stamp that a scheduled job just ran, so a missing scheduler is observable
    (otherwise the digest/close-pack/retention/redelivery sweeps silently never fire).
    `detail` may be a dict (JSON-encoded) or a string."""
    if isinstance(detail, (dict, list)):
        detail = json.dumps(detail, separators=(",", ":"))
    conn = connect(path)
    try:
        conn.execute(
            "INSERT INTO cron_runs(job, last_run_at, detail) VALUES(?,?,?)"
            " ON CONFLICT(job) DO UPDATE SET last_run_at=excluded.last_run_at, detail=excluded.detail",
            (job, now or time.time(), (detail or "")[:500]))
        conn.commit()
    finally:
        conn.close()


def get_cron_runs(path: str | None = None) -> dict:
    conn = connect(path)
    try:
        rows = conn.execute("SELECT job, last_run_at, detail FROM cron_runs").fetchall()
        return {r["job"]: {"last_run_at": r["last_run_at"], "detail": r["detail"]} for r in rows}
    finally:
        conn.close()


def cron_health(now: float | None = None, path: str | None = None) -> dict:
    """Per-job freshness for the health surface: {job: {last_run_at, age_seconds,
    stale, ran}}. `stale` is True when overdue or never seen."""
    now = now or time.time()
    runs = get_cron_runs(path)
    out = {}
    for job, max_age in CRON_JOBS.items():
        r = runs.get(job)
        last = r["last_run_at"] if r else None
        age = (now - last) if last else None
        out[job] = {"last_run_at": last, "age_seconds": age, "ran": bool(last),
                    "stale": (age is None or age > max_age)}
    return out


def init_db(path: str | None = None) -> None:
    conn = connect(path)
    try:
        conn.executescript(SCHEMA)
        for stmt in _MIGRATIONS:
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass  # column already exists
        # Reframe: the 'finance leader' persona is now 'business leader'. Migrate any
        # existing rows so a returning user keeps their experience. Idempotent.
        try:
            conn.execute("UPDATE personas SET persona='business' WHERE persona='finance'")
        except sqlite3.OperationalError:
            pass
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
                 member_id: int = 0, epoch: int = 0, seen: float | None = None,
                 path: str | None = None) -> str:
    """Signed stateless session. Carries `issued` (absolute lifetime), `seen`
    (sliding idle-timeout anchor, refreshed on activity), and `epoch` (bumped to
    revoke all sessions on logout-everywhere / password change)."""
    now = int(time.time())
    seen = int(seen if seen is not None else now)
    payload = f"{account_id}:{role}:{team_role}:{member_id}:{now}:{seen}:{int(epoch)}"
    sig = hmac.new(_secret(path), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def reseal_session(token: str, path: str | None = None) -> str | None:
    """Re-issue a valid token with `seen` bumped to now (sliding refresh), preserving
    issued/epoch. Returns None if the token is invalid."""
    sess = read_session(token, path)
    if not sess:
        return None
    now = int(time.time())
    payload = (f"{sess['account_id']}:{sess['role']}:{sess['team_role']}:"
               f"{sess['member_id']}:{int(sess['issued'])}:{now}:{int(sess['epoch'])}")
    sig = hmac.new(_secret(path), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def read_session(token: str, path: str | None = None) -> dict | None:
    try:
        account_id, role, team_role, member_id, issued, seen, epoch, sig = token.rsplit(":", 7)
    except (ValueError, AttributeError):
        return None
    payload = f"{account_id}:{role}:{team_role}:{member_id}:{issued}:{seen}:{epoch}"
    expected = hmac.new(_secret(path), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    if time.time() - float(issued) > SESSION_TTL:   # hard absolute cap (per-account max enforced in _current)
        return None
    return {"account_id": int(account_id), "role": role, "team_role": team_role,
            "member_id": int(member_id), "issued": float(issued),
            "seen": float(seen), "epoch": int(epoch)}


def bump_session_epoch(account_id: int, member_id: int = 0, path: str | None = None) -> None:
    """Invalidate all of this principal's existing sessions (logout-everywhere)."""
    conn = connect(path)
    try:
        if member_id:
            conn.execute("UPDATE members SET session_epoch=session_epoch+1 WHERE id=?", (member_id,))
        else:
            conn.execute("UPDATE accounts SET session_epoch=session_epoch+1 WHERE id=?", (account_id,))
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Accounts
# --------------------------------------------------------------------------- #

class StoreError(ValueError):
    pass


def create_account(email: str, password: str, company: str = "", role: str = "customer",
                   path: str | None = None, now: float | None = None,
                   consent: bool = False, name: str = "") -> dict:
    """Create an account + its deployment + default settings + a started trial.
    `consent=True` records that the owner accepted the Terms + Privacy Policy.
    `name` is an optional display name; when blank we fall back to the email alias."""
    email = (email or "").strip().lower()
    if "@" not in email or len(email) < 5:
        raise StoreError("Enter a valid email address.")
    problem = password_problem(password)
    if problem:
        raise StoreError(problem)
    now = now or time.time()
    pw_hash, salt = hash_password(password)
    conn = connect(path)
    try:
        try:
            cur = conn.execute(
                "INSERT INTO accounts(email, company, name, pw_hash, pw_salt, role, status, created_at,"
                " tos_accepted_at) VALUES(?,?,?,?,?,?, 'active', ?, ?)",
                (email, (company or "").strip()[:200], (name or "").strip()[:120], pw_hash, salt,
                 role, now, now if consent else None))
        except sqlite3.IntegrityError:
            raise StoreError("An account with that email already exists.")
        account_id = cur.lastrowid
        dep = "dep_" + secrets.token_hex(12)
        conn.execute("INSERT INTO deployments(deployment_id, account_id, label, created_at)"
                     " VALUES(?,?,?,?)", (dep, account_id, "default", now))
        conn.execute("INSERT INTO settings(account_id) VALUES(?)", (account_id,))
        # trial_started_at = 0 → the trial hasn't started yet; the 14-day clock
        # begins at setup completion (the first real, non-sample report), via
        # start_trial(). Until then the account is fully entitled but not counting down.
        conn.execute("INSERT INTO plans(account_id, plan, rate, trial_started_at)"
                     " VALUES(?, 'trial', ?, 0)", (account_id, DEFAULT_RATE))
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


def set_account_name(account_id: int, name: str, path: str | None = None) -> None:
    """Set the owner's display name (blank clears it → fall back to email alias)."""
    conn = connect(path)
    try:
        conn.execute("UPDATE accounts SET name=? WHERE id=?",
                     ((name or "").strip()[:120], account_id))
        conn.commit()
    finally:
        conn.close()


def set_member_name(member_id: int, account_id: int, name: str, path: str | None = None) -> None:
    """Set an invited member's display name (scoped to their org)."""
    conn = connect(path)
    try:
        conn.execute("UPDATE members SET name=? WHERE id=? AND account_id=?",
                     ((name or "").strip()[:120], member_id, account_id))
        conn.commit()
    finally:
        conn.close()


def display_name(principal: dict | None) -> str:
    """Best display name for an account/member row: explicit name, else email alias."""
    if not principal:
        return ""
    name = (principal.get("name") or "").strip()
    if name:
        return name
    email = (principal.get("email") or "").strip()
    return email.split("@")[0] if "@" in email else email


def authenticate(email: str, password: str, path: str | None = None) -> dict | None:
    acct = get_account_by_email(email, path)
    if not acct or acct["status"] != "active":
        return None
    if not verify_password(password, acct["pw_hash"], acct["pw_salt"]):
        return None
    return acct


# --------------------------------------------------------------------------- #
# Password policy (NIST SP 800-63B: length over complexity + breach screening)
# --------------------------------------------------------------------------- #

PASSWORD_MIN_LEN = 8
# A small bundled denylist of the most common/breached passwords — the offline
# floor of "screen against known-breached" (AC/IA, 800-63B 5.1.1.2). The online
# HIBP k-anonymity check (below) extends this and fails OPEN on any network error,
# so signups never break on a transient outage.
_COMMON_WEAK = {
    "password", "password1", "password123", "passw0rd", "123456", "1234567",
    "12345678", "123456789", "1234567890", "qwerty", "qwerty123", "abc123",
    "111111", "000000", "iloveyou", "admin", "admin123", "letmein", "welcome",
    "welcome1", "monkey", "dragon", "sunshine", "princess", "football", "baseball",
    "trustno1", "changeme", "secret", "master", "shadow", "superman", "michael",
    "outlay", "outlay123", "test1234", "pass1234", "p@ssw0rd", "qwertyuiop",
}


def _hibp_breached(password: str) -> bool | None:
    """k-anonymity check against Have I Been Pwned. Sends only the first 5 hex chars
    of the SHA-1; never the password. Returns True/False, or None on any error
    (caller treats None as 'not breached' — fail open, never block on a hiccup)."""
    try:
        import urllib.request
        sha1 = hashlib.sha1(password.encode()).hexdigest().upper()
        prefix, suffix = sha1[:5], sha1[5:]
        req = urllib.request.Request(
            f"https://api.pwnedpasswords.com/range/{prefix}",
            headers={"User-Agent": "Outlay-pw-check", "Add-Padding": "true"})
        with urllib.request.urlopen(req, timeout=3) as resp:  # noqa: S310
            body = resp.read().decode("utf-8", "replace")
        for line in body.splitlines():
            h, _, count = line.partition(":")
            if h.strip().upper() == suffix and count.strip() not in ("", "0"):
                return True
        return False
    except Exception:  # noqa: BLE001 — fail open
        return None


def password_problem(password: str) -> str | None:
    """Return a user-facing reason the password is unacceptable, or None if OK.
    Enforces NIST 800-63B: a minimum length, and screening against common/breached
    passwords (always the bundled list; the online HIBP check runs only when
    CONSOLE_HIBP_CHECK=1, so tests/dev stay offline and fast)."""
    pw = password or ""
    if len(pw) < PASSWORD_MIN_LEN:
        return f"Password must be at least {PASSWORD_MIN_LEN} characters."
    if len(pw) > 200:
        return "Password is too long (max 200 characters)."
    if pw.lower() in _COMMON_WEAK:
        return "That password is on the breached/common-password list — choose a different one."
    if os.environ.get("CONSOLE_HIBP_CHECK") == "1" and _hibp_breached(pw) is True:
        return "That password has appeared in a known data breach — choose a different one."
    return None


# --------------------------------------------------------------------------- #
# Login lockout / throttling (NIST 800-53 AC-7)
# --------------------------------------------------------------------------- #

LOCKOUT_THRESHOLD = 5      # consecutive failures before lockout
LOCKOUT_SECONDS = 900      # 15-minute lockout window


def login_locked(email: str, path: str | None = None, now: float | None = None) -> int:
    """Seconds remaining on a lockout for this identity, or 0 if not locked."""
    email = (email or "").strip().lower()
    now = now or time.time()
    conn = connect(path)
    try:
        row = conn.execute("SELECT locked_until FROM login_throttle WHERE email=?", (email,)).fetchone()
    finally:
        conn.close()
    lu = (row["locked_until"] if row else None) or 0
    return int(lu - now) if lu and lu > now else 0


def note_login_failure(email: str, path: str | None = None, now: float | None = None) -> int:
    """Record a failed login; lock the identity after LOCKOUT_THRESHOLD in a row.
    Returns seconds of lockout now in effect (0 if not yet locked)."""
    email = (email or "").strip().lower()
    now = now or time.time()
    conn = connect(path)
    try:
        row = conn.execute("SELECT fails, locked_until FROM login_throttle WHERE email=?", (email,)).fetchone()
        fails = ((row["fails"] if row else 0) or 0) + 1
        locked_until = None
        if fails >= LOCKOUT_THRESHOLD:
            locked_until = now + LOCKOUT_SECONDS
            fails = 0  # reset the counter; the lock is the penalty
        conn.execute(
            "INSERT INTO login_throttle(email, fails, locked_until) VALUES(?,?,?) "
            "ON CONFLICT(email) DO UPDATE SET fails=excluded.fails, locked_until=excluded.locked_until",
            (email, fails, locked_until))
        conn.commit()
    finally:
        conn.close()
    return LOCKOUT_SECONDS if locked_until else 0


def clear_login_throttle(email: str, path: str | None = None) -> None:
    """Reset failure tracking on a successful login."""
    email = (email or "").strip().lower()
    conn = connect(path)
    try:
        conn.execute("DELETE FROM login_throttle WHERE email=?", (email,))
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Two-factor authentication (email/SMS one-time codes)
# --------------------------------------------------------------------------- #

def get_2fa(account_id: int, path: str | None = None, member_id: int = 0) -> dict:
    """2FA state for a principal: the account owner (member_id=0) or an invited member.
    Members are authenticator-only (TOTP), so dest is always None for them."""
    if member_id:
        m = get_member(member_id, path)
        if not m:
            return {"enabled": False, "channel": None, "dest": None}
        return {"enabled": bool(m.get("twofa_enabled")), "channel": m.get("twofa_channel"), "dest": None}
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


def disable_2fa(account_id: int, path: str | None = None, member_id: int = 0) -> None:
    conn = connect(path)
    try:
        if member_id:
            conn.execute("UPDATE members SET twofa_enabled=0, twofa_channel=NULL, totp_secret=NULL"
                         " WHERE id=?", (member_id,))
        else:
            conn.execute("UPDATE accounts SET twofa_enabled=0, twofa_channel=NULL, twofa_dest=NULL,"
                         " totp_secret=NULL WHERE id=?", (account_id,))
            conn.execute("DELETE FROM otp_codes WHERE account_id=?", (account_id,))
        conn.commit()
    finally:
        conn.close()


# --- TOTP authenticator (RFC 6238) — phishing-resistant-grade MFA, no shared OTP --- #

def new_totp_secret() -> str:
    """A fresh base32 TOTP secret to show on enrollment (provisioning URI / QR)."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def totp_code(secret_b32: str, now: float | None = None, step: int = 30, digits: int = 6) -> str:
    counter = int((now or time.time()) // step)
    key = base64.b32decode(secret_b32 + "=" * (-len(secret_b32) % 8))
    mac = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    off = mac[-1] & 0x0F
    val = (struct.unpack(">I", mac[off:off + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(val).zfill(digits)


def set_totp(account_id: int, secret_b32: str, path: str | None = None, member_id: int = 0) -> None:
    """Enable TOTP 2FA for the principal (owner or member), secret encrypted at rest."""
    from . import secret_box
    enc = secret_box.encrypt(secret_b32)
    conn = connect(path)
    try:
        if member_id:
            conn.execute("UPDATE members SET twofa_enabled=1, twofa_channel='totp', totp_secret=?"
                         " WHERE id=?", (enc, member_id))
        else:
            conn.execute("UPDATE accounts SET twofa_enabled=1, twofa_channel='totp', twofa_dest=NULL,"
                         " totp_secret=? WHERE id=?", (enc, account_id))
        conn.commit()
    finally:
        conn.close()


def verify_totp(account_id: int, code: str, path: str | None = None,
                now: float | None = None, window: int = 1, member_id: int = 0) -> bool:
    """Verify a TOTP code for the principal (owner or member); ±1 step for clock drift."""
    from . import secret_box
    if member_id:
        principal = get_member(member_id, path)
    else:
        principal = get_account(account_id, path)
    enc = principal.get("totp_secret") if principal else None
    if not enc:
        return False
    secret = secret_box.decrypt(enc)
    if not secret:
        return False
    code = (code or "").strip().replace(" ", "")
    if not code.isdigit():
        return False
    base = now or time.time()
    for drift in range(-window, window + 1):
        if hmac.compare_digest(totp_code(secret, base + drift * 30), code):
            return True
    return False


# --- WebAuthn / passkeys (FIDO2) — phishing-resistant MFA ------------------- #

def add_webauthn_credential(account_id: int, member_id: int, credential_id: str, public_key: str,
                            sign_count: int = 0, label: str | None = None,
                            path: str | None = None, now: float | None = None) -> int:
    conn = connect(path)
    try:
        cur = conn.execute(
            "INSERT INTO webauthn_credentials(account_id, member_id, credential_id, public_key,"
            " sign_count, label, created_at) VALUES(?,?,?,?,?,?,?)",
            (account_id, int(member_id or 0), credential_id, public_key, int(sign_count),
             (label or "Passkey")[:80], now or time.time()))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_webauthn_credentials(account_id: int, member_id: int = 0,
                              path: str | None = None) -> list[dict]:
    conn = connect(path)
    try:
        rows = conn.execute(
            "SELECT id, credential_id, label, created_at, last_used_at FROM webauthn_credentials"
            " WHERE account_id=? AND member_id=? ORDER BY created_at",
            (account_id, int(member_id or 0))).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def webauthn_credential_ids(account_id: int, member_id: int = 0,
                            path: str | None = None) -> list[str]:
    return [c["credential_id"] for c in list_webauthn_credentials(account_id, member_id, path)]


def get_webauthn_credential(credential_id: str, path: str | None = None) -> dict | None:
    """Look up a stored credential by its (base64url) credential id — used at login to
    resolve which principal + public key is asserting."""
    conn = connect(path)
    try:
        row = conn.execute("SELECT * FROM webauthn_credentials WHERE credential_id=?",
                           (credential_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_webauthn_sign_count(cred_db_id: int, new_count: int, path: str | None = None,
                               now: float | None = None) -> None:
    conn = connect(path)
    try:
        conn.execute("UPDATE webauthn_credentials SET sign_count=?, last_used_at=? WHERE id=?",
                     (int(new_count), now or time.time(), cred_db_id))
        conn.commit()
    finally:
        conn.close()


def delete_webauthn_credential(cred_db_id: int, account_id: int, member_id: int = 0,
                               path: str | None = None) -> bool:
    conn = connect(path)
    try:
        cur = conn.execute("DELETE FROM webauthn_credentials WHERE id=? AND account_id=? AND member_id=?",
                           (cred_db_id, account_id, int(member_id or 0)))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def principal_has_mfa(account_id: int, member_id: int = 0, path: str | None = None) -> bool:
    """True if the principal (owner or member) has ANY second factor enrolled — a TOTP/
    email channel OR at least one passkey. This is the canonical 'MFA satisfied' check
    used by the admin require_mfa gate and the login second-factor decision."""
    if get_2fa(account_id, path, member_id=member_id)["enabled"]:
        return True
    conn = connect(path)
    try:
        n = conn.execute("SELECT COUNT(*) c FROM webauthn_credentials WHERE account_id=? AND member_id=?",
                         (account_id, int(member_id or 0))).fetchone()["c"]
        return n > 0
    finally:
        conn.close()


# --- Account security policy (admin-enforced MFA, session timeouts, residency) --- #

def get_security_policy(account_id: int, path: str | None = None) -> dict:
    s = get_settings(account_id, path)
    return {
        "require_mfa": bool(s.get("require_mfa")),
        "session_idle_min": int(s.get("session_idle_min") or 0),
        "session_max_hours": int(s.get("session_max_hours") or 0),
        "security_webhook": s.get("security_webhook") or "",
        "data_region": s.get("data_region") or "",
    }


def update_security_policy(account_id: int, *, require_mfa=None, session_idle_min=None,
                           session_max_hours=None, security_webhook=None, data_region=None,
                           path: str | None = None) -> None:
    get_settings(account_id, path)  # ensure a row exists
    sets, vals = [], []
    if require_mfa is not None:
        sets.append("require_mfa=?"); vals.append(1 if require_mfa else 0)
    if session_idle_min is not None:
        sets.append("session_idle_min=?"); vals.append(max(0, int(session_idle_min)))
    if session_max_hours is not None:
        sets.append("session_max_hours=?"); vals.append(max(0, int(session_max_hours)))
    if security_webhook is not None:
        sets.append("security_webhook=?"); vals.append((security_webhook or "").strip()[:300] or None)
    if data_region is not None:
        sets.append("data_region=?"); vals.append((data_region or "").strip()[:80] or None)
    if not sets:
        return
    conn = connect(path)
    try:
        conn.execute(f"UPDATE settings SET {', '.join(sets)} WHERE account_id=?", (*vals, account_id))
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


def make_pending_2fa(account_id: int, path: str | None = None, member_id: int = 0) -> str:
    """Short-lived signed marker carried between the password step and the OTP step.
    Carries the member_id so an invited teammate's 2FA challenge resolves to them."""
    payload = f"p2fa:{account_id}:{int(member_id or 0)}:{int(time.time())}"
    sig = hmac.new(_secret(path), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def read_pending_2fa(token: str, path: str | None = None, max_age: int = 600) -> tuple[int, int] | None:
    """Return (account_id, member_id) or None. member_id is 0 for an account owner."""
    try:
        marker, aid, mid, issued, sig = token.split(":")
    except (ValueError, AttributeError):
        return None
    if marker != "p2fa":
        return None
    payload = f"{marker}:{aid}:{mid}:{issued}"
    good = hmac.new(_secret(path), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(good, sig) or time.time() - int(issued) > max_age:
        return None
    return int(aid), int(mid)


def make_challenge_token(challenge_b64: str, path: str | None = None) -> str:
    """Sign a WebAuthn challenge for round-tripping via a short-lived cookie (the
    challenge is base64url, so it has no ':' to collide with the delimiter)."""
    payload = f"wac:{challenge_b64}:{int(time.time())}"
    sig = hmac.new(_secret(path), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def read_challenge_token(token: str, path: str | None = None, max_age: int = 300) -> str | None:
    try:
        marker, ch, issued, sig = token.split(":")
    except (ValueError, AttributeError):
        return None
    if marker != "wac":
        return None
    payload = f"{marker}:{ch}:{issued}"
    good = hmac.new(_secret(path), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(good, sig) or time.time() - int(issued) > max_age:
        return None
    return ch


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
        # tables keyed directly by account_id (incl. all ingested Outlay data, audit
        # log, personas, OTP codes, and feedback — full erasure for DPA/right-to-be-forgotten)
        for tbl in ("api_keys", "request_logs", "proposals", "webhooks", "webhook_deliveries",
                    "budget_alerts", "resets", "members", "sso_configs", "settings", "plans",
                    "personas", "audit_log", "otp_codes", "webauthn_credentials",
                    "outlay_reports", "outlay_history", "outlay_program_history",
                    "outlay_connections", "outlay_budgets",
                    "outlay_programs", "outlay_program_enforcement",
                    "deployments"):
            conn.execute(f"DELETE FROM {tbl} WHERE account_id=?", (account_id,))
        # Feedback is anonymized, not deleted: severing the account link satisfies
        # erasure while preserving the aggregate cancel-reason signal (no PII in it).
        conn.execute("UPDATE feedback SET account_id=NULL WHERE account_id=?", (account_id,))
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
    blob = json.dumps(report)
    conn = connect(path)
    try:
        conn.execute("INSERT OR REPLACE INTO outlay_reports(account_id, ts, report) VALUES(?,?,?)",
                     (account_id, now, blob))
        conn.commit()
    finally:
        conn.close()
    # Watch the JSON-blob scale ceiling: warn (don't truncate) when a report gets large,
    # so the ceiling is visible in logs + /admin/health before it's a real problem.
    n_bytes = len(blob.encode("utf-8"))
    if n_bytes > OUTLAY_REPORT_SOFT_LIMIT_BYTES and not (report or {}).get("_sample"):
        _log.warning("outlay report for account %s is %d bytes (> soft limit %d)",
                     account_id, n_bytes, OUTLAY_REPORT_SOFT_LIMIT_BYTES)
    # Setup is "complete" the moment real data lands — start the trial clock then,
    # not at signup. Sample/demo data doesn't count.
    if not (report or {}).get("_sample"):
        start_trial(account_id, path=path, now=now)


def outlay_report_storage_stats(path: str | None = None) -> dict:
    """Fleet-wide size of the stored report blobs — the JSON-in-SQLite scale ceiling
    made observable. Byte length via CAST(... AS BLOB) so multibyte JSON counts
    correctly. Returns the count, total/largest bytes, the largest account, and whether
    anything is over the soft limit (for the operator health surface)."""
    conn = connect(path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(length(CAST(report AS BLOB))),0) AS total, "
            "COALESCE(MAX(length(CAST(report AS BLOB))),0) AS mx FROM outlay_reports").fetchone()
        top = conn.execute(
            "SELECT account_id, length(CAST(report AS BLOB)) AS b FROM outlay_reports "
            "ORDER BY b DESC LIMIT 1").fetchone()
    finally:
        conn.close()
    max_bytes = int(row["mx"] or 0)
    return {"count": int(row["n"] or 0),
            "total_bytes": int(row["total"] or 0),
            "max_bytes": max_bytes,
            "max_account_id": int(top["account_id"]) if top else None,
            "soft_limit_bytes": OUTLAY_REPORT_SOFT_LIMIT_BYTES,
            "over_soft_limit": max_bytes > OUTLAY_REPORT_SOFT_LIMIT_BYTES}


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
        conn.execute("DELETE FROM outlay_program_history WHERE account_id=?", (account_id,))
        conn.commit()
    finally:
        conn.close()


def delete_outlay_connection(account_id: int, path: str | None = None) -> None:
    """Remove an account's connector config (used to reset demo mode to a clean
    standard-customer state)."""
    conn = connect(path)
    try:
        conn.execute("DELETE FROM outlay_connections WHERE account_id=?", (account_id,))
        conn.commit()
    finally:
        conn.close()


def set_demo_mode(account_id: int, on: bool, path: str | None = None) -> None:
    """Flip the per-account demo flag. Whether an account is *allowed* to do this is
    gated separately (DEMO_ACCOUNT_EMAILS); this just records the current state."""
    conn = connect(path)
    try:
        conn.execute("UPDATE accounts SET demo_mode=? WHERE id=?", (1 if on else 0, account_id))
        conn.commit()
    finally:
        conn.close()


def record_outlay_snapshot(account_id: int, report: dict, path: str | None = None,
                           now: float | None = None) -> None:
    """Append a spend snapshot to history on a genuine data refresh (run / sync) —
    powers the dashboard's trend delta and sparkline. Not called on estimate re-saves."""
    total = (report.get("spend", {}) or {}).get("total_usd", 0.0)
    fc = (report.get("forecast", {}) or {}).get("expected_usd", 0.0)
    # Capture a compact per-category breakdown so we can show real movement
    # (Δ vs the previous refresh) on the Overview, not just a total.
    breakdown = json.dumps({
        "team": {t["team"]: t.get("spent_usd", 0.0)
                 for t in (report.get("team_spend") or []) if t.get("team") != "(unassigned)"},
        "class": {c["task_class"]: c.get("spent_usd", 0.0)
                  for c in (report.get("class_spend") or [])},
    })
    ts = now or time.time()
    # Per-program spend snapshots (the budget-pacing substrate) — computed from the same
    # report. Lazy import avoids a store<->outlay_app cycle at module load.
    prog_spends = {}
    try:
        programs = list_outlay_programs(account_id, path)
        if programs:
            from . import outlay_app
            prog_spends = outlay_app.program_spends(report, programs)
    except Exception:  # noqa: BLE001 — a history write must never break a sync
        prog_spends = {}
    conn = connect(path)
    try:
        conn.execute("INSERT INTO outlay_history(account_id, ts, total_usd, forecast_usd, breakdown)"
                     " VALUES(?,?,?,?,?)", (account_id, ts, total, fc, breakdown))
        for pid, spent in prog_spends.items():
            conn.execute("INSERT INTO outlay_program_history(account_id, program_id, ts, spent_usd)"
                         " VALUES(?,?,?,?)", (account_id, pid, ts, spent))
        # Enforce the account's retention window inline so it holds even without the
        # cron (a pilot that set 90-day retention shouldn't accumulate forever).
        row = conn.execute("SELECT retention_days FROM accounts WHERE id=?", (account_id,)).fetchone()
        rd = (row["retention_days"] if row else 0) or 0
        if rd:
            cutoff = ts - rd * 86400
            conn.execute("DELETE FROM outlay_history WHERE account_id=? AND ts < ?", (account_id, cutoff))
            conn.execute("DELETE FROM outlay_program_history WHERE account_id=? AND ts < ?",
                         (account_id, cutoff))
        conn.commit()
    finally:
        conn.close()


def outlay_history(account_id: int, limit: int = 12, path: str | None = None) -> list[dict]:
    """Recent spend snapshots, oldest→newest (for sparkline + delta-vs-last)."""
    conn = connect(path)
    try:
        rows = conn.execute(
            "SELECT ts, total_usd, forecast_usd, breakdown FROM outlay_history WHERE account_id=?"
            " ORDER BY ts DESC LIMIT ?", (account_id, limit)).fetchall()
    finally:
        conn.close()
    out = []
    for r in reversed(rows):
        d = dict(r)
        try:
            d["breakdown"] = json.loads(d.get("breakdown") or "") or {}
        except (ValueError, TypeError):
            d["breakdown"] = {}
        out.append(d)
    return out


def program_history(account_id: int, program_id: int, limit: int = 60,
                    path: str | None = None) -> list[dict]:
    """A program's spend snapshots, oldest→newest — the pacing substrate (actual-to-date)."""
    conn = connect(path)
    try:
        rows = conn.execute(
            "SELECT ts, spent_usd FROM outlay_program_history WHERE account_id=? AND program_id=?"
            " ORDER BY ts DESC LIMIT ?", (account_id, program_id, limit)).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in reversed(rows)]


def program_histories(account_id: int, program_ids: list[int] | None = None,
                      path: str | None = None) -> dict:
    """{program_id: [{ts, spent_usd}, …ascending]} for all (or the given) programs — one
    query, so the pacing engine can be fed without N round-trips."""
    conn = connect(path)
    try:
        rows = conn.execute(
            "SELECT program_id, ts, spent_usd FROM outlay_program_history WHERE account_id=?"
            " ORDER BY ts ASC", (account_id,)).fetchall()
    finally:
        conn.close()
    out: dict = {}
    want = set(program_ids) if program_ids else None
    for r in rows:
        if want is not None and r["program_id"] not in want:
            continue
        out.setdefault(r["program_id"], []).append({"ts": r["ts"], "spent_usd": r["spent_usd"]})
    return out


RETENTION_CHOICES = (0, 30, 90, 180, 365)  # 0 = keep forever; else purge snapshots older than N days


def set_retention_days(account_id: int, days: int, path: str | None = None) -> None:
    """Set how long spend-history snapshots are kept (0 = forever). Data minimization
    is a standard enterprise procurement / DPA requirement."""
    days = days if days in RETENTION_CHOICES else 0
    conn = connect(path)
    try:
        conn.execute("UPDATE accounts SET retention_days=? WHERE id=?", (days, account_id))
        conn.commit()
    finally:
        conn.close()


def get_retention_days(account_id: int, path: str | None = None) -> int:
    conn = connect(path)
    try:
        row = conn.execute("SELECT retention_days FROM accounts WHERE id=?", (account_id,)).fetchone()
        return (row["retention_days"] if row else 0) or 0
    finally:
        conn.close()


def purge_outlay_history(account_id: int, retention_days: int, path: str | None = None,
                         now: float | None = None) -> int:
    """Delete spend snapshots older than the retention window. No-op when retention
    is 'forever' (0). Returns the number of rows removed."""
    if not retention_days:
        return 0
    cutoff = (now or time.time()) - retention_days * 86400
    conn = connect(path)
    try:
        cur = conn.execute("DELETE FROM outlay_history WHERE account_id=? AND ts < ?",
                           (account_id, cutoff))
        conn.execute("DELETE FROM outlay_program_history WHERE account_id=? AND ts < ?",
                     (account_id, cutoff))
        conn.commit()
        return cur.rowcount or 0
    finally:
        conn.close()


def purge_due_outlay_history(path: str | None = None, now: float | None = None) -> dict:
    """Enforce every account's retention window (cron). Resilient: returns a summary."""
    conn = connect(path)
    try:
        rows = conn.execute(
            "SELECT id, retention_days FROM accounts WHERE retention_days > 0").fetchall()
    finally:
        conn.close()
    accounts, purged = 0, 0
    for r in rows:
        n = purge_outlay_history(r["id"], r["retention_days"], path=path, now=now)
        if n:
            accounts += 1
            purged += n
    return {"accounts": accounts, "rows_purged": purged}


def purge_outlay_data(account_id: int, path: str | None = None) -> None:
    """Right-to-erasure for ingested spend data: wipe the current report and all
    history snapshots. Leaves the connection config so the customer can re-sync."""
    conn = connect(path)
    try:
        conn.execute("DELETE FROM outlay_reports WHERE account_id=?", (account_id,))
        conn.execute("DELETE FROM outlay_history WHERE account_id=?", (account_id,))
        conn.execute("DELETE FROM outlay_program_history WHERE account_id=?", (account_id,))
        conn.commit()
    finally:
        conn.close()


ANOMALY_THRESHOLD_DEFAULT = 3.0


def _upsert_connection_field(account_id: int, field: str, value, path: str | None = None) -> None:
    conn = connect(path)
    try:
        exists = conn.execute("SELECT 1 FROM outlay_connections WHERE account_id=?",
                              (account_id,)).fetchone()
        if exists:
            conn.execute(f"UPDATE outlay_connections SET {field}=? WHERE account_id=?",
                         (value, account_id))
        else:
            conn.execute(f"INSERT INTO outlay_connections(account_id, {field}) VALUES(?,?)",
                         (account_id, value))
        conn.commit()
    finally:
        conn.close()


def get_anomaly_prefs(account_id: int, path: str | None = None) -> tuple[float, set]:
    """(threshold_multiple, muted_ticket_ids). Threshold floors at the default 3x;
    muting hides a known-expensive ticket from the runaway flags and alerts."""
    conn = connect(path)
    try:
        row = conn.execute("SELECT anomaly_threshold, muted_tickets FROM outlay_connections "
                          "WHERE account_id=?", (account_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        return ANOMALY_THRESHOLD_DEFAULT, set()
    thr = row["anomaly_threshold"]
    thr = float(thr) if thr and thr >= ANOMALY_THRESHOLD_DEFAULT else ANOMALY_THRESHOLD_DEFAULT
    try:
        muted = set(json.loads(row["muted_tickets"] or "[]"))
    except (ValueError, TypeError):
        muted = set()
    return thr, muted


def set_slack_webhook(account_id: int, url: str | None, path: str | None = None) -> None:
    url = (url or "").strip() or None
    if url:
        from . import notify
        if not notify.is_safe_url(url):
            raise StoreError("Slack webhook must be a public https URL (not localhost / internal / metadata).")
    from . import secret_box  # a Slack/Teams incoming-webhook URL is a bearer secret — encrypt at rest
    _upsert_connection_field(account_id, "slack_webhook", secret_box.encrypt(url), path)


def get_slack_webhook(account_id: int, path: str | None = None) -> str | None:
    from . import secret_box
    conn = connect(path)
    try:
        row = conn.execute("SELECT slack_webhook FROM outlay_connections WHERE account_id=?",
                          (account_id,)).fetchone()
    finally:
        conn.close()
    return secret_box.decrypt(row["slack_webhook"] if row else None) or None


def set_anomaly_threshold(account_id: int, threshold: float, path: str | None = None) -> None:
    thr = max(ANOMALY_THRESHOLD_DEFAULT, min(50.0, float(threshold)))
    _upsert_connection_field(account_id, "anomaly_threshold", thr, path)


def mute_ticket(account_id: int, ticket_id: str, path: str | None = None) -> None:
    _, muted = get_anomaly_prefs(account_id, path)
    muted.add(str(ticket_id))
    _upsert_connection_field(account_id, "muted_tickets", json.dumps(sorted(muted)), path)


def unmute_ticket(account_id: int, ticket_id: str, path: str | None = None) -> None:
    _, muted = get_anomaly_prefs(account_id, path)
    muted.discard(str(ticket_id))
    _upsert_connection_field(account_id, "muted_tickets", json.dumps(sorted(muted)), path)


def set_digest_weekly(account_id: int, on: bool, path: str | None = None) -> None:
    conn = connect(path)
    try:
        conn.execute("UPDATE accounts SET digest_weekly=? WHERE id=?",
                     (1 if on else 0, account_id))
        conn.commit()
    finally:
        conn.close()


def mark_digest_sent(account_id: int, now: float | None = None, path: str | None = None) -> None:
    conn = connect(path)
    try:
        conn.execute("UPDATE accounts SET digest_last_at=? WHERE id=?",
                     (now or time.time(), account_id))
        conn.commit()
    finally:
        conn.close()


def accounts_due_for_digest(now: float | None = None, every_seconds: int = 7 * 24 * 3600,
                            path: str | None = None) -> list[int]:
    """Active accounts opted into the weekly digest that have a saved spend report
    and whose last send is older than the cadence (or never sent)."""
    now = now or time.time()
    cutoff = now - every_seconds
    conn = connect(path)
    try:
        rows = conn.execute(
            "SELECT a.id FROM accounts a JOIN outlay_reports r ON r.account_id = a.id "
            "WHERE a.status='active' AND a.digest_weekly=1 "
            "AND (a.digest_last_at IS NULL OR a.digest_last_at <= ?)",
            (cutoff,)).fetchall()
    finally:
        conn.close()
    return [r["id"] for r in rows]


def set_close_pack_monthly(account_id: int, on: bool, path: str | None = None) -> None:
    conn = connect(path)
    try:
        conn.execute("UPDATE accounts SET close_pack_monthly=? WHERE id=?",
                     (1 if on else 0, account_id))
        conn.commit()
    finally:
        conn.close()


def mark_close_pack_sent(account_id: int, now: float | None = None, path: str | None = None) -> None:
    conn = connect(path)
    try:
        conn.execute("UPDATE accounts SET close_pack_last_at=? WHERE id=?",
                     (now or time.time(), account_id))
        conn.commit()
    finally:
        conn.close()


def accounts_due_for_close_pack(now: float | None = None, every_seconds: int = 30 * 24 * 3600,
                                path: str | None = None) -> list[int]:
    """Active accounts opted into the monthly close pack that have a saved report and
    whose last send is older than the cadence (or never sent)."""
    now = now or time.time()
    cutoff = now - every_seconds
    conn = connect(path)
    try:
        rows = conn.execute(
            "SELECT a.id FROM accounts a JOIN outlay_reports r ON r.account_id = a.id "
            "WHERE a.status='active' AND a.close_pack_monthly=1 "
            "AND (a.close_pack_last_at IS NULL OR a.close_pack_last_at <= ?)",
            (cutoff,)).fetchall()
    finally:
        conn.close()
    return [r["id"] for r in rows]


def get_alerted_anomalies(account_id: int, path: str | None = None) -> set:
    """Ticket ids we've already alerted on, so a standing runaway ticket isn't
    re-emailed every sync (a ticket that drops off and re-spikes will re-alert)."""
    conn = connect(path)
    try:
        row = conn.execute("SELECT alerted_anomalies FROM outlay_connections WHERE account_id=?",
                          (account_id,)).fetchone()
    finally:
        conn.close()
    if not row or not row["alerted_anomalies"]:
        return set()
    try:
        return set(json.loads(row["alerted_anomalies"]))
    except (ValueError, TypeError):
        return set()


def set_alerted_anomalies(account_id: int, ticket_ids, path: str | None = None) -> None:
    payload = json.dumps(sorted(str(t) for t in ticket_ids))
    conn = connect(path)
    try:
        exists = conn.execute("SELECT 1 FROM outlay_connections WHERE account_id=?",
                              (account_id,)).fetchone()
        if exists:
            conn.execute("UPDATE outlay_connections SET alerted_anomalies=? WHERE account_id=?",
                         (payload, account_id))
        else:
            conn.execute("INSERT INTO outlay_connections(account_id, alerted_anomalies) VALUES(?,?)",
                         (account_id, payload))
        conn.commit()
    finally:
        conn.close()


def set_outlay_identity_map(account_id: int, identity_map: str | None,
                            path: str | None = None) -> None:
    """Persist the per-account identity→team map (JSON text). Upserts the
    connection row so it works even for paste-only customers with no live sync."""
    conn = connect(path)
    try:
        exists = conn.execute("SELECT 1 FROM outlay_connections WHERE account_id=?",
                              (account_id,)).fetchone()
        if exists:
            conn.execute("UPDATE outlay_connections SET identity_map=? WHERE account_id=?",
                         (identity_map, account_id))
        else:
            conn.execute("INSERT INTO outlay_connections(account_id, identity_map) VALUES(?,?)",
                         (account_id, identity_map))
        conn.commit()
    finally:
        conn.close()


def get_outlay_identity_map(account_id: int, path: str | None = None) -> str | None:
    conn = connect(path)
    try:
        row = conn.execute("SELECT identity_map FROM outlay_connections WHERE account_id=?",
                          (account_id,)).fetchone()
    finally:
        conn.close()
    return (row["identity_map"] if row else None) or None


_IDENTITY_DIR_COLS = ("identity_names", "identity_titles")


def _merge_identity_dir(account_id: int, column: str, mapping: dict, path: str | None = None) -> None:
    """Merge an {identifier: value} JSON directory (names or job titles) onto the
    connection row, lower-casing identifiers and dropping blanks."""
    assert column in _IDENTITY_DIR_COLS
    import json as _json
    cur = _get_identity_dir(account_id, column, path)
    cur.update({k.strip().lower(): v.strip() for k, v in (mapping or {}).items()
                if k and k.strip() and v and v.strip()})
    blob = _json.dumps(cur) if cur else None
    conn = connect(path)
    try:
        exists = conn.execute("SELECT 1 FROM outlay_connections WHERE account_id=?",
                              (account_id,)).fetchone()
        if exists:
            conn.execute(f"UPDATE outlay_connections SET {column}=? WHERE account_id=?",
                         (blob, account_id))
        else:
            conn.execute(f"INSERT INTO outlay_connections(account_id, {column}) VALUES(?,?)",
                         (account_id, blob))
        conn.commit()
    finally:
        conn.close()


def _get_identity_dir(account_id: int, column: str, path: str | None = None) -> dict:
    assert column in _IDENTITY_DIR_COLS
    import json as _json
    conn = connect(path)
    try:
        row = conn.execute(f"SELECT {column} FROM outlay_connections WHERE account_id=?",
                          (account_id,)).fetchone()
    finally:
        conn.close()
    if not row or not row[column]:
        return {}
    try:
        return _json.loads(row[column]) or {}
    except Exception:  # noqa: BLE001
        return {}


def set_outlay_identity_names(account_id: int, names: dict, path: str | None = None) -> None:
    """Merge {identifier: display name} so spend can be shown by person name."""
    _merge_identity_dir(account_id, "identity_names", names, path)


def get_outlay_identity_names(account_id: int, path: str | None = None) -> dict:
    return _get_identity_dir(account_id, "identity_names", path)


def set_outlay_identity_titles(account_id: int, titles: dict, path: str | None = None) -> None:
    """Merge {identifier: job title} — the engineering 'direct reports' detail."""
    _merge_identity_dir(account_id, "identity_titles", titles, path)


def get_outlay_identity_titles(account_id: int, path: str | None = None) -> dict:
    return _get_identity_dir(account_id, "identity_titles", path)


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
    d["slack_webhook"] = secret_box.decrypt(d.get("slack_webhook"))  # bearer secret, encrypted at rest
    return d


def mark_outlay_synced(account_id: int, path: str | None = None,
                       now: float | None = None) -> None:
    """Record a successful sync: stamp synced_at + last_attempt_at, clear any error
    and the consecutive-failure / alert state (the pipeline is healthy again)."""
    ts = now or time.time()
    conn = connect(path)
    try:
        conn.execute("UPDATE outlay_connections SET synced_at=?, last_attempt_at=?,"
                     " last_sync_error=NULL, sync_fail_count=0, sync_alerted_at=NULL"
                     " WHERE account_id=?", (ts, ts, account_id))
        conn.commit()
    finally:
        conn.close()


def mark_outlay_sync_error(account_id: int, message: str, path: str | None = None,
                           now: float | None = None) -> int:
    """Record a failed sync attempt so the UI can surface why refreshing stopped.
    Increments the consecutive-failure counter and returns its new value so callers
    can alert once a failure persists (vs. a single transient blip)."""
    conn = connect(path)
    try:
        conn.execute("UPDATE outlay_connections SET last_attempt_at=?, last_sync_error=?,"
                     " sync_fail_count=COALESCE(sync_fail_count,0)+1 WHERE account_id=?",
                     (now or time.time(), (message or "")[:300], account_id))
        conn.commit()
        row = conn.execute("SELECT sync_fail_count FROM outlay_connections WHERE account_id=?",
                           (account_id,)).fetchone()
        return row["sync_fail_count"] if row else 0
    finally:
        conn.close()


def mark_outlay_sync_alerted(account_id: int, path: str | None = None,
                             now: float | None = None) -> None:
    """Stamp when we last alerted about a stale/failing sync, so we don't re-spam
    the owner every cron tick while the connection stays broken."""
    conn = connect(path)
    try:
        conn.execute("UPDATE outlay_connections SET sync_alerted_at=? WHERE account_id=?",
                     (now or time.time(), account_id))
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


def update_outlay_budget(account_id: int, budget_id: int, *, limit_usd: float | None = None,
                         period_days: int | None = None, path: str | None = None) -> None:
    """Adjust a budget's limit and/or period in place — the 'address it' action behind
    an over/at-risk budget alert. Only the fields supplied are changed; scoped to the
    account so one customer can't touch another's budget."""
    sets, params = [], []
    if limit_usd is not None:
        sets.append("limit_usd=?")
        params.append(float(limit_usd))
    if period_days is not None:
        sets.append("period_days=?")
        params.append(int(period_days))
    if not sets:
        return
    params += [int(budget_id), account_id]
    conn = connect(path)
    try:
        conn.execute(f"UPDATE outlay_budgets SET {', '.join(sets)} WHERE id=? AND account_id=?", params)
        conn.commit()
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


PROGRAM_ENFORCE_MODES = ("alert", "hard")
PROGRAM_ACTIONS = ("block", "downgrade")


def add_outlay_program(account_id: int, name: str, members: list, limit_usd: float,
                       period_days: int = 90, enforce_mode: str = "alert",
                       action: str = "block", floor_model: str | None = None,
                       start_ts: float | None = None, end_ts: float | None = None,
                       path: str | None = None) -> int:
    """Create a program budget (a named budget spanning several teams/projects/work
    types). `members` is a list of {scope_type, scope_id}. A program has a timeline:
    `start_ts` defaults to now and `end_ts` to start + period_days; when both dates
    are given, period_days is derived from them so the pace projection stays in sync.
    Returns the new id."""
    enforce_mode = enforce_mode if enforce_mode in PROGRAM_ENFORCE_MODES else "alert"
    action = action if action in PROGRAM_ACTIONS else "block"
    clean = [{"scope_type": m.get("scope_type"), "scope_id": (m.get("scope_id") or "").strip() or None}
             for m in (members or []) if m.get("scope_type")]
    start_ts = float(start_ts) if start_ts else time.time()
    if end_ts:
        end_ts = float(end_ts)
        period_days = max(1, round((end_ts - start_ts) / 86400))
    else:
        end_ts = start_ts + int(period_days) * 86400
    conn = connect(path)
    try:
        cur = conn.execute(
            "INSERT INTO outlay_programs(account_id, name, members, limit_usd, period_days,"
            " enforce_mode, action, floor_model, start_ts, end_ts) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (account_id, (name or "Program").strip()[:80], json.dumps(clean), float(limit_usd),
             int(period_days), enforce_mode, action, (floor_model or "").strip() or None,
             start_ts, end_ts))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_outlay_programs(account_id: int, path: str | None = None) -> list[dict]:
    conn = connect(path)
    try:
        rows = conn.execute("SELECT * FROM outlay_programs WHERE account_id=? ORDER BY id",
                            (account_id,)).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["members"] = json.loads(d.get("members") or "[]") or []
        except (ValueError, TypeError):
            d["members"] = []
        out.append(d)
    return out


def update_outlay_program(account_id: int, program_id: int, *, limit_usd=None,
                          period_days=None, enforce_mode=None, action=None,
                          floor_model=None, path: str | None = None) -> bool:
    """Patch a program in place (reallocate budget, flip enforcement, …). Only the
    provided fields change. Returns True if a row was updated. Account-scoped."""
    sets, vals = [], []
    if limit_usd is not None:
        sets.append("limit_usd=?"); vals.append(float(limit_usd))
    if period_days is not None:
        sets.append("period_days=?"); vals.append(int(period_days))
    if enforce_mode is not None and enforce_mode in PROGRAM_ENFORCE_MODES:
        sets.append("enforce_mode=?"); vals.append(enforce_mode)
    if action is not None and action in PROGRAM_ACTIONS:
        sets.append("action=?"); vals.append(action)
    if floor_model is not None:
        sets.append("floor_model=?"); vals.append((floor_model or "").strip() or None)
    if not sets:
        return False
    vals += [int(program_id), account_id]
    conn = connect(path)
    try:
        cur = conn.execute(f"UPDATE outlay_programs SET {', '.join(sets)} WHERE id=? AND account_id=?", vals)
        conn.commit()
        return (cur.rowcount or 0) > 0
    finally:
        conn.close()


def delete_outlay_program(account_id: int, program_id: int, path: str | None = None) -> None:
    conn = connect(path)
    try:
        conn.execute("DELETE FROM outlay_programs WHERE id=? AND account_id=?",
                     (int(program_id), account_id))
        conn.execute("DELETE FROM outlay_program_enforcement WHERE program_id=? AND account_id=?",
                     (int(program_id), account_id))
        conn.commit()
    finally:
        conn.close()


COMMITMENT_KINDS = ("committed_spend", "provisioned")


def add_commitment(account_id: int, amount_usd: float, start_ts: float, end_ts: float, *,
                   provider: str = "", kind: str = "committed_spend",
                   used_to_date_usd: float = 0.0, now: float | None = None,
                   path: str | None = None) -> int:
    """Record an active vendor commitment (metadata only — the numbers, not the
    contract). Powers commitment pacing (forfeit/overage projection). Returns id."""
    kind = kind if kind in COMMITMENT_KINDS else "committed_spend"
    start_ts, end_ts = float(start_ts), float(end_ts)
    if end_ts <= start_ts:
        end_ts = start_ts + 86400  # guard: a term must be at least a day
    conn = connect(path)
    try:
        cur = conn.execute(
            "INSERT INTO outlay_commitment(account_id, provider, kind, amount_usd,"
            " used_to_date_usd, start_ts, end_ts, created_at) VALUES(?,?,?,?,?,?,?,?)",
            (account_id, (provider or "").strip()[:40], kind, max(0.0, float(amount_usd)),
             max(0.0, float(used_to_date_usd)), start_ts, end_ts, now or time.time()))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_commitments(account_id: int, path: str | None = None) -> list[dict]:
    conn = connect(path)
    try:
        rows = conn.execute("SELECT * FROM outlay_commitment WHERE account_id=? ORDER BY id",
                            (account_id,)).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def delete_commitment(account_id: int, commitment_id: int, path: str | None = None) -> None:
    conn = connect(path)
    try:
        conn.execute("DELETE FROM outlay_commitment WHERE id=? AND account_id=?",
                     (int(commitment_id), account_id))
        conn.commit()
    finally:
        conn.close()


def set_work_key_class(account_id: int, api_key_id: str, classification: str,
                       path: str | None = None) -> None:
    """Tag an API key as 'work' or 'non_work' (or clear with '' / None). Drives the
    work-vs-non-work split — metadata only, no prompt content involved."""
    api_key_id = (api_key_id or "").strip()
    if not api_key_id:
        return
    conn = connect(path)
    try:
        if classification in ("work", "non_work"):
            conn.execute(
                "INSERT INTO outlay_work_key(account_id, api_key_id, classification) VALUES(?,?,?)"
                " ON CONFLICT(account_id, api_key_id) DO UPDATE SET classification=excluded.classification",
                (account_id, api_key_id, classification))
        else:
            conn.execute("DELETE FROM outlay_work_key WHERE account_id=? AND api_key_id=?",
                         (account_id, api_key_id))
        conn.commit()
    finally:
        conn.close()


def get_work_key_classes(account_id: int, path: str | None = None) -> dict:
    """{api_key_id: 'work'|'non_work'} for the account."""
    conn = connect(path)
    try:
        rows = conn.execute("SELECT api_key_id, classification FROM outlay_work_key WHERE account_id=?",
                            (account_id,)).fetchall()
    finally:
        conn.close()
    return {r["api_key_id"]: r["classification"] for r in rows}


def set_work_enforce(account_id: int, team_id: str, *, block_non_work: bool,
                     block_unknown: bool, path: str | None = None) -> None:
    """Per-team opt-in enforcement: what this team's gateway should block. Cleared
    (row removed) when both are off."""
    team_id = (team_id or "").strip()
    if not team_id:
        return
    conn = connect(path)
    try:
        if block_non_work or block_unknown:
            conn.execute(
                "INSERT INTO outlay_work_enforce(account_id, team_id, block_non_work, block_unknown)"
                " VALUES(?,?,?,?) ON CONFLICT(account_id, team_id) DO UPDATE SET"
                " block_non_work=excluded.block_non_work, block_unknown=excluded.block_unknown",
                (account_id, team_id, int(bool(block_non_work)), int(bool(block_unknown))))
        else:
            conn.execute("DELETE FROM outlay_work_enforce WHERE account_id=? AND team_id=?",
                         (account_id, team_id))
        conn.commit()
    finally:
        conn.close()


def get_work_enforce(account_id: int, path: str | None = None) -> dict:
    """{team_id: {'block_non_work': bool, 'block_unknown': bool}} for the account."""
    conn = connect(path)
    try:
        rows = conn.execute("SELECT team_id, block_non_work, block_unknown FROM outlay_work_enforce"
                            " WHERE account_id=?", (account_id,)).fetchall()
    finally:
        conn.close()
    return {r["team_id"]: {"block_non_work": bool(r["block_non_work"]),
                           "block_unknown": bool(r["block_unknown"])} for r in rows}


def set_outlay_program_status(program_id: int, status: str, path: str | None = None) -> None:
    conn = connect(path)
    try:
        conn.execute("UPDATE outlay_programs SET last_status=? WHERE id=?", (status, int(program_id)))
        conn.commit()
    finally:
        conn.close()


def record_program_enforcement(account_id: int, counts: dict, now: float | None = None,
                               path: str | None = None) -> int:
    """Add the gateway's enforcement tallies to each program (so business sees the cap
    actually biting). `counts` is {program_id: n}. Returns the number of programs hit."""
    now = now or time.time()
    day = datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%d")
    conn = connect(path)
    hit = 0
    try:
        for pid, n in (counts or {}).items():
            try:
                pid, n = int(pid), int(n)
            except (TypeError, ValueError):
                continue
            if n <= 0:
                continue
            cur = conn.execute(
                "UPDATE outlay_programs SET enforced_count=COALESCE(enforced_count,0)+?,"
                " last_enforced_at=? WHERE id=? AND account_id=?", (n, now, pid, account_id))
            if cur.rowcount:  # only bucket for programs that actually belong to this account
                hit += cur.rowcount
                conn.execute(
                    "INSERT INTO outlay_program_enforcement(program_id, account_id, day, count)"
                    " VALUES(?,?,?,?) ON CONFLICT(program_id, day) DO UPDATE SET count=count+excluded.count",
                    (pid, account_id, day, n))
        conn.commit()
    finally:
        conn.close()
    return hit


def program_enforcement_history(account_id: int, program_id: int, days: int = 14,
                                now: float | None = None, path: str | None = None) -> list[dict]:
    """Per-day enforcement counts for one program over the last `days`, oldest→newest
    and zero-filled (so a sparkline shows gaps as flat, not missing)."""
    from datetime import timedelta
    now = now or time.time()
    end = datetime.fromtimestamp(now, timezone.utc).date()
    start = end - timedelta(days=days - 1)
    conn = connect(path)
    try:
        rows = conn.execute(
            "SELECT day, count FROM outlay_program_enforcement WHERE program_id=? AND account_id=?"
            " AND day >= ?", (int(program_id), account_id, start.strftime("%Y-%m-%d"))).fetchall()
    finally:
        conn.close()
    by_day = {r["day"]: r["count"] for r in rows}
    out = []
    for i in range(days):
        d = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        out.append({"day": d, "count": by_day.get(d, 0)})
    return out


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
    problem = password_problem(new_password)
    if problem:
        raise StoreError(problem)
    pw_hash, salt = hash_password(new_password)
    conn = connect(path)
    try:
        conn.execute("UPDATE members SET pw_hash=?, pw_salt=?, status='active', session_epoch=session_epoch+1 WHERE id=?",
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
    label = (label or "deployment").strip()[:120]
    conn = connect(path)
    try:
        conn.execute("INSERT INTO deployments(deployment_id, account_id, label, created_at)"
                     " VALUES(?,?,?,?)", (dep, account_id, label, now))
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
                     ((label or "").strip()[:120], deployment_id, account_id))
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


def audit_events(account_id: int, since_id: int = 0, limit: int = 1000,
                 path: str | None = None) -> list[dict]:
    """Audit rows in *ascending* id order for SIEM ingestion. `since_id` is a cursor:
    pass the last id you saw to fetch only newer events (incremental, gap-free)."""
    limit = max(1, min(int(limit or 1000), 5000))
    conn = connect(path)
    try:
        rows = conn.execute(
            "SELECT id, ts, actor, action, detail FROM audit_log"
            " WHERE account_id=? AND id > ? ORDER BY id ASC LIMIT ?",
            (account_id, int(since_id or 0), limit)).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


PERSONAS = ("business", "eng")


def get_persona(account_id: int, member_id: int = 0, path: str | None = None) -> str:
    """The chosen experience ('business'|'eng'|'') for this person (member_id 0 = owner)."""
    conn = connect(path)
    try:
        row = conn.execute("SELECT persona FROM personas WHERE account_id=? AND member_id=?",
                           (account_id, member_id)).fetchone()
        return (row["persona"] if row else "") or ""
    finally:
        conn.close()


def set_persona(account_id: int, persona: str, member_id: int = 0, path: str | None = None) -> None:
    """Set this person's experience (per member — business and eng are separate logins)."""
    if persona == "finance":           # legacy alias for the reframed 'business' persona
        persona = "business"
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


# --- Saved dashboard views (per-person Home lens personalization) ------------- #

def list_dashboard_views(account_id: int, member_id: int = 0, path: str | None = None) -> list[dict]:
    conn = connect(path)
    try:
        rows = conn.execute(
            "SELECT * FROM dashboard_views WHERE account_id=? AND member_id=? ORDER BY id",
            (account_id, member_id)).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["lens"] = json.loads(d.get("lens") or "{}") or {}
        except (ValueError, TypeError):
            d["lens"] = {}
        out.append(d)
    return out


def add_dashboard_view(account_id: int, name: str, lens: dict, member_id: int = 0,
                       make_default: bool = False, path: str | None = None) -> int:
    """Save a named Home lens for this person. Optionally make it their default."""
    conn = connect(path)
    try:
        cur = conn.execute(
            "INSERT INTO dashboard_views(account_id, member_id, name, lens) VALUES(?,?,?,?)",
            (account_id, member_id, (name or "View").strip()[:60], json.dumps(lens or {})))
        vid = cur.lastrowid
        if make_default:
            conn.execute("UPDATE dashboard_views SET is_default=0 WHERE account_id=? AND member_id=?",
                         (account_id, member_id))
            conn.execute("UPDATE dashboard_views SET is_default=1 WHERE id=?", (vid,))
        conn.commit()
        return vid
    finally:
        conn.close()


def set_default_dashboard_view(account_id: int, view_id: int, member_id: int = 0,
                               path: str | None = None) -> None:
    """Mark one saved view as this person's default (0 clears the default → opinionated default)."""
    conn = connect(path)
    try:
        conn.execute("UPDATE dashboard_views SET is_default=0 WHERE account_id=? AND member_id=?",
                     (account_id, member_id))
        if view_id:
            conn.execute("UPDATE dashboard_views SET is_default=1 WHERE id=? AND account_id=? AND member_id=?",
                         (view_id, account_id, member_id))
        conn.commit()
    finally:
        conn.close()


def get_default_dashboard_view(account_id: int, member_id: int = 0, path: str | None = None) -> dict | None:
    for v in list_dashboard_views(account_id, member_id, path=path):
        if v.get("is_default"):
            return v
    return None


def delete_dashboard_view(account_id: int, view_id: int, member_id: int = 0,
                          path: str | None = None) -> None:
    conn = connect(path)
    try:
        conn.execute("DELETE FROM dashboard_views WHERE id=? AND account_id=? AND member_id=?",
                     (view_id, account_id, member_id))
        conn.commit()
    finally:
        conn.close()


def get_dashboard_layout(account_id: int, member_id: int = 0, path: str | None = None) -> dict:
    """This person's Home card layout — {order:[keys], hidden:[keys]}. Empty = the
    opinionated default order with nothing hidden."""
    conn = connect(path)
    try:
        row = conn.execute("SELECT layout FROM dashboard_prefs WHERE account_id=? AND member_id=?",
                           (account_id, member_id)).fetchone()
    finally:
        conn.close()
    if not row:
        return {}
    try:
        return json.loads(row["layout"] or "{}") or {}
    except (ValueError, TypeError):
        return {}


def set_dashboard_layout(account_id: int, member_id: int, layout: dict, path: str | None = None) -> None:
    conn = connect(path)
    try:
        conn.execute(
            "INSERT INTO dashboard_prefs(account_id, member_id, layout) VALUES(?,?,?) "
            "ON CONFLICT(account_id, member_id) DO UPDATE SET layout=excluded.layout",
            (account_id, member_id, json.dumps(layout or {})))
        conn.commit()
    finally:
        conn.close()


def clear_persona(account_id: int, member_id: int = 0, path: str | None = None) -> None:
    """Remove this person's persona so they're treated as first-run again (the role
    gate fires). Used to re-test the new-user onboarding from an internal account."""
    conn = connect(path)
    try:
        conn.execute("DELETE FROM personas WHERE account_id=? AND member_id=?",
                     (account_id, member_id))
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
                   path: str | None = None, now: float | None = None,
                   expires_in_days: int | None = None) -> dict:
    """Mint a key. Returns the FULL key once (never recoverable) plus its row.
    Only the sha256 hash + a display prefix are stored. `expires_in_days` sets an
    optional expiry (None = never) — enterprises often require rotating keys."""
    if not account_for_deployment(deployment_id, path):
        raise StoreError("unknown deployment")
    now = now or time.time()
    expires_at = (now + expires_in_days * 86400) if expires_in_days else None
    full = KEY_PREFIX + secrets.token_urlsafe(24)
    prefix = full[:16]
    key_hash = hashlib.sha256(full.encode()).hexdigest()
    name = (name or "key").strip()[:120]
    conn = connect(path)
    try:
        conn.execute("INSERT INTO api_keys(account_id, deployment_id, name, prefix, key_hash,"
                     " created_at, expires_at) VALUES(?,?,?,?,?,?,?)",
                     (account_id, deployment_id, name, prefix, key_hash, now, expires_at))
        conn.commit()
    finally:
        conn.close()
    return {"full_key": full, "prefix": prefix, "name": name, "expires_at": expires_at}


def list_api_keys(account_id: int, path: str | None = None) -> list[dict]:
    conn = connect(path)
    try:
        rows = conn.execute(
            "SELECT id, deployment_id, name, prefix, created_at, last_used_at, revoked_at, expires_at"
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
    (unknown/revoked/expired). Updates last_used_at on success."""
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
        if row["expires_at"] and row["expires_at"] <= now:
            return None  # expired keys are rejected like revoked ones
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


def start_trial(account_id: int, path: str | None = None, now: float | None = None) -> None:
    """Begin the trial countdown — called once, at setup completion (first real
    report). Idempotent and a no-op if the trial already started or the account has
    converted to paid, so it never resets or restarts a running clock."""
    now = now or time.time()
    plan = get_plan(account_id, path)
    if not plan or plan.get("plan") != "trial" or plan.get("trial_started_at"):
        return
    conn = connect(path)
    try:
        conn.execute("UPDATE plans SET trial_started_at=? WHERE account_id=? AND trial_started_at=0",
                     (now, account_id))
        conn.commit()
    finally:
        conn.close()


def trial_status(account_id: int, path: str | None = None, now: float | None = None) -> dict:
    now = now or time.time()
    plan = get_plan(account_id, path)
    if not plan:
        return {"active": False, "days_left": 0, "ends_at": 0}
    if not plan["trial_started_at"]:
        # Not started yet — entitled, full clock, counting down hasn't begun.
        return {"active": True, "days_left": TRIAL_DAYS, "ends_at": 0,
                "started_at": 0, "not_started": True}
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
    problem = password_problem(new_password)
    if problem:
        raise StoreError(problem)
    pw_hash, salt = hash_password(new_password)
    conn = connect(path)
    try:
        # Bump the session epoch so a password change logs out all existing sessions.
        conn.execute("UPDATE accounts SET pw_hash=?, pw_salt=?, session_epoch=session_epoch+1 WHERE id=?",
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
    try:
        if row.get("member_id"):
            set_member_password(row["member_id"], new_password, path)
        else:
            set_password(row["account_id"], new_password, path)
    except StoreError:
        # Password failed the policy (too short / breached). Re-open the token so the
        # user can try again, and report failure for the route to surface.
        c2 = connect(path)
        try:
            c2.execute("UPDATE resets SET used=0 WHERE token=?", (token,))
            c2.commit()
        finally:
            c2.close()
        raise
    record_audit(row["account_id"], "password.reset",
                 detail="member" if row.get("member_id") else "owner", path=path)
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
    if len(url) > 2000:   # reject rather than silently truncate a URL into something broken
        raise StoreError("webhook url is too long")
    from . import notify
    if not notify.is_safe_url(url):
        raise StoreError("webhook url must be a public address (not localhost / internal / metadata)")
    now = now or time.time()
    secret = "whsec_" + secrets.token_urlsafe(24)
    from . import secret_box  # HMAC signing secret — encrypt at rest (returned once in cleartext)
    conn = connect(path)
    try:
        cur = conn.execute("INSERT INTO webhooks(account_id, url, secret, events, active, created_at)"
                           " VALUES(?,?,?,?,1,?)", (account_id, url.strip(), secret_box.encrypt(secret),
                                                    (events or "all").strip(), now))
        wid = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return {"id": wid, "secret": secret, "url": url}


def list_webhooks(account_id: int, path: str | None = None) -> list[dict]:
    from . import secret_box
    conn = connect(path)
    try:
        rows = conn.execute("SELECT * FROM webhooks WHERE account_id=? ORDER BY created_at DESC",
                            (account_id,)).fetchall()
        out = []
        for r in rows:  # decrypt the signing secret for delivery/redelivery + display
            d = dict(r)
            d["secret"] = secret_box.decrypt(d.get("secret"))
            out.append(d)
        return out
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


# --- Security / incident webhook (the SOC/SIEM alert hook) ------------------ #
# Distinct from the product `webhooks` table above (which carries spend/budget
# events): this fires on AUTHENTICATION / SECURITY events to the customer's
# incident endpoint, supporting their notification SLA (e.g. Maryland MD-SOC).

# Audit actions that are security-relevant enough to alert a SOC on.
SECURITY_EVENT_ACTIONS = {
    "login.fail", "login.locked", "2fa.enable", "2fa.disable",
    "password.reset", "security.policy", "session.logout_all",
}


def security_webhook_secret(account_id: int) -> str:
    """Deterministic per-account HMAC secret for verifying security-webhook posts.
    Derived from CONSOLE_SECRET so the customer can be shown a stable value to
    verify the `x-outlay-signature` header — no extra secret to store."""
    base = os.environ.get("CONSOLE_SECRET") or "dev-insecure-console-secret"
    return "swhsec_" + hmac.new(base.encode(), f"secwebhook:{account_id}".encode(),
                                hashlib.sha256).hexdigest()[:40]


def notify_security_event(account_id: int, action: str, actor: str = "", detail: str = "",
                          path: str | None = None, post_fn=None, now: float | None = None) -> bool:
    """Best-effort: POST a signed alert to the account's incident/breach webhook on a
    security event. Returns True if a post was dispatched. Never raises into the caller
    (auth flows must not break if the SOC endpoint is down)."""
    if action not in SECURITY_EVENT_ACTIONS:
        return False
    try:
        url = (get_security_policy(account_id, path) or {}).get("security_webhook")
        if not url:
            return False
        from . import notify
        if not notify.is_safe_url(url):
            return False
        body = json.dumps({"event": action, "ts": now or time.time(), "account_id": account_id,
                           "actor": actor, "detail": detail}, separators=(",", ":")).encode()
        headers = {"content-type": "application/json", "user-agent": "Outlay-Security",
                   "x-outlay-event": action,
                   "x-outlay-signature": sign_payload(security_webhook_secret(account_id), body)}

        def _send():
            try:
                _webhook_attempt(url, body, headers, post_fn)
            except Exception:  # noqa: BLE001 — fire-and-forget
                pass

        if post_fn is not None:  # tests / synchronous path
            _send()
        else:
            import threading
            threading.Thread(target=_send, daemon=True).start()
        return True
    except Exception:  # noqa: BLE001 — never break the auth flow on a webhook hiccup
        return False


WEBHOOK_MAX_ATTEMPTS = 3          # immediate, in-thread attempts on the first dispatch
WEBHOOK_BACKOFF = (0.0, 1.0, 3.0)  # seconds before attempts 1, 2, 3
WEBHOOK_MAX_TOTAL_ATTEMPTS = 8    # after which a failed delivery is given up ('dead')
# Backoff (seconds) before the Nth cron redelivery — escalating; with a daily cron
# anything under a day just means "next sweep". Indexed by redelivery number.
WEBHOOK_REDELIVER_BACKOFF = (3600, 6 * 3600, 24 * 3600, 24 * 3600, 24 * 3600)


def _webhook_headers(event_type: str, secret: str, body: bytes) -> dict:
    return {"content-type": "application/json", "user-agent": "Outlay-Webhook",
            "x-outlay-event": event_type, "x-outlay-signature": sign_payload(secret, body)}


def _webhook_attempt(url: str, body: bytes, headers: dict, post_fn=None) -> tuple:
    """One delivery attempt → (ok, status_code, error). `post_fn` (tests) may return
    an HTTP status int or raise to simulate failure."""
    if post_fn is not None:
        try:
            code = post_fn(url, body, headers)
        except Exception as e:  # noqa: BLE001 — capture, then retry/record
            return False, None, str(e)[:200]
        code = code if isinstance(code, int) else 200
        return (200 <= code < 300), code, ""
    from . import notify
    # SSRF guard, re-checked at delivery (not just at save) to blunt DNS rebinding,
    # and a no-redirect opener so a public URL can't 30x us to an internal address.
    if not notify.is_safe_url(url):
        return False, None, "blocked: url resolves to a private/internal address"
    import urllib.request
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        resp = notify._no_redirect_opener().open(req, timeout=5)
        code = getattr(resp, "status", 200)
        resp.close()
        return (200 <= code < 300), code, ""
    except Exception as e:  # noqa: BLE001 — capture, then retry/record
        code = getattr(e, "code", None)
        return False, code, str(e)[:200]


def record_webhook_delivery(account_id: int, webhook_id: int, event_type: str, status: str,
                            attempts: int = 1, status_code=None, error: str = "",
                            payload: str | None = None, next_attempt_at: float | None = None,
                            path: str | None = None, now: float | None = None) -> None:
    """Persist a webhook delivery so a dropped event is visible (not silently
    swallowed) and can be durably redelivered. `status`: delivered | failed | dead.
    A 'failed' row carries the signed `payload` + `next_attempt_at` so the cron can
    re-send it even across a process restart."""
    conn = connect(path)
    try:
        conn.execute(
            "INSERT INTO webhook_deliveries(account_id, webhook_id, event_type, status, attempts,"
            " status_code, error, payload, next_attempt_at, created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (account_id, webhook_id, event_type, status, attempts, status_code,
             (error or "")[:200], payload, next_attempt_at, now or time.time()))
        conn.commit()
    finally:
        conn.close()


def recent_webhook_deliveries(account_id: int, limit: int = 10, path: str | None = None) -> list[dict]:
    conn = connect(path)
    try:
        rows = conn.execute(
            "SELECT * FROM webhook_deliveries WHERE account_id=? ORDER BY id DESC LIMIT ?",
            (account_id, int(limit))).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def deliver_event(account_id: int, event_type: str, data: dict, path: str | None = None,
                  post_fn=None, sleep_fn=None) -> int:
    """Fire `event_type` to the account's subscribed webhooks (HMAC-signed,
    off-thread). Retries up to WEBHOOK_MAX_ATTEMPTS in-thread with backoff on failure
    / non-2xx; anything still failing is recorded with its signed payload + a
    next_attempt_at so the cron (`redeliver_due_webhooks`) re-sends it durably (even
    across a restart). Returns how many webhooks were dispatched. `post_fn` (tests)
    may return an HTTP status int or raise to simulate failure."""
    hooks = _matching_webhooks(account_id, event_type, path)
    if not hooks:
        return 0
    body = json.dumps({"event": event_type, "ts": time.time(), "data": data},
                      separators=(",", ":")).encode()
    _sleep = sleep_fn if sleep_fn is not None else time.sleep

    def _send(wid, url, secret):
        # Runs in a daemon thread for the live path — must never raise out of it
        # (an unhandled thread exception is noise at best, and the recording write
        # can fail, e.g. a transient DB lock). Best-effort, top to bottom.
        try:
            headers = _webhook_headers(event_type, secret, body)
            ok, code, err = False, None, ""
            for i in range(WEBHOOK_MAX_ATTEMPTS):
                if i and _sleep:
                    _sleep(WEBHOOK_BACKOFF[min(i, len(WEBHOOK_BACKOFF) - 1)])
                ok, code, err = _webhook_attempt(url, body, headers, post_fn)
                if ok:
                    break
            next_at = None if ok else (time.time() + WEBHOOK_REDELIVER_BACKOFF[0])
            record_webhook_delivery(account_id, wid, event_type,
                                    "delivered" if ok else "failed",
                                    attempts=i + 1, status_code=code, error=err,
                                    payload=(None if ok else body.decode("utf-8", "replace")),
                                    next_attempt_at=next_at, path=path)
        except Exception:  # noqa: BLE001 — delivery is best-effort; never crash the thread
            pass

    for w in hooks:
        if post_fn is not None:
            _send(w["id"], w["url"], w["secret"])
        else:
            import threading
            threading.Thread(target=_send, args=(w["id"], w["url"], w["secret"]), daemon=True).start()
    return len(hooks)


def redeliver_due_webhooks(now: float | None = None, path: str | None = None,
                           post_fn=None, limit: int = 200) -> dict:
    """Durably re-send failed webhook deliveries whose next_attempt_at has elapsed —
    one attempt per sweep. On success → 'delivered'; once WEBHOOK_MAX_TOTAL_ATTEMPTS
    is hit (or the webhook was deleted) → 'dead'; else reschedule with backoff.
    Resilient: returns a summary. Meant to ride the daily cron."""
    now = now or time.time()
    conn = connect(path)
    try:
        rows = conn.execute(
            "SELECT * FROM webhook_deliveries WHERE status='failed' AND next_attempt_at IS NOT NULL"
            " AND next_attempt_at <= ? ORDER BY id ASC LIMIT ?", (now, int(limit))).fetchall()
        rows = [dict(r) for r in rows]
    finally:
        conn.close()
    redelivered = failed = dead = 0
    for r in rows:
        hook = None
        for w in list_webhooks(r["account_id"], path):
            if w["id"] == r["webhook_id"]:
                hook = w
                break
        attempts = (r["attempts"] or 0) + 1
        body = (r["payload"] or "").encode()
        if hook is None or not body:
            # webhook deleted or no stored payload → nothing to redeliver to
            _update_delivery(r["id"], "dead", attempts, r["status_code"],
                             "webhook deleted" if hook is None else "no payload", None, path)
            dead += 1
            continue
        headers = _webhook_headers(r["event_type"], hook["secret"], body)
        ok, code, err = _webhook_attempt(hook["url"], body, headers, post_fn)
        if ok:
            _update_delivery(r["id"], "delivered", attempts, code, "", None, path)
            redelivered += 1
        elif attempts >= WEBHOOK_MAX_TOTAL_ATTEMPTS:
            _update_delivery(r["id"], "dead", attempts, code, err, None, path)
            dead += 1
        else:
            idx = min(attempts - WEBHOOK_MAX_ATTEMPTS, len(WEBHOOK_REDELIVER_BACKOFF) - 1)
            nxt = now + WEBHOOK_REDELIVER_BACKOFF[max(0, idx)]
            _update_delivery(r["id"], "failed", attempts, code, err, nxt, path)
            failed += 1
    return {"due": len(rows), "redelivered": redelivered, "failed": failed, "dead": dead}


def _update_delivery(delivery_id: int, status: str, attempts: int, status_code,
                     error: str, next_attempt_at, path: str | None = None) -> None:
    # Once a delivery is terminal (delivered/dead) drop its stored payload — it's the
    # exact event body (customer data) and only needed while the row can still retry.
    drop_payload = status != "failed"
    conn = connect(path)
    try:
        conn.execute(
            "UPDATE webhook_deliveries SET status=?, attempts=?, status_code=?, error=?,"
            " next_attempt_at=?" + (", payload=NULL" if drop_payload else "") + " WHERE id=?",
            (status, attempts, status_code, (error or "")[:200], next_attempt_at, delivery_id))
        conn.commit()
    finally:
        conn.close()


def prune_webhook_deliveries(now: float | None = None, keep_days: int = 30,
                             path: str | None = None) -> int:
    """Delete terminal (delivered/dead) delivery-log rows older than keep_days so the
    table doesn't grow without bound. 'failed' rows are the live redelivery queue and
    are never pruned here. Returns rows removed."""
    cutoff = (now or time.time()) - keep_days * 86400
    conn = connect(path)
    try:
        cur = conn.execute(
            "DELETE FROM webhook_deliveries WHERE status IN ('delivered','dead') AND created_at < ?",
            (cutoff,))
        conn.commit()
        return cur.rowcount or 0
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# SSO (OIDC) + SCIM provisioning (per account)
# --------------------------------------------------------------------------- #

def get_sso(account_id: int, path: str | None = None) -> dict:
    from . import secret_box
    conn = connect(path)
    try:
        row = conn.execute("SELECT * FROM sso_configs WHERE account_id=?", (account_id,)).fetchone()
        if not row:
            return {"account_id": account_id, "enabled": 0}
        d = dict(row)
        d["client_secret"] = secret_box.decrypt(d.get("client_secret"))  # OIDC secret, encrypted at rest
        return d
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
        from . import secret_box  # OIDC client_secret is a credential — encrypt at rest
        conn.execute("UPDATE sso_configs SET enabled=?, domain=?, client_id=?, client_secret=?,"
                     " auth_url=?, token_url=?, userinfo_url=?, default_role=? WHERE account_id=?",
                     (new["enabled"], new["domain"], new["client_id"],
                      secret_box.encrypt(new["client_secret"]),
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
    from . import secret_box
    conn = connect(path)
    try:
        row = conn.execute("SELECT * FROM sso_configs WHERE domain=? AND enabled=1", (domain,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["client_secret"] = secret_box.decrypt(d.get("client_secret"))
        return d
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


def account_cost_drivers(account_id: int, path: str | None = None) -> dict:
    """Per-account cost-to-serve drivers (admin/KTLO). Cheap counts + the live report
    size — fed to `cost_to_serve.estimate`. Outlay makes no LLM calls, so cost is infra:
    storage of the report + history, CPU per sync, a little egress + email."""
    report = get_outlay_report(account_id, path)
    report_bytes = len(json.dumps(report)) if report else 0
    tickets = len(report.get("tickets", [])) if report else 0
    conn = connect(path)
    try:
        def n(sql, *a):
            return conn.execute(sql, a).fetchone()[0] or 0
        history_rows = n("SELECT COUNT(*) FROM outlay_history WHERE account_id=?", account_id)
        prog_history_rows = n("SELECT COUNT(*) FROM outlay_program_history WHERE account_id=?", account_id)
        audit_rows = n("SELECT COUNT(*) FROM audit_log WHERE account_id=?", account_id)
        delivery_rows = n("SELECT COUNT(*) FROM webhook_deliveries WHERE account_id=?", account_id)
        webhooks = n("SELECT COUNT(*) FROM webhooks WHERE account_id=?", account_id)
        members = n("SELECT COUNT(*) FROM members WHERE account_id=? AND status!='removed'", account_id)
        crow = conn.execute(
            "SELECT auto_sync_hours, github_token, anthropic_key, cursor_key, jira_token, linear_key"
            " FROM outlay_connections WHERE account_id=?", (account_id,)).fetchone()
        rrow = conn.execute("SELECT retention_days FROM accounts WHERE id=?", (account_id,)).fetchone()
        srow = conn.execute(
            "SELECT digest_weekly, close_pack_monthly FROM accounts WHERE id=?", (account_id,)).fetchone()
    finally:
        conn.close()
    sync_hours = (crow["auto_sync_hours"] if crow else 0) or 0
    connectors = sum(1 for k in ("github_token", "anthropic_key", "cursor_key", "jira_token", "linear_key")
                     if crow and crow[k]) if crow else 0
    retention_days = (rrow["retention_days"] if rrow else 0) or 0
    emails_month = (4 if (srow and srow["digest_weekly"]) else 0) + \
                   (1 if (srow and srow["close_pack_monthly"]) else 0) + 1  # + occasional alerts
    return {"report_bytes": report_bytes, "tickets": tickets, "events": report_bytes // 250,
            "history_rows": history_rows, "prog_history_rows": prog_history_rows,
            "audit_rows": audit_rows, "delivery_rows": delivery_rows, "webhooks": webhooks,
            "members": members, "sync_hours": sync_hours, "connectors": connectors,
            "retention_days": retention_days, "emails_month": emails_month}


def fleet_cost_to_serve(path: str | None = None) -> dict:
    """Cost-to-serve rolled up across all accounts (admin overview)."""
    from . import cost_to_serve as cts
    accounts = [a for a in list_accounts(path) if a["status"] != "suspended"]
    n_active = max(1, len(accounts))
    rows = []
    total_marginal = total_loaded = 0.0
    for a in accounts:
        est = cts.estimate(account_cost_drivers(a["id"], path), active_accounts=n_active)
        total_marginal += est["marginal_monthly"]
        total_loaded += est["loaded_monthly"]
        rows.append({"id": a["id"], "email": a["email"], **est})
    rows.sort(key=lambda r: r["loaded_monthly"], reverse=True)
    return {"n_accounts": len(accounts), "fixed_monthly": cts.FLY_BASE_MONTHLY,
            "total_marginal_monthly": round(total_marginal, 4),
            "total_loaded_monthly": round(total_loaded, 4),
            "avg_loaded_per_account": round(total_loaded / n_active, 4),
            "top": rows[:8]}
