"""Create (or report) the single vendor ADMIN account — no demo data.

Use this on a fresh PRODUCTION deployment so you can log in at /login and land on
/admin. Unlike `console.seed`, this creates ONLY your admin account (no demo
customers, no synthetic metering). Idempotent: if the email already exists as an
admin, it does nothing; it refuses weak/default passwords.

Locally:
  CONSOLE_DB=console.db ADMIN_EMAIL=you@co.com ADMIN_PASSWORD='strong-passphrase' \
    python -m console.create_admin

On Fly (after `fly secrets set ADMIN_EMAIL=... ADMIN_PASSWORD=...`):
  fly ssh console -C "python -m console.create_admin"
  # then: fly secrets unset ADMIN_PASSWORD
"""

import os
import sys

from . import store

_WEAK = {"", "changeme-admin-pw", "password", "admin", "secret", "changeme"}


def main() -> int:
    email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    pw = os.environ.get("ADMIN_PASSWORD", "")
    if not email or "@" not in email:
        print("Set ADMIN_EMAIL to a real email address.", file=sys.stderr)
        return 2
    if pw in _WEAK or len(pw) < 10:
        print("Set ADMIN_PASSWORD to a strong value (>= 10 chars, not a default).", file=sys.stderr)
        return 2

    store.init_db()
    existing = store.get_account_by_email(email)
    if existing:
        if existing.get("role") != "admin":
            print(f"An account for {email} already exists with role={existing.get('role')!r}, "
                  f"not admin. Use a different email for the admin login.", file=sys.stderr)
            return 1
        print(f"Admin already exists: {email} (no change).")
        return 0

    store.create_account(email, pw, company="ModelPilot", role="admin", consent=True)
    print(f"Created admin: {email}")
    print("Log in at <your-console-url>/login — you'll be routed to /admin.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
