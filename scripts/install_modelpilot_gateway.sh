#!/usr/bin/env bash
# Install the Maven gateway as a launchd agent: shadow mode + 25% prompt
# capture, auto-starts at login, restarts if it dies. Also adds a `claude`
# wrapper to ~/.zshrc that routes Claude Code through the gateway when it's
# up and falls back to direct API access when it isn't.
#
# Re-running is safe — it unloads first and the zshrc edit is idempotent.
#
# Usage:
#   ./scripts/install_modelpilot_gateway.sh                       # shadow mode
#   MODELPILOT_MODE=autopilot ./scripts/install_modelpilot_gateway.sh
set -euo pipefail

MODE="${MODELPILOT_MODE:-shadow}"
case "$MODE" in shadow|advise|autopilot) ;; *)
    echo "ERROR: MODELPILOT_MODE must be shadow|advise|autopilot (got '$MODE')" >&2; exit 1;;
esac

BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="$BOT_DIR/launchd/com.modelpilot.gateway.plist.template"
RENDERED="$BOT_DIR/launchd/com.modelpilot.gateway.plist"
TARGET="$HOME/Library/LaunchAgents/com.modelpilot.gateway.plist"

if [ ! -x "$BOT_DIR/venv/bin/python" ]; then
    echo "No venv found — creating one at $BOT_DIR/venv"
    python3 -m venv "$BOT_DIR/venv"
fi

if ! "$BOT_DIR/venv/bin/python" -c "import uvicorn, fastapi, httpx" 2>/dev/null; then
    echo "Installing modelpilot dependencies into the venv..."
    "$BOT_DIR/venv/bin/pip" install -q -r "$BOT_DIR/modelpilot/requirements.txt"
fi

mkdir -p "$BOT_DIR/logs"

echo "Rendering plist with BOT_DIR=$BOT_DIR MODE=$MODE"
sed -e "s|__BOT_DIR__|$BOT_DIR|g" -e "s|__MODE__|$MODE|g" "$TEMPLATE" > "$RENDERED"

mkdir -p "$HOME/Library/LaunchAgents"
cp "$RENDERED" "$TARGET"
echo "Installed $TARGET"

UID_NUM="$(id -u)"
launchctl bootout "gui/$UID_NUM" "$TARGET" 2>/dev/null || true
sleep 1
launchctl bootstrap "gui/$UID_NUM" "$TARGET"
sleep 2

# Route Claude Code through the gateway when it's healthy; fall back silently.
ZSHRC="$HOME/.zshrc"
MARKER="# modelpilot-claude-wrapper"
if ! grep -qF "$MARKER" "$ZSHRC" 2>/dev/null; then
    cat >> "$ZSHRC" <<'SNIPPET'

# modelpilot-claude-wrapper — route Claude Code through the local Maven
# gateway (shadow mode) when it's running; fall back to direct API otherwise.
# Remove this block to undo.
claude() {
  if curl -sf -m 1 http://127.0.0.1:8400/modelpilot/stats >/dev/null 2>&1; then
    ANTHROPIC_BASE_URL=http://127.0.0.1:8400 command claude "$@"
  else
    command claude "$@"
  fi
}
SNIPPET
    echo "Added claude() wrapper to $ZSHRC (open a new terminal to pick it up)"
else
    echo "claude() wrapper already present in $ZSHRC"
fi

echo
echo "Status:"
if launchctl list | grep -q com.modelpilot.gateway; then
    sleep 1
    if curl -sf -m 2 http://127.0.0.1:8400/modelpilot/stats >/dev/null 2>&1; then
        echo "  gateway is UP at http://127.0.0.1:8400 ($MODE mode, 25% prompt capture)"
    else
        echo "  agent loaded; gateway still starting — check logs/modelpilot.gateway.err.log if it stays down"
    fi
else
    echo "  NOT running — check $BOT_DIR/logs/modelpilot.gateway.err.log"
fi
echo
echo "Dashboard:   open http://127.0.0.1:8400/modelpilot/dashboard"
echo "Uninstall:   launchctl bootout gui/$UID_NUM $TARGET && rm $TARGET  (and remove the wrapper block from ~/.zshrc)"
