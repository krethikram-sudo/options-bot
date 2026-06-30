"""Create a single regular (non-admin) TEST/EVALUATION account — for handing a
partner a ready login to explore the product. No demo data is seeded here; demo
access is granted separately by putting the account's email (or its whole domain,
e.g. `@outlay-ai.com`) in the `DEMO_ACCOUNT_EMAILS` env var, after which the
account can one-click load the sample dataset from the app.

Idempotent: if the email already exists it does nothing (and won't clobber an
admin). Refuses weak/short passwords (NIST 800-63B, same rule as signup).

Locally:
  CONSOLE_DB=console.db TEST_EMAIL=partner@outlay-ai.com TEST_PASSWORD='strong-passphrase' \
    python -m console.create_test_account

On Fly (after `fly secrets set TEST_EMAIL=... TEST_PASSWORD=...`):
  fly ssh console -C "python -m console.create_test_account"
  # then: fly secrets unset TEST_PASSWORD
"""

import os
import sys

from . import store


def main() -> int:
    email = os.environ.get("TEST_EMAIL", "").strip().lower()
    pw = os.environ.get("TEST_PASSWORD", "")
    if not email or "@" not in email:
        print("Set TEST_EMAIL to a real email address.", file=sys.stderr)
        return 2
    # Reuse the exact signup password policy so this can never create a login the
    # app itself would reject.
    problem = store.password_problem(pw)
    if problem:
        print(f"TEST_PASSWORD rejected: {problem}", file=sys.stderr)
        return 2

    store.init_db()
    existing = store.get_account_by_email(email)
    if existing:
        print(f"Account already exists: {email} (role={existing.get('role')!r}, no change).")
        return 0

    store.create_account(email, pw, company="Partner Eval", role="customer", consent=True)
    print(f"Created test account: {email}")
    print("Log in at <your-console-url>/login.")
    print("To preload the sample dataset, ensure this email (or its @domain) is in "
          "DEMO_ACCOUNT_EMAILS, then click 'Enter demo mode' / 'See it with sample data'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
