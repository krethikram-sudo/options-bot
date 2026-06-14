"""ModelPilot console — data layer (SQLite).

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
import os
import secrets
import sqlite3
import time
from datetime import datetime, timezone

TRIAL_DAYS = 7
DEFAULT_RATE = 0.20            # we bill 20% of realized savings
DAY = 86_400
SESSION_TTL = 14 * DAY
MODES = ("shadow", "guidance", "autopilot")
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
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS deployments (
    deployment_id TEXT PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    label TEXT,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    account_id INTEGER PRIMARY KEY REFERENCES accounts(id),
    mode TEXT NOT NULL DEFAULT 'guidance',
    telemetry_opt_in INTEGER NOT NULL DEFAULT 1,
    min_model TEXT NOT NULL DEFAULT '',
    risk TEXT NOT NULL DEFAULT 'balanced'
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
    stripe_reported INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_meter_dep ON meter(deployment_id);
CREATE INDEX IF NOT EXISTS idx_meter_ts ON meter(ts);
"""


def init_db(path: str | None = None) -> None:
    conn = connect(path)
    try:
        conn.executescript(SCHEMA)
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


def make_session(account_id: int, role: str, path: str | None = None) -> str:
    payload = f"{account_id}:{role}:{int(time.time())}"
    sig = hmac.new(_secret(path), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def read_session(token: str, path: str | None = None) -> dict | None:
    try:
        account_id, role, issued, sig = token.rsplit(":", 3)
    except (ValueError, AttributeError):
        return None
    payload = f"{account_id}:{role}:{issued}"
    expected = hmac.new(_secret(path), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    if time.time() - float(issued) > SESSION_TTL:
        return None
    return {"account_id": int(account_id), "role": role, "issued": float(issued)}


# --------------------------------------------------------------------------- #
# Accounts
# --------------------------------------------------------------------------- #

class StoreError(ValueError):
    pass


def create_account(email: str, password: str, company: str = "", role: str = "customer",
                   path: str | None = None, now: float | None = None) -> dict:
    """Create an account + its deployment + default settings + a started trial."""
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
                "INSERT INTO accounts(email, company, pw_hash, pw_salt, role, status, created_at)"
                " VALUES(?,?,?,?,?, 'active', ?)",
                (email, company.strip(), pw_hash, salt, role, now))
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


def update_settings(account_id: int, *, mode: str | None = None,
                    telemetry_opt_in: bool | None = None, min_model: str | None = None,
                    risk: str | None = None, path: str | None = None) -> dict:
    if mode is not None and mode not in MODES:
        raise StoreError(f"mode must be one of {MODES}")
    if risk is not None and risk not in RISK_LEVELS:
        raise StoreError(f"risk must be one of {RISK_LEVELS}")
    cur = get_settings(account_id, path)
    new = {
        "mode": cur["mode"] if mode is None else mode,
        "telemetry_opt_in": cur["telemetry_opt_in"] if telemetry_opt_in is None else int(telemetry_opt_in),
        "min_model": cur["min_model"] if min_model is None else min_model,
        "risk": cur["risk"] if risk is None else risk,
    }
    conn = connect(path)
    try:
        conn.execute("UPDATE settings SET mode=?, telemetry_opt_in=?, min_model=?, risk=?"
                     " WHERE account_id=?",
                     (new["mode"], new["telemetry_opt_in"], new["min_model"], new["risk"], account_id))
        conn.commit()
    finally:
        conn.close()
    return get_settings(account_id, path)


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
    else:
        ts = trial_status(acct["id"], path, now)
        entitled = ts["active"]
        reason = f"trial ({ts['days_left']}d left)" if entitled else "trial ended"
    apply = entitled and mode == "autopilot"
    return {"entitled": entitled, "apply": apply, "mode": mode, "reason": reason,
            "account_id": acct["id"], "plan": plan.get("plan", "trial")}


# --------------------------------------------------------------------------- #
# Metering + savings + billing
# --------------------------------------------------------------------------- #

def record_meter(deployment_id: str, *, requests: int = 0, routed: int = 0,
                 escalations: int = 0, baseline_cost: float = 0.0, actual_cost: float = 0.0,
                 realized_savings: float | None = None, category: str | None = None,
                 ts: float | None = None, path: str | None = None) -> dict:
    """Record one aggregate metering report from a gateway. Dollars + counts only.

    `realized_savings` defaults to baseline_cost - actual_cost (never negative for
    billing). Raises if the deployment is unknown."""
    if not account_for_deployment(deployment_id, path):
        raise StoreError("unknown deployment")
    if realized_savings is None:
        realized_savings = max(0.0, baseline_cost - actual_cost)
    ts = ts or time.time()
    conn = connect(path)
    try:
        conn.execute(
            "INSERT INTO meter(deployment_id, ts, category, requests, routed, escalations,"
            " baseline_cost, actual_cost, realized_savings) VALUES(?,?,?,?,?,?,?,?,?)",
            (deployment_id, ts, category, int(requests), int(routed), int(escalations),
             float(baseline_cost), float(actual_cost), float(realized_savings)))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "realized_savings": realized_savings}


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
        f" COALESCE(SUM(m.realized_savings),0) AS savings"
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
    n_trial = n_paid = n_suspended = 0
    for a in accounts:
        if a["status"] == "suspended":
            n_suspended += 1
        plan = get_plan(a["id"], path)
        rate = plan.get("rate", DEFAULT_RATE)
        life = savings_summary(a["id"], path=path)["savings"]
        cyc_s = savings_summary(a["id"], since=cyc, path=path)["savings"]
        total_savings += life
        cycle_savings += cyc_s
        if plan.get("plan") == "paid":
            n_paid += 1
            total_revenue += rate * life
            cycle_revenue += rate * cyc_s
        else:
            n_trial += 1
    return {
        "n_accounts": len(accounts), "n_trial": n_trial, "n_paid": n_paid,
        "n_suspended": n_suspended,
        "total_savings_delivered": round(total_savings, 2),
        "total_revenue": round(total_revenue, 2),
        "cycle_savings": round(cycle_savings, 2),
        "cycle_revenue": round(cycle_revenue, 2),
    }
