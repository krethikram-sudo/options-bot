#!/usr/bin/env bash
# Render the launchd plist template with this user's bot directory, install
# it into ~/Library/LaunchAgents/, and (re)load it so the bot starts now and
# at every login. Re-running this script is safe — it unloads first.
#
# Usage:
#   ./scripts/install_launchd.sh
set -euo pipefail

BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="$BOT_DIR/launchd/com.options-bot.live.plist.template"
RENDERED="$BOT_DIR/launchd/com.options-bot.live.plist"
TARGET="$HOME/Library/LaunchAgents/com.options-bot.live.plist"

if [ ! -f "$TEMPLATE" ]; then
    echo "ERROR: template not found at $TEMPLATE" >&2
    exit 1
fi

if [ ! -x "$BOT_DIR/venv/bin/python" ]; then
    echo "ERROR: no venv at $BOT_DIR/venv. Run:" >&2
    echo "  python3 -m venv venv && ./venv/bin/pip install -r requirements.txt" >&2
    exit 1
fi

if [ ! -f "$BOT_DIR/.env" ]; then
    echo "ERROR: no .env at $BOT_DIR/.env. Copy .env.example and fill it in first." >&2
    exit 1
fi

echo "Rendering plist with BOT_DIR=$BOT_DIR"
sed "s|__BOT_DIR__|$BOT_DIR|g" "$TEMPLATE" > "$RENDERED"

mkdir -p "$HOME/Library/LaunchAgents"
cp "$RENDERED" "$TARGET"
echo "Installed $TARGET"

# Unload any existing instance, then load. Bootout is no-op if not loaded.
UID_NUM="$(id -u)"
launchctl bootout "gui/$UID_NUM" "$TARGET" 2>/dev/null || true
sleep 1
launchctl bootstrap "gui/$UID_NUM" "$TARGET"
sleep 2

echo
echo "Status:"
launchctl list | grep com.options-bot.live || echo "(not running — check $BOT_DIR/logs/live.err.log)"
echo
echo "Done. Tail logs with:"
echo "  tail -f $BOT_DIR/logs/live.out.log"
