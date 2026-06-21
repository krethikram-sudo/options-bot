"""Create a single TEST CUSTOMER account so you can experience the new-user
onboarding flow (the first-run role gate + org-structure + invite steps) that the
vendor /admin account intentionally skips.

The account is created as a normal customer (an account *owner*) with **no
persona**, so the first login lands on the `/app/welcome` role gate — exactly what
a real first user from a company sees. It seeds no data.

Locally:
  CONSOLE_DB=console.db python -m console.create_test_customer you+test@example.com 'a-password'

On Fly (production console):
  fly ssh console -a modelpilot-console-prod \
    -C "python -m console.create_test_customer you+test@example.com 'a-password'"
  # then open  https://app.outlay-ai.com/login  and sign in as that email.

Idempotent and safe: it refuses to touch an existing account (pick a different
`+alias` email to make another). Email + password may also come from the
TEST_EMAIL / TEST_PASSWORD environment variables instead of argv.
"""

import os
import sys

from . import store

_WEAK = {"", "password", "changeme", "test", "secret", "12345678"}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    email = (argv[0] if len(argv) > 0 else os.environ.get("TEST_EMAIL", "")).strip().lower()
    pw = argv[1] if len(argv) > 1 else os.environ.get("TEST_PASSWORD", "")

    if not email or "@" not in email:
        print("Usage: python -m console.create_test_customer <email> <password>", file=sys.stderr)
        return 2
    if pw in _WEAK or len(pw) < 8:
        print("Choose a password of at least 8 characters (and not a common default).", file=sys.stderr)
        return 2

    store.init_db()
    if store.get_account_by_email(email) or store.get_member_by_email(email):
        print(f"{email} already exists — pick a different +alias to make another test account.",
              file=sys.stderr)
        return 1

    store.create_account(email, pw, company="Test Co", role="customer", consent=True)
    # No persona is set on purpose: the first login hits the onboarding role gate.
    print(f"Created test customer: {email}")
    print("Sign in at <your-console-url>/login — first login lands on the welcome role gate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
