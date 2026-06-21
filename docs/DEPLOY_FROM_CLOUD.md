# Deploy the console from a Claude Code *cloud* session (phone-friendly)

Goal: let a Claude Code **web/mobile** session run `fly deploy` itself, so you can
ship from your phone without dropping to your Mac. This is "Option B": the cloud
environment gets a **scoped Fly deploy token** + network access + `flyctl`.

> Everything below is configured in the Claude Code environment settings
> (https://code.claude.com/docs/en/claude-code-on-the-web), from your account —
> it can't be done from inside a running session. Do it once.

## What a session needs (all three, or deploy fails)

A probe from inside the cloud container on 2026-06-21 found **none** of these yet:

1. **Network policy must allow Fly hosts.** Today the egress proxy denies them
   (`HTTP 403  x-deny-reason: host_not_allowed` for `api.fly.io`,
   `registry.fly.io`, `fly.io`; `github.com` is allowed). Pick a network policy
   for the environment that permits at least:
   - `api.fly.io` — Fly Machines / GraphQL API
   - `registry.fly.io` — image push during deploy
   - `fly.io` — only needed for the official flyctl install script (skip if you
     install flyctl from its GitHub release instead — GitHub is already allowed)
2. **`flyctl` installed** — via the environment **setup script** (persists across
   sessions). See snippet below.
3. **`FLY_API_TOKEN`** — a **scoped, single-app deploy token** added as an
   environment secret (NOT your personal account token).

## Step 1 — create a least-privilege deploy token (on your Mac, once)

```bash
fly tokens create deploy -a modelpilot-console-prod
```
This prints a token (starts with `FlyV1 ...`). It can deploy **only** that app —
it can't read other apps, rotate secrets, or touch billing. Copy it.

Revoke anytime: `fly tokens list` then `fly tokens revoke <id>`.

## Step 2 — add it to the environment

In the environment settings, add a secret:
```
FLY_API_TOKEN = FlyV1 ...   (the token from step 1)
```

## Step 3 — install flyctl via the environment setup script

Paste this into the environment's **setup script** (runs when the container
starts). It installs flyctl from the official installer if `fly.io` is allowed,
otherwise falls back to the GitHub release (which is allowed):

```bash
# Install flyctl into ~/.fly and expose it on PATH
if ! command -v flyctl >/dev/null 2>&1; then
  if curl -fsSL https://fly.io/install.sh | sh; then
    :
  else
    # Fallback: pull the release tarball straight from GitHub (allowed host)
    ver=$(curl -fsSL https://api.github.com/repos/superfly/flyctl/releases/latest \
          | grep -m1 '"tag_name"' | cut -d'"' -f4)
    arch=$(uname -m); case "$arch" in x86_64) a=x86_64;; aarch64|arm64) a=arm64;; esac
    curl -fsSL "https://github.com/superfly/flyctl/releases/download/${ver}/flyctl_${ver#v}_Linux_${a}.tar.gz" \
      | tar -xz -C /usr/local/bin flyctl
  fi
fi
export FLYCTL_INSTALL="$HOME/.fly"
export PATH="$FLYCTL_INSTALL/bin:$PATH"
```

## Step 4 — verify (in a NEW cloud session, after saving the above)

Ask Claude (or run):
```bash
fly version
fly status -a modelpilot-console-prod          # auth works via FLY_API_TOKEN
```
If `fly status` lists the machine, you're set. Then a full deploy:
```bash
fly deploy -a modelpilot-console-prod
```
`fly deploy` builds `console/Dockerfile` from the repo root (the cloud session
already has the repo checked out) and pushes to `registry.fly.io`.

## Security notes

- The token is **app-scoped deploy-only** and lives only in this environment's
  secret store. Revoke it (`fly tokens revoke`) if the environment is ever
  shared or retired.
- Keep `fly secrets unset`, volume deletes, and app deletes as **manual /
  local-only** operations — a deploy token can't do most of them anyway.
- This does not affect the customer product; it only changes who can push the
  console image.

## After this is set up

"Ship the console" becomes something a phone-driven session can do end to end:
build → push → deploy → confirm `fly status`, with no trip to the Mac.
